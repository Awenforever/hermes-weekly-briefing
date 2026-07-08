---
name: hermes-alive
description: "Hermes Alive — gateway-native proactive AI companion for WeChat. Evolves a per-user Personality Genome, discovers content, generates Chinese messages via LLM, and consolidates memory through Claude Dreaming. One-command deploy: bash scripts/deploy.sh --all"
version: 2.3.1
author: Hermes Agent
license: MIT
metadata:
  short-description: Gateway-native proactive WeChat companion for Hermes
  hermes:
    tags:
      - hermes
      - wechat
      - gateway
      - proactive-messaging
      - memory
    related_skills:
      - hermes-wechat-enhance
---

# Hermes Alive

## Overview

Hermes Alive is a self-contained gateway module that adds a proactive WeChat companion to Hermes Agent. Install the skill into the Hermes skills tree, deploy it with `bash scripts/deploy.sh --all`, restart the gateway, then verify with `bash scripts/verify.sh`.

The runtime adds a persistent asyncio watcher at `gateway:startup` that:

- logs every proactive decision with a shared `tick_id`
- enforces the three-layer activity guard before sending anything
- refreshes `ContextQueue` from `state.db` before each tick
- discovers content from external sources on a 4h cadence
- composes 1-5 Chinese messages via LLM, with fallback support
- consolidates memory through the dream cycle and updates voice state

## When to Use

Use this skill when you need a Hermes gateway to proactively message a WeChat user while preserving:

- the existing proactive watcher architecture
- content discovery across the current external sources
- the Personality Genome and dream-engine behavior
- operational observability through JSONL logs and `scripts/logs.py`

Do not use this skill for generic chat adapters, non-WeChat proactive flows, or tasks that require changing core Hermes code under `/opt/hermes/`.

## Quick Start

```bash
cd /opt/data/skills/hermes/hermes-alive
bash scripts/deploy.sh --all

# Set in /opt/data/.env:
# HERMES_PROACTIVE_WEIXIN_CHAT_ID=<your-id>

docker-compose up -d hermes
bash scripts/verify.sh
```

## What It Does

- **Pipeline logging**: discovery -> compose -> sent, linked by `tick_id`
- **Log rotation**: daily archive with configurable retention
- **Query tool**: `scripts/logs.py` for filtering, stats, and previews
- **Context injection**: recent conversation injected with cosine freshness decay
- **Multi-message burst**: LLM may compose 1-5 messages split by `---`
- **Activity guard**: send only when Hermes is idle, Hermes spoke last, and that last Hermes message is at least 30 minutes old
- **ContextQueue**: in-memory queue persisted to `context_queue.json`, refreshed from `state.db` before every tick
- **Voice Genome**: per-user Personality Genome stored in `voice_state.json`
- **Voice-linked cooldown**: `max(30, 120 - social_urge x 90)` minutes
- **Dream reads sessions**: transcripts come from `state.db`, not only static memory
- **Dream auto-apply**: high-confidence ops update `MEMORY.md` with backup
- **Content discovery**: 10 current sources with disk-backed cache
- **LLM fallback**: retries with `HERMES_PROACTIVE_LLM_FALLBACK_MODEL`

## Architecture

```text
Hook (gateway:startup) -> ProactivePlatformWatcher (asyncio task)
  |
  tick() every 300s
  |
  |- voice.load()
  |- is_session_busy()
  |- ContextQueue.refresh()
  |- activity guard
  |- cooldown.check()
  |- discovery.collect()
  |- dream.run_cycle()
  `- LLM.compose() -> adapter.send()
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

1. **Orient**: read `MEMORY.md`, proactive context, and recent session transcripts from `state.db`
2. **Gather**: send dream prompt and context to the auxiliary LLM
3. **Consolidate**: parse add/replace/remove operations with confidence
4. **Prune**: flag stale or low-trust entries

High-confidence results (`>= 0.7`) auto-apply to `MEMORY.md`. High-confidence academic and leisure findings also shift the Personality Genome.

## Files

```text
hermes-alive/
|- SKILL.md
|- hooks/
|  |- HOOK.yaml
|  |- handler.py
|  |- proactive_watcher.py
|  |- discovery.py
|  |- llm_message_composer.py
|  |- context_tracker.py
|  |- dream_engine.py
|  |- dream_prompt.py
|  |- voice_engine.py
|  |- cooldown_manager.py
|  |- dream_diff_store.py
|  |- log_rotate.py
|  |- safe_io.py
|  |- alive_control.py
|  `- __init__.py
|- scripts/
|  |- deploy.sh
|  |- verify.sh
|  `- logs.py
|- templates/
|  |- .env.template
|  `- sources.yaml
`- references/
   |- codex-patterns.md
   |- docker-build-pitfalls.md
   |- message-style-guidelines.md
   |- platform-discovery-patterns.md
   |- session-id-format-change.md
   `- testing-deployment-pitfalls.md
```

## Configuration

All settings are driven by environment variables. See `templates/.env.template` for the full list.

| Variable | Default | Purpose |
|----------|---------|---------|
| `HERMES_PROACTIVE_PLATFORM_ENABLED` | false | Master enable |
| `HERMES_PROACTIVE_WEIXIN_CHAT_ID` | - | Target chat |
| `HERMES_PROACTIVE_PLATFORM_INTERVAL_SECONDS` | 300 | Tick interval |
| `HERMES_PROACTIVE_LLM_ENABLED` | false | Use LLM generation |
| `HERMES_PROACTIVE_LLM_MODEL` | deepseek-v4-flash-ascend | Primary model |
| `HERMES_PROACTIVE_LLM_FALLBACK_MODEL` | deepseek-v4-flash | Fallback model |
| `HERMES_PROACTIVE_LLM_TIMEOUT` | 60 | LLM timeout seconds |
| `HERMES_DREAM_ENABLED` | false | Enable dream consolidation |
| `HERMES_DREAM_INTERVAL_HOURS` | 24 | Dream cadence |
| `HERMES_PROACTIVE_COOLDOWN_MINUTES` | 120 | Base cooldown |
| `HERMES_PROACTIVE_DISCOVERY_INTERVAL_SECONDS` | 14400 | Discovery cadence |
| `HERMES_PROACTIVE_DISCOVERY_ENABLED` | true | Enable discovery |
| `HERMES_PROACTIVE_QUIET_START` | 0:30 | Quiet hours start |
| `HERMES_PROACTIVE_QUIET_END` | 8:30 | Quiet hours end |
| `HERMES_ALIVE_LOG_RETENTION_DAYS` | 7 | Log retention |
| `PLAYWRIGHT_BROWSERS_PATH` | `/opt/data/.playwright-browsers` | Chromium path |

Removed in v2.2: `HERMES_PROACTIVE_ACTIVE_COOLDOWN_MINUTES`.

Changed in v2.3: `recent_context.json`, `mood_engine.py`, and `message_composer.py` were removed in favor of `ContextQueue` and `context_queue.json`. Session busy/idle tracking now comes from `session:start` and `agent:end`.

## Logging

All watcher decisions are written to `proactive_log.jsonl` in the shared directory.

- `log_rotate.py` archives yesterday's log as `proactive_log.YYYY-MM-DD.jsonl`
- `scripts/logs.py` provides human-readable filtering and stats

```bash
python3 scripts/logs.py --tail 5 --preview
python3 scripts/logs.py --decision sent --since 2026-07-01 --preview
python3 scripts/logs.py --stats
python3 scripts/logs.py --decision error --json
python3 scripts/logs.py --reason cooldown --tail 5
```

Available filters: `--decision`, `--voice`, `--since`, `--until`, `--reason`, `--tail`, `--all`, `--preview`, `--stats`, `--json`.

## Context Injection

Recent conversation is captured in `ContextQueue` and injected into the compose prompt with cosine-based freshness decay:

| Time Since | Label | Weight | Effect |
|------------|-------|--------|--------|
| < 30 min | - | - | Tick suppressed |
| 30 min | 刚刚 | 1.0 | Likely to continue the thread |
| 30 min-3h | 大约一小时前 | ~0.7 | May reference if relevant |
| 3h-6h | 之前 | ~0.0 | Ignored entirely |
| > 6h | 更早 | 0 | Ignored |

Activity guard semantics:

1. `is_session_busy()` -> suppress
2. `last_message_role == "user"` -> suppress
3. `last_message_role == "assistant"` and last message < 1800s -> suppress
4. `last_message_role == "assistant"` and last message >= 1800s -> allow
5. no conversation history -> allow

## Design Principles

1. Positive guidance over hard bans
2. Code handles format, prompt handles content
3. Non-destructive memory updates
4. Failure isolation for dream and discovery paths
5. LLM owns creative output; code enforces only hard constraints

## Development Operations

This skill follows the gateway-module pattern. Keep operational docs accurate, prefer goal-oriented verification, and never modify a running gateway without explicit user approval.

### Lifecycle Commands

| Lifecycle stage | Command | Notes |
|-----------------|---------|-------|
| Initial deploy | `bash scripts/deploy.sh --all` | Installs dependencies, syncs files, and prepares the skill |
| Redeploy updates | `bash scripts/deploy.sh` | Refreshes deployed hook files without the full bootstrap |
| Verify | `bash scripts/verify.sh` | Runs the packaged health checks |
| Inspect logs | `python3 scripts/logs.py --stats` | Operational visibility and debugging |
| Uninstall | No bundled script | Remove deployed files manually if the user explicitly requests teardown |

## Common Pitfalls

- Use absolute imports only in hook files; they are loaded flat by `importlib`.
- Restart the gateway after hook changes; they are loaded at `gateway:startup`.
- Keep the startup notification text exactly `✨ Gateway online — Hermes is back and ready.`
- `ContextQueue` is the source of truth in v2.3+. Do not reintroduce `recent_context.json`.
- Proactive message metadata must keep `is_system: false` so the footer shows the real model name.
- Runtime state must consistently honor `HERMES_ALIVE_SHARED_DIR`.
- For Playwright, browser binaries must persist outside the image layer.
- See `references/docker-build-pitfalls.md` for browser/image pitfalls.
- See `references/testing-deployment-pitfalls.md` for isolated deploy-test guidance.
- See `references/session-id-format-change.md` when debugging activity guard failures after Hermes session format changes.

## Verification Checklist

- Frontmatter starts with `---` and includes peer metadata.
- `SKILL.md` remains the entrypoint and stays concise enough for skill loading.
- Script references mention only `deploy.sh`, `verify.sh`, and `logs.py`.
- `ContextQueue` references consistently use `context_queue.json`.
- The startup notification text remains unchanged.
- Hook architecture, content discovery sources, dream engine design, and code under `hooks/` remain untouched.

## Extending

To add a new content platform:

1. Check for an official API, then `robots.txt`, then a curlable endpoint, then Playwright.
2. Add the extractor in `hooks/discovery.py`.
3. Add source config in `templates/sources.yaml`.
4. Redeploy with `bash scripts/deploy.sh`.
5. Read `references/platform-discovery-patterns.md` for the detailed workflow.

To customize the personality, edit `hooks/llm_message_composer.py` and preserve the positive-guidance prompt style.
