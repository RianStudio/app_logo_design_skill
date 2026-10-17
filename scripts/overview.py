#!/usr/bin/env python3
"""
Family overview: the example icons side by side, iOS-masked, each with its name. Two bands:
the default (graphite) look on a dark page, then the light look of the same icons on a light page.

  python3 scripts/overview.py [ICON.svg ...] [-o FILE]

Without paths it uses every examples/*.svg: the README order first (Tide, Halo, Ledgerly), then any other
SVG there by file name. Seven icons fit on one row; more wrap onto further rows.

  -o FILE   output PNG (default examples/renders/overview.png); a directory (or a path without an extension)
            gets overview.png inside it

Each SVG is rendered fresh to a 1024 master with render.py's renderer (the light look with render.py's
make_light recipe), so the strip never shows a stale PNG. Use it to judge visual weight across the family:
every icon should look about as heavy as Tide, in both bands.
Needs the same setup as render.py (Python 3, Pillow, numpy, Playwright with Chromium).
"""

import argparse
import base64
import io
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render as R  # noqa: E402

EXAMPLES = R.SKILL_DIR / "examples"
RENDERS = EXAMPLES / "renders"
ORDER = ["tide", "halo", "ledgerly"]
LABELS = {"tide": "Tide", "halo": "Halo", "ledgerly": "Ledgerly"}

# 300 px tiles, 65 px gaps, rendered at 1.452x (the original strip's scale)
TILE, GAP, PAD_Y, ROW_GAP, LABEL_GAP, LABEL_H = 300, 65, 72, 72, 24, 29
PER_ROW = 7
SCALE = 1.452
BANDS = {
    "default": {"page": "linear-gradient(#16181A,#0E0F11)", "label": "#9A9B9D",
                "shadow": "drop-shadow(0 10px 18px rgba(0,0,0,.45))"},
    "light": {"page": "linear-gradient(#F6F8FA,#E6E8EC)", "label": "#646667",
              "shadow": "drop-shadow(0 10px 18px rgba(0,0,0,.14))"},
}


def discover():
    found = {p.stem: p for p in EXAMPLES.glob("*.svg")}
    names = [n for n in ORDER if n in found] + sorted(n for n in found if n not in ORDER)
    return [found[n] for n in names]


def label_for(svg, root):
    if svg.stem in LABELS:
        return LABELS[svg.stem]
    for el in root.iter():
        if R.local(el) == "title" and (el.text or "").strip():
            return el.text.strip()
    return " ".join(w.capitalize() for w in re.split(r"[-_ ]+", svg.stem) if w)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def band_html(items, look, cols):
    t = BANDS[look]
    d = R.ios_path(TILE)
    cells = ""
    for i, (png, name) in enumerate(items):
        b = base64.b64encode(png).decode()
        cid = f"m{look}{i}"
        cells += (f'<div class="c"><svg width="{TILE}" height="{TILE}" viewBox="0 0 {TILE} {TILE}" '
                  f'style="filter:{t["shadow"]}"><defs><clipPath id="{cid}"><path d="{d}"/></clipPath></defs>'
                  f'<image href="data:image/png;base64,{b}" width="{TILE}" height="{TILE}" clip-path="url(#{cid})"/>'
                  f'</svg><div class="l" style="color:{t["label"]}">{esc(name)}</div></div>')
    return (f'<section style="background:{t["page"]};grid-template-columns:repeat({cols},{TILE}px)">'
            f"{cells}</section>")


def build_html(rows):
    """rows: {look: [(png bytes, label)]}, the same icons in each look."""
    n = len(next(iter(rows.values())))
    cols = min(n, PER_ROW)
    lines = math.ceil(n / PER_ROW)
    width = cols * TILE + (cols + 1) * GAP
    band_h = round(2 * PAD_Y + lines * (TILE + LABEL_GAP + LABEL_H) + (lines - 1) * ROW_GAP)
    height = band_h * len(rows)
    bands = "".join(band_html(items, look, cols) for look, items in rows.items())
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0}}
body{{width:{width}px;height:{height}px;font:500 24px -apple-system,Inter,Helvetica,sans-serif}}
section{{height:{band_h}px;box-sizing:border-box;display:grid;column-gap:{GAP}px;row-gap:{ROW_GAP}px;
  justify-content:center;align-content:center}}
.c{{display:flex;flex-direction:column;align-items:center;gap:{LABEL_GAP}px}}
.l{{line-height:{LABEL_H}px;white-space:nowrap}}
svg{{display:block}}
</style></head><body>{bands}</body></html>"""
    return html, width, height


def overview(svgs, out):
    renderer = R.Renderer()
    try:
        rows = {"default": [], "light": []}
        for svg in svgs:
            text, root = R.load_svg(svg)
            name = label_for(svg, root)
            for look, src in (("default", text), ("light", R.make_light(text))):
                buf = io.BytesIO()
                renderer.image(src, 1024).save(buf, "PNG")
                rows[look].append((buf.getvalue(), name))
        html, width, height = build_html(rows)
        page = renderer.browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=SCALE)
        page.set_content(html)
        out.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": width, "height": height})
        page.close()
    finally:
        renderer.close()
    return [label for _, label in rows["default"]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("svgs", nargs="*", type=Path, metavar="ICON.svg")
    ap.add_argument("-o", "--out", type=Path, metavar="FILE")
    args = ap.parse_args()
    svgs = args.svgs or discover()
    if not svgs:
        sys.exit(f"no SVG given and none found in {EXAMPLES}")
    out = args.out or RENDERS / "overview.png"
    if out.is_dir() or not out.suffix:
        out = out / "overview.png"
    try:
        names = overview(svgs, out)
    except (OSError, ValueError, ET.ParseError) as e:
        sys.exit(f"ERROR {e}")
    print(f"写入 {out}: {len(names)} 枚（{'、'.join(names)}），默认外观一行、浅色外观一行")


if __name__ == "__main__":
    main()
