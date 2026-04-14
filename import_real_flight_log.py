#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR - Phase 39: Real-World Flight Log Importer
=========================================================
Converts raw ArduPilot telemetry exports (.csv) or DJI logs into 
the standardized JSON format required for SITL validation.

How to use:
1. Go to discuss.ardupilot.org -> "Copter" -> "Crashes".
2. Find an urban drone crash log (.bin) where wind was the suspected cause.
3. Open in MissionPlanner -> "Telemetry Logs" -> "Create KML + CSV".
4. Run this script passing the generated GPS.csv and ATT.csv.
   python import_real_flight_log.py --gps flight_GPS.csv --att flight_ATT.csv

This completely decouples the SITL engine from synthetic data, allowing 
genuine, non-circular scientific validation of the D2Q9 Vortex Engine.
"""

import csv
import json
import argparse
from datetime import datetime

def parse_ardupilot_csv(gps_file, att_file, output_json="real_case_study.json"):
    print(f"[*] Importing real-world ArduPilot Telemetry...")
    print(f"    -> GPS File: {gps_file}")
    print(f"    -> ATT File: {att_file}")
    
    # 1. Parse ATT (Attitude) - High Frequency Pitch/Roll
    att_data = [] # List of dicts
    try:
        with open(att_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                att_data.append({
                    "time_us": int(row['TimeUS']),
                    "pitch": float(row['Pitch']),
                    "roll": float(row['Roll'])
                })
        print(f"[+] Loaded {len(att_data)} Attitude (Pitch/Roll) records.")
    except Exception as e:
        print(f"[!] Failed to parse ATT file: {e}")
        return

    # 2. Parse GPS (Position) - Lower frequency
    trace = []
    try:
        with open(gps_file, 'r') as f:
            reader = csv.DictReader(f)
            start_time = None
            
            for row in reader:
                time_us = int(row['TimeUS'])
                if start_time is None: start_time = time_us
                
                # Match closest ATT record
                closest_att = min(att_data, key=lambda x: abs(x['time_us'] - time_us))
                
                # Compute elapsed time in seconds
                t_sec = int((time_us - start_time) / 1e6)
                
                # ArduPilot encodes Lat/Lng as floats
                lat = float(row['Lat'])
                lon = float(row['Lng'])
                
                # Detect anomalies programmatically for the engine to verify
                # Example: If pitch exceeds 20 degrees suddenly, flag it.
                is_anomaly = abs(closest_att['pitch']) > 20.0 or abs(closest_att['roll']) > 25.0
                
                trace.append({
                    "time_sec": t_sec,
                    "lat": lat,
                    "lon": lon,
                    "recorded_pitch_deg": round(closest_att['pitch'], 2),
                    "recorded_roll_deg": round(closest_att['roll'], 2),
                    "motor_rpm_spike": is_anomaly
                })
    except Exception as e:
        print(f"[!] Failed to parse GPS file: {e}")
        return

    print(f"[+] Interpolated {len(trace)} GPS/ATT traces into synchronized timeline.")

    # 3. Construct the Case Study JSON
    output = {
        "mission_id": "ARDUPILOT_EXTERNAL_CRASH_LOG",
        "location": f"Sourced from Coordinates: {trace[0]['lat']:.4f}, {trace[0]['lon']:.4f}",
        "timestamp": datetime.now().isoformat(),
        "historical_weather": {
            "speed_mph": 20.0, # User must manually update this based on NOAA historical archives for the date
            "direction_deg": 270.0,
            "note": "AWAITING EXTERNAL WEATHER VERIFICATION"
        },
        "incident_report": "Imported from external .bin -> .csv telemetry log via MissionPlanner.",
        "flight_trace": trace
    }

    with open(output_json, "w") as f:
        json.dump(output, f, indent=2)
        
    print(f"\n[SUCCESS] Exported real flight envelope to '{output_json}'.")
    print("\nNext Steps:")
    print("1. Open 'real_case_study.json' and manually input the historical wind speed for those coordinates.")
    print("2. Modify 'sitl_flight_analyzer.py' to load 'real_case_study.json'.")
    print("3. Rerun the simulator to objectively validate the integer engine against this real-world event.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Import ArduPilot CSV logs to WindNavigator SITL.')
    parser.add_argument('--gps', type=str, default='GPS.csv', help='ArduPilot GPS CSV file')
    parser.add_argument('--att', type=str, default='ATT.csv', help='ArduPilot Attitude CSV file')
    args = parser.parse_args()
    
    parse_ardupilot_csv(args.gps, args.att)
