#!/usr/bin/env python3
"""Genus-router selection and LiteLLM-only invocation for governance tasks."""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = ROOT / "config" / "model-policy.json"
MAX_GATEWAY_RESPONSE_BYTES = 1_048_576
MAX_MODEL_INPUT_BYTES = 300_000
DECISION_ID = re.compile(r"^d-\d{8}-\d{6}$")
CANONICAL_LITELLM_BASE_URL = "http://172.22.10.160:3333"
STANDARD_MODELS = [
    "codex/gpt-5.6-sol",
    "codex/gpt-5.6-terra",
    "codex/gpt-5.6-luna",
]
ALLOWED_GENERATIVE_MODELS = {*STANDARD_MODELS, "claude-fable-5"}
AGENT_REVIEW_TASK = {
    "task_kind": "review",
    "complexity": "complex",
    "blast_radius": "interface",
    "high_value": False,
    "awaited": True,
}


class ModelRoutingError(RuntimeError):
    pass


def strict_json(value: str | bytes) -> Any:
    def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ModelRoutingError(f"duplicate JSON key: {key}")
            result[key] = item
        return result

    def finite_float(raw: str) -> float:
        parsed = float(raw)
        if not math.isfinite(parsed):
            raise ModelRoutingError("non-finite JSON number")
        return parsed

    try:
        return json.loads(
            value,
            object_pairs_hook=reject_duplicate,
            parse_constant=lambda item: (_ for _ in ()).throw(
                ModelRoutingError(f"invalid JSON constant: {item}")
            ),
            parse_float=finite_float,
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ModelRoutingError("invalid JSON") from error


def load_policy(path: Path | None = None) -> dict[str, Any]:
    configured = path or Path(os.environ.get("NOETIC_MODEL_POLICY", DEFAULT_POLICY_PATH))
    try:
        policy = strict_json(configured.read_bytes())
    except OSError as error:
        raise ModelRoutingError("model policy is unavailable") from error
    if not isinstance(policy, dict) or policy.get("schema_version") != "1":
        raise ModelRoutingError("model policy has an unsupported shape or version")
    validate_policy_invariants(policy)
    return policy


def validate_policy_invariants(policy: dict[str, Any]) -> None:
    selection = _mapping(policy, "selection")
    access = _mapping(policy, "access")
    generative = _mapping(policy, "generative")
    failure = _mapping(policy, "failure")
    fable_eligibility = _mapping(generative, "fable_eligibility")
    tasks = _mapping(policy, "tasks")
    required_lifecycle = ["classify", "route_task", "invoke", "report_outcome"]
    if (
        selection.get("router") != "genus-router"
        or selection.get("mandatory_for_generative_tasks") is not True
        or selection.get("selection_varies_with_sophistication") is not True
        or selection.get("lifecycle") != required_lifecycle
    ):
        raise ModelRoutingError("model policy weakens mandatory genus-router selection")
    if (
        access.get("endpoint_id") != "local-litellm"
        or _required_string(access, "base_url").rstrip("/") != CANONICAL_LITELLM_BASE_URL
        or access.get("token_env") != "LITELLM_API_KEY"
        or access.get("systemd_credential") != "litellm_api_key"
        or access.get("litellm_required") is not True
        or access.get("direct_provider_access") is not False
        or set(_string_list(access, "applies_to_harnesses")) != {"pi", "opencode", "broker", "bare"}
    ):
        raise ModelRoutingError("model policy weakens the canonical LiteLLM boundary")
    if (
        _string_list(generative, "standard_models") != STANDARD_MODELS
        or set(_string_list(generative, "allowed_models")) != ALLOWED_GENERATIVE_MODELS
        or generative.get("capability_tiers")
        != [[STANDARD_MODELS[0], "claude-fable-5"], [STANDARD_MODELS[1]], [STANDARD_MODELS[2]]]
        or generative.get("reasoning_effort") != "high"
        or fable_eligibility.get("limited") is not True
        or set(_string_list(fable_eligibility, "task_kinds")) != {"review", "research", "design"}
        or fable_eligibility.get("minimum_complexity") != "complex"
    ):
        raise ModelRoutingError("model policy weakens the governed generative set")
    if (
        failure.get("report_outcome_required") is not True
        or failure.get("reroute_with_prior_failure") is not True
        or failure.get("exclude_failed_models") is not True
        or failure.get("manual_model_escalation") is not False
    ):
        raise ModelRoutingError("model policy weakens the routed failure lifecycle")
    if _mapping(tasks, "agent_review") != AGENT_REVIEW_TASK:
        raise ModelRoutingError("model policy changed the protected agent-review classification")


def create_router_service() -> Any:
    config_path = os.environ.get("GENUS_ROUTER_CONFIG")
    if not config_path:
        raise ModelRoutingError("GENUS_ROUTER_CONFIG is required")
    try:
        from genus_router.server import create_service
    except ImportError as error:
        raise ModelRoutingError("genus-router is not installed") from error
    try:
        return create_service(config_path)
    except Exception as error:
        raise ModelRoutingError("genus-router configuration failed") from error


def load_litellm_key(policy: dict[str, Any]) -> str:
    access = _mapping(policy, "access")
    token_env = _required_string(access, "token_env")
    value = os.environ.get(token_env)
    if value:
        if any(char.isspace() for char in value):
            raise ModelRoutingError(f"{token_env} credential is invalid")
        return value

    key_file = os.environ.get(f"{token_env}_FILE")
    if key_file:
        candidate = Path(key_file)
    else:
        credential_dir = os.environ.get("CREDENTIALS_DIRECTORY")
        credential_name = _required_string(access, "systemd_credential")
        candidate = Path(credential_dir) / credential_name if credential_dir else None
    if candidate is None:
        raise ModelRoutingError(f"{token_env} credential is unavailable")
    try:
        value = candidate.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise ModelRoutingError(f"{token_env} credential is unavailable") from error
    if not value or any(char.isspace() for char in value):
        raise ModelRoutingError(f"{token_env} credential is invalid")
    os.environ[token_env] = value
    return value


def validate_decision(
    raw: Any,
    policy: dict[str, Any],
    excluded_models: set[str],
) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("error"):
        raise ModelRoutingError("genus-router returned no valid candidate")
    required_fields = {
        "availability",
        "decision_id",
        "effective_complexity",
        "fable_eligible",
        "fallback_refs",
        "fallbacks",
        "genus",
        "genus_code",
        "model",
        "model_ref",
        "rationale",
        "sophistication",
    }
    if set(raw) != required_fields:
        raise ModelRoutingError("genus-router decision fields are incomplete or unknown")
    decision_id = raw.get("decision_id")
    if not isinstance(decision_id, str) or not DECISION_ID.fullmatch(decision_id):
        raise ModelRoutingError("genus-router returned an invalid decision_id")
    model = raw.get("model")
    if not isinstance(model, str) or model not in set(STANDARD_MODELS) or model in excluded_models:
        raise ModelRoutingError("genus-router selected a forbidden or excluded model")
    if (
        raw.get("genus_code") != "REVIEW-COMPLEX"
        or raw.get("effective_complexity") != "complex"
        or raw.get("sophistication") != "complex"
        or raw.get("availability") != "verified"
        or raw.get("fable_eligible") is not False
    ):
        raise ModelRoutingError("genus-router decision does not match protected review classification")
    if not isinstance(raw.get("genus"), str) or not raw["genus"]:
        raise ModelRoutingError("genus-router omitted genus")
    rationale = raw.get("rationale")
    if not isinstance(rationale, list) or not rationale or not all(isinstance(item, str) for item in rationale):
        raise ModelRoutingError("genus-router rationale evidence is invalid")

    model_ref = _validate_model_ref(raw.get("model_ref"), policy, model)
    fallbacks = raw.get("fallbacks")
    fallback_refs = raw.get("fallback_refs")
    if not isinstance(fallbacks, list) or not isinstance(fallback_refs, list):
        raise ModelRoutingError("genus-router fallback evidence is invalid")
    if len(fallbacks) != len(fallback_refs) or len(fallbacks) != len(set(fallbacks)):
        raise ModelRoutingError("genus-router fallback evidence is inconsistent")
    validated_fallbacks = []
    for fallback, fallback_ref in zip(fallbacks, fallback_refs, strict=True):
        if (
            not isinstance(fallback, str)
            or fallback not in set(STANDARD_MODELS)
            or fallback in excluded_models
            or fallback == model
        ):
            raise ModelRoutingError("genus-router returned a forbidden fallback")
        validated_fallbacks.append(_validate_model_ref(fallback_ref, policy, fallback))
    return {
        **raw,
        "model_ref": model_ref,
        "fallback_refs": validated_fallbacks,
    }


def _validate_model_ref(raw: Any, policy: dict[str, Any], expected_model: str) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ModelRoutingError("genus-router model reference is invalid")
    required = {
        "model_id",
        "endpoint_id",
        "upstream_model_id",
        "interface_type",
        "base_url",
        "endpoint_path",
        "token_env",
    }
    allowed_fields = required | {"reasoning_effort"}
    if set(raw) - allowed_fields:
        raise ModelRoutingError("genus-router model reference contains unknown fields")
    if not required <= set(raw) or not all(isinstance(raw[key], str) and raw[key] for key in required):
        raise ModelRoutingError("genus-router model reference is incomplete")

    access = _mapping(policy, "access")
    allowed_models = set(_string_list(_mapping(policy, "generative"), "allowed_models"))
    if expected_model not in allowed_models:
        raise ModelRoutingError("genus-router model reference is not governed")
    if raw["model_id"] != expected_model:
        raise ModelRoutingError("genus-router model reference does not match selection")
    if raw["upstream_model_id"] != expected_model:
        raise ModelRoutingError("genus-router model reference changed the governed model identity")
    if raw["endpoint_id"] != _required_string(access, "endpoint_id"):
        raise ModelRoutingError("genus-router bypassed the required LiteLLM endpoint")
    if raw["base_url"].rstrip("/") != _required_string(access, "base_url").rstrip("/"):
        raise ModelRoutingError("genus-router returned a forbidden base URL")
    if raw["token_env"] != _required_string(access, "token_env"):
        raise ModelRoutingError("genus-router returned a forbidden credential binding")
    if raw["interface_type"] != "openai-compatible":
        raise ModelRoutingError("genus-router returned a forbidden interface type")
    if raw["endpoint_path"] not in set(_string_list(access, "allowed_endpoint_paths")):
        raise ModelRoutingError("genus-router returned a forbidden endpoint path")
    generative_paths = set(
        _string_list(_mapping(policy, "generative"), "allowed_endpoint_paths")
    )
    if raw["endpoint_path"] not in generative_paths:
        raise ModelRoutingError("genus-router returned a non-generative endpoint")

    standard_models = set(_string_list(_mapping(policy, "generative"), "standard_models"))
    reasoning = _required_string(_mapping(policy, "generative"), "reasoning_effort")
    if expected_model in standard_models and raw.get("reasoning_effort") != reasoning:
        raise ModelRoutingError("standard GPT reference does not require high reasoning")
    return {key: value for key, value in raw.items() if isinstance(value, str)}


def route_and_invoke_review(
    prompt: str,
    parse_output: Callable[[str], dict[str, Any]],
    *,
    service: Any | None = None,
    policy: dict[str, Any] | None = None,
    http_post: Callable[[str, dict[str, str], bytes, int], bytes] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(prompt, str) or not prompt:
        raise ModelRoutingError("review prompt must be non-empty")
    if len(prompt.encode("utf-8")) > MAX_MODEL_INPUT_BYTES:
        raise ModelRoutingError("review prompt exceeded its byte limit")
    active_policy = policy or load_policy()
    validate_policy_invariants(active_policy)
    active_service = service or create_router_service()
    api_key = load_litellm_key(active_policy)
    task = dict(AGENT_REVIEW_TASK)
    excluded: list[str] = []
    attempts: list[dict[str, str]] = []

    for _ in STANDARD_MODELS:
        route_input = {
            **task,
            "prior_failure": bool(excluded),
            "exclude_models": list(excluded),
            "task_summary": "Immutable noetic-dev pull-request semantic review",
        }
        decision = validate_decision(
            asyncio.run(active_service.route_task(route_input)),
            active_policy,
            set(excluded),
        )
        decision_id = decision["decision_id"]
        model = decision["model"]
        try:
            output = _invoke_litellm(
                decision,
                prompt,
                active_policy,
                api_key,
                http_post=http_post,
            )
            parsed = parse_output(output)
        except Exception as error:
            _report_outcome(
                active_service,
                decision_id,
                "failure",
                f"{type(error).__name__}: routed review invocation failed",
            )
            excluded.append(model)
            attempts.append({"decision_id": decision_id, "model": model, "outcome": "failure"})
            continue

        _report_outcome(active_service, decision_id, "success", "Review output passed contract validation")
        attempts.append({"decision_id": decision_id, "model": model, "outcome": "success"})
        evidence = {
            "decision_id": decision_id,
            "attempts": attempts,
            "model": model,
            "endpoint_id": decision["model_ref"]["endpoint_id"],
            "endpoint_path": decision["model_ref"]["endpoint_path"],
            "reasoning": _required_string(_mapping(active_policy, "generative"), "reasoning_effort"),
            "genus_code": decision["genus_code"],
            "effective_complexity": decision["effective_complexity"],
            "sophistication": decision["sophistication"],
            "availability": decision["availability"],
            "fallbacks": decision["fallbacks"],
        }
        return parsed, evidence
    raise ModelRoutingError("all routed review candidates failed")


def _report_outcome(service: Any, decision_id: str, outcome: str, notes: str) -> None:
    try:
        result = service.report_outcome(
            {"decision_id": decision_id, "outcome": outcome, "notes": notes[:1_000]}
        )
    except Exception as error:
        raise ModelRoutingError("genus-router outcome reporting failed") from error
    if result != {"recorded": True}:
        raise ModelRoutingError("genus-router did not record the outcome")


def _invoke_litellm(
    decision: dict[str, Any],
    prompt: str,
    policy: dict[str, Any],
    api_key: str,
    *,
    http_post: Callable[[str, dict[str, str], bytes, int], bytes] | None = None,
) -> str:
    validated = validate_decision(decision, policy, set())
    model_ref = validated["model_ref"]
    access = _mapping(policy, "access")
    reasoning = _required_string(_mapping(policy, "generative"), "reasoning_effort")
    endpoint_path = model_ref["endpoint_path"]
    if endpoint_path == "/v1/responses":
        request_body = {
            "model": model_ref["upstream_model_id"],
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                }
            ],
            "reasoning": {"effort": reasoning},
        }
    elif endpoint_path == "/v1/chat/completions":
        request_body = {
            "model": model_ref["upstream_model_id"],
            "messages": [{"role": "user", "content": prompt}],
            "reasoning_effort": reasoning,
        }
    else:
        raise ModelRoutingError("model endpoint is not generative")

    url = _required_string(access, "base_url").rstrip("/") + endpoint_path
    body = json.dumps(request_body, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    sender = http_post or _http_post
    response = strict_json(sender(url, headers, body, 900))
    return _extract_output(response, endpoint_path)


def _http_post(url: str, headers: dict[str, str], body: bytes, timeout: int) -> bytes:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            result = response.read(MAX_GATEWAY_RESPONSE_BYTES + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        raise ModelRoutingError("LiteLLM invocation failed") from error
    if len(result) > MAX_GATEWAY_RESPONSE_BYTES:
        raise ModelRoutingError("LiteLLM response exceeded its byte limit")
    return result


def _extract_output(response: Any, endpoint_path: str) -> str:
    if not isinstance(response, dict):
        raise ModelRoutingError("LiteLLM response must be an object")
    if endpoint_path == "/v1/chat/completions":
        choices = response.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise ModelRoutingError("LiteLLM chat response choices are invalid")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content:
            raise ModelRoutingError("LiteLLM chat response content is invalid")
        return content

    direct = response.get("output_text")
    if isinstance(direct, str) and direct:
        return direct
    output = response.get("output")
    texts: list[str] = []
    if isinstance(output, list):
        for item in output:
            content = item.get("content") if isinstance(item, dict) else None
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, dict) and part.get("type") == "output_text":
                    text = part.get("text")
                    if isinstance(text, str) and text:
                        texts.append(text)
    if len(texts) != 1:
        raise ModelRoutingError("LiteLLM responses output is invalid")
    return texts[0]


def _mapping(value: dict[str, Any], key: str) -> dict[str, Any]:
    result = value.get(key)
    if not isinstance(result, dict):
        raise ModelRoutingError(f"model policy field {key} must be an object")
    return result


def _required_string(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ModelRoutingError(f"model policy field {key} must be a non-empty string")
    return result


def _string_list(value: dict[str, Any], key: str) -> list[str]:
    result = value.get(key)
    if not isinstance(result, list) or not result or not all(
        isinstance(item, str) and item for item in result
    ):
        raise ModelRoutingError(f"model policy field {key} must be a non-empty string list")
    return list(result)
