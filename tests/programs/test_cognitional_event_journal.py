"""Tests for the bounded cognitional-event journal."""

from __future__ import annotations

import ast
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import scripts.cognitional_event_journal as journal
import scripts.development_verified_change as program
import scripts.development_verified_change_explain as explain
import scripts.development_verified_change_replay as replay
from scripts.m0_trace import canonical_json_bytes, load_json_strict
from scripts.m0_trace import validate_and_project as validate_m0_trace


ROOT = Path(__file__).resolve().parents[2]
PROGRAM_ROOT = ROOT / "spec/programs/development.verified-change/v1"
PACKET_PATH = PROGRAM_ROOT / "golden/valid-bounded-remediation-packet.json"
M0_TRACE_PATH = ROOT / "spec/m0/v0/golden/valid-telos-adjudication-trace.json"
CONTRACT_PATH = ROOT / "spec/events/v1/cognitional-event-journal-contract.json"
DOC_PATH = ROOT / "docs/cognitional-event-journal-v1.md"
SCRIPT_PATH = ROOT / "scripts/cognitional_event_journal.py"


def m0_packet(source: dict[str, Any]) -> dict[str, Any]:
    packet = load_json_strict(PACKET_PATH)
    projection = validate_m0_trace(source)
    accepted = projection["accepted_generation"]
    packet["execution_profile"] = program.M0_PROFILE
    packet["source_trace_version"] = program.M0_TRACE_VERSION
    packet["program_instance_id"] = projection["binding"]["program_id"]
    packet["governing_purpose_id"] = projection["delegation"]["purpose"]
    packet["source_trace_digest"] = program.source_trace_digest(source)
    packet["final_implementation"].update(
        {
            "generation": accepted["generation"],
            "accepted_event_id": accepted["event_id"],
            "candidate_id": accepted["candidate_id"],
            "candidate_digest": accepted["candidate_digest"],
            "implementer_actor_id": accepted["implementer_actor_id"],
            "verification_obligation_id": accepted["verification_obligation_id"],
        }
    )
    return packet


class CognitionalEventJournalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = load_json_strict(M0_TRACE_PATH)
        self.packet = m0_packet(self.source)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "events.jsonl"

    def append_prefix(self, count: int) -> dict[str, Any]:
        state: dict[str, Any] = {}
        for record in self.source["records"][:count]:
            state = journal.append_event(self.path, self.packet, record)
        return state

    def test_restart_replay_after_every_prefix_reaches_existing_terminal_consumer(self) -> None:
        expected_states = [state for _, state in replay.M0_STEPS]
        expected_bytes = b""
        for index, record in enumerate(self.source["records"]):
            expected_bytes += canonical_json_bytes(record)
            state = journal.append_event(self.path, self.packet, record)
            self.assertEqual(self.path.read_bytes(), expected_bytes)
            self.assertEqual(state, journal.inspect_journal(self.path, self.packet))
            self.assertEqual(state["record_count"], index + 1)
            self.assertEqual(state["state"], expected_states[index])
            if index < 7:
                self.assertFalse(state["complete"])
                self.assertEqual(
                    state["next_event_type"],
                    self.source["records"][index + 1]["event_type"],
                )
                self.assertNotIn("terminal_status", state)
            else:
                self.assertTrue(state["complete"])
                self.assertNotIn("next_event_type", state)
                self.assertEqual(
                    state["terminal_status"],
                    explain.explain_verified_change(self.packet, self.source),
                )

        self.assertEqual(
            journal.parse_journal_bytes(self.path.read_bytes()),
            self.source["records"],
        )

    def test_missing_journal_is_initial_and_all_versions_are_explicit(self) -> None:
        state = journal.inspect_journal(self.path, self.packet)
        self.assertEqual(
            state,
            {
                "schema_version": journal.READ_MODEL_VERSION,
                "journal_version": journal.JOURNAL_VERSION,
                "consumer_id": journal.CONSUMER_ID,
                "record_version": journal.RECORD_VERSION,
                "record_count": 0,
                "state": "initial",
                "complete": False,
                "next_event_type": "telos.delegation.authorized",
            },
        )
        self.assertFalse(self.path.exists())

    def test_rejected_order_cause_duplicate_size_and_ninth_event_preserve_bytes(self) -> None:
        wrong_order = copy.deepcopy(self.source["records"][1])
        with self.assertRaisesRegex(ValueError, "event_type"):
            journal.append_event(self.path, self.packet, wrong_order)
        self.assertFalse(self.path.exists())

        self.append_prefix(1)
        before = self.path.read_bytes()
        duplicate = copy.deepcopy(self.source["records"][1])
        duplicate["event_id"] = self.source["records"][0]["event_id"]
        wrong_cause = copy.deepcopy(self.source["records"][1])
        wrong_cause["caused_by"] = ["event-wrong"]
        missing_attribution = copy.deepcopy(self.source["records"][1])
        missing_attribution.pop("actor")
        oversized = copy.deepcopy(self.source["records"][1])
        oversized["payload"]["padding"] = "x" * journal.MAX_RECORD_BYTES
        for candidate, message in (
            (duplicate, "replayed"),
            (wrong_cause, "caused_by"),
            (missing_attribution, "expected exactly"),
            (oversized, "canonical bytes"),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    journal.append_event(self.path, self.packet, candidate)
                self.assertEqual(self.path.read_bytes(), before)

        for record in self.source["records"][1:]:
            journal.append_event(self.path, self.packet, record)
        terminal = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "additional records"):
            journal.append_event(self.path, self.packet, self.source["records"][-1])
        self.assertEqual(self.path.read_bytes(), terminal)

    def test_invalid_terminal_append_is_atomic_and_valid_retry_completes(self) -> None:
        self.append_prefix(7)
        before = self.path.read_bytes()
        invalid = copy.deepcopy(self.source["records"][-1])
        invalid["payload"]["disposition"] = "blocked"
        with self.assertRaises(ValueError):
            journal.append_event(self.path, self.packet, invalid)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(journal.inspect_journal(self.path, self.packet)["record_count"], 7)

        state = journal.append_event(
            self.path,
            self.packet,
            self.source["records"][-1],
        )
        self.assertTrue(state["complete"])

    def test_explicit_recovery_removes_only_an_unterminated_tail(self) -> None:
        self.append_prefix(2)
        prefix = self.path.read_bytes()
        fragment = b'{"event_id":"event-torn"'
        with self.path.open("ab") as handle:
            handle.write(fragment)
        with self.assertRaisesRegex(ValueError, "explicit recovery"):
            journal.inspect_journal(self.path, self.packet)

        state = journal.recover_trailing_fragment(self.path, self.packet)
        self.assertEqual(self.path.read_bytes(), prefix)
        self.assertEqual(state["record_count"], 2)
        self.assertEqual(state["next_event_type"], "controller.run.started")
        journal.append_event(self.path, self.packet, self.source["records"][2])

        valid_prefix = self.path.read_bytes()
        corruption = b"not-json\n{\"torn\""
        self.path.write_bytes(valid_prefix + corruption)
        corrupted = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            journal.recover_trailing_fragment(self.path, self.packet)
        self.assertEqual(self.path.read_bytes(), corrupted)

    def test_complete_noncanonical_or_malformed_records_are_never_repaired(self) -> None:
        record = self.source["records"][0]
        cases = (
            (json.dumps(record).encode("ascii") + b"\n", "not canonical"),
            (b"not-json\n", "invalid JSON"),
            (canonical_json_bytes(record) * 2, "event_type"),
        )
        for data, message in cases:
            with self.subTest(message=message):
                self.path.write_bytes(data)
                before = self.path.read_bytes()
                with self.assertRaisesRegex(ValueError, message):
                    journal.recover_trailing_fragment(self.path, self.packet)
                self.assertEqual(self.path.read_bytes(), before)

    def test_cli_append_inspect_recover_and_hash_seed_output_are_deterministic(self) -> None:
        packet_path = self.root / "packet.json"
        record_path = self.root / "record.json"
        packet_path.write_bytes(canonical_json_bytes(self.packet))
        record_path.write_bytes(canonical_json_bytes(self.source["records"][0]))
        appended = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "append",
                str(packet_path),
                str(self.path),
                str(record_path),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
        self.assertEqual(appended.returncode, 0, appended.stderr.decode())
        self.assertEqual(appended.stderr, b"")

        expected = appended.stdout
        for seed in ("0", "1", "42", "random"):
            environment = os.environ.copy()
            environment["PYTHONHASHSEED"] = seed
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            inspected = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "inspect",
                    str(packet_path),
                    str(self.path),
                ],
                cwd=ROOT,
                env=environment,
                check=False,
                capture_output=True,
            )
            self.assertEqual(inspected.returncode, 0, inspected.stderr.decode())
            self.assertEqual(inspected.stdout, expected)
            self.assertEqual(inspected.stderr, b"")

        with self.path.open("ab") as handle:
            handle.write(b'{"torn"')
        recovered = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "recover",
                str(packet_path),
                str(self.path),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
        self.assertEqual(recovered.returncode, 0, recovered.stderr.decode())
        self.assertEqual(recovered.stdout, expected)

        failed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
        self.assertEqual(failed.returncode, 2)
        self.assertEqual(failed.stdout, b"")
        self.assertNotIn(b"Traceback", failed.stderr)

    def test_contract_matches_runtime_and_keeps_provider_free_boundary(self) -> None:
        contract = load_json_strict(CONTRACT_PATH)
        self.assertEqual(contract["journal_version"], journal.JOURNAL_VERSION)
        self.assertEqual(contract["read_model_version"], journal.READ_MODEL_VERSION)
        self.assertEqual(contract["consumer"]["consumer_id"], journal.CONSUMER_ID)
        self.assertEqual(contract["record_contract"]["record_version"], journal.RECORD_VERSION)
        self.assertEqual(contract["storage"]["max_records"], journal.MAX_RECORDS)
        self.assertEqual(
            contract["storage"]["max_record_bytes_including_lf"],
            journal.MAX_RECORD_BYTES,
        )
        self.assertEqual(
            contract["storage"]["max_journal_bytes"],
            journal.MAX_JOURNAL_BYTES,
        )
        self.assertEqual(
            contract["event_sequence"],
            [event_type for event_type, _ in replay.M0_STEPS],
        )
        self.assertEqual(
            contract["record_contract"]["envelope_fields"],
            list(journal.RECORD_FIELDS),
        )
        self.assertTrue(DOC_PATH.is_file())

        tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
        modules = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        modules.update(
            (node.module or "").split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        self.assertTrue(
            modules.isdisjoint(
                {"socket", "subprocess", "time", "random", "requests", "litellm"}
            )
        )
if __name__ == "__main__":
    unittest.main()
