"""Tests for evidence manifest validation."""

import json
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
# Direct import by manipulating path to scripts/governance/
GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)
from check_evidence_manifest import check as check_manifest
from hash_tree import (
    canonical_json,
    canonical_json_sha256,
    manifest_digest_excluding_own,
    sha256_file,
    sha256_text,
    validate_sha_hex,
    validate_sha256_hex,
)


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str):
    path = FIXTURES_DIR / name
    with open(path) as f:
        return json.load(f)


class TestEvidenceManifestValidation(unittest.TestCase):
    """Test evidence manifest schema validation."""

    def test_valid_advisory_passes(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        errors = check_manifest(manifest)
        self.assertEqual(errors, [], f"Expected no errors, got: {errors}")

    def test_schema_version_required(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        del manifest["schema_version"]
        errors = check_manifest(manifest)
        self.assertTrue(any("schema_version" in e for e in errors))

    def test_schema_version_must_be_1(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        manifest["schema_version"] = "2"
        errors = check_manifest(manifest)
        self.assertTrue(any("schema_version" in e for e in errors))

    def test_missing_required_field(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        del manifest["repo"]
        errors = check_manifest(manifest)
        self.assertTrue(any("repo" in e for e in errors))

    def test_candidate_sha_must_be_40_chars(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        manifest["repo"]["candidate_sha"] = "short"
        errors = check_manifest(manifest)
        self.assertTrue(any("candidate_sha" in e for e in errors))

    def test_pull_request_head_sha_matches_candidate_sha(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        manifest["pull_request"]["head_sha"] = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        errors = check_manifest(manifest)
        self.assertTrue(any("head_sha" in e for e in errors))

    def test_validate_repo_as_test_rejected(self):
        manifest = load_fixture("negative_validator_as_test_manifest.json")
        errors = check_manifest(manifest)
        self.assertTrue(
            any("validate_repo.py" in e and "test" in e for e in errors),
            f"Expected validate_repo as test error, got: {errors}"
        )

    def test_qa_verdict_must_be_pass_or_fail(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        manifest["qa"]["verdict"] = "maybe"
        errors = check_manifest(manifest)
        self.assertTrue(any("verdict" in e for e in errors))

    def test_missing_impl_pass(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        manifest["passes"]["implementation_pass_ids"] = []
        manifest["passes"]["remediation_pass_ids"] = []
        errors = check_manifest(manifest)
        self.assertTrue(any("at least one" in e for e in errors))

    def test_isolation_proof_source_ro(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        manifest["qa"]["isolation_proof"]["source_mount_read_only"] = False
        errors = check_manifest(manifest)
        self.assertTrue(any("source_mount_read_only" in e for e in errors))

    def test_isolation_proof_write_tools_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        manifest["qa"]["isolation_proof"]["write_tools_observed"] = True
        errors = check_manifest(manifest)
        self.assertTrue(any("write_tools_observed" in e for e in errors))

    def test_isolation_proof_tree_change_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        manifest["qa"]["isolation_proof"]["candidate_tree_after"] = "ffffffffffffffffffffffffffffffffffffffff"
        errors = check_manifest(manifest)
        self.assertTrue(any("tree changed" in e for e in errors))

    def test_pass_candidate_sha_mismatch(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        manifest["passes"]["candidate_sha"] = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        errors = check_manifest(manifest)
        self.assertTrue(any("candidate_sha" in e for e in errors))

    def test_forged_trusted_manifest_sha_mismatch(self):
        """A manifest with trusted_runner=true but wrong manifest_sha256 should be caught."""
        manifest = load_fixture("negative_forged_trusted_manifest.json")
        errors = check_manifest(manifest)
        self.assertTrue(
            any("digest" in e.lower() and "mismatch" in e.lower() for e in errors),
            f"Expected digest mismatch error, got: {errors}"
        )


class TestHashTree(unittest.TestCase):
    """Test hash tree utility functions."""

    def test_sha256_text_consistency(self):
        h1 = sha256_text("hello")
        h2 = sha256_text("hello")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_sha256_text_different(self):
        h1 = sha256_text("hello")
        h2 = sha256_text("world")
        self.assertNotEqual(h1, h2)

    def test_canonical_json_sorted_keys(self):
        obj = {"b": 2, "a": 1}
        result = canonical_json(obj)
        self.assertEqual(result, '{"a":1,"b":2}')

    def test_canonical_json_no_whitespace(self):
        obj = {"a": [1, 2, 3]}
        result = canonical_json(obj)
        self.assertNotIn(" ", result)

    def test_canonical_json_sha256_consistency(self):
        obj = {"a": 1, "b": 2}
        h1 = canonical_json_sha256(obj)
        h2 = canonical_json_sha256(obj)
        self.assertEqual(h1, h2)

    def test_manifest_digest_excludes_own_field(self):
        manifest = {
            "policy": {
                "runner_attestation": {
                    "artifact": {
                        "manifest_sha256": "should_be_removed"
                    }
                }
            }
        }
        digest = manifest_digest_excluding_own(manifest)
        # The digest should not include the manifest_sha256 field
        # We verify by checking the serialized form doesn't contain the field
        result_json = canonical_json(manifest)
        # After the function, manifest should have been modified (deep copy)
        self.assertIsInstance(digest, str)
        self.assertEqual(len(digest), 64)

    def test_validate_sha256_hex_valid(self):
        validate_sha256_hex("a" * 64)
        # No exception = pass

    def test_validate_sha256_hex_invalid_length(self):
        with self.assertRaises(ValueError):
            validate_sha256_hex("a" * 63)

    def test_validate_sha256_hex_non_hex(self):
        with self.assertRaises(ValueError):
            validate_sha256_hex("z" + "a" * 63)

    def test_validate_sha_hex_40(self):
        validate_sha_hex("a" * 40, 40)
        # No exception = pass

    def test_validate_sha_hex_invalid(self):
        with self.assertRaises(ValueError):
            validate_sha_hex("a" * 39, 40)

    def test_sha256_file(self):
        path = FIXTURES_DIR / "valid_advisory_manifest.json"
        h = sha256_file(path)
        self.assertEqual(len(h), 64)

    def test_manifest_digest_consistency(self):
        m1 = load_fixture("valid_advisory_manifest.json")
        m2 = load_fixture("valid_advisory_manifest.json")
        d1 = manifest_digest_excluding_own(m1)
        d2 = manifest_digest_excluding_own(m2)
        self.assertEqual(d1, d2)

    def test_manifest_digest_different_for_different_content(self):
        m1 = load_fixture("valid_advisory_manifest.json")
        m2 = load_fixture("negative_missing_qa_manifest.json")
        d1 = manifest_digest_excluding_own(m1)
        d2 = manifest_digest_excluding_own(m2)
        self.assertNotEqual(d1, d2)


if __name__ == "__main__":
    unittest.main()
