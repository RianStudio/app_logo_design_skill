# SVG 构造与平台规格

## 骨架模板

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
  <defs><!-- 渐变、滤镜，id 用语义名：bg, metal, drop, hand --></defs>
  <g id="background"><rect width="1024" height="1024" fill="..."/></g>
  <g id="glyph"><!-- 主图形 --></g>
  <g id="accent"><!-- 可选：唯一的点缀 --></g>
</svg>
```

规则：

- 根节点不写 `width` / `height`，只写 `viewBox`。
- 背景是 1024 全出血正方形，**不画圆角**。iOS、macOS 和 Icon Composer 会自己加遮罩；`render.py` 的对照图会模拟遮罩效果。
- 不嵌入位图，不用 `<text>`（字体在别的机器上不存在）。
- 渐变用 `gradientUnits="userSpaceOnUse"` 写绝对坐标，避免图形尺寸变化时光的位置跟着漂移。
- 弧线用 `A` 命令，并在注释里写下半径和角度，方便以后改。

## 几何速查

画布中心 `(512, 512)`。圆上角度 θ（从 3 点钟方向顺时针）的点：`(512 + r·cosθ, 512 + r·sinθ)`。

| 想要 | 做法 |
|---|---|
| 未闭合圆环 | `A` 弧 + `stroke-linecap="round"`，缺口 40°–80° |
| 两个图形咬合 | 两个圆互相 `<mask>` 掉一条 24–32 px 的缝 |
| 切角 | 在 `<clipPath>` 里放一个旋转 45° 的矩形 |
| 圆润的负形缺口 | 用 `stroke-linejoin="round"` 的描边做遮罩，不要用直角矩形去切 |

## 光影配方

**投影（Obsidian：黑色；Glaze：背景色相的深色）**

```svg
<filter id="drop" x="-30%" y="-30%" width="160%" height="170%">
  <feGaussianBlur in="SourceAlpha" stdDeviation="22"/>
  <feOffset dy="18"/>
  <feFlood flood-color="#0A3A8C" flood-opacity=".28"/>
  <feComposite operator="in" in2="SourceAlpha"/>  <!-- 只留模糊后的形状 -->
  <feComposite operator="in"/>
  <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
```

**金属渐变（Obsidian）**：沿光源方向的线性渐变，`#FFFFFF → #D5D9E2 (45%) → #7B8292`。

**受光边缘高光**：把同一路径再画一遍，线宽 2–4，描边用白色向下渐隐的线性渐变，透明度 0.5。

**点缀色发光（只用于 Obsidian 的强调色）**：同形状放大 30%，`feGaussianBlur stdDeviation="28"`，透明度 0.7，放在强调色下面。

**釉面顶光（Glaze）**：`<radialGradient cx="512" cy="0" r="760">`，白色 0.28 → 0，盖在背景上。

**手绘线条（Ink）**

```svg
<filter id="hand" x="-5%" y="-5%" width="110%" height="110%">
  <feTurbulence type="fractalNoise" baseFrequency="0.018" numOctaves="2" seed="7"/>
  <feDisplacementMap in="SourceGraphic" scale="9" xChannelSelector="R" yChannelSelector="G"/>
</filter>
```

换 `seed` 可以得到不同的手抖。滤镜挂在整个线稿组上，保证所有线条抖动一致。

## 渲染检查

```bash
pip install playwright && playwright install chromium   # 第一次
python3 scripts/render.py icon.svg -o renders
```

用 Chromium 渲染，滤镜和渐变与浏览器完全一致。机器上已有 Chromium 时，可以设 `CHROMIUM_PATH` 跳过下载。

## 平台规格

| 平台 | 要什么 | 备注 |
|---|---|---|
| iOS / iPadOS / macOS | 1024 × 1024 PNG，不透明，无圆角 | Xcode 的单尺寸 App Icon 即可；iOS 26 起可用 Icon Composer 导入分层 SVG 做玻璃效果，`background` / `glyph` / `accent` 三个组直接对应三层 |
| iOS 深色 / 着色模式 | 深色版：背景透明或换成深色，主图形保持；着色版：纯白主图形在透明背景上 | 需要时从同一份 SVG 派生 |
| Android 自适应图标 | 108 dp 画布，前景内容在中心 66 dp 圆内 | 等价于 1024 画布里中心约 626 px 的圆：主图形放在 600 关键线框内就自然满足 |
| Android 单色图标（Android 13+） | 只有主图形的单色剪影 | 就是对照图里 mono 版本的剪影 |
| Web favicon | `icon.svg` + 32 px ICO + 180 px apple-touch-icon | 小尺寸只保留主图形，去掉点缀和光影 |
| PWA | 192 / 512 PNG，外加 maskable 512（内容在中心 80% 圆内） | 同 Android 安全区 |

PNG 的批量导出、ICO 打包建议用 realfavicongenerator.net 或 Xcode / Android Studio 自带的资源工具，不要手工拼。
