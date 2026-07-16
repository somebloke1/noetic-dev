#!/usr/bin/env python3
"""Pure, provider-free validation and projection for the frozen M0 trace."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class StrictJSONError(ValueError):
    """Raised when input is outside the strict JSON subset used by M0."""


class TraceValidationError(ValueError):
    """Raised when a trace violates the frozen M0 contract."""


def _reject_float(value: str) -> None:
    raise StrictJSONError(f"floating-point numbers are not supported: {value}")


def _reject_constant(value: str) -> None:
    raise StrictJSONError(f"non-finite numbers are not supported: {value}")


def _object_without_duplicates(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJSONError(f"duplicate object key: {key}")
        result[key] = value
    return result


def _reject_unsupported_values(value: Any, path: str = "$") -> None:
    if value is None:
        raise StrictJSONError(f"{path}: null is not supported")
    if isinstance(value, float):
        raise StrictJSONError(f"{path}: floating-point numbers are not supported")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_unsupported_values(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            _reject_unsupported_values(item, f"{path}.{key}")


def strict_json_loads(text: str) -> Any:
    """Parse strict JSON, rejecting duplicate keys, floats, constants, and nulls."""
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise StrictJSONError(f"invalid JSON: {exc}") from exc
    _reject_unsupported_values(value)
    return value


def load_json_strict(path: str | Path) -> Any:
    """Load a UTF-8 file through the M0 strict JSON parser."""
    return strict_json_loads(Path(path).read_text(encoding="utf-8"))


def canonical_json_bytes(value: Any) -> bytes:
    """Return the one canonical byte representation used by M0."""
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def _fail(path: str, message: str) -> None:
    raise TraceValidationError(f"{path}: {message}")


def _object(value: Any, path: str) -> dict[str, Any]:
    if type(value) is not dict:
        _fail(path, "expected object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if type(value) is not list:
        _fail(path, "expected array")
    return value


def _string(value: Any, path: str) -> str:
    if type(value) is not str:
        _fail(path, "expected string")
    return value


def _integer(value: Any, path: str) -> int:
    if type(value) is not int:
        _fail(path, "expected integer (booleans are not integers)")
    return value


def _shape(value: Any, fields: tuple[str, ...], path: str) -> dict[str, Any]:
    obj = _object(value, path)
    expected = set(fields)
    actual = set(obj)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing:
        _fail(path, f"missing fields: {', '.join(missing)}")
    if unknown:
        _fail(path, f"unknown fields: {', '.join(unknown)}")
    return obj


def _exact(value: Any, expected: Any, path: str) -> None:
    if type(value) is not type(expected) or value != expected:
        _fail(path, f"expected {expected!r}")


def _identifier(value: Any, prefix: str, path: str) -> str:
    text = _string(value, path)
    pattern = rf"{re.escape(prefix)}-[a-z0-9]+(?:-[a-z0-9]+)*"
    if re.fullmatch(pattern, text) is None:
        _fail(path, f"malformed {prefix} identifier")
    return text


def _numbered_identifier(value: Any, prefix: str, path: str) -> str:
    text = _string(value, path)
    if re.fullmatch(rf"{re.escape(prefix)}-[1-9][0-9]*", text) is None:
        _fail(path, f"malformed {prefix} identifier")
    return text


def _digest(value: Any, path: str) -> str:
    text = _string(value, path)
    if re.fullmatch(r"sha256:[0-9a-f]{64}", text) is None:
        _fail(path, "expected a lowercase sha256 digest")
    return text


def _timestamp(value: Any, path: str) -> datetime:
    text = _string(value, path)
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", text) is None:
        _fail(path, "expected an RFC 3339 UTC timestamp at whole-second precision")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        _fail(path, f"invalid UTC timestamp: {exc}")
    return parsed.replace(tzinfo=timezone.utc)


def _binding(value: Any, path: str) -> dict[str, Any]:
    binding = _shape(
        value,
        (
            "delegation_id",
            "delegation_digest",
            "goal_chain_id",
            "sub_goal_id",
            "program_id",
            "run_id",
            "generation",
            "correlation_id",
        ),
        path,
    )
    _identifier(binding["delegation_id"], "delegation", f"{path}.delegation_id")
    _digest(binding["delegation_digest"], f"{path}.delegation_digest")
    _numbered_identifier(binding["goal_chain_id"], "chain", f"{path}.goal_chain_id")
    _numbered_identifier(binding["sub_goal_id"], "subgoal", f"{path}.sub_goal_id")
    _identifier(binding["program_id"], "program", f"{path}.program_id")
    _identifier(binding["run_id"], "run", f"{path}.run_id")
    _exact(_integer(binding["generation"], f"{path}.generation"), 1, f"{path}.generation")
    _identifier(binding["correlation_id"], "correlation", f"{path}.correlation_id")
    return binding


def _actor(value: Any, path: str) -> dict[str, str]:
    actor = _shape(value, ("role", "actor_id"), path)
    role = _string(actor["role"], f"{path}.role")
    if role not in ("telos", "controller", "implementer", "qa"):
        _fail(f"{path}.role", "unknown actor role")
    _identifier(actor["actor_id"], "actor", f"{path}.actor_id")
    return actor


def _operation(payload: dict[str, Any], expected: str, path: str) -> None:
    _exact(_string(payload["operation"], f"{path}.operation"), expected, f"{path}.operation")


def _authority_entry(
    value: Any,
    expected_actions: tuple[str, ...],
    path: str,
) -> dict[str, Any]:
    entry = _shape(value, ("actor_id", "actions"), path)
    _identifier(entry["actor_id"], "actor", f"{path}.actor_id")
    actions = _array(entry["actions"], f"{path}.actions")
    for index, action in enumerate(actions):
        _string(action, f"{path}.actions[{index}]")
    if tuple(actions) != expected_actions:
        _fail(f"{path}.actions", f"expected exactly {list(expected_actions)!r}")
    return entry


def _delegation_payload(value: Any, path: str) -> dict[str, Any]:
    payload = _shape(
        value,
        (
            "operation",
            "purpose",
            "authorized_at",
            "valid_from",
            "expires_at",
            "revocation_status",
            "authority",
        ),
        path,
    )
    _operation(payload, "authorize_delegation", path)
    _identifier(payload["purpose"], "purpose", f"{path}.purpose")
    authorized_at = _timestamp(payload["authorized_at"], f"{path}.authorized_at")
    valid_from = _timestamp(payload["valid_from"], f"{path}.valid_from")
    expires_at = _timestamp(payload["expires_at"], f"{path}.expires_at")
    if not valid_from <= authorized_at < expires_at:
        _fail(path, "delegation validity interval does not contain authorization")
    _exact(
        _string(payload["revocation_status"], f"{path}.revocation_status"),
        "not_revoked",
        f"{path}.revocation_status",
    )

    authority = _shape(
        payload["authority"],
        ("telos", "controller", "implementer", "qa"),
        f"{path}.authority",
    )
    expected = (
        (
            "telos",
            ("telos.sub_goal.adjudicated",),
        ),
        (
            "controller",
            (
                "controller.run.created",
                "controller.run.started",
                "controller.implementation_generation.accepted",
                "controller.run.succeeded",
                "controller.result.reported",
            ),
        ),
        ("implementer", ()),
        ("qa", ("qa.verification.adjudicated",)),
    )
    actor_ids: list[str] = []
    for role, actions in expected:
        entry = _authority_entry(authority[role], actions, f"{path}.authority.{role}")
        actor_ids.append(entry["actor_id"])
    if len(set(actor_ids)) != len(actor_ids):
        _fail(f"{path}.authority", "all delegated actor identities must be distinct")
    return payload


def compute_delegation_digest(record: dict[str, Any]) -> str:
    """Compute the digest over all delegation authority and identity material."""
    binding = record["binding"]
    material = {
        "schema_version": record["schema_version"],
        "event_id": record["event_id"],
        "event_type": record["event_type"],
        "occurred_at": record["occurred_at"],
        "actor": record["actor"],
        "delegation_identity": {
            "delegation_id": binding["delegation_id"],
            "goal_chain_id": binding["goal_chain_id"],
            "sub_goal_id": binding["sub_goal_id"],
            "program_id": binding["program_id"],
            "run_id": binding["run_id"],
            "generation": binding["generation"],
            "correlation_id": binding["correlation_id"],
        },
        "delegation": record["payload"],
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(material)).hexdigest()


def _validate_record_payload(
    record: dict[str, Any],
    accepted: dict[str, Any] | None,
    qa_record: dict[str, Any] | None,
    success_record: dict[str, Any] | None,
    result_record: dict[str, Any] | None,
    path: str,
) -> None:
    event_type = record["event_type"]
    value = record["payload"]
    if event_type == "telos.delegation.authorized":
        _delegation_payload(value, f"{path}.payload")
        return

    if event_type == "controller.run.created":
        payload = _shape(value, ("operation",), f"{path}.payload")
        _operation(payload, "create_run", f"{path}.payload")
        return

    if event_type == "controller.run.started":
        payload = _shape(value, ("operation",), f"{path}.payload")
        _operation(payload, "start_run", f"{path}.payload")
        return

    if event_type == "controller.implementation_generation.accepted":
        payload = _shape(
            value,
            (
                "operation",
                "candidate_id",
                "candidate_digest",
                "implementer_actor_id",
                "verification_obligation_id",
            ),
            f"{path}.payload",
        )
        _operation(payload, "accept_implementation_generation", f"{path}.payload")
        _identifier(payload["candidate_id"], "candidate", f"{path}.payload.candidate_id")
        _digest(payload["candidate_digest"], f"{path}.payload.candidate_digest")
        _identifier(payload["implementer_actor_id"], "actor", f"{path}.payload.implementer_actor_id")
        _identifier(
            payload["verification_obligation_id"],
            "obligation",
            f"{path}.payload.verification_obligation_id",
        )
        return

    if accepted is None:
        _fail(path, "accepted generation must precede dependent evidence")
    accepted_payload = accepted["payload"]

    if event_type == "qa.verification.adjudicated":
        payload = _shape(
            value,
            (
                "operation",
                "accepted_event_id",
                "candidate_id",
                "candidate_digest",
                "verification_obligation_id",
                "conclusion",
            ),
            f"{path}.payload",
        )
        _operation(payload, "adjudicate_verification", f"{path}.payload")
        _exact(payload["accepted_event_id"], accepted["event_id"], f"{path}.payload.accepted_event_id")
        for field in ("candidate_id", "candidate_digest", "verification_obligation_id"):
            _exact(payload[field], accepted_payload[field], f"{path}.payload.{field}")
        _exact(_string(payload["conclusion"], f"{path}.payload.conclusion"), "PASS", f"{path}.payload.conclusion")
        return

    if qa_record is None:
        _fail(path, "exactly one QA PASS must precede controller success")
    qa_payload = qa_record["payload"]

    if event_type == "controller.run.succeeded":
        payload = _shape(
            value,
            (
                "operation",
                "accepted_event_id",
                "qa_event_id",
                "candidate_id",
                "candidate_digest",
                "verification_obligation_id",
                "qa_conclusion",
            ),
            f"{path}.payload",
        )
        _operation(payload, "succeed_run", f"{path}.payload")
        _exact(payload["accepted_event_id"], accepted["event_id"], f"{path}.payload.accepted_event_id")
        _exact(payload["qa_event_id"], qa_record["event_id"], f"{path}.payload.qa_event_id")
        for field in ("candidate_id", "candidate_digest", "verification_obligation_id"):
            _exact(payload[field], accepted_payload[field], f"{path}.payload.{field}")
        _exact(payload["qa_conclusion"], qa_payload["conclusion"], f"{path}.payload.qa_conclusion")
        return

    if success_record is None:
        _fail(path, "controller success must precede result reporting")

    if event_type == "controller.result.reported":
        payload = _shape(
            value,
            (
                "operation",
                "result_id",
                "accepted_event_id",
                "qa_event_id",
                "success_event_id",
                "candidate_id",
                "candidate_digest",
                "verification_obligation_id",
                "run_outcome",
                "evidence_event_ids",
            ),
            f"{path}.payload",
        )
        _operation(payload, "report_result", f"{path}.payload")
        _identifier(payload["result_id"], "result", f"{path}.payload.result_id")
        _exact(payload["accepted_event_id"], accepted["event_id"], f"{path}.payload.accepted_event_id")
        _exact(payload["qa_event_id"], qa_record["event_id"], f"{path}.payload.qa_event_id")
        _exact(payload["success_event_id"], success_record["event_id"], f"{path}.payload.success_event_id")
        for field in ("candidate_id", "candidate_digest", "verification_obligation_id"):
            _exact(payload[field], accepted_payload[field], f"{path}.payload.{field}")
        _exact(
            _string(payload["run_outcome"], f"{path}.payload.run_outcome"),
            "succeeded",
            f"{path}.payload.run_outcome",
        )
        evidence = _array(payload["evidence_event_ids"], f"{path}.payload.evidence_event_ids")
        expected_evidence = [accepted["event_id"], qa_record["event_id"], success_record["event_id"]]
        _exact(evidence, expected_evidence, f"{path}.payload.evidence_event_ids")
        return

    if result_record is None:
        _fail(path, "controller result must precede Telos adjudication")
    result_payload = result_record["payload"]

    if event_type == "telos.sub_goal.adjudicated":
        payload = _shape(
            value,
            (
                "operation",
                "result_id",
                "result_event_id",
                "disposition",
                "evidence_event_ids",
            ),
            f"{path}.payload",
        )
        _operation(payload, "adjudicate_sub_goal", f"{path}.payload")
        _exact(payload["result_id"], result_payload["result_id"], f"{path}.payload.result_id")
        _exact(payload["result_event_id"], result_record["event_id"], f"{path}.payload.result_event_id")
        _exact(
            _string(payload["disposition"], f"{path}.payload.disposition"),
            "complete",
            f"{path}.payload.disposition",
        )
        evidence = _array(payload["evidence_event_ids"], f"{path}.payload.evidence_event_ids")
        expected_evidence = result_payload["evidence_event_ids"] + [result_record["event_id"]]
        _exact(evidence, expected_evidence, f"{path}.payload.evidence_event_ids")
        return

    _fail(path, f"unsupported event type: {event_type}")


def validate_and_project(trace: Any) -> dict[str, Any]:
    """Validate one frozen M0 trace and return its deterministic projection."""
    _reject_unsupported_values(trace)
    document = _shape(trace, ("schema_version", "records"), "$")
    _exact(
        _string(document["schema_version"], "$.schema_version"),
        "noetic.m0.telos-adjudication-trace/v0",
        "$.schema_version",
    )
    records = _array(document["records"], "$.records")
    transitions = (
        ("initial", "telos.delegation.authorized", "delegated"),
        ("delegated", "controller.run.created", "run_created"),
        ("run_created", "controller.run.started", "run_started"),
        (
            "run_started",
            "controller.implementation_generation.accepted",
            "generation_accepted",
        ),
        ("generation_accepted", "qa.verification.adjudicated", "qa_pass_attributed"),
        ("qa_pass_attributed", "controller.run.succeeded", "run_succeeded"),
        ("run_succeeded", "controller.result.reported", "result_reported"),
        ("result_reported", "telos.sub_goal.adjudicated", "telos_adjudicated"),
    )
    if len(records) != len(transitions):
        _fail("$.records", f"expected exactly {len(transitions)} records")

    expected_roles = (
        "telos",
        "controller",
        "controller",
        "controller",
        "qa",
        "controller",
        "controller",
        "telos",
    )
    bindings: list[dict[str, Any]] = []
    actors: list[dict[str, str]] = []
    timestamps: list[datetime] = []
    event_ids: list[str] = []

    state = "initial"
    for index, (from_state, expected_event, to_state) in enumerate(transitions):
        path = f"$.records[{index}]"
        _exact(state, from_state, f"{path}.state")
        record = _shape(
            records[index],
            (
                "schema_version",
                "event_id",
                "event_type",
                "occurred_at",
                "actor",
                "binding",
                "caused_by",
                "payload",
            ),
            path,
        )
        _exact(
            _string(record["schema_version"], f"{path}.schema_version"),
            "noetic.m0.trace-record/v0",
            f"{path}.schema_version",
        )
        event_id = _identifier(record["event_id"], "event", f"{path}.event_id")
        if event_id in event_ids:
            _fail(f"{path}.event_id", "replayed event identifier")
        event_ids.append(event_id)
        _exact(_string(record["event_type"], f"{path}.event_type"), expected_event, f"{path}.event_type")
        timestamps.append(_timestamp(record["occurred_at"], f"{path}.occurred_at"))
        actor = _actor(record["actor"], f"{path}.actor")
        _exact(actor["role"], expected_roles[index], f"{path}.actor.role")
        actors.append(actor)
        bindings.append(_binding(record["binding"], f"{path}.binding"))
        caused_by = _array(record["caused_by"], f"{path}.caused_by")
        for parent_index, parent_id in enumerate(caused_by):
            _identifier(parent_id, "event", f"{path}.caused_by[{parent_index}]")
        expected_cause = [] if index == 0 else [records[index - 1]["event_id"]]
        _exact(caused_by, expected_cause, f"{path}.caused_by")
        state = to_state

    _exact(state, "telos_adjudicated", "$.state")

    if any(later <= earlier for earlier, later in zip(timestamps, timestamps[1:])):
        _fail("$.records", "record timestamps must increase strictly with causality")
    root_binding = bindings[0]
    for index, binding in enumerate(bindings[1:], 1):
        _exact(binding, root_binding, f"$.records[{index}].binding")

    delegation = _delegation_payload(records[0]["payload"], "$.records[0].payload")
    if records[0]["occurred_at"] != delegation["authorized_at"]:
        _fail("$.records[0].occurred_at", "must equal delegation authorized_at")
    valid_from = _timestamp(delegation["valid_from"], "$.records[0].payload.valid_from")
    expires_at = _timestamp(delegation["expires_at"], "$.records[0].payload.expires_at")
    if any(timestamp < valid_from or timestamp >= expires_at for timestamp in timestamps):
        _fail("$.records", "record occurs outside the unexpired delegation interval")

    computed_digest = compute_delegation_digest(records[0])
    _exact(root_binding["delegation_digest"], computed_digest, "$.records[0].binding.delegation_digest")

    authority = delegation["authority"]
    if actors[0]["actor_id"] != authority["telos"]["actor_id"]:
        _fail("$.records[0].actor.actor_id", "does not match delegating Telos identity")
    for index, record in enumerate(records[1:], 1):
        role = actors[index]["role"]
        if actors[index]["actor_id"] != authority[role]["actor_id"]:
            _fail(f"$.records[{index}].actor.actor_id", "does not match delegated role identity")
        if record["event_type"] not in authority[role]["actions"]:
            _fail(f"$.records[{index}].event_type", "action was not delegated to this role")

    accepted_record: dict[str, Any] | None = None
    qa_record: dict[str, Any] | None = None
    success_record: dict[str, Any] | None = None
    result_record: dict[str, Any] | None = None
    for index, record in enumerate(records):
        _validate_record_payload(
            record,
            accepted_record,
            qa_record,
            success_record,
            result_record,
            f"$.records[{index}]",
        )
        if record["event_type"] == "controller.implementation_generation.accepted":
            accepted_record = record
        elif record["event_type"] == "qa.verification.adjudicated":
            if qa_record is not None:
                _fail(f"$.records[{index}]", "duplicate QA adjudication")
            qa_record = record
        elif record["event_type"] == "controller.run.succeeded":
            success_record = record
        elif record["event_type"] == "controller.result.reported":
            result_record = record

    if accepted_record is None or qa_record is None or result_record is None:
        _fail("$.records", "trace did not reach the frozen terminal state")
    if accepted_record["payload"]["implementer_actor_id"] != authority["implementer"]["actor_id"]:
        _fail(
            "$.records[3].payload.implementer_actor_id",
            "does not match the delegated implementer identity",
        )
    if actors[4]["actor_id"] == accepted_record["payload"]["implementer_actor_id"]:
        _fail("$.records[4].actor.actor_id", "QA identity must be distinct from the implementer")

    return {
        "schema_version": "noetic.m0.telos-adjudication-projection/v0",
        "state": state,
        "binding": dict(root_binding),
        "delegation": {
            "event_id": records[0]["event_id"],
            "actor_id": actors[0]["actor_id"],
            "purpose": delegation["purpose"],
            "revocation_status": delegation["revocation_status"],
        },
        "accepted_generation": {
            "event_id": accepted_record["event_id"],
            "generation": root_binding["generation"],
            "candidate_id": accepted_record["payload"]["candidate_id"],
            "candidate_digest": accepted_record["payload"]["candidate_digest"],
            "implementer_actor_id": accepted_record["payload"]["implementer_actor_id"],
            "verification_obligation_id": accepted_record["payload"]["verification_obligation_id"],
        },
        "qa_adjudication": {
            "event_id": qa_record["event_id"],
            "actor_id": qa_record["actor"]["actor_id"],
            "accepted_event_id": qa_record["payload"]["accepted_event_id"],
            "verification_obligation_id": qa_record["payload"]["verification_obligation_id"],
            "conclusion": qa_record["payload"]["conclusion"],
        },
        "controller_result": {
            "event_id": result_record["event_id"],
            "actor_id": result_record["actor"]["actor_id"],
            "result_id": result_record["payload"]["result_id"],
            "run_outcome": result_record["payload"]["run_outcome"],
            "evidence_event_ids": list(result_record["payload"]["evidence_event_ids"]),
        },
        "telos_adjudication": {
            "event_id": records[7]["event_id"],
            "actor_id": records[7]["actor"]["actor_id"],
            "result_id": records[7]["payload"]["result_id"],
            "disposition": records[7]["payload"]["disposition"],
            "evidence_event_ids": list(records[7]["payload"]["evidence_event_ids"]),
        },
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare projection with canonical expected bytes")
    parser.add_argument("trace", type=Path, help="strict M0 trace JSON")
    parser.add_argument("expected", type=Path, nargs="?", help="canonical expected projection for --check")
    args = parser.parse_args(argv)
    if args.check and args.expected is None:
        parser.error("--check requires an expected projection")
    if not args.check and args.expected is not None:
        parser.error("an expected projection is only valid with --check")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        trace = load_json_strict(args.trace)
        projection = validate_and_project(trace)
        rendered = canonical_json_bytes(projection)
        if args.check:
            expected = load_json_strict(args.expected)
            expected_bytes = args.expected.read_bytes()
            if canonical_json_bytes(expected) != expected_bytes:
                raise TraceValidationError("expected projection is not canonical JSON bytes")
            if rendered != expected_bytes:
                raise TraceValidationError("computed projection does not match expected bytes")
            print("M0 Telos adjudication trace passed canonical projection check.")
            return 0
        sys.stdout.buffer.write(rendered)
        return 0
    except (OSError, UnicodeError, StrictJSONError, TraceValidationError) as exc:
        print(f"M0 trace validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
