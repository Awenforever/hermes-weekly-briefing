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

- **DATA_ROOT**: config.json 中配置的 `data_dir`（默认为 `$HERMES_HOME/weekly-briefing/`）
- **SCRIPTS_DIR**: 本 skill 的 `scripts/` 目录（所有脚本随 skill 安装）

## 维护脚本

| 脚本 | 位置 | 触发 |
|------|------|------|
| `daily_maintenance.py` | 本 skill `scripts/` | cron: 每日 03:00（no_agent） |
| `health_check.py` | 本 skill `scripts/` | 手动 / 故障排查 |
| `recover_archive.py` | 本 skill `scripts/` | 手动 / archive 异常时 |
| `setup.py` | 本 skill `scripts/` | 首次安装初始化 |

---

## 铁律

### Git 版本管理
**任何持久化修改前必须先 git commit。** 三个 repo：`/opt/data/skills/`、`/opt/data/weekly-briefing/`、`/opt/data/home/.hermes/`。
流程：修改 → `git add -A` → `git commit -m "..."` → 再操作。

### 禁止无验证删除 Skill
2026-07-03 教训：删除 `academic-briefing-ops` 导致 `recover_archive.py` 永久丢失。删 skill 前必须：
1. `skill_view(name)` 列出全部 `scripts/`、`references/` 内容
2. `cronjob action=list` 确认无 cron 依赖
3. 有脚本的先备份到 `/opt/data/weekly-briefing/scripts/`
4. `git commit` 当前状态

## 初始化

### 依赖检查清单

| 依赖 | 检查方式 |
|------|----------|
| Typst | `which typst && typst --version` |
| WeasyPrint | `python3 -c "from weasyprint import HTML"` |
| agently-cli | `command -v agently-cli` |
| CJK 字体 | `fc-list :lang=zh` |
| pdftotext | `which pdftotext` |

### 数据目录初始化

```bash
mkdir -p $DATA_DIR/{papers/candidates,reports,profile/daily,profile/weekly,profile/monthly,teams,logs,exports,indices/quarterly}
```

---

## Archive 生命周期管理

### archive.json Schema

```json
{
  "papers": [{
    "archive_id": "uuid",
    "title": "...",
    "canonical_id": "doi or arxiv id",
    "first_seen_week": "2026-W27",
    "last_checked_week": "2026-W30",
    "included_in_reports": ["2026-W27"],
    "reading_status": "unread | skimmed | reading | deep_read | archived",
    "notes": "",
    "tags": ["must-cite", "baseline", "competitor", "reference"],
    "quality_tier": "T1 | T2 | T3 | T4",
    "superseded_by": null,
    "retracted": false
  }]
}
```

### 审查流程

1. 被取代检测：relations.json 中标记 superseded_by
2. 撤稿检测：web_search 检查 retracted/withdrawal
3. 发表状态变更：原 T4 论文是否已正式发表
4. 引用爆炸：近4周引用 ≥15/week → 标记 trending

---

## 清理策略

| 数据 | 策略 | 执行 |
|------|------|------|
| PDF | 保留最近 12 期 | 自动 |
| candidates/*.json | 保留最近 12 周 | 自动 |
| dedup.json | 保留最近 26 周条目 | 自动 |
| archive.json | 永久保留 | 手动确认 |
| taxonomy.json | 永久保留 | 手动确认 |
| relations.json edges | > 26 周自动重新验证 | 自动 |

---

## 已知陷阱

### Typst PATH 检测（daily_maintenance.py）

原脚本用 `os.path.exists("typst")` 检查 Typst 是否可用——这检查的是**当前工作目录**下名为 "typst" 的文件，不是 PATH。cron 运行时 cwd 不是 `/usr/local/bin/`，导致此检查永远返回 False，进而产生误报警告并可能导致 exit 1。

**正确做法**：`shutil.which("typst")` 或 `os.path.exists("/usr/local/bin/typst")`。

### 退出逻辑

`daily_maintenance.py` 的退出条件应为"实际数据损坏/缺失"，而非"存在 warnings"。Typst PATH 等环境差异不应导致 exit 1。已修复：仅 critical errors（含 "corrupt", "missing", "critical", "failed" 关键词的警告）才 exit 1。

1. 所有必需 JSON 文件存在且有效
2. archive.json 无 null reading_status（>4周未读）
3. relations.json 无 >26周的过期边
4. candidates/ 文件数 ≤12
5. agently-cli OAuth token 有效
6. Typst 可用

---

## BibTeX 导出

`exports/bibliography.bib` — 所有已归档论文的 BibTeX 集合。

## Obsidian 导出

`$DATA_DIR/exports/obsidian/*.md` — 每篇论文一个笔记，含 YAML frontmatter（如启用 Obsidian 导出）。

## Archive Recovery

使用 `scripts/recover_archive.py` 从 backups 和 manifests 恢复 archive.json 条目。

> ⚠️ **重建版本**：此脚本为 2026-07-03 重建实现，原版已丢失。
> 已验证：从 recovery bak + backup archive 恢复 2 篇缺失论文 (13→15)。
> 功能：扫描 `recovery/` bak 文件、`backups/` 历史 archive、`reports/*/manifest.json`。