# Hermes Alive — Reference Architecture

## File Layout

```
/opt/data/hooks/hermes-alive/
  HOOK.yaml              — Events: gateway:startup, session:start, agent:end
  handler.py             — Event dispatch: startup → watcher, session → mood, agent → mood
  proactive_watcher.py   — Main loop: 5min tick → mood → cooldown → compose → send
  cooldown_manager.py    — Quiet hours (00:30-08:30), 90min cooldown, 5/day cap
  llm_message_composer.py— LLM generation + sanitize + basic guards
  message_composer.py    — Template fallback (10 time-bucket templates)
  discovery.py           — External (arXiv/GitHub/HN/RSS/Playwright) + Local discovery
  __init__.py            — Package marker

/opt/data/hermes_alive_shared/
  mood_engine.py         — 5-dim mood (energy/curiosity/social_urge/care/mischief)
  sources.yaml           — Discovery source config
```

## Message Flow

```
tick → MoodEngine.tick() → CooldownManager.can_send()
     → DiscoveryEngine (every 24h) → LLMMessageComposer.compose()
     → adapter.send(chat_id, content)
```

## LLM Config

```yaml
auxiliary:
  proactive:
    provider: ustc
    model: deepseek-v4-flash-ascend
    timeout: 25
```

## Env Vars

```
HERMES_PROACTIVE_PLATFORM_ENABLED=true
HERMES_PROACTIVE_WEIXIN_CHAT_ID=...
HERMES_PROACTIVE_LLM_ENABLED=true
HERMES_PROACTIVE_LLM_VALIDATE=0
HERMES_PROACTIVE_MAX_PER_DAY=5
HERMES_PROACTIVE_COOLDOWN_MINUTES=90
HERMES_PROACTIVE_QUIET_START=0:30
HERMES_PROACTIVE_QUIET_END=8:30
HERMES_PROACTIVE_DISCOVERY_ENABLED=true
HERMES_PROACTIVE_DISCOVERY_INTERVAL_SECONDS=86400
```

## Prompt Design Principles

1. "像真人发微信，不是写作文" — casual, not literary
2. 1-2 sentences max, usually 1
3. Weather is optional, usually skip it
4. Context injection with "仅供参考，大部分时候不需要提到"
5. Trust the prompt over regex enforcement

## Lessons Learned

1. **Relative imports break in flat hook deployment** → always absolute
2. **Container timezone is UTC by default** → set TZ explicitly
3. **Dual-LLM validation is over-engineering** → single LLM + sanitize is enough
4. **Weather dominates if given to LLM** → frame as optional, discourage use
5. **Discovery needs 24h interval minimum** → allow empty results
6. **Git before modify** → backup commit then change