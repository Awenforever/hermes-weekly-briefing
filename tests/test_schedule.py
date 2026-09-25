from __future__ import annotations

import argparse
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("weekly_plugin_cli", ROOT / "plugin_cli.py")
plugin = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(plugin)


class ScheduleTests(unittest.TestCase):
    def test_existing_agent_job_is_repaired_in_place(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            data = home / "plugin-data" / "hermes-weekly-briefing"
            data.mkdir(parents=True)
            (data / "config.json").write_text('{"research":{"core_keywords":["smoke"]},"delivery":{"channel":"email","email_to":["a@example.com"]}}', encoding="utf-8")
            calls = []

            def fake_run(command, **_kwargs):
                calls.append(command)
                if command[-2:] == ["cron", "list"]:
                    return argparse.Namespace(returncode=0, stdout="  8f1c27e3174d [active]\n    Name:      weekly-briefing-v2\n", stderr="")
                return argparse.Namespace(returncode=0, stdout="ok", stderr="")

            with mock.patch.object(plugin, "_home", return_value=home), mock.patch.object(plugin, "_hermes_cli", return_value="hermes"), mock.patch.object(plugin, "_doctor_result", return_value={"ok": True, "errors": []}), mock.patch.object(plugin.subprocess, "run", side_effect=fake_run):
                self.assertEqual(0, plugin._install_schedule("0 2 * * 5"))
            command = calls[-1]
            self.assertEqual(["hermes", "cron", "edit", "8f1c27e3174d"], command[:4])
            self.assertIn("--no-agent", command)
            self.assertIn("--clear-skills", command)
            self.assertIn("local", command)
            wrapper = home / "scripts" / "hermes_weekly_briefing.py"
            self.assertTrue(wrapper.is_file())
            self.assertNotIn("weixin", wrapper.read_text(encoding="utf-8").lower())

    def test_init_creates_safe_non_drifting_config(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            with mock.patch.object(plugin, "_home", return_value=home):
                self.assertEqual(0, plugin._initialize(["a@example.com"], ["wildfire smoke"]))
                self.assertEqual([], plugin._config_diagnostics())
            config = __import__("json").loads((home / "plugin-data" / "hermes-weekly-briefing" / "config.json").read_text(encoding="utf-8"))
            self.assertFalse(config["research"]["use_profile_weights"])
            self.assertFalse(config["research"]["use_user_feedback"])
            self.assertEqual("email", config["delivery"]["channel"])

    def test_schedule_refuses_until_every_runtime_dependency_is_ready(self):
        with mock.patch.object(plugin, "_doctor_result", return_value={"ok": False, "errors": ["Agently CLI login is required"]}):
            self.assertEqual(2, plugin._install_schedule("0 2 * * 5"))

    def test_setup_reports_mail_install_then_login_without_guessing_success(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            with mock.patch.object(plugin, "_home", return_value=home), mock.patch.object(plugin, "_mail_status", return_value={"installed": False, "authenticated": False, "cli": None, "install_package": "@tencent-qqmail/agently-cli"}):
                state = plugin._setup_status()
                self.assertIn("personal_preferences", state["unresolved"])
                self.assertIn("agently_install", state["unresolved"])
            data = home / "plugin-data" / "hermes-weekly-briefing"
            data.mkdir(parents=True)
            (data / "config.json").write_text('{"research":{"core_keywords":["smoke"]},"delivery":{"channel":"email","email_to":["a@example.com"]}}', encoding="utf-8")
            with mock.patch.object(plugin, "_home", return_value=home), mock.patch.object(plugin, "_mail_status", return_value={"installed": True, "authenticated": False, "cli": "/bin/agently-cli", "install_package": "@tencent-qqmail/agently-cli"}):
                state = plugin._setup_status()
                self.assertEqual(["agently_login"], state["unresolved"])
                self.assertIn("interactive", state["next_action"])

    def test_guided_setup_persists_every_personal_choice(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            args = argparse.Namespace(
                email_to=["researcher@example.com"],
                keyword=["wildfire smoke", "satellite segmentation"],
                max_selected=4,
                timezone="Asia/Shanghai",
                schedule="30 8 * * 5",
                provider="USTC",
                model="deepseek-flash",
                fallback_model="qwen3.6-chat",
                use_profile_weights=False,
                use_user_feedback=True,
            )
            with mock.patch.object(plugin, "_home", return_value=home), mock.patch.object(plugin, "_mail_status", return_value={"installed": False, "authenticated": False, "cli": None, "install_package": "@tencent-qqmail/agently-cli"}):
                self.assertEqual(0, plugin._configure(args))
            config = __import__("json").loads((home / "plugin-data" / "hermes-weekly-briefing" / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(4, config["max_selected"])
            self.assertEqual("30 8 * * 5", config["schedule"]["expression"])
            self.assertEqual("Asia/Shanghai", config["schedule"]["timezone"])
            self.assertTrue(config["research"]["use_user_feedback"])
            self.assertEqual("deepseek-flash", config["analysis"]["model"])


if __name__ == "__main__":
    unittest.main()
