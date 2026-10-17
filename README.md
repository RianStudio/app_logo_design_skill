# rian-app-icon

一个 Claude skill：把一句产品描述变成一枚可以上架的 app 图标（1024 SVG 母版，默认、浅色、深色、单色四种外观，Icon Composer 分层，评审对照图，Android、Play、PWA、favicon 导出文件，App Store A/B 变体）。

风格只有一种：**石墨**。深石墨底上放一块亮色实形，用 48 px 的负形切口分出结构，强调色只点一处。

- **实形加切口**：主体是 2–4 块实心几何形（一般 3–4 块；圆、圆角矩形、胶囊、扇形、环段、圆角多边形），相邻两块之间是一道最窄处 48 px 的负形切口，整个图标没有一条描边。切口学 Linear 的标志；变成单色、缩到 29 px，结构仍然看得出来。
- **石墨底和顶光**：底是 `#26282B → #191C1F` 的竖直渐变，主体是 `#F8F9FB → #C6C8CB` 的顶光渐变。不画投影和高光，iOS 26 的 Liquid Glass 由系统自己加。
- **一块强调色**：六色之一，单独一块实形，占 10–25 %（一对同类物体里较小的那个当强调色时到 33 %），和主体隔一道切口，可以带一层极淡的辉光。
- **类别记号**：工具（蓝）是一道贯穿的水平切口，图片（黄）是左上角的圆太阳，视频（珊瑚）是镂空的播放三角，AI（紫）是右下角的「/」斜带；绿只给健康和财务。用户靠图形认类别，不靠颜色。
- **平台规格**：1024 全出血母版和 Icon Composer 两层学 Apple；自适应图标三层、主题图标和 Play 512 学 Google。

![示例](examples/renders/overview.png)

| 示例 | 强调色 | 画了什么 |
|---|---|---|
| Tide 专注计时 | 珊瑚 | 秒表：实心表盘、两段表圈（珊瑚段是 25 分钟的进度）、冠钮 |
| Halo 天气 | 黄 | 云，右上方的太阳被一条 45° 的切口切成弓形 |
| Ledgerly 记账（财务） | 绿 | 饼图，沿右上方抽出一块 72° 的切片 |

## 姊妹 skill：App UI 主题

用同一套强调色生成整套 UI 主题（石墨中性色阶梯、标准和高对比两套 token、字号、圆角、动效，导出 CSS、SwiftUI、Compose、Tailwind），在单独的仓库：[RianStudio/app_ui_design_skill](https://github.com/RianStudio/app_ui_design_skill)。图标的强调色是蓝、绿、紫时，界面主色跟图标同色；珊瑚、黄、灰只留在图标里，界面用蓝。

## 安装

**Claude Code**：把整个仓库复制到 `~/.claude/skills/rian-app-icon/`（个人）或项目里的 `.claude/skills/rian-app-icon/`。

**Claude.ai / Claude 桌面版**：把仓库打成 zip，在 Settings → Capabilities → Skills 上传。

渲染脚本需要 Python 3.9 及以上，一次性安装：

```bash
pip install playwright pillow numpy && playwright install chromium
```

## 用法

直接对 Claude 说，例如：

> 给我做一个 app 图标：「Tide」，把待办拆成 25 分钟专注块的计时器。

Claude 会读懂产品、自己选定隐喻和配色、从模板画 SVG、渲染并按指标自检（最多两轮），然后交付四种外观和 Icon Composer 分层。

也可以自己渲染：

```bash
python3 scripts/render.py icon.svg -o renders                       # 1024 PNG + 对照图 + 指标报告
python3 scripts/render.py icon.svg -o renders --variants            # 另出浅色、深色、单色和 small 版
python3 scripts/render.py icon.svg -o renders --variants --export   # 另出 Icon Composer、Android、Play、PWA、favicon 文件
python3 scripts/render.py icon.svg -o renders --store-ab           # 另出商店 A/B 变体（浅一档底、细亮边、类别色底）和对比图
python3 scripts/render.py icon.svg -o renders --json                # 指标另存为 JSON
python3 scripts/overview.py examples/tide.svg icon.svg -o renders/compare.png   # 新图标和 Tide 并排，看轻重
python3 scripts/series.py icon.svg --with a.svg b.svg -o renders    # 系列检查：和已有图标一起出 40 / 29 px 对照，标出像的配对和扎堆的强调色
python3 scripts/shapes.py                                           # 环段、弓形、扇形、圆角矩形、多边形、播放三角、AI 斜带、切口线、气泡、路径相减的用法
```

指标报告逐条打印 PASS / FAIL / INFO：块数、切口宽（每对最窄处，加沿边宽的 p50 / p90）、实形最薄处、不重叠、强调色占比、尺寸、墨量和重心（和 Tide 比，不对时直接给出该改的 k 和 translate）、渐变跨度、无描边、色板、亮度对比、辉光、切口清晰度、类别记号、商店边缘、安卓主题图标、小尺寸（40 / 29 / 16 px）、Android / PWA 缩放系数。

## 结构

```
SKILL.md                    工作流程（入口）、示例索引、无字母品类的画法
references/style.md         风格原则、切口规则、全部数字和测量口径、配色、类别记号、商店 A/B 变体、系列检查、禁忌、验收清单
references/construction.md  图层结构、属性和类、几何速查（mask 切口、evenodd 挖空、shapes.py）、外观配方、平台导出、商店 A/B 变体、渲染参数
references/sources.md       一手来源与致谢
assets/template.svg         图标模板（用 Tide 写成）：只改 TODO 的地方
scripts/render.py           SVG → 1024 PNG、对照图、指标报告；外观、Icon Composer 分层、平台导出和商店 A/B 变体（Chromium 渲染）
scripts/shapes.py           环段（带接缝切口）、弓形、圆角扇形、圆角矩形、圆角多边形、播放三角、AI 斜带、切口线、对话气泡的路径，和路径相减（minus：主体减去强调色外扩 48）
scripts/series.py           系列检查：新图标和已有图标的 40 / 29 px 对照表、配对相似分数、强调色位置登记
scripts/overview.py         三枚示例并排的总览图（README 顶部那张）：深底一行，浅色外观一行
examples/                   Tide、Halo、Ledgerly 三枚示例；renders/ 里是每枚的 1024 母版、对照图（-sheet.png）和三枚并排的 overview.png
```

## 许可

MIT
