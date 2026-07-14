"""Tests for the fail-closed delivery gate."""

from __future__ import annotations

import copy
import hashlib
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

from check_delivery_gate import check_bootstrap_blocked, check_delivery, check_pinning  # noqa: E402
from hash_tree import canonical_json_sha256, manifest_digest_excluding_own  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[2]


def load_fixture(name: str):
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def advisory_external():
    return load_fixture("advisory_external_evidence.json")


class TestDeliveryGatePositive(unittest.TestCase):
    def test_self_consistent_external_evidence_remains_advisory(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        passed, errors, gate_type = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertEqual(gate_type, "merge")
        joined = "\n".join(errors)
        self.assertIn("caller-supplied external evidence is advisory only", joined)
        self.assertIn("credential_broker_established", joined)
        self.assertNotIn("canonical manifest digest mismatch", joined)
        self.assertNotIn("retained execution prompt", joined)
        self.assertNotIn("retained final assistant text", joined)
        self.assertNotIn("retained event stream", joined)

    def test_github_api_mode_cannot_establish_review_authority(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("signed artifact attestation is required", "\n".join(errors))

    def test_valid_advisory_is_blocked_without_external_evidence(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        passed, errors, gate_type = check_delivery(manifest)
        self.assertFalse(passed)
        self.assertEqual(gate_type, "merge")
        self.assertIn("authoritative trusted runner", " ".join(errors).lower())

    def test_publication_remains_blocked_by_bootstrap_freeze(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        passed, errors, gate_type = check_delivery(manifest, external_evidence=advisory_external(), phase="publication")
        self.assertFalse(passed)
        self.assertEqual(gate_type, "publication")
        self.assertIn("existing-work freeze", "\n".join(errors))

    def test_multigeneration_history_is_valid_except_external_authority(self):
        manifest = load_fixture("valid_multigeneration_advisory_manifest.json")
        passed, errors, gate_type = check_delivery(manifest)
        self.assertFalse(passed)
        self.assertEqual(gate_type, "merge")
        joined = "\n".join(errors)
        self.assertIn("authoritative trusted runner", joined)
        self.assertNotIn("stale candidate", joined)
        self.assertNotIn("stale base", joined)
        self.assertNotIn("candidate_tree_oid mismatch", joined)

    def test_bootstrap_blocked_check_passes_while_dependencies_unresolved(self):
        passed, errors = check_bootstrap_blocked()
        self.assertTrue(passed, errors)

    def test_qa_retained_prompt_and_event_stream_are_recomputed(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        mutations = [
            ("prompt_text", "forged prompt", "execution prompt hash"),
            ("final_assistant_text", "forged answer", "final assistant hash"),
            (
                "qa_event_log",
                '{"type":"agent_end","willRetry":false,"messages":[]}\n',
                "event stream",
            ),
        ]
        for field, value, expected in mutations:
            with self.subTest(field=field):
                changed = copy.deepcopy(manifest)
                actual = changed["qa"]["records"][0]["protected_execution_record"][
                    "actual_invocation"
                ]
                actual[field] = value
                _passed, errors, _gate = check_delivery(changed)
                self.assertIn(expected, "\n".join(errors))

    def test_qa_retained_event_stream_rejects_unknown_assistant_parts(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        actual = qa["protected_execution_record"]["actual_invocation"]
        final_message = json.loads(actual["qa_event_log"].splitlines()[1])["message"]
        tool_call = {
            "type": "toolCall",
            "id": "call-qa-forgery-1",
            "name": "write",
            "arguments": {"path": "/tmp/forbidden", "content": "forged"},
        }
        tool_message = copy.deepcopy(final_message)
        tool_message["content"] = [tool_call]
        tool_message["stopReason"] = "toolUse"
        events = [
            {"type": "agent_start"},
            {"type": "turn_start"},
            {"type": "message_end", "message": tool_message},
            {
                "type": "tool_execution_start",
                "toolCallId": tool_call["id"],
                "toolName": tool_call["name"],
                "args": tool_call["arguments"],
            },
            {
                "type": "tool_execution_end",
                "toolCallId": tool_call["id"],
                "toolName": tool_call["name"],
                "result": {"content": [{"type": "text", "text": "written"}]},
                "isError": False,
            },
            {"type": "turn_end", "message": tool_message},
            {"type": "turn_start"},
            {"type": "message_end", "message": final_message},
            {"type": "turn_end", "message": final_message},
            {
                "type": "agent_end",
                "messages": [tool_message, final_message],
                "willRetry": False,
            },
        ]
        event_log = "".join(
            json.dumps(event, ensure_ascii=True, separators=(",", ":")) + "\n"
            for event in events
        )
        event_hash = hashlib.sha256(event_log.encode("utf-8")).hexdigest()
        actual["qa_event_log"] = event_log
        actual["qa_event_log_sha256"] = event_hash
        actual["stdout_sha256"] = event_hash
        qa["event_log_hash"] = event_hash

        _passed, errors, _gate = check_delivery(manifest)

        self.assertIn("forbidden tool event", "\n".join(errors))

    def test_qa_retained_event_stream_does_not_expose_parser_input(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        actual = qa["protected_execution_record"]["actual_invocation"]
        sentinel = "::error::attacker-controlled"
        event_log = (
            '{"type":"agent_start","\\n' + sentinel + '":1,"\\n' + sentinel + '":2}\n'
        )
        event_hash = hashlib.sha256(event_log.encode("utf-8")).hexdigest()
        actual["qa_event_log"] = event_log
        actual["qa_event_log_sha256"] = event_hash
        actual["stdout_sha256"] = event_hash
        qa["event_log_hash"] = event_hash

        _passed, errors, _gate = check_delivery(manifest)
        joined = "\n".join(errors)

        self.assertIn("malformed or inconsistent event data", joined)
        self.assertNotIn(sentinel, joined)

    def test_qa_retained_event_stream_normalizes_unexpected_parser_errors(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        with mock.patch(
            "check_delivery_gate.parse_pi_jsonl_final_assistant",
            side_effect=RecursionError("attacker-controlled recursion detail"),
        ):
            _passed, errors, _gate = check_delivery(manifest)
        joined = "\n".join(errors)

        self.assertIn("malformed or inconsistent event data", joined)
        self.assertNotIn("attacker-controlled recursion detail", joined)


class TestDeliveryGateNegativeFixtures(unittest.TestCase):
    CASES = {
        "negative_validator_as_test_manifest.json": "validate_repo.py cannot be reported as a test",
        "negative_self_qa_manifest.json": "self-QA rejected",
        "negative_missing_qa_manifest.json": "cardinality mismatch",
        "negative_stale_qa_manifest.json": "candidate_sha",
        "negative_wrong_sha_manifest.json": "candidate SHA must equal PR head SHA",
        "negative_wip_pr_manifest.json": "WIP prefix",
        "negative_draft_pr_manifest.json": "PR is a draft",
        "negative_stacked_pr_manifest.json": "stacked PR",
        "negative_blocked_issue_manifest.json": "prevents closure",
        "negative_mutable_action_manifest.json": "workflow.pinning",
        "negative_branch_publication_manifest.json": "branch-name publication forbidden",
        "negative_unsupported_model_manifest.json": "unsupported model profile",
        "negative_two_qas_one_pass_manifest.json": "multiple QA",
        "negative_missing_probe_manifest.json": "missing protected READY probe",
        "negative_probe_model_mismatch_manifest.json": "schema_version=2",
        "negative_qa_base_mismatch_manifest.json": "base_sha",
        "negative_execution_candidate_mismatch_manifest.json": "candidate_sha",
        "negative_execution_record_hash_mismatch_manifest.json": "execution record hash mismatch",
        "negative_probe_event_reused_manifest.json": "probe event stream reused",
        "negative_qa_record_writable_manifest.json": "writable by QA/model",
        "negative_record_only_qa_manifest.json": "record-only",
    }

    def test_negative_fixtures_fail_for_named_reason(self):
        for fixture_name, expected in self.CASES.items():
            with self.subTest(fixture=fixture_name):
                manifest = load_fixture(fixture_name)
                passed, errors, _gate_type = check_delivery(manifest, external_evidence=advisory_external())
                self.assertFalse(passed, f"{fixture_name} unexpectedly passed")
                joined = "\n".join(errors)
                self.assertIn(expected, joined, f"{fixture_name} errors were: {errors}")


class TestExternalEvidenceFailures(unittest.TestCase):
    def test_manifest_only_trusted_runner_is_rejected(self):
        result = subprocess.run(
            [sys.executable, "scripts/governance/check_evidence_manifest.py", str(FIXTURES_DIR / "negative_manifest_only_authoritative_manifest.json")],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manifest-only authority claim", result.stderr)

    def test_external_artifact_digest_mismatch_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["artifact"]["digest"] = "sha256:" + "8" * 64
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("artifact digest mismatch", "\n".join(errors))

    def test_external_policy_hash_mismatch_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["policy_file_hashes"][manifest["policy"]["generator_path"]] = "0" * 64
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("policy generator_sha256", "\n".join(errors))

    def test_author_approval_rejected_from_external_evidence(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        author = manifest["pull_request"]["author"]
        external["approvals"][0]["reviewer"] = author
        external["approvals"][0]["agent_id"] = author
        external["approvals"][0]["identity_binding"]["subject"] = author
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("PR author", "\n".join(errors))

    def test_stale_approval_rejected_from_external_evidence(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["submitted_at"] = "2026-07-11T11:59:00+00:00"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("predates candidate", "\n".join(errors))

    def test_static_profile_without_route_evidence_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0].pop("route_evidence")
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("route evidence", "\n".join(errors))

    def test_low_reasoning_approval_rejected_from_external_evidence(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["route_evidence"]["attempts"][0]["reasoning_effort"] = "low"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("did not enact high reasoning", "\n".join(errors))

    def test_terra_cannot_be_final_independent_approval_model(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        route = external["approvals"][0]["route_evidence"]
        fable_attempt = route["attempts"][0]
        fable_attempt["outcome"] = "failure"
        fable_decision = fable_attempt["decision"]
        terra_decision = copy.deepcopy(fable_decision)
        terra_decision["decision_id"] = "d-20260713-400002"
        terra_decision["model"] = fable_decision["fallbacks"][0]
        terra_decision["model_ref"] = copy.deepcopy(fable_decision["fallback_refs"][0])
        terra_decision["fallbacks"] = fable_decision["fallbacks"][1:]
        terra_decision["fallback_refs"] = copy.deepcopy(fable_decision["fallback_refs"][1:])
        route["attempts"].append({
            "decision": terra_decision,
            "outcome": "success",
            "outcome_recorded": True,
            "reasoning_effort": "high",
        })
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("successful model must be Fable or Sol", "\n".join(errors))

    def test_reviewer_alias_is_rejected_from_external_evidence(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["reviewer"] = "alias-for-same-agent"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("not bound to protected agent_id", "\n".join(errors))

    def test_reviewer_role_run_reuse_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["role_run_id"] = manifest["passes"]["pass_records"][0]["role_run_id"]
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("reused implementation role_run_id", "\n".join(errors))

    def test_unverified_identity_binding_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["identity_binding"]["verified"] = False
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("lacks verified protected-runner identity binding", "\n".join(errors))

    def test_incomplete_transition_path_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        manifest["state_transitions"] = manifest["state_transitions"][-2:]
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("required state_transition missing", "\n".join(errors))

    def test_discontinuous_transition_path_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        manifest["state_transitions"].pop(1)
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("state_transition path is discontinuous", "\n".join(errors))

    def test_equal_transition_timestamps_are_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        same = manifest["state_transitions"][0]["timestamp"]
        for transition in manifest["state_transitions"]:
            transition["timestamp"] = same
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("timestamp did not advance", "\n".join(errors))

    def test_blocked_terminal_state_is_not_merge_eligible(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        last_time = manifest["state_transitions"][-1]["timestamp"]
        manifest["state_transitions"].append({
            "from": manifest["state_transitions"][-1]["to"],
            "to": "BLOCKED",
            "authority": "orchestrator",
            "timestamp": last_time.replace("+00:00", ".999999+00:00"),
        })
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("is not eligible for pre-merge", "\n".join(errors))

    def test_coordinated_alias_without_canonical_principal_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        approval = external["approvals"][0]
        approval["reviewer"] = "fresh-coordinated-alias"
        approval["agent_id"] = "fresh-coordinated-alias"
        approval["identity_binding"]["subject"] = "fresh-coordinated-alias"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("no protected canonical principal", "\n".join(errors))

    def test_duplicate_reviewer_role_run_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"].append(copy.deepcopy(external["approvals"][0]))
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("duplicated reviewer role_run_id", "\n".join(errors))

    def test_reviewer_alias_bound_to_implementation_principal_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        reviewer = next(item for item in external["agent_identities"] if item["agent_id"] == "agent-reviewer-fable")
        reviewer["principal_id"] = "principal-implementer"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("protected canonical principal is assigned to multiple aliases", "\n".join(errors))

    def test_reviewer_alias_bound_to_author_principal_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        reviewer = next(item for item in external["agent_identities"] if item["agent_id"] == "agent-reviewer-fable")
        reviewer["principal_id"] = "principal-author"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("protected canonical principal is assigned to multiple aliases", "\n".join(errors))

    def test_duplicate_implementation_role_run_is_rejected(self):
        manifest = load_fixture("valid_multigeneration_advisory_manifest.json")
        records = manifest["passes"]["pass_records"]
        records[1]["role_run_id"] = records[0]["role_run_id"]
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("implementation/remediation role_run_id must be unique", "\n".join(errors))

    def test_duplicate_qa_role_run_is_rejected(self):
        manifest = load_fixture("valid_multigeneration_advisory_manifest.json")
        records = manifest["qa"]["records"]
        records[1]["role_run_id"] = records[0]["role_run_id"]
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("QA role_run_id must be unique", "\n".join(errors))

    def test_review_evidence_digest_mismatch_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["reasoning_level"] = "xhigh"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("review identity/approval evidence digest mismatch", "\n".join(errors))

    def test_naive_approval_timestamp_returns_controlled_failure(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["submitted_at"] = "2026-07-11T12:40:00"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("invalid timestamp", "\n".join(errors))

    def test_wrong_sha_approval_after_candidate_pin_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["approvals"][0]["commit_sha"] = "f" * 40
        external["approvals"][0]["submitted_at"] = "2026-07-11T12:40:00+00:00"
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("wrong SHA", "\n".join(errors))

    def test_policy_ref_must_be_protected_full_sha_and_separate(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["protected_ref"]["protected"] = False
        external["checkouts"]["candidate_path"] = external["checkouts"]["policy_path"]
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        joined = "\n".join(errors)
        self.assertIn("policy ref is not independently protected", joined)
        self.assertIn("candidate checkout reused as policy checkout", joined)

    def test_candidate_controlled_or_short_policy_sha_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        manifest["policy"]["sha"] = manifest["repo"]["candidate_sha"]
        external["workflow"]["sha"] = manifest["policy"]["sha"]
        external["protected_ref"]["sha"] = manifest["policy"]["sha"]
        external["checkouts"]["policy_sha"] = manifest["policy"]["sha"]
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("candidate checkout reused as protected policy checkout", "\n".join(errors))

        manifest["policy"]["sha"] = "a" * 8
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("policy SHA must be full", "\n".join(errors))

    def test_manifest_generated_by_candidate_modifiable_code_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        external = advisory_external()
        external["generator"]["from_policy_checkout"] = False
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("candidate-modifiable code", "\n".join(errors))


class TestPublicationBindingFailures(unittest.TestCase):
    def _publication_candidate(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        publication_sha = "f" * 40
        manifest["publication"]["merge_result_sha"] = publication_sha
        manifest["publication"]["publication_sha"] = publication_sha
        for command in manifest["commands"]:
            if command.get("phase") == "post_merge":
                command["commit_sha"] = publication_sha
        external = advisory_external()
        external["artifact"]["manifest_sha256"] = manifest_digest_excluding_own(manifest)
        external["post_merge"] = {
            "event": "push",
            "ref": "refs/heads/main",
            "sha": publication_sha,
            "merge_result_sha": publication_sha,
            "merge_method": "squash",
            "main_contains_sha": True,
        }
        return manifest, external

    def test_premerge_postmerge_claim_cannot_satisfy_publication(self):
        manifest, external = self._publication_candidate()
        external["post_merge"]["event"] = "pull_request"
        passed, errors, gate_type = check_delivery(manifest, external_evidence=external, phase="publication")
        self.assertFalse(passed)
        self.assertEqual(gate_type, "publication")
        self.assertIn("push to refs/heads/main", "\n".join(errors))

    def test_non_main_publication_sha_rejected(self):
        manifest, external = self._publication_candidate()
        external["post_merge"]["ref"] = "refs/heads/feature"
        passed, errors, _ = check_delivery(manifest, external_evidence=external, phase="publication")
        self.assertFalse(passed)
        self.assertIn("refs/heads/main", "\n".join(errors))


class TestQaBindingFailures(unittest.TestCase):
    def _first_qa_with_rehashed_records(self, manifest):
        qa = manifest["qa"]["records"][0]
        qa["protected_execution_record_sha256"] = canonical_json_sha256(qa["protected_execution_record"])
        qa["protected_probe_record_sha256"] = canonical_json_sha256(qa["protected_probe_record"])
        return qa

    def test_execution_route_must_match_protected_qa_contract(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        actual = qa["protected_execution_record"]["actual_invocation"]
        actual["route_evidence"]["classification"]["high_value"] = True
        self._first_qa_with_rehashed_records(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("route classification", "\n".join(errors))

    def test_legacy_static_only_qa_evidence_is_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        qa["protected_execution_record"]["actual_invocation"].pop("route_evidence")
        qa["protected_probe_record"].pop("route_evidence")
        self._first_qa_with_rehashed_records(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("route_evidence", "\n".join(errors))

    def test_invoked_model_reference_must_match_final_route(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        actual = qa["protected_execution_record"]["actual_invocation"]
        actual["invoked_model_ref"]["model_id"] = "codex/gpt-5.6-sol"
        self._first_qa_with_rehashed_records(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("invoked_model_ref does not match", "\n".join(errors))

    def test_execution_argv_hash_and_exact_invocation_contract_are_recomputed(self):
        mutations = [
            ("hash", lambda actual: actual.__setitem__("argv_sha256", "0" * 64), "argv SHA256"),
            (
                "model",
                lambda actual: actual["argv"].__setitem__(actual["argv"].index("--model") + 1, "local-litellm/forged"),
                "argv does not bind",
            ),
            (
                "tools",
                lambda actual: actual["argv"].__setitem__(actual["argv"].index("--no-tools"), "--no-builtin-tools"),
                "argv does not bind",
            ),
            (
                "prompt",
                lambda actual: actual["argv"].__setitem__(-1, "@"),
                "argv does not bind",
            ),
            (
                "config",
                lambda actual: actual.__setitem__("model_config_sha256", "1" * 64),
                "model config hash",
            ),
        ]
        for label, mutate, expected in mutations:
            manifest = load_fixture("valid_advisory_manifest.json")
            qa = manifest["qa"]["records"][0]
            actual = qa["protected_execution_record"]["actual_invocation"]
            mutate(actual)
            if label not in {"hash", "config"}:
                actual["argv_sha256"] = canonical_json_sha256(actual["argv"])
            self._first_qa_with_rehashed_records(manifest)
            with self.subTest(label=label):
                passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
                self.assertFalse(passed)
                self.assertIn(expected, "\n".join(errors))

    def test_probe_final_text_hash_is_bound_to_ready_response(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        qa["protected_probe_record"]["final_assistant_text_sha256"] = "0" * 64
        self._first_qa_with_rehashed_records(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("final assistant hash", "\n".join(errors))

    def test_probe_and_execution_require_same_fresh_authority_worker(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        qa["protected_probe_record"]["authority_worker_pid"] += 1
        self._first_qa_with_rehashed_records(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("share one fresh authority worker", "\n".join(errors))

    def test_inner_execution_isolation_must_match_protected_outer_proof(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        qa["protected_execution_record"]["actual_invocation"]["isolation"]["host_home_mounted"] = True
        self._first_qa_with_rehashed_records(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        joined = "\n".join(errors)
        self.assertIn("execution isolation host_home_mounted must be False", joined)
        self.assertIn("inner/outer isolation mismatch", joined)

    def test_empty_probe_nonce_and_event_hash_are_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        probe = qa["protected_probe_record"]
        probe["nonce"] = ""
        probe["expected_response"] = ""
        probe["observed_response"] = ""
        probe["probe_event_log_sha256"] = ""
        self._first_qa_with_rehashed_records(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        joined = "\n".join(errors)
        self.assertIn("probe nonce must be 16", joined)
        self.assertIn("probe event stream hash is missing or invalid", joined)

    def test_probe_and_execution_must_not_reuse_route_decisions(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        actual = qa["protected_execution_record"]["actual_invocation"]
        probe = qa["protected_probe_record"]
        probe["route_evidence"] = copy.deepcopy(actual["route_evidence"])
        probe["invoked_model_ref"] = copy.deepcopy(actual["invoked_model_ref"])
        self._first_qa_with_rehashed_records(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("reused a route decision_id", "\n".join(errors))

    def test_policy_binds_pi_probe_and_execution_as_separate_operations(self):
        policy = json.loads((REPO_ROOT / "config" / "model-policy.json").read_text())
        self.assertEqual(policy["execution_contracts"]["authoritative_qa_pi"], {
            "operations": ["readiness_probe", "execution"],
            "decision_scope": "per_operation",
            "maximum_invocations_per_decision": 1,
            "report_outcome_scope": "per_operation",
        })

    def test_pi_attempt_accounting_rejects_duplicate_invocation(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        actual = qa["protected_execution_record"]["actual_invocation"]
        actual["attempt_accounting"][0]["invocation_count"] = 2
        self._first_qa_with_rehashed_records(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("exceeded one invocation per decision", "\n".join(errors))

    def test_pi_operation_contract_rejects_boolean_integer_confusion(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        actual = qa["protected_execution_record"]["actual_invocation"]
        probe = qa["protected_probe_record"]
        actual["operation_contract"]["maximum_invocations_per_decision"] = True
        probe["operation_contract"]["maximum_invocations_per_decision"] = True
        self._first_qa_with_rehashed_records(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        joined = "\n".join(errors)
        self.assertIn("does not bind the authoritative QA Pi execution contract", joined)
        self.assertIn("expected type integer, got boolean", joined)

    def test_probe_and_execution_timestamps_must_be_valid_and_ordered(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        probe = qa["protected_probe_record"]
        actual = qa["protected_execution_record"]["actual_invocation"]
        probe["started_at"] = "not-a-time"
        actual["finished_at"] = "2026-07-11T12:06:00+00:00"
        self._first_qa_with_rehashed_records(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        joined = "\n".join(errors)
        self.assertIn("probe timestamps are invalid", joined)
        self.assertIn("execution must finish after it starts", joined)

    def test_any_tool_in_authoritative_qa_record_rejected_until_broker_exists(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        qa["protected_execution_record"]["actual_invocation"]["tools"] = ["read"]
        qa["protected_probe_record"]["tools"] = ["read"]
        self._first_qa_with_rehashed_records(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=advisory_external())
        self.assertFalse(passed)
        self.assertIn("must use no tools until a credential broker exists", "\n".join(errors))

    def test_failed_or_non_ready_probe_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        probe = qa["protected_probe_record"]
        probe["observed_response"] = "not ready"
        probe["exit_code"] = 1
        self._first_qa_with_rehashed_records(manifest)
        external = advisory_external()
        external["artifact"]["manifest_sha256"] = manifest_digest_excluding_own(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        joined = "\n".join(errors)
        self.assertIn("READY nonce", joined)
        self.assertIn("probe exit code", joined)

    def test_probe_after_qa_start_is_stale(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        qa["protected_probe_record"]["finished_at"] = "2026-07-11T12:08:00+00:00"
        self._first_qa_with_rehashed_records(manifest)
        external = advisory_external()
        external["artifact"]["manifest_sha256"] = manifest_digest_excluding_own(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("probe finished after QA started", "\n".join(errors))

    def test_probe_candidate_and_pi_version_must_match_execution(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        probe = qa["protected_probe_record"]
        probe["candidate_sha"] = "f" * 40
        probe["pi_version"] = "pi 9.9.9"
        self._first_qa_with_rehashed_records(manifest)
        external = advisory_external()
        external["artifact"]["manifest_sha256"] = manifest_digest_excluding_own(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        joined = "\n".join(errors)
        self.assertIn("probe/execution mismatch for pi_version", joined)
        self.assertIn("probe candidate_sha mismatch", joined)

    def test_qa_event_log_hash_must_match_protected_execution_record(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        qa["event_log_hash"] = "9" * 64
        external = advisory_external()
        external["artifact"]["manifest_sha256"] = manifest_digest_excluding_own(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("event_log_hash does not match", "\n".join(errors))

    def test_missing_protected_execution_record_rejected(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        qa.pop("protected_execution_record")
        qa["protected_execution_record_path"] = "missing.json"
        external = advisory_external()
        external["artifact"]["manifest_sha256"] = manifest_digest_excluding_own(manifest)
        passed, errors, _ = check_delivery(manifest, manifest_path=str(FIXTURES_DIR / "valid_advisory_manifest.json"), external_evidence=external)
        self.assertFalse(passed)
        self.assertIn("missing protected QA execution record", "\n".join(errors))

    def test_no_tools_qa_binding_has_no_qa_tool_error_but_gate_stays_blocked(self):
        manifest = load_fixture("valid_advisory_manifest.json")
        qa = manifest["qa"]["records"][0]
        qa["protected_execution_record"]["actual_invocation"]["tools"] = []
        qa["protected_probe_record"]["tools"] = []
        self._first_qa_with_rehashed_records(manifest)
        external = advisory_external()
        external["artifact"]["manifest_sha256"] = manifest_digest_excluding_own(manifest)
        passed, errors, _ = check_delivery(manifest, external_evidence=external)
        joined = "\n".join(errors)
        self.assertFalse(passed)
        self.assertIn("caller-supplied external evidence is advisory only", joined)
        self.assertNotIn("must use no tools", joined)


class TestDeliveryGateCLI(unittest.TestCase):
    def test_cli_rejects_forged_trusted_manifest_during_manifest_validation(self):
        fixture = FIXTURES_DIR / "negative_forged_trusted_manifest.json"
        result = subprocess.run(
            [sys.executable, "scripts/governance/check_delivery_gate.py", str(fixture)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("digest mismatch", result.stderr)

    def test_cli_blocks_premerge_with_advisory_external_evidence(self):
        fixture = FIXTURES_DIR / "valid_advisory_manifest.json"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/governance/check_delivery_gate.py",
                "--external-evidence",
                str(FIXTURES_DIR / "advisory_external_evidence.json"),
                "--phase",
                "pre-merge",
                str(fixture),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("caller-supplied external evidence is advisory only", result.stderr)

    def test_cli_publication_phase_remains_blocked(self):
        fixture = FIXTURES_DIR / "valid_advisory_manifest.json"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/governance/check_delivery_gate.py",
                "--external-evidence",
                str(FIXTURES_DIR / "advisory_external_evidence.json"),
                "--phase",
                "publication",
                str(fixture),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("existing-work freeze", result.stderr)

    def test_cli_bootstrap_blocked_check_passes(self):
        result = subprocess.run(
            [sys.executable, "scripts/governance/check_delivery_gate.py", "--check-bootstrap-blocked"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BLOCKED", result.stderr)


class TestDeliveryGatePinning(unittest.TestCase):
    def test_governance_workflow_is_pinned(self):
        workflow_path = REPO_ROOT / ".github" / "workflows" / "governance.yml"
        errors = check_pinning(str(workflow_path))
        self.assertEqual(errors, [])

    def test_mutable_tag_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as handle:
            handle.write("""
jobs:
  test:
    steps:
      - uses: actions/checkout@v4
""")
            path = Path(handle.name)
        try:
            errors = check_pinning(str(path))
            self.assertTrue(any("unpinned" in error for error in errors), errors)
        finally:
            path.unlink(missing_ok=True)

    def test_mutable_docker_image_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as handle:
            handle.write("""
jobs:
  test:
    steps:
      - uses: docker://python:3.12
""")
            path = Path(handle.name)
        try:
            errors = check_pinning(str(path))
            self.assertTrue(any("docker" in error for error in errors), errors)
        finally:
            path.unlink(missing_ok=True)

    def test_mutable_job_container_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as handle:
            handle.write("""
jobs:
  test:
    container: python:3.12
    steps:
      - run: python --version
""")
            path = Path(handle.name)
        try:
            errors = check_pinning(str(path))
            self.assertTrue(any("job container" in error and "unpinned" in error for error in errors), errors)
        finally:
            path.unlink(missing_ok=True)

    def test_mutable_service_image_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as handle:
            handle.write("""
jobs:
  test:
    services:
      db:
        image: postgres:16
    steps:
      - run: echo ok
""")
            path = Path(handle.name)
        try:
            errors = check_pinning(str(path))
            self.assertTrue(any("service" in error and "unpinned" in error for error in errors), errors)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
