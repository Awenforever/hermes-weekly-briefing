# Testing Deployment Pitfalls

Use this reference when validating deployment behavior without touching the running Hermes gateway.

## Safe Deployment Rules

- Never test deploys against the live hooks directory unless the user explicitly approves it.
- Use `HOOK_DIR` and `SHARED_DIR` overrides for isolated tests.
- Do not start containers, restart production services, or mutate `/opt/data/hooks/hermes-alive/` in a live environment without permission.

## Isolation Pattern

```bash
HOOK_DIR=/tmp/test-hooks SHARED_DIR=/tmp/test-shared bash scripts/deploy.sh
```

## Common Failure Modes

- **False confidence from cached imports**: Python may keep already-loaded modules in memory even after source files were removed. Verify the deployed files on disk, not only process behavior.
- **Log-lock mismatch**: readers and writers must use the same lock name for `proactive_log.jsonl`.
- **Guard regressions**: confirm the last-speaker check is directional, not just timestamp-based.
- **Voice migration drift**: after migration from `mood_state.json`, verify low-value dimensions did not collapse below intended floors.
