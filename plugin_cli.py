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
    setup = actions.add_parser("setup", help="Inspect or apply guided personal setup")
    setup.add_argument("--email-to", action="append", default=[])
    setup.add_argument("--keyword", action="append", default=[])
    setup.add_argument("--max-selected", type=int, default=None)
    setup.add_argument("--timezone", default=None)
    setup.add_argument("--schedule", default=None)
    setup.add_argument("--provider", default=None)
    setup.add_argument("--model", default=None)
    setup.add_argument("--fallback-model", default=None)
    setup.add_argument("--use-profile-weights", action=argparse.BooleanOptionalAction, default=None)
    setup.add_argument("--use-user-feedback", action=argparse.BooleanOptionalAction, default=None)
    init = actions.add_parser("init", help="Initialize configuration or migrate legacy Weekly Briefing data")
    init.add_argument("--email-to", action="append", default=[])
    init.add_argument("--keyword", action="append", default=[])
    actions.add_parser("doctor", help="Validate configuration and delivery readiness")
    actions.add_parser("mail-status", help="Check Agently CLI installation and login")
    install_mail = actions.add_parser("mail-install", help="Install the supported Agently mail CLI")
    install_mail.add_argument("--yes", action="store_true", help="Confirm the global npm installation")
    actions.add_parser("mail-login", help="Open Agently's interactive login flow")
    run = actions.add_parser("run", help="Generate a report and optionally send it by email")
    run.add_argument("--email-to", action="append", default=[])
    run.add_argument("--send-email", action="store_true")
    run.add_argument("--max-selected", type=int, default=None)
    run.add_argument("--week", default=None)
    run.add_argument("--analysis-file", default=None)
    run.add_argument("--allow-shallow", action="store_true")
    schedule = actions.add_parser("schedule-install", help="Install or repair the email-only weekly schedule")
    schedule.add_argument("--schedule", default=None)
    actions.add_parser("schedule-status", help="Show the managed weekly schedule")
    parser.set_defaults(func=weekly_briefing_command)


def _run(args: argparse.Namespace) -> int:
    script = _root() / "research" / "weekly-briefing-v2" / "scripts" / "run_weekly_e2e.py"
    config = _load_config()
    configured_max = int(config.get("max_selected") or 5) if config else 5
    command = [sys.executable, str(script), "--data-dir", str(_data()), "--max-selected", str(args.max_selected or configured_max)]
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


def _load_config() -> dict:
    path = _data() / "config.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _write_config(config: dict) -> None:
    path = _data() / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.new")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def _find_agently_cli() -> str | None:
    candidates = [
        os.environ.get("AGENTLY_CLI_PATH"),
        shutil.which("agently-cli"),
        shutil.which("agently"),
        str(Path.home() / ".local" / "bin" / "agently-cli"),
        str(Path.home() / ".local" / "bin" / "agently"),
        "/usr/local/bin/agently-cli",
        "/usr/local/bin/agently",
    ]
    return next((str(value) for value in candidates if value and Path(value).is_file()), None)


def _portable_command(executable: str, *arguments: str) -> list[str]:
    command = [executable, *arguments]
    if os.name == "nt" and Path(executable).suffix.casefold() in {".cmd", ".bat"}:
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
    return command


def _mail_status(probe: bool = True) -> dict:
    cli = _find_agently_cli()
    result = {
        "installed": bool(cli),
        "authenticated": False,
        "cli": cli,
        "install_package": "@tencent-qqmail/agently-cli",
    }
    if not cli or not probe:
        return result
    try:
        check = subprocess.run(_portable_command(cli, "+me"), text=True, capture_output=True, timeout=30, check=False)
        result["authenticated"] = check.returncode == 0
        if check.returncode:
            result["diagnostic"] = "login required or identity probe failed"
    except Exception as exc:
        result["diagnostic"] = str(exc)
    return result


def _model_status(config: dict) -> dict:
    try:
        scripts = _root() / "research" / "weekly-briefing-v2" / "scripts"
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from weekly_analysis_engine import resolve_backend

        backend = resolve_backend(config, _home())
        return {
            "ready": True,
            "provider": backend["provider_name"],
            "model": backend["model"],
            "fallback_model": backend["fallback_model"],
        }
    except Exception as exc:
        return {"ready": False, "diagnostic": str(exc)}


def _renderer_status() -> dict:
    available = []
    for module in ("weasyprint", "reportlab"):
        try:
            __import__(module)
            available.append(module)
        except Exception:
            pass
    return {"ready": bool(available), "available": available}


def _profile_timezone() -> str:
    if os.environ.get("HERMES_TIMEZONE"):
        return str(os.environ["HERMES_TIMEZONE"]).strip()
    path = _home() / "config.yaml"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    try:
        import yaml
        value = yaml.safe_load(text)
        if isinstance(value, dict):
            return str(value.get("timezone") or "").strip()
    except Exception:
        pass
    match = re.search(r"(?m)^\s*timezone\s*:\s*['\"]?([^'\"#\r\n]+)", text)
    return match.group(1).strip() if match else ""


def _doctor_result() -> dict:
    config = _load_config()
    errors = _config_diagnostics()
    mail = _mail_status()
    model = _model_status(config) if config else {"ready": False, "diagnostic": "configuration missing"}
    renderer = _renderer_status()
    schedule_cfg = config.get("schedule") if isinstance(config.get("schedule"), dict) else {}
    requested_timezone = str(schedule_cfg.get("timezone") or "").strip()
    profile_timezone = _profile_timezone()
    if not mail["installed"]:
        errors.append("Agently CLI is not installed")
    elif not mail["authenticated"]:
        errors.append("Agently CLI login is required")
    if not model["ready"]:
        errors.append("analysis provider is not ready")
    if not renderer["ready"]:
        errors.append("no PDF renderer is available")
    if requested_timezone and requested_timezone != profile_timezone:
        errors.append(
            f"Hermes profile timezone must be {requested_timezone!r} before installing this schedule"
        )
    return {
        "ok": not errors,
        "errors": errors,
        "mail": mail,
        "analysis": model,
        "renderer": renderer,
        "schedule_timezone": {"requested": requested_timezone, "profile": profile_timezone},
    }


def _setup_status() -> dict:
    config = _load_config()
    config_errors = _config_diagnostics()
    mail = _mail_status()
    unresolved = []
    if config_errors:
        unresolved.append("personal_preferences")
    if not mail["installed"]:
        unresolved.append("agently_install")
    elif not mail["authenticated"]:
        unresolved.append("agently_login")
    return {
        "ok": not unresolved,
        "configured": bool(config) and not config_errors,
        "unresolved": unresolved,
        "mail": mail,
        "next_action": (
            "ask the user for research topics, recipient, schedule/timezone and optional model preferences"
            if "personal_preferences" in unresolved else
            "ask permission, then run mail-install --yes"
            if "agently_install" in unresolved else
            "run mail-login in the user's interactive terminal and wait for completion"
            if "agently_login" in unresolved else
            "run doctor, then offer a manual report test before installing the schedule"
        ),
        "privacy": "Never ask the user to paste a mail password, token, cookie, or OAuth code into chat.",
        "config": config,
    }


def _configure(args: argparse.Namespace) -> int:
    config = _load_config()
    if not config:
        initialized = _initialize(args.email_to, args.keyword, emit=False)
        if initialized:
            return initialized
        config = _load_config()
    research = config.setdefault("research", {})
    delivery = config.setdefault("delivery", {})
    analysis = config.setdefault("analysis", {})
    schedule = config.setdefault("schedule", {})
    if args.email_to:
        delivery["email_to"] = [str(value).strip() for value in args.email_to if "@" in str(value)]
    if args.keyword:
        research["core_keywords"] = [str(value).strip() for value in args.keyword if str(value).strip()]
    if args.max_selected is not None:
        config["max_selected"] = max(1, min(10, args.max_selected))
    if args.timezone:
        schedule["timezone"] = args.timezone
    if args.schedule:
        schedule["expression"] = args.schedule
    if args.provider:
        analysis["provider_name"] = args.provider
    if args.model:
        analysis["model"] = args.model
    if args.fallback_model:
        analysis["fallback_model"] = args.fallback_model
    if args.use_profile_weights is not None:
        research["use_profile_weights"] = args.use_profile_weights
    if args.use_user_feedback is not None:
        research["use_user_feedback"] = args.use_user_feedback
    _write_config(config)
    result = _setup_status()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not _config_diagnostics() else 2


def _initialize(email_to: list[str], keywords: list[str], emit: bool = True) -> int:
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
                if emit:
                    print("new setup requires --email-to and at least one --keyword", file=sys.stderr)
                return 2
            data.mkdir(parents=True, exist_ok=True)
            config = {
                "version": 2,
                "max_selected": 5,
                "research": {"core_keywords": clean_keywords, "use_profile_weights": False, "use_user_feedback": False},
                "analysis": {"auto": True, "provider_name": "USTC", "model": "deepseek-flash", "fallback_model": "qwen3.6-chat", "timeout_seconds": 180, "max_tokens": 7000},
                "delivery": {"channel": "email", "email_to": clean_emails},
                "schedule": {"expression": "0 2 * * 5", "timezone": "Asia/Shanghai"},
            }
            _write_config(config)
    errors = _config_diagnostics()
    if emit:
        print(json.dumps({"ok": not errors, "config": str(config_path), "migrated_from": migrated_from, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


def _install_schedule(schedule: str | None) -> int:
    readiness = _doctor_result()
    if not readiness["ok"]:
        print("setup is not ready: " + "; ".join(readiness["errors"]), file=sys.stderr)
        return 2
    config = _load_config()
    schedule_cfg = config.get("schedule") if isinstance(config.get("schedule"), dict) else {}
    schedule = schedule or str(schedule_cfg.get("expression") or "0 2 * * 5")
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
    if action == "setup":
        supplied = any(
            getattr(args, name, None) not in (None, [], "")
            for name in (
                "email_to", "keyword", "max_selected", "timezone", "schedule", "provider",
                "model", "fallback_model", "use_profile_weights", "use_user_feedback",
            )
        )
        if supplied:
            return _configure(args)
        print(json.dumps(_setup_status(), ensure_ascii=False, indent=2))
        return 0
    if action == "doctor":
        result = _doctor_result()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 2
    if action == "mail-status":
        result = _mail_status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["installed"] and result["authenticated"] else 2
    if action == "mail-install":
        if not args.yes:
            print("Refusing a global install without --yes", file=sys.stderr)
            return 2
        npm = shutil.which("npm")
        if not npm:
            print("npm is required to install @tencent-qqmail/agently-cli", file=sys.stderr)
            return 2
        result = subprocess.run(_portable_command(npm, "install", "--global", "@tencent-qqmail/agently-cli"))
        return result.returncode
    if action == "mail-login":
        cli = _find_agently_cli()
        if not cli:
            print("Agently CLI is not installed; run mail-install --yes first", file=sys.stderr)
            return 2
        return subprocess.run(_portable_command(cli, "auth", "login")).returncode
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
