import json
import time
import urllib.request
import urllib.parse
from osm_terrain_parser import build_overpass_query, process_buildings, rasterize_terrain

def get_navi():
    from sitl_flight_analyzer import run_sitl_analysis
    with open("real_case_study.json", "r") as f:
        log_data = json.load(f)
    trace_lats = [t['lat'] for t in log_data['flight_trace']]
    trace_lons = [t['lon'] for t in log_data['flight_trace']]
    lat_min, lat_max = min(trace_lats) - 0.002, max(trace_lats) + 0.002
    lon_min, lon_max = min(trace_lons) - 0.002, max(trace_lons) + 0.002
    
    query = build_overpass_query(lat_min, lon_min, lat_max, lon_max)
    data = {"data": query}
    data_encoded = urllib.parse.urlencode(data).encode('utf-8')
    
    endpoints = ["https://lz4.overpass-api.de/api/interpreter", "http://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
    
    for url in endpoints:
        req = urllib.request.Request(url, data=data_encoded, headers={'User-Agent': 'WindNavigator-Sim2Real'})
        try:
            print(f"Trying {url}...")
            with urllib.request.urlopen(req) as response:
                osm = json.loads(response.read().decode('utf-8'))
                buildings = process_buildings(osm)
                print(f"SUCCESS! Rasterizing {len(buildings)} buildings...")
                grid = rasterize_terrain(buildings, lat_min, lon_min, lat_max, lon_max)
                
                # Output to text explicitly so later solvers just load the local copy immediately
                with open("urban_terrain.txt", "w") as f:
                    f.write(f"{len(grid[0])} {len(grid)}\n")
                    for row in grid:
                        f.write(" ".join([str(h) for h in row]) + " ")
                print("Exported urban_terrain.txt successfully!")
                return
        except Exception as e:
            print(f"Failed {url}: {e}")
            time.sleep(2)
            
get_navi()
