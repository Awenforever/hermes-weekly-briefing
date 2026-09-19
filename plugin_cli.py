"""Profile-aware CLI for Weekly Briefing v4."""

from __future__ import annotations

import argparse
import json
import os
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
    run = actions.add_parser("run", help="Generate a report and optionally send it by email")
    run.add_argument("--email-to", action="append", default=[])
    run.add_argument("--send-email", action="store_true")
    run.add_argument("--max-selected", type=int, default=5)
    run.add_argument("--week", default=None)
    run.add_argument("--analysis-file", default=None)
    run.add_argument("--allow-shallow", action="store_true")
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


def weekly_briefing_command(args: argparse.Namespace) -> int:
    action = getattr(args, "weekly_action", None)
    if action == "run":
        return _run(args)
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
