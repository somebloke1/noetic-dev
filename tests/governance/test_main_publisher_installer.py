"""Behavioral tests for the fixed privileged main-publisher installer."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "deploy/install-main-publisher.sh"
CRITICAL_FILES = (
    "deploy/install-main-publisher.sh",
    "deploy/noetic-dev-promote-main",
    "scripts/governance/promote_main.py",
    "scripts/governance/check_delivery_gate.py",
    "scripts/governance/check_evidence_manifest.py",
    "scripts/governance/hash_tree.py",
    "scripts/governance/json_schema.py",
    "scripts/governance/route_evidence.py",
)


def run(*argv: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


class TestMainPublisherInstaller(unittest.TestCase):
    def _build_remote(self, root: Path, marker: str = "primary") -> tuple[Path, str, str]:
        remote = root / "remote"
        remote.mkdir()
        self.assertEqual(run("git", "init", "-b", "dev", cwd=remote).returncode, 0)
        self.assertEqual(
            run("git", "config", "user.name", "Installer Test", cwd=remote).returncode,
            0,
        )
        self.assertEqual(
            run("git", "config", "user.email", "installer@example.invalid", cwd=remote).returncode,
            0,
        )
        for relative in CRITICAL_FILES:
            target = remote / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if relative == "deploy/install-main-publisher.sh":
                target.write_bytes(INSTALLER.read_bytes())
            else:
                target.write_text(
                    f"protected policy {marker}: {relative}\n", encoding="utf-8"
                )
            target.chmod(0o755 if relative.startswith("deploy/") else 0o644)
        (remote / "policy-only.txt").write_text("protected policy\n", encoding="utf-8")
        self.assertEqual(run("git", "add", ".", cwd=remote).returncode, 0)
        self.assertEqual(run("git", "commit", "-m", "policy", cwd=remote).returncode, 0)
        policy_sha = run("git", "rev-parse", "HEAD", cwd=remote).stdout.strip()

        (remote / "candidate-only.txt").write_text("candidate bytes\n", encoding="utf-8")
        self.assertEqual(run("git", "add", ".", cwd=remote).returncode, 0)
        self.assertEqual(run("git", "commit", "-m", "candidate", cwd=remote).returncode, 0)
        candidate_sha = run("git", "rev-parse", "HEAD", cwd=remote).stdout.strip()
        return remote, policy_sha, candidate_sha

    def _run_installer(
        self,
        *,
        stage0: Path,
        install_root: Path,
        remote: Path,
        verifier: Path,
        launcher: Path,
        key: Path,
        git_wrapper: Path,
        policy_sha: str,
        candidate_sha: str,
        receipt: Path,
    ) -> subprocess.CompletedProcess[str]:
        return run(
            str(INSTALLER),
            "--test",
            str(stage0),
            str(install_root),
            str(remote),
            str(verifier),
            str(launcher),
            str(key),
            str(git_wrapper),
            str(os.getuid()),
            str(os.getgid()),
            policy_sha,
            candidate_sha,
            str(receipt),
            str(stage0.parent.parent),
            str(stage0.parent.parent / "install.lock"),
        )

    def test_installer_fetches_policy_verifies_receipt_and_installs_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            remote, policy_sha, candidate_sha = self._build_remote(temporary)
            fixed = temporary / "fixed"
            fixed.mkdir()
            fixed.chmod(0o700)
            stage0 = fixed / "noetic-dev-install-main-publisher"
            stage0.write_bytes(INSTALLER.read_bytes())
            stage0.chmod(0o700)

            verifier_log = temporary / "verifier-challenge.json"
            verifier = fixed / "verify-delivery-attestation"
            verifier.write_text(
                "#!/usr/bin/python3\n"
                "import json, sys\n"
                "challenge = json.load(sys.stdin)\n"
                f"json.dump(challenge, open({str(verifier_log)!r}, 'w', encoding='utf-8'))\n"
                "raise SystemExit(0 if challenge.get('receipt') == {'authorized': True} else 17)\n",
                encoding="utf-8",
            )
            verifier.chmod(0o700)

            key = fixed / "deploy-key"
            generated = run("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key))
            self.assertEqual(generated.returncode, 0, generated.stderr)
            key.chmod(0o400)

            git_log = temporary / "git.log"
            git_wrapper = fixed / "git"
            git_wrapper.write_text(
                "#!/bin/sh\n"
                f"/usr/bin/printf '%s\\n' \"$*\" >> {shlex.quote(str(git_log))}\n"
                "exec /usr/bin/git \"$@\"\n",
                encoding="utf-8",
            )
            git_wrapper.chmod(0o700)

            receipt = fixed / "receipt.json"
            receipt.write_text('{"authorized":true}\n', encoding="utf-8")
            receipt.chmod(0o600)
            install_root = temporary / "installed"
            launcher = fixed / "promote-main"
            common = {
                "stage0": stage0,
                "remote": remote,
                "verifier": verifier,
                "key": key,
                "git_wrapper": git_wrapper,
                "policy_sha": policy_sha,
            }

            result = self._run_installer(
                install_root=install_root,
                launcher=launcher,
                candidate_sha=candidate_sha,
                receipt=receipt,
                **common,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            release = install_root / "policy-releases" / policy_sha / candidate_sha
            repository = release / "repository"
            self.assertTrue((repository / "policy-only.txt").is_file())
            self.assertFalse((repository / "candidate-only.txt").exists())
            self.assertEqual((repository / "deploy/install-main-publisher.sh").stat().st_mode & 0o022, 0)
            self.assertEqual(
                launcher.read_bytes(),
                (repository / "deploy/noetic-dev-promote-main").read_bytes(),
            )
            self.assertEqual((install_root / "current").resolve(), release)

            installation = json.loads(
                (release / "publisher-installation.json").read_text(encoding="utf-8")
            )
            claims = installation["expected_claims"]
            self.assertEqual(claims["policy_sha"], policy_sha)
            self.assertEqual(claims["candidate_sha"], candidate_sha)
            self.assertEqual(claims["policy_tree_sha"], run("git", "rev-parse", f"{policy_sha}^{{tree}}", cwd=remote).stdout.strip())
            self.assertEqual(claims["candidate_tree_sha"], run("git", "rev-parse", f"{candidate_sha}^{{tree}}", cwd=remote).stdout.strip())
            challenge = json.loads(verifier_log.read_text(encoding="utf-8"))
            self.assertEqual(challenge["expected_claims"], claims)
            self.assertIn("fetch --no-tags", git_log.read_text(encoding="utf-8"))
            self.assertIn(f"archive {policy_sha}", git_log.read_text(encoding="utf-8"))

            rejected_receipt = fixed / "rejected-receipt.json"
            rejected_receipt.write_text('{"authorized":false}\n', encoding="utf-8")
            rejected_receipt.chmod(0o600)
            rejected_root = temporary / "rejected"
            rejected = self._run_installer(
                install_root=rejected_root,
                launcher=fixed / "rejected-promote-main",
                candidate_sha=candidate_sha,
                receipt=rejected_receipt,
                **common,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertFalse(rejected_root.exists())

            wrong_head_root = temporary / "wrong-head"
            wrong_head = self._run_installer(
                install_root=wrong_head_root,
                launcher=fixed / "wrong-head-promote-main",
                candidate_sha="f" * 40,
                receipt=receipt,
                **common,
            )
            self.assertNotEqual(wrong_head.returncode, 0)
            self.assertFalse(wrong_head_root.exists())

            collision_root = temporary / "collision"
            collision_root.mkdir()
            collision_root.chmod(0o755)
            (collision_root / "current.new").mkdir()
            collision = self._run_installer(
                install_root=collision_root,
                launcher=fixed / "collision-promote-main",
                candidate_sha=candidate_sha,
                receipt=receipt,
                **common,
            )
            self.assertNotEqual(collision.returncode, 0)
            self.assertTrue((collision_root / "current.new").is_dir())
            self.assertFalse(
                (collision_root / "policy-releases" / policy_sha / candidate_sha).exists()
            )

            for blocker_type in ("file", "symlink"):
                blocked_root = temporary / f"current-new-{blocker_type}"
                blocked_root.mkdir()
                blocked_root.chmod(0o755)
                blocker = blocked_root / "current.new"
                if blocker_type == "file":
                    blocker.write_text("preexisting\n", encoding="utf-8")
                else:
                    blocker.symlink_to(blocked_root / "missing")
                blocked = self._run_installer(
                    install_root=blocked_root,
                    launcher=fixed / f"current-new-{blocker_type}-launcher",
                    candidate_sha=candidate_sha,
                    receipt=receipt,
                    **common,
                )
                self.assertNotEqual(blocked.returncode, 0)
                self.assertTrue(blocker.exists() or blocker.is_symlink())
                self.assertFalse(
                    (blocked_root / "policy-releases" / policy_sha / candidate_sha).exists()
                )

            current_directory_root = temporary / "current-directory"
            current_directory_root.mkdir()
            current_directory_root.chmod(0o755)
            (current_directory_root / "current").mkdir()
            current_directory = self._run_installer(
                install_root=current_directory_root,
                launcher=fixed / "current-directory-launcher",
                candidate_sha=candidate_sha,
                receipt=receipt,
                **common,
            )
            self.assertNotEqual(current_directory.returncode, 0)
            self.assertTrue((current_directory_root / "current").is_dir())
            self.assertFalse(
                (current_directory_root / "policy-releases" / policy_sha / candidate_sha).exists()
            )

            writable_parent = temporary / "writable-launcher"
            writable_parent.mkdir()
            writable_parent.chmod(0o777)
            rejected_root = temporary / "writable-parent-rejected"
            writable = self._run_installer(
                install_root=rejected_root,
                launcher=writable_parent / "promote-main",
                candidate_sha=candidate_sha,
                receipt=receipt,
                **common,
            )
            self.assertNotEqual(writable.returncode, 0)
            self.assertFalse(rejected_root.exists())
            writable_parent.chmod(0o700)
            retry = self._run_installer(
                install_root=rejected_root,
                launcher=writable_parent / "promote-main",
                candidate_sha=candidate_sha,
                receipt=receipt,
                **common,
            )
            self.assertEqual(retry.returncode, 0, retry.stderr)
            self.assertTrue((rejected_root / "current").is_symlink())

            dangling_launcher = fixed / "dangling-promote-main"
            dangling_launcher.symlink_to(fixed / "missing-launcher-target")
            dangling_root = temporary / "dangling-launcher-rejected"
            dangling = self._run_installer(
                install_root=dangling_root,
                launcher=dangling_launcher,
                candidate_sha=candidate_sha,
                receipt=receipt,
                **common,
            )
            self.assertNotEqual(dangling.returncode, 0)
            self.assertTrue(dangling_launcher.is_symlink())
            self.assertFalse(dangling_root.exists())

            launcher_directory = fixed / "directory-promote-main"
            launcher_directory.mkdir()
            directory_root = temporary / "launcher-directory-rejected"
            directory_result = self._run_installer(
                install_root=directory_root,
                launcher=launcher_directory,
                candidate_sha=candidate_sha,
                receipt=receipt,
                **common,
            )
            self.assertNotEqual(directory_result.returncode, 0)
            self.assertTrue(launcher_directory.is_dir())
            self.assertFalse(directory_root.exists())

            secondary_root = temporary / "secondary"
            secondary_root.mkdir()
            remote_two, policy_two, candidate_two = self._build_remote(
                secondary_root, marker="secondary"
            )
            concurrent_root = temporary / "concurrent"
            concurrent_launcher = fixed / "concurrent-promote-main"
            calls = (
                (remote, policy_sha, candidate_sha),
                (remote_two, policy_two, candidate_two),
            )
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(
                    executor.map(
                        lambda call: self._run_installer(
                            stage0=stage0,
                            install_root=concurrent_root,
                            remote=call[0],
                            verifier=verifier,
                            launcher=concurrent_launcher,
                            key=key,
                            git_wrapper=git_wrapper,
                            policy_sha=call[1],
                            candidate_sha=call[2],
                            receipt=receipt,
                        ),
                        calls,
                    )
                )
            self.assertEqual([result.returncode for result in results], [0, 0])
            selected_release = (concurrent_root / "current").resolve()
            expected_releases = {
                concurrent_root / "policy-releases" / policy_sha / candidate_sha,
                concurrent_root / "policy-releases" / policy_two / candidate_two,
            }
            self.assertIn(selected_release, expected_releases)
            self.assertEqual(
                concurrent_launcher.read_bytes(),
                (selected_release / "repository/deploy/noetic-dev-promote-main").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
