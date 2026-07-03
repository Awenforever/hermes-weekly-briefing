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

MARKER = "HERMES_WEEKLY_E2E_RUNNER_V1"
DATA_DIR = Path(os.environ.get("HERMES_WEEKLY_DATA_DIR", str(Path.home() / ".hermes" / "weekly-briefing")))
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
        search = urllib.parse.quote(f'all:"{q}"')
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
    weights = profile.get("topic_weights") if isinstance(profile, dict) else None
    if isinstance(weights, dict):
        for k, v in sorted(weights.items(), key=lambda kv: -float(kv[1] or 0))[:4]:
            base.append(str(k))
    biases = feedback.get("biases") if isinstance(feedback, dict) else None
    if isinstance(biases, list):
        for b in biases:
            if isinstance(b, dict) and str(b.get("direction","")).lower() in ("increase","force_explore","boost"):
                base.append(str(b.get("topic") or b.get("keyword") or ""))
    cleaned = []
    for q in base:
        q = normalize_title(str(q))
        if q and q.lower() not in [x.lower() for x in cleaned]:
            cleaned.append(q)
    return cleaned[:10]

def make_report(week: str, selected: list[dict[str, Any]], stats: dict[str, Any], outdir: Path) -> str:
    lines = []
    lines.append(f"# ⚚ 学术研究周报 {week}")
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
        lines.append(f"### {i}. {s.get('title', '?')}")
        lines.append(f"- **来源：** {s.get('source', '?')}")
        if s.get("doi"):
            lines.append(f"- **DOI：** [{s['doi']}](https://doi.org/{s['doi']})")
        if s.get("arxiv_id"):
            lines.append(f"- **arXiv：** [{s['arxiv_id']}](https://arxiv.org/abs/{s['arxiv_id']})")
        if s.get("published"):
            lines.append(f"- **发表：** {s['published']}")
        if s.get("authors"):
            lines.append(f"- **作者：** {', '.join(s['authors'][:5])}")
        if s.get("abstract"):
            lines.append(f"\n{s['abstract'][:500]}")
        lines.append("")
    return "\n".join(lines)

def make_typst(md: str, out: Path) -> None:
    lines = []
    lines.append('#set page(paper: "a4", margin: (top: 2.5cm, bottom: 2cm, left: 2.2cm, right: 2.2cm))')
    lines.append('#set text(font: ("Noto Sans CJK SC", "Noto Serif CJK SC"), size: 10pt, lang: "zh")')
    lines.append(md)
    out.write_text("\n".join(lines), encoding="utf-8")

def make_minimal_pdf(md: str, out: Path) -> None:
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.add_font("NotoSansCJK", "", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", uni=True)
        pdf.set_font("NotoSansCJK", "", 10)
        for line in md.split("\n")[:500]:
            clean = re.sub(r"[#*`\[\]]+", "", line).strip()[:200]
            if clean:
                pdf.multi_cell(0, 5, clean)
        pdf.output(str(out))
    except Exception:
        pass

def split_weixin(text: str, max_chars: int = 1500) -> list[str]:
    chunks = []
    cur = ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > max_chars and cur.strip():
            chunks.append(cur.strip())
            cur = line + "\n"
        else:
            cur += line + "\n"
    if cur.strip():
        chunks.append(cur.strip())
    return chunks

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
    try:
        cwd = body_path.parent
        result = run_cmd([cli, "message", "+send", "--to", to[0], "--subject", subject, "--body-file", body_path.name, "--attachment", pdf_path.name], timeout=60, cwd=cwd)
        rec["send_result"] = result
        if result.get("ok"):
            rec["status"] = "sent"
        else:
            stderr = result.get("stderr", "")
            token_match = re.search(r"confirmation[_\s]?token[:\s]+([a-zA-Z0-9_-]+)", stderr)
            if token_match:
                token = token_match.group(1)
                confirm_result = run_cmd([cli, "message", "+send", "--to", to[0], "--subject", subject, "--body-file", body_path.name, "--attachment", pdf_path.name, "--confirmation-token", token], timeout=60, cwd=cwd)
                rec["confirm_result"] = confirm_result
                rec["status"] = "sent" if confirm_result.get("ok") else "confirm_failed"
            else:
                rec["status"] = "send_failed"
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
    ap.add_argument("--data-dir", default=None, help=f"Override data directory (default: $HERMES_WEEKLY_DATA_DIR or {Path.home() / '.hermes' / 'weekly-briefing'})")
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

        arxiv = arxiv_search(queries[:5], max_each=4)
        candidates.extend(arxiv)
        log_event(run_log, type="arxiv_api_candidates", count=len(arxiv))

        crossref = crossref_search(queries[:5], max_each=4)
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

        filtered = []
        rejected = []
        for c in candidates:
            ok, score, reasons = is_paper_like(c)
            c["filter_score"] = score
            c["filter_reasons"] = reasons
            if ok:
                filtered.append(c)
            else:
                rejected.append(c)

        filtered.sort(key=lambda x: (x.get("filter_score",0), len(str(x.get("abstract",""))), 1 if x.get("source") != "existing" else 0), reverse=True)
        selected = filtered[: max(1, args.max_selected)]

        stats = {
            "raw_candidates": raw_count,
            "candidate_deduped": url_dedup_count,
            "cross_week_deduped": cross_dedup_removed,
            "hard_filter_passed": len(filtered),
            "selected_count": len(selected),
            "rejected_count": len(rejected),
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

        report_md = make_report(week, selected, stats, outdir)
        report_md_path = outdir / "report.md"
        report_typ_path = outdir / "report.typ"
        report_pdf_path = outdir / "report.pdf"
        report_md_path.write_text(report_md, encoding="utf-8")
        make_typst(report_md, report_typ_path)
        make_minimal_pdf(report_md, report_pdf_path)

        chunks = split_weixin(report_md, int(read_json(DATA_DIR / "delivery.json", {}).get("weixin", {}).get("max_chars_per_chunk", 1500)))
        write_json(outdir / "weixin_chunks.json", {
            "week": week,
            "generated_at": now_iso(),
            "max_chars": 1500,
            "chunk_count": len(chunks),
            "chunks": chunks,
            "status": "prepared",
            "note": "Runner prepares Weixin chunks; actual send should be performed by Hermes gateway/cron wrapper with metadata footer.",
        })

        email_to = args.email_to or []
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
                "typst": str(report_typ_path),
                "pdf": str(report_pdf_path),
            },
            "weixin": {
                "status": "prepared",
                "chunks_file": str(outdir / "weixin_chunks.json"),
                "chunk_count": len(chunks),
            },
            "email": email_receipt,
        }
        write_json(outdir / "delivery_receipt.json", delivery_receipt)

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
                "typst": "report.typ",
                "pdf": "report.pdf",
                "weixin_chunks": "weixin_chunks.json",
                "delivery_receipt": "delivery_receipt.json",
                "run_log": str(run_log),
            },
            "delivery": {
                "weixin": "prepared",
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