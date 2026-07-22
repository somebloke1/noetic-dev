"""Tests for the command registry."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
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
            "roadmap.migration_v1_v2",
            "workflow.pinning",
            "tests.all",
            "governance.manifest",
            "governance.delivery_gate",
            "postmerge.validate",
            "postmerge.tests",
            "main.promote_exact",
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

    def test_main_publisher_uses_distinct_protected_policy_release(self):
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
        self.assertIn("actual_uid=$(/usr/bin/id -u)", installer)
        self.assertTrue(installer.startswith("#!/usr/bin/bash -p\n"))
        self.assertIn("[[ $- == *p* ]] || exit 2", installer)
        self.assertIn(
            "unset BASH_ENV ENV CDPATH GLOBIGNORE TMPDIR TMP TEMP",
            installer,
        )
        self.assertIn("/usr/local/sbin/noetic-dev-install-main-publisher", installer)
        self.assertIn('$(/usr/bin/readlink -f "$0") != "$stage0"', installer)
        self.assertNotIn("NOETIC_SOURCE", installer)
        self.assertIn("https://github.com/somebloke1/noetic-dev.git", installer)
        self.assertIn("refs/heads/dev:refs/heads/dev", installer)
        self.assertIn("install-main-publisher", installer)
        self.assertIn('[[ $policy_sha != "$authorized_sha" ]]', installer)
        self.assertIn('merge-base --is-ancestor "$policy_sha" "$authorized_sha"', installer)
        self.assertIn("verify-delivery-attestation", installer)
        self.assertIn("trusted_executable_path", installer)
        self.assertIn("trusted_private_key_path", installer)
        self.assertIn("trusted_or_absent_directory_path", installer)
        self.assertIn("trusted_directory_path", installer)
        self.assertIn("/etc/noetic-dev/main-publisher/deploy-key", installer)
        self.assertIn("$mode -eq 8#400", installer)
        self.assertIn("/usr/bin/ssh-keygen -y -P ''", installer)
        self.assertIn("[[ ! -L $current ]]", installer)
        self.assertIn("install_owner=0", installer)
        self.assertIn("$owner -eq 0 || $owner -eq $install_owner", installer)
        self.assertIn("(mode & 8#022) == 0", installer)
        self.assertIn("current=$(/usr/bin/dirname \"$current\")", installer)
        self.assertIn("GIT_NO_REPLACE_OBJECTS=1", installer)
        self.assertIn("git_executable=/usr/bin/git", installer)
        self.assertIn('"$git_executable" --no-replace-objects', installer)
        self.assertIn('archive "$policy_sha"', installer)
        self.assertNotIn('archive "$authorized_sha"', installer)
        self.assertIn("actual_tree", installer)
        self.assertIn('/usr/bin/find "$staging" -type l -print -quit', installer)
        self.assertIn("policy_files_sha256", installer)
        self.assertIn("policy_tree_sha", installer)
        self.assertIn("candidate_tree_sha", installer)
        self.assertIn("installer_sha256", installer)
        self.assertIn('"$staging/deploy/install-main-publisher.sh"', installer)
        self.assertIn("verifier_sha256", installer)
        self.assertIn("authorization_receipt_sha256", installer)
        self.assertIn("publisher-installation-receipt.json", installer)
        self.assertIn("chown -R \"$install_owner:$install_group\" \"$installation_staging\"", installer)
        self.assertIn("chmod -R go-w \"$installation_staging\"", installer)
        self.assertIn('[[ ! -e $current_new && ! -L $current_new ]]', installer)
        self.assertIn('/usr/bin/ln -sT "$release" "$current_new"', installer)
        self.assertIn("release_created=true", installer)
        self.assertIn("/usr/bin/flock -x", installer)
        self.assertIn("/run/noetic-dev-main-publisher/install.lock", installer)
        self.assertIn("-m 0700", installer)
        self.assertIn("/opt/noetic-dev-main-publisher", launcher)
        self.assertIn("policy-releases", launcher)
        self.assertIn("NOETIC_PUBLISHER_INSTALLATION", launcher)
        self.assertIn("publisher-installation-receipt.json", launcher)
        self.assertIn("$release/repository/scripts/governance/promote_main.py", launcher)
        self.assertIn("/usr/bin/id -u", launcher)
        self.assertIn("exec /usr/bin/env -i", launcher)
        self.assertIn("HOME=/root", launcher)
        self.assertIn("/usr/bin/python3 -I", launcher)
        self.assertNotIn("SSH_AUTH_SOCK", launcher)
        self.assertNotIn("key_path", " ".join(command["argv"]))
        self.assertFalse((REPO_ROOT / "deploy/noetic-dev-promote-main").is_symlink())
        self.assertFalse((REPO_ROOT / "scripts/governance/promote_main.py").is_symlink())

    def test_stage0_direct_execution_ignores_path_and_bash_env_startup_code(self):
        installer = REPO_ROOT / "deploy/install-main-publisher.sh"
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            marker = temporary / "startup-code-ran"
            fake_bash = temporary / "bash"
            fake_bash.write_text(
                f"#!/bin/sh\n/usr/bin/touch {marker}\nexec /usr/bin/bash \"$@\"\n",
                encoding="utf-8",
            )
            fake_bash.chmod(0o755)
            bash_env = temporary / "bash-env"
            bash_env.write_text(f"/usr/bin/touch {marker}\n", encoding="utf-8")
            env = dict(os.environ)
            env.update(
                {
                    "PATH": f"{temporary}:/usr/bin:/bin",
                    "BASH_ENV": str(bash_env),
                    "EUID": "123",
                    "git_executable": str(fake_bash),
                    "install_group": "1234",
                    "install_owner": "1234",
                    "TEMP": str(temporary),
                    "TMP": str(temporary),
                    "TMPDIR": str(temporary),
                    "trust_anchor": str(temporary),
                }
            )
            result = subprocess.run(
                [str(installer), "a" * 40, "b" * 40, str(bash_env)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                env=env,
            )
            marker_exists = marker.exists()
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)
        self.assertFalse(marker_exists)

    def test_stage0_rejects_non_privileged_sourcing_before_execution(self):
        installer = REPO_ROOT / "deploy/install-main-publisher.sh"
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    "/usr/bin/bash",
                    "-c",
                    'function /usr/bin/false { return 0; }; source "$1"',
                    "source-mode-test",
                    str(installer),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                env={
                    **os.environ,
                    "BASH_FUNC_return%%": "() { return 0; }",
                    "BASH_FUNC_unset%%": "() { return 0; }",
                    "TEMP": directory,
                    "TMP": directory,
                    "TMPDIR": directory,
                },
            )
            artifacts = list(Path(directory).iterdir())
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(artifacts, [])

    def test_stage0_rejects_symbolic_test_identity(self):
        installer = REPO_ROOT / "deploy/install-main-publisher.sh"
        result = subprocess.run(
            [
                str(installer),
                "--test",
                *(["unused"] * 7),
                f"{os.getuid()}+0",
                str(os.getgid()),
                "a" * 40,
                "b" * 40,
                "/tmp/receipt",
                "/",
                "/tmp/install.lock",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_stage0_validates_publisher_root_before_install_or_move(self):
        installer = (REPO_ROOT / "deploy/install-main-publisher.sh").read_text(
            encoding="utf-8"
        )
        validation = installer.index('trusted_or_absent_directory_path "$root"')
        root_install = installer.index(
            '/usr/bin/install -d -o "$install_owner" -g "$install_group" -m 0755 "$root"'
        )
        parent_recheck = installer.index(
            'trusted_directory_path "$root/policy-releases/$policy_sha"',
            root_install,
        )
        release_move = installer.index('/usr/bin/mv "$installation_staging" "$release"')
        self.assertLess(validation, root_install)
        self.assertLess(parent_recheck, release_move)

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
