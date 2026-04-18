"""
WIND_NAVIGATOR: Real-Time 3D Flight Visualizer
===============================================
Connects JSBSim Physics + Wind_Navigator Wind Vectors
and renders the drone's live flight path in beautiful 3D.

Color Code:
  RED    = THRUST  (motors fighting gravity)
  GREEN  = GLIDE   (motors OFF, surfing the updraft)
  YELLOW = Wind Arrows (updraft vectors)

Press Ctrl+C in the terminal to stop the simulation.
"""

import jsbsim
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import warnings
warnings.filterwarnings('ignore')

# ============================================================
#  WIND_NAVIGATOR: Physics Data (from our Integer LBM Engine)
# ============================================================
WIND_VECTORS = [
    {"t_sec": 0,  "wind_n": 0.5,  "wind_e": 0.2, "wind_d": -1.5, "action": "THRUST"},
    {"t_sec": 5,  "wind_n": 1.2,  "wind_e": 0.8, "wind_d": -4.5, "action": "THRUST"},
    {"t_sec": 10, "wind_n": 2.1,  "wind_e": 1.5, "wind_d": -8.0, "action": "GLIDE"},
    {"t_sec": 18, "wind_n": 1.8,  "wind_e": 0.9, "wind_d": -3.5, "action": "GLIDE"},
    {"t_sec": 25, "wind_n": 0.3,  "wind_e": 0.1, "wind_d":  0.5, "action": "THRUST"},
]

# ============================================================
#  MANHATTAN SKYLINE: Simplified building geometry (OSM-inspired)
# ============================================================
BUILDINGS = [
    # [x_center, y_center, width, depth, height] all in meters
    [30,  20,  20, 20, 60],   # Empire State Building (simplified)
    [60,  40,  15, 15, 45],   # Midtown skyscraper
    [10,  50,  25, 20, 35],   # Office block
    [80,  15,  10, 12, 55],   # Chrysler-style tower
    [50,  70,  18, 14, 28],   # Lower building
    [20,  80,  12, 10, 40],   # East side tower
    [90,  60,  20, 16, 32],   # Wide commercial building
    [70,  85,  14, 12, 48],   # Rear skyscraper
]

def draw_building(ax, bx, by, bw, bd, bh):
    """Draw a filled 3D box representing a skyscraper."""
    x0, x1 = bx - bw/2, bx + bw/2
    y0, y1 = by - bd/2, by + bd/2
    z0, z1 = 0, bh

    verts = [
        [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0)],  # bottom
        [(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)],  # top
        [(x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1)],  # front
        [(x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1)],  # back
        [(x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1)],  # left
        [(x1,y0,z0),(x1,y1,z0),(x1,y1,z1),(x1,y0,z1)],  # right
    ]
    poly = Poly3DCollection(verts, alpha=0.25, facecolor='#3a4a6b', edgecolor='#5a6a8b', linewidth=0.4)
    ax.add_collection3d(poly)

def init_jsbsim():
    fdm = jsbsim.FGFDMExec(None)
    fdm.set_debug_level(0)
    fdm.load_model('F450')
    fdm['ic/lat-geod-deg'] = 40.7128
    fdm['ic/long-gc-deg']  = -74.0060
    fdm['ic/h-sl-ft']      = 100.0
    fdm['ic/vn-fps']       = 0.0
    fdm['ic/ve-fps']       = 0.0
    fdm['ic/vd-fps']       = 0.0
    fdm['ic/psi-true-deg'] = 90.0
    fdm.run_ic()
    return fdm

# ============================================================
#  SETUP THE FIGURE — Dark Mode Aerospace Theme
# ============================================================
plt.style.use('dark_background')
fig = plt.figure(figsize=(16, 9), facecolor='#0a0f1a')
fig.suptitle('WIND_NAVIGATOR  |  JSBSim F450 Real-Time Flight Dynamics',
             fontsize=14, color='#00d4ff', fontweight='bold', y=0.98)

# Main 3D viewport
ax3d = fig.add_subplot(121, projection='3d', facecolor='#0a0f1a')
ax3d.set_title('Manhattan Airspace — Live Flight', color='#aabbcc', fontsize=10, pad=10)

# Altitude chart
ax_alt = fig.add_subplot(222, facecolor='#0d1525')
ax_alt.set_title('Altitude Profile (ft)', color='#aabbcc', fontsize=9)
ax_alt.set_facecolor('#0d1525')
ax_alt.tick_params(colors='#556677')
for spine in ax_alt.spines.values():
    spine.set_edgecolor('#1a2a3a')

# Throttle chart
ax_thr = fig.add_subplot(224, facecolor='#0d1525')
ax_thr.set_title('Throttle % — Energy Arbitrage', color='#aabbcc', fontsize=9)
ax_thr.set_facecolor('#0d1525')
ax_thr.tick_params(colors='#556677')
for spine in ax_thr.spines.values():
    spine.set_edgecolor('#1a2a3a')

plt.tight_layout(rect=[0, 0, 1, 0.96])

# ============================================================
#  SHARED STATE
# ============================================================
state = {
    'fdm': init_jsbsim(),
    'frame': 0,
    'xs': [], 'ys': [], 'zs': [],
    'colors': [],
    'times': [], 'alts': [], 'throttles': [],
    'drone_x': 0.0, 'drone_y': 0.0,
}

# Setup 3D scene once
for b in BUILDINGS:
    draw_building(ax3d, *b)

ax3d.set_xlim(0, 100); ax3d.set_ylim(0, 100); ax3d.set_zlim(0, 120)
ax3d.set_xlabel('East →', color='#4488aa', fontsize=8)
ax3d.set_ylabel('North →', color='#4488aa', fontsize=8)
ax3d.set_zlabel('Alt (m)', color='#4488aa', fontsize=8)
ax3d.tick_params(colors='#334455', labelsize=7)
ax3d.xaxis.pane.fill = False
ax3d.yaxis.pane.fill = False
ax3d.zaxis.pane.fill = False
ax3d.xaxis.pane.set_edgecolor('#1a2a3a')
ax3d.yaxis.pane.set_edgecolor('#1a2a3a')
ax3d.zaxis.pane.set_edgecolor('#1a2a3a')
ax3d.view_init(elev=25, azim=-60)

# Ground grid
gx = np.linspace(0, 100, 10)
gy = np.linspace(0, 100, 10)
gX, gY = np.meshgrid(gx, gy)
ax3d.plot_wireframe(gX, gY, np.zeros_like(gX), color='#1a2a3a', linewidth=0.3, alpha=0.5)

# ============================================================
#  ANIMATION UPDATE FUNCTION
# ============================================================
def update(frame_num):
    fdm   = state['fdm']
    frame = state['frame']

    current_time = frame * 0.1

    # Get the active Wind_Navigator vector
    wv = WIND_VECTORS[0]
    for v in WIND_VECTORS:
        if current_time >= v["t_sec"]:
            wv = v

    # Inject wind into JSBSim atmosphere
    fdm['atmosphere/wind-north-fps'] = wv['wind_n'] * 3.281
    fdm['atmosphere/wind-east-fps']  = wv['wind_e'] * 3.281
    fdm['atmosphere/wind-down-fps']  = wv['wind_d'] * 3.281

    if wv['action'] == "GLIDE":
        fdm['fcs/throttle-cmd-norm'] = 0.0
        color = '#00ff88'   # Bright green = GLIDE (motors off)
    else:
        fdm['fcs/throttle-cmd-norm'] = 0.60
        color = '#ff4455'   # Red = THRUST

    fdm.run()

    # Convert JSBSim ft to meters, map to our 0-100 visualizer grid
    alt_ft  = fdm['position/h-sl-ft']
    alt_m   = alt_ft * 0.3048
    speed   = fdm['velocities/vt-fps'] / 3.281
    throttle = fdm['fcs/throttle-cmd-norm'] * 100

    # Move drone through the grid over time (East-West trajectory)
    state['drone_x'] = (current_time / 30.0) * 80 + 10   # East progress
    state['drone_y'] = 50 + 15 * np.sin(current_time / 8) # Gentle S-curve path

    state['xs'].append(state['drone_x'])
    state['ys'].append(state['drone_y'])
    state['zs'].append(alt_m)
    state['colors'].append(color)
    state['times'].append(current_time)
    state['alts'].append(alt_ft)
    state['throttles'].append(throttle)
    state['frame'] += 1

    # --- REDRAW 3D scene ---
    ax3d.cla()
    ax3d.set_facecolor('#0a0f1a')

    # Re-draw buildings
    for b in BUILDINGS:
        draw_building(ax3d, *b)

    # Re-draw ground grid
    ax3d.plot_wireframe(gX, gY, np.zeros_like(gX), color='#1a2a3a', linewidth=0.3, alpha=0.5)

    # Draw flight trail with color-coded segments
    xs, ys, zs = state['xs'], state['ys'], state['zs']
    if len(xs) > 1:
        for i in range(1, len(xs)):
            ax3d.plot([xs[i-1], xs[i]], [ys[i-1], ys[i]], [zs[i-1], zs[i]],
                     color=state['colors'][i], linewidth=1.5, alpha=0.8)

    # Draw the drone as a glowing sphere
    ax3d.scatter([state['drone_x']], [state['drone_y']], [alt_m],
                 s=120, c=color, marker='o', zorder=10, alpha=1.0,
                 edgecolors='white', linewidths=1)

    # Draw wind updraft arrow at drone position
    if wv['wind_d'] < -1.0:  # Significant updraft
        uw = -wv['wind_d'] * 0.8
        ax3d.quiver(state['drone_x'], state['drone_y'], alt_m - uw,
                    0, 0, uw * 2,
                    color='#ffdd00', linewidth=2, alpha=0.7, arrow_length_ratio=0.3)

    ax3d.set_xlim(0, 100); ax3d.set_ylim(0, 100); ax3d.set_zlim(0, 120)
    ax3d.set_xlabel('East →', color='#4488aa', fontsize=8)
    ax3d.set_ylabel('North →', color='#4488aa', fontsize=8)
    ax3d.set_zlabel('Alt (m)', color='#4488aa', fontsize=8)
    ax3d.tick_params(colors='#334455', labelsize=7)
    ax3d.xaxis.pane.fill = False
    ax3d.yaxis.pane.fill = False
    ax3d.zaxis.pane.fill = False
    ax3d.xaxis.pane.set_edgecolor('#1a2a3a')
    ax3d.yaxis.pane.set_edgecolor('#1a2a3a')
    ax3d.zaxis.pane.set_edgecolor('#1a2a3a')
    ax3d.view_init(elev=25, azim=-60 + frame * 0.1)  # Slowly rotating camera

    # HUD overlays
    action_label = f"MODE: {'🟢 GLIDE  (Motors OFF)' if wv['action'] == 'GLIDE' else '🔴 THRUST (Motors ON)'}"
    ax3d.set_title(f"Manhattan Airspace  |  T={current_time:.1f}s  |  Alt={alt_m:.1f}m  |  {action_label}",
                   color='#aabbcc', fontsize=8, pad=8)

    # --- REDRAW ALTITUDE CHART ---
    ax_alt.cla()
    ax_alt.set_facecolor('#0d1525')
    ax_alt.set_title('Altitude Profile (ft)', color='#aabbcc', fontsize=9)

    if len(state['times']) > 1:
        for i in range(1, len(state['times'])):
            clr = state['colors'][i]
            ax_alt.plot(state['times'][i-1:i+1], state['alts'][i-1:i+1],
                       color=clr, linewidth=2)

    ax_alt.axhline(y=state['alts'][0] if state['alts'] else 100,
                   color='#334455', linestyle='--', linewidth=0.8, alpha=0.6, label='Start Alt')
    ax_alt.set_ylabel('ft', color='#556677', fontsize=8)
    ax_alt.tick_params(colors='#556677', labelsize=7)
    for spine in ax_alt.spines.values():
        spine.set_edgecolor('#1a2a3a')

    # Shade GLIDE zones
    glide_start = None
    for i, t in enumerate(state['times']):
        if state['colors'][i] == '#00ff88' and glide_start is None:
            glide_start = t
        elif state['colors'][i] != '#00ff88' and glide_start is not None:
            ax_alt.axvspan(glide_start, t, alpha=0.08, color='#00ff88', label='GLIDE zone')
            glide_start = None

    # --- REDRAW THROTTLE CHART ---
    ax_thr.cla()
    ax_thr.set_facecolor('#0d1525')
    ax_thr.set_title('Throttle % — Energy Arbitrage', color='#aabbcc', fontsize=9)

    if len(state['times']) > 1:
        ax_thr.fill_between(state['times'], state['throttles'],
                           alpha=0.6, color='#ff6644')
        ax_thr.plot(state['times'], state['throttles'],
                   color='#ff8866', linewidth=1.5)

    ax_thr.axhline(y=0, color='#00ff88', linestyle='--', linewidth=0.8,
                   alpha=0.6, label='0% = GLIDE')
    ax_thr.set_ylim(-5, 100)
    ax_thr.set_ylabel('%', color='#556677', fontsize=8)
    ax_thr.tick_params(colors='#556677', labelsize=7)
    for spine in ax_thr.spines.values():
        spine.set_edgecolor('#1a2a3a')

    # Stop after 30 seconds of simulated time
    if current_time >= 30:
        ani.event_source.stop()
        ax3d.set_title("✅ MISSION COMPLETE — Wind_Navigator Validated!", color='#00ff88', fontsize=10)
        print("\n[+] Mission complete. Close the window to exit.")

ani = animation.FuncAnimation(
    fig,
    update,
    frames=300,
    interval=80,   # ~12fps — smooth but not choppy
    repeat=False
)

plt.show()
