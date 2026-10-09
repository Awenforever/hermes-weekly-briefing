"""Profile-aware CLI for Weekly Briefing v4."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


SUPPORTED_SEARCH_SOURCES = {
    "arxiv", "crossref", "semantic_scholar", "openalex", "dblp",
    "openreview", "scopus", "google_scholar", "europe_pmc", "core",
    "hal", "zenodo", "datacite",
}

SOURCE_GUIDANCE = {
    "general": ["openalex", "crossref", "semantic_scholar"],
    "computer_science": ["arxiv", "dblp", "openreview"],
    "life_sciences": ["europe_pmc"],
    "open_access_fulltext": ["core", "hal"],
    "research_outputs_and_dois": ["zenodo", "datacite"],
    "credentialed_optional": ["scopus", "google_scholar"],
}

DEFAULT_SEARCH_SOURCES = [
    "openalex", "semantic_scholar", "crossref", "arxiv", "dblp", "openreview",
    "europe_pmc", "core", "hal", "zenodo", "datacite",
]

DEFAULT_RECIPIENT_SALUTATION = "你好"
DEFAULT_SENDER_SIGNATURE = "Hermes"


def _trusted_ssl_context() -> ssl.SSLContext:
    """Use Hermes' bundled CA store when embedded Python has none (Windows)."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _home() -> Path:
    from hermes_constants import get_hermes_home

    return get_hermes_home()


def _root() -> Path:
    return Path(__file__).resolve().parent


def _data() -> Path:
    return _home() / "plugin-data" / "hermes-weekly-briefing"


def _runtime_path() -> Path:
    """Return the plugin-owned dependency directory.

    Hermes upgrades reconcile the core virtual environment against Hermes'
    lockfile.  Optional plugin packages therefore belong under plugin-data,
    which is both persistent and outside that reconciliation boundary.
    """
    abi = str(getattr(sys.implementation, "cache_tag", "python") or "python")
    return _data() / "runtime" / f"{abi}-{sys.platform}"


def register_cli(parser: argparse.ArgumentParser) -> None:
    actions = parser.add_subparsers(dest="weekly_action")
    actions.add_parser("status", help="Show data, configuration, and last-report status")
    setup = actions.add_parser("setup", help="Inspect or apply guided personal setup")
    setup.add_argument("--email-to", action="append", default=[])
    setup.add_argument("--recipient-salutation", default=None)
    setup.add_argument("--sender-signature", default=None)
    setup.add_argument("--keyword", action="append", default=[])
    setup.add_argument("--direction-term", action="append", default=[])
    setup.add_argument(
        "--require-all", action="append", default=[], metavar="TERM|SYNONYM",
        help="Add a concept group to the research profile; hard-require only in strict mode",
    )
    setup.add_argument("--require-any", action="append", default=[])
    setup.add_argument("--exclude-term", action="append", default=[])
    setup.add_argument("--minimum-any", type=int, default=None)
    setup.add_argument(
        "--selection-mode", choices=("semantic", "strict"), default=None,
        help="Let the model judge relevance (default), or explicitly enforce Boolean admission",
    )
    setup.add_argument(
        "--match-field", action="append", default=[],
        choices=("title", "abstract", "keywords", "venue"),
    )
    setup.add_argument("--max-selected", type=int, default=None)
    setup.add_argument("--timezone", default=None)
    setup.add_argument("--schedule", default=None)
    setup.add_argument("--provider", default=None)
    setup.add_argument("--model", default=None)
    setup.add_argument("--fallback-model", default=None)
    setup.add_argument("--search-source", action="append", default=[])
    setup.add_argument("--semantic-scholar-api-key-env", default=None)
    setup.add_argument("--openalex-api-key-env", default=None)
    setup.add_argument("--core-api-key-env", default=None)
    setup.add_argument("--scopus-api-key-env", default=None)
    setup.add_argument("--scopus-insttoken-env", default=None)
    setup.add_argument("--google-scholar-api-key-env", default=None)
    setup.add_argument(
        "--use-profile-weights",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=argparse.SUPPRESS,
    )
    setup.add_argument("--use-user-feedback", action=argparse.BooleanOptionalAction, default=None)
    feedback = actions.add_parser(
        "feedback",
        help="List or explicitly update user-confirmed research preferences",
    )
    feedback.add_argument("--topic", action="append", default=[])
    feedback.add_argument("--direction", choices=("more", "less", "explore"), default="more")
    feedback.add_argument("--remove", action="append", default=[])
    feedback.add_argument("--clear", action="store_true")
    feedback.add_argument("--note", default="")
    init = actions.add_parser("init", help="Initialize configuration or migrate legacy Weekly Briefing data")
    init.add_argument("--email-to", action="append", default=[])
    init.add_argument("--keyword", action="append", default=[])
    init.add_argument("--recipient-salutation", default=None)
    init.add_argument("--sender-signature", default=None)
    actions.add_parser("doctor", help="Validate configuration and delivery readiness")
    runtime = actions.add_parser("runtime-install", help="Install the declared PDF runtime dependencies")
    runtime.add_argument("--yes", action="store_true", help="Confirm installation into the active Hermes Python")
    actions.add_parser("dependencies-status", help="Check external dependency versions and runtime contracts")
    dependencies = actions.add_parser("dependencies-update", help="Update managed dependencies to latest and verify compatibility")
    dependencies.add_argument("--yes", action="store_true", help="Confirm npm and isolated Python package updates")
    actions.add_parser("mail-status", help="Check Agently CLI installation and login")
    actions.add_parser("search-status", help="Probe configured academic discovery engines")
    install_mail = actions.add_parser("mail-install", help="Install the supported Agently mail CLI")
    install_mail.add_argument("--yes", action="store_true", help="Confirm the global npm installation")
    actions.add_parser("mail-login", help="Start Agently login and return a portable authorization link")
    actions.add_parser("mail-login-start", help="Start Agently login for a terminal or Hermes message channel")
    actions.add_parser("mail-login-status", help="Check a previously started Agently login")
    run = actions.add_parser("run", help="Generate a report and optionally send it by email")
    run.add_argument("--email-to", action="append", default=[])
    run.add_argument("--send-email", action="store_true")
    run.add_argument("--max-selected", type=int, default=None)
    run.add_argument("--week", default=None)
    run.add_argument("--data-dir", default=None, help=argparse.SUPPRESS)
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
    requested_data = str(args.data_dir or os.environ.get("HERMES_WEEKLY_DATA_DIR") or _data()).strip()
    data_dir = Path(requested_data).expanduser().resolve()
    command = [sys.executable, str(script), "--data-dir", str(data_dir), "--max-selected", str(args.max_selected or configured_max)]
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
    env["HERMES_WEEKLY_DATA_DIR"] = str(data_dir)
    env["HERMES_WEEKLY_RUNTIME_PATH"] = str(_runtime_path())
    agently_cli = _find_agently_cli()
    if agently_cli:
        env["AGENTLY_CLI_PATH"] = agently_cli
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
        [_hermes_cli(), "cron", "list"], text=True, encoding="utf-8",
        errors="replace", capture_output=True, check=False,
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
    schedule = config.get("schedule") if isinstance(config.get("schedule"), dict) else {}
    configured_timezone = str(schedule.get("timezone") or "").strip()
    if not configured_timezone or "$" in configured_timezone:
        errors.append("schedule.timezone needs an explicit IANA timezone")
    search = config.get("search") if isinstance(config.get("search"), dict) else {}
    raw_sources = search.get("sources") if isinstance(search.get("sources"), list) else DEFAULT_SEARCH_SOURCES
    sources = {
        str(value).strip().casefold().replace("-", "_")
        for value in raw_sources
        if str(value).strip()
    }
    if not sources:
        errors.append("search.sources needs at least one academic discovery engine")
    unsupported = sorted(sources - SUPPORTED_SEARCH_SOURCES)
    if unsupported:
        errors.append("unsupported academic search sources: " + ", ".join(unsupported))
    if research.get("use_profile_weights") is True:
        errors.append(
            "research.use_profile_weights is retired because no verified profile producer exists; "
            "use explicit user-confirmed feedback instead"
        )
    relevance = research.get("relevance") if isinstance(research.get("relevance"), dict) else None
    if relevance is not None:
        mode = str(relevance.get("mode") or "semantic").strip().casefold()
        if mode not in {"semantic", "strict"}:
            errors.append("research.relevance.mode must be semantic or strict")
        groups = relevance.get("all_groups") if isinstance(relevance.get("all_groups"), list) else []
        for index, group in enumerate(groups, start=1):
            if not isinstance(group, list) or not any(str(value).strip() for value in group):
                errors.append(f"research.relevance.all_groups[{index}] needs at least one term")
        any_terms = relevance.get("any_terms") if isinstance(relevance.get("any_terms"), list) else []
        try:
            minimum_any = int(relevance.get("minimum_any") or 0)
        except (TypeError, ValueError):
            minimum_any = -1
        if minimum_any < 0 or minimum_any > len([term for term in any_terms if str(term).strip()]):
            errors.append("research.relevance.minimum_any must be between zero and the any-term count")
    return errors


def _effective_personalization(config: dict) -> dict[str, str]:
    def usable(value: object) -> str:
        text = str(value or "").strip()
        return "" if "$" in text else text

    delivery = config.get("delivery") if isinstance(config.get("delivery"), dict) else {}
    recipient_salutation = usable(delivery.get("recipient_salutation"))
    sender_signature = usable(delivery.get("sender_signature"))
    user = config.get("user") if isinstance(config.get("user"), dict) else {}
    style = config.get("style") if isinstance(config.get("style"), dict) else {}
    salutation_source = "delivery.recipient_salutation"
    signature_source = "delivery.sender_signature"
    if (
        not str(delivery.get("letter_identity_mode") or "").strip()
        and recipient_salutation == DEFAULT_RECIPIENT_SALUTATION
        and sender_signature == DEFAULT_SENDER_SIGNATURE
    ):
        recipient_salutation = ""
        sender_signature = ""
    if not recipient_salutation:
        recipient_salutation = usable(user.get("display_name"))
        salutation_source = "user.display_name" if recipient_salutation else "default"
    if not sender_signature:
        sender_signature = usable(style.get("signature"))
        signature_source = "style.signature" if sender_signature else "default"
    if not recipient_salutation:
        salutation_source = "model_dynamic"
    if not sender_signature:
        signature_source = "model_dynamic"
    return {
        "recipient_salutation": recipient_salutation,
        "sender_signature": sender_signature,
        "recipient_salutation_source": salutation_source,
        "sender_signature_source": signature_source,
    }


def _personalization_errors(config: dict) -> list[str]:
    delivery = config.get("delivery") if isinstance(config.get("delivery"), dict) else {}
    errors = []
    if "$" in str(delivery.get("recipient_salutation") or ""):
        errors.append("delivery.recipient_salutation contains an unresolved placeholder")
    if "$" in str(delivery.get("sender_signature") or ""):
        errors.append("delivery.sender_signature contains an unresolved placeholder")
    return errors


def _search_status(config: dict, probe: bool = True) -> dict:
    search = config.get("search") if isinstance(config.get("search"), dict) else {}
    raw_sources = search.get("sources") if isinstance(search.get("sources"), list) else DEFAULT_SEARCH_SOURCES
    sources = [
        str(value).strip().casefold().replace("-", "_")
        for value in raw_sources
        if str(value).strip()
    ]
    probes = {
        "arxiv": "https://export.arxiv.org/api/query?search_query=all%3Atest&start=0&max_results=1",
        "crossref": "https://api.crossref.org/works?query=test&rows=1",
        "semantic_scholar": "https://api.semanticscholar.org/graph/v1/paper/search?query=test&limit=1&fields=title",
        "openalex": "https://api.openalex.org/works?search=test&per_page=1&select=id,title",
        "dblp": "https://dblp.org/search/publ/api?q=test&h=1&format=json",
        "openreview": "https://api2.openreview.net/notes/search?term=test&content=title&source=forum&limit=1",
        "scopus": "https://api.elsevier.com/content/search/scopus?query=TITLE-ABS-KEY%28test%29&count=1",
        "google_scholar": "https://serpapi.com/search.json?engine=google_scholar&q=test&num=1",
        "europe_pmc": "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=test&format=json&pageSize=1",
        "core": "https://api.core.ac.uk/v3/search/works?q=test&limit=1",
        "hal": "https://api.hal.science/search/?q=test&wt=json&rows=1",
        "zenodo": "https://zenodo.org/api/records?q=test&size=1",
        "datacite": "https://api.datacite.org/dois?query=test&page%5Bsize%5D=1",
    }
    details = []
    for source in sources:
        item = {"source": source, "supported": source in SUPPORTED_SEARCH_SOURCES, "ready": False}
        if source not in SUPPORTED_SEARCH_SOURCES:
            item["diagnostic"] = "unsupported by this plugin version"
            details.append(item)
            continue
        if not probe:
            item.update({"ready": True, "diagnostic": "configured; live probe skipped"})
            details.append(item)
            continue
        headers = {"User-Agent": "hermes-weekly-briefing/4"}
        if source == "semantic_scholar":
            key_env = str(search.get("semantic_scholar_api_key_env") or "SEMANTIC_SCHOLAR_API_KEY").strip()
            key = str(os.environ.get(key_env) or "").strip()
            if key:
                headers["x-api-key"] = key
            item["credential"] = "configured" if key else "anonymous"
        elif source == "openalex":
            key_env = str(search.get("openalex_api_key_env") or "OPENALEX_API_KEY").strip()
            key = str(os.environ.get(key_env) or "").strip()
            if key:
                headers["Authorization"] = "Bearer " + key
            item["credential"] = "configured" if key else "anonymous"
        elif source == "core":
            key_env = str(search.get("core_api_key_env") or "CORE_API_KEY").strip()
            key = str(os.environ.get(key_env) or "").strip()
            if key:
                headers["Authorization"] = "Bearer " + key
            item["credential"] = "configured" if key else "anonymous"
        elif source == "scopus":
            key_env = str(search.get("scopus_api_key_env") or "SCOPUS_API_KEY").strip()
            key = str(os.environ.get(key_env) or "").strip()
            token_env = str(search.get("scopus_insttoken_env") or "SCOPUS_INSTTOKEN").strip()
            insttoken = str(os.environ.get(token_env) or "").strip()
            if not key:
                item.update({"diagnostic": f"credential missing: {key_env}", "credential": "missing"})
                details.append(item)
                continue
            headers["X-ELS-APIKey"] = key
            if insttoken:
                headers["X-ELS-Insttoken"] = insttoken
            item["credential"] = "configured"
        elif source == "google_scholar":
            key_env = str(search.get("google_scholar_api_key_env") or "SERPAPI_API_KEY").strip()
            key = str(os.environ.get(key_env) or "").strip()
            if not key:
                item.update({"diagnostic": f"credential missing: {key_env}; Google Scholar has no public official search API", "credential": "missing"})
                details.append(item)
                continue
            probes[source] += "&api_key=" + urllib.parse.quote(key)
            item["credential"] = "configured via SerpApi"
        try:
            request = urllib.request.Request(probes[source], headers=headers)
            with urllib.request.urlopen(
                request, timeout=10, context=_trusted_ssl_context()
            ) as response:
                response.read(1024)
                item["ready"] = 200 <= int(getattr(response, "status", 200) or 200) < 400
            item["diagnostic"] = "reachable" if item["ready"] else "unexpected response"
        except urllib.error.HTTPError as exc:
            item["diagnostic"] = f"HTTP {exc.code}"
        except Exception as exc:
            item["diagnostic"] = str(exc)[:240]
        details.append(item)
    ready = [item["source"] for item in details if item.get("ready")]
    return {
        "ok": bool(ready),
        "configured_sources": sources,
        "ready_sources": ready,
        "engines": details,
        "source_guidance": SOURCE_GUIDANCE,
        "openalex_key_signup": "https://openalex.org/settings/api",
        "next_action": (
            "academic discovery is ready"
            if ready else
            "choose sources by research coverage and configure any optional credential; production OpenAlex keys are free at https://openalex.org/settings/api"
        ),
    }


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


def _feedback_path() -> Path:
    return _data() / "profile" / "topic_feedback.json"


def _feedback_events_path() -> Path:
    return _data() / "profile" / "feedback_events.jsonl"


def _load_feedback() -> dict:
    path = _feedback_path()
    if not path.is_file():
        return {"version": 1, "biases": []}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "biases": []}
    return value if isinstance(value, dict) else {"version": 1, "biases": []}


def _write_feedback(value: dict) -> None:
    path = _feedback_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.new")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _record_feedback_event(event: dict) -> None:
    path = _feedback_events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _feedback_command(args: argparse.Namespace) -> int:
    additions = [str(value).strip() for value in args.topic if str(value).strip()]
    removals = [str(value).strip() for value in args.remove if str(value).strip()]
    mutated = bool(args.clear or additions or removals)
    if mutated and not _load_config():
        print("Weekly Briefing must be configured before recording feedback", file=sys.stderr)
        return 2
    if args.clear and (additions or removals):
        print("--clear cannot be combined with --topic or --remove", file=sys.stderr)
        return 2
    feedback = _load_feedback()
    current = feedback.get("biases") if isinstance(feedback.get("biases"), list) else []
    biases = [item for item in current if isinstance(item, dict)]
    now = datetime.now(timezone.utc).isoformat()
    events: list[dict] = []

    if args.clear:
        biases = []
        events.append({"action": "clear", "source": "user", "recorded_at": now})
    else:
        remove_keys = {value.casefold() for value in removals}
        if remove_keys:
            biases = [
                item for item in biases
                if str(item.get("topic") or item.get("keyword") or "").strip().casefold()
                not in remove_keys
            ]
            events.extend(
                {"action": "remove", "source": "user", "topic": value, "recorded_at": now}
                for value in removals
            )
        direction = {
            "more": "increase",
            "less": "decrease",
            "explore": "force_explore",
        }[args.direction]
        for topic in additions:
            key = topic.casefold()
            biases = [
                item for item in biases
                if str(item.get("topic") or item.get("keyword") or "").strip().casefold() != key
            ]
            item = {
                "source": "user",
                "direction": direction,
                "topic": topic,
                "updated_at": now,
            }
            if str(args.note or "").strip():
                item["note"] = str(args.note).strip()
            biases.append(item)
            events.append({"action": "set", **item, "recorded_at": now})

    if mutated:
        feedback = {"version": 1, "biases": biases, "updated_at": now}
        _write_feedback(feedback)
        for event in events:
            _record_feedback_event(event)
        config = _load_config()
        research = config.setdefault("research", {})
        research["use_user_feedback"] = bool(biases)
        research.pop("use_profile_weights", None)
        _write_config(config)

    print(json.dumps({
        "ok": True,
        "enabled": bool((_load_config().get("research") or {}).get("use_user_feedback")),
        "feedback": _load_feedback(),
        "collection": "explicit user-confirmed command; email replies are not monitored",
    }, ensure_ascii=False, indent=2))
    return 0


def _find_agently_cli() -> str | None:
    npm = _find_npm()
    npm_directory = Path(npm).parent if npm else None
    roaming_npm = Path(os.environ.get("APPDATA", "")) / "npm" if os.environ.get("APPDATA") else None
    candidates = [
        os.environ.get("AGENTLY_CLI_PATH"),
        shutil.which("agently-cli"),
        shutil.which("agently"),
        str(npm_directory / "agently-cli.cmd") if npm_directory else None,
        str(npm_directory / "agently.cmd") if npm_directory else None,
        str(roaming_npm / "agently-cli.cmd") if roaming_npm else None,
        str(roaming_npm / "agently.cmd") if roaming_npm else None,
        str(Path.home() / ".local" / "bin" / "agently-cli"),
        str(Path.home() / ".local" / "bin" / "agently"),
        "/usr/local/bin/agently-cli",
        "/usr/local/bin/agently",
    ]
    return next((str(value) for value in candidates if value and Path(value).is_file()), None)


def _find_npm() -> str | None:
    """Find npm even when a Windows package manager exposes only node.exe.

    WinGet's user-scoped portable Node package creates a command alias for
    ``node`` but keeps ``npm.cmd`` beside the real executable.  Looking only at
    PATH therefore produces a false missing-dependency result on a clean
    Windows profile.
    """
    candidates: list[str | None] = [os.environ.get("NPM_PATH"), shutil.which("npm")]
    node = shutil.which("node")
    if node:
        node_path = Path(node)
        candidates.extend(
            [
                str(node_path.with_name("npm.cmd")),
                str(node_path.resolve().with_name("npm.cmd")),
            ]
        )
    local_app_data = os.environ.get("LOCALAPPDATA")
    if os.name == "nt" and local_app_data:
        packages = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        candidates.extend(
            str(path)
            for path in sorted(packages.glob("OpenJS.NodeJS*/*/npm.cmd"), reverse=True)
        )
    candidates.extend(["/usr/local/bin/npm", "/usr/bin/npm"])
    return next((str(value) for value in candidates if value and Path(value).is_file()), None)


def _portable_command(executable: str, *arguments: str) -> list[str]:
    command = [executable, *arguments]
    if os.name == "nt" and Path(executable).suffix.casefold() in {".cmd", ".bat"}:
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
    return command


def _find_uv() -> str | None:
    """Locate uv in PATH or in the profile-managed Hermes tool directory."""
    executable = "uv.exe" if os.name == "nt" else "uv"
    candidates = [
        shutil.which("uv"),
        str(_home() / "bin" / executable),
        str(Path.home() / ".local" / "bin" / executable),
    ]
    return next((str(value) for value in candidates if value and Path(value).is_file()), None)


def _agently_env(config: dict | None = None) -> dict[str, str]:
    """Keep every Agently probe/login/send in Hermes' persisted workspace."""
    env = os.environ.copy()
    if not str(env.get("AGENTLY_WORKSPACE") or "").strip():
        current = config if isinstance(config, dict) else _load_config()
        delivery = current.get("delivery") if isinstance(current.get("delivery"), dict) else {}
        env["AGENTLY_WORKSPACE"] = str(delivery.get("agently_workspace") or "hermes").strip()
    # Agently also auto-detects HERMES_SESSION_ID.  A transient chat/session id must
    # not override the stable workspace selected above or each invocation appears
    # to need a fresh OAuth login.
    env.pop("HERMES_SESSION_ID", None)
    return env


def _npm_latest(package: str) -> str:
    npm = _find_npm()
    if not npm:
        return ""
    try:
        completed = subprocess.run(
            _portable_command(npm, "view", package, "version", "--json"),
            text=True, encoding="utf-8", errors="replace", capture_output=True,
            timeout=20, check=False,
        )
        if completed.returncode:
            return ""
        value = json.loads(completed.stdout or '""')
        return str(value or "").strip()
    except Exception:
        return ""


def _agently_contract(cli: str) -> dict:
    checks = {
        "version": _portable_command(cli, "--version"),
        "send_help": _portable_command(cli, "message", "+send", "--help"),
        "login_help": _portable_command(cli, "auth", "login", "--help"),
    }
    outputs: dict[str, str] = {}
    for name, command in checks.items():
        try:
            completed = subprocess.run(
                command, text=True, encoding="utf-8", errors="replace",
                capture_output=True, timeout=20, check=False, env=_agently_env(),
            )
            outputs[name] = "\n".join((completed.stdout, completed.stderr)).strip()
            if completed.returncode:
                return {"compatible": False, "diagnostic": f"{name} exited {completed.returncode}"}
        except Exception as exc:
            return {"compatible": False, "diagnostic": f"{name}: {exc}"}
    version_match = re.search(r"(?i)version\s+([0-9]+(?:\.[0-9]+){1,3}(?:[-+][^\s]+)?)", outputs["version"])
    if not version_match:
        version_match = re.search(r"\b([0-9]+(?:\.[0-9]+){1,3}(?:[-+][^\s]+)?)\b", outputs["version"])
    required_send = ("--body-file", "--attachment", "--confirmation-token", "--to", "--subject")
    missing = [flag for flag in required_send if flag not in outputs["send_help"]]
    if "--verbose" not in outputs["login_help"]:
        missing.append("auth login --verbose")
    return {
        "compatible": not missing,
        "installed_version": version_match.group(1) if version_match else "",
        "missing_contracts": missing,
        "diagnostic": "Agently send/login contract is compatible" if not missing else "missing required CLI contracts",
    }


def _mail_status(probe: bool = True, check_latest: bool = False) -> dict:
    cli = _find_agently_cli()
    agently_env = _agently_env()
    result = {
        "installed": bool(cli),
        "authenticated": False,
        "cli": cli,
        "workspace": agently_env.get("AGENTLY_WORKSPACE"),
        "install_package": "@tencent-qqmail/agently-cli",
    }
    if not cli or not probe:
        return result
    contract = _agently_contract(cli)
    result.update(contract)
    latest = _npm_latest(result["install_package"]) if check_latest else ""
    result["latest_version"] = latest
    result["update_available"] = bool(
        latest and contract.get("installed_version") and latest != contract.get("installed_version")
    )
    try:
        check = subprocess.run(
            _portable_command(cli, "+me"), text=True, encoding="utf-8",
            errors="replace", capture_output=True,
            timeout=30, check=False, env=agently_env,
        )
        result["authenticated"] = check.returncode == 0
        if check.returncode:
            detail = "\n".join(part.strip() for part in (check.stdout, check.stderr) if part.strip()) or "identity probe failed"
            result["diagnostic"] = detail[-500:]
    except Exception as exc:
        result["diagnostic"] = str(exc)
    return result


def _pypi_latest(package: str) -> str:
    try:
        request = urllib.request.Request(
            f"https://pypi.org/pypi/{urllib.parse.quote(package)}/json",
            headers={"User-Agent": "HermesWeeklyBriefing/dependency-check"},
        )
        with urllib.request.urlopen(request, timeout=12, context=_trusted_ssl_context()) as response:
            value = json.loads(response.read().decode("utf-8", errors="replace"))
        return str((value.get("info") or {}).get("version") or "").strip()
    except Exception:
        return ""


def _mail_login_dir() -> Path:
    return _data() / "mail-login"


def _mail_login_state_path() -> Path:
    return _mail_login_dir() / "state.json"


def _write_private_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".new")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    os.replace(temporary, path)


def _read_mail_login_state() -> dict:
    path = _mail_login_state_path()
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _login_url(text: str) -> str:
    matches = re.findall(r"https://[^\s<>\"']+", str(text or ""))
    return next((value.rstrip(".,，。)）]") for value in matches if "oauth" in value.casefold()), "")


def _process_alive(pid: object) -> bool:
    try:
        value = int(pid)
        if value <= 0:
            return False
        os.kill(value, 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def _optional_login_qr(url: str) -> str:
    """Create a QR when the optional plugin runtime supports it.

    A clickable URL remains the canonical cross-channel contract; failure to
    render a QR never blocks authentication.
    """
    runtime = _runtime_path()
    if runtime.is_dir() and str(runtime) not in sys.path:
        sys.path.insert(0, str(runtime))
    try:
        import qrcode

        path = _mail_login_dir() / "authorization.png"
        image = qrcode.make(url)
        image.save(path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return str(path.resolve())
    except Exception:
        return ""


def _mail_login_public_state(state: dict) -> dict:
    result = {
        "installed": True,
        "authenticated": False,
        "status": str(state.get("status") or "pending"),
        "verification_url": str(state.get("verification_url") or ""),
        "started_at": str(state.get("started_at") or ""),
        "expires_at": str(state.get("expires_at") or ""),
        "next_action": "Open verification_url, finish authorization, then run mail-login-status.",
    }
    qr_path = str(state.get("qr_path") or "")
    if qr_path and Path(qr_path).is_file():
        result["qr_path"] = qr_path
        result["media_directive"] = f"MEDIA:{qr_path}"
    return result


def _mail_login_expired(state: dict) -> bool:
    try:
        return datetime.now(timezone.utc) >= datetime.fromisoformat(
            str(state.get("expires_at") or "")
        )
    except (TypeError, ValueError):
        return False


def _start_mail_login(wait_seconds: float = 12.0) -> tuple[int, dict]:
    current = _mail_status()
    if not current.get("installed"):
        return 2, {
            **current,
            "status": "missing_cli",
            "next_action": "Run mail-install --yes first.",
        }
    if current.get("compatible") is False:
        return 2, {
            **current,
            "status": "incompatible_cli",
            "next_action": "Run dependencies-update --yes before starting login.",
        }
    if current.get("authenticated"):
        return 0, {**current, "status": "authenticated", "next_action": "No login is needed."}

    existing = _read_mail_login_state()
    if (
        existing.get("status") == "pending"
        and existing.get("verification_url")
        and not _mail_login_expired(existing)
        and _process_alive(existing.get("pid"))
    ):
        return 0, _mail_login_public_state(existing)

    login_dir = _mail_login_dir()
    login_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = login_dir / "agently.stdout.log"
    stderr_path = login_dir / "agently.stderr.log"
    for path in (stdout_path, stderr_path):
        path.write_text("", encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    cli = str(current["cli"])
    popen_kwargs: dict = {
        "env": _agently_env(),
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    else:
        popen_kwargs["start_new_session"] = True
    with stdout_path.open("a", encoding="utf-8") as stdout, stderr_path.open("a", encoding="utf-8") as stderr:
        process = subprocess.Popen(
            _portable_command(cli, "auth", "login", "--verbose"),
            stdout=stdout,
            stderr=stderr,
            **popen_kwargs,
        )

    deadline = time.monotonic() + max(0.5, float(wait_seconds))
    url = ""
    while time.monotonic() < deadline:
        combined = stdout_path.read_text(encoding="utf-8", errors="replace") + "\n" + stderr_path.read_text(encoding="utf-8", errors="replace")
        url = _login_url(combined)
        if url or process.poll() is not None:
            break
        time.sleep(0.1)
    if not url:
        diagnostic = (stderr_path.read_text(encoding="utf-8", errors="replace") or stdout_path.read_text(encoding="utf-8", errors="replace"))[-600:]
        state = {
            "status": "failed" if process.poll() is not None else "link_unavailable",
            "pid": process.pid,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic": diagnostic,
        }
        _write_private_json(_mail_login_state_path(), state)
        return 2, {
            "installed": True,
            "authenticated": False,
            "status": state["status"],
            "diagnostic": diagnostic,
            "next_action": "Retry mail-login-start in an interactive terminal.",
        }

    now = datetime.now(timezone.utc)
    state = {
        "status": "pending",
        "pid": process.pid,
        "started_at": now.isoformat(),
        "expires_at": datetime.fromtimestamp(now.timestamp() + 900, timezone.utc).isoformat(),
        "verification_url": url,
        "qr_path": _optional_login_qr(url),
    }
    _write_private_json(_mail_login_state_path(), state)
    return 0, _mail_login_public_state(state)


def _mail_login_status() -> tuple[int, dict]:
    status = _mail_status()
    if status.get("authenticated"):
        state = _read_mail_login_state()
        if state:
            state = {"status": "authenticated", "completed_at": datetime.now(timezone.utc).isoformat()}
            _write_private_json(_mail_login_state_path(), state)
        return 0, {**status, "status": "authenticated", "next_action": "Run doctor to continue setup."}
    state = _read_mail_login_state()
    if not state:
        return 2, {**status, "status": "not_started", "next_action": "Run mail-login-start."}
    if _mail_login_expired(state):
        return 2, {**status, "status": "expired", "next_action": "Run mail-login-start for a new link."}
    if not _process_alive(state.get("pid")):
        return 2, {**status, "status": "failed", "next_action": "Run mail-login-start to retry."}
    return 2, _mail_login_public_state(state)


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


def _renderer_status(check_latest: bool = False, runtime_path: Path | None = None) -> dict:
    runtime = (runtime_path or _runtime_path()).resolve()
    probe = f"""
import importlib
import importlib.metadata
import json
import re
import sys
from pathlib import Path

runtime = Path({str(runtime)!r}).resolve()
sys.path.insert(0, str(runtime))
result = {{}}
metadata = {{"weasyprint": [], "reportlab": []}}
for dist in importlib.metadata.distributions(path=[str(runtime)]):
    raw_name = str(dist.metadata.get("Name") or "")
    name = re.sub(r"[-_.]+", "-", raw_name).lower()
    if name in metadata:
        metadata[name].append({{
            "version": str(dist.version or ""),
            "path": str(getattr(dist, "_path", "")),
        }})
for name in ("weasyprint", "reportlab"):
    try:
        module = importlib.import_module(name)
        origin = Path(module.__file__).resolve()
        isolated = origin == runtime or runtime in origin.parents
        module_version = str(
            getattr(module, "__version__", "")
            or getattr(module, "Version", "")
        )
        distributions = metadata[name]
        metadata_versions = sorted({{item["version"] for item in distributions if item["version"]}})
        integrity_errors = []
        if isolated and len(distributions) != 1:
            integrity_errors.append(
                f"{{name}} has {{len(distributions)}} distribution metadata records; expected exactly one"
            )
        if isolated and len(metadata_versions) == 1 and module_version and metadata_versions[0] != module_version:
            integrity_errors.append(
                f"{{name}} import version {{module_version}} does not match metadata {{metadata_versions[0]}}"
            )
        result[name] = {{
            "available": True,
            "isolated": isolated,
            "origin": str(origin),
            "version": module_version or (metadata_versions[0] if len(metadata_versions) == 1 else ""),
            "metadata": distributions,
            "metadata_versions": metadata_versions,
            "integrity_errors": integrity_errors,
        }}
    except Exception as exc:
        distributions = metadata[name]
        metadata_versions = sorted({{item["version"] for item in distributions if item["version"]}})
        integrity_errors = []
        if len(distributions) > 1:
            integrity_errors.append(
                f"{{name}} has {{len(distributions)}} distribution metadata records; expected at most one when unavailable"
            )
        result[name] = {{
            "available": False,
            "isolated": False,
            "error": str(exc),
            "metadata": distributions,
            "metadata_versions": metadata_versions,
            "integrity_errors": integrity_errors,
        }}
print(json.dumps(result))
"""
    try:
        completed = subprocess.run(
            [sys.executable, "-c", probe], text=True, encoding="utf-8",
            errors="replace", capture_output=True,
            timeout=30, check=False,
        )
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        result = json.loads(lines[-1]) if completed.returncode == 0 and lines else {}
    except Exception:
        result = {}
    isolated = [
        name for name in ("weasyprint", "reportlab")
        if isinstance(result.get(name), dict) and result[name].get("isolated") is True
    ]
    host_available = [
        name for name in ("weasyprint", "reportlab")
        if isinstance(result.get(name), dict)
        and result[name].get("available") is True
        and result[name].get("isolated") is not True
    ]
    versions = {}
    for name, value in result.items():
        if not isinstance(value, dict):
            continue
        if value.get("isolated") is True:
            versions[name] = str(value.get("version") or "")
            continue
        metadata_versions = value.get("metadata_versions", [])
        if value.get("available") is False and len(metadata_versions) == 1:
            # Optional WeasyPrint may be correctly installed but unavailable
            # because the OS lacks Pango/GTK. Its isolated distribution
            # metadata still provides an unambiguous update version.
            versions[name] = str(metadata_versions[0])
    latest_versions = {
        name: _pypi_latest(name) for name in ("weasyprint", "reportlab")
    } if check_latest else {}
    updates = {
        name: {"installed": version, "latest": latest_versions.get(name, "")}
        for name, version in versions.items()
        if latest_versions.get(name) and latest_versions[name] != version
    }
    # ReportLab is the portable renderer contract on Windows/WSL/Linux/Docker.
    # WeasyPrint is installed at its current release too, but native GTK/Pango
    # availability is an OS capability rather than a Python package version;
    # its import failure must not make a healthy ReportLab fallback unusable.
    integrity_errors = [
        str(error)
        for name in ("weasyprint", "reportlab")
        for error in (
            result.get(name, {}).get("integrity_errors", [])
            if isinstance(result.get(name), dict) else []
        )
    ]
    integrity_ok = not integrity_errors
    complete = "reportlab" in isolated and integrity_ok
    return {
        "ready": bool(isolated) and integrity_ok,
        "complete": complete,
        "available": isolated,
        "host_available": host_available,
        "origins": {
            name: value.get("origin")
            for name, value in result.items()
            if isinstance(value, dict) and value.get("origin")
        },
        "versions": versions,
        "metadata_versions": {
            name: value.get("metadata_versions", [])
            for name, value in result.items()
            if isinstance(value, dict)
        },
        "integrity_ok": integrity_ok,
        "integrity_errors": integrity_errors,
        "latest_versions": latest_versions,
        "update_available": updates,
        "required_renderer": "reportlab",
        "optional_renderer": "weasyprint",
        "runtime": str(runtime),
        "isolated": bool(isolated),
        "diagnostic": (
            "plugin-owned PDF runtime has conflicting package metadata; run dependencies-update --yes"
            if integrity_errors else
            "plugin-owned PDF runtime is ready" if isolated else
            "run runtime-install --yes; packages found only in Hermes core are not persistent"
        ),
    }


def _runtime_render_smoke(runtime: Path) -> dict:
    scripts = _root() / "research" / "weekly-briefing-v2" / "scripts"
    probe = f"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, {str(runtime.resolve())!r})
sys.path.insert(0, {str(scripts.resolve())!r})
from run_weekly_e2e import make_pdf

with tempfile.TemporaryDirectory(prefix="weekly-runtime-smoke-") as raw:
    target = Path(raw) / "smoke.pdf"
    make_pdf(
        "<html><body><h1>Weekly Briefing</h1><p>Dependency compatibility check.</p></body></html>",
        "# Weekly Briefing\\n\\nDependency compatibility check.",
        target,
    )
    payload = target.read_bytes()
    ok = payload.startswith(b"%PDF") and len(payload) > 500
    print(json.dumps({{"ok": ok, "size": len(payload)}}))
    raise SystemExit(0 if ok else 2)
"""
    try:
        completed = subprocess.run(
            [sys.executable, "-c", probe], text=True, encoding="utf-8",
            errors="replace", capture_output=True, timeout=90, check=False,
        )
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        result = json.loads(lines[-1]) if lines else {}
        return {
            "ok": completed.returncode == 0 and result.get("ok") is True,
            "size": int(result.get("size") or 0),
            "diagnostic": completed.stderr.strip()[-1000:],
        }
    except Exception as exc:
        return {"ok": False, "size": 0, "diagnostic": str(exc)}


def _swap_runtime(stage: Path, runtime: Path) -> None:
    backup = runtime.with_name(
        f".{runtime.name}.rollback-{os.getpid()}-{int(time.time() * 1000)}"
    )
    had_runtime = runtime.exists()
    if had_runtime:
        runtime.rename(backup)
    try:
        stage.rename(runtime)
    except Exception:
        if had_runtime and backup.exists() and not runtime.exists():
            backup.rename(runtime)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def _install_runtime(confirmed: bool, emit: bool = True) -> int:
    if not confirmed:
        print("Refusing to install the plugin runtime without --yes", file=sys.stderr)
        return 2
    # Deliberately install current releases without upper caps. Compatibility
    # is established by the renderer contract and full plugin acceptance, not
    # by freezing users on an old major version.
    packages = ["weasyprint", "reportlab"]
    runtime = _runtime_path()
    runtime.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{runtime.name}.stage-", dir=runtime.parent))
    if importlib.util.find_spec("pip") is not None:
        command = [
            sys.executable, "-m", "pip", "install", "--upgrade",
            "--target", str(stage), *packages,
        ]
    else:
        uv = _find_uv()
        if not uv:
            print("Neither pip nor uv is available; install one package manager first", file=sys.stderr)
            shutil.rmtree(stage, ignore_errors=True)
            return 2
        command = _portable_command(
            uv, "pip", "install", "--python", sys.executable,
            "--upgrade", "--target", str(stage), *packages
        )
    try:
        completed = subprocess.run(command)
        if completed.returncode:
            return completed.returncode
        status = _renderer_status(check_latest=True, runtime_path=stage)
        smoke = _runtime_render_smoke(stage)
        status["render_smoke"] = smoke
        status["operation"] = "runtime_update"
        if not status.get("complete") or status.get("update_available") or not smoke.get("ok"):
            if emit:
                print(json.dumps(status, ensure_ascii=False, indent=2))
            return 2
        _swap_runtime(stage, runtime)
        stage = Path()
    finally:
        if stage and stage.exists() and stage != Path("."):
            shutil.rmtree(stage, ignore_errors=True)
    status = _renderer_status(check_latest=True)
    status["render_smoke"] = _runtime_render_smoke(runtime)
    status["operation"] = "runtime_update"
    if emit:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if (
        status.get("complete")
        and not status.get("update_available")
        and status.get("render_smoke", {}).get("ok") is True
    ) else 2


def _install_mail(confirmed: bool, emit: bool = True) -> int:
    if not confirmed:
        print("Refusing a global install without --yes", file=sys.stderr)
        return 2
    npm = _find_npm()
    if not npm:
        print(
            "npm is required to install @tencent-qqmail/agently-cli; "
            "install a supported Node.js LTS package, restart the shell, and retry",
            file=sys.stderr,
        )
        return 2
    before = _mail_status(probe=True, check_latest=False)
    completed = subprocess.run(_portable_command(
        npm, "install", "--global", "@tencent-qqmail/agently-cli@latest"
    ))
    if completed.returncode:
        return completed.returncode
    after = _mail_status(probe=True, check_latest=True)
    preserved_auth = not before.get("authenticated") or bool(after.get("authenticated"))
    result = {
        "operation": "agently_update",
        "before_version": str(before.get("installed_version") or ""),
        "installed_version": str(after.get("installed_version") or ""),
        "latest_version": str(after.get("latest_version") or ""),
        "compatible": bool(after.get("compatible")),
        "authentication_preserved": preserved_auth,
        "authenticated": bool(after.get("authenticated")),
        "workspace": after.get("workspace"),
        "update_available": bool(after.get("update_available")),
        "diagnostic": after.get("diagnostic"),
    }
    if emit:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["compatible"] and preserved_auth and not result["update_available"] else 2


def _dependencies_status() -> dict:
    mail = _mail_status(probe=True, check_latest=True)
    runtime = _renderer_status(check_latest=True)
    errors = []
    if not mail.get("installed"):
        errors.append("Agently CLI is not installed")
    elif mail.get("compatible") is False:
        errors.append("installed Agently CLI does not satisfy the current send/login contract")
    if mail.get("update_available"):
        errors.append("Agently CLI update is available")
    if runtime.get("integrity_ok") is False:
        errors.append("plugin-owned PDF runtime has conflicting package metadata")
    elif not runtime.get("complete"):
        errors.append("plugin-owned PDF runtime is not installed")
    elif runtime.get("update_available"):
        errors.append("plugin-owned PDF runtime updates are available")
    return {"ok": not errors, "errors": errors, "mail": mail, "runtime": runtime}


def _update_dependencies(confirmed: bool) -> int:
    if not confirmed:
        print("Refusing dependency updates without --yes", file=sys.stderr)
        return 2
    runtime_code = _install_runtime(True, emit=False)
    mail_code = _install_mail(True, emit=False)
    result = _dependencies_status()
    result["operation"] = "dependencies_update"
    result["runtime_exit_code"] = runtime_code
    result["mail_exit_code"] = mail_code
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if runtime_code == 0 and mail_code == 0 and result["ok"] else 2


def _profile_timezone() -> str:
    if os.environ.get("HERMES_TIMEZONE"):
        return str(os.environ["HERMES_TIMEZONE"]).strip()
    path = _home() / "config.yaml"
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        try:
            import yaml
            value = yaml.safe_load(text)
            if isinstance(value, dict) and str(value.get("timezone") or "").strip():
                return str(value["timezone"]).strip()
        except Exception:
            pass
        match = re.search(
            r"(?m)^[ \t]*timezone[ \t]*:[ \t]*['\"]?([^'\"#\r\n]+)", text
        )
        if match and match.group(1).strip():
            return match.group(1).strip()
    return str(os.environ.get("TZ") or "").strip()


def _doctor_result() -> dict:
    config = _load_config()
    errors = _config_diagnostics() + (_personalization_errors(config) if config else [])
    mail = _mail_status(check_latest=True)
    model = _model_status(config) if config else {"ready": False, "diagnostic": "configuration missing"}
    renderer = _renderer_status(check_latest=True)
    search = _search_status(config) if config else {"ok": False, "configured_sources": [], "ready_sources": [], "engines": []}
    schedule_cfg = config.get("schedule") if isinstance(config.get("schedule"), dict) else {}
    requested_timezone = str(schedule_cfg.get("timezone") or "").strip()
    profile_timezone = _profile_timezone()
    if not mail["installed"]:
        errors.append("Agently CLI is not installed")
    elif mail.get("compatible") is False:
        errors.append("Agently CLI is incompatible with the current Weekly Briefing contract")
    elif mail.get("update_available"):
        errors.append("Agently CLI update is available; run dependencies-update --yes")
    elif not mail["authenticated"]:
        errors.append("Agently CLI login is required")
    if not model["ready"]:
        errors.append("analysis provider is not ready")
    if renderer.get("integrity_ok") is False:
        errors.append("plugin-owned PDF runtime has conflicting package metadata; run dependencies-update --yes")
    elif not renderer.get("complete"):
        errors.append("plugin-owned PDF renderer is not installed")
    elif renderer.get("update_available"):
        errors.append("plugin-owned PDF runtime updates are available; run dependencies-update --yes")
    if not search["ok"]:
        errors.append("no configured academic search engine is reachable")
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
        "academic_search": search,
        "schedule_timezone": {"requested": requested_timezone, "profile": profile_timezone},
    }


def _setup_status() -> dict:
    config = _load_config()
    config_errors = _config_diagnostics()
    personalization_errors = _personalization_errors(config) if config else []
    mail = _mail_status(check_latest=True)
    renderer = _renderer_status(check_latest=True)
    search = _search_status(config) if config else {
        "ok": False,
        "configured_sources": [],
        "ready_sources": [],
        "engines": [],
        "next_action": "configure at least one supported academic discovery engine",
    }
    unresolved = []
    if config_errors or personalization_errors:
        unresolved.append("personal_preferences")
    dependency_install = not mail["installed"] or not renderer.get("complete")
    dependency_update = bool(
        mail.get("update_available")
        or mail.get("compatible") is False
        or renderer.get("integrity_ok") is False
        or renderer.get("update_available")
    )
    if dependency_install:
        unresolved.append("dependencies_install")
    elif dependency_update:
        unresolved.append("dependencies_update")
    if mail["installed"] and not mail["authenticated"]:
        unresolved.append("agently_login")
    if not search["ok"]:
        unresolved.append("academic_search")
    return {
        "ok": not unresolved,
        "configured": bool(config) and not config_errors,
        "unresolved": unresolved,
        "mail": mail,
        "runtime": renderer,
        "academic_search": search,
        "next_action": (
            "ask the user for research topics, recipient email, preferred form of address, Hermes sign-off, schedule/timezone and optional model preferences"
            if "personal_preferences" in unresolved else
            "ask permission, then run dependencies-update --yes to install current Agently and PDF dependencies"
            if "dependencies_install" in unresolved else
            "ask permission, then run dependencies-update --yes and re-run doctor"
            if "dependencies_update" in unresolved else
            "run mail-login-start, present verification_url (and media_directive when present) through the current Hermes channel, then poll mail-login-status"
            if "agently_login" in unresolved else
            search["next_action"]
            if "academic_search" in unresolved else
            "run doctor, then offer a manual report test before installing the schedule"
        ),
        "privacy": "Never ask the user to paste a mail password, token, cookie, or OAuth code into chat.",
        "personalization_errors": personalization_errors,
        "personalization": {
            **_effective_personalization(config),
            "customization_recommended": any(
                value == "model_dynamic" for value in (
                    _effective_personalization(config)["recipient_salutation_source"],
                    _effective_personalization(config)["sender_signature_source"],
                )
            ),
        } if config else {},
        "config": config,
    }


def _configure(args: argparse.Namespace) -> int:
    config = _load_config()
    if not config:
        initialized = _initialize(
            args.email_to,
            args.keyword,
            getattr(args, "recipient_salutation", None),
            getattr(args, "sender_signature", None),
            emit=False,
        )
        config = _load_config()
        if initialized and not config:
            return initialized
    research = config.setdefault("research", {})
    delivery = config.setdefault("delivery", {})
    analysis = config.setdefault("analysis", {})
    schedule = config.setdefault("schedule", {})
    search = config.setdefault("search", {})
    if args.email_to:
        delivery["email_to"] = [str(value).strip() for value in args.email_to if "@" in str(value)]
    if getattr(args, "recipient_salutation", None) is not None:
        delivery["recipient_salutation"] = str(args.recipient_salutation).strip()
        delivery["letter_identity_mode"] = "model_dynamic"
    if getattr(args, "sender_signature", None) is not None:
        delivery["sender_signature"] = str(args.sender_signature).strip()
        delivery["letter_identity_mode"] = "model_dynamic"
    if args.keyword:
        research["core_keywords"] = [str(value).strip() for value in args.keyword if str(value).strip()]
    if getattr(args, "direction_term", None):
        research["direction_terms"] = [str(value).strip() for value in args.direction_term if str(value).strip()]
    relevance_requested = any((
        getattr(args, "require_all", None), getattr(args, "require_any", None),
        getattr(args, "exclude_term", None), getattr(args, "match_field", None),
        getattr(args, "minimum_any", None) is not None,
    ))
    if relevance_requested:
        relevance = research.setdefault("relevance", {})
        if args.require_all:
            relevance["all_groups"] = [
                [term.strip() for term in str(group).split("|") if term.strip()]
                for group in args.require_all if str(group).strip()
            ]
        if args.require_any:
            relevance["any_terms"] = [
                term.strip() for value in args.require_any
                for term in str(value).split("|") if term.strip()
            ]
        if args.exclude_term:
            relevance["none_terms"] = [str(value).strip() for value in args.exclude_term if str(value).strip()]
        if args.minimum_any is not None:
            relevance["minimum_any"] = max(0, args.minimum_any)
        if args.match_field:
            relevance["fields"] = list(dict.fromkeys(args.match_field))
    if getattr(args, "selection_mode", None):
        research.setdefault("relevance", {})["mode"] = args.selection_mode
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
    if getattr(args, "search_source", None):
        search["sources"] = list(dict.fromkeys(
            str(value).strip().casefold().replace("-", "_")
            for value in args.search_source
            if str(value).strip()
        ))
    if getattr(args, "semantic_scholar_api_key_env", None):
        search["semantic_scholar_api_key_env"] = str(args.semantic_scholar_api_key_env).strip()
    for arg_name, config_name in (
        ("openalex_api_key_env", "openalex_api_key_env"),
        ("core_api_key_env", "core_api_key_env"),
        ("scopus_api_key_env", "scopus_api_key_env"),
        ("scopus_insttoken_env", "scopus_insttoken_env"),
        ("google_scholar_api_key_env", "google_scholar_api_key_env"),
    ):
        value = getattr(args, arg_name, None)
        if value:
            search[config_name] = str(value).strip()
    if args.use_profile_weights is not None:
        if args.use_profile_weights:
            print(
                "Automatic profile weighting is not supported; use the explicit feedback command",
                file=sys.stderr,
            )
            return 2
        research.pop("use_profile_weights", None)
    if args.use_user_feedback is not None:
        research["use_user_feedback"] = args.use_user_feedback
    _write_config(config)
    result = _setup_status()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not _config_diagnostics() else 2


def _initialize(
    email_to: list[str],
    keywords: list[str],
    recipient_salutation: str | None = None,
    sender_signature: str | None = None,
    emit: bool = True,
) -> int:
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
            clean_salutation = str(recipient_salutation or "").strip()
            clean_signature = str(sender_signature or "").strip()
            if not clean_emails or not clean_keywords:
                if emit:
                    print(
                        "new setup requires --email-to and at least one --keyword; "
                        "salutation and sign-off are model-generated when omitted",
                        file=sys.stderr,
                    )
                return 2
            data.mkdir(parents=True, exist_ok=True)
            config = {
                "version": 2,
                "max_selected": 5,
                "research": {"core_keywords": clean_keywords, "use_user_feedback": False},
                "analysis": {"auto": True, "provider_name": "hermes", "model": "", "fallback_model": "", "timeout_seconds": 180, "max_tokens": 7000},
                "search": {
                    "sources": list(DEFAULT_SEARCH_SOURCES),
                    "semantic_scholar_api_key_env": "SEMANTIC_SCHOLAR_API_KEY",
                    "openalex_api_key_env": "OPENALEX_API_KEY",
                    "core_api_key_env": "CORE_API_KEY",
                    "scopus_api_key_env": "SCOPUS_API_KEY",
                    "scopus_insttoken_env": "SCOPUS_INSTTOKEN",
                    "google_scholar_api_key_env": "SERPAPI_API_KEY",
                },
                "delivery": {
                    "channel": "email",
                    "email_to": clean_emails,
                    "letter_identity_mode": "model_dynamic",
                },
                "schedule": {"expression": "0 2 * * 5", "timezone": _profile_timezone()},
            }
            if clean_salutation:
                config["delivery"]["recipient_salutation"] = clean_salutation
            if clean_signature:
                config["delivery"]["sender_signature"] = clean_signature
            _write_config(config)
    current_config = _load_config()
    errors = _config_diagnostics() + (_personalization_errors(current_config) if current_config else [])
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
    result = subprocess.run(
        command, text=True, encoding="utf-8", errors="replace",
        capture_output=True, check=False,
    )
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
        return _initialize(
            args.email_to,
            args.keyword,
            args.recipient_salutation,
            args.sender_signature,
        )
    if action == "setup":
        supplied = any(
            getattr(args, name, None) not in (None, [], "")
            for name in (
                "email_to", "recipient_salutation", "sender_signature", "keyword", "direction_term", "require_all", "require_any",
                "exclude_term", "minimum_any", "match_field", "selection_mode", "max_selected", "timezone", "schedule", "provider",
                "model", "fallback_model", "use_profile_weights", "use_user_feedback",
                "search_source", "semantic_scholar_api_key_env",
                "openalex_api_key_env", "core_api_key_env", "scopus_api_key_env", "scopus_insttoken_env",
                "google_scholar_api_key_env",
            )
        )
        if supplied:
            return _configure(args)
        print(json.dumps(_setup_status(), ensure_ascii=False, indent=2))
        return 0
    if action == "feedback":
        return _feedback_command(args)
    if action == "doctor":
        result = _doctor_result()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 2
    if action == "runtime-install":
        return _install_runtime(args.yes)
    if action == "dependencies-status":
        result = _dependencies_status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 2
    if action == "dependencies-update":
        return _update_dependencies(args.yes)
    if action == "mail-status":
        result = _mail_status(check_latest=True)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if (
            result["installed"]
            and result["authenticated"]
            and result.get("compatible") is not False
            and not result.get("update_available")
        ) else 2
    if action == "search-status":
        result = _search_status(_load_config())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 2
    if action == "mail-install":
        return _install_mail(args.yes)
    if action in {"mail-login", "mail-login-start"}:
        code, result = _start_mail_login()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return code
    if action == "mail-login-status":
        code, result = _mail_login_status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return code
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
