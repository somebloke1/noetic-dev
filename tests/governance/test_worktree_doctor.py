"""Adversarial tests for read-only Git worktree validation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

from check_worktree import inspect_worktree, isolated_git_environment

REPO_ROOT = Path(__file__).resolve().parents[2]


def write_config(path: Path, extra: str = "") -> None:
    path.write_text(
        "[core]\n\trepositoryformatversion = 0\n\tbare = false\n" + extra,
        encoding="utf-8",
    )


class TestWorktreeDoctor(unittest.TestCase):
    def test_accepts_normal_main_and_standalone_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / ".git").mkdir(parents=True)
            write_config(repo / ".git" / "config")
            result = inspect_worktree(repo)
        self.assertEqual(result["status"], "pass", result["errors"])

    def test_rejects_common_worktree_fixture_identity_and_executable_filter(self):
        attacks = [
            "\tworktree = /tmp/candidate\n",
            "[user]\n\tname = Test User\n",
            "[user]\n\temail = test@example.invalid\n",
            "[filter \"hostile\"]\n\tsmudge = /tmp/hostile.sh\n",
            "[core]\n\tfsmonitor = /tmp/hostile.sh\n",
            "[alias]\n\thostile = !/tmp/hostile.sh\n",
            "[credential]\n\thelper = !/tmp/hostile.sh\n",
            "[tar \"hostile\"]\n\tcommand = /tmp/hostile.sh\n",
            "[uploadpack]\n\tpackObjectsHook = /tmp/hostile.sh\n",
            "[gpg \"ssh\"]\n\tprogram = /tmp/hostile.sh\n",
            "[interactive]\n\tdiffFilter = /tmp/hostile.sh\n",
            "[gc]\n\tauto = not-an-integer\n",
            "[gc]\n\trecentObjectsHook = /tmp/hostile.sh\n",
            "[include]\n\tpath = /tmp/hidden-config\n",
            '[includeIf "gitdir:/tmp/"]\n\tpath = /tmp/hidden-config\n',
            "[remote \"hostile\"]\n\turl = ext::/tmp/hostile.sh\n",
        ]
        for attack in attacks:
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp) / "repo"
                (repo / ".git").mkdir(parents=True)
                write_config(repo / ".git" / "config", attack)
                result = inspect_worktree(repo)
            self.assertEqual(result["status"], "fail")

    def test_accepts_actions_checkout_integer_gc_auto(self):
        for value in ("0", "1", "-1"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp) / "repo"
                (repo / ".git").mkdir(parents=True)
                write_config(repo / ".git" / "config", f"[gc]\n\tauto = {value}\n")
                result = inspect_worktree(repo)
            self.assertEqual(result["status"], "pass", result["errors"])

    def test_accepts_reciprocal_linked_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            common = base / "main" / ".git"
            admin = common / "worktrees" / "candidate"
            candidate = base / "candidate"
            admin.mkdir(parents=True)
            candidate.mkdir()
            write_config(common / "config")
            (candidate / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
            (admin / "commondir").write_text("../..\n", encoding="utf-8")
            (admin / "gitdir").write_text(f"{candidate / '.git'}\n", encoding="utf-8")
            result = inspect_worktree(candidate)
        self.assertEqual(result["status"], "pass", result["errors"])

    def test_rejects_foreign_backlink_and_duplicate_admin_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            common = base / "main" / ".git"
            admin = common / "worktrees" / "candidate"
            candidate = base / "candidate"
            impostor = base / "impostor"
            admin.mkdir(parents=True)
            candidate.mkdir()
            impostor.mkdir()
            write_config(common / "config")
            for worktree in (candidate, impostor):
                (worktree / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
            (admin / "commondir").write_text("../..\n", encoding="utf-8")
            (admin / "gitdir").write_text(f"{candidate / '.git'}\n", encoding="utf-8")
            result = inspect_worktree(impostor)
        joined = "\n".join(result["errors"])
        self.assertIn("backlink does not identify", joined)
        self.assertIn("multiple worktree pointers", joined)

    def test_cli_default_scan_rejects_duplicate_admin_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            common = base / "main" / ".git"
            admin = common / "worktrees" / "candidate"
            candidate = base / "candidate"
            duplicate = base / "duplicate"
            admin.mkdir(parents=True)
            candidate.mkdir()
            duplicate.mkdir()
            write_config(common / "config")
            for worktree in (candidate, duplicate):
                (worktree / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
            (admin / "commondir").write_text("../..\n", encoding="utf-8")
            (admin / "gitdir").write_text(f"{candidate / '.git'}\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts/governance/check_worktree.py"), "--repo", str(candidate)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("multiple worktree pointers", "\n".join(json.loads(result.stdout)["errors"]))

    def test_default_scan_rejects_symlinked_git_file_and_directory_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            common = base / "main" / ".git"
            admin = common / "worktrees" / "candidate"
            candidate = base / "candidate"
            file_alias = base / "file-alias"
            directory_alias = base / "directory-alias"
            admin.mkdir(parents=True)
            candidate.mkdir()
            file_alias.mkdir()
            directory_alias.mkdir()
            write_config(common / "config")
            (candidate / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
            (admin / "commondir").write_text("../..\n", encoding="utf-8")
            (admin / "gitdir").write_text(f"{candidate / '.git'}\n", encoding="utf-8")
            (file_alias / ".git").symlink_to(candidate / ".git")
            (directory_alias / ".git").symlink_to(admin, target_is_directory=True)
            result = inspect_worktree(candidate)
        joined = "\n".join(result["errors"])
        self.assertIn(str(file_alias / ".git"), joined)
        self.assertIn(str(directory_alias / ".git"), joined)
        self.assertEqual(result["status"], "fail")

    def test_scan_entry_budget_and_traversal_errors_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            extra = base / "extra"
            (repo / ".git").mkdir(parents=True)
            extra.mkdir()
            write_config(repo / ".git" / "config")
            limited = inspect_worktree(repo, [base], scan_entry_limit=1)
            with mock.patch("check_worktree.os.scandir", side_effect=PermissionError("denied")):
                unreadable = inspect_worktree(repo, [base])
        self.assertIn("entry limit exceeded", "\n".join(limited["errors"]))
        self.assertIn("scan cannot read", "\n".join(unreadable["errors"]))

    def test_scan_entry_budget_rejects_wrong_types_and_ranges(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / ".git").mkdir(parents=True)
            write_config(repo / ".git" / "config")
            for value in (0, -1, True, None, "1", 1.0):
                with self.subTest(value=value):
                    result = inspect_worktree(repo, scan_entry_limit=value)  # type: ignore[arg-type]
                    self.assertEqual(result["status"], "fail")
                    self.assertIn("positive integer", "\n".join(result["errors"]))

    def test_rejects_foreign_backlink_outside_conventional_worktrees_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            common = base / "main" / ".git"
            admin = common / "slots" / "candidate"
            candidate = base / "candidate"
            admin.mkdir(parents=True)
            candidate.mkdir()
            write_config(common / "config")
            (candidate / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
            (admin / "commondir").write_text("../..\n", encoding="utf-8")
            (admin / "gitdir").write_text(f"{base / 'foreign' / '.git'}\n", encoding="utf-8")
            result = inspect_worktree(candidate)
        self.assertEqual(result["status"], "fail")
        self.assertIn("backlink does not identify", "\n".join(result["errors"]))

    def test_rejects_reciprocal_link_outside_registered_worktrees_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            common = base / "main" / ".git"
            admin = common / "slots" / "candidate"
            candidate = base / "candidate"
            admin.mkdir(parents=True)
            candidate.mkdir()
            write_config(common / "config")
            (candidate / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
            (admin / "commondir").write_text("../..\n", encoding="utf-8")
            (admin / "gitdir").write_text(f"{candidate / '.git'}\n", encoding="utf-8")
            result = inspect_worktree(candidate)
        self.assertEqual(result["status"], "fail")
        self.assertIn("worktrees registry", "\n".join(result["errors"]))

    def test_rejects_git_topology_environment_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / ".git").mkdir(parents=True)
            write_config(repo / ".git" / "config")
            for name in sorted(
                {
                    "GIT_DIR",
                    "GIT_WORK_TREE",
                    "GIT_INDEX_FILE",
                    "GIT_COMMON_DIR",
                    "GIT_CONFIG_COUNT",
                    "GIT_CONFIG_NOSYSTEM",
                    "GIT_CONFIG_PARAMETERS",
                    "GIT_CONFIG_KEY_0",
                    "GIT_CONFIG_VALUE_0",
                }
            ):
                with self.subTest(name=name), mock.patch.dict(os.environ, {name: "/tmp/attack"}):
                    result = inspect_worktree(repo)
                self.assertIn(name, "\n".join(result["errors"]))

    def test_malformed_commondir_returns_failure_instead_of_raising(self):
        for content in (b"\xff\xfe", b"bad\x00path"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                common = base / "main" / ".git"
                admin = common / "worktrees" / "candidate"
                candidate = base / "candidate"
                admin.mkdir(parents=True)
                candidate.mkdir()
                write_config(common / "config")
                (candidate / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
                (admin / "commondir").write_bytes(content)
                (admin / "gitdir").write_text(f"{candidate / '.git'}\n", encoding="utf-8")
                result = inspect_worktree(candidate)
            self.assertEqual(result["status"], "fail")
            self.assertIn("commondir is", "\n".join(result["errors"]))

    def test_isolated_git_environment_drops_all_inherited_git_controls(self):
        source = {
            "HOME": "/home/test",
            "GIT_DIR": "/victim/.git",
            "GIT_WORK_TREE": "/candidate",
            "GIT_INDEX_FILE": "/candidate/index",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.worktree",
            "GIT_CONFIG_VALUE_0": "/candidate",
        }
        result = isolated_git_environment(source)
        self.assertEqual(result["HOME"], "/home/test")
        self.assertEqual(result["GIT_CONFIG_GLOBAL"], "/dev/null")
        self.assertEqual(result["GIT_OPTIONAL_LOCKS"], "0")
        self.assertNotIn("GIT_DIR", result)
        self.assertNotIn("GIT_WORK_TREE", result)
        self.assertNotIn("GIT_INDEX_FILE", result)
        self.assertNotIn("GIT_CONFIG_COUNT", result)

    def test_nested_git_tests_cannot_mutate_inherited_live_admin(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            victim = base / "victim"
            victim.mkdir()
            env = isolated_git_environment({"HOME": str(base)})
            subprocess.run(["git", "init"], cwd=victim, env=env, check=True, capture_output=True)
            config = victim / ".git" / "config"
            before = config.read_bytes()
            hostile = dict(os.environ)
            hostile.update(
                {
                    "GIT_DIR": str(victim / ".git"),
                    "GIT_WORK_TREE": str(base / "candidate"),
                    "GIT_INDEX_FILE": str(base / "synthetic-index"),
                }
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "tests.governance.test_run_isolated_pi.TestRunIsolatedPiPolicy.test_validate_candidate_checkout_requires_clean_git_tree",
                ],
                cwd=REPO_ROOT,
                env=hostile,
                capture_output=True,
                text=True,
                check=False,
            )
            after = config.read_bytes()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
