from __future__ import annotations

import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "research" / "weekly-briefing-v2" / "scripts" / "run_weekly_e2e.py"
SPEC = importlib.util.spec_from_file_location("weekly_discovery_runner", RUNNER)
runner = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(runner)


class _Response:
    def __init__(self, payload: dict):
        self.payload = json.dumps(payload).encode()
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


class DiscoverySourceTests(unittest.TestCase):
    def test_openalex_reconstructs_abstract_and_identity(self):
        payload = {"results": [{
            "id": "https://openalex.org/W1",
            "doi": "https://doi.org/10.1000/example",
            "display_name": "A useful paper",
            "publication_date": "2026-09-01",
            "authorships": [{"author": {"display_name": "Ada Example"}}],
            "abstract_inverted_index": {"Useful": [0], "evidence": [1]},
            "primary_location": {"landing_page_url": "https://example.org/paper"},
        }]}
        with mock.patch.object(runner.urllib.request, "urlopen", return_value=_Response(payload)):
            rows = runner.openalex_search(["useful topic"], 1)
        self.assertEqual("Useful evidence", rows[0]["abstract"])
        self.assertEqual("10.1000/example", rows[0]["doi"])
        self.assertEqual(["Ada Example"], rows[0]["authors"])

    def test_openreview_uses_term_search_and_unwraps_content_values(self):
        payload = {"notes": [{
            "id": "note-1", "forum": "forum-1", "cdate": 1780000000000,
            "content": {
                "title": {"value": "An OpenReview paper"},
                "abstract": {"value": "Evidence from a reviewed submission."},
                "authors": {"value": ["One Author", "Two Author"]},
                "venue": {"value": "Example Conference"},
            },
        }]}
        with mock.patch.object(runner, "fetch_url", return_value=(200, "application/json", json.dumps(payload))) as fetch:
            rows = runner.openreview_search(["reviewed topic"], 1)
        self.assertIn("term=reviewed+topic", fetch.call_args.args[0])
        self.assertEqual("An OpenReview paper", rows[0]["title"])
        self.assertEqual(["One Author", "Two Author"], rows[0]["authors"])

    def test_dblp_normalizes_single_author_and_doi(self):
        payload = {"result": {"hits": {"hit": [{"info": {
            "title": "Database paper", "year": "2026", "venue": "VLDB",
            "authors": {"author": {"text": "Single Author"}},
            "ee": "https://doi.org/10.1000/database",
        }}]}}}
        with mock.patch.object(runner, "fetch_url", return_value=(200, "application/json", json.dumps(payload))):
            rows = runner.dblp_search(["database"], 1)
        self.assertEqual(["Single Author"], rows[0]["authors"])
        self.assertEqual("10.1000/database", rows[0]["doi"])

    def test_credentialed_sources_are_opt_in_and_never_guess_keys(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual([], runner.scopus_search(["topic"], 1))
            self.assertEqual([], runner.google_scholar_search(["topic"], 1))

    def test_source_executor_is_bounded_and_keeps_adapter_queries_serial(self):
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn("ThreadPoolExecutor(max_workers=max(1, min(6, len(discovery_tasks))))", source)
        self.assertIn("query_window = queries[:6]", source)
        self.assertIn("for query in queries:", source)


if __name__ == "__main__":
    unittest.main()
