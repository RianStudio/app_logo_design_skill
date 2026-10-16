#!/usr/bin/env python3
"""
Render and check a Rian app icon SVG (minimal line style).

  python3 scripts/render.py ICON.svg [more.svg ...] [-o DIR] [--variants] [--export] [--json]

Always writes, for each SVG:
  DIR/<name>-1024.png    full-bleed opaque 1024 master (Xcode / App Store Connect / Icon Composer)
  DIR/<name>-sheet.png   review sheet: iOS-masked master, 180/120/80/60/40/29 px, the icon next to Tide
                         at the same size, the dark and tinted variants, 32/16 px favicon tests
and prints a metrics report, one line per check with value, target and PASS / FAIL / INFO.
Exit code 0 even when a check fails (1 only when an SVG cannot be read).

  --variants  also writes <name>-dark.svg/.png and <name>-tinted.svg/.png
  --export    also writes DIR/export/ (DIR/export/<name>/ when several SVGs are given):
              ios-1024.png (opaque), icon-1024-transparent.png, android-foreground-432.png,
              android-monochrome-432.png, pwa-192.png, pwa-512.png, pwa-maskable-512.png,
              apple-touch-180.png, favicon-16.png, favicon-32.png, favicon.ico, favicon.svg
              Android layers are scaled by 313 / r_max, the PWA maskable icon by 409.6 / r_max.
  --json      also writes <name>-metrics.json

All numbers are final pixels on the 1024 canvas (after the #subject transform). Areas are compared with
examples/tide.svg, measured at run time. Layers are rasterised separately in headless Chromium
(Playwright) and measured with numpy. Install once with:
  pip install playwright && playwright install chromium
If a Chromium build already exists on the machine, set CHROMIUM_PATH to its executable.

SVG conventions read here (see references/construction.md):
  #background, #subject (transform, data-shape = circle | square | tall | wide | open),
  #backing (first child of #subject), #accent-shape (data-accent="line" for a scan beam),
  #line (one stroke width); on single lines class="on-accent", class="detail", data-part="split".
"""

import argparse
import base64
import copy
import glob
import heapq
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
from PIL import Image

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

SKILL_DIR = Path(__file__).resolve().parent.parent
TIDE_SVG = SKILL_DIR / "examples" / "tide.svg"

# ---------------------------------------------------------------- house rules (references/style.md)

STROKE = 52.0                 # line width after scaling
STROKE_TOL = 1.0
LONG_SIDE_MAX = 740
SOLID_RATIO = (0.90, 1.10)    # filled silhouette area / Tide's
OPEN_RATIO = (0.90, 1.15)     # convex hull area / Tide's hull
ACCENT_SHARE = (15.0, 30.0)   # visible accent / subject convex hull, %
ACCENT_SHARE_LINE = (8.0, 15.0)
GAP_LINE = 78                 # clear gap between separate lines
GAP_SPLIT = 52                # two parts of one object cut apart (data-part="split")
GAP_ACCENT = 40               # free accent edge to a line; on-accent line to the accent edge
GAP_TOL = 1.0                 # pixel measurement tolerance for the gap checks
JUNCTION_ARC = 47             # free accent edge this close (along the edge) to where it leaves a line is exempt
GRAD_SPAN = 480               # accent gradient span, final px, centred on the accent shape
GRAD_TOL = 8
CENTROID_MAX = 12             # filled-silhouette centroid to (512, 512)
BODY_CENTRE = (512, 530)      # with a top protrusion: the body's own centre
BODY_TOL = 6
PROTRUSION_W = 80             # parts thinner than this (an opening of radius 40) count as protrusions
ANDROID_R = 313.0             # 66 dp safe circle of a 108 dp layer on the 1024 canvas
PWA_R = 409.6                 # maskable: centre 80 % circle
KEYLINES = {"circle": "⌀ 600", "square": "540 × 540", "tall": "480 × 600", "wide": "600 × 480",
            "open": "+10% 以内"}
SHAPES = ("circle", "square", "tall", "wide", "open")

INK = "#1C1C1E"
KNOCK = "#FFFFFF"
BG_LIGHT = ("#FFFFFF", "#EEEEEB")
PALETTE = {"蓝": ("#7AAEFF", "#3B7BEA"), "绿": ("#6FD3A6", "#23A36B"), "黄": ("#FFD978", "#F2AE2E"),
           "珊瑚": ("#FF9C86", "#EC5B45"), "紫": ("#B3A6FF", "#7A63F0"), "灰": ("#C8C7C3", "#8E8D89")}

# variants
DARK_BG = ("#3A3A3D", "#1C1C1E")
DARK_INK = "#F5F5F7"
DARK_KNOCK = "#3A3A3D"
DARK_LIFT = ".35"
TINT_ACCENT_OPACITY = ".4"
SMALL_STROKE = 72.0

# Tide reference used only when examples/tide.svg cannot be found next to this script.
TIDE_FALLBACK = {"silhouette": 288000.0, "hull": 315800.0}

NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
GRAPHIC = {"path", "circle", "rect", "ellipse", "line", "polyline", "polygon", "use", "g", "text", "image"}


# ---------------------------------------------------------------- kept helpers (imported elsewhere)

def squircle_path(size=1024, n=4.0, steps=360):
    """Apple-style continuous-corner mask (superellipse) on a size x size canvas, as an SVG path.
    Used for previews and for the rounded favicon / PWA background; the master stays full-bleed."""
    r = size / 2
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        x = r + r * math.copysign(abs(c) ** (2 / n), c)
        y = r + r * math.copysign(abs(s) ** (2 / n), s)
        pts.append(f"{x:.1f},{y:.1f}")
    return "M" + " L".join(pts) + " Z"


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


def by_id(root, ident):
    return next((e for e in root.iter() if e.get("id") == ident), None)


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


def norm_color(c):
    c = (c or "").strip().lower()
    named = {"white": "#ffffff", "black": "#000000"}
    c = named.get(c, c)
    if re.fullmatch(r"#[0-9a-f]{3}", c):
        c = "#" + "".join(ch * 2 for ch in c[1:])
    return c


def is_white(c):
    return norm_color(c) == "#ffffff"


def is_ink(c):
    c = norm_color(c)
    if not re.fullmatch(r"#[0-9a-f]{6}", c):
        return False
    r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b < 80


def url_id(v):
    m = re.match(r"\s*url\(\s*#([^)\s]+)\s*\)", v or "")
    return m.group(1) if m else None


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


def gradient_stops(grad):
    return [norm_color(get_prop(s, "stop-color")).upper() for s in grad.iter(q("stop"))]


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

def static_info(root):
    info = {"errors": []}
    subject = by_id(root, "subject")
    line = by_id(root, "line")
    accent = by_id(root, "accent-shape")
    background = by_id(root, "background")
    if subject is None:
        info["errors"].append("缺 #subject")
    if line is None:
        info["errors"].append("缺 #line")
    if accent is None:
        info["errors"].append("缺 #accent-shape")
    M = parse_transform(subject.get("transform")) if subject is not None else np.eye(3)
    info["matrix"] = M
    info["k"] = float(math.sqrt(abs(np.linalg.det(M[:2, :2]))))
    info["shape"] = subject.get("data-shape") if subject is not None else None
    info["accent_line"] = (accent is not None and accent.get("data-accent") == "line")

    sw = None
    overrides = []
    if line is not None:
        v = get_prop(line, "stroke-width")
        sw = float(re.sub(r"px$", "", v)) if v else 1.0
        for e in line.iter():
            if e is line:
                continue
            w = get_prop(e, "stroke-width")
            if w is not None and abs(float(re.sub(r"px$", "", w)) - sw) > 1e-6:
                overrides.append(f"{local(e)}={w}")
    info["stroke_attr"] = sw
    info["stroke_overrides"] = overrides
    info["has_split"] = line is not None and any(e.get("data-part") == "split" for e in line.iter())
    info["has_on_accent"] = line is not None and any("on-accent" in classes(e) for e in line.iter())
    info["has_detail"] = line is not None and any("detail" in classes(e) for e in line.iter())

    # colours
    grads = {g.get("id"): g for g in root.iter(q("linearGradient"))}
    acc_grad = grads.get(url_id(get_prop(accent, "fill"))) if accent is not None else None
    bg_grad = grads.get(url_id(get_prop(background, "fill"))) if background is not None else None
    info["accent_stops"] = gradient_stops(acc_grad) if acc_grad is not None else []
    info["accent_fill"] = get_prop(accent, "fill") if accent is not None else None
    info["bg_stops"] = gradient_stops(bg_grad) if bg_grad is not None else []
    info["bg_fill"] = get_prop(background, "fill") if background is not None else None
    info["ink"] = norm_color(get_prop(line, "stroke")).upper() if line is not None else None
    other_fills, knock_fills = [], []
    if line is not None:
        for e in line.iter():
            f = get_prop(e, "fill")
            if f is None or f.strip().lower() in ("none", "currentcolor") or is_ink(f):
                continue
            (knock_fills if is_white(f) else other_fills).append(f)
    info["knock_fills"] = knock_fills
    info["other_fills"] = other_fills
    info["grad"] = None
    if acc_grad is not None:
        units = acc_grad.get("gradientUnits", "objectBoundingBox")
        y1, y2 = acc_grad.get("y1"), acc_grad.get("y2")
        info["grad"] = {"units": units,
                        "y1": float(y1) if y1 and not y1.endswith("%") else None,
                        "y2": float(y2) if y2 and not y2.endswith("%") else None}

    # backing
    info["backing"] = None
    backing = by_id(root, "backing")
    if backing is not None and subject is not None:
        kids = [c for c in subject if local(c) in GRAPHIC]
        info["backing"] = {"first": bool(kids) and kids[0] is backing,
                           "fill": get_prop(backing, "fill")}
    flood = [f for f in root.iter(q("feFlood"))]
    info["lift_opacity"] = flood[0].get("flood-opacity") if flood else None
    return info


# ---------------------------------------------------------------- variants (SVG DOM rewrites)

def _set_bg(root, stops):
    bg = by_id(root, "background")
    gid = url_id(get_prop(bg, "fill")) if bg is not None else "bg"
    grad = by_id(root, gid or "bg")
    if grad is None:
        return
    st = list(grad.iter(q("stop")))
    if st:
        set_prop(st[0], "stop-color", stops[0])
        set_prop(st[-1], "stop-color", stops[1])


def _remove(root, el):
    if el is not None:
        P = parents(root)
        if el in P:
            P[el].remove(el)


def _subtree(el):
    return set(el.iter()) if el is not None else set()


def make_dark(text):
    """bg #3A3A3D -> #1C1C1E, lines #F5F5F7, knock-out fills #3A3A3D, lift .35, accent unchanged,
    class="on-accent" lines stay #1C1C1E."""
    root = ET.fromstring(strip_xml_prolog(text))
    _set_bg(root, DARK_BG)
    for f in root.iter(q("feFlood")):
        f.set("flood-opacity", DARK_LIFT)
    subject = by_id(root, "subject")
    if subject is None:
        return serialize(root)
    skip = _subtree(by_id(root, "accent-shape")) | _subtree(by_id(root, "backing"))
    on_roots = [e for e in subject.iter() if "on-accent" in classes(e)]
    on = set().union(*[_subtree(e) for e in on_roots]) if on_roots else set()
    for el in subject.iter():
        if el in skip or el in on:
            continue
        for prop in ("stroke", "fill", "color"):
            v = get_prop(el, prop)
            if v is None:
                continue
            if is_ink(v):
                set_prop(el, prop, DARK_INK)
            elif prop == "fill" and is_white(v):
                set_prop(el, prop, DARK_KNOCK)
    for el in on_roots:
        for prop in ("stroke", "color"):
            v = get_prop(el, prop)
            if v is None or is_ink(v):
                set_prop(el, prop, INK)
    return serialize(root)


def _knockout(root, subject, K, n):
    """Hide everything painted before K (inside #subject) under K's shape, with a mask per nesting level."""
    P = parents(root)
    chain = [K]
    while chain[-1] is not subject:
        chain.append(P[chain[-1]])
    chain.reverse()                       # [subject, line, ..., K]
    defs = root.find(q("defs"))
    if defs is None:
        defs = ET.Element(q("defs"))
        root.insert(0, defs)
    for lvl in range(len(chain) - 1):
        A, child = chain[lvl], chain[lvl + 1]
        kids = list(A)
        before = [c for c in kids[:kids.index(child)] if local(c) in GRAPHIC]
        if not before:
            continue
        tr = " ".join(c.get("transform") for c in chain[lvl + 1:] if c.get("transform"))
        mid = f"knockout-{n}-{lvl}"
        mask = ET.SubElement(defs, q("mask"), {"id": mid, "maskUnits": "userSpaceOnUse",
                                               "x": "-4096", "y": "-4096", "width": "9216", "height": "9216"})
        ET.SubElement(mask, q("rect"), {"x": "-4096", "y": "-4096", "width": "9216", "height": "9216",
                                        "fill": "#FFFFFF"})
        clone = copy.deepcopy(K)
        for a in ("id", "class", "mask", "filter", "style", "fill-opacity", "opacity", "data-part"):
            clone.attrib.pop(a, None)
        clone.set("fill", "#000000")
        clone.set("stroke", "none")
        if tr:
            clone.set("transform", tr)
        else:
            clone.attrib.pop("transform", None)
        mask.append(clone)
        g = ET.Element(q("g"), {"mask": f"url(#{mid})"})
        at = kids.index(before[0])
        for c in before:
            A.remove(c)
            g.append(c)
        A.insert(at, g)


def make_tinted(text):
    """No background, no lift, lines white 100 %, accent white 40 %, knock-out shapes become masks."""
    root = ET.fromstring(strip_xml_prolog(text))
    _remove(root, by_id(root, "background"))
    _remove(root, by_id(root, "backing"))
    for el in root.iter():
        el.attrib.pop("filter", None)
    subject = by_id(root, "subject")
    accent = by_id(root, "accent-shape")
    line = by_id(root, "line")
    if accent is not None:
        for el in accent.iter():
            if url_id(get_prop(el, "fill")) or el is accent:
                set_prop(el, "fill", "#FFFFFF")
        accent.set("fill-opacity", TINT_ACCENT_OPACITY)
    knocks = []
    if line is not None:
        for el in line.iter():
            for prop in ("stroke", "fill", "color"):
                v = get_prop(el, prop)
                if v is None:
                    continue
                if is_ink(v):
                    set_prop(el, prop, "#FFFFFF")
                elif prop == "fill" and is_white(v) and el is not line:
                    knocks.append(el)
    if subject is not None:
        for n, K in enumerate(knocks):
            _knockout(root, subject, K, n)
            set_prop(K, "fill", "none")
    return serialize(prune_defs(root))


def make_small(text, k):
    """Favicon / small sizes: drop class="detail", stroke 72 after scaling, no lift."""
    root = ET.fromstring(strip_xml_prolog(text))
    for el in [e for e in root.iter() if "detail" in classes(e)]:
        _remove(root, el)
    for el in root.iter():
        el.attrib.pop("filter", None)
    line = by_id(root, "line")
    if line is not None:
        w = f"{SMALL_STROKE / k:.2f}"
        for el in line.iter():
            if el is line or get_prop(el, "stroke-width") is not None:
                set_prop(el, "stroke-width", w)
    return serialize(prune_defs(root))


def with_scale(text, s):
    """Scale the subject about the canvas centre (platform exports)."""
    root = ET.fromstring(strip_xml_prolog(text))
    subject = by_id(root, "subject")
    if subject is not None and abs(s - 1) > 1e-6:
        subject.set("transform", f"translate(512 512) scale({s:.4f}) translate(-512 -512) "
                    + (subject.get("transform") or ""))
    return serialize(root)


def without_background(text):
    root = ET.fromstring(strip_xml_prolog(text))
    _remove(root, by_id(root, "background"))
    return serialize(root)


def with_rounded_background(text):
    root = ET.fromstring(strip_xml_prolog(text))
    bg = by_id(root, "background")
    if bg is not None:
        P = parents(root)
        parent = P[bg]
        i = list(parent).index(bg)
        parent.remove(bg)
        parent.insert(i, ET.Element(q("path"), {"id": "background", "d": squircle_path(),
                                                "fill": get_prop(bg, "fill") or "#FFFFFF"}))
    return serialize(root)


# ---------------------------------------------------------------- rasterising

BASE_CSS = "#background,#backing{display:none!important}#subject{filter:none!important}"
LAYER_CSS = {
    "line": BASE_CSS + "#accent-shape{display:none!important}",
    "accent": BASE_CSS + "#line{display:none!important}",
    "split": BASE_CSS + "#accent-shape{display:none!important}#line{visibility:hidden!important}"
             '#line [data-part="split"],#line [data-part="split"] *{visibility:visible!important}',
    "on": BASE_CSS + "#accent-shape{display:none!important}#line{visibility:hidden!important}"
          "#line .on-accent,#line .on-accent *{visibility:visible!important}",
}


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
        self.load(svg_text, 1024)
        return {n: np.asarray(self.shot(LAYER_CSS[n]).convert("RGBA")) for n in names}

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


def fill_holes(mask):
    lab, _ = label(~mask)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    return mask | ((~mask) & ~np.isin(lab, border))


def boundary(mask):
    inner = mask.copy()
    inner[1:, :] &= mask[:-1, :]
    inner[:-1, :] &= mask[1:, :]
    inner[:, 1:] &= mask[:, :-1]
    inner[:, :-1] &= mask[:, 1:]
    inner[0, :] = inner[-1, :] = False
    inner[:, 0] = inner[:, -1] = False
    return mask & ~inner


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


def octagon_morph(mask, r, grow):
    """Erode (grow=False) or dilate (grow=True) by an octagon of radius r (alternating 4- and 8-neighbour steps)."""
    m = mask
    for i in range(r):
        n = m.copy()
        shifts = [((1, 0), (0, 0)), ((0, 0), (1, 0)), ((0, 1), (0, 0)), ((0, 0), (0, 1))]
        if i % 2:
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


def top_protrusion(filled):
    """Body of the silhouette without thin top parts (button, binder rings, handle), or None.
    An opening removes everything thinner than PROTRUSION_W; it counts as a top protrusion only when
    the body keeps most of the area and only the top edge moved."""
    x0, y0, x1, y1 = bbox(filled)
    r = PROTRUSION_W // 2
    pad_ = r + 4
    crop = np.zeros((y1 - y0 + 2 * pad_, x1 - x0 + 2 * pad_), bool)
    crop[pad_:-pad_, pad_:-pad_] = filled[y0:y1, x0:x1]
    opened = octagon_morph(octagon_morph(crop, r, False), r, True)
    if not opened.any() or opened.sum() < 0.75 * crop.sum():
        return None
    ox0, oy0, ox1, oy1 = bbox(opened)
    ox0, ox1, oy0, oy1 = ox0 - pad_ + x0, ox1 - pad_ + x0, oy0 - pad_ + y0, oy1 - pad_ + y0
    if oy0 - y0 > 24 and (y1 - oy1) <= 12 and (ox0 - x0) <= 12 and (x1 - ox1) <= 12:
        # area centroid of the body: insensitive to the small bump the opening leaves where a stem joins
        ys, xs = np.nonzero(opened)
        cx, cy = xs.mean() + 0.5 - pad_ + x0, ys.mean() + 0.5 - pad_ + y0
        return {"centre": (float(cx), float(cy)), "height": oy0 - y0, "bbox": [ox0, oy0, ox1, oy1]}
    return None


def points(mask):
    ys, xs = np.nonzero(mask)
    return np.stack([xs, ys], 1).astype(np.float64)


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


def hull_area(mask):
    rows = np.nonzero(mask.any(1))[0]
    if len(rows) == 0:
        return 0.0
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
    h = lo[:-1] + up[:-1]
    return abs(sum(h[i][0] * h[(i + 1) % len(h)][1] - h[(i + 1) % len(h)][0] * h[i][1]
                   for i in range(len(h)))) / 2


def geodesic_from(seeds, allowed):
    """Arc length along the 8-connected pixel set `allowed`, from the seed pixels (Dijkstra)."""
    ys, xs = np.nonzero(allowed)
    index = {(y, x): i for i, (y, x) in enumerate(zip(ys.tolist(), xs.tolist()))}
    dist = np.full(len(ys), np.inf)
    heap = []
    for y, x in zip(*np.nonzero(seeds & allowed)):
        i = index[(int(y), int(x))]
        dist[i] = 0.0
        heap.append((0.0, i))
    heapq.heapify(heap)
    steps = [(dy, dx, math.hypot(dy, dx)) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
    ylist, xlist = ys.tolist(), xs.tolist()
    while heap:
        d, i = heapq.heappop(heap)
        if d > dist[i]:
            continue
        y, x = ylist[i], xlist[i]
        for dy, dx, w in steps:
            j = index.get((y + dy, x + dx))
            if j is not None and d + w < dist[j]:
                dist[j] = d + w
                heapq.heappush(heap, (d + w, j))
    out = np.full(allowed.shape, np.inf)
    out[ys, xs] = dist
    return out


def bbox(mask):
    ys, xs = np.nonzero(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


# ---------------------------------------------------------------- measuring one icon

def ink_coverage(rgba):
    """Ink coverage 0..1 of a line layer: alpha, minus the white knock-out fills (alpha 1, light colour)."""
    a = rgba[..., 3].astype(np.float32) / 255
    lum = rgba[..., :3].astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
    return a * np.clip((255 - lum) / (255 - 28), 0, 1)


def measure_masks(L):
    """Coverages and masks from the separately rasterised layers."""
    occ_c = L["line"][..., 3].astype(np.float32) / 255
    ink_c = ink_coverage(L["line"])
    acc_c = L["accent"][..., 3].astype(np.float32) / 255
    occ, ink, acc = occ_c >= 0.5, ink_c >= 0.5, acc_c >= 0.5
    return {"occ": occ, "ink": ink, "acc": acc, "sil": occ | acc, "ink_c": ink_c, "acc_c": acc_c}


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


def tide_reference(renderer, cache={}):
    if "ref" in cache:
        return cache["ref"]
    ref = None
    if TIDE_SVG.exists():
        try:
            text, _ = load_svg(TIDE_SVG)
            m = measure_masks(renderer.layers(text, ["line", "accent"]))
            if m["sil"].any():
                ref = {"silhouette": float(fill_holes(m["sil"]).sum()), "hull": float(hull_area(m["sil"])),
                       "source": str(TIDE_SVG)}
        except (OSError, ValueError) as e:
            print(f"WARNING Tide reference: {e}", file=sys.stderr)
    if ref is None:
        ref = dict(TIDE_FALLBACK, source="built-in (examples/tide.svg not usable)")
    cache["ref"] = ref
    return ref


def check(key, label_, value, target, status, **data):
    return {"key": key, "label": label_, "value": value, "target": target, "status": status, "data": data}


def measure(renderer, text, root, name, ref):
    info = static_info(root)
    k = info["k"]
    names = ["line", "accent"] + (["split"] if info["has_split"] else []) + (["on"] if info["has_on_accent"] else [])
    L = renderer.layers(text, names)
    m = measure_masks(L)
    occ, ink, acc, sil = m["occ"], m["ink"], m["acc"], m["sil"]
    C = []
    raw = {"k": k, "data_shape": info["shape"]}

    # stroke
    if info["stroke_attr"] is not None:
        eff = info["stroke_attr"] * k
        ok = abs(eff - STROKE) <= STROKE_TOL and not info["stroke_overrides"]
        val = f"{eff:.1f} px ({info['stroke_attr']:g} × {k:.3g})"
        if info["stroke_overrides"]:
            val += " · 单独线宽 " + ", ".join(info["stroke_overrides"])
        C.append(check("stroke", "线宽", val, f"{STROKE:.0f} ± {STROKE_TOL:.0f}", "PASS" if ok else "FAIL",
                       effective=eff))
        raw["stroke_effective"] = eff
    else:
        C.append(check("stroke", "线宽", "缺 #line", f"{STROKE:.0f} ± {STROKE_TOL:.0f}", "FAIL"))

    if not sil.any():
        C.append(check("subject", "主体", "没有画出任何像素", "—", "FAIL"))
        return {"name": name, "checks": C, "raw": raw, "info": info, "masks": m}

    x0, y0, x1, y1 = bbox(sil)
    w, h = x1 - x0, y1 - y0
    raw.update(bbox=[x0, y0, x1, y1], width=w, height=h, long_side=max(w, h))
    C.append(check("long_side", "长边", f"{max(w, h)} px ({w} × {h})", f"≤ {LONG_SIDE_MAX}",
                   "PASS" if max(w, h) <= LONG_SIDE_MAX else "FAIL"))

    shape = info["shape"]
    if shape in SHAPES:
        C.append(check("shape", "形状", f"{shape} · 外框 {w} × {h}", f"关键线 {KEYLINES[shape]}", "INFO"))
    elif shape is None:
        C.append(check("shape", "形状", "没写 data-shape，按实心算", "circle|square|tall|wide|open", "INFO"))
    else:
        C.append(check("shape", "形状", f'data-shape="{shape}" 不认识', "circle|square|tall|wide|open", "FAIL"))
    is_open = shape == "open"

    filled = fill_holes(sil)
    sil_area = float(filled.sum())
    hull = float(hull_area(sil))
    sr, hr = sil_area / ref["silhouette"], hull / ref["hull"]
    raw.update(silhouette_area=sil_area, hull_area=hull, silhouette_ratio=sr, hull_ratio=hr)
    s_ok = SOLID_RATIO[0] <= round(sr, 2) <= SOLID_RATIO[1]
    h_ok = OPEN_RATIO[0] <= round(hr, 2) <= OPEN_RATIO[1]
    C.append(check("silhouette", "剪影面积", f"{sr:.2f} × Tide ({sil_area / 1000:.0f}k px²)",
                   f"{SOLID_RATIO[0]:.2f}–{SOLID_RATIO[1]:.2f}" if not is_open else "开放形状只看凸包",
                   ("PASS" if s_ok else "FAIL") if not is_open else "INFO"))
    C.append(check("hull", "凸包面积", f"{hr:.2f} × Tide ({hull / 1000:.0f}k px²)",
                   f"{OPEN_RATIO[0]:.2f}–{OPEN_RATIO[1]:.2f}" if is_open else "实心形状只看剪影",
                   ("PASS" if h_ok else "FAIL") if is_open else "INFO"))

    # accent share
    vis_acc = acc & ~occ
    share = 100.0 * vis_acc.sum() / hull if hull else 0.0
    lo, hi = ACCENT_SHARE_LINE if info["accent_line"] else ACCENT_SHARE
    raw["accent_share"] = share
    if acc.any():
        C.append(check("accent", "色块占比", f"{share:.1f} % 可见 / 凸包" + (" (线状)" if info["accent_line"] else ""),
                       f"{lo:.0f}–{hi:.0f} %", "PASS" if lo <= round(share, 1) <= hi else "FAIL"))
    else:
        C.append(check("accent", "色块占比", "没有色块", f"{lo:.0f}–{hi:.0f} %", "FAIL"))

    # separate line parts (connected lines form one part and are not checked against each other)
    ink_c = m["ink_c"]
    on_c = ink_coverage(L["on"]) if "on" in L else None
    on_ink = on_c >= 0.5 if on_c is not None else np.zeros_like(ink)
    split_ink = (L["split"][..., 3] > 127) if "split" in L else np.zeros_like(ink)
    lab, n = label(ink)
    comps = []
    for i in range(1, n + 1):
        cm = lab == i
        cnt = int(cm.sum())
        if cnt < 30:
            continue
        comps.append({"pts": edge_points(np.where(dilate(cm, 2), ink_c, 0)),
                      "split": bool((cm & split_ink).sum() > 0.5 * cnt)})
    raw["line_parts"] = len(comps)
    pairs = {"line": [], "split": []}
    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            a, b = comps[i], comps[j]
            d, idx = nearest(a["pts"], b["pts"])
            t = int(d.argmin())
            pa, pb = a["pts"][t], b["pts"][idx[t]]
            kind = "split" if a["split"] and b["split"] else "line"
            pairs[kind].append({"gap": float(d[t]), "at": [(pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2]})
    for kind, lab_, target in (("line", "线间净空", GAP_LINE), ("split", "切开净空", GAP_SPLIT)):
        if kind == "split" and not info["has_split"]:
            continue
        P_ = pairs[kind]
        if P_:
            g = min(P_, key=lambda p: p["gap"])
            raw[f"{kind}_gap"] = g["gap"]
            C.append(check(f"{kind}_gap", lab_, f"{g['gap']:.1f} px @ ({g['at'][0]:.0f}, {g['at'][1]:.0f})",
                           f"≥ {target}", "PASS" if g["gap"] >= target - GAP_TOL else "FAIL", at=g["at"]))
        else:
            note = "只有一组相连的线" if kind == "line" else "data-part=split 少于两段"
            C.append(check(f"{kind}_gap", lab_, f"— ({note})", f"≥ {target}",
                           "PASS" if kind == "line" else "FAIL"))

    # accent edge to lines: an edge under a line is fine; a free edge keeps GAP_ACCENT from every line,
    # except within JUNCTION_ARC (measured along the edge) of the point where it comes out from under a line
    acc_pts = edge_points(m["acc_c"]) if acc.any() else np.zeros((0, 2))
    if len(acc_pts):
        ink_main_c = np.where(dilate(on_ink, 2), 0, ink_c) if on_ink.any() else ink_c
        px, py = acc_pts[:, 0].astype(int).clip(0, 1023), acc_pts[:, 1].astype(int).clip(0, 1023)
        free = ~occ[py, px]
        if free.any():
            fp = acc_pts[free]
            fx, fy = px[free], py[free]
            ip = edge_points(ink_main_c)
            if len(ip):
                lo_, hi_ = fp.min(0) - 80, fp.max(0) + 80
                ip = ip[((ip >= lo_) & (ip <= hi_)).all(1)]
            d, _ = nearest(fp, ip)
            clear = np.full(acc.shape, np.inf)
            np.minimum.at(clear, (fy, fx), d)
            free_pix = np.zeros(acc.shape, bool)
            free_pix[fy, fx] = True
            covered_pix = np.zeros(acc.shape, bool)
            covered_pix[py[~free], px[~free]] = True
            # where the edge comes out from under a line
            seeds = free_pix & (dilate(covered_pix, 2) | (clear <= 2.0))
            arc = geodesic_from(seeds, free_pix) if seeds.any() else np.full(acc.shape, np.inf)
            checked = free_pix & (arc > JUNCTION_ARC)
            if checked.any() and np.isfinite(clear[checked]).any():
                cv = np.where(checked, clear, np.inf)
                yy, xx = np.unravel_index(int(cv.argmin()), cv.shape)
                g = float(cv[yy, xx])
                raw["accent_gap"] = g
                C.append(check("accent_gap", "色块到线", f"{g:.1f} px @ ({xx}, {yy})",
                               f"≥ {GAP_ACCENT} 或压中心线", "PASS" if g >= GAP_ACCENT - GAP_TOL else "FAIL",
                               at=[int(xx), int(yy)]))
            else:
                C.append(check("accent_gap", "色块到线", "自由边都从线下伸出", f"≥ {GAP_ACCENT} 或压中心线", "PASS"))
        else:
            C.append(check("accent_gap", "色块到线", "边缘全部压在线上", f"≥ {GAP_ACCENT} 或压中心线", "PASS"))

    # lines lying inside the accent (class="on-accent")
    if info["has_on_accent"]:
        outside = int((on_ink & ~dilate(acc, 1)).sum())
        if outside > 20:
            C.append(check("on_accent_gap", "色块内的线", f"越出色块 {outside} px²", f"≥ {GAP_ACCENT}", "FAIL"))
        elif on_ink.any() and len(acc_pts):
            op = edge_points(on_c)
            d, idx = nearest(op, acc_pts)
            t = int(d.argmin())
            g = float(d[t])
            pt = (op[t] + acc_pts[idx[t]]) / 2
            raw["on_accent_gap"] = g
            C.append(check("on_accent_gap", "色块内的线", f"{g:.1f} px @ ({pt[0]:.0f}, {pt[1]:.0f})",
                           f"≥ {GAP_ACCENT}", "PASS" if g >= GAP_ACCENT - GAP_TOL else "FAIL",
                           at=[float(pt[0]), float(pt[1])]))
        else:
            C.append(check("on_accent_gap", "色块内的线", "on-accent 没画出像素", f"≥ {GAP_ACCENT}", "FAIL"))
    else:
        C.append(check("on_accent_gap", "色块内的线", "— (没有 class=on-accent)", f"≥ {GAP_ACCENT}", "INFO"))

    # centroid
    ys, xs = np.nonzero(filled)
    cx, cy = float(xs.mean() + 0.5), float(ys.mean() + 0.5)
    off = math.hypot(cx - 512, cy - 512)
    raw.update(centroid=[cx, cy], centroid_offset=off)
    body = top_protrusion(filled)
    if body:
        bx, by = body["centre"]
        ok = abs(bx - BODY_CENTRE[0]) <= BODY_TOL and abs(by - BODY_CENTRE[1]) <= BODY_TOL
        raw.update(top_protrusion=body["height"], body_centre=[bx, by])
        C.append(check("centroid", "重心", f"主体中心 ({bx:.0f}, {by:.0f}) · 顶部凸起 {body['height']} px",
                       f"({BODY_CENTRE[0]}, {BODY_CENTRE[1]}) ± {BODY_TOL}", "PASS" if ok else "FAIL"))
    else:
        C.append(check("centroid", "重心", f"剪影质心 ({cx:.0f}, {cy:.0f}) 偏 {off:.1f} px",
                       f"≤ {CENTROID_MAX}", "PASS" if off <= CENTROID_MAX else "FAIL"))

    # platform circles
    ys, xs = np.nonzero(sil)
    r_max = float(np.sqrt((xs + 0.5 - 512) ** 2 + (ys + 0.5 - 512) ** 2).max())
    a_s, p_s = ANDROID_R / r_max, PWA_R / r_max
    raw.update(r_max=r_max, android_scale=a_s, pwa_scale=p_s)
    C.append(check("android", "安卓安全圆", f"r_max {r_max:.0f} {'>' if r_max > ANDROID_R else '≤'} 313 → ×{a_s:.3f}",
                   "导出自动缩放", "INFO"))
    C.append(check("pwa", "PWA 遮罩圆", f"r_max {r_max:.0f} {'>' if r_max > PWA_R else '≤'} 409.6 → ×{p_s:.3f}",
                   "导出自动缩放", "INFO"))

    # accent gradient span
    g = info["grad"]
    if acc.any() and g:
        if g["units"] != "userSpaceOnUse" or g["y1"] is None or g["y2"] is None:
            C.append(check("gradient", "色块渐变", "要用 userSpaceOnUse 绝对坐标", f"跨度 {GRAD_SPAN}，居中", "FAIL"))
        else:
            M = info["matrix"]
            Y1, Y2 = M[1, 1] * g["y1"] + M[1, 2], M[1, 1] * g["y2"] + M[1, 2]
            span = abs(Y2 - Y1)
            _, ay0, _, ay1 = bbox(acc)
            dc = (Y1 + Y2) / 2 - (ay0 + ay1) / 2
            ok = abs(span - GRAD_SPAN) <= GRAD_TOL and abs(dc) <= GRAD_TOL
            mid = (ay0 + ay1) / 2
            want = (round((mid - GRAD_SPAN / 2 - M[1, 2]) / M[1, 1]), round((mid + GRAD_SPAN / 2 - M[1, 2]) / M[1, 1]))
            raw.update(gradient_span=span, gradient_centre_offset=dc, gradient_y1_y2=list(want))
            C.append(check("gradient", "色块渐变", f"跨度 {span:.0f} px · 中心差 {dc:+.0f} px"
                           + ("" if ok else f" → 改 y1 {want[0]} y2 {want[1]}"),
                           f"{GRAD_SPAN} ± {GRAD_TOL}，居中", "PASS" if ok else "FAIL", y1_y2=list(want)))
    elif acc.any():
        C.append(check("gradient", "色块渐变", "色块没有用渐变", f"跨度 {GRAD_SPAN}，居中", "FAIL"))

    # backing (keeps the lift shadow outside the outline)
    holes = float(sil_area - sil.sum())
    raw["enclosed_area"] = holes
    b = info["backing"]
    if b is None:
        if holes > 1500:
            C.append(check("backing", "背衬", f"缺 #backing，围出的空白 {holes / 1000:.0f}k px²", "#subject 第一个子元素",
                           "FAIL"))
        else:
            C.append(check("backing", "背衬", "没有封闭主体，可以不加", "#subject 第一个子元素", "PASS"))
    else:
        ok = b["first"] and url_id(b["fill"]) is not None
        why = "" if ok else (" · 不是第一个子元素" if not b["first"] else " · fill 要 url(#bg)")
        C.append(check("backing", "背衬", "#backing" + why, "#subject 第一个子元素", "PASS" if ok else "FAIL"))

    # palette
    acc_name = next((n_ for n_, v in PALETTE.items() if tuple(info["accent_stops"][:1] + info["accent_stops"][-1:]) == v),
                    None)
    parts, ok = [], True
    if acc_name:
        parts.append(f"{acc_name} {PALETTE[acc_name][0]}→{PALETTE[acc_name][1]}")
    else:
        parts.append("色块 " + ("→".join(info["accent_stops"]) or str(info["accent_fill"])) + " 不在色板")
        ok = False
    bg = tuple(info["bg_stops"][:1] + info["bg_stops"][-1:])
    if bg == BG_LIGHT:
        parts.append("底 浅")
    else:
        parts.append("底 " + ("→".join(info["bg_stops"]) or str(info["bg_fill"])) + f" 应为 {BG_LIGHT[0]}→{BG_LIGHT[1]}")
        ok = False
    if info["ink"] == INK:
        parts.append(f"墨 {INK}")
    else:
        parts.append(f"墨 {info['ink']} 应为 {INK}")
        ok = False
    if info["knock_fills"]:
        parts.append(f"挡色 {KNOCK}")
    if info["other_fills"]:
        parts.append("线上的填充 " + ", ".join(sorted(set(info["other_fills"]))) + " 不认识")
        ok = False
    raw["accent_colour"] = acc_name
    C.append(check("palette", "颜色", " · ".join(parts), "色板", "PASS" if ok else "FAIL"))
    if info["errors"]:
        C.insert(0, check("structure", "结构", "；".join(info["errors"]), "template.svg 的图层", "FAIL"))
    return {"name": name, "checks": C, "raw": raw, "info": info, "masks": m}


# ---------------------------------------------------------------- report

def dwidth(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, w):
    return s + " " * max(0, w - dwidth(s))


def report(result, path, ref):
    rows = [(f"{c['label']} [{c['key']}]", c["value"], c["target"], c["status"]) for c in result["checks"]]
    head = ("检查 [key]", "数值", "目标", "结果")
    widths = [max(dwidth(r[i]) for r in rows + [head]) for i in range(3)]
    widths[1] = min(widths[1], 46)
    lines = []
    raw = result["raw"]
    title = f"{result['name']}  ({path})"
    lines.append("─" * 4 + " " + title + " " + "─" * max(4, 96 - dwidth(title)))
    lines.append(f"  k {raw.get('k', 0):.3g} · data-shape {raw.get('data_shape') or '—'} · "
                 f"Tide 参考: 剪影 {ref['silhouette'] / 1000:.0f}k px², 凸包 {ref['hull'] / 1000:.0f}k px²")
    lines.append("  " + "  ".join(pad(h, widths[i]) if i < 3 else h for i, h in enumerate(head)))
    for r in rows:
        lines.append("  " + "  ".join(pad(r[i], widths[i]) if i < 3 else r[i] for i in range(4)))
    counts = {s: sum(1 for c in result["checks"] if c["status"] == s) for s in ("FAIL", "PASS", "INFO")}
    fails = [c["key"] for c in result["checks"] if c["status"] == "FAIL"]
    lines.append(f"  汇总: {counts['FAIL']} FAIL · {counts['PASS']} PASS · {counts['INFO']} INFO"
                 + (f"  (FAIL: {', '.join(fails)})" if fails else ""))
    return "\n".join(lines)


# ---------------------------------------------------------------- sheet

SHEET = """<!doctype html><html><head><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ width: 1240px; font: 500 14px/1.35 -apple-system, "SF Pro Text", "Inter", "Helvetica Neue", sans-serif;
         background: #EDEDF0; color: #1d1d1f; }}
  .sheet {{ display: flex; width: 1240px; }}
  .panel {{ flex: 1; padding: 40px 44px 44px; display: flex; flex-direction: column; gap: 34px; }}
  .light {{ background: linear-gradient(160deg, #F4F3F7, #DCDDE6); }}
  .dark  {{ background: linear-gradient(160deg, #24252B, #0B0B0E); color: #f5f5f7; }}
  .hero {{ display: flex; align-items: center; gap: 36px; }}
  .strip {{ display: flex; align-items: flex-end; gap: 22px; }}
  .sep {{ width: 18px; }}
  .cap {{ font-size: 12px; opacity: .55; margin-top: 8px; text-align: center; white-space: nowrap; }}
  .sh {{ filter: drop-shadow(0 1px 1.5px rgba(0,0,0,.16)) drop-shadow(0 5px 12px rgba(0,0,0,.10)); }}
  .dark .sh {{ filter: drop-shadow(0 1px 1.5px rgba(0,0,0,.5)) drop-shadow(0 5px 12px rgba(0,0,0,.35)); }}
  .sq {{ display: block; clip-path: url(#sq); }}
  .fav {{ display: block; }}
  .tile {{ background: #2B2B2E; position: relative; }}
  .glyph {{ position: absolute; inset: 0; background: #F0C46A;
           -webkit-mask-size: 100% 100%; mask-size: 100% 100%; }}
  h1 {{ font-size: 22px; font-weight: 600; letter-spacing: -.01em; }}
  .label {{ font-size: 13px; opacity: .55; margin-top: 2px; }}
  .stat {{ font-size: 12px; opacity: .7; margin-top: 14px; line-height: 1.55; white-space: nowrap; }}
  .bad {{ color: #C2410C; opacity: 1; }}
  .dark .bad {{ color: #F59E66; }}
</style></head><body>
<svg width="0" height="0" style="position:absolute"><defs>
  <clipPath id="sq" clipPathUnits="objectBoundingBox"><path transform="scale(0.0009765625)" d="{squircle}"/></clipPath>
</defs></svg>
<div class="sheet">
  <div class="panel light">
    <div class="hero">
      <div class="sh"><img class="sq" src="{master}" width="260" height="260"></div>
      <div><h1>{name}</h1><div class="label">light · master</div>{stat}</div>
    </div>
    <div class="strip">{sizes_light}</div>
    <div class="strip">
      <div><div class="sh"><img class="sq" src="{master}" width="110" height="110"></div><div class="cap">{name}</div></div>
      <div><div class="sh"><img class="sq" src="{tide}" width="110" height="110"></div><div class="cap">tide</div></div>
      <div class="sep"></div>
      <div><img class="fav" src="{fav32}" width="16" height="16"><div class="cap">32px</div></div>
      <div><img class="fav" src="{fav16}" width="8" height="8"><div class="cap">16px</div></div>
      <div><img class="fav" src="{fav32}" width="32" height="32"><div class="cap">favicon</div></div>
    </div>
  </div>
  <div class="panel dark">
    <div class="hero">
      <div class="sh"><img class="sq" src="{dark}" width="260" height="260"></div>
      <div><h1>{name}</h1><div class="label">dark variant</div></div>
    </div>
    <div class="strip">{sizes_dark}</div>
    <div class="strip">
      <div><div class="sh"><div class="sq tile" style="width:110px;height:110px"><div class="glyph" style="{tint_mask}"></div></div></div><div class="cap">tinted</div></div>
      <div><div class="sh"><div class="sq tile" style="width:110px;height:110px"><div class="glyph" style="{tide_tint_mask}"></div></div></div><div class="cap">tide tinted</div></div>
      <div class="sep"></div>
      <div><div class="sh"><img class="sq" src="{dark}" width="110" height="110"></div><div class="cap">{name}</div></div>
      <div><div class="sh"><img class="sq" src="{tide_dark}" width="110" height="110"></div><div class="cap">tide</div></div>
    </div>
  </div>
</div>
</body></html>"""


def data_uri(svg_text):
    return "data:image/svg+xml;base64," + base64.b64encode(strip_xml_prolog(svg_text).encode()).decode()


def png_uri(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def sizes_strip(src):
    return "".join(f'<div><div class="sh"><img class="sq" src="{src}" width="{s / 2:g}" height="{s / 2:g}"></div>'
                   f'<div class="cap">{s}</div></div>' for s in (180, 120, 80, 60, 40, 29))


def mask_style(uri):
    return f"-webkit-mask-image:url('{uri}');mask-image:url('{uri}')"


def build_sheet(renderer, result, text, dark, tinted, tide_text, path):
    k = result["info"]["k"]
    small = with_rounded_background(make_small(text, k))
    fav32 = renderer.image(small, 32, transparent=True)
    fav16 = renderer.image(small, 16, transparent=True)
    raw = result["raw"]
    fails = [c["key"] for c in result["checks"] if c["status"] == "FAIL"]
    stat_lines = [f'{raw.get("silhouette_ratio", 0):.2f}× Tide silhouette · {raw.get("hull_ratio", 0):.2f}× hull',
                  f'accent {raw.get("accent_share", 0):.0f}% · long side {raw.get("long_side", 0)} px',
                  f'r_max {raw.get("r_max", 0):.0f} · android ×{raw.get("android_scale", 1):.3f}',
                  f'<span class="bad">FAIL: {", ".join(fails)}</span>' if fails else "all checks pass"]
    stat = '<div class="stat">' + "".join(f"<div>{x}</div>" for x in stat_lines) + "</div>"
    html = SHEET.format(
        squircle=squircle_path(), name=result["name"], stat=stat,
        master=data_uri(text), dark=data_uri(dark), tide=data_uri(tide_text), tide_dark=data_uri(make_dark(tide_text)),
        sizes_light=sizes_strip(data_uri(text)), sizes_dark=sizes_strip(data_uri(dark)),
        tint_mask=mask_style(data_uri(tinted)), tide_tint_mask=mask_style(data_uri(make_tinted(tide_text))),
        fav32=png_uri(fav32), fav16=png_uri(fav16))
    renderer.sheet(html, path)


# ---------------------------------------------------------------- exports

def export(renderer, text, tinted, result, out):
    out.mkdir(parents=True, exist_ok=True)
    k = result["info"]["k"]
    a_s = result["raw"].get("android_scale", 1.0)
    p_s = result["raw"].get("pwa_scale", 1.0)
    written = []

    def save(im, name):
        im.save(out / name)
        written.append(name)

    save(renderer.image(text, 1024), "ios-1024.png")
    save(renderer.image(without_background(text), 1024, transparent=True), "icon-1024-transparent.png")
    save(renderer.image(with_scale(without_background(text), a_s), 432, transparent=True), "android-foreground-432.png")
    save(renderer.image(with_scale(tinted, a_s), 432, transparent=True), "android-monochrome-432.png")
    rounded = with_rounded_background(text)
    save(renderer.image(rounded, 192, transparent=True), "pwa-192.png")
    save(renderer.image(rounded, 512, transparent=True), "pwa-512.png")
    save(renderer.image(with_scale(text, p_s), 512), "pwa-maskable-512.png")
    save(renderer.image(text, 180), "apple-touch-180.png")
    small = with_rounded_background(make_small(text, k))
    f16 = renderer.image(small, 16, transparent=True)
    f32 = renderer.image(small, 32, transparent=True)
    f48 = renderer.image(small, 48, transparent=True)
    save(f16, "favicon-16.png")
    save(f32, "favicon-32.png")
    f48.save(out / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], append_images=[f32, f16])
    written.append("favicon.ico")
    (out / "favicon.svg").write_text(small, encoding="utf-8")
    written.append("favicon.svg")
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


def render(svgs, out_dir, variants=False, export_files=False, json_out=False):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bad = 0
    renderer = Renderer()
    try:
        ref = tide_reference(renderer)
        try:
            tide_text = load_svg(TIDE_SVG)[0]
        except (OSError, ValueError):
            tide_text = None
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
            renderer.image(text, 1024).save(out_dir / f"{name}-1024.png")
            dark, tinted = make_dark(text), make_tinted(text)
            build_sheet(renderer, result, text, dark, tinted, tide_text or text, out_dir / f"{name}-sheet.png")
            written = [f"{name}-1024.png", f"{name}-sheet.png"]
            if variants:
                (out_dir / f"{name}-dark.svg").write_text(dark, encoding="utf-8")
                (out_dir / f"{name}-tinted.svg").write_text(tinted, encoding="utf-8")
                renderer.image(dark, 1024).save(out_dir / f"{name}-dark.png")
                renderer.image(tinted, 1024, transparent=True).save(out_dir / f"{name}-tinted.png")
                written += [f"{name}-dark.svg", f"{name}-dark.png", f"{name}-tinted.svg", f"{name}-tinted.png"]
            if export_files:
                ex_dir = out_dir / "export" if len(svgs) == 1 else out_dir / "export" / name
                export(renderer, text, tinted, result, ex_dir)
                written.append(str(ex_dir.relative_to(out_dir)) + "/ (12 files)")
            if json_out:
                payload = {"name": name, "file": str(svg), "tide_reference": ref, "metrics": result["raw"],
                           "checks": result["checks"]}
                (out_dir / f"{name}-metrics.json").write_text(
                    json.dumps(payload, ensure_ascii=False, indent=1, default=jsonable), encoding="utf-8")
                written.append(f"{name}-metrics.json")
            print(report(result, svg, ref))
            print(f"  写入 {out_dir}/: " + ", ".join(written) + f"  ({time.time() - t0:.1f} s)\n")
    finally:
        renderer.close()
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("svgs", nargs="+", type=Path, metavar="ICON.svg")
    ap.add_argument("-o", "--out", type=Path, default=Path("renders"), metavar="DIR")
    ap.add_argument("--variants", action="store_true", help="also write <name>-dark/-tinted .svg and .png")
    ap.add_argument("--export", action="store_true", help="also write the platform files to DIR/export/")
    ap.add_argument("--json", action="store_true", help="also write <name>-metrics.json")
    args = ap.parse_args()
    bad = render(args.svgs, args.out, args.variants, args.export, args.json)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
