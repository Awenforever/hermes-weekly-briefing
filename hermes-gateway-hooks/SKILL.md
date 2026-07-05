---
name: hermes-gateway-hooks
description: "Develop, test, and deploy Hermes Agent gateway hooks — event-driven extensions that run inside the gateway process."
version: 1.0.0
category: hermes
---

# Hermes Gateway Hook Development

Gateway hooks are event-driven Python handlers that run inside the Hermes Agent gateway process. They react to lifecycle events (gateway:startup, session:start, etc.) and can spawn long-running background tasks like proactive messaging systems.

## Hook Lifecycle

1. Hooks live under `$HERMES_HOME/hooks/<name>/` with `HOOK.yaml` + `handler.py`
2. Gateway discovers them at startup via `HookRegistry.discover_and_load()`
3. `gateway:startup` fires after platforms connect
4. Handler receives `(event_type: str, context: dict)` and can spawn asyncio tasks

## Critical: Import Path When Deploying Flat Files

**The most common pitfall.** Hooks loaded by the gateway use `importlib.util.spec_from_file_location` which loads `handler.py` as a standalone module (`__package__` is None). If your hook files use relative imports (`from .xxx import ...`), they will fail at runtime with `ImportError: attempted relative import with no known parent package`.

**Fix:** Use absolute imports throughout deployed hook files. Since the hook directory is added to `sys.path` by the handler, `from mood_engine import MoodEngine` works correctly.

**Do NOT use** `from .mood_engine import ...` in deployed hook files.

```python
# handler.py — correct pattern
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOK_DIR not in sys.path:
    sys.path.insert(0, _HOOK_DIR)
from proactive_watcher import ProactivePlatformWatcher  # absolute import
```

## Accessing Gateway Internals

To access live adapters and config from a hook:

```python
sys.path.insert(0, "/opt/hermes")
from gateway.run import _gateway_runner_ref

runner = _gateway_runner_ref()
if runner is None:
    return
# runner.adapters: Dict[Platform, BasePlatformAdapter]
# runner.config: GatewayConfig
```

## Timezone in Docker Containers

Docker containers default to UTC. For hooks that use `datetime.now()`, add `TZ=Asia/Shanghai` (or appropriate timezone) to the container's environment. Without this, time-based logic (morning/evening buckets, quiet hours) will be wrong by the UTC offset.

```yaml
# docker-compose.yaml
environment:
  TZ: Asia/Shanghai
```

## Environment Variables

Hook handlers read env vars via `os.getenv()`. Hermes loads `$HERMES_HOME/.env` at gateway startup, so variables defined there are available. For Docker containers, also set them in `docker-compose.yaml` environment section for clarity.

## Proactive Messaging Pattern

When building a proactive messaging system inside a gateway hook:

1. **Watcher**: An asyncio task spawned at `gateway:startup` that loops with a configurable interval
2. **Mood Engine**: Optional emotional state that evolves over time, influencing message tone
3. **Cooldown Manager**: Prevents message spam with quiet hours, minimum intervals, and daily caps
4. **LLM Composer**: Generates messages via `async_call_llm(task="your_task")` which reads from `auxiliary.your_task` in config.yaml
5. **Send via adapter**: `await adapter.send(chat_id, content, metadata={...})`

### LLM Message Composition Best Practices

For casual/friend-style proactive messaging:

- **Prompt tone**: "像真人发微信，不是写作文。可以懒、可以碎、可以没头没尾。不用每句话都有信息量。"
- **Length**: 1 sentence preferred, 2 max, never 3
- **Context injection**: Inject user profile and recent context via a context file, but frame it as "仅供参考，大部分时候不需要提到"
- **Weather**: Make it explicitly optional — "天气数据仅供参考，绝大多数时候不要提。只有天气很特别时才提。"
- **Simplicity over validation**: A single LLM call + basic sanitization (strip markdown/formatting artifacts, check non-empty and length) is sufficient. Dual-LLM validation pipelines are over-engineering for casual chat.

### Discovery Content Integration

For systems that find and share interesting content:

- **Interval**: 24 hours minimum for external content discovery
- **Allow empty results**: Most discovery runs should produce nothing
- **Local sources**: Scan for TODOs, recent git commits, error logs, recently modified files
- **External sources**: arXiv API, GitHub trending, Hacker News (all have free APIs)
- **Integration**: Inject discovery results as optional context into the LLM prompt, let the LLM decide if anything is worth sharing

## Testing Hooks

### Isolated Python Test
```bash
cd $HERMES_HOME/hooks/<hook-name>
HERMES_HOME=/opt/data /opt/hermes/.venv/bin/python3 -c "
import sys; sys.path.insert(0, '.')
from your_module import YourClass
# Test instantiation and basic functionality
"
```

### Gateway Container Test
```bash
docker run --rm --name hook-test \
  --volumes-from hermes-hermes-1 \
  -e HERMES_HOME=/opt/data/hermes-alive-test-data \
  -e YOUR_ENV_VAR=true \
  --entrypoint /bin/sh hermes-agent:v0.17.0 \
  -c 'rm -f /opt/data/hermes-alive-test-data/gateway.pid
       timeout 12 hermes gateway run --replace --force --no-supervise 2>&1 || true'
# Check docker logs for hook lifecycle messages
docker logs hook-test | grep -i "hook\|your_module"
```

**Warning:** Disable production platform connections (e.g., remove `weixin:` from test config) to avoid dual-connection conflicts.

## Shared State Between Gateway and Agent Sessions

For personality/mood systems that should affect both proactive messages and agent responses:

```
/opt/data/hermes_alive_shared/    — Shared state directory
  mood_engine.py                  — Mood engine (importable from both contexts)
  mood_state.json                 — Persisted mood state
  current_mood.txt                — Human-readable mood description
```

**Hook integration:** Add `session:start` and `agent:end` events to HOOK.yaml. On `session:start`, update mood (boost energy on interaction). On `agent:end`, adjust mood based on conversation duration. The agent reads `current_mood.txt` at session start.

```yaml
# HOOK.yaml
events:
  - gateway:startup
  - session:start
  - agent:end
```

## Anti-Pattern: Over-Engineering Validation

For casual/friend-style proactive messaging, **do NOT** build dual-LLM validation pipelines or regex-based content enforcement. These were tried and removed as over-engineering:

- ❌ Dual-LLM (generate → validate → fix) — doubles cost, marginal quality gain
- ❌ Deterministic time-context checks — timezone fix solves the real problem
- ❌ Forbidden-term regex — makes messages feel like a compliance system
- ✅ Single LLM call + format sanitization + basic guards (non-empty, length, no markdown leak)

**Rule of thumb:** "Hermes Alive is a friend, not a compliance officer." If prompt quality is good, trust the LLM. If prompt quality is bad, fix the prompt — don't add more layers.

## Discovery Architecture

Structure discovery as a separate module with async collectors:

```python
class DiscoveryEngine:
    def __init__(self):
        self._external = ExternalDiscovery()  # arXiv, GitHub, HN, RSS
        self._local = LocalDiscovery()       # TODOs, git log, errors
        self._url_cache: set[str] = set()    # dedup cache
    
    async def collect(self) -> dict:
        external, local = await asyncio.gather(...)
        external = self._dedup(external)
        for item in external:
            item['score'] = _score_item(item)
        return {'external': external, 'local': local}
```

Configuration via `sources.yaml` (not hardcoded). Playwright adapter MUST be `enabled: false` by default.

## Codex Delegation Pattern

For multi-file architecture changes, delegate to Codex with:
1. Clear goal (WHAT, not HOW)
2. Explicit boundaries (files to touch, files to NEVER touch)
3. Verification command
4. Git commit instructions
5. Rollback path

Codex does the implementation; Hermes verifies the result. For small fixes (single-file, single-function), Hermes can patch directly.

See `references/hermes-alive-architecture.md` for the full reference implementation.

Before enabling a hook in production:
- [ ] All imports use absolute paths (no `from .xxx`)
- [ ] Container timezone matches user timezone (`TZ=Asia/Shanghai`)
- [ ] `.env` variables are set for all required config
- [ ] `auxiliary.<task>` entries exist in `config.yaml` if using `async_call_llm`
- [ ] Git backup committed before any file changes
- [ ] Isolated test container verified hook loads and handler executes
- [ ] Rollback path confirmed: `git checkout <commit> -- hooks/<name>/`