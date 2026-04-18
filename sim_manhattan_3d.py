"""
WIND_NAVIGATOR — Phase 17: 3D Manhattan Drone Simulation
=========================================================
A self-contained simulation + visualizer.
  1. Parses urban_terrain.txt → renders Manhattan as 3D buildings
  2. Runs the Rational 6-DOF physics on a pre-planned route
  3. Injects Wind_Navigator bifurcation events dynamically
  4. Serves a Three.js WebGL scene you can spin/zoom in the browser
  5. Drone leaves a glowing trail. Bifurcation zones pulse in red.
     Attractor zones pulse in green.

Run:  python sim_manhattan_3d.py
Open: http://127.0.0.1:7777
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import asyncio, json, math, os

app = FastAPI()

# ─── Parse the Manhattan Terrain ─────────────────────────────────────────────
def load_terrain(path="urban_terrain.txt"):
    with open(path) as f:
        lines = f.read().split()
    idx = 0
    W, H = int(lines[idx]), int(lines[idx+1]); idx += 2
    grid = []
    for y in range(H):
        row = []
        for x in range(W):
            row.append(int(lines[idx])); idx += 1
        grid.append(row)
    return W, H, grid

W, H, TERRAIN = load_terrain()

# ─── Pre-plan the route (A* style waypoints across the grid) ─────────────────
# Route diagonally from top-left to bottom-right, weaving around tall blocks
RAW_ROUTE = []
for step in range(120):
    t = step / 119.0
    # Slight S-curve to navigate between block clusters
    rx = int(3 + t * 72)
    ry = int(3 + t * 72 + 8 * math.sin(t * math.pi * 3))
    ry = max(3, min(76, ry))
    rx = max(3, min(76, rx))
    alt = max(TERRAIN[ry][rx] + 15, 40)  # Always 15m above terrain
    RAW_ROUTE.append((rx, ry, alt))

# ─── Bifurcation Map (Phase 15 logic, pre-computed) ──────────────────────────
def compute_bifurcations():
    bif = set()
    for y in range(1, H-1):
        for x in range(1, W-1):
            # Integer Spread (Eastern-Western momentum difference)
            spread_x = TERRAIN[y][x+1] - TERRAIN[y][x-1]
            # Integer Spread (Northern-Southern momentum difference)
            spread_y = TERRAIN[y+1][x] - TERRAIN[y-1][x]
            if spread_x * spread_y < 0:
                bif.add((x, y))
    return bif

BIFURCATIONS = compute_bifurcations()

# ─── Shared Simulation State ──────────────────────────────────────────────────
SIM_STATE = {
    "drone": {"x": 3.0, "y": 3.0, "z": 40.0,
              "phi": 0.0, "theta": 0.0, "psi": 0.0},
    "trail": [],
    "step": 0,
    "confidence": "HIGH",
    "chaos": 2,
    "wind": {"vx": 0, "vy": 0},
    "running": True
}

# ─── Physics Loop ─────────────────────────────────────────────────────────────
async def physics_loop():
    vx, vy, vz = 0.0, 0.0, 0.0
    phi, theta = 0.0, 0.0

    while True:
        step = SIM_STATE["step"] % len(RAW_ROUTE)
        tx, ty, tz = RAW_ROUTE[step]

        dx = tx - SIM_STATE["drone"]["x"]
        dy = ty - SIM_STATE["drone"]["y"]
        dz = tz - SIM_STATE["drone"]["z"]
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)

        # Clamp to next waypoint
        if dist > 0.5:
            vx = dx / dist * 0.4
            vy = dy / dist * 0.4
            vz = dz / dist * 0.3
        else:
            SIM_STATE["step"] += 1

        # ── Wind_Navigator Insight ──────────────────────────────
        gx = int(SIM_STATE["drone"]["x"])
        gy = int(SIM_STATE["drone"]["y"])
        in_bifurcation = (gx, gy) in BIFURCATIONS
        chaos  = 35 if in_bifurcation else 2
        conf   = "LOW" if in_bifurcation else "HIGH"

        # Wind burst in bifurcation zones
        wind_x = (math.sin(SIM_STATE["step"] * 0.3) * 5) if in_bifurcation else 0
        wind_y = (math.cos(SIM_STATE["step"] * 0.2) * 5) if in_bifurcation else 0

        # ── Mechanical Skew (Motor 3 at 60%) ───────────────────
        t1, t2, t3, t4 = 1.0, 1.0, 0.6, 1.0
        roll_torque  = (t2 + t4) - (t1 + t3)   # = 0.4 permanent offset
        pitch_torque = (t1 + t2) - (t3 + t4)   # = 0.4 permanent offset

        # ── 6-DOF update ────────────────────────────────────────
        drag_x = -(vx - wind_x * 0.02) * 0.15
        drag_y = -(vy - wind_y * 0.02) * 0.15
        vx += drag_x * 0.02
        vy += drag_y * 0.02

        phi   += roll_torque  * 0.008
        theta += pitch_torque * 0.008
        # Damping
        phi   *= 0.97
        theta *= 0.97

        # ── Position update ─────────────────────────────────────
        SIM_STATE["drone"]["x"] += vx
        SIM_STATE["drone"]["y"] += vy
        SIM_STATE["drone"]["z"] += vz
        SIM_STATE["drone"]["phi"]   = phi
        SIM_STATE["drone"]["theta"] = theta
        SIM_STATE["drone"]["psi"]   += 0.005  # Slow yaw drift

        # Trail (last 80 positions)
        trail = SIM_STATE["trail"]
        trail.append([round(SIM_STATE["drone"]["x"], 2),
                      round(SIM_STATE["drone"]["z"], 2),
                      round(SIM_STATE["drone"]["y"], 2)])
        if len(trail) > 80:
            trail.pop(0)

        SIM_STATE["confidence"] = conf
        SIM_STATE["chaos"]      = chaos
        SIM_STATE["wind"]       = {"vx": round(wind_x, 1), "vy": round(wind_y, 1)}

        await asyncio.sleep(0.05)

@app.on_event("startup")
async def on_start():
    asyncio.create_task(physics_loop())

@app.get("/state")
async def state():
    return SIM_STATE

@app.get("/terrain")
async def terrain_data():
    # Return building data as list of {x,z,h} objects
    buildings = []
    for y in range(H):
        for x in range(W):
            h = TERRAIN[y][x]
            if h > 0:
                buildings.append({"x": x, "z": y, "h": h})
    return {"buildings": buildings, "bifurcations": list(BIFURCATIONS)}

@app.get("/", response_class=HTMLResponse)
async def index():
    return r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Wind_Navigator — Manhattan 3D Flight Sim</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #04060f; overflow: hidden; font-family: 'Inter', monospace; color: #cff; }
    #canvas { display: block; }

    #hud {
      position: absolute; top: 0; left: 0; width: 260px;
      background: rgba(0,10,30,0.85);
      border-right: 1px solid rgba(0,255,255,0.15);
      border-bottom: 1px solid rgba(0,255,255,0.15);
      border-radius: 0 0 12px 0;
      padding: 18px 20px; backdrop-filter: blur(10px);
    }
    #hud h2 { font-size: 1.05em; color:#0ff; letter-spacing:2px; margin-bottom:14px; text-transform:uppercase; }
    .row { display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid rgba(0,255,255,0.07); font-size:0.8em; }
    .label { color: #68a; }
    .val { font-weight: bold; color: #0ff; }
    .val.LOW  { color: #f44; animation: pulse 0.6s infinite alternate; }
    .val.HIGH { color: #4f4; }

    #legend {
      position: absolute; bottom: 20px; left: 20px;
      background: rgba(0,10,30,0.82); border-radius: 10px;
      padding: 12px 16px; font-size: 0.75em;
      border: 1px solid rgba(0,255,255,0.1);
    }
    .dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; }

    @keyframes pulse { to { opacity:0.4; } }

    #controls {
      position: absolute; bottom: 20px; right: 20px;
      background: rgba(0,10,30,0.82); border-radius:10px;
      padding: 12px 16px; font-size:0.75em;
      border: 1px solid rgba(0,255,255,0.1);
    }

    #loading {
      position: absolute; top:50%; left:50%; transform: translate(-50%,-50%);
      color:#0ff; font-size:1.3em; letter-spacing:4px;
    }
  </style>
</head>
<body>
<div id="loading">LOADING MANHATTAN...</div>
<canvas id="canvas"></canvas>

<div id="hud" style="display:none">
  <h2>⚡ Wind_Navigator</h2>
  <div class="row"><span class="label">POSITION</span><span class="val" id="pos">—</span></div>
  <div class="row"><span class="label">ALTITUDE</span><span class="val" id="alt">—</span></div>
  <div class="row"><span class="label">ROLL</span><span class="val" id="roll">—</span></div>
  <div class="row"><span class="label">PITCH</span><span class="val" id="pitch">—</span></div>
  <div class="row"><span class="label">WIND</span><span class="val" id="wind">—</span></div>
  <div class="row"><span class="label">CHAOS SCORE</span><span class="val" id="chaos">—</span></div>
  <div class="row"><span class="label">CONFIDENCE</span><span class="val" id="conf">HIGH</span></div>
  <div class="row"><span class="label">PHASE ENGINE</span><span class="val HIGH">ACTIVE</span></div>
</div>

<div id="legend" style="display:none">
  <div style="margin-bottom:6px;color:#0ff;font-weight:bold;">LEGEND</div>
  <div><span class="dot" style="background:#888"></span>Manhattan Building</div>
  <div><span class="dot" style="background:#f40"></span>Bifurcation Zone</div>
  <div><span class="dot" style="background:#0f8"></span>Drone</div>
  <div><span class="dot" style="background:#0cf"></span>Flight Trail</div>
  <div style="margin-top:6px;color:#668;font-size:0.85em;">Motor 3 @ 60% efficiency</div>
</div>

<div id="controls" style="display:none">
  <div style="color:#0ff;font-weight:bold;margin-bottom:6px;">CONTROLS</div>
  <div>🖱 Drag — Orbit camera</div>
  <div>🖱 Scroll — Zoom</div>
  <div>🖱 Right-drag — Pan</div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
const canvas = document.getElementById('canvas');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x04060f);
scene.fog = new THREE.Fog(0x04060f, 100, 380);

const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(80, 80, 120);
camera.lookAt(40, 20, 40);

// Lighting
scene.add(new THREE.AmbientLight(0x1a2040, 1.5));
const sun = new THREE.DirectionalLight(0x6080ff, 1.2);
sun.position.set(60, 120, 40);
sun.castShadow = true;
scene.add(sun);

// Ground
const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(100, 100),
  new THREE.MeshPhongMaterial({ color: 0x080c18, shininess: 10 })
);
ground.rotation.x = -Math.PI / 2;
ground.position.set(40, 0, 40);
scene.add(ground);

// Grid overlay
const grid = new THREE.GridHelper(100, 40, 0x1a2040, 0x0f1830);
grid.position.set(40, 0.1, 40);
scene.add(grid);

// ── Build Manhattan ────────────────────────────────────────────────────────
const buildingMats = [
  new THREE.MeshPhongMaterial({ color: 0x1a2a4a, shininess:30, transparent:true, opacity:0.92 }),
  new THREE.MeshPhongMaterial({ color: 0x2a1a4a, shininess:30, transparent:true, opacity:0.92 }),
  new THREE.MeshPhongMaterial({ color: 0x1a3a3a, shininess:30, transparent:true, opacity:0.92 }),
];
const bifMat = new THREE.MeshPhongMaterial({
  color: 0xff3300, transparent: true, opacity: 0.55, emissive: 0x440000
});

let bifMeshes = [];

fetch('/terrain').then(r => r.json()).then(data => {
  const geo = new THREE.BoxGeometry(1, 1, 1);
  data.buildings.forEach(b => {
    const h = Math.max(b.h / 20, 0.5);
    const m = buildingMats[Math.floor((b.x + b.z) % 3)];
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(0.92, h, 0.92), m);
    mesh.position.set(b.x, h / 2, b.z);
    mesh.castShadow = true;
    scene.add(mesh);
  });

  // Bifurcation zone markers (flat glowing pads)
  data.bifurcations.forEach(([bx, bz]) => {
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(0.95, 0.15, 0.95), bifMat
    );
    mesh.position.set(bx, 0.08, bz);
    scene.add(mesh);
    bifMeshes.push(mesh);
  });

  document.getElementById('loading').style.display = 'none';
  document.getElementById('hud').style.display = 'block';
  document.getElementById('legend').style.display = 'block';
  document.getElementById('controls').style.display = 'block';
});

// ── Drone Model ────────────────────────────────────────────────────────────
const droneGroup = new THREE.Group();

// Body
const body = new THREE.Mesh(
  new THREE.BoxGeometry(1.2, 0.25, 1.2),
  new THREE.MeshPhongMaterial({ color: 0x334455, shininess: 80 })
);
droneGroup.add(body);

// Arms
const armGeo = new THREE.BoxGeometry(2.4, 0.1, 0.15);
const armMat = new THREE.MeshPhongMaterial({ color: 0x223344 });
const arm1 = new THREE.Mesh(armGeo, armMat); droneGroup.add(arm1);
const arm2 = new THREE.Mesh(armGeo, armMat); arm2.rotation.y = Math.PI/2; droneGroup.add(arm2);

// Motors (4 rotors)
const motorColors = [0x00ffff, 0x00ffff, 0xff4400, 0x00ffff]; // Motor 3 = RED (damaged)
const motorPositions = [[1.1,0.15,1.1],[-1.1,0.15,-1.1],[1.1,0.15,-1.1],[-1.1,0.15,1.1]];
motorPositions.forEach((pos, i) => {
  const m = new THREE.Mesh(
    new THREE.CylinderGeometry(0.35, 0.35, 0.08, 16),
    new THREE.MeshPhongMaterial({ color: motorColors[i], emissive: motorColors[i], emissiveIntensity: 0.4 })
  );
  m.position.set(...pos);
  droneGroup.add(m);
});

// Drone light
const droneLight = new THREE.PointLight(0x00ffff, 2, 8);
droneGroup.add(droneLight);
scene.add(droneGroup);

// ── Trail ─────────────────────────────────────────────────────────────────
const TRAIL_MAX = 80;
const trailPositions = new Float32Array(TRAIL_MAX * 3);
const trailGeo = new THREE.BufferGeometry();
trailGeo.setAttribute('position', new THREE.BufferAttribute(trailPositions, 3));
const trailLine = new THREE.Line(
  trailGeo,
  new THREE.LineBasicMaterial({ color: 0x00ccff, transparent: true, opacity: 0.6 })
);
scene.add(trailLine);

// ── Mouse Orbit ────────────────────────────────────────────────────────────
let isDragging = false, lastX = 0, lastY = 0;
let theta2 = 0.7, phi2 = 0.5, radius = 140;
let target = new THREE.Vector3(40, 15, 40);

canvas.addEventListener('mousedown', e => { isDragging = true; lastX = e.clientX; lastY = e.clientY; });
canvas.addEventListener('mouseup',   () => { isDragging = false; });
canvas.addEventListener('mousemove', e => {
  if (!isDragging) return;
  theta2 += (e.clientX - lastX) * 0.005;
  phi2    = Math.max(0.1, Math.min(1.4, phi2 - (e.clientY - lastY) * 0.005));
  lastX = e.clientX; lastY = e.clientY;
});
canvas.addEventListener('wheel', e => { radius = Math.max(30, Math.min(300, radius + e.deltaY * 0.15)); });

// ── State Polling ──────────────────────────────────────────────────────────
let dronePos  = new THREE.Vector3(3, 40, 3);
let droneRot  = new THREE.Euler();
let currentConf = "HIGH";

async function pollState() {
  try {
    const data = await fetch('/state').then(r => r.json());
    const d = data.drone;
    dronePos.set(d.x, d.z / 5, d.y);  // z is altitude → Y in Three.js
    droneRot.set(d.theta, d.psi, d.phi);

    // Update trail
    const trail = data.trail;
    for (let i = 0; i < TRAIL_MAX; i++) {
      const pt = trail[i] || [d.x, d.z / 5, d.y];
      trailPositions[i * 3]     = pt[0];
      trailPositions[i * 3 + 1] = pt[1] / 5;
      trailPositions[i * 3 + 2] = pt[2];
    }
    trailGeo.setDrawRange(0, trail.length);
    trailGeo.attributes.position.needsUpdate = true;

    // HUD
    document.getElementById('pos').textContent   = `${d.x.toFixed(1)}, ${d.y.toFixed(1)}`;
    document.getElementById('alt').textContent   = `${(d.z).toFixed(0)} m`;
    document.getElementById('roll').textContent  = `${(d.phi  * 180/Math.PI).toFixed(1)}°`;
    document.getElementById('pitch').textContent = `${(d.theta * 180/Math.PI).toFixed(1)}°`;
    document.getElementById('wind').textContent  = `${data.wind.vx}/${data.wind.vy} fps`;
    document.getElementById('chaos').textContent = data.chaos;
    const confEl = document.getElementById('conf');
    confEl.textContent = data.confidence;
    confEl.className = 'val ' + data.confidence;
    currentConf = data.confidence;
  } catch(e) {}
}

setInterval(pollState, 60);

// ── Animate ────────────────────────────────────────────────────────────────
const clock = new THREE.Clock();
function animate() {
  requestAnimationFrame(animate);
  const t = clock.getElapsedTime();

  // Interpolate drone position smoothly
  droneGroup.position.lerp(dronePos, 0.12);
  droneGroup.rotation.set(droneRot.x, droneRot.y, droneRot.z);

  // Propeller spin illusion (scale flicker)
  droneGroup.children.slice(3).forEach((m, i) => {
    m.scale.y = 1 + Math.sin(t * 40 + i) * 0.05;
  });

  // Bifurcation zone pulse
  bifMeshes.forEach((m, i) => {
    m.material.opacity = 0.3 + 0.3 * Math.sin(t * 3 + i * 0.5);
  });

  // Drone light color based on confidence
  droneLight.color.setHex(currentConf === "LOW" ? 0xff2200 : 0x00ffff);
  droneLight.intensity = 2 + Math.sin(t * 6) * 0.5;

  // Camera orbit
  camera.position.x = target.x + radius * Math.sin(theta2) * Math.cos(phi2);
  camera.position.y = target.y + radius * Math.sin(phi2);
  camera.position.z = target.z + radius * Math.cos(theta2) * Math.cos(phi2);

  // Camera gently tracks drone
  target.lerp(droneGroup.position, 0.01);
  camera.lookAt(droneGroup.position);

  renderer.render(scene, camera);
}
animate();

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});
</script>
</body>
</html>
    """
