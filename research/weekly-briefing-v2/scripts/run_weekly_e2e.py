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

ACADEMIC_DOMAINS = (
    "arxiv.org", "doi.org", "ieee.org", "ieeecomputer.org", "sciencedirect.com",
    "springer.com", "springeropen.com", "nature.com", "mdpi.com", "frontiersin.org",
    "tandfonline.com", "copernicus.org", "isprs", "acm.org", "wiley.com", "agu.org",
    "neurips.cc", "openaccess.thecvf.com", "eartharxiv", "essopenarchive.org",
)
REJECT_DOMAINS = (
    "noaa.gov", "ospo.noaa.gov", "nesdis.noaa.gov", "weather.gov",
    "amazonaws.com", "github.com", "kaggle.com", "medium.com", "overwatchimaging.com"
)
CORE_TERMS = (
    "smoke", "wildfire", "fire", "satellite", "remote sensing", "multispectral",
    "segmentation", "detection", "transformer", "cnn", "vision", "earth observation"
)

def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")

def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def log_event(log_path: Path, **kw: Any) -> None:
    kw.setdefault("time", now_iso())
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(kw, ensure_ascii=False) + "\n")

def iso_week_today() -> str:
    y, w, _ = dt.date.today().isocalendar()
    return f"{y}-W{w:02d}"

def fetch_url(url: str, timeout: int = 20) -> tuple[int, str, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "HermesWeeklyE2E/1.0 (+academic weekly briefing; contact: local)",
            "Accept": "application/json, application/atom+xml, text/plain, */*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(1024 * 1024)
            ctype = r.headers.get("content-type", "")
            text = raw.decode("utf-8", "replace")
            return int(getattr(r, "status", 200)), ctype, text
    except Exception as e:
        return 0, "", f"FETCH_ERROR: {type(e).__name__}: {e}"

def extract_doi(text: str) -> str | None:
    if not text:
        return None
    m = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", text)
    if m:
        return m.group(0).rstrip(").,;]")
    return None

def extract_arxiv_id(text: str) -> str | None:
    if not text:
        return None
    m = re.search(r"arxiv\.org/(?:abs|html|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?", text, re.I)
    if m:
        return m.group(1)
    m = re.search(r"\barxiv[:\s]+(\d{4}\.\d{4,5})(?:v\d+)?", text, re.I)
    if m:
        return m.group(1)
    return None

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

def normalize_title(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip()

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
                "doi": extract_doi(e),
                "arxiv_id": extract_arxiv_id(idurl),
                "source": "arxiv_api",
                "published": published,
                "authors": authors,
            })
    return out

def crossref_search(queries: list[str], max_each: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for q in queries:
        params = urllib.parse.urlencode({
            "query.title": q,
            "rows": str(max_each),
            "sort": "published",
            "order": "desc",
            "filter": "from-pub-date:2024-01-01,type:journal-article",
        })
        url = "https://api.crossref.org/works?" + params
        code, ctype, text = fetch_url(url, timeout=25)
        if code != 200 or not text.strip().startswith("{"):
            continue
        try:
            data = json.loads(text)
        except Exception:
            continue
        for item in data.get("message", {}).get("items", []):
            title = normalize_title(" ".join(item.get("title") or []))
            abstract = normalize_title(re.sub("<.*?>", " ", item.get("abstract") or ""))
            doi = item.get("DOI")
            url2 = item.get("URL") or ("https://doi.org/" + doi if doi else "")
            year = ""
            parts = item.get("published-print") or item.get("published-online") or item.get("created") or {}
            if parts.get("date-parts"):
                year = str(parts["date-parts"][0][0])
            authors = []
            for a in item.get("author") or []:
                nm = " ".join(x for x in [a.get("given",""), a.get("family","")] if x)
                if nm:
                    authors.append(nm)
            out.append({
                "title": title,
                "url": url2,
                "abstract": abstract,
                "doi": doi,
                "arxiv_id": None,
                "source": "crossref_api",
                "published": year,
                "authors": authors,
            })
    return out

def is_paper_like(c: dict[str, Any]) -> tuple[bool, int, list[str]]:
    title = normalize_title(c.get("title") or "")
    url = str(c.get("url") or "")
    abstract = normalize_title(c.get("abstract") or c.get("desc") or "")
    blob = " ".join([title, url, abstract]).lower()
    reasons: list[str] = []
    score = 0

    doi = c.get("doi") or extract_doi(blob)
    arx = c.get("arxiv_id") or extract_arxiv_id(blob)
    if doi:
        score += 3
        reasons.append("doi")
    if arx:
        score += 3
        reasons.append("arxiv")
    if any(d in url.lower() for d in ACADEMIC_DOMAINS):
        score += 2
        reasons.append("academic_domain")
    if any(k in blob for k in ("journal", "proceedings", "conference", "arxiv", "doi", "abstract", "authors")):
        score += 1
        reasons.append("scholarly_text")
    if len(abstract) >= 120:
        score += 1
        reasons.append("abstract_len")

    rel = sum(1 for k in CORE_TERMS if k in blob)
    score += min(rel, 5)
    if rel:
        reasons.append(f"relevance_terms:{rel}")

    if any(d in url.lower() for d in REJECT_DOMAINS) and not (doi or arx):
        score -= 4
        reasons.append("reject_nonpaper_domain")
    if any(x in title.lower() for x in ("product", "office", "system fire and smoke product", "dataset page")) and not (doi or arx):
        score -= 3
        reasons.append("reject_product_page")
    if not title or len(title) < 10:
        score -= 3
        reasons.append("reject_bad_title")

    return score >= 6 and bool(doi or arx or any(d in url.lower() for d in ACADEMIC_DOMAINS)), score, reasons

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
    lines.append("## 本周总体判断")
    if selected:
        lines.append("本轮流程已改为确定性 E2E runner：一次执行完成候选加载、硬过滤、报告生成、PDF 输出和交付回执落盘，避免在微信中分步执行时“说完就停”。")
    else:
        lines.append("本轮未筛出足够可靠论文，流程仍生成 manifest 与失败原因，避免静默失败。")
    lines.append("")
    lines.append("## 流水线统计")
    for k, v in stats.items():
        lines.append(f"- **{k}：** {v}")
    lines.append("")
    lines.append("## 入选论文")
    if not selected:
        lines.append("- 未入选论文。")
    for i, p in enumerate(selected, 1):
        title = normalize_title(p.get("title") or f"Paper {i}")
        abstract = normalize_title(p.get("abstract") or p.get("desc") or "")
        abstract_short = abstract[:600] + ("…" if len(abstract) > 600 else "")
        lines.append(f"### {i}. {title}")
        if p.get("authors"):
            authors = p.get("authors")
            if isinstance(authors, list):
                lines.append(f"- **作者：** {', '.join(str(a) for a in authors[:6])}")
        if p.get("published"):
            lines.append(f"- **时间：** {p.get('published')}")
        if p.get("doi"):
            lines.append(f"- **DOI：** {p.get('doi')}")
        if p.get("arxiv_id"):
            lines.append(f"- **arXiv：** {p.get('arxiv_id')}")
        if p.get("url"):
            lines.append(f"- **链接：** {p.get('url')}")
        lines.append(f"- **相关性判断：** 与烟雾/火灾遥感、深度学习检测或多光谱分析存在直接或邻近关系。")
        if abstract_short:
            lines.append(f"- **摘要摘录：** {abstract_short}")
        lines.append("")
    lines.append("## 下一步")
    lines.append("- 正式观察期只看三件事：定时触发、论文真实性与方向相关性、manifest/report/PDF/delivery receipt 完整性。")
    lines.append("- 跨设备同步已 discard，不再列为未完成项。")
    lines.append("")
    lines.append("---")
    lines.append("Hermes ᥫᩣ")
    return "\n".join(lines) + "\n"

def make_typst(markdown_text: str, out: Path) -> None:
    title = "学术研究周报"
    body = markdown_text.replace("\\", "\\\\").replace('"', '\\"')
    out.write_text(
        '#set text(font: "Noto Sans CJK SC", size: 10pt)\n'
        '#set page(margin: 1.8cm)\n'
        f'= {title}\n\n'
        f'#raw("{body}")\n',
        encoding="utf-8",
    )

def pdf_escape(s: str) -> str:
    s = s.encode("latin-1", "replace").decode("latin-1")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

def make_minimal_pdf(markdown_text: str, out: Path) -> None:
    plain = []
    for line in markdown_text.splitlines():
        line = re.sub(r"^#+\s*", "", line)
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        line = line.replace("⚚", "*").replace("ᥫᩣ", "")
        if line.strip():
            plain.append(line.strip())
    pages = []
    cur = []
    for line in plain:
        while len(line) > 92:
            cur.append(line[:92])
            line = line[92:]
        cur.append(line)
        if len(cur) >= 42:
            pages.append(cur); cur=[]
    if cur:
        pages.append(cur)
    if not pages:
        pages=[["Hermes weekly report"]]

    objects = []
    # 1 catalog, 2 pages, then pairs page/content, final font
    font_obj_num = 3 + 2 * len(pages)
    kids = []
    for idx, lines in enumerate(pages):
        page_num = 3 + idx*2
        cont_num = page_num + 1
        kids.append(f"{page_num} 0 R")
        content_lines = ["BT", "/F1 10 Tf", "50 790 Td", "14 TL"]
        for l in lines:
            content_lines.append(f"({pdf_escape(l)}) Tj")
            content_lines.append("T*")
        content_lines.append("ET")
        stream = "\n".join(content_lines).encode("latin-1", "replace")
        page_obj = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {font_obj_num} 0 R >> >> /Contents {cont_num} 0 R >>"
        cont_obj = f"<< /Length {len(stream)} >>\nstream\n" + stream.decode("latin-1") + "\nendstream"
        objects.append((page_num, page_obj))
        objects.append((cont_num, cont_obj))
    root = "<< /Type /Catalog /Pages 2 0 R >>"
    pages_obj = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>"
    font_obj = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    all_objs = [(1, root), (2, pages_obj)] + sorted(objects) + [(font_obj_num, font_obj)]

    data = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (font_obj_num + 1)
    for num, obj in all_objs:
        offsets[num] = len(data)
        data.extend(f"{num} 0 obj\n{obj}\nendobj\n".encode("latin-1", "replace"))
    xref = len(data)
    data.extend(f"xref\n0 {font_obj_num+1}\n".encode())
    data.extend(b"0000000000 65535 f \n")
    for i in range(1, font_obj_num+1):
        data.extend(f"{offsets[i]:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size {font_obj_num+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    out.write_bytes(bytes(data))

def split_weixin(markdown_text: str, max_chars: int = 1500) -> list[str]:
    blocks = re.split(r"(?m)(?=^###\s+)", markdown_text)
    chunks: list[str] = []
    cur = ""
    for b in blocks:
        if len(cur) + len(b) <= max_chars:
            cur += b
        else:
            if cur.strip():
                chunks.append(cur.strip())
            if len(b) <= max_chars:
                cur = b
            else:
                for i in range(0, len(b), max_chars):
                    chunks.append(b[i:i+max_chars].strip())
                cur = ""
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


# HERMES_WEEKLY_AGENTLY_MAIL_V1

# HERMES_WEEKLY_AGENTLY_MAIL_CONFIRM_V1
def run_cmd(cmd: list[str], timeout: int = 90, cwd: Path | None = None) -> dict[str, Any]:
    started = time.time()
    env = {
        **os.environ,
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
    }
    try:
        p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, cwd=str(cwd) if cwd else None, env=env)
        return {
            "cmd": cmd,
            "cwd": str(cwd) if cwd else None,
            "returncode": p.returncode,
            "stdout": p.stdout[-12000:],
            "stderr": p.stderr[-12000:],
            "seconds": round(time.time()-started, 2),
        }
    except subprocess.TimeoutExpired as e:
        return {
            "cmd": cmd,
            "cwd": str(cwd) if cwd else None,
            "returncode": 124,
            "stdout": (e.stdout or "")[-12000:] if isinstance(e.stdout, str) else "",
            "stderr": (e.stderr or "")[-12000:] if isinstance(e.stderr, str) else "TIMEOUT",
            "seconds": round(time.time()-started, 2),
        }

def extract_oauth(text: str) -> str | None:
    m = re.search(r"https?://\S*oauth\S*", text or "")
    if m:
        return m.group(0).rstrip("`'\" )]")
    return None

def extract_confirmation_token(text: str) -> str | None:
    m = re.search(r"\bctk_[A-Za-z0-9_-]+\b", text or "")
    if m:
        return m.group(0)
    return None

def parse_jsonish(text: str) -> Any:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"(\{.*\})", text, flags=re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None

def parsed_confirmation(parsed: Any) -> tuple[bool, str | None]:
    if isinstance(parsed, dict):
        data = parsed.get("data")
        if isinstance(data, dict):
            if data.get("confirmation_required") is True:
                return True, data.get("confirmation_token")
    return False, None

def try_send_email(to: list[str], subject: str, body_file: Path, pdf_file: Path, enabled: bool) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "enabled": enabled,
        "recipients": to,
        "status": "not_attempted",
        "attempts": [],
        "oauth_url": None,
        "confirmation_token": None,
        "auto_confirmed": False,
        "attachment_attempted": False,
        "marker": "HERMES_WEEKLY_AGENTLY_MAIL_CONFIRM_V1",
    }

    if not enabled:
        rec["status"] = "prepared"
        return rec

    cli = find_agently_cli() or ""
    rec["cli"] = cli

    if not cli:
        rec["status"] = "failed"
        rec["error"] = "agently-cli not found"
        return rec

    for cmd in ([cli, "--version"], [cli, "+me"]):
        r = run_cmd(cmd, timeout=30)
        rec["attempts"].append(r)

    me_probe = rec["attempts"][-1]
    if me_probe.get("returncode") != 0:
        auth = run_cmd([cli, "auth", "login"], timeout=45)
        rec["attempts"].append(auth)
        combined = (auth.get("stdout","") or "") + "\n" + (auth.get("stderr","") or "")
        rec["oauth_url"] = extract_oauth(combined)
        rec["status"] = "auth_required"
        rec["error"] = "OAuth required before sending" if rec["oauth_url"] else "agently-cli +me failed and auth login did not expose OAuth URL"
        return rec

    cwd = body_file.parent
    base = [cli, "message", "+send"]
    for recipient in to:
        base.extend(["--to", recipient])

    # Primary command: documented body-file + PDF attachment.
    send_cmds = [
        base + ["--subject", subject, "--body-file", body_file.name, "--attachment", pdf_file.name],
        base + ["--subject", subject, "--body-file", body_file.name],
    ]

    last = None
    for send_cmd in send_cmds:
        rec["attachment_attempted"] = rec["attachment_attempted"] or ("--attachment" in send_cmd)
        first = run_cmd(send_cmd, timeout=120, cwd=cwd)
        rec["attempts"].append(first)
        last = first

        combined = (first.get("stdout","") or "") + "\n" + (first.get("stderr","") or "")
        parsed = parse_jsonish(combined)
        rec["last_send_parsed"] = parsed
        required, token = parsed_confirmation(parsed)
        if token:
            rec["confirmation_token"] = token
        else:
            token = extract_confirmation_token(combined)
            if token:
                rec["confirmation_token"] = token
                required = True

        # IMPORTANT: confirmation_required has priority over returncode=0.
        if required:
            rec["status"] = "confirmation_required"
            rec["error"] = "agently-cli requested confirmation-token"
            auto_confirm_allowed = os.environ.get("HERMES_WEEKLY_EMAIL_AUTO_CONFIRM", "0") == "1"
            fixed_recipient_ok = to == ["vive@mail.ustc.edu.cn"]

            if auto_confirm_allowed and fixed_recipient_ok and token:
                confirm_cmd = send_cmd + ["--confirmation-token", token]
                second = run_cmd(confirm_cmd, timeout=120, cwd=cwd)
                rec["attempts"].append(second)
                rec["confirm_cmd"] = confirm_cmd
                rec["auto_confirmed"] = True

                combined2 = (second.get("stdout","") or "") + "\n" + (second.get("stderr","") or "")
                parsed2 = parse_jsonish(combined2)
                rec["confirm_send_parsed"] = parsed2
                required2, token2 = parsed_confirmation(parsed2)
                if token2:
                    rec["confirmation_token_2"] = token2

                if second.get("returncode") == 0 and not required2:
                    # HERMES_WEEKLY_AGENTLY_MAIL_RECEIPT_CLEAN_V1
                    rec["status"] = "sent"
                    rec["successful_cmd"] = confirm_cmd
                    rec.pop("error", None)
                    return rec

                rec["status"] = "failed"
                rec["error"] = "confirmation-token send failed or still requires confirmation"
                rec["last_returncode"] = second.get("returncode")
                rec["last_stderr"] = second.get("stderr")
                return rec

            return rec

        if first.get("returncode") == 0:
            # HERMES_WEEKLY_AGENTLY_MAIL_RECEIPT_CLEAN_V1_DIRECT
            rec["status"] = "sent"
            rec["successful_cmd"] = send_cmd
            rec.pop("error", None)
            return rec

        if first.get("returncode") == 3:
            rec["oauth_url"] = extract_oauth(combined)
            rec["status"] = "auth_required"
            rec["error"] = "authorization expired or missing"
            return rec

        stderr = (first.get("stderr") or "")
        if "unknown flag" in stderr or "unknown shorthand" in stderr or "unknown command" in stderr:
            continue

    rec["status"] = "failed"
    rec["error"] = "agently-cli message +send failed"
    if last:
        rec["last_returncode"] = last.get("returncode")
        rec["last_stderr"] = last.get("stderr")
    return rec

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

        # Use direct APIs, not Hermes web_extract, to avoid URL safety fake-ip blocking.
        arxiv = arxiv_search(queries[:5], max_each=4)
        candidates.extend(arxiv)
        log_event(run_log, type="arxiv_api_candidates", count=len(arxiv))

        crossref = crossref_search(queries[:5], max_each=4)
        candidates.extend(crossref)
        log_event(run_log, type="crossref_api_candidates", count=len(crossref))

        raw_count = len(candidates)
        candidates = dedup_candidates(candidates)
        url_dedup_count = len(candidates)

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

        # Rank by filter score + relevance + source freshness.
        filtered.sort(key=lambda x: (x.get("filter_score",0), len(str(x.get("abstract",""))), 1 if x.get("source") != "existing" else 0), reverse=True)
        selected = filtered[: max(1, args.max_selected)]

        stats = {
            "raw_candidates": raw_count,
            "candidate_deduped": url_dedup_count,
            "hard_filter_passed": len(filtered),
            "selected_count": len(selected),
            "rejected_count": len(rejected),
            "queries": len(queries),
        }

        # Discovery-only mode: stop here, output selected papers for LLM deep analysis
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

        email_to = args.email_to or [r.get("email") for r in read_json(DATA_DIR / "delivery.json", {}).get("email", {}).get("recipients", []) if r.get("email") and not str(r.get("email")).startswith("example")]
        subject = f"⚚ 学术研究周报 {week} — smoke remote sensing"
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

        candidates_snapshot = {
            "week": week,
            "generated_at": now_iso(),
            "raw_count": raw_count,
            "filtered_count": len(filtered),
            "selected_count": len(selected),
            "selected": selected,
            "rejected_sample": rejected[:10],
        }
        CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
        write_json(CANDIDATES_DIR / f"{week}_e2e_candidates.json", candidates_snapshot)

        manifest.update({
            "status": "success" if selected else "no_selection",
            "stats": stats,
            "queries": queries,
            "selected_papers": [
                {
                    "title": p.get("title"),
                    "url": p.get("url"),
                    "doi": p.get("doi"),
                    "arxiv_id": p.get("arxiv_id"),
                    "source": p.get("source"),
                    "filter_score": p.get("filter_score"),
                    "filter_reasons": p.get("filter_reasons"),
                } for p in selected
            ],
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
        print(json.dumps({"ok": True, "manifest": str(outdir / "manifest.json"), "report": str(report_md_path), "pdf": str(report_pdf_path), "email_status": email_receipt.get("status"), "oauth_url": email_receipt.get("oauth_url")}, ensure_ascii=False, indent=2))
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
