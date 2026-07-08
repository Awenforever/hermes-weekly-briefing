---
name: research-profile-engine
description: 研究画像演化引擎：每日语义分析、每周画像综合、每月轨迹追踪。不负责论文搜索/周报生成/PDF/邮件。
version: 2.0.0
related_skills:
  - weekly-briefing-v3
---

# Research Profile Engine

Three-tier semantic research profile evolution: daily digest → weekly synthesis → monthly trajectory analysis.

## Architecture

```
Daily (23:55)  →  /opt/data/weekly-briefing/profile/daily/YYYY-MM-DD.md
Weekly (Sun 00:30) →  /opt/data/weekly-briefing/profile/weekly/YYYY-Www.md
Monthly (1st 01:00) → /opt/data/weekly-briefing/profile/monthly/YYYY-MM.md
                                   ↓
                          memory update (user profile)
```

## Modes

### Mode: daily
Scan today's conversations via `session_search()`, perform semantic analysis (NOT keyword counting), write daily digest.

Before analysis, classify conversation segments into:
- `research_core` — affects profile (method discussion, architecture debate, data analysis)
- `research_tooling` — does NOT affect profile (writing code, installing tools)
- `system_ops` — does NOT affect profile (config, deployment)
- `life_general` — does NOT affect profile

Key dimensions for research_core segments:
- Thematic threads: underlying research questions
- Depth progression: curiosity → technical depth → implementation
- Methodological taste: approaches favored/rejected with reasoning
- Cross-domain bridges: connections between fields
- Tensions: competing approaches or contradictions
- Seed questions: implied next questions

Output: `/opt/data/weekly-briefing/profile/daily/{date}.md`

### Mode: weekly
Read past 7 days of daily digests, perform cross-day pattern analysis:
- Theme evolution over time
- Emergent cross-day patterns
- Interest velocity (accelerating/decelerating attention)
- Convergence detection (multiple threads merging)

Update research profile in memory (user profile).

Output: `/opt/data/weekly-briefing/profile/weekly/{week}.md`

### Mode: monthly
Read past month of weekly syntheses, perform long-range trajectory analysis:
- Research identity shift
- Paradigm oscillation (swinging between opposing methods)
- Intellectual debt detection (foundational gaps)
- Unexplored adjacencies

Major profile rewrite via memory tool.

Output: `/opt/data/weekly-briefing/profile/monthly/{month}.md`

## Semantic Analysis Dimensions (all tiers)

Beyond keyword frequency — the system tracks:
- **Thematic threads**: underlying research questions, not surface topics
- **Depth signals**: curiosity → technical depth → implementation gradient
- **Methodological taste**: approaches favored/rejected with reasoning
- **Cross-domain bridges**: connections between different fields
- **Interest velocity**: acceleration/deceleration of attention on topics
- **Seed questions**: implied next questions the user hasn't asked yet
- **Intellectual debt**: foundational gaps that may block future progress

## Storage

- `/opt/data/weekly-briefing/profile/daily/` — daily distilled insights
- `/opt/data/weekly-briefing/profile/weekly/` — cross-day semantic syntheses
- `/opt/data/weekly-briefing/profile/monthly/` — long-range trajectory reports

## Classification Rules

1. Writing code ≠ research; architecture discussion = research
2. Installing tools ≠ research; tool evaluation = research
3. Data loading code ≠ research; data characteristics discussion = research
4. System config ≠ research; hyperparameter discussion = research
5. Long mixed sessions → segment before classification
6. Ambiguous → exclude (prefer false negative)

## Cron Integration

Three cron jobs call this skill:
- `research-profile-daily`: daily 23:55, mode=daily
- `research-profile-weekly`: Sun 00:30, mode=weekly
- `research-profile-monthly`: 1st 01:00, mode=monthly
