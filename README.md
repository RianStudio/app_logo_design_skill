# rian-app-icon

一个 Claude skill：把一句产品描述变成一枚可以上架的 app 图标（1024 SVG 母版，浅色、深色、着色三种外观，评审对照图，各平台导出文件）。

风格只有一种：**极简线条**。一笔粗细统一的墨线画出物件，一块强调色点出重点，圆头圆角；线条和留白学 Notion，几何和关键线学 Google 产品图标，柔和渐变和轻微立体学 Apple。每枚图标都是同样的四层：很淡的中性色背景、挡住内投影的衬底、一个强调色块、一组墨线（没有封闭的空白时省掉衬底）。

![示例](examples/renders/overview.png)

| 示例 | 强调色 | 画了什么 |
|---|---|---|
| Tide 专注计时 | 珊瑚 | 秒表，25 分钟的进度填色 |
| Halo 天气 | 黄 | 太阳和云，云挡住太阳的一角 |
| Margin 笔记 | 黄 | 一页笔记，左侧一条高亮色边 |
| QR Code Scanner | 蓝 | 取景框加扫描线 |
| Image Compressor | 蓝 | 相框和两侧向内收的箭头 |
| Ledgerly 记账 | 绿 | 饼图，抽出一块填色的切片 |
| Streak 习惯打卡 | 绿 | 日历页上一枚打勾的圆形徽章（最初由一个只读过 skill 的新 Claude 画出，用来验证 skill；后来按评审调小了尺寸、加大了留白） |

## 姊妹 skill：App UI 主题

用同一套强调色生成整套 UI 主题（浅色和深色 token、字号、圆角、毛玻璃材质，导出 CSS、SwiftUI、Compose、Tailwind），在单独的仓库：[RianStudio/app_ui_design_skill](https://github.com/RianStudio/app_ui_design_skill)。图标的强调色是蓝、绿、紫时，界面主色跟图标同色；其余用蓝。

## 安装

**Claude Code**：把整个仓库复制到 `~/.claude/skills/rian-app-icon/`（个人）或项目里的 `.claude/skills/rian-app-icon/`。

**Claude.ai / Claude 桌面版**：把仓库打成 zip，在 Settings → Capabilities → Skills 上传。

渲染脚本需要一次性安装：

```bash
pip install playwright pillow numpy && playwright install chromium
```

## 用法

直接对 Claude 说，例如：

> 给我做一个 app 图标：「Tide」，把待办拆成 25 分钟专注块的计时器。

Claude 会读懂产品、自己选定隐喻和配色、从模板画 SVG、渲染并按指标自检（最多两轮），然后交付浅色、深色、着色三种外观。

也可以自己渲染：

```bash
python3 scripts/render.py icon.svg -o renders              # 1024 PNG + 对照图 + 指标报告
python3 scripts/render.py icon.svg -o renders --variants   # 另出深色版和着色版
python3 scripts/render.py icon.svg -o renders --export     # 另出 iOS、Android、PWA、favicon 文件
python3 scripts/render.py icon.svg -o renders --json       # 指标另存为 JSON
python3 scripts/overview.py examples/tide.svg icon.svg -o renders/compare.png   # 新图标和 Tide 并排，看轻重
```

## 结构

```
SKILL.md                    工作流程（入口）、示例索引
references/style.md         风格原则、全部数字和测量口径、配色、禁忌、验收清单
references/construction.md  图层结构、属性和类、几何速查、变体配方、平台导出、渲染参数
references/sources.md       参考来源与致谢
assets/template.svg         图标模板：只改 TODO 的地方
scripts/render.py           SVG → 1024 PNG、对照图、指标报告；变体和平台导出（Chromium 渲染）
scripts/shapes.py           圆角扇形、对话气泡等需要做圆角的路径
scripts/overview.py         七枚示例并排的总览图（README 顶部那张），--dark 出深色版
examples/                   七枚示例和它们的渲染图
```

## 许可

MIT
