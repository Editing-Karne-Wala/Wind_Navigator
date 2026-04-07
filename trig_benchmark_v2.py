import math
import time
import random
from fractions import Fraction
import csv

# ── CLASSICAL TRIGONOMETRY ─────────────────────────────────────
def on_segment(px, py, qx, qy, rx, ry):
    if (rx <= max(px, qx) and rx >= min(px, qx) and
            ry <= max(py, qy) and ry >= min(py, qy)):
        return True
    return False

def cross_product_classical(ax, ay, bx, by):
    return ax * by - ay * bx

def classical_intersect(ax, ay, bx, by, cx, cy, dx, dy):
    abx, aby = bx - ax, by - ay
    cdx, cdy = dx - cx, dy - cy
    
    d1 = cross_product_classical(cdx, cdy, ax - cx, ay - cy)
    d2 = cross_product_classical(cdx, cdy, bx - cx, by - cy)
    d3 = cross_product_classical(abx, aby, cx - ax, cy - ay)
    d4 = cross_product_classical(abx, aby, dx - ax, dy - ay)
    
    epsilon = 1e-10
    
    if ((d1 > epsilon and d2 < -epsilon) or 
        (d1 < -epsilon and d2 > epsilon)) and \
       ((d3 > epsilon and d4 < -epsilon) or 
        (d3 < -epsilon and d4 > epsilon)):
        return True
    
    if abs(d1) < epsilon and on_segment(cx, cy, dx, dy, ax, ay): return True
    if abs(d2) < epsilon and on_segment(cx, cy, dx, dy, bx, by): return True
    if abs(d3) < epsilon and on_segment(ax, ay, bx, by, cx, cy): return True
    if abs(d4) < epsilon and on_segment(ax, ay, bx, by, dx, dy): return True
        
    return False

# ── RATIONAL TRIGONOMETRY ──────────────────────────────────────
def rational_intersect(ax, ay, bx, by, cx, cy, dx, dy):
    # Convert to exact rationals
    ax, ay, bx, by = Fraction(ax), Fraction(ay), Fraction(bx), Fraction(by)
    cx, cy, dx, dy = Fraction(cx), Fraction(cy), Fraction(dx), Fraction(dy)
    
    d1 = (dx-cx)*(ay-cy) - (dy-cy)*(ax-cx)
    d2 = (dx-cx)*(by-cy) - (dy-cy)*(bx-cx)
    d3 = (bx-ax)*(cy-ay) - (by-ay)*(cx-ax)
    d4 = (bx-ax)*(dy-ay) - (by-ay)*(dx-ax)
    
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    
    if d1 == 0 and min(cx,dx) <= ax <= max(cx,dx) and min(cy,dy) <= ay <= max(cy,dy): return True
    if d2 == 0 and min(cx,dx) <= bx <= max(cx,dx) and min(cy,dy) <= by <= max(cy,dy): return True
    if d3 == 0 and min(ax,bx) <= cx <= max(ax,bx) and min(ay,by) <= cy <= max(ay,by): return True
    if d4 == 0 and min(ax,bx) <= dx <= max(ax,bx) and min(ay,by) <= dy <= max(ay,by): return True
    
    return False

# ── BENCHMARK RUNNER ───────────────────────────────────────────
def run_benchmark(n=10000):
    print(f"[*] Running performance benchmark: {n} iterations...")
    
    # Pre-generate random segments
    datasets = []
    for _ in range(n):
        datasets.append([random.randint(-1000, 1000) for _ in range(8)])
    
    # 1. Benchmark Classical
    start_time = time.time()
    results_classical = []
    for d in datasets:
        results_classical.append(classical_intersect(*d))
    classical_time = time.time() - start_time
    
    # 2. Benchmark Rational
    start_time = time.time()
    results_rational = []
    for d in datasets:
        results_rational.append(rational_intersect(*d))
    rational_time = time.time() - start_time
    
    # 3. Compare Precision (Divergence)
    divergences = 0
    for c, r in zip(results_classical, results_rational):
        if c != r: divergences += 1
        
    print("\n=== BENCHMARK RESULTS ===")
    print(f"Classical (Floating Point): {classical_time:.4f}s")
    print(f"Rational (Exact Fraction): {rational_time:.4f}s")
    print(f"Speed Factor: {rational_time/classical_time:.2f}x slower (Price of Perfection)")
    print(f"Divergence Count: {divergences} / {n} cases where Classical was 'wrong' (Approximation Tax)")
    
    return {
        "classical": classical_time,
        "rational": rational_time,
        "divergences": divergences
    }

if __name__ == "__main__":
    run_benchmark(10000)
