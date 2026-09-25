#!/usr/bin/env python3
# HERMES_WEEKLY_E2E_RUNNER_V1
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import html
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
import traceback
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from weekly_analysis_engine import analyze_papers

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
}
NON_ACADEMIC_DOMAINS = {
    "github.com", "youtube.com", "twitter.com", "linkedin.com", "medium.com",
    "reddit.com", "facebook.com", "instagram.com", "wikipedia.org",
    "stackoverflow.com", "stackexchange.com", "quora.com", "substack.com",
}

# --- Fixed research direction guard -------------------------------------------
# The briefing's scope is wildfire smoke detection/segmentation from satellite and
# multispectral imagery. Generic query strings such as "deep learning segmentation" or
# "multispectral image analysis" make arXiv/Crossref return medical, telecom and
# agriculture papers (MRI stroke, retinal OCT, renal tumours, 6G channels, wheat
# disease), which then win the score-based selection and drift the report off-direction.
# Every admitted candidate must therefore carry at least one direction term.
DEFAULT_DIRECTION_TERMS = (
    "wildfire", "wild fire", "wildland fire", "forest fire", "bushfire",
    "brush fire", "peat fire", "smoke", "smouldering", "smoldering",
    "burned area", "burnt area", "burn scar", "burn severity",
    "fire detection", "fire segmentation", "active fire", "fire danger",
    "fire risk", "fire spread", "fire weather", "fire radiative",
    "pyrocumul", "pyroconvect", "ember", "combustion", "prescribed burn",
)

# Candidates published after the current year are pipeline artefacts (Crossref
# "sort=published&order=desc" serves future-dated records) and must never be selected.
FRESH_WINDOW_DAYS = 180


def direction_terms(config: dict[str, Any]) -> tuple[str, ...]:
    configured = (config.get("research") or {}).get("direction_terms")
    if isinstance(configured, list):
        cleaned = tuple(str(t).strip().lower() for t in configured if str(t).strip())
        if cleaned:
            return cleaned
    return DEFAULT_DIRECTION_TERMS


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


def direction_verdict(c: dict[str, Any], terms: tuple[str, ...]) -> tuple[bool, str]:
    """Relevance + recency gate. Returns (admitted, reason)."""
    blob = " ".join([
        str(c.get("title") or ""),
        str(c.get("abstract") or ""),
        str(c.get("url") or ""),
    ]).lower()
    if not any(term in blob for term in terms):
        return False, "off_direction"
    published = _published_date(c)
    if published and published.year > dt.date.today().year:
        return False, "future_dated:" + published.isoformat()
    return True, "on_direction"


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

def canonical_id(c: dict[str, Any]) -> str:
    doi = (c.get("doi") or extract_doi(" ".join(str(c.get(k,"")) for k in ("title","url","desc","abstract")))) or ""
    arx = (c.get("arxiv_id") or extract_arxiv_id(" ".join(str(c.get(k,"")) for k in ("title","url","desc","abstract")))) or ""
    if doi:
        return "doi:" + doi.lower()
    if arx:
        return "arxiv:" + arx.lower()
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
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ct = r.headers.get_content_type()
            return r.status, ct, r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, "", str(e)

def arxiv_search(queries: list[str], max_each: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for q in queries:
        # arXiv treats all:"multi word phrase" as an exact phrase, which returns 0 hits for
        # every multi-word direction query ("wildfire smoke satellite segmentation" -> 0),
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
    for q in queries:
        encoded = urllib.parse.quote(q)
        url = f"https://api.crossref.org/works?query={encoded}&rows={max_each}&sort=published&order=desc&filter=type:journal-article"
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
    seen = set()
    out = []
    for c in cands:
        cid = canonical_id(c)
        if not cid or cid in seen:
            continue
        seen.add(cid)
        out.append(c)
    return out

def build_queries(config: dict[str, Any], profile: dict[str, Any], feedback: dict[str, Any]) -> list[str]:
    base = []
    base.extend(config.get("research", {}).get("core_keywords") or [])
    base.extend(["wildfire smoke satellite segmentation", "multispectral smoke detection", "remote sensing fire smoke deep learning"])
    research_cfg = config.get("research", {}) if isinstance(config, dict) else {}
    weights = profile.get("topic_weights") if isinstance(profile, dict) else None
    if research_cfg.get("use_profile_weights") is True and isinstance(weights, dict):
        for k, v in sorted(weights.items(), key=lambda kv: -float(kv[1] or 0))[:4]:
            base.append(str(k))
    biases = feedback.get("biases") if isinstance(feedback, dict) else None
    if research_cfg.get("use_user_feedback") is True and isinstance(biases, list):
        for b in biases:
            if (
                isinstance(b, dict)
                and str(b.get("source", "")).lower() == "user"
                and str(b.get("direction","")).lower() in ("increase","force_explore","boost")
            ):
                base.append(str(b.get("topic") or b.get("keyword") or ""))
    cleaned = []
    for q in base:
        q = normalize_title(str(q))
        if q and q.lower() not in [x.lower() for x in cleaned]:
            cleaned.append(q)
    return cleaned[:10]

def source_url(paper: dict[str, Any]) -> str:
    if paper.get("doi"):
        return f"https://doi.org/{paper['doi']}"
    if paper.get("arxiv_id"):
        return f"https://arxiv.org/abs/{paper['arxiv_id']}"
    value = str(paper.get("url") or "").strip()
    return value if value.startswith(("https://", "http://")) else ""


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


def make_report(week: str, selected: list[dict[str, Any]], stats: dict[str, Any], outdir: Path, queries: list[str]) -> str:
    lines = []
    lines.append(f"# 学术研究周报 {week}")
    lines.append("")
    lines.append(f"**生成时间：** {now_iso()}")
    lines.append("")
    lines.append("## 流水线统计")
    for k, v in stats.items():
        lines.append(f"- **{k}：** {v}")
    lines.append("")
    lines.append("## 入选论文")
    if not selected:
        lines.append("- 未入选论文。")
    for i, s in enumerate(selected, 1):
        link = source_url(s)
        title = s.get('title', '?')
        lines.append(f"### {i}. [{title}]({link})" if link else f"### {i}. {title}")
        lines.append(f"- **来源：** {s.get('source', '?')}")
        if s.get("doi"):
            lines.append(f"- **DOI：** [{s['doi']}](https://doi.org/{s['doi']})")
        if s.get("arxiv_id"):
            lines.append(f"- **arXiv：** [{s['arxiv_id']}](https://arxiv.org/abs/{s['arxiv_id']})")
        if s.get("published"):
            lines.append(f"- **发表：** {s['published']}")
        if s.get("authors"):
            lines.append(f"- **作者：** {', '.join(s['authors'][:5])}")
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
            lines.append(f"\n{s['abstract'][:500]}")
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
    lines.append("## 持续关注（不会自动漂移）")
    lines.append("")
    lines.append("本节仅复述配置中的固定主题与本期检索词；报告正文不会反向改写下周主题。")
    for query in queries:
        lines.append(f"- {query}")
    lines.append("")
    lines.append("> 作者与团队指标来自 OpenAlex，表示其数据库中的收录与引用情况，不等同于主观排名。")
    return "\n".join(lines)

def make_report_html(week: str, selected: list[dict[str, Any]], stats: dict[str, Any], queries: list[str], out: Path) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value or ""))
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
            for recent in list(author.get("recent_works") or [])[:3]:
                if not isinstance(recent, dict):
                    continue
                recent_url = str(recent.get("url") or "")
                recent_label = esc(str(recent.get("title") or "近期论文") + " · " + str(recent.get("year") or "年份未知"))
                recent_links.append(f'<li><a href="{esc(recent_url)}">{recent_label}</a></li>' if recent_url.startswith("http") else f'<li>{recent_label}</li>')
            author_cards.append(
                '<div class="author">' + author_heading + '<br>'
                + esc(" · ".join(metrics)) + '<br><span>' + esc(" / ".join(author.get("topics") or [])) + '</span>'
                + (f'<div class="recent"><b>近期研究</b><ul>{"".join(recent_links)}</ul></div>' if recent_links else '') + '</div>'
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
        analysis_html = f'''
          <div class="analysis"><h3>研究问题</h3><p>{esc(analysis.get("problem") or "等待深度分析")}</p>
          <h3>为什么值得关注</h3><p>{esc(analysis.get("why_it_matters") or "等待深度分析")}</p>
          <h3>方法链</h3><div class="method-tree">{''.join(method_steps) or '<div class="missing">暂无可靠方法拆解</div>'}</div>
          <h3>关键证据</h3><ul>{evidence_items or '<li>暂无可核验证据摘要</li>'}</ul>
          {('<h3>与基线对比</h3><table><thead><tr><th>维度</th><th>本文</th><th>基线</th></tr></thead><tbody>' + ''.join(comparison_rows) + '</tbody></table>') if comparison_rows else ''}
          <h3>局限与验证点</h3><ul>{limitation_items or '<li>需阅读原文后确认</li>'}</ul></div>'''
        papers.append(f'''<section class="paper">
          <div class="paper-index">{index:02d}</div><h2>{title_html}</h2>
          <div class="meta">{esc(paper.get("published"))} · {esc(paper.get("source"))}</div>
          <p>{esc(str(paper.get("abstract") or "")[:900])}</p>
          {analysis_html}
          <div class="team"><h3>作者团队与研究路径</h3>
            <p><strong>机构：</strong>{esc("、".join(team.get("institutions") or []) or "暂无可靠机构数据")}</p>
            <p><strong>主题路径：</strong>{esc(" → ".join(team.get("work_topics") or []) or "暂无可靠主题数据")}</p>
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
    stats_html = ''.join(f'<div class="stat"><b>{esc(v)}</b><span>{esc(k)}</span></div>' for k, v in stats.items())
    queries_html = ''.join(f'<li>{esc(item)}</li>' for item in queries)
    document = f'''<!doctype html><html lang="zh"><head><meta charset="utf-8"><style>
      @page {{ size: A4; margin: 18mm 17mm 20mm; @bottom-right {{ content: counter(page) " / " counter(pages); color:#64748b; font-size:8pt; }} }}
      body {{ font-family: "Noto Sans CJK SC","Microsoft YaHei",sans-serif; color:#172033; font-size:10pt; line-height:1.65; }}
      a {{ color:#0969a8; text-decoration:none; }} h1 {{ font-size:25pt; margin:0 0 5mm; color:#0f2847; }}
      h2 {{ font-size:15pt; line-height:1.35; margin:0 0 2mm; }} h3 {{ font-size:10pt; color:#234b70; margin:0 0 2mm; }}
      .cover {{ min-height:235mm; display:flex; flex-direction:column; justify-content:center; page-break-after:always; }}
      .eyebrow {{ color:#0b7285; letter-spacing:2px; font-weight:700; }} .subtitle {{ color:#52657a; font-size:12pt; }}
      .stats {{ display:grid; grid-template-columns:repeat(3,1fr); gap:3mm; margin-top:12mm; }}
      .stat {{ background:#edf6f8; padding:4mm; border-radius:3mm; }} .stat b {{ display:block; font-size:18pt; color:#0b7285; }} .stat span {{ color:#52657a; font-size:8pt; }}
      .paper {{ position:relative; page-break-inside:avoid; border-top:1px solid #cbd5e1; padding:7mm 0 5mm 13mm; }}
      .paper-index {{ position:absolute; left:0; top:7mm; color:#0b7285; font-weight:800; font-size:10pt; }}
      .meta,.source {{ color:#64748b; font-size:8.5pt; }} .team {{ background:#f6f8fb; border-left:3px solid #4f86a6; padding:4mm; border-radius:1mm; }}
      .author-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:2mm; }} .author {{ background:white; padding:3mm; font-size:8pt; border:1px solid #dce4ea; border-radius:2mm; }}
      .author span {{ color:#52657a; }} .author .recent {{ margin-top:2mm; border-top:1px solid #e2e8f0; padding-top:2mm; }} .author .recent ul {{ margin:1mm 0 0; padding-left:4mm; }}
      .focus,.synthesis {{ page-break-before:always; }} .note {{ padding:4mm; background:#fff7df; border-radius:2mm; color:#66531c; }}
      .synthesis-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:3mm; margin-bottom:5mm; }} .synthesis-card {{ background:#eef5f8; border-left:3px solid #0b7285; padding:3mm; }} .synthesis-card b,.synthesis-card span {{ display:block; }} .synthesis-card span {{ color:#40566d; margin-top:1mm; }}
      .analysis {{ margin:4mm 0; }} .method-tree {{ display:grid; gap:2mm; margin:2mm 0 4mm; }}
      .method-step {{ display:grid; grid-template-columns:42mm 1fr; gap:3mm; background:#eef5f8; border-left:3px solid #0b7285; padding:3mm; border-radius:1.5mm; }}
      .method-step span {{ color:#40566d; }} .missing {{ color:#8a5b00; background:#fff7df; padding:3mm; }}
      table {{ width:100%; border-collapse:collapse; margin:2mm 0 4mm; font-size:8.5pt; }} th,td {{ border:1px solid #d5dee5; padding:2.5mm; vertical-align:top; }}
      th {{ background:#eef5f8; text-align:left; color:#234b70; }}
    </style></head><body>
      <section class="cover"><div class="eyebrow">HERMES RESEARCH BRIEFING</div><h1>学术研究周报<br>{esc(week)}</h1>
      <p class="subtitle">论文证据、作者团队与研究路径的一体化阅读稿</p><div class="stats">{stats_html}</div></section>
      <h1>本期论文</h1>{''.join(papers)}{synthesis_html}
      <section class="focus"><h1>持续关注</h1><p class="note">本节只展示固定配置和显式用户反馈形成的检索词。本期报告不会自动改写下周主题，避免关注点自我强化和漂移。</p><ul>{queries_html}</ul>
      <p class="meta">作者与团队指标来自 OpenAlex，表示数据库收录与引用情况，不等同于主观排名。</p></section>
    </body></html>'''
    out.write_text(document, encoding="utf-8")
    return document


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
    try:
        p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, cwd=str(cwd) if cwd else None, env=env)
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
            if result.get("ok"):
                item["status"] = "sent"
            else:
                stderr = str(result.get("stderr") or "")
                token_match = re.search(r"confirmation[_\s]?token[:\s]+([a-zA-Z0-9_-]+)", stderr, flags=re.I)
                if token_match:
                    token = token_match.group(1)
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
    outdir = REPORTS_DIR / week
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
        profile = read_json(PROFILE_DIR / "current.json", {})
        feedback = read_json(PROFILE_DIR / "topic_feedback.json", {})
        dedup = read_json(PAPERS_DIR / "dedup.json", {})
        archive = read_json(PAPERS_DIR / "archive.json", {})

        queries = build_queries(config, profile, feedback)
        log_event(run_log, type="queries", queries=queries)

        candidates = []
        existing = load_existing_candidates(week)
        candidates.extend(existing)
        log_event(run_log, type="existing_candidates", count=len(existing))

        # Search every built query, not just the first five: build_queries appends the
        # direction-specific strings ("wildfire smoke satellite segmentation" etc.) after the
        # config keywords, and the old queries[:5] slice silently discarded exactly those.
        arxiv = arxiv_search(queries[:8], max_each=4)
        candidates.extend(arxiv)
        log_event(run_log, type="arxiv_api_candidates", count=len(arxiv))

        crossref = crossref_search(queries[:8], max_each=4)
        candidates.extend(crossref)
        log_event(run_log, type="crossref_api_candidates", count=len(crossref))

        raw_count = len(candidates)
        candidates = dedup_candidates(candidates)
        url_dedup_count = len(candidates)

        # Cross-week dedup: exclude papers already seen in dedup.json
        existing_ids = set()
        for raw_key in dedup.get("papers", {}).keys():
            if not any(raw_key.startswith(p) for p in ("doi:", "arxiv:", "url:", "title:")) and raw_key.startswith("10."):
                existing_ids.add("doi:" + raw_key)
            else:
                existing_ids.add(raw_key)
        cross_week_deduped = [c for c in candidates if canonical_id(c) not in existing_ids]
        cross_dedup_removed = len(candidates) - len(cross_week_deduped)
        candidates = cross_week_deduped

        terms = direction_terms(config)
        filtered = []
        rejected = []
        off_direction: list[dict[str, Any]] = []
        future_dated: list[dict[str, Any]] = []
        for c in candidates:
            ok, score, reasons = is_paper_like(c)
            c["filter_score"] = score
            c["filter_reasons"] = reasons
            if not ok:
                rejected.append(c)
                continue
            admitted, verdict = direction_verdict(c, terms)
            c["direction_verdict"] = verdict
            if not admitted:
                rejected.append(c)
                if verdict.startswith("future_dated"):
                    future_dated.append(c)
                else:
                    off_direction.append(c)
                continue
            c["filter_score"] = score + freshness_bonus(c)
            filtered.append(c)

        filtered.sort(key=lambda x: (x.get("filter_score",0), len(str(x.get("abstract",""))), 1 if x.get("source") != "existing" else 0), reverse=True)
        selected = filtered[: max(1, args.max_selected)]

        stats = {
            "raw_candidates": raw_count,
            "candidate_deduped": url_dedup_count,
            "cross_week_deduped": cross_dedup_removed,
            "hard_filter_passed": len(filtered),
            "selected_count": len(selected),
            "rejected_count": len(rejected),
            "off_direction_rejected": len(off_direction),
            "future_dated_rejected": len(future_dated),
            "queries": len(queries),
        }

        # Update dedup.json with newly selected papers for cross-week dedup
        now_ts = now_iso()
        for s in selected:
            dedup.setdefault("papers", {})[canonical_id(s)] = {
                "first_seen_week": week,
                "first_seen_at": now_ts,
                "title": s.get("title", "")[:200],
            }
        dedup["updated_at"] = now_ts
        write_json(PAPERS_DIR / "dedup.json", dedup)

        if args.discovery_only:
            discovery_out = {
                "version": 2,
                "runner": MARKER,
                "week": week,
                "generated_at": now_iso(),
                "mode": "discovery_only",
                "stats": stats,
                "queries": queries,
                "selected": selected,
                "note": "Selected papers ready for LLM deep analysis phase",
            }
            CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
            discovery_path = CANDIDATES_DIR / f"{week}_selected.json"
            write_json(discovery_path, discovery_out)
            log_event(run_log, type="discovery_done", selected=len(selected), output=str(discovery_path))
            print(json.dumps({"ok": True, "mode": "discovery_only", "selected": len(selected), "output": str(discovery_path)}, ensure_ascii=False))
            return 0

        analysis_path = Path(args.analysis_file) if args.analysis_file else outdir / "analysis.json"
        analysis_payload = read_json(analysis_path, {})
        analysis_cfg = config.get("analysis") if isinstance(config.get("analysis"), dict) else {}
        if (
            selected
            and not isinstance(analysis_payload.get("papers") if isinstance(analysis_payload, dict) else None, dict)
            and not args.allow_shallow
            and analysis_cfg.get("auto", True) is not False
        ):
            analysis_input = [{**paper, "canonical_id": canonical_id(paper)} for paper in selected]
            analysis_payload, provenance = analyze_papers(analysis_input, config, HERMES_HOME)
            analysis_payload["provenance"] = provenance
            write_json(analysis_path, analysis_payload)
            log_event(run_log, type="deep_analysis", **provenance)
        missing_analysis = attach_deep_analysis(selected, analysis_payload)
        if missing_analysis and not args.allow_shallow:
            raise RuntimeError(
                "deep analysis is required before production rendering; missing: "
                + ", ".join(missing_analysis)
            )
        stats["deep_analysis_count"] = len(selected) - len(missing_analysis)
        enrich_author_teams(selected)
        report_md = make_report(week, selected, stats, outdir, queries)
        report_md_path = outdir / "report.md"
        report_html_path = outdir / "report.html"
        report_pdf_path = outdir / "report.pdf"
        report_md_path.write_text(report_md, encoding="utf-8")
        report_html = make_report_html(week, selected, stats, queries, report_html_path)
        make_pdf(report_html, report_md, report_pdf_path)

        delivery_cfg = config.get("delivery") if isinstance(config.get("delivery"), dict) else {}
        if str(delivery_cfg.get("channel") or "email").casefold() != "email":
            raise RuntimeError("Weekly Briefing supports email delivery only")
        configured_recipients = delivery_cfg.get("email_to") if isinstance(delivery_cfg.get("email_to"), list) else []
        email_to = args.email_to or [str(value) for value in configured_recipients if str(value).strip() and "$" not in str(value)]
        subject = f"⚚ 学术研究周报 {week}"
        email_receipt = try_send_email(email_to, subject, report_md_path, report_pdf_path, bool(args.send_email and email_to))

        delivery_receipt = {
            "version": 1,
            "runner": MARKER,
            "week": week,
            "generated_at": now_iso(),
            "local": {
                "status": "written",
                "report_dir": str(outdir),
                "markdown": str(report_md_path),
                "html": str(report_html_path),
                "pdf": str(report_pdf_path),
            },
            "email": email_receipt,
        }
        write_json(outdir / "delivery_receipt.json", delivery_receipt)

        if args.send_email and email_receipt.get("status") != "sent":
            raise RuntimeError(
                "email delivery required but not completed: "
                + str(email_receipt.get("status") or "unknown")
            )

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
                "delivery_receipt": "delivery_receipt.json",
                "run_log": str(run_log),
            },
            "delivery": {
                "email": email_receipt.get("status"),
            },
        })
        write_json(outdir / "manifest.json", manifest)
        log_event(run_log, type="done", manifest_status=manifest["status"], email_status=email_receipt.get("status"), selected=len(selected))
        print(json.dumps({"ok": True, "manifest": str(outdir / "manifest.json"), "report": str(report_md_path), "pdf": str(report_pdf_path), "email_status": email_receipt.get("status")}, ensure_ascii=False, indent=2))
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
