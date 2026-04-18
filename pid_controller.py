# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR — Phase 20: Closed-Loop JSBSim PID Control
==========================================================
Physics NOW drives position. Two PID controllers run every frame:
  AltitudePID  : commands throttle to hold street-level AGL.
                 In heavy updraft/downdraft the drone actually drifts vertically.
  LateralPID   : commands roll/pitch to steer toward next A* waypoint.
                 In a bifurcation vortex the drone genuinely deviates from the
                 planned route — deviation is logged and shown on dashboard.

Key differences from Phase 19 (scripted waypoint lerp):
  - self._drone.setPos() is NO LONGER called with route coordinates.
  - Position = JSBSim position integrated from forces each frame.
  - The waypoint system becomes a "chase target" not a rail.
  - Bifurcation zones cause real lateral drift (visible path deviation).
  - Altitude hold can fail under extreme gust load.
"""

import sys, os, math, heapq, json
os.environ['PYTHONUTF8'] = '1'

# ── PID Controller ────────────────────────────────────────────────────────────
class PID:
    """Simple discrete PID with anti-windup clamp."""
    def __init__(self, kp, ki, kd, out_min=-1.0, out_max=1.0):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.out_min, self.out_max = out_min, out_max
        self._integral = 0.0
        self._prev_err = 0.0

    def update(self, error, dt):
        if dt <= 0: return 0.0
        self._integral  = max(self.out_min,
                              min(self.out_max, self._integral + error * dt))
        derivative = (error - self._prev_err) / dt
        self._prev_err = error
        out = self.kp * error + self.ki * self._integral + self.kd * derivative
        return max(self.out_min, min(self.out_max, out))

    def reset(self):
        self._integral = 0.0
        self._prev_err = 0.0
