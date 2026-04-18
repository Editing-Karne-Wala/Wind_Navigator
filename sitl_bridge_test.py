# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR -- Phase 23: SITL Integration Test (pymavlink native)
=====================================================================
Uses pymavlink directly (no dronekit) -- the same library as mavlink_bridge.py.
Starts ArduCopter SITL via dronekit-sitl, then connects with pymavlink,
arms, takes off, and validates the vortex prediction -> command loop.

Run:
    python sitl_bridge_test.py

Exit: Ctrl+C after observations are logged
"""

import json, math, os, sys, time, threading, subprocess
from datetime import datetime, timezone
from mavlink_bridge import predict_vortex_ahead, MAVLinkBridge, VORTEX_THRESHOLD

LOG_FILE = 'phase23_sitl_log.json'
log_entries = []

# â”€â”€ Scenarios â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
SCENARIO_VORTEX = {"fleet": [{"id": 0, "drone_model": "Heavy-Lift Hexa",
    "payload_kg": 10.0, "waypoint": 5, "total_waypoints": 109,
    "chaos": 38, "confidence": "LOW", "speed_factor": 1.0,
    "crashed": False, "mission_complete": False}]}
SCENARIO_CLEAR  = {"fleet": [{"id": 0, "drone_model": "Heavy-Lift Hexa",
    "payload_kg": 10.0, "waypoint": 5, "total_waypoints": 109,
    "chaos":  2, "confidence": "HIGH", "speed_factor": 1.0,
    "crashed": False, "mission_complete": False}]}

def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).isoformat()
    log_entries.append({"ts": ts, "level": level, "msg": msg})
    icon = {"INFO": "*", "ACTION": "!", "WARN": "~", "ERROR": "X", "PASS": "+"}
    print(f"  [{icon.get(level,'*')}] {msg}")


# â”€â”€ SITL startup via dronekit-sitl â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def start_sitl():
    try:
        import dronekit_sitl
        log("Starting ArduCopter SITL (NYC coords: 40.748817, -73.985428)...")
        sitl = dronekit_sitl.start_default(lat=40.748817, lon=-73.985428)
        conn = sitl.connection_string()
        log(f"SITL process started | connection: {conn}")
        return sitl, conn
    except Exception as e:
        log(f"SITL start failed: {e}", "WARN")
        return None, None


# â”€â”€ pymavlink arm + takeoff â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def pymav_arm_takeoff(master, target_alt):
    """Arm and takeoff using raw pymavlink commands."""
    from pymavlink import mavutil

    log(f"Waiting for heartbeat...")
    master.wait_heartbeat(timeout=15)
    log(f"Heartbeat OK: sys={master.target_system} comp={master.target_component}")

    # Set GUIDED mode (mode 4 in ArduCopter)
    log("Setting GUIDED mode...")
    master.set_mode('GUIDED')
    time.sleep(1.0)

    # Arm
    log("Arming motors...")
    master.arducopter_arm()
    t0 = time.time()
    while time.time() - t0 < 10:
        hb = master.recv_match(type='HEARTBEAT', blocking=True, timeout=2)
        if hb and hb.base_mode & 0x80:   # MAV_MODE_FLAG_SAFETY_ARMED
            log("Motors ARMED", "PASS")
            break
        time.sleep(0.5)

    # Takeoff
    log(f"Commanding takeoff to {target_alt}m...")
    master.mav.command_long_send(
        master.target_system, master.target_component,
        22,       # MAV_CMD_NAV_TAKEOFF
        0,        # confirmation
        0, 0, 0, 0,    # params 1-4 unused
        0, 0,          # params 5-6 unused
        float(target_alt))  # param 7 = altitude

    t0 = time.time()
    peak_alt = 0.0
    while time.time() - t0 < 30:
        msg = master.recv_match(type='VFR_HUD', blocking=True, timeout=2)
        if msg:
            alt = msg.alt
            peak_alt = max(peak_alt, alt)
            log(f"  Alt: {alt:.1f}m | Airspeed: {msg.airspeed:.1f}m/s "
                f"| Throttle: {msg.throttle}%")
            if alt >= target_alt * 0.85:
                log(f"Reached {alt:.1f}m (target {target_alt}m)", "PASS")
                break
        time.sleep(1.0)
    return peak_alt


# â”€â”€ Prediction test loop â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def run_prediction_tests(bridge):
    results = {"passed": 0, "failed": 0, "tests": []}

    # Test 1: Vortex -> HOLD
    log("â”€â”€â”€ Test 1: Vortex scenario (chaos=38, LOW confidence) â”€â”€â”€")
    p = predict_vortex_ahead(SCENARIO_VORTEX, 12.0)[0]
    log(f"  danger={p['danger_score']} | alert={p['vortex_alert']} "
        f"| lookahead_wp={p['wp_lookahead']}")
    if p['vortex_alert']:
        msg = f"D0 VORTEX {p['danger_score']:.0f} @WP{p['wp_lookahead']} HOLD"
        bridge.send_statustext(msg, severity=3)
        bridge.send_hold(8.0)
        log(f"  -> Sent HOLD: '{msg}'", "ACTION")
        results["passed"] += 1
        results["tests"].append({"test": "vortex_detect", "status": "PASS",
                                  "danger": p['danger_score'], "wp": p['wp_lookahead']})
    else:
        log("  -> Expected alert=True, got False", "ERROR")
        results["failed"] += 1
        results["tests"].append({"test": "vortex_detect", "status": "FAIL"})
    time.sleep(1.5)

    # Test 2: Clear -> PROCEED
    log("â”€â”€â”€ Test 2: Clear scenario (chaos=2, HIGH confidence) â”€â”€â”€")
    p2 = predict_vortex_ahead(SCENARIO_CLEAR, 12.0)[0]
    log(f"  danger={p2['danger_score']} | alert={p2['vortex_alert']}")
    if not p2['vortex_alert']:
        bridge.send_statustext("D0 PATH CLEAR -- PROCEED", severity=6)
        bridge.send_proceed()
        log("  -> Sent PROCEED", "ACTION")
        results["passed"] += 1
        results["tests"].append({"test": "clear_proceed", "status": "PASS",
                                  "danger": p2['danger_score']})
    else:
        log("  -> Expected alert=False, got True", "ERROR")
        results["failed"] += 1
        results["tests"].append({"test": "clear_proceed", "status": "FAIL"})
    time.sleep(1.5)

    # Test 3: Threshold boundary (chaos=20 exactly)
    log("â”€â”€â”€ Test 3: Boundary (chaos=20, threshold=20) â”€â”€â”€")
    boundary = {"fleet": [dict(SCENARIO_VORTEX["fleet"][0], chaos=20)]}
    p3 = predict_vortex_ahead(boundary, 12.0)[0]
    expected = p3['danger_score'] >= VORTEX_THRESHOLD
    log(f"  danger={p3['danger_score']} | alert={p3['vortex_alert']} | "
        f"expected={'ALERT' if expected else 'CLEAR'}")
    if p3['vortex_alert'] == expected:
        log("  -> Threshold boundary correct", "PASS")
        results["passed"] += 1
        results["tests"].append({"test": "threshold_boundary", "status": "PASS",
                                  "danger": p3['danger_score']})
    else:
        results["failed"] += 1
        results["tests"].append({"test": "threshold_boundary", "status": "FAIL"})

    return results


# â”€â”€ Main â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def main():
    print("=" * 65)
    print("WIND_NAVIGATOR  Phase 23 -- SITL Bridge Test (pymavlink)")
    print("=" * 65)

    sitl   = None
    master = None
    peak_alt = 0.0
    vehicle_connected = False

    # â”€â”€ Start SITL â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    sitl, conn_str = start_sitl()

    if conn_str:
        try:
            from pymavlink import mavutil
            log(f"pymavlink connecting to {conn_str}...")
            master = mavutil.mavlink_connection(conn_str, autoreconnect=True)
            vehicle_connected = True
            peak_alt = pymav_arm_takeoff(master, target_alt=10)
        except Exception as e:
            log(f"pymavlink connect/arm failed: {e}", "WARN")
            log("Continuing with prediction-only tests...")

    # â”€â”€ Create bridge (dry-run to log commands without re-sending) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    bridge = MAVLinkBridge(conn_str or "dry-run")
    # If we have an active MAVLink master, give it to the bridge
    if master and vehicle_connected:
        bridge.mav = master
        bridge.connected = True
        log("Bridge using LIVE pymavlink connection to SITL", "PASS")
    else:
        bridge.connected = False
        log("Bridge in dry-run mode (command output printed, not sent)")

    # â”€â”€ Prediction + command tests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    results = run_prediction_tests(bridge)

    # â”€â”€ Print results â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print("\n" + "=" * 65)
    total  = results["passed"] + results["failed"]
    print(f"RESULTS: {results['passed']}/{total} tests PASSED")
    for t in results["tests"]:
        icon = "OK" if t["status"] == "PASS" else "!!"
        extra = f"danger={t.get('danger','?')}" if 'danger' in t else ''
        print(f"  [{icon}] {t['test']:28s} {t['status']:6s}  {extra}")
    print("=" * 65)

    # â”€â”€ Save log â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    final_log = {
        "phase": 23,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sitl_started": sitl is not None,
        "vehicle_connected": vehicle_connected,
        "peak_altitude_m": round(peak_alt, 1),
        "results": results,
        "log": log_entries,
    }
    with open(LOG_FILE, 'w') as f:
        json.dump(final_log, f, indent=2)
    print(f"\n[+] Log saved to {LOG_FILE}")

    # â”€â”€ Teardown â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if master:
        master.close()
    if sitl:
        sitl.stop()
        log("SITL process stopped")
    print("[+] Phase 23 test complete.")


if __name__ == '__main__':
    main()

