"""Bounded implementation tests; the separate independent QA pass follows."""

from contextlib import closing, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import noetic_application as application
from scripts import noetic_harness as harness
from scripts import noetic_local as local
from scripts import noetic_semantic as semantic
from scripts import noetic_storage as storage
from scripts import noetic_telos as telos


class PrivateStorageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        previous = os.umask(0o022)
        self.addCleanup(os.umask, previous)

    def mode(self, path):
        return stat.S_IMODE(path.stat().st_mode)

    def assert_private(self, root):
        for path in (root, *root.rglob("*")):
            self.assertEqual(self.mode(path), 0o700 if path.is_dir() else 0o600, str(path))

    def test_creation_modes_and_umask(self):
        for mask in (0o022, 0o002):
            os.umask(mask)
            parent = self.root / str(mask)
            parent.mkdir(mode=0o755)
            original = self.mode(parent)
            state = storage.ensure_private_directory(parent / "state/nested")
            with storage.open_private(state / "text") as stream:
                stream.write("private text")
            with storage.open_private(state / "binary", "wb") as stream:
                stream.write(b"private bytes")
            with self.assertRaises(RuntimeError):
                with storage.open_private(state / "exception") as stream:
                    raise RuntimeError("fixture")
            self.assertTrue(stream.closed)
            self.assert_private(parent / "state")
            self.assertEqual(self.mode(parent), original)
            self.assertEqual(os.umask(mask), mask)

    def test_sqlite_journal_wal_and_reopen(self):
        db = self.root / "state/db.sqlite3"
        self.assertEqual(storage.create_private_sqlite(db), db)
        with closing(sqlite3.connect(db)) as connection:
            connection.execute("CREATE TABLE private (text)")
            connection.execute("INSERT INTO private VALUES ('unchanged')")
            self.assertEqual(self.mode(Path(str(db) + "-journal")), 0o600)
            connection.commit()
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("INSERT INTO private VALUES ('second')")
            for suffix in ("-wal", "-shm"):
                self.assertEqual(self.mode(Path(str(db) + suffix)), 0o600)
            connection.commit()
        before = db.read_bytes()
        storage.create_private_sqlite(db)
        self.assertEqual(db.read_bytes(), before)
        with closing(sqlite3.connect(db)) as connection:
            self.assertEqual(connection.execute("SELECT text FROM private").fetchall(), [("unchanged",), ("second",)])
        db.chmod(0o644)
        with self.assertWarnsRegex(RuntimeWarning, "explicitly protect"):
            storage.create_private_sqlite(db)
        self.assertEqual(self.mode(db), 0o644)

    def test_legacy_inspect_then_explicit_protect(self):
        state = self.root / "state"
        state.mkdir()
        data = state / "task.md"
        data.write_bytes(b"private legacy text\n")
        executable = state / "owned-driver"
        executable.write_bytes(b"#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
        digest = hashlib.sha256(data.read_bytes()).hexdigest()
        before = storage.inspect_tree(state)
        self.assertEqual((before["files"], before["directories"], before["needs_protection"]), (2, 1, 3))
        self.assertEqual(self.mode(data), 0o644)
        self.assertEqual(before["sha256"]["task.md"], digest)
        result = storage.protect_tree(state)
        self.assertTrue(result["content_preserved"])
        self.assertEqual(result["before"]["bytes"], result["after"]["bytes"])
        self.assertEqual(result["changed"], 3)
        self.assertEqual(self.mode(executable), 0o700)
        self.assertEqual(self.mode(data), 0o600)
        self.assertEqual(storage.protect_tree(state)["changed"], 0)

    def test_links_and_foreign_ownership_declined(self):
        outside = self.root / "outside"
        outside.mkdir()
        target = outside / "data"
        target.write_text("untouched")
        state = storage.ensure_private_directory(self.root / "state")
        (state / "link").symlink_to(outside, target_is_directory=True)
        (state / "file-link").symlink_to(target)
        for path in (state / "file-link", state / "link/data"):
            with self.assertRaises((OSError, ValueError)):
                storage.open_private(path)
        with self.assertRaises((OSError, ValueError)):
            storage.create_private_sqlite(state / "file-link")
        result = storage.protect_tree(state)
        self.assertEqual(len(result["after"]["skipped"]), 2)
        self.assertEqual(target.read_text(), "untouched")
        self.assertEqual(self.mode(target), 0o644)
        with self.assertRaises(OSError):
            storage.protect_tree(state / "link")
        # Exercise the UID refusal without requiring sudo or a second OS account.
        with patch.object(storage.os, "geteuid", return_value=os.geteuid() + 1):
            with self.assertRaises(PermissionError):
                storage.open_private(target)
            with self.assertRaises(PermissionError):
                storage.protect_tree(state)
        self.assertEqual(target.read_text(), "untouched")

    def test_foreign_entry_skipped_without_modification(self):
        state = storage.ensure_private_directory(self.root / "state")
        foreign = state / "foreign"
        foreign.write_text("unchanged foreign fixture")
        original_stat = os.stat

        def foreign_stat(path, *args, **kwargs):
            result = original_stat(path, *args, **kwargs)
            if path == "foreign":
                values = list(result)
                values[4] = os.geteuid() + 1
                return os.stat_result(values)
            return result

        with patch.object(storage.os, "stat", side_effect=foreign_stat):
            result = storage.protect_tree(state)
        self.assertEqual(result["after"]["skipped"], [{"path": "foreign", "reason": "foreign owner"}])
        self.assertEqual(foreign.read_text(), "unchanged foreign fixture")
        self.assertEqual(self.mode(foreign), 0o644)

    def test_semantic_cache_creation_without_inference(self):
        runs = storage.ensure_private_directory(self.root / "state/runs")
        db = runs / ".semantic.sqlite3"
        with redirect_stdout(io.StringIO()):
            result = semantic.main(["index", "--runs-dir", str(runs)])
        self.assertEqual(result, 0)
        with closing(sqlite3.connect(db)) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM semantic_vectors").fetchone(), (0,))
        self.assert_private(self.root / "state")

    def test_hardlinks_and_workspace_migration_declined(self):
        state = storage.ensure_private_directory(self.root / "state")
        source = self.root / "source.py"
        source.write_text("unchanged")
        os.link(source, state / "hardlink")
        with self.assertRaises(ValueError):
            storage.open_private(state / "hardlink")
        self.assertEqual(len(storage.protect_tree(state)["after"]["skipped"]), 1)
        self.assertEqual(self.mode(source), 0o644)
        (self.root / ".git").mkdir()
        with self.assertRaises(ValueError):
            storage.protect_tree(self.root)
        with self.assertRaises(ValueError):
            storage.protect_tree(Path.home())

    def test_cli_reports(self):
        state = self.root / "state"
        state.mkdir()
        (state / "legacy").write_text("retained")
        for command, expected in (("inspect", 1), ("protect", 0), ("inspect", 0)):
            result = subprocess.run([sys.executable, "-B", "-m", "scripts.noetic_storage", command, str(state)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, expected, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report.get("content_preserved", True))

    def test_harness_application_and_summary_without_models(self):
        workspace = self.root / "workspace"
        workspace.mkdir()
        source = workspace / "source.py"
        source.write_text("# untouched source\n")
        source.chmod(0o755)
        before = (source.read_bytes(), self.mode(source), self.mode(workspace))
        with redirect_stdout(io.StringIO()):
            run, state = harness.start("cognition", "private task", workspace, self.root / "state/runs",
                                       max_activations=0)
        self.assertEqual(state["status"], "active")
        app = application.Application(run.parent)
        with app.mutation():
            application.write_driver(run, {"status": "held"})
        # Exercise real launch-file creation without starting a driver/model.
        child = Mock(pid=123)
        child.poll.return_value = None
        with patch.object(application.subprocess, "Popen", return_value=child), harness.driver_slot(run.parent) as slot:
            app._launch(run, state, 0, slot)
        directory = storage.ensure_private_directory(run / "activations/fixture")
        harness._write_text(directory / "prompt.txt", "private prompt")
        observation = harness._execute(run, directory, workspace, "actor",
                                       [sys.executable, "-c", "print('synthetic transcript')"], 5)
        self.assertEqual(observation["state"], "passed")
        client = Mock()
        client.settings.text_model = "test-only"
        client.complete.return_value = {"text": "Synthetic summary"}
        summary = local.summarize_run(run, client, save=True)
        self.assertTrue(summary["saved"])
        harness.pause(run)
        self.assert_private(self.root / "state")
        self.assertEqual((source.read_bytes(), self.mode(source), self.mode(workspace)), before)
        self.assertEqual(os.umask(0o022), 0o022)

    def test_native_telos_private_creation(self):
        source = telos.source_path()
        if not shutil.which("node") or not (source / "node_modules/tsx/dist/loader.mjs").is_file():
            self.skipTest("Native Telos/Node unavailable")
        version = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=10)
        if int(version.stdout.strip().lstrip("v").split(".")[0]) < 24:
            self.skipTest("Native Telos requires Node 24")
        db = self.root / "state/telos.sqlite3"
        goal = telos.create_goal("Synthetic private purpose", db, source)
        goals = telos.list_goals(db, source)
        self.assertEqual(goals[0]["chain"]["chainId"], goal["chain"]["chainId"])
        self.assert_private(db.parent)


if __name__ == "__main__":
    unittest.main()
