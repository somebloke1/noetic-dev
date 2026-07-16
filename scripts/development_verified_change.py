#!/usr/bin/env python3
"""Provider-free reduction for development.verified-change/v1."""

from __future__ import annotations

import argparse
import copy
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

if __package__:
    from scripts.m0_trace import (
        StrictJSONError,
        TraceValidationError,
        canonical_json_bytes,
        load_json_strict,
        validate_and_project as validate_m0_trace,
    )
    from scripts.m1_trace import (
        M1TraceValidationError,
        validate_and_project as validate_m1_trace,
    )
else:
    from m0_trace import (
        StrictJSONError,
        TraceValidationError,
        canonical_json_bytes,
        load_json_strict,
        validate_and_project as validate_m0_trace,
    )
    from m1_trace import (
        M1TraceValidationError,
        validate_and_project as validate_m1_trace,
    )


class ProgramValidationError(ValueError):
    """Raised when a development program packet or binding is invalid."""


PROGRAM_ID = "development.verified-change"
PROGRAM_VERSION = "v1"
PACKET_VERSION = "development.verified-change.packet/v1"
PROJECTION_VERSION = "development.verified-change.projection/v1"
M0_PROFILE = "m0-direct-pass"
M1_PROFILE = "m1-bounded-remediation"
M0_TRACE_VERSION = "noetic.m0.telos-adjudication-trace/v0"
M1_TRACE_VERSION = "noetic.m1.telos-recoverability-trace/v0"

PACKET_FIELDS = (
    "schema_version",
    "program_id",
    "program_version",
    "program_instance_id",
    "execution_profile",
    "governing_purpose_id",
    "attention_packet",
    "insight_packet",
    "implementation_procedure",
    "final_implementation",
    "source_trace_digest",
    "source_trace_version",
)
ATTENTION_FIELDS = (
    "packet_id",
    "producer_actor_id",
    "evidence_id",
    "evidence_digest",
    "question_id",
)
INSIGHT_FIELDS = (
    "packet_id",
    "producer_actor_id",
    "insight_digest",
    "attention_packet_id",
    "question_id",
)
PROCEDURE_FIELDS = (
    "artifact_id",
    "artifact_digest",
    "producer_actor_id",
    "insight_packet_id",
)
FINAL_FIELDS = (
    "generation",
    "accepted_event_id",
    "candidate_id",
    "candidate_digest",
    "implementer_actor_id",
    "verification_obligation_id",
    "implementation_procedure_artifact_id",
)


def _fail(path: str, message: str) -> None:
    raise ProgramValidationError(f"{path}: {message}")


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
    if re.fullmatch(rf"{re.escape(prefix)}-[a-z0-9]+(?:-[a-z0-9]+)*", text) is None:
        _fail(path, f"malformed {prefix} identifier")
    return text


def _digest(value: Any, path: str) -> str:
    text = _string(value, path)
    if re.fullmatch(r"sha256:[0-9a-f]{64}", text) is None:
        _fail(path, "expected a lowercase sha256 digest")
    return text


def source_trace_digest(source_trace: Any) -> str:
    """Return the canonical digest binding a separately supplied source trace."""
    try:
        _reject_non_json_values(source_trace, "$source")
        rendered = canonical_json_bytes(source_trace)
    except RecursionError as exc:
        raise ProgramValidationError(
            f"$source: input nesting exceeds recursion limit: {exc}"
        ) from exc
    except (TypeError, ValueError) as exc:
        raise ProgramValidationError(f"$source: cannot canonicalize strict JSON: {exc}") from exc
    return "sha256:" + hashlib.sha256(rendered).hexdigest()


def _validate_packet(packet: Any) -> dict[str, Any]:
    try:
        _reject_non_json_values(packet)
    except RecursionError as exc:
        raise ProgramValidationError(
            f"$: input nesting exceeds recursion limit: {exc}"
        ) from exc

    document = _shape(packet, PACKET_FIELDS, "$")
    _exact(_string(document["schema_version"], "$.schema_version"), PACKET_VERSION, "$.schema_version")
    _exact(_string(document["program_id"], "$.program_id"), PROGRAM_ID, "$.program_id")
    _exact(_string(document["program_version"], "$.program_version"), PROGRAM_VERSION, "$.program_version")
    _identifier(document["program_instance_id"], "program", "$.program_instance_id")
    profile = _string(document["execution_profile"], "$.execution_profile")
    if profile not in (M0_PROFILE, M1_PROFILE):
        _fail("$.execution_profile", "unsupported source profile")
    _identifier(document["governing_purpose_id"], "purpose", "$.governing_purpose_id")
    _digest(document["source_trace_digest"], "$.source_trace_digest")

    attention = _shape(document["attention_packet"], ATTENTION_FIELDS, "$.attention_packet")
    _identifier(attention["packet_id"], "product", "$.attention_packet.packet_id")
    _identifier(attention["producer_actor_id"], "actor", "$.attention_packet.producer_actor_id")
    _identifier(attention["evidence_id"], "evidence", "$.attention_packet.evidence_id")
    _digest(attention["evidence_digest"], "$.attention_packet.evidence_digest")
    _identifier(attention["question_id"], "question", "$.attention_packet.question_id")

    insight = _shape(document["insight_packet"], INSIGHT_FIELDS, "$.insight_packet")
    _identifier(insight["packet_id"], "product", "$.insight_packet.packet_id")
    _identifier(insight["producer_actor_id"], "actor", "$.insight_packet.producer_actor_id")
    _digest(insight["insight_digest"], "$.insight_packet.insight_digest")
    _identifier(insight["attention_packet_id"], "product", "$.insight_packet.attention_packet_id")
    _identifier(insight["question_id"], "question", "$.insight_packet.question_id")
    _exact(
        insight["attention_packet_id"],
        attention["packet_id"],
        "$.insight_packet.attention_packet_id",
    )
    _exact(insight["question_id"], attention["question_id"], "$.insight_packet.question_id")

    procedure = _shape(
        document["implementation_procedure"],
        PROCEDURE_FIELDS,
        "$.implementation_procedure",
    )
    _identifier(procedure["artifact_id"], "product", "$.implementation_procedure.artifact_id")
    _digest(procedure["artifact_digest"], "$.implementation_procedure.artifact_digest")
    _identifier(
        procedure["producer_actor_id"],
        "actor",
        "$.implementation_procedure.producer_actor_id",
    )
    _identifier(
        procedure["insight_packet_id"],
        "product",
        "$.implementation_procedure.insight_packet_id",
    )
    _exact(
        procedure["insight_packet_id"],
        insight["packet_id"],
        "$.implementation_procedure.insight_packet_id",
    )

    product_ids = (attention["packet_id"], insight["packet_id"], procedure["artifact_id"])
    if len(set(product_ids)) != len(product_ids):
        _fail(
            "$",
            "attention packet, insight packet, and procedure artifact IDs must be pairwise distinct",
        )

    final = _shape(document["final_implementation"], FINAL_FIELDS, "$.final_implementation")
    _integer(final["generation"], "$.final_implementation.generation")
    _identifier(final["accepted_event_id"], "event", "$.final_implementation.accepted_event_id")
    _identifier(final["candidate_id"], "candidate", "$.final_implementation.candidate_id")
    _digest(final["candidate_digest"], "$.final_implementation.candidate_digest")
    _identifier(
        final["implementer_actor_id"],
        "actor",
        "$.final_implementation.implementer_actor_id",
    )
    _identifier(
        final["verification_obligation_id"],
        "obligation",
        "$.final_implementation.verification_obligation_id",
    )
    _identifier(
        final["implementation_procedure_artifact_id"],
        "product",
        "$.final_implementation.implementation_procedure_artifact_id",
    )
    _exact(
        final["implementation_procedure_artifact_id"],
        procedure["artifact_id"],
        "$.final_implementation.implementation_procedure_artifact_id",
    )
    return document


def _select_source_projection(
    packet: dict[str, Any], source_trace: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = packet["execution_profile"]
    source_version = _string(packet["source_trace_version"], "$.source_trace_version")
    source = _object(source_trace, "$source")
    supplied_version = source.get("schema_version")

    if profile == M0_PROFILE:
        _exact(source_version, M0_TRACE_VERSION, "$.source_trace_version")
        _exact(supplied_version, M0_TRACE_VERSION, "$source.schema_version")
        try:
            projection = validate_m0_trace(source_trace)
        except (StrictJSONError, TraceValidationError) as exc:
            raise ProgramValidationError(f"$source: M0 source trace rejected: {exc}") from None
        return projection, projection["accepted_generation"]

    if profile == M1_PROFILE:
        _exact(source_version, M1_TRACE_VERSION, "$.source_trace_version")
        _exact(supplied_version, M1_TRACE_VERSION, "$source.schema_version")
        try:
            projection = validate_m1_trace(source_trace)
        except (StrictJSONError, M1TraceValidationError) as exc:
            raise ProgramValidationError(f"$source: M1 source trace rejected: {exc}") from None
        terminal = dict(projection["generation_history"][1]["accepted_generation"])
        terminal["generation"] = projection["generation_history"][1]["generation"]
        return projection, terminal

    _fail("$.execution_profile", "unsupported source profile")


def _bind_source(
    packet: dict[str, Any],
    source_projection: dict[str, Any],
    terminal: dict[str, Any],
) -> None:
    _exact(
        packet["program_instance_id"],
        source_projection["binding"]["program_id"],
        "$.program_instance_id",
    )
    _exact(
        packet["governing_purpose_id"],
        source_projection["delegation"]["purpose"],
        "$.governing_purpose_id",
    )
    final = packet["final_implementation"]
    expected = {
        "generation": terminal["generation"],
        "accepted_event_id": terminal["event_id"],
        "candidate_id": terminal["candidate_id"],
        "candidate_digest": terminal["candidate_digest"],
        "implementer_actor_id": terminal["implementer_actor_id"],
        "verification_obligation_id": terminal["verification_obligation_id"],
    }
    for field, value in expected.items():
        _exact(final[field], value, f"$.final_implementation.{field}")


def _deterministic_gates(packet: dict[str, Any]) -> dict[str, Any]:
    attention = packet["attention_packet"]
    insight = packet["insight_packet"]
    procedure = packet["implementation_procedure"]
    final = packet["final_implementation"]
    return {
        "attention_to_insight_lineage": {
            "kind": "deterministic",
            "determination": "structurally_bound",
            "attention_packet_id": attention["packet_id"],
            "insight_packet_id": insight["packet_id"],
            "question_id": attention["question_id"],
        },
        "procedure_to_implementation_lineage": {
            "kind": "deterministic",
            "determination": "structurally_bound",
            "insight_packet_id": insight["packet_id"],
            "procedure_artifact_id": procedure["artifact_id"],
            "final_procedure_artifact_id": final[
                "implementation_procedure_artifact_id"
            ],
        },
        "final_implementation_binding": {
            "kind": "deterministic",
            "determination": "source_equal",
            "generation": final["generation"],
            "accepted_event_id": final["accepted_event_id"],
            "candidate_id": final["candidate_id"],
            "candidate_digest": final["candidate_digest"],
            "implementer_actor_id": final["implementer_actor_id"],
            "verification_obligation_id": final["verification_obligation_id"],
        },
    }


def _m0_gates(packet: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    gates = _deterministic_gates(packet)
    accepted = source["accepted_generation"]
    qa = source["qa_adjudication"]
    gates.update(
        {
            "verification": {
                "kind": "attributed_semantic",
                "attribution": "source_trace",
                "actor_id": qa["actor_id"],
                "event_id": qa["event_id"],
                "generation": accepted["generation"],
                "accepted_event_id": qa["accepted_event_id"],
                "candidate_id": accepted["candidate_id"],
                "candidate_digest": accepted["candidate_digest"],
                "verification_obligation_id": qa["verification_obligation_id"],
                "conclusion": qa["conclusion"],
            },
            "remediation": {"represented": False},
            "controller_result": {
                "kind": "attributed_semantic",
                "attribution": "source_trace",
                "result": copy.deepcopy(source["controller_result"]),
            },
            "telos_adjudication": {
                "kind": "attributed_semantic",
                "attribution": "source_trace",
                "adjudication": copy.deepcopy(source["telos_adjudication"]),
            },
        }
    )
    return gates


def _m1_gates(packet: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    gates = _deterministic_gates(packet)
    terminal_history = source["generation_history"][1]
    accepted = terminal_history["accepted_generation"]
    qa = terminal_history["qa_adjudication"]
    gates.update(
        {
            "verification": {
                "kind": "attributed_semantic",
                "attribution": "source_trace",
                "actor_id": qa["actor_id"],
                "event_id": qa["event_id"],
                "generation": terminal_history["generation"],
                "accepted_event_id": qa["accepted_event_id"],
                "candidate_id": accepted["candidate_id"],
                "candidate_digest": accepted["candidate_digest"],
                "verification_obligation_id": qa["verification_obligation_id"],
                "conclusion": qa["conclusion"],
            },
            "remediation": {
                "represented": True,
                "kind": "attributed_semantic",
                "attribution": "source_trace",
                "remediation_budget": copy.deepcopy(source["remediation_budget"]),
                "remediation_generation": copy.deepcopy(
                    source["remediation_generation"]
                ),
            },
            "controller_result": {
                "kind": "attributed_semantic",
                "attribution": "source_trace",
                "result": copy.deepcopy(source["controller_result"]),
            },
            "telos_adjudication": {
                "kind": "attributed_semantic",
                "attribution": "source_trace",
                "adjudication": copy.deepcopy(source["telos_adjudication"]),
            },
        }
    )
    return gates


def validate_and_project(packet: Any, source_trace: Any) -> dict[str, Any]:
    """Validate one strict program packet and independently supplied source trace."""
    document = _validate_packet(packet)
    computed_digest = source_trace_digest(source_trace)
    _exact(document["source_trace_digest"], computed_digest, "$.source_trace_digest")
    source_projection, terminal = _select_source_projection(document, source_trace)
    _bind_source(document, source_projection, terminal)

    if document["execution_profile"] == M0_PROFILE:
        gates = _m0_gates(document, source_projection)
    elif document["execution_profile"] == M1_PROFILE:
        gates = _m1_gates(document, source_projection)
    else:  # pragma: no cover - profile validation is closed above
        _fail("$.execution_profile", "unsupported source profile")

    return {
        "schema_version": PROJECTION_VERSION,
        "program_id": PROGRAM_ID,
        "program_version": PROGRAM_VERSION,
        "program_instance_id": document["program_instance_id"],
        "execution_profile": document["execution_profile"],
        "state": "telos_adjudicated",
        "governing_purpose_id": document["governing_purpose_id"],
        "attention_packet": copy.deepcopy(document["attention_packet"]),
        "insight_packet": copy.deepcopy(document["insight_packet"]),
        "implementation_procedure": copy.deepcopy(
            document["implementation_procedure"]
        ),
        "final_implementation": copy.deepcopy(document["final_implementation"]),
        "source_trace_digest": document["source_trace_digest"],
        "source_trace_version": document["source_trace_version"],
        "source_trace_projection": copy.deepcopy(source_projection),
        "gates": gates,
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare canonical projection bytes")
    parser.add_argument("packet", type=Path, help="strict development program packet JSON")
    parser.add_argument("source", type=Path, help="strict frozen M0 or M1 source trace JSON")
    parser.add_argument("expected", type=Path, nargs="?", help="canonical expected projection for --check")
    args = parser.parse_args(argv)
    if args.check and args.expected is None:
        parser.error("--check requires packet, source, and expected projection paths")
    if not args.check and args.expected is not None:
        parser.error("an expected projection is only valid with --check")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        packet = load_json_strict(args.packet)
        source = load_json_strict(args.source)
        projection = validate_and_project(packet, source)
        rendered = canonical_json_bytes(projection)
        if args.check:
            expected = load_json_strict(args.expected)
            expected_bytes = args.expected.read_bytes()
            if canonical_json_bytes(expected) != expected_bytes:
                raise ProgramValidationError(
                    "expected projection is not canonical JSON bytes"
                )
            if rendered != expected_bytes:
                raise ProgramValidationError(
                    "computed projection does not match expected bytes"
                )
            print(
                "development.verified-change/v1 passed canonical projection check."
            )
            return 0
        sys.stdout.buffer.write(rendered)
        return 0
    except (
        OSError,
        UnicodeError,
        StrictJSONError,
        ProgramValidationError,
    ) as exc:
        print(f"development.verified-change validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
