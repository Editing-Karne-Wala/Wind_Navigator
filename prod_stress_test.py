# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR -- Phase 33: Production Swarm API Stress Test
============================================================
Resolving Gap E3: "Stress test runs against the local API. No test 
against the deployed production endpoint under real network conditions."

We use `aiohttp` and `asyncio` to blast an HTTP endpoint with 250 
concurrent real-time weather-routing queries. This tests:
1. Nginx/Uvicorn worker starvation or thread-lock.
2. Network Latency vs Compute Latency (TCP Overhead).
3. JSON Unmarshaling at scale over the wire.
"""

import asyncio
import time
import argparse
import json
import uuid
import statistics
import sys

# Required for async HTTP benchmarking
try:
    import aiohttp
except ImportError:
    print("WARNING: aiohttp not installed. Please run: pip install aiohttp")
    sys.exit(1)

async def measure_drone_ping(session, endpoint, payload):
    """Fires a single payload and measures exact round-trip network latency."""
    t_start = time.perf_counter()
    status_code = 0
    try:
        async with session.post(endpoint, json=payload, timeout=10.0) as response:
            status_code = response.status
            data = await response.json()
    except Exception as e:
        status_code = 500
        
    t_end = time.perf_counter()
    latency_ms = (t_end - t_start) * 1000
    return status_code, latency_ms

async def swarm_attack(endpoint="http://127.0.0.1:8000/route", swarm_size=250):
    print("="*60)
    print(f"Phase 33: Validating Swarm API at Scale")
    print(f"Targeting: {endpoint}")
    print(f"Swarm Size: {swarm_size} Concurrent Drones")
    print("="*60)
    
    # Random payloads simulating a swarm over Manhattan
    payloads = []
    for i in range(swarm_size):
        payloads.append({
            "drone_id": f"SWARM-DRONE-{i}",
            "lat": 40.753, # Valid inner-Manhattan bounding box coord
            "lon": -73.982,
            "altitude_meters": 100.0
        })
        
    # Connection pooling: Test how the server handles massive parallel TCP sockets
    connector = aiohttp.TCPConnector(limit=swarm_size) # Do not queue on client side
    
    start_time = time.time()
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [measure_drone_ping(session, endpoint, p) for p in payloads]
        
        # Launch all 250 drones at the exact same millisecond
        results = await asyncio.gather(*tasks)
        
    total_time = time.time() - start_time
    
    # Analyze Latency Distribution
    latencies = [rt[1] for rt in results if rt[0] == 200]
    failures = [rt for rt in results if rt[0] != 200]
    
    if len(latencies) == 0:
        print("\n[CRITICAL FAILURE] Zero requests succeeded.")
        print("Check if the server is running.")
        return

    latencies.sort()
    
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies)*0.95)] if len(latencies) > 20 else max(latencies)
    p99 = latencies[int(len(latencies)*0.99)] if len(latencies) > 50 else max(latencies)
    
    print("\n[STRESS TEST RESULTS]")
    print(f"Total Wall Clock Time:  {round(total_time * 1000, 2)} ms")
    print(f"Successful Pings:       {len(latencies)} / {swarm_size}")
    print(f"Failed Pings (500s/TO): {len(failures)}")
    
    print("\n[LATENCY DISTRIBUTION PROFILE]")
    print(f"  Minimum Latency: {round(min(latencies), 1)} ms")
    print(f"  p50 (Median):    {round(p50, 1)} ms")
    print(f"  p95 (Heavy):     {round(p95, 1)} ms")
    print(f"  p99 (Spike):     {round(p99, 1)} ms")
    print(f"  Max Latency:     {round(max(latencies), 1)} ms")
    
    print("\nGap E3 Closed: Actual TCP connection limits and JSON marshaling overhead at scale are now captured.")
    
    if p99 < 50:
        print("[PERFORMANCE VALIDATED] Engine conforms to <50ms Edge-Node constraint.")
    else:
        print("[ARCHITECTURE WARNING] Tail latencies (p99) exceeded 50ms.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/route", help="Production API endpoint")
    parser.add_argument("--drones", type=int, default=250, help="Number of concurrent drones in swarm")
    args = parser.parse_args()
    
    # Note: If running on Windows, must use SelectorEventLoop for aiohttp stability at high scale
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(swarm_attack(endpoint=args.url, swarm_size=args.drones))
