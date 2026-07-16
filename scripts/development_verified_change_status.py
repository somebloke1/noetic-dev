#!/usr/bin/env python3
"""Provider-free terminal status view for an accepted terminal observability model."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


class TerminalStatusCompatibilityError(ValueError):
    """Raised when input is not a compatible terminal observability shape."""


INPUT_VERSION = "development.verified-change.terminal-observability/v1"
OUTPUT_VERSION = "development.verified-change.terminal-status/v1"
M0_PROFILE = "m0-direct-pass"
M1_PROFILE = "m1-bounded-remediation"

ROOT_FIELDS = (
    "schema_version",
    "scope",
    "subject",
    "evidence",
    "qa",
    "remediation",
    "controller",
    "telos",
    "explicit_unknowns",
)
SCOPE_FIELDS = ("view_kind", "claim_boundary", "live_operational_data", "input_provenance")
SUBJECT_FIELDS = (
    "program_id",
    "program_version",
    "program_instance_id",
    "execution_profile",
    "projection_state",
    "governing_purpose_id",
    "source",
)
SOURCE_FIELDS = ("trace_version", "trace_digest", "projection_version", "projection_state", "binding")
EVIDENCE_FIELDS = ("attention", "insight", "procedure", "final_implementation", "lineage")
EVIDENCE_VALUE_FIELDS = ("evidence_status", "value")
FINAL_VALUE_FIELDS = (
    "generation",
    "accepted_event_id",
    "candidate_id",
    "candidate_digest",
    "implementation_procedure_artifact_id",
    "implementer_actor_id",
    "verification_obligation_id",
)
QA_FIELDS = ("generation_history", "terminal_verification")
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
TELOS_FIELDS = ("delegation", "adjudication")
TELOS_DELEGATION_FIELDS = ("kind", "attribution", "value")
M0_CONTROLLER_FIELDS = ("actor_id", "event_id", "evidence_event_ids", "result_id", "run_outcome")
M0_TELOS_FIELDS = ("actor_id", "disposition", "event_id", "evidence_event_ids", "result_id")
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
M1_TELOS_FIELDS = ("actor_id", "disposition", "event_id", "evidence_event_ids", "generation", "result_event_id", "result_id")
M0_ACCEPTED_FIELDS = ("candidate_digest", "candidate_id", "event_id", "generation", "implementer_actor_id", "verification_obligation_id")
M1_ACCEPTED_BASE_FIELDS = ("candidate_digest", "candidate_id", "event_id", "implementer_actor_id", "verification_obligation_id")
M1_ACCEPTED_REMEDIATED_FIELDS = M1_ACCEPTED_BASE_FIELDS + ("remediation_event_id", "superseded_accepted_event_id")
M0_QA_FIELDS = ("accepted_event_id", "actor_id", "conclusion", "event_id", "verification_obligation_id")
M1_QA_FAILED_FIELDS = M0_QA_FIELDS + ("finding_digest", "finding_id")
M1_QA_PASS_FIELDS = M0_QA_FIELDS
M1_REMEDIATION_FIELDS = ("represented", "kind", "attribution", "remediation_budget", "remediation_generation")
M1_BUDGET_FIELDS = ("authorized", "consumed", "remaining")
M1_REMEDIATION_GENERATION_FIELDS = (
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
REQUIRED_UNKNOWNS = (
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
    raise TerminalStatusCompatibilityError(f"{path}: {message}")


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


def _copy_string_map(value: Any, path: str) -> dict[str, Any]:
    if type(value) is not dict:
        _fail(path, "expected object")
    for field, item in value.items():
        _string(field, f"{path}.<key>")
        _string(item, f"{path}.{field}")
    return copy.deepcopy(value)


def _validate_binding(value: Any, path: str) -> dict[str, Any]:
    if type(value) is not dict:
        _fail(path, "expected object")
    for field, item in value.items():
        _string(field, f"{path}.<key>")
        if field == "generation":
            _integer(item, f"{path}.{field}")
        else:
            _string(item, f"{path}.{field}")
    return value


def _validate_subject(subject: Any) -> dict[str, Any]:
    obj = _shape(subject, SUBJECT_FIELDS, "$.subject")
    for field in SUBJECT_FIELDS[:-1]:
        _string(obj[field], f"$.subject.{field}")
    if obj["execution_profile"] not in (M0_PROFILE, M1_PROFILE):
        _fail("$.subject.execution_profile", "unsupported profile")
    source = _shape(obj["source"], SOURCE_FIELDS, "$.subject.source")
    for field in SOURCE_FIELDS[:-1]:
        _string(source[field], f"$.subject.source.{field}")
    _validate_binding(source["binding"], "$.subject.source.binding")
    return obj


def _validate_common(observability: Any) -> dict[str, Any]:
    root = _shape(observability, ROOT_FIELDS, "$")
    _exact(_string(root["schema_version"], "$.schema_version"), INPUT_VERSION, "$.schema_version")
    scope = _shape(root["scope"], SCOPE_FIELDS, "$.scope")
    _exact(scope["view_kind"], "terminal_projection", "$.scope.view_kind")
    _exact(scope["claim_boundary"], "structural_or_source_attributed_only", "$.scope.claim_boundary")
    _exact(scope["live_operational_data"], "not_present", "$.scope.live_operational_data")
    _exact(scope["input_provenance"], "upstream_precondition_not_authenticated", "$.scope.input_provenance")
    subject = _validate_subject(root["subject"])
    evidence = _shape(root["evidence"], EVIDENCE_FIELDS, "$.evidence")
    for field in ("attention", "insight", "procedure", "final_implementation"):
        _shape(evidence[field], EVIDENCE_VALUE_FIELDS, f"$.evidence.{field}")
        _string(evidence[field]["evidence_status"], f"$.evidence.{field}.evidence_status")
        if type(evidence[field]["value"]) is not dict:
            _fail(f"$.evidence.{field}.value", "expected object")
    final = _shape(evidence["final_implementation"]["value"], FINAL_VALUE_FIELDS, "$.evidence.final_implementation.value")
    _integer(final["generation"], "$.evidence.final_implementation.value.generation")
    for field in FINAL_VALUE_FIELDS[1:]:
        _string(final[field], f"$.evidence.final_implementation.value.{field}")
    _shape(evidence["lineage"], ("attention_to_insight", "procedure_to_implementation", "final_implementation_binding"), "$.evidence.lineage")
    qa = _shape(root["qa"], QA_FIELDS, "$.qa")
    verification = _shape(qa["terminal_verification"], VERIFICATION_FIELDS, "$.qa.terminal_verification")
    _exact(verification["kind"], "attributed_semantic", "$.qa.terminal_verification.kind")
    _exact(verification["attribution"], "source_trace", "$.qa.terminal_verification.attribution")
    _integer(verification["generation"], "$.qa.terminal_verification.generation")
    for field in VERIFICATION_FIELDS[2:4] + VERIFICATION_FIELDS[5:]:
        _string(verification[field], f"$.qa.terminal_verification.{field}")
    controller = _shape(root["controller"], ATTRIBUTED_RESULT_FIELDS, "$.controller")
    _exact(controller["kind"], "attributed_semantic", "$.controller.kind")
    _exact(controller["attribution"], "source_trace", "$.controller.attribution")
    telos = _shape(root["telos"], TELOS_FIELDS, "$.telos")
    delegation = _shape(telos["delegation"], TELOS_DELEGATION_FIELDS, "$.telos.delegation")
    _exact(delegation["kind"], "attributed_semantic", "$.telos.delegation.kind")
    _exact(delegation["attribution"], "source_trace", "$.telos.delegation.attribution")
    adjudication = _shape(telos["adjudication"], ("kind", "attribution", "adjudication"), "$.telos.adjudication")
    _exact(adjudication["kind"], "attributed_semantic", "$.telos.adjudication.kind")
    _exact(adjudication["attribution"], "source_trace", "$.telos.adjudication.attribution")
    if tuple(_strings(root["explicit_unknowns"], "$.explicit_unknowns")) != REQUIRED_UNKNOWNS:
        _fail("$.explicit_unknowns", "unexpected unknown set or order")
    return root


def _controller_status(result: dict[str, Any], profile: str) -> dict[str, Any]:
    fields = M0_CONTROLLER_FIELDS if profile == M0_PROFILE else M1_CONTROLLER_FIELDS
    obj = _shape(result, fields, "$.controller.result")
    for field in fields:
        if field == "generation":
            _integer(obj[field], f"$.controller.result.{field}")
        elif field == "evidence_event_ids":
            _strings(obj[field], f"$.controller.result.{field}")
        else:
            _string(obj[field], f"$.controller.result.{field}")
    status = {
        "kind": "source_attributed_controller_result",
        "run_outcome": obj["run_outcome"],
        "event_id": obj["event_id"],
        "result_id": obj["result_id"],
        "evidence_event_ids": copy.deepcopy(obj["evidence_event_ids"]),
        "no_telos_disposition": True,
        "no_command_authority": True,
    }
    if profile == M1_PROFILE:
        status.update({
            "generation": obj["generation"],
            "accepted_event_id": obj["accepted_event_id"],
            "qa_event_id": obj["qa_event_id"],
            "success_event_id": obj["success_event_id"],
        })
    return status


def _telos_status(adjudication: dict[str, Any], profile: str) -> dict[str, Any]:
    fields = M0_TELOS_FIELDS if profile == M0_PROFILE else M1_TELOS_FIELDS
    obj = _shape(adjudication, fields, "$.telos.adjudication.adjudication")
    for field in fields:
        if field == "generation":
            _integer(obj[field], f"$.telos.adjudication.adjudication.{field}")
        elif field == "evidence_event_ids":
            _strings(obj[field], f"$.telos.adjudication.adjudication.{field}")
        else:
            _string(obj[field], f"$.telos.adjudication.adjudication.{field}")
    status = {
        "kind": "source_attributed_telos_adjudication",
        "disposition": obj["disposition"],
        "event_id": obj["event_id"],
        "result_id": obj["result_id"],
        "evidence_event_ids": copy.deepcopy(obj["evidence_event_ids"]),
        "no_controller_success_inference": True,
        "no_command_authority": True,
    }
    if profile == M1_PROFILE:
        status.update({"generation": obj["generation"], "result_event_id": obj["result_event_id"]})
    return status


def _qa_status(qa: dict[str, Any], profile: str) -> dict[str, Any]:
    history = qa["generation_history"]
    if type(history) is not list or not history:
        _fail("$.qa.generation_history", "expected non-empty array")
    if profile == M0_PROFILE and len(history) != 1:
        _fail("$.qa.generation_history", "M0 status requires exactly one generation")
    if profile == M1_PROFILE and len(history) != 2:
        _fail("$.qa.generation_history", "M1 status requires exactly two generations")
    generations = []
    for index, item in enumerate(history):
        path = f"$.qa.generation_history[{index}]"
        item = _shape(item, ("generation", "accepted_generation", "qa_adjudication"), path)
        generation = _integer(item["generation"], f"{path}.generation")
        if type(item["accepted_generation"]) is not dict:
            _fail(f"{path}.accepted_generation", "expected object")
        if type(item["qa_adjudication"]) is not dict:
            _fail(f"{path}.qa_adjudication", "expected object")
        if profile == M0_PROFILE:
            accepted_fields = M0_ACCEPTED_FIELDS
            qa_fields = M0_QA_FIELDS
        elif index == 0:
            accepted_fields = M1_ACCEPTED_BASE_FIELDS
            qa_fields = M1_QA_FAILED_FIELDS
        else:
            accepted_fields = M1_ACCEPTED_REMEDIATED_FIELDS
            qa_fields = M1_QA_PASS_FIELDS
        accepted = _shape(item["accepted_generation"], accepted_fields, f"{path}.accepted_generation")
        if "generation" in accepted:
            _integer(accepted["generation"], f"{path}.accepted_generation.generation")
        for field in accepted_fields:
            if field != "generation":
                _string(accepted[field], f"{path}.accepted_generation.{field}")
        adjudication = _string_fields(item["qa_adjudication"], qa_fields, f"{path}.qa_adjudication")
        generations.append({
            "generation": generation,
            "accepted_event_id": accepted["event_id"],
            "qa_event_id": adjudication["event_id"],
            "conclusion": adjudication["conclusion"],
            "finding_present": "finding_id" in adjudication,
            "remediation_reference_present": "remediation_event_id" in accepted,
        })
    terminal = qa["terminal_verification"]
    return {
        "terminal_generation": terminal["generation"],
        "terminal_conclusion": terminal["conclusion"],
        "terminal_event_id": terminal["event_id"],
        "generations": generations,
        "semantic_truth_not_judged": True,
        "independence_not_authenticated": True,
    }


def _remediation_status(remediation: Any, profile: str) -> dict[str, Any]:
    if type(remediation) is not dict:
        _fail("$.remediation", "expected object")
    if profile == M0_PROFILE and set(remediation) != {"represented"}:
        _fail("$.remediation", "M0 status requires exact no-remediation shape")
    obj = _shape(remediation, ("represented",) if set(remediation) == {"represented"} else M1_REMEDIATION_FIELDS, "$.remediation")
    represented = _boolean(obj["represented"], "$.remediation.represented")
    if profile == M0_PROFILE and represented:
        _fail("$.remediation.represented", "M0 status cannot represent remediation")
    if profile == M1_PROFILE and not represented:
        _fail("$.remediation.represented", "M1 status requires represented remediation")
    if set(obj) == {"represented"} and represented:
        _fail("$.remediation", "represented true requires source-attributed remediation fields")
    if not represented:
        return {"represented": False, "no_zero_budget_inferred": True}
    _exact(obj["kind"], "attributed_semantic", "$.remediation.kind")
    _exact(obj["attribution"], "source_trace", "$.remediation.attribution")
    budget = _shape(obj["remediation_budget"], M1_BUDGET_FIELDS, "$.remediation.remediation_budget")
    for field in M1_BUDGET_FIELDS:
        _integer(budget[field], f"$.remediation.remediation_budget.{field}")
    generation = _shape(obj["remediation_generation"], M1_REMEDIATION_GENERATION_FIELDS, "$.remediation.remediation_generation")
    for field in M1_REMEDIATION_GENERATION_FIELDS:
        if field in ("generation", "remediation_ordinal", "target_generation"):
            _integer(generation[field], f"$.remediation.remediation_generation.{field}")
        else:
            _string(generation[field], f"$.remediation.remediation_generation.{field}")
    return {
        "represented": True,
        "attribution": "source_trace",
        "budget": copy.deepcopy(budget),
        "generation": copy.deepcopy(generation),
    }


def _operational_status() -> dict[str, Any]:
    return {
        "readiness": {
            "status": "not_derivable_from_terminal_projection",
            "reason": "terminal input has no live runtime state or ready/blocked evaluation",
            "supporting_unknown": "readiness_blockage_or_critical_path",
        },
        "current_command_authority": {
            "status": "not_derivable_from_terminal_projection",
            "reason": "terminal input has no current command actor, approval, or act-from surface",
            "supporting_unknown": "current_command_authority",
        },
        "critical_path": {
            "status": "not_derivable_from_terminal_projection",
            "reason": "terminal input has no dependency graph, queue, or live blocker state",
            "supporting_unknown": "readiness_blockage_or_critical_path",
        },
        "causal_graph": {
            "status": "not_derivable_from_terminal_projection",
            "reason": "terminal input preserves named references but not immediate caused_by edges or a complete graph",
            "supporting_unknown": "causality_not_preserved_in_projection",
        },
    }


def derive_terminal_status(observability: Any) -> dict[str, Any]:
    """Derive a fresh status explanation from accepted terminal observability."""
    try:
        root = _validate_common(observability)
        profile = root["subject"]["execution_profile"]
        controller_status = _controller_status(root["controller"]["result"], profile)
        telos_status = _telos_status(root["telos"]["adjudication"]["adjudication"], profile)
        qa_status = _qa_status(root["qa"], profile)
        remediation_status = _remediation_status(root["remediation"], profile)
        final = root["evidence"]["final_implementation"]["value"]
        return {
            "schema_version": OUTPUT_VERSION,
            "scope": {
                "view_kind": "terminal_status_explanation",
                "claim_boundary": "terminal_observability_projection_only",
                "live_operational_data": "not_present",
                "input_provenance": "upstream_precondition_not_authenticated",
            },
            "subject": copy.deepcopy(root["subject"]),
            "controller_status": controller_status,
            "telos_status": telos_status,
            "qa_status": qa_status,
            "remediation_status": remediation_status,
            "operational_status": _operational_status(),
            "references": {
                "source_trace_digest": root["subject"]["source"]["trace_digest"],
                "candidate_id": final["candidate_id"],
                "candidate_digest": final["candidate_digest"],
                "verification_obligation_id": final["verification_obligation_id"],
            },
            "explicit_unknowns": copy.deepcopy(root["explicit_unknowns"]),
        }
    except RecursionError as exc:
        raise TerminalStatusCompatibilityError(f"$: input nesting exceeds recursion limit: {exc}") from exc


def _reject_float(value: str) -> Any:
    raise TerminalStatusCompatibilityError(f"floating-point numbers are not supported: {value}")


def _reject_constant(value: str) -> Any:
    raise TerminalStatusCompatibilityError(f"non-finite numbers are not supported: {value}")


def _closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TerminalStatusCompatibilityError(f"duplicate object key: {key!r}")
        result[key] = value
    return result


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_float=_reject_float, parse_constant=_reject_constant, object_pairs_hook=_closed_object)
    except RecursionError as exc:
        raise TerminalStatusCompatibilityError(f"JSON nesting exceeds recursion limit: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TerminalStatusCompatibilityError(f"invalid JSON: {exc}") from exc


def _render(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n").encode("ascii")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare exact status bytes")
    parser.add_argument("observability", type=Path, help="accepted terminal observability JSON")
    parser.add_argument("expected", type=Path, nargs="?", help="expected status model for --check")
    args = parser.parse_args(argv)
    if args.check and args.expected is None:
        parser.error("--check requires observability and expected status paths")
    if not args.check and args.expected is not None:
        parser.error("an expected status model is only valid with --check")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        rendered = _render(derive_terminal_status(_load_json(args.observability)))
        if args.check:
            expected = _load_json(args.expected)
            expected_bytes = args.expected.read_bytes()
            if _render(expected) != expected_bytes:
                raise TerminalStatusCompatibilityError("expected status model is not canonical presentation JSON bytes")
            if rendered != expected_bytes:
                raise TerminalStatusCompatibilityError("derived status model does not match expected bytes")
            print("development.verified-change terminal status/v1 passed exact status check.")
            return 0
        sys.stdout.buffer.write(rendered)
        return 0
    except (OSError, UnicodeError, TerminalStatusCompatibilityError, ValueError) as exc:
        print(f"terminal status failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
