---
name: rian-app-icon
description: Design app icons as production SVG in Rian's house style, which is minimal line art with rounded geometry drawing on Apple, Google and Notion (one uniform ink line drawing plus a single accent-colour shape on a soft neutral background, drawn to Google-style keylines). Renders a review sheet with automatic size, spacing and accent checks, and generates dark and tinted variants plus iOS, Android, PWA and favicon exports. Use when asked to create, redesign or iterate on an app icon, launcher icon, app logo mark or favicon. Not for wordmarks or logos with letters, and not for in-app UI icons. 用于按 Rian 的极简线条风格设计应用图标、启动图标、app 图标和 favicon（SVG）；不做字标或带字母的 logo，也不做界面里的小图标。
---

# Rian App Icon

把一句产品描述变成一枚可以直接上架的 app 图标：1024 全出血 SVG 母版，浅色、深色、着色三种外观，一张评审对照图；需要时再导出各平台文件。

只有一种风格：**极简线条**。一笔粗细统一的墨线画出物件，一块强调色点出重点，圆头圆角，衬在很淡的中性色背景上。每一枚都是同样的四层：背景、衬底、强调色块、墨线。

**动笔前只读 `references/style.md`**，所有规则和数字都在那里。需要几何写法、图层属性或平台规格时，再查 `references/construction.md`。

目标是快：第一版渲染出来之前不停下来问用户。

## 示例

`examples/` 里有七枚。不用全看：挑和题材最接近的一枚，只借技巧，不要照搬整体框架。

| 示例 | 画了什么 | 可借的技巧 |
|---|---|---|
| `tide.svg` 专注计时 | 秒表，25 分钟的扇形 | 圆角扇形用 `scripts/shapes.py sector` 生成；顶部凸起时的光学居中 |
| `halo.svg` 天气 | 云挡住太阳的一角 | 云是填了挖空色的闭合线形，挡住后面的色块 |
| `margin.svg` 笔记 | 纸页左侧一条色边 | 色条三边压在页面线的中心线上；右边是自由边，两端也落在中心线上 |
| `qr-scanner.svg` 扫码 | 取景框加扫描光束 | 镂空形状（`data-shape="open"`）直接按最终尺寸画，k = 1；线状色块标 `data-accent="line"` |
| `image-compressor.svg` 图片压缩 | 相框加两侧向内的箭头 | 组合形状按凸包算大小；主体框画饱满，不比 Tide 显轻 |
| `ledgerly.svg` 记账 | 饼图抽出一块切片 | 切开的两部分标 `data-part="split"`，用切开的净空；凹角手写反向圆弧 |
| `streak.svg` 习惯打卡 | 圆形徽章上的勾 | 圆形徽章托住结果；勾在色块里，标 `class="on-accent"` |

## 工作流程

### 1. 读懂产品

用户用什么语言说话，说明和交付就用什么语言。

需要三样：**名字**、**一句话说清它做什么**、**品牌色**（可选）。「一句话」要具体到动作或对象，比如「把待办拆成 25 分钟的专注块」，不能只说「效率工具」。信息不全时不要追问：自己补一个合理版本，标明「这是我的假设」，然后继续。

### 2. 定隐喻

这个风格追求**一眼看懂**，像 Apple 和 Google 自己的 app：计时就是秒表，笔记就是一页纸，天气就是太阳和云。

1. 写 3 个方向，每个一行：**画什么物件 → 色块填在哪 → 为什么一眼能懂**。
2. 每个方向按三项各打 0–2 分：**一眼看懂**、**有自己的一处**、**能用 3–7 段线画出**。
3. 自己选总分最高的一个往下做，不等用户确认。用户要多方案时，3 个都画。

- 隐喻抓产品最核心的那个结果，不必把每个功能都画进去。
- **有自己的一处**：先找 SF Symbols 和 Material Symbols 里的同名符号。轮廓一样的，必须在轮廓或结构上改一处：物件的局部形状、组合方式、色块的形状。只挪色块的位置不算。不要沿用示例的整体框架。
- **色块本身可以就是第二个物件**：词典的书签，翻译里前面那个气泡。
- 不用字母、文字，不用 ✦ 闪光这类 AI 套路符号。标准图标就是字母的品类，用这张表：

| 品类 | 画什么 | 色块 |
|---|---|---|
| 翻译 | 两个错开叠放的对话气泡 | 前一个气泡填色，挡住后一个；后一个只画露出来的那段线 |
| 字体 | 钢笔尖 | 填满笔尖，中缝是一条 `class="on-accent"` 的线 |
| 词典 | 一本合着的书 | 从书顶垂下的书签 |
| 输入法 | 一排三个圆角键帽 | 中间按下去的那个键 |
| 字幕 | 圆角屏幕 | 屏幕底部的字幕条，条上一道 `on-accent` 短线 |

### 3. 定颜色

从 `style.md` 的强调色表里只选一个，按顺序判断，命中就停：

1. 有品牌色 → 表里最接近的一个
2. 物件在现实里有颜色（太阳、树叶、天空）→ 用它
3. 表里「适合」一列对得上 → 用它
4. 都没有 → 蓝

不要自造颜色。只画浅色版，深色版和着色版由脚本生成。

### 4. 画 SVG

复制 `assets/template.svg`，只改标了 TODO 的地方：`data-shape`、transform、`#backing`、强调色和渐变、色块形状、线条。坐标用整齐的数字，在注释里写出几何关系。需要标记的线（`on-accent`、`detail`、`split`）见 `construction.md`「属性和类」。

### 5. 渲染、自检

```bash
python3 <skill 目录>/scripts/render.py icon.svg -o renders --variants
```

终端逐条打印指标，每条标 PASS / FAIL / INFO。再打开 `*-sheet.png` 亲眼看：80 px 下认不认得出，和 Tide 并排是否一样大，深色版和着色版的含义还在不在。

**节奏**：第一次渲染后只修报告里 FAIL 的项和验收清单里没过的项，最多 2 轮。剩下的写进交付的「可再调」，不要无限打磨。打磨时不加东西，只调准已有的东西：比例、间距、色块位置。

| 看到 | 哪项指标会报 | 改 |
|---|---|---|
| 小尺寸糊成一团 | 线与线净空、切开净空 | 拉开间距；删掉最细碎的几笔，或标 `class="detail"` |
| 主体显得小、显得重，和 Tide 不一样大 | 长边、剪影比或凸包比 | 按关键线调 transform 的 scale |
| 线条粗细看起来不一样 | 有效线宽 | `stroke-width` 写成线宽 ÷ k；不给单条线设线宽；线都在 `#subject` 里 |
| 色块边缘露出一条细边 | 色块与线净空 | 色块边缘落在线的中心线上，或者往里收 |
| 色块太抢或太弱 | 色块占比 | 改色块范围，不动线 |
| 色块上的线贴着色块边 | 色块上的线净空 | 把线挪向色块中间，或放大色块 |
| 主体偏上、偏下或偏一边 | 重心偏移 | 调 transform 的 translate |
| 物件里面有一圈灰影 | 对照图 | 加 `#backing` |
| 看起来太平、太廉价 | 色板颜色 | 背景渐变、色块渐变、lift 投影都要在；颜色只从色板来 |
| Android 圆形遮罩会裁到 | r_max | 不改母版，`--export` 按系数自动缩放 |
| 和同名系统符号一模一样 | 对照图（和 SF Symbol 叠放） | 在轮廓或结构上改一处，见第 2 步 |
| 认不出来 | 对照图 80 px | 换更具体的物件，或把色块挪到最能说明用途的那一处 |
| 认得出物件，但猜错用途 | 对照图 80 px | 回第 2 步换方向 |
| 两轮后仍不满意 | 无 | 交付，并写明还差什么 |

### 6. 交付

默认交付浅色、深色、着色三种外观（`--variants` 已经生成）。给用户：

- 对照图，SVG 和三张 PNG 的路径
- 三行设计说明：画了什么物件、色块点在哪、用的强调色
- 另外两个方向，各一行
- 「可再调」：没修完的问题，没有就省略
- 一行界面主色，按 `style.md` 颜色表的「界面主色」列（蓝、绿、紫同色，其余用蓝）。要做 UI 主题时用 `rian-app-theme`：`python3 <rian-app-theme 目录>/scripts/build.py --name <名字> --accent <界面主色> -o themes/<名字>`，预览的 `--icon` 用本次的 `<name>-1024.png`

要上架文件时加 `--export`（iOS、Android、PWA、favicon），见 `construction.md`「平台导出」。迭代时只改用户点名的部分。
