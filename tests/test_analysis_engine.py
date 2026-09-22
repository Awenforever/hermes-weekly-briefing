from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "research" / "weekly-briefing-v2" / "scripts" / "weekly_analysis_engine.py"
SPEC = importlib.util.spec_from_file_location("weekly_analysis_engine_test", ENGINE)
engine = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(engine)


class _Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


class AnalysisEngineTests(unittest.TestCase):
    def test_resolver_prefers_complete_case_insensitive_provider(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            (home / "config.yaml").write_text(json.dumps({"custom_providers": [
                {"name": "ustc", "base_url": "https://stub.invalid"},
                {"name": "USTC", "base_url": "https://llm.example/v1", "api_key": "secret", "models": ["qwen3.6-chat"]},
            ]}), encoding="utf-8")
            backend = engine.resolve_backend({"analysis": {"provider_name": "uStC"}}, home)
            self.assertEqual("https://llm.example/v1", backend["endpoint"])
            self.assertEqual("deepseek-flash", backend["model"])
            self.assertEqual("qwen3.6-chat", backend["fallback_model"])
            self.assertEqual(8192, engine.resolve_backend({"analysis": {"max_tokens": 99999}}, home)["max_tokens"])

    def test_analysis_is_grounded_json_and_provenance_has_no_secret(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            (home / "config.yaml").write_text(json.dumps({"custom_providers": [{
                "name": "USTC", "base_url": "https://llm.example/v1", "api_key": "top-secret", "models": ["qwen3.6-chat"]
            }]}), encoding="utf-8")
            returned = {"papers": {"title:test": {"problem": "问题", "evidence": ["摘要未说明"]}}}
            payload = {"model": "qwen3.6-chat", "choices": [{"message": {"content": "```json\n" + json.dumps(returned, ensure_ascii=False) + "\n```"}}]}
            with mock.patch.object(engine.urllib.request, "urlopen", return_value=_Response(payload)) as opened:
                result, provenance = engine.analyze_papers([{
                    "canonical_id": "title:test", "title": "Test", "abstract": "Only this abstract may be used."
                }], {}, home)
            self.assertEqual(returned, result)
            self.assertNotIn("top-secret", json.dumps(provenance))
            request = opened.call_args.args[0]
            body = json.loads(request.data)
            self.assertEqual(0, body["temperature"])
            self.assertIn("不得虚构", body["messages"][0]["content"])

    def test_analysis_falls_back_to_qwen_and_records_provenance(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            (home / "config.yaml").write_text(json.dumps({"custom_providers": [{
                "name": "USTC", "base_url": "https://llm.example/v1", "api_key": "secret"
            }]}), encoding="utf-8")
            returned = {"papers": {"title:test": {"problem": "问题"}}}
            payload = {"model": "qwen3.6-chat", "choices": [{"message": {"content": json.dumps(returned, ensure_ascii=False)}}]}
            with mock.patch.object(
                engine.urllib.request,
                "urlopen",
                side_effect=[TimeoutError("primary unavailable"), _Response(payload)],
            ) as opened:
                result, provenance = engine.analyze_papers(
                    [{"canonical_id": "title:test", "title": "Test", "abstract": "Abstract"}],
                    {},
                    home,
                )
            self.assertEqual(returned, result)
            self.assertEqual(2, opened.call_count)
            fallback_request = opened.call_args_list[1].args[0]
            self.assertEqual("qwen3.6-chat", json.loads(fallback_request.data)["model"])
            self.assertTrue(provenance["fallback_used"])
            self.assertEqual("qwen3.6-chat", provenance["actual_model"])


if __name__ == "__main__":
    unittest.main()
