"""Tests for evidence manifest validation and canonical hashing."""

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

from check_evidence_manifest import _command_matches_registry, check as check_manifest
from hash_tree import (
    canonical_json,
    canonical_json_sha256,
    manifest_digest_excluding_own,
    sha256_file,
    sha256_text,
    validate_sha_hex,
    validate_sha256_hex,
)
from json_schema import DuplicateKeyError, load_json_strict

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[2]


def load_fixture(name: str):
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


class TestEvidenceManifestValidation(unittest.TestCase):
    def test_registry_templates_match_standalone_and_embedded_placeholders(self):
        registry = {
            "example": {
                "category": "gate",
                "argv": [
                    "command",
                    "{{manifest_path}}",
                    "--lease=main:{{old_sha}}",
                ],
            }
        }
        command = {
            "category": "gate",
            "argv": ["command", "/tmp/manifest.json", "--lease=main:" + "a" * 40],
        }
        self.assertTrue(_command_matches_registry(command, "example", registry))
        command["argv"][2] = "--lease=dev:" + "a" * 40
        self.assertFalse(_command_matches_registry(command, "example", registry))

    def test_valid_advisory_manifest_is_structurally_valid(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        errors = check_manifest(manifest)
        self.assertEqual(errors, [], f"expected advisory manifest to validate structurally: {errors}")

    def test_manifest_only_authoritative_claim_is_invalid(self):
        manifest = load_fixture("negative_manifest_only_authoritative_manifest.json")
        errors = check_manifest(manifest)
        self.assertTrue(any("manifest-only authority claim" in error for error in errors), errors)

    def test_valid_multigeneration_manifest_is_structurally_valid(self):
        manifest = load_fixture("valid_multigeneration_advisory_manifest.json")
        errors = check_manifest(manifest)
        self.assertEqual(errors, [], f"expected multigeneration advisory manifest to validate: {errors}")

    def test_schema_version_required(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        del manifest["schema_version"]
        errors = check_manifest(manifest)
        self.assertTrue(any("schema_version" in error for error in errors), errors)

    def test_candidate_sha_must_be_40_chars(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        manifest["repo"]["candidate_sha"] = "short"
        errors = check_manifest(manifest)
        self.assertTrue(any("candidate_sha" in error for error in errors), errors)

    def test_validate_repo_as_test_rejected(self):
        manifest = load_fixture("negative_validator_as_test_manifest.json")
        errors = check_manifest(manifest)
        self.assertTrue(any("validate_repo.py" in error and "test" in error for error in errors), errors)

    def test_missing_qa_rejected_as_cardinality_error(self):
        manifest = load_fixture("negative_missing_qa_manifest.json")
        errors = check_manifest(manifest)
        self.assertTrue(any("exactly one QA" in error for error in errors), errors)

    def test_isolation_tree_change_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        manifest["qa"]["records"][0]["isolation_proof"]["candidate_tree_after"] = "f" * 40
        errors = check_manifest(manifest)
        self.assertTrue(any("candidate_tree_after" in error or "tree changed" in error for error in errors), errors)

    def test_forged_trusted_manifest_sha_mismatch(self):
        manifest = load_fixture("negative_forged_trusted_manifest.json")
        errors = check_manifest(manifest)
        self.assertTrue(any("digest mismatch" in error for error in errors), errors)

    def test_cli_rejects_duplicate_json_keys(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            handle.write('{"schema_version":"1","schema_version":"1"}')
            path = Path(handle.name)
        try:
            result = subprocess.run(
                [sys.executable, "scripts/governance/check_evidence_manifest.py", str(path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate object key", result.stderr)
        finally:
            path.unlink(missing_ok=True)


class TestHashTree(unittest.TestCase):
    def test_sha256_text_consistency(self):
        self.assertEqual(sha256_text("hello"), sha256_text("hello"))
        self.assertEqual(len(sha256_text("hello")), 64)

    def test_canonical_json_sorted_keys_no_whitespace(self):
        self.assertEqual(canonical_json({"b": 2, "a": [1, 2]}), '{"a":[1,2],"b":2}')

    def test_canonical_json_rejects_nan(self):
        with self.assertRaises(ValueError):
            canonical_json({"bad": float("nan")})

    def test_manifest_digest_removes_exact_own_field_only(self):
        manifest = {
            "policy": {
                "runner_attestation": {
                    "artifact": {
                        "manifest_sha256": "a" * 64,
                        "artifact_digest": "sha256:" + "b" * 64,
                    }
                }
            }
        }
        digest = manifest_digest_excluding_own(manifest)
        expected_obj = {
            "policy": {
                "runner_attestation": {
                    "artifact": {"artifact_digest": "sha256:" + "b" * 64}
                }
            }
        }
        self.assertEqual(digest, canonical_json_sha256(expected_obj))
        self.assertIn("manifest_sha256", manifest["policy"]["runner_attestation"]["artifact"])

    def test_validate_sha_helpers(self):
        validate_sha256_hex("a" * 64)
        validate_sha_hex("b" * 40, 40)
        with self.assertRaises(ValueError):
            validate_sha256_hex("z" * 64)
        with self.assertRaises(ValueError):
            validate_sha_hex("b" * 39, 40)

    def test_sha256_file(self):
        self.assertEqual(len(sha256_file(FIXTURES_DIR / "valid_advisory_manifest.json")), 64)

    def test_manifest_digest_consistency(self):
        m1 = load_fixture("valid_advisory_manifest.json")
        m2 = load_fixture("valid_advisory_manifest.json")
        self.assertEqual(manifest_digest_excluding_own(m1), manifest_digest_excluding_own(m2))


if __name__ == "__main__":
    unittest.main()
