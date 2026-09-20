#!/usr/bin/env python3
"""Grounded deep-analysis client using an existing Hermes provider."""

from __future__ import annotations

import json
import os
import urllib.request
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
    provider_name = str(analysis.get("provider_name") or "USTC")
    model = str(analysis.get("model") or "qwen3.6-chat")
    endpoint = str(analysis.get("endpoint") or "").rstrip("/")
    api_key = ""
    api_key_env = str(analysis.get("api_key_env") or "")
    if api_key_env:
        api_key = os.getenv(api_key_env, "")

    hermes = _load_hermes_config(hermes_home / "config.yaml")
    providers = hermes.get("custom_providers") if isinstance(hermes, dict) else []
    if isinstance(providers, list):
        candidates = [
            item for item in providers
            if isinstance(item, dict)
            and str(item.get("name") or "").casefold() == provider_name.casefold()
        ]
        # Prefer the complete provider entry over historical duplicate stubs.
        candidates.sort(
            key=lambda item: (
                bool(item.get("api_key")), bool(item.get("models")), bool(item.get("base_url"))
            ),
            reverse=True,
        )
        if candidates:
            provider = candidates[0]
            endpoint = endpoint or str(provider.get("base_url") or "").rstrip("/")
            api_key = api_key or str(provider.get("api_key") or "")

    if not endpoint:
        raise RuntimeError(f"Hermes provider {provider_name!r} has no endpoint")
    if not api_key:
        raise RuntimeError(f"Hermes provider {provider_name!r} has no API key")
    return {
        "provider_name": provider_name,
        "model": model,
        "endpoint": endpoint,
        "api_key": api_key,
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
    user = json.dumps(
        {"task": "逐篇生成可核验深度分析", "output_schema": schema, "papers": items},
        ensure_ascii=False,
    )
    body = json.dumps({
        "model": backend["model"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0,
        "max_tokens": backend["max_tokens"],
        "response_format": {"type": "json_object"},
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        backend["endpoint"] + "/chat/completions",
        data=body,
        headers={"Authorization": "Bearer " + backend["api_key"], "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=backend["timeout_seconds"]) as response:
        payload = json.loads(response.read().decode("utf-8"))
    content = payload["choices"][0]["message"]["content"]
    result = _json_object(content)
    papers_result = result.get("papers")
    if not isinstance(papers_result, dict):
        raise RuntimeError("analysis JSON is missing papers")
    provenance = {
        "provider": backend["provider_name"],
        "requested_model": backend["model"],
        "actual_model": str(payload.get("model") or backend["model"]),
        "paper_count": len(papers),
    }
    return result, provenance
