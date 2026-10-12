"""Implementation checks using actual temporary Git indexes, without commits or models."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import noetic_changes as changes


class ChangesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "workspace"
        self.repo.mkdir()
        self.run_dir = self.root / "run"
        self.run_dir.mkdir()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True).stdout

    def retain(self, baseline):
        changes.retain_changes(self.repo, self.run_dir, baseline)
        return json.loads((self.run_dir / "changes.json").read_text()), (self.run_dir / "changes.diff").read_text()

    def test_dirty_work_is_baseline_and_git_is_unchanged(self):
        self.git("init")
        (self.repo / ".gitignore").write_text(".runtime/\nnode_modules/\n")
        (self.repo / "modified.txt").write_text("indexed\n")
        (self.repo / "deleted.txt").write_text("delete me\n")
        self.git("add", ".")
        (self.repo / "modified.txt").write_text("preexisting dirty\n")
        (self.repo / "untracked.txt").write_text("preexisting untracked\n")
        (self.repo / "missing.txt").write_text("already gone")
        self.git("add", "missing.txt")
        (self.repo / "missing.txt").unlink()
        for directory in (".runtime", "node_modules"):
            (self.repo / directory).mkdir()
            (self.repo / directory / "ignored.txt").write_text("before")
        index = (self.repo / ".git/index").read_bytes()
        baseline = changes.snapshot(self.repo)
        self.assertEqual((self.repo / "modified.txt").read_text(), "preexisting dirty\n")
        (self.repo / "modified.txt").write_text("after\n")
        (self.repo / "deleted.txt").unlink()
        (self.repo / "added.txt").write_text("new file")
        for directory in (".runtime", "node_modules"):
            (self.repo / directory / "ignored.txt").write_text("after")
        manifest, diff = self.retain(baseline)
        self.assertEqual(manifest["status"], "available")
        entries = {entry["path"]: entry for entry in manifest["changes"]}
        self.assertEqual({name: entry["status"] for name, entry in entries.items()},
                         {"added.txt": "added", "deleted.txt": "deleted", "modified.txt": "modified"})
        self.assertEqual(entries["modified.txt"]["before"]["sha256"], hashlib.sha256(b"preexisting dirty\n").hexdigest())
        self.assertEqual(entries["modified.txt"]["after"]["sha256"], hashlib.sha256(b"after\n").hexdigest())
        self.assertIsNone(entries["added.txt"]["before"])
        self.assertIsNone(entries["deleted.txt"]["after"])
        self.assertIn("-preexisting dirty\n+after\n", diff)
        self.assertNotIn("indexed", diff)
        self.assertIn("-delete me", diff)
        self.assertIn("+new file\n\\ No newline at end of file", diff)
        self.assertEqual((self.repo / ".git/index").read_bytes(), index)
        self.assertEqual((self.repo / "untracked.txt").read_text(), "preexisting untracked\n")

    def test_binary_large_and_symlink_contents(self):
        self.git("init")
        baseline = changes.snapshot(self.repo)
        (self.repo / "binary").write_bytes(b"\0binary")
        (self.repo / "large").write_bytes(b"x" * (changes.TEXT_LIMIT + 1))
        (self.repo / "link").symlink_to("missing-target")
        manifest, diff = self.retain(baseline)
        entries = {entry["path"]: entry for entry in manifest["changes"]}
        for name in ("binary", "large"):
            self.assertTrue(entries[name]["diff_omission_reason"])
            self.assertIn(f'# Omitted "{name}"', diff)
            self.assertEqual(entries[name]["after"]["sha256"], hashlib.sha256((self.repo / name).read_bytes()).hexdigest())
        self.assertEqual(entries["link"]["after"]["kind"], "symlink")
        self.assertIn("+missing-target", diff)

    def test_non_git_and_failed_snapshot_are_not_no_changes(self):
        for baseline in (changes.snapshot(self.repo), {"files": None, "reason": "Read failed"}):
            manifest, diff = self.retain(baseline)
            self.assertEqual(manifest["status"], "unavailable")
            self.assertIsNone(manifest["changes"])
            self.assertIn("Unavailable evidence", diff)
            self.assertNotIn("No changes observed", diff)
        with patch.object(changes.subprocess, "run", side_effect=FileNotFoundError("git missing")):
            self.assertIsNone(changes.snapshot(self.repo)["files"])

    def test_no_changes_and_new_ignore_rule(self):
        self.git("init")
        (self.repo / "existing").write_text("before")
        baseline = changes.snapshot(self.repo)
        manifest, diff = self.retain(baseline)
        self.assertEqual(manifest["changes"], [])
        self.assertIn("No changes observed", diff)
        (self.repo / ".gitignore").write_text("existing\n")
        (self.repo / "existing").write_text("after")
        manifest, _ = self.retain(baseline)
        self.assertEqual({entry["path"]: entry["status"] for entry in manifest["changes"]},
                         {".gitignore": "added", "existing": "modified"})


if __name__ == "__main__":
    unittest.main()
