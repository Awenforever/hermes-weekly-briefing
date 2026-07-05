---
name: hermes-hook-development
description: Use when developing or debugging Python hooks for Hermes Agent Gateway — import pitfalls, deployment patterns, verification, and safe editing with Codex.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, hooks, gateway, deployment, debugging, python-imports]
    related_skills: [hermes-config-changes, hermes-agent-skill-authoring, codex]
---

# Hermes Hook Development

## Overview

Hermes Gateway supports event hooks — Python handlers that fire at lifecycle events (`gateway:startup`, `session:start`, `agent:end`, etc.). Hooks live at `$HERMES_HOME/hooks/<hook-name>/` and contain `HOOK.yaml` + `handler.py`. This skill covers the pitfalls, patterns, and verification workflow for developing and deploying hooks.

## When to Use

- Writing a new gateway hook
- Debugging a hook that silently fails to start or fire
- Deploying hook code from a dev project to `/opt/data/hooks/`
- Modifying hook code in production (safe edit pattern)

## Hook Structure

```
$HERMES_HOME/hooks/<hook-name>/
├── HOOK.yaml        # name, version, events list
├── handler.py       # async def handle(event_type, context)
├── __init__.py      # optional, makes dir a package
└── <other modules>  # imported by handler or its dependencies
```

HOOK.yaml:
```yaml
name: my-hook
version: "1.0"
events:
  - gateway:startup
description: "What this hook does"
```

Handler signature:
```python
async def handle(event_type: str, context: dict):
    # event_type: "gateway:startup", "session:start", etc.
    # context: event-specific data (may be empty)
    pass
```

## ⚠️ CRITICAL: The Relative Import Pitfall

**This is the #1 cause of silent hook failures.** If you miss this, your hook will load, appear to start, and then crash on first tick with zero visible errors.

### Root Cause

The gateway hook loader (`gateway/hooks.py`) uses `importlib.util.spec_from_file_location` to load `handler.py` as a standalone module:

```python
module_name = f"hermes_hook_{hook_name}"
spec = importlib.util.spec_from_file_location(module_name, handler_path)
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module
spec.loader.exec_module(module)
```

This creates a **top-level module** with `__package__ = None`. When the handler (or any module it imports) uses relative imports like `from .mood_engine import MoodEngine`, Python raises:

```
ImportError: attempted relative import with no known parent package
```

### The Pattern That Fails

```python
# handler.py (loaded by hook system)
sys.path.insert(0, os.path.dirname(__file__))
from my_module import MyClass  # absolute import — this works!

# my_module.py (imported by handler)
from .helper import helper_fn  # RELATIVE — this FAILS!
```

### The Fix: Absolute Imports Only

All modules deployed to the flat hook directory MUST use absolute imports:

```python
# ✅ CORRECT
from helper import helper_fn
from mood_engine import MoodEngine, MoodState
from llm_message_composer import LLMMessageComposer

# ❌ WRONG — will fail in production
from .helper import helper_fn
from .mood_engine import MoodEngine
```

### Why Tests Pass But Production Fails

If your project uses a proper Python package structure (`src/my_package/` with `__init__.py`, installed via `pip install -e .`), relative imports work in tests. But when you copy the flat `.py` files to `/opt/data/hooks/<name>/`, the package context is lost.

**Rule**: The same code deployed flat = absolute imports. The same code in a proper package = relative imports are fine. Always verify in the deployment context, not the dev context.

## Safe Edit Workflow (Production Hooks)

When modifying deployed hook files:

1. **Git backup first** — iron rule:
   ```bash
   cd $HERMES_HOME && git add hooks/<hook-name>/ && git commit -m "backup: pre-edit snapshot of <hook-name>"
   ```

2. **Make the change** — prefer delegating to Codex with explicit constraints:
   ```
   - ONLY modify files under /opt/data/hooks/<name>/
   - Do NOT touch /opt/hermes/ (production source)
   - Do NOT restart anything
   - Only change specific things, nothing else
   ```

3. **Verify imports** — run a standalone Python test BEFORE restarting gateway:
   ```bash
   cd /opt/data/hooks/<hook-name> && python3 /opt/data/scripts/verify-hook-imports.py <hook-name>
   ```
   See `scripts/verify-hook-imports.py` for the verification script.

4. **Commit the fix**:
   ```bash
   cd $HERMES_HOME && git add hooks/<hook-name>/ && git commit -m "fix: <description>"
   ```

5. **Restart gateway** only after verification passes.

## Verification Checklist

After any hook change and BEFORE gateway restart:

- [ ] All modules in the hook directory import without `ImportError`
- [ ] Standalone Python test passes (run `verify-hook-imports.py`)
- [ ] Git commit exists (pre-edit backup + post-fix)
- [ ] Rollback path tested: `git checkout <backup-commit> -- hooks/<name>/`
- [ ] Gateway restart command known and ready

## Rollback

```bash
cd $HERMES_HOME
git checkout <backup-commit-sha> -- hooks/<hook-name>/
# Then restart gateway
```

## Common Pitfalls

1. **Relative imports in flat-deployed hooks.** Already covered above — this is the #1 killer.
2. **Forgetting `HERMES_HOME` when running `hermes config`.** The CLI is at `/opt/hermes/.venv/bin/hermes` and needs `HERMES_HOME=/opt/data` in containers.
3. **Modifying config without committing.** Iron rule: any persistent modification must be git-committed first.
4. **Testing in the wrong context.** Dev venv ≠ production hook directory. Always verify in the deployment path.
5. **Silent exception swallowing.** Hook errors are caught and logged but never block the gateway. A hook that crashes goes unnoticed unless you check logs. Always add explicit `print()` or logger calls for startup confirmation.

## Hook-Specific Gotchas

### gateway:startup hooks

- Fires exactly once, at gateway process start.
- The hook runs as an asyncio task — long-running work must use `asyncio.create_task()` and manage its own lifecycle.
- Access live gateway state via `_gateway_runner_ref()` from `gateway.run`:
  ```python
  sys.path.insert(0, "/opt/hermes")
  from gateway.run import _gateway_runner_ref
  runner = _gateway_runner_ref()
  adapters = runner.adapters  # Dict[Platform, BasePlatformAdapter]
  ```
- `runner.adapters` is keyed by `Platform` enum. To find a specific adapter:
  ```python
  for key, adapter in adapters.items():
      if getattr(key, "value", key) == "weixin":
          return adapter
  ```

### Weixin adapter send()

```python
await adapter.send(
    chat_id="o9cq800ipxRzd6B0ooO0zo2DJ-MU@im.wechat",
    content="消息文本",
    metadata={"model_name": "hermes", "is_system": True}
)
```