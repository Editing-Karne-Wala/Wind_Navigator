import os
import sys
from pymavlink import mavutil

def get_first_gps(file_path):
    try:
        if file_path.endswith('.tlog'):
            mlog = mavutil.mavlink_connection(file_path)
            while True:
                msg = mlog.recv_match(type=['GPS_RAW_INT', 'GLOBAL_POSITION_INT'], blocking=False)
                if not msg: break
                lat = msg.lat / 1e7
                lon = msg.lon / 1e7
                if lat != 0 and lon != 0:
                    return lat, lon
        else: # .bin
            mlog = mavutil.mavlink_connection(file_path, robust_parsing=True)
            while True:
                msg = mlog.recv_msg()
                if not msg: break
                if msg.get_type() == 'GPS':
                    lat = getattr(msg, 'Lat', 0)
                    lon = getattr(msg, 'Lng', 0)
                    if abs(lat) > 1000: lat /= 1e7
                    if abs(lon) > 1000: lon /= 1e7
                    if lat != 0 and lon != 0:
                        return lat, lon
    except Exception as e:
        return f"Error: {e}"
    return "No GPS found"

logs_dir = r'C:\Users\shiny\Documents\Crash_Logs'
files = [f for f in os.listdir(logs_dir) if f.lower().endswith(('.bin', '.tlog'))]

print("| Filename | Latitude | Longitude |")
print("|----------|----------|-----------|")
for f in files:
    full_path = os.path.join(logs_dir, f)
    result = get_first_gps(full_path)
    if isinstance(result, tuple):
        print(f"| {f} | {result[0]:.6f} | {result[1]:.6f} |")
    else:
        print(f"| {f} | {result} | |")
