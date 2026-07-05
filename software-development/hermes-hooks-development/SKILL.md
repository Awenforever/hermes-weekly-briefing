---
name: hermes-hooks-development
description: "Build, test, and deploy gateway event hooks for Hermes Agent. Covers the complete hook lifecycle: discovery, flat-deployment import pitfalls, Codex delegation patterns, and the user's preference for simplicity over over-engineering."
version: 1.0.0
author: agent
tags: [hermes, hooks, gateway, development, codex, proactive]
---

# Hermes Hooks Development

Building extensions for Hermes Agent via the gateway event hook system — `~/.hermes/hooks/<name>/` with `HOOK.yaml` + `handler.py`.

## Critical Pitfall: Relative Imports in Flat-Deployed Hooks

**THE #1 BUG**: The gateway hook loader uses `importlib.util.spec_from_file_location(module_name, handler_path)` to load `handler.py` as a standalone module. The handler's `__package__` is `None`. When the handler does `sys.path.insert(0, _HOOK_DIR)` and then `from some_module import ...`, the imported module is a TOP-LEVEL module.

If any sub-module uses `from .other_module import ...` (relative import), it will fail with:
```
ImportError: attempted relative import with no known parent package
```

**Rule**: ALL imports in hook-deployed files MUST be absolute (`from mood_engine import ...`), NEVER relative (`from .mood_engine import ...`).

This is different from project-source code where `pip install -e .` provides a proper package context. Tests pass in the project but fail in deployment — always verify imports in the deployed flat-directory context.

## User's Design Preferences

This user (停云) has strong opinions about design simplicity:

- **"过度设计" (over-engineering) is the cardinal sin.** When in doubt, simplify.
- **Trust LLM prompt over regex for content quality.** Don't add deterministic content checks that duplicate what a good prompt can handle. Regex is for format hygiene only (markdown leaks, empty output, length caps), not content judgment.
- **Test in isolation before production.** Use isolated Docker containers (`--volumes-from`) with separate `HERMES_HOME` before touching the live gateway.
- **Codex for complex changes.** Multi-file refactors with clear boundaries go to Codex via `delegate_task`. Provide: exact files to touch, files to NOT touch, git backup requirement, verification commands, and rollback path.
- **"观察期" (observation period) for architecture decisions.** Freeze architecture, document relationships, observe for 2-3 weeks before merging/consolidating overlapping systems.

## Codex Delegation Template

For complex hook development delegated to Codex, provide this structure:

```
goal: "What to build"
context: |
  ## CONTEXT (explain current state)
  ## FILES TO MODIFY (list exact paths)
  ## FILES TO NOT TOUCH (explicit deny-list)
  ## ABSOLUTE CONSTRAINTS
  ## VERIFICATION (exact commands to run after)
  ## GIT (backup before, commit after)
  ## ROLLBACK (exact command)
toolsets: ["terminal", "file"]
```

Always include `cd /opt/data && git add -A && git commit -m "backup: pre-<change>"` before Codex starts.

## Hook Development Workflow

1. **Design** → Plan the hook lifecycle (which events? what state?)
2. **Develop** → Build files in project repo first (`/home/vive/Work/Hermes/YYYY-MM-DD-name/`)
3. **Test imports** → Verify in flat-deployment context:
   ```bash
   cd /opt/data/hooks/<hook-name> && python3 -c "
   import sys; sys.path.insert(0, '.')
   from your_module import YourClass  # Must use absolute imports
   "
   ```
4. **Isolated gateway test** → Docker container with `--volumes-from`, separate `HERMES_HOME`, fake chat IDs:
   ```bash
   ssh NAS "docker run --rm --name test \
     --volumes-from hermes-hermes-1 \
     -e HERMES_HOME=/opt/data/test-data \
     -e HERMES_PROACTIVE_PLATFORM_ENABLED=true \
     -e HERMES_PROACTIVE_WEIXIN_CHAT_ID=test-only \
     hermes-agent:v0.17.0 \
     -c 'hermes gateway run --replace --force --no-supervise' 2>&1 | grep 'hook\|alive\|watcher'"
   ```
5. **Git backup** → Always commit before deployment
6. **Deploy** → Copy to `$HERMES_HOME/hooks/<name>/`, update config/env, restart gateway
7. **Verify** → Check gateway logs for hook loading and execution

## Hook Events Reference

| Event | When | Context |
|-------|------|---------|
| `gateway:startup` | Gateway process starts | `{platforms: [...]}` |
| `session:start` | New session created | `{platform, user_id, chat_id, session_id, message}` |
| `session:end` | Session ends | `{platform, user_id, chat_id, session_id}` |
| `agent:start` | Agent begins processing | `{platform, user_id, chat_id, session_id, message}` |
| `agent:end` | Agent finishes processing | `{platform, user_id, chat_id, session_id, response}` |
| `agent:step` | Each tool-calling loop iteration | (same as agent:start) |
| `command:*` | Any slash command | Command-specific |

Handler signature: `async def handle(event_type: str, context: dict) -> None`

## Key Patterns

### Using Gateway Internals Without Modifying Source
```python
# In handler.py
import sys; sys.path.insert(0, "/opt/hermes")  # Only if needed
from gateway.run import _gateway_runner_ref

runner = _gateway_runner_ref()
weixin_adapter = runner.adapters[Platform.WEIXIN]
await weixin_adapter.send(chat_id, content, metadata={"is_system": True})
```

### Lazy Initialization with Graceful Degradation
```python
def _get_component(self):
    if self._component is None:
        try:
            from component import Component
            self._component = Component()
        except Exception:
            logger.exception("Failed to init component")
            self._component = False  # Sentinel: tried and failed
    return None if self._component is False else self._component
```

### Config for Auxiliary LLM Tasks
```yaml
# config.yaml
auxiliary:
  my_task:
    provider: ustc
    model: deepseek-v4-flash-ascend
    timeout: 25
```
Then in code: `await async_call_llm(task="my_task", messages=[...])`