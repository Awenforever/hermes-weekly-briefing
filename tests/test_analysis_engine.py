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


class AnalysisEngineTests(unittest.TestCase):
    def test_resolver_prefers_complete_case_insensitive_provider(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            (home / "config.yaml").write_text(json.dumps({"custom_providers": [
                {"name": "ustc", "base_url": "https://stub.invalid"},
                {"name": "USTC", "base_url": "https://llm.example/v1", "api_key": "secret", "models": ["qwen3.6-chat"]},
            ]}), encoding="utf-8")
            backend = engine.resolve_backend({"analysis": {"provider_name": "uStC"}}, home)
            self.assertEqual("hermes", backend["provider_name"])
            self.assertEqual("", backend["model"])
            self.assertEqual("", backend["fallback_model"])
            self.assertEqual(8192, engine.resolve_backend({"analysis": {"max_tokens": 99999}}, home)["max_tokens"])

    def test_analysis_is_grounded_json_and_provenance_has_no_secret(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            (home / "config.yaml").write_text(json.dumps({"custom_providers": [{
                "name": "USTC", "base_url": "https://llm.example/v1", "api_key": "top-secret", "models": ["qwen3.6-chat"]
            }]}), encoding="utf-8")
            returned = {"papers": {"title:test": {"problem": "问题", "evidence": ["摘要未说明"]}}}
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

    def test_analysis_falls_back_to_qwen_and_records_provenance(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            (home / "config.yaml").write_text(json.dumps({"custom_providers": [{
                "name": "USTC", "base_url": "https://llm.example/v1", "api_key": "secret"
            }]}), encoding="utf-8")
            returned = {"papers": {"title:test": {"problem": "问题"}}}
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


if __name__ == "__main__":
    unittest.main()
