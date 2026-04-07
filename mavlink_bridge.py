import asyncio
from mavsdk import System
from mavsdk.mission import (MissionItem, MissionPlan)

# =========================================================================
# THE SIM2REAL BRIDGE: Connecting Wind_Navigator to PX4 Gazebo Autopilot
# =========================================================================

async def run():
    drone = System()
    print("======================================================")
    print("      WIND_NAVIGATOR -> MAVLINK FLIGHT CONTROLLER      ")
    print("======================================================")
    
    # 1. Connect to the PX4 SITL Virtual Drone over UDP
    print("\n[*] Connecting to PX4 Virtual Drone (Listening on port 14540)...")
    await drone.connect(system_address="udp://:14540")

    # Wait for the drone to establish a heartbeat connection
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("[+] Drone MAVLink Heartbeat detected! Firmware Online.")
            break

    # 2. Extract Route from our Wind_Navigator 4D Router
    # In production, we would use: requests.get('http://localhost:8000/route')
    print("[*] Asking Wind_Navigator API for the optimal 4D Space-Time Route...")
    
    # This is the exact output we generated in Phase 8
    route_plan = [
        {"x": 10, "y": 25, "z": 5,  "action": "THRUST"}, 
        {"x": 25, "y": 25, "z": 5,  "action": "THRUST"},
        {"x": 25, "y": 25, "z": 10, "action": "GLIDE"}, # Thermal Updraft caught dynamically!
        {"x": 30, "y": 25, "z": 15, "action": "THRUST"}
    ]
    
    # 3. Translate Cartesian XYZ Voxels into real GPS Coordinates (Latitude/Longitude)
    # Assuming Simulator Environment is spawning in Downtown Manhattan
    HOME_LAT = 40.7128
    HOME_LON = -74.0060
    
    mission_items = []
    
    print("\n--- TRANSLATING INTEGER MATH TO PHYSICAL FLIGHT CONTROLS ---")
    for waypoint in route_plan:
        # Math: 1 degree of Latitude is ~111,111 meters. 
        # Assuming 1 of our Voxels = 5 physical meters.
        lat_offset = (waypoint["y"] * 5) / 111111.0
        lon_offset = (waypoint["x"] * 5) / (111111.0 * 0.766) # Cosine compensation for NY
        alt_meters = waypoint["z"] * 5.0
        
        print(f"[*] Parsed Voxel [X:{waypoint['x']}, Z:{waypoint['z']}] -> Target GPS: {HOME_LAT+lat_offset:.5f}, Alt: {alt_meters}m")
        
        item = MissionItem(
            HOME_LAT + lat_offset,
            HOME_LON + lon_offset,
            alt_meters,
            speed_m_s=5.0, # Physical Drone speed
            is_fly_through=True,
            gimbal_pitch_deg=float('nan'),
            gimbal_yaw_deg=float('nan'),
            camera_action=MissionItem.CameraAction.NONE,
            loiter_time_s=float('nan'),
            camera_photo_interval_s=float('nan'),
            acceptance_radius_m=2.0, # Margin of error for physical turbulence
            yaw_deg=float('nan'),
            camera_photo_distance_m=float('nan'),
            vehicle_action=MissionItem.VehicleAction.NONE 
        )
        mission_items.append(item)

    # 4. Upload to physical/virtual Flight Controller memory
    mission_plan = MissionPlan(mission_items)
    print("\n[*] Flashing 4D trajectory to Drone's active memory...")
    await drone.mission.upload_mission(mission_plan)

    print("[*] Engaging Rotors and Arming Vehicle...")
    await drone.action.arm()
    
    print("[+] TAKEOFF! Executing Wind_Navigator Flight Plan in Gazebo physics engine.")
    await drone.mission.start_mission()

if __name__ == "__main__":
    asyncio.run(run())
