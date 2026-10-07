from __future__ import annotations

import importlib.util
import json
import tempfile
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "research" / "weekly-briefing-v2" / "scripts" / "weekly_analysis_engine.py"
SPEC = importlib.util.spec_from_file_location("weekly_analysis_engine_test", ENGINE)
engine = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(engine)


def _router(call):
    agent = types.ModuleType("agent")
    auxiliary = types.ModuleType("agent.auxiliary_client")
    auxiliary.call_llm = call
    auxiliary.extract_content_or_reasoning = lambda response: response["content"]
    return mock.patch.dict(sys.modules, {"agent": agent, "agent.auxiliary_client": auxiliary})


def _record(problem="问题"):
    return {
        "problem": problem,
        "why_it_matters": "价值",
        "method_steps": [{"name": "步骤", "detail": "摘要依据"}],
        "evidence": ["摘要未说明"],
        "comparison": [],
        "limitations": ["需阅读全文核验"],
    }


class AnalysisEngineTests(unittest.TestCase):
    def test_resolver_prefers_complete_case_insensitive_provider(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            (home / "config.yaml").write_text(json.dumps({"custom_providers": [
                {"name": "example", "base_url": "https://stub.invalid"},
                {"name": "EXAMPLE", "base_url": "https://llm.example/v1", "api_key": "secret", "models": ["fallback-model"]},
            ]}), encoding="utf-8")
            backend = engine.resolve_backend({"analysis": {"provider_name": "eXaMpLe"}}, home)
            self.assertEqual("hermes", backend["provider_name"])
            self.assertEqual("", backend["model"])
            self.assertEqual("", backend["fallback_model"])
            self.assertEqual(8192, engine.resolve_backend({"analysis": {"max_tokens": 99999}}, home)["max_tokens"])

    def test_analysis_is_grounded_json_and_provenance_has_no_secret(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            (home / "config.yaml").write_text(json.dumps({"custom_providers": [{
                "name": "EXAMPLE", "base_url": "https://llm.example/v1", "api_key": "top-secret", "models": ["fallback-model"]
            }]}), encoding="utf-8")
            returned = {"papers": {"title:test": _record()}}
            captured = {}
            def call(**kwargs):
                captured.update(kwargs)
                kwargs["route_info"].update({"resolved_model": "profile-main", "resolved_provider": "profile"})
                return {"content": "```json\n" + json.dumps(returned, ensure_ascii=False) + "\n```"}
            with _router(call):
                result, provenance = engine.analyze_papers([{
                    "canonical_id": "title:test", "title": "Test", "abstract": "Only this abstract may be used."
                }], {}, home)
            self.assertEqual(returned, result)
            self.assertNotIn("top-secret", json.dumps(provenance))
            self.assertEqual(0, captured["temperature"])
            self.assertIsNone(captured["model"])
            self.assertIn("不得虚构", captured["messages"][0]["content"])

    def test_analysis_falls_back_and_records_provenance(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            (home / "config.yaml").write_text(json.dumps({"custom_providers": [{
                "name": "EXAMPLE", "base_url": "https://llm.example/v1", "api_key": "secret"
            }]}), encoding="utf-8")
            returned = {"papers": {"title:test": _record()}}
            calls = []
            def call(**kwargs):
                calls.append(kwargs.get("model"))
                if len(calls) == 1:
                    raise TimeoutError("primary unavailable")
                kwargs["route_info"]["resolved_model"] = "profile-fallback"
                return {"content": json.dumps(returned, ensure_ascii=False)}
            config = {"analysis": {"model": "profile-main", "fallback_model": "profile-fallback"}}
            with _router(call):
                result, provenance = engine.analyze_papers(
                    [{"canonical_id": "title:test", "title": "Test", "abstract": "Abstract"}],
                    config,
                    home,
                )
            self.assertEqual(returned, result)
            self.assertEqual(["profile-main", "profile-fallback"], calls)
            self.assertTrue(provenance["fallback_used"])
            self.assertEqual("profile-fallback", provenance["actual_model"])

    def test_missing_paper_is_retried_and_merged_without_fallback(self):
        calls = []
        def call(**kwargs):
            request = json.loads(kwargs["messages"][1]["content"])
            calls.append([item["id"] for item in request["papers"]])
            if len(calls) == 1:
                payload = {"papers": {"title:one": _record("一")}, "narrative": {"overview": "总览"}}
            else:
                payload = {"papers": {"title:two": _record("二")}}
            kwargs["route_info"]["resolved_model"] = "primary-model"
            return {"content": json.dumps(payload, ensure_ascii=False)}
        papers = [
            {"canonical_id": "title:one", "title": "One", "abstract": "A"},
            {"canonical_id": "title:two", "title": "Two", "abstract": "B"},
        ]
        with _router(call):
            result, provenance = engine.analyze_papers(papers, {"analysis": {"model": "primary-model", "fallback_model": "fallback-model"}}, Path("."))
        self.assertEqual([["title:one", "title:two"], ["title:two"]], calls)
        self.assertEqual({"title:one", "title:two"}, set(result["papers"]))
        self.assertEqual("总览", result["narrative"]["overview"])
        self.assertEqual(2, provenance["analysis_attempts"])
        self.assertFalse(provenance["fallback_used"])

    def test_resilient_analysis_quarantines_only_the_bad_paper(self):
        papers = [
            {"canonical_id": "good", "title": "Good", "abstract": "Evidence"},
            {"canonical_id": "bad", "title": "Bad", "abstract": "Evidence"},
        ]
        def analyze(items, _config, _home):
            if len(items) > 1:
                raise RuntimeError("batch omitted one id")
            paper_id = items[0]["canonical_id"]
            if paper_id == "bad":
                raise RuntimeError("bad record")
            return {"papers": {paper_id: _record()}}, {
                "provider": "hermes", "requested_model": "inherit",
                "actual_model": "main", "fallback_model": "inherit",
                "fallback_used": False, "analysis_attempts": 1,
                "paper_count": 1,
            }
        with mock.patch.object(engine, "analyze_papers", side_effect=analyze):
            result, provenance, failures = engine.analyze_papers_resilient(
                papers, {}, Path(".")
            )
        self.assertEqual({"good"}, set(result["papers"]))
        self.assertEqual(["bad"], failures)
        self.assertTrue(provenance["isolation_used"])

    def test_semantic_selection_model_owns_relevance_and_portfolio_order(self):
        calls = []
        def call(**kwargs):
            request = json.loads(kwargs["messages"][1]["content"])
            calls.append(request["task"])
            kwargs["route_info"]["resolved_model"] = "profile-main"
            if "逐篇" in request["task"]:
                payload = {"evaluations": {
                    item["id"]: {
                        "classification": "core" if item["id"] == "paper:b" else "adjacent",
                        "overall_score": 96 if item["id"] == "paper:b" else 82,
                        "topical_relevance": 95,
                        "methodological_value": 88,
                        "novelty_value": 75,
                        "evidence_confidence": 90,
                        "reason": "摘要显示明确的语义联系",
                        "profile_connections": ["研究问题"],
                    } for item in request["candidates"]
                }}
            else:
                payload = {
                    "selected_ids": ["paper:b"],
                    "reserve_ids": ["paper:a"],
                    "editorial_rationale": "B 更贴近核心问题，A 保留作方法扩展。",
                }
            return {"content": json.dumps(payload, ensure_ascii=False)}
        papers = [
            {"canonical_id": "paper:a", "title": "A", "abstract": "Evidence A" * 20},
            {"canonical_id": "paper:b", "title": "B", "abstract": "Evidence B" * 20},
        ]
        profile = {"core_topics": ["topic"], "selection_mode": "semantic"}
        with _router(call):
            ordered, receipt, provenance = engine.select_papers_semantically(
                papers, profile, {"analysis": {"model": "profile-main"}}, Path("."), 1
            )
        self.assertEqual(["paper:b", "paper:a"], [paper["canonical_id"] for paper in ordered])
        self.assertEqual(["paper:b"], receipt["selected_ids"])
        self.assertEqual(["paper:a"], receipt["reserve_ids"])
        self.assertEqual(2, len(calls))
        self.assertEqual("profile-main", provenance["actual_model"])

    def test_semantic_selection_does_not_fall_back_to_mechanical_choice(self):
        def call(**_kwargs):
            raise RuntimeError("all configured models unavailable")
        paper = {"canonical_id": "paper:a", "title": "A", "abstract": "Evidence" * 30}
        with _router(call):
            with self.assertRaisesRegex(RuntimeError, "no candidate received"):
                engine.select_papers_semantically(
                    [paper], {}, {"analysis": {"selection_attempts": 1}}, Path("."), 1
                )

    def test_semantic_selection_retries_systemic_batch_without_per_paper_amplification(self):
        calls = []
        papers = [
            {"canonical_id": "paper:a", "title": "A", "abstract": "Evidence A"},
            {"canonical_id": "paper:b", "title": "B", "abstract": "Evidence B"},
        ]
        def call(**kwargs):
            request = json.loads(kwargs["messages"][1]["content"])
            calls.append(request)
            if len(calls) == 1:
                raise TimeoutError("temporary upstream timeout")
            if "逐篇" in request["task"]:
                payload = {"evaluations": {
                    item["id"]: {
                        "classification": "core", "overall_score": 90,
                        "reason": "语义相关", "profile_connections": ["主题"],
                    } for item in request["candidates"]
                }}
            else:
                payload = {"selected_ids": ["paper:a"], "reserve_ids": ["paper:b"]}
            return {"content": json.dumps(payload, ensure_ascii=False)}
        config = {"analysis": {
            "selection_attempts": 2, "selection_retry_delays_seconds": [0]
        }}
        with _router(call):
            ordered, receipt, provenance = engine.select_papers_semantically(
                papers, {}, config, Path("."), 1
            )
        self.assertEqual(["paper:a", "paper:b"], [item["canonical_id"] for item in ordered])
        self.assertEqual(3, len(calls))
        self.assertEqual(2, len(calls[0]["candidates"]))
        self.assertEqual(2, len(calls[1]["candidates"]))
        self.assertEqual(2, provenance["evaluation_attempts"])
        self.assertTrue(receipt["evaluation_errors"])

    def test_systemic_failure_is_bounded_diagnostic_and_redacts_secret(self):
        calls = []
        def call(**_kwargs):
            calls.append(1)
            raise RuntimeError("HTTP 403 api_key=do-not-leak token:also-secret")
        config = {"analysis": {
            "selection_attempts": 2, "selection_retry_delays_seconds": [0]
        }}
        paper = {"canonical_id": "paper:a", "title": "A", "abstract": "Evidence"}
        with _router(call):
            with self.assertRaises(RuntimeError) as raised:
                engine.select_papers_semantically([paper], {}, config, Path("."), 1)
        message = str(raised.exception)
        self.assertEqual(2, len(calls))
        self.assertIn("HTTP 403", message)
        self.assertNotIn("do-not-leak", message)
        self.assertNotIn("also-secret", message)

    def test_successful_incomplete_batch_isolated_per_paper(self):
        calls = []
        papers = [
            {"canonical_id": "paper:a", "title": "A", "abstract": "A"},
            {"canonical_id": "paper:b", "title": "B", "abstract": "B"},
        ]
        def evaluation(paper_id):
            return {
                "classification": "core", "overall_score": 90,
                "reason": "语义相关", "profile_connections": ["主题"],
            }
        def call(**kwargs):
            request = json.loads(kwargs["messages"][1]["content"])
            calls.append(request)
            if "逐篇" not in request["task"]:
                return {"content": json.dumps({"selected_ids": ["paper:a"], "reserve_ids": ["paper:b"]})}
            ids = [item["id"] for item in request["candidates"]]
            records = {"paper:a": evaluation("paper:a")} if len(ids) > 1 else {ids[0]: evaluation(ids[0])}
            return {"content": json.dumps({"evaluations": records}, ensure_ascii=False)}
        config = {"analysis": {"selection_attempts": 1}}
        with _router(call):
            ordered, receipt, _ = engine.select_papers_semantically(
                papers, {}, config, Path("."), 1
            )
        self.assertEqual({"paper:a", "paper:b"}, set(receipt["evaluations"]))
        self.assertEqual(3, len(calls))
        self.assertEqual(["paper:b"], [item["id"] for item in calls[1]["candidates"]])
        self.assertEqual(["paper:a", "paper:b"], [item["canonical_id"] for item in ordered])


if __name__ == "__main__":
    unittest.main()
