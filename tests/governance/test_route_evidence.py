"""Tests for protected broker route evidence contracts."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

from route_evidence import (  # noqa: E402
    REQUIRED_PROTECTED_CHECKS, REQUIRED_PULL_REQUEST_PARAMETERS, REQUIRED_RULESET_RULES,
    STANDARD_MODELS, main, protected_ci_snapshot, validate_protected_provenance,
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


class TestRouteEvidence(unittest.TestCase):
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
            run = {
                "id": 123, "name": "Agent Review", "path": ".github/workflows/agent-review.yml",
                "event": "pull_request_target", "status": "completed", "conclusion": "success",
                "head_sha": head_sha, "repository": {"full_name": "somebloke1/noetic-dev"},
                "created_at": protection_run["created_at"],
                "pull_requests": [{
                    "number": 55,
                    "head": {"sha": head_sha, "repo": {"url": "https://api.github.com/repos/somebloke1/noetic-dev"}},
                    "base": {
                        "ref": "dev", "sha": "b" * 40,
                        "repo": {"url": "https://api.github.com/repos/somebloke1/noetic-dev"},
                    },
                }],
            }
            artifacts = {"artifacts": [{"name": f"agent-review-55-{head_sha}", "expired": False}]}
            responses = [
                subprocess.CompletedProcess([], 0, json.dumps(run).encode(), b""),
                subprocess.CompletedProcess([], 0, json.dumps(artifacts).encode(), b""),
                subprocess.CompletedProcess([], 0, json.dumps(applied_rules).encode(), b""),
                subprocess.CompletedProcess([], 0, json.dumps(ruleset).encode(), b""),
            ]
            arguments = ["route_evidence.py", "--run-id", "123", "--pr-number", "55", "--head-sha", head_sha]
            with mock.patch.object(sys, "argv", arguments), mock.patch(
                "route_evidence.subprocess.run", side_effect=responses
            ), mock.patch("route_evidence.download_protected_evidence", return_value=evidence):
                self.assertEqual(main(), 0)
            run["conclusion"] = "failure"
            responses = [
                subprocess.CompletedProcess([], 0, json.dumps(run).encode(), b""),
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

    def test_malformed_retained_ruleset_identity_fails_closed(self) -> None:
        with mock.patch("route_evidence.github_json") as api:
            errors = validate_protected_provenance(123, 55, "a" * 40, "b" * 40, {"ruleset": []})
        self.assertEqual(errors, ["retained protected-CI ruleset identity is invalid"])
        api.assert_not_called()

    def test_capture_adds_the_applicable_ruleset_to_retained_evidence(self) -> None:
        run, applied, ruleset, snapshot = protection_records()
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "agent-review-result.json"
            evidence.write_text(json.dumps({"repository": "somebloke1/noetic-dev"}), encoding="utf-8")
            arguments = [
                "capture_protected_ci.py", "--run-id", "123", "--evidence", str(evidence),
            ]
            with mock.patch.object(sys, "argv", arguments), mock.patch(
                "capture_protected_ci.github_json", side_effect=[run, applied, ruleset]
            ):
                self.assertEqual(capture_protected_ci_main(), 0)
            self.assertEqual(json.loads(evidence.read_text(encoding="utf-8"))["protected_ci"], snapshot)

    def test_capture_rejects_malformed_applied_rules_without_rewriting_evidence(self) -> None:
        _, valid_rules, _, _ = protection_records()
        malformed = [None, True, 1, {}, "rule"]
        responses = malformed + [valid_rules + [item] for item in malformed]
        for response in responses:
            with self.subTest(response=response), tempfile.TemporaryDirectory() as directory:
                evidence = Path(directory) / "agent-review-result.json"
                original = json.dumps({"repository": "somebloke1/noetic-dev"})
                evidence.write_text(original, encoding="utf-8")
                arguments = [
                    "capture_protected_ci.py", "--run-id", "123", "--evidence", str(evidence),
                ]
                with mock.patch.object(sys, "argv", arguments), mock.patch(
                    "capture_protected_ci.github_json", side_effect=[{}, response]
                ):
                    with self.assertRaises(SystemExit):
                        capture_protected_ci_main()
                self.assertEqual(evidence.read_text(encoding="utf-8"), original)

    def test_capture_rejects_ignored_or_multiple_applicable_rulesets(self) -> None:
        _, valid_rules, _, _ = protection_records()
        invalid_responses = [
            valid_rules + [{"type": "unknown", "ruleset_id": 19122088}],
            valid_rules + [{"type": "unknown", "ruleset_id": 2}],
            valid_rules + [{"type": "deletion", "ruleset_id": 2}],
        ]
        for response in invalid_responses:
            with self.subTest(response=response), tempfile.TemporaryDirectory() as directory:
                evidence = Path(directory) / "agent-review-result.json"
                original = json.dumps({"repository": "somebloke1/noetic-dev"})
                evidence.write_text(original, encoding="utf-8")
                arguments = [
                    "capture_protected_ci.py", "--run-id", "123", "--evidence", str(evidence),
                ]
                with mock.patch.object(sys, "argv", arguments), mock.patch(
                    "capture_protected_ci.github_json", side_effect=[{}, response]
                ):
                    with self.assertRaises(SystemExit):
                        capture_protected_ci_main()
                self.assertEqual(evidence.read_text(encoding="utf-8"), original)

    def test_downloaded_artifact_is_the_only_evidence_source(self) -> None:
        from route_evidence import download_protected_evidence

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def download(command, **_kwargs):
                destination = Path(command[command.index("--dir") + 1])
                (destination / "agent-review-result.json").write_text("{}", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, b"", b"")

            with mock.patch("route_evidence.subprocess.run", side_effect=download):
                evidence = download_protected_evidence(123, 55, "a" * 40, root)
            self.assertEqual(evidence, root / "agent-review-result.json")

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
