"""Owned purpose continuity through real disposable controller and Telos stores."""
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import noetic_application as application
from scripts import noetic_controller as controller
from scripts import noetic_disciplines as disciplines
from scripts import noetic_harness as harness
from scripts import noetic_purpose_binding as purpose_binding
from scripts import noetic_run as runtime
from scripts import noetic_telos as telos
from scripts.noetic_purposes import Purposes, PurposeError
from scripts.noetic_scope import Scope, ScopeStore
from tests.programs.test_noetic_harness import result_for, protocol, process_command


class PurposeContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="purpose-continuity-native-")
        cls.addClassCleanup(cls.build.cleanup)
        cls.source = Path(cls.build.name) / "configured-telos.mjs"
        telos.bundle_goal_store(telos.source_path(), cls.source)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="purpose-continuity-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "same-cwd"
        self.workspace.mkdir()
        env = dict(os.environ)
        env.pop("USER_PROVIDED_PASSWORD", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        subprocess.run(["git", "init", str(self.workspace)], env=env, check=True, capture_output=True)
        (self.workspace / "retained.txt").write_text("original work\n")
        self.runs = self.root / "runs"
        self.runs.mkdir(mode=0o700)
        self.namespace = self.root / "namespace.sqlite3"
        self.store = ScopeStore(self.namespace, root_mandate={"purpose": "Coordinate trials"},
                                human_ref={"fixture": "owner"}, source_ref={"fixture": "root"})
        self.efforts = [self.store.create_effort(intent=name, environment={"cwd": str(self.workspace)},
            mandate={"purpose": name}, origin="human", human_ref={"fixture": "owner"},
            source_ref={"fixture": name})["ordinal"] for name in ("A", "B")]
        self.adapter = disciplines.Disciplines(self.namespace)
        self.instances = [self.adapter.create_instance(command_id=name, effort_root=effort, initiator=effort,
            pattern="cognition", intent=name, environment={"cwd": str(self.workspace)})
            for name, effort in zip(("A", "B"), self.efforts)]
        self.purposes = Purposes(self.namespace, source=self.source)
        self.reference = self.purposes.create("A's maintained purpose", scope=Scope.effort(self.efforts[0]),
            origin_ref={"fixture": "owner"}, source_ref={"fixture": "purpose"})["reference"]
        self.calls = []
        guard = patch.object(harness, "actor_command", side_effect=self.command)
        guard.start()
        self.addCleanup(guard.stop)

    def request(self, index=0):
        instance = self.instances[index]
        return {"namespace_path": str(self.namespace), "effort_root": instance["effort"],
                "discipline_id": instance["id"], "environment": instance["environment"],
                "origin": "human", "human_ref": {"fixture": "owner"}}

    def app(self, **kwargs):
        return application.Application(self.runs, namespace_path=self.namespace, telos_source=self.source, **kwargs)

    def start(self, app=None):
        app = app or self.app()
        body = {**self.request(), "workspace": str(self.workspace), "task": "Bounded task distinct from master purpose",
                "pattern": "cognition", "client": "opencode", "model": "fixture/model", "purpose_ref": self.reference}
        body.pop("namespace_path")
        with patch.object(app, "_launch", side_effect=lambda run, state, *args: (run, state)), redirect_stdout(io.StringIO()):
            return app.start(body)

    def command(self, run, state, options, prompt):
        self.calls.append(state["current_activation"])
        events = protocol(json.dumps(result_for(state)), "opencode", f"fixture-{run.name}-{state['current_activation']}")
        return process_command(events, "import os; assert 'USER_PROVIDED_PASSWORD' not in os.environ; ")

    def snapshot(self, run):
        return {str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.root.rglob("*") if path.is_file() and path.name != "driver.lock" and not path.name.endswith(("-wal", "-shm"))}

    def test_application_retains_full_owned_reference_in_each_authority(self):
        run, state = self.start()
        options = json.loads((run / "options.json").read_text())
        self.assertEqual(options.get("purpose_ref"), self.reference)
        canonical = disciplines.correspondence(run)["native_run"]["options"]
        self.assertEqual(canonical["purpose_ref"], self.reference)
        self.assertEqual(canonical["purpose_config"], options["purpose_config"])
        governing = state["artifacts"][state["slots"]["external.governing"]]["content"]
        self.assertEqual(governing["purpose_ref"], self.reference)
        self.assertEqual(governing["primary_goal"], "A's maintained purpose")
        self.assertEqual(state["purpose"], "Bounded task distinct from master purpose")
        with self.assertRaises(PurposeError):
            self.purposes.resolve(self.reference, scope=Scope.effort(self.efforts[1]))
        self.assertFalse(self.calls)

    def test_custom_resolver_config_survives_restart_actual_advance_and_result_sync(self):
        custom = self.root / "independently-configured-purpose-root"
        self.purposes = Purposes(self.namespace, purposes_root=custom, source=self.source)
        self.reference = self.purposes.create("Custom purpose", scope=Scope.effort(self.efforts[0]),
            origin_ref={"fixture": "owner"}, source_ref={"fixture": "custom"})["reference"]
        app = self.app(purposes_root=custom)
        run, state = self.start(app)
        governing = deepcopy(state["artifacts"][state["slots"]["external.governing"]])
        options = json.loads((run / "options.json").read_text())
        self.assertEqual(options["purpose_config"]["purposes_root"], str(custom))
        self.assertEqual(options["purpose_config"]["source"], str(self.source))
        harness.pause(run)
        restarted = self.app(purposes_root=self.root / "different-current-default", telos_db=self.root / "other.sqlite3")
        with patch.object(restarted, "_launch", side_effect=lambda run, state, *args: (run, state)):
            restarted.advance(run, {"mode": "one"}, selection={"kind": "effort", "effort_root": self.efforts[0]})
        self.assertFalse((run / "pause.requested").exists())
        with patch.dict(os.environ, {"USER_PROVIDED_PASSWORD": "public-development-test-sentinel"}), redirect_stdout(io.StringIO()):
            _, completed = harness.drive(run)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(completed["artifacts"][completed["slots"]["external.governing"]], governing)
        purpose_binding.validate(run, json.loads((run / "options.json").read_text()))
        native = self.purposes.resolve(self.reference, scope=Scope.effort(self.efforts[0]))["native"]
        self.assertEqual(native["chain"]["status"], "active")
        self.assertEqual([s["status"] for s in native["subGoals"]], ["complete"])
        result = [event["data"] for event in runtime.read_events(run) if event["kind"] == "telos.result"][-1]
        self.assertEqual(result["completion_boundary"], "responsible_cognitive_completion")
        self.assertNotIn("opermem", result)
        self.assertFalse((self.root / "different-current-default").exists())
        self.assertFalse((self.root / "other.sqlite3").exists())

    def test_substituted_reference_configuration_and_scalars_refuse_without_effects(self):
        run, _ = self.start()
        harness.pause(run)
        original = json.loads((run / "options.json").read_text())
        self.adapter.cache.unlink()
        substitutions = []
        for field, value in (("owner", {**self.reference["owner"], "ordinal": self.efforts[1]}),
                             ("store_id", "foreign/store"), ("db_path", str(self.root / "foreign.sqlite3")),
                             ("source", str(self.root / "foreign.mjs")), ("chain_id", "foreign-chain")):
            modified = deepcopy(original)
            modified["purpose_ref"][field] = value
            substitutions.append(modified)
        for field, value in (("purposes_root", str(self.root / "substitute")), ("source", str(self.root / "substitute.mjs"))):
            modified = deepcopy(original)
            modified["purpose_config"][field] = value
            substitutions.append(modified)
        modified = deepcopy(original)
        modified.pop("purpose_ref")
        modified.pop("purpose_config")
        substitutions.append(modified)
        modified = deepcopy(original)
        modified["telos_chain"] = "foreign-chain"
        substitutions.append(modified)
        for modified in substitutions:
            with self.subTest(options=modified):
                (run / "options.json").write_text(json.dumps(modified))
                before = self.snapshot(run)
                with self.assertRaises(PurposeError):
                    harness.resume(run)
                with self.assertRaises(PurposeError):
                    harness.drive(run, 1)
                with self.assertRaises(PurposeError):
                    harness._sync_telos(run, modified)
                with self.assertRaises(PurposeError):
                    harness._sync_telos(run, original)
                self.assertEqual(self.snapshot(run), before)
                self.assertTrue((run / "pause.requested").exists())
                self.assertFalse(self.calls)
                self.assertFalse(self.adapter.cache.exists())
        (run / "options.json").write_text(json.dumps(original))
        harness.resume(run)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(harness.drive(run)[1]["status"], "completed")

    def test_actual_missing_or_replaced_store_refuses_then_retained_work_recovers(self):
        run, state = self.start()
        path = Path(self.reference["db_path"])
        retained = path.with_name("original.sqlite3")
        path.rename(retained)
        for replacement in (False, True):
            if replacement:
                foreign = self.purposes.create("Foreign B", scope=Scope.effort(self.efforts[1]),
                    origin_ref={"fixture": "owner"}, source_ref={"fixture": "replacement"})
                shutil.copy2(foreign["reference"]["db_path"], path)
            before = self.snapshot(run)
            with self.assertRaises(PurposeError):
                harness.resume(run)
            with self.assertRaises(PurposeError):
                harness.drive(run)
            self.assertEqual(self.snapshot(run), before)
            self.assertEqual(harness.inspect(run), state)
            self.assertFalse(self.calls)
        path.unlink()
        retained.rename(path)
        self.assertEqual((self.workspace / "retained.txt").read_text(), "original work\n")
        harness.resume(run)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(harness.drive(run)[1]["status"], "completed")

    def test_start_rejects_foreign_or_incomplete_binding_before_preparation(self):
        app = self.app()
        body = {**self.request(1), "workspace": str(self.workspace), "task": "Wrong purpose", "pattern": "development",
                "purpose_ref": self.reference}
        body.pop("namespace_path")
        # Use a maintained development instance so purpose ownership is the refusal.
        instance = self.adapter.create_instance(command_id="dev-B", effort_root=self.efforts[1],
            initiator=self.efforts[1], pattern="development", intent="B", environment={"cwd": str(self.workspace)})
        body["discipline_id"] = instance["id"]
        before = self.snapshot(self.runs)
        with patch.object(application.projects, "task_worktree") as preparation:
            with self.assertRaises(PurposeError):
                app.start(body)
            preparation.assert_not_called()
        for kwargs in ({"purpose_ref": self.reference}, {"telos_chain": self.reference["chain_id"]},
                       {"purpose_ref": self.reference, "purpose_config": purpose_binding.configuration(self.purposes),
                        "telos_db": self.root / "foreign.sqlite3"}):
            with self.assertRaises(PurposeError):
                harness.start("cognition", "task", self.workspace, self.runs,
                              scope_request=self.request(), max_activations=0, **kwargs)
        self.assertEqual(self.snapshot(self.runs), before)
        self.assertFalse(self.calls)

    def test_no_purpose_and_unassigned_legacy_remain_usable_without_adoption(self):
        with redirect_stdout(io.StringIO()):
            plain, _ = harness.start("cognition", "Unowned-purpose task", self.workspace, self.runs,
                                     scope_request=self.request(), max_activations=0)
            self.assertEqual(harness.drive(plain)[1]["status"], "completed")
        self.assertNotIn("purpose_ref", json.loads((plain / "options.json").read_text()))
        legacy_db = self.root / "explicit-legacy.sqlite3"
        native = telos.create_goal("Unassigned legacy purpose", legacy_db, self.source)
        with redirect_stdout(io.StringIO()):
            legacy, _ = harness.start("cognition", "Historical mode", self.workspace, self.runs,
                telos_chain=native["chain"]["chainId"], telos_db=legacy_db, telos_source=self.source, max_activations=0)
            harness.resume(legacy)
            self.assertEqual(harness.drive(legacy)[1]["status"], "completed")
        self.assertEqual(disciplines.correspondence(legacy)["correlation_status"], "unassigned")
        self.assertNotIn("purpose_ref", json.loads((legacy / "options.json").read_text()))

    def test_scoped_historical_bare_chain_is_unavailable_but_cancellation_preserves_work(self):
        options = {"pattern": "cognition", "client": "opencode", "model": "fixture/model", "qa_model": None,
                   "thinking": "high", "verify": None, "timeout": 900, "max_returns": 1, "max_remediations": 1,
                   "goal_ref": "telos:" + self.reference["chain_id"], "telos_chain": self.reference["chain_id"],
                   "telos_db": self.reference["db_path"], "telos_source": self.reference["source"]}
        run = runtime.create_run({"goal": "Historical scoped task", "work": [sys.executable, "-c", "pass"],
                                  "timeout_seconds": 900}, self.workspace, self.runs)
        options["scope"] = self.adapter.execution(self.request(), run, {**options, "workspace": str(self.workspace)})
        runtime.record(run, "scope.bound", options["scope"])
        (run / "options.json").write_text(json.dumps(options))
        pattern = json.loads((controller.PATTERN_DIR / "cognition.json").read_text())
        controller.start_run(run / "controller.sqlite3", pattern, "Historical scoped task", self.workspace)
        before = self.purposes.resolve(self.reference, scope=Scope.effort(self.efforts[0]))["native"]
        with self.assertRaisesRegex(PurposeError, "lacks an owned purpose binding"):
            harness.resume(run)
        with self.assertRaisesRegex(PurposeError, "lacks an owned purpose binding"):
            harness.drive(run)
        self.assertEqual(harness.cancel(run)["status"], "cancelled")
        self.assertEqual((self.workspace / "retained.txt").read_text(), "original work\n")
        self.assertEqual(self.purposes.resolve(self.reference, scope=Scope.effort(self.efforts[0]))["native"], before)
        self.assertNotIn("purpose_ref", json.loads((run / "options.json").read_text()))
        self.assertFalse(self.calls)

    def test_cli_accepts_explicit_owned_reference_and_resolver_files(self):
        files = {}
        for name, data in (("scope", self.request()), ("reference", self.reference),
                           ("config", purpose_binding.configuration(self.purposes))):
            files[name] = self.root / f"{name}.json"
            files[name].write_text(json.dumps(data))
        task = self.root / "task.txt"
        task.write_text("CLI bounded task")
        env = dict(os.environ)
        env.pop("USER_PROVIDED_PASSWORD", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run([sys.executable, "-B", "-m", "scripts.noetic", "harness", "start", "cognition", str(task),
            "--workspace", str(self.workspace), "--runs-dir", str(self.runs), "--max-activations", "0",
            "--scope-request", str(files["scope"]), "--purpose-ref", str(files["reference"]),
            "--purpose-config", str(files["config"])], env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Kernel status: active", result.stdout)
        runs = [p for p in self.runs.iterdir() if p.is_dir()]
        self.assertEqual(len(runs), 1)
        self.assertEqual(json.loads((runs[0] / "options.json").read_text())["purpose_ref"], self.reference)
        self.assertFalse(self.calls)


if __name__ == "__main__":
    unittest.main()
