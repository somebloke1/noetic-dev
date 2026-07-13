"""Tests for genus-router selection and LiteLLM-only governance invocation."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

from model_routing import (
    ModelRoutingError,
    _invoke_litellm,
    load_litellm_key,
    load_policy,
    route_and_invoke_review,
    strict_json,
    validate_decision,
    validate_policy_invariants,
)

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


class FakeService:
    def __init__(self, decisions: list[dict[str, object]]) -> None:
        self.decisions = list(decisions)
        self.inputs: list[dict[str, object]] = []
        self.outcomes: list[dict[str, object]] = []

    async def route_task(self, payload: dict[str, object]) -> dict[str, object]:
        self.inputs.append(payload)
        return self.decisions.pop(0)

    def report_outcome(self, payload: dict[str, object]) -> dict[str, bool]:
        self.outcomes.append(payload)
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

        def post(_url, _headers, _body, _timeout):
            return json.dumps({"output_text": '{"verdict":"pass"}'}).encode()

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
        self.assertEqual(service.outcomes[0]["outcome"], "success")
        self.assertEqual(service.inputs[0]["prior_failure"], False)
        self.assertEqual(service.inputs[0]["exclude_models"], [])

    @mock.patch.dict(os.environ, {"LITELLM_API_KEY": "test-key"}, clear=False)
    def test_failure_is_reported_then_rerouted_with_exclusion(self):
        service = FakeService([decision(TERRA, 1), decision(SOL, 2)])

        def post(_url, _headers, body, _timeout):
            model = json.loads(body)["model"]
            if model == TERRA:
                raise ModelRoutingError("first invocation failed")
            return json.dumps({"output_text": '{"verdict":"pass"}'}).encode()

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

    @mock.patch.dict(os.environ, {"LITELLM_API_KEY": "test-key"}, clear=False)
    def test_review_stops_after_three_standard_candidates_fail(self):
        service = FakeService([decision(TERRA, 1), decision(SOL, 2), decision(LUNA, 3)])
        with self.assertRaisesRegex(ModelRoutingError, "all routed review candidates failed"):
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
                os.environ.pop("LITELLM_API_KEY", None)

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
        with self.assertRaisesRegex(ModelRoutingError, "prompt exceeded"):
            route_and_invoke_review(
                "x" * 300_001,
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
