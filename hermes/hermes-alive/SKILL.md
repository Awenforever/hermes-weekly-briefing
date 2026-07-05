---
name: hermes-alive
description: "Hermes Alive — gateway-native proactive AI companion for WeChat. Auto-discovers content from 10 platforms, generates personality-driven Chinese messages via LLM, and consolidates memory through Claude Dreaming. One-command deploy: bash scripts/deploy.sh --all"
version: 2.0.0
---

# Hermes Alive

A self-contained, installable skill that turns Hermes Agent into a proactive WeChat companion. Drops into any Hermes installation — copy one directory, run one script, restart gateway.

## Quick Start

```bash
# 1. Install the skill (copy to /opt/data/skills/hermes/hermes-alive/)
# 2. Deploy + install dependencies
cd /opt/data/skills/hermes/hermes-alive
bash scripts/deploy.sh --all

# 3. Set your WeChat chat ID in /opt/data/.env:
#    HERMES_PROACTIVE_WEIXIN_CHAT_ID=<your-id>

# 4. Restart gateway
docker-compose up -d hermes

# 5. Verify
bash scripts/verify.sh
```

## What It Does

Hermes Alive adds a persistent asyncio task to your Hermes gateway that:

- **Checks in periodically** (every 5 min default) — sends LLM-generated WeChat messages in a distinct personality voice (庄奕, a casual friend with no "assistant" obligations)
- **Discovers interesting content** from 10 platforms — arXiv, GitHub, HN, V2EX, B站, 少数派, 知乎, papers.cool, 煎蛋, 小红书
- **Consolidates memory** every 24h via Claude Dreaming — non-destructive DreamDiff you review before applying
- **Respects quiet hours** (00:30–08:30) and cooldown periods — won't spam you

## Architecture

```
Hook (gateway:startup) → ProactivePlatformWatcher (asyncio task)
  │
  tick() every 300s
  │
  ├─ mood.tick()            → 5-dimensional emotional state
  ├─ cooldown.check()       → quiet hours | cooldown
  ├─ discovery.collect()    → 10 content sources (per 24h)
  ├─ dream.run_cycle()      → memory consolidation (per 24h)
  └─ LLM.compose()          → System Prompt + mood + discovery
       │
       └─ adapter.send()    → WeChat message
```

### Content Sources

| Source | Method | Type |
|--------|--------|------|
| arXiv | aiohttp API | Academic papers |
| GitHub Trending | aiohttp API | Repositories |
| Hacker News | aiohttp API | Tech news |
| V2EX | JSON API | Chinese tech |
| Bilibili | JSON API | Popular videos |
| 少数派 | RSS 2.0 | Tech articles |
| 知乎 | Playwright | Hot list |
| papers.cool | Playwright | Paper discussions |
| 煎蛋 | Playwright | Misc interesting |
| 小红书 | Playwright + anti-detect | Lifestyle notes |

### Dream Memory Consolidation

4-phase Claude Dreaming cycle:

1. **Orient** — read MEMORY.md from filesystem
2. **Gather** — send dream prompt + memory context to auxiliary LLM
3. **Consolidate** — parse operations (add/replace/remove)
4. **Prune** — flag stale entries

Results written to `dream_diff.json`. Non-destructive — review before applying.

## Files

```
hermes-alive/
├── SKILL.md                 ← This file
├── hooks/                   ← Gateway hook source (deployed to /opt/data/hooks/)
│   ├── HOOK.yaml
│   ├── handler.py           ← Event dispatcher
│   ├── proactive_watcher.py ← Main loop
│   ├── discovery.py         ← Multi-platform content engine
│   ├── llm_message_composer.py ← LLM prompt + sanitize
│   ├── dream_engine.py      ← Memory consolidation
│   ├── dream_prompt.py      ← Claude Dreaming prompt
│   ├── mood_engine.py       ← 5-dim emotion
│   ├── cooldown_manager.py  ← Rate limiting
│   ├── log_rotate.py        ← Daily log rotation + retention
│   └── safe_io.py           ← Thread-safe file I/O helpers
├── scripts/
│   ├── deploy.sh            ← One-command setup
│   ├── verify.sh            ← Health check
│   └── logs.py              ← Log query tool (filter, stats, preview)
├── templates/
│   ├── .env.template        ← Required env vars
│   └── sources.yaml         ← Content source config
└── references/
    ├── codex-patterns.md
    └── platform-discovery-patterns.md
```

## Configuration

All settings via environment variables. See `templates/.env.template` for the complete list.

Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `HERMES_PROACTIVE_PLATFORM_ENABLED` | false | Master enable |
| `HERMES_PROACTIVE_WEIXIN_CHAT_ID` | — | Target chat (required) |
| `HERMES_PROACTIVE_PLATFORM_INTERVAL_SECONDS` | 300 | Tick interval |
| `HERMES_PROACTIVE_LLM_ENABLED` | false | Use LLM generation |
| `HERMES_DREAM_ENABLED` | false | Enable dream consolidation |
| `HERMES_DREAM_INTERVAL_HOURS` | 24 | Hours between dreams |
| `HERMES_PROACTIVE_COOLDOWN_MINUTES` | 120 | Min minutes between messages |
| `PLAYWRIGHT_BROWSERS_PATH` | `/opt/data/.playwright-browsers` | Chromium location |

## Logging

All watcher decisions are logged to `proactive_log.jsonl` in the shared directory. Every tick produces one JSONL entry.

**Log rotation** (`log_rotate.py`): Runs on watcher startup. Archives yesterday's log as `proactive_log.YYYY-MM-DD.jsonl`, deletes archives older than `HERMES_ALIVE_LOG_RETENTION_DAYS` (default 7).

**Query tool** (`scripts/logs.py`): Human-readable filtering and stats.

```bash
# Recent entries with message previews
python3 scripts/logs.py --tail 5 --preview

# All sent messages since a date
python3 scripts/logs.py --decision sent --since 2026-07-01 --preview

# Stats overview
python3 scripts/logs.py --stats

# Raw JSON for piping
python3 scripts/logs.py --decision error --json

# See cooldown skips
python3 scripts/logs.py --reason cooldown --tail 5
```

Available filters: `--decision` (sent/skip/dream/start/stop/error), `--since`, `--until`, `--reason`, `--tail N`, `--all`, `--preview`, `--stats`, `--json`.

## Design Principles

1. **Positive guidance over hard bans** — prompt defines what the persona IS, not what it ISN'T
2. **Code handles format, prompt handles content** — 3 hard-error checks only (empty, >300 chars, format leak)
3. **Non-destructive memory** — dream engine writes diffs, never overwrites directly
4. **Failure isolation** — dream/discovery errors don't block message sending

## Pitfalls

- **Absolute imports only** — hook files loaded flat by `importlib`, no relative imports
- **Timezone** — set `TZ=Asia/Shanghai` or time context will be wrong
- **Gateway restart required** — hook changes only picked up at `gateway:startup`
- **Playwright persistence** — Chromium must be on persistent volume (`/opt/data/.playwright-browsers`), Python package reinstalled after image rebuild
- **Bilibili anti-bot** — needs full browser UA, not the discovery UA

## Extending

To add a new content platform:
1. Research: official API → robots.txt → curl test → Playwright fallback
2. Add extractor method in `hooks/discovery.py`
3. Add site config in `templates/sources.yaml`
4. Redeploy: `bash scripts/deploy.sh`
5. See `references/platform-discovery-patterns.md` for detailed workflow

To customize the personality:
- Edit `hooks/llm_message_composer.py` SYSTEM_PROMPT
- Follow the "positive guidance" principle — don't add prohibitions