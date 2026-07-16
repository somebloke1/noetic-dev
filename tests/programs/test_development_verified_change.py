"""Adversarial self-checks for development.verified-change/v1."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable
from unittest import mock

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:
    Draft202012Validator = None

import scripts.development_verified_change as adapter
from scripts.development_verified_change import (
    ATTENTION_FIELDS,
    FINAL_FIELDS,
    INSIGHT_FIELDS,
    M0_PROFILE,
    M0_TRACE_VERSION,
    M1_PROFILE,
    M1_TRACE_VERSION,
    PACKET_FIELDS,
    PACKET_VERSION,
    PROCEDURE_FIELDS,
    PROGRAM_ID,
    PROGRAM_VERSION,
    PROJECTION_VERSION,
    ProgramValidationError,
    source_trace_digest,
    validate_and_project,
)
from scripts.m0_trace import (
    StrictJSONError,
    canonical_json_bytes,
    compute_delegation_digest as compute_m0_delegation_digest,
    load_json_strict,
    strict_json_loads,
    validate_and_project as validate_m0_trace,
)
from scripts.m1_trace import (
    compute_delegation_digest as compute_m1_delegation_digest,
    validate_and_project as validate_m1_trace,
)


ROOT = Path(__file__).resolve().parents[2]
PROGRAM_ROOT = ROOT / "spec/programs/development.verified-change/v1"
PACKET_PATH = PROGRAM_ROOT / "golden/valid-bounded-remediation-packet.json"
EXPECTED_PATH = PROGRAM_ROOT / "golden/expected-projection.json"
CONTRACT_PATH = PROGRAM_ROOT / "program-contract.json"
SCHEMA_PATH = PROGRAM_ROOT / "development-verified-change-packet.schema.json"
M0_TRACE_PATH = ROOT / "spec/m0/v0/golden/valid-telos-adjudication-trace.json"
M0_PROJECTION_PATH = ROOT / "spec/m0/v0/golden/expected-projection.json"
M0_CONTRACT_PATH = ROOT / "spec/m0/v0/trace-contract.json"
M1_TRACE_PATH = ROOT / "spec/m1/v0/golden/valid-telos-recoverability-trace.json"
M1_PROJECTION_PATH = ROOT / "spec/m1/v0/golden/expected-projection.json"
M1_CONTRACT_PATH = ROOT / "spec/m1/v0/trace-contract.json"
SCRIPT_PATH = ROOT / "scripts/development_verified_change.py"

FROZEN_SHA256 = {
    "docs/m0-telos-adjudication-trace.md": "f5e8bf8b991d6a5d0e98e8914714bcadb6d75696303661943dcd6cb55fecbb74",
    "scripts/m0_trace.py": "51742621d34c98a7bcc65cd607aabebd24515c1bdd50788b584cd3a39fd0cea1",
    "spec/m0/v0/trace-contract.json": "a3063ccc601736c25782c28ae6e66416e1c3092c1f39815f2e270301d913313b",
    "spec/m0/v0/telos-adjudication-trace.schema.json": "f5883bf96e091d34bb7c79c7bf1c598a0d2c4aea7ce8d26514a3f6ea37aa57b7",
    "spec/m0/v0/golden/valid-telos-adjudication-trace.json": "7688570f2417edf42acde0d3f1f3409a8053b537befc1c7e65698e4e8f9148e1",
    "spec/m0/v0/golden/expected-projection.json": "e196d32be81293ae4fdf50f2c02cfa3a1167158cb1c8b52230c9e5216f9769cf",
    "tests/m0/__init__.py": "9b71874801187574893e98751216bdf7d4adeba77248566a9bb9390459d21e50",
    "tests/m0/test_telos_adjudication_trace.py": "7f1d0a52ad41197c411fad4573be291d2432924ea8edeb6dd4787ce15e740dfa",
    "docs/m1-telos-recoverability-trace.md": "64dbaf853ebb2deb90d2010ca5c7dfaf5f1c959f05ab7b06dbac489ca8609f8d",
    "scripts/m1_trace.py": "1fa14c64b2bffaf2a4911a80bd9995af95b9782b7d3ffa92a7fcb6126f594b2c",
    "spec/m1/v0/trace-contract.json": "80070189abebce25c3a8617a68434e04e6709f70660a109b4cab3d7d98e8d29a",
    "spec/m1/v0/telos-recoverability-trace.schema.json": "edd1cc318a8bbf328ad4bf06fa4922acf12128b50b414bffbc697adad592ab56",
    "spec/m1/v0/golden/valid-telos-recoverability-trace.json": "2af3ef489cb29123dd51bbac98c03d81be945f1735681c6a4ce4a1b5eac1f4d1",
    "spec/m1/v0/golden/expected-projection.json": "20587de172aa0900f73ff8c1db9c296e591a9171ba8e9a94feb0f26210c6d055",
    "tests/m1/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "tests/m1/test_telos_recoverability_trace.py": "bc257bc63bb44997959dac31dca08c7bae4b7ae52dc5bc04e985c4c93e49cfe6",
}


def _reverse_objects(value: Any) -> Any:
    if type(value) is dict:
        return {key: _reverse_objects(value[key]) for key in reversed(tuple(value))}
    if type(value) is list:
        return [_reverse_objects(item) for item in value]
    return value


def _terminal_final(source_projection: dict[str, Any], profile: str) -> dict[str, Any]:
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


class DevelopmentVerifiedChangeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.packet = load_json_strict(PACKET_PATH)
        self.expected = load_json_strict(EXPECTED_PATH)
        self.m0_source = load_json_strict(M0_TRACE_PATH)
        self.m1_source = load_json_strict(M1_TRACE_PATH)
        self.m0_projection = load_json_strict(M0_PROJECTION_PATH)
        self.m1_projection = load_json_strict(M1_PROJECTION_PATH)

    def packet_for(self, profile: str, source: dict[str, Any]) -> dict[str, Any]:
        packet = copy.deepcopy(self.packet)
        if profile == M0_PROFILE:
            projection = validate_m0_trace(source)
            packet["execution_profile"] = M0_PROFILE
            packet["source_trace_version"] = M0_TRACE_VERSION
        else:
            projection = validate_m1_trace(source)
            packet["execution_profile"] = M1_PROFILE
            packet["source_trace_version"] = M1_TRACE_VERSION
        packet["program_instance_id"] = projection["binding"]["program_id"]
        packet["governing_purpose_id"] = projection["delegation"]["purpose"]
        packet["source_trace_digest"] = source_trace_digest(source)
        packet["final_implementation"].update(_terminal_final(projection, profile))
        return packet

    def assert_rejected(
        self,
        mutate_packet: Callable[[dict[str, Any]], None] | None = None,
        *,
        profile: str = M1_PROFILE,
        source: dict[str, Any] | None = None,
        mutate_source: Callable[[dict[str, Any]], None] | None = None,
        refresh_outer_digest: bool = False,
    ) -> None:
        candidate_source = copy.deepcopy(
            self.m1_source if source is None and profile == M1_PROFILE else source or self.m0_source
        )
        packet = self.packet_for(profile, candidate_source)
        if mutate_packet is not None:
            mutate_packet(packet)
        if mutate_source is not None:
            mutate_source(candidate_source)
        if refresh_outer_digest:
            packet["source_trace_digest"] = source_trace_digest(candidate_source)
        with self.assertRaises(ProgramValidationError):
            validate_and_project(packet, candidate_source)

    def test_m1_golden_produces_exact_canonical_projection(self) -> None:
        projection = validate_and_project(self.packet, self.m1_source)
        self.assertEqual(projection, self.expected)
        self.assertEqual(canonical_json_bytes(projection), EXPECTED_PATH.read_bytes())
        self.assertEqual(projection["schema_version"], PROJECTION_VERSION)
        self.assertEqual(projection["state"], "telos_adjudicated")

    def test_m0_and_m1_profiles_each_have_a_positive_projection(self) -> None:
        m0_packet = self.packet_for(M0_PROFILE, self.m0_source)
        m0_result = validate_and_project(m0_packet, self.m0_source)
        m1_result = validate_and_project(self.packet, self.m1_source)
        self.assertEqual(m0_result["execution_profile"], M0_PROFILE)
        self.assertEqual(m0_result["final_implementation"]["generation"], 1)
        self.assertEqual(m1_result["execution_profile"], M1_PROFILE)
        self.assertEqual(m1_result["final_implementation"]["generation"], 2)

    def test_both_profiles_accept_coherent_source_identity_variants(self) -> None:
        cases = (
            (M0_PROFILE, self.m0_source, compute_m0_delegation_digest),
            (M1_PROFILE, self.m1_source, compute_m1_delegation_digest),
        )
        for profile, original, compute_digest in cases:
            with self.subTest(profile=profile):
                source = copy.deepcopy(original)
                for record in source["records"]:
                    record["binding"]["run_id"] = "run-coherent-variant-1"
                digest = compute_digest(source["records"][0])
                for record in source["records"]:
                    record["binding"]["delegation_digest"] = digest
                packet = self.packet_for(profile, source)
                projection = validate_and_project(packet, source)
                self.assertEqual(
                    projection["source_trace_projection"]["binding"]["run_id"],
                    "run-coherent-variant-1",
                )

    def test_complete_source_projections_are_preserved_unchanged(self) -> None:
        m0_packet = self.packet_for(M0_PROFILE, self.m0_source)
        m0_result = validate_and_project(m0_packet, self.m0_source)
        m1_result = validate_and_project(self.packet, self.m1_source)
        self.assertEqual(m0_result["source_trace_projection"], self.m0_projection)
        self.assertEqual(m1_result["source_trace_projection"], self.m1_projection)
        self.assertEqual(
            canonical_json_bytes(m0_result["source_trace_projection"]),
            M0_PROJECTION_PATH.read_bytes(),
        )
        self.assertEqual(
            canonical_json_bytes(m1_result["source_trace_projection"]),
            M1_PROJECTION_PATH.read_bytes(),
        )

    def test_m1_preserves_failure_remediation_success_and_full_telos_lineage(self) -> None:
        source = validate_and_project(self.packet, self.m1_source)["source_trace_projection"]
        self.assertEqual(
            [item["qa_adjudication"]["conclusion"] for item in source["generation_history"]],
            ["FAIL", "PASS"],
        )
        self.assertEqual(
            source["generation_history"][0]["qa_adjudication"]["finding_id"],
            self.m1_projection["generation_history"][0]["qa_adjudication"]["finding_id"],
        )
        self.assertEqual(
            source["remediation_budget"],
            {"authorized": 1, "consumed": 1, "remaining": 0},
        )
        self.assertEqual(source["controller_result"], self.m1_projection["controller_result"])
        self.assertEqual(
            source["telos_adjudication"]["evidence_event_ids"],
            [record["event_id"] for record in self.m1_source["records"][3:10]],
        )

    def test_remediation_gate_preserves_profile_difference_without_synthesis(self) -> None:
        m0_result = validate_and_project(
            self.packet_for(M0_PROFILE, self.m0_source), self.m0_source
        )
        m1_result = validate_and_project(self.packet, self.m1_source)
        self.assertEqual(m0_result["gates"]["remediation"], {"represented": False})
        self.assertNotIn("remediation_budget", m0_result["source_trace_projection"])
        remediation = m1_result["gates"]["remediation"]
        self.assertTrue(remediation["represented"])
        self.assertEqual(
            remediation["remediation_budget"], self.m1_projection["remediation_budget"]
        )
        self.assertEqual(
            remediation["remediation_generation"],
            self.m1_projection["remediation_generation"],
        )

    def test_gate_kinds_and_determinations_do_not_smuggle_semantic_judgment(self) -> None:
        gates = validate_and_project(self.packet, self.m1_source)["gates"]
        for name in (
            "attention_to_insight_lineage",
            "procedure_to_implementation_lineage",
            "final_implementation_binding",
        ):
            self.assertEqual(gates[name]["kind"], "deterministic")
        self.assertEqual(
            gates["attention_to_insight_lineage"]["determination"],
            "structurally_bound",
        )
        self.assertEqual(
            gates["procedure_to_implementation_lineage"]["determination"],
            "structurally_bound",
        )
        self.assertEqual(
            gates["final_implementation_binding"]["determination"], "source_equal"
        )
        for name in ("verification", "controller_result", "telos_adjudication"):
            self.assertEqual(gates[name]["kind"], "attributed_semantic")
            self.assertEqual(gates[name]["attribution"], "source_trace")

    def test_verification_gate_is_exact_terminal_source_attribution(self) -> None:
        cases = (
            (M0_PROFILE, self.m0_source),
            (M1_PROFILE, self.m1_source),
        )
        for profile, source in cases:
            with self.subTest(profile=profile):
                packet = self.packet_for(profile, source)
                projection = validate_and_project(packet, source)
                gate = projection["gates"]["verification"]
                final = projection["final_implementation"]
                self.assertEqual(gate["conclusion"], "PASS")
                for field in (
                    "generation",
                    "accepted_event_id",
                    "candidate_id",
                    "candidate_digest",
                    "verification_obligation_id",
                ):
                    self.assertEqual(gate[field], final[field])
                self.assertEqual(gate["attribution"], "source_trace")

    def test_controller_result_and_telos_adjudication_remain_separate(self) -> None:
        gates = validate_and_project(self.packet, self.m1_source)["gates"]
        controller = gates["controller_result"]["result"]
        telos = gates["telos_adjudication"]["adjudication"]
        self.assertEqual(controller, self.m1_projection["controller_result"])
        self.assertEqual(telos, self.m1_projection["telos_adjudication"])
        self.assertNotIn("sub_goal_status", controller)
        self.assertNotIn("disposition", controller)
        self.assertEqual(telos["disposition"], "complete")
        self.assertNotIn("disposition", gates["verification"])

    def test_packet_root_and_every_nested_shape_are_closed(self) -> None:
        additions = (
            lambda packet: packet.update(extra="forbidden"),
            lambda packet: packet["attention_packet"].update(extra="forbidden"),
            lambda packet: packet["insight_packet"].update(extra="forbidden"),
            lambda packet: packet["implementation_procedure"].update(extra="forbidden"),
            lambda packet: packet["final_implementation"].update(extra="forbidden"),
        )
        removals = (
            lambda packet: packet.pop("program_id"),
            lambda packet: packet["attention_packet"].pop("evidence_id"),
            lambda packet: packet["insight_packet"].pop("insight_digest"),
            lambda packet: packet["implementation_procedure"].pop("artifact_digest"),
            lambda packet: packet["final_implementation"].pop("candidate_id"),
        )
        for index, mutation in enumerate(additions + removals):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_strict_json_rejects_duplicates_floats_constants_nulls_and_large_ints(self) -> None:
        cases = (
            ('{"program_id":"a","program_id":"b"}', "duplicate object key"),
            ('{"value":1.0}', "floating-point numbers"),
            ('{"value":NaN}', "non-finite numbers"),
            ('{"value":null}', "null is not supported"),
            ("1" * 5000, "invalid JSON"),
        )
        for document, message in cases:
            with self.subTest(message=message):
                with self.assertRaises(StrictJSONError) as raised:
                    strict_json_loads(document)
                self.assertIn(message, str(raised.exception))

    def test_direct_calls_reject_unsupported_values_and_recursion(self) -> None:
        invalid = (None, 1.5, object(), {1: "non-string-key"})
        for value in invalid:
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ProgramValidationError):
                    validate_and_project(value, self.m1_source)

        nested: Any = 0
        for _ in range(sys.getrecursionlimit() + 100):
            nested = [nested]
        with self.assertRaises(ProgramValidationError) as raised:
            validate_and_project(nested, self.m1_source)
        self.assertIn("nesting exceeds recursion limit", str(raised.exception))
        with self.assertRaises(ProgramValidationError):
            validate_and_project(self.packet, {"bad": object()})

    def test_boolean_is_not_a_final_generation_integer(self) -> None:
        self.assert_rejected(
            lambda packet: packet["final_implementation"].update(generation=True)
        )

    def test_p1_p2_procedure_and_final_lineage_mismatches_are_rejected(self) -> None:
        mutations = (
            lambda packet: packet["insight_packet"].update(
                attention_packet_id="product-other-attention"
            ),
            lambda packet: packet["insight_packet"].update(
                question_id="question-other-development"
            ),
            lambda packet: packet["implementation_procedure"].update(
                insight_packet_id="product-other-insight"
            ),
            lambda packet: packet["final_implementation"].update(
                implementation_procedure_artifact_id="product-other-procedure"
            ),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_all_pairwise_product_id_collisions_are_rejected(self) -> None:
        def collide_attention_insight(packet: dict[str, Any]) -> None:
            packet["attention_packet"]["packet_id"] = packet["insight_packet"]["packet_id"]
            packet["insight_packet"]["attention_packet_id"] = packet["insight_packet"]["packet_id"]

        def collide_attention_procedure(packet: dict[str, Any]) -> None:
            artifact_id = packet["attention_packet"]["packet_id"]
            packet["implementation_procedure"]["artifact_id"] = artifact_id
            packet["final_implementation"]["implementation_procedure_artifact_id"] = artifact_id

        def collide_insight_procedure(packet: dict[str, Any]) -> None:
            artifact_id = packet["insight_packet"]["packet_id"]
            packet["implementation_procedure"]["artifact_id"] = artifact_id
            packet["final_implementation"]["implementation_procedure_artifact_id"] = artifact_id

        for mutation in (
            collide_attention_insight,
            collide_attention_procedure,
            collide_insight_procedure,
        ):
            with self.subTest(mutation=mutation.__name__):
                self.assert_rejected(mutation)

    def test_every_final_implementation_field_is_bound(self) -> None:
        replacements: dict[str, Any] = {
            "generation": 1,
            "accepted_event_id": "event-other-accepted",
            "candidate_id": "candidate-other-final",
            "candidate_digest": "sha256:" + "9" * 64,
            "implementer_actor_id": "actor-other-implementer",
            "verification_obligation_id": "obligation-other-final",
            "implementation_procedure_artifact_id": "product-other-procedure",
        }
        for field, value in replacements.items():
            with self.subTest(field=field):
                self.assert_rejected(
                    lambda packet, field=field, value=value: packet[
                        "final_implementation"
                    ].update({field: value})
                )

    def test_profile_source_version_and_source_root_mismatches_are_rejected(self) -> None:
        self.assert_rejected(
            lambda packet: packet.update(execution_profile="m2-variable-loop")
        )
        self.assert_rejected(
            lambda packet: packet.update(source_trace_version=M0_TRACE_VERSION)
        )
        m0_packet = self.packet_for(M0_PROFILE, self.m0_source)
        m0_packet["source_trace_digest"] = source_trace_digest(self.m1_source)
        with self.assertRaises(ProgramValidationError):
            validate_and_project(m0_packet, self.m1_source)

    def test_program_instance_and_governing_purpose_mismatches_are_rejected(self) -> None:
        self.assert_rejected(
            lambda packet: packet.update(program_instance_id="program-other-instance")
        )
        self.assert_rejected(
            lambda packet: packet.update(governing_purpose_id="purpose-other-governance")
        )

    def test_program_contract_versions_and_identifier_formats_are_enforced(self) -> None:
        mutations = (
            lambda packet: packet.update(schema_version="development.verified-change.packet/v2"),
            lambda packet: packet.update(program_id="development.other"),
            lambda packet: packet.update(program_version="v2"),
            lambda packet: packet.update(program_instance_id="program_bad"),
            lambda packet: packet["attention_packet"].update(packet_id="product_bad"),
            lambda packet: packet["attention_packet"].update(evidence_digest="sha256:ABC"),
            lambda packet: packet["final_implementation"].update(candidate_id="candidate_bad"),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_source_digest_uses_canonical_complete_trace_with_final_lf(self) -> None:
        canonical = canonical_json_bytes(self.m1_source)
        expected = "sha256:" + hashlib.sha256(canonical).hexdigest()
        without_lf = "sha256:" + hashlib.sha256(canonical[:-1]).hexdigest()
        self.assertEqual(source_trace_digest(self.m1_source), expected)
        self.assertEqual(self.packet["source_trace_digest"], expected)
        self.assertNotEqual(expected, without_lf)
        self.assertEqual(source_trace_digest(_reverse_objects(self.m1_source)), expected)

    def test_source_object_order_does_not_change_projection_or_digest(self) -> None:
        reordered = _reverse_objects(self.m1_source)
        projection = validate_and_project(self.packet, reordered)
        self.assertEqual(canonical_json_bytes(projection), EXPECTED_PATH.read_bytes())

    def test_source_mutation_is_rejected_with_stale_outer_digest(self) -> None:
        self.assert_rejected(
            mutate_source=lambda source: source["records"][7]["payload"].update(
                conclusion="FAIL"
            )
        )

    def test_representative_source_mutations_fail_after_outer_digest_refresh(self) -> None:
        cases = (
            (
                M0_PROFILE,
                self.m0_source,
                lambda source: source["records"][4]["payload"].update(conclusion="FAIL"),
            ),
            (
                M0_PROFILE,
                self.m0_source,
                lambda source: source["records"][7]["payload"].update(disposition="blocked"),
            ),
            (
                M1_PROFILE,
                self.m1_source,
                lambda source: source["records"][4]["payload"].update(conclusion="PASS"),
            ),
            (
                M1_PROFILE,
                self.m1_source,
                lambda source: source["records"][5]["payload"].update(
                    finding_digest="sha256:" + "8" * 64
                ),
            ),
            (
                M1_PROFILE,
                self.m1_source,
                lambda source: source["records"][10]["payload"][
                    "evidence_event_ids"
                ].pop(),
            ),
        )
        for profile, source, mutation in cases:
            with self.subTest(profile=profile, mutation=mutation):
                self.assert_rejected(
                    profile=profile,
                    source=source,
                    mutate_source=mutation,
                    refresh_outer_digest=True,
                )

    def test_each_profile_calls_exactly_one_existing_frozen_reducer(self) -> None:
        cases = (
            (M0_PROFILE, self.m0_source, "validate_m0_trace", "validate_m1_trace"),
            (M1_PROFILE, self.m1_source, "validate_m1_trace", "validate_m0_trace"),
        )
        for profile, source, selected_name, other_name in cases:
            with self.subTest(profile=profile):
                packet = self.packet_for(profile, source)
                selected = getattr(adapter, selected_name)
                with mock.patch.object(adapter, selected_name, wraps=selected) as selected_mock:
                    with mock.patch.object(
                        adapter,
                        other_name,
                        side_effect=AssertionError("wrong reducer called"),
                    ) as other_mock:
                        validate_and_project(packet, source)
                self.assertEqual(selected_mock.call_count, 1)
                self.assertEqual(other_mock.call_count, 0)

    def test_source_reducer_failures_become_controlled_program_errors(self) -> None:
        source = copy.deepcopy(self.m1_source)
        source["records"][7]["payload"]["conclusion"] = "FAIL"
        packet = self.packet_for(M1_PROFILE, self.m1_source)
        packet["source_trace_digest"] = source_trace_digest(source)
        with self.assertRaises(ProgramValidationError) as raised:
            validate_and_project(packet, source)
        self.assertIn("M1 source trace rejected", str(raised.exception))
        self.assertNotIsInstance(raised.exception.__cause__, Exception)

    def test_opaque_products_do_not_gain_distinctness_or_quality_inference(self) -> None:
        packet = copy.deepcopy(self.packet)
        shared_actor = "actor-shared-product-producer"
        shared_digest = "sha256:" + "7" * 64
        packet["attention_packet"]["producer_actor_id"] = shared_actor
        packet["insight_packet"]["producer_actor_id"] = shared_actor
        packet["implementation_procedure"]["producer_actor_id"] = shared_actor
        packet["attention_packet"]["evidence_digest"] = shared_digest
        packet["insight_packet"]["insight_digest"] = shared_digest
        packet["implementation_procedure"]["artifact_digest"] = shared_digest
        projection = validate_and_project(packet, self.m1_source)
        self.assertEqual(projection["attention_packet"], packet["attention_packet"])
        self.assertEqual(projection["insight_packet"], packet["insight_packet"])
        self.assertEqual(
            projection["implementation_procedure"], packet["implementation_procedure"]
        )

    def test_reduction_does_not_mutate_inputs_and_returns_fresh_nested_values(self) -> None:
        packet = copy.deepcopy(self.packet)
        source = copy.deepcopy(self.m1_source)
        original_packet = copy.deepcopy(packet)
        original_source = copy.deepcopy(source)
        projection = validate_and_project(packet, source)
        self.assertEqual(packet, original_packet)
        self.assertEqual(source, original_source)
        projection["attention_packet"]["packet_id"] = "product-mutated-output"
        projection["source_trace_projection"]["binding"]["run_id"] = "run-mutated-output"
        self.assertEqual(packet, original_packet)
        self.assertEqual(source, original_source)

    def test_pure_reducer_performs_no_file_process_or_write_effects(self) -> None:
        with mock.patch("builtins.open", side_effect=AssertionError("unexpected open")):
            with mock.patch.object(Path, "read_text", side_effect=AssertionError("unexpected read")):
                with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("unexpected read")):
                    with mock.patch.object(Path, "write_text", side_effect=AssertionError("unexpected write")):
                        with mock.patch.object(Path, "write_bytes", side_effect=AssertionError("unexpected write")):
                            with mock.patch("subprocess.run", side_effect=AssertionError("unexpected process")):
                                projection = validate_and_project(self.packet, self.m1_source)
        self.assertEqual(projection, self.expected)

    def test_adapter_imports_only_standard_library_and_public_m0_m1_interfaces(self) -> None:
        tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
        top_level_modules = set()
        reducer_imports: dict[str, list[tuple[str, ...]]] = {"m0": [], "m1": []}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                top_level_modules.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module in ("scripts.m0_trace", "m0_trace"):
                    reducer_imports["m0"].append(tuple(alias.name for alias in node.names))
                elif node.module in ("scripts.m1_trace", "m1_trace"):
                    reducer_imports["m1"].append(tuple(alias.name for alias in node.names))
                else:
                    top_level_modules.add(node.module.split(".", 1)[0])
        self.assertLessEqual(
            top_level_modules,
            {
                "__future__",
                "argparse",
                "copy",
                "hashlib",
                "re",
                "sys",
                "pathlib",
                "typing",
            },
        )
        expected_m0 = (
            "StrictJSONError",
            "TraceValidationError",
            "canonical_json_bytes",
            "load_json_strict",
            "validate_and_project",
        )
        expected_m1 = ("M1TraceValidationError", "validate_and_project")
        self.assertEqual(reducer_imports["m0"], [expected_m0, expected_m0])
        self.assertEqual(reducer_imports["m1"], [expected_m1, expected_m1])

    def test_projection_is_byte_deterministic_in_process(self) -> None:
        expected = EXPECTED_PATH.read_bytes()
        for _ in range(25):
            self.assertEqual(
                canonical_json_bytes(validate_and_project(self.packet, self.m1_source)),
                expected,
            )

    def test_projection_is_byte_deterministic_across_processes_and_hash_seeds(self) -> None:
        expected = EXPECTED_PATH.read_bytes()
        command = [sys.executable, str(SCRIPT_PATH), str(PACKET_PATH), str(M1_TRACE_PATH)]
        for seed in ("0", "1", "42", "314159", "random"):
            environment = os.environ.copy()
            environment["PYTHONHASHSEED"] = seed
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            with self.subTest(seed=seed):
                for _ in range(2):
                    completed = subprocess.run(
                        command,
                        cwd=ROOT,
                        env=environment,
                        check=False,
                        capture_output=True,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr.decode())
                    self.assertEqual(completed.stdout, expected)
                    self.assertEqual(completed.stderr, b"")

    def test_cli_check_and_non_check_modes_are_exact(self) -> None:
        non_check = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(PACKET_PATH), str(M1_TRACE_PATH)],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
        self.assertEqual(non_check.returncode, 0, non_check.stderr.decode())
        self.assertEqual(non_check.stdout, EXPECTED_PATH.read_bytes())
        checked = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--check",
                str(PACKET_PATH),
                str(M1_TRACE_PATH),
                str(EXPECTED_PATH),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(checked.stderr, "")
        self.assertIn("passed canonical projection check", checked.stdout)

    def test_cli_argument_failures_are_controlled(self) -> None:
        cases = (
            [],
            [str(PACKET_PATH)],
            ["--check", str(PACKET_PATH), str(M1_TRACE_PATH)],
            [str(PACKET_PATH), str(M1_TRACE_PATH), str(EXPECTED_PATH)],
            ["--unknown", str(PACKET_PATH), str(M1_TRACE_PATH)],
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                completed = subprocess.run(
                    [sys.executable, str(SCRIPT_PATH), *arguments],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, "")
                self.assertIn("usage:", completed.stderr)
                self.assertNotIn("Traceback", completed.stderr)

    def test_cli_validation_failures_are_controlled_without_stdout_or_traceback(self) -> None:
        cases = (
            (
                "duplicate.json",
                '{"schema_version":"a","schema_version":"b"}\n',
                "duplicate object key",
            ),
            ("float.json", '{"value":1.0}\n', "floating-point numbers"),
            ("constant.json", '{"value":NaN}\n', "non-finite numbers"),
            ("null.json", '{"value":null}\n', "null is not supported"),
            ("oversized.json", "1" * 5000, "invalid JSON:"),
            (
                "deep.json",
                "[" * (sys.getrecursionlimit() * 2)
                + "0"
                + "]" * (sys.getrecursionlimit() * 2),
                "JSON nesting exceeds recursion limit:",
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            for filename, document, expected_message in cases:
                with self.subTest(filename=filename):
                    invalid_packet = Path(temporary) / filename
                    invalid_packet.write_text(document, encoding="utf-8")
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPT_PATH),
                            str(invalid_packet),
                            str(M1_TRACE_PATH),
                        ],
                        cwd=ROOT,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(completed.returncode, 1)
                    self.assertEqual(completed.stdout, "")
                    self.assertIn(
                        "development.verified-change validation failed:", completed.stderr
                    )
                    self.assertIn(expected_message, completed.stderr)
                    self.assertNotIn("Traceback", completed.stderr)

    def test_cli_source_rejection_after_outer_digest_refresh_is_controlled(self) -> None:
        source = copy.deepcopy(self.m1_source)
        source["records"][10]["payload"]["evidence_event_ids"].pop()
        packet = self.packet_for(M1_PROFILE, self.m1_source)
        packet["source_trace_digest"] = source_trace_digest(source)
        with tempfile.TemporaryDirectory() as temporary:
            packet_path = Path(temporary) / "packet.json"
            source_path = Path(temporary) / "source.json"
            packet_path.write_bytes(canonical_json_bytes(packet))
            source_path.write_bytes(canonical_json_bytes(source))
            completed = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(packet_path), str(source_path)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        self.assertIn("M1 source trace rejected", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_cli_rejects_noncanonical_and_wrong_expected_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            noncanonical = Path(temporary) / "noncanonical.json"
            noncanonical.write_text(json.dumps(self.expected, indent=2) + "\n", encoding="utf-8")
            wrong = Path(temporary) / "wrong.json"
            wrong_projection = copy.deepcopy(self.expected)
            wrong_projection["state"] = "result_reported"
            wrong.write_bytes(canonical_json_bytes(wrong_projection))
            for path, message in (
                (noncanonical, "not canonical JSON bytes"),
                (wrong, "does not match expected bytes"),
            ):
                with self.subTest(path=path.name):
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPT_PATH),
                            "--check",
                            str(PACKET_PATH),
                            str(M1_TRACE_PATH),
                            str(path),
                        ],
                        cwd=ROOT,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(completed.returncode, 1)
                    self.assertEqual(completed.stdout, "")
                    self.assertIn(message, completed.stderr)
                    self.assertNotIn("Traceback", completed.stderr)

    def test_contract_schema_reducer_fixture_and_projection_are_mutually_exact(self) -> None:
        contract = load_json_strict(CONTRACT_PATH)
        schema = load_json_strict(SCHEMA_PATH)
        projection = validate_and_project(self.packet, self.m1_source)
        self.assertEqual(contract["schema_version"], "development.verified-change.contract/v1")
        self.assertEqual(contract["program_id"], PROGRAM_ID)
        self.assertEqual(contract["program_version"], PROGRAM_VERSION)
        self.assertEqual(contract["packet_version"], PACKET_VERSION)
        self.assertEqual(contract["projection_version"], PROJECTION_VERSION)
        self.assertEqual(contract["packet_fields"], list(PACKET_FIELDS))
        self.assertEqual(contract["projection_fields"], list(projection))
        self.assertEqual(schema["required"], list(PACKET_FIELDS))
        self.assertEqual(schema["properties"]["schema_version"]["const"], PACKET_VERSION)
        self.assertEqual(schema["properties"]["program_id"]["const"], PROGRAM_ID)
        self.assertEqual(schema["properties"]["program_version"]["const"], PROGRAM_VERSION)
        components = contract["packet_components"]
        self.assertEqual(components["attention_packet"]["fields"], list(ATTENTION_FIELDS))
        self.assertEqual(components["insight_packet"]["fields"], list(INSIGHT_FIELDS))
        self.assertEqual(
            components["implementation_procedure"]["fields"], list(PROCEDURE_FIELDS)
        )
        self.assertEqual(components["final_implementation"]["fields"], list(FINAL_FIELDS))
        self.assertEqual(contract["gate_order"], list(projection["gates"]))
        for name, gate in projection["gates"].items():
            gate_contract = contract["gates"][name]
            if name == "remediation":
                self.assertEqual(
                    set(gate),
                    {
                        "represented",
                        "kind",
                        "attribution",
                        "remediation_budget",
                        "remediation_generation",
                    },
                )
            else:
                self.assertEqual(gate_contract["fields"], list(gate))

    def test_contract_explicit_profiles_match_frozen_source_contracts(self) -> None:
        contract = load_json_strict(CONTRACT_PATH)
        profiles = contract["supported_source_profiles"]
        self.assertEqual(list(profiles), [M0_PROFILE, M1_PROFILE])
        for profile, source_contract_path in (
            (M0_PROFILE, M0_CONTRACT_PATH),
            (M1_PROFILE, M1_CONTRACT_PATH),
        ):
            with self.subTest(profile=profile):
                source_contract = load_json_strict(source_contract_path)
                profile_contract = profiles[profile]
                self.assertEqual(
                    profile_contract["source_trace_version"], source_contract["trace_version"]
                )
                self.assertEqual(
                    profile_contract["source_projection_version"],
                    source_contract["projection_version"],
                )
                self.assertEqual(
                    profile_contract["event_sequence"], source_contract["event_sequence"]
                )
                self.assertEqual(
                    profile_contract["source_states"], source_contract["states"]
                )
                if profile == M0_PROFILE:
                    self.assertEqual(
                        profile_contract["semantic_generation_sequence"],
                        [source_contract["generation"]] * 8,
                    )
                else:
                    self.assertEqual(
                        profile_contract["semantic_generation_sequence"],
                        source_contract["semantic_generation_sequence"],
                    )

    @unittest.skipIf(
        Draft202012Validator is None,
        "optional jsonschema is unavailable; Draft 2020-12 validation is skipped",
    )
    def test_draft_2020_12_schema_is_valid_and_accepts_only_closed_packet_shapes(self) -> None:
        schema = load_json_strict(SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        self.assertEqual(list(validator.iter_errors(self.packet)), [])
        invalid_packets = []
        for path in (
            (),
            ("attention_packet",),
            ("insight_packet",),
            ("implementation_procedure",),
            ("final_implementation",),
        ):
            packet = copy.deepcopy(self.packet)
            target = packet
            for component in path:
                target = target[component]
            target["unknown"] = "forbidden"
            invalid_packets.append(packet)
        boolean_generation = copy.deepcopy(self.packet)
        boolean_generation["final_implementation"]["generation"] = True
        invalid_packets.append(boolean_generation)
        wrong_profile_version = copy.deepcopy(self.packet)
        wrong_profile_version["source_trace_version"] = M0_TRACE_VERSION
        invalid_packets.append(wrong_profile_version)
        for index, packet in enumerate(invalid_packets):
            with self.subTest(index=index):
                self.assertTrue(list(validator.iter_errors(packet)))

    def test_schema_contract_required_fields_and_patterns_are_in_parity(self) -> None:
        contract = load_json_strict(CONTRACT_PATH)
        schema = load_json_strict(SCHEMA_PATH)
        mapping = {
            "product_id": "productId",
            "actor_id": "actorId",
            "evidence_id": "evidenceId",
            "question_id": "questionId",
            "program_instance_id": "programId",
            "purpose_id": "purposeId",
            "event_id": "eventId",
            "candidate_id": "candidateId",
            "obligation_id": "obligationId",
            "digest": "digest",
        }
        for contract_name, schema_name in mapping.items():
            self.assertEqual(
                contract["identity_formats"][contract_name],
                schema["$defs"][schema_name]["pattern"],
            )
        component_defs = {
            "attention_packet": "attentionPacket",
            "insight_packet": "insightPacket",
            "implementation_procedure": "implementationProcedure",
            "final_implementation": "finalImplementation",
        }
        for component, definition in component_defs.items():
            self.assertEqual(
                contract["packet_components"][component]["fields"],
                schema["$defs"][definition]["required"],
            )
            self.assertFalse(schema["$defs"][definition]["additionalProperties"])

    def test_all_frozen_m0_m1_artifacts_retain_exact_base_bytes(self) -> None:
        actual = {
            relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            for relative in FROZEN_SHA256
        }
        self.assertEqual(actual, FROZEN_SHA256)


if __name__ == "__main__":
    unittest.main()
