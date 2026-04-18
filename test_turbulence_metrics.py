# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR -- Phase 24: TurbulenceMonitor Unit Tests
=========================================================
Validates TI computation, threshold boundaries, and rolling window behaviour.
All expected values derived from the FAA AC 00-30C TI definition.
"""

import math, sys
from turbulence_metrics import (
    TurbulenceMonitor, TI_SMOOTH, TI_LIGHT, TI_MODERATE, TI_SEVERE,
    ti_to_confidence, ti_to_label, ti_is_danger
)

PASS = 0; FAIL = 0
results = []

def check(name, got, expected=None, condition=None, tol=0.5):
    global PASS, FAIL
    if condition is not None:
        ok = condition
    else:
        ok = abs(got - expected) <= tol
    status = "PASS" if ok else "FAIL"
    if ok: PASS += 1
    else:  FAIL += 1
    extra = f"got={got}" if expected is None else f"got={got:.3f} expected~={expected}"
    print(f"  [{status}] {name:45s} {extra}")
    results.append({"test": name, "status": status})

print("=" * 65)
print("WIND_NAVIGATOR  Phase 24 -- TurbulenceMonitor Unit Tests")
print("=" * 65)

# -- Test 1: Empty window returns 0 ------------------------------------------
mon = TurbulenceMonitor(window_size=10)
check("Empty window TI == 0.0", mon.ti(), 0.0, tol=0.001)

# -- Test 2: Constant wind = 0% TI (no fluctuation) --------------------------
mon = TurbulenceMonitor(window_size=10)
for _ in range(15):
    mon.update(10.0, 0.0, 0.0)   # constant 10 fps eastward
check("Constant wind TI == 0.0%", mon.ti(), 0.0, tol=0.5)
check("Constant wind confidence == HIGH", got=0,
      condition=(mon.confidence() == "HIGH"))

# -- Test 3: Highly variable wind = high TI ----------------------------------
mon = TurbulenceMonitor(window_size=20)
# Alternate between 2 and 18 fps -- large fluctuation
for i in range(20):
    spd = 18.0 if i % 2 == 0 else 2.0
    mon.update(spd, 0.0, 0.0)
# Mean = (18+2)/2 = 10, sigma ~ 8, TI ~ 80%
ti_high = mon.ti()
check("Highly variable wind TI > 15%", ti_high, condition=(ti_high > 15.0))
check("Highly variable confidence == LOW or CRITICAL",
      got=0, condition=(mon.confidence() in ("LOW", "CRITICAL")))
check("ti_is_danger True when TI > 15%",
      got=0, condition=(ti_is_danger(ti_high) == True))

# -- Test 4: Threshold boundary at exactly 15% --------------------------------
check("TI_LIGHT threshold constant == 15.0", TI_LIGHT, 15.0, tol=0.001)
check("ti_is_danger(14.9) == False", got=0, condition=(not ti_is_danger(14.9)))
check("ti_is_danger(15.0) == True",  got=0, condition=(ti_is_danger(15.0)))
check("ti_is_danger(15.1) == True",  got=0, condition=(ti_is_danger(15.1)))

# -- Test 5: TI labels --------------------------------------------------------
check("TI 4.9% -> SMOOTH",   got=0, condition=(ti_to_label(4.9)  == "SMOOTH"))
check("TI 14.9% -> LIGHT",   got=0, condition=(ti_to_label(14.9) == "LIGHT"))
check("TI 15.0% -> MODERATE",got=0, condition=(ti_to_label(15.0) == "MODERATE"))
check("TI 25.0% -> SEVERE",  got=0, condition=(ti_to_label(25.0) == "SEVERE"))

# -- Test 6: Confidence labels ------------------------------------------------
check("TI 4%  -> HIGH",     got=0, condition=(ti_to_confidence(4.0)  == "HIGH"))
check("TI 10% -> MEDIUM",   got=0, condition=(ti_to_confidence(10.0) == "MEDIUM"))
check("TI 20% -> LOW",      got=0, condition=(ti_to_confidence(20.0) == "LOW"))
check("TI 30% -> CRITICAL", got=0, condition=(ti_to_confidence(30.0) == "CRITICAL"))

# -- Test 7: Rolling window eviction ------------------------------------------
mon = TurbulenceMonitor(window_size=5)
for _ in range(5):
    mon.update(100.0, 0.0, 0.0)   # fill with high-speed calm
calm_ti = mon.ti()
check("Window of identical speeds has near-zero TI", calm_ti, 0.0, tol=1.0)
# Now flood with alternating -- old samples evict
for i in range(5):
    mon.update(1.0 if i % 2 == 0 else 19.0, 0.0, 0.0)
turbulent_ti = mon.ti()
check("New turbulent samples dominate after window evict",
      got=0, condition=(turbulent_ti > 15.0))

# -- Test 8: state_dict structure ---------------------------------------------
mon = TurbulenceMonitor()
for _ in range(10):
    mon.update(8.0, 5.0, 1.0)
sd = mon.state_dict()
check("state_dict has ti_pct",       got=0, condition=("ti_pct" in sd))
check("state_dict has ti_label",     got=0, condition=("ti_label" in sd))
check("state_dict has ti_mean_fps",  got=0, condition=("ti_mean_fps" in sd))
check("state_dict has ti_threshold", got=0, condition=("ti_threshold" in sd))
check("state_dict threshold == 15.0",got=0, condition=(sd["ti_threshold"] == 15.0))

# -- Test 9: near-calm air (mean ~0) -----------------------------------------
mon = TurbulenceMonitor()
for _ in range(10):
    mon.update(0.0001, 0.0, 0.0)
check("Near-zero wind returns TI 0.0", mon.ti(), 0.0, tol=0.01)

# -- Summary ------------------------------------------------------------------
print("\n" + "=" * 65)
total = PASS + FAIL
print(f"RESULTS: {PASS}/{total} tests PASSED  ({FAIL} failed)")
print("=" * 65)

sys.exit(0 if FAIL == 0 else 1)
