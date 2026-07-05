---
name: codex
description: "Delegate coding to OpenAI Codex CLI (features, PRs)."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Coding-Agent, Codex, OpenAI, Code-Review, Refactoring]
    related_skills: [claude-code, hermes-agent]
---

# Codex CLI

Delegate coding tasks to [Codex](https://github.com/openai/codex) via the Hermes terminal. Codex is OpenAI's autonomous coding agent CLI.

## When to use

- Building features
- Refactoring
- PR reviews
- Batch issue fixing

Requires the codex CLI and a git repository.

## Prerequisites

- Codex installed: `npm install -g @openai/codex`
- OpenAI auth configured: either `OPENAI_API_KEY` or Codex OAuth credentials
  from the Codex CLI login flow. Verify with `codex doctor`.
- **Must run inside a git repository** — Codex refuses to run outside one

For Hermes itself, `model.provider: openai-codex` uses Hermes-managed Codex
OAuth from `~/.hermes/auth.json` after `hermes auth add openai-codex`. For the
standalone Codex CLI, a valid CLI OAuth session may live under
`~/.codex/auth.json`; do not treat a missing `OPENAI_API_KEY` alone as proof
that Codex auth is missing.

## One-Shot Tasks

```
terminal(command="codex exec -s workspace-write 'Add dark mode toggle to settings'", workdir="~/project")
```

For scratch work (Codex needs a git repo):
```
terminal(command="cd $(mktemp -d) && git init && codex exec -s workspace-write 'Build a snake game in Python'")
```

## Background Mode (Long Tasks)

```
# Start in background
terminal(command="codex exec -s workspace-write 'Refactor the auth module'", workdir="~/project", background=true)
# Returns session_id

# Monitor progress
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")

# Kill if needed
process(action="kill", session_id="<id>")
```

## Key Flags

| Flag | Effect |
|------|--------|
| `exec "prompt"` | One-shot non-interactive execution, exits when done |
| `-s read-only` | Sandbox: read filesystem, no writes (default) |
| `-s workspace-write` | Sandbox: read + write within repo directory |
| `-s danger-full-access` | No sandbox restrictions |
| `-m <model>` | Model override (e.g. `gpt-5`, `o3`) |
| `--dangerously-bypass-approvals-and-sandbox` | Skip all sandboxing and approvals |

**Important**: `pty=true` is NOT needed for `codex exec` — it's non-interactive and works without a PTY. Only use `pty=true` for `codex` (interactive mode) without `exec`.

## Sandbox Setup (Docker Containers)

Codex sandbox requires `bubblewrap` (`bwrap`). In Docker containers, two things must work:

```bash
# 1. bubblewrap must be installed
apt-get install -y bubblewrap

# 2. Docker must allow user namespaces
# Container needs: --security-opt seccomp=unconfined
# Verify with: bwrap --ro-bind / / /bin/echo "works"
```

**Persistence**: If Codex is baked into the Docker image, `bubblewrap` must also be baked in. Installing at runtime with `apt-get` will be lost on container rebuild.

**Hermes Gateway context**: When running Codex from inside the Hermes gateway container, `--dangerously-bypass-approvals-and-sandbox` may trigger Hermes security filters. Prefer `-s workspace-write` with a properly configured sandbox instead.

## Model Selection

Codex v0.142.5 uses OpenAI ChatGPT OAuth by default (no API key needed). Check auth with `codex doctor`.

For heavy architecture work, use the strongest available model:
```
codex exec -s workspace-write -m gpt-5 "<task>"
```

For smaller fixes, omit `-m` to use the default model.

## PR Reviews

Clone to a temp directory for safe review:

```
terminal(command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && gh pr checkout 42 && codex review --base origin/main")
```

## Parallel Issue Fixing with Worktrees

```
# Create worktrees
terminal(command="git worktree add -b fix/issue-78 /tmp/issue-78 main", workdir="~/project")
terminal(command="git worktree add -b fix/issue-99 /tmp/issue-99 main", workdir="~/project")

# Launch Codex in each
terminal(command="codex exec -s workspace-write 'Fix issue #78: <description>. Commit when done.'", workdir="/tmp/issue-78", background=true)
terminal(command="codex exec -s workspace-write 'Fix issue #99: <description>. Commit when done.'", workdir="/tmp/issue-99", background=true)

# Monitor
process(action="list")

# After completion, push and create PRs
terminal(command="cd /tmp/issue-78 && git push -u origin fix/issue-78")
terminal(command="gh pr create --repo user/repo --head fix/issue-78 --title 'fix: ...' --body '...'")

# Cleanup
terminal(command="git worktree remove /tmp/issue-78", workdir="~/project")
```

## Batch PR Reviews

```
# Fetch all PR refs
terminal(command="git fetch origin '+refs/pull/*/head:refs/remotes/origin/pr/*'", workdir="~/project")

# Review multiple PRs in parallel
terminal(command="codex exec -s read-only 'Review PR #86. git diff origin/main...origin/pr/86'", workdir="~/project", background=true)
terminal(command="codex exec -s read-only 'Review PR #87. git diff origin/main...origin/pr/87'", workdir="~/project", background=true)

# Post results
terminal(command="gh pr comment 86 --body '<review>'", workdir="~/project")
```

## Pitfalls

### Auth file in wrong home directory

When running Codex inside a Docker container via `docker exec`, the OAuth file may be in a different user's home than the one running the command. Common case: `hermes` user's home is `/opt/data/` but `codex login` may have written auth to `/opt/data/home/.codex/auth.json`. The Codex CLI checks `~/.codex/auth.json` relative to the current user — root's home is `/root/`, hermes user's home is `/opt/data/`.

**Fix**: Copy auth.json to the running user's Codex directory:
```bash
# For hermes user inside container:
mkdir -p /opt/data/.codex && cp /opt/data/home/.codex/auth.json /opt/data/.codex/auth.json
# For root inside container:
mkdir -p /root/.codex && cp /opt/data/home/.codex/auth.json /root/.codex/auth.json
```
Verify with `codex doctor | grep auth`. Should show `auth is configured`.

### Model restriction with ChatGPT OAuth

When using Codex with ChatGPT OAuth (not API key), only OpenAI models are supported. Non-OpenAI models (e.g. `deepseek-v4-flash-ascend`, `gpt-5-codex`) fail with:

```
ERROR: The '{model}' model is not supported when using Codex with a ChatGPT account.
```

Omit `-m` to use Codex's default model, or switch to API key auth for custom providers.

### Shell quoting with SSH + docker exec

Never pass a multi-line Codex prompt through nested shell quoting (e.g. `sh -c "codex exec '...prompt with quotes...'"`) — it will break. Instead, write the prompt to a file inside the container, then pipe it:

```bash
# Step 1: Write prompt via python -c (triple-quoted strings survive SSH):
docker exec container python3 -c "
prompt = '''...multi-line prompt with 'quotes' and \"double quotes\"...'''
with open('/tmp/codex-prompt.txt', 'w') as f:
    f.write(prompt)
"

# Step 2: Run codex reading from the file:
docker exec container sh -c 'cd /repo && cat /tmp/codex-prompt.txt | codex exec -s workspace-write'
```

### Git commit blocked by sandbox

`codex exec -s workspace-write` mounts `.git` read-only in the sandbox. Codex can write source files but cannot `git commit`. If Codex reports "Unable to create .git/index.lock: Read-only file system", commit manually after Codex exits:

```bash
cd /path/to/repo && git add -A && git commit -m "feat: description"
```

### Chinese character accuracy

Codex often confuses visually similar Chinese characters (e.g. 庄奕 → 庄义, 停云 → 停雲). Always audit Codex output after completion — `grep` for expected names and fix any typos before committing. Include the exact characters in the prompt to reduce errors, but do not assume Codex will get them right.

### Sandbox failure in Docker containers (bwrap)

Inside Docker containers, Codex's `bwrap` sandbox may fail on `.git` mounts:

```
bwrap: Can't find source path /opt/data/.git: Permission denied
```

This blocks ALL shell calls (ls, find, rg, even `true`) and prevents file reads/writes even with `-s workspace-write`. Codex can still do web research and MCP calls — it just can't touch the filesystem.

**Proven workaround**: Use Codex for research/analysis only, then implement file changes yourself. Pattern:
1. Codex researches (curl tests, API discovery, web search)
2. Codex reports findings (structured YAML/JSON)
3. You implement the file changes based on Codex's findings

This was used successfully for the Hermes Alive multi-platform research task.
