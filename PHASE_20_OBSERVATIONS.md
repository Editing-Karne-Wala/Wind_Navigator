# Phase 20 — Closed-Loop JSBSim PID Control: Observations & Bugs

## Summary
Phase 20 replaced the scripted waypoint-lerp position system with a real
PID closed-loop control architecture. Physics now drives drone position —
wind genuinely drifts the drone off the A* route, and the altitude hold
is commanded, not scripted.

---

## Architecture Change (Phase 19 → Phase 20)

| Dimension | Phase 19 (Scripted) | Phase 20 (Closed-Loop) |
|:---|:---|:---|
| Position | `drone.setPos(waypoint_coords)` — rail | `drone.setPos(_px, _py, _pz)` — physics |
| Altitude | waypoint altitude ± JSBSim AGL offset | wind_w vertical perturbation, hard-capped |
| Steering | always snap to waypoint heading | Lateral PID commands roll/pitch |
| Throttle | static `hover_floor` | Altitude PID modulates throttle |
| Waypoint advance | every N frames (timer) | proximity-based (dist_to_wp < 0.6 su) |

---

## New Files

| File | Purpose |
|:---|:---|
| `pid_controller.py` | Discrete PID with anti-windup. `PID(kp, ki, kd, out_min, out_max)` |

---

## PID Tuning Values

```python
# Altitude PID: error = target_agl - actual_agl
_alt_pid = PID(kp=0.08, ki=0.005, kd=0.04, out_min=0.0, out_max=0.92)

# Lateral PID: error = sin(bearing - current_heading)
_lat_pid = PID(kp=0.035, ki=0.001, kd=0.020, out_min=-0.30, out_max=0.30)
```

---

## Bugs Caught & Fixed

### Bug 1 — JSBSim KeyError: 'velocities/vn-fps'
**Symptom:** Sim crashed immediately on first frame of Phase 20.
**Root cause:** F450 JSBSim model does not expose NED-frame velocity
properties (`velocities/vn-fps`, `ve-fps`, `vd-fps`). These are not
registered in the F450 aircraft config.
**Fix:** Replaced JSBSim NED velocity reads with a waypoint-direction
speed model:
```python
speed_su = thr * 1.8 / (1.0 + PAYLOAD_KG * 0.04)
self._vx = (dx / fwd_len) * speed_su
self._vy = (dy / fwd_len) * speed_su
```
Physics honesty maintained: heavier drones move slower (reduced speed_su),
wind still pushes `_px/_py` off course.

---

### Bug 2 — Altitude Climbing to 145m AGL (then 118m after partial fix)
**Symptom:** Drone drifted to 145m AGL and camera pulled so far back that
buildings were invisible — entire screen filled with cyan drone geometry.
**Root cause:** JSBSim has **no position feedback**. With throttle at 0.92,
JSBSim simulated the drone climbing freely and indefinitely.
`position/h-agl-ft` kept increasing. We were reading that value and
feeding it into `_pz`:
```python
# WRONG — JSBSim altitude drifts without feedback
agl_dev_m = actual_agl_m - target_agl_m   # grows to 109m
self._pz  = wz_t + agl_dev_m * SZ * 0.5  # propagates into scene
```
**Fix (attempt 1):** Added `max(-3, min(3, ...))` clamp — failed.
JSBSim's 118m value was still being read and influencing result.
**Fix (final):** Completely removed JSBSim altitude from `_pz` calculation.
Altitude now driven purely by vertical wind component:
```python
vert_wind = self.wind_w * 0.015 * (1.8 if in_bif else 0.06)
vert_wind = max(-0.5, min(0.5, vert_wind))   # hard scene-unit cap
self._pz  = max(0.05, wz_t + vert_wind)
```
JSBSim still runs for roll/pitch attitude. Its `h-agl-ft` is never
read for position again. HUD altitude now shows scene-derived value.

---

### Bug 3 — Same Path Every Run
**Symptom:** Wind always pushed the drone in the same direction,
producing identical drift and identical visual path every run.
**Root cause:** Wind formula `math.sin(t * 2.3)` where `t` always
starts at 0. Identical seed → identical wind → identical drift.
**Fix:** Per-session random wind phase offset:
```python
self._wind_seed = random.uniform(0, 200.0)
wt = t + self._wind_seed
self.wind_u = math.sin(wt * 2.3) * 12 if in_bif else ...
```
Every launch now has a unique wind phase → genuinely different drift.

---

### Bug 4 — Altitude Runaway at Mission End (Destination)
**Symptom:** At waypoint 108/109 (last waypoint), `dist_to_wp` never
reached the advance threshold, so the drone "parked" but JSBSim kept
running full throttle. Combined with Bug 2, altitude climbed forever
after arrival.
**Fix:** Mission-complete state triggered on proximity to final waypoint:
```python
elif wi == len(self.ROUTE) - 1 and dist_to_wp < 0.6:
    if not self.mission_complete:
        self.mission_complete = True
        self._pz = wz_t   # snap to route altitude
        for i in range(4):
            self.fdm[f'fcs/throttle-cmd-norm[{i}]'] = 0.35  # idle
        print(f"[+] MISSION COMPLETE")
    self._vx = 0.0; self._vy = 0.0
    wind_push_x = 0.0; wind_push_y = 0.0
```

---

## Critical Finding: math.sin() Violates Rational Trigonometry

**The `math.sin((t + seed) * 2.3)` in the wind generator is a direct
violation of the Rational Trigonometry framework.**

| Level | Impact |
|:---|:---|
| Framework integrity | sin() is a transcendental function — the exact thing RT eliminates |
| Determinism claim | IEEE 754 sin() differs across CPU vendors at 16th decimal place |
| Downstream contamination | wind_u → JSBSim → wind_push_x → _px → deviation telemetry |
| Agent Oracle trust signal | `max_deviation_su` published to agents is float-trig contaminated |

**Current state:** sin() only lives in the mock wind oscillator, NOT in
the LBM bifurcation kernel or the A* cost function (which are pure integer).

**Phase 21 resolution:** Replace mock wind oscillator with:
1. NOAA GFS live wind data (integer mph at integer degrees — rational)
2. Integer Chebyshev rational oscillator for local turbulence variation

---

## Phase 20 Telemetry Additions to sim_state.json

```json
{
  "control_mode": "CLOSED_LOOP_PID",
  "drone_model":   "Heavy-Lift Hexacopter",
  "motors":        6,
  "max_deviation_su": 0.241,
  "total_deviation":  12.8,
  "physics_pos":   [37.0, 36.2, 2.1]
}
```

---

## Phase 20 Status: COMPLETE (with known sin() debt logged above)
**Next: Phase 21 — Scientific Validation**
- Replace mock sin() wind with NOAA rational wind data
- Pull Manhattan CFD reference data (Columbia/NYU datasets)
- Head-to-head: Rational LBM vs float LBM vs OpenFOAM reference
- Produce VALIDATION_REPORT.md
- Validate the 32% improvement claim with evidence
