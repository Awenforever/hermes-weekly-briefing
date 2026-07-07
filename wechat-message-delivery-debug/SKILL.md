---
name: wechat-message-delivery-debug
description: Debug WeChat (Weixin) message delivery and footer tag issues in Hermes Agent on UGREEN NAS.
---

# WeChat Message Delivery Debug

> **⚠️ v0.18+ fix implementations live in `hermes-wechat-enhance`.**  
> This skill covers root cause diagnosis and debugging patterns. For the actual patch-based fixes (ReplyBudgetStore, /continue, footer, model propagation, system metadata), load `hermes-wechat-enhance`. The CUSTOMIZATIONS.md there is the single source of truth for what was changed and how.

Use this skill when Weixin messages split, rate-limit, fail to send, or show the wrong footer tag (`hermes`, actual model, or `error`).

## User Preferences

- **Root cause over symptom fixes**: Do not patch individual occurrences. Trace the full data/metadata flow end-to-end to find WHY a class of messages is wrong, then fix at the source.
- **Behavioral verification over existence checks**: When writing verification scripts, test actual function behavior (class instantiation, method calls, edge cases), not just `grep` for function/class names. Extract source via `ast.get_source_segment()`, mock dependencies, and test real logic.

## What to check first

1. Search logs for send/metadata failures:
   ```bash
   grep -i "send\|weixin\|model_name\|resolved_model\|error\|rate\|chunk" /opt/data/logs/agent.log | tail -50
   ```
2. Confirm whether the message was sent as:
   - true system notice → should tag `hermes`
   - assistant/model output → should tag actual model name
   - missing metadata → will fall back to `error`

## ⚠️ Footer Principle (User Mandate)

> **"永远不要让fallback掩盖bug。Footer必须唯一准确反映内容来源。"**

Translation: Never let fallback logic mask a bug. Footer must uniquely and accurately reflect the true content source.

| Source | Footer | 
|--------|--------|
| Agent LLM response | Actual model name (e.g. `deepseek-v4-pro`) |
| System/control message | `hermes` |
| Hermes Alive proactive message | `deepseek-v4-flash-ascend` (its actual model) |
| Unknown / metadata missing | `hermes` (default to system, NOT config.yaml) |

**Forbidden**: Reading `config.yaml` `model.default` as footer fallback. This hides metadata propagation bugs by showing the default model instead of the real one.

## Tag rules

The Weixin footer logic should stay strict:
- `is_system=True` or `actor=system` → `hermes`
- non-reserved `model_name` / `model` → use that model name
- otherwise → `hermes` (not config.yaml, not `error`)

Do **not** mask missing metadata by inventing a fake model label. If the metadata chain is broken, `hermes` is the honest answer — it means "we don't know the model, so this is likely a system message."

## Verification pattern

When verifying footer correctness, use behavioral tests over existence checks:
- **Wrong**: `grep "function_name" file.py` — only proves the function exists
- **Right**: Extract source via `ast.get_source_segment()`, mock dependencies, and test actual logic with edge cases
- See `hermes-wechat-enhance/verify-v18.py` for a 63-check functional verification script that tests ReplyBudgetStore, MessageSendQueue, `_is_system_meta()`, `_footer_model_name()`, and /continue control flow with real inputs.

## Common root cause: metadata arrives too early or incomplete

There are **two distinct classes** of `"error"` footer bugs:

### Class A: Agent responses — model name not propagated

Agent responses run through `_handle_message_with_agent()` → `_run_agent()`. The
model name is resolved inside `_run_agent()`, but by the time `base.py` sends the
response via `_process_message_background()`, the metadata may not carry it.

### Class B: Slash command results — no actor/model metadata at all

When a slash command (like `/resume`, `/help`, `/compact`, etc.) returns a plain
string, the dispatch path is:

1. `_handle_message()` in `run.py` calls `_handle_resume_command()` etc.
2. The handler returns a string (e.g. `"📋 **Named Sessions**\n..."`)
3. `_process_message_background()` in `base.py` (line 1691) receives the string as `response`
4. It sends via `_send_with_retry(..., metadata=_thread_metadata)` where:
   ```python
   _thread_metadata = {"thread_id": event.source.thread_id} if event.source.thread_id else None
   ```
5. This metadata dict has **no `is_system`, `actor`, `model_name`, or `model`**
6. `weixin.py` → `send()` (line 1644) sees zero recognized fields → falls back to `"error"`

**Affected commands:** `/resume`, `/resume <name>`, `/help`, `/compact`, `/commands`,
`/profile`, `/status`, `/restart`, `/stop`, `/reasoning`, `/fast`, `/branch`,
`/background`, and any other slash command that returns a string directly.

The same issue affects the session auto-reset notice (~line 3664 in `run.py`) and
the STT-not-available notice (~line 3479) — both call `adapter.send()` with
metadata that has only `thread_id`.

**Fix approach:** Before sending any response in `_process_message_background()`,
enrich `_thread_metadata` with:
- `"is_system": True` if the response is from a slash command or system notice
- `"model_name"` from the resolved model if the response is from the agent

**Quick verification:**
```bash
grep -n "send() metadata=" /opt/data/logs/agent.log | grep -v "model_name\|is_system\|actor" | tail -20
```
Any `send()` call whose metadata dict lacks `model_name`, `is_system`, or `actor` will produce `"error"`.

A very common failure mode in Hermes is that the agent has already chosen a model, but the footer path still sees no model metadata.

### Root cause: missing metadata propagation (v0.17→v0.18 regression)

The v0.18 migration **removed two critical code blocks** that v0.17 had as custom patches. Both must exist for the footer to show the actual model name. When either is missing, the footer renders `error` (or a fake config-based fallback — see anti-pattern below).

### Block 1: run.py — set event.model_name from agent_result

In `_handle_message_with_agent()`, after `agent_result` is returned from `_run_agent()`, the model name must be propagated to the event object so `base.py` can read it later. `agent_result["model"]` contains the REAL model used (`getattr(_agent, "model")`), not a config default.

The missing code (v0.18 location: after stale-result check, before `response = agent_result.get("final_response")`):

```python
# Propagate resolved model to event for platform footer metadata
_result_model = ""
if isinstance(agent_result, dict):
    for _key in ("model_name", "resolved_model", "routed_model", "model"):
        _candidate = str(agent_result.get(_key) or "").strip()
        if _candidate:
            _result_model = _candidate
            break
if _result_model:
    setattr(event, "model_name", _result_model)
    setattr(event, "resolved_model", _result_model)
    setattr(event, "message_origin", "model")
    try:
        setattr(event.source, "model_name", _result_model)
        setattr(event.source, "resolved_model", _result_model)
    except Exception:
        pass
```

### Block 2: base.py — propagate event.model_name to _thread_metadata

In the send handler (inside `_process_message_background` or the equivalent), before `_final_thread_metadata = _mark_notify_metadata(_thread_metadata)`, the model name must be read from the event and written into the metadata dict that goes to `adapter.send()`:

```python
# Preserve the actual model used by this turn in platform send metadata
_model = ""
_source = getattr(event, "source", None)
for _candidate in (
    getattr(event, "resolved_model", None),
    getattr(event, "model_name", None),
    getattr(_source, "resolved_model", None),
    getattr(_source, "model_name", None),
):
    _candidate = str(_candidate or "").strip()
    if _candidate:
        _model = _candidate
        break
if _model:
    _thread_metadata["model_name"] = _model
```

### The metadata flow (must be intact end-to-end)

```
agent._model → agent_result["model"] → event.model_name → _thread_metadata["model_name"] → adapter.send(metadata) → weixin footer
```

If ANY link in this chain is broken, the footer has no model name.

### Anti-pattern: config.yaml fallback in footer

Do NOT add config.yaml fallback logic to the footer. Config holds the **default** model, not the **actual** model used for this specific turn. When a user routes a message to `gpt-5.5` but `config.yaml` says `deepseek-v4-pro`, the config fallback would show the wrong model. The correct fix is ALWAYS to ensure the metadata carries the real model name through the full chain above.

An `error` footer means the metadata chain is broken — fix the chain, don't paper over it.

## Cron delivery metadata propagation

Cron-style replies have a separate delivery path from normal chat. A useful pattern is:

1. Capture the resolved model from the agent result as soon as the job finishes.
2. Store it on the job object temporarily if later delivery is deferred.
3. Forward it through the delivery helper into platform senders as `metadata`.
4. Keep system notifications separate so startup/status messages still tag `hermes`.

### Delivery chain to preserve

For cron results, the model name should flow through all of these layers:

- `cron/scheduler.py` → `_deliver_result(...)`
- `tools/send_message_tool.py` → `_send_to_platform(...)`
- `tools/send_message_tool.py` → `_send_weixin(...)`
- `gateway/platforms/weixin.py` → `send_weixin_direct(...)`
- `WeixinAdapter.send(...)` → footer tag selection

If any layer drops `metadata`, Weixin falls back to `error` even when the model was actually resolved.

### Practical implementation notes

- Prefer an extensible metadata dict over a bare string so future fields can be added without another signature change.
- For Weixin, `send_weixin_direct()` should accept optional `metadata` and pass it into the adapter send calls.
- Do **not** reuse cron model metadata for system notices like startup ready or "Still working" status messages.
- System notices should keep `actor: "system"` / `is_system: True` so they intentionally render as `hermes`.

### Verification pattern for cron

Check that these cases still pass independently:
- normal assistant response → actual model name
- startup / system notice → `hermes`
- long-running status notice → `hermes`
- cron final delivery → actual model name from the resolved agent result

Tests that proved useful:
- scheduler-level test that the resolved model is forwarded into delivery
- Weixin test that the platform sender receives the forwarded metadata
- regression test for system notices so the `hermes` tag remains unchanged

## Environment / dependency pitfalls

On Debian-based NAS hosts, Python may be externally managed (PEP 668). If `pip install` fails with `externally-managed-environment`, use one of:

- a virtual environment, or
- `python3 -m pip install --break-system-packages ...` for quick repair in the system interpreter

In this session, missing test dependencies included:
- `python-dotenv`
- `aiohttp`
- `openai`

## Ready notices vs. system notices

- Startup/reset banners that are truly system-generated should stay `hermes`.
- A user-facing ready message that comes from the model should carry the real model name.
- If both appear, that is usually because there are two different send paths, not one duplicate message.

## Message splitting / rate limiting

If the issue is message splitting instead of footer tags:
- check `_split_text()` / `_split_text_for_weixin_delivery()`
- check `split_multiline_messages`
- check `send_chunk_delay_seconds` and `send_chunk_retries`
- increase delay if WeChat throttles rapid consecutive bubbles

## File map and function map

### Core files
| File | Role |
|------|------|
| `gateway/platforms/weixin.py` | WeChat adapter — `send()` (line 1644) builds footer tag from metadata |
| `gateway/platforms/base.py` | Base adapter — `_process_message_background()` (line 1663) sends responses; `_send_with_retry()` (line 1454) calls `send()` |
| `gateway/run.py` | Gateway runner — `_handle_message()` (line 2818) dispatches commands; `_handle_message_with_agent()` (line 3569) runs agent; `_handle_resume_command()` (line 6515) handles /resume |
| `gateway/stream_consumer.py` | `GatewayStreamConsumer` (line 48) — streaming delivery, receives metadata via `.metadata` attribute |

### Key functions in the tag pipeline
| Function | File:line | What it does |
|----------|-----------|--------------|
| `WeixinAdapter.send()` | `weixin.py:1644` | Builds footer tag: checks `is_system`/`actor` → `"hermes"`, then `model_name`/`model` → model name, else `"error"` |
| `_process_message_background()` | `base.py:1663` | Builds `_thread_metadata = {"thread_id": ...}`, calls `message_handler`, sends response |
| `_send_with_retry()` | `base.py:1454` | Passes `metadata` through to `self.send()` |
| `_handle_resume_command()` | `run.py:6515` | Returns string (Named Sessions / Resumed session) — NO metadata enrichment |
| `_handle_message_with_agent()` | `run.py:3569` | Runs agent, writes `resolved_model` to event, but event not propagated to metadata in base.py |
| `_run_agent()` | `run.py:8306` | Returns `agent_result` with `model` field — caller must propagate this to metadata |

### Dispatch path for slash commands
```
User sends /resume
  → run.py _handle_message() line 3124-3141: identifies command
  → run.py _handle_resume_command() line 6515: returns string (e.g. "📋 Named Sessions")
  → base.py _process_message_background() line 1691: response = await self._message_handler(event)
  → base.py line 1779: _send_with_retry(content=response, metadata=_thread_metadata)
  → base.py line 1472: self.send(content=content, metadata=metadata)
  → weixin.py send() line 1644: metadata has only thread_id → footer = "error"
```

### Dispatch path for agent responses (v0.18 — propagation MISSING by default)

```
User sends text message
  → run.py _handle_message_with_agent()
  → run.py _run_agent(): returns agent_result with "model" field (= real model from agent)
  → ❌ v0.18 MISSING: event.model_name not set from agent_result["model"]
  → base.py handler: _thread_metadata built from event.source
  → ❌ v0.18 MISSING: _thread_metadata["model_name"] not populated from event
  → adapter.send(content, metadata=_thread_metadata)
  → weixin.py send(): metadata has no model_name → footer = "error"
```

With BOTH fixes in place:

```
  → ✅ run.py: event.model_name = agent_result.get("model")
  → ✅ base.py: _thread_metadata["model_name"] = event.model_name
  → adapter.send(metadata) carries model_name → footer = actual model
```

### Three specific `"error"` messages
| Message | Source function | Why `"error"` |
|---------|----------------|---------------|
| 📋 Named Sessions | `_handle_resume_command()` line 6538 | String returned, metadata has no actor/model |
| ↻ Resumed session X | `_handle_resume_command()` line 6590 | Same — slash command result path |
| Session reset/restart notice | `_handle_message_with_agent()` line 3664 | `adapter.send()` with metadata=`{"thread_id":...}` — no actor/model |

## Useful files

- `/opt/hermes/gateway/platforms/weixin.py`
- `/opt/hermes/gateway/platforms/base.py`
- `/opt/hermes/gateway/run.py`
- `/opt/hermes/gateway/stream_consumer.py`
- `/opt/data/logs/agent.log`
