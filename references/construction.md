# SVG 构造与平台规格

## 图层结构

`assets/template.svg` 已经搭好：

```
<defs>       bg 背景渐变、accent 强调色渐变、lift 投影
#background  1024 全出血矩形，填 bg
#subject     整体 transform（缩放、居中）+ lift 投影
  #accent-shape  一个闭合形状，填 accent，在线条下面；可以是 <path>、<circle> 或 <rect>
  #line          所有墨线：同一线宽 52，round 端点和拐角
```

要点：

- 先在 1024 画布上按方便的尺寸画，再用 `#subject` 的 transform `translate(512 512) scale(k) translate(-512 -512) translate(tx ty)` 放大到规定尺寸（外轮廓长边约 680 px）。线宽会跟着 k 一起放大：**画的时候用 52 ÷ k 作为线宽**，放大后才是 52。直接按最终尺寸画时 k = 1。
- 色块的边缘要么被线条压住（色块边缘落在线的中心线上），要么完全在线条围出的区域里，和线的描边外沿之间净空至少 40 px。不要让色块露出一条细边。
- 线需要挡住色块时（比如云挡住太阳），给那个闭合线形填背景色（浅色版 `#FFFFFF`，深色版 `#2A2A2C`），而不是 `none`。
- 多段线条放在同一个 `<g id="line">` 里，共用线宽和颜色；不要给单条线单独设线宽。
- lift 投影作用在整个主体上，色块在页面空白处投下的淡影是预期效果，不算内阴影。
- 渐变用 `gradientUnits="userSpaceOnUse"` 写绝对坐标，accent 的 y1、y2 对准色块的上下沿。
- 根节点只写 `viewBox`，不写宽高。不嵌入位图，不用 `<text>`。

## 几何速查

画布中心 `(512, 512)`。从 3 点钟方向顺时针 θ 角、半径 r 的点：`(cx + r·cosθ, cy + r·sinθ)`。

| 形状 | 写法 |
|---|---|
| 圆角扇形（进度、饼图） | `python3 scripts/shapes.py sector CX CY R A0 A1 圆角` |
| 圆弧 | `M 起点 A r r 0 大弧标志 1 终点`，角度 > 180° 时大弧标志为 1 |
| 胶囊 | `<rect rx="高度/2">` |
| 云 | 一条闭合 path：左圆 → 凹角圆角 → 顶部大圆 → 凹角圆角 → 右圆 → 平底，见 `examples/halo.svg` |
| 对勾、箭头 | 折线 `M … L … L …`，靠 round join 磨圆拐角 |

## 深色版和着色版

| 版本 | 怎么做 |
|---|---|
| 深色版（iOS 深色模式、深色主题 app） | bg 换成 `#3A3A3D → #1C1C1E`，墨线换成 `#F5F5F7`，挡色块的填充换成 `#2A2A2C`，lift 透明度 0.35；强调色不变 |
| 着色版 / 单色版（iOS tinted、Android 单色图标） | 去掉背景和色块，只留墨线，改成白色 |

## 平台规格

| 平台 | 要什么 | 备注 |
|---|---|---|
| iOS / iPadOS / macOS | 1024 × 1024 PNG，不透明，无圆角 | Xcode 单尺寸 App Icon；或把背景、色块、墨线三层导入 Icon Composer |
| Android 自适应图标 | 108 dp 画布，前景在中心 66 dp 圆内 | 等价于 1024 画布中心约 626 px 的圆：导出 Android 版时把 k 再乘 0.85 左右 |
| Web favicon | `icon.svg` + 32 px ICO + 180 px apple-touch-icon | 16 / 32 px 时线宽加粗到画布的 7% 左右，去掉投影 |
| PWA | 192 / 512 PNG + maskable 512 | 内容在中心 80% 圆内 |

PNG 批量导出和 ICO 打包用 Xcode、Android Studio 或 realfavicongenerator.net，不要手工拼。

## 渲染

```bash
pip install playwright && playwright install chromium   # 第一次
python3 scripts/render.py icon.svg -o renders
```

用 Chromium 渲染，和浏览器一致。机器上已有 Chromium 时设 `CHROMIUM_PATH` 跳过下载。
