# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR -- Phase 25: NOAA Aviation Weather METAR Client
==============================================================
Replaces the hardcoded 8 mph @ 220-degree wind default with live METAR data
from the NOAA Aviation Weather Center API.

Stations: KLGA (LaGuardia) + KJFK (JFK) -- closest official ASOS stations
to Manhattan. Their surface winds are averaged to represent the urban canyon
inflow for the simulation.

METAR update schedule: once per hour, special observations every 20 minutes.
This client uses a 20-minute cache TTL so it's never stale but also never
hammers the API.

API endpoint:
    https://aviationweather.gov/api/data/metar?ids=KLGA,KJFK&format=raw

Sample response:
    METAR KLGA 120751Z 01004KT 10SM CLR 07/M03 A3045 RMK AO2 ...
    METAR KJFK 120751Z 02004KT 10SM CLR 07/M03 A3046 RMK AO2 ...

METAR wind field format: DDDSSKTorDDDSSGGGKT
    DDD = direction (degrees true, 000-360), or VRB (variable)
    SS or SSS = speed (knots)
    GGG = optional gust speed (knots, ignored for steady-state planning)
    KT = knots

Fallback hierarchy:
    1. Live NOAA METAR (freshly fetched)
    2. File-cached NOAA METAR (noaa_wind_cache.json, within TTL)
    3. NYC climatological mean: 9.2 mph @ 215 deg
       Source: NOAA NCEI surface wind climatology 1991-2020, NYC Central Park
"""

import json, math, os, re, threading, time, urllib.request, urllib.error
from datetime import datetime, timezone

# ── Configuration ─────────────────────────────────────────────────────────────
METAR_STATIONS   = ['KLGA', 'KJFK']
METAR_API_URL    = ('https://aviationweather.gov/api/data/metar'
                    '?ids={ids}&format=raw')
CACHE_FILE       = 'noaa_wind_cache.json'
CACHE_TTL_S      = 20 * 60    # 20 minutes (matches METAR special obs interval)
FETCH_TIMEOUT_S  = 8          # HTTP request timeout

# NYC 30-year climatological surface wind (NOAA NCEI 1991-2020, Central Park)
# Used ONLY if API is unreachable AND no cache file exists
NYC_CLIMO_SPEED_MPH = 9.2
NYC_CLIMO_DIR_DEG   = 215

_fetch_lock   = threading.Lock()
_fetch_thread = None   # background fetch thread

# ── METAR wind parser ─────────────────────────────────────────────────────────
# Regex: optional leading whitespace, then DDD(SS|SSS)[GGG]KT
_WIND_RE = re.compile(r'\b(VRB|\d{3})(\d{2,3})(?:G\d{2,3})?KT\b')

def parse_metar_wind(metar_str: str):
    """
    Extract (speed_mph, direction_deg) from a raw METAR string.
    Returns None if wind field is not found or direction is VRB (variable).

    Examples:
        '01004KT' -> (4.6, 10)
        '25015G25KT' -> (17.3, 250)  [gust ignored]
        'VRB03KT' -> None (variable direction -- skip this obs)
        '00000KT' -> (0.0, 0)  [calm]
    """
    m = _WIND_RE.search(metar_str)
    if m is None:
        return None

    dir_str, spd_str = m.group(1), m.group(2)

    if dir_str == 'VRB':
        return None    # variable: direction undefined, derive from next station

    direction_deg = int(dir_str)
    speed_kt      = int(spd_str)
    speed_mph     = round(speed_kt * 1.15078, 2)   # 1 knot = 1.15078 mph exactly

    return speed_mph, direction_deg


# ── METAR fetcher ─────────────────────────────────────────────────────────────
def fetch_metar(stations=None) -> list:
    """
    Fetch raw METAR strings from NOAA API.
    Returns list of dicts: [{station, speed_mph, direction_deg, raw_metar}, ...]
    Raises on network/parse failure.
    """
    if stations is None:
        stations = METAR_STATIONS

    url = METAR_API_URL.format(ids=','.join(stations))
    req = urllib.request.Request(url, headers={'User-Agent': 'WindNavigator/25'})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
        body = resp.read().decode('utf-8')

    obs = []
    for line in body.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Identify station: first token after 'METAR' or just the first token
        tokens = line.split()
        if tokens[0] == 'METAR':
            tokens = tokens[1:]    # strip the 'METAR' prefix
        station_id = tokens[0] if tokens else '????'

        wind = parse_metar_wind(line)
        if wind is None:
            continue    # variable direction or no wind field

        speed_mph, dir_deg = wind
        obs.append({
            'station':       station_id,
            'speed_mph':     speed_mph,
            'direction_deg': dir_deg,
            'raw':           line,
        })

    return obs


# ── Vector averaging of multiple stations ─────────────────────────────────────
def vector_average_wind(observations: list):
    """
    Compute the vector-average wind across multiple METAR observations.
    Uses U/V components to correctly average directions (avoids 0/360 wrap).

    Returns (speed_mph, direction_deg) as floats.
    """
    if not observations:
        return NYC_CLIMO_SPEED_MPH, NYC_CLIMO_DIR_DEG

    u_sum = 0.0; v_sum = 0.0
    for obs in observations:
        rad = math.radians(obs['direction_deg'])
        # Meteorological convention: direction is FROM, so:
        # wind blows FROM dir -> u = -sin(dir), v = -cos(dir)
        u_sum += obs['speed_mph'] * (-math.sin(rad))
        v_sum += obs['speed_mph'] * (-math.cos(rad))

    n = len(observations)
    u_avg = u_sum / n
    v_avg = v_sum / n

    mean_speed = math.sqrt(u_avg**2 + v_avg**2)
    # Direction the wind is FROM (meteorological)
    mean_dir   = (math.degrees(math.atan2(-u_avg, -v_avg)) + 360) % 360

    return round(mean_speed, 2), round(mean_dir, 1)


# ── Cache management ──────────────────────────────────────────────────────────
def _write_cache(speed_mph: float, direction_deg: float, obs: list):
    data = {
        'speed_mph':     speed_mph,
        'direction_deg': direction_deg,
        'timestamp':     datetime.now(timezone.utc).isoformat(),
        'stations':      obs,
        'source':        'NOAA_METAR',
    }
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def _read_cache():
    """
    Read cache file. Returns (speed_mph, direction_deg) if fresh, else None.
    """
    try:
        with open(CACHE_FILE) as f:
            data = json.load(f)
        ts = datetime.fromisoformat(data['timestamp'])
        age_s = (datetime.now(timezone.utc) - ts).total_seconds()
        if age_s <= CACHE_TTL_S:
            return data['speed_mph'], data['direction_deg']
    except Exception:
        pass
    return None


# ── Background refresh ────────────────────────────────────────────────────────
def _bg_fetch():
    """
    Background thread: fetch fresh METAR, write cache, then exit.
    Safe to call multiple times -- only one thread runs at a time.
    """
    global _fetch_thread
    try:
        obs  = fetch_metar()
        spd, dirn = vector_average_wind(obs)
        _write_cache(spd, dirn, obs)
        print(f"[NOAA] Cache updated: {spd:.1f} mph @ {dirn:.0f}deg "
              f"({', '.join(o['station'] for o in obs)})")
    except Exception as e:
        print(f"[NOAA] Background fetch failed: {e}")
    finally:
        _fetch_thread = None


def _trigger_bg_fetch():
    """Start a background fetch if one isn't already running."""
    global _fetch_thread
    with _fetch_lock:
        if _fetch_thread is None or not _fetch_thread.is_alive():
            _fetch_thread = threading.Thread(target=_bg_fetch, daemon=True)
            _fetch_thread.start()


# ── Public API ────────────────────────────────────────────────────────────────
def get_noaa_wind(blocking: bool = False) -> tuple:
    """
    Get current NYC wind as (speed_mph, direction_deg).

    Caching strategy (never blocks the render loop):
      1. Cache fresh (<20 min)  -> return immediately
      2. Cache stale but exists -> start background refresh, return stale value
      3. No cache              -> synchronous fetch (first run only)

    Set blocking=True to force a synchronous fetch (for testing).
    """
    # Fast path: fresh cache
    cached = _read_cache()
    if cached is not None:
        return cached

    if blocking:
        # Synchronous fetch (used in tests and first-run forced refresh)
        try:
            obs  = fetch_metar()
            spd, dirn = vector_average_wind(obs)
            _write_cache(spd, dirn, obs)
            print(f"[NOAA] Live fetch: {spd:.1f} mph @ {dirn:.0f}deg")
            return spd, dirn
        except Exception as e:
            print(f"[NOAA] Live fetch failed: {e} -- using climatological fallback")
            return NYC_CLIMO_SPEED_MPH, NYC_CLIMO_DIR_DEG

    # Stale cache: trigger background refresh, return stale for now
    try:
        data = json.load(open(CACHE_FILE))
        spd  = data['speed_mph']
        dirn = data['direction_deg']
        print(f"[NOAA] Stale cache ({data.get('timestamp','?')}), "
              f"returning {spd}mph@{dirn}deg, refreshing in background...")
        _trigger_bg_fetch()
        return spd, dirn
    except Exception:
        pass

    # No cache at all: background thread + synchronous climatological fallback
    print(f"[NOAA] No cache; using climatological fallback "
          f"({NYC_CLIMO_SPEED_MPH} mph @ {NYC_CLIMO_DIR_DEG} deg) "
          f"while fetching in background...")
    _trigger_bg_fetch()
    return NYC_CLIMO_SPEED_MPH, NYC_CLIMO_DIR_DEG


# ── CLI usage ─────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("Fetching live NOAA METAR wind (KLGA + KJFK)...")
    obs = fetch_metar()
    print(f"  Raw observations ({len(obs)}):")
    for o in obs:
        print(f"    {o['station']}: {o['speed_mph']:.1f} mph @ {o['direction_deg']}deg"
              f"  [{o['raw']}]")
    spd, dirn = vector_average_wind(obs)
    print(f"\n  Vector average: {spd:.1f} mph @ {dirn:.0f} deg")
    print(f"  (was hardcoded: {NYC_CLIMO_SPEED_MPH} mph @ 220 deg)")
    _write_cache(spd, dirn, obs)
    print(f"  Cache written: {CACHE_FILE}")
