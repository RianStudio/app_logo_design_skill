#!/usr/bin/env python3
"""
Family overview: the example icons side by side, iOS-masked, each with its name.

  python3 scripts/overview.py [ICON.svg ...] [-o FILE] [--dark]

Without paths it uses every examples/*.svg: the README order first (Tide, Halo, Margin, QR Code Scanner,
Image Compressor, Ledgerly, Streak), then any other SVG there by file name. Seven icons fit on one row;
more wrap onto further rows.

  -o FILE   output PNG (default examples/renders/overview.png, or overview-dark.png with --dark);
            a directory (or a path without an extension) gets overview.png / overview-dark.png inside it
  --dark    use each icon's dark variant (render.py's make_dark recipe) on a dark page

Each SVG is rendered fresh to a 1024 master with render.py's renderer, so the strip never shows a stale PNG.
Use it to judge visual weight across the family: every icon should look about as heavy as Tide.
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
ORDER = ["tide", "halo", "margin", "qr-scanner", "image-compressor", "ledgerly", "streak"]
LABELS = {"tide": "Tide", "halo": "Halo", "margin": "Margin", "qr-scanner": "QR Code Scanner",
          "image-compressor": "Image Compressor", "ledgerly": "Ledgerly", "streak": "Streak"}

# layout of the original strip: 300 px tiles, 65 px gaps, 532 px tall, rendered at 1.452x (3804 x 772 for seven)
TILE, GAP, PAD_Y, ROW_GAP, LABEL_GAP, LABEL_H = 300, 65, 89.5, 90, 24, 29
PER_ROW = 7
SCALE = 1.452
THEMES = {
    "light": {"page": "linear-gradient(#F4F4F6,#E6E6EC)", "label": "#555555",
              "shadow": "drop-shadow(0 10px 18px rgba(0,0,0,.14))"},
    "dark": {"page": "linear-gradient(#141416,#0B0B0C)", "label": "#9A9AA0",
             "shadow": "drop-shadow(0 10px 18px rgba(0,0,0,.45))"},
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


def build_html(items, theme):
    t = THEMES[theme]
    n = len(items)
    cols = min(n, PER_ROW)
    rows = math.ceil(n / PER_ROW)
    width = cols * TILE + (cols + 1) * GAP
    height = round(2 * PAD_Y + rows * (TILE + LABEL_GAP + LABEL_H) + (rows - 1) * ROW_GAP)
    d = R.squircle_path(TILE)
    cells = ""
    for i, (png, name) in enumerate(items):
        b = base64.b64encode(png).decode()
        cells += (f'<div class="c"><svg width="{TILE}" height="{TILE}" viewBox="0 0 {TILE} {TILE}">'
                  f'<defs><clipPath id="m{i}"><path d="{d}"/></clipPath></defs>'
                  f'<image href="data:image/png;base64,{b}" width="{TILE}" height="{TILE}" clip-path="url(#m{i})"/>'
                  f'</svg><div class="l">{esc(name)}</div></div>')
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0}}
body{{width:{width}px;height:{height}px;background:{t['page']};display:grid;
  grid-template-columns:repeat({cols},{TILE}px);column-gap:{GAP}px;row-gap:{ROW_GAP}px;
  justify-content:center;align-content:center;font:500 24px -apple-system,Inter,Helvetica,sans-serif;color:{t['label']}}}
.c{{display:flex;flex-direction:column;align-items:center;gap:{LABEL_GAP}px}}
.l{{line-height:{LABEL_H}px;white-space:nowrap}}
svg{{display:block;filter:{t['shadow']}}}
</style></head><body>{cells}</body></html>"""
    return html, width, height


def overview(svgs, out, dark=False):
    renderer = R.Renderer()
    try:
        items = []
        for svg in svgs:
            text, root = R.load_svg(svg)
            if dark:
                text = R.make_dark(text)
            buf = io.BytesIO()
            renderer.image(text, 1024).save(buf, "PNG")
            items.append((buf.getvalue(), label_for(svg, root)))
        html, width, height = build_html(items, "dark" if dark else "light")
        page = renderer.browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=SCALE)
        page.set_content(html)
        out.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": width, "height": height})
        page.close()
    finally:
        renderer.close()
    return [label for _, label in items]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("svgs", nargs="*", type=Path, metavar="ICON.svg")
    ap.add_argument("-o", "--out", type=Path, metavar="FILE")
    ap.add_argument("--dark", action="store_true", help="dark variants on a dark page")
    args = ap.parse_args()
    svgs = args.svgs or discover()
    if not svgs:
        sys.exit(f"no SVG given and none found in {EXAMPLES}")
    default = "overview-dark.png" if args.dark else "overview.png"
    out = args.out or RENDERS / default
    if out.is_dir() or not out.suffix:
        out = out / default
    try:
        names = overview(svgs, out, args.dark)
    except (OSError, ValueError, ET.ParseError) as e:
        sys.exit(f"ERROR {e}")
    print(f"写入 {out}: {len(names)} 枚（{'、'.join(names)}）")


if __name__ == "__main__":
    main()
