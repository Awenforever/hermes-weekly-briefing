# Dual-LLM Validation Pipeline

Pattern for quality-controlling LLM-generated content from hooks: generate (high-temp) → sanitize → validate (low-temp, JSON output) → safety net → deliver.

## Motivation

LLMs are inherently poor at strict multi-constraint following (see SIFo Benchmark, FollowEval, CIF-Bench). Adding more prompt strictness doesn't reliably solve this. Instead, use a second LLM call at low temperature with a JSON-schema'd output to validate and optionally fix the candidate output.

## Pipeline

```
Generation (temp 0.6-0.7)
  → Sanitization (regex: strip quotes, role prefixes, markdown, special tags)
  → Validation (temp 0.1, JSON output: {status: ok|fixed|reject, message, issues})
  → Deterministic safety net (regex blacklist for forbidden terms)
  → Fallback chain (bucket-safe template → global fallback → heartbeat)
```

## Validator Prompt Design

The validator is NOT a creative writer — it's a quality checker. Its system prompt should enumerate concrete rules with pass/fail criteria:

```
1. Time awareness: no terms from FORBIDDEN_TIME_CONTEXT
2. No fabricated facts beyond KNOWN_FACTS
3. No false co-presence (running on NAS, can't say "I see you")
4. Friend tone, not assistant/counselor/tech-support
5. Don't default to questions
6. 1-3 sentences, no markdown, no role names
```

Input to validator includes:
- `CURRENT_TIME_BUCKET` + `ALLOWED_TIME_CONTEXT` / `FORBIDDEN_TIME_CONTEXT`
- `WEATHER` (or `WEATHER_UNAVAILABLE`)
- `KNOWN_FACTS` (exhaustive list — validator must not go beyond these)
- `CANDIDATE_MESSAGE`

## Fallback Chain

Priority order when the pipeline fails:
1. Validator says `ok` or `fixed` → use its output
2. Validator says `reject` → use bucket-safe template (per time-of-day)
3. Bucket template fails safety net → global fallback ("嘿，我在。")
4. Everything fails → heartbeat message

## Config Requirements

```yaml
auxiliary:
  my_feature:           # generation task (higher temp)
    provider: ustc
    model: deepseek-v4-flash-ascend
    timeout: 25
  my_feature_validate:  # validation task (lower temp)
    provider: ustc
    model: deepseek-v4-flash-ascend
    timeout: 15
```

## Cost

Two LLM calls per tick. At 300s (5min) interval: ~12/day for generate, ~12/day for validate = ~24 calls/day. Cheap models (flash variants) make this negligible.

## Disable Validation

Set env var `FEATURE_LLM_VALIDATE=0` to skip the validation pass — falls through to deterministic safety net + templates.