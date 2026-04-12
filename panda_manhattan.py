# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR — Phase 20: Closed-Loop JSBSim PID Control
==========================================================
Physics NOW drives position. Two PID controllers every frame:
  AltitudePID : throttle commands to hold street-level AGL.
                Heavy updraft = altitude actually changes.
  LateralPID  : roll/pitch commands to steer toward waypoint.
                Bifurcation vortex = drone genuinely drifts off route.
Route deviation is tracked, logged, and shown on the dashboard.
"""

import sys, os, math, heapq, json, random
from pid_controller import PID
from rational_wind import rational_wind_components, load_noaa_wind, lbm_bifurcation_score
os.environ['PYTHONUTF8'] = '1'

from panda3d.core import (
    AmbientLight, DirectionalLight, PointLight,
    Vec3, Point3, LColor,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode, Fog,
    LineSegs, TextNode,
    TransparencyAttrib, AntialiasAttrib,
    WindowProperties, NodePath, CardMaker
)
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from direct.gui.OnscreenText import OnscreenText
import jsbsim

# =============================================================================
# TERRAIN
# =============================================================================
def load_terrain(path="urban_terrain.txt"):
    with open(path) as f:
        tokens = f.read().split()
    idx = 0
    W, H = int(tokens[idx]), int(tokens[idx+1]); idx += 2
    grid = []
    for y in range(H):
        grid.append([int(tokens[idx + x]) for x in range(W)])
        idx += W
    return W, H, grid

W, H, TERRAIN = load_terrain()
MAX_H = max(TERRAIN[y][x] for y in range(H) for x in range(W))
SXY   = 0.5            # scene units per voxel (horizontal)
SZ    = 14.0 / MAX_H  # scene units per meter (vertical), tallest = 14

STREET_THRESH = 8  # voxels with terrain < this are "streets / open space"
PAYLOAD_KG       = 10.0  # delivery payload (kg) — change freely
GRAVITY_N_PER_KG = 9.81  # standard gravity (m/s²)

# ── Drone Fleet Profiles ─────────────────────────────────────────────────────
# max_payload = (max_thrust_n - empty_kg * 9.81) / 9.81
DRONE_PROFILES = {
    # Quad |  empty: 1.5 kg |  thrust: 44 N  |  max payload: ~3.0 kg
    "F450":       {"name": "DJI F450 Quadrotor",    "empty_kg": 1.5, "max_thrust_n":  44.0, "motors": 4},
    # Hexa |  empty: 2.5 kg |  thrust: 130 N |  max payload: ~10.8 kg
    "HEXA_PRO":   {"name": "Heavy-Lift Hexacopter", "empty_kg": 2.5, "max_thrust_n": 130.0, "motors": 6},
    # Octo |  empty: 4.0 kg |  thrust: 240 N |  max payload: ~20.5 kg
    "OCTO_CARGO": {"name": "Cargo Octocopter X8",   "empty_kg": 4.0, "max_thrust_n": 240.0, "motors": 8},
}
ACTIVE_DRONE   = "HEXA_PRO"          # ← change this to switch vehicle
_PROFILE       = DRONE_PROFILES[ACTIVE_DRONE]
MAX_THRUST_N   = _PROFILE["max_thrust_n"]
DRONE_EMPTY_KG = _PROFILE["empty_kg"]
print(f"[~] DRONE: {_PROFILE['name']}  |  Empty: {DRONE_EMPTY_KG}kg  |  Max thrust: {MAX_THRUST_N}N  |  Max payload: {(MAX_THRUST_N - DRONE_EMPTY_KG*GRAVITY_N_PER_KG)/GRAVITY_N_PER_KG:.1f}kg")

# =============================================================================
# A* STREET PATHFINDER
# =============================================================================
def find_open_cell(sx, sy):
    """Find the nearest voxel with terrain < STREET_THRESH."""
    for r in range(25):
        for dx in range(-r, r+1):
            for dy in [-r, r] if dx not in (-r, r) else range(-r, r+1):
                x, y = sx+dx, sy+dy
                if 0 <= x < W and 0 <= y < H and TERRAIN[y][x] < STREET_THRESH:
                    return x, y
    return sx, sy

def astar(start_raw, goal_raw, payload_kg: float = 0.0):
    """
    Cost-based A*:
      Street (TERRAIN < STREET_THRESH) : cost 1.0
      Low building (< 40)              : cost 1 + h*0.15   (prefer to avoid)
      Tall building (>= 40)            : cost 1 + h*0.4    (strongly avoid)
    payload_kg: adds canyon-tightness penalty — heavier drones prefer wider
      streets that give more lateral wind-recovery margin.
    """
    sx, sy = find_open_cell(*start_raw)
    gx, gy = find_open_cell(*goal_raw)
    goal   = (gx, gy)

    def heuristic(x, y):
        return math.sqrt((x-gx)**2 + (y-gy)**2)

    open_heap = [(0.0, (sx, sy))]
    came_from = {}
    g_score   = {(sx, sy): 0.0}

    DIRS8 = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]

    while open_heap:
        _, cur = heapq.heappop(open_heap)
        if cur == goal:
            path = []
            while cur in came_from:
                path.append(cur); cur = came_from[cur]
            path.append((sx, sy)); path.reverse()
            return path

        cx, cy = cur
        for dx, dy in DIRS8:
            nx, ny = cx+dx, cy+dy
            if not (0 <= nx < W and 0 <= ny < H):
                continue
            h = TERRAIN[ny][nx]
            if h < STREET_THRESH:
                step_cost = 1.414 if (dx and dy) else 1.0
            elif h < 40:
                step_cost = (1 + h * 0.15) * (1.414 if (dx and dy) else 1.0)
            else:
                step_cost = (1 + h * 0.40) * (1.414 if (dx and dy) else 1.0)

            # Payload canyon-tightness penalty: heavier drones prefer wider streets
            if payload_kg > 0:
                tight = sum(1 for ddx, ddy in [(1,0),(-1,0),(0,1),(0,-1)]
                            if 0 <= nx+ddx < W and 0 <= ny+ddy < H
                            and TERRAIN[ny+ddy][nx+ddx] >= STREET_THRESH)
                step_cost += payload_kg * tight * 0.06

            ng = g_score[cur] + step_cost
            if (nx, ny) not in g_score or ng < g_score[(nx, ny)]:
                g_score[(nx, ny)] = ng
                came_from[(nx, ny)] = cur
                heapq.heappush(open_heap, (ng + heuristic(nx, ny), (nx, ny)))

    print("[!] A* could not reach goal — using diagonal fallback")
    return [(sx, sy), (gx, gy)]

def smooth_path(path, window=4):
    """Running-average smoothing to remove grid-aligned jaggedness."""
    if len(path) < window * 2:
        return path
    smoothed = []
    n = len(path)
    for i in range(n):
        xs = [path[j][0] for j in range(max(0,i-window), min(n,i+window+1))]
        ys = [path[j][1] for j in range(max(0,i-window), min(n,i+window+1))]
        smoothed.append((sum(xs)/len(xs), sum(ys)/len(ys)))
    return smoothed

def build_route(terrain=None, start=(4,4), end=(74,74), payload_kg=None):
    """Generate an A* street route. Accepts custom start/end for swarm drones."""
    pl = payload_kg if payload_kg is not None else PAYLOAD_KG
    raw    = astar(start, end, payload_kg=pl)
    smooth = smooth_path(raw, window=5)
    step   = max(1, len(smooth) // 300)
    route  = []
    for i in range(0, len(smooth), step):
        gx, gy = smooth[i]
        gx_i = max(0, min(W-1, int(gx)))
        gy_i = max(0, min(H-1, int(gy)))
        alt  = TERRAIN[gy_i][gx_i] * SZ + 2.8
        route.append((gx * SXY, gy * SXY, alt))
    print(f"[*] Route: {len(route)} waypoints at street-canyon altitude.")
    return route

# =============================================================================
# BIFURCATIONS
# =============================================================================
def compute_bifurcations():
    bif = set()
    for y in range(1, H-1):
        for x in range(1, W-1):
            if (TERRAIN[y][x+1] - TERRAIN[y][x-1]) * \
               (TERRAIN[y+1][x] - TERRAIN[y-1][x]) < 0:
                bif.add((x, y))
    return bif

BIFURCATIONS = compute_bifurcations()

from swarm_controller import DroneAgent, FLEET, apply_collision_avoidance

# =============================================================================
# GEOMETRY HELPER
# =============================================================================
def make_box_node(r, g, b):
    fmt   = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData('box', fmt, Geom.UHStatic)
    vdata.setNumRows(24)
    vert  = GeomVertexWriter(vdata, 'vertex')
    norm  = GeomVertexWriter(vdata, 'normal')
    col   = GeomVertexWriter(vdata, 'color')
    faces = [
        ((0,-1,0), [(0,0,0),(1,0,0),(1,0,1),(0,0,1)]),
        ((0, 1,0), [(1,1,0),(0,1,0),(0,1,1),(1,1,1)]),
        ((-1,0,0), [(0,1,0),(0,0,0),(0,0,1),(0,1,1)]),
        (( 1,0,0), [(1,0,0),(1,1,0),(1,1,1),(1,0,1)]),
        (( 0,0,1), [(0,0,1),(1,0,1),(1,1,1),(0,1,1)]),
        (( 0,0,-1),[(0,1,0),(1,1,0),(1,0,0),(0,0,0)]),
    ]
    tris = GeomTriangles(Geom.UHStatic)
    vi = 0
    for (nx, ny, nz), verts in faces:
        shade = 1.40 if nz == 1 else (0.50 if nz == -1 else 1.0)
        for (vx, vy, vz) in verts:
            vert.addData3(vx, vy, vz)
            norm.addData3(nx, ny, nz)
            col.addData4(min(r*shade,1), min(g*shade,1), min(b*shade,1), 1)
        tris.addVertices(vi, vi+1, vi+2)
        tris.addVertices(vi, vi+2, vi+3)
        vi += 4
    geom = Geom(vdata); geom.addPrimitive(tris)
    node = GeomNode('box'); node.addGeom(geom)
    return node

# =============================================================================
# APPLICATION
# =============================================================================
class ManhattanSim(ShowBase):

    def __init__(self):
        ShowBase.__init__(self)

        props = WindowProperties()
        props.setTitle(f'WIND_NAVIGATOR v3 — {_PROFILE["name"]} | Payload: {PAYLOAD_KG}kg | Phase 19')
        props.setSize(1280, 720)
        self.win.requestProperties(props)
        self.setBackgroundColor(0.03, 0.05, 0.12, 1)
        self.render.setAntialias(AntialiasAttrib.MAuto)
        self.disableMouse()

        # ── Lighting ──────────────────────────────────────────────────────────
        amb = AmbientLight('amb')
        amb.setColor(LColor(0.55, 0.60, 0.75, 1))
        self.render.setLight(self.render.attachNewNode(amb))

        sun = DirectionalLight('sun')
        sun.setColor(LColor(0.70, 0.75, 1.00, 1))
        snp = self.render.attachNewNode(sun); snp.setHpr(30, -50, 0)
        self.render.setLight(snp)

        fill = DirectionalLight('fill')
        fill.setColor(LColor(0.35, 0.25, 0.10, 1))
        fnp = self.render.attachNewNode(fill); fnp.setHpr(180, 55, 0)
        self.render.setLight(fnp)

        fog = Fog('atmo')
        fog.setColor(0.03, 0.05, 0.10)
        fog.setLinearRange(25, 100)
        self.render.setFog(fog)

        # ── Plan street route first (can take a second) ───────────────────────
        self.ROUTE = build_route()

        # ── Simulation state ──────────────────────────────────────────────────
        self.wp_idx      = 0
        self.frame_n     = 0
        self.trail_pts   = []
        self.confidence  = "HIGH"
        self.chaos       = 2
        self.wind_u      = 0.0
        self.wind_v      = 0.0
        self.wind_w      = 0.0
        self.sim_speed   = 1
        self._wind_nodes = []
        self._bif_nps    = []
        self._follow_cam = True   # Start in canyon follow mode
        self._cam_pos_sm = Vec3(self.ROUTE[0][0], self.ROUTE[0][1] - 8, self.ROUTE[0][2] + 3)
        self._cam_lk_sm  = Vec3(*self.ROUTE[min(5, len(self.ROUTE)-1)])
        # ── Crash state (Phase 19) ─────────────────────────────────────────────
        self.crashed        = False
        self.crash_reason   = ""
        self._crash_t       = 0.0
        self._tumble_phase  = 0.0
        self.crash_altitude = 0.0
        self.crash_waypoint = 0
        # ── Phase 20: Closed-Loop PIDs ───────────────────────────────────────
        # Altitude hold: error = target_agl - actual_agl
        self._alt_pid = PID(kp=0.08, ki=0.005, kd=0.04,
                            out_min=0.0, out_max=0.92)
        # Lateral: error = signed bearing deviation from waypoint
        self._lat_pid = PID(kp=0.035, ki=0.001, kd=0.020,
                            out_min=-0.30, out_max=0.30)
        # Physics position (scene units, initialised to route start)
        self._px = self.ROUTE[0][0]
        self._py = self.ROUTE[0][1]
        self._pz = self.ROUTE[0][2]
        # Velocity (scene units/s)
        self._vx = 0.0
        self._vy = 0.0
        self._vz = 0.0
        # Deviation tracking
        self.max_deviation   = 0.0   # worst lateral deviation (scene units)
        self.total_deviation = 0.0   # cumulative deviation
        self.mission_complete = False
        # Wind seed: used only for LOCAL turbulence INTEGER recurrence (Phase 21)
        # Global wind now comes from NOAA rational decomposition -- no sin()
        self._turb_seed = random.randint(1000, 9999)   # integer seed
        self._turb_x    = self._turb_seed              # integer oscillator state X
        self._turb_y    = self._turb_seed + 1337       # integer oscillator state Y
        # Load NOAA baseline wind (rational integer components)
        _noaa_spd, _noaa_dir = load_noaa_wind()
        self._noaa_u, self._noaa_v = rational_wind_components(_noaa_spd, _noaa_dir)
        print(f"[~] NOAA wind: {_noaa_spd:.0f} mph @ {_noaa_dir:.0f}deg -> "
              f"U={self._noaa_u} V={self._noaa_v} (integer fps, no sin())")

        # -- Phase 22: Spawn swarm agents --------------------------------------
        print(f"[*] Spawning {len(FLEET)} drone agents for swarm mission...")
        self._agents = []
        for i, (prof_key, pl_kg, start, end, color) in enumerate(FLEET):
            agent = DroneAgent(
                agent_id    = i,
                profile_key = prof_key,
                payload_kg  = pl_kg,
                start_cell  = start,
                end_cell    = end,
                color       = color,
                terrain     = TERRAIN,
                route_fn    = build_route,
                SXY         = SXY,
                SZ          = SZ,
                turb_seed   = self._turb_seed,
            )
            self._agents.append(agent)
            status = "FLYABLE" if agent.weight_n < agent.max_thrust else "OVERWEIGHT-CRASH"
            print(f"    Drone {i}: {prof_key} + {pl_kg}kg | "
                  f"{agent.weight_n:.1f}N / {agent.max_thrust:.0f}N | {status} | "
                  f"route: {start}->{end} | {len(agent.route)} wps")

        # ── Build scene ───────────────────────────────────────────────────────
        self._build_ground()
        self._build_city()
        self._build_bif_zones()
        self._build_wind_arrows()
        self._build_drone()
        self._build_swarm_nodes()   # Phase 22: additional drone visuals
        self._trail_root = self.render.attachNewNode('trail')
        self._build_hud()
        self._init_jsbsim()


        self.camera.setPos(self._cam_pos_sm)
        self.camera.lookAt(Point3(*self.ROUTE[0]))

        self.taskMgr.add(self._sim_update,   'sim')
        self.taskMgr.add(self._wind_animate, 'wind')
        self.taskMgr.doMethodLater(1.0, self._write_state, 'state_write')
        self.accept('escape', sys.exit)
        self.accept('q', lambda: setattr(self, 'sim_speed', min(self.sim_speed+1, 6)))
        self.accept('e', lambda: setattr(self, 'sim_speed', max(self.sim_speed-1, 1)))
        self.accept('v', lambda: setattr(self, '_follow_cam', not self._follow_cam))
        print("[+] Ready. V=toggle bird/canyon cam  Q/E=speed  ESC=quit")
        print("[+] Dashboard: http://127.0.0.1:7777  (run mission_api.py)")

    # ─────────────────────────────────────────────────────────────────────────
    def _build_ground(self):
        cm = CardMaker('ground')
        cm.setFrame(0, W*SXY, 0, H*SXY)
        g = self.render.attachNewNode(cm.generate())
        g.setP(-90); g.setPos(0, 0, -0.05)
        g.setColor(0.04, 0.06, 0.10, 1)

    def _build_city(self):
        print(f"[*] Placing {W}x{H} Manhattan buildings (shared GeomNodes)...")
        low_n  = make_box_node(0.37, 0.47, 0.68)
        mid_n  = make_box_node(0.53, 0.63, 0.83)
        tall_n = make_box_node(0.76, 0.81, 0.97)   # glass skyscrapers
        root   = self.render.attachNewNode('city')
        cnt    = 0
        for y in range(H):
            for x in range(W):
                h = TERRAIN[y][x]
                if h < 3: continue
                bh    = max(h * SZ, 0.18)
                gnode = tall_n if h >= 80 else (mid_n if h >= 30 else low_n)
                np    = root.attachNewNode(gnode)
                np.setPos(x*SXY, y*SXY, 0)
                np.setScale(SXY*0.90, SXY*0.90, bh)
                cnt += 1
        print(f"[*] {cnt} buildings placed.")

    def _build_bif_zones(self):
        bif_node = make_box_node(0.9, 0.12, 0.04)
        root = self.render.attachNewNode('bif')
        root.setTransparency(TransparencyAttrib.MAlpha)
        for bx, by in list(BIFURCATIONS)[::4]:
            h  = max(TERRAIN[by][bx] * SZ, 0.2)
            np = root.attachNewNode(bif_node)
            np.setPos(bx*SXY, by*SXY, 0)
            np.setScale(SXY*0.92, SXY*0.92, h + 0.6)
            np.setColorScale(1, 0.18, 0.04, 0.50)
            self._bif_nps.append(np)

    def _build_wind_arrows(self):
        self._wind_root = self.render.attachNewNode('wind')
        STEP = 4
        for gy in range(0, H, STEP):
            for gx in range(0, W, STEP):
                ls = LineSegs()
                ls.setThickness(1.4)
                ls.setColor(0.1, 0.6, 1.0, 0.4)
                ls.moveTo(0,0,0); ls.drawTo(0,0,0.3)
                np = self._wind_root.attachNewNode(ls.create())
                bz = TERRAIN[gy][gx] * SZ + 0.1
                np.setPos(gx*SXY+SXY*0.5, gy*SXY+SXY*0.5, bz)
                self._wind_nodes.append((np, gx, gy))

    def _build_drone(self):
        self._drone      = self.render.attachNewNode('drone')
        body_n = make_box_node(0.28, 0.33, 0.40)
        body   = self._drone.attachNewNode(body_n)
        body.setScale(1.0, 1.0, 0.22); body.setPos(-0.5,-0.5,-0.11)

        arm_n = make_box_node(0.18, 0.23, 0.33)
        ah = self._drone.attachNewNode(arm_n); ah.setScale(2.2,0.12,0.07); ah.setPos(-1.1,-0.06,0)
        av = self._drone.attachNewNode(arm_n); av.setScale(0.12,2.2,0.07); av.setPos(-0.06,-1.1,0)

        healthy = make_box_node(0.0, 0.90, 1.00)
        damaged = make_box_node(1.0, 0.35, 0.00)
        mpos    = [(0.85,0.85),(-0.85,-0.85),(0.85,-0.85),(-0.85,0.85)]
        self._motor_nps = []
        for i, (mx, my) in enumerate(mpos):
            m = self._drone.attachNewNode(damaged if i == 0 else healthy)
            m.setScale(0.28,0.28,0.09); m.setPos(mx-0.14,my-0.14,0.04)
            self._motor_nps.append(m)

        dl = PointLight('dl'); dl.setColor(LColor(0,1,0.85,1))
        dl.setAttenuation((0.5,0,0.06))
        self._drone_light = dl
        dl_np = self._drone.attachNewNode(dl); dl_np.setPos(0,0,0.5)
        self.render.setLight(dl_np)
        self._drone.setScale(0.9)
        self._drone.setPos(*self.ROUTE[0])

    def _build_swarm_nodes(self):
        """Create colour-coded 3D nodes for swarm agents 1..N-1.
        Agent 0 reuses the existing primary _drone node."""
        self._agent_nodes = [self._drone]   # agent 0 = primary drone
        for i, agent in enumerate(self._agents[1:], start=1):
            node = self.loader.loadModel('models/misc/sphere')
            r, g, b = agent.color
            node.setColor(r, g, b, 1.0)
            node.setScale(0.09)   # misc/sphere native radius ~10 -- 0.09 -> ~0.9 unit diameter
            node.reparentTo(self.render)
            if agent.route:
                node.setPos(*agent.route[0])
            self._agent_nodes.append(node)
            print(f"    [+] Swarm node {i}: color=({r:.1f},{g:.1f},{b:.1f})")

    def _update_swarm(self, dt, t):
        """Update all swarm agents and apply collision avoidance."""
        close_pairs = apply_collision_avoidance(self._agents)
        for i, agent in enumerate(self._agents):
            agent.update(dt, t, TERRAIN, W, H, self._noaa_u, self._noaa_v)
            # Move the 3D node
            if i < len(self._agent_nodes):
                self._agent_nodes[i].setPos(agent._px, agent._py, agent._pz)
        if close_pairs:
            for (ai, aj, dist) in close_pairs:
                pass   # future: visual alert on close-approach

    def _build_hud(self):
        self._hud = OnscreenText(
            text='...', mayChange=True,

            scale=0.040, pos=(-1.60, 0.87),
            fg=(0.0, 1.0, 0.8, 1.0),
            shadow=(0, 0.12, 0.06, 0.7),
            align=TextNode.ALeft,
        )
        OnscreenText(
            text='WIND_NAVIGATOR v3  |  A* Street Nav  |  JSBSim F450  |  Phase 17',
            mayChange=False, scale=0.048, pos=(0.0, 0.90),
            fg=(0.3, 0.85, 1.0, 1.0), shadow=(0, 0.1, 0.3, 0.8),
            align=TextNode.ACenter,
        )
        OnscreenText(
            text='[V] Bird/Canyon cam    [Q/E] Speed    [ESC] Quit',
            mayChange=False, scale=0.035, pos=(0.0, -0.94),
            fg=(0.4, 0.5, 0.6, 0.8), align=TextNode.ACenter
        )

    def _init_jsbsim(self):
        root = os.path.dirname(jsbsim.__file__)
        self.fdm = jsbsim.FGFDMExec(root)
        self.fdm.set_debug_level(0)
        self.fdm.load_model('F450')
        self.fdm['ic/lat-geod-deg'] = 40.758
        self.fdm['ic/long-gc-deg']  = -73.985
        self.fdm['ic/h-agl-ft']     = 30.0   # 9m = street level
        self.fdm['ic/vn-fps']       = 3.0
        self.fdm['ic/psi-true-deg'] = 90.0
        self.fdm.run_ic()
        # Apply payload mass — 1 slug = 14.594 kg
        total_kg = DRONE_EMPTY_KG + PAYLOAD_KG
        self.fdm['inertia/mass-slugs'] = total_kg / 14.594
        print(f"[+] {_PROFILE['name']} — total: {total_kg:.1f}kg | thrust: {MAX_THRUST_N}N | payload: {PAYLOAD_KG}kg | margin: {MAX_THRUST_N - total_kg*GRAVITY_N_PER_KG:.1f}N")

    # =========================================================================
    def _trigger_crash(self, reason: str):
        """Halt the drone and enter crash state."""
        self.crashed        = True
        self.crash_reason   = reason
        self._crash_t       = globalClock.getFrameTime()
        self.crash_altitude = self.fdm['position/h-agl-ft'] * 0.3048
        self.crash_waypoint = self.wp_idx
        self.confidence     = "CRASH"
        self.chaos          = 99
        for i in range(4):          # kill motors
            try: self.fdm[f'fcs/throttle-cmd-norm[{i}]'] = 0.0
            except: pass
        log = {
            "crashed":      True, "crash_reason": reason,
            "payload_kg":   PAYLOAD_KG, "max_thrust_n": MAX_THRUST_N,
            "weight_n":     round((DRONE_EMPTY_KG + PAYLOAD_KG) * GRAVITY_N_PER_KG, 1),
            "drone_pos":    [round(self._drone.getPos().x, 2), round(self._drone.getPos().y, 2)],
            "altitude_m":   round(self.crash_altitude, 1),
            "waypoint":     self.wp_idx,
        }
        try:
            with open('crash_log.json', 'w') as f: json.dump(log, f, indent=2)
            print(f"\n[!!!] CRASH: {reason}")
            print(f"[!!!] Crash log → crash_log.json\n")
        except Exception as e:
            print(f"[!] crash log write failed: {e}")

    # =========================================================================
    def _sim_update(self, task):
        dt = globalClock.getDt()
        t  = task.time

        # ── PHASE 19: FLIGHT ENVELOPE CHECK ───────────────────────────────────
        weight_n    = (DRONE_EMPTY_KG + PAYLOAD_KG) * GRAVITY_N_PER_KG
        wind_load_n = abs(self.wind_w) * 0.20      # vertical gust load equivalent
        total_load  = weight_n + wind_load_n
        if not self.crashed and total_load > MAX_THRUST_N:
            stall_type = "OVERWEIGHT" if wind_load_n < 0.5 else "MID-FLIGHT STALL"
            self._trigger_crash(
                f"{stall_type}: {total_load:.1f}N > {MAX_THRUST_N:.0f}N  ({PAYLOAD_KG}kg payload)"
            )

        if self.crashed:
            # ── CRASH ANIMATION ───────────────────────────────────────────────
            self._tumble_phase += dt * 8.0
            self._drone.setHpr(
                self._tumble_phase * 80 % 360,
                45  + math.cos(self._tumble_phase * 1.7) * 30,
                90  + math.sin(self._tumble_phase * 1.3) * 45,
            )
            cur = self._drone.getPos()
            if cur.z > 0.05:
                self._drone.setZ(max(0.0, cur.z - dt * 15))  # fall
            self._drone.setColorScale(1.0, 0.0, 0.0, 1.0)   # turn red
            blink = int((t - self._crash_t) * 3) % 2
            self._hud.setText(
                f"  !! CRASH — FLIGHT TERMINATED !!\n"
                f"  \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\n"
                f"  {self.crash_reason}\n"
                f"  \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\n"
                f"  PAYLOAD   : {PAYLOAD_KG:.1f} kg\n"
                f"  MAX THRUST: {MAX_THRUST_N:.0f} N\n"
                f"  REQUIRED  : {weight_n:.1f} N (weight) + {wind_load_n:.1f} N (gust)\n"
                f"  WAYPOINT  : {self.crash_waypoint}/{len(self.ROUTE)}\n"
                f"  AGL CRASH : {self.crash_altitude:.1f} m\n"
            )
            self._hud.setFg((1.0, 0.0, 0.0, 1.0) if blink else (0.9, 0.2, 0.0, 1.0))
            cp = Vec3(self._drone.getPos().x - 4, self._drone.getPos().y - 4, 6)
            self._cam_pos_sm += (cp - self._cam_pos_sm) * dt * 2
            self.camera.setPos(self._cam_pos_sm)
            self.camera.lookAt(self._drone)
            return Task.cont
        # ── NORMAL FLIGHT ─────────────────────────────────────────────────────
        for _ in range(self.sim_speed):
            wi = min(self.wp_idx, len(self.ROUTE)-1)
            wx, wy, wz = self.ROUTE[wi]
            gx = max(1, min(W-2, int(wx / SXY)))
            gy = max(1, min(H-2, int(wy / SXY)))


            in_bif = (TERRAIN[gy][gx+1] - TERRAIN[gy][gx-1]) * \
                     (TERRAIN[gy+1][gx] - TERRAIN[gy-1][gx]) < 0
            self.chaos      = 38 if in_bif else 2
            self.confidence = "LOW" if in_bif else "HIGH"

            # ── PHASE 21: Rational Wind (no sin/cos) ─────────────────────────
            # Global wind: NOAA rational integer components (fps)
            base_u = self._noaa_u
            base_v = self._noaa_v

            if in_bif:
                # Local bifurcation turbulence: integer Chebyshev recurrence
                # x_{n+1} = (2 * x_n * x_n - x_{n-1}^2) mod PRIME  (integer only)
                PRIME = 104729  # large prime for period length
                new_x = (2 * self._turb_x - self._turb_y) % PRIME
                self._turb_y = self._turb_x
                self._turb_x = new_x
                # Map to [-12, +12] fps range (integer arithmetic)
                tu = ((self._turb_x % 25) - 12)   # integer, range [-12, 12]
                tv = ((self._turb_y % 19) - 9)    # integer, range [-9, 9]
                tw = ((self._turb_x % 15) - 7)    # integer, range [-7, 7]
                self.wind_u = float(base_u + tu)
                self.wind_v = float(base_v + tv)
                self.wind_w = float(tw)
            else:
                # Calm street: NOAA global wind only (rational, steady)
                self.wind_u = float(base_u)
                self.wind_v = float(base_v)
                self.wind_w = 0.2

            self.fdm['atmosphere/u-wind-fps'] = self.wind_u
            self.fdm['atmosphere/v-wind-fps'] = self.wind_v
            self.fdm['atmosphere/w-wind-fps'] = self.wind_w

            # ── PHASE 20: PID CLOSED-LOOP CONTROL ────────────────────────────
            wi   = min(self.wp_idx, len(self.ROUTE)-1)
            wx_t, wy_t, wz_t = self.ROUTE[wi]   # waypoint TARGET (chase goal)

            # ── Altitude PID: hold target AGL ────────────────────────────────
            target_agl_m = 9.0   # street level = 9 m AGL
            actual_agl_m = self.fdm['position/h-agl-ft'] * 0.3048
            alt_err   = target_agl_m - actual_agl_m          # +ve = too low
            thr_cmd   = self._alt_pid.update(alt_err, dt)
            # Payload floor: must at least hover
            hover_floor = min(0.50 + PAYLOAD_KG * 0.09, 0.92)
            thr = max(hover_floor + thr_cmd * 0.15, 0.05)
            thr = min(thr, 0.92)
            m0  = thr * (0.72 if in_bif else 0.85)    # damaged motor cap
            self.fdm['fcs/throttle-cmd-norm[0]'] = m0
            self.fdm['fcs/throttle-cmd-norm[1]'] = thr
            self.fdm['fcs/throttle-cmd-norm[2]'] = thr
            self.fdm['fcs/throttle-cmd-norm[3]'] = thr

            # ── Lateral PID: steer toward next waypoint ───────────────────────
            dx = wx_t - self._px;  dy = wy_t - self._py
            dist_to_wp = math.sqrt(dx*dx + dy*dy)
            bearing = math.atan2(dx, dy)              # desired heading (rad)
            cur_hdg = math.radians(self._drone.getH() if hasattr(self, '_drone') else 0)
            lat_err = math.sin(bearing - cur_hdg)    # signed deviation
            lat_cmd = self._lat_pid.update(lat_err, dt)
            self.fdm['fcs/aileron-cmd-norm']   = lat_cmd * 0.5
            self.fdm['fcs/elevator-cmd-norm']  = -0.04 - lat_cmd * 0.08

            self.fdm.run()

            # ── Physics position integration ──────────────────────────────────
            # Drive toward waypoint at throttle-scaled speed (heavier = slower)
            fwd_len  = max(dist_to_wp, 0.001)
            speed_su = thr * 1.8 / (1.0 + PAYLOAD_KG * 0.04)   # scene units/s
            self._vx = (dx / fwd_len) * speed_su
            self._vy = (dy / fwd_len) * speed_su

            # Wind pushes drone off the A* path — 2.5× amplified in bifurcation
            wind_push_x = self.wind_u * 0.006 * (2.5 if in_bif else 0.10)
            wind_push_y = self.wind_v * 0.006 * (2.5 if in_bif else 0.10)

            self._px += (self._vx + wind_push_x) * dt
            self._py += (self._vy + wind_push_y) * dt
            # -- Altitude: driven by vertical wind only, never by JSBSim AGL.
            #    JSBSim has no position feedback so its h-agl-ft drifts freely.
            #    We use JSBSim only for roll/pitch attitude, not absolute height.
            vert_wind = self.wind_w * 0.015 * (1.8 if in_bif else 0.06)
            vert_wind = max(-0.5, min(0.5, vert_wind))     # hard scene-unit cap
            self._pz  = max(0.05, wz_t + vert_wind)

            # ── Waypoint advance: proximity-based ────────────────────────────
            if dist_to_wp < 0.6 and wi < len(self.ROUTE) - 1:
                self.wp_idx += 1
            elif wi == len(self.ROUTE) - 1 and dist_to_wp < 0.6:
                # Mission complete -- kill throttle, freeze altitude, hold position
                if not self.mission_complete:
                    self.mission_complete = True
                    self._pz = wz_t   # snap to route altitude, stop climbing
                    for i in range(4):
                        try: self.fdm[f'fcs/throttle-cmd-norm[{i}]'] = 0.35
                        except: pass
                    print(f"[+] MISSION COMPLETE -- {self.wp_idx} waypoints, "
                          f"max drift: {self.max_deviation:.2f} su")
                # Hold current XY, don't apply wind push anymore
                self._vx = 0.0; self._vy = 0.0
                wind_push_x = 0.0; wind_push_y = 0.0

            # ── Deviation from planned route ──────────────────────────────────
            plan_x, plan_y = wx_t, wy_t
            deviation = math.sqrt((self._px - plan_x)**2 + (self._py - plan_y)**2)
            self.max_deviation   = max(self.max_deviation, deviation)
            self.total_deviation += deviation * dt

        # ── Apply physics position to drone node (Phase 20) ──────────────────
        lp = Vec3(self._px, self._py, self._pz)
        self._drone.setPos(lp)

        # Heading: blend route tangent with actual velocity direction
        wi = min(self.wp_idx, len(self.ROUTE) - 1)
        wx, wy, wz = self.ROUTE[wi]
        wi_next = min(wi + 3, len(self.ROUTE)-1)
        route_hdg = math.degrees(math.atan2(
            self.ROUTE[wi_next][0] - wx, self.ROUTE[wi_next][1] - wy))
        phi   = self.fdm['attitude/phi-deg']   * 0.18
        theta = self.fdm['attitude/theta-deg'] * 0.18
        # Tilt proportional to lateral wind in bifurcation
        extra_roll = self.wind_u * 0.6 if self.confidence == 'LOW' else 0
        self._drone.setHpr(route_hdg, theta, phi + extra_roll)


        # Motor 0 flicker
        f = 0.5 + 0.5 * math.sin(t * 22)
        self._motor_nps[0].setColorScale(1.0, f*0.3, 0.0, 1.0)
        self._drone_light.setColor(LColor(1.0, 0.15, 0.0, 1) if self.confidence == "LOW"
                                   else LColor(0.0, 1.0, 0.85, 1))

        # Bifurcation pulse
        pulse = 0.28 + 0.35 * math.sin(t * 3.8)
        for np in self._bif_nps:
            np.setColorScale(1.0, 0.15, 0.05, pulse)

        # Trail
        self.trail_pts.append(Point3(lp))
        # Phase 22: update all swarm agents
        self._update_swarm(dt, t)

        if len(self.trail_pts) > 180:
            self.trail_pts.pop(0)
        if len(self.trail_pts) > 2:
            self._trail_root.removeNode()
            self._trail_root = self.render.attachNewNode('trail')
            ls = LineSegs(); ls.setThickness(2.5)
            n_ = len(self.trail_pts)
            for i, pt in enumerate(self.trail_pts):
                a = i / n_
                ls.setColor(0.0, 0.7*a, a, a*0.9)
                ls.moveTo(pt) if i == 0 else ls.drawTo(pt)
            self._trail_root.attachNewNode(ls.create())

        # ── CAMERA ────────────────────────────────────────────────────────────
        # Forward vector from route tangent
        wi_ahead = min(wi + 8, len(self.ROUTE)-1)
        fwd_x = self.ROUTE[wi_ahead][0] - wx
        fwd_y = self.ROUTE[wi_ahead][1] - wy
        fwd_l = math.sqrt(fwd_x**2 + fwd_y**2) + 0.001
        fwd_x /= fwd_l; fwd_y /= fwd_l

        if self._follow_cam:
            # CANYON VIEW: camera behind drone at building height, looking forward
            # Offset: 7 units back along route, 2.5 units up = sees buildings L/R
            cam_tgt = Vec3(lp.x - fwd_x * 7,
                           lp.y - fwd_y * 7,
                           lp.z + 2.5)
        else:
            # BIRD EYE: overhead, slow pan following drone
            cam_tgt = Vec3(lp.x - fwd_x * 3, lp.y - fwd_y * 3, lp.z + 28)

        self._cam_pos_sm += (cam_tgt - self._cam_pos_sm) * dt * 2.5
        look_tgt  = lp + Vec3(fwd_x * 6, fwd_y * 6, 0.5)
        self._cam_lk_sm  += (look_tgt  - self._cam_lk_sm)  * dt * 3.0
        self.camera.setPos(self._cam_pos_sm)
        self.camera.lookAt(self._cam_lk_sm)

        # ── HUD ───────────────────────────────────────────────────────────────
        agl_m    = self._pz / max(SZ, 0.001)    # scene-derived, not JSBSim's drifting AGL
        conf_str = "!! LOW  <- DANGER" if self.confidence == "LOW" else "   HIGH"
        hover_thr = min(0.50 + PAYLOAD_KG * 0.09, 0.92)
        adv_rate  = max(3, int(3 + PAYLOAD_KG * 0.8))
        total_mass = DRONE_EMPTY_KG + PAYLOAD_KG
        max_pl = (MAX_THRUST_N - DRONE_EMPTY_KG * GRAVITY_N_PER_KG) / GRAVITY_N_PER_KG
        self._hud.setText(
            f"  WIND_NAVIGATOR  Phase 19\n"
            f"  ─────────────────────────────────────────\n"
            f"  DRONE     : {_PROFILE['name']}\n"
            f"  MOTORS    : {_PROFILE['motors']}x  |  Max thrust: {MAX_THRUST_N:.0f}N\n"
            f"  MAX PAYLOAD: {max_pl:.1f} kg\n"
            f"  PAYLOAD   : {PAYLOAD_KG:.1f} kg  [LOADED]\n"
            f"  HOVER THR : {hover_thr:.2f}  (adv every {adv_rate} frames)\n"
            f"  SIM TIME  : {t:.1f}s  ({self.sim_speed}x)\n"
            f"  DRONE POS : ({wx:.1f}, {wy:.1f})\n"
            f"  ALTITUDE  : {agl_m:.1f} m AGL\n"
            f"  ROLL      : {phi*5:.1f} deg\n"
            f"  PITCH     : {theta*5:.1f} deg\n"
            f"  WIND U/V/W: {self.wind_u:.0f}/{self.wind_v:.0f}/{self.wind_w:.0f} fps\n"
            f"  CHAOS     : {self.chaos}\n"
            f"  CONFIDENCE: {conf_str}\n"
            f"  MOTOR[0]  : {'72%%' if self.confidence=='LOW' else '85%%'} DAMAGED\n"
            f"  MOTOR[1-3]: 100%%  NOMINAL\n"
            f"  WAYPOINTS : {self.wp_idx}/{len(self.ROUTE)}\n"
        )
        self._hud.setFg((1.0, 0.3, 0.1, 1.0) if self.confidence == "LOW"
                        else (0.0, 1.0, 0.8, 1.0))
        return Task.cont

    # =========================================================================
    def _wind_animate(self, task):
        t = task.time
        for i, (old_np, gx, gy) in enumerate(self._wind_nodes):
            old_np.removeNode()
            gxc = max(1, min(W-2, gx)); gyc = max(1, min(H-2, gy))
            in_bif = (TERRAIN[gyc][gxc+1] - TERRAIN[gyc][gxc-1]) * \
                     (TERRAIN[gyc+1][gxc] - TERRAIN[gyc-1][gxc]) < 0

            ls = LineSegs()
            if in_bif:
                angle = math.sin(t * 2.5 + gx*0.6 + gy*0.4) * math.pi
                mag   = 0.7 + 0.5 * math.sin(t*2 + gx + gy)
                wvx   = math.cos(angle) * mag * 0.35
                wvy   = math.sin(angle) * mag * 0.35
                wvz   = abs(math.sin(t*3.5 + gx*0.3)) * 1.3  # strong updraft
                ls.setColor(1.0, 0.28, 0.04, 0.90); ls.setThickness(2.2)
            else:
                wvx = 0.25 + math.sin(t*0.4 + gy*0.08) * 0.08
                wvy = 0.0; wvz = 0.05
                ls.setColor(0.1, 0.55, 1.0, 0.28); ls.setThickness(1.1)

            ls.moveTo(0, 0, 0); ls.drawTo(wvx, wvy, wvz)
            ls.moveTo(wvx, wvy, wvz)
            ls.drawTo(wvx-wvx*0.4+wvy*0.3, wvy-wvy*0.4-wvx*0.3, wvz*0.6)
            ls.moveTo(wvx, wvy, wvz)
            ls.drawTo(wvx-wvx*0.4-wvy*0.3, wvy-wvy*0.4+wvx*0.3, wvz*0.6)

            bz    = TERRAIN[gyc][gxc] * SZ + 0.15
            new_np = self._wind_root.attachNewNode(ls.create())
            new_np.setPos(gx*SXY+SXY*0.5, gy*SXY+SXY*0.5, bz)
            self._wind_nodes[i] = (new_np, gx, gy)

        return Task.cont

    # =========================================================================
    def _write_state(self, task):
        """Write live telemetry to sim_state.json for the Mission Control dashboard."""
        wi = min(self.wp_idx, len(self.ROUTE)-1)
        wx, wy, _ = self.ROUTE[wi]
        phi   = self.fdm['attitude/phi-deg']   * 0.18
        theta = self.fdm['attitude/theta-deg'] * 0.18
        state = {
            "drone_pos":       [round(wx, 2), round(wy, 2)],
            "altitude_m":      round(self.fdm['position/h-agl-ft'] * 0.3048, 1),
            "chaos":           self.chaos,
            "confidence":      self.confidence,
            "roll_deg":        round(phi * 5, 1),
            "pitch_deg":       round(theta * 5, 1),
            "wind_u":          round(self.wind_u, 1),
            "wind_v":          round(self.wind_v, 1),
            "wind_w":          round(self.wind_w, 1),
            "waypoint":        self.wp_idx,
            "total_waypoints": len(self.ROUTE),
            "motor_0_health":  0 if self.crashed else (72 if self.confidence == 'LOW' else 85),
            "sim_time":        round(globalClock.getFrameTime(), 1),
            "profit_usd":      round(self.wp_idx * 0.10, 2),
            "crashed":         self.crashed,
            "crash_reason":    self.crash_reason,
            "payload_kg":      PAYLOAD_KG,
            "max_thrust_n":    MAX_THRUST_N,
            "weight_n":        round((DRONE_EMPTY_KG + PAYLOAD_KG) * GRAVITY_N_PER_KG, 1),
            # Phase 20 — closed-loop deviation metrics
            "drone_model":      _PROFILE["name"],
            "motors":           _PROFILE["motors"],
            "max_deviation_su": round(self.max_deviation, 3),
            "total_deviation":  round(self.total_deviation, 2),
            "physics_pos":      [round(self._px, 2), round(self._py, 2), round(self._pz, 2)],
            "control_mode":     "CLOSED_LOOP_PID",
            "wind_mode":        "NOAA_RATIONAL_INTEGER",   # Phase 21: no sin()
            "noaa_u_fps":       self._noaa_u,
            "noaa_v_fps":       self._noaa_v,
        }
        try:
            with open('sim_state.json', 'w') as f:
                json.dump(state, f)
        except Exception:
            pass
        return Task.again


if __name__ == '__main__':
    ManhattanSim().run()


