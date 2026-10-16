# rian-app-icon

一个 Claude skill：把一句产品描述变成一枚可以上架的 app 图标（1024 SVG 母版 + PNG + 评审对照图）。

风格只有一种：**简洁、明确、有质感，带东方气质**。几何构造学 Google，光影学 Apple，材质和颜色来自中国美学。每枚图标都是同样的三层：传统色的底，一个有体积的实色几何形，一层叠在前面的青瓷釉；主体按 Apple 和 Google 的图标网格撑满画面。

![示例](examples/renders/overview.png)

| 示例 | 配色 | 画了什么 |
|---|---|---|
| Tide 专注计时 | 墨 · 朱砂 · 天青釉 | 25 分钟的进度圆弧，釉面表盘 |
| Halo 天气 | 黛蓝 · 藤黄 · 月白釉 | 太阳，釉面云 |
| Margin 笔记 | 宣纸 · 朱砂 · 月白釉 | 红笺，釉面便签 |
| QR Code Scanner | 墨 · 藤黄 · 天青釉 | 二维码，釉面扫描条 |
| Image Compressor | 宣纸 · 石青 · 月白釉 | 风景照，右上角一块更小的釉面副本 |

## 安装

**Claude Code**：把整个仓库复制到 `~/.claude/skills/rian-app-icon/`（个人）或项目里的 `.claude/skills/rian-app-icon/`。

**Claude.ai / Claude 桌面版**：把仓库打成 zip，在 Settings → Capabilities → Skills 上传。

渲染脚本需要一次性安装：

```bash
pip install playwright && playwright install chromium
```

## 用法

直接对 Claude 说，例如：

> 给我做一个 app 图标：「Tide」，把待办拆成 25 分钟专注块的计时器。

Claude 会读懂产品、定隐喻和配色、从模板画 SVG、渲染对照图自检，然后交付。

## 结构

```
SKILL.md                    工作流程（入口）
references/style.md         风格原则、参数、配色、禁忌、验收清单
references/construction.md  图层结构、几何速查、平台规格
references/sources.md       参考来源与致谢
assets/template.svg         图标模板：只改 TODO 的地方
scripts/render.py           SVG → 1024 PNG + 对照图（Chromium 渲染）
examples/                   三枚示例和它们的渲染图
```

## 许可

MIT
