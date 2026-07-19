"""Adversarial contract tests for the canonical roadmap."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.governance.check_roadmap import (
    _parse_instant,
    _validate_d2_protected_review,
    validate_roadmap,
    validate_roadmap_files,
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

        review = {
            "schema_version": "2",
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
                "subject": {"purpose": "d2-freeze-completion-v2"},
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
            self.assertEqual(claims["purpose"], "d2-freeze-completion-v2")
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
