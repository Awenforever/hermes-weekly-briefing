---
name: hermes-smart-model-routing
description: Configure Hermes to route simple turns to a cheap model while keeping the primary model for complex work. Useful when mixing a strong primary model with a cheaper custom provider such as USTC/DeepSeek.
category: hermes
---

# Hermes Smart Model Routing

Use this when you want Hermes to keep a strong primary model for complex work, but automatically send short/simple turns to a cheaper model.

## When to use
- You want a primary model for deep reasoning, coding, or tool-heavy work.
- You have a cheaper provider/model for short, casual, or low-risk prompts.
- You want routing to happen automatically based on prompt length and complexity.

## Configuration pattern
In `config.yaml`:

```yaml
smart_model_routing:
  enabled: true
  max_simple_chars: 160
  max_simple_words: 28
  cheap_model:
    provider: ustc
    model: deepseek-v4-pro
```

## Recommended workflow
1. Keep the primary model unchanged.
2. Choose one reliable cheap model for short prompts.
3. Enable `smart_model_routing`.
4. Start with conservative thresholds (`160 chars`, `28 words`).
5. Verify with a short prompt like `hi` or `what time is it?`.
6. Make sure there is only one active `smart_model_routing:` block in YAML; later duplicate blocks can silently overwrite the first one.
7. If the TUI shows the "wrong" model after switching, check for a lingering session-level `/model` override. Re-run `/model <current-model>` (or `/model <current-model> --global` if you want it persisted) to realign the session display with the config.

## Related model layers
- **delegation.model / delegation.provider** controls subagents spawned by `delegate_task`.
- **auxiliary.*.provider / auxiliary.*.model** controls background helpers like compression, web_extract, session_search, flush_memories, vision, etc.
- Keep smart routing separate from delegation and auxiliary; they solve different problems and should not be tuned together by accident.
- For custom providers, a provider alias such as `ustc` can be valid if it resolves through `custom_providers` / runtime provider lookup.

## What counts as "simple"
Hermes' routing logic is conservative. It avoids the cheap model for prompts containing:
- code fences or inline code
- URLs
- obvious debugging / implementation / refactor / test / docker / tool keywords
- long prompts or multi-line prompts

## Verification
- Check the active config in `config.yaml`.
- Confirm `smart_model_routing.enabled: true`.
- Confirm `cheap_model` is a populated single dict, not a list.
- Send a short prompt and verify the route label looks like `smart route → <model> (<provider>)`.
- For custom providers, verify the runtime alias matches the provider name used in `cheap_model.provider` (for example, `ustc`).
- If routing seems inactive, inspect the resolved route output before changing thresholds.

## Pitfalls
- If the provider name is wrong, routing may look enabled but fail at runtime.
- If the prompt is too long or contains code/debugging keywords, Hermes will keep using the primary model.
- `cheap_model` currently supports only one route; multiple cheap models are not supported without code changes.
- A custom provider may need its runtime alias to match the name used in `cheap_model.provider`.
- Duplicate YAML blocks for `smart_model_routing` can override the intended setting and make it look like routing is off.

## Notes
This is best used as an optimization layer, not as a replacement for the primary model.
Keep the cheap model conservative and low-risk.
