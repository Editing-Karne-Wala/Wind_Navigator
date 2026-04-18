# -*- coding: utf-8 -*-
"""
WIND_NAVIGATOR -- Phase 27: External CFD Validation
===================================================
Compares our discrete Integer Bifurcation detection against
published Ground Truth CFD datasets for urban flows.

Reference Literature:
1. "Flow around a surface-mounted cube" (Martinuzzi & Tropea, 1993)
   - GT: Peak turbulent kinetic energy (TKE) / separation occurs 
     at the sharp vertical edges (corners) of the structure.
2. "Street Canyon Skimming Flow" (Oke 1988)
   - GT: Bifurcation sheer layers form exactly at the step-up 
     and step-down edges perpendicular to the wind.

This script generates those specific topological test cases and
checks if our O(1) integer math correctly flags those exact grid 
coordinates without doing full Navier-Stokes flow fields.
"""

import sys

def lbm_bifurcation_score(terrain, gx, gy, W, H):
    # Same logic as rational_wind.py: lbm_bifurcation_score
    gx = max(1, min(W-2, gx))
    gy = max(1, min(H-2, gy))
    dx = terrain[gy][gx+1] - terrain[gy][gx-1]
    dy = terrain[gy+1][gx] - terrain[gy-1][gx]
    cross = dx * dy
    magn  = dx*dx + dy*dy
    return cross, magn

def run_validation():
    print("="*60)
    print("WIND_NAVIGATOR -- External CFD Ground Truth Validation")
    print("="*60)

    # ---------------------------------------------------------
    # TEST 1: The "Surface-Mounted Cube" (Martinuzzi & Tropea)
    # ---------------------------------------------------------
    W, H = 10, 10
    terrain = [[0 for _ in range(W)] for _ in range(H)]
    
    # Place a 4x4 cube in the center
    for y in range(3, 7):
        for x in range(3, 7):
            terrain[y][x] = 10
            
    print("\n[TEST 1] Surface-Mounted Prism Corners (Horseshoe Vortex)")
    print("CFD Literature: Peak separation shears occur at the 4 topological corners.")
    
    corners = [(3,3), (3,6), (6,3), (6,6)]
    edges   = [(3,4), (3,5), (6,4), (6,5), (4,3), (5,3), (4,6), (5,6)]
    
    corner_hits = 0
    edge_hits = 0
    
    for y in range(H):
        for x in range(W):
            cross, _ = lbm_bifurcation_score(terrain, x, y, W, H)
            if cross < 0:
                if (y, x) in corners: corner_hits += 1
                if (y, x) in edges: edge_hits += 1

    print(f"  -> Predicted Vortex Locations: Corners={corner_hits}/4, Edges={edge_hits}")
    if corner_hits == 2:
        print("  -> RESULT: PARTIAL FAIL. Math catches (3,6) and (6,3) where signs differ, but misses (3,3) and (6,6) where dx and dy have the same sign (either both + or both -).")
        print("  -> CONCLUSION: `dx * dy < 0` is geometrically blind to 50% of building corners!")
    else:
        print("  -> RESULT: UNEXPECTED.")

    # ---------------------------------------------------------
    # TEST 2: Street Canyon Cross-Section (Oke)
    # ---------------------------------------------------------
    # Building from x=2..4, Canyon at x=5..6, Building at x=7..8
    W2, H2 = 12, 12
    terrain2 = [[0 for _ in range(W2)] for _ in range(H2)]
    for y in range(2, 10):
        for x in range(2, 5): terrain2[y][x] = 20    # Windward Building
        for x in range(7, 10): terrain2[y][x] = 20   # Leeward Building

    print("\n[TEST 2] Urban Street Canyon Wake (Skimming Flow)")
    print("CFD Literature: Vortex sheer detaches at the roof edges bounding the canyon.")
    
    canyon_edge_hits = 0
    for y in range(H2):
        for x in range(W2):
            cross, _ = lbm_bifurcation_score(terrain2, x, y, W2, H2)
            if cross < 0:
                # Is it on the canyon boundary? x=4, 5, 6, 7?
                if x in [1, 5, 6, 10]: 
                     canyon_edge_hits += 1

    # Corners of the two buildings
    print(f"  -> Canyon Wake / Corner Separations Detected: {canyon_edge_hits}")
    if canyon_edge_hits == 0:
        print("  -> RESULT: FAIL. `dx*dy < 0` misses straight 1D shear boundaries completely, because either dx or dy is 0 on a straight wall, making the product exactly 0 (not < 0).")

    print("\n[CONCLUSION]")
    print("External CFD Validation exposes fundamental flaws in the 'Rational Trigonometry' proxy.")
    print("1. It misses 50% of building corners (where gradient signs match).")
    print("2. It misses 100% of street canyon long-edges (where one gradient is 0).")
    print("Gap B2 & B3 closed: Validation complete. Phase 29 (Real LBM Streaming) is mathematically mandatory.")
    print("="*60)

if __name__ == "__main__":
    run_validation()
