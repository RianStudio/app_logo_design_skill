# 参考与致谢

石墨风格的规则是 Rian 自己的，依据下面这些一手来源。所有 L 值和 hex（CIE LCh，D65，色相 265）、关键线收小 3 %、切口 48、最薄处 72 和各项检查阈值是在这些来源上推导出来的，不是原文数字。

## 一手来源

| 来源 | 用到了什么 |
|---|---|
| [Linear · Brand](https://linear.app/brand) | 标志本身：一个圆被一条 45° 的弦切开，左下三条带；深色底、单色、克制的用法 |
| [simple-icons · linear.svg](https://github.com/simple-icons/simple-icons/blob/develop/icons/linear.svg) | Linear 标志的矢量（24 × 24 viewBox）：切口是等宽的平行负形，带宽等于间隙，切口约为直径的 7.4 %。这里的 48（关键线圆直径的 8.3 %）由它放宽而来 |
| [Linear · How we redesigned the Linear UI](https://linear.app/now/how-we-redesigned-the-linear-ui) | 在 LCH 里从少数几个输入生成整套中性色：石墨底的色相和明度阶梯照这个思路推导，和 `rian-app-theme` 的界面底同色相 |
| [Linear · Behind the latest design refresh](https://linear.app/now/behind-the-latest-design-refresh) | 去掉多余的线和装饰、只靠明度分层的克制；图标不画投影、不加装饰也出于同样的取舍 |
| [Apple HIG · App icons](https://developer.apple.com/design/human-interface-guidelines/app-icons) | 1024 全出血母版、系统加遮罩；避免极细线宽和尖角；分层图标与 Liquid Glass（反射、折射、阴影、高光由系统加）；Default / Dark / Tinted / Clear 外观，至少一个元素是白色或接近白色 |
| [Apple · Creating your app icon using Icon Composer](https://developer.apple.com/documentation/xcode/creating-your-app-icon-using-icon-composer) | 分组和层、Fill 渐变、Specular、组阴影、各外观的设定：`export/icon-composer/` 的两层和 README.txt 照它写 |
| [Android · Adaptive icons](https://developer.android.com/develop/ui/views/launch/icon_design_adaptive) | 108 dp 的 background / foreground / monochrome 三层，66 dp 安全圆，72 dp 可见区；Android 13 起的主题图标 |
| [Google Play · Icon design specifications](https://developer.android.com/distribute/google-play/resources/icon-design-specifications) | 512 × 512、32-bit PNG、sRGB、≤ 1024 KB、满幅方形；Play 自己加 30 % 圆角和投影 |

**待验证**：Icon Composer 的 Chromatic 组阴影（以实际版本的选项为准）；Android monochrome 层是否只按 alpha 通道着色（官方页面没写）。

## 流程上借鉴的开源项目

| 项目 | 借鉴了什么 | 许可 |
|---|---|---|
| [anthropics/skills · canvas-design](https://github.com/anthropics/skills/tree/main/skills/canvas-design) | 「先定义设计哲学再动手」的两段式流程；打磨阶段「只精修、不加东西」 | Apache-2.0 |
| [anthropics/skills · frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | 列出 AI 生成设计的常见特征并主动避开；先写方案、对照需求自审、再执行 | Apache-2.0 |
| [op7418/logo-generator-skill](https://github.com/op7418/logo-generator-skill) | 信息收集 → 多方案 → 迭代 → 展示的流程；单一焦点、比例精确；SVG 转 PNG 的渲染脚本思路 | MIT |
| [PianoNic/ClaudeSkills · app-icon-expert](https://github.com/PianoNic/ClaudeSkills) | 动笔前的需求检查；剪影测试；「AI 创业公司图标」反模式；平台规格和交付前的验收清单 | MIT |

本仓库没有复制上述项目的文件，只吸收了方法。Linear、Apple、Google 的规范和标志仅作参考，图标不画成它们的标志。
