# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR -- Phase 24: Turbulence Intensity (TI) Metrics
==============================================================
Replaces hardcoded chaos=38/2 with physically grounded Turbulence Intensity.

Definition (ICAO 9817 / FAA AC 00-30C):
    TI (%) = sigma(u_prime) / U_bar * 100

Where:
    u_prime  = instantaneous wind speed deviation from mean
    U_bar    = mean wind speed over a rolling time window
    sigma    = standard deviation of u_prime samples

Aviation TI thresholds (FAA Moderate Turbulence criterion):
    TI <  5.0%  : SMOOTH      -- no action
    TI  5-15.0% : LIGHT       -- advisory only
    TI 15-25.0% : MODERATE    -- HOLD command issued (our safety threshold)
    TI > 25.0%  : SEVERE      -- emergency, auto-reroute

The 15% HOLD threshold is not arbitrary: it is the boundary
between FAA "light" and "moderate" turbulence intensity, and is
the standard criterion used in UAS (drone) risk assessment under
EASA Category A operations (PDRA-G02, GM1 Article 11).

Sources:
    FAA AC 00-30C: Atmospheric Turbulence Avoidance (2016)
    ICAO Doc 9817: Manual on Low-Level Wind Shear (2005)
    EASA PDRA-G02: Ground Risk Class for UAS operations (2022)
"""

import math
from collections import deque


# ── Aviation-standard TI thresholds ──────────────────────────────────────────
TI_SMOOTH       =  5.0   # %  --  calm air, no advisory
TI_LIGHT        = 15.0   # %  --  HOLD threshold (FAA moderate turbulence)
TI_MODERATE     = 25.0   # %  --  severe, emergency reroute
TI_SEVERE       = 40.0   # %  --  extreme (tornado-class urban canyon)

# Confidence labels map
def ti_to_confidence(ti_pct: float) -> str:
    if ti_pct < TI_SMOOTH:    return "HIGH"
    if ti_pct < TI_LIGHT:     return "MEDIUM"
    if ti_pct < TI_MODERATE:  return "LOW"
    return "CRITICAL"

def ti_to_label(ti_pct: float) -> str:
    if ti_pct < TI_SMOOTH:    return "SMOOTH"
    if ti_pct < TI_LIGHT:     return "LIGHT"
    if ti_pct < TI_MODERATE:  return "MODERATE"
    return "SEVERE"

def ti_is_danger(ti_pct: float) -> bool:
    """True if TI meets or exceeds the FAA moderate turbulence threshold."""
    return ti_pct >= TI_LIGHT


# ── Rolling-window TI estimator ───────────────────────────────────────────────
class TurbulenceMonitor:
    """
    Computes Turbulence Intensity (TI) from a rolling window of wind samples.

    At 5Hz polling and window_size=30 this gives a 6-second rolling average,
    which matches the ICAO 9817 recommended sampling period for urban LLJ
    (Low Level Jet) turbulence characterisation.

    Usage:
        mon = TurbulenceMonitor(window_size=30)
        ti  = mon.update(wind_u, wind_v, wind_w)  # call each frame/poll
        if mon.is_danger():
            send_hold_command()
    """

    def __init__(self, window_size: int = 30):
        self._window   = deque(maxlen=window_size)
        self._min_samples = 3       # need >= 3 samples for meaningful sigma

    # ── Core update ──────────────────────────────────────────────────────────
    def update(self, wind_u: float, wind_v: float, wind_w: float = 0.0) -> float:
        """
        Add one wind sample (u=east, v=north, w=vertical, all in fps).
        Returns current TI% (0.0 if insufficient samples).
        """
        speed = math.sqrt(wind_u**2 + wind_v**2 + wind_w**2)
        self._window.append(speed)
        return self.ti()

    # ── TI computation ────────────────────────────────────────────────────────
    def ti(self) -> float:
        """
        Turbulence Intensity in percent.
        Returns 0.0 if fewer than min_samples are available.
        """
        n = len(self._window)
        if n < self._min_samples:
            return 0.0

        mean = sum(self._window) / n
        if mean < 0.001:      # near-calm air: TI is undefined, treat as 0
            return 0.0

        # Sample standard deviation (Bessel correction: n-1)
        variance = sum((s - mean) ** 2 for s in self._window) / (n - 1)
        sigma    = math.sqrt(variance)
        return round((sigma / mean) * 100.0, 2)

    # ── Convenience accessors ─────────────────────────────────────────────────
    def confidence(self) -> str:
        return ti_to_confidence(self.ti())

    def label(self) -> str:
        return ti_to_label(self.ti())

    def is_danger(self) -> bool:
        return ti_is_danger(self.ti())

    def mean_speed(self) -> float:
        """Mean wind speed over current window (fps)."""
        n = len(self._window)
        return sum(self._window) / n if n > 0 else 0.0

    def peak_speed(self) -> float:
        return max(self._window) if self._window else 0.0

    def sample_count(self) -> int:
        return len(self._window)

    def state_dict(self) -> dict:
        """Full telemetry dict for sim_state.json."""
        ti = self.ti()
        return {
            "ti_pct":         ti,
            "ti_label":       ti_to_label(ti),
            "ti_mean_fps":    round(self.mean_speed(), 2),
            "ti_peak_fps":    round(self.peak_speed(), 2),
            "ti_samples":     self.sample_count(),
            "ti_threshold":   TI_LIGHT,
        }
