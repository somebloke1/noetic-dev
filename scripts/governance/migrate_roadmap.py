#!/usr/bin/env python3
"""Deterministically migrate the canonical roadmap schema from v1 to v2."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hash_tree import canonical_json_sha256  # noqa: E402
from json_schema import load_json_strict, validate_schema  # noqa: E402

ROOT = SCRIPT_DIR.parents[1]
V1_SCHEMA_PATH = ROOT / "governance/schemas/roadmap.schema.json"
V2_SCHEMA_PATH = ROOT / "governance/schemas/roadmap-v2.schema.json"
V1_MARKERS = ("./schemas/roadmap.schema.json", "1")
V2_MARKERS = ("./schemas/roadmap-v2.schema.json", "2")
CANONICAL_V1_SHA256 = "fe12c85712d2505229e4a7139bc56b0864614ceb24c0b1cf24a8b6bda2f4816b"
STAGE_IDS = [
    "D0", "D1a", "D1b", "D2", "D3a", "D3b", "D4a", "D4b",
    "D4c", "D4d", "D5", "D6", "D7", "D8", "D9",
]
TRACK_IDS = ["T1", "T2", "T3", "T4"]
V1_CONFLICT_IDS = ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"]
V2_CONFLICT_IDS = (["C2", "C5", "C6", "C7", "C8"], ["C5", "C6", "C7", "C8"])


class RoadmapMigrationError(ValueError):
    """Raised when a roadmap cannot be migrated without guessing."""


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _ids(value: Any, field: str) -> list[str]:
    if type(value) is not list or any(type(item) is not dict for item in value):
        raise RoadmapMigrationError(f"{field} is not a strict object catalog")
    ids = [item.get("id") for item in value]
    if any(type(item) is not str for item in ids):
        raise RoadmapMigrationError(f"{field} contains an invalid identity")
    return ids


def _validate_catalogs(value: dict[str, Any], version: str) -> None:
    if _ids(value.get("stages"), "stages") != STAGE_IDS:
        raise RoadmapMigrationError("stage catalog identity or order is invalid")
    if _ids(value.get("parallel_tracks"), "parallel_tracks") != TRACK_IDS:
        raise RoadmapMigrationError("parallel-track catalog identity or order is invalid")
    conflict_ids = _ids(value.get("unresolved_conflicts"), "unresolved_conflicts")
    allowed = [V1_CONFLICT_IDS] if version == "1" else list(V2_CONFLICT_IDS)
    if conflict_ids not in allowed:
        raise RoadmapMigrationError("unresolved-conflict catalog identity or order is invalid")


def _validate(value: Any, schema_path: Path, version: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise RoadmapMigrationError("roadmap root is not a strict object")
    schema = load_json_strict(schema_path)
    errors = validate_schema(value, schema)
    if errors:
        raise RoadmapMigrationError(f"roadmap v{version} schema validation failed: {errors[0]}")
    _validate_catalogs(value, version)
    return value


def migrate_v1_to_v2(value: Any) -> dict[str, Any]:
    source = _validate(value, V1_SCHEMA_PATH, "1")
    if canonical_json_sha256(source) != CANONICAL_V1_SHA256:
        raise RoadmapMigrationError("roadmap v1 input is not the persisted canonical predecessor")
    migrated = copy.deepcopy(source)
    migrated["$schema"] = V2_MARKERS[0]
    migrated["schema_version"] = V2_MARKERS[1]
    migrated["unresolved_conflicts"] = [
        item for item in migrated["unresolved_conflicts"] if item["id"] not in {"C1", "C3", "C4"}
    ]
    return _validate(migrated, V2_SCHEMA_PATH, "2")


def migrate_roadmap(value: Any) -> dict[str, Any]:
    if type(value) is not dict:
        raise RoadmapMigrationError("roadmap root is not a strict object")
    markers = (value.get("$schema"), value.get("schema_version"))
    if markers == V1_MARKERS:
        return migrate_v1_to_v2(value)
    if markers == V2_MARKERS:
        return copy.deepcopy(_validate(value, V2_SCHEMA_PATH, "2"))
    raise RoadmapMigrationError("roadmap schema markers are missing, mixed, or unsupported")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("source")
    parser.add_argument("expected", nargs="?")
    args = parser.parse_args(argv)
    if args.check != (args.expected is not None):
        parser.error("--check requires SOURCE and EXPECTED; normal mode accepts SOURCE only")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        source = load_json_strict(args.source)
        output = canonical_json_bytes(migrate_roadmap(source))
        if args.check:
            expected = Path(args.expected).read_bytes()
            if expected != output:
                raise RoadmapMigrationError("expected v2 fixture is not the exact canonical migration")
        else:
            sys.stdout.buffer.write(output)
    except (OSError, ValueError, TypeError) as exc:
        print(f"roadmap migration blocked: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
