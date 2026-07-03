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

## 渲染策略（3 级 fallback）

```
Typst 首选 → WeasyPrint 后备 → fpdf2 轻量后备 → Markdown-only
```

## Typst 模板

字体：Noto Sans CJK SC / Noto Serif CJK SC。
色彩：主色 #1a365d（深蓝），强调色 #2b6cb0（中蓝）。

编译：
```bash
cd $DATA_DIR/reports/{week}/
typst compile report.typ report.pdf
```

## 邮件交付

- 使用 agently-cli（通过 `command -v agently-cli` 确认安装）
- 主题前缀：⚚
- 落款：按 config.json 的 `style.signature` 设置
- 称呼：按 config.json 的 `user.display_name` 和 `style.role` 设置

### 发送命令（两阶段确认）

```bash
cd $DATA_DIR/reports/{week}/
agently-cli message +send \
  --to "your@email.com" \
  --subject "⚚ 学术研究周报 {week} — {主题}" \
  --body-file email_body.txt \
  --attachment report.pdf

# 第二阶段：确认
agently-cli message +send ... --confirmation-token {token}
```

自动确认：设 `HERMES_WEEKLY_EMAIL_AUTO_CONFIRM=1`。