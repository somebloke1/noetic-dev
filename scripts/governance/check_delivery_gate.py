#!/usr/bin/env python3
"""Fail-closed delivery gate for noetic-dev governance.

The gate distinguishes repository validation from genuine tests and refuses to
promote advisory/local evidence to merge or publication readiness. It requires
captured GitHub API/artifact-attestation payloads supplied as external protected
evidence; it never treats a manifest-controlled boolean as authoritative
provenance.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:  # Optional; the fallback scanner keeps the checker dependency-light.
    import yaml as _yaml  # type: ignore
except ImportError:  # pragma: no cover - exercised only when PyYAML is absent.
    _yaml = None

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_evidence_manifest import (  # noqa: E402
    all_pass_ids,
    command_registry_id,
    normalize_qa_records,
    pass_records_by_id,
)
from hash_tree import canonical_json_sha256, manifest_digest_excluding_own, sha256_file, validate_sha_hex  # noqa: E402
from json_schema import DuplicateKeyError, load_json_strict, validate_schema  # noqa: E402
from route_evidence import protected_ci_snapshot  # noqa: E402

SHA1_RE = re.compile(r"^[a-f0-9]{40}$")
PINNED_ACTION_RE = re.compile(r"^[a-f0-9]{40}$")
IMAGE_DIGEST_RE = re.compile(r"@sha256:[a-f0-9]{64}$")
WIP_PREFIXES = ("[WIP]", "WIP:", "Draft:", "Do not merge:", "Checkpoint:")
REPO_FULL_NAME = "somebloke1/noetic-dev"
REPOSITORY_OWNER = "somebloke1"
QA_TOOL_ALLOWLIST: set[str] = set()
ALLOWED_MERGE_METHODS = {"squash", "rebase"}
LOCAL_PROTECTED_EXTERNAL_INTEGRATION_AVAILABLE = False
BOOTSTRAP_AUTHORITY_FIELDS = [
    "protected_policy_ref_established",
    "trusted_runner_provenance_established",
    "branch_protection_requires_governance",
    "independent_agent_review_process_established",
    "credential_broker_established",
]


def load_json(path: str) -> Dict[str, Any]:
    return load_json_strict(path)


def _load_repo_json(relative: str) -> Dict[str, Any]:
    return load_json_strict(REPO_ROOT / relative)


def _command_registry() -> Dict[str, Any]:
    return _load_repo_json("governance/command-registry.json")


def _issue_statuses() -> Dict[str, Any]:
    return _load_repo_json("governance/issue-status.json").get("statuses", {})


def _model_profiles() -> Dict[str, Any]:
    return _load_repo_json("governance/model-profiles.json")


def _parse_time(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA1_RE.fullmatch(value))


def _truth(value: Any) -> bool:
    return value is True


def _workflow_paths(path: str) -> List[Path]:
    target = Path(path)
    if target.is_dir():
        return sorted([*target.glob("*.yml"), *target.glob("*.yaml")])
    return [target]


def _image_is_digest_pinned(image_ref: str) -> bool:
    return bool(IMAGE_DIGEST_RE.search(image_ref.strip().strip('"\'')))


def _strip_scalar(value: str) -> str:
    value = value.strip()
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value.strip().strip('"\'')


def _workflow_image_refs_from_yaml(content: str) -> List[Tuple[str, str]]:
    """Return job container and service image refs from workflow YAML.

    PyYAML is used when available; the fallback scanner covers the GitHub
    workflow subset used here so the checker remains dependency-light in CI.
    """
    refs: List[Tuple[str, str]] = []
    if _yaml is not None:
        try:
            loaded = _yaml.safe_load(content) or {}
        except Exception:
            loaded = {}
        jobs = loaded.get("jobs", {}) if isinstance(loaded, dict) else {}
        if isinstance(jobs, dict):
            for job_id, job in jobs.items():
                if not isinstance(job, dict):
                    continue
                container = job.get("container")
                if isinstance(container, str):
                    refs.append((f"job container {job_id}", container))
                elif isinstance(container, dict) and isinstance(container.get("image"), str):
                    refs.append((f"job container {job_id}", container["image"]))
                services = job.get("services", {})
                if isinstance(services, dict):
                    for service_id, service in services.items():
                        if isinstance(service, str):
                            refs.append((f"service {job_id}.{service_id}", service))
                        elif isinstance(service, dict) and isinstance(service.get("image"), str):
                            refs.append((f"service {job_id}.{service_id}", service["image"]))
            return refs

    # Fallback for common workflow syntax: scalar/inline container refs and
    # image: entries nested under container/services mappings.
    active_blocks: List[Tuple[int, str]] = []
    for raw in content.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        text = raw.strip()
        while active_blocks and indent <= active_blocks[-1][0]:
            active_blocks.pop()
        container_match = re.match(r"container:\s*(.*)$", text)
        if container_match:
            value = _strip_scalar(container_match.group(1))
            if value:
                inline = re.search(r"(?:^|[{,]\s*)image\s*:\s*([^,}]+)", value)
                refs.append(("job container", _strip_scalar(inline.group(1) if inline else value)))
            else:
                active_blocks.append((indent, "job container"))
            continue
        if re.match(r"services:\s*$", text):
            active_blocks.append((indent, "service"))
            continue
        image_match = re.match(r"image:\s*(.+)$", text)
        if image_match and any(label in {"job container", "service"} for _i, label in active_blocks):
            label = active_blocks[-1][1]
            refs.append((label, _strip_scalar(image_match.group(1))))
    return refs


def check_pinning(workflow_path: str) -> List[str]:
    """Check that workflow actions, job containers, and services are immutable."""
    errors: List[str] = []
    action_pattern = re.compile(
        r"^\s+(?:-\s+)?uses:\s+([^\s#]+)",
        re.MULTILINE,
    )

    for path in _workflow_paths(workflow_path):
        if not path.exists():
            errors.append(f"workflow path not found: {path}")
            continue
        content = path.read_text(encoding="utf-8")
        for match in action_pattern.finditer(content):
            uses = match.group(1).strip().strip('"\'')
            if uses.startswith("./"):
                continue
            if uses.startswith("docker://"):
                image_ref = uses.removeprefix("docker://")
                if not _image_is_digest_pinned(image_ref):
                    errors.append(
                        f"unpinned docker image ref: {uses} "
                        f"(must use @sha256:<64-hex-digest>) in {path}"
                    )
                continue
            if "@" not in uses:
                errors.append(f"unpinned action ref: {uses} (missing @<sha>) in {path}")
                continue
            action, ref = uses.rsplit("@", 1)
            if action.startswith("./"):
                continue
            if not PINNED_ACTION_RE.fullmatch(ref):
                errors.append(
                    f"unpinned action ref: {action}@{ref} "
                    f"(must use full 40-char SHA) in {path}"
                )

        for label, image_ref in _workflow_image_refs_from_yaml(content):
            if not _image_is_digest_pinned(image_ref):
                errors.append(
                    f"unpinned {label} image ref: {image_ref} "
                    f"(must use @sha256:<64-hex-digest>) in {path}"
                )

    return errors


def calculate_allowed_status_labels() -> List[str]:
    """Backward-compatible helper for merge-eligible issue labels."""
    return ["status:accepted", "status:ready", "status:in_progress"]


def _canonical_status_value(label: str) -> str:
    return label.split(":", 1)[1] if isinstance(label, str) and label.startswith("status:") else ""


def _command_by_id(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {cmd.get("command_id", ""): cmd for cmd in manifest.get("commands", [])}


def _registry_matches(command: Dict[str, Any], registry_id: str, registry: Dict[str, Any]) -> bool:
    spec = registry.get("commands", {}).get(registry_id)
    if not spec:
        return False
    if command.get("category") != spec.get("category"):
        return False
    expected = spec.get("argv", [])
    actual = command.get("argv", [])
    if "{{manifest_path}}" in expected:
        fixed = [item for item in expected if item != "{{manifest_path}}"]
        return actual[: len(fixed)] == fixed
    return actual == expected


def _successful_registered_command_ids(manifest: Dict[str, Any], phase: str, *, commit_sha: str | None = None) -> set[str]:
    registry = _command_registry()
    result: set[str] = set()
    for command in manifest.get("commands", []):
        registry_id = command_registry_id(command)
        if registry_id not in registry.get("commands", {}):
            continue
        spec = registry["commands"][registry_id]
        if spec.get("phase", "pre_merge") != phase:
            continue
        if command.get("phase", spec.get("phase", "pre_merge")) != phase:
            continue
        if commit_sha is not None and command.get("commit_sha") != commit_sha:
            continue
        if command.get("exit_code") != 0:
            continue
        if _registry_matches(command, registry_id, registry):
            result.add(registry_id)
    return result


def _check_required_commands(manifest: Dict[str, Any], errors: List[str]) -> None:
    registry = _command_registry()
    commands = manifest.get("commands", [])
    by_id = _command_by_id(manifest)

    for command in commands:
        registry_id = command_registry_id(command)
        if registry_id not in registry.get("commands", {}):
            errors.append(f"unregistered command cannot satisfy gate: {registry_id or command.get('command_id')}")
            continue
        if not _registry_matches(command, registry_id, registry):
            errors.append(f"command {command.get('command_id')} does not match registry entry {registry_id}")
        if "scripts/validate_repo.py" in " ".join(command.get("argv", [])) and command.get("category") == "test":
            errors.append("validate_repo.py cannot be reported as a test")

    for command_id in manifest.get("validations", []):
        command = by_id.get(command_id)
        if not command:
            errors.append(f"validations references missing command {command_id}")
        elif command.get("category") != "validation":
            errors.append(f"validations references non-validation command {command_id}")
    for command_id in manifest.get("tests", []):
        command = by_id.get(command_id)
        if not command:
            errors.append(f"tests references missing command {command_id}")
        elif command.get("category") != "test":
            errors.append(f"tests references non-test command {command_id}")

    successful_pre = _successful_registered_command_ids(manifest, "pre_merge")
    for required in registry.get("rules", {}).get("required_pre_merge_validations", []):
        if required not in successful_pre:
            errors.append(f"required validation command missing or failed: {required}")
    for required in registry.get("rules", {}).get("required_pre_merge_tests", []):
        if required not in successful_pre:
            errors.append(f"required test command missing or failed: {required}")


def _check_pr_and_issue(
    manifest: Dict[str, Any], errors: List[str], target_branch: str
) -> None:
    pr = manifest.get("pull_request", {})
    repo = manifest.get("repo", {})
    issue = manifest.get("issue", {})

    if pr.get("draft_state"):
        errors.append("PR is a draft")
    title = pr.get("title", "")
    for prefix in WIP_PREFIXES:
        if title.startswith(prefix):
            errors.append(f"PR title has WIP prefix: {prefix}")
            break
    if pr.get("base") != target_branch or repo.get("base_branch") != target_branch:
        errors.append(
            "stacked PR/base branch rejected: PR base and repo.base_branch must both be "
            f"{target_branch}"
        )
    if pr.get("is_stacked"):
        errors.append("stacked PR rejected: pull_request.is_stacked is true")

    candidate_sha = repo.get("candidate_sha", "")
    base_sha = repo.get("base_sha", "")
    if not _is_sha(candidate_sha):
        errors.append(f"candidate SHA is not a full 40-character SHA: {candidate_sha}")
    if candidate_sha != pr.get("head_sha"):
        errors.append("candidate SHA must equal PR head SHA")
    if not _is_sha(base_sha):
        errors.append("base SHA is not a full 40-character SHA")

    issue_numbers = issue.get("numbers", [])
    linked_issues = pr.get("linked_issues", [])
    if not issue_numbers:
        errors.append("no linked issue numbers recorded")
    if not linked_issues:
        errors.append("pull_request.linked_issues is empty")
    for number in issue_numbers:
        if number not in linked_issues:
            errors.append(f"linked issue mismatch: issue {number} absent from PR linked_issues")

    labels = issue.get("labels", [])
    status_labels = [label for label in labels if isinstance(label, str) and label.startswith("status:")]
    canonical = issue.get("canonical_status", "")
    if len(status_labels) != 1:
        errors.append(f"exactly one canonical status label required, got {status_labels}")
    elif canonical != status_labels[0]:
        errors.append(f"canonical issue status {canonical!r} does not match label {status_labels[0]!r}")

    value = _canonical_status_value(canonical)
    statuses = _issue_statuses()
    if value not in statuses:
        errors.append(f"unknown issue status: {canonical}")
    elif statuses[value].get("prevents_closure"):
        errors.append(f"issue status prevents closure: {canonical}")
    elif value not in {"accepted", "ready", "in_progress"}:
        errors.append(f"issue status is not merge-eligible: {canonical}")


def _authenticated_github_response(
    envelope: Any,
    errors: List[str],
    label: str,
    response_type: type,
) -> Any:
    if not isinstance(envelope, dict):
        errors.append(f"{label} GitHub API response envelope is missing")
        return response_type()
    authentication = envelope.get("authentication")
    if (
        not isinstance(authentication, dict)
        or authentication.get("verified") is not True
        or authentication.get("source") != "protected-integration"
        or not isinstance(authentication.get("principal"), str)
        or not authentication.get("principal")
    ):
        errors.append(f"{label} GitHub API response is not authenticated")
    if envelope.get("status") != 200 or not isinstance(envelope.get("request_id"), str):
        errors.append(f"{label} GitHub API response metadata is invalid")
    if _parse_time(envelope.get("fetched_at")) is None:
        errors.append(f"{label} GitHub API capture timestamp is invalid")
    response = envelope.get("response")
    if not isinstance(response, response_type):
        errors.append(f"{label} GitHub API response body has the wrong type")
        return response_type()
    if envelope.get("response_sha256") != canonical_json_sha256(response):
        errors.append(f"{label} GitHub API response digest mismatch")
    return response


def _check_owner_promotion_authorization(
    manifest: Dict[str, Any],
    errors: List[str],
    external_evidence: Optional[Dict[str, Any]],
) -> None:
    authorization = (external_evidence or {}).get("promotion_authorization")
    if not isinstance(authorization, dict):
        errors.append("owner promotion authorization missing from protected external evidence")
        return
    candidate_sha = manifest.get("repo", {}).get("candidate_sha")
    if (
        manifest.get("repo", {}).get("candidate_branch") != "dev"
        or manifest.get("pull_request", {}).get("head_ref") != "dev"
    ):
        errors.append("main-promotion pull request head must be protected dev")
    if authorization.get("authorized") is not True:
        errors.append("owner promotion authorization is not affirmative")
    if authorization.get("authorized_by") != REPOSITORY_OWNER:
        errors.append("promotion was not authorized by the repository owner")
    if authorization.get("dev_sha") != candidate_sha:
        errors.append("owner-authorized dev SHA does not equal the promotion candidate SHA")
    if authorization.get("dev_validation_sha") != candidate_sha:
        errors.append("protected dev validation SHA does not equal the promotion candidate SHA")
    provenance = authorization.get("dev_provenance")
    if not isinstance(provenance, dict):
        errors.append("authenticated protected dev provenance is missing")
        provenance = {}
    branch_envelope = provenance.get("branch_api_response")
    branch = _authenticated_github_response(branch_envelope, errors, "protected dev branch", dict)
    if not isinstance(branch_envelope, dict) or branch_envelope.get("request_url") != (
        f"https://api.github.com/repos/{REPO_FULL_NAME}/branches/dev"
    ):
        errors.append("protected dev branch GitHub API request URL is invalid")
    commit = branch.get("commit")
    if (
        branch.get("name") != "dev"
        or branch.get("protected") is not True
        or not isinstance(commit, dict)
        or commit.get("sha") != candidate_sha
    ):
        errors.append("promotion candidate is not the authenticated protected dev head")

    applied_envelope = provenance.get("applied_rules_api_response")
    applied_rules = _authenticated_github_response(
        applied_envelope, errors, "protected dev applied rules", list
    )
    if not isinstance(applied_envelope, dict) or applied_envelope.get("request_url") != (
        f"https://api.github.com/repos/{REPO_FULL_NAME}/rules/branches/dev"
    ):
        errors.append("protected dev applied-rules GitHub API request URL is invalid")

    ruleset_envelope = provenance.get("ruleset_api_response")
    ruleset = _authenticated_github_response(ruleset_envelope, errors, "protected dev ruleset", dict)
    ruleset_id = ruleset.get("id")
    expected_ruleset_url = (
        f"https://api.github.com/repos/{REPO_FULL_NAME}/rulesets/{ruleset_id}"
        if type(ruleset_id) is int
        else ""
    )
    if not isinstance(ruleset_envelope, dict) or ruleset_envelope.get("request_url") != expected_ruleset_url:
        errors.append("protected dev ruleset GitHub API request URL is invalid")

    run_envelope = provenance.get("validation_run_api_response")
    validation_run = _authenticated_github_response(
        run_envelope, errors, "protected dev validation run", dict
    )
    run_id = validation_run.get("id")
    expected_run_api_url = (
        f"https://api.github.com/repos/{REPO_FULL_NAME}/actions/runs/{run_id}"
        if type(run_id) is int
        else ""
    )
    expected_run_url = (
        f"https://github.com/{REPO_FULL_NAME}/actions/runs/{run_id}"
        if type(run_id) is int
        else ""
    )
    if not isinstance(run_envelope, dict) or run_envelope.get("request_url") != expected_run_api_url:
        errors.append("protected dev validation-run GitHub API request URL is invalid")
    repository = validation_run.get("repository")
    if (
        not isinstance(repository, dict)
        or repository.get("full_name") != REPO_FULL_NAME
        or validation_run.get("path") != ".github/workflows/governance.yml"
        or validation_run.get("event") != "push"
        or validation_run.get("head_branch") != "dev"
        or validation_run.get("head_sha") != candidate_sha
        or validation_run.get("status") != "completed"
        or validation_run.get("conclusion") != "success"
        or validation_run.get("html_url") != expected_run_url
    ):
        errors.append("protected dev validation run is not bound to the promotion candidate")
    if protected_ci_snapshot(run_id, validation_run, applied_rules, ruleset) != _load_repo_json(
        "governance/protected-dev-ruleset.json"
    ):
        errors.append("protected dev rules are absent, bypassable, stale, or missing required checks")
    if authorization.get("issue") != 32:
        errors.append("owner promotion authorization must be recorded on issue 32")
    comment_id = authorization.get("comment_id")
    url = authorization.get("authorization_url", "")
    expected_url = (
        f"https://github.com/somebloke1/noetic-dev/issues/32#issuecomment-{comment_id}"
        if isinstance(comment_id, int)
        else ""
    )
    if re.fullmatch(
        r"https://github\.com/somebloke1/noetic-dev/issues/32#issuecomment-[1-9][0-9]*",
        url,
    ) is None or url != expected_url:
        errors.append("owner promotion authorization URL is invalid")
    if authorization.get("comment_source") != "github_api" or authorization.get("comment_verified") is not True:
        errors.append("owner promotion authorization comment is not authenticated GitHub API evidence")
    if authorization.get("comment_author") != REPOSITORY_OWNER:
        errors.append("owner promotion authorization comment author is not the repository owner")
    if authorization.get("comment_author_association") != "OWNER":
        errors.append("owner promotion authorization comment lacks OWNER association")
    expected_body = f"noetic-dev-main-promotion: authorize {candidate_sha}"
    if authorization.get("comment_body") != expected_body:
        errors.append("owner promotion authorization comment body is not the exact affirmative record")
    authorized_at = _parse_time(authorization.get("authorized_at", ""))
    comment_created_at = _parse_time(authorization.get("comment_created_at", ""))
    dev_validated_at = _parse_time(authorization.get("dev_validated_at", ""))
    pinned_at = _parse_time(manifest.get("repo", {}).get("candidate_pinned_at", ""))
    if authorized_at is None:
        errors.append("owner promotion authorization timestamp is invalid")
    elif comment_created_at is None or comment_created_at != authorized_at:
        errors.append("owner promotion authorization time does not match authenticated comment creation")
    elif dev_validated_at is None:
        errors.append("protected dev validation timestamp is invalid")
    elif _parse_time(validation_run.get("updated_at", "")) != dev_validated_at:
        errors.append("protected dev validation timestamp does not match the authenticated run")
    elif authorized_at <= dev_validated_at:
        errors.append("owner promotion authorization must follow protected dev validation")
    elif pinned_at is None:
        errors.append("candidate pin timestamp is missing or invalid for main promotion")
    elif authorized_at >= pinned_at:
        errors.append("owner promotion authorization must precede candidate pinning")
    capture_times = [
        _parse_time(envelope.get("fetched_at")) if isinstance(envelope, dict) else None
        for envelope in (branch_envelope, applied_envelope, ruleset_envelope, run_envelope)
    ]
    if (
        authorized_at is None
        or pinned_at is None
        or any(captured is None or captured < authorized_at or captured >= pinned_at for captured in capture_times)
    ):
        errors.append("protected dev API captures must follow authorization and precede candidate pinning")

def _profile_for(profile_id: str) -> Optional[Dict[str, Any]]:
    return _model_profiles().get("profiles", {}).get(profile_id)


def _profile_hash(profile_id: str) -> Optional[str]:
    profile = _profile_for(profile_id)
    return canonical_json_sha256(profile) if profile else None


def _load_schema(relative: str) -> Dict[str, Any]:
    return _load_repo_json(relative)


def _validate_record_schema(record: Dict[str, Any], schema_relative: str, label: str, errors: List[str]) -> None:
    schema = _load_schema(schema_relative)
    for error in validate_schema(record, schema):
        errors.append(f"{label} schema: {error}")


def _record_hash(record: Dict[str, Any]) -> str:
    return canonical_json_sha256(record)


def _resolve_embedded_or_path(record: Dict[str, Any], embedded_key: str, path_key: str, manifest_path: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    embedded = record.get(embedded_key)
    if isinstance(embedded, dict):
        return embedded, _record_hash(embedded)
    path_value = record.get(path_key)
    if not path_value:
        return None, None
    path = Path(path_value)
    if not path.is_absolute() and manifest_path:
        path = Path(manifest_path).resolve().parent / path
    if not path.exists():
        return None, None
    try:
        data = load_json_strict(path)
    except Exception:
        return None, None
    return data, sha256_file(path)


def _actual(record: Dict[str, Any]) -> Dict[str, Any]:
    return record.get("actual_invocation", {}) if isinstance(record, dict) else {}


def _same_list(a: Any, b: Any) -> bool:
    return isinstance(a, list) and isinstance(b, list) and a == b


def _check_probe_execution_binding(
    qa_record: Dict[str, Any],
    exec_record: Dict[str, Any],
    probe_record: Dict[str, Any],
    pass_record: Dict[str, Any],
    manifest: Dict[str, Any],
    errors: List[str],
) -> None:
    policy = manifest.get("policy", {})
    actual = _actual(exec_record)
    iso = actual.get("isolation", {})
    qa_run_id = qa_record.get("qa_run_id", "<unknown>")

    _validate_record_schema(exec_record, "governance/schemas/qa-execution-record.schema.json", f"qa {qa_run_id} execution", errors)
    _validate_record_schema(probe_record, "governance/schemas/qa-probe-record.schema.json", f"qa {qa_run_id} probe", errors)

    if exec_record.get("schema_version") != "1" or exec_record.get("role") != "qa":
        errors.append(f"qa {qa_run_id} protected execution record is not a QA schema_version=1 record")
    if exec_record.get("evidence_class", "authoritative") != "authoritative":
        errors.append(f"qa {qa_run_id} execution record is non-evidence/advisory")
    if exec_record.get("record_only"):
        errors.append(f"qa {qa_run_id} record-only execution output cannot satisfy QA evidence")
    if exec_record.get("writable_by_model") or actual.get("isolation", {}).get("protected_record_writable_by_model"):
        errors.append(f"qa {qa_run_id} protected execution record was writable by QA/model")
    if exec_record.get("run_id") != manifest.get("run_id") or probe_record.get("run_id") != manifest.get("run_id"):
        errors.append(f"qa {qa_run_id} run_id does not match manifest")
    if exec_record.get("role_run_id") != qa_record.get("role_run_id"):
        errors.append(f"qa {qa_run_id} execution role_run_id mismatch")
    if probe_record.get("role_run_id") != qa_record.get("role_run_id"):
        errors.append(f"qa {qa_run_id} probe role_run_id mismatch")
    if exec_record.get("qa_for_pass_id") != qa_record.get("qa_for_pass_id"):
        errors.append(f"qa {qa_run_id} execution qa_for_pass_id mismatch")

    generated_by = exec_record.get("generated_by", {})
    if generated_by.get("policy_commit_sha") != policy.get("sha"):
        errors.append(f"qa {qa_run_id} execution generated_by policy SHA mismatch")
    if actual.get("policy_commit_sha") != policy.get("sha"):
        errors.append(f"qa {qa_run_id} actual invocation policy SHA mismatch")
    if probe_record.get("policy_commit_sha") != policy.get("sha"):
        errors.append(f"qa {qa_run_id} probe policy SHA mismatch")

    expected_profile_id = qa_record.get("model_profile")
    expected_profile = _profile_for(expected_profile_id)
    expected_profile_hash = _profile_hash(expected_profile_id) if expected_profile else None
    if expected_profile:
        for label, record in [("execution", actual), ("probe", probe_record)]:
            if record.get("profile_id") != expected_profile_id:
                errors.append(f"qa {qa_run_id} {label} profile_id does not match qa.model_profile")
            if record.get("resolved_model") != expected_profile.get("model_id"):
                errors.append(f"qa {qa_run_id} {label} resolved_model does not match protected model profile")
            if record.get("profile_hash") != expected_profile_hash:
                errors.append(f"qa {qa_run_id} {label} profile_hash does not match protected model profile")

    comparable = [
        ("resolved_model", actual.get("resolved_model"), probe_record.get("resolved_model")),
        ("profile_id", actual.get("profile_id"), probe_record.get("profile_id")),
        ("profile_hash", actual.get("profile_hash"), probe_record.get("profile_hash")),
        ("pi_version", actual.get("pi_version"), probe_record.get("pi_version")),
        ("candidate_sha", actual.get("candidate_sha"), probe_record.get("candidate_sha")),
        ("candidate_tree_oid", actual.get("candidate_tree_oid"), probe_record.get("candidate_tree_oid")),
        ("base_sha", actual.get("base_sha"), probe_record.get("base_sha")),
    ]
    for label, left, right in comparable:
        if left != right:
            errors.append(f"qa {qa_run_id} probe/execution mismatch for {label}")

    for field in ["candidate_sha", "base_sha", "candidate_tree_oid"]:
        if qa_record.get(field) != pass_record.get(field):
            errors.append(f"QA {qa_run_id} stale/mismatched {field}")
        if actual.get(field) != pass_record.get(field):
            errors.append(f"qa {qa_run_id} execution {field} mismatch")
        if probe_record.get(field) != pass_record.get(field):
            errors.append(f"qa {qa_run_id} probe {field} mismatch")

    tools = actual.get("tools", [])
    if not _same_list(tools, probe_record.get("tools")):
        errors.append(f"qa {qa_run_id} probe/execution tools mismatch")
    if not isinstance(tools, list):
        errors.append(f"qa {qa_run_id} tools field must be a list")
    elif tools:
        errors.append(f"qa {qa_run_id} authoritative QA dispatch must use no tools until a credential broker exists")
    if not _same_list(actual.get("environment_name_allowlist"), probe_record.get("environment_name_allowlist")):
        errors.append(f"qa {qa_run_id} probe/execution environment allowlist mismatch")

    disabled_pairs = [
        ("context_files_disabled", iso.get("context_files_disabled"), probe_record.get("context_files_disabled")),
        ("extensions_disabled", iso.get("extensions_disabled"), probe_record.get("extensions_disabled")),
        ("skills_disabled", iso.get("skills_disabled"), probe_record.get("skills_disabled")),
        ("themes_disabled", iso.get("themes_disabled"), probe_record.get("themes_disabled")),
    ]
    for label, left, right in disabled_pairs:
        if left is not True or right is not True:
            errors.append(f"qa {qa_run_id} disabled-feature binding failed for {label}")

    nonce = probe_record.get("nonce", "")
    expected = f"READY {nonce}" if nonce else ""
    if probe_record.get("expected_response") != expected or probe_record.get("observed_response") != expected:
        errors.append(f"qa {qa_run_id} probe did not observe exact READY nonce response")
    if probe_record.get("exit_code") != 0:
        errors.append(f"qa {qa_run_id} probe exit code was not 0")
    if actual.get("exit_code") != 0:
        errors.append(f"qa {qa_run_id} execution exit code was not 0")
    if qa_record.get("event_log_hash") != actual.get("qa_event_log_sha256"):
        errors.append(f"qa {qa_run_id} event_log_hash does not match protected execution record")
    if probe_record.get("probe_event_log_sha256") and probe_record.get("probe_event_log_sha256") == actual.get("qa_event_log_sha256"):
        errors.append(f"qa {qa_run_id} probe event stream reused as QA event stream")

    probe_finish = _parse_time(probe_record.get("finished_at", ""))
    qa_start = _parse_time(actual.get("started_at", ""))
    if not probe_finish or not qa_start:
        errors.append(f"qa {qa_run_id} probe/QA timestamps are invalid")
    elif probe_finish > qa_start:
        errors.append(f"qa {qa_run_id} probe finished after QA started")


def _check_qa_pairing(manifest: Dict[str, Any], errors: List[str], manifest_path: Optional[str]) -> None:
    repo = manifest.get("repo", {})
    policy = manifest.get("policy", {})
    pass_ids = all_pass_ids(manifest)
    records_by_pass = pass_records_by_id(manifest)
    qa_records = normalize_qa_records(manifest)
    if not pass_ids:
        errors.append("no implementation/remediation pass IDs recorded")
        return
    if len(set(pass_ids)) != len(pass_ids):
        errors.append("implementation/remediation pass IDs are not unique")

    if len(qa_records) != len(pass_ids):
        errors.append(f"implementation:QA cardinality mismatch: {len(pass_ids)} pass(es), {len(qa_records)} QA record(s)")

    by_pass: Dict[str, List[Dict[str, Any]]] = {pass_id: [] for pass_id in pass_ids}
    for qa_record in qa_records:
        by_pass.setdefault(qa_record.get("qa_for_pass_id", ""), []).append(qa_record)
    for pass_id in pass_ids:
        count = len(by_pass.get(pass_id, []))
        if count != 1:
            errors.append(f"pass {pass_id} must have exactly one QA record, got {count}")
    for pass_id, records in by_pass.items():
        if pass_id not in pass_ids:
            errors.append(f"QA references unknown pass: {pass_id}")
        elif len(records) > 1:
            errors.append(f"pass {pass_id} has multiple QA records")

    previous_candidate_sha = repo.get("base_sha")
    for index, pass_id in enumerate(pass_ids):
        pass_record = records_by_pass.get(pass_id)
        if not pass_record:
            errors.append(f"missing pass record for {pass_id}")
            continue
        for field in ["candidate_sha", "base_sha", "candidate_tree_oid"]:
            if not _is_sha(pass_record.get(field)):
                errors.append(f"pass {pass_id} {field} is not a full 40-character SHA")
        if index == 0 and pass_record.get("base_sha") != repo.get("base_sha"):
            errors.append(f"pass {pass_id} stale base SHA")
        elif index > 0 and pass_record.get("base_sha") != previous_candidate_sha:
            errors.append(f"pass {pass_id} stale base SHA")
        previous_candidate_sha = pass_record.get("candidate_sha")

    if pass_ids:
        final_record = records_by_pass.get(pass_ids[-1], {})
        if final_record.get("candidate_sha") != repo.get("candidate_sha"):
            errors.append(f"final pass {pass_ids[-1]} candidate SHA does not match repo.candidate_sha")
        if final_record.get("candidate_tree_oid") != repo.get("candidate_tree_oid"):
            errors.append(f"final pass {pass_ids[-1]} candidate tree does not match repo.candidate_tree_oid")

    for qa_record in qa_records:
        qa_run_id = qa_record.get("qa_run_id", "<unknown>")
        pass_id = qa_record.get("qa_for_pass_id")
        pass_record = records_by_pass.get(pass_id, {})

        if qa_record.get("verdict") != "pass":
            errors.append(f"QA verdict is not 'pass' for {qa_run_id}")
        profile = _profile_for(qa_record.get("model_profile", ""))
        if not profile:
            errors.append(f"unsupported model profile for QA: {qa_record.get('model_profile')}")
        elif not profile.get("verified"):
            errors.append(f"QA model profile is not verified: {qa_record.get('model_profile')}")
        elif not qa_record.get("model_profile", "").startswith("qa"):
            errors.append(f"model profile is not authorized for QA: {qa_record.get('model_profile')}")

        if qa_record.get("agent_id") and qa_record.get("agent_id") == pass_record.get("agent_id"):
            errors.append(f"self-QA rejected for pass {pass_id}: QA agent equals implementation agent")
        if qa_record.get("role_run_id") and qa_record.get("role_run_id") == pass_record.get("role_run_id"):
            errors.append(f"self-QA rejected for pass {pass_id}: role_run_id reused")
        if not qa_record.get("agent_id"):
            errors.append(f"QA {qa_run_id} missing independent agent_id")
        if not pass_record.get("agent_id"):
            errors.append(f"pass {pass_id} missing implementation agent_id")

        for field in ["candidate_sha", "base_sha", "candidate_tree_oid"]:
            expected = pass_record.get(field)
            if qa_record.get(field) != expected:
                errors.append(f"QA {qa_run_id} stale/mismatched {field}")

        iso = qa_record.get("isolation_proof", {})
        expected_iso = {
            "source_mount_read_only": True,
            "scratch_separate_from_source": True,
            "host_home_mounted": False,
            "ssh_config_mounted": False,
            "gh_config_mounted": False,
            "ambient_credentials_available": False,
            "context_files_disabled": True,
            "extensions_disabled": True,
            "skills_disabled": True,
            "themes_disabled": True,
            "write_tools_observed": False,
        }
        for flag, expected in expected_iso.items():
            if iso.get(flag) is not expected:
                errors.append(f"QA isolation {flag} must be {expected}")
        if iso.get("candidate_tree_before") != pass_record.get("candidate_tree_oid") or iso.get("candidate_tree_after") != pass_record.get("candidate_tree_oid"):
            errors.append(f"QA {qa_run_id} candidate tree before/after must equal generation candidate_tree_oid")

        exec_record, exec_hash = _resolve_embedded_or_path(
            qa_record, "protected_execution_record", "protected_execution_record_path", manifest_path
        )
        probe_record, probe_hash = _resolve_embedded_or_path(
            qa_record, "protected_probe_record", "protected_probe_record_path", manifest_path
        )
        if not exec_record:
            errors.append(f"QA {qa_run_id} missing protected QA execution record")
            continue
        if not probe_record:
            errors.append(f"QA {qa_run_id} missing protected READY probe record")
            continue
        if qa_record.get("protected_execution_record_sha256") != exec_hash:
            errors.append(f"QA {qa_run_id} protected execution record hash mismatch")
        if qa_record.get("protected_probe_record_sha256") != probe_hash:
            errors.append(f"QA {qa_run_id} protected probe record hash mismatch")

        _check_probe_execution_binding(qa_record, exec_record, probe_record, pass_record, manifest, errors)


def _external_integration_blockers(external_evidence: Optional[Dict[str, Any]]) -> List[str]:
    """Return bootstrap blockers for the future protected integration interface."""
    bootstrap = _load_repo_json("governance/bootstrap-status.json")
    gate = bootstrap.get("authoritative_delivery_gate", {})
    blockers: List[str] = []
    if not external_evidence:
        blockers.append(
            "merge readiness blocked: no authoritative trusted runner provenance supplied; "
            "candidate-local manifest evidence is advisory only"
        )
    elif not LOCAL_PROTECTED_EXTERNAL_INTEGRATION_AVAILABLE:
        blockers.append(
            "merge readiness blocked: authoritative external integration is not available to this local gate; "
            "caller-supplied external evidence is advisory only"
        )
    elif gate.get("status") != "established":
        blockers.append(
            "merge readiness blocked: authoritative external integration is not established; "
            "caller-supplied external evidence is advisory only"
        )
    for field in BOOTSTRAP_AUTHORITY_FIELDS:
        if gate.get(field) is not True:
            blockers.append(f"bootstrap dependency unresolved: {field}")
    return blockers


def verify_authoritative_provenance(
    manifest: Dict[str, Any],
    external_evidence: Optional[Dict[str, Any]] = None,
    *,
    target_branch: str = "main",
) -> List[str]:
    """Verify the future protected-runner provenance interface, failing closed.

    During bootstrap, caller-provided JSON is parsed for diagnostics only. It is
    not accepted as authenticated provenance until the separately protected
    integration is installed and required by branch protection.
    """
    errors: List[str] = _external_integration_blockers(external_evidence)
    policy = manifest.get("policy", {})
    repo = manifest.get("repo", {})
    pr = manifest.get("pull_request", {})

    if not external_evidence:
        return errors

    for error in validate_schema(external_evidence, _load_schema("governance/schemas/external-evidence.schema.json")):
        errors.append(f"external evidence schema: {error}")
    if external_evidence.get("schema_version") != "1" or external_evidence.get("evidence_class") != "protected-external":
        errors.append("external provenance evidence must be schema_version=1 protected-external")

    mode = external_evidence.get("mode")
    if mode not in {"github_api", "github_artifact_attestation"}:
        errors.append("trusted runner provenance must be verified by GitHub API or artifact attestation")
    if mode == "github_api":
        errors.append("github_api mode is diagnostic only for review authority; signed artifact attestation is required")
    if external_evidence.get("verification_status") != "verified":
        errors.append("trusted runner provenance verification_status is not verified")

    artifact = external_evidence.get("artifact", {})
    artifact_digest = artifact.get("artifact_digest") or artifact.get("digest")
    if artifact.get("artifact_digest") and artifact.get("digest") and artifact.get("artifact_digest") != artifact.get("digest"):
        errors.append("artifact digest mismatch")
    if not artifact.get("artifact_id") and not artifact.get("id"):
        errors.append("trusted runner artifact_id missing")
    if not artifact_digest or not re.fullmatch(r"sha256:[a-f0-9]{64}", artifact_digest):
        errors.append("trusted runner artifact digest missing or invalid")
    computed_manifest_digest = manifest_digest_excluding_own(manifest)
    if artifact.get("manifest_sha256") != computed_manifest_digest:
        errors.append(
            "trusted runner canonical manifest digest mismatch: "
            f"computed={computed_manifest_digest}, recorded={artifact.get('manifest_sha256')}"
        )
    promotion_authorization_digest = canonical_json_sha256(
        external_evidence.get("promotion_authorization", {})
    )
    freeze_review_digest = canonical_json_sha256(
        external_evidence.get("freeze_review", {})
    )
    freeze_review_pr_api_digest = canonical_json_sha256(
        external_evidence.get("freeze_review", {}).get("pr_api_response", {})
    )
    review_evidence_digest = canonical_json_sha256({
        "agent_identities": external_evidence.get("agent_identities", []),
        "approvals": external_evidence.get("approvals", []),
        "promotion_authorization": external_evidence.get("promotion_authorization", {}),
        "freeze_review": external_evidence.get("freeze_review", {}),
    })
    if artifact.get("review_evidence_sha256") != review_evidence_digest:
        errors.append("protected review identity/approval evidence digest mismatch")
    if artifact.get("promotion_authorization_sha256") != promotion_authorization_digest:
        errors.append("protected promotion authorization evidence digest mismatch")
    if artifact.get("freeze_review_sha256") != freeze_review_digest:
        errors.append("protected freeze review evidence digest mismatch")
    if artifact.get("freeze_review_pr_api_sha256") != freeze_review_pr_api_digest:
        errors.append("protected freeze review PR API response digest mismatch")

    repository = external_evidence.get("repository", {})
    if repository.get("full_name") != REPO_FULL_NAME:
        errors.append(f"GitHub provenance repository mismatch: {repository.get('full_name')}")
    if repo.get("repository") and repository.get("full_name") != repo.get("repository"):
        errors.append("GitHub provenance repository does not match manifest repo.repository")
    if repo.get("repository_id") and repository.get("id") != repo.get("repository_id"):
        errors.append("GitHub provenance repository_id mismatch")

    workflow = external_evidence.get("workflow", {})
    if workflow.get("path") not in {".github/workflows/governance.yml", "governance.yml"}:
        errors.append("GitHub provenance workflow path mismatch")
    if workflow.get("sha") != policy.get("sha"):
        errors.append("GitHub provenance workflow SHA must equal protected policy SHA")
    if workflow.get("ref") != policy.get("ref"):
        errors.append("GitHub provenance workflow ref must equal policy.ref")

    run = external_evidence.get("run", {})
    if run.get("event") != "pull_request":
        errors.append("GitHub provenance event must be pull_request")
    if run.get("head_sha") != repo.get("candidate_sha"):
        errors.append("GitHub provenance run head_sha does not match candidate SHA")
    if run.get("base_branch") != target_branch:
        errors.append(f"GitHub provenance base branch must be {target_branch}")
    if run.get("conclusion") != "success":
        errors.append("GitHub provenance run conclusion must be success")
    if not run.get("id") or not run.get("attempt"):
        errors.append("GitHub provenance run id/attempt missing")

    job = external_evidence.get("job", {})
    if job.get("conclusion") != "success":
        errors.append("GitHub provenance job conclusion must be success")
    if not job.get("id") or not job.get("name"):
        errors.append("GitHub provenance job id/name missing")

    gh_pr = external_evidence.get("pull_request", {})
    if gh_pr.get("number") != pr.get("number"):
        errors.append("GitHub provenance PR number mismatch")
    if gh_pr.get("base_ref") != target_branch:
        errors.append(f"GitHub provenance PR base ref must be {target_branch}")
    if gh_pr.get("head_ref") != repo.get("candidate_branch"):
        errors.append("GitHub provenance PR head ref mismatch")
    if gh_pr.get("head_sha") != repo.get("candidate_sha"):
        errors.append("GitHub provenance PR head SHA mismatch")

    protected_ref = external_evidence.get("protected_ref", {})
    if protected_ref.get("ref") != policy.get("ref"):
        errors.append("protected policy ref mismatch")
    if protected_ref.get("sha") != policy.get("sha"):
        errors.append("protected policy SHA mismatch")
    if protected_ref.get("protected") is not True:
        errors.append("policy ref is not independently protected")
    if not _is_sha(policy.get("sha")):
        errors.append("policy SHA must be full 40-character SHA")
    if policy.get("sha") == repo.get("candidate_sha"):
        errors.append("candidate checkout reused as protected policy checkout")

    checkouts = external_evidence.get("checkouts", {})
    if checkouts.get("policy_sha") != policy.get("sha"):
        errors.append("protected policy checkout SHA mismatch")
    if checkouts.get("candidate_sha") != repo.get("candidate_sha"):
        errors.append("candidate checkout SHA mismatch")
    if checkouts.get("policy_path") == checkouts.get("candidate_path"):
        errors.append("candidate checkout reused as policy checkout")
    if checkouts.get("separate") is not True:
        errors.append("policy and candidate checkouts are not separate")

    generator = external_evidence.get("generator", {})
    if generator.get("path") != policy.get("generator_path"):
        errors.append("manifest generator path provenance mismatch")
    if generator.get("from_policy_checkout") is not True:
        errors.append("manifest was generated by candidate-modifiable code")

    external_file_hashes = external_evidence.get("policy_file_hashes", {})
    if not external_file_hashes:
        errors.append("protected policy file hashes missing from external provenance")
    if external_file_hashes and external_evidence.get("policy_file_hashes_source") != "protected_checkout":
        errors.append("policy file hashes were not computed from protected checkout")
    for path, recorded_hash in policy.get("file_hashes", {}).items():
        if external_file_hashes.get(path) != recorded_hash:
            errors.append(f"policy file hash mismatch: {path}")
    generator_path = policy.get("generator_path")
    if generator_path and external_file_hashes.get(generator_path) != policy.get("generator_sha256"):
        errors.append("policy generator_sha256 does not match protected checkout hash")

    branch_protection = external_evidence.get("branch_protection", {})
    if branch_protection.get("requires_governance") is not True:
        errors.append("branch protection does not require governance checks")

    if mode == "github_artifact_attestation":
        signed = external_evidence.get("signed_attestation", {})
        subject = signed.get("subject", {})
        claims = signed.get("claims", {})
        if signed.get("verified") is not True:
            errors.append("GitHub artifact attestation is not verified")
        if subject.get("digest") != artifact_digest:
            errors.append("artifact attestation subject digest mismatch")
        for label, expected in [
            ("repository", REPO_FULL_NAME),
            ("workflow_sha", policy.get("sha")),
            ("head_sha", repo.get("candidate_sha")),
            ("run_id", run.get("id")),
            ("job_id", job.get("id")),
            ("event", "pull_request"),
            ("review_evidence_sha256", review_evidence_digest),
            ("promotion_authorization_sha256", promotion_authorization_digest),
            ("freeze_review_sha256", freeze_review_digest),
            ("freeze_review_pr_api_sha256", freeze_review_pr_api_digest),
        ]:
            if claims.get(label) != expected:
                errors.append(f"artifact attestation claim mismatch: {label}")

    return errors


def _check_approvals(manifest: Dict[str, Any], errors: List[str], external_evidence: Optional[Dict[str, Any]]) -> None:
    pr = manifest.get("pull_request", {})
    repo = manifest.get("repo", {})
    records = pass_records_by_id(manifest)
    implementation_agents = {record.get("agent_id") for record in records.values() if record.get("agent_id")}
    implementation_role_runs = {record.get("role_run_id") for record in records.values() if record.get("role_run_id")}
    qa_agents = {record.get("agent_id") for record in normalize_qa_records(manifest) if record.get("agent_id")}
    qa_role_runs = {record.get("role_run_id") for record in normalize_qa_records(manifest) if record.get("role_run_id")}
    candidate_sha = repo.get("candidate_sha")
    candidate_pinned_at = _parse_time(repo.get("candidate_pinned_at", ""))
    if not candidate_pinned_at:
        errors.append("candidate_pinned_at missing or invalid; approval recency cannot be verified")

    approvals = (external_evidence or {}).get("approvals", [])
    identity_records = (external_evidence or {}).get("agent_identities", [])
    identities: Dict[str, str] = {}
    principal_agents: Dict[str, str] = {}
    for record in identity_records:
        agent_id = record.get("agent_id", "")
        if not agent_id or agent_id in identities:
            errors.append(f"protected agent identity is missing or duplicated: {agent_id or '<empty>'}")
            continue
        if record.get("provider") != "protected-runner" or record.get("verified") is not True or not record.get("principal_id"):
            errors.append(f"protected agent identity is not verified: {agent_id}")
            continue
        principal_id = record["principal_id"]
        if principal_id in principal_agents:
            errors.append(f"protected canonical principal is assigned to multiple aliases: {principal_id}")
            continue
        identities[agent_id] = principal_id
        principal_agents[principal_id] = agent_id
    for agent_id in sorted(implementation_agents | qa_agents):
        if agent_id not in identities:
            errors.append(f"protected canonical identity missing for implementation/QA agent: {agent_id}")
    author = pr.get("author", "")
    if not author or author not in identities:
        errors.append(f"protected canonical identity missing for PR author: {author or '<empty>'}")
    if not approvals:
        errors.append("no external protected approval evidence supplied")

    valid = False
    reviewer_role_runs: set[str] = set()
    for approval in approvals:
        reviewer = approval.get("reviewer", "") or approval.get("user", "")
        agent_id = approval.get("agent_id", "")
        role_run_id = approval.get("role_run_id", "")
        identity_binding = approval.get("identity_binding", {})
        model_profile_id = approval.get("model_profile", "")
        model_profile = _profile_for(model_profile_id)
        reasoning_level = approval.get("reasoning_level", "")
        approval_time = _parse_time(approval.get("submitted_at", "") or approval.get("timestamp", ""))
        if not reviewer:
            errors.append("approval missing reviewer")
            continue
        if not agent_id or reviewer != agent_id:
            errors.append(f"approval reviewer identity is not bound to protected agent_id: {reviewer}")
            continue
        if not role_run_id:
            errors.append(f"approval by {reviewer} missing reviewer role_run_id")
            continue
        if role_run_id in reviewer_role_runs:
            errors.append(f"approval by {reviewer} duplicated reviewer role_run_id: {role_run_id}")
            continue
        reviewer_role_runs.add(role_run_id)
        if identity_binding.get("provider") != "protected-runner" or identity_binding.get("verified") is not True or identity_binding.get("subject") != agent_id:
            errors.append(f"approval by {reviewer} lacks verified protected-runner identity binding")
            continue
        reviewer_principal = identities.get(agent_id)
        if not reviewer_principal:
            errors.append(f"approval by {reviewer} has no protected canonical principal")
            continue
        implementation_principals = {identities[item] for item in implementation_agents if item in identities}
        qa_principals = {identities[item] for item in qa_agents if item in identities}
        author_principal = identities.get(author)
        if reviewer_principal == author_principal:
            errors.append(f"approval by PR author principal is not independent: {reviewer_principal}")
            continue
        if reviewer_principal in implementation_principals:
            errors.append(f"approval by implementation principal is not independent: {reviewer_principal}")
            continue
        if reviewer_principal in qa_principals:
            errors.append(f"approval by QA principal is not independent: {reviewer_principal}")
            continue
        if approval.get("commit_sha") != candidate_sha:
            errors.append(f"approval by {reviewer} is stale or for wrong SHA")
            continue
        if approval_time is None:
            errors.append(f"approval by {reviewer} has invalid timestamp")
            continue
        if candidate_pinned_at and approval_time <= candidate_pinned_at:
            errors.append(f"approval by {reviewer} predates candidate SHA pinning")
            continue
        if approval.get("state") != "APPROVED":
            errors.append(f"approval by {reviewer} state is not APPROVED")
            continue
        if reviewer == author:
            errors.append(f"approval by PR author is not independent: {reviewer}")
            continue
        if reviewer in implementation_agents:
            errors.append(f"approval by implementation identity is not independent: {reviewer}")
            continue
        if reviewer in qa_agents:
            errors.append(f"approval by QA identity is not independent: {reviewer}")
            continue
        if role_run_id in implementation_role_runs:
            errors.append(f"approval by {reviewer} reused implementation role_run_id")
            continue
        if role_run_id in qa_role_runs:
            errors.append(f"approval by {reviewer} reused QA role_run_id")
            continue
        if model_profile_id not in {"reviewer_fable", "reviewer_sol"} or not model_profile or not model_profile.get("verified"):
            errors.append(f"approval by {reviewer} did not use an authorized independent reviewer profile")
            continue
        if reasoning_level not in {"high", "xhigh", "max"}:
            errors.append(f"approval by {reviewer} did not use high reasoning")
            continue
        valid = True

    if not valid:
        errors.append("no independent current-SHA high-reasoning agent approval recorded")


def _check_terminal_state(
    manifest: Dict[str, Any], errors: List[str], phase: str, target_branch: str
) -> None:
    transitions = manifest.get("state_transitions", [])
    if not transitions:
        return
    terminal = transitions[-1].get("to")
    allowed = (
        {"READY_TO_INTEGRATE_DEV", "MERGED_TO_DEV", "POST_DEV_VALIDATING", "MAIN_PROMOTION_PENDING"}
        if target_branch == "dev"
        else {"READY_TO_MERGE", "MERGED_TO_MAIN", "POST_MERGE_VALIDATING", "PUBLICATION_READY", "PUBLISHED", "DEPLOYED"}
    )
    if phase == "publication":
        allowed = {"PUBLICATION_READY", "PUBLISHED", "DEPLOYED"}
    if terminal not in allowed:
        errors.append(f"delivery state {terminal} is not eligible for {phase}")


def _protected_freeze() -> Dict[str, Any]:
    return _load_repo_json("governance/audits/existing-work-freeze.json")


def _check_publication(manifest: Dict[str, Any], errors: List[str], external_evidence: Optional[Dict[str, Any]]) -> None:
    publication = manifest.get("publication", {})
    registry = _command_registry()

    merge_sha = publication.get("merge_result_sha", "")
    publication_sha = publication.get("publication_sha", "")
    if not _is_sha(merge_sha):
        errors.append("publication blocked: merge_result_sha must be a full 40-character SHA")
    if not _is_sha(publication_sha):
        if publication_sha:
            errors.append(f"branch-name publication forbidden: {publication_sha}")
        else:
            errors.append("publication blocked: publication_sha missing")
    if merge_sha and publication_sha and merge_sha != publication_sha:
        errors.append("publication_sha must equal merge_result_sha for this composition-root publication")

    post_merge = (external_evidence or {}).get("post_merge", {})
    if not post_merge:
        errors.append("publication blocked: protected post-merge main-run evidence missing")
    else:
        if post_merge.get("event") != "push" or post_merge.get("ref") != "refs/heads/main":
            errors.append("publication blocked: post-merge evidence must be a push to refs/heads/main")
        if post_merge.get("sha") != publication_sha or post_merge.get("merge_result_sha") != merge_sha:
            errors.append("publication blocked: post-merge evidence SHA mismatch")
        if post_merge.get("main_contains_sha") is not True:
            errors.append("publication blocked: publication SHA is not verified on main")
        if post_merge.get("merge_method") not in ALLOWED_MERGE_METHODS:
            errors.append("publication blocked: merge method must be squash or rebase")

    successful_post = _successful_registered_command_ids(manifest, "post_merge", commit_sha=publication_sha if _is_sha(publication_sha) else None)
    for required in registry.get("rules", {}).get("required_post_merge_validations", []):
        if required not in successful_post:
            errors.append(f"publication blocked: required post-merge validation missing or failed: {required}")
    for required in registry.get("rules", {}).get("required_post_merge_tests", []):
        if required not in successful_post:
            errors.append(f"publication blocked: required post-merge test missing or failed: {required}")

    freeze = _protected_freeze()
    external_freeze = (external_evidence or {}).get("freeze")
    if external_freeze and external_freeze != freeze:
        errors.append("publication blocked: external freeze evidence does not match protected freeze artifact")
    repair = freeze.get("authorized_repair", {})
    freeze_review = (external_evidence or {}).get("freeze_review")
    if not isinstance(freeze_review, dict):
        errors.append("publication blocked: protected independent freeze review evidence missing")
    else:
        if freeze_review.get("verdict") != "pass" or freeze_review.get("independent") is not True:
            errors.append("publication blocked: freeze review did not independently pass")
        if freeze_review.get("audit_sha256") != freeze.get("audit_sha256"):
            errors.append("publication blocked: freeze review audit digest mismatch")
        reviewed_candidate_sha = freeze_review.get("reviewed_candidate_sha", "")
        if not _is_sha(reviewed_candidate_sha):
            errors.append("publication blocked: freeze review candidate SHA is invalid")
        if reviewed_candidate_sha != freeze.get("reviewed_candidate_sha"):
            errors.append("publication blocked: freeze review candidate SHA mismatch")
        if freeze_review.get("pull_request") != freeze.get("reviewed_pull_request"):
            errors.append("publication blocked: freeze review PR binding mismatch")
        if freeze_review.get("pr_source") != "github_api" or freeze_review.get("pr_verified") is not True:
            errors.append("publication blocked: freeze review PR is not authenticated GitHub API evidence")
        if freeze_review.get("pr_head_ref") != repair.get("head"):
            errors.append("publication blocked: freeze review PR head ref mismatch")
        if freeze_review.get("pr_base_ref") != repair.get("base"):
            errors.append("publication blocked: freeze review PR base ref mismatch")
        if freeze_review.get("pr_head_sha") != reviewed_candidate_sha:
            errors.append("publication blocked: freeze review PR head SHA mismatch")
        if freeze_review.get("pr_linked_issues") != [32]:
            errors.append("publication blocked: freeze review PR must link only issue 32")
        pr_api = freeze_review.get("pr_api_response", {})
        pr_response = pr_api.get("response", {}) if isinstance(pr_api, dict) else {}
        expected_pr_url = (
            "https://api.github.com/repos/somebloke1/noetic-dev/pulls/"
            f"{freeze_review.get('pull_request')}"
        )
        if pr_api.get("request_url") != expected_pr_url or pr_api.get("status") != 200:
            errors.append("publication blocked: freeze review PR API request binding is invalid")
        authentication = pr_api.get("authentication", {})
        if (
            authentication.get("verified") is not True
            or authentication.get("source") != "protected-integration"
            or not authentication.get("principal")
            or not pr_api.get("request_id")
        ):
            errors.append("publication blocked: freeze review PR API response is not authenticated")
        computed_pr_response_digest = canonical_json_sha256(pr_response)
        if pr_api.get("response_sha256") != computed_pr_response_digest:
            errors.append("publication blocked: freeze review PR API response digest mismatch")
        expected_pr_response = {
            "number": freeze_review.get("pull_request"),
            "state": pr_response.get("state"),
            "head_ref": freeze_review.get("pr_head_ref"),
            "head_sha": freeze_review.get("pr_head_sha"),
            "base_ref": freeze_review.get("pr_base_ref"),
            "linked_issues": freeze_review.get("pr_linked_issues"),
        }
        if pr_response != expected_pr_response:
            errors.append("publication blocked: freeze review fields do not derive from PR API response")
        if freeze_review.get("dev_integration_sha") != freeze.get("dev_integration_sha"):
            errors.append("publication blocked: freeze review dev integration SHA mismatch")
        if freeze_review.get("dev_contains_integration_sha") is not True:
            errors.append("publication blocked: reviewed D2 integration is not verified on dev")
        if freeze_review.get("issue") != 32:
            errors.append("publication blocked: freeze review must bind issue 32")
        if freeze_review.get("head") != repair.get("head") or freeze_review.get("base") != repair.get("base"):
            errors.append("publication blocked: freeze review branch binding mismatch")
        evidence_url = freeze_review.get("evidence_url", "")
        if re.fullmatch(
            r"https://github\.com/somebloke1/noetic-dev/(?:issues/32|pull/[1-9][0-9]*)#issuecomment-[1-9][0-9]*",
            evidence_url,
        ) is None:
            errors.append("publication blocked: freeze review evidence URL is invalid")
        if evidence_url != freeze.get("review_evidence_url"):
            errors.append("publication blocked: freeze review evidence URL mismatch")
        reviewed_at = _parse_time(freeze_review.get("reviewed_at", ""))
        captured_at = _parse_time(freeze.get("captured_at", ""))
        local_reviewed_at = _parse_time(freeze.get("reviewed_at", ""))
        fetched_at = _parse_time(pr_api.get("fetched_at", ""))
        if reviewed_at is None or reviewed_at != local_reviewed_at:
            errors.append("publication blocked: freeze review timestamp mismatch")
        if reviewed_at is None or captured_at is None or reviewed_at <= captured_at:
            errors.append("publication blocked: freeze review timestamp must follow audit capture")
        if fetched_at is None or reviewed_at is None or fetched_at > reviewed_at:
            errors.append("publication blocked: freeze review PR API capture postdates review")
    if (
        freeze.get("status") != "complete"
        or freeze.get("independent_review_completed") is not True
        or not _is_sha(freeze.get("reviewed_candidate_sha", ""))
        or not _is_sha(freeze.get("dev_integration_sha", ""))
        or not isinstance(freeze.get("reviewed_pull_request"), int)
        or freeze.get("blocks_publication") is True
    ):
        errors.append("publication blocked: existing-work freeze/audit is still active")


def check_delivery(
    manifest: Dict[str, Any],
    manifest_path: Optional[str] = None,
    *,
    phase: str = "pre-merge",
    external_evidence: Optional[Dict[str, Any]] = None,
    gate_mode: str = "main-promotion",
) -> Tuple[bool, List[str], str]:
    """Run fail-closed delivery checks.

    ``phase='pre-merge'`` checks merge readiness only. ``phase='publication'``
    additionally requires protected post-merge evidence bound to the main SHA.
    """
    if gate_mode not in {"dev-integration", "main-promotion"}:
        return False, [f"unsupported delivery gate mode: {gate_mode}"], gate_mode
    target_branch = "dev" if gate_mode == "dev-integration" else "main"
    if phase == "publication" and target_branch != "main":
        return False, ["publication phase requires main-promotion gate mode"], "publication"

    merge_errors: List[str] = []
    from check_evidence_manifest import check as validate_manifest  # noqa: WPS433

    merge_errors.extend(
        validate_manifest(
            manifest,
            manifest_path or "<manifest>",
            target_branch=target_branch,
        )
    )

    # Publication SHA format is safety-critical; surface it even when merge is also blocked.
    publication_sha = manifest.get("publication", {}).get("publication_sha", "")
    if publication_sha and not _is_sha(publication_sha):
        merge_errors.append(f"branch-name publication forbidden: {publication_sha}")

    _check_pr_and_issue(manifest, merge_errors, target_branch)
    if gate_mode == "main-promotion":
        _check_owner_promotion_authorization(manifest, merge_errors, external_evidence)
    _check_required_commands(manifest, merge_errors)
    _check_qa_pairing(manifest, merge_errors, manifest_path)
    _check_terminal_state(manifest, merge_errors, phase, target_branch)
    merge_errors.extend(
        verify_authoritative_provenance(
            manifest,
            external_evidence,
            target_branch=target_branch,
        )
    )
    _check_approvals(manifest, merge_errors, external_evidence)

    if phase == "pre-merge":
        if merge_errors:
            return False, merge_errors, gate_mode
        return True, [], gate_mode

    publication_errors: List[str] = []
    if merge_errors:
        publication_errors.append("publication blocked: merge readiness gate did not pass")
        publication_errors.extend(merge_errors)
    _check_publication(manifest, publication_errors, external_evidence)
    if publication_errors:
        return False, publication_errors, "publication"

    return True, [], "publication"


def check_bootstrap_blocked() -> Tuple[bool, List[str]]:
    """Return success only while bootstrap advisory mode remains honestly blocked."""
    errors: List[str] = []
    freeze = _protected_freeze()
    if freeze.get("status") != "repair_authorized" or freeze.get("audit_completed") is not True:
        errors.append("existing-work portfolio inventory is not in repair-authorized state")
    if freeze.get("independent_review_completed") is not False:
        errors.append("repair-authorized inventory must remain review-pending")
    if freeze.get("blocks_publication") is not True:
        errors.append("review-pending inventory must continue to block publication")
    bootstrap_path = REPO_ROOT / "governance" / "bootstrap-status.json"
    if not bootstrap_path.exists():
        errors.append("governance/bootstrap-status.json missing")
    else:
        bootstrap = load_json_strict(bootstrap_path)
        gate = bootstrap.get("authoritative_delivery_gate", {})
        if gate.get("status") != "external_dependency_missing":
            errors.append("authoritative delivery gate dependency is not marked unresolved")
        expected = {
            "protected_policy_ref_established": False,
            "trusted_runner_provenance_established": False,
            "branch_protection_requires_governance": True,
            "independent_agent_review_process_established": True,
            "credential_broker_established": False,
        }
        for field in BOOTSTRAP_AUTHORITY_FIELDS:
            if gate.get(field) is not expected[field]:
                errors.append(
                    f"bootstrap dependency state mismatch for {field}: "
                    f"expected {expected[field]}"
                )
    return not errors, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Noetic-dev delivery gate")
    parser.add_argument("path", nargs="?", help="Path to manifest.json, workflow.yml, or workflow directory")
    parser.add_argument("--check-pinning-only", action="store_true", help="Only check workflow action pinning")
    parser.add_argument("--check-bootstrap-blocked", action="store_true", help="Assert bootstrap advisory mode remains honestly blocked")
    parser.add_argument("--external-evidence", help="Protected external GitHub/approval/freeze evidence JSON")
    parser.add_argument("--phase", choices=["pre-merge", "publication"], default="pre-merge")
    parser.add_argument("--gate-mode", choices=["dev-integration", "main-promotion"], default="main-promotion")
    args = parser.parse_args()

    if args.check_bootstrap_blocked:
        passed, errors = check_bootstrap_blocked()
        if not passed:
            print("Bootstrap blocked check FAILED:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 1
        print("Bootstrap advisory mode confirmed: merge/publication authority remains BLOCKED", file=sys.stderr)
        return 0

    if args.check_pinning_only:
        if not args.path:
            print("Usage: check_delivery_gate.py --check-pinning-only <workflow.yml|workflow-dir>", file=sys.stderr)
            return 2
        errors = check_pinning(args.path)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print(f"Workflow pinning check PASSED: {args.path}", file=sys.stderr)
        return 0

    if not args.path:
        print("Usage: check_delivery_gate.py <manifest.json>", file=sys.stderr)
        return 2

    try:
        manifest = load_json(args.path)
    except (FileNotFoundError, json.JSONDecodeError, DuplicateKeyError, ValueError) as exc:
        print(f"Error reading manifest: {exc}", file=sys.stderr)
        return 1

    from check_evidence_manifest import check as validate_manifest  # noqa: WPS433

    target_branch = "dev" if args.gate_mode == "dev-integration" else "main"
    manifest_errors = validate_manifest(manifest, args.path, target_branch=target_branch)
    if manifest_errors:
        print("Manifest validation failed:", file=sys.stderr)
        for error in manifest_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    external_evidence = None
    if args.external_evidence:
        try:
            external_evidence = load_json(args.external_evidence)
        except (FileNotFoundError, json.JSONDecodeError, DuplicateKeyError, ValueError) as exc:
            print(f"Error reading external evidence: {exc}", file=sys.stderr)
            return 1

    passed, errors, gate_type = check_delivery(
        manifest,
        args.path,
        phase=args.phase,
        external_evidence=external_evidence,
        gate_mode=args.gate_mode,
    )
    if not passed:
        print(f"Delivery gate FAILED ({gate_type}):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"Delivery gate PASSED ({gate_type}, phase={args.phase})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
