"""Adversarial tests for the frozen provider-free M0 reference trace."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable

from scripts.m0_trace import (
    StrictJSONError,
    TraceValidationError,
    canonical_json_bytes,
    compute_delegation_digest,
    load_json_strict,
    strict_json_loads,
    validate_and_project,
)


ROOT = Path(__file__).resolve().parents[2]
TRACE_PATH = ROOT / "spec/m0/v0/golden/valid-telos-adjudication-trace.json"
PROJECTION_PATH = ROOT / "spec/m0/v0/golden/expected-projection.json"
CONTRACT_PATH = ROOT / "spec/m0/v0/trace-contract.json"
SCHEMA_PATH = ROOT / "spec/m0/v0/telos-adjudication-trace.schema.json"
SCRIPT_PATH = ROOT / "scripts/m0_trace.py"


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


class M0TraceTest(unittest.TestCase):
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
        with self.assertRaises((StrictJSONError, TraceValidationError)):
            validate_and_project(candidate)

    def test_golden_trace_produces_exact_canonical_projection(self) -> None:
        projection = validate_and_project(self.trace)
        self.assertEqual(projection, self.expected)
        self.assertEqual(canonical_json_bytes(projection), PROJECTION_PATH.read_bytes())
        self.assertEqual(projection["state"], "telos_adjudicated")
        self.assertEqual(projection["telos_adjudication"]["disposition"], "complete")

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

    def test_contract_schema_and_fixture_versions_are_bound(self) -> None:
        contract = load_json_strict(CONTRACT_PATH)
        schema = load_json_strict(SCHEMA_PATH)
        events = [record["event_type"] for record in self.trace["records"]]
        self.assertEqual(events, contract["event_sequence"])
        self.assertEqual(events, [transition[1] for transition in contract["transitions"]])
        self.assertEqual(contract["transitions"][-1][2], self.expected["state"])
        self.assertEqual(self.trace["schema_version"], contract["trace_version"])
        self.assertEqual(self.expected["schema_version"], contract["projection_version"])
        self.assertEqual(schema["properties"]["schema_version"]["const"], contract["trace_version"])
        self.assertFalse(schema["additionalProperties"])
        authority = self.trace["records"][0]["payload"]["authority"]
        for role, actions in contract["delegated_actions"].items():
            self.assertEqual(authority[role]["actions"], actions)
        for record in self.trace["records"]:
            self.assertIn(record["event_type"], contract["actor_action_ceiling"][record["actor"]["role"]])

    def test_projection_attributes_semantic_conclusions(self) -> None:
        projection = validate_and_project(self.trace)
        self.assertEqual(projection["qa_adjudication"]["actor_id"], "actor-qa-m0")
        self.assertEqual(projection["qa_adjudication"]["conclusion"], "PASS")
        self.assertEqual(projection["controller_result"]["actor_id"], "actor-controller-m0")
        self.assertEqual(projection["telos_adjudication"]["actor_id"], "actor-telos-m0")
        self.assertNotIn("sub_goal_status", projection["controller_result"])

    def test_validation_does_not_mutate_input(self) -> None:
        original = copy.deepcopy(self.trace)
        validate_and_project(self.trace)
        self.assertEqual(self.trace, original)

    def test_strict_json_rejects_duplicates_floats_constants_and_nulls(self) -> None:
        invalid_documents = (
            '{"schema_version":"a","schema_version":"b","records":[]}',
            '{"records":[{"payload":{"generation":1.0}}]}',
            '{"records":[{"payload":{"score":NaN}}]}',
            '{"records":[{"payload":null}]}',
            '{"outer":{"key":1,"key":2}}',
        )
        for document in invalid_documents:
            with self.subTest(document=document):
                with self.assertRaises(StrictJSONError):
                    strict_json_loads(document)

    def test_float_and_null_are_rejected_when_validator_is_called_directly(self) -> None:
        self.assert_rejected(lambda trace: trace["records"][1]["payload"].update(extra=1.5))
        self.assert_rejected(lambda trace: trace["records"][1].update(payload=None))

    def test_boolean_cannot_serve_as_generation_integer(self) -> None:
        self.assert_rejected(lambda trace: trace["records"][4]["binding"].update(generation=True))

    def test_unsupported_document_and_record_versions_are_rejected(self) -> None:
        self.assert_rejected(lambda trace: trace.update(schema_version="noetic.m0.telos-adjudication-trace/v1"))
        for index in range(8):
            with self.subTest(index=index):
                self.assert_rejected(
                    lambda trace, index=index: trace["records"][index].update(
                        schema_version="noetic.m0.trace-record/v1"
                    )
                )

    def test_unknown_fields_are_rejected_at_every_shape_layer(self) -> None:
        mutations = (
            lambda trace: trace.update(extra="forbidden"),
            lambda trace: trace["records"][1].update(extra="forbidden"),
            lambda trace: trace["records"][1]["actor"].update(extra="forbidden"),
            lambda trace: trace["records"][1]["binding"].update(extra="forbidden"),
            lambda trace: trace["records"][1]["payload"].update(extra="forbidden"),
            lambda trace: trace["records"][0]["payload"].update(extra="forbidden"),
            lambda trace: trace["records"][0]["payload"]["authority"].update(extra={}),
            lambda trace: trace["records"][0]["payload"]["authority"]["qa"].update(
                extra="forbidden"
            ),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_missing_fields_are_rejected_at_every_shape_layer(self) -> None:
        mutations = (
            lambda trace: trace.pop("records"),
            lambda trace: trace["records"][2].pop("actor"),
            lambda trace: trace["records"][2]["actor"].pop("actor_id"),
            lambda trace: trace["records"][2]["binding"].pop("program_id"),
            lambda trace: trace["records"][3]["payload"].pop("implementer_actor_id"),
            lambda trace: trace["records"][3]["payload"].pop("verification_obligation_id"),
            lambda trace: trace["records"][0]["payload"].pop("expires_at"),
            lambda trace: trace["records"][0]["payload"]["authority"].pop("qa"),
            lambda trace: trace["records"][0]["payload"]["authority"]["qa"].pop("actions"),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_malformed_binding_identifiers_and_digests_are_rejected(self) -> None:
        bad_values = {
            "delegation_id": "delegation_unsafe",
            "delegation_digest": "sha256:ABC",
            "goal_chain_id": "chain-0",
            "sub_goal_id": "subgoal-x",
            "program_id": "program_unsafe",
            "run_id": "run/unsafe",
            "correlation_id": "correlation_unsafe",
        }
        for field, value in bad_values.items():
            with self.subTest(field=field):
                self.assert_rejected(
                    lambda trace, field=field, value=value: trace["records"][2]["binding"].update(
                        {field: value}
                    )
                )

    def test_malformed_event_actor_candidate_obligation_and_result_ids_are_rejected(self) -> None:
        mutations = (
            lambda trace: trace["records"][2].update(event_id="event_bad"),
            lambda trace: trace["records"][2]["actor"].update(actor_id="actor_bad"),
            lambda trace: trace["records"][3]["payload"].update(candidate_id="candidate_bad"),
            lambda trace: trace["records"][3]["payload"].update(candidate_digest="sha256:1234"),
            lambda trace: trace["records"][3]["payload"].update(
                verification_obligation_id="obligation_bad"
            ),
            lambda trace: trace["records"][6]["payload"].update(result_id="result_bad"),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_every_downstream_identity_binding_mismatch_is_rejected(self) -> None:
        mismatches: dict[str, Any] = {
            "delegation_id": "delegation-other",
            "delegation_digest": "sha256:" + "2" * 64,
            "goal_chain_id": "chain-34",
            "sub_goal_id": "subgoal-34",
            "program_id": "program-other",
            "run_id": "run-other-1",
            "generation": 2,
            "correlation_id": "correlation-other-1",
        }
        for field, value in mismatches.items():
            with self.subTest(field=field):
                self.assert_rejected(
                    lambda trace, field=field, value=value: trace["records"][4]["binding"].update(
                        {field: value}
                    )
                )

    def test_delegation_digest_binds_identity_authority_and_validity_material(self) -> None:
        def replace_run(trace: dict[str, Any]) -> None:
            for record in trace["records"]:
                record["binding"]["run_id"] = "run-other-1"

        def replace_root_event(trace: dict[str, Any]) -> None:
            trace["records"][0]["event_id"] = "event-other-authorization"
            trace["records"][1]["caused_by"] = ["event-other-authorization"]

        def replace_telos_identity(trace: dict[str, Any]) -> None:
            trace["records"][0]["actor"]["actor_id"] = "actor-other-telos"
            trace["records"][0]["payload"]["authority"]["telos"]["actor_id"] = (
                "actor-other-telos"
            )
            trace["records"][7]["actor"]["actor_id"] = "actor-other-telos"

        mutations = (
            lambda trace: trace["records"][0]["payload"].update(
                purpose="purpose-other-proof"
            ),
            lambda trace: trace["records"][0]["payload"].update(
                expires_at="2026-07-17T12:00:00Z"
            ),
            replace_run,
            replace_root_event,
            replace_telos_identity,
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_strict_utc_timestamp_forms(self) -> None:
        invalid = (
            "2026-07-15",
            "2026-07-15T12:00:01",
            "2026-07-15T12:00:01+00:00",
            "2026-07-15T12:00:01.000Z",
            "2026-02-30T12:00:01Z",
            "2026-07-15t12:00:01z",
        )
        for timestamp in invalid:
            with self.subTest(timestamp=timestamp):
                self.assert_rejected(
                    lambda trace, timestamp=timestamp: trace["records"][1].update(
                        occurred_at=timestamp
                    )
                )

    def test_causal_timestamps_are_strictly_increasing_and_within_delegation(self) -> None:
        mutations = (
            lambda trace: trace["records"][2].update(occurred_at="2026-07-15T12:00:01Z"),
            lambda trace: trace["records"][7].update(occurred_at="2026-07-16T12:00:00Z"),
            lambda trace: trace["records"][0]["payload"].update(
                valid_from="2026-07-15T12:00:01Z"
            ),
            lambda trace: trace["records"][0]["payload"].update(
                expires_at="2026-07-15T12:00:00Z"
            ),
            lambda trace: trace["records"][0]["payload"].update(revocation_status="revoked"),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation, refresh_digest=index in (2, 3, 4))

    def test_every_wrong_actor_action_combination_is_rejected(self) -> None:
        authorities = self.trace["records"][0]["payload"]["authority"]
        expected_roles = ("telos", "controller", "controller", "controller", "qa", "controller", "controller", "telos")
        for record_index, expected_role in enumerate(expected_roles):
            for wrong_role in ("telos", "controller", "implementer", "qa"):
                if wrong_role == expected_role:
                    continue
                with self.subTest(record=record_index, role=wrong_role):
                    self.assert_rejected(
                        lambda trace, record_index=record_index, wrong_role=wrong_role: trace[
                            "records"
                        ][record_index].update(
                            actor={
                                "role": wrong_role,
                                "actor_id": authorities[wrong_role]["actor_id"],
                            }
                        )
                    )

    def test_every_event_action_is_fixed_to_its_state_transition(self) -> None:
        event_types = [record["event_type"] for record in self.trace["records"]]
        for index, current in enumerate(event_types):
            for replacement in event_types:
                if replacement == current:
                    continue
                with self.subTest(index=index, replacement=replacement):
                    self.assert_rejected(
                        lambda trace, index=index, replacement=replacement: trace["records"][
                            index
                        ].update(event_type=replacement)
                    )

    def test_authority_is_complete_narrow_and_attenuated(self) -> None:
        mutations = (
            lambda trace: trace["records"][0]["payload"]["authority"]["controller"][
                "actions"
            ].append("telos.sub_goal.adjudicated"),
            lambda trace: trace["records"][0]["payload"]["authority"]["controller"][
                "actions"
            ].pop(),
            lambda trace: trace["records"][0]["payload"]["authority"]["controller"][
                "actions"
            ].reverse(),
            lambda trace: trace["records"][0]["payload"]["authority"]["implementer"][
                "actions"
            ].append("controller.run.succeeded"),
            lambda trace: trace["records"][0]["payload"]["authority"]["qa"]["actions"].append(
                "controller.run.succeeded"
            ),
            lambda trace: trace["records"][0]["payload"]["authority"]["telos"][
                "actions"
            ].insert(0, "telos.delegation.authorized"),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_delegated_identities_must_be_unique_and_events_must_use_them(self) -> None:
        self.assert_rejected(
            lambda trace: trace["records"][0]["payload"]["authority"]["qa"].update(
                actor_id="actor-controller-m0"
            )
        )
        self.assert_rejected(
            lambda trace: trace["records"][4]["actor"].update(actor_id="actor-unbound-qa")
        )
        self.assert_rejected(
            lambda trace: trace["records"][3]["payload"].update(
                implementer_actor_id="actor-unbound-implementer"
            )
        )

    def test_missing_duplicate_skipped_reordered_and_replayed_records_are_rejected(self) -> None:
        self.assert_rejected(lambda trace: trace["records"].pop(4))
        self.assert_rejected(lambda trace: trace["records"].insert(5, copy.deepcopy(trace["records"][4])))
        self.assert_rejected(
            lambda trace: trace["records"].__setitem__(
                slice(2, 4), [trace["records"][3], trace["records"][2]]
            )
        )
        self.assert_rejected(
            lambda trace: trace["records"][4].update(event_id=trace["records"][3]["event_id"])
        )
        self.assert_rejected(
            lambda trace: trace["records"][5].update(caused_by=[trace["records"][3]["event_id"]])
        )

    def test_cyclic_self_and_forward_causes_are_rejected(self) -> None:
        self.assert_rejected(
            lambda trace: trace["records"][4].update(caused_by=[trace["records"][4]["event_id"]])
        )
        self.assert_rejected(
            lambda trace: trace["records"][4].update(caused_by=[trace["records"][5]["event_id"]])
        )
        self.assert_rejected(
            lambda trace: trace["records"][0].update(caused_by=[trace["records"][7]["event_id"]])
        )

    def test_accepted_generation_creates_the_only_qa_obligation(self) -> None:
        mutations = (
            lambda trace: trace["records"][4]["payload"].update(
                accepted_event_id="event-other-accepted"
            ),
            lambda trace: trace["records"][4]["payload"].update(
                candidate_id="candidate-other-generation-1"
            ),
            lambda trace: trace["records"][4]["payload"].update(
                candidate_digest="sha256:" + "2" * 64
            ),
            lambda trace: trace["records"][4]["payload"].update(
                verification_obligation_id="obligation-other-generation-1"
            ),
            lambda trace: trace["records"][4]["binding"].update(generation=2),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_qa_must_be_exactly_one_distinct_pass_before_success(self) -> None:
        self.assert_rejected(lambda trace: trace["records"][4]["payload"].update(conclusion="FAIL"))
        self.assert_rejected(
            lambda trace: trace["records"][4].update(
                actor={"role": "implementer", "actor_id": "actor-implementer-m0"}
            )
        )
        self.assert_rejected(lambda trace: trace["records"].pop(4))
        self.assert_rejected(lambda trace: trace["records"].insert(5, copy.deepcopy(trace["records"][4])))
        self.assert_rejected(
            lambda trace: trace["records"].__setitem__(
                slice(4, 6), [trace["records"][5], trace["records"][4]]
            )
        )
        self.assert_rejected(lambda trace: trace["records"][5]["payload"].update(qa_conclusion="FAIL"))

    def test_success_result_and_terminal_records_bind_the_same_evidence(self) -> None:
        mutations = (
            lambda trace: trace["records"][5]["payload"].update(
                accepted_event_id="event-other-accepted"
            ),
            lambda trace: trace["records"][5]["payload"].update(qa_event_id="event-other-qa"),
            lambda trace: trace["records"][5]["payload"].update(
                candidate_digest="sha256:" + "2" * 64
            ),
            lambda trace: trace["records"][5]["payload"].update(
                verification_obligation_id="obligation-other-generation-1"
            ),
            lambda trace: trace["records"][6]["payload"].update(
                success_event_id="event-other-success"
            ),
            lambda trace: trace["records"][6]["payload"].update(qa_event_id="event-other-qa"),
            lambda trace: trace["records"][6]["payload"]["evidence_event_ids"].reverse(),
            lambda trace: trace["records"][6]["payload"]["evidence_event_ids"].pop(),
            lambda trace: trace["records"][7]["payload"].update(result_id="result-other-1"),
            lambda trace: trace["records"][7]["payload"].update(
                result_event_id="event-other-result"
            ),
            lambda trace: trace["records"][7]["payload"]["evidence_event_ids"].pop(),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_controller_cannot_supply_or_imply_sub_goal_status(self) -> None:
        self.assert_rejected(
            lambda trace: trace["records"][5]["payload"].update(sub_goal_status="complete")
        )
        self.assert_rejected(
            lambda trace: trace["records"][6]["payload"].update(sub_goal_status="complete")
        )
        self.assert_rejected(
            lambda trace: trace["records"][6]["payload"].update(disposition="complete")
        )

    def test_only_telos_can_adjudicate_and_terminal_state_is_monotonic(self) -> None:
        self.assert_rejected(
            lambda trace: trace["records"][7].update(
                actor={"role": "controller", "actor_id": "actor-controller-m0"}
            )
        )
        self.assert_rejected(lambda trace: trace["records"].pop())
        self.assert_rejected(lambda trace: trace["records"].append(copy.deepcopy(trace["records"][7])))
        self.assert_rejected(
            lambda trace: trace["records"].__setitem__(
                slice(6, 8), [trace["records"][7], trace["records"][6]]
            )
        )

    def test_bad_enums_types_and_contradictory_operations_are_rejected(self) -> None:
        mutations = (
            lambda trace: trace["records"][1]["payload"].update(operation="start_run"),
            lambda trace: trace["records"][3]["payload"].update(operation="succeed_run"),
            lambda trace: trace["records"][4]["payload"].update(conclusion="INCONCLUSIVE"),
            lambda trace: trace["records"][6]["payload"].update(run_outcome="failed"),
            lambda trace: trace["records"][7]["payload"].update(disposition="blocked"),
            lambda trace: trace["records"][1].update(caused_by="event-delegation-authorized"),
            lambda trace: trace["records"][3].update(payload="not-an-object"),
            lambda trace: trace["records"][3]["payload"].update(candidate_digest=True),
            lambda trace: trace["records"][0]["payload"]["authority"]["qa"].update(actions=True),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

    def test_projection_is_stable_for_input_object_order(self) -> None:
        reordered = _reverse_objects(self.trace)
        self.assertEqual(
            canonical_json_bytes(validate_and_project(reordered)),
            canonical_json_bytes(validate_and_project(self.trace)),
        )

    def test_projection_is_byte_deterministic_in_process(self) -> None:
        expected = PROJECTION_PATH.read_bytes()
        for _ in range(25):
            self.assertEqual(canonical_json_bytes(validate_and_project(self.trace)), expected)

    def test_projection_is_byte_deterministic_across_processes_and_hash_seeds(self) -> None:
        expected = PROJECTION_PATH.read_bytes()
        for seed in ("0", "1", "42", "314159", "random"):
            environment = os.environ.copy()
            environment["PYTHONHASHSEED"] = seed
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

    def test_cli_rejects_noncanonical_expected_projection_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            expected_path = Path(temporary) / "expected.json"
            expected_path.write_text(json.dumps(self.expected, indent=2) + "\n", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--check", str(TRACE_PATH), str(expected_path)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("not canonical JSON bytes", completed.stderr)


if __name__ == "__main__":
    unittest.main()
