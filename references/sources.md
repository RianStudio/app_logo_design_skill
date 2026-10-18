# 参考与致谢

石墨线稿风格的规则是 Rian 自己的，依据下面这些一手来源。所有 L 值和 hex（CIE LCh，D65，色相 265）、线宽 60、净空 60 和各项检查阈值是在这些来源上推导出来的，不是原文数字。

## 一手来源

| 来源 | 用到了什么 |
|---|---|
| [Linear · Brand](https://linear.app/brand) | 标志本身：一个圆被一条 45° 的弦切开，左下三条带；深色底、单色、克制的用法 |
| [Lucide · Icon design guide](https://lucide.dev/guide/design/icon-design-guide) | 24 格、2 单位圆头圆角的线，元素之间至少隔 2 单位：图标的线宽 60（2 单位按主体约 640 px 放大）、净空 60 和圆头圆角由它而来，`rian-app-theme` 的界面图标也是 Lucide |
| [Linear · How we redesigned the Linear UI](https://linear.app/now/how-we-redesigned-the-linear-ui) | 在 LCH 里从少数几个输入生成整套中性色：石墨底的色相和明度阶梯照这个思路推导，和 `rian-app-theme` 的界面底同色相 |
| [Linear · Behind the latest design refresh](https://linear.app/now/behind-the-latest-design-refresh) | 去掉多余的线和装饰、只靠明度分层的克制；图标不画投影、不加装饰也出于同样的取舍 |
| [Apple HIG · App icons](https://developer.apple.com/design/human-interface-guidelines/app-icons) | 1024 全出血母版、系统加遮罩；避免极细线宽和尖角；分层图标与 Liquid Glass（反射、折射、阴影、高光由系统加）；Default / Dark / Tinted / Clear 外观，至少一个元素是白色或接近白色 |
| [Apple · Configuring your app icon](https://developer.apple.com/documentation/xcode/configuring-your-app-icon) | asset catalog 的 Any / Dark / Tinted 三种外观：深色图标用透明底，让系统垫的底透出来；Tinted 交灰度图。`ios-1024-dark.png`、`ios-1024-tinted.png` 照它出 |
| [Apple · Product page optimization](https://developer.apple.com/app-store/product-page-optimization/) | 在 App Store 产品页上 A/B 测试图标：一次最多三个对照组；测试里的备用图标要全部打进已上架版本的安装包，下载的用户主屏上看到的也是它。`--store-ab` 的变体和 README.txt 照它写 |
| [Apple · App Review Guidelines 2.3.8](https://developer.apple.com/app-store/review/guidelines/#accurate-metadata) | 应用名和各尺寸图标、备用图标要彼此相像，不让用户混淆：商店变体只换底或加边，图形不动 |
| [Apple · Creating your app icon using Icon Composer](https://developer.apple.com/documentation/xcode/creating-your-app-icon-using-icon-composer) | 分组和层、Fill 渐变、Specular、组阴影、各外观的设定：`export/icon-composer/` 的两层和 README.txt 照它写 |
| [Android · Adaptive icons](https://developer.android.com/develop/ui/views/launch/icon_design_adaptive) | 108 dp 的 background / foreground / monochrome 三层，66 dp 安全圆，72 dp 可见区；Android 13 起的主题图标：系统按壁纸颜色给 monochrome 层重新上色 |
| [AOSP Launcher3 · ThemedIconDrawable.java](https://github.com/LineageOS/android_frameworks_libs_systemui/blob/lineage-20.0/iconloaderlib/src/com/android/launcher3/icons/ThemedIconDrawable.java)（Android 13，`getColors`） | 主题图标的两对色调按系统深色主题选，不按壁纸：浅色主题 `system_accent1_100` 底、`system_neutral2_700` 图形，深色主题 `system_neutral1_800` 底、`system_accent1_100` 图形。对照图的两格照它分浅色、深色主题 |
| [material-foundation · material-color-utilities](https://github.com/material-foundation/material-color-utilities)（`dynamic_scheme.ts`） | Material You 从种子色生成色调盘：Android 12、13 默认的 tonal spot 方案 primary 彩度 36、neutral variant 8，色调就是 L*。对照图里主题图标的模拟照它近似（用 CIE LCh 代替 HCT） |
| [Google Play · Icon design specifications](https://developer.android.com/distribute/google-play/resources/icon-design-specifications) | 512 × 512、32-bit PNG、sRGB、≤ 1024 KB、满幅方形；Play 自己加 30 % 圆角和投影 |

**待验证**：Icon Composer 的 Chromatic 组阴影（以实际版本的选项为准）；Android monochrome 层是否只按 alpha 通道着色（官方页面没写）；主题图标的色调值是用 CIE LCh 近似的 Material You 色调盘（HCT 才准），neutral1 的彩度取 4（material-color-utilities 2021 版写的是 6）；各家启动器也不一样。所以验收清单要求上架前在真机启动器上看。Apple 图标外形用圆角 22.37 %、60 % 平滑近似，Apple 没有公开精确的遮罩公式，细亮边上传前在 App Store Connect 的预览里看一眼角。

## 流程上借鉴的开源项目

| 项目 | 借鉴了什么 | 许可 |
|---|---|---|
| [anthropics/skills · canvas-design](https://github.com/anthropics/skills/tree/main/skills/canvas-design) | 「先定义设计哲学再动手」的两段式流程；打磨阶段「只精修、不加东西」 | Apache-2.0 |
| [anthropics/skills · frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | 列出 AI 生成设计的常见特征并主动避开；先写方案、对照需求自审、再执行 | Apache-2.0 |
| [op7418/logo-generator-skill](https://github.com/op7418/logo-generator-skill) | 信息收集 → 多方案 → 迭代 → 展示的流程；单一焦点、比例精确；SVG 转 PNG 的渲染脚本思路 | MIT |
| [PianoNic/ClaudeSkills · app-icon-expert](https://github.com/PianoNic/ClaudeSkills) | 动笔前的需求检查；剪影测试；「AI 创业公司图标」反模式；平台规格和交付前的验收清单 | MIT |

本仓库没有复制上述项目的文件，只吸收了方法。Linear、Apple、Google 的规范和标志仅作参考，图标不画成它们的标志。
