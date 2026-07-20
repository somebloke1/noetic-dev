"""Tests for the Pi isolation dispatcher policy surface."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

from check_worktree import isolated_git_environment
from run_isolated_pi import (
    QA_TOOL_ALLOWLIST,
    ROLE_TOOL_ALLOWLISTS,
    _candidate_git_metadata_ro_mounts,
    _credential_interface,
    _non_evidence_record,
    _write_tools_observed,
    build_bwrap_command,
    materialize_candidate_checkout,
    resolve_scoped_credentials,
    validate_candidate_checkout,
    validate_model,
    validate_tools,
)


class TestRunIsolatedPiPolicy(unittest.TestCase):
    def setUp(self) -> None:
        self._git_environment = mock.patch.dict(
            os.environ,
            isolated_git_environment(dict(os.environ)),
            clear=True,
        )
        self._git_environment.start()
        self.addCleanup(self._git_environment.stop)

    def test_qa_tool_allowlist_is_empty_until_credential_broker_exists(self):
        self.assertEqual(QA_TOOL_ALLOWLIST, set())
        ok, message, _tools = validate_tools("qa", "")
        self.assertTrue(ok, message)
        ok, message, _tools = validate_tools("qa", "read")
        self.assertFalse(ok)
        self.assertIn("cannot use tools", message)

    def test_unsupported_model_rejected(self):
        ok, message = validate_model("unsupported/model")
        self.assertFalse(ok)
        self.assertIn("not in allowed profiles", message)

    def test_role_specific_model_binding_rejects_implementer_model_for_qa(self):
        ok, message = validate_model("litellm/deepseek-v4-flash", "qa")
        self.assertFalse(ok)
        self.assertIn("not authorized for role qa", message)

    def test_dispatcher_no_longer_pretends_to_support_writable_implementers(self):
        self.assertNotIn("implementer", ROLE_TOOL_ALLOWLISTS)
        self.assertNotIn("remediator", ROLE_TOOL_ALLOWLISTS)

    def test_write_tool_observation_is_derived_from_events(self):
        stdout = '{"tool_name":"read"}\n{"tool_name":"write"}\n'
        self.assertTrue(_write_tools_observed(stdout))
        self.assertFalse(_write_tools_observed('{"tool_name":"read"}\n'))

    def test_scoped_credentials_block_missing_or_disallowed_names(self):
        ok, message, creds = resolve_scoped_credentials(["GH_TOKEN"])
        self.assertFalse(ok)
        self.assertEqual(creds, {})
        self.assertIn("not an allowed provider credential", message)
        with mock.patch.dict("run_isolated_pi.os.environ", {}, clear=True):
            ok, message, creds = resolve_scoped_credentials(["OPENAI_API_KEY"])
        self.assertFalse(ok)
        self.assertEqual(creds, {})
        self.assertIn("unavailable", message)

    def test_scoped_env_credentials_are_not_claimed_hidden_from_tools(self):
        interface = _credential_interface({"OPENAI_API_KEY": "secret"}, ["bash"], "validator")
        self.assertFalse(interface["brokered"])
        self.assertTrue(interface["available_to_tools"])
        qa_interface = _credential_interface({"OPENAI_API_KEY": "secret"}, [], "qa")
        self.assertTrue(qa_interface["tools_disabled_for_authoritative_qa"])
        self.assertFalse(qa_interface["available_to_tools"])

    def test_build_bwrap_command_mounts_candidate_read_only_and_hides_home(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp, mock.patch.dict("os.environ", {"HOME": "/tmp"}):
            root = Path(tmp)
            node_prefix = root / "node" / "v24.0.0"
            pi_bin = node_prefix / "bin" / "pi"
            prompt = root / "prompt.md"
            candidate = root / "candidate"
            pi_bin.parent.mkdir(parents=True)
            pi_bin.write_text("#!/bin/sh\n", encoding="utf-8")
            prompt.write_text("prompt", encoding="utf-8")
            candidate.mkdir()
            with mock.patch("run_isolated_pi.shutil.which", side_effect=lambda name: "/usr/bin/bwrap" if name == "bwrap" else str(pi_bin)):
                command = build_bwrap_command([str(pi_bin), "--version"], candidate_dir=candidate, prompt_file=prompt, cwd=candidate)
        self.assertIn("--ro-bind", command)
        triples = list(zip(command, command[1:], command[2:]))
        ro_pairs = [triple for triple in triples if triple[0] == "--ro-bind"]
        self.assertIn(("--ro-bind", str(candidate), str(candidate)), ro_pairs)
        self.assertNotIn(("--ro-bind", "/tmp", "/tmp"), ro_pairs)
        self.assertIn(("--setenv", "HOME", "/tmp/home"), triples)

    def _init_candidate_repo(self, root: Path) -> str:
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
        (root / "tracked.txt").write_text("clean\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True)
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()

    def _commit_file(self, root: Path, relative_path: str, content: str, message: str) -> str:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", relative_path], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", message], cwd=root, check=True, capture_output=True)
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()

    def test_validate_candidate_checkout_requires_clean_git_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._init_candidate_repo(root)
            expected_tree = subprocess.check_output(["git", "rev-parse", f"{sha}^{{tree}}"], cwd=root, text=True).strip()
            ok, message, tree = validate_candidate_checkout(root, sha)
            self.assertTrue(ok, message)
            self.assertEqual(tree, expected_tree)

            (root / "tracked.txt").write_text("dirty\n", encoding="utf-8")
            ok, message, _tree = validate_candidate_checkout(root, sha)
            self.assertFalse(ok)
            self.assertIn("dirty or has untracked files", message)

    def test_validate_candidate_checkout_rejects_untracked_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._init_candidate_repo(root)
            (root / "untracked.txt").write_text("untracked\n", encoding="utf-8")
            ok, message, _tree = validate_candidate_checkout(root, sha)
            self.assertFalse(ok)
            self.assertIn("dirty or has untracked files", message)

    def test_validate_candidate_checkout_rejects_ignored_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_candidate_repo(root)
            sha = self._commit_file(root, ".gitignore", "ignored.log\n", "ignore logs")
            (root / "ignored.log").write_text("ignored but visible\n", encoding="utf-8")
            ok, message, _tree = validate_candidate_checkout(root, sha)
            self.assertFalse(ok)
            self.assertIn("ignored untracked entries", message)
            self.assertIn("ignored.log", message)

    def test_validate_candidate_checkout_rejects_assume_unchanged_modified_tracked_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._init_candidate_repo(root)
            subprocess.run(["git", "update-index", "--assume-unchanged", "tracked.txt"], cwd=root, check=True)
            (root / "tracked.txt").write_text("hidden dirty\n", encoding="utf-8")
            ok, message, _tree = validate_candidate_checkout(root, sha)
            self.assertFalse(ok)
            self.assertIn("assume-unchanged or skip-worktree", message)
            self.assertIn("tracked.txt", message)

    def test_validate_candidate_checkout_rejects_skip_worktree_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._init_candidate_repo(root)
            subprocess.run(["git", "update-index", "--skip-worktree", "tracked.txt"], cwd=root, check=True)
            ok, message, _tree = validate_candidate_checkout(root, sha)
            self.assertFalse(ok)
            self.assertIn("assume-unchanged or skip-worktree", message)
            self.assertIn("tracked.txt", message)

    @unittest.skipUnless(shutil.which("bwrap") or shutil.which("bubblewrap"), "bubblewrap is required")
    def test_materialize_candidate_checkout_creates_private_verified_tree(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as private_tmp:
            root = Path(tmp)
            sha = self._init_candidate_repo(root)
            expected_tree = subprocess.check_output(["git", "rev-parse", f"{sha}^{{tree}}"], cwd=root, text=True).strip()
            private_dir, private_tree = materialize_candidate_checkout(root, sha, Path(private_tmp))
            self.assertNotEqual(private_dir.resolve(), root.resolve())
            self.assertEqual(private_tree, expected_tree)
            ok, message, tree = validate_candidate_checkout(private_dir, sha)
            self.assertTrue(ok, message)
            self.assertEqual(tree, expected_tree)

            (root / "tracked.txt").write_text("source mutated after materialization\n", encoding="utf-8")
            self.assertEqual((private_dir / "tracked.txt").read_text(encoding="utf-8"), "clean\n")

    @unittest.skipUnless(shutil.which("bwrap") or shutil.which("bubblewrap"), "bubblewrap is required")
    def test_materialize_candidate_checkout_revalidates_source_inside_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as private_tmp:
            root = Path(tmp)
            sha = self._init_candidate_repo(root)
            (root / "untracked.txt").write_text("late mutation\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "untracked files"):
                materialize_candidate_checkout(root, sha, Path(private_tmp))

    @unittest.skipUnless(shutil.which("bwrap") or shutil.which("bubblewrap"), "bubblewrap is required")
    def test_materialize_candidate_checkout_confines_core_fsmonitor(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as private_tmp:
            base = Path(tmp)
            root = base / "candidate"
            root.mkdir()
            sha = self._init_candidate_repo(root)
            marker = base / "host-fsmonitor-marker"
            callback = base / "fsmonitor.sh"
            callback.write_text(f"#!/bin/sh\nprintf marker > {marker}\nexit 0\n", encoding="utf-8")
            callback.chmod(0o755)
            subprocess.run(["git", "config", "core.fsmonitor", str(callback)], cwd=root, check=True)

            expected_tree = subprocess.check_output(["git", "rev-parse", f"{sha}^{{tree}}"], cwd=root, text=True).strip()
            private_dir, private_tree = materialize_candidate_checkout(root, sha, Path(private_tmp))

            self.assertFalse(marker.exists(), "source-local core.fsmonitor escaped bootstrap confinement")
            self.assertEqual(private_tree, expected_tree)
            ok, message, tree = validate_candidate_checkout(private_dir, sha)
            self.assertTrue(ok, message)
            self.assertEqual(tree, expected_tree)

    @unittest.skipUnless(shutil.which("bwrap") or shutil.which("bubblewrap"), "bubblewrap is required")
    def test_materialize_candidate_checkout_does_not_execute_uploadpack_hook_on_host(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as private_tmp:
            base = Path(tmp)
            root = base / "candidate"
            root.mkdir()
            sha = self._init_candidate_repo(root)
            marker = base / "host-uploadpack-marker"
            hook = base / "pack-objects-hook.sh"
            hook.write_text(
                "#!/bin/sh\n"
                f"printf marker > {marker}\n"
                "exec git pack-objects \"$@\"\n",
                encoding="utf-8",
            )
            hook.chmod(0o755)
            subprocess.run(["git", "config", "uploadpack.packObjectsHook", str(hook)], cwd=root, check=True)

            expected_tree = subprocess.check_output(["git", "rev-parse", f"{sha}^{{tree}}"], cwd=root, text=True).strip()
            private_dir, private_tree = materialize_candidate_checkout(root, sha, Path(private_tmp))

            self.assertFalse(marker.exists(), "source-local uploadpack.packObjectsHook escaped bootstrap confinement")
            self.assertEqual(private_tree, expected_tree)
            ok, message, tree = validate_candidate_checkout(private_dir, sha)
            self.assertTrue(ok, message)
            self.assertEqual(tree, expected_tree)

    @unittest.skipUnless(shutil.which("bwrap") or shutil.which("bubblewrap"), "bubblewrap is required")
    def test_materialize_candidate_checkout_does_not_execute_source_smudge_filter(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as private_tmp:
            base = Path(tmp)
            root = base / "candidate"
            root.mkdir()
            marker = Path(private_tmp) / "filter-marker"
            filter_script = root / "hostile-filter.sh"
            filter_script.write_text(
                "#!/bin/sh\n"
                f"printf marker > {marker}\n"
                "cat\n",
                encoding="utf-8",
            )
            filter_script.chmod(0o755)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
            subprocess.run(["git", "config", "filter.hostile.smudge", str(filter_script)], cwd=root, check=True)
            (root / ".gitattributes").write_text("payload.txt filter=hostile\n", encoding="utf-8")
            (root / "payload.txt").write_text("payload\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitattributes", "payload.txt", "hostile-filter.sh"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "add filtered payload"], cwd=root, check=True, capture_output=True)
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()

            private_dir, _private_tree = materialize_candidate_checkout(root, sha, Path(private_tmp))

            self.assertFalse(marker.exists(), "source-local smudge filter executed during materialization")
            self.assertEqual((private_dir / "payload.txt").read_text(encoding="utf-8"), "payload\n")

    @unittest.skipUnless(shutil.which("bwrap") or shutil.which("bubblewrap"), "bubblewrap is required")
    def test_materialize_candidate_checkout_does_not_execute_source_process_filter(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as private_tmp:
            base = Path(tmp)
            root = base / "candidate"
            root.mkdir()
            marker = Path(private_tmp) / "process-filter-marker"
            filter_script = root / "hostile-process-filter.sh"
            filter_script.write_text(
                "#!/bin/sh\n"
                "while read line; do\n"
                f"  printf marker > {marker}\n"
                "  case \"$line\" in\n"
                "    command=*) printf 'status=success\\n\\n' ;;\n"
                "    '') printf '\\n' ;;\n"
                "  esac\n"
                "done\n",
                encoding="utf-8",
            )
            filter_script.chmod(0o755)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
            (root / ".gitattributes").write_text("payload.txt filter=hostile\n", encoding="utf-8")
            (root / "payload.txt").write_text("payload\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitattributes", "payload.txt", "hostile-process-filter.sh"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "add process filtered payload"], cwd=root, check=True, capture_output=True)
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            subprocess.run(["git", "config", "filter.hostile.process", str(filter_script)], cwd=root, check=True)

            private_dir, _private_tree = materialize_candidate_checkout(root, sha, Path(private_tmp))

            self.assertFalse(marker.exists(), "source-local process filter executed during materialization")
            self.assertEqual((private_dir / "payload.txt").read_text(encoding="utf-8"), "payload\n")

    def test_candidate_git_metadata_mounts_exclude_git_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            common = base / "repo" / ".git"
            gitdir = common / "worktrees" / "candidate"
            candidate = base / "candidate"
            gitdir.mkdir(parents=True)
            (common / "objects").mkdir(parents=True)
            (common / "refs").mkdir()
            candidate.mkdir()
            (candidate / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
            (gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (gitdir / "index").write_bytes(b"DIRC")
            (gitdir / "commondir").write_text("../..\n", encoding="utf-8")
            (gitdir / "gitdir").write_text(f"{candidate / '.git'}\n", encoding="utf-8")
            (common / "config").write_text("[filter \"hostile\"]\n", encoding="utf-8")

            mounts = _candidate_git_metadata_ro_mounts(candidate)

            self.assertIn(gitdir / "HEAD", mounts)
            self.assertIn(gitdir / "index", mounts)
            self.assertIn(common / "objects", mounts)
            self.assertNotIn(gitdir, mounts)
            self.assertNotIn(common, mounts)
            self.assertNotIn(common / "config", mounts)

    def test_candidate_git_metadata_rejects_unowned_commondir(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            common = base / "repo" / ".git"
            gitdir = common / "worktrees" / "candidate"
            candidate = base / "candidate"
            gitdir.mkdir(parents=True)
            candidate.mkdir()
            (candidate / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
            (gitdir / "commondir").write_text(str(base), encoding="utf-8")
            (gitdir / "gitdir").write_text(f"{candidate / '.git'}\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "external commondir"):
                _candidate_git_metadata_ro_mounts(candidate)

    def test_candidate_git_metadata_rejects_foreign_worktree_backlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            common = base / "victim" / ".git"
            gitdir = common / "worktrees" / "victim-worktree"
            candidate = base / "impostor"
            victim = base / "victim-worktree"
            gitdir.mkdir(parents=True)
            candidate.mkdir()
            victim.mkdir()
            (candidate / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
            (gitdir / "gitdir").write_text(f"{victim / '.git'}\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "backlink does not identify candidate"):
                _candidate_git_metadata_ro_mounts(candidate)

    def test_record_only_is_non_evidence(self):
        args = argparse.Namespace(
            run_id="run-1",
            role="qa",
            role_run_id="qa-run-1",
            qa_for_pass_id="impl-1",
            model="openai-codex/gpt-5.6-terra",
            candidate_sha="d" * 40,
            base_sha="c" * 40,
        )
        record = _non_evidence_record(args, "qa_primary", ["read"])
        self.assertTrue(record["record_only"])
        self.assertEqual(record["evidence_class"], "non-evidence")
        self.assertNotEqual(record["actual_invocation"]["exit_code"], None)


if __name__ == "__main__":
    unittest.main()
