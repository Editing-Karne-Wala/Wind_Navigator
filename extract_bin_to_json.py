import sys
import json
import os
from datetime import datetime

try:
    from pymavlink import mavutil
except ImportError:
    print("[!] pymavlink not installed. Run: pip install pymavlink")
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_bin_to_json.py <path_to.bin>")
        sys.exit(1)
        
    bin_file = sys.argv[1]
    print(f"[*] Opening {bin_file} via pymavlink DFReader...")
    
    try:
        mlog = mavutil.mavlink_connection(bin_file, robust_parsing=True)
    except Exception as e:
        print(f"[!] Failed to open log: {e}")
        sys.exit(1)
        
    print("[*] Scanning telemetry messages (this may take a moment for large files)...")
    
    # Store history of attitude to match with GPS ticks
    current_att = {"Pitch": 0.0, "Roll": 0.0}
    
    trace_data = []
    start_time_us = None
    
    msg_count = 0
    gps_count = 0
    
    while True:
        msg = mlog.recv_msg()
        if msg is None:
            break
            
        msg_type = msg.get_type()
        msg_count += 1
        
        if msg_type == 'ATT':
            # DataFlash ATT message usually contains Roll, Pitch, Yaw in degrees
            try:
                current_att["Pitch"] = msg.Pitch
                current_att["Roll"] = msg.Roll
            except AttributeError:
                pass # Structure might vary slightly
                
        elif msg_type == 'GPS':
            gps_count += 1
            # DataFlash GPS message
            try:
                lat = msg.Lat
                lng = msg.Lng
                time_us = msg.TimeUS
                
                # ArduCopter sometimes logs Lat/Lng as scaled integers (x 1e7)
                if abs(lat) > 1000: lat /= 1e7
                if abs(lng) > 1000: lng /= 1e7
                
                # Ignore 0,0 raw boots
                if lat == 0.0 and lng == 0.0: continue
                
                if start_time_us is None:
                    start_time_us = time_us
                    
                t_sec = int((time_us - start_time_us) / 1e6)
                
                # Check for wind anomaly symptoms: Pitch or Roll > 20 deg
                is_anomaly = abs(current_att["Pitch"]) > 20.0 or abs(current_att["Roll"]) > 25.0
                
                # To prevent massive arrays, downsample to 1 frame per second
                if len(trace_data) == 0 or trace_data[-1]["time_sec"] < t_sec:
                    trace_data.append({
                        "time_sec": t_sec,
                        "lat": lat,
                        "lon": lng,
                        "recorded_pitch_deg": round(current_att["Pitch"], 2),
                        "recorded_roll_deg": round(current_att["Roll"], 2),
                        "motor_rpm_spike": is_anomaly
                    })
            except AttributeError:
                pass
                
    print(f"[+] Total messages parsed: {msg_count}")
    print(f"[+] Total GPS fixes extracted: {gps_count}")
    print(f"[+] Downsampled synchronized trace length: {len(trace_data)} seconds.")
    
    if len(trace_data) == 0:
        print("[!] No GPS traces found in the log! Was GPS disabled?")
        sys.exit(1)
        
    output_json = "real_case_study.json"
    
    output = {
        "mission_id": f"ARDUPILOT_{os.path.basename(bin_file)}",
        "location": f"Extracted from log: Lat {trace_data[0]['lat']:.4f}, Lon {trace_data[0]['lon']:.4f}",
        "timestamp": datetime.now().isoformat(),
        "historical_weather": {
            "speed_mph": 22.5, # Assume heavy wind setting for simulation testing if unknown
            "direction_deg": 270.0,
            "note": "Wind synthetically assumed for generic crash simulation since METAR fetch requires historical API key."
        },
        "incident_report": f"Parsed directly from raw telemetry binary {os.path.basename(bin_file)}.",
        "flight_trace": trace_data
    }
    
    with open(output_json, "w") as f:
        json.dump(output, f, indent=2)
        
    print(f"\n[SUCCESS] Extracted JSON to {output_json}!")
    
if __name__ == "__main__":
    main()
