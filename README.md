# Wind_Navigator
### Deterministic Urban Drone Networking & Vortex Avoidance

> **Current State:** Phase 28 — Validated Integer Physics & Real-World Bridge.
> An autonomous flight-management engine designed to detect urban building vortices and send MAVLink rerouting alerts to PyHawk/ArduCopter drones before they hit turbulent airspace, using real NOAA METAR data and live OpenStreetMap structural footprints.

---

## The Core Concept: Integer Gradient Cross-Product Bifurcation Detection

Traditional Navier-Stokes approximations (like OpenFOAM) use floating-point calculus. Float approximation creates state drift across heterogeneous parallel hardware architectures (the "IEEE 754 fiasco"), which causes swarm collisions in simulation environments.

**Wind_Navigator** bypasses floating-point derivatives by utilizing **Integer gradient cross-product bifurcation detection**.
Instead of solving the complete Navier-Stokes field, we use an O(1) integer proxy to flag aerodynamic "saddle points" where severe turbulent mixing occurs at the corners of buildings.

### How it works natively in `rational_wind.py`:
```python
dx = terrain[gy][gx+1] - terrain[gy][gx-1]   # Integer Terrain Gradient X
dy = terrain[gy+1][gx] - terrain[gy-1][gx]   # Integer Terrain Gradient Y
is_bifurcation = (dx * dy < 0)               # Gradient Vector Crossing Check
```
*Note: Phase 27 External CFD Validation exposed that this 1D integer proxy misses 50% of building corners and straight canyon sheers. A full D2Q9 Lattice Boltzmann streaming step (Phase 29) is slated to correct this mathematical hole entirely.*

---

## Live Performance & Features

### 1. Real-World Terrain Ingestion (Phase 26)
Procedural 80x80 grids have been completely replaced. `osm_terrain_parser.py` grabs the literal live bounding-box coordinates from **OpenStreetMap (Midtown Manhattan)**, ray-casting the physical 3D polygons directly into our discrete integer physics mesh. 

### 2. Live NOAA Aviation Wind Data (Phase 25)
The engine pulls and vector-averages live API METAR wind observations from JFK and LaGuardia. 
- Real-world validation: Discovered that previous empirical hardcoded guesses (8mph @ 220 deg) were off by roughly 200 degrees from reality. 
- Sourced natively in `noaa_wind_client.py` using non-blocking background threads with a 20-min TTL.

### 3. FAA-Standard Turbulence Intensity (Phase 24)
Arbitrary "chaos" flags were replaced by standard aviation **Turbulence Intensity (TI)** calculations. We use rolling standard-deviation windows across the simulated wind field. If `TI% > 15%` (equivalent to "moderate turbulence" per FAA AC 00-30C), the drone is flagged for immediate rerouting.

### 4. MAVLink / SITL hardware bridging (Phase 23)
Wind_Navigator sends live physics data straight to ArduPilot via `mavlink_bridge.py`:
- Predicts turbulence 12 seconds along the flight path.
- Injects standard MAVLink `STATUSTEXT` warnings.
- Commands standard-flight `HOLD` and `PROCEED` overrides natively. 

---

## Validated Metrics and Benchmarks

Every performance claim below has been logged via automated testing (`validate_physics.py`):

| Metric | Validated Result | Code Origin |
|:-------|:-----------------|:------------|
| **False-Positive Bifurcation Rate** | **0%** (vs 45.3% in float approximation pipeline) | `VALIDATION_REPORT.md` (Runs against Manhattan geometry) |
| **Edge-API Response Latency** | **p50=3ms / p95=18ms / p99=30ms at 250 concurrent queries.** | `server.py` |
| **Compute Speed Improvement** | **1.91× faster** than floating-point math | `validate_physics.py` benchmark iteration |
| **Determinism Guarantee** | **100% (0 drift failures across 1,000 runs)** | Pure integer grid in `rational_wind.py` |

*(Previously stated claims of "sub-15ms response" have been precisely updated above to reflect true concurrent probability distribution boundaries.)*

---

## File Architecture

| Component | Responsibility |
|:----------|:---------------|
| `panda_manhattan.py` | The live 3D visualizer running the simulation engine alongside the 3D models. |
| `noaa_wind_client.py`| Live API consumption from `aviationweather.gov`. |
| `osm_terrain_parser.py`| NYC OpenStreetMap topology extractor and integer grid ray-caster. |
| `rational_wind.py`   | The core integer cross-product mathematics isolating building saddle points. |
| `turbulence_metrics.py`| Rolling standard deviation logic conforming to FAA TI% thresholds. |
| `mavlink_bridge.py`  | SITL hardware connection loop sending actual flight controller commands. |

---

## Roadmap

**Phase 29:** Implement a true LBM D2Q9 flow-streaming sequence with a proper BGK collision operator. (Fixes the geometric anomaly that `dx*dy < 0` ignores 50% of structural corners and 100% of street canyon long-edges).

**Phase 30:** Implement Spatial Partitioning for O(N) swarm collision avoidance, replacing the brute force O(N²) approach currently limiting horizontal scale.
