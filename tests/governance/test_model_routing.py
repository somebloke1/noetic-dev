"""Tests for genus-router selection and LiteLLM-only governance invocation."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

from model_routing import (  # noqa: E402
    MAX_MODEL_INPUT_BYTES,
    ModelRoutingError,
    RoutedReviewExhausted,
    _invoke_litellm,
    _policy_commit_identity,
    load_litellm_key,
    load_policy,
    route_and_invoke_review,
    strict_json,
    validate_decision,
    validate_policy_invariants,
)
from hash_tree import canonical_json_sha256, sha256_text  # noqa: E402
from route_evidence import validate_route_evidence  # noqa: E402

SOL = "codex/gpt-5.6-sol"
FABLE = "claude-fable-5"
TERRA = "codex/gpt-5.6-terra"
LUNA = "codex/gpt-5.6-luna"


def model_ref(model: str) -> dict[str, str]:
    endpoint_path = "/v1/chat/completions" if model == FABLE else "/v1/responses"
    result = {
        "model_id": model,
        "endpoint_id": "local-litellm",
        "upstream_model_id": model,
        "interface_type": "openai-compatible",
        "base_url": "http://172.22.10.160:3333",
        "endpoint_path": endpoint_path,
        "token_env": "LITELLM_API_KEY",
    }
    if model != FABLE:
        result["reasoning_effort"] = "high"
    return result


def decision(model: str, number: int = 1) -> dict[str, object]:
    candidate_order = [TERRA, SOL, LUNA]
    fallbacks = candidate_order[candidate_order.index(model) + 1:] if model in candidate_order else []
    return {
        "availability": "verified",
        "fable_eligible": False,
        "genus": "Complex Code Review",
        "model": model,
        "model_ref": model_ref(model),
        "genus_code": "REVIEW-COMPLEX",
        "fallbacks": fallbacks,
        "fallback_refs": [model_ref(item) for item in fallbacks],
        "effective_complexity": "complex",
        "sophistication": "complex",
        "rationale": ["fixed protected review classification"],
        "decision_id": f"d-20260713-{number:06d}",
    }


def request_prompt(body: bytes) -> str:
    request = json.loads(body)
    return request["input"][0]["content"][0]["text"]


def routed_response(body: bytes, review_output: str = '{"verdict":"pass"}') -> bytes:
    prompt = request_prompt(body)
    match = re.fullmatch(
        r"Respond with exactly '(READY [a-f0-9]{16} [a-f0-9]{64})' and nothing else\.",
        prompt,
    )
    output = match.group(1) if match else review_output
    return json.dumps({"output_text": output}).encode()


class FakeService:
    def __init__(self, decisions: list[dict[str, object]], *, reject_outcomes: bool = False) -> None:
        self.decisions = list(decisions)
        self.reject_outcomes = reject_outcomes
        self.inputs: list[dict[str, object]] = []
        self.outcomes: list[dict[str, object]] = []

    async def route_task(self, payload: dict[str, object]) -> dict[str, object]:
        self.inputs.append(payload)
        return self.decisions.pop(0)

    def report_outcome(self, payload: dict[str, object]) -> dict[str, bool]:
        self.outcomes.append(payload)
        if self.reject_outcomes:
            raise RuntimeError("outcome ledger unavailable")
        return {"recorded": True}


class TestModelRouting(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load_policy()

    def test_policy_requires_standard_order_and_high_reasoning(self):
        generative = self.policy["generative"]
        self.assertEqual(generative["standard_models"], [SOL, TERRA, LUNA])
        self.assertEqual(generative["reasoning_effort"], "high")
        self.assertEqual(self.policy["access"]["token_env"], "LITELLM_API_KEY")
        self.assertFalse(self.policy["access"]["direct_provider_access"])

    def test_decision_rejects_direct_or_low_reasoning_references(self):
        valid = decision(TERRA)
        self.assertEqual(validate_decision(valid, self.policy, set())["model"], TERRA)
        mutations = [
            ("endpoint_id", "direct-provider"),
            ("base_url", "https://provider.example"),
            ("base_url", "http://172.22.10.160:3333/"),
            ("token_env", "OPENAI_API_KEY"),
            ("reasoning_effort", "low"),
            ("model_id", "openai-codex/gpt-5.6-terra"),
            ("upstream_model_id", "provider/gpt-5.6-terra"),
            ("endpoint_path", "/v1/embeddings"),
        ]
        for field, value in mutations:
            mutated = json.loads(json.dumps(valid))
            mutated["model_ref"][field] = value
            with self.subTest(field=field), self.assertRaises(ModelRoutingError):
                validate_decision(mutated, self.policy, set())

        unknown = json.loads(json.dumps(valid))
        unknown["model_ref"]["api_key"] = "not-allowed"
        with self.assertRaisesRegex(ModelRoutingError, "unknown fields"):
            validate_decision(unknown, self.policy, set())

        ungoverned = decision(TERRA)
        ungoverned["fallbacks"] = ["unapproved-model"]
        ungoverned["fallback_refs"] = [{
            **model_ref(TERRA),
            "model_id": "unapproved-model",
            "upstream_model_id": "unapproved-model",
        }]
        with self.assertRaisesRegex(ModelRoutingError, "inconsistent"):
            validate_decision(ungoverned, self.policy, set())

    def test_decision_rejects_reselected_excluded_model(self):
        with self.assertRaisesRegex(ModelRoutingError, "forbidden or excluded"):
            validate_decision(decision(TERRA), self.policy, {TERRA})

    def test_decision_rejects_noncanonical_genus_endpoint_and_fallback_order(self):
        wrong_genus = decision(TERRA)
        wrong_genus["genus"] = "FORGED-NONCANONICAL-GENUS"
        with self.assertRaisesRegex(ModelRoutingError, "noncanonical genus"):
            validate_decision(wrong_genus, self.policy, set())

        wrong_endpoint = decision(TERRA)
        wrong_endpoint["model_ref"]["endpoint_path"] = "/v1/chat/completions"
        with self.assertRaisesRegex(ModelRoutingError, "noncanonical endpoint"):
            validate_decision(wrong_endpoint, self.policy, set())

        wrong_order = decision(TERRA)
        wrong_order["fallbacks"] = [LUNA, SOL]
        wrong_order["fallback_refs"] = [model_ref(LUNA), model_ref(SOL)]
        with self.assertRaisesRegex(ModelRoutingError, "inconsistent"):
            validate_decision(wrong_order, self.policy, set())

    def test_responses_invocation_enacts_high_reasoning(self):
        captured = {}

        def post(url, headers, body, timeout):
            captured.update(url=url, headers=headers, body=json.loads(body), timeout=timeout)
            return json.dumps({"output_text": "review-json"}).encode()

        result = _invoke_litellm(
            decision(TERRA), "prompt", self.policy, "key", excluded_models=set(), http_post=post
        )
        self.assertEqual(result, "review-json")
        self.assertEqual(captured["url"], "http://172.22.10.160:3333/v1/responses")
        self.assertEqual(captured["body"]["reasoning"], {"effort": "high"})
        self.assertEqual(captured["body"]["input"], [{
            "role": "user",
            "content": [{"type": "input_text", "text": "prompt"}],
        }])
        self.assertEqual(captured["headers"]["Authorization"], "Bearer key")

    def test_protected_review_rejects_fable_and_forged_route_evidence(self):
        forged = decision(FABLE)
        forged["fable_eligible"] = True
        with self.assertRaisesRegex(ModelRoutingError, "forbidden or excluded"):
            _invoke_litellm(
                forged,
                "prompt",
                self.policy,
                "key",
                excluded_models=set(),
                http_post=lambda *_args: b"",
            )

        mutations = [
            ("effective_complexity", "trivial"),
            ("sophistication", "trivial"),
            ("availability", "forged-unavailable"),
            ("fable_eligible", True),
            ("genus_code", "CHAT-TRIVIAL"),
        ]
        for field, value in mutations:
            forged = decision(TERRA)
            forged[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ModelRoutingError, "protected review"):
                validate_decision(forged, self.policy, set())

    @mock.patch.dict(os.environ, {"LITELLM_API_KEY": "test-key"}, clear=False)
    def test_route_success_reports_outcome_and_returns_evidence(self):
        service = FakeService([decision(TERRA)])

        bodies = []

        def post(_url, _headers, body, _timeout):
            bodies.append(body)
            return routed_response(body)

        result, evidence = route_and_invoke_review(
            "prompt",
            json.loads,
            service=service,
            policy=self.policy,
            http_post=post,
        )
        self.assertEqual(result, {"verdict": "pass"})
        self.assertEqual(evidence["model"], TERRA)
        self.assertEqual(evidence["reasoning"], "high")
        self.assertEqual(evidence["classification"]["high_value"], False)
        self.assertEqual(validate_route_evidence(evidence["route_evidence"], "protected_review"), [])
        self.assertEqual(service.outcomes[0]["outcome"], "success")
        self.assertEqual(service.inputs[0]["prior_failure"], False)
        self.assertEqual(service.inputs[0]["exclude_models"], [])
        self.assertEqual(len(bodies), 2)
        probe = evidence["readiness_probes"][0]
        self.assertEqual(probe["outcome"], "success")
        self.assertEqual(probe["route_decision_id"], "d-20260713-000001")
        self.assertEqual(probe["work_unit_sha256"], sha256_text("prompt"))
        self.assertRegex(probe["policy_commit_sha"], r"^[a-f0-9]{40}$")
        self.assertEqual(probe["policy_sha256"], canonical_json_sha256(self.policy))
        self.assertEqual(
            probe["harness_configuration_sha256"],
            canonical_json_sha256(probe["harness_configuration"]),
        )
        nonce = probe["probe_id"].removeprefix("ready-")
        binding = {
            "nonce": nonce,
            "work_unit_sha256": probe["work_unit_sha256"],
            "policy_commit_sha": probe["policy_commit_sha"],
            "policy_commit_source": probe["policy_commit_source"],
            "policy_sha256": probe["policy_sha256"],
            "route_decision_id": probe["route_decision_id"],
            "model_ref_sha256": probe["model_ref_sha256"],
            "harness_configuration_sha256": probe["harness_configuration_sha256"],
        }
        self.assertEqual(probe["binding_sha256"], canonical_json_sha256(binding))
        self.assertEqual(
            probe["expected_response"],
            f"READY {nonce} {probe['binding_sha256']}",
        )

    @mock.patch.dict(os.environ, {"LITELLM_API_KEY": "test-key"}, clear=False)
    def test_failure_is_reported_then_rerouted_with_exclusion(self):
        service = FakeService([decision(TERRA, 1), decision(SOL, 2)])

        def post(_url, _headers, body, _timeout):
            model = json.loads(body)["model"]
            if model == TERRA and not request_prompt(body).startswith("Respond with exactly 'READY "):
                raise ModelRoutingError("first invocation failed")
            return routed_response(body)

        _, evidence = route_and_invoke_review(
            "prompt",
            json.loads,
            service=service,
            policy=self.policy,
            http_post=post,
        )
        self.assertEqual([item["outcome"] for item in service.outcomes], ["failure", "success"])
        self.assertEqual(service.inputs[1]["prior_failure"], True)
        self.assertEqual(service.inputs[1]["exclude_models"], [TERRA])
        self.assertEqual(evidence["model"], SOL)
        self.assertEqual([item["model"] for item in evidence["attempts"]], [TERRA, SOL])
        self.assertEqual([item["outcome"] for item in evidence["readiness_probes"]], ["success", "success"])
        self.assertNotEqual(
            evidence["readiness_probes"][0]["probe_id"],
            evidence["readiness_probes"][1]["probe_id"],
        )

    @mock.patch.dict(os.environ, {"LITELLM_API_KEY": "test-key"}, clear=False)
    def test_readiness_mismatch_is_reported_then_rerouted(self):
        service = FakeService([decision(TERRA, 1), decision(SOL, 2)])

        def post(_url, _headers, body, _timeout):
            model = json.loads(body)["model"]
            prompt = request_prompt(body)
            if model == TERRA and prompt.startswith("Respond with exactly 'READY "):
                return json.dumps({"output_text": "READY forged"}).encode()
            return routed_response(body)

        _, evidence = route_and_invoke_review(
            "prompt",
            json.loads,
            service=service,
            policy=self.policy,
            http_post=post,
        )
        self.assertEqual([item["outcome"] for item in service.outcomes], ["failure", "success"])
        self.assertEqual([item["outcome"] for item in evidence["readiness_probes"]], ["failure", "success"])
        self.assertEqual(evidence["readiness_probes"][0]["error_type"], "ModelRoutingError")
        self.assertEqual(service.inputs[1]["exclude_models"], [TERRA])

    @mock.patch.dict(os.environ, {"LITELLM_API_KEY": "test-key"}, clear=False)
    def test_outcome_reporting_failure_preserves_evidence_without_rerouting(self):
        service = FakeService([decision(TERRA, 1)], reject_outcomes=True)
        with self.assertRaises(RoutedReviewExhausted) as caught:
            route_and_invoke_review(
                "prompt",
                json.loads,
                service=service,
                policy=self.policy,
                http_post=lambda _url, _headers, body, _timeout: routed_response(body),
            )
        self.assertEqual(len(service.inputs), 1)
        self.assertEqual(len(service.outcomes), 1)
        self.assertEqual(caught.exception.evidence["outcome"], "failure")
        self.assertEqual(caught.exception.evidence["readiness_probes"][0]["outcome"], "success")
        self.assertFalse(caught.exception.evidence["route_evidence"]["attempts"][0]["outcome_recorded"])

    @mock.patch.dict(os.environ, {"LITELLM_API_KEY": "test-key"}, clear=False)
    def test_review_stops_after_three_standard_candidates_fail(self):
        service = FakeService([decision(TERRA, 1), decision(SOL, 2), decision(LUNA, 3)])
        with self.assertRaisesRegex(RoutedReviewExhausted, "all routed review candidates failed") as caught:
            route_and_invoke_review(
                "prompt",
                json.loads,
                service=service,
                policy=self.policy,
                http_post=lambda *_args: (_ for _ in ()).throw(ModelRoutingError("failed")),
            )
        self.assertEqual(len(service.inputs), 3)
        self.assertEqual([item["outcome"] for item in service.outcomes], ["failure"] * 3)
        self.assertEqual(service.inputs[-1]["exclude_models"], [TERRA, SOL])
        self.assertEqual(caught.exception.evidence["outcome"], "failure")
        self.assertEqual(len(caught.exception.evidence["readiness_probes"]), 3)
        self.assertEqual(
            [item["outcome"] for item in caught.exception.evidence["readiness_probes"]],
            ["failure"] * 3,
        )

    def test_policy_commit_uses_fixed_git_and_rejects_bare_hex_directory(self):
        sha = "a" * 40
        with tempfile.TemporaryDirectory() as directory:
            fake_root = Path(directory) / sha
            fake_root.mkdir()
            failed = subprocess.CompletedProcess([], 1, "", "not a repository")
            with (
                mock.patch("model_routing.ROOT", fake_root),
                mock.patch("model_routing.subprocess.run", return_value=failed) as run,
                mock.patch.dict(os.environ, {"PATH": str(Path(directory) / "hostile")}, clear=False),
                self.assertRaisesRegex(ModelRoutingError, "identity is unavailable"),
            ):
                _policy_commit_identity()
        command = run.call_args.args[0]
        child_env = run.call_args.kwargs["env"]
        self.assertEqual(command[0], "/usr/bin/git")
        self.assertEqual(child_env["PATH"], "/usr/bin:/bin")

    @mock.patch("model_routing.subprocess.run")
    def test_policy_commit_verifies_git_root_and_commit(self, run: mock.Mock):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, str(Path(__file__).resolve().parents[2]) + "\n", ""),
            subprocess.CompletedProcess([], 0, "b" * 40 + "\n", ""),
        ]
        commit, source = _policy_commit_identity()
        self.assertEqual(commit, "b" * 40)
        self.assertEqual(source, "verified-git-worktree")
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[1].args[0][-3:], ["rev-parse", "--verify", "HEAD^{commit}"])

    def test_policy_commit_accepts_only_root_controlled_current_release(self):
        sha = "c" * 40
        with tempfile.TemporaryDirectory() as directory:
            install_root = Path(directory) / "noetic-dev-agent-review"
            releases = install_root / "releases"
            release = releases / sha
            release.mkdir(parents=True)
            current = install_root / "current"
            current.symlink_to(release)
            root_owned = SimpleNamespace(st_uid=0, st_mode=0o100755)
            with (
                mock.patch("model_routing.ROOT", release),
                mock.patch("model_routing.PRODUCTION_RELEASES_ROOT", releases),
                mock.patch("model_routing.PRODUCTION_CURRENT_LINK", current),
                mock.patch.object(Path, "lstat", return_value=root_owned),
                mock.patch.object(Path, "is_symlink", return_value=True),
                mock.patch.dict(os.environ, {"NOETIC_AGENT_REVIEW_PRODUCTION": "1"}, clear=False),
            ):
                commit, source = _policy_commit_identity()
        self.assertEqual(commit, sha)
        self.assertEqual(source, "root-owned-current-release")

    def test_production_mode_rejects_noncanonical_root_without_git_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                mock.patch("model_routing.ROOT", Path(directory)),
                mock.patch("model_routing.subprocess.run") as run,
                mock.patch.dict(os.environ, {"NOETIC_AGENT_REVIEW_PRODUCTION": "1"}, clear=False),
                self.assertRaisesRegex(ModelRoutingError, "not a canonical immutable release"),
            ):
                _policy_commit_identity()
        run.assert_not_called()

    def test_production_mode_rejects_writable_release_child(self):
        sha = "d" * 40
        with tempfile.TemporaryDirectory() as directory:
            install_root = Path(directory) / "noetic-dev-agent-review"
            releases = install_root / "releases"
            release = releases / sha
            release.mkdir(parents=True)
            writable = release / "hash_tree.py"
            writable.write_text("pass\n", encoding="utf-8")
            current = install_root / "current"
            current.symlink_to(release)
            root_owned = SimpleNamespace(st_uid=0, st_mode=0o100755)
            root_writable = SimpleNamespace(st_uid=0, st_mode=0o100666)

            def fake_lstat(path: Path):
                return root_writable if path == writable else root_owned

            with (
                mock.patch("model_routing.ROOT", release),
                mock.patch("model_routing.PRODUCTION_RELEASES_ROOT", releases),
                mock.patch("model_routing.PRODUCTION_CURRENT_LINK", current),
                mock.patch.object(Path, "lstat", fake_lstat),
                mock.patch.object(Path, "is_symlink", return_value=True),
                mock.patch.dict(os.environ, {"NOETIC_AGENT_REVIEW_PRODUCTION": "1"}, clear=False),
                self.assertRaisesRegex(ModelRoutingError, "not root-controlled"),
            ):
                _policy_commit_identity()

    def test_credential_file_is_bounded_to_litellm_key(self):
        with tempfile.TemporaryDirectory() as directory:
            key_file = Path(directory) / "key"
            key_file.write_text("file-key\n", encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {"LITELLM_API_KEY_FILE": str(key_file)},
                clear=False,
            ):
                os.environ.pop("LITELLM_API_KEY", None)
                self.assertEqual(load_litellm_key(self.policy), "file-key")
                self.assertNotIn("LITELLM_API_KEY", os.environ)
                inherited = subprocess.run(
                    [sys.executable, "-c", "import os; print(os.environ.get('LITELLM_API_KEY', ''))"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertEqual(inherited.stdout.strip(), "")

    def test_gateway_json_and_output_fail_closed(self):
        for value in [b'{"x":1,"x":2}', b"NaN", b"Infinity", b"1e309"]:
            with self.subTest(value=value), self.assertRaises(ModelRoutingError):
                strict_json(value)
        with self.assertRaises(ModelRoutingError):
            _invoke_litellm(
                decision(TERRA),
                "prompt",
                self.policy,
                "key",
                excluded_models=set(),
                http_post=lambda *_args: b'{"output":[]}',
            )

    @mock.patch.dict(os.environ, {"LITELLM_API_KEY": "test-key"}, clear=False)
    def test_review_prompt_size_is_bounded(self):
        accepted, _ = route_and_invoke_review(
            "x" * 650_000,
            json.loads,
            service=FakeService([decision(TERRA)]),
            policy=self.policy,
            http_post=lambda _url, _headers, body, _timeout: routed_response(body),
        )
        self.assertEqual(accepted, {"verdict": "pass"})
        with self.assertRaisesRegex(ModelRoutingError, "prompt exceeded"):
            route_and_invoke_review(
                "x" * (MAX_MODEL_INPUT_BYTES + 1),
                json.loads,
                service=FakeService([decision(TERRA)]),
                policy=self.policy,
            )

    def test_environment_credential_rejects_whitespace(self):
        with mock.patch.dict(os.environ, {"LITELLM_API_KEY": "bad key"}, clear=False):
            with self.assertRaisesRegex(ModelRoutingError, "credential is invalid"):
                load_litellm_key(self.policy)

    def test_policy_invariants_reject_weakened_selection_or_access(self):
        mutations = [
            ("selection", "router", "manual"),
            ("selection", "mandatory_for_generative_tasks", False),
            ("access", "base_url", "https://provider.example"),
            ("access", "token_env", "OPENAI_API_KEY"),
            ("access", "direct_provider_access", True),
            ("generative", "reasoning_effort", "low"),
            ("failure", "report_outcome_required", False),
        ]
        for section, field, value in mutations:
            weakened = json.loads(json.dumps(self.policy))
            weakened[section][field] = value
            with self.subTest(section=section, field=field), self.assertRaises(ModelRoutingError):
                validate_policy_invariants(weakened)

    def test_policy_invariants_bind_fixed_review_and_fable_scope(self):
        mutations = [
            ("tasks", "agent_review", {
                "task_kind": "chat",
                "complexity": "trivial",
                "blast_radius": "isolated",
                "high_value": True,
                "awaited": False,
            }),
            ("fable", "task_kinds", ["chat"]),
            ("fable", "minimum_complexity", "trivial"),
        ]
        for section, field, value in mutations:
            weakened = json.loads(json.dumps(self.policy))
            target = weakened["tasks"] if section == "tasks" else weakened["generative"]["fable_eligibility"]
            target[field] = value
            with self.subTest(section=section, field=field), self.assertRaises(ModelRoutingError):
                validate_policy_invariants(weakened)

        duplicate = json.loads(json.dumps(self.policy))
        duplicate["generative"]["allowed_models"].append(SOL)
        with self.assertRaises(ModelRoutingError):
            validate_policy_invariants(duplicate)

    def test_policy_invariants_reject_schema_shape_and_endpoint_list_mutations(self):
        mutations = []
        missing_schema = json.loads(json.dumps(self.policy))
        missing_schema.pop("schema_version")
        mutations.append(missing_schema)
        wrong_schema = json.loads(json.dumps(self.policy))
        wrong_schema["schema_version"] = "2"
        mutations.append(wrong_schema)
        unknown = json.loads(json.dumps(self.policy))
        unknown["provider_override"] = {"enabled": True}
        mutations.append(unknown)
        for section in ("access", "generative"):
            for operation in ("duplicate", "reverse", "partial", "extra"):
                mutated = json.loads(json.dumps(self.policy))
                paths = mutated[section]["allowed_endpoint_paths"]
                if operation == "duplicate":
                    paths.append(paths[0])
                elif operation == "reverse":
                    paths.reverse()
                elif operation == "partial":
                    paths.pop()
                else:
                    paths.append("/v1/provider-bypass")
                mutations.append(mutated)
        for mutated in mutations:
            with self.subTest(policy=mutated), self.assertRaisesRegex(ModelRoutingError, "exact contract"):
                validate_policy_invariants(mutated)

    @mock.patch.dict(os.environ, {"LITELLM_API_KEY": "test-key"}, clear=False)
    def test_empty_injected_policy_and_integer_booleans_fail_before_routing(self):
        policies = [{}]
        for field, value in (("high_value", 0), ("awaited", 1)):
            mutated = json.loads(json.dumps(self.policy))
            mutated["tasks"]["agent_review"][field] = value
            policies.append(mutated)
        tuple_list = json.loads(json.dumps(self.policy))
        tuple_list["generative"]["allowed_models"] = tuple(tuple_list["generative"]["allowed_models"])
        policies.append(tuple_list)
        for policy in policies:
            service = FakeService([decision(TERRA)])
            sender = mock.Mock()
            with self.subTest(policy=policy), self.assertRaisesRegex(ModelRoutingError, "exact contract"):
                route_and_invoke_review(
                    "prompt",
                    json.loads,
                    service=service,
                    policy=policy,
                    http_post=sender,
                )
            self.assertEqual(service.inputs, [])
            sender.assert_not_called()
        with tempfile.TemporaryDirectory() as directory:
            policy_path = Path(directory) / "policy.json"
            for policy in policies[1:3]:
                policy_path.write_text(json.dumps(policy), encoding="utf-8")
                with self.subTest(loaded_policy=policy), self.assertRaisesRegex(ModelRoutingError, "exact contract"):
                    load_policy(policy_path)


if __name__ == "__main__":
    unittest.main()
