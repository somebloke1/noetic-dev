#!/usr/bin/env python3
"""Incrementally replay one M0 verified-change source into terminal status.

Intermediate admission establishes only the fixed event order and immediate
causality. The existing whole-trace pipeline validates authority, bindings,
payloads, and attributed judgments transactionally at the terminal event. It
does not authenticate the fixture or enact the work described by its records.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__:
    from scripts.development_verified_change import M0_TRACE_VERSION, load_json_strict
    from scripts.development_verified_change_explain import explain_verified_change
else:
    from development_verified_change import M0_TRACE_VERSION, load_json_strict
    from development_verified_change_explain import explain_verified_change


class ReplayValidationError(ValueError):
    """Raised when an incremental M0 replay violates its bounded contract."""


M0_STEPS = (
    ("telos.delegation.authorized", "delegated"),
    ("controller.run.created", "run_created"),
    ("controller.run.started", "run_started"),
    ("controller.implementation_generation.accepted", "generation_accepted"),
    ("qa.verification.adjudicated", "qa_pass_attributed"),
    ("controller.run.succeeded", "run_succeeded"),
    ("controller.result.reported", "result_reported"),
    ("telos.sub_goal.adjudicated", "telos_adjudicated"),
)


def _fail(path: str, message: str) -> None:
    raise ReplayValidationError(f"{path}: {message}")


def _copy_strict_json(value: Any, path: str) -> Any:
    value_type = type(value)
    if value_type is dict:
        copied: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                _fail(path, "object keys must be strings")
            copied[key] = _copy_strict_json(item, f"{path}.{key}")
        return copied
    if value_type is list:
        return [
            _copy_strict_json(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if value_type in (str, int, bool):
        return value
    if value is None:
        _fail(path, "null is not supported")
    if value_type is float:
        _fail(path, "floating-point numbers are not supported")
    _fail(path, f"unsupported value type: {value_type.__name__}")


def _copy_input(value: Any, path: str) -> Any:
    try:
        return _copy_strict_json(value, path)
    except RecursionError as exc:
        raise ReplayValidationError(
            f"{path}: input nesting exceeds recursion limit: {exc}"
        ) from exc


def _record_envelope(record: Any) -> tuple[dict[str, Any], str, str, list[Any]]:
    copied = _copy_input(record, "$record")
    if type(copied) is not dict:
        _fail("$record", "expected object")
    for field in ("event_id", "event_type", "caused_by"):
        if field not in copied:
            _fail("$record", f"missing field: {field}")
    event_id = copied["event_id"]
    event_type = copied["event_type"]
    caused_by = copied["caused_by"]
    if type(event_id) is not str or not event_id:
        _fail("$record.event_id", "expected nonempty string")
    if type(event_type) is not str:
        _fail("$record.event_type", "expected string")
    if type(caused_by) is not list:
        _fail("$record.caused_by", "expected array")
    if any(type(parent) is not str for parent in caused_by):
        _fail("$record.caused_by", "expected string event identifiers")
    return copied, event_id, event_type, caused_by


class M0ReplayController:
    """Admit M0 records by event order and immediate causality."""

    def __init__(self, packet: Any) -> None:
        self._packet = _copy_input(packet, "$packet")
        self._records: list[dict[str, Any]] = []
        self._event_ids: set[str] = set()
        self._state = "initial"
        self._terminal_status: dict[str, Any] | None = None

    @property
    def state(self) -> str:
        return self._state

    @property
    def admitted_count(self) -> int:
        return len(self._records)

    @property
    def admitted_records(self) -> list[dict[str, Any]]:
        return _copy_input(self._records, "$records")

    @property
    def next_event_type(self) -> str | None:
        if len(self._records) == len(M0_STEPS):
            return None
        return M0_STEPS[len(self._records)][0]

    @property
    def complete(self) -> bool:
        return self._terminal_status is not None

    def accept(self, record: Any) -> str:
        """Admit one record or leave controller state unchanged on rejection."""
        if len(self._records) == len(M0_STEPS):
            _fail("$record", "terminal replay does not accept additional records")

        copied, event_id, event_type, caused_by = _record_envelope(record)
        expected_type, next_state = M0_STEPS[len(self._records)]
        if event_type != expected_type:
            _fail("$record.event_type", f"expected {expected_type!r}")
        if event_id in self._event_ids:
            _fail("$record.event_id", "replayed event identifier")
        expected_cause = [] if not self._records else [self._records[-1]["event_id"]]
        if caused_by != expected_cause:
            _fail("$record.caused_by", f"expected {expected_cause!r}")

        terminal_status: dict[str, Any] | None = None
        if len(self._records) + 1 == len(M0_STEPS):
            source = {
                "schema_version": M0_TRACE_VERSION,
                "records": self._records + [copied],
            }
            terminal_status = _copy_input(
                explain_verified_change(self._packet, source),
                "$terminal_status",
            )

        self._records.append(copied)
        self._event_ids.add(event_id)
        self._state = next_state
        self._terminal_status = terminal_status
        return self._state

    def finish(self) -> dict[str, Any]:
        """Return a copy of terminal status after all eight records validate."""
        if self._terminal_status is None:
            _fail("$records", f"incomplete replay: admitted {len(self._records)} of {len(M0_STEPS)} records")
        return _copy_input(self._terminal_status, "$terminal_status")


def replay_m0_verified_change(packet: Any, source: Any) -> dict[str, Any]:
    """Replay one complete M0 source through the incremental controller."""
    document = _copy_input(source, "$source")
    if type(document) is not dict:
        _fail("$source", "expected object")
    if set(document) != {"schema_version", "records"}:
        _fail("$source", "expected exactly schema_version and records")
    if document["schema_version"] != M0_TRACE_VERSION:
        _fail("$source.schema_version", f"expected {M0_TRACE_VERSION!r}")
    records = document["records"]
    if type(records) is not list:
        _fail("$source.records", "expected array")

    controller = M0ReplayController(packet)
    for record in records:
        controller.accept(record)
    return controller.finish()


def _render(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("ascii")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path, help="strict development program packet JSON")
    parser.add_argument("source", type=Path, help="strict frozen M0 source trace JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        packet = load_json_strict(args.packet)
        source = load_json_strict(args.source)
        sys.stdout.buffer.write(_render(replay_m0_verified_change(packet, source)))
        return 0
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        print(f"verified-change M0 replay failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
