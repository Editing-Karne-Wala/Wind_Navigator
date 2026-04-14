# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR -- Phase 30: 3D A* Pathfinding + O(1) Spatial Hashing
========================================================================
We solve two critical scaling blockers (E1, E2):

1. Spatial Partitioning: Replaces the O(N^2) brute-force swarm collision 
   check with a Spatial Hash Grid, achieving O(1) neighborhood lookups.
2. 3D A* Routing: Upgrades the 2D router to navigate the Z-axis, forcing
   drones to climb over structural obstacles (like the OSM Skyscrapers)
   instead of getting stuck or ignoring height parameters.
"""

import math, time, random, heapq

# =======================================================================
# 1. SPATIAL HASH GRID (O(1) Collision Avoidance) -> Fixes Gap E1
# =======================================================================

class SpatialHash:
    def __init__(self, cell_size):
        self.cell_size = cell_size
        self.grid = {}

    def _hash(self, x, y):
        # Convert continuous coordinates to discrete hash cells
        return (int(x // self.cell_size), int(y // self.cell_size))

    def insert(self, drone_id, x, y):
        h = self._hash(x, y)
        if h not in self.grid:
            self.grid[h] = set()
        self.grid[h].add(drone_id)

    def get_nearby(self, x, y):
        """Returns all drone IDs in the same cell and immediately adjacent 8 cells."""
        hx, hy = self._hash(x, y)
        nearby = set()
        # O(1) lookup in exactly 9 hash buckets, regardless of swarm size N
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                h = (hx + dx, hy + dy)
                if h in self.grid:
                    nearby.update(self.grid[h])
        return nearby

def benchmark_collisions(N=2000):
    print("= Benchmarking Swarm Collision Avoidance (N={}) =".format(N))
    # Generate N random drone positions in a 1000x1000 city
    drones = [(i, random.uniform(0, 1000), random.uniform(0, 1000)) for i in range(N)]
    collision_radius = 5.0
    
    # ---------------------------------------------
    # Method A: Brute Force O(N^2) (The old way)
    # ---------------------------------------------
    t0 = time.time()
    brute_collisions = 0
    for i, x1, y1 in drones:
        for j, x2, y2 in drones:
            if i >= j: continue # Avoid double check
            dist_sq = (x1-x2)**2 + (y1-y2)**2
            if dist_sq < collision_radius**2:
                brute_collisions += 1
    t_brute = time.time() - t0
    print(f"  [O(N²)] Brute Force Time: {round(t_brute * 1000, 2)} ms")

    # ---------------------------------------------
    # Method B: Spatial Hash Array O(1) (The new way)
    # ---------------------------------------------
    t0 = time.time()
    hash_collisions = 0
    shash = SpatialHash(cell_size=10.0) # Cell slightly larger than collision radius
    
    # O(N) Insertion
    for i, x, y in drones:
        shash.insert(i, x, y)
        
    # O(N) lookup
    for i, x1, y1 in drones:
        # We ONLY check drones returned by the hash bucket
        candidates = shash.get_nearby(x1, y1)
        for j in candidates:
            if i >= j: continue
            # Actual physics object coordinates (pretending we lookup drone j's pos)
            x2, y2 = drones[j][1], drones[j][2]
            dist_sq = (x1-x2)**2 + (y1-y2)**2
            if dist_sq < collision_radius**2:
                hash_collisions += 1
                
    t_hash = time.time() - t0
    print(f"  [O(1)]  Hash Grid Time:   {round(t_hash * 1000, 2)} ms")
    print(f"  -> Speedup Factor: {round(t_brute / t_hash, 1)}x Faster!")
    assert brute_collisions == hash_collisions, "Collision Mismatch!"


# =======================================================================
# 2. 3D A* ROUTER WITH HEIGHT CLEARANCE -> Fixes Gap E2
# =======================================================================

def a_star_3d(start, target, terrain_grid):
    """
    start & target are (X, Y, Z). 
    terrain_grid is a 2D array representing building height (Z) at (X, Y).
    """
    W = len(terrain_grid[0])
    H = len(terrain_grid)
    
    # Priority Queue for A* exploration: (f_score, (x, y, z))
    open_set = []
    heapq.heappush(open_set, (0, start))
    
    came_from = {}
    g_score = {start: 0}
    
    # 3D Manhattan Heuristic
    def heuristic(a, b):
        return abs(a[0]-b[0]) + abs(a[1]-b[1]) + abs(a[2]-b[2])

    # 3D Orthogonal + Vertical Movement
    # We can go N, S, E, W keeping Z flat, OR go perfectly vertical (Up/Down)
    directions = [
        (1,0,0), (-1,0,0), (0,1,0), (0,-1,0),  # Horizontal
        (0,0,1), (0,0,-1)                      # Vertical
    ]

    while open_set:
        _, current = heapq.heappop(open_set)
        
        if current == target:
            # Reconstruct Path
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.reverse()
            return path
            
        cx, cy, cz = current
        
        for dx, dy, dz in directions:
            nx, ny, nz = cx + dx, cy + dy, cz + dz
            
            # Map boundaries
            if not (0 <= nx < W and 0 <= ny < H):
                continue
            
            # Flight Ceiling limits
            if not (0 <= nz <= 100):
                continue
                
            # THE HARD OBSTACLE CHECK: You cannot be inside/below a building!
            # If our Z is less than or equal to the building height at this xy, it's a crash.
            if nz <= terrain_grid[ny][nx]:
                continue
                
            # Movement cost: Altitude changes cost more battery
            move_cost = 1.0
            if dz > 0: move_cost = 3.0  # Vertical climb penalty (fights gravity)
            if dz < 0: move_cost = 0.5  # Vertical descent (surfing gravity)
            
            tentative_g = g_score[current] + move_cost
            neighbor = (nx, ny, nz)
            
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + heuristic(neighbor, target)
                heapq.heappush(open_set, (f_score, neighbor))
                
    return None # No path found

def test_3d_routing():
    print("\n= Testing 3D A* Route Over Skyscraper =")
    terrain = [[0 for _ in range(10)] for _ in range(10)]
    
    # Drop a massive, impassable wall blocking the entire Middle section (Height: 30)
    for y in range(10):
        for x in range(4, 7):
            terrain[y][x] = 30
            
    # From West to East, matching starting altitude of 10.
    start = (1, 5, 10)
    target = (8, 5, 10)
    
    t0 = time.time()
    path = a_star_3d(start, target, terrain)
    t1 = time.time()
    
    print(f"Path calculated in {round((t1-t0)*1000, 2)} ms.")
    
    min_z = min(p[2] for p in path)
    max_z = max(p[2] for p in path)
    print(f"Mission Vertical Envelope: Min Altitude {min_z}, Max Altitude {max_z}")
    
    # Did we successfully climb over the wall (Height 30)?
    if max_z > 30:
        print("[SUCCESS] The drone recognized the 3D barrier and scaled the height axis to clear the roof.")
    else:
        print("[FAIL] The drone crashed into the wall or failed to route.")

if __name__ == "__main__":
    benchmark_collisions(N=2000)
    test_3d_routing()
