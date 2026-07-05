# SSH + Docker Exec Quoting Patterns

Reliable patterns for passing complex arguments through SSH → Docker → shell chains.

## The Problem

Nested quoting through `ssh host "docker exec container sh -c '...'"` breaks
invisibly — single quotes, double quotes, and backslashes compound in
unpredictable ways. Multi-line prompts with special characters are the
worst case.

## Pattern 1: Shared Docker volume (RECOMMENDED for multi-container setups)

When the local container and the target container share a Docker volume (e.g.
both mount `/volume2/Hermes-v017-current:/opt/data`), write the prompt file
locally and read it inside the target container:

```bash
# Step 1: Write prompt to shared volume (from local container)
# Use mcp_filesystem_write_file or write to the shared path directly

# Step 2: Run codex reading from the shared file
ssh host "docker exec target-container sh -c 'cd /repo && cat /opt/data/prompts/task.txt | codex exec -s workspace-write'"
```

This avoids ALL quoting issues — the prompt file contains the exact text,
no escaping needed. This only works when both containers share a volume.
Otherwise use Pattern 2.

## Pattern 2: File-based prompt via python -c

Write the prompt to a temp file inside the container, then pipe it:

```bash
# Step 1: Write prompt via python (triple-quoted strings survive SSH)
ssh host "docker exec container python3 -c \"
prompt = '''Your multi-line prompt here.
It can contain single quotes ' and double quotes \" and backslashes \.
No escaping headaches.'''
with open('/tmp/prompt.txt', 'w') as f:
    f.write(prompt)
\""

# Step 2: Run codex reading from file
ssh host "docker exec container sh -c 'cd /repo && codex exec -s workspace-write < /tmp/prompt.txt'"
```

## Pattern 3: Single-quote the outer, double-quote the inner

```bash
ssh host 'docker exec container sh -c "cd /repo && codex exec -s workspace-write"'
```

This works for simple commands but breaks if the inner command itself needs
double quotes (like JSON or Python strings with both quote types).

## Pattern 4: Base64 encoding (fire-and-forget)

```bash
PAYLOAD=$(echo -n "your command" | base64 -w0)
ssh host "docker exec container sh -c 'echo \$PAYLOAD | base64 -d | sh'"
```

Useful when the command contains literal newlines or control characters.

## Pattern 5: Background ssh with `&` (for Docker test containers)

```bash
ssh host 'docker run --rm --name test ...' &
sleep 8
ssh host 'docker logs test 2>&1 | tail -20'
```

The `&` detaches the first SSH so the second can run immediately.
Always `sleep` to give the container time to start.

## Anti-patterns (verified to fail)

- `ssh host "docker exec container su -s /bin/sh user -c 'codex exec ...'"` — the `su`'s `-c` quotes collide with the outer `-c` quotes
- `ssh host "docker exec container sh -c \"echo 'hello'\""` — backslash-escaped inner quotes get consumed differently by bash vs sh
- `ssh host "docker exec container sh -c 'cd && echo \"$VAR\"'"` — `$VAR` expands on the wrong host
- `ssh host "docker exec container sh -c 'codex exec \"prompt with 'quotes'\"'"` — single quotes inside single quotes break; use Prompts 1 or 2 instead