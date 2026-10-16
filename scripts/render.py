#!/usr/bin/env python3
"""
Render and check a Rian app icon SVG (graphite style).

  python3 scripts/render.py ICON.svg [more.svg ...] [-o DIR] [--variants] [--export] [--json] [--tide FILE]

Always writes, for each SVG:
  DIR/<name>-1024.png    full-bleed opaque 1024 master, default (graphite) look
  DIR/<name>-sheet.png   review sheet: iOS-masked master; 180/120/80/60/40/29 px (40 and 29 from the small
                         version); light and dark looks; Tinted yellow and blue; Clear on a light and a dark
                         wallpaper; Android circle and squircle masks, themed icon light and dark; the icon next
                         to Tide at the same size
and prints a metrics report, one line per check with value, target and PASS / FAIL / INFO.
Exit code 0 even when a check fails (1 only when an SVG cannot be read).

  --variants  also writes <name>-light.svg/.png, <name>-dark.svg/.png, <name>-mono.svg/.png (transparent)
              and <name>-small.svg (64 px and below: erode 8, no class="detail", no glow)
  --export    also writes DIR/export/ (DIR/export/<name>/ when several SVGs are given):
              ios-1024.png, icon-1024-transparent.png, play-512.png, pwa-192.png, pwa-512.png,
              pwa-maskable-512.png, apple-touch-180.png, favicon-16.png, favicon-32.png, favicon.ico, favicon.svg,
              android-foreground-432.png, android-monochrome-432.png,
              android/mipmap-anydpi-v26/ic_launcher.xml + ic_launcher_round.xml,
              android/drawable/ic_launcher_background.xml,
              android/mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/ic_launcher_foreground.png + _monochrome.png,
              plus legacy 48 dp ic_launcher.png + ic_launcher_round.png for API 25 and below,
              icon-composer/1_body.svg, 2_accent.svg (1_body.png / 2_accent.png when a layer uses a mask
              and cannot be baked to plain paths), icon-composer/README.txt
              Android layers are scaled by min(290 / r_max, 0.72), the PWA maskable icon by
              min(409.6 / r_max, 409.6 / Tide's r_max), so compact icons are not blown up past Tide.
  --json      also writes <name>-metrics.json
  --tide FILE Tide reference for the size checks and the side-by-side cell (default examples/tide.svg;
              falls back to built-in numbers when that file is missing or not a graphite icon)

All numbers are final pixels on the 1024 canvas (after the #subject transform). Layers are rasterised
separately in headless Chromium (Playwright) and measured with numpy. Install once with:
  pip install playwright pillow numpy && playwright install chromium
If a Chromium build already exists on the machine, set CHROMIUM_PATH to its executable.

SVG conventions read here (brief B10, references/construction.md):
  defs: #bg, #body-fill, #accent linearGradients (userSpaceOnUse); optional #glow-blur filter and #cut mask
  #background (full-bleed rect), #subject (transform, data-shape = circle | square | tall | wide | open,
  data-cut="48"), #glow (optional first child: <use href="#accent-shape" filter="url(#glow-blur)"/>),
  #body (<g fill="url(#body-fill)"> with every body piece), #accent-shape (one element, fill url(#accent);
  data-accent="band" for a band accent); on single pieces data-part="band" and class="detail";
  in the #cut mask <g id="cuts" stroke-width="48 / k">.
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

CUT = 48.0                    # cut width between neighbouring pieces, final px
CUT_TOL = 2.0
CUT_ATTR_TOL = 1.0            # #cuts stroke-width x k
ADJACENT = 96                 # pieces closer than this share a cut
THIN_R = 34                   # octagon opening radius: removes everything thinner than about 68
THIN_KEEP = 0.80              # each piece keeps this share of its area after the opening
THIN_REACH = 2 * THIN_R       # a part the opening removes may reach at most this far from what it keeps
                              # (a 45 deg corner reaches about 55, a 30 x 100 stick 79)
CLOSE_R = 30                  # closing radius that shuts the cuts for the silhouette
SLOT_AREA = 1500              # px²: a single piece's closing adds more than this -> a cut that stops inside it
OVERLAP_MAX = 0.002           # body & accent pixels / accent pixels
PIECES = (2, 5)               # connected pieces without class="detail"
MIN_PIECE = 50                # px²: smaller specks are antialiasing noise
DETAIL_SHARE = 2.0            # pieces under this % of the hull are marked class="detail"
LONG_SIDE_MAX = 720
SOLID_RATIO = (0.90, 1.10)    # filled silhouette area / Tide's
OPEN_RATIO = (0.90, 1.15)     # convex hull area / Tide's hull
ACCENT_SHARE = (10.0, 25.0)   # accent / silhouette convex hull, %
ACCENT_SHARE_BAND = (4.0, 15.0)   # one 72 wide band across a 580 circle is about 14 %
GRAD_SPAN = 480               # accent gradient span, final px, centred on the accent shape
BODY_SPAN = 600               # body gradient span, final px, centred on the body
GRAD_TOL = 8
CENTROID_MAX = 12             # filled-silhouette centroid to (512, 512)
BODY_CENTRE = (512, 530)      # with a top protrusion: the body's own centre
BODY_TOL = 6
PROTRUSION_W = 80             # parts thinner than this (an opening of radius 40) count as protrusions
CONTRAST_BODY = 7.0           # body over background, default look
CONTRAST_ACCENT = 3.0         # accent over background, default look
GLOW_OPACITY_MAX = 0.16
GLOW_SD_MAX = 28.0            # stdDeviation x k
CUT_DL_MAX = 8.0              # L* of a cut's centre line minus the background's
BAND_COUNT = (2, 3)
BAND_ANGLE = 45.0             # long axis, y down: top left to bottom right
BAND_ANGLE_TOL = 1.5
BAND_WIDTH = 72.0
BAND_WIDTH_TOL = 2.0
SMALL_ERODE = 8.0             # small version: erode on #subject, final px (cuts 48 -> 64)
SMALL_CHECK = 40              # piece count must hold at this size (FAIL); 29 and 16 px are INFO
SMALL_INFO = 29
SMALL_FAVICON = 16            # favicon-16: only the silhouette has to read
ANDROID_SAFE_R = 313.0        # 66 dp safe circle of a 108 dp layer on the 1024 canvas
ANDROID_R = 290.0             # target r_max: 23 px (~2.4 dp) inside the safe circle
ANDROID_CAP = 0.72            # Tide's factor (290 / 403): compact icons are not blown up past it
PWA_R = 409.6                 # maskable: centre 80 % circle; capped at Tide's factor like Android
KEYLINES = {"circle": "⌀ 580", "square": "520 × 520", "tall": "464 × 580", "wide": "580 × 464",
            "open": "+10% 以内"}
KEYLINE_WH = {"circle": (580, 580), "square": (520, 520), "tall": (464, 580), "wide": (580, 464)}
KEYLINE_NAME = {"square": "方形", "tall": "竖矩形", "wide": "横矩形"}
OPEN_EXTRA = 1.10             # open shapes may be 10 % larger than the keyline of their overall form
SHAPES = ("circle", "square", "tall", "wide", "open")
LINEAR_SIDE = 135.0           # bands stacked towards the lower left of a circle: the Linear logo (forbidden)
BODY_GRAD = "body-fill"       # the body gradient's id (the <g id="body"> group owns "body")

# looks (brief B4): background and body gradient stops, top -> bottom
LOOKS = {
    "default": {"bg": ("#26282B", "#191C1F"), "body": ("#F8F9FB", "#C6C8CB")},
    "light": {"bg": ("#FBFCFE", "#E9EBEE"), "body": ("#333538", "#1E2022")},
    "dark": {"bg": ("#191C1F", "#0E1115"), "body": ("#EDEEEF", "#BDBFC2")},
}
MONO_ACCENT_OPACITY = ".5"
PALETTE = {"蓝": ("#7AAEFF", "#3B7BEA"), "绿": ("#6FD3A6", "#23A36B"), "黄": ("#FFD978", "#F2AE2E"),
           "珊瑚": ("#FF9C86", "#EC5B45"), "紫": ("#B3A6FF", "#7A63F0"), "灰": ("#C8C7C3", "#8E8D89")}
TINTS = (("Tinted 黄", "#F5C542"), ("Tinted 蓝", "#5E9BFF"))
FAVICON_RADIUS = 0.22         # favicon: graphite tile with 22 % corners

# Tide reference used only when the Tide SVG cannot be measured (new Tide: silhouette, hull, r_max, ink).
TIDE_FALLBACK = {"silhouette": 278700.0, "hull": 298700.0, "r_max": 403.0, "ink": 212300.0}

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
    """Apple-style continuous-corner mask (superellipse) on a size x size canvas, as an SVG path.
    Used for previews and for the rounded PWA background; the master stays full-bleed."""
    r = size / 2
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        x = r + r * math.copysign(abs(c) ** (2 / n), c)
        y = r + r * math.copysign(abs(s) ** (2 / n), s)
        pts.append(f"{x:.1f},{y:.1f}")
    return "M" + " L".join(pts) + " Z"


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
    for old in ("line", "backing"):
        if node(root, old) is not None:
            info["errors"].append(f"旧风格的 #{old}：按石墨风格重画")
    if any(e.get("data-part") == "split" for e in root.iter()):
        info["errors"].append('data-part="split" 不再使用（切口宽已覆盖）')
    if any(local(e) in ("text", "image") for e in rendered(root)):
        info["errors"].append("不用 <text> 和位图")
    if root.get("width") or root.get("height") or \
            re.split(r"[\s,]+", (root.get("viewBox") or "").strip()) != ["0", "0", "1024", "1024"]:
        info["errors"].append('根只写 viewBox="0 0 1024 1024"，不写宽高')
    stray = [c for c in root if local(c) in GRAPHIC and c not in (background, subject)]
    if stray:
        info["errors"].append("底上不加任何东西：#background 和 #subject 之外还有 "
                              + ", ".join(f"<{local(c)}>" for c in stray[:3]))

    M = parse_transform(subject.get("transform")) if subject is not None else np.eye(3)
    info["matrix"] = M
    info["k"] = float(math.sqrt(abs(np.linalg.det(M[:2, :2]))))
    info["shape"] = subject.get("data-shape") if subject is not None else None
    info["data_cut"] = subject.get("data-cut") if subject is not None else None
    info["accent_band"] = accent is not None and accent.get("data-accent") == "band"
    info["body_matrix"] = M @ chain_matrix(body, body, P) if body is not None else M
    info["accent_matrix"] = M @ chain_matrix(accent, accent, P) if accent is not None else M

    glow = node(root, "glow")
    if subject is not None:
        kids = [c for c in subject if local(c) in GRAPHIC]
        allowed = [e for e in (glow, body, accent) if e is not None]
        extra = [c for c in kids if c not in allowed]
        if extra:
            info["errors"].append("#subject 里只放 #glow、#body、#accent-shape，多了 "
                                  + ", ".join(f"<{local(c)}{' id=' + c.get('id') if c.get('id') else ''}>"
                                              for c in extra[:3]))
        if body is not None and accent is not None and body in kids and accent in kids \
                and kids.index(accent) < kids.index(body):
            info["errors"].append("#accent-shape 要画在 #body 后面")
    sub_nodes = [e for e in rendered(subject)] if subject is not None else []

    # gradients and fills
    info["bg_grad"] = grad_info(grad(root, url_id(get_prop(background, "fill")) or "bg")) \
        if background is not None else grad_info(grad(root, "bg"))
    info["bg_fill"] = get_prop(background, "fill") if background is not None else None
    info["body_fill"] = get_prop(body, "fill") if body is not None else None
    info["accent_fill"] = get_prop(accent, "fill") if accent is not None else None
    info["body_grad"] = grad_info(grad(root, url_id(info["body_fill"]) or BODY_GRAD))
    info["accent_grad"] = grad_info(grad(root, url_id(info["accent_fill"]) or "accent"))
    # pieces paint with the group's gradient only: no fill of their own, nothing see-through
    own = []
    for group, allowed in ((body, f"url(#{BODY_GRAD})"), (accent, "url(#accent)")):
        if group is None:
            continue
        for e in rendered(group):
            v = get_prop(e, "fill")
            if e is not group and v is not None and v.strip().lower() not in ("inherit", allowed.lower()):
                own.append(f"<{local(e)}> fill={v}")
            for a in ("opacity", "fill-opacity"):
                o = num(get_prop(e, a))
                if o is not None and o < 1:
                    own.append(f"<{local(e)}> {a}={o:g}")
    info["piece_fills"] = own

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

    # cut lines in a mask
    cuts = defn(root, "cuts")
    info["cuts"] = None
    if cuts is not None:
        sw = num(get_prop(cuts, "stroke-width"))
        over = []
        for e in cuts.iter():
            if e is cuts:
                continue
            w = num(get_prop(e, "stroke-width"))
            if w is not None and (sw is None or abs(w - sw) > 1e-6):
                over.append(f"<{local(e)}> {w:g}")
        info["cuts"] = {"stroke_width": sw, "overrides": over}

    info["masked"] = {name: any(get_prop(e, "mask") or get_prop(e, "clip-path") for e in el.iter())
                      for name, el in (("body", body), ("accent", accent)) if el is not None}
    info["bands"] = [e for e in sub_nodes if e.get("data-part") == "band"]
    info["details"] = [e for e in sub_nodes if "detail" in classes(e)]
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


def _look(text, look, glow):
    root = ET.fromstring(strip_xml_prolog(text))
    _set_stops(root, _bg_gradient_id(root), LOOKS[look]["bg"])
    body = node(root, "body")
    _set_stops(root, (url_id(get_prop(body, "fill")) if body is not None else None) or BODY_GRAD, LOOKS[look]["body"])
    if not glow:
        _remove(root, node(root, "glow"))
    return serialize(prune_defs(root))


def make_light(text):
    """Light look: background #FBFCFE -> #E9EBEE, body #333538 -> #1E2022, no glow, accent unchanged."""
    return _look(text, "light", glow=False)


def make_dark(text):
    """iOS Dark look: background #191C1F -> #0E1115, body #EDEEEF -> #BDBFC2, glow kept, accent unchanged."""
    return _look(text, "dark", glow=True)


def make_mono(text):
    """Mono (iOS Tinted / Clear source, Android monochrome): no background, no glow,
    body white 100 %, accent white 50 %."""
    root = ET.fromstring(strip_xml_prolog(text))
    _remove(root, node(root, "background"))
    _remove(root, node(root, "glow"))
    body, accent = node(root, "body"), node(root, "accent-shape")
    _set_stops(root, (url_id(get_prop(body, "fill")) if body is not None else None) or BODY_GRAD,
               ("#FFFFFF", "#FFFFFF"))
    _set_stops(root, (url_id(get_prop(accent, "fill")) if accent is not None else None) or "accent",
               ("#FFFFFF", "#FFFFFF"), MONO_ACCENT_OPACITY)
    return serialize(prune_defs(root))


def make_small(text, k):
    """64 px and below: feMorphology erode 8 final px on #subject (cuts 48 -> 64; on #subject, not on #body,
    because a filter runs before the mask that draws the cuts), drop class="detail", no glow."""
    root = ET.fromstring(strip_xml_prolog(text))
    for el in [e for e in root.iter() if "detail" in classes(e)]:
        _remove(root, el)
    _remove(root, node(root, "glow"))
    subject = node(root, "subject")
    if subject is not None:
        defs = root.find(q("defs"))
        if defs is None:
            defs = ET.Element(q("defs"))
            root.insert(0, defs)
        f = ET.SubElement(defs, q("filter"), {"id": "small-erode"})
        ET.SubElement(f, q("feMorphology"), {"operator": "erode", "radius": f"{SMALL_ERODE / k:.2f}"})
        subject.set("filter", "url(#small-erode)")
    return serialize(prune_defs(root))


def glow_source(text):
    """For the glow layer: #accent-shape moved into <defs>, so only the <use id="glow"> clone paints it.
    (CSS cannot hide the original alone: rules that match it also match its <use> clone.)"""
    root = ET.fromstring(strip_xml_prolog(text))
    accent = node(root, "accent-shape")
    if accent is not None:
        _remove(root, accent)
        defs = root.find(q("defs"))
        if defs is None:
            defs = ET.Element(q("defs"))
            root.insert(0, defs)
        defs.append(accent)
    return serialize(root)


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
    "body": "#background,#glow,#accent-shape" + HIDE,
    "accent": "#background,#glow,#body" + HIDE,
    "glow": "#background,#body" + HIDE,          # applied to glow_source(): only the glow is left
    "all": "#background" + HIDE,
}
MEASURE_CSS = {                                 # extra layers for the checks
    "core": "#background,#glow,.detail" + HIDE,
    "full": "",
    "bg": "#subject" + HIDE,
    "band": "#background,#glow" + HIDE + "#subject{visibility:hidden!important}"
            '[data-part="band"],[data-part="band"] *{visibility:visible!important}',
    "band-detail": "#background,#glow" + HIDE + "#subject{visibility:hidden!important}"
                   '[data-part="band"].detail,[data-part="band"].detail *{visibility:visible!important}',
    "detail": "#background,#glow" + HIDE + "#subject{visibility:hidden!important}"
              ".detail,.detail *{visibility:visible!important}",
}
OPAQUE = {"full", "bg"}

STROKE_JS = """() => {
  const subject = document.getElementById('subject');
  if (!subject) return [];
  const GEO = 'path,circle,rect,ellipse,line,polyline,polygon,text,use';
  const SKIP = 'defs,mask,clipPath,pattern,marker,symbol';
  const out = [], seen = new Set();
  const visit = (el, via) => {
    if (seen.has(el)) return;
    seen.add(el);
    const cs = getComputedStyle(el);
    if (cs.stroke && cs.stroke !== 'none')
      out.push({tag: el.tagName, id: el.id || '', stroke: cs.stroke, width: cs.strokeWidth, via: via});
  };
  for (const el of subject.querySelectorAll(GEO)) {
    if (el.closest(SKIP)) continue;
    visit(el, '');
    if (el.tagName === 'use') {
      const ref = el.getAttribute('href') || el.getAttribute('xlink:href');
      const target = ref && ref.startsWith('#') ? document.getElementById(ref.slice(1)) : null;
      if (target && target.closest('defs')) {
        visit(target, 'use');
        for (const t of target.querySelectorAll(GEO)) visit(t, 'use');
      }
    }
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
        plain = [n for n in names if n != "glow"]
        if plain:
            self.load(svg_text, 1024)
            for n in plain:
                css = LAYER_CSS.get(n, MEASURE_CSS.get(n))
                out[n] = np.asarray(self.shot(css, transparent=n not in OPAQUE).convert("RGBA"))
        if "glow" in names:
            self.load(glow_source(svg_text), 1024)
            out["glow"] = np.asarray(self.shot(LAYER_CSS["glow"]).convert("RGBA"))
        return out

    def strokes(self, svg_text):
        """Computed stroke of every shape in #subject outside masks (inherited and CSS strokes included)."""
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


# ---------------------------------------------------------------- measuring one icon

def silhouette(union):
    """Cuts closed with a radius-30 disk, then holes filled."""
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
            if info["fatal"] or node(root, "line") is not None:
                why = "不是石墨风格（缺 #body / #accent-shape）"
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


def small_counts(renderer, small_svg):
    """Pieces of the small version at 40, 29 and 16 px, split by a lightness threshold between the graphite
    background and the pieces (L* 13 and >= 50)."""
    im = renderer.image(small_svg, 1024)
    bg_mid = (hex_rgb(LOOKS["default"]["bg"][0]) + hex_rgb(LOOKS["default"]["bg"][1])) / 2
    thr = (float(lab_L(bg_mid)) + 60) / 2
    out = {}
    for s in (SMALL_CHECK, SMALL_INFO, SMALL_FAVICON):
        L_ = lab_L(np.asarray(im.resize((s, s), Image.LANCZOS)))
        out[s] = label(L_ > thr)[1]
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
    return (f" → k 改为 {k2:.3g}（切口、圆角用 shapes.py --k {k2:.3g} 重出；translate 跟着重调）")


def thin_reach(cp, opened):
    """How far the parts an opening removed reach from what it kept: (distance, point in cp's frame).
    A corner the opening trims reaches a little; a stick or a thin wedge reaches far."""
    removed = cp & ~opened
    if not removed.any():
        return 0.0, None
    if not opened.any():
        return math.inf, centre_of(removed)
    ys, xs = np.nonzero(opened & dilate(~opened, 1))
    K = np.stack([xs + 0.5, ys + 0.5], 1)
    best = (0.0, None)
    for c in components(removed, MIN_PIECE):
        ys, xs = np.nonzero(c)
        P = np.stack([xs + 0.5, ys + 0.5], 1)
        if len(P) > 6000:
            P = P[:: len(P) // 6000 + 1]
        d, _ = nearest(P, K)
        i = int(d.argmax())
        if d[i] > best[0]:
            best = (float(d[i]), (float(P[i][0]), float(P[i][1])))
    return best


def facing_widths(P, Q, d, idx):
    """Gap widths along a cut: distances from P's edge points to Q (d, idx from nearest(P, Q)), kept where
    the two edges face each other (the nearest point on Q sees P about as far away). Leaves out the outline
    at the cut's mouths, so a parallel cut reads 48 all along and a wedge shows how far it opens."""
    near = d < ADJACENT
    if not near.any():
        return np.zeros(0)
    back, _ = nearest(Q[idx[near]], P)
    return d[near][back >= 0.8 * d[near]]


def measure(renderer, text, root, name, ref):
    info = static_info(root)
    k = info["k"]
    C = []
    raw = {"k": k, "data_shape": info["shape"], "data_cut": info["data_cut"]}
    if info["errors"]:
        C.append(check("structure", "结构", "；".join(info["errors"]), "B10 的 id、图层和顺序", "FAIL"))
    if info["fatal"]:
        return {"name": name, "checks": C, "raw": raw, "info": info}

    # no stroke anywhere in #subject (masks excluded)
    st = renderer.strokes(text)
    raw["strokes"] = len(st)
    if st:
        desc = ", ".join(f"<{s['tag']}{' #' + s['id'] if s['id'] else ''}>{' (经 use)' if s['via'] else ''} "
                         f"stroke {s['stroke']} {s['width']}" for s in st[:3])
        C.append(check("no_stroke", "无描边", f"{len(st)} 处描边：{desc}", "#subject 里没有 stroke", "FAIL"))
    else:
        C.append(check("no_stroke", "无描边", "没有描边", "#subject 里没有 stroke", "PASS"))

    # palette: every stop of the three gradients is one of the allowed pair (no third colour, no light band,
    # no see-through stop), pieces paint only with their group's gradient
    def stop_note(g, pair):
        """'' when the gradient's stops are the pair (first and last) and nothing else, else what is wrong."""
        if not g:
            return "缺渐变"
        st = g["stops"]
        if len(st) < 2 or (st[0], st[-1]) != tuple(pair):
            return "→".join(st[:1] + st[-1:]) or "没有 stop"
        extra = [c for c in st[1:-1] if c not in pair]
        if extra:
            return f"中间多了 {', '.join(extra[:2])}（只能有这两个色值：第二个颜色、亮带都不行）"
        if any(o < 1 for o in g.get("opacities", [])):
            return "stop 半透明"
        return ""

    parts, good = [], True
    bgs = info["bg_grad"]
    bg_vertical = bool(bgs) and bgs["tag"] == "linearGradient" and bgs["x1"] == bgs["x2"] and bgs["y2"] > bgs["y1"]
    note = stop_note(bgs, LOOKS["default"]["bg"])
    if bg_vertical and not note and url_id(info["bg_fill"]):
        parts.append(f"底 {LOOKS['default']['bg'][0]}→{LOOKS['default']['bg'][1]}")
    else:
        parts.append("底 " + (note or str(info["bg_fill"]))
                     + ("" if bg_vertical else " 要从上到下的竖直线性渐变")
                     + f" 应为 {LOOKS['default']['bg'][0]}→{LOOKS['default']['bg'][1]}")
        good = False
    bds = info["body_grad"]
    note = stop_note(bds, LOOKS["default"]["body"])
    if not note and url_id(info["body_fill"]) == BODY_GRAD:
        parts.append(f"主体 {LOOKS['default']['body'][0]}→{LOOKS['default']['body'][1]}")
    else:
        if note:
            parts.append(f"主体 {note} 应为 {LOOKS['default']['body'][0]}→{LOOKS['default']['body'][1]}")
        else:
            parts.append(f"主体 fill 是 {info['body_fill']}，要写 url(#{BODY_GRAD})")
        good = False
    if info["piece_fills"]:
        parts.append("单块自带 fill 或透明度：" + ", ".join(info["piece_fills"][:3]))
        good = False
    acs = info["accent_grad"]
    acc_ends = tuple(acs["stops"][:1] + acs["stops"][-1:]) if acs else ()
    acc_name = next((n_ for n_, v in PALETTE.items() if acc_ends == v), None)
    note = stop_note(acs, PALETTE[acc_name]) if acc_name else ("→".join(acc_ends) or "缺渐变") + " 不在色板"
    if not note and url_id(info["accent_fill"]) == "accent":
        parts.append(f"强调色 {acc_name} {acc_ends[0]}→{acc_ends[1]}")
    else:
        parts.append("强调色 " + (note or f"fill 写 url(#accent)，不是 {info['accent_fill']}"))
        good = False
    raw["accent_colour"] = acc_name
    C.append(check("palette", "颜色", " · ".join(parts), "B4 默认外观 + 六色表", ok(good)))

    names = ["body", "accent", "core", "full", "bg", "glow"]
    if info["bands"]:
        names += ["band", "band-detail"]
    if info["details"]:
        names += ["detail"]
    L = renderer.layers(text, names)
    body_c = L["body"][..., 3].astype(np.float32) / 255
    acc_c = L["accent"][..., 3].astype(np.float32) / 255
    body, acc = body_c >= 0.5, acc_c >= 0.5
    union = body | acc
    cov = np.maximum(body_c, acc_c)
    if not union.any() or not acc.any() or not body.any():
        what = "没有画出任何像素" if not union.any() else ("强调色没有像素" if not acc.any() else "主体没有像素")
        C.append(check("subject", "主体", what, "—", "FAIL"))
        return {"name": name, "checks": C, "raw": raw, "info": info}

    sil = silhouette(union)
    hull = float(hull_area(sil))
    sil_area = float(sil.sum())
    pieces = components(union)
    core = components(L["core"][..., 3] >= 128)
    acc_pieces = components(acc)
    centres = [centre_of(p) for p in pieces]
    none = np.zeros_like(union)
    det_mask = L["detail"][..., 3] >= 128 if "detail" in L else none
    band_det = L["band-detail"][..., 3] >= 128 if "band-detail" in L else none
    is_detail = [bool((p & det_mask).sum() > 0.5 * p.sum()) for p in pieces]
    raw.update(pieces=len(pieces), pieces_core=len(core), accent_pieces=len(acc_pieces))

    # pieces; class="detail" only on fragments under 2 % of the hull or on the shortest band
    lo_p, hi_p = PIECES
    tiny = [p for p in core if 100.0 * p.sum() / hull < DETAIL_SHARE]
    val = f"{len(core)} 块"
    if len(pieces) > len(core):
        val += f"（另有 {len(pieces) - len(core)} 块 detail）"
    good = lo_p <= len(core) <= hi_p
    if tiny:
        val += f" · {100.0 * tiny[0].sum() / hull:.1f} % 凸包的碎块 {at(centre_of(tiny[0]))} 要标 class=\"detail\""
        good = False
    for c in components(det_mask):
        share = 100.0 * c.sum() / hull
        if share >= DETAIL_SHARE and (c & band_det).sum() <= 0.5 * c.sum():
            val += (f" · detail 块占 {share:.1f} % 凸包 {at(centre_of(c))}：detail 只能给 < {DETAIL_SHARE:.0f} % 凸包"
                    "的碎块或最短的那条斜纹带（64 px 及以下它会消失）")
            good = False
            break
    C.append(check("pieces", "块数", val, f"{lo_p}–{hi_p}（不算 detail）", ok(good)))
    C.append(check("accent_count", "强调色块数", f"{len(acc_pieces)} 块", "1（只有一处）", ok(len(acc_pieces) == 1)))

    # cut width between neighbouring pieces (the narrowest point of each pair)
    pts = [edge_points(np.where(dilate(p, 2), cov, 0)) for p in pieces]
    boxes = [bbox(p) for p in pieces]
    pairs = []
    for i in range(len(pieces)):
        for j in range(i + 1, len(pieces)):
            a, b = boxes[i], boxes[j]
            if max(a[0] - b[2], b[0] - a[2], a[1] - b[3], b[1] - a[3]) >= ADJACENT:
                continue
            d, idx = nearest(pts[i], pts[j])
            if not len(d):
                continue
            t = int(d.argmin())
            if d[t] < ADJACENT:
                pa, pb = pts[i][t], pts[j][idx[t]]
                d2, idx2 = nearest(pts[j], pts[i])
                w = np.concatenate([facing_widths(pts[i], pts[j], d, idx), facing_widths(pts[j], pts[i], d2, idx2)])
                pairs.append({"i": i, "j": j, "gap": float(d[t]), "at": [(pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2],
                              "p50": float(np.percentile(w, 50)) if len(w) else float(d[t]),
                              "p90": float(np.percentile(w, 90)) if len(w) else float(d[t])})
    raw["cuts"] = [round(p["gap"], 1) for p in pairs]
    notes, good = [], True
    if pairs:
        gaps = [p["gap"] for p in pairs]
        val = f"{min(gaps):.1f}–{max(gaps):.1f} px · {len(pairs)} 对相邻"
        worst = max(pairs, key=lambda p: abs(p["gap"] - CUT))
        if abs(worst["gap"] - CUT) > CUT_TOL:
            notes.append(f"最差 {worst['gap']:.1f} {at(worst['at'])}")
            good = False
    else:
        val = "没有相邻的块（间距都 ≥ 96）"
        good = False
    # accent to body, on the separately rendered layers: an accent that touches the body merges with it into
    # one piece, so the pairs above never see that cut
    ea, eb = edge_points(acc_c), edge_points(body_c)
    d_ab, i_ab = nearest(ea, eb)
    t = int(d_ab.argmin())
    gap_ab = float(d_ab[t])
    pa, pb = ea[t], eb[i_ab[t]]
    at_ab = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
    raw["accent_gap"] = gap_ab
    merged = [p for p in pieces if (p & body).sum() > MIN_PIECE and (p & acc).sum() > MIN_PIECE]
    if merged:
        notes.append(f"强调色和主体粘成一块 {at(at_ab)}：中间要隔一道 {CUT:.0f} 的切口，不贴边")
        good = False
    elif abs(gap_ab - CUT) > CUT_TOL:
        notes.append(f"强调色到主体最近 {gap_ab:.1f} {at(at_ab)}："
                     + (("贴边了" if gap_ab < 4 else "切口不到 48") if gap_ab < CUT
                        else "要隔正好 48 的切口（离得更远就不是一道切口）"))
        good = False
    else:
        notes.append(f"强调色↔主体 {gap_ab:.1f}")
    dc = num(info["data_cut"])
    if dc is None:
        notes.append("缺 data-cut")
        good = False
    elif abs(dc - CUT) > 1e-6:
        notes.append(f"data-cut {info['data_cut']} 应为 {CUT:.0f}")
        good = False
    else:
        notes.append(f"data-cut {dc:g}")
    if info["cuts"] is not None:
        sw = info["cuts"]["stroke_width"]
        if sw is None:
            notes.append("#cuts 没写 stroke-width")
            good = False
        else:
            eff = sw * k
            raw["cuts_stroke_effective"] = eff
            notes.append(f"#cuts {eff:.1f} px ({sw:g} × {k:.3g})")
            if abs(eff - CUT) > CUT_ATTR_TOL:
                notes[-1] += f" 应为 {CUT:.0f} ± {CUT_ATTR_TOL:.0f}（stroke-width {CUT / k:.2f}）"
                good = False
        if info["cuts"]["overrides"]:
            notes.append("#cuts 里单独的线宽 " + ", ".join(info["cuts"]["overrides"][:3]))
            good = False
    C.append(check("cut", "切口宽", val + " · " + " · ".join(notes), f"相邻每对最窄处 {CUT:.0f} ± {CUT_TOL:.0f}",
                   ok(good), pairs=pairs))
    # how the gap runs along each cut: cut only judges the narrowest point; a wedge opens up away from it
    if pairs:
        wide = max(pairs, key=lambda p: p["p50"])
        raw["cut_spread"] = [[round(p["p50"], 1), round(p["p90"], 1)] for p in pairs]
        C.append(check("cut_spread", "切口沿边宽",
                       f"最宽一对 p50 {wide['p50']:.0f} / p90 {wide['p90']:.0f} {at(wide['at'])} · {len(pairs)} 对",
                       "参考：平行切口约 48 / 52", "INFO"))

    # cuts go all the way through: closing one piece on its own must not fill a slot inside it
    worst = None
    for p, c0 in zip(pieces, centres):
        cp, (ox, oy) = crop(p, CLOSE_R + 4)
        added = disk_close(cp, CLOSE_R) & ~cp
        for a in components(added, 1):
            area = float(a.sum())
            if area > SLOT_AREA and (worst is None or area > worst[0]):
                cx, cy = centre_of(a)
                outside = dilate(a, 1) & ~a & ~cp
                mouths = len(components(outside, 1))
                worst = (area, (cx + ox, cy + oy), mouths)
    if worst:
        kind = "缺口没把形体分成两块" if worst[2] >= 2 else "切口没切透，留下悬空的槽"
        C.append(check("cut_through", "切口贯穿", f"{kind} {at(worst[1])}（{worst[0] / 1000:.1f}k px²）",
                       "每道切口把形体切成两块", "FAIL"))
    else:
        C.append(check("cut_through", "切口贯穿", "没有悬空的槽", "每道切口把形体切成两块", "PASS"))

    # thinnest part: an octagon opening of radius 34 keeps most of every piece, and what it removes stays
    # close to what it keeps (a trimmed corner, not a stick or a thin wedge). detail pieces are dropped at
    # 64 px and below, so they are not judged.
    keeps, reach = [], (0.0, None)
    for p, c0, det in zip(pieces, centres, is_detail):
        if det:
            continue
        cp, (ox, oy) = crop(p, THIN_R + 2)
        opened = octagon_morph(octagon_morph(cp, THIN_R, False, True), THIN_R, True, True) & cp
        keeps.append((float(opened.sum() / cp.sum()), c0))
        r_, pt = thin_reach(cp, opened)
        if r_ > reach[0]:
            reach = (r_, (pt[0] + ox, pt[1] + oy))
    raw["open34_keep"] = [round(100 * v, 1) for v, _ in keeps]
    raw["open34_reach"] = round(reach[0], 1) if math.isfinite(reach[0]) else None
    if keeps:
        k_min, c_min = min(keeps, key=lambda v: v[0])
        good = k_min >= THIN_KEEP and reach[0] <= THIN_REACH
        val = f"开运算 r {THIN_R} 后最少保留 {100 * k_min:.1f} % {at(c_min)}"
        if reach[1] is not None:
            val += f" · 去掉的部分最远 {reach[0]:.0f} px {at(reach[1])}"
            if reach[0] > THIN_REACH:
                val += "：这里有细杆或细楔，最薄不到 72"
        if any(is_detail):
            val += f" · {sum(is_detail)} 块 detail 不查"
        C.append(check("thin", "实形最薄处", val, f"每块 ≥ {THIN_KEEP:.0%}，凸出 ≤ {THIN_REACH}（≈ 最薄 72）", ok(good)))
    else:
        C.append(check("thin", "实形最薄处", "只有 detail 块", "—", "FAIL"))

    # no overlap
    inter = int((body & acc).sum())
    ratio = inter / acc.sum()
    raw["overlap_px"] = inter
    C.append(check("overlap", "不重叠", f"交集 {inter} px²（强调色的 {100 * ratio:.2f} %）",
                   f"≤ {100 * OVERLAP_MAX:.1f} %", ok(ratio <= OVERLAP_MAX)))

    # accent share
    share = 100.0 * acc.sum() / hull
    lo, hi = ACCENT_SHARE_BAND if info["accent_band"] else ACCENT_SHARE
    raw["accent_share"] = share
    C.append(check("accent", "强调色占比", f"{share:.1f} % 强调色 / 凸包" + ("（斜纹带）" if info["accent_band"] else ""),
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
        C.append(check("shape", "形状", "没写 data-shape，按实心算", "circle|square|tall|wide|open", "INFO"))
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
                   f"{OPEN_RATIO[0]:.2f}–{OPEN_RATIO[1]:.2f}" if is_open else "实心形状只看剪影",
                   ok(h_ok) if is_open else "INFO"))
    # ink: the painted area, which is what reads as weight side by side (the size checks fill the cuts in)
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
        # a diagonal composite (cloud and sun, two bubbles) centred on its centroid alone drifts towards its
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

    # contrast against the background (mean colours, background sampled inside the convex hull)
    full, bgim = L["full"][..., :3], L["bg"][..., :3]
    hm = hull_mask(sil)
    bg_mean = bgim[hm].mean(0)
    cb, ca = contrast(full[body].mean(0), bg_mean), contrast(full[acc].mean(0), bg_mean)
    Ll = renderer.layers(make_light(text), ["full", "bg"])
    bg_l = Ll["bg"][..., :3][hm].mean(0)
    cbl, cal = contrast(Ll["full"][..., :3][body].mean(0), bg_l), contrast(Ll["full"][..., :3][acc].mean(0), bg_l)
    raw.update(contrast_body=cb, contrast_accent=ca, contrast_body_light=cbl, contrast_accent_light=cal)
    C.append(check("contrast_body", "主体对底", f"{cb:.1f}:1 · 浅色外观 {cbl:.1f}:1（INFO）",
                   f"默认外观 ≥ {CONTRAST_BODY:.0f}:1", ok(cb >= CONTRAST_BODY)))
    C.append(check("contrast_accent", "强调色对底", f"{ca:.1f}:1 · 浅色外观 {cal:.1f}:1（INFO）",
                   f"默认外观 ≥ {CONTRAST_ACCENT:.0f}:1", ok(ca >= CONTRAST_ACCENT)))

    # glow
    g = info["glow"]
    target = f"≤ 1 个，只在强调色上，≤ {GLOW_OPACITY_MAX:.2f}，σ ≤ {GLOW_SD_MAX:.0f} px"
    glow_a = L["glow"][..., 3].astype(np.float32) / 255
    raw["glow_peak_alpha"] = float(glow_a[~dilate(acc, 1)].max()) if g else 0.0
    probs = []
    if info["other_filters"]:
        probs.append("除 #glow 外还有滤镜 " + ", ".join(info["other_filters"][:3]))
    if g is None:
        C.append(check("glow", "辉光", "没有（可选）" + ("；" + "；".join(probs) if probs else ""), target,
                       ok(not probs)))
    else:
        if g["tag"] != "use" or g["href"] != "accent-shape":
            probs.append('要 <use href="#accent-shape">')
        if not g["first"]:
            probs.append("要是 #subject 的第一个子元素")
        if g["filter"] != "glow-blur":
            probs.append(f"filter 叫 #{g['filter']}，应为 #glow-blur")
        sd = g["sd"] * k if g["sd"] is not None else None
        if sd is None or g["opacity"] is None:
            probs.append("#glow-blur 要有 feGaussianBlur 和 feFlood")
        else:
            if sd > GLOW_SD_MAX + 1e-6:
                probs.append(f"σ {sd:.1f} px 过大")
            if g["opacity"] > GLOW_OPACITY_MAX + 1e-6:
                probs.append(f"不透明度 {g['opacity']:g} 过高")
        if acc_name and g["color"] and g["color"] != PALETTE[acc_name][1]:
            probs.append(f"颜色 {g['color']} 应为强调色的主 {PALETTE[acc_name][1]}")
        if g["offset"]:
            probs.append("不偏移")
        raw.update(glow_opacity=g["opacity"], glow_sd=sd)
        val = "1 个"
        if sd is not None and g["opacity"] is not None:
            val += f" · 不透明度 {g['opacity']:g} · σ {sd:.0f} px · {g['color']}"
        C.append(check("glow", "辉光", val + ("；" + "；".join(probs) if probs else ""), target, ok(not probs)))

    # cut clarity: the centre line of every cut stays close to the background
    mid = np.zeros_like(union)
    r_out, r_in = int(round(CUT / 2 + 2)), int(round(CUT / 2 - 6))
    grown = {}
    for p in pairs:
        for i in (p["i"], p["j"]):
            if i not in grown:
                grown[i] = disk_dilate(pieces[i], r_out)
        mid |= grown[p["i"]] & grown[p["j"]]
    if pairs:
        mid &= ~disk_dilate(union, r_in)
    if mid.any():
        dl = np.abs(lab_L(full[mid]) - lab_L(bgim[mid]))
        dmax = float(dl.max())
        raw["cut_dL"] = dmax
        C.append(check("cut_clarity", "切口清晰度", f"切口中线 ΔL 最多 {dmax:.1f}（{int(mid.sum())} px）",
                       f"≤ {CUT_DL_MAX:.0f}", ok(dmax <= CUT_DL_MAX)))
    else:
        C.append(check("cut_clarity", "切口清晰度", "没有 48 宽的切口可量", f"≤ {CUT_DL_MAX:.0f}", "INFO"))

    # bands
    if info["bands"]:
        C.append(band_check(L, info, (cx, cy), raw))

    # small sizes: same pieces at 40 px as at 1024 (without details)
    n_small = small_counts(renderer, make_small(text, k))
    raw["small_pieces"] = n_small
    C.append(check("small", "小尺寸", f"small 版 {SMALL_CHECK} px {n_small[SMALL_CHECK]} 块 · 1024 px {len(core)} 块",
                   "块数一样（切口没糊）", ok(n_small[SMALL_CHECK] == len(core))))
    C.append(check("small_29", "小尺寸 29", f"small 版 {SMALL_INFO} px {n_small[SMALL_INFO]} 块", "参考", "INFO"))
    C.append(check("small_16", "小尺寸 16", f"small 版 {SMALL_FAVICON} px {n_small[SMALL_FAVICON]} 块（favicon-16）",
                   "参考：16 px 只要剪影认得出", "INFO"))

    # gradients
    c_, extra = gradient_check("body_gradient", "主体渐变", info["body_grad"], info["body_matrix"], body,
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
    a_s, p_s = min(ANDROID_R / r_max, ANDROID_CAP), min(PWA_R / r_max, pwa_cap)
    raw.update(r_max=r_max, android_scale=a_s, pwa_scale=p_s)
    tide_note = f" · Tide r_max {t_r:.0f}" if t_r else ""
    C.append(check("android", "安卓安全圆",
                   f"r_max {r_max:.0f}（安全圆 {ANDROID_SAFE_R:.0f}）→ ×{a_s:.3f}"
                   + (f"（封顶 {ANDROID_CAP}）" if a_s == ANDROID_CAP else "") + tide_note,
                   f"min({ANDROID_R:.0f} / r_max, {ANDROID_CAP})，导出自动缩放", "INFO"))
    C.append(check("pwa", "PWA 遮罩圆", f"r_max {r_max:.0f} {'>' if r_max > PWA_R else '≤'} 409.6 → ×{p_s:.3f}"
                   + (f"（封顶 Tide 的 ×{pwa_cap:.3f}）" if PWA_R / r_max > pwa_cap + 1e-6 else ""),
                   "min(409.6 / r_max, Tide 的系数)，导出自动缩放", "INFO"))
    return {"name": name, "checks": C, "raw": raw, "info": info}


def band_check(L, info, centre, raw):
    """2-3 bands at 45 deg, 72 wide, shorter further out; the shortest one marked class="detail"."""
    target = (f"{BAND_COUNT[0]}–{BAND_COUNT[1]} 条，{BAND_ANGLE:.0f}° ± {BAND_ANGLE_TOL}（\\ 向），"
              f"宽 {BAND_WIDTH:.0f} ± {BAND_WIDTH_TOL:.0f}，越外越短")
    cov = L["band"][..., 3].astype(np.float32) / 255
    det = L["band-detail"][..., 3] >= 128
    bands_ = components(cov >= 0.5)
    probs = []
    if len(bands_) != len(info["bands"]):
        probs.append(f"{len(info['bands'])} 个 data-part=band 只画出 {len(bands_)} 条（带之间要留切口）")
    rows = []
    for m in bands_:
        ys, xs = np.nonzero(m)
        P = np.stack([xs + 0.5, ys + 0.5], 1)
        c = P.mean(0)
        evals, evecs = np.linalg.eigh(np.cov((P - c).T))
        major = evecs[:, 1]
        a = math.degrees(math.atan2(major[1], major[0])) % 180
        nrm = np.array([-major[1], major[0]])
        e = edge_points(np.where(dilate(m, 2), cov, 0))
        width = float((e @ nrm).max() - (e @ nrm).min())
        length = float((e @ major).max() - (e @ major).min())
        dist = abs(float((c - np.array(centre)) @ nrm))
        rows.append({"angle": a, "width": width, "length": length, "dist": dist, "at": c,
                     "detail": bool((m & det).sum() > 0.5 * m.sum())})
    rows.sort(key=lambda r: r["dist"])
    raw["bands"] = [{k_: (round(v, 1) if isinstance(v, float) else v) for k_, v in r.items() if k_ != "at"}
                    for r in rows]
    if not BAND_COUNT[0] <= len(rows) <= BAND_COUNT[1]:
        probs.append(f"{len(rows)} 条")
    for r in rows:
        if abs(r["angle"] - BAND_ANGLE) > BAND_ANGLE_TOL:
            probs.append(f"角度 {r['angle']:.1f}° {at(r['at'])}")
        if abs(r["width"] - BAND_WIDTH) > BAND_WIDTH_TOL:
            probs.append(f"宽 {r['width']:.1f} {at(r['at'])}")
    if any(rows[i + 1]["length"] >= rows[i]["length"] for i in range(len(rows) - 1)):
        probs.append("长度要越外越短")
    if rows:
        shortest = min(rows, key=lambda r: r["length"])
        if not shortest["detail"]:
            probs.append(f"最短那条 {at(shortest['at'])} 要标 class=\"detail\"")
        extra = [r for r in rows if r["detail"] and r is not shortest]
        if extra:
            probs.append(f"detail 只给最短那条，{at(extra[0]['at'])} 这条不是")
        # the Linear logo: a circle whose lower left is cut into bands (B9)
        P = np.array([r["at"] for r in rows]).mean(0) - np.array(centre)
        side = math.degrees(math.atan2(P[1], P[0]))
        if info["shape"] == "circle" and math.hypot(*P) > 40 and abs((side - LINEAR_SIDE + 180) % 360 - 180) <= 30:
            probs.append("圆 + 左下 45° 斜纹就是 Linear 的标：换位置或换物件")
    val = (f"{len(rows)} 条 · 角度 " + "/".join(f"{r['angle']:.1f}" for r in rows) + " · 宽 "
           + "/".join(f"{r['width']:.0f}" for r in rows) + " · 长 " + "/".join(f"{r['length']:.0f}" for r in rows))
    return check("bands", "斜纹", val + ("；" + "；".join(probs) if probs else ""), target, ok(not probs))


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
                 f"data-cut {raw.get('data_cut') or '—'} · Tide 参考: 剪影 {ref['silhouette'] / 1000:.0f}k px², "
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


def _circle(size=1024):
    big = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(big).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    return big.resize((size, size), Image.LANCZOS)


def mask_alpha(name):
    """ios: superellipse n 4 (approximates Apple's mask); squircle: n 3 (Android); circle."""
    if name not in MASKS:
        MASKS[name] = {"ios": lambda: _superellipse(4.0), "squircle": lambda: _superellipse(3.0),
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


def tinted(mono, tint):
    """iOS Tinted, approximated: a dark tinted background, the mono layer in the tint colour."""
    t = hex_rgb(tint).astype(np.float32)
    y = np.linspace(0, 1, 1024, dtype=np.float32)[:, None, None]
    top, bot = t * 0.16 + 6, t * 0.07 + 4
    bg = (top * (1 - y) + bot * y) * np.ones((1, 1024, 1), np.float32)
    a = np.asarray(mono)[..., 3:4].astype(np.float32) / 255
    return Image.fromarray(np.clip(bg * (1 - a) + t * a, 0, 255).astype(np.uint8), "RGB")


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


def clear_tile(mono, kind):
    """iOS Clear, approximated: the blurred wallpaper under a glass tint, mono white at 90 %."""
    g = wallpaper(kind).filter(ImageFilter.GaussianBlur(40)).convert("RGBA")
    tint = Image.new("RGBA", g.size, (0, 0, 0, 46) if kind == "light" else (255, 255, 255, 22))
    g = Image.alpha_composite(g, tint)
    glyph = np.zeros((1024, 1024, 4), np.uint8)
    glyph[..., :3] = 255
    glyph[..., 3] = (np.asarray(mono)[..., 3].astype(np.float32) * 0.9).astype(np.uint8)
    return Image.alpha_composite(g, Image.fromarray(glyph, "RGBA")).convert("RGB")


def themed(mono_scaled, kind):
    """Android themed icon, approximated with fixed tones: light = tone 90 background, tone 10 glyph;
    dark = tone 20 background, tone 90 glyph (the monochrome layer's alpha carries the accent at .5)."""
    bgc, fgc = ("#DCE2F9", "#14213D") if kind == "light" else ("#262B36", "#D6E0F7")
    bg, fg = hex_rgb(bgc), hex_rgb(fgc)
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
    <div class="meta"><h1>{name}</h1><div class="label">默认外观 · 石墨 · iOS 遮罩</div>{stat}</div>
    <div class="vs"><div class="pair">{vs}</div><div class="label">和 Tide 同尺寸，比轻重</div></div>
  </div>
  <div class="strip">{sizes}</div>
  <div class="h">外观（Tinted、Clear 由 mono 近似）</div>
  <div class="row">{looks}</div>
  <div class="h">Android（前景叠背景渐变取 72 dp 可见区；主题图标由 monochrome 近似）</div>
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
    stat_lines = [f'剪影 {raw.get("silhouette_ratio", 0):.2f}× Tide · 凸包 {raw.get("hull_ratio", 0):.2f}×',
                  f'强调色 {raw.get("accent_share", 0):.1f} % · 长边 {raw.get("long_side", 0)} px · '
                  f'{raw.get("pieces_core", 0)} 块',
                  "切口 " + ("–".join(f"{v:.1f}" for v in (min(raw["cuts"]), max(raw["cuts"])))
                            if raw.get("cuts") else "—") + f' · 主体对底 {raw.get("contrast_body", 0):.1f}:1',
                  f'r_max {raw.get("r_max", 0):.0f} · Android ×{raw.get("android_scale", 1):.3f}',
                  f'<span class="bad">FAIL: {", ".join(fails)}</span>' if fails else "全部通过"]
    stat = '<div class="stat">' + "".join(f"<div>{x}</div>" for x in stat_lines) + "</div>"
    vs = cell(tile(ims["master"], 240), 120, result["name"])
    vs += cell(tile(tide_im, 240), 120, "Tide") if tide_im is not None else \
        '<div class="cap">（没有新 Tide 可比）</div>'
    sizes = "".join(cell(tile(ims["small" if s <= 64 else "master"], s), s / 2, f"{s}" + (" small" if s <= 64 else ""))
                    for s in (180, 120, 80, 60, 40, 29))
    T = 220                       # tile px in the grid (110 CSS px)
    looks = [box(cell(tile(ims["light"], T), T / 2, "浅色"), "mid"),
             box(cell(tile(ims["dark"], T), T / 2, "深色 · iOS Dark"), "dark")]
    looks += [box(cell(tile(tinted(ims["mono"], c), T), T / 2, lab), "dark") for lab, c in TINTS]
    looks += [box(cell(tile(clear_tile(ims["mono"], kind), T), T / 2, lab), f"wall-{kind}", wallpaper(kind))
              for kind, lab in (("light", "Clear · 浅壁纸"), ("dark", "Clear · 深壁纸"))]
    android = [box(cell(tile(ims["android"], T, "circle"), T / 2, "圆形遮罩"), "lite"),
               box(cell(tile(ims["android"], T, "squircle"), T / 2, "方圆遮罩"), "lite"),
               box(cell(tile(adaptive_visible(themed(ims["mono_scaled"], "light")), T, "circle"), T / 2,
                        "主题图标 · 浅"), "mid"),
               box(cell(tile(adaptive_visible(themed(ims["mono_scaled"], "dark")), T, "circle"), T / 2,
                        "主题图标 · 深"), "dark"),
               box(cell(tile(ims["android"], 96, "circle"), 48, "圆形 48"), "lite"),
               box(cell(over(Image.new("RGB", (1024, 1024), (60, 64, 72)), ims["mono"]).resize((T, T), Image.LANCZOS),
                        T / 2, "mono 层"), "lite")]
    html = SHEET.format(hero=png_uri(tile(ims["master"], 480)), name=result["name"], stat=stat, vs=vs,
                        sizes=sizes, looks="".join(looks), android="".join(android))
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
    """Path data for a basic shape element, None when it has no fill area."""
    t = local(el)
    g = lambda a, dflt=0.0: num(el.get(a), dflt)
    if t == "path":
        return el.get("d")
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
        if len(v) < 6:
            return None
        return "M " + " L ".join(f"{v[i]} {v[i + 1]}" for i in range(0, len(v) - 1, 2)) + " Z"
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
        if t == "line":
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

文件
  {f1}   组 1：主体，整张 1024 画布{n1}
  {f2}   组 2：强调色块，整张 1024 画布{n2}

在 Icon Composer 里手动设
  Background     Fill 用渐变。Default：#26282B → #191C1F；Dark：#191C1F → #0E1115
  组 1（主体）   Specular Automatic；Shadow Neutral
  组 2（强调色） Specular Automatic；Shadow Chromatic（代替平面版里的辉光，以实际版本的选项为准）
  Mono           主体 White；强调色 50 % 灰

层文件里没有辉光、遮罩、背景、圆角、阴影和半透明。
"""

IC_LAUNCHER = """<?xml version="1.0" encoding="utf-8"?>
<!-- {title}: adaptive icon, three layers (API 26 and up). Foreground and monochrome are scaled by {a_s:.3f}
     (r_max {r_max:.0f}; min(290 / r_max, 0.72)): inside the 66 dp safe circle, same relative size as on iOS.
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
    for ident, gid, num_, css, name in (("body", "body", 1, "body", "body"), ("accent-shape", "accent", 2, "accent",
                                                                            "accent")):
        paths = bake_layer(root, ident, info)
        g = info["body_grad"] if gid == "body" else info["accent_grad"]
        M = info["body_matrix"] if gid == "body" else info["accent_matrix"]
        for stale in (out / f"{num_}_{name}.svg", out / f"{num_}_{name}.png"):
            if stale.exists():
                stale.unlink()
        if paths and g is not None and g["units"] == "userSpaceOnUse":
            body = "\n".join(f'    <path d="{d}"' + (f' fill-rule="{r}"' if r else "") + "/>" for d, r in paths)
            svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">\n'
                   f"  <!-- {title}: Icon Composer group {num_}, the {name}. Final pixels, transform baked in. -->\n"
                   f"  <defs>{layer_gradient_svg(gid, g, M)}</defs>\n"
                   f'  <g fill="url(#{gid})">\n{body}\n  </g>\n</svg>\n')
            (out / f"{num_}_{name}.svg").write_text(svg, encoding="utf-8")
            files.append((f"{num_}_{name}.svg", "，transform 已烘焙进坐标，保留渐变"))
        else:
            L = renderer.layers(text, [css])[css]
            Image.fromarray(L, "RGBA").save(out / f"{num_}_{name}.png")
            files.append((f"{num_}_{name}.png", "（用了遮罩或无法写成纯路径，改出 PNG 层）"))
    (out / "README.txt").write_text(IC_README.format(title=title, f1=files[0][0], n1=files[0][1],
                                                     f2=files[1][0], n2=files[1][1]), encoding="utf-8")
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


def render(svgs, out_dir, variants=False, export_files=False, json_out=False, tide=TIDE_SVG):
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
            if export_files:
                ex_dir = out_dir / "export" if len(svgs) == 1 else out_dir / "export" / name
                files = export(renderer, text, root, looks, ims, result, ex_dir)
                written.append(str(ex_dir.relative_to(out_dir)) + f"/ ({len(files)} 项)")
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
    ap.add_argument("--json", action="store_true", help="also write <name>-metrics.json")
    ap.add_argument("--tide", type=Path, default=TIDE_SVG, metavar="FILE",
                    help="Tide reference SVG (default examples/tide.svg)")
    args = ap.parse_args()
    bad = render(args.svgs, args.out, args.variants, args.export, args.json, args.tide)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
