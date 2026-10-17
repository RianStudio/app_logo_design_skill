# SVG 构造与平台规格

这里只讲怎么搭、怎么导出。所有数字都在 `style.md`。

## 图层结构

`assets/template.svg` 是用 Tide 写好的模板，结构如下（从下到上）：

```
<svg viewBox="0 0 1024 1024">   根只写 viewBox，不写宽高
<defs>
  #bg            linearGradient：底，y 0 → 1024
  #body-fill     linearGradient：主体，跨度 600 ÷ k（不叫 #body，那是主体组的 id）
  #accent        linearGradient：强调色「浅 → 主」，跨度 480 ÷ k
  #glow-blur     可选 filter：辉光
  #cut           可选 mask：起稿时画切口（模板里是空的、没挂到任何层上；用不到就删掉）
#background      一个 rect：0 0 1024 1024，fill url(#bg)，里面不放东西
#subject         transform；data-shape；data-cut="48"；data-category
  #glow          可选：<use href="#accent-shape" filter="url(#glow-blur)"/>，第一个子元素
  #body          <g fill="url(#body-fill)">：主体的所有实形（可以带 mask="url(#cut)"）
  #accent-shape  一个元素（path 或 g），fill url(#accent)（可以带 mask="url(#cut)"）
```

`render.py --store-ab` 写出的商店变体在根上加 `data-variant`，细亮边变体另在 `#background` 和 `#subject` 之间加一个 `<path id="rim">`；手画的母版不写这些。

三个渐变都写 `gradientUnits="userSpaceOnUse"`，竖直（x1 = x2 = 0）。辉光 filter 照抄：

```xml
<filter id="glow-blur" x="-50%" y="-50%" width="200%" height="200%" color-interpolation-filters="sRGB">
  <feGaussianBlur in="SourceAlpha" stdDeviation="24" result="b"/>   <!-- 24 ÷ k -->
  <feFlood flood-color="#EC5B45" flood-opacity="0.16"/>              <!-- 强调色的「主」 -->
  <feComposite in2="b" operator="in"/>
</filter>
```

## 属性和类

render.py 靠这些标记测量、换外观、导出分层，画的时候顺手写上：

| 写在哪 | 写法 | 作用 |
|---|---|---|
| 根 | 只写 `viewBox="0 0 1024 1024"` | |
| 根 | `data-variant="lighter｜rim｜tint"`，细亮边另有 `<path id="rim" fill="url(#rim-fill)">` | 只出现在 `--store-ab` 写出的商店变体上：色板按变体查那一对底（细亮边另查 `#rim-fill`），小尺寸块数不算 `#rim`。手画的母版不写 |
| `<defs>` | `#bg`、`#body-fill`、`#accent` 三个 `linearGradient`，都用 `userSpaceOnUse`；每个只有两个 stop，取色板里那一对值，不加第三色、不写 stop-opacity；可选 `#glow-blur` filter、`#cut` mask | 读色板，算渐变跨度。整个文件 id 不能重复（主体渐变写成 `id="body"` 会和 `<g id="body">` 撞，结构 FAIL） |
| `#background` | 一个 `rect`，x = y = 0，宽高 1024（或 100%），fill `url(#bg)`；没有子元素、没有 transform。底上不加光斑、纹理，根下面也不放 `#background`、`#subject` 以外的图形 | 换外观时改它；不合规是结构 FAIL |
| `#subject` | `data-shape="circle｜square｜tall｜wide｜open"`、`data-cut="48"`、`transform="translate(512 512) scale(k) translate(-512 -512) translate(tx ty)"` | 选尺寸检查；声明切口宽；k 用来换算源坐标 |
| `#subject` | `data-category="tools｜image｜video｜ai｜health｜finance"`，不属于这些类就不写 | 按类别查强调色和类别记号，见 `style.md`「类别记号」 |
| `#subject` | `data-pieces-why="…"`，只在有第 5 块时写，一句话说为什么非要它 | 5 块时没有它，块数 FAIL；理由印在块数那一行 |
| `#glow` | 可选，`#subject` 的第一个子元素，`<use href="#accent-shape" filter="url(#glow-blur)"/>`。filter 叫 `#glow-blur`，不叫 `#glow`，否则 id 重复 | 测量时隐藏；从 `#glow-blur` 读 stdDeviation 和 flood-opacity |
| `#body` | `<g fill="url(#body-fill)">`，里面是主体的所有实形；单块不写自己的 fill（写也只能是 `url(#body-fill)`），不写 opacity / fill-opacity | 测主体面积、主体对底的亮度对比 |
| `#accent-shape` | 一个元素（`path` 或 `g`），fill `url(#accent)`；同样不带 opacity | 测强调色占比、和主体之间的切口 |
| `#accent-shape` | `data-accent="band"` | 强调色是 AI 斜带（`shapes.py aiband` 打印的那条）：占比按 8–18 % 查，另查方向、带宽和位置；只给 `data-category="ai"` |
| `#accent-shape` | `data-accent="pair"` | 强调色是一对同类物体里较小或一样大的那个：占比按 10–33 % 查，另查它不大于最大一块主体的凸包 |
| 单块实形 | `class="detail"` | 64 px 及以下删掉。只给面积 < 2 % 凸包的碎块；≥ 2 % 的块标了也是块数 FAIL（不能拿它躲块数上限） |
| `<mask id="cut">` | `maskUnits="userSpaceOnUse"`，x、y、宽、高覆盖整个源坐标；先放白色 rect，再放 `<g id="cuts" stroke="#000" stroke-width="48÷k" stroke-linecap="butt" fill="none">` | 起稿时画切口；查 `stroke-width × k` = 48。mask 写在 `#body` 或 `#accent-shape` 上，不写在 `#subject` 上，这样坐标跟着 transform 走 |

旧风格的 `#backing`、`#line`、`lift`、`class="on-accent"`、`data-part="split"`、`data-accent="line"`，以及斜纹的 `data-part="band"` 都不再使用。

## 要点

- **缩放**：直接按最终像素画，k = 1（Tide、Ledgerly），transform 里只调 translate。剪影比 / 凸包比不在范围里时，报告会写「k 改为 …」；改了 k，源坐标 = 最终像素 ÷ k，要除以 k 的有：切口 48、最薄 72、圆角 24、渐变跨度 600 / 480、辉光 stdDeviation、mask 的 stroke-width。带切口、圆角的路径用 `shapes.py … --k K` 重出（`--gap`、`--fillet`、`--grow` 等自动 ÷ k），其余几项手算。Halo 是 k = 1.15，切口写 41.7（`--gap 48 --k 1.15`）。重心不对时报告会写「translate 改为 (tx ty)」，照抄。
- **渐变坐标**（源坐标）：y1、y2 = 中心 ∓ 300 ÷ k（主体）或 ∓ 240 ÷ k（强调色），中心是这一层上下范围的中点。Tide：主体 y 114–826，中心 470，写 170 / 770；珊瑚段 y 247–774，写 270.5 / 750.5。
- **主体共用一个渐变**：所有主体块放进同一个 `#body` 组，像同一束顶光照下来。换外观时 render.py 只改 `#bg`、`#body-fill`、`#accent` 的 stop 和辉光，不动形状。
- **能烘焙的写法**：`#body` 和 `#accent-shape` 里只用 `path`、`circle`、`ellipse`、`rect`、`polygon`，`--export` 才能把 transform 烘焙进 Icon Composer 层的坐标（点坐标按 transform 换算，圆弧半径乘 k）。里面出现 `mask`、`clip-path`、`filter`、`<use>` 或非等比缩放时，那一层退回 PNG。
- **渐变不对时**，报告的主体渐变跨度、强调色渐变跨度两行会直接给出该写的 y1、y2（源坐标），照抄即可。
- 注释里不能出现连续两个连字符，否则 SVG 解析失败、渲染出来是空白。不用 `<text>`，不嵌位图。坐标取整齐的数，在注释里写出几何关系（圆心、半径、角度、切口宽、块数）。

## 几何速查

画布中心 `(512, 512)`。从 3 点钟方向顺时针 θ 角、半径 r 的点：`(cx + r·cosθ, cy + r·sinθ)`；12 点是 −90°。

`scripts/shapes.py` 打印填充用的 SVG 路径（不带参数运行时打印完整用法）：

| 形状 | 命令 | 用在哪 |
|---|---|---|
| 环段 | `python3 scripts/shapes.py ring CX CY R_OUT R_IN A0 A1 [--gap 48] [--fillet 0]` | 进度环、表圈。`--gap G` 把两端写成和接缝半径平行、往段内偏 G ÷ 2 的直线：两段共用一个接缝角，中间正好是一道 G 宽的径向切口，不用 mask。`--fillet` 给四个角倒圆。Tide：`ring 512 536 290 206 -90 60 --gap 48`（珊瑚）和 `ring 512 536 290 206 60 270 --gap 48`（主体） |
| 弓形 | `python3 scripts/shapes.py segment CX CY R A D [--fillet 0]` | 圆被一条弦切开后，朝方向 A 的那一侧；D 是弦到圆心的距离（负数时留下大半个圆）。45° 自由切口用 A = −45（留右上，弦是「\」向）或 135（留左下）。Halo 的太阳：`segment 692 372 156 -45 5.7`，弦落在云凸包外 48 |
| 圆角扇形 | `python3 scripts/shapes.py sector CX CY R A0 A1 FILLET` | 饼图切片，三个角都圆角 FILLET（取 24）。Ledgerly 的切片：`sector 557.74 466.26 280 -81 -9 24`，也就是 `sector 500 524 …` 沿平分线 −45° 外移 81.7 后的圆心 |
| 圆角矩形 | `python3 scripts/shapes.py rrect X Y W H R [--grow 0]` | 卡片、书签、字幕条、键帽。R = H ÷ 2 是胶囊。`--grow 48` 出一份外扩 48 的轮廓（宽高各 + 96、圆角 + 48），喂给 `minus` |
| 圆角多边形 | `python3 scripts/shapes.py poly "X1,Y1 X2,Y2 X3,Y3 ..." [--r 24 \| --radii R1,R2,...] [--grow 0]` | 箭头、切角的卡片、台阶这类直边的块。按顺序给角点（顺时针、逆时针都行），每个角一个圆角半径（0 是尖角，凹角写成反向圆弧）。`--grow G` 外扩 G（凸角 R + G，凹角 R − G），喂给 `minus` |
| 播放三角 | `python3 scripts/shapes.py play CX CY H [--r 32] [--grow 0]` | 视频记号：尖朝右的正三角，竖边长 H（≥ 200），质心在 (CX, CY)，三个角圆角 32。用 `minus` 从实形里挖掉，结果是两圈，加 `fill-rule="evenodd"` |
| AI 斜带 | `python3 scripts/shapes.py aiband "PATH" [--chamfer 48] [--width 96] [--gap 48]` | AI 记号：把外轮廓 PATH 的右下角沿 45°「/」切下，打印主体和斜带两条 path。斜带宽 96，外沿离外轮廓最右下点 CHAMFER，主体在斜带前 48 停下。斜带放进 `#accent-shape`，加 `data-accent="band"`。那个角的圆角是 R 时 chamfer ≥ 0.3 R，斜带两端才落在直边上 |
| 切口线 | `python3 scripts/shapes.py cutline CX CY A R0 R1` | 一条 `<line>`，放进 `#cuts`：绕 (CX, CY) 沿方向 A，从半径 R0 到 R1。两端都要伸出外轮廓 |
| 气泡 | `python3 scripts/shapes.py bubble X Y W H R TAIL [left\|right] [--angle 55] [--tip-r 24] [--concave 56] [--grow 0]` | 对话气泡：圆角矩形，左（或右）边往下伸出尾巴，尾尖圆角 TIP_R，和底边之间是半径 CONCAVE 的凹角。R ≤ H ÷ 2，R = H ÷ 2 是胶囊气泡。`--grow G` 把整个轮廓外扩 G：前一个气泡用 `--grow 48` 再出一份，喂给 `minus`，从后一个气泡上减掉 |
| 减去 | `python3 scripts/shapes.py minus "PATH_A" "PATH_B"` | A 减去 B，结果是一条只有直线和圆弧的 path（不用 mask，Icon Composer 层是纯路径）。B 通常是 `bubble` / `rrect --grow 48` 的输出。两条路径只能用 M L H V A Z、正圆弧；A、B 的边不要重合。结果有几圈时会提示加 `fill-rule="evenodd"` |

每个命令都接受 `--k K`：k ≠ 1 时，按最终像素定的数（`--gap`、`--fillet`、FILLET、`--grow`、`--tip-r`、`--concave`、poly 的 `--r` 和 `--radii`、play 的 `--r`、aiband 的 `--chamfer`、`--width` 和 `--gap`）自动 ÷ k；坐标、圆的半径和 play 的 H 仍是源坐标。

常用切口的写法：

| 切口 | 写法 |
|---|---|
| 径向（环段接缝） | 两段都用 `ring … --gap 48`，接缝角相同 |
| 同心（表盘和表圈） | 内块半径 = 环内半径 − 48。Tide：表盘 158 = 206 − 48。冠钮和环顶之间同样隔 48：冠钮底边 y 198，环顶 y 246 |
| 平行（抽出的扇形） | 主体挖掉同一扇形；切片沿平分线外移 48 ÷ sin(θ ÷ 2)（θ 是切片角）。缺口内凹角用 r = 24 + 48 = 72 的反向圆弧，圆心和切片顶点圆角的圆心重合，拐角处切口也是 48。Ledgerly：θ 72°，外移 81.7，即 (+57.7, −57.7) |
| 自由（45° 弦） | 强调色写成 `segment`，弦的方向 45°「\」，弦到主体凸包的距离 48 |
| 水平贯穿（工具记号） | 上下两块：上一块的底边和下一块的顶边都是水平直边，y 相差 48，左右两头都通到剪影外面。两块可以都是主体，也可以有一块是强调色 |
| 「/」斜带（AI 记号） | `aiband` 直接算好，斜带和主体之间全程 48 |
| 镂空三角（视频记号） | `minus "<实形>" "<play …>"`：三角孔就是露出底色的负形，不另画一块 |
| 主体减去「强调色外扩 48」 | 强调色盖在主体上（前面的气泡、书签、字幕条）时，用 `minus` 从主体里减掉强调色外扩 48 的轮廓，见下面的例子。只有气泡、圆角矩形能用 `--grow`；别的形状起稿时用 mask：在 `#cuts` 之外放一份强调色的路径 `<path d="（和 #accent-shape 同一个 d）" fill="#000" stroke="#000" stroke-width="96÷k" stroke-linejoin="round"/>`（描边一半在外，正好外扩 48），交付前再把外扩后的轮廓算出来，用 `minus` 烘焙。不要用 `<use href="#accent-shape">`：被引用元素自己的 `fill="url(#accent)"` 盖过 use 上的 fill，挖出来的是半透明，单色版会透 |

**例：两个气泡（翻译）**。后面的大气泡是主体，前面的胶囊气泡是强调色，两者之间正好一道 48 的切口：

```bash
A=$(python3 scripts/shapes.py bubble 228 380 470 330 72 110 left)              # 后气泡 470 × 330，尾巴朝左下
B=$(python3 scripts/shapes.py bubble 560 210 300 200 100 90 right --grow 48)    # 前气泡外扩 48
python3 scripts/shapes.py minus "$A" "$B"                                       # 主体 = A − B，一条 path
python3 scripts/shapes.py bubble 560 210 300 200 100 90 right                   # 强调色：前气泡，R = H ÷ 2 是胶囊
```

`data-shape="open"`，k = 1，`translate(-22.8 13.9)`（照重心那行的提示改的）：凸包 0.92 × Tide，强调色 22.6 %，切口 48，0 FAIL。前气泡要压在后气泡的一角上，让外扩 48 的轮廓切进 A，`minus` 才会在两者之间留下 48 的切口；只挨着放、不压上去时，两者最近距离不是 48，切口 FAIL。

**用 mask 画切口**（起稿手段）：

```xml
<mask id="cut" maskUnits="userSpaceOnUse" x="-512" y="-512" width="2048" height="2048">
  <rect x="-512" y="-512" width="2048" height="2048" fill="#fff"/>
  <g id="cuts" stroke="#000" stroke-width="48" stroke-linecap="butt" fill="none">   <!-- 48 ÷ k -->
    <line x1="512" y1="354" x2="512" y2="220"/>     <!-- cutline 512 536 -90 182 316：从表盘和表圈之间穿出表圈外 -->
  </g>
</mask>
<g id="body" fill="url(#body)" mask="url(#cut)"> … </g>
```

- 白色留下，黑色挖掉。切口线两端都要伸出外轮廓（贯穿），butt 端头不会多出半圆。
- mask 挂在 `#body` 或 `#accent-shape` 上，不挂在 `#subject` 上。
- 交付前尽量烘焙成路径：mask 会让 Icon Composer 层退回 PNG。

**用 evenodd 挖空**：强调色整块落在主体里面时（主体中间一个孔，孔里是强调色），把主体的外轮廓和「强调色外扩 48」的轮廓写进同一个 `d`，加 `fill-rule="evenodd"`，孔就是真的空的，单色版不会透出来（`minus` 遇到这种情况会输出两圈并提示 evenodd）。环也可以这样写：

```xml
<path fill-rule="evenodd" d="M 222 512 A 290 290 0 1 1 802 512 A 290 290 0 1 1 222 512 Z
                             M 306 512 A 206 206 0 1 1 718 512 A 206 206 0 1 1 306 512 Z"/>
```

其他形状：

| 形状 | 写法 |
|---|---|
| 圆弧 | `M 起点 A r r 0 大弧标志 1 终点`，角度 > 180° 时大弧标志为 1 |
| 胶囊 | `<rect>`，rx 取高的一半；要参与 `minus` 时用 `rrect X Y W H H÷2` 出 path。Tide 冠钮：152 × 84，`<rect x="436" y="114" width="152" height="84" rx="42"/>`；表盘直接写 `<circle cx="512" cy="536" r="158"/>` |
| 云 | 一条闭合 path：左圆 → 凹角圆弧 → 顶部大圆 → 凹角圆弧 → 右圆 → 平底。Halo：左 r 112、顶 r 168、右 r 128，凹角 r 56，底 y 700 |
| 凹角 | 两条边之间插一段反向圆弧（`A r r 0 0 0`），圆心在凹口里，见 `examples/ledgerly.svg` |

## 外观

`render.py --variants` 按下面的配方生成，不用手画；只有生成结果不对时才手改。外观之间不增减、不替换元素，只换颜色（small 版例外，见下）。

| 文件 | 用在哪 | 配方 |
|---|---|---|
| `<name>-1024.png` | 默认外观（石墨），母版本身 | 见 `style.md`「颜色」 |
| `<name>-light.svg/.png` | 浅色场景：网页、营销、浅色主题 app 里的 logo | 底 `#FBFCFE → #E9EBEE`，主体 `#333538 → #1E2022`，去掉辉光 |
| `<name>-dark.svg/.png` | iOS Dark 外观的对照；`rian-app-theme` 的 `preview.py --icon-dark` 用它。交给 Xcode 的是透明底的 `export/ios-1024-dark.png` | 底 `#191C1F → #0E1115`，主体 `#EDEEEF → #BDBFC2`，辉光保留 |
| `<name>-mono.svg/.png` | iOS Tinted / Clear 的来源，Android monochrome | 去掉底和辉光；主体白色 100 %，强调色白色 50 % |
| `<name>-small.svg` | 64 px 及以下（对照图里的 60 / 40 / 29 px、favicon） | `#subject` 加 `feMorphology erode`，半径 8 ÷ k，切口 48 → 64；删掉 `class="detail"`；去掉辉光 |

- **erode 加在 `#subject` 上**，不分别加在 `#body`、`#accent-shape` 上：SVG 里滤镜先于 mask 执行，加在 `#body` 上时 mask 切出的切口不会变宽。半径 12 会把 72 宽的环削到 48（60 px 时只剩约 2.8 px），所以用 8。
- **Tinted 和 Clear** 由系统从 mono 生成。对照图里给近似效果：Tinted 用黄、蓝两种色调各一张，叠在深底上；Clear 用 mono 白 90 % 叠在模糊的浅色壁纸和深色壁纸上各一张。HIG 要求至少一个元素是白色或接近白色，这里主体就是白色。
- **安卓主题图标**由启动器从 monochrome 层生成。对照图里放在一张浅壁纸、一张深壁纸上各一张：从壁纸取种子色相（彩度 ≥ 12 的像素按彩度加权，取色相直方图的峰），按 Material You 的色调近似上色。浅壁纸：底 accent1 色调 90，图形 neutral2 色调 30；深壁纸：底 neutral1 色调 20，图形 accent1 色调 90（色调 = CIE L*，彩度 accent1 36、neutral1 4、neutral2 8）。强调色是图形色 50 % 叠在底上。这是近似，待验证（见 `sources.md`），上架前在开启主题图标的真机启动器上看一遍。

## 平台导出

```bash
python3 scripts/render.py icon.svg -o renders --variants --export
```

写出 `renders/export/`（一次渲染多个 SVG 时是 `renders/export/<name>/`），不需要 Xcode、Android Studio 或在线生成器：

| 文件 | 用在哪 |
|---|---|
| `ios-1024.png` | iOS 26 以下和 App Store：不透明、无圆角，放进 Xcode 的 AppIcon（asset catalog 的 Any） |
| `ios-1024-dark.png` | asset catalog 的 Dark：透明底（Apple 建议深色图标不画底，由系统垫深色底），主体用深色外观的渐变，保留辉光。角上不透明时 render.py 打印 WARNING |
| `ios-1024-tinted.png` | asset catalog 的 Tinted：灰度，不透明黑底，主体白、强调色 50 % 灰，系统按用户选的色调上色 |
| `icon-1024-transparent.png` | 去掉底的主体和强调色，透明背景，给别的用途 |
| `icon-composer/1_body.svg` | Icon Composer 组 1：只有主体，整张 1024 画布，transform 烘焙进坐标，保留主体渐变 |
| `icon-composer/2_accent.svg` | Icon Composer 组 2：只有强调色块，整张 1024 画布 |
| `icon-composer/README.txt` | 在 Icon Composer 里要手动设的东西，见下；不用 Icon Composer 时 asset catalog 三种外观各用哪张 |
| `android/mipmap-anydpi-v26/ic_launcher.xml`、`ic_launcher_round.xml` | 自适应图标（API 26 起），三层：background、foreground、monochrome；两份内容相同，round 给 `android:roundIcon` |
| `android/drawable/ic_launcher_background.xml` | 背景层：108 dp vector，竖直渐变 `#26282B → #191C1F` |
| `android/mipmap-*/ic_launcher_foreground.png`、`ic_launcher_monochrome.png` | 前景和单色层：xxxhdpi 432 px，往下 xxhdpi 324、xhdpi 216、hdpi 162、mdpi 108。monochrome 就是 mono 版（强调色 alpha .5） |
| `android/mipmap-*/ic_launcher.png`、`ic_launcher_round.png` | API 25 及以下的旧图标：48 dp（mdpi 48、hdpi 72、xhdpi 96、xxhdpi 144、xxxhdpi 192 px），自适应图标切成方圆 / 圆形，占 48 dp 里的 44 dp，四周透明 |
| `android-foreground-432.png`、`android-monochrome-432.png` | 同上两层的 432 px 平铺副本，方便预览或手动放进项目 |
| `play-512.png` | Play 商店：512 × 512，32-bit sRGB，满幅方形，不透明，不加圆角和投影（Play 自己加 30 % 圆角和投影），≤ 1024 KB（超过时 render.py 打印 WARNING） |
| `pwa-192.png`、`pwa-512.png`、`pwa-maskable-512.png` | PWA manifest |
| `apple-touch-180.png` | 网页的 apple-touch-icon |
| `favicon-16.png`、`favicon-32.png`、`favicon.ico`、`favicon.svg` | 浏览器标签页：small 版，石墨底切 22 % 圆角，浅色和深色标签栏上都站得住。16 px 只要剪影认得出，切口糊住不算问题（报告 `small_16` 给块数，INFO） |

**Icon Composer**（iOS 26 起的分层图标）：

- 背景不导出，在 Icon Composer 里设：Fill 用渐变，Default `#26282B → #191C1F`，Dark `#191C1F → #0E1115`。层在各外观下不变，深色只换 Background。
- Icon Composer 和 asset catalog 二选一：走 asset catalog（单尺寸 1024）时，Any、Dark、Tinted 分别用 `ios-1024.png`、`ios-1024-dark.png`、`ios-1024-tinted.png`。
- 组 1 是主体，组 2 是强调色。Specular 设 Automatic；组 1 的阴影用 Neutral，组 2 的阴影用 Chromatic，代替平面版里的辉光（Chromatic 以实际版本的选项为准）。
- Mono 标注：主体 White，强调色 50 % 灰。
- 层文件里没有辉光、遮罩、背景、圆角、阴影、半透明。用了 `<mask>` 又烘焙不成纯路径时，改出 1024 PNG 层（`1_body.png`、`2_accent.png`），Icon Composer 也接受。

**Android 和 PWA 的缩放**由 render.py 自动算并套用，母版不用改：

```
r_max         = 主体任一像素到 (512, 512) 的最远距离
android_scale = min(290 ÷ r_max, 0.72)   290 = 66 dp 安全圆（半径 313）往里收 23 px；0.72 是 Tide 的系数（r_max 403）
pwa_scale     = min(409.6 ÷ r_max, 409.6 ÷ Tide 的 r_max)   409.6 = maskable 安全区（中心 80 % 的圆）的半径；Tide 的系数 1.016
```

两处封顶都是为了相对大小和 iOS 一致：只按 r_max 缩的话，紧凑的圆形会被放大（Ledgerly r_max 336 → 安卓 × 0.86、PWA × 1.22），比 Tide 大 20 %。r_max 和两个系数都在指标报告里。manifest 里写 `android:icon="@mipmap/ic_launcher"` 和 `android:roundIcon="@mipmap/ic_launcher_round"`。monochrome 层「系统只按 alpha 通道着色」这一点官方页面没写，待验证。

## 商店 A/B 变体

```bash
python3 scripts/render.py icon.svg -o renders --store-ab
```

写出 `renders/store-ab/`（一次渲染多个 SVG 时是 `renders/store-ab/<name>/`）。颜色和用法见 `style.md`「商店图标的 A/B 变体」：

| 文件 | 内容 |
|---|---|
| `<name>-lighter.svg/.png` | 浅一档的底，别的不动 |
| `<name>-rim.svg/.png` | 默认底，iOS 遮罩里最外 16 px 一圈细亮边 |
| `<name>-tint.svg/.png` | 类别色底（强调色是灰或色板外时不出） |
| `<name>-store-ab.png` | 对比图：默认和变体放在黑、白两种商店底上，120 px 和 60 px，标边缘对比度 |
| `README.txt` | 在产品页优化里怎么用：备用图标打进安装包、和主图标相像（审核规则 2.3.8）、一次只测一项 |

变体的 `.svg` 可以直接交给 render.py 检查：色板按根上的 `data-variant` 查，其余检查和母版一样。传进去的已经是变体时不再出它的变体。

## 渲染

```bash
pip install playwright pillow numpy && playwright install chromium   # 第一次；Python 3.9 及以上
python3 scripts/render.py ICON.svg [more.svg ...] [-o DIR] [--variants] [--export] [--store-ab] [--json] [--tide FILE]
python3 scripts/overview.py examples/tide.svg icon.svg -o renders/compare.png   # 新图标和 Tide 并排，看轻重
python3 scripts/series.py icon.svg [more.svg ...] [--with EXISTING.svg ...] [-o DIR] [--json]   # 系列检查
```

| 参数 | 输出 |
|---|---|
| （总是） | `DIR/<name>-1024.png`、`DIR/<name>-sheet.png`，终端打印指标报告 |
| `--variants` | `<name>-light`、`-dark`、`-mono` 的 `.svg/.png`，`<name>-small.svg` |
| `--export` | `DIR/export/` 下的各平台文件，见「平台导出」 |
| `--store-ab` | `DIR/store-ab/` 下的商店 A/B 变体，见「商店 A/B 变体」 |
| `--json` | `<name>-metrics.json`，内容和终端报告相同 |
| `--tide FILE` | 换一枚尺寸基准（默认 `examples/tide.svg`；找不到或不是石墨风格时用内置的新 Tide 数字：剪影 278 700、凸包 298 700、墨量 212 300、r_max 403） |

- **指标报告**：每项一行，写「名称 [key]」、数值、目标和 PASS / FAIL / INFO，最后一行汇总 FAIL 的 key。有 FAIL 时退出码仍是 0，靠读报告判断（只有 SVG 读不了时退出码是 1）。数字和阈值见 `style.md`「参数」。各项和报告里的 key：

  | 检查项 | key | 级别 |
  |---|---|---|
  | 结构（id、图层和顺序；id 重复；`#background` 是不是一个干净的全画布 rect；旧风格的 `#line`、`#backing`、`split`） | `structure` | 有问题才出现，FAIL |
  | 无描边 | `no_stroke` | FAIL |
  | 色板（报告里叫「颜色」：每个 stop 都在那一对值里、不透明；主体 fill 是 `url(#body-fill)`；单块不带自己的 fill 和 opacity） | `palette` | FAIL |
  | 块数（2–4；5 块要有 `data-pieces-why`；≥ 2 % 凸包的块标了 detail 也 FAIL）；强调色块数 = 1 | `pieces`、`accent_count` | FAIL |
  | 切口宽：相邻每对的最窄处；强调色层到主体层的最近距离单独量，贴边（粘成一块）、不到 48、远于 50 都 FAIL；另查 `data-cut`、`#cuts` 线宽 | `cut` | FAIL |
  | 切口沿边宽（每对切口沿边宽度的 p50 / p90，平行切口约 48 / 52，楔形会张开） | `cut_spread` | INFO |
  | 切口贯穿（没有悬空的槽） | `cut_through` | FAIL |
  | 实形最薄处（开运算 r 34 后每块保留 ≥ 80 %，去掉的部分离保留部分 ≤ 68，细杆、细楔会超；detail 块不查） | `thin` | FAIL |
  | 不重叠 | `overlap` | FAIL |
  | 强调色占比（`pair`、`band` 各有范围） | `accent` | FAIL |
  | 长边 | `long_side` | FAIL |
  | 关键线（报告里叫「形状」：外框比关键线大多少） | `shape` | INFO |
  | 剪影比 / 凸包比（和 Tide 比；实形看剪影，`open` 看凸包，另一项 INFO；FAIL 时给出新的 k） | `silhouette`、`hull` | FAIL |
  | 墨量（实际涂色的面积和 Tide 比，并排看轻重用） | `ink` | INFO |
  | 重心（`open` 横向取质心和外框中心的中点；FAIL 时给出新的 translate） | `centroid` | FAIL |
  | 亮度对比（报告里分「主体对底」「强调色对底」；浅色外观的数字附在后面，INFO） | `contrast_body`、`contrast_accent` | FAIL |
  | 辉光 | `glow` | FAIL |
  | 切口清晰度 | `cut_clarity` | FAIL |
  | 类别记号（强调色是不是这一类的颜色，记号在不在；绿只给健康、财务，斜带只给 AI；没写 `data-category` 时 INFO） | `category` | FAIL |
  | 商店边缘（iOS 遮罩里最外 16 px 对黑、对白的对比度，附 A/B 变体对黑的数字） | `store_edge` | INFO |
  | 安卓主题图标（浅、深壁纸下图形和强调色对主题底的对比度，近似） | `themed` | INFO |
  | 小尺寸：40 px 块数；29 px、16 px 块数 | `small`、`small_29`、`small_16` | FAIL；INFO |
  | 主体渐变跨度、强调色渐变跨度（报告里叫「主体渐变」「强调色渐变」） | `body_gradient`、`gradient` | FAIL |
  | r_max 和 Android / PWA 系数（附 Tide 的 r_max；两个都按 Tide 的系数封顶） | `android`、`pwa` | INFO |

- **对照图**（`<name>-sheet.png`）：iOS 遮罩下的默认外观和读数（第一行是类别和强调色）；180 / 120 / 80 / 60 / 40 / 29 px（60 及以下用 small 版）；和 Tide 同尺寸并排；浅色、深色；Tinted 黄、Tinted 蓝；Clear 浅壁纸、Clear 深壁纸；Android 圆形遮罩、方圆遮罩、主题图标（mono 层按浅、深两张壁纸取的色调上色，放在壁纸上）、圆形 48 px、mono 层。
- **系列检查**（`series.py`）：新图标和已有图标（`--with`，默认 `examples/*.svg`）一起渲染，写 `DIR/series-sheet.png`（加 `--json` 另写 `series.json`），终端打印强调色登记、配对分数和扎堆。规则和阈值见 `style.md`「系列检查」。
- 用 Chromium 渲染，和浏览器一致。机器上已有 Chromium 时设 `CHROMIUM_PATH` 跳过下载。
