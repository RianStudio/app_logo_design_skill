#!/usr/bin/env python3
"""Build an app UI theme from the same three traditional colours as the app icon.

    python3 scripts/build.py --name Tide --ground 玄青 --solid 淡朱砂 --glaze 天青 -o out/

Writes tokens.json, theme.css, Theme.swift, Theme.kt and tailwind.preset.js to the output folder.
Colour names come from assets/palette.json (Chinese or English names both work).
Every text and accent colour is checked against WCAG contrast and nudged until it passes.
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PALETTE = json.load(open(os.path.join(HERE, "..", "assets", "palette.json"), encoding="utf-8"))


# ---------- colour maths ----------
def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexc(c):
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v))) for v in c)


def mix(a, b, t):
    """t = 0 gives a, t = 1 gives b"""
    a, b = rgb(a), rgb(b)
    return hexc(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


def lum(h):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def reach(start, toward, bg, target):
    """walk from start toward `toward` until the contrast with bg reaches target;
    if even `toward` falls short, keep going to black or white, whichever is further from bg"""
    ink = "#000000" if lum(bg) > 0.18 else "#FFFFFF"
    for a, b in ((start, toward), (toward, ink)):
        for i in range(0, 101):
            c = mix(a, b, i / 100)
            if contrast(c, bg) >= target:
                return c
    return ink


def rgba(h, a):
    r, g, b = rgb(h)
    return f"rgba({r}, {g}, {b}, {a})"


def find(kind, name):
    for k, v in PALETTE[kind].items():
        if name in (k, v["en"]):
            return k, v
    sys.exit(f"unknown {kind} colour {name!r}; choose from: " + ", ".join(PALETTE[kind]))


# ---------- derive ----------
def derive(name, ground, solid, glaze):
    gk, g = find("ground", ground)
    sk, s = find("solid", solid)
    zk, z = find("glaze", glaze)
    hi, main, shade = s["tones"]
    zt, zb, zp = z["tones"]

    # dark surfaces come from the icon's ground; a light ground (霜白) borrows 玄青 for dark mode
    dark_ground = g if lum(g["tones"][1]) < 0.2 else PALETTE["ground"]["玄青"]
    deep, mid = dark_ground["tones"][2], dark_ground["tones"][1]
    # light surfaces are 霜白, faintly tinted by the ground's hue
    tint = g["tones"][1]
    L = {
        "bg": mix("#F4F7F7", tint, 0.03),
        "surface": "#FFFFFF",
        "surface-2": mix("#EDF1F2", tint, 0.04),
        "border": mix("#D8DFE2", tint, 0.06),
        "text": "#161D24",
        "text-2": "#4A5661",
        "text-3": "#7A8791",
    }
    D = {
        "bg": mix(deep, mid, 0.08),
        "surface": mix(deep, mid, 0.42),
        "surface-2": mix(deep, mid, 0.72),
        "border": mix(mid, "#FFFFFF", 0.10),
        "text": "#E8EEF1",
        "text-2": "#A6B2BC",
        "text-3": "#76838E",
    }
    for M, ink in ((L, "#000000"), (D, "#FFFFFF")):
        M["text-2"] = reach(M["text-2"], ink, M["surface-2"], 4.5)
        M["text-3"] = reach(M["text-3"], ink, M["surface"], 3.0)

    def accent(c_light_start, c_light_dir, c_dark_start, c_dark_dir):
        lt = reach(c_light_start, c_light_dir, L["surface"], 4.5)
        dk = reach(c_dark_start, c_dark_dir, D["surface"], 4.5)
        return lt, dk

    pL, pD = accent(main, shade, main, hi)
    for M, p in ((L, pL), (D, pD)):
        M["primary"] = p
        M["on-primary"] = max(("#FFFFFF", "#0B0F13"), key=lambda c: contrast(c, p))
        M["primary-container"] = mix(p, M["surface"], 0.86 if M is L else 0.78)
        M["on-primary-container"] = reach(p, "#000000" if M is L else "#FFFFFF", M["primary-container"], 7.0)

    status = {
        "success": ("#4E7A6C", "#2F5A4C", "#8FBFAE", "#D6EEE5"),
        "warning": ("#A57F3A", "#6E531F", "#D9B46A", "#F4ECD4"),
        "danger": ("#BF4639", "#8A2A23", "#E4836E", "#F6C9BE"),
        "info": ("#3F7FB5", "#1F4A78", "#9CC3E0", "#D9E9F5"),
    }
    for k, (ls, ld, ds, dd) in status.items():
        L[k], D[k] = reach(ls, ld, L["surface"], 4.5), reach(ds, dd, D["surface"], 4.5)
        L[k + "-container"] = mix(L[k], L["surface"], 0.88)
        D[k + "-container"] = mix(D[k], D["surface"], 0.80)

    # glaze: the translucent celadon material for bars, sheets and floating controls
    L["glaze"] = rgba(mix(zt, "#FFFFFF", 0.35), 0.72)
    L["glaze-tint"] = mix(zb, L["surface"], 0.55)
    L["glaze-lip"] = "rgba(255, 255, 255, 0.95)"
    L["glaze-pool"] = rgba(zp, 0.10)
    D["glaze"] = rgba(mix(zp, D["surface-2"], 0.72), 0.66)
    D["glaze-tint"] = mix(zp, D["surface"], 0.6)
    D["glaze-lip"] = "rgba(255, 255, 255, 0.14)"
    D["glaze-pool"] = rgba("#000000", 0.18)
    L["shadow"], D["shadow"] = g["shadow"] if lum(g["tones"][1]) > 0.5 else "#1E2A33", "#000000"

    return {
        "name": name,
        "source": {"ground": gk, "solid": sk, "glaze": zk},
        "color": {"light": L, "dark": D},
        "radius": {"xs": 6, "sm": 10, "md": 14, "lg": 20, "xl": 28, "full": 999},
        "space": {"1": 4, "2": 8, "3": 12, "4": 16, "5": 20, "6": 24, "8": 32, "10": 40, "12": 48},
        "font": {
            "family": "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'PingFang SC', Roboto, 'Noto Sans SC', 'Helvetica Neue', sans-serif",
            "mono": "'SF Mono', ui-monospace, 'JetBrains Mono', Menlo, monospace",
            "scale": {
                "large-title": [34, 41, 700, 0.37], "title-1": [28, 34, 700, 0.36], "title-2": [22, 28, 600, 0.35],
                "title-3": [20, 25, 600, 0.38], "headline": [17, 22, 600, -0.41], "body": [17, 22, 400, -0.41],
                "callout": [16, 21, 400, -0.32], "subhead": [15, 20, 400, -0.24], "footnote": [13, 18, 400, -0.08],
                "caption": [12, 16, 500, 0.0],
            },
        },
        "elevation": {
            "1": [[0, 1, 2, 0.10], [0, 2, 6, 0.06]],
            "2": [[0, 2, 4, 0.10], [0, 8, 20, 0.08], [0, 1, 1, 0.06]],
            "3": [[0, 4, 8, 0.10], [0, 18, 40, 0.14], [0, 1, 2, 0.08]],
        },
        "blur": {"glaze": 26, "saturate": 1.25},
        "motion": {"fast": "160ms cubic-bezier(.2, 0, 0, 1)", "standard": "240ms cubic-bezier(.2, 0, 0, 1)",
                   "spring": "420ms cubic-bezier(.34, 1.36, .64, 1)"},
    }


# ---------- emit ----------
def shadow_css(layers, colour, k=1.0):
    return ", ".join(f"{x}px {y}px {b}px {rgba(colour, round(a * k, 3))}" for x, y, b, a in layers)


def css(t):
    out = [f"/* {t['name']} theme: generated by rian-app-theme from {t['source']['ground']} · {t['source']['solid']} · {t['source']['glaze']} */"]

    def block(sel, mode):
        C = t["color"][mode]
        lines = [f"  --c-{k}: {v};" for k, v in C.items() if k != "shadow"]
        k = 1.0 if mode == "light" else 2.6
        lines += [f"  --elev-{n}: {shadow_css(L, C['shadow'], k)};" for n, L in t["elevation"].items()]
        lines.append(f"  color-scheme: {mode};")
        return f"{sel} {{\n" + "\n".join(lines) + "\n}"

    common = [f"  --r-{k}: {v}px;" for k, v in t["radius"].items()]
    common += [f"  --s-{k}: {v}px;" for k, v in t["space"].items()]
    common += [f"  --font: {t['font']['family']};", f"  --font-mono: {t['font']['mono']};"]
    for k, (size, lh, w, tr) in t["font"]["scale"].items():
        common.append(f"  --t-{k}: {w} {size}px/{lh}px var(--font);")
        common.append(f"  --tr-{k}: {tr / size:.4f}em;")
    common += [f"  --m-{k}: {v};" for k, v in t["motion"].items()]
    out.append(":root {\n" + "\n".join(common) + "\n}")
    out.append(block(":root, [data-theme=\"light\"]", "light"))
    out.append("@media (prefers-color-scheme: dark) {\n" + block(":root:not([data-theme=\"light\"])", "dark").replace("\n", "\n  ") + "\n}")
    out.append(block("[data-theme=\"dark\"]", "dark"))
    out.append(f"""/* celadon glaze material: bars, sheets, floating controls */
.glaze {{
  background: linear-gradient(to bottom, transparent 55%, var(--c-glaze-pool)), var(--c-glaze);
  -webkit-backdrop-filter: blur({t['blur']['glaze']}px) saturate({t['blur']['saturate']});
  backdrop-filter: blur({t['blur']['glaze']}px) saturate({t['blur']['saturate']});
  box-shadow: inset 0 1px 0 var(--c-glaze-lip), var(--elev-2);
}}""")
    for k in t["font"]["scale"]:
        out.append(f".t-{k} {{ font: var(--t-{k}); letter-spacing: var(--tr-{k}); }}")
    return "\n\n".join(out) + "\n"


def swift(t):
    L, D = t["color"]["light"], t["color"]["dark"]

    def hx(h):
        return "0x" + h.lstrip("#") if h.startswith("#") else None

    def camel(k):
        p = k.split("-")
        return p[0] + "".join(x.title() for x in p[1:])

    rows = []
    for k in L:
        if k == "shadow" or not L[k].startswith("#"):
            continue
        rows.append(f"    static let {camel(k)} = Color(light: {hx(L[k])}, dark: {hx(D[k])})")
    radii = "\n".join(f"    static let {k} : CGFloat = {v}" for k, v in t["radius"].items() if k != "full")
    space = "\n".join(f"    static let s{k} : CGFloat = {v}" for k, v in t["space"].items())
    return f"""// {t['name']} theme: generated by rian-app-theme from {t['source']['ground']} · {t['source']['solid']} · {t['source']['glaze']}
import SwiftUI

extension Color {{
    init(light: UInt32, dark: UInt32) {{
        self.init(uiColor: UIColor {{ $0.userInterfaceStyle == .dark ? UIColor(hex: dark) : UIColor(hex: light) }})
    }}
}}

extension UIColor {{
    convenience init(hex: UInt32, alpha: CGFloat = 1) {{
        self.init(red: CGFloat((hex >> 16) & 0xFF) / 255, green: CGFloat((hex >> 8) & 0xFF) / 255,
                  blue: CGFloat(hex & 0xFF) / 255, alpha: alpha)
    }}
}}

enum Palette {{
{chr(10).join(rows)}
}}

enum Radius {{
{radii}
}}

enum Space {{
{space}
}}

/// Celadon glaze: system material, a faint celadon tint and a bright top lip.
struct Glaze: ViewModifier {{
    var radius: CGFloat = Radius.lg
    func body(content: Content) -> some View {{
        content
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            .background(Palette.glazeTint.opacity(0.35), in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .strokeBorder(LinearGradient(colors: [.white.opacity(0.9), .white.opacity(0)],
                                                 startPoint: .top, endPoint: .center), lineWidth: 1)
            )
            .shadow(color: .black.opacity(0.10), radius: 10, y: 8)
    }}
}}

extension View {{
    func glaze(radius: CGFloat = Radius.lg) -> some View {{ modifier(Glaze(radius: radius)) }}
}}
"""


def kotlin(t):
    L, D = t["color"]["light"], t["color"]["dark"]

    def c(h):
        return "Color(0xFF" + h.lstrip("#") + ")"

    def scheme(M, fn):
        m = {"primary": "primary", "onPrimary": "on-primary", "primaryContainer": "primary-container",
             "onPrimaryContainer": "on-primary-container", "secondary": "glaze-tint", "error": "danger",
             "errorContainer": "danger-container", "background": "bg", "onBackground": "text",
             "surface": "surface", "onSurface": "text", "surfaceVariant": "surface-2",
             "onSurfaceVariant": "text-2", "outline": "border"}
        body = ",\n".join(f"    {k} = {c(M[v])}" for k, v in m.items())
        return f"val {fn} = {'lightColorScheme' if fn.startswith('Light') else 'darkColorScheme'}(\n{body}\n)"

    type_rows = []
    names = {"large-title": "displaySmall", "title-1": "headlineMedium", "title-2": "headlineSmall",
             "title-3": "titleLarge", "headline": "titleMedium", "body": "bodyLarge", "callout": "bodyMedium",
             "subhead": "titleSmall", "footnote": "bodySmall", "caption": "labelSmall"}
    for k, (size, lh, w, tr) in t["font"]["scale"].items():
        type_rows.append(f"    {names[k]} = TextStyle(fontSize = {size}.sp, lineHeight = {lh}.sp, "
                         f"fontWeight = FontWeight.W{w}, letterSpacing = ({tr / size:.4f}).em)")
    r = t["radius"]
    return f"""// {t['name']} theme: generated by rian-app-theme from {t['source']['ground']} · {t['source']['solid']} · {t['source']['glaze']}
package theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp

{scheme(L, 'LightColors')}

{scheme(D, 'DarkColors')}

val AppShapes = Shapes(
    extraSmall = RoundedCornerShape({r['xs']}.dp), small = RoundedCornerShape({r['sm']}.dp),
    medium = RoundedCornerShape({r['md']}.dp), large = RoundedCornerShape({r['lg']}.dp),
    extraLarge = RoundedCornerShape({r['xl']}.dp)
)

val AppTypography = Typography(
{(","+chr(10)).join(type_rows)}
)

@Composable
fun AppTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) =
    MaterialTheme(colorScheme = if (dark) DarkColors else LightColors,
                  shapes = AppShapes, typography = AppTypography, content = content)
"""


def tailwind(t):
    keys = [k for k in t["color"]["light"] if k != "shadow"]
    colors = ",\n".join(f"        '{k}': 'var(--c-{k})'" for k in keys)
    radius = ",\n".join(f"        '{k}': 'var(--r-{k})'" for k in t["radius"])
    return f"""// {t['name']} theme: Tailwind preset. Load theme.css first; values read its CSS variables.
module.exports = {{
  theme: {{
    extend: {{
      colors: {{
{colors}
      }},
      borderRadius: {{
{radius}
      }},
      boxShadow: {{ e1: 'var(--elev-1)', e2: 'var(--elev-2)', e3: 'var(--elev-3)' }},
      fontFamily: {{ sans: ['var(--font)'], mono: ['var(--font-mono)'] }},
    }},
  }},
}};
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--ground", required=True)
    ap.add_argument("--solid", required=True)
    ap.add_argument("--glaze", required=True)
    ap.add_argument("-o", "--out", default="theme-out")
    a = ap.parse_args()
    t = derive(a.name, a.ground, a.solid, a.glaze)
    os.makedirs(a.out, exist_ok=True)
    files = {"tokens.json": json.dumps(t, ensure_ascii=False, indent=2), "theme.css": css(t),
             "Theme.swift": swift(t), "Theme.kt": kotlin(t), "tailwind.preset.js": tailwind(t)}
    for f, body in files.items():
        open(os.path.join(a.out, f), "w", encoding="utf-8").write(body)
    for mode in ("light", "dark"):
        C = t["color"][mode]
        checks = [("text-2", "surface-2"), ("primary", "surface"), ("on-primary", "primary"), ("danger", "surface")]
        print(mode + ": " + ", ".join(f"{a}/{b} {contrast(C[a], C[b]):.1f}" for a, b in checks))
    print("wrote", ", ".join(files), "to", a.out)


if __name__ == "__main__":
    main()
