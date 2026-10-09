#!/usr/bin/env python3
# HERMES_WEEKLY_E2E_RUNNER_V1
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import html
import itertools
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import textwrap
import time
import traceback
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# PDF packages live in plugin-data rather than Hermes' core environment.  The
# latter is intentionally reconciled during every Hermes upgrade.
RUNTIME_PATH_RAW = str(os.environ.get("HERMES_WEEKLY_RUNTIME_PATH") or "").strip()
RUNTIME_PATH = Path(RUNTIME_PATH_RAW).expanduser() if RUNTIME_PATH_RAW else None
if RUNTIME_PATH is not None and RUNTIME_PATH.is_dir() and str(RUNTIME_PATH) not in sys.path:
    sys.path.insert(0, str(RUNTIME_PATH))

from weekly_analysis_engine import (
    analyze_papers_resilient,
    incomplete_analysis_ids,
    select_papers_semantically,
)

MARKER = "HERMES_WEEKLY_E2E_RUNNER_V1"
HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
DEFAULT_DATA_DIR = HERMES_HOME / "plugin-data" / "hermes-weekly-briefing"
DATA_DIR = Path(os.environ.get("HERMES_WEEKLY_DATA_DIR", str(DEFAULT_DATA_DIR))).expanduser()
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = DATA_DIR / "logs"
PAPERS_DIR = DATA_DIR / "papers"
CANDIDATES_DIR = PAPERS_DIR / "candidates"
PROFILE_DIR = DATA_DIR / "profile"

ACADEMIC_DOMAINS = {
    ".edu", "arxiv.org", "doi.org", "springer.com", "elsevier.com", "ieee.org",
    "mdpi.com", "wiley.com", "nature.com", "science.org", "acm.org",
    "researchgate.net", "semanticscholar.org", "sagepub.com", "tandfonline.com",
    "frontiersin.org", "copernicus.org", "agu.org", "egu.eu",
    "neurips.cc", "openaccess.thecvf.com", "eartharxiv", "essopenarchive.org",
    "openalex.org", "dblp.org", "openreview.net", "scopus.com",
    "europepmc.org", "core.ac.uk", "hal.science", "zenodo.org", "datacite.org",
}
NON_ACADEMIC_DOMAINS = {
    "github.com", "youtube.com", "twitter.com", "linkedin.com", "medium.com",
    "reddit.com", "facebook.com", "instagram.com", "wikipedia.org",
    "stackoverflow.com", "stackexchange.com", "quora.com", "substack.com",
}

# Candidates published after the current year are pipeline artefacts (Crossref
# "sort=published&order=desc" serves future-dated records) and must never be selected.
FRESH_WINDOW_DAYS = 180
DEFAULT_SEARCH_SOURCES = [
    "openalex", "semantic_scholar", "crossref", "arxiv", "dblp", "openreview",
    "europe_pmc", "core", "hal", "zenodo", "datacite",
]
DEFAULT_RECIPIENT_SALUTATION = "你好"
DEFAULT_SENDER_SIGNATURE = "Hermes"


def effective_email_delivery(config: dict[str, Any]) -> dict[str, Any]:
    """Resolve explicit, legacy-explicit, then portable default letter identity."""
    def usable(value: Any) -> str:
        text = str(value or "").strip()
        return "" if "$" in text else text

    delivery = dict(config.get("delivery")) if isinstance(config.get("delivery"), dict) else {}
    user = config.get("user") if isinstance(config.get("user"), dict) else {}
    style = config.get("style") if isinstance(config.get("style"), dict) else {}
    if not usable(delivery.get("recipient_salutation")):
        delivery["recipient_salutation"] = (
            usable(user.get("display_name")) or DEFAULT_RECIPIENT_SALUTATION
        )
    if not usable(delivery.get("sender_signature")):
        delivery["sender_signature"] = (
            usable(style.get("signature")) or DEFAULT_SENDER_SIGNATURE
        )
    return delivery


def trusted_ssl_context() -> ssl.SSLContext:
    """Use a portable CA bundle when the active Python has no system CA file."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def direction_terms(config: dict[str, Any]) -> tuple[str, ...]:
    research = config.get("research") if isinstance(config.get("research"), dict) else {}
    configured = research.get("direction_terms")
    if isinstance(configured, list):
        cleaned = tuple(str(t).strip().lower() for t in configured if str(t).strip())
        if cleaned:
            return cleaned
    derived = []
    for field in ("core_keywords", "cross_domain_interests"):
        values = research.get(field) if isinstance(research.get(field), list) else []
        derived.extend(str(value).strip().lower() for value in values if str(value).strip())
    return tuple(dict.fromkeys(derived))


def relevance_policy(config: dict[str, Any]) -> dict[str, Any]:
    """Return normalized research concepts and any explicit strict policy.

    Concepts are semantic profile and retrieval hints by default. They become
    deterministic admission rules only when a user explicitly chooses
    ``mode=strict``. Hard exclusions remain hard because they are explicit user
    intent rather than an inferred topical judgment.
    """
    research = config.get("research") if isinstance(config.get("research"), dict) else {}
    raw = research.get("relevance") if isinstance(research.get("relevance"), dict) else None
    if raw is None:
        terms = list(direction_terms(config))
        return {
            "all_groups": [], "any_terms": terms, "minimum_any": 1 if terms else 0,
            "none_terms": [], "fields": ["title"], "legacy": True, "mode": "semantic",
        }

    groups: list[list[str]] = []
    for value in raw.get("all_groups") or []:
        values = value if isinstance(value, list) else [value]
        group = list(dict.fromkeys(
            str(term).strip() for term in values if str(term).strip()
        ))
        if group:
            groups.append(group)
    any_terms = list(dict.fromkeys(
        str(term).strip() for term in (raw.get("any_terms") or []) if str(term).strip()
    ))
    none_terms = list(dict.fromkeys(
        str(term).strip() for term in (raw.get("none_terms") or []) if str(term).strip()
    ))
    allowed_fields = {"title", "abstract", "keywords", "venue"}
    fields = [
        str(field).strip().casefold() for field in (raw.get("fields") or ["title", "abstract", "keywords"])
        if str(field).strip().casefold() in allowed_fields
    ] or ["title", "abstract", "keywords"]
    try:
        minimum_any = int(raw.get("minimum_any", 1 if any_terms else 0))
    except (TypeError, ValueError):
        minimum_any = 1 if any_terms else 0
    return {
        "all_groups": groups,
        "any_terms": any_terms,
        "minimum_any": max(0, min(len(any_terms), minimum_any)),
        "none_terms": none_terms,
        "fields": list(dict.fromkeys(fields)),
        "concept_scope": str(raw.get("concept_scope") or "same_segment").strip().casefold(),
        "mode": "strict" if str(raw.get("mode") or "semantic").strip().casefold() == "strict" else "semantic",
        "legacy": False,
    }


def _match_text(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9\u4e00-\u9fff]+", str(value or "").casefold()))


def _term_matches(text: str, term: str) -> bool:
    normalized = _match_text(term)
    if not normalized:
        return False
    # Punctuation and hyphen variants normalize to spaces, but word boundaries
    # remain intact ("flow" cannot accidentally match "workflow").
    return f" {normalized} " in f" {text} "


def _candidate_segments(candidate: dict[str, Any], fields: list[str]) -> list[str]:
    segments: list[str] = []
    for field in fields:
        value = candidate.get(field)
        values = value if isinstance(value, list) else [value]
        for item in values:
            raw = str(item or "").strip()
            if not raw:
                continue
            if field == "abstract":
                # A same-sentence/paragraph relation is stronger than unrelated
                # terms appearing somewhere in a long abstract.
                parts = re.split(r"(?<=[.!?。！？])\s+|\n+", raw)
                segments.extend(_match_text(part) for part in parts if _match_text(part))
            else:
                normalized = _match_text(raw)
                if normalized:
                    segments.append(normalized)
    return segments


def metadata_integrity_verdict(candidate: dict[str, Any]) -> tuple[bool, str]:
    """Reject untrusted repository metadata that is not safe paper evidence.

    Academic metadata is external data, never instructions. The gate is source
    neutral: it bounds abstract size, code density, repeated payloads, and text
    that explicitly addresses automated agents with control instructions.
    """
    abstract = str(candidate.get("abstract") or "")
    if len(abstract) > 12000:
        return False, "metadata_oversized"
    folded = abstract.casefold()
    code_tokens = sum(folded.count(token) for token in (
        " import ", " def ", " class ", "if __name__", "```", "<meta ",
        "async def ", "response.headers", "system instruction",
    ))
    if code_tokens >= 5:
        return False, "metadata_code_payload"
    agent_terms = any(term in folded for term in (
        "language model", "llm", "ai agent", "crawler", "transformer",
    ))
    control_terms = any(term in folded for term in (
        "ignore previous", "system override", "must forcibly", "execute absolute",
        "overwrite weights", "inject payload", "hidden dom", "prompt injection",
    ))
    if agent_terms and control_terms:
        return False, "metadata_instruction_payload"
    compact = re.sub(r"\s+", " ", folded).strip()
    if len(compact) > 2000:
        blocks = [compact[index:index + 240] for index in range(0, len(compact) - 239, 240)]
        if blocks and len(set(blocks)) < len(blocks) * 0.65:
            return False, "metadata_repetition_payload"
    return True, "metadata_integrity_ok"


def _published_date(c: dict[str, Any]) -> dt.date | None:
    raw = str(c.get("published") or "").strip()
    if not raw:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.match(r"(\d{4})", raw)
    if m:
        try:
            return dt.date(int(m.group(1)), 1, 1)
        except ValueError:
            return None
    return None


def direction_verdict(c: dict[str, Any], policy: Any) -> tuple[bool, str]:
    """Apply only objective and explicitly requested deterministic gates."""
    if not isinstance(policy, dict):
        terms = [str(term) for term in (policy or ())]
        policy = {
            "all_groups": [], "any_terms": terms, "minimum_any": 1 if terms else 0,
            "none_terms": [], "fields": ["title"], "legacy": True, "mode": "semantic",
        }
    parts = []
    for field in policy.get("fields") or ["title"]:
        value = c.get(field)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value or ""))
    text = _match_text(" ".join(parts))
    excluded = [term for term in policy.get("none_terms") or [] if _term_matches(text, term)]
    if excluded:
        return False, "excluded:" + excluded[0]
    published = _published_date(c)
    if published and published.year > dt.date.today().year:
        return False, "future_dated:" + published.isoformat()
    if policy.get("mode") != "strict":
        return True, "semantic_selection_pending"
    for index, group in enumerate(policy.get("all_groups") or [], start=1):
        if not any(_term_matches(text, term) for term in group):
            return False, f"missing_required_group:{index}"
    groups = policy.get("all_groups") or []
    if len(groups) > 1 and policy.get("concept_scope", "same_segment") == "same_segment":
        segments = _candidate_segments(c, policy.get("fields") or ["title"])
        if not any(
            all(any(_term_matches(segment, term) for term in group) for group in groups)
            for segment in segments
        ):
            return False, "required_concepts_not_related"
    any_terms = policy.get("any_terms") or []
    any_hits = [term for term in any_terms if _term_matches(text, term)]
    if len(any_hits) < int(policy.get("minimum_any") or 0):
        return False, f"minimum_any:{len(any_hits)}/{int(policy.get('minimum_any') or 0)}"
    return True, "on_direction_strict"


def freshness_bonus(c: dict[str, Any]) -> int:
    published = _published_date(c)
    if not published:
        return 0
    age = (dt.date.today() - published).days
    return 1 if 0 <= age <= FRESH_WINDOW_DAYS else 0

def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()

def iso_week_today() -> str:
    y, w, _ = dt.date.today().isocalendar()
    return f"{y}-W{w:02d}"

def read_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def normalize_title(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip()

def extract_doi(text: str) -> str | None:
    m = re.search(r"\b(10\.\d{4,}/[^\s\"'<>]+)", text)
    return m.group(1).rstrip(".;,") if m else None

def extract_arxiv_id(text: str) -> str | None:
    m = re.search(r"(?:arxiv\.org/abs/|arxiv:)(\d{4}\.\d{4,5}v?\d*)", text, re.IGNORECASE)
    return m.group(1) if m else None

def strip_arxiv_version(value: str) -> str:
    """Drop the arXiv revision suffix so v1/v2/v3 dedups against the base identifier.

    Without this, 2026-W39 re-selected 2609.01392v1 (already reported in W36 as
    2609.01392) and 2601.14475v1 (already reported in W29): dedup.json stored the
    unversioned key while fresh API hits carry the version, so cross-week dedup missed.
    """
    return re.sub(r"v\d+$", "", str(value or "").strip(), flags=re.IGNORECASE)


def canonical_id(c: dict[str, Any]) -> str:
    doi = (c.get("doi") or extract_doi(" ".join(str(c.get(k,"")) for k in ("title","url","desc","abstract")))) or ""
    arx = (c.get("arxiv_id") or extract_arxiv_id(" ".join(str(c.get(k,"")) for k in ("title","url","desc","abstract")))) or ""
    if doi:
        return "doi:" + doi.lower()
    if arx:
        return "arxiv:" + strip_arxiv_version(arx).lower()
    url = str(c.get("url") or "").strip().lower()
    title = re.sub(r"\s+", " ", str(c.get("title") or "")).strip().lower()
    return "url:" + url if url else "title:" + title[:120]

def candidate_from_existing(obj: dict[str, Any], source: str) -> dict[str, Any]:
    title = normalize_title(str(obj.get("title") or obj.get("name") or ""))
    url = str(obj.get("url") or obj.get("link") or "").strip()
    desc = normalize_title(str(obj.get("desc") or obj.get("abstract") or obj.get("summary") or ""))
    blob = " ".join([title, url, desc])
    return {
        "title": title,
        "url": url,
        "abstract": desc,
        "doi": obj.get("doi") or extract_doi(blob),
        "arxiv_id": obj.get("arxiv_id") or extract_arxiv_id(blob),
        "source": source,
        "published": obj.get("published") or obj.get("year") or "",
        "authors": obj.get("authors") or [],
        "raw": obj,
    }

def load_existing_candidates(week: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in sorted(CANDIDATES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    out.append(candidate_from_existing(item, "existing:" + path.name))
        elif isinstance(data, dict):
            for key in ("candidates", "selected_papers", "papers", "items", "results"):
                val = data.get(key)
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            out.append(candidate_from_existing(item, "existing:" + path.name))
    return out

def fetch_url(url: str, timeout: int = 15) -> tuple[int, str, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HermesWeeklyBriefing/1.0"})
        with urllib.request.urlopen(
            req, timeout=timeout, context=trusted_ssl_context()
        ) as r:
            ct = r.headers.get_content_type()
            return r.status, ct, r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, "", str(e)

def arxiv_search(queries: list[str], max_each: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for q in queries:
        # arXiv treats all:"multi word phrase" as an exact phrase, which returns 0 hits for
        # every multi-word direction query ("quantum error correction benchmark" -> 0),
        # silently leaving only the generic config keywords and drifting the selection.
        # Use the term-wise AND form documented in references/is-paper-like-filter-failures.md.
        terms = [t for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9.\-]*", q) if len(t) > 2]
        if not terms:
            continue
        search = urllib.parse.quote(" AND ".join(f"all:{t}" for t in terms))
        url = f"https://export.arxiv.org/api/query?search_query={search}&start=0&max_results={max_each}&sortBy=submittedDate&sortOrder=descending"
        code, ctype, text = fetch_url(url, timeout=25)
        if code != 200 or "<entry>" not in text:
            continue
        entries = re.findall(r"<entry>(.*?)</entry>", text, flags=re.S)
        for e in entries:
            title = normalize_title(re.sub("<.*?>", " ", re.search(r"<title>(.*?)</title>", e, re.S).group(1) if re.search(r"<title>(.*?)</title>", e, re.S) else ""))
            summary = normalize_title(re.sub("<.*?>", " ", re.search(r"<summary>(.*?)</summary>", e, re.S).group(1) if re.search(r"<summary>(.*?)</summary>", e, re.S) else ""))
            idurl = normalize_title(re.sub("<.*?>", " ", re.search(r"<id>(.*?)</id>", e, re.S).group(1) if re.search(r"<id>(.*?)</id>", e, re.S) else ""))
            published = normalize_title(re.sub("<.*?>", " ", re.search(r"<published>(.*?)</published>", e, re.S).group(1) if re.search(r"<published>(.*?)</published>", e, re.S) else ""))
            authors = [normalize_title(re.sub("<.*?>", " ", a)) for a in re.findall(r"<author>(.*?)</author>", e, flags=re.S)]
            out.append({
                "title": title,
                "url": idurl,
                "abstract": summary,
                "arxiv_id": extract_arxiv_id(idurl),
                "source": "arxiv_api",
                "published": published,
                "authors": authors,
            })
    return out

def crossref_search(queries: list[str], max_each: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    from_date = (dt.date.today() - dt.timedelta(days=730)).isoformat()
    for q in queries:
        encoded = urllib.parse.quote(q)
        url = (
            f"https://api.crossref.org/works?query.title={encoded}&rows={max_each}"
            f"&filter=type:journal-article,from-pub-date:{from_date}"
        )
        code, ctype, text = fetch_url(url, timeout=25)
        if code != 200:
            continue
        try:
            data = json.loads(text)
        except Exception:
            continue
        for item in data.get("message", {}).get("items", []):
            title = normalize_title(str(item.get("title", [""])[0] if item.get("title") else ""))
            doi = item.get("DOI", "")
            url_link = f"https://doi.org/{doi}" if doi else ""
            abstract = normalize_title(str(item.get("abstract") or ""))
            authors = []
            for a in item.get("author", [])[:5]:
                family = a.get("family", "")
                given = a.get("given", "")
                if family or given:
                    authors.append(f"{given} {family}".strip())
            published = ""
            dp = item.get("published-print", {}) or item.get("published-online", {}) or item.get("created", {})
            if isinstance(dp, dict):
                parts = dp.get("date-parts", [[None]])[0]
                if parts and parts[0]:
                    published = str(parts[0])
            out.append({
                "title": title,
                "url": url_link,
                "abstract": abstract,
                "doi": doi,
                "source": "crossref_api",
                "published": published,
                "authors": authors,
            })
    return out

def semantic_scholar_search(queries: list[str], max_each: int = 5, api_key_env: str = "SEMANTIC_SCHOLAR_API_KEY") -> list[dict[str, Any]]:
    """Search Semantic Scholar without owning credentials.

    The optional API key remains in Hermes/the host environment; the plugin only
    selects the environment-variable name from its configuration.
    """
    out: list[dict[str, Any]] = []
    headers = {"User-Agent": "hermes-weekly-briefing/4"}
    api_key = str(os.environ.get(api_key_env) or "").strip()
    if api_key:
        headers["x-api-key"] = api_key
    consecutive_failures = 0
    for query in queries:
        params = urllib.parse.urlencode({
            "query": query,
            "limit": max_each,
            "fields": "title,abstract,authors,year,publicationDate,url,externalIds",
        })
        req = urllib.request.Request(
            "https://api.semanticscholar.org/graph/v1/paper/search?" + params,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(
                req, timeout=25, context=trusted_ssl_context()
            ) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception:
            consecutive_failures += 1
            if consecutive_failures >= 2:
                break
            continue
        consecutive_failures = 0
        for item in payload.get("data") or []:
            if not isinstance(item, dict):
                continue
            external = item.get("externalIds") if isinstance(item.get("externalIds"), dict) else {}
            authors = [
                str(author.get("name") or "").strip()
                for author in item.get("authors") or []
                if isinstance(author, dict) and str(author.get("name") or "").strip()
            ]
            out.append({
                "title": str(item.get("title") or "").strip(),
                "abstract": str(item.get("abstract") or "").strip(),
                "url": str(item.get("url") or "").strip(),
                "doi": str(external.get("DOI") or "").strip(),
                "arxiv_id": str(external.get("ArXiv") or "").strip(),
                "published": str(item.get("publicationDate") or item.get("year") or "").strip(),
                "authors": authors,
                "source": "semantic_scholar_api",
            })
    return out


def _openalex_abstract(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for token, indexes in value.items():
        if not isinstance(indexes, list):
            continue
        positions.extend((int(index), str(token)) for index in indexes if str(index).isdigit())
    return normalize_title(" ".join(token for _index, token in sorted(positions)))


def openalex_search(
    queries: list[str], max_each: int = 5, api_key_env: str = "OPENALEX_API_KEY"
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    headers = {"User-Agent": "hermes-weekly-briefing/4.6"}
    api_key = str(os.environ.get(api_key_env) or "").strip()
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    for query in queries:
        params = urllib.parse.urlencode({
            "search": query,
            "per_page": max_each,
            "filter": f"from_publication_date:{(dt.date.today() - dt.timedelta(days=730)).isoformat()}",
            "select": "id,doi,display_name,publication_date,authorships,abstract_inverted_index,primary_location,type",
        })
        req = urllib.request.Request("https://api.openalex.org/works?" + params, headers=headers)
        try:
            with urllib.request.urlopen(
                req, timeout=25, context=trusted_ssl_context()
            ) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception:
            continue
        for item in payload.get("results") or []:
            if not isinstance(item, dict):
                continue
            raw_doi = str(item.get("doi") or "").strip()
            doi = re.sub(r"^https?://doi\.org/", "", raw_doi, flags=re.I)
            location = item.get("primary_location") if isinstance(item.get("primary_location"), dict) else {}
            landing = str(location.get("landing_page_url") or item.get("id") or "").strip()
            authors = []
            for authorship in item.get("authorships") or []:
                author = authorship.get("author") if isinstance(authorship, dict) else {}
                name = str(author.get("display_name") or "").strip() if isinstance(author, dict) else ""
                if name:
                    authors.append(name)
            out.append({
                "title": str(item.get("display_name") or "").strip(),
                "abstract": _openalex_abstract(item.get("abstract_inverted_index")),
                "url": f"https://doi.org/{doi}" if doi else landing,
                "doi": doi,
                "published": str(item.get("publication_date") or "").strip(),
                "authors": authors[:10],
                "source": "openalex_api",
                "openalex_id": str(item.get("id") or "").strip(),
            })
    return out


def dblp_search(queries: list[str], max_each: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    consecutive_failures = 0
    for query in queries:
        params = urllib.parse.urlencode({"q": query, "h": max_each, "format": "json"})
        code, _ctype, text = fetch_url("https://dblp.org/search/publ/api?" + params, timeout=25)
        if code != 200:
            consecutive_failures += 1
            if consecutive_failures >= 2:
                break
            continue
        consecutive_failures = 0
        try:
            hits = json.loads(text).get("result", {}).get("hits", {}).get("hit", [])
        except Exception:
            continue
        for hit in hits if isinstance(hits, list) else []:
            info = hit.get("info") if isinstance(hit, dict) else {}
            if not isinstance(info, dict):
                continue
            raw_authors = (info.get("authors") or {}).get("author", []) if isinstance(info.get("authors"), dict) else []
            if isinstance(raw_authors, (str, dict)):
                raw_authors = [raw_authors]
            authors = [
                str(author.get("text") or "").strip() if isinstance(author, dict) else str(author).strip()
                for author in raw_authors
            ]
            ee = info.get("ee")
            if isinstance(ee, list):
                ee = next((value for value in ee if str(value).startswith("http")), "")
            url = str(ee or info.get("url") or "").strip()
            out.append({
                "title": normalize_title(str(info.get("title") or "")),
                "abstract": "",
                "url": url,
                "doi": extract_doi(url) or "",
                "published": str(info.get("year") or "").strip(),
                "authors": [name for name in authors if name][:10],
                "venue": str(info.get("venue") or "").strip(),
                "source": "dblp_api",
            })
    return out


def openreview_search(queries: list[str], max_each: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for query in queries:
        params = urllib.parse.urlencode({
            "term": query, "content": "all", "source": "forum",
            "sort": "tmdate:desc", "limit": max_each,
        })
        code, _ctype, text = fetch_url("https://api2.openreview.net/notes/search?" + params, timeout=25)
        if code != 200:
            continue
        try:
            notes = json.loads(text).get("notes") or []
        except Exception:
            continue
        for note in notes:
            if not isinstance(note, dict):
                continue
            content = note.get("content") if isinstance(note.get("content"), dict) else {}
            def value(name: str) -> Any:
                raw = content.get(name)
                return raw.get("value") if isinstance(raw, dict) and "value" in raw else raw
            authors = value("authors") or []
            if isinstance(authors, str):
                authors = [authors]
            note_id = str(note.get("forum") or note.get("id") or "").strip()
            out.append({
                "title": normalize_title(str(value("title") or "")),
                "abstract": normalize_title(str(value("abstract") or value("TL;DR") or "")),
                "url": f"https://openreview.net/forum?id={urllib.parse.quote(note_id)}" if note_id else "",
                "published": dt.datetime.fromtimestamp(float(note.get("cdate") or note.get("pdate") or 0) / 1000, tz=dt.timezone.utc).date().isoformat() if (note.get("cdate") or note.get("pdate")) else "",
                "authors": [str(name).strip() for name in authors if str(name).strip()][:10],
                "venue": str(value("venue") or value("venueid") or "").strip(),
                "source": "openreview_api",
                "openreview_id": note_id,
            })
    return out


def europe_pmc_search(queries: list[str], max_each: int = 5) -> list[dict[str, Any]]:
    """Search the official Europe PMC API for life-science papers and preprints."""
    out: list[dict[str, Any]] = []
    for query in queries:
        params = urllib.parse.urlencode({
            "query": f"({query}) sort_date:y", "format": "json",
            "resultType": "core", "pageSize": max_each,
        })
        code, _ctype, text = fetch_url(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + params,
            timeout=25,
        )
        if code != 200:
            continue
        try:
            records = json.loads(text).get("resultList", {}).get("result", [])
        except Exception:
            continue
        for item in records if isinstance(records, list) else []:
            if not isinstance(item, dict):
                continue
            author_list = item.get("authorList") if isinstance(item.get("authorList"), dict) else {}
            authors = [
                str(author.get("fullName") or author.get("lastName") or "").strip()
                for author in author_list.get("author") or [] if isinstance(author, dict)
            ]
            doi = str(item.get("doi") or "").strip()
            pmcid = str(item.get("pmcid") or "").strip()
            ext_id = str(item.get("id") or "").strip()
            out.append({
                "title": normalize_title(str(item.get("title") or "")),
                "abstract": normalize_title(str(item.get("abstractText") or "")),
                "url": f"https://doi.org/{doi}" if doi else (
                    f"https://europepmc.org/article/PMC/{pmcid}" if pmcid else
                    (f"https://europepmc.org/article/MED/{ext_id}" if ext_id else "")
                ),
                "doi": doi,
                "published": str(item.get("firstPublicationDate") or item.get("pubYear") or "").strip(),
                "authors": [name for name in authors if name][:10],
                "venue": str(item.get("journalTitle") or "").strip(),
                "keywords": item.get("keywordList", {}).get("keyword", []) if isinstance(item.get("keywordList"), dict) else [],
                "source": "europe_pmc_api",
            })
    return out


def core_search(
    queries: list[str], max_each: int = 5, api_key_env: str = "CORE_API_KEY",
) -> list[dict[str, Any]]:
    """Search CORE's official open-access corpus; a key improves availability."""
    out: list[dict[str, Any]] = []
    headers = {"User-Agent": "hermes-weekly-briefing/4.8"}
    api_key = str(os.environ.get(api_key_env) or "").strip()
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    for query in queries:
        params = urllib.parse.urlencode({"q": query, "limit": max_each})
        req = urllib.request.Request(
            "https://api.core.ac.uk/v3/search/works?" + params, headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=25, context=trusted_ssl_context()) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception:
            continue
        records = payload.get("results") if isinstance(payload, dict) else []
        for item in records if isinstance(records, list) else []:
            if not isinstance(item, dict):
                continue
            authors = []
            for author in item.get("authors") or []:
                name = str(author.get("name") or "").strip() if isinstance(author, dict) else str(author).strip()
                if name:
                    authors.append(name)
            doi = str(item.get("doi") or "").removeprefix("https://doi.org/").strip()
            links = item.get("sourceFulltextUrls") if isinstance(item.get("sourceFulltextUrls"), list) else []
            out.append({
                "title": normalize_title(str(item.get("title") or "")),
                "abstract": normalize_title(str(item.get("abstract") or "")),
                "url": f"https://doi.org/{doi}" if doi else str(item.get("downloadUrl") or (links[0] if links else "")).strip(),
                "doi": doi,
                "published": str(item.get("publishedDate") or item.get("yearPublished") or "").strip(),
                "authors": authors[:10],
                "venue": str(item.get("publisher") or "").strip(),
                "source": "core_api",
            })
    return out


def hal_search(queries: list[str], max_each: int = 5) -> list[dict[str, Any]]:
    """Search the official HAL Solr API across its multidisciplinary archive."""
    out: list[dict[str, Any]] = []
    fields = "title_s,abstract_s,doiId_s,uri_s,authFullName_s,producedDate_tdate,journalTitle_s,keyword_s"
    for query in queries:
        params = urllib.parse.urlencode({
            "q": query, "wt": "json", "rows": max_each, "fl": fields,
            "sort": "producedDate_tdate desc",
        })
        code, _ctype, text = fetch_url("https://api.hal.science/search/?" + params, timeout=25)
        if code != 200:
            continue
        try:
            docs = json.loads(text).get("response", {}).get("docs", [])
        except Exception:
            continue
        for item in docs if isinstance(docs, list) else []:
            if not isinstance(item, dict):
                continue
            title_value = item.get("title_s") or ""
            abstract_value = item.get("abstract_s") or ""
            title = title_value[0] if isinstance(title_value, list) and title_value else title_value
            abstract = abstract_value[0] if isinstance(abstract_value, list) and abstract_value else abstract_value
            doi = str(item.get("doiId_s") or "").strip()
            out.append({
                "title": normalize_title(str(title or "")),
                "abstract": normalize_title(str(abstract or "")),
                "url": f"https://doi.org/{doi}" if doi else str(item.get("uri_s") or "").strip(),
                "doi": doi,
                "published": str(item.get("producedDate_tdate") or "").strip(),
                "authors": [str(name).strip() for name in item.get("authFullName_s") or [] if str(name).strip()][:10],
                "venue": str(item.get("journalTitle_s") or "").strip(),
                "keywords": item.get("keyword_s") or [],
                "source": "hal_api",
            })
    return out


def zenodo_search(queries: list[str], max_each: int = 5) -> list[dict[str, Any]]:
    """Search Zenodo's official records API for papers and preprints."""
    out: list[dict[str, Any]] = []
    for query in queries[:4]:  # documented search endpoint limit is 30/minute
        params = urllib.parse.urlencode({
            "q": query, "size": max_each, "sort": "mostrecent",
            "type": "publication",
        })
        code, _ctype, text = fetch_url("https://zenodo.org/api/records?" + params, timeout=25)
        if code != 200:
            continue
        try:
            hits = json.loads(text).get("hits", {}).get("hits", [])
        except Exception:
            continue
        for item in hits if isinstance(hits, list) else []:
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            creators = metadata.get("creators") if isinstance(metadata.get("creators"), list) else []
            doi = str(metadata.get("doi") or item.get("doi") or "").strip()
            out.append({
                "title": normalize_title(str(metadata.get("title") or "")),
                "abstract": normalize_title(re.sub(r"<[^>]+>", " ", str(metadata.get("description") or ""))),
                "url": f"https://doi.org/{doi}" if doi else str((item.get("links") or {}).get("html") or "").strip(),
                "doi": doi,
                "published": str(metadata.get("publication_date") or item.get("created") or "").strip(),
                "authors": [str(author.get("name") or "").strip() for author in creators if isinstance(author, dict) and author.get("name")][:10],
                "keywords": metadata.get("keywords") or [],
                "source": "zenodo_api",
            })
    return out


def datacite_search(queries: list[str], max_each: int = 5) -> list[dict[str, Any]]:
    """Search DataCite's public REST API for article/preprint DOI records."""
    out: list[dict[str, Any]] = []
    for query in queries:
        params = urllib.parse.urlencode({
            "query": query, "page[size]": max_each,
            "resource-type-id": "text", "sort": "published:desc",
        })
        code, _ctype, text = fetch_url("https://api.datacite.org/dois?" + params, timeout=25)
        if code != 200:
            continue
        try:
            records = json.loads(text).get("data", [])
        except Exception:
            continue
        for record in records if isinstance(records, list) else []:
            attrs = record.get("attributes") if isinstance(record, dict) and isinstance(record.get("attributes"), dict) else {}
            types = attrs.get("types") if isinstance(attrs.get("types"), dict) else {}
            scholarly_type = str(types.get("bibtex") or types.get("citeproc") or "").strip().casefold()
            if scholarly_type and scholarly_type not in {
                "article", "inproceedings", "proceedings-article", "phdthesis",
                "mastersthesis", "dissertation", "posted-content",
            }:
                continue
            titles = attrs.get("titles") if isinstance(attrs.get("titles"), list) else []
            descriptions = attrs.get("descriptions") if isinstance(attrs.get("descriptions"), list) else []
            creators = attrs.get("creators") if isinstance(attrs.get("creators"), list) else []
            doi = str(attrs.get("doi") or record.get("id") or "").strip()
            out.append({
                "title": normalize_title(str((titles[0] if titles else {}).get("title") or "")),
                "abstract": normalize_title(str((descriptions[0] if descriptions else {}).get("description") or "")),
                "url": str(attrs.get("url") or (f"https://doi.org/{doi}" if doi else "")).strip(),
                "doi": doi,
                "published": str(attrs.get("published") or attrs.get("publicationYear") or "").strip(),
                "authors": [str(author.get("name") or "").strip() for author in creators if isinstance(author, dict) and author.get("name")][:10],
                "venue": str(attrs.get("publisher") or "").strip(),
                "work_type": scholarly_type,
                "keywords": [str(subject.get("subject") or "").strip() for subject in attrs.get("subjects") or [] if isinstance(subject, dict)],
                "source": "datacite_api",
            })
    return out


def scopus_search(
    queries: list[str], max_each: int = 5,
    api_key_env: str = "SCOPUS_API_KEY", insttoken_env: str = "SCOPUS_INSTTOKEN",
) -> list[dict[str, Any]]:
    api_key = str(os.environ.get(api_key_env) or "").strip()
    if not api_key:
        return []
    headers = {"Accept": "application/json", "X-ELS-APIKey": api_key, "User-Agent": "hermes-weekly-briefing/4.6"}
    insttoken = str(os.environ.get(insttoken_env) or "").strip()
    if insttoken:
        headers["X-ELS-Insttoken"] = insttoken
    out: list[dict[str, Any]] = []
    for query in queries:
        query_terms = re.findall(r"[A-Za-z0-9\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff.-]+", query)
        if not query_terms:
            continue
        scopus_query = "TITLE-ABS-KEY(" + " AND ".join(query_terms) + ")"
        params = urllib.parse.urlencode({"query": scopus_query, "count": max_each, "sort": "-coverDate", "view": "STANDARD"})
        req = urllib.request.Request("https://api.elsevier.com/content/search/scopus?" + params, headers=headers)
        try:
            with urllib.request.urlopen(
                req, timeout=25, context=trusted_ssl_context()
            ) as response:
                entries = json.loads(response.read().decode("utf-8", errors="replace")).get("search-results", {}).get("entry", [])
        except Exception:
            continue
        for item in entries:
            if not isinstance(item, dict):
                continue
            doi = str(item.get("prism:doi") or "").strip()
            eid = str(item.get("eid") or item.get("dc:identifier") or "").strip()
            out.append({
                "title": normalize_title(str(item.get("dc:title") or "")),
                "abstract": normalize_title(str(item.get("dc:description") or "")),
                "url": f"https://doi.org/{doi}" if doi else (f"https://www.scopus.com/record/display.uri?eid={urllib.parse.quote(eid)}" if eid else ""),
                "doi": doi,
                "published": str(item.get("prism:coverDate") or "").strip(),
                "authors": [str(item.get("dc:creator") or "").strip()] if item.get("dc:creator") else [],
                "venue": str(item.get("prism:publicationName") or "").strip(),
                "source": "scopus_api",
                "scopus_id": eid,
            })
    return out


def google_scholar_search(
    queries: list[str], max_each: int = 5, api_key_env: str = "SERPAPI_API_KEY"
) -> list[dict[str, Any]]:
    """Search Google Scholar through an explicitly configured SerpApi account.

    Google does not expose a public official Scholar search API.  This adapter
    is therefore opt-in and never scrapes Scholar pages directly.
    """
    api_key = str(os.environ.get(api_key_env) or "").strip()
    if not api_key:
        return []
    out: list[dict[str, Any]] = []
    for query in queries:
        params = urllib.parse.urlencode({
            "engine": "google_scholar", "q": query, "num": min(20, max_each),
            "hl": "en", "scisbd": "1", "api_key": api_key,
        })
        code, _ctype, text = fetch_url("https://serpapi.com/search.json?" + params, timeout=30)
        if code != 200:
            continue
        try:
            results = json.loads(text).get("organic_results") or []
        except Exception:
            continue
        for item in results:
            if not isinstance(item, dict):
                continue
            publication = item.get("publication_info") if isinstance(item.get("publication_info"), dict) else {}
            summary = str(publication.get("summary") or "")
            year_match = re.search(r"\b(20\d{2}|19\d{2})\b", summary)
            authors = publication.get("authors") if isinstance(publication.get("authors"), list) else []
            out.append({
                "title": normalize_title(str(item.get("title") or "")),
                "abstract": normalize_title(str(item.get("snippet") or "")),
                "url": str(item.get("link") or "").strip(),
                "doi": extract_doi(str(item.get("link") or "") + " " + str(item.get("snippet") or "")) or "",
                "published": year_match.group(1) if year_match else "",
                "authors": [str(author.get("name") or "").strip() for author in authors if isinstance(author, dict) and author.get("name")],
                "source": "google_scholar_serpapi",
                "cited_by": int(((item.get("inline_links") or {}).get("cited_by") or {}).get("total") or 0),
            })
    return out

def is_paper_like(c: dict[str, Any]) -> tuple[bool, int, list[str]]:
    score = 0
    reasons = []
    title = str(c.get("title") or "")
    url = str(c.get("url") or "")
    abstract = str(c.get("abstract") or "")

    for bad in NON_ACADEMIC_DOMAINS:
        if bad in url.lower():
            reasons.append(f"non_academic_domain:{bad}")
            return False, -100, reasons

    if any(d in url.lower() for d in ACADEMIC_DOMAINS):
        score += 2
    doi = extract_doi(" ".join([title, url, abstract]))
    if doi:
        score += 3
        reasons.append("has_doi")
    if extract_arxiv_id(" ".join([title, url])):
        score += 2
        reasons.append("has_arxiv_id")
    if len(abstract) > 100:
        score += 2
        reasons.append("has_abstract")
    if len(title) < 10 or len(title) > 400:
        score -= 2
        reasons.append("bad_title_length")
    return score >= 2, score, reasons

def dedup_candidates(cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for c in cands:
        cid = canonical_id(c)
        if not cid:
            continue
        source = str(c.get("source") or "").strip()
        if cid not in merged:
            item = dict(c)
            item["discovery_sources"] = [source] if source else []
            merged[cid] = item
            continue
        item = merged[cid]
        provenance = item.setdefault("discovery_sources", [])
        if source and source not in provenance:
            provenance.append(source)
        for field in ("title", "abstract", "url", "doi", "arxiv_id", "published", "venue"):
            incoming = c.get(field)
            current = item.get(field)
            if incoming and (not current or len(str(incoming)) > len(str(current))):
                item[field] = incoming
        authors = list(dict.fromkeys([*(item.get("authors") or []), *(c.get("authors") or [])]))
        item["authors"] = authors[:20]
    return list(merged.values())

def _user_feedback_biases(config: dict[str, Any], feedback: dict[str, Any]) -> list[dict[str, Any]]:
    research_cfg = config.get("research", {}) if isinstance(config, dict) else {}
    if research_cfg.get("use_user_feedback") is not True or not isinstance(feedback, dict):
        return []
    biases = feedback.get("biases")
    if not isinstance(biases, list):
        return []
    return [
        item for item in biases
        if isinstance(item, dict)
        and str(item.get("source") or "").casefold() == "user"
        and str(item.get("topic") or item.get("keyword") or "").strip()
    ]


def feedback_score_adjustment(
    candidate: dict[str, Any], config: dict[str, Any], feedback: dict[str, Any]
) -> float:
    """Apply only explicit, user-confirmed preferences to candidate ranking."""

    text = " ".join(
        str(candidate.get(key) or "") for key in ("title", "abstract", "venue")
    ).casefold()
    adjustment = 0.0
    for item in _user_feedback_biases(config, feedback):
        topic = str(item.get("topic") or item.get("keyword") or "").strip().casefold()
        if not topic or topic not in text:
            continue
        direction = str(item.get("direction") or "").casefold()
        if direction in {"increase", "boost"}:
            adjustment += 1.0
        elif direction == "force_explore":
            adjustment += 0.5
        elif direction in {"decrease", "suppress"}:
            adjustment -= 2.0
    return max(-4.0, min(2.0, adjustment))


def build_research_profile(
    config: dict[str, Any], feedback: dict[str, Any]
) -> dict[str, Any]:
    """Build an auditable model-facing profile without inventing preferences."""
    research = config.get("research") if isinstance(config.get("research"), dict) else {}
    policy = relevance_policy(config)
    confirmed_feedback = []
    for item in _user_feedback_biases(config, feedback):
        confirmed_feedback.append({
            "topic": str(item.get("topic") or item.get("keyword") or ""),
            "direction": str(item.get("direction") or ""),
            "note": str(item.get("note") or "")[:500],
        })
    return {
        "core_topics": [str(value) for value in research.get("core_keywords") or [] if str(value).strip()],
        "methods": [str(value) for value in research.get("method_keywords") or [] if str(value).strip()],
        "cross_domain_interests": [
            str(value) for value in research.get("cross_domain_interests") or [] if str(value).strip()
        ],
        "user_search_phrases": [
            str(value) for value in research.get("search_queries") or [] if str(value).strip()
        ],
        "concept_groups": policy.get("all_groups") or [],
        "supporting_concepts": policy.get("any_terms") or [],
        "explicit_exclusions": policy.get("none_terms") or [],
        "selection_mode": policy.get("mode") or "semantic",
        "confirmed_user_feedback": confirmed_feedback,
        "interpretation": (
            "These concepts describe the user's research interests and aid retrieval. "
            "They are not literal keyword admission requirements unless selection_mode is strict."
        ),
    }


def build_queries(config: dict[str, Any], _profile: dict[str, Any], feedback: dict[str, Any]) -> list[str]:
    research_cfg = config.get("research", {}) if isinstance(config, dict) else {}
    explicit = research_cfg.get("search_queries") if isinstance(research_cfg.get("search_queries"), list) else []
    core = [str(value).strip() for value in research_cfg.get("core_keywords") or [] if str(value).strip()]
    methods = [str(value).strip() for value in research_cfg.get("method_keywords") or [] if str(value).strip()]
    cross = [str(value).strip() for value in research_cfg.get("cross_domain_interests") or [] if str(value).strip()]
    base = [*explicit, *core]
    for topic in core[:4]:
        base.extend(f"{topic} {method}" for method in methods[:2] if method.casefold() not in topic.casefold())
        base.extend(f"{topic} {interest}" for interest in cross[:1] if interest.casefold() not in topic.casefold())
    for item in _user_feedback_biases(config, feedback):
        if str(item.get("direction") or "").casefold() in {
            "increase", "force_explore", "boost",
        }:
            base.append(str(item.get("topic") or item.get("keyword") or ""))
    # Concept groups broaden retrieval. Combinations are useful query variants,
    # not evidence that every returned paper must contain their literal words.
    policy = relevance_policy(config)
    groups = [list(group)[:3] for group in policy.get("all_groups") or [] if group]
    policy_queries: list[str] = []
    if groups:
        combinations = itertools.islice(itertools.product(*groups), 8)
        any_terms = list(policy.get("any_terms") or [])
        for combo in combinations:
            joined = " ".join(combo)
            policy_queries.append(joined)
            policy_queries.extend(f"{joined} {term}" for term in any_terms[:2])
    concept_queries = [term for group in groups for term in group]
    base = [*base, *concept_queries, *policy_queries]
    cleaned = []
    for q in base:
        q = normalize_title(str(q))
        if q and q.lower() not in [x.lower() for x in cleaned]:
            cleaned.append(q)
    return cleaned[:16]

def source_url(paper: dict[str, Any]) -> str:
    if paper.get("doi"):
        return f"https://doi.org/{paper['doi']}"
    if paper.get("arxiv_id"):
        return f"https://arxiv.org/abs/{paper['arxiv_id']}"
    value = str(paper.get("url") or "").strip()
    return value if value.startswith(("https://", "http://")) else ""


def source_label(paper: dict[str, Any]) -> str:
    """Return a reader-facing provenance label, never an internal cache filename."""
    raw = str(paper.get("source") or "").strip()
    folded = raw.casefold()
    if paper.get("arxiv_id") or "arxiv" in folded:
        return "arXiv"
    if "openalex" in folded:
        return "OpenAlex"
    if "semantic" in folded:
        return "Semantic Scholar"
    if "dblp" in folded:
        return "DBLP"
    if "openreview" in folded:
        return "OpenReview"
    if "scopus" in folded:
        return "Scopus"
    if "google_scholar" in folded:
        return "Google Scholar"
    if "crossref" in folded:
        return "Crossref"
    if "europe_pmc" in folded:
        return "Europe PMC"
    if "core_api" in folded:
        return "CORE"
    if "hal_api" in folded:
        return "HAL"
    if "zenodo" in folded:
        return "Zenodo"
    if "datacite" in folded:
        return "DataCite"
    if paper.get("doi"):
        return "DOI"
    if raw.startswith("http://") or raw.startswith("https://"):
        return "公开学术来源"
    if not raw or raw.startswith("existing:") or raw.endswith(".json"):
        return "历史学术候选库"
    return raw.replace("_", " ")


def select_source_diverse(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Prefer source breadth among similarly strong papers, without source quotas."""
    remaining = list(candidates)
    selected: list[dict[str, Any]] = []
    covered: set[str] = set()
    while remaining and len(selected) < max(1, limit):
        best_score = float(remaining[0].get("filter_score") or 0)
        near_top = [paper for paper in remaining if float(paper.get("filter_score") or 0) >= best_score - 1.0]
        paper = max(
            near_top,
            key=lambda item: (
                len(set(item.get("discovery_sources") or [item.get("source")]) - covered),
                len(item.get("discovery_sources") or []),
                float(item.get("filter_score") or 0),
                _published_date(item) or dt.date.min,
                len(str(item.get("abstract") or "")),
            ),
        )
        selected.append(paper)
        covered.update(str(value) for value in (paper.get("discovery_sources") or [paper.get("source")]) if value)
        remaining.remove(paper)
    return selected


def _strip_markup(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _paper_doi(paper: dict[str, Any]) -> str:
    doi = str(paper.get("doi") or "").strip()
    if not doi:
        doi = extract_doi(
            " ".join(str(paper.get(key) or "") for key in ("title", "url", "desc"))
        ) or ""
    return re.sub(r"^https?://doi\.org/", "", doi, flags=re.I).strip()


def recover_abstract(paper: dict[str, Any], timeout: int = 20) -> str:
    """Recover evidence text through identifiers, without inventing content."""
    doi = _paper_doi(paper)
    if doi:
        encoded = urllib.parse.quote(doi)
        lookups = (
            (
                f"https://api.openalex.org/works/doi:{encoded}",
                lambda payload: _openalex_abstract(payload.get("abstract_inverted_index")),
            ),
            (
                f"https://api.crossref.org/works/{encoded}",
                lambda payload: _strip_markup((payload.get("message") or {}).get("abstract")),
            ),
        )
        for url, extract in lookups:
            try:
                code, _ctype, text = fetch_url(url, timeout=timeout)
                if code != 200:
                    continue
                recovered = normalize_title(str(extract(json.loads(text)) or ""))
            except Exception:
                continue
            if len(recovered) >= 80:
                return recovered
    arxiv_id = str(paper.get("arxiv_id") or "").strip()
    if arxiv_id:
        try:
            recovered = arxiv_search([f"id:{arxiv_id}"], max_each=1)
            if recovered and len(str(recovered[0].get("abstract") or "")) >= 80:
                return str(recovered[0]["abstract"])
        except Exception:
            pass
    return ""


def prepare_evidence_pool(
    candidates: list[dict[str, Any]], limit: int, *, recover: bool = True
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """Separate publishable evidence from quarantined metadata records.

    Missing evidence is a candidate-level condition, not a report-level fatal
    exception.  Only a bounded selection frontier performs network recovery;
    every other candidate remains eligible as a reserve when it already has
    sufficient evidence.
    """
    frontier = max(12, max(1, int(limit)) * 4)
    stats = {"abstracts_backfilled": 0, "evidence_quarantined": 0}
    eligible: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for index, paper in enumerate(candidates):
        abstract = re.sub(r"\s+", " ", str(paper.get("abstract") or "")).strip()
        if len(abstract) < 80 and recover and index < frontier:
            abstract = recover_abstract(paper)
            if abstract:
                paper["abstract"] = abstract
                stats["abstracts_backfilled"] += 1
        reasons = []
        if not str(paper.get("title") or "").strip():
            reasons.append("missing_title")
        if len(abstract) < 80:
            reasons.append("insufficient_abstract_evidence")
        if not source_url(paper):
            reasons.append("missing_original_link")
        if reasons:
            quarantined.append({
                "id": canonical_id(paper),
                "title": str(paper.get("title") or "")[:240],
                "reasons": reasons,
            })
            continue
        eligible.append(paper)
    stats["evidence_quarantined"] = len(quarantined)
    return eligible, quarantined, stats


def paper_publishability_issues(paper: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not source_url(paper):
        issues.append("missing_original_link")
    if len(str(paper.get("abstract") or "").strip()) < 80:
        issues.append("insufficient_abstract_evidence")
    analysis = _paper_analysis(paper)
    if not all(analysis.get(key) for key in ("problem", "why_it_matters", "method_steps", "evidence", "limitations")):
        issues.append("incomplete_deep_analysis")
    team = paper.get("team_profile") if isinstance(paper.get("team_profile"), dict) else {}
    if not list(team.get("authors") or []) and not list(paper.get("authors") or []):
        issues.append("missing_author_identity")
    return issues


def sentence_excerpt(value: Any, limit: int = 900) -> str:
    """Shorten prose without exposing a broken word or half sentence."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    window = text[: limit + 1]
    sentence_ends = [m.end() for m in re.finditer(r"(?:[。！？]|[.!?](?=\s|$))", window)]
    usable = [position for position in sentence_ends if position >= int(limit * 0.55)]
    if usable:
        return window[: usable[-1]].strip()
    words = list(re.finditer(r"\s+", window))
    cut = words[-1].start() if words else limit
    return window[:cut].rstrip(" ,;:-") + "…"


def reader_prose(value: Any, limit: int = 900) -> str:
    """Normalize repository prose for direct HTML/PDF display."""
    text = str(value or "").replace("**", "").replace("__", "").replace("`", "")
    return sentence_excerpt(text, limit)


def _openalex_json(url: str, cache_path: Path) -> dict[str, Any]:
    cached = read_json(cache_path, {})
    if isinstance(cached, dict) and cached.get("cached_at") and isinstance(cached.get("payload"), dict):
        return cached["payload"]
    code, _ctype, text = fetch_url(url, timeout=25)
    if code != 200:
        return {}
    try:
        payload = json.loads(text)
    except ValueError:
        return {}
    write_json(cache_path, {"cached_at": now_iso(), "url": url, "payload": payload})
    return payload if isinstance(payload, dict) else {}


def enrich_author_teams(selected: list[dict[str, Any]]) -> None:
    cache = DATA_DIR / "cache" / "openalex"
    mailto = str(os.environ.get("OPENALEX_MAILTO") or "").strip()
    for paper in selected:
        if paper.get("doi"):
            work_url = "https://api.openalex.org/works/https://doi.org/" + urllib.parse.quote(str(paper["doi"]), safe="/")
        else:
            work_url = "https://api.openalex.org/works?search=" + urllib.parse.quote(str(paper.get("title") or "")) + "&per-page=1"
        if mailto:
            work_url += ("&" if "?" in work_url else "?") + "mailto=" + urllib.parse.quote(mailto)
        key = re.sub(r"[^a-zA-Z0-9_.-]+", "_", canonical_id(paper))[:120]
        payload = _openalex_json(work_url, cache / f"work-{key}.json")
        work = payload
        if isinstance(payload.get("results"), list):
            work = payload["results"][0] if payload["results"] else {}
        authors = []
        institutions = []
        for authorship in list(work.get("authorships") or [])[:3]:
            author = authorship.get("author") if isinstance(authorship, dict) else {}
            author_id = str((author or {}).get("id") or "")
            profile = {}
            if author_id:
                api_id = author_id.rsplit("/", 1)[-1]
                author_url = f"https://api.openalex.org/authors/{api_id}"
                if mailto:
                    author_url += "?mailto=" + urllib.parse.quote(mailto)
                profile = _openalex_json(author_url, cache / f"author-{api_id}.json")
                works_url = (
                    "https://api.openalex.org/works?filter=author.id:"
                    + urllib.parse.quote(api_id)
                    + "&sort=publication_date:desc&per-page=3&select=display_name,publication_year,doi,id"
                )
                if mailto:
                    works_url += "&mailto=" + urllib.parse.quote(mailto)
                works_payload = _openalex_json(works_url, cache / f"author-works-{api_id}.json")
            else:
                works_payload = {}
            affiliations = []
            for institution in list(authorship.get("institutions") or [])[:3]:
                name = str((institution or {}).get("display_name") or "").strip()
                if name and name not in affiliations:
                    affiliations.append(name)
                if name and name not in institutions:
                    institutions.append(name)
            topics = [str((item or {}).get("display_name") or "") for item in list(profile.get("topics") or [])[:4]]
            authors.append({
                "name": str((author or {}).get("display_name") or ""),
                "openalex": author_id,
                "affiliations": affiliations,
                "works_count": profile.get("works_count"),
                "cited_by_count": profile.get("cited_by_count"),
                "h_index": (profile.get("summary_stats") or {}).get("h_index") if isinstance(profile.get("summary_stats"), dict) else None,
                "topics": [topic for topic in topics if topic],
                "recent_works": [
                    {
                        "title": item.get("display_name"),
                        "year": item.get("publication_year"),
                        "url": item.get("doi") or item.get("id"),
                    }
                    for item in list(works_payload.get("results") or [])[:3]
                    if isinstance(item, dict)
                ],
            })
        paper["team_profile"] = {
            "authors": [author for author in authors if author.get("name")],
            "institutions": institutions,
            "work_citations": work.get("cited_by_count"),
            "work_topics": [str((item or {}).get("display_name") or "") for item in list(work.get("topics") or [])[:5]],
            "evidence_source": str(work.get("id") or ""),
        }


def _paper_analysis(paper: dict[str, Any]) -> dict[str, Any]:
    value = paper.get("analysis")
    return value if isinstance(value, dict) else {}


def attach_deep_analysis(selected: list[dict[str, Any]], analysis_payload: dict[str, Any]) -> list[str]:
    records = analysis_payload.get("papers") if isinstance(analysis_payload, dict) else None
    records = records if isinstance(records, dict) else {}
    missing = []
    for paper in selected:
        analysis = records.get(canonical_id(paper))
        if not isinstance(analysis, dict):
            analysis = records.get(str(paper.get("doi") or paper.get("arxiv_id") or ""))
        if isinstance(analysis, dict):
            paper["analysis"] = analysis
        else:
            missing.append(canonical_id(paper))
    return missing


def make_report(week: str, selected: list[dict[str, Any]], stats: dict[str, Any], outdir: Path, queries: list[str], narrative: dict[str, Any] | None = None) -> str:
    lines = []
    narrative = narrative if isinstance(narrative, dict) else {}
    lines.append(f"# 学术研究周报 {week}")
    lines.append("")
    lines.append(f"**生成时间：** {now_iso()}")
    lines.append("")
    lines.append("## 流水线统计")
    for k, v in stats.items():
        lines.append(f"- **{k}：** {v}")
    lines.append("")
    if narrative.get("discovery_note"):
        lines.append("## 发现方式说明")
        lines.append("")
        lines.append(str(narrative["discovery_note"]))
        lines.append("")
    if narrative.get("overview"):
        lines.append("## 本周总体判断")
        lines.append("")
        lines.append(str(narrative["overview"]))
        lines.append("")
    if narrative.get("editorial_rationale"):
        lines.append("## 本期选稿说明")
        lines.append("")
        lines.append(str(narrative["editorial_rationale"]))
        lines.append("")
    lines.append("## 入选论文")
    if not selected:
        lines.append("- 未入选论文。")
    for i, s in enumerate(selected, 1):
        link = source_url(s)
        title = s.get('title', '?')
        lines.append(f"### {i}. [{title}]({link})" if link else f"### {i}. {title}")
        lines.append(f"- **来源：** {source_label(s)}")
        if s.get("doi"):
            lines.append(f"- **DOI：** [{s['doi']}](https://doi.org/{s['doi']})")
        if s.get("arxiv_id"):
            lines.append(f"- **arXiv：** [{s['arxiv_id']}](https://arxiv.org/abs/{s['arxiv_id']})")
        if s.get("published"):
            lines.append(f"- **发表：** {s['published']}")
        if s.get("authors"):
            lines.append(f"- **作者：** {', '.join(s['authors'][:5])}")
        semantic = s.get("semantic_evaluation") if isinstance(s.get("semantic_evaluation"), dict) else {}
        if semantic.get("reason"):
            lines.append(f"- **入选理由：** {semantic['reason']}")
        team = s.get("team_profile") if isinstance(s.get("team_profile"), dict) else {}
        if team.get("institutions"):
            lines.append(f"- **作者团队：** {', '.join(team['institutions'][:4])}")
        if team.get("work_topics"):
            lines.append(f"- **研究路径：** {' → '.join(team['work_topics'][:4])}")
        for author in list(team.get("authors") or [])[:3]:
            metrics = []
            if author.get("works_count") is not None:
                metrics.append(f"OpenAlex 收录作品 {author['works_count']}")
            if author.get("cited_by_count") is not None:
                metrics.append(f"引用 {author['cited_by_count']}")
            if author.get("h_index") is not None:
                metrics.append(f"h-index {author['h_index']}")
            topic_text = "、".join(author.get("topics") or [])
            detail = "；".join(metrics + ([f"主要方向：{topic_text}"] if topic_text else []))
            if detail:
                author_name = str(author.get("name") or "作者")
                author_url = str(author.get("openalex") or "")
                author_label = f"[{author_name}]({author_url})" if author_url.startswith("http") else author_name
                lines.append(f"  - **{author_label}：** {detail}")
            recent = [item for item in list(author.get("recent_works") or [])[:3] if isinstance(item, dict)]
            for item in recent:
                recent_url = str(item.get("url") or "")
                recent_title = str(item.get("title") or "近期论文")
                label = f"{recent_title} ({item.get('year') or '年份未知'})"
                lines.append(f"    - [{label}]({recent_url})" if recent_url.startswith("http") else f"    - {label}")
        if s.get("abstract"):
            lines.append(f"\n{sentence_excerpt(s['abstract'], 500)}")
        analysis = _paper_analysis(s)
        if analysis.get("problem"):
            lines.append(f"\n**研究问题：** {analysis['problem']}")
        if analysis.get("why_it_matters"):
            lines.append(f"\n**为什么值得关注：** {analysis['why_it_matters']}")
        steps = analysis.get("method_steps") if isinstance(analysis.get("method_steps"), list) else []
        if steps:
            lines.append("\n**方法链：**")
            for index, step in enumerate(steps, 1):
                if isinstance(step, dict):
                    lines.append(f"{index}. **{step.get('name', '步骤')}** — {step.get('detail', '')}")
        evidence = analysis.get("evidence") if isinstance(analysis.get("evidence"), list) else []
        if evidence:
            lines.append("\n**关键证据：**")
            lines.extend(f"- {item}" for item in evidence)
        comparisons = analysis.get("comparison") if isinstance(analysis.get("comparison"), list) else []
        if comparisons:
            lines.append("\n**对比：**")
            for row in comparisons:
                if isinstance(row, dict):
                    lines.append(f"- {row.get('dimension', '维度')}：本文 {row.get('paper', '—')}；基线 {row.get('baseline', '—')}")
        limitations = analysis.get("limitations") if isinstance(analysis.get("limitations"), list) else []
        if limitations:
            lines.append("\n**局限与验证点：**")
            lines.extend(f"- {item}" for item in limitations)
        lines.append("")
    if selected:
        lines.append("## 跨论文方法与证据对比")
        lines.append("")
        lines.append("| 论文 | 研究问题 | 方法路径 | 关键证据 | 需核验点 |")
        lines.append("|---|---|---|---|---|")
        for paper in selected:
            analysis = _paper_analysis(paper)
            steps = " → ".join(str(item.get("name") or "步骤") for item in list(analysis.get("method_steps") or []) if isinstance(item, dict))
            evidence = "；".join(str(item) for item in list(analysis.get("evidence") or [])[:2])
            limitations = "；".join(str(item) for item in list(analysis.get("limitations") or [])[:2])
            values = [paper.get("title"), analysis.get("problem"), steps, evidence, limitations]
            lines.append("| " + " | ".join(str(value or "摘要未说明").replace("|", "／") for value in values) + " |")
        lines.append("")
    if narrative.get("literature_position"):
        lines.append("## 文献定位回顾")
        lines.append("")
        for item in narrative["literature_position"]:
            lines.append(f"- {item}")
        lines.append("")
    if narrative.get("cross_paper_synthesis"):
        lines.append("## 跨论文综合")
        lines.append("")
        for item in narrative["cross_paper_synthesis"]:
            lines.append(f"- {item}")
        lines.append("")
    timeline = narrative.get("submission_timeline") if isinstance(narrative.get("submission_timeline"), list) else []
    if timeline:
        lines.append("## 投稿时间线")
        lines.append("")
        lines.append("| 目标 | 时间窗 | 说明 |")
        lines.append("|---|---|---|")
        for row in timeline:
            if isinstance(row, dict):
                lines.append("| " + " | ".join(str(row.get(key) or "—").replace("|", "／") for key in ("venue", "window", "note")) + " |")
        lines.append("")
    if narrative.get("next_week"):
        lines.append("## 下周关注")
        lines.append("")
        for item in narrative["next_week"]:
            lines.append(f"- {item}")
        lines.append("")
    lines.append("## 持续关注（不会自动漂移）")
    lines.append("")
    lines.append("本节仅复述配置中的固定主题与本期检索词；报告正文不会反向改写下周主题。")
    for query in queries:
        lines.append(f"- {query}")
    lines.append("")
    lines.append("> 作者与团队指标来自 OpenAlex，表示其数据库中的收录与引用情况，不等同于主观排名。")
    return "\n".join(lines)


def make_email_brief(
    week: str,
    selected: list[dict[str, Any]],
    narrative: dict[str, Any] | None,
    delivery: dict[str, Any] | None,
) -> str:
    """Compose the reader-facing letter; never reuse the detailed report body.

    The model-authored editorial rationale and per-paper analysis supply the
    semantic content.  Runtime code owns the greeting, sign-off, length bound,
    links and the explicit hand-off to the attached detailed report.
    """
    narrative = narrative if isinstance(narrative, dict) else {}
    delivery = delivery if isinstance(delivery, dict) else {}
    salutation = str(delivery.get("recipient_salutation") or DEFAULT_RECIPIENT_SALUTATION).strip()
    signature = str(delivery.get("sender_signature") or DEFAULT_SENDER_SIGNATURE).strip()

    lines = [f"{salutation}：", "", f"这是我为你整理的 {week} 学术研究周报。"]
    rationale = sentence_excerpt(
        narrative.get("editorial_rationale") or narrative.get("overview") or "",
        760,
    )
    if rationale:
        lines.extend(["", rationale])

    if selected:
        lines.extend(["", "如果时间有限，我建议先从下面几篇开始：", ""])
        for index, paper in enumerate(selected[:3], 1):
            title = str(paper.get("title") or "未命名论文").strip()
            url = source_url(paper)
            label = f"[{title}]({url})" if url else title
            analysis = _paper_analysis(paper)
            semantic = paper.get("semantic_evaluation") if isinstance(paper.get("semantic_evaluation"), dict) else {}
            reason = sentence_excerpt(
                analysis.get("why_it_matters") or semantic.get("reason") or "",
                260,
            )
            lines.append(f"{index}. {label}")
            if reason:
                lines.append(f"   {reason}")

    prompts = narrative.get("next_week") if isinstance(narrative.get("next_week"), list) else []
    if not prompts and selected:
        prompts = list(_paper_analysis(selected[0]).get("limitations") or [])[:1]
    prompts = [sentence_excerpt(value, 260) for value in prompts[:2] if str(value).strip()]
    if prompts:
        lines.extend(["", "读完后，也许值得继续追问："])
        lines.extend(f"- {value}" for value in prompts)

    lines.extend([
        "",
        "完整的论文分析、方法链、证据对比和作者团队信息都放在附件 `report.pdf` 中。",
        "",
        "祝好，",
        signature,
    ])
    body = "\n".join(lines).strip() + "\n"
    forbidden = ("## 流水线统计", "## 入选论文", "## 跨论文方法与证据对比")
    if any(value in body for value in forbidden):
        raise RuntimeError("email brief accidentally contains detailed report sections")
    if len(body) > 5000:
        raise RuntimeError("email brief exceeds the reader-facing length contract")
    return body

def make_report_html(week: str, selected: list[dict[str, Any]], stats: dict[str, Any], queries: list[str], out: Path, narrative: dict[str, Any] | None = None) -> str:
    narrative = narrative if isinstance(narrative, dict) else {}
    def esc(value: Any) -> str:
        return html.escape("" if value is None else str(value))
    papers = []
    for index, paper in enumerate(selected, 1):
        url = source_url(paper)
        title = esc(paper.get("title") or "未命名论文")
        title_html = f'<a href="{esc(url)}">{title}</a>' if url else title
        team = paper.get("team_profile") if isinstance(paper.get("team_profile"), dict) else {}
        analysis = _paper_analysis(paper)
        author_cards = []
        for author in list(team.get("authors") or [])[:3]:
            metrics = []
            for label, key in (("作品", "works_count"), ("引用", "cited_by_count"), ("h-index", "h_index")):
                if author.get(key) is not None:
                    metrics.append(f"{label} {esc(author[key])}")
            author_url = str(author.get("openalex") or "")
            author_name = esc(author.get("name"))
            author_heading = f'<a href="{esc(author_url)}"><strong>{author_name}</strong></a>' if author_url.startswith("http") else f'<strong>{author_name}</strong>'
            recent_links = []
            for recent in list(author.get("recent_works") or [])[:2]:
                if not isinstance(recent, dict):
                    continue
                recent_url = str(recent.get("url") or "")
                recent_title = sentence_excerpt(recent.get("title") or "近期论文", 72)
                recent_label = esc(recent_title + " · " + str(recent.get("year") or "年份未知"))
                recent_links.append(f'<li><a href="{esc(recent_url)}">{recent_label}</a></li>' if recent_url.startswith("http") else f'<li>{recent_label}</li>')
            author_cards.append(
                '<div class="author">' + author_heading + '<br>'
                + esc(" · ".join(metrics)) + '<br><span>' + esc(" / ".join(list(author.get("topics") or [])[:3])) + '</span>'
                + (f'<div class="recent"><b>近期研究</b><ul>{"".join(recent_links)}</ul></div>' if recent_links else '') + '</div>'
            )
        if not author_cards:
            for author_name in list(paper.get("authors") or [])[:5]:
                if str(author_name).strip():
                    author_cards.append(
                        '<div class="author"><strong>' + esc(author_name)
                        + '</strong><br><span>论文署名作者；公开学术画像暂不可用</span></div>'
                    )
        method_steps = []
        for step_index, step in enumerate(list(analysis.get("method_steps") or []), 1):
            if isinstance(step, dict):
                method_steps.append(
                    f'<div class="method-step"><b>{step_index:02d} · {esc(step.get("name") or "步骤")}</b><span>{esc(step.get("detail"))}</span></div>'
                )
        comparison_rows = []
        for row in list(analysis.get("comparison") or []):
            if isinstance(row, dict):
                comparison_rows.append(
                    f'<tr><th>{esc(row.get("dimension"))}</th><td>{esc(row.get("paper"))}</td><td>{esc(row.get("baseline"))}</td></tr>'
                )
        evidence_items = ''.join(f'<li>{esc(item)}</li>' for item in list(analysis.get("evidence") or []))
        limitation_items = ''.join(f'<li>{esc(item)}</li>' for item in list(analysis.get("limitations") or []))
        semantic = paper.get("semantic_evaluation") if isinstance(paper.get("semantic_evaluation"), dict) else {}
        selection_html = (
            f'<div class="selection-reason"><strong>入选理由</strong><p>{esc(semantic.get("reason"))}</p></div>'
            if semantic.get("reason") else ''
        )
        analysis_html = f'''
          {selection_html}<div class="analysis"><h3>研究问题</h3><p>{esc(analysis.get("problem") or "等待深度分析")}</p>
          <h3>为什么值得关注</h3><p>{esc(analysis.get("why_it_matters") or "等待深度分析")}</p>
          <h3>方法链</h3><div class="method-tree">{''.join(method_steps) or '<div class="missing">暂无可靠方法拆解</div>'}</div>
          <h3>关键证据</h3><ul>{evidence_items or '<li>暂无可核验证据摘要</li>'}</ul>
          {('<h3>与基线对比</h3><table><thead><tr><th>维度</th><th>本文</th><th>基线</th></tr></thead><tbody>' + ''.join(comparison_rows) + '</tbody></table>') if comparison_rows else ''}
          <h3>局限与验证点</h3><ul>{limitation_items or '<li>需阅读原文后确认</li>'}</ul></div>'''
        papers.append(f'''<section class="paper">
          <div class="paper-index">{index:02d}</div><h2>{title_html}</h2>
          <div class="meta">{esc(paper.get("published"))} · {esc(source_label(paper))}</div>
          <p class="abstract">{esc(reader_prose(paper.get("abstract"), 900))}</p>
          {analysis_html}
          <div class="team"><h3>作者团队与研究路径</h3>
            <p><strong>机构：</strong>{esc("、".join(team.get("institutions") or []) or "公开来源未提供可靠机构信息")}</p>
            <p><strong>主题路径：</strong>{esc(" → ".join(team.get("work_topics") or []) or "公开来源未提供可靠主题画像")}</p>
            <div class="author-grid">{''.join(author_cards)}</div>
          </div>
          <p class="source"><a href="{esc(url)}">打开论文原文 ↗</a></p>
        </section>''')
    synthesis_rows = []
    method_cards = []
    for paper in selected:
        analysis = _paper_analysis(paper)
        steps = [str(item.get("name") or "步骤") for item in list(analysis.get("method_steps") or []) if isinstance(item, dict)]
        method_cards.append(f'<div class="synthesis-card"><b>{esc(paper.get("title"))}</b><span>{esc(" → ".join(steps) or "摘要未说明")}</span></div>')
        synthesis_rows.append(
            '<tr><th>' + esc(paper.get("title")) + '</th><td>' + esc(analysis.get("problem") or "摘要未说明")
            + '</td><td>' + esc("；".join(str(x) for x in list(analysis.get("evidence") or [])[:2]) or "摘要未说明")
            + '</td><td>' + esc("；".join(str(x) for x in list(analysis.get("limitations") or [])[:2]) or "需阅读全文核验") + '</td></tr>'
        )
    synthesis_html = (
        '<section class="synthesis"><h1>跨论文方法与证据对比</h1><div class="synthesis-grid">'
        + ''.join(method_cards) + '</div><table><thead><tr><th>论文</th><th>研究问题</th><th>关键证据</th><th>需核验点</th></tr></thead><tbody>'
        + ''.join(synthesis_rows) + '</tbody></table></section>'
    ) if selected else ''
    stat_labels = {
        "raw_candidates": "候选总数",
        "candidate_deduped": "候选去重后",
        "cross_week_deduped": "跨周去重",
        "hard_filter_passed": "客观清洗通过",
        "selected_count": "本期入选",
        "rejected_count": "筛除总数",
        "off_direction_rejected": "规则明确排除",
        "future_dated_rejected": "未来日期筛除",
        "queries": "检索式",
        "deep_analysis_count": "深度分析",
        "semantic_evaluated": "模型语义评审",
        "semantic_selected": "模型首选",
        "semantic_reserves": "模型备用",
        "semantic_evaluation_failures": "语义评审失败",
    }
    cover_stat_keys = (
        "raw_candidates", "candidate_deduped", "semantic_evaluated",
        "semantic_reserves", "selected_count", "deep_analysis_count",
    )
    stats_html = ''.join(
        f'<div class="stat" data-stat-key="{esc(k)}"><b>{esc(v)}</b><span>{esc(stat_labels.get(k, k))}</span></div>'
        for k in cover_stat_keys if (v := stats.get(k)) is not None
    )
    queries_html = ''.join(f'<li>{esc(item)}</li>' for item in queries)
    overview_html = ''
    if narrative.get("discovery_note"):
        overview_html += f'<section class="focus"><h1>发现方式说明</h1><p class="note">{esc(narrative["discovery_note"])}</p></section>'
    if narrative.get("overview"):
        overview_html += f'<section class="focus"><h1>本周总体判断</h1><p>{esc(narrative["overview"])}</p></section>'
    if narrative.get("editorial_rationale"):
        overview_html += f'<section class="focus"><h1>本期选稿说明</h1><p>{esc(narrative["editorial_rationale"])}</p></section>'
    tail_html = ''
    for key, heading in (("literature_position", "文献定位回顾"), ("cross_paper_synthesis", "跨论文综合")):
        items = narrative.get(key) if isinstance(narrative.get(key), list) else []
        if items:
            body = ''.join(f'<li>{esc(item)}</li>' for item in items)
            tail_html += f'<section class="focus"><h1>{heading}</h1><ul>{body}</ul></section>'
    timeline = narrative.get("submission_timeline") if isinstance(narrative.get("submission_timeline"), list) else []
    if timeline:
        rows = ''.join(
            '<tr><th>' + esc(row.get("venue") or "—") + '</th><td>' + esc(row.get("window") or "—")
            + '</td><td>' + esc(row.get("note") or "—") + '</td></tr>'
            for row in timeline if isinstance(row, dict)
        )
        tail_html += ('<section class="focus"><h1>投稿时间线</h1><table><thead><tr><th>目标</th><th>时间窗</th>'
                      '<th>说明</th></tr></thead><tbody>' + rows + '</tbody></table></section>')
    next_week = narrative.get("next_week") if isinstance(narrative.get("next_week"), list) else []
    if next_week:
        body = ''.join(f'<li>{esc(item)}</li>' for item in next_week)
        tail_html += f'<section class="focus"><h1>下周关注</h1><ul>{body}</ul></section>'
    document = f'''<!doctype html><html lang="zh"><head><meta charset="utf-8"><style>
      @page {{ size: A4; margin: 18mm 17mm 20mm; @bottom-right {{ content: counter(page) " / " counter(pages); color:#64748b; font-size:8pt; }} }}
      body {{ font-family: "Noto Sans CJK SC","Microsoft YaHei",sans-serif; color:#172033; font-size:10pt; line-height:1.65; }}
      a {{ color:#0969a8; text-decoration:none; }} h1 {{ font-size:25pt; margin:0 0 5mm; color:#0f2847; }}
      h2 {{ font-size:15pt; line-height:1.35; margin:0 0 2mm; }} h3 {{ font-size:10pt; color:#234b70; margin:0 0 2mm; }}
      .cover {{ min-height:235mm; display:flex; flex-direction:column; justify-content:center; page-break-after:always; }}
      .eyebrow {{ color:#0b7285; letter-spacing:2px; font-weight:700; }} .subtitle {{ color:#52657a; font-size:12pt; }}
      .stats {{ display:grid; grid-template-columns:repeat(3,1fr); gap:3mm; margin-top:12mm; }}
      .stat {{ background:#edf6f8; padding:4mm; border-radius:3mm; }} .stat b {{ display:block; font-size:18pt; color:#0b7285; }} .stat span {{ color:#52657a; font-size:8pt; }}
      h1,h2,h3 {{ break-after:avoid; page-break-after:avoid; }}
      .papers-title {{ margin-bottom:5mm; }}
      .paper {{ position:relative; break-inside:auto; page-break-inside:auto; border-top:1px solid #cbd5e1; padding:7mm 0 5mm 13mm; }}
      .paper-index {{ position:absolute; left:0; top:7mm; color:#0b7285; font-weight:800; font-size:10pt; }}
      .meta,.source {{ color:#64748b; font-size:8.5pt; }} .team {{ background:#f6f8fb; border-left:3px solid #4f86a6; padding:4mm; border-radius:1mm; }}
      .author-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:2mm; }} .author {{ background:white; padding:2.5mm; font-size:7.5pt; line-height:1.45; border:1px solid #dce4ea; border-radius:2mm; }}
      .author span {{ color:#52657a; }} .author .recent {{ margin-top:2mm; border-top:1px solid #e2e8f0; padding-top:2mm; }} .author .recent ul {{ margin:1mm 0 0; padding-left:4mm; }}
      .focus,.synthesis {{ page-break-before:always; }} .note {{ padding:4mm; background:#fff7df; border-radius:2mm; color:#66531c; }}
      .synthesis-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:3mm; margin-bottom:5mm; }} .synthesis-card {{ background:#eef5f8; border-left:3px solid #0b7285; padding:3mm; }} .synthesis-card b,.synthesis-card span {{ display:block; }} .synthesis-card span {{ color:#40566d; margin-top:1mm; }}
      .analysis {{ margin:4mm 0; }} .selection-reason {{ margin:4mm 0; padding:3mm 4mm; background:#f0f7f4; border-left:3px solid #2f855a; border-radius:1.5mm; }} .selection-reason p {{ margin:1mm 0 0; }} .method-tree {{ display:grid; gap:2mm; margin:2mm 0 4mm; }}
      .method-step {{ display:grid; grid-template-columns:42mm 1fr; gap:3mm; background:#eef5f8; border-left:3px solid #0b7285; padding:3mm; border-radius:1.5mm; }}
      .method-step span {{ color:#40566d; }} .missing {{ color:#8a5b00; background:#fff7df; padding:3mm; }}
      .team,.author-grid {{ break-inside:auto; page-break-inside:auto; }}
      .selection-reason,.method-step,.author,table,tr {{ break-inside:avoid; page-break-inside:avoid; }}
      table {{ width:100%; border-collapse:collapse; margin:2mm 0 4mm; font-size:8.5pt; }} th,td {{ border:1px solid #d5dee5; padding:2.5mm; vertical-align:top; }}
      th {{ background:#eef5f8; text-align:left; color:#234b70; }}
    </style></head><body>
      <section class="cover"><div class="eyebrow">HERMES RESEARCH BRIEFING</div><h1>学术研究周报<br>{esc(week)}</h1>
      <p class="subtitle">论文证据、作者团队与研究路径的一体化阅读稿</p><div class="stats">{stats_html}</div></section>
      {overview_html}
      <h1 class="papers-title">本期论文</h1>{''.join(papers)}{synthesis_html}{tail_html}
      <section class="focus"><h1>持续关注</h1><p class="note">本节只展示固定配置和显式用户反馈形成的检索词。本期报告不会自动改写下周主题，避免关注点自我强化和漂移。</p><ul>{queries_html}</ul>
      <p class="meta">作者与团队指标来自 OpenAlex，表示数据库收录与引用情况，不等同于主观排名。</p></section>
    </body></html>'''
    out.write_text(document, encoding="utf-8")
    return document


def validate_report_quality(selected: list[dict[str, Any]], html_text: str) -> dict[str, Any]:
    """Fail closed on editorial defects that previously reached the user's inbox."""
    errors: list[str] = []
    if not selected:
        return {"passed": True, "checks": {"selected": 0}, "errors": []}
    if "page-break-inside:avoid; border-top" in html_text:
        errors.append("paper-level keep-together pagination can create heading-only pages")
    if re.search(r"existing:[^<\s]+\.json|\b[\w-]+_arxiv_[\w.-]+\.json\b", html_text, re.I):
        errors.append("internal candidate filename leaked into reader-facing report")
    if re.search(r'<div class="stat"[^>]*><b>\s*</b>', html_text):
        errors.append("a cover statistic rendered without a value")
    for index, paper in enumerate(selected, 1):
        analysis = _paper_analysis(paper)
        if not source_url(paper):
            errors.append(f"paper {index} has no clickable original source")
        if not str(paper.get("abstract") or "").strip():
            errors.append(f"paper {index} has no abstract")
        if not all(analysis.get(key) for key in ("problem", "why_it_matters", "method_steps", "evidence", "limitations")):
            errors.append(f"paper {index} deep analysis is incomplete")
        team = paper.get("team_profile") if isinstance(paper.get("team_profile"), dict) else {}
        if not list(team.get("authors") or []) and not list(paper.get("authors") or []):
            errors.append(f"paper {index} has no author identity")
        original = source_url(paper)
        if original and html.escape(original, quote=True) not in html_text:
            errors.append(f"paper {index} original link is absent from HTML")
    receipt = {
        "passed": not errors,
        "checks": {
            "selected": len(selected),
            "clickable_originals": sum(1 for paper in selected if source_url(paper)),
            "author_identified": sum(
                1 for paper in selected
                if list((paper.get("team_profile") or {}).get("authors") or []) or list(paper.get("authors") or [])
            ),
            "pagination_policy": "flowing_papers_with_atomic_components",
            "internal_source_names_hidden": True,
        },
        "errors": errors,
    }
    if errors:
        raise RuntimeError("report quality gate failed: " + "; ".join(errors))
    return receipt


def make_pdf(html_text: str, md: str, out: Path) -> None:
    try:
        from weasyprint import HTML
        HTML(string=html_text, base_url=str(out.parent)).write_pdf(str(out))
        return
    except Exception:
        pass
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        from xml.sax.saxutils import escape

        regular_candidates = [
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/simsun.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            Path("/System/Library/Fonts/PingFang.ttc"),
        ]
        bold_candidates = [
            Path("C:/Windows/Fonts/msyhbd.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"),
        ]
        regular_path = next((path for path in regular_candidates if path.is_file()), None)
        bold_path = next((path for path in bold_candidates if path.is_file()), regular_path)
        if regular_path:
            pdfmetrics.registerFont(TTFont("HermesCJK", str(regular_path)))
            pdfmetrics.registerFont(TTFont("HermesCJK-Bold", str(bold_path)))
            font_name, bold_name = "HermesCJK", "HermesCJK-Bold"
        else:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
            font_name = bold_name = "STSong-Light"
        styles = getSampleStyleSheet()
        body = ParagraphStyle("ChineseBody", parent=styles["BodyText"], fontName=font_name, fontSize=9.5, leading=15, textColor=colors.HexColor("#172033"))
        title = ParagraphStyle("ChineseTitle", parent=body, fontName=bold_name, fontSize=22, leading=30, alignment=TA_CENTER, textColor=colors.HexColor("#0f2847"), spaceAfter=12 * mm)
        heading = ParagraphStyle("ChineseHeading", parent=body, fontName=bold_name, fontSize=14, leading=20, textColor=colors.HexColor("#0b7285"), spaceBefore=5 * mm, spaceAfter=2 * mm)
        subheading = ParagraphStyle("ChineseSubheading", parent=body, fontName=bold_name, fontSize=11, leading=16, textColor=colors.HexColor("#234b70"), spaceBefore=3 * mm, spaceAfter=1 * mm)
        note = ParagraphStyle("ChineseNote", parent=body, fontSize=8, leading=12, textColor=colors.HexColor("#64748b"))
        method = ParagraphStyle(
            "MethodCard", parent=body, fontSize=8.5, leading=13,
            backColor=colors.HexColor("#eef5f8"), borderColor=colors.HexColor("#0b7285"),
            borderWidth=0.7, borderPadding=7, spaceBefore=1.5 * mm, spaceAfter=1.5 * mm,
        )
        section_label = ParagraphStyle(
            "SectionLabel", parent=body, fontName=bold_name, fontSize=9.5,
            textColor=colors.HexColor("#234b70"), spaceBefore=2.5 * mm, spaceAfter=1 * mm,
        )
        table_cell = ParagraphStyle("TableCell", parent=body, fontSize=7, leading=9)
        table_head = ParagraphStyle("TableHead", parent=table_cell, fontName=bold_name, textColor=colors.HexColor("#234b70"))

        def inline_markup(value: str) -> str:
            placeholders: list[tuple[str, str, str]] = []
            def remember(match: re.Match[str]) -> str:
                token = f"@@LINK{len(placeholders)}@@"
                placeholders.append((token, match.group(1), match.group(2)))
                return token
            value = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", remember, value)
            value = escape(value.replace("**", "").replace("`", ""))
            for token, label, url in placeholders:
                value = value.replace(token, f'<link href="{escape(url)}" color="#0969a8">{escape(label)}</link>')
            return value

        story = []
        raw_lines = md.splitlines()
        line_index = 0
        while line_index < len(raw_lines):
            raw = raw_lines[line_index]
            line = raw.strip()
            if line.startswith("|"):
                table_lines = []
                while line_index < len(raw_lines) and raw_lines[line_index].strip().startswith("|"):
                    table_lines.append(raw_lines[line_index].strip())
                    line_index += 1
                rows = []
                for row_index, table_line in enumerate(table_lines):
                    values = [value.strip() for value in table_line.strip("|").split("|")]
                    if row_index == 1 and all(re.fullmatch(r":?-{3,}:?", value) for value in values):
                        continue
                    style = table_head if not rows else table_cell
                    rows.append([Paragraph(inline_markup(value), style) for value in values])
                if rows:
                    width = 176 * mm
                    columns = len(rows[0])
                    if columns == 5:
                        widths = [35 * mm, 36 * mm, 34 * mm, 36 * mm, 35 * mm]
                    else:
                        widths = [width / columns] * columns
                    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
                    table.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef5f8")),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d5dee5")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]))
                    story.extend([table, Spacer(1, 3 * mm)])
                continue
            if not line:
                story.append(Spacer(1, 1.5 * mm))
            elif line.startswith("# "):
                if story:
                    story.append(PageBreak())
                story.append(Paragraph(inline_markup(line[2:]), title))
            elif line.startswith("## "):
                story.append(Paragraph(inline_markup(line[3:]), heading))
            elif line.startswith("### "):
                story.append(Paragraph(inline_markup(line[4:]), subheading))
            elif line.startswith("> "):
                story.append(Paragraph(inline_markup(line[2:]), note))
            elif line.startswith("- "):
                story.append(Paragraph("• " + inline_markup(line[2:]), body))
            elif re.match(r"^\d+\.\s+\*\*", line):
                story.append(Paragraph(inline_markup(line), method))
            elif line.startswith("**") and "：**" in line:
                story.append(Paragraph(inline_markup(line), section_label))
            else:
                story.append(Paragraph(inline_markup(line), body))
            line_index += 1

        def page_number(canvas: Any, doc: Any) -> None:
            canvas.saveState()
            canvas.setFont(font_name, 7)
            canvas.setFillColor(colors.HexColor("#64748b"))
            canvas.drawRightString(A4[0] - 17 * mm, 10 * mm, str(doc.page))
            canvas.restoreState()

        document = SimpleDocTemplate(
            str(out), pagesize=A4, rightMargin=17 * mm, leftMargin=17 * mm,
            topMargin=18 * mm, bottomMargin=20 * mm,
            title="Hermes Academic Weekly Briefing",
        )
        document.build(story, onFirstPage=page_number, onLaterPages=page_number)
    except Exception as exc:
        raise RuntimeError(f"PDF generation failed: {exc}") from exc

def find_agently_cli() -> str | None:
    candidates = [
        os.environ.get("AGENTLY_CLI_PATH"),
        shutil.which("agently-cli"),
        shutil.which("agently"),
        str(Path.home() / ".local" / "bin" / "agently-cli"),
        str(Path.home() / ".local" / "bin" / "agently"),
        "/usr/local/bin/agently-cli",
        "/usr/local/bin/agently",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None

def run_cmd(cmd: list[str], timeout: int = 90, cwd: Path | None = None) -> dict[str, Any]:
    started = time.time()
    env = {
        **os.environ,
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
    }
    env.pop("HERMES_SESSION_ID", None)
    try:
        portable_cmd = cmd
        if os.name == "nt" and cmd and Path(cmd[0]).suffix.casefold() in {".cmd", ".bat"}:
            portable_cmd = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *cmd]
        p = subprocess.run(portable_cmd, text=True, capture_output=True, timeout=timeout, cwd=str(cwd) if cwd else None, env=env)
        return {"ok": p.returncode == 0, "stdout": p.stdout, "stderr": p.stderr, "returncode": p.returncode, "elapsed": round(time.time() - started, 2)}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "timeout", "returncode": -1, "elapsed": round(time.time() - started, 2)}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e), "returncode": -1, "elapsed": round(time.time() - started, 2)}

def try_send_email(to: list[str], subject: str, body_path: Path, pdf_path: Path, enabled: bool) -> dict[str, Any]:
    rec: dict[str, Any] = {"status": "prepared", "to": to, "subject": subject}
    if not to:
        rec["status"] = "no_recipients"
        return rec
    if not enabled:
        rec["status"] = "prepared"
        return rec
    cli = find_agently_cli() or ""
    rec["cli"] = cli
    if not cli:
        rec["status"] = "no_agently_cli"
        return rec
    def redacted(result: dict[str, Any]) -> dict[str, Any]:
        clean = dict(result)
        for key in ("stdout", "stderr"):
            clean[key] = re.sub(
                r"(?i)(confirmation[_\s]?token[:\s]+)[a-zA-Z0-9_-]+",
                r"\1[REDACTED]",
                str(clean.get(key) or ""),
            )
        return clean

    try:
        cwd = body_path.parent
        deliveries = []
        for address in to:
            result = run_cmd([cli, "message", "+send", "--to", address, "--subject", subject, "--body-file", body_path.name, "--attachment", pdf_path.name], timeout=60, cwd=cwd)
            item: dict[str, Any] = {"to": address, "send_result": redacted(result)}
            response_payload: dict[str, Any] = {}
            try:
                parsed = json.loads(str(result.get("stdout") or "{}"))
                response_payload = parsed if isinstance(parsed, dict) else {}
            except (TypeError, ValueError):
                pass
            response_data = response_payload.get("data") if isinstance(response_payload.get("data"), dict) else {}
            confirmation_required = response_data.get("confirmation_required") is True
            token = str(response_data.get("confirmation_token") or "").strip()
            if not token:
                combined = "\n".join((str(result.get("stdout") or ""), str(result.get("stderr") or "")))
                token_match = re.search(r"confirmation[_\s]?token[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9_-]+)", combined, flags=re.I)
                token = token_match.group(1) if token_match else ""

            # Agently deliberately returns rc=0/ok=true for a prepared message
            # that still needs confirmation.  That state is not delivery.
            if confirmation_required:
                if not token:
                    item["status"] = "confirmation_missing"
                else:
                    confirm_result = run_cmd([cli, "message", "+send", "--to", address, "--subject", subject, "--body-file", body_path.name, "--attachment", pdf_path.name, "--confirmation-token", token], timeout=60, cwd=cwd)
                    item["confirm_result"] = redacted(confirm_result)
                    confirm_payload: dict[str, Any] = {}
                    try:
                        parsed = json.loads(str(confirm_result.get("stdout") or "{}"))
                        confirm_payload = parsed if isinstance(parsed, dict) else {}
                    except (TypeError, ValueError):
                        pass
                    confirm_data = confirm_payload.get("data") if isinstance(confirm_payload.get("data"), dict) else {}
                    still_pending = confirm_data.get("confirmation_required") is True
                    item["status"] = "sent" if confirm_result.get("ok") and not still_pending else "confirm_failed"
            elif result.get("ok") and response_payload.get("ok", True) is not False:
                item["status"] = "sent"
            elif token:
                confirm_result = run_cmd([cli, "message", "+send", "--to", address, "--subject", subject, "--body-file", body_path.name, "--attachment", pdf_path.name, "--confirmation-token", token], timeout=60, cwd=cwd)
                item["confirm_result"] = redacted(confirm_result)
                item["status"] = "sent" if confirm_result.get("ok") else "confirm_failed"
            else:
                item["status"] = "send_failed"
            deliveries.append(item)
        rec["deliveries"] = deliveries
        rec["status"] = "sent" if deliveries and all(item["status"] == "sent" for item in deliveries) else "send_failed"
    except Exception as e:
        rec["status"] = "error"
        rec["error"] = str(e)
    return rec

def log_event(log_path: Path, **kw: Any) -> None:
    try:
        entry = {"ts": now_iso(), **kw}
        with log_path.open("a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def publish_attempt(attempt_dir: Path, published_dir: Path, names: list[str]) -> None:
    """Publish a complete attempt with the manifest as the commit marker."""
    published_dir.mkdir(parents=True, exist_ok=True)
    ordered = [name for name in names if name != "manifest.json"] + ["manifest.json"]
    for name in ordered:
        source = attempt_dir / name
        if not source.is_file():
            continue
        temporary = published_dir / f".{name}.publishing"
        shutil.copy2(source, temporary)
        os.replace(temporary, published_dir / name)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", default=iso_week_today())
    ap.add_argument("--email-to", action="append", default=[])
    ap.add_argument("--send-email", action="store_true")
    ap.add_argument("--max-selected", type=int, default=5)
    ap.add_argument("--discovery-only", action="store_true", help="Stop after paper selection, write selected_papers.json")
    ap.add_argument("--analysis-file", default=None, help="Deep-analysis JSON keyed by canonical paper id")
    ap.add_argument("--allow-shallow", action="store_true", help="Render without deep analysis (development only)")
    ap.add_argument("--data-dir", default=None, help=f"Override data directory (default: $HERMES_WEEKLY_DATA_DIR or {DEFAULT_DATA_DIR})")
    args = ap.parse_args()

    if args.data_dir:
        global DATA_DIR, REPORTS_DIR, LOGS_DIR, PAPERS_DIR, CANDIDATES_DIR, PROFILE_DIR
        DATA_DIR = Path(args.data_dir)
        REPORTS_DIR = DATA_DIR / "reports"
        LOGS_DIR = DATA_DIR / "logs"
        PAPERS_DIR = DATA_DIR / "papers"
        CANDIDATES_DIR = PAPERS_DIR / "candidates"
        PROFILE_DIR = DATA_DIR / "profile"

    week = args.week
    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    published_outdir = REPORTS_DIR / week
    outdir = REPORTS_DIR / ".attempts" / f"{week}-{run_id}"
    outdir.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    run_log = LOGS_DIR / f"run-{week}-{run_id}.jsonl"

    manifest: dict[str, Any] = {
        "version": 2,
        "runner": MARKER,
        "week": week,
        "mode": "deterministic_e2e",
        "generated_at": now_iso(),
        "status": "started",
        "stats": {},
        "outputs": {},
        "errors": [],
    }

    try:
        config = read_json(DATA_DIR / "config.json", {})
        delivery_settings = effective_email_delivery(config)
        os.environ.setdefault(
            "AGENTLY_WORKSPACE",
            str(delivery_settings.get("agently_workspace") or "hermes").strip(),
        )
        feedback = read_json(PROFILE_DIR / "topic_feedback.json", {})
        dedup = read_json(PAPERS_DIR / "dedup.json", {})
        archive = read_json(PAPERS_DIR / "archive.json", {})

        policy = relevance_policy(config)
        queries = build_queries(config, {}, feedback)
        log_event(run_log, type="queries", queries=queries, relevance_policy=policy)

        candidates = []
        existing = load_existing_candidates(week)
        candidates.extend(existing)
        log_event(run_log, type="existing_candidates", count=len(existing))

        search_cfg = config.get("search") if isinstance(config.get("search"), dict) else {}
        source_names = search_cfg.get("sources") if isinstance(search_cfg.get("sources"), list) else DEFAULT_SEARCH_SOURCES
        sources = {str(value).strip().casefold().replace("-", "_") for value in source_names if str(value).strip()}
        query_window = queries[:6]
        discovery_tasks: list[tuple[str, Any, tuple[Any, ...], dict[str, Any]]] = []
        if "openalex" in sources:
            discovery_tasks.append(("openalex_api_candidates", openalex_search, (query_window,), {"max_each": 6, "api_key_env": str(search_cfg.get("openalex_api_key_env") or "OPENALEX_API_KEY")}))
        if "semantic_scholar" in sources:
            discovery_tasks.append(("semantic_scholar_api_candidates", semantic_scholar_search, (query_window,), {"max_each": 6, "api_key_env": str(search_cfg.get("semantic_scholar_api_key_env") or "SEMANTIC_SCHOLAR_API_KEY")}))
        if "crossref" in sources:
            discovery_tasks.append(("crossref_api_candidates", crossref_search, (query_window,), {"max_each": 6}))
        if "arxiv" in sources:
            discovery_tasks.append(("arxiv_api_candidates", arxiv_search, (query_window,), {"max_each": 6}))
        if "dblp" in sources:
            discovery_tasks.append(("dblp_api_candidates", dblp_search, (query_window,), {"max_each": 6}))
        if "openreview" in sources:
            discovery_tasks.append(("openreview_api_candidates", openreview_search, (query_window,), {"max_each": 6}))
        if "europe_pmc" in sources:
            discovery_tasks.append(("europe_pmc_api_candidates", europe_pmc_search, (query_window,), {"max_each": 6}))
        if "core" in sources:
            discovery_tasks.append(("core_api_candidates", core_search, (query_window,), {"max_each": 6, "api_key_env": str(search_cfg.get("core_api_key_env") or "CORE_API_KEY")}))
        if "hal" in sources:
            discovery_tasks.append(("hal_api_candidates", hal_search, (query_window,), {"max_each": 6}))
        if "zenodo" in sources:
            discovery_tasks.append(("zenodo_api_candidates", zenodo_search, (query_window,), {"max_each": 6}))
        if "datacite" in sources:
            discovery_tasks.append(("datacite_api_candidates", datacite_search, (query_window,), {"max_each": 6}))
        if "scopus" in sources:
            discovery_tasks.append(("scopus_api_candidates", scopus_search, (query_window,), {"max_each": 6, "api_key_env": str(search_cfg.get("scopus_api_key_env") or "SCOPUS_API_KEY"), "insttoken_env": str(search_cfg.get("scopus_insttoken_env") or "SCOPUS_INSTTOKEN")}))
        if "google_scholar" in sources:
            discovery_tasks.append(("google_scholar_api_candidates", google_scholar_search, (query_window,), {"max_each": 6, "api_key_env": str(search_cfg.get("google_scholar_api_key_env") or "SERPAPI_API_KEY")}))

        # Sources are independent failure domains.  Run one bounded worker per
        # configured source while keeping each adapter's own query loop serial,
        # which avoids both N×timeout latency and bursty per-provider traffic.
        with ThreadPoolExecutor(max_workers=max(1, min(8, len(discovery_tasks)))) as pool:
            pending = {
                pool.submit(function, *arguments, **keywords): event_type
                for event_type, function, arguments, keywords in discovery_tasks
            }
            for future in as_completed(pending):
                event_type = pending[future]
                try:
                    records = future.result()
                    candidates.extend(records)
                    log_event(run_log, type=event_type, count=len(records))
                except Exception as exc:
                    log_event(run_log, type=event_type, count=0, error=repr(exc)[:500])

        raw_count = len(candidates)
        candidates = dedup_candidates(candidates)
        url_dedup_count = len(candidates)

        # Cross-week dedup: exclude papers already seen in dedup.json
        existing_ids = set()
        for raw_key in dedup.get("papers", {}).keys():
            key = str(raw_key)
            if key.lower().startswith("arxiv:"):
                existing_ids.add("arxiv:" + strip_arxiv_version(key.split(":", 1)[1]).lower())
            elif not any(key.startswith(p) for p in ("doi:", "arxiv:", "url:", "title:")) and key.startswith("10."):
                existing_ids.add("doi:" + key)
            else:
                existing_ids.add(key)
        cross_week_deduped = [c for c in candidates if canonical_id(c) not in existing_ids]
        cross_dedup_removed = len(candidates) - len(cross_week_deduped)
        candidates = cross_week_deduped

        # Identifier aliasing: the same work can arrive as "arxiv:2606.11676" in one week and
        # as its journal DOI the next (2026-W39 re-selected W36 papers through their Ecological
        # Informatics DOI). Exclude on the stored title as well.
        dedup_titles = {
            re.sub(r"\s+", " ", str(v.get("title") or "")).strip().lower()
            for v in dedup.get("papers", {}).values()
            if isinstance(v, dict) and str(v.get("title") or "").strip()
        }
        if dedup_titles:
            before_title_dedup = len(candidates)
            candidates = [
                c for c in candidates
                if re.sub(r"\s+", " ", str(c.get("title") or "")).strip().lower() not in dedup_titles
            ]
            cross_dedup_removed += before_title_dedup - len(candidates)

        filtered = []
        rejected = []
        off_direction: list[dict[str, Any]] = []
        future_dated: list[dict[str, Any]] = []
        for c in candidates:
            integrity_ok, integrity_reason = metadata_integrity_verdict(c)
            if not integrity_ok:
                c["filter_score"] = -100
                c["filter_reasons"] = [integrity_reason]
                c["direction_verdict"] = integrity_reason
                rejected.append(c)
                off_direction.append(c)
                continue
            ok, score, reasons = is_paper_like(c)
            c["filter_score"] = score
            c["filter_reasons"] = reasons
            if not ok:
                rejected.append(c)
                continue
            admitted, verdict = direction_verdict(c, policy)
            c["direction_verdict"] = verdict
            if not admitted:
                rejected.append(c)
                if verdict.startswith("future_dated"):
                    future_dated.append(c)
                else:
                    off_direction.append(c)
                continue
            preference_adjustment = feedback_score_adjustment(c, config, feedback)
            c["feedback_score_adjustment"] = preference_adjustment
            c["filter_score"] = score + freshness_bonus(c) + preference_adjustment
            filtered.append(c)

        # Recency is the tiebreak inside a score band: without it, posts from 2025 with long
        # abstracts outrank this week's new work on abstract length alone.
        filtered.sort(
            key=lambda x: (
                x.get("filter_score", 0),
                _published_date(x) or dt.date.min,
                len(str(x.get("abstract", ""))),
                1 if x.get("source") != "existing" else 0,
            ),
            reverse=True,
        )
        evidence_pool, quarantined, evidence_stats = prepare_evidence_pool(
            filtered, args.max_selected
        )
        for paper in evidence_pool:
            paper["canonical_id"] = canonical_id(paper)
        research_profile = build_research_profile(config, feedback)
        semantic_order, semantic_receipt, semantic_provenance = select_papers_semantically(
            evidence_pool,
            research_profile,
            config,
            HERMES_HOME,
            args.max_selected,
        )
        write_json(outdir / "semantic_selection_receipt.json", {
            "version": 1,
            "week": week,
            "generated_at": now_iso(),
            "research_profile": research_profile,
            "selection": semantic_receipt,
            "provenance": semantic_provenance,
        })
        selected: list[dict[str, Any]] = []

        stats = {
            **evidence_stats,
            "raw_candidates": raw_count,
            "candidate_deduped": url_dedup_count,
            "cross_week_deduped": cross_dedup_removed,
            "hard_filter_passed": len(filtered),
            "selected_count": 0,
            "rejected_count": len(rejected),
            "off_direction_rejected": len(off_direction),
            "relevance_policy": "strict_boolean" if policy.get("mode") == "strict" else "semantic_model",
            "future_dated_rejected": len(future_dated),
            "queries": len(queries),
            "selected_discovery_sources": [],
            "semantic_evaluated": len(semantic_receipt.get("evaluations") or {}),
            "semantic_selected": len(semantic_receipt.get("selected_ids") or []),
            "semantic_reserves": len(semantic_receipt.get("reserve_ids") or []),
            "semantic_evaluation_failures": len(semantic_receipt.get("evaluation_failures") or []),
        }

        if args.discovery_only:
            selected = semantic_order[:args.max_selected]
            stats["selected_count"] = len(selected)
            stats["selected_discovery_sources"] = sorted({
                source for paper in selected
                for source in (paper.get("discovery_sources") or [paper.get("source")]) if source
            })
            discovery_out = {
                "version": 2,
                "runner": MARKER,
                "week": week,
                "generated_at": now_iso(),
                "mode": "discovery_only",
                "stats": stats,
                "queries": queries,
                "selected": selected,
                "note": "Papers selected by semantic model review and ready for deep analysis",
            }
            CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
            discovery_path = CANDIDATES_DIR / f"{week}_selected.json"
            write_json(discovery_path, discovery_out)
            log_event(run_log, type="discovery_done", selected=len(selected), output=str(discovery_path))
            print(json.dumps({"ok": True, "mode": "discovery_only", "selected": len(selected), "output": str(discovery_path)}, ensure_ascii=False))
            return 0

        analysis_path = Path(args.analysis_file) if args.analysis_file else outdir / "analysis.json"
        cached_analysis_path = analysis_path if args.analysis_file else published_outdir / "analysis.json"
        analysis_payload = read_json(cached_analysis_path, {})
        if not isinstance(analysis_payload.get("papers"), dict):
            analysis_payload["papers"] = {}
        analysis_cfg = config.get("analysis") if isinstance(config.get("analysis"), dict) else {}
        attempted: set[str] = set()
        analysis_failures: list[str] = []
        analysis_runs: list[dict[str, Any]] = []
        while len(selected) < max(1, args.max_selected):
            available = [paper for paper in semantic_order if canonical_id(paper) not in attempted]
            proposal = available[:max(1, args.max_selected - len(selected))]
            if not proposal:
                break
            for paper in proposal:
                attempted.add(canonical_id(paper))
            proposal_input = [{**paper, "canonical_id": canonical_id(paper)} for paper in proposal]
            pending_ids = incomplete_analysis_ids(analysis_payload, [
                {"id": paper["canonical_id"]} for paper in proposal_input
            ]) if proposal_input else []
            if (
                pending_ids
                and not args.allow_shallow
                and analysis_cfg.get("auto", True) is not False
            ):
                pending_set = set(pending_ids)
                fresh_payload, provenance, isolated_failures = analyze_papers_resilient(
                    [paper for paper in proposal_input if paper["canonical_id"] in pending_set],
                    config,
                    HERMES_HOME,
                )
                analysis_payload["papers"].update(fresh_payload.get("papers") or {})
                if isinstance(fresh_payload.get("narrative"), dict):
                    analysis_payload["narrative"] = fresh_payload["narrative"]
                analysis_runs.append(provenance)
                analysis_failures.extend(isolated_failures)
                analysis_payload["provenance"] = provenance
                write_json(analysis_path, analysis_payload)
                log_event(run_log, type="deep_analysis", requested_ids=pending_ids, **provenance)
            missing = set(attach_deep_analysis(proposal, analysis_payload))
            enrich_author_teams(proposal)
            for paper in proposal:
                issues = [] if args.allow_shallow else paper_publishability_issues(paper)
                if canonical_id(paper) in missing and not args.allow_shallow:
                    if "incomplete_deep_analysis" not in issues:
                        issues.append("incomplete_deep_analysis")
                if issues:
                    quarantined.append({
                        "id": canonical_id(paper),
                        "title": str(paper.get("title") or "")[:240],
                        "reasons": issues,
                    })
                    continue
                selected.append(paper)
                if len(selected) >= max(1, args.max_selected):
                    break
        stats["selected_count"] = len(selected)
        stats["deep_analysis_count"] = sum(
            1 for paper in selected if not paper_publishability_issues(paper)
        )
        stats["paper_failures_isolated"] = len(quarantined)
        stats["analysis_failures_isolated"] = len(set(analysis_failures))
        stats["selected_discovery_sources"] = sorted({
            source for paper in selected
            for source in (paper.get("discovery_sources") or [paper.get("source")]) if source
        })
        write_json(outdir / "quarantine_receipt.json", {
            "version": 1,
            "week": week,
            "generated_at": now_iso(),
            "target_count": max(1, args.max_selected),
            "selected_count": len(selected),
            "items": quarantined,
            "analysis_runs": analysis_runs,
        })
        narrative = analysis_payload.get("narrative") if isinstance(analysis_payload, dict) and isinstance(analysis_payload.get("narrative"), dict) else {}
        if semantic_receipt.get("editorial_rationale") and not narrative.get("editorial_rationale"):
            narrative["editorial_rationale"] = semantic_receipt["editorial_rationale"]
        write_json(outdir / "selected_snapshot.json", {
            "version": 1,
            "runner": MARKER,
            "week": week,
            "generated_at": now_iso(),
            "queries": queries,
            "stats": stats,
            "narrative": narrative,
            "selected": selected,
        })
        report_md = make_report(week, selected, stats, outdir, queries, narrative)
        report_md_path = outdir / "report.md"
        email_body_path = outdir / "email_body.md"
        report_html_path = outdir / "report.html"
        report_pdf_path = outdir / "report.pdf"
        report_md_path.write_text(report_md, encoding="utf-8")
        email_body_path.write_text(
            make_email_brief(week, selected, narrative, delivery_settings),
            encoding="utf-8",
        )
        report_html = make_report_html(week, selected, stats, queries, report_html_path, narrative)
        quality_receipt = validate_report_quality(selected, report_html)
        make_pdf(report_html, report_md, report_pdf_path)
        quality_receipt["pdf_bytes"] = report_pdf_path.stat().st_size
        quality_receipt["pdf_nonempty"] = report_pdf_path.stat().st_size > 5000
        if not quality_receipt["pdf_nonempty"]:
            raise RuntimeError("report quality gate failed: PDF is unexpectedly small")
        write_json(outdir / "quality_receipt.json", quality_receipt)

        delivery_cfg = config.get("delivery") if isinstance(config.get("delivery"), dict) else {}
        if str(delivery_cfg.get("channel") or "email").casefold() != "email":
            raise RuntimeError("Weekly Briefing supports email delivery only")
        configured_recipients = delivery_cfg.get("email_to") if isinstance(delivery_cfg.get("email_to"), list) else []
        email_to = args.email_to or [str(value) for value in configured_recipients if str(value).strip() and "$" not in str(value)]
        subject = f"⚚ 学术研究周报 {week}"
        email_receipt = try_send_email(email_to, subject, email_body_path, report_pdf_path, bool(args.send_email and email_to))

        delivery_receipt = {
            "version": 1,
            "runner": MARKER,
            "week": week,
            "generated_at": now_iso(),
            "local": {
                "status": "written",
                "report_dir": str(published_outdir),
                "markdown": str(published_outdir / "report.md"),
                "html": str(published_outdir / "report.html"),
                "pdf": str(published_outdir / "report.pdf"),
            },
            "email": email_receipt,
        }
        write_json(outdir / "delivery_receipt.json", delivery_receipt)

        if args.send_email and email_receipt.get("status") != "sent":
            raise RuntimeError(
                "email delivery required but not completed: "
                + str(email_receipt.get("status") or "unknown")
            )

        # Selection history is a delivery commit, not a discovery side effect.
        # Dry-runs and failed deliveries must remain repeatable and must not
        # suppress papers that the reader never received.
        history_committed = bool(args.send_email and email_receipt.get("status") == "sent")
        if history_committed:
            now_ts = now_iso()
            for paper in selected:
                dedup.setdefault("papers", {})[canonical_id(paper)] = {
                    "first_seen_week": week,
                    "first_seen_at": now_ts,
                    "title": str(paper.get("title") or "")[:200],
                }
            dedup["updated_at"] = now_ts
            write_json(PAPERS_DIR / "dedup.json", dedup)
        stats["history_committed"] = history_committed

        manifest.update({
            "status": "success" if selected else "no_selection",
            "stats": stats,
            "queries": queries,
            "selected_papers": [{
                "title": p.get("title"),
                "url": p.get("url"),
                "doi": p.get("doi"),
                "arxiv_id": p.get("arxiv_id"),
                "source": p.get("source"),
                "filter_score": p.get("filter_score"),
                "filter_reasons": p.get("filter_reasons"),
            } for p in selected],
            "outputs": {
                "markdown": "report.md",
                "html": "report.html",
                "pdf": "report.pdf",
                "email_body": "email_body.md",
                "selected_snapshot": "selected_snapshot.json",
                "semantic_selection_receipt": "semantic_selection_receipt.json",
                "quarantine_receipt": "quarantine_receipt.json",
                "quality_receipt": "quality_receipt.json",
                "delivery_receipt": "delivery_receipt.json",
                "run_log": str(run_log),
            },
            "delivery": {
                "email": email_receipt.get("status"),
            },
        })
        write_json(outdir / "manifest.json", manifest)
        publish_attempt(
            outdir,
            published_outdir,
            [
                "analysis.json", "selected_snapshot.json", "semantic_selection_receipt.json",
                "quarantine_receipt.json",
                "report.md", "report.html", "report.pdf", "email_body.md", "quality_receipt.json",
                "delivery_receipt.json", "manifest.json",
            ],
        )
        log_event(run_log, type="done", manifest_status=manifest["status"], email_status=email_receipt.get("status"), selected=len(selected))
        print(json.dumps({"ok": True, "manifest": str(published_outdir / "manifest.json"), "report": str(published_outdir / "report.md"), "pdf": str(published_outdir / "report.pdf"), "email_status": email_receipt.get("status")}, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        tb = traceback.format_exc()
        manifest["status"] = "failed"
        manifest["errors"].append({"type": type(e).__name__, "message": str(e), "traceback": tb})
        write_json(outdir / "manifest.json", manifest)
        log_event(run_log, type="failed", error=str(e), traceback=tb)
        print(tb, file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
