#!/usr/bin/env python3
"""
Render and check a Rian app icon SVG (graphite line style).

  python3 scripts/render.py ICON.svg [more.svg ...] [-o DIR] [--variants] [--export] [--store-ab] [--json]
                           [--tide FILE]

Always writes, for each SVG:
  DIR/<name>-1024.png    full-bleed opaque 1024 master, default (graphite) look
  DIR/<name>-sheet.png   review sheet: iOS-masked master; 180/120/80/60/40/29 px (40 and 29 from the small
                         version); Apple's six iOS 26 appearances (default, dark, clear light and dark, tinted
                         light and dark) with an approximate Liquid Glass (specular rim and shadow per group);
                         the flat light, dark and mono looks; Android circle and squircle masks, the themed icon in the light and the
                         dark theme (monochrome layer recoloured with the theme's Material You tones, seed hue
                         from a light and a dark wallpaper); the icon next to Tide at the same size
and prints a metrics report, one line per check with value, target and PASS / FAIL / INFO.
Exit code 0 even when a check fails (1 only when an SVG cannot be read).

  --variants  also writes <name>-light.svg/.png, <name>-dark.svg/.png, <name>-mono.svg/.png (transparent)
              and <name>-small.svg (64 px and below: the line 76 instead of 60), and
              the flat marks for in-app brand art (rian-app-theme's brand panels): #subject alone, every line one
              solid colour, the volume that colour at a low opacity and the accent its main tone, transparent,
              cropped to the subject:
              <name>-mark.svg/.png (light lines, for the dark graphite panel) and <name>-mark-light.svg/.png (dark
              lines, for the light panel)
  --export    also writes DIR/export/ (DIR/export/<name>/ when several SVGs are given):
              ios-1024.png, ios-1024-dark.png (asset catalog Dark: transparent background, the system draws
              its own), ios-1024-tinted.png (asset catalog Tinted: grayscale), icon-1024-transparent.png,
              play-512.png, pwa-192.png, pwa-512.png,
              pwa-maskable-512.png, apple-touch-180.png, favicon-16.png, favicon-32.png, favicon.ico, favicon.svg,
              android-foreground-432.png, android-monochrome-432.png,
              android/mipmap-anydpi-v26/ic_launcher.xml + ic_launcher_round.xml,
              android/drawable/ic_launcher_background.xml,
              android/mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/ic_launcher_foreground.png + _monochrome.png,
              plus legacy 48 dp ic_launcher.png + ic_launcher_round.png for API 25 and below,
              icon-composer/1_volume.svg + .png (the volume, opaque: set its opacity in Icon Composer),
              2_body.svg (the strokes, transform baked in) + 2_body.png, 3_accent.svg + 3_accent.png
              (only the PNG when a layer uses a mask and cannot be baked to plain paths), icon-composer/README.txt
              Android layers are scaled by min(290 / r_max, 0.72), the PWA maskable icon by
              min(409.6 / r_max, 409.6 / Tide's r_max), so compact icons are not blown up past Tide.
  --store-ab  also writes DIR/store-ab/ (DIR/store-ab/<name>/ when several SVGs are given): the App Store
              A/B variants of the default look, <name>-lighter, <name>-rim and (for a coloured accent)
              <name>-tint as .svg and .png, a comparison sheet <name>-store-ab.png on the dark and the light
              store, and README.txt
  --json      also writes <name>-metrics.json
  --tide FILE Tide reference for the size checks and the side-by-side cell (default examples/tide.svg;
              falls back to built-in numbers when that file is missing or not a graphite icon)

All numbers are final pixels on the 1024 canvas (after the #subject transform). Layers are rasterised
separately in headless Chromium (Playwright) and measured with numpy. Install once with:
  pip install playwright pillow numpy && playwright install chromium
If a Chromium build already exists on the machine, set CHROMIUM_PATH to its executable.

SVG conventions read here (references/construction.md):
  defs: #bg, #body-fill, #accent linearGradients (userSpaceOnUse); no filters (no glow)
  #background (full-bleed rect), #subject (transform, data-shape = circle | square | tall | wide | open,
  data-category = tools | image | video | ai | health | finance), #volume (first child: one flat shape,
  fill #FFFFFF, fill-opacity 0.14, bounded by the lines' centre line), #body (<g fill="none" stroke="url(#body-fill)"
  stroke-width="60 / k" stroke-linecap="round" stroke-linejoin="round"> with every line), #accent-shape (one
  filled element, fill url(#accent), no stroke; data-accent="band" for the AI band).
  Store A/B variants written by --store-ab carry data-variant = lighter | rim | tint on the root (rim adds
  <path id="rim"> between #background and #subject).
"""

import argparse
import base64
import glob
import io
import json
import math
import os
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

SKILL_DIR = Path(__file__).resolve().parent.parent
TIDE_SVG = SKILL_DIR / "examples" / "tide.svg"

# ---------------------------------------------------------------- house rules (references/style.md, brief B)

STROKE = 60.0                 # the line, final px: Lucide's 2-unit stroke on a 24 grid scaled to the subject
STROKE_TOL = 1.0              # (about 30 px a unit) is 60; it is 1.7 px at 29 px and 2.3 px at 40 px
SMALL_STROKE = 76.0           # small version (64 px and below): 2.2 px at 29 px
GAP_LINE = 60.0               # clear gap between two separate lines: one line width
GAP_TOL = 1.0
PINCH_R = 30                  # closing radius: shuts every gap narrower than GAP_LINE
PINCH_AREA = 3000             # px²: a closed-up corridor this big is a gap that clogs (a 45 deg join adds ~2200)
GAP_ACCENT = 60.0             # clear gap from the filled accent to any line: one line width as well (at 40
                              # the small version, lines 76, clogs it at 40 px)
OVERLAP_MAX = 0.002           # body & accent pixels / accent pixels
PARTS_MAX = 4                 # separate lines (connected strokes) in the body
MIN_PIECE = 50                # px²: smaller specks are antialiasing noise
CLOSE_R = 30                  # closing radius that shuts the gaps for the silhouette
LONG_SIDE_MAX = 720
SOLID_RATIO = (0.90, 1.10)    # filled silhouette area / Tide's
OPEN_RATIO = (0.90, 1.15)     # convex hull area / Tide's hull
ACCENT_SHARE = (6.0, 20.0)    # filled accent / silhouette convex hull, % (an image sun r 74 is about 6 %)
ACCENT_SHARE_BAND = (6.0, 14.0)   # the AI band across a corner
GRAD_SPAN = 480               # accent gradient span, final px, centred on the accent shape
BODY_SPAN = 600               # body gradient span, final px, centred on the lines
GRAD_TOL = 8
CENTROID_MAX = 12             # filled-silhouette centroid to (512, 512)
BODY_CENTRE = (512, 530)      # with a top protrusion: the body's own centre
BODY_TOL = 6
PROTRUSION_W = 80             # parts thinner than this (an opening of radius 40) count as protrusions
CONTRAST_BODY = 7.0           # lines over background, default look
CONTRAST_ACCENT = 3.0         # accent over background, default look
# the volume (Apple HIG, iOS 26: filled, overlapping shapes at different opacities give the layers depth; the system adds
# the light): one flat translucent shape under the lines, bounded by the lines' centre line, so its edge hides under
# them. Colour and opacity per look; the master is the default look
VOLUME_FILL = "#FFFFFF"
VOLUME_OPACITY = 0.14
VOLUME_TOL = 0.005
VOLUME_SPILL = 0.01           # volume pixels outside the (filled) silhouette / volume pixels
VOLUME_EDGE = 0.90            # share of the volume's edge hidden under a line or the accent
VOLUME_ALPHA = 8              # alpha above this counts as volume when measuring (0.14 renders as about 36)
BAND_ANGLE = 135.0            # the AI band's long axis, y down: bottom left to top right ("/")
BAND_ANGLE_TOL = 1.5
BAND_WIDTH = 80.0
BAND_WIDTH_TOL = 3.0
# category marks (references/style.md, 类别记号): data-category -> (name, accent colour)
CATEGORIES = {"tools": ("工具", "蓝"), "image": ("图片", "黄"), "video": ("视频", "珊瑚"), "ai": ("AI", "紫"),
              "health": ("健康", "绿"), "finance": ("财务", "绿")}
RESERVED = "绿"               # only health and finance
TOOLS_SPAN = 0.95             # the tools line runs across this share of the drawing's width (or more)
TOOLS_AT = (0.35, 0.75)       # its centre line, share of the drawing's height from the top
SUN_CORNER = 0.42             # the image sun's centre within this share of the box from the top left (inside a
                              # framed photo it sits a line and a gap in from the frame)
SUN_ROUND = 0.92              # area / (pi R²), R = farthest edge from the centre
SUN_R_MIN = 72.0              # 2 px across at 29 px
PLAY_H_MIN = 110              # the video mark's hole, measured height (shapes.py play H 240 measures about 120)
AI_CORNER = (0.65, 0.50)      # the AI band's centre in the box: mean of x and y share >= .65, each >= .50
SMALL_CHECK = 40              # parts and holes must hold at this size (FAIL); 29 and 16 px are INFO
SMALL_INFO = 29
SMALL_FAVICON = 16            # favicon-16: only the silhouette has to read
ANDROID_SAFE_R = 313.0        # 66 dp safe circle of a 108 dp layer on the 1024 canvas
ANDROID_R = 290.0             # target r_max: 23 px (~2.4 dp) inside the safe circle
ANDROID_CAP = 0.72            # Tide's factor (290 / 401): compact icons are not blown up past it
PWA_R = 409.6                 # maskable: centre 80 % circle; capped at Tide's factor like Android
KEYLINES = {"circle": "⌀ 600", "square": "540 × 540", "tall": "480 × 600", "wide": "600 × 480",
            "open": "+10% 以内"}
KEYLINE_WH = {"circle": (600, 600), "square": (540, 540), "tall": (480, 600), "wide": (600, 480)}
KEYLINE_NAME = {"square": "方形", "tall": "竖矩形", "wide": "横矩形"}
OPEN_EXTRA = 1.10             # open shapes may be 10 % larger than the keyline of their overall form
SHAPES = ("circle", "square", "tall", "wide", "open")
BODY_GRAD = "body-fill"       # the body gradient's id (the <g id="body"> group owns "body")

# looks (brief B4): background and body gradient stops, top -> bottom
LOOKS = {
    "default": {"bg": ("#26282B", "#191C1F"), "body": ("#F8F9FB", "#C6C8CB"), "volume": (VOLUME_FILL, VOLUME_OPACITY)},
    "light": {"bg": ("#FBFCFE", "#E9EBEE"), "body": ("#333538", "#1E2022"), "volume": ("#1E2022", 0.07)},
    "dark": {"bg": ("#191C1F", "#0E1115"), "body": ("#EDEEEF", "#BDBFC2"), "volume": ("#FFFFFF", 0.10)},
}
MONO_ACCENT_OPACITY = ".5"
MONO_VOLUME_OPACITY = 0.3     # mono (Tinted, Clear, Android monochrome): lines 100 %, accent 50 %, volume 30 %
MARK_PAD = 8                  # <name>-mark: transparent margin around the subject, px
# in-app brand marks (rian-app-theme's brand panels): flat, like the UI's Lucide lines. The suffix names the scheme the
# mark is for, like -light / -dark for the icon: <name>-mark (light lines) on the dark graphite panel, <name>-mark-light
# (dark lines) on the light panel. The accent is its main tone in both. Same values as rian-app-theme's brand.line.
MARK_LINE = {"mark": "#E6E8EB", "mark-light": "#2A2C2F"}
# the marks keep the volume, flat, in the line colour at a low opacity: the in-app art reads as the same object
MARK_VOLUME = {"mark": 0.14, "mark-light": 0.08}
PALETTE = {"蓝": ("#7AAEFF", "#3B7BEA"), "绿": ("#6FD3A6", "#23A36B"), "黄": ("#FFD978", "#F2AE2E"),
           "珊瑚": ("#FF9C86", "#EC5B45"), "紫": ("#B3A6FF", "#7A63F0"), "灰": ("#C8C7C3", "#8E8D89")}
TINT = "#5E9BFF"              # the tint the sheet's two Tinted tiles use (the user picks it on the device)
FAVICON_RADIUS = 0.22         # favicon: graphite tile with 22 % corners
IOS_CORNER = 0.2237           # Apple's icon shape: corner radius / side ...
IOS_SMOOTH = 0.6              # ... with 60 % corner smoothing (previews, the store rim, its edge ring)

# App Store A/B variants (style.md, 商店图标的 A/B 变体): extra exports of the default look, never the master
STORE_AB = ("lighter", "rim", "tint")
STORE_NAME = {"lighter": "浅一档", "rim": "细亮边", "tint": "类别色"}   # tint: 强调色底 outside the categories
LIGHTER_BG = ("#323538", "#26282B")   # one step lighter: L 22 -> 16, the default's top is its bottom
RIM = ("#66686C", "#44474A")          # rim gradient, L 44 -> 30, hue 265, chroma 2.5
RIM_W = 16                            # rim width inside Apple's icon shape (ios_path), final px
TINT_BG = {"蓝": ("#262730", "#1A1B23"), "黄": ("#2D2720", "#201B13"), "珊瑚": ("#302523", "#241917"),
           "紫": ("#29272F", "#1D1A22"), "绿": ("#212A24", "#151E18")}   # L 16 -> 10, chroma 6 at the accent's hue
STORE_BG = {"dark": "#000000", "light": "#FFFFFF"}

# Android themed icon, approximated: Material You tonal palettes (Android 13 tonal spot: accent1 chroma 36,
# neutral1 4, neutral2 8; tone = CIE L*) from a seed hue taken from the wallpaper. Launcher3
# (ThemedIconDrawable.getColors) picks the pair by the system theme, not the wallpaper: light theme
# accent1_100 behind neutral2_700, dark theme neutral1_800 behind accent1_100. The sheet shows the light
# theme on a light wallpaper and the dark theme on a dark one.
TONAL_CHROMA = {"accent1": 36.0, "neutral1": 4.0, "neutral2": 8.0}
THEMED_TONES = {"light": (("accent1", 90), ("neutral2", 30)), "dark": (("neutral1", 20), ("accent1", 90))}

# Tide reference used only when the Tide SVG cannot be measured (line Tide: silhouette, hull, r_max, ink).
TIDE_FALLBACK = {"silhouette": 261400.0, "hull": 286500.0, "r_max": 401.0, "ink": 141000.0}

NS = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
ET.register_namespace("", NS)
ET.register_namespace("xlink", XLINK)
GRAPHIC = {"path", "circle", "rect", "ellipse", "line", "polyline", "polygon", "use", "g", "text", "image"}
GEOMETRY = {"path", "circle", "rect", "ellipse", "line", "polyline", "polygon"}
NONRENDER = {"defs", "mask", "clipPath", "pattern", "marker", "symbol", "linearGradient", "radialGradient",
             "filter", "style", "title", "desc", "metadata"}


# ---------------------------------------------------------------- kept helpers (imported elsewhere)

def squircle_path(size=1024, n=4.0, steps=360):
    """Superellipse on a size x size canvas, as an SVG path: the rounded PWA background. (iOS previews and the
    store rim use ios_path, which is closer to Apple's mask.)"""
    r = size / 2
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        x = r + r * math.copysign(abs(c) ** (2 / n), c)
        y = r + r * math.copysign(abs(s) ** (2 / n), s)
        pts.append(f"{x:.1f},{y:.1f}")
    return "M" + " L".join(pts) + " Z"


def _ios_corners(size, inset):
    """Apple's icon shape: a rounded square with corner radius IOS_CORNER of the side and IOS_SMOOTH corner
    smoothing (the cubic, arc, cubic construction Figma uses for its iOS preset), shrunk by inset on every
    side (radius minus inset, so the rim inside it is inset wide all round). -> per corner, clockwise from the
    top right: [start, (c1, c2, end), arc end, (c1, c2, end), arc centre], and the arc radius."""
    r = IOS_CORNER * size - inset
    xi = IOS_SMOOTH
    p = (1 + xi) * r
    arc = math.radians(90 * (1 - xi))
    alpha = (math.pi / 2 - arc) / 2
    beta = math.radians(45 * xi)
    c = r * math.tan(alpha / 2) * math.cos(beta)
    d = c * math.tan(beta)
    b = (p - math.sin(arc / 2) * r * math.sqrt(2) - c - d) / 3
    a = 2 * b
    local = [(-p, 0), ((-p + a, 0), (-p + a + b, 0), (-p + a + b + c, d)), (-d, p - a - b - c),
             ((0, p - a - b), (0, p - a), (0, p)), (-r, r)]   # around the top right corner, y down
    lo, hi = inset, size - inset
    out = []
    for (cx, cy), turns in (((hi, lo), 0), ((hi, hi), 1), ((lo, hi), 2), ((lo, lo), 3)):
        def at(v, t=turns, cx=cx, cy=cy):
            x, y = v
            for _ in range(t):
                x, y = -y, x
            return (cx + x, cy + y)
        out.append([at(local[0]), tuple(map(at, local[1])), at(local[2]), tuple(map(at, local[3])), at(local[4])])
    return out, r


def ios_path(size=1024, inset=0.0):
    """Apple's icon shape as an SVG path (cubics and arcs), optionally shrunk by inset."""
    corners, r = _ios_corners(size, inset)

    def pt(v):
        return f"{v[0]:.2f} {v[1]:.2f}"

    d = []
    for start, c1, arc_end, c2, _ in corners:
        d.append(("M " if not d else "L ") + pt(start))
        d.append("C " + " ".join(map(pt, c1)))
        d.append(f"A {r:.2f} {r:.2f} 0 0 1 " + pt(arc_end))
        d.append("C " + " ".join(map(pt, c2)))
    return " ".join(d) + " Z"


def ios_points(size=1024, inset=0.0, steps=24):
    """The same outline as points (for raster masks)."""
    corners, r = _ios_corners(size, inset)

    def cubic(p0, c):
        for i in range(1, steps + 1):
            t = i / steps
            yield tuple((1 - t) ** 3 * p0[k] + 3 * (1 - t) ** 2 * t * c[0][k] + 3 * (1 - t) * t * t * c[1][k]
                        + t ** 3 * c[2][k] for k in (0, 1))

    pts = []
    for start, c1, arc_end, c2, (ox, oy) in corners:
        pts.append(start)
        pts += cubic(start, c1)
        t0 = math.atan2(c1[2][1] - oy, c1[2][0] - ox)
        t1 = math.atan2(arc_end[1] - oy, arc_end[0] - ox)
        t1 += 2 * math.pi if t1 < t0 else 0
        pts += [(ox + r * math.cos(t0 + (t1 - t0) * i / steps), oy + r * math.sin(t0 + (t1 - t0) * i / steps))
                for i in range(1, steps + 1)]
        pts += cubic(arc_end, c2)
    return pts


def rounded_rect_path(size=1024, frac=FAVICON_RADIUS):
    r = size * frac
    e = size - r
    return (f"M {r:.1f} 0 H {e:.1f} A {r:.1f} {r:.1f} 0 0 1 {size} {r:.1f} V {e:.1f} "
            f"A {r:.1f} {r:.1f} 0 0 1 {e:.1f} {size} H {r:.1f} A {r:.1f} {r:.1f} 0 0 1 0 {e:.1f} "
            f"V {r:.1f} A {r:.1f} {r:.1f} 0 0 1 {r:.1f} 0 Z")


def find_chromium():
    env = os.environ.get("CHROMIUM_PATH")
    if env:
        return env
    for pattern in ("/opt/pw-browsers/chromium-*/chrome-linux*/chrome",):
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    return None


# ---------------------------------------------------------------- SVG DOM helpers

def local(el):
    return el.tag.split("}")[-1] if isinstance(el.tag, str) else ""


def q(tag):
    return f"{{{NS}}}{tag}"


def rendered(root):
    """Elements outside <defs>, masks and other non-rendered containers, in document order."""
    def walk(el):
        yield el
        for c in el:
            if isinstance(c.tag, str) and local(c) not in NONRENDER:
                yield from walk(c)
    return walk(root)


def node(root, ident):
    """The rendered element with this id, skipping <defs> (older files used "body" for both the gradient
    and the group; the gradient is now body-fill)."""
    return next((e for e in rendered(root) if e.get("id") == ident), None)


def grad(root, ident):
    return next((e for e in root.iter() if local(e) in ("linearGradient", "radialGradient")
                 and e.get("id") == ident), None)


def defn(root, ident):
    """An element inside <defs> (filter, mask) with this id."""
    for d in root.iter(q("defs")):
        for e in d.iter():
            if e.get("id") == ident:
                return e
    return None


def parents(root):
    return {c: p for p in root.iter() for c in p}


def classes(el):
    return (el.get("class") or "").split()


def style_dict(el):
    out = {}
    for part in (el.get("style") or "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def get_prop(el, prop):
    st = style_dict(el)
    return st[prop] if prop in st else el.get(prop)


def set_prop(el, prop, value):
    st = style_dict(el)
    if prop in st:
        st[prop] = value
        el.set("style", "; ".join(f"{k}: {v}" for k, v in st.items()))
    else:
        el.set(prop, value)


def href(el):
    return el.get("href") or el.get(f"{{{XLINK}}}href")


def norm_color(c):
    c = (c or "").strip().lower()
    named = {"white": "#ffffff", "black": "#000000"}
    c = named.get(c, c)
    if re.fullmatch(r"#[0-9a-f]{3}", c):
        c = "#" + "".join(ch * 2 for ch in c[1:])
    return c


def url_id(v):
    m = re.match(r"\s*url\(\s*#([^)\s]+)\s*\)", v or "")
    return m.group(1) if m else None


def num(v, default=None):
    if v is None:
        return default
    m = re.match(r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)", str(v))
    return float(m.group(1)) if m else default


def parse_transform(s):
    """SVG transform list -> 3x3 matrix."""
    M = np.eye(3)
    for name, args in re.findall(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)", s or ""):
        v = [float(x) for x in re.split(r"[\s,]+", args.strip()) if x]
        T = np.eye(3)
        if name == "translate":
            T[0, 2], T[1, 2] = v[0], (v[1] if len(v) > 1 else 0.0)
        elif name == "scale":
            T[0, 0], T[1, 1] = v[0], (v[1] if len(v) > 1 else v[0])
        elif name == "rotate":
            a = math.radians(v[0])
            R = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
            if len(v) == 3:
                A = np.eye(3); A[0, 2], A[1, 2] = v[1], v[2]
                B = np.eye(3); B[0, 2], B[1, 2] = -v[1], -v[2]
                R = A @ R @ B
            T = R
        elif name == "matrix":
            T = np.array([[v[0], v[2], v[4]], [v[1], v[3], v[5]], [0, 0, 1]])
        elif name == "skewX":
            T[0, 1] = math.tan(math.radians(v[0]))
        elif name == "skewY":
            T[1, 0] = math.tan(math.radians(v[0]))
        M = M @ T
    return M


def chain_matrix(el, top, P):
    """Product of the transforms from `top` (included) down to `el` (included)."""
    seq = [el]
    while seq[-1] is not top and seq[-1] in P:
        seq.append(P[seq[-1]])
    M = np.eye(3)
    for e in reversed(seq):
        M = M @ parse_transform(e.get("transform"))
    return M


def gradient_stops(g):
    return [norm_color(get_prop(s, "stop-color")).upper() for s in g.iter(q("stop"))]


def gradient_opacities(g):
    return [num(get_prop(s, "stop-opacity"), 1.0) for s in g.iter(q("stop"))]


def strip_xml_prolog(text):
    text = re.sub(r"<\?xml[^>]*\?>", "", text)
    return re.sub(r"<!DOCTYPE[^>]*>", "", text, flags=re.I).strip()


def prune_defs(root):
    """Drop gradients, filters, masks and clip paths that nothing references any more."""
    while True:
        text = ET.tostring(root, encoding="unicode")
        used = set(re.findall(r"url\(\s*#([^)\s]+)\s*\)", text)) | set(re.findall(r'href="#([^"]+)"', text))
        dead = [(d, c) for d in root.iter(q("defs")) for c in list(d)
                if c.get("id") and c.get("id") not in used]
        if not dead:
            return root
        for d, c in dead:
            d.remove(c)


def serialize(root):
    s = ET.tostring(root, encoding="unicode")
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip() + "\n"


def load_svg(path):
    text = Path(path).read_text(encoding="utf-8")
    try:
        root = ET.fromstring(strip_xml_prolog(text))
    except ET.ParseError as e:
        hint = ""
        if re.search(r"<!--(?:(?!-->).)*--(?!>)", text, flags=re.S):
            hint = " (a comment contains two hyphens in a row, which XML forbids)"
        raise ValueError(f"cannot parse {path}: {e}{hint}")
    return text, root


# ---------------------------------------------------------------- static facts from the SVG

def grad_info(g):
    if g is None:
        return None
    units = g.get("gradientUnits", "objectBoundingBox")
    co = {a: g.get(a) for a in ("x1", "y1", "x2", "y2")}
    pct = any(v is not None and v.strip().endswith("%") for v in co.values())
    return {"tag": local(g), "units": units, "stops": gradient_stops(g), "opacities": gradient_opacities(g),
            "id": g.get("id"), "x1": num(co["x1"], 0.0), "x2": num(co["x2"], 1024.0 if units == "userSpaceOnUse" else 1.0),
            "y1": num(co["y1"], 0.0), "y2": num(co["y2"], 0.0), "explicit": all(co[a] is not None for a in co),
            "percent": pct, "transform": parse_transform(g.get("gradientTransform"))}


def static_info(root):
    info = {"errors": [], "fatal": False}
    P = parents(root)
    subject, body = node(root, "subject"), node(root, "body")
    accent, background = node(root, "accent-shape"), node(root, "background")
    volume = node(root, "volume")
    info["no_volume"] = subject is not None and subject.get("data-volume") == "none"
    if volume is None and not info["no_volume"]:
        info["errors"].append('缺 #volume：线稿下面垫一层半透明白色实形，边落在线的中线上（style.md「体积层」）；'
                              '物件没有「里面」（一支箭头、一条线）时在 #subject 上写 data-volume="none"')
    if volume is not None and info["no_volume"]:
        info["errors"].append('有 #volume 就不写 data-volume="none"')
    for el, name in ((subject, "#subject"), (body, "#body"), (accent, "#accent-shape")):
        if el is None:
            info["errors"].append(f"缺 {name}")
            info["fatal"] = True
    if background is None:
        info["errors"].append("缺 #background")
    else:
        full = (local(background) == "rect" and not len(background) and not background.get("transform")
                and num(background.get("x"), 0) == 0 and num(background.get("y"), 0) == 0
                and (background.get("width") or "").strip() in ("1024", "100%")
                and (background.get("height") or "").strip() in ("1024", "100%"))
        if not full:
            info["errors"].append("#background 只能是一个覆盖 0 0 1024 1024 的 <rect>，里面不放东西（底上不加光斑、纹理）")
    ids = {}
    for e in root.iter():
        if e.get("id"):
            ids[e.get("id")] = ids.get(e.get("id"), 0) + 1
    dup = [i for i, n in ids.items() if n > 1]
    if dup:
        info["errors"].append("id 重复：" + ", ".join(dup[:3])
                              + (f'（主体渐变的 id 是 {BODY_GRAD}，<g id="body"> 才叫 body）' if "body" in dup else ""))
    if body is not None and local(body) != "g":
        info["errors"].append("#body 要是 <g>")
    for old in ("line", "backing", "cut", "cuts"):
        if node(root, old) is not None or defn(root, old) is not None:
            info["errors"].append(f"旧风格的 #{old}：按线稿风格重画（线都在 #body 里）")
    if subject is not None and (subject.get("data-cut") or subject.get("data-pieces-why")):
        info["errors"].append("data-cut、data-pieces-why 是旧的实形风格：线稿风格没有切口和块数，删掉")
    if any(e.get("data-part") for e in root.iter()) or any("detail" in classes(e) or "on-accent" in classes(e)
                                                           for e in root.iter()):
        info["errors"].append('data-part、class="detail"、class="on-accent" 不再使用')
    if any(local(e) in ("text", "image") for e in rendered(root)):
        info["errors"].append("不用 <text> 和位图")
    if root.get("width") or root.get("height") or \
            re.split(r"[\s,]+", (root.get("viewBox") or "").strip()) != ["0", "0", "1024", "1024"]:
        info["errors"].append('根只写 viewBox="0 0 1024 1024"，不写宽高')
    rim = node(root, "rim") if root.get("data-variant") == "rim" else None
    stray = [c for c in root if local(c) in GRAPHIC and c not in (background, subject, rim)]
    if stray:
        info["errors"].append("底上不加任何东西：#background 和 #subject 之外还有 "
                              + ", ".join(f"<{local(c)}>" for c in stray[:3]))

    M = parse_transform(subject.get("transform")) if subject is not None else np.eye(3)
    info["matrix"] = M
    info["k"] = float(math.sqrt(abs(np.linalg.det(M[:2, :2]))))
    info["shape"] = subject.get("data-shape") if subject is not None else None
    info["category"] = subject.get("data-category") if subject is not None else None
    info["accent_kind"] = accent.get("data-accent") if accent is not None else None
    info["accent_band"] = info["accent_kind"] == "band"
    info["variant"] = root.get("data-variant")
    if info["category"] is not None and info["category"] not in CATEGORIES:
        info["errors"].append(f'data-category="{info["category"]}" 不认识：tools | image | video | ai | health | '
                              "finance，不属于这几类就不写")
    if info["accent_kind"] not in (None, "band"):
        info["errors"].append('data-accent 只能是 band（AI 斜带）')
    if info["variant"] not in (None,) + STORE_AB:
        info["errors"].append(f'data-variant="{info["variant"]}" 不认识：只有 render.py --store-ab 写的 '
                              "lighter | rim | tint")
    info["body_matrix"] = M @ chain_matrix(body, body, P) if body is not None else M
    info["accent_matrix"] = M @ chain_matrix(accent, accent, P) if accent is not None else M

    glow = node(root, "glow")
    if glow is not None or defn(root, "glow-blur") is not None:
        info["errors"].append("不再画辉光：删掉 #glow 和 #glow-blur（iOS 26 的阴影、高光由系统加；Icon Composer 里强调色组设 Chromatic 阴影）")
    if subject is not None:
        kids = [c for c in subject if local(c) in GRAPHIC]
        allowed = [e for e in (volume, body, accent) if e is not None]
        extra = [c for c in kids if c not in allowed and c is not glow]
        if extra:
            info["errors"].append("#subject 里只放 #volume、#body、#accent-shape，多了 "
                                  + ", ".join(f"<{local(c)}{' id=' + c.get('id') if c.get('id') else ''}>"
                                              for c in extra[:3]))
        if body is not None and accent is not None and body in kids and accent in kids \
                and kids.index(accent) < kids.index(body):
            info["errors"].append("#accent-shape 要画在 #body 后面")
        if volume is not None and body is not None and volume in kids and body in kids \
                and kids.index(volume) > kids.index(body):
            info["errors"].append("#volume 要画在 #body 前面（在线的下面）")
    sub_nodes = [e for e in rendered(subject)] if subject is not None else []

    # gradients and fills
    info["bg_grad"] = grad_info(grad(root, url_id(get_prop(background, "fill")) or "bg")) \
        if background is not None else grad_info(grad(root, "bg"))
    info["bg_fill"] = get_prop(background, "fill") if background is not None else None
    info["body_fill"] = get_prop(body, "fill") if body is not None else None
    info["body_stroke"] = get_prop(body, "stroke") if body is not None else None
    info["accent_fill"] = get_prop(accent, "fill") if accent is not None else None
    info["body_grad"] = grad_info(grad(root, url_id(info["body_stroke"]) or BODY_GRAD))
    info["accent_grad"] = grad_info(grad(root, url_id(info["accent_fill"]) or "accent"))
    sw = num(get_prop(body, "stroke-width")) if body is not None else None
    info["stroke_attr"] = sw
    info["linecap"] = get_prop(body, "stroke-linecap") if body is not None else None
    info["linejoin"] = get_prop(body, "stroke-linejoin") if body is not None else None
    # lines paint with the group's stroke only, the accent with its fill only: nothing of their own, nothing
    # see-through, no second line width
    own = []
    if body is not None:
        if (info["body_fill"] or "").strip().lower() != "none":
            own.append(f'#body fill={info["body_fill"]}（要 none：线稿不填色）')
        for e in rendered(body):
            if e is body:
                continue
            v = get_prop(e, "fill")
            if v is not None and v.strip().lower() not in ("inherit", "none"):
                own.append(f"<{local(e)}> fill={v}")
            v = get_prop(e, "stroke")
            if v is not None and v.strip().lower() not in ("inherit", f"url(#{BODY_GRAD})"):
                own.append(f"<{local(e)}> stroke={v}")
            w = num(get_prop(e, "stroke-width"))
            if w is not None and (sw is None or abs(w - sw) > 1e-6):
                own.append(f"<{local(e)}> stroke-width={w:g}")
            for a in ("opacity", "stroke-opacity", "fill-opacity"):
                o = num(get_prop(e, a))
                if o is not None and o < 1:
                    own.append(f"<{local(e)}> {a}={o:g}")
    if accent is not None:
        for e in rendered(accent):
            v = get_prop(e, "fill")
            if e is not accent and v is not None and v.strip().lower() not in ("inherit", "url(#accent)"):
                own.append(f"<{local(e)}> fill={v}")
            for a in ("opacity", "fill-opacity"):
                o = num(get_prop(e, a))
                if o is not None and o < 1:
                    own.append(f"<{local(e)}> {a}={o:g}")
    info["piece_fills"] = own
    vol = {"fill": None, "opacity": None, "problems": []}
    if volume is not None:
        vol["fill"] = norm_color(get_prop(volume, "fill") or "").upper() or None
        vol["opacity"] = num(get_prop(volume, "fill-opacity"), 1.0)
        if (get_prop(volume, "stroke") or "none").strip().lower() != "none":
            vol["problems"].append("#volume 不描边")
        if num(get_prop(volume, "opacity")) is not None:
            vol["problems"].append("透明度写 fill-opacity，不写 opacity")
        for e in rendered(volume):
            if e is volume:
                continue
            for a in ("fill", "stroke", "opacity", "fill-opacity", "stroke-width"):
                if get_prop(e, a) is not None and (get_prop(e, a) or "").strip().lower() != "inherit":
                    vol["problems"].append(f"<{local(e)}> 自带 {a}")
                    break
        if not [e for e in rendered(volume) if local(e) in GEOMETRY]:
            vol["problems"].append("#volume 里没有形状")
    info["volume"] = vol

    # glow and other filters
    info["glow"] = None
    if glow is not None:
        fid = url_id(get_prop(glow, "filter"))
        f = defn(root, fid) if fid else None
        g = {"tag": local(glow), "href": (href(glow) or "").lstrip("#"), "filter": fid,
             "first": subject is not None and [c for c in subject if local(c) in GRAPHIC][:1] == [glow],
             "sd": None, "opacity": None, "color": None, "offset": False}
        if f is not None:
            blur = next(iter(f.iter(q("feGaussianBlur"))), None)
            flood = next(iter(f.iter(q("feFlood"))), None)
            if blur is not None:
                sds = [num(v) for v in (blur.get("stdDeviation") or "").replace(",", " ").split()]
                g["sd"] = max(v for v in sds if v is not None) if any(v is not None for v in sds) else None
            if flood is not None:
                g["opacity"] = num(get_prop(flood, "flood-opacity"), 1.0)
                g["color"] = norm_color(get_prop(flood, "flood-color")).upper()
            g["offset"] = any(local(e) in ("feOffset", "feDropShadow") for e in f.iter())
        info["glow"] = g
    info["other_filters"] = [f"<{local(e)}{' id=' + e.get('id') if e.get('id') else ''}>"
                             for e in sub_nodes if get_prop(e, "filter") and e is not glow]

    info["masked"] = {name: any(get_prop(e, "mask") or get_prop(e, "clip-path") for e in el.iter())
                      for name, el in (("body", body), ("accent", accent), ("volume", volume)) if el is not None}
    return info


# ---------------------------------------------------------------- variants (SVG DOM rewrites)

def _set_stops(root, gid, stops, opacity=None):
    g = grad(root, gid)
    if g is None:
        return
    st = list(g.iter(q("stop")))
    for s, c in zip((st[0], st[-1]) if st else (), stops):
        set_prop(s, "stop-color", c)
    if opacity is not None:
        for s in st:
            set_prop(s, "stop-opacity", opacity)


def _remove(root, el):
    if el is not None:
        P = parents(root)
        if el in P:
            P[el].remove(el)


def _bg_gradient_id(root):
    bg = node(root, "background")
    return (url_id(get_prop(bg, "fill")) if bg is not None else None) or "bg"


def _set_volume(root, colour, opacity):
    v = node(root, "volume")
    if v is not None:
        set_prop(v, "fill", colour)
        set_prop(v, "fill-opacity", f"{opacity:g}")


def _drop_glow(root):
    """Older masters may still carry a glow: no look keeps it."""
    _remove(root, node(root, "glow"))


def _look(text, look):
    root = ET.fromstring(strip_xml_prolog(text))
    _remove(root, node(root, "rim"))
    _drop_glow(root)
    _set_stops(root, _bg_gradient_id(root), LOOKS[look]["bg"])
    body = node(root, "body")
    _set_stops(root, (url_id(get_prop(body, "stroke")) if body is not None else None) or BODY_GRAD, LOOKS[look]["body"])
    _set_volume(root, *LOOKS[look]["volume"])
    return serialize(prune_defs(root))


def make_light(text):
    """Light look: background #FBFCFE -> #E9EBEE, body #333538 -> #1E2022, volume #1E2022 at .07, accent unchanged."""
    return _look(text, "light")


def make_dark(text):
    """iOS Dark look: background #191C1F -> #0E1115, body #EDEEEF -> #BDBFC2, volume white at .10, accent unchanged."""
    return _look(text, "dark")


def make_mono(text):
    """Mono (iOS Tinted / Clear source, Android monochrome): no background, body white 100 %, accent white 50 %,
    volume white 30 %."""
    root = ET.fromstring(strip_xml_prolog(text))
    _remove(root, node(root, "background"))
    _remove(root, node(root, "rim"))
    _drop_glow(root)
    _set_volume(root, "#FFFFFF", MONO_VOLUME_OPACITY)
    body, accent = node(root, "body"), node(root, "accent-shape")
    _set_stops(root, (url_id(get_prop(body, "stroke")) if body is not None else None) or BODY_GRAD,
               ("#FFFFFF", "#FFFFFF"))
    _set_stops(root, (url_id(get_prop(accent, "fill")) if accent is not None else None) or "accent",
               ("#FFFFFF", "#FFFFFF"), MONO_ACCENT_OPACITY)
    return serialize(prune_defs(root))


def make_small(text, k):
    """64 px and below: the line 76 final px instead of 60 (stroke-width on #body, so every line follows); the volume
    stays."""
    root = ET.fromstring(strip_xml_prolog(text))
    _drop_glow(root)
    body = node(root, "body")
    if body is not None:
        set_prop(body, "stroke-width", f"{SMALL_STROKE / k:.2f}")
    return serialize(prune_defs(root))


def with_scale(text, s):
    """Scale the subject about the canvas centre (platform exports)."""
    root = ET.fromstring(strip_xml_prolog(text))
    subject = node(root, "subject")
    if subject is not None and abs(s - 1) > 1e-6:
        subject.set("transform", f"translate(512 512) scale({s:.4f}) translate(-512 -512) "
                    + (subject.get("transform") or ""))
    return serialize(root)


def without_background(text):
    root = ET.fromstring(strip_xml_prolog(text))
    _remove(root, node(root, "background"))
    _remove(root, node(root, "rim"))
    return serialize(root)


def flat_mark(text, line, volume=MARK_VOLUME["mark"]):
    """#subject alone, flat: no background; every line one solid `line` colour (the body gradient goes), the
    accent its main tone (the last stop of its gradient), the volume the line colour at `volume`, so the mark matches
    the UI's flat line icons and still reads as the icon's object."""
    root = ET.fromstring(strip_xml_prolog(without_background(text)))
    _drop_glow(root)
    _set_volume(root, line, volume)
    for layer, prop, colour in (("body", "stroke", lambda gid: line), ("accent-shape", "fill", None)):
        el = node(root, layer)
        for e in (el.iter() if el is not None else ()):
            gid = url_id(get_prop(e, prop))
            if gid is None:
                continue
            if colour is None:
                g = grad(root, gid)
                st = list(g.iter(q("stop"))) if g is not None else []
                c = get_prop(st[-1], "stop-color") if st else PALETTE["蓝"][1]
            else:
                c = colour(gid)
            set_prop(e, prop, c)
    return serialize(prune_defs(root))


def make_marks(renderer, text, pad=MARK_PAD):
    """In-app brand art for rian-app-theme: the flat marks of MARK_LINE, cropped to what is drawn plus `pad` (the same
    box for both). Scaled only as a whole, so the line stays 60 / 1024 of the icon.
    Returns {suffix: (svg text, RGBA image)}."""
    flats = {k: flat_mark(text, c, MARK_VOLUME[k]) for k, c in MARK_LINE.items()}
    ims = {k: renderer.image(v, 1024, transparent=True) for k, v in flats.items()}
    alpha = np.asarray(ims["mark"])[:, :, 3]
    ys, xs = np.nonzero(alpha > 2)
    x0, y0 = max(int(xs.min()) - pad, 0), max(int(ys.min()) - pad, 0)
    x1, y1 = min(int(xs.max()) + 1 + pad, 1024), min(int(ys.max()) + 1 + pad, 1024)
    out = {}
    for k, v in flats.items():
        root = ET.fromstring(strip_xml_prolog(v))
        root.set("viewBox", f"{x0} {y0} {x1 - x0} {y1 - y0}")
        root.set("width", str(x1 - x0))
        root.set("height", str(y1 - y0))
        out[k] = (serialize(root), ims[k].crop((x0, y0, x1, y1)))
    return out


def make_store_variant(text, kind, accent_name=None):
    """App Store A/B variant of the default look, marked data-variant on the root: lighter (the base one step
    lighter), rim (a thin bright rim inside Apple's icon shape) or tint (the base turned towards the accent's
    hue)."""
    root = ET.fromstring(strip_xml_prolog(text))
    root.set("data-variant", kind)
    bg_id = _bg_gradient_id(root)
    if kind == "lighter":
        _set_stops(root, bg_id, LIGHTER_BG)
    elif kind == "tint":
        _set_stops(root, bg_id, TINT_BG[accent_name])
    elif kind == "rim":
        defs = root.find(q("defs"))
        if defs is None:
            defs = ET.Element(q("defs"))
            root.insert(0, defs)
        g = ET.SubElement(defs, q("linearGradient"), {"id": "rim-fill", "x1": "0", "y1": "0", "x2": "0",
                                                      "y2": "1024", "gradientUnits": "userSpaceOnUse"})
        for off, c in zip(("0", "1"), RIM):
            ET.SubElement(g, q("stop"), {"offset": off, "stop-color": c})
        bg = node(root, "background")
        i = list(root).index(bg) + 1 if bg is not None and bg in list(root) else len(root)
        root.insert(i, ET.Element(q("path"), {"id": "rim", "fill": "url(#rim-fill)", "fill-rule": "evenodd",
                                              "d": "M 0 0 H 1024 V 1024 H 0 Z " + ios_path(inset=RIM_W)}))
    return serialize(root)


def with_rounded_background(text, d=None):
    """Replace the full-bleed background with a rounded tile (squircle by default)."""
    root = ET.fromstring(strip_xml_prolog(text))
    bg = node(root, "background")
    if bg is not None:
        P = parents(root)
        parent = P[bg]
        i = list(parent).index(bg)
        parent.remove(bg)
        parent.insert(i, ET.Element(q("path"), {"id": "background", "d": d or squircle_path(),
                                                "fill": get_prop(bg, "fill") or LOOKS["default"]["bg"][1]}))
    return serialize(root)


# ---------------------------------------------------------------- rasterising

HIDE = "{display:none!important}"
LAYER_CSS = {
    "body": "#background,#rim,#glow,#volume,#accent-shape" + HIDE,
    "accent": "#background,#rim,#glow,#volume,#body" + HIDE,
    "volume": "#background,#rim,#glow,#body,#accent-shape" + HIDE,
    "solid-volume": "#background,#rim,#glow,#body,#accent-shape" + HIDE + "#volume{fill-opacity:1!important}",
    "lines": "#background,#rim,#glow,#volume" + HIDE,   # lines and accent: what the size checks measure
}
MEASURE_CSS = {                                 # extra layers for the checks
    "full": "",
    "bg": "#subject" + HIDE,
}
OPAQUE = {"full", "bg"}

STROKE_JS = """() => {
  const subject = document.getElementById('subject');
  if (!subject) return [];
  const body = document.getElementById('body'), accent = document.getElementById('accent-shape');
  const GEO = 'path,circle,rect,ellipse,line,polyline,polygon,text,use';
  const SKIP = 'defs,mask,clipPath,pattern,marker,symbol';
  const out = [];
  for (const el of subject.querySelectorAll(GEO)) {
    if (el.closest(SKIP) || el.id === 'glow') continue;
    const cs = getComputedStyle(el);
    const volume = document.getElementById('volume');
    const layer = body && body.contains(el) ? 'body' : accent && (accent === el || accent.contains(el)) ? 'accent'
      : volume && (volume === el || volume.contains(el)) ? 'volume' : '';
    out.push({tag: el.tagName, id: el.id || '', layer: layer, stroke: cs.stroke, width: cs.strokeWidth,
              cap: cs.strokeLinecap, join: cs.strokeLinejoin, fill: cs.fill});
  }
  return out;
}"""


class Renderer:
    def __init__(self):
        if sync_playwright is None:
            sys.exit("playwright is not installed: pip install playwright && playwright install chromium")
        self.pw = sync_playwright().start()
        exe = find_chromium()
        self.browser = self.pw.chromium.launch(executable_path=exe) if exe else self.pw.chromium.launch()
        self.page = self.browser.new_page(viewport={"width": 1024, "height": 1024}, device_scale_factor=1)
        self.sheet_page = None
        self.size = 1024

    def close(self):
        self.browser.close()
        self.pw.stop()

    def load(self, svg_text, size=1024):
        if size != self.size:
            self.page.set_viewport_size({"width": size, "height": size})
            self.size = size
        html = ("<!doctype html><html><head><meta charset='utf-8'><style>html,body{margin:0;background:transparent}"
                f"svg{{display:block;width:{size}px;height:{size}px}}</style><style id='layer'></style></head>"
                f"<body>{strip_xml_prolog(svg_text)}</body></html>")
        self.page.set_content(html)

    def shot(self, css="", transparent=True):
        self.page.evaluate("c => { document.getElementById('layer').textContent = c; }", css)
        png = self.page.screenshot(clip={"x": 0, "y": 0, "width": self.size, "height": self.size},
                                   omit_background=transparent)
        return Image.open(io.BytesIO(png))

    def image(self, svg_text, size=1024, transparent=False):
        self.load(svg_text, size)
        im = self.shot("", transparent)
        return im.convert("RGBA") if transparent else im.convert("RGB")

    def layers(self, svg_text, names):
        """Separately rasterised layers at 1024, RGBA arrays (transparent except "full" and "bg")."""
        out = {}
        self.load(svg_text, 1024)
        for n in names:
            css = LAYER_CSS.get(n, MEASURE_CSS.get(n))
            out[n] = np.asarray(self.shot(css, transparent=n not in OPAQUE).convert("RGBA"))
        return out

    def strokes(self, svg_text):
        """Computed stroke, caps, joins and fill of every shape in #subject outside masks, and its layer."""
        self.load(svg_text, 1024)
        return self.page.evaluate(STROKE_JS)

    def sheet(self, html, path):
        if self.sheet_page is None:
            self.sheet_page = self.browser.new_page(device_scale_factor=2, viewport={"width": 1240, "height": 900})
        self.sheet_page.set_content(html)
        self.sheet_page.locator(".sheet").screenshot(path=str(path))


# ---------------------------------------------------------------- numpy measurement helpers

def label(mask):
    """8-connected components of a bool mask (run-length union-find, numpy only). -> (labels, count)"""
    H, W = mask.shape
    pad = np.zeros((H, W + 2), np.int8)
    pad[:, 1:-1] = mask
    d = np.diff(pad, axis=1)
    sy, sx = np.nonzero(d == 1)
    _, ex = np.nonzero(d == -1)
    lab = np.zeros((H, W), np.int32)
    n = len(sy)
    if n == 0:
        return lab, 0
    parent = list(range(n))

    def find(i):
        r = i
        while parent[r] != r:
            r = parent[r]
        while parent[i] != r:
            parent[i], i = r, parent[i]
        return r

    starts = np.searchsorted(sy, np.arange(H + 1)).tolist()
    sxl, exl = sx.tolist(), ex.tolist()
    for y in range(1, H):
        i, i1, j, j1 = starts[y - 1], starts[y], starts[y], starts[y + 1]
        while i < i1 and j < j1:
            if sxl[i] <= exl[j] and sxl[j] <= exl[i]:
                a, b = find(i), find(j)
                if a != b:
                    parent[b] = a
            if exl[i] < exl[j]:
                i += 1
            else:
                j += 1
    ids = {}
    run_id = np.array([ids.setdefault(find(i), len(ids) + 1) for i in range(n)], np.int32)
    lengths = ex - sx
    rows = np.repeat(sy, lengths)
    cols = np.arange(lengths.sum()) - np.repeat(np.cumsum(lengths) - lengths, lengths) + np.repeat(sx, lengths)
    lab[rows, cols] = np.repeat(run_id, lengths)
    return lab, len(ids)


def components(mask, min_area=MIN_PIECE):
    """Connected pieces of a mask, largest first, specks dropped."""
    lab, n = label(mask)
    if n == 0:
        return []
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    keep = sorted((i for i in range(1, n + 1) if sizes[i] >= min_area), key=lambda i: -sizes[i])
    return [lab == i for i in keep]


def fill_holes(mask):
    lab, _ = label(~mask)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    return mask | ((~mask) & ~np.isin(lab, border))


def dilate(mask, r=1):
    out = mask.copy()
    for _ in range(r):
        m = out.copy()
        m[1:, :] |= out[:-1, :]
        m[:-1, :] |= out[1:, :]
        m[:, 1:] |= out[:, :-1]
        m[:, :-1] |= out[:, 1:]
        out = m
    return out


def octagon_morph(mask, r, grow, regular=False):
    """Erode (grow=False) or dilate (grow=True) by an octagon of radius r built from 4- and 8-neighbour steps.
    Default: the steps alternate, so the octagon reaches r along the axes and 1.06 r along the diagonals.
    regular=True mixes them 1.414 : 1, which gives the same apothem r in all eight directions (a 45 deg piece
    is judged like an upright one)."""
    m = mask
    square = round(r * (math.sqrt(2) - 1)) if regular else r // 2
    for i in range(r):
        n = m.copy()
        shifts = [((1, 0), (0, 0)), ((0, 0), (1, 0)), ((0, 1), (0, 0)), ((0, 0), (0, 1))]
        if ((i + 1) * square // r > i * square // r) if regular else i % 2:
            shifts += [((1, 1), (0, 0)), ((0, 0), (1, 1)), ((1, 0), (0, 1)), ((0, 1), (1, 0))]
        H, W = m.shape
        for (ay, ax), (by, bx) in shifts:
            dst = n[ay:H - by, ax:W - bx]
            src = m[by:H - ay, bx:W - ax]
            if grow:
                dst |= src
            else:
                dst &= src
        m = n
    return m


def disk_conv(mask, r):
    """Count of mask pixels under a disk of radius r around every pixel (FFT), and the disk's size."""
    H, W = mask.shape
    P = r + 2
    a = np.zeros((H + 2 * P, W + 2 * P), np.float32)
    a[P:P + H, P:P + W] = mask
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    ker = ((xx ** 2 + yy ** 2) <= r * r + r).astype(np.float32)
    kp = np.zeros_like(a)
    kp[:2 * r + 1, :2 * r + 1] = ker
    kp = np.roll(kp, (-r, -r), (0, 1))
    c = np.fft.irfft2(np.fft.rfft2(a) * np.fft.rfft2(kp), a.shape)
    return c[P:P + H, P:P + W], ker.sum()


def disk_dilate(mask, r):
    return disk_conv(mask, r)[0] > 0.5


def disk_erode(mask, r):
    c, s = disk_conv(mask, r)
    return c > s - 0.5


def disk_close(mask, r):
    return disk_erode(disk_dilate(mask, r), r)


def crop(mask, pad_):
    """mask cropped to its bounding box plus pad_ on every side, and the offset (x0, y0)."""
    x0, y0, x1, y1 = bbox(mask)
    out = np.zeros((y1 - y0 + 2 * pad_, x1 - x0 + 2 * pad_), bool)
    out[pad_:-pad_, pad_:-pad_] = mask[y0:y1, x0:x1]
    return out, (x0 - pad_, y0 - pad_)


def top_protrusion(filled):
    """Body of the silhouette without thin top parts (button, binder rings, handle), or None.
    An opening removes everything thinner than PROTRUSION_W; it counts as a top protrusion only when
    the body keeps most of the area and only the top edge moved."""
    x0, y0, x1, y1 = bbox(filled)
    r = PROTRUSION_W // 2
    pad_ = r + 4
    c, _ = crop(filled, pad_)
    opened = octagon_morph(octagon_morph(c, r, False), r, True)
    if not opened.any() or opened.sum() < 0.75 * c.sum():
        return None
    ox0, oy0, ox1, oy1 = bbox(opened)
    ox0, ox1, oy0, oy1 = ox0 - pad_ + x0, ox1 - pad_ + x0, oy0 - pad_ + y0, oy1 - pad_ + y0
    if oy0 - y0 > 24 and (y1 - oy1) <= 12 and (ox0 - x0) <= 12 and (x1 - ox1) <= 12:
        # area centroid of the body: insensitive to the small bump the opening leaves where a stem joins
        ys, xs = np.nonzero(opened)
        cx, cy = xs.mean() + 0.5 - pad_ + x0, ys.mean() + 0.5 - pad_ + y0
        return {"centre": (float(cx), float(cy)), "height": oy0 - y0, "bbox": [ox0, oy0, ox1, oy1]}
    return None


def nearest(P, Q, chunk=512):
    """Distance from each point of P to the nearest point of Q, and that point's index."""
    if len(P) == 0:
        return np.zeros(0), np.zeros(0, int)
    if len(Q) == 0:
        return np.full(len(P), np.inf), np.zeros(len(P), int)
    P = P - 512.0
    Q = Q - 512.0
    q2 = (Q ** 2).sum(1)
    dist = np.empty(len(P))
    idx = np.empty(len(P), int)
    for i in range(0, len(P), chunk):
        p = P[i:i + chunk]
        d2 = (p ** 2).sum(1)[:, None] + q2[None, :] - 2.0 * (p @ Q.T)
        j = d2.argmin(1)
        dist[i:i + chunk] = np.sqrt(np.maximum(d2[np.arange(len(p)), j], 0))
        idx[i:i + chunk] = j
    return dist, idx


def hull_points(mask):
    """Convex hull of a mask's pixel squares, as a polygon (pixel-corner coordinates)."""
    rows = np.nonzero(mask.any(1))[0]
    if len(rows) == 0:
        return []
    sub = mask[rows]
    W = mask.shape[1]
    x0 = sub.argmax(1)
    x1 = W - sub[:, ::-1].argmax(1)
    pts = sorted(set(zip(x0.tolist(), rows.tolist())) | set(zip(x0.tolist(), (rows + 1).tolist()))
                 | set(zip(x1.tolist(), rows.tolist())) | set(zip(x1.tolist(), (rows + 1).tolist())))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def hull_area(mask):
    h = hull_points(mask)
    return abs(sum(h[i][0] * h[(i + 1) % len(h)][1] - h[(i + 1) % len(h)][0] * h[i][1]
                   for i in range(len(h)))) / 2 if h else 0.0


def hull_mask(mask):
    im = Image.new("L", mask.shape[::-1], 0)
    h = hull_points(mask)
    if h:
        ImageDraw.Draw(im).polygon(h, fill=255)
    return np.asarray(im) > 127


def bbox(mask):
    ys, xs = np.nonzero(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def centre_of(mask):
    ys, xs = np.nonzero(mask)
    return float(xs.mean() + 0.5), float(ys.mean() + 0.5)


def edge_points(cov):
    """Sub-pixel points where a coverage map crosses 0.5, interpolated between 4-neighbour pixel centres.
    Distances between these points are clear gaps directly (no pixel-centre offset)."""
    out = []
    for axis in (1, 0):
        a = cov[:, :-1] if axis == 1 else cov[:-1, :]
        b = cov[:, 1:] if axis == 1 else cov[1:, :]
        ys, xs = np.nonzero((a >= 0.5) != (b >= 0.5))
        va, vb = a[ys, xs], b[ys, xs]
        t = (0.5 - va) / np.where(vb != va, vb - va, 1)
        if axis == 1:
            out.append(np.stack([xs + 0.5 + t, ys + 0.5], 1))
        else:
            out.append(np.stack([xs + 0.5, ys + 0.5 + t], 1))
    return np.concatenate(out).astype(np.float64) if out else np.zeros((0, 2))


def lab_L(rgb):
    """CIE L* of sRGB pixels (any shape ending in 3)."""
    c = np.asarray(rgb, np.float64) / 255
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    Y = c @ np.array([0.2126, 0.7152, 0.0722])
    return np.where(Y > 216 / 24389, 116 * np.cbrt(Y) - 16, Y * 24389 / 27)


def rel_lum(rgb):
    c = np.asarray(rgb, np.float64) / 255
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return float(c @ np.array([0.2126, 0.7152, 0.0722]))


def contrast(a, b):
    la, lb = rel_lum(a), rel_lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def hex_rgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float64)


XYZ = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                [0.0193339, 0.1191920, 0.9503041]])
WHITE = np.array([0.95047, 1.0, 1.08883])     # D65


def rgb_lch(rgb):
    """CIE LCh (D65) of sRGB pixels (any shape ending in 3) -> L, C, h in degrees."""
    c = np.asarray(rgb, np.float64) / 255
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    t = (c @ XYZ.T) / WHITE
    f = np.where(t > 216 / 24389, np.cbrt(t), (24389 / 27 * t + 16) / 116)
    a, b = 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])
    return 116 * f[..., 1] - 16, np.hypot(a, b), np.degrees(np.arctan2(b, a)) % 360


def lch_rgb(L, C, h):
    """sRGB 0..255 of one CIE LCh colour; out of gamut, the chroma is lowered until it fits."""
    inv = np.linalg.inv(XYZ)

    def linear(c):
        fy = (L + 16) / 116
        f = np.array([fy + c * math.cos(math.radians(h)) / 500, fy, fy - c * math.sin(math.radians(h)) / 200])
        t = np.where(f ** 3 > 216 / 24389, f ** 3, (116 * f - 16) * 27 / 24389)
        t[1] = fy ** 3 if L > 8 else L * 27 / 24389
        return inv @ (t * WHITE)

    def fits(c):
        v = linear(c)
        return bool(np.all((v >= -1e-4) & (v <= 1 + 1e-4)))

    lo, hi = (float(C), float(C)) if fits(C) else (0.0, float(C))
    while hi - lo > 0.01:
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if fits(mid) else (lo, mid)
    v = np.clip(linear(lo), 0, 1)
    return np.round(np.where(v <= 0.0031308, 12.92 * v, 1.055 * v ** (1 / 2.4) - 0.055) * 255)


def seed_hue(im):
    """The wallpaper's seed hue, approximated: hue histogram of its colourful pixels (C >= 12) weighted by
    chroma, smoothed over 30°, the peak refined by the weighted mean of the hues within 15° of it."""
    _, C, h = rgb_lch(np.asarray(im.convert("RGB").resize((128, 128), Image.BILINEAR)))
    sel = C >= 12
    if not sel.any():
        return 265.0
    C, h = C[sel], h[sel]
    hist = np.bincount(h.astype(int) % 360, weights=C, minlength=360)
    peak = int(np.convolve(np.concatenate([hist[-15:], hist, hist[:15]]), np.ones(31), "valid").argmax())
    d = (h - peak + 180) % 360 - 180
    near = np.abs(d) <= 15
    return float((peak + (d[near] * C[near]).sum() / C[near].sum()) % 360)


def themed_colors(kind):
    """Android themed icon in the light or dark system theme, seed hue from the matching sample wallpaper:
    (background rgb, glyph rgb, seed hue)."""
    hue = seed_hue(wallpaper(kind))
    (bp, bt), (fp, ft) = THEMED_TONES[kind]
    return lch_rgb(bt, TONAL_CHROMA[bp], hue), lch_rgb(ft, TONAL_CHROMA[fp], hue), hue


# ---------------------------------------------------------------- measuring one icon

def silhouette(union):
    """Gaps narrower than a line width closed with a radius-30 disk, then holes filled."""
    return fill_holes(disk_close(union, CLOSE_R) | union)


def tide_reference(renderer, path, cache={}):
    """Silhouette, hull, r_max and ink of the new Tide, measured from its SVG (built-in numbers as fallback),
    plus its SVG text for the side-by-side cell (None when unusable)."""
    key = str(path)
    if key in cache:
        return cache[key]
    ref, text = None, None
    why = "没有这个文件"
    if path.exists():
        try:
            text, root = load_svg(path)
            info = static_info(root)
            if info["fatal"] or info["errors"] or not info.get("stroke_attr"):
                why = "不是石墨线稿风格（缺 #body / #accent-shape，或 #body 没有描边）"
                text = None
            else:
                L = renderer.layers(text, ["body", "accent"])
                union = (L["body"][..., 3] >= 128) | (L["accent"][..., 3] >= 128)
                if union.any():
                    ys, xs = np.nonzero(union)
                    sil = silhouette(union)
                    ref = {"silhouette": float(sil.sum()), "hull": float(hull_area(sil)),
                           "r_max": float(np.sqrt((xs + 0.5 - 512) ** 2 + (ys + 0.5 - 512) ** 2).max()),
                           "ink": float(union.sum()), "source": str(path)}
        except (OSError, ValueError) as e:
            why, text = str(e), None
    if ref is None:
        print(f"WARNING Tide 参考 {path}: {why}；用内置的新 Tide 数值", file=sys.stderr)
        ref = dict(TIDE_FALLBACK, source="built-in")
    cache[key] = (ref, text)
    return ref, text


def check(key, label_, value, target, status, **data):
    return {"key": key, "label": label_, "value": value, "target": target, "status": status, "data": data}


def ok(cond):
    return "PASS" if cond else "FAIL"


def at(p):
    return f"@ ({p[0]:.0f}, {p[1]:.0f})"


def keyline_note(shape, w, h, body):
    """Outer box against the shape's keyline, in percent. Keylines are drafting sizes: INFO only,
    the silhouette or hull ratio decides."""
    bw, bh = (body["bbox"][2] - body["bbox"][0], body["bbox"][3] - body["bbox"][1]) if body else (w, h)
    if shape == "open":
        base = "wide" if w > 1.1 * h else "tall" if h > 1.1 * w else "square"
        kw, kh = (round(v * OPEN_EXTRA) for v in KEYLINE_WH[base])
        target = f"关键线 {kw} × {kh}（{KEYLINE_NAME[base]} +10%）"
    else:
        kw, kh = KEYLINE_WH[shape]
        target = f"关键线 {KEYLINES[shape]}"
    if shape == "circle":
        over = f"比关键线 {max(bw, bh) / kw - 1:+.0%}"
    else:
        over = f"比关键线 宽 {bw / kw - 1:+.0%} 高 {bh / kh - 1:+.0%}"
    box = f"外框 {w} × {h}" + (f" · 不计凸起 {bw} × {bh}" if body else "")
    return f"{shape} · {box} · {over}", target


def gradient_check(key, label_, g, M, mask, span, name):
    """Vertical userSpaceOnUse gradient of `span` final px, centred on the mask's vertical extent."""
    target = f"竖直，跨度 {span} ± {GRAD_TOL}，居中"
    if g is None:
        return check(key, label_, f"缺 #{name} 渐变", target, "FAIL"), {}
    if g["tag"] != "linearGradient" or g["units"] != "userSpaceOnUse" or g["percent"] or not g["explicit"]:
        return check(key, label_, "要 linearGradient，userSpaceOnUse，x1 y1 x2 y2 写绝对坐标", target, "FAIL"), {}
    G = M @ g["transform"]
    X1, Y1 = (G @ [g["x1"], g["y1"], 1])[:2]
    X2, Y2 = (G @ [g["x2"], g["y2"], 1])[:2]
    s = abs(Y2 - Y1)
    _, y0, _, y1 = bbox(mask)
    mid = (y0 + y1) / 2
    dc = (Y1 + Y2) / 2 - mid
    dc = 0.0 if abs(dc) < 0.5 else dc
    vertical = abs(X2 - X1) < 0.5 and Y2 > Y1
    good = vertical and abs(s - span) <= GRAD_TOL and abs(dc) <= GRAD_TOL
    Gi = np.linalg.inv(G)
    want = [float((Gi @ [0, mid - span / 2, 1])[1]), float((Gi @ [0, mid + span / 2, 1])[1])]
    val = f"跨度 {s:.0f} px · 中心差 {dc:+.0f} px" + ("" if vertical else " · 不是从上到下的竖直渐变")
    if not good:
        val += f" → 改 y1 {want[0]:.1f} y2 {want[1]:.1f}"
    return check(key, label_, val, target, ok(good), y1_y2=want), {f"{name}_gradient_span": s,
                                                                    f"{name}_gradient_offset": dc}


def small_signature(renderer, small_svg):
    """Separate shapes and enclosed holes of the small version at 1024 and at 40, 29 and 16 px, split by a lightness
    threshold between the graphite background (L* 13) and the lines and accent (L* 50 and up). A gap that clogs
    merges two shapes; a hole that clogs disappears. A store variant's rim is left out."""
    root = ET.fromstring(strip_xml_prolog(small_svg))
    _remove(root, node(root, "rim"))
    _remove(root, node(root, "volume"))   # the signature is about the lines and the accent
    im = renderer.image(serialize(root), 1024)
    bg_mid = (hex_rgb(LOOKS["default"]["bg"][0]) + hex_rgb(LOOKS["default"]["bg"][1])) / 2
    thr = (float(lab_L(bg_mid)) + 50) / 2
    out = {}
    for s in (1024, SMALL_CHECK, SMALL_INFO, SMALL_FAVICON):
        L_ = lab_L(np.asarray(im if s == 1024 else im.resize((s, s), Image.LANCZOS)))
        ink = L_ > thr
        least = (1024 / SMALL_CHECK) ** 2 if s == 1024 else 1
        lab, n = label(ink)
        sizes = np.bincount(lab.ravel(), minlength=n + 1)
        shapes = int(sum(1 for i in range(1, n + 1) if sizes[i] >= least))
        holes = fill_holes(ink) & ~ink
        hl, hn = label(holes)
        hs = np.bincount(hl.ravel(), minlength=hn + 1)
        out[s] = (shapes, int(sum(1 for i in range(1, hn + 1) if hs[i] >= least)))
    return out


TEMPLATE_TRANSFORM = re.compile(
    r"^\s*translate\(\s*512[\s,]+512\s*\)\s*scale\(\s*([-+\d.eE]+)\s*\)\s*translate\(\s*-512[\s,]+-512\s*\)"
    r"\s*(?:translate\(\s*([-+\d.eE]+)(?:[\s,]+([-+\d.eE]+))?\s*\))?\s*$")


def move_hint(transform, k, dx, dy):
    """What to write so the subject moves by (dx, dy) final px."""
    m = TEMPLATE_TRANSFORM.match(transform or "")
    if m:
        tx, ty = float(m.group(2) or 0), float(m.group(3) or 0)
        return f" → translate 改为 ({tx + dx / k:.1f} {ty + dy / k:.1f})"
    return f" → 整体移 ({dx:+.1f}, {dy:+.1f}) 终像素（源坐标 ÷ k）"


def scale_hint(k, ratio, target=1.0):
    """What k brings an area ratio to the target (areas scale with k²)."""
    k2 = k * math.sqrt(target / ratio)
    return (f" → k 改为 {k2:.3g}（stroke-width 改为 {STROKE / k2:.1f}，圆角和强调色用 shapes.py --k {k2:.3g} 重出；"
            "translate 跟着重调）")


def measure(renderer, text, root, name, ref):
    info = static_info(root)
    k = info["k"]
    C = []
    raw = {"k": k, "data_shape": info["shape"]}
    if info["errors"]:
        C.append(check("structure", "结构", "；".join(info["errors"]), "construction.md 的 id、图层和顺序", "FAIL"))
    if info["fatal"]:
        return {"name": name, "checks": C, "raw": raw, "info": info}

    # the line: one width (60 final px) on #body, round caps and joins, nothing filled in the body, no stroke on
    # the accent (computed styles, so inherited and CSS strokes count)
    st = renderer.strokes(text)
    probs = []
    sw = info["stroke_attr"]
    eff = sw * k if sw is not None else None
    raw["stroke_effective"] = eff
    if eff is None:
        probs.append("#body 没写 stroke-width")
    elif abs(eff - STROKE) > STROKE_TOL:
        probs.append(f"线宽 {eff:.1f} px，stroke-width 要写 {STROKE / k:.2f}（{STROKE:.0f} ÷ k）")
    lines = [x for x in st if x["layer"] == "body"]
    widths = sorted({x["width"] for x in lines})
    if len(widths) > 1:
        probs.append("线宽不统一：" + "、".join(widths[:3]))
    for key_, want, label_ in (("cap", "round", "端头"), ("join", "round", "拐角")):
        bad = [x for x in lines if x[key_] != want and x["stroke"] != "none"]
        if bad:
            probs.append(f"{label_}要 round：<{bad[0]['tag']}> 是 {bad[0][key_]}")
    nostroke = [x for x in lines if x["stroke"] == "none"]
    if nostroke:
        probs.append(f"#body 里有 {len(nostroke)} 处没有描边（<{nostroke[0]['tag']}>）")
    filled = [x for x in lines if x["fill"] != "none"]
    if filled:
        probs.append(f"#body 里有填色（<{filled[0]['tag']}> fill {filled[0]['fill']}）：线稿不填色，填色只给强调色")
    acc_st = [x for x in st if x["layer"] == "accent" and x["stroke"] != "none"]
    if acc_st:
        probs.append(f"强调色带描边（<{acc_st[0]['tag']}>）：强调色是一块填色，不描边")
    stray = [x for x in st if not x["layer"]]
    if stray:
        probs.append(f"#volume、#body、#accent-shape 之外有图形 <{stray[0]['tag']}>")
    vol_st = [x for x in st if x["layer"] == "volume" and x["stroke"] != "none"]
    if vol_st:
        probs.append(f"体积层带描边（<{vol_st[0]['tag']}>）：#volume 只填色")
    val = (f"{eff:.1f} px（{sw:g} × {k:.3g}）" if eff is not None else "—") + f" · {len(lines)} 段线"
    C.append(check("stroke", "线宽", val + ("；" + "；".join(probs) if probs else " · 圆头圆角"),
                   f"{STROKE:.0f} ± {STROKE_TOL:.0f}，一种线宽，圆头圆角", ok(not probs)))

    # palette: every stop of the three gradients is one of the allowed pair (no third colour, no light band,
    # no see-through stop); the lines paint only with the body gradient, the accent only with its own
    def stop_note(g, pair):
        """'' when the gradient's stops are the pair (first and last) and nothing else, else what is wrong."""
        if not g:
            return "缺渐变"
        st_ = g["stops"]
        if len(st_) < 2 or (st_[0], st_[-1]) != tuple(pair):
            return "→".join(st_[:1] + st_[-1:]) or "没有 stop"
        extra = [c for c in st_[1:-1] if c not in pair]
        if extra:
            return f"中间多了 {', '.join(extra[:2])}（只能有这两个色值：第二个颜色、亮带都不行）"
        if any(o < 1 for o in g.get("opacities", [])):
            return "stop 半透明"
        return ""

    parts, good = [], True
    acs = info["accent_grad"]
    acc_ends = tuple(acs["stops"][:1] + acs["stops"][-1:]) if acs else ()
    acc_name = next((n_ for n_, v in PALETTE.items() if acc_ends == v), None)
    # the base is the fixed graphite; only the App Store A/B variants written by --store-ab change it
    variant = info["variant"]
    bg_pair = {"lighter": LIGHTER_BG, "tint": TINT_BG.get(acc_name)}.get(variant) or LOOKS["default"]["bg"]
    bg_label = "底" + (f"（A/B {STORE_NAME[variant]}）" if variant in STORE_NAME else "")
    bgs = info["bg_grad"]
    bg_vertical = bool(bgs) and bgs["tag"] == "linearGradient" and bgs["x1"] == bgs["x2"] and bgs["y2"] > bgs["y1"]
    note = stop_note(bgs, bg_pair)
    if variant == "tint" and acc_name not in TINT_BG:
        parts.append(f"{bg_label} 灰和色板外的强调色没有类别色变体")
        good = False
    elif bg_vertical and not note and url_id(info["bg_fill"]):
        parts.append(f"{bg_label} {bg_pair[0]}→{bg_pair[1]}")
    else:
        parts.append(f"{bg_label} " + (note or str(info["bg_fill"]))
                     + ("" if bg_vertical else " 要从上到下的竖直线性渐变")
                     + f" 应为 {bg_pair[0]}→{bg_pair[1]}")
        good = False
    if variant == "rim":
        note = stop_note(grad_info(grad(root, "rim-fill")), RIM)
        parts.append(f"亮边 {RIM[0]}→{RIM[1]}" if not note else f"亮边 {note} 应为 {RIM[0]}→{RIM[1]}")
        good = good and not note
    bds = info["body_grad"]
    note = stop_note(bds, LOOKS["default"]["body"])
    if not note and url_id(info["body_stroke"]) == BODY_GRAD:
        parts.append(f"线 {LOOKS['default']['body'][0]}→{LOOKS['default']['body'][1]}")
    else:
        if note:
            parts.append(f"线 {note} 应为 {LOOKS['default']['body'][0]}→{LOOKS['default']['body'][1]}")
        else:
            parts.append(f"#body 的 stroke 是 {info['body_stroke']}，要写 url(#{BODY_GRAD})")
        good = False
    if info["piece_fills"]:
        parts.append("单个元素自带颜色、线宽或透明度：" + ", ".join(info["piece_fills"][:3]))
        good = False
    note = stop_note(acs, PALETTE[acc_name]) if acc_name else ("→".join(acc_ends) or "缺渐变") + " 不在色板"
    if not note and url_id(info["accent_fill"]) == "accent":
        parts.append(f"强调色 {acc_name} {acc_ends[0]}→{acc_ends[1]}")
    else:
        parts.append("强调色 " + (note or f"fill 写 url(#accent)，不是 {info['accent_fill']}"))
        good = False
    vol = info.get("volume") or {}
    if vol.get("fill") is not None:
        v_ok = vol["fill"] == VOLUME_FILL and abs((vol["opacity"] or 0) - VOLUME_OPACITY) <= VOLUME_TOL \
            and not vol["problems"]
        parts.append(f"体积层 {vol['fill']} {vol['opacity']:g}" + ("" if v_ok else
                     f" 应为 fill {VOLUME_FILL}、fill-opacity {VOLUME_OPACITY:g}，平涂"
                     + ("；" + "；".join(vol["problems"][:2]) if vol["problems"] else "")))
        good = good and v_ok
    raw["accent_colour"] = acc_name
    C.append(check("palette", "颜色", " · ".join(parts), "默认外观 + 六色表", ok(good)))
    if variant:
        C.append(check("variant", "商店变体", f'data-variant="{variant}"：--store-ab 写出的 A/B 变体，不是母版',
                       "母版不写 data-variant；变体只进产品页优化，不出 --export", "INFO"))

    L = renderer.layers(text, ["body", "accent", "volume", "full", "bg"])
    body_c = L["body"][..., 3].astype(np.float32) / 255
    acc_c = L["accent"][..., 3].astype(np.float32) / 255
    body, acc = body_c >= 0.5, acc_c >= 0.5
    union = body | acc
    if not union.any() or not acc.any() or not body.any():
        what = "没有画出任何像素" if not union.any() else ("强调色没有像素" if not acc.any() else "线稿没有像素")
        C.append(check("subject", "主体", what, "—", "FAIL"))
        return {"name": name, "checks": C, "raw": raw, "info": info}

    sil = silhouette(union)
    hull = float(hull_area(sil))
    sil_area = float(sil.sum())
    lines_ = components(body)
    acc_pieces = components(acc)
    raw.update(parts=len(lines_), accent_pieces=len(acc_pieces))

    # parts: separate lines (each a connected stroke) and the one accent
    C.append(check("parts", "线条段数", f"{len(lines_)} 段相连的线", f"1–{PARTS_MAX}（一个隐喻，29 px 下不碎）",
                   ok(1 <= len(lines_) <= PARTS_MAX)))
    C.append(check("accent_count", "强调色块数", f"{len(acc_pieces)} 块", "1（只有一处）", ok(len(acc_pieces) == 1)))

    # clear gap between separate lines: at least one line width
    pts = [edge_points(np.where(dilate(p, 2), body_c, 0)) for p in lines_]
    gaps = []
    for i in range(len(lines_)):
        for j in range(i + 1, len(lines_)):
            d, idx = nearest(pts[i], pts[j])
            if len(d):
                t = int(d.argmin())
                pa, pb = pts[i][t], pts[j][idx[t]]
                gaps.append((float(d[t]), ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)))
    if gaps:
        g, where = min(gaps)
        raw["line_gap"] = g
        C.append(check("line_gap", "线间净空", f"最近 {g:.1f} px {at(where)} · {len(gaps)} 对",
                       f"≥ {GAP_LINE:.0f}（一个线宽）", ok(g >= GAP_LINE - GAP_TOL)))
    else:
        C.append(check("line_gap", "线间净空", "只有一段相连的线", f"≥ {GAP_LINE:.0f}（一个线宽）", "PASS"))

    # pinch: inside one line drawing, gaps narrower than a line width (a tight acute join, two strokes running
    # close side by side, a hole too small) close up with a radius-30 disk; a corridor bigger than 3000 px² clogs
    cp, (ox, oy) = crop(body, PINCH_R + 4)
    added = disk_close(cp, PINCH_R) & ~cp
    worst = None
    for a_ in components(added, 1):
        area = float(a_.sum())
        if area > PINCH_AREA and (worst is None or area > worst[0]):
            cx, cy = centre_of(a_)
            worst = (area, (cx + ox, cy + oy))
    if worst:
        raw["pinch"] = worst[0]
        C.append(check("pinch", "线间夹缝", f"窄于 {GAP_LINE:.0f} 的夹缝 {at(worst[1])}（{worst[0] / 1000:.1f}k px²）："
                       "拉开两条线、把锐角拐角放宽到 ≥ 45°，或把小孔放大", f"夹缝 ≤ {PINCH_AREA / 1000:.0f}k px²", "FAIL"))
    else:
        C.append(check("pinch", "线间夹缝", "没有会糊住的夹缝", f"夹缝 ≤ {PINCH_AREA / 1000:.0f}k px²", "PASS"))

    # the accent keeps clear of every line
    inter = int((body & acc).sum())
    ea, eb = edge_points(acc_c), edge_points(body_c)
    d_ab, i_ab = nearest(ea, eb)
    t = int(d_ab.argmin())
    gap_ab = float(d_ab[t])
    pa, pb = ea[t], eb[i_ab[t]]
    at_ab = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
    raw.update(accent_gap=gap_ab, overlap_px=inter)
    if inter > OVERLAP_MAX * acc.sum():
        C.append(check("accent_gap", "强调色到线", f"压在线上 {at(at_ab)}（交集 {inter} px²）",
                       f"净空 ≥ {GAP_ACCENT:.0f}（一个线宽），不碰线", "FAIL"))
    else:
        C.append(check("accent_gap", "强调色到线", f"{gap_ab:.1f} px {at(at_ab)}", f"净空 ≥ {GAP_ACCENT:.0f}（一个线宽），不碰线",
                       ok(gap_ab >= GAP_ACCENT - GAP_TOL)))

    # the volume: inside the silhouette, its edge hidden under the lines (it is the area the lines' centre line closes);
    # the accent may lie on it
    vol_m = L["volume"][..., 3] > VOLUME_ALPHA
    if vol_m.any():
        v_area = float(vol_m.sum())
        spill = float((vol_m & ~dilate(hull_mask(sil), 2)).sum()) / v_area   # open drawings: the hull
        edge = vol_m & ~disk_erode(vol_m, 1)
        hidden = float((edge & dilate(union, 3)).sum()) / max(float(edge.sum()), 1.0)
        cover = v_area / hull
        raw.update(volume_spill=spill, volume_edge_hidden=hidden, volume_cover=cover)
        good = spill <= VOLUME_SPILL and hidden >= VOLUME_EDGE
        hint = []
        if spill > VOLUME_SPILL:
            hint.append(f"超出剪影 {spill * 100:.1f} %")
        if hidden < VOLUME_EDGE:
            hint.append("边没压在线下：#volume 用线的中线围成的形状（同一个 d、同一个圆）")
        C.append(check("volume", "体积层", f"占凸包 {cover * 100:.0f} % · 边在线下 {hidden * 100:.0f} % · 溢出 {spill * 100:.1f} %"
                       + ("；" + "；".join(hint) if hint else ""),
                       f"边 ≥ {VOLUME_EDGE * 100:.0f} % 在线或强调色下，溢出 ≤ {VOLUME_SPILL * 100:.0f} %", ok(good)))
    elif info.get("no_volume"):
        C.append(check("volume", "体积层", 'data-volume="none"：物件没有「里面」，只有线和强调色',
                       "物件里面一层半透明实形；没有「里面」时可以不画", "INFO"))
    else:
        C.append(check("volume", "体积层", "没有画出像素", "物件里面一层半透明实形", "FAIL"))

    # accent share
    share = 100.0 * acc.sum() / hull
    kind = info["accent_kind"]
    lo, hi = ACCENT_SHARE_BAND if kind == "band" else ACCENT_SHARE
    raw["accent_share"] = share
    C.append(check("accent", "强调色占比", f"{share:.1f} % 强调色 / 凸包" + ("（AI 斜带）" if kind == "band" else ""),
                   f"{lo:.0f}–{hi:.0f} %", ok(lo <= round(share, 1) <= hi)))

    # size
    x0, y0, x1, y1 = bbox(union)
    w, h = x1 - x0, y1 - y0
    raw.update(bbox=[x0, y0, x1, y1], width=w, height=h, long_side=max(w, h))
    C.append(check("long_side", "长边", f"{max(w, h)} px ({w} × {h})", f"≤ {LONG_SIDE_MAX}",
                   ok(max(w, h) <= LONG_SIDE_MAX)))
    body_part = top_protrusion(sil)
    shape = info["shape"]
    if shape in SHAPES:
        val, target = keyline_note(shape, w, h, body_part)
        C.append(check("shape", "形状", val, target, "INFO"))
    elif shape is None:
        C.append(check("shape", "形状", "没写 data-shape，按封闭形算", "circle|square|tall|wide|open", "INFO"))
    else:
        C.append(check("shape", "形状", f'data-shape="{shape}" 不认识', "circle|square|tall|wide|open", "FAIL"))
    is_open = shape == "open"
    sr, hr = sil_area / ref["silhouette"], hull / ref["hull"]
    raw.update(silhouette_area=sil_area, hull_area=hull, silhouette_ratio=sr, hull_ratio=hr)
    s_ok = SOLID_RATIO[0] <= round(sr, 2) <= SOLID_RATIO[1]
    h_ok = OPEN_RATIO[0] <= round(hr, 2) <= OPEN_RATIO[1]
    C.append(check("silhouette", "剪影面积", f"{sr:.2f} × Tide ({sil_area / 1000:.0f}k px²)"
                   + ("" if is_open or s_ok else scale_hint(k, sr)),
                   f"{SOLID_RATIO[0]:.2f}–{SOLID_RATIO[1]:.2f}" if not is_open else "开放形状只看凸包",
                   ok(s_ok) if not is_open else "INFO"))
    C.append(check("hull", "凸包面积", f"{hr:.2f} × Tide ({hull / 1000:.0f}k px²)"
                   + ("" if not is_open or h_ok else scale_hint(k, hr)),
                   f"{OPEN_RATIO[0]:.2f}–{OPEN_RATIO[1]:.2f}" if is_open else "参考：线稿看剪影",
                   ok(h_ok) if is_open else "INFO"))
    ink = float(union.sum())
    raw["ink"] = ink
    if ref.get("ink"):
        raw["ink_ratio"] = ink / ref["ink"]
        C.append(check("ink", "墨量", f"{ink / ref['ink']:.2f} × Tide ({ink / 1000:.0f}k px²)",
                       "参考：和 Tide 并排看轻重", "INFO"))

    # centroid
    cx, cy = centre_of(sil)
    off = math.hypot(cx - 512, cy - 512)
    raw.update(centroid=[cx, cy], centroid_offset=off)
    transform = node(root, "subject").get("transform")
    if body_part:
        bx, by = body_part["centre"]
        good = abs(bx - BODY_CENTRE[0]) <= BODY_TOL and abs(by - BODY_CENTRE[1]) <= BODY_TOL
        raw.update(top_protrusion=body_part["height"], body_centre=[bx, by])
        C.append(check("centroid", "重心", f"主体中心 ({bx:.0f}, {by:.0f}) · 顶部凸起 {body_part['height']} px"
                       + ("" if good else move_hint(transform, k, BODY_CENTRE[0] - bx, BODY_CENTRE[1] - by)),
                       f"({BODY_CENTRE[0]}, {BODY_CENTRE[1]}) ± {BODY_TOL}", ok(good)))
    elif is_open:
        # a diagonal composite (cloud and sun, frame and person) centred on its centroid alone drifts towards its
        # light corner: across, take the midpoint of the centroid and the outer box's centre
        bcx = (x0 + x1) / 2
        mx = (cx + bcx) / 2
        off_o = math.hypot(mx - 512, cy - 512)
        good = off_o <= CENTROID_MAX
        raw.update(open_centre=[mx, cy], open_offset=off_o)
        C.append(check("centroid", "重心", f"剪影质心 ({cx:.0f}, {cy:.0f}) · 外框中心 x {bcx:.0f} → 横向取中 "
                       f"({mx:.0f}, {cy:.0f}) 偏 {off_o:.1f} px · 外框左右边距 {x0} / {1024 - x1}"
                       + ("" if good else move_hint(transform, k, 512 - mx, 512 - cy)),
                       f"≤ {CENTROID_MAX}（横向取质心和外框中心的中点）", ok(good)))
    else:
        good = off <= CENTROID_MAX
        C.append(check("centroid", "重心", f"剪影质心 ({cx:.0f}, {cy:.0f}) 偏 {off:.1f} px"
                       + ("" if good else move_hint(transform, k, 512 - cx, 512 - cy)),
                       f"≤ {CENTROID_MAX}", ok(good)))

    # contrast against the background (mean colours of fully covered pixels, background inside the convex hull)
    full, bgim = L["full"][..., :3], L["bg"][..., :3]
    core_b, core_a = body_c >= 0.95, acc_c >= 0.95
    hm = hull_mask(sil)
    bg_mean = bgim[hm].mean(0)
    cb, ca = contrast(full[core_b].mean(0), bg_mean), contrast(full[core_a].mean(0), bg_mean)
    Ll = renderer.layers(make_light(text), ["full", "bg"])
    bg_l = Ll["bg"][..., :3][hm].mean(0)
    cbl, cal = contrast(Ll["full"][..., :3][core_b].mean(0), bg_l), contrast(Ll["full"][..., :3][core_a].mean(0), bg_l)
    raw.update(contrast_body=cb, contrast_accent=ca, contrast_body_light=cbl, contrast_accent_light=cal)
    on_vol = ""
    if vol_m.any():
        # the lines against the base with the volume over it (its mean colour inside the volume)
        vbg = (bgim[vol_m].astype(np.float32) * (1 - VOLUME_OPACITY) + 255 * VOLUME_OPACITY).mean(0)
        cv = contrast(full[core_b].mean(0), vbg)
        raw["contrast_body_volume"] = cv
        on_vol = f" · 线对体积层 {cv:.1f}:1（INFO）"
    C.append(check("contrast_body", "线对底", f"{cb:.1f}:1{on_vol} · 浅色外观 {cbl:.1f}:1（INFO）",
                   f"默认外观 ≥ {CONTRAST_BODY:.0f}:1", ok(cb >= CONTRAST_BODY)))
    C.append(check("contrast_accent", "强调色对底", f"{ca:.1f}:1 · 浅色外观 {cal:.1f}:1（INFO）",
                   f"默认外观 ≥ {CONTRAST_ACCENT:.0f}:1", ok(ca >= CONTRAST_ACCENT)))

    # no baked effects: the system adds shadow, specular highlight and refraction (Apple HIG, app icons)
    probs = []
    if info["glow"] is not None:
        probs.append("还有 #glow：删掉 #glow 和 #glow-blur")
    if info["other_filters"]:
        probs.append("滤镜 " + ", ".join(info["other_filters"][:3]))
    C.append(check("glow", "辉光和滤镜", "没有" if not probs else "；".join(probs),
                   "不画辉光、阴影、高光（iOS 26 由系统加）", ok(not probs)))

    # category mark (tools line, image sun, video play outline, AI band) and the reserved green
    C.append(category_check(info, union, body, acc, acc_c, lines_, hull, acc_name, raw))
    # the tile's edge in the App Store (dark and light), with the A/B variants for comparison
    C.append(store_edge_check(full, acc_name, raw))
    # Android themed icon: the base and the accent are gone, the shape has to carry it
    C.append(themed_check(raw))

    # small sizes: the small version's shapes and holes at 40 px are the ones it has at 1024 (no gap clogged)
    sig = small_signature(renderer, make_small(text, k))
    raw["small"] = {str(s_): list(v) for s_, v in sig.items()}

    def sig_text(v):
        return f"{v[0]} 形 {v[1]} 孔"
    C.append(check("small", "小尺寸", f"small 版 {SMALL_CHECK} px {sig_text(sig[SMALL_CHECK])} · 1024 px {sig_text(sig[1024])}",
                   "一样（线间没有糊住，孔还在）", ok(sig[SMALL_CHECK] == sig[1024])))
    C.append(check("small_29", "小尺寸 29", f"small 版 {SMALL_INFO} px {sig_text(sig[SMALL_INFO])}", "参考", "INFO"))
    C.append(check("small_16", "小尺寸 16", f"small 版 {SMALL_FAVICON} px {sig_text(sig[SMALL_FAVICON])}（favicon-16）",
                   "参考：16 px 只要剪影认得出", "INFO"))

    # gradients
    c_, extra = gradient_check("body_gradient", "线渐变", info["body_grad"], info["body_matrix"], body,
                               BODY_SPAN, "body")
    C.append(c_)
    raw.update(extra)
    c_, extra = gradient_check("gradient", "强调色渐变", info["accent_grad"], info["accent_matrix"], acc,
                               GRAD_SPAN, "accent")
    C.append(c_)
    raw.update(extra)

    # platform circles
    ys, xs = np.nonzero(union)
    r_max = float(np.sqrt((xs + 0.5 - 512) ** 2 + (ys + 0.5 - 512) ** 2).max())
    t_r = ref.get("r_max")
    pwa_cap = PWA_R / (t_r or TIDE_FALLBACK["r_max"])
    a_cap = ANDROID_R / (t_r or TIDE_FALLBACK["r_max"])
    a_s, p_s = min(ANDROID_R / r_max, a_cap), min(PWA_R / r_max, pwa_cap)
    raw.update(r_max=r_max, android_scale=a_s, pwa_scale=p_s)
    tide_note = f" · Tide r_max {t_r:.0f}" if t_r else ""
    C.append(check("android", "安卓安全圆",
                   f"r_max {r_max:.0f}（安全圆 {ANDROID_SAFE_R:.0f}）→ ×{a_s:.3f}"
                   + (f"（封顶 Tide 的 ×{a_cap:.3f}）" if ANDROID_R / r_max > a_cap + 1e-6 else "") + tide_note,
                   "min(290 / r_max, Tide 的系数)，导出自动缩放", "INFO"))
    C.append(check("pwa", "PWA 遮罩圆", f"r_max {r_max:.0f} {'>' if r_max > PWA_R else '≤'} 409.6 → ×{p_s:.3f}"
                   + (f"（封顶 Tide 的 ×{pwa_cap:.3f}）" if PWA_R / r_max > pwa_cap + 1e-6 else ""),
                   "min(409.6 / r_max, Tide 的系数)，导出自动缩放", "INFO"))
    return {"name": name, "checks": C, "raw": raw, "info": info}


def tools_line(union):
    """The tools mark: rows where one unbroken run of ink spans TOOLS_SPAN of the drawing's width or more, grouped
    into bands. -> (bands as (top, bottom)), box) """
    x0, y0, x1, y1 = bbox(union)
    W = x1 - x0
    sub = union[y0:y1, x0:x1].astype(np.int8)
    pad = np.zeros((sub.shape[0], sub.shape[1] + 2), np.int8)
    pad[:, 1:-1] = sub
    d = np.diff(pad, axis=1)
    longest = np.zeros(sub.shape[0])
    for r in range(sub.shape[0]):
        s_, e_ = np.nonzero(d[r] == 1)[0], np.nonzero(d[r] == -1)[0]
        if len(s_):
            longest[r] = (e_ - s_).max()
    rows = longest >= TOOLS_SPAN * W
    dd = np.diff(np.concatenate([[0], rows.astype(np.int8), [0]]))
    bands = [(y0 + int(a), y0 + int(b)) for a, b in zip(np.nonzero(dd == 1)[0], np.nonzero(dd == -1)[0])]
    return bands


def play_hole(lines_, hull):
    """The video mark: the tallest hole in a line drawing that is a triangle pointing right.
    -> (height, centre, width) or None."""
    found = None
    for p in lines_:
        for c in components(fill_holes(p) & ~p, max(MIN_PIECE, int(0.004 * hull))):
            bx0, by0, bx1, by1 = bbox(c)
            bw, bh = bx1 - bx0, by1 - by0
            area = float(c.sum())
            hx, hy = centre_of(c)
            convex = area / max(hull_area(c), 1.0) >= 0.95
            triangle = 0.42 <= area / (bw * bh) <= 0.75 and 0.7 <= bw / bh <= 1.0     # rounded corners fill out
            right = (hx - bx0) / bw <= 0.42 and abs(hy - (by0 + by1) / 2) <= 0.06 * bh
            if convex and triangle and right and (found is None or bh > found[0]):
                found = (bh, (hx, hy), bw)
    return found


def min_width(points):
    """Rotating calipers on edge points: (narrowest extent, its direction in degrees, extent across it)."""
    t = np.radians(np.arange(0, 180, 0.25))
    proj = points @ np.stack([np.cos(t), np.sin(t)])
    ext = proj.max(0) - proj.min(0)
    i = int(ext.argmin())
    j = (i + len(t) // 2) % len(t)
    return float(ext[i]), float(np.degrees(t[i])), float(ext[j])


CATEGORY_TARGET = {"tools": "一条横贯整幅线稿的水平直线（中线在高度 35–75 %）",
                   "image": "左上角一个实心正圆太阳（强调色）", "video": "一个描边的播放三角（尖朝右，中间是空的）",
                   "ai": "右下角一条「/」向 45° 斜带（宽 80，强调色）", "health": "强调色绿", "finance": "强调色绿"}


def category_check(info, union, body, acc, acc_c, lines_, hull, acc_name, raw):
    """data-category: the accent colour of the category and its mark; green only for health and finance;
    the band only for AI."""
    cat, kind = info["category"], info["accent_kind"]
    x0, y0, x1, y1 = bbox(union)
    W, H = x1 - x0, y1 - y0
    if cat not in CATEGORIES:
        if cat:
            return check("category", "类别记号", f'data-category="{cat}" 不认识', "工具 / 图片 / 视频 / AI 各有记号",
                         "FAIL")
        probs = []
        if acc_name == RESERVED:
            probs.append('绿只给健康和财务：写 data-category="health" 或 "finance"，别的 app 换色')
        if kind == "band":
            probs.append('斜带只给 AI 类（data-category="ai"）')
        return check("category", "类别记号", "没写 data-category：不属于四类" + ("；" + "；".join(probs) if probs else ""),
                     "工具 / 图片 / 视频 / AI 各有记号", "FAIL" if probs else "INFO")
    name, colour = CATEGORIES[cat]
    raw["category"] = cat
    notes, probs = [], []
    if acc_name != colour:
        probs.append(f"{name}类的强调色是{colour}，这里是{acc_name or '色板外的颜色'}")
    if kind == "band" and cat != "ai":
        probs.append("斜带只给 AI 类")
    if cat == "tools":
        bands = [b for b in tools_line(union) if b[1] - b[0] >= STROKE / 2]
        if not bands:
            probs.append(f"没有一条横贯整幅线稿（≥ {TOOLS_SPAN:.0%} 宽）的水平直线")
        else:
            ya, yb = bands[0]
            frac = ((ya + yb) / 2 - y0) / H
            raw["tools_line"] = {"y": [ya, yb], "at": round(frac, 3), "lines": len(bands)}
            notes.append(f"水平直线 y {ya}–{yb}（中线在高度 {frac:.0%}）")
            if not TOOLS_AT[0] <= frac <= TOOLS_AT[1]:
                probs.append(f"水平直线的中线要在线稿高度的 {TOOLS_AT[0]:.0%}–{TOOLS_AT[1]:.0%}")
            if len(bands) > 1:
                probs.append(f"只要一条横贯的直线；这里有 {len(bands)} 条（两条平行横线读成菜单、等号）")
    elif cat == "image":
        cx, cy = centre_of(acc)
        e = edge_points(acc_c)
        R = float(np.sqrt(((e - [cx, cy]) ** 2).sum(1)).max()) if len(e) else 0.0
        round_ = float(acc.sum()) / (math.pi * R * R) if R else 0.0
        fx, fy = (cx - x0) / W, (cy - y0) / H
        raw["sun"] = {"r": round(R, 1), "roundness": round(round_, 3), "at": [round(fx, 3), round(fy, 3)]}
        notes.append(f"太阳 r {R:.0f} · 圆度 {round_:.2f} · 圆心在外框 ({fx:.0%}, {fy:.0%})")
        if round_ < SUN_ROUND:
            probs.append("强调色要是一个完整的实心正圆（太阳），不切、不缺")
        if R < SUN_R_MIN:
            probs.append(f"太阳半径要 ≥ {SUN_R_MIN:.0f}")
        if fx > SUN_CORNER or fy > SUN_CORNER:
            probs.append(f"太阳要在左上角（圆心在外框左上 {SUN_CORNER:.0%} × {SUN_CORNER:.0%} 以内）")
    elif cat == "video":
        hole = play_hole(lines_, hull)
        if hole is None:
            probs.append("没找到描边的播放三角：用 shapes.py play 画一个尖朝右的三角线框，不和别的线相连")
        else:
            raw["play_hole"] = {"height": hole[0], "at": [round(v, 1) for v in hole[1]]}
            notes.append(f"三角线框里的孔 高 {hole[0]} px {at(hole[1])}")
            if hole[0] < PLAY_H_MIN:
                probs.append(f"三角的孔实测要高 ≥ {PLAY_H_MIN}（shapes.py play 的 H ≥ 240 ÷ k）")
    elif cat == "ai":
        if kind != "band":
            probs.append('AI 斜带就是强调色：#accent-shape 写 data-accent="band"')
        else:
            width, normal, length = min_width(edge_points(np.where(dilate(acc, 2), acc_c, 0)))
            angle = (normal + 90) % 180
            cx, cy = centre_of(acc)
            fx, fy = (cx - x0) / W, (cy - y0) / H
            raw["ai_band"] = {"angle": round(angle, 2), "width": round(width, 1), "length": round(length, 1),
                              "at": [round(fx, 3), round(fy, 3)]}
            notes.append(f"斜带「/」{180 - angle:.1f}° · 宽 {width:.0f} · 长 {length:.0f} · 中心在外框 ({fx:.0%}, {fy:.0%})")
            if abs(angle - BAND_ANGLE) > BAND_ANGLE_TOL:
                probs.append("斜带要「/」向 45°（左下到右上，shapes.py aiband）")
            if abs(width - BAND_WIDTH) > BAND_WIDTH_TOL:
                probs.append(f"带宽要 {BAND_WIDTH:.0f}")
            if (fx + fy) / 2 < AI_CORNER[0] or min(fx, fy) < AI_CORNER[1]:
                probs.append("斜带要在右下角")
            if info["shape"] == "circle":
                probs.append("圆 + 斜带像 Linear 的标：AI 斜带不放在圆形物件上")
    else:
        notes.append("没有形状记号")
    val = f"{name}类" + "".join(" · " + n_ for n_ in notes) + ("；" + "；".join(probs) if probs else "")
    return check("category", "类别记号", val, CATEGORY_TARGET[cat], ok(not probs))


def edge_ring(width=RIM_W):
    """The outermost `width` px inside Apple's icon shape (where the rim variant paints its rim)."""
    return (np.asarray(mask_alpha("ios")) >= 128) & ~(np.asarray(_ios_mask(1024, width)) >= 128)


def store_name(kind, category):
    return "强调色底" if kind == "tint" and category not in CATEGORIES else STORE_NAME[kind]


def store_edge_check(full, acc_name, raw):
    """Contrast of the tile's outer edge against the dark (#000) and the light (#FFF) App Store, for this
    file and for the A/B variants --store-ab writes."""
    ring = edge_ring()

    def against(rgb):
        m = np.asarray(rgb, np.float64)[ring].mean(0)
        return contrast(m, hex_rgb(STORE_BG["dark"])), contrast(m, hex_rgb(STORE_BG["light"]))

    own = against(full)
    ab = {"lighter": against(vgrad(*LIGHTER_BG)), "rim": against(vgrad(*RIM))}
    if acc_name in TINT_BG:
        ab["tint"] = against(vgrad(*TINT_BG[acc_name]))
    raw["store_edge"] = {"dark": round(own[0], 2), "light": round(own[1], 2),
                         "ab_dark": {k: round(v[0], 2) for k, v in ab.items()}}
    val = (f"对黑 {own[0]:.1f}:1 · 对白 {own[1]:.1f}:1 · A/B 变体对黑："
           + " · ".join(f"{store_name(k, raw.get('category'))} {v[0]:.1f}" for k, v in ab.items()))
    return check("store_edge", "商店边缘", val, "参考（母版的底固定，每枚一样）：深色商店里边缘要看得出，"
                 "--store-ab 出变体", "INFO")


def themed_check(raw):
    """Android themed icon, approximated: contrast of the glyph and of the accent (alpha .5) on the themed
    background in the light and the dark theme. Fixed numbers (the same for every icon): the accent keeps
    only this much; whether the shape still reads is judged on the sheet's two themed tiles."""
    parts, out = [], {}
    for kind, label_ in (("light", "浅色主题"), ("dark", "深色主题")):
        bg, fg, hue = themed_colors(kind)
        a = float(MONO_ACCENT_OPACITY)
        mix = bg * (1 - a) + fg * a
        cg, ca = contrast(fg, bg), contrast(mix, bg)
        out[kind] = {"seed_hue": round(hue, 1), "glyph": round(cg, 2), "accent": round(ca, 2)}
        parts.append(f"{label_}（种子色相 {hue:.0f}°）图形 {cg:.1f}:1 · 强调色 {ca:.1f}:1")
    raw["themed"] = out
    return check("themed", "安卓主题图标", " · ".join(parts),
                 "固定参考，每枚一样：认不认得出看对照图的两格；上架前在真机启动器上看", "INFO")


# ---------------------------------------------------------------- report

def dwidth(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, w):
    return s + " " * max(0, w - dwidth(s))


def report(result, path, ref):
    rows = [(f"{c['label']} [{c['key']}]", c["value"], c["target"], c["status"]) for c in result["checks"]]
    head = ("检查 [key]", "数值", "目标", "结果")
    widths = [max(dwidth(r[i]) for r in rows + [head]) for i in range(3)]
    widths[1] = min(widths[1], 52)
    widths[2] = min(widths[2], 30)
    lines = []
    raw = result["raw"]
    title = f"{result['name']}  ({path})"
    lines.append("─" * 4 + " " + title + " " + "─" * max(4, 96 - dwidth(title)))
    lines.append(f"  k {raw.get('k', 0):.3g} · data-shape {raw.get('data_shape') or '—'} · "
                 f"线宽 {raw.get('stroke_effective') or 0:.0f} px · Tide 参考: 剪影 {ref['silhouette'] / 1000:.0f}k px², "
                 f"凸包 {ref['hull'] / 1000:.0f}k px²" + (" (内置)" if ref.get("source") == "built-in" else ""))
    lines.append("  " + "  ".join(pad(h, widths[i]) if i < 3 else h for i, h in enumerate(head)))
    for r in rows:
        lines.append("  " + "  ".join(pad(r[i], widths[i]) if i < 3 else r[i] for i in range(4)))
    counts = {s: sum(1 for c in result["checks"] if c["status"] == s) for s in ("FAIL", "PASS", "INFO")}
    fails = [c["key"] for c in result["checks"] if c["status"] == "FAIL"]
    lines.append(f"  汇总: {counts['FAIL']} FAIL · {counts['PASS']} PASS · {counts['INFO']} INFO"
                 + (f"  (FAIL: {', '.join(fails)})" if fails else ""))
    return "\n".join(lines)


# ---------------------------------------------------------------- preview composites (approximations)

MASKS = {}


def _superellipse(n, size=1024):
    big = Image.new("L", (size * 4, size * 4), 0)
    h = size * 2
    pts = []
    for i in range(1440):
        t = 2 * math.pi * i / 1440
        c, s = math.cos(t), math.sin(t)
        pts.append((h + h * math.copysign(abs(c) ** (2 / n), c), h + h * math.copysign(abs(s) ** (2 / n), s)))
    ImageDraw.Draw(big).polygon(pts, fill=255)
    return big.resize((size, size), Image.LANCZOS)


def _ios_mask(size=1024, inset=0.0):
    big = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(big).polygon(ios_points(size * 4, inset * 4), fill=255)
    return big.resize((size, size), Image.LANCZOS)


def _circle(size=1024):
    big = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(big).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    return big.resize((size, size), Image.LANCZOS)


def mask_alpha(name):
    """ios: Apple's icon shape (ios_path); squircle: superellipse n 3 (Android); circle."""
    if name not in MASKS:
        MASKS[name] = {"ios": _ios_mask, "squircle": lambda: _superellipse(3.0),
                       "circle": _circle}[name]()
    return MASKS[name]


def tile(im, size, shape="ios"):
    """A 1024 image under a mask, scaled to size px (premultiplied, so edges don't darken)."""
    im = im.convert("RGBA")
    if im.size != (1024, 1024):
        im = im.resize((1024, 1024), Image.LANCZOS)
    arr = np.asarray(im).copy()
    arr[..., 3] = (arr[..., 3].astype(np.float32) * np.asarray(mask_alpha(shape)).astype(np.float32) / 255
                   ).astype(np.uint8)
    return Image.fromarray(arr, "RGBA").convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA")


def over(bg, fg):
    """fg (RGBA) over bg, RGB."""
    b = Image.new("RGBA", fg.size)
    b.paste(bg.convert("RGBA"))
    return Image.alpha_composite(b, fg.convert("RGBA")).convert("RGB")


def vgrad(top, bottom, size=1024):
    t, b = hex_rgb(top).astype(np.float32), hex_rgb(bottom).astype(np.float32)
    y = np.linspace(0, 1, size, dtype=np.float32)[:, None, None]
    arr = (t * (1 - y) + b * y) * np.ones((1, size, 1), np.float32)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _tint_bg(tint, light):
    """Tinted base, approximated: dark (tint 16 % -> 7 %) or pale (tint 30 % -> 42 % over white)."""
    t = hex_rgb(tint).astype(np.float32)
    y = np.linspace(0, 1, 1024, dtype=np.float32)[:, None, None]
    if light:
        top, bot = 255 * 0.70 + t * 0.30, 255 * 0.58 + t * 0.42
    else:
        top, bot = t * 0.16 + 6, t * 0.07 + 4
    arr = (top * (1 - y) + bot * y) * np.ones((1, 1024, 1), np.float32)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _clear_bg(kind):
    """Clear base, approximated: the blurred wallpaper under a light (dark wallpaper) or dark (light one) glass tint."""
    g = wallpaper(kind).filter(ImageFilter.GaussianBlur(40)).convert("RGBA")
    tint = Image.new("RGBA", g.size, (0, 0, 0, 46) if kind == "light" else (255, 255, 255, 22))
    return Image.alpha_composite(g, tint).convert("RGB")


def _recolour(layer, colour):
    out = np.array(layer, copy=True)
    out[..., :3] = hex_rgb(colour)
    return out


def _blur(a, r):
    return np.asarray(Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)),
                      np.float32) / 255


def liquid_glass(bg, groups, dark=False):
    """iOS 26 Liquid Glass, approximated for review only: each foreground group (RGBA arrays, bottom to top) throws a
    soft shadow on what is below it and gets a specular rim, bright along its top-left edges and fainter along the
    bottom-right ones. Icon Composer's real rendering (refraction, translucency, the light moving with the device) is
    richer; judge depth and legibility here, the final look in Icon Composer."""
    out = np.asarray(bg.convert("RGB"), np.float32).copy()
    for g in groups:
        a = g[..., 3].astype(np.float32) / 255
        if a.max() < 0.01:
            continue
        solid = np.clip(a / max(float(a.max()), 1e-3), 0, 1)        # the group's shape, whatever its opacity
        sh = np.roll(_blur(solid, 16), 12, axis=0) * (0.34 if dark else 0.22) * float(a.max()) ** 0.5
        out *= (1 - sh[..., None])
        out = out * (1 - a[..., None]) + g[..., :3].astype(np.float32) * a[..., None]
        hi = _blur(np.clip(solid - np.roll(np.roll(solid, 5, axis=0), 3, axis=1), 0, 1), 1.6)
        lo = _blur(np.clip(solid - np.roll(np.roll(solid, -4, axis=0), -2, axis=1), 0, 1), 1.6)
        lift = (hi * 0.55 + lo * 0.18)[..., None]
        out = out * (1 - lift) + 255 * lift
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def appearances(renderer, text, looks):
    """Apple's six iOS 26 appearances, each through liquid_glass(): default, dark, clear light and dark, tinted light
    and dark. Groups: volume, lines, accent. Clear and tinted come from the mono look, as the system derives them."""
    names = ["volume", "body", "accent"]
    dflt = renderer.layers(text, names)
    drk = renderer.layers(looks["dark"], names)
    mono = renderer.layers(looks["mono"], names)
    tint_dark = [_recolour(mono[n], TINT) for n in names]
    deep = "#{:02X}{:02X}{:02X}".format(*[int(c * 0.62) for c in hex_rgb(TINT)])
    tint_light = [_recolour(mono[n], deep) for n in names]
    return [
        ("默认", liquid_glass(vgrad(*LOOKS["default"]["bg"]), [dflt[n] for n in names], dark=True), "mid", None),
        ("深色", liquid_glass(vgrad(*LOOKS["dark"]["bg"]), [drk[n] for n in names], dark=True), "dark", None),
        ("Clear 浅色", liquid_glass(_clear_bg("light"), [mono[n] for n in names]), "wall-light", "light"),
        ("Clear 深色", liquid_glass(_clear_bg("dark"), [mono[n] for n in names], dark=True), "wall-dark", "dark"),
        ("Tinted 浅色", liquid_glass(_tint_bg(TINT, True), tint_light), "wall-light", "light"),
        ("Tinted 深色", liquid_glass(_tint_bg(TINT, False), tint_dark, dark=True), "wall-dark", "dark"),
    ]


WALLS = {}


def wallpaper(kind, size=1024):
    if kind in WALLS:
        return WALLS[kind]
    rng = np.random.default_rng(7 if kind == "light" else 11)
    if kind == "light":
        base, blobs = "#E9E3DC", ["#F2C3AE", "#B7D2F0", "#D5E6C4", "#F5DFA6", "#C9C2EE"]
    else:
        base, blobs = "#0F1320", ["#2B3B78", "#5A2A5E", "#17504F", "#3D2A6E", "#173A66"]
    im = Image.new("RGB", (size, size), base)
    d = ImageDraw.Draw(im)
    for c in blobs * 2:
        x, y = rng.uniform(-0.1, 1.1) * size, rng.uniform(-0.1, 1.1) * size
        r = rng.uniform(0.18, 0.34) * size
        d.ellipse((x - r, y - r, x + r, y + r), fill=c)
    WALLS[kind] = im.filter(ImageFilter.GaussianBlur(size * 0.09))
    return WALLS[kind]


def themed(mono_scaled, kind):
    """Android themed icon, approximated: the monochrome layer recoloured with the light or dark theme's
    Material You tones from the wallpaper's seed hue (THEMED_TONES; the layer's alpha carries the accent
    at .5)."""
    bg, fg, _ = themed_colors(kind)
    a = np.asarray(mono_scaled)[..., 3:4].astype(np.float32) / 255
    return Image.fromarray(np.clip(bg * (1 - a) + fg * a, 0, 255).astype(np.uint8), "RGB")


def adaptive_visible(layer108):
    """The 72 dp visible area of a 108 dp adaptive layer (1024 canvas), scaled back to 1024."""
    s = 1024 * 18 / 108
    return layer108.crop((round(s), round(s), round(1024 - s), round(1024 - s))).resize((1024, 1024), Image.LANCZOS)


def icon_images(renderer, text, looks, a_s):
    """The 1024 renders the sheet and the exports share."""
    bg = LOOKS["default"]["bg"]
    ims = {"master": renderer.image(text, 1024), "small": renderer.image(looks["small"], 1024),
           "light": renderer.image(looks["light"], 1024), "dark": renderer.image(looks["dark"], 1024),
           "mono": renderer.image(looks["mono"], 1024, transparent=True),
           "fg": renderer.image(with_scale(without_background(text), a_s), 1024, transparent=True),
           "mono_scaled": renderer.image(with_scale(looks["mono"], a_s), 1024, transparent=True)}
    ims["android"] = adaptive_visible(over(vgrad(*bg), ims["fg"]))
    ims["glass"] = appearances(renderer, text, looks)
    return ims


# ---------------------------------------------------------------- sheet

SHEET = """<!doctype html><html><head><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ width: 1240px; font: 500 14px/1.35 -apple-system, "SF Pro Text", Inter, "PingFang SC", "Noto Sans CJK SC",
         "WenQuanYi Zen Hei", "Helvetica Neue", sans-serif; background: #EEF0F2; color: #1B1C1D; }}
  .sheet {{ width: 1240px; padding: 36px 44px 40px; background: linear-gradient(170deg, #F6F7F9, #E4E6EA);
           display: flex; flex-direction: column; gap: 30px; }}
  .top {{ display: flex; align-items: center; gap: 34px; }}
  .meta {{ flex: 1; }}
  h1 {{ font-size: 22px; font-weight: 600; letter-spacing: -.01em; }}
  .label {{ font-size: 13px; color: #646667; margin-top: 2px; }}
  .stat {{ font-size: 12px; color: #48494B; margin-top: 14px; line-height: 1.6; white-space: nowrap; }}
  .bad {{ color: #B4321F; }}
  .vs {{ display: flex; flex-direction: column; align-items: center; gap: 10px; }}
  .pair {{ display: flex; gap: 18px; align-items: flex-end; }}
  .strip {{ display: flex; align-items: flex-end; gap: 26px; }}
  .row {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; }}
  .h {{ font-size: 12px; font-weight: 600; color: #48494B; margin-bottom: -18px; }}
  .box {{ height: 170px; border-radius: 14px; display: flex; flex-direction: column; align-items: center;
          justify-content: center; gap: 10px; background-size: cover; background-position: center; }}
  .lite {{ background-color: #F7F8FA; color: #646667; }}
  .mid {{ background-color: #DADDE1; color: #48494B; }}
  .dark {{ background-color: #0E0F11; color: #9A9B9D; }}
  .wall-light {{ color: #1B1C1D; }}
  .wall-dark {{ color: #FFFFFF; }}
  .cell {{ display: flex; flex-direction: column; align-items: center; }}
  .cap {{ font-size: 11px; opacity: .8; margin-top: 7px; text-align: center; white-space: nowrap; }}
  img {{ display: block; }}
  .sh {{ filter: drop-shadow(0 1px 1.5px rgba(0,0,0,.18)) drop-shadow(0 6px 14px rgba(0,0,0,.14)); }}
  .dark .sh {{ filter: drop-shadow(0 1px 1.5px rgba(0,0,0,.6)) drop-shadow(0 6px 14px rgba(0,0,0,.4)); }}
</style></head><body><div class="sheet">
  <div class="top">
    <img class="sh" src="{hero}" width="240" height="240">
    <div class="meta"><h1>{name}</h1><div class="label">默认外观 · 石墨 · iOS 遮罩（平面，指标按它量）</div>{stat}</div>
    <div class="vs"><div class="pair">{vs}</div><div class="label">和 Tide 同尺寸，比轻重</div></div>
  </div>
  <div class="strip">{sizes}</div>
  <div class="h">iOS 26 · Apple 的六种外观（Liquid Glass 是近似：每组加了边缘高光和投影，Clear、Tinted 由 mono 推出；真机效果以 Icon Composer 预览为准）</div>
  <div class="row">{glass}</div>
  <div class="h">平面版（iOS 26 以下、App Store 截图、网页和营销用的浅色版，没有玻璃）</div>
  <div class="row">{looks}</div>
  <div class="h">Android（前景叠背景渐变取 72 dp 可见区；主题图标：monochrome 层按浅色、深色主题的 Material You 色调上色（色相取自壁纸），近似，上架前在真机启动器上看）</div>
  <div class="row">{android}</div>
</div></body></html>"""


def png_uri(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def cell(im_tile, css, cap):
    return (f'<div class="cell"><img class="sh" src="{png_uri(im_tile)}" width="{css:g}" height="{css:g}">'
            f'<div class="cap">{cap}</div></div>')


def box(inner, cls, bg_im=None):
    style = f' style="background-image:url({png_uri(bg_im.resize((340, 340), Image.LANCZOS))})"' if bg_im else ""
    return f'<div class="box {cls}"{style}>{inner}</div>'


def build_sheet(renderer, result, ims, tide_im, path):
    """Review sheet at 2x: tiles are made at real pixel size and shown at half that in CSS px."""
    raw = result["raw"]
    fails = [c["key"] for c in result["checks"] if c["status"] == "FAIL"]
    cat = raw.get("category")
    stat_lines = [(f"{CATEGORIES[cat][0]}类 · {CATEGORIES[cat][1]}" if cat in CATEGORIES else "不属于四类")
                  + f' · 剪影 {raw.get("silhouette_ratio", 0):.2f}× Tide · 凸包 {raw.get("hull_ratio", 0):.2f}×',
                  f'强调色 {raw.get("accent_share", 0):.1f} % · 长边 {raw.get("long_side", 0)} px · '
                  f'{raw.get("parts", 0)} 段线',
                  f'线宽 {raw.get("stroke_effective") or 0:.0f} px · 线间 '
                  + (f'{raw["line_gap"]:.0f} px' if raw.get("line_gap") is not None else "—")
                  + f' · 线对底 {raw.get("contrast_body", 0):.1f}:1',
                  f'r_max {raw.get("r_max", 0):.0f} · Android ×{raw.get("android_scale", 1):.3f}',
                  f'<span class="bad">FAIL: {", ".join(fails)}</span>' if fails else "全部通过"]
    stat = '<div class="stat">' + "".join(f"<div>{x}</div>" for x in stat_lines) + "</div>"
    vs = cell(tile(ims["master"], 240), 120, result["name"])
    vs += cell(tile(tide_im, 240), 120, "Tide") if tide_im is not None else \
        '<div class="cap">（没有新 Tide 可比）</div>'
    sizes = "".join(cell(tile(ims["small" if s <= 64 else "master"], s), s / 2, f"{s}" + (" small" if s <= 64 else ""))
                    for s in (180, 120, 80, 60, 40, 29))
    T = 220                       # tile px in the grid (110 CSS px)
    glass = [box(cell(tile(im, T), T / 2, lab), cls, wallpaper(wall) if wall else None)
             for lab, im, cls, wall in ims["glass"]]
    looks = [box(cell(tile(ims["master"], T), T / 2, "默认（平面）"), "mid"),
             box(cell(tile(ims["light"], T), T / 2, "浅色"), "mid"),
             box(cell(tile(ims["dark"], T), T / 2, "深色"), "dark"),
             box(cell(over(Image.new("RGB", (1024, 1024), (60, 64, 72)), ims["mono"]).resize((T, T), Image.LANCZOS),
                      T / 2, "mono（Tinted、Clear 的来源）"), "lite")]
    android = [box(cell(tile(ims["android"], T, "circle"), T / 2, "圆形遮罩"), "lite"),
               box(cell(tile(ims["android"], T, "squircle"), T / 2, "方圆遮罩"), "lite"),
               box(cell(tile(adaptive_visible(themed(ims["mono_scaled"], "light")), T, "circle"), T / 2,
                        "主题图标 · 浅色主题"), "wall-light", wallpaper("light")),
               box(cell(tile(adaptive_visible(themed(ims["mono_scaled"], "dark")), T, "circle"), T / 2,
                        "主题图标 · 深色主题"), "wall-dark", wallpaper("dark")),
               box(cell(tile(ims["android"], 96, "circle"), 48, "圆形 48"), "lite"),
               box(cell(tile(ims["android"], 96, "squircle"), 48, "方圆 48"), "lite")]
    html = SHEET.format(hero=png_uri(tile(ims["master"], 480)), name=result["name"], stat=stat, vs=vs,
                        sizes=sizes, glass="".join(glass), looks="".join(looks), android="".join(android))
    renderer.sheet(html, path)


# ---------------------------------------------------------------- Icon Composer layers (transform baked in)

PATH_TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
PATH_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}


def _fmt(v):
    # 4 decimals: arcs whose chord is almost their diameter (Halo's cloud) move visibly with coarser rounding
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def transform_path(d, M):
    """Path data with a similarity transform (uniform scale, rotation, translation) applied, absolute commands."""
    a, c, e = M[0]
    b, dd, f = M[1]
    s = math.sqrt(abs(a * dd - b * c))
    flip = a * dd - b * c < 0
    rot = math.degrees(math.atan2(b, a))
    P = lambda x, y: (a * x + c * y + e, b * x + dd * y + f)
    toks = PATH_TOKEN.findall(d)
    out, i, cmd = [], 0, None
    cur = start = (0.0, 0.0)
    while i < len(toks):
        if toks[i].isalpha():
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                out.append("Z")
                cur = start
                continue
        elif cmd is None:
            raise ValueError("path data must start with a command")
        up, rel = cmd.upper(), cmd.islower()
        n = PATH_ARGS[up]
        args = toks[i:i + n]
        if up == "A":
            # arc flags may be written without separators ("011")
            args = toks[i:i + 3]
            j = i + 3
            flags = []
            while len(flags) < 2:
                t = toks[j]
                flags.append(t[0])
                if len(t) > 1:
                    toks[j] = t[1:]
                else:
                    j += 1
            args += flags + toks[j:j + 2]
            i = j + 2
        else:
            i += n
        v = [float(x) for x in args]
        if up == "H":
            pt = (v[0] + (cur[0] if rel else 0), cur[1])
            out.append("L " + " ".join(map(_fmt, P(*pt))))
            cur = pt
            continue
        if up == "V":
            pt = (cur[0], v[0] + (cur[1] if rel else 0))
            out.append("L " + " ".join(map(_fmt, P(*pt))))
            cur = pt
            continue
        if up == "A":
            end = (v[5] + (cur[0] if rel else 0), v[6] + (cur[1] if rel else 0))
            sweep = int(v[4]) ^ (1 if flip else 0)
            angle = (rot - v[2]) if flip else (v[2] + rot)
            X, Y = P(*end)
            out.append(f"A {_fmt(v[0] * s)} {_fmt(v[1] * s)} {_fmt(angle % 360)} {int(v[3])} {sweep} {_fmt(X)} {_fmt(Y)}")
            cur = end
            continue
        pts = [(v[j] + (cur[0] if rel else 0), v[j + 1] + (cur[1] if rel else 0)) for j in range(0, n, 2)]
        out.append(up + " " + " ".join(f"{_fmt(X)} {_fmt(Y)}" for X, Y in (P(*p) for p in pts)))
        cur = pts[-1]
        if up == "M":
            start = cur
            cmd = "l" if rel else "L"     # further pairs after M are line-tos
    return " ".join(out)


def shape_path(el):
    """Path data for a basic shape element (open for <line> and <polyline>), None when it draws nothing."""
    t = local(el)
    g = lambda a, dflt=0.0: num(el.get(a), dflt)
    if t == "path":
        return el.get("d")
    if t == "line":
        return f"M {g('x1')} {g('y1')} L {g('x2')} {g('y2')}"
    if t in ("circle", "ellipse"):
        cx, cy = g("cx"), g("cy")
        rx, ry = (g("r"), g("r")) if t == "circle" else (g("rx"), g("ry"))
        return (f"M {cx - rx} {cy} A {rx} {ry} 0 1 0 {cx + rx} {cy} A {rx} {ry} 0 1 0 {cx - rx} {cy} Z"
                if rx > 0 and ry > 0 else None)
    if t == "rect":
        x, y, w, h = g("x"), g("y"), g("width"), g("height")
        rx, ry = num(el.get("rx")), num(el.get("ry"))
        rx = rx if rx is not None else (ry or 0.0)
        ry = ry if ry is not None else rx
        rx, ry = min(rx, w / 2), min(ry, h / 2)
        if rx <= 0 or ry <= 0:
            return f"M {x} {y} H {x + w} V {y + h} H {x} Z"
        return (f"M {x + rx} {y} H {x + w - rx} A {rx} {ry} 0 0 1 {x + w} {y + ry} V {y + h - ry} "
                f"A {rx} {ry} 0 0 1 {x + w - rx} {y + h} H {x + rx} A {rx} {ry} 0 0 1 {x} {y + h - ry} "
                f"V {y + ry} A {rx} {ry} 0 0 1 {x + rx} {y} Z")
    if t in ("polygon", "polyline"):
        v = [float(x) for x in re.split(r"[\s,]+", (el.get("points") or "").strip()) if x]
        if len(v) < 4:
            return None
        return "M " + " L ".join(f"{v[i]} {v[i + 1]}" for i in range(0, len(v) - 1, 2)) + (" Z" if t == "polygon" else "")
    return None


def bake_layer(root, ident, info):
    """[(path data in final pixels, fill-rule)] for #body or #accent-shape, or None when the layer cannot
    be written as plain paths (mask, clip path, filter, <use>, non-uniform transform)."""
    el = node(root, ident)
    if el is None:
        return None
    P = parents(root)
    M0 = info["matrix"]
    subject = node(root, "subject")
    out = []
    for e in el.iter():
        t = local(e)
        if t in NONRENDER and e is not el:
            continue
        if any(get_prop(e, a) for a in ("mask", "clip-path", "filter")):
            return None
        if t in ("use", "image", "text", "foreignObject"):
            return None
        if t not in GEOMETRY:
            continue
        M = M0 @ chain_matrix(e, el, P) if el is not subject else M0
        a, b, c, d = M[0, 0], M[1, 0], M[0, 1], M[1, 1]
        if abs(a * a + b * b - (c * c + d * d)) > 1e-6 or abs(a * c + b * d) > 1e-6:
            return None
        dpath = shape_path(e)
        if not dpath:
            continue
        rule = None
        anc = e
        while anc is not None and rule is None:
            rule = get_prop(anc, "fill-rule")
            anc = P.get(anc) if anc is not el else None
        out.append((transform_path(dpath, M), rule))
    return out


def layer_gradient_svg(gid, g, M):
    G = M @ g["transform"]
    X1, Y1 = (G @ [g["x1"], g["y1"], 1])[:2]
    X2, Y2 = (G @ [g["x2"], g["y2"], 1])[:2]
    stops = g["stops"]
    return (f'<linearGradient id="{gid}" x1="{_fmt(X1)}" y1="{_fmt(Y1)}" x2="{_fmt(X2)}" y2="{_fmt(Y2)}" '
            f'gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="{stops[0]}"/>'
            f'<stop offset="1" stop-color="{stops[-1]}"/></linearGradient>')


IC_README = """Icon Composer 分层（{title}）

Apple 的做法（HIG · App icons）：一个背景加最多四组前景，层是方形、不带遮罩，系统加高光、折射、阴影。
这里是三组前景，从下到上：

文件
  {f1}   组 1：体积层（物件里面的实形），整张 1024 画布，不透明白色{n1}
  {f2}   组 2：线稿{n2}
  {f3}   组 3：强调色块{n3}

在 Icon Composer 里手动设
  Background     Fill 用渐变。Default：#26282B → #191C1F；Dark：#191C1F → #0E1115
  组 1（体积层） Opacity 14 %（Dark 10 %）；Liquid Glass 开；Specular Automatic；Shadow 关
  组 2（线稿）   Liquid Glass 开；Specular Automatic；Shadow Neutral
  组 3（强调色） Liquid Glass 开；Specular Automatic；Shadow Chromatic
  Mono           体积层 White 30 %；线稿 White；强调色 50 % 灰
  Clear、Tinted  由系统从 Mono 推出，在 Icon Composer 的外观预览里六种都看一遍
                 （默认、深色、Clear 浅色、Clear 深色、Tinted 浅色、Tinted 深色）

层文件里没有辉光、遮罩、背景、圆角、阴影：这些都交给系统。底只在 Background 里设，
深色外观换 Background 的渐变和体积层的透明度，层不变。

不用 Icon Composer、走 asset catalog（AppIcon，单尺寸 1024）时用上一级目录的三张
  Any            ios-1024.png          不透明，带石墨底和体积层
  Dark           ios-1024-dark.png     透明底，系统自己垫深色底；线稿用深色外观的渐变
  Tinted         ios-1024-tinted.png   灰度，不透明黑底：线稿白，强调色 50 % 灰，体积层 30 % 灰
"""

IC_LAUNCHER = """<?xml version="1.0" encoding="utf-8"?>
<!-- {title}: adaptive icon, three layers (API 26 and up). Foreground and monochrome are scaled by {a_s:.3f}
     (r_max {r_max:.0f}; min(290 / r_max, Tide's factor)): inside the 66 dp safe circle, same relative size as on iOS.
     Below API 26 the launcher uses mipmap-*/ic_launcher.png and ic_launcher_round.png next to this folder.
     Manifest: android:icon="@mipmap/ic_launcher" android:roundIcon="@mipmap/ic_launcher_round" -->
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/ic_launcher_background" />
    <foreground android:drawable="@mipmap/ic_launcher_foreground" />
    <monochrome android:drawable="@mipmap/ic_launcher_monochrome" />
</adaptive-icon>
"""

IC_BACKGROUND = """<?xml version="1.0" encoding="utf-8"?>
<!-- Graphite background: vertical linear gradient {top} to {bottom}, 108 dp full bleed. -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:aapt="http://schemas.android.com/aapt"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path android:pathData="M0,0h108v108h-108z">
        <aapt:attr name="android:fillColor">
            <gradient
                android:type="linear"
                android:startX="54"
                android:startY="0"
                android:endX="54"
                android:endY="108"
                android:startColor="#FF{top_hex}"
                android:endColor="#FF{bottom_hex}" />
        </aapt:attr>
    </path>
</vector>
"""

DENSITIES = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}
LEGACY = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}   # 48 dp, API 25 and below
LEGACY_FILL = 44 / 48         # the legacy shape fills 44 of the 48 dp (old Material launcher keyline)


def legacy_icon(adaptive, px, shape):
    """Pre-API-26 launcher icon: the adaptive icon's visible area under a squircle or circle, 44 of 48 dp."""
    inner = round(px * LEGACY_FILL)
    im = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    im.alpha_composite(tile(adaptive, inner, shape), ((px - inner) // 2, (px - inner) // 2))
    return im


def export_icon_composer(renderer, text, root, info, title, out):
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for stale in ("1_body", "2_accent"):       # names before the volume group
        for ext in (".svg", ".png"):
            if (out / (stale + ext)).exists():
                (out / (stale + ext)).unlink()
    for ident, gid, num_, css, name in (("volume", "volume", 1, "solid-volume", "volume"),
                                        ("body", "body", 2, "body", "body"),
                                        ("accent-shape", "accent", 3, "accent", "accent")):
        if gid == "volume" and node(root, "volume") is None:
            for stale in (out / "1_volume.svg", out / "1_volume.png"):
                if stale.exists():
                    stale.unlink()
            files.append(("（没有 1_volume）", '：data-volume="none"，这一组不出，组 2、3 照旧'))
            continue
        paths = bake_layer(root, ident, info)
        g = {"body": info["body_grad"], "accent": info["accent_grad"]}.get(gid,
                                                                          {"units": "userSpaceOnUse"})
        M = info["body_matrix"] if gid == "body" else info["accent_matrix"]
        if gid == "volume":
            P_ = parents(root)
            vol_el = node(root, "volume")
            M = info["matrix"] @ chain_matrix(vol_el, vol_el, P_) if vol_el is not None else info["matrix"]
        for stale in (out / f"{num_}_{name}.svg", out / f"{num_}_{name}.png"):
            if stale.exists():
                stale.unlink()
        # the PNG layer is always written (Icon Composer takes either); the SVG one when it bakes to plain paths
        L = renderer.layers(text, [css])[css]
        Image.fromarray(L, "RGBA").save(out / f"{num_}_{name}.png")
        if paths and g is not None and g["units"] == "userSpaceOnUse":
            body = "\n".join(f'    <path d="{d}"' + (f' fill-rule="{r}"' if r else "") + "/>" for d, r in paths)
            paint = (f'fill="none" stroke="url(#{gid})" stroke-width="{STROKE:g}" stroke-linecap="round" '
                     'stroke-linejoin="round"' if gid == "body" else
                     f'fill="{VOLUME_FILL}"' if gid == "volume" else f'fill="url(#{gid})"')
            defs = "" if gid == "volume" else f"  <defs>{layer_gradient_svg(gid, g, M)}</defs>\n"
            svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">\n'
                   f"  <!-- {title}: Icon Composer group {num_}, the {name}. Final pixels, transform baked in. -->\n"
                   + defs +
                   f'  <g {paint}>\n{body}\n  </g>\n</svg>\n')
            (out / f"{num_}_{name}.svg").write_text(svg, encoding="utf-8")
            files.append((f"{num_}_{name}.svg 和 .png", {"volume": "；透明度在 Icon Composer 里设",
                                                       "body": "，transform 已烘焙进坐标，保留渐变和 60 px 圆头线",
                                                       "accent": "，transform 已烘焙进坐标，保留渐变"}[gid]))
        else:
            files.append((f"{num_}_{name}.png", "（用了遮罩或无法写成纯路径，只出 PNG 层）"))
    (out / "README.txt").write_text(IC_README.format(title=title, f1=files[0][0], n1=files[0][1],
                                                     f2=files[1][0], n2=files[1][1], f3=files[2][0], n3=files[2][1]),
                                    encoding="utf-8")
    return [f"icon-composer/{f}" for f, _ in files] + ["icon-composer/README.txt"]


def export(renderer, text, root, looks, ims, result, out):
    out.mkdir(parents=True, exist_ok=True)
    info, raw = result["info"], result["raw"]
    a_s, p_s = raw.get("android_scale", ANDROID_CAP), raw.get("pwa_scale", 1.0)
    written = []

    def save(im, name):
        im.save(out / name)
        written.append(name)

    save(ims["master"], "ios-1024.png")
    # asset catalog Dark: transparent background (Apple: the system provides the dark background)
    dark = renderer.image(without_background(looks["dark"]), 1024, transparent=True)
    if np.asarray(dark)[..., 3][[0, 0, -1, -1], [0, -1, 0, -1]].any():
        print("WARNING ios-1024-dark.png 的角上不透明：深色外观要透明底", file=sys.stderr)
    save(dark, "ios-1024-dark.png")
    # asset catalog Tinted: grayscale, the mono layer over black
    save(over(Image.new("RGB", (1024, 1024)), ims["mono"]).convert("L"), "ios-1024-tinted.png")
    save(renderer.image(without_background(text), 1024, transparent=True), "icon-1024-transparent.png")
    play = renderer.image(text, 512).convert("RGBA")          # 32-bit, fully opaque
    play.save(out / "play-512.png", optimize=True)
    written.append("play-512.png")
    kb = (out / "play-512.png").stat().st_size / 1024
    if kb > 1024:
        print(f"WARNING play-512.png 是 {kb:.0f} KB，Play 要 ≤ 1024 KB", file=sys.stderr)
    # Android: flat previews plus the res/ tree
    save(ims["fg"].resize((432, 432), Image.LANCZOS), "android-foreground-432.png")
    save(ims["mono_scaled"].resize((432, 432), Image.LANCZOS), "android-monochrome-432.png")
    an = out / "android"
    (an / "mipmap-anydpi-v26").mkdir(parents=True, exist_ok=True)
    (an / "drawable").mkdir(parents=True, exist_ok=True)
    for xml in ("ic_launcher.xml", "ic_launcher_round.xml"):
        (an / "mipmap-anydpi-v26" / xml).write_text(
            IC_LAUNCHER.format(title=result["name"], a_s=a_s, r_max=raw.get("r_max", 0)), encoding="utf-8")
    top, bottom = LOOKS["default"]["bg"]
    (an / "drawable" / "ic_launcher_background.xml").write_text(
        IC_BACKGROUND.format(top=top, bottom=bottom, top_hex=top[1:], bottom_hex=bottom[1:]), encoding="utf-8")
    for dens, px in DENSITIES.items():
        d = an / f"mipmap-{dens}"
        d.mkdir(exist_ok=True)
        ims["fg"].resize((px, px), Image.LANCZOS).save(d / "ic_launcher_foreground.png")
        ims["mono_scaled"].resize((px, px), Image.LANCZOS).save(d / "ic_launcher_monochrome.png")
        legacy_icon(ims["android"], LEGACY[dens], "squircle").save(d / "ic_launcher.png")
        legacy_icon(ims["android"], LEGACY[dens], "circle").save(d / "ic_launcher_round.png")
    written += ["android/mipmap-anydpi-v26/ic_launcher.xml", "ic_launcher_round.xml",
                "android/drawable/ic_launcher_background.xml", f"android/mipmap-*/ (×{len(DENSITIES)}，含 legacy 48 dp)"]
    # web
    rounded = with_rounded_background(text)
    save(renderer.image(rounded, 192, transparent=True), "pwa-192.png")
    save(renderer.image(rounded, 512, transparent=True), "pwa-512.png")
    save(renderer.image(with_scale(text, p_s), 512), "pwa-maskable-512.png")
    save(renderer.image(text, 180), "apple-touch-180.png")
    fav = with_rounded_background(looks["small"], rounded_rect_path())
    f16 = renderer.image(fav, 16, transparent=True)
    f32 = renderer.image(fav, 32, transparent=True)
    f48 = renderer.image(fav, 48, transparent=True)
    save(f16, "favicon-16.png")
    save(f32, "favicon-32.png")
    f48.save(out / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], append_images=[f32, f16])
    written.append("favicon.ico")
    (out / "favicon.svg").write_text(fav, encoding="utf-8")
    written.append("favicon.svg")
    written += export_icon_composer(renderer, text, root, info, result["name"], out / "icon-composer")
    return written


# ---------------------------------------------------------------- App Store A/B variants

STORE_SHEET = """<!doctype html><html><head><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ width: 1240px; font: 500 14px/1.35 -apple-system, "SF Pro Text", Inter, "PingFang SC", "Noto Sans CJK SC",
         "WenQuanYi Zen Hei", "Helvetica Neue", sans-serif; background: #EEF0F2; color: #1B1C1D; }}
  .sheet {{ width: 1240px; padding: 36px 44px 40px; background: linear-gradient(170deg, #F6F7F9, #E4E6EA);
           display: flex; flex-direction: column; gap: 14px; }}
  h1 {{ font-size: 22px; font-weight: 600; letter-spacing: -.01em; }}
  .label {{ font-size: 13px; color: #646667; margin-bottom: 8px; }}
  .h {{ font-size: 12px; font-weight: 600; color: #48494B; margin-top: 8px; }}
  .row {{ display: grid; grid-template-columns: repeat({n}, 1fr); gap: 12px; }}
  .box {{ height: 210px; border-radius: 14px; display: flex; flex-direction: column; align-items: center;
          justify-content: center; gap: 12px; }}
  .store-dark {{ background: #000000; color: #A0A1A3; }}
  .store-light {{ background: #FFFFFF; color: #48494B; }}
  .pair {{ display: flex; align-items: flex-end; gap: 18px; }}
  .cap {{ font-size: 11px; opacity: .85; text-align: center; white-space: nowrap; }}
  img {{ display: block; }}
</style></head><body><div class="sheet">
  <h1>{name} · 商店图标 A/B</h1>
  <div class="label">只换底或加一圈细亮边，图形和强调色不动；深色、Tinted 外观沿用主图标。边缘对比度 = iOS 遮罩内最外 16 px 的平均色对商店底</div>
  <div class="h">深色 App Store（#000）</div>
  <div class="row">{dark}</div>
  <div class="h">浅色 App Store（#FFF）</div>
  <div class="row">{light}</div>
</div></body></html>"""

STORE_README = """商店图标 A/B（{name}）

文件
{files}
  {sheet}   对比图：默认和变体放在深色（#000）和浅色（#FFF）商店底上，标了边缘对比度

怎么用
  只在 App Store Connect 的产品页优化（Product Page Optimization）里做对照，主图标不改。
  测试用的图标要作为备用图标（alternate app icon）打进当前上架版本的二进制里；从测试页下载的用户，
  主屏上看到的也是它。
  变体和主图标要一眼看出是同一个 app（审核指南 2.3.8）：只换底或加一圈细亮边，图形、强调色和位置都不动。
  深色和 Tinted 外观沿用主图标（export/ios-1024-dark.png、ios-1024-tinted.png），变体只换默认外观。
  细亮边只出平面 PNG，按 Apple 图标外形（圆角 22.37 %、60 % 平滑）的近似画在里面 16 px：不进 Icon Composer
  （玻璃自带边缘高光），也不拿去做 Android、网页图标；上传前在 App Store Connect 的预览里看一眼四个角。
  一次只测一个变化，样本够了再定。结果只决定这个 app 的商店图标，不改石墨风格的底色。
"""

STORE_FILE = {"lighter": "浅一档：底 {0} → {1}（亮一档，主体和强调色不变）",
              "rim": "细亮边：默认底，iOS 遮罩内沿一圈 16 px 亮边 {0} → {1}",
              "tint": "{name}：底朝强调色的色相偏一点（彩度 6）{0} → {1}"}


def store_ab(renderer, text, result, ims, out):
    """App Store A/B variants of the default look (style.md, 商店图标的 A/B 变体): .svg + .png each, a comparison
    sheet on the dark and the light store, README.txt."""
    out.mkdir(parents=True, exist_ok=True)
    name, acc_name, category = result["name"], result["raw"].get("accent_colour"), result["raw"].get("category")
    kinds = [k for k in STORE_AB if k != "tint" or acc_name in TINT_BG]
    pics, written, lines = {"default": ims["master"]}, [], []
    for kind in kinds:
        svg = make_store_variant(text, kind, acc_name)
        (out / f"{name}-{kind}.svg").write_text(svg, encoding="utf-8")
        pics[kind] = renderer.image(svg, 1024)
        pics[kind].save(out / f"{name}-{kind}.png")
        written += [f"{name}-{kind}.svg", f"{name}-{kind}.png"]
        stops = {"lighter": LIGHTER_BG, "rim": RIM, "tint": TINT_BG.get(acc_name)}[kind]
        lines.append((f"{name}-{kind}.svg/.png", STORE_FILE[kind].format(*stops, name=store_name(kind, category))))
    ring = edge_ring()
    rows = {}
    for store, bg in STORE_BG.items():
        cells = []
        for kind, im in pics.items():
            ratio = contrast(np.asarray(im, np.float64)[ring].mean(0), hex_rgb(bg))
            cap = ("默认" if kind == "default" else store_name(kind, category)) + f" · 边缘 {ratio:.1f}:1"
            cells.append(f'<div class="box store-{store}"><div class="pair">'
                         f'<img src="{png_uri(tile(im, 240))}" width="120" height="120">'
                         f'<img src="{png_uri(tile(im, 120))}" width="60" height="60"></div>'
                         f'<div class="cap">{cap}</div></div>')
        rows[store] = "".join(cells)
    renderer.sheet(STORE_SHEET.format(name=name, n=len(pics), dark=rows["dark"], light=rows["light"]),
                   out / f"{name}-store-ab.png")
    w = max(len(f) for f, _ in lines + [(f"{name}-store-ab.png", "")])
    files = "\n".join(f"  {f.ljust(w)}   {t}" for f, t in lines)
    (out / "README.txt").write_text(STORE_README.format(name=name, files=files, sheet=f"{name}-store-ab.png".ljust(w)),
                                    encoding="utf-8")
    return written + [f"{name}-store-ab.png", "README.txt"]


# ---------------------------------------------------------------- main

def jsonable(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(type(o))


def render(svgs, out_dir, variants=False, export_files=False, json_out=False, tide=TIDE_SVG, store=False):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bad = 0
    renderer = Renderer()
    try:
        ref, tide_text = tide_reference(renderer, Path(tide))
        tide_im = renderer.image(tide_text, 1024) if tide_text else None
        for svg in map(Path, svgs):
            t0 = time.time()
            try:
                text, root = load_svg(svg)
            except (OSError, ValueError) as e:
                print(f"ERROR {e}", file=sys.stderr)
                bad += 1
                continue
            name = svg.stem
            result = measure(renderer, text, root, name, ref)
            print(report(result, svg, ref))
            if result["info"]["fatal"]:
                print("  缺图层，跳过渲染\n")
                continue
            k = result["info"]["k"]
            looks = {"light": make_light(text), "dark": make_dark(text), "mono": make_mono(text),
                     "small": make_small(text, k)}
            ims = icon_images(renderer, text, looks, result["raw"].get("android_scale", ANDROID_CAP))
            ims["master"].save(out_dir / f"{name}-1024.png")
            build_sheet(renderer, result, ims, tide_im, out_dir / f"{name}-sheet.png")
            written = [f"{name}-1024.png", f"{name}-sheet.png"]
            if variants:
                for look in ("light", "dark", "mono"):
                    (out_dir / f"{name}-{look}.svg").write_text(looks[look], encoding="utf-8")
                    ims[look].save(out_dir / f"{name}-{look}.png")
                    written += [f"{name}-{look}.svg", f"{name}-{look}.png"]
                (out_dir / f"{name}-small.svg").write_text(looks["small"], encoding="utf-8")
                written.append(f"{name}-small.svg")
                for suffix, (mark_svg, mark_im) in make_marks(renderer, text).items():
                    (out_dir / f"{name}-{suffix}.svg").write_text(mark_svg, encoding="utf-8")
                    mark_im.save(out_dir / f"{name}-{suffix}.png")
                    written += [f"{name}-{suffix}.svg", f"{name}-{suffix}.png"]
            if export_files and result["info"]["variant"]:
                print("  这是商店变体（data-variant），不出 --export：平台文件只从母版出")
            elif export_files:
                ex_dir = out_dir / "export" if len(svgs) == 1 else out_dir / "export" / name
                files = export(renderer, text, root, looks, ims, result, ex_dir)
                written.append(str(ex_dir.relative_to(out_dir)) + f"/ ({len(files)} 项)")
            if store:
                if result["info"]["variant"]:
                    print("  这已经是商店变体，不再出 --store-ab")
                else:
                    sb_dir = out_dir / "store-ab" if len(svgs) == 1 else out_dir / "store-ab" / name
                    files = store_ab(renderer, text, result, ims, sb_dir)
                    written.append(str(sb_dir.relative_to(out_dir)) + f"/ ({len(files)} 项)")
            if json_out:
                payload = {"name": name, "file": str(svg), "tide_reference": ref, "metrics": result["raw"],
                           "checks": result["checks"]}
                (out_dir / f"{name}-metrics.json").write_text(
                    json.dumps(payload, ensure_ascii=False, indent=1, default=jsonable), encoding="utf-8")
                written.append(f"{name}-metrics.json")
            print(f"  写入 {out_dir}/: " + ", ".join(written) + f"  ({time.time() - t0:.1f} s)\n")
    finally:
        renderer.close()
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("svgs", nargs="+", type=Path, metavar="ICON.svg")
    ap.add_argument("-o", "--out", type=Path, default=Path("renders"), metavar="DIR")
    ap.add_argument("--variants", action="store_true", help="also write the light, dark, mono and small looks")
    ap.add_argument("--export", action="store_true", help="also write the platform files to DIR/export/")
    ap.add_argument("--store-ab", action="store_true",
                    help="also write the App Store A/B variants (lighter base, rim, category tint) to DIR/store-ab/")
    ap.add_argument("--json", action="store_true", help="also write <name>-metrics.json")
    ap.add_argument("--tide", type=Path, default=TIDE_SVG, metavar="FILE",
                    help="Tide reference SVG (default examples/tide.svg)")
    args = ap.parse_args()
    bad = render(args.svgs, args.out, args.variants, args.export, args.json, args.tide, args.store_ab)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
