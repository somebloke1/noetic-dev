"""Tests for the fail-closed delivery gate."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

from check_delivery_gate import check_delivery, check_pinning

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[2]


def load_fixture(name: str):
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


class TestDeliveryGatePositive(unittest.TestCase):
    def test_valid_authoritative_publication_passes(self):
        manifest = load_fixture("valid_authoritative_manifest.json")
        passed, errors, gate_type = check_delivery(manifest)
        self.assertTrue(passed, f"expected authoritative fixture to pass, got {gate_type}: {errors}")
        self.assertEqual(gate_type, "publication")

    def test_valid_advisory_is_blocked_before_merge(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        passed, errors, gate_type = check_delivery(manifest)
        self.assertFalse(passed)
        self.assertEqual(gate_type, "merge")
        self.assertIn("authoritative trusted runner", " ".join(errors).lower())


class TestDeliveryGateNegativeFixtures(unittest.TestCase):
    CASES = {
        "negative_validator_as_test_manifest.json": "validate_repo.py cannot be reported as a test",
        "negative_self_qa_manifest.json": "self-QA rejected",
        "negative_missing_qa_manifest.json": "cardinality mismatch",
        "negative_stale_qa_manifest.json": "candidate_sha",
        "negative_wrong_sha_manifest.json": "candidate SHA must equal PR head SHA",
        "negative_wip_pr_manifest.json": "WIP prefix",
        "negative_draft_pr_manifest.json": "PR is a draft",
        "negative_stacked_pr_manifest.json": "stacked PR",
        "negative_blocked_issue_manifest.json": "prevents closure",
        "negative_author_approval_manifest.json": "PR author",
        "negative_pre_candidate_approval_manifest.json": "predates candidate",
        "negative_mutable_action_manifest.json": "workflow.pinning",
        "negative_branch_publication_manifest.json": "branch-name publication forbidden",
        "negative_unsupported_model_manifest.json": "unsupported model profile",
        "negative_two_qas_one_pass_manifest.json": "multiple QA",
        "negative_forged_trusted_manifest.json": "GitHub API or artifact attestation",
        "negative_no_external_provenance_manifest.json": "GitHub provenance payload missing",
        "negative_artifact_digest_mismatch_manifest.json": "artifact digest mismatch",
        "negative_policy_file_hash_mismatch_manifest.json": "policy file hash mismatch",
        "negative_missing_probe_manifest.json": "missing protected READY probe",
        "negative_probe_model_mismatch_manifest.json": "resolved_model",
        "negative_qa_base_mismatch_manifest.json": "base_sha",
        "negative_execution_candidate_mismatch_manifest.json": "candidate_sha",
        "negative_execution_record_hash_mismatch_manifest.json": "execution record hash mismatch",
        "negative_probe_event_reused_manifest.json": "probe event stream reused",
        "negative_qa_record_writable_manifest.json": "writable by QA/model",
        "negative_record_only_qa_manifest.json": "record-only",
    }

    def test_negative_fixtures_fail_for_named_reason(self):
        for fixture_name, expected in self.CASES.items():
            with self.subTest(fixture=fixture_name):
                manifest = load_fixture(fixture_name)
                passed, errors, gate_type = check_delivery(manifest)
                self.assertFalse(passed, f"{fixture_name} unexpectedly passed")
                joined = "\n".join(errors)
                self.assertIn(expected, joined, f"{fixture_name} errors were: {errors}")


class TestDeliveryGateCLI(unittest.TestCase):
    def test_cli_rejects_forged_trusted_manifest_during_manifest_validation(self):
        fixture = FIXTURES_DIR / "negative_forged_trusted_manifest.json"
        result = subprocess.run(
            [sys.executable, "scripts/governance/check_delivery_gate.py", str(fixture)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("digest mismatch", result.stderr)

    def test_cli_passes_authoritative_fixture(self):
        fixture = FIXTURES_DIR / "valid_authoritative_manifest.json"
        result = subprocess.run(
            [sys.executable, "scripts/governance/check_delivery_gate.py", str(fixture)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Delivery gate PASSED", result.stderr)


class TestDeliveryGatePinning(unittest.TestCase):
    def test_governance_workflow_is_pinned(self):
        workflow_path = REPO_ROOT / ".github" / "workflows" / "governance.yml"
        errors = check_pinning(str(workflow_path))
        self.assertEqual(errors, [])

    def test_mutable_tag_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as handle:
            handle.write("""
jobs:
  test:
    steps:
      - uses: actions/checkout@v4
""")
            path = Path(handle.name)
        try:
            errors = check_pinning(str(path))
            self.assertTrue(any("unpinned" in error for error in errors), errors)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
