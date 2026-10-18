---
name: rian-app-icon
description: Design app icons as production SVG in Rian's house style, the graphite line style with Apple and Google platform specs - a light round-cap line drawing (60 px at 1024, the same line as the UI's Lucide icons) on a graphite gradient, with one filled accent shape. No fills in the body and no letters; every gap at least one line width, so the mark survives monochrome and small sizes, and tools, image, video and AI apps each carry a fixed category mark. Renders a review sheet with automatic stroke, gap, size, contrast, accent and category checks, runs a series check against existing icons, and generates light, dark and mono appearances, Icon Composer layers, Android adaptive and themed icons, Play, PWA and favicon exports, and App Store A/B variants. Use when asked to create, redesign or iterate on an app icon, launcher icon, app logo mark or favicon. Not for wordmarks or logos with letters, and not for in-app UI icons. 用于按 Rian 的石墨线稿风格（深石墨底、60 px 圆头亮线、一块填色强调色，和界面的 Lucide 细线图标同一种线）设计应用图标、启动图标和 favicon（SVG）；不做字标或带字母的 logo，也不做界面里的小图标。
---

# Rian App Icon

把一句产品描述变成一枚可以直接上架的 app 图标：1024 全出血 SVG 母版，默认（石墨）、浅色、深色、单色四种外观，Icon Composer 分层，一张评审对照图；需要时再导出 Android、Play、PWA、favicon 文件和商店 A/B 变体。

只有一种风格：**石墨线稿**。深石墨底上一笔亮色圆头细线画出物件，强调色是一块填色，只点一处。线 1024 下 60 px（Lucide 24 格上 2 个单位的线，按主体约 640 px 放大；界面里 20 px 图标的 1.5 px 线同比例约 56），只有一种线宽，圆头圆角，不填色；分开的线之间、线和强调色之间都至少隔一个线宽。每一枚都是同样的四层：石墨底、可选的辉光、线稿、强调色。工具、图片、视频、AI 四类 app 各有一个固定的类别记号。不画实心的主体：界面图标是细线，图标也是。

**动笔前读 `references/style.md`**：风格规则、线宽的来由、全部阈值和验收清单都在那里。**画 SVG 时再查 `references/construction.md`** 的「几何速查」（`shapes.py` 各命令、常用写法）和「属性和类」；平台规格也在它的「平台导出」。

目标是快：第一版渲染出来之前不停下来问用户。

## 示例

`examples/` 里有三枚，渲染图在 `examples/renders/`（三枚并排是 `overview.png`）。挑和题材最接近的一枚，只借技巧，不要照搬整体框架。

| 示例 | 画了什么 | 可借的技巧 |
|---|---|---|
| `tide.svg` 专注计时 · 珊瑚 | 秒表：表圈、柄和冠钮是一笔线，珊瑚扇形是 25 分钟的进度 | 尺寸基准（外框 560 × 694）；柄的端点落在表圈中线上，连成一段；扇形 R 158 离表圈内沿 62（`shapes.py sector`） |
| `halo.svg` 天气 · 黄 | 云是一笔闭合的线，右上方的太阳是一块月牙形的填色 | 太阳 = 圆减去两个外扩 90 的云团（`shapes.py minus`），全程离云 60；`data-shape="open"` 按凸包比大小 |
| `ledgerly.svg` 记账 · 绿（财务） | 饼图一笔画（288° 弧加两条半径），缺的 72° 切片抽出来填绿 | 切片沿平分线外移 165，直边离半径线 97 − 30 = 67；用 72° 不用 90°，和 `chart.pie` 拉开 |

`examples/` 以外，品牌评审的 8 枚（Scan、Convert、Squeeze、Cutout、Trim、Loop、Ask、Upscale）是四类记号的线稿写法，见 `construction.md`「常用写法」。

## 工作流程

### 1. 读懂产品

用户用什么语言说话，说明和交付就用什么语言。

需要三样：**名字**、**一句话说清它做什么**、**品牌色**（可选）。「一句话」要具体到动作或对象，比如「把待办拆成 25 分钟的专注块」，不能只说「效率工具」。信息不全时不要追问：自己补一个合理版本，标明「这是我的假设」，然后继续。

### 2. 定隐喻

这个风格追求**一眼看懂**，像 Apple 和 Google 自己的 app：计时就是秒表，天气就是太阳和云，记账就是饼图。

先定类别：工具、图片、视频、AI，健康、财务，或者都不是（按主要功能归，顺序见 `style.md`「类别记号」：先看是不是靠模型，再看处理的是图片、视频还是文件；计时、笔记、翻译这类不归类）。类别定了强调色和类别记号，隐喻要放得下这个记号：工具是一条横贯整幅的水平直线，图片是左上角的圆太阳，视频是一个线画的播放三角，AI 是外轮廓右下角的 45° 斜角加旁边的「/」斜带。

1. 写 3 个方向，每个一行：**画什么物件 → 强调色是哪一块 → 为什么一眼能懂**。
2. 每个方向按三项各打 0–2 分：**一眼看懂**、**有自己的一处**、**能用 1–4 段线加一块填色画出**（放进类别记号之后）。
3. 自己选总分最高的一个往下做，不等用户确认。用户要多方案时，3 个都画。

- 只画一个隐喻，抓产品最核心的那个结果，不必把每个功能都画进去。线越多，29 px 下越糊。
- **有自己的一处**：先找 SF Symbols、Material Symbols 和 Lucide 里的同名符号（线稿风格最容易撞 Lucide）。剪影一样的，必须在轮廓或结构上改一处：物件的局部形状、线在哪里断开、哪一块是强调色。只挪强调色的位置不算。不要沿用示例的整体框架，也不要画成 Linear 的标。
- **强调色本身可以就是第二个物件**：剪辑手柄、扫描光束、词典的书签。隐喻本身是一对同类物体时（互换的两支箭头），一个画线，另一个填色（Convert）。
- 用户已有别的 app 图标时，新图标的外形和强调色位置要和它们拉开，第 5 步用 `series.py` 查。
- 不用字母、文字，不用 ✦ 闪光这类 AI 套路符号：AI 类用右下角的斜带。标准图标就是字母的品类，用这张表（表里的品类默认不写 `data-category`；用户把它归进四类之一时，比如字幕归视频，再加上那一类的记号和颜色）：

| 品类 | 画什么（线） | 强调色 |
|---|---|---|
| 翻译 | 两个错开的对话气泡，后一个画线，尾巴朝左下 | 前一个小一号的胶囊气泡填色，压在后一个的右上角上；后一个的线在它两侧各停在 60 以外。80 px 下可能被读成聊天 app，交付时写进「可再调」 |
| 字体 | 钢笔尖的轮廓和中缝，尖角 ≥ 90° | 笔尖后面那一截握位，离笔尖 60 |
| 词典 | 一本合着的书（圆角矩形，r ≥ 56） | 从书顶边垂下的燕尾书签，书的顶边在书签两侧各停在 60 以外 |
| 输入法 | 一排三个圆角键帽，键帽之间净空 ≥ 60 | 中间那个键填色、低一截：被按下 |
| 字幕 | 圆角屏幕 | 屏幕底部的字幕条（胶囊），屏幕的底边在它两侧各停在 60 以外 |

### 3. 定颜色

从 `style.md` 的强调色表里只选一个，按顺序判断，命中就停：

1. 属于四类或健康、财务 → 这一类的颜色（工具蓝、图片黄、视频珊瑚、AI 紫、健康和财务绿），不看品牌色
2. 有品牌色 → 表里最接近的一个（绿除外）
3. 物件在现实里有颜色（太阳、天空）→ 用它（绿除外）
4. 都没有 → 蓝

不要自造颜色。底和线的颜色是固定的，不用选。只画默认（石墨）外观，浅色、深色、单色由脚本生成。

### 4. 画 SVG

复制 `assets/template.svg`，只改标了 TODO 的地方：`data-shape`、`data-category`、transform（k 和 translate）、线稿、强调色、两个渐变的 y1 / y2、辉光的颜色和 stdDeviation（不要辉光就删掉 `#glow` 和 `#glow-blur`）。线写成中线，`#body` 组上统一写 stroke（60 ÷ k、圆头圆角），单个元素不带颜色和线宽。圆弧、圆角矩形、气泡、多边形和折线、播放三角用 `scripts/shapes.py` 出中线；扇形、弓形、环段、胶囊、AI 斜带出强调色的轮廓，强调色被线挡住的地方用 `shapes.py minus` 减掉。坐标用整齐的数字，在注释里写出几何关系和净空，并把生成每一笔用的 `shapes.py` 命令留在注释里。写法见 `construction.md`「几何速查」和「属性和类」。

**直接按最终像素画（k = 1）**，位置只靠 translate 调。报告说凸包或剪影不够时会给出「k 改为 …」：改 k 之后 stroke-width 写 60 ÷ k，把注释里的 `shapes.py` 命令加上 `--k <新 k>` 重跑一遍，再按下一次报告给的 translate 调位置。

### 5. 渲染、自检

```bash
python3 <skill 目录>/scripts/render.py icon.svg -o renders --variants
```

终端逐条打印指标，每条标 PASS / FAIL / INFO。再打开 `*-sheet.png` 亲眼看：80 px 下认不认得出，和 Tide 并排是否一样大，40 / 29 px 的 small 版线之间有没有糊住，单色、Tinted、Clear 和安卓主题图标（浅色、深色主题）里结构和含义还在不在。

报告没有 FAIL 以后，和已有的图标一起跑一次系列检查（用户给了他别的 app 图标就用 `--with` 传进去；没有就不写 `--with`，和 `examples/` 比，示例只作参考，只看配对、不算扎堆）：

```bash
python3 <skill 目录>/scripts/series.py icon.svg --with <已有图标>.svg ... -o renders
```

看 `series-sheet.png` 和终端的「像」「扎堆」「占了记号的角」：新图标三项都要是 0。

**节奏**：第一次渲染后只修报告里 FAIL 的项和验收清单里没过的项，最多 2 轮。一轮 = 改一次 SVG 再跑一次 render.py；`overview.py`、`series.py` 和定稿时加 `--export` 的那次不算。猜错用途时换方向也算 1 轮；2 轮用完就交付，把没画的方向写进「可再调」。剩下的问题也写进「可再调」，不要无限打磨。打磨时不加东西，只调准已有的东西：比例、断口、强调色的大小和位置。

| 看到 | 哪项指标会报（报告里的 key） | 改 |
|---|---|---|
| 报告第一行就是结构 FAIL | 结构 `structure` | 按 `construction.md`「图层结构」改 id 和顺序：`#subject` 里只放 `#glow`、`#body`、`#accent-shape`；删掉旧风格的 `data-cut`、`#cut`、`detail` |
| 线粗细不一、方头或尖角 | 线宽 `stroke` | stroke 只写在 `#body` 上：60 ÷ k，`stroke-linecap` 和 `stroke-linejoin` 都是 round；单个元素不写 stroke-width；填色的白块改成线 |
| 两段线挨得太近，小尺寸糊住 | 线间净空 `line_gap`、小尺寸 `small` | 中线相距 ≥ 120；一段线在另一段旁边停下时，端点离它的中线 ≥ 90，或者干脆接在它的中线上连成一段 |
| 锐角拐角、窄缝、小孔糊成一团 | 线间夹缝 `pinch` | 拐角放宽到 ≥ 45°，两笔拉开，孔放大到内径 ≥ 60 |
| 强调色贴着线或压线 | 强调色到线 `accent_gap` | 强调色缩小或挪开到离线 ≥ 60；被线挡住的地方用 `minus` 减掉「那条线外扩 90」 |
| 线太多、太碎 | 线条段数 `parts` | 合成 1–4 段：能接上的接在一起，只留一个隐喻 |
| 主体显得小、显得重，和 Tide 不一样大 | 长边 `long_side`、剪影面积或凸包面积 `silhouette` / `hull`（形状 `shape` 只作参考）；墨量 `ink`（INFO） | 照报告给的「k 改为 …」改 scale，stroke-width 跟着改，再用 `shapes.py --k` 重出圆角和强调色 |
| 主体偏上、偏下或偏一边 | 重心 `centroid` | 照报告给的「translate 改为 (…)」改，一次到位 |
| 强调色太抢或太弱 | 强调色占比 `accent` | 改强调色的大小或角度，不动线 |
| 看起来发平、发灰，或多出了颜色 | 颜色 `palette`、线渐变 `body_gradient`、线对底 `contrast_body` | 底和线只用色板的值，每个渐变只有那一对 stop；线渐变跨度 600，所有线共用一个；y1、y2 照报告给的值改 |
| 强调色周围发亮 | 辉光 `glow` | 辉光不透明度降到 .16 以下，或 stdDeviation 调小；不行就去掉辉光 |
| 遮住颜色说不出类别，或类别记号 FAIL | 类别记号 `category` | 颜色换成这一类的；工具加一条横贯整幅的水平直线（中线在高度 35–75 %），图片的太阳画成整圆（r ≥ 72）挪到左上角，视频单独画一个 `play` H ≥ 240 ÷ k 的三角，AI 在外轮廓右下角走一道 45° 斜角、旁边放 `shapes.py aiband`（不放在圆上）。见 `style.md`「类别记号」 |
| 和已有的某个图标像，或强调色挤在一处 | `series.py` 的「像」「扎堆」「占了记号的角」 | 改轮廓（长宽比、线在哪里断开、强调色压在框角上）或强调色的位置，只换颜色不算 |
| 安卓主题图标里认不出 | 对照图的主题图标两格 | 底和强调色都没了，只剩线：换更具体的轮廓 |
| 深色商店里边缘看不见 | 商店边缘 `store_edge`（INFO） | 不改母版：交付时提 `--store-ab` 的变体，见第 6 步 |
| Android 圆形遮罩会裁到 | r_max `android` | 不改母版，`--export` 按系数自动缩放 |
| 浅色版里白线读成了别的东西（白云变乌云） | 线对底的浅色外观数字（INFO） | 已知取舍，不改：写进「可再调」，营销图用默认石墨版 |
| 和同名系统符号一模一样 | 无（凭记忆比对） | 在轮廓或结构上改一处，见第 2 步 |
| 认不出来 | 对照图 80 px | 换更具体的物件，或把强调色挪到最能说明用途的那一块 |
| 认得出物件，但猜错用途 | 对照图 80 px | 回第 2 步换方向（算 1 轮） |
| 两轮后仍不满意 | 无 | 交付，并写明还差什么 |

### 6. 交付

定稿后加 `--export` 再渲染一次，生成 Icon Composer 分层和各平台文件；要上 App Store 时再加 `--store-ab`，出商店 A/B 变体：

```bash
python3 <skill 目录>/scripts/render.py icon.svg -o renders --variants --export --store-ab
```

默认交付默认（石墨）、浅色、深色、单色四种外观，加 Icon Composer 分层。给用户：

- 对照图、SVG 母版、四张 PNG（`<name>-1024`、`-light`、`-dark`、`-mono`）和 `renders/export/icon-composer/` 的路径
- 三行设计说明：画了什么物件、强调色是哪一块、用的强调色
- 一句和同名 SF Symbol / Material Symbol / Lucide 图标的差别
- 另外两个方向，各一行
- 系列检查的结论：和哪个已有图标分数最高、多少
- 「可再调」：没修完的问题和已知取舍（比如浅色版里白云读成乌云），没有就省略
- 一句提醒：安卓主题图标在对照图里是近似，上架前在开启主题图标的真机启动器上看一遍
- 出了 `--store-ab` 时一句：深色 App Store 里石墨底的边缘看不清，`renders/store-ab/` 的浅一档底、细亮边（和类别色底）可以在产品页优化里和主图标对照，测试图标要作为备用图标打进安装包（`README.txt` 有步骤）
- 一行界面主色，按 `style.md` 强调色表的「界面主色」列（蓝、绿、紫同色，珊瑚、黄、灰用蓝）。要做 UI 主题时用 `rian-app-theme`：`python3 <rian-app-theme 目录>/scripts/build.py --name <名字> --accent <色名> -o themes/<名字>`。`--accent` 传图标强调色的**色名**（蓝 / 绿 / 黄 / 珊瑚 / 紫 / 灰，或 blue / green / yellow / coral / violet / gray；强调色表里的两个色值也认，别的色值会被拒），脚本自己换算界面主色。预览用 `python3 <rian-app-theme 目录>/scripts/preview.py themes/<名字> --screen <timer|notes|list|editor|chat> --icon renders/<name>-1024.png --icon-dark renders/<name>-dark.png`（深色版来自 `--variants`）。`--variants` 还写出两份平涂的主体（只有线稿和强调色，透明底，不带渐变和辉光，和界面的 Lucide 线是一种画法）：`<name>-mark.svg/.png` 是亮线，给深色模式的石墨品牌面板；`<name>-mark-light.svg/.png` 是深线，给浅色模式的浅品牌面板。界面的引导、付费墙、空状态、启动页用它们做插图，`preview.py` 在 `--icon` 旁边自动找到。app 图标本身（关于页）保留渐变。`--screen` 按 app 类型选：计时、工具类，以及翻译这类 → `timer`，笔记和阅读类 → `notes`，账本和列表类 → `list`，图片、视频类 → `editor`，AI 类 → `chat`，拿不准就 `timer`

Android 三层图标、Play 512、PWA 和 favicon 也在 `renders/export/` 里，用户要上架时指给他，见 `construction.md`「平台导出」。Xcode 走 asset catalog 时，深色外观用透明底的 `ios-1024-dark.png`。迭代时只改用户点名的部分。
