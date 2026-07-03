# Vision Model Providers (Tested 2026-07-03)

Three vision-capable models verified and available as providers.

## Primary: Zhipu GLM-4V-Flash (Free)

- **Provider**: custom (Zhipu)
- **Model**: `glm-4v-flash`
- **Base URL**: `https://open.bigmodel.cn/api/paas/v4/`
- **API Key**: configured in `auxiliary.vision`
- **Notes**: OpenAI-compatible endpoint. Free tier. Tested with image→text successfully.

## Fallback A: Gemini 2.5 Flash

- **API Key**: `GEMINI_API_KEY` in `/opt/data/.env`
- **Native endpoint**: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={KEY}`
- **Notes**: 50 models available. Tested vision successfully. To use as primary, change `auxiliary.vision.provider` to `gemini` and model to `gemini-2.5-flash`.

## Fallback B: USTC Qwen3.6-Chat

- **Provider**: USTC (via existing `custom_providers` config)
- **Model**: `qwen3.6-chat`
- **Base URL**: `https://api.llm.ustc.edu.cn/v1`
- **Notes**: OpenAI-compatible. Tested vision successfully. Uses same API key as other USTC models.

## Switching Providers

Edit `auxiliary.vision` in `/opt/data/config.yaml`:

```yaml
auxiliary:
  vision:
    provider: custom          # or gemini, or ustc
    model: glm-4v-flash       # or gemini-2.5-flash, qwen3.6-chat
    base_url: https://open.bigmodel.cn/api/paas/v4/
    api_key: {key}
```

Note: Hermes does NOT support vision-specific fallback chains. If primary fails, manual switch required.