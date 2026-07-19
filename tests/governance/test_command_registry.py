"""Tests for the command registry."""

from __future__ import annotations

import json
import re
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
        self.assertEqual(rules["required_pre_merge_validations"], ["repo.validate", "workflow.pinning"])
        self.assertEqual(rules["required_pre_merge_tests"], ["tests.all"])

    def test_required_post_merge_lists_are_canonical(self):
        rules = self.registry["rules"]
        self.assertEqual(rules["required_post_merge_validations"], ["postmerge.validate"])
        self.assertEqual(rules["required_post_merge_tests"], ["postmerge.tests"])

    def test_main_publisher_uses_fixed_root_launcher_and_immutable_release(self):
        command = self.registry["commands"]["main.promote_exact"]
        self.assertEqual(
            command["argv"][0], "/usr/local/libexec/noetic-dev/promote-main"
        )
        installer = (REPO_ROOT / "deploy/install-main-publisher.sh").read_text(
            encoding="utf-8"
        )
        launcher = (REPO_ROOT / "deploy/noetic-dev-promote-main").read_text(
            encoding="utf-8"
        )
        self.assertIn("$EUID -ne 0", installer)
        self.assertNotIn("NOETIC_SOURCE", installer)
        self.assertIn("https://github.com/somebloke1/noetic-dev.git", installer)
        self.assertIn("refs/heads/dev:refs/heads/dev", installer)
        self.assertIn("install-main-publisher", installer)
        self.assertIn("verify-delivery-attestation", installer)
        self.assertIn("trusted_executable_path", installer)
        self.assertIn("[[ ! -L $current ]]", installer)
        self.assertIn("[[ $owner -eq 0 ]]", installer)
        self.assertIn("(mode & 8#022) == 0", installer)
        self.assertIn("current=$(/usr/bin/dirname \"$current\")", installer)
        self.assertIn("GIT_NO_REPLACE_OBJECTS=1", installer)
        self.assertIn("/usr/bin/git --no-replace-objects", installer)
        self.assertIn("archive \"$authorized_sha\"", installer)
        self.assertIn("actual_tree", installer)
        self.assertIn('/usr/bin/find "$release" -type l -print -quit', installer)
        self.assertIn("! -L $release/deploy/noetic-dev-promote-main", installer)
        self.assertIn("! -L $release/scripts/governance/promote_main.py", installer)
        self.assertIn("chown -R root:root \"$release\"", installer)
        self.assertIn("chmod -R go-w \"$release\"", installer)
        self.assertIn("/opt/noetic-dev-main-publisher", launcher)
        self.assertIn("exec /usr/bin/python3", launcher)
        self.assertFalse((REPO_ROOT / "deploy/noetic-dev-promote-main").is_symlink())
        self.assertFalse((REPO_ROOT / "scripts/governance/promote_main.py").is_symlink())

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

    def test_every_argv_placeholder_has_a_declared_anchored_grammar(self):
        for command_id, command in self.registry["commands"].items():
            declared = command.get("placeholder_grammars", {})
            placeholders = {
                name
                for argument in command["argv"]
                for name in re.findall(r"\{\{([a-z0-9_]+)\}\}", argument)
            }
            with self.subTest(command_id=command_id):
                self.assertEqual(placeholders, set(declared))
                self.assertTrue(
                    all(grammar.startswith("^") and grammar.endswith("$") for grammar in declared.values())
                )


if __name__ == "__main__":
    unittest.main()
