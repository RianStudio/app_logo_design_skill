---
name: rian-app-icon
description: Design app icons and logo marks as production SVG in Rian's house style, which is minimal line art with rounded geometry, drawing on Apple, Google and Notion (one uniform ink line drawing plus a single accent-colour shape on a soft light or dark background, sized full on the icon grid). Use when asked to create, redesign, or iterate on an app icon, app logo, or logo mark. 用于按 Rian 的极简线条风格生成 app 图标 / logo（SVG）。
---

# Rian App Icon

把一句产品描述变成一枚可以直接上架的 app 图标：1024×1024 全出血 SVG 母版、PNG 导出和一张评审对照图。

只有一种风格：**极简线条**。一笔粗细统一的墨线画出物件，一块强调色点出重点，圆头圆角；线条和留白学 Notion，几何和关键线学 Google 产品图标，柔和渐变和轻微立体学 Apple。详细规则在 `references/style.md`，SVG 配方和平台规格在 `references/construction.md`。动笔前两份都要读。

## 风格的签名

每一枚图标都由同样的三层构成：

1. **背景**：很淡的中性色上下渐变，浅色版（默认）或深色版
2. **强调色块**：一个色块，填在物件里最有意义的那一处（进度、太阳、扫描线），在线条下面
3. **墨线**：所有线一样粗（52 px），圆头、圆角拐弯，画出整个物件

主体尺寸按 Apple 和 Google 的图标网格，外轮廓长边约 680 px，饱满不空。

`examples/` 里有七枚示例（README 有对照表），其中 Streak 是一个新 Claude 只读这个 skill 画出来的。动笔前打开和你的题材最接近的一两枚 SVG，看线条怎么走、色块放在哪；只借构图思路，不要照抄图形。

## 工作流程

### 1. 读懂产品

用户用什么语言说话，说明和交付就用什么语言。

需要四样东西：**名字**、**一句话说清它做什么**、**三个形容词**（用来挑强调色和浅色 / 深色版）、**已有品牌色**（没有也行）。

信息不全时，不要连环追问：自己补一个合理版本，标明「这是我的假设」，然后继续。「一句话」要具体到动作或对象，比如「把待办拆成 25 分钟的专注块」，不能只说「效率工具」。

### 2. 定隐喻：明确优先

这个风格追求**一眼看懂**，像 Apple 和 Google 自己的 app 一样：计时就是秒表，笔记就是一页纸，天气就是太阳和云。

- 先写出 3 个方向，每个一行：**画的是什么物件 → 色块填在哪 → 为什么一眼能懂**。
- 隐喻抓产品最核心的那个结果，不必把每个功能都画进去。
- 物件要能用 3–6 笔线条画出来：圆、圆角矩形、胶囊、圆弧、直线。线条围出的细碎小格子在小尺寸会糊，要合并或删掉。
- 不用字母，不用文字，不用 ✦ 闪光这类 AI 套路符号。
- 和同类 app 最常见的图标比一比（习惯打卡最常见的是日历加勾，天气是太阳加云）。可以用常见物件，但要有一处是这个 app 自己的：物件的细节，或者色块点在哪。
- 选最明确的那个方向往下做；用户要求多方案时，3 个都画。

### 3. 定颜色

- 默认**浅色背景 + 蓝**。从 `references/style.md` 的强调色表里只选一个；题材有自然的颜色时用它（太阳用黄，计时用珊瑚，记账用绿）。
- 产品有品牌色时，选表里最接近的一个，不要自造颜色。
- 深色版只在用户要求或 app 本身是深色主题时做。

### 4. 画 SVG

从 `assets/template.svg` 复制开始，只改标了 TODO 的地方：强调色、色块形状、线条、整体 transform。

- 线宽始终是 52（放大前写 52 ÷ k）。所有线放在同一个 `<g id="line">` 里。
- 色块只有一个闭合形状，在线条下面；边缘被线压住或者完全在线围出的区域里。
- 坐标、半径、角度用整齐的数字，并在注释里写出几何关系。
- 主体用 `#subject` 的 transform 缩放到外轮廓长边约 680 px，视觉重心在画布中心。

### 5. 渲染、自检、打磨

```bash
python3 <skill 目录>/scripts/render.py path/to/icon.svg -o renders
```

打开 `*-sheet.png` 亲眼看，逐条检查 `references/style.md` 末尾的验收清单。最常见的问题和改法：

| 看到 | 改 |
|---|---|
| 小尺寸糊成一团 | 线与线之间拉开到至少 78 px；删掉最细碎的那几笔 |
| 主体显得小、四周太空 | 加大 transform 里的 scale，让外轮廓长边到 640–700 px，和 Tide 并排时视觉大小相当 |
| 线条粗细看起来不一样 | 检查是不是有线在 transform 外面，或者单独设了线宽；放大前的线宽要写 52 ÷ k |
| 色块边缘露出一条细边 | 让色块边缘正好落在线的中心线上，或者往里收半个线宽 |
| 看起来太平、太廉价 | 检查背景渐变、色块渐变和 lift 投影是否都在；颜色是否来自色板 |
| 看起来像 Notion 而不像自己的 app | 物件要具体到这个 app 的动作，色块要点在那个动作上 |
| 认不出来 | 换更具体的物件，或者把色块挪到最能说明用途的那一处 |

打磨时**不加东西，只调准已有的东西**：比例、间距、色块位置。

### 6. 交付

给用户：对照图、三行设计说明（画了什么物件、色块点在哪、用的强调色和背景）、SVG 和 1024 PNG 的路径。需要时再给深色版、着色版、Android 自适应图标、favicon，规格在 `construction.md`。

迭代时只改用户点名的部分。
