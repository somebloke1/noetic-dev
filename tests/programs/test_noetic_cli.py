"""Public entrypoint smoke tests; no configured models or network required."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class NoeticCliTests(unittest.TestCase):
    def call(self, *args):
        return subprocess.run([sys.executable, "-m", "scripts.noetic", *args], cwd=ROOT,
                              capture_output=True, text=True, timeout=15,
                              env={key:value for key,value in os.environ.items() if key != "USER_PROVIDED_PASSWORD"})

    def test_top_level_and_every_command_help(self):
        for command in ((), ("sessions",), ("release",), ("archive",), ("storage",), ("local",), ("semantic",), ("harness",), ("harness", "start"), ("harness", "advance"),
                        ("harness", "inspect"), ("harness", "cancel"), ("batch",),
                        ("run",), ("develop",), ("inquire",), ("goal",), ("list",), ("status",),
                        ("events",), ("review",), ("search",), ("index",), ("serve",), ("open",)):
            with self.subTest(command=command):
                result = self.call(*command, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)

    def test_version_and_local_capability_report(self):
        self.assertEqual(self.call("--version").stdout.strip(), "noetic-dev 0.3.0")
        result = self.call("doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertIn("sqlite_fts5", report)
        self.assertEqual(set(report["clients"]), {"opencode", "pi"})
        self.assertEqual(report["model_access"], "not probed; use a configured client model")

    def test_harness_delegates_real_controller_checkpoint_inspect_cancel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = root / "task.md"
            task.write_text("Investigate a bounded question")
            result = self.call("harness", "start", "cognition", str(task), "--workspace", str(root),
                               "--runs-dir", str(root / "runs"), "--max-activations", "0")
            self.assertEqual(result.returncode, 2, result.stderr)
            run = next((root / "runs").iterdir())
            state = json.loads(self.call("harness", "inspect", str(run), "--json").stdout)
            self.assertEqual(state["status"], "active")
            self.assertEqual(state["pattern"]["kind"], "recurrent_operations")
            self.assertEqual(self.call("harness", "cancel", str(run)).returncode, 0)
            self.assertEqual(self.call("harness", "advance", str(run)).returncode, 1)
        self.assertIn("Legacy task utilities", " ".join(self.call("--help").stdout.split()))

    def test_session_router_preserves_explicit_effort_and_exact_context(self):
        from tests.programs.test_noetic_sessions import SessionTests
        fixture = SessionTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        runs, namespace = str(fixture.runs), str(fixture.runs / "ordinals.sqlite3")
        def call(*args):
            return self.call("sessions", *args, "--runs-dir", runs, "--namespace-path", namespace)
        registered = call("register-effort", "--workspace", str(fixture.workspace), "--intent", "CLI effort")
        self.assertEqual(registered.returncode, 0, registered.stderr)
        effort = json.loads(registered.stdout)["ordinal"]
        first = fixture.create(effort_root=effort)
        fixture.wait(first["id"])
        selectors = (effort, "--effort-root", effort, "--instantiation", "1", "--session", "1")
        shown = call("show", *selectors, "--limit", "500")
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertEqual(json.loads(shown.stdout)["session"]["target"], first["target"])
        prompt = call("prompt", *selectors, "CLI exact message")
        self.assertEqual(prompt.returncode, 0, prompt.stderr)
        fixture.wait(first["id"])
        self.assertIn("CLI exact message", str(fixture.records(first["id"])))
        second = fixture.create(effort_root=effort)
        fixture.wait(second["id"])
        rejected = call("prompt", *selectors, "Do not redirect")
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("superseded", rejected.stderr)
        self.assertNotIn("Do not redirect", str(fixture.records(second["id"])))
        history = call("history", "0", "--limit", "2")
        self.assertEqual(history.returncode, 0, history.stderr)
        page = json.loads(history.stdout)
        self.assertEqual(len(page["records"]), 2)
        continued = call("history", "0", "--limit", "2", "--after", str(page["next_after"]))
        self.assertGreater(json.loads(continued.stdout)["records"][0]["sequence"], page["next_after"])

    def test_repository_validator_does_not_treat_runtime_reports_as_source(self):
        local = ROOT / ".runtime"
        local.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=local) as directory:
            Path(directory, "report.md").write_text("User evidence [an absent file](not-present.txt)  \n")
            result = subprocess.run([sys.executable, "scripts/validate_repo.py"], cwd=ROOT,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
