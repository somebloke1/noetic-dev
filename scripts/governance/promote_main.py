#!/usr/bin/env python3
"""Protected compare-and-swap publisher for an exact dev-to-main promotion."""

from __future__ import annotations

import argparse
import os
import pwd
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_delivery_gate import (  # noqa: E402
    REPO_FULL_NAME,
    _check_owner_promotion_authorization,
    _trusted_root_executable,
    load_json,
)
from hash_tree import canonical_json, sha256_text  # noqa: E402

PROTECTED_PUBLISHER = Path("/usr/local/libexec/noetic-dev/promote-main")
GIT = "/usr/bin/git"
ALLOWED_ORIGINS = {
    f"https://github.com/{REPO_FULL_NAME}.git",
    f"git@github.com:{REPO_FULL_NAME}.git",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": pwd.getpwuid(os.getuid()).pw_dir,
        "GIT_TERMINAL_PROMPT": "0",
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


def _remote_heads(repo_root: Path) -> Dict[str, str]:
    result = _git(
        repo_root,
        "ls-remote",
        "--refs",
        "origin",
        "refs/heads/dev",
        "refs/heads/main",
    )
    if result.returncode != 0:
        raise RuntimeError("cannot read authoritative remote heads")
    heads: Dict[str, str] = {}
    for line in result.stdout.splitlines():
        sha, ref = line.split("\t", 1)
        heads[ref] = sha
    return heads


def promote(
    manifest: Dict[str, Any],
    external_evidence: Dict[str, Any],
    repo_root: Path,
) -> Dict[str, Any]:
    errors: List[str] = []
    _check_owner_promotion_authorization(manifest, errors, external_evidence)
    if errors:
        raise RuntimeError("; ".join(errors))

    repo = manifest.get("repo", {})
    candidate_sha = repo.get("candidate_sha", "")
    old_main_sha = repo.get("base_sha", "")
    if _require_git(repo_root, "remote", "get-url", "origin") not in ALLOWED_ORIGINS:
        raise RuntimeError("origin is not the canonical repository")
    if _require_git(repo_root, "remote", "get-url", "--push", "--all", "origin") not in ALLOWED_ORIGINS:
        raise RuntimeError("origin push URL is not the canonical repository")
    if _require_git(repo_root, "rev-parse", "HEAD") != candidate_sha:
        raise RuntimeError("publisher checkout HEAD is not the authorized dev SHA")
    if _require_git(repo_root, "status", "--porcelain"):
        raise RuntimeError("publisher checkout is dirty")

    heads = _remote_heads(repo_root)
    if heads.get("refs/heads/dev") != candidate_sha:
        raise RuntimeError("remote dev is not the authorized SHA")
    if heads.get("refs/heads/main") != old_main_sha:
        raise RuntimeError("remote main changed after authorization")
    ancestry = _git(repo_root, "merge-base", "--is-ancestor", old_main_sha, candidate_sha)
    if ancestry.returncode != 0 or old_main_sha == candidate_sha:
        raise RuntimeError("authorized dev is not strictly ahead of main")

    argv = [
        GIT,
        "push",
        "--porcelain",
        f"--force-with-lease=refs/heads/main:{old_main_sha}",
        "origin",
        f"{candidate_sha}:refs/heads/main",
    ]
    started_at = _now()
    result = _git(repo_root, *argv[1:])
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
        record = promote(manifest, external, Path.cwd())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"promotion blocked: {exc}", file=sys.stderr)
        return 1
    print(canonical_json(record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
