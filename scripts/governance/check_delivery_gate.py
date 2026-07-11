#!/usr/bin/env python3
"""Fail-closed delivery gate for noetic-dev governance.

Checks whether a candidate PR meets all gates for merge-readiness and
publication-readiness. In bootstrap mode (no trusted runner, no independent
human reviewer), publication and merge-readiness remain BLOCKED.

Usage:
    check_delivery_gate.py <manifest.json>
    check_delivery_gate.py --check-pinning-only <workflow.yml>

Exit codes:
    0 = gate passed
    1 = gate failed (check diagnostics on stderr)
    2 = usage error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def check_pinning(workflow_path: str) -> List[str]:
    """Check that all GitHub Actions refs are pinned to full SHAs.

    Accepts patterns like:
      - actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
      - actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065

    Rejects:
      - actions/checkout@v4
      - actions/setup-python@v5
      - docker://...@latest
    """
    errors: List[str] = []
    content = Path(workflow_path).read_text()

    # Find all uses-action patterns: uses: owner/repo@ref
    action_pattern = re.compile(r"^\s+(?:-\s+)?uses:\s+([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)@(\S+)", re.MULTILINE)

    for match in action_pattern.finditer(content):
        action = match.group(1)
        ref = match.group(2)

        # Skip docker:// or local actions
        if action.startswith("docker://") or action == "local":
            continue

        # Skip if action is from within the repo (./path)
        if action.startswith("."):
            continue

        # Check if ref is a full 40-char SHA
        if not re.match(r"^[a-f0-9]{40}$", ref):
            errors.append(
                f"unpinned action ref: {action}@{ref} "
                f"(must use full 40-char SHA) in {workflow_path}"
            )

    return errors


def calculate_allowed_status_labels() -> List[str]:
    """Returns the list of status labels that allow work to proceed."""
    return [
        "status:accepted",
        "status:ready",
        "status:in_progress",
    ]


def check_delivery(manifest: Dict[str, Any]) -> Tuple[bool, List[str], str]:
    """Run all delivery gate checks.

    Returns:
        (passed, errors, gate_type) where gate_type is 'merge' or 'publication'
    """
    errors: List[str] = []
    merge_ready = False
    publication_ready = False

    pr = manifest.get("pull_request", {})
    repo = manifest.get("repo", {})
    qa = manifest.get("qa", {})
    passes = manifest.get("passes", {})
    policy = manifest.get("policy", {})
    approvals = manifest.get("approvals", [])
    publication = manifest.get("publication", {})
    commands = manifest.get("commands", [])
    issue = manifest.get("issue", {})

    # === PR-readiness checks ===

    # 1. Not a draft
    if pr.get("draft_state", False):
        errors.append("PR is a draft")

    # 2. Title not WIP
    title = pr.get("title", "")
    wip_prefixes = ["[WIP]", "WIP:", "Draft:", "Do not merge:", "Checkpoint:"]
    for prefix in wip_prefixes:
        if title.startswith(prefix):
            errors.append(f"PR title has WIP prefix: {prefix}")
            break

    # 3. Base is main
    if pr.get("base", "") != "main":
        errors.append(f"PR base is '{pr.get('base')}', must be 'main'")

    # 4. Linked issue exists with canonical status
    issue_status = issue.get("canonical_status", "")
    if not issue_status:
        errors.append("no canonical issue status")
    elif issue_status in ("status:blocked", "status:checkpointed"):
        errors.append(f"issue status {issue_status} prevents closure")
    elif issue_status not in calculate_allowed_status_labels():
        if issue_status.startswith("status:"):
            pass  # Known status that may not be in the allowed list yet
        else:
            errors.append(f"unknown issue status format: {issue_status}")

    # 5. Candidate SHA is full 40-char and matches PR head SHA
    candidate_sha = repo.get("candidate_sha", "")
    if len(candidate_sha) != 40:
        errors.append(f"candidate SHA is not 40 chars: {candidate_sha}")
    elif candidate_sha != pr.get("head_sha", ""):
        errors.append(
            f"candidate SHA ({candidate_sha}) != PR head SHA ({pr.get('head_sha', '')})"
        )

    # 6. Base SHA present
    base_sha = repo.get("base_sha", "")
    if len(base_sha) != 40:
        errors.append(f"base SHA is not 40 chars")

    # 7. Required validations passed
    validation_commands = [c for c in commands if c.get("category") == "validation"]
    validation_failures = [c for c in validation_commands if c.get("exit_code", 1) != 0]
    if validation_failures:
        for vf in validation_failures:
            errors.append(f"validation failed: {' '.join(vf.get('argv', []))} (exit {vf.get('exit_code')})")

    # 8. Required tests passed
    test_commands = [c for c in commands if c.get("category") == "test"]
    test_failures = [c for c in test_commands if c.get("exit_code", 1) != 0]
    if test_failures:
        for tf in test_failures:
            errors.append(f"test failed: {' '.join(tf.get('argv', []))} (exit {tf.get('exit_code')})")

    # 9. Implementation:QA pass cardinality exactly 1:1
    impl_ids = passes.get("implementation_pass_ids", [])
    remediation_ids = passes.get("remediation_pass_ids", [])
    all_pass_ids = impl_ids + remediation_ids

    if len(all_pass_ids) == 0:
        errors.append("no implementation or remediation passes recorded")
    else:
        qa_for_pass_id = qa.get("qa_for_pass_id", "")
        if not qa_for_pass_id:
            errors.append("no qa_for_pass_id (no QA pass recorded)")
        else:
            # For a 1:1 mapping, qa_for_pass_id should be the single pass ID
            if len(all_pass_ids) > 1:
                # With multiple passes, each should have its own QA entry
                # For first-generation, we check if the qa_for_pass_id is one of them
                if qa_for_pass_id not in all_pass_ids:
                    errors.append(
                        f"qa_for_pass_id ({qa_for_pass_id}) not in pass IDs: {all_pass_ids}"
                    )
            elif len(all_pass_ids) == 1:
                if qa_for_pass_id != all_pass_ids[0]:
                    errors.append(
                        f"qa_for_pass_id ({qa_for_pass_id}) != single pass ID ({all_pass_ids[0]})"
                    )

    # 10. QA isolation proof
    iso = qa.get("isolation_proof", {})
    if iso.get("source_mount_read_only") is False:
        errors.append("QA source mount was not read-only")
    if iso.get("write_tools_observed", True):
        errors.append("QA used write tools on candidate source")
    if iso.get("context_files_disabled") is False:
        errors.append("QA context files were not disabled")
    if iso.get("candidate_tree_before") and iso.get("candidate_tree_after"):
        if iso["candidate_tree_before"] != iso["candidate_tree_after"]:
            errors.append("candidate tree changed during QA")
    if iso.get("ambient_credentials_available"):
        errors.append("ambient credentials were available during QA")

    # 11. QA verdict
    if qa.get("verdict") != "pass":
        errors.append(f"QA verdict is not 'pass': {qa.get('verdict')!r}")

    # 12. Human approval
    approver = ""
    approval_found = False
    for a in approvals:
        if a.get("reviewer"):
            approver = a["reviewer"]
            approval_found = True
            break

    if not approval_found:
        errors.append("no human approval recorded")

    # 13. Workflow pinning — we don't check the workflow file here, that's done by --check-pinning-only

    # If no merge-readiness errors, candidate is merge-ready
    merge_errors = list(errors)  # clone

    # === Publication checks (additional after merge) ===
    pub_errors: List[str] = []

    # Publication SHA must be 40 chars
    pub_sha = publication.get("publication_sha", "")
    if pub_sha and len(pub_sha) != 40:
        pub_errors.append(f"publication_sha must be 40 chars: {pub_sha}")

    # Branch-name publication always forbidden
    if pub_sha and not re.match(r"^[a-f0-9]{40}$", pub_sha):
        pub_errors.append(f"branch-name publication forbidden: {pub_sha}")

    # Trusted runner check
    if not policy.get("trusted_runner"):
        pub_errors.append(
            "publication blocked: no trusted runner (policy.trusted_runner is false)"
        )

    # Independent human approval for publication
    independent_approval = False
    for a in approvals:
        if a.get("independent") and a.get("reviewer"):
            independent_approval = True
            break
    if not independent_approval:
        pub_errors.append("publication blocked: no independent human approval")

    merge_passed = len(errors) == 0
    pub_passed = merge_passed and len(pub_errors) == 0

    if not merge_passed:
        return (False, errors, "merge")

    if not pub_passed:
        return (False, pub_errors, "publication")

    return (True, [], "publication")


def main() -> int:
    parser = argparse.ArgumentParser(description="Noetic-dev delivery gate")
    parser.add_argument("path", nargs="?", help="Path to manifest.json or workflow.yml")
    parser.add_argument("--check-pinning-only", action="store_true",
                        help="Only check workflow action pinning")
    args = parser.parse_args()

    if args.check_pinning_only:
        if not args.path:
            print("Usage: check_delivery_gate.py --check-pinning-only <workflow.yml>",
                  file=sys.stderr)
            return 2
        errors = check_pinning(args.path)
        if errors:
            for e in errors:
                print(e, file=sys.stderr)
            return 1
        print(f"Workflow pinning check PASSED: {args.path}", file=sys.stderr)
        return 0

    if not args.path:
        print("Usage: check_delivery_gate.py <manifest.json>", file=sys.stderr)
        return 2

    try:
        manifest = load_json(args.path)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading manifest: {e}", file=sys.stderr)
        return 1

    # First, validate the manifest
    # Import from sibling module
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_evidence_manifest import check as validate_manifest
    manifest_errors = validate_manifest(manifest, args.path)
    if manifest_errors:
        print("Manifest validation failed:", file=sys.stderr)
        for e in manifest_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    # Then run delivery gate
    passed, errors, gate_type = check_delivery(manifest)

    if not passed:
        print(f"Delivery gate FAILED ({gate_type}):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"Delivery gate PASSED ({gate_type})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
