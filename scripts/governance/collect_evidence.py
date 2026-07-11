#!/usr/bin/env python3
"""Collect evidence for a governance run and produce an evidence manifest.

This script is part of the protected policy code. It generates the evidence
manifest at .governance/runs/<run_id>/manifest.json.

Usage:
    collect_evidence.py --run-id <uuid> --candidate-sha <sha> --base-sha <sha> [options]

Output:
    Writes manifest to stdout or to --output <path>.
    The manifest is advisory unless trusted_runner is true and provenance is
    externally verified by the delivery gate.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add sibling directory to path for hash_tree imports
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from hash_tree import (  # noqa: E402
    canonical_json_sha256,
    manifest_digest_excluding_own,
    sha256_file,
    sha256_text,
)


def get_git_sha(ref: str) -> str:
    """Get full 40-character SHA for a git ref."""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        capture_output=True, text=True, cwd=REPO_ROOT
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to resolve git ref {ref}: {result.stderr.strip()}")
    return result.stdout.strip()


def get_git_tree_oid(sha: str) -> str:
    """Get tree OID for a commit SHA."""
    result = subprocess.run(
        ["git", "rev-parse", f"{sha}^{{tree}}"],
        capture_output=True, text=True, cwd=REPO_ROOT
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get tree OID for {sha}: {result.stderr.strip()}")
    return result.stdout.strip()


def run_command(argv: List[str], cwd: Optional[str] = None) -> Dict[str, Any]:
    """Run a command and capture output with hashes."""
    start = datetime.now(timezone.utc)
    result = subprocess.run(
        argv,
        capture_output=True, text=True,
        cwd=cwd or REPO_ROOT
    )
    finish = datetime.now(timezone.utc)
    return {
        "command_id": f"cmd-{uuid.uuid4().hex[:12]}",
        "category": "validation",
        "argv": argv,
        "cwd": cwd or str(REPO_ROOT),
        "exit_code": result.returncode,
        "stdout_sha256": sha256_text(result.stdout) if result.stdout else sha256_text(""),
        "stderr_sha256": sha256_text(result.stderr) if result.stderr else sha256_text(""),
        "started_at": start.isoformat(),
        "finished_at": finish.isoformat(),
    }


REPO_ROOT = Path(__file__).resolve().parents[2]


def collect(args: argparse.Namespace) -> Dict[str, Any]:
    """Collect evidence and produce a manifest dict."""
    run_id = args.run_id
    candidate_sha = args.candidate_sha
    base_sha = args.base_sha or get_git_sha("main")

    # Resolve repo info
    remote_result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True, text=True, cwd=REPO_ROOT
    )
    remote = remote_result.stdout.strip() if remote_result.returncode == 0 else "unknown"

    candidate_branch = args.candidate_branch or ""
    try:
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        if branch_result.returncode == 0:
            candidate_branch = candidate_branch or branch_result.stdout.strip()
    except Exception:
        pass

    candidate_tree = get_git_tree_oid(candidate_sha)

    # Calculate policy script hashes
    self_path = Path(__file__).resolve()
    generator_sha256 = sha256_file(self_path)

    # Commands
    commands_list = []

    # Run validate_repo.py
    validate_cmd = run_command(["python3", "scripts/validate_repo.py"])
    validate_cmd["category"] = "validation"
    commands_list.append(validate_cmd)

    # Run tests
    test_cmd = run_command(["python3", "-m", "unittest", "discover", "-s", "tests"])
    test_cmd["category"] = "test"
    commands_list.append(test_cmd)

    manifest: Dict[str, Any] = {
        "schema_version": "1",
        "manifest_id": str(uuid.uuid4()),
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "ref": args.policy_ref or "refs/heads/main",
            "sha": args.policy_sha or get_git_sha("HEAD"),
            "generator_path": str(self_path.relative_to(REPO_ROOT)),
            "generator_sha256": generator_sha256,
            "trusted_runner": args.trusted_runner or False,
        },
        "repo": {
            "remote": remote,
            "base_branch": "main",
            "base_sha": base_sha,
            "candidate_branch": candidate_branch,
            "candidate_sha": candidate_sha,
            "candidate_tree_oid": candidate_tree,
        },
        "issue": {
            "numbers": args.issue_numbers or [],
            "labels": args.issue_labels or [],
            "canonical_status": args.issue_status or "status:triage",
        },
        "pull_request": {
            "number": args.pr_number or 0,
            "title": args.pr_title or "",
            "author": args.pr_author or "",
            "draft_state": args.pr_draft or False,
            "base": "main",
            "head_sha": candidate_sha,
            "linked_issues": args.issue_numbers or [],
        },
        "passes": {
            "implementation_pass_ids": args.impl_pass_ids or [],
            "remediation_pass_ids": args.remediation_pass_ids or [],
            "parent_pass_id": args.parent_pass_id or "",
            "candidate_sha": candidate_sha,
            "ordering": (args.impl_pass_ids or []) + (args.remediation_pass_ids or []),
        },
        "qa": {
            "qa_for_pass_id": args.qa_for_pass_id or "",
            "model_profile": args.qa_model_profile or "",
            "verdict": args.qa_verdict or "",
            "report_hash": args.qa_report_hash or "",
            "event_log_hash": args.qa_event_log_hash or "",
            "isolation_proof": {
                "source_mount_read_only": args.iso_source_ro or True,
                "scratch_separate_from_source": args.iso_scratch_separate or True,
                "host_home_mounted": args.iso_home_mounted or False,
                "ssh_config_mounted": args.iso_ssh_mounted or False,
                "gh_config_mounted": args.iso_gh_mounted or False,
                "ambient_credentials_available": args.iso_creds or False,
                "context_files_disabled": args.iso_no_context or True,
                "extensions_disabled": args.iso_no_extensions or True,
                "skills_disabled": args.iso_no_skills or True,
                "themes_disabled": args.iso_no_themes or True,
                "candidate_tree_before": args.iso_tree_before or candidate_tree,
                "candidate_tree_after": args.iso_tree_after or candidate_tree,
                "write_tools_observed": args.iso_write_tools or False,
            },
        },
        "commands": commands_list,
        "validations": [c["command_id"] for c in commands_list if c["category"] == "validation"],
        "tests": [c["command_id"] for c in commands_list if c["category"] == "test"],
        "state_transitions": [
            {
                "from": args.state_from or "",
                "to": args.state_to or "",
                "authority": args.state_authority or "",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ],
        "approvals": [
            {
                "reviewer": args.approver or "",
                "commit_sha": candidate_sha,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "independent": args.approver_independent or False,
            }
        ] if args.approver else [],
        "publication": {
            "merge_result_sha": args.merge_sha or "",
            "publication_sha": args.publication_sha or "",
        },
    }

    # Add the manifest digest excluding its own field
    digest = manifest_digest_excluding_own(manifest)
    manifest.setdefault("policy", {})
    manifest["policy"].setdefault("runner_attestation", {})
    manifest["policy"]["runner_attestation"]["artifact"] = {
        "manifest_sha256": digest
    }

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect governance evidence manifest")
    parser.add_argument("--run-id", required=True, help="Governance run UUID")
    parser.add_argument("--candidate-sha", required=True, help="Full 40-char candidate SHA")
    parser.add_argument("--base-sha", help="Full 40-char base SHA (default: main)")
    parser.add_argument("--candidate-branch", help="Candidate branch name")
    parser.add_argument("--output", help="Output file path (default: stdout)")

    # Policy options
    parser.add_argument("--policy-ref", help="Policy ref (default: refs/heads/main)")
    parser.add_argument("--policy-sha", help="Policy SHA (default: HEAD)")
    parser.add_argument("--trusted-runner", action="store_true", help="Mark as trusted runner")

    # Issue options
    parser.add_argument("--issue-numbers", nargs="*", type=int, default=[])
    parser.add_argument("--issue-labels", nargs="*", default=[])
    parser.add_argument("--issue-status", default="status:triage")

    # PR options
    parser.add_argument("--pr-number", type=int, default=0)
    parser.add_argument("--pr-title", default="")
    parser.add_argument("--pr-author", default="")
    parser.add_argument("--pr-draft", action="store_true")

    # Pass options
    parser.add_argument("--impl-pass-ids", nargs="*", default=[])
    parser.add_argument("--remediation-pass-ids", nargs="*", default=[])
    parser.add_argument("--parent-pass-id", default="")

    # QA options
    parser.add_argument("--qa-for-pass-id", default="")
    parser.add_argument("--qa-model-profile", default="")
    parser.add_argument("--qa-verdict", default="", choices=["", "pass", "fail"])
    parser.add_argument("--qa-report-hash", default="")
    parser.add_argument("--qa-event-log-hash", default="")

    # Isolation proof options
    parser.add_argument("--iso-source-ro", action="store_true", default=True)
    parser.add_argument("--iso-scratch-separate", action="store_true", default=True)
    parser.add_argument("--iso-home-mounted", action="store_true")
    parser.add_argument("--iso-ssh-mounted", action="store_true")
    parser.add_argument("--iso-gh-mounted", action="store_true")
    parser.add_argument("--iso-creds", action="store_true")
    parser.add_argument("--iso-no-context", action="store_true", default=True)
    parser.add_argument("--iso-no-extensions", action="store_true", default=True)
    parser.add_argument("--iso-no-skills", action="store_true", default=True)
    parser.add_argument("--iso-no-themes", action="store_true", default=True)
    parser.add_argument("--iso-tree-before", default="")
    parser.add_argument("--iso-tree-after", default="")
    parser.add_argument("--iso-write-tools", action="store_true")

    # State options
    parser.add_argument("--state-from", default="")
    parser.add_argument("--state-to", default="")
    parser.add_argument("--state-authority", default="")

    # Approval options
    parser.add_argument("--approver", default="")
    parser.add_argument("--approver-independent", action="store_true")

    # Publication options
    parser.add_argument("--merge-sha", default="")
    parser.add_argument("--publication-sha", default="")

    args = parser.parse_args()

    try:
        manifest = collect(args)
        output = json.dumps(manifest, indent=2, sort_keys=True)

        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output)
            print(f"Manifest written to {output_path}", file=sys.stderr)
        else:
            print(output)

        return 0
    except Exception as e:
        print(f"Error collecting evidence: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
