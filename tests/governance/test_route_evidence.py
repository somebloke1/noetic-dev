"""Tests for protected broker route evidence contracts."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

from route_evidence import (  # noqa: E402
    REQUIRED_PROTECTED_CHECKS, REQUIRED_PULL_REQUEST_PARAMETERS, REQUIRED_RULESET_RULES,
    STANDARD_MODELS, github_json, main, protected_checkout_matches, protected_ci_snapshot,
    validate_protected_provenance,
    validate_route_evidence,
)
from capture_protected_ci import main as capture_protected_ci_main  # noqa: E402

SOL, TERRA, LUNA = STANDARD_MODELS


def model_ref(model: str) -> dict[str, str]:
    return {
        "model_id": model,
        "endpoint_id": "local-litellm",
        "upstream_model_id": model,
        "interface_type": "openai-compatible",
        "base_url": "http://172.22.10.160:3333",
        "endpoint_path": "/v1/responses",
        "token_env": "LITELLM_API_KEY",
        "reasoning_effort": "high",
    }


def decision(model: str, remaining: list[str], number: int = 1) -> dict[str, object]:
    return {
        "availability": "verified",
        "decision_id": f"d-20260716-{number:06d}",
        "effective_complexity": "complex",
        "fable_eligible": False,
        "fallback_refs": [model_ref(item) for item in remaining[1:]],
        "fallbacks": remaining[1:],
        "genus": "Complex Code Review",
        "genus_code": "REVIEW-COMPLEX",
        "independent_approval_eligible": False,
        "model": model,
        "model_ref": model_ref(model),
        "rationale": ["protected broker route evidence fixture"],
        "routing_profile": "standard",
        "sophistication": "complex",
    }


def route_evidence(models: list[str] | None = None) -> dict[str, object]:
    candidates = [TERRA, SOL, LUNA]
    selected = models or [TERRA]
    attempts = []
    for index, model in enumerate(selected):
        remaining = [item for item in candidates if item not in selected[:index]]
        attempts.append({
            "decision": decision(model, remaining, index + 1),
            "invocation_count": 1,
            "outcome": "success" if index == len(selected) - 1 else "failure",
            "outcome_recorded": True,
            "reasoning_effort": "high",
        })
    return {
        "schema_version": "1",
        "component_sha": "f2b839b0cfc737c4c1f0a46d3d519d414529545c",
        "classification": {
            "task_kind": "review",
            "complexity": "complex",
            "blast_radius": "interface",
            "high_value": False,
            "awaited": True,
        },
        "attempts": attempts,
    }


def protection_records() -> tuple[dict, list, dict, dict]:
    run = {"created_at": "2026-07-17T20:10:00Z"}
    checks = copy.deepcopy(REQUIRED_PROTECTED_CHECKS)
    applied = [
        {"type": "deletion", "ruleset_id": 19122088},
        {"type": "non_fast_forward", "ruleset_id": 19122088},
        {
            "type": "pull_request", "ruleset_id": 19122088,
            "parameters": copy.deepcopy(REQUIRED_PULL_REQUEST_PARAMETERS),
        },
        {
            "type": "required_status_checks", "ruleset_id": 19122088,
            "parameters": {
                "strict_required_status_checks_policy": True,
                "do_not_enforce_on_create": False,
                "required_status_checks": checks,
            },
        },
    ]
    ruleset = {
        "id": 19122088,
        "name": "Protected dev governance",
        "target": "branch",
        "source_type": "Repository",
        "source": "somebloke1/noetic-dev",
        "enforcement": "active",
        "conditions": {"ref_name": {"exclude": [], "include": ["refs/heads/dev"]}},
        "rules": copy.deepcopy(REQUIRED_RULESET_RULES),
        "created_at": "2026-07-17T20:05:00Z",
        "updated_at": "2026-07-17T20:05:00Z",
        "bypass_actors": [],
        "current_user_can_bypass": "never",
    }
    snapshot = protected_ci_snapshot(123, run, applied, ruleset)
    assert snapshot is not None
    return run, applied, ruleset, snapshot


def provenance_records(
    head_sha: str, base_sha: str, pr_number: int = 55
) -> tuple[dict, dict, dict, dict, dict]:
    run = {
        "id": 123,
        "name": "Agent Review",
        "path": ".github/workflows/agent-review.yml",
        "workflow_id": 312422987,
        "run_attempt": 1,
        "event": "pull_request_target",
        "status": "completed",
        "conclusion": "success",
        "display_title": f"agent-review-{pr_number}-{head_sha}",
        "head_branch": "issue-route-canary",
        "head_sha": head_sha,
        "created_at": "2026-07-17T20:10:00Z",
        "repository": {"id": 1297462728, "full_name": "somebloke1/noetic-dev"},
        "head_repository": {"id": 1297462728, "full_name": "somebloke1/noetic-dev"},
        "pull_requests": [],
    }
    pull = {
        "number": pr_number,
        "state": "closed",
        "merged": True,
        "merge_commit_sha": "f" * 40,
        "merged_at": "2026-07-17T20:12:00Z",
        "created_at": "2026-07-17T20:00:00Z",
        "draft": False,
        "head": {
            "ref": "issue-route-canary",
            "sha": head_sha,
            "repo": {"id": 1297462728, "full_name": "somebloke1/noetic-dev"},
        },
        "base": {
            "ref": "dev",
            "sha": base_sha,
            "repo": {"id": 1297462728, "full_name": "somebloke1/noetic-dev"},
        },
    }
    merge_commit = {"sha": "f" * 40, "parents": [{"sha": base_sha}]}
    jobs = {
        "total_count": 1,
        "jobs": [{
            "id": 456,
            "run_id": 123,
            "run_attempt": 1,
            "workflow_name": f"agent-review-{pr_number}-{head_sha}",
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
        }],
    }
    artifacts = {
        "total_count": 1,
        "artifacts": [{
            "id": 789,
            "name": f"agent-review-{pr_number}-{head_sha}",
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
    return run, pull, merge_commit, jobs, artifacts


class TestRouteEvidence(unittest.TestCase):
    def test_github_queries_reject_duplicate_json_and_inherited_tokens(self) -> None:
        response = subprocess.CompletedProcess([], 0, b'{"id":1,"id":2}', b"")
        with mock.patch("route_evidence.subprocess.run", return_value=response) as execute:
            with self.assertRaises(ValueError):
                github_json("repos/somebloke1/noetic-dev")
        environment = execute.call_args.kwargs["env"]
        self.assertNotIn("GH_TOKEN", environment)
        self.assertNotIn("GITHUB_TOKEN", environment)
        self.assertNotIn("GH_HOST", environment)

    def test_valid_success_and_reroute_sequences(self) -> None:
        self.assertEqual(validate_route_evidence(route_evidence()), [])
        self.assertEqual(validate_route_evidence(route_evidence([TERRA, SOL])), [])

    def test_exhausted_route_can_end_in_terminal_failure(self) -> None:
        exhausted = route_evidence([TERRA, SOL, LUNA])
        exhausted["attempts"][-1]["outcome"] = "failure"
        self.assertEqual(validate_route_evidence(exhausted), [])

        partial = route_evidence([TERRA, SOL])
        partial["attempts"][-1]["outcome"] = "failure"
        self.assertTrue(validate_route_evidence(partial))

    def test_zero_invocation_rejection_can_precede_success(self) -> None:
        evidence = route_evidence([TERRA, SOL])
        evidence["attempts"][0] = {
            "decision_rejection": {
                "decision_id": "d-20260716-000001",
                "model": TERRA,
                "raw_decision_sha256": "a" * 64,
                "rejection_type": "ModelRoutingError",
            },
            "invocation_count": 0,
            "outcome": "failure",
            "outcome_recorded": True,
        }
        self.assertEqual(validate_route_evidence(evidence), [])

        tainted = copy.deepcopy(evidence)
        tainted["attempts"][0]["decision_rejection"]["decision_id"] += "\n"
        self.assertTrue(validate_route_evidence(tainted))

        tainted = copy.deepcopy(evidence)
        tainted["attempts"][0]["decision_rejection"]["raw_decision_sha256"] += "\n"
        self.assertTrue(validate_route_evidence(tainted))

    def test_terminal_rejections_must_exhaust_all_candidates(self) -> None:
        evidence = route_evidence([TERRA, SOL, LUNA])
        for index, model in enumerate([TERRA, SOL, LUNA]):
            evidence["attempts"][index] = {
                "decision_rejection": {
                    "decision_id": f"d-20260716-{index + 1:06d}",
                    "model": model,
                    "raw_decision_sha256": "a" * 64,
                    "rejection_type": "invalid external decision",
                },
                "invocation_count": 0,
                "outcome": "failure",
                "outcome_recorded": True,
            }
        self.assertEqual(validate_route_evidence(evidence), [])
        self.assertTrue(validate_route_evidence({**evidence, "attempts": evidence["attempts"][:2]}))

    def test_rejects_static_or_unknown_contract_evidence(self) -> None:
        self.assertTrue(validate_route_evidence({"model": TERRA}))
        self.assertTrue(validate_route_evidence(route_evidence(), "unknown"))

    def test_retained_evidence_cli_binds_candidate_sha(self) -> None:
        head_sha = "a" * 40
        protection_run, applied_rules, ruleset, protected_ci = protection_records()
        payload = {
            "repository": "somebloke1/noetic-dev", "pr_number": 55, "head_sha": head_sha,
            "base_sha": "b" * 40, "protected_ci": protected_ci,
            "route_evidence": route_evidence(),
        }
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "agent-review-result.json"
            evidence.write_text(json.dumps(payload), encoding="utf-8")
            run, pull, merge_commit, jobs, artifacts = provenance_records(head_sha, "b" * 40)
            run["created_at"] = protection_run["created_at"]
            responses = [
                subprocess.CompletedProcess([], 0, json.dumps(run).encode(), b""),
                subprocess.CompletedProcess([], 0, json.dumps(pull).encode(), b""),
                subprocess.CompletedProcess([], 0, json.dumps(merge_commit).encode(), b""),
                subprocess.CompletedProcess([], 0, json.dumps(jobs).encode(), b""),
                subprocess.CompletedProcess([], 0, json.dumps(artifacts).encode(), b""),
                subprocess.CompletedProcess([], 0, json.dumps(applied_rules).encode(), b""),
                subprocess.CompletedProcess([], 0, json.dumps(ruleset).encode(), b""),
            ]
            arguments = ["route_evidence.py", "--run-id", "123", "--pr-number", "55", "--head-sha", head_sha]
            with mock.patch.object(sys, "argv", arguments), mock.patch(
                "route_evidence.subprocess.run", side_effect=responses
            ), mock.patch("route_evidence.download_protected_evidence", return_value=evidence), mock.patch(
                "route_evidence.protected_checkout_matches", return_value=True
            ):
                self.assertEqual(main(), 0)
            run["conclusion"] = "failure"
            responses = [
                subprocess.CompletedProcess([], 0, json.dumps(run).encode(), b""),
                subprocess.CompletedProcess([], 0, json.dumps(pull).encode(), b""),
                subprocess.CompletedProcess([], 0, json.dumps(merge_commit).encode(), b""),
                subprocess.CompletedProcess([], 0, json.dumps(jobs).encode(), b""),
                subprocess.CompletedProcess([], 0, json.dumps(artifacts).encode(), b""),
                subprocess.CompletedProcess([], 0, json.dumps(applied_rules).encode(), b""),
                subprocess.CompletedProcess([], 0, json.dumps(ruleset).encode(), b""),
            ]
            with mock.patch.object(sys, "argv", arguments), mock.patch(
                "route_evidence.subprocess.run", side_effect=responses
            ), mock.patch("route_evidence.download_protected_evidence", return_value=evidence):
                self.assertNotEqual(main(), 0)

            payload["base_sha"] = head_sha
            evidence.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(sys, "argv", arguments), mock.patch(
                "route_evidence.subprocess.run"
            ) as run_api, mock.patch(
                "route_evidence.download_protected_evidence", return_value=evidence
            ):
                self.assertNotEqual(main(), 0)
                run_api.assert_not_called()

    def test_merged_run_uses_stable_pr_and_exact_job_artifact_metadata(self) -> None:
        head_sha = "a" * 40
        base_sha = "b" * 40
        run, applied, ruleset, protected_ci = protection_records()
        github_run, pull, merge_commit, jobs, artifacts = provenance_records(head_sha, base_sha)

        def validate(records: tuple[dict, dict, dict, dict, dict]) -> list[str]:
            source_run, source_pull, source_merge, source_jobs, source_artifacts = records
            responses = [
                source_run, source_pull, source_merge, source_jobs, source_artifacts,
                applied, ruleset,
            ]
            with mock.patch("route_evidence.github_json", side_effect=responses), mock.patch(
                "route_evidence.protected_checkout_matches", return_value=True
            ):
                return validate_protected_provenance(123, 55, head_sha, base_sha, protected_ci)

        self.assertEqual(validate((github_run, pull, merge_commit, jobs, artifacts)), [])
        base_job = copy.deepcopy(jobs)
        base_job["jobs"][0]["head_sha"] = base_sha
        self.assertEqual(validate((github_run, pull, merge_commit, base_job, artifacts)), [])
        base_artifact = copy.deepcopy(artifacts)
        base_artifact["artifacts"][0]["workflow_run"]["head_sha"] = base_sha
        self.assertEqual(validate((github_run, pull, merge_commit, jobs, base_artifact)), [])
        advanced_pull = copy.deepcopy(pull)
        advanced_pull["base"]["sha"] = "e" * 40
        self.assertEqual(validate((github_run, advanced_pull, merge_commit, jobs, artifacts)), [])
        mutations = []
        for target, path, value in [
            ("run", ("id",), 123.0),
            ("run", ("workflow_id",), 1),
            ("run", ("run_attempt",), True),
            ("pull", ("head", "sha"), "d" * 40),
            ("pull", ("state",), None),
            ("pull", ("merged_at",), "2026-07-17T20:09:00Z"),
            ("merge", ("parents", 0, "sha"), "e" * 40),
            ("jobs", ("total_count",), True),
            ("jobs", ("jobs", 0, "id"), 0),
            ("jobs", ("jobs", 0, "run_attempt"), 2),
            ("jobs", ("jobs", 0, "workflow_name"), "Agent Review"),
            ("jobs", ("jobs", 0, "labels"), ["self-hosted"]),
            ("jobs", ("jobs", 0, "steps"), jobs["jobs"][0]["steps"] + [{"name": "extra", "conclusion": "success"}]),
            ("artifacts", ("total_count",), True),
            ("artifacts", ("artifacts", 0, "id"), 789.0),
            ("artifacts", ("artifacts", 0, "digest"), "sha256:bad"),
            ("artifacts", ("artifacts", 0, "workflow_run", "id"), 999),
        ]:
            records = [
                copy.deepcopy(item)
                for item in (github_run, pull, merge_commit, jobs, artifacts)
            ]
            item = records[
                {"run": 0, "pull": 1, "merge": 2, "jobs": 3, "artifacts": 4}[target]
            ]
            for key in path[:-1]:
                item = item[key]
            item[path[-1]] = value
            mutations.append((target, path, tuple(records)))
        for target, path, records in mutations:
            with self.subTest(target=target, path=path):
                self.assertTrue(validate(records))

    def test_protected_ci_snapshot_rejects_mutable_or_bypassable_rulesets(self) -> None:
        run, applied, ruleset, snapshot = protection_records()
        self.assertEqual(protected_ci_snapshot(123, run, applied, ruleset), snapshot)
        for mutation in (
            "late", "equal-time", "naive-time", "bypass", "viewer-bypass", "missing-check",
            "deletion", "force-push", "merge-method", "full-rule-detail", "duplicate-full-rule",
        ):
            changed_ruleset = copy.deepcopy(ruleset)
            changed_applied = copy.deepcopy(applied)
            if mutation == "late":
                changed_ruleset["updated_at"] = "2026-07-17T20:11:00Z"
            elif mutation == "equal-time":
                changed_ruleset["updated_at"] = run["created_at"]
            elif mutation == "naive-time":
                changed_ruleset["updated_at"] = "2026-07-17T20:05:00"
            elif mutation == "bypass":
                changed_ruleset["bypass_actors"] = [{"actor_type": "User", "actor_id": 1}]
            elif mutation == "viewer-bypass":
                changed_ruleset["current_user_can_bypass"] = "always"
            elif mutation == "missing-check":
                changed_applied[3]["parameters"]["required_status_checks"].pop()
            elif mutation == "deletion":
                changed_applied.pop(0)
            elif mutation == "force-push":
                changed_applied.pop(1)
            elif mutation == "merge-method":
                changed_applied[2]["parameters"]["allowed_merge_methods"] = ["merge"]
            elif mutation == "full-rule-detail":
                changed_ruleset["rules"][2]["parameters"]["allowed_merge_methods"] = ["merge"]
            else:
                changed_ruleset["rules"].append({"type": "deletion"})
            with self.subTest(mutation=mutation):
                self.assertIsNone(protected_ci_snapshot(123, run, changed_applied, changed_ruleset))

        extra_ruleset = copy.deepcopy(applied)
        extra_ruleset.append({"type": "required_status_checks", "ruleset_id": 2, "parameters": {}})
        self.assertIsNone(protected_ci_snapshot(123, run, extra_ruleset, ruleset))
        confused_rules = copy.deepcopy(applied)
        confused_rules[0]["ruleset_id"] = True
        self.assertIsNone(protected_ci_snapshot(123, run, confused_rules, ruleset))
        confused_ruleset = copy.deepcopy(ruleset)
        confused_ruleset["rules"][2]["parameters"]["required_approving_review_count"] = False
        self.assertIsNone(protected_ci_snapshot(123, run, applied, confused_ruleset))

    def test_malformed_retained_ruleset_identity_fails_closed(self) -> None:
        with mock.patch("route_evidence.github_json") as api:
            errors = validate_protected_provenance(123, 55, "a" * 40, "b" * 40, {"ruleset": []})
        self.assertEqual(errors, ["retained protected-CI ruleset identity is invalid"])
        api.assert_not_called()

    def test_validator_checkout_must_be_the_clean_protected_base(self) -> None:
        base_sha = "b" * 40
        clean = [
            subprocess.CompletedProcess([], 0, f"{base_sha}\n".encode(), b""),
            subprocess.CompletedProcess([], 1, b"", b""),
            subprocess.CompletedProcess([], 0, b"H governance/protected-dev-ruleset.json\nH scripts/governance/route_evidence.py\n", b""),
            subprocess.CompletedProcess([], 0, b"", b""),
            subprocess.CompletedProcess([], 0, b"", b""),
            subprocess.CompletedProcess([], 0, b"", b""),
        ]
        with mock.patch("route_evidence.subprocess.run", side_effect=clean):
            self.assertTrue(protected_checkout_matches(base_sha))
        failures = [
            ("a" * 40, 1, 0, b""),
            (base_sha, 0, 0, b""),
            (base_sha, 1, 1, b""),
            (base_sha, 1, 0, b"?? scripts/governance/route_evidence.py\n"),
        ]
        tracked_paths = b"H governance/protected-dev-ruleset.json\nH scripts/governance/route_evidence.py\n"
        for revision, branch_status, tracked_status, status in failures:
            responses = [
                subprocess.CompletedProcess([], 0, f"{revision}\n".encode(), b""),
                subprocess.CompletedProcess([], branch_status, b"refs/heads/dev\n" if branch_status == 0 else b"", b""),
                subprocess.CompletedProcess([], tracked_status, tracked_paths if tracked_status == 0 else b"", b""),
                subprocess.CompletedProcess([], 0, status, b""),
                subprocess.CompletedProcess([], 0, b"", b""),
                subprocess.CompletedProcess([], 0, b"", b""),
            ]
            with self.subTest(
                revision=revision, branch_status=branch_status,
                tracked_status=tracked_status, status=status,
            ), mock.patch(
                "route_evidence.subprocess.run", side_effect=responses
            ):
                self.assertFalse(protected_checkout_matches(base_sha))
        for concealed in [
            b"S governance/protected-dev-ruleset.json\nH scripts/governance/route_evidence.py\n",
            b"H governance/protected-dev-ruleset.json\nh scripts/governance/route_evidence.py\n",
        ]:
            responses = [
                subprocess.CompletedProcess([], 0, f"{base_sha}\n".encode(), b""),
                subprocess.CompletedProcess([], 1, b"", b""),
                subprocess.CompletedProcess([], 0, concealed, b""),
                subprocess.CompletedProcess([], 0, b"", b""),
                subprocess.CompletedProcess([], 0, b"", b""),
                subprocess.CompletedProcess([], 0, b"", b""),
            ]
            with self.subTest(concealed=concealed), mock.patch(
                "route_evidence.subprocess.run", side_effect=responses
            ):
                self.assertFalse(protected_checkout_matches(base_sha))
        replacement = [
            subprocess.CompletedProcess([], 0, f"{base_sha}\n".encode(), b""),
            subprocess.CompletedProcess([], 1, b"", b""),
            subprocess.CompletedProcess([], 0, tracked_paths, b""),
            subprocess.CompletedProcess([], 0, b"", b""),
            subprocess.CompletedProcess([], 0, b"", b""),
            subprocess.CompletedProcess([], 0, f"refs/replace/{base_sha}\n".encode(), b""),
        ]
        with mock.patch("route_evidence.subprocess.run", side_effect=replacement):
            self.assertFalse(protected_checkout_matches(base_sha))
        ignored = clean.copy()
        ignored[4] = subprocess.CompletedProcess([], 0, b"scripts/governance/json.pyc\n", b"")
        with mock.patch("route_evidence.subprocess.run", side_effect=ignored):
            self.assertFalse(protected_checkout_matches(base_sha))

    def test_capture_adds_the_applicable_ruleset_to_retained_evidence(self) -> None:
        _, _, _, snapshot = protection_records()
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "agent-review-result.json"
            policy = Path(directory) / "protected-dev-ruleset.json"
            evidence.write_text(json.dumps({"repository": "somebloke1/noetic-dev"}), encoding="utf-8")
            policy.write_text(json.dumps(snapshot), encoding="utf-8")
            arguments = [
                "capture_protected_ci.py", "--evidence", str(evidence), "--policy", str(policy),
            ]
            with mock.patch.object(sys, "argv", arguments):
                self.assertEqual(capture_protected_ci_main(), 0)
            self.assertEqual(json.loads(evidence.read_text(encoding="utf-8"))["protected_ci"], snapshot)

    def test_capture_rejects_malformed_policy_without_rewriting_evidence(self) -> None:
        malformed = [
            None, True, 1, {}, "policy", {"schema_version": "1"},
            {"schema_version": "1", "ruleset": {}, "applied_rules": []},
        ]
        for policy_payload in malformed:
            with self.subTest(policy=policy_payload), tempfile.TemporaryDirectory() as directory:
                evidence = Path(directory) / "agent-review-result.json"
                policy = Path(directory) / "protected-dev-ruleset.json"
                original = json.dumps({"repository": "somebloke1/noetic-dev"})
                evidence.write_text(original, encoding="utf-8")
                policy.write_text(json.dumps(policy_payload), encoding="utf-8")
                arguments = [
                    "capture_protected_ci.py", "--evidence", str(evidence), "--policy", str(policy),
                ]
                with mock.patch.object(sys, "argv", arguments):
                    with self.assertRaises(SystemExit):
                        capture_protected_ci_main()
                self.assertEqual(evidence.read_text(encoding="utf-8"), original)

    def test_downloaded_artifact_is_the_only_evidence_source(self) -> None:
        from route_evidence import download_protected_evidence

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_file = io.BytesIO()
            with zipfile.ZipFile(archive_file, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("agent-review-result.json", "{}")
            archive_bytes = archive_file.getvalue()
            _, pull, merge_commit, _, artifacts = provenance_records("a" * 40, "b" * 40)
            artifact = artifacts["artifacts"][0]
            artifact["size_in_bytes"] = len(archive_bytes)
            artifact["digest"] = f"sha256:{hashlib.sha256(archive_bytes).hexdigest()}"

            def download(command, **_kwargs):
                if command[-1].endswith("/pulls/55"):
                    output = json.dumps(pull).encode()
                elif "/commits/" in command[-1]:
                    output = json.dumps(merge_commit).encode()
                elif command[-1].endswith("/artifacts"):
                    output = json.dumps(artifacts).encode()
                else:
                    output = archive_bytes
                return subprocess.CompletedProcess(command, 0, output, b"")

            with mock.patch("route_evidence.subprocess.run", side_effect=download):
                evidence = download_protected_evidence(123, 55, "a" * 40, root)
            self.assertEqual(evidence, root / "agent-review-result.json")
            self.assertEqual(evidence.read_text(encoding="utf-8"), "{}")

            artifact["workflow_run"]["head_sha"] = "b" * 40
            with tempfile.TemporaryDirectory() as base_directory, mock.patch(
                "route_evidence.subprocess.run", side_effect=download
            ):
                base_evidence = download_protected_evidence(
                    123, 55, "a" * 40, Path(base_directory)
                )
                self.assertEqual(base_evidence.read_text(encoding="utf-8"), "{}")

            artifact["digest"] = f"sha256:{'0' * 64}"
            with mock.patch("route_evidence.subprocess.run", side_effect=download):
                with self.assertRaisesRegex(ValueError, "digest does not match"):
                    download_protected_evidence(123, 55, "a" * 40, root / "unused")

    def test_route_mutations_fail_closed(self) -> None:
        mutations = []
        for path, value in [
            (("classification", "high_value"), True),
            (("component_sha",), "a" * 39),
            (("component_sha",), "a" * 40),
            (("attempts", 0, "invocation_count"), 0),
            (("attempts", 0, "outcome_recorded"), False),
            (("attempts", 0, "reasoning_effort"), "low"),
            (("attempts", 0, "decision", "genus"), "Other"),
            (("attempts", 0, "decision", "model"), SOL),
            (("attempts", 0, "decision", "fallbacks"), [LUNA, SOL]),
            (("attempts", 0, "decision", "model_ref", "base_url"), "https://provider.example"),
            (("attempts", 0, "decision", "model_ref", "endpoint_path"), "/v1/chat/completions"),
            (("attempts", 0, "decision", "rationale"), [""]),
        ]:
            mutated = copy.deepcopy(route_evidence())
            target = mutated
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            mutations.append(mutated)
        unknown = copy.deepcopy(route_evidence())
        unknown["attempts"][0]["decision"]["model_ref"]["api_key"] = "forbidden"
        mutations.append(unknown)
        for evidence in mutations:
            with self.subTest(evidence=evidence):
                self.assertTrue(validate_route_evidence(evidence))

    def test_decision_ids_are_unique_and_ascii_shaped(self) -> None:
        reused = route_evidence([TERRA, SOL])
        reused["attempts"][1]["decision"]["decision_id"] = reused["attempts"][0]["decision"]["decision_id"]
        self.assertTrue(validate_route_evidence(reused))
        for bad_id in ["d-20260716-000001\n", "d-20260716-00001", "d-٢٠٢٦٠٧١٦-٠٠٠٠٠١"]:
            mutated = route_evidence()
            mutated["attempts"][0]["decision"]["decision_id"] = bad_id
            with self.subTest(bad_id=bad_id):
                self.assertTrue(validate_route_evidence(mutated))


if __name__ == "__main__":
    unittest.main()
