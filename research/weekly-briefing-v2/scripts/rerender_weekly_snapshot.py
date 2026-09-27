#!/usr/bin/env python3
"""Transactionally rebuild a completed briefing from its immutable snapshot."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import tempfile
from pathlib import Path

import run_weekly_e2e as runner


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".new")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--week", required=True)
    parser.add_argument("--send-email", action="store_true")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    report_dir = data_dir / "reports" / args.week
    snapshot_path = report_dir / "selected_snapshot.json"
    manifest_path = report_dir / "manifest.json"
    if not snapshot_path.is_file() or not manifest_path.is_file():
        raise RuntimeError("completed report snapshot and manifest are required")
    snapshot = read_json(snapshot_path)
    manifest = read_json(manifest_path)
    selected = snapshot.get("selected") if isinstance(snapshot.get("selected"), list) else []
    stats = snapshot.get("stats") if isinstance(snapshot.get("stats"), dict) else {}
    queries = snapshot.get("queries") if isinstance(snapshot.get("queries"), list) else []
    narrative = snapshot.get("narrative") if isinstance(snapshot.get("narrative"), dict) else {}
    if manifest.get("status") != "success" or not selected:
        raise RuntimeError("only successful non-empty reports can be rebuilt")

    config = read_json(data_dir / "config.json")
    delivery = config.get("delivery") if isinstance(config.get("delivery"), dict) else {}
    os.environ.setdefault("AGENTLY_WORKSPACE", str(delivery.get("agently_workspace") or "hermes"))
    with tempfile.TemporaryDirectory(prefix="rerender-", dir=str(report_dir.parent)) as raw_stage:
        stage = Path(raw_stage)
        markdown = runner.make_report(args.week, selected, stats, stage, queries, narrative)
        markdown_path = stage / "report.md"
        html_path = stage / "report.html"
        pdf_path = stage / "report.pdf"
        markdown_path.write_text(markdown, encoding="utf-8")
        html_text = runner.make_report_html(args.week, selected, stats, queries, html_path, narrative)
        quality = runner.validate_report_quality(selected, html_text)
        runner.make_pdf(html_text, markdown, pdf_path)
        quality["pdf_bytes"] = pdf_path.stat().st_size
        quality["pdf_nonempty"] = pdf_path.stat().st_size > 5000
        if not quality["pdf_nonempty"]:
            raise RuntimeError("rebuilt PDF is unexpectedly small")

        recipients = [str(value) for value in delivery.get("email_to", []) if str(value).strip()]
        subject = f"⚚ 学术研究周报 {args.week}（排版修正版）"
        email = runner.try_send_email(recipients, subject, markdown_path, pdf_path, bool(args.send_email and recipients))
        if args.send_email and email.get("status") != "sent":
            raise RuntimeError("corrected report email was not sent")

        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = data_dir / "rerender-backups" / args.week / stamp
        backup.mkdir(parents=True, exist_ok=False)
        for name in ("report.md", "report.html", "report.pdf", "quality_receipt.json", "delivery_receipt.json", "manifest.json"):
            source = report_dir / name
            if source.is_file():
                shutil.copy2(source, backup / name)
        for name in ("report.md", "report.html", "report.pdf"):
            os.replace(stage / name, report_dir / name)
        write_json(report_dir / "quality_receipt.json", quality)
        receipt = {
            "version": 1,
            "runner": runner.MARKER,
            "week": args.week,
            "generated_at": runner.now_iso(),
            "rerendered_from_snapshot": True,
            "local": {"status": "written", "report_dir": str(report_dir), "markdown": str(report_dir / "report.md"), "html": str(report_dir / "report.html"), "pdf": str(report_dir / "report.pdf")},
            "email": email,
        }
        write_json(report_dir / "delivery_receipt.json", receipt)
        manifest["delivery"] = {"email": email.get("status")}
        manifest["rerender"] = {"at": runner.now_iso(), "source": "selected_snapshot.json", "backup": str(backup)}
        write_json(manifest_path, manifest)
    print(json.dumps({"ok": True, "week": args.week, "quality": True, "email": email.get("status")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
