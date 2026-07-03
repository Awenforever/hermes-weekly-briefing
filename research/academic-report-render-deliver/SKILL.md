---
name: academic-report-render-deliver
description: 学术报告渲染与交付：Typst PDF 渲染、邮件发送、本地归档。不负责论文搜索/选择/画像演化。
version: 2.0.0
related_skills:
  - academic-weekly-briefing-core
  - generate-pdf-with-cjk
---

# Academic Report Render & Deliver

## 单一职责

渲染和交付：Markdown → 精美 Typst PDF → 邮件（附件）。

**不负责：** 论文搜索、论文选择、画像演化、去重、周报内容逻辑。

## 输入

- `report.md` — core skill 生成的周报正文
- `report_meta.json` — 元信息（周次/论文数/运行模式）

## 输出

- `report.typ` — Typst 源文件
- `report.pdf` — 精美 PDF
- `delivery_receipt.json` — 交付回执

## 渲染策略（3 级 fallback）

```
Typst 首选 → WeasyPrint 后备 → fpdf2 轻量后备 → Markdown-only
```

## Typst

Typst 已 bake 进标准镜像，路径 `/usr/local/bin/typst`。
检查：`which typst && typst --version`。

### 字体
容器有 Noto Sans CJK SC / Noto Serif CJK SC。fallback: `("Noto Sans CJK SC", "Noto Serif CJK SC")`

### 编译陷阱
1. 字体：`fc-list :lang=zh` 确认
2. `#sym.*` 不存在：直接用 Unicode
3. 编译前：`grep -n 'sym\.' report.typ` 确保零残留
4. 验证：`ls -lh report.pdf` 应 > 50KB

## 精美 PDF 模板

### 设计原则
- 学术但不呆板：深色标题栏 + 细线分隔 + 留白充足
- 色彩克制：主色 #1a365d（深蓝），强调色 #2b6cb0（中蓝）
- 论文卡片式排版，每篇论文有清晰的视觉边界
- "论文与我"标签用彩色小徽章
- 表格斑马纹 + 细线边框
- 页脚带页码和周次

### Typst 模板骨架

```typst
#let primary = rgb("#1a365d")
#let accent = rgb("#2b6cb0")
#let light-bg = rgb("#f7fafc")
#let border = rgb("#e2e8f0")
#let tag-can-use = rgb("#3182ce")
#let tag-compare = rgb("#dd6b20")
#let tag-compete = rgb("#e53e3e")
#let tag-gap = rgb("#38a169")

#set page(paper: "a4", margin: (top: 2.5cm, bottom: 2cm, left: 2.2cm, right: 2.2cm))
#set text(font: ("Noto Sans CJK SC", "Noto Serif CJK SC"), size: 10pt, lang: "zh")

// 封面标题区
#block(fill: primary, inset: (x: 0pt, y: 20pt), width: 100%, radius: 4pt)[
  #align(center)[
    #text(size: 22pt, weight: "bold", fill: white)[Academic Research Weekly Briefing]
    #v(0.3cm)
    #text(size: 14pt, fill: rgb("#bee3f8"))[2026 Week XX]
    #v(0.2cm)
    #text(size: 9pt, fill: rgb("#90cdf4"))[Generated: date | Source | Mode]
  ]
]
```

### 论文卡片宏
```typst
#let paper-card(title, authors, venue, year, tags, body) = {
  block(fill: light-bg, inset: 14pt, radius: 3pt, stroke: 0.5pt + border)[
    #text(size: 11pt, weight: "bold", fill: primary)[#title]
    #v(0.2cm)
    #text(size: 8.5pt, fill: gray)[#authors · #venue · #year]
    #v(0.3cm)
    #body
  ]
}
```

### PDF 验证
1. 文件存在且 > 50KB
2. `pdftotext` 能抽取标题
3. 无残留 `#sym.*` 引用

## 邮件交付

- 使用 agently-cli（`/opt/data/home/.local/bin/agently-cli`）
- 主题前缀：⚚
- 附件：report.pdf（相对路径，需 cd 到 PDF 所在目录）
- 落款格式：按 config.json 的 `style.signature` 设置
- 称呼：按 config.json 的 `user.display_name` 和 `style.role` 设置
- 寒暄/收束语：即兴，有人情味

### 发送命令（两阶段确认）

```bash
export PATH="/opt/data/home/.local/bin:$PATH"
cd /opt/data/weekly-briefing/reports/{week}/

# 第一阶段：发送（获取 confirmation_token）
agently-cli message +send \
  --to "your@email.com" \
  --subject "⚚ 学术研究周报 {week} — {主题}" \
  --body-file email_body.txt \
  --attachment report.pdf

# 第二阶段：确认
agently-cli message +send ... --confirmation-token {token}
```

自动确认：设 `HERMES_WEEKLY_EMAIL_AUTO_CONFIRM=1`。

## 错误处理

- PDF 失败 → 邮件发送 markdown-only + 记录 error
- 邮件失败 → 保存 receipt + 本地报告不回滚
- 全部失败 → 本地报告保留，manifest 记录 error