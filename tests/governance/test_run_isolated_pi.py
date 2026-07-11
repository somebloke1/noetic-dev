"""Tests for the Pi isolation dispatcher policy surface."""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

from run_isolated_pi import QA_TOOL_ALLOWLIST, _non_evidence_record, validate_model, validate_tools


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
