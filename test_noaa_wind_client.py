# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR -- Phase 25: NOAA Wind Client Tests
===================================================
Tests METAR parsing, vector averaging, cache logic, and fallback behaviour.
HTTP calls are mocked -- these tests pass offline.
"""

import json, math, os, sys, tempfile, time, unittest
from unittest.mock import patch, MagicMock

# ── Import module under test ──────────────────────────────────────────────────
from noaa_wind_client import (
    parse_metar_wind, fetch_metar, vector_average_wind,
    NYC_CLIMO_SPEED_MPH, NYC_CLIMO_DIR_DEG,
    _write_cache, _read_cache, get_noaa_wind, CACHE_TTL_S
)

PASS = 0; FAIL = 0

def check(name, got=None, condition=None, expected=None, tol=0.5):
    global PASS, FAIL
    if condition is not None:
        ok = bool(condition)
    elif expected is not None:
        ok = abs(float(got) - float(expected)) <= tol
    else:
        ok = bool(got)
    status = "PASS" if ok else "FAIL"
    if ok: PASS += 1
    else:  FAIL += 1
    detail = f"got={got}" if expected is None else f"got={got}, exp~={expected}"
    print(f"  [{status}] {name:50s} {detail}")


print("=" * 70)
print("WIND_NAVIGATOR  Phase 25 -- NOAA Wind Client Tests")
print("=" * 70)


# ── Test 1: METAR parsing ─────────────────────────────────────────────────────
print("\n[1] METAR wind parsing")

spd, dirn = parse_metar_wind("METAR KLGA 120751Z 01004KT 10SM CLR 07/M03 A3045")
check("01004KT speed = 4.6 mph",    spd,  expected=4.6, tol=0.1)
check("01004KT direction = 10 deg", dirn, expected=10,  tol=0.1)

spd2, dirn2 = parse_metar_wind("KJFK 231251Z 25015G28KT 10SM BKN040 12/04 A2990")
check("25015G28KT speed = 17.3 mph",    spd2,  expected=17.3, tol=0.2)
check("25015G28KT direction = 250 deg", dirn2, expected=250,   tol=0.1)
check("Gust ignored (only steady speed)", condition=(spd2 < 20))

check("VRB wind returns None", condition=(parse_metar_wind("VRB03KT") is None))
check("Calm 00000KT -> (0.0, 0)",
      condition=(parse_metar_wind("00000KT") == (0.0, 0)))
check("No wind field -> None", condition=(parse_metar_wind("KLGA 120751Z 10SM CLR") is None))

spd3, d3 = parse_metar_wind("METAR KEWR 120351Z 18012KT 10SM OVC018")
check("18012KT speed = 13.8 mph",    spd3, expected=13.81, tol=0.1)
check("18012KT direction = 180 deg", d3,   expected=180,   tol=0.1)


# ── Test 2: Vector averaging ──────────────────────────────────────────────────
print("\n[2] Vector averaging")

# Two identical observations -> same result
obs_same = [
    {"speed_mph": 10.0, "direction_deg": 90},
    {"speed_mph": 10.0, "direction_deg": 90},
]
spd_v, dir_v = vector_average_wind(obs_same)
check("Two identical easterlies -> 10 mph",       spd_v, expected=10.0, tol=0.2)
check("Two identical easterlies -> 90 deg",       dir_v, expected=90.0, tol=1.0)

# Two opposing equal winds -> near-calm (should average to ~0 speed)
obs_opp = [
    {"speed_mph": 10.0, "direction_deg":   0},
    {"speed_mph": 10.0, "direction_deg": 180},
]
spd_opp, _ = vector_average_wind(obs_opp)
check("Opposing equal winds -> near-calm speed", spd_opp, expected=0.0, tol=0.5)

# KLGA + KJFK from actual API response (010 and 020 deg, both 4.6 mph)
obs_live = [
    {"speed_mph": 4.6, "direction_deg": 10},
    {"speed_mph": 4.6, "direction_deg": 20},
]
spd_l, dir_l = vector_average_wind(obs_live)
check("KLGA+KJFK vector avg speed ~4.6 mph",   spd_l, expected=4.6, tol=0.3)
check("KLGA+KJFK vector avg direction ~15 deg", dir_l, expected=15,  tol=2.0)

# Empty observations -> climatological fallback
spd_e, dir_e = vector_average_wind([])
check("Empty obs -> climo speed",   spd_e, expected=NYC_CLIMO_SPEED_MPH, tol=0.1)
check("Empty obs -> climo dir",     dir_e, expected=NYC_CLIMO_DIR_DEG,   tol=0.1)


# ── Test 3: Cache read/write ──────────────────────────────────────────────────
print("\n[3] Cache behaviour")

import noaa_wind_client as _nwc

# Write a fresh cache to a temp file and read it back
old_cache = _nwc.CACHE_FILE
_nwc.CACHE_FILE = tempfile.mktemp(suffix='.json')
try:
    _write_cache(7.5, 230.0, [{"station": "TEST", "speed_mph": 7.5, "direction_deg": 230, "raw": "TEST"}])
    result = _read_cache()
    check("Fresh cache returns (7.5, 230)", condition=(result == (7.5, 230.0)))

    # Expire the cache by backdating the timestamp
    with open(_nwc.CACHE_FILE) as f:
        data = json.load(f)
    from datetime import datetime, timezone, timedelta
    data['timestamp'] = (datetime.now(timezone.utc) - timedelta(seconds=CACHE_TTL_S + 60)).isoformat()
    with open(_nwc.CACHE_FILE, 'w') as f:
        json.dump(data, f)
    check("Expired cache returns None", condition=(_read_cache() is None))
finally:
    try: os.remove(_nwc.CACHE_FILE)
    except: pass
    _nwc.CACHE_FILE = old_cache


# ── Test 4: Live API fetch (mocked) ──────────────────────────────────────────
print("\n[4] Live API fetch (HTTP mocked)")

MOCK_METAR = (
    "METAR KLGA 120751Z 01004KT 10SM CLR 07/M03 A3045 RMK AO2 SLP311 T00721033\n"
    "METAR KJFK 120751Z 02004KT 10SM CLR 07/M03 A3046 RMK AO2 SLP315 T00671033\n"
)

class MockHTTPResp:
    def read(self): return MOCK_METAR.encode()
    def __enter__(self): return self
    def __exit__(self, *a): pass

with patch('urllib.request.urlopen', return_value=MockHTTPResp()):
    obs = fetch_metar(['KLGA', 'KJFK'])

check("Mocked fetch returns 2 observations",  condition=(len(obs) == 2))
check("First obs station == KLGA",            condition=(obs[0]['station'] == 'KLGA'))
check("First obs speed ~ 4.6",                obs[0]['speed_mph'], expected=4.6, tol=0.1)
check("Second obs station == KJFK",           condition=(obs[1]['station'] == 'KJFK'))

spd_m, dir_m = vector_average_wind(obs)
check("Mocked vector avg speed ~4.6 mph",     spd_m, expected=4.6, tol=0.3)
check("Mocked vector avg direction ~15 deg",  dir_m, expected=15,  tol=2.0)


# ── Test 5: Fallback chain ────────────────────────────────────────────────────
print("\n[5] Fallback chain (network failure)")

old_cache2 = _nwc.CACHE_FILE
_nwc.CACHE_FILE = tempfile.mktemp(suffix='.json')   # empty cache file path
try:
    with patch('urllib.request.urlopen', side_effect=OSError("network down")):
        spd_fb, dir_fb = get_noaa_wind(blocking=True)  # blocking so bg thread runs

    # With no cache and network failure, should return climatological values
    check("Network failure -> climo speed",
          condition=(abs(spd_fb - NYC_CLIMO_SPEED_MPH) < 2.0))
    check("Network failure -> climo dir in [180,270] (SW quadrant)",
          condition=(180 <= dir_fb <= 270))
finally:
    try: os.remove(_nwc.CACHE_FILE)
    except: pass
    _nwc.CACHE_FILE = old_cache2


# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
total = PASS + FAIL
print(f"RESULTS: {PASS}/{total} tests PASSED  ({FAIL} failed)")
print("=" * 70)
sys.exit(0 if FAIL == 0 else 1)
