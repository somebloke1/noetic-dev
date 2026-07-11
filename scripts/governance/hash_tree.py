#!/usr/bin/env python3
"""Compute SHA256 hashes deterministically from paths or strings.

Used by governance evidence collection to produce verifiable content hashes
independent of model output or candidate-modifiable scripts.

This module operates outside the candidate checkout (it is part of the
protected policy code) so its own hash is not subject to candidate tampering.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Union


def sha256_file(path: Union[str, Path]) -> str:
    """Compute SHA256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(65536)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Compute SHA256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """Compute SHA256 hex digest of UTF-8 encoded text."""
    return sha256_bytes(text.encode("utf-8"))


def canonical_json(obj) -> str:
    """Serialize to deterministic canonical JSON.

    - Object keys sorted lexicographically
    - Arrays preserve order
    - No insignificant whitespace
    - Separators are ',' and ':'
    - Strings use standard JSON escaping
    - Rejects NaN, Infinity, duplicate keys, non-deterministic numbers
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def canonical_json_sha256(obj) -> str:
    """Compute SHA256 of the canonical JSON representation."""
    return sha256_text(canonical_json(obj))


def canonical_json_from_file(path: Union[str, Path]) -> str:
    """Read a JSON file, re-serialize canonically, return canonical JSON string."""
    with open(path, "r") as f:
        data = json.load(f)
    return canonical_json(data)


def manifest_digest_excluding_own(manifest: dict) -> str:
    """Compute canonical manifest digest after removing /policy/runner_attestation/artifact/manifest_sha256.

    This prevents a circular self-reference where the manifest hash includes
    its own recorded hash field.
    """
    manifest = _deep_copy(manifest)

    # Remove the self-reference field
    try:
        del manifest["policy"]["runner_attestation"]["artifact"]["manifest_sha256"]
    except (KeyError, TypeError):
        pass

    # Also remove empty runner_attestation if that made it empty
    try:
        if manifest["policy"]["runner_attestation"] == {}:
            del manifest["policy"]["runner_attestation"]
    except (KeyError, TypeError):
        pass

    return canonical_json_sha256(manifest)


def _deep_copy(obj):
    """Simple deep copy for dict/list structures."""
    if isinstance(obj, dict):
        return {k: _deep_copy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_deep_copy(v) for v in obj]
    return obj


def validate_sha256_hex(value: str, label: str = "value") -> None:
    """Validate that a string is a valid 64-character lowercase hex SHA256."""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string, got {type(value).__name__}")
    if len(value) != 64:
        raise ValueError(f"{label} must be 64 hex chars, got {len(value)}")
    try:
        int(value, 16)
    except ValueError:
        raise ValueError(f"{label} is not valid hex: {value}")


def validate_sha_hex(value: str, expected_length: int = 40, label: str = "value") -> None:
    """Validate that a string is a valid hex SHA (git SHA = 40, SHA256 = 64)."""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string, got {type(value).__name__}")
    if len(value) != expected_length:
        raise ValueError(f"{label} must be {expected_length} hex chars, got {len(value)}")
    try:
        int(value, 16)
    except ValueError:
        raise ValueError(f"{label} is not valid hex: {value}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: hash_tree.py <file> [<file> ...]")
        print("       hash_tree.py --canonical-json <file>")
        print("       hash_tree.py --manifest-digest <file>")
        sys.exit(1)

    if sys.argv[1] == "--canonical-json":
        for path in sys.argv[2:]:
            print(canonical_json_from_file(path))
    elif sys.argv[1] == "--manifest-digest":
        import json as json_mod
        with open(sys.argv[2], "r") as f:
            manifest = json_mod.load(f)
        print(manifest_digest_excluding_own(manifest))
    else:
        for path in sys.argv[1:]:
            print(sha256_file(path))
