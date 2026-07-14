"""Contract tests for mandatory genus-router and LiteLLM model governance."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class TestModelPolicy(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((ROOT / "config" / "model-policy.json").read_text())

    def test_all_access_is_litellm_only(self):
        access = self.policy["access"]
        self.assertEqual(access["endpoint_id"], "local-litellm")
        self.assertTrue(access["litellm_required"])
        self.assertFalse(access["direct_provider_access"])
        self.assertEqual(set(access["applies_to_harnesses"]), {"pi", "opencode", "broker", "bare"})

    def test_generative_capability_order_and_fable_limit(self):
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
        self.assertEqual(
            set(generative["allowed_models"]),
            {model for tier in generative["capability_tiers"] for model in tier},
        )
        self.assertTrue(generative["fable_eligibility"]["limited"])
        self.assertEqual(generative["fable_eligibility"]["minimum_complexity"], "complex")

    def test_selection_and_failure_lifecycle_are_mandatory(self):
        selection = self.policy["selection"]
        failure = self.policy["failure"]
        self.assertEqual(selection["router"], "genus-router")
        self.assertTrue(selection["mandatory_for_generative_tasks"])
        self.assertTrue(selection["selection_varies_with_sophistication"])
        self.assertEqual(selection["lifecycle"], ["classify", "route_task", "invoke", "report_outcome"])
        self.assertTrue(failure["report_outcome_required"])
        self.assertTrue(failure["reroute_with_prior_failure"])
        self.assertTrue(failure["exclude_failed_models"])
        self.assertFalse(failure["manual_model_escalation"])
        self.assertEqual(self.policy["execution_contracts"], {
            "agent_review_broker": {
                "readiness_probe_is_phase": True,
                "maximum_substantive_invocations": 1,
                "report_outcome_scope": "aggregate_attempt",
            },
            "authoritative_qa_pi": {
                "operations": ["readiness_probe", "execution"],
                "decision_scope": "per_operation",
                "maximum_invocations_per_decision": 1,
                "report_outcome_scope": "per_operation",
            },
        })
        self.assertEqual(self.policy["tasks"]["agent_review"], {
            "task_kind": "review",
            "complexity": "complex",
            "blast_radius": "interface",
            "high_value": False,
            "awaited": True,
        })
        self.assertEqual(self.policy["tasks"]["authoritative_qa"], self.policy["tasks"]["agent_review"])
        self.assertEqual(self.policy["tasks"]["independent_approval"], {
            **self.policy["tasks"]["agent_review"],
            "high_value": True,
        })

    def test_modality_routes_remain_litellm_governed(self):
        self.assertEqual(self.policy["modalities"], {
            "embed": "snowflake-arctic-embed2",
            "asr": "qwen3-asr",
        })

    def test_agent_review_broker_contains_no_direct_provider_harness(self):
        paths = [
            ROOT / "scripts" / "governance" / "agent_review_broker.py",
            ROOT / "scripts" / "governance" / "model_routing.py",
        ]
        combined = "\n".join(path.read_text() for path in paths)
        for forbidden in ["openai-codex/", "--provider", "run_terra", "OPENAI_API_KEY"]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, combined)

    def test_legacy_profiles_cannot_authorize_runtime_selection(self):
        profiles = json.loads((ROOT / "governance" / "model-profiles.json").read_text())
        self.assertEqual(profiles["runtime_selection"], "forbidden")
        pi_source = (ROOT / "scripts" / "governance" / "run_isolated_pi.py").read_text()
        self.assertIn("--model cannot authorize routed Pi execution", pi_source)
        self.assertIn('policy["tasks"]["authoritative_qa"]', pi_source)


if __name__ == "__main__":
    unittest.main()
