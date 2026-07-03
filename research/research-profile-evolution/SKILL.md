---
name: research-profile-evolution
description: 三层语义研究画像演化系统——日总结→周合成→月轨迹，基于对话内容自动更新用户研究画像
version: 1.0.0
---

# Research Profile Evolution System

Three-tier semantic research profile evolution: daily digest → weekly synthesis → monthly trajectory analysis.

## Architecture

### §0 初始化向导（首次加载时执行）

Hermes 加载此 skill 后，向用户确认以下配置：

> 我已经准备好三层研究画像演化系统。确认以下设置：
> 1. **Daily Digest**：每天 23:55 分析当天对话（写入 `/opt/data/research-profile/daily/`）
> 2. **Weekly Synthesis**：每周日 00:30 跨天合成（更新研究画像 memory）
> 3. **Monthly Trajectory**：每月 1 日 01:00 长期轨迹分析
> 4. 存储目录：`/opt/data/research-profile/`（首次自动创建）
> 
> 要我现在为你创建这三个 cron job 吗？（回复"全部"即可）

用户确认后，使用 `cronjob` 工具创建三个 cron，参考下方 "Cron Job Setup" 中的 prompt。

### Architecture

```
Daily (23:55)  →  /opt/data/research-profile/daily/YYYY-MM-DD.md
Weekly (Sun 00:30) →  /opt/data/research-profile/weekly/YYYY-Www.md
Monthly (1st 01:00) → /opt/data/research-profile/monthly/YYYY-MM.md
                                   ↓
                          memory update (user profile)
```

## Storage
- `/opt/data/research-profile/daily/` — daily distilled insights
- `/opt/data/research-profile/weekly/` — cross-day semantic syntheses  
- `/opt/data/research-profile/monthly/` — long-range trajectory reports

## Modes

### Mode: daily
Scan today's conversations via `session_search()`, perform semantic analysis (NOT keyword counting), and write daily digest.

See `/opt/data/research-profile/prompts/daily-digest.md` for full analysis framework.
Key dimensions: thematic threads, depth progression, methodological taste, cross-domain connections, tensions, seed questions.

### Mode: weekly
Read past 7 days of daily digests, perform cross-day pattern analysis, update research profile in memory.

See `/opt/data/research-profile/prompts/weekly-synthesis.md` for full framework.
Key: theme evolution over time, emergent cross-day patterns, interest velocity, convergence detection.

### Mode: monthly
Read past month of weekly syntheses, perform long-range trajectory analysis, major profile rewrite.

See `/opt/data/research-profile/prompts/monthly-trajectory.md` for full framework.
Key: research identity shift, paradigm oscillation, intellectual debt detection, unexplored adjacencies.

## Semantic Analysis Dimensions (across all tiers)
Beyond keyword frequency — the system tracks:
- **Thematic threads**: underlying research questions, not surface topics
- **Depth signals**: curiosity → technical depth → implementation gradient
- **Methodological taste**: approaches favored/rejected with reasoning
- **Cross-domain bridges**: connections between different fields
- **Interest velocity**: acceleration/deceleration of attention on topics
- **Seed questions**: implied next questions the user hasn't asked yet
- **Intellectual debt**: foundational gaps that may block future progress

## Cron Job Setup
After installing this skill, set up three cron jobs:

```bash
# Daily digest — runs 23:55 every day
Prompt: "Run research-profile-evolution in daily mode. Read the full analysis framework from /opt/data/research-profile/prompts/daily-digest.md, then execute: gather today's sessions via session_search, perform semantic analysis, write digest to /opt/data/research-profile/daily/{today}.md"

# Weekly synthesis — runs Sunday 00:30
Prompt: "Run research-profile-evolution in weekly mode. Read the full framework from /opt/data/research-profile/prompts/weekly-synthesis.md, then: load the past 7 daily digests from /opt/data/research-profile/daily/, perform cross-day semantic synthesis, update the user's research profile via memory tool, write synthesis to /opt/data/research-profile/weekly/{this_week}.md"

# Monthly trajectory — runs 1st of month 01:00
Prompt: "Run research-profile-evolution in monthly mode. Read the full framework from /opt/data/research-profile/prompts/monthly-trajectory.md, then: load all weekly syntheses from /opt/data/research-profile/weekly/ from the past month, perform long-range trajectory analysis, rewrite research profile via memory tool, write report to /opt/data/research-profile/monthly/{this_month}.md"
```