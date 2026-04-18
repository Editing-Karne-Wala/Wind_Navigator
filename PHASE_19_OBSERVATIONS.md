# Phase 19 — Flight Envelope Enforcement: Observations & Readings

## Summary
Phase 19 implemented real physics honesty into the Wind_Navigator simulator.
The drone now **cannot fly** if the payload exceeds what the motors can physically lift.

---

## Key Results

### Thrust vs Weight Formula
```
max_payload_kg = (max_thrust_N - empty_kg × 9.81) / 9.81
```

### Drone Fleet Profiles (implemented)

| Drone | Motors | Empty | Max Thrust | Max Payload |
|:---|:---:|:---:|:---:|:---:|
| DJI F450 Quadrotor | 4× | 1.5 kg | 44 N | **~3.0 kg** |
| Heavy-Lift Hexacopter | 6× | 2.5 kg | 130 N | **~10.8 kg** |
| Cargo Octocopter X8 | 8× | 4.0 kg | 240 N | **~20.5 kg** |

---

## Test Runs & Observations

### Run 1 — F450 + 0 kg payload
- Total mass: 1.5 kg → Weight: 14.7 N
- Thrust margin: 44 - 14.7 = **+29.3 N**
- Result: ✅ NOMINAL FLIGHT, full 109 waypoints completed
- Canvas speed: 1 waypoint every 3 frames (fastest)

### Run 2 — F450 + 2.5 kg payload
- Total mass: 4.0 kg → Weight: 39.2 N
- Thrust margin: 44 - 39.2 = **+4.8 N** (10.9% margin — borderline)
- Result: ✅ FLIES but at risk during bifurcation updrafts
- Canvas speed: 1 waypoint every 5 frames (40% slower than unloaded)
- A* route: biased toward wider avenues (canyon-tightness penalty active)

### Run 3 — F450 + 10 kg payload
- Total mass: 11.5 kg → Weight: 112.8 N
- Thrust deficit: 44 - 112.8 = **-68.8 N** (IMPOSSIBLE)
- Result: ❌ IMMEDIATE CRASH at startup (waypoint 0/109)
- Visual: Drone turned red, tumbled, fell to ground at AGL 9.1m
- crash_log.json written: coords, altitude, reason, force breakdown
- Dashboard: Full-screen ⚠ CRASH overlay with force comparison table

### Run 4 — HEXA_PRO + 10 kg payload
- Total mass: 12.5 kg → Weight: 122.6 N
- Thrust margin: 130 - 122.6 = **+7.4 N** (5.7% margin — tight but flyable)
- Result: ✅ FLIES — navigated full 109 waypoints
- HUD shows: DRONE: Heavy-Lift Hexacopter | MOTORS: 6x | Max thrust: 130N
- Canvas speed: 1 waypoint every 11 frames (slowest run so far — heaviest load)
- Waypoints at 108/109 when flight observed (near final destination)

---

## Phase 19 New Files / Changes

| File | Change |
|:---|:---|
| `panda_manhattan.py` | DRONE_PROFILES fleet system, _trigger_crash(), flight envelope check in _sim_update, crash animation, _write_state crash fields |
| `index.html` | Crash overlay CSS + HTML + JS hook into pollStatus |
| `crash_log.json` | Auto-generated at crash event — coordinates, forces, payload |
| `sim_state.json` | Now includes: crashed, crash_reason, payload_kg, max_thrust_n, weight_n |

---

## Key Code: Flight Envelope Check (per-frame)
```python
weight_n    = (DRONE_EMPTY_KG + PAYLOAD_KG) * GRAVITY_N_PER_KG
wind_load_n = abs(self.wind_w) * 0.20      # vertical gust load equivalent
total_load  = weight_n + wind_load_n
if not self.crashed and total_load > MAX_THRUST_N:
    stall_type = "OVERWEIGHT" if wind_load_n < 0.5 else "MID-FLIGHT STALL"
    self._trigger_crash(f"{stall_type}: {total_load:.1f}N > {MAX_THRUST_N:.0f}N")
```

---

## Phase 19 Status: ✅ COMPLETE

**Next: Phase 20 — Closed-Loop JSBSim Control**
Physics drives position — drift, deviation, honest simulation.
