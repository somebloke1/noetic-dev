"""Tests for the fail-closed delivery gate."""

from __future__ import annotations

import copy
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

import check_delivery_gate as delivery_gate
from check_delivery_gate import (
    check_bootstrap_blocked,
    check_delivery,
    check_pinning,
    verify_authoritative_provenance,
)
from hash_tree import canonical_json_sha256, manifest_digest_excluding_own

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[2]


def load_fixture(name: str):
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def advisory_external():
    return load_fixture("advisory_external_evidence.json")


def pr_api_response(
    number: int,
    head_ref: str,
    head_sha: str,
    linked_issues: list[int],
    fetched_at: str,
):
    response = {
        "number": number,
        "state": "open",
        "head_ref": head_ref,
        "head_sha": head_sha,
        "base_ref": "dev",
        "linked_issues": linked_issues,
    }
    return {
        "request_url": f"https://api.github.com/repos/somebloke1/noetic-dev/pulls/{number}",
        "status": 200,
        "request_id": f"request-{number}",
        "fetched_at": fetched_at,
        "authentication": {
            "verified": True,
            "source": "protected-integration",
            "principal": "noetic-dev-delivery-app",
        },
        "response_sha256": canonical_json_sha256(response),
        "response": response,
    }


def github_api_response(request_url: str, response) -> dict:
    return {
        "request_url": request_url,
        "status": 200,
        "request_id": "request-1",
        "fetched_at": "2026-07-11T11:59:59.500000+00:00",
        "authentication": {
            "verified": True,
            "source": "protected-integration",
            "principal": "noetic-dev-delivery-app",
        },
        "response_sha256": canonical_json_sha256(response),
        "response": response,
    }


def resign_response(envelope: dict) -> None:
    envelope["response_sha256"] = canonical_json_sha256(envelope["response"])


def protected_attestation_receipt() -> dict:
    return {
        "schema_version": "1",
        "receipt_id": "receipt-1",
        "provider": "protected-integration",
        "issued_at": "2026-07-11T11:59:59.600000+00:00",
        "expires_at": "2026-07-11T12:04:59.600000+00:00",
        "subject": {"digest": "sha256:" + "9" * 64},
        "claims": {"repository": "somebloke1/noetic-dev"},
        "proof": {
            "format": "protected-integration-receipt-v1",
            "key_id": "protected-delivery-v1",
            "payload_sha256": "8" * 64,
            "signature": "opaque-verifier-proof",
        },
    }


def bind_external_evidence(manifest: dict, external: dict) -> None:
    promotion = external.get("promotion_authorization", {})
    freeze = external.get("freeze_review", {})
    external["artifact"]["manifest_sha256"] = manifest_digest_excluding_own(manifest)
    external["artifact"]["promotion_authorization_sha256"] = canonical_json_sha256(promotion)
    external["artifact"]["freeze_review_sha256"] = canonical_json_sha256(freeze)
    external["artifact"]["freeze_review_pr_api_sha256"] = canonical_json_sha256(
        freeze.get("pr_api_response", {})
    )
    external["artifact"]["review_evidence_sha256"] = canonical_json_sha256(
        {
            "agent_identities": external.get("agent_identities", []),
            "approvals": external.get("approvals", []),
            "promotion_authorization": promotion,
            "freeze_review": freeze,
        }
    )


def promotion_authorization(manifest: dict) -> dict:
    candidate_sha = manifest["repo"]["candidate_sha"]
    with open(REPO_ROOT / "governance/protected-dev-ruleset.json", encoding="utf-8") as file:
        policy = json.load(file)
    ruleset = copy.deepcopy(policy["ruleset"])
    ruleset["created_at"] = "2026-07-11T10:00:00+00:00"
    ruleset["updated_at"] = "2026-07-11T11:00:00+00:00"
    ruleset_id = ruleset["id"]
    applied_rules = [
        {**copy.deepcopy(rule), "ruleset_id": ruleset_id}
        for rule in policy["applied_rules"]
    ]
    run_id = 123
    run = {
        "id": run_id,
        "repository": {"full_name": "somebloke1/noetic-dev"},
        "path": ".github/workflows/governance.yml",
        "event": "push",
        "head_branch": "dev",
        "head_sha": candidate_sha,
        "status": "completed",
        "conclusion": "success",
        "html_url": f"https://github.com/somebloke1/noetic-dev/actions/runs/{run_id}",
        "created_at": "2026-07-11T11:59:57+00:00",
        "updated_at": "2026-07-11T11:59:58+00:00",
    }
    return {
        "authorized": True,
        "authorized_by": "somebloke1",
        "dev_sha": candidate_sha,
        "dev_validation_sha": candidate_sha,
        "dev_provenance": {
            "branch_api_response": github_api_response(
                "https://api.github.com/repos/somebloke1/noetic-dev/branches/dev",
                {"name": "dev", "protected": True, "commit": {"sha": candidate_sha}},
            ),
            "applied_rules_api_response": github_api_response(
                "https://api.github.com/repos/somebloke1/noetic-dev/rules/branches/dev",
                applied_rules,
            ),
            "ruleset_api_response": github_api_response(
                f"https://api.github.com/repos/somebloke1/noetic-dev/rulesets/{ruleset_id}",
                ruleset,
            ),
            "validation_run_api_response": github_api_response(
                f"https://api.github.com/repos/somebloke1/noetic-dev/actions/runs/{run_id}",
                run,
            ),
        },
        "issue": 32,
        "comment_id": 1,
        "comment_source": "github_api",
        "comment_verified": True,
        "comment_author": "somebloke1",
        "comment_author_association": "OWNER",
        "comment_body": f"noetic-dev-main-promotion: authorize {candidate_sha}",
        "comment_created_at": "2026-07-11T11:59:59+00:00",
        "authorization_url": "https://github.com/somebloke1/noetic-dev/issues/32#issuecomment-1",
        "authorized_at": "2026-07-11T11:59:59+00:00",
        "dev_validated_at": "2026-07-11T11:59:58+00:00",
    }


class TestDeliveryGatePositive(unittest.TestCase):
    def test_main_promotion_requires_exact_owner_authorization(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        _passed, errors, _gate_type = check_delivery(manifest, external_evidence=external)
        self.assertIn("owner promotion authorization missing", "\n".join(errors))

        external["promotion_authorization"] = promotion_authorization(manifest)
        _passed, errors, _gate_type = check_delivery(manifest, external_evidence=external)
        self.assertNotIn("owner promotion authorization missing", "\n".join(errors))
        self.assertNotIn("owner-authorized dev SHA", "\n".join(errors))

        external["promotion_authorization"]["dev_sha"] = "0" * 40
        _passed, errors, _gate_type = check_delivery(manifest, external_evidence=external)
        self.assertIn("owner-authorized dev SHA", "\n".join(errors))

        external["promotion_authorization"]["dev_sha"] = manifest["repo"]["candidate_sha"]
        external["promotion_authorization"]["authorized_at"] = "2026-07-11T11:59:57+00:00"
        external["promotion_authorization"]["comment_created_at"] = "2026-07-11T11:59:57+00:00"
        _passed, errors, _gate_type = check_delivery(manifest, external_evidence=external)
        self.assertIn("must follow protected dev validation", "\n".join(errors))

        external["promotion_authorization"]["authorized_at"] = "2026-07-11T11:59:59+00:00"
        external["promotion_authorization"]["comment_created_at"] = "2026-07-11T11:59:59+00:00"
        external["promotion_authorization"]["dev_validated_at"] = "2026-07-11T11:59:59+00:00"
        run_envelope = external["promotion_authorization"]["dev_provenance"]["validation_run_api_response"]
        run_envelope["response"]["updated_at"] = "2026-07-11T11:59:59+00:00"
        resign_response(run_envelope)
        external["promotion_authorization"]["comment_body"] = "unrelated checkpoint"
        _passed, errors, _gate_type = check_delivery(manifest, external_evidence=external)
        joined = "\n".join(errors)
        self.assertIn("must follow protected dev validation", joined)
        self.assertIn("exact affirmative record", joined)

    def test_main_promotion_requires_authenticated_protected_dev_validation(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        candidate_sha = manifest["repo"]["candidate_sha"]

        external = advisory_external()
        external["promotion_authorization"] = promotion_authorization(manifest)
        _passed, errors, _gate_type = check_delivery(manifest, external_evidence=external)
        self.assertIn("pull request head must be protected dev", "\n".join(errors))

        manifest["repo"]["candidate_branch"] = "dev"
        manifest["pull_request"]["head_ref"] = "dev"
        external["promotion_authorization"] = promotion_authorization(manifest)
        _passed, errors, _gate_type = check_delivery(manifest, external_evidence=external)
        self.assertNotIn("pull request head must be protected dev", "\n".join(errors))

        branch_attacks = [
            ("name", "main"),
            ("protected", False),
            ("commit", {"sha": "0" * 40}),
        ]
        for field, value in branch_attacks:
            with self.subTest(field=field):
                external = advisory_external()
                external["promotion_authorization"] = promotion_authorization(manifest)
                envelope = external["promotion_authorization"]["dev_provenance"]["branch_api_response"]
                envelope["response"][field] = value
                resign_response(envelope)
                _passed, errors, _gate_type = check_delivery(manifest, external_evidence=external)
                self.assertIn("authenticated protected dev head", "\n".join(errors))

        external = advisory_external()
        external["promotion_authorization"] = promotion_authorization(manifest)
        envelope = external["promotion_authorization"]["dev_provenance"]["branch_api_response"]
        envelope["response"]["protected"] = False
        _passed, errors, _gate_type = check_delivery(manifest, external_evidence=external)
        self.assertIn("response digest mismatch", "\n".join(errors))

        external = advisory_external()
        external["promotion_authorization"] = promotion_authorization(manifest)
        envelope = external["promotion_authorization"]["dev_provenance"]["branch_api_response"]
        envelope["authentication"]["verified"] = False
        _passed, errors, _gate_type = check_delivery(manifest, external_evidence=external)
        self.assertIn("response is not authenticated", "\n".join(errors))

        rule_attacks = ["empty-applied", "bypass", "inactive", "missing-check"]
        for attack in rule_attacks:
            with self.subTest(rule_attack=attack):
                external = advisory_external()
                external["promotion_authorization"] = promotion_authorization(manifest)
                provenance = external["promotion_authorization"]["dev_provenance"]
                applied = provenance["applied_rules_api_response"]
                ruleset = provenance["ruleset_api_response"]
                if attack == "empty-applied":
                    applied["response"] = []
                    resign_response(applied)
                elif attack == "bypass":
                    ruleset["response"]["bypass_actors"] = [{"actor_type": "User", "actor_id": 1}]
                    resign_response(ruleset)
                elif attack == "inactive":
                    ruleset["response"]["enforcement"] = "disabled"
                    resign_response(ruleset)
                else:
                    status_rule = next(
                        rule for rule in ruleset["response"]["rules"]
                        if rule["type"] == "required_status_checks"
                    )
                    status_rule["parameters"]["required_status_checks"].pop()
                    resign_response(ruleset)
                _passed, errors, _gate_type = check_delivery(manifest, external_evidence=external)
                self.assertIn("rules are absent, bypassable, stale, or missing required checks", "\n".join(errors))

        run_attacks = [
            ("head_sha", "0" * 40),
            ("event", "pull_request"),
            ("head_branch", "main"),
            ("conclusion", "failure"),
            ("status", "in_progress"),
            ("path", ".github/workflows/other.yml"),
            ("html_url", "https://github.com/somebloke1/noetic-dev/actions/runs/999"),
        ]
        for field, value in run_attacks:
            with self.subTest(run_field=field):
                external = advisory_external()
                external["promotion_authorization"] = promotion_authorization(manifest)
                envelope = external["promotion_authorization"]["dev_provenance"]["validation_run_api_response"]
                run = envelope["response"]
                run[field] = value
                resign_response(envelope)
                _passed, errors, _gate_type = check_delivery(manifest, external_evidence=external)
                self.assertIn("validation run is not bound", "\n".join(errors))

        external = advisory_external()
        external["promotion_authorization"] = promotion_authorization(manifest)
        envelope = external["promotion_authorization"]["dev_provenance"]["validation_run_api_response"]
        envelope["response"]["updated_at"] = "2026-07-11T11:59:57+00:00"
        resign_response(envelope)
        _passed, errors, _gate_type = check_delivery(manifest, external_evidence=external)
        self.assertIn("timestamp does not match the authenticated run", "\n".join(errors))

        external = advisory_external()
        external["promotion_authorization"] = promotion_authorization(manifest)
        envelope = external["promotion_authorization"]["dev_provenance"]["branch_api_response"]
        envelope["fetched_at"] = "2026-07-11T11:59:58+00:00"
        _passed, errors, _gate_type = check_delivery(manifest, external_evidence=external)
        self.assertIn("captures must follow authorization", "\n".join(errors))

        external = advisory_external()
        external["promotion_authorization"] = promotion_authorization(manifest)
        envelope = external["promotion_authorization"]["dev_provenance"]["branch_api_response"]
        envelope["fetched_at"] = external["promotion_authorization"]["authorized_at"]
        _passed, errors, _gate_type = check_delivery(manifest, external_evidence=external)
        self.assertIn("captures must follow authorization", "\n".join(errors))

        external = advisory_external()
        external["promotion_authorization"] = promotion_authorization(manifest)
        provenance = external["promotion_authorization"]["dev_provenance"]
        self.assertEqual(provenance["branch_api_response"]["response"]["commit"]["sha"], candidate_sha)
        self.assertEqual(
            provenance["validation_run_api_response"]["response"]["head_sha"], candidate_sha
        )

    def test_main_promotion_rejects_missing_invalid_or_retroactive_pin_time(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        for value in [None, 1, {}, [], "not-a-time", "2026-07-11T12:00:00"]:
            with self.subTest(value=value):
                attacked = copy.deepcopy(manifest)
                if value is None:
                    attacked["repo"].pop("candidate_pinned_at")
                else:
                    attacked["repo"]["candidate_pinned_at"] = value
                external = advisory_external()
                external["promotion_authorization"] = promotion_authorization(attacked)
                _passed, errors, _gate_type = check_delivery(attacked, external_evidence=external)
                self.assertIn("candidate pin timestamp is missing or invalid", "\n".join(errors))

        manifest["repo"]["candidate_pinned_at"] = "2026-07-11T11:59:59+00:00"
        external = advisory_external()
        external["promotion_authorization"] = promotion_authorization(manifest)
        _passed, errors, _gate_type = check_delivery(manifest, external_evidence=external)
        self.assertIn("authorization must precede candidate pinning", "\n".join(errors))

    def test_dev_integration_mode_accepts_dev_shape_until_external_authority_gate(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        manifest["repo"]["base_branch"] = "dev"
        manifest["pull_request"]["base"] = "dev"
        ready_index = next(
            index
            for index, transition in enumerate(manifest["state_transitions"])
            if transition["to"] == "READY_TO_MERGE"
        )
        manifest["state_transitions"] = manifest["state_transitions"][: ready_index + 1]
        manifest["state_transitions"][-1]["to"] = "READY_TO_INTEGRATE_DEV"

        external = advisory_external()
        external["run"]["base_branch"] = "dev"
        external["pull_request"]["base_ref"] = "dev"
        external.pop("promotion_authorization", None)
        external.pop("freeze_review", None)
        external["artifact"]["manifest_sha256"] = manifest_digest_excluding_own(manifest)
        promotion_digest = canonical_json_sha256({})
        freeze_digest = canonical_json_sha256({})
        review_digest = canonical_json_sha256(
            {
                "agent_identities": external["agent_identities"],
                "approvals": external["approvals"],
                "promotion_authorization": {},
                "freeze_review": {},
            }
        )
        external["artifact"]["review_evidence_sha256"] = review_digest
        external["artifact"]["promotion_authorization_sha256"] = promotion_digest
        external["artifact"]["freeze_review_sha256"] = freeze_digest
        external["artifact"]["freeze_review_pr_api_sha256"] = canonical_json_sha256({})

        passed, errors, gate_type = check_delivery(
            manifest,
            external_evidence=external,
            gate_mode="dev-integration",
        )
        joined = "\n".join(errors)
        self.assertFalse(passed)
        self.assertEqual(gate_type, "dev-integration")
        self.assertIn("caller-supplied external evidence is advisory only", joined)
        self.assertNotIn("must be main", joined)
        self.assertNotIn("must both be main", joined)
        self.assertNotIn("owner promotion authorization", joined)
        self.assertNotIn("not eligible for pre-merge", joined)

    def test_attestation_digest_detects_authorization_substitution(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["promotion_authorization"] = promotion_authorization(manifest)
        promotion_digest = canonical_json_sha256(external["promotion_authorization"])
        freeze_digest = canonical_json_sha256({})
        review_digest = canonical_json_sha256(
            {
                "agent_identities": external["agent_identities"],
                "approvals": external["approvals"],
                "promotion_authorization": external["promotion_authorization"],
                "freeze_review": {},
            }
        )
        external["artifact"]["promotion_authorization_sha256"] = promotion_digest
        external["artifact"]["freeze_review_sha256"] = freeze_digest
        external["artifact"]["freeze_review_pr_api_sha256"] = canonical_json_sha256({})
        external["artifact"]["review_evidence_sha256"] = review_digest

        external["promotion_authorization"]["dev_sha"] = "0" * 40
        errors = verify_authoritative_provenance(manifest, external)
        joined = "\n".join(errors)
        self.assertIn("promotion authorization evidence digest mismatch", joined)
        self.assertIn("review identity/approval evidence digest mismatch", joined)

    def test_self_consistent_external_evidence_remains_advisory(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        passed, errors, gate_type = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertEqual(gate_type, "main-promotion")
        joined = "\n".join(errors)
        self.assertIn("caller-supplied external evidence is advisory only", joined)
        self.assertIn("credential_broker_established", joined)
        self.assertNotIn("canonical manifest digest mismatch", joined)

    def test_github_api_mode_cannot_establish_review_authority(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("protected integration receipt is required", "\n".join(errors))

    def test_self_consistent_outer_evidence_requires_independent_receipt_verification(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["mode"] = "protected_integration_receipt"
        external["promotion_authorization"] = promotion_authorization(manifest)
        external["protected_attestation_receipt"] = protected_attestation_receipt()
        bind_external_evidence(manifest, external)

        with mock.patch(
            "check_delivery_gate._verify_protected_attestation_receipt", return_value=False
        ) as verifier:
            errors = verify_authoritative_provenance(manifest, external)
        self.assertIn("receipt is not independently verified", "\n".join(errors))
        expected_claims = verifier.call_args.args[1]
        self.assertEqual(expected_claims["head_sha"], manifest["repo"]["candidate_sha"])
        self.assertEqual(
            expected_claims["dev_provenance_sha256"],
            canonical_json_sha256(external["promotion_authorization"]["dev_provenance"]),
        )

        external["promotion_authorization"]["dev_sha"] = "0" * 40
        external["protected_attestation_receipt"]["claims"]["head_sha"] = "0" * 40
        external["protected_attestation_receipt"]["proof"]["payload_sha256"] = "7" * 64
        bind_external_evidence(manifest, external)
        with mock.patch(
            "check_delivery_gate._verify_protected_attestation_receipt", return_value=False
        ):
            errors = verify_authoritative_provenance(manifest, external)
        joined = "\n".join(errors)
        self.assertIn("receipt is not independently verified", joined)
        self.assertNotIn("promotion authorization evidence digest mismatch", joined)

        with mock.patch(
            "check_delivery_gate._verify_protected_attestation_receipt", return_value=True
        ):
            errors = verify_authoritative_provenance(manifest, external)
        self.assertNotIn("receipt is not independently verified", "\n".join(errors))

    def test_receipt_mode_rejects_omitted_malformed_and_legacy_receipts_before_verifier(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["mode"] = "protected_integration_receipt"
        external["promotion_authorization"] = promotion_authorization(manifest)
        bind_external_evidence(manifest, external)

        with mock.patch(
            "check_delivery_gate._verify_protected_attestation_receipt", return_value=True
        ) as verifier:
            errors = verify_authoritative_provenance(manifest, external)
        joined = "\n".join(errors)
        self.assertIn("missing required property protected_attestation_receipt", joined)
        self.assertIn("protected attestation receipt schema", joined)
        verifier.assert_not_called()

        external["protected_attestation_receipt"] = protected_attestation_receipt()
        external["protected_attestation_receipt"].pop("proof")
        with mock.patch(
            "check_delivery_gate._verify_protected_attestation_receipt", return_value=True
        ) as verifier:
            errors = verify_authoritative_provenance(manifest, external)
        self.assertIn("protected attestation receipt schema", "\n".join(errors))
        verifier.assert_not_called()

        external["protected_attestation_receipt"] = protected_attestation_receipt()
        external["signed_attestation"] = {"verified": True}
        with mock.patch(
            "check_delivery_gate._verify_protected_attestation_receipt", return_value=True
        ):
            errors = verify_authoritative_provenance(manifest, external)
        self.assertIn("additional property not allowed: signed_attestation", "\n".join(errors))

    def test_protected_receipt_verifier_protocol_fails_closed(self):
        receipt = protected_attestation_receipt()
        expected_claims = {"head_sha": "d" * 40}
        with mock.patch.object(
            delivery_gate,
            "PROTECTED_ATTESTATION_VERIFIER",
            Path("/definitely/missing/verify-delivery-attestation"),
        ):
            self.assertFalse(
                delivery_gate._verify_protected_attestation_receipt(receipt, expected_claims)
            )

        completed = subprocess.CompletedProcess([], 0)
        with mock.patch(
            "check_delivery_gate._trusted_root_executable", return_value=True
        ), mock.patch("check_delivery_gate.subprocess.run", return_value=completed) as run:
            self.assertTrue(
                delivery_gate._verify_protected_attestation_receipt(receipt, expected_claims)
            )
        challenge = json.loads(run.call_args.kwargs["input"])
        self.assertEqual(challenge["receipt"], receipt)
        self.assertEqual(challenge["expected_claims"], expected_claims)
        self.assertEqual(run.call_args.kwargs["stdout"], subprocess.DEVNULL)
        self.assertEqual(run.call_args.kwargs["stderr"], subprocess.DEVNULL)
        self.assertEqual(run.call_args.kwargs["timeout"], 30)

        with mock.patch(
            "check_delivery_gate._trusted_root_executable", return_value=True
        ), mock.patch(
            "check_delivery_gate.subprocess.run",
            return_value=subprocess.CompletedProcess([], 1),
        ):
            self.assertFalse(
                delivery_gate._verify_protected_attestation_receipt(receipt, expected_claims)
            )

        for value in [float("nan"), float("inf"), float("-inf")]:
            with self.subTest(non_finite=value):
                attacked = copy.deepcopy(receipt)
                attacked["claims"]["non_finite"] = value
                with mock.patch(
                    "check_delivery_gate._trusted_root_executable", return_value=True
                ), mock.patch("check_delivery_gate.subprocess.run") as run:
                    self.assertFalse(
                        delivery_gate._verify_protected_attestation_receipt(
                            attacked, expected_claims
                        )
                    )
                run.assert_not_called()

    def test_valid_advisory_is_blocked_without_external_evidence(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        passed, errors, gate_type = check_delivery(manifest)
        self.assertFalse(passed)
        self.assertEqual(gate_type, "main-promotion")
        self.assertIn("authoritative trusted runner", " ".join(errors).lower())

    def test_publication_remains_blocked_by_missing_release_authority(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        passed, errors, gate_type = check_delivery(manifest, external_evidence=advisory_external(), phase="publication")
        self.assertFalse(passed)
        self.assertEqual(gate_type, "publication")
        joined = "\n".join(errors)
        self.assertIn("publication blocked", joined)
        self.assertIn("freeze/audit is still active", joined)
        self.assertIn("protected independent freeze review evidence missing", joined)

    def test_publication_rejects_freeze_review_digest_mismatch(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["freeze_review"] = {
            "verdict": "pass",
            "independent": True,
            "audit_sha256": "0" * 64,
            "reviewed_candidate_sha": "1" * 40,
            "pull_request": 67,
            "pr_source": "github_api",
            "pr_verified": True,
            "pr_head_ref": "issue-32-canonical-roadmap",
            "pr_base_ref": "dev",
            "pr_head_sha": "1" * 40,
            "pr_linked_issues": [32],
            "pr_api_response": pr_api_response(
                67,
                "issue-32-canonical-roadmap",
                "1" * 40,
                [32],
                "2026-07-18T23:46:08Z",
            ),
            "dev_integration_sha": "2" * 40,
            "dev_contains_integration_sha": True,
            "issue": 32,
            "head": "issue-32-canonical-roadmap",
            "base": "dev",
            "evidence_url": "https://github.com/somebloke1/noetic-dev/issues/32#issuecomment-1",
            "reviewed_at": "2026-07-18T23:46:09Z",
        }
        _passed, errors, _gate_type = check_delivery(
            manifest,
            external_evidence=external,
            phase="publication",
        )
        self.assertIn("freeze review audit digest mismatch", "\n".join(errors))

    def test_publication_binds_freeze_review_url_and_time_to_local_completion(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        local_freeze = load_fixture("advisory_external_evidence.json")["freeze"]
        local_freeze.update(
            {
                "status": "complete",
                "blocks_publication": False,
                "independent_review_completed": True,
                "audit_sha256": "a" * 64,
                "reviewed_candidate_sha": "1" * 40,
                "reviewed_pull_request": 67,
                "dev_integration_sha": "2" * 40,
                "reviewed_at": "2026-07-19T00:10:00Z",
                "review_evidence_url": "https://github.com/somebloke1/noetic-dev/pull/67#issuecomment-10",
                "captured_at": "2026-07-18T23:46:09Z",
                "authorized_repair": {
                    "issue": 32,
                    "head": "issue-32-canonical-roadmap",
                    "base": "dev",
                    "max_pull_requests": 1,
                },
            }
        )
        external["freeze"] = copy.deepcopy(local_freeze)
        external["freeze_review"] = {
            "verdict": "pass",
            "independent": True,
            "audit_sha256": "a" * 64,
            "reviewed_candidate_sha": "1" * 40,
            "pull_request": 67,
            "pr_source": "github_api",
            "pr_verified": True,
            "pr_head_ref": "issue-32-canonical-roadmap",
            "pr_base_ref": "dev",
            "pr_head_sha": "1" * 40,
            "pr_linked_issues": [32],
            "pr_api_response": pr_api_response(
                67,
                "issue-32-canonical-roadmap",
                "1" * 40,
                [32],
                "2026-07-19T00:09:00Z",
            ),
            "dev_integration_sha": "2" * 40,
            "dev_contains_integration_sha": True,
            "issue": 32,
            "head": "issue-32-canonical-roadmap",
            "base": "dev",
            "evidence_url": "https://github.com/somebloke1/noetic-dev/pull/67#issuecomment-11",
            "reviewed_at": "2026-07-19T00:11:00Z",
        }
        with mock.patch("check_delivery_gate._protected_freeze", return_value=local_freeze):
            _passed, errors, _gate_type = check_delivery(
                manifest,
                external_evidence=external,
                phase="publication",
            )
        joined = "\n".join(errors)
        self.assertIn("freeze review evidence URL mismatch", joined)
        self.assertIn("freeze review timestamp mismatch", joined)

        unrelated_sha = "8fcb1c509b14f10f1f7e2ef2363ffb98996fa46b"
        local_freeze["reviewed_candidate_sha"] = unrelated_sha
        local_freeze["reviewed_pull_request"] = 66
        local_freeze["review_evidence_url"] = (
            "https://github.com/somebloke1/noetic-dev/pull/66#issuecomment-12"
        )
        external["freeze"] = copy.deepcopy(local_freeze)
        external["freeze_review"].update(
            {
                "reviewed_candidate_sha": unrelated_sha,
                "pull_request": 66,
                "pr_head_ref": "issue-65-opencode-spike",
                "pr_head_sha": unrelated_sha,
                "pr_linked_issues": [],
                "pr_api_response": pr_api_response(
                    66,
                    "issue-65-opencode-spike",
                    unrelated_sha,
                    [],
                    "2026-07-19T00:09:00Z",
                ),
                "evidence_url": local_freeze["review_evidence_url"],
                "reviewed_at": local_freeze["reviewed_at"],
            }
        )
        with mock.patch("check_delivery_gate._protected_freeze", return_value=local_freeze):
            _passed, errors, _gate_type = check_delivery(
                manifest,
                external_evidence=external,
                phase="publication",
            )
        joined = "\n".join(errors)
        self.assertIn("freeze review PR head ref mismatch", joined)
        self.assertIn("freeze review PR must link only issue 32", joined)

        local_freeze["reviewed_candidate_sha"] = "1" * 40
        local_freeze["reviewed_pull_request"] = 67
        local_freeze["review_evidence_url"] = (
            "https://github.com/somebloke1/noetic-dev/pull/67#issuecomment-10"
        )
        external["freeze"] = copy.deepcopy(local_freeze)
        external["freeze_review"].update(
            {
                "reviewed_candidate_sha": "1" * 40,
                "pull_request": 67,
                "pr_head_ref": "issue-32-canonical-roadmap",
                "pr_head_sha": "1" * 40,
                "pr_linked_issues": [32],
                "evidence_url": local_freeze["review_evidence_url"],
                "reviewed_at": local_freeze["reviewed_at"],
                "pr_api_response": pr_api_response(
                    67,
                    "issue-32-canonical-roadmap",
                    "1" * 40,
                    [32],
                    "2026-07-19T00:09:00Z",
                ),
            }
        )
        external["freeze_review"]["pr_api_response"]["response"]["head_sha"] = "3" * 40
        with mock.patch("check_delivery_gate._protected_freeze", return_value=local_freeze):
            _passed, errors, _gate_type = check_delivery(
                manifest,
                external_evidence=external,
                phase="publication",
            )
        joined = "\n".join(errors)
        self.assertIn("PR API response digest mismatch", joined)
        self.assertIn("fields do not derive from PR API response", joined)

        external["freeze_review"]["pr_api_response"] = pr_api_response(
            67,
            "issue-32-canonical-roadmap",
            "1" * 40,
            [32],
            "2026-07-19T00:10:01Z",
        )
        with mock.patch("check_delivery_gate._protected_freeze", return_value=local_freeze):
            _passed, errors, _gate_type = check_delivery(
                manifest,
                external_evidence=external,
                phase="publication",
            )
        self.assertIn("PR API capture postdates review", "\n".join(errors))

    def test_multigeneration_history_is_valid_except_external_authority(self):
        manifest = load_fixture("valid_multigeneration_advisory_manifest.json")
        passed, errors, gate_type = check_delivery(manifest)
        self.assertFalse(passed)
        self.assertEqual(gate_type, "main-promotion")
        joined = "\n".join(errors)
        self.assertIn("authoritative trusted runner", joined)
        self.assertNotIn("stale candidate", joined)
        self.assertNotIn("stale base", joined)
        self.assertNotIn("candidate_tree_oid mismatch", joined)

    def test_bootstrap_blocked_check_passes_while_dependencies_unresolved(self):
        passed, errors = check_bootstrap_blocked()
        self.assertTrue(passed, errors)


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
        "negative_mutable_action_manifest.json": "workflow.pinning",
        "negative_branch_publication_manifest.json": "branch-name publication forbidden",
        "negative_unsupported_model_manifest.json": "unsupported model profile",
        "negative_two_qas_one_pass_manifest.json": "multiple QA",
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
                passed, errors, _gate_type = check_delivery(manifest, external_evidence=advisory_external())
                self.assertFalse(passed, f"{fixture_name} unexpectedly passed")
                joined = "\n".join(errors)
                self.assertIn(expected, joined, f"{fixture_name} errors were: {errors}")


class TestExternalEvidenceFailures(unittest.TestCase):
    def test_manifest_only_trusted_runner_is_rejected(self):
        result = subprocess.run(
            [sys.executable, "scripts/governance/check_evidence_manifest.py", str(FIXTURES_DIR / "negative_manifest_only_authoritative_manifest.json")],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manifest-only authority claim", result.stderr)

    def test_external_artifact_digest_mismatch_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["artifact"]["digest"] = "sha256:" + "8" * 64
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("artifact digest mismatch", "\n".join(errors))

    def test_external_policy_hash_mismatch_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["policy_file_hashes"][manifest["policy"]["generator_path"]] = "0" * 64
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("policy generator_sha256", "\n".join(errors))

    def test_author_approval_rejected_from_external_evidence(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        author = manifest["pull_request"]["author"]
        external["approvals"][0]["reviewer"] = author
        external["approvals"][0]["agent_id"] = author
        external["approvals"][0]["identity_binding"]["subject"] = author
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("PR author", "\n".join(errors))

    def test_stale_approval_rejected_from_external_evidence(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["submitted_at"] = "2026-07-11T11:59:00+00:00"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("predates candidate", "\n".join(errors))

    def test_unapproved_model_profile_rejected_from_external_evidence(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["model_profile"] = "qa_primary"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("authorized independent reviewer profile", "\n".join(errors))

    def test_low_reasoning_approval_rejected_from_external_evidence(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["reasoning_level"] = "low"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("did not use high reasoning", "\n".join(errors))

    def test_reviewer_alias_is_rejected_from_external_evidence(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["reviewer"] = "alias-for-same-agent"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("not bound to protected agent_id", "\n".join(errors))

    def test_reviewer_role_run_reuse_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["role_run_id"] = manifest["passes"]["pass_records"][0]["role_run_id"]
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("reused implementation role_run_id", "\n".join(errors))

    def test_unverified_identity_binding_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["identity_binding"]["verified"] = False
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("lacks verified protected-runner identity binding", "\n".join(errors))

    def test_incomplete_transition_path_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        manifest["state_transitions"] = manifest["state_transitions"][-2:]
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("required state_transition missing", "\n".join(errors))

    def test_discontinuous_transition_path_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        manifest["state_transitions"].pop(1)
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("state_transition path is discontinuous", "\n".join(errors))

    def test_equal_transition_timestamps_are_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        same = manifest["state_transitions"][0]["timestamp"]
        for transition in manifest["state_transitions"]:
            transition["timestamp"] = same
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("timestamp did not advance", "\n".join(errors))

    def test_blocked_terminal_state_is_not_merge_eligible(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        last_time = manifest["state_transitions"][-1]["timestamp"]
        manifest["state_transitions"].append({
            "from": manifest["state_transitions"][-1]["to"],
            "to": "BLOCKED",
            "authority": "orchestrator",
            "timestamp": last_time.replace("+00:00", ".999999+00:00"),
        })
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("is not eligible for pre-merge", "\n".join(errors))

    def test_coordinated_alias_without_canonical_principal_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        approval = external["approvals"][0]
        approval["reviewer"] = "fresh-coordinated-alias"
        approval["agent_id"] = "fresh-coordinated-alias"
        approval["identity_binding"]["subject"] = "fresh-coordinated-alias"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("no protected canonical principal", "\n".join(errors))

    def test_duplicate_reviewer_role_run_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"].append(copy.deepcopy(external["approvals"][0]))
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("duplicated reviewer role_run_id", "\n".join(errors))

    def test_reviewer_alias_bound_to_implementation_principal_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        reviewer = next(item for item in external["agent_identities"] if item["agent_id"] == "agent-reviewer-fable")
        reviewer["principal_id"] = "principal-implementer"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("protected canonical principal is assigned to multiple aliases", "\n".join(errors))

    def test_reviewer_alias_bound_to_author_principal_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        reviewer = next(item for item in external["agent_identities"] if item["agent_id"] == "agent-reviewer-fable")
        reviewer["principal_id"] = "principal-author"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("protected canonical principal is assigned to multiple aliases", "\n".join(errors))

    def test_duplicate_implementation_role_run_is_rejected(self):
        manifest = load_fixture("valid_multigeneration_advisory_manifest.json")
        records = manifest["passes"]["pass_records"]
        records[1]["role_run_id"] = records[0]["role_run_id"]
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("implementation/remediation role_run_id must be unique", "\n".join(errors))

    def test_duplicate_qa_role_run_is_rejected(self):
        manifest = load_fixture("valid_multigeneration_advisory_manifest.json")
        records = manifest["qa"]["records"]
        records[1]["role_run_id"] = records[0]["role_run_id"]
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("QA role_run_id must be unique", "\n".join(errors))

    def test_review_evidence_digest_mismatch_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["reasoning_level"] = "xhigh"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("review identity/approval evidence digest mismatch", "\n".join(errors))

    def test_naive_approval_timestamp_returns_controlled_failure(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["submitted_at"] = "2026-07-11T12:40:00"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("invalid timestamp", "\n".join(errors))

    def test_wrong_sha_approval_after_candidate_pin_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["commit_sha"] = "f" * 40
        external["approvals"][0]["submitted_at"] = "2026-07-11T12:40:00+00:00"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("wrong SHA", "\n".join(errors))

    def test_policy_ref_must_be_protected_full_sha_and_separate(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["protected_ref"]["protected"] = False
        external["checkouts"]["candidate_path"] = external["checkouts"]["policy_path"]
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        joined = "\n".join(errors)
        self.assertIn("policy ref is not independently protected", joined)
        self.assertIn("candidate checkout reused as policy checkout", joined)

    def test_candidate_controlled_or_short_policy_sha_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        manifest["policy"]["sha"] = manifest["repo"]["candidate_sha"]
        external["workflow"]["sha"] = manifest["policy"]["sha"]
        external["protected_ref"]["sha"] = manifest["policy"]["sha"]
        external["checkouts"]["policy_sha"] = manifest["policy"]["sha"]
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("candidate checkout reused as protected policy checkout", "\n".join(errors))

        manifest["policy"]["sha"] = "a" * 8
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("policy SHA must be full", "\n".join(errors))

    def test_manifest_generated_by_candidate_modifiable_code_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["generator"]["from_policy_checkout"] = False
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("candidate-modifiable code", "\n".join(errors))


class TestPublicationBindingFailures(unittest.TestCase):
    def _publication_candidate(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        publication_sha = "f" * 40
        manifest["publication"]["merge_result_sha"] = publication_sha
        manifest["publication"]["publication_sha"] = publication_sha
        for command in manifest["commands"]:
            if command.get("phase") == "post_merge":
                command["commit_sha"] = publication_sha
        external = advisory_external()
        external["artifact"]["manifest_sha256"] = manifest_digest_excluding_own(manifest)
        external["post_merge"] = {
            "event": "push",
            "ref": "refs/heads/main",
            "sha": publication_sha,
            "merge_result_sha": publication_sha,
            "merge_method": "squash",
            "main_contains_sha": True,
        }
        return manifest, external

    def test_premerge_postmerge_claim_cannot_satisfy_publication(self):
        manifest, external = self._publication_candidate()
        external["post_merge"]["event"] = "pull_request"
        passed, errors, gate_type = check_delivery(manifest, external_evidence=external, phase="publication")
        self.assertFalse(passed)
        self.assertEqual(gate_type, "publication")
        self.assertIn("push to refs/heads/main", "\n".join(errors))

    def test_non_main_publication_sha_rejected(self):
        manifest, external = self._publication_candidate()
        external["post_merge"]["ref"] = "refs/heads/feature"
        passed, errors, _ = check_delivery(manifest, external_evidence=external, phase="publication")
        self.assertFalse(passed)
        self.assertIn("refs/heads/main", "\n".join(errors))


class TestQaBindingFailures(unittest.TestCase):
    def _first_qa_with_rehashed_records(self, manifest):
        qa = manifest["qa"]["records"][0]
        qa["protected_execution_record_sha256"] = canonical_json_sha256(qa["protected_execution_record"])
        qa["protected_probe_record_sha256"] = canonical_json_sha256(qa["protected_probe_record"])
        return qa

    def test_execution_profile_must_match_protected_qa_profile(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        actual = qa["protected_execution_record"]["actual_invocation"]
        actual["profile_id"] = "implementer_candidate"
        actual["resolved_model"] = "litellm/deepseek-v4-flash"
        self._first_qa_with_rehashed_records(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("profile_id does not match", "\n".join(errors))

    def test_any_tool_in_authoritative_qa_record_rejected_until_broker_exists(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        qa["protected_execution_record"]["actual_invocation"]["tools"] = ["read"]
        qa["protected_probe_record"]["tools"] = ["read"]
        self._first_qa_with_rehashed_records(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("must use no tools until a credential broker exists", "\n".join(errors))

    def test_failed_or_non_ready_probe_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        probe = qa["protected_probe_record"]
        probe["observed_response"] = "not ready"
        probe["exit_code"] = 1
        self._first_qa_with_rehashed_records(manifest)
        external = advisory_external()
        external["artifact"]["manifest_sha256"] = manifest_digest_excluding_own(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        joined = "\n".join(errors)
        self.assertIn("READY nonce", joined)
        self.assertIn("probe exit code", joined)

    def test_probe_after_qa_start_is_stale(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        qa["protected_probe_record"]["finished_at"] = "2026-07-11T12:08:00+00:00"
        self._first_qa_with_rehashed_records(manifest)
        external = advisory_external()
        external["artifact"]["manifest_sha256"] = manifest_digest_excluding_own(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("probe finished after QA started", "\n".join(errors))

    def test_probe_candidate_and_pi_version_must_match_execution(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        probe = qa["protected_probe_record"]
        probe["candidate_sha"] = "f" * 40
        probe["pi_version"] = "pi 9.9.9"
        self._first_qa_with_rehashed_records(manifest)
        external = advisory_external()
        external["artifact"]["manifest_sha256"] = manifest_digest_excluding_own(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        joined = "\n".join(errors)
        self.assertIn("probe/execution mismatch for pi_version", joined)
        self.assertIn("probe candidate_sha mismatch", joined)

    def test_qa_event_log_hash_must_match_protected_execution_record(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        qa["event_log_hash"] = "9" * 64
        external = advisory_external()
        external["artifact"]["manifest_sha256"] = manifest_digest_excluding_own(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("event_log_hash does not match", "\n".join(errors))

    def test_missing_protected_execution_record_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        qa.pop("protected_execution_record")
        qa["protected_execution_record_path"] = "missing.json"
        external = advisory_external()
        external["artifact"]["manifest_sha256"] = manifest_digest_excluding_own(manifest)
        passed, errors, _ = check_delivery(manifest, manifest_path=str(FIXTURES_DIR / "valid_advisory_manifest.json"), external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("missing protected QA execution record", "\n".join(errors))

    def test_no_tools_qa_binding_has_no_qa_tool_error_but_gate_stays_blocked(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        qa["protected_execution_record"]["actual_invocation"]["tools"] = []
        qa["protected_probe_record"]["tools"] = []
        self._first_qa_with_rehashed_records(manifest)
        external = advisory_external()
        external["artifact"]["manifest_sha256"] = manifest_digest_excluding_own(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        joined = "\n".join(errors)
        self.assertFalse(passed)
        self.assertIn("caller-supplied external evidence is advisory only", joined)
        self.assertNotIn("must use no tools", joined)


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

    def test_cli_blocks_premerge_with_advisory_external_evidence(self):
        fixture = FIXTURES_DIR / "valid_advisory_manifest.json"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/governance/check_delivery_gate.py",
                "--external-evidence",
                str(FIXTURES_DIR / "advisory_external_evidence.json"),
                "--phase",
                "pre-merge",
                str(fixture),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("caller-supplied external evidence is advisory only", result.stderr)

    def test_cli_publication_phase_remains_blocked(self):
        fixture = FIXTURES_DIR / "valid_advisory_manifest.json"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/governance/check_delivery_gate.py",
                "--external-evidence",
                str(FIXTURES_DIR / "advisory_external_evidence.json"),
                "--phase",
                "publication",
                str(fixture),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("publication blocked", result.stderr)
        self.assertIn("freeze/audit is still active", result.stderr)
        self.assertIn("protected independent freeze review evidence missing", result.stderr)

    def test_cli_bootstrap_blocked_check_passes(self):
        result = subprocess.run(
            [sys.executable, "scripts/governance/check_delivery_gate.py", "--check-bootstrap-blocked"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BLOCKED", result.stderr)


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

    def test_mutable_docker_image_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as handle:
            handle.write("""
jobs:
  test:
    steps:
      - uses: docker://python:3.12
""")
            path = Path(handle.name)
        try:
            errors = check_pinning(str(path))
            self.assertTrue(any("docker" in error for error in errors), errors)
        finally:
            path.unlink(missing_ok=True)

    def test_mutable_job_container_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as handle:
            handle.write("""
jobs:
  test:
    container: python:3.12
    steps:
      - run: python --version
""")
            path = Path(handle.name)
        try:
            errors = check_pinning(str(path))
            self.assertTrue(any("job container" in error and "unpinned" in error for error in errors), errors)
        finally:
            path.unlink(missing_ok=True)

    def test_mutable_service_image_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as handle:
            handle.write("""
jobs:
  test:
    services:
      db:
        image: postgres:16
    steps:
      - run: echo ok
""")
            path = Path(handle.name)
        try:
            errors = check_pinning(str(path))
            self.assertTrue(any("service" in error and "unpinned" in error for error in errors), errors)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
