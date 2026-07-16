"""Contract tests for embedding and ASR readiness policy."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.governance.json_schema import validate_schema


ROOT = Path(__file__).resolve().parents[2]
MODEL_POLICY_PATH = ROOT / "config" / "model-policy.json"
POLICY_PATH = ROOT / "config" / "modality-readiness-policy.json"
SCHEMA_PATH = ROOT / "governance" / "schemas" / "modality-readiness-policy.schema.json"
DOC_PATH = ROOT / "docs" / "model-routing-policy.md"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestModalityReadinessPolicy(unittest.TestCase):
    def setUp(self) -> None:
        self.model_policy = load_json(MODEL_POLICY_PATH)
        self.policy = load_json(POLICY_PATH)
        self.schema = load_json(SCHEMA_PATH)

    def test_schema_validates_exact_contract(self) -> None:
        self.assertEqual(validate_schema(self.policy, self.schema), [])
        for path, value in (
            (("runtime_adapters_ready",), True),
            (("status",), "ready"),
            (("selection", "direct_access_allowed"), True),
            (("selection", "access_endpoint_id"), "direct-asr"),
            (("modalities", "embed", "ready"), True),
            (("modalities", "asr", "required_endpoint_path"), "/v1/audio"),
            (("evidence_required",), ["readiness_probe_id"]),
        ):
            with self.subTest(path=path):
                mutated = json.loads(json.dumps(self.policy))
                target = mutated
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.assertNotEqual(validate_schema(mutated, self.schema), [])

    def test_modalities_match_canonical_model_policy(self) -> None:
        self.assertEqual(self.policy["modalities"]["embed"]["model"], self.model_policy["modalities"]["embed"])
        self.assertEqual(self.policy["modalities"]["asr"]["model"], self.model_policy["modalities"]["asr"])
        self.assertIn(self.policy["modalities"]["embed"]["required_endpoint_path"], self.model_policy["access"]["allowed_endpoint_paths"])
        self.assertIn(self.policy["modalities"]["asr"]["required_endpoint_path"], self.model_policy["access"]["allowed_endpoint_paths"])

    def test_readiness_claims_remain_blocked_without_evidence(self) -> None:
        self.assertEqual(self.policy["status"], "contract-only")
        self.assertFalse(self.policy["runtime_adapters_ready"])
        self.assertFalse(self.policy["modalities"]["embed"]["ready"])
        self.assertFalse(self.policy["modalities"]["asr"]["ready"])
        for required in [
            "route_decision_id",
            "readiness_probe_id",
            "request_shape_hash",
            "response_shape_hash",
            "latency_budget_ms",
            "report_outcome_id",
        ]:
            self.assertIn(required, self.policy["evidence_required"])

    def test_docs_do_not_claim_modality_runtime_readiness(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")
        self.assertIn("modality readiness contract", text)
        self.assertIn("runtime_adapters_ready=false", text)
        self.assertIn("must not be cited as evidence", text)


if __name__ == "__main__":
    unittest.main()
