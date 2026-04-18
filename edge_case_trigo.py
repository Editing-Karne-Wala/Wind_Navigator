from fractions import Fraction
import math

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
    if ((d1 > epsilon and d2 < -epsilon) or (d1 < -epsilon and d2 > epsilon)) and \
       ((d3 > epsilon and d4 < -epsilon) or (d3 < -epsilon and d4 > epsilon)):
        return True
    return False

def rational_intersect(ax, ay, bx, by, cx, cy, dx, dy):
    ax, ay, bx, by = Fraction(ax), Fraction(ay), Fraction(bx), Fraction(by)
    cx, cy, dx, dy = Fraction(cx), Fraction(cy), Fraction(dx), Fraction(dy)
    d1 = (dx-cx)*(ay-cy) - (dy-cy)*(ax-cx)
    d2 = (dx-cx)*(by-cy) - (dy-cy)*(bx-cx)
    d3 = (bx-ax)*(cy-ay) - (by-ay)*(cx-ax)
    d4 = (bx-ax)*(dy-ay) - (by-ay)*(dx-ax)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return False

# ── EXTREME EDGE CASE TEST ────────────────────────────────────
def test_edge_case():
    print("[*] Testing 'The Breaking Point' (Extreme Precision)...")
    
    # CASE: Intersection point is 1e-12 away from the line segment
    # This is SMALLER than the epsilon (1e-10), meaning Classical WILL MISS IT.
    
    # Segment 1: Fixed horizontal line
    ax, ay = 0.0, 0.0
    bx, by = 1.0, 0.0
    
    # Segment 2: Intersecting at exactly 0.5, but mathematically 
    # slightly shifted by 1e-12 in coordinates
    cx, cy = 0.5, -0.5
    dx, dy = 0.5, 1e-12
    
    # This DOES intersect at Y=0, X=0.5. 
    # But Classical epsilon = 1e-10 might treat d1, d2 as zero or fail thresholds.
    
    c_res = classical_intersect(ax, ay, bx, by, cx, cy, dx, dy)
    r_res = rational_intersect(ax, ay, bx, by, cx, cy, dx, dy)
    
    print(f"\nCoordinates: A(0,0), B(1,0) | C(0.5, -0.5), D(0.5, 1e-12)")
    print(f"Classical Intersection: {c_res}")
    print(f"Rational Intersection:  {r_res}")
    
    if c_res != r_res:
        print("\n[!!!] FAILED! The Approximation Tax just cost you a collision.")
        print("This is exactly why your physics engine would drift or leak over time.")
    else:
        print("\nClassical survived this one (likely d2 was exactly zero). Let's try harder.")

test_edge_case()
