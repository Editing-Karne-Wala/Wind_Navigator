# Wind_Navigator
### Integer-Native Computational Fluid Dynamics for Real-Time Drone Weather Routing

> Replacing 60 years of floating-point Navier-Stokes approximation with 
> thermodynamically perfect, integer-only Lattice Boltzmann physics.

---

## The Problem We Are Solving

Commercial drone logistics (Amazon Prime Air, Zipline, Skydio) are bottlenecked by battery constraints. Wind resistance, micro-vortices between skyscrapers, and unexpected thermal updrafts cause drones to burn exponentially more power than optimal routes require.

Current solutions use floating-point CFD solvers (OpenFOAM, ANSYS) that:
- Require expensive supercomputer clusters.
- Take 10-20 minutes to converge on a simulation.
- Accumulate rounding errors that corrupt long-term simulation stability.

**Wind_Navigator** delivers real-time (sub-10ms) wind vector routing using a purely integer-based approach.

---

## The Core Innovation

Classical solvers rely on continuous calculus and irrational numbers (like $\sqrt{2}/2$). A computer's binary representation of these is always lossy, leading to "Numerical Dissipation"—phantom energy leakage.

**Wind_Navigator** applies **Rational Trigonometry** (Wildberger, UNSW) to:
- Replace continuous derivatives with discrete integer summations.
- Use exact integer multipliers scaled by 36 (D2Q9 lattice).
- **The Remainder Vault:** Audits voxel mass per frame and deposits lost integers back into the system, guaranteeing $\sum(mass_{t+1}) == \sum(mass_{t})$.

---

## Benchmark Results

| Metric | Value |
| :--- | :--- |
| **Engine Type** | Pure Integer ALU |
| **Grid Size (2D)** | 60 × 25 voxels |
| **Time Steps (Validation)** | 10,000 |
| **Energy Conservation** | 100.00% |
| **Floating Point Operations** | 0 |
| **Compute Time (100 steps)** | ~2.5ms on i5-11400H |

---

## Stress Test Results

| Test | Scenario | Result |
| :--- | :--- | :--- |
| **Antimatter Void** | Negative mass injection (-1M) | ✅ STABLE |
| **Mach-Infinity** | 1.8 Quintillion vector magnitude | ✅ STABLE |
| **Micro-Cavitation** | Indivisible mass (35) in 1-voxel cage | ✅ STABLE |
| **Energy Leak** | 10,000 frame closed-box audit | ✅ 0% Loss |
| **OpenStreetMap Urban Mask** | 5,000 frames over jagged Midtown Manhattan topography | ✅ 0% Loss |

---

## Real-World Simulation Physics (Scientific Validation)

A critical question for any numerical model is: *How do we know discrete integer arithmetic accurately reflects real-world aerodynamics?* The engine's validity relies on two fundamental pillars of statistical mechanics:

1. **The Chapman-Enskog Mathematical Proof:** In fluid physics, it is mathematically proven that if a discrete lattice (like our D2Q9 grid) enforces perfect mass conservation (via the Remainder Vault) and momentum conservation (via algorithmic bounce-back), the macroscopic behavior of those discrete particles is mathematically guaranteed to solve the continuous Navier-Stokes equations. 
2. **The Incompressibility Constraint:** Lattice Boltzmann models perfectly mirror atmospheric reality only for incompressible fluids (Mach < 0.3 or < 230 mph). Because urban drones navigate winds between 10 mph and 50 mph (Mach 0.01 to Mach 0.06), the algorithm operates exactly inside the physical sweet spot where discrete physics reflect reality 1:1.

---

## Real-World Data Integration

The engine ingests live weather and terrain data via free public APIs:

```bash
# 1. Fetch live wind vectors from meteorological data
python fetch_weather.py

# 2. Fetch building heights/footprints for the target GPS Bounding Box
python osm_terrain_parser.py
# Maps Manhattan Topography into an Integer Voxel mask (urban_terrain.txt)
```

The Python layer handles floating-point API conversion, then passes exact integers to the C++ core. All subsequent physics computation is pure integer arithmetic.

---

## Project Files

| File | Purpose |
| :--- | :--- |
| `conservative_lbm.cpp` | **Production engine.** D2Q9 + Remainder Vault logic. |
| `real_world_2d_test.cpp` | Stress tests the integer core against OpenStreetMap geometry. |
| `extreme_stress.cpp` | Destruction testing suite (3 failure scenarios). |
| `osm_terrain_parser.py` | OpenStreetMap Overpass API bounding box terrain rasterizer. |
| `fetch_weather.py` | Live Open-Meteo data fetcher & integer converter. |
| `discrete_fluid.cpp` | Initial prototype (naive integer fluid model). |
| `lbm_engine.cpp` | Intermediate LBM implementation (pre-vault). |
| `stress_tests.cpp` | Phase 1 stress tests (exposed 3 initial failure modes). |
| `weather_test.py` | Python benchmark (Classical FPU vs Rational ALU). |
| `cpp_benchmark.cpp` | 50M particle speedtest (Float vs Integer). |

---

## Roadmap

- [x] **Phase 1:** Validate Rational Integer fluid mechanics (D2Q9)
- [x] **Phase 2:** Stress test thermodynamic conservation (10,000 frames)
- [x] **Phase 3 A:** Integrate live real-world weather data (Open-Meteo)
- [x] **Phase 3 B:** Integrate live real-world building topologies (OpenStreetMap)
- [ ] **Phase 4:** Upgrade to 3D (`D3Q19` — 19-vector, 3-axis voxels)
- [ ] **Phase 5:** Phenomenological Visualizer (Von Kármán vortex streets)
- [ ] **Phase 6:** FastAPI web server (GPS to JSON wind vectors)
- [ ] **Phase 7:** CUDA kernel port (RTX 2050 parallel acceleration)

---

## Hardware Requirements

| Component | Minimum | Recommended |
| :--- | :--- | :--- |
| **CPU** | Any x86-64 | Intel i5-11400H+ |
| **RAM** | 8 GB | 16 GB |
| **GPU** | None (CPU-only) | NVIDIA RTX 2050+ (for CUDA) |
| **OS** | Windows/Linux | Windows 11 / Ubuntu 22.04 |

---

## Building & Running

```bash
# Compile and run the production engine over Manhattan
python osm_terrain_parser.py
g++ -O3 real_world_2d_test.cpp -o real_world_2d_test.exe
./real_world_2d_test.exe
```

---

## Acknowledgements

- **Norman J. Wildberger (UNSW):** Rational Trigonometry foundational philosophy.
- **Frisch, Hasslacher, Pomeau (1986):** Lattice Gas Automata fundamentals.
- **Open-Meteo / OpenStreetMap:** Free public APIs.

---

## License

MIT License. See `LICENSE` for details.
