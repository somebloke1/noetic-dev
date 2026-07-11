#!/usr/bin/env python3
"""Dispatch Pi in a process-isolated governance role.

The dispatcher produces protected execution/probe records outside model output.
For QA, source access is read-only, tools are disabled until a credential broker
exists, context/extensions are disabled, and record-only mode is non-evidence.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
GOVERNANCE_DIR = REPO_ROOT / "governance"
PROFILES_PATH = GOVERNANCE_DIR / "model-profiles.json"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hash_tree import canonical_json, canonical_json_sha256, sha256_file, sha256_text  # noqa: E402
from json_schema import load_json_strict  # noqa: E402

QA_TOOL_ALLOWLIST: set[str] = set()
ROLE_TOOL_ALLOWLISTS = {
    "qa": QA_TOOL_ALLOWLIST,
    "planner": {"read", "grep", "find", "ls"},
    "validator": {"read", "grep", "find", "ls", "bash"},
    "publisher": {"read", "grep", "find", "ls", "bash"},
    "orchestrator": {"read", "grep", "find", "ls"},
}
ROLE_PROFILE_IDS = {
    "qa": {"qa_primary"},
    "planner": {"planner"},
    "validator": {"orchestrator"},
    "publisher": {"publisher_dry_run", "publisher_alternate_dry_run"},
    "orchestrator": {"orchestrator"},
}
WRITE_CAPABLE_TOOLS = {"bash", "edit", "write"}
PROVIDER_CREDENTIAL_ENV_NAMES = {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "LITELLM_API_KEY"}
CREDENTIAL_ENV_NAMES = {
    "GH_TOKEN", "GITHUB_TOKEN", "SSH_AUTH_SOCK", "GIT_ASKPASS", "SSH_ASKPASS",
    *PROVIDER_CREDENTIAL_ENV_NAMES,
}
ENV_ALLOWLIST = ["HOME", "PI_TELEMETRY", "PI_SKIP_VERSION_CHECK"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_profiles() -> Dict[str, Any]:
    return load_json_strict(PROFILES_PATH)


def find_profile(profiles: Dict[str, Any], model_id: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    for key, profile in profiles.get("profiles", {}).items():
        if profile.get("model_id") == model_id:
            return key, profile
    return None


def validate_model(model_id: str, role: str | None = None) -> Tuple[bool, str]:
    profiles = load_profiles()
    for disallowed in profiles.get("disallowed_until_reprobed", []):
        if disallowed.get("model_id") == model_id:
            return False, f"model {model_id} is disallowed until re-probed: {disallowed.get('reason', '')}"
    found = find_profile(profiles, model_id)
    if not found:
        allowed = [profile.get("model_id", key) for key, profile in profiles.get("profiles", {}).items()]
        return False, f"model {model_id} not in allowed profiles: {allowed}"
    key, profile = found
    if not profile.get("verified", False):
        return False, f"model {model_id} (profile: {key}) is not verified"
    if role is not None and key not in ROLE_PROFILE_IDS.get(role, set()):
        return False, f"model {model_id} (profile: {key}) is not authorized for role {role}"
    return True, key


def validate_tools(role: str, tools_arg: str | None) -> Tuple[bool, str, List[str]]:
    tools = [item.strip() for item in (tools_arg or "").split(",") if item.strip()]
    allowed = ROLE_TOOL_ALLOWLISTS.get(role, set())
    disallowed = [tool for tool in tools if tool not in allowed]
    if disallowed:
        return False, f"role {role} cannot use tools: {disallowed}; allowed={sorted(allowed)}", tools
    return True, "", tools


def get_policy_sha() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def get_pi_version() -> str:
    try:
        result = subprocess.run(["pi", "--version"], capture_output=True, text=True, timeout=10)
        return (result.stdout or result.stderr).strip() or "unknown"
    except Exception:
        return "unknown"


def _git_stdout(candidate_dir: Path, *args: str) -> Tuple[bool, str, str]:
    result = subprocess.run(["git", *args], cwd=candidate_dir, capture_output=True, text=True)
    return result.returncode == 0, result.stdout.strip(), result.stderr.strip()


def get_candidate_tree_oid(candidate_dir: Path) -> str:
    ok, stdout, _stderr = _git_stdout(candidate_dir, "rev-parse", "HEAD^{tree}")
    return stdout if ok else ""


def get_candidate_head_sha(candidate_dir: Path) -> str:
    ok, stdout, _stderr = _git_stdout(candidate_dir, "rev-parse", "HEAD")
    return stdout if ok else ""


def validate_candidate_checkout(candidate_dir: Path, candidate_sha: str) -> Tuple[bool, str, str]:
    if not candidate_dir.exists():
        return False, f"candidate-dir does not exist: {candidate_dir}", ""
    ok, inside, stderr = _git_stdout(candidate_dir, "rev-parse", "--is-inside-work-tree")
    if not ok or inside != "true":
        return False, f"candidate-dir is not a git worktree: {stderr or inside or candidate_dir}", ""

    head_sha = get_candidate_head_sha(candidate_dir)
    if head_sha != candidate_sha:
        return False, f"candidate-dir HEAD {head_sha or '<unknown>'} does not match --candidate-sha {candidate_sha}", ""

    ok, expected_tree, stderr = _git_stdout(candidate_dir, "rev-parse", f"{candidate_sha}^{{tree}}")
    if not ok or not re_full_sha(expected_tree):
        return False, f"candidate SHA tree cannot be resolved with git rev-parse {candidate_sha}^{{tree}}: {stderr or expected_tree}", expected_tree
    ok, head_tree, stderr = _git_stdout(candidate_dir, "rev-parse", "HEAD^{tree}")
    if not ok or not re_full_sha(head_tree):
        return False, f"candidate HEAD tree cannot be resolved: {stderr or head_tree}", head_tree
    if head_tree != expected_tree:
        return False, f"candidate HEAD tree {head_tree} does not match git rev-parse {candidate_sha}^{{tree}} {expected_tree}", head_tree

    ok, status, stderr = _git_stdout(candidate_dir, "status", "--porcelain=v1", "--untracked-files=all")
    if not ok:
        return False, f"candidate git status failed: {stderr}", expected_tree
    if status:
        return False, f"candidate checkout is dirty or has untracked files; git status --porcelain: {status}", expected_tree

    return True, "", expected_tree


def _pi_binary() -> Path:
    found = shutil.which("pi")
    if not found:
        raise RuntimeError("pi executable not found on PATH")
    return Path(found).resolve()


def _node_prefix_for_pi(pi_binary: Path) -> Optional[Path]:
    # pi is expected under .../versions/node/<version>/bin or a symlink into that tree.
    for parent in [pi_binary, *pi_binary.parents]:
        if parent.name == "bin" and parent.parent.name.startswith("v"):
            return parent.parent
        if parent.name.startswith("v") and parent.parent.name == "node":
            return parent
    # Resolved CLI may be under <prefix>/lib/node_modules/...
    for parent in pi_binary.parents:
        if parent.name.startswith("v") and parent.parent.name == "node":
            return parent
    return None


def _mkdir_mount_parents(path: Path) -> List[str]:
    parts = path.resolve().parts
    result: List[str] = []
    current = Path(parts[0])
    for part in parts[1:-1]:
        current = current / part
        result.extend(["--dir", str(current)])
    return result


def build_bwrap_command(inner_argv: List[str], *, candidate_dir: Optional[Path], prompt_file: Path, cwd: Optional[Path]) -> List[str]:
    bwrap = shutil.which("bwrap") or shutil.which("bubblewrap")
    if not bwrap:
        raise RuntimeError("bubblewrap (bwrap) is required for isolated Pi dispatch")

    pi_path = _pi_binary()
    node_prefix = _node_prefix_for_pi(pi_path)
    if not node_prefix:
        raise RuntimeError(f"unable to identify node prefix for pi executable: {pi_path}")

    cmd: List[str] = [
        bwrap,
        "--die-with-parent",
        "--unshare-user",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--ro-bind", "/usr", "/usr",
        "--symlink", "usr/bin", "/bin",
        "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib64", "/lib64",
        "--ro-bind", "/etc", "/etc",
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",
        "--dir", "/tmp/home",
        "--dir", "/tmp/scratch",
        "--setenv", "HOME", "/tmp/home",
        "--setenv", "PI_TELEMETRY", "0",
        "--setenv", "PI_SKIP_VERSION_CHECK", "1",
        "--unsetenv", "GH_TOKEN",
        "--unsetenv", "GITHUB_TOKEN",
        "--unsetenv", "SSH_AUTH_SOCK",
        "--unsetenv", "GIT_ASKPASS",
        "--unsetenv", "SSH_ASKPASS",
    ]

    # Mount only the node runtime, not the host HOME tree.
    cmd.extend(_mkdir_mount_parents(node_prefix))
    cmd.extend(["--ro-bind", str(node_prefix), str(node_prefix)])

    # Mount prompt read-only into tmpfs; the inner argv must reference /tmp/prompt.md.
    cmd.extend(["--ro-bind", str(prompt_file.resolve()), "/tmp/prompt.md"])

    if candidate_dir:
        candidate_dir = candidate_dir.resolve()
        cmd.extend(_mkdir_mount_parents(candidate_dir))
        cmd.extend(["--ro-bind", str(candidate_dir), str(candidate_dir)])

    actual_cwd = cwd.resolve() if cwd else Path("/tmp/scratch")
    cmd.extend(["--chdir", str(actual_cwd)])
    cmd.extend(["--"])
    cmd.extend(inner_argv)
    return cmd


def _clean_env(scoped_credentials: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    # bwrap does the real containment. Keep only path-like runtime values plus
    # explicitly scoped provider credentials required by the Pi process.
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PI_TELEMETRY": "0",
        "PI_SKIP_VERSION_CHECK": "1",
    }
    for name, value in (scoped_credentials or {}).items():
        env[name] = value
    return env


def _run_isolated(
    inner_argv: List[str],
    *,
    candidate_dir: Optional[Path],
    prompt_file: Path,
    cwd: Optional[Path],
    timeout: int,
    scoped_credentials: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    bwrap_argv = build_bwrap_command(inner_argv, candidate_dir=candidate_dir, prompt_file=prompt_file, cwd=cwd)
    return subprocess.run(
        bwrap_argv,
        capture_output=True,
        text=True,
        env=_clean_env(scoped_credentials),
        timeout=timeout,
    )


def _base_invocation_fields(
    *,
    model_id: str,
    profile_key: str,
    tools: List[str],
    candidate_sha: str,
    base_sha: str,
    candidate_tree_oid: str,
) -> Dict[str, Any]:
    profile = load_profiles().get("profiles", {}).get(profile_key, {})
    return {
        "resolved_model": model_id,
        "profile_id": profile_key,
        "profile_hash": canonical_json_sha256(profile),
        "pi_version": get_pi_version(),
        "tools": tools,
        "environment_name_allowlist": ENV_ALLOWLIST,
        "candidate_sha": candidate_sha,
        "base_sha": base_sha,
        "candidate_tree_oid": candidate_tree_oid,
        "policy_commit_sha": get_policy_sha(),
    }


def run_ready_probe(
    *,
    model_id: str,
    profile_key: str,
    run_id: str,
    role_run_id: str,
    candidate_dir: Optional[Path],
    tools: List[str],
    candidate_sha: str,
    base_sha: str,
    candidate_tree_oid: str,
    timeout: int,
    scoped_credentials: Optional[Dict[str, str]] = None,
) -> Tuple[bool, Dict[str, Any], str]:
    nonce = uuid.uuid4().hex[:16]
    prompt = f"Respond with exactly 'READY {nonce}' and nothing else."
    with tempfile.NamedTemporaryFile("w", suffix=".md", prefix="pi-probe-", delete=False) as handle:
        handle.write(prompt)
        prompt_path = Path(handle.name)
    inner_argv = [
        str(_pi_binary()),
        "--mode", "json",
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
    if tools:
        inner_argv.extend(["--tools", ",".join(tools)])
    inner_argv.extend(["@", "/tmp/prompt.md"])

    start = _now()
    try:
        result = _run_isolated(
            inner_argv,
            candidate_dir=candidate_dir,
            prompt_file=prompt_path,
            cwd=candidate_dir,
            timeout=timeout,
            scoped_credentials=scoped_credentials,
        )
    finally:
        prompt_path.unlink(missing_ok=True)
    finish = _now()

    expected = f"READY {nonce}"
    observed = result.stdout.strip()
    probe_passed = result.returncode == 0 and observed == expected
    base_fields = _base_invocation_fields(
        model_id=model_id,
        profile_key=profile_key,
        tools=tools,
        candidate_sha=candidate_sha,
        base_sha=base_sha,
        candidate_tree_oid=candidate_tree_oid,
    )
    record = {
        "schema_version": "1",
        "probe_id": f"probe-{uuid.uuid4().hex[:12]}",
        "run_id": run_id,
        "role_run_id": role_run_id,
        **base_fields,
        "context_files_disabled": True,
        "extensions_disabled": True,
        "skills_disabled": True,
        "themes_disabled": True,
        "probe_argv": inner_argv,
        "probe_argv_sha256": sha256_text(canonical_json(inner_argv)),
        "probe_prompt_hash": sha256_text(prompt),
        "probe_event_log_sha256": sha256_text(result.stdout),
        "nonce": nonce,
        "expected_response": expected,
        "observed_response": observed,
        "exit_code": result.returncode,
        "stdout_sha256": sha256_text(result.stdout),
        "stderr_sha256": sha256_text(result.stderr),
        "started_at": start,
        "finished_at": finish,
    }
    return probe_passed, record, nonce


def _observed_tool_names(stdout: str) -> List[str]:
    import json

    observed: List[str] = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        for key in ["tool", "tool_name", "name", "recipient_name"]:
            value = event.get(key)
            if isinstance(value, str) and value:
                observed.append(value.split(".")[-1])
    return observed


def _write_tools_observed(stdout: str) -> bool:
    return any(name in WRITE_CAPABLE_TOOLS for name in _observed_tool_names(stdout))


def _credential_interface(scoped_credentials: Optional[Dict[str, str]], tools: List[str], role: str) -> Dict[str, Any]:
    credential_names = sorted((scoped_credentials or {}).keys())
    return {
        "type": "scoped_env",
        "names": credential_names,
        "values_recorded": False,
        "brokered": False,
        "available_to_tools": bool(credential_names and tools),
        "tools_disabled_for_authoritative_qa": role == "qa" and not tools,
    }


def dispatch_pi(
    *,
    role: str,
    model_id: str,
    profile_key: str,
    run_id: str,
    role_run_id: str,
    tools: List[str],
    prompt_file: Path,
    candidate_dir: Optional[Path],
    qa_for_pass_id: Optional[str],
    candidate_sha: str,
    base_sha: str,
    timeout: int,
    scoped_credentials: Optional[Dict[str, str]] = None,
) -> Tuple[int, Dict[str, Any], str, str]:
    candidate_tree_before = get_candidate_tree_oid(candidate_dir) if candidate_dir else ""
    inner_argv = [
        str(_pi_binary()),
        "--mode", "json",
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
    if tools:
        inner_argv.extend(["--tools", ",".join(tools)])
    inner_argv.extend(["@", "/tmp/prompt.md"])

    start = _now()
    result = _run_isolated(
        inner_argv,
        candidate_dir=candidate_dir,
        prompt_file=prompt_file,
        cwd=candidate_dir,
        timeout=timeout,
        scoped_credentials=scoped_credentials,
    )
    finish = _now()
    candidate_tree_after = get_candidate_tree_oid(candidate_dir) if candidate_dir else ""

    base_fields = _base_invocation_fields(
        model_id=model_id,
        profile_key=profile_key,
        tools=tools,
        candidate_sha=candidate_sha,
        base_sha=base_sha,
        candidate_tree_oid=candidate_tree_before,
    )
    isolation = {
        "source_mount_read_only": candidate_dir is not None,
        "scratch_separate_from_source": True,
        "host_home_mounted": False,
        "ssh_config_mounted": False,
        "gh_config_mounted": False,
        "ambient_credentials_available": False,
        "host_proc_mounted": False,
        "procfs_scope": "private_pid_namespace",
        "context_files_disabled": True,
        "extensions_disabled": True,
        "skills_disabled": True,
        "themes_disabled": True,
        "candidate_tree_before": candidate_tree_before,
        "candidate_tree_after": candidate_tree_after,
        "write_tools_observed": _write_tools_observed(result.stdout),
    }
    record = {
        "schema_version": "1",
        "record_id": str(uuid.uuid4()),
        "run_id": run_id,
        "role": role,
        "role_run_id": role_run_id,
        "qa_for_pass_id": qa_for_pass_id or "",
        "evidence_class": "authoritative" if role == "qa" else "execution",
        "record_only": False,
        "generated_by": {
            "policy_commit_sha": get_policy_sha(),
            "dispatcher_path": "scripts/governance/run_isolated_pi.py",
            "dispatcher_sha256": sha256_file(Path(__file__).resolve()),
        },
        "actual_invocation": {
            **base_fields,
            "argv": inner_argv,
            "argv_sha256": sha256_text(canonical_json(inner_argv)),
            "environment_values_recorded": False,
            "credential_interface": _credential_interface(scoped_credentials, tools, role),
            "started_at": start,
            "finished_at": finish,
            "exit_code": result.returncode,
            "stdout_sha256": sha256_text(result.stdout),
            "stderr_sha256": sha256_text(result.stderr),
            "qa_event_log_sha256": sha256_text(result.stdout),
            "isolation": isolation,
        },
    }
    return result.returncode, record, result.stdout, result.stderr


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(data), encoding="utf-8")


def write_protected_record(record: Dict[str, Any], run_dir: Path) -> Path:
    record_dir = run_dir / "protected"
    record_dir.mkdir(parents=True, exist_ok=True)
    record_path = record_dir / "qa-execution-record.json"
    write_json(record_path, record)
    return record_path


def _inside(path: Path, maybe_parent: Path) -> bool:
    try:
        path.resolve().relative_to(maybe_parent.resolve())
        return True
    except ValueError:
        return False


def resolve_scoped_credentials(names: Iterable[str]) -> Tuple[bool, str, Dict[str, str]]:
    credentials: Dict[str, str] = {}
    for name in names:
        if name not in PROVIDER_CREDENTIAL_ENV_NAMES:
            return False, f"credential env {name} is not an allowed provider credential name", {}
        value = os.environ.get(name)
        if not value:
            return False, f"credential env {name} is unavailable; invocation blocked", {}
        credentials[name] = value
    return True, "", credentials


def _non_evidence_record(args: argparse.Namespace, profile_key: str, tools: List[str]) -> Dict[str, Any]:
    return {
        "schema_version": "1",
        "record_id": str(uuid.uuid4()),
        "run_id": args.run_id,
        "role": args.role,
        "role_run_id": args.role_run_id,
        "qa_for_pass_id": args.qa_for_pass_id or "",
        "evidence_class": "non-evidence",
        "record_only": True,
        "generated_by": {
            "policy_commit_sha": get_policy_sha(),
            "dispatcher_path": "scripts/governance/run_isolated_pi.py",
            "dispatcher_sha256": sha256_file(Path(__file__).resolve()),
        },
        "actual_invocation": {
            **_base_invocation_fields(
                model_id=args.model,
                profile_key=profile_key,
                tools=tools,
                candidate_sha=args.candidate_sha,
                base_sha=args.base_sha,
                candidate_tree_oid="",
            ),
            "argv": [],
            "argv_sha256": "",
            "environment_values_recorded": False,
            "started_at": _now(),
            "finished_at": _now(),
            "exit_code": 0,
            "stdout_sha256": "",
            "stderr_sha256": "",
            "qa_event_log_sha256": "",
            "isolation": {
                "source_mount_read_only": False,
                "scratch_separate_from_source": True,
                "host_home_mounted": False,
                "ssh_config_mounted": False,
                "gh_config_mounted": False,
                "ambient_credentials_available": False,
                "host_proc_mounted": False,
                "procfs_scope": "private_pid_namespace",
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Dispatch Pi in isolated process")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--role", required=True, choices=sorted(ROLE_TOOL_ALLOWLISTS))
    parser.add_argument("--role-run-id", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--tools", default="")
    parser.add_argument("--prompt", required=True, type=Path)
    parser.add_argument("--candidate-dir", type=Path)
    parser.add_argument("--qa-for-pass-id", default="")
    parser.add_argument("--candidate-sha", default="")
    parser.add_argument("--base-sha", default="")
    parser.add_argument("--record-only", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--credential-env", action="append", default=[], help="Scoped provider credential env name for Pi process")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output-dir", type=Path, default=Path(".governance/runs"))
    args = parser.parse_args()

    valid, profile_key_or_error = validate_model(args.model, args.role)
    if not valid:
        print(f"Model validation failed: {profile_key_or_error}", file=sys.stderr)
        return 1
    profile_key = profile_key_or_error

    tools_ok, tool_error, tools = validate_tools(args.role, args.tools)
    if not tools_ok:
        print(tool_error, file=sys.stderr)
        return 1

    if args.role == "qa":
        if not args.qa_for_pass_id:
            print("QA dispatch requires --qa-for-pass-id", file=sys.stderr)
            return 1
        if not args.candidate_dir:
            print("QA dispatch requires --candidate-dir", file=sys.stderr)
            return 1
        if not re_full_sha(args.candidate_sha):
            print("QA dispatch requires full --candidate-sha", file=sys.stderr)
            return 1
        if not re_full_sha(args.base_sha):
            print("QA dispatch requires full --base-sha", file=sys.stderr)
            return 1
        if _inside(args.output_dir, args.candidate_dir):
            print("protected output-dir must not be inside candidate-dir", file=sys.stderr)
            return 1
        checkout_ok, checkout_error, _tree = validate_candidate_checkout(args.candidate_dir, args.candidate_sha)
        if not checkout_ok:
            print(checkout_error, file=sys.stderr)
            return 1

    if not args.prompt.exists():
        print(f"Prompt file not found: {args.prompt}", file=sys.stderr)
        return 1

    creds_ok, creds_error, scoped_credentials = resolve_scoped_credentials(args.credential_env)
    if not creds_ok:
        print(creds_error, file=sys.stderr)
        return 1

    run_dir = args.output_dir / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    if args.record_only:
        record = _non_evidence_record(args, profile_key, tools)
        path = run_dir / "non-evidence" / f"{args.role}-record-only.json"
        write_json(path, record)
        print(f"NON-EVIDENCE record-only output written to {path}", file=sys.stderr)
        return 0

    candidate_tree = get_candidate_tree_oid(args.candidate_dir) if args.candidate_dir else ""

    if args.probe or args.role == "qa":
        probe_passed, probe_record, nonce = run_ready_probe(
            model_id=args.model,
            profile_key=profile_key,
            run_id=args.run_id,
            role_run_id=args.role_run_id,
            candidate_dir=args.candidate_dir,
            tools=tools,
            candidate_sha=args.candidate_sha,
            base_sha=args.base_sha,
            candidate_tree_oid=candidate_tree,
            timeout=min(args.timeout, 120),
            scoped_credentials=scoped_credentials,
        )
        probe_path = run_dir / "protected" / "qa-probe-record.json" if args.role == "qa" else run_dir / "execution" / f"{args.role}-probe-record.json"
        write_json(probe_path, probe_record)
        print(f"Probe record written to {probe_path}", file=sys.stderr)
        if not probe_passed:
            print(f"READY probe failed; expected exact 'READY {nonce}'", file=sys.stderr)
            return 1

    exit_code, execution_record, stdout, stderr = dispatch_pi(
        role=args.role,
        model_id=args.model,
        profile_key=profile_key,
        run_id=args.run_id,
        role_run_id=args.role_run_id,
        tools=tools,
        prompt_file=args.prompt,
        candidate_dir=args.candidate_dir,
        qa_for_pass_id=args.qa_for_pass_id,
        candidate_sha=args.candidate_sha,
        base_sha=args.base_sha,
        timeout=args.timeout,
        scoped_credentials=scoped_credentials,
    )

    if args.role == "qa":
        record_path = write_protected_record(execution_record, run_dir)
        sha_path = run_dir / "protected" / "qa-execution-record.sha256"
        sha_path.write_text(sha256_file(record_path), encoding="utf-8")
        print(f"Protected QA execution record written to {record_path}", file=sys.stderr)
        print(f"Protected QA execution record SHA256: {sha_path.read_text(encoding='utf-8')}", file=sys.stderr)
    else:
        record_path = run_dir / "execution" / f"{args.role}-execution-record.json"
        write_json(record_path, execution_record)
        print(f"Execution record written to {record_path}", file=sys.stderr)

    (run_dir / f"{args.role}-stdout.jsonl").write_text(stdout, encoding="utf-8")
    (run_dir / f"{args.role}-stderr.log").write_text(stderr, encoding="utf-8")
    return exit_code


def re_full_sha(value: str) -> bool:
    import re

    return bool(re.fullmatch(r"[a-f0-9]{40}", value or ""))


if __name__ == "__main__":
    raise SystemExit(main())
