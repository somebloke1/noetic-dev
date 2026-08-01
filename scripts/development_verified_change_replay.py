#!/usr/bin/env python3
"""Incrementally replay one fixed M0 or M1 source into terminal status.

Each profile retains its own fixed transition sequence. Intermediate admission
establishes only event order and immediate causality. The existing whole-trace
pipeline validates authority, bindings, payloads, and attributed judgments
transactionally at the terminal event. It does not authenticate the fixture or
enact the work described by its records.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__:
    from scripts.development_verified_change import (
        M0_TRACE_VERSION,
        M1_TRACE_VERSION,
        load_json_strict,
    )
    from scripts.development_verified_change_explain import explain_verified_change
    from scripts.m1_trace import TRANSITIONS as M1_TRANSITIONS
else:
    from development_verified_change import (
        M0_TRACE_VERSION,
        M1_TRACE_VERSION,
        load_json_strict,
    )
    from development_verified_change_explain import explain_verified_change
    from m1_trace import TRANSITIONS as M1_TRANSITIONS


class ReplayValidationError(ValueError):
    """Raised when a fixed-profile replay violates its bounded contract."""


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
M1_STEPS = tuple((event_type, to_state) for _, event_type, to_state in M1_TRANSITIONS)


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


class _FixedReplayController:
    """Admit records for one fixed profile by order and immediate causality."""

    def __init__(
        self,
        packet: Any,
        *,
        steps: tuple[tuple[str, str], ...],
        trace_version: str,
    ) -> None:
        self._packet = _copy_input(packet, "$packet")
        self._steps = steps
        self._trace_version = trace_version
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
        if len(self._records) == len(self._steps):
            return None
        return self._steps[len(self._records)][0]

    @property
    def complete(self) -> bool:
        return self._terminal_status is not None

    def accept(self, record: Any) -> str:
        """Admit one record or leave controller state unchanged on rejection."""
        if len(self._records) == len(self._steps):
            _fail("$record", "terminal replay does not accept additional records")

        copied, event_id, event_type, caused_by = _record_envelope(record)
        expected_type, next_state = self._steps[len(self._records)]
        if event_type != expected_type:
            _fail("$record.event_type", f"expected {expected_type!r}")
        if event_id in self._event_ids:
            _fail("$record.event_id", "replayed event identifier")
        expected_cause = [] if not self._records else [self._records[-1]["event_id"]]
        if caused_by != expected_cause:
            _fail("$record.caused_by", f"expected {expected_cause!r}")

        terminal_status: dict[str, Any] | None = None
        if len(self._records) + 1 == len(self._steps):
            source = {
                "schema_version": self._trace_version,
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
        """Return a copy of terminal status after the fixed sequence validates."""
        if self._terminal_status is None:
            _fail(
                "$records",
                f"incomplete replay: admitted {len(self._records)} of {len(self._steps)} records",
            )
        return _copy_input(self._terminal_status, "$terminal_status")


class M0ReplayController(_FixedReplayController):
    """Admit records for the frozen M0 direct-pass profile."""

    def __init__(self, packet: Any) -> None:
        super().__init__(packet, steps=M0_STEPS, trace_version=M0_TRACE_VERSION)


class M1ReplayController(_FixedReplayController):
    """Admit records for the frozen M1 bounded-remediation profile."""

    def __init__(self, packet: Any) -> None:
        super().__init__(packet, steps=M1_STEPS, trace_version=M1_TRACE_VERSION)


def _source_document(source: Any) -> dict[str, Any]:
    document = _copy_input(source, "$source")
    if type(document) is not dict:
        _fail("$source", "expected object")
    if set(document) != {"schema_version", "records"}:
        _fail("$source", "expected exactly schema_version and records")
    if type(document["schema_version"]) is not str:
        _fail("$source.schema_version", "expected string")
    if type(document["records"]) is not list:
        _fail("$source.records", "expected array")
    return document


def _replay_document(
    packet: Any,
    document: dict[str, Any],
    *,
    trace_version: str,
    controller_type: type[_FixedReplayController],
) -> dict[str, Any]:
    if document["schema_version"] != trace_version:
        _fail("$source.schema_version", f"expected {trace_version!r}")
    controller = controller_type(packet)
    for record in document["records"]:
        controller.accept(record)
    return controller.finish()


def replay_m0_verified_change(packet: Any, source: Any) -> dict[str, Any]:
    """Replay one complete M0 source through its fixed controller."""
    return _replay_document(
        packet,
        _source_document(source),
        trace_version=M0_TRACE_VERSION,
        controller_type=M0ReplayController,
    )


def replay_m1_verified_change(packet: Any, source: Any) -> dict[str, Any]:
    """Replay one complete M1 source through its fixed controller."""
    return _replay_document(
        packet,
        _source_document(source),
        trace_version=M1_TRACE_VERSION,
        controller_type=M1ReplayController,
    )


def replay_verified_change(packet: Any, source: Any) -> dict[str, Any]:
    """Select exactly one frozen source profile and replay it."""
    document = _source_document(source)
    trace_version = document["schema_version"]
    if trace_version == M0_TRACE_VERSION:
        controller_type = M0ReplayController
    elif trace_version == M1_TRACE_VERSION:
        controller_type = M1ReplayController
    else:
        _fail("$source.schema_version", "unsupported fixed replay profile")

    return _replay_document(
        packet,
        document,
        trace_version=trace_version,
        controller_type=controller_type,
    )


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
        sys.stdout.buffer.write(_render(replay_verified_change(packet, source)))
        return 0
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        print(f"verified-change replay failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
