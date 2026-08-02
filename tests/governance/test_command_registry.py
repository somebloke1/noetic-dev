"""Tests for the command registry."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_REGISTRY_PATH = REPO_ROOT / "governance" / "command-registry.json"


class TestCommandRegistry(unittest.TestCase):
    def setUp(self):
        with open(COMMAND_REGISTRY_PATH, encoding="utf-8") as f:
            self.registry = json.load(f)

    def test_has_required_keys(self):
        self.assertEqual(self.registry["schema_version"], "1")
        self.assertIn("commands", self.registry)
        self.assertIn("rules", self.registry)
        self.assertTrue((REPO_ROOT / "governance" / self.registry["$schema"].removeprefix("./")).exists())

    def test_required_commands_registered(self):
        for command_id in [
            "repo.validate",
            "workflow.pinning",
            "tests.all",
            "governance.manifest",
            "governance.delivery_gate",
            "postmerge.validate",
            "postmerge.tests",
        ]:
            with self.subTest(command_id=command_id):
                self.assertIn(command_id, self.registry["commands"])

    def test_validate_repo_is_validation_not_test(self):
        cmd = self.registry["commands"]["repo.validate"]
        self.assertEqual(cmd["category"], "validation")
        self.assertFalse(cmd["counts_as_test"])
        self.assertTrue(cmd["counts_as_validation"])

    def test_tests_all_is_test_not_validation(self):
        cmd = self.registry["commands"]["tests.all"]
        self.assertEqual(cmd["category"], "test")
        self.assertTrue(cmd["counts_as_test"])
        self.assertFalse(cmd["counts_as_validation"])

    def test_required_pre_merge_lists_are_canonical(self):
        rules = self.registry["rules"]
        self.assertEqual(rules["required_pre_merge_validations"], ["repo.validate"])
        self.assertEqual(rules["required_pre_merge_tests"], ["tests.all"])

    def test_optional_assurance_does_not_gate_development(self):
        pinning = self.registry["commands"]["workflow.pinning"]
        assurance = self.registry["commands"]["governance.delivery_gate"]
        self.assertFalse(pinning["required_for_merge"])
        self.assertFalse(assurance["required_for_merge"])
        self.assertIn("does not gate ordinary development", assurance["description"])

    def test_required_post_merge_lists_are_canonical(self):
        rules = self.registry["rules"]
        self.assertEqual(rules["required_post_merge_validations"], ["postmerge.validate"])
        self.assertEqual(rules["required_post_merge_tests"], ["postmerge.tests"])

    def test_registry_rules_prevent_false_equivalences(self):
        rules = self.registry["rules"]
        self.assertTrue(rules["validate_repo_cannot_be_test"])
        self.assertTrue(rules["unregistered_commands_invalid"])
        self.assertIn("Model output", rules["model_prose_not_evidence"])

    def test_all_commands_have_required_fields(self):
        valid_categories = {"validation", "test", "gate"}
        for cmd_id, cmd in self.registry["commands"].items():
            with self.subTest(cmd_id=cmd_id):
                for field in ["category", "argv", "cwd", "description", "counts_as_test", "counts_as_validation"]:
                    self.assertIn(field, cmd)
                self.assertIn(cmd["category"], valid_categories)
                self.assertFalse(cmd["counts_as_test"] and cmd["counts_as_validation"])


if __name__ == "__main__":
    unittest.main()
