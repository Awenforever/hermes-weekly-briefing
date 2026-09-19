#!/usr/bin/env python3
# HERMES_WEEKLY_DEPS_BAKED_POLICY_FINAL_V1
import importlib.util
import shutil
import sys

checks = {
    "weasyprint": importlib.util.find_spec("weasyprint") is not None,
    "reportlab": importlib.util.find_spec("reportlab") is not None,
    "requests": importlib.util.find_spec("requests") is not None,
    "yaml": importlib.util.find_spec("yaml") is not None,
    "pdfinfo": shutil.which("pdfinfo") is not None,
    "pdftotext": shutil.which("pdftotext") is not None,
}
for k, v in checks.items():
    print(f"{k}={v}")
missing = [k for k, v in checks.items() if not v]
if missing:
    print("Missing baked dependencies:", ",".join(missing), file=sys.stderr)
    print("Action: use the Hermes Weekly image or install the declared plugin dependencies.", file=sys.stderr)
    raise SystemExit(1)
print("All weekly dependencies are present. Runtime dependency installation is disabled.")
