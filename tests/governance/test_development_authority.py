"""Regression tests for direct user authority and product-scope discipline."""

from __future__ import annotations

import json
import copy
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

from scripts.governance.check_delivery_gate import _development_authority_errors


class TestDevelopmentAuthority(unittest.TestCase):
    def test_explicit_user_authority_is_the_active_policy(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        practices = (ROOT / "docs" / "development-practices.md").read_text(encoding="utf-8")
        self.assertIn("The user's explicit instruction is sufficient authority", agents)
        self.assertIn("generated goalchain principles", agents)
        self.assertIn("Direct commits and pushes to `dev` are valid", practices)

    def test_unsolicited_security_scope_is_rejected(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        delivery = (ROOT / "docs" / "governance" / "delivery-governance.md").read_text(encoding="utf-8")
        self.assertIn("Do not introduce threat models", agents)
        self.assertIn("No external trust root", delivery)
        self.assertIn("are not blockers", delivery)

    def test_optional_assurance_cannot_block_development(self) -> None:
        status = json.loads((ROOT / "governance" / "bootstrap-status.json").read_text(encoding="utf-8"))
        gate = status["authoritative_delivery_gate"]
        self.assertEqual("not_required_for_development", gate["status"])
        self.assertEqual("", gate["required_dependency"])
        self.assertNotEqual("blocked", status["publication"]["status"])
        self.assertEqual([], _development_authority_errors(status))

    def test_contradictory_or_incomplete_authority_state_is_rejected(self) -> None:
        status = json.loads((ROOT / "governance" / "bootstrap-status.json").read_text(encoding="utf-8"))
        mutations = {
            "missing_publication_status": lambda value: value["publication"].pop("status"),
            "blank_publication_reason": lambda value: value["publication"].update({"reason": " "}),
            "branch_protection_required": lambda value: value["authoritative_delivery_gate"].update(
                {"branch_protection_requires_governance": True}
            ),
            "missing_authority_field": lambda value: value["authoritative_delivery_gate"].pop(
                "trusted_runner_provenance_established"
            ),
            "external_dependency": lambda value: value["authoritative_delivery_gate"].update(
                {"required_dependency": "trust root"}
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                candidate = copy.deepcopy(status)
                mutate(candidate)
                self.assertTrue(_development_authority_errors(candidate))

    def test_protected_dev_and_automatic_agent_review_are_removed(self) -> None:
        self.assertFalse((ROOT / "governance" / "protected-dev-ruleset.json").exists())
        self.assertFalse((ROOT / ".github" / "workflows" / "agent-review.yml").exists())
        ci = (ROOT / ".github" / "workflows" / "governance.yml").read_text(encoding="utf-8")
        self.assertNotIn("--check-bootstrap-blocked", ci)
        self.assertNotIn("Bootstrap honesty", ci)


if __name__ == "__main__":
    unittest.main()
