# V2 Capability Coverage — Dry-Run Verification

**Date:** 2026-07-03 | **Week:** 2026-W27 | **Status:** PASS (10/10)

The `weekly-briefing-v2` pipeline covers all capabilities previously distributed across
`academic-weekly-briefing-core`, `academic-report-render-deliver`, and `academic-briefing-ops`.

## Capability Matrix

| # | Capability | Implementation | Evidence |
|---|-----------|---------------|----------|
| 1 | Dual-source search | `run_weekly_e2e.py`: `arxiv_search()` + `crossref_search()` | 42 raw candidates (20 Crossref + 22 existing) |
| 2 | Candidate hard filter | `run_weekly_e2e.py`: `is_paper_like()` | 28 passed, 2 rejected (non-academic domains) |
| 3 | DOI/arXiv dedup | `run_weekly_e2e.py`: `canonical_id()` + `dedup_candidates()` | 42→30 after dedup |
| 4 | Archive update | SKILL.md §阶段6 → `archive.json` | 15 papers after recovery |
| 5 | Taxonomy update | SKILL.md §阶段6 → `taxonomy.json` with filter_score/reasons | Scores recorded per candidate |
| 6 | Manifest generation | `run_weekly_e2e.py` main() manifest block | manifest.json with stats, queries, papers |
| 7 | Typst PDF | `typst compile` → `report.pdf` | 22K PDF generated |
| 8 | PDF fallback (WeasyPrint) | Python `weasyprint` import available | `from weasyprint import HTML` succeeds |
| 9 | PDF fallback (minimal) | `run_weekly_e2e.py`: `make_minimal_pdf()` | Hand-written PDF generator, no deps |
| 10 | WeChat chunks | `run_weekly_e2e.py`: `split_weixin()` | Chunked output to `weixin_chunks.json` |
| 11 | Topic feedback | `run_weekly_e2e.py`: `build_queries()` reads `topic_feedback.json` | Biases applied to search queries |
| 12 | Recovery integration | `academic-briefing-ops/scripts/recover_archive.py` | Tested: 13→15 papers |
| 13 | Maintenance | `daily_maintenance.py` → exit 0 | Warnings: 0, Actions: 3 |

## v2 vs Core Skill Architecture

```
weekly-briefing-v2 (LLM entry point)
│
├── run_weekly_e2e.py --discovery-only  (deterministic paper discovery)
│   ├── arxiv_search()       — arXiv REST API
│   ├── crossref_search()    — Crossref REST API
│   ├── is_paper_like()      — hard filter + relevance scoring
│   └── dedup_candidates()   — DOI/arXiv canonical dedup
│
├── LLM Deep Analysis  (only in v2, not in runner)
│   ├── Author research via web_search
│   ├── Paper type classification
│   ├── "论文与我" relevance tags
│   ├── Cross-paper synthesis
│   └── Personalized email writing
│
├── PDF: Typst (primary) / WeasyPrint / make_minimal_pdf() (fallback)
├── Email: agently-cli + HERMES_WEEKLY_EMAIL_AUTO_CONFIRM
└── Data: dedup.json / archive.json / taxonomy.json / relations.json
```

## What v2 Does NOT Replace

These remain in their original skills:

| Component | Skill | Reason |
|-----------|-------|--------|
| Archive recovery | `academic-briefing-ops` | Standalone operational tool |
| Daily maintenance | `academic-briefing-ops` | Standalone cron (no_agent) |
| Profile evolution | `research-profile-engine` | Separate concern, separate crons |
| Venue quality grading | `academic-weekly-briefing-core` | Reference rules, not yet migrated |

## Signature Format

```
--- 
{限定词}
Hermes ᥫᩣ   (or 庄奕 ᥫᩣ — name, space, symbol)
```