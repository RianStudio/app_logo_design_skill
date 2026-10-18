#!/usr/bin/env python3
"""Path helpers for a Rian line icon. The body is a line drawing: these commands print the CENTRE LINE of each
stroke (render it with the body's stroke, 60 final px, round caps and joins). The one accent is a filled shape:
sector, segment, ring, capsule, aiband and minus print filled outlines for it. Angles are degrees clockwise from
3 o'clock (SVG y-down), all numbers are source units. Needs Python 3.9 or later, nothing else.

Centre lines (body):

    python3 scripts/shapes.py arc CX CY R A0 A1
an open circular arc from A0 clockwise to A1 (a dial, a loop, a hand's sweep).

    python3 scripts/shapes.py rrect X Y W H R
rounded rectangle at (X, Y), W x H, corner radius R (R = H / 2 or W / 2 gives a capsule). Cards, screens,
pages, frames. As a filled accent the same command works with --grow.

    python3 scripts/shapes.py bubble X Y W H R TAIL [left|right] [--angle 55] [--tip-r 24] [--concave 56]
speech bubble: a W x H rounded rectangle at (X, Y), corner radius R (at most H / 2), whose left (or right) side
runs on straight down to a tail tip TAIL below the bottom edge; the tip is rounded by TIP_R and meets the bottom
edge with a concave arc of radius CONCAVE.

    python3 scripts/shapes.py poly "X1,Y1 X2,Y2 X3,Y3 ..." [--r 24 | --radii R1,R2,...] [--open] [--grow 0]
polygon through the corner points, each corner rounded by its radius (0 = sharp; the round join still rounds
the stroke's outside). --open draws a polyline instead: the first and last points are the line's ends (round
caps) and only the inner corners are rounded. Arrows, chevrons, staircases, mountain ridges, chamfered cards.

    python3 scripts/shapes.py play CX CY H [--r 24]
the video mark's centre line: an equilateral play triangle pointing right, its upright side H long, its
centroid at (CX, CY), corners rounded by R. Stroked, its hole is the mark: H ≥ 240 ÷ k, so the hole still shows
at 40 px (it measures about H / 1.7).

Filled shapes (the accent):

    python3 scripts/shapes.py capsule X1 Y1 X2 Y2 W
a stadium W wide whose round ends are centred on (X1, Y1) and (X2, Y2): a beam, a bar, a band.

    python3 scripts/shapes.py aiband X1 Y1 X2 Y2 [--stroke 60] [--gap 60] [--width 80] [--inset 0]
the AI mark. (X1, Y1) -> (X2, Y2) is the outline's 45 deg chamfer across its lower right corner (its centre
line, running "/": from the lower left point to the upper right one). Prints the band: a capsule WIDTH wide on
the outer side of the chamfer, its edge GAP clear of the line's edge (STROKE / 2 + GAP + WIDTH / 2 from the
centre line), as long as the chamfer less INSET at each end.

    python3 scripts/shapes.py sector CX CY R A0 A1 FILLET
pie slice centred at (CX, CY), radius R, from A0 to A1, all three corners rounded by FILLET.

    python3 scripts/shapes.py ring CX CY R_OUT R_IN A0 A1 [--fillet 0]
filled ring segment from A0 to A1 (clockwise), corners rounded by FILLET: a progress arc, a loop arrow's body.

    python3 scripts/shapes.py segment CX CY R A D [--fillet 0]
circular segment: the part of the disc on the side of direction A beyond a chord at distance D from the centre
(a sun behind a cloud: A = -45 keeps the upper right part, the chord runs top left to bottom right).

    python3 scripts/shapes.py minus "PATH_A" "PATH_B"
filled outline A with outline B taken out, as one path of lines and arcs: an accent kept clear of a line it
would touch (B = that line's shape grown by STROKE / 2 + 60, e.g. rrect --grow). Both may use M L H V A Z
(circular arcs only); keep their edges from running along each other.

--k K (any command): the drawing's scale k (the #subject transform). Every number that is a house rule in
final pixels is divided by k: --r, --radii, --grow, --tip-r, --concave, FILLET, --fillet, capsule's W, and
aiband's --stroke, --gap, --width and --inset. Coordinates, radii of circles and play's H stay source units.
"""
import argparse
import math
import re
import sys


def f(p):
    return f"{p[0]:.1f} {p[1]:.1f}"


def unit(a):
    t = math.radians(a)
    return (math.cos(t), math.sin(t))


def ang(c, p):
    return math.degrees(math.atan2(p[1] - c[1], p[0] - c[0])) % 360


# ---------------------------------------------------------------- tangent chain (shared by most shapes)

EPS = 1e-3                                    # shorter lines and arcs are tangency round-off, not edges


def _dedupe(circles):
    """Drop a circle that repeats its neighbour (a capsule's two corner circles on one end coincide)."""
    out = []
    for c in circles:
        if out and math.hypot(c[0] - out[-1][0], c[1] - out[-1][1]) < 1e-9 and abs(c[2] - out[-1][2]) < 1e-9:
            continue
        out.append(c)
    while len(out) > 1 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-9 \
            and abs(out[0][2] - out[-1][2]) < 1e-9:
        out.pop()
    return out


def chain(circles):
    """Closed outline through a ring of circles, clockwise on screen (y down).
    Each item is (cx, cy, s): s > 0 the outline wraps the circle (a convex corner of radius s), s < 0 the circle
    sits outside the shape (a concave corner of radius -s), s = 0 a sharp corner at (cx, cy). Consecutive
    circles are joined by their common tangent, so the outline is smooth wherever s != 0. A circle that repeats
    its neighbour is merged with it (capsule ends)."""
    circles = _dedupe(circles)
    n = len(circles)
    if n < 2:
        raise ValueError("an outline needs at least two distinct corner circles")
    tangents = []
    for i in range(n):
        ax, ay, sa = circles[i]
        bx, by, sb = circles[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        if L < 1e-9:
            raise ValueError(f"corner circles {i} and {(i + 1) % n} share a centre but not a radius "
                             f"({sa:g} and {sb:g})")
        ux, uy = dx / L, dy / L
        wx, wy = uy, -ux                      # outward side when travelling clockwise
        c = (sa - sb) / L
        if c > 1 + 1e-6 or c < -1 - 1e-6:
            raise ValueError(f"no common tangent between corner circles {i} and {(i + 1) % n}")
        c = max(-1.0, min(1.0, c))
        s = math.sqrt(1 - c * c)
        nx, ny = c * ux + s * wx, c * uy + s * wy
        tangents.append(((ax + sa * nx, ay + sa * ny), (bx + sb * nx, by + sb * ny)))
    start = tangents[-1][1]
    d = [f"M {f(start)}"]
    cur = start
    for i, (cx, cy, s) in enumerate(circles):
        out = tangents[i][0]
        if abs(s) > 1e-9 and math.hypot(out[0] - cur[0], out[1] - cur[1]) > EPS:
            a_in, a_out = ang((cx, cy), cur), ang((cx, cy), out)
            span = (a_out - a_in) % 360 if s > 0 else (a_in - a_out) % 360
            d.append(f"A {abs(s):g} {abs(s):g} 0 {1 if span > 180 else 0} {1 if s > 0 else 0} {f(out)}")
        nxt = tangents[i][1]
        if i < n - 1 and math.hypot(nxt[0] - out[0], nxt[1] - out[1]) > EPS:
            d.append(f"L {f(nxt)}")
        cur = nxt
    if d[-1] == f"L {f(start)}":
        d.pop()                               # the closing line is the Z
    return " ".join(d) + " Z"


# ---------------------------------------------------------------- shapes

def rounded_sector(cx, cy, R, a0, a1, rho):
    """Pie slice from a0 to a1 with all three corners rounded by rho."""
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
    large = 1 if (a1 - a0) > 180 else 0
    return (f"M {f(p0)} L {f(q0)} A {rho:g} {rho:g} 0 0 1 {f(s0)} "
            f"A {R:g} {R:g} 0 {large} 1 {f(s1)} A {rho:g} {rho:g} 0 0 1 {f(q1)} "
            f"L {f(p1)} A {rho:g} {rho:g} 0 0 1 {f(p0)} Z")


def ring(cx, cy, R, r, a0, a1, gap=0.0, fillet=0.0):
    """Ring segment a0 -> a1 (clockwise), outer radius R, inner r. Ends are lines parallel to the seam radius,
    gap / 2 into the segment; fillet rounds the four corners."""
    if not 0 < r < R:
        raise ValueError("need 0 < R_IN < R_OUT")
    if a1 <= a0:
        a1 += 360
    if a1 - a0 >= 360:
        raise ValueError("a ring segment spans less than 360 deg")
    half, fl = gap / 2, fillet
    if 2 * fl > R - r:
        raise ValueError(f"fillet too large for a ring {R - r:g} thick")
    u0, u1 = unit(a0), unit(a1)
    n0 = (-u0[1], u0[0])      # into the segment at the a0 end
    n1 = (u1[1], -u1[0])      # into the segment at the a1 end

    def corner(u, n, rad, outer):
        off = half + fl
        dist = rad - fl if outer else rad + fl
        if dist <= off:
            raise ValueError("gap too wide for this radius")
        t = math.sqrt(dist * dist - off * off)
        return (cx + t * u[0] + off * n[0], cy + t * u[1] + off * n[1], fl)

    return chain([(cx, cy, R), corner(u1, n1, R, True), corner(u1, n1, r, False),
                  (cx, cy, -r), corner(u0, n0, r, False), corner(u0, n0, R, True)])


def segment(cx, cy, R, a, dist, fillet=0.0):
    """The part of the disc on the side of direction a beyond a chord at distance dist from the centre."""
    if not -R < dist < R:
        raise ValueError("the chord must cross the circle: -R < D < R")
    n = unit(a)
    t = (-n[1], n[0])
    fl = fillet

    def corner(sign):
        e = dist + fl
        h2 = (R - fl) ** 2 - e * e
        if h2 <= 0:
            raise ValueError("fillet too large for this segment")
        h = math.sqrt(h2)
        return (cx + e * n[0] + sign * h * t[0], cy + e * n[1] + sign * h * t[1], fl)

    return chain([(cx, cy, R), corner(1), corner(-1)])


def rrect(x, y, w, h, r, grow=0.0):
    """Rounded rectangle, optionally offset outwards by grow."""
    if w <= 0 or h <= 0:
        raise ValueError("W and H must be positive")
    if r < 0 or r > min(w, h) / 2 + 1e-9:
        raise ValueError(f"R must be between 0 and {min(w, h) / 2:g} (half the shorter side: a capsule)")
    r = min(r, min(w, h) / 2)
    return chain([(x + r, y + r, r + grow), (x + w - r, y + r, r + grow),
                  (x + w - r, y + h - r, r + grow), (x + r, y + h - r, r + grow)])


def bubble(x, y, w, h, r, tail, side="left", angle=55.0, tip_r=24.0, concave=56.0, grow=0.0):
    """Speech bubble with a tail under its left (or right) side, as one filled outline; grow offsets it."""
    a = math.radians(angle)
    rho, rf = tip_r, concave
    if r > h / 2 + 1e-9 or r > w / 2 + 1e-9:
        raise ValueError(f"R must be at most {min(w, h) / 2:g} (half of H = {h:g} and of W = {w:g}); "
                         f"R = H / 2 gives a capsule bubble")
    if tail <= rho:
        raise ValueError("TAIL must be longer than the tip radius")
    yt = y + h + tail - rho                     # tip circle centre: lowest point at y + h + tail
    nx, ny = math.cos(a), math.sin(a)           # outward normal of the slanted edge
    xj = x + rho + (ny * (yt - (y + h + rf)) + rf + rho) / nx   # concave circle centre on the bottom edge
    if xj > x + w - r - 1e-6:
        raise ValueError(f"bubble too narrow for this tail: W must exceed {xj - x + r:.0f}")
    if grow > rf:
        raise ValueError(f"--grow {grow:g} needs --concave of at least {grow:g}")
    circles = [(x + r, y + r, r), (x + w - r, y + r, r), (x + w - r, y + h - r, r),
               (xj, y + h + rf, -rf), (x + rho, yt, rho)]
    if side == "right":
        circles = [(2 * x + w - cx, cy, s) for cx, cy, s in reversed(circles)]
    return chain([(cx, cy, s + grow) for cx, cy, s in circles])


def _turn(p, v, q):
    """Cross product of the edges p -> v -> q: > 0 is a right turn on screen (y down), a convex corner of a
    clockwise outline."""
    return (v[0] - p[0]) * (q[1] - v[1]) - (v[1] - p[1]) * (q[0] - v[0])


def poly(pts, radii, grow=0.0):
    """Polygon with rounded corners (radius per corner, 0 = sharp), optionally offset outwards by grow."""
    n = len(pts)
    if n < 3:
        raise ValueError("a polygon needs at least three corners")
    if len(radii) != n:
        raise ValueError(f"{n} corners but {len(radii)} radii")
    area2 = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    if area2 < 0:                             # anticlockwise on screen: walk it the other way
        pts, radii = pts[::-1], radii[::-1]
    circles, reach = [], []
    for i in range(n):
        p, v, q = pts[i - 1], pts[i], pts[(i + 1) % n]
        u1 = (p[0] - v[0], p[1] - v[1])
        u2 = (q[0] - v[0], q[1] - v[1])
        l1, l2 = math.hypot(*u1), math.hypot(*u2)
        turn = _turn(p, v, q)
        if l1 < 1e-9 or l2 < 1e-9 or abs(turn) < 1e-9 * l1 * l2:
            raise ValueError(f"corner {i + 1} repeats a point or lies on a straight line")
        u1, u2 = (u1[0] / l1, u1[1] / l1), (u2[0] / l2, u2[1] / l2)
        half = math.acos(max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))) / 2
        b = (u1[0] + u2[0], u1[1] + u2[1])    # into the shape at a convex corner, out of it at a concave one
        lb = math.hypot(*b)
        b = (b[0] / lb, b[1] / lb)
        r = radii[i]
        reach.append(r / math.tan(half))      # where the arc meets each edge, measured from the corner
        if turn > 0:                          # convex
            d = r / math.sin(half)
            circles.append((v[0] + b[0] * d, v[1] + b[1] * d, r + grow))
        elif r - grow > 1e-9:                 # concave, still rounded after the offset
            d = r / math.sin(half)
            circles.append((v[0] + b[0] * d, v[1] + b[1] * d, -(r - grow)))
        else:                                 # concave, sharp: where the two offset edges meet
            d = grow / math.sin(half)
            circles.append((v[0] + b[0] * d, v[1] + b[1] * d, 0.0))
    for i in range(n):
        j = (i + 1) % n
        edge = math.hypot(pts[j][0] - pts[i][0], pts[j][1] - pts[i][1])
        if reach[i] + reach[j] > edge + 1e-6:
            raise ValueError(f"corners {i + 1} and {j + 1}: radii too large for the {edge:.0f} long edge between them")
    return chain(circles)


def play(cx, cy, h, r=32.0, grow=0.0):
    """Equilateral play triangle pointing right: upright side h, centroid (cx, cy), corners rounded by r."""
    alt = h * math.sqrt(3) / 2
    xb = cx - alt / 3
    return poly([(xb, cy - h / 2), (xb + alt, cy), (xb, cy + h / 2)], [r, r, r], grow)


def arc(cx, cy, r, a0, a1):
    """Open centre-line arc from a0 clockwise to a1."""
    if a1 <= a0:
        a1 += 360
    if a1 - a0 >= 360:
        raise ValueError("an arc spans less than 360 deg: draw a full circle as <circle>")
    p, q = (cx + r * unit(a0)[0], cy + r * unit(a0)[1]), (cx + r * unit(a1)[0], cy + r * unit(a1)[1])
    return f"M {f(p)} A {r:g} {r:g} 0 {1 if a1 - a0 > 180 else 0} 1 {f(q)}"


def polyline(pts, radii):
    """Open centre line through pts, inner corners filleted with their radius (the ends get round caps)."""
    if len(pts) < 2:
        raise ValueError("a polyline needs at least two points")
    if len(radii) != len(pts):
        raise ValueError(f"{len(pts)} points but {len(radii)} radii (the two ends' radii are ignored)")
    d = [f"M {f(pts[0])}"]
    for i in range(1, len(pts) - 1):
        p, v, q = pts[i - 1], pts[i], pts[i + 1]
        u1 = (p[0] - v[0], p[1] - v[1])
        u2 = (q[0] - v[0], q[1] - v[1])
        l1, l2 = math.hypot(*u1), math.hypot(*u2)
        turn = _turn(p, v, q)
        r = radii[i]
        if r <= 0 or abs(turn) < 1e-9 * l1 * l2:
            d.append(f"L {f(v)}")
            continue
        u1, u2 = (u1[0] / l1, u1[1] / l1), (u2[0] / l2, u2[1] / l2)
        half = math.acos(max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))) / 2
        t = r / math.tan(half)
        if t > l1 + 1e-6 or t > l2 + 1e-6:
            raise ValueError(f"corner {i + 1}: radius {r:g} too large for its edges")
        a, b = (v[0] + u1[0] * t, v[1] + u1[1] * t), (v[0] + u2[0] * t, v[1] + u2[1] * t)
        d.append(f"L {f(a)} A {r:g} {r:g} 0 0 {1 if turn > 0 else 0} {f(b)}")
    d.append(f"L {f(pts[-1])}")
    return " ".join(d)


def capsule(x1, y1, x2, y2, w):
    """Filled stadium w wide between the centres of its two round ends."""
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-9:
        return f"M {x1 - w / 2:.1f} {y1:.1f} A {w / 2:g} {w / 2:g} 0 1 0 {x1 + w / 2:.1f} {y1:.1f} A {w / 2:g} {w / 2:g} 0 1 0 {x1 - w / 2:.1f} {y1:.1f} Z"
    return chain([(x1, y1, w / 2), (x2, y2, w / 2)])


def aiband(x1, y1, x2, y2, stroke=60.0, gap=60.0, width=80.0, inset=0.0):
    """The AI band beside a 45 deg "/" chamfer (x1, y1) lower left -> (x2, y2) upper right, on its lower right."""
    dx, dy = x2 - x1, y2 - y1
    if dx <= 0 or dy >= 0 or abs(abs(dx) - abs(dy)) > 1e-6 * max(abs(dx), 1):
        raise ValueError('the chamfer runs "/" at 45 deg: from the lower left point (X1, Y1) to the upper right one '
                         '(X2, Y2), with X2 - X1 = Y1 - Y2')
    L = math.hypot(dx, dy)
    u = (dx / L, dy / L)
    n = (math.sqrt(0.5), math.sqrt(0.5))       # towards the lower right
    off = stroke / 2 + gap + width / 2
    a = (x1 + n[0] * off + u[0] * inset, y1 + n[1] * off + u[1] * inset)
    b = (x2 + n[0] * off - u[0] * inset, y2 + n[1] * off - u[1] * inset)
    return capsule(a[0], a[1], b[0], b[1], width), a, b


# ---------------------------------------------------------------- outline boolean: A minus B (lines and arcs)

TAU = 2 * math.pi
GEO_EPS = 1e-7                                # parameter tolerance on a segment
JOIN_EPS = 1e-4                               # px: end points closer than this are the same point


def _line(p0, p1):
    return {"p0": p0, "p1": p1, "arc": None}


def _arc_seg(p0, p1, c, r, a0, da):
    return {"p0": p0, "p1": p1, "arc": (c, r, a0, da)}


def _svg_arc(p0, p1, rx, ry, large, sweep):
    """SVG endpoint arc -> centre form (circular arcs only)."""
    if abs(rx - ry) > 1e-6 * max(rx, ry, 1):
        raise ValueError("minus only handles circular arcs (rx = ry)")
    r = abs(rx)
    hx, hy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    d2 = hx * hx + hy * hy
    if d2 < 1e-18:
        return None
    if r * r < d2:
        r = math.sqrt(d2)                     # SVG scales a radius that is too small
    sq = math.sqrt(max(0.0, (r * r - d2) / d2))
    sign = -1 if large == sweep else 1
    cx = sign * sq * hy + (p0[0] + p1[0]) / 2
    cy = -sign * sq * hx + (p0[1] + p1[1]) / 2
    a0 = math.atan2(p0[1] - cy, p0[0] - cx)
    a1 = math.atan2(p1[1] - cy, p1[0] - cx)
    da = (a1 - a0) % TAU if sweep else -((a0 - a1) % TAU)
    return _arc_seg(p0, p1, (cx, cy), r, a0, da)


_TOKEN = re.compile(r"[MmLlHhVvAaZzCcSsQqTt]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def parse_path(d):
    """Path data -> closed loops of line and arc segments."""
    toks = _TOKEN.findall(d)
    loops, segs = [], []
    cur = start = None
    i, cmd = 0, None

    def close():
        nonlocal segs
        if segs:
            if math.hypot(cur[0] - start[0], cur[1] - start[1]) > JOIN_EPS:
                segs.append(_line(cur, start))
            loops.append(segs)
        segs = []

    def take(n):
        nonlocal i
        if i + n > len(toks) or any(not _isnum(t) for t in toks[i:i + n]):
            raise ValueError(f"path data ends early after {cmd}")
        v = [float(t) for t in toks[i:i + n]]
        i += n
        return v

    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in "CcSsQqTt":
                raise ValueError("minus only handles lines and circular arcs (M L H V A Z)")
            if cmd in "Zz":
                close()
                cur = start
                continue
        elif cmd is None:
            raise ValueError("path data must start with M")
        up, rel = cmd.upper(), cmd.islower()
        base = cur if rel and cur is not None else (0.0, 0.0)
        if up == "M":
            x, y = take(2)
            close()
            cur = start = (base[0] + x, base[1] + y)
            cmd = "l" if rel else "L"
        elif up in "LHV":
            if up == "L":
                x, y = take(2)
                p = (base[0] + x, base[1] + y)
            elif up == "H":
                p = ((cur[0] if rel else 0.0) + take(1)[0], cur[1])
            else:
                p = (cur[0], (cur[1] if rel else 0.0) + take(1)[0])
            if math.hypot(p[0] - cur[0], p[1] - cur[1]) > JOIN_EPS:
                segs.append(_line(cur, p))
            cur = p
        elif up == "A":
            rx, ry, _rot = take(3)
            flags = []
            while len(flags) < 2:             # flags may be written without separators ("011")
                if i >= len(toks):
                    raise ValueError("path data ends early in an arc")
                t = toks[i]
                flags.append(int(t[0]))
                if len(t) > 1:
                    toks[i] = t[1:]
                else:
                    i += 1
            x, y = take(2)
            p = (base[0] + x, base[1] + y)
            s = _svg_arc(cur, p, rx, ry, flags[0], flags[1])
            if s is not None:
                segs.append(s)
            cur = p
    if segs:
        close()
    if not loops:
        raise ValueError("no closed outline in the path data")
    return loops


def _isnum(t):
    return not t.isalpha()


def _point(s, t):
    if s["arc"] is None:
        return (s["p0"][0] + t * (s["p1"][0] - s["p0"][0]), s["p0"][1] + t * (s["p1"][1] - s["p0"][1]))
    (cx, cy), r, a0, da = s["arc"]
    a = a0 + t * da
    return (cx + r * math.cos(a), cy + r * math.sin(a))


def _arc_param(s, q):
    """Parameter of point q (on the circle) along arc s, or None when outside the arc."""
    (cx, cy), r, a0, da = s["arc"]
    a = math.atan2(q[1] - cy, q[0] - cx)
    off = (a - a0) % TAU if da > 0 else (a0 - a) % TAU
    if off > TAU - 1e-9:
        off = 0.0
    u = off / abs(da)
    return u if -GEO_EPS <= u <= 1 + GEO_EPS else None


def _hits(s1, s2):
    """Crossings of two segments: [(t1, t2, point)]."""
    out = []
    l1, l2 = s1["arc"] is None, s2["arc"] is None
    if l1 and l2:
        p, q = s1["p0"], s2["p0"]
        r = (s1["p1"][0] - p[0], s1["p1"][1] - p[1])
        s = (s2["p1"][0] - q[0], s2["p1"][1] - q[1])
        den = r[0] * s[1] - r[1] * s[0]
        if abs(den) < 1e-12:
            return out
        w = (q[0] - p[0], q[1] - p[1])
        t = (w[0] * s[1] - w[1] * s[0]) / den
        u = (w[0] * r[1] - w[1] * r[0]) / den
        if -GEO_EPS <= t <= 1 + GEO_EPS and -GEO_EPS <= u <= 1 + GEO_EPS:
            out.append((t, u, _point(s1, t)))
        return out
    if not l1 and l2:
        return [(b, a, pt) for a, b, pt in _hits(s2, s1)]
    if l1:
        (cx, cy), r, _, _ = s2["arc"]
        p0 = s1["p0"]
        v = (s1["p1"][0] - p0[0], s1["p1"][1] - p0[1])
        w = (p0[0] - cx, p0[1] - cy)
        a = v[0] * v[0] + v[1] * v[1]
        b = 2 * (v[0] * w[0] + v[1] * w[1])
        c = w[0] * w[0] + w[1] * w[1] - r * r
        disc = b * b - 4 * a * c
        if disc < -1e-9 * a * r * r or a < 1e-18:
            return out
        sq = math.sqrt(max(0.0, disc))
        for t in sorted({(-b - sq) / (2 * a), (-b + sq) / (2 * a)}):
            if -GEO_EPS <= t <= 1 + GEO_EPS:
                pt = _point(s1, t)
                u = _arc_param(s2, pt)
                if u is not None:
                    out.append((t, u, pt))
        return out
    (c1, r1, _, _), (c2, r2, _, _) = s1["arc"], s2["arc"]
    dx, dy = c2[0] - c1[0], c2[1] - c1[1]
    d = math.hypot(dx, dy)
    if d < 1e-9 or d > r1 + r2 + 1e-9 or d < abs(r1 - r2) - 1e-9:
        return out
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, r1 * r1 - a * a))
    m = (c1[0] + a * dx / d, c1[1] + a * dy / d)
    for sgn in ((1,) if h < 1e-9 else (1, -1)):
        pt = (m[0] + sgn * h * -dy / d, m[1] + sgn * h * dx / d)
        t, u = _arc_param(s1, pt), _arc_param(s2, pt)
        if t is not None and u is not None:
            out.append((t, u, pt))
    return out


def _split(s, cuts):
    """Pieces of s between the cut points [(t, point)], in order."""
    cuts = sorted(c for c in cuts if GEO_EPS < c[0] < 1 - GEO_EPS)
    pts = [(0.0, s["p0"])]
    for t, p in cuts:
        if t - pts[-1][0] > GEO_EPS:
            pts.append((t, p))
    pts.append((1.0, s["p1"]))
    out = []
    for (t0, q0), (t1, q1) in zip(pts, pts[1:]):
        if s["arc"] is None:
            out.append(_line(q0, q1))
        else:
            c, r, a0, da = s["arc"]
            out.append(_arc_seg(q0, q1, c, r, a0 + t0 * da, (t1 - t0) * da))
    return out


def _mid(s):
    return _point(s, 0.5)


def _polyline(loop):
    pts = []
    for s in loop:
        n = 1 if s["arc"] is None else max(2, int(abs(s["arc"][3]) / math.radians(1)) + 1)
        pts += [_point(s, k / n) for k in range(n)]
    return pts


def _inside(p, polys):
    """Even-odd point in polygon over all loops."""
    x, y = p
    hit = False
    for pts in polys:
        for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                hit = not hit
    return hit


def _reverse(s):
    if s["arc"] is None:
        return _line(s["p1"], s["p0"])
    c, r, a0, da = s["arc"]
    return _arc_seg(s["p1"], s["p0"], c, r, a0 + da, -da)


def _emit(loop):
    d = [f"M {f(loop[0]['p0'])}"]
    for s in loop:
        if s["arc"] is None:
            d.append(f"L {f(s['p1'])}")
        else:
            # arcs over 120 deg are written in pieces: a chord close to the diameter lets the renderer move
            # the centre visibly when the end points are rounded to 0.1
            _, r, _, da = s["arc"]
            n = max(1, math.ceil(abs(da) / (TAU / 3) - 1e-9))
            for k in range(1, n + 1):
                q = s["p1"] if k == n else _point(s, k / n)
                d.append(f"A {r:g} {r:g} 0 0 {1 if da > 0 else 0} {f(q)}")
    if d[-1].startswith("L"):
        d.pop()                               # the closing line is the Z
    return " ".join(d) + " Z"


def _oriented(loops):
    """Loops turned clockwise on screen, holes (inside an odd number of the other loops) anticlockwise,
    so that A's kept edges and B's reversed edges join head to tail whichever way the input was drawn."""
    polys = [_polyline(loop) for loop in loops]
    out = []
    for k, (loop, pts) in enumerate(zip(loops, polys)):
        area2 = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
        hole = _inside(pts[0], [q for m, q in enumerate(polys) if m != k])
        if (area2 > 0) == hole:
            loop = [_reverse(s) for s in reversed(loop)]
        out.append(loop)
    return out


def minus(path_a, path_b):
    """Outline A with outline B removed (even-odd inside tests), as path data; returns (d, loop count)."""
    loops_a, loops_b = _oriented(parse_path(path_a)), _oriented(parse_path(path_b))
    A = [s for loop in loops_a for s in loop]
    B = [s for loop in loops_b for s in loop]
    cut_a = [[] for _ in A]
    cut_b = [[] for _ in B]
    for i, sa in enumerate(A):
        for j, sb in enumerate(B):
            for ta, tb, pt in _hits(sa, sb):
                cut_a[i].append((ta, pt))
                cut_b[j].append((tb, pt))
    poly_a = [_polyline(loop) for loop in loops_a]
    poly_b = [_polyline(loop) for loop in loops_b]
    keep = [p for s, c in zip(A, cut_a) for p in _split(s, c) if not _inside(_mid(p), poly_b)]
    keep += [_reverse(p) for s, c in zip(B, cut_b) for p in _split(s, c) if _inside(_mid(p), poly_a)]
    if not keep:
        raise ValueError("B covers all of A: nothing is left")
    loops = []
    while keep:
        loop = [keep.pop(0)]
        start = loop[0]["p0"]
        while math.hypot(loop[-1]["p1"][0] - start[0], loop[-1]["p1"][1] - start[1]) > JOIN_EPS:
            end = loop[-1]["p1"]
            k = min(range(len(keep)), default=None,
                    key=lambda m: math.hypot(keep[m]["p0"][0] - end[0], keep[m]["p0"][1] - end[1]))
            if k is None or math.hypot(keep[k]["p0"][0] - end[0], keep[k]["p0"][1] - end[1]) > 1e-3:
                raise ValueError("could not close the result: keep the two outlines from touching "
                                 "or running along each other")
            loop.append(keep.pop(k))
        loops.append(loop)
    return " ".join(_emit(loop) for loop in loops), len(loops)


# ---------------------------------------------------------------- command line

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    kp = argparse.ArgumentParser(add_help=False)
    kp.add_argument("--k", type=float, default=1.0,
                    help="the #subject scale: rule numbers in final px (corner radii, grow, fillets, capsule width, "
                         "aiband stroke, gap, width and inset) are divided by it")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("arc", parents=[kp])
    for a in ("cx", "cy", "r", "a0", "a1"):
        p.add_argument(a, type=float)
    p = sub.add_parser("rrect", parents=[kp])
    for a in ("x", "y", "w", "h", "r"):
        p.add_argument(a, type=float)
    p.add_argument("--grow", type=float, default=0.0)
    p = sub.add_parser("bubble", parents=[kp])
    for a in ("x", "y", "w", "h", "r", "tail"):
        p.add_argument(a, type=float)
    p.add_argument("side", nargs="?", default="left", choices=["left", "right"])
    p.add_argument("--angle", type=float, default=55.0)
    p.add_argument("--tip-r", type=float, default=24.0)
    p.add_argument("--concave", type=float, default=56.0)
    p.add_argument("--grow", type=float, default=0.0)
    p = sub.add_parser("poly", parents=[kp])
    p.add_argument("points", metavar="POINTS", help='corner points "X1,Y1 X2,Y2 ..."')
    g = p.add_mutually_exclusive_group()
    g.add_argument("--r", type=float, default=24.0, help="one radius for every corner (0 = sharp)")
    g.add_argument("--radii", metavar="R1,R2,...", help="one radius per corner, in order")
    p.add_argument("--open", action="store_true", help="a polyline: no closing edge, the ends get round caps")
    p.add_argument("--grow", type=float, default=0.0)
    p = sub.add_parser("play", parents=[kp])
    for a in ("cx", "cy", "h"):
        p.add_argument(a, type=float)
    p.add_argument("--r", type=float, default=24.0)
    p.add_argument("--grow", type=float, default=0.0)
    p = sub.add_parser("capsule", parents=[kp])
    for a in ("x1", "y1", "x2", "y2", "w"):
        p.add_argument(a, type=float)
    p = sub.add_parser("aiband", parents=[kp])
    for a in ("x1", "y1", "x2", "y2"):
        p.add_argument(a, type=float)
    p.add_argument("--stroke", type=float, default=60.0)
    p.add_argument("--gap", type=float, default=60.0)
    p.add_argument("--width", type=float, default=80.0)
    p.add_argument("--inset", type=float, default=0.0)
    p = sub.add_parser("sector", parents=[kp])
    for a in ("cx", "cy", "r", "a0", "a1", "fillet"):
        p.add_argument(a, type=float)
    p = sub.add_parser("ring", parents=[kp])
    for a in ("cx", "cy", "r_out", "r_in", "a0", "a1"):
        p.add_argument(a, type=float)
    p.add_argument("--fillet", type=float, default=0.0)
    p = sub.add_parser("segment", parents=[kp])
    for a in ("cx", "cy", "r", "a", "d"):
        p.add_argument(a, type=float)
    p.add_argument("--fillet", type=float, default=0.0)
    p = sub.add_parser("minus", parents=[kp])
    p.add_argument("path_a", metavar="PATH_A")
    p.add_argument("path_b", metavar="PATH_B")
    args = ap.parse_args()
    if args.cmd and args.k <= 0:
        sys.exit("--k must be positive")
    px = (lambda v: v / args.k) if args.cmd else (lambda v: v)   # final-pixel rule numbers -> source units
    try:
        if args.cmd == "arc":
            print(arc(args.cx, args.cy, args.r, args.a0, args.a1))
        elif args.cmd == "rrect":
            print(rrect(args.x, args.y, args.w, args.h, args.r, px(args.grow)))
        elif args.cmd == "bubble":
            print(bubble(args.x, args.y, args.w, args.h, args.r, args.tail, args.side, args.angle,
                         px(args.tip_r), px(args.concave), px(args.grow)))
        elif args.cmd == "poly":
            pts = [tuple(float(v) for v in xy.split(",")) for xy in args.points.replace(";", " ").split()]
            if any(len(p) != 2 for p in pts):
                sys.exit('POINTS are "X1,Y1 X2,Y2 ...": a comma inside each pair, spaces between pairs')
            radii = [float(v) for v in args.radii.split(",")] if args.radii else [args.r] * len(pts)
            if args.open:
                print(polyline(pts, [px(r) for r in radii]))
            else:
                print(poly(pts, [px(r) for r in radii], px(args.grow)))
        elif args.cmd == "play":
            print(play(args.cx, args.cy, args.h, px(args.r), px(args.grow)))
        elif args.cmd == "capsule":
            print(capsule(args.x1, args.y1, args.x2, args.y2, px(args.w)))
        elif args.cmd == "aiband":
            band, a, b = aiband(args.x1, args.y1, args.x2, args.y2, px(args.stroke), px(args.gap), px(args.width),
                                px(args.inset))
            print(f"<!-- band (accent, data-accent=\"band\"): {px(args.width):g} wide, end centres ({f(a)}) and ({f(b)}), "
                  f"its edge {px(args.gap):g} clear of the chamfer's line -->")
            print(band)
        elif args.cmd == "sector":
            print(rounded_sector(args.cx, args.cy, args.r, args.a0, args.a1, px(args.fillet)))
        elif args.cmd == "ring":
            print(ring(args.cx, args.cy, args.r_out, args.r_in, args.a0, args.a1, 0.0, px(args.fillet)))
        elif args.cmd == "segment":
            print(segment(args.cx, args.cy, args.r, args.a, args.d, px(args.fillet)))
        elif args.cmd == "minus":
            d, n = minus(args.path_a, args.path_b)
            if n > 1:
                print(f'<!-- {n} loops: give this path fill-rule="evenodd" -->')
            print(d)
        else:
            print(__doc__)
    except ValueError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
