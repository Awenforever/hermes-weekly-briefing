from __future__ import annotations

import argparse
import importlib.util
import json
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
    def test_cron_status_decodes_hermes_output_as_utf8(self):
        completed = argparse.Namespace(
            returncode=0,
            stdout="  abcdef123456 [active]\n    Name:      hermes-weekly-briefing\n",
            stderr="",
        )
        with mock.patch.object(plugin, "_hermes_cli", return_value="hermes"), mock.patch.object(
            plugin.subprocess, "run", return_value=completed
        ) as run:
            jobs = plugin._weekly_jobs()
        self.assertEqual("abcdef123456", jobs[0]["id"])
        self.assertEqual("utf-8", run.call_args.kwargs["encoding"])
        self.assertEqual("replace", run.call_args.kwargs["errors"])

    def test_npm_discovery_checks_beside_node_alias_target(self):
        with tempfile.TemporaryDirectory() as raw:
            package = Path(raw) / "node-package"
            package.mkdir()
            node = package / "node.exe"
            npm = package / "npm.cmd"
            node.write_bytes(b"")
            npm.write_text("@echo off\n", encoding="utf-8")

            def which(name):
                return str(node) if name == "node" else None

            with mock.patch.object(plugin.shutil, "which", side_effect=which), mock.patch.dict(
                plugin.os.environ, {}, clear=True
            ):
                self.assertEqual(str(npm), plugin._find_npm())

    def test_agently_discovery_checks_beside_npm(self):
        with tempfile.TemporaryDirectory() as raw:
            package = Path(raw)
            npm = package / "npm.cmd"
            agently = package / "agently-cli.cmd"
            npm.write_text("@echo off\n", encoding="utf-8")
            agently.write_text("@echo off\n", encoding="utf-8")
            with mock.patch.object(plugin, "_find_npm", return_value=str(npm)), mock.patch.object(
                plugin.shutil, "which", return_value=None
            ), mock.patch.object(plugin.Path, "home", return_value=package), mock.patch.dict(
                plugin.os.environ, {}, clear=True
            ):
                self.assertEqual(str(agently), plugin._find_agently_cli())

    def test_renderer_probe_ignores_dependency_banner_before_json(self):
        completed = argparse.Namespace(
            returncode=0,
            stdout="WeasyPrint optional native library warning\n"
            + json.dumps({
                "weasyprint": {"available": False, "isolated": False},
                "reportlab": {
                    "available": True,
                    "isolated": True,
                    "origin": "runtime/reportlab/__init__.py",
                },
            }) + "\n",
            stderr="",
        )
        with mock.patch.object(plugin, "_runtime_path", return_value=Path("runtime")), mock.patch.object(
            plugin.subprocess, "run", return_value=completed
        ):
            status = plugin._renderer_status()
        self.assertTrue(status["ready"])
        self.assertEqual(["reportlab"], status["available"])
        self.assertTrue(status["isolated"])

    def test_renderer_probe_rejects_packages_found_only_in_hermes_core(self):
        completed = argparse.Namespace(
            returncode=0,
            stdout=json.dumps({
                "weasyprint": {
                    "available": True,
                    "isolated": False,
                    "origin": "/opt/hermes/site-packages/weasyprint/__init__.py",
                },
                "reportlab": {
                    "available": True,
                    "isolated": False,
                    "origin": "/opt/hermes/site-packages/reportlab/__init__.py",
                },
            }),
            stderr="",
        )
        with mock.patch.object(plugin, "_runtime_path", return_value=Path("runtime")), mock.patch.object(
            plugin.subprocess, "run", return_value=completed
        ):
            status = plugin._renderer_status()
        self.assertFalse(status["ready"])
        self.assertEqual(["weasyprint", "reportlab"], status["host_available"])
        self.assertIn("runtime-install", status["diagnostic"])

    def test_search_probe_uses_verified_ssl_context(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = b"{}"
        context = mock.sentinel.ssl_context
        config = {"search": {"sources": ["crossref"]}}
        with mock.patch.object(plugin, "_trusted_ssl_context", return_value=context), mock.patch.object(
            plugin.urllib.request, "urlopen", return_value=response
        ) as open_url:
            status = plugin._search_status(config)
        self.assertTrue(status["ok"])
        self.assertIs(context, open_url.call_args.kwargs["context"])

    def test_runtime_installer_finds_profile_managed_uv(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            uv = home / "bin" / ("uv.exe" if plugin.os.name == "nt" else "uv")
            uv.parent.mkdir(parents=True)
            uv.write_text("", encoding="utf-8")
            with mock.patch.object(plugin, "_home", return_value=home), mock.patch.object(
                plugin.shutil, "which", return_value=None
            ), mock.patch.object(plugin.importlib.util, "find_spec", return_value=None), mock.patch.object(
                plugin.subprocess, "run", return_value=argparse.Namespace(returncode=0)
            ) as run, mock.patch.object(
                plugin, "_renderer_status", return_value={"ready": True, "complete": True, "update_available": {}}
            ), mock.patch.object(
                plugin, "_runtime_render_smoke", return_value={"ok": True, "size": 1024, "diagnostic": ""}
            ):
                self.assertEqual(0, plugin._install_runtime(True))
            command = run.call_args.args[0]
            self.assertEqual(str(uv), command[0])
            self.assertEqual(["pip", "install", "--python", plugin.sys.executable], command[1:5])
            self.assertEqual(["--upgrade", "--target"], command[5:7])
            self.assertEqual(["weasyprint", "reportlab"], command[-2:])
            expected = home / "plugin-data" / "hermes-weekly-briefing" / "runtime" / f"{plugin.sys.implementation.cache_tag}-{plugin.sys.platform}"
            target = Path(command[7])
            self.assertEqual(expected.parent, target.parent)
            self.assertTrue(target.name.startswith(f".{expected.name}.stage-"))
            self.assertTrue(expected.is_dir())

    def test_renderer_rejects_duplicate_distribution_metadata_even_when_import_is_new(self):
        with tempfile.TemporaryDirectory() as raw:
            runtime = Path(raw) / "runtime"
            (runtime / "weasyprint").mkdir(parents=True)
            (runtime / "weasyprint" / "__init__.py").write_text(
                "__version__ = '70.0'\n", encoding="utf-8"
            )
            (runtime / "reportlab").mkdir()
            (runtime / "reportlab" / "__init__.py").write_text(
                "Version = '5.0.1'\n", encoding="utf-8"
            )
            for name, version in (("weasyprint", "69.0"), ("weasyprint", "70.0"), ("reportlab", "5.0.1")):
                dist = runtime / f"{name}-{version}.dist-info"
                dist.mkdir()
                (dist / "METADATA").write_text(
                    f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
                    encoding="utf-8",
                )
            status = plugin._renderer_status(runtime_path=runtime)
        self.assertFalse(status["integrity_ok"])
        self.assertFalse(status["complete"])
        self.assertEqual("70.0", status["versions"]["weasyprint"])
        self.assertEqual(["69.0", "70.0"], status["metadata_versions"]["weasyprint"])
        self.assertTrue(any("weasyprint has 2" in item for item in status["integrity_errors"]))

    def test_runtime_swap_replaces_the_whole_owned_directory(self):
        with tempfile.TemporaryDirectory() as raw:
            parent = Path(raw)
            runtime = parent / "runtime"
            stage = parent / ".runtime.stage-test"
            runtime.mkdir()
            stage.mkdir()
            (runtime / "weasyprint-69.0.dist-info").mkdir()
            (stage / "weasyprint-70.0.dist-info").mkdir()
            (stage / "reportlab-5.0.1.dist-info").mkdir()
            plugin._swap_runtime(stage, runtime)
            self.assertFalse(stage.exists())
            self.assertFalse((runtime / "weasyprint-69.0.dist-info").exists())
            self.assertTrue((runtime / "weasyprint-70.0.dist-info").is_dir())
            self.assertFalse(list(parent.glob(".runtime.rollback-*")))

    def test_failed_runtime_install_keeps_previous_runtime_and_cleans_stage(self):
        with tempfile.TemporaryDirectory() as raw:
            runtime = Path(raw) / "runtime" / "python-platform"
            runtime.mkdir(parents=True)
            (runtime / "sentinel.txt").write_text("old-runtime", encoding="utf-8")
            with mock.patch.object(plugin, "_runtime_path", return_value=runtime), mock.patch.object(
                plugin.importlib.util, "find_spec", return_value=object()
            ), mock.patch.object(
                plugin.subprocess, "run", return_value=argparse.Namespace(returncode=1)
            ):
                self.assertEqual(1, plugin._install_runtime(True, emit=False))
            self.assertEqual("old-runtime", (runtime / "sentinel.txt").read_text(encoding="utf-8"))
            self.assertFalse(list(runtime.parent.glob(f".{runtime.name}.stage-*")))

    def test_failed_render_validation_never_replaces_previous_runtime(self):
        with tempfile.TemporaryDirectory() as raw:
            runtime = Path(raw) / "runtime" / "python-platform"
            runtime.mkdir(parents=True)
            (runtime / "sentinel.txt").write_text("known-good", encoding="utf-8")
            with mock.patch.object(plugin, "_runtime_path", return_value=runtime), mock.patch.object(
                plugin.importlib.util, "find_spec", return_value=object()
            ), mock.patch.object(
                plugin.subprocess, "run", return_value=argparse.Namespace(returncode=0)
            ), mock.patch.object(
                plugin, "_renderer_status", return_value={"ready": True, "complete": True, "update_available": {}}
            ), mock.patch.object(
                plugin, "_runtime_render_smoke", return_value={"ok": False, "size": 0, "diagnostic": "boom"}
            ):
                self.assertEqual(2, plugin._install_runtime(True, emit=False))
            self.assertEqual("known-good", (runtime / "sentinel.txt").read_text(encoding="utf-8"))
            self.assertFalse(list(runtime.parent.glob(f".{runtime.name}.stage-*")))

    def test_runtime_is_plugin_owned_and_survives_core_environment_replacement(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            runtime = home / "plugin-data" / "hermes-weekly-briefing" / "runtime" / f"{plugin.sys.implementation.cache_tag}-{plugin.sys.platform}"
            runtime.mkdir(parents=True)
            (runtime / "sentinel.txt").write_text("persistent", encoding="utf-8")
            with mock.patch.object(plugin, "_home", return_value=home):
                self.assertEqual(runtime, plugin._runtime_path())
            self.assertEqual("persistent", (runtime / "sentinel.txt").read_text(encoding="utf-8"))

    def test_mail_probe_uses_persistent_hermes_workspace(self):
        completed = argparse.Namespace(returncode=0, stdout='{"ok":true}', stderr="")
        with mock.patch.object(plugin, "_find_agently_cli", return_value="/bin/agently-cli"), mock.patch.object(
            plugin, "_load_config", return_value={}
        ), mock.patch.object(plugin.subprocess, "run", return_value=completed) as run, mock.patch.dict(
            plugin.os.environ, {"HERMES_SESSION_ID": "transient"}, clear=True
        ):
            self.assertTrue(plugin._mail_status()["authenticated"])
        self.assertEqual("hermes", run.call_args.kwargs["env"]["AGENTLY_WORKSPACE"])
        self.assertNotIn("HERMES_SESSION_ID", run.call_args.kwargs["env"])

    def test_agently_contract_checks_the_commands_weekly_actually_uses(self):
        outputs = {
            ("agently-cli", "--version"): "agently-cli version 2.3.4",
            ("agently-cli", "message", "+send", "--help"): (
                "--to --subject --body-file --attachment --confirmation-token"
            ),
            ("agently-cli", "auth", "login", "--help"): "--verbose",
        }
        def run(command, **_kwargs):
            return argparse.Namespace(returncode=0, stdout=outputs[tuple(command)], stderr="")
        with mock.patch.object(plugin.subprocess, "run", side_effect=run), mock.patch.object(
            plugin, "_agently_env", return_value={"AGENTLY_WORKSPACE": "hermes"}
        ):
            status = plugin._agently_contract("agently-cli")
        self.assertTrue(status["compatible"])
        self.assertEqual("2.3.4", status["installed_version"])

    def test_mail_update_targets_latest_and_preserves_existing_authentication(self):
        before = {"installed": True, "authenticated": True, "installed_version": "1.0.0"}
        after = {
            "installed": True, "authenticated": True, "installed_version": "1.1.0",
            "latest_version": "1.1.0", "compatible": True, "update_available": False,
            "workspace": "hermes", "diagnostic": "compatible",
        }
        completed = argparse.Namespace(returncode=0)
        with mock.patch.object(plugin, "_find_npm", return_value="npm"), mock.patch.object(
            plugin, "_mail_status", side_effect=[before, after]
        ), mock.patch.object(plugin.subprocess, "run", return_value=completed) as run:
            self.assertEqual(0, plugin._install_mail(True, emit=False))
        self.assertEqual(
            ["npm", "install", "--global", "@tencent-qqmail/agently-cli@latest"],
            run.call_args.args[0],
        )

    def test_dependency_status_rejects_known_updates_but_not_unknown_registry_state(self):
        current_mail = {
            "installed": True, "authenticated": True, "compatible": True,
            "update_available": False,
        }
        current_runtime = {"ready": True, "complete": True, "update_available": {}}
        with mock.patch.object(plugin, "_mail_status", return_value=current_mail), mock.patch.object(
            plugin, "_renderer_status", return_value=current_runtime
        ):
            self.assertTrue(plugin._dependencies_status()["ok"])
        with mock.patch.object(plugin, "_mail_status", return_value={**current_mail, "update_available": True}), mock.patch.object(
            plugin, "_renderer_status", return_value=current_runtime
        ):
            status = plugin._dependencies_status()
        self.assertFalse(status["ok"])
        self.assertIn("Agently CLI update is available", status["errors"])

    def test_run_respects_explicit_isolated_data_directory(self):
        with tempfile.TemporaryDirectory() as raw:
            isolated = Path(raw) / "acceptance"
            args = argparse.Namespace(
                data_dir=str(isolated), max_selected=2, week="2026-W39-C01",
                analysis_file=None, allow_shallow=False, email_to=[], send_email=False,
            )
            completed = argparse.Namespace(returncode=0)
            runtime = Path(raw) / "runtime"
            agently = Path(raw) / "agently-cli.cmd"
            agently.write_text("@echo off\n", encoding="utf-8")
            with mock.patch.object(plugin, "_load_config", return_value={"max_selected": 5}), mock.patch.object(
                plugin, "_runtime_path", return_value=runtime
            ), mock.patch.object(
                plugin, "_find_agently_cli", return_value=str(agently)
            ), mock.patch.object(plugin.subprocess, "run", return_value=completed) as run:
                self.assertEqual(0, plugin._run(args))
            command = run.call_args.args[0]
            env = run.call_args.kwargs["env"]
            resolved = str(isolated.resolve())
            self.assertEqual(resolved, command[command.index("--data-dir") + 1])
            self.assertEqual(resolved, env["HERMES_WEEKLY_DATA_DIR"])
            self.assertEqual(str(runtime), env["HERMES_WEEKLY_RUNTIME_PATH"])
            self.assertEqual(str(agently), env["AGENTLY_CLI_PATH"])

    def test_existing_agent_job_is_repaired_in_place(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            data = home / "plugin-data" / "hermes-weekly-briefing"
            data.mkdir(parents=True)
            (data / "config.json").write_text('{"research":{"core_keywords":["graph algorithms"]},"delivery":{"channel":"email","email_to":["a@example.com"]},"schedule":{"timezone":"Europe/Berlin"}}', encoding="utf-8")
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
            with mock.patch.object(plugin, "_home", return_value=home), mock.patch.object(
                plugin, "_profile_timezone", return_value="Europe/Berlin"
            ):
                self.assertEqual(0, plugin._initialize(
                    ["a@example.com"], ["quantum error correction"], "王老师", "Hermes"
                ))
                self.assertEqual([], plugin._config_diagnostics())
            config = __import__("json").loads((home / "plugin-data" / "hermes-weekly-briefing" / "config.json").read_text(encoding="utf-8"))
            self.assertNotIn("use_profile_weights", config["research"])
            self.assertFalse(config["research"]["use_user_feedback"])
            self.assertEqual("email", config["delivery"]["channel"])
            self.assertEqual("Europe/Berlin", config["schedule"]["timezone"])

    def test_missing_profile_timezone_keeps_fresh_setup_unresolved(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            with mock.patch.object(plugin, "_home", return_value=home), mock.patch.object(
                plugin, "_profile_timezone", return_value=""
            ):
                self.assertEqual(2, plugin._initialize(
                    ["a@example.com"], ["graph algorithms"], "王老师", "Hermes"
                ))
                errors = plugin._config_diagnostics()
            self.assertIn("schedule.timezone needs an explicit IANA timezone", errors)

    def test_profile_timezone_falls_back_to_standard_container_tz(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            (home / "config.yaml").write_text("timezone: ''\n", encoding="utf-8")
            with mock.patch.object(
                plugin, "_home", return_value=home
            ), mock.patch.dict(plugin.os.environ, {"TZ": "Europe/Berlin"}, clear=True):
                self.assertEqual("Europe/Berlin", plugin._profile_timezone())

    def test_explicit_feedback_is_auditable_reversible_and_enables_itself(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            data = home / "plugin-data" / "hermes-weekly-briefing"
            data.mkdir(parents=True)
            (data / "config.json").write_text(
                '{"research":{"core_keywords":["quantum error correction"],"use_user_feedback":false},'
                '"delivery":{"channel":"email","email_to":["a@example.com"]}}',
                encoding="utf-8",
            )
            add = argparse.Namespace(
                topic=["fault-tolerant decoding"], direction="more", remove=[], clear=False,
                note="user confirmed in chat",
            )
            remove = argparse.Namespace(
                topic=[], direction="more", remove=["fault-tolerant decoding"], clear=False,
                note="",
            )
            with mock.patch.object(plugin, "_home", return_value=home):
                self.assertEqual(0, plugin._feedback_command(add))
                state = plugin._load_feedback()
                self.assertEqual("user", state["biases"][0]["source"])
                self.assertEqual("increase", state["biases"][0]["direction"])
                self.assertTrue(plugin._load_config()["research"]["use_user_feedback"])
                self.assertEqual(0, plugin._feedback_command(remove))
                self.assertEqual([], plugin._load_feedback()["biases"])
                self.assertFalse(plugin._load_config()["research"]["use_user_feedback"])
            events = (data / "profile" / "feedback_events.jsonl").read_text(encoding="utf-8")
            self.assertIn('"action": "set"', events)
            self.assertIn('"action": "remove"', events)

    def test_legacy_automatic_profile_weighting_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            data = home / "plugin-data" / "hermes-weekly-briefing"
            data.mkdir(parents=True)
            (data / "config.json").write_text(
                '{"research":{"core_keywords":["quantum error correction"],'
                '"use_profile_weights":true},'
                '"delivery":{"channel":"email","email_to":["a@example.com"]}}',
                encoding="utf-8",
            )
            with mock.patch.object(plugin, "_home", return_value=home):
                errors = plugin._config_diagnostics()
            self.assertTrue(any("use_profile_weights is retired" in error for error in errors))

    def test_schedule_refuses_until_every_runtime_dependency_is_ready(self):
        with mock.patch.object(plugin, "_doctor_result", return_value={"ok": False, "errors": ["Agently CLI login is required"]}):
            self.assertEqual(2, plugin._install_schedule("0 2 * * 5"))

    def test_setup_reports_mail_install_then_login_without_guessing_success(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            with mock.patch.object(plugin, "_home", return_value=home), mock.patch.object(plugin, "_mail_status", return_value={"installed": False, "authenticated": False, "cli": None, "install_package": "@tencent-qqmail/agently-cli"}), mock.patch.object(plugin, "_renderer_status", return_value={"ready": False, "complete": False, "update_available": {}}), mock.patch.object(plugin, "_search_status", return_value={"ok": True, "ready_sources": ["arxiv"], "next_action": "ready"}):
                state = plugin._setup_status()
                self.assertIn("personal_preferences", state["unresolved"])
                self.assertIn("dependencies_install", state["unresolved"])
            data = home / "plugin-data" / "hermes-weekly-briefing"
            data.mkdir(parents=True)
            (data / "config.json").write_text('{"research":{"core_keywords":["graph algorithms"]},"delivery":{"channel":"email","email_to":["a@example.com"],"recipient_salutation":"王老师","sender_signature":"Hermes"},"schedule":{"timezone":"Europe/Berlin"}}', encoding="utf-8")
            with mock.patch.object(plugin, "_home", return_value=home), mock.patch.object(plugin, "_mail_status", return_value={"installed": True, "authenticated": False, "compatible": True, "update_available": False, "cli": "/bin/agently-cli", "install_package": "@tencent-qqmail/agently-cli"}), mock.patch.object(plugin, "_renderer_status", return_value={"ready": True, "complete": True, "update_available": {}}), mock.patch.object(plugin, "_search_status", return_value={"ok": True, "ready_sources": ["arxiv"], "next_action": "ready"}):
                state = plugin._setup_status()
                self.assertEqual(["agently_login"], state["unresolved"])
                self.assertIn("mail-login-start", state["next_action"])
                self.assertIn("verification_url", state["next_action"])

    def test_guided_setup_persists_every_personal_choice(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            args = argparse.Namespace(
                email_to=["researcher@example.com"],
                recipient_salutation="王老师",
                sender_signature="Hermes 研究助理",
                keyword=["quantum error correction", "fault-tolerant computing"],
                direction_term=["quantum code", "fault-tolerant"],
                selection_mode="semantic",
                max_selected=4,
                timezone="Asia/Shanghai",
                schedule="30 8 * * 5",
                provider="example-provider",
                model="primary-model",
                fallback_model="fallback-model",
                use_profile_weights=False,
                use_user_feedback=True,
            )
            with mock.patch.object(plugin, "_home", return_value=home), mock.patch.object(plugin, "_mail_status", return_value={"installed": False, "authenticated": False, "cli": None, "install_package": "@tencent-qqmail/agently-cli"}), mock.patch.object(plugin, "_search_status", return_value={"ok": True, "ready_sources": ["arxiv"], "next_action": "ready"}):
                self.assertEqual(0, plugin._configure(args))
            config = __import__("json").loads((home / "plugin-data" / "hermes-weekly-briefing" / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(4, config["max_selected"])
            self.assertEqual("30 8 * * 5", config["schedule"]["expression"])
            self.assertEqual("Asia/Shanghai", config["schedule"]["timezone"])
            self.assertTrue(config["research"]["use_user_feedback"])
            self.assertEqual(["quantum code", "fault-tolerant"], config["research"]["direction_terms"])
            self.assertEqual("semantic", config["research"]["relevance"]["mode"])
            self.assertEqual("primary-model", config["analysis"]["model"])
            self.assertEqual("王老师", config["delivery"]["recipient_salutation"])
            self.assertEqual("Hermes 研究助理", config["delivery"]["sender_signature"])

    def test_existing_install_uses_model_dynamic_letter_identity(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            data = home / "plugin-data" / "hermes-weekly-briefing"
            data.mkdir(parents=True)
            (data / "config.json").write_text(
                '{"research":{"core_keywords":["graph algorithms"]},'
                '"delivery":{"channel":"email","email_to":["a@example.com"]},'
                '"schedule":{"timezone":"Europe/Berlin"},"search":{"sources":["arxiv"]}}',
                encoding="utf-8",
            )
            with mock.patch.object(plugin, "_home", return_value=home), mock.patch.object(
                plugin, "_mail_status", return_value={"installed": True, "authenticated": True, "compatible": True, "update_available": False}
            ), mock.patch.object(
                plugin, "_renderer_status", return_value={"ready": True, "complete": True, "update_available": {}}
            ), mock.patch.object(
                plugin, "_search_status", return_value={"ok": True, "ready_sources": ["arxiv"], "next_action": "ready"}
            ):
                state = plugin._setup_status()
            self.assertNotIn("personal_preferences", state["unresolved"])
            self.assertEqual([], state["personalization_errors"])
            self.assertEqual("", state["personalization"]["recipient_salutation"])
            self.assertEqual("", state["personalization"]["sender_signature"])
            self.assertEqual("model_dynamic", state["personalization"]["recipient_salutation_source"])
            self.assertEqual("model_dynamic", state["personalization"]["sender_signature_source"])
            self.assertTrue(state["personalization"]["customization_recommended"])

    def test_existing_explicit_legacy_identity_wins_over_defaults(self):
        config = {
            "user": {"display_name": "Kelvin J."},
            "style": {"signature": "庄奕"},
            "delivery": {},
        }
        effective = plugin._effective_personalization(config)
        self.assertEqual("Kelvin J.", effective["recipient_salutation"])
        self.assertEqual("庄奕", effective["sender_signature"])
        self.assertEqual("user.display_name", effective["recipient_salutation_source"])
        self.assertEqual("style.signature", effective["sender_signature_source"])

    def test_new_setup_leaves_identity_to_the_model_when_personalization_is_omitted(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            with mock.patch.object(plugin, "_home", return_value=home), mock.patch.object(
                plugin, "_profile_timezone", return_value="Asia/Shanghai"
            ):
                self.assertEqual(
                    0,
                    plugin._initialize(["researcher@example.com"], ["graph algorithms"], emit=False),
                )
            config = __import__("json").loads(
                (home / "plugin-data" / "hermes-weekly-briefing" / "config.json").read_text(encoding="utf-8")
            )
            self.assertEqual("model_dynamic", config["delivery"]["letter_identity_mode"])
            self.assertNotIn("recipient_salutation", config["delivery"])
            self.assertNotIn("sender_signature", config["delivery"])

    def test_login_url_parser_prefers_oauth_capability_link(self):
        text = "docs https://example.com/help\n请登录 https://agent.qq.com/page/oauth?oauth_type=device&user_code=abc"
        self.assertEqual(
            "https://agent.qq.com/page/oauth?oauth_type=device&user_code=abc",
            plugin._login_url(text),
        )

    def test_login_public_state_uses_hermes_media_contract_only_when_qr_exists(self):
        with tempfile.TemporaryDirectory() as raw:
            qr = Path(raw) / "login.png"
            state = {"status": "pending", "verification_url": "https://agent.qq.com/oauth", "qr_path": str(qr)}
            without = plugin._mail_login_public_state(state)
            self.assertNotIn("media_directive", without)
            qr.write_bytes(b"png")
            with_qr = plugin._mail_login_public_state(state)
            self.assertEqual(f"MEDIA:{qr}", with_qr["media_directive"])

    def test_mail_login_start_returns_link_without_blocking_on_auth_completion(self):
        with tempfile.TemporaryDirectory() as raw:
            login_dir = Path(raw) / "mail-login"
            process = mock.MagicMock()
            process.pid = 4321
            process.poll.return_value = None

            def spawn(*_args, **_kwargs):
                (login_dir / "agently.stderr.log").write_text(
                    "请点击以下链接登录：\nhttps://agent.qq.com/page/oauth?oauth_type=device&user_code=abc\n",
                    encoding="utf-8",
                )
                return process

            mail = {"installed": True, "authenticated": False, "cli": "/bin/agently-cli"}
            with mock.patch.object(plugin, "_mail_status", return_value=mail), mock.patch.object(
                plugin, "_mail_login_dir", return_value=login_dir
            ), mock.patch.object(
                plugin, "_mail_login_state_path", return_value=login_dir / "state.json"
            ), mock.patch.object(plugin, "_read_mail_login_state", return_value={}), mock.patch.object(
                plugin, "_optional_login_qr", return_value=""
            ), mock.patch.object(
                plugin, "_agently_env", return_value={"AGENTLY_WORKSPACE": "hermes"}
            ), mock.patch.object(plugin.subprocess, "Popen", side_effect=spawn):
                code, result = plugin._start_mail_login(wait_seconds=0.5)
            self.assertEqual(0, code)
            self.assertEqual("pending", result["status"])
            self.assertIn("user_code=abc", result["verification_url"])
            self.assertTrue((login_dir / "state.json").is_file())

    def test_mail_login_status_requires_real_identity_probe(self):
        authenticated = {"installed": True, "authenticated": True, "workspace": "hermes"}
        with tempfile.TemporaryDirectory() as raw, mock.patch.object(
            plugin, "_mail_status", return_value=authenticated
        ), mock.patch.object(
            plugin, "_mail_login_state_path", return_value=Path(raw) / "state.json"
        ), mock.patch.object(plugin, "_read_mail_login_state", return_value={}):
            code, result = plugin._mail_login_status()
        self.assertEqual(0, code)
        self.assertEqual("authenticated", result["status"])

    def test_setup_requires_a_reachable_academic_search_engine(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            data = home / "plugin-data" / "hermes-weekly-briefing"
            data.mkdir(parents=True)
            (data / "config.json").write_text(
                '{"research":{"core_keywords":["graph algorithms"]},"delivery":{"channel":"email","email_to":["a@example.com"],"recipient_salutation":"王老师","sender_signature":"Hermes"},"schedule":{"timezone":"Europe/Berlin"},"search":{"sources":["arxiv"]}}',
                encoding="utf-8",
            )
            unavailable = {"ok": False, "ready_sources": [], "next_action": "configure an academic search engine"}
            with mock.patch.object(plugin, "_home", return_value=home), mock.patch.object(plugin, "_mail_status", return_value={"installed": True, "authenticated": True, "compatible": True, "update_available": False}), mock.patch.object(plugin, "_renderer_status", return_value={"ready": True, "complete": True, "update_available": {}}), mock.patch.object(plugin, "_search_status", return_value=unavailable):
                state = plugin._setup_status()
            self.assertIn("academic_search", state["unresolved"])
            self.assertIn("configure", state["next_action"])

    def test_setup_blocks_known_outdated_dependencies_until_user_authorizes_update(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            data = home / "plugin-data" / "hermes-weekly-briefing"
            data.mkdir(parents=True)
            (data / "config.json").write_text(
                '{"research":{"core_keywords":["graph algorithms"]},'
                '"delivery":{"channel":"email","email_to":["a@example.com"]},'
                '"schedule":{"timezone":"Europe/Berlin"},"search":{"sources":["arxiv"]}}',
                encoding="utf-8",
            )
            mail = {
                "installed": True, "authenticated": True, "compatible": True,
                "update_available": True, "installed_version": "1.0.0", "latest_version": "1.1.0",
            }
            runtime = {"ready": True, "complete": True, "update_available": {}}
            with mock.patch.object(plugin, "_home", return_value=home), mock.patch.object(
                plugin, "_mail_status", return_value=mail
            ), mock.patch.object(plugin, "_renderer_status", return_value=runtime), mock.patch.object(
                plugin, "_search_status", return_value={"ok": True, "ready_sources": ["arxiv"], "next_action": "ready"}
            ):
                state = plugin._setup_status()
        self.assertIn("dependencies_update", state["unresolved"])
        self.assertIn("dependencies-update --yes", state["next_action"])


if __name__ == "__main__":
    unittest.main()
