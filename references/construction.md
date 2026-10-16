# SVG 构造与平台规格

## 图层结构

`assets/template.svg` 已经搭好，结构如下：

```
<defs>        bg 渐变、grain 颗粒、solid 渐变、inner-solid 内阴影、elevate 三层投影、
              frost 模糊、veil、rim-top / rim-bottom、inner-glass、glass-shape、glass-clip
#scene
  #background   bg 渐变 + 颗粒
  #glyph        （可选柔光）+ 实色图形：solid 渐变 + inner-solid，外面包 elevate
#glass          不在 #scene 里
  1. glass-shape 白色实心 + elevate        → 玻璃的阴影
  2. 裁切到 glass-shape 内：
     <use href="#scene"> + frost            → 透出背后的模糊颜色
     glass-shape + veil                     → 让玻璃变亮
     glass-shape + inner-glass              → 上沿下方的厚度阴影
  3. rim-top 7 px、rim-bottom 4 px 描边，裁切到内部 → 上下两道边缘光
```

要点：

- `#glyph` 和 `#glass` 用同一个 `translate` 整体居中；玻璃里的 `<use href="#scene">` 用**相反**的 translate。
- veil、rim 渐变的 y 坐标要对准玻璃形状自己的上下沿，光才会落在正确的位置。
- 实色是多个形状组合时（比如纸页加两行线），把它们放进一个 `<g filter="url(#inner-solid)">`，再整体包 `elevate`。
- 根节点只写 `viewBox`，不写宽高。不嵌入位图，不用 `<text>`。

## 分层与 Icon Composer

三层正好对应 Apple Icon Composer 的分层：`background` → 背景层，`glyph` → 中间层，`glass` 的 glass-shape → 前景层（在 Icon Composer 里可以直接打开 Liquid Glass 效果，替代 SVG 里模拟的磨砂）。

## 几何速查

画布中心 `(512, 512)`。从 3 点钟方向顺时针 θ 角、半径 r 的点：`(cx + r·cosθ, cy + r·sinθ)`。

| 形状 | 写法 |
|---|---|
| 扇形 | `M cx cy L 起点 A r r 0 大弧标志 1 终点 Z`，角度 > 180° 时大弧标志为 1 |
| 胶囊 | `<rect rx="高度/2">` |
| 云（胶囊 + 圆凸起） | 用一条 path 写：左半圆弧 → 凸起大圆弧 → 右半圆弧 → 底边（见 `examples/halo.svg`） |
| 两个形合并 | 计算交点后写成一条 path；不要用两个重叠的形状当玻璃 |

## 平台规格

| 平台 | 要什么 | 备注 |
|---|---|---|
| iOS / iPadOS / macOS | 1024 × 1024 PNG，不透明，无圆角 | Xcode 单尺寸 App Icon；或者把三层导入 Icon Composer |
| iOS 深色模式 | 背景换成深石墨，实色和玻璃保持 | 从同一份 SVG 改 `#bg` 渐变即可 |
| iOS 着色模式 | 透明背景上的白色剪影 | 实色 + 玻璃合并成一个白色剪影 |
| Android 自适应图标 | 108 dp 画布，前景在中心 66 dp 圆内 | 等价于 1024 画布中心约 626 px 的圆，600 关键线框天然满足 |
| Android 单色图标 | 主体单色剪影 | 同 iOS 着色模式 |
| Web favicon | `icon.svg` + 32 px ICO + 180 px apple-touch-icon | 16/32 px 时去掉玻璃的模糊，只保留两个色块 |
| PWA | 192 / 512 PNG + maskable 512 | 内容在中心 80% 圆内 |

PNG 批量导出和 ICO 打包用 Xcode、Android Studio 或 realfavicongenerator.net，不要手工拼。

## 渲染

```bash
pip install playwright && playwright install chromium   # 第一次
python3 scripts/render.py icon.svg -o renders
```

用 Chromium 渲染，滤镜与浏览器一致。机器上已有 Chromium 时设 `CHROMIUM_PATH` 跳过下载。注意：一些设计软件（包括部分版本的 Figma 导入）不支持 `<use href="#scene">` 加滤镜的写法，需要在那里重新做磨砂效果；交付的 PNG 不受影响。
