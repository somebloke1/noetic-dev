#!/usr/bin/env python3
"""Protected compare-and-swap publisher for an exact dev-to-main promotion."""

from __future__ import annotations

import argparse
import os
import pwd
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_delivery_gate import (  # noqa: E402
    REPO_FULL_NAME,
    _trusted_root_executable,
    check_delivery,
    load_json,
)
from hash_tree import canonical_json, sha256_text  # noqa: E402

PROTECTED_PUBLISHER = Path("/usr/local/libexec/noetic-dev/promote-main")
GIT = "/usr/bin/git"
CANONICAL_REMOTE = f"git@github.com:{REPO_FULL_NAME}.git"
UNSAFE_LOCAL_CONFIG = (
    "core.sshcommand",
    "core.fsmonitor",
    "core.hookspath",
    "diff.external",
    "filter.",
    "credential.",
    "http.",
    "url.",
    "include.",
    "includeif.",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": pwd.getpwuid(os.getuid()).pw_dir,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_SSH_COMMAND": "/usr/bin/ssh -F /dev/null -oBatchMode=yes -oPermitLocalCommand=no -oProxyCommand=none",
        "SHELL": "/bin/sh",
    }
    if os.environ.get("SSH_AUTH_SOCK"):
        env["SSH_AUTH_SOCK"] = os.environ["SSH_AUTH_SOCK"]
    return subprocess.run(
        [GIT, *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _require_git(repo_root: Path, *args: str) -> str:
    result = _git(repo_root, *args)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _remote_heads(transfer_root: Path) -> Dict[str, str]:
    return {
        ref: _require_git(transfer_root, "rev-parse", ref)
        for ref in ("refs/heads/dev", "refs/heads/main")
    }


def _unsafe_local_config_keys(repo_root: Path) -> List[str]:
    raw = _require_git(
        repo_root,
        "config",
        "--local",
        "--no-includes",
        "--name-only",
        "--null",
        "--list",
    )
    keys = [key.lower() for key in raw.split("\0") if key]
    return [
        key
        for key in keys
        if key in UNSAFE_LOCAL_CONFIG
        or any(key.startswith(prefix) for prefix in UNSAFE_LOCAL_CONFIG if prefix.endswith("."))
        or (key.startswith("diff.") and key.endswith(".command"))
        or (
            key.startswith("remote.")
            and key.rsplit(".", 1)[-1] in {"uploadpack", "receivepack", "pushurl"}
        )
    ]


def promote(
    manifest: Dict[str, Any],
    external_evidence: Dict[str, Any],
    repo_root: Path,
    manifest_path: str | None = None,
) -> Dict[str, Any]:
    passed, errors, _gate_type = check_delivery(
        manifest,
        manifest_path,
        phase="pre-merge",
        external_evidence=external_evidence,
        gate_mode="main-promotion",
    )
    if not passed:
        raise RuntimeError("main-promotion readiness gate failed: " + "; ".join(errors))

    repo = manifest.get("repo", {})
    candidate_sha = repo.get("candidate_sha", "")
    old_main_sha = repo.get("base_sha", "")
    unsafe_config = _unsafe_local_config_keys(repo_root)
    if unsafe_config:
        raise RuntimeError(
            "publisher checkout has executable or transport-altering Git config: "
            + ", ".join(unsafe_config)
        )
    if _require_git(repo_root, "rev-parse", "HEAD") != candidate_sha:
        raise RuntimeError("publisher checkout HEAD is not the authorized dev SHA")
    index_flags = _require_git(repo_root, "ls-files", "-v")
    hidden = [
        line
        for line in index_flags.splitlines()
        if line and (line[0].islower() or line[0] == "S")
    ]
    if hidden:
        raise RuntimeError("publisher checkout has hidden index modifications")
    if _require_git(repo_root, "status", "--porcelain"):
        raise RuntimeError("publisher checkout is dirty")
    if _require_git(repo_root, "ls-files", "--others", "--ignored", "--exclude-standard"):
        raise RuntimeError("publisher checkout contains ignored untracked files")

    argv = [
        GIT,
        "push",
        "--porcelain",
        f"--force-with-lease=refs/heads/main:{old_main_sha}",
        CANONICAL_REMOTE,
        f"{candidate_sha}:refs/heads/main",
    ]
    with tempfile.TemporaryDirectory(prefix="noetic-main-promotion-") as transfer:
        transfer_root = Path(transfer)
        _require_git(transfer_root, "init", "--bare", ".")
        _require_git(
            transfer_root,
            "fetch",
            "--no-tags",
            CANONICAL_REMOTE,
            "+refs/heads/dev:refs/heads/dev",
            "+refs/heads/main:refs/heads/main",
        )
        heads = _remote_heads(transfer_root)
        if heads.get("refs/heads/dev") != candidate_sha:
            raise RuntimeError("remote dev is not the authorized SHA")
        if heads.get("refs/heads/main") != old_main_sha:
            raise RuntimeError("remote main changed after authorization")
        ancestry = _git(
            transfer_root, "merge-base", "--is-ancestor", old_main_sha, candidate_sha
        )
        if ancestry.returncode != 0 or old_main_sha == candidate_sha:
            raise RuntimeError("authorized dev is not strictly ahead of main")
        started_at = _now()
        result = _git(transfer_root, *argv[1:])
        finished_at = _now()
    if result.returncode != 0:
        raise RuntimeError("compare-and-swap promotion failed")
    return {
        "registry_id": "main.promote_exact",
        "publisher": str(PROTECTED_PUBLISHER),
        "authorized_dev_sha": candidate_sha,
        "expected_old_main_sha": old_main_sha,
        "git_argv": argv,
        "exit_code": result.returncode,
        "stdout_sha256": sha256_text(result.stdout),
        "stderr_sha256": sha256_text(result.stderr),
        "started_at": started_at,
        "finished_at": finished_at,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--external-evidence", required=True)
    args = parser.parse_args()
    if not _trusted_root_executable(PROTECTED_PUBLISHER):
        print("publisher is not installed as a trusted root-owned executable", file=sys.stderr)
        return 1
    try:
        manifest = load_json(args.manifest)
        external = load_json(args.external_evidence)
        record = promote(manifest, external, Path.cwd(), args.manifest)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"promotion blocked: {exc}", file=sys.stderr)
        return 1
    print(canonical_json(record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
