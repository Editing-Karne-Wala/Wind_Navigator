# Phase 23 -- Real Hardware Bridge: Observations & Test Results

## Summary
Phase 23 connected the Wind_Navigator vortex prediction engine to a live
flight controller (ArduPilot SITL) via MAVLink. The full loop was validated:

```
Panda3D sim (12s lookahead) -> predict_vortex_ahead() -> MAVLinkBridge -> ArduCopter SITL
```

---

## Files Created

| File | Purpose |
|:---|:---|
| `mavlink_bridge.py` | Production MAVLink bridge -- 5Hz prediction poll, HOLD/PROCEED commands |
| `sitl_bridge_test.py` | SITL integration test -- arm, takeoff, prediction validation |
| `phase23_sitl_log.json` | Machine-readable test log with timestamps |
| `hardware_state.json` | Written at 5Hz by bridge -- predictions + actions for dashboard |

---

## SITL Environment

| Parameter | Value |
|:---|:---|
| Simulator | ArduCopter SITL v3.3 (via dronekit-sitl) |
| Location | NYC Midtown (lat=40.748817, lon=-73.985428) |
| Connection | tcp:127.0.0.1:5760 (pymavlink) |
| Heartbeat | sys=1 comp=0 |
| Mode sequence | GUIDED -> ARMED -> TAKEOFF 10m |

---

## Test Results: 3/3 PASSED

### Test 1 -- Vortex Detection (chaos=38, LOW confidence)
```
Input:   chaos=38, confidence=LOW
Lookahead: 12.0s -> wp_lookahead=17
Output:  danger_score=38.0 | vortex_alert=True
Action:  STATUSTEXT(severity=3) "D0 VORTEX 38 @WP17 HOLD"
         MAV_CMD_CONDITION_DELAY 8s
Result:  PASS
```
At chaos=38 (bifurcation zone), the bridge correctly issued a HOLD
command 17 waypoints (~12 seconds of flight) ahead of the danger zone.

### Test 2 -- Clear Path (chaos=2, HIGH confidence)
```
Input:   chaos=2, confidence=HIGH
Output:  danger_score=0.2 | vortex_alert=False
Action:  STATUSTEXT(severity=6) "D0 PATH CLEAR -- PROCEED"
         MAV_CMD_DO_CONTINUE
Result:  PASS
```
At chaos=2, no alert was triggered. PROCEED command sent correctly.

### Test 3 -- Threshold Boundary (chaos=20, threshold=20)
```
Input:   chaos=20, confidence=LOW
Output:  danger_score=20.0 | vortex_alert=True (>= threshold)
Result:  PASS -- boundary behaviour correct (>= not >)
```

---

## Bugs Caught & Fixed

### Bug 1 -- DroneKit Python 3.12 Incompatibility
**Symptom:** `AttributeError: module 'collections' has no attribute 'MutableMapping'`
**Root cause:** DroneKit uses `collections.MutableMapping` which was moved to
`collections.abc` in Python 3.10 and removed entirely from the top-level
`collections` namespace in Python 3.12.
**Fix:** Replaced DroneKit with raw pymavlink throughout the test.
DroneKit is only used for `dronekit_sitl.start_default()` (starting the
SITL process) -- the actual MAVLink communication uses pymavlink directly.
This is MORE production-accurate since mavlink_bridge.py uses pymavlink.

### Bug 2 -- UnicodeEncodeError on Windows (cp1252)
**Symptom:** Test crashed at first print statement containing `---` (U+2500).
**Root cause:** Windows terminal cp1252 codec does not support box-drawing
characters. Same class of bug as the Panda3D HUD issue in Phase 20.
**Fix:** Replaced all U+2500 (---) with ASCII `-` characters.
**Note:** Added to project-wide rule -- never use Unicode box-drawing chars
in any terminal-output code path on Windows.

---

## Timing Observations

| Stage | Duration |
|:---|:---|
| SITL download (first run) | ~45 seconds (S3 download) |
| SITL boot (cached) | ~8 seconds |
| pymavlink heartbeat wait | <2 seconds |
| Arm -> takeoff sequence | ~15 seconds |
| Prediction test loop (3 tests) | ~5 seconds |

---

## How to Connect Real Hardware

```bash
# Test loop (no hardware):
python mavlink_bridge.py --dry-run

# SITL (ArduPilot):
python mavlink_bridge.py --sitl

# USB telemetry radio (SiK 433/915MHz):
python mavlink_bridge.py --connect COM5 --baud 57600

# UDP (Mission Planner / QGroundControl):
python mavlink_bridge.py --connect udp:192.168.1.100:14550
```

The bridge reads `sim_state.json` at 5Hz (written by Panda3D simulation)
and sends MAVLink `STATUSTEXT` + `MAV_CMD_CONDITION_DELAY` when any drone's
predicted path crosses a vortex zone `>= 12s` ahead.

---

## Phase 23 Status: COMPLETE (3/3 SITL tests PASSED)
**Next: Phase 24 -- Regulatory Certification Package**
Produce FAA/EASA-format evidence dossier:
- VALIDATION_REPORT.md as airworthiness evidence
- SITL test log as hardware-in-loop test record
- Rational LBM false-positive analysis as safety case
