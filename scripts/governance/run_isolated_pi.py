#!/usr/bin/env python3
"""Dispatch Pi in a process-isolated governance role.

The dispatcher produces protected execution/probe records outside model output.
For QA, source access is read-only, tools are disabled until a credential broker
exists, context/extensions are disabled, and record-only mode is non-evidence.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
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
from json_schema import load_json_strict, validate_schema  # noqa: E402
from model_routing import (  # noqa: E402
    AUTHORITATIVE_QA_PI_CONTRACT,
    ModelRoutingError,
    STANDARD_MODELS,
    _report_outcome,
    _strict_json_equal,
    create_router_service,
    load_litellm_key,
    load_policy,
    strict_json,
    validate_decision,
)
from route_evidence import validate_route_evidence  # noqa: E402

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
PROVIDER_CREDENTIAL_ENV_NAMES = {"LITELLM_API_KEY"}
CREDENTIAL_ENV_NAMES = {
    "GH_TOKEN", "GITHUB_TOKEN", "SSH_AUTH_SOCK", "GIT_ASKPASS", "SSH_ASKPASS",
    *PROVIDER_CREDENTIAL_ENV_NAMES,
}
ENV_ALLOWLIST = ["HOME", "PI_CODING_AGENT_DIR", "PI_TELEMETRY", "PI_SKIP_VERSION_CHECK", "LITELLM_API_KEY"]
PI_CONFIG_MOUNT = Path("/tmp/pi-agent")
MAX_ROUTED_PI_TIMEOUT = 900
QA_FOR_PASS_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
PI_DECISION_CLAIM_DIR = Path("/var/tmp") / f"noetic-dev-pi-decision-claims-{os.getuid()}"
PI_JSONL_EVENT_TYPES = {
    "session",
    "agent_start", "agent_end", "turn_start", "turn_end",
    "message_start", "message_update", "message_end",
    "tool_execution_start", "tool_execution_update", "tool_execution_end",
    "queue_update", "compaction_start", "compaction_end",
    "auto_retry_start", "auto_retry_end", "session_info_changed",
    "thinking_level_changed",
}


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


def _require_validated_tools(role: str, tools: List[str]) -> None:
    if not isinstance(tools, list) or not all(isinstance(tool, str) and tool for tool in tools):
        raise RuntimeError("routed Pi tools must be a list of non-empty names")
    allowed = ROLE_TOOL_ALLOWLISTS.get(role)
    if allowed is None or any(tool not in allowed for tool in tools):
        raise RuntimeError(f"role {role} cannot use routed Pi tools: {tools}")


def _require_validated_identity(role: str, qa_for_pass_id: Optional[str]) -> None:
    if role not in ROLE_TOOL_ALLOWLISTS:
        raise RuntimeError("routed Pi role is invalid")
    if role == "qa":
        if not isinstance(qa_for_pass_id, str) or not QA_FOR_PASS_ID.fullmatch(qa_for_pass_id):
            raise RuntimeError("routed QA requires a bounded ASCII qa_for_pass_id")
    elif qa_for_pass_id not in (None, ""):
        raise RuntimeError("non-QA routed Pi cannot claim a QA generation")


def get_policy_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, env=_clean_env()
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def get_pi_version() -> str:
    try:
        result = subprocess.run(
            ["pi", "--version"], capture_output=True, text=True, timeout=10, env=_clean_env()
        )
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
    """Validate a trusted/private checkout with host Git.

    Do not call this on a candidate-controlled source checkout before
    materialization. Source checkout validation is performed inside the
    bootstrap bubblewrap sandbox by materialize_candidate_checkout().
    """
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

    ok, index_flags, stderr = _git_stdout(candidate_dir, "ls-files", "-v")
    if not ok:
        return False, f"candidate git ls-files -v failed: {stderr}", expected_tree
    hidden_index_entries = [line for line in index_flags.splitlines() if line and (line[0].islower() or line[0] == "S")]
    if hidden_index_entries:
        return False, "candidate checkout has assume-unchanged or skip-worktree index entries: " + "; ".join(hidden_index_entries), expected_tree

    ok, status, stderr = _git_stdout(candidate_dir, "status", "--porcelain=v1", "--untracked-files=all")
    if not ok:
        return False, f"candidate git status failed: {stderr}", expected_tree
    if status:
        return False, f"candidate checkout is dirty or has untracked files; git status --porcelain: {status}", expected_tree

    ok, ignored, stderr = _git_stdout(candidate_dir, "ls-files", "--others", "--ignored", "--exclude-standard")
    if not ok:
        return False, f"candidate ignored-file scan failed: {stderr}", expected_tree
    if ignored:
        return False, "candidate checkout has ignored untracked entries: " + ignored, expected_tree

    return True, "", expected_tree


def _read_gitfile(path: Path) -> Optional[Path]:
    if path.is_dir():
        return path.resolve()
    if not path.is_file():
        return None
    try:
        data = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    prefix = "gitdir:"
    if not data.lower().startswith(prefix):
        return None
    gitdir = data[len(prefix):].strip()
    gitdir_path = Path(gitdir)
    if not gitdir_path.is_absolute():
        gitdir_path = path.parent / gitdir_path
    return gitdir_path.resolve()


def _candidate_git_metadata_ro_mounts(candidate_dir: Path) -> List[Path]:
    """Return narrowly scoped Git metadata paths needed for a worktree.

    Git worktrees often have a .git file pointing outside the working tree.
    Parsing that file lets the bootstrap sandbox mount the required object and
    index metadata read-only, while avoiding any host-authority Git invocation
    against candidate-controlled local configuration.
    """
    mounts: List[Path] = []
    gitdir = _read_gitfile(candidate_dir / ".git")
    if not gitdir:
        return mounts
    try:
        gitdir.relative_to(candidate_dir.resolve())
    except ValueError:
        if gitdir.parent.name != "worktrees":
            raise RuntimeError(f"external gitdir is not a supported Git worktree metadata path: {gitdir}")
        backlink_file = gitdir / "gitdir"
        try:
            backlink = Path(backlink_file.read_text(encoding="utf-8", errors="strict").strip())
        except (OSError, UnicodeError) as error:
            raise RuntimeError(f"external gitdir has no readable worktree backlink: {gitdir}") from error
        if not backlink.is_absolute():
            backlink = gitdir / backlink
        if backlink.resolve() != (candidate_dir / ".git").resolve():
            raise RuntimeError(f"external gitdir backlink does not identify candidate worktree: {gitdir}")
        mounts.extend([gitdir / "HEAD", gitdir / "index", gitdir / "commondir"])

    commondir_file = gitdir / "commondir"
    if commondir_file.is_file():
        data = commondir_file.read_text(encoding="utf-8", errors="replace").strip()
        if data:
            common = Path(data)
            if not common.is_absolute():
                common = gitdir / common
            common = common.resolve()
            try:
                common.relative_to(candidate_dir.resolve())
            except ValueError:
                if common.name != ".git" or gitdir.parent.parent != common:
                    raise RuntimeError(f"external commondir is not the owning common Git directory: {common}")
                mounts.extend([common / "objects", common / "refs", common / "packed-refs"])
    return sorted(set(mounts), key=lambda item: (len(str(item)), str(item)))


def _build_bootstrap_bwrap_command(candidate_dir: Path, parent_dir: Path, candidate_sha: str) -> List[str]:
    bwrap = shutil.which("bwrap") or shutil.which("bubblewrap")
    if not bwrap:
        raise RuntimeError("bubblewrap (bwrap) is required for private candidate materialization")

    source = candidate_dir.resolve()
    destination_parent = parent_dir.resolve()
    if not source.exists():
        raise RuntimeError(f"candidate-dir does not exist: {candidate_dir}")
    if _inside(destination_parent, source):
        raise RuntimeError("private candidate parent must not be inside candidate-dir")

    script = r'''set -eu
src="$1"
sha="$2"
dst_parent="$3"
dst="$dst_parent/candidate-checkout"

export HOME=/tmp/home
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=/bin/false
export SSH_ASKPASS=/bin/false

case "$sha" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) ;;
  *) echo "candidate SHA is not a full lowercase SHA-1" >&2; exit 11 ;;
esac

[ ! -e "$dst" ] || { echo "private candidate checkout path already exists: $dst" >&2; exit 12; }
mkdir -p "$dst"

# Source validation runs inside confinement. Command-line config disables known
# executable status callbacks while preserving fail-closed clean-tree checks.
expected_head=$(git -c safe.directory=* -c core.fsmonitor=false -C "$src" rev-parse HEAD)
[ "$expected_head" = "$sha" ] || { echo "candidate-dir HEAD $expected_head does not match requested $sha" >&2; exit 13; }
expected_tree=$(git -c safe.directory=* -c core.fsmonitor=false -C "$src" rev-parse "$sha^{tree}")
head_tree=$(git -c safe.directory=* -c core.fsmonitor=false -C "$src" rev-parse HEAD^{tree})
[ "$head_tree" = "$expected_tree" ] || { echo "candidate HEAD tree $head_tree does not match requested tree $expected_tree" >&2; exit 14; }

index_flags=$(git -c safe.directory=* -c core.fsmonitor=false -C "$src" ls-files -v)
if printf '%s\n' "$index_flags" | grep -E '^[[:lower:]S]' >/dev/null 2>&1; then
  echo "candidate checkout has assume-unchanged or skip-worktree index entries" >&2
  exit 15
fi
python3 - "$src" "$expected_tree" <<'PY'
import os
import stat
import subprocess
import sys
from pathlib import Path

src = Path(sys.argv[1])
tree = sys.argv[2]
expected = {}
entries = subprocess.check_output(
    ["git", "-c", "safe.directory=*", "-c", "core.fsmonitor=false", "-C", str(src), "ls-tree", "-r", "-z", "--full-tree", tree]
).split(b"\0")
for entry in entries:
    if not entry:
        continue
    meta, raw_path = entry.split(b"\t", 1)
    mode, kind, oid = meta.decode("ascii").split(" ")
    if kind != "blob":
        raise SystemExit(f"unsupported tree entry kind {kind} for {raw_path!r}")
    path_text = raw_path.decode("utf-8", errors="surrogateescape")
    data = subprocess.check_output(["git", "-C", str(src), "cat-file", "blob", oid])
    expected[path_text] = (mode, data)

for path_text, (mode, data) in expected.items():
    path = src / path_text
    if mode == "120000":
        if not path.is_symlink() or os.readlink(path).encode("utf-8", errors="surrogateescape") != data:
            raise SystemExit(f"candidate checkout differs from expected tree: {path_text}")
        continue
    if not path.is_file() or path.is_symlink() or path.read_bytes() != data:
        raise SystemExit(f"candidate checkout differs from expected tree: {path_text}")
    executable = bool(path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
    if executable != (mode == "100755"):
        raise SystemExit(f"candidate checkout executable bit differs from expected tree: {path_text}")

expected_paths = set(expected)
untracked = []
for root, dirs, files in os.walk(src):
    root_path = Path(root)
    if root_path == src:
        dirs[:] = [item for item in dirs if item != ".git"]
        files = [item for item in files if item != ".git"]
    for name in files:
        rel = (root_path / name).relative_to(src).as_posix()
        if rel not in expected_paths:
            untracked.append(rel)
if untracked:
    raise SystemExit("candidate checkout has untracked files: " + "; ".join(sorted(untracked)))
PY

python3 - "$src" "$expected_tree" "$dst" <<'PY'
import os
import stat
import subprocess
import sys
from pathlib import Path

src = Path(sys.argv[1])
tree = sys.argv[2]
dst = Path(sys.argv[3])
entries = subprocess.check_output(
    ["git", "-c", "safe.directory=*", "-c", "core.fsmonitor=false", "-C", str(src), "ls-tree", "-r", "-z", "--full-tree", tree]
).split(b"\0")
for entry in entries:
    if not entry:
        continue
    meta, raw_path = entry.split(b"\t", 1)
    mode, kind, oid = meta.decode("ascii").split(" ")
    if kind != "blob":
        raise SystemExit(f"unsupported tree entry kind {kind} for {raw_path!r}")
    path_text = raw_path.decode("utf-8", errors="surrogateescape")
    target = dst / path_text
    target.parent.mkdir(parents=True, exist_ok=True)
    data = subprocess.check_output(["git", "-C", str(src), "cat-file", "blob", oid])
    if mode == "120000":
        os.symlink(data.decode("utf-8", errors="surrogateescape"), target)
    else:
        target.write_bytes(data)
        if mode == "100755":
            target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
PY

git -c init.defaultBranch=qa-candidate init --quiet "$dst"
git -C "$dst" config --local core.fsmonitor false
git -C "$dst" config --local core.hooksPath /dev/null
git -C "$dst" add -A -f
actual_tree=$(git -C "$dst" write-tree)
[ "$actual_tree" = "$expected_tree" ] || { echo "neutral export tree $actual_tree does not match expected tree $expected_tree" >&2; exit 18; }

git -c safe.directory=* -c core.fsmonitor=false -C "$src" cat-file commit "$sha" > /tmp/candidate.commit
imported_sha=$(git -C "$dst" hash-object -t commit -w /tmp/candidate.commit)
[ "$imported_sha" = "$sha" ] || { echo "imported commit $imported_sha does not match requested $sha" >&2; exit 19; }
git -C "$dst" update-ref refs/heads/qa-candidate "$sha"
git -C "$dst" symbolic-ref HEAD refs/heads/qa-candidate
git -C "$dst" reset --hard --quiet "$sha"

private_status=$(git -C "$dst" status --porcelain=v1 --untracked-files=all)
[ -z "$private_status" ] || { echo "private checkout is dirty after reset" >&2; printf '%s\n' "$private_status" >&2; exit 20; }
printf '%s\n' "$expected_tree"
'''

    cmd: List[str] = [
        bwrap,
        "--die-with-parent",
        "--unshare-user",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--unshare-net",
        "--ro-bind", "/usr", "/usr",
        "--symlink", "usr/bin", "/bin",
        "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib64", "/lib64",
        "--ro-bind", "/etc", "/etc",
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",
        "--dir", "/tmp/home",
        "--setenv", "HOME", "/tmp/home",
        "--setenv", "GIT_TERMINAL_PROMPT", "0",
        "--unsetenv", "GH_TOKEN",
        "--unsetenv", "GITHUB_TOKEN",
        "--unsetenv", "SSH_AUTH_SOCK",
        "--unsetenv", "GIT_ASKPASS",
        "--unsetenv", "SSH_ASKPASS",
    ]
    cmd.extend(_mkdir_mount_parents(source))
    cmd.extend(["--ro-bind", str(source), str(source)])
    for metadata in _candidate_git_metadata_ro_mounts(source):
        if metadata.exists():
            cmd.extend(_mkdir_mount_parents(metadata))
            cmd.extend(["--ro-bind", str(metadata), str(metadata)])
    cmd.extend(_mkdir_mount_parents(destination_parent))
    cmd.extend(["--bind", str(destination_parent), str(destination_parent)])
    cmd.extend(["--chdir", str(source), "--", "/bin/sh", "-eu", "-c", script, "bootstrap-materialize", str(source), candidate_sha, str(destination_parent)])
    return cmd


def materialize_candidate_checkout(candidate_dir: Path, candidate_sha: str, parent_dir: Path) -> Tuple[Path, str]:
    """Create a private checkout of candidate_sha and verify its tree.

    Authoritative QA inspects a freshly materialized checkout, not the caller's
    mutable worktree. No host-authority Git command is executed against the
    candidate-controlled source repository: all source Git access occurs inside
    a credential-free, network-free bubblewrap bootstrap sandbox with the source
    and Git metadata mounted read-only and only the private destination writable.
    """
    if not re_full_sha(candidate_sha):
        raise RuntimeError("candidate SHA must be a full lowercase SHA-1")

    parent_dir.mkdir(parents=True, exist_ok=True)
    private_dir = parent_dir / "candidate-checkout"
    if private_dir.exists():
        raise RuntimeError(f"private candidate checkout path already exists: {private_dir}")

    command = _build_bootstrap_bwrap_command(candidate_dir, parent_dir, candidate_sha)
    result = subprocess.run(command, capture_output=True, text=True, env=_clean_env(), timeout=120)
    if result.returncode != 0:
        detail = (result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}")
        raise RuntimeError(f"private candidate bootstrap failed: {detail}")
    expected_tree = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    if not re_full_sha(expected_tree):
        raise RuntimeError(f"private candidate bootstrap did not return a tree oid: {result.stdout.strip()}")

    private_ok, private_error, private_tree = validate_candidate_checkout(private_dir, candidate_sha)
    if not private_ok:
        raise RuntimeError(f"private candidate checkout validation failed: {private_error}")
    if private_tree != expected_tree:
        raise RuntimeError(f"private candidate tree {private_tree} does not match expected tree {expected_tree}")

    return private_dir, private_tree


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


def build_bwrap_command(
    inner_argv: List[str],
    *,
    candidate_dir: Optional[Path],
    prompt_fd: int,
    cwd: Optional[Path],
    pi_config_fd: int,
) -> List[str]:
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
        "--dir", str(PI_CONFIG_MOUNT),
        "--setenv", "HOME", "/tmp/home",
        "--setenv", "PI_CODING_AGENT_DIR", str(PI_CONFIG_MOUNT),
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

    # bwrap copies held descriptors into private read-only files, eliminating
    # path lookup between validation and use.
    cmd.extend(["--perms", "0400", "--ro-bind-data", str(prompt_fd), "/tmp/prompt.md"])
    cmd.extend(["--perms", "0400", "--ro-bind-data", str(pi_config_fd), str(PI_CONFIG_MOUNT / "models.json")])

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
    supplied = scoped_credentials or {}
    if set(supplied) - PROVIDER_CREDENTIAL_ENV_NAMES:
        raise RuntimeError("direct provider credential is forbidden")
    for name, value in supplied.items():
        env[name] = value
    return env


def _pi_models_config(model_ref: Dict[str, str]) -> Dict[str, Any]:
    if model_ref.get("endpoint_path") != "/v1/responses":
        raise ModelRoutingError("Pi authoritative QA requires the canonical Responses endpoint")
    base_url = model_ref["base_url"].rstrip("/") + "/v1"
    token_env = model_ref["token_env"]
    return {
        "providers": {
            model_ref["endpoint_id"]: {
                "api": "openai-responses",
                "apiKey": f"${token_env}",
                "authHeader": True,
                "baseUrl": base_url,
                "models": [{
                    "id": model_ref["upstream_model_id"],
                    "name": model_ref["model_id"],
                    "reasoning": True,
                    "thinkingLevelMap": {
                        "off": None,
                        "minimal": None,
                        "low": None,
                        "medium": None,
                        "high": "high",
                        "xhigh": None,
                    },
                }],
            },
        },
    }


@dataclass(frozen=True)
class _RoutedRunResult:
    process: subprocess.CompletedProcess[str]
    inner_argv: List[str]
    route_evidence: Dict[str, Any]
    invoked_model_ref: Dict[str, str]
    invoked_model_name: str
    final_assistant_text: str
    model_config_sha256: str
    operation: str
    operation_contract: Dict[str, Any]
    attempt_accounting: List[Dict[str, Any]]


@dataclass(frozen=True)
class _RoutedPiLifecycleResult:
    probe_record: Optional[Dict[str, Any]]
    execution_record: Dict[str, Any]
    stdout: str
    stderr: str


class _RoutedOperationFailure(ModelRoutingError):
    def __init__(self, message: str, evidence: Dict[str, Any]) -> None:
        super().__init__(message)
        self.evidence = evidence


class _RoutedPiTerminalFailure(ModelRoutingError):
    def __init__(self, message: str, record: Dict[str, Any]) -> None:
        super().__init__(message)
        self.record = record


@dataclass
class _OperationAttemptAccounting:
    operation: str
    decision_id: str
    maximum_invocations: int
    invocation_count: int = 0
    outcome_count: int = 0

    def record_invocation(self) -> None:
        self.invocation_count += 1
        if self.invocation_count > self.maximum_invocations:
            raise ModelRoutingError("routed Pi decision exceeded its invocation contract")

    def record_outcome(self) -> None:
        self.outcome_count += 1
        if self.outcome_count > 1:
            raise ModelRoutingError("routed Pi decision reported more than one outcome")

    def evidence(self) -> Dict[str, Any]:
        if self.invocation_count > self.maximum_invocations or self.outcome_count != 1:
            raise ModelRoutingError("routed Pi attempt accounting is incomplete")
        return {
            "operation": self.operation,
            "decision_id": self.decision_id,
            "invocation_count": self.invocation_count,
            "outcome_count": self.outcome_count,
        }

    def terminal_evidence(self) -> Dict[str, Any]:
        if self.invocation_count > self.maximum_invocations or self.outcome_count > 1:
            raise ModelRoutingError("routed Pi terminal attempt accounting is invalid")
        return {
            "operation": self.operation,
            "decision_id": self.decision_id,
            "invocation_count": self.invocation_count,
            "outcome_count": self.outcome_count,
        }


def _authoritative_qa_pi_contract(policy: Dict[str, Any]) -> Dict[str, Any]:
    contracts = policy.get("execution_contracts")
    contract = contracts.get("authoritative_qa_pi") if isinstance(contracts, dict) else None
    if not _strict_json_equal(contract, AUTHORITATIVE_QA_PI_CONTRACT):
        raise ModelRoutingError("authoritative QA Pi execution contract is invalid")
    return {**contract, "operations": list(contract["operations"])}


def _validate_terminal_failure_record(record: Dict[str, Any]) -> None:
    schema = load_json_strict(GOVERNANCE_DIR / "schemas" / "pi-terminal-failure-record.schema.json")
    errors = validate_schema(record, schema)
    if errors:
        raise ModelRoutingError(f"protected Pi terminal failure record is invalid: {errors[0]}")
    binding = record["candidate_binding"]
    if record["role"] == "qa" and not all(re_full_sha(binding[field]) for field in binding):
        raise ModelRoutingError("protected QA terminal failure candidate binding is incomplete")

    attempts = record["route_attempts"]
    accounting = record["attempt_accounting"]
    policy = load_policy()
    if len(attempts) != len(accounting):
        raise ModelRoutingError("protected Pi terminal failure attempts and accounting disagree")
    if [attempt["order"] for attempt in attempts] != list(range(1, len(attempts) + 1)):
        raise ModelRoutingError("protected Pi terminal failure route order is invalid")
    expected_models = [STANDARD_MODELS[1], STANDARD_MODELS[0], STANDARD_MODELS[2]][:len(attempts)]
    if [attempt["decision"].get("model") for attempt in attempts] != expected_models:
        raise ModelRoutingError("protected Pi terminal failure model order is invalid")
    decision_ids: set[str] = set()
    excluded_models: set[str] = set()
    for attempt, counted in zip(attempts, accounting):
        decision = attempt["decision"]
        try:
            decision = validate_decision(decision, policy, excluded_models)
        except Exception as error:
            raise ModelRoutingError("protected Pi terminal failure route decision is invalid") from error
        decision_id = decision["decision_id"]
        if not isinstance(decision_id, str) or decision_id in decision_ids:
            raise ModelRoutingError("protected Pi terminal failure decision identity is invalid")
        decision_ids.add(decision_id)
        if (
            counted["operation"] != record["failed_operation"]
            or counted["decision_id"] != decision_id
            or counted["invocation_count"] != attempt["invocation_count"]
            or counted["outcome_count"] != (1 if attempt["outcome_report_state"] == "recorded" else 0)
            or (attempt["invocation_outcome"] == "success" and attempt["invocation_count"] != 1)
        ):
            raise ModelRoutingError("protected Pi terminal failure attempt accounting is inconsistent")
        excluded_models.add(decision["model"])
    final_attempt = attempts[-1]
    if record["failure_kind"] == "all-candidates-failed":
        if len(attempts) != len(STANDARD_MODELS) or any(
            attempt["invocation_outcome"] != "failure" or attempt["outcome_report_state"] != "recorded"
            for attempt in attempts
        ):
            raise ModelRoutingError("protected Pi exhausted-candidate evidence is inconsistent")
    elif final_attempt["outcome_report_state"] != "failed":
        raise ModelRoutingError("protected Pi outcome-reporting failure evidence is inconsistent")
    elif any(
        attempt["invocation_outcome"] != "failure" or attempt["outcome_report_state"] != "recorded"
        for attempt in attempts[:-1]
    ):
        raise ModelRoutingError("protected Pi pre-terminal route evidence is inconsistent")

    probe = record["successful_probe_record"]
    probe_hash = record["successful_probe_record_sha256"]
    if probe is None:
        if probe_hash != "" or record["failed_operation"] != "readiness_probe":
            raise ModelRoutingError("protected Pi terminal failure probe binding is inconsistent")
    elif (
        record["failed_operation"] != "execution"
        or probe.get("operation") != "readiness_probe"
        or probe_hash != canonical_json_sha256(probe)
    ):
        raise ModelRoutingError("protected Pi successful probe evidence is inconsistent")
    else:
        probe_schema = load_json_strict(GOVERNANCE_DIR / "schemas" / "qa-probe-record.schema.json")
        probe_errors = validate_schema(probe, probe_schema)
        if probe_errors:
            raise ModelRoutingError(f"protected Pi successful probe record is invalid: {probe_errors[0]}")
        binding = record["candidate_binding"]
        if (
            probe["run_id"] != record["run_id"]
            or probe["role"] != record["role"]
            or probe["role_run_id"] != record["role_run_id"]
            or probe["qa_for_pass_id"] != record["qa_for_pass_id"]
            or probe["candidate_sha"] != binding["candidate_sha"]
            or probe["base_sha"] != binding["base_sha"]
            or probe["candidate_tree_oid"] != binding["candidate_tree_oid"]
        ):
            raise ModelRoutingError("protected Pi successful probe candidate binding is inconsistent")
        route_errors = validate_route_evidence(probe["route_evidence"], "authoritative_qa")
        if route_errors:
            raise ModelRoutingError(f"protected Pi successful probe route evidence is invalid: {route_errors[0]}")


def _terminal_failure_record(
    *,
    failure: _RoutedOperationFailure,
    role: str,
    run_id: str,
    role_run_id: str,
    qa_for_pass_id: Optional[str],
    candidate_sha: str,
    base_sha: str,
    candidate_tree_oid: str,
    successful_probe_record: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    record = {
        "schema_version": "1",
        "record_id": str(uuid.uuid4()),
        "run_id": run_id,
        "role": role,
        "role_run_id": role_run_id,
        "qa_for_pass_id": qa_for_pass_id or "",
        "evidence_class": "terminal-failure",
        "generated_by": {
            "policy_commit_sha": get_policy_sha(),
            "dispatcher_path": "scripts/governance/run_isolated_pi.py",
            "dispatcher_sha256": sha256_file(Path(__file__).resolve()),
        },
        "candidate_binding": {
            "candidate_sha": candidate_sha,
            "base_sha": base_sha,
            "candidate_tree_oid": candidate_tree_oid,
        },
        **failure.evidence,
        "successful_probe_record": successful_probe_record,
        "successful_probe_record_sha256": (
            canonical_json_sha256(successful_probe_record) if successful_probe_record is not None else ""
        ),
        "finished_at": _now(),
    }
    _validate_terminal_failure_record(record)
    return record


def parse_pi_jsonl_final_assistant(stdout: str) -> str:
    """Validate Pi 0.80.3 JSON events and return its sole final answer."""
    events: List[Dict[str, Any]] = []
    for line_number, line in enumerate(stdout.splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = strict_json(line)
        except ModelRoutingError as error:
            raise ModelRoutingError(f"Pi JSONL line {line_number} is malformed") from error
        if not isinstance(event, dict):
            raise ModelRoutingError(f"Pi JSONL line {line_number} is not an event object")
        event_type = event.get("type")
        if not isinstance(event_type, str) or event_type not in PI_JSONL_EVENT_TYPES:
            raise ModelRoutingError(f"Pi JSONL line {line_number} has an unknown event type")
        if event_type.startswith("tool_execution_"):
            raise ModelRoutingError("Pi emitted a tool event while tools were disabled")
        events.append(event)
    if not events or events[-1].get("type") != "agent_end":
        raise ModelRoutingError("Pi JSONL did not end with agent_end")

    agent_ends = [event for event in events if event.get("type") == "agent_end"]
    if len(agent_ends) != 1 or agent_ends[0].get("willRetry") is not False:
        raise ModelRoutingError("Pi JSONL has an ambiguous or retrying agent_end")
    messages = agent_ends[0].get("messages")
    if not isinstance(messages, list):
        raise ModelRoutingError("Pi agent_end messages are invalid")
    final_assistants = [message for message in messages if isinstance(message, dict) and message.get("role") == "assistant"]
    ended_assistants = [
        event.get("message") for event in events
        if event.get("type") == "message_end"
        and isinstance(event.get("message"), dict)
        and event["message"].get("role") == "assistant"
    ]
    if len(final_assistants) != 1 or len(ended_assistants) != 1:
        raise ModelRoutingError("Pi JSONL does not contain exactly one final assistant message")
    if canonical_json(final_assistants[0]) != canonical_json(ended_assistants[0]):
        raise ModelRoutingError("Pi message_end and agent_end assistant messages disagree")

    message = final_assistants[0]
    if message.get("stopReason") != "stop":
        raise ModelRoutingError("Pi final assistant message did not stop successfully")
    content = message.get("content")
    if not isinstance(content, list):
        raise ModelRoutingError("Pi final assistant content is invalid")
    texts: List[str] = []
    for part in content:
        if not isinstance(part, dict) or part.get("type") not in {"text", "thinking"}:
            raise ModelRoutingError("Pi final assistant content contains an unknown relevant part")
        if part["type"] == "text":
            text = part.get("text")
            if not isinstance(text, str) or not text:
                raise ModelRoutingError("Pi final assistant text is invalid")
            texts.append(text)
    if len(texts) != 1:
        raise ModelRoutingError("Pi final assistant text is missing or ambiguous")
    return texts[0]


def _claim_decision_id(claim_dir: Path, decision_id: str) -> None:
    """Atomically claim a router decision across dispatcher processes."""
    if not re.fullmatch(r"d-\d{8}-\d{6}", decision_id):
        raise ModelRoutingError("genus-router decision_id is unsafe for a replay claim")
    claim_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory_stat = claim_dir.lstat()
    if claim_dir.is_symlink() or directory_stat.st_uid != os.getuid():
        raise ModelRoutingError("decision claim directory is not privately owned")
    claim_dir.chmod(0o700)
    directory_fd = os.open(claim_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            claim_fd = os.open(
                decision_id,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory_fd,
            )
        except FileExistsError as error:
            raise ModelRoutingError("genus-router decision_id was replayed across Pi invocations") from error
        else:
            try:
                os.fsync(claim_fd)
            finally:
                os.close(claim_fd)
            os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _claim_authority_decision_id(decision_id: str) -> None:
    _claim_decision_id(PI_DECISION_CLAIM_DIR, decision_id)


def _make_routed_pi_lifecycle():
    def route_operation(
        *,
        operation: str,
        name: str,
        tools: List[str],
        candidate_dir: Optional[Path],
        prompt_text: str,
        cwd: Optional[Path],
        timeout: int,
        expected_response: Optional[str],
    ) -> _RoutedRunResult:
        policy = load_policy()
        operation_contract = _authoritative_qa_pi_contract(policy)
        if operation not in operation_contract["operations"]:
            raise ModelRoutingError("routed Pi operation is outside its execution contract")
        classification = dict(policy["tasks"]["authoritative_qa"])
        service = create_router_service()
        excluded: List[str] = []
        attempts: List[Dict[str, Any]] = []
        terminal_attempts: List[Dict[str, Any]] = []
        attempt_accounting: List[Dict[str, Any]] = []
        operation_started_at = _now()

        def terminal_failure(kind: str, message: str) -> _RoutedOperationFailure:
            return _RoutedOperationFailure(message, {
                "failed_operation": operation,
                "failure_kind": kind,
                "operation_contract": operation_contract,
                "attempt_accounting": list(attempt_accounting),
                "route_attempts": list(terminal_attempts),
                "started_at": operation_started_at,
            })

        for _ in range(3):
            route_input = {
                **classification,
                "prior_failure": bool(excluded),
                "exclude_models": list(excluded),
                "task_summary": f"Immutable noetic-dev authoritative QA Pi {operation}",
            }
            raw_decision = asyncio.run(service.route_task(route_input))
            decision_id = raw_decision.get("decision_id") if isinstance(raw_decision, dict) else None
            try:
                decision = validate_decision(raw_decision, policy, set(excluded))
                _claim_authority_decision_id(decision["decision_id"])
            except Exception as error:
                if isinstance(decision_id, str) and decision_id:
                    _report_outcome(
                        service,
                        decision_id,
                        "failure",
                        f"{type(error).__name__}: routed Pi {operation} decision rejected",
                    )
                raise

            accounting = _OperationAttemptAccounting(
                operation=operation,
                decision_id=decision["decision_id"],
                maximum_invocations=operation_contract["maximum_invocations_per_decision"],
            )

            try:
                api_key = load_litellm_key(policy)
                model_ref = dict(decision["model_ref"])
                model_name = f"{model_ref['endpoint_id']}/{model_ref['upstream_model_id']}"
                config_text = canonical_json(_pi_models_config(model_ref))
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
                    "--name", name,
                    "--model", model_name,
                    "--thinking", "high",
                ]
                if tools:
                    inner_argv.extend(["--tools", ",".join(tools)])
                else:
                    inner_argv.append("--no-tools")
                inner_argv.append("@/tmp/prompt.md")
                with tempfile.TemporaryFile() as prompt_handle, tempfile.TemporaryFile() as config_handle:
                    prompt_handle.write(prompt_text.encode("utf-8"))
                    prompt_handle.flush()
                    prompt_handle.seek(0)
                    config_handle.write(config_text.encode("utf-8"))
                    config_handle.flush()
                    config_handle.seek(0)
                    prompt_fd = prompt_handle.fileno()
                    config_fd = config_handle.fileno()
                    bwrap_argv = build_bwrap_command(
                        inner_argv,
                        candidate_dir=candidate_dir,
                        prompt_fd=prompt_fd,
                        cwd=cwd,
                        pi_config_fd=config_fd,
                    )
                    accounting.record_invocation()
                    result = subprocess.run(
                        bwrap_argv,
                        capture_output=True,
                        text=True,
                        env=_clean_env({"LITELLM_API_KEY": api_key}),
                        pass_fds=(prompt_fd, config_fd),
                        timeout=timeout,
                    )
                if api_key in bwrap_argv or api_key in result.stdout or api_key in result.stderr:
                    raise RuntimeError("routed Pi credential leakage detected; output discarded")
                if result.returncode != 0:
                    raise RuntimeError(f"routed Pi exited with status {result.returncode}")
                final_text = parse_pi_jsonl_final_assistant(result.stdout)
                if expected_response is not None and final_text != expected_response:
                    raise RuntimeError("routed Pi final assistant response failed its exact contract")

                success_attempt = {
                    "decision": decision,
                    "outcome": "success",
                    "outcome_recorded": True,
                    "reasoning_effort": "high",
                }
                route_evidence = {
                    "schema_version": "1",
                    "classification": classification,
                    "attempts": [*attempts, success_attempt],
                }
                errors = validate_route_evidence(route_evidence, "authoritative_qa")
                if errors:
                    raise ModelRoutingError(f"protected Pi route evidence is invalid: {errors[0]}")
            except Exception as error:
                failed_attempt = {
                    "decision": decision,
                    "outcome": "failure",
                    "outcome_recorded": True,
                    "reasoning_effort": "high",
                }
                terminal_attempt = {
                    "order": len(terminal_attempts) + 1,
                    "decision": decision,
                    "invocation_count": accounting.invocation_count,
                    "invocation_outcome": "failure",
                    "outcome_report_state": "recorded",
                    "failure_type": type(error).__name__,
                }
                try:
                    _report_outcome(
                        service,
                        decision["decision_id"],
                        "failure",
                        f"{type(error).__name__}: routed Pi {operation} failed",
                    )
                except Exception as report_error:
                    terminal_attempt["outcome_report_state"] = "failed"
                    terminal_attempts.append(terminal_attempt)
                    attempt_accounting.append(accounting.terminal_evidence())
                    raise terminal_failure(
                        "outcome-reporting-failed",
                        f"routed Pi {operation} outcome reporting failed",
                    ) from report_error
                accounting.record_outcome()
                attempts.append(failed_attempt)
                terminal_attempts.append(terminal_attempt)
                attempt_accounting.append(accounting.evidence())
                excluded.append(decision["model"])
                continue

            try:
                _report_outcome(service, decision["decision_id"], "success", f"Routed Pi {operation} passed its contract")
            except Exception as report_error:
                terminal_attempts.append({
                    "order": len(terminal_attempts) + 1,
                    "decision": decision,
                    "invocation_count": accounting.invocation_count,
                    "invocation_outcome": "success",
                    "outcome_report_state": "failed",
                    "failure_type": type(report_error).__name__,
                })
                attempt_accounting.append(accounting.terminal_evidence())
                raise terminal_failure(
                    "outcome-reporting-failed",
                    f"routed Pi {operation} outcome reporting failed",
                ) from report_error
            accounting.record_outcome()
            attempt_accounting.append(accounting.evidence())
            return _RoutedRunResult(
                process=result,
                inner_argv=inner_argv,
                route_evidence=route_evidence,
                invoked_model_ref=model_ref,
                invoked_model_name=model_name,
                final_assistant_text=final_text,
                model_config_sha256=sha256_text(config_text),
                operation=operation,
                operation_contract=operation_contract,
                attempt_accounting=attempt_accounting,
            )
        raise terminal_failure(
            "all-candidates-failed",
            f"all routed Pi {operation} candidates failed",
        )

    def lifecycle(
        *,
        role: str,
        run_id: str,
        role_run_id: str,
        tools: List[str],
        prompt_file: Path,
        candidate_dir: Optional[Path],
        qa_for_pass_id: Optional[str],
        candidate_sha: str,
        base_sha: str,
        candidate_tree_oid: str,
        timeout: int,
        perform_probe: bool = False,
    ) -> _RoutedPiLifecycleResult:
        _require_validated_identity(role, qa_for_pass_id)
        _require_validated_tools(role, tools)
        try:
            prompt_text = prompt_file.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeError) as error:
            raise RuntimeError("Pi execution prompt is unavailable or not UTF-8") from error
        if not prompt_text:
            raise RuntimeError("Pi execution prompt must not be empty")

        probe_record: Optional[Dict[str, Any]] = None
        if perform_probe or role == "qa":
            nonce = uuid.uuid4().hex[:16]
            probe_prompt = f"Respond with exactly 'READY {nonce}' and nothing else."
            expected = f"READY {nonce}"
            probe_start = _now()
            try:
                probe = route_operation(
                    operation="readiness_probe",
                    name=f"probe-{role_run_id}",
                    tools=tools,
                    candidate_dir=candidate_dir,
                    prompt_text=probe_prompt,
                    cwd=candidate_dir,
                    timeout=min(timeout, 120),
                    expected_response=expected,
                )
            except _RoutedOperationFailure as failure:
                record = _terminal_failure_record(
                    failure=failure,
                    role=role,
                    run_id=run_id,
                    role_run_id=role_run_id,
                    qa_for_pass_id=qa_for_pass_id,
                    candidate_sha=candidate_sha,
                    base_sha=base_sha,
                    candidate_tree_oid=candidate_tree_oid,
                    successful_probe_record=None,
                )
                raise _RoutedPiTerminalFailure(str(failure), record) from failure
            probe_finish = _now()
            probe_record = {
                "schema_version": "2",
                "probe_id": f"probe-{uuid.uuid4().hex[:12]}",
                "run_id": run_id,
                "role": role,
                "role_run_id": role_run_id,
                "qa_for_pass_id": qa_for_pass_id or "",
                "authority_process": "fresh-isolated-worker",
                "authority_worker_pid": os.getpid(),
                **_base_invocation_fields(
                    routed=probe,
                    tools=tools,
                    candidate_sha=candidate_sha,
                    base_sha=base_sha,
                    candidate_tree_oid=candidate_tree_oid,
                ),
                "context_files_disabled": True,
                "extensions_disabled": True,
                "skills_disabled": True,
                "themes_disabled": True,
                "probe_argv": probe.inner_argv,
                "probe_argv_sha256": sha256_text(canonical_json(probe.inner_argv)),
                "probe_prompt_hash": sha256_text(probe_prompt),
                "probe_event_log_sha256": sha256_text(probe.process.stdout),
                "final_assistant_text_sha256": sha256_text(probe.final_assistant_text),
                "model_config_sha256": probe.model_config_sha256,
                "model_config_delivery": "inherited-fd-copy",
                "nonce": nonce,
                "expected_response": expected,
                "observed_response": probe.final_assistant_text,
                "exit_code": probe.process.returncode,
                "stdout_sha256": sha256_text(probe.process.stdout),
                "stderr_sha256": sha256_text(probe.process.stderr),
                "started_at": probe_start,
                "finished_at": probe_finish,
            }

        if role == "qa" and candidate_dir is not None:
            mount_ok, mount_error, mount_tree = validate_candidate_checkout(candidate_dir, candidate_sha)
            if not mount_ok or mount_tree != candidate_tree_oid:
                raise RuntimeError(f"private candidate changed between probe and execution: {mount_error or mount_tree}")

        candidate_tree_before = get_candidate_tree_oid(candidate_dir) if candidate_dir else ""
        start = _now()
        try:
            routed = route_operation(
                operation="execution",
                name=f"{role}-{role_run_id}",
                tools=tools,
                candidate_dir=candidate_dir,
                prompt_text=prompt_text,
                cwd=candidate_dir,
                timeout=timeout,
                expected_response=None,
            )
        except _RoutedOperationFailure as failure:
            record = _terminal_failure_record(
                failure=failure,
                role=role,
                run_id=run_id,
                role_run_id=role_run_id,
                qa_for_pass_id=qa_for_pass_id,
                candidate_sha=candidate_sha,
                base_sha=base_sha,
                candidate_tree_oid=candidate_tree_oid,
                successful_probe_record=probe_record,
            )
            raise _RoutedPiTerminalFailure(str(failure), record) from failure
        finish = _now()
        candidate_tree_after = get_candidate_tree_oid(candidate_dir) if candidate_dir else ""
        base_fields = _base_invocation_fields(
            routed=routed,
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
            "write_tools_observed": _write_tools_observed(routed.process.stdout),
        }
        execution_record = {
            "schema_version": "2",
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
                "authority_process": "fresh-isolated-worker",
                "authority_worker_pid": os.getpid(),
                "argv": routed.inner_argv,
                "argv_sha256": sha256_text(canonical_json(routed.inner_argv)),
                "prompt_text": prompt_text,
                "prompt_sha256": sha256_text(prompt_text),
                "final_assistant_text": routed.final_assistant_text,
                "final_assistant_text_sha256": sha256_text(routed.final_assistant_text),
                "qa_event_log": routed.process.stdout,
                "model_config_sha256": routed.model_config_sha256,
                "model_config_delivery": "inherited-fd-copy",
                "environment_values_recorded": False,
                "credential_interface": _credential_interface({"LITELLM_API_KEY": ""}, tools, role),
                "started_at": start,
                "finished_at": finish,
                "exit_code": routed.process.returncode,
                "stdout_sha256": sha256_text(routed.process.stdout),
                "stderr_sha256": sha256_text(routed.process.stderr),
                "qa_event_log_sha256": sha256_text(routed.process.stdout),
                "isolation": isolation,
            },
        }
        return _RoutedPiLifecycleResult(
            probe_record=probe_record,
            execution_record=execution_record,
            stdout=routed.process.stdout,
            stderr=routed.process.stderr,
        )

    return lifecycle


_WORKER_MODE = __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--routed-worker"
if _WORKER_MODE:
    _worker_lifecycle = _make_routed_pi_lifecycle()
del _make_routed_pi_lifecycle


def _worker_env() -> Dict[str, str]:
    env = _clean_env()
    for name in ("GENUS_ROUTER_CONFIG", "LITELLM_API_KEY", "LITELLM_API_KEY_FILE", "CREDENTIALS_DIRECTORY"):
        value = os.environ.get(name)
        if value:
            env[name] = value
    return env


def run_routed_pi_lifecycle(
    *,
    role: str,
    run_id: str,
    role_run_id: str,
    tools: List[str],
    prompt_file: Path,
    candidate_dir: Optional[Path],
    qa_for_pass_id: Optional[str],
    candidate_sha: str,
    base_sha: str,
    candidate_tree_oid: str,
    timeout: int,
    perform_probe: bool = False,
) -> _RoutedPiLifecycleResult:
    """Run the authority-bearing lifecycle in a fresh isolated interpreter."""
    if type(timeout) is not int or not 1 <= timeout <= MAX_ROUTED_PI_TIMEOUT:
        raise RuntimeError(f"routed Pi timeout must be an integer from 1 to {MAX_ROUTED_PI_TIMEOUT}")
    request = {
        "role": role,
        "run_id": run_id,
        "role_run_id": role_run_id,
        "tools": tools,
        "prompt_file": str(prompt_file.resolve()),
        "candidate_dir": str(candidate_dir.resolve()) if candidate_dir else None,
        "qa_for_pass_id": qa_for_pass_id,
        "candidate_sha": candidate_sha,
        "base_sha": base_sha,
        "candidate_tree_oid": candidate_tree_oid,
        "timeout": timeout,
        "perform_probe": perform_probe,
    }
    with tempfile.TemporaryDirectory(prefix="pi-authority-worker-") as directory:
        root = Path(directory)
        request_path = root / "request.json"
        response_path = root / "response.json"
        request_path.write_text(canonical_json(request), encoding="utf-8")
        candidate_count = len(STANDARD_MODELS)
        probe_budget = min(timeout, 120) * candidate_count if role == "qa" or perform_probe else 0
        worker_timeout = timeout * candidate_count + probe_budget + 60
        try:
            result = subprocess.run(
                [sys.executable, "-I", str(Path(__file__).resolve()), "--routed-worker", str(request_path), str(response_path)],
                capture_output=True,
                text=True,
                env=_worker_env(),
                timeout=worker_timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise ModelRoutingError("fresh routed Pi authority worker timed out") from error
        if result.returncode != 0 or not response_path.is_file():
            raise ModelRoutingError("fresh routed Pi authority worker failed")
        response = load_json_strict(response_path)
    if not isinstance(response, dict) or response.get("status") not in {"success", "failure"}:
        raise ModelRoutingError("fresh routed Pi authority worker returned an invalid response")
    if response["status"] == "failure":
        if set(response) != {"status", "message", "terminal_failure_record"} or not isinstance(response["message"], str):
            raise ModelRoutingError("fresh routed Pi authority worker returned invalid terminal failure evidence")
        record = response["terminal_failure_record"]
        if not isinstance(record, dict):
            raise ModelRoutingError("fresh routed Pi authority worker returned invalid terminal failure evidence")
        _validate_terminal_failure_record(record)
        binding = record["candidate_binding"]
        if (
            record["run_id"] != run_id
            or record["role"] != role
            or record["role_run_id"] != role_run_id
            or record["qa_for_pass_id"] != (qa_for_pass_id or "")
            or binding["candidate_sha"] != candidate_sha
            or binding["base_sha"] != base_sha
            or binding["candidate_tree_oid"] != candidate_tree_oid
        ):
            raise ModelRoutingError("fresh routed Pi authority worker returned mismatched terminal failure evidence")
        raise _RoutedPiTerminalFailure(response["message"], record)
    if set(response) != {"status", "probe_record", "execution_record", "stdout", "stderr"}:
        raise ModelRoutingError("fresh routed Pi authority worker returned an invalid success response")
    if response["probe_record"] is not None and not isinstance(response["probe_record"], dict):
        raise ModelRoutingError("fresh routed Pi authority worker returned an invalid probe record")
    if not isinstance(response["execution_record"], dict) or not isinstance(response["stdout"], str) or not isinstance(response["stderr"], str):
        raise ModelRoutingError("fresh routed Pi authority worker returned invalid execution evidence")
    return _RoutedPiLifecycleResult(
        probe_record=response["probe_record"],
        execution_record=response["execution_record"],
        stdout=response["stdout"],
        stderr=response["stderr"],
    )


def _base_invocation_fields(
    *,
    routed: _RoutedRunResult,
    tools: List[str],
    candidate_sha: str,
    base_sha: str,
    candidate_tree_oid: str,
) -> Dict[str, Any]:
    return {
        "operation": routed.operation,
        "operation_contract": routed.operation_contract,
        "attempt_accounting": routed.attempt_accounting,
        "route_evidence": routed.route_evidence,
        "invoked_model_ref": routed.invoked_model_ref,
        "reasoning_effort": "high",
        "resolved_model": routed.invoked_model_name,
        "pi_version": get_pi_version(),
        "tools": tools,
        "environment_name_allowlist": ENV_ALLOWLIST,
        "candidate_sha": candidate_sha,
        "base_sha": base_sha,
        "candidate_tree_oid": candidate_tree_oid,
        "policy_commit_sha": get_policy_sha(),
        "model_config_sha256": routed.model_config_sha256,
    }


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


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(data), encoding="utf-8")


def write_protected_record(record: Dict[str, Any], run_dir: Path) -> Path:
    record_dir = run_dir / "protected"
    record_dir.mkdir(parents=True, exist_ok=True)
    record_path = record_dir / "qa-execution-record.json"
    write_json(record_path, record)
    return record_path


def write_terminal_failure_record(record: Dict[str, Any], run_dir: Path) -> Path:
    _validate_terminal_failure_record(record)
    record_dir = run_dir / "protected"
    record_dir.mkdir(parents=True, exist_ok=True)
    record_path = record_dir / "pi-terminal-failure-record.json"
    write_json(record_path, record)
    sha_path = record_dir / "pi-terminal-failure-record.sha256"
    sha_path.write_text(sha256_file(record_path), encoding="utf-8")
    probe = record["successful_probe_record"]
    if probe is not None:
        write_json(record_dir / "qa-probe-record.json", probe)
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
    profile = load_profiles().get("profiles", {}).get(profile_key, {}) if profile_key else {}
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
            "resolved_model": args.model or "",
            "profile_id": profile_key,
            "profile_hash": canonical_json_sha256(profile),
            "pi_version": get_pi_version(),
            "tools": tools,
            "environment_name_allowlist": ENV_ALLOWLIST,
            "candidate_sha": args.candidate_sha,
            "base_sha": args.base_sha,
            "candidate_tree_oid": "",
            "policy_commit_sha": get_policy_sha(),
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
    parser.add_argument("--model", help="Deprecated historical model label for --record-only output")
    parser.add_argument("--tools", default="")
    parser.add_argument("--prompt", required=True, type=Path)
    parser.add_argument("--candidate-dir", type=Path)
    parser.add_argument("--qa-for-pass-id", default="")
    parser.add_argument("--candidate-sha", default="")
    parser.add_argument("--base-sha", default="")
    parser.add_argument("--record-only", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--credential-env", action="append", default=[], help=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output-dir", type=Path, default=Path(".governance/runs"))
    args = parser.parse_args()

    if not args.record_only and args.model:
        print("--model cannot authorize routed Pi execution; genus-router selects every real invocation", file=sys.stderr)
        return 1
    if args.credential_env:
        print("--credential-env is deprecated; routed Pi accepts only the policy-bound LiteLLM credential", file=sys.stderr)
        return 1

    profile_key = ""
    if args.record_only and args.model:
        valid, profile_key_or_error = validate_model(args.model, args.role)
        if not valid:
            print(f"Historical model validation failed: {profile_key_or_error}", file=sys.stderr)
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

    if not args.prompt.exists():
        print(f"Prompt file not found: {args.prompt}", file=sys.stderr)
        return 1

    run_dir = args.output_dir / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    if args.record_only:
        record = _non_evidence_record(args, profile_key, tools)
        path = run_dir / "non-evidence" / f"{args.role}-record-only.json"
        write_json(path, record)
        print(f"NON-EVIDENCE record-only output written to {path}", file=sys.stderr)
        return 0

    candidate_mount_dir = args.candidate_dir
    private_candidate_tmp: Optional[tempfile.TemporaryDirectory[str]] = None
    try:
        if args.role == "qa":
            private_candidate_tmp = tempfile.TemporaryDirectory(prefix="pi-candidate-")
            try:
                candidate_mount_dir, candidate_tree = materialize_candidate_checkout(args.candidate_dir, args.candidate_sha, Path(private_candidate_tmp.name))
            except RuntimeError as error:
                print(str(error), file=sys.stderr)
                return 1
        else:
            candidate_tree = get_candidate_tree_oid(candidate_mount_dir) if candidate_mount_dir else ""

        if args.role == "qa":
            mount_ok, mount_error, mount_tree = validate_candidate_checkout(candidate_mount_dir, args.candidate_sha)
            if not mount_ok:
                print(f"private candidate checkout changed before routed lifecycle: {mount_error}", file=sys.stderr)
                return 1
            if mount_tree != candidate_tree:
                print(f"private candidate tree {mount_tree} does not match expected tree {candidate_tree}", file=sys.stderr)
                return 1

        lifecycle = run_routed_pi_lifecycle(
            role=args.role,
            run_id=args.run_id,
            role_run_id=args.role_run_id,
            tools=tools,
            prompt_file=args.prompt,
            candidate_dir=candidate_mount_dir,
            qa_for_pass_id=args.qa_for_pass_id,
            candidate_sha=args.candidate_sha,
            base_sha=args.base_sha,
            candidate_tree_oid=candidate_tree,
            timeout=args.timeout,
            perform_probe=args.probe,
        )
        probe_record = lifecycle.probe_record
        if probe_record is not None:
            probe_path = run_dir / "protected" / "qa-probe-record.json" if args.role == "qa" else run_dir / "execution" / f"{args.role}-probe-record.json"
            write_json(probe_path, probe_record)
            print(f"Probe record written to {probe_path}", file=sys.stderr)
        execution_record = lifecycle.execution_record
        stdout = lifecycle.stdout
        stderr = lifecycle.stderr
        exit_code = execution_record["actual_invocation"]["exit_code"]
    except _RoutedPiTerminalFailure as error:
        record_path = write_terminal_failure_record(error.record, run_dir)
        print(str(error), file=sys.stderr)
        print(f"Protected Pi terminal failure record written to {record_path}", file=sys.stderr)
        return 1
    except (ModelRoutingError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        if private_candidate_tmp is not None:
            private_candidate_tmp.cleanup()

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
    if _WORKER_MODE:
        if len(sys.argv) != 4:
            raise SystemExit(2)
        try:
            worker_request = load_json_strict(Path(sys.argv[2]))
            required = {
                "role", "run_id", "role_run_id", "tools", "prompt_file", "candidate_dir",
                "qa_for_pass_id", "candidate_sha", "base_sha", "candidate_tree_oid", "timeout",
                "perform_probe",
            }
            if not isinstance(worker_request, dict) or set(worker_request) != required:
                raise RuntimeError("invalid authority worker request")
            worker_result = _worker_lifecycle(
                role=worker_request["role"],
                run_id=worker_request["run_id"],
                role_run_id=worker_request["role_run_id"],
                tools=worker_request["tools"],
                prompt_file=Path(worker_request["prompt_file"]),
                candidate_dir=Path(worker_request["candidate_dir"]) if worker_request["candidate_dir"] else None,
                qa_for_pass_id=worker_request["qa_for_pass_id"],
                candidate_sha=worker_request["candidate_sha"],
                base_sha=worker_request["base_sha"],
                candidate_tree_oid=worker_request["candidate_tree_oid"],
                timeout=worker_request["timeout"],
                perform_probe=worker_request["perform_probe"],
            )
            write_json(Path(sys.argv[3]), {
                "status": "success",
                "probe_record": worker_result.probe_record,
                "execution_record": worker_result.execution_record,
                "stdout": worker_result.stdout,
                "stderr": worker_result.stderr,
            })
        except _RoutedPiTerminalFailure as error:
            write_json(Path(sys.argv[3]), {
                "status": "failure",
                "message": str(error),
                "terminal_failure_record": error.record,
            })
        except Exception:
            raise SystemExit(1) from None
        raise SystemExit(0)
    raise SystemExit(main())
