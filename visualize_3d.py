from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import asyncio
import json

# IMPORT OUR RATIONAL PHYSICS (Simplified for real-time visualization)
# We use the Phase 17 logic to drive the 3D model.

app = FastAPI()

# SHARED STATE
drone_state = {
    "x": 0, "y": 0, "z": 100,
    "phi": 0, "theta": 0, "psi": 0,
    "chaos": 0, "confidence": "HIGH",
    "status": "FLIGHT_READY"
}

async def physics_loop():
    """Background loop running the Rational 6-DOF Matrix"""
    global drone_state
    
    # Init 6-DOF properties
    x, y, z = 0.0, 0.0, 10.0
    vx, vy, vz = 15.0, 0.0, 0.0 # 15ft/s forward
    phi, theta, psi = 0.0, 0.0, 0.0
    p, q, r = 0.0, 0.0, 0.0
    dt = 0.02
    
    while True:
        # 1. BIFURCATION TRIGGER (at 15ft)
        wind_vx, wind_vy = 0, 0
        chaos = 2
        confidence = "HIGH"
        
        if x > 15:
            wind_vx, wind_vy = 8, 8 # Strike!
            chaos = 45
            confidence = "LOW"
            
        # 2. MECHANICAL SKEW (Motor 3 at 30% power)
        motor_efficiency = 0.3
        t1, t2, t3, t4 = 1.0, 1.0, motor_efficiency, 1.0
        
        # Torques
        roll_torque = (t2 + t4) - (t1 + t3)
        pitch_torque = (t1 + t2) - (t3 + t4)
        
        # 3. DRAG + LIFT
        drag_x = -(vx - wind_vx) * 0.5
        drag_y = -(vy - wind_vy) * 0.5
        lift = (t1 + t2 + t3 + t4) * 0.5 # Total lift relative to weight
        
        # 4. EULER INTEGRATION (6-DOF)
        ax, ay, az = drag_x, drag_y, (lift - 1.0) * 32.2
        vx += ax * dt
        vy += ay * dt
        vz += az * dt
        
        # Rotational physics (Inertia mocked as 0.2)
        p += (roll_torque * dt) / 0.1
        q += (pitch_torque * dt) / 0.1
        
        phi   += p * dt
        theta += q * dt
        
        x += vx * dt
        y += vy * dt
        z += vz * dt
        
        # Limit the 'fall' for visual loop
        if z < 0:
            z = 0
            if confidence == "LOW":
                drone_state["status"] = "CRASHED"
            await asyncio.sleep(2) # Show the crash site, then reset
            x, y, z = 0, 0, 10
            vx, vy, vz = 15, 0, 0
            phi, theta, psi = 0, 0, 0
            p, q, r = 0, 0, 0
            drone_state["status"] = "FLIGHT_READY"
        
        # Sync to Global State for Website
        drone_state.update({
            "x": x, "y": y, "z": z,
            "phi": phi, "theta": theta, "psi": psi,
            "chaos": chaos, "confidence": confidence
        })
        
        await asyncio.sleep(dt)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(physics_loop())

@app.get("/telemetry")
async def telemetry():
    return drone_state

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Wind_Navigator 3D</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <style>
        body { margin: 0; background: #050505; color: white; font-family: 'Inter', sans-serif; overflow: hidden; }
        #overlay { position: absolute; top: 20px; left: 20px; text-shadow: 0 0 10px rgba(0,255,255,0.5); }
        .stat { margin-bottom: 10px; font-size: 1.2em; }
        .val { color: #0ff; font-weight: bold; }
        .LOW { color: #f22; }
        .HIGH { color: #2f2; }
    </style>
</head>
<body>
    <div id="overlay">
        <div class="stat">POSITION: <span id="pos" class="val">0, 0, 0</span></div>
        <div class="stat">CHAOS SCORE: <span id="chaos" class="val">0</span></div>
        <div class="stat">CONFIDENCE: <span id="conf" class="val">HIGH</span></div>
        <div class="stat">STATUS: <span id="status" class="val">FLIGHT_READY</span></div>
    </div>
    <script>
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        document.body.appendChild(renderer.domElement);

        // Ground Grid
        const grid = new THREE.GridHelper(200, 20, 0x444444, 0x222222);
        scene.add(grid);

        // The Drone Model (Group)
        const drone = new THREE.Group();
        const body = new THREE.Mesh(new THREE.BoxGeometry(1, 0.2, 1), new THREE.MeshPhongMaterial({ color: 0x555555 }));
        drone.add(body);
        
        // Motors
        const motorGeo = new THREE.CylinderGeometry(0.5, 0.5, 0.1, 16);
        const m1 = new THREE.Mesh(motorGeo, new THREE.MeshPhongMaterial({ color: 0x00ffff })); m1.position.set(0.5, 0.1, 0.5); drone.add(m1);
        const m2 = new THREE.Mesh(motorGeo, new THREE.MeshPhongMaterial({ color: 0x00ffff })); m2.position.set(-0.5, 0.1, 0.5); drone.add(m2);
        const m3 = new THREE.Mesh(motorGeo, new THREE.MeshPhongMaterial({ color: 0xff0000 })); m3.position.set(0.5, 0.1, -0.5); drone.add(m3); // Skeptical motor
        const m4 = new THREE.Mesh(motorGeo, new THREE.MeshPhongMaterial({ color: 0x00ffff })); m4.position.set(-0.5, 0.1, -0.5); drone.add(m4);
        
        scene.add(drone);

        // Lighting
        const light = new THREE.DirectionalLight(0xffffff, 1);
        light.position.set(10, 20, 10);
        scene.add(light);
        scene.add(new THREE.AmbientLight(0x404040));

        camera.position.set(10, 15, 20);
        camera.lookAt(0, 0, 0);

        async function update() {
            const res = await fetch('/telemetry');
            const data = await res.json();
            
            // Sync 3D Position
            drone.position.set(data.x, data.z, -data.y); // Three.js Y is up
            
            // Sync Rotation (Radians)
            drone.rotation.set(data.theta, data.psi, data.phi);
            
            // Camera follow
            camera.position.x = data.x + 10;
            camera.position.y = data.z + 10;
            camera.lookAt(data.x, data.z, -data.y);

            // Update HUD
            document.getElementById('pos').innerText = `${Math.round(data.x)}, ${Math.round(data.y)}, ${Math.round(data.z)}`;
            document.getElementById('pos').className = 'val ' + data.confidence;
            document.getElementById('chaos').innerText = data.chaos;
            document.getElementById('conf').innerText = data.confidence;
            document.getElementById('conf').className = 'val ' + data.confidence;
            document.getElementById('status').innerText = data.status;
            document.getElementById('status').className = 'val ' + (data.status === 'CRASHED' ? 'LOW' : 'HIGH');
        }

        function animate() {
            requestAnimationFrame(animate);
            renderer.render(scene, camera);
        }
        
        setInterval(update, 20);
        animate();
    </script>
</body>
</html>
    """
