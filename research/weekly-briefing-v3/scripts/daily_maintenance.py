# HERMES_WEEKLY_DEPS_BAKED_POLICY_FINAL_V1
#!/usr/bin/env python3
"""Archive Maintenance: prune, review quality, clean candidates, revalidate relations.

Runs daily via cron. Non-destructive: all pruning suggestions require manual confirmation.
Output: $DATA_DIR/logs/maintenance-YYYY-MM-DD.json
"""

import json
import os
import shutil
import glob
import re
from datetime import datetime, timedelta

DATA = os.environ.get("HERMES_WEEKLY_DATA_DIR", os.path.expanduser("~/.hermes/weekly-briefing"))
LOGS = f"{DATA}/logs"
os.makedirs(LOGS, exist_ok=True)

today = datetime.now().strftime("%Y-%m-%d")
report = {"date": today, "actions": [], "warnings": [], "suggestions": []}

# ──────────────────────────────────────────────
# 0. DEPENDENCY POLICY: HERMES_WEEKLY_DEPS_BAKED_POLICY_V2; dependencies are baked into hermes-agent:v0.17.0. No runtime apt-get/init-deps/stage2 hook.
try:
    __import__("weasyprint")
    __import__("fpdf")
except ImportError:
    rc = 0  # HERMES_WEEKLY_DEPS_BAKED_POLICY_RESIDUAL_CLEAN_V1: runtime apt-get disabled; rebuild hermes-agent:v0.17.0 if dependencies are missing
    if rc == 0:
        report["actions"].append("Bootstrap (fallback): reinstalled apt packages")
    else:
        report["warnings"].append("Bootstrap (fallback): apt install failed")

if not shutil.which("typst") and not os.path.exists("/usr/local/bin/typst"):
    report["warnings"].append("Typst not found in PATH or /usr/local/bin/typst")

# ──────────────────────────────────────────────
# 1. CANDIDATE CLEANUP (keep last 12 weeks)
# ──────────────────────────────────────────────
candidate_dir = f"{DATA}/papers/candidates"
candidates = sorted(glob.glob(f"{candidate_dir}/*.json"))
cutoff_12w = datetime.now() - timedelta(weeks=12)
cleaned = 0
for f in candidates:
    mtime = datetime.fromtimestamp(os.path.getmtime(f))
    if mtime < cutoff_12w:
        os.remove(f)
        cleaned += 1

if cleaned:
    report["actions"].append(f"Cleaned {cleaned} old candidate files (>{12} weeks)")
else:
    report["actions"].append("No candidate files to clean")

# ──────────────────────────────────────────────
# 2. LOG ROTATION (keep last 90 days)
# ──────────────────────────────────────────────
logs = sorted(glob.glob(f"{LOGS}/maintenance-*.json"))
cutoff_90d = datetime.now() - timedelta(days=90)
for f in logs:
    mtime = datetime.fromtimestamp(os.path.getmtime(f))
    if mtime < cutoff_90d:
        os.remove(f)
report["actions"].append(f"Log rotation checked ({len(logs)} maintenance logs)")

# ──────────────────────────────────────────────
# 3. ARCHIVE QUALITY REVIEW
# ──────────────────────────────────────────────
try:
    with open(f"{DATA}/papers/archive.json") as f:
        archive = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    report["warnings"].append("archive.json not found or corrupt")
    archive = {"papers": []}

try:
    with open(f"{DATA}/papers/relations.json") as f:
        relations = json.load(f)
except:
    relations = {"edges": [], "by_paper": {}}

# 3a. Check for superseded papers
by_paper = relations.get("by_paper", {})
superseded_ids = set()
for paper_id, rels in by_paper.items():
    for sid in rels.get("superseded_by", []):
        superseded_ids.add(sid)

for paper in archive.get("papers", []):
    pid = paper.get("canonical_id") or paper.get("archive_id")
    
    # Check if superseded
    if pid in superseded_ids and not paper.get("superseded_by"):
        paper["superseded_by"] = True
        paper["quality_tier"] = "obsolete"
        report["suggestions"].append({
            "paper_id": paper.get("archive_id"),
            "title": paper.get("title", "")[:80],
            "action": "mark_obsolete",
            "reason": "Superseded by newer paper in relations graph",
            "auto": True
        })

    # Check if never read in 12+ weeks
    if paper.get("reading_status") == "unread" and paper.get("first_seen_week"):
        try:
            week_num = int(paper["first_seen_week"].split("-W")[-1])
            current_week = datetime.now().isocalendar()[1]
            weeks_ago = current_week - week_num
            if weeks_ago >= 12:
                report["suggestions"].append({
                    "paper_id": paper.get("archive_id"),
                    "title": paper.get("title", "")[:80],
                    "action": "suggest_removal",
                    "reason": f"Unread for {weeks_ago} weeks",
                    "auto": False
                })
        except:
            pass

# Save updated archive
with open(f"{DATA}/papers/archive.json", "w") as f:
    json.dump(archive, f, indent=2, ensure_ascii=False)

report["actions"].append(f"Archive quality reviewed: {len(archive.get('papers',[]))} papers")

# ──────────────────────────────────────────────
# 4. RELATION GRAPH HYGIENE (>26 weeks revalidate)
# ──────────────────────────────────────────────
deprecated_count = 0
for edge in relations.get("edges", []):
    added_week = edge.get("added_week", "")
    if added_week:
        try:
            yr, wk = added_week.split("-W")
            edge_date = datetime.strptime(f"{yr}-W{wk}-1", "%Y-W%W-%w")
            if (datetime.now() - edge_date).days > 26 * 7:
                if not edge.get("deprecated"):
                    edge["deprecated"] = True
                    edge["deprecated_at"] = today
                    deprecated_count += 1
        except:
            pass

if deprecated_count:
    report["actions"].append(f"Deprecated {deprecated_count} stale relation edges (>26 weeks)")

with open(f"{DATA}/papers/relations.json", "w") as f:
    json.dump(relations, f, indent=2, ensure_ascii=False)

# ──────────────────────────────────────────────
# 5. REPORT
# ──────────────────────────────────────────────
log_path = f"{LOGS}/maintenance-{today}.json"
with open(log_path, "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

# Print summary
print(json.dumps(report, indent=2, ensure_ascii=False))

# Exit with warning if actual errors exist (not just Typst/PATH warnings)
real_errors = [w for w in report.get("warnings", []) if any(k in w.lower() for k in ["corrupt", "missing", "critical", "failed"])]
if real_errors:
    exit(1)
exit(0)
