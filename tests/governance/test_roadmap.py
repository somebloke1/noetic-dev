"""Adversarial contract tests for the canonical roadmap."""

from __future__ import annotations

import copy
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.governance.check_roadmap import validate_roadmap, validate_roadmap_files
from scripts.governance.json_schema import load_json_strict, validate_schema


ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "governance" / "roadmap.json"
SCHEMA_PATH = ROOT / "governance" / "schemas" / "roadmap-v2.schema.json"
V1_SCHEMA_PATH = ROOT / "governance" / "schemas" / "roadmap.schema.json"
DOC_PATH = ROOT / "ROADMAP.md"


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

    def test_schema_v1_is_preserved_and_v2_migration_is_explicit(self) -> None:
        v1_schema = load_json_strict(V1_SCHEMA_PATH)
        predecessor = copy.deepcopy(self.state)
        predecessor["$schema"] = "./schemas/roadmap.schema.json"
        predecessor["schema_version"] = "1"
        predecessor["unresolved_conflicts"] = [
            {"id": "C1", "title": "resolved branch-flow conflict", "resolution_stage": "D2", "blocks": ["D3a", "D9"]},
            {"id": "C2", "title": "resolved audit conflict", "resolution_stage": "D2", "blocks": ["D3a", "D9"]},
            {"id": "C3", "title": "resolved notation conflict", "resolution_stage": "D2", "blocks": ["D3a"]},
            {"id": "C4", "title": "resolved model-access conflict", "resolution_stage": "D2", "blocks": ["D3a", "D4c"]},
            *copy.deepcopy(self.state["unresolved_conflicts"][1:]),
        ]
        self.assertEqual(validate_schema(predecessor, v1_schema), [])
        self.assertNotEqual(validate_schema(predecessor, self.schema), [])
        self.assertNotEqual(validate_schema(self.state, v1_schema), [])

    def test_d2_checkpoint_transition_is_reachable(self) -> None:
        transitioned = copy.deepcopy(self.state)
        transitioned["stages"][3]["status"] = "checkpointed"
        transitioned["stages"][3]["evidence"].append(
            {"kind": "commit", "reference": transitioned["baseline"]["sha"]}
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
            f"  `commit:{transitioned['baseline']['sha']}`.",
        ).replace(
            "- **C2 - D2 portfolio audit awaits protected independent review and integration:** resolve in D2; blocks D3a, D9.\n",
            "",
        )
        transitioned["document_sha256"] = hashlib.sha256(
            markdown.encode("utf-8")
        ).hexdigest()
        self.assertEqual(
            validate_roadmap(transitioned, self.schema, markdown),
            [],
        )

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
