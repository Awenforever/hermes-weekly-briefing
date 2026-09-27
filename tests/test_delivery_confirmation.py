from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "research" / "weekly-briefing-v2" / "scripts" / "run_weekly_e2e.py"
SPEC = importlib.util.spec_from_file_location("weekly_runner_delivery", RUNNER)
runner = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(runner)


class DeliveryConfirmationTests(unittest.TestCase):
    def test_command_preserves_selected_agently_workspace(self):
        completed = mock.Mock(returncode=0, stdout="{}", stderr="")
        with mock.patch.dict(os.environ, {"AGENTLY_WORKSPACE": "hermes", "HERMES_SESSION_ID": "transient"}, clear=False), mock.patch.object(
            runner.subprocess, "run", return_value=completed
        ) as run:
            runner.run_cmd(["agently-cli", "+me"])
        self.assertEqual("hermes", run.call_args.kwargs["env"]["AGENTLY_WORKSPACE"])
        self.assertNotIn("HERMES_SESSION_ID", run.call_args.kwargs["env"])

    def test_successful_prepare_response_is_confirmed_before_sent(self):
        prepared = {
            "ok": True,
            "data": {"confirmation_required": True, "confirmation_token": "secret-token"},
        }
        confirmed = {"ok": True, "data": {"confirmation_required": False, "message": "sent"}}
        responses = [
            {"ok": True, "stdout": json.dumps(prepared), "stderr": "", "returncode": 0},
            {"ok": True, "stdout": json.dumps(confirmed), "stderr": "", "returncode": 0},
        ]
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            body, pdf = root / "report.md", root / "report.pdf"
            body.write_text("body", encoding="utf-8")
            pdf.write_bytes(b"pdf")
            with mock.patch.object(runner, "find_agently_cli", return_value="agently-cli"), mock.patch.object(runner, "run_cmd", side_effect=responses) as call:
                receipt = runner.try_send_email(["reader@example.com"], "subject", body, pdf, True)
        self.assertEqual("sent", receipt["status"])
        self.assertEqual(2, call.call_count)
        self.assertIn("--confirmation-token", call.call_args_list[1].args[0])

    def test_missing_confirmation_token_is_not_delivery(self):
        prepared = {"ok": True, "data": {"confirmation_required": True}}
        response = {"ok": True, "stdout": json.dumps(prepared), "stderr": "", "returncode": 0}
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            body, pdf = root / "report.md", root / "report.pdf"
            body.write_text("body", encoding="utf-8")
            pdf.write_bytes(b"pdf")
            with mock.patch.object(runner, "find_agently_cli", return_value="agently-cli"), mock.patch.object(runner, "run_cmd", return_value=response):
                receipt = runner.try_send_email(["reader@example.com"], "subject", body, pdf, True)
        self.assertEqual("send_failed", receipt["status"])
        self.assertEqual("confirmation_missing", receipt["deliveries"][0]["status"])


if __name__ == "__main__":
    unittest.main()
