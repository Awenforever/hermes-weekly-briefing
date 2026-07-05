# Audit-and-Fix Delegation Pattern

Two-round Codex delegation for comprehensive code quality improvement.

## Round 1: Comprehensive Audit

Goal: A single Codex task that reads every file, does static analysis, AND runs a real isolation test.

```python
delegate_task(
    goal="""Audit <project> for two aspects:
    1. Functional completeness — read all source files, check imports, 
       dead code, async correctness, error handling, edge cases, hardcoded paths
    2. Isolation environment test — copy to temp dir, simulate fresh install,
       run deploy/verify, document every failure
    
    Output: severity-tagged issues (P0/P1/P2) with file/line/repair guidance.
    Do NOT auto-fix — just report.""",
    context="""Background: <what the project does, where files live, key constraints>
    Audit dir: <absolute path>
    Do not modify files. Test in /tmp/<project>-audit/.""",
    toolsets=["terminal", "file", "web"]
)
```

**Key details for the audit context:**
- Project directory, file count, language (Python/JS/etc.)
- Deployment method (deploy.sh, Docker, etc.)
- Environment (Python version, package manager, OS)
- Known constraints (no venv support, hardcoded paths, Docker dependency)

## Round 2: Fix + Verify

Goal: Fix every P0 and critical P1, then prove it works.

```python
delegate_task(
    goal="""Fix all P0 blocking issues and critical P1 issues from the audit.
    Then verify: (1) local function normal (2) isolation install test passes 
    (3) code clean. Sync runtime files. Git commit.""",
    context="""Audit results: <paste Round 1 output>
    Source dir: <path>
    Runtime dir: <path> (sync fixes here too)
    Git repos: <paths> (commit after each fix batch)
    Testing: run verify.sh, run deploy.sh in isolation,
    check import chain (all modules import successfully).""",
    toolsets=["terminal", "file", "web"]
)
```

## Proven Results

Applied to Hermes Alive skill (15 Python files, ~2500 LOC):
- Round 1: 28 tool calls, 10 min — found 4 P0 + 9 P1 + 5 P2, plus 16 missing env vars
- Round 2: 50 tool calls, 14 min — fixed all 9 critical issues, verified isolation deploy, committed

## Pitfalls

- **Audit must NOT auto-fix** — say "do not modify files" explicitly. Codex defaults to fixing, which muddies the audit results.
- **Provide the exact P0/P1 list in Round 2 context** — don't make Codex re-read the audit, just paste the issues.
- **Isolation test dir matters** — use `/tmp/` not a subdirectory of the project, to catch hardcoded path bugs.
- **Git commit discipline** — remind Codex to commit after each batch of fixes. A 14-min session without commits is risky.