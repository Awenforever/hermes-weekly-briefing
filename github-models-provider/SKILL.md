---
name: github-models-provider
description: Configure GitHub Models (models.github.ai) as an LLM provider for Hermes — add gpt-5-chat, o4-mini, gpt-4.1, gpt-4o, and other models as custom providers.
category: devops
---

# GitHub Models Provider for Hermes

Add GitHub Models (models.github.ai) as a custom LLM provider in Hermes config.yaml. Free tier for all GitHub accounts with rate limits.

## Prerequisites

1. GitHub PAT with `models` scope
2. Activate GitHub Models at https://github.com/marketplace/models (open playground once)
3. PAT available in `/opt/data/.env` as `GITHUB_TOKEN`

## Available Models (free tier)

| Model ID | Type | Notes |
|----------|------|-------|
| `openai/gpt-5-chat` | Chat | **Best for Hermes** — conversational GPT-5 |
| `openai/gpt-5` | Reasoning | Pure reasoning, needs high max_tokens |
| `openai/o4-mini` | Reasoning | Latest o-series |
| `openai/gpt-5-mini` | Chat | Lightweight GPT-5 |
| `openai/gpt-5-nano` | Chat | Fastest |
| `openai/gpt-4.1` | Chat | Stable |
| `openai/gpt-4o` | Chat | Multimodal |
| `openai/gpt-4o-mini` | Chat | Lightweight |

## API Endpoint

```
POST https://models.github.ai/marketplace/openai/gpt-5-chat/chat/completions
Authorization: Bearer {GITHUB_TOKEN}
Content-Type: application/json
```

## Configuring in Hermes

Add to `/opt/data/config.yaml` under `custom_providers`:

```yaml
custom_providers:
  - id: github-models
    name: GitHub Models
    base_url: https://models.github.ai/marketplace/openai
    api_key_env: GITHUB_TOKEN
    models:
      - id: gpt-5-chat
        name: GPT-5 Chat
```

## Critical Pitfall

**config.yaml changes are overwritten on Hermes Gateway restart.** The WebUI manages config.yaml. To persist changes:

1. Use the Hermes WebUI to add the provider (Settings → LLM Providers → Add Custom)
2. OR keep config changes and avoid restarting the gateway
3. After WebUI config, the model appears in the model selector dropdown

## Testing

```bash
curl -s -X POST "https://models.github.ai/marketplace/openai/gpt-5-chat/chat/completions" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hi"}],"max_tokens":50}' | jq .
```

Expected: HTTP 200 with `choices[0].message.content`.

## Troubleshooting

- **HTTP 403 "no_access"**: PAT missing `models` scope, or GitHub Models not activated. Fix at github.com/settings/tokens.
- **HTTP 401**: Token invalid or expired.
- **HTTP 429**: Rate limit hit. Wait and retry.
- **Connection timeout**: Needs proxy. Ensure `HTTPS_PROXY=http://192.168.124.88:7890` is set.