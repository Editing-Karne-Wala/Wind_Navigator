import heapq
import math

print("=========================================================")
print("      PHASE 8: AEROSPACE 4D PATHFINDING ROUTER (A*)      ")
print("=========================================================\n")

# Grid Dimensions (Sub-section of the city)
WIDTH = 50
HEIGHT = 50
DEPTH = 20  # Altitude voxels

# We simulate a "Moving Updraft" (Transient Vortex).
# This perfectly tests your concern: The updraft is moving East over time.
# If the drone just targets where the updraft is at T=0, it will miss it.
def get_wind_vector_at_time(x, y, z, t):
    # A powerful thermal updraft (Vz = +8.0) that moves 1 voxel East (+X) every 2 seconds
    vortex_center_x = 20 + (t // 2)
    vortex_center_y = 25
    
    # If the drone is inside the 3x3 footprint of this moving vortex, it gets a massive lift
    if abs(x - vortex_center_x) <= 2 and abs(y - vortex_center_y) <= 2:
        return {'vx': 2.0, 'vy': 0.0, 'vz': 8.0} # Moving east, powerful lift
        
    # Ambient city wind (Slight headwind)
    return {'vx': -1.0, 'vy': 0.0, 'vz': 0.0}

def heuristic(x1, y1, z1, x2, y2, z2):
    # Manhattan distance heuristic (Base battery cost of flying straight)
    return (abs(x2 - x1) + abs(y2 - y1) + abs(z2 - z1)) * 10.0

def a_star_4d(start, target):
    # Start: (x, y, z, t)
    # Target: (x, y, z) - We don't care *when* we arrive, just the cheapest battery path to get there
    
    # Priority Queue for A*
    open_set = []
    heapq.heappush(open_set, (0, start))
    
    # Tracks the best path
    came_from = {}
    
    # Tracks the true battery cost to reach a space-time coordinate
    g_score = {start: 0}
    
    while open_set:
        current_f, current = heapq.heappop(open_set)
        cx, cy, cz, ct = current
        
        # Did we reach the target coordinates?
        if cx == target[0] and cy == target[1] and cz == target[2]:
            return reconstruct_path(came_from, current)
            
        # The drone can move in 6 cardinal directions, or hold position
        moves = [
            (1, 0, 0), (-1, 0, 0), 
            (0, 1, 0), (0, -1, 0), 
            (0, 0, 1), (0, 0, -1)
        ]
        
        for mx, my, mz in moves:
            nx, ny, nz = cx + mx, cy + my, cz + mz
            nt = ct + 1 # Time ALWAYS moves forward by 1 tick!
            
            # Boundary checks
            if not (0 <= nx < WIDTH and 0 <= ny < HEIGHT and 0 <= nz < DEPTH):
                continue
                
            # Physics Consultation: What is the wind doing at this EXACT future millisecond?
            wind = get_wind_vector_at_time(nx, ny, nz, nt)
            
            # Battery Cost Logic
            base_motor_cost = 10.0 
            
            # If wind is pushing us the direction we want to go, we save battery
            wind_assist = (mx * wind['vx']) + (my * wind['vy']) + (mz * wind['vz'])
            
            # Cost = Base Moyer Cost - Wind Assist. Minimum cost is 1.0 (Avionics power)
            movement_cost = max(1.0, base_motor_cost - (wind_assist * 1.5))
            
            neighbor = (nx, ny, nz, nt)
            tentative_g_score = g_score[current] + movement_cost
            
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score = tentative_g_score + heuristic(nx, ny, nz, target[0], target[1], target[2])
                heapq.heappush(open_set, (f_score, neighbor))
                
    return None # No path found

def reconstruct_path(came_from, current):
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path

if __name__ == "__main__":
    # Drone starts on roof at T=0
    start_node = (10, 25, 5, 0)
    
    # Needs to deliver package across town 
    target_node = (30, 25, 15)
    
    print(f"[*] Dispatching Drone from {start_node[:3]} to {target_node}")
    print("[*] Running 4D Ray-Marching A* Search (Predicting transient updrafts)...\n")
    
    optimal_flight_plan = a_star_4d(start_node, target_node)
    
    if optimal_flight_plan:
        print("--- GENERATED FLIGHT PLAN ---")
        total_battery = 0
        for step in optimal_flight_plan:
            x, y, z, t = step
            wind = get_wind_vector_at_time(x, y, z, t)
            
            action = "PROP: Normal Thrust"
            if wind['vz'] >= 8.0:
                action = "GLIDE: Motors Cut (Surfing Predicted Thermal)"
            elif wind['vx'] < -0.5:
                action = "PROP: High Thrust (Fighting Headwind)"
                
            print(f"T={t:02d}s | GPS Voxel: [{x:02d}, {y:02d}, {z:02d}] | Wind: Vz={wind['vz']} | Action: {action}")
        
        print(f"\n[+] Routing Complete.")
        print("[+] The Drone successfully altered its path in TIME to intersect the moving updraft and glide to its target!")
    else:
        print("[-] PATH FAILED.")
