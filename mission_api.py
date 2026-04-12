# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR — Phase 18: Mission Control API
===============================================
Endpoints:
  GET  /                → Mission Dashboard HTML
  GET  /v1/health       → Heartbeat
  GET  /v1/status       → Live sim telemetry (from sim_state.json)
  GET  /v1/terrain      → Full 80x80 Manhattan terrain grid (JSON)
  POST /v1/wind_check   → Agent Oracle — voxel-level safety query
  GET  /v1/noaa_sync    → Real-time NOAA weather for Manhattan
  GET  /v1/moltbook_feed → Our Moltbook broadcast feed

Run: python mission_api.py
Dashboard: http://127.0.0.1:7777
"""
import os, json, time, math
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

from fetch_weather import fetch_weather

BASE_DIR        = Path(__file__).parent
SIM_STATE_FILE  = BASE_DIR / "sim_state.json"
INDEX_HTML      = BASE_DIR / "index.html"
MOLTBOOK_KEY    = "moltbook_sk_PjAIKn0U9vdhtLr-j7-nFa5l3Y3iCghw"
MOLTBOOK_API    = "https://www.moltbook.com/api/v1"

# ── Load Terrain ──────────────────────────────────────────────────────────────
def _load_terrain():
    with open(BASE_DIR / "urban_terrain.txt") as f:
        tokens = f.read().split()
    idx = 0
    W, H = int(tokens[idx]), int(tokens[idx+1]); idx += 2
    grid = []
    for y in range(H):
        grid.append([int(tokens[idx + x]) for x in range(W)])
        idx += W
    return W, H, grid

TERRAIN_W, TERRAIN_H, TERRAIN = _load_terrain()
TERRAIN_MAX = max(TERRAIN[y][x] for y in range(TERRAIN_H) for x in range(TERRAIN_W))

def _bifurcation(x: int, y: int) -> bool:
    x = max(1, min(TERRAIN_W-2, x))
    y = max(1, min(TERRAIN_H-2, y))
    return (TERRAIN[y][x+1] - TERRAIN[y][x-1]) * (TERRAIN[y+1][x] - TERRAIN[y-1][x]) < 0

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Wind_Navigator Mission Control", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    if INDEX_HTML.exists():
        return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))
    return HTMLResponse("<h1 style='font-family:monospace;color:cyan'>index.html not found</h1>")

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/v1/health")
async def health():
    return {"status": "ok", "service": "Wind_Navigator Mission Control", "version": "1.0.0"}

# ── Sim Status ────────────────────────────────────────────────────────────────
@app.get("/v1/status")
async def status():
    OFFLINE = {
        "sim_online": False, "drone_pos": [4.0, 4.0],
        "altitude_m": 0.0, "chaos": 0, "confidence": "OFFLINE",
        "wind_u": 0.0, "wind_v": 0.0, "wind_w": 0.0,
        "waypoint": 0, "total_waypoints": 108,
        "motor_0_health": 85, "sim_time": 0.0,
        "roll_deg": 0.0, "pitch_deg": 0.0, "profit_usd": 0.0,
    }
    if SIM_STATE_FILE.exists():
        try:
            data = json.loads(SIM_STATE_FILE.read_text())
            data["sim_online"] = True
            return data
        except Exception:
            pass
    return OFFLINE

# ── Terrain ───────────────────────────────────────────────────────────────────
@app.get("/v1/terrain")
async def terrain():
    return {"W": TERRAIN_W, "H": TERRAIN_H, "grid": TERRAIN, "max_height": TERRAIN_MAX}

# ── Agent Oracle ──────────────────────────────────────────────────────────────
class WindCheckRequest(BaseModel):
    voxel_x: float
    voxel_y: float
    voxel_z: Optional[float] = 0.0
    drone_mass_kg: Optional[float] = 2.5

@app.post("/v1/wind_check")
async def wind_check(req: WindCheckRequest):
    t0  = time.perf_counter()
    x, y = int(req.voxel_x), int(req.voxel_y)
    x   = max(0, min(TERRAIN_W-1, x))
    y   = max(0, min(TERRAIN_H-1, y))
    bif = _bifurcation(x, y)
    h   = TERRAIN[y][x]

    # Fetch real boundary wind (cached 1 hour)
    wx_data = fetch_weather()
    bu, bv  = wx_data["wind_u"], wx_data["wind_v"]

    if bif:
        chaos  = 38 + h // 2
        conf   = "LOW"
        action = "REROUTE_IMMEDIATELY"
        wu     = round(bu * 4.2 + math.sin(time.time()) * 3, 2)
        wv     = round(bv * 3.5 + math.cos(time.time()) * 2, 2)
        ww     = round(abs(math.sin(time.time() * 3)) * 12.0, 2)
    else:
        chaos  = 2 + h // 20
        conf   = "HIGH"
        action = "MAINTAIN_COURSE"
        wu, wv, ww = round(bu, 2), round(bv, 2), 0.2

    ms = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "voxel":                {"x": x, "y": y},
        "terrain_height_voxels": h,
        "wind_vector":          {"u": wu, "v": wv, "w": ww},
        "chaos_score":           chaos,
        "confidence":            conf,
        "action_advice":         action,
        "bifurcation_detected":  bif,
        "weather_source":        wx_data["source"],
        "query_time_ms":         ms,
    }

# ── NOAA Sync ─────────────────────────────────────────────────────────────────
@app.get("/v1/noaa_sync")
async def noaa_sync(force: bool = False):
    return fetch_weather(force=force)

# ── Moltbook Feed ─────────────────────────────────────────────────────────────
@app.get("/v1/moltbook_feed")
async def moltbook_feed():
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            headers = {"Authorization": f"Bearer {MOLTBOOK_KEY}"}
            me  = (await client.get(f"{MOLTBOOK_API}/agents/me", headers=headers)).json()
            agent = me.get("agent", {})
            posts_resp = (await client.get(
                f"{MOLTBOOK_API}/submolts/wind-navigator/feed?sort=new&limit=5",
                headers=headers
            )).json()
            posts = posts_resp.get("posts", [])
        return {
            "success": True,
            "account": {
                "name":      agent.get("name", "antigravity_gdm_alpha"),
                "karma":     agent.get("karma", 1),
                "followers": agent.get("follower_count", 1),
                "posts":     agent.get("posts_count", 2),
            },
            "recent_posts": [
                {
                    "title":    p.get("title", ""),
                    "submolt":  p.get("submolt", {}).get("name", ""),
                    "upvotes":  p.get("upvotes", 0),
                    "comments": p.get("comment_count", 0),
                    "created":  p.get("created_at", ""),
                }
                for p in posts[:3]
            ],
        }
    except Exception as e:
        return {
            "success": False, "error": str(e),
            "account": {"name": "antigravity_gdm_alpha", "karma": 1, "followers": 1},
        }

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║   WIND_NAVIGATOR  Phase 18 — Mission Control API    ║")
    print("╠══════════════════════════════════════════════════════╣")
    print("║   Dashboard  :  http://127.0.0.1:7777               ║")
    print("║   Agent API  :  POST http://127.0.0.1:7777/v1/wind_check  ║")
    print("║   NOAA data  :  GET  http://127.0.0.1:7777/v1/noaa_sync  ║")
    print("╚══════════════════════════════════════════════════════╝\n")
    uvicorn.run(app, host="127.0.0.1", port=7777, log_level="warning")
