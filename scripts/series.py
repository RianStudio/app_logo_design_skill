#!/usr/bin/env python3
"""
Series check: new icons next to every existing one at 40 and 29 px, silhouette-similar pairs scored, and a
register of where each accent sits (references/style.md, 系列检查).

  python3 scripts/series.py NEW.svg [more.svg ...] [--with EXISTING.svg ...] [-o DIR] [--json]

Without --with the new icons are compared with every examples/*.svg not already given, as a reference only:
pairs count (do not copy an example's framework), crowding does not (the examples are not a portfolio).
Writes DIR/series-sheet.png (default DIR renders/) and prints three tables: the accent register, the pairs
by score, and accent crowding.

  --with FILE ...  the icons already in the portfolio (default: examples/*.svg as a reference)
  --json           also writes DIR/series.json

Pair score, 0–1:
  0.3 × 外形    filled silhouettes (gaps narrower than a line closed, holes filled), each scaled to the same
                box: IoU, times the ratio of the two aspect ratios
  0.3 × 布局    the small version's glyph on a 12 × 12 grid of its own box (where the lines and the accent
                sit): soft IoU
  0.4 × 强调色  the accents on the canvas at 40 px, blurred σ 3: soft IoU times hue closeness (1 − Δh / 60°)
A pair at 0.37 or more is flagged (像). Two icons of the same data-category share their mark on
purpose, so they are scored on outline and layout only, (0.3 × 外形 + 0.3 × 布局) / 0.6, and flagged at 0.50
or more: they have to differ in shape more than icons that already differ in colour. Calibrated on the solid
graphite drafts; kept for the line style, where they still separate: the line drafts' Squeeze as a plain
pinched card scored 0.40 to 0.42 against Halo (two wide rounded silhouettes) and was flagged, the final
Squeeze with the sun on its corner is under the line, and so is every other pair of the eight line redraws.

Accent register: the accent's centroid (final px) and its direction from the canvas centre (8 sectors; 中
within 80 px). Accents closer than 160 px link up, and a group of 3 or more is flagged (扎堆); two image or
two AI accents never link, since the sun and the band sit in their corner on purpose. 左上 belongs to the
image sun and 右下 to the AI band: another category's accent there is flagged as well (占了记号的角).
Findings among the existing icons alone are listed but marked and left out of the summary.

Every SVG is rendered fresh with render.py's renderer (40 and 29 px from its small version).
Needs the same setup as render.py (Python 3, Pillow, numpy, Playwright with Chromium).
"""

import argparse
import itertools
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render as R  # noqa: E402

EXAMPLES = R.SKILL_DIR / "examples"
W_OUTLINE, W_LAYOUT, W_ACCENT = 0.3, 0.3, 0.4
FLAG = 0.37                   # pair score at or above this: 像
FLAG_SAME = 0.50              # same category: (0.3 outline + 0.3 layout) / 0.6 at or above this: 像
OUTLINE_GRID = 32             # filled silhouette, scaled to its box
LAYOUT_GRID = 12              # small version's glyph, scaled to its box
LAYOUT_BLUR = 0.6
ACCENT_GRID = 40
ACCENT_BLUR = 3.0
HUE_SPAN = 60.0               # accents this far apart in hue no longer count as alike
GREY_C = 15.0                 # chroma below this: a grey accent, alike only with grey
CENTRE_R = 80                 # accent centroid this close to (512, 512): 中
CROWD_R = 160                 # accents closer than this link up
CROWD_N = 3                   # a linked group this big: 扎堆
SECTORS = ("右", "右上", "上", "左上", "左", "左下", "下", "右下")
MARK_SECTOR = {"左上": "image", "右下": "ai"}   # the image sun and the AI band own these corners
MARK_IS_ACCENT = {"image", "ai"}              # the accent is the mark itself: two of these never crowd
SIZES = (40, 29)


def label_for(svg, root):
    for el in root.iter():
        if R.local(el) == "title" and (el.text or "").strip():
            return el.text.strip()
    return " ".join(w.capitalize() for w in re.split(r"[-_ ]+", svg.stem) if w)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def boxed(mask_u8, box, size, blur=0.0):
    """A coverage map (uint8) cropped to box and scaled to size × size, 0..1."""
    x0, y0, x1, y1 = box
    im = Image.fromarray(mask_u8).crop((x0, y0, x1, y1)).resize((size, size), Image.BOX)
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(im, np.float64) / 255


def soft_iou(a, b):
    return float(np.minimum(a, b).sum() / max(np.maximum(a, b).sum(), 1e-9))


def sector(c):
    dx, dy = c[0] - 512, 512 - c[1]
    if math.hypot(dx, dy) < CENTRE_R:
        return "中"
    return SECTORS[int(((math.degrees(math.atan2(dy, dx)) % 360 + 22.5) % 360) // 45)]


def features(renderer, svg):
    """Everything the series check needs from one icon."""
    text, root = R.load_svg(svg)
    info = R.static_info(root)
    if info["fatal"]:
        raise ValueError(f"{svg}: 缺图层（{'; '.join(info['errors'])}）")
    small = R.make_small(text, info["k"])
    full = renderer.layers(text, ["body", "accent"])
    tiny = renderer.layers(small, ["body", "accent"])
    body, acc = full["body"][..., 3], full["accent"][..., 3]
    union = np.maximum(body, acc) >= 128
    box = R.bbox(union)
    x0, y0, x1, y1 = box
    ys, xs = np.nonzero(acc >= 128)
    centre = (float(xs.mean()), float(ys.mean())) if len(xs) else (512.0, 512.0)
    stops = info["accent_grad"]["stops"] if info["accent_grad"] else []
    colour = next((n for n, v in R.PALETTE.items() if tuple(stops[:1] + stops[-1:]) == v), None)
    _, C, h = R.rgb_lch(R.hex_rgb(stops[-1])) if stops else (0, 0.0, 0.0)
    acc_map = Image.fromarray(acc).resize((ACCENT_GRID, ACCENT_GRID), Image.BOX).filter(
        ImageFilter.GaussianBlur(ACCENT_BLUR))
    return {
        "file": str(svg), "name": label_for(svg, root), "category": info["category"],
        "colour": colour, "main": stops[-1] if stops else None, "hue": float(h), "chroma": float(C),
        "accent_at": [round(centre[0]), round(centre[1])], "sector": sector(centre),
        "aspect": (x1 - x0) / max(y1 - y0, 1),
        "outline": boxed((R.silhouette(union) * 255).astype(np.uint8), box, OUTLINE_GRID),
        "layout": boxed(np.maximum(tiny["body"][..., 3], tiny["accent"][..., 3]), box, LAYOUT_GRID, LAYOUT_BLUR),
        "accent": np.asarray(acc_map, np.float64) / 255,
        "master": renderer.image(text, 1024), "small": renderer.image(small, 1024),
    }


def hue_closeness(a, b):
    grey_a, grey_b = a["chroma"] < GREY_C, b["chroma"] < GREY_C
    if grey_a or grey_b:
        return 1.0 if grey_a and grey_b else 0.0
    dh = abs((a["hue"] - b["hue"] + 180) % 360 - 180)
    return max(0.0, 1 - dh / HUE_SPAN)


def same_category(a, b):
    return a["category"] is not None and a["category"] == b["category"]


def pair_score(a, b):
    outline = soft_iou(a["outline"], b["outline"]) * min(a["aspect"], b["aspect"]) / max(a["aspect"], b["aspect"])
    layout = soft_iou(a["layout"], b["layout"])
    same = same_category(a, b)
    if same:              # colour and mark are shared on purpose: outline and layout only, own threshold
        accent = None
        score = (W_OUTLINE * outline + W_LAYOUT * layout) / (W_OUTLINE + W_LAYOUT)
    else:
        accent = soft_iou(a["accent"], b["accent"]) * hue_closeness(a, b)
        score = W_OUTLINE * outline + W_LAYOUT * layout + W_ACCENT * accent
    return {"pair": [a["name"], b["name"]], "ids": [a["id"], b["id"]], "score": round(score, 3),
            "outline": round(outline, 3), "layout": round(layout, 3),
            "accent": None if accent is None else round(accent, 3), "same_category": same,
            "line": FLAG_SAME if same else FLAG, "flag": score >= (FLAG_SAME if same else FLAG)}


def crowding(icons):
    """Groups of accents closer than CROWD_R (two image or two AI accents never link), and accents in another
    category's corner. Reference icons (the examples when no --with is given) take no part."""
    icons = [ic for ic in icons if ic["role"] != "ref"]
    n = len(icons)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in itertools.combinations(range(n), 2):
        a, b = icons[i], icons[j]
        if same_category(a, b) and a["category"] in MARK_IS_ACCENT:
            continue
        if math.dist(a["accent_at"], b["accent_at"]) < CROWD_R:
            parent[find(j)] = find(i)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    out = []
    for members in groups.values():
        if len(members) >= CROWD_N:
            secs = sorted({icons[i]["sector"] for i in members}, key=lambda s: (SECTORS + ("中",)).index(s))
            out.append({"kind": "扎堆", "sector": "、".join(secs), "icons": [icons[i]["name"] for i in members],
                        "ids": [icons[i]["id"] for i in members]})
    for ic in icons:
        owner = MARK_SECTOR.get(ic["sector"])
        if owner and ic["category"] != owner:
            out.append({"kind": "占了记号的角", "sector": ic["sector"], "icons": [ic["name"]], "ids": [ic["id"]],
                        "owner": R.CATEGORIES[owner]})
    return out


# ---------------------------------------------------------------- report

def report(icons, pairs, crowds):
    pad = R.pad
    n_new = sum(ic["role"] == "new" for ic in icons)
    lines = [f"──── 系列检查：{len(icons)} 个图标（新 {n_new} 个）" + "─" * 40]
    if any(ic["role"] == "ref" for ic in icons):
        lines.append("  没给 --with：和 examples/ 比，示例只作参考（配对照算，不算扎堆）")
    lines.append("  强调色登记")
    lines.append("  " + pad("图标", 14) + pad("类别", 8) + pad("强调色", 8) + pad("重心", 14) + "方位")
    for ic in icons:
        cat = R.CATEGORIES[ic["category"]] if ic["category"] in R.CATEGORIES else "—"
        mark = " *" if ic["role"] == "new" else ""
        lines.append("  " + pad(ic["name"] + mark, 14) + pad(cat, 8) + pad(ic["colour"] or ic["main"] or "—", 8)
                     + pad(f"({ic['accent_at'][0]}, {ic['accent_at'][1]})", 14) + ic["sector"])
    lines.append(f"  配对（分数 = {W_OUTLINE} 外形 + {W_LAYOUT} 布局 + {W_ACCENT} 强调色，≥ {FLAG} 标出；"
                 f"同类别只比外形和布局，÷ {W_OUTLINE + W_LAYOUT:g}，≥ {FLAG_SAME} 标出）")
    lines.append("  " + pad("分数", 7) + pad("外形", 7) + pad("布局", 7) + pad("强调色", 8) + "配对")
    shown = [p for p in pairs if p["flag"]] or pairs[:3]
    for p in shown:
        acc = "—" if p["accent"] is None else f"{p['accent']:.2f}"
        lines.append("  " + pad(f"{p['score']:.3f}", 7) + pad(f"{p['outline']:.2f}", 7) + pad(f"{p['layout']:.2f}", 7)
                     + pad(acc, 8) + " – ".join(p["pair"])
                     + ("  同类别" if p["same_category"] else "") + ("  像" if p["flag"] else "")
                     + ("（只有已有图标）" if p["flag"] and p["old_only"] else ""))
    if len(shown) < len(pairs):
        lines.append(f"  （其余 {len(pairs) - len(shown)} 对都没到线）")
    lines.append(f"  强调色扎堆（相距 < {CROWD_R} px 的连成一组，≥ {CROWD_N} 个标出；两个图片、两个 AI 的不连；"
                 "左上留给图片、右下留给 AI）")
    for c in crowds:
        extra = f"（{c['owner']}类记号的位置）" if c["kind"] == "占了记号的角" else ""
        lines.append(f"  {c['sector']}：{'、'.join(c['icons'])}  {c['kind']}{extra}"
                     + ("（只有已有图标）" if c["old_only"] else ""))
    if not crowds:
        lines.append("  没有")
    n_flag = sum(p["flag"] and not p["old_only"] for p in pairs)
    n_crowd = sum(c["kind"] == "扎堆" and not c["old_only"] for c in crowds)
    n_corner = sum(c["kind"] == "占了记号的角" and not c["old_only"] for c in crowds)
    old = sum(p["flag"] and p["old_only"] for p in pairs) + sum(c["old_only"] for c in crowds)
    lines.append(f"  汇总: {n_flag} 对像 · {n_crowd} 处扎堆 · {n_corner} 处占了记号的角"
                 + ("" if n_flag or n_crowd or n_corner else "  全部通过")
                 + (f"（另有 {old} 处只涉及已有图标）" if old else ""))
    return "\n".join(lines)


# ---------------------------------------------------------------- sheet

SHEET = """<!doctype html><html><head><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ width: 1240px; font: 500 14px/1.35 -apple-system, "SF Pro Text", Inter, "PingFang SC", "Noto Sans CJK SC",
         "WenQuanYi Zen Hei", "Helvetica Neue", sans-serif; background: #EEF0F2; color: #1B1C1D; }}
  .sheet {{ width: 1240px; padding: 36px 44px 40px; background: linear-gradient(170deg, #F6F7F9, #E4E6EA);
           display: flex; flex-direction: column; gap: 14px; }}
  h1 {{ font-size: 22px; font-weight: 600; letter-spacing: -.01em; }}
  .label {{ font-size: 13px; color: #646667; }}
  .h {{ font-size: 12px; font-weight: 600; color: #48494B; margin-top: 14px; }}
  .band {{ border-radius: 14px; padding: 18px 22px; display: flex; flex-wrap: wrap; gap: 14px 22px; }}
  .dark {{ background: #0E0F11; color: #9A9B9D; }}
  .lite {{ background: #F7F8FA; color: #646667; }}
  .cell {{ display: flex; flex-direction: column; align-items: center; gap: 6px; width: 64px; }}
  .cap {{ font-size: 10px; opacity: .85; text-align: center; white-space: nowrap; }}
  .new {{ font-weight: 700; }}
  .pairs {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }}
  .pair {{ background: #F7F8FA; border-radius: 14px; padding: 14px; display: flex; align-items: center; gap: 12px; }}
  .pair .t {{ font-size: 12px; color: #48494B; line-height: 1.5; }}
  .bad {{ color: #B4321F; font-weight: 600; }}
  .low {{ display: grid; grid-template-columns: 340px 1fr; gap: 22px; align-items: start; }}
  table {{ border-collapse: collapse; font-size: 12px; color: #48494B; }}
  td, th {{ padding: 3px 12px 3px 0; text-align: left; white-space: nowrap; }}
  th {{ font-weight: 600; }}
  img {{ display: block; }}
</style></head><body><div class="sheet">
  <h1>系列检查 · {n} 个图标</h1>
  <div class="label">40 / 29 px 用 small 版，真实像素；新图标的名字加粗。分数 = 0.3 外形 + 0.3 布局 + 0.4 强调色，≥ {flag} 标出；同类别只比外形和布局，≥ {flag_same} 标出{ref}</div>
  {strips}
  <div class="h">配对（离线最近的 6 对；标红的是「像」）</div>
  <div class="pairs">{pairs}</div>
  <div class="h">强调色登记</div>
  <div class="low"><div>{map}</div><div>{table}{crowds}</div></div>
</div></body></html>"""


def strip(icons, size, cls):
    cells = "".join(f'<div class="cell"><img src="{R.png_uri(R.tile(ic["small"], size))}" width="{size / 2:g}" '
                    f'height="{size / 2:g}"><div class="cap{" new" if ic["role"] == "new" else ""}">{esc(ic["name"])}'
                    f"</div></div>" for ic in icons)
    return f'<div class="band {cls}">{cells}</div>'


def accent_map(icons, crowds):
    """The 1024 canvas at 300 px: sector lines, the 80 px centre and every accent's centroid."""
    s = 300 / 1024
    parts = ['<svg width="320" height="320" viewBox="-10 -10 320 320" style="background:#191C1F;border-radius:14px">']
    for k in range(8):
        a = math.radians(22.5 + 45 * k)
        parts.append(f'<line x1="{150 + CENTRE_R * s * math.cos(a):.1f}" y1="{150 - CENTRE_R * s * math.sin(a):.1f}" '
                     f'x2="{150 + 220 * math.cos(a):.1f}" y2="{150 - 220 * math.sin(a):.1f}" stroke="#34373B"/>')
    parts.append(f'<circle cx="150" cy="150" r="{CENTRE_R * s:.1f}" fill="none" stroke="#34373B"/>')
    crowded = {i for c in crowds for i in c["ids"]}
    for ic in icons:
        x, y = ic["accent_at"][0] * s, ic["accent_at"][1] * s
        fill = ic["main"] or "#8E8D89"
        ring = ' stroke="#FF6B5A" stroke-width="2"' if ic["id"] in crowded else ""
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{fill}"{ring}/>'
                     f'<text x="{x + 9:.1f}" y="{y + 4:.1f}" font-size="10" fill="#C6C8CB">{esc(ic["name"])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def build_sheet(renderer, icons, pairs, crowds, path):
    strips = ""
    for size in SIZES:
        strips += f'<div class="h">{size} px</div>' + strip(icons, size, "dark") + strip(icons, size, "lite")
    cards = ""
    for p in pairs[:6]:
        a, b = (icons[i] for i in p["ids"])
        imgs = "".join(f'<img src="{R.png_uri(R.tile(ic["small"], 40))}" width="20" height="20">'
                       f'<img src="{R.png_uri(R.tile(ic["master"], 112))}" width="56" height="56">' for ic in (a, b))
        cls = "bad" if p["flag"] else ""
        cards += (f'<div class="pair">{imgs}<div class="t"><div class="{cls}">{p["score"]:.3f} · '
                  f'{esc(" – ".join(p["pair"]))}</div><div>外形 {p["outline"]:.2f} · 布局 {p["layout"]:.2f} · '
                  + ("同类别，不比强调色" if p["same_category"] else f'强调色 {p["accent"]:.2f}')
                  + "</div></div></div>")
    rows = "".join(f"<tr><td>{esc(ic['name'])}</td><td>{R.CATEGORIES[ic['category']] if ic['category'] in R.CATEGORIES else '—'}"
                   f"</td><td>{ic['colour'] or ic['main'] or '—'}</td><td>({ic['accent_at'][0]}, {ic['accent_at'][1]})</td>"
                   f"<td>{ic['sector']}</td></tr>" for ic in icons)
    table = f"<table><tr><th>图标</th><th>类别</th><th>强调色</th><th>重心</th><th>方位</th></tr>{rows}</table>"
    crowd_html = "".join(f'<div class="{"label" if c["old_only"] else "bad"}" style="font-size:12px;margin-top:10px">'
                         f'{c["sector"]}：{esc("、".join(c["icons"]))} {c["kind"]}'
                         f'{"（只有已有图标）" if c["old_only"] else ""}</div>' for c in crowds)
    ref = "；没给 --with，示例只作参考（不算扎堆）" if any(ic["role"] == "ref" for ic in icons) else ""
    html = SHEET.format(n=len(icons), flag=FLAG, flag_same=FLAG_SAME, ref=ref, strips=strips, pairs=cards,
                        map=accent_map(icons, crowds),
                        table=table, crowds=crowd_html or '<div class="label" style="margin-top:10px">没有扎堆</div>')
    renderer.sheet(html, path)


# ---------------------------------------------------------------- main

def series(new_svgs, old_svgs, out_dir, json_out=False, reference=False):
    """reference: old_svgs are the examples, not the user's portfolio (no crowding with them)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    renderer = R.Renderer()
    try:
        icons = [features(renderer, p) for p in list(new_svgs) + list(old_svgs)]
        for i, ic in enumerate(icons):
            ic["id"] = i
            ic["role"] = "new" if i < len(new_svgs) else "ref" if reference else "old"
        names = [ic["name"] for ic in icons]
        for ic in icons:          # a redesign of an app already in the portfolio has the same name
            if names.count(ic["name"]) > 1:
                ic["name"] += "（新）" if ic["role"] == "new" else "（已有）"
        new = {ic["id"] for ic in icons if ic["role"] == "new"}
        pairs = sorted((pair_score(a, b) for a, b in itertools.combinations(icons, 2)),
                       key=lambda p: -p["score"] / p["line"])        # closest to its line first
        crowds = crowding(icons)
        for f_ in pairs + crowds:
            f_["old_only"] = not new & set(f_["ids"])
        print(report(icons, pairs, crowds))
        build_sheet(renderer, icons, pairs, crowds, out_dir / "series-sheet.png")
        written = ["series-sheet.png"]
        if json_out:
            keep = ("file", "name", "category", "colour", "accent_at", "sector", "role")
            payload = {"icons": [{k: ic[k] for k in keep} for ic in icons], "pairs": pairs, "crowding": crowds,
                       "score": {"outline": W_OUTLINE, "layout": W_LAYOUT, "accent": W_ACCENT, "flag": FLAG,
                                 "flag_same_category": FLAG_SAME}}
            (out_dir / "series.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
            written.append("series.json")
        print(f"  写入 {out_dir}/: " + ", ".join(written) + "\n")
    finally:
        renderer.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("svgs", nargs="+", type=Path, metavar="NEW.svg")
    ap.add_argument("--with", dest="existing", nargs="*", type=Path, metavar="FILE",
                    help="icons already in the portfolio (default: examples/*.svg as a reference)")
    ap.add_argument("-o", "--out", type=Path, default=Path("renders"), metavar="DIR")
    ap.add_argument("--json", action="store_true", help="also write DIR/series.json")
    args = ap.parse_args()
    given = {p.resolve() for p in args.svgs}
    existing = args.existing if args.existing is not None else sorted(EXAMPLES.glob("*.svg"))
    existing = [p for p in existing if p.resolve() not in given]
    try:
        series(args.svgs, existing, args.out, args.json, reference=args.existing is None)
    except (OSError, ValueError, ET.ParseError) as e:
        sys.exit(f"ERROR {e}")


if __name__ == "__main__":
    main()
