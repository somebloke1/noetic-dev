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


def model_ref(model: str) -> dict[str, str]:
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
        result["reasoning_effort"] = "high"
    return result


def route_evidence(contract: str, models: list[str] | None = None) -> dict[str, object]:
    high_value = contract == "independent_approval"
    candidates = [FABLE, TERRA, SOL, LUNA] if high_value else [TERRA, SOL, LUNA]
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
                "fallback_refs": [model_ref(item) for item in remaining[1:]],
                "fallbacks": remaining[1:],
                "genus": "Complex Code Review",
                "genus_code": "REVIEW-COMPLEX",
                "model": model,
                "model_ref": model_ref(model),
                "rationale": ["protected route evidence fixture"],
                "sophistication": "complex",
            },
            "outcome": "success" if index == len(selected) - 1 else "failure",
            "outcome_recorded": True,
            "reasoning_effort": "high",
        })
    return {
        "schema_version": "1",
        "classification": {
            "task_kind": "review",
            "complexity": "complex",
            "blast_radius": "interface",
            "high_value": high_value,
            "awaited": True,
        },
        "attempts": attempts,
    }


class TestRouteEvidence(unittest.TestCase):
    def test_authoritative_qa_and_high_value_approval_contracts(self):
        self.assertEqual(validate_route_evidence(route_evidence("authoritative_qa"), "authoritative_qa"), [])
        self.assertEqual(validate_route_evidence(route_evidence("independent_approval"), "independent_approval"), [])
        rerouted = route_evidence("independent_approval", [FABLE, TERRA, SOL])
        self.assertEqual(validate_route_evidence(rerouted, "independent_approval"), [])

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
            (("attempts", 0, "decision", "model"), TERRA),
            (("attempts", 0, "decision", "model_ref", "base_url"), "https://provider.example"),
            (("attempts", 0, "decision", "model_ref", "endpoint_path"), "/v1/responses"),
        ]:
            mutated = copy.deepcopy(base)
            target = mutated
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            mutations.append(mutated)
        reordered = copy.deepcopy(base)
        reordered["attempts"][0]["decision"]["fallbacks"].reverse()
        mutations.append(reordered)
        unknown = copy.deepcopy(base)
        unknown["attempts"][0]["decision"]["model_ref"]["api_key"] = "forbidden"
        mutations.append(unknown)
        for evidence in mutations:
            with self.subTest(evidence=evidence):
                self.assertTrue(validate_route_evidence(evidence, "independent_approval"))


if __name__ == "__main__":
    unittest.main()
