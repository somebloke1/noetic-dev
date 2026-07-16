"""Contract tests for the canonical model routing policy."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.governance.json_schema import validate_schema


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "config" / "model-policy.json"
SCHEMA_PATH = ROOT / "governance" / "schemas" / "model-policy.schema.json"
DOC_PATH = ROOT / "docs" / "model-routing-policy.md"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestModelPolicy(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load_json(POLICY_PATH)
        self.schema = load_json(SCHEMA_PATH)

    def test_schema_validates_exact_policy_contract(self) -> None:
        self.assertEqual(validate_schema(self.policy, self.schema), [])
        for path, value in (
            (("selection", "router"), "manual"),
            (("access", "direct_provider_access"), True),
            (("access", "base_url"), "https://api.openai.com"),
            (("access", "base_url"), "http://172.22.10.160:3333"),
            (("generative", "allowed_models"), ["codex/gpt-5.6-terra"]),
            (("generative", "fable_eligibility", "high_value_required"), False),
            (("modalities", "asr"), "qwen3.6-a3b"),
        ):
            with self.subTest(path=path):
                mutated = json.loads(json.dumps(self.policy))
                target = mutated
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.assertNotEqual(validate_schema(mutated, self.schema), [])

    def test_all_access_is_litellm_only(self) -> None:
        access = self.policy["access"]
        self.assertEqual(access["endpoint_id"], "local-litellm")
        self.assertEqual(access["base_url"], "http://127.0.0.1:3333")
        self.assertEqual(access["token_env"], "LITELLM_API_KEY")
        self.assertTrue(access["litellm_required"])
        self.assertFalse(access["direct_provider_access"])
        self.assertEqual(set(access["applies_to_harnesses"]), {"pi", "opencode", "broker", "bare"})
        self.assertIn("/v1/embeddings", access["allowed_endpoint_paths"])
        self.assertIn("/v1/audio/transcriptions", access["allowed_endpoint_paths"])

    def test_generative_capability_order_and_fable_limit(self) -> None:
        generative = self.policy["generative"]
        self.assertEqual(generative["standard_models"], [
            "codex/gpt-5.6-sol",
            "codex/gpt-5.6-terra",
            "codex/gpt-5.6-luna",
        ])
        self.assertEqual(generative["reasoning_effort"], "high")
        self.assertEqual(generative["capability_tiers"], [
            ["codex/gpt-5.6-sol", "claude-fable-5"],
            ["codex/gpt-5.6-terra"],
            ["codex/gpt-5.6-luna"],
        ])
        self.assertEqual(generative["allowed_models"], [
            "codex/gpt-5.6-sol",
            "claude-fable-5",
            "codex/gpt-5.6-terra",
            "codex/gpt-5.6-luna",
        ])
        self.assertTrue(generative["fable_eligibility"]["limited"])
        self.assertTrue(generative["fable_eligibility"]["high_value_required"])
        self.assertEqual(generative["fable_eligibility"]["minimum_complexity"], "complex")
        self.assertFalse(self.policy["tasks"]["agent_review"]["high_value"])
        self.assertFalse(self.policy["tasks"]["authoritative_qa"]["high_value"])

    def test_selection_and_failure_lifecycle_are_mandatory(self) -> None:
        self.assertEqual(self.policy["selection"], {
            "lifecycle": ["classify", "route_task", "invoke", "report_outcome"],
            "mandatory_for_generative_tasks": True,
            "router": "genus-router",
            "selection_varies_with_sophistication": True,
        })
        self.assertEqual(self.policy["failure"], {
            "exclude_failed_models": True,
            "manual_model_escalation": False,
            "report_outcome_required": True,
            "reroute_with_prior_failure": True,
        })

    def test_tasks_and_execution_contracts_are_bounded(self) -> None:
        self.assertEqual(self.policy["execution_contracts"]["agent_review_broker"], {
            "invocation_limit_scope": "per_route_decision",
            "maximum_substantive_invocations_per_route": 1,
            "readiness_probe_is_phase": True,
            "reroute_after_reported_failure": True,
            "report_outcome_scope": "aggregate_attempt",
        })
        self.assertTrue(self.policy["failure"]["reroute_with_prior_failure"])
        self.assertEqual(self.policy["execution_contracts"]["authoritative_qa_pi"], {
            "decision_scope": "per_operation",
            "maximum_invocations_per_decision": 1,
            "operations": ["readiness_probe", "execution"],
            "report_outcome_scope": "per_operation",
        })
        self.assertEqual(self.policy["tasks"]["agent_review"], self.policy["tasks"]["authoritative_qa"])
        self.assertTrue(self.policy["tasks"]["independent_approval"]["independent_approval"])

    def test_modality_routes_remain_litellm_governed(self) -> None:
        self.assertEqual(self.policy["modalities"], {
            "asr": "qwen3-asr",
            "embed": "snowflake-arctic-embed2",
        })

    def test_docs_do_not_overclaim_runtime_migration(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")
        self.assertIn("does not claim live OpenCode, protected Pi, embedding, or ASR adapters are fully migrated", text)
        self.assertIn("must not be cited as evidence", text)
        self.assertIn("Missing runtime adapters remain open work", text)
        self.assertIn("full broker genus-router outcome reporting", text)


if __name__ == "__main__":
    unittest.main()
