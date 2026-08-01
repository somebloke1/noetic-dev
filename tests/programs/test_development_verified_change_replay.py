"""Tests for fixed-profile incremental verified-change replay."""

from __future__ import annotations

import ast
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from typing import Any
from unittest import mock

import scripts.development_verified_change as program
import scripts.development_verified_change_explain as explain
import scripts.development_verified_change_replay as replay
import scripts.m1_trace as m1_trace
from scripts.m0_trace import load_json_strict
from scripts.m0_trace import validate_and_project as validate_m0_trace


ROOT = Path(__file__).resolve().parents[2]
PROGRAM_ROOT = ROOT / "spec/programs/development.verified-change/v1"
PACKET_PATH = PROGRAM_ROOT / "golden/valid-bounded-remediation-packet.json"
M0_TRACE_PATH = ROOT / "spec/m0/v0/golden/valid-telos-adjudication-trace.json"
M1_TRACE_PATH = ROOT / "spec/m1/v0/golden/valid-telos-recoverability-trace.json"
M1_EXPECTED_PATH = PROGRAM_ROOT / "golden/expected-terminal-status.json"
SCRIPT_PATH = ROOT / "scripts/development_verified_change_replay.py"


def terminal_final(source_projection: dict[str, Any]) -> dict[str, Any]:
    accepted = source_projection["accepted_generation"]
    return {
        "generation": accepted["generation"],
        "accepted_event_id": accepted["event_id"],
        "candidate_id": accepted["candidate_id"],
        "candidate_digest": accepted["candidate_digest"],
        "implementer_actor_id": accepted["implementer_actor_id"],
        "verification_obligation_id": accepted["verification_obligation_id"],
    }


class DevelopmentVerifiedChangeReplayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.packet = load_json_strict(PACKET_PATH)
        self.m1_packet = copy.deepcopy(self.packet)
        self.source = load_json_strict(M0_TRACE_PATH)
        self.m1_source = load_json_strict(M1_TRACE_PATH)
        source_projection = validate_m0_trace(self.source)
        self.packet["execution_profile"] = program.M0_PROFILE
        self.packet["source_trace_version"] = program.M0_TRACE_VERSION
        self.packet["program_instance_id"] = source_projection["binding"]["program_id"]
        self.packet["governing_purpose_id"] = source_projection["delegation"]["purpose"]
        self.packet["source_trace_digest"] = program.source_trace_digest(self.source)
        self.packet["final_implementation"].update(terminal_final(source_projection))

    def test_admits_each_ratified_step_and_preserves_copied_history(self) -> None:
        packet_before = copy.deepcopy(self.packet)
        source_before = copy.deepcopy(self.source)
        controller = replay.M0ReplayController(self.packet)
        self.assertEqual(controller.state, "initial")
        self.assertEqual(controller.next_event_type, replay.M0_STEPS[0][0])

        expected_states = [state for _, state in replay.M0_STEPS]
        first_record = copy.deepcopy(self.source["records"][0])
        self.assertEqual(controller.accept(first_record), expected_states[0])
        first_record["event_id"] = "event-mutated"
        for index, record in enumerate(self.source["records"][1:], 1):
            self.assertEqual(controller.accept(record), expected_states[index])
            self.assertEqual(controller.admitted_count, index + 1)

        self.assertTrue(controller.complete)
        self.assertIsNone(controller.next_event_type)
        self.assertEqual(controller.admitted_records[0], self.source["records"][0])
        self.assertEqual(self.packet, packet_before)
        self.assertEqual(self.source, source_before)
        self.assertEqual(
            controller.finish(),
            explain.explain_verified_change(self.packet, self.source),
        )

    def test_calls_existing_terminal_pipeline_once_only_at_terminal_step(self) -> None:
        controller = replay.M0ReplayController(self.packet)
        with mock.patch.object(
            replay,
            "explain_verified_change",
            wraps=explain.explain_verified_change,
        ) as terminal:
            for record in self.source["records"][:-1]:
                controller.accept(record)
            terminal.assert_not_called()
            controller.accept(self.source["records"][-1])
            terminal.assert_called_once()

    def test_rejected_steps_leave_state_unchanged(self) -> None:
        controller = replay.M0ReplayController(self.packet)
        first = copy.deepcopy(self.source["records"][0])
        wrong_type = copy.deepcopy(first)
        wrong_type["event_type"] = "controller.run.created"
        with self.assertRaisesRegex(replay.ReplayValidationError, "event_type"):
            controller.accept(wrong_type)
        self.assertEqual((controller.state, controller.admitted_count), ("initial", 0))

        controller.accept(first)
        second = copy.deepcopy(self.source["records"][1])
        second["caused_by"] = ["event-wrong"]
        with self.assertRaisesRegex(replay.ReplayValidationError, "caused_by"):
            controller.accept(second)
        self.assertEqual((controller.state, controller.admitted_count), ("delegated", 1))

        replayed = copy.deepcopy(self.source["records"][1])
        replayed["event_id"] = first["event_id"]
        with self.assertRaisesRegex(replay.ReplayValidationError, "replayed"):
            controller.accept(replayed)
        self.assertEqual((controller.state, controller.admitted_count), ("delegated", 1))

    def test_rejects_non_strict_values_without_partial_admission(self) -> None:
        controller = replay.M0ReplayController(self.packet)
        for value in (None, 1.5, {"event_id": object()}):
            with self.subTest(value=value):
                with self.assertRaises(replay.ReplayValidationError):
                    controller.accept(value)
                self.assertEqual(controller.admitted_count, 0)

        subclassed = type("Record", (dict,), {})()
        with self.assertRaisesRegex(replay.ReplayValidationError, "unsupported value type"):
            controller.accept(subclassed)
        self.assertEqual(controller.admitted_count, 0)

    def test_terminal_validation_failure_is_atomic_and_retryable(self) -> None:
        controller = replay.M0ReplayController(self.packet)
        for record in self.source["records"][:-1]:
            controller.accept(record)
        invalid = copy.deepcopy(self.source["records"][-1])
        invalid["payload"]["disposition"] = "blocked"
        with self.assertRaises(ValueError):
            controller.accept(invalid)
        self.assertEqual(controller.state, "result_reported")
        self.assertEqual(controller.admitted_count, 7)
        self.assertFalse(controller.complete)

        controller.accept(self.source["records"][-1])
        self.assertTrue(controller.complete)
        with self.assertRaisesRegex(replay.ReplayValidationError, "additional records"):
            controller.accept(self.source["records"][-1])

    def test_complete_replay_rejects_incomplete_m1_and_wrong_source_shapes(self) -> None:
        incomplete = copy.deepcopy(self.source)
        incomplete["records"].pop()
        with self.assertRaisesRegex(replay.ReplayValidationError, "incomplete replay"):
            replay.replay_m0_verified_change(self.packet, incomplete)

        with self.assertRaisesRegex(replay.ReplayValidationError, "schema_version"):
            replay.replay_m0_verified_change(self.packet, self.m1_source)

        incomplete_m1 = copy.deepcopy(self.m1_source)
        incomplete_m1["records"].pop()
        with self.assertRaisesRegex(replay.ReplayValidationError, "incomplete replay"):
            replay.replay_m1_verified_change(self.m1_packet, incomplete_m1)

        wrong_shape = copy.deepcopy(self.source)
        wrong_shape["extra"] = True
        with self.assertRaisesRegex(replay.ReplayValidationError, "exactly"):
            replay.replay_m0_verified_change(self.packet, wrong_shape)

    def test_cli_emits_existing_terminal_status_bytes_and_fails_cleanly(self) -> None:
        expected = explain.explain_verified_change(self.packet, self.source)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet_path = root / "packet.json"
            source_path = root / "source.json"
            packet_path.write_text(json.dumps(self.packet), encoding="ascii")
            source_path.write_text(json.dumps(self.source), encoding="ascii")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(packet_path), str(source_path)],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            self.assertEqual(
                completed.stdout,
                (json.dumps(expected, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n").encode("ascii"),
            )
            self.assertEqual(completed.stderr, b"")

            source_path.write_text('{"bad":', encoding="ascii")
            failed = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(packet_path), str(source_path)],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
            packet_path.write_text("[" * 5000 + '"x"' + "]" * 5000, encoding="ascii")
            source_path.write_text(json.dumps(self.source), encoding="ascii")
            deeply_nested = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(packet_path), str(source_path)],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
        self.assertEqual(failed.returncode, 1)
        self.assertEqual(failed.stdout, b"")
        self.assertIn(b"verified-change replay failed:", failed.stderr)
        self.assertNotIn(b"Traceback", failed.stderr)
        self.assertEqual(deeply_nested.returncode, 1)
        self.assertEqual(deeply_nested.stdout, b"")
        self.assertIn(b"nesting exceeds recursion limit", deeply_nested.stderr)
        self.assertNotIn(b"Traceback", deeply_nested.stderr)

    def test_m1_uses_canonical_fixed_transitions_and_terminal_golden(self) -> None:
        self.assertEqual(program.M1_TRACE_VERSION, m1_trace.TRACE_VERSION)
        self.assertEqual(
            replay.M1_STEPS,
            tuple((event_type, to_state) for _, event_type, to_state in m1_trace.TRANSITIONS),
        )
        controller = replay.M1ReplayController(self.m1_packet)
        expected_states = [state for _, state in replay.M1_STEPS]
        for index, record in enumerate(self.m1_source["records"]):
            self.assertEqual(controller.accept(record), expected_states[index])
            self.assertEqual(controller.admitted_count, index + 1)
        self.assertTrue(controller.complete)
        self.assertEqual(
            controller.finish(),
            explain.explain_verified_change(self.m1_packet, self.m1_source),
        )

    def test_m1_terminal_validation_is_atomic_and_called_once_per_attempt(self) -> None:
        controller = replay.M1ReplayController(self.m1_packet)
        for record in self.m1_source["records"][:-1]:
            controller.accept(record)
        invalid = copy.deepcopy(self.m1_source["records"][-1])
        invalid["payload"]["disposition"] = "blocked"
        with mock.patch.object(
            replay,
            "explain_verified_change",
            wraps=explain.explain_verified_change,
        ) as terminal:
            with self.assertRaises(ValueError):
                controller.accept(invalid)
            self.assertEqual(controller.state, "result_reported")
            self.assertEqual(controller.admitted_count, 10)
            self.assertFalse(controller.complete)
            controller.accept(self.m1_source["records"][-1])
            self.assertEqual(terminal.call_count, 2)
        self.assertTrue(controller.complete)

    def test_generic_replay_selects_only_m0_and_m1(self) -> None:
        self.assertEqual(
            replay.replay_verified_change(self.packet, self.source),
            replay.replay_m0_verified_change(self.packet, self.source),
        )
        self.assertEqual(
            replay.replay_verified_change(self.m1_packet, self.m1_source),
            replay.replay_m1_verified_change(self.m1_packet, self.m1_source),
        )
        unsupported = copy.deepcopy(self.source)
        unsupported["schema_version"] = "noetic.m2.unsupported/v0"
        with self.assertRaisesRegex(replay.ReplayValidationError, "unsupported"):
            replay.replay_verified_change(self.packet, unsupported)

    def test_cli_emits_exact_existing_m1_terminal_status_golden(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(PACKET_PATH), str(M1_TRACE_PATH)],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        self.assertEqual(completed.stdout, M1_EXPECTED_PATH.read_bytes())
        self.assertEqual(completed.stderr, b"")

    def test_main_normalizes_direct_loader_recursion(self) -> None:
        stderr = io.StringIO()
        with (
            mock.patch.object(
                replay,
                "load_json_strict",
                side_effect=RecursionError("synthetic decoder recursion"),
            ),
            redirect_stderr(stderr),
        ):
            result = replay.main(["packet.json", "source.json"])
        self.assertEqual(result, 1)
        self.assertIn("synthetic decoder recursion", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_argument_errors_return_two_and_leaf_has_no_effect_imports(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, b"")
        self.assertNotIn(b"Traceback", completed.stderr)

        tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
        modules = {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        roots = {module.split(".", 1)[0] for module in modules}
        self.assertTrue(roots.isdisjoint({"os", "subprocess", "socket", "time", "random"}))


if __name__ == "__main__":
    unittest.main()
