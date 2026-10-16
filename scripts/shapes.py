"""Path helpers for shapes that need rounded corners but are used as fills or clips
(a round-join stroke cannot round those, e.g. the accent shape).

    python3 scripts/shapes.py sector CX CY R A0 A1 FILLET
prints an SVG path for a pie slice centred at (CX, CY), radius R, from angle A0 to A1
(degrees, clockwise from 3 o'clock), with all three corners rounded by FILLET.

    python3 scripts/shapes.py bubble X Y W H R TAIL [left|right]
prints an SVG path for a speech bubble on its centre line: a W x H rounded rectangle at (X, Y),
corner radius R, whose bottom-left (or bottom-right) corner runs on straight down TAIL past the
bottom edge to a tip. The tip is a 55 deg wedge (the stroke's round join rounds it); the tail's
slanted edge meets the bottom edge with a concave arc r 52, so the stroke keeps r 26 there.
Use the same path for the line and, when the bubble is the accent, for #accent-shape.
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

def bubble(x, y, w, h, r, tail, side="left", tip=55.0, rf=52.0):
    """Speech bubble on its centre line; the tail hangs from the bottom-left (or bottom-right) corner."""
    b = y + h
    a = math.radians(tip)
    jx = tail * math.tan(a)                     # where the slanted edge meets the bottom edge, from the side
    tl = rf * math.tan((math.pi / 2 - a) / 2)   # tangent length of the concave arc
    if r + jx + tl > w - r:
        raise ValueError(f"bubble too narrow for this tail: W must exceed {2 * r + jx + tl:.0f}")
    # left-tail points (x measured from the left side); mirrored for a right tail
    pts = {"s": (0, r), "c1": (r, 0), "c2": (w - r, 0), "c3": (w, r), "c4": (w, h - r), "c5": (w - r, h),
           "j2": (jx + tl, h), "j1": (jx - tl * math.sin(a), h + tl * math.cos(a)), "tip": (0, h + tail)}
    mx = (lambda u: x + w - u) if side == "right" else (lambda u: x + u)
    P = {k: (mx(u), y + v) for k, (u, v) in pts.items()}
    cw, ccw = (0, 1) if side == "right" else (1, 0)   # sweep flags flip when mirrored
    f = lambda k: f"{P[k][0]:.1f} {P[k][1]:.1f}"
    return (f"M {f('s')} A {r:g} {r:g} 0 0 {cw} {f('c1')} H {P['c2'][0]:.1f} A {r:g} {r:g} 0 0 {cw} {f('c3')} "
            f"V {P['c4'][1]:.1f} A {r:g} {r:g} 0 0 {cw} {f('c5')} H {P['j2'][0]:.1f} "
            f"A {rf:g} {rf:g} 0 0 {ccw} {f('j1')} L {f('tip')} Z")

if __name__ == "__main__":
    if len(sys.argv) == 8 and sys.argv[1] == "sector":
        print(rounded_sector(*map(float, sys.argv[2:])))
    elif len(sys.argv) in (8, 9) and sys.argv[1] == "bubble":
        side = sys.argv[8] if len(sys.argv) == 9 else "left"
        if side not in ("left", "right"):
            sys.exit("side must be left or right")
        try:
            print(bubble(*map(float, sys.argv[2:8]), side=side))
        except ValueError as e:
            sys.exit(str(e))
    else:
        print(__doc__)
