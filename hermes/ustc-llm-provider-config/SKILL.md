---
name: ustc-llm-provider-config
description: Discover and configure the USTC LLM endpoint for Hermes by querying the live /v1/models list, then wiring the returned model IDs into config.yaml custom_providers.
category: hermes
---

# USTC LLM Provider Configuration

Use this when the user wants Hermes to expose more USTC-hosted models in the model picker or `/model` command.

## When to use
- USTC endpoint is already reachable, but only one model appears.
- You need the authoritative model list from the live endpoint.
- You want to add per-model names/aliases in `custom_providers`.

## Discovery flow
1. Read the USTC credential from `/opt/data/auth.json`.
   - Use the `credential_pool` entry for `custom:ustc`.
   - Do not guess the token or reuse a redacted placeholder from `config.yaml`.
2. Query the live models endpoint:
   - `GET https://api.llm.ustc.edu.cn/v1/models`
   - Authorization header: `Bearer <USTC_TOKEN>`
3. Treat the returned `data[].id` values as the authoritative model IDs.
4. If the endpoint returns HTTP 401, re-check that you used the `custom:ustc` token, not another provider’s key.

## Config pattern
In `/opt/data/config.yaml`:

```yaml
custom_providers:
  - name: USTC
    base_url: https://api.llm.ustc.edu.cn/v1
    api_key: <USTC_TOKEN>
    model: deepseek-v4-pro
    models:
      qwen3.5:
        name: Qwen 3.5
      qwen-chat:
        name: Qwen Chat
      deepseek-v4-pro:
        name: DeepSeek V4 Pro
```

### Notes
- `model` is the default model for the provider.
- `models` is optional but useful when you want the picker to show friendly aliases.
- Keep the model IDs exactly as returned by `/v1/models`.
- For USTC, the endpoint may expose models such as `qwen3.5`, `qwen-chat`, `qwen-reasoner`, `qwen3.6-chat`, `qwen3.6-reasoner`, `glm-chat`, `glm-reasoner`, `glm-5.2`, `deepseek-v4-flash-ascend`, `deepseek-v4-flash-ascend1`, `deepseek-v4-pro`, `smart/default`, and `smart/reasoning`.

## Verification
After editing config:
1. Load the YAML and confirm `custom_providers` is a list.
2. Confirm the USTC entry has the expected `base_url` and `model`.
3. In Hermes, check that the provider appears once and the new models are selectable.
4. If runtime uses compatibility helpers, confirm the USTC entry survives normalization via `get_compatible_custom_providers()`.

## Pitfalls
- Do not paste a redacted token placeholder into config.
- Do not assume the model list from a static doc is complete; query `/v1/models`.
- If the provider is missing from the picker, check whether `custom_providers` was accidentally converted from a YAML list into a dict.
- If you want multiple USTC models to appear as separate selectable entries in `/model`, create one `custom_providers` entry per model (unique `name`, same `base_url`, same `api_key`). The `models:` sub-dict is for per-model metadata, not for populating the picker.
- If you need a fresh model list, re-query the live endpoint rather than relying on cached names.
