"""Path helpers for shapes that need rounded corners but are used as fills or clips
(a round-join stroke cannot round those, e.g. the accent shape).

    python3 scripts/shapes.py sector CX CY R A0 A1 FILLET
prints an SVG path for a pie slice centred at (CX, CY), radius R, from angle A0 to A1
(degrees, clockwise from 3 o'clock), with all three corners rounded by FILLET.
"""
import math, sys

def rounded_sector(cx, cy, R, a0, a1, rho):
    if a1 <= a0:
        a1 += 360
    th = math.radians(a1 - a0)
    u0 = (math.cos(math.radians(a0)), math.sin(math.radians(a0)))
    u1 = (math.cos(math.radians(a1)), math.sin(math.radians(a1)))
    n0 = (-u0[1], u0[0])      # inward normal of the a0 edge
    n1 = (u1[1], -u1[0])      # inward normal of the a1 edge
    d = rho / math.tan(th / 2)                  # apex fillet tangent distance
    t = math.sqrt((R - rho) ** 2 - rho ** 2)    # rim fillet tangent point on each edge
    P = lambda s, u, k=0, n=(0, 0): (cx + s * u[0] + k * n[0], cy + s * u[1] + k * n[1])
    p0, p1 = P(d, u0), P(d, u1)
    q0, q1 = P(t, u0), P(t, u1)
    c0, c1 = P(t, u0, rho, n0), P(t, u1, rho, n1)
    s0 = (cx + (c0[0] - cx) * R / (R - rho), cy + (c0[1] - cy) * R / (R - rho))
    s1 = (cx + (c1[0] - cx) * R / (R - rho), cy + (c1[1] - cy) * R / (R - rho))
    f = lambda p: f"{p[0]:.1f} {p[1]:.1f}"
    large = 1 if (a1 - a0) > 180 else 0
    return (f"M {f(p0)} L {f(q0)} A {rho} {rho} 0 0 1 {f(s0)} "
            f"A {R} {R} 0 {large} 1 {f(s1)} A {rho} {rho} 0 0 1 {f(q1)} "
            f"L {f(p1)} A {rho} {rho} 0 0 1 {f(p0)} Z")

if __name__ == "__main__":
    if len(sys.argv) == 8 and sys.argv[1] == "sector":
        print(rounded_sector(*map(float, sys.argv[2:])))
    else:
        print(__doc__)
