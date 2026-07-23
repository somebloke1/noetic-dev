#!/usr/bin/env python3
"""Validate an evidence manifest against schema and governance invariants.

The validator is a repository validator, not a delivery test. It rejects false
machine-readable claims before the delivery gate considers merge/publication
readiness.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hash_tree import (  # noqa: E402
    manifest_digest_excluding_own,
    validate_sha_hex,
    validate_sha256_hex,
)
from json_schema import DuplicateKeyError, load_json_strict, validate_schema  # noqa: E402

SHA1_RE = re.compile(r"^[a-f0-9]{40}$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
STATUS_RE = re.compile(r"^status:([a-z0-9_-]+)$")


def _load_repo_json(relative: str) -> Dict[str, Any]:
    return load_json_strict(REPO_ROOT / relative)


def _load_schema() -> Dict[str, Any]:
    return _load_repo_json("governance/schemas/evidence-manifest.schema.json")


def _load_command_registry() -> Dict[str, Any]:
    return _load_repo_json("governance/command-registry.json")


def _load_issue_status() -> Dict[str, Any]:
    return _load_repo_json("governance/issue-status.json")


def _load_model_profiles() -> Dict[str, Any]:
    return _load_repo_json("governance/model-profiles.json")


def _load_state_machine() -> Dict[str, Any]:
    return _load_repo_json("governance/state-machine.json")


def _parse_time(value: Any, label: str, errors: List[str]) -> datetime | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label} missing timestamp")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{label} is not an ISO-8601 timestamp: {value!r}")
        return None
    if parsed.tzinfo is None:
        errors.append(f"{label} must include an explicit timezone offset: {value!r}")
        return None
    return parsed


def _validate_sha(value: str, length: int, label: str, errors: List[str]) -> None:
    try:
        validate_sha_hex(value, length, label)
    except ValueError as exc:
        errors.append(str(exc))


def _validate_sha256(value: str, label: str, errors: List[str]) -> None:
    try:
        validate_sha256_hex(value, label)
    except ValueError as exc:
        errors.append(str(exc))


def _status_values() -> set[str]:
    return set(_load_issue_status().get("statuses", {}).keys())


def _registry_commands() -> Dict[str, Any]:
    return _load_command_registry().get("commands", {})


def command_registry_id(command: Dict[str, Any]) -> str:
    """Return the registry id claimed by a command record."""
    return command.get("registry_id") or command.get("command_id", "")


def normalize_qa_records(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return QA records, with legacy object shape mapped to a single record.

    The new contract is ``qa.records``. Legacy compatibility exists only so the
    validator can return meaningful diagnostics for old manifests.
    """
    qa = manifest.get("qa", {})
    if isinstance(qa, dict) and isinstance(qa.get("records"), list):
        return qa["records"]
    if isinstance(qa, dict) and qa.get("qa_for_pass_id"):
        return [qa]
    return []


def all_pass_ids(manifest: Dict[str, Any]) -> List[str]:
    passes = manifest.get("passes", {})
    return list(passes.get("implementation_pass_ids", [])) + list(passes.get("remediation_pass_ids", []))


def pass_records_by_id(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    passes = manifest.get("passes", {})
    return {
        item.get("pass_id", ""): item
        for item in passes.get("pass_records", [])
        if isinstance(item, dict) and item.get("pass_id")
    }


def _check_policy(manifest: Dict[str, Any], errors: List[str]) -> None:
    policy = manifest.get("policy", {})
    repo = manifest.get("repo", {})

    _validate_sha(policy.get("sha", ""), 40, "policy.sha", errors)
    _validate_sha256(policy.get("generator_sha256", ""), "policy.generator_sha256", errors)
    if policy.get("sha") and policy.get("sha") == repo.get("candidate_sha"):
        errors.append("policy.sha must not equal repo.candidate_sha (candidate-controlled policy checkout)")

    if not isinstance(policy.get("trusted_runner"), bool):
        errors.append("policy.trusted_runner must be a boolean")
    elif policy.get("trusted_runner") is True:
        errors.append(
            "policy.trusted_runner=true is a manifest-only authority claim; "
            "delivery authority requires separately supplied external protected evidence"
        )

    attestation = policy.get("runner_attestation", {})
    recorded_digest = attestation.get("artifact", {}).get("manifest_sha256") if isinstance(attestation, dict) else None
    if recorded_digest:
        _validate_sha256(recorded_digest, "policy.runner_attestation.artifact.manifest_sha256", errors)
        computed_digest = manifest_digest_excluding_own(manifest)
        if recorded_digest != computed_digest:
            errors.append(
                "manifest digest mismatch (excluding own field): "
                f"computed={computed_digest}, recorded={recorded_digest}"
            )


def _check_repo_and_pr(
    manifest: Dict[str, Any], errors: List[str], target_branch: str
) -> None:
    repo = manifest.get("repo", {})
    pr = manifest.get("pull_request", {})
    for field in ["base_sha", "candidate_sha", "candidate_tree_oid"]:
        _validate_sha(repo.get(field, ""), 40, f"repo.{field}", errors)
    if repo.get("candidate_sha") != pr.get("head_sha"):
        errors.append("pull_request.head_sha must equal repo.candidate_sha")
    if pr.get("base") != repo.get("base_branch"):
        errors.append("pull_request.base must equal repo.base_branch")
    if repo.get("base_branch") != target_branch:
        errors.append(
            f"repo.base_branch must be {target_branch} for this governed delivery mode"
        )
    candidate_pinned_at = _parse_time(
        repo.get("candidate_pinned_at", ""),
        "repo.candidate_pinned_at",
        errors,
    )
    generated_at = _parse_time(
        manifest.get("generated_at", ""), "generated_at", errors
    )
    if candidate_pinned_at and generated_at and candidate_pinned_at > generated_at:
        errors.append("repo.candidate_pinned_at must not follow manifest generation")


def _check_issue(manifest: Dict[str, Any], errors: List[str]) -> None:
    issue = manifest.get("issue", {})
    pr = manifest.get("pull_request", {})
    labels = issue.get("labels", [])
    status_labels = [label for label in labels if isinstance(label, str) and label.startswith("status:")]
    canonical = issue.get("canonical_status", "")

    if not issue.get("numbers"):
        errors.append("issue.numbers must contain at least one linked issue")
    if not pr.get("linked_issues"):
        errors.append("pull_request.linked_issues must contain at least one issue")
    for number in issue.get("numbers", []):
        if number not in pr.get("linked_issues", []):
            errors.append(f"issue {number} missing from pull_request.linked_issues")

    if len(status_labels) != 1:
        errors.append(f"exactly one status:* label is required, got {status_labels}")
    elif canonical != status_labels[0]:
        errors.append(f"issue.canonical_status {canonical!r} must equal status label {status_labels[0]!r}")

    match = STATUS_RE.match(canonical or "")
    if not match:
        errors.append(f"issue.canonical_status must match status:<value>, got {canonical!r}")
        return
    value = match.group(1)
    statuses = _status_values()
    if value not in statuses:
        errors.append(f"unknown issue status: {canonical}")


def _check_passes(manifest: Dict[str, Any], errors: List[str]) -> None:
    passes = manifest.get("passes", {})
    repo = manifest.get("repo", {})
    ids = all_pass_ids(manifest)
    if not ids:
        errors.append("passes must contain at least one implementation or remediation pass")
    if len(ids) != len(set(ids)):
        errors.append("implementation/remediation pass IDs must be unique")
    if passes.get("candidate_sha") != repo.get("candidate_sha"):
        errors.append("passes.candidate_sha must equal final repo.candidate_sha")
    if passes.get("ordering") != ids:
        errors.append("passes.ordering must exactly match implementation_pass_ids + remediation_pass_ids")

    records = pass_records_by_id(manifest)
    previous_candidate_sha = repo.get("base_sha")
    role_run_ids: set[str] = set()
    for index, pass_id in enumerate(ids):
        record = records.get(pass_id)
        if not record:
            errors.append(f"missing pass_records entry for {pass_id}")
            continue
        _validate_sha(record.get("candidate_sha", ""), 40, f"pass {pass_id}.candidate_sha", errors)
        _validate_sha(record.get("base_sha", ""), 40, f"pass {pass_id}.base_sha", errors)
        _validate_sha(record.get("candidate_tree_oid", ""), 40, f"pass {pass_id}.candidate_tree_oid", errors)
        if index == 0 and record.get("base_sha") != repo.get("base_sha"):
            errors.append(f"pass {pass_id} base_sha must equal repo.base_sha for the first generation")
        elif index > 0 and record.get("base_sha") != previous_candidate_sha:
            errors.append(f"pass {pass_id} base_sha must equal previous generation candidate_sha")
        previous_candidate_sha = record.get("candidate_sha")
        if not record.get("agent_id"):
            errors.append(f"pass {pass_id} missing agent_id for role-independence checks")
        role_run_id = record.get("role_run_id")
        if not role_run_id:
            errors.append(f"pass {pass_id} missing role_run_id")
        elif role_run_id in role_run_ids:
            errors.append(f"implementation/remediation role_run_id must be unique: {role_run_id}")
        else:
            role_run_ids.add(role_run_id)
        if record.get("finished_at"):
            _parse_time(record["finished_at"], f"pass {pass_id}.finished_at", errors)
        if record.get("started_at"):
            _parse_time(record["started_at"], f"pass {pass_id}.started_at", errors)

    if ids:
        final_record = records.get(ids[-1], {})
        if final_record.get("candidate_sha") != repo.get("candidate_sha"):
            errors.append(f"final pass {ids[-1]} candidate_sha must equal repo.candidate_sha")
        if final_record.get("candidate_tree_oid") != repo.get("candidate_tree_oid"):
            errors.append(f"final pass {ids[-1]} candidate_tree_oid must equal repo.candidate_tree_oid")


def _check_model_profile(profile_id: str, label: str, errors: List[str]) -> None:
    profiles = _load_model_profiles()
    profile = profiles.get("profiles", {}).get(profile_id)
    if not profile:
        errors.append(f"{label} unsupported model profile: {profile_id}")
        return
    if not profile.get("verified"):
        errors.append(f"{label} model profile is not verified: {profile_id}")
    model_id = profile.get("model_id")
    for disallowed in profiles.get("disallowed_until_reprobed", []):
        if disallowed.get("model_id") == model_id:
            errors.append(f"{label} model {model_id} is disallowed until re-probed")


def _check_qa(manifest: Dict[str, Any], errors: List[str]) -> None:
    ids = all_pass_ids(manifest)
    pass_records = pass_records_by_id(manifest)
    qa_records = normalize_qa_records(manifest)

    if not isinstance(manifest.get("qa", {}).get("records"), list):
        errors.append("qa.records array is required; legacy single qa object is not authoritative")
    if not qa_records:
        errors.append("no QA records present")

    seen: dict[str, int] = {}
    qa_run_ids: set[str] = set()
    qa_role_run_ids: set[str] = set()
    pass_role_run_ids = {record.get("role_run_id") for record in pass_records.values() if record.get("role_run_id")}
    for record in qa_records:
        qa_label = record.get("qa_run_id", "<unknown>")
        qa_run_id = record.get("qa_run_id", "")
        qa_role_run_id = record.get("role_run_id", "")
        pass_id = record.get("qa_for_pass_id", "")
        pass_record = pass_records.get(pass_id, {})
        seen[pass_id] = seen.get(pass_id, 0) + 1
        if pass_id not in ids:
            errors.append(f"qa record {qa_label} references unknown pass {pass_id}")
        _check_model_profile(record.get("model_profile", ""), "qa", errors)
        if record.get("verdict") not in {"pass", "fail"}:
            errors.append(f"qa {qa_label} verdict must be pass or fail")
        for field in ["report_hash", "event_log_hash", "protected_execution_record_sha256", "protected_probe_record_sha256"]:
            value = record.get(field, "")
            if value:
                _validate_sha256(value, f"qa.{field}", errors)
        for field in ["candidate_sha", "base_sha", "candidate_tree_oid"]:
            _validate_sha(record.get(field, ""), 40, f"qa {qa_label}.{field}", errors)
            if pass_record and record.get(field) != pass_record.get(field):
                errors.append(f"qa {qa_label} {field} does not match pass {pass_id}")
        if not record.get("agent_id"):
            errors.append(f"qa {qa_label} missing agent_id")
        if not qa_run_id:
            errors.append("qa record missing qa_run_id")
        elif qa_run_id in qa_run_ids:
            errors.append(f"qa_run_id must be unique: {qa_run_id}")
        else:
            qa_run_ids.add(qa_run_id)
        if not qa_role_run_id:
            errors.append(f"qa {qa_label} missing role_run_id")
        elif qa_role_run_id in qa_role_run_ids:
            errors.append(f"QA role_run_id must be unique: {qa_role_run_id}")
        elif qa_role_run_id in pass_role_run_ids:
            errors.append(f"QA role_run_id reuses implementation/remediation role_run_id: {qa_role_run_id}")
        else:
            qa_role_run_ids.add(qa_role_run_id)

        iso = record.get("isolation_proof", {})
        if iso:
            expected_tree = pass_record.get("candidate_tree_oid") if pass_record else record.get("candidate_tree_oid")
            if iso.get("candidate_tree_before") != expected_tree:
                errors.append("qa isolation candidate_tree_before must equal the QA generation candidate_tree_oid")
            if iso.get("candidate_tree_after") != expected_tree:
                errors.append("qa isolation candidate_tree_after must equal the QA generation candidate_tree_oid")
            if iso.get("candidate_tree_before") != iso.get("candidate_tree_after"):
                errors.append("candidate tree changed during QA")
            for flag, required in [
                ("source_mount_read_only", True),
                ("scratch_separate_from_source", True),
                ("host_home_mounted", False),
                ("ssh_config_mounted", False),
                ("gh_config_mounted", False),
                ("ambient_credentials_available", False),
                ("context_files_disabled", True),
                ("extensions_disabled", True),
                ("skills_disabled", True),
                ("themes_disabled", True),
                ("write_tools_observed", False),
            ]:
                if iso.get(flag) is not required:
                    errors.append(f"qa isolation {flag} must be {required}")

    for pass_id in ids:
        count = seen.get(pass_id, 0)
        if count != 1:
            errors.append(f"pass {pass_id} must have exactly one QA record, got {count}")
    for pass_id, count in seen.items():
        if count > 1:
            errors.append(f"pass {pass_id} has multiple QA records ({count})")


def _command_matches_registry(command: Dict[str, Any], registry_id: str, registry: Dict[str, Any]) -> bool:
    spec = registry.get(registry_id)
    if not spec:
        return False
    if command.get("category") != spec.get("category"):
        return False
    expected = spec.get("argv", [])
    actual = command.get("argv", [])
    if len(actual) != len(expected):
        return False
    grammars = spec.get("placeholder_grammars", {})
    for template, value in zip(expected, actual):
        pattern = re.escape(template)
        placeholders = re.findall(r"\{\{([a-z0-9_]+)\}\}", template)
        for placeholder in placeholders:
            grammar = grammars.get(placeholder)
            if not isinstance(grammar, str) or not grammar.startswith("^") or not grammar.endswith("$"):
                return False
            token = re.escape("{{" + placeholder + "}}")
            pattern = pattern.replace(token, "(?:" + grammar[1:-1] + ")")
        if re.fullmatch(pattern, value) is None:
            return False
    return True


def _check_commands(manifest: Dict[str, Any], errors: List[str]) -> None:
    registry = _registry_commands()
    commands = manifest.get("commands", [])
    ids = [command.get("command_id") for command in commands]
    if len(ids) != len(set(ids)):
        errors.append("command_id values must be unique")

    by_id = {command.get("command_id"): command for command in commands}
    for list_name in ["validations", "tests"]:
        for command_id in manifest.get(list_name, []):
            if command_id not in by_id:
                errors.append(f"{list_name} references missing command_id {command_id}")

    for command in commands:
        joined = " ".join(command.get("argv", []))
        registry_id = command_registry_id(command)
        if registry_id not in registry:
            errors.append(f"unregistered command: {registry_id or command.get('command_id')}")
            continue
        if not _command_matches_registry(command, registry_id, registry):
            errors.append(f"command {command.get('command_id')} does not match registry entry {registry_id}")
        if "scripts/validate_repo.py" in joined and command.get("category") == "test":
            errors.append(f"command {command.get('command_id')}: validate_repo.py cannot be categorized as test")
        for field in ["stdout_sha256", "stderr_sha256"]:
            _validate_sha256(command.get(field, ""), f"command {command.get('command_id')}.{field}", errors)
        for field in ["commit_sha", "tree_oid"]:
            value = command.get(field, "")
            if value:
                _validate_sha(value, 40, f"command {command.get('command_id')}.{field}", errors)
        if command.get("started_at"):
            _parse_time(command["started_at"], f"command {command.get('command_id')}.started_at", errors)
        if command.get("finished_at"):
            _parse_time(command["finished_at"], f"command {command.get('command_id')}.finished_at", errors)


def _check_state_transitions(
    manifest: Dict[str, Any], errors: List[str], target_branch: str
) -> None:
    sm = _load_state_machine()
    state_ids = set(sm.get("states", {}))
    transition_specs = sm.get("transitions", [])
    transitions = manifest.get("state_transitions", [])
    if not isinstance(transitions, list):
        errors.append("state_transitions must be an array")
        return
    if not transitions:
        errors.append("state_transitions must record the governed delivery path")
        return

    candidate_pinned_at = _parse_time(
        manifest.get("repo", {}).get("candidate_pinned_at", ""),
        "repo.candidate_pinned_at",
        errors,
    )
    previous_target = None
    previous_time = None
    observed_edges = set()
    for index, transition in enumerate(transitions):
        if not isinstance(transition, dict):
            errors.append(f"state_transition {index} must be an object")
            continue
        source = transition.get("from")
        target = transition.get("to")
        authority = transition.get("authority")
        if previous_target is not None and source != previous_target:
            errors.append(f"state_transition path is discontinuous: expected from {previous_target}, got {source}")
        if source not in state_ids:
            errors.append(f"state_transition from unknown state: {source}")
            continue
        if target not in state_ids:
            errors.append(f"state_transition to unknown state: {target}")
            continue
        matching = [
            spec for spec in transition_specs
            if (spec.get("from") == source or spec.get("from") == "*") and spec.get("to") == target
        ]
        if not matching:
            errors.append(f"state_transition not allowed: {source}->{target}")
            continue
        if not any(authority in spec.get("authorized_roles", []) for spec in matching):
            errors.append(f"state_transition {source}->{target} not authorized for {authority}")
        timestamp = _parse_time(transition.get("timestamp", ""), f"state_transition {source}->{target}", errors)
        if timestamp and previous_time and timestamp <= previous_time:
            errors.append(f"state_transition timestamp did not advance at {source}->{target}")
        if (
            source == "IMPLEMENTING"
            and target == "CANDIDATE_PINNED"
            and timestamp
            and candidate_pinned_at
            and timestamp != candidate_pinned_at
        ):
            errors.append(
                "IMPLEMENTING->CANDIDATE_PINNED timestamp must equal "
                "repo.candidate_pinned_at"
            )
        if timestamp:
            previous_time = timestamp
        previous_target = target
        observed_edges.add((source, target))

    required_edges = {
        ("AUDITED", "ISSUE_ACCEPTED"),
        ("ISSUE_ACCEPTED", "PLAN_REQUESTED"),
        ("PLAN_REQUESTED", "PLAN_READY"),
        ("PLAN_READY", "IMPLEMENTING"),
        ("IMPLEMENTING", "CANDIDATE_PINNED"),
    }
    for source, target in sorted(required_edges - observed_edges):
        errors.append(f"required state_transition missing: {source}->{target}")


def _check_publication(manifest: Dict[str, Any], errors: List[str]) -> None:
    publication = manifest.get("publication", {})
    for field in ["merge_result_sha", "publication_sha", "tag_sha", "deploy_sha"]:
        value = publication.get(field, "")
        if value and not SHA1_RE.match(value):
            errors.append(f"publication.{field} must be empty or a full 40-character lowercase hex SHA, got {value!r}")


def _check_schema_references(errors: List[str]) -> None:
    for path in [
        REPO_ROOT / "governance/state-machine.json",
        REPO_ROOT / "governance/model-profiles.json",
        REPO_ROOT / "governance/command-registry.json",
        REPO_ROOT / "governance/issue-status.json",
        REPO_ROOT / "governance/audits/existing-work-freeze.json",
        REPO_ROOT / "governance/bootstrap-status.json",
    ]:
        data = load_json_strict(path)
        schema_ref = data.get("$schema")
        if not schema_ref:
            errors.append(f"{path.relative_to(REPO_ROOT)} missing $schema reference")
            continue
        if not schema_ref.startswith("./") and not schema_ref.startswith("../"):
            continue
        schema_path = (path.parent / schema_ref).resolve()
        if not schema_path.exists():
            errors.append(f"{path.relative_to(REPO_ROOT)} references missing schema {schema_ref}")
            continue
        schema = load_json_strict(schema_path)
        schema_errors = validate_schema(data, schema)
        for err in schema_errors:
            errors.append(f"{path.relative_to(REPO_ROOT)} schema error: {err}")


def check(
    manifest: Dict[str, Any],
    path: str = "<manifest>",
    *,
    target_branch: str = "main",
) -> List[str]:
    """Run validation checks. Returns error messages."""
    errors: List[str] = []

    try:
        errors.extend(
            f"schema: {err}" for err in validate_schema(manifest, _load_schema())
        )
    except Exception as exc:
        errors.append(f"schema validation failed internally: {exc}")
        return errors
    if errors:
        return errors

    # If required top-level fields are absent, semantic checks would cascade.
    required = [
        "schema_version", "policy", "repo", "issue", "pull_request", "passes",
        "qa", "commands", "validations", "tests", "state_transitions", "approvals", "publication",
    ]
    missing = [field for field in required if field not in manifest]
    if missing:
        return errors + [f"missing required field: {field}" for field in missing]

    if target_branch not in {"dev", "main"}:
        return errors + [f"unsupported governed target branch: {target_branch}"]

    _check_schema_references(errors)
    _check_policy(manifest, errors)
    _check_repo_and_pr(manifest, errors, target_branch)
    _check_issue(manifest, errors)
    _check_passes(manifest, errors)
    _check_qa(manifest, errors)
    _check_commands(manifest, errors)
    _check_state_transitions(manifest, errors, target_branch)
    _check_publication(manifest, errors)

    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: check_evidence_manifest.py <manifest.json>", file=sys.stderr)
        return 1

    manifest_path = sys.argv[1]
    try:
        manifest = load_json_strict(manifest_path)
    except (FileNotFoundError, json.JSONDecodeError, DuplicateKeyError, ValueError) as exc:
        print(f"Error reading manifest: {exc}", file=sys.stderr)
        return 1

    errors = check(manifest, manifest_path)
    if errors:
        print(f"Evidence manifest validation FAILED ({len(errors)} errors):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"Evidence manifest validation PASSED: {manifest_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
