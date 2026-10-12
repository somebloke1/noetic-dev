#!/usr/bin/env python3
"""Persist and replay the bounded M0 cognitional-event journal."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

if __package__:
    from scripts.development_verified_change import load_json_strict
    from scripts.development_verified_change_replay import M0_STEPS, M0ReplayController
    from scripts.m0_trace import canonical_json_bytes, strict_json_loads
else:
    from development_verified_change import load_json_strict
    from development_verified_change_replay import M0_STEPS, M0ReplayController
    from m0_trace import canonical_json_bytes, strict_json_loads


class JournalValidationError(ValueError):
    """Raised when journal bytes violate the bounded persistence contract."""


JOURNAL_VERSION = "noetic.cognitional-event-journal/v1"
READ_MODEL_VERSION = "noetic.cognitional-event-journal-read-model/v1"
CONSUMER_ID = "development.verified-change/m0-direct-pass"
RECORD_VERSION = "noetic.m0.trace-record/v0"
MAX_RECORDS = len(M0_STEPS)
MAX_RECORD_BYTES = 64 * 1024
MAX_JOURNAL_BYTES = MAX_RECORDS * MAX_RECORD_BYTES
RECORD_FIELDS = (
    "schema_version",
    "event_id",
    "event_type",
    "occurred_at",
    "actor",
    "binding",
    "caused_by",
    "payload",
)
ACTOR_FIELDS = ("role", "actor_id")


def _fail(path: str, message: str) -> None:
    raise JournalValidationError(f"{path}: {message}")


def _read_bounded(path: Path) -> bytes:
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return b""
    if size > MAX_JOURNAL_BYTES:
        _fail("$journal", f"exceeds {MAX_JOURNAL_BYTES} bytes")
    data = path.read_bytes()
    if len(data) > MAX_JOURNAL_BYTES:
        _fail("$journal", f"exceeds {MAX_JOURNAL_BYTES} bytes")
    return data


def _validate_storage_envelope(record: Any, path: str) -> None:
    if type(record) is not dict:
        _fail(path, "expected object")
    if set(record) != set(RECORD_FIELDS):
        _fail(path, f"expected exactly {', '.join(RECORD_FIELDS)}")
    if record["schema_version"] != RECORD_VERSION:
        _fail(f"{path}.schema_version", f"expected {RECORD_VERSION!r}")
    if type(record["occurred_at"]) is not str:
        _fail(f"{path}.occurred_at", "expected string")
    actor = record["actor"]
    if type(actor) is not dict or set(actor) != set(ACTOR_FIELDS):
        _fail(f"{path}.actor", f"expected exactly {', '.join(ACTOR_FIELDS)}")
    for field in ACTOR_FIELDS:
        if type(actor[field]) is not str or not actor[field]:
            _fail(f"{path}.actor.{field}", "expected nonempty string")
    if type(record["binding"]) is not dict:
        _fail(f"{path}.binding", "expected object")
    if type(record["payload"]) is not dict:
        _fail(f"{path}.payload", "expected object")


def parse_journal_bytes(data: bytes) -> list[dict[str, Any]]:
    """Parse complete canonical JSONL records without replaying them."""
    if type(data) is not bytes:
        _fail("$journal", "expected bytes")
    if len(data) > MAX_JOURNAL_BYTES:
        _fail("$journal", f"exceeds {MAX_JOURNAL_BYTES} bytes")
    if not data:
        return []
    if not data.endswith(b"\n"):
        _fail("$journal", "unterminated final record; explicit recovery is required")

    lines = [chunk + b"\n" for chunk in data.split(b"\n")[:-1]]
    if len(lines) > MAX_RECORDS:
        _fail("$journal", f"expected at most {MAX_RECORDS} records")

    records: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        path = f"$journal.records[{index}]"
        if len(line) > MAX_RECORD_BYTES:
            _fail(path, f"exceeds {MAX_RECORD_BYTES} bytes")
        try:
            text = line.decode("ascii")
        except UnicodeDecodeError as exc:
            raise JournalValidationError(f"{path}: expected ASCII: {exc}") from exc
        try:
            record = strict_json_loads(text)
        except ValueError as exc:
            raise JournalValidationError(f"{path}: {exc}") from exc
        _validate_storage_envelope(record, path)
        if canonical_json_bytes(record) != line:
            _fail(path, "record is not canonical JSONL bytes")
        records.append(record)
    return records


def replay_development_verified_change(
    packet: Any,
    records: list[dict[str, Any]],
) -> M0ReplayController:
    """Reconstruct one journal through the existing M0 replay controller."""
    controller = M0ReplayController(packet)
    for record in records:
        controller.accept(record)
    return controller


def derive_journal_read_model(controller: M0ReplayController) -> dict[str, Any]:
    """Project deterministic consumer state without adding semantic judgments."""
    result: dict[str, Any] = {
        "schema_version": READ_MODEL_VERSION,
        "journal_version": JOURNAL_VERSION,
        "consumer_id": CONSUMER_ID,
        "record_version": RECORD_VERSION,
        "record_count": controller.admitted_count,
        "state": controller.state,
        "complete": controller.complete,
    }
    if controller.complete:
        result["terminal_status"] = controller.finish()
    else:
        next_event_type = controller.next_event_type
        if next_event_type is None:
            _fail("$journal", "incomplete replay has no next event")
        result["next_event_type"] = next_event_type
    return result


def inspect_journal(path: str | Path, packet: Any) -> dict[str, Any]:
    """Read and replay one journal, treating a missing file as an empty journal."""
    records = parse_journal_bytes(_read_bounded(Path(path)))
    return derive_journal_read_model(
        replay_development_verified_change(packet, records)
    )


def append_event(path: str | Path, packet: Any, record: Any) -> dict[str, Any]:
    """Validate then append one canonical event and return reconstructed state."""
    journal_path = Path(path)
    existing = _read_bounded(journal_path)
    records = parse_journal_bytes(existing)
    controller = replay_development_verified_change(packet, records)
    _validate_storage_envelope(record, "$record")
    controller.accept(record)
    encoded = canonical_json_bytes(controller.admitted_records[-1])
    if len(encoded) > MAX_RECORD_BYTES:
        _fail("$record", f"exceeds {MAX_RECORD_BYTES} canonical bytes")
    if len(existing) + len(encoded) > MAX_JOURNAL_BYTES:
        _fail("$journal", f"append would exceed {MAX_JOURNAL_BYTES} bytes")

    with journal_path.open("ab") as handle:
        written = handle.write(encoded)
        if written != len(encoded):
            raise OSError(f"partial journal append: wrote {written} of {len(encoded)} bytes")
        handle.flush()
        os.fsync(handle.fileno())
    return derive_journal_read_model(controller)


def recover_trailing_fragment(path: str | Path, packet: Any) -> dict[str, Any]:
    """Explicitly remove one unterminated tail after validating every full record."""
    journal_path = Path(path)
    data = _read_bounded(journal_path)
    if not data or data.endswith(b"\n"):
        records = parse_journal_bytes(data)
        return derive_journal_read_model(
            replay_development_verified_change(packet, records)
        )

    prefix_length = data.rfind(b"\n") + 1
    fragment = data[prefix_length:]
    if len(fragment) > MAX_RECORD_BYTES:
        _fail("$journal.trailing_fragment", f"exceeds {MAX_RECORD_BYTES} bytes")
    records = parse_journal_bytes(data[:prefix_length])
    controller = replay_development_verified_change(packet, records)

    with journal_path.open("r+b") as handle:
        handle.truncate(prefix_length)
        handle.flush()
        os.fsync(handle.fileno())
    return derive_journal_read_model(controller)


def _render(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("ascii")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    inspect = commands.add_parser("inspect", help="replay a journal without changing it")
    inspect.add_argument("packet", type=Path, help="strict M0 development program packet")
    inspect.add_argument("journal", type=Path, help="canonical event journal JSONL")

    append = commands.add_parser("append", help="validate and append one event")
    append.add_argument("packet", type=Path, help="strict M0 development program packet")
    append.add_argument("journal", type=Path, help="canonical event journal JSONL")
    append.add_argument("record", type=Path, help="strict event record JSON")

    recover = commands.add_parser(
        "recover",
        help="remove one unterminated tail after replaying every complete record",
    )
    recover.add_argument("packet", type=Path, help="strict M0 development program packet")
    recover.add_argument("journal", type=Path, help="canonical event journal JSONL")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        packet = load_json_strict(args.packet)
        if args.command == "append":
            result = append_event(args.journal, packet, load_json_strict(args.record))
        elif args.command == "recover":
            result = recover_trailing_fragment(args.journal, packet)
        else:
            result = inspect_journal(args.journal, packet)
        sys.stdout.buffer.write(_render(result))
        return 0
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        print(f"cognitional event journal failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
