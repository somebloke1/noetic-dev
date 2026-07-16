"""Adversarial self-checks for development.verified-change terminal observability/v1."""

from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable
from unittest import mock

import scripts.development_verified_change as program
import scripts.development_verified_change_observe as observer
from scripts.development_verified_change import M0_PROFILE, M0_TRACE_VERSION, M1_PROFILE, source_trace_digest
from scripts.m0_trace import canonical_json_bytes, load_json_strict
from scripts.m0_trace import validate_and_project as validate_m0_trace


ROOT = Path(__file__).resolve().parents[2]
PROGRAM_ROOT = ROOT / "spec/programs/development.verified-change/v1"
PACKET_PATH = PROGRAM_ROOT / "golden/valid-bounded-remediation-packet.json"
PROJECTION_PATH = PROGRAM_ROOT / "golden/expected-projection.json"
EXPECTED_PATH = PROGRAM_ROOT / "golden/expected-terminal-observability.json"
CONTRACT_PATH = PROGRAM_ROOT / "terminal-observability-contract.json"
DOC_PATH = ROOT / "docs/development-verified-change-terminal-observability-v1.md"
SCRIPT_PATH = ROOT / "scripts/development_verified_change_observe.py"
M0_TRACE_PATH = ROOT / "spec/m0/v0/golden/valid-telos-adjudication-trace.json"
M1_TRACE_PATH = ROOT / "spec/m1/v0/golden/valid-telos-recoverability-trace.json"


def canonical_observer_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n").encode("ascii")


def load_ascii_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="ascii"))


def terminal_final(source_projection: dict[str, Any], profile: str) -> dict[str, Any]:
    if profile == M0_PROFILE:
        accepted = source_projection["accepted_generation"]
        generation = accepted["generation"]
    else:
        history = source_projection["generation_history"][1]
        accepted = history["accepted_generation"]
        generation = history["generation"]
    return {
        "generation": generation,
        "accepted_event_id": accepted["event_id"],
        "candidate_id": accepted["candidate_id"],
        "candidate_digest": accepted["candidate_digest"],
        "implementer_actor_id": accepted["implementer_actor_id"],
        "verification_obligation_id": accepted["verification_obligation_id"],
    }


class DevelopmentVerifiedChangeObserveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.packet = load_json_strict(PACKET_PATH)
        self.m1_projection = load_ascii_json(PROJECTION_PATH)
        self.expected = load_ascii_json(EXPECTED_PATH)
        self.m0_source = load_json_strict(M0_TRACE_PATH)
        self.m1_source = load_json_strict(M1_TRACE_PATH)

    def m0_projection(self) -> dict[str, Any]:
        packet = copy.deepcopy(self.packet)
        source_projection = validate_m0_trace(self.m0_source)
        packet["execution_profile"] = M0_PROFILE
        packet["source_trace_version"] = M0_TRACE_VERSION
        packet["program_instance_id"] = source_projection["binding"]["program_id"]
        packet["governing_purpose_id"] = source_projection["delegation"]["purpose"]
        packet["source_trace_digest"] = source_trace_digest(self.m0_source)
        packet["final_implementation"].update(terminal_final(source_projection, M0_PROFILE))
        return program.validate_and_project(packet, self.m0_source)

    def assert_rejected(self, mutate: Callable[[dict[str, Any]], None]) -> None:
        candidate = copy.deepcopy(self.m1_projection)
        mutate(candidate)
        with self.assertRaises(observer.ObservabilityCompatibilityError):
            observer.derive_terminal_observability(candidate)

    def test_m1_golden_derives_exact_canonical_terminal_read_model(self) -> None:
        derived = observer.derive_terminal_observability(self.m1_projection)
        self.assertEqual(derived, self.expected)
        self.assertEqual(canonical_observer_bytes(derived), EXPECTED_PATH.read_bytes())
        self.assertEqual(derived["schema_version"], observer.OUTPUT_VERSION)
        self.assertEqual(list(derived), CONTRACT_PATH.read_text(encoding="ascii") and [
            "schema_version",
            "scope",
            "subject",
            "evidence",
            "qa",
            "remediation",
            "controller",
            "telos",
            "explicit_unknowns",
        ])

    def test_m0_profile_is_derived_without_normalizing_absent_remediation(self) -> None:
        projection = self.m0_projection()
        derived = observer.derive_terminal_observability(projection)
        self.assertEqual(derived["subject"]["execution_profile"], M0_PROFILE)
        self.assertEqual(derived["remediation"], {"represented": False})
        self.assertNotIn("remediation_budget", derived["remediation"])
        self.assertEqual(len(derived["qa"]["generation_history"]), 1)
        self.assertEqual(derived["qa"]["generation_history"][0]["generation"], 1)
        self.assertEqual(derived["subject"]["source"]["binding"], projection["source_trace_projection"]["binding"])

    def test_m1_profile_preserves_failure_remediation_and_telos_controller_boundary(self) -> None:
        derived = observer.derive_terminal_observability(self.m1_projection)
        self.assertEqual(
            [item["qa_adjudication"]["conclusion"] for item in derived["qa"]["generation_history"]],
            ["FAIL", "PASS"],
        )
        self.assertEqual(derived["remediation"]["remediation_budget"], {"authorized": 1, "consumed": 1, "remaining": 0})
        self.assertEqual(derived["controller"], self.m1_projection["gates"]["controller_result"])
        self.assertEqual(derived["telos"]["adjudication"], self.m1_projection["gates"]["telos_adjudication"])
        controller_text = json.dumps(derived["controller"], sort_keys=True)
        self.assertNotIn("complete", controller_text)
        self.assertNotIn("disposition", controller_text)
        self.assertNotIn("readiness", controller_text)

    def test_projection_is_not_mutated_and_output_is_fresh(self) -> None:
        projection = copy.deepcopy(self.m1_projection)
        original = copy.deepcopy(projection)
        derived = observer.derive_terminal_observability(projection)
        derived["evidence"]["attention"]["value"]["packet_id"] = "changed-after-return"
        derived["subject"]["source"]["binding"]["run_id"] = "changed-after-return"
        self.assertEqual(projection, original)
        self.assertEqual(projection["attention_packet"]["packet_id"], original["attention_packet"]["packet_id"])
        self.assertEqual(projection["source_trace_projection"]["binding"]["run_id"], original["source_trace_projection"]["binding"]["run_id"])

    def test_pure_function_does_not_use_external_effect_surfaces(self) -> None:
        with mock.patch("pathlib.Path.read_text", side_effect=AssertionError("unexpected file read")):
            with mock.patch("pathlib.Path.write_text", side_effect=AssertionError("unexpected file write")):
                with mock.patch("subprocess.run", side_effect=AssertionError("unexpected process")):
                    observer.derive_terminal_observability(copy.deepcopy(self.m1_projection))

    def test_compatibility_guard_rejects_unknown_versions_shapes_and_types(self) -> None:
        cases: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
            ("unknown root field", lambda data: data.__setitem__("extra", "field")),
            ("wrong schema", lambda data: data.__setitem__("schema_version", "development.verified-change.projection/v2")),
            ("unsupported profile", lambda data: data.__setitem__("execution_profile", "future-profile")),
            ("semantic source packet", lambda data: data.__setitem__("source_packet", {})),
            ("bad final binding event type", lambda data: data["gates"]["final_implementation_binding"].__setitem__("accepted_event_id", True)),
            ("bad m1 controller success generation", lambda data: data["source_trace_projection"]["controller_success"].__setitem__("generation", "2")),
            ("bad remediation budget", lambda data: data["gates"]["remediation"]["remediation_budget"].__setitem__("remaining", "0")),
            ("bad copied controller evidence type", lambda data: data["gates"]["controller_result"]["result"].__setitem__("evidence_event_ids", [True])),
            ("bad copied telos generation type", lambda data: data["gates"]["telos_adjudication"]["adjudication"].__setitem__("generation", True)),
            ("controller overclaim", lambda data: data["gates"]["controller_result"]["result"].__setitem__("disposition", "complete")),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                self.assert_rejected(mutate)

    def test_m0_guard_rejects_remediation_normalization(self) -> None:
        projection = self.m0_projection()
        for value in ({"represented": False, "remediation_budget": {"authorized": 0}}, {"represented": None}, {"represented": True}):
            with self.subTest(value=value):
                candidate = copy.deepcopy(projection)
                candidate["gates"]["remediation"] = value
                with self.assertRaises(observer.ObservabilityCompatibilityError):
                    observer.derive_terminal_observability(candidate)

    def test_cli_check_and_non_check_modes_are_exact_and_controlled(self) -> None:
        non_check = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(PROJECTION_PATH)],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
        self.assertEqual(non_check.returncode, 0, non_check.stderr.decode())
        self.assertEqual(non_check.stdout, EXPECTED_PATH.read_bytes())
        self.assertEqual(non_check.stderr, b"")

        checked = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--check", str(PROJECTION_PATH), str(EXPECTED_PATH)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn("passed exact read-model check", checked.stdout)
        self.assertEqual(checked.stderr, "")

    def test_cli_rejects_bad_json_noncanonical_expected_and_wrong_expected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            duplicate = temp / "duplicate.json"
            duplicate.write_text('{"schema_version":"x","schema_version":"y"}\n', encoding="ascii")
            noncanonical = temp / "noncanonical.json"
            noncanonical.write_text(json.dumps(self.expected, sort_keys=True), encoding="ascii")
            wrong = temp / "wrong.json"
            wrong_model = copy.deepcopy(self.expected)
            wrong_model["explicit_unknowns"] = list(reversed(wrong_model["explicit_unknowns"]))
            wrong.write_bytes(canonical_observer_bytes(wrong_model))
            cases = (
                ([str(SCRIPT_PATH), str(duplicate)], "duplicate object key"),
                ([str(SCRIPT_PATH), "--check", str(PROJECTION_PATH), str(noncanonical)], "not canonical presentation JSON bytes"),
                ([str(SCRIPT_PATH), "--check", str(PROJECTION_PATH), str(wrong)], "does not match expected bytes"),
            )
            for argv, stderr in cases:
                with self.subTest(stderr=stderr):
                    completed = subprocess.run(
                        [sys.executable, *argv],
                        cwd=ROOT,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(completed.returncode, 1)
                    self.assertEqual(completed.stdout, "")
                    self.assertIn(stderr, completed.stderr)
                    self.assertNotIn("Traceback", completed.stderr)

    def test_cli_argument_failures_return_two(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--check", str(PROJECTION_PATH)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("--check requires", completed.stderr)

    def test_observer_imports_only_standard_library(self) -> None:
        tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertEqual(sorted(imports), ["__future__", "argparse", "copy", "json", "pathlib", "sys", "typing"])
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        for forbidden in ("development_verified_change", "m0_trace", "m1_trace", "requests", "socket", "os.environ"):
            self.assertNotIn(forbidden, source)

    def test_docs_contract_and_golden_keep_boundary_terms_in_sync(self) -> None:
        contract = load_ascii_json(CONTRACT_PATH)
        doc = DOC_PATH.read_text(encoding="utf-8")
        self.assertEqual(contract["read_model_version"], observer.OUTPUT_VERSION)
        self.assertEqual(contract["input_projection_version"], observer.INPUT_VERSION)
        self.assertEqual(contract["explicit_unknowns"], list(observer.EXPLICIT_UNKNOWNS))
        self.assertEqual(self.expected["explicit_unknowns"], list(observer.EXPLICIT_UNKNOWNS))
        for phrase in (
            "not another source validator",
            "do not authenticate",
            "does not import or call the program, M0, or M1 reducers",
            "current_command_authority",
            "causality_not_preserved_in_projection",
        ):
            self.assertIn(phrase, doc)

    def test_existing_m1_program_projection_remains_byte_identical(self) -> None:
        self.assertEqual(canonical_json_bytes(self.m1_projection), PROJECTION_PATH.read_bytes())


if __name__ == "__main__":
    unittest.main()
