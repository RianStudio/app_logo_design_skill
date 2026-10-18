#!/usr/bin/env python3
"""
Concept board and blind test: several icons or rough sketches side by side, iOS-masked, at 180 px and the
80 px home-screen size, plus the mono look (shape only, no colour) and a squint tile (the 80 px tile blurred
until the gaps close, as a designer squints at a screen: a good mark reduces to one or two masses and one
accent spot; grey fog means too many lines, and an accent that vanishes is too small).

  python3 scripts/concepts.py a.svg b.svg ... [-o FILE] [--blind]

  -o FILE   output PNG (default concepts.png, or blind.png with --blind); a directory (or a path without an
            extension) gets that file name inside it
  --blind   no titles, no file names: each tile only gets a letter (A, B, C ...), and the letter-to-file key
            is printed to the terminal, never written into the image. Hand the image to a reviewer who does not
            know the product and ask what each app does.

Concept stage (SKILL.md step 2): each direction is a quick sketch SVG, 1024 viewBox, lines and one accent are
enough (it need not pass render.py). The label is the SVG's <title>, else its file name, so write the
direction in the title, for example <title>A 文件夹 + 放大镜：库和搜索</title>.

Product-fit gate (SKILL.md step 5): run with --blind on the finished icon (alone, or mixed with the other
directions) and give the image to a fresh reviewer with no context.
Needs the same setup as render.py (Python 3, Pillow, numpy, Playwright with Chromium).
"""

import argparse
import base64
import io
import re
import string
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render as R  # noqa: E402
from PIL import Image  # noqa: E402

BIG, SMALL, GAP, PAD, LABEL_H = 180, 80, 40, 48, 64
PER_ROW = 4
SCALE = 2
PAGE = "linear-gradient(#16181A,#0E0F11)"
MONO_TILE = (74, 77, 82, 255)   # mono look (white at 100 / 50 / 30 %) on a mid grey, like a tinted home screen
SQUINT = 3                      # blur sigma in px at 80 px: the 60 / 1024 line is 4.7 px there, so gaps close


def title_for(svg, root):
    for el in root.iter():
        if R.local(el) == "title" and (el.text or "").strip():
            return el.text.strip()
    return " ".join(w for w in re.split(r"[-_ ]+", svg.stem) if w)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def masked(png, size, cid, blur=0):
    """the tile under the iOS mask; blur > 0 blurs the picture inside the mask, so the mask edge stays sharp"""
    b = base64.b64encode(png).decode()
    filt = (f'<filter id="{cid}f" x="-10%" y="-10%" width="120%" height="120%">'
            f'<feGaussianBlur stdDeviation="{blur}" edgeMode="duplicate"/></filter>') if blur else ""
    img = (f'<image href="data:image/png;base64,{b}" width="{size}" height="{size}"'
           + (f' filter="url(#{cid}f)"' if blur else "") + "/>")
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}"><defs><clipPath id="{cid}">'
            f'<path d="{R.ios_path(size)}"/></clipPath>{filt}</defs><g clip-path="url(#{cid})">{img}</g></svg>')


def build_html(items):
    """items: [(label, default png, mono png)]"""
    cols = min(len(items), PER_ROW)
    cell_w = BIG + GAP + SMALL + 20 + SMALL
    cells = ""
    for i, (lab, png, mono) in enumerate(items):
        cells += (f'<div class="c"><div class="r">{masked(png, BIG, f"b{i}")}'
                  f'<div class="s">{masked(png, SMALL, f"s{i}")}{masked(mono, SMALL, f"m{i}")}</div>'
                  f'<div class="s">{masked(png, SMALL, f"q{i}", SQUINT)}<div class="k">眯眼</div></div></div>'
                  f'<div class="l">{esc(lab)}</div></div>')
    width = cols * cell_w + (cols + 1) * PAD
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0}}
body{{width:{width}px;background:{PAGE};font:500 18px -apple-system,Inter,"WenQuanYi Zen Hei",sans-serif}}
.g{{display:grid;grid-template-columns:repeat({cols},{cell_w}px);gap:{PAD}px;padding:{PAD}px}}
.c{{display:flex;flex-direction:column;gap:14px}}
.r{{display:flex;gap:{GAP}px;align-items:flex-end}}
.s{{display:flex;flex-direction:column;gap:20px;width:{SMALL}px}}
.r .s+.s{{margin-left:-20px}}
.k{{color:#6E7176;font-size:15px;line-height:{SMALL}px;height:{SMALL}px;text-align:center}}
.l{{color:#B4B6B9;line-height:24px;min-height:{LABEL_H - 14}px;width:{cell_w}px}}
svg{{display:block}}
</style></head><body><div class="g">{cells}</div></body></html>"""
    return html, width


def board(svgs, out, blind):
    renderer = R.Renderer()
    key = []
    try:
        items = []
        for i, svg in enumerate(svgs):
            text, root = R.load_svg(svg)
            letter = string.ascii_uppercase[i % 26] + ("" if i < 26 else str(i // 26))
            lab = letter if blind else f"{letter}  {title_for(svg, root)}"
            key.append((letter, svg))
            mono = renderer.image(R.make_mono(text), 1024, transparent=True)
            tile = Image.new("RGBA", mono.size, MONO_TILE)
            tile.alpha_composite(mono)
            pngs = []
            for im in (renderer.image(text, 1024), tile):
                buf = io.BytesIO()
                im.save(buf, "PNG")
                pngs.append(buf.getvalue())
            items.append((lab, *pngs))
        html, width = build_html(items)
        page = renderer.browser.new_page(viewport={"width": width, "height": 400}, device_scale_factor=SCALE)
        page.set_content(html)
        out.parent.mkdir(parents=True, exist_ok=True)
        page.locator(".g").screenshot(path=str(out))
        page.close()
    finally:
        renderer.close()
    return key


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("svgs", nargs="+", type=Path, metavar="ICON.svg")
    ap.add_argument("-o", "--out", type=Path, metavar="FILE")
    ap.add_argument("--blind", action="store_true", help="letters only, no titles (product-fit test)")
    args = ap.parse_args()
    name = "blind.png" if args.blind else "concepts.png"
    out = args.out or Path(name)
    if out.is_dir() or not out.suffix:
        out = out / name
    try:
        key = board(args.svgs, out, args.blind)
    except (OSError, ValueError, ET.ParseError) as e:
        sys.exit(f"ERROR {e}")
    print(f"写入 {out}: {len(key)} 枚，每枚 {BIG} px、{SMALL} px、{SMALL} px 单色和 {SMALL} px 眯眼")
    for letter, svg in key:
        print(f"  {letter} = {svg}")
    if args.blind:
        print("  对照表只在终端：不要把它和图片一起交给盲测的人")


if __name__ == "__main__":
    main()
