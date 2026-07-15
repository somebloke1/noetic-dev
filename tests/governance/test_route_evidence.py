"""Tests for protected routed model evidence."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

from route_evidence import FABLE, STANDARD_MODELS, validate_route_evidence

SOL, TERRA, LUNA = STANDARD_MODELS


def model_ref(model: str, reasoning_effort: str = "high") -> dict[str, str]:
    result = {
        "model_id": model,
        "endpoint_id": "local-litellm",
        "upstream_model_id": model,
        "interface_type": "openai-compatible",
        "base_url": "http://172.22.10.160:3333",
        "endpoint_path": "/v1/chat/completions" if model == FABLE else "/v1/responses",
        "token_env": "LITELLM_API_KEY",
    }
    if model != FABLE:
        result["reasoning_effort"] = reasoning_effort
    return result


def route_evidence(contract: str, models: list[str] | None = None) -> dict[str, object]:
    high_value = contract == "independent_approval"
    candidates = [SOL] if high_value else [TERRA, SOL, LUNA]
    reasoning_effort = "xhigh" if high_value else "high"
    selected = models or candidates[:1]
    attempts = []
    for index, model in enumerate(selected):
        remaining = [item for item in candidates if item not in selected[:index]]
        attempts.append({
            "decision": {
                "availability": "verified",
                "decision_id": f"d-20260713-{index + 1:06d}",
                "effective_complexity": "complex",
                "fable_eligible": high_value,
                "fallback_refs": [model_ref(item, reasoning_effort) for item in remaining[1:]],
                "fallbacks": remaining[1:],
                "genus": "Complex Code Review",
                "genus_code": "REVIEW-COMPLEX",
                "independent_approval_eligible": high_value,
                "model": model,
                "model_ref": model_ref(model, reasoning_effort),
                "rationale": ["protected route evidence fixture"],
                "routing_profile": "independent_approval" if high_value else "standard",
                "sophistication": "complex",
            },
            "outcome": "success" if index == len(selected) - 1 else "failure",
            "outcome_recorded": True,
            "reasoning_effort": reasoning_effort,
        })
    return {
        "schema_version": "1",
        "classification": {
            "task_kind": "review",
            "complexity": "complex",
            "blast_radius": "interface",
            "high_value": high_value,
            "awaited": True,
            **({"independent_approval": True} if high_value else {}),
        },
        "attempts": attempts,
    }


class TestRouteEvidence(unittest.TestCase):
    def test_authoritative_qa_and_closed_approval_contracts(self):
        self.assertEqual(validate_route_evidence(route_evidence("authoritative_qa"), "authoritative_qa"), [])
        self.assertEqual(validate_route_evidence(route_evidence("independent_approval"), "independent_approval"), [])
        self.assertEqual(
            route_evidence("independent_approval")["attempts"][0]["decision"]["model"], SOL
        )

    def test_independent_approval_rejects_standard_profile_and_non_sol_model(self):
        evidence = route_evidence("independent_approval")
        evidence["attempts"][0]["decision"]["routing_profile"] = "standard"
        self.assertTrue(validate_route_evidence(evidence, "independent_approval"))

        evidence = route_evidence("independent_approval")
        evidence["attempts"][0]["decision"]["model"] = FABLE
        self.assertTrue(validate_route_evidence(evidence, "independent_approval"))

    def test_zero_invocation_decision_rejection_precedes_validated_reroute(self):
        evidence = route_evidence("protected_review", [TERRA, SOL])
        evidence["attempts"][0] = {
            "decision_rejection": {
                "decision_id": "d-20260713-000001",
                "model": TERRA,
                "raw_decision_sha256": "a" * 64,
                "rejection_type": "ModelRoutingError",
            },
            "invocation_count": 0,
            "outcome": "failure",
            "outcome_recorded": True,
        }
        self.assertEqual(validate_route_evidence(evidence, "protected_review"), [])

        for field, value in [
            ("invocation_count", 1),
            ("outcome", "success"),
            ("outcome_recorded", False),
        ]:
            mutated = copy.deepcopy(evidence)
            mutated["attempts"][0][field] = value
            with self.subTest(field=field):
                self.assertTrue(validate_route_evidence(mutated, "protected_review"))
        malformed_digest = copy.deepcopy(evidence)
        malformed_digest["attempts"][0]["decision_rejection"]["raw_decision_sha256"] = "short"
        self.assertTrue(validate_route_evidence(malformed_digest, "protected_review"))
        terminal_rejection = copy.deepcopy(evidence)
        terminal_rejection["attempts"] = terminal_rejection["attempts"][:1]
        self.assertTrue(validate_route_evidence(terminal_rejection, "protected_review"))

    def test_static_or_wrong_contract_evidence_fails_closed(self):
        self.assertTrue(validate_route_evidence({"model_profile": "qa_primary"}, "authoritative_qa"))
        evidence = route_evidence("independent_approval")
        self.assertTrue(validate_route_evidence(evidence, "authoritative_qa"))

    def test_route_mutations_are_rejected(self):
        base = route_evidence("independent_approval")
        mutations = []
        for path, value in [
            (("classification", "high_value"), False),
            (("attempts", 0, "outcome_recorded"), False),
            (("attempts", 0, "reasoning_effort"), "low"),
            (("attempts", 0, "decision", "genus"), "Forged Review"),
            (("attempts", 0, "decision", "independent_approval_eligible"), False),
            (("attempts", 0, "decision", "routing_profile"), "standard"),
            (("attempts", 0, "decision", "model_ref", "reasoning_effort"), "high"),
            (("attempts", 0, "decision", "model"), TERRA),
            (("attempts", 0, "decision", "model_ref", "base_url"), "https://provider.example"),
            (("attempts", 0, "decision", "model_ref", "endpoint_path"), "/v1/chat/completions"),
        ]:
            mutated = copy.deepcopy(base)
            target = mutated
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            mutations.append(mutated)
        unknown = copy.deepcopy(base)
        unknown["attempts"][0]["decision"]["model_ref"]["api_key"] = "forbidden"
        mutations.append(unknown)
        for evidence in mutations:
            with self.subTest(evidence=evidence):
                self.assertTrue(validate_route_evidence(evidence, "independent_approval"))


if __name__ == "__main__":
    unittest.main()
