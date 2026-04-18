import os
import sys
from pymavlink import mavutil

# Suppress pymavlink errors
class DevNull:
    def write(self, msg): pass
    def flush(self): pass

sys.stderr = DevNull()

def get_gps_data(file_path):
    coords = []
    try:
        if file_path.endswith('.tlog'):
            mlog = mavutil.mavlink_connection(file_path)
            # Sample first 20 valid GPS points
            count = 0
            while count < 20:
                msg = mlog.recv_match(type=['GPS_RAW_INT', 'GLOBAL_POSITION_INT'], blocking=False)
                if not msg: break
                lat = msg.lat / 1e7
                lon = msg.lon / 1e7
                if lat != 0 and lon != 0:
                    coords.append((lat, lon))
                    count += 1
        else: # .bin
            mlog = mavutil.mavlink_connection(file_path, robust_parsing=True)
            count = 0
            while count < 5000: # Scan deeper into bin
                msg = mlog.recv_msg()
                if not msg: break
                if msg.get_type() == 'GPS':
                    lat = getattr(msg, 'Lat', 0)
                    lon = getattr(msg, 'Lng', 0)
                    if abs(lat) > 1000: lat /= 1e7
                    if abs(lon) > 1000: lon /= 1e7
                    if lat != 0 and lon != 0:
                        coords.append((lat, lon))
                        if len(coords) >= 20: break
                count += 1
    except:
        pass
    return coords

logs_dir = r'C:\Users\shiny\Documents\Crash_Logs'
files = [f for f in os.listdir(logs_dir) if f.lower().endswith(('.bin', '.tlog'))]

print("RESULT_START")
for f in files:
    full_path = os.path.join(logs_dir, f)
    coords = get_gps_data(full_path)
    if coords:
        # Use the most common coord or first one
        lat, lon = coords[-1]
        print(f"{f}|{lat}|{lon}")
    else:
        print(f"{f}|NONE|NONE")
print("RESULT_END")
