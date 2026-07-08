# HERMES_WEEKLY_DEPS_BAKED_POLICY_FINAL_V1
# HERMES_WEEKLY_DEPS_BAKED_POLICY_V2
#!/usr/bin/env python3
"""Dependency health check for weekly-briefing-v3 system.

Run: python3 health_check.py
Exit 0 if all healthy, exit 1 if warnings, exit 2 if critical failures.
"""

import subprocess
import json
import sys
import os

CHECKS = []
DATA = os.environ.get("HERMES_WEEKLY_DATA_DIR", os.path.expanduser("~/.hermes/weekly-briefing"))

def check(name, fn):
    try:
        result = fn()
        CHECKS.append({"name": name, "status": "ok", "detail": result})
        return True
    except Exception as e:
        CHECKS.append({"name": name, "status": "fail", "detail": str(e)})
        return False

def run(cmd, timeout=10):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise Exception(r.stderr.strip() or "exit code " + str(r.returncode))
    return r.stdout.strip()

# ─── Critical Dependencies ───
check("Typst (baked image PATH)", lambda: run("command -v typst && typst --version"))
check("WeasyPrint", lambda: run("python3 -c 'from weasyprint import HTML; print(\"ok\")'"))
check("fpdf2", lambda: run("python3 -c 'from fpdf import FPDF; print(\"ok\")'"))
check("CJK fonts", lambda: run("fc-list :lang=zh | head -1"))
check("agently-cli installed", lambda: run("command -v agently-cli >/dev/null 2>&1 && echo ok || echo not_found"))

# ─── agently-cli OAuth health ───
try:
    result = run("agently-cli +me 2>&1", timeout=15)
    # Try to extract JSON object from output
    import re
    json_match = re.search(r'\{.*"ok".*\}', result, re.DOTALL)
    if json_match:
        data = json.loads(json_match.group(0))
        if data.get("ok"):
            scopes = data.get("data", {}).get("scopes", [])
            quota = data.get("data", {}).get("rate_limits", {}).get("daily_send_quota", "?")
            CHECKS.append({
                "name": "agently-cli OAuth",
                "status": "ok",
                "detail": f"scopes={','.join(scopes)}, daily_quota={quota}"
            })
        else:
            CHECKS.append({
                "name": "agently-cli OAuth",
                "status": "fail",
                "detail": str(data.get("error", {}).get("message", "unknown"))[:80]
            })
    else:
        CHECKS.append({
            "name": "agently-cli OAuth",
            "status": "fail",
            "detail": "No valid JSON response — token may be expired"
        })
except Exception as e:
    CHECKS.append({"name": "agently-cli OAuth", "status": "fail", "detail": str(e)[:80]})

# ─── Data Integrity ───
for fname in ["config.json", "papers/archive.json", "papers/dedup.json", "papers/relations.json"]:
    path = os.path.join(DATA, fname)
    check(f"Data: {fname}", lambda p=path: (
        open(p).read(),
        json.load(open(p)),
        f"valid ({os.path.getsize(p)} bytes)"
    )[2])

# ─── Typst font check (on actual compile) ───
check("Typst font compile test", lambda: run(
    "echo '#set text(font:(\"WenQuanYi Zen Hei\",\"Unifont\")); = Test' | "
    "typst compile - /tmp/_healthcheck.pdf 2>&1 && echo ok"
))

# ─── Summary ───
total = len(CHECKS)
passed = sum(1 for c in CHECKS if c["status"] == "ok")
failed = sum(1 for c in CHECKS if c["status"] == "fail")

print(f"\n{'='*50}")
print(f"Health Check: {passed}/{total} passed")
for c in CHECKS:
    icon = "✅" if c["status"] == "ok" else "❌"
    print(f"  {icon} {c['name']}: {c['detail'][:80]}")

# Write result for ops skill
os.makedirs(f"{DATA}/logs", exist_ok=True)
with open(f"{DATA}/logs/healthcheck.jsonl", "a") as f:
    f.write(json.dumps({"timestamp": subprocess.run("date -Iseconds", shell=True, capture_output=True, text=True).stdout.strip(), "checks": CHECKS, "total": total, "passed": passed}) + "\n")

if failed == 0:
    print("\n✅ All healthy")
    sys.exit(0)
elif any(c["name"].startswith("agently-cli") and c["status"] == "fail" for c in CHECKS):
    print("\n⚠️  OAuth token may have expired. Run: agently-cli auth login")
    sys.exit(1)
else:
    print(f"\n❌ {failed} failure(s) detected")
    sys.exit(2)
