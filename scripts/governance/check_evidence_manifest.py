#!/usr/bin/env python3
"""Validate an evidence manifest against its schema and invariant rules.

Usage:
    check_evidence_manifest.py <manifest.json>

Returns exit code 0 if valid, 1 if invalid.
Outputs diagnostics to stderr.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Keep scripts directory in path for sibling imports
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
# Direct import from sibling module
from hash_tree import (  # noqa: E402
    canonical_json,
    canonical_json_sha256,
    manifest_digest_excluding_own,
    validate_sha_hex,
    validate_sha256_hex,
)


def check(manifest: Dict[str, Any], path: str = "<manifest>") -> List[str]:
    """Run all validation checks. Returns list of error messages."""
    errors: List[str] = []

    # Schema version
    if manifest.get("schema_version") != "1":
        errors.append(f"schema_version must be '1', got {manifest.get('schema_version')!r}")

    # Required top-level fields
    required_fields = [
        "schema_version", "manifest_id", "run_id", "generated_at",
        "policy", "repo", "issue", "pull_request", "passes", "qa",
        "commands", "validations", "tests", "state_transitions",
        "approvals", "publication",
    ]
    for field in required_fields:
        if field not in manifest:
            errors.append(f"missing required field: {field}")

    if errors:
        return errors

    # Policy checks
    policy = manifest["policy"]
    if not policy.get("sha", "").startswith("0000000"):
        try:
            validate_sha_hex(policy.get("sha", ""), 40, "policy.sha")
        except ValueError as e:
            errors.append(str(e))

    if not isinstance(policy.get("trusted_runner"), bool):
        errors.append("policy.trusted_runner must be a boolean")

    generator_sha = policy.get("generator_sha256", "")
    try:
        validate_sha256_hex(generator_sha, "policy.generator_sha256")
    except ValueError as e:
        errors.append(str(e))

    # If trusted_runner, verify self-referencing hash
    if policy.get("trusted_runner"):
        try:
            computed_digest = manifest_digest_excluding_own(manifest)
            recorded = policy.get("runner_attestation", {}).get("artifact", {}).get("manifest_sha256", "")
            if not recorded:
                errors.append("trusted_runner=true but no manifest_sha256 in policy.runner_attestation.artifact")
            elif computed_digest != recorded:
                errors.append(
                    f"manifest digest mismatch (excluding own field): "
                    f"computed={computed_digest}, recorded={recorded}"
                )
        except Exception as e:
            errors.append(f"error computing manifest digest: {e}")

    # Repo checks
    repo = manifest["repo"]
    for sha_field in ["base_sha", "candidate_sha", "candidate_tree_oid"]:
        val = repo.get(sha_field, "")
        try:
            validate_sha_hex(val, 40, f"repo.{sha_field}")
        except ValueError as e:
            errors.append(str(e))

    # SHA lengths
    for field in ["base_sha", "candidate_sha"]:
        val = repo.get(field, "")
        if len(val) != 40:
            errors.append(f"repo.{field} must be 40 characters, got {len(val)}")

    # PR checks
    pr = manifest["pull_request"]
    pr_head_sha = pr.get("head_sha", "")
    if pr_head_sha and pr_head_sha != repo.get("candidate_sha", ""):
        errors.append(
            f"pull_request.head_sha ({pr_head_sha}) must equal "
            f"repo.candidate_sha ({repo.get('candidate_sha', '')})"
        )

    # Passes checks
    passes = manifest["passes"]
    impl_ids = passes.get("implementation_pass_ids", [])
    remediation_ids = passes.get("remediation_pass_ids", [])

    if not impl_ids and not remediation_ids:
        errors.append("passes must have at least one implementation or remediation pass")

    if passes.get("candidate_sha") != repo.get("candidate_sha", ""):
        errors.append(
            f"passes.candidate_sha ({passes.get('candidate_sha')}) must equal "
            f"repo.candidate_sha ({repo.get('candidate_sha', '')})"
        )

    # QA checks
    qa = manifest["qa"]
    if qa.get("qa_for_pass_id"):
        # If qa_for_pass_id is set, check that it matches one of the pass IDs
        all_pass_ids = impl_ids + remediation_ids
        # The qa_for_pass_id might be a single value or pattern
        # For first generation, it should match the only implementation pass
        if qa["qa_for_pass_id"] not in all_pass_ids and len(all_pass_ids) > 0:
            errors.append(
                f"qa.qa_for_pass_id ({qa['qa_for_pass_id']}) not found in "
                f"pass IDs: {all_pass_ids}"
            )

    if qa.get("verdict") and qa["verdict"] not in ("pass", "fail"):
        errors.append(f"qa.verdict must be 'pass' or 'fail', got {qa['verdict']!r}")

    # Hash format checks for QA
    for hash_field in ["report_hash", "event_log_hash"]:
        val = qa.get(hash_field, "")
        if val:
            try:
                validate_sha256_hex(val, f"qa.{hash_field}")
            except ValueError as e:
                errors.append(str(e))

    # Isolation proof checks
    iso = qa.get("isolation_proof", {})
    if iso:
        if not iso.get("source_mount_read_only", True):
            errors.append("isolation_proof.source_mount_read_only must be True")
        if iso.get("write_tools_observed", False):
            errors.append("isolation_proof.write_tools_observed must be False for valid QA")

        for tree_field in ["candidate_tree_before", "candidate_tree_after"]:
            val = iso.get(tree_field, "")
            if val:
                try:
                    validate_sha_hex(val, 40, f"isolation_proof.{tree_field}")
                except ValueError as e:
                    errors.append(str(e))

        if iso.get("candidate_tree_before") and iso.get("candidate_tree_after"):
            if iso["candidate_tree_before"] != iso["candidate_tree_after"]:
                errors.append(
                    f"candidate tree changed during QA: "
                    f"{iso['candidate_tree_before']} -> {iso['candidate_tree_after']}"
                )

    # Commands checks — validate_repo.py must not be categorized as test
    for cmd in manifest.get("commands", []):
        if "scripts/validate_repo.py" in " ".join(cmd.get("argv", [])):
            if cmd.get("category") == "test":
                errors.append(
                    f"command {cmd.get('command_id')}: validate_repo.py cannot be categorized as test"
                )

    # State transitions
    for st in manifest.get("state_transitions", []):
        if not st.get("from") or not st.get("to"):
            errors.append(f"state_transition missing 'from' or 'to': {st}")
        if not st.get("authority"):
            errors.append(f"state_transition missing 'authority': {st}")

    # Publication checks
    pub = manifest.get("publication", {})
    if pub.get("publication_sha") and len(pub["publication_sha"]) != 40:
        errors.append(f"publication.publication_sha must be 40 chars, got {len(pub['publication_sha'])}")

    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: check_evidence_manifest.py <manifest.json>", file=sys.stderr)
        return 1

    manifest_path = sys.argv[1]
    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading manifest: {e}", file=sys.stderr)
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
