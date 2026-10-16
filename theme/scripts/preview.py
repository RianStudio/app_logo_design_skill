#!/usr/bin/env python3
"""Render a review sheet for a generated theme: the same sample screen in light and dark, plus swatches.

    python3 scripts/preview.py out/ [--icon path/to/icon-1024.png]

Writes out/preview.png. Needs Playwright + Chromium (same setup as rian-app-icon's render.py;
set CHROMIUM_PATH to use an existing Chromium).
"""
import argparse, base64, glob, json, os

PHONE = """
<div class="phone" data-theme="{mode}">
  <div class="screen">
    <div class="status t-subhead"><b>9:41</b><span>●●● ▮</span></div>
    <header class="nav glaze">
      <div class="row between"><span class="t-callout link">编辑</span>{icon}<span class="t-callout link">＋</span></div>
      <h1 class="t-large-title">{name}</h1>
    </header>
    <main>
      <section class="card hero">
        <div class="t-footnote muted">本周</div>
        <div class="t-title-1">12 / 20</div>
        <div class="bar"><i style="width:60%"></i></div>
        <div class="t-subhead muted">再完成 8 次就达成目标</div>
      </section>
      <div class="seg"><span class="on t-subhead">今天</span><span class="t-subhead">本周</span><span class="t-subhead">本月</span></div>
      <section class="card list">
        <div class="li"><i class="dot"></i><div><div class="t-body">深度工作</div><div class="t-footnote muted">25 分钟 · 已完成</div></div><span class="chev">›</span></div>
        <div class="li"><i class="dot"></i><div><div class="t-body">阅读</div><div class="t-footnote muted">40 分钟 · 进行中</div></div><span class="chev">›</span></div>
        <div class="li"><i class="dot"></i><div><div class="t-body">复盘</div><div class="t-footnote faint">未开始</div></div><span class="chev">›</span></div>
      </section>
      <div class="chips">
        <span class="chip success t-caption">已完成</span><span class="chip warning t-caption">将到期</span>
        <span class="chip danger t-caption">已超时</span><span class="chip info t-caption">新功能</span>
      </div>
      <button class="btn primary t-headline">开始专注</button>
      <button class="btn tonal t-headline">稍后提醒</button>
    </main>
    <nav class="tabs glaze">
      <span class="tab on"><i></i><b class="t-caption">首页</b></span><span class="tab"><i></i><b class="t-caption">统计</b></span>
      <span class="tab"><i></i><b class="t-caption">发现</b></span><span class="tab"><i></i><b class="t-caption">设置</b></span>
    </nav>
  </div>
  <div class="label t-footnote">{mode}</div>
</div>"""

STYLE = """
* { box-sizing: border-box; margin: 0; }
body { width: 1080px; padding: 40px; background: #E9ECEE; font-family: var(--font); display: flex; flex-direction: column; gap: 32px; }
.phones { display: flex; gap: 48px; justify-content: center; }
.phone { color: var(--c-text); text-align: center; }
.screen { position: relative; width: 390px; height: 844px; border-radius: 54px; overflow: hidden; text-align: left;
  background: var(--c-bg); box-shadow: 0 0 0 10px #101418, 0 30px 60px rgba(0,0,0,.25); }
.label { margin-top: 26px; color: #66727C; text-transform: uppercase; letter-spacing: .12em; }
.status { display: flex; justify-content: space-between; padding: 16px 30px 0; height: 50px; }
.nav { position: relative; z-index: 2; margin: 0 12px; padding: 10px 16px 14px; border-radius: var(--r-xl); }
.nav h1 { margin-top: 6px; }
.row { display: flex; align-items: center; } .between { justify-content: space-between; }
.nav img { width: 34px; height: 34px; border-radius: 9px; }
.link { color: var(--c-primary); }
main { padding: 14px 16px 0; display: flex; flex-direction: column; gap: 12px; }
.card { background: var(--c-surface); border-radius: var(--r-lg); box-shadow: var(--elev-1); }
.hero { padding: 16px; display: flex; flex-direction: column; gap: 6px; }
.muted { color: var(--c-text-2); } .faint { color: var(--c-text-3); }
.bar { height: 8px; border-radius: 4px; background: var(--c-surface-2); overflow: hidden; margin: 4px 0; }
.bar i { display: block; height: 100%; border-radius: 4px; background: var(--c-primary); }
.seg { display: flex; padding: 3px; border-radius: var(--r-sm); background: var(--c-surface-2); }
.seg span { flex: 1; text-align: center; padding: 6px 0; border-radius: 8px; color: var(--c-text-2); }
.seg .on { background: var(--c-surface); color: var(--c-text); box-shadow: var(--elev-1); font-weight: 600; }
.list { padding: 0 0 0 16px; }
.li { display: flex; align-items: center; gap: 12px; padding: 10px 16px 10px 0; border-bottom: 1px solid var(--c-border); }
.li:last-child { border-bottom: 0; } .li > div { flex: 1; }
.dot { width: 30px; height: 30px; border-radius: 9px; background: var(--c-primary-container);
  box-shadow: inset 0 0 0 9px var(--c-primary-container), inset 0 0 0 30px var(--c-primary); }
.chev { color: var(--c-text-3); font-size: 22px; }
.chips { display: flex; gap: 8px; }
.chip { padding: 4px 10px; border-radius: var(--r-full); }
.chip.success { background: var(--c-success-container); color: var(--c-success); }
.chip.warning { background: var(--c-warning-container); color: var(--c-warning); }
.chip.danger { background: var(--c-danger-container); color: var(--c-danger); }
.chip.info { background: var(--c-info-container); color: var(--c-info); }
.btn { border: 0; height: 50px; border-radius: var(--r-md); font-family: var(--font); }
.btn.primary { background: var(--c-primary); color: var(--c-on-primary); box-shadow: var(--elev-1); }
.btn.tonal { background: var(--c-primary-container); color: var(--c-on-primary-container); }
.tabs { position: absolute; left: 16px; right: 16px; bottom: 26px; height: 64px; border-radius: var(--r-full);
  display: flex; justify-content: space-around; align-items: center; }
.tab { display: flex; flex-direction: column; align-items: center; gap: 3px; color: var(--c-text-3); }
.tab i { width: 22px; height: 22px; border-radius: 7px; border: 2px solid currentColor; }
.tab.on { color: var(--c-primary); } .tab.on i { background: currentColor; }
.swatches { display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; }
.sw { display: grid; grid-template-columns: repeat(8, 1fr); gap: 6px; padding: 16px; border-radius: 18px; background: var(--c-bg); }
.sw div { height: 54px; border-radius: 10px; display: flex; align-items: flex-end; padding: 4px 6px; font: 500 9px var(--font);
  box-shadow: inset 0 0 0 1px rgba(127,127,127,.18); }
.title { font: 600 15px var(--font); color: #3A454F; }
"""

SWATCH_KEYS = ["bg", "surface", "surface-2", "border", "text", "text-2", "text-3", "primary",
               "on-primary", "primary-container", "glaze-tint", "success", "warning", "danger", "info", "glaze"]


def label(c):
    if not c.startswith("#"):
        return "#888"
    r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
    return "#000" if 0.299 * r + 0.587 * g + 0.114 * b > 150 else "#fff"


def find_chromium():
    p = os.environ.get("CHROMIUM_PATH")
    if p:
        return p
    hits = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))
    return hits[-1] if hits else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--icon")
    a = ap.parse_args()
    t = json.load(open(os.path.join(a.out, "tokens.json"), encoding="utf-8"))
    theme_css = open(os.path.join(a.out, "theme.css"), encoding="utf-8").read()
    icon = ""
    if a.icon:
        icon = f'<img src="data:image/png;base64,{base64.b64encode(open(a.icon, "rb").read()).decode()}">'
    phones = "".join(PHONE.format(mode=m, name=t["name"], icon=icon) for m in ("light", "dark"))
    sw = ""
    for m in ("light", "dark"):
        C = t["color"][m]
        cells = "".join(f'<div style="background:{C[k]};color:{label(C[k])}">{k}</div>'
                        for k in SWATCH_KEYS)
        sw += f'<div data-theme="{m}"><div class="title">{m} · {t["source"]["ground"]} · {t["source"]["solid"]} · {t["source"]["glaze"]}</div><div class="sw">{cells}</div></div>'
    html = f"<html><head><style>{theme_css}{STYLE}</style></head><body><div class='phones'>{phones}</div><div class='swatches'>{sw}</div></body></html>"
    open(os.path.join(a.out, "preview.html"), "w", encoding="utf-8").write(html)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        kw = {"executable_path": find_chromium()} if find_chromium() else {}
        b = p.chromium.launch(**kw)
        pg = b.new_page(viewport={"width": 1080, "height": 800}, device_scale_factor=2)
        pg.set_content(html)
        pg.screenshot(path=os.path.join(a.out, "preview.png"), full_page=True)
        b.close()
    print("wrote", os.path.join(a.out, "preview.png"))


if __name__ == "__main__":
    main()
