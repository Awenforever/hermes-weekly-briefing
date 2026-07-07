---
name: fifo-outbox-send-pipeline
description: Debug and implement chat/message send paths where every send call must enqueue first, count exactly once, and flush only when a token/context slot is available.
---
# FIFO outbox send pipeline

Use this skill when a message gateway or chat adapter has ordering, quota, or token-gated delivery requirements, especially when chunked messages and retry logic make direct-send implementations incorrect.

## Core invariants
1. Every `send()` call enqueues payloads into a FIFO outbox before any network I/O.
2. Each `send()` increments the reply/counter exactly once, never per chunk.
3. Actual delivery happens only while a valid token/context slot exists; otherwise leave the entry queued.
4. Footer/model tags/badges are appended per `send()`, then shared across chunks from that send.
5. `/continue`-style commands should reset the counter and trigger an outbox flush.

## Workflow
1. Identify where direct send paths bypass queueing.
2. Separate enqueue, counter increment, and flush into distinct steps.
3. Make flush FIFO and stop cleanly when token/context is unavailable.
4. Preserve inter-chunk delays if tests or downstream rate limits expect them.
5. Verify with tests that cover ordering, token gating, counter increments, and chunk delays.

## Common pitfalls
- Counting once per chunk instead of once per send.
- Appending footer/badge only to the last chunk.
- Dropping queued entries when token is missing instead of re-queuing or preserving them.
- Forgetting that a command handler may need to flush pending outbox entries.
## Verification

- Run the adapter test suite.
- Confirm FIFO order, exact counter increments, and token-gated flush behavior.
- Confirm `/continue` or equivalent command restores delivery from the queue.

## Reference Implementation

See `references/weixin-v017-implementation.md` for the WeChat (Weixin) v0.17 production adapter's concrete implementation of this pattern, including BudgetStore, SendQueue, footer format, and porting dependencies.
