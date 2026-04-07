import urllib.request
import json
import math

# Fetch real-time weather data for Manhattan, NY from Open-Meteo (No API key needed)
url = "https://api.open-meteo.com/v1/forecast?latitude=40.7128&longitude=-74.0060&current_weather=true"

print("Fetching REAL-TIME wind data for Manhattan, NY (Lat: 40.7128, Lon: -74.0060)...")

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode())

current = data['current_weather']
wind_speed_kmh = current['windspeed']
wind_direction_deg = current['winddirection']

print(f"Current Real Wind: {wind_speed_kmh} km/h at {wind_direction_deg} degrees.")

# Convert to standard vectors (m/s)
wind_speed_ms = wind_speed_kmh * (1000.0 / 3600.0)

# We use classical trig down here ONLY to parse the real-world data into our discrete format.
# Once it goes into the simulation, it remains pure integer.
rad = math.radians(270 - wind_direction_deg) # Meteorological to Math angle
vx = wind_speed_ms * math.cos(rad)
vy = wind_speed_ms * math.sin(rad)

# Scale up for our Integer "Max Planck" grid (Scale factor 1000)
vx_int = int(vx * 1000)
vy_int = int(vy * 1000)

print(f"Discrete Vector Input Generated -> Vx: {vx_int}, Vy: {vy_int}")

# We will generate a configuration file for the C++ engine
with open("real_wind_input.txt", "w") as f:
    f.write(f"{vx_int} {vy_int}\n")

print("Saved absolute integer weather parameters to real_wind_input.txt")
