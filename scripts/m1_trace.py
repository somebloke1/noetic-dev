#!/usr/bin/env python3
"""Pure, provider-free validation and projection for the frozen M1 trace."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__:
    from scripts.m0_trace import StrictJSONError, canonical_json_bytes, load_json_strict
else:
    from m0_trace import StrictJSONError, canonical_json_bytes, load_json_strict


class M1TraceValidationError(ValueError):
    """Raised when a trace violates the frozen M1 contract."""


TRACE_VERSION = "noetic.m1.telos-recoverability-trace/v0"
RECORD_VERSION = "noetic.m1.trace-record/v0"
PROJECTION_VERSION = "noetic.m1.telos-recoverability-projection/v0"

TRANSITIONS = (
    ("initial", "telos.delegation.authorized", "delegated"),
    ("delegated", "controller.run.created", "run_created"),
    ("run_created", "controller.run.started", "run_started"),
    (
        "run_started",
        "controller.implementation_generation.accepted",
        "generation_1_accepted",
    ),
    ("generation_1_accepted", "qa.verification.adjudicated", "generation_1_qa_failed"),
    (
        "generation_1_qa_failed",
        "controller.remediation_generation.started",
        "generation_2_remediation_started",
    ),
    (
        "generation_2_remediation_started",
        "controller.implementation_generation.accepted",
        "generation_2_accepted",
    ),
    ("generation_2_accepted", "qa.verification.adjudicated", "generation_2_qa_passed"),
    ("generation_2_qa_passed", "controller.run.succeeded", "run_succeeded"),
    ("run_succeeded", "controller.result.reported", "result_reported"),
    ("result_reported", "telos.sub_goal.adjudicated", "telos_adjudicated"),
)
EVENT_SEQUENCE = tuple(transition[1] for transition in TRANSITIONS)
GENERATION_SEQUENCE = (1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2)
EXPECTED_ROLES = (
    "telos",
    "controller",
    "controller",
    "controller",
    "qa",
    "controller",
    "controller",
    "qa",
    "controller",
    "controller",
    "telos",
)
DELEGATED_ACTIONS = {
    "telos": ("telos.sub_goal.adjudicated",),
    "controller": (
        "controller.run.created",
        "controller.run.started",
        "controller.implementation_generation.accepted",
        "controller.remediation_generation.started",
        "controller.run.succeeded",
        "controller.result.reported",
    ),
    "implementer": (),
    "qa": ("qa.verification.adjudicated",),
}
STABLE_BINDING_FIELDS = (
    "delegation_id",
    "delegation_digest",
    "goal_chain_id",
    "sub_goal_id",
    "program_id",
    "run_id",
    "correlation_id",
)


def _fail(path: str, message: str) -> None:
    raise M1TraceValidationError(f"{path}: {message}")


def _reject_non_json_values(value: Any, path: str = "$") -> None:
    value_type = type(value)
    if value is None:
        _fail(path, "null is not supported")
    if value_type is float:
        _fail(path, "floating-point numbers are not supported")
    if value_type is list:
        for index, item in enumerate(value):
            _reject_non_json_values(item, f"{path}[{index}]")
        return
    if value_type is dict:
        for key, item in value.items():
            if type(key) is not str:
                _fail(path, "object keys must be strings")
            _reject_non_json_values(item, f"{path}.{key}")
        return
    if value_type not in (str, int, bool):
        _fail(path, f"unsupported value type: {value_type.__name__}")


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


def _binding(value: Any, generation: int, path: str) -> dict[str, Any]:
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
    _exact(_integer(binding["generation"], f"{path}.generation"), generation, f"{path}.generation")
    _identifier(binding["correlation_id"], "correlation", f"{path}.correlation_id")
    return binding


def _actor(value: Any, path: str) -> dict[str, Any]:
    actor = _shape(value, ("role", "actor_id"), path)
    role = _string(actor["role"], f"{path}.role")
    if role not in DELEGATED_ACTIONS:
        _fail(f"{path}.role", "unknown actor role")
    _identifier(actor["actor_id"], "actor", f"{path}.actor_id")
    return actor


def _operation(payload: dict[str, Any], expected: str, path: str) -> None:
    _exact(_string(payload["operation"], f"{path}.operation"), expected, f"{path}.operation")


def _authority_entry(value: Any, role: str, path: str) -> dict[str, Any]:
    entry = _shape(value, ("actor_id", "actions"), path)
    _identifier(entry["actor_id"], "actor", f"{path}.actor_id")
    actions = _array(entry["actions"], f"{path}.actions")
    for index, action in enumerate(actions):
        _string(action, f"{path}.actions[{index}]")
    expected = DELEGATED_ACTIONS[role]
    if tuple(actions) != expected:
        _fail(f"{path}.actions", f"expected exactly {list(expected)!r}")
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
            "policy",
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

    policy = _shape(payload["policy"], ("max_remediation_generations",), f"{path}.policy")
    _exact(
        _integer(
            policy["max_remediation_generations"],
            f"{path}.policy.max_remediation_generations",
        ),
        1,
        f"{path}.policy.max_remediation_generations",
    )

    authority = _shape(
        payload["authority"],
        ("telos", "controller", "implementer", "qa"),
        f"{path}.authority",
    )
    actor_ids = []
    for role in ("telos", "controller", "implementer", "qa"):
        entry = _authority_entry(authority[role], role, f"{path}.authority.{role}")
        actor_ids.append(entry["actor_id"])
    if len(set(actor_ids)) != 4:
        _fail(f"{path}.authority", "all fixture-declared actor identities must be distinct")
    return payload


def compute_delegation_digest(record: dict[str, Any]) -> str:
    """Compute the M1 digest over fixture-declared delegation material."""
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
            "initial_generation": binding["generation"],
            "correlation_id": binding["correlation_id"],
        },
        "delegation": record["payload"],
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(material)).hexdigest()


def _operation_only_payload(value: Any, expected: str, path: str) -> dict[str, Any]:
    payload = _shape(value, ("operation",), path)
    _operation(payload, expected, path)
    return payload


def _accepted_payload(value: Any, generation: int, path: str) -> dict[str, Any]:
    fields = (
        "operation",
        "candidate_id",
        "candidate_digest",
        "implementer_actor_id",
        "verification_obligation_id",
    )
    if generation == 2:
        fields += ("remediation_event_id", "superseded_accepted_event_id")
    payload = _shape(value, fields, path)
    _operation(payload, "accept_implementation_generation", path)
    _identifier(payload["candidate_id"], "candidate", f"{path}.candidate_id")
    _digest(payload["candidate_digest"], f"{path}.candidate_digest")
    _identifier(payload["implementer_actor_id"], "actor", f"{path}.implementer_actor_id")
    _identifier(
        payload["verification_obligation_id"],
        "obligation",
        f"{path}.verification_obligation_id",
    )
    if generation == 2:
        _identifier(payload["remediation_event_id"], "event", f"{path}.remediation_event_id")
        _identifier(
            payload["superseded_accepted_event_id"],
            "event",
            f"{path}.superseded_accepted_event_id",
        )
    return payload


def _qa_payload(
    value: Any,
    accepted: dict[str, Any],
    conclusion: str,
    path: str,
) -> dict[str, Any]:
    fields = (
        "operation",
        "accepted_event_id",
        "candidate_id",
        "candidate_digest",
        "verification_obligation_id",
        "conclusion",
    )
    if conclusion == "FAIL":
        fields += ("finding_id", "finding_digest")
    payload = _shape(value, fields, path)
    _operation(payload, "adjudicate_verification", path)
    accepted_payload = accepted["payload"]
    _exact(payload["accepted_event_id"], accepted["event_id"], f"{path}.accepted_event_id")
    for field in ("candidate_id", "candidate_digest", "verification_obligation_id"):
        _exact(payload[field], accepted_payload[field], f"{path}.{field}")
    _exact(_string(payload["conclusion"], f"{path}.conclusion"), conclusion, f"{path}.conclusion")
    if conclusion == "FAIL":
        _identifier(payload["finding_id"], "finding", f"{path}.finding_id")
        _digest(payload["finding_digest"], f"{path}.finding_digest")
    return payload


def _remediation_payload(
    value: Any,
    failed_acceptance: dict[str, Any],
    failed_qa: dict[str, Any],
    path: str,
) -> dict[str, Any]:
    payload = _shape(
        value,
        (
            "operation",
            "remediation_ordinal",
            "target_generation",
            "failed_accepted_event_id",
            "failed_qa_event_id",
            "failed_verification_obligation_id",
            "finding_id",
            "finding_digest",
        ),
        path,
    )
    _operation(payload, "start_remediation_generation", path)
    _exact(_integer(payload["remediation_ordinal"], f"{path}.remediation_ordinal"), 1, f"{path}.remediation_ordinal")
    failed_generation = failed_qa["binding"]["generation"]
    _exact(
        _integer(payload["target_generation"], f"{path}.target_generation"),
        failed_generation + 1,
        f"{path}.target_generation",
    )
    _exact(
        payload["failed_accepted_event_id"],
        failed_acceptance["event_id"],
        f"{path}.failed_accepted_event_id",
    )
    _exact(payload["failed_qa_event_id"], failed_qa["event_id"], f"{path}.failed_qa_event_id")
    _exact(
        payload["failed_verification_obligation_id"],
        failed_acceptance["payload"]["verification_obligation_id"],
        f"{path}.failed_verification_obligation_id",
    )
    _exact(payload["finding_id"], failed_qa["payload"]["finding_id"], f"{path}.finding_id")
    _exact(
        payload["finding_digest"],
        failed_qa["payload"]["finding_digest"],
        f"{path}.finding_digest",
    )
    return payload


def _success_payload(
    value: Any,
    accepted: dict[str, Any],
    qa_record: dict[str, Any],
    path: str,
) -> dict[str, Any]:
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
        path,
    )
    _operation(payload, "succeed_run", path)
    _exact(payload["accepted_event_id"], accepted["event_id"], f"{path}.accepted_event_id")
    _exact(payload["qa_event_id"], qa_record["event_id"], f"{path}.qa_event_id")
    for field in ("candidate_id", "candidate_digest", "verification_obligation_id"):
        _exact(payload[field], accepted["payload"][field], f"{path}.{field}")
    _exact(payload["qa_conclusion"], qa_record["payload"]["conclusion"], f"{path}.qa_conclusion")
    _exact(payload["qa_conclusion"], "PASS", f"{path}.qa_conclusion")
    return payload


def _result_payload(
    value: Any,
    accepted: dict[str, Any],
    qa_record: dict[str, Any],
    success: dict[str, Any],
    path: str,
) -> dict[str, Any]:
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
        path,
    )
    _operation(payload, "report_result", path)
    _identifier(payload["result_id"], "result", f"{path}.result_id")
    _exact(payload["accepted_event_id"], accepted["event_id"], f"{path}.accepted_event_id")
    _exact(payload["qa_event_id"], qa_record["event_id"], f"{path}.qa_event_id")
    _exact(payload["success_event_id"], success["event_id"], f"{path}.success_event_id")
    for field in ("candidate_id", "candidate_digest", "verification_obligation_id"):
        _exact(payload[field], accepted["payload"][field], f"{path}.{field}")
    _exact(_string(payload["run_outcome"], f"{path}.run_outcome"), "succeeded", f"{path}.run_outcome")
    evidence = _array(payload["evidence_event_ids"], f"{path}.evidence_event_ids")
    expected = [accepted["event_id"], qa_record["event_id"], success["event_id"]]
    _exact(evidence, expected, f"{path}.evidence_event_ids")
    return payload


def _telos_payload(
    value: Any,
    generation_1_acceptance: dict[str, Any],
    generation_1_qa: dict[str, Any],
    remediation: dict[str, Any],
    generation_2_acceptance: dict[str, Any],
    generation_2_qa: dict[str, Any],
    success: dict[str, Any],
    result: dict[str, Any],
    path: str,
) -> dict[str, Any]:
    payload = _shape(
        value,
        ("operation", "result_id", "result_event_id", "disposition", "evidence_event_ids"),
        path,
    )
    _operation(payload, "adjudicate_sub_goal", path)
    _exact(payload["result_id"], result["payload"]["result_id"], f"{path}.result_id")
    _exact(payload["result_event_id"], result["event_id"], f"{path}.result_event_id")
    _exact(_string(payload["disposition"], f"{path}.disposition"), "complete", f"{path}.disposition")
    evidence = _array(payload["evidence_event_ids"], f"{path}.evidence_event_ids")
    expected = [
        generation_1_acceptance["event_id"],
        generation_1_qa["event_id"],
        remediation["event_id"],
        generation_2_acceptance["event_id"],
        generation_2_qa["event_id"],
        success["event_id"],
        result["event_id"],
    ]
    _exact(evidence, expected, f"{path}.evidence_event_ids")
    return payload


def _stable_binding(binding: dict[str, Any]) -> dict[str, Any]:
    return {field: binding[field] for field in STABLE_BINDING_FIELDS}


def validate_and_project(trace: Any) -> dict[str, Any]:
    """Validate the one frozen M1 trace and return its deterministic projection."""
    try:
        _reject_non_json_values(trace)
    except RecursionError as exc:
        raise M1TraceValidationError(f"$: input nesting exceeds recursion limit: {exc}") from exc

    document = _shape(trace, ("schema_version", "records"), "$")
    _exact(_string(document["schema_version"], "$.schema_version"), TRACE_VERSION, "$.schema_version")
    records = _array(document["records"], "$.records")
    if len(records) != len(TRANSITIONS):
        _fail("$.records", f"expected exactly {len(TRANSITIONS)} records")

    bindings: list[dict[str, Any]] = []
    actors: list[dict[str, Any]] = []
    timestamps: list[datetime] = []
    event_ids: list[str] = []
    state = "initial"

    for index, (from_state, expected_event, to_state) in enumerate(TRANSITIONS):
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
        _exact(_string(record["schema_version"], f"{path}.schema_version"), RECORD_VERSION, f"{path}.schema_version")
        event_id = _identifier(record["event_id"], "event", f"{path}.event_id")
        if event_id in event_ids:
            _fail(f"{path}.event_id", "replayed event identifier")
        event_ids.append(event_id)
        _exact(_string(record["event_type"], f"{path}.event_type"), expected_event, f"{path}.event_type")
        timestamps.append(_timestamp(record["occurred_at"], f"{path}.occurred_at"))
        actor = _actor(record["actor"], f"{path}.actor")
        _exact(actor["role"], EXPECTED_ROLES[index], f"{path}.actor.role")
        actors.append(actor)
        bindings.append(_binding(record["binding"], GENERATION_SEQUENCE[index], f"{path}.binding"))
        caused_by = _array(record["caused_by"], f"{path}.caused_by")
        for cause_index, cause in enumerate(caused_by):
            _identifier(cause, "event", f"{path}.caused_by[{cause_index}]")
        expected_cause = [] if index == 0 else [records[index - 1]["event_id"]]
        _exact(caused_by, expected_cause, f"{path}.caused_by")
        state = to_state

    _exact(state, "telos_adjudicated", "$.state")
    if tuple(binding["generation"] for binding in bindings) != GENERATION_SEQUENCE:
        _fail("$.records", f"expected generation sequence {list(GENERATION_SEQUENCE)!r}")
    if any(later <= earlier for earlier, later in zip(timestamps, timestamps[1:])):
        _fail("$.records", "record timestamps must increase strictly with causality")

    stable_binding = _stable_binding(bindings[0])
    for index, binding in enumerate(bindings[1:], 1):
        _exact(_stable_binding(binding), stable_binding, f"$.records[{index}].binding")

    delegation = _delegation_payload(records[0]["payload"], "$.records[0].payload")
    if records[0]["occurred_at"] != delegation["authorized_at"]:
        _fail("$.records[0].occurred_at", "must equal delegation authorized_at")
    valid_from = _timestamp(delegation["valid_from"], "$.records[0].payload.valid_from")
    expires_at = _timestamp(delegation["expires_at"], "$.records[0].payload.expires_at")
    if any(timestamp < valid_from or timestamp >= expires_at for timestamp in timestamps):
        _fail("$.records", "record occurs outside the unexpired delegation interval")
    _exact(
        bindings[0]["delegation_digest"],
        compute_delegation_digest(records[0]),
        "$.records[0].binding.delegation_digest",
    )

    authority = delegation["authority"]
    if actors[0]["actor_id"] != authority["telos"]["actor_id"]:
        _fail("$.records[0].actor.actor_id", "does not match fixture-declared Telos identity")
    for index, record in enumerate(records[1:], 1):
        role = actors[index]["role"]
        if actors[index]["actor_id"] != authority[role]["actor_id"]:
            _fail(f"$.records[{index}].actor.actor_id", "does not match fixture-declared role identity")
        if record["event_type"] not in authority[role]["actions"]:
            _fail(f"$.records[{index}].event_type", "action is outside fixture-declared authority")

    _operation_only_payload(records[1]["payload"], "create_run", "$.records[1].payload")
    _operation_only_payload(records[2]["payload"], "start_run", "$.records[2].payload")
    generation_1_acceptance = records[3]
    _accepted_payload(generation_1_acceptance["payload"], 1, "$.records[3].payload")
    generation_1_qa = records[4]
    _qa_payload(generation_1_qa["payload"], generation_1_acceptance, "FAIL", "$.records[4].payload")
    remediation = records[5]
    _remediation_payload(
        remediation["payload"],
        generation_1_acceptance,
        generation_1_qa,
        "$.records[5].payload",
    )
    generation_2_acceptance = records[6]
    _accepted_payload(generation_2_acceptance["payload"], 2, "$.records[6].payload")
    _exact(
        generation_2_acceptance["payload"]["remediation_event_id"],
        remediation["event_id"],
        "$.records[6].payload.remediation_event_id",
    )
    _exact(
        generation_2_acceptance["payload"]["superseded_accepted_event_id"],
        generation_1_acceptance["event_id"],
        "$.records[6].payload.superseded_accepted_event_id",
    )
    generation_2_qa = records[7]
    _qa_payload(generation_2_qa["payload"], generation_2_acceptance, "PASS", "$.records[7].payload")
    success = records[8]
    _success_payload(success["payload"], generation_2_acceptance, generation_2_qa, "$.records[8].payload")
    result = records[9]
    _result_payload(
        result["payload"],
        generation_2_acceptance,
        generation_2_qa,
        success,
        "$.records[9].payload",
    )
    terminal = records[10]
    _telos_payload(
        terminal["payload"],
        generation_1_acceptance,
        generation_1_qa,
        remediation,
        generation_2_acceptance,
        generation_2_qa,
        success,
        result,
        "$.records[10].payload",
    )

    for index, accepted in ((3, generation_1_acceptance), (6, generation_2_acceptance)):
        if accepted["payload"]["implementer_actor_id"] != authority["implementer"]["actor_id"]:
            _fail(
                f"$.records[{index}].payload.implementer_actor_id",
                "does not match fixture-declared implementer identity",
            )

    for field in ("candidate_id", "candidate_digest", "verification_obligation_id"):
        if generation_1_acceptance["payload"][field] == generation_2_acceptance["payload"][field]:
            _fail(f"$.records[6].payload.{field}", "must be distinct across semantic generations")
    if generation_1_acceptance["event_id"] == generation_2_acceptance["event_id"]:
        _fail("$.records[6].event_id", "accepted event identifiers must be distinct")
    if generation_1_qa["event_id"] == generation_2_qa["event_id"]:
        _fail("$.records[7].event_id", "QA event identifiers must be distinct")

    policy = delegation["policy"]
    remediation_count = sum(
        record["event_type"] == "controller.remediation_generation.started" for record in records
    )
    authorized_budget = policy["max_remediation_generations"]
    if remediation_count != 1 or remediation_count > authorized_budget:
        _fail("$.records", "remediation event does not consume the one-generation budget exactly")

    generation_1_payload = generation_1_acceptance["payload"]
    generation_1_qa_payload = generation_1_qa["payload"]
    generation_2_payload = generation_2_acceptance["payload"]
    generation_2_qa_payload = generation_2_qa["payload"]
    result_payload = result["payload"]
    terminal_payload = terminal["payload"]

    return {
        "schema_version": PROJECTION_VERSION,
        "state": state,
        "binding": dict(stable_binding),
        "delegation": {
            "event_id": records[0]["event_id"],
            "actor_id": actors[0]["actor_id"],
            "purpose": delegation["purpose"],
            "revocation_status": delegation["revocation_status"],
            "policy": dict(policy),
        },
        "remediation_budget": {
            "authorized": authorized_budget,
            "consumed": remediation_count,
            "remaining": authorized_budget - remediation_count,
        },
        "generation_history": [
            {
                "generation": 1,
                "accepted_generation": {
                    "event_id": generation_1_acceptance["event_id"],
                    "candidate_id": generation_1_payload["candidate_id"],
                    "candidate_digest": generation_1_payload["candidate_digest"],
                    "implementer_actor_id": generation_1_payload["implementer_actor_id"],
                    "verification_obligation_id": generation_1_payload[
                        "verification_obligation_id"
                    ],
                },
                "qa_adjudication": {
                    "event_id": generation_1_qa["event_id"],
                    "actor_id": generation_1_qa["actor"]["actor_id"],
                    "accepted_event_id": generation_1_qa_payload["accepted_event_id"],
                    "verification_obligation_id": generation_1_qa_payload[
                        "verification_obligation_id"
                    ],
                    "conclusion": generation_1_qa_payload["conclusion"],
                    "finding_id": generation_1_qa_payload["finding_id"],
                    "finding_digest": generation_1_qa_payload["finding_digest"],
                },
            },
            {
                "generation": 2,
                "accepted_generation": {
                    "event_id": generation_2_acceptance["event_id"],
                    "candidate_id": generation_2_payload["candidate_id"],
                    "candidate_digest": generation_2_payload["candidate_digest"],
                    "implementer_actor_id": generation_2_payload["implementer_actor_id"],
                    "verification_obligation_id": generation_2_payload[
                        "verification_obligation_id"
                    ],
                    "remediation_event_id": generation_2_payload["remediation_event_id"],
                    "superseded_accepted_event_id": generation_2_payload[
                        "superseded_accepted_event_id"
                    ],
                },
                "qa_adjudication": {
                    "event_id": generation_2_qa["event_id"],
                    "actor_id": generation_2_qa["actor"]["actor_id"],
                    "accepted_event_id": generation_2_qa_payload["accepted_event_id"],
                    "verification_obligation_id": generation_2_qa_payload[
                        "verification_obligation_id"
                    ],
                    "conclusion": generation_2_qa_payload["conclusion"],
                },
            },
        ],
        "remediation_generation": {
            "event_id": remediation["event_id"],
            "generation": remediation["binding"]["generation"],
            "remediation_ordinal": remediation["payload"]["remediation_ordinal"],
            "target_generation": remediation["payload"]["target_generation"],
            "failed_accepted_event_id": remediation["payload"]["failed_accepted_event_id"],
            "failed_qa_event_id": remediation["payload"]["failed_qa_event_id"],
            "failed_verification_obligation_id": remediation["payload"][
                "failed_verification_obligation_id"
            ],
            "finding_id": remediation["payload"]["finding_id"],
            "finding_digest": remediation["payload"]["finding_digest"],
        },
        "controller_success": {
            "event_id": success["event_id"],
            "actor_id": success["actor"]["actor_id"],
            "generation": success["binding"]["generation"],
            "accepted_event_id": success["payload"]["accepted_event_id"],
            "qa_event_id": success["payload"]["qa_event_id"],
            "candidate_id": success["payload"]["candidate_id"],
            "candidate_digest": success["payload"]["candidate_digest"],
            "verification_obligation_id": success["payload"]["verification_obligation_id"],
            "qa_conclusion": success["payload"]["qa_conclusion"],
        },
        "controller_result": {
            "event_id": result["event_id"],
            "actor_id": result["actor"]["actor_id"],
            "generation": result["binding"]["generation"],
            "result_id": result_payload["result_id"],
            "accepted_event_id": result_payload["accepted_event_id"],
            "qa_event_id": result_payload["qa_event_id"],
            "success_event_id": result_payload["success_event_id"],
            "candidate_id": result_payload["candidate_id"],
            "candidate_digest": result_payload["candidate_digest"],
            "verification_obligation_id": result_payload["verification_obligation_id"],
            "run_outcome": result_payload["run_outcome"],
            "evidence_event_ids": list(result_payload["evidence_event_ids"]),
        },
        "telos_adjudication": {
            "event_id": terminal["event_id"],
            "actor_id": terminal["actor"]["actor_id"],
            "generation": terminal["binding"]["generation"],
            "result_id": terminal_payload["result_id"],
            "result_event_id": terminal_payload["result_event_id"],
            "disposition": terminal_payload["disposition"],
            "evidence_event_ids": list(terminal_payload["evidence_event_ids"]),
        },
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare projection with canonical expected bytes")
    parser.add_argument("trace", type=Path, help="strict M1 trace JSON")
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
                raise M1TraceValidationError("expected projection is not canonical JSON bytes")
            if rendered != expected_bytes:
                raise M1TraceValidationError("computed projection does not match expected bytes")
            print("M1 Telos recoverability trace passed canonical projection check.")
            return 0
        sys.stdout.buffer.write(rendered)
        return 0
    except (OSError, UnicodeError, StrictJSONError, M1TraceValidationError) as exc:
        print(f"M1 trace validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
