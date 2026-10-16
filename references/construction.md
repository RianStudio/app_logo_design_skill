# SVG 构造与平台规格

这里只讲怎么搭、怎么导出。所有数字都在 `style.md`「参数」。

## 图层结构

`assets/template.svg` 已经搭好，四层：

```
<defs>            bg 背景渐变、accent 强调色渐变、lift 投影
#background       1. 1024 全出血矩形，填 bg
#subject          整体 transform（缩放、居中）+ lift 投影；data-shape 写形状
  #backing        2. 第一个子元素：和外轮廓同形，填 url(#bg)，让投影只落在外沿
  #accent-shape   3. 一个闭合形状，填 accent，在线条下面
  #line           4. 所有墨线：同一线宽、同一颜色，round 端点和拐角
```

## 属性和类

render.py 靠这些标记选检查项和生成变体，画的时候顺手写上：

| 写在哪 | 写法 | 作用 |
|---|---|---|
| `#subject` | `data-shape="circle"`、`square`、`tall`、`wide` 或 `open` | 选尺寸检查：实心形状比填充剪影，`open`（镂空或组合形状）比凸包 |
| `#accent-shape` | `data-accent="line"` | 线状色块（扫描光束），面积按线状色块的标准查 |
| 单条线 | `class="on-accent"` | 躺在色块里的线：查它到色块边缘的净空；深色版保持 `#1C1C1E` |
| 单条线 | `class="detail"` | 内部细节（文字线、定位块、装订环）：favicon 和小尺寸时删掉 |
| 两部分 | `data-part="split"` | 同一物件切开的两部分，两边都标：按切开的净空查 |

## 要点

- **缩放**：先按方便的尺寸画，再用 `#subject` 的 `translate(512 512) scale(k) translate(-512 -512) translate(tx ty)` 放到关键线上。线宽会跟着 k 放大，所以源坐标里写线宽 ÷ k（Tide：52 ÷ 1.08 ≈ 48）。直接按最终尺寸画时 k = 1。
- **线**：所有线放在同一个 `<g id="line">` 里，共用线宽和线色；不给单条线单独设线宽或线色，变体换色只改这一组。
- **挖空**：线需要挡住色块时（云挡住太阳），给那个闭合线形填挖空色 `#FFFFFF`，不要 `none`。深色版和着色版的挖空由 render.py 处理，见「变体」。
- **衬底**：`#backing` 画在外轮廓线的中心线上（Tide 是 r 250 的圆，Margin 是页面那个圆角矩形），填 `url(#bg)`。k ≠ 1 时它和背景的色差不到 1 级，可以忽略。
- **色块渐变**：`gradientUnits="userSpaceOnUse"`，写源坐标：y1、y2 = 色块上下范围的中心 ∓ 半个跨度 ÷ k（跨度见 style.md；Tide 是 527 ∓ 222）。
- 根节点只写 `viewBox`，不写宽高。不嵌入位图，不用 `<text>`。
- 注释里不能出现连续两个连字符，否则 SVG 解析失败，渲染出来是空白。

## 几何速查

画布中心 `(512, 512)`。从 3 点钟方向顺时针 θ 角、半径 r 的点：`(cx + r·cosθ, cy + r·sinθ)`。

| 形状 | 写法 |
|---|---|
| 圆角扇形（进度、饼图） | `python3 scripts/shapes.py sector CX CY R A0 A1 圆角` |
| 圆弧 | `M 起点 A r r 0 大弧标志 1 终点`，角度 > 180° 时大弧标志为 1 |
| 胶囊 | `<rect rx="高度/2">` |
| 云 | 一条闭合 path：左圆 → 凹角圆弧 → 顶部大圆 → 凹角圆弧 → 右圆 → 平底，见 `examples/halo.svg` |
| 凹角 | 两条边之间插一段反向圆弧（`A r r 0 0 0`），圆心在凹口里，见 `examples/ledgerly.svg` |
| 对勾、箭头 | 折线 `M … L … L …`，round join 磨圆拐角外侧，内侧的尖角允许 |

## 变体

`render.py --variants` 按下面的配方生成 `<name>-dark.svg/.png` 和 `<name>-tinted.svg/.png`，不用手画。只有生成结果不对时才手改。

| 版本 | 配方 |
|---|---|
| 深色（iOS 深色模式、深色主题 app） | 背景 `#3A3A3D → #1C1C1E`；墨线 `#F5F5F7`；挖空填充 `#3A3A3D`；lift 透明度 0.35；强调色不变；`class="on-accent"` 的线保持 `#1C1C1E` |
| 着色 / 单色（iOS tinted、Android 单色图标） | 去掉背景和 `#backing`；墨线白色 100%；色块白色 40%（`fill="#FFFFFF" fill-opacity=".4"`）；挖空形状变成遮罩，挖掉它盖住的线和色块，自身只留轮廓；去掉 lift |
| favicon 和小尺寸 | 删掉 `class="detail"` 的元素；线宽 72；去掉 lift |

## 平台导出

```bash
python3 scripts/render.py icon.svg -o renders --export
```

写出 `renders/export/`，不需要 Xcode、Android Studio 或在线生成器：

| 文件 | 用在哪 |
|---|---|
| `ios-1024.png` | iOS / iPadOS / macOS：不透明、无圆角，放进 Xcode 的 AppIcon 或 Icon Composer |
| `icon-1024-transparent.png` | 透明底的主体，给 Icon Composer 分层或别的用途 |
| `android-foreground-432.png` | Android 自适应图标的前景（108 dp，xxxhdpi）；背景层用纯色 `#F7F7F5`（bg 渐变的中间色） |
| `android-monochrome-432.png` | Android 13+ 的主题图标 |
| `pwa-192.png`、`pwa-512.png`、`pwa-maskable-512.png` | PWA manifest |
| `apple-touch-180.png` | 网页的 apple-touch-icon |
| `favicon-16.png`、`favicon-32.png`、`favicon.ico`、`favicon.svg` | 浏览器标签页，按「变体」里的 favicon 配方 |

Android 和 PWA 的缩放由 render.py 自动算并套用，母版不用改：

```
r_max         = 主体任一像素（含线宽）到 (512, 512) 的最远距离
android_scale = 313 / r_max      313 = 66 dp 安全圆在 1024 画布上的半径
pwa_scale     = 409.6 / r_max    409.6 = maskable 安全区（中心 80% 的圆）的半径
```

r_max 和两个系数都在指标报告里。

## 渲染

```bash
pip install playwright pillow numpy && playwright install chromium   # 第一次
python3 scripts/render.py ICON.svg [-o DIR] [--variants] [--export] [--json]
```

| 参数 | 输出 |
|---|---|
| （总是） | `DIR/<name>-1024.png`、`DIR/<name>-sheet.png`，终端打印指标报告 |
| `--variants` | `<name>-dark.svg/.png`、`<name>-tinted.svg/.png` |
| `--export` | `DIR/export/` 下的各平台文件，见「平台导出」 |
| `--json` | `<name>-metrics.json`，内容和终端报告相同 |

- **指标报告**：每项一行，写数值、目标和 PASS / FAIL / INFO：有效线宽、长边、和 Tide 比的剪影或凸包面积、色块占比、线与线最小净空、色块与线净空、色块上的线到色块边缘的净空、重心偏移、r_max 和 Android / PWA 系数、色块渐变跨度、`#backing` 在不在、用到的颜色是否都在色板里。有 FAIL 时退出码仍是 0，靠读报告判断。
- **对照图**：iOS 遮罩下的母版；180 / 120 / 80 / 60 / 40 / 29 px；和 Tide 同尺寸并排；深色版和着色版。
- 用 Chromium 渲染，和浏览器一致。机器上已有 Chromium 时设 `CHROMIUM_PATH` 跳过下载。
