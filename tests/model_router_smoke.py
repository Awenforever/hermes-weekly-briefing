#!/usr/bin/env python3
"""Opt-in live Hermes model-router smoke test without provider assumptions."""

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
    paper_id = "doi:10.1000/example"
    papers = [{
        "canonical_id": paper_id,
        "title": "A Reproducible Benchmark for Quantum Error Correction",
        "abstract": "The study compares decoders under controlled noise models and reports uncertainty, ablations, and cross-device transfer.",
        "authors": ["Alex Example", "Riley Example"],
        "published": "2026",
        "doi": "10.1000/example",
    }]
    result, provenance = engine.analyze_papers(papers, {}, Path(args.hermes_home))
    record = result.get("papers", {}).get(paper_id, {})
    required = {
        "problem", "why_it_matters", "method_steps", "evidence", "comparison", "limitations"
    }
    missing = sorted(required - set(record))
    if missing:
        raise RuntimeError("live analysis missing fields: " + ", ".join(missing))
    print(json.dumps(
        {"ok": True, "provenance": provenance, "fields": sorted(record)},
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
