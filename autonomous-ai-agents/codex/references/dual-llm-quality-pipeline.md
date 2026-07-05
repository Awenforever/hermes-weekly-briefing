# Dual-LLM Quality Pipeline

Pattern: use a second, lower-temperature LLM call to validate and optionally repair the first call's output. Prevents semantic quality failures that regex/post-processing cannot catch.

## When to use

When LLM output correctness matters for downstream consumption — proactive chat messages, user-facing notifications, generated configs — and the failure class is semantic (not structural). Structural failures (JSON syntax, max length) should still be validated deterministically.

## Architecture

```
Input context + system prompt
  → LLM call 1: generate (temperature 0.55-0.70, creative)
  → structural sanitize (regex: strip quotes, remove code blocks, cap length)
  → LLM call 2: validate/fix (temperature 0.0-0.2, precise)
    → input includes: candidate text + quality rules + allowed/forbidden terms
    → output: structured JSON {status:"ok|fixed|reject", message:"...", issues:[...]}
  → deterministic safety net (regex guard for obvious misses)
  → return final or fallback
```

## Key design decisions

### Structured validation output
The validator must return parseable JSON — not free text. This lets the caller decide programmatically whether to accept, use the fixed version, or fall back. Free-text validation output requires another classification step (recursive problem).

### Low temperature for validation
Validation temperature should be 0.0-0.2. The validator is a reviewer/repairer, not a creative writer. Higher temperature risks the validator introducing its own errors.

### Separate task names
Use different task names (e.g. `proactive` vs `proactive_validate`) to allow different model routing. The validator can use a cheaper/faster model (deepseek-v4-flash-ascend) or a better-instruction-following model (claude-haiku-4-5) independent of the generator.

### Always validate, not "only on suspicion"
Suspicion-based validation requires a second classifier — recreating the same problem. With cooldown/mood gates limiting volume (e.g. max 5 proactive messages/day), cost impact of always-validate is negligible.

### Fallback hierarchy
1. Validator returns `ok` → use original
2. Validator returns `fixed` → use repaired
3. Validator rejects → use per-category safe template
4. Validator fails (timeout/malformed) → use global fallback

## Prompt design for the validator

The validator prompt must:
- List what to check explicitly (not "check quality" — list each dimension)
- Provide allowed/forbidden term lists for each dimension
- State KNOWN_FACTS the validator is permitted to reference
- Explicitly forbid inventing new facts while repairing
- Require the JSON output format with no surrounding text

Example validator prompt structure:
```
你是质检员。检查候选消息是否符合所有规则：

【当前时间】{time_bucket}
【允许时间表达】{allowed_terms}
【禁止时间表达】{forbidden_terms}
【已知事实】{known_facts}
【质量规则】
1. 时间匹配：语境必须符合当前时间
2. 不编造：不杜撰未提供的事实/事件/论文
3. 不假共处：不假装与收信人同处一室
4. 自然语气：朋友聊天，不是客服
5. 不强制提问：可以只分享想法
6. 格式：纯中文1-3句

【候选消息】{candidate}

完全合规 → {"status":"ok","message":"原消息","issues":[]}
有小问题 → {"status":"fixed","message":"修后消息","issues":["问题标签"]}
无法修复 → {"status":"reject","message":"","issues":["原因标签"]}

只输出JSON，不要其他内容。
```

## When NOT to use

- For structural validation (JSON syntax, schema, max length) — use deterministic checks
- When a single LLM call is already reliable (e.g. structured data extraction with strict grammars)
- When latency requirements preclude a second call
- When cost per call is prohibitive at high volume (consider sampling instead)

## References

- SIFo Benchmark: instruction-following robustness gap (arXiv 2406.19999)
- FollowEval: multi-dimensional instruction following (arXiv 2311.09829)
- CIF-Bench: Chinese instruction following (arXiv 2402.13109)