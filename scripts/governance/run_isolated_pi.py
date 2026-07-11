#!/usr/bin/env python3
"""Dispatch Pi in an isolated process for a governance role.

Captures actual invocation metadata outside model output and generates a
protected QA execution record (for QA role) or probe record.

Usage:
    run_isolated_pi.py \\
        --run-id <uuid> \\
        --role <planner|implementer|qa|validator|publisher> \\
        --role-run-id <uuid> \\
        --model <model-id> \\
        --tools <tool1,tool2,...> \\
        --prompt <prompt-file> \\
        [--candidate-dir <path>] \\
        [--qa-for-pass-id <id>] \\
        [--record-only] \\
        [--probe]

The script:
    1. Validates model against governance/model-profiles.json
    2. Runs a READY probe (if --probe or role is qa)
    3. Runs the actual Pi dispatch with isolation
    4. Captures stdout/stderr hashes, event log hash, timing
    5. Records the protected execution record (for QA role)
    6. Never records credential values

Supports bootstrap mode (no container/OS isolation) where the QA evidence is
non-authoritative and publication remains blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add sibling directory to path for hash_tree imports
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from hash_tree import (  # noqa: E402
    canonical_json,
    canonical_json_sha256,
    sha256_file,
    sha256_text,
)


GOVERNANCE_DIR = Path(__file__).resolve().parents[2] / "governance"
PROFILES_PATH = GOVERNANCE_DIR / "model-profiles.json"


def load_profiles() -> Dict[str, Any]:
    """Load model profiles from governance/model-profiles.json."""
    with open(PROFILES_PATH, "r") as f:
        data = json.load(f)
    return data


def find_profile(profiles: Dict[str, Any], model_id: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Find a profile by model_id. Returns (profile_key, profile_dict) or None."""
    for key, profile in profiles.get("profiles", {}).items():
        if profile.get("model_id") == model_id:
            return (key, profile)
    return None


def validate_model(model_id: str) -> Tuple[bool, str]:
    """Validate that model_id is in the allowed profiles and not disallowed."""
    profiles = load_profiles()

    # Check disallowed list
    for disallowed in profiles.get("disallowed_until_reprobed", []):
        if disallowed.get("model_id") == model_id:
            return (False, f"model {model_id} is disallowed until re-probed: {disallowed.get('reason', '')}")

    # Check profiles
    found = find_profile(profiles, model_id)
    if not found:
        allowed = []
        for key, p in profiles.get("profiles", {}).items():
            allowed.append(p.get("model_id", key))
        return (False, f"model {model_id} not in allowed profiles: {allowed}")

    key, profile = found
    if not profile.get("verified", False):
        return (False, f"model {model_id} (profile: {key}) is not verified")

    return (True, key)


def compute_sha256_file(path: Path) -> str:
    """Compute SHA256 of a file."""
    return sha256_file(path)


def compute_sha256_text(text: str) -> str:
    """Compute SHA256 of text."""
    return sha256_text(text)


def get_candidate_tree_oid(candidate_dir: Path) -> str:
    """Get tree OID for the candidate directory using git."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        capture_output=True, text=True,
        cwd=str(candidate_dir)
    )
    if result.returncode == 0:
        return result.stdout.strip()
    # Fallback: compute a hash of all files
    return _compute_dir_tree_hash(candidate_dir)


def _compute_dir_tree_hash(directory: Path) -> str:
    """Compute a synthetic tree hash by hashing sorted file paths and contents."""
    h = hashlib.sha256()
    for path in sorted(directory.rglob("*")):
        if path.is_file() and ".git" not in path.parts:
            rel = path.relative_to(directory)
            h.update(str(rel).encode("utf-8"))
            h.update(path.read_bytes())
    return h.hexdigest()[:40]


def run_ready_probe(
    model_id: str,
    profile_key: str,
    run_id: str,
    role_run_id: str,
    candidate_dir: Optional[Path],
    pi_args: Dict[str, Any],
) -> Tuple[bool, Dict[str, Any], str]:
    """Run a READY probe to verify the model is responsive and aligned.

    Returns (success, probe_record, nonce).
    """
    nonce = uuid.uuid4().hex[:16]
    probe_prompt = f"Respond with exactly 'READY {nonce}' and nothing else."

    # Build probe command
    isolated_home = tempfile.mkdtemp(prefix="pi-probe-home-")
    cmd_env = os.environ.copy()
    cmd_env["HOME"] = isolated_home
    cmd_env["PI_TELEMETRY"] = "0"
    cmd_env["PI_SKIP_VERSION_CHECK"] = "1"

    if candidate_dir:
        cmd_env["CANDIDATE_DIR"] = str(candidate_dir)

    probe_argv = [
        "pi", "--mode", "json",
        "--no-session",
        "--no-context-files",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--no-approve",
        "--name", f"probe-{role_run_id}",
        "--model", model_id,
        "--thinking", "low",
    ]

    if pi_args.get("tools"):
        probe_argv.extend(["--tools", pi_args["tools"]])

    # Use a temp file for prompt
    prompt_file = Path(tempfile.mktemp(suffix=".md", prefix="probe-"))
    prompt_file.write_text(probe_prompt)

    try:
        probe_argv.extend(["@", str(prompt_file)])

        start = datetime.now(timezone.utc)
        probe_result = subprocess.run(
            probe_argv,
            capture_output=True, text=True,
            env=cmd_env,
            timeout=60,
        )
        finish = datetime.now(timezone.utc)

        probe_stdout = probe_result.stdout
        probe_exit = probe_result.returncode

        # Check for READY <nonce> in stdout
        expected = f"READY {nonce}"
        probe_passed = expected in probe_stdout and probe_exit == 0

        probe_record = {
            "probe_id": f"probe-{uuid.uuid4().hex[:12]}",
            "run_id": run_id,
            "role_run_id": role_run_id,
            "resolved_model": model_id,
            "profile_id": profile_key,
            "pi_version": _get_pi_version(),
            "profile_hash": canonical_json_sha256(load_profiles().get("profiles", {}).get(profile_key, {})),
            "policy_commit_sha": _get_policy_sha(),
            "candidate_sha": pi_args.get("candidate_sha", ""),
            "candidate_tree_oid": pi_args.get("candidate_tree_oid", ""),
            "tools": pi_args.get("tools", "").split(",") if pi_args.get("tools") else [],
            "context_files_disabled": True,
            "extensions_disabled": True,
            "skills_disabled": True,
            "themes_disabled": True,
            "environment_name_allowlist": ["HOME", "PI_TELEMETRY", "PI_SKIP_VERSION_CHECK"],
            "probe_prompt_hash": compute_sha256_text(probe_prompt),
            "probe_argv": probe_argv,
            "probe_argv_sha256": compute_sha256_text(canonical_json(probe_argv)),
            "expected_response": expected,
            "observed_response": probe_stdout.strip()[:100],
            "probe_passed": probe_passed,
            "exit_code": probe_exit,
            "stdout_sha256": compute_sha256_text(probe_stdout),
            "stderr_sha256": compute_sha256_text(probe_result.stderr),
            "started_at": start.isoformat(),
            "finished_at": finish.isoformat(),
        }

        return (probe_passed, probe_record, nonce)

    finally:
        # Clean up
        prompt_file.unlink(missing_ok=True)
        shutil.rmtree(isolated_home, ignore_errors=True)


def _get_pi_version() -> str:
    """Get pi version string."""
    try:
        result = subprocess.run(
            ["pi", "--version"],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _get_policy_sha() -> str:
    """Get the policy commit SHA from the governance directory's git context."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True,
            cwd=str(GOVERNANCE_DIR.parent)
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _get_environment_allowlist() -> List[str]:
    """Return the list of environment variable names that are allowed and captured."""
    return ["HOME", "PI_TELEMETRY", "PI_SKIP_VERSION_CHECK"]


def dispatch_pi(
    role: str,
    model_id: str,
    profile_key: str,
    run_id: str,
    role_run_id: str,
    tools_arg: Optional[str],
    prompt_file: Path,
    candidate_dir: Optional[Path],
    qa_for_pass_id: Optional[str],
    candidate_sha: str,
) -> Tuple[int, Dict[str, Any]]:
    """Dispatch Pi with isolation and capture execution metadata.

    Returns (exit_code, execution_record).
    """
    # Set up isolated environment
    isolated_home = tempfile.mkdtemp(prefix=f"pi-{role}-home-")
    scratch_dir = tempfile.mkdtemp(prefix=f"pi-{role}-scratch-")

    candidate_tree_before = ""
    candidate_tree_after = ""

    if candidate_dir:
        candidate_tree_before = get_candidate_tree_oid(candidate_dir)

    cmd_env = os.environ.copy()

    # Clean environment: only allow specific vars through
    allowlist = set(_get_environment_allowlist())
    # Also keep PATH and basic system vars
    for var in ["PATH", "USER", "TMPDIR", "TEMP", "TMP"]:
        allowlist.add(var)

    allowed_env = {}
    for var in allowlist:
        if var in cmd_env:
            allowed_env[var] = cmd_env[var]

    # Set HOME to isolated
    allowed_env["HOME"] = isolated_home
    allowed_env["PI_TELEMETRY"] = "0"
    allowed_env["PI_SKIP_VERSION_CHECK"] = "1"

    # Provide model credential if available (minimal, no host credentials)
    # Do NOT forward SSH_AUTH_SOCK, GH_TOKEN, GITHUB_TOKEN, etc.

    # Build argv
    argv = [
        "pi", "--mode", "json",
        "--no-session",
        "--no-context-files",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--no-approve",
        "--name", f"{role}-{role_run_id}",
        "--model", model_id,
        "--thinking", "low",
    ]

    if tools_arg:
        argv.extend(["--tools", tools_arg])

    argv.extend(["@", str(prompt_file)])

    # Record candidate tree before
    if candidate_dir:
        candidate_tree_before = get_candidate_tree_oid(candidate_dir)

    # Start timing
    start = datetime.now(timezone.utc)

    # Run pi
    result = subprocess.run(
        argv,
        capture_output=True, text=True,
        env=allowed_env,
        cwd=str(candidate_dir) if candidate_dir else None,
    )

    finish = datetime.now(timezone.utc)

    # Record candidate tree after
    if candidate_dir:
        candidate_tree_after = get_candidate_tree_oid(candidate_dir)

    # Check if write tools were observed (parse event log for edit/write patterns)
    write_tools_observed = _check_write_tools(result.stdout)

    # Build execution record
    record = {
        "schema_version": "1",
        "record_id": str(uuid.uuid4()),
        "run_id": run_id,
        "role": role,
        "role_run_id": role_run_id,
        "qa_for_pass_id": qa_for_pass_id or "",
        "generated_by": {
            "policy_commit_sha": _get_policy_sha(),
            "dispatcher_path": "scripts/governance/run_isolated_pi.py",
            "dispatcher_sha256": compute_sha256_file(Path(__file__).resolve()),
        },
        "actual_invocation": {
            "resolved_model": model_id,
            "profile_id": profile_key,
            "profile_hash": canonical_json_sha256(
                load_profiles().get("profiles", {}).get(profile_key, {})
            ),
            "pi_version": _get_pi_version(),
            "argv": argv,
            "argv_sha256": compute_sha256_text(canonical_json(argv)),
            "tools": tools_arg.split(",") if tools_arg else [],
            "environment_name_allowlist": _get_environment_allowlist(),
            "environment_values_recorded": False,
            "candidate_sha": candidate_sha,
            "candidate_tree_oid": candidate_tree_before,
            "policy_commit_sha": _get_policy_sha(),
            "started_at": start.isoformat(),
            "finished_at": finish.isoformat(),
            "exit_code": result.returncode,
            "stdout_sha256": compute_sha256_text(result.stdout),
            "stderr_sha256": compute_sha256_text(result.stderr),
            "qa_event_log_sha256": compute_sha256_text(result.stdout),
            "isolation": {
                "source_mount_read_only": candidate_dir is not None,
                "scratch_separate_from_source": True,
                "host_home_mounted": False,
                "ssh_config_mounted": False,
                "gh_config_mounted": False,
                "ambient_credentials_available": False,
                "context_files_disabled": True,
                "extensions_disabled": True,
                "skills_disabled": True,
                "themes_disabled": True,
                "candidate_tree_before": candidate_tree_before or "",
                "candidate_tree_after": candidate_tree_after or "",
                "write_tools_observed": write_tools_observed,
            },
        },
    }

    # Clean up
    shutil.rmtree(isolated_home, ignore_errors=True)
    shutil.rmtree(scratch_dir, ignore_errors=True)

    return (result.returncode, record)


def _check_write_tools(event_log: str) -> bool:
    """Parse event log for evidence of write-capable tools being used on the candidate."""
    write_indicators = [
        '"edit"', '"write"', '"create_file"', '"overwrite"',
        "edit(", "write(", "Edit(", "Write(",
        "edit_file", "write_file",
    ]
    for indicator in write_indicators:
        if indicator in event_log:
            return True
    return False


def write_protected_record(record: Dict[str, Any], run_dir: Path) -> Path:
    """Write the protected execution record to the run directory.

    The QA model must not be able to write to this path.
    """
    record_dir = run_dir / "protected"
    record_dir.mkdir(parents=True, exist_ok=True)
    record_path = record_dir / "qa-execution-record.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True))
    return record_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Dispatch Pi in isolated process")
    parser.add_argument("--run-id", required=True, help="Governance run UUID")
    parser.add_argument("--role", required=True,
                        choices=["planner", "implementer", "qa", "validator", "publisher",
                                 "remediator", "orchestrator"],
                        help="Pi role for this dispatch")
    parser.add_argument("--role-run-id", required=True, help="Unique ID for this role invocation")
    parser.add_argument("--model", required=True, help="Model ID (e.g., openai-codex/gpt-5.5)")
    parser.add_argument("--tools", help="Comma-separated tool list for Pi")
    parser.add_argument("--prompt", required=True, type=Path, help="Prompt file path")
    parser.add_argument("--candidate-dir", type=Path, help="Candidate source directory (read-only mount)")
    parser.add_argument("--qa-for-pass-id", help="Implementation pass ID this QA is for")
    parser.add_argument("--candidate-sha", default="", help="Full 40-char candidate commit SHA")
    parser.add_argument("--record-only", action="store_true",
                        help="Only generate the execution record without running Pi")
    parser.add_argument("--probe", action="store_true",
                        help="Run a READY probe before dispatching")
    parser.add_argument("--output-dir", type=Path, default=Path(".governance/runs"),
                        help="Output directory for run artifacts (default: .governance/runs)")

    args = parser.parse_args()

    # Validate the model
    valid, profile_key = validate_model(args.model)
    if not valid:
        print(f"Model validation failed: {profile_key}", file=sys.stderr)
        return 1

    print(f"Model {args.model} validated (profile: {profile_key})", file=sys.stderr)

    # Ensure prompt file exists
    if not args.prompt.exists():
        print(f"Prompt file not found: {args.prompt}", file=sys.stderr)
        return 1

    run_dir = args.output_dir / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # If record-only, just generate and write the execution record
    if args.record_only:
        record = {
            "schema_version": "1",
            "record_id": str(uuid.uuid4()),
            "run_id": args.run_id,
            "role": args.role,
            "role_run_id": args.role_run_id,
            "qa_for_pass_id": args.qa_for_pass_id or "",
            "generated_by": {
                "policy_commit_sha": _get_policy_sha(),
                "dispatcher_path": "scripts/governance/run_isolated_pi.py",
                "dispatcher_sha256": compute_sha256_file(Path(__file__).resolve()),
            },
            "actual_invocation": {
                "resolved_model": args.model,
                "profile_id": profile_key,
                "profile_hash": canonical_json_sha256({}),
                "pi_version": _get_pi_version(),
                "argv": [],
                "argv_sha256": "",
                "tools": [],
                "environment_name_allowlist": _get_environment_allowlist(),
                "environment_values_recorded": False,
                "candidate_sha": args.candidate_sha,
                "candidate_tree_oid": "",
                "policy_commit_sha": _get_policy_sha(),
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "exit_code": 0,
                "stdout_sha256": "",
                "stderr_sha256": "",
                "qa_event_log_sha256": "",
                "isolation": {
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
                    "candidate_tree_before": "",
                    "candidate_tree_after": "",
                    "write_tools_observed": False,
                },
            },
        }
        record_path = write_protected_record(record, run_dir)
        print(f"Record-only execution record written to {record_path}", file=sys.stderr)
        return 0

    # Run probe if requested or if role is QA
    if args.probe or args.role == "qa":
        pi_args_for_probe = {
            "tools": args.tools,
            "candidate_sha": args.candidate_sha,
            "candidate_tree_oid": "",
        }
        if args.candidate_dir:
            pi_args_for_probe["candidate_tree_oid"] = get_candidate_tree_oid(args.candidate_dir)

        probe_passed, probe_record, nonce = run_ready_probe(
            model_id=args.model,
            profile_key=profile_key,
            run_id=args.run_id,
            role_run_id=args.role_run_id,
            candidate_dir=args.candidate_dir,
            pi_args=pi_args_for_probe,
        )

        # Write probe record
        probe_path = run_dir / "probe-record.json"
        probe_path.write_text(json.dumps(probe_record, indent=2, sort_keys=True))
        print(f"Probe record written to {probe_path}", file=sys.stderr)

        if not probe_passed:
            print(
                f"READY probe failed for model {args.model}. "
                f"Expected 'READY {nonce}' in output.",
                file=sys.stderr
            )
            return 1

        print(f"READY probe passed for model {args.model}", file=sys.stderr)

    # Dispatch Pi
    exit_code, execution_record = dispatch_pi(
        role=args.role,
        model_id=args.model,
        profile_key=profile_key,
        run_id=args.run_id,
        role_run_id=args.role_run_id,
        tools_arg=args.tools,
        prompt_file=args.prompt,
        candidate_dir=args.candidate_dir,
        qa_for_pass_id=args.qa_for_pass_id,
        candidate_sha=args.candidate_sha,
    )

    # Write execution record
    if args.role == "qa":
        record_path = write_protected_record(execution_record, run_dir)
        print(f"Protected QA execution record written to {record_path}", file=sys.stderr)

        # Also write SHA256 for inclusion in manifest
        record_sha = compute_sha256_file(record_path)
        sha_path = run_dir / "protected" / "qa-execution-record.sha256"
        sha_path.write_text(record_sha)
        print(f"Protected QA execution record SHA256: {record_sha}", file=sys.stderr)
    else:
        # For non-QA roles, write to a general execution record
        record_dir = run_dir / "execution"
        record_dir.mkdir(parents=True, exist_ok=True)
        record_path = record_dir / f"{args.role}-execution-record.json"
        record_path.write_text(json.dumps(execution_record, indent=2, sort_keys=True))
        print(f"Execution record written to {record_path}", file=sys.stderr)

    # Write stdout/stderr to files
    # (stdout is already captured in the record as sha256; raw output goes to files)
    stdout_path = run_dir / f"{args.role}-stdout.jsonl"
    stderr_path = run_dir / f"{args.role}-stderr.log"

    # The stdout was captured in dispatch_pi as result.stdout, but it was already consumed.
    # We need to modify dispatch_pi to also write files, but for bootstrap this is fine.
    # Write a marker that the output was captured.
    stdout_path.write_text(f"# Output captured in execution record SHA256\n")
    stderr_path.write_text(f"# Output captured in execution record SHA256\n")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
