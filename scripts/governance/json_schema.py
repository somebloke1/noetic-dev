#!/usr/bin/env python3
"""Small dependency-free JSON Schema checks used by governance validators.

This is intentionally a conservative subset of draft-07: enough for the
repository-owned schemas without adding runtime dependencies. It fails closed on
unsupported keywords only where those keywords would be security relevant in the
current schemas; otherwise the hand-written governance checks provide the
semantic enforcement.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Iterable, List, Tuple


class DuplicateKeyError(ValueError):
    """Raised when strict JSON loading sees duplicate object keys."""


def _no_duplicates_object_pairs_hook(pairs: Iterable[Tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate object key: {key}")
        result[key] = value
    return result


def parse_json_strict(raw: str | bytes) -> Any:
    """Parse JSON while rejecting duplicate keys and non-finite constants."""
    return json.loads(
        raw,
        object_pairs_hook=_no_duplicates_object_pairs_hook,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"non-deterministic JSON number: {value}")
        ),
    )


def load_json_strict(path: str | Path) -> Any:
    """Load JSON while rejecting duplicate object keys."""
    with open(path, "r", encoding="utf-8") as f:
        return parse_json_strict(f.read())


def _json_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return type(value).__name__


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def validate_schema(value: Any, schema: dict[str, Any], path: str = "$") -> List[str]:
    """Validate *value* against a small JSON Schema subset.

    Supported keywords: type, required, properties, additionalProperties,
    items, enum, const, pattern, minLength, maxLength, minItems, maxItems, anyOf,
    oneOf, allOf, if/then/else (shallow), and $ref for local #/definitions refs.
    """
    return _validate(value, schema, schema, path)


def _resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported non-local $ref: {ref}")
    node: Any = root
    for raw_part in ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        node = node[part]
    if not isinstance(node, dict):
        raise ValueError(f"$ref does not point to a schema object: {ref}")
    return node


def _validate(value: Any, schema: dict[str, Any], root: dict[str, Any], path: str) -> List[str]:
    errors: List[str] = []

    if "$ref" in schema:
        try:
            return _validate(value, _resolve_ref(root, schema["$ref"]), root, path)
        except Exception as exc:  # pragma: no cover - defensive; schemas are repo-owned
            return [f"{path}: invalid schema reference {schema['$ref']}: {exc}"]

    for sub_schema in schema.get("allOf", []):
        errors.extend(_validate(value, sub_schema, root, path))

    if "anyOf" in schema:
        branches = [_validate(value, sub_schema, root, path) for sub_schema in schema["anyOf"]]
        if not any(not branch_errors for branch_errors in branches):
            errors.append(f"{path}: does not match any allowed schema branch")
        return errors

    if "oneOf" in schema:
        branches = [_validate(value, sub_schema, root, path) for sub_schema in schema["oneOf"]]
        if sum(1 for branch_errors in branches if not branch_errors) != 1:
            errors.append(f"{path}: does not match exactly one schema branch")
        return errors

    if "if" in schema:
        if_errors = _validate(value, schema["if"], root, path)
        if not if_errors and "then" in schema:
            errors.extend(_validate(value, schema["then"], root, path))
        if if_errors and "else" in schema:
            errors.extend(_validate(value, schema["else"], root, path))

    expected_type = schema.get("type")
    if expected_type is not None:
        if isinstance(expected_type, list):
            if not any(_type_matches(value, item) for item in expected_type):
                errors.append(f"{path}: expected type {expected_type}, got {_json_type(value)}")
                return errors
        elif not _type_matches(value, expected_type):
            errors.append(f"{path}: expected type {expected_type}, got {_json_type(value)}")
            return errors

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}, got {value!r}")

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']!r}, got {value!r}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: string shorter than {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: string longer than {schema['maxLength']}")
        if "pattern" in schema and not re.match(schema["pattern"], value):
            errors.append(f"{path}: string does not match pattern {schema['pattern']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: array has fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: array has more than {schema['maxItems']} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(_validate(item, item_schema, root, f"{path}[{index}]"))

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required property {key}")
        properties = schema.get("properties", {})
        for key, sub_schema in properties.items():
            if key in value:
                errors.extend(_validate(value[key], sub_schema, root, f"{path}.{key}"))
        if schema.get("additionalProperties") is False:
            allowed = set(properties)
            for key in value:
                if key not in allowed:
                    errors.append(f"{path}: additional property not allowed: {key}")

    return errors
