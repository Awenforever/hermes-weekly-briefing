---
name: add-custom-web-search-backend
description: Add a new web search API as a Hermes backend in web_tools.py — register, wire up detection, dispatch.
---

# Add Custom Web Search Backend to Hermes

Use when you need to integrate a new web search API (SearchX, Brave, etc.) not in Hermes' built-in list (exa, tavily, firecrawl, parallel, serpapi).

## Integration Points in `/opt/hermes/tools/web_tools.py`

Seven places to modify, one env var to add:

### 1. Search Function

Write a function that:
- Reads its credential from an env var (e.g., `os.environ.get("MY_BACKEND_KEY")`)
- Calls the external API and returns `{"success": true, "data": {"web": [{"url","title","description","position"}]}}`
- Uses `requests` library (handles gzip/SSL better than `urllib`)
- If the service is directly accessible from China (not GFW-blocked), bypass proxy with `proxies={"http": None, "https": None}` to avoid SSL MITM issues from Clash/Surge TUN mode

Insert it in the file between the `_searchx_search` function and the `_exa_search` function, or after the Tavily section and before the main search entry-point — anywhere before the Firecrawl fallback block in `web_search_tool()`.

### 2a. Hooks for backend auto-detection

Hermes also checks availability in two "glue" functions:

- `_web_requires_env()` (around line 187) — append your env var name (e.g. `"BRAVE_API_KEY"`) to the `requires` list so tool metadata reflects it
- `check_web_api_key()` (around line 2102) — add your backend name to both the explicit `if configured in (...)` tuple and the fallback `any(_is_backend_available(...))` generator
- **Docstring** (around line 15) — add a new `- YourBackend: https://...` line under the `Backend compatibility:` section

### 2. Registration (simplified after 2026-06-29 refactor)

After the fallback refactor, `web_search_tool()` uses a unified `_run_search_with_fallback()` dispatch — you **no longer need to add a separate branch** in the search tool. Just add your backend to two dicts/tuples:

**`_run_search_with_fallback()` — `search_funcs` dict** (add your function):
```python
search_funcs = {
    "exa": _exa_search,
    ...
    "mybackend": _my_backend_search,
}
```

**`_get_backend()` — allowed list + fallback chain:**
```python
if configured in ("parallel", "firecrawl", "tavily", "exa", "searchx", "serpapi", "brave", "mybackend"):
```
```python
backend_candidates = (
    ("mybackend", _has_env("MY_BACKEND_API_KEY")),
    ...
)
```

**`_is_backend_available()` — env var check:**
```python
if backend == "mybackend":
    return _has_env("MY_BACKEND_API_KEY")
```

**`_web_requires_env()` — metadata:**
```python
requires = ["...", "MY_BACKEND_API_KEY", "..."]
```

**`check_web_api_key()` — both tuples (line ~2160):**
```python
if configured in ("exa", "parallel", ..., "mybackend"):
```
```python
any(_is_backend_available(backend) for backend in ("exa", ..., "mybackend"))
```

**Docstring — add to `Backend compatibility:` list**

### 3. Environment

Append the credential key to `/opt/data/.env`, then set `web.backend` in config.yaml to the backend name.

### 4. Optional: Configure Fallback

Set `web.fallback` in `config.yaml` to an alternative backend that takes over if the primary fails (rate limit, quota exceeded, API error):

```yaml
web:
  backend: serpapi     # primary
  fallback: tavily     # backup — auto-switches on failure
```

This uses `_run_search_with_fallback()` which transparently retries with the fallback. The fallback must also be a registered backend with a valid API key.

**Wrapper pattern**: If your backend has complex initialization (like Firecrawl's SDK or Tavily's multi-step request), create a simple wrapper that returns the standard `{"success": true, "data": {"web": [...]}}` dict. Then register the wrapper — not the raw function — in `search_funcs`.

### 5. Verification

Test each backend before declaring done:

```bash
docker restart hermes-hermes-1
```

## Pitfalls

- **SSL EOF**: Proxy MITM breaks HTTPS. Bypass with `proxies={"http": None, "https": None}`.
- **DNS hijacking**: Clash TUN returns 198.18.x.x fake IPs. SSRF check blocks them.
- **Module cache**: Edits need gateway restart. During dev, test with `.venv/bin/python3` directly: `cd /opt/hermes && export $(grep MY_BACKEND_API_KEY /opt/data/.env | xargs) && HOME=/root .venv/bin/python3 -c "from tools.web_tools import _my_backend_search; print(_my_backend_search('test', 2))"`
- **Config loading**: Hermes resolves `config.yaml` from its own config directory (`/opt/data/`), not `~/.hermes/`. Always set `HOME=/root` when testing outside the gateway.
- **Wrong endpoint**: Always verify the exact API URL from the backend's docs — don't guess subdomains (e.g. `searchx.dev` not `api.searchx.dev`).
- **gzip encoding**: Some APIs return gzip-compressed responses. Use `requests` (handles automatically) not raw `urllib`. To debug with curl, pipe through `| gzip -d`.
- **Free tier comparison (2026-06-29)**: SerpAPI 100/mo (auto-charges), Brave 5000/mo + $5 credit, Tavily 1000/mo (limits, no charge), Exa 1000/mo, SearchX free, Firecrawl limited free.
