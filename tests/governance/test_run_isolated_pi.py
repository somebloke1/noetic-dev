"""Tests for the Pi isolation dispatcher policy surface."""

from __future__ import annotations

import argparse
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
    _non_evidence_record,
    _write_tools_observed,
    build_bwrap_command,
    resolve_scoped_credentials,
    validate_model,
    validate_tools,
)


class TestRunIsolatedPiPolicy(unittest.TestCase):
    def test_qa_tool_allowlist_excludes_write_capable_tools(self):
        self.assertEqual(QA_TOOL_ALLOWLIST, {"read", "grep", "find", "ls"})
        ok, message, _tools = validate_tools("qa", "read,grep,find,ls")
        self.assertTrue(ok, message)
        ok, message, _tools = validate_tools("qa", "read,bash,edit,write")
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

    def test_build_bwrap_command_mounts_candidate_read_only_and_hides_home(self):
        with tempfile.TemporaryDirectory() as tmp:
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
        self.assertNotIn(str(Path.home()), command)
        ro_pairs = list(zip(command, command[1:], command[2:]))
        self.assertIn(("--ro-bind", str(candidate), str(candidate)), ro_pairs)
        self.assertIn(("--setenv", "HOME", "/tmp/home"), ro_pairs)

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
