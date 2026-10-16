#!/usr/bin/env python3
"""
Render app icon SVGs into PNG exports and a review contact sheet.

For each input SVG this writes, next to an output directory:
  <name>-1024.png        full-bleed square master (what App Store Connect / Icon Composer wants)
  <name>-sheet.png       contact sheet: masked icon on light + dark wallpaper, real home-screen
                         sizes (180 / 120 / 80 px), a monochrome test and 32 / 16 pt favicon tests

Rendering uses headless Chromium through Playwright so SVG filters, blend modes and
gradients look exactly like they will in a browser. Install once with:
  pip install playwright && playwright install chromium
If a Chromium build already exists on the machine, set CHROMIUM_PATH to its executable.

Usage:
  python3 scripts/render.py icon.svg [more.svg ...] [-o out_dir]
"""

import argparse
import base64
import glob
import os
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("playwright is not installed: pip install playwright && playwright install chromium")

# Apple-style continuous-corner mask (superellipse, n = 4) on a 1024 canvas, used only for previews.
# The exported master stays full-bleed: iOS and Icon Composer apply their own mask.
def squircle_path(size=1024, n=4.0, steps=360):
    import math
    r = size / 2
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        x = r + r * math.copysign(abs(c) ** (2 / n), c)
        y = r + r * math.copysign(abs(s) ** (2 / n), s)
        pts.append(f"{x:.1f},{y:.1f}")
    return "M" + " L".join(pts) + " Z"


SHEET = """<!doctype html><html><head><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ width: 1240px; font: 500 15px/1.4 -apple-system, "SF Pro Text", "Inter", "Helvetica Neue", sans-serif;
         background: #EDEDF0; color: #1d1d1f; }}
  .row {{ display: flex; }}
  .panel {{ flex: 1; padding: 48px; display: flex; flex-direction: column; gap: 32px; }}
  .light {{ background: linear-gradient(160deg, #F4F3F7, #DCDDE6); }}
  .dark  {{ background: linear-gradient(160deg, #24252B, #0B0B0E); color: #f5f5f7; }}
  .hero {{ display: flex; align-items: center; gap: 40px; }}
  .sizes {{ display: flex; align-items: flex-end; gap: 28px; }}
  .cap {{ font-size: 13px; opacity: .55; margin-top: 8px; text-align: center; }}
  .icon {{ display: block; filter: drop-shadow(0 1px 1.5px rgba(0,0,0,.18)) drop-shadow(0 6px 14px rgba(0,0,0,.12)); }}
  .mono {{ filter: grayscale(1) contrast(1.15); }}
  .label {{ font-size: 13px; letter-spacing: .02em; opacity: .55; }}
  h1 {{ font-size: 22px; font-weight: 600; }}
</style></head><body>
<svg width="0" height="0" style="position:absolute"><defs>
  <clipPath id="sq" clipPathUnits="objectBoundingBox"><path transform="scale(0.0009765625)" d="{squircle}"/></clipPath>
</defs></svg>
<div class="row">
  {panels}
</div>
</body></html>"""

PANEL = """<div class="panel {theme}">
  <div class="hero">
    <img class="icon" src="{src}" width="320" height="320" style="clip-path:url(#sq)">
    <div><h1>{name}</h1><div class="label">{theme} wallpaper</div></div>
  </div>
  <div class="sizes">
    {sizes}
  </div>
  <div class="sizes">
    <div><img class="icon mono" src="{src}" width="120" height="120" style="clip-path:url(#sq)"><div class="cap">mono</div></div>
    <div><img src="{src}" width="32" height="32" style="border-radius:7px"><div class="cap">32pt</div></div>
    <div><img src="{src}" width="16" height="16" style="border-radius:3.5px"><div class="cap">16pt</div></div>
  </div>
</div>"""


def find_chromium():
    env = os.environ.get("CHROMIUM_PATH")
    if env:
        return env
    for pattern in ("/opt/pw-browsers/chromium-*/chrome-linux*/chrome",):
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    return None


def render(svgs, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    exe = find_chromium()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        page = browser.new_page(device_scale_factor=1)
        for svg in svgs:
            name = svg.stem
            data = "data:image/svg+xml;base64," + base64.b64encode(svg.read_bytes()).decode()

            # Full-bleed 1024 master.
            page.set_viewport_size({"width": 1024, "height": 1024})
            page.set_content(f'<html><body style="margin:0"><img src="{data}" width="1024" height="1024" style="display:block"></body></html>')
            page.wait_for_timeout(150)
            page.screenshot(path=str(out_dir / f"{name}-1024.png"), clip={"x": 0, "y": 0, "width": 1024, "height": 1024})

            # Contact sheet, rendered at 2x so the small sizes look like a retina home screen.
            sizes = "".join(
                f'<div><img class="icon" src="{data}" width="{s // 2}" height="{s // 2}" style="clip-path:url(#sq)"><div class="cap">{s}px</div></div>'
                for s in (180, 120, 80)
            )
            panels = "".join(PANEL.format(theme=t, src=data, name=name, sizes=sizes) for t in ("light", "dark"))
            html = SHEET.format(squircle=squircle_path(), panels=panels)
            sheet = browser.new_page(device_scale_factor=2, viewport={"width": 1240, "height": 800})
            sheet.set_content(html)
            sheet.wait_for_timeout(200)
            sheet.locator(".row").screenshot(path=str(out_dir / f"{name}-sheet.png"))
            sheet.close()
            print(f"rendered {name}: {out_dir / (name + '-1024.png')}, {out_dir / (name + '-sheet.png')}")
        browser.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("svgs", nargs="+", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("renders"))
    args = ap.parse_args()
    render(args.svgs, args.out)


if __name__ == "__main__":
    main()
