---
name: hermes-wechat-enhance
description: "Use when working on Hermes WeChat gateway enhancements: JSONL message capture, /continue pass-through, footer with context-token count + model name, and patch management (001-005 for v0.18 migration)."
version: 4.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags:
      - hermes
      - wechat
      - gateway
      - patches
      - hooks
    related_skills:
      - hermes-alive
---

# Hermes WeChat Enhance

## Overview

This skill packages Hermes WeChat enhancement artifacts without modifying the production gateway tree by default. It combines hook-based JSONL capture with a five-patch gateway customization set that restores the v0.17 feature surface on Hermes `v2026.7.1`.

### Contents

- `hooks/hermes-wechat-enhance/`: Hermes hook package. Subscribes to `agent:start` and `agent:end` only and captures inbound/outbound messages to JSONL store.
- `hermes_wechat_enhance/`: self-contained Python helpers used by the hook handler.
- `patches/001-weixin-continue-hook.patch`: /continue interception. **Must be applied LAST.**
- `patches/002-weixin-footer-hook.patch`: Inline footer model name from metadata.
- `patches/003-gateway-system-metadata.patch`: Tag system messages `is_system=True`.
- `patches/004-gateway-model-propagation.patch`: `agent.model -> event -> metadata` chain.
- `patches/005-weixin-send-queue.patch`: `ReplyBudgetStore + MessageSendQueue + footer count`.
- `CUSTOMIZATIONS.md`: Complete modification checklist plus upgrade protocol.
- `scripts/install.sh`: One-command install (version detect -> git pristine -> apply patches -> hooks).
- `scripts/update.sh`: Revert to pristine -> apply new patches -> restore user changes.
- `scripts/uninstall.sh`: Git checkout pristine -> remove hooks.
- `scripts/check-consistency.sh`: Audit patches vs docs cross-references.
- `verify-v18.py`: Functional verification for the v2026.7.1 patch set.
- `references/development-blueprint.md`: Cross-session recall anchor for architecture, conventions, lifecycle, and task tracking.

## When to Use

Use this skill when you need one or more of the following on Hermes WeChat:

- JSONL capture of inbound and outbound messages via hooks.
- Inline WeChat footer attribution with context-token count and real model name.
- `/continue` pass-through that drains the queued outbound chunks instead of routing to the agent.
- System-vs-model footer separation based on structured metadata.
- A reproducible patch workflow for Hermes `v2026.7.1` migration and upgrade audits.

## Install Hooks

Install by copying or symlinking the hook directory into the Hermes hook scan path:

```bash
mkdir -p ~/.hermes/hooks
ln -sfn /opt/data/skills/hermes-wechat-enhance/hooks/hermes-wechat-enhance ~/.hermes/hooks/hermes-wechat-enhance
```

Make the helper package importable by the gateway hook runtime:

```bash
export PYTHONPATH="/opt/data/skills/hermes-wechat-enhance:${PYTHONPATH:-}"
```

**Note:** The `hermes-wechat-enhance` hook also requires `PYTHONPATH` to include the skill directory. Without it, the hook handler's imports fail with `ImportError`. Set this in your Dockerfile or environment configuration:

```dockerfile
ENV PYTHONPATH="/opt/data/skills/hermes-wechat-enhance:${PYTHONPATH}"
```

Restart Hermes gateway after installing the hook.

## Message Storage

The hook stores captured messages in:

```text
~/.hermes/wechat_enhance/messages.jsonl
```

Each record includes `message_id`, `platform`, `user_id`, `chat_id`, `session_id`, `direction`, `content`, `timestamp`, and `model_name`.

## Applying Patches

All five patches must be applied in order **(002->003->004->005->001)** to restore the current feature set on Hermes `v2026.7.1`. Patch 001 must remain last because it depends on `_drain_pending()` and `_safe_id()` added by patch 005.

```bash
cd /opt/hermes
# Check each patch
for p in 002 003 004 005 001; do
  git apply --check /opt/data/skills/hermes-wechat-enhance/patches/${p}-*.patch
done

# Apply in correct order
for p in 002 003 004 005 001; do
  git apply /opt/data/skills/hermes-wechat-enhance/patches/${p}-*.patch
done

# Verify
python3 /opt/data/skills/hermes-wechat-enhance/verify-v18.py /opt/hermes/gateway
```

### Patch Versioning

When upgrading Hermes to a new version, patches may need regeneration if `weixin.py` changed:

```text
patches/
├── 001-weixin-continue-hook.patch        ← current (latest Hermes version)
├── 001-weixin-continue-hook.v017.patch   ← archive: v0.17 compatible
├── 002-weixin-footer-hook.patch          ← current
├── 002-weixin-footer-hook.v017.patch     ← archive: v0.17 compatible
└── CHANGELOG.md                          ← record per-version adaptations
```

**Upgrade workflow:**
1. Run `git apply --check` for both patches on the new Hermes version.
2. If clean, no action is needed.
3. If not, regenerate patches for the new version, archive old ones with a version suffix, and update `CHANGELOG.md`.

Patches were regenerated for `v2026.7.1` on `2026-07-06`. See `references/v018-weixin-changes.md`.

## Hermes Version Compatibility

| Hermes | Patch status | Notes |
|--------|-------------|-------|
| v0.17.0 | `.v017.patch` (archived) | Initial patch set, production |
| v2026.7.1 | `.patch` (current) | Patches regenerated and verified |
| v2026.6.19 | untested | Should be close to v2026.7.1 |

Hermes uses date tags, not semver. Earlier "v0.18" references map to `v2026.7.1`. See `references/v018-migration-pitfalls.md` for config-format and container-start differences.

## Common Pitfalls

### Model Sourcing Principle

**Footer model MUST come from the actual model used by the agent, never from `config.yaml`.**

`agent_result["model"]` <- `getattr(_agent, "model", None)` <- the real model. `config.yaml` `model.default` is only a static fallback and will silently lie when model routing or session override changes the actual model.

`error` or `hermes` in the footer means metadata did not contain a model name. The fix is to repair model propagation in the gateway, not to add a config fallback.

**Principle:** Read the real model from the agent object. Never fall back to config. Config is not the truth.

### Migration Debugging Philosophy

**Root cause over piecemeal fixes.** For a Hermes version migration, do a full three-way diff audit:

1. Clone official source for both old and new Hermes versions.
2. Diff production vs official on the old version to enumerate the full customization set.
3. Diff the patched test tree vs official on the new version.
4. Cross-reference every customization to either a patch or an explicit skip reason.
5. Verify hooks independently from patches.

This was required during the `v0.17 -> v2026.7.1` migration because piecemeal debugging missed the `/continue` break, hook-loading failure, and footer semantic regressions.

### Footer Controls

The Weixin footer patch reads metadata directly. If `is_system` is true, the footer shows `hermes`. Otherwise it uses this strict fallback chain:

1. `HERMES_WECHAT_FOOTER_MODEL_NAME`
2. `metadata.model_name`
3. `metadata.resolved_model`
4. `metadata.routed_model`
5. `metadata.model`
6. `"hermes"`

**`config.yaml` fallback is forbidden.** If metadata lacks a model name, the footer should stay honest and surface the propagation bug.

### Startup and Hook Loading

If the gateway omits `--accept-hooks`, the hooks will not load and Hermes Alive startup notification logic will never run. Start the gateway with:

```bash
hermes gateway run --no-supervise --accept-hooks -v
```

Verify with:

```bash
docker logs <container> 2>&1 | grep "hooks"
```

### Docker Build Pitfalls

When building a patched image from `hermes-agent:v2026.7.1`:

1. `git` user identity must be configured before any commit in the image build.
2. The `patch` CLI is not installed; use `git apply`.
3. s6-overlay can override your custom startup command unless you bypass the entrypoint.
4. `--user 0:0` is ineffective under the default s6 entrypoint.
5. NAS build context permissions can block Docker from reading the source tree.

Reference commands and full deployment notes live in `references/docker-build-and-test.md` and `references/side-by-side-testing.md`.

### Testing Deployment Pitfalls

- Do not use `--replace --force` for side-by-side test startup; it creates PID-file races with s6 restarts.
- Check both `$HERMES_HOME/logs/gateway.log` and `$HERMES_HOME/logs/gateways/default/current`.
- For isolated test homes, set `GATEWAY_ALLOW_ALL_USERS=true` instead of copying production `state.db`.
- Pre-create cache directories before `exec hermes gateway run` when wrapping in `sh -c`.

### WeChat Emoji Convention

WeChat emojis appear in the message stream as `[Name]` brackets such as `[Trick]` and `[Smile]`. They are platform-native emoji tokens, not feature markers or command names.

## Verification Checklist

- Hook symlink exists under `~/.hermes/hooks/hermes-wechat-enhance`.
- `PYTHONPATH` includes `/opt/data/skills/hermes-wechat-enhance`.
- All five patches pass `git apply --check` in the required order.
- `python3 /opt/data/skills/hermes-wechat-enhance/verify-v18.py /opt/hermes/gateway` passes.
- Gateway starts with `--accept-hooks`.
- Real WeChat testing confirms footer rendering and `/continue` behavior in the client, not just in logs.

## Upgrade Resources

- `CUSTOMIZATIONS.md`: Complete modification checklist and upgrade protocol. Read this first during a version migration.
- `references/v017-full-audit.md`: Line-level diff methodology used for the `v0.17 -> v2026.7.1` migration audit.
- `references/v018-model-propagation-bug.md`: Root-cause record for the footer model propagation break.
- `references/v018-weixin-changes.md`: Official `weixin.py` delta that forced patch regeneration.
- `references/development-blueprint.md`: Current architecture, lifecycle, and status tracking.

## v0.17 Production Audit (Full — 2026-07-07)

Full three-way diff: official `v0.17.0` vs production `v0.17`, then official `v2026.7.1` vs patched `v2026.7.1`. **28 customizations across 3 files, about 539 lines total.**

### weixin.py (20 items, +371 lines)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **ReplyBudgetStore** | Per-token message counter (10/token), persisted to disk |
| 2 | **MessageSendQueue** | In-memory FIFO queue for outbound text chunks |
| 3 | **Footer: count + model** | `` `{count}` `{model}` `` appended to each message |
| 4 | **/continue drain** | `/continue` intercepts in intake -> `_drain_pending()` -> return early |
| 5 | **inbound token->budget** | New context token resets counter for that user |
| 6 | **Protocol leak guard** | Replaces raw tool JSON with Hermes notice (skipped in v2026.7.1) |
| 7 | **send()->queue->drain** | Text chunks enqueued, drained with budget and footer |
| 8 | **Footer metadata-only** | Attribution via `metadata.is_system`, never content heuristics |
| 9 | **Cron badge override** | Cron messages use custom badge (skipped) |
| 10 | **Image metadata fix** | Images get `footer_metadata` |
| 11 | **Control command dedup bypass** | `/approve`, `/deny`, `/steer`, `/continue` and peers bypass content dedup |
| 12 | **Content heuristic disabled** | `_content_looks_like_system_error()` always returns `False` |
| 13 | **Budget store init + restore** | `ReplyBudgetStore` created in `__init__`, restored in `connect()` |
| 14 | **Footer model resolution** | `_resolve_model_name_for_footer()`: system -> `hermes`, else metadata |
| 15 | **Config fallback removed** | Final fallback is `"hermes"`, never `config.yaml` |
| 16 | **Queue metadata footer** | Per-chunk footer attribution in the drain loop |
| 17 | **Footer format** | `chunk + "\\n\\n---\\n\\n`{count}` `{model}`"` |

### base.py (5 items, +85 lines)

| # | Feature | Description |
|---|---------|-------------|
| 18 | **_mark_hermes_system_notify_metadata** | Marks slash-command/control responses as Hermes-authored |
| 19 | **Metadata always dict** | Ensures `_thread_metadata` is a dict, never `None` |
| 20 | **Model name propagation** | `event.model_name/resolved_model -> _thread_metadata` |
| 21 | **Slash command system tag** | Command results inherit session model, then force `hermes` attribution |
| 22 | **Final send origin metadata** | Command -> system, agent response -> model |

### run.py (4 items, +83 lines)

| # | Feature | Description |
|---|---------|-------------|
| 23 | **_non_conversational_metadata** | Lifecycle/status/platform messages -> `is_system=True` for Weixin |
| 24 | **Agent result model propagation** | `agent_result["model"] -> event.model_name -> metadata` |
| 25 | **Model-origin thread metadata** | Model name injected into `_model_thread_metadata` |
| 26 | **Startup ready notification** | `HERMES_WEIXIN_STARTUP_READY_NOTIFY` controls gateway ready message |

See `references/v017-full-audit.md` for the full methodology and line-level audit procedure.

## Notes

- `MessageStore` is self-contained and uses only Python standard library modules.
- Do not deploy test containers or modify a running gateway without explicit user approval.
- Codex CLI prompt strings should not embed shell operators like `&&` or backticks; write complex logic to a script first.
