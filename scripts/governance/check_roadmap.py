#!/usr/bin/env python3
"""Validate the canonical roadmap graph and its Markdown projection."""

from __future__ import annotations

import hashlib
import re
import subprocess
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
BASELINE_RE = re.compile(
    r"^\*\*Exact checkpoint:\*\* `(?P<branch>[^@`]+)@(?P<sha>[0-9a-f]{40})` "
    r"on (?P<captured_at>[0-9]{4}-[0-9]{2}-[0-9]{2})$",
    re.MULTILINE,
)
AUTHORITY_RE = re.compile(
    r"^\*\*Portfolio authority:\*\* \[GitHub issue #(?P<label>[1-9][0-9]*)\]"
    r"\(https://github\.com/somebloke1/noetic-dev/issues/(?P<url>[1-9][0-9]*)\)$",
    re.MULTILINE,
)
MACHINE_INDEX_LINE = (
    "**Machine index:** "
    "[`governance/roadmap.json`](governance/roadmap.json)"
)
POLICY_SNAPSHOT_RE = re.compile(
    r"^\*\*Policy snapshot:\*\* freeze=(?P<existing_work_freeze>[a-z_]+); "
    r"publication=(?P<publication>[a-z_]+); "
    r"delivery_gate=(?P<authoritative_delivery_gate>[a-z_]+)$",
    re.MULTILINE,
)
TRACK_RE = re.compile(
    r"^- \*\*(?P<id>T[0-9]+) - (?P<title>.+):\*\* (?P<constraint>.+)$",
    re.MULTILINE,
)
CONFLICT_RE = re.compile(
    r"^- \*\*(?P<id>C[0-9]+) - (?P<title>.+):\*\* resolve in "
    r"(?P<resolution>D[0-9]+[a-z]?); blocks (?P<blocks>.+)\.$",
    re.MULTILINE,
)
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
ISSUE_RE = re.compile(
    r"https://github\.com/somebloke1/noetic-dev/issues/([1-9][0-9]*)\Z"
)
PULL_REQUEST_RE = re.compile(
    r"https://github\.com/somebloke1/noetic-dev/pull/[1-9][0-9]*\Z"
)
WORKFLOW_RUN_RE = re.compile(
    r"https://github\.com/somebloke1/noetic-dev/actions/runs/[1-9][0-9]*\Z"
)
EXPECTED_STAGE_IDS = (
    "D0", "D1a", "D1b", "D2", "D3a", "D3b", "D4a", "D4b",
    "D4c", "D4d", "D5", "D6", "D7", "D8", "D9",
)
EXPECTED_TRACK_IDS = ("T1", "T2", "T3", "T4")
EXPECTED_CONFLICT_IDS = ("C5", "C6", "C7", "C8")
EXPECTED_EVIDENCE_BY_STAGE = {
    "D0": (
        ("commit", "29196a67349537d6f8a8a711df11b86da0430857"),
        ("commit", "15b9ae66ff316abf28a5041c465e95baef5e82f9"),
        ("issue", "https://github.com/somebloke1/noetic-dev/issues/32"),
    ),
    "D1a": (
        ("commit", "f5efd668304a7dbade20bd20704ed4930cbecef9"),
        ("commit", "0ab63d8fac1ceadfaca72717e62ff1d564c81e0e"),
        ("commit", "38c2812eca31983e39f8705f7bc7aed05df31329"),
        ("commit", "b846efa0392eda96a58e1b6d099c9e39385cac58"),
    ),
    "D1b": (
        ("commit", "58c4c791d7f39c0a6eca0dc7b1ddfd8bb67d02b2"),
        ("pull_request", "https://github.com/somebloke1/noetic-dev/pull/64"),
        (
            "workflow_run",
            "https://github.com/somebloke1/noetic-dev/actions/runs/29629152718",
        ),
        ("commit", "15b9ae66ff316abf28a5041c465e95baef5e82f9"),
    ),
    "D2": (
        ("artifact", "governance/audits/20260718-d2-portfolio/inventory.json"),
        ("issue", "https://github.com/somebloke1/noetic-dev/issues/32"),
    ),
}
EXPECTED_REMOTE_EVIDENCE = frozenset(
    {
        ("issue", "https://github.com/somebloke1/noetic-dev/issues/32"),
        ("pull_request", "https://github.com/somebloke1/noetic-dev/pull/64"),
        (
            "workflow_run",
            "https://github.com/somebloke1/noetic-dev/actions/runs/29629152718",
        ),
    }
)
EXPECTED_POLICY_EXIT_GATES = {
    "D2": (
        "Accepted authority and branch-flow decisions, reviewed freeze disposition, "
        "consistent machine and prose policy, synchronized issue 32 and roadmap, "
        "green validation, and paired independent QA."
    ),
    "D9": (
        "License, audit, distinct protected trust root, protected main, post-merge "
        "evidence, independent approval, rollback, and immutable tag bind one full "
        "main SHA."
    ),
}
FREEZE_PATH = Path("governance/audits/existing-work-freeze.json")
BOOTSTRAP_STATUS_PATH = Path("governance/bootstrap-status.json")


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


def _normalize_markdown(value: str) -> str:
    return " ".join(value.split())


def _stage_sections(markdown: str) -> tuple[list[dict[str, str]], dict[str, str]]:
    matches = list(STAGE_HEADING_RE.finditer(markdown))
    headings = [match.groupdict() for match in matches]
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections[match.group("id")] = markdown[match.end():end]
    return headings, sections


def _markdown_field(section: str, label: str) -> str | None:
    pattern = re.compile(
        rf"^- \*\*{re.escape(label)}:\*\* (?P<value>[^\n]*(?:\n  [^\n]*)*)",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(section))
    if len(matches) != 1:
        return None
    return _normalize_markdown(matches[0].group("value"))


def _expected_evidence_field(stage: dict[str, Any]) -> str:
    if not stage["evidence"]:
        return "none."
    rendered = [
        f"`{item['kind']}:{item['reference']}`"
        for item in stage["evidence"]
    ]
    return f"{', '.join(rendered)}."


def _validate_markdown_projection(
    state: dict[str, Any],
    markdown: str,
    document_bytes: bytes | None,
) -> list[str]:
    errors: list[str] = []
    payload = document_bytes if document_bytes is not None else markdown.encode("utf-8")
    document_sha256 = hashlib.sha256(payload).hexdigest()
    if document_sha256 != state["document_sha256"]:
        errors.append("ROADMAP.md SHA-256 does not match governance/roadmap.json")
    baseline_matches = list(BASELINE_RE.finditer(markdown))
    expected_baseline = state["baseline"]
    if len(baseline_matches) != 1:
        errors.append("ROADMAP.md must contain exactly one structured checkpoint line")
    else:
        actual = baseline_matches[0].groupdict()
        expected = {
            "branch": expected_baseline["branch"],
            "sha": expected_baseline["sha"],
            "captured_at": expected_baseline["captured_at"],
        }
        if actual != expected:
            errors.append("ROADMAP.md checkpoint line does not match roadmap baseline")

    authority_matches = list(AUTHORITY_RE.finditer(markdown))
    if len(authority_matches) != 1:
        errors.append("ROADMAP.md must contain exactly one structured authority line")
    else:
        authority = str(state["authority_issue"])
        actual = authority_matches[0].groupdict()
        if actual != {"label": authority, "url": authority}:
            errors.append("ROADMAP.md authority line does not match authority_issue")
    if markdown.count(MACHINE_INDEX_LINE) != 1:
        errors.append("ROADMAP.md must contain exactly one canonical machine-index line")
    policy_matches = list(POLICY_SNAPSHOT_RE.finditer(markdown))
    if len(policy_matches) != 1:
        errors.append("ROADMAP.md must contain exactly one structured policy snapshot")
    elif policy_matches[0].groupdict() != state["policy_snapshot"]:
        errors.append("ROADMAP.md policy snapshot does not match governance/roadmap.json")

    headings, sections = _stage_sections(markdown)
    expected_headings = [
        {"id": stage["id"], "title": stage["title"], "status": stage["status"]}
        for stage in state["stages"]
    ]
    if headings != expected_headings:
        errors.append("ROADMAP.md stage headings do not match governance/roadmap.json")
    else:
        for stage in state["stages"]:
            stage_id = stage["id"]
            section = sections[stage_id]
            expected_dependencies = (
                f"{', '.join(stage['depends_on'])}." if stage["depends_on"] else "none."
            )
            actual_dependencies = _markdown_field(section, "Dependencies")
            if actual_dependencies != expected_dependencies:
                errors.append(f"{stage_id}: Markdown dependencies do not match JSON")
            actual_evidence = _markdown_field(section, "Evidence refs")
            if actual_evidence != _expected_evidence_field(stage):
                errors.append(f"{stage_id}: Markdown evidence does not match JSON")
            actual_gate = _markdown_field(section, "Exit gate")
            if actual_gate != stage["exit_gate"]:
                errors.append(f"{stage_id}: Markdown exit gate does not match JSON")

    tracks = [match.groupdict() for match in TRACK_RE.finditer(markdown)]
    expected_tracks = [
        {
            "id": track["id"],
            "title": track["title"],
            "constraint": track["constraint"],
        }
        for track in state["parallel_tracks"]
    ]
    if tracks != expected_tracks:
        errors.append("ROADMAP.md parallel tracks do not match governance/roadmap.json")

    conflicts: list[dict[str, Any]] = []
    for match in CONFLICT_RE.finditer(markdown):
        item = match.groupdict()
        blocks = [] if item["blocks"] == "none" else item["blocks"].split(", ")
        conflicts.append(
            {
                "id": item["id"],
                "title": item["title"],
                "resolution_stage": item["resolution"],
                "blocks": blocks,
            }
        )
    if conflicts != state["unresolved_conflicts"]:
        errors.append("ROADMAP.md conflicts do not match governance/roadmap.json")
    return errors


def _git_succeeds(root: Path, *arguments: str) -> bool:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _validate_evidence(
    state: dict[str, Any],
    root: Path | None,
) -> list[str]:
    errors: list[str] = []
    baseline = state["baseline"]["sha"]
    remote_evidence: set[tuple[str, str]] = set()
    if root is not None:
        remote_branch = f"refs/remotes/origin/{state['baseline']['branch']}"
        if not _git_succeeds(root, "cat-file", "-e", f"{baseline}^{{commit}}"):
            errors.append(f"baseline commit does not resolve: {baseline}")
        else:
            if not _git_succeeds(root, "merge-base", "--is-ancestor", baseline, "HEAD"):
                errors.append("roadmap baseline is not an ancestor of HEAD")
            if not _git_succeeds(root, "cat-file", "-e", f"{remote_branch}^{{commit}}"):
                errors.append(f"declared roadmap branch does not resolve: {remote_branch}")
            elif not _git_succeeds(
                root, "merge-base", "--is-ancestor", baseline, remote_branch
            ):
                errors.append(
                    f"roadmap baseline is not an ancestor of declared branch {remote_branch}"
                )

    for stage in state["stages"]:
        expected_evidence = EXPECTED_EVIDENCE_BY_STAGE.get(stage["id"], ())
        actual_evidence = tuple(
            (item["kind"], item["reference"])
            for item in stage["evidence"]
        )
        if actual_evidence != expected_evidence:
            errors.append(
                f"{stage['id']}: schema version 2 evidence catalog changed"
            )
        seen: set[tuple[str, str]] = set()
        commit_count = 0
        for item in stage["evidence"]:
            identity = (item["kind"], item["reference"])
            if identity in seen:
                errors.append(f"{stage['id']}: duplicate evidence {identity!r}")
                continue
            seen.add(identity)
            kind = item["kind"]
            reference = item["reference"]
            if kind == "commit":
                if not COMMIT_RE.fullmatch(reference):
                    errors.append(f"{stage['id']}: invalid commit evidence {reference!r}")
                    continue
                commit_count += 1
                if root is not None:
                    if not _git_succeeds(root, "cat-file", "-e", f"{reference}^{{commit}}"):
                        errors.append(
                            f"{stage['id']}: evidence commit does not resolve: {reference}"
                        )
                    elif not _git_succeeds(
                        root, "merge-base", "--is-ancestor", reference, baseline
                    ):
                        errors.append(
                            f"{stage['id']}: evidence commit is not a baseline ancestor: "
                            f"{reference}"
                        )
            elif kind == "issue":
                remote_evidence.add(identity)
                match = ISSUE_RE.fullmatch(reference)
                if match is None:
                    errors.append(f"{stage['id']}: invalid issue evidence {reference!r}")
                elif int(match.group(1)) != state["authority_issue"]:
                    errors.append(
                        f"{stage['id']}: issue evidence must be authority issue "
                        f"#{state['authority_issue']}"
                    )
            elif kind == "pull_request":
                remote_evidence.add(identity)
                if PULL_REQUEST_RE.fullmatch(reference) is None:
                    errors.append(
                        f"{stage['id']}: invalid pull-request evidence {reference!r}"
                    )
            elif kind == "workflow_run":
                remote_evidence.add(identity)
                if WORKFLOW_RUN_RE.fullmatch(reference) is None:
                    errors.append(
                        f"{stage['id']}: invalid workflow-run evidence {reference!r}"
                    )
            elif kind == "artifact":
                artifact = Path(reference)
                if artifact.is_absolute() or ".." in artifact.parts:
                    errors.append(f"{stage['id']}: unsafe artifact evidence {reference!r}")
                elif root is not None:
                    resolved_root = root.resolve()
                    resolved_artifact = (resolved_root / artifact).resolve()
                    if resolved_root not in resolved_artifact.parents:
                        errors.append(
                            f"{stage['id']}: artifact evidence resolves outside repository: "
                            f"{reference}"
                        )
                    elif not resolved_artifact.is_file():
                        errors.append(
                            f"{stage['id']}: artifact evidence does not exist: {reference}"
                        )
        if stage["status"] == "checkpointed" and commit_count == 0:
            errors.append(
                f"{stage['id']}: checkpointed stage requires baseline-ancestor commit evidence"
            )
    if remote_evidence != EXPECTED_REMOTE_EVIDENCE:
        errors.append("schema version 2 remote evidence catalog changed")
    return errors


def _validate_repository_policy(
    state: dict[str, Any],
    root: Path,
) -> list[str]:
    errors: list[str] = []

    def load_policy(relative: Path) -> dict[str, Any]:
        path = root.resolve() / relative
        if path.is_symlink():
            raise ValueError(f"{relative}: policy file must not be a symlink")
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise ValueError(f"{relative}: policy file does not resolve: {exc}") from exc
        resolved_root = root.resolve()
        if resolved_root not in resolved.parents:
            raise ValueError(f"{relative}: policy file resolves outside repository")
        if not resolved.is_file():
            raise ValueError(f"{relative}: policy file must be a regular file")
        value = load_json_strict(resolved)
        if not isinstance(value, dict):
            raise ValueError(f"{relative}: policy file must contain an object")
        return value

    try:
        freeze = load_policy(FREEZE_PATH)
        bootstrap = load_policy(BOOTSTRAP_STATUS_PATH)
    except (OSError, ValueError) as exc:
        return [f"roadmap policy files failed to load: {exc}"]

    actual_snapshot = {
        "existing_work_freeze": freeze.get("status"),
        "publication": bootstrap.get("publication", {}).get("status"),
        "authoritative_delivery_gate": bootstrap.get(
            "authoritative_delivery_gate", {}
        ).get("status"),
    }
    if actual_snapshot != state["policy_snapshot"]:
        errors.append("roadmap policy snapshot does not match repository policy files")

    stages = {stage["id"]: stage for stage in state["stages"]}
    conflicts = {
        conflict["id"]: conflict
        for conflict in state["unresolved_conflicts"]
    }
    d2 = stages["D2"]
    d9 = stages["D9"]
    c8 = conflicts["C8"]

    if d2["exit_gate"] != EXPECTED_POLICY_EXIT_GATES["D2"]:
        errors.append("D2 requires the exact schema-v2 D2 exit gate")

    if freeze.get("status") == "active" or freeze.get("blocks_publication") is True:
        if d2["status"] != "next":
            errors.append("active freeze requires D2 to remain the next stage")
        errors.append("active freeze is incompatible with the schema-v2 D2 disposition")

    if bootstrap.get("publication", {}).get("status") == "blocked":
        if d9["status"] in {"checkpointed", "next"}:
            errors.append("blocked publication cannot be checkpointed or next")
        if c8["resolution_stage"] != "D9" or "D9" not in c8["blocks"]:
            errors.append("blocked publication must remain an unresolved D9 conflict")
        if "D2" not in d9["depends_on"]:
            errors.append("D9 must retain D2 governance convergence as a dependency")

    if (
        actual_snapshot["authoritative_delivery_gate"] == "external_dependency_missing"
        and d9["exit_gate"] != EXPECTED_POLICY_EXIT_GATES["D9"]
    ):
        errors.append("missing trust root requires the exact schema-v2 D9 exit gate")
    return errors


def validate_roadmap(
    state: Any,
    schema: dict[str, Any],
    markdown: str,
    root: Path | None = None,
    document_bytes: bytes | None = None,
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
    if tuple(stage_ids) != EXPECTED_STAGE_IDS:
        errors.append("schema version 2 stage catalog or order changed")

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
        if stage["status"] in {"checkpointed", "next"}:
            for dependency in dependencies:
                if statuses.get(dependency) != "checkpointed":
                    errors.append(
                        f"{stage_id}: {stage['status']} stage depends on "
                        f"non-checkpointed {dependency}"
                    )

    next_stages = [stage["id"] for stage in stages if stage["status"] == "next"]
    if len(next_stages) != 1:
        errors.append(f"expected exactly one next stage, found {len(next_stages)}")

    for cycle in _find_cycles(stages):
        errors.append(f"dependency cycle: {cycle}")

    conflict_ids = [conflict["id"] for conflict in state["unresolved_conflicts"]]
    if len(conflict_ids) != len(set(conflict_ids)):
        errors.append("conflict ids must be unique")
    if tuple(conflict_ids) != EXPECTED_CONFLICT_IDS:
        errors.append("schema version 2 conflict catalog or order changed")
    named_blocks: set[str] = set()
    for conflict in state["unresolved_conflicts"]:
        if conflict["resolution_stage"] not in stage_set:
            errors.append(
                f"{conflict['id']}: unknown resolution stage {conflict['resolution_stage']}"
            )
        if len(conflict["blocks"]) != len(set(conflict["blocks"])):
            errors.append(f"{conflict['id']}: blocked stages must be unique")
        resolution = conflict["resolution_stage"]
        if resolution in statuses and statuses[resolution] == "checkpointed":
            errors.append(
                f"{conflict['id']}: unresolved conflict resolves in checkpointed "
                f"{resolution}"
            )
        for blocked in conflict["blocks"]:
            if blocked not in stage_set:
                errors.append(f"{conflict['id']}: unknown blocked stage {blocked}")
                continue
            named_blocks.add(blocked)
            if statuses[blocked] == "checkpointed":
                errors.append(
                    f"{conflict['id']}: unresolved conflict blocks checkpointed {blocked}"
                )
            if resolution in positions and positions[resolution] > positions[blocked]:
                errors.append(
                    f"{conflict['id']}: resolution stage {resolution} follows blocked {blocked}"
                )

    for stage in stages:
        if stage["status"] == "blocked" and stage["id"] not in named_blocks:
            errors.append(f"{stage['id']}: blocked stage has no named conflict")

    if len(next_stages) == 1:
        next_stage = next_stages[0]
        next_position = positions[next_stage]
        for earlier in stages[:next_position]:
            if earlier["status"] != "checkpointed":
                errors.append(
                    f"{next_stage}: earlier stage {earlier['id']} is not checkpointed"
                )
        if next_stage in named_blocks:
            errors.append(f"{next_stage}: next stage is blocked by an unresolved conflict")

    track_ids = [track["id"] for track in state["parallel_tracks"]]
    if len(track_ids) != len(set(track_ids)):
        errors.append("parallel track ids must be unique")
    if tuple(track_ids) != EXPECTED_TRACK_IDS:
        errors.append("schema version 2 parallel-track catalog or order changed")

    errors.extend(_validate_evidence(state, root))
    errors.extend(_validate_markdown_projection(state, markdown, document_bytes))
    if root is not None:
        errors.extend(_validate_repository_policy(state, root))
    return errors


def validate_roadmap_files(root: Path = ROOT) -> list[str]:
    """Load and validate the repository roadmap files."""
    root = root.resolve()
    try:
        state = load_json_strict(root / STATE_PATH)
        schema = load_json_strict(root / SCHEMA_PATH)
    except (OSError, ValueError) as exc:
        return [f"roadmap files failed to load: {exc}"]
    schema_errors = validate_schema(state, schema)
    if schema_errors:
        return schema_errors
    document_path = (root / state["document_path"]).resolve()
    if root not in document_path.parents:
        return ["roadmap document path escapes repository"]
    try:
        document_bytes = document_path.read_bytes()
        markdown = document_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"roadmap document failed to load: {exc}"]
    return validate_roadmap(state, schema, markdown, root, document_bytes)


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
