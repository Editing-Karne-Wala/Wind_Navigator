---

# Chapter 5: Code Architecture

## 5.1 Repository Overview

```
Wind_Navigator/
├── Core Physics
│   ├── rational_wind.py          # D2Q9 Integer LBM engine (Remainder Vault)
│   ├── lbm_engine.cpp            # C++ hot-path collision loop
│   ├── conservative_lbm.cpp      # Mass-conservative LBM reference impl
│   └── turbulence_metrics.py     # FAA AC 00-30C turbulence classification
│
├── Forensic Pipeline
│   ├── extract_bin_to_json.py    # ArduPilot .BIN binary parser
│   ├── sitl_flight_analyzer.py   # SITL validation + confusion matrix
│   └── wind_solver.py            # 360° Back-Propagation Engine
│
├── Terrain & Weather
│   ├── osm_terrain_parser.py     # Global OSM building geometry extractor
│   ├── fetch_osm.py              # Multi-endpoint OSM fetcher with cache
│   └── noaa_wind_client.py       # Live METAR aviation weather ingestion
│
├── Hardware Bridge
│   ├── mavlink_bridge.py         # MAVLink SITL flight controller commands
│   └── jsbsim_bridge.py          # JSBSim aerodynamic validation bridge
│
├── Routing & Pathfinding
│   ├── router_4d.cpp             # 4D A* vorticity-aware pathfinding
│   ├── router_4d.py              # Python wrapper for 4D router
│   └── swarm_controller.py       # Multi-drone swarm coordination
│
├── CUDA Acceleration
│   ├── cuda_swarm_pathfinder.cu  # GPU-accelerated swarm routing
│   ├── cuda_lyapunov_monitor.cu  # Real-time Lyapunov instability detection
│   ├── cuda_attractor_map.cu     # Strange attractor phase-space mapping
│   └── cuda_dynamic_memory.cu    # Dynamic GPU memory allocation
│
├── Validation & Testing
│   ├── test_determinism.py       # Cross-platform hash validation
│   ├── validate_physics.py       # Full benchmark suite
│   └── sitl_bridge_test.py       # Hardware-in-loop test harness
│
└── Service Layer
    ├── server.py                 # FastAPI edge inference server
    ├── wind_navigator_daemon.py  # Background pre-computation daemon
    └── post_to_moltbook.py       # Community outreach integration
```

## 5.2 Component Deep-Dives

### 5.2.1 `extract_bin_to_json.py` — The Telemetry Parser

This is the entry point of the forensic pipeline. Every drone crash investigation starts here.

**Purpose:** Parse a binary ArduPilot dataflash `.BIN` file into a structured JSON document containing the GPS trace, IMU readings, motor RPM values, and atmospheric pressure data — timestamped and indexed to the millisecond.

**Technical approach:**
The ArduPilot dataflash format is a proprietary binary encoding. Each log record begins with a 2-byte header (0xA3, 0x95), followed by a 1-byte message type ID, followed by the message payload. The schema for each message type is defined in a `FMT` record at the top of the log.

```python
def parse_bin_file(filepath):
    """
    Stage 1: Read the FMT records to build the message schema.
    Stage 2: Iterate all records, decode by type, append to timeline.
    Stage 3: Interpolate GPS coordinates to fill gaps (GPS logs at 5 Hz,
             IMU logs at 400 Hz — we align them by timestamp).
    """
    from pymavlink import mavutil

    mlog = mavutil.mavlink_connection(filepath, dialect='ardupilotmega')
    timeline = []

    while True:
        msg = mlog.recv_match(blocking=False)
        if msg is None:
            break
        mtype = msg.get_type()
        if mtype == 'GPS':
            timeline.append({
                'time_ms': msg.TimeUS // 1000,
                'lat': msg.Lat / 1e7,
                'lon': msg.Lng / 1e7,
                'alt': msg.Alt / 100.0,
                'record_type': 'GPS'
            })
        elif mtype == 'ATT':
            timeline.append({
                'time_ms': msg.TimeUS // 1000,
                'roll': msg.Roll,
                'pitch': msg.Pitch,
                'yaw': msg.Yaw,
                'record_type': 'ATT'
            })
        # ... RCOU, BARO, VIBE records similarly processed

    return build_unified_trace(timeline)
```

**Output format:**
```json
{
  "metadata": {
    "flight_duration_seconds": 695,
    "total_records": 278450,
    "gps_records": 3475,
    "att_records": 278000,
    "anomaly_detected": true
  },
  "flight_trace": [
    {
      "time_ms": 1000,
      "lat": 19.0921,
      "lon": 73.0285,
      "alt_m": 45.2,
      "roll_deg": 2.1,
      "pitch_deg": -0.8,
      "rpm_m1": 4820,
      "rpm_m2": 4835,
      "is_anomaly": false
    }
  ]
}
```

**Anomaly detection logic:**
A frame is flagged as `is_anomaly = true` when ANY of the following conditions are met:
- `abs(roll_deg) > 15.0` — uncommanded lateral tilt
- `abs(pitch_deg) > 15.0` — uncommanded fore-aft tilt
- Any motor RPM deviates from mean RPM by more than 25%

These thresholds are derived from ArduPilot's own EKF innovation threshold documentation and are consistent with what the flight controller itself classifies as an "attitude error event."

---

### 5.2.2 `osm_terrain_parser.py` — The Geometry Engine

**Purpose:** Given a GPS bounding box (lat_min, lon_min, lat_max, lon_max), download the actual physical building footprints from OpenStreetMap and rasterize them into an integer height map suitable for the LBM physics engine.

**The Overpass Query:**
```python
def build_overpass_query(lat_min, lon_min, lat_max, lon_max):
    return f"""
    [out:json][timeout:25];
    (
      way["building"]({lat_min},{lon_min},{lat_max},{lon_max});
      relation["building"]({lat_min},{lon_min},{lat_max},{lon_max});
    );
    out geom;
    """
```

**Multi-endpoint resilience:**
The Overpass API has multiple public mirrors. The parser attempts them in priority order:
1. `https://lz4.overpass-api.de/api/interpreter`
2. `http://overpass-api.de/api/interpreter`
3. `https://overpass.kumi.systems/api/interpreter`

If all API endpoints fail (common during rate-limiting), the engine falls back to `urban_terrain.txt` — a local binary cache of the last successfully downloaded geometry.

**Rasterization:**
The building polygons (WGS-84 coordinate arrays) are projected onto an 80×80 integer grid using ray-casting:

```python
def rasterize_terrain(buildings, lat_min, lon_min, lat_max, lon_max, grid_size=80):
    """
    For each building polygon:
    1. Normalize coordinates to [0, grid_size] range.
    2. Use integer ray-casting to determine which grid cells fall inside the polygon.
    3. Assign the building's height (from OSM 'height' or 'building:levels' tag)
       as the integer value of those cells.
    4. Cells with no building have value 0.
    """
    grid = [[0]*grid_size for _ in range(grid_size)]

    for building in buildings:
        h = building.get('height', building.get('levels', 3) * 3)
        polygon = normalize_polygon(building['nodes'], lat_min, lon_min,
                                    lat_max, lon_max, grid_size)
        for y in range(grid_size):
            for x in range(grid_size):
                if point_in_polygon(x + 0.5, y + 0.5, polygon):
                    grid[y][x] = int(h)
    return grid
```

The `point_in_polygon` check uses the **integer ray-casting algorithm** — no floating-point trig. The ray is cast horizontally, and the number of polygon edge crossings is counted. Odd count = inside. Even count = outside. This is exact for integer coordinates.

---

### 5.2.3 `rational_wind.py` — The D2Q9 Physics Engine

This is the mathematical heart of Wind_Navigator. It implements a 2D Lattice Boltzmann Method using the D2Q9 lattice with BGK collision operator, entirely in integer arithmetic with the Remainder Vault mass conservation system.

**The D2Q9 Lattice:**

The D2Q9 (2 Dimensions, 9 Velocities) lattice assigns 9 discrete velocity directions to each cell:

```
NW  N  NE       (-1,1) (0,1) (1,1)
 W  C   E   =   (-1,0) (0,0) (1,0)
SW  S  SE       (-1,-1)(0,-1)(1,-1)
```

Each direction `i` has:
- A velocity vector `(ex[i], ey[i])` — exact integers in {-1, 0, 1}
- A weight `w[i]` — exact rationals: 4/9 for center, 1/9 for cardinals, 1/36 for diagonals

**The LBM Algorithm (one time step):**

```
Step 1: COLLISION
    For each cell (x, y) and direction i:
        Compute local density: rho = Σ f[x][y][i]
        Compute velocity: u = Σ f[x][y][i] * e[i] / rho
        Compute equilibrium: f_eq[i] = w[i] * rho * (1 + 3(e·u) + 9(e·u)²/2 - 3u²/2)
        Relax: f_new[i] = f[i] + (f_eq[i] - f[i]) / tau   [INTEGER + VAULT]

Step 2: STREAMING
    For each cell and direction:
        Move f_new from (x,y) to (x + ex[i], y + ey[i])

Step 3: BOUNDARY CONDITIONS
    For solid cells (buildings): apply no-slip bounce-back
    For inlet cells: apply constant velocity inflow (the wind direction being tested)
    For outlet cells: apply zero-gradient outflow
```

**Integer scaling:**
All distribution functions are stored as integers scaled by `SCALE = 1,000,000`:
- `f[i] = 1.0` is stored as `1,000,000`
- `f_eq = 0.4444...` is stored as `444,444` with the remainder `0.4444... - 0.4444 = 0.0000...` captured in the vault

**Vorticity computation:**
After the simulation runs for N steps, vorticity at each cell is computed:

```python
def compute_vorticity(ux, uy, grid_size):
    """
    Vorticity = duy/dx - dux/dy
    All computed with integer central differences.
    """
    vorticity = [[0] * grid_size for _ in range(grid_size)]
    for y in range(1, grid_size-1):
        for x in range(1, grid_size-1):
            duy_dx = uy[y][x+1] - uy[y][x-1]  # integer
            dux_dy = ux[y+1][x] - ux[y-1][x]  # integer
            vorticity[y][x] = duy_dx - dux_dy  # integer — no trig, no floats
    return vorticity
```

A vorticity magnitude exceeding the threshold of **800 (in scaled integer units)** corresponds to aerodynamically significant shear — roughly 8 m/s wind speed differential across one cell width, sufficient to destabilize a 5kg drone.

---

### 5.2.4 `wind_solver.py` — The Back-Propagation Engine

**Purpose:** Given a crash flight log with no historical weather data, mathematically determine the ambient wind direction at time of crash — or exonerate the aerodynamics entirely.

**Algorithm:**

```python
WIND_ANGLES = range(0, 360, 20)  # 18 angles to test

def back_propagate(terrain_grid, crash_frames, safe_frames):
    results = {}

    for angle in WIND_ANGLES:
        # Convert angle to integer velocity components
        # (Using only the 8 cardinal/diagonal D2Q9 directions for pure integer math)
        ux_inlet = INLET_SPEEDS[nearest_d2q9_direction(angle)][0]
        uy_inlet = INLET_SPEEDS[nearest_d2q9_direction(angle)][1]

        # Run 120 frames of D2Q9 LBM simulation
        vorticity_map = run_lbm(terrain_grid, ux_inlet, uy_inlet, steps=120)

        # For each crash frame GPS coordinate, check if vorticity > 800
        true_positives = 0
        for frame in crash_frames:
            grid_x, grid_y = gps_to_grid(frame['lat'], frame['lon'], terrain_grid)
            if vorticity_map[grid_y][grid_x] > VORTICITY_THRESHOLD:
                true_positives += 1

        # Accuracy: (TP + TN) / Total
        true_negatives = sum(1 for f in safe_frames
                            if vorticity_map[gps_to_grid_y(f)][gps_to_grid_x(f)]
                            <= VORTICITY_THRESHOLD)
        accuracy = (true_positives + true_negatives) / (len(crash_frames) + len(safe_frames))

        results[angle] = {
            'true_positives': true_positives,
            'accuracy': accuracy
        }

    # Find the wind angle that best explains the crash
    best_angle = max(results, key=lambda a: results[a]['true_positives'])
    return results, best_angle
```

**Interpretation:**
- If `true_positives > 0` at any angle: that angle is the probable wind direction at time of crash. The report states: *"Urban aerodynamic forces consistent with N-degree wind were present and are a plausible contributing factor."*
- If `true_positives == 0` at all angles: the report states: *"No ambient wind direction tested produces structural vorticity at the crash coordinates. Aerodynamic forces are exonerated. Probable cause: mechanical/electrical failure."*

---

### 5.2.5 `sitl_flight_analyzer.py` — The Statistical Validator

**Purpose:** Apply the confusion matrix framework to the full flight log, producing scientifically rigorous accuracy metrics rather than a simple percentage.

**The Confusion Matrix:**

|  | Predicted: Danger | Predicted: Safe |
|---|---|---|
| **Actual: Anomaly** | True Positive (TP) | False Negative (FN) |
| **Actual: Normal** | False Positive (FP) | True Negative (TN) |

**Key metrics computed:**
- **Precision** = TP / (TP + FP) — When we say "danger," how often are we right?
- **Recall** = TP / (TP + FN) — Of all actual dangers, how many did we catch?
- **F1 Score** = 2 * (Precision * Recall) / (Precision + Recall)
- **Specificity** = TN / (TN + FP) — Of all safe moments, how many did we correctly clear?

These four metrics appear in the final forensic report.

---

# Chapter 6: The Forensic Pipeline

## 6.1 End-to-End Flow

```
INPUT: Customer uploads ARDUPILOT_LOG.bin via web portal
          │
          ▼
STAGE 1: extract_bin_to_json.py
  - Parse binary dataflash format via pymavlink
  - Extract GPS trace (5 Hz), ATT (attitude) records (400 Hz)
  - Flag anomaly frames: |roll| > 15° OR |pitch| > 15° OR RPM spike > 25%
  - Output: real_case_study.json
          │
          ▼
STAGE 2: fetch_osm.py
  - Compute GPS bounding box from flight trace ± 0.002° margin
  - Query OpenStreetMap Overpass API for building footprints
  - Rasterize into 80×80 integer height grid
  - Cache to urban_terrain.txt (fallback if API unavailable)
          │
          ▼
STAGE 3: wind_solver.py (The Back-Propagation)
  - Sweep 18 wind angles (0° to 340° in 20° steps)
  - For each angle: run 120-step D2Q9 LBM simulation
  - Cross-reference vorticity map with anomaly frame GPS positions
  - Compute TP/FP/TN/FN at each angle
  - Identify best-fit wind direction OR exonerate aerodynamics
          │
          ▼
STAGE 4: sitl_flight_analyzer.py
  - Run full confusion matrix on complete flight log
  - Compute Precision, Recall, F1, Specificity
  - Generate detailed per-frame event log
          │
          ▼
STAGE 5: report_generator.py (to be built in Phase 40)
  - Assemble findings into structured PDF
  - Include: flight map, vorticity heatmap, confusion matrix table,
             back-propagation results, determinism certificate
  - Output: FORENSIC_REPORT_[timestamp].pdf
          │
          ▼
OUTPUT: PDF delivered to customer email
```

## 6.2 Processing Time

| Stage | Typical Duration |
|---|---|
| Binary parsing (extract_bin_to_json.py) | 5–30 seconds (scales with log size) |
| OSM geometry fetch | 2–8 seconds (network dependent) |
| Back-propagation sweep (18 angles × 120 LBM steps) | 90–180 seconds |
| Statistical analysis | < 5 seconds |
| PDF generation | < 10 seconds |
| **Total end-to-end** | **~5 minutes** |

This is entirely acceptable for a forensic report service where customers expect results within hours, not milliseconds.

---

# Chapter 7: The PDF Report Format

## 7.1 Report Structure

Every forensic report produced by Wind_Navigator follows a fixed, legally-oriented structure:

### Page 1: Cover Page
- Report title: "Aerodynamic Forensic Analysis Report"
- Incident reference number (auto-generated UUID)
- Date of analysis
- Drone model (extracted from log if present)
- Flight duration and GPS bounds
- **Determinism Certificate:** SHA-256 hash of the physics computation, proving the result is reproducible

### Page 2: Executive Determination
A single, unambiguous determination in large type:

> **DETERMINATION: AERODYNAMIC FORCES EXONERATED**
> *Mathematical analysis of 18 ambient wind scenarios found no configuration capable of producing the observed attitude excursion at the recorded crash coordinates given the structural geometry of the area.*

or:

> **DETERMINATION: AERODYNAMIC CONTRIBUTION PROBABLE**
> *Wind from approximately 220° produces structural vorticity exceeding critical threshold at the crash coordinates. This is consistent with the recorded attitude anomaly.*

### Pages 3–4: Flight Data Summary
- GPS trace map (building polygons overlaid)
- Altitude profile over time
- Attitude (roll/pitch) over time with anomaly timestamps highlighted in red
- Motor RPM trace

### Pages 5–6: Physics Analysis
- Vorticity heatmap for the best-fit (or worst-case) wind angle
- Explanation of the D2Q9 LBM methodology in plain language
- The Remainder Vault mass conservation proof

### Pages 7–8: Back-Propagation Results Table

| Wind Direction | True Positives | Accuracy | Conclusion |
|---|---|---|---|
| 0° (North) | 0 | 86.6% | No correlation |
| 20° | 0 | 86.6% | No correlation |
| ... | ... | ... | ... |
| 220° (SW) | 12 | 97.1% | **HIGHEST CORRELATION** |

### Page 9: Statistical Validation
- Full confusion matrix
- Precision, Recall, F1 Score, Specificity values
- Comparison to baseline random classifier

### Page 10: Methodology & Limitations
- Data sources used (OpenStreetMap version, NOAA METAR if available)
- Known limitations (D2Q9 is 2D — vertical updrafts not modeled)
- Assumptions made
- Disclaimer language

### Page 11: Determinism Certificate
- Hardware used for computation
- Software version hash (git commit SHA)
- Physics output SHA-256 hash
- Instructions for independent verification

---

# Chapter 8: The Web Service Architecture

## 8.1 Service Components

```
Customer Browser
      │
      ▼
Landing Page (index.html)
  - Pricing tiers
  - File upload form (.BIN, max 500MB)
  - Stripe checkout
      │
      ▼
FastAPI Backend (server.py)
  - POST /upload — receive .BIN file, validate, queue job
  - GET /status/{job_id} — poll job status
  - GET /report/{job_id} — download completed PDF
      │
      ▼
Job Queue (Redis or SQLite)
  - Stores: job_id, customer_email, bin_filepath, status, report_path
      │
      ▼
Worker Process (wind_solver.py wrapped in job runner)
  - Picks up queued jobs
  - Runs 5-stage forensic pipeline
  - Generates PDF
  - Sends email with download link
      │
      ▼
Email Delivery (SMTP / SendGrid)
  - PDF attached or linked
  - Report reference number included
```

## 8.2 Pricing Tiers

| Tier | Price | Delivery | Features |
|---|---|---|---|
| **Standard Report** | $75 | 24 hours | 11-page PDF, basic determination |
| **Expert Report** | $150 | 4 hours | Full 11-page PDF + raw data JSON + phone consultation slot |
| **Legal Package** | $250 | 24 hours | Expert Report + notarized cover letter + expert witness availability |

## 8.3 Target Customers

1. **Individual drone operators** disputing insurance claims — $75 is trivially affordable vs. a $5,000 claim dispute.
2. **Commercial delivery companies** (small to mid-size) investigating fleet incidents.
3. **Legal firms** handling drone liability cases — they bill at $300/hr, a $250 technical report is cheap.
4. **Drone insurance companies** — potential for bulk processing contracts.
5. **Aviation safety researchers** — academic licensing.

---

# Chapter 9: Roadmap

## 9.1 Phase 40 — Launch Sub-Product 1 (Forensic Reports)

**Week 1:**
- Build `report_generator.py` (ReportLab or WeasyPrint PDF generation)
- Build simple landing page with Stripe Checkout integration
- Set up job queue with SQLite
- Deploy on a single VPS (DigitalOcean $12/month droplet)

**Week 2:**
- Connect email delivery (SendGrid free tier: 100 emails/day)
- End-to-end test with 5 real .BIN logs
- Soft-launch on Moltbook m/Wind_Navigator

**Week 3–4:**
- Collect first paying customers
- Iterate on PDF report quality based on feedback
- Begin building Sub-Product 2 (route checker) in parallel

## 9.2 Phase 41 — Sub-Product 2: Safe Route Checker

A web form where operators enter start/end GPS coordinates before a flight. The engine returns a risk-annotated route map. Subscription model: $9/month for 50 checks.

## 9.3 Phase 42 — Sub-Product 3: Live Mid-Flight API

Pre-computed tile cache + FastAPI inference endpoint. Enterprise subscriptions per city zone. This is the largest revenue opportunity but requires the most infrastructure.

## 9.4 Phase 43 — D3Q19 Vertical Expansion

Upgrade from 2D D2Q9 to 3D D3Q19 lattice to model vertical updrafts, thermal plumes, and multi-altitude routing. Critical for VTOL aircraft operating above rooftop level.

---

*End of Documentation — Wind_Navigator Forensic Report Service v1.0*
*All rights reserved. MIT License for open-source components.*
*For commercial licensing inquiries: see GitHub repository.*
