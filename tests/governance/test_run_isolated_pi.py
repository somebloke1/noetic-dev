"""Tests for the Pi isolation dispatcher policy surface."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

from run_isolated_pi import (
    QA_TOOL_ALLOWLIST,
    ROLE_TOOL_ALLOWLISTS,
    _credential_interface,
    _non_evidence_record,
    _write_tools_observed,
    build_bwrap_command,
    resolve_scoped_credentials,
    validate_candidate_checkout,
    validate_model,
    validate_tools,
)


class TestRunIsolatedPiPolicy(unittest.TestCase):
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
