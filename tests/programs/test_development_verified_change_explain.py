"""Tests for the provider-free one-shot verified-change explanation."""

from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import scripts.development_verified_change as program
import scripts.development_verified_change_explain as explain
import scripts.development_verified_change_observe as observer
import scripts.development_verified_change_status as status
from scripts.m0_trace import load_json_strict
from scripts.m0_trace import validate_and_project as validate_m0_trace


ROOT = Path(__file__).resolve().parents[2]
PROGRAM_ROOT = ROOT / "spec/programs/development.verified-change/v1"
PACKET_PATH = PROGRAM_ROOT / "golden/valid-bounded-remediation-packet.json"
EXPECTED_PATH = PROGRAM_ROOT / "golden/expected-terminal-status.json"
M0_TRACE_PATH = ROOT / "spec/m0/v0/golden/valid-telos-adjudication-trace.json"
M1_TRACE_PATH = ROOT / "spec/m1/v0/golden/valid-telos-recoverability-trace.json"
SCRIPT_PATH = ROOT / "scripts/development_verified_change_explain.py"


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


class DevelopmentVerifiedChangeExplainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.packet = load_json_strict(PACKET_PATH)
        self.m0_source = load_json_strict(M0_TRACE_PATH)
        self.m1_source = load_json_strict(M1_TRACE_PATH)

    def m0_packet(self) -> dict[str, Any]:
        packet = copy.deepcopy(self.packet)
        source_projection = validate_m0_trace(self.m0_source)
        packet["execution_profile"] = program.M0_PROFILE
        packet["source_trace_version"] = program.M0_TRACE_VERSION
        packet["program_instance_id"] = source_projection["binding"]["program_id"]
        packet["governing_purpose_id"] = source_projection["delegation"]["purpose"]
        packet["source_trace_digest"] = program.source_trace_digest(self.m0_source)
        packet["final_implementation"].update(terminal_final(source_projection))
        return packet

    def test_m1_golden_emits_existing_terminal_status_bytes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(PACKET_PATH), str(M1_TRACE_PATH)],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        self.assertEqual(completed.stdout, EXPECTED_PATH.read_bytes())
        self.assertEqual(completed.stderr, b"")

    def test_m0_explanation_preserves_one_generation_without_remediation(self) -> None:
        result = explain.explain_verified_change(self.m0_packet(), self.m0_source)
        self.assertEqual(result["subject"]["execution_profile"], program.M0_PROFILE)
        self.assertEqual(len(result["qa_status"]["generations"]), 1)
        self.assertEqual(
            result["remediation_status"],
            {"represented": False, "no_zero_budget_inferred": True},
        )
        self.assertEqual(
            result["scope"]["input_provenance"],
            "upstream_precondition_not_authenticated",
        )

    def test_composition_calls_each_existing_stage_once(self) -> None:
        with (
            mock.patch.object(
                explain,
                "validate_and_project",
                wraps=program.validate_and_project,
            ) as project,
            mock.patch.object(
                explain,
                "derive_terminal_observability",
                wraps=observer.derive_terminal_observability,
            ) as observe,
            mock.patch.object(
                explain,
                "derive_terminal_status",
                wraps=status.derive_terminal_status,
            ) as derive_status,
        ):
            result = explain.explain_verified_change(self.packet, self.m1_source)
        self.assertEqual(result["schema_version"], status.OUTPUT_VERSION)
        project.assert_called_once()
        observe.assert_called_once()
        derive_status.assert_called_once()

    def test_invalid_inputs_fail_cleanly_without_intermediate_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet_path = root / "packet.json"
            source_path = root / "source.json"
            packet_path.write_text('{"bad":', encoding="ascii")
            source_path.write_bytes(M1_TRACE_PATH.read_bytes())
            before = sorted(path.name for path in root.iterdir())
            completed = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(packet_path), str(source_path)],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
            after = sorted(path.name for path in root.iterdir())
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, b"")
        self.assertIn(b"verified-change explanation failed:", completed.stderr)
        self.assertNotIn(b"Traceback", completed.stderr)
        self.assertEqual(after, before)

    def test_argument_failure_returns_two(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, b"")
        self.assertNotIn(b"Traceback", completed.stderr)

    def test_leaf_facade_has_no_external_effect_imports(self) -> None:
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
        self.assertTrue(
            {
                "scripts.development_verified_change",
                "scripts.development_verified_change_observe",
                "scripts.development_verified_change_status",
            }
            <= modules
        )
        roots = {module.split(".", 1)[0] for module in modules}
        self.assertTrue(roots.isdisjoint({"os", "subprocess", "socket", "time", "requests"}))


if __name__ == "__main__":
    unittest.main()
