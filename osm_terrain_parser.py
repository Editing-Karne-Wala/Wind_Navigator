import urllib.request
import urllib.parse
import json
import math

# Bounding box for a slice of Manhattan (Midtown near Bryant Park)
LAT_MIN = 40.752
LON_MIN = -73.985
LAT_MAX = 40.756
LON_MAX = -73.980

# Target Grid Size for our Physics Engine
# This establishes the resolution of our voxels (e.g., 100x100 grid over this area)
GRID_WIDTH = 80
GRID_DEPTH = 80 # Represents the Y-axis on a traditional map

def build_overpass_query():
    # The Overpass API query fetches building footprints (polygons) and their metadata
    query = f"""
    [out:json][timeout:25];
    (
      way["building"]({LAT_MIN},{LON_MIN},{LAT_MAX},{LON_MAX});
      relation["building"]({LAT_MIN},{LON_MIN},{LAT_MAX},{LON_MAX});
    );
    out geom;
    """
    return query

def fetch_osm_data(query):
    print("[OSM] Querying OpenStreetMap Overpass API for real-world geometry...")
    url = "http://overpass-api.de/api/interpreter"
    data = {"data": query}
    data_encoded = urllib.parse.urlencode(data).encode('utf-8')
    req = urllib.request.Request(url, data=data_encoded, headers={'User-Agent': 'WindNavigator-SITL/1.0 (contact@opensource.org)'})
    
    # We use basic urllib to avoid requiring external pip installs like 'requests'
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

# Standard Point-in-Polygon Ray Casting algorithm to check if a grid voxel is inside a building
def point_in_polygon(x, y, poly):
    n = len(poly)
    inside = False
    p1x, p1y = poly[0]
    for i in range(n + 1):
        p2x, p2y = poly[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def process_buildings(osm_data):
    buildings = []
    elements = osm_data.get('elements', [])
    print(f"[OSM] Found {len(elements)} structural elements in the bounding box.")
    
    for element in elements:
        tags = element.get('tags', {})
        
        # Estimate height in meters
        height_m = 10.0 # Default if unknown
        if 'height' in tags:
            try:
                # Clean up strings like "30.5", "40m"
                h_str = tags['height'].replace('m', '').replace(' ', '')
                height_m = float(h_str)
            except:
                pass
        elif 'building:levels' in tags:
            try:
                # Estimate 3.5 meters per story
                height_m = float(tags['building:levels']) * 3.5 
            except:
                pass
                
        # We process 'way' elements (which are distinct closed polygons)
        if element['type'] == 'way':
            geometry = element.get('geometry', [])
            if len(geometry) > 2:
                poly = [(pt['lon'], pt['lat']) for pt in geometry]
                buildings.append({'poly': poly, 'height': height_m})
            
    return buildings

def rasterize_terrain(buildings):
    print(f"[OSM] Rasterizing {len(buildings)} building polygons into a {GRID_WIDTH}x{GRID_DEPTH} Voxel Mask...")
    
    # Initialize a flat 2D grid containing the maximum height at that coordinate
    terrain_grid = [[0.0 for _ in range(GRID_WIDTH)] for _ in range(GRID_DEPTH)]
    
    lon_range = LON_MAX - LON_MIN
    lat_range = LAT_MAX - LAT_MIN
    
    # Sweep the area
    for y in range(GRID_DEPTH):
        current_lat = LAT_MIN + (y / float(GRID_DEPTH - 1)) * lat_range
        for x in range(GRID_WIDTH):
            current_lon = LON_MIN + (x / float(GRID_WIDTH - 1)) * lon_range
            
            # Check if this grid coordinate falls inside any building's footprint
            max_h = 0.0
            for b in buildings:
                if point_in_polygon(current_lon, current_lat, b['poly']):
                    max_h = max(max_h, b['height'])
            
            terrain_grid[y][x] = max_h
            
    return terrain_grid

def preview_ascii(grid):
    print("\n[OSM] TERRAIN PREVIEW (Top-Down ASCII Map):\n")
    # We print backwards so North is Up
    for row in reversed(grid):
        line = ""
        for h in row:
            if h == 0:
                line += ". "    # Street / Empty Space
            elif h < 15:
                line += "o "    # Low building (< 4 stories)
            elif h < 45:
                line += "X "    # Medium building
            elif h < 100:
                line += "# "    # Tall building
            else:
                line += "M "    # Skyscraper / Massive block
        print(line)
    print("\nLegend: [.] Street  [o] Low  [X] Mid  [#] High  [M] Skyscraper\n")

def save_voxel_mask(grid, filename="urban_terrain.txt"):
    print(f"[OSM] Exporting Voxel Engine Mask to {filename}...")
    with open(filename, 'w') as f:
        # Header for the C++ engine to parse sizes
        f.write(f"{GRID_WIDTH} {GRID_DEPTH}\n")
        for row in grid:
            # We output integer heights for the exact discrete integer math
            line = " ".join([str(int(h)) for h in row])
            f.write(line + "\n")
    print("[OSM] Export complete. Ready for integration.")

if __name__ == "__main__":
    query = build_overpass_query()
    data = fetch_osm_data(query)
    buildings = process_buildings(data)
    grid = rasterize_terrain(buildings)
    preview_ascii(grid)
    save_voxel_mask(grid)
