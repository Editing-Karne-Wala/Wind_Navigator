# Phase 22 — Swarm Intelligence: Observations & Bugs

## Summary
Phase 22 scaled from 1 drone to a 3-drone fleet operating simultaneously
on independent A* routes through Manhattan with collision avoidance.

---

## Fleet Configuration

| # | Model | Payload | Thrust | Weight | Margin | Route | Color |
|:---|:---|:---:|:---:|:---:|:---:|:---|:---:|
| 0 | HEXA_PRO | 10.0 kg | 130 N | 122.6 N | +7.4 N | NW(4,4)→SE(74,74) | Cyan |
| 1 | F450 | 2.0 kg | 44 N | 33.4 N | +10.6 N | NE(74,4)→SW(4,74) | Green |
| 2 | OCTO_CARGO | 15.0 kg | 240 N | 186.4 N | +53.6 N | Mid(4,40)→MidE(74,40) | Orange |

All three are flyable (no crash at launch). Routes are mutually independent —
no shared start or destination points.

---

## New Files

| File | Purpose |
|:---|:---|
| `swarm_controller.py` | `DroneAgent` class, `FLEET` config, `apply_collision_avoidance()` |

---

## Architecture

### DroneAgent
Each agent is fully self-contained:
- Independent A* route (different start/end cells)
- Independent altitude PID + lateral PID (from `pid_controller.py`)
- Independent integer turbulence recurrence (seeded by `agent_id * 7919`)
- Independent physics position (`_px`, `_py`, `_pz`)
- Independent flight envelope check (crash if weight > thrust)
- Independent `mission_complete` state

### Collision Avoidance
O(N²) pairwise separation check every frame:
```python
MIN_SEPARATION = 1.8   # scene units (~18m real-world)
# If dist(A, B) < MIN_SEPARATION:
#   trailing drone (lower wp_idx) -> speed_factor = 0.5
#   leading drone maintains speed
```

### sim_state.json Fleet Telemetry
```json
{
  "fleet_size": 3,
  "fleet_complete": 0,
  "fleet_crashed": 0,
  "fleet": [
    { "id": 0, "drone_model": "Heavy-Lift Hexa", "payload_kg": 10.0,
      "pos": [37.0, 36.2, 2.1], "waypoint": 54, "total_waypoints": 109, ... },
    { "id": 1, "drone_model": "DJI F450 Quad",   "payload_kg": 2.0, ... },
    { "id": 2, "drone_model": "Cargo Octocopter X8", "payload_kg": 15.0, ... }
  ]
}
```

---

## Bugs Caught & Fixed

### Bug 1 — Swarm Sphere Nodes 10-15x Too Large
**Symptom:** "Light green and orange balls" filling half the screen —
larger than Manhattan skyscrapers.
**Root cause:** `models/misc/sphere` in Panda3D has a native radius of
approximately 10 scene units, NOT 1. `setScale(0.7)` → 7 unit radius →
14 unit diameter → building-sized spheres.
**Fix:** `setScale(0.09)` → ~0.9 unit diameter, roughly drone-sized.

### Bug 2 — Camera Glitch at End of Route (Destination Collision)
**Symptom:** At waypoint 107/108, primary drone (Drone 0) "glitched"
violently over an orange ball and the HUD tilted.
**Root cause:** Drone 0 (HEXA_PRO) and Drone 2 (OCTO_CARGO) shared the
same destination cell `(74, 74)`. Drone 2 arrived first and parked there
as a sphere. When Drone 0's follow-camera approached `(74, 74)`, it flew
directly into the parked sphere — camera-inside-sphere = visual chaos.
**Fix:** Changed Drone 2's endpoint from `(74, 74)` to `(74, 40)`.
All three drones now have unique destinations on different grid rows/columns.

---

## Observations

- Collision avoidance correctly slows trailing drone when separation < 1.8 su
- All 3 A* routes computed in ~300ms at startup (serial, acceptable for N=3)
- Each drone's integer recurrence produces different turbulence (verified:
  seeds differ by `agent_id * 7919` — large enough to avoid near-identical sequences)
- `fleet_crashed` counter in sim_state.json updates in real-time —
  ready for dashboard fleet panel

---

## Phase 22 Status: COMPLETE
**Next: Phase 23 — Real Hardware Bridge**
Connect simulation vortex prediction to a live MAVLink drone.
Predict danger zones BEFORE the physical drone reaches them.
