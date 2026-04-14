# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR -- Phase 34: Cross-Platform Determinism Test
===========================================================
Closing Gap D4: "Cross-platform determinism not tested."

This script forces the D2Q9 Integer physics core to run an exact 
number of deterministic collisions, dumping the final multi-dimensional 
memory matrix into a cryptographic SHA-256 hash.

If this SHA-256 hash matches across Windows (x86_64), Ubuntu (x86_64),
and macOS (ARM64 Apple Silicon M-Series), it physically proves that 
the engine is immune to IEEE 754 floating-point hardware drift.
"""

import hashlib
import json
import time
from lbm_d2q9_core import IntegerLBM

def run_determinism_audit():
    print("="*60)
    print("Phase 34: Universal Architecture Determinism Audit")
    print("="*60)
    
    # 1. Setup a standard validation matrix (must be tightly controlled)
    W, H = 40, 40
    terrain = [[0 for _ in range(W)] for _ in range(H)]
    
    # Add an asymmetrical obstacle to force complex turbulence
    for y in range(15, 25):
        for x in range(10, 15):
            terrain[y][x] = 1
    
    print(f"[1] Allocating standard D2Q9 grid ({W}x{H})")
    lbm = IntegerLBM(W, H, terrain)
    
    # 2. Burn-in Phase
    FRAMES = 250
    print(f"[2] Executing {FRAMES} integer lattice collisions...")
    
    t0 = time.perf_counter()
    for _ in range(FRAMES):
        # Strict inputs across all hardware
        lbm.simulate_step(tau_omega=120, inlet_u=5000, inlet_v=0)
    t1 = time.perf_counter()
    
    exec_time = (t1 - t0) * 1000
    print(f"    Burn-in complete: {exec_time:.2f} ms")
    
    # 3. Memory Extraction & Cryptographic Hashing
    print("[3] Initiating memory serialization...")
    # Serialize the exact raw population data of the entire lattice
    # f_in is structured as: H x W x 9 (array of 9 integers)
    
    # We must use strict separators to prevent JSON artifact differences across OS
    serialized_memory = json.dumps(lbm.f_in, separators=(',', ':'))
    
    print("[4] Executing SHA-256 computation over resulting memory state...")
    sha_signature = hashlib.sha256(serialized_memory.encode('utf-8')).hexdigest()
    
    print("\n[DETERMINISM OUPUT]")
    print(f"  Matrix Bytes: {len(serialized_memory)}")
    print(f"  SHA-256 Hash: {sha_signature}")
    print("="*60)

if __name__ == "__main__":
    run_determinism_audit()
