# Gemini Provider Gap (2026-07-03)

## Issue

Auxiliary model config references `gemini` as provider for vision and approval:

```yaml
auxiliary:
  vision:
    provider: gemini
    model: gemini-2.5-flash
  approval:
    provider: gemini
    model: gemini-2.5-pro
```

But no `gemini` provider exists in `custom_providers` or `providers` sections of config.yaml.

## Verification

Gemini API key is present and working (`.env`: `GEMINI_API_KEY=***`).
API test: `gemini-2.5-flash` and `gemini-2.5-pro` are both available (50 models in catalog).

## Resolution Needed

Add a gemini custom_provider to config.yaml:

```yaml
custom_providers:
  - name: gemini
    provider: gemini
    model: gemini-2.5-flash
    api_key: ${GEMINI_API_KEY}
    base_url: https://generativelanguage.googleapis.com/v1beta/openai
```

Or use `hermes config set` CLI to register it programmatically.
Once registered, vision and approval aux models will become functional.