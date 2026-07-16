"""Adversarial self-checks for the fixed provider-free M1 reference trace."""

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

from scripts.m0_trace import StrictJSONError, canonical_json_bytes, load_json_strict
from scripts.m1_trace import (
    DELEGATED_ACTIONS,
    EVENT_SEQUENCE,
    GENERATION_SEQUENCE,
    M1TraceValidationError,
    PROJECTION_VERSION,
    RECORD_VERSION,
    STABLE_BINDING_FIELDS,
    TRACE_VERSION,
    TRANSITIONS,
    compute_delegation_digest,
    validate_and_project,
)


ROOT = Path(__file__).resolve().parents[2]
TRACE_PATH = ROOT / "spec/m1/v0/golden/valid-telos-recoverability-trace.json"
PROJECTION_PATH = ROOT / "spec/m1/v0/golden/expected-projection.json"
CONTRACT_PATH = ROOT / "spec/m1/v0/trace-contract.json"
SCHEMA_PATH = ROOT / "spec/m1/v0/telos-recoverability-trace.schema.json"
SCRIPT_PATH = ROOT / "scripts/m1_trace.py"

M0_SHA256 = {
    "docs/m0-telos-adjudication-trace.md": "f5e8bf8b991d6a5d0e98e8914714bcadb6d75696303661943dcd6cb55fecbb74",
    "scripts/m0_trace.py": "51742621d34c98a7bcc65cd607aabebd24515c1bdd50788b584cd3a39fd0cea1",
    "spec/m0/v0/trace-contract.json": "a3063ccc601736c25782c28ae6e66416e1c3092c1f39815f2e270301d913313b",
    "spec/m0/v0/telos-adjudication-trace.schema.json": "f5883bf96e091d34bb7c79c7bf1c598a0d2c4aea7ce8d26514a3f6ea37aa57b7",
    "spec/m0/v0/golden/valid-telos-adjudication-trace.json": "7688570f2417edf42acde0d3f1f3409a8053b537befc1c7e65698e4e8f9148e1",
    "spec/m0/v0/golden/expected-projection.json": "e196d32be81293ae4fdf50f2c02cfa3a1167158cb1c8b52230c9e5216f9769cf",
    "tests/m0/__init__.py": "9b71874801187574893e98751216bdf7d4adeba77248566a9bb9390459d21e50",
    "tests/m0/test_telos_adjudication_trace.py": "7f1d0a52ad41197c411fad4573be291d2432924ea8edeb6dd4787ce15e740dfa",
}


def _refresh_delegation_digest(trace: dict[str, Any]) -> None:
    digest = compute_delegation_digest(trace["records"][0])
    for record in trace["records"]:
        record["binding"]["delegation_digest"] = digest


def _reverse_objects(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _reverse_objects(value[key]) for key in reversed(tuple(value))}
    if isinstance(value, list):
        return [_reverse_objects(item) for item in value]
    return value


class M1TraceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.trace = load_json_strict(TRACE_PATH)
        self.expected = load_json_strict(PROJECTION_PATH)

    def assert_rejected(
        self,
        mutate: Callable[[dict[str, Any]], None],
        *,
        refresh_digest: bool = False,
    ) -> None:
        candidate = copy.deepcopy(self.trace)
        mutate(candidate)
        if refresh_digest:
            _refresh_delegation_digest(candidate)
        with self.assertRaises((StrictJSONError, M1TraceValidationError)):
            validate_and_project(candidate)

    def test_golden_trace_produces_exact_canonical_projection(self) -> None:
        projection = validate_and_project(self.trace)
        self.assertEqual(projection, self.expected)
        self.assertEqual(canonical_json_bytes(projection), PROJECTION_PATH.read_bytes())
        self.assertEqual(projection["state"], "telos_adjudicated")
        self.assertEqual(projection["remediation_budget"], {"authorized": 1, "consumed": 1, "remaining": 0})
        self.assertEqual(
            [entry["qa_adjudication"]["conclusion"] for entry in projection["generation_history"]],
            ["FAIL", "PASS"],
        )
        self.assertNotIn("finding_id", projection["generation_history"][1]["qa_adjudication"])

    def test_cli_check_accepts_golden_pair(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--check", str(TRACE_PATH), str(PROJECTION_PATH)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("passed canonical projection check", completed.stdout)
        self.assertEqual(completed.stderr, "")

    def test_contract_schema_fixture_reducer_and_projection_are_bound(self) -> None:
        contract = load_json_strict(CONTRACT_PATH)
        schema = load_json_strict(SCHEMA_PATH)
        records = self.trace["records"]
        events = [record["event_type"] for record in records]
        generations = [record["binding"]["generation"] for record in records]
        roles = [record["actor"]["role"] for record in records]

        self.assertEqual(events, list(EVENT_SEQUENCE))
        self.assertEqual(events, contract["event_sequence"])
        self.assertEqual(events, [transition[1] for transition in contract["transitions"]])
        self.assertEqual(contract["transitions"], [list(transition) for transition in TRANSITIONS])
        self.assertEqual(generations, list(GENERATION_SEQUENCE))
        self.assertEqual(generations, contract["semantic_generation_sequence"])
        self.assertEqual(roles, contract["actor_role_sequence"])
        self.assertEqual(len(records), contract["record_cardinality"])
        self.assertEqual(self.trace["schema_version"], TRACE_VERSION)
        self.assertEqual(contract["trace_version"], TRACE_VERSION)
        self.assertEqual(contract["record_version"], RECORD_VERSION)
        self.assertEqual(contract["projection_version"], PROJECTION_VERSION)
        self.assertEqual(self.expected["schema_version"], PROJECTION_VERSION)
        self.assertEqual(contract["stable_binding_fields"], list(STABLE_BINDING_FIELDS))
        self.assertEqual(schema["properties"]["schema_version"]["const"], TRACE_VERSION)
        self.assertEqual(schema["properties"]["records"]["minItems"], 11)
        self.assertEqual(schema["properties"]["records"]["maxItems"], 11)
        self.assertFalse(schema["additionalProperties"])

    def test_contract_authority_and_evidence_match_fixture(self) -> None:
        contract = load_json_strict(CONTRACT_PATH)
        authority = self.trace["records"][0]["payload"]["authority"]
        for role, actions in contract["delegated_actions"].items():
            self.assertEqual(authority[role]["actions"], actions)
            self.assertEqual(list(DELEGATED_ACTIONS[role]), actions)
        for record in self.trace["records"]:
            self.assertIn(record["event_type"], contract["actor_action_ceiling"][record["actor"]["role"]])
        self.assertEqual(
            self.trace["records"][9]["payload"]["evidence_event_ids"],
            [
                self.trace["records"][6]["event_id"],
                self.trace["records"][7]["event_id"],
                self.trace["records"][8]["event_id"],
            ],
        )
        self.assertEqual(
            self.trace["records"][10]["payload"]["evidence_event_ids"],
            [record["event_id"] for record in self.trace["records"][3:10]],
        )

    def test_m1_imports_only_m0_public_json_and_canonicalization_utilities(self) -> None:
        tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
        m0_imports = []
        top_level_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                top_level_modules.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module in ("scripts.m0_trace", "m0_trace"):
                    m0_imports.append(tuple(alias.name for alias in node.names))
                elif node.module:
                    top_level_modules.add(node.module.split(".", 1)[0])

        self.assertEqual(
            m0_imports,
            [
                ("StrictJSONError", "canonical_json_bytes", "load_json_strict"),
                ("StrictJSONError", "canonical_json_bytes", "load_json_strict"),
            ],
        )
        self.assertLessEqual(
            top_level_modules,
            {"__future__", "argparse", "hashlib", "re", "sys", "datetime", "pathlib", "typing"},
        )

    def test_all_m0_artifacts_retain_exact_base_bytes(self) -> None:
        actual = {
            relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            for relative in M0_SHA256
        }
        self.assertEqual(actual, M0_SHA256)

    def test_validation_does_not_mutate_input(self) -> None:
        original = copy.deepcopy(self.trace)
        validate_and_project(self.trace)
        self.assertEqual(self.trace, original)

    def test_direct_validation_controls_non_json_values_and_deep_inputs(self) -> None:
        invalid_values = (None, 1.5, object(), {1: "non-string-key"})
        for value in invalid_values:
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(M1TraceValidationError):
                    validate_and_project(value)

        nested: Any = 0
        for _ in range(sys.getrecursionlimit() + 100):
            nested = [nested]
        with self.assertRaises(M1TraceValidationError) as raised:
            validate_and_project(nested)
        self.assertIn("nesting exceeds recursion limit", str(raised.exception))

    def test_cli_controls_strict_json_failures_without_tracebacks(self) -> None:
        cases = (
            ("duplicate.json", '{"schema_version":"a","schema_version":"b","records":[]}', "duplicate object key"),
            ("float.json", '{"schema_version":"a","records":[1.0]}', "floating-point numbers"),
            ("constant.json", '{"schema_version":"a","records":[NaN]}', "non-finite numbers"),
            ("null.json", '{"schema_version":"a","records":[null]}', "null is not supported"),
            ("oversized.json", "1" * 5000, "invalid JSON:"),
            (
                "deep.json",
                "[" * (sys.getrecursionlimit() * 2) + "0" + "]" * (sys.getrecursionlimit() * 2),
                "JSON nesting exceeds recursion limit:",
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            for filename, document, expected_message in cases:
                with self.subTest(filename=filename):
                    path = Path(temporary) / filename
                    path.write_text(document, encoding="utf-8")
                    completed = subprocess.run(
                        [sys.executable, str(SCRIPT_PATH), str(path)],
                        cwd=ROOT,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(completed.returncode, 1)
                    self.assertEqual(completed.stdout, "")
                    self.assertIn("M1 trace validation failed:", completed.stderr)
                    self.assertIn(expected_message, completed.stderr)
                    self.assertNotIn("Traceback", completed.stderr)

    def test_cli_argument_errors_are_controlled(self) -> None:
        cases = (
            [],
            ["--check", str(TRACE_PATH)],
            [str(TRACE_PATH), str(PROJECTION_PATH)],
            ["--unknown", str(TRACE_PATH)],
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

    def test_unknown_missing_fields_and_bad_types_are_rejected(self) -> None:
        mutations = (
            lambda trace: trace.update(extra="forbidden"),
            lambda trace: trace.pop("records"),
            lambda trace: trace["records"][5].update(extra="forbidden"),
            lambda trace: trace["records"][5].pop("actor"),
            lambda trace: trace["records"][5]["actor"].update(extra="forbidden"),
            lambda trace: trace["records"][5]["binding"].update(extra="forbidden"),
            lambda trace: trace["records"][5]["payload"].update(extra="forbidden"),
            lambda trace: trace["records"][4]["payload"].pop("finding_digest"),
            lambda trace: trace["records"][7]["payload"].update(finding_id="finding-forbidden"),
            lambda trace: trace["records"][5].update(caused_by="event-not-an-array"),
            lambda trace: trace["records"][6].update(payload="not-an-object"),
            lambda trace: trace["records"][5]["payload"].update(remediation_ordinal=True),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_unsupported_versions_identifiers_digests_and_timestamps_are_rejected(self) -> None:
        mutations = (
            lambda trace: trace.update(schema_version="noetic.m1.telos-recoverability-trace/v1"),
            lambda trace: trace["records"][7].update(schema_version="noetic.m1.trace-record/v1"),
            lambda trace: trace["records"][7].update(event_id="event_bad"),
            lambda trace: trace["records"][7]["actor"].update(actor_id="actor_bad"),
            lambda trace: trace["records"][6]["payload"].update(candidate_id="candidate_bad"),
            lambda trace: trace["records"][6]["payload"].update(candidate_digest="sha256:ABC"),
            lambda trace: trace["records"][6]["payload"].update(verification_obligation_id="obligation_bad"),
            lambda trace: trace["records"][4]["payload"].update(finding_id="finding_bad"),
            lambda trace: trace["records"][4]["payload"].update(finding_digest="sha256:1234"),
            lambda trace: trace["records"][9]["payload"].update(result_id="result_bad"),
            lambda trace: trace["records"][3].update(occurred_at="2026-07-16T07:00:03+00:00"),
            lambda trace: trace["records"][3].update(occurred_at="2026-02-30T07:00:03Z"),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_exact_record_cardinality_order_causality_and_terminal_position(self) -> None:
        mutations = (
            lambda trace: trace["records"].pop(4),
            lambda trace: trace["records"].insert(5, copy.deepcopy(trace["records"][4])),
            lambda trace: trace["records"].append(copy.deepcopy(trace["records"][10])),
            lambda trace: trace["records"].__setitem__(slice(3, 5), [trace["records"][4], trace["records"][3]]),
            lambda trace: trace["records"].__setitem__(slice(4, 6), [trace["records"][5], trace["records"][4]]),
            lambda trace: trace["records"][7].update(event_id=trace["records"][4]["event_id"]),
            lambda trace: trace["records"][6].update(caused_by=[trace["records"][4]["event_id"]]),
            lambda trace: trace["records"][6].update(caused_by=[trace["records"][6]["event_id"]]),
            lambda trace: trace["records"][6].update(caused_by=[trace["records"][7]["event_id"]]),
            lambda trace: trace["records"][0].update(caused_by=[trace["records"][10]["event_id"]]),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_every_event_action_is_fixed_to_its_transition(self) -> None:
        event_types = [record["event_type"] for record in self.trace["records"]]
        for index, current in enumerate(event_types):
            for replacement in set(event_types):
                if replacement == current:
                    continue
                with self.subTest(index=index, replacement=replacement):
                    self.assert_rejected(
                        lambda trace, index=index, replacement=replacement: trace["records"][index].update(
                            event_type=replacement
                        )
                    )

    def test_generation_changes_exactly_once_at_remediation_start(self) -> None:
        mutations = (
            lambda trace: trace["records"][5]["binding"].update(generation=1),
            lambda trace: trace["records"][4]["binding"].update(generation=2),
            lambda trace: trace["records"][5]["binding"].update(generation=3),
            lambda trace: trace["records"][7]["binding"].update(generation=1),
            lambda trace: trace["records"][5]["payload"].update(target_generation=1),
            lambda trace: trace["records"][5]["payload"].update(target_generation=3),
            lambda trace: trace["records"][5]["payload"].update(target_generation=True),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_stable_binding_digest_and_attributed_time_interval_are_enforced(self) -> None:
        mismatches: dict[str, Any] = {
            "delegation_id": "delegation-other",
            "delegation_digest": "sha256:" + "9" * 64,
            "goal_chain_id": "chain-36",
            "sub_goal_id": "subgoal-36",
            "program_id": "program-other",
            "run_id": "run-other-1",
            "correlation_id": "correlation-other-1",
        }
        for field, value in mismatches.items():
            with self.subTest(field=field):
                self.assert_rejected(
                    lambda trace, field=field, value=value: trace["records"][7]["binding"].update(
                        {field: value}
                    )
                )

        def replace_run_everywhere(trace: dict[str, Any]) -> None:
            for record in trace["records"]:
                record["binding"]["run_id"] = "run-other-1"

        self.assert_rejected(replace_run_everywhere)
        self.assert_rejected(
            lambda trace: trace["records"][0]["payload"].update(purpose="purpose-other-proof")
        )
        self.assert_rejected(lambda trace: trace["records"][3].update(occurred_at="2026-07-16T07:00:02Z"))
        self.assert_rejected(lambda trace: trace["records"][10].update(occurred_at="2026-07-17T07:00:00Z"))
        self.assert_rejected(
            lambda trace: trace["records"][0]["payload"].update(valid_from="2026-07-16T07:00:01Z"),
            refresh_digest=True,
        )
        self.assert_rejected(
            lambda trace: trace["records"][0]["payload"].update(expires_at="2026-07-16T07:00:10Z"),
            refresh_digest=True,
        )
        self.assert_rejected(
            lambda trace: trace["records"][0]["payload"].update(revocation_status="revoked"),
            refresh_digest=True,
        )

    def test_candidates_digests_acceptances_and_obligations_are_fresh(self) -> None:
        mutations = (
            lambda trace: trace["records"][6]["payload"].update(
                candidate_id=trace["records"][3]["payload"]["candidate_id"]
            ),
            lambda trace: trace["records"][6]["payload"].update(
                candidate_digest=trace["records"][3]["payload"]["candidate_digest"]
            ),
            lambda trace: trace["records"][6]["payload"].update(
                verification_obligation_id=trace["records"][3]["payload"]["verification_obligation_id"]
            ),
            lambda trace: trace["records"][6].update(event_id=trace["records"][3]["event_id"]),
            lambda trace: trace["records"][7].update(event_id=trace["records"][4]["event_id"]),
            lambda trace: trace["records"][6]["payload"].update(
                remediation_event_id=trace["records"][4]["event_id"]
            ),
            lambda trace: trace["records"][6]["payload"].update(
                superseded_accepted_event_id=trace["records"][2]["event_id"]
            ),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_each_qa_record_binds_only_its_accepted_generation(self) -> None:
        mutations = (
            lambda trace: trace["records"][4]["payload"].update(
                accepted_event_id=trace["records"][6]["event_id"]
            ),
            lambda trace: trace["records"][4]["payload"].update(
                candidate_id=trace["records"][6]["payload"]["candidate_id"]
            ),
            lambda trace: trace["records"][4]["payload"].update(
                candidate_digest=trace["records"][6]["payload"]["candidate_digest"]
            ),
            lambda trace: trace["records"][4]["payload"].update(
                verification_obligation_id=trace["records"][6]["payload"]["verification_obligation_id"]
            ),
            lambda trace: trace["records"][7]["payload"].update(
                accepted_event_id=trace["records"][3]["event_id"]
            ),
            lambda trace: trace["records"][7]["payload"].update(
                candidate_id=trace["records"][3]["payload"]["candidate_id"]
            ),
            lambda trace: trace["records"][7]["payload"].update(
                candidate_digest=trace["records"][3]["payload"]["candidate_digest"]
            ),
            lambda trace: trace["records"][7]["payload"].update(
                verification_obligation_id=trace["records"][3]["payload"]["verification_obligation_id"]
            ),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_qa_cardinality_conclusions_and_finding_shapes_are_exact(self) -> None:
        mutations = (
            lambda trace: trace["records"][4]["payload"].update(conclusion="PASS"),
            lambda trace: trace["records"][7]["payload"].update(conclusion="FAIL"),
            lambda trace: trace["records"][4]["payload"].pop("finding_id"),
            lambda trace: trace["records"][4]["payload"].pop("finding_digest"),
            lambda trace: trace["records"][4]["payload"].update(finding_summary="not-opaque"),
            lambda trace: trace["records"][7]["payload"].update(finding_id="finding-m1-generation-2"),
            lambda trace: trace["records"][7]["payload"].update(
                finding_digest="sha256:" + "4" * 64
            ),
            lambda trace: trace["records"].pop(4),
            lambda trace: trace["records"].insert(5, copy.deepcopy(trace["records"][4])),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_remediation_requires_failed_lineage_ordinal_target_and_budget(self) -> None:
        mutations = (
            lambda trace: trace["records"][5]["payload"].update(remediation_ordinal=0),
            lambda trace: trace["records"][5]["payload"].update(remediation_ordinal=2),
            lambda trace: trace["records"][5]["payload"].update(
                failed_accepted_event_id=trace["records"][6]["event_id"]
            ),
            lambda trace: trace["records"][5]["payload"].update(
                failed_qa_event_id=trace["records"][7]["event_id"]
            ),
            lambda trace: trace["records"][5]["payload"].update(
                failed_verification_obligation_id=trace["records"][6]["payload"][
                    "verification_obligation_id"
                ]
            ),
            lambda trace: trace["records"][5]["payload"].update(finding_id="finding-other"),
            lambda trace: trace["records"][5]["payload"].update(
                finding_digest="sha256:" + "4" * 64
            ),
            lambda trace: trace["records"][5]["payload"].update(authorized=1),
            lambda trace: trace["records"][5]["payload"].update(consumed=1),
            lambda trace: trace["records"][5]["payload"].update(remaining=0),
            lambda trace: trace["records"][0]["payload"]["policy"].update(
                max_remediation_generations=0
            ),
            lambda trace: trace["records"][0]["payload"]["policy"].update(
                max_remediation_generations=2
            ),
            lambda trace: trace["records"][0]["payload"]["policy"].update(consumed=1),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation, refresh_digest=index >= 10)

    def test_remediation_cannot_precede_qa_follow_pass_or_repeat(self) -> None:
        mutations = (
            lambda trace: trace["records"].__setitem__(slice(4, 6), [trace["records"][5], trace["records"][4]]),
            lambda trace: trace["records"].__setitem__(slice(5, 8), [trace["records"][6], trace["records"][7], trace["records"][5]]),
            lambda trace: trace["records"].insert(8, copy.deepcopy(trace["records"][5])),
            lambda trace: trace["records"][4]["payload"].update(conclusion="PASS"),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_success_and_result_are_gated_to_generation_2_pass_only(self) -> None:
        mutations = (
            lambda trace: trace["records"][8]["binding"].update(generation=1),
            lambda trace: trace["records"][8]["payload"].update(
                accepted_event_id=trace["records"][3]["event_id"]
            ),
            lambda trace: trace["records"][8]["payload"].update(
                qa_event_id=trace["records"][4]["event_id"]
            ),
            lambda trace: trace["records"][8]["payload"].update(
                candidate_id=trace["records"][3]["payload"]["candidate_id"]
            ),
            lambda trace: trace["records"][8]["payload"].update(
                candidate_digest=trace["records"][3]["payload"]["candidate_digest"]
            ),
            lambda trace: trace["records"][8]["payload"].update(
                verification_obligation_id=trace["records"][3]["payload"]["verification_obligation_id"]
            ),
            lambda trace: trace["records"][8]["payload"].update(qa_conclusion="FAIL"),
            lambda trace: trace["records"].__setitem__(slice(7, 9), [trace["records"][8], trace["records"][7]]),
            lambda trace: trace["records"][9]["binding"].update(generation=1),
            lambda trace: trace["records"][9]["payload"].update(
                accepted_event_id=trace["records"][3]["event_id"]
            ),
            lambda trace: trace["records"][9]["payload"].update(run_outcome="failed"),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_controller_and_telos_evidence_are_strictly_separate(self) -> None:
        result_evidence = self.trace["records"][9]["payload"]["evidence_event_ids"]
        telos_evidence = self.trace["records"][10]["payload"]["evidence_event_ids"]
        self.assertEqual(result_evidence, [record["event_id"] for record in self.trace["records"][6:9]])
        self.assertEqual(telos_evidence, [record["event_id"] for record in self.trace["records"][3:10]])

        mutations = (
            lambda trace: trace["records"][9]["payload"]["evidence_event_ids"].insert(
                0, trace["records"][3]["event_id"]
            ),
            lambda trace: trace["records"][9]["payload"]["evidence_event_ids"].reverse(),
            lambda trace: trace["records"][9]["payload"]["evidence_event_ids"].pop(),
            lambda trace: trace["records"][9]["payload"].update(sub_goal_status="complete"),
            lambda trace: trace["records"][9]["payload"].update(disposition="complete"),
            lambda trace: trace["records"][10]["payload"]["evidence_event_ids"].pop(0),
            lambda trace: trace["records"][10]["payload"]["evidence_event_ids"].reverse(),
            lambda trace: trace["records"][10]["payload"].update(result_id="result-other"),
            lambda trace: trace["records"][10]["payload"].update(
                result_event_id=trace["records"][8]["event_id"]
            ),
            lambda trace: trace["records"][10]["payload"].update(disposition="blocked"),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_every_wrong_actor_role_and_action_is_rejected(self) -> None:
        authority = self.trace["records"][0]["payload"]["authority"]
        expected_roles = [record["actor"]["role"] for record in self.trace["records"]]
        for record_index, expected_role in enumerate(expected_roles):
            for wrong_role in ("telos", "controller", "implementer", "qa"):
                if wrong_role == expected_role:
                    continue
                with self.subTest(record=record_index, role=wrong_role):
                    self.assert_rejected(
                        lambda trace, record_index=record_index, wrong_role=wrong_role: trace["records"][
                            record_index
                        ].update(
                            actor={
                                "role": wrong_role,
                                "actor_id": authority[wrong_role]["actor_id"],
                            }
                        )
                    )

    def test_fixture_actor_id_distinction_and_action_ceiling_are_exact(self) -> None:
        mutations = (
            lambda trace: trace["records"][0]["payload"]["authority"]["qa"].update(
                actor_id="actor-controller-m1"
            ),
            lambda trace: trace["records"][4]["actor"].update(actor_id="actor-unbound-qa"),
            lambda trace: trace["records"][6]["payload"].update(
                implementer_actor_id="actor-unbound-implementer"
            ),
            lambda trace: trace["records"][0]["payload"]["authority"]["controller"]["actions"].append(
                "telos.sub_goal.adjudicated"
            ),
            lambda trace: trace["records"][0]["payload"]["authority"]["controller"]["actions"].pop(),
            lambda trace: trace["records"][0]["payload"]["authority"]["controller"]["actions"].reverse(),
            lambda trace: trace["records"][0]["payload"]["authority"]["implementer"]["actions"].append(
                "controller.run.succeeded"
            ),
            lambda trace: trace["records"][0]["payload"]["authority"]["qa"]["actions"].append(
                "controller.run.succeeded"
            ),
            lambda trace: trace["records"][0]["payload"]["authority"]["telos"]["actions"].insert(
                0, "telos.delegation.authorized"
            ),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation, refresh_digest=True)

    def test_only_fixture_telos_actor_can_record_terminal_complete(self) -> None:
        mutations = (
            lambda trace: trace["records"][10].update(
                actor={"role": "controller", "actor_id": "actor-controller-m1"}
            ),
            lambda trace: trace["records"][10]["actor"].update(actor_id="actor-unbound-telos"),
            lambda trace: trace["records"].pop(),
            lambda trace: trace["records"].append(copy.deepcopy(trace["records"][10])),
            lambda trace: trace["records"].__setitem__(slice(9, 11), [trace["records"][10], trace["records"][9]]),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_projection_attributes_fixture_claims_without_controller_status_smuggling(self) -> None:
        projection = validate_and_project(self.trace)
        history = projection["generation_history"]
        self.assertEqual(history[0]["qa_adjudication"]["actor_id"], "actor-qa-m1")
        self.assertEqual(history[1]["qa_adjudication"]["actor_id"], "actor-qa-m1")
        self.assertEqual(projection["controller_success"]["actor_id"], "actor-controller-m1")
        self.assertEqual(projection["controller_result"]["actor_id"], "actor-controller-m1")
        self.assertEqual(projection["telos_adjudication"]["actor_id"], "actor-telos-m1")
        self.assertEqual(projection["telos_adjudication"]["disposition"], "complete")
        self.assertNotIn("sub_goal_status", projection["controller_result"])
        self.assertNotIn("disposition", projection["controller_result"])
        self.assertNotIn(history[0]["accepted_generation"]["event_id"], projection["controller_result"]["evidence_event_ids"])

    def test_projection_is_stable_for_input_object_order_and_in_process(self) -> None:
        expected = PROJECTION_PATH.read_bytes()
        reordered = _reverse_objects(self.trace)
        self.assertEqual(canonical_json_bytes(validate_and_project(reordered)), expected)
        for _ in range(25):
            self.assertEqual(canonical_json_bytes(validate_and_project(self.trace)), expected)

    def test_projection_is_byte_deterministic_across_processes_and_hash_seeds(self) -> None:
        expected = PROJECTION_PATH.read_bytes()
        for seed in ("0", "1", "42", "314159", "random"):
            environment = os.environ.copy()
            environment["PYTHONHASHSEED"] = seed
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            with self.subTest(seed=seed):
                for _ in range(2):
                    completed = subprocess.run(
                        [sys.executable, str(SCRIPT_PATH), str(TRACE_PATH)],
                        cwd=ROOT,
                        env=environment,
                        check=False,
                        capture_output=True,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr.decode())
                    self.assertEqual(completed.stdout, expected)

    def test_cli_rejects_noncanonical_or_wrong_expected_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            noncanonical = Path(temporary) / "noncanonical.json"
            noncanonical.write_text(json.dumps(self.expected, indent=2) + "\n", encoding="utf-8")
            wrong = Path(temporary) / "wrong.json"
            wrong_projection = copy.deepcopy(self.expected)
            wrong_projection["state"] = "result_reported"
            wrong.write_bytes(canonical_json_bytes(wrong_projection))

            cases = (
                (noncanonical, "not canonical JSON bytes"),
                (wrong, "does not match expected bytes"),
            )
            for path, message in cases:
                with self.subTest(path=path.name):
                    completed = subprocess.run(
                        [sys.executable, str(SCRIPT_PATH), "--check", str(TRACE_PATH), str(path)],
                        cwd=ROOT,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(completed.returncode, 1)
                    self.assertEqual(completed.stdout, "")
                    self.assertIn(message, completed.stderr)
                    self.assertNotIn("Traceback", completed.stderr)


if __name__ == "__main__":
    unittest.main()
