---
name: hermes-safe-deployment
description: "Safe development and deployment patterns for Hermes Agent modifications — isolated testing, hook-based zero-patch deployment, Docker test containers, and rollback strategies."
version: 1.0.0
---

# Hermes Safe Deployment

Safe patterns for developing and deploying modifications to Hermes Agent without risking production stability.

## Core Principles

1. **Zero-patch first**: Always seek a way to deploy without modifying Hermes core source.
2. **Isolated testing**: Never test on the production gateway—use separate containers, temp directories, or profiles. **CRITICAL: never run destructive commands (`rm -rf`, `mv`, overwrite) on `/opt/data/hooks/` or `/opt/data/hermes_alive_shared/` during testing.** Even if you immediately restore files, runtime state files (voice_state.json, recent_context.json) may be lost. Use env-var overrides (`HOOK_DIR=/tmp/test-hooks SHARED_DIR=/tmp/test-shared`) to redirect all paths.
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

### Python Unit Test Isolation (Lightweight)

For hook components that only depend on safe_io (file read/write with locks), skip Docker containers and test directly in a temp directory:

```python
import tempfile, shutil
from pathlib import Path

TEST_DIR = Path(tempfile.mkdtemp(prefix="voice_test_"))
SHARED_DIR = TEST_DIR / "hermes_alive_shared"
SHARED_DIR.mkdir(parents=True)
os.environ["HERMES_ALIVE_SHARED_DIR"] = str(SHARED_DIR)

# Override module-level paths before importing
import voice_engine
voice_engine.SHARED_STATE_PATH = SHARED_DIR / "voice_state.json"
voice_engine.OLD_MOOD_STATE_PATH = SHARED_DIR / "mood_state.json"
```

Key pattern: import the module, then overwrite its `SHARED_STATE_PATH` / `OLD_MOOD_STATE_PATH` module-level constants BEFORE calling any functions that read/write state. This redirects all file I/O to the temp directory.

Coverage checklist for hook unit tests:
- Fresh initialization (state file creation, all dims in range)
- State persistence (reload preserves values)
- Core event handlers (all mutation types)
- Boundary clamping (push extreme values, verify [0,1])
- Evolution/mutation log integrity
- Migration path (old format → new format)
- Signal extraction (input → output correctness)
- Snapshot formatting (prompt injection output)
- Import chain (all modules importable without broken refs)

Clean up with `shutil.rmtree(TEST_DIR, ignore_errors=True)`.

### Codex Audit Before Deploy

For architecture-level changes (new modules, deleted files, renamed interfaces), run a Codex audit before deploying:

```
codex exec -m gpt-5.5 --dangerously-bypass-approvals-and-sandbox "<audit prompt>"
```

Audit prompt must include:
1. Complete file change list (created/modified/deleted)
2. Core design decisions and data structures
3. Test results summary
4. Explicit audit checklist (old refs cleared, thread safety, migration, edge cases)

Codex will return a verdict with risk rating. Fix all HIGH and MEDIUM issues before running deploy.sh.

Proven audit checklist:
1. All old module references cleared
2. Dataclass serialization/deserialization correct
3. Thread safety (locked_read/write coverage)
4. Event wiring completeness
5. Backward compatibility / migration
6. Boundary/null handling
7. Prompt/personality preservation
8. Any potential runtime crash paths

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

**CRITICAL: Codex CLI parses shell operators in prompts as its own arguments.** Never include `&&`, `||`, `|`, backticks, or `$(...)` inside a Codex prompt string. They will be interpreted by `codex exec` as CLI arguments, not passed to the model. Instead:
- Write the logic as a Python script to a file first, then tell Codex to "read the script and execute it"
- Use `write_file` or `terminal` to create the script, then reference its path in the Codex prompt
- Keep Codex prompts to natural-language instructions only — no inline shell commands

## Docker Build Pitfalls

**git commit needs identity config.** When building Docker images that use `git init && git add -A && git commit`, add:
```dockerfile
RUN git config user.email "build@hermes.local" && git config user.name "Builder"
```
before `git commit`. Without it, `git commit` fails with `fatal: unable to auto-detect email address`.

**NAS build context permissions.** On UGREEN NAS, the data directory is mode 700, owned by container UID. User `vive` cannot read it. Copy patches to `/tmp/` first using `docker run --rm -v ... alpine cp`.

**Codex CLI prompt escaping.** Codex CLI interprets `&&`, `||`, backticks in prompts as its own arguments. Write logic as Python scripts, then ask Codex to execute the script file. Never inline shell commands in Codex prompts.

## NAS Data Migration Pattern

To clone a production data directory on UGREEN NAS without `sudo`:
```bash
# Copy via docker (runs as root inside container)
docker run --rm -v /volume2/Hermes-v017-current:/src:ro -v /volume2:/dst alpine cp -a /src /dst/Hermes-v018-test
```

To copy individual files across permission boundaries:
```bash
docker run --rm -v /volume2/Hermes-v017-current:/src:ro -v /tmp/patches:/dst alpine cp /src/skills/hermes-wechat-enhance/patches/001.patch /dst/
```

For hook-based deployments: `rm -rf <HERMES_HOME>/hooks/<hook-name>/` + restart gateway.

For source patches: revert the commit or unset the env var gate.

## Patch Migration: Always Diff First

When porting custom patches from one Hermes version to another (e.g., v0.17 → v0.18):

1. **Diff production code against the official release FIRST.** Don't guess what was changed — get the exact diff. Use `diff -u official.py production.py` or a Codex audit.
2. **List all custom modifications** grouped by feature (footer, continue, budget store, protocol guard, etc.) with their dependency chains.
3. **Check if the target version's source structure changed.** Code that was in one function may have moved, been removed, or been refactored. Don't blindly apply patches.
4. **Understand dependency chains.** Some modifications depend on new classes or data structures (e.g., `BudgetStore`, `_send_queue`). You can't port the footer without porting the counter that feeds it.

**Pitfall — Codex blindly porting patches:** Codex will write plausible-looking patches that pass `py_compile` but miss entire subsystems. A v0.17 footer patch ported to v0.18 may show the model name but silently drop the context-token counter, the send queue, and the drain mechanism. The patch appears to work at the code level but the real WeChat messages tell the truth.

**Counter-pattern:** Don't add config.yaml fallbacks to hide missing metadata. If the footer shows "error" or a wrong model, the metadata flow is broken — fix the flow, not the fallback.

## Real WeChat Testing

After any WeChat-related patch, test with actual WeChat messages in an isolated container connected to the same account. Code-level validation (`py_compile`, unit tests) is NOT sufficient. The real WeChat message is the only authoritative test.

- Start a test container with the same WeChat credentials as production
- Send messages prefixed with "测试"
- Visually verify the footer shows correct **model name + context-token count**
- Kill the test container immediately after verification

## State Migration Guards

When migrating state between systems (e.g., mood → voice engine), always add a degradation guard. Long-running state machines accumulate invalid values (decayed to near-zero, NaN from division, stuck at boundary). Blind migration copies the corruption into the new system.

**Guard pattern:**
```python
# Threshold: values below this are considered degraded/meaningless
DEGRADATION_THRESHOLD = 0.08

old_value = float(old_state.get("dimension", default))
if old_value >= DEGRADATION_THRESHOLD:
    new_state.dimension = _clamp((old_value + new_default) / 2)
# else: use freshly generated default — skip migration
```

**After migration:** rename or delete the old state file to prevent re-migration on subsequent restarts:
```python
try:
    OLD_STATE_PATH.rename(OLD_STATE_PATH.with_suffix(".json.migrated"))
except Exception:
    pass
```

**Detection:** if new system values are suspiciously close to 0 after deployment, check whether old state was degraded and migration guard didn't fire. Delete the migrated file and the old state, restart to force fresh initialization.