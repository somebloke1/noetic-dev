"""Adversarial contract tests for the canonical roadmap."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from scripts.governance.check_roadmap import validate_roadmap
from scripts.governance.json_schema import load_json_strict


ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "governance" / "roadmap.json"
SCHEMA_PATH = ROOT / "governance" / "schemas" / "roadmap.schema.json"
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
        self.assertEqual(validate_roadmap(self.state, self.schema, self.markdown), [])

    def test_duplicate_stage_id_fails(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][-1]["id"] = mutated["stages"][-2]["id"]
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "stage ids must be unique")

    def test_unknown_dependency_fails(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][3]["depends_on"].append("D404")
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "unknown dependency D404")

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

    def test_next_stage_requires_checkpointed_dependencies(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][1]["status"] = "planned"
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "next stage depends on non-checkpointed D1a")

    def test_exactly_one_next_stage_is_required(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["stages"][3]["status"] = "planned"
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "expected exactly one next stage")

    def test_markdown_heading_drift_fails(self) -> None:
        mutated = self.markdown.replace(
            "### D2 - Governance and source convergence [next]",
            "### D2 - Unrecorded replacement [next]",
        )
        errors = validate_roadmap(self.state, self.schema, mutated)
        self.assert_has_error(errors, "stage headings do not match")

    def test_unknown_conflict_stage_fails(self) -> None:
        mutated = copy.deepcopy(self.state)
        mutated["unresolved_conflicts"][0]["blocks"].append("D404")
        errors = validate_roadmap(mutated, self.schema, self.markdown)
        self.assert_has_error(errors, "unknown blocked stage D404")


if __name__ == "__main__":
    unittest.main()
