#!/usr/bin/env python3
"""Provider-free terminal read model for an accepted verified-change projection."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


class ObservabilityCompatibilityError(ValueError):
    """Raised when an input is not a compatible terminal projection shape."""


INPUT_VERSION = "development.verified-change.projection/v1"
OUTPUT_VERSION = "development.verified-change.terminal-observability/v1"
PROGRAM_ID = "development.verified-change"
PROGRAM_VERSION = "v1"
M0_PROFILE = "m0-direct-pass"
M1_PROFILE = "m1-bounded-remediation"

ROOT_FIELDS = (
    "schema_version",
    "program_id",
    "program_version",
    "program_instance_id",
    "execution_profile",
    "state",
    "governing_purpose_id",
    "attention_packet",
    "insight_packet",
    "implementation_procedure",
    "final_implementation",
    "source_trace_digest",
    "source_trace_version",
    "source_trace_projection",
    "gates",
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
GATE_FIELDS = (
    "attention_to_insight_lineage",
    "procedure_to_implementation_lineage",
    "final_implementation_binding",
    "verification",
    "remediation",
    "controller_result",
    "telos_adjudication",
)
ATTENTION_GATE_FIELDS = (
    "kind",
    "determination",
    "attention_packet_id",
    "insight_packet_id",
    "question_id",
)
PROCEDURE_GATE_FIELDS = (
    "kind",
    "determination",
    "insight_packet_id",
    "procedure_artifact_id",
    "final_procedure_artifact_id",
)
FINAL_GATE_FIELDS = (
    "kind",
    "determination",
    "generation",
    "accepted_event_id",
    "candidate_id",
    "candidate_digest",
    "implementer_actor_id",
    "verification_obligation_id",
)
VERIFICATION_FIELDS = (
    "kind",
    "attribution",
    "actor_id",
    "event_id",
    "generation",
    "accepted_event_id",
    "candidate_id",
    "candidate_digest",
    "verification_obligation_id",
    "conclusion",
)
ATTRIBUTED_RESULT_FIELDS = ("kind", "attribution", "result")
ATTRIBUTED_ADJUDICATION_FIELDS = ("kind", "attribution", "adjudication")

M0_SOURCE_VERSION = "noetic.m0.telos-adjudication-trace/v0"
M0_PROJECTION_VERSION = "noetic.m0.telos-adjudication-projection/v0"
M0_SOURCE_FIELDS = (
    "schema_version",
    "state",
    "binding",
    "delegation",
    "accepted_generation",
    "qa_adjudication",
    "controller_result",
    "telos_adjudication",
)
M0_BINDING_FIELDS = (
    "correlation_id",
    "delegation_digest",
    "delegation_id",
    "generation",
    "goal_chain_id",
    "program_id",
    "run_id",
    "sub_goal_id",
)
M0_DELEGATION_FIELDS = ("actor_id", "event_id", "purpose", "revocation_status")
M0_ACCEPTED_FIELDS = (
    "candidate_digest",
    "candidate_id",
    "event_id",
    "generation",
    "implementer_actor_id",
    "verification_obligation_id",
)
M0_QA_FIELDS = (
    "accepted_event_id",
    "actor_id",
    "conclusion",
    "event_id",
    "verification_obligation_id",
)
M0_CONTROLLER_FIELDS = (
    "actor_id",
    "event_id",
    "evidence_event_ids",
    "result_id",
    "run_outcome",
)
M0_TELOS_FIELDS = (
    "actor_id",
    "disposition",
    "event_id",
    "evidence_event_ids",
    "result_id",
)

M1_SOURCE_VERSION = "noetic.m1.telos-recoverability-trace/v0"
M1_PROJECTION_VERSION = "noetic.m1.telos-recoverability-projection/v0"
M1_SOURCE_FIELDS = (
    "schema_version",
    "state",
    "binding",
    "delegation",
    "generation_history",
    "remediation_budget",
    "remediation_generation",
    "controller_success",
    "controller_result",
    "telos_adjudication",
)
M1_BINDING_FIELDS = (
    "correlation_id",
    "delegation_digest",
    "delegation_id",
    "goal_chain_id",
    "program_id",
    "run_id",
    "sub_goal_id",
)
M1_DELEGATION_FIELDS = (
    "actor_id",
    "event_id",
    "policy",
    "purpose",
    "revocation_status",
)
M1_HISTORY_FIELDS = ("accepted_generation", "generation", "qa_adjudication")
M1_ACCEPTED_1_FIELDS = (
    "candidate_digest",
    "candidate_id",
    "event_id",
    "implementer_actor_id",
    "verification_obligation_id",
)
M1_ACCEPTED_2_FIELDS = M1_ACCEPTED_1_FIELDS + (
    "remediation_event_id",
    "superseded_accepted_event_id",
)
M1_QA_1_FIELDS = (
    "accepted_event_id",
    "actor_id",
    "conclusion",
    "event_id",
    "finding_digest",
    "finding_id",
    "verification_obligation_id",
)
M1_QA_2_FIELDS = M0_QA_FIELDS
M1_BUDGET_FIELDS = ("authorized", "consumed", "remaining")
M1_REMEDIATION_FIELDS = (
    "event_id",
    "failed_accepted_event_id",
    "failed_qa_event_id",
    "failed_verification_obligation_id",
    "finding_digest",
    "finding_id",
    "generation",
    "remediation_ordinal",
    "target_generation",
)
M1_CONTROLLER_FIELDS = (
    "accepted_event_id",
    "actor_id",
    "candidate_digest",
    "candidate_id",
    "event_id",
    "evidence_event_ids",
    "generation",
    "qa_event_id",
    "result_id",
    "run_outcome",
    "success_event_id",
    "verification_obligation_id",
)
M1_CONTROLLER_SUCCESS_FIELDS = (
    "accepted_event_id",
    "actor_id",
    "candidate_digest",
    "candidate_id",
    "event_id",
    "generation",
    "qa_conclusion",
    "qa_event_id",
    "verification_obligation_id",
)
M1_TELOS_FIELDS = (
    "actor_id",
    "disposition",
    "event_id",
    "evidence_event_ids",
    "generation",
    "result_event_id",
    "result_id",
)
M1_REMEDIATION_GATE_FIELDS = (
    "represented",
    "kind",
    "attribution",
    "remediation_budget",
    "remediation_generation",
)

EXPLICIT_UNKNOWNS = (
    "artifact_availability_and_content",
    "semantic_correctness",
    "authenticated_actor_identity",
    "genuinely_independent_qa",
    "live_runtime_state",
    "readiness_blockage_or_critical_path",
    "current_command_authority",
    "external_effect_execution",
    "causality_not_preserved_in_projection",
)


def _fail(path: str, message: str) -> None:
    raise ObservabilityCompatibilityError(f"{path}: {message}")


def _shape(value: Any, fields: tuple[str, ...], path: str) -> dict[str, Any]:
    if type(value) is not dict:
        _fail(path, "expected object")
    if any(type(key) is not str for key in value):
        _fail(path, "object keys must be strings")
    expected = set(fields)
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing:
        _fail(path, f"missing fields: {', '.join(missing)}")
    if unknown:
        _fail(path, f"unknown fields: {', '.join(unknown)}")
    return value


def _string(value: Any, path: str) -> str:
    if type(value) is not str:
        _fail(path, "expected string")
    return value


def _integer(value: Any, path: str) -> int:
    if type(value) is not int:
        _fail(path, "expected integer (booleans are not integers)")
    return value


def _boolean(value: Any, path: str) -> bool:
    if type(value) is not bool:
        _fail(path, "expected boolean")
    return value


def _exact(value: Any, expected: Any, path: str) -> None:
    if type(value) is not type(expected) or value != expected:
        _fail(path, f"expected {expected!r}")


def _strings(value: Any, path: str) -> list[str]:
    if type(value) is not list:
        _fail(path, "expected array")
    for index, item in enumerate(value):
        _string(item, f"{path}[{index}]")
    return value


def _string_fields(value: Any, fields: tuple[str, ...], path: str) -> dict[str, Any]:
    obj = _shape(value, fields, path)
    for field in fields:
        _string(obj[field], f"{path}.{field}")
    return obj


def _validate_common(projection: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = _shape(projection, ROOT_FIELDS, "$")
    _exact(_string(root["schema_version"], "$.schema_version"), INPUT_VERSION, "$.schema_version")
    _exact(_string(root["program_id"], "$.program_id"), PROGRAM_ID, "$.program_id")
    _exact(_string(root["program_version"], "$.program_version"), PROGRAM_VERSION, "$.program_version")
    _string(root["program_instance_id"], "$.program_instance_id")
    _string(root["governing_purpose_id"], "$.governing_purpose_id")
    _string(root["source_trace_digest"], "$.source_trace_digest")
    _exact(_string(root["state"], "$.state"), "telos_adjudicated", "$.state")
    profile = _string(root["execution_profile"], "$.execution_profile")
    if profile not in (M0_PROFILE, M1_PROFILE):
        _fail("$.execution_profile", "unsupported profile")

    _string_fields(root["attention_packet"], ATTENTION_FIELDS, "$.attention_packet")
    _string_fields(root["insight_packet"], INSIGHT_FIELDS, "$.insight_packet")
    _string_fields(root["implementation_procedure"], PROCEDURE_FIELDS, "$.implementation_procedure")
    final = _shape(root["final_implementation"], FINAL_FIELDS, "$.final_implementation")
    _integer(final["generation"], "$.final_implementation.generation")
    for field in FINAL_FIELDS[1:]:
        _string(final[field], f"$.final_implementation.{field}")

    gates = _shape(root["gates"], GATE_FIELDS, "$.gates")
    attention_gate = _shape(gates["attention_to_insight_lineage"], ATTENTION_GATE_FIELDS, "$.gates.attention_to_insight_lineage")
    _exact(attention_gate["kind"], "deterministic", "$.gates.attention_to_insight_lineage.kind")
    _exact(attention_gate["determination"], "structurally_bound", "$.gates.attention_to_insight_lineage.determination")
    for field in ATTENTION_GATE_FIELDS[2:]:
        _string(attention_gate[field], f"$.gates.attention_to_insight_lineage.{field}")
    procedure_gate = _shape(gates["procedure_to_implementation_lineage"], PROCEDURE_GATE_FIELDS, "$.gates.procedure_to_implementation_lineage")
    _exact(procedure_gate["kind"], "deterministic", "$.gates.procedure_to_implementation_lineage.kind")
    _exact(procedure_gate["determination"], "structurally_bound", "$.gates.procedure_to_implementation_lineage.determination")
    for field in PROCEDURE_GATE_FIELDS[2:]:
        _string(procedure_gate[field], f"$.gates.procedure_to_implementation_lineage.{field}")
    final_gate = _shape(gates["final_implementation_binding"], FINAL_GATE_FIELDS, "$.gates.final_implementation_binding")
    _exact(final_gate["kind"], "deterministic", "$.gates.final_implementation_binding.kind")
    _exact(final_gate["determination"], "source_equal", "$.gates.final_implementation_binding.determination")
    _integer(final_gate["generation"], "$.gates.final_implementation_binding.generation")
    for field in FINAL_GATE_FIELDS[3:]:
        _string(final_gate[field], f"$.gates.final_implementation_binding.{field}")

    verification = _shape(gates["verification"], VERIFICATION_FIELDS, "$.gates.verification")
    _exact(verification["kind"], "attributed_semantic", "$.gates.verification.kind")
    _exact(verification["attribution"], "source_trace", "$.gates.verification.attribution")
    _integer(verification["generation"], "$.gates.verification.generation")
    for field in VERIFICATION_FIELDS[2:4] + VERIFICATION_FIELDS[5:]:
        _string(verification[field], f"$.gates.verification.{field}")

    controller_gate = _shape(gates["controller_result"], ATTRIBUTED_RESULT_FIELDS, "$.gates.controller_result")
    _exact(controller_gate["kind"], "attributed_semantic", "$.gates.controller_result.kind")
    _exact(controller_gate["attribution"], "source_trace", "$.gates.controller_result.attribution")
    telos_gate = _shape(gates["telos_adjudication"], ATTRIBUTED_ADJUDICATION_FIELDS, "$.gates.telos_adjudication")
    _exact(telos_gate["kind"], "attributed_semantic", "$.gates.telos_adjudication.kind")
    _exact(telos_gate["attribution"], "source_trace", "$.gates.telos_adjudication.attribution")
    source = root["source_trace_projection"]
    return root, source, gates


def _validate_m0(root: dict[str, Any], source: Any, gates: dict[str, Any]) -> list[dict[str, Any]]:
    _exact(root["source_trace_version"], M0_SOURCE_VERSION, "$.source_trace_version")
    source = _shape(source, M0_SOURCE_FIELDS, "$.source_trace_projection")
    _exact(source["schema_version"], M0_PROJECTION_VERSION, "$.source_trace_projection.schema_version")
    _exact(source["state"], "telos_adjudicated", "$.source_trace_projection.state")
    binding = _shape(source["binding"], M0_BINDING_FIELDS, "$.source_trace_projection.binding")
    _integer(binding["generation"], "$.source_trace_projection.binding.generation")
    for field in M0_BINDING_FIELDS[:3] + M0_BINDING_FIELDS[4:]:
        _string(binding[field], f"$.source_trace_projection.binding.{field}")
    _string_fields(source["delegation"], M0_DELEGATION_FIELDS, "$.source_trace_projection.delegation")
    accepted = _shape(source["accepted_generation"], M0_ACCEPTED_FIELDS, "$.source_trace_projection.accepted_generation")
    _integer(accepted["generation"], "$.source_trace_projection.accepted_generation.generation")
    for field in M0_ACCEPTED_FIELDS[:3] + M0_ACCEPTED_FIELDS[4:]:
        _string(accepted[field], f"$.source_trace_projection.accepted_generation.{field}")
    qa = _string_fields(source["qa_adjudication"], M0_QA_FIELDS, "$.source_trace_projection.qa_adjudication")
    controller = _shape(source["controller_result"], M0_CONTROLLER_FIELDS, "$.source_trace_projection.controller_result")
    for field in M0_CONTROLLER_FIELDS:
        if field == "evidence_event_ids":
            _strings(controller[field], f"$.source_trace_projection.controller_result.{field}")
        else:
            _string(controller[field], f"$.source_trace_projection.controller_result.{field}")
    telos = _shape(source["telos_adjudication"], M0_TELOS_FIELDS, "$.source_trace_projection.telos_adjudication")
    for field in M0_TELOS_FIELDS:
        if field == "evidence_event_ids":
            _strings(telos[field], f"$.source_trace_projection.telos_adjudication.{field}")
        else:
            _string(telos[field], f"$.source_trace_projection.telos_adjudication.{field}")
    remediation = _shape(gates["remediation"], ("represented",), "$.gates.remediation")
    _exact(_boolean(remediation["represented"], "$.gates.remediation.represented"), False, "$.gates.remediation.represented")
    gate_controller = _shape(gates["controller_result"]["result"], M0_CONTROLLER_FIELDS, "$.gates.controller_result.result")
    for field in M0_CONTROLLER_FIELDS:
        if field == "evidence_event_ids":
            _strings(gate_controller[field], f"$.gates.controller_result.result.{field}")
        else:
            _string(gate_controller[field], f"$.gates.controller_result.result.{field}")
    gate_telos = _shape(gates["telos_adjudication"]["adjudication"], M0_TELOS_FIELDS, "$.gates.telos_adjudication.adjudication")
    for field in M0_TELOS_FIELDS:
        if field == "evidence_event_ids":
            _strings(gate_telos[field], f"$.gates.telos_adjudication.adjudication.{field}")
        else:
            _string(gate_telos[field], f"$.gates.telos_adjudication.adjudication.{field}")
    return [{"generation": accepted["generation"], "accepted_generation": copy.deepcopy(accepted), "qa_adjudication": copy.deepcopy(qa)}]


def _validate_m1(root: dict[str, Any], source: Any, gates: dict[str, Any]) -> list[dict[str, Any]]:
    _exact(root["source_trace_version"], M1_SOURCE_VERSION, "$.source_trace_version")
    source = _shape(source, M1_SOURCE_FIELDS, "$.source_trace_projection")
    _exact(source["schema_version"], M1_PROJECTION_VERSION, "$.source_trace_projection.schema_version")
    _exact(source["state"], "telos_adjudicated", "$.source_trace_projection.state")
    _string_fields(source["binding"], M1_BINDING_FIELDS, "$.source_trace_projection.binding")
    delegation = _shape(source["delegation"], M1_DELEGATION_FIELDS, "$.source_trace_projection.delegation")
    for field in ("actor_id", "event_id", "purpose", "revocation_status"):
        _string(delegation[field], f"$.source_trace_projection.delegation.{field}")
    policy = _shape(delegation["policy"], ("max_remediation_generations",), "$.source_trace_projection.delegation.policy")
    _integer(policy["max_remediation_generations"], "$.source_trace_projection.delegation.policy.max_remediation_generations")
    history = source["generation_history"]
    if type(history) is not list or len(history) != 2:
        _fail("$.source_trace_projection.generation_history", "expected two profile history items")
    for index, (accepted_fields, qa_fields) in enumerate(((M1_ACCEPTED_1_FIELDS, M1_QA_1_FIELDS), (M1_ACCEPTED_2_FIELDS, M1_QA_2_FIELDS))):
        item_path = f"$.source_trace_projection.generation_history[{index}]"
        item = _shape(history[index], M1_HISTORY_FIELDS, item_path)
        _integer(item["generation"], f"{item_path}.generation")
        _string_fields(item["accepted_generation"], accepted_fields, f"{item_path}.accepted_generation")
        _string_fields(item["qa_adjudication"], qa_fields, f"{item_path}.qa_adjudication")
    budget = _shape(source["remediation_budget"], M1_BUDGET_FIELDS, "$.source_trace_projection.remediation_budget")
    for field in M1_BUDGET_FIELDS:
        _integer(budget[field], f"$.source_trace_projection.remediation_budget.{field}")
    remediation_generation = _shape(source["remediation_generation"], M1_REMEDIATION_FIELDS, "$.source_trace_projection.remediation_generation")
    for field in M1_REMEDIATION_FIELDS:
        if field in ("generation", "remediation_ordinal", "target_generation"):
            _integer(remediation_generation[field], f"$.source_trace_projection.remediation_generation.{field}")
        else:
            _string(remediation_generation[field], f"$.source_trace_projection.remediation_generation.{field}")
    controller_success = _shape(source["controller_success"], M1_CONTROLLER_SUCCESS_FIELDS, "$.source_trace_projection.controller_success")
    for field in M1_CONTROLLER_SUCCESS_FIELDS:
        if field == "generation":
            _integer(controller_success[field], f"$.source_trace_projection.controller_success.{field}")
        else:
            _string(controller_success[field], f"$.source_trace_projection.controller_success.{field}")
    controller = _shape(source["controller_result"], M1_CONTROLLER_FIELDS, "$.source_trace_projection.controller_result")
    for field in M1_CONTROLLER_FIELDS:
        if field == "generation":
            _integer(controller[field], f"$.source_trace_projection.controller_result.{field}")
        elif field == "evidence_event_ids":
            _strings(controller[field], f"$.source_trace_projection.controller_result.{field}")
        else:
            _string(controller[field], f"$.source_trace_projection.controller_result.{field}")
    telos = _shape(source["telos_adjudication"], M1_TELOS_FIELDS, "$.source_trace_projection.telos_adjudication")
    for field in M1_TELOS_FIELDS:
        if field == "generation":
            _integer(telos[field], f"$.source_trace_projection.telos_adjudication.{field}")
        elif field == "evidence_event_ids":
            _strings(telos[field], f"$.source_trace_projection.telos_adjudication.{field}")
        else:
            _string(telos[field], f"$.source_trace_projection.telos_adjudication.{field}")
    remediation = _shape(gates["remediation"], M1_REMEDIATION_GATE_FIELDS, "$.gates.remediation")
    _exact(_boolean(remediation["represented"], "$.gates.remediation.represented"), True, "$.gates.remediation.represented")
    _exact(remediation["kind"], "attributed_semantic", "$.gates.remediation.kind")
    _exact(remediation["attribution"], "source_trace", "$.gates.remediation.attribution")
    remediation_budget = _shape(remediation["remediation_budget"], M1_BUDGET_FIELDS, "$.gates.remediation.remediation_budget")
    for field in M1_BUDGET_FIELDS:
        _integer(remediation_budget[field], f"$.gates.remediation.remediation_budget.{field}")
    remediation_gate_generation = _shape(remediation["remediation_generation"], M1_REMEDIATION_FIELDS, "$.gates.remediation.remediation_generation")
    for field in M1_REMEDIATION_FIELDS:
        if field in ("generation", "remediation_ordinal", "target_generation"):
            _integer(remediation_gate_generation[field], f"$.gates.remediation.remediation_generation.{field}")
        else:
            _string(remediation_gate_generation[field], f"$.gates.remediation.remediation_generation.{field}")
    gate_controller = _shape(gates["controller_result"]["result"], M1_CONTROLLER_FIELDS, "$.gates.controller_result.result")
    for field in M1_CONTROLLER_FIELDS:
        if field == "generation":
            _integer(gate_controller[field], f"$.gates.controller_result.result.{field}")
        elif field == "evidence_event_ids":
            _strings(gate_controller[field], f"$.gates.controller_result.result.{field}")
        else:
            _string(gate_controller[field], f"$.gates.controller_result.result.{field}")
    gate_telos = _shape(gates["telos_adjudication"]["adjudication"], M1_TELOS_FIELDS, "$.gates.telos_adjudication.adjudication")
    for field in M1_TELOS_FIELDS:
        if field == "generation":
            _integer(gate_telos[field], f"$.gates.telos_adjudication.adjudication.{field}")
        elif field == "evidence_event_ids":
            _strings(gate_telos[field], f"$.gates.telos_adjudication.adjudication.{field}")
        else:
            _string(gate_telos[field], f"$.gates.telos_adjudication.adjudication.{field}")
    return copy.deepcopy(history)


def derive_terminal_observability(projection: Any) -> dict[str, Any]:
    """Derive a fresh presentation-only read model from an accepted projection."""
    try:
        root, source, gates = _validate_common(projection)
        profile = root["execution_profile"]
        if profile == M0_PROFILE:
            history = _validate_m0(root, source, gates)
        else:
            history = _validate_m1(root, source, gates)
        source = root["source_trace_projection"]
        return {
            "schema_version": OUTPUT_VERSION,
            "scope": {
                "view_kind": "terminal_projection",
                "claim_boundary": "structural_or_source_attributed_only",
                "live_operational_data": "not_present",
                "input_provenance": "upstream_precondition_not_authenticated",
            },
            "subject": {
                "program_id": root["program_id"],
                "program_version": root["program_version"],
                "program_instance_id": root["program_instance_id"],
                "execution_profile": profile,
                "projection_state": root["state"],
                "governing_purpose_id": root["governing_purpose_id"],
                "source": {
                    "trace_version": root["source_trace_version"],
                    "trace_digest": root["source_trace_digest"],
                    "projection_version": source["schema_version"],
                    "projection_state": source["state"],
                    "binding": copy.deepcopy(source["binding"]),
                },
            },
            "evidence": {
                "attention": {"evidence_status": "opaque_fixture_attributed_product", "value": copy.deepcopy(root["attention_packet"])},
                "insight": {"evidence_status": "opaque_fixture_attributed_product", "value": copy.deepcopy(root["insight_packet"])},
                "procedure": {"evidence_status": "opaque_fixture_attributed_procedure", "value": copy.deepcopy(root["implementation_procedure"])},
                "final_implementation": {"evidence_status": "opaque_fixture_attributed_candidate_reference", "value": copy.deepcopy(root["final_implementation"])},
                "lineage": {
                    "attention_to_insight": copy.deepcopy(gates["attention_to_insight_lineage"]),
                    "procedure_to_implementation": copy.deepcopy(gates["procedure_to_implementation_lineage"]),
                    "final_implementation_binding": copy.deepcopy(gates["final_implementation_binding"]),
                },
            },
            "qa": {
                "generation_history": history,
                "terminal_verification": copy.deepcopy(gates["verification"]),
            },
            "remediation": copy.deepcopy(gates["remediation"]),
            "controller": copy.deepcopy(gates["controller_result"]),
            "telos": {
                "delegation": {
                    "kind": "attributed_semantic",
                    "attribution": "source_trace",
                    "value": copy.deepcopy(source["delegation"]),
                },
                "adjudication": copy.deepcopy(gates["telos_adjudication"]),
            },
            "explicit_unknowns": list(EXPLICIT_UNKNOWNS),
        }
    except RecursionError as exc:
        raise ObservabilityCompatibilityError(f"$: input nesting exceeds recursion limit: {exc}") from exc


def _reject_float(value: str) -> Any:
    raise ObservabilityCompatibilityError(f"floating-point numbers are not supported: {value}")


def _reject_constant(value: str) -> Any:
    raise ObservabilityCompatibilityError(f"non-finite numbers are not supported: {value}")


def _closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ObservabilityCompatibilityError(f"duplicate object key: {key!r}")
        result[key] = value
    return result


def _load_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="ascii")
        return json.loads(text, parse_float=_reject_float, parse_constant=_reject_constant, object_pairs_hook=_closed_object)
    except RecursionError as exc:
        raise ObservabilityCompatibilityError(f"JSON nesting exceeds recursion limit: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ObservabilityCompatibilityError(f"invalid JSON: {exc}") from exc


def _render(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n").encode("ascii")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare exact read-model bytes")
    parser.add_argument("projection", type=Path, help="accepted terminal projection JSON")
    parser.add_argument("expected", type=Path, nargs="?", help="expected read model for --check")
    args = parser.parse_args(argv)
    if args.check and args.expected is None:
        parser.error("--check requires projection and expected read-model paths")
    if not args.check and args.expected is not None:
        parser.error("an expected read model is only valid with --check")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        rendered = _render(derive_terminal_observability(_load_json(args.projection)))
        if args.check:
            expected = _load_json(args.expected)
            expected_bytes = args.expected.read_bytes()
            if _render(expected) != expected_bytes:
                raise ObservabilityCompatibilityError("expected read model is not canonical presentation JSON bytes")
            if rendered != expected_bytes:
                raise ObservabilityCompatibilityError("derived read model does not match expected bytes")
            print("development.verified-change terminal observability/v1 passed exact read-model check.")
            return 0
        sys.stdout.buffer.write(rendered)
        return 0
    except (OSError, UnicodeError, ObservabilityCompatibilityError, ValueError) as exc:
        print(f"terminal observability failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
