"""Tests for the command registry."""

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_REGISTRY_PATH = REPO_ROOT / "governance" / "command-registry.json"


class TestCommandRegistry(unittest.TestCase):
    """Test that the command registry is well-formed."""

    def setUp(self):
        with open(COMMAND_REGISTRY_PATH) as f:
            self.registry = json.load(f)

    def test_has_required_keys(self):
        self.assertIn("schema_version", self.registry)
        self.assertIn("commands", self.registry)
        self.assertIn("rules", self.registry)

    def test_repo_validate_is_registered(self):
        self.assertIn("repo.validate", self.registry["commands"])

    def test_tests_all_is_registered(self):
        self.assertIn("tests.all", self.registry["commands"])

    def test_governance_manifest_is_registered(self):
        self.assertIn("governance.manifest", self.registry["commands"])

    def test_governance_delivery_gate_is_registered(self):
        self.assertIn("governance.delivery_gate", self.registry["commands"])

    def test_workflow_pinning_is_registered(self):
        self.assertIn("workflow.pinning", self.registry["commands"])

    def test_validate_repo_is_not_a_test(self):
        cmd = self.registry["commands"]["repo.validate"]
        self.assertFalse(cmd["counts_as_test"])
        self.assertTrue(cmd["counts_as_validation"])

    def test_tests_all_is_not_validation(self):
        cmd = self.registry["commands"]["tests.all"]
        self.assertTrue(cmd["counts_as_test"])
        self.assertFalse(cmd["counts_as_validation"])

    def test_governance_manifest_is_validation_not_test(self):
        cmd = self.registry["commands"]["governance.manifest"]
        self.assertFalse(cmd["counts_as_test"])
        self.assertTrue(cmd["counts_as_validation"])

    def test_validate_repo_cannot_be_test_rule(self):
        self.assertTrue(self.registry["rules"]["validate_repo_cannot_be_test"])

    def test_unregistered_commands_invalid_rule(self):
        self.assertTrue(self.registry["rules"]["unregistered_commands_invalid"])

    def test_model_prose_not_evidence_rule(self):
        self.assertIn("model_prose_not_evidence", self.registry["rules"])
        self.assertTrue(len(self.registry["rules"]["model_prose_not_evidence"]) > 0)

    def test_all_commands_have_required_fields(self):
        for cmd_id, cmd in self.registry["commands"].items():
            with self.subTest(cmd_id=cmd_id):
                self.assertIn("category", cmd)
                self.assertIn("argv", cmd)
                self.assertIn("cwd", cmd)
                self.assertIn("description", cmd)
                self.assertIn("counts_as_test", cmd)
                self.assertIn("counts_as_validation", cmd)

    def test_categories_are_valid(self):
        valid_categories = {"validation", "test", "gate"}
        for cmd_id, cmd in self.registry["commands"].items():
            with self.subTest(cmd_id=cmd_id):
                self.assertIn(cmd["category"], valid_categories)

    def test_no_command_is_both_test_and_validation(self):
        for cmd_id, cmd in self.registry["commands"].items():
            with self.subTest(cmd_id=cmd_id):
                self.assertFalse(cmd["counts_as_test"] and cmd["counts_as_validation"])
