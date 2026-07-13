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


def decision(model: str, number: int = 1) -> dict[str, object]:
    endpoint_path = "/v1/chat/completions" if model == FABLE else "/v1/responses"
    model_ref = {
        "model_id": model,
        "endpoint_id": "local-litellm",
        "upstream_model_id": model,
        "interface_type": "openai-compatible",
        "base_url": "http://172.22.10.160:3333",
        "endpoint_path": endpoint_path,
        "token_env": "LITELLM_API_KEY",
    }
    if model != FABLE:
        model_ref["reasoning_effort"] = "high"
    return {
        "model": model,
        "model_ref": model_ref,
        "genus_code": "REVIEW-COMPLEX",
        "fallbacks": [],
        "fallback_refs": [],
        "effective_complexity": "complex",
        "sophistication": "complex",
        "availability": "verified",
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
            **ungoverned["model_ref"],
            "model_id": "unapproved-model",
            "upstream_model_id": "unapproved-model",
        }]
        with self.assertRaisesRegex(ModelRoutingError, "not governed"):
            validate_decision(ungoverned, self.policy, set())

    def test_decision_rejects_reselected_excluded_model(self):
        with self.assertRaisesRegex(ModelRoutingError, "forbidden or excluded"):
            validate_decision(decision(TERRA), self.policy, {TERRA})

    def test_responses_invocation_enacts_high_reasoning(self):
        captured = {}

        def post(url, headers, body, timeout):
            captured.update(url=url, headers=headers, body=json.loads(body), timeout=timeout)
            return json.dumps({"output_text": "review-json"}).encode()

        result = _invoke_litellm(
            decision(TERRA), "prompt", self.policy, "key", http_post=post
        )
        self.assertEqual(result, "review-json")
        self.assertEqual(captured["url"], "http://172.22.10.160:3333/v1/responses")
        self.assertEqual(captured["body"]["reasoning"], {"effort": "high"})
        self.assertEqual(captured["body"]["input"], [{
            "role": "user",
            "content": [{"type": "input_text", "text": "prompt"}],
        }])
        self.assertEqual(captured["headers"]["Authorization"], "Bearer key")

    def test_fable_chat_invocation_enacts_high_reasoning(self):
        captured = {}

        def post(_url, _headers, body, _timeout):
            captured.update(json.loads(body))
            return json.dumps({"choices": [{"message": {"content": "review-json"}}]}).encode()

        result = _invoke_litellm(
            decision(FABLE), "prompt", self.policy, "key", http_post=post
        )
        self.assertEqual(result, "review-json")
        self.assertEqual(captured["reasoning_effort"], "high")
        self.assertEqual(captured["messages"], [{"role": "user", "content": "prompt"}])

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


if __name__ == "__main__":
    unittest.main()
