"""Bounded batch behavior using real journals, never model invocations."""

from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch
import uuid

from scripts import noetic as cli
from scripts import noetic_batch as batch
from scripts import noetic_develop as development
from scripts import noetic_run as runtime


ROOT = Path(__file__).resolve().parents[2]
VERIFY = [sys.executable, "-c", "pass"]


@unittest.skipUnless(os.name == "posix", "batch execution uses POSIX flock")
class BatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.manifest = self.inputs / "manifest.json"
        self.runs = self.root / "runs"
        self.batches = self.root / "batches"
        self.calls = []
        which = shutil.which
        self.addCleanup(patch.stopall)
        patch.object(batch.shutil, "which", side_effect=lambda command, **kwargs:
                     sys.executable if command in ("opencode", "pi", "node") else which(command, **kwargs)).start()
        self.output = io.StringIO()
        context = redirect_stdout(self.output)
        context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def task(self, task_id, deps=(), program="develop"):
        (self.inputs / f"{task_id}.md").write_text(f"Task {task_id}\n", encoding="utf-8")
        result = {"id": task_id, "program": program, "task": f"{task_id}.md", "depends_on": list(deps)}
        if program == "develop":
            result["verify"] = list(VERIFY)
        return result

    def create(self, tasks=None, **options):
        if tasks is None:
            tasks = [self.task("first"), self.task("second", ["first"])]
        self.manifest.write_text(json.dumps({"name": "Bounded delivery", "tasks": tasks}), encoding="utf-8")
        return batch.create_batch(self.manifest, self.workspace, self.runs, self.batches, **options)

    def record_child(self, task, workspace, runs_dir, verify, *, state="accepted", **options):
        plan = {"goal": task, "work": VERIFY, "timeout_seconds": options.get("timeout", 900)}
        if verify is not None:
            plan["verify"] = verify
        run_dir = runtime.create_run(plan, workspace, runs_dir, run_id=options["run_id"])
        if state in ("accepted", "rejected", "awaiting_review"):
            runtime.record(run_dir, "run.finished", {"state": "awaiting_review"})
            if state != "awaiting_review":
                evidence = run_dir / "fixture-review.md"
                evidence.write_text("Test-authored review evidence, not a real model review.\n", encoding="utf-8")
                runtime.review_run(run_dir, "accept" if state == "accepted" else "reject", "test-fixture", evidence)
        elif state != "unfinished":
            runtime.record(run_dir, "run.finished", {"state": state})
        return run_dir, runtime.project(runtime.read_events(run_dir))

    def launch(self, task, workspace, runs_dir, verify, **options):
        # Every launch sees the complete frozen input, not a partially written plan.
        frozen = list(self.batches.glob("*/batch.json"))
        self.assertTrue(frozen)
        self.assertTrue(any(task in [entry["task_text"] for entry in json.loads(path.read_text())["tasks"]]
                            for path in frozen))
        self.calls.append({"task": task, "workspace": workspace, "runs_dir": runs_dir, "verify": verify, **options})
        return self.record_child(task, workspace, runs_dir, verify, **options)

    def seed(self, directory, task_id, state="accepted"):
        data = batch.load_batch(directory)
        task = next(task for task in data["tasks"] if task["id"] == task_id)
        row = next(row for row in batch.batch_status(directory)["tasks"] if row["id"] == task_id)
        return self.record_child(task["task_text"], self.workspace, self.runs, task.get("verify"),
                                 run_id=row["run_id"], state=state)[0]

    def test_stable_topological_order_and_dependencies(self):
        tasks = [self.task("c", ["b"]), self.task("independent"), self.task("a"),
                 self.task("b", ["a"]), self.task("last")]
        directory = self.create(tasks)
        self.assertEqual(batch.load_batch(directory)["order"], ["independent", "a", "b", "c", "last"])
        initial = batch.batch_status(directory)
        self.assertEqual(initial["state"], "ready")
        self.assertEqual(next(row for row in initial["tasks"] if row["id"] == "c")["disposition"], "blocked")
        with patch.object(development, "develop", side_effect=self.launch):
            result = batch.resume_batch(directory)
        self.assertEqual(result["state"], "complete")
        self.assertEqual([call["task"] for call in self.calls],
                          [f"Task {task_id}\n" for task_id in ("independent", "a", "b", "c", "last")])
        children = {row["id"]: row["run_dir"] for row in result["tasks"]}
        self.assertEqual(self.calls[2]["dependency_runs"], {"a": children["a"]})
        self.assertEqual(self.calls[3]["dependency_runs"], {"b": children["b"]})

    def test_preflight_rejects_entire_invalid_manifest_before_work(self):
        good = [self.task("first"), self.task("second", ["first"])]
        variants = {"empty": [], "too_many": [self.task(f"t{i}") for i in range(33)]}
        for name, field, value in (
            ("duplicate", "id", "first"), ("empty_id", "id", ""), ("id_type", "id", 5),
            ("missing_ref", "depends_on", ["unknown"]), ("dependency_type", "depends_on", "first"),
            ("self_cycle", "depends_on", ["second"]), ("program", "program", "planner"),
            ("missing_file", "task", "absent.md"), ("absolute_file", "task", str(self.inputs / "first.md")),
            ("shell_command", "verify", "python -m unittest"), ("empty_command", "verify", []),
            ("null_command", "verify", None), ("argument_type", "verify", [sys.executable, 1]),
            ("nul_argument", "verify", [sys.executable, "\0"]),
            ("missing_executable", "verify", ["noetic-test-nonexistent-executable"]),
        ):
            tasks = copy.deepcopy(good)
            tasks[1][field] = value
            variants[name] = tasks
        missing_verify = copy.deepcopy(good)
        del missing_verify[1]["verify"]
        variants["required_verify"] = missing_verify
        cycle = copy.deepcopy(good)
        cycle[0]["depends_on"] = ["second"]
        variants["cycle"] = cycle
        for name, tasks in variants.items():
            with self.subTest(name=name), patch.object(development, "develop") as launcher:
                with self.assertRaises((ValueError, OSError)):
                    self.create(tasks)
                launcher.assert_not_called()
                self.assertFalse(self.runs.exists())
                self.assertFalse(self.batches.exists())

    def test_preflight_options_empty_text_and_telos_files(self):
        tasks = [self.task("first"), self.task("second")]
        for options in ({"timeout": 0}, {"timeout": float("nan")}, {"client": "planner"},
                        {"model": ""}, {"telos_chain": "chain", "telos_source": self.root / "absent.mjs"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.create(tasks, **options)
            self.assertFalse(self.batches.exists())
        (self.inputs / "second.md").write_text(" \n")
        with self.assertRaises(ValueError):
            self.create(tasks)
        self.assertFalse(self.batches.exists())

    def test_nul_in_later_task_text_fails_before_any_child_or_batch(self):
        tasks = [self.task("first"), self.task("second", ["first"])]
        (self.inputs / "second.md").write_text("Invalid command argument\0text")
        with patch.object(development, "develop") as launcher, self.assertRaises(ValueError):
            self.create(tasks)
        launcher.assert_not_called()
        self.assertFalse(self.runs.exists())
        self.assertFalse(self.batches.exists())

    def test_documented_verifier_executes_after_json_decoding(self):
        document = (ROOT / "docs/batch-example.md").read_text(encoding="utf-8")
        example = json.loads(document.split("```json\n", 1)[1].split("```", 1)[0])
        command = example["tasks"][0]["verify"]
        artifact = self.workspace / "batch-artifact.txt"
        artifact.write_bytes(b"Hello from noetic.\n")
        self.assertEqual(subprocess.run(command, cwd=self.workspace, capture_output=True).returncode, 0)
        artifact.write_bytes(b"incorrect")
        self.assertEqual(subprocess.run(command, cwd=self.workspace, capture_output=True).returncode, 1)

    def test_preflight_checks_client_and_workspace_relative_executable(self):
        tasks = [self.task("first")]
        with patch.object(batch.shutil, "which", return_value=None), self.assertRaisesRegex(ValueError, "opencode"):
            self.create(tasks)
        self.assertFalse(self.batches.exists())
        checker = self.workspace / "check"
        checker.write_text("#!/bin/sh\nexit 0\n")
        checker.chmod(0o755)
        tasks[0]["verify"] = ["./check"]
        directory = self.create(tasks)
        self.assertEqual(batch.load_batch(directory)["tasks"][0]["verify"], ["./check"])

    def test_frozen_text_and_options_survive_manifest_and_environment_changes(self):
        tasks = [self.task("first", program="inquire"), self.task("second", ["first"])]
        (self.inputs / "first.md").write_bytes(b"Original inquiry\r\n")
        source = self.root / "telos.mjs"
        source.write_text("// Test fixture; never executed.\n")
        database = self.root / "goals.sqlite3"
        options = {"client": "pi", "model": "provider/worker", "review_model": "provider/reviewer", "timeout": 42,
                   "goal_ref": "user:vision", "telos_chain": "master", "telos_db": database, "telos_source": source}
        directory = self.create(tasks, **options)
        frozen = (directory / "batch.json").read_bytes()
        self.manifest.write_text("not JSON any more")
        (self.inputs / "first.md").unlink()
        (self.inputs / "second.md").write_text("Changed task, must not execute")
        with patch.dict(os.environ, {"NOETIC_TELOS_SOURCE": "/changed/source"}), \
                patch.object(development, "develop", side_effect=self.launch), \
                patch.object(batch.telos, "get_goal") as get_goal, \
                patch.object(batch.telos, "record_result") as record_result:
            result = batch.resume_batch(directory)
        self.assertEqual(result["state"], "complete")
        self.assertEqual([call["task"] for call in self.calls], ["Original inquiry\r\n", "Task second\n"])
        self.assertTrue(self.calls[0]["inquiry"])
        self.assertIsNone(self.calls[0]["verify"])
        self.assertFalse(self.calls[1]["inquiry"])
        self.assertEqual(self.calls[1]["verify"], VERIFY)
        for call in self.calls:
            for key, value in options.items():
                self.assertEqual(call[key], value)
            self.assertEqual(call["workspace"], self.workspace)
            self.assertEqual(call["runs_dir"], self.runs)
        get_goal.assert_not_called()
        record_result.assert_not_called()  # Only develop owns child Telos updates.
        self.assertEqual((directory / "batch.json").read_bytes(), frozen)

    def test_inquiry_can_request_verification(self):
        task = self.task("inspect", program="inquire")
        task["verify"] = VERIFY
        directory = self.create([task])
        with patch.object(development, "develop", side_effect=self.launch):
            self.assertEqual(batch.resume_batch(directory)["state"], "complete")
        self.assertEqual(self.calls[0]["verify"], VERIFY)
        self.assertTrue(self.calls[0]["inquiry"])

    def test_accepted_skip_across_fresh_process_and_complete_resume_has_zero_launches(self):
        directory = self.create()
        first = self.seed(directory, "first")
        before = (first / "events.sqlite3").read_bytes()
        code = textwrap.dedent("""
            import io, sys
            from contextlib import redirect_stdout
            from pathlib import Path
            from unittest.mock import patch
            from scripts import noetic_batch as batch, noetic_run as runtime
            directory = Path(sys.argv[1])
            def launch(task, workspace, runs_dir, verify, **options):
                assert task == 'Task second\\n', 'accepted first task was relaunched'
                run_dir = runtime.create_run({'goal': task, 'work': verify, 'verify': verify},
                                             workspace, runs_dir, run_id=options['run_id'])
                runtime.record(run_dir, 'run.finished', {'state': 'awaiting_review'})
                evidence = run_dir / 'fixture-review.md'
                evidence.write_text('Test-authored independent evidence fixture')
                runtime.review_run(run_dir, 'accept', 'test-fixture', evidence)
                return run_dir, {'state': 'accepted'}
            with patch.object(batch, 'preflight_execution'), patch.object(batch.development, 'develop', side_effect=launch) as launcher:
                with redirect_stdout(io.StringIO()):
                    result = batch.resume_batch(directory)
                assert result['state'] == 'complete'
                assert launcher.call_count == 1
        """)
        result = subprocess.run([sys.executable, "-c", code, str(directory)], cwd=ROOT,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((first / "events.sqlite3").read_bytes(), before)
        complete = textwrap.dedent("""
            import sys
            from unittest.mock import patch
            from scripts import noetic as cli, noetic_batch as batch
            with patch.object(batch.development, 'develop', side_effect=AssertionError('model invocation')) as launcher:
                with patch.object(batch, 'preflight_execution', side_effect=AssertionError('unneeded preflight')):
                    assert cli.main(['batch', 'resume', sys.argv[1]]) == 0
                launcher.assert_not_called()
        """)
        result = subprocess.run([sys.executable, "-c", complete, str(directory)], cwd=ROOT,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, "-m", "scripts.noetic", "batch", "status", str(directory), "--json"],
                                cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["state"], "complete")

    def test_existing_nonaccepted_children_are_held_and_preserved(self):
        for state in ("failed", "rejected", "awaiting_review", "unfinished", "interrupted", "timed_out",
                      "corrupt", "missing_journal"):
            with self.subTest(state=state):
                directory = self.create()
                row = batch.batch_status(directory)["tasks"][0]
                run_dir = Path(row["run_dir"])
                if state == "missing_journal":
                    run_dir.mkdir(parents=True)
                else:
                    self.seed(directory, "first", state="unfinished" if state == "corrupt" else state)
                    if state == "corrupt":
                        (run_dir / "events.sqlite3").write_bytes(b"broken journal")
                before = {path.name: path.read_bytes() for path in run_dir.iterdir()}
                with patch.object(development, "develop", side_effect=AssertionError("must not rerun")) as launcher:
                    result = batch.resume_batch(directory)
                launcher.assert_not_called()
                self.assertEqual(result["state"], "held")
                self.assertEqual(result["tasks"][0]["state"], state)
                self.assertEqual(result["tasks"][0]["disposition"], "needs_disposition")
                self.assertEqual(result["tasks"][1]["disposition"], "blocked")
                self.assertEqual({path.name: path.read_bytes() for path in run_dir.iterdir()}, before)

    def test_failure_stops_dependents_and_independent_tasks_ignoring_returned_success(self):
        directory = self.create([self.task("first"), self.task("second", ["first"]), self.task("independent")])
        def failed(*args, **kwargs):
            run_dir, _ = self.record_child(*args, **kwargs, state="failed")
            return run_dir, {"state": "accepted"}
        with patch.object(development, "develop", side_effect=failed) as launcher:
            result = batch.resume_batch(directory)
        self.assertEqual(launcher.call_count, 1)
        self.assertEqual(result["state"], "held")
        self.assertEqual([row["state"] for row in result["tasks"]], ["failed", "pending", "pending"])

    def test_interruption_after_child_creation_holds_on_resume(self):
        directory = self.create()
        def interrupted(*args, **kwargs):
            self.record_child(*args, **kwargs, state="unfinished")
            raise KeyboardInterrupt
        with patch.object(development, "develop", side_effect=interrupted), self.assertRaises(KeyboardInterrupt):
            batch.resume_batch(directory)
        with patch.object(development, "develop") as launcher:
            result = batch.resume_batch(directory)
        launcher.assert_not_called()
        self.assertEqual(result["state"], "held")
        self.assertEqual(result["tasks"][0]["state"], "unfinished")

    def test_no_child_journal_cannot_be_replaced_by_launcher_success(self):
        directory = self.create()
        with patch.object(development, "develop", return_value=(None, {"state": "accepted"})) as launcher:
            with self.assertRaisesRegex(ValueError, "without creating a child journal"):
                batch.resume_batch(directory)
        self.assertEqual(launcher.call_count, 1)
        self.assertEqual(batch.batch_status(directory)["state"], "ready")

    def test_accepted_state_requires_recorded_review_and_matching_child_identity(self):
        directory = self.create()
        first = self.seed(directory, "first", state="unfinished")
        runtime.record(first, "run.finished", {"state": "accepted"})
        self.assertEqual(batch.batch_status(directory)["tasks"][0]["state"], "corrupt")
        other = self.create()
        row = batch.batch_status(other)["tasks"][0]
        wrong = runtime.create_run({"goal": "Wrong task", "work": VERIFY}, self.workspace, self.runs, run_id=row["run_id"])
        self.assertTrue(wrong.exists())
        self.assertEqual(batch.batch_status(other)["tasks"][0]["state"], "corrupt")

    def test_journal_disposition_is_seen_without_editing_frozen_batch(self):
        directory = self.create()
        first = self.seed(directory, "first", state="awaiting_review")
        frozen = (directory / "batch.json").read_bytes()
        self.assertEqual(batch.resume_batch(directory)["state"], "held")
        evidence = first / "fixture-review.md"
        evidence.write_text("Test fixture: externally supplied review following evidence inspection.")
        runtime.review_run(first, "accept", "external-fixture", evidence)
        with patch.object(development, "develop", side_effect=self.launch):
            self.assertEqual(batch.resume_batch(directory)["state"], "complete")
        self.assertEqual([call["task"] for call in self.calls], ["Task second\n"])
        self.assertEqual((directory / "batch.json").read_bytes(), frozen)

    def test_telos_error_is_visible_and_never_relaunches_accepted_work(self):
        directory = self.create([self.task("first")])
        first = self.seed(directory, "first")
        runtime.record(first, "telos.error", {"error": "result not synchronized"})
        with patch.object(development, "develop") as launcher:
            result = batch.resume_batch(directory)
        launcher.assert_not_called()
        self.assertEqual(result["state"], "held")
        self.assertEqual(result["tasks"][0]["state"], "accepted")
        self.assertIn("Telos", result["tasks"][0]["reason"])

    def test_cooperative_lock_blocks_other_process_and_releases_without_stale_cleanup(self):
        import fcntl
        directory = self.create()
        with (directory / ".execution.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = subprocess.run([sys.executable, "-m", "scripts.noetic", "batch", "resume", str(directory)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 1)
            self.assertIn("already executing", result.stderr)
            self.assertFalse(self.runs.exists())
        with patch.object(development, "develop", side_effect=self.launch):
            self.assertEqual(batch.resume_batch(directory)["state"], "complete")
        self.assertTrue((directory / ".execution.lock").exists())

    def test_known_run_id_validation_before_mkdir_and_no_overwrite(self):
        for run_id in ("", "../outside", "g" * 32, "a" * 31, 42):
            with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                runtime.create_run({"goal": "fixture"}, self.workspace, self.runs, run_id=run_id)
            self.assertFalse(self.runs.exists())
        run_id = uuid.uuid4().hex
        run_dir = runtime.create_run({"goal": "fixture"}, self.workspace, self.runs, run_id=run_id)
        before = (run_dir / "events.sqlite3").read_bytes()
        with self.assertRaises(FileExistsError):
            runtime.create_run({"goal": "overwrite"}, self.workspace, self.runs, run_id=run_id)
        self.assertEqual((run_dir / "events.sqlite3").read_bytes(), before)
        default = runtime.create_run({"goal": "default"}, self.workspace, self.runs)
        self.assertNotEqual(default, run_dir)
        self.assertEqual(uuid.UUID(default.name).hex, default.name)

    def test_real_develop_protocol_children_use_deterministic_ids_and_common_discovery(self):
        directory = self.create([self.task("inspect", program="inquire"), self.task("change", ["inspect"])])
        roles = []
        def command(client, prompt, role, model, run_dir=None, workspace=None, context_dirs=()):
            roles.append(role)
            text = "ACCEPT\nTest-authored evidence fixture." if role == "reviewer" else "Test-authored work fixture."
            events = [
                {"type": "text", "sessionID": role, "part": {"id": "text", "messageID": "final", "text": text}},
                {"type": "step_finish", "sessionID": role, "part": {"messageID": "final", "reason": "stop"}},
            ]
            return [sys.executable, "-c", "print(" + repr("\n".join(json.dumps(event) for event in events)) + ")"], None
        with patch.object(development, "client_command", side_effect=command):
            result = batch.resume_batch(directory)
        self.assertEqual(result["state"], "complete")
        self.assertEqual(roles, ["inquirer", "reviewer", "worker", "reviewer"])
        discovered = {run["run_id"] for run in runtime.list_runs(self.runs)}
        for row in result["tasks"]:
            expected_id = uuid.uuid5(uuid.UUID(result["batch_id"]), row["id"]).hex
            self.assertEqual(row["run_id"], expected_id)
            self.assertIn(expected_id, discovered)
            run_dir = self.runs / expected_id
            self.assertEqual(Path(row["run_dir"]), run_dir)
            self.assertEqual(runtime.project(runtime.read_events(run_dir))["state"], "accepted")
        self.assertFalse(any(path.name == "runs" for path in directory.iterdir()))

    def test_public_cli_run_and_held_exit_codes(self):
        self.manifest.write_text(json.dumps({"name": "CLI", "tasks": [self.task("first")]}))
        with patch.object(development, "develop", side_effect=self.launch):
            code = cli.main(["batch", "run", str(self.manifest), "--workspace", str(self.workspace),
                             "--runs-dir", str(self.runs), "--batches-dir", str(self.batches),
                             "--client", "opencode", "--model", "provider/model"])
        self.assertEqual(code, 0)
        self.assertEqual(self.calls[0]["model"], "provider/model")
        held = self.create()
        self.seed(held, "first", state="failed")
        with patch.object(development, "develop") as launcher:
            self.assertEqual(cli.main(["batch", "resume", str(held)]), 1)
        launcher.assert_not_called()
        with redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["batch", "status", str(self.root / "absent")]), 1)


if __name__ == "__main__":
    unittest.main()
