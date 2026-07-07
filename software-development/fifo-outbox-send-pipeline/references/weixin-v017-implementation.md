# WeChat (Weixin) v0.17 Send Pipeline — Concrete Implementation

This documents the v0.17 production WeChat adapter's send pipeline as a
reference implementation of the FIFO outbox pattern.

## Architecture

```
send() -> _send_queue.enqueue() -> _drain_pending()
                                       |
                                  _budget_store.increment_and_get()
                                       |
                                  _send_text_chunk(footer={count} {model})
```

## Key Components

### ContextTokenStore
- Disk-backed cache at `<HERMES_HOME>/weixin/accounts/{account_id}.context-tokens.json`
- Keyed by `account_id:user_id`
- Persisted via `atomic_json_write`

### BudgetStore (ReplyBudgetStore)
- Tracks message count per context token (max 10 per token: `_MAX_BUBBLES_PER_TOKEN`)
- `increment_and_get(account_id, chat_id)` → returns current count
- `is_exhausted(account_id, chat_id)` → True when count >= 10
- `get_valid_token(account_id, chat_id)` → returns valid context token or None

### SendQueue
- FIFO queue per `(account_id, chat_id)`
- `enqueue(account_id, chat_id, chunk, reply_to, metadata)`
- `dequeue(account_id, chat_id)` → (chunk, chat_id, reply_to, metadata)
- `has_pending()` / `pending_count()`

### Footer Format
```
{message_content}

---

`{badge}` `{model_name}`
```

- `badge` = reply budget counter (e.g., "7") or cron badge override
- `model_name` = from metadata, default "error"

## Send Flow

1. `send()` resolves model_name from metadata via `_resolve_model_name_for_footer()`
2. Media files are sent first (images, voice, documents)
3. Text is split into chunks, each enqueued with `{model_name}` in metadata
4. `_drain_pending()` dequeues in FIFO order:
   - Checks `_budget_store.is_exhausted()` — stops if token used up
   - `_budget_store.increment_and_get()` — increments counter
   - Appends footer: `` `{count}` `{model}` ``
   - Sends via `_send_text_chunk()` with context token
5. `/continue` command: resets budget counter, triggers drain

## Dependencies for Porting

To port this to another version, you need ALL of:
- `ContextTokenStore` (disk cache for tokens)
- `BudgetStore` (counter, max 10 per token)
- `SendQueue` (FIFO queue class)
- `_send_text_chunk()` (low-level WeChat API call)
- `_drain_pending()` (drain loop)
- Footer format logic
- `/continue` handler that resets counter and drains

Missing any one of these = footer shows wrong count, messages get lost, or rate limits are hit.