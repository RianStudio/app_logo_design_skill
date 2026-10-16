# rian-app-icon

一个 Claude skill：把一句产品描述变成一枚可以上架的 app 图标（1024 SVG 母版 + PNG + 评审对照图），风格统一为 Rian 的三种模式。

| 曜石 Obsidian | 墨线 Ink | 釉光 Glaze |
|---|---|---|
| ![](examples/renders/tide-obsidian-1024.png) | ![](examples/renders/margin-ink-1024.png) | ![](examples/renders/halo-glaze-1024.png) |
| 深色几何 + 精致光泽（Linear / Raycast） | 黑白手绘线稿（Notion） | 柔和同色渐变 + 轻微立体（Apple 原生） |

## 安装

**Claude Code**：把整个仓库复制到 `~/.claude/skills/rian-app-icon/`（个人）或项目里的 `.claude/skills/rian-app-icon/`。

**Claude.ai / Claude 桌面版**：把目录打成 zip，在 Settings → Capabilities → Skills 上传。

渲染脚本需要一次性安装：

```bash
pip install playwright && playwright install chromium
```

## 用法

直接对 Claude 说，例如：

> 给我做一个 app 图标：「Tide」，把待办拆成 25 分钟专注块的计时器，冷静、精准、有点高级感。

Claude 会读产品、选模式、给出 3 个隐喻方向、画 SVG、渲染对照图自检，然后交付。

## 结构

```
SKILL.md                     工作流程（入口）
references/style-dna.md      三种模式共用的原则、参数、禁忌和验收清单
references/mode-obsidian.md  曜石模式
references/mode-ink.md       墨线模式
references/mode-glaze.md     釉光模式
references/construction.md   SVG 骨架、光影配方、平台规格
references/sources.md        参考的开源 skill 与致谢
scripts/render.py            SVG → 1024 PNG + 对照图（Chromium 渲染）
examples/                    三种模式各一枚示例和它们的对照图
```

## 许可

MIT
