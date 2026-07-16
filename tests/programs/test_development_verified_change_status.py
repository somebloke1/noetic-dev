"""Adversarial self-checks for development.verified-change terminal status/v1."""

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
import scripts.development_verified_change_status as status
from scripts.development_verified_change import M0_PROFILE, M0_TRACE_VERSION, M1_PROFILE, source_trace_digest
from scripts.m0_trace import load_json_strict
from scripts.m0_trace import validate_and_project as validate_m0_trace


ROOT = Path(__file__).resolve().parents[2]
PROGRAM_ROOT = ROOT / "spec/programs/development.verified-change/v1"
PACKET_PATH = PROGRAM_ROOT / "golden/valid-bounded-remediation-packet.json"
OBSERVABILITY_PATH = PROGRAM_ROOT / "golden/expected-terminal-observability.json"
EXPECTED_PATH = PROGRAM_ROOT / "golden/expected-terminal-status.json"
CONTRACT_PATH = PROGRAM_ROOT / "terminal-status-contract.json"
DOC_PATH = ROOT / "docs/development-verified-change-terminal-status-v1.md"
SCRIPT_PATH = ROOT / "scripts/development_verified_change_status.py"
M0_TRACE_PATH = ROOT / "spec/m0/v0/golden/valid-telos-adjudication-trace.json"
M1_TRACE_PATH = ROOT / "spec/m1/v0/golden/valid-telos-recoverability-trace.json"


def canonical_status_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n").encode("ascii")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="ascii"))


def terminal_final(source_projection: dict[str, Any], profile: str) -> dict[str, Any]:
    if profile == M0_PROFILE:
        accepted = source_projection["accepted_generation"]
        generation = accepted["generation"]
    else:
        accepted = source_projection["generation_history"][1]["accepted_generation"]
        generation = 2
    return {
        "generation": generation,
        "accepted_event_id": accepted["event_id"],
        "candidate_id": accepted["candidate_id"],
        "candidate_digest": accepted["candidate_digest"],
        "implementer_actor_id": accepted["implementer_actor_id"],
        "verification_obligation_id": accepted["verification_obligation_id"],
    }


class DevelopmentVerifiedChangeStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.packet = load_json_strict(PACKET_PATH)
        self.m1_observability = load_json(OBSERVABILITY_PATH)
        self.expected = load_json(EXPECTED_PATH)
        self.m0_source = load_json_strict(M0_TRACE_PATH)
        self.m1_source = load_json_strict(M1_TRACE_PATH)

    def m0_observability(self) -> dict[str, Any]:
        packet = copy.deepcopy(self.packet)
        source_projection = validate_m0_trace(self.m0_source)
        packet["execution_profile"] = M0_PROFILE
        packet["source_trace_version"] = M0_TRACE_VERSION
        packet["program_instance_id"] = source_projection["binding"]["program_id"]
        packet["governing_purpose_id"] = source_projection["delegation"]["purpose"]
        packet["source_trace_digest"] = source_trace_digest(self.m0_source)
        packet["final_implementation"].update(terminal_final(source_projection, M0_PROFILE))
        projection = program.validate_and_project(packet, self.m0_source)
        return observer.derive_terminal_observability(projection)

    def assert_rejected(self, mutate: Callable[[dict[str, Any]], None]) -> None:
        candidate = copy.deepcopy(self.m1_observability)
        mutate(candidate)
        with self.assertRaises(status.TerminalStatusCompatibilityError):
            status.derive_terminal_status(candidate)

    def test_m1_golden_derives_exact_canonical_terminal_status(self) -> None:
        derived = status.derive_terminal_status(self.m1_observability)
        self.assertEqual(derived, self.expected)
        self.assertEqual(canonical_status_bytes(derived), EXPECTED_PATH.read_bytes())
        self.assertEqual(list(derived), [
            "schema_version",
            "scope",
            "subject",
            "controller_status",
            "telos_status",
            "qa_status",
            "remediation_status",
            "operational_status",
            "references",
            "explicit_unknowns",
        ])

    def test_m0_profile_preserves_no_remediation_and_no_generation_synthesis(self) -> None:
        derived = status.derive_terminal_status(self.m0_observability())
        self.assertEqual(derived["subject"]["execution_profile"], M0_PROFILE)
        self.assertEqual(derived["remediation_status"], {"represented": False, "no_zero_budget_inferred": True})
        self.assertNotIn("generation", derived["controller_status"])
        self.assertNotIn("generation", derived["telos_status"])
        self.assertEqual(len(derived["qa_status"]["generations"]), 1)

    def test_m1_status_keeps_controller_telos_qa_and_operational_boundaries(self) -> None:
        derived = status.derive_terminal_status(self.m1_observability)
        self.assertEqual(derived["controller_status"]["run_outcome"], "succeeded")
        self.assertNotIn("disposition", derived["controller_status"])
        self.assertEqual(derived["telos_status"]["disposition"], "complete")
        self.assertNotIn("run_outcome", derived["telos_status"])
        self.assertEqual([item["conclusion"] for item in derived["qa_status"]["generations"]], ["FAIL", "PASS"])
        self.assertTrue(derived["qa_status"]["semantic_truth_not_judged"])
        self.assertEqual(
            {entry["status"] for entry in derived["operational_status"].values()},
            {"not_derivable_from_terminal_projection"},
        )
        self.assertNotEqual(derived["operational_status"]["readiness"]["status"], "ready")

    def test_derivation_is_fresh_and_does_not_mutate_input(self) -> None:
        candidate = copy.deepcopy(self.m1_observability)
        original = copy.deepcopy(candidate)
        derived = status.derive_terminal_status(candidate)
        derived["subject"]["source"]["binding"]["run_id"] = "changed"
        derived["controller_status"]["evidence_event_ids"].append("changed")
        self.assertEqual(candidate, original)

    def test_pure_function_does_not_use_external_effect_surfaces(self) -> None:
        with mock.patch("pathlib.Path.read_text", side_effect=AssertionError("unexpected file read")):
            with mock.patch("pathlib.Path.write_text", side_effect=AssertionError("unexpected file write")):
                with mock.patch("subprocess.run", side_effect=AssertionError("unexpected process")):
                    status.derive_terminal_status(copy.deepcopy(self.m1_observability))

    def test_compatibility_guard_rejects_overclaims_and_bad_types(self) -> None:
        cases: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
            ("unknown root", lambda data: data.__setitem__("extra", True)),
            ("wrong version", lambda data: data.__setitem__("schema_version", "development.verified-change.terminal-observability/v2")),
            ("unknown profile", lambda data: data["subject"].__setitem__("execution_profile", "future")),
            ("controller disposition overclaim", lambda data: data["controller"]["result"].__setitem__("disposition", "complete")),
            ("telos run outcome overclaim", lambda data: data["telos"]["adjudication"]["adjudication"].__setitem__("run_outcome", "succeeded")),
            ("bad controller evidence", lambda data: data["controller"]["result"].__setitem__("evidence_event_ids", [True])),
            ("bad telos generation", lambda data: data["telos"]["adjudication"]["adjudication"].__setitem__("generation", True)),
            ("missing final candidate", lambda data: data["evidence"]["final_implementation"]["value"].pop("candidate_id")),
            ("null remediation", lambda data: data.__setitem__("remediation", None)),
            ("null accepted generation", lambda data: data["qa"]["generation_history"][0].__setitem__("accepted_generation", None)),
            ("boolean qa adjudication", lambda data: data["qa"]["generation_history"][0].__setitem__("qa_adjudication", True)),
            ("bad unknown order", lambda data: data["explicit_unknowns"].reverse()),
            ("readiness smuggled", lambda data: data.__setitem__("readiness", "ready")),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                self.assert_rejected(mutate)

    def test_m0_rejects_remediation_normalization(self) -> None:
        m0 = self.m0_observability()
        m1_remediation = copy.deepcopy(self.m1_observability["remediation"])
        m1_false_remediation = copy.deepcopy(m1_remediation)
        m1_false_remediation["represented"] = False
        for value in ({"represented": False, "budget": {"authorized": 0}}, {"represented": None}, {"represented": True}, m1_remediation, m1_false_remediation):
            with self.subTest(value=value):
                candidate = copy.deepcopy(m0)
                candidate["remediation"] = value
                with self.assertRaises(status.TerminalStatusCompatibilityError):
                    status.derive_terminal_status(candidate)

    def test_m1_rejects_absent_remediation_profile_confusion(self) -> None:
        candidate = copy.deepcopy(self.m1_observability)
        candidate["remediation"] = {"represented": False}
        with self.assertRaises(status.TerminalStatusCompatibilityError):
            status.derive_terminal_status(candidate)

    def test_profile_bound_qa_history_rejects_cross_profile_shapes(self) -> None:
        m0 = self.m0_observability()
        m0["qa"]["generation_history"] = copy.deepcopy(self.m1_observability["qa"]["generation_history"])
        with self.assertRaises(status.TerminalStatusCompatibilityError):
            status.derive_terminal_status(m0)
        m1 = copy.deepcopy(self.m1_observability)
        m1["qa"]["generation_history"] = copy.deepcopy(self.m0_observability()["qa"]["generation_history"])
        with self.assertRaises(status.TerminalStatusCompatibilityError):
            status.derive_terminal_status(m1)

    def test_cli_modes_utf8_input_and_failures_are_controlled(self) -> None:
        completed = subprocess.run([sys.executable, str(SCRIPT_PATH), str(OBSERVABILITY_PATH)], cwd=ROOT, check=False, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        self.assertEqual(completed.stdout, EXPECTED_PATH.read_bytes())
        checked = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--check", str(OBSERVABILITY_PATH), str(EXPECTED_PATH)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn("passed exact status check", checked.stdout)

        utf8_model = copy.deepcopy(self.m1_observability)
        utf8_model["subject"]["program_instance_id"] = "program-r\u00e9f\u6f22"
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            utf8_path = temp / "utf8.json"
            utf8_path.write_text(json.dumps(utf8_model, ensure_ascii=False), encoding="utf-8")
            duplicate = temp / "duplicate.json"
            duplicate.write_text('{"schema_version":"x","schema_version":"y"}\n', encoding="utf-8")
            noncanonical = temp / "noncanonical.json"
            noncanonical.write_text(json.dumps(self.expected, sort_keys=True), encoding="utf-8")
            wrong = temp / "wrong.json"
            wrong_model = copy.deepcopy(self.expected)
            wrong_model["operational_status"]["readiness"]["status"] = "ready"
            wrong.write_bytes(canonical_status_bytes(wrong_model))
            utf8 = subprocess.run([sys.executable, str(SCRIPT_PATH), str(utf8_path)], cwd=ROOT, check=False, capture_output=True)
            self.assertEqual(utf8.returncode, 0, utf8.stderr.decode())
            utf8.stdout.decode("ascii")
            self.assertIn(b"\\u00e9", utf8.stdout)
            for argv, expected_stderr in (
                ([str(SCRIPT_PATH), str(duplicate)], "duplicate object key"),
                ([str(SCRIPT_PATH), "--check", str(OBSERVABILITY_PATH), str(noncanonical)], "not canonical presentation JSON bytes"),
                ([str(SCRIPT_PATH), "--check", str(OBSERVABILITY_PATH), str(wrong)], "does not match expected bytes"),
            ):
                result = subprocess.run([sys.executable, *argv], cwd=ROOT, check=False, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn(expected_stderr, result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_cli_argument_failure_returns_two(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPT_PATH), "--check", str(OBSERVABILITY_PATH)], cwd=ROOT, check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("--check requires", result.stderr)

    def test_import_boundary_docs_and_contract_are_aligned(self) -> None:
        tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertEqual(sorted(imports), ["__future__", "argparse", "copy", "json", "pathlib", "sys", "typing"])
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        for forbidden in ("development_verified_change", "development_verified_change_observe", "m0_trace", "m1_trace", "hashlib", "requests", "socket", "os.environ"):
            self.assertNotIn(forbidden, source)
        contract = load_json(CONTRACT_PATH)
        doc = DOC_PATH.read_text(encoding="utf-8")
        self.assertEqual(contract["read_model_version"], status.OUTPUT_VERSION)
        self.assertEqual(contract["explicit_unknowns"], list(status.REQUIRED_UNKNOWNS))
        for phrase in ("not_derivable_from_terminal_projection", "no command authority", "does not import or call", "does not authenticate"):
            self.assertIn(phrase, doc)


if __name__ == "__main__":
    unittest.main()
