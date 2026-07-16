"""Contract tests for the OpenCode routed-session policy."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.governance.json_schema import validate_schema


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "config" / "opencode-session-policy.json"
SCHEMA_PATH = ROOT / "governance" / "schemas" / "opencode-session-policy.schema.json"
DOC_PATH = ROOT / "docs" / "model-routing-policy.md"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestOpenCodeSessionPolicy(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load_json(POLICY_PATH)
        self.schema = load_json(SCHEMA_PATH)

    def test_schema_validates_exact_contract(self) -> None:
        self.assertEqual(validate_schema(self.policy, self.schema), [])
        for path, value in (
            (("runtime_adapter_ready",), True),
            (("status",), "ready"),
            (("selection", "allowed_provider"), "openai"),
            (("selection", "provider_allowlist"), ["litellm", "openai"]),
            (("session_contract", "maximum_model_turns_per_session"), 2),
            (("session_contract", "tools_allowed"), True),
            (("failure", "missing_report_outcome"), "warn"),
        ):
            with self.subTest(path=path):
                mutated = json.loads(json.dumps(self.policy))
                target = mutated
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.assertNotEqual(validate_schema(mutated, self.schema), [])

    def test_contract_keeps_opencode_blocked_until_wrapper_evidence_exists(self) -> None:
        self.assertEqual(self.policy["adapter"], "opencode")
        self.assertEqual(self.policy["status"], "contract-only")
        self.assertFalse(self.policy["runtime_adapter_ready"])
        self.assertEqual(self.policy["selection"]["router"], "genus-router")
        self.assertEqual(self.policy["selection"]["provider_allowlist"], ["litellm"])
        self.assertTrue(self.policy["selection"]["direct_provider_credentials_scrubbed"])

    def test_session_boundary_is_one_routed_model_turn(self) -> None:
        contract = self.policy["session_contract"]
        self.assertEqual(contract["route_decision_scope"], "per_model_turn")
        self.assertEqual(contract["maximum_model_turns_per_session"], 1)
        self.assertEqual(contract["outcome_reporting_scope"], "per_route_decision")
        self.assertTrue(contract["static_title_required"])
        self.assertTrue(contract["json_events_required"])
        self.assertFalse(contract["tools_allowed"])

    def test_failure_modes_are_fail_closed(self) -> None:
        for key, action in self.policy["failure"].items():
            with self.subTest(key=key):
                self.assertEqual(action, "fail_closed")

    def test_docs_do_not_claim_live_opencode_adapter(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")
        self.assertIn("OpenCode routed-session contract", text)
        self.assertIn("runtime_adapter_ready=false", text)
        self.assertIn("must not be cited as evidence", text)


if __name__ == "__main__":
    unittest.main()
