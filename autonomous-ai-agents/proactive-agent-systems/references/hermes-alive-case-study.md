# Hermes Alive — Case Study

Reference implementation of a gateway-native proactive messaging agent built on Hermes v0.17.0.

## Architecture

```
Gateway Hook (gateway:startup, session:start, agent:end)
  → ProactivePlatformWatcher (async tick loop, 300s)
    → MoodEngine (5-dim, shared with agent)
    → CooldownManager (quiet hours 00:30-08:30, 90min cooldown, 5/day max)
    → DiscoveryEngine (24h interval, arXiv/GitHub/HN/RSS/Playwright + local scan)
    → LLMMessageComposer (deepseek-v4-flash-ascend, single-pass, no validator)
    → Weixin adapter.send()
```

## Key Files

```
/opt/data/hooks/hermes-alive/     — hook directory (gateway discovers here)
  handler.py                       — event dispatch (gateway:startup, session:start, agent:end)
  proactive_watcher.py             — main tick loop and adapter integration
  cooldown_manager.py              — rate limiting
  llm_message_composer.py          — LLM generation + sanitize + 3 hard checks
  message_composer.py              — template fallback
  discovery.py                     — external + local discovery engine

/opt/data/hermes_alive_shared/    — shared state
  mood_engine.py                   — 5-dim mood with interaction hooks
  sources.yaml                     — discovery source config
  mood_state.json                  — runtime persistence
  current_mood.txt                 — agent-readable mood description

/opt/data/proactive_context.md    — user profile for LLM injection
```

## Env Vars

```
HERMES_PROACTIVE_PLATFORM_ENABLED=true
HERMES_PROACTIVE_WEIXIN_CHAT_ID=...
HERMES_PROACTIVE_LLM_ENABLED=true
HERMES_PROACTIVE_LLM_VALIDATE=0
HERMES_PROACTIVE_DISCOVERY_ENABLED=true
HERMES_PROACTIVE_DISCOVERY_INTERVAL_SECONDS=86400
HERMES_PROACTIVE_MAX_PER_DAY=5
HERMES_PROACTIVE_COOLDOWN_MINUTES=90
HERMES_PROACTIVE_QUIET_START=0:30
HERMES_PROACTIVE_QUIET_END=8:30
TZ=Asia/Shanghai
```

## Config

```yaml
auxiliary:
  proactive:
    provider: ustc
    model: deepseek-v4-flash-ascend
    timeout: 25
```

## Prompt Evolution (4 iterations)

### v1: Weather-dominated
All 6 messages opened with "毛毛雨/湿度/闷" — LLM latched onto weather data.

### v2: Casual but stilted
Weather gone but messages felt constructed — "快到晚上了，突然想问问你今天怎么样" instead of "干嘛呢".

### v3: Context-aware + anti-patterns
Added user profile injection + banned patterns ("这么晚还在X？"). Messages improved but still formulaic.

### v4: Philosophy-based (current)
Instead of listing "what to say", described "how to think" — "your brain wanders, thoughts pop up, you send them without editing." Messages feel human: "刚把时区那个破bug干掉，终于能正常说人话了。"

## Pitfalls Encountered

1. **Relative imports**: `from .module import X` fails in flat hook deployment → use absolute imports
2. **UTC timezone**: Container UTC caused "上午好" at 5PM → explicit `TZ=Asia/Shanghai`
3. **TODO regex too broad**: `(?:TODO|FIXME)` matched `TodoStore` class names → add `\b` word boundary
4. **Cooldown env vars unnamed**: `MAX_PER_DAY` vs `HERMES_PROACTIVE_MAX_PER_DAY` → always prefix
5. **Dual-LLM over-engineering**: Validation LLM added cost with no benefit for casual chat → removed

## Codex Usage

7 Codex delegations across the build:
- Phase 1: Gateway audit
- Phase 2-4: Core watcher + mood + cooldown
- Phase 5: LLM message composer + validation (later removed)
- Discovery engine (external + local)
- Audit fixes (C1-H5, M1-M6)
- Personality evolution (shared mood + hooks)
- Discovery completion (RSS, dedup, scoring)
- Playwright adapter
- Prompt fixes (3 iterations)

Pattern: Codex for multi-file implementation, Hermes for architecture + verification.