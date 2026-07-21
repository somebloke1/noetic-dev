"""Adversarial contract tests for the canonical roadmap."""

from __future__ import annotations

import base64
import copy
import contextlib
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from unittest import mock

import scripts.governance.capture_d2_inventory as d2_capture
from scripts.governance.check_roadmap import (
    _d2_connection,
    _git_succeeds,
    _parse_instant,
    _validate_d2_inventory,
    _validate_d2_protected_review,
    validate_roadmap,
    validate_roadmap_files,
)
from scripts.governance.capture_d2_inventory import (
    _repository,
    _validate_derived_issues,
    _validate_derived_snapshot,
)
from scripts.governance.hash_tree import canonical_json_sha256
from scripts.governance.json_schema import load_json_strict, validate_schema
from scripts.governance.migrate_roadmap import (
    CANONICAL_V1_SHA256,
    RoadmapMigrationError,
    canonical_json_bytes,
    migrate_roadmap,
    migrate_v1_to_v2,
)


ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "governance" / "roadmap.json"
SCHEMA_PATH = ROOT / "governance" / "schemas" / "roadmap-v2.schema.json"
V1_SCHEMA_PATH = ROOT / "governance" / "schemas" / "roadmap.schema.json"
DOC_PATH = ROOT / "ROADMAP.md"
V1_FIXTURE_PATH = ROOT / "tests/governance/fixtures/canonical_roadmap_v1.json"
V2_MIGRATION_FIXTURE_PATH = (
    ROOT / "tests/governance/fixtures/expected_roadmap_v2_from_v1.json"
)


class TestRoadmap(unittest.TestCase):
    def setUp(self) -> None:
        self.state = load_json_strict(STATE_PATH)
        self.schema = load_json_strict(SCHEMA_PATH)
        self.markdown = DOC_PATH.read_text(encoding="utf-8")

    def assert_has_error(self, errors: list[str], fragment: str) -> None:
        self.assertTrue(
            any(fragment in error for error in errors),
            f"expected {fragment!r} in {errors!r}",
        )

    def test_exact_roadmap_contract_is_valid(self) -> None:
        self.assertEqual(validate_roadmap(self.state, self.schema, self.markdown, ROOT), [])
        self.assertEqual(validate_roadmap_files(ROOT), [])

    def test_v1_and_v2_schemas_are_disjoint(self) -> None:
        v1_schema = load_json_strict(V1_SCHEMA_PATH)
        predecessor = load_json_strict(V1_FIXTURE_PATH)
        self.assertEqual(validate_schema(predecessor, v1_schema), [])
        self.assertNotEqual(validate_schema(predecessor, self.schema), [])
        self.assertNotEqual(validate_schema(self.state, v1_schema), [])

    def test_persisted_v1_fixture_has_exact_provenance(self) -> None:
        source = load_json_strict(V1_FIXTURE_PATH)
        self.assertEqual(
            hashlib.sha256(V1_FIXTURE_PATH.read_bytes()).hexdigest(),
            "64e13e09d6ee20626a588a098854f47e1fd2319e7dd589556b93b63b8c6b90f5",
        )
        self.assertEqual(canonical_json_sha256(source), CANONICAL_V1_SHA256)
        self.assertEqual(validate_schema(source, load_json_strict(V1_SCHEMA_PATH)), [])

    def test_v1_to_v2_migration_matches_golden_and_changes_only_declared_paths(self) -> None:
        source = load_json_strict(V1_FIXTURE_PATH)
        original = copy.deepcopy(source)
        migrated = migrate_v1_to_v2(source)
        self.assertEqual(source, original)
        self.assertEqual(canonical_json_bytes(migrated), V2_MIGRATION_FIXTURE_PATH.read_bytes())
        self.assertEqual(validate_schema(migrated, self.schema), [])
        self.assertEqual(migrated["$schema"], "./schemas/roadmap-v2.schema.json")
        self.assertEqual(migrated["schema_version"], "2")
        source_without_markers = copy.deepcopy(source)
        migrated_without_markers = copy.deepcopy(migrated)
        source_without_markers.pop("$schema")
        source_without_markers.pop("schema_version")
        migrated_without_markers.pop("$schema")
        migrated_without_markers.pop("schema_version")
        source_without_markers["unresolved_conflicts"] = [
            item
            for item in source_without_markers["unresolved_conflicts"]
            if item["id"] not in {"C1", "C3", "C4"}
        ]
        self.assertEqual(migrated_without_markers, source_without_markers)

    def test_migration_is_idempotent_and_fails_closed_on_unknown_inputs(self) -> None:
        source = load_json_strict(V1_FIXTURE_PATH)
        migrated = migrate_roadmap(source)
        self.assertEqual(migrate_roadmap(migrated), migrated)
        attacks = []
        changed = copy.deepcopy(source)
        changed["unresolved_conflicts"][0]["title"] = "plausible but unknown v1"
        attacks.append(changed)
        reordered = copy.deepcopy(source)
        reordered["stages"][0], reordered["stages"][1] = (
            reordered["stages"][1], reordered["stages"][0]
        )
        attacks.append(reordered)
        for schema, version in [
            ("./schemas/roadmap.schema.json", "2"),
            ("./schemas/roadmap-v2.schema.json", "1"),
            ("./schemas/roadmap-v3.schema.json", "3"),
            (None, None),
        ]:
            attacked = copy.deepcopy(source)
            attacked["$schema"] = schema
            attacked["schema_version"] = version
            attacks.append(attacked)
        attacks.extend([None, [], "1", 1, True])
        for attack in attacks:
            with self.subTest(attack=repr(attack)[:80]):
                with self.assertRaises(RoadmapMigrationError):
                    migrate_roadmap(attack)

    def test_migration_cli_emits_exact_bytes_and_check_fails_without_stdout(self) -> None:
        script = ROOT / "scripts/governance/migrate_roadmap.py"
        result = subprocess.run(
            ["python3", str(script), str(V1_FIXTURE_PATH)],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, V2_MIGRATION_FIXTURE_PATH.read_bytes())
        checked = subprocess.run(
            [
                "python3", str(script), "--check", str(V1_FIXTURE_PATH),
                str(V2_MIGRATION_FIXTURE_PATH),
            ],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(checked.stdout, b"")
        with tempfile.TemporaryDirectory() as temp:
            wrong = Path(temp) / "wrong.json"
            wrong.write_text("{}\n", encoding="utf-8")
            rejected = subprocess.run(
                ["python3", str(script), "--check", str(V1_FIXTURE_PATH), str(wrong)],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
        self.assertEqual(rejected.returncode, 1)
        self.assertEqual(rejected.stdout, b"")
        self.assertIn(b"roadmap migration blocked", rejected.stderr)

    def test_d2_checkpoint_transition_is_reachable(self) -> None:
        transitioned = copy.deepcopy(self.state)
        integration_sha = "d" * 40
        transitioned["stages"][3]["status"] = "checkpointed"
        transitioned["stages"][3]["evidence"].append(
            {"kind": "commit", "reference": integration_sha}
        )
        transitioned["stages"][4]["status"] = "next"
        transitioned["unresolved_conflicts"] = [
            item for item in transitioned["unresolved_conflicts"] if item["id"] != "C2"
        ]
        markdown = self.markdown.replace(
            "### D2 - Governance and source convergence [next]",
            "### D2 - Governance and source convergence [checkpointed]",
        ).replace(
            "### D3a - Donor characterization and design decisions [planned]",
            "### D3a - Donor characterization and design decisions [next]",
        ).replace(
            "- **Evidence refs:** `artifact:governance/audits/20260718-d2-portfolio/inventory.json`,\n"
            "  `issue:https://github.com/somebloke1/noetic-dev/issues/32`.",
            "- **Evidence refs:** `artifact:governance/audits/20260718-d2-portfolio/inventory.json`,\n"
            "  `issue:https://github.com/somebloke1/noetic-dev/issues/32`,\n"
            f"  `commit:{integration_sha}`.",
        ).replace(
            "- **C2 - D2 portfolio audit awaits protected independent review and integration:** resolve in D2; blocks D3a, D9.\n",
            "",
        )
        transitioned["document_sha256"] = hashlib.sha256(
            markdown.encode("utf-8")
        ).hexdigest()
        with mock.patch(
            "scripts.governance.check_roadmap._git_succeeds", return_value=True
        ), mock.patch(
            "scripts.governance.check_roadmap._validate_repository_policy",
            return_value=[],
        ):
            self.assertEqual(
                validate_roadmap(transitioned, self.schema, markdown, ROOT), []
            )

    def test_d2_checkpoint_requires_authenticated_protected_review_and_integration_sha(self) -> None:
        freeze = load_json_strict(
            ROOT / "governance/audits/existing-work-freeze.json"
        )
        candidate_sha = "c" * 40
        integration_sha = "d" * 40

        def envelope(url: str, fetched_at: str, response) -> dict:
            return {
                "request_url": url,
                "status": 200,
                "request_id": "request-1",
                "fetched_at": fetched_at,
                "authentication": {
                    "verified": True,
                    "source": "protected-integration",
                    "principal": "noetic-dev-delivery-app",
                },
                "response_sha256": canonical_json_sha256(response),
                "response": response,
            }

        qa_record = {
            "schema_version": "1",
            "role": "qa",
            "objective": "adversarial-falsification",
            "verdict": "pass",
            "independent": True,
            "agent_id": "qa-protected-terra",
            "principal_id": "protected-principal-qa",
            "provider": "protected-runner",
            "qa_for_generation_id": "generation-d2-final",
            "reviewed_candidate_sha": candidate_sha,
            "protected_run_id": 29691499052,
            "protected_run_url": "https://github.com/somebloke1/noetic-dev/actions/runs/29691499052",
            "falsification_transcript_sha256": "b" * 64,
            "completed_at": "2026-07-19T00:01:00+00:00",
        }
        review = {
            "schema_version": "3",
            "audit_sha256": freeze["audit_sha256"],
            "reviewed_candidate_sha": candidate_sha,
            "pull_request": 67,
            "pr_api_response": envelope(
                "https://api.github.com/repos/somebloke1/noetic-dev/pulls/67",
                "2026-07-19T00:00:00+00:00",
                {
                    "number": 67,
                    "state": "open",
                    "head_ref": "issue-32-canonical-roadmap",
                    "head_sha": candidate_sha,
                    "base_ref": "dev",
                    "linked_issues": [32],
                },
            ),
            "implementation_generation": {
                "generation_id": "generation-d2-final",
                "agent_id": "implementation-codex",
                "principal_id": "protected-principal-implementation",
                "provider": "protected-runner",
                "candidate_sha": candidate_sha,
                "completed_at": "2026-07-19T00:00:30+00:00",
            },
            "qa_records": [
                {
                    "record_sha256": canonical_json_sha256(qa_record),
                    "record": qa_record,
                }
            ],
            "integration_pr_api_response": envelope(
                "https://api.github.com/repos/somebloke1/noetic-dev/pulls/67",
                "2026-07-19T00:01:30+00:00",
                {
                    "number": 67,
                    "state": "closed",
                    "merged": True,
                    "merged_at": "2026-07-19T00:01:15+00:00",
                    "head_ref": "issue-32-canonical-roadmap",
                    "head_sha": candidate_sha,
                    "base_ref": "dev",
                    "merge_commit_sha": integration_sha,
                    "linked_issues": [32],
                },
            ),
            "dev_integration_sha": integration_sha,
            "dev_branch_api_response": envelope(
                "https://api.github.com/repos/somebloke1/noetic-dev/branches/dev",
                "2026-07-19T00:02:00+00:00",
                {"name": "dev", "protected": True, "commit": {"sha": integration_sha}},
            ),
            "dev_compare_api_response": envelope(
                "https://api.github.com/repos/somebloke1/noetic-dev/compare/"
                f"{integration_sha}...{integration_sha}",
                "2026-07-19T00:02:00.500000+00:00",
                {
                    "status": "identical",
                    "ahead_by": 0,
                    "behind_by": 0,
                    "base_commit": {"sha": integration_sha},
                    "merge_base_commit": {"sha": integration_sha},
                },
            ),
            "issue": 32,
            "head": "issue-32-canonical-roadmap",
            "base": "dev",
            "evidence_url": "https://github.com/somebloke1/noetic-dev/pull/67#issuecomment-1",
            "reviewed_at": "2026-07-19T00:01:00+00:00",
            "protected_attestation_receipt": {
                "schema_version": "1",
                "receipt_id": "receipt-1",
                "provider": "protected-integration",
                "issued_at": "2026-07-19T00:02:01+00:00",
                "expires_at": "2026-07-19T00:07:01+00:00",
                "subject": {"purpose": "d2-freeze-completion-v3"},
                "claims": {},
                "proof": {
                    "format": "protected-integration-receipt-v1",
                    "key_id": "protected-delivery-v1",
                    "payload_sha256": "e" * 64,
                    "signature": "opaque-verifier-proof",
                },
            },
        }
        completed_freeze = copy.deepcopy(freeze)
        completed_freeze.update(
            {
                "status": "complete",
                "independent_review_completed": True,
                "blocks_publication": False,
                "reviewed_candidate_sha": candidate_sha,
                "reviewed_pull_request": 67,
                "dev_integration_sha": integration_sha,
                "reviewed_at": review["reviewed_at"],
                "review_evidence_url": review["evidence_url"],
                "protected_review_artifact": "governance/audits/d2-protected-freeze-review.json",
            }
        )
        d2 = copy.deepcopy(self.state["stages"][3])
        d2["evidence"].append({"kind": "commit", "reference": integration_sha})

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "governance/audits").mkdir(parents=True)
            (root / "governance/schemas").mkdir(parents=True)
            schema_source = ROOT / "governance/schemas/d2-freeze-review.schema.json"
            (root / "governance/schemas/d2-freeze-review.schema.json").write_bytes(
                schema_source.read_bytes()
            )
            review_path = root / "governance/audits/d2-protected-freeze-review.json"

            def write_review(payload: dict) -> None:
                review_path.write_text(json.dumps(payload), encoding="utf-8")
                completed_freeze["protected_review_sha256"] = hashlib.sha256(
                    review_path.read_bytes()
                ).hexdigest()

            def validate_review(payload: dict) -> list[str]:
                write_review(payload)
                with mock.patch(
                    "scripts.governance.check_roadmap._verify_protected_attestation_receipt",
                    return_value=True,
                ):
                    return _validate_d2_protected_review(
                        root, completed_freeze, d2
                    )

            write_review(review)

            with mock.patch(
                "scripts.governance.check_roadmap._verify_protected_attestation_receipt",
                return_value=True,
            ) as verifier:
                self.assertEqual(
                    _validate_d2_protected_review(root, completed_freeze, d2), []
                )
            claims = verifier.call_args.args[1]
            self.assertEqual(claims["contained_dev_head_sha"], integration_sha)
            self.assertEqual(claims["purpose"], "d2-freeze-completion-v3")
            self.assertEqual(claims["qa_record_sha256"], canonical_json_sha256(qa_record))
            self.assertEqual(claims["qa_protected_run_id"], 29691499052)
            self.assertEqual(
                claims["integration_pr_api_response_sha256"],
                review["integration_pr_api_response"]["response_sha256"],
            )
            self.assertEqual(
                claims["dev_compare_api_response_sha256"],
                review["dev_compare_api_response"]["response_sha256"],
            )

            with mock.patch(
                "scripts.governance.check_roadmap._verify_protected_attestation_receipt",
                return_value=False,
            ):
                errors = _validate_d2_protected_review(root, completed_freeze, d2)
            self.assert_has_error(errors, "receipt is not independently verified")

            attacked_review = copy.deepcopy(review)
            attacked_review["pr_api_response"]["response"]["head_sha"] = "f" * 40
            attacked_review["pr_api_response"]["response_sha256"] = canonical_json_sha256(
                attacked_review["pr_api_response"]["response"]
            )
            write_review(attacked_review)
            with mock.patch(
                "scripts.governance.check_roadmap._verify_protected_attestation_receipt",
                return_value=True,
            ):
                errors = _validate_d2_protected_review(root, completed_freeze, d2)
            self.assert_has_error(errors, "not derived from the authenticated PR response")

            qa_attacks = []
            missing_qa = copy.deepcopy(review)
            missing_qa["qa_records"] = []
            qa_attacks.append(("missing-qa", missing_qa))
            duplicate_qa = copy.deepcopy(review)
            duplicate_qa["qa_records"].append(copy.deepcopy(duplicate_qa["qa_records"][0]))
            qa_attacks.append(("duplicate-qa", duplicate_qa))
            self_qa = copy.deepcopy(review)
            self_qa_record = self_qa["qa_records"][0]["record"]
            self_qa_record["agent_id"] = self_qa["implementation_generation"]["agent_id"]
            self_qa_record["principal_id"] = self_qa["implementation_generation"]["principal_id"]
            self_qa["qa_records"][0]["record_sha256"] = canonical_json_sha256(
                self_qa_record
            )
            qa_attacks.append(("self-qa", self_qa))
            stale_candidate = copy.deepcopy(review)
            stale_record = stale_candidate["qa_records"][0]["record"]
            stale_record["reviewed_candidate_sha"] = "f" * 40
            stale_candidate["qa_records"][0]["record_sha256"] = canonical_json_sha256(
                stale_record
            )
            qa_attacks.append(("stale-candidate", stale_candidate))
            digest_substitution = copy.deepcopy(review)
            digest_substitution["qa_records"][0]["record"][
                "falsification_transcript_sha256"
            ] = "c" * 64
            qa_attacks.append(("qa-digest-substitution", digest_substitution))
            confused_run = copy.deepcopy(review)
            confused_record = confused_run["qa_records"][0]["record"]
            confused_record["protected_run_id"] = True
            confused_run["qa_records"][0]["record_sha256"] = canonical_json_sha256(
                confused_record
            )
            qa_attacks.append(("qa-run-type-confusion", confused_run))
            for attack, attacked_review in qa_attacks:
                with self.subTest(qa_attack=attack):
                    self.assertTrue(validate_review(attacked_review), attack)

            integration_attacks = []
            unrelated = copy.deepcopy(review)
            unrelated_response = unrelated["integration_pr_api_response"]["response"]
            unrelated_response["merge_commit_sha"] = "f" * 40
            unrelated["integration_pr_api_response"]["response_sha256"] = canonical_json_sha256(
                unrelated_response
            )
            integration_attacks.append(("unrelated-integration", unrelated))
            wrong_candidate = copy.deepcopy(review)
            wrong_candidate_response = wrong_candidate["integration_pr_api_response"]["response"]
            wrong_candidate_response["head_sha"] = "f" * 40
            wrong_candidate["integration_pr_api_response"]["response_sha256"] = canonical_json_sha256(
                wrong_candidate_response
            )
            integration_attacks.append(("wrong-integrated-candidate", wrong_candidate))
            false_merge = copy.deepcopy(review)
            false_merge_response = false_merge["integration_pr_api_response"]["response"]
            false_merge_response["merged"] = False
            false_merge["integration_pr_api_response"]["response_sha256"] = canonical_json_sha256(
                false_merge_response
            )
            integration_attacks.append(("false-merged-state", false_merge))
            stale_merge = copy.deepcopy(review)
            stale_merge_response = stale_merge["integration_pr_api_response"]["response"]
            stale_merge_response["merged_at"] = "2026-07-19T00:00:45+00:00"
            stale_merge["integration_pr_api_response"]["response_sha256"] = canonical_json_sha256(
                stale_merge_response
            )
            integration_attacks.append(("merge-before-qa", stale_merge))
            for attack, attacked_review in integration_attacks:
                with self.subTest(integration_attack=attack):
                    self.assertTrue(validate_review(attacked_review), attack)

            for successor_stage in range(3, 10):
                successor_review = copy.deepcopy(review)
                successor_sha = f"{successor_stage:040x}"
                successor_branch = successor_review["dev_branch_api_response"]
                successor_branch["response"]["commit"]["sha"] = successor_sha
                successor_branch["response_sha256"] = canonical_json_sha256(
                    successor_branch["response"]
                )
                successor_compare = successor_review["dev_compare_api_response"]
                successor_compare["request_url"] = (
                    "https://api.github.com/repos/somebloke1/noetic-dev/compare/"
                    f"{integration_sha}...{successor_sha}"
                )
                successor_compare["response"] = {
                    "status": "ahead",
                    "ahead_by": successor_stage - 2,
                    "behind_by": 0,
                    "base_commit": {"sha": integration_sha},
                    "merge_base_commit": {"sha": integration_sha},
                }
                successor_compare["response_sha256"] = canonical_json_sha256(
                    successor_compare["response"]
                )
                write_review(successor_review)
                with self.subTest(successor=f"D{successor_stage}"), mock.patch(
                    "scripts.governance.check_roadmap._verify_protected_attestation_receipt",
                    return_value=True,
                ):
                    errors = _validate_d2_protected_review(
                        root, completed_freeze, d2
                    )
                    self.assertEqual(errors, [])

            ancestry_attacks = []
            wrong_branch = copy.deepcopy(successor_review)
            wrong_branch["dev_branch_api_response"]["response"]["name"] = "main"
            wrong_branch["dev_branch_api_response"]["response_sha256"] = canonical_json_sha256(
                wrong_branch["dev_branch_api_response"]["response"]
            )
            ancestry_attacks.append(("wrong-branch", wrong_branch))
            wrong_merge_base = copy.deepcopy(successor_review)
            wrong_merge_base["dev_compare_api_response"]["response"]["merge_base_commit"]["sha"] = "f" * 40
            wrong_merge_base["dev_compare_api_response"]["response_sha256"] = canonical_json_sha256(
                wrong_merge_base["dev_compare_api_response"]["response"]
            )
            ancestry_attacks.append(("non-descendant", wrong_merge_base))
            rewritten = copy.deepcopy(successor_review)
            rewritten["dev_compare_api_response"]["response"]["behind_by"] = 1
            rewritten["dev_compare_api_response"]["response_sha256"] = canonical_json_sha256(
                rewritten["dev_compare_api_response"]["response"]
            )
            ancestry_attacks.append(("rewritten-history", rewritten))
            reversed_compare = copy.deepcopy(successor_review)
            reversed_compare["dev_compare_api_response"]["request_url"] = (
                "https://api.github.com/repos/somebloke1/noetic-dev/compare/"
                f"{successor_sha}...{integration_sha}"
            )
            ancestry_attacks.append(("reversed-compare", reversed_compare))
            stale = copy.deepcopy(successor_review)
            stale["dev_compare_api_response"]["fetched_at"] = "2026-07-19T00:02:00+00:00"
            ancestry_attacks.append(("stale-capture", stale))
            confused = copy.deepcopy(successor_review)
            confused["dev_compare_api_response"]["response"]["ahead_by"] = True
            confused["dev_compare_api_response"]["response_sha256"] = canonical_json_sha256(
                confused["dev_compare_api_response"]["response"]
            )
            ancestry_attacks.append(("bool-int-confusion", confused))
            digest_attack = copy.deepcopy(successor_review)
            digest_attack["dev_compare_api_response"]["response"]["ahead_by"] = 8
            ancestry_attacks.append(("digest-substitution", digest_attack))
            extra_data = copy.deepcopy(successor_review)
            extra_data["dev_compare_api_response"]["response"]["commits"] = []
            extra_data["dev_compare_api_response"]["response_sha256"] = canonical_json_sha256(
                extra_data["dev_compare_api_response"]["response"]
            )
            ancestry_attacks.append(("type-surface", extra_data))
            for attack, attacked_review in ancestry_attacks:
                with self.subTest(ancestry_attack=attack):
                    write_review(attacked_review)
                    with mock.patch(
                        "scripts.governance.check_roadmap._verify_protected_attestation_receipt",
                        return_value=True,
                    ):
                        errors = _validate_d2_protected_review(
                            root, completed_freeze, d2
                        )
                    self.assertTrue(errors, attack)

            write_review(review)

            attacked = copy.deepcopy(d2)
            attacked["evidence"][-1]["reference"] = "f" * 40
            with mock.patch(
                "scripts.governance.check_roadmap._verify_protected_attestation_receipt",
                return_value=True,
            ):
                errors = _validate_d2_protected_review(root, completed_freeze, attacked)
            self.assert_has_error(errors, "exact dev integration SHA")

    def test_portfolio_audit_is_schema_valid_and_digest_bound(self) -> None:
        audit_path = ROOT / "governance" / "audits" / "20260718-d2-portfolio" / "inventory.json"
        audit = load_json_strict(audit_path)
        audit_schema = load_json_strict(
            ROOT / "governance" / "schemas" / "d2-portfolio-audit.schema.json"
        )
        freeze = load_json_strict(
            ROOT / "governance" / "audits" / "existing-work-freeze.json"
        )
        self.assertEqual(validate_schema(audit, audit_schema), [])
        self.assertEqual(hashlib.sha256(audit_path.read_bytes()).hexdigest(), freeze["audit_sha256"])

        thin = copy.deepcopy(audit)
        del thin["open_issues"][0]["title"]
        self.assertNotEqual(validate_schema(thin, audit_schema), [])

        freeze_schema = load_json_strict(
            ROOT / "governance" / "schemas" / "existing-work-freeze.schema.json"
        )
        unbound_complete = copy.deepcopy(freeze)
        unbound_complete["status"] = "complete"
        unbound_complete["independent_review_completed"] = True
        unbound_complete["blocks_publication"] = False
        self.assertNotEqual(validate_schema(unbound_complete, freeze_schema), [])

    def test_portfolio_capture_rejects_omission_substitution_pagination_type_chronology_and_receipt_attacks(self) -> None:
        audit_path = ROOT / "governance/audits/20260718-d2-portfolio/inventory.json"
        audit = load_json_strict(audit_path)
        audit_schema = load_json_strict(
            ROOT / "governance/schemas/d2-portfolio-audit.schema.json"
        )
        source_order = ("principal", "open_pull_requests", "branches", "open_issues")

        def refresh_claims(attacked: dict) -> None:
            envelopes = attacked["capture"]["source_envelopes"]
            claims = {
                "repository": "somebloke1/noetic-dev",
                "repository_id": 1297462728,
                "capture_started_at": attacked["capture"]["started_at"],
                "capture_completed_at": attacked["capture"]["completed_at"],
                "response_sha256": {
                    source: envelopes[source]["response_sha256"]
                    for source in source_order
                },
                "body_sha256": {
                    source: envelopes[source]["body_sha256"]
                    for source in source_order
                },
            }
            attacked["verification"]["required_claims"] = claims
            attacked["verification"]["required_claims_sha256"] = canonical_json_sha256(
                claims
            )

        def mutate_response(attacked: dict, source: str, mutation) -> None:
            envelope = attacked["capture"]["source_envelopes"][source]
            response = json.loads(
                gzip.decompress(base64.b64decode(envelope["response_gzip_base64"]))
            )
            mutation(response)
            raw = json.dumps(response, separators=(",", ":")).encode("utf-8") + b"\n"
            envelope["response_gzip_base64"] = base64.b64encode(
                gzip.compress(raw, compresslevel=9, mtime=0)
            ).decode("ascii")
            envelope["body_sha256"] = hashlib.sha256(raw).hexdigest()
            envelope["canonical_response_sha256"] = canonical_json_sha256(response)
            envelope["response_sha256"] = canonical_json_sha256(
                {key: value for key, value in envelope.items() if key != "response_sha256"}
            )
            refresh_claims(attacked)

        omitted_envelope_field = copy.deepcopy(audit)
        del omitted_envelope_field["capture"]["source_envelopes"]["branches"][
            "body_sha256"
        ]
        self.assertNotEqual(validate_schema(omitted_envelope_field, audit_schema), [])

        substituted_projection = copy.deepcopy(audit)
        substituted_projection["open_pull_requests"][0]["title"] = "plausible substitute"
        self.assert_has_error(
            _validate_d2_inventory(substituted_projection), "not derived from the response body"
        )

        mismatched_head = copy.deepcopy(audit)
        pr_head = mismatched_head["open_pull_requests"][0]
        branch = next(
            item
            for item in mismatched_head["branches"]
            if item["name"] == pr_head["head"]
        )
        branch["sha"] = "f" * 40
        branch_envelope = mismatched_head["capture"]["source_envelopes"]["branches"]
        branch_response = json.loads(
            gzip.decompress(base64.b64decode(branch_envelope["response_gzip_base64"]))
        )
        response_branch = next(
            item
            for item in branch_response["data"]["repository"]["refs"]["nodes"]
            if item["name"] == pr_head["head"]
        )
        response_branch["target"]["oid"] = branch["sha"]
        raw = json.dumps(branch_response, separators=(",", ":")).encode("utf-8") + b"\n"
        branch_envelope["response_gzip_base64"] = base64.b64encode(
            gzip.compress(raw, compresslevel=9, mtime=0)
        ).decode("ascii")
        branch_envelope["body_sha256"] = hashlib.sha256(raw).hexdigest()
        branch_envelope["canonical_response_sha256"] = canonical_json_sha256(
            branch_response
        )
        branch_envelope["response_sha256"] = canonical_json_sha256(
            {
                key: value
                for key, value in branch_envelope.items()
                if key != "response_sha256"
            }
        )
        refresh_claims(mismatched_head)
        self.assert_has_error(
            _validate_d2_inventory(mismatched_head),
            "head SHA disagrees with its branch",
        )

        default_race = copy.deepcopy(audit)

        def change_default_head(response: dict) -> None:
            response["data"]["repository"]["defaultBranchRef"]["target"]["oid"] = (
                "f" * 40
            )

        mutate_response(default_race, "open_pull_requests", change_default_head)
        self.assert_has_error(
            _validate_d2_inventory(default_race),
            "default branch changed between responses",
        )

        default_vs_branch = copy.deepcopy(audit)
        for source in ("open_pull_requests", "branches", "open_issues"):
            mutate_response(default_vs_branch, source, change_default_head)
        self.assert_has_error(
            _validate_d2_inventory(default_vs_branch),
            "default branch target disagrees with dev branch",
        )

        substituted_pr_url = copy.deepcopy(audit)

        def change_pr_url(response: dict) -> None:
            response["data"]["repository"]["pullRequests"]["nodes"][0]["url"] = (
                "https://github.com/somebloke1/noetic-dev/pull/999"
            )

        mutate_response(substituted_pr_url, "open_pull_requests", change_pr_url)
        substituted_pr_url["open_pull_requests"][0]["url"] = (
            "https://github.com/somebloke1/noetic-dev/pull/999"
        )
        self.assert_has_error(
            _validate_d2_inventory(substituted_pr_url),
            "PR response identity is invalid",
        )

        malformed_target = copy.deepcopy(audit)

        def replace_branch_target(response: dict) -> None:
            response["data"]["repository"]["refs"]["nodes"][0]["target"]["oid"] = 1

        mutate_response(malformed_target, "branches", replace_branch_target)
        self.assert_has_error(
            _validate_d2_inventory(malformed_target),
            "branch response node shape is invalid",
        )

        duplicate_issue = copy.deepcopy(audit)

        def duplicate_issue_number(response: dict) -> None:
            nodes = response["data"]["repository"]["issues"]["nodes"]
            nodes[1]["number"] = nodes[0]["number"]
            nodes[1]["url"] = nodes[0]["url"]

        mutate_response(duplicate_issue, "open_issues", duplicate_issue_number)
        self.assert_has_error(
            _validate_d2_inventory(duplicate_issue),
            "issue numbers are duplicated",
        )

        omitted_response_node = copy.deepcopy(audit)

        def omit_pull(response: dict) -> None:
            connection = response["data"]["repository"]["pullRequests"]
            connection["nodes"].pop(0)
            connection["totalCount"] -= 1

        mutate_response(omitted_response_node, "open_pull_requests", omit_pull)
        omitted_response_node["capture"]["source_envelopes"]["open_pull_requests"][
            "pagination"
        ]["item_count"] -= 1
        omitted_response_node["capture"]["source_envelopes"]["open_pull_requests"][
            "pagination"
        ]["total_count"] -= 1
        envelope = omitted_response_node["capture"]["source_envelopes"][
            "open_pull_requests"
        ]
        envelope["response_sha256"] = canonical_json_sha256(
            {key: value for key, value in envelope.items() if key != "response_sha256"}
        )
        refresh_claims(omitted_response_node)
        self.assert_has_error(
            _validate_d2_inventory(omitted_response_node),
            "PR identities are not derived",
        )

        paginated = copy.deepcopy(audit)

        def add_next_page(response: dict) -> None:
            response["data"]["repository"]["refs"]["pageInfo"]["hasNextPage"] = True

        mutate_response(paginated, "branches", add_next_page)
        self.assert_has_error(_validate_d2_inventory(paginated), "pagination was substituted")

        for source, connection_name in (
            ("open_pull_requests", "pullRequests"),
            ("branches", "refs"),
            ("open_issues", "issues"),
        ):
            outer_bool_int_confusion = copy.deepcopy(audit)

            def confuse_outer_count(
                response: dict, key: str = connection_name
            ) -> None:
                connection = response["data"]["repository"][key]
                connection["nodes"] = connection["nodes"][:1]
                connection["totalCount"] = True

            mutate_response(outer_bool_int_confusion, source, confuse_outer_count)
            envelope = outer_bool_int_confusion["capture"]["source_envelopes"][source]
            envelope["pagination"]["item_count"] = 1
            envelope["pagination"]["total_count"] = 1
            envelope["response_sha256"] = canonical_json_sha256(
                {
                    key: value
                    for key, value in envelope.items()
                    if key != "response_sha256"
                }
            )
            refresh_claims(outer_bool_int_confusion)
            with self.subTest(outer_total_count_bool=source):
                self.assert_has_error(
                    _validate_d2_inventory(outer_bool_int_confusion),
                    "pagination was substituted",
                )

        wrong_type = copy.deepcopy(audit)
        wrong_type["counts"]["branches"] = True
        self.assertNotEqual(validate_schema(wrong_type, audit_schema), [])
        self.assert_has_error(
            _validate_d2_inventory(wrong_type), "counts are not derived"
        )

        label_bool_int_confusion = copy.deepcopy(audit)

        def confuse_label_count(response: dict) -> None:
            labels = response["data"]["repository"]["issues"]["nodes"][0]["labels"]
            labels["nodes"] = labels["nodes"][:1]
            labels["totalCount"] = True

        mutate_response(label_bool_int_confusion, "open_issues", confuse_label_count)
        response = json.loads(
            gzip.decompress(
                base64.b64decode(
                    label_bool_int_confusion["capture"]["source_envelopes"][
                        "open_issues"
                    ]["response_gzip_base64"]
                )
            )
        )
        first_issue = response["data"]["repository"]["issues"]["nodes"][0]
        projected = next(
            item
            for item in label_bool_int_confusion["open_issues"]
            if item["number"] == first_issue["number"]
        )
        projected["labels"] = [first_issue["labels"]["nodes"][0]["name"]]
        status_labels = [
            label for label in projected["labels"] if label.startswith("status:")
        ]
        projected["status"] = (
            status_labels[0].removeprefix("status:")
            if len(status_labels) == 1
            else "missing"
        )
        self.assert_has_error(
            _validate_d2_inventory(label_bool_int_confusion), "labels are incomplete"
        )

        reversed_chronology = copy.deepcopy(audit)
        principal = reversed_chronology["capture"]["source_envelopes"]["principal"]
        principal["fetched_at"] = reversed_chronology["capture"]["completed_at"]
        principal["response_sha256"] = canonical_json_sha256(
            {key: value for key, value in principal.items() if key != "response_sha256"}
        )
        refresh_claims(reversed_chronology)
        self.assert_has_error(
            _validate_d2_inventory(reversed_chronology), "capture chronology"
        )

        equal_server_dates = copy.deepcopy(audit)
        equal_envelopes = equal_server_dates["capture"]["source_envelopes"]
        equal_envelopes["open_pull_requests"]["response_headers"]["date"] = (
            equal_envelopes["principal"]["response_headers"]["date"]
        )
        pulls = equal_envelopes["open_pull_requests"]
        pulls["response_sha256"] = canonical_json_sha256(
            {key: value for key, value in pulls.items() if key != "response_sha256"}
        )
        refresh_claims(equal_server_dates)
        self.assert_has_error(
            _validate_d2_inventory(equal_server_dates), "capture chronology"
        )

        reversed_server_dates = copy.deepcopy(audit)
        reversed_envelopes = reversed_server_dates["capture"]["source_envelopes"]
        principal_date = parsedate_to_datetime(
            reversed_envelopes["principal"]["response_headers"]["date"]
        )
        reversed_envelopes["open_pull_requests"]["response_headers"]["date"] = (
            format_datetime(principal_date - timedelta(seconds=1), usegmt=True)
        )
        pulls = reversed_envelopes["open_pull_requests"]
        pulls["response_sha256"] = canonical_json_sha256(
            {key: value for key, value in pulls.items() if key != "response_sha256"}
        )
        refresh_claims(reversed_server_dates)
        self.assert_has_error(
            _validate_d2_inventory(reversed_server_dates), "capture chronology"
        )

        fake_receipt = copy.deepcopy(audit)
        fake_receipt["verification"]["status"] = "protected_receipt_verified"
        fake_receipt["verification"]["protected_attestation_receipt"] = {"proof": "fake"}
        with mock.patch(
            "scripts.governance.check_roadmap._verify_protected_attestation_receipt",
            return_value=False,
        ) as verifier:
            self.assert_has_error(
                _validate_d2_inventory(fake_receipt), "receipt verification failed"
            )
            verifier.assert_called_once()

        with mock.patch(
            "scripts.governance.check_roadmap._verify_protected_attestation_receipt",
            return_value=True,
        ) as verifier:
            self.assertEqual(_validate_d2_inventory(fake_receipt), [])
            verifier.assert_called_once_with(
                fake_receipt["verification"]["protected_attestation_receipt"],
                fake_receipt["verification"]["required_claims"],
            )

        receipt_in_pending = copy.deepcopy(audit)
        receipt_in_pending["verification"]["protected_attestation_receipt"] = {
            "proof": "self-authored"
        }
        self.assert_has_error(
            _validate_d2_inventory(receipt_in_pending), "must not embed an unverified receipt"
        )

    def test_roadmap_git_checks_use_fixed_binary_and_minimal_environment(self) -> None:
        completed = subprocess.CompletedProcess([], 0, b"", b"")
        with mock.patch(
            "scripts.governance.check_roadmap.trusted_git_binary",
            return_value="/usr/bin/git",
        ), mock.patch(
            "scripts.governance.check_roadmap.subprocess.run",
            return_value=completed,
        ) as run:
            self.assertTrue(_git_succeeds(ROOT, "cat-file", "-e", "HEAD^{commit}"))
        self.assertEqual(run.call_args.args[0][0], "/usr/bin/git")
        child = run.call_args.kwargs["env"]
        self.assertEqual(child["PATH"], os.defpath)
        self.assertEqual(child["HOME"], "/nonexistent")
        self.assertEqual(child["GIT_NO_REPLACE_OBJECTS"], "1")
        self.assertEqual(run.call_args.args[0][1], "--no-replace-objects")
        self.assertNotIn("LD_PRELOAD", child)
        self.assertNotIn("BASH_ENV", child)
        with mock.patch(
            "scripts.governance.check_roadmap.trusted_git_binary",
            return_value="/usr/bin/git",
        ), mock.patch(
            "scripts.governance.check_roadmap.subprocess.run",
            side_effect=OSError("cannot execute"),
        ):
            self.assertFalse(_git_succeeds(ROOT, "cat-file", "-e", "HEAD^{commit}"))

        with tempfile.TemporaryDirectory() as tmp:
            repository = Path(tmp)
            env = {
                "HOME": "/nonexistent",
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": os.defpath,
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_OPTIONAL_LOCKS": "0",
                "GIT_TERMINAL_PROMPT": "0",
            }

            def git(*arguments: str) -> subprocess.CompletedProcess:
                return subprocess.run(
                    ["/usr/bin/git", *arguments],
                    cwd=repository,
                    env=env,
                    capture_output=True,
                    check=True,
                )

            git("init", "--quiet")
            git(
                "-c",
                "user.name=QA",
                "-c",
                "user.email=qa@example.com",
                "commit",
                "--allow-empty",
                "--quiet",
                "-m",
                "first",
            )
            first = git("rev-parse", "HEAD").stdout.decode("ascii").strip()
            git("switch", "--orphan", "other")
            git(
                "-c",
                "user.name=QA",
                "-c",
                "user.email=qa@example.com",
                "commit",
                "--allow-empty",
                "--quiet",
                "-m",
                "second",
            )
            second = git("rev-parse", "HEAD").stdout.decode("ascii").strip()
            git("replace", "--graft", second, first)
            self.assertEqual(
                subprocess.run(
                    ["/usr/bin/git", "merge-base", "--is-ancestor", first, second],
                    cwd=repository,
                    env=env,
                    check=False,
                ).returncode,
                0,
            )
            self.assertFalse(
                _git_succeeds(repository, "merge-base", "--is-ancestor", first, second)
            )

    def test_capture_uses_strict_fixed_github_boundary_and_controlled_cli(self) -> None:
        raw = (
            b"HTTP/2 200\r\n"
            b"date: Tue, 21 Jul 2026 11:10:08 GMT\r\n"
            b"x-github-request-id: QA:1\r\n\r\n"
            b'{"data":{"viewer":{"databaseId":1,"login":"somebloke1"}}}'
        )
        completed = subprocess.CompletedProcess([], 0, raw, b"")
        hostile = {
            "PATH": "/tmp/hostile",
            "BASH_ENV": "/tmp/hostile-env",
            "LD_PRELOAD": "/tmp/hostile.so",
            "GH_TOKEN": "attacker-token",
            "GH_HOST": "attacker.invalid",
        }
        with mock.patch.dict(os.environ, hostile, clear=True), mock.patch(
            "scripts.governance.capture_d2_inventory.subprocess.run",
            return_value=completed,
        ) as run:
            envelope, data = d2_capture._graphql("principal")
        self.assertEqual(data["viewer"]["login"], "somebloke1")
        self.assertEqual(envelope["request_id"], "QA:1")
        command = run.call_args.args[0]
        child = run.call_args.kwargs
        self.assertEqual(command[0], "/usr/bin/gh")
        self.assertEqual(child["executable"], "/usr/bin/gh")
        self.assertEqual(child["stdin"], subprocess.DEVNULL)
        self.assertEqual(child["stdout"], subprocess.PIPE)
        self.assertEqual(child["stderr"], subprocess.DEVNULL)
        self.assertEqual(child["timeout"], 30)
        self.assertNotIn("GH_TOKEN", child["env"])
        self.assertNotIn("GH_HOST", child["env"])
        self.assertNotIn("LD_PRELOAD", child["env"])
        self.assertNotIn("BASH_ENV", child["env"])

        for body in (
            b'{"data":{"viewer":{"login":"bad","login":"somebloke1"}}}',
            b'{"data":{"viewer":{"databaseId":NaN,"login":"somebloke1"}}}',
        ):
            with self.subTest(body=body), self.assertRaisesRegex(
                RuntimeError, "not strict JSON"
            ):
                d2_capture._parse_included_response(
                    raw.split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n" + body
                )

        with mock.patch(
            "scripts.governance.capture_d2_inventory.subprocess.run",
            side_effect=FileNotFoundError("missing"),
        ), self.assertRaisesRegex(
            RuntimeError, "trusted GitHub CLI execution failed"
        ):
            d2_capture._graphql("principal")

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "inventory.json"
            stderr = io.StringIO()
            with mock.patch.object(
                sys, "argv", ["capture_d2_inventory.py", "--output", str(output)]
            ), mock.patch(
                "scripts.governance.capture_d2_inventory.capture",
                return_value={"schema_version": "2"},
            ), contextlib.redirect_stderr(stderr):
                self.assertEqual(d2_capture.main(), 1)
            self.assertFalse(output.exists())
            self.assertIn("failed schema validation", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_capture_rejects_duplicate_malformed_and_renamed_identities(self) -> None:
        audit = load_json_strict(
            ROOT / "governance/audits/20260718-d2-portfolio/inventory.json"
        )
        pulls = copy.deepcopy(audit["open_pull_requests"])
        branches = copy.deepcopy(audit["branches"])
        self.assertTrue(_validate_derived_snapshot(pulls, branches))

        duplicate = copy.deepcopy(branches)
        duplicate.append(copy.deepcopy(duplicate[0]))
        with self.assertRaisesRegex(RuntimeError, "duplicate identities"):
            _validate_derived_snapshot(pulls, duplicate)

        malformed = copy.deepcopy(branches)
        malformed[0]["sha"] = "not-a-commit-oid"
        with self.assertRaisesRegex(RuntimeError, "invalid or duplicate"):
            _validate_derived_snapshot(pulls, malformed)

        renamed_pulls = copy.deepcopy(pulls)
        renamed_branches = copy.deepcopy(branches)
        repair = next(item for item in renamed_pulls if item["number"] == 67)
        repair_branch = next(
            item for item in renamed_branches if item["name"] == repair["head"]
        )
        repair["head"] = "renamed-d2-head"
        repair_branch["name"] = "renamed-d2-head"
        with self.assertRaisesRegex(RuntimeError, "repair pull request identity"):
            _validate_derived_snapshot(renamed_pulls, renamed_branches)

        class DictSubclass(dict):
            pass

        hostile_pulls = copy.deepcopy(pulls)
        hostile_pulls[0] = DictSubclass(hostile_pulls[0])
        with self.assertRaisesRegex(RuntimeError, "not strict JSON"):
            _validate_derived_snapshot(hostile_pulls, branches)

        issues = copy.deepcopy(audit["open_issues"])
        self.assertEqual(_validate_derived_issues(issues), issues)
        duplicate_issues = copy.deepcopy(issues)
        duplicate_issues[1]["number"] = duplicate_issues[0]["number"]
        duplicate_issues[1]["url"] = duplicate_issues[0]["url"]
        with self.assertRaisesRegex(RuntimeError, "duplicate identities"):
            _validate_derived_issues(duplicate_issues)
        wrong_issue_url = copy.deepcopy(issues)
        wrong_issue_url[0]["url"] = "https://github.com/somebloke1/noetic-dev/issues/999"
        with self.assertRaisesRegex(RuntimeError, "invalid or duplicate"):
            _validate_derived_issues(wrong_issue_url)

        repository = {
            "databaseId": 1297462728,
            "nameWithOwner": "somebloke1/noetic-dev",
            "defaultBranchRef": {"name": "dev", "target": {"oid": 1}},
        }
        with self.assertRaisesRegex(RuntimeError, "repository identity"):
            _repository({"repository": repository})

        repository = {
            "refs": {
                "totalCount": 1,
                "pageInfo": {"hasNextPage": False, "endCursor": "cursor"},
                "nodes": [{"name": "dev", "target": {"oid": "a" * 40}}],
            }
        }
        envelope = {
            "pagination": {
                "first": 100,
                "item_count": True,
                "total_count": True,
                "has_next_page": False,
                "end_cursor": "cursor",
            }
        }
        errors: list[str] = []
        _d2_connection(repository, "refs", envelope, errors)
        self.assert_has_error(errors, "pagination was substituted")

        class AuditSubclass(dict):
            pass

        self.assert_has_error(
            _validate_d2_inventory(AuditSubclass(audit)),
            "not strict JSON",
        )

    def test_complete_freeze_chronology_compares_instants_not_strings(self) -> None:
        captured = _parse_instant("2026-07-18T23:46:09-12:00")
        reviewed = _parse_instant("2026-07-19T00:00:00+14:00")
        self.assertIsNotNone(captured)
        self.assertIsNotNone(reviewed)
        self.assertLess(reviewed, captured)

    def test_wrong_stage_container_type_fails(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"] = None
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "expected type array")

    def test_document_path_is_closed_to_root_roadmap(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["document_path"] = "../../etc/passwd"
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "expected constant 'ROADMAP.md'")

    def test_duplicate_stage_id_fails(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][-1]["id"] = mutated["stages"][-2]["id"]
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "stage ids must be unique")

    def test_unknown_dependency_fails(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][3]["depends_on"].append("D404")
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "expected one of")

    def test_dependency_cycle_fails(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][0]["depends_on"] = ["D9"]
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "dependency cycle")

    def test_checkpoint_without_evidence_fails(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][0]["evidence"] = []
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "checkpointed stage requires evidence")

    def test_commit_evidence_requires_full_sha(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][0]["evidence"][0]["reference"] = "29196a6"
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "string does not match pattern")

    def test_commit_evidence_rejects_trailing_newline(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][0]["evidence"][0]["reference"] += "\n"
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "invalid commit evidence")

    def test_unknown_full_commit_fails_repository_validation(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][0]["evidence"][0]["reference"] = "0" * 40
        errors = validate_roadmap(mutated, self.schema, self.markdown, ROOT)
        self.assert_has_error(errors, "evidence commit does not resolve")

    def test_checkpoint_requires_commit_evidence(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][0]["evidence"] = [
            item for item in mutated["stages"][0]["evidence"]
            if item["kind"] == "issue"
        ]
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "requires baseline-ancestor commit evidence")

    def test_non_authority_issue_cannot_be_checkpoint_evidence(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][0]["evidence"][-1]["reference"] = (
            "https://github.com/somebloke1/noetic-dev/issues/65"
        )
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "issue evidence must be authority issue #32")

    def test_malformed_remote_evidence_fails(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][0]["evidence"][-1]["reference"] = "not-a-url"
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "string does not match pattern")

    def test_artifact_path_traversal_fails(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][0]["evidence"][-1] = {
            "kind": "artifact",
            "reference": "../../etc/passwd",
        }
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assertTrue(errors)

    def test_artifact_symlink_cannot_escape_repository(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][0]["evidence"][-1] = {
            "kind": "artifact",
            "reference": "evidence-link",
        }
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            root = temporary / "repo"
            root.mkdir()
            outside = temporary / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            (root / "evidence-link").symlink_to(outside)
            errors = validate_roadmap(mutated, self.schema, self.markdown, root)
        self.assert_has_error(errors, "artifact evidence resolves outside repository")

    def test_unapproved_remote_evidence_fails_closed_catalog(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][2]["evidence"][1]["reference"] = (
            "https://github.com/somebloke1/noetic-dev/pull/999"
        )
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "remote evidence catalog changed")

    def test_duplicate_evidence_fails(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][0]["evidence"].append(
            copy.deepcopy(mutated["stages"][0]["evidence"][0])
        )
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "duplicate evidence")

    def test_evidence_cannot_move_between_stages(self) -> None:
        mutated = copy.deepcopy(self.state)
        moved = mutated["stages"][2]["evidence"].pop(1)
        mutated["stages"][0]["evidence"].append(moved)
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "schema version 2 evidence catalog changed")

    def test_next_stage_requires_checkpointed_dependencies(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][1]["status"] = "planned"
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "next stage depends on non-checkpointed D1a")

    def test_next_stage_cannot_skip_earlier_stage(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][3]["status"] = "planned"
        mutated["stages"][4]["status"] = "next"
        mutated["stages"][4]["depends_on"] = ["D0", "D1a", "D1b"]
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "D3a: earlier stage D2 is not checkpointed")

    def test_exactly_one_next_stage_is_required(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][3]["status"] = "planned"
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "expected exactly one next stage")

    def test_checkpointed_stage_requires_checkpointed_dependencies(self) -> None:
        mutated = copy.deepcopy(self.state)
        stage = mutated["stages"][10]
        stage["status"] = "checkpointed"
        stage["evidence"] = [copy.deepcopy(mutated["stages"][0]["evidence"][0])]
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "checkpointed stage depends on non-checkpointed D4d")

    def test_blocked_stage_requires_named_conflict(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][6]["status"] = "blocked"
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "D4a: blocked stage has no named conflict")

    def test_conflict_cannot_block_checkpointed_stage(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["unresolved_conflicts"][0]["blocks"].append("D0")
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "unresolved conflict blocks checkpointed D0")

    def test_conflict_blocks_must_be_unique(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["unresolved_conflicts"][1]["blocks"].append("D4c")
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "blocked stages must be unique")

    def test_conflict_resolution_cannot_follow_blocked_stage(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["unresolved_conflicts"][1]["resolution_stage"] = "D9"
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "resolution stage D9 follows blocked D4c")

    def test_unresolved_conflict_cannot_resolve_in_checkpointed_stage(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["unresolved_conflicts"][0]["resolution_stage"] = "D0"
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "unresolved conflict resolves in checkpointed D0")

    def test_baseline_branch_is_closed_to_dev(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["baseline"]["branch"] = "invented"
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "expected constant 'dev'")

    def test_candidate_head_cannot_replace_remote_branch_baseline(self) -> None:
        mutated = copy.deepcopy(self.state)
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
        ).strip()
        mutated["baseline"]["sha"] = head
        errors = validate_roadmap(mutated, self.schema, self.markdown, ROOT)
        self.assert_has_error(errors, "not an ancestor of declared branch")

    def test_markdown_heading_drift_fails(self) -> None:
        mutated = self.markdown.replace(
            "### D2 - Governance and source convergence [next]",
            "### D2 - Unrecorded replacement [next]",
        )
        errors = validate_roadmap(self.state, self.schema, mutated)
        self.assert_has_error(errors, "stage headings do not match")

    def test_unstructured_markdown_claim_drift_fails_document_hash(self) -> None:
        mutated = self.markdown.replace(
            "These foundations do **not** establish a production Telos dispatcher",
            "These foundations establish a production Telos dispatcher",
            1,
        )
        errors = validate_roadmap(self.state, self.schema, mutated)
        self.assert_has_error(errors, "ROADMAP.md SHA-256 does not match")

    def test_machine_document_hash_drift_fails(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["document_sha256"] = "0" * 64
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "ROADMAP.md SHA-256 does not match")

    def test_file_validation_hashes_raw_crlf_bytes(self) -> None:
        copied_paths = (
            "governance/roadmap.json",
            "governance/schemas/roadmap.schema.json",
            "governance/schemas/roadmap-v2.schema.json",
            "governance/schemas/d2-portfolio-audit.schema.json",
            "governance/audits/20260718-d2-portfolio/inventory.json",
            "governance/audits/existing-work-freeze.json",
            "governance/bootstrap-status.json",
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            for relative in copied_paths:
                target = temporary_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            crlf = self.markdown.replace("\n", "\r\n").encode("utf-8")
            (temporary_root / "ROADMAP.md").write_bytes(crlf)
            errors = validate_roadmap_files(temporary_root)
        self.assert_has_error(errors, "ROADMAP.md SHA-256 does not match")

    def test_policy_snapshot_must_match_repository_files(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["policy_snapshot"]["existing_work_freeze"] = "active"
        errors = validate_roadmap(mutated, self.schema, self.markdown, ROOT)
        self.assert_has_error(errors, "policy snapshot does not match repository")

    def test_resolved_d2_conflicts_are_absent(self) -> None:
        conflict_ids = {item["id"] for item in self.state["unresolved_conflicts"]}
        self.assertTrue({"C1", "C3", "C4"}.isdisjoint(conflict_ids))
        self.assertIn("C2", conflict_ids)

    def test_d2_gate_cannot_negate_freeze_requirements(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][3]["exit_gate"] += (
            " Reviewed freeze disposition is not required."
        )
        errors = validate_roadmap(mutated, self.schema, self.markdown, ROOT)
        self.assert_has_error(errors, "exact schema-v2 D2 exit gate")

    def test_d9_gate_cannot_negate_trust_requirements(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][-1]["exit_gate"] += (
            " License, protected main, post-merge evidence, full main SHA, and the "
            "distinct protected trust root are not required."
        )
        errors = validate_roadmap(mutated, self.schema, self.markdown, ROOT)
        self.assert_has_error(errors, "exact schema-v2 D9 exit gate")

    def test_policy_files_cannot_be_symlinks(self) -> None:
        policy_paths = (
            "governance/audits/existing-work-freeze.json",
            "governance/bootstrap-status.json",
        )
        support_paths = (
            "governance/schemas/existing-work-freeze.schema.json",
            "governance/schemas/d2-portfolio-audit.schema.json",
            "governance/audits/20260718-d2-portfolio/inventory.json",
        )
        for symlinked in policy_paths:
            with self.subTest(path=symlinked), tempfile.TemporaryDirectory() as directory:
                temporary = Path(directory)
                root = temporary / "repo"
                outside = temporary / "outside.json"
                outside.write_text("{}", encoding="utf-8")
                for relative in support_paths:
                    target = root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((ROOT / relative).read_bytes())
                for relative in policy_paths:
                    target = root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if relative == symlinked:
                        target.symlink_to(outside)
                    else:
                        target.write_bytes((ROOT / relative).read_bytes())
                errors = validate_roadmap(
                    self.state,
                    self.schema,
                    self.markdown,
                    root,
                )
                self.assert_has_error(errors, "policy file must not be a symlink")

    def test_markdown_checkpoint_line_drift_fails_even_if_sha_remains(self) -> None:
        mutated = self.markdown.replace(
            "**Exact checkpoint:** `dev@15b9ae66ff316abf28a5041c465e95baef5e82f9` "
            "on 2026-07-18",
            "**Exact checkpoint:** `main@0000000000000000000000000000000000000000` "
            "on 2099-01-01",
        )
        errors = validate_roadmap(self.state, self.schema, mutated)
        self.assert_has_error(errors, "checkpoint line does not match")

    def test_markdown_authority_line_drift_fails_even_if_url_remains(self) -> None:
        mutated = self.markdown.replace(
            "[GitHub issue #32](https://github.com/somebloke1/noetic-dev/issues/32)",
            "[GitHub issue #999](https://github.com/somebloke1/noetic-dev/issues/999)",
            1,
        )
        errors = validate_roadmap(self.state, self.schema, mutated)
        self.assert_has_error(errors, "authority line does not match")

    def test_markdown_dependency_drift_fails(self) -> None:
        mutated = self.markdown.replace(
            "- **Dependencies:** D0, D1a, D1b.",
            "- **Dependencies:** D9.",
            1,
        )
        errors = validate_roadmap(self.state, self.schema, mutated)
        self.assert_has_error(errors, "D2: Markdown dependencies do not match JSON")

    def test_markdown_evidence_drift_fails(self) -> None:
        mutated = self.markdown.replace(
            "`commit:29196a67349537d6f8a8a711df11b86da0430857`",
            "`commit:0000000000000000000000000000000000000000`",
            1,
        )
        errors = validate_roadmap(self.state, self.schema, mutated)
        self.assert_has_error(errors, "D0: Markdown evidence does not match JSON")

    def test_markdown_exit_gate_drift_fails(self) -> None:
        mutated = self.markdown.replace(
            "baseline without claiming publication readiness.",
            "baseline and proves publication readiness.",
            1,
        )
        errors = validate_roadmap(self.state, self.schema, mutated)
        self.assert_has_error(errors, "D0: Markdown exit gate does not match JSON")

    def test_markdown_track_drift_fails(self) -> None:
        mutated = self.markdown.replace(
            "May improve models and evaluation but cannot gate D2-D9.",
            "Gates every delivery stage.",
            1,
        )
        errors = validate_roadmap(self.state, self.schema, mutated)
        self.assert_has_error(errors, "parallel tracks do not match")

    def test_markdown_conflict_drift_fails(self) -> None:
        mutated = self.markdown.replace(
            "resolve in D3a; blocks D4c, D5.",
            "resolve in D9; blocks D0.",
            1,
        )
        errors = validate_roadmap(self.state, self.schema, mutated)
        self.assert_has_error(errors, "conflicts do not match")

    def test_machine_conflict_catalog_cannot_be_removed(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["unresolved_conflicts"] = []
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "array has fewer than 4 items")

    def test_version_two_stage_catalog_is_closed(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][-1]["id"] = "D99"
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "expected one of")

    def test_version_two_track_catalog_is_closed(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["parallel_tracks"][-1]["id"] = "T99"
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "expected one of")

    def test_version_two_conflict_catalog_is_closed(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["unresolved_conflicts"][-1]["id"] = "C99"
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "expected one of")

    def test_unknown_conflict_stage_fails(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["unresolved_conflicts"][0]["blocks"].append("D404")
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "expected one of")


if __name__ == "__main__":
    unittest.main()
