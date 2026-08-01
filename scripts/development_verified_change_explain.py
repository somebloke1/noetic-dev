#!/usr/bin/env python3
"""Compose a verified-change packet and source into one terminal explanation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__:
    from scripts.development_verified_change import load_json_strict, validate_and_project
    from scripts.development_verified_change_observe import derive_terminal_observability
    from scripts.development_verified_change_status import derive_terminal_status
else:
    from development_verified_change import load_json_strict, validate_and_project
    from development_verified_change_observe import derive_terminal_observability
    from development_verified_change_status import derive_terminal_status


def explain_verified_change(packet: Any, source: Any) -> dict[str, Any]:
    """Run the three accepted pure stages without intermediate files."""
    projection = validate_and_project(packet, source)
    observability = derive_terminal_observability(projection)
    return derive_terminal_status(observability)


def _render(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("ascii")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path, help="strict development program packet JSON")
    parser.add_argument("source", type=Path, help="strict frozen M0 or M1 source trace JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        packet = load_json_strict(args.packet)
        source = load_json_strict(args.source)
        sys.stdout.buffer.write(_render(explain_verified_change(packet, source)))
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"verified-change explanation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
