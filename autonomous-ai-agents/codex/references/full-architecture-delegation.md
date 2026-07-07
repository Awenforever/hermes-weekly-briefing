# Full Architecture Delegation Pattern

Pattern for delegating a complete multi-module architecture change to Codex.

## When to use

- 5+ files to create or modify
- Architecture-level changes (new module replacing old, new data flow)
- Design is fully settled before delegation — no back-and-forth needed
- Implementation order matters (dependencies between modules)

## Pattern

### 1. Settle design first (with user or via internal reasoning)

Don't delegate until the design is final. All decisions (data structures, module boundaries, migration strategy) should be locked.

### 2. Compose a comprehensive single prompt

The prompt must include:
- **Background**: what exists, why change
- **Final design**: data structures, module specs, constraints
- **Implementation order**: numbered sequence showing dependencies
- **Key constraints**: paths, import style, backward compatibility, IO patterns
- **All file paths**: every file that needs reading or writing

### 3. Run with gpt-5.5 for large scope

```
codex exec -m gpt-5.5 --dangerously-bypass-approvals-and-sandbox '<prompt>' 2>&1
```

Timeout: 600s+. Large implementations can take 5-10 minutes.

### 4. Verify after completion

- Check syntax: `python3 -c "import ast; ast.parse(open('file.py').read())"` for all modified files
- Check imports: `grep -rn "old_module" hooks/` to find stale references
- Check file existence: old modules deleted, new modules created
- Check SKILL.md version bump

## Example: Hermes Alive Personality Genome (v2.2 → v2.3)

- 1 new module (voice_engine.py, 539 lines)
- 2 modules deleted (mood_engine.py, message_composer.py)
- 5 modules modified (llm_message_composer, proactive_watcher, context_tracker, handler, dream_engine)
- 3 supporting files updated (logs.py, deploy.sh, SKILL.md)
- Prompt: ~200 lines of design spec + implementation order + constraints
- Model: gpt-5.5, ran to near-completion before hitting 600s timeout

## Pitfalls

- **Timeout**: Set generous timeout. If Codex hits the wall, check what was written — it may have completed most of the work.
- **Stale references**: After deletion of old modules, grep for remaining imports. Codex can miss some.
- **Multi-line strings**: If Codex patches inside SYSTEM_PROMPT or similar, check for corruption (extra `|` prefixes from git diff context).
- **One shot only**: Don't interrupt Codex mid-implementation. Let it finish or time out naturally.