# Approval Model Deadlock — Real Case (2026-07-03)

## Scenario

User had `auxiliary.approval.model = gemini-2.5-pro` with `approvals.mode: smart`.
Gemini 2.5-pro free tier quota was exhausted (429 RESOURCE_EXHAUSTED).

## Deadlock Sequence

1. `hermes config set auxiliary.approval.model gemini-2.5-flash` → config file updated
2. `ssh ... docker compose restart hermes` → command triggers smart approval
3. Running process still uses gemini-2.5-pro for approval (old model, no quota)
4. Approval fails → restart never executes → process stays on broken config
5. Container shows "Up N minutes" but Start time unchanged = restart never happened

## Root Cause

`hermes config set` writes the file. The running process reads config at startup only.
Changing `auxiliary.*` requires a restart, but restart requires working approval.
If the old approval model is broken, you can't restart to pick up the new one.

## Resolution

External intervention — restarted directly from Docker host, bypassing Hermes approval.

## API Test Results

| Model | Native Gemini API | OpenAI-compatible endpoint |
|-------|:---:|:---:|
| gemini-2.5-flash | ✅ OK | ⚠️ Initially OK, later "invalid key" (quota?) |
| gemini-2.5-pro | — | ❌ 429 quota exhausted |

Key prefix: `AIzaSyAu` (39 chars, standard Google AI Studio key format).

OpenAI-compatible endpoint: `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`
Native endpoint: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}`

## Key Commands

```bash
# Check what the RUNNING process uses (login to container)
docker exec hermes-hermes-1 grep -A5 "approval:" /opt/data/config.yaml

# Restart from host (bypasses Hermes approval)
ssh user@nas 'cd /path/to/compose && docker compose restart hermes'

# Verify restart actually happened
docker inspect hermes-hermes-1 --format 'Started: {{.State.StartedAt}}'

# Direct API test (not through Hermes)
curl -s "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$KEY" \
  -H "Content-Type: application/json" \
  -d '{"contents":[{"parts":[{"text":"OK"}]}],"generationConfig":{"maxOutputTokens":5}}'
```