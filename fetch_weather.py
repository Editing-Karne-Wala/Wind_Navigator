# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR — Real Weather Bridge
Fetches live Manhattan wind data from Open-Meteo (NOAA GFS model, free, no API key)
and converts into LBM boundary condition vectors (u, v, w).
"""
import math, time, json

try:
    import httpx
    def _get(url): return httpx.get(url, timeout=6.0).json()
except ImportError:
    import urllib.request as _ur
    def _get(url):
        with _ur.urlopen(url, timeout=6) as r:
            return json.loads(r.read())

LAT, LON = 40.758, -73.985          # Midtown Manhattan
OPEN_METEO = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&current=wind_speed_10m,wind_direction_10m,wind_gusts_10m"
    "&wind_speed_unit=mph"
)
CACHE_TTL = 3600   # 1 hour

_cache   = {}
_cache_t = 0.0

def fetch_weather(force: bool = False) -> dict:
    """
    Returns a dict with:
      speed_mph, direction_deg, gusts_mph,
      wind_u, wind_v, wind_w  (LBM-ready fps-equivalent vectors),
      source, timestamp, location
    """
    global _cache, _cache_t
    if not force and time.time() - _cache_t < CACHE_TTL and _cache:
        return _cache

    url = OPEN_METEO.format(lat=LAT, lon=LON)
    try:
        data  = _get(url)
        cur   = data["current"]
        spd   = float(cur["wind_speed_10m"])
        dirg  = float(cur["wind_direction_10m"])
        gust  = float(cur["wind_gusts_10m"])
        rad   = math.radians(dirg)
        _cache = {
            "speed_mph":    round(spd,  1),
            "direction_deg":round(dirg, 1),
            "gusts_mph":    round(gust, 1),
            "wind_u": round(-spd * math.sin(rad), 2),   # W-E  (fps scale)
            "wind_v": round(-spd * math.cos(rad), 2),   # S-N
            "wind_w": 0.0,                               # vertical (injected by LBM)
            "source":    "Open-Meteo (NOAA GFS Model)",
            "timestamp": cur.get("time", "unknown"),
            "location":  "Manhattan, NYC",
        }
        _cache_t = time.time()
    except Exception as e:
        _cache = {
            "speed_mph": 8.0, "direction_deg": 270.0, "gusts_mph": 14.0,
            "wind_u": 8.0, "wind_v": 0.0, "wind_w": 0.0,
            "source": f"Fallback (offline: {e})",
            "timestamp": "unavailable", "location": "Manhattan, NYC",
        }
    return _cache

if __name__ == "__main__":
    w = fetch_weather(force=True)
    print(json.dumps(w, indent=2))
