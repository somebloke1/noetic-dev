#!/usr/bin/env python3
"""Fail-closed delivery gate for noetic-dev governance.

The gate distinguishes repository validation from genuine tests and refuses to
promote advisory/local evidence to merge or publication readiness. It can verify
captured GitHub API/artifact-attestation payloads supplied in the manifest; it
never treats a manifest-controlled boolean as authoritative provenance.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

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
from hash_tree import canonical_json_sha256, sha256_file, validate_sha_hex  # noqa: E402
from json_schema import DuplicateKeyError, load_json_strict  # noqa: E402

SHA1_RE = re.compile(r"^[a-f0-9]{40}$")
PINNED_ACTION_RE = re.compile(r"^[a-f0-9]{40}$")
WIP_PREFIXES = ("[WIP]", "WIP:", "Draft:", "Do not merge:", "Checkpoint:")
REPO_FULL_NAME = "somebloke1/noetic-dev"


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


def _parse_time(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA1_RE.fullmatch(value))


def _truth(value: Any) -> bool:
    return value is True


def check_pinning(workflow_path: str) -> List[str]:
    """Check that all remote GitHub Action refs are pinned to full SHAs."""
    errors: List[str] = []
    content = Path(workflow_path).read_text(encoding="utf-8")
    action_pattern = re.compile(
        r"^\s+(?:-\s+)?uses:\s+([^\s#]+)",
        re.MULTILINE,
    )

    for match in action_pattern.finditer(content):
        uses = match.group(1).strip().strip('"\'')
        if uses.startswith("./") or uses.startswith("docker://"):
            continue
        if "@" not in uses:
            errors.append(f"unpinned action ref: {uses} (missing @<sha>) in {workflow_path}")
            continue
        action, ref = uses.rsplit("@", 1)
        if action.startswith("./") or action.startswith("docker://"):
            continue
        if not PINNED_ACTION_RE.fullmatch(ref):
            errors.append(
                f"unpinned action ref: {action}@{ref} "
                f"(must use full 40-char SHA) in {workflow_path}"
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


def _successful_registered_command_ids(manifest: Dict[str, Any], phase: str) -> set[str]:
    registry = _command_registry()
    result: set[str] = set()
    for command in manifest.get("commands", []):
        registry_id = command_registry_id(command)
        if registry_id not in registry.get("commands", {}):
            continue
        spec = registry["commands"][registry_id]
        if spec.get("phase", "pre_merge") != phase:
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


def _check_pr_and_issue(manifest: Dict[str, Any], errors: List[str]) -> None:
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
    if pr.get("base") != "main" or repo.get("base_branch") != "main":
        errors.append("stacked PR/base branch rejected: PR base and repo.base_branch must both be main")
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


def _profile_for(profile_id: str) -> Optional[Dict[str, Any]]:
    return _model_profiles().get("profiles", {}).get(profile_id)


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
    manifest: Dict[str, Any],
    errors: List[str],
) -> None:
    repo = manifest.get("repo", {})
    policy = manifest.get("policy", {})
    actual = _actual(exec_record)
    iso = actual.get("isolation", {})
    qa_run_id = qa_record.get("qa_run_id", "<unknown>")

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

    if actual.get("candidate_sha") != repo.get("candidate_sha"):
        errors.append(f"qa {qa_run_id} execution candidate_sha mismatch")
    if actual.get("base_sha") != repo.get("base_sha"):
        errors.append(f"qa {qa_run_id} execution base_sha mismatch")
    if actual.get("candidate_tree_oid") != repo.get("candidate_tree_oid"):
        errors.append(f"qa {qa_run_id} execution candidate_tree_oid mismatch")

    if not _same_list(actual.get("tools"), probe_record.get("tools")):
        errors.append(f"qa {qa_run_id} probe/execution tools mismatch")
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

    for pass_id in pass_ids:
        pass_record = records_by_pass.get(pass_id)
        if not pass_record:
            errors.append(f"missing pass record for {pass_id}")
            continue
        if pass_record.get("candidate_sha") != repo.get("candidate_sha"):
            errors.append(f"pass {pass_id} stale candidate SHA")
        if pass_record.get("base_sha") != repo.get("base_sha"):
            errors.append(f"pass {pass_id} stale base SHA")
        if pass_record.get("candidate_tree_oid") != repo.get("candidate_tree_oid"):
            errors.append(f"pass {pass_id} stale candidate tree")

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
            expected = repo.get(field)
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
        if iso.get("candidate_tree_before") != repo.get("candidate_tree_oid") or iso.get("candidate_tree_after") != repo.get("candidate_tree_oid"):
            errors.append(f"QA {qa_run_id} candidate tree before/after must equal repo.candidate_tree_oid")

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

        _check_probe_execution_binding(qa_record, exec_record, probe_record, manifest, errors)


def verify_authoritative_provenance(manifest: Dict[str, Any]) -> List[str]:
    """Verify captured external provenance bindings for authoritative mode."""
    errors: List[str] = []
    policy = manifest.get("policy", {})
    repo = manifest.get("repo", {})
    pr = manifest.get("pull_request", {})
    attestation = policy.get("runner_attestation", {})

    if policy.get("trusted_runner") is not True:
        return ["merge readiness blocked: no authoritative trusted runner provenance"]
    if not isinstance(attestation, dict) or not attestation:
        return ["trusted runner provenance missing; local trusted_runner boolean is insufficient"]
    mode = attestation.get("mode")
    if mode not in {"github_api", "github_artifact_attestation"}:
        errors.append("trusted runner provenance must be verified by GitHub API or artifact attestation")
    if attestation.get("verification_status") != "verified":
        errors.append("trusted runner provenance verification_status is not verified")

    artifact = attestation.get("artifact", {})
    artifact_digest = artifact.get("artifact_digest") or artifact.get("digest")
    if not artifact.get("artifact_id"):
        errors.append("trusted runner artifact_id missing")
    if not artifact_digest or not re.fullmatch(r"sha256:[a-f0-9]{64}", artifact_digest):
        errors.append("trusted runner artifact digest missing or invalid")
    if not artifact.get("manifest_sha256"):
        errors.append("trusted runner canonical manifest digest missing")
    else:
        from hash_tree import manifest_digest_excluding_own  # local import avoids CLI cycle surprises

        computed_manifest_digest = manifest_digest_excluding_own(manifest)
        if artifact.get("manifest_sha256") != computed_manifest_digest:
            errors.append(
                "trusted runner canonical manifest digest mismatch: "
                f"computed={computed_manifest_digest}, recorded={artifact.get('manifest_sha256')}"
            )

    github = attestation.get("github", {})
    if not github:
        if mode == "github_artifact_attestation":
            signed = attestation.get("signed_attestation", {})
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
                ("event", "pull_request"),
            ]:
                if claims.get(label) != expected:
                    errors.append(f"artifact attestation claim mismatch: {label}")
            if not claims.get("run_id") or not claims.get("job_id"):
                errors.append("artifact attestation run_id/job_id claims missing")
            if claims.get("base_ref") != "main":
                errors.append("artifact attestation base_ref must be main")
            if claims.get("policy_ref") != policy.get("ref"):
                errors.append("artifact attestation policy_ref mismatch")
            if claims.get("policy_sha") != policy.get("sha"):
                errors.append("artifact attestation policy_sha mismatch")
            if claims.get("policy_protected") is not True:
                errors.append("artifact attestation policy ref is not protected")
            if claims.get("candidate_sha") != repo.get("candidate_sha"):
                errors.append("artifact attestation candidate_sha mismatch")
            if claims.get("policy_checkout_path") == claims.get("candidate_checkout_path"):
                errors.append("candidate checkout reused as policy checkout")
            if claims.get("generator_from_policy_checkout") is not True:
                errors.append("manifest was generated by candidate-modifiable code")
            external_file_hashes = attestation.get("policy_file_hashes", {})
            if not external_file_hashes:
                errors.append("protected policy file hashes missing from artifact attestation")
            if external_file_hashes.get(policy.get("generator_path")) != policy.get("generator_sha256"):
                errors.append("policy generator_sha256 does not match artifact-attested policy hash")
            return errors
        errors.append("trusted runner GitHub provenance payload missing")
        return errors

    repository = github.get("repository", {})
    if repository.get("full_name") != REPO_FULL_NAME:
        errors.append(f"GitHub provenance repository mismatch: {repository.get('full_name')}")
    if repo.get("repository") and repository.get("full_name") != repo.get("repository"):
        errors.append("GitHub provenance repository does not match manifest repo.repository")
    if repo.get("repository_id") and repository.get("id") != repo.get("repository_id"):
        errors.append("GitHub provenance repository_id mismatch")

    workflow = github.get("workflow", {})
    if workflow.get("path") not in {".github/workflows/governance.yml", "governance.yml"}:
        errors.append("GitHub provenance workflow path mismatch")
    if workflow.get("sha") != policy.get("sha"):
        errors.append("GitHub provenance workflow SHA must equal protected policy SHA")
    if workflow.get("ref") != policy.get("ref"):
        errors.append("GitHub provenance workflow ref must equal policy.ref")

    run = github.get("run", {})
    if run.get("event") != "pull_request":
        errors.append("GitHub provenance event must be pull_request")
    if run.get("head_sha") != repo.get("candidate_sha"):
        errors.append("GitHub provenance run head_sha does not match candidate SHA")
    if run.get("base_branch") != "main":
        errors.append("GitHub provenance base branch must be main")
    if run.get("conclusion") != "success":
        errors.append("GitHub provenance run conclusion must be success")
    if not run.get("id") or not run.get("attempt"):
        errors.append("GitHub provenance run id/attempt missing")

    job = github.get("job", {})
    if job.get("conclusion") != "success":
        errors.append("GitHub provenance job conclusion must be success")
    if not job.get("id") or not job.get("name"):
        errors.append("GitHub provenance job id/name missing")

    gh_pr = github.get("pull_request", {})
    if gh_pr.get("number") != pr.get("number"):
        errors.append("GitHub provenance PR number mismatch")
    if gh_pr.get("base_ref") != "main":
        errors.append("GitHub provenance PR base ref must be main")
    if gh_pr.get("head_ref") != repo.get("candidate_branch"):
        errors.append("GitHub provenance PR head ref mismatch")
    if gh_pr.get("head_sha") != repo.get("candidate_sha"):
        errors.append("GitHub provenance PR head SHA mismatch")

    gh_artifact = github.get("artifact", {})
    if gh_artifact.get("id") != artifact.get("artifact_id"):
        errors.append("GitHub provenance artifact id mismatch")
    if gh_artifact.get("digest") != artifact_digest:
        errors.append("GitHub provenance artifact digest mismatch")
    if gh_artifact.get("name") and artifact.get("name") and gh_artifact.get("name") != artifact.get("name"):
        errors.append("GitHub provenance artifact name mismatch")

    protected_ref = github.get("protected_ref", {})
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

    checkouts = github.get("checkouts", {})
    if checkouts.get("policy_sha") != policy.get("sha"):
        errors.append("protected policy checkout SHA mismatch")
    if checkouts.get("candidate_sha") != repo.get("candidate_sha"):
        errors.append("candidate checkout SHA mismatch")
    if checkouts.get("policy_path") == checkouts.get("candidate_path"):
        errors.append("candidate checkout reused as policy checkout")
    if checkouts.get("separate") is not True:
        errors.append("policy and candidate checkouts are not separate")

    generator = github.get("generator", {})
    if generator.get("path") != policy.get("generator_path"):
        errors.append("manifest generator path provenance mismatch")
    if generator.get("from_policy_checkout") is not True:
        errors.append("manifest was generated by candidate-modifiable code")

    policy_file_hashes = policy.get("file_hashes", {})
    external_file_hashes = github.get("policy_file_hashes", {}) or github.get("policy_files", {})
    if not external_file_hashes:
        errors.append("protected policy file hashes missing from external provenance")
    if external_file_hashes and github.get("policy_file_hashes_source") != "protected_checkout":
        errors.append("policy file hashes were not computed from protected checkout")
    if policy_file_hashes:
        for path, recorded_hash in policy_file_hashes.items():
            if external_file_hashes.get(path) != recorded_hash:
                errors.append(f"policy file hash mismatch: {path}")
    generator_path = policy.get("generator_path")
    if generator_path and external_file_hashes:
        if external_file_hashes.get(generator_path) != policy.get("generator_sha256"):
            errors.append("policy generator_sha256 does not match protected checkout hash")

    if mode == "github_artifact_attestation":
        signed = attestation.get("signed_attestation", {})
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
        ]:
            if claims.get(label) != expected:
                errors.append(f"artifact attestation claim mismatch: {label}")

    return errors


def _check_approvals(manifest: Dict[str, Any], errors: List[str]) -> None:
    pr = manifest.get("pull_request", {})
    repo = manifest.get("repo", {})
    records = pass_records_by_id(manifest)
    implementation_agents = {record.get("agent_id") for record in records.values() if record.get("agent_id")}
    qa_agents = {record.get("agent_id") for record in normalize_qa_records(manifest) if record.get("agent_id")}
    candidate_sha = repo.get("candidate_sha")
    candidate_pinned_at = _parse_time(repo.get("candidate_pinned_at", ""))
    if not candidate_pinned_at:
        errors.append("candidate_pinned_at missing or invalid; approval recency cannot be verified")

    valid = False
    for approval in manifest.get("approvals", []):
        reviewer = approval.get("reviewer", "")
        approval_time = _parse_time(approval.get("timestamp", ""))
        if not reviewer:
            errors.append("approval missing reviewer")
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
        if approval.get("independent") is not True:
            errors.append(f"approval by {reviewer} is not marked independent")
            continue
        if approval.get("state") and approval.get("state") != "APPROVED":
            errors.append(f"approval by {reviewer} state is not APPROVED")
            continue
        if reviewer == pr.get("author"):
            errors.append(f"approval by PR author is not independent: {reviewer}")
            continue
        if reviewer in implementation_agents:
            errors.append(f"approval by implementation identity is not independent: {reviewer}")
            continue
        if reviewer in qa_agents:
            errors.append(f"approval by QA identity is not independent: {reviewer}")
            continue
        valid = True

    if not valid:
        errors.append("no independent current-SHA human approval recorded")


def _check_publication(manifest: Dict[str, Any], errors: List[str]) -> None:
    publication = manifest.get("publication", {})
    registry = _command_registry()
    successful_post = _successful_registered_command_ids(manifest, "post_merge")

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

    for required in registry.get("rules", {}).get("required_post_merge_validations", []):
        if required not in successful_post:
            errors.append(f"publication blocked: required post-merge validation missing or failed: {required}")
    for required in registry.get("rules", {}).get("required_post_merge_tests", []):
        if required not in successful_post:
            errors.append(f"publication blocked: required post-merge test missing or failed: {required}")

    audit = manifest.get("audit", {}).get("existing_work_freeze", {})
    if audit.get("status") == "active" or audit.get("blocks_publication") is True:
        errors.append("publication blocked: existing-work freeze/audit is still active")


def check_delivery(manifest: Dict[str, Any], manifest_path: Optional[str] = None) -> Tuple[bool, List[str], str]:
    """Run fail-closed delivery checks.

    Returns ``(passed, errors, gate_type)``. ``gate_type`` is the first blocked
    gate: ``merge`` or ``publication``.
    """
    merge_errors: List[str] = []

    # Publication SHA format is safety-critical; surface it even when merge is also blocked.
    publication_sha = manifest.get("publication", {}).get("publication_sha", "")
    if publication_sha and not _is_sha(publication_sha):
        merge_errors.append(f"branch-name publication forbidden: {publication_sha}")

    _check_pr_and_issue(manifest, merge_errors)
    _check_required_commands(manifest, merge_errors)
    _check_qa_pairing(manifest, merge_errors, manifest_path)
    merge_errors.extend(verify_authoritative_provenance(manifest))
    _check_approvals(manifest, merge_errors)

    if merge_errors:
        return False, merge_errors, "merge"

    publication_errors: List[str] = []
    _check_publication(manifest, publication_errors)
    # Human approval and provenance are rechecked by merge gate; if code changes later,
    # this remains explicit for publication safety.
    publication_errors.extend(verify_authoritative_provenance(manifest))
    if publication_errors:
        return False, publication_errors, "publication"

    return True, [], "publication"


def main() -> int:
    parser = argparse.ArgumentParser(description="Noetic-dev delivery gate")
    parser.add_argument("path", nargs="?", help="Path to manifest.json or workflow.yml")
    parser.add_argument("--check-pinning-only", action="store_true", help="Only check workflow action pinning")
    args = parser.parse_args()

    if args.check_pinning_only:
        if not args.path:
            print("Usage: check_delivery_gate.py --check-pinning-only <workflow.yml>", file=sys.stderr)
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

    manifest_errors = validate_manifest(manifest, args.path)
    if manifest_errors:
        print("Manifest validation failed:", file=sys.stderr)
        for error in manifest_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    passed, errors, gate_type = check_delivery(manifest, args.path)
    if not passed:
        print(f"Delivery gate FAILED ({gate_type}):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"Delivery gate PASSED ({gate_type})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
