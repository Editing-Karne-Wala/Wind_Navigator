import heapq
import math
import time
from datetime import datetime

print("=========================================================")
print("      PHASE 8: AEROSPACE 4D PATHFINDING ROUTER (A*)      ")
print("=========================================================\n")

# Grid Dimensions 
WIDTH = 50
HEIGHT = 50
DEPTH = 20  

def get_wind_vector_at_time(x, y, z, unix_timestamp):
    # We map the physical vortex to absolute Universal Time (UNIX Epoch).
    # Using modulo 100 ensures the vortex cycles exactly predictably every 100 seconds
    # relative to the global atomic clock, regardless of when the drone takes off.
    cycle_time = int(unix_timestamp) % 100
    vortex_center_x = 15 + (cycle_time // 2)
    vortex_center_y = 25
    
    if abs(x - vortex_center_x) <= 2 and abs(y - vortex_center_y) <= 2:
        return {'vx': 2.0, 'vy': 0.0, 'vz': 8.0} 
        
    return {'vx': -1.0, 'vy': 0.0, 'vz': 0.0}

def heuristic(x1, y1, z1, x2, y2, z2):
    return (abs(x2 - x1) + abs(y2 - y1) + abs(z2 - z1)) * 10.0

def a_star_4d(start, target):
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}
    
    while open_set:
        current_f, current = heapq.heappop(open_set)
        cx, cy, cz, ct_unix = current
        
        if cx == target[0] and cy == target[1] and cz == target[2]:
            return reconstruct_path(came_from, current)
            
        moves = [
            (1, 0, 0), (-1, 0, 0), 
            (0, 1, 0), (0, -1, 0), 
            (0, 0, 1), (0, 0, -1)
        ]
        
        for mx, my, mz in moves:
            nx, ny, nz = cx + mx, cy + my, cz + mz
            # Time strictly advances by 1 absolute second (1000ms) for 1 voxel of physical drone movement
            nt_unix = ct_unix + 1.0 
            
            if not (0 <= nx < WIDTH and 0 <= ny < HEIGHT and 0 <= nz < DEPTH):
                continue
                
            wind = get_wind_vector_at_time(nx, ny, nz, nt_unix)
            
            base_motor_cost = 10.0 
            wind_assist = (mx * wind['vx']) + (my * wind['vy']) + (mz * wind['vz'])
            movement_cost = max(1.0, base_motor_cost - (wind_assist * 1.5))
            
            neighbor = (nx, ny, nz, nt_unix)
            tentative_g_score = g_score[current] + movement_cost
            
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score = tentative_g_score + heuristic(nx, ny, nz, target[0], target[1], target[2])
                heapq.heappush(open_set, (f_score, neighbor))
                
    return None 

def reconstruct_path(came_from, current):
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path

if __name__ == "__main__":
    # Query universal absolute time via hardware/NTP (Usually how GPS satellites sync)
    current_unix_time = time.time()
    
    # Start: X=10, Y=25, Z=5, T=1712xxxxxxx.xx
    start_node = (10, 25, 5, current_unix_time)
    target_node = (30, 25, 15)
    
    print(f"[*] Fetching absolute atomic GPS Time: UNIX {current_unix_time:.2f}")
    print(f"[*] Dispatching Drone from {start_node[:3]} to {target_node}")
    print("[*] Running 4D UNIX-Synchronized A* Search...\n")
    
    optimal_flight_plan = a_star_4d(start_node, target_node)
    
    if optimal_flight_plan:
        print("--- GENERATED ABSOLUTE FLIGHT PLAN ---")
        for step in optimal_flight_plan:
            x, y, z, t_unix = step
            wind = get_wind_vector_at_time(x, y, z, t_unix)
            
            # Format to human-readable ISO-8601 UTC timestamp 
            human_time = datetime.fromtimestamp(t_unix).strftime('%H:%M:%S UTC')
            
            action = "PROP: Normal Thrust"
            if wind['vz'] >= 8.0:
                action = "GLIDE: Motors Cut (Surfing Thermal)"
            elif wind['vx'] < -0.5:
                action = "PROP: High Thrust (Fighting Headwind)"
                
            print(f"Time: {human_time} | Voxel: [{x:02d}, {y:02d}, {z:02d}] | Wind: Vz={wind['vz']} | Action: {action}")
        
    else:
        print("[-] PATH FAILED.")
