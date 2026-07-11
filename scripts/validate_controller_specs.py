#!/usr/bin/env python3
"""Dependency-free cross-document validation for controller v0 contracts."""

from __future__ import annotations

import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec" / "controller" / "v0"
EVENT_TYPE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
RFC3339_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
SENSITIVE_KEY_PARTS = {
    "password",
    "secret",
    "token",
    "credential",
    "full_prompt",
    "private_artifact",
    "critical_contact",
    "phone_number",
}


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load(relative: str) -> Any:
    path = SPEC / relative
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot load {path.relative_to(ROOT)}: {error}") from error


def enum_at(schema: dict[str, Any], *keys: str) -> list[str]:
    value: Any = schema
    for key in keys:
        value = value[key]
    ensure(isinstance(value, list), f"{'.'.join(keys)} must be a list")
    ensure(all(isinstance(item, str) for item in value), f"{'.'.join(keys)} must contain strings")
    return value


def is_type(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, True)


def validate_schema(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Validate the JSON Schema subset used by the v0 examples."""
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        types = [expected] if isinstance(expected, str) else expected
        if not any(is_type(value, item) for item in types):
            return [f"{path}: expected type {types}, got {type(value).__name__}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} not in enum")

    if isinstance(value, dict):
        required = set(schema.get("required", []))
        missing = sorted(required - value.keys())
        errors.extend(f"{path}: missing required property {name!r}" for name in missing)
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = sorted(value.keys() - properties.keys())
            errors.extend(f"{path}: unknown property {name!r}" for name in unknown)
        for name, child in value.items():
            if name in properties:
                errors.extend(validate_schema(child, properties[name], f"{path}.{name}"))
        property_names = schema.get("propertyNames", {})
        allowed_pattern = property_names.get("pattern")
        denied_pattern = property_names.get("not", {}).get("pattern")
        for name in value:
            if allowed_pattern and not re.fullmatch(allowed_pattern, name):
                errors.append(f"{path}: property name must be lower_snake_case: {name!r}")
            if denied_pattern and re.search(denied_pattern, name):
                errors.append(f"{path}: privacy-forbidden property name {name!r}")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: too few items")
        if schema.get("uniqueItems"):
            canonical = [json.dumps(item, sort_keys=True) for item in value]
            if len(canonical) != len(set(canonical)):
                errors.append(f"{path}: duplicate items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, child in enumerate(value):
                errors.extend(validate_schema(child, item_schema, f"{path}[{index}]"))

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: string is too short")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: does not match required pattern")
        if schema.get("format") == "date-time" and not RFC3339_UTC.fullmatch(value):
            errors.append(f"{path}: example timestamp must be RFC 3339 UTC")
    if isinstance(value, int) and not isinstance(value, bool) and value < schema.get("minimum", value):
        errors.append(f"{path}: below minimum")

    for clause in schema.get("allOf", []):
        condition = clause.get("if")
        if condition is None or not validate_schema(value, condition, path):
            errors.extend(validate_schema(value, clause.get("then", {}), path))
    return errors


def check_schema_basics(name: str, schema: dict[str, Any]) -> None:
    ensure(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{name}: draft")
    expected_prefix = "https://github.com/somebloke1/noetic-dev/spec/controller/v0/"
    ensure(schema.get("$id", "").startswith(expected_prefix), f"{name}: versioned $id")
    ensure(schema.get("type") == "object", f"{name}: root type")
    ensure(schema.get("additionalProperties") is False, f"{name}: root must be strict")
    required = schema.get("required")
    properties = schema.get("properties")
    ensure(isinstance(required, list) and required, f"{name}: required list")
    ensure(len(required) == len(set(required)), f"{name}: duplicate required property")
    ensure(isinstance(properties, dict), f"{name}: properties")
    ensure(set(required) <= set(properties), f"{name}: required property missing definition")


def check_authority(command_schema: dict[str, Any], authority: dict[str, Any]) -> None:
    schema_commands = set(enum_at(command_schema, "properties", "command_type", "enum"))
    schema_actors = set(enum_at(command_schema, "properties", "actor", "properties", "actor_type", "enum"))
    commands = authority.get("commands", [])
    actors = authority.get("actors", {})
    ensure(authority.get("schema_version") == "controller.authority/v0", "authority schema version")
    ensure(len(commands) == len(set(commands)), "duplicate authority command")
    ensure(set(commands) == schema_commands, "command schema/authority matrix drift")
    ensure(set(actors) == schema_actors, "actor schema/authority matrix drift")

    allowed_by: dict[str, set[str]] = {command: set() for command in commands}
    for actor, decision in actors.items():
        allowed = decision.get("allow", [])
        denied = decision.get("deny", [])
        ensure(len(allowed) == len(set(allowed)), f"{actor}: duplicate allow")
        ensure(len(denied) == len(set(denied)), f"{actor}: duplicate deny")
        ensure(not (set(allowed) & set(denied)), f"{actor}: command both allowed and denied")
        ensure(set(allowed) | set(denied) == schema_commands, f"{actor}: incomplete authority coverage")
        for command in allowed:
            allowed_by[command].add(actor)

    ensure(all(allowed_by.values()), "every command needs at least one authorized actor")
    ensure(set(actors["adapter"]["allow"]) == {"effect.receipt"}, "adapter authority must be receipt-only")
    internal = {"run.reconcile", "scheduler.tick", "lease.expire"}
    ensure(set(actors["controller"]["allow"]) == internal, "controller authority must be internal-only")
    ensure(not (internal & set(actors["implementation_agent"]["allow"])), "implementation agent has internal authority")
    ensure(not (internal & set(actors["qa_agent"]["allow"])), "QA agent has internal authority")
    ensure("verification.adjudicate" not in actors["implementation_agent"]["allow"], "implementation agent can self-adjudicate")
    ensure("publication.request" not in actors["qa_agent"]["allow"], "QA agent can publish")
    rules = " ".join(authority.get("rules", [])).lower()
    ensure("narrow" in rules and "never broaden" in rules, "authority attenuation rule missing")
    ensure("fail-closed" in rules and "no domain transition" in rules, "denial effect rule missing")


def check_transitions(
    command_schema: dict[str, Any], event_schema: dict[str, Any], tables: dict[str, Any]
) -> None:
    command_aggregates = set(enum_at(command_schema, "properties", "aggregate_type", "enum"))
    event_aggregates = set(enum_at(event_schema, "properties", "aggregate_type", "enum"))
    aggregates = tables.get("aggregates", {})
    ensure(tables.get("schema_version") == "controller.transitions/v0", "transition schema version")
    ensure(command_aggregates == event_aggregates, "command/event aggregate drift")
    ensure(set(aggregates) == event_aggregates, "aggregate transition table coverage drift")

    all_events: set[str] = set()
    for aggregate, table in aggregates.items():
        states = table.get("states", [])
        terminal = set(table.get("terminal", []))
        initial = table.get("initial")
        transitions = table.get("transitions", [])
        ensure(states and len(states) == len(set(states)), f"{aggregate}: states must be unique")
        ensure(initial in states and initial not in terminal, f"{aggregate}: invalid initial state")
        ensure(terminal and terminal <= set(states), f"{aggregate}: invalid terminal states")
        seen_pairs: set[tuple[str, str]] = set()
        outgoing: dict[str, set[str]] = {state: set() for state in states}
        for transition in transitions:
            ensure(set(transition) == {"from", "event", "to"}, f"{aggregate}: malformed transition")
            source, event, target = transition["from"], transition["event"], transition["to"]
            ensure(source in states and target in states, f"{aggregate}: transition references unknown state")
            ensure(EVENT_TYPE.fullmatch(event) is not None, f"{aggregate}: invalid event type {event!r}")
            ensure(event.startswith(f"{aggregate}."), f"{aggregate}: event has wrong aggregate prefix")
            ensure((source, event) not in seen_pairs, f"{aggregate}: nondeterministic duplicate reducer key")
            ensure(source not in terminal, f"{aggregate}: terminal state has outgoing transition")
            seen_pairs.add((source, event))
            outgoing[source].add(target)
            all_events.add(event)
        for state in set(states) - terminal:
            ensure(outgoing[state], f"{aggregate}: nonterminal state {state!r} has no exit")

        reached = {initial}
        queue = deque([initial])
        while queue:
            for target in outgoing[queue.popleft()]:
                if target not in reached:
                    reached.add(target)
                    queue.append(target)
        ensure(reached == set(states), f"{aggregate}: unreachable states {sorted(set(states) - reached)}")

    ensure(all_events, "transition tables must declare events")


def graph_errors(program: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    nodes = program.get("nodes", [])
    node_ids = [node.get("node_id") for node in nodes]
    if len(node_ids) != len(set(node_ids)):
        errors.append("duplicate node_id")
    by_id = {node["node_id"]: node for node in nodes if isinstance(node.get("node_id"), str)}
    barriers = program.get("barriers", [])
    barrier_ids = [barrier.get("barrier_id") for barrier in barriers]
    if len(barrier_ids) != len(set(barrier_ids)):
        errors.append("duplicate barrier_id")
    memberships: dict[str, list[dict[str, Any]]] = {node_id: [] for node_id in by_id}
    for barrier in barriers:
        for member in barrier.get("members", []):
            if member not in by_id:
                errors.append(f"barrier references unknown node: {member}")
            else:
                memberships[member].append(barrier)
    for node_id, member_of in memberships.items():
        if len(member_of) != 1:
            errors.append(f"node must belong to exactly one barrier: {node_id}")
        elif member_of[0].get("order") != by_id[node_id].get("barrier_order"):
            errors.append(f"node/barrier order mismatch: {node_id}")

    dependency_ids: list[str] = []
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in by_id}
    indegree = {node_id: 0 for node_id in by_id}
    for dependency in program.get("dependencies", []):
        dependency_ids.append(dependency.get("dependency_id"))
        source, target = dependency.get("source"), dependency.get("target")
        if target not in by_id:
            errors.append(f"dependency target is not a node: {target}")
            continue
        if dependency.get("kind") == "control":
            if source not in by_id:
                errors.append(f"control dependency source is not a node: {source}")
                continue
            if target not in adjacency[source]:
                adjacency[source].add(target)
                indegree[target] += 1
            if by_id[source]["barrier_order"] > by_id[target]["barrier_order"]:
                errors.append(f"dependency crosses barriers backwards: {dependency.get('dependency_id')}")
    if len(dependency_ids) != len(set(dependency_ids)):
        errors.append("duplicate dependency_id")

    queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    visited = 0
    while queue:
        source = queue.popleft()
        visited += 1
        for target in sorted(adjacency[source]):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(by_id):
        errors.append("dependency graph contains a cycle")

    for node in nodes:
        if node.get("kind") in {"implementation", "remediation"} and node.get("requires_verification") is not True:
            errors.append(f"implementation generation lacks verification: {node.get('node_id')}")
    policy = program.get("verification_policy", {})
    if policy != {"mode": "exactly_one_per_implementation_generation", "qa_actor_type": "qa_agent"}:
        errors.append("verification policy is not exact 1:1")
    return errors


def sensitive_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = key.lower()
            if any(re.search(rf"(^|_){re.escape(part)}($|_)", lowered) for part in SENSITIVE_KEY_PARTS):
                found.append(f"{path}.{key}")
            found.extend(sensitive_paths(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(sensitive_paths(child, f"{path}[{index}]"))
    return found


def check_examples(
    command_schema: dict[str, Any], event_schema: dict[str, Any], graph_schema: dict[str, Any]
) -> None:
    examples = [
        ("examples/valid-command.json", command_schema),
        ("examples/valid-event.json", event_schema),
        ("examples/valid-program.json", graph_schema),
    ]
    for relative, schema in examples:
        errors = validate_schema(load(relative), schema)
        ensure(not errors, f"{relative}: {errors}")

    valid_program = load("examples/valid-program.json")
    ensure(not graph_errors(valid_program), f"valid program rejected: {graph_errors(valid_program)}")
    invalid_cycle = load("examples/invalid-cycle.json")
    actual = graph_errors(invalid_cycle["program"])
    ensure(set(invalid_cycle["expected_errors"]) <= set(actual), f"cycle fixture mismatch: {actual}")

    valid_event = load("examples/valid-event.json")
    ensure(not sensitive_paths(valid_event["payload"]), "valid event contains sensitive payload fields")
    invalid_privacy = load("examples/invalid-sensitive-event.json")
    privacy_errors = validate_schema(invalid_privacy["event"], event_schema)
    ensure(invalid_privacy["expected_error"] in privacy_errors, f"privacy fixture mismatch: {privacy_errors}")
    ensure(sensitive_paths(invalid_privacy["event"]["payload"]), "privacy fixture contains no sensitive key")


def check_contract_policy(
    command_schema: dict[str, Any], event_schema: dict[str, Any], graph_schema: dict[str, Any]
) -> None:
    ensure(command_schema["properties"]["schema_version"].get("const") == "controller.command/v0", "command version")
    ensure(event_schema["properties"]["schema_version"].get("const") == "controller.event/v0", "event version")
    ensure(graph_schema["properties"]["schema_version"].get("const") == "controller.program/v0", "program version")
    ensure("causation_id" in command_schema["required"], "command causation must be explicit")
    ensure("causation_id" in event_schema["required"], "event causation must be explicit")
    privacy = set(enum_at(event_schema, "properties", "privacy", "enum"))
    ensure(privacy == {"public", "internal", "sensitive_reference"}, "privacy classification drift")
    property_names = event_schema["properties"]["payload"]["propertyNames"]
    ensure(property_names.get("pattern") == "^[a-z][a-z0-9_]*$", "payload keys must be lower_snake_case")
    denied_pattern = property_names["not"]["pattern"]
    for part in SENSITIVE_KEY_PARTS:
        ensure(part in denied_pattern, f"privacy schema omits {part!r}")

    readme = (SPEC / "README.md").read_text(encoding="utf-8")
    ensure("additive" in readme.lower() and "breaking" in readme.lower(), "compatibility policy incomplete")
    ensure("reference" in readme.lower() and "redact" in readme.lower(), "privacy policy incomplete")
    test_plan = (ROOT / "docs" / "controller-stage-a-test-plan.md").read_text(encoding="utf-8")
    ensure("exactly one" in test_plan.lower() and "authority denial" in test_plan.lower(), "Stage A QA/authority plan incomplete")


def main() -> int:
    try:
        command_schema = load("command-envelope.schema.json")
        event_schema = load("event-envelope.schema.json")
        graph_schema = load("program-graph.schema.json")
        authority = load("authority-matrix.json")
        transitions = load("transition-tables.json")
        for name, schema in (
            ("command", command_schema),
            ("event", event_schema),
            ("program", graph_schema),
        ):
            check_schema_basics(name, schema)
        check_contract_policy(command_schema, event_schema, graph_schema)
        check_authority(command_schema, authority)
        check_transitions(command_schema, event_schema, transitions)
        check_examples(command_schema, event_schema, graph_schema)
    except (AssertionError, KeyError, TypeError) as error:
        print(f"Controller specification validation failed: {error}", file=sys.stderr)
        return 1

    print("Controller v0 specification validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
