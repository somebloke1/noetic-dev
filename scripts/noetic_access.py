"""Local operator pairing, independent of model/provider credentials."""

from __future__ import annotations

import os
from pathlib import Path
import re
import secrets
import stat


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def validate_token(token: str) -> str:
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
        raise ValueError("Operator token must contain 32-128 URL-safe ASCII characters.")
    return token


def _validate_token_directory(path: Path) -> None:
    info = path.parent.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o022:
        raise ValueError(f"Unsafe operator token directory: {path.parent}. Select an owner-controlled directory without group/other write access using --token-file.")


def load_token(path: Path | str) -> str:
    """Create/reuse an owner-only token; never repair existing permissions implicitly."""
    path = Path(path).expanduser().absolute()
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700, exist_ok=True)
    _validate_token_directory(path)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        fd = None
    if fd is not None:
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(generate_token() + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    return read_token(path)


def read_token(path: Path | str) -> str:
    """Validate an existing owner token without creating or changing any files."""
    path = Path(path).expanduser().absolute()
    try:
        _validate_token_directory(path)
    except FileNotFoundError:
        raise ValueError(f"Operator token directory is missing: {path.parent}. Match --runs-dir/--token-file to the running GUI; no token or directory was created.") from None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        raise ValueError(f"Operator token file is missing: {path}. Select the running GUI's existing --token-file; no token was created.") from None
    except OSError as exc:
        raise ValueError(f"Cannot open operator token file: {path}. Use a regular owner-only file, not a symlink, or select --token-file.") from exc
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
        os.close(fd)
        raise ValueError(f"Unsafe operator token file: {path}. Inspect ownership and links; explicitly chmod 600 this file if owner-controlled, or select a new private --token-file. No permissions were changed.")
    with os.fdopen(fd, "r", encoding="ascii") as stream:
        try:
            return validate_token(stream.read(130).removesuffix("\n"))
        except (ValueError, UnicodeError) as exc:
            raise ValueError(f"Invalid operator token file: {path}. With the server stopped, explicitly replace this file to generate a new token; existing pairings will need updating.") from exc
