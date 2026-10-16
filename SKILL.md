---
name: rian-app-icon
description: Design app icons and logo marks as production SVG in Rian's house style (dark geometric gloss like Linear/Raycast, hand-drawn ink like Notion, soft native depth like Apple). Use when asked to create, redesign, or iterate on an app icon, app logo, or logo mark. 用于按 Rian 的风格生成 app 图标 / logo（SVG）。
---

# Rian App Icon

把一句产品描述变成一枚可以直接上架的 app 图标：1024×1024 全出血 SVG 母版、PNG 导出和一张评审对照图。

风格不是随机的：所有图标共用一套「风格基因」，再从三种「模式」中选一种表达。动笔前先读 `references/style-dna.md`，再读所选模式的文件。

| 模式 | 一句话 | 参考气质 | 文件 |
|---|---|---|---|
| **曜石 Obsidian** | 深色底上一块打磨过的几何金属件 | Linear、Raycast | `references/mode-obsidian.md` |
| **墨线 Ink** | 白纸上一笔有温度的黑色线稿 | Notion | `references/mode-ink.md` |
| **釉光 Glaze** | 同色系柔和渐变上的白色浮雕 | Apple 原生 app | `references/mode-glaze.md` |

SVG 构造、光影配方和平台规格在 `references/construction.md`。

## 工作流程

### 1. 读懂产品（不要跳过）

需要四样东西：**名字**、**一句话说清它做什么**、**三个形容词**、**已有品牌色**（没有也行）。

用户给的信息不全时，不要连环追问：自己补一个合理版本写出来，标明「这是我的假设」，然后继续。泛泛的输入只会得到泛泛的图标，所以「一句话」必须具体到动作或对象，例如「把待办拆成 25 分钟的专注块」，而不是「效率工具」。

### 2. 选模式

按产品气质选，不按用户随口说的颜色选：

- 开发者工具、效率工具、命令行、AI 基础设施、夜间使用多 → **Obsidian**
- 笔记、写作、阅读、知识管理、教育、需要人味和亲切感 → **Ink**
- 生活、健康、天气、相机、系统类、面向大众 → **Glaze**

可以混合，但一枚图标只能有一个主模式，另一个只借**一个**元素（比如 Glaze 的配色加上 Ink 的手绘线条）。用户指定了模式就照做。

### 3. 找隐喻，出 3 个方向

先用文字写出 3 个方向，每个一行：**隐喻 → 几何化形态 → 为什么属于这个产品**。

- 隐喻要从产品的动作里找（计时 → 未闭合的环；同步 → 两个互相咬合的半圆），不要从品类里找（AI → ✦ 闪光，笔记 → 铅笔）。
- 三个方向在形态上要真的不同，不能只是同一个形状改参数。
- 首字母方向最多占一个，而且字母必须被几何化重构，不能直接打字。

然后选最强的一个（或者用户指定的）往下做。用户要求多方案时，3 个方向都画出来。

### 4. 画 SVG

严格按 `references/construction.md`：

- `viewBox="0 0 1024 1024"`，全出血正方形背景，**不要自己画圆角**，系统会加遮罩。
- 用 `<g id="background">`、`<g id="glyph">`、`<g id="accent">` 分层，方便导入 Apple Icon Composer 做分层/玻璃效果。
- 主图形落在中心 **600 px** 的关键线框内（细长图形可以放宽到 680），所有内容留在 **824 px** 安全区内。
- 坐标取整数或 .5，几何关系（半径、角度、线宽）用整齐的数字，并在注释里写出来。

### 5. 渲染、自检、再打磨

```bash
python3 scripts/render.py path/to/icon.svg -o renders
```

产出 `*-1024.png` 和 `*-sheet.png`。**一定要打开对照图亲眼看**，逐条检查 `references/style-dna.md` 末尾的验收清单。不合格就改，通常需要 2 轮。

打磨时遵循 Anthropic canvas-design 的原则：**不要加东西，只把已有的东西做得更准**。想再加一个光点、一条线的时候，先问自己能不能通过调整比例、间距或光的方向解决。

### 6. 交付

给用户：

1. 对照图（先给图，让作品说话）
2. 三行设计说明：隐喻、模式、关键参数（主色、线宽、关键线尺寸）
3. SVG 母版和 1024 PNG 的路径
4. 下一步建议：深色/着色模式变体、Android 自适应图标、favicon（需要时按 `construction.md` 的平台规格导出）

迭代时只改用户点名的部分，不要整枚重画。

## 示例

`examples/` 里有三种模式各一枚参考图标和它们的对照图：

- `tide-obsidian.svg`：专注计时器，未闭合的金属环加一颗发光的终点
- `margin-ink.svg`：读书笔记，手绘摊开的书和一条红色书签
- `halo-glaze.svg`：天气，白色日轮和一圈断开的光晕

新图标不要模仿示例的形状，只对齐它们的完成度和克制程度。
