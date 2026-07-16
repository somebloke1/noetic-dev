"""Tests for protected broker route evidence contracts."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

from route_evidence import STANDARD_MODELS, validate_route_evidence  # noqa: E402

SOL, TERRA, LUNA = STANDARD_MODELS


def model_ref(model: str) -> dict[str, str]:
    return {
        "model_id": model,
        "endpoint_id": "local-litellm",
        "upstream_model_id": model,
        "interface_type": "openai-compatible",
        "base_url": "http://127.0.0.1:3333",
        "endpoint_path": "/v1/responses",
        "token_env": "LITELLM_API_KEY",
        "reasoning_effort": "high",
    }


def decision(model: str, remaining: list[str], number: int = 1) -> dict[str, object]:
    return {
        "availability": "verified",
        "decision_id": f"d-20260716-{number:06d}",
        "effective_complexity": "complex",
        "fable_eligible": False,
        "fallback_refs": [model_ref(item) for item in remaining[1:]],
        "fallbacks": remaining[1:],
        "genus": "Complex Code Review",
        "genus_code": "REVIEW-COMPLEX",
        "independent_approval_eligible": False,
        "model": model,
        "model_ref": model_ref(model),
        "rationale": ["protected broker route evidence fixture"],
        "routing_profile": "standard",
        "sophistication": "complex",
    }


def route_evidence(models: list[str] | None = None) -> dict[str, object]:
    candidates = [TERRA, SOL, LUNA]
    selected = models or [TERRA]
    attempts = []
    for index, model in enumerate(selected):
        remaining = [item for item in candidates if item not in selected[:index]]
        attempts.append({
            "decision": decision(model, remaining, index + 1),
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
            "high_value": False,
            "awaited": True,
        },
        "attempts": attempts,
    }


class TestRouteEvidence(unittest.TestCase):
    def test_valid_success_and_reroute_sequences(self) -> None:
        self.assertEqual(validate_route_evidence(route_evidence()), [])
        self.assertEqual(validate_route_evidence(route_evidence([TERRA, SOL])), [])

    def test_zero_invocation_rejection_can_precede_success(self) -> None:
        evidence = route_evidence([TERRA, SOL])
        evidence["attempts"][0] = {
            "decision_rejection": {
                "decision_id": "d-20260716-000001",
                "model": TERRA,
                "raw_decision_sha256": "a" * 64,
                "rejection_type": "ModelRoutingError",
            },
            "invocation_count": 0,
            "outcome": "failure",
            "outcome_recorded": True,
        }
        self.assertEqual(validate_route_evidence(evidence), [])

        tainted = copy.deepcopy(evidence)
        tainted["attempts"][0]["decision_rejection"]["decision_id"] += "\n"
        self.assertTrue(validate_route_evidence(tainted))

        tainted = copy.deepcopy(evidence)
        tainted["attempts"][0]["decision_rejection"]["raw_decision_sha256"] += "\n"
        self.assertTrue(validate_route_evidence(tainted))

    def test_rejects_static_or_unknown_contract_evidence(self) -> None:
        self.assertTrue(validate_route_evidence({"model": TERRA}))
        self.assertTrue(validate_route_evidence(route_evidence(), "unknown"))

    def test_route_mutations_fail_closed(self) -> None:
        mutations = []
        for path, value in [
            (("classification", "high_value"), True),
            (("attempts", 0, "outcome_recorded"), False),
            (("attempts", 0, "reasoning_effort"), "low"),
            (("attempts", 0, "decision", "genus"), "Other"),
            (("attempts", 0, "decision", "model"), SOL),
            (("attempts", 0, "decision", "fallbacks"), [LUNA, SOL]),
            (("attempts", 0, "decision", "model_ref", "base_url"), "https://provider.example"),
            (("attempts", 0, "decision", "model_ref", "endpoint_path"), "/v1/chat/completions"),
            (("attempts", 0, "decision", "rationale"), [""]),
        ]:
            mutated = copy.deepcopy(route_evidence())
            target = mutated
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            mutations.append(mutated)
        unknown = copy.deepcopy(route_evidence())
        unknown["attempts"][0]["decision"]["model_ref"]["api_key"] = "forbidden"
        mutations.append(unknown)
        for evidence in mutations:
            with self.subTest(evidence=evidence):
                self.assertTrue(validate_route_evidence(evidence))

    def test_decision_ids_are_unique_and_ascii_shaped(self) -> None:
        reused = route_evidence([TERRA, SOL])
        reused["attempts"][1]["decision"]["decision_id"] = reused["attempts"][0]["decision"]["decision_id"]
        self.assertTrue(validate_route_evidence(reused))
        for bad_id in ["d-20260716-000001\n", "d-20260716-00001", "d-٢٠٢٦٠٧١٦-٠٠٠٠٠١"]:
            mutated = route_evidence()
            mutated["attempts"][0]["decision"]["decision_id"] = bad_id
            with self.subTest(bad_id=bad_id):
                self.assertTrue(validate_route_evidence(mutated))


if __name__ == "__main__":
    unittest.main()
