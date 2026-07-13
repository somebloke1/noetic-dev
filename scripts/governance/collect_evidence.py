#!/usr/bin/env python3
"""Collect local governance evidence into an advisory manifest.

This script may be run from protected policy code against a separate candidate
checkout. Unless externally verified GitHub provenance and protected QA records
are supplied later, the resulting manifest remains advisory and the delivery
gate blocks merge/publication readiness.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
POLICY_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hash_tree import manifest_digest_excluding_own, sha256_file, sha256_text  # noqa: E402

ZERO_SHA256 = "0" * 64


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, cwd=repo_root)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def get_git_sha(repo_root: Path, ref: str) -> str:
    return _run_git(repo_root, "rev-parse", "--verify", ref)


def get_git_tree_oid(repo_root: Path, sha: str) -> str:
    return _run_git(repo_root, "rev-parse", f"{sha}^{{tree}}")


def get_remote(repo_root: Path) -> str:
    result = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, cwd=repo_root)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def run_command(registry_id: str, argv: List[str], repo_root: Path, category: str, phase: str = "pre_merge") -> Dict[str, Any]:
    start = _now()
    result = subprocess.run(argv, capture_output=True, text=True, cwd=repo_root)
    finish = _now()
    return {
        "command_id": registry_id,
        "registry_id": registry_id,
        "category": category,
        "phase": phase,
        "argv": argv,
        "cwd": str(repo_root),
        "exit_code": result.returncode,
        "stdout_sha256": sha256_text(result.stdout),
        "stderr_sha256": sha256_text(result.stderr),
        "started_at": start,
        "finished_at": finish,
    }


def load_registry(policy_root: Path) -> Dict[str, Any]:
    with open(policy_root / "governance/command-registry.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _cmd_argv(registry: Dict[str, Any], registry_id: str) -> List[str]:
    return list(registry["commands"][registry_id]["argv"])


def collect(args: argparse.Namespace) -> Dict[str, Any]:
    candidate_root = Path(args.repo_root).resolve()
    policy_root = Path(args.policy_root).resolve()
    registry = load_registry(policy_root)

    candidate_sha = args.candidate_sha
    base_sha = args.base_sha or get_git_sha(candidate_root, "main")
    candidate_tree = get_git_tree_oid(candidate_root, candidate_sha)
    policy_sha = args.policy_sha or get_git_sha(policy_root, "HEAD")
    policy_ref = args.policy_ref or "refs/heads/main"
    generator_path = Path(__file__).resolve()
    generator_sha256 = sha256_file(generator_path)

    commands: List[Dict[str, Any]] = []
    for registry_id in ["repo.validate", "workflow.pinning", "tests.all"]:
        spec = registry["commands"][registry_id]
        argv = _cmd_argv(registry, registry_id)
        commands.append(run_command(registry_id, argv, candidate_root, spec["category"], spec.get("phase", "pre_merge")))

    branch = args.candidate_branch
    if not branch:
        try:
            branch = _run_git(candidate_root, "rev-parse", "--abbrev-ref", "HEAD")
        except Exception:
            branch = ""

    supplied_pass_records: List[Dict[str, Any]] = []
    if args.pass_records_json:
        supplied_pass_records = json.loads(Path(args.pass_records_json).read_text(encoding="utf-8"))
        if not isinstance(supplied_pass_records, list):
            raise RuntimeError("--pass-records-json must contain a JSON array")

    total_pass_ids = (args.impl_pass_ids or []) + (args.remediation_pass_ids or [])
    if supplied_pass_records:
        pass_records = supplied_pass_records
        if not total_pass_ids:
            args.impl_pass_ids = [p.get("pass_id") for p in pass_records if p.get("role") == "implementer"]
            args.remediation_pass_ids = [p.get("pass_id") for p in pass_records if p.get("role") == "remediator"]
            total_pass_ids = (args.impl_pass_ids or []) + (args.remediation_pass_ids or [])
    else:
        if len(total_pass_ids) > 1:
            raise RuntimeError("multi-generation history requires explicit --pass-records-json with per-generation SHA/base/tree")
        pass_records = []
        for pass_id in total_pass_ids:
            role = "remediator" if pass_id in (args.remediation_pass_ids or []) else "implementer"
            pass_records.append({
                "pass_id": pass_id,
                "role": role,
                "role_run_id": f"{pass_id}-run",
                "agent_id": args.implementation_agent_id or "unknown-implementation-agent",
                "model_profile": args.implementation_model_profile or "implementer_candidate",
                "candidate_sha": candidate_sha,
                "base_sha": base_sha,
                "candidate_tree_oid": candidate_tree,
                "started_at": args.candidate_pinned_at or _now(),
                "finished_at": args.candidate_pinned_at or _now(),
            })

    qa_records: List[Dict[str, Any]] = []
    if args.qa_records_json:
        qa_records = json.loads(Path(args.qa_records_json).read_text(encoding="utf-8"))
        if not isinstance(qa_records, list):
            raise RuntimeError("--qa-records-json must contain a JSON array")
    elif args.qa_for_pass_id:
        qa_records.append({
            "qa_run_id": args.qa_run_id or f"qa-{uuid.uuid4().hex[:12]}",
            "role_run_id": args.qa_role_run_id or f"qa-role-{uuid.uuid4().hex[:12]}",
            "agent_id": args.qa_agent_id or "unknown-qa-agent",
            "qa_for_pass_id": args.qa_for_pass_id,
            "model_profile": args.qa_model_profile or "qa_primary",
            "verdict": args.qa_verdict or "fail",
            "report_hash": args.qa_report_hash or ZERO_SHA256,
            "event_log_hash": args.qa_event_log_hash or ZERO_SHA256,
            "base_sha": base_sha,
            "candidate_sha": candidate_sha,
            "candidate_tree_oid": candidate_tree,
            "protected_execution_record_sha256": args.qa_execution_record_sha256 or "",
            "protected_probe_record_sha256": args.qa_probe_record_sha256 or "",
            "protected_execution_record_path": args.qa_execution_record_path or "",
            "protected_probe_record_path": args.qa_probe_record_path or "",
            "isolation_proof": {
                "source_mount_read_only": args.iso_source_ro,
                "scratch_separate_from_source": args.iso_scratch_separate,
                "host_home_mounted": args.iso_home_mounted,
                "ssh_config_mounted": args.iso_ssh_mounted,
                "gh_config_mounted": args.iso_gh_mounted,
                "ambient_credentials_available": args.iso_creds,
                "context_files_disabled": args.iso_no_context,
                "extensions_disabled": args.iso_no_extensions,
                "skills_disabled": args.iso_no_skills,
                "themes_disabled": args.iso_no_themes,
                "candidate_tree_before": args.iso_tree_before or candidate_tree,
                "candidate_tree_after": args.iso_tree_after or candidate_tree,
                "write_tools_observed": args.iso_write_tools,
            },
        })

    candidate_pinned_at = args.candidate_pinned_at or _now()
    manifest: Dict[str, Any] = {
        "schema_version": "1",
        "manifest_id": str(uuid.uuid4()),
        "run_id": args.run_id,
        "generated_at": _now(),
        "policy": {
            "ref": policy_ref,
            "sha": policy_sha,
            "generator_path": str(generator_path.relative_to(policy_root)) if generator_path.is_relative_to(policy_root) else "scripts/governance/collect_evidence.py",
            "generator_sha256": generator_sha256,
            "trusted_runner": False,
            "workflow": {
                "path": ".github/workflows/governance.yml",
                "ref": policy_ref,
                "sha": policy_sha,
                "pinned": True,
            },
            "checkout": {
                "policy_path": str(policy_root),
                "candidate_path": str(candidate_root),
                "separate": policy_root != candidate_root,
            },
        },
        "repo": {
            "remote": get_remote(candidate_root),
            "repository": args.repository,
            "repository_id": args.repository_id,
            "base_branch": "main",
            "base_sha": base_sha,
            "candidate_branch": branch,
            "candidate_sha": candidate_sha,
            "candidate_tree_oid": candidate_tree,
            "candidate_pinned_at": candidate_pinned_at,
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
            "draft_state": args.pr_draft,
            "base": "main",
            "head_ref": branch,
            "head_sha": candidate_sha,
            "linked_issues": args.issue_numbers or [],
            "is_stacked": False,
        },
        "passes": {
            "implementation_pass_ids": args.impl_pass_ids or [],
            "remediation_pass_ids": args.remediation_pass_ids or [],
            "parent_pass_id": args.parent_pass_id or "",
            "candidate_sha": candidate_sha,
            "ordering": (args.impl_pass_ids or []) + (args.remediation_pass_ids or []),
            "pass_records": pass_records,
        },
        "qa": {"records": qa_records},
        "commands": commands,
        "validations": [c["command_id"] for c in commands if c["category"] == "validation" and c.get("phase") == "pre_merge"],
        "tests": [c["command_id"] for c in commands if c["category"] == "test" and c.get("phase") == "pre_merge"],
        "state_transitions": [
            {"from": "AUDITED", "to": "ISSUE_ACCEPTED", "authority": "orchestrator", "timestamp": candidate_pinned_at},
            {"from": "ISSUE_ACCEPTED", "to": "PLAN_REQUESTED", "authority": "orchestrator", "timestamp": candidate_pinned_at},
            {"from": "PLAN_REQUESTED", "to": "PLAN_READY", "authority": "orchestrator", "timestamp": candidate_pinned_at},
            {"from": "PLAN_READY", "to": "IMPLEMENTING", "authority": "orchestrator", "timestamp": candidate_pinned_at},
            {"from": "IMPLEMENTING", "to": "CANDIDATE_PINNED", "authority": "implementer", "timestamp": candidate_pinned_at},
        ],
        "approvals": [
            {
                "reviewer": args.approver,
                "commit_sha": candidate_sha,
                "timestamp": args.approval_timestamp or _now(),
                "independent": args.approver_independent,
                "model_profile": args.approver_model_profile,
                "reasoning_level": args.approver_reasoning_level,
                "state": "APPROVED",
            }
        ] if args.approver else [],
        "publication": {
            "merge_result_sha": args.merge_sha or "",
            "publication_sha": args.publication_sha or "",
            "post_merge_validations": [],
            "post_merge_tests": [],
        },
        "audit": {
            "existing_work_freeze": {
                "status": "active",
                "known_open_pr_count": 10,
                "blocks_publication": True,
                "audit_required": True,
                "audit_completed": False,
            }
        },
    }

    manifest.setdefault("policy", {}).setdefault("runner_attestation", {}).setdefault("artifact", {})
    digest = manifest_digest_excluding_own(manifest)
    manifest["policy"]["runner_attestation"]["artifact"]["manifest_sha256"] = digest
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect governance evidence manifest")
    parser.add_argument("--run-id", required=True, help="Governance run UUID/string")
    parser.add_argument("--candidate-sha", required=True, help="Full 40-char candidate SHA")
    parser.add_argument("--base-sha", help="Full 40-char base SHA (default: candidate main)")
    parser.add_argument("--candidate-branch", default="")
    parser.add_argument("--repo-root", default=str(POLICY_ROOT), help="Candidate checkout root")
    parser.add_argument("--policy-root", default=str(POLICY_ROOT), help="Protected policy checkout root")
    parser.add_argument("--output", help="Output file path (default: stdout)")

    parser.add_argument("--policy-ref", default="refs/heads/main")
    parser.add_argument("--policy-sha", default="")
    parser.add_argument("--repository", default="somebloke1/noetic-dev")
    parser.add_argument("--repository-id", type=int, default=0)

    parser.add_argument("--issue-numbers", nargs="*", type=int, default=[])
    parser.add_argument("--issue-labels", nargs="*", default=[])
    parser.add_argument("--issue-status", default="status:triage")
    parser.add_argument("--pr-number", type=int, default=0)
    parser.add_argument("--pr-title", default="")
    parser.add_argument("--pr-author", default="")
    parser.add_argument("--pr-draft", action="store_true")

    parser.add_argument("--impl-pass-ids", nargs="*", default=[])
    parser.add_argument("--remediation-pass-ids", nargs="*", default=[])
    parser.add_argument("--parent-pass-id", default="")
    parser.add_argument("--pass-records-json", default="", help="JSON array of per-generation pass records")
    parser.add_argument("--implementation-agent-id", default="")
    parser.add_argument("--implementation-model-profile", default="implementer_candidate")
    parser.add_argument("--candidate-pinned-at", default="")

    parser.add_argument("--qa-for-pass-id", default="")
    parser.add_argument("--qa-run-id", default="")
    parser.add_argument("--qa-role-run-id", default="")
    parser.add_argument("--qa-agent-id", default="")
    parser.add_argument("--qa-model-profile", default="qa_primary")
    parser.add_argument("--qa-verdict", default="", choices=["", "pass", "fail"])
    parser.add_argument("--qa-report-hash", default="")
    parser.add_argument("--qa-event-log-hash", default="")
    parser.add_argument("--qa-execution-record-sha256", default="")
    parser.add_argument("--qa-probe-record-sha256", default="")
    parser.add_argument("--qa-execution-record-path", default="")
    parser.add_argument("--qa-probe-record-path", default="")
    parser.add_argument("--qa-records-json", default="", help="JSON array of protected QA records")

    parser.add_argument("--iso-source-ro", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--iso-scratch-separate", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--iso-home-mounted", action="store_true")
    parser.add_argument("--iso-ssh-mounted", action="store_true")
    parser.add_argument("--iso-gh-mounted", action="store_true")
    parser.add_argument("--iso-creds", action="store_true")
    parser.add_argument("--iso-no-context", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--iso-no-extensions", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--iso-no-skills", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--iso-no-themes", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--iso-tree-before", default="")
    parser.add_argument("--iso-tree-after", default="")
    parser.add_argument("--iso-write-tools", action="store_true")

    parser.add_argument("--approver", default="")
    parser.add_argument("--approver-independent", action="store_true")
    parser.add_argument("--approver-model-profile", choices=["reviewer_fable", "reviewer_sol"], default="reviewer_fable")
    parser.add_argument("--approver-reasoning-level", choices=["high", "xhigh", "max"], default="high")
    parser.add_argument("--approval-timestamp", default="")
    parser.add_argument("--merge-sha", default="")
    parser.add_argument("--publication-sha", default="")

    args = parser.parse_args()
    try:
        manifest = collect(args)
        output = json.dumps(manifest, indent=2, sort_keys=True)
        if args.output:
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(output, encoding="utf-8")
            print(f"Manifest written to {path}", file=sys.stderr)
        else:
            print(output)
        return 0
    except Exception as exc:
        print(f"Error collecting evidence: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
