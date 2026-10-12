"""Installed routing at actual command boundaries, without model calls."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.noetic_efforts import Efforts
from scripts.noetic_sessions import Registry


ROOT = Path(__file__).resolve().parents[2]


class ScopedCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.app = self.root / "application"
        self.state = self.root / "retained-state"
        self.cwd = self.root / "caller"
        self.cwd.mkdir()
        self.environment = {key: value for key, value in os.environ.items()
                            if key not in ("USER_PROVIDED_PASSWORD", "NOETIC_APP_HOME", "NOETIC_STATE_HOME")}
        self.environment.update(NOETIC_APP_HOME=str(self.app), NOETIC_STATE_HOME=str(self.state),
                                PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")

    def call(self, *arguments):
        return subprocess.run([sys.executable, "-m", "scripts.noetic", *arguments], cwd=self.cwd,
                              env=self.environment, capture_output=True, text=True, timeout=20)

    def fixture(self, namespace, runs):
        efforts = Efforts(runs, namespace_path=namespace)
        first = efforts.create({"intent": "First distinct intention", "environment": {"cwd": str(self.cwd)}})
        efforts.create({"intent": "Second distinct intention", "environment": {"cwd": str(self.cwd)}})
        Registry(runs, namespace_path=namespace)
        return first["ordinal"], efforts.store().namespace

    def test_new_command_help_does_not_create_installed_state(self):
        for command in ("disciplines", "purposes", "recall"):
            with self.subTest(command=command):
                result = self.call(command, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)
        self.assertFalse(self.app.exists())
        self.assertFalse(self.state.exists())

    def test_recall_uses_installed_namespace_and_retained_runs_from_another_cwd(self):
        namespace = self.app / "state" / "ordinals.sqlite3"
        ordinal, identity = self.fixture(namespace, self.state / "runs")
        before = hashlib.sha256(namespace.read_bytes()).hexdigest()
        result = self.call("recall", "--scope", "effort", "--effort-root", ordinal)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = json.loads(result.stdout)
        self.assertEqual(data["identity"]["namespace"]["id"], identity)
        self.assertEqual(data["identity"]["runs_dir"], str(self.state / "runs"))
        self.assertEqual(data["identity"]["sessions_home"], str(self.state / "runs"))
        self.assertTrue(data["sources"])
        self.assertEqual(hashlib.sha256(namespace.read_bytes()).hexdigest(), before)
        self.assertFalse((self.cwd / ".runtime").exists())

    def test_explicit_namespace_and_runs_override_each_installed_default(self):
        namespace, runs = self.root / "explicit.sqlite3", self.root / "explicit-runs"
        ordinal, identity = self.fixture(namespace, runs)
        result = self.call("recall", "--namespace-path=" + str(namespace), "--runs-dir", str(runs),
                           "--scope", "effort", "--effort-root", ordinal)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = json.loads(result.stdout)
        self.assertEqual(data["identity"]["namespace"]["id"], identity)
        self.assertEqual(data["identity"]["runs_dir"], str(runs))
        self.assertEqual(data["identity"]["sessions_home"], str(runs))
        self.assertFalse(self.app.exists())
        self.assertFalse(self.state.exists())

    def test_harness_start_uses_retained_state_and_preserves_explicit_override(self):
        task = self.root / "task.md"
        task.write_text("Investigate a bounded question without starting an actor.")
        for runs, override in ((self.state / "runs", ()),
                               (self.root / "explicit-runs", ("--runs-dir=" + str(self.root / "explicit-runs"),))):
            with self.subTest(runs=runs):
                result = self.call("harness", "start", "cognition", str(task), "--workspace", str(self.cwd),
                                   "--max-activations", "0", *override)
                self.assertEqual(result.returncode, 2, result.stderr)
                run = next(path for path in runs.iterdir() if (path / "controller.sqlite3").is_file())
                stopped = self.call("harness", "cancel", str(run))
                self.assertEqual(stopped.returncode, 0, stopped.stderr)
        self.assertFalse((self.cwd / ".runtime").exists())

    def test_harness_default_stays_outside_verifier_arguments(self):
        task = self.root / "task.md"
        task.write_text("Retain a verification command without executing it.")
        for label, verify, override in (
            ("plain", [sys.executable, "-c", "pass"], ()),
            ("equals", [sys.executable], ()),
            ("verifier-option", [sys.executable, "-c", "pass", "--runs-dir", "verifier-output"], ()),
            ("explicit", [sys.executable, "-c", "pass", "--runs-dir=verifier-output"],
             ("--runs-dir=" + str(self.root / "explicit-runs"),)),
        ):
            with self.subTest(label=label):
                runs = self.root / "explicit-runs" if override else self.state / "runs"
                prior = set(runs.iterdir()) if runs.exists() else set()
                verification = (["--verify=" + verify[0], *verify[1:]] if label == "equals" else ["--verify", *verify])
                result = self.call("harness", "start", "cognition", str(task), "--workspace", str(self.cwd),
                                   "--max-activations", "0", *override, *verification)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertTrue(runs.is_dir(), result.stdout + result.stderr)
                created = [path for path in runs.iterdir() if path not in prior and (path / "controller.sqlite3").is_file()]
                self.assertEqual(len(created), 1)
                self.assertEqual(json.loads((created[0] / "options.json").read_text())["verify"], verify)
                self.assertEqual(self.call("harness", "cancel", str(created[0])).returncode, 0)
        self.assertFalse((self.cwd / ".runtime").exists())


if __name__ == "__main__":
    unittest.main()
