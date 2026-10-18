---
name: rian-app-icon
description: Design app icons as production SVG in Rian's house style, the graphite style after Linear with Apple and Google platform specs - a solid light geometric mark with 48 px negative-space cuts on a graphite gradient, one accent piece. No strokes and no letters; 2 to 4 solid pieces carry the structure, so the mark survives monochrome and small sizes, and tools, image, video and AI apps each carry a fixed category mark. Renders a review sheet with automatic cut, thickness, size, contrast, accent and category checks, runs a series check against existing icons, and generates light, dark and mono appearances, Icon Composer layers, Android adaptive and themed icons, Play, PWA and favicon exports, and App Store A/B variants. Use when asked to create, redesign or iterate on an app icon, launcher icon, app logo mark or favicon. Not for wordmarks or logos with letters, and not for in-app UI icons. 用于按 Rian 的石墨风格（Linear 式：深石墨底、亮色实形、48 px 负形切口、一块强调色）设计应用图标、启动图标和 favicon（SVG）；不做字标或带字母的 logo，也不做界面里的小图标。
---

# Rian App Icon

把一句产品描述变成一枚可以直接上架的 app 图标：1024 全出血 SVG 母版，默认（石墨）、浅色、深色、单色四种外观，Icon Composer 分层，一张评审对照图；需要时再导出 Android、Play、PWA、favicon 文件和商店 A/B 变体。

只有一种风格：**石墨**。深石墨底上放一块亮色实形，用 48 px 的负形切口分出结构，强调色只点一处。整个图标没有一条描边：2–4 块实心几何形（一般 3–4 块），相邻两块之间是一道最窄处 48 px 的切口，强调色是其中一块。每一枚都是同样的四层：石墨底、可选的辉光、主体、强调色块。工具、图片、视频、AI 四类 app 各有一个固定的类别记号。

**动笔前读 `references/style.md`**：风格规则、全部阈值和验收清单都在那里。**画 SVG 时再查 `references/construction.md`** 的「几何速查」（`shapes.py` 各命令、切口写法、翻译气泡的完整例子）和「属性和类」；平台规格也在它的「平台导出」。

目标是快：第一版渲染出来之前不停下来问用户。

## 示例

`examples/` 里有三枚，渲染图在 `examples/renders/`（三枚并排是 `overview.png`）。挑和题材最接近的一枚，只借技巧，不要照搬整体框架。

| 示例 | 画了什么 | 可借的技巧 |
|---|---|---|
| `tide.svg` 专注计时 · 珊瑚 | 秒表：实心表盘、两段表圈（珊瑚段是 25 分钟的进度）、冠钮，4 块 | 尺寸基准（外框 580 × 712）；环段接缝的径向切口直接写进路径（`shapes.py ring`，gap 48）；表盘和表圈之间是同心切口；冠钮高 84 ≥ 80，按剪影质心居中 |
| `halo.svg` 天气 · 黄 | 云是主体，右上方的太阳被一条 45° 的弦切成弓形，2 块 | 自由切口用 45° 弦（`shapes.py segment`），不沿云的轮廓外扩；弦切口只在切点是 48，往两头张开到约 95（报告 `cut_spread` p50 71 / p90 85，已知取舍）；云是三个圆加 r 56 凹角的一条 path；`data-shape="open"` 按凸包比大小，k = 1.15 |
| `ledgerly.svg` 记账 · 绿（财务） | 饼图沿 −45° 抽出一块 72° 的切片，2 块 | `shapes.py sector`；切片外移 48 ÷ sin 36° = 81.7，两条直切口都是 48；缺口凹角 r 72 和切片顶点的 r 24 同心；用 72° 不用 90°，强调色占比和另两枚拉平，也和 `chart.pie.fill` 拉开 |

## 工作流程

### 1. 读懂产品

用户用什么语言说话，说明和交付就用什么语言。

需要三样：**名字**、**一句话说清它做什么**、**品牌色**（可选）。「一句话」要具体到动作或对象，比如「把待办拆成 25 分钟的专注块」，不能只说「效率工具」。信息不全时不要追问：自己补一个合理版本，标明「这是我的假设」，然后继续。

### 2. 定隐喻

这个风格追求**一眼看懂**，像 Apple 和 Google 自己的 app：计时就是秒表，天气就是太阳和云，记账就是饼图。

先定类别：工具、图片、视频、AI，健康、财务，或者都不是（按主要功能归，顺序见 `style.md`「类别记号」：先看是不是靠模型，再看处理的是图片、视频还是文件；计时、笔记、翻译这类不归类）。类别定了强调色和类别记号，隐喻要放得下这个记号：工具是一道把物件分成上下两块的水平切口，图片是左上角的圆太阳，视频是挖在主要实形里的播放三角，AI 是切掉右下角的「/」斜带。

1. 写 3 个方向，每个一行：**画什么物件 → 强调色是哪一块 → 为什么一眼能懂**。
2. 每个方向按三项各打 0–2 分：**一眼看懂**、**有自己的一处**、**能用 3–4 块实形画出**（放进类别记号之后）。
3. 自己选总分最高的一个往下做，不等用户确认。用户要多方案时，3 个都画。

- 只画一个隐喻，抓产品最核心的那个结果，不必把每个功能都画进去。块越多，29 px 下越糊。
- **有自己的一处**：先找 SF Symbols 和 Material Symbols 里的同名符号。剪影一样的，必须在轮廓或结构上改一处：物件的局部形状、切口的位置、哪一块是强调色。只挪强调色的位置不算。不要沿用示例的整体框架，也不要画成 Linear 的标（圆 + 左下三条带）。
- **强调色本身可以就是第二个物件**：词典的书签，翻译里前面那个气泡。隐喻本身是一对同类物体时（互换的两支箭头），较小或一样大的那个当强调色，写 `data-accent="pair"`，占比上限 33 %，不必硬画成一大一小。
- 用户已有别的 app 图标时，新图标的外形和强调色位置要和它们拉开，第 5 步用 `series.py` 查。
- 不用字母、文字，不用 ✦ 闪光这类 AI 套路符号：AI 类用右下角的斜带。标准图标就是字母的品类，用这张表（表里的品类默认不写 `data-category`；用户把它归进四类之一时，比如字幕归视频，再加上那一类的记号和颜色）：

| 品类 | 画什么（主体） | 强调色 |
|---|---|---|
| 翻译 | 两个错开叠放的对话气泡（`shapes.py bubble`）。默认做法（和 SF Symbols `bubble.left.and.bubble.right` 两个同样大的气泡拉开）：后一个是圆角矩形气泡、尾巴朝左，在左下；前一个是**胶囊气泡**（R = H / 2）、小一号、尾巴朝右，在右上，盖住后一个的右上角。切口直接写进路径：`shapes.py minus "<后一个>" "<前一个 --grow 48>"`，完整命令见 `construction.md`「几何速查」。两个气泡在 80 px 下可能被读成聊天 app，交付时写进「可再调」 | 前一个气泡 |
| 字体 | 钢笔尖，尖角 ≥ 90°（中缝和两侧轮廓的夹角才 ≥ 45°），端头圆角 24。中缝做成一道 48 的切口，从笔尖一直通到笔尖后沿，把笔尖切成左右两半 | 笔尖后面那一截握位，和笔尖之间隔一道垂直于笔身的切口 |
| 词典 | 一本合着的书（圆角矩形，rx ≥ 短边 20 %） | 从书顶边垂下的燕尾书签。书在书签的位置挖空，两侧和下端留 48，切口从书顶边通出去：书签外扩 48 的轮廓写成 path，用 `shapes.py minus` 从书上减掉 |
| 输入法 | 一排三个圆角键帽（`shapes.py rrect`），间隙 48 | 中间那个键被按下：顶边比两侧低约 30 %。三个等高的话强调色约占 28 %，超过 25 % |
| 字幕 | 圆角屏幕 | 屏幕底部的字幕条，横跨屏幕下沿（一半在屏内）。屏幕减去「字幕条外扩 48」：`shapes.py minus "<rrect 屏幕>" "<rrect 字幕条 --grow 48>"`，切口两端都通到屏幕外 |

### 3. 定颜色

从 `style.md` 的强调色表里只选一个，按顺序判断，命中就停：

1. 属于四类或健康、财务 → 这一类的颜色（工具蓝、图片黄、视频珊瑚、AI 紫、健康和财务绿），不看品牌色
2. 有品牌色 → 表里最接近的一个（绿除外）
3. 物件在现实里有颜色（太阳、天空）→ 用它（绿除外）
4. 都没有 → 蓝

不要自造颜色。底和主体的颜色是固定的，不用选。只画默认（石墨）外观，浅色、深色、单色由脚本生成。

### 4. 画 SVG

复制 `assets/template.svg`，只改标了 TODO 的地方：`data-shape`、`data-category`、transform（k 和 translate）、主体的实形、强调色块、两个渐变的 y1 / y2、辉光的颜色和 stdDeviation（不要辉光就删掉 `#glow` 和 `#glow-blur`）；模板里的 `#cut` mask 是空的、没挂到任何层上，用不到就删掉。环段、弓形、扇形、圆角矩形、多边形、气泡、播放三角、AI 斜带用 `scripts/shapes.py` 生成，「主体减去强调色外扩 48」用 `shapes.py minus`，切口直接写进路径；`#cut` mask 只用来起稿。坐标用整齐的数字，在注释里写出几何关系，并把生成每块用的 `shapes.py` 命令留在注释里。写法见 `construction.md`「几何速查」和「属性和类」。

**直接按最终像素画（k = 1）**，位置只靠 translate 调。报告说凸包或剪影不够时会给出「k 改为 …」：改 k 之后，把注释里的 `shapes.py` 命令加上 `--k <新 k>` 重跑一遍（切口、圆角、外扩这些最终像素参数会自动除以 k，坐标不变），再按下一次报告给的 translate 调位置。

### 5. 渲染、自检

```bash
python3 <skill 目录>/scripts/render.py icon.svg -o renders --variants
```

终端逐条打印指标，每条标 PASS / FAIL / INFO。再打开 `*-sheet.png` 亲眼看：80 px 下认不认得出，和 Tide 并排是否一样大，40 / 29 px 的 small 版切口有没有糊住，单色、Tinted、Clear 和安卓主题图标（浅色、深色主题）里结构和含义还在不在。

报告没有 FAIL 以后，和已有的图标一起跑一次系列检查（用户给了他别的 app 图标就用 `--with` 传进去；没有就不写 `--with`，和 `examples/` 比，示例只作参考，只看配对、不算扎堆）：

```bash
python3 <skill 目录>/scripts/series.py icon.svg --with <已有图标>.svg ... -o renders
```

看 `series-sheet.png` 和终端的「像」「扎堆」「占了记号的角」：新图标三项都要是 0。

**节奏**：第一次渲染后只修报告里 FAIL 的项和验收清单里没过的项，最多 2 轮。一轮 = 改一次 SVG 再跑一次 render.py；`overview.py`、`series.py` 和定稿时加 `--export` 的那次不算。猜错用途时换方向也算 1 轮；2 轮用完就交付，把没画的方向写进「可再调」。剩下的问题也写进「可再调」，不要无限打磨。打磨时不加东西，只调准已有的东西：比例、切口、强调色块的大小和位置。

| 看到 | 哪项指标会报（报告里的 key） | 改 |
|---|---|---|
| 报告第一行就是结构 FAIL | 结构 `structure` | 按 `construction.md`「图层结构」改 id 和顺序：`#subject` 里只放 `#glow`、`#body`、`#accent-shape` |
| 小尺寸切口糊住，几块粘成一团 | 小尺寸 `small`、切口宽 `cut` | 每道切口最窄处 48（mask 的 stroke-width 48 ÷ k）；删掉最碎的一块，或标 `class="detail"`；不该相邻的两块拉开到 ≥ 96 |
| 强调色贴着主体，或离得太远 | 切口宽 `cut`（「强调色和主体粘成一块」「强调色到主体最近 …」） | 强调色和主体之间正好隔一道 48：`ring --gap 48`、外移 48 ÷ sin(θ ÷ 2)、`minus` 减去强调色外扩 48 |
| 两块之间的缝宽窄不一 | 没有 FAIL：`cut` 只量最窄处；看切口沿边宽 `cut_spread`（INFO，平行切口约 48 / 52）和眼睛 | 用 `shapes.py` 的 gap、平移量 48 ÷ sin(θ ÷ 2)、同心半径差 48 算出来，不凭眼睛摆；mask 的 stroke-width 写 48 ÷ k。自由 45° 弦切口离开切点会变宽，是已知取舍（Halo） |
| 切口停在形体中间，留下一道槽 | 切口贯穿 `cut_through` | 把切口延长到外轮廓外面，真正切成两块；或者不要这道切口 |
| 某一块显得细，或伸出一根细杆、细楔，小尺寸下断掉 | 实形最薄处 `thin`（保留率，和「去掉的部分最远 … px」） | 加厚到 ≥ 72（环 ≥ 84），或删掉这一截；切口和轮廓的夹角 ≥ 45° |
| 块太多、太碎，或者只有一整块 | 块数 `pieces` | 合并成 3–4 块，只留一个隐喻；第 5 块非要不可时在 `#subject` 写 `data-pieces-why`。只有一块时用切口把强调色那一块分出来；< 2 % 凸包的碎块标 `class="detail"`。detail 只给这种碎块，大块标了会 FAIL（64 px 及以下它会消失） |
| 单色版里强调色下面透出主体 | 不重叠 `overlap` | 主体在强调色的位置真正挖空（写进路径、evenodd 或 mask），不靠盖住 |
| 主体显得小、显得重，和 Tide 不一样大 | 长边 `long_side`、剪影比或凸包比 `silhouette` / `hull`（关键线 `shape` 只作参考）；墨量 `ink`（INFO） | 照报告给的「k 改为 …」改 scale，再用 `shapes.py --k` 重出带切口的路径 |
| 主体偏上、偏下或偏一边 | 重心 `centroid` | 照报告给的「translate 改为 (…)」改，一次到位 |
| 强调色太抢或太弱 | 强调色占比 `accent` | 改强调色块的大小或角度，不动主体。一对同类物体里较小或一样大的那个当强调色时写 `data-accent="pair"`（上限 33 %） |
| 看起来发平、发灰，或多出了颜色 | 色板 `palette`、主体渐变跨度 `body_gradient`、亮度对比 `contrast_body` | 底和主体只用色板的值，每个渐变只有那一对 stop（中间不加第三个颜色或亮带）；单块不带自己的 fill 和透明度；主体渐变跨度 600，所有块共用一个；y1、y2 照报告给的值改 |
| 切口里发亮、看不清 | 辉光 `glow`、切口清晰度 `cut_clarity` | 辉光不透明度降到 .16 以下，或 stdDeviation 调小；不行就去掉辉光 |
| 出现线条、轮廓线 | 无描边 `no_stroke` | 改成填充的实形；切口只在 mask 里用描边画 |
| 遮住颜色说不出类别，或类别记号 FAIL | 类别记号 `category` | 颜色换成这一类的；工具加一道贯穿的水平切口（中线在高度 35–75 %），图片的太阳画成整圆（r ≥ 100）挪到左上角，视频挖一个 `play` H ≥ 200 ÷ k 的三角，AI 用 `shapes.py aiband` 切掉右下角（不放在圆上，占比不到 10 % 时加大 `--chamfer`）。不属于四类就不写 `data-category`，也不用绿和斜带。见 `style.md`「类别记号」 |
| 和已有的某个图标像，或强调色挤在一处 | `series.py` 的「像」「扎堆」「占了记号的角」 | 改外形（轮廓、长宽比、块怎么分）或强调色的位置，只换颜色不算；同一类别的两枚颜色和记号一样，只能靠外形和布局分开（门槛 0.50） |
| 安卓主题图标里认不出 | 对照图的主题图标两格（`themed` 那一行是固定参考，每枚都一样） | 底和强调色都没了，只剩形状：换更具体的轮廓，或让切口两边的块更分明 |
| 深色商店里边缘看不见 | 商店边缘 `store_edge`（INFO） | 不改母版：交付时提 `--store-ab` 的变体，见第 6 步 |
| Android 圆形遮罩会裁到 | r_max `android` | 不改母版，`--export` 按系数自动缩放 |
| 浅色版里白色主体读成了别的东西（白云变乌云） | 亮度对比的浅色外观数字（INFO） | 已知取舍，不改：写进「可再调」，营销图用默认石墨版 |
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
- 一句和同名 SF Symbol / Material Symbol 的差别
- 另外两个方向，各一行
- 系列检查的结论：和哪个已有图标分数最高、多少
- 「可再调」：没修完的问题和已知取舍（比如浅色版里白云读成乌云），没有就省略
- 一句提醒：安卓主题图标在对照图里是近似，上架前在开启主题图标的真机启动器上看一遍
- 出了 `--store-ab` 时一句：深色 App Store 里石墨底的边缘看不清，`renders/store-ab/` 的浅一档底、细亮边（和类别色底）可以在产品页优化里和主图标对照，测试图标要作为备用图标打进安装包（`README.txt` 有步骤）
- 一行界面主色，按 `style.md` 强调色表的「界面主色」列（蓝、绿、紫同色，珊瑚、黄、灰用蓝）。要做 UI 主题时用 `rian-app-theme`：`python3 <rian-app-theme 目录>/scripts/build.py --name <名字> --accent <色名> -o themes/<名字>`。`--accent` 传图标强调色的**色名**（蓝 / 绿 / 黄 / 珊瑚 / 紫 / 灰，或 blue / green / yellow / coral / violet / gray；强调色表里的两个色值也认，别的色值会被拒），脚本自己换算界面主色。预览用 `python3 <rian-app-theme 目录>/scripts/preview.py themes/<名字> --screen <timer|notes|list|editor|chat> --icon renders/<name>-1024.png --icon-dark renders/<name>-dark.png`（深色版来自 `--variants`）。`--variants` 还写出 `<name>-mark.svg/.png`（只有主体，透明底）：界面的引导、付费墙、空状态、关于页、启动页用它做插图，放在同样的石墨上，`preview.py` 在 `--icon` 旁边自动找到。`--screen` 按 app 类型选：计时、工具类，以及翻译这类 → `timer`，笔记和阅读类 → `notes`，账本和列表类 → `list`，图片、视频类 → `editor`，AI 类 → `chat`，拿不准就 `timer`

Android 三层图标、Play 512、PWA 和 favicon 也在 `renders/export/` 里，用户要上架时指给他，见 `construction.md`「平台导出」。Xcode 走 asset catalog 时，深色外观用透明底的 `ios-1024-dark.png`。迭代时只改用户点名的部分。
