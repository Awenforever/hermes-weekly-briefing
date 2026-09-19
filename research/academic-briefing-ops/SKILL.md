---
name: academic-briefing-ops
description: 学术周报系统运维：初始化、依赖检查、cron 管理、健康检查、Archive 审查/修剪、候选清理、BibTeX 导出、全文 PDF 管理、Obsidian 导出、关系图谱维护。不负责论文搜索/周报生成/PDF/邮件。
version: 2.0.0
related_skills:
  - research-profile-engine
  - academic-weekly-briefing-core
  - academic-report-render-deliver
---

# Academic Briefing Ops

## 单一职责

周报系统全生命周期运维：从初始化到长期维护，从数据健康到知识导出。

**不负责：** 论文搜索、论文选择、画像演化、周报内容、PDF 渲染、邮件发送。

## 路径约定

- **DATA_ROOT**: `HERMES_WEEKLY_DATA_DIR`，插件模式默认为 `$HERMES_HOME/plugin-data/hermes-weekly-briefing/`
- **SCRIPTS_DIR**: 本 skill 的 `scripts/` 目录（所有脚本随 skill 安装）

## 维护脚本

| 脚本 | 位置 | 触发 |
|------|------|------|
| `daily_maintenance.py` | 本 skill `scripts/` | cron: 每日 03:00（no_agent） |
| `health_check.py` | 本 skill `scripts/` | 手动 / 故障排查 |
| `recover_archive.py` | 本 skill `scripts/` | 手动 / archive 异常时 |
| `setup.py` | 本 skill `scripts/` | 首次安装初始化 |

## 初始化

### 依赖检查清单

| 依赖 | 检查方式 |
|------|----------|
| WeasyPrint | `python3 -c "from weasyprint import HTML"` |
| ReportLab（降级渲染） | `python3 -c "import reportlab"` |
| agently-cli | `command -v agently-cli` |
| CJK 字体 | `fc-list :lang=zh` |
| pdftotext | `which pdftotext` |

### 数据目录初始化

```bash
mkdir -p $DATA_DIR/{papers/candidates,reports,profile/daily,profile/weekly,profile/monthly,teams,logs,exports,indices/quarterly}
```

## Archive 生命周期管理

- 被取代检测 / 撤稿检测 / 发表状态变更 / 引用爆炸

## 清理策略

| 数据 | 策略 |
|------|------|
| PDF | 保留最近 12 期 |
| candidates/*.json | 保留最近 12 周 |
| archive.json | 永久保留 |

## Obsidian 导出

`$DATA_DIR/exports/obsidian/*.md` — 每篇论文一个笔记（如启用）。

## Archive Recovery

使用 `scripts/recover_archive.py` 从 backups 和 manifests 恢复 archive.json 条目。
