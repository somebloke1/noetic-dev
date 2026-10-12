"""Owner-only creation and explicit migration of selected Noetic state (POSIX)."""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import warnings


@contextmanager
def _directory(path, create=False):
    # Walk descriptors so neither a leaf nor an ancestor symlink is followed.
    path = Path(os.path.abspath(Path(path).expanduser()))
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            created = False
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                    created = True
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            if created:
                os.fchmod(fd, 0o700)
        yield fd
    finally:
        os.close(fd)


def _owned(info, path):
    if info.st_uid != os.geteuid():
        raise PermissionError(f"Not owned by the current user: {path}")


def ensure_private_directory(path):
    """Create missing components as 0700; never chmod existing ancestors."""
    path = Path(path)
    with _directory(path, create=True) as fd:
        info = os.fstat(fd)
        _owned(info, path)
        if stat.S_IMODE(info.st_mode) != 0o700:
            warnings.warn(f"Existing state directory is not 0700: {path}; inspect then explicitly "
                          "protect the Noetic-owned state root with scripts.noetic_storage", RuntimeWarning,
                          stacklevel=2)
    return path


def open_private(path, mode="w", encoding="utf-8"):
    """Return a context-manageable file, 0600 before any truncation or write.

    Only owned, single-link regular managed files are accepted. Binary modes
    ignore encoding. Existing files are narrowed, but never their parents.
    """
    if not isinstance(mode, str) or not mode or mode[0] not in "rwax" or any(
        char not in "rwax+bt" for char in mode
    ) or sum(mode.count(char) for char in "rwax") != 1 or any(
        mode.count(char) > 1 for char in "+bt"
    ) or ("b" in mode and "t" in mode):
        raise ValueError(f"Unsupported file mode: {mode}")
    path = Path(path)
    ensure_private_directory(path.parent)
    flags = os.O_RDWR if "+" in mode else (os.O_RDONLY if mode[0] == "r" else os.O_WRONLY)
    if mode[0] in "wax":
        flags |= os.O_CREAT
    if mode[0] == "x":
        flags |= os.O_EXCL
    if mode[0] == "a":
        flags |= os.O_APPEND
    with _directory(path.parent) as parent:
        fd = os.open(path.name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent)
    try:
        info = os.fstat(fd)
        _owned(info, path)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError(f"Not a single-link regular managed file: {path}")
        os.fchmod(fd, 0o600)
        if mode[0] == "w":
            os.ftruncate(fd, 0)
        stream = os.fdopen(fd, mode, encoding=None if "b" in mode else encoding)
    except BaseException:
        os.close(fd)
        raise
    return stream


def create_private_sqlite(path):
    """Precreate a new DB as 0600; return its Path, not a connection.

    Existing databases are not overwritten or chmodded (external Telos stores
    may be user-managed). Broad legacy modes require explicit migration.
    """
    path = Path(path)
    try:
        with open_private(path, "xb"):
            pass
    except FileExistsError:
        with _directory(path.parent) as parent:
            info = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        _owned(info, path)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError(f"Not a single-link regular database: {path}")
        if stat.S_IMODE(info.st_mode) != 0o600:
            warnings.warn(f"Existing database is not 0600: {path}; inspect then explicitly protect "
                          "its Noetic-owned state root (not an external user-managed store)",
                          RuntimeWarning, stacklevel=2)
    return path


def _tree(root, protect=False):
    root = Path(os.path.abspath(Path(root).expanduser()))
    home = Path.home().resolve()
    if root == Path(root.anchor) or root == home or root in home.parents:
        raise ValueError("Select only a Noetic-owned state directory, not home or an ancestor")
    report = {"root": str(root), "directories": 0, "files": 0, "bytes": 0,
              "needs_protection": 0, "changed": 0, "skipped": [], "sha256": {}}

    def visit(fd, relative):
        info = os.fstat(fd)
        _owned(info, root / relative)
        names = sorted(os.listdir(fd))
        if any(name in names for name in (".git", "pyproject.toml", "package.json")):
            raise ValueError(f"Refusing source/workspace directory: {root / relative}")
        report["directories"] += 1
        if stat.S_IMODE(info.st_mode) != 0o700:
            report["needs_protection"] += 1
            if protect:
                os.fchmod(fd, 0o700)
                report["changed"] += 1
        for name in names:
            rel = relative / name
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            reason = None
            if info.st_uid != os.geteuid():
                reason = "foreign owner"
            elif stat.S_ISLNK(info.st_mode):
                reason = "symlink"
            elif not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                reason = "special file"
            elif stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                reason = "hard-linked file"
            if reason:
                report["skipped"].append({"path": str(rel), "reason": reason})
                continue
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if stat.S_ISDIR(info.st_mode):
                flags |= os.O_DIRECTORY
            child = os.open(name, flags, dir_fd=fd)
            try:
                current = os.fstat(child)
                if (current.st_dev, current.st_ino, current.st_uid, current.st_nlink) != (
                    info.st_dev, info.st_ino, info.st_uid, info.st_nlink
                ):
                    raise ValueError(f"State changed during inspection: {rel}; stop writers and retry")
                if stat.S_ISDIR(current.st_mode):
                    visit(child, rel)
                    continue
                digest = hashlib.sha256()
                size = 0
                while chunk := os.read(child, 1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
                report["files"] += 1
                report["bytes"] += size
                report["sha256"][str(rel)] = digest.hexdigest()
                # Explicit migration preserves only the owner's executable bit.
                target = 0o600 | (current.st_mode & stat.S_IXUSR)
                if stat.S_IMODE(current.st_mode) != target:
                    report["needs_protection"] += 1
                    if protect:
                        os.fchmod(child, target)
                        report["changed"] += 1
            finally:
                os.close(child)

    with _directory(root) as fd:
        visit(fd, Path("."))
    return report


def inspect_tree(root):
    """Read-only inventory of an explicitly selected Noetic-owned state tree."""
    return _tree(root)


def protect_tree(root):
    """Explicit offline mode migration. Skipped entries are never followed."""
    before = inspect_tree(root)
    applied = _tree(root, protect=True)
    after = inspect_tree(root)
    preserved = all(before[key] == after[key] for key in ("files", "directories", "bytes", "sha256"))
    if not preserved:
        raise ValueError("State content changed during protection; stop writers and inspect again")
    return {"before": before, "after": after, "changed": applied["changed"], "content_preserved": preserved}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "protect"))
    parser.add_argument("root", type=Path, help="Noetic-owned state ONLY; never a workspace or home")
    args = parser.parse_args(argv)
    try:
        result = protect_tree(args.root) if args.command == "protect" else inspect_tree(args.root)
        print(json.dumps(result, indent=2, sort_keys=True))
        report = result.get("after", result)
        return 1 if report["skipped"] or report["needs_protection"] else 0
    except (OSError, ValueError) as exc:
        parser.exit(2, f"private storage: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
