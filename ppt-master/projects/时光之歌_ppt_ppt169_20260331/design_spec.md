# 时光之歌_ppt - Design Spec

## I. Project Information

| Item | Value |
| ---- | ----- |
| **Project Name** | 时光之歌_ppt |
| **Canvas Format** | PPT 16:9 (1280×720) |
| **Page Count** | 11页 |
| **Design Style** | General Consulting (McKinsey风格) |
| **Target Audience** | 文学爱好者、学生、教育工作者、对时间哲学感兴趣的人群 |
| **Use Case** | 课堂展示、演讲分享、文学赏析、个人作品展示 |
| **Created Date** | 2026-03-31 |

---

## II. Canvas Specification

| Property | Value |
| -------- | ----- |
| **Format** | PPT 16:9 |
| **Dimensions** | 1280×720 |
| **viewBox** | `0 0 1280 720` |
| **Margins** | 上下50px，左右60px |
| **Content Area** | 1160×620 (居中) |

---

## III. Visual Theme

### Theme Style

- **Style**: General Consulting - 数据驱动、结构化思维、专业留白、极简高级
- **Theme**: Light theme (白色背景) 
- **Tone**: 专业、严谨、现代、思想性

### Color Scheme

基于McKinsey品牌蓝色主色调：

| Role | HEX | Purpose |
| ---- | --- | ------- |
| **Background** | `#FFFFFF` | 页面背景（白色） |
| **Secondary bg** | `#F5F5F5` | 卡片背景、章节背景 |
| **Primary** | `#005587` | 标题装饰、关键部分（McKinsey蓝）|
| **Accent** | `#2196F3` | 关键信息、数据高亮（科技蓝） |
| **Secondary accent** | `#4CAF50` | 积极强调、增长概念（绿色） |
| **Body text** | `#333333` | 诗歌正文（深灰） |
| **Secondary text** | `#666666` | 注释、解读（中灰） |
| **Tertiary text** | `#999999` | 补充信息、脚注（浅灰） |
| **Border/divider** | `#E0E0E0` | 卡片边框、分隔线 |
| **Success** | `#4CAF50` | 积极正面（绿色） |
| **Warning** | `#F44336` | 强调提醒（红色） |

---

## IV. Typography System

### Font Plan

**推荐预设**: P3（文化、艺术、人文）

| Role | Chinese | English | Fallback |
| ---- | ------- | ------- | -------- |
| **Title** | KaiTi | Georgia | SimHei |
| **Body** | Microsoft YaHei | Calibri | Arial |
| **Emphasis** | SimHei | Arial Black | - |

**字体栈**: `"Microsoft YaHei", Calibri, Arial, sans-serif`

### Font Size Hierarchy

**基准**: 正文字体大小 = 18px（中等密度内容）

| Purpose | Ratio | 18px基准 | Weight |
| ------- | ----- | -------- | ------ |
| 封面标题 | 3.0x | 54px | Bold |
| 章节标题 | 2.0x | 36px | Bold |
| 内容标题 | 1.5x | 27px | SemiBold |
| 副标题 | 1.2x | 22px | SemiBold |
| **正文内容** | **1x** | **18px** | Regular |
| 注释 | 0.8x | 14px | Regular |
| 页码/日期 | 0.6x | 11px | Regular |

---

## V. Layout Principles

### Page Structure

- **页眉区域**: 高度100px（包含标题栏）
- **内容区域**: 高度520px（主要内容区域）
- **页脚区域**: 高度40px（页码信息）

### Common Layout Modes

| Mode | 适用场景 |
| ---- | -------- |
| **单列居中** | 封面页、结语页、核心观点 |
| **左右分栏 (5:5)** | 诗歌赏析、内容对比 |
| **左右分栏 (4:6)** | 图像+文字混合 |
| **三栏卡片** | 核心思想分解 |
| **上下分栏** | 流程展示、时间线 |

### Spacing Specification

| Element | Recommended Range | Current Project |
| ------- | ---------------- | --------------- |
| 卡片间隙 | 24px | 24px |
| 内容块间隙 | 32px | 32px |
| 卡片内边距 | 24px | 24px |
| 卡片圆角 | 12px | 12px |
| 图标-文字间隙 | 12px | 12px |
| 单行卡片高度 | 580px | 580px |
| 双行卡片高度 | 280px | 280px |

---

## VI. Icon Usage Specification

### Source

- **内置图标库**: `templates/icons/` (640+ icons)
- **使用方法**: 占位符格式 `{{icon:category/icon-name}}`

### Recommended Icon List

| Purpose | Icon Path | Page |
| ------- | --------- | ---- |
| 时间概念 | `{{icon:time/clock}}` | 封面页 |
| 日夜更替 | `{{icon:nature/sun}}` `{{icon:nature/moon}}` | 第4页 |
| 人生阶段 | `{{icon:time/calendar}}` | 第5页 |
| 历史文明 | `{{icon:interface/book}}` | 第6页 |
| 珍惜当下 | `{{icon:time/hourglass}}` | 第7页 |
| 思维概念 | `{{icon:abstract/idea}}` | 第8页 |
| 书本教育 | `{{icon:education/book}}` | 第9页 |

---

## VII. Chart Reference List (if needed)

本诗歌PPT不含数据可视化图表。

---

## VIII. Image Resource List

**图像处理方式**：用户选择跳过AI图片生成，使用纯色背景代替。

| Filename | Dimensions | Ratio | Purpose | Type | Status | Generation Description |
| -------- | --------- | ----- | ------- | ---- | ------ | --------------------- |
| cover_bg.png | 1280×720 | 1.78 | 封面背景 | Background | Skipped | 使用深蓝色(#005587)纯色背景代替AI生成图像 |
| chapter_bg.png | 1280×720 | 1.78 | 章节过渡背景 | Background | Skipped | 使用浅灰色(#F5F5F5)纯色背景代替AI生成图像 |
| time_flow.png | 1280×720 | 1.78 | 时间主题背景 | Background | Skipped | 使用蓝色渐变(#005587 → #2196F3)背景代替AI生成图像 |

---

## IX. Content Outline

### Part 1: 诗歌介绍

#### Slide 01 - 封面页

- **Layout**: 全屏背景图 + 居中标题
- **Title**: 时光之歌
- **Subtitle**: 一首关于时间、生命与人生的哲理诗歌
- **Info**: 创作于2026年 | 作者：AI助理 | 风格：现代文学

#### Slide 02 - 诗歌简介

- **Layout**: 左右分栏 (5:5)
- **Title**: 诗歌主题与特点
- **Content**:
  - 主题：时间流逝与人生哲思
  - 篇幅：18行现代诗歌
  - 结构：6个主题部分
  - 风格：平实含蓄，深意绵长
  - 修辞：比喻、对仗、拟人

### Part 2: 诗歌内容解析

#### Slide 03 - 时光流逝 (1-4行)

- **Layout**: 左右分栏 (4:6)
- **Title**: 时光如水匆匆过
- **Content**:
  - 时光如水匆匆过，岁月如梭织人生
  - 幼年成长真奇妙，青春年华最难忘
  - **意象解析**：水流、织机
  - **哲学思考**：时间的不可逆性

#### Slide 04 - 日夜更替 (5-8行)

- **Layout**: 上下分栏
- **Title**: 日夜交替的韵律
- **Content**:
  - 晨曦微露新一日，夕阳西下又黄昏
  - 春夏秋冬轮流转，喜怒哀乐皆常态
  - **自然节奏**：昼夜、四季
  - **人生启示**：平衡与接受

#### Slide 05 - 人生阶段 (9-12行)

- **Layout**: 三栏卡片
- **Title**: 人生的不同阶段
- **Content**:
  - 少年轻狂不知愁，壮年奋斗追梦想
  - 中年安稳知天命，老年静坐忆往昔
  - **阶段特征**：少年、壮年、中年、老年
  - **成长智慧**：每个阶段的价值

#### Slide 06 - 历史文明 (13-16行)

- **Layout**: 左右分栏 (5:5)
- **Title**: 历史长河中的文明
- **Content**:
  - 历史长河滚滚流，文明星火代代传
  - 秦皇汉武成过往，唐宗宋祖亦尘埃
  - **历史视角**：宏观时间尺度
  - **文明传承**：精神延续

#### Slide 07 - 人生感悟 (17-20行)

- **Layout**: 单列居中
- **Title**: 珍惜当下的智慧
- **Content**:
  - 珍惜当下每一刻，把握今朝好时光
  - 莫等白头空叹息，悔恨往事不可追
  - **核心信息**：当下的重要性
  - **行动召唤**：立即行动

#### Slide 08 - 祝福结语 (21-22行)

- **Layout**: 左右分栏 (4:6)
- **Title**: 时光的祝福
- **Content**:
  - 愿君不负好韶华，活出精彩每一天
  - **诗歌结语**：积极正向的祝福
  - **终极启示**：活出意义

### Part 3: 总结升华

#### Slide 09 - 核心思想总结

- **Layout**: 四象限矩阵
- **Title**: 诗歌的五维哲学观
- **Content**:
  - 时间观：流逝与永恒
  - 生命观：阶段与成长
  - 历史观：宏观与传承
  - 价值观：珍惜与感恩
  - 人生观：行动与意义

#### Slide 10 - 结语与互动

- **Layout**: 单列居中
- **Title**: 感谢欣赏
- **Content**:
  - 《时光之歌》的文学价值
  - 对观众的思考引导
  - 互动提问：你对时间有什么感悟？

---

## X. Speaker Notes Requirements

生成对应的演讲者笔记文件，保存到 `notes/` 目录：

- **文件命名**: 匹配SVG名称，例如 `01_cover.md`
- **内容包含**: 演讲要点、时间提示、过渡语句
- **总时长**: 约15-20分钟展示
- **风格**: 正式、文学性、启发性

---

## XI. Technical Constraints Reminder

### SVG生成必须遵循：

1. viewBox: `0 0 1280 720`
2. 背景使用 `<rect>` 元素
3. 文本换行使用 `<tspan>` (`<foreignObject>` 禁止使用)
4. 透明度使用 `fill-opacity` / `stroke-opacity`；`rgba()` 禁止使用
5. 禁止：`clipPath`, `mask`, `<style>`, `class`, `foreignObject`
6. 禁止：`textPath`, `animate*`, `script`, `marker`/`marker-end`
7. 箭头使用 `<polygon>` 三角形代替 `<marker>`

### PPT兼容性规则：

- `<g opacity="...">` 禁止使用（组透明度）；在每个子元素上单独设置
- 图像透明度使用覆盖遮罩层 (`<rect fill="bg-color" opacity="0.x"/>`)
- 内联样式only；外部CSS和 `@font-face` 禁止使用

---

## XII. Design Checklist

### 预生成检查

- [ ] 内容适合页面容量
- [ ] 布局模式选择正确
- [ ] 颜色使用语义化

### 后生成检查

- [ ] viewBox = `0 0 1280 720`
- [ ] 无 `<foreignObject>` 元素
- [ ] 所有文本可读 (>=14px)
- [ ] 内容在安全区域内
- [ ] 所有元素对齐网格
- [ ] 相同元素保持一致性
- [ ] 颜色符合规范
- [ ] CRAP四原则检查通过

---

## XIII. Next Steps

1. ✅ 设计规范完成
2. **下一步骤**: 因包含AI生成的图片（封面背景、章节背景），需要调用 **Image_Generator** 角色生成图片，然后调用Executor生成SVG

