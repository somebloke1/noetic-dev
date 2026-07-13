#!/usr/bin/env python3
"""Deterministic validation for protected genus-router/LiteLLM evidence."""

from __future__ import annotations

import re
from typing import Any

CANONICAL_BASE_URL = "http://172.22.10.160:3333"
STANDARD_MODELS = [
    "codex/gpt-5.6-sol",
    "codex/gpt-5.6-terra",
    "codex/gpt-5.6-luna",
]
FABLE = "claude-fable-5"
CONTRACTS = {
    "protected_review": {
        "classification": {
            "task_kind": "review",
            "complexity": "complex",
            "blast_radius": "interface",
            "high_value": False,
            "awaited": True,
        },
        "candidates": [STANDARD_MODELS[1], STANDARD_MODELS[0], STANDARD_MODELS[2]],
        "fable_eligible": False,
    },
    "authoritative_qa": {
        "classification": {
            "task_kind": "review",
            "complexity": "complex",
            "blast_radius": "interface",
            "high_value": False,
            "awaited": True,
        },
        "candidates": [STANDARD_MODELS[1], STANDARD_MODELS[0], STANDARD_MODELS[2]],
        "fable_eligible": False,
    },
    "independent_approval": {
        "classification": {
            "task_kind": "review",
            "complexity": "complex",
            "blast_radius": "interface",
            "high_value": True,
            "awaited": True,
        },
        "candidates": [FABLE, STANDARD_MODELS[1], STANDARD_MODELS[0], STANDARD_MODELS[2]],
        "fable_eligible": True,
    },
}
DECISION_ID = re.compile(r"^d-\d{8}-\d{6}$")


def validate_route_evidence(evidence: Any, contract_name: str) -> list[str]:
    errors: list[str] = []
    contract = CONTRACTS.get(contract_name)
    if contract is None:
        return [f"unknown route contract: {contract_name}"]
    if not isinstance(evidence, dict):
        return ["route evidence must be an object"]
    if set(evidence) != {"schema_version", "classification", "attempts"}:
        errors.append("route evidence fields are incomplete or unknown")
    if evidence.get("schema_version") != "1":
        errors.append("route evidence schema_version must be 1")
    if not _strict_equal(evidence.get("classification"), contract["classification"]):
        errors.append(f"route classification does not match {contract_name}")

    attempts = evidence.get("attempts")
    candidates = list(contract["candidates"])
    if not isinstance(attempts, list) or not attempts or len(attempts) > len(candidates):
        errors.append("route attempts must contain one bounded candidate sequence")
        return errors

    decision_ids: set[str] = set()
    failed_models: list[str] = []
    for index, attempt in enumerate(attempts):
        label = f"route attempt {index + 1}"
        if not isinstance(attempt, dict) or set(attempt) != {
            "decision", "outcome", "outcome_recorded", "reasoning_effort"
        }:
            errors.append(f"{label} fields are incomplete or unknown")
            continue
        if attempt.get("outcome_recorded") is not True:
            errors.append(f"{label} outcome was not recorded")
        if attempt.get("reasoning_effort") != "high":
            errors.append(f"{label} did not enact high reasoning")
        expected_outcome = "success" if index == len(attempts) - 1 else "failure"
        if attempt.get("outcome") != expected_outcome:
            errors.append(f"{label} outcome must be {expected_outcome}")

        remaining = [model for model in candidates if model not in failed_models]
        decision = attempt.get("decision")
        _validate_decision(
            decision,
            remaining,
            bool(contract["fable_eligible"]),
            decision_ids,
            label,
            errors,
        )
        if isinstance(decision, dict) and decision.get("model") in remaining:
            failed_models.append(decision["model"])
    return errors


def _validate_decision(
    decision: Any,
    remaining: list[str],
    fable_eligible: bool,
    decision_ids: set[str],
    label: str,
    errors: list[str],
) -> None:
    expected_fields = {
        "availability", "decision_id", "effective_complexity", "fable_eligible",
        "fallback_refs", "fallbacks", "genus", "genus_code", "model", "model_ref",
        "rationale", "sophistication",
    }
    if not isinstance(decision, dict) or set(decision) != expected_fields:
        errors.append(f"{label} decision fields are incomplete or unknown")
        return
    decision_id = decision.get("decision_id")
    if not isinstance(decision_id, str) or not DECISION_ID.fullmatch(decision_id):
        errors.append(f"{label} decision_id is invalid")
    elif decision_id in decision_ids:
        errors.append(f"{label} decision_id is reused")
    else:
        decision_ids.add(decision_id)
    if not remaining or decision.get("model") != remaining[0]:
        errors.append(f"{label} selected model violates routed candidate order")
    if decision.get("fallbacks") != remaining[1:]:
        errors.append(f"{label} fallback order is inconsistent")
    if (
        decision.get("genus") != "Complex Code Review"
        or decision.get("genus_code") != "REVIEW-COMPLEX"
        or decision.get("effective_complexity") != "complex"
        or decision.get("sophistication") != "complex"
        or decision.get("availability") != "verified"
        or decision.get("fable_eligible") is not fable_eligible
    ):
        errors.append(f"{label} decision does not match the protected review genus")
    rationale = decision.get("rationale")
    if not isinstance(rationale, list) or not rationale or not all(isinstance(item, str) for item in rationale):
        errors.append(f"{label} rationale is invalid")

    _validate_model_ref(decision.get("model_ref"), decision.get("model"), label, errors)
    fallback_refs = decision.get("fallback_refs")
    fallbacks = decision.get("fallbacks")
    if not isinstance(fallback_refs, list) or not isinstance(fallbacks, list) or len(fallback_refs) != len(fallbacks):
        errors.append(f"{label} fallback references are invalid")
        return
    for index, (model, model_ref) in enumerate(zip(fallbacks, fallback_refs, strict=True)):
        _validate_model_ref(model_ref, model, f"{label} fallback {index + 1}", errors)


def _validate_model_ref(raw: Any, expected_model: Any, label: str, errors: list[str]) -> None:
    standard_fields = {
        "model_id", "endpoint_id", "upstream_model_id", "interface_type", "base_url",
        "endpoint_path", "token_env", "reasoning_effort",
    }
    fable_fields = standard_fields - {"reasoning_effort"}
    expected_fields = fable_fields if expected_model == FABLE else standard_fields
    if not isinstance(raw, dict) or set(raw) != expected_fields:
        errors.append(f"{label} model reference fields are incomplete or unknown")
        return
    expected_path = "/v1/chat/completions" if expected_model == FABLE else "/v1/responses"
    if (
        raw.get("model_id") != expected_model
        or raw.get("upstream_model_id") != expected_model
        or raw.get("endpoint_id") != "local-litellm"
        or raw.get("interface_type") != "openai-compatible"
        or raw.get("base_url") != CANONICAL_BASE_URL
        or raw.get("endpoint_path") != expected_path
        or raw.get("token_env") != "LITELLM_API_KEY"
    ):
        errors.append(f"{label} model reference bypasses the canonical LiteLLM contract")
    if expected_model != FABLE and raw.get("reasoning_effort") != "high":
        errors.append(f"{label} standard model reference does not require high reasoning")


def _strict_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _strict_equal(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _strict_equal(item, expected_item)
            for item, expected_item in zip(actual, expected, strict=True)
        )
    return bool(actual == expected)
