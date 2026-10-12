"""Real-process tests of the live goal-directed workflow, not fixture replay."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from scripts import noetic_run as runtime


SCRIPT = Path(runtime.__file__).resolve()


class LiveRunTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.runs = self.root / "runs"
        self.plan = {
            "goal": "Create an artifact and verify its actual contents",
            "goal_ref": "chain/example",
            "work": [sys.executable, "-c", "from pathlib import Path; Path('answer.txt').write_text('42'); print('created')"],
            "verify": [sys.executable, "-c", "from pathlib import Path; assert Path('answer.txt').read_text() == '42'; print('verified')"],
            "timeout_seconds": 10,
        }

    def run_plan(self, **changes):
        with redirect_stdout(io.StringIO()):
            return runtime.run_plan({**self.plan, **changes}, self.workspace, self.runs)

    def cli(self, *argv):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, argv)], capture_output=True, text=True, timeout=20)

    def test_actual_work_verification_restart_and_independent_review(self):
        run_dir, result = self.run_plan()
        self.assertEqual((self.workspace / "answer.txt").read_text(), "42")
        self.assertEqual(result["state"], "awaiting_review")
        self.assertIsNone(result["review"])
        self.assertEqual((run_dir / "work.stdout.log").read_text(), "created\n")
        self.assertEqual((run_dir / "verify.stdout.log").read_text(), "verified\n")
        restarted = self.cli("status", run_dir, "--json")
        self.assertEqual(restarted.returncode, 0, restarted.stderr)
        self.assertEqual(json.loads(restarted.stdout), result)
        events = runtime.read_events(run_dir)
        self.assertEqual([e["kind"] for e in events], [
            "run.created", "step.started", "step.finished", "step.started", "step.finished", "run.finished",
        ])
        self.assertEqual([e["sequence"] for e in events], list(range(1, 7)))
        evidence = self.root / "review.txt"
        evidence.write_text("Separate reviewer inspected answer.txt and the verification result: correct.")
        reviewed = self.cli("review", run_dir, "--verdict", "accept", "--reviewer", "independent-reviewer", "--evidence", evidence)
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        evidence.unlink()
        accepted = runtime.project(runtime.read_events(run_dir))
        self.assertEqual(accepted["state"], "accepted")
        self.assertIn("Separate reviewer", accepted["review"]["evidence"])

    def test_failures_do_not_advance_and_cannot_be_approved(self):
        for stage in ("work", "verify"):
            with self.subTest(stage=stage):
                run_dir, result = self.run_plan(**{stage: [sys.executable, "-c", "import sys; print('broken', file=sys.stderr); sys.exit(7)"]})
                self.assertEqual(result["state"], "failed")
                self.assertEqual(result["steps"][stage]["returncode"], 7)
                self.assertEqual((run_dir / f"{stage}.stderr.log").read_text(), "broken\n")
                if stage == "work":
                    self.assertNotIn("verify", result["steps"])
                evidence = self.root / "review.txt"
                evidence.write_text("Cannot turn a failed run into an accepted run")
                with self.assertRaisesRegex(ValueError, "awaiting_review"):
                    runtime.review_run(run_dir, "accept", "reviewer", evidence)

    def test_missing_command_and_timeout_are_recorded(self):
        run_dir, result = self.run_plan(work=[str(self.root / "absent-command")])
        self.assertEqual(result["state"], "failed")
        self.assertIsNone(result["steps"]["work"]["returncode"])
        self.assertTrue(result["steps"]["work"]["error"])
        run_dir, result = self.run_plan(work=[sys.executable, "-c", "import time; time.sleep(30)"], timeout_seconds=0.1)
        self.assertEqual(result["state"], "timed_out")
        self.assertNotIn("verify", result["steps"])

    def test_review_is_terminal_and_rejection_is_not_success(self):
        run_dir, _ = self.run_plan()
        evidence = self.root / "review.txt"
        evidence.write_text("")
        with self.assertRaisesRegex(ValueError, "empty"):
            runtime.review_run(run_dir, "accept", "reviewer", evidence)
        evidence.write_text("The requested outcome needs a different artifact.")
        rejected = runtime.review_run(run_dir, "reject", "reviewer", evidence)
        self.assertEqual(rejected["state"], "rejected")
        before = runtime.read_events(run_dir)
        with self.assertRaisesRegex(ValueError, "awaiting_review"):
            runtime.review_run(run_dir, "accept", "reviewer", evidence)
        self.assertEqual(runtime.read_events(run_dir), before)

    def test_invalid_plan_has_no_execution_and_run_ids_do_not_collide(self):
        for changes in ({"verify": []}, {"work": "echo hello"}, {"goal": " "}, {"timeout_seconds": True}, {"timeout_seconds": float("inf")}, {"extra": 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.run_plan(**changes)
        self.assertFalse(self.runs.exists())
        first, _ = self.run_plan()
        second, _ = self.run_plan()
        self.assertNotEqual(first, second)

    def test_cli_run_failure_and_event_export(self):
        path = self.root / "plan.json"
        path.write_text(json.dumps({**self.plan, "verify": [sys.executable, "-c", "raise SystemExit(3)"]}))
        result = self.cli("run", path, "--workspace", self.workspace, "--runs-dir", self.runs)
        self.assertEqual(result.returncode, 1, result.stderr)
        run_dir = next(self.runs.iterdir())
        exported = self.cli("events", run_dir)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        self.assertEqual([json.loads(line) for line in exported.stdout.splitlines()], runtime.read_events(run_dir))
        absent = self.root / "not-a-run"
        failed = self.cli("status", absent)
        self.assertEqual(failed.returncode, 1)
        self.assertFalse(absent.exists())
        self.assertNotIn("Traceback", failed.stderr)

    @unittest.skipUnless(os.name == "posix", "POSIX process-group cancellation")
    def test_interrupt_is_recorded_and_no_verification_runs(self):
        path = self.root / "plan.json"
        path.write_text(json.dumps({**self.plan, "work": [sys.executable, "-c", "import time; time.sleep(30)"]}))
        process = subprocess.Popen(
            [sys.executable, str(SCRIPT), "run", str(path), "--workspace", str(self.workspace), "--runs-dir", str(self.runs)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 10
            run_dir = None
            while time.monotonic() < deadline:
                candidates = list(self.runs.iterdir()) if self.runs.exists() else []
                if candidates:
                    run_dir = candidates[0]
                    try:
                        if any(e["kind"] == "step.started" for e in runtime.read_events(run_dir)):
                            break
                    except sqlite3.Error:
                        pass
                time.sleep(0.02)
            else:
                self.fail("runner did not start a child")
            process.send_signal(signal.SIGTERM)
            _, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 1, stderr.decode())
            result = runtime.project(runtime.read_events(run_dir))
            self.assertEqual(result["state"], "interrupted")
            self.assertNotIn("verify", result["steps"])
            pid = next(e["data"]["pid"] for e in runtime.read_events(run_dir) if e["kind"] == "step.started")
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_list_after_restart_shows_newest_first_and_current_state(self):
        older, _ = self.run_plan(goal="Older run")
        with redirect_stdout(io.StringIO()):
            newer = runtime.create_run(self.plan, self.workspace, self.runs)
        # A later review must not change creation order.
        for run_dir, at in ((older, "2026-01-01T00:00:00+00:00"), (newer, "2026-01-02T00:00:00+00:00")):
            with sqlite3.connect(run_dir / "events.sqlite3") as connection:
                connection.execute("UPDATE events SET occurred_at = ? WHERE sequence = 1", (at,))
        evidence = self.root / "review.txt"
        evidence.write_text("Separate review accepts the artifact.")
        runtime.review_run(older, "accept", "reviewer", evidence)
        expected = [
            {"run_id": newer.name, "goal": self.plan["goal"], "state": "unfinished", "directory": str(newer)},
            {"run_id": older.name, "goal": "Older run", "state": "accepted", "directory": str(older)},
        ]
        result = self.cli("list", "--runs-dir", self.runs, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout), expected)
        text = self.cli("list", "--runs-dir", self.runs)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertLess(text.stdout.index(newer.name), text.stdout.index(older.name))
        for summary in expected:
            for value in summary.values():
                self.assertIn(value, text.stdout)

    def test_list_missing_and_empty_directory_does_not_create_records(self):
        for exists in (False, True):
            if exists:
                self.runs.mkdir()
            for options in ((), ("--json",)):
                with self.subTest(exists=exists, options=options):
                    result = self.cli("list", "--runs-dir", self.runs, *options)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stderr, "")
                    self.assertEqual(result.stdout.strip(), "[]" if options else "")
                    self.assertEqual(self.runs.exists(), exists)
            if exists:
                self.assertEqual(list(self.runs.iterdir()), [])

    def test_list_ignores_non_runs_and_continues_after_damaged_journals(self):
        valid, _ = self.run_plan()
        (self.runs / "notes.txt").write_text("not a run")
        (self.runs / "unrelated").mkdir()
        damaged = self.runs / "damaged"
        damaged.mkdir()
        (damaged / "events.sqlite3").write_text("not a SQLite database")
        with redirect_stdout(io.StringIO()):
            malformed = runtime.create_run(self.plan, self.workspace, self.runs)
        with sqlite3.connect(malformed / "events.sqlite3") as connection:
            connection.execute("UPDATE events SET data = '{}' WHERE sequence = 1")
        result = self.cli("list", "--runs-dir", self.runs, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([run["run_id"] for run in json.loads(result.stdout)], [valid.name])
        self.assertIn(str(damaged), result.stderr)
        self.assertIn(str(malformed), result.stderr)
        self.assertEqual(len(result.stderr.splitlines()), 2)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse((self.runs / "unrelated" / "events.sqlite3").exists())

    def test_unfinished_is_never_reported_as_accepted(self):
        run_dir, _ = self.run_plan()
        events = runtime.read_events(run_dir)
        for length in range(1, len(events)):
            with self.subTest(length=length):
                self.assertEqual(runtime.project(events[:length])["state"], "unfinished")


if __name__ == "__main__":
    unittest.main()
