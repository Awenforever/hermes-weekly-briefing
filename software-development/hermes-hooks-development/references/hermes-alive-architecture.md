# Hermes Alive — Proactive Messaging Architecture

A complete worked example of Hermes hook development: a proactive WeChat messaging system that makes the AI feel "alive" by periodically sending casual messages to the user.

## Architecture

```
Gateway Process
  └── Hook (gateway:startup)
       └── ProactivePlatformWatcher (asyncio task)
            ├── MoodEngine (5-dim emotional state, time-decay)
            ├── CooldownManager (rate limit, quiet hours, daily cap)
            ├── DiscoveryEngine (arXiv/GitHub/HN + local filesystem)
            └── LLMMessageComposer
                 ├── LLM generate (deepseek-v4-flash-ascend, temp 0.65)
                 ├── Sanitize (strip formatting artifacts)
                 ├── 3 basic guards (non-empty, ≤300 chars, no markdown leak)
                 └── adapter.send() → WeChat
```

## Component Details

### MoodEngine
- 5 dimensions: energy, curiosity, social_urge, care, mischief
- Time-based decay: each dimension drifts toward neutral over hours
- Persists to `mood_state.json`
- Shared between gateway watcher AND agent sessions via hooks on `session:start` + `agent:end`

### CooldownManager
- Quiet hours: 00:30–08:30 (no messages)
- Daily cap: 5 messages/day
- Cooldown between messages: 90 minutes
- All configurable via `HERMES_PROACTIVE_*` env vars

### DiscoveryEngine
- **External** (every 24h): arXiv API, GitHub trending, Hacker News top stories
- **Local** (every 24h): TODO/FIXME/HACK scan, git log, error patterns, recent files
- Results cached, optionally injected into LLM prompt

### LLMMessageComposer
- Generates casual Chinese WeChat messages via `async_call_llm(task="proactive")`
- Context injection from `proactive_context.md` (user profile + recent memories)
- No deterministic content checks beyond format hygiene
- Message quality depends entirely on prompt engineering, not regex

## Key Design Decisions (User's Preferences)

1. **Single LLM, not dual-LLM** — validation was removed as over-engineering
2. **Trust prompt over regex** — no time-context checks, no co-presence checks, no assistant-tone checks. Only format hygiene.
3. **24h discovery interval** — low frequency, allow empty results
4. **TZ=Asia/Shanghai in Docker** — container timezone must match user's timezone
5. **Shared mood engine** — mood affects both proactive messages AND agent response tone

## Deployment Checklist

1. Copy hook files to `$HERMES_HOME/hooks/hermes-alive/`
2. Add to `config.yaml`:
   ```yaml
   auxiliary:
     proactive:
       provider: ustc
       model: deepseek-v4-flash-ascend
       timeout: 25
   ```
3. Add to `.env`:
   ```
   HERMES_PROACTIVE_PLATFORM_ENABLED=true
   HERMES_PROACTIVE_WEIXIN_CHAT_ID=...
   HERMES_PROACTIVE_LLM_ENABLED=true
   HERMES_PROACTIVE_LLM_VALIDATE=0
   HERMES_PROACTIVE_DISCOVERY_ENABLED=true
   ```
4. Docker compose: add `TZ: Asia/Shanghai`
5. Verify imports in flat directory context (see main skill)
6. Restart gateway
7. Check logs: `[hooks] Loaded hook 'hermes-alive-proactive'`

## Rollback

Set `HERMES_PROACTIVE_PLATFORM_ENABLED=false` and restart gateway. No core Hermes files were modified.