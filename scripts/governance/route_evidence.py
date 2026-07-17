#!/usr/bin/env python3
"""Validate protected genus-router/LiteLLM route evidence.

This is a deterministic evidence contract only; it does not perform routing or
change broker runtime behavior.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from json_schema import load_json_strict, validate_schema

REPO_ROOT = Path(__file__).resolve().parents[2]
GENUS_ROUTER_SHA = "f2b839b0cfc737c4c1f0a46d3d519d414529545c"
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


def validate_route_decision(decision: Any, excluded_models: list[str]) -> list[str]:
    if not isinstance(excluded_models, list) or any(type(model) is not str for model in excluded_models):
        return ["excluded model list is invalid"]
    if len(excluded_models) != len(set(excluded_models)) or any(
        model not in PROTECTED_REVIEW_CANDIDATES for model in excluded_models
    ):
        return ["excluded model list is inconsistent"]
    errors: list[str] = []
    policy = load_json_strict(REPO_ROOT / "config" / "model-policy.json")
    remaining = [model for model in PROTECTED_REVIEW_CANDIDATES if model not in excluded_models]
    _validate_decision(
        decision,
        remaining,
        policy.get("access", {}),
        policy.get("generative", {}),
        set(),
        "external route",
        errors,
    )
    return errors


def validate_route_evidence(evidence: Any, contract_name: str = "protected_review") -> list[str]:
    if contract_name != "protected_review":
        return [f"unknown route contract: {contract_name}"]
    errors: list[str] = []
    schema = load_json_strict(REPO_ROOT / "governance" / "schemas" / "route-evidence.schema.json")
    errors.extend(f"schema: {error}" for error in validate_schema(evidence, schema))
    if errors:
        return errors
    if evidence["component_sha"] != GENUS_ROUTER_SHA:
        return ["protected_review component SHA is not canonical"]
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
    if "decision" not in final_attempt and len(attempts) != len(PROTECTED_REVIEW_CANDIDATES):
        errors.append("protected_review terminal rejection must exhaust all routed candidates")
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate retained protected route evidence")
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-f0-9]{40}", args.head_sha):
        parser.error("--head-sha must be a full lowercase SHA-1")
    try:
        with tempfile.TemporaryDirectory() as directory:
            evidence_path = download_protected_evidence(args.run_id, args.pr_number, args.head_sha, Path(directory))
            payload = load_json_strict(evidence_path)
    except (OSError, ValueError) as error:
        print(f"protected route evidence is unavailable: {error}", file=sys.stderr)
        return 1
    if (
        type(payload) is not dict
        or payload.get("repository") != "somebloke1/noetic-dev"
        or payload.get("pr_number") != args.pr_number
        or payload.get("head_sha") != args.head_sha
        or not isinstance(payload.get("base_sha"), str)
        or not re.fullmatch(r"[a-f0-9]{40}", payload["base_sha"])
        or payload["base_sha"] == args.head_sha
        or type(payload.get("route_evidence")) is not dict
    ):
        print("route evidence wrapper does not match the candidate SHA", file=sys.stderr)
        return 1
    provenance_errors = validate_protected_provenance(
        args.run_id, args.pr_number, args.head_sha, payload["base_sha"]
    )
    if provenance_errors:
        print(json.dumps(provenance_errors, ensure_ascii=True), file=sys.stderr)
        return 1
    errors = validate_route_evidence(payload["route_evidence"])
    if errors:
        print(json.dumps(errors, ensure_ascii=True), file=sys.stderr)
        return 1
    print("Protected route evidence is valid")
    return 0


def download_protected_evidence(run_id: int, pr_number: int, head_sha: str, directory: Path) -> Path:
    artifact_name = f"agent-review-{pr_number}-{head_sha}"
    result = subprocess.run(
        [
            "gh", "run", "download", str(run_id), "--repo", "somebloke1/noetic-dev",
            "--name", artifact_name, "--dir", str(directory),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=60,
        check=False,
    )
    if result.returncode != 0 or len(result.stdout) > 65_536:
        raise ValueError("exact-SHA Agent Review artifact download failed")
    evidence_path = directory / "agent-review-result.json"
    if not evidence_path.is_file():
        raise ValueError("Agent Review artifact does not contain route evidence")
    return evidence_path


def validate_protected_provenance(run_id: int, pr_number: int, head_sha: str, base_sha: str) -> list[str]:
    if not 1 <= run_id <= 9_223_372_036_854_775_807 or not 1 <= pr_number <= 2_147_483_647:
        return ["protected run or PR identifier is invalid"]

    def gh_json(path: str) -> Any:
        result = subprocess.run(
            ["gh", "api", path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
        if result.returncode != 0 or len(result.stdout) > 1_048_576:
            raise ValueError("GitHub provenance query failed")
        return json.loads(result.stdout)

    try:
        run = gh_json(f"repos/somebloke1/noetic-dev/actions/runs/{run_id}")
        artifacts = gh_json(f"repos/somebloke1/noetic-dev/actions/runs/{run_id}/artifacts")
    except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return ["protected run provenance is unavailable"]
    pull_requests = run.get("pull_requests") if isinstance(run, dict) else None
    if (
        run.get("id") != run_id
        or run.get("name") != "Agent Review"
        or run.get("path") != ".github/workflows/agent-review.yml"
        or run.get("event") != "pull_request_target"
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or run.get("head_sha") not in {head_sha, base_sha}
        or not isinstance(run.get("repository"), dict)
        or run["repository"].get("full_name") != "somebloke1/noetic-dev"
        or not isinstance(pull_requests, list)
        or not any(
            isinstance(item, dict)
            and item.get("number") == pr_number
            and isinstance(item.get("head"), dict)
            and item["head"].get("sha") == head_sha
            and isinstance(item["head"].get("repo"), dict)
            and item["head"]["repo"].get("url") == "https://api.github.com/repos/somebloke1/noetic-dev"
            and isinstance(item.get("base"), dict)
            and item["base"].get("ref") == "dev"
            and item["base"].get("sha") == base_sha
            and isinstance(item["base"].get("repo"), dict)
            and item["base"]["repo"].get("url") == "https://api.github.com/repos/somebloke1/noetic-dev"
            for item in pull_requests
        )
    ):
        return ["GitHub run does not match the protected Agent Review candidate"]
    expected_name = f"agent-review-{pr_number}-{head_sha}"
    listed = artifacts.get("artifacts") if isinstance(artifacts, dict) else None
    if not isinstance(listed, list) or not any(
        isinstance(item, dict) and item.get("name") == expected_name and item.get("expired") is False
        for item in listed
    ):
        return ["exact-SHA Agent Review artifact is unavailable or expired"]
    return []


if __name__ == "__main__":
    raise SystemExit(main())
