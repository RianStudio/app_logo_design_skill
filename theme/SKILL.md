---
name: rian-app-theme
description: Design an app's UI theme (colour tokens for light and dark, type scale, spacing, radii, elevation and a celadon-glaze material) in Rian's cool, minimal Chinese-aesthetic style, matched to the app's icon, and export it as CSS variables, SwiftUI, Jetpack Compose and Tailwind. Use when asked for an app theme, design tokens, colour scheme, dark mode palette or UI style for an app. 用于按 Rian 的清冷东方风格生成 app UI 主题和设计 token。
---

# Rian App Theme

把 app 图标的三种传统色变成一整套 UI 主题：浅色和深色两套颜色 token、字号、间距、圆角、投影和「青瓷釉」材质，导出成 CSS、SwiftUI、Compose 和 Tailwind，并渲染一张样例界面对照图。

风格和图标 skill（`rian-app-icon`）是同一种：**清冷的东方质感**，极简、偏科技、偏冷淡。规则在 `references/rules.md`，动笔前要读。

## 工作流程

### 1. 定三种颜色

主题从图标的三种颜色来：**底色、实色、釉色**（名字见 `assets/palette.json`）。

- 已经用 `rian-app-icon` 做过图标：直接用图标的三种颜色，README 的示例表或 SVG 注释里都写着。
- 还没有图标：按图标 skill 的选色规则挑。工具类默认「玄青 · 银白 · 天青」，内容类默认「霜白 · 黛 · 月白」。
- 用户有品牌色：从色板里选最接近的实色，不要直接用西式亮色。

信息不全时自己补一个合理版本，标明「这是我的假设」，然后继续。

### 2. 生成

```bash
python3 scripts/build.py --name Tide --ground 玄青 --solid 淡朱砂 --glaze 天青 -o themes/tide
```

脚本按规则推导所有颜色，并逐个检查 WCAG 对比度：正文和强调色对表面至少 4.5:1，占位文字至少 3:1，不达标会自动加深或提亮。输出 `tokens.json`、`theme.css`、`Theme.swift`、`Theme.kt`、`tailwind.preset.js`。

**不要手改生成的颜色。** 想调颜色，就换一组传统色重新生成；规则本身要改时改 `build.py` 的 `derive()`。

### 3. 预览、自检

```bash
python3 scripts/preview.py themes/tide --icon path/to/tide-1024.png
```

打开 `preview.png` 亲眼看，逐条检查 `references/rules.md` 末尾的验收清单。最常见的问题：

| 看到 | 改 |
|---|---|
| 整个界面太暖、太花 | 实色是淡朱砂或淡藤黄时，暖色会铺满按钮和进度条；换成银白、黛或石青做主色，暖色留给图标 |
| 深色模式的主色发灰、没精神 | 正常：深色模式的主色是实色往高光方向提亮的版本；觉得太灰就换更饱和的实色 |
| 釉面导航栏在深色模式下发绿 | 釉色换成月白（天青、粉青在深色上会偏绿） |
| 和图标对不上 | 确认三种颜色和图标一致 |

### 4. 交付

给用户：预览图、三行说明（三种颜色、主色在浅色和深色下的色值、生成了哪些文件）和输出目录。告诉他们各平台怎么接入（见 `references/rules.md` 的「接入」）。

用户用什么语言说话，说明就用什么语言。
