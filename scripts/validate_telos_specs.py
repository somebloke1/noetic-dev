#!/usr/bin/env python3
"""Dependency-free validation for Telos delegation/controller contracts."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec" / "telos" / "v0"
CONTROLLER = ROOT / "spec" / "controller" / "v0"
EVENTS = ROOT / "spec" / "events" / "v0"
DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
SECRET_PATTERNS = [
    re.compile(r"Bearer\s+\S+", re.I),
    re.compile(r"(?:sk-|xai-|hf_|tgp_v1_)[A-Za-z0-9_-]{8,}"),
    re.compile(r"[a-z][a-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@", re.I),
]


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot load {path.relative_to(ROOT)}: {error}") from error


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical_digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def contains_secret(value: Any) -> bool:
    if isinstance(value, dict):
        return any(contains_secret(key) or contains_secret(child) for key, child in value.items())
    if isinstance(value, list):
        return any(contains_secret(child) for child in value)
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in SECRET_PATTERNS)
    return False


def shape_errors(value: dict[str, Any], schema: dict[str, Any], label: str) -> list[str]:
    required = set(schema["required"])
    properties = set(schema["properties"])
    errors = [f"{label} missing required field: {field}" for field in sorted(required - value.keys())]
    errors.extend(f"{label} unknown field: {field}" for field in sorted(value.keys() - properties))
    return errors


def delegation_errors(
    delegation: dict[str, Any], schema: dict[str, Any], telos_commands: set[str], expected_clause_version: int
) -> list[str]:
    errors = shape_errors(delegation, schema, "delegation")
    if errors:
        return errors
    if delegation["schema_version"] != "telos.delegation/v0":
        errors.append("delegation schema version mismatch")

    commands = set(delegation["scope"]["allowed_commands"])
    permissions = set(delegation["authority"]["permissions"])
    for command in commands:
        if command not in telos_commands:
            errors.append("delegation command not allowed to Telos")
    if permissions != commands:
        errors.append("authority permissions must equal narrowed command scope")
    internal = {"run.reconcile", "scheduler.tick", "lease.expire", "effect.receipt", "verification.adjudicate"}
    if commands & internal:
        errors.append("delegation contains internal controller authority")

    authority = delegation["authority"]
    try:
        issued = parse_time(authority["issued_at"])
        not_before = parse_time(authority["not_before"])
        expires = parse_time(authority["expires_at"])
        created = parse_time(delegation["created_at"])
        if not (issued <= not_before <= created < expires):
            errors.append("delegation created outside authority window")
    except (TypeError, ValueError):
        errors.append("delegation authority time is invalid")
    if authority["revocation_ref"] is not None:
        errors.append("delegation authority is revoked")

    run_id = delegation["controller_target"]["run_id"]
    run_subjects = {
        subject["subject_id"]
        for subject in delegation["scope"]["allowed_subjects"]
        if subject.get("subject_type") == "run"
    }
    if run_id not in run_subjects:
        errors.append("controller run is outside delegation scope")
    if delegation["controller_target"]["expected_run_version"] != 0:
        errors.append("new delegated run must target version zero")

    objective = delegation["purpose"]["objective"]
    expected_objective_digest = "sha256:" + hashlib.sha256(objective.encode("utf-8")).hexdigest()
    if delegation["owner"]["objective_digest"] != expected_objective_digest:
        errors.append("objective digest mismatch")
    if delegation["owner"]["reproductive_clause_version"] != expected_clause_version:
        errors.append("fixture purpose version is stale")
    if not delegation["purpose"]["governing_principles"] or not delegation["purpose"]["acceptance_refs"]:
        errors.append("delegation purpose is incomplete")

    attempts = delegation["retry_policy"]["max_dispatch_attempts"]
    if not isinstance(attempts, int) or not 1 <= attempts <= 10:
        errors.append("dispatch retry count is out of bounds")
    if delegation["retry_policy"]["idempotency_scope"] != "delegation_contract_digest":
        errors.append("dispatch idempotency scope drift")
    if delegation["cancellation_policy"]["command_type"] != "run.abort":
        errors.append("cancellation must use run.abort")
    if contains_secret(delegation):
        errors.append("delegation contains secret-shaped value")
    return errors


def result_errors(
    result: dict[str, Any], schema: dict[str, Any], delegation: dict[str, Any], digest: str
) -> list[str]:
    errors = shape_errors(result, schema, "result")
    if "sub_goal_status" in result:
        errors.append("result cannot mutate Telos sub-goal status")
    if errors:
        return errors
    if result["schema_version"] != "telos.delegation-result/v0":
        errors.append("result schema version mismatch")
    if result["delegation_id"] != delegation["delegation_id"]:
        errors.append("result delegation identity mismatch")
    if result["delegation_contract_digest"] != digest:
        errors.append("result delegation digest mismatch")
    if result["run_id"] != delegation["controller_target"]["run_id"]:
        errors.append("result run identity mismatch")
    if result["status"] == "requires_decision" and not result["interaction_ref"]:
        errors.append("requires_decision result needs interaction_ref")
    if result["status"] in {"succeeded", "failed", "cancelled", "expired"} and not result["controller_final_event_id"]:
        errors.append("terminal result needs controller_final_event_id")
    if contains_secret(result):
        errors.append("result contains secret-shaped value")
    return errors


def set_path(target: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current: Any = target
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


def check_transitions(table: dict[str, Any]) -> None:
    ensure(table["schema_version"] == "telos.delegation-transitions/v0", "delegation transition version drift")
    states = set(table["states"])
    terminal = set(table["terminal"])
    initial = table["initial"]
    ensure(initial in states and initial not in terminal, "invalid delegation initial state")
    ensure(terminal <= states, "invalid delegation terminal states")
    outgoing = {state: set() for state in states}
    keys: set[tuple[str, str]] = set()
    for transition in table["transitions"]:
        key = (transition["from"], transition["event"])
        ensure(key not in keys, f"nondeterministic delegation transition: {key}")
        ensure(transition["from"] not in terminal, "terminal delegation state has an exit")
        ensure(transition["from"] in states and transition["to"] in states, "delegation transition state drift")
        keys.add(key)
        outgoing[transition["from"]].add(transition["to"])
    reached = {initial}
    queue = deque([initial])
    while queue:
        for state in outgoing[queue.popleft()]:
            if state not in reached:
                reached.add(state)
                queue.append(state)
    ensure(reached == states, f"unreachable delegation states: {sorted(states - reached)}")
    ensure(all(outgoing[state] for state in states - terminal), "nonterminal delegation state has no exit")
    ownership = table["ownership"]
    ensure(ownership["telos_sub_goal_status_while_delegated"] == "delegated-pending", "delegated ownership status drift")
    rule = ownership["terminal_result_rule"].lower()
    ensure("never directly completes or blocks" in rule and "telos adjudicates" in rule, "result ownership rule weakened")


def check_binding(binding: dict[str, Any], telos_commands: set[str], event_schema: dict[str, Any]) -> None:
    ensure(binding["schema_version"] == "telos.controller-binding/v0", "binding version drift")
    for name, mapping in binding["outbound"].items():
        ensure(mapping["actor_type"] == "telos", f"{name}: non-Telos outbound actor")
        ensure(mapping["command_type"] in telos_commands, f"{name}: command outside Telos authority")
        ensure("{" in mapping["idempotency_key"], f"{name}: idempotency template missing identity")
    event_classes = set(event_schema["properties"]["event_class"]["enum"])
    for mapping in binding["inbound"].values():
        if "event_class" in mapping:
            ensure(mapping["event_class"] in event_classes, "binding event class drift")
    rules = " ".join(binding["rules"]).lower()
    for phrase in ("same idempotency key", "expected_version", "expired or revoked", "never mutate telos sub-goal status"):
        ensure(phrase in rules, f"binding rule missing: {phrase}")


def check_examples(
    delegation_schema: dict[str, Any], result_schema: dict[str, Any], telos_commands: set[str]
) -> None:
    delegation = load(SPEC / "examples" / "valid-delegation.json")
    result = load(SPEC / "examples" / "valid-result.json")
    digest = canonical_digest(delegation)
    ensure(not delegation_errors(delegation, delegation_schema, telos_commands, 5), "valid delegation rejected")
    ensure(not result_errors(result, result_schema, delegation, digest), "valid result rejected")

    cases = load(SPEC / "examples" / "invalid-delegations.json")["cases"]
    for case in cases:
        attacked = copy.deepcopy(delegation)
        for path, value in case["mutations"].items():
            set_path(attacked, path, value)
        errors = delegation_errors(attacked, delegation_schema, telos_commands, 5)
        ensure(any(case["expected_error"] in error for error in errors), f"{case['name']}: {errors}")

    result_cases = load(SPEC / "examples" / "invalid-results.json")["cases"]
    for case in result_cases:
        attacked = copy.deepcopy(result)
        for path, value in case["mutations"].items():
            set_path(attacked, path, value)
        errors = result_errors(attacked, result_schema, delegation, digest)
        ensure(any(case["expected_error"] in error for error in errors), f"{case['name']}: {errors}")


def check_docs() -> None:
    text = (ROOT / "docs" / "telos-delegation-contract.md").read_text(encoding="utf-8").lower()
    for phrase in (
        "telos remains", "telos performs p3", "delegated-pending", "same intent", "cancellation/terminal-result race",
        "expired or revoked", "opaque references", "no runtime dispatcher",
    ):
        ensure(phrase in text, f"delegation documentation omits {phrase!r}")


def main() -> int:
    try:
        delegation_schema = load(SPEC / "delegation.schema.json")
        result_schema = load(SPEC / "delegation-result.schema.json")
        transitions = load(SPEC / "delegation-transitions.json")
        binding = load(SPEC / "controller-binding.json")
        authority = load(CONTROLLER / "authority-matrix.json")
        event_schema = load(EVENTS / "cognitional-event.schema.json")
        telos_commands = set(authority["actors"]["telos"]["allow"])
        ensure(delegation_schema["additionalProperties"] is False, "delegation root must be strict")
        ensure(result_schema["additionalProperties"] is False, "result root must be strict")
        check_transitions(transitions)
        check_binding(binding, telos_commands, event_schema)
        check_examples(delegation_schema, result_schema, telos_commands)
        check_docs()
    except (AssertionError, KeyError, TypeError, ValueError) as error:
        print(f"Telos delegation specification validation failed: {error}", file=sys.stderr)
        return 1
    print("Telos delegation v0 specification validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
