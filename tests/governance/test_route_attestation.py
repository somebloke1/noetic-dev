"""Tests for recurring protected-route attestation orchestration."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
ROOT = Path(__file__).resolve().parents[2]
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

from route_attestation import (  # noqa: E402
    IneligibleRun,
    attest_run,
    load_attestation_context,
    main,
    select_runs,
    validate_existing_receipt,
    validate_from_protected_base,
    write_receipt,
)


def run_record(run_id: int = 123) -> dict:
    return {
        "id": run_id,
        "run_attempt": 1,
        "workflow_id": 312422987,
        "path": ".github/workflows/agent-review.yml",
        "event": "pull_request_target",
        "status": "completed",
        "conclusion": "success",
        "head_branch": "issue-route-canary",
        "head_sha": "a" * 40,
        "repository": {"id": 1297462728, "full_name": "somebloke1/noetic-dev"},
        "head_repository": {"id": 1297462728, "full_name": "somebloke1/noetic-dev"},
    }


def attestation_records() -> tuple[dict, dict, dict]:
    head_sha = "a" * 40
    artifacts = {
        "total_count": 1,
        "artifacts": [{
            "id": 789,
            "name": f"agent-review-55-{head_sha}",
            "expired": False,
            "size_in_bytes": 1024,
            "digest": f"sha256:{'c' * 64}",
            "workflow_run": {
                "id": 123,
                "repository_id": 1297462728,
                "head_repository_id": 1297462728,
                "head_sha": head_sha,
            },
        }],
    }
    pull = {
        "number": 55,
        "state": "closed",
        "merged": True,
        "draft": False,
        "head": {
            "ref": "issue-route-canary",
            "sha": head_sha,
            "repo": {"id": 1297462728, "full_name": "somebloke1/noetic-dev"},
        },
        "base": {
            "ref": "dev",
            "sha": "b" * 40,
            "repo": {"id": 1297462728, "full_name": "somebloke1/noetic-dev"},
        },
    }
    jobs = {"total_count": 1, "jobs": [{
        "id": 456,
        "run_id": 123,
        "run_attempt": 1,
        "workflow_name": "Agent Review",
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": "success",
        "name": "agent-review",
        "labels": ["self-hosted", "noetic-dev", "terra-review"],
        "steps": [
            {"name": name, "conclusion": "success"}
            for name in [
                "Set up job",
                "Checkout protected policy SHA only",
                "Enforce local-runner admission policy",
                "Request immutable semantic review",
                "Retain exact-SHA route evidence",
                "Upload exact-SHA route evidence",
                "Post Checkout protected policy SHA only",
                "Complete job",
            ]
        ],
    }]}
    return artifacts, pull, jobs


def valid_receipt(run_id: int = 123) -> dict:
    return {
        "schema_version": "1",
        "repository": "somebloke1/noetic-dev",
        "run_id": run_id,
        "run_attempt": 1,
        "workflow_id": 312422987,
        "job_id": 456,
        "pr_number": 55,
        "head_sha": "a" * 40,
        "base_sha": "b" * 40,
        "artifact_id": 789,
        "artifact_name": f"agent-review-55-{'a' * 40}",
        "artifact_digest": f"sha256:{'c' * 64}",
        "artifact_size": 1024,
        "run_head_sha": "a" * 40,
        "run_head_branch": "issue-route-canary",
        "pr_state": "closed",
        "pr_merged": True,
        "validator_sha256": "d" * 64,
        "result": "valid",
        "validated_at": "2026-07-17T20:00:00Z",
    }


class TestRouteAttestation(unittest.TestCase):
    def test_selects_only_unattested_successful_runs_after_cutoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            existing = state / "run-125-attempt-1.json"
            write_receipt(existing, valid_receipt(125))
            response = {"workflow_runs": [run_record(125), run_record(124), run_record(100)]}
            with mock.patch("route_attestation.github_json_pages", return_value=[response]):
                selected = select_runs(None, 100, state)
            self.assertEqual([item["id"] for item in selected], [124, 125])

            with mock.patch(
                "route_attestation.github_json_pages",
                return_value=[{"workflow_runs": [run_record(100)]}],
            ):
                self.assertEqual(select_runs(None, 100, state), [])

            duplicate = {"workflow_runs": [run_record(126), run_record(126), run_record(100)]}
            with mock.patch("route_attestation.github_json_pages", return_value=[duplicate]):
                self.assertEqual(
                    [item["id"] for item in select_runs(None, 100, state)], [126]
                )

            malformed = {
                "workflow_runs": [
                    {"id": "bad", "run_attempt": 1}, run_record(127), run_record(100),
                ]
            }
            with mock.patch("route_attestation.github_json_pages", return_value=[malformed]):
                self.assertEqual(
                    [item["id"] for item in select_runs(None, 100, state)], [127]
                )

            in_flight = run_record(128)
            in_flight["status"] = "in_progress"
            in_flight["conclusion"] = None
            out_of_order = {
                "workflow_runs": [run_record(100), in_flight, run_record(129)]
            }
            with mock.patch(
                "route_attestation.github_json_pages", return_value=[out_of_order]
            ):
                self.assertEqual(select_runs(None, 100, state), [])

    def test_discovery_paginates_and_one_failure_does_not_starve_later_runs(self) -> None:
        failed = [{**run_record(1000 - index), "conclusion": "failure"} for index in range(100)]
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "route_attestation.github_json_pages",
            return_value=[{"workflow_runs": failed}, {"workflow_runs": [run_record(1100)]}],
        ):
            selected = select_runs(None, 0, Path(directory))
        self.assertEqual([item["id"] for item in selected], [1100])

        runs = [run_record(201), run_record(202)]
        arguments = ["route_attestation.py", "--state-dir", "/tmp/state"]
        with mock.patch.object(sys, "argv", arguments), mock.patch(
            "route_attestation.select_runs", return_value=runs
        ), mock.patch(
            "route_attestation.attest_run", side_effect=[ValueError("bad run"), Path("receipt.json")]
        ) as attest, mock.patch("route_attestation.write_cursor"):
            self.assertEqual(main(), 1)
        self.assertEqual(attest.call_count, 2)

    def test_successful_rerun_receives_terminal_disposition(self) -> None:
        rerun = run_record(203)
        rerun["run_attempt"] = 2
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            arguments = ["route_attestation.py", "--state-dir", directory]
            with mock.patch.object(sys, "argv", arguments), mock.patch(
                "route_attestation.select_runs", return_value=[rerun]
            ), mock.patch("route_attestation.write_skip") as skip, mock.patch(
                "route_attestation.write_cursor"
            ) as cursor:
                self.assertEqual(main(), 0)
        skip.assert_called_once_with(
            state, 203, 2, "unsupported-rerun-attempt", None
        )
        cursor.assert_called_once_with(state, 203)

    def test_records_exact_run_artifact_pr_job_and_validator(self) -> None:
        run = run_record()
        artifacts, pull, jobs = attestation_records()
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "route_attestation.github_json",
            side_effect=[run, artifacts, pull, jobs, run, artifacts, pull, jobs],
        ), mock.patch(
            "route_attestation.validate_from_protected_base", return_value="d" * 64
        ) as validate, mock.patch(
            "route_attestation.retained_base_sha", return_value="b" * 40
        ):
            receipt_path = attest_run(run, Path(directory))
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        validate.assert_called_once_with(123, 55, "a" * 40, "b" * 40)
        self.assertEqual(receipt["artifact_id"], 789)
        self.assertEqual(receipt["artifact_digest"], f"sha256:{'c' * 64}")
        self.assertEqual(receipt["job_id"], 456)
        self.assertEqual(receipt["validator_sha256"], "d" * 64)
        self.assertEqual(receipt["result"], "valid")

    def test_metadata_must_remain_stable_across_protected_validation(self) -> None:
        run = run_record()
        artifacts, pull, jobs = attestation_records()
        changed = json.loads(json.dumps(artifacts))
        changed["artifacts"][0]["digest"] = f"sha256:{'e' * 64}"
        responses = [run, artifacts, pull, jobs, run, changed, pull, jobs]
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "route_attestation.github_json", side_effect=responses
        ), mock.patch(
            "route_attestation.validate_from_protected_base", return_value="d" * 64
        ), mock.patch("route_attestation.retained_base_sha", return_value="b" * 40):
            with self.assertRaisesRegex(ValueError, "changed during attestation"):
                attest_run(run, Path(directory))

    def test_closed_unmerged_run_is_classified_without_retained_artifact(self) -> None:
        run = run_record()
        artifacts, pull, jobs = attestation_records()
        artifacts["artifacts"][0]["expired"] = True
        pull.update({"state": "closed", "merged": False})
        with mock.patch(
            "route_attestation.github_json", side_effect=[run, artifacts, pull, jobs]
        ), mock.patch("route_attestation.retained_base_sha") as retained:
            with self.assertRaises(IneligibleRun):
                load_attestation_context(123)
        retained.assert_not_called()

    def test_attestation_metadata_fails_closed(self) -> None:
        run = run_record()
        artifacts, pull, jobs = attestation_records()
        mutations = [
            ({**artifacts, "total_count": 2}, pull, jobs),
            ({**artifacts, "artifacts": [{**artifacts["artifacts"][0], "expired": True}]}, pull, jobs),
            (artifacts, {**pull, "base": {"ref": "main", "sha": "b" * 40}}, jobs),
            (artifacts, {**pull, "base": {**pull["base"], "sha": "e" * 40}}, jobs),
            (artifacts, pull, {"total_count": 2, "jobs": jobs["jobs"]}),
            (artifacts, {**pull, "state": "open", "merged": False}, jobs),
        ]
        for responses in mutations:
            with self.subTest(responses=responses), tempfile.TemporaryDirectory() as directory, mock.patch(
                "route_attestation.github_json", side_effect=[run, *responses]
            ), mock.patch(
                "route_attestation.validate_from_protected_base"
            ) as validate, mock.patch(
                "route_attestation.retained_base_sha", return_value="b" * 40
            ):
                with self.assertRaises(ValueError):
                    attest_run(run, Path(directory))
                validate.assert_not_called()

    def test_fresh_clone_executes_only_the_protected_base_validator(self) -> None:
        commands = []
        environments = []

        def execute(command, **kwargs):
            commands.append(command)
            environments.append(kwargs["env"])
            if command[1] == "clone":
                checkout = Path(command[-1])
                validator = checkout / "scripts/governance/route_evidence.py"
                validator.parent.mkdir(parents=True)
                validator.write_text("# protected validator\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, b"", b"")
            if "checkout" in command:
                return subprocess.CompletedProcess(command, 0, b"", b"")
            kwargs["stdout"].write(b"Protected route evidence is valid\n")
            return subprocess.CompletedProcess(command, 0, b"", b"")

        with mock.patch("route_attestation.subprocess.run", side_effect=execute):
            digest = validate_from_protected_base(123, 55, "a" * 40, "b" * 40)
        self.assertEqual(len(digest), 64)
        self.assertEqual(commands[0][0:3], ["/usr/bin/git", "clone", "--filter=blob:none"])
        self.assertIn("--detach", commands[1])
        self.assertEqual(commands[2][0:2], ["/usr/bin/python3", "-I"])
        self.assertIn("route_evidence.py", commands[2][2])
        self.assertEqual(commands[2][-6:], [
            "--run-id", "123", "--pr-number", "55", "--head-sha", "a" * 40,
        ])
        for environment in environments:
            self.assertNotIn("PYTHONPATH", environment)
            self.assertNotIn("LD_PRELOAD", environment)
            self.assertEqual(environment["PATH"], "/usr/local/bin:/usr/bin:/bin")

    def test_receipt_is_atomic_private_and_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state" / "receipt.json"
            receipt = valid_receipt()
            write_receipt(path, receipt)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            validate_existing_receipt(path, 123, 1)
            with self.assertRaises(ValueError):
                write_receipt(path, receipt)

            path.chmod(0o644)
            with self.assertRaises(ValueError):
                validate_existing_receipt(path, 123, 1)
            path.chmod(0o600)
            alias = path.with_name("receipt-alias.json")
            os.link(path, alias)
            with self.assertRaises(ValueError):
                validate_existing_receipt(path, 123, 1)
            alias.unlink()

            path.parent.chmod(0o755)
            with self.assertRaises(ValueError):
                validate_existing_receipt(path, 123, 1)
            path.parent.chmod(0o700)

            dangling = Path(directory) / "dangling.json"
            dangling.symlink_to(Path(directory) / "missing")
            with self.assertRaises(ValueError):
                write_receipt(dangling, receipt)

            locked = Path(directory) / "locked.json"
            stale_lock = locked.with_suffix(".json.lock")
            stale_lock.write_text("stale", encoding="utf-8")
            stale_lock.chmod(0o600)
            write_receipt(locked, receipt)
            self.assertTrue(locked.exists())
            self.assertTrue(stale_lock.exists())

    def test_user_timer_is_least_privilege_and_credential_free(self) -> None:
        service = (
            ROOT / "deploy/systemd/user/noetic-dev-route-attestation.service"
        ).read_text(encoding="utf-8")
        timer = (
            ROOT / "deploy/systemd/user/noetic-dev-route-attestation.timer"
        ).read_text(encoding="utf-8")
        installer = (
            ROOT / "deploy/install-route-attestation-user.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("EnvironmentFile=%h/.config/noetic-dev/route-attestation.env", service)
        self.assertIn("--after-run-id ${NOETIC_ROUTE_AFTER_RUN_ID}", service)
        self.assertIn("TimeoutStartSec=30min", service)
        self.assertIn("ProtectSystem=strict", service)
        self.assertIn("ProtectHome=tmpfs", service)
        self.assertIn("BindReadOnlyPaths=%h/.config/gh", service)
        self.assertIn("NoNewPrivileges=true", service)
        self.assertIn("/usr/bin/python3 -I", service)
        self.assertIn("UnsetEnvironment=GH_TOKEN GITHUB_TOKEN GH_ENTERPRISE_TOKEN", service)
        self.assertIn("GH_HOST PYTHONPATH PYTHONHOME LD_PRELOAD", service)
        self.assertNotIn("GH_TOKEN=", service + installer)
        self.assertNotIn("GITHUB_TOKEN=", service + installer)
        self.assertIn("OnUnitActiveSec=10min", timer)
        self.assertIn("test \"$#\" -eq 1", installer)
        self.assertIn("''|0|0*|*[!0-9]*)", installer)
        self.assertIn("NOETIC_ROUTE_AFTER_RUN_ID=%s", installer)
        self.assertIn("env -i HOME=", installer)
        self.assertIn('--property=Linger --value)" = yes', installer)
        self.assertIn("systemctl --user enable --now noetic-dev-route-attestation.timer", installer)


if __name__ == "__main__":
    unittest.main()
