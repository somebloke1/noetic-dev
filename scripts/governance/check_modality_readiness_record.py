#!/usr/bin/env python3
"""Validate one persisted modality readiness evidence record.

This checker validates evidence shape and binding only. It does not claim that
embedding or ASR runtime adapters are ready.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from json_schema import DuplicateKeyError, load_json_strict, validate_schema  # noqa: E402

EXPECTED_ENDPOINT_PATH = {
    "asr": "/v1/audio/transcriptions",
    "embed": "/v1/embeddings",
}


def _load_repo_json(relative: str) -> dict[str, Any]:
    data = load_json_strict(REPO_ROOT / relative)
    if not isinstance(data, dict):
        raise ValueError(f"{relative} must contain a JSON object")
    return data


def check(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema = _load_repo_json("governance/schemas/modality-readiness-record.schema.json")
    errors.extend(f"schema: {error}" for error in validate_schema(record, schema))
    if errors:
        return errors

    policy = _load_repo_json("config/model-policy.json")
    modality = record["modality"]
    expected_model = policy.get("modalities", {}).get(modality)
    expected_path = EXPECTED_ENDPOINT_PATH[modality]

    if record["model"] != expected_model:
        errors.append(f"record.model must match config/model-policy.json modalities.{modality}")
    if expected_path not in policy.get("access", {}).get("allowed_endpoint_paths", []):
        errors.append(f"model policy does not allow endpoint path {expected_path}")
    if record["endpoint"]["path"] != expected_path:
        errors.append(f"endpoint.path must be {expected_path} for modality {modality}")

    route = record["route_decision"]
    probe = record["readiness_probe"]
    outcome = record["report_outcome"]
    for label, item in [("route_decision", route), ("readiness_probe", probe)]:
        if item["model"] != record["model"]:
            errors.append(f"{label}.model must match record.model")
        if item["endpoint_id"] != record["endpoint"]["id"]:
            errors.append(f"{label}.endpoint_id must match endpoint.id")
        if item["endpoint_path"] != record["endpoint"]["path"]:
            errors.append(f"{label}.endpoint_path must match endpoint.path")

    if outcome["decision_id"] != route["decision_id"]:
        errors.append("report_outcome.decision_id must match route_decision.decision_id")
    if probe["latency_ms"] <= 0:
        errors.append("readiness_probe.latency_ms must be positive")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_modality_readiness_record.py <record.json>", file=sys.stderr)
        return 2
    try:
        record = load_json_strict(argv[1])
    except (OSError, ValueError, DuplicateKeyError) as exc:
        print(f"failed to load record: {exc}", file=sys.stderr)
        return 1
    if not isinstance(record, dict):
        print("record must be a JSON object", file=sys.stderr)
        return 1
    errors = check(record)
    if errors:
        print("Modality readiness record validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Modality readiness record validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
