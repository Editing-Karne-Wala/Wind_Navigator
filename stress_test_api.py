import concurrent.futures
import time
import urllib.request
import urllib.error
import urllib.parse
import json
import random

API_URL = "http://127.0.0.1:8000/route"

LAT_TARGETS = [40.753, 40.754, 40.755]
LON_TARGETS = [-73.984, -73.983, -73.982, -73.981]

def ping_drone_api(drone_id):
    lat = random.choice(LAT_TARGETS) + random.uniform(-0.0005, 0.0005)
    lon = random.choice(LON_TARGETS) + random.uniform(-0.0005, 0.0005)
    alt = random.uniform(5.0, 100.0) 
    
    payload = {
        "drone_id": f"ALPHA_SWARM_{drone_id}",
        "lat": lat,
        "lon": lon,
        "altitude_meters": alt
    }
    
    payload_bytes = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(API_URL, data=payload_bytes, headers={'Content-Type': 'application/json'})
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120.0) as response:
            ms = (time.time() - start_time) * 1000
            data = json.loads(response.read().decode('utf-8'))
            
            if data['status'] == 'SAFE':
                vec = data['wind_vector']
                return f"[+] {payload['drone_id']}: SAFE PATH | Wind [Vx:{vec['vx']:.0f}, Vy:{vec['vy']:.0f}, Vz:{vec['vz']:.0f}] | Ping: {ms:.0f}ms", True
            else:
                return f"[-] {payload['drone_id']}: {data['status']} - {data['warning']} | Ping: {ms:.0f}ms", False
    except Exception as e:
         return f"[!] {payload['drone_id']}: CONNECTION FAILED ({str(e)})", False

if __name__ == "__main__":
    print("====== PHASE 6: ENTERPRISE EDGE-API STRESS TEST ======")
    print("Simulating a tactical swarm hitting the API...")
    
    start_total = time.time()
    
    results = []
    successes = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(ping_drone_api, i) for i in range(25)]
        for f in concurrent.futures.as_completed(futures):
            res_str, is_safe = f.result()
            results.append(res_str)
            if is_safe: successes += 1
            
    end_total = time.time()
    
    print("\n--- BATTLEFIELD ROUTING SAMPLE ---")
    for r in results:
        print(r)
        
    print("\n=======================================================")
    print(f"Total Drones Routed Safely: {successes}")
    print(f"Total Computation Time: {(end_total - start_total):.2f} seconds")
    print("Every ping initialized a C++ Matrix translating OSM terrain and computing aerodynamic turbulence.")
    print("=======================================================\n")
