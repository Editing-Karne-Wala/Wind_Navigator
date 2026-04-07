from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import uvicorn
import math

app = FastAPI(title="Wind_Navigator Edge API")

class DroneRequest(BaseModel):
    drone_id: str
    lat: float
    lon: float
    altitude_meters: float

# Bounding Box Extents (From osm_terrain_parser.py)
LAT_MIN = 40.752
LON_MIN = -73.985
LAT_MAX = 40.756
LON_MAX = -73.980

GRID_WIDTH = 80
GRID_DEPTH = 80  # Y-axis
Z_MAX = 30 # Voxels

def map_gps_to_voxel(lat, lon, alt_m):
    # Map raw GPS coordinates to the C++ grid matrices
    if not (LAT_MIN <= lat <= LAT_MAX) or not (LON_MIN <= lon <= LON_MAX):
        return -1, -1, -1 # Out of bounding limits
        
    y_ratio = (lat - LAT_MIN) / (LAT_MAX - LAT_MIN)
    x_ratio = (lon - LON_MIN) / (LON_MAX - LON_MIN)
    
    voxel_y = int(y_ratio * (GRID_DEPTH - 1))
    voxel_x = int(x_ratio * (GRID_WIDTH - 1))
    
    # Z coordinate transformation (1 Voxel = 5 meters of vertical height)
    voxel_z = int(alt_m / 5.0)
    
    return voxel_x, voxel_y, voxel_z

@app.post("/route")
async def get_wind_vector(req: DroneRequest):
    x, y, z = map_gps_to_voxel(req.lat, req.lon, req.altitude_meters)
    
    if x < 0:
        raise HTTPException(status_code=400, detail="GPS Coordinates out of Manhattan Simulation Bounds")
        
    # Execute the purely Integer C++ Core dynamically
    try:
        process = subprocess.Popen(
            [r"api_physics_core.exe", str(x), str(y), str(z)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        
        # Parse the C++ outputs for macroscopic aerodynamic metrics
        for line in stdout.split('\n'):
            if line.startswith("VECTOR_RESULT:"):
                payload = line.replace("VECTOR_RESULT:", "").strip()
                
                # Check 1: Did the drone fly into a brick wall?
                if "DRONE COLLISION" in payload:
                    return {"drone_id": req.drone_id, "status": "CRITICAL", "warning": "Drone is attempting to fly inside a solid OSM building structure. Hard structural intercept detected."}
                if "OUT OF BOUNDS" in payload:
                    return {"drone_id": req.drone_id, "status": "ERROR", "warning": "Voxel calculation out of physical grid boundaries."}
                    
                # Check 2: Safe flight, extract ambient wind vectors
                vectors = payload.split(",")
                return {
                    "drone_id": req.drone_id,
                    "status": "SAFE",
                    "wind_vector": {
                        "vx": float(vectors[0]),
                        "vy": float(vectors[1]),
                        "vz": float(vectors[2])
                    },
                    "action": "Adjust target trajectory using provided XYZ wind shear to maximize battery conservation."
                }
                
        raise HTTPException(status_code=500, detail="Physics Engine failed to safely deduce aerodynamic vectors.")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("🚀 Booting Wind_Navigator Edge-API Server on Port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
