#!/usr/bin/env python3
"""Archive recovery: restore archive.json entries from backups and manifests.

Usage:
    python3 recover_archive.py [--dry-run] [--verbose]

Recovery sources (in priority order):
    1. recovery/ archive.json.bak snapshots
    2. backups/ backup directories with archive-like JSON
    3. reports/*/manifest.json selected_papers entries
"""

import json, os, sys, glob
from datetime import datetime
from pathlib import Path
from typing import Any

DATA = Path("/opt/data/weekly-briefing")

def now_iso() -> str:
    return datetime.now().isoformat()

def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except Exception:
        return None

def log(msg: str) -> None:
    print(f"[{now_iso()}] {msg}")

def find_recovery_sources() -> list[dict[str, Any]]:
    """Collect all recoverable paper entries from various sources."""
    recovered: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # Source 1: recovery/*.bak snapshots
    for bak in sorted((DATA / "recovery").glob("**/*.bak")):
        data = read_json(bak)
        if not isinstance(data, dict):
            continue
        papers = data.get("papers", [])
        for p in papers:
            if not isinstance(p, dict):
                continue
            pid = p.get("canonical_id") or p.get("archive_id") or p.get("doi") or p.get("arxiv_id") or p.get("title", "")
            if not pid or pid in seen_ids:
                continue
            seen_ids.add(pid)
            p["_recovery_source"] = str(bak)
            p["_recovered"] = True
            recovered.append(p)
        log(f"Source (recovery bak): {len(papers)} papers from {bak.name}")

    # Source 2: backup directories
    for backup_dir in sorted((DATA / "backups").glob("before-*")):
        for arc_file in backup_dir.glob("**/archive.json"):
            data = read_json(arc_file)
            if not isinstance(data, dict):
                continue
            papers = data.get("papers", [])
            for p in papers:
                if not isinstance(p, dict):
                    continue
                pid = p.get("canonical_id") or p.get("archive_id") or p.get("doi") or p.get("arxiv_id") or p.get("title", "")
                if not pid or pid in seen_ids:
                    continue
                seen_ids.add(pid)
                p["_recovery_source"] = str(arc_file)
                p["_recovered"] = True
                recovered.append(p)
            log(f"Source (backup): {len(papers)} papers from {arc_file}")

    # Source 3: report manifests
    for manifest_path in sorted((DATA / "reports").glob("*/manifest.json")):
        manifest = read_json(manifest_path)
        if not isinstance(manifest, dict):
            continue
        week = manifest.get("week", manifest_path.parent.name)
        selected = manifest.get("selected_papers") or manifest.get("papers") or []
        for p in selected:
            if not isinstance(p, dict):
                continue
            pid = p.get("canonical_id") or p.get("archive_id") or p.get("doi") or p.get("arxiv_id") or p.get("title", "")
            if not pid or pid in seen_ids:
                continue
            seen_ids.add(pid)
            entry = {
                "title": p.get("title", ""),
                "canonical_id": pid,
                "doi": p.get("doi"),
                "arxiv_id": p.get("arxiv_id"),
                "first_seen_week": week,
                "last_checked_week": week,
                "included_in_reports": [week],
                "reading_status": "unread",
                "quality_tier": "T4",
                "tags": p.get("keywords", []),
                "_recovery_source": str(manifest_path),
                "_recovered": True,
            }
            recovered.append(entry)
        log(f"Source (manifest): {len(selected)} papers from {manifest_path.parent.name}")

    return recovered

def main() -> int:
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv

    archive_path = DATA / "papers" / "archive.json"
    archive = read_json(archive_path) or {"papers": [], "last_updated": "", "total_briefings": 0, "total_papers_covered": 0}

    existing_ids: set[str] = set()
    for p in archive.get("papers", []):
        pid = p.get("canonical_id") or p.get("archive_id") or p.get("doi") or p.get("arxiv_id") or p.get("title", "")
        if pid:
            existing_ids.add(pid)

    recovered = find_recovery_sources()
    new_entries = [r for r in recovered if r.get("canonical_id") not in existing_ids]

    log(f"Archive current: {len(archive.get('papers', []))} papers")
    log(f"Recovered total: {len(recovered)} entries from sources")
    log(f"New entries (not in archive): {len(new_entries)}")

    if verbose:
        for entry in new_entries:
            log(f"  NEW: {entry.get('title', '?')[:80]} [source: {entry.get('_recovery_source')}]")

    if not new_entries:
        log("Nothing to recover. Archive is complete.")
        return 0

    if dry_run:
        log(f"DRY RUN: would add {len(new_entries)} entries to archive.json")
        return 0

    for entry in new_entries:
        clean = {k: v for k, v in entry.items() if not k.startswith("_")}
        archive["papers"].append(clean)

    archive["last_updated"] = now_iso()
    archive["total_papers_covered"] = len(archive["papers"])

    bak_path = DATA / "recovery" / f"archive_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json.bak"
    bak_path.parent.mkdir(parents=True, exist_ok=True)
    bak_path.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")

    archive_path.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"SUCCESS: Added {len(new_entries)} entries. Archive now has {len(archive['papers'])} papers.")
    log(f"Backup saved: {bak_path}")

    log_path = DATA / "logs" / "recovery.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(json.dumps({
            "time": now_iso(), "action": "recover",
            "added": len(new_entries), "total_after": len(archive["papers"]),
            "sources": len(recovered), "dry_run": dry_run,
        }, ensure_ascii=False) + "\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())