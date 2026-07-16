#!/usr/bin/env python3
"""Validate protected genus-router/LiteLLM route evidence.

This is a deterministic evidence contract only; it does not perform routing or
change broker runtime behavior.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from json_schema import load_json_strict, validate_schema

REPO_ROOT = Path(__file__).resolve().parents[2]
DECISION_ID = re.compile(r"^d-[0-9]{8}-[0-9]{6}$")
SHA256_HEX = re.compile(r"[a-f0-9]{64}")
STANDARD_MODELS = [
    "codex/gpt-5.6-sol",
    "codex/gpt-5.6-terra",
    "codex/gpt-5.6-luna",
]
PROTECTED_REVIEW_CLASSIFICATION = {
    "task_kind": "review",
    "complexity": "complex",
    "blast_radius": "interface",
    "high_value": False,
    "awaited": True,
}
PROTECTED_REVIEW_CANDIDATES = [STANDARD_MODELS[1], STANDARD_MODELS[0], STANDARD_MODELS[2]]


def validate_route_evidence(evidence: Any, contract_name: str = "protected_review") -> list[str]:
    if contract_name != "protected_review":
        return [f"unknown route contract: {contract_name}"]
    errors: list[str] = []
    schema = load_json_strict(REPO_ROOT / "governance" / "schemas" / "route-evidence.schema.json")
    errors.extend(f"schema: {error}" for error in validate_schema(evidence, schema))
    if errors:
        return errors
    if evidence["classification"] != PROTECTED_REVIEW_CLASSIFICATION:
        errors.append("route classification does not match protected_review")

    policy = load_json_strict(REPO_ROOT / "config" / "model-policy.json")
    access = policy.get("access", {})
    generative = policy.get("generative", {})
    decision_ids: set[str] = set()
    failed_models: list[str] = []
    attempts = evidence["attempts"]
    for index, attempt in enumerate(attempts):
        label = f"route attempt {index + 1}"
        remaining = [model for model in PROTECTED_REVIEW_CANDIDATES if model not in failed_models]
        if "decision_rejection" in attempt:
            model = _validate_rejection(attempt, remaining, decision_ids, label, errors)
            if model in remaining:
                failed_models.append(model)
            continue
        decision = attempt["decision"]
        _validate_decision(decision, remaining, access, generative, decision_ids, label, errors)
        if attempt["invocation_count"] != 1:
            errors.append(f"{label} decision attempt must record exactly one invocation")
        if index < len(attempts) - 1 and attempt["outcome"] != "failure":
            errors.append(f"{label} non-terminal outcome must be failure")
        if decision.get("model") in remaining:
            failed_models.append(decision["model"])
    final_attempt = attempts[-1]
    if "decision" not in final_attempt:
        errors.append("protected_review must end in one validated decision")
    elif final_attempt["outcome"] == "failure" and len(attempts) != len(PROTECTED_REVIEW_CANDIDATES):
        errors.append("protected_review terminal failure must exhaust all routed candidates")
    return errors


def _validate_rejection(
    attempt: dict[str, Any],
    remaining: list[str],
    decision_ids: set[str],
    label: str,
    errors: list[str],
) -> Any:
    rejection = attempt["decision_rejection"]
    decision_id = rejection["decision_id"]
    if not DECISION_ID.fullmatch(decision_id):
        errors.append(f"{label} rejected decision_id is invalid")
    elif decision_id in decision_ids:
        errors.append(f"{label} decision_id is reused")
    else:
        decision_ids.add(decision_id)
    model = rejection["model"]
    if not remaining or model != remaining[0]:
        errors.append(f"{label} rejected model violates routed candidate order")
    if not SHA256_HEX.fullmatch(rejection["raw_decision_sha256"]):
        errors.append(f"{label} rejected raw decision digest is invalid")
    return model


def _validate_decision(
    decision: Any,
    remaining: list[str],
    access: dict[str, Any],
    generative: dict[str, Any],
    decision_ids: set[str],
    label: str,
    errors: list[str],
) -> None:
    expected_fields = {
        "availability", "decision_id", "effective_complexity", "fable_eligible",
        "fallback_refs", "fallbacks", "genus", "genus_code", "independent_approval_eligible",
        "model", "model_ref", "rationale", "routing_profile", "sophistication",
    }
    if not isinstance(decision, dict) or set(decision) != expected_fields:
        errors.append(f"{label} decision fields are incomplete or unknown")
        return
    decision_id = decision["decision_id"]
    if not isinstance(decision_id, str) or not DECISION_ID.fullmatch(decision_id):
        errors.append(f"{label} decision_id is invalid")
    elif decision_id in decision_ids:
        errors.append(f"{label} decision_id is reused")
    else:
        decision_ids.add(decision_id)
    if not remaining or decision["model"] != remaining[0]:
        errors.append(f"{label} selected model violates routed candidate order")
    if decision["fallbacks"] != remaining[1:]:
        errors.append(f"{label} fallback order is inconsistent")
    if (
        decision["genus"] != "Complex Code Review"
        or decision["genus_code"] != "REVIEW-COMPLEX"
        or decision["effective_complexity"] != "complex"
        or decision["sophistication"] != "complex"
        or decision["availability"] != "verified"
        or decision["fable_eligible"] is not False
        or decision["independent_approval_eligible"] is not False
        or decision["routing_profile"] != "standard"
    ):
        errors.append(f"{label} decision does not match protected review classification")
    if not isinstance(decision["rationale"], list) or not decision["rationale"] or not all(
        isinstance(item, str) and item.strip() for item in decision["rationale"]
    ):
        errors.append(f"{label} rationale is invalid")
    _validate_model_ref(decision["model_ref"], decision["model"], access, generative, label, errors)
    fallback_refs = decision["fallback_refs"]
    if not isinstance(fallback_refs, list) or len(fallback_refs) != len(decision["fallbacks"]):
        errors.append(f"{label} fallback references are invalid")
        return
    for index, (model, model_ref) in enumerate(zip(decision["fallbacks"], fallback_refs, strict=True)):
        _validate_model_ref(model_ref, model, access, generative, f"{label} fallback {index + 1}", errors)


def _validate_model_ref(
    raw: Any,
    expected_model: Any,
    access: dict[str, Any],
    generative: dict[str, Any],
    label: str,
    errors: list[str],
) -> None:
    expected_fields = {
        "model_id", "endpoint_id", "upstream_model_id", "interface_type",
        "base_url", "endpoint_path", "token_env", "reasoning_effort",
    }
    if not isinstance(raw, dict) or set(raw) != expected_fields:
        errors.append(f"{label} model reference fields are incomplete or unknown")
        return
    if (
        raw["model_id"] != expected_model
        or raw["upstream_model_id"] != expected_model
        or raw["endpoint_id"] != access.get("endpoint_id")
        or raw["interface_type"] != "openai-compatible"
        or raw["base_url"] != access.get("base_url")
        or raw["endpoint_path"] != "/v1/responses"
        or raw["token_env"] != access.get("token_env")
        or raw["reasoning_effort"] != generative.get("reasoning_effort")
    ):
        errors.append(f"{label} model reference bypasses the canonical LiteLLM contract")
    if expected_model not in generative.get("standard_models", []):
        errors.append(f"{label} model reference is not a standard protected-review model")
