#!/usr/bin/env python3
"""Opt-in live backend smoke test. Never prints provider credentials or model prose."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-home", required=True)
    parser.add_argument("--engine", required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("weekly_analysis_engine_live", args.engine)
    engine = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(engine)
    papers = [{
        "canonical_id": "arxiv:2609.01234",
        "title": "A Multimodal Foundation Model for Wildfire Smoke Mapping",
        "abstract": "We combine multispectral satellite observations with temporal priors to map wildfire smoke while reporting uncertainty and cross-region transfer performance.",
        "authors": ["Lin Chen", "Mei Wang"],
        "published": "2026",
        "arxiv_id": "2609.01234",
    }]
    result, provenance = engine.analyze_papers(papers, {}, Path(args.hermes_home))
    record = result.get("papers", {}).get("arxiv:2609.01234", {})
    required = {"problem", "why_it_matters", "method_steps", "evidence", "comparison", "limitations"}
    missing = sorted(required - set(record))
    if missing:
        raise RuntimeError("live analysis missing fields: " + ", ".join(missing))
    print(json.dumps({"ok": True, "provenance": provenance, "fields": sorted(record)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
