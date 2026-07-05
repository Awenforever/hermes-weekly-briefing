---
name: hermes-safe-deployment
description: "Safe development and deployment patterns for Hermes Agent modifications — isolated testing, hook-based zero-patch deployment, Docker test containers, and rollback strategies."
version: 1.0.0
---

# Hermes Safe Deployment

Safe patterns for developing and deploying modifications to Hermes Agent without risking production stability.

## Core Principles

1. **Zero-patch first**: Always seek a way to deploy without modifying Hermes core source.
2. **Isolated testing**: Never test on the production gateway—use separate containers or profiles.
3. **Env var gating**: All new behavior must be disabled by default, enabled via environment variable.
4. **Instant rollback**: Disabling must be as simple as unsetting an env var or removing a hook directory.

## Deployment Patterns

### Hook-Based (Zero-Patch)

Use Hermes's built-in `~/.hermes/hooks/` system for `gateway:startup` events.

```
~/.hermes/hooks/<hook-name>/
├── HOOK.yaml      # metadata: name, events list
└── handler.py     # async def handle(event_type, context)
```

Key facts:
- `HOOKS_DIR` = `get_hermes_home() / "hooks"` (e.g., `/opt/data/hooks/`)
- `gateway:startup` fires AFTER adapters connect, before kanban watchers start
- Handler signature: `async def handle(event_type: str, context: dict)`
- `context["platforms"]` = list of connected platform names
- Handlers are loaded at gateway startup (restart required after changes)
- Hook output goes to `errors.log`, NOT `gateway.log`
- All Python imports in the handler must be from persistent paths

### Env Var Gating

```python
def _enabled():
    return os.getenv("FEATURE_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
```

Production stays untouched—the env var isn't set.

### Accessing Live Gateway Adapters

From a hook handler or gateway-internal code:
```python
from gateway.run import _gateway_runner_ref

runner = _gateway_runner_ref()
adapter = runner.adapters.get(Platform.WEIXIN)
await adapter.send(chat_id, content, metadata=SYSTEM_METADATA)
```

For system messages on WeChat, always include metadata:
```python
{"is_system": True, "actor": "system", "message_origin": "system", "model_name": "hermes"}
```

### Hook-Based LLM Features

When a hook needs to call Hermes's auxiliary LLM API (for message generation, validation, content processing, etc.), use `async_call_llm` with a named task:

```python
from agent.auxiliary_client import async_call_llm

response = await async_call_llm(
    task="my_feature",
    messages=[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
    temperature=0.65,
    max_tokens=150,
    timeout=20,
)
content = response.choices[0].message.content
```

**Registering the auxiliary task:** Each task name (e.g., `my_feature`) needs a matching config entry. From inside the container:

```bash
HERMES_HOME=/opt/data /opt/hermes/.venv/bin/hermes config set auxiliary.my_feature.provider ustc
HERMES_HOME=/opt/data /opt/hermes/.venv/bin/hermes config set auxiliary.my_feature.model deepseek-v4-flash-ascend
HERMES_HOME=/opt/data /opt/hermes/.venv/bin/hermes config set auxiliary.my_feature.timeout 25
```

The config entry looks like:
```yaml
auxiliary:
  my_feature:
    provider: ustc
    model: deepseek-v4-flash-ascend
    timeout: 25
```

**Env var gating for multi-step LLM pipelines:** When a feature uses multiple LLM calls (e.g., generate + validate), gate each layer independently:

```python
VALIDATION_ENABLED_ENV = "FEATURE_LLM_VALIDATE"
VALIDATION_TASK_ENV   = "FEATURE_VALIDATE_TASK"    # separate config task for validator
```

This allows instant rollback per-layer (`FEATURE_LLM_VALIDATE=0` skips validation, but generation still runs).

See `references/dual-llm-validation.md` for the full generate→sanitize→validate→safety-net pipeline pattern.

## Isolated Test Environments

### Docker Test Container

```bash
# Create test data directory (persistent, no PID lock conflict)
docker exec hermes-hermes-1 mkdir -p /opt/data/hermes-alive-test-data/hooks/...

# Start test container sharing volumes but using separate HERMES_HOME subdir
docker run -d --name hermes-alive-test \
  --volumes-from hermes-hermes-1 \
  -e HERMES_HOME=/opt/data/hermes-alive-test-data \
  -e FEATURE_ENABLED=true \
  hermes-agent:v0.17.0 \
  hermes gateway run --replace --force --no-supervise
```

Key pitfalls:
- `--volumes-from` shares the PID lock file → test container MUST use a different `HERMES_HOME` subdirectory
- Two containers using same HERMES_HOME = PID lock conflict = gateway won't start
- Files in container writable layer are lost on restart → put everything on persistent volume
- Test config must NOT enable real messaging platforms unless intentionally testing delivery

### File Persistence

All deployed files must be on a Docker volume, NOT in the container's writable layer.

| Location | Persistent? |
|----------|-------------|
| `/opt/data/...` (volume) | ✅ |
| `/opt/hermes/gateway/...` (image layer) | ✅ (read-only from image) |
| Anything else | ❌ Lost on restart |

## Debugging

### Hook Handler Debugging

Hook handler `logger.warning()` and `print()` output goes to:
- `docker logs <container>` — for s6-managed output
- `<HERMES_HOME>/logs/errors.log` — for gateway application output
- `<HERMES_HOME>/logs/gateway.log` — main gateway log (handler output NOT here)
- `<HERMES_HOME>/logs/gateways/default/current` — raw stdout from s6 supervision

### Codex Integration

Codex CLI for Hermes source auditing:
- Requires `bubblewrap` package AND `--security-opt seccomp=unconfined` on Docker
- Use `codex exec -s workspace-write` for tasks that write files
- Always have Codex audit before modifying

## Rollback

For hook-based deployments: `rm -rf <HERMES_HOME>/hooks/<hook-name>/` + restart gateway.

For source patches: revert the commit or unset the env var gate.