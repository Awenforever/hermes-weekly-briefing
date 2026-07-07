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
- **Comprehensive audits** — delegate a deep code review + isolation test, then a follow-up task to fix everything found
- **Bulk code changes** — this is the primary workflow: delegate ALL non-trivial code modifications to Codex. The parent agent (庄奕) handles ONLY architecture decisions, planning, and final verification — never bulk implementation.

**Codex-first principle**: Codex handles all implementation. The parent agent's role is: plan → delegate to Codex → verify → delegate next task. When in doubt, delegate. Never do Codex's work yourself — it bloats your context and distracts from the architectural overview.

**Delegation workflow**: Plan the full task → split into independent subtasks → delegate ONE subtask at a time → verify it passed → delegate the next. Never batch unrelated tasks into one Codex call. Never skip verification between subtasks.

**No limits**: Never artificially cap Codex's API calls, iterations, or runtime. Codex uses its own OpenAI models (gpt-5.4/gpt-5.5), not Hermes' configured model. Give Codex whatever tools and permissions it needs. Do NOT set `max_iterations` or similar constraints unless the user explicitly asks.

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

**Codex is intentionally used for OpenAI models only** — this is the design. Codex's ChatGPT OAuth limits it to OpenAI's own models, and that's exactly why we route tasks to it: Codex gives us access to OpenAI's strongest models (gpt-5.4, gpt-5.5) that Hermes itself doesn't use. For non-OpenAI models (deepseek, etc.), use Hermes directly.

**Tiered model strategy:**

| Model | When | Task class |
|-------|------|------------|
| `gpt-5.4` | Daily driver | Normal complex tasks, code fixes, reviews, mid-size refactors |
| `gpt-5.5` | Heavy lifting | Large multi-file implementations, architecture overhauls, comprehensive audits |

```
# Normal complexity
codex exec -m gpt-5.4 --dangerously-bypass-approvals-and-sandbox "Fix the login race condition"

# Large complexity (multi-file, architecture-level)
codex exec -m gpt-5.5 --dangerously-bypass-approvals-and-sandbox "Implement the new auth module..."
```

For trivial fixes, omit `-m` to use Codex's default model.

## Full Architecture Delegation

For large multi-module implementations (5+ files, architecture-level changes), use the pattern documented in `references/full-architecture-delegation.md`. Key points:

1. Settle design fully before delegating — no back-and-forth
2. Compose a single comprehensive prompt with implementation order
3. Use `gpt-5.5` with generous timeout (600s+)
4. Verify syntax, imports, and file state after completion

## PR Reviews

Clone to a temp directory for safe review:

```
terminal(command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && gh pr checkout 42 && codex review --base origin/main")
```

## Comprehensive Audits

For deep code quality audits, use the two-round delegation pattern documented in `references/audit-and-fix-pattern.md`. Round 1 audits (read-only, no fixes) → Round 2 fixes all critical issues + verifies in isolation.

**Splitting fix rounds**: If a single "fix everything" task is too large (50+ tool calls, 3+ independent changes across many files), split into one delegation per issue rather than one massive task. Codex will hit `max_iterations` and exit without finishing if the task scope exceeds ~50 operations. A successful pattern: audit (one task) → issue-A fix (one task) → issue-B fix (one task) → verify (you).

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

### Don't artificially limit Codex

**This is the #1 user complaint.** Never set `max_iterations`, API call caps, or arbitrary timeouts on Codex calls unless the user explicitly asks. Codex uses OpenAI's own models (gpt-5.4/gpt-5.5) — it does NOT consume Hermes' configured model or API quota. The `delegation.model` and `delegation.provider` config fields in Hermes' config.yaml are for Hermes sub-agents, not for Codex CLI. Codex has its own auth and model selection.

### Codex model is independent from Hermes config

Codex CLI authenticates via ChatGPT OAuth or `OPENAI_API_KEY`, not through Hermes' provider config. Setting `delegation.model: deepseek-v4-flash-ascend` or `delegation.provider: ustc` does NOT affect Codex — it only affects Hermes' own `delegate_task` sub-agents. Codex always uses OpenAI models (gpt-5.4, gpt-5.5, o3, etc.) via its own auth.

### One task at a time, verify before next

Never batch unrelated tasks into one Codex call. The pattern is: plan → delegate ONE task → verify → delegate next. Batching causes Codex to run out of iterations with partial results. Verification between tasks catches failures early.

### Parent agent should NOT do Codex's work

The parent agent's role is architecture + planning + verification. If you find yourself implementing code changes that Codex should handle, STOP and delegate. Doing implementation work yourself bloats your context and means you're not using Codex for what it's designed for.

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

Codex with ChatGPT OAuth supports **only OpenAI models** — this is by design, not a bug. Codex is our dedicated gateway to OpenAI's models (gpt-5.4, gpt-5.5). Non-OpenAI models (deepseek, etc.) are handled by Hermes directly.

If you see:
```
ERROR: The '{model}' model is not supported when using Codex with a ChatGPT account.
```
You're trying to use a non-OpenAI model through Codex. Either pick an OpenAI model (`gpt-5.4` / `gpt-5.5`) or route the task through Hermes instead.

### Codex CLI eating shell operators from prompt text

**This is the #1 recurring failure pattern.** Codex CLI (`codex exec`) parses shell operators (`&&`, `||`, `|`, `>`, `<`) that appear in the prompt text as its OWN arguments, not as prompt content. The error looks like:

```
error: unexpected argument 'OK || echo PATCH1' found
error: unexpected argument 'Hermes' found
```

This happens when the prompt contains inline shell commands, bash snippets, or pipeline examples. Codex CLI's argument parser treats bare `&&`/`||`/`|` as shell command separators before the prompt ever reaches the LLM.

**Prevention rules:**
1. **Never** put shell one-liners with operators in Codex prompts. No `grep ... && echo OK || echo FAIL`, no `cmd1 | cmd2`, no `cmd > file`.
2. **Rewrite** all verification/execution instructions as Python scripts. Instead of "Run `docker ps && docker logs`", say "Write a Python script that calls subprocess.run for docker ps and docker logs, then execute it."
3. **Use Python as the execution language** for all steps Codex needs to perform. `python3 -c "..."` is safe — `&&` inside Python strings doesn't confuse Codex CLI.
4. **For complex multi-step procedures**, write the entire procedure as a .py file first, then tell Codex to execute that file. Never embed shell pipelines in the prompt.
5. **If you absolutely must mention shell syntax**, use quoted examples or heredoc notation, not bare operators.

**Failed patterns (do NOT use):**
```
codex exec ... "Run: docker ps && docker logs"     ← ❌
codex exec ... "git apply --check && echo OK"       ← ❌
codex exec ... "grep pattern file | wc -l"          ← ❌
```

**Safe patterns (use these):**
```
# Write a script first, then execute it
codex exec ... "Execute /tmp/my_script.py which does X, Y, Z"
codex exec ... "Use Python subprocess to run docker commands and check results"
codex exec ... "Write a verification script, save it, then run it"
```

This was discovered across 3+ failures in one session (2026-07-06) during Hermes v0.18 migration testing.

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

### Multi-line string corruption from patch operations

Codex `patch` operations can silently corrupt multi-line strings (e.g. Python triple-quoted `"""..."""` blocks like SYSTEM_PROMPT). The symptom: lines gain extra `|` or `|||` prefix characters because the patch's `old_string` partially matched a git diff context prefix. This is especially likely when modifying sections inside long string literals.

**Detection**: grep for `^||||` or `^|||` in .py files after any Codex patch that touched string content.

**Fix**: use `sed -i '158,168d' file.py` to delete the corrupted lines, or rewrite the entire string block. Then verify with `python3 -c "import ast; ast.parse(open('file.py').read())"`.

**Prevention**: when delegating changes to SYSTEM_PROMPT or other multi-line strings, ask Codex to rewrite the ENTIRE block rather than patching sub-sections.

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
