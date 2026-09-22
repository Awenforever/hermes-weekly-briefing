"""Profile-aware CLI for Weekly Briefing v4."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _home() -> Path:
    from hermes_constants import get_hermes_home

    return get_hermes_home()


def _root() -> Path:
    return Path(__file__).resolve().parent


def _data() -> Path:
    return _home() / "plugin-data" / "hermes-weekly-briefing"


def register_cli(parser: argparse.ArgumentParser) -> None:
    actions = parser.add_subparsers(dest="weekly_action")
    actions.add_parser("status", help="Show data, configuration, and last-report status")
    init = actions.add_parser("init", help="Initialize configuration or migrate legacy Weekly Briefing data")
    init.add_argument("--email-to", action="append", default=[])
    init.add_argument("--keyword", action="append", default=[])
    actions.add_parser("doctor", help="Validate configuration and delivery readiness")
    run = actions.add_parser("run", help="Generate a report and optionally send it by email")
    run.add_argument("--email-to", action="append", default=[])
    run.add_argument("--send-email", action="store_true")
    run.add_argument("--max-selected", type=int, default=5)
    run.add_argument("--week", default=None)
    run.add_argument("--analysis-file", default=None)
    run.add_argument("--allow-shallow", action="store_true")
    schedule = actions.add_parser("schedule-install", help="Install or repair the email-only weekly schedule")
    schedule.add_argument("--schedule", default="0 2 * * 5")
    actions.add_parser("schedule-status", help="Show the managed weekly schedule")
    parser.set_defaults(func=weekly_briefing_command)


def _run(args: argparse.Namespace) -> int:
    script = _root() / "research" / "weekly-briefing-v2" / "scripts" / "run_weekly_e2e.py"
    command = [sys.executable, str(script), "--data-dir", str(_data()), "--max-selected", str(args.max_selected)]
    if args.week:
        command.extend(["--week", args.week])
    if args.analysis_file:
        command.extend(["--analysis-file", args.analysis_file])
    if args.allow_shallow:
        command.append("--allow-shallow")
    for address in args.email_to:
        command.extend(["--email-to", address])
    if args.send_email:
        command.append("--send-email")
    env = os.environ.copy()
    env["HERMES_WEEKLY_DATA_DIR"] = str(_data())
    return subprocess.run(command, env=env).returncode


def _hermes_cli() -> str:
    candidate = shutil.which("hermes")
    if candidate:
        return candidate
    if Path(sys.argv[0]).is_file():
        return str(Path(sys.argv[0]).resolve())
    raise RuntimeError("cannot locate the Hermes CLI")


def _weekly_jobs() -> list[dict[str, str]]:
    result = subprocess.run(
        [_hermes_cli(), "cron", "list"], text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "cannot list Hermes cron jobs")
    jobs: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in result.stdout.splitlines():
        match = re.match(r"\s*([0-9a-f]{12})\s+\[", line)
        if match:
            current = {"id": match.group(1)}
            jobs.append(current)
            continue
        name = re.match(r"\s*Name:\s*(.+?)\s*$", line)
        if name and current is not None:
            current["name"] = name.group(1)
    return [job for job in jobs if job.get("name") in {"weekly-briefing-v2", "hermes-weekly-briefing"}]


def _config_diagnostics() -> list[str]:
    path = _data() / "config.json"
    if not path.is_file():
        return [f"missing configuration: {path}"]
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"invalid configuration JSON: {exc}"]
    errors = []
    research = config.get("research") if isinstance(config.get("research"), dict) else {}
    keywords = research.get("core_keywords") if isinstance(research.get("core_keywords"), list) else []
    if not [value for value in keywords if str(value).strip() and "$" not in str(value)]:
        errors.append("research.core_keywords needs at least one real keyword")
    delivery = config.get("delivery") if isinstance(config.get("delivery"), dict) else {}
    if str(delivery.get("channel") or "email").casefold() != "email":
        errors.append("delivery.channel must be email")
    recipients = delivery.get("email_to") if isinstance(delivery.get("email_to"), list) else []
    if not [value for value in recipients if "@" in str(value) and "$" not in str(value)]:
        errors.append("delivery.email_to needs at least one real email address")
    return errors


def _initialize(email_to: list[str], keywords: list[str]) -> int:
    data = _data()
    config_path = data / "config.json"
    migrated_from = None
    if not config_path.is_file():
        legacy_candidates = [_home() / "weekly-briefing", _home() / "weekly-briefing-v2"]
        legacy = next((path for path in legacy_candidates if (path / "config.json").is_file()), None)
        if legacy:
            shutil.copytree(legacy, data, dirs_exist_ok=True)
            migrated_from = str(legacy)
        else:
            clean_emails = [str(value).strip() for value in email_to if "@" in str(value) and "$" not in str(value)]
            clean_keywords = [str(value).strip() for value in keywords if str(value).strip() and "$" not in str(value)]
            if not clean_emails or not clean_keywords:
                print("new setup requires --email-to and at least one --keyword", file=sys.stderr)
                return 2
            data.mkdir(parents=True, exist_ok=True)
            config = {
                "version": 2,
                "research": {"core_keywords": clean_keywords, "use_profile_weights": False, "use_user_feedback": False},
                "analysis": {"auto": True, "provider_name": "USTC", "model": "deepseek-flash", "fallback_model": "qwen3.6-chat", "timeout_seconds": 180, "max_tokens": 7000},
                "delivery": {"channel": "email", "email_to": clean_emails},
            }
            temporary = config_path.with_suffix(".json.new")
            temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
            temporary.replace(config_path)
    errors = _config_diagnostics()
    print(json.dumps({"ok": not errors, "config": str(config_path), "migrated_from": migrated_from, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


def _install_schedule(schedule: str) -> int:
    errors = _config_diagnostics()
    if errors:
        print("configuration is not ready: " + "; ".join(errors), file=sys.stderr)
        return 2
    scripts = _home() / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    wrapper = scripts / "hermes_weekly_briefing.py"
    wrapper.write_text(
        "#!/usr/bin/env python3\n"
        "import shutil, subprocess, sys\n"
        "cli = shutil.which('hermes')\n"
        "if not cli:\n"
        "    raise SystemExit('Hermes CLI not found')\n"
        "result = subprocess.run([cli, 'weekly-briefing', 'run', '--send-email'])\n"
        "raise SystemExit(result.returncode)\n",
        encoding="utf-8",
        newline="\n",
    )
    jobs = _weekly_jobs()
    cli = _hermes_cli()
    common = [
        "--name", "hermes-weekly-briefing",
        "--deliver", "local",
        "--failure-deliver", "local",
        "--script", wrapper.name,
        "--no-agent",
    ]
    if jobs:
        command = [
            cli, "cron", "edit", jobs[0]["id"], "--schedule", schedule,
            *common, "--no-continuity", "--clear-skills", "--model", "", "--provider", "",
        ]
    else:
        command = [cli, "cron", "create", schedule, "", *common]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        print(result.stderr.strip() or result.stdout.strip(), file=sys.stderr)
        return result.returncode
    print(json.dumps({
        "ok": True,
        "schedule": schedule,
        "mode": "no-agent",
        "delivery": "email-only; cron output local",
        "script": str(wrapper),
        "repaired_job": jobs[0]["id"] if jobs else None,
    }, indent=2))
    return 0


def weekly_briefing_command(args: argparse.Namespace) -> int:
    action = getattr(args, "weekly_action", None)
    if action == "run":
        return _run(args)
    if action == "init":
        return _initialize(args.email_to, args.keyword)
    if action == "doctor":
        errors = _config_diagnostics()
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
        return 0 if not errors else 2
    if action == "schedule-install":
        return _install_schedule(args.schedule)
    if action == "schedule-status":
        print(json.dumps({"ok": True, "jobs": _weekly_jobs()}, indent=2))
        return 0
    if action in {None, "status"}:
        reports = _data() / "reports"
        weeks = sorted((path.name for path in reports.iterdir() if path.is_dir()), reverse=True) if reports.is_dir() else []
        print(
            json.dumps(
                {
                    "ok": True,
                    "hermes_home": str(_home()),
                    "data_dir": str(_data()),
                    "delivery": "email-only",
                    "latest_report": weeks[0] if weeks else None,
                    "config_present": (_data() / "config.json").is_file(),
                },
                indent=2,
            )
        )
        return 0
    print(f"Unknown action: {action}")
    return 2
