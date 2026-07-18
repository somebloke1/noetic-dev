#!/usr/bin/env python3
"""Validate the canonical roadmap graph and its Markdown projection."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.governance.json_schema import load_json_strict, validate_schema  # noqa: E402


STATE_PATH = Path("governance/roadmap.json")
SCHEMA_PATH = Path("governance/schemas/roadmap.schema.json")
STAGE_HEADING_RE = re.compile(
    r"^### (?P<id>D[0-9]+[a-z]?) - (?P<title>.+) "
    r"\[(?P<status>checkpointed|next|planned|blocked)\]$",
    re.MULTILINE,
)


def _find_cycles(stages: list[dict[str, Any]]) -> list[str]:
    dependencies = {stage["id"]: stage["depends_on"] for stage in stages}
    visiting: list[str] = []
    visited: set[str] = set()
    cycles: set[tuple[str, ...]] = set()

    def visit(stage_id: str) -> None:
        if stage_id in visiting:
            start = visiting.index(stage_id)
            cycles.add(tuple(visiting[start:] + [stage_id]))
            return
        if stage_id in visited:
            return
        visiting.append(stage_id)
        for dependency in dependencies.get(stage_id, []):
            if dependency in dependencies:
                visit(dependency)
        visiting.pop()
        visited.add(stage_id)

    for stage_id in dependencies:
        visit(stage_id)
    return [" -> ".join(cycle) for cycle in sorted(cycles)]


def validate_roadmap(
    state: Any,
    schema: dict[str, Any],
    markdown: str,
) -> list[str]:
    """Return deterministic roadmap contract violations."""
    errors = validate_schema(state, schema)
    if errors:
        return errors

    stages = state["stages"]
    stage_ids = [stage["id"] for stage in stages]
    stage_set = set(stage_ids)
    if len(stage_ids) != len(stage_set):
        errors.append("stage ids must be unique")

    positions = {stage_id: index for index, stage_id in enumerate(stage_ids)}
    statuses = {stage["id"]: stage["status"] for stage in stages}
    for stage in stages:
        stage_id = stage["id"]
        dependencies = stage["depends_on"]
        if len(dependencies) != len(set(dependencies)):
            errors.append(f"{stage_id}: dependencies must be unique")
        for dependency in dependencies:
            if dependency not in stage_set:
                errors.append(f"{stage_id}: unknown dependency {dependency}")
            elif positions[dependency] >= positions[stage_id]:
                errors.append(f"{stage_id}: dependency {dependency} must appear earlier")
        if stage["status"] == "checkpointed" and not stage["evidence"]:
            errors.append(f"{stage_id}: checkpointed stage requires evidence")
        if stage["status"] == "next":
            for dependency in dependencies:
                if statuses.get(dependency) != "checkpointed":
                    errors.append(
                        f"{stage_id}: next stage depends on non-checkpointed {dependency}"
                    )

    next_stages = [stage["id"] for stage in stages if stage["status"] == "next"]
    if len(next_stages) != 1:
        errors.append(f"expected exactly one next stage, found {len(next_stages)}")

    for cycle in _find_cycles(stages):
        errors.append(f"dependency cycle: {cycle}")

    conflict_ids = [conflict["id"] for conflict in state["unresolved_conflicts"]]
    if len(conflict_ids) != len(set(conflict_ids)):
        errors.append("conflict ids must be unique")
    for conflict in state["unresolved_conflicts"]:
        if conflict["resolution_stage"] not in stage_set:
            errors.append(
                f"{conflict['id']}: unknown resolution stage {conflict['resolution_stage']}"
            )
        for blocked in conflict["blocks"]:
            if blocked not in stage_set:
                errors.append(f"{conflict['id']}: unknown blocked stage {blocked}")

    track_ids = [track["id"] for track in state["parallel_tracks"]]
    if len(track_ids) != len(set(track_ids)):
        errors.append("parallel track ids must be unique")

    headings = [match.groupdict() for match in STAGE_HEADING_RE.finditer(markdown)]
    expected_headings = [
        {"id": stage["id"], "title": stage["title"], "status": stage["status"]}
        for stage in stages
    ]
    if headings != expected_headings:
        errors.append("ROADMAP.md stage headings do not match governance/roadmap.json")

    baseline_sha = state["baseline"]["sha"]
    if baseline_sha not in markdown:
        errors.append("ROADMAP.md does not contain the exact baseline SHA")
    authority_url = (
        "https://github.com/somebloke1/noetic-dev/issues/"
        f"{state['authority_issue']}"
    )
    if authority_url not in markdown:
        errors.append("ROADMAP.md does not link its authority issue")

    return errors


def validate_roadmap_files(root: Path = ROOT) -> list[str]:
    """Load and validate the repository roadmap files."""
    try:
        state = load_json_strict(root / STATE_PATH)
        schema = load_json_strict(root / SCHEMA_PATH)
        document_path = state.get("document_path") if isinstance(state, dict) else None
        if not isinstance(document_path, str):
            return ["governance/roadmap.json: document_path must be a string"]
        markdown = (root / document_path).read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        return [f"roadmap files failed to load: {exc}"]
    return validate_roadmap(state, schema, markdown)


def main() -> int:
    errors = validate_roadmap_files()
    if errors:
        print("Roadmap validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Roadmap validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
