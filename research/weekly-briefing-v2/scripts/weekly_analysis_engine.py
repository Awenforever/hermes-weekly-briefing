#!/usr/bin/env python3
"""Grounded deep-analysis client using an existing Hermes provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_hermes_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        import yaml
        value = yaml.safe_load(text)
    except Exception:
        try:
            value = json.loads(text)
        except Exception:
            value = {}
    return value if isinstance(value, dict) else {}


def resolve_backend(config: dict[str, Any], hermes_home: Path) -> dict[str, Any]:
    analysis = config.get("analysis") if isinstance(config.get("analysis"), dict) else {}
    return {
        "provider_name": "hermes",
        "model": str(analysis.get("model") or "").strip(),
        "fallback_model": str(analysis.get("fallback_model") or "").strip(),
        "timeout_seconds": int(analysis.get("timeout_seconds") or 180),
        "max_tokens": min(8192, max(2000, int(analysis.get("max_tokens") or 7000))),
    }


def _json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:].lstrip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise RuntimeError("analysis model returned no JSON object")
    value = json.loads(raw[start : end + 1])
    if not isinstance(value, dict):
        raise RuntimeError("analysis model returned a non-object")
    return value


def _request_analysis(
    backend: dict[str, Any], model: str, system: str, user: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        from agent.auxiliary_client import call_llm, extract_content_or_reasoning
    except Exception as exc:
        raise RuntimeError("Hermes auxiliary model router is unavailable") from exc
    route_info: dict[str, str] = {}
    response = call_llm(
        task="weekly_briefing",
        model=model or None,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0,
        max_tokens=backend["max_tokens"],
        timeout=backend["timeout_seconds"],
        extra_body={"response_format": {"type": "json_object"}},
        route_info=route_info,
    )
    content = extract_content_or_reasoning(response)
    result = _json_object(content)
    if not isinstance(result.get("papers"), dict):
        raise RuntimeError("analysis JSON is missing papers")
    return result, {
        "model": route_info.get("resolved_model") or route_info.get("model") or model or "hermes-primary",
        "provider": route_info.get("resolved_provider") or "hermes",
    }


def incomplete_analysis_ids(result: dict[str, Any], items: list[dict[str, Any]]) -> list[str]:
    records = result.get("papers") if isinstance(result.get("papers"), dict) else {}
    incomplete: list[str] = []
    for item in items:
        paper_id = str(item.get("id") or "")
        record = records.get(paper_id)
        if not isinstance(record, dict):
            incomplete.append(paper_id)
            continue
        scalars_ok = all(str(record.get(key) or "").strip() for key in ("problem", "why_it_matters"))
        lists_ok = all(isinstance(record.get(key), list) and bool(record.get(key)) for key in ("method_steps", "evidence", "limitations"))
        if not scalars_ok or not lists_ok:
            incomplete.append(paper_id)
    return incomplete


def _analysis_request(items: list[dict[str, Any]], schema: dict[str, Any], retry: bool = False) -> str:
    task = "补全上次遗漏或不完整的论文分析；每个给定 id 必须原样作为 papers 的键" if retry else "逐篇生成可核验深度分析；每个给定 id 必须原样作为 papers 的键"
    return json.dumps({"task": task, "output_schema": schema, "papers": items}, ensure_ascii=False)


def _request_complete_analysis(
    backend: dict[str, Any],
    model: str,
    system: str,
    items: list[dict[str, Any]],
    schema: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], int]:
    merged: dict[str, Any] = {"papers": {}}
    payload: dict[str, Any] = {}
    pending = list(items)
    for attempt in range(1, 3):
        partial, payload = _request_analysis(
            backend, model, system, _analysis_request(pending, schema, retry=attempt > 1)
        )
        if attempt == 1:
            merged.update({key: value for key, value in partial.items() if key != "papers"})
        merged["papers"].update(partial.get("papers") or {})
        missing = incomplete_analysis_ids(merged, items)
        if not missing:
            return merged, payload, attempt
        pending = [item for item in items if str(item.get("id") or "") in set(missing)]
    raise RuntimeError("analysis model omitted or incompletely analyzed ids: " + ", ".join(incomplete_analysis_ids(merged, items)))


def analyze_papers(
    papers: list[dict[str, Any]],
    config: dict[str, Any],
    hermes_home: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    backend = resolve_backend(config, hermes_home)
    items = []
    for paper in papers:
        items.append({
            "id": paper.get("canonical_id"),
            "title": paper.get("title"),
            "abstract": str(paper.get("abstract") or "")[:8000],
            "authors": list(paper.get("authors") or [])[:8],
            "published": paper.get("published"),
            "doi": paper.get("doi"),
            "arxiv_id": paper.get("arxiv_id"),
        })
    system = (
        "你是严谨的中文学术研究分析员。只能依据给定题名、摘要和元数据陈述论文事实；"
        "未知内容必须明确写‘摘要未说明’，不得虚构实验结果、作者背景或数值。"
        "返回单个 JSON 对象，不要 Markdown。"
    )
    schema = {
        "papers": {
            "<id>": {
                "problem": "研究问题",
                "why_it_matters": "价值",
                "method_steps": [{"name": "步骤", "detail": "依据摘要的说明"}],
                "evidence": ["摘要明确支持的证据；没有则写摘要未说明"],
                "comparison": [{"dimension": "维度", "paper": "本文", "baseline": "基线或摘要未说明"}],
                "limitations": ["明确局限或需阅读全文核验项"],
            }
        }
    }
    requested_model = backend["model"]
    fallback_used = False
    try:
        result, payload, attempts = _request_complete_analysis(backend, requested_model, system, items, schema)
    except Exception:
        fallback_model = str(backend.get("fallback_model") or "").strip()
        if not fallback_model or fallback_model == requested_model:
            raise
        result, payload, attempts = _request_complete_analysis(backend, fallback_model, system, items, schema)
        fallback_used = True
    provenance = {
        "provider": str(payload.get("provider") or backend["provider_name"]),
        "requested_model": backend["model"] or "inherit",
        "actual_model": str(payload.get("model") or (backend["fallback_model"] if fallback_used else backend["model"])),
        "fallback_model": backend["fallback_model"] or "inherit",
        "fallback_used": fallback_used,
        "analysis_attempts": attempts,
        "paper_count": len(papers),
    }
    return result, provenance
