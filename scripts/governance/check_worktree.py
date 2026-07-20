#!/usr/bin/env python3
"""Read-only validation of Git worktree administration and local config."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit

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
SCAN_ENTRY_LIMIT = 4096


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
    except (OSError, RuntimeError, ValueError):
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
    except (OSError, RuntimeError, ValueError):
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
    try:
        parsed = urlsplit(value)
        if parsed.query or parsed.fragment or parsed.password is not None:
            return False
        if not parsed.scheme:
            return re.fullmatch(
                r"(?:[A-Za-z0-9._+-]+@)?"
                r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?:"
                r"(?!-)[^\s?#]+",
                value,
            ) is not None
        if parsed.scheme in {"http", "https"}:
            return parsed.hostname is not None and parsed.username is None
        if parsed.scheme == "ssh":
            return parsed.hostname is not None
        if parsed.scheme == "git":
            return parsed.hostname is not None and parsed.username is None
        if parsed.scheme == "file":
            return bool(parsed.path) and parsed.username is None
    except ValueError:
        return False
    return False


def _safe_config_entry(key: str, values: list[str]) -> bool:
    if key in SAFE_CONFIG:
        return True
    if key == "user.name":
        return all(0 < len(value) <= 256 and value.isprintable() for value in values)
    if key == "user.email":
        for value in values:
            local, separator, domain = value.partition("@")
            if (
                not separator
                or value.count("@") != 1
                or not local
                or not domain
                or len(value) > 320
                or not value.isprintable()
                or any(character.isspace() for character in value)
                or domain.casefold() == "invalid"
                or domain.casefold().endswith(".invalid")
            ):
                return False
        return True
    if key == "gc.auto":
        return all(
            bool(number := value.removeprefix("-"))
            and all("0" <= character <= "9" for character in number)
            for value in values
        )
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
    if any(value.casefold() == "test user" for value in values.get("user.name", [])):
        errors.append("fixture Git user.name leaked into common config")
    if any(value.casefold().endswith(".invalid") for value in values.get("user.email", [])):
        errors.append("fixture Git user.email leaked into common config")
    for key, configured_values in values.items():
        if not _safe_config_entry(key, configured_values):
            errors.append(f"repository-local Git config key is not allowed: {key}")


def _scan_duplicates(
    scan_roots: Iterable[Path], errors: list[str], entry_limit: int
) -> None:
    identities: dict[Path, list[Path]] = {}
    entries_seen = 0
    for root in scan_roots:
        try:
            root = root.resolve()
        except (OSError, RuntimeError, ValueError) as error:
            errors.append(f"worktree scan root cannot be resolved: {root}: {error}")
            continue
        if not root.is_dir():
            errors.append(f"worktree scan root is not a directory: {root}")
            continue

        markers = [root / ".git"]
        try:
            with os.scandir(root) as children:
                for child in children:
                    entries_seen += 1
                    if entries_seen > entry_limit:
                        errors.append(
                            f"worktree scan entry limit exceeded: {entry_limit}"
                        )
                        return
                    try:
                        if child.is_dir(follow_symlinks=False):
                            markers.append(Path(child.path) / ".git")
                    except OSError as error:
                        errors.append(f"worktree scan cannot inspect {child.path}: {error}")
        except OSError as error:
            errors.append(f"worktree scan cannot read {root}: {error}")
            continue

        for marker in markers:
            try:
                mode = marker.lstat().st_mode
            except FileNotFoundError:
                continue
            except OSError as error:
                errors.append(f"worktree scan cannot inspect {marker}: {error}")
                continue
            if stat.S_ISLNK(mode):
                errors.append(f"symlinked .git marker is forbidden: {marker}")
                continue
            if stat.S_ISREG(mode):
                target = _read_gitfile(marker)
                if target is not None:
                    try:
                        marker_identity = marker.resolve()
                    except (OSError, RuntimeError, ValueError) as error:
                        errors.append(f"worktree marker cannot be resolved: {marker}: {error}")
                        continue
                    identities.setdefault(target, []).append(marker_identity)
            elif not stat.S_ISDIR(mode):
                errors.append(f"non-regular .git marker is forbidden: {marker}")
    for target, markers in identities.items():
        unique = sorted(set(markers), key=str)
        if len(unique) > 1:
            errors.append(
                f"multiple worktree pointers share Git administration {target}: "
                + ", ".join(str(marker) for marker in unique)
            )


def inspect_worktree(
    repo: Path,
    scan_roots: Iterable[Path] = (),
    scan_entry_limit: int = SCAN_ENTRY_LIMIT,
) -> dict[str, object]:
    errors = [
        f"unsafe Git environment override is set: {name}"
        for name in sorted(name for name in os.environ if name.startswith("GIT_"))
    ]
    try:
        repo = repo.resolve()
    except (OSError, RuntimeError, ValueError) as error:
        errors.append(f"repository path cannot be resolved: {repo}: {error}")
        marker = repo / ".git"
        return {
            "schema_version": "1",
            "repo": str(repo),
            "git_dir": str(marker),
            "common_dir": str(marker),
            "status": "fail",
            "errors": errors,
        }
    valid_scan_limit = type(scan_entry_limit) is int and scan_entry_limit > 0
    if not valid_scan_limit:
        errors.append("worktree scan entry limit must be a positive integer")
    marker = repo / ".git"
    linked = False
    primary = False
    if marker.is_symlink():
        errors.append(f"worktree .git marker must not be a symlink: {marker}")
        git_dir = marker
    elif marker.is_dir():
        primary = True
        git_dir = marker.resolve()
    else:
        target = _read_gitfile(marker)
        linked = target is not None
        git_dir = target or marker
        if not git_dir.is_dir():
            errors.append(f"worktree has no valid .git directory or pointer: {repo}")

    if primary:
        if os.path.lexists(git_dir / "commondir"):
            errors.append("primary .git directory must not contain commondir")
        common = git_dir
    else:
        common = _common_dir(git_dir, errors) if git_dir.is_dir() else git_dir
    if linked:
        backlink_file = git_dir / "gitdir"
        try:
            backlink_mode = backlink_file.lstat().st_mode
        except OSError:
            errors.append("linked worktree backlink is missing or unreadable")
        else:
            if not stat.S_ISREG(backlink_mode):
                errors.append("linked worktree backlink must be a regular non-symlink file")
            else:
                try:
                    backlink = Path(
                        backlink_file.read_text(encoding="utf-8", errors="strict").strip()
                    )
                    if not backlink.is_absolute():
                        backlink = git_dir / backlink
                    if backlink.resolve() != marker.resolve():
                        errors.append("linked worktree backlink does not identify this worktree")
                except (OSError, RuntimeError, UnicodeError, ValueError):
                    errors.append("linked worktree backlink is missing or unreadable")
        if git_dir.parent != common / "worktrees":
            errors.append(
                "linked worktree administration is not in its common Git worktrees registry"
            )

    if common.is_dir():
        _check_config(_local_config(common / "config", errors), errors)
    roots = list(scan_roots)
    if valid_scan_limit:
        _scan_duplicates(roots or [repo.parent], errors, scan_entry_limit)
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
    parser.add_argument("--scan-entry-limit", type=int, default=SCAN_ENTRY_LIMIT)
    args = parser.parse_args()
    if args.scan_entry_limit < 1:
        parser.error("--scan-entry-limit must be positive")
    result = inspect_worktree(args.repo, args.scan_root, args.scan_entry_limit)
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
