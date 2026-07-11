#!/usr/bin/env python3
"""Dependency-free validation for model selection/access contracts."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec" / "models" / "v0"
CONFIG_REF = re.compile(r"^config:[a-z][a-z0-9_.-]+$")
ENV_REF = re.compile(r"^env:[A-Z][A-Z0-9_]+$")
DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load(relative: str) -> Any:
    path = SPEC / relative
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot load {path.relative_to(ROOT)}: {error}") from error


def digest(value: dict[str, Any]) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def registry_errors(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    endpoints = registry.get("endpoints", [])
    models = registry.get("models", [])
    endpoint_ids = [endpoint.get("endpoint_id") for endpoint in endpoints]
    model_refs = [model.get("model_ref") for model in models]
    if len(endpoint_ids) != len(set(endpoint_ids)):
        errors.append("duplicate endpoint_id")
    if len(model_refs) != len(set(model_refs)):
        errors.append("duplicate model_ref")
    by_endpoint = {endpoint["endpoint_id"]: endpoint for endpoint in endpoints}
    for endpoint in endpoints:
        if not CONFIG_REF.fullmatch(endpoint.get("base_url_ref", "")):
            errors.append("endpoint base_url_ref must be opaque config reference")
        credential = endpoint.get("credential_ref")
        if credential is not None and not ENV_REF.fullmatch(credential):
            errors.append("endpoint credential_ref must be env reference")
        health = endpoint.get("health_policy", {})
        if not 1 <= health.get("ttl_seconds", 0) <= 3600:
            errors.append("endpoint health ttl out of bounds")
    for model in models:
        if model.get("endpoint_id") not in by_endpoint:
            errors.append("model references unknown endpoint")
    enabled = [endpoint for endpoint in endpoints if endpoint.get("enabled")]
    if not any(endpoint["access_kind"] == "litellm_normalized" and endpoint["interface_type"] in {"chat_completions", "responses"} for endpoint in enabled):
        errors.append("registry lacks LiteLLM-normalized primary chat access")
    if not any(endpoint["access_kind"] == "direct_local" and endpoint["interface_type"] == "embeddings" for endpoint in enabled):
        errors.append("registry loses direct local embedding access")
    if not any(endpoint["access_kind"] == "direct_local" and endpoint["interface_type"] == "asr" for endpoint in enabled):
        errors.append("registry loses direct local ASR access")
    return errors


def candidate_errors(candidate: dict[str, Any], registry: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    models = {model["model_ref"]: model for model in registry["models"]}
    endpoints = {endpoint["endpoint_id"]: endpoint for endpoint in registry["endpoints"]}
    model = models.get(candidate.get("model_ref"))
    if model is None:
        return [f"{label} is not registered"]
    endpoint = endpoints.get(model["endpoint_id"])
    if endpoint is None or candidate.get("endpoint_id") != model["endpoint_id"]:
        errors.append(f"{label} endpoint mismatch")
        return errors
    expected = {
        "access_kind": endpoint["access_kind"],
        "interface_type": endpoint["interface_type"],
        "base_url_ref": endpoint["base_url_ref"],
        "credential_ref": endpoint["credential_ref"],
        "upstream_model_ref": model["upstream_model_ref"],
    }
    for field, value in expected.items():
        if candidate.get(field) != value:
            errors.append(f"{label} {field} mismatch")
    if not CONFIG_REF.fullmatch(str(candidate.get("base_url_ref", ""))):
        errors.append("candidate base_url_ref must be opaque config reference")
    credential = candidate.get("credential_ref")
    if credential is not None and not ENV_REF.fullmatch(str(credential)):
        errors.append("candidate credential_ref must be env reference")
    return errors


def selection_errors(selection: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    registry_digest = digest(registry)
    if selection["registry"]["registry_digest"] != registry_digest:
        errors.append("selection registry digest mismatch")
    if selection["availability_snapshot"]["registry_digest"] != selection["registry"]["registry_digest"]:
        errors.append("availability snapshot registry digest mismatch")
    if selection["registry"]["registry_id"] != registry["registry_id"] or selection["registry"]["registry_version"] != registry["registry_version"]:
        errors.append("selection registry identity mismatch")
    if selection["registry"]["policy_version"] != registry["policy_version"]:
        errors.append("selection policy version mismatch")
    if not DIGEST.fullmatch(selection["registry"].get("policy_digest", "")):
        errors.append("selection policy digest invalid")
    try:
        observed = parse_time(selection["availability_snapshot"]["observed_at"])
        expires = parse_time(selection["availability_snapshot"]["expires_at"])
        decided = parse_time(selection["decided_at"])
        if not observed <= decided < expires:
            errors.append("availability snapshot expired before decision")
    except (TypeError, ValueError):
        errors.append("availability snapshot times invalid")

    errors.extend(candidate_errors(selection["selected"], registry, "selected model"))
    for fallback in selection["fallbacks"]:
        errors.extend(candidate_errors(fallback, registry, "fallback"))
    candidate_ids = [selection["selected"]["model_ref"], *[item["model_ref"] for item in selection["fallbacks"]]]
    if len(candidate_ids) != len(set(candidate_ids)):
        errors.append("selected/fallback candidates are duplicated")

    observations = selection["availability_snapshot"]["observations"]
    available_pairs = {
        (observation["endpoint_id"], model_ref)
        for observation in observations
        if observation["status"] == "available"
        for model_ref in observation["available_model_refs"]
    }
    selected = selection["selected"]
    if selected["availability_status"] == "available" and (selected["endpoint_id"], selected["model_ref"]) not in available_pairs:
        errors.append("selected model is absent from availability snapshot")
    for fallback in selection["fallbacks"]:
        if fallback["availability_status"] == "available" and (fallback["endpoint_id"], fallback["model_ref"]) not in available_pairs:
            errors.append("fallback is absent from availability snapshot")

    models = {model["model_ref"]: model for model in registry["models"]}
    endpoints = {endpoint["endpoint_id"]: endpoint for endpoint in registry["endpoints"]}
    required = set(selection["request"]["required_capabilities"])
    model = models.get(selected["model_ref"], {})
    endpoint = endpoints.get(selected["endpoint_id"], {})
    if not required <= set(model.get("capabilities", [])) | set(endpoint.get("capabilities", [])):
        errors.append("selected model capability mismatch")
    if selection["request"]["privacy_class"] not in endpoint.get("privacy_classes", []):
        errors.append("selected endpoint privacy mismatch")
    if model.get("promotion_status") == "blocked":
        errors.append("blocked model selected")

    policy = selection["invocation_policy"]
    if policy.get("selection_only") is not True:
        errors.append("selection record cannot execute a model")
    if policy.get("fallback_rule") != "ordered_pinned_candidates_only":
        errors.append("fallback policy drift")
    if policy.get("secret_handling") != "resolve_credential_ref_at_adapter_only":
        errors.append("secret handling boundary drift")
    if not 1 <= policy.get("max_attempts", 0) <= 10:
        errors.append("invocation attempts out of bounds")
    return errors


def set_path(target: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    current: Any = target
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


def check_docs() -> None:
    text = (ROOT / "docs" / "model-selection-access-contract.md").read_text(encoding="utf-8").lower()
    for phrase in (
        "selection and access are different", "does not own", "direct-local embedding", "direct-local asr",
        "availability snapshot", "ordered pinned", "user-global agent-loop safety", "contextforge is unchanged",
        "no model invocation",
    ):
        ensure(phrase in text, f"model contract documentation omits {phrase!r}")


def main() -> int:
    try:
        registry_schema = load("endpoint-registry.schema.json")
        selection_schema = load("selection-record.schema.json")
        registry = load("examples/registry.json")
        selection = load("examples/selection.json")
        ensure(registry_schema["additionalProperties"] is False, "registry root must be strict")
        ensure(selection_schema["additionalProperties"] is False, "selection root must be strict")
        ensure(not registry_errors(registry), f"valid registry rejected: {registry_errors(registry)}")
        ensure(not selection_errors(selection, registry), f"valid selection rejected: {selection_errors(selection, registry)}")
        cases = load("examples/invalid-selections.json")["cases"]
        for case in cases:
            attacked = copy.deepcopy(selection)
            for path, value in case["mutations"].items():
                set_path(attacked, path, value)
            errors = selection_errors(attacked, registry)
            ensure(any(case["expected_error"] in error for error in errors), f"{case['name']}: {errors}")
        check_docs()
    except (AssertionError, KeyError, TypeError, ValueError) as error:
        print(f"Model composition specification validation failed: {error}", file=sys.stderr)
        return 1
    print("Model selection/access v0 specification validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
