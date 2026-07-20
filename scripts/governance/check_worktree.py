#!/usr/bin/env python3
"""Read-only validation of Git worktree administration and local config."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Iterable

TOPOLOGY_ENV = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_DIR",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_WORK_TREE",
}
SAFE_CONFIG = {
    "core.bare",
    "core.filemode",
    "core.ignorecase",
    "core.logallrefupdates",
    "core.precomposeunicode",
    "core.repositoryformatversion",
    "core.symlinks",
    "lfs.repositoryformatversion",
}


def isolated_git_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """Return a child environment that cannot inherit repository administration."""
    env = dict(os.environ if source is None else source)
    for name in list(env):
        if name.startswith("GIT_"):
            env.pop(name)
    env.update(
        {
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return env


def _read_gitfile(path: Path) -> Path | None:
    if not path.is_file() or path.is_symlink():
        return None
    try:
        value = path.read_text(encoding="utf-8", errors="strict").strip()
    except (OSError, UnicodeError):
        return None
    if not value.lower().startswith("gitdir:"):
        return None
    try:
        target = Path(value.split(":", 1)[1].strip())
        if not target.is_absolute():
            target = path.parent / target
        return target.resolve()
    except (OSError, ValueError):
        return None


def _common_dir(git_dir: Path, errors: list[str]) -> Path:
    commondir = git_dir / "commondir"
    if not commondir.exists():
        return git_dir
    if not commondir.is_file() or commondir.is_symlink():
        errors.append(f"linked worktree commondir must be a regular file: {commondir}")
        return git_dir
    try:
        value = commondir.read_text(encoding="utf-8", errors="strict").strip()
    except (OSError, UnicodeError):
        errors.append(f"linked worktree commondir is unreadable: {commondir}")
        return git_dir
    try:
        target = Path(value)
        if not target.is_absolute():
            target = git_dir / target
        return target.resolve()
    except (OSError, ValueError):
        errors.append(f"linked worktree commondir is invalid: {commondir}")
        return git_dir


def _local_config(config: Path, errors: list[str]) -> dict[str, list[str]]:
    if not config.is_file() or config.is_symlink():
        errors.append(f"common Git config is missing, non-regular, or a symlink: {config}")
        return {}
    result = subprocess.run(
        ["/usr/bin/git", "config", "--file", str(config), "--null", "--list", "--no-includes"],
        capture_output=True,
        check=False,
        env=isolated_git_environment(),
    )
    if result.returncode != 0:
        errors.append("common Git config cannot be parsed")
        return {}
    values: dict[str, list[str]] = {}
    for record in result.stdout.decode("utf-8", errors="replace").split("\0"):
        if not record:
            continue
        key, separator, value = record.partition("\n")
        if not separator:
            key, separator, value = record.partition("=")
        values.setdefault(key.lower(), []).append(value if separator else "")
    return values


def _safe_remote_url(value: str) -> bool:
    return value.lower().startswith(("https://", "http://", "ssh://", "git://", "file://"))


def _safe_config_entry(key: str, values: list[str]) -> bool:
    if key in SAFE_CONFIG:
        return True
    if key.startswith("branch.") and key.endswith((".remote", ".merge")):
        return True
    if key.startswith("remote.") and key.endswith(".fetch"):
        return True
    if key.startswith("remote.") and key.endswith((".url", ".pushurl")):
        return all(_safe_remote_url(value) for value in values)
    return False


def _check_config(values: dict[str, list[str]], errors: list[str]) -> None:
    if values.get("core.worktree"):
        errors.append("common core.worktree must be absent in a normal worktree repository")
    if any(value == "Test User" for value in values.get("user.name", [])):
        errors.append("fixture Git user.name leaked into common config")
    if any(value.endswith(".invalid") for value in values.get("user.email", [])):
        errors.append("fixture Git user.email leaked into common config")
    for key, configured_values in values.items():
        if not _safe_config_entry(key, configured_values):
            errors.append(f"repository-local Git config key is not allowed: {key}")


def _scan_duplicates(scan_roots: Iterable[Path], errors: list[str]) -> None:
    identities: dict[Path, list[Path]] = {}
    for root in scan_roots:
        root = root.resolve()
        if not root.is_dir():
            errors.append(f"worktree scan root is not a directory: {root}")
            continue
        for current, directories, files in os.walk(root):
            directories[:] = [name for name in directories if name != ".git"]
            if ".git" not in files:
                continue
            marker = Path(current) / ".git"
            target = _read_gitfile(marker)
            if target is not None:
                identities.setdefault(target, []).append(marker.resolve())
    for target, markers in identities.items():
        unique = sorted(set(markers), key=str)
        if len(unique) > 1:
            errors.append(
                f"multiple worktree pointers share Git administration {target}: "
                + ", ".join(str(marker) for marker in unique)
            )


def inspect_worktree(repo: Path, scan_roots: Iterable[Path] = ()) -> dict[str, object]:
    repo = repo.resolve()
    errors = [
        f"unsafe Git environment override is set: {name}"
        for name in sorted(
            name
            for name in os.environ
            if name in TOPOLOGY_ENV or name == "GIT_CONFIG" or name.startswith("GIT_CONFIG_")
        )
    ]
    marker = repo / ".git"
    if marker.is_symlink():
        errors.append(f"worktree .git marker must not be a symlink: {marker}")
        git_dir = marker
    elif marker.is_dir():
        git_dir = marker.resolve()
    else:
        git_dir = _read_gitfile(marker) or marker
        if not git_dir.is_dir():
            errors.append(f"worktree has no valid .git directory or pointer: {repo}")

    common = _common_dir(git_dir, errors) if git_dir.is_dir() else git_dir
    if git_dir.parent.name == "worktrees":
        backlink_file = git_dir / "gitdir"
        try:
            backlink = Path(backlink_file.read_text(encoding="utf-8", errors="strict").strip())
            if not backlink.is_absolute():
                backlink = git_dir / backlink
            if backlink.resolve() != marker.resolve():
                errors.append("linked worktree backlink does not identify this worktree")
        except (OSError, UnicodeError, ValueError):
            errors.append("linked worktree backlink is missing or unreadable")
        if common.name != ".git" or git_dir.parent.parent != common:
            errors.append("linked worktree commondir is not its owning common Git directory")

    if common.is_dir():
        _check_config(_local_config(common / "config", errors), errors)
    roots = list(scan_roots)
    _scan_duplicates(roots or [repo.parent], errors)
    return {
        "schema_version": "1",
        "repo": str(repo),
        "git_dir": str(git_dir),
        "common_dir": str(common),
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--scan-root", type=Path, action="append", default=[])
    args = parser.parse_args()
    result = inspect_worktree(args.repo, args.scan_root)
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
