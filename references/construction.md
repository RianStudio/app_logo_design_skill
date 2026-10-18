# SVG 构造与平台规格

这里只讲怎么搭、怎么导出。所有数字都在 `style.md`。

## 图层结构

`assets/template.svg` 是用 Tide 写好的模板，结构如下（从下到上）：

```
<svg viewBox="0 0 1024 1024">   根只写 viewBox，不写宽高
<defs>
  #bg            linearGradient：底，y 0 → 1024
  #body-fill     linearGradient：线，跨度 600 ÷ k（不叫 #body，那是线稿组的 id）
  #accent        linearGradient：强调色「浅 → 主」，跨度 480 ÷ k
  #glow-blur     可选 filter：辉光
#background      一个 rect：0 0 1024 1024，fill url(#bg)，里面不放东西
#subject         transform；data-shape；data-category
  #glow          可选：<use href="#accent-shape" filter="url(#glow-blur)"/>，第一个子元素
  #body          <g fill="none" stroke="url(#body-fill)" stroke-width="60÷k" stroke-linecap="round" stroke-linejoin="round">：所有线的中线
  #accent-shape  一个元素（path、circle 或 g），fill url(#accent)，不描边
```

`render.py --store-ab` 写出的商店变体在根上加 `data-variant`，细亮边变体另在 `#background` 和 `#subject` 之间加一个 `<path id="rim">`；手画的母版不写这些。

三个渐变都写 `gradientUnits="userSpaceOnUse"`，竖直（x1 = x2 = 0）。线的渐变挂在 stroke 上，userSpaceOnUse 让所有线共用同一束顶光。辉光 filter 照抄：

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
| 根 | `data-variant="lighter｜rim｜tint"`，细亮边另有 `<path id="rim" fill="url(#rim-fill)">` | 只出现在 `--store-ab` 写出的商店变体上。手画的母版不写 |
| `<defs>` | `#bg`、`#body-fill`、`#accent` 三个 `linearGradient`，都用 `userSpaceOnUse`；每个只有两个 stop，取色板里那一对值；可选 `#glow-blur` filter | 读色板，算渐变跨度。整个文件 id 不能重复 |
| `#background` | 一个 `rect`，x = y = 0，宽高 1024，fill `url(#bg)`；没有子元素、没有 transform | 换外观时改它 |
| `#subject` | `data-shape="circle｜square｜tall｜wide｜open"`、`transform="translate(512 512) scale(k) translate(-512 -512) translate(tx ty)"` | 选尺寸检查（封闭的线稿看剪影，`open` 看凸包）；k 用来换算源坐标 |
| `#subject` | `data-category="tools｜image｜video｜ai｜health｜finance"`，不属于这些类就不写 | 按类别查强调色和类别记号 |
| `#glow` | 可选，`#subject` 的第一个子元素，`<use href="#accent-shape" filter="url(#glow-blur)"/>` | 测量时隐藏 |
| `#body` | `<g fill="none" stroke="url(#body-fill)" stroke-width="60÷k" stroke-linecap="round" stroke-linejoin="round">`，里面是 `path`、`circle`、`rect`、`line`、`polyline`、`polygon`；单个元素不写自己的 fill、stroke、stroke-width、opacity | 线宽、圆头圆角、线间净空、夹缝、线对底 |
| `#accent-shape` | 一个元素，fill `url(#accent)`，不写 stroke 和 opacity | 强调色占比、到线的净空 |
| `#accent-shape` | `data-accent="band"` | 强调色是 AI 斜带（`shapes.py aiband` 打印的那条）：占比按 6–14 % 查，另查方向、带宽和位置；只给 `data-category="ai"` |

旧风格的标记都不再使用：实形风格的 `data-cut`、`data-pieces-why`、`class="detail"`、`data-accent="pair"`、`#cut` mask 和 `#cuts`；更早的 `#backing`、`#line`、`lift`、`class="on-accent"`、`data-part`。出现时报结构 FAIL。

## 要点

- **缩放**：直接按最终像素画，k = 1（三枚示例都是），transform 里只调 translate。剪影比 / 凸包比不在范围里时，报告会写「k 改为 …」；改了 k，`stroke-width` 写 60 ÷ k，圆角、强调色用 `shapes.py … --k K` 重出，渐变跨度、辉光 stdDeviation 也要 ÷ k。重心不对时报告会写「translate 改为 (tx ty)」，照抄。
- **画中线**：坐标是线的中线，线向两边各占 30。关键线、净空都量线的外沿：两段线的中线相距 ≥ 120 才有 60 的净空；强调色的边到线的中线 ≥ 90。
- **断开处**：一段线绕开强调色或另一段线时，在离它 60 + 30 的地方停下（圆头会再伸出 30），不画半截拐角。
- **接头**：一段线的端点落在另一段线的中线上（T 字接头、山脊接到框边），圆头藏在线里，连成一段。夹角 ≥ 45°，否则夹缝会糊。
- **渐变坐标**（源坐标）：y1、y2 = 中心 ∓ 300 ÷ k（线）或 ∓ 240 ÷ k（强调色），中心是这一层上下范围（线含线宽）的中点。Tide：线 y 136–830，写 183 / 783；扇形 y 394–676，写 295 / 775。报告的「线渐变」「强调色渐变」两行会直接给出该写的 y1、y2。
- **能烘焙的写法**：`#body` 和 `#accent-shape` 里只用 `path`、`circle`、`ellipse`、`rect`、`line`、`polyline`、`polygon`，`--export` 才能把 transform 烘焙进 Icon Composer 层的坐标。出现 `mask`、`clip-path`、`filter`、`<use>` 或非等比缩放时，那一层只出 PNG。
- 注释里不能出现连续两个连字符，否则 SVG 解析失败、渲染出来是空白（`shapes.py` 的参数写进注释时去掉 `--`）。不用 `<text>`，不嵌位图。坐标取整齐的数，在注释里写出几何关系（圆心、半径、角度、净空）。

## 几何速查

画布中心 `(512, 512)`。从 3 点钟方向顺时针 θ 角、半径 r 的点：`(cx + r·cosθ, cy + r·sinθ)`；12 点是 −90°。

`scripts/shapes.py` 打印 SVG 路径（不带参数运行时打印完整用法）。前五个打印**线的中线**，放进 `#body`；后面的打印**填色的轮廓**，给强调色：

| 形状 | 命令 | 用在哪 |
|---|---|---|
| 圆弧 | `arc CX CY R A0 A1` | 开口的圆弧：循环箭头、表盘的一段。整圆直接写 `<circle>` |
| 圆角矩形 | `rrect X Y W H R [--grow 0]` | 卡片、页面、屏幕、框；R = H ÷ 2 是胶囊。`--grow G` 出一份外扩 G 的轮廓，喂给 `minus` |
| 气泡 | `bubble X Y W H R TAIL [left\|right] [--angle 55] [--tip-r 24] [--concave 56]` | 对话气泡 |
| 圆角多边形 | `poly "X1,Y1 X2,Y2 ..." [--r 24 \| --radii R1,R2,...] [--open] [--grow 0]` | 切角的页面、台阶、捏扁的卡片、山脊。`--open` 画折线：首尾是线的两端（圆头），只有中间的角倒圆 |
| 播放三角 | `play CX CY H [--r 24]` | 视频记号：尖朝右的正三角，竖边长 H（≥ 240 ÷ k），质心在 (CX, CY)。线画的三角里的孔实测约 H ÷ 1.7 高 |
| 胶囊 | `capsule X1 Y1 X2 Y2 W` | 强调色：两端圆心之间、宽 W 的胶囊。扫描光束、剪辑手柄 |
| AI 斜带 | `aiband X1 Y1 X2 Y2 [--stroke 60] [--gap 60] [--width 80] [--inset 0]` | AI 记号：(X1, Y1) → (X2, Y2) 是外轮廓右下角那道 45° 斜角的中线（左下到右上）。打印外侧那条斜带：宽 80，离线的外沿 60，`--inset` 两头各缩进 |
| 圆角扇形 | `sector CX CY R A0 A1 FILLET` | 饼图切片、计时的进度，三个角都圆角 FILLET（取 24） |
| 环段 | `ring CX CY R_OUT R_IN A0 A1 [--fillet 0]` | 填色的进度环、循环箭头的箭身 |
| 弓形 | `segment CX CY R A D [--fillet 0]` | 圆被一条弦切开后，朝方向 A 的那一侧 |
| 减去 | `minus "PATH_A" "PATH_B"` | A 减去 B（只有直线和圆弧）：强调色被线挡住的地方，减掉「那条线的形状外扩 30 + 60」。Halo 的太阳 = 圆减去两个外扩 90 的云团 |

每个命令都接受 `--k K`：k ≠ 1 时，按最终像素定的数（圆角、`--grow`、FILLET、capsule 的 W、aiband 的四个参数）自动 ÷ k；坐标、圆的半径和 play 的 H 仍是源坐标。

常用写法：

| 要画的 | 写法 |
|---|---|
| 计时进度（Tide） | 表圈 `<circle r="250">`，冠钮和柄一条 path（`M 452 166 H 572 M 512 166 V 300`，柄的端点落在表圈中线上）；扇形 `sector 512 550 158 -90 60 24`：表圈内沿 220，220 − 158 = 62 |
| 抽出的切片（Ledgerly） | 饼图一条 path：圆心 → 弧起点，288° 大弧，回圆心；切片 `sector` 沿平分线外移 d，直边离半径线 d · sin(θ ÷ 2) ≥ 90 |
| 太阳挨着云（Halo） | 云是 Lucide 的 cloud 放大（一大一小两个圆弧接平底）；太阳 = 圆 `minus` 两个外扩 90 的云团圆 |
| 工具横线（Scan） | 页面拆成上下两段线，在光束中线 ± (40 + 60 + 30) 处停下；光束 `capsule`，两头伸出页面 |
| 视频三角（Trim、Loop） | `play` 单独一段线，离别的线 ≥ 60；强调色另画（手柄 `capsule`，箭头 `poly`） |
| AI 斜角（Ask、Upscale） | 外轮廓用 `poly`，右下角两点连成 45° 斜角；`aiband` 用这两点的坐标 |
| 照片和太阳（Squeeze、Cutout） | 太阳在框里时离框 ≥ 60；压在框角上时，框的线从太阳两侧各 90 + 半径之外开始画 |

## 外观

`render.py --variants` 按下面的配方生成，不用手画；只有生成结果不对时才手改。外观之间不增减、不替换元素，只换颜色（small 版例外，见下）。

| 文件 | 用在哪 | 配方 |
|---|---|---|
| `<name>-1024.png` | 默认外观（石墨），母版本身 | 见 `style.md`「颜色」 |
| `<name>-light.svg/.png` | 浅色场景：网页、营销、浅色主题 app 里的 logo | 底 `#FBFCFE → #E9EBEE`，线 `#333538 → #1E2022`，去掉辉光 |
| `<name>-dark.svg/.png` | iOS Dark 外观的对照；`rian-app-theme` 的 `preview.py --icon-dark` 用它。交给 Xcode 的是透明底的 `export/ios-1024-dark.png` | 底 `#191C1F → #0E1115`，线 `#EDEEEF → #BDBFC2`，辉光保留 |
| `<name>-mono.svg/.png` | iOS Tinted / Clear 的来源，Android monochrome | 去掉底和辉光；线白色 100 %，强调色白色 50 % |
| `<name>-small.svg` | 64 px 及以下（对照图里的 60 / 40 / 29 px、favicon） | `#body` 的 stroke-width 改成 76 ÷ k（29 px 约 2.2 px），去掉辉光；净空 60 → 44，40 px 下还分得开 |
| `<name>-mark.svg/.png` | app 里的品牌插图，深色模式：`rian-app-theme` 的引导、付费墙、空状态、启动页把它放在石墨品牌面板上（`preview.py --mark`） | `#subject` 一组，去掉底和辉光，**平涂**：线全是 `#E6E8EB`（亮线），强调色是它的「主」一个色，没有渐变。透明，裁到画出来的部分外加 8。只能整体缩放，线宽跟着缩，始终是 60 / 1024 |
| `<name>-mark-light.svg/.png` | 同上，浅色模式：放在浅色的品牌面板上 | 同 `-mark`，只是线换成 `#2A2C2F`（深线，浅色外观的线），强调色不变；外框和 `-mark` 一样大 |

- **mark 是平的**：界面的 Lucide 图标是一种颜色的线，插图跟它一样，所以 mark 不带图标的顶光渐变和辉光；渐变只留在 app 图标本身。后缀和外观同名：`-mark` 配默认（石墨）的深色面板，`-mark-light` 配浅色面板。两种线色和 `rian-app-theme` 的 `brand-line` 同值（`render.py` 的 `MARK_LINE`）。
- **small 版只加粗线**：线宽写在 `#body` 上，所有线一起变；强调色不变。加粗到 76 而不是更多：净空还剩 44，40 px 时约 1.7 px。
- **Tinted 和 Clear** 由系统从 mono 生成。对照图里给近似效果：Tinted 用黄、蓝两种色调各一张，叠在深底上；Clear 用 mono 白 90 % 叠在模糊的浅色壁纸和深色壁纸上各一张。HIG 要求至少一个元素是白色或接近白色，这里线就是白色。
- **安卓主题图标**由启动器从 monochrome 层生成，用哪一对色调看系统的浅色、深色主题（Launcher3 `ThemedIconDrawable.getColors`），色相来自壁纸。对照图里浅色主题放在浅壁纸上、深色主题放在深壁纸上各一张：从壁纸取种子色相（彩度 ≥ 12 的像素按彩度加权，取色相直方图的峰），按 Material You 的色调近似上色。浅色主题：底 accent1 色调 90，图形 neutral2 色调 30；深色主题：底 neutral1 色调 20，图形 accent1 色调 90（色调 = CIE L*，彩度 accent1 36、neutral1 4、neutral2 8）。强调色是图形色 50 % 叠在底上。这是近似，待验证（见 `sources.md`），上架前在开启主题图标的真机启动器上看一遍。

## 平台导出

```bash
python3 scripts/render.py icon.svg -o renders --variants --export
```

写出 `renders/export/`（一次渲染多个 SVG 时是 `renders/export/<name>/`），不需要 Xcode、Android Studio 或在线生成器：

| 文件 | 用在哪 |
|---|---|
| `ios-1024.png` | iOS 26 以下和 App Store：不透明、无圆角，放进 Xcode 的 AppIcon（asset catalog 的 Any） |
| `ios-1024-dark.png` | asset catalog 的 Dark：透明底（Apple 建议深色图标不画底，由系统垫深色底），线用深色外观的渐变，保留辉光。角上不透明时 render.py 打印 WARNING |
| `ios-1024-tinted.png` | asset catalog 的 Tinted：灰度，不透明黑底，线白、强调色 50 % 灰，系统按用户选的色调上色 |
| `icon-1024-transparent.png` | 去掉底的线和强调色，透明背景，给别的用途 |
| `icon-composer/1_body.svg`、`1_body.png` | Icon Composer 组 1：只有线，整张 1024 画布；SVG 是 60 px 圆头线，transform 烘焙进坐标，保留线的渐变 |
| `icon-composer/2_accent.svg`、`2_accent.png` | Icon Composer 组 2：只有强调色，整张 1024 画布 |
| `icon-composer/README.txt` | 在 Icon Composer 里要手动设的东西，见下；不用 Icon Composer 时 asset catalog 三种外观各用哪张 |
| `android/mipmap-anydpi-v26/ic_launcher.xml`、`ic_launcher_round.xml` | 自适应图标（API 26 起），三层：background、foreground、monochrome；两份内容相同，round 给 `android:roundIcon` |
| `android/drawable/ic_launcher_background.xml` | 背景层：108 dp vector，竖直渐变 `#26282B → #191C1F` |
| `android/mipmap-*/ic_launcher_foreground.png`、`ic_launcher_monochrome.png` | 前景和单色层：xxxhdpi 432 px，往下 xxhdpi 324、xhdpi 216、hdpi 162、mdpi 108。monochrome 就是 mono 版（强调色 alpha .5） |
| `android/mipmap-*/ic_launcher.png`、`ic_launcher_round.png` | API 25 及以下的旧图标：48 dp（mdpi 48、hdpi 72、xhdpi 96、xxhdpi 144、xxxhdpi 192 px），自适应图标切成方圆 / 圆形，占 48 dp 里的 44 dp，四周透明 |
| `android-foreground-432.png`、`android-monochrome-432.png` | 同上两层的 432 px 平铺副本，方便预览或手动放进项目 |
| `play-512.png` | Play 商店：512 × 512，32-bit sRGB，满幅方形，不透明，不加圆角和投影（Play 自己加 30 % 圆角和投影），≤ 1024 KB（超过时 render.py 打印 WARNING） |
| `pwa-192.png`、`pwa-512.png`、`pwa-maskable-512.png` | PWA manifest |
| `apple-touch-180.png` | 网页的 apple-touch-icon |
| `favicon-16.png`、`favicon-32.png`、`favicon.ico`、`favicon.svg` | 浏览器标签页：small 版，石墨底切 22 % 圆角，浅色和深色标签栏上都站得住。16 px 只要剪影认得出，线糊在一起不算问题（报告 `small_16` 给形数和孔数，INFO） |

**Icon Composer**（iOS 26 起的分层图标）：

- 背景不导出，在 Icon Composer 里设：Fill 用渐变，Default `#26282B → #191C1F`，Dark `#191C1F → #0E1115`。层在各外观下不变，深色只换 Background。
- Icon Composer 和 asset catalog 二选一：走 asset catalog（单尺寸 1024）时，Any、Dark、Tinted 分别用 `ios-1024.png`、`ios-1024-dark.png`、`ios-1024-tinted.png`。
- 组 1 是线，组 2 是强调色。Specular 设 Automatic；组 1 的阴影用 Neutral，组 2 的阴影用 Chromatic，代替平面版里的辉光（Chromatic 以实际版本的选项为准）。
- Mono 标注：线 White，强调色 50 % 灰。
- 层文件里没有辉光、遮罩、背景、圆角、阴影、半透明。每层都出 1024 PNG；能烘焙成纯路径时另出 SVG（线层是 `fill="none"` 的 60 px 圆头描边）。Icon Composer 两种都接受，SVG 放大不糊。

**Android 和 PWA 的缩放**由 render.py 自动算并套用，母版不用改：

```
r_max         = 线或强调色任一像素到 (512, 512) 的最远距离
android_scale = min(290 ÷ r_max, 290 ÷ Tide 的 r_max)   290 = 66 dp 安全圆（半径 313）往里收 23 px；Tide 的系数 0.723（r_max 401）
pwa_scale     = min(409.6 ÷ r_max, 409.6 ÷ Tide 的 r_max)   409.6 = maskable 安全区（中心 80 % 的圆）的半径；Tide 的系数 1.022
```

两处封顶都是为了相对大小和 iOS 一致：只按 r_max 缩的话，紧凑的图标会被放大，比 Tide 大一圈。r_max 和两个系数都在指标报告里。manifest 里写 `android:icon="@mipmap/ic_launcher"` 和 `android:roundIcon="@mipmap/ic_launcher_round"`。monochrome 层「系统只按 alpha 通道着色」这一点官方页面没写，待验证。

## 商店 A/B 变体

```bash
python3 scripts/render.py icon.svg -o renders --store-ab
```

写出 `renders/store-ab/`（一次渲染多个 SVG 时是 `renders/store-ab/<name>/`）。颜色和用法见 `style.md`「商店图标的 A/B 变体」：

| 文件 | 内容 |
|---|---|
| `<name>-lighter.svg/.png` | 浅一档的底，别的不动 |
| `<name>-rim.svg/.png` | 默认底，Apple 图标外形里最外 16 px 一圈细亮边 |
| `<name>-tint.svg/.png` | 类别色底，四类以外的 app 叫强调色底（强调色是灰或色板外时不出） |
| `<name>-store-ab.png` | 对比图：默认和变体放在黑、白两种商店底上，120 px 和 60 px，标边缘对比度 |
| `README.txt` | 在产品页优化里怎么用：备用图标打进安装包、和主图标相像（审核规则 2.3.8）、一次只测一项 |

变体的 `.svg` 可以直接交给 render.py 检查：色板按根上的 `data-variant` 查，其余检查和母版一样，报告多一行「商店变体」（INFO）。传进去的已经是变体时不再出它的变体，也不出 `--export`：平台文件只从母版出。

细亮边贴着 Apple 图标外形的近似（`render.py` 的 `ios_path`：圆角 22.37 % 的圆角正方形，60 % 平滑，和 Figma 的 iOS 预设同一种画法）往里 16 px。对照图里的 iOS 遮罩、商店边缘一行量的那一圈也用它。

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
| `--variants` | `<name>-light`、`-dark`、`-mono`、`-mark`、`-mark-light` 的 `.svg/.png`，`<name>-small.svg` |
| `--export` | `DIR/export/` 下的各平台文件，见「平台导出」 |
| `--store-ab` | `DIR/store-ab/` 下的商店 A/B 变体，见「商店 A/B 变体」 |
| `--json` | `<name>-metrics.json`，内容和终端报告相同 |
| `--tide FILE` | 换一枚尺寸基准（默认 `examples/tide.svg`；找不到或不是石墨线稿时用内置的 Tide 数字：剪影 261 400、凸包 286 500、墨量 141 000、r_max 401） |

- **指标报告**：每项一行，写「名称 [key]」、数值、目标和 PASS / FAIL / INFO，最后一行汇总 FAIL 的 key。有 FAIL 时退出码仍是 0，靠读报告判断（只有 SVG 读不了时退出码是 1）。数字和阈值见 `style.md`「参数」。各项和报告里的 key：

  | 检查项 | key | 级别 |
  |---|---|---|
  | 结构（id、图层和顺序；id 重复；`#background` 是不是一个干净的全画布 rect；旧风格的 `#cut`、`data-cut`、`detail`、`#line`、`#backing`） | `structure` | 有问题才出现，FAIL |
  | 线宽（60 ± 1，一种线宽，圆头圆角；#body 不填色；强调色不描边；两层之外没有图形） | `stroke` | FAIL |
  | 颜色（每个 stop 都在那一对值里、不透明；线的 stroke 是 `url(#body-fill)`；单个元素不带自己的颜色、线宽和透明度） | `palette` | FAIL |
  | 线条段数（1–4）；强调色块数 = 1 | `parts`、`accent_count` | FAIL |
  | 线间净空（分开的线之间 ≥ 60） | `line_gap` | FAIL |
  | 线间夹缝（半径 30 闭运算后多出的一块 ≤ 3000 px²） | `pinch` | FAIL |
  | 强调色到线（≥ 60，不压线） | `accent_gap` | FAIL |
  | 强调色占比（`band` 有自己的范围） | `accent` | FAIL |
  | 长边 | `long_side` | FAIL |
  | 形状（外框比关键线大多少） | `shape` | INFO |
  | 剪影面积 / 凸包面积（和 Tide 比；封闭的线稿看剪影，`open` 看凸包，另一项 INFO；FAIL 时给出新的 k） | `silhouette`、`hull` | FAIL |
  | 墨量（实际上色的面积和 Tide 比） | `ink` | INFO |
  | 重心（FAIL 时给出新的 translate） | `centroid` | FAIL |
  | 线对底、强调色对底（浅色外观的数字附在后面，INFO） | `contrast_body`、`contrast_accent` | FAIL |
  | 辉光 | `glow` | FAIL |
  | 类别记号（强调色是不是这一类的颜色，记号在不在；绿只给健康、财务，斜带只给 AI；没写 `data-category` 时 INFO） | `category` | FAIL |
  | 商店边缘 | `store_edge` | INFO |
  | 安卓主题图标 | `themed` | INFO |
  | 商店变体（文件根上有 `data-variant`） | `variant` | 有才出现，INFO |
  | 小尺寸：small 版 40 px 的形数和孔数和 1024 px 一样；29 px、16 px | `small`、`small_29`、`small_16` | FAIL；INFO |
  | 线渐变、强调色渐变 | `body_gradient`、`gradient` | FAIL |
  | r_max 和 Android / PWA 系数（都按 Tide 的系数封顶） | `android`、`pwa` | INFO |

- **对照图**（`<name>-sheet.png`）：iOS 遮罩下的默认外观和读数（第一行是类别和强调色）；180 / 120 / 80 / 60 / 40 / 29 px（60 及以下用 small 版）；和 Tide 同尺寸并排；浅色、深色；Tinted 黄、Tinted 蓝；Clear 浅壁纸、Clear 深壁纸；Android 圆形遮罩、方圆遮罩、主题图标（mono 层按浅色、深色主题的色调上色，色相取自壁纸，放在壁纸上）、圆形 48 px、mono 层。
- **系列检查**（`series.py`）：新图标和已有图标（`--with`；不写时用 `examples/*.svg` 作参考，只算配对、不算扎堆）一起渲染，写 `DIR/series-sheet.png`（加 `--json` 另写 `series.json`），终端打印强调色登记、配对分数、扎堆和占了记号的角。规则和阈值见 `style.md`「系列检查」。
- 用 Chromium 渲染，和浏览器一致。机器上已有 Chromium 时设 `CHROMIUM_PATH` 跳过下载。
