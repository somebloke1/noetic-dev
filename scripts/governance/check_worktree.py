#!/usr/bin/env python3
"""Read-only validation of Git worktree administration and local config."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit

BOOLEAN_CONFIG = {
    "core.filemode",
    "core.ignorecase",
    "core.logallrefupdates",
    "core.precomposeunicode",
    "core.symlinks",
}
SCAN_ENTRY_LIMIT = 4096
SAFE_GIT_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_NO_REPLACE_OBJECTS": "1",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_TERMINAL_PROMPT": "0",
}
SAFE_PROCESS_ENV = {
    "HOME": "/nonexistent",
    "LANG": "C",
    "LC_ALL": "C",
    "PATH": os.defpath,
    **SAFE_GIT_ENV,
}


def isolated_git_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """Return the fixed minimal environment used by trusted Git subprocesses."""
    del source
    return dict(SAFE_PROCESS_ENV)


def trusted_git_binary() -> str | None:
    """Resolve Git only from the platform's fixed default executable path."""
    return shutil.which("git", path=os.defpath)


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


def _common_dir(git_dir: Path, errors: list[str], required: bool = False) -> Path:
    commondir = git_dir / "commondir"
    try:
        commondir_mode = commondir.lstat().st_mode
    except FileNotFoundError:
        if required:
            errors.append("linked worktree commondir is missing")
        return git_dir
    except OSError:
        errors.append(f"linked worktree commondir is unreadable: {commondir}")
        return git_dir
    if not stat.S_ISREG(commondir_mode):
        errors.append(
            f"linked worktree commondir must be a regular non-symlink file: {commondir}"
        )
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
    git_binary = trusted_git_binary()
    if git_binary is None:
        errors.append("Git executable is unavailable on the trusted system path")
        return {}
    try:
        result = subprocess.run(
            [git_binary, "config", "--file", str(config), "--null", "--list", "--no-includes"],
            capture_output=True,
            check=False,
            env=isolated_git_environment(),
        )
    except OSError as error:
        errors.append(f"Git config parser could not start: {error}")
        return {}
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
    if key in {"core.repositoryformatversion", "lfs.repositoryformatversion"}:
        return values == ["0"]
    if key == "core.bare":
        return len(values) == 1 and _git_bool(values[0]) is not None
    if key in BOOLEAN_CONFIG:
        return len(values) == 1 and (
            _git_bool(values[0]) is not None
            or (key == "core.logallrefupdates" and values[0].casefold() == "always")
        )
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


def _git_bool(value: str) -> bool | None:
    normalized = value.casefold()
    if normalized in {"true", "yes", "on", "1"}:
        return True
    if normalized in {"false", "no", "off", "0", ""}:
        return False
    return None


def _check_config(
    values: dict[str, list[str]], errors: list[str], primary: bool
) -> None:
    if values.get("core.worktree"):
        errors.append("common core.worktree must be absent in a normal worktree repository")
    if any(value.casefold() == "test user" for value in values.get("user.name", [])):
        errors.append("fixture Git user.name leaked into common config")
    if any(value.casefold().endswith(".invalid") for value in values.get("user.email", [])):
        errors.append("fixture Git user.email leaked into common config")
    if values.get("core.repositoryformatversion") != ["0"]:
        errors.append("core.repositoryformatversion must be exactly 0")
    bare_values = values.get("core.bare", [])
    bare = _git_bool(bare_values[0]) if len(bare_values) == 1 else None
    if primary and bare is not False:
        errors.append("primary worktree core.bare must be false")
    for key, configured_values in values.items():
        if not _safe_config_entry(key, configured_values):
            errors.append(f"repository-local Git config key is not allowed: {key}")


def _scan_duplicates(
    scan_roots: Iterable[Path], errors: list[str], entry_limit: int
) -> None:
    identities: dict[Path, list[Path]] = {}
    resolved_roots: set[Path] = set()
    entries_seen = 0
    for root in scan_roots:
        try:
            root = root.resolve()
        except (OSError, RuntimeError, ValueError) as error:
            errors.append(f"worktree scan root cannot be resolved: {root}: {error}")
            continue
        if root in resolved_roots:
            continue
        resolved_roots.add(root)
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
        for name in sorted(
            name
            for name, value in os.environ.items()
            if name.startswith("GIT_") and SAFE_GIT_ENV.get(name) != value
        )
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
        common = (
            _common_dir(git_dir, errors, required=linked)
            if git_dir.is_dir()
            else git_dir
        )
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
        _check_config(_local_config(common / "config", errors), errors, primary)
    roots = [repo.parent, *scan_roots]
    if valid_scan_limit:
        _scan_duplicates(roots, errors, scan_entry_limit)
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
