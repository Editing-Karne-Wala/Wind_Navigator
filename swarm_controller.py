# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR -- Phase 22: Swarm Controller
============================================
Manages N independent drone agents on simultaneous A* routes.
Each agent has:
  - Unique drone profile (F450 / HEXA_PRO / OCTO_CARGO)
  - Unique payload weight
  - Independent PID controllers (altitude + lateral)
  - Independent physics position (_px, _py, _pz)
  - Independent A* route (different start/end cells)
  - Flight envelope check (crash if weight > thrust)

Collision avoidance: O(N^2) separation check per frame.
If two drones come within MIN_SEPARATION scene units, the
trailing drone reduces speed by 50% until separation recovers.
"""

import math
from pid_controller import PID
from rational_wind  import rational_wind_components, lbm_bifurcation_score

MIN_SEPARATION = 1.8   # scene units (~18m real-world separation)

# Fleet definition — each tuple: (profile_key, payload_kg, start_cell, end_cell, color_rgb)
FLEET = [
    # Drone 0: heavy cargo, NW -> SE  (original route)
    ("HEXA_PRO",   10.0, (4,  4),  (74, 74), (0.0, 0.9, 1.0)),
    # Drone 1: light parcel, NE -> SW (cross-town)
    ("F450",        2.0, (74,  4), (4,  74), (0.2, 1.0, 0.4)),
    # Drone 2: industrial, mid -> SE  (short haul)
    ("OCTO_CARGO", 15.0, (4,  40), (74, 74), (1.0, 0.5, 0.1)),
]


class DroneAgent:
    """
    Single drone physical agent for the swarm controller.
    Self-contained: route, PIDs, position, state.
    """
    PROFILES = {
        "F450":       {"name": "DJI F450 Quad",      "empty_kg": 1.5, "max_thrust_n":  44.0, "motors": 4},
        "HEXA_PRO":   {"name": "Heavy-Lift Hexa",    "empty_kg": 2.5, "max_thrust_n": 130.0, "motors": 6},
        "OCTO_CARGO": {"name": "Cargo Octocopter X8","empty_kg": 4.0, "max_thrust_n": 240.0, "motors": 8},
    }
    G = 9.81

    def __init__(self, agent_id, profile_key, payload_kg, start_cell, end_cell, color,
                 terrain, route_fn, SXY, SZ, turb_seed):
        self.id          = agent_id
        self.profile     = self.PROFILES[profile_key]
        self.profile_key = profile_key
        self.payload_kg  = payload_kg
        self.color       = color                    # (R,G,B) for Panda3D node

        # Physics specs
        self.empty_kg    = self.profile["empty_kg"]
        self.total_kg    = self.empty_kg + payload_kg
        self.max_thrust  = self.profile["max_thrust_n"]
        self.weight_n    = self.total_kg * self.G
        self.SXY         = SXY
        self.SZ          = SZ

        # Route
        self.route  = route_fn(terrain, start_cell, end_cell)
        self.wp_idx = 0

        # Physics position
        if self.route:
            self._px, self._py, self._pz = self.route[0]
        else:
            self._px = start_cell[0] * SXY
            self._py = start_cell[1] * SXY
            self._pz = 1.5
        self._vx = 0.0;  self._vy = 0.0

        # PID controllers (each drone has its own independent controllers)
        self._alt_pid = PID(kp=0.08, ki=0.005, kd=0.04, out_min=0.0, out_max=0.92)
        self._lat_pid = PID(kp=0.035, ki=0.001, kd=0.020, out_min=-0.30, out_max=0.30)

        # Wind / turbulence state (integer recurrence, unique per drone)
        self._turb_x = turb_seed + agent_id * 7919
        self._turb_y = turb_seed + agent_id * 7919 + 1337
        self.wind_u  = 0.0;  self.wind_v = 0.0;  self.wind_w = 0.2

        # Flight state
        self.crashed          = False
        self.crash_reason     = ""
        self.mission_complete = False
        self.confidence       = "HIGH"
        self.chaos            = 2
        self.speed_factor     = 1.0   # reduced during collision avoidance

        # Telemetry
        self.max_deviation   = 0.0
        self.total_deviation = 0.0
        self.altitude_m      = 9.0

    # ── Flight envelope check ─────────────────────────────────────────────────
    def check_envelope(self, wind_load_n=0.0):
        total_load = self.weight_n + wind_load_n
        if not self.crashed and total_load > self.max_thrust:
            stall = "OVERWEIGHT" if wind_load_n < 0.5 else "MID-FLIGHT STALL"
            self.crashed      = True
            self.crash_reason = (f"{stall}: {total_load:.1f}N > "
                                 f"{self.max_thrust:.0f}N ({self.payload_kg}kg)")
            print(f"[!!!] Drone {self.id} CRASH: {self.crash_reason}")
        return self.crashed

    # ── Per-frame physics update ──────────────────────────────────────────────
    def update(self, dt, t, terrain, W, H, noaa_u, noaa_v, turb_prime=104729):
        if self.crashed or self.mission_complete:
            return

        if not self.route:
            return

        wi       = min(self.wp_idx, len(self.route) - 1)
        wx_t, wy_t, wz_t = self.route[wi]
        gx = max(1, min(W-2, int(self._px / self.SXY)))
        gy = max(1, min(H-2, int(self._py / self.SXY)))

        # Bifurcation check (integer LBM)
        cross, quad = lbm_bifurcation_score(terrain, gx, gy, W, H)
        in_bif = cross < 0
        self.chaos      = 38 if in_bif else 2
        self.confidence = "LOW" if in_bif else "HIGH"

        # Rational wind (integer Chebyshev recurrence for turbulence)
        if in_bif:
            new_x = (2 * self._turb_x - self._turb_y) % turb_prime
            self._turb_y = self._turb_x;  self._turb_x = new_x
            tu = (self._turb_x % 25) - 12
            tv = (self._turb_y % 19) - 9
            tw = (self._turb_x % 15) - 7
            self.wind_u = float(noaa_u + tu)
            self.wind_v = float(noaa_v + tv)
            self.wind_w = float(tw)
        else:
            self.wind_u = float(noaa_u)
            self.wind_v = float(noaa_v)
            self.wind_w = 0.2

        # Flight envelope
        wind_load = abs(self.wind_w) * 0.20
        self.check_envelope(wind_load)
        if self.crashed:
            return

        # Altitude vertical wind
        vert_wind = self.wind_w * 0.015 * (1.8 if in_bif else 0.06)
        vert_wind = max(-0.5, min(0.5, vert_wind))
        self._pz  = max(0.05, wz_t + vert_wind)
        self.altitude_m = self._pz / max(self.SZ, 0.001)

        # Throttle
        hover_floor = min(0.50 + self.payload_kg * 0.09, 0.92)

        # Lateral PID
        dx = wx_t - self._px;  dy = wy_t - self._py
        dist_to_wp = math.sqrt(dx*dx + dy*dy)
        bearing    = math.atan2(dx, dy)
        cur_hdg    = math.atan2(self._vx, self._vy) if (self._vx or self._vy) else bearing
        lat_err    = math.sin(bearing - cur_hdg)
        lat_cmd    = self._lat_pid.update(lat_err, dt)

        # Speed — weighted by collision avoidance factor + payload
        speed_su = hover_floor * 1.8 / (1.0 + self.payload_kg * 0.04)
        speed_su *= self.speed_factor   # reduced during close-approach

        fwd_len  = max(dist_to_wp, 0.001)
        self._vx = (dx / fwd_len) * speed_su
        self._vy = (dy / fwd_len) * speed_su

        wind_push_x = self.wind_u * 0.006 * (2.5 if in_bif else 0.10)
        wind_push_y = self.wind_v * 0.006 * (2.5 if in_bif else 0.10)

        self._px += (self._vx + wind_push_x) * dt
        self._py += (self._vy + wind_push_y) * dt

        # Waypoint advance
        if dist_to_wp < 0.6 and wi < len(self.route) - 1:
            self.wp_idx += 1
        elif wi == len(self.route) - 1 and dist_to_wp < 0.6:
            if not self.mission_complete:
                self.mission_complete = True
                print(f"[+] Drone {self.id} ({self.profile['name']}) MISSION COMPLETE"
                      f" -- {self.wp_idx} waypoints, max drift: {self.max_deviation:.2f} su")

        # Deviation
        dev = math.sqrt((self._px - wx_t)**2 + (self._py - wy_t)**2)
        self.max_deviation   = max(self.max_deviation, dev)
        self.total_deviation += dev * dt

    # ── Telemetry dict ────────────────────────────────────────────────────────
    def telemetry(self):
        return {
            "id":              self.id,
            "drone_model":     self.profile["name"],
            "profile_key":     self.profile_key,
            "payload_kg":      self.payload_kg,
            "max_thrust_n":    self.max_thrust,
            "weight_n":        round(self.weight_n, 1),
            "pos":             [round(self._px, 2), round(self._py, 2), round(self._pz, 2)],
            "waypoint":        self.wp_idx,
            "total_waypoints": len(self.route),
            "altitude_m":      round(self.altitude_m, 1),
            "confidence":      self.confidence,
            "chaos":           self.chaos,
            "wind_u":          round(self.wind_u, 1),
            "wind_v":          round(self.wind_v, 1),
            "wind_w":          round(self.wind_w, 1),
            "crashed":         self.crashed,
            "crash_reason":    self.crash_reason,
            "mission_complete": self.mission_complete,
            "max_deviation_su": round(self.max_deviation, 3),
            "speed_factor":    round(self.speed_factor, 2),
        }


# ── Swarm collision avoidance ─────────────────────────────────────────────────
def apply_collision_avoidance(agents):
    """
    O(N^2) pairwise separation enforcement.
    If dist(A, B) < MIN_SEPARATION: slow the faster/leading drone.
    Returns list of (agent_i, agent_j, distance) for any close pairs.
    """
    close_pairs = []
    n = len(agents)
    for i in range(n):
        agents[i].speed_factor = 1.0   # reset each frame

    for i in range(n):
        for j in range(i+1, n):
            a = agents[i];  b = agents[j]
            if a.crashed or b.crashed:
                continue
            dx = a._px - b._px;  dy = a._py - b._py
            dist = math.sqrt(dx*dx + dy*dy)
            if dist < MIN_SEPARATION:
                close_pairs.append((i, j, round(dist, 3)))
                # Slow leading drone (further along its route)
                if a.wp_idx >= b.wp_idx:
                    a.speed_factor = 0.5
                else:
                    b.speed_factor = 0.5
    return close_pairs
