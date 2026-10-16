# SVG 构造与平台规格

## 图层结构

`assets/template.svg` 已经搭好，结构如下：

```
<defs>        bg 渐变、grain 颗粒、solid 渐变、inner-solid 内阴影、elevate 三层投影、
              through-glaze 模糊、glaze 釉色、pool 积釉、soft 釉光模糊、lip 细亮线、glaze-shape、glaze-clip
#scene
  #background   bg 渐变 + 颗粒
  #glyph        （可选柔光）+ 实色图形：solid 渐变 + inner-solid，外面包 elevate
#glaze          不在 #scene 里
  1. glaze-shape 白色实心 + elevate          → 釉的阴影
  2. 裁切到 glaze-shape 内：
     <use href="#scene"> + through-glaze      → 背后颜色晕出来
     glaze-shape + glaze 釉色                 → 釉身
     glaze-shape + pool                       → 下沿积釉
     白色椭圆 + soft                           → 左上一片釉光
  3. lip 4 px 描边，裁切到内部                 → 边缘一道细亮线
```

要点：

- `#glyph` 和 `#glaze` 用同一个 transform：`translate(512 512) scale(0.88) translate(-512 -512) translate(tx ty)`，其中 tx、ty 用来把主体视觉居中。釉里面的 `<use href="#scene">` 必须用它的**逆变换**：`translate(-tx -ty) translate(512 512) scale(1.13636) translate(-512 -512)`。
- glaze、lip 渐变的 y 坐标对准釉形状自己的上下沿；釉光椭圆放在釉形状左上三分之一处，宽度约为形状宽度的 70%。
- 实色是多个形状组合时（比如纸页加两行线），把它们放进一个 `<g filter="url(#inner-solid)">`，再整体包 `elevate`。
- 根节点只写 `viewBox`，不写宽高。不嵌入位图，不用 `<text>`。

## 分层与 Icon Composer

三层正好对应 Apple Icon Composer 的分层：`background` → 背景层，`glyph` → 中间层，`glaze` 的 glaze-shape → 前景层（在 Icon Composer 里可以用半透明材质加柔光近似瓷釉，或保留 SVG 渲染出的 PNG）。

## 几何速查

画布中心 `(512, 512)`。从 3 点钟方向顺时针 θ 角、半径 r 的点：`(cx + r·cosθ, cy + r·sinθ)`。

| 形状 | 写法 |
|---|---|
| 扇形 | `M cx cy L 起点 A r r 0 大弧标志 1 终点 Z`，角度 > 180° 时大弧标志为 1 |
| 胶囊 | `<rect rx="高度/2">` |
| 云（胶囊 + 圆凸起） | 用一条 path 写：左半圆弧 → 凸起大圆弧 → 右半圆弧 → 底边（见 `examples/halo.svg`） |
| 两个形合并 | 计算交点后写成一条 path；不要用两个重叠的形状当釉 |

## 平台规格

| 平台 | 要什么 | 备注 |
|---|---|---|
| iOS / iPadOS / macOS | 1024 × 1024 PNG，不透明，无圆角 | Xcode 单尺寸 App Icon；或者把三层导入 Icon Composer |
| iOS 深色模式 | 底色换成墨，实色和釉保持 | 从同一份 SVG 改 `#bg` 渐变即可 |
| iOS 着色模式 | 透明背景上的白色剪影 | 实色 + 釉合并成一个白色剪影 |
| Android 自适应图标 | 108 dp 画布，前景在中心 66 dp 圆内 | 等价于 1024 画布中心约 626 px 的圆，600 关键线框天然满足 |
| Android 单色图标 | 主体单色剪影 | 同 iOS 着色模式 |
| Web favicon | `icon.svg` + 32 px ICO + 180 px apple-touch-icon | 16/32 px 时去掉釉的模糊和釉光，只保留两个色块 |
| PWA | 192 / 512 PNG + maskable 512 | 内容在中心 80% 圆内 |

PNG 批量导出和 ICO 打包用 Xcode、Android Studio 或 realfavicongenerator.net，不要手工拼。

## 渲染

```bash
pip install playwright && playwright install chromium   # 第一次
python3 scripts/render.py icon.svg -o renders
```

用 Chromium 渲染，滤镜与浏览器一致。机器上已有 Chromium 时设 `CHROMIUM_PATH` 跳过下载。注意：一些设计软件（包括部分版本的 Figma 导入）不支持 `<use href="#scene">` 加滤镜的写法，需要在那里重新做釉面效果；交付的 PNG 不受影响。
