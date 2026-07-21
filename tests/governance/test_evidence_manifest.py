"""Tests for evidence manifest validation and canonical hashing."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

import collect_evidence  # noqa: E402
from check_evidence_manifest import _command_matches_registry, check as check_manifest  # noqa: E402
from hash_tree import (  # noqa: E402
    canonical_json,
    canonical_json_sha256,
    manifest_digest_excluding_own,
    sha256_file,
    sha256_text,
    validate_sha_hex,
    validate_sha256_hex,
)
from json_schema import load_json_strict, validate_schema  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[2]


def load_fixture(name: str):
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


class TestEvidenceManifestValidation(unittest.TestCase):
    def test_collector_emits_schema_valid_candidate_pin(self):
        candidate_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
        pinned_at = "2026-07-21T15:40:44+00:00"

        def command(registry_id, argv, repo_root, category, phase="pre_merge"):
            return {
                "command_id": registry_id,
                "registry_id": registry_id,
                "category": category,
                "phase": phase,
                "argv": argv,
                "cwd": str(repo_root),
                "exit_code": 0,
                "stdout_sha256": "0" * 64,
                "stderr_sha256": "0" * 64,
                "started_at": pinned_at,
                "finished_at": pinned_at,
            }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "manifest.json"
            argv = [
                "collect_evidence.py",
                "--run-id", "collector-schema-regression",
                "--candidate-sha", candidate_sha,
                "--base-sha", candidate_sha,
                "--target-branch", "dev",
                "--candidate-branch", "issue-32-canonical-roadmap",
                "--repo-root", str(REPO_ROOT),
                "--policy-root", str(REPO_ROOT),
                "--candidate-pinned-at", pinned_at,
                "--output", str(output),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                collect_evidence, "run_command", side_effect=command
            ):
                self.assertEqual(collect_evidence.main(), 0)
            manifest = load_json_strict(output)

        schema = load_json_strict(
            REPO_ROOT / "governance/schemas/evidence-manifest.schema.json"
        )
        self.assertEqual(manifest["repo"]["candidate_pinned_at"], pinned_at)
        self.assertEqual(validate_schema(manifest, schema), [])
        errors = check_manifest(manifest, target_branch="dev")
        self.assertFalse(any("candidate_pinned_at" in error for error in errors))
        self.assertFalse(any("state_transition" in error for error in errors))

    def test_registry_templates_match_standalone_and_embedded_placeholders(self):
        registry = {
            "example": {
                "category": "gate",
                "argv": [
                    "command",
                    "{{manifest_path}}",
                    "--lease=main:{{old_sha}}",
                ],
                "placeholder_grammars": {
                    "manifest_path": "^/(?!.*\\.\\.)[A-Za-z0-9._/-]+$",
                    "old_sha": "^[a-f0-9]{40}$",
                },
            }
        }
        command = {
            "category": "gate",
            "argv": ["command", "/tmp/manifest.json", "--lease=main:" + "a" * 40],
        }
        self.assertTrue(_command_matches_registry(command, "example", registry))
        for malformed in [
            "--lease=dev:" + "a" * 40,
            "--lease=main:" + "a" * 40 + " --evil",
            "--lease=main:../escape",
        ]:
            command["argv"][2] = malformed
            self.assertFalse(_command_matches_registry(command, "example", registry))
        command["argv"] = [
            "command",
            "/tmp/manifest.json --evil",
            "--lease=main:" + "a" * 40,
        ]
        self.assertFalse(_command_matches_registry(command, "example", registry))
        command["argv"][1] = "/tmp/../manifest.json"
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
