# 主题规则：清冷的东方质感

一句话：**界面是一张安静的霜白（或玄青）纸，颜色只出现在需要你按的地方。** 和图标同一套色板、同一种釉，所以图标放在界面里像是从里面长出来的。

## 原则

1. **中性为主，颜色克制。** 背景、表面、文字全是带一点冷调的中性色；主色只用在按钮、选中态、进度、链接上，一屏里主色面积不超过 10%。
2. **深浅两套，同等对待。** 深色模式不是反色：底色来自图标的深色底（玄青、黛蓝、苍绿），表面一层比一层亮，投影更深。
3. **青瓷釉是唯一的材质。** 导航栏、标签栏、浮层、底部弹窗用釉面：半透明、背景模糊 26、轻微提饱和、顶部一道 1 px 亮线。卡片和列表不用釉，用实心表面加浅投影。
4. **一个强调色。** 主色来自图标的实色；状态色（成功、警告、危险、信息）来自同一色板，降饱和，只在状态出现时用。
5. **可读性先于风格。** 所有文字和强调色都过 WCAG：正文与强调色 4.5:1，占位文字 3:1。脚本自动保证，不要手动调回去。
6. **系统字体，克制的字重。** 用 SF Pro / PingFang SC / Roboto / Noto Sans SC；只用 400、500、600、700 四档，字号沿用 Apple 的文字样式。

## Token

| 组 | 内容 |
|---|---|
| 颜色 | `bg`、`surface`、`surface-2`、`border`、`text`、`text-2`、`text-3`、`primary`、`on-primary`、`primary-container`、`on-primary-container`、`success / warning / danger / info` 及各自的 `-container`、`glaze`、`glaze-tint`、`glaze-lip`、`glaze-pool` |
| 圆角 | xs 6 · sm 10 · md 14 · lg 20 · xl 28 · full；iOS 用 continuous 圆角 |
| 间距 | 4 的倍数：4 8 12 16 20 24 32 40 48 |
| 字号 | large-title 34 · title-1 28 · title-2 22 · title-3 20 · headline 17/600 · body 17 · callout 16 · subhead 15 · footnote 13 · caption 12 |
| 投影 | elev-1 卡片、elev-2 浮层与釉面、elev-3 弹窗；多层，颜色同图标投影色，深色模式加深 |
| 动效 | fast 160 ms、standard 240 ms（缓出），spring 420 ms（轻回弹）；不用夸张的弹跳和视差 |

## 用法速查

| 组件 | 用什么 |
|---|---|
| 页面背景 | `bg` |
| 卡片、列表组 | `surface` + `elev-1`，圆角 lg |
| 输入框、分段控件底、进度条轨道 | `surface-2` |
| 分隔线 | `border`，1 px，列表里从文字左边开始 |
| 主按钮 | `primary` 底、`on-primary` 字，圆角 md，高 50 |
| 次按钮 | `primary-container` 底、`on-primary-container` 字 |
| 导航栏、标签栏、底部弹窗、浮动按钮 | 釉面（CSS `.glaze`、SwiftUI `.glaze()`） |
| 选中的标签、链接、开关 | `primary` |
| 标签 / 徽章 | 状态色的 `-container` 底、状态色字，圆角 full |

## 不要

- 大面积的主色背景（整屏红、整屏蓝）；主色只给可交互的东西
- 渐变按钮、霓虹描边、彩色投影
- 卡片也用釉（釉只给浮在内容上方的东西）
- 纹样、印章、书法字体这类「中国元素」装饰：东方感来自色名、釉和留白的节奏
- 第二个强调色

## 验收清单

- [ ] 浅色、深色两张都看过，深色不是简单反色
- [ ] 主色只出现在可交互元素上，一屏面积 ≤ 10%
- [ ] 导航栏和标签栏是釉面，顶部有细亮线
- [ ] 正文、次要文字、按钮文字都清楚（脚本输出的对比度都 ≥ 4.5）
- [ ] 图标放在导航栏里和界面颜色协调
- [ ] 状态色只在对应状态出现

## 接入

- **Web**：先引入 `theme.css`，用 `var(--c-primary)` 等变量；`<html data-theme="dark">` 强制深色，不写则跟随系统。Tailwind 项目在 `presets` 里加 `tailwind.preset.js`，即可用 `bg-surface`、`text-text-2`、`shadow-e2`、`rounded-lg`。
- **SwiftUI**：把 `Theme.swift` 加进项目，用 `Palette.primary`、`Radius.lg`、`Space.s4`，浮层加 `.glaze()`。需要 iOS 15 以上。
- **Jetpack Compose**：把 `Theme.kt` 放进 `theme` 包，用 `AppTheme { … }` 包住界面，组件自动取 `MaterialTheme.colorScheme`。
