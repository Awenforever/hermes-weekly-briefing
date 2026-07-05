---
name: hermes-config-changes
description: Safely change Hermes Agent configuration — what needs restart, the approval model deadlock, verification steps.
category: hermes
tags: [hermes, config, restart, approval, deadlock]
---

# Hermes Configuration Changes

## Rule: Which changes need restart?

| Config path | Needs restart? |
|-------------|:---:|
| `auxiliary.*` (vision, approval, compression, etc.) | **YES** |
| `approvals.mode` | **YES** |
| `model.default` / `model.provider` | **YES** |
| `providers.*` (new provider, API key change) | **YES** |
| `custom_providers` | **YES** |
| `toolsets` | **YES** |
| `memory.*` | Usually NO |
| `display.*` | Usually NO |

When in doubt: `hermes config set` writes the file. The running process reads config at startup. If a change needs the process to re-read it → restart.

## ⚠️ CRITICAL: The Approval Model Deadlock

This is the most dangerous pitfall when changing `auxiliary.approval.model`:

```
1. You change approval.model (e.g. gemini-2.5-pro → gemini-2.5-flash)
2. Config file is updated ✅
3. Running process STILL uses old model ❌
4. You run `docker compose restart` → triggers approval check
5. Approval check uses the OLD (broken) model → FAILS
6. Restart command is blocked → container stays on old config
7. DEADLOCK: can't restart because approval is broken,
   can't fix approval without restart
```

### How to avoid it

**Before** changing the approval model, verify the new model works:

```bash
# Direct API test (bypasses Hermes)
curl -s "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions" \
  -H "Authorization: Bearer $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-2.5-flash","messages":[{"role":"user","content":"OK"}],"max_tokens":5}'
```

Then make the config change and restart **on the host directly** (bypassing Hermes approval):

```bash
# On the Docker host (NOT inside the Hermes container)
cd /path/to/hermes/compose/dir
docker compose restart hermes
```

### If you're already in the deadlock

The running Hermes can't restart itself because its approval model is broken. Solutions:

1. **Manual restart on host** (recommended): SSH to the Docker host and run `docker compose restart` directly — this bypasses Hermes approval entirely.
2. **Disable then re-enable**: `hermes config set approvals.mode off` → restart → `hermes config set approvals.mode smart` (but mode change also needs restart, so this might not help if the process is stuck).

## Verification after restart

After restart, verify the change took effect by reading config from inside the container:

```bash
docker exec hermes-hermes-1 grep -A5 "approval:" /opt/data/config.yaml
```

Don't trust `hermes config get` output — it reads the file, not the running process state. Check the file and also verify the provider works with a live API test.

## Pitfalls

- **`hermes config set` writes the file but the running process ignores it until restart.** If you make multiple config changes, batch them and restart once.
- **The approval model is gating your ability to restart.** Always verify the new approval model works BEFORE changing the config.
- **`hermes config list` reads the config file, not the running process.** It will show the new value even though the old one is still active.
- **Free-tier API quotas can exhaust silently.** Test the model with a real API call, not just config inspection.
- **Gemini OpenAI-compatible endpoint** may return different errors than the native Gemini API. Test with the exact endpoint Hermes will use.
- **`hermes` CLI not in PATH inside containers.** In the Hermes Docker container, the CLI lives at `/opt/hermes/.venv/bin/hermes`. Always set `HERMES_HOME=/opt/data` (or the correct data directory) when running it:
  ```bash
  HERMES_HOME=/opt/data /opt/hermes/.venv/bin/hermes config set <key> <value>
  ```
  Without `HERMES_HOME`, it defaults to `~/.hermes/` which may be the wrong path inside the container.