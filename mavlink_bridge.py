# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR -- Phase 23: Real Hardware Bridge
=================================================
Connects the simulation vortex prediction engine to a live physical drone
via MAVLink (pymavlink). The sim runs ahead of the hardware by LOOKAHEAD_S
seconds, predicts which vortex zones are on the approach path, and sends:

  STATUSTEXT   "VORTEX AHEAD 12s -- HOLD"
  SET_MODE     GUIDED (if danger > threshold)
  COMMAND_LONG MAV_CMD_CONDITION_DELAY (hold N seconds)

Or if safe:
  STATUSTEXT   "PATH CLEAR -- PROCEED"
  SET_MODE     AUTO

Architecture:
  - mavlink_bridge.py runs as a background thread
  - Reads sim_state.json at 5Hz to get current prediction
  - Sends MAVLink messages to the physical drone (UDP or serial)
  - Writes hardware_state.json for dashboard display

Hardware connection options:
  A) USB serial:   /dev/ttyUSB0 or COM5 at 57600 baud
  B) UDP telemetry: udp:192.168.1.x:14550  (Mission Planner style)
  C) TCP sitl:     tcp:127.0.0.1:5760     (SITL for dry-run test)

Usage:
  python mavlink_bridge.py --connect udp:127.0.0.1:14550
  python mavlink_bridge.py --connect COM5 --baud 57600
  python mavlink_bridge.py --sitl   (connects to ArduPilot SITL, no hardware needed)
"""

import argparse, json, math, os, sys, time, threading
from datetime import datetime, timezone

try:
    from pymavlink import mavutil
    MAVLINK_AVAILABLE = True
except ImportError:
    MAVLINK_AVAILABLE = False
    print("[!] pymavlink not installed -- running in SIMULATION-ONLY mode")
    print("    Install: pip install pymavlink")

LOOKAHEAD_S      = 12.0   # seconds ahead to predict (12s at 5m/s = 60m lookahead)
POLL_HZ          = 5      # how often to read sim_state.json
VORTEX_THRESHOLD = 15.0  # TI% >= 15% = FAA moderate turbulence HOLD criterion
                          # Source: FAA AC 00-30C / ICAO Doc 9817 / EASA PDRA-G02
                          # (was: 20, arbitrary integer -- Phase 24 fix)
STATE_FILE       = 'sim_state.json'
HW_STATE_FILE    = 'hardware_state.json'

# ── Vortex prediction from sim state ──────────────────────────────────────────
def predict_vortex_ahead(sim_state: dict, lookahead_s: float) -> dict:
    """
    Reads fleet telemetry from sim_state.json.
    For each drone: looks LOOKAHEAD_WP waypoints ahead of current wp_idx.
    Returns a prediction dict per drone.
    """
    predictions = {}
    fleet = sim_state.get('fleet', [])

    for drone in fleet:
        did      = drone['id']
        wp_now   = drone.get('waypoint', 0)
        wp_total = drone.get('total_waypoints', 1)
        chaos    = drone.get('chaos', 0.0)    # Phase 24: now TI%
        conf     = drone.get('confidence', 'HIGH')

        # Estimate waypoints per second
        wps_sec  = max(0.1, 1.5 / (1.0 + pl_kg * 0.04)) * speed_f
        wp_ahead = int(wp_now + lookahead_s * wps_sec)
        wp_ahead = min(wp_ahead, wp_total - 1)

        # Danger score IS the TI% -- no multiplier needed (TI already meaningful)
        danger = chaos

        predictions[did] = {
            'drone_id':       did,
            'model':          drone.get('drone_model', '?'),
            'wp_now':         wp_now,
            'wp_lookahead':   wp_ahead,
            'danger_score':   round(danger, 1),
            'vortex_alert':   danger >= VORTEX_THRESHOLD,
            'confidence':     conf,
            'crashed':        drone.get('crashed', False),
            'mission_complete': drone.get('mission_complete', False),
        }
    return predictions


# ── MAVLink command sender ────────────────────────────────────────────────────
class MAVLinkBridge:
    def __init__(self, connection_str: str, baud: int = 57600):
        self.conn_str   = connection_str
        self.baud       = baud
        self.mav        = None
        self.connected  = False
        self.last_send  = {}
        self._lock      = threading.Lock()

    def connect(self):
        if not MAVLINK_AVAILABLE:
            print("[~] pymavlink not available -- dry-run mode")
            self.connected = False
            return False
        try:
            print(f"[*] Connecting to hardware: {self.conn_str} ...")
            self.mav = mavutil.mavlink_connection(
                self.conn_str, baud=self.baud, autoreconnect=True)
            self.mav.wait_heartbeat(timeout=10)
            print(f"[+] Heartbeat received! System {self.mav.target_system}, "
                  f"Component {self.mav.target_component}")
            self.connected = True
            return True
        except Exception as e:
            print(f"[!] MAVLink connection failed: {e}")
            self.connected = False
            return False

    def send_statustext(self, text: str, severity: int = 6):
        """Send a text message to GCS/drone. severity: 0=EMERGENCY 6=INFO"""
        if not self.connected:
            print(f"    [DRY-RUN] STATUSTEXT: {text}")
            return
        try:
            with self._lock:
                self.mav.mav.statustext_send(severity, text[:50].encode())
        except Exception as e:
            print(f"[!] statustext send failed: {e}")

    def send_hold(self, duration_s: float = 8.0):
        """Command drone to hold position for duration_s seconds."""
        if not self.connected:
            print(f"    [DRY-RUN] HOLD {duration_s:.0f}s")
            return
        try:
            with self._lock:
                # MAV_CMD_CONDITION_DELAY = 159
                self.mav.mav.command_long_send(
                    self.mav.target_system,
                    self.mav.target_component,
                    159,   # MAV_CMD_CONDITION_DELAY
                    0,     # confirmation
                    duration_s, 0, 0, 0, 0, 0, 0)
        except Exception as e:
            print(f"[!] hold command failed: {e}")

    def send_proceed(self):
        """Resume autonomous flight after a hold."""
        if not self.connected:
            print(f"    [DRY-RUN] PROCEED")
            return
        try:
            with self._lock:
                # MAV_CMD_DO_CONTINUE_AND_CHANGE_ALT = 30
                self.mav.mav.command_long_send(
                    self.mav.target_system,
                    self.mav.target_component,
                    30, 0, 0, 0, 0, 0, 0, 0, 0)
        except Exception as e:
            print(f"[!] proceed command failed: {e}")

    def read_telemetry(self) -> dict:
        """Read latest telemetry from physical drone."""
        if not self.connected:
            return {}
        try:
            msg = self.mav.recv_match(
                type=['ATTITUDE', 'GLOBAL_POSITION_INT', 'VFR_HUD'],
                blocking=False)
            if msg is None:
                return {}
            t = msg.get_type()
            if t == 'VFR_HUD':
                return {
                    'hw_airspeed_ms': round(msg.airspeed, 2),
                    'hw_groundspeed_ms': round(msg.groundspeed, 2),
                    'hw_alt_m': round(msg.alt, 1),
                    'hw_climb_ms': round(msg.climb, 2),
                    'hw_throttle_pct': msg.throttle,
                }
            if t == 'ATTITUDE':
                return {
                    'hw_roll_deg':  round(math.degrees(msg.roll), 1),
                    'hw_pitch_deg': round(math.degrees(msg.pitch), 1),
                    'hw_yaw_deg':   round(math.degrees(msg.yaw), 1),
                }
        except Exception:
            pass
        return {}


# ── Bridge main loop ──────────────────────────────────────────────────────────
def run_bridge(bridge: MAVLinkBridge, poll_hz: int = POLL_HZ):
    interval  = 1.0 / poll_hz
    in_hold   = {}   # drone_id -> bool
    hw_telem  = {}

    print(f"[*] Bridge running at {poll_hz}Hz | lookahead={LOOKAHEAD_S}s "
          f"| vortex_threshold={VORTEX_THRESHOLD}")

    while True:
        t0 = time.time()

        # Read sim prediction
        try:
            with open(STATE_FILE) as f:
                sim = json.load(f)
        except Exception:
            time.sleep(interval)
            continue

        preds = predict_vortex_ahead(sim, LOOKAHEAD_S)

        # Read live hardware telemetry
        if bridge.connected:
            hw = bridge.read_telemetry()
            if hw:
                hw_telem.update(hw)

        # Act on predictions
        actions = []
        for did, pred in preds.items():
            if pred['crashed'] or pred['mission_complete']:
                continue

            if pred['vortex_alert'] and not in_hold.get(did, False):
                # Issue HOLD + STATUSTEXT warning
                msg = (f"D{did} VORTEX {pred['danger_score']:.0f} "
                       f"@WP{pred['wp_lookahead']} HOLD")
                bridge.send_statustext(msg, severity=3)  # 3=WARNING
                bridge.send_hold(duration_s=8.0)
                in_hold[did] = True
                actions.append({'drone': did, 'action': 'HOLD',
                                'danger': pred['danger_score'],
                                'wp_ahead': pred['wp_lookahead']})
                print(f"  [!!!] {msg}")

            elif not pred['vortex_alert'] and in_hold.get(did, False):
                # Clear: send PROCEED
                bridge.send_statustext(f"D{did} PATH CLEAR -- PROCEED", severity=6)
                bridge.send_proceed()
                in_hold[did] = False
                actions.append({'drone': did, 'action': 'PROCEED'})
                print(f"  [+] Drone {did} path clear -- PROCEED")

        # Write hardware_state.json for dashboard
        hw_state = {
            'timestamp':    datetime.now(timezone.utc).isoformat(),
            'connected':    bridge.connected,
            'connection':   bridge.conn_str,
            'lookahead_s':  LOOKAHEAD_S,
            'predictions':  preds,
            'actions':      actions,
            'hw_telemetry': hw_telem,
            'in_hold':      in_hold,
        }
        try:
            with open(HW_STATE_FILE, 'w') as f:
                json.dump(hw_state, f, indent=2)
        except Exception:
            pass

        elapsed = time.time() - t0
        time.sleep(max(0, interval - elapsed))


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='Wind_Navigator Phase 23 -- MAVLink Hardware Bridge')
    parser.add_argument('--connect', default='tcp:127.0.0.1:5760',
        help='MAVLink connection string  (udp:IP:PORT | COMx | tcp:IP:PORT)')
    parser.add_argument('--baud', type=int, default=57600,
        help='Serial baud rate (ignored for UDP/TCP)')
    parser.add_argument('--sitl', action='store_true',
        help='Connect to ArduPilot SITL (tcp:127.0.0.1:5760) -- no hardware needed')
    parser.add_argument('--dry-run', action='store_true',
        help='Print commands without connecting to any hardware')
    args = parser.parse_args()

    conn = 'tcp:127.0.0.1:5760' if args.sitl else args.connect

    bridge = MAVLinkBridge(conn, baud=args.baud)

    if args.dry_run:
        print("[~] DRY-RUN mode -- no hardware connection attempted")
        bridge.connected = False
    else:
        bridge.connect()

    print(f"[*] Phase 23 bridge started")
    print(f"    Reading:  {STATE_FILE}")
    print(f"    Writing:  {HW_STATE_FILE}")
    print(f"    Hardware: {'CONNECTED' if bridge.connected else 'DRY-RUN'}")

    try:
        run_bridge(bridge)
    except KeyboardInterrupt:
        print("\n[*] Bridge stopped.")


if __name__ == '__main__':
    main()
