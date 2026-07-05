---
name: proactive-agent-systems
description: "Patterns for building gateway-native proactive/autonomous messaging agents on Hermes — hooks, prompts, discovery, mood, and safety."
version: 1.0.0
author: Hermes Agent
tags: [proactive, gateway, hooks, messaging, personality, discovery]
---

# Proactive Agent Systems

Class-level patterns for building agents that initiate contact — not just respond.

## Core Pattern: Hook-Based Zero-Core-Mod

The fundamental architecture for gateway-native proactive messaging without touching `/opt/hermes/`:

```
Gateway Hook (gateway:startup)
  → _gateway_runner_ref()         → access live adapters
  → adapter.send(chat_id, msg)    → push to platform
  → asyncio.create_task(watcher)  → persistent tick loop
```

**Why not `ctx.inject_message`:** It depends on CLI prompt_toolkit event loop reference, which is `None` in Gateway mode.

**Why not cron:** Cron creates a fresh agent session per tick — expensive, slow, no access to live adapters.

## Prompt Philosophy: Teach "How to Think", Not Rules

For proactive messages that feel natural:

1. **Don't give lists of "what to say"** — the LLM treats them as a menu and cycles through them mechanically
2. **Describe the mental process** — "your brain wanders, thoughts pop up, you send them without editing"
3. **Anti-patterns over rules** — "never do X" is stronger than "prefer Y"
4. **Ban weather explicitly** — LLMs latch onto weather data if it's available. Say "weather almost never matters, don't mention it"
5. **Normalize laziness** — "most real messages are useless. 'hungry' 'tired' '...' are perfect."

**Pitfall:** Every prompt iteration should be tested with 4-6 diverse mood/trigger combinations. Don't judge a prompt by one output.

## Pitfalls

### Relative imports in flat hook deployment

Hook files deployed flat in `/opt/data/hooks/<name>/` are loaded via `importlib.util.spec_from_file_location`. The module's `__package__` is `None`, so `from .module import X` fails with `ImportError: attempted relative import with no known parent package`.

**Fix:** Use absolute imports. Add the hook directory to `sys.path` and import directly: `from module import X`.

### Timezone: container != user

Docker containers often default to UTC. If `datetime.now()` returns UTC but the user is in CST, time-of-day buckets and quiet hours will be wrong by 8 hours.

**Fix:** Explicit timezone: `datetime.now(timezone(timedelta(hours=8)))` or set `TZ=Asia/Shanghai` in docker-compose.

### Over-engineering: the "Hermes Almighty" trap

The natural instinct is to add layers: dual-LLM validation, deterministic content checks, multi-stage pipelines. For casual proactive messaging, this is harmful — it makes messages feel sterile and the code bloated.

**Rule of thumb:** If a check can be expressed in the prompt, prefer the prompt. If a failure mode is cosmetic (slightly awkward phrasing), tolerate it. Only hard-guard format leaks and empty messages.

## Mood / Personality

A shared mood engine (accessed by both gateway watcher AND agent session) creates consistent personality:

- Five dimensions: energy, curiosity, social_urge, care, mischief
- Time decay: passive evolution every tick
- Interaction hooks: `session:start` → boost energy, `agent:end` → drain based on duration
- Persist to JSON file in shared location

## Discovery Pipeline

For proactive content sharing:

- External: arXiv API (free), GitHub Search API (rate-limited, no token needed for low volume), Hacker News API (free), RSS feeds (XML parsing)
- Local: TODO/FIXME scan (use `\b` word boundary in regex!), git log recent commits, error log tail, recent files
- Processing: URL dedup → keyword scoring → source budget → threshold filter
- Playwright: optional, disabled by default, read-only, max 3 pages per run

## Codex Delegation Pattern

For complex multi-file implementation:

1. Write the goal as a self-contained prompt with architecture, boundaries, and verification commands
2. Always include git backup step (commit before changes)
3. Always include verification commands Codex should run after changes
4. Always include rollback instructions
5. Delegate ONE concern per task (audit fixes OR personality, not both)
6. Use `toolsets: ["terminal", "file"]` — keeps Codex focused

## Verification Workflow

After any change to the proactive system:

```bash
# 1. Import test
python3 -c "from proactive_watcher import ProactivePlatformWatcher; ..."

# 2. LLM pipeline test (4-6 messages)
python3 -c "from llm_message_composer import LLMMessageComposer; ..."

# 3. Discovery test
python3 -c "from discovery import DiscoveryEngine; ..."

# 4. Gateway isolated container test (docker logs for hook lifecycle)
```

## References

See `references/hermes-alive-case-study.md` for the full build log and decision history of the reference implementation.