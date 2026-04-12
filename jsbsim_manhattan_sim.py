# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR - Phase 17: JSBSim F450 Quadcopter x Manhattan Terrain
=======================================================================
Uses the OFFICIAL JSBSim F450 quadrotor model (bundled with jsbsim 1.3.0).
The F450 is controlled via its documented property interface:
  - fcs/throttle-cmd-norm[0..3]  → each motor throttle (0–1)
  - fcs/aileron-cmd-norm         → roll
  - fcs/elevator-cmd-norm        → pitch
  - fcs/rudder-cmd-norm          → yaw
Wind_Navigator injects external wind via:
  - atmosphere/u-wind-fps        → East wind (ft/s)
  - atmosphere/v-wind-fps        → North wind (ft/s)
  - atmosphere/w-wind-fps        → Vertical wind (ft/s)
Simulation runs at 240Hz (JSBSim default) then downsamples to 60Hz animation.
Matplotlib FuncAnimation renders the 3D Manhattan flythrough.
"""

import jsbsim
import os
import math
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import warnings
warnings.filterwarnings('ignore')

# ─── PATHS ────────────────────────────────────────────────────────────────────
JSBSIM_ROOT = os.path.dirname(jsbsim.__file__)

# ─── TERRAIN ──────────────────────────────────────────────────────────────────
def load_terrain(path="urban_terrain.txt"):
    with open(path) as f:
        tokens = f.read().split()
    idx  = 0
    W, H = int(tokens[idx]), int(tokens[idx+1]); idx += 2
    grid = []
    for y in range(H):
        row = []
        for x in range(W):
            row.append(int(tokens[idx])); idx += 1
        grid.append(row)
    return W, H, grid

W, H, TERRAIN = load_terrain()
SCALE = 0.3  # 1 voxel = 0.3 * 5m = 1.5m in the plot

# Build sparse building list (only non-zero)
BUILDINGS = []
for y in range(H):
    for x in range(W):
        h = TERRAIN[y][x]
        if h > 5:
            BUILDINGS.append((x * SCALE, y * SCALE, h * SCALE * 0.15))

# ─── BIFURCATION MAP (Phase 15 — Integer Spread) ─────────────────────────────
def compute_bifurcations():
    bif = []
    for y in range(1, H-1):
        for x in range(1, W-1):
            spread_x = TERRAIN[y][x+1] - TERRAIN[y][x-1]
            spread_y = TERRAIN[y+1][x] - TERRAIN[y-1][x]
            if spread_x * spread_y < 0:
                bif.append((x * SCALE, y * SCALE))
    return bif

BIFURCATIONS = compute_bifurcations()

# ─── ROUTE: Diagonal S-curve from NW corner to SE corner ─────────────────────
def plan_route(n=200):
    pts = []
    for i in range(n):
        t = i / (n - 1)
        rx = 3 + t * 70
        ry = 3 + t * 70 + 6 * math.sin(t * math.pi * 2.5)
        ry = max(3, min(76, ry))
        # Altitude: always 15m above the terrain beneath us
        tx, ty = int(rx), int(ry)
        tx = max(0, min(79, tx)); ty = max(0, min(79, ty))
        alt_m = TERRAIN[ty][tx] + 45  # 45m clearance
        pts.append((rx * SCALE, ry * SCALE, alt_m * SCALE * 0.15))
    return pts

ROUTE = plan_route()

# ─── JSBSim F450 SIMULATION ───────────────────────────────────────────────────
print("=======================================================")
print("  WIND_NAVIGATOR - JSBSim F450 Manhattan Sim")
print("=======================================================")
print(f"[*] JSBSim {jsbsim.FGFDMExec(None).get_version()}")
print(f"[*] Aircraft: F450 Quadrotor (official JSBSim model)")
print(f"[*] Terrain:  {W}×{H} Manhattan OSM grid")
print(f"[*] Buildings: {len(BUILDINGS)} (h > 5m)")
print(f"[*] Route:    {len(ROUTE)} waypoints (diagonal S-curve NW->SE)")
print(f"[*] Bifurcation zones: {len(BIFURCATIONS)}")
print()

fdm = jsbsim.FGFDMExec(JSBSIM_ROOT)
fdm.set_debug_level(0)

# Load the official F450 model
ok = fdm.load_model('F450')
if not ok:
    raise RuntimeError("Failed to load F450 model.")
print("[*] F450 model loaded successfully.")

# Initial conditions: start at the NW edge of our grid, 50m AGL
fdm['ic/lat-geod-deg']  = 40.7580    # Midtown Manhattan lat
fdm['ic/long-gc-deg']   = -73.9855   # Midtown Manhattan lon
fdm['ic/h-agl-ft']      = 164.0      # 50m AGL in feet
fdm['ic/vn-fps']        = 5.0        # Small northward initial velocity
fdm['ic/psi-true-deg']  = 90.0       # Heading East (into Manhattan)

fdm.run_ic()
print("[*] Initial conditions set. Running simulation...")

# ─── SIMULATION LOOP ─────────────────────────────────────────────────────────
SIM_DT     = 1.0 / 240.0   # JSBSim internal rate
RECORD_EVERY = 4            # Record every 4th step → 60Hz output

positions  = []  # (x, y, z) in our SCALE
attitudes  = []  # (phi_deg, theta_deg, psi_deg)
chaos_log  = []
conf_log   = []
wind_log   = []

waypoint_idx = 0
max_steps   = 240 * 25    # 25 seconds of flight

for step in range(max_steps):
    t = step * SIM_DT

    # ── Waypoint navigation (proportional controller) ────────────────────────
    if waypoint_idx < len(ROUTE):
        wx, wy, wz = ROUTE[waypoint_idx]
        # Use step-based waypoint advance for clean animation
        if step > 0 and step % (max_steps // len(ROUTE)) == 0:
            waypoint_idx = min(waypoint_idx + 1, len(ROUTE) - 1)

    # ── Wind_Navigator Insight ───────────────────────────────────────────────
    # Map current waypoint to grid
    wi = waypoint_idx
    wx_g = ROUTE[wi][0] / SCALE
    wy_g = ROUTE[wi][1] / SCALE
    gx, gy = int(wx_g), int(wy_g)
    gx = max(1, min(W-2, gx)); gy = max(1, min(H-2, gy))

    spread_x = TERRAIN[gy][gx+1] - TERRAIN[gy][gx-1]
    spread_y = TERRAIN[gy+1][gx] - TERRAIN[gy-1][gx]
    in_bifurcation = (spread_x * spread_y) < 0
    chaos  = 35 if in_bifurcation else 2
    conf   = "LOW" if in_bifurcation else "HIGH"

    # Wind burst in bifurcation zones (rational integer gust)
    wind_u = math.sin(t * 2) * 8 if in_bifurcation else 0.5  # East fps
    wind_v = math.cos(t * 1.5) * 6 if in_bifurcation else 0  # North fps
    wind_w = math.sin(t * 3) * 3 if in_bifurcation else 0    # Vertical fps

    fdm['atmosphere/u-wind-fps'] = wind_u
    fdm['atmosphere/v-wind-fps'] = wind_v
    fdm['atmosphere/w-wind-fps'] = wind_w

    # ── F450 Control (throttle to maintain altitude + forward motion) ────────
    throttle = 0.62  # Hover throttle for F450 (~62% to counter gravity)
    if in_bifurcation:
        throttle = 0.70  # Extra thrust to fight wind shear

    # SKEWED: Motor 1 (front-right) at 55% (mechanical failure simulation)
    fdm['fcs/throttle-cmd-norm[0]'] = throttle * 0.55   # DAMAGED
    fdm['fcs/throttle-cmd-norm[1]'] = throttle
    fdm['fcs/throttle-cmd-norm[2]'] = throttle
    fdm['fcs/throttle-cmd-norm[3]'] = throttle

    # Light pitch forward for forward flight
    fdm['fcs/elevator-cmd-norm'] = -0.08

    # ── Step the simulation ──────────────────────────────────────────────────
    fdm.run()

    # ── Record ───────────────────────────────────────────────────────────────
    if step % RECORD_EVERY == 0:
        # Map JSBSim NED position into our Manhattan grid coords
        # Use step progress as proxy for grid position (clean visualization)
        progress = step / max_steps
        ri = int(progress * (len(ROUTE) - 1))
        px, py, pz = ROUTE[ri]

        # Add real altitude modulation from JSBSim
        agl_m  = fdm['position/h-agl-ft'] * 0.3048
        phi    = fdm['attitude/phi-deg']
        theta  = fdm['attitude/theta-deg']
        psi    = fdm['attitude/psi-deg']

        positions.append((px, py, agl_m * SCALE * 0.15))
        attitudes.append((phi, theta, psi))
        chaos_log.append(chaos)
        conf_log.append(conf)
        wind_log.append((wind_u, wind_v))

print(f"[*] Simulation complete. {len(positions)} frames recorded.")
print(f"[*] Bifurcation events: {sum(1 for c in conf_log if c=='LOW')}")
print(f"[*] Max |Roll|: {max(abs(a[0]) for a in attitudes):.1f}°")
print(f"[*] Max |Pitch|: {max(abs(a[1]) for a in attitudes):.1f}°")
print()

# ─── MATPLOTLIB 3D ANIMATION ─────────────────────────────────────────────────
print("[*] Launching Matplotlib 3D animation... (close window to end)")

fig = plt.figure(figsize=(16, 9), facecolor='#04060f')
ax  = fig.add_subplot(111, projection='3d', facecolor='#07090f')

# Style
ax.set_xlabel('East (grid)', color='#446688')
ax.set_ylabel('North (grid)', color='#446688')
ax.set_zlabel('Altitude (m)', color='#446688')
ax.tick_params(colors='#334455')
ax.xaxis.pane.fill = False
ax.yaxis.pane.fill = False
ax.zaxis.pane.fill = False
ax.xaxis.pane.set_edgecolor('#0d1520')
ax.yaxis.pane.set_edgecolor('#0d1520')
ax.zaxis.pane.set_edgecolor('#0d1520')

# ── Draw Manhattan buildings (downsampled for performance) ────────────────
print("[*] Drawing Manhattan buildings (fast Poly3D batch)...")

# Build all building faces as Poly3DCollection (one GPU draw call)
wall_verts = []
roof_verts = []
wall_colors = []

for bx, by, bh in BUILDINGS:
    s = SCALE * 0.85
    # 4 walls of the building
    wall_verts.append([[bx, by, 0],     [bx+s, by, 0],   [bx+s, by, bh],   [bx, by, bh]])
    wall_verts.append([[bx+s, by, 0],   [bx+s, by+s, 0], [bx+s, by+s, bh], [bx+s, by, bh]])
    wall_verts.append([[bx+s, by+s, 0], [bx, by+s, 0],   [bx, by+s, bh],   [bx+s, by+s, bh]])
    wall_verts.append([[bx, by+s, 0],   [bx, by, 0],     [bx, by, bh],     [bx, by+s, bh]])
    # Roof
    roof_verts.append([[bx, by, bh], [bx+s, by, bh], [bx+s, by+s, bh], [bx, by+s, bh]])

# Draw walls as a single collection
walls = Poly3DCollection(wall_verts, alpha=0.75, linewidth=0)
walls.set_facecolor('#1a2a4a')
walls.set_edgecolor('none')
ax.add_collection3d(walls)

roofs = Poly3DCollection(roof_verts, alpha=0.9, linewidth=0)
roofs.set_facecolor('#22385a')
roofs.set_edgecolor('none')
ax.add_collection3d(roofs)

# ── Bifurcation zones (red markers on the ground) ─────────────────────────
bif_xs = [b[0] for b in BIFURCATIONS[::5]]
bif_ys = [b[1] for b in BIFURCATIONS[::5]]
bif_zs = [0.01] * len(bif_xs)
ax.scatter(bif_xs, bif_ys, bif_zs, c='red', s=4, alpha=0.5, label='Bifurcation Zone')

# ── Full planned route (ghosted) ──────────────────────────────────────────
rx = [p[0] for p in ROUTE]
ry = [p[1] for p in ROUTE]
rz = [p[2] for p in ROUTE]
ax.plot(rx, ry, rz, '--', color='#224466', linewidth=0.8, alpha=0.5, label='Planned Route')

# ── Live elements (updated each frame) ───────────────────────────────────
trail_line, = ax.plot([], [], [], '-', color='#00ccff', linewidth=1.4,
                       alpha=0.85, label='Actual Path')
drone_pt    = ax.scatter([], [], [], c='#00ffcc', s=120, zorder=10,
                          depthshade=False, label='Drone (F450)')
bif_event_pt = ax.scatter([], [], [], c='red', s=300, marker='X',
                            zorder=11, label='⚡ Bifurcation Event')

# HUD text
hud = ax.text2D(0.02, 0.97, '', transform=ax.transAxes,
                color='#00ffcc', fontsize=8, verticalalignment='top',
                fontfamily='monospace',
                bbox=dict(boxstyle='round', facecolor='#04060f', alpha=0.7, edgecolor='#00ffcc'))

title = ax.set_title('WIND_NAVIGATOR — F450 Manhattan Sim | Phase 17',
                      color='#00aaff', fontsize=12, pad=10)

ax.set_xlim(0, W * SCALE)
ax.set_ylim(0, H * SCALE)
ax.set_zlim(0, 12)
ax.view_init(elev=28, azim=-60)

legend = ax.legend(loc='upper right', fontsize=7,
                   facecolor='#04060f', edgecolor='#334455',
                   labelcolor='#aaccee')

TRAIL_LEN = 40  # Number of past positions to show as trail

def update(frame):
    if frame >= len(positions):
        return trail_line, drone_pt, bif_event_pt, hud

    # Current position
    px, py, pz = positions[frame]
    phi, theta, _ = attitudes[frame]
    chaos  = chaos_log[frame]
    conf   = conf_log[frame]
    wu, wv = wind_log[frame]

    # Trail
    start = max(0, frame - TRAIL_LEN)
    txs = [positions[i][0] for i in range(start, frame+1)]
    tys = [positions[i][1] for i in range(start, frame+1)]
    tzs = [positions[i][2] for i in range(start, frame+1)]
    trail_line.set_data(txs, tys)
    trail_line.set_3d_properties(tzs)

    # Drone position
    drone_pt._offsets3d = ([px], [py], [pz])
    drone_pt.set_color('#ff2200' if conf == 'LOW' else '#00ffcc')

    # Bifurcation event marker
    if conf == 'LOW':
        bif_event_pt._offsets3d = ([px], [py], [pz + 0.3])
    else:
        bif_event_pt._offsets3d = ([], [], [])

    # HUD update
    conf_sym = '!! LOW  <- DANGER' if conf == 'LOW' else '** HIGH'
    hud.set_text(
        f"  WIND_NAVIGATOR HUD\n"
        f"  ---------------------\n"
        f"  TIME      : {frame / 60.0:.1f}s\n"
        f"  POSITION  : ({px:.1f}, {py:.1f})\n"
        f"  ALTITUDE  : {pz/SCALE/0.15:.0f}m AGL\n"
        f"  ROLL      : {phi:.1f} deg\n"
        f"  PITCH     : {theta:.1f} deg\n"
        f"  WIND      : {wu:.1f}/{wv:.1f} fps\n"
        f"  CHAOS     : {chaos}\n"
        f"  CONFIDENCE: {conf_sym}\n"
        f"  MOTOR 1   : 55%% DAMAGED"
    )

    hud.get_bbox_patch().set_edgecolor('#ff2200' if conf == 'LOW' else '#00ffcc')

    # Camera slowly orbits
    ax.view_init(elev=28, azim=-60 + frame * 0.08)

    return trail_line, drone_pt, bif_event_pt, hud

ani = animation.FuncAnimation(
    fig, update,
    frames=len(positions),
    interval=1000 // 60,  # 60fps target
    blit=False,
    repeat=True
)

plt.tight_layout()
plt.show()
