#!/usr/bin/env python3
"""Dependency-free validation for noetic.event/v0 contracts and fixtures."""

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
SPEC = ROOT / "spec" / "events" / "v0"
CONTROLLER = ROOT / "spec" / "controller" / "v0"
EVENT_ID = re.compile(r"^evt_[a-z0-9][a-z0-9_-]{7,127}$")
EVENT_TYPE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
LOWER_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
SENSITIVE_KEY = re.compile(
    r"(^|_)(password|secret|token|credential|full_prompt|private_artifact|critical_contact|phone_number)($|_)"
)
SECRET_VALUE_PATTERNS = [
    re.compile(r"Bearer\s+\S+", re.I),
    re.compile(r"(?:sk-|xai-|hf_|tgp_v1_)[A-Za-z0-9_-]{8,}"),
    re.compile(r"AIza[A-Za-z0-9_-]{8,}"),
    re.compile(r"eyJ[A-Za-z0-9_.-]{24,}"),
    re.compile(r"[a-z][a-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@", re.I),
]
PHASE_OPERATIONS = {"p1": "attending", "p2": "understanding", "p3": "judging", "p4": "deciding"}


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot load {path.relative_to(ROOT)}: {error}") from error


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical_digest(event: dict[str, Any]) -> str:
    encoded = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def parse_time(value: Any, field: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str):
        errors.append(f"{field} must be a timestamp")
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} must be RFC 3339")
        return None


def privacy_errors(value: Any, path: str = "payload") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if not LOWER_KEY.fullmatch(key):
                errors.append(f"{path} key must be lower_snake_case: {key}")
            if SENSITIVE_KEY.search(key):
                errors.append(f"{path} contains forbidden sensitive key: {key}")
            errors.extend(privacy_errors(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(privacy_errors(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                errors.append(f"{path} contains secret-shaped value")
                break
    return errors


def event_errors(
    event: dict[str, Any], schema: dict[str, Any], matrix: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    required = set(schema["required"])
    properties = set(schema["properties"])
    missing = sorted(required - event.keys())
    unknown = sorted(event.keys() - properties)
    errors.extend(f"missing required field: {field}" for field in missing)
    errors.extend(f"unknown event field: {field}" for field in unknown)
    if missing:
        return errors

    if event["schema_version"] != "noetic.event/v0":
        errors.append("unsupported event schema version")
    if not isinstance(event["event_id"], str) or not EVENT_ID.fullmatch(event["event_id"]):
        errors.append("invalid event_id")
    if not isinstance(event["event_type"], str) or not EVENT_TYPE.fullmatch(event["event_type"]):
        errors.append("invalid event_type")
    event_class = event["event_class"]
    classes = matrix["classes"]
    if event_class not in classes:
        errors.append("unknown event class")
        return errors
    policy = classes[event_class]
    if not any(event["event_type"].startswith(prefix) for prefix in policy["event_type_prefixes"]):
        errors.append("event type prefix is not allowed for event class")

    actor = event["actor"]
    authority = event["authority"]
    if set(actor) != {"actor_type", "actor_id"}:
        errors.append("actor shape is invalid")
    elif actor["actor_type"] not in policy["actor_types"]:
        errors.append("actor type is not allowed for event class")
    if set(authority) != {"authority_ref", "assertion_scope"}:
        errors.append("authority shape is invalid")
    elif authority["assertion_scope"] not in policy["assertion_scopes"]:
        errors.append("assertion scope is not allowed for event class")

    cognition = event["cognition"]
    presence = policy["cognition"]
    if presence == "required" and not isinstance(cognition, dict):
        errors.append("cognition is required for event class")
    if presence == "forbidden" and cognition is not None:
        errors.append("cognition is forbidden for event class")
    if event_class == "cognition_report" and authority.get("assertion_scope") != "reported":
        errors.append("cognition_report requires reported assertion scope")
    if event_class == "domain_transition":
        if actor.get("actor_type") != "controller" or authority.get("assertion_scope") != "enacted":
            errors.append("domain_transition requires enacted controller authority")
        if not authority.get("authority_ref"):
            errors.append("domain_transition requires authority_ref")
    if event_class == "diagnostic":
        if authority.get("authority_ref") is not None or authority.get("assertion_scope") != "diagnostic":
            errors.append("diagnostic must be non-authoritative")

    if isinstance(cognition, dict):
        expected_cognition = {
            "phase", "operation", "modality", "cycle_id", "iteration", "recursion_depth",
            "governing_purpose_ref", "parent_operation_event_id",
        }
        if set(cognition) != expected_cognition:
            errors.append("cognition shape is invalid")
        phase = cognition.get("phase")
        if phase not in PHASE_OPERATIONS or cognition.get("operation") != PHASE_OPERATIONS.get(phase):
            errors.append("cognitive phase/operation mismatch")
        elif event_class == "cognition_report":
            expected_type = f"cognition.{phase}_{cognition['operation']}"
            if event["event_type"] != expected_type:
                errors.append("cognition event_type does not match phase/operation")
        if cognition.get("modality") not in {"sought", "enacted"}:
            errors.append("invalid cognition modality")
        if not isinstance(cognition.get("iteration"), int) or cognition["iteration"] < 1:
            errors.append("invalid cognition iteration")
        if not isinstance(cognition.get("recursion_depth"), int) or cognition["recursion_depth"] < 0:
            errors.append("invalid cognition recursion_depth")
        if not cognition.get("governing_purpose_ref"):
            errors.append("cognition requires governing_purpose_ref")

    privacy = event["privacy"]
    if set(privacy) != {"classification", "redaction_status", "policy_version"}:
        errors.append("privacy shape is invalid")
    elif privacy["classification"] == "sensitive_reference":
        if privacy["redaction_status"] != "passed":
            errors.append("sensitive_reference requires passed redaction")
        if not event["evidence_refs"]:
            errors.append("sensitive_reference requires an opaque evidence_ref")
    errors.extend(privacy_errors(event["payload"]))

    refs = event["evidence_refs"]
    if not isinstance(refs, list) or len(refs) > 64:
        errors.append("evidence_refs must be a bounded array")
    else:
        ref_ids: set[str] = set()
        for ref in refs:
            if set(ref) != {"ref_id", "kind", "relation", "digest", "access_classification"}:
                errors.append("evidence_ref shape is invalid")
                continue
            if ref["ref_id"] in ref_ids:
                errors.append("duplicate evidence ref_id")
            ref_ids.add(ref["ref_id"])
            if not DIGEST.fullmatch(ref["digest"]):
                errors.append("invalid evidence digest")

    if not isinstance(event["stream_position"], int) or event["stream_position"] < 1:
        errors.append("invalid stream_position")
    occurred = parse_time(event["occurred_at"], "occurred_at", errors)
    recorded = parse_time(event["recorded_at"], "recorded_at", errors)
    if occurred and recorded and recorded < occurred:
        errors.append("recorded_at precedes occurred_at")
    return errors


def set_path(target: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    current: Any = target
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


def check_schema_and_matrix(schema: dict[str, Any], matrix: dict[str, Any]) -> None:
    ensure(schema["$schema"] == "https://json-schema.org/draft/2020-12/schema", "event schema draft drift")
    ensure(schema["$id"].endswith("/spec/events/v0/cognitional-event.schema.json"), "event schema $id drift")
    ensure(schema["type"] == "object" and schema["additionalProperties"] is False, "event root must be strict")
    ensure(len(schema["required"]) == len(set(schema["required"])), "duplicate required event field")
    classes = set(schema["properties"]["event_class"]["enum"])
    ensure(classes == set(matrix["classes"]), "event schema/class matrix drift")
    ensure(matrix["schema_version"] == "noetic.event-class-matrix/v0", "matrix version drift")
    for name, policy in matrix["classes"].items():
        ensure(policy["event_type_prefixes"], f"{name}: no event prefixes")
        ensure(policy["actor_types"], f"{name}: no actors")
        ensure(policy["assertion_scopes"], f"{name}: no assertion scopes")
        ensure(policy["cognition"] in {"required", "optional", "forbidden"}, f"{name}: cognition policy")
    ensure(matrix["classes"]["domain_transition"]["actor_types"] == ["controller"], "domain authority broadened")
    ensure(matrix["classes"]["cognition_report"]["assertion_scopes"] == ["reported"], "semantic report authority broadened")

    schema_text = json.dumps(schema, sort_keys=True)
    for phase, operation in PHASE_OPERATIONS.items():
        ensure(f'"const": "{phase}"' in schema_text and f'"const": "{operation}"' in schema_text, f"missing {phase} pairing")


def check_examples(schema: dict[str, Any], matrix: dict[str, Any]) -> None:
    valid_names = ["valid-p1-event.json", "valid-p4-event.json", "valid-domain-event.json"]
    for name in valid_names:
        event = load(SPEC / "examples" / name)
        errors = event_errors(event, schema, matrix)
        ensure(not errors, f"{name}: {errors}")

    cases = load(SPEC / "examples" / "invalid-events.json")["cases"]
    ensure(len(cases) == len({case["name"] for case in cases}), "duplicate invalid-event case")
    for case in cases:
        event = copy.deepcopy(load(SPEC / "examples" / case["base"]))
        for path, value in case["mutations"].items():
            set_path(event, path, value)
        errors = event_errors(event, schema, matrix)
        ensure(
            any(case["expected_error"] in error for error in errors),
            f"{case['name']}: expected {case['expected_error']!r}, got {errors}",
        )


def receipt_errors(receipt: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = set(schema["required"])
    properties = set(schema["properties"])
    if set(receipt) != required or required != properties:
        errors.append("receipt shape is invalid")
        return errors
    if receipt["schema_version"] != "noetic.event-sink-receipt/v0":
        errors.append("receipt version is invalid")
    if not EVENT_ID.fullmatch(receipt["event_id"]):
        errors.append("receipt event_id is invalid")
    if receipt["sink_type"] not in {"direct", "contextforge"}:
        errors.append("receipt sink_type is invalid")
    if receipt["status"] not in {"accepted", "duplicate", "rejected"}:
        errors.append("receipt status is invalid")
    if not DIGEST.fullmatch(receipt["canonical_digest"]):
        errors.append("receipt digest is invalid")
    if receipt["status"] in {"accepted", "duplicate"} and (not receipt["sink_receipt_ref"] or not receipt["accepted_at"]):
        errors.append("accepted receipt lacks sink evidence")
    if receipt["status"] == "rejected" and (receipt["sink_receipt_ref"] is not None or receipt["accepted_at"] is not None):
        errors.append("rejected receipt claims acceptance")
    return errors


def check_sink_parity(event_schema: dict[str, Any], matrix: dict[str, Any]) -> None:
    receipt_schema = load(SPEC / "sink-receipt.schema.json")
    fixture = load(SPEC / "examples" / "sink-parity.json")
    source = load(SPEC / "examples" / fixture["source_event"])
    ensure(not event_errors(source, event_schema, matrix), "parity source event is invalid")
    digest = canonical_digest(source)
    ensure(fixture["canonical_digest"] == digest, "parity canonical digest drift")
    ensure(set(fixture["required_semantic_fields"]) == set(event_schema["required"]), "parity semantic field drift")
    receipts = fixture["receipts"]
    ensure({receipt["sink_type"] for receipt in receipts} == {"direct", "contextforge"}, "sink parity lacks a profile")
    for receipt in receipts:
        ensure(not receipt_errors(receipt, receipt_schema), f"invalid sink receipt: {receipt_errors(receipt, receipt_schema)}")
        ensure(receipt["event_id"] == source["event_id"], "sink changed event identity")
        ensure(receipt["canonical_digest"] == digest, "sink changed canonical semantics")


def check_controller_compatibility(matrix: dict[str, Any]) -> None:
    command_schema = load(CONTROLLER / "command-envelope.schema.json")
    transitions = load(CONTROLLER / "transition-tables.json")
    aggregate_names = set(command_schema["properties"]["aggregate_type"]["enum"])
    prefixes = {prefix.removesuffix(".") for prefix in matrix["classes"]["domain_transition"]["event_type_prefixes"]}
    ensure(prefixes == aggregate_names == set(transitions["aggregates"]), "controller/canonical domain aggregate drift")
    controller_events = {
        transition["event"]
        for table in transitions["aggregates"].values()
        for transition in table["transitions"]
    }
    ensure("run.started" in controller_events, "domain fixture event absent from controller contract")


def check_docs() -> None:
    contract = (ROOT / "docs" / "cognitional-event-contract.md").read_text(encoding="utf-8").lower()
    required = [
        "does not mean", "p4 governance", "opaque", "contextforge", "identical canonical bytes",
        "unsupported major", "no sink or ui implementation", "reported a judgment",
    ]
    for phrase in required:
        ensure(phrase in contract, f"contract documentation omits {phrase!r}")


def main() -> int:
    try:
        schema = load(SPEC / "cognitional-event.schema.json")
        matrix = load(SPEC / "event-class-matrix.json")
        check_schema_and_matrix(schema, matrix)
        check_examples(schema, matrix)
        check_sink_parity(schema, matrix)
        check_controller_compatibility(matrix)
        check_docs()
    except (AssertionError, KeyError, TypeError, ValueError) as error:
        print(f"Cognitional event specification validation failed: {error}", file=sys.stderr)
        return 1
    print("Cognitional event v0 specification validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
