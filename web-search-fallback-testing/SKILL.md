---
name: web-search-fallback-testing
description: Debug web search backend fallback in Hermes — test individual backends, diagnose hang/timeout issues, configure primary backend in config.yaml.
---

# Web Search Fallback Testing

Use this skill when web search is not working, slow, or you need to verify which backend is being used and whether fallback works correctly.

## Trigger Conditions
- User reports search not working / timing out
- Need to verify which backend is active
- Need to test fallback chain
- Web search returns empty results but API keys are configured

## Procedure

### 1. Check Environment Variables
Environment variables in `.env` are not automatically reloaded into the running Hermes process. Use dotenv with override=True:
```python
from dotenv import load_dotenv
import os
load_dotenv('/opt/data/.env', override=True)
for k in ['TAVILY_API_KEY', 'EXA_API_KEY', 'FIRECRAWL_API_KEY', 'SERPAPI_API_KEY', 'SEARCHX_API_KEY']:
    v = os.environ.get(k, '')
    print(f"{k}: present={bool(v)}, len={len(v)}, prefix={v[:10] if v else 'N/A'}")
```

Use `/opt/hermes/.venv/bin/python` (not system python) to import from tools.web_tools.

### 2. Check Primary Backend Detection
```python
from tools.web_tools import _get_backend, _is_backend_available
print(f"Primary backend: {_get_backend()}")
for b in ['serpapi', 'parallel', 'firecrawl', 'tavily', 'exa', 'searchx']:
    print(f"  {b}: {'✅' if _is_backend_available(b) else '❌'}")
```

Auto-detection priority order (for unconfigured backend):
1. `firecrawl` (if FIRECRAWL_API_KEY or FIRECRAWL_API_URL set)
2. `tavily` (if TAVILY_API_KEY set)
3. `serpapi` (if SERPAPI_API_KEY set)
4. `brave` (if BRAVE_API_KEY set)
5. `exa` (if EXA_API_KEY set)
6. `parallel` (if PARALLEL_API_KEY set)
7. `firecrawl` (default fallback)

### 3. Test Individual Backends
```python
# SerpAPI
result = wt._serpapi_search(query, limit)

# Exa
result = wt._exa_search(query, limit)

# Tavily (requires 2 calls)
raw = wt._tavily_request("search", {"query": query, "limit": limit})
result = wt._normalize_tavily_search_results(raw)

# Firecrawl
response = wt._get_firecrawl_client().search(query=query, limit=limit)
```

### 4. Debug the Full Search Call
```python
import json
result = json.loads(web_search_tool(query="test", limit=2))
debug = result.get('_debug', {})
print(f"Backend: {debug.get('backend', 'unknown')}")
```

The `_debug` field shows which backend was actually used after fallback.

### 5. Known Issues

#### Firecrawl Hang (No Timeout)
**Problem**: Firecrawl's search call has no timeout set. If the API endpoint is unreachable (common behind restrictive networks/firewalls in China), the request hangs indefinitely and **blocks** the entire fallback chain from triggering.

**Fix**: Set a primary backend in config.yaml that doesn't hang:
```yaml
web:
  backend: exa   # or: serpapi
```
Add this to `/opt/data/config.yaml` under the `toolsets:` section. This bypasses auto-detection and uses the configured backend directly.

#### Tavily SSL Timeout
**Problem**: Tavily often fails with SSL handshake timeout behind restrictive networks. This is a network-level issue.

**Impact**: Tavily throws an exception (doesn't hang like Firecrawl) so the fallback chain continues to the next backend.

#### SSRF False Positive Behind Proxy (DNS Hijack)
**Problem**: Clash/Surge TUN mode returns fake IPs in the RFC 2544 Benchmarking range (`198.18.0.0/15`) for all DNS queries. Python's ipaddress.is_private() returns True for this range, causing url_safety.is_safe_url() to block ALL external URLs. web_extract returns "Blocked: URL targets a private or internal network address" for every URL including example.com and Wikipedia.

**Diagnosis**: Use Python to call socket.getaddrinfo('example.com') and check if the resolved IP starts with 198.18.

**Fix**: Edit `/opt/hermes/tools/url_safety.py`:
- Define `_FAKE_IP_NETWORK = ipaddress.ip_network("198.18.0.0/15")` as a module constant.
- In `_is_blocked_ip()`, add an early return of False if the IP is in `_FAKE_IP_NETWORK` (before any other check).
- This fix takes effect WITHOUT restarting the gateway (module is re-imported per call).

### 6. Check Quota Tracking

Hermes tracks per-backend usage to prevent exhausting paid-free tiers. Inspect:

```bash
cat /opt/data/web_quota.json
```

When a backend hits its monthly limit, `_run_search_with_fallback()` skips it and moves to the next candidate. The quota resets on the first of each month.

To reset manually for testing:
```bash
rm /opt/data/web_quota.json
```

### 7. Understand the Fallback Chain

`_run_search_with_fallback()` tries backends in this order:
1. Configured `web.backend` (from config.yaml)
2. Configured `web.fallback` (from config.yaml)
3. Hardcoded priority chain: **exa** → **brave** → **tavily** → **searchx** (last resort, unlimited)

At each step, two conditions must pass:
- **Quota check**: `_check_quota(backend)` must return True (not exhausted for this month)
- **API success**: The search function must return `{"success": true, ...}`

If a backend fails either check, the chain moves to the next candidate. Successful searches are recorded via `_record_usage()`.

### 8. Verify Current Quota Status

```python
from tools.web_tools import _get_quota_status
print(_get_quota_status())
```

Free tier limits (2026-06-29, from official pricing pages):
| Backend | Free/mo | Source |
|---------|---------|--------|
| SerpAPI | 250 | https://serpapi.com/pricing |
| Exa | 20,000 | https://exa.ai/pricing |
| Brave | 1,000 | https://api-dashboard.search.brave.com/documentation/pricing |
| Tavily | 1,000 | https://docs.tavily.com/documentation/api-credits |
| Firecrawl | 500 | https://www.firecrawl.dev/pricing |
| SearchX | ∞ | open source |
Write test scripts to `/tmp/` and run with the Hermes venv:
```bash
/opt/hermes/.venv/bin/python /tmp/test_search.py
```
Always set a timeout via `timeout 30` when the backend might hang:
```bash
cd /opt/hermes && timeout 30 /opt/hermes/.venv/bin/python /tmp/test_search.py
```

## Verification
- Primary backend should respond in under 5 seconds
- If primary fails, the next available backend in fallback chain should be tried
- Check `_debug.backend` in result JSON to confirm which backend served the request