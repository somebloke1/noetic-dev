"""Concrete SQLite protocol checks; no live roles, models, or downstream QA."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from scripts import noetic_controller as controller


class ControllerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store_number = 0

    def start(self, kind="development", **kwargs):
        self.store_number += 1
        self.store = self.root / f"run-{self.store_number}.sqlite"
        return controller.start_run(
            self.store, controller.PATTERN_DIR / f"{kind}.json",
            "Deliver the requested behavior", self.root,
            inputs={"sources": [{"ref": "fixture:acceptance-criteria"}]}, **kwargs,
        )

    def activation(self, state):
        return state["activations"][state["current_activation"]]

    def content(self, phase):
        return {
            "design_intent": {"objective": "Deliver behavior", "scope": ["local kernel"], "acceptance_criteria": ["Persist transitions"]},
            "abstract_design": {"components": ["kernel"], "interfaces": ["submit_result"], "decision": "Use SQLite"},
            "implementation_procedure_design": {"steps": ["Implement", "Run focused checks"]},
            "implementation": {"report": "Test fixture, not real implementation evidence", "changes": ["fixture.py"], "verification": [{"command": "fixture-check", "exit_code": 0}]},
            "P1": {"observations": ["Fixture observed"], "questions": ["What follows?"], "evidence_refs": ["fixture:1"]},
            "P2": {"hypotheses": ["One possible explanation"]},
            "P3": {"judgment": "Conditionally supported", "grounds": ["fixture:1"], "conditions": ["Limited fixture"]},
            "P4": {"decision": "Proceed", "rationale": "Grounded in the judgment", "next_actions": ["Implement"]},
        }[phase]

    def result(self, state, verdict="pass"):
        activation = self.activation(state)
        if activation["mode"] == "review":
            return {"subject_artifact_id": state["subject_artifact_id"], "verdict": verdict,
                    "report": "Checked explicit acceptance criteria",
                    "findings": [] if verdict == "pass" else [{"description": "Concrete fixture defect", "blocking": True}]}
        outcome = "produced" if activation["mode"] == "produce" else ("complete" if activation["phase"] == "P4" else "advance")
        return {"outcome": outcome, "content": self.content(activation["phase"])}

    def submit(self, state, result=None):
        activation = self.activation(state)
        result = self.result(state) if result is None else result
        if activation["status"] == "ready":
            state = controller.begin_activation(self.store, activation["id"], state["version"])
        return controller.submit_result(self.store, activation["id"], state["version"], result,
                                        f"session:{activation['id']}", f"command:{activation['id']}")

    def reach(self, state, phase):
        while self.activation(state)["phase"] != phase:
            state = self.submit(state)
        return state

    def returning(self, target):
        return {"outcome": "return", "target": target, "reason": "The evidence is incomplete",
                "question": "Which observation would resolve this?", "content": {"unfinished": "Need more data"}}

    def assert_serial(self, state):
        active = [item["id"] for item in state["activations"].values() if item["status"] in ("ready", "running")]
        self.assertEqual(active, [state["current_activation"]] if state["current_activation"] else [])
        for activation in state["activations"].values():
            actor = state["actors"][activation["actor_id"]]
            self.assertEqual(actor["status"], activation["status"])
            self.assertEqual(actor["session_ref"], activation["session_ref"])

    def assert_rejected(self, state, result, **overrides):
        activation = self.activation(state)
        if activation["status"] == "ready":
            state = controller.begin_activation(self.store, activation["id"], state["version"])
        arguments = {"activation_id": activation["id"], "expected_version": state["version"], "result": result,
                     "session_ref": f"session:{activation['id']}", "command_id": "invalid-command"}
        arguments.update(overrides)
        with self.assertRaises(controller.ControllerError):
            controller.submit_result(self.store, **arguments)
        self.assertEqual(controller.inspect_run(self.store), state)
        with closing(sqlite3.connect(self.store)) as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM commands WHERE command_id = ?", (arguments["command_id"],)).fetchone())
        return state

    def test_all_four_development_phases_require_subject_specific_qa(self):
        state = self.start(max_remediations=0)
        self.assertEqual(self.activation(state)["ordinal"], "0.0")
        for phase in state["pattern"]["phases"]:
            producer = self.activation(state)
            self.assertEqual(producer["phase"], phase["id"])
            self.assertEqual(producer["generation"], 0)
            self.assertEqual(producer["role"], phase["role"])
            self.assertNotIn(f"accepted.{phase['id']}", state["slots"])
            for slot, artifact_type in phase["required_inputs"].items():
                artifact_id = producer["input_bindings"][slot]
                self.assertEqual(state["artifacts"][artifact_id]["type"], artifact_type)
                self.assertEqual(state["slots"][slot], artifact_id)
            state = self.submit(state)
            self.assert_serial(state)
            reviewer = self.activation(state)
            self.assertEqual(state["machine_state"], "qa_review")
            self.assertEqual(reviewer["role"], "independent_qa")
            subject = state["subject_artifact_id"]
            self.assertEqual(reviewer["input_bindings"]["subject"], subject)
            self.assertNotIn(f"accepted.{phase['id']}", state["slots"])
            self.assertIn("non-perfectionistic", reviewer["qa_framing"])
            state = self.submit(state)
            self.assertEqual(state["slots"][f"accepted.{phase['id']}"], subject)
        self.assertEqual(state["status"], "completed")
        self.assert_serial(state)
        self.assertIsNone(controller.result_contract(state))
        self.assertEqual(len(state["activations"]), 8)
        actors = list(state["actors"].values())
        self.assertEqual([actor["ordinal"] for actor in actors], [f"0.{i}" for i in range(8)])
        self.assertEqual(len({actor["session_ref"] for actor in actors}), 8)
        transitions = [event["data"] for event in state["events"] if event["kind"] == "transition"]
        for phase in state["pattern"]["phases"]:
            rows = [row for row in transitions if row["phase"] == phase["id"]]
            self.assertEqual([row["on"] for row in rows], ["activate", "produced", "pass"])
        self.assertEqual(controller.inspect_run(self.store), state)

    def test_every_phase_can_remediate_with_fresh_author_and_qa(self):
        state = self.start(max_remediations=2)
        for phase in state["pattern"]["phases"]:
            self.assertEqual(self.activation(state)["generation"], 0)
            for generation in range(2):
                state = self.submit(state)
                subject = state["subject_artifact_id"]
                reviewer_id = state["current_activation"]
                state = self.submit(state, self.result(state, "fail"))
                author = self.activation(state)
                self.assertEqual(state["machine_state"], "remediating")
                self.assertEqual(author["generation"], generation + 1)
                self.assertEqual(author["phase"], phase["id"])
                self.assertNotEqual(author["id"], reviewer_id)
                self.assertEqual(author["input_bindings"]["subject"], subject)
                self.assertEqual(state["artifacts"][author["input_bindings"]["feedback.qa"]]["type"], "qa.review")
                self.assertNotIn(f"accepted.{phase['id']}", state["slots"])
                self.assert_serial(state)
            state = self.submit(state)
            self.assertEqual(self.activation(state)["generation"], 2)
            self.assertNotEqual(state["current_activation"], reviewer_id)
            self.assertNotEqual(state["subject_artifact_id"], subject)
            state = self.submit(state)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(len(state["actors"]), 24)
        self.assertEqual(len({actor["session_ref"] for actor in state["actors"].values()}), 24)

    def test_exhaustion_is_non_success_in_every_phase_including_zero_budget(self):
        phases = ["design_intent", "abstract_design", "implementation_procedure_design", "implementation"]
        for phase in phases:
            for budget in (0, 1):
                with self.subTest(phase=phase, budget=budget):
                    state = self.reach(self.start(max_remediations=budget), phase)
                    for _ in range(budget + 1):
                        state = self.submit(state)
                        self.assertEqual(self.activation(state)["mode"], "review")
                        state = self.submit(state, self.result(state, "fail"))
                    self.assertEqual(state["status"], "blocked")
                    self.assertEqual(state["reason"], f"remediations_exhausted:{phase}")
                    self.assertEqual(state["generation"], budget)
                    self.assertNotIn(f"accepted.{phase}", state["slots"])
                    self.assert_serial(state)

    def test_qa_rejects_wrong_subject_blocking_pass_and_malformed_reports(self):
        state = self.submit(self.start())
        valid = self.result(state)
        for change in (
            {"subject_artifact_id": "artifact-missing"}, {"subject_artifact_id": state["slots"]["external.purpose"]},
            {"findings": [{"description": "Missing requirement", "blocking": True}]},
            {"findings": [{"description": "Unclassified"}]}, {"findings": "none"}, {"report": ""},
            {"outcome": "fail"}, {"verdict": "unknown"}, {"session_ref": "model-supplied"},
        ):
            with self.subTest(change=change):
                state = self.assert_rejected(state, {**valid, **change})
        outcome_only = dict(valid)
        outcome_only["outcome"] = outcome_only.pop("verdict")
        state = self.submit(state, outcome_only)
        self.assertIn("accepted.design_intent", state["slots"])

    def test_stale_qa_cannot_accept_the_previous_generation_subject(self):
        state = self.submit(self.start())
        old_subject = state["subject_artifact_id"]
        state = self.submit(state, self.result(state, "fail"))
        state = self.submit(state)
        state = self.assert_rejected(state, {**self.result(state), "subject_artifact_id": old_subject})
        self.assertNotEqual(old_subject, state["subject_artifact_id"])
        state = self.submit(state)
        self.assertNotEqual(old_subject, state["slots"]["accepted.design_intent"])

    def test_result_shapes_for_every_role_and_model_cannot_supply_identity(self):
        for kind in ("development", "cognition"):
            state = self.start(kind)
            while state["status"] == "active":
                if self.activation(state)["mode"] != "review":
                    valid = self.result(state)
                    field = next(iter(valid["content"]))
                    for invalid in ({**valid, "content": {}}, {**valid, "content": {**valid["content"], field: 42}},
                                    {**valid, "actor_id": "model-actor"}, {**valid, "outcome": "pass"}):
                        state = self.assert_rejected(state, invalid)
                    schema = controller.result_contract(state)
                    schema = schema.get("oneOf", [schema])[0]
                    self.assertEqual(set(schema["properties"]["content"]["required"]), set(valid["content"]))
                state = self.submit(state)
            self.assertEqual(state["status"], "completed")

    def test_artifacts_are_immutable_typed_and_have_runtime_provenance(self):
        state = self.start()
        external = copy.deepcopy(state["artifacts"])
        state = self.submit(state)
        subject = state["subject_artifact_id"]
        snapshot = copy.deepcopy(state["artifacts"])
        artifact = snapshot[subject]
        canonical = json.dumps(artifact["content"], sort_keys=True, separators=(",", ":"), allow_nan=False)
        self.assertEqual(artifact["digest"], hashlib.sha256(canonical.encode()).hexdigest())
        self.assertEqual(artifact["produced_by"], "actor-0")
        self.assertEqual(artifact["activation_id"], "activation-0")
        self.assertEqual(artifact["type"], "development.design_intent")
        self.assertEqual(artifact["derived_from"], list(artifact["input_bindings"].values()))
        self.assertFalse(artifact["partial"])
        self.assertTrue(all(item["origin"] == "external" and item["produced_by"] is None for item in external.values()))
        state = self.submit(state, self.result(state, "fail"))
        state = self.submit(state)
        state = self.submit(state)
        for artifact_id, item in snapshot.items():
            self.assertEqual(state["artifacts"][artifact_id], item)
        state["artifacts"][subject]["content"]["objective"] = "caller mutation"
        self.assertEqual(controller.inspect_run(self.store)["artifacts"][subject], artifact)

    def test_typed_required_inputs_are_checked_before_start(self):
        pattern = json.loads((controller.PATTERN_DIR / "development.json").read_text())
        for invalid in (
            {"accepted.design_intent": "wrong.type"},
            {"accepted.implementation": "development.implementation"},
            {"external.sources": "wrong.type"},
        ):
            changed = copy.deepcopy(pattern)
            changed["phases"][1]["required_inputs"].update(invalid)
            with self.subTest(invalid=invalid), self.assertRaises(controller.ControllerError):
                controller.start_run(self.root / "invalid.sqlite", changed, "Purpose", self.root)
        self.assertFalse((self.root / "invalid.sqlite").exists())
        pattern["phases"][3]["required_inputs"]["external.requirements"] = "external.requirements"
        with self.assertRaisesRegex(controller.ControllerError, "Missing external"):
            controller.start_run(self.root / "missing.sqlite", pattern, "Purpose", self.root)
        state = controller.start_run(self.root / "typed.sqlite", pattern, "Purpose", self.root, inputs={"requirements": ["Explicit"]})
        self.assertIn("external.requirements", state["slots"])

    def test_transition_tables_are_data_and_not_arbitrary_expressions(self):
        pattern = json.loads((controller.PATTERN_DIR / "cognition.json").read_text())
        pattern["transitions"][0]["guard"] = "eval('anything')"
        with self.assertRaisesRegex(controller.ControllerError, "fixed transition table"):
            controller.start_run(self.root / "invalid.sqlite", pattern, "Purpose", self.root)
        self.assertFalse((self.root / "invalid.sqlite").exists())

    def test_serial_begin_stale_versions_and_submit_before_begin(self):
        state = self.start()
        result = self.result(state)
        activation_id = state["current_activation"]
        with self.assertRaises(controller.ConflictError):
            controller.submit_result(self.store, activation_id, state["version"], result, "session", "command")
        self.assertEqual(controller.inspect_run(self.store), state)
        running = controller.begin_activation(self.store, activation_id, state["version"])
        for version in (state["version"], running["version"]):
            with self.assertRaises(controller.ConflictError):
                controller.begin_activation(self.store, activation_id, version)
        self.assertEqual(controller.inspect_run(self.store), running)
        self.assert_rejected(running, result, expected_version=state["version"])
        self.assert_rejected(running, result, activation_id="activation-other")
        state = self.submit(running)
        with self.assertRaises(controller.ConflictError):
            controller.runtime_failed(self.store, activation_id, state["version"], "Old runtime failed")
        self.assertEqual(controller.inspect_run(self.store), state)

    def test_duplicate_command_returns_original_state_even_after_later_progress(self):
        state = self.start()
        activation_id = state["current_activation"]
        state = controller.begin_activation(self.store, activation_id, state["version"])
        request = {"activation_id": activation_id, "expected_version": state["version"], "result": self.result(state),
                   "session_ref": "session-original", "command_id": "command-original"}
        receipt_state = controller.submit_result(self.store, **request)
        later = self.submit(receipt_state)
        duplicate = controller.submit_result(self.store, **request)
        self.assertEqual(duplicate, receipt_state)
        self.assertEqual(controller.inspect_run(self.store), later)
        for change in ({"session_ref": "different"}, {"expected_version": later["version"]},
                       {"activation_id": later["current_activation"]}, {"result": {"outcome": "produced", "content": {}}}):
            with self.subTest(change=change), self.assertRaises(controller.ConflictError):
                controller.submit_result(self.store, **{**request, **change})
            self.assertEqual(controller.inspect_run(self.store), later)
        with closing(sqlite3.connect(self.store)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM commands").fetchone()[0], 2)
            response = connection.execute("SELECT response FROM commands WHERE command_id = ?", (request["command_id"],)).fetchone()[0]
            self.assertEqual(json.loads(response), receipt_state)

    def test_concurrent_same_command_delivery_accepts_once(self):
        state = self.start()
        activation_id = state["current_activation"]
        state = controller.begin_activation(self.store, activation_id, state["version"])
        result = self.result(state)

        def deliver(_):
            return controller.submit_result(self.store, activation_id, state["version"], result, "one-session", "one-command")

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(deliver, range(2)))
        self.assertEqual(responses[0], responses[1])
        self.assertEqual(responses[0]["version"], state["version"] + 1)
        self.assertEqual(len(responses[0]["actors"]), 2)

    def test_transaction_rolls_back_even_after_result_and_next_actor_allocation(self):
        state = self.start()
        state = controller.begin_activation(self.store, state["current_activation"], state["version"])
        original_save = controller._save

        def fail_after_save(connection, candidate):
            original_save(connection, candidate)
            raise RuntimeError("Simulated interrupted transaction")

        with patch.object(controller, "_save", side_effect=fail_after_save), self.assertRaises(RuntimeError):
            self.submit(state)
        self.assertEqual(controller.inspect_run(self.store), state)
        with closing(sqlite3.connect(self.store)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM commands").fetchone()[0], 0)
        self.assertEqual(self.submit(state)["machine_state"], "qa_review")

    def test_qa_cannot_reuse_author_or_previous_qa_sessions(self):
        state = self.submit(self.start())
        state = self.assert_rejected(state, self.result(state), session_ref="session:activation-0")
        state = self.submit(state, self.result(state, "fail"))
        state = self.assert_rejected(state, self.result(state), session_ref="session:activation-0")
        state = self.submit(state)
        for session in ("session:activation-0", "session:activation-1", "session:activation-2"):
            state = self.assert_rejected(state, self.result(state), session_ref=session)
        self.assertIn("accepted.design_intent", self.submit(state)["slots"])

    def test_cognition_forward_traversal_uses_differentiated_current_artifacts(self):
        state = self.start("cognition")
        for i in range(1, 5):
            activation = self.activation(state)
            self.assertEqual(activation["phase"], f"P{i}")
            self.assertEqual(activation["visit"], 1)
            self.assertEqual(activation["mode"], "operate")
            self.assertEqual(activation["input_bindings"]["external.purpose"], state["slots"]["external.purpose"])
            for prior in range(1, i):
                self.assertEqual(activation["input_bindings"][f"effective.P{prior}"], state["slots"][f"effective.P{prior}"])
            state = self.submit(state)
            self.assert_serial(state)
            self.assertIn(f"effective.P{i}", state["slots"])
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["returns_used"], 0)
        self.assertEqual(len(state["actors"]), 4)

    def test_all_six_backedges_invalidate_effective_bindings_and_keep_history(self):
        for source, target in (("P2", "P1"), ("P3", "P1"), ("P3", "P2"),
                               ("P4", "P1"), ("P4", "P2"), ("P4", "P3")):
            with self.subTest(source=source, target=target):
                state = self.reach(self.start("cognition"), source)
                prior_artifacts = copy.deepcopy(state["artifacts"])
                old_slots = dict(state["slots"])
                old_actor_count = len(state["actors"])
                state = self.submit(state, self.returning(target))
                self.assertEqual(state["returns_used"], 1)
                self.assertEqual(self.activation(state)["phase"], target)
                self.assertEqual(self.activation(state)["visit"], 2)
                self.assertEqual(len(state["actors"]), old_actor_count + 1)
                for i in range(1, 5):
                    slot = f"effective.P{i}"
                    if i < int(target[1]):
                        self.assertEqual(state["slots"][slot], old_slots[slot])
                    else:
                        self.assertNotIn(slot, state["slots"])
                        self.assertNotIn(slot, self.activation(state)["input_bindings"])
                feedback_id = state["feedback"][-1]
                feedback = state["artifacts"][feedback_id]
                partial = state["artifacts"][feedback["content"]["partial_artifact_id"]]
                self.assertEqual(feedback["type"], "cognition.feedback")
                self.assertTrue(feedback["content"]["accepted"])
                self.assertEqual(feedback["content"]["question"], self.returning(target)["question"])
                self.assertEqual(partial["type"], f"cognition.{source}")
                self.assertTrue(partial["partial"])
                self.assertNotIn("judgment", partial["content"])
                self.assertEqual(self.activation(state)["input_bindings"]["feedback.return"], feedback_id)
                traversed = []
                while state["status"] == "active":
                    traversed.append(self.activation(state)["phase"])
                    state = self.submit(state)
                self.assertEqual(traversed, [f"P{i}" for i in range(int(target[1]), 5)])
                self.assertEqual(state["status"], "completed")
                for artifact_id, artifact in prior_artifacts.items():
                    self.assertEqual(state["artifacts"][artifact_id], artifact)
                for slot, artifact_id in old_slots.items():
                    if slot.startswith("effective.") and int(slot[-1]) >= int(target[1]):
                        self.assertNotEqual(state["slots"][slot], artifact_id)
                self.assert_serial(state)

    def test_invalid_return_targets_and_missing_feedback_are_atomic_rejections(self):
        for source in ("P1", "P2", "P3", "P4"):
            state = self.reach(self.start("cognition"), source)
            invalid_targets = ["unknown", source] + [f"P{i}" for i in range(int(source[1]) + 1, 5)]
            for target in invalid_targets:
                state = self.assert_rejected(state, self.returning(target))
            if source != "P1":
                for field in ("reason", "question", "content", "target"):
                    incomplete = self.returning("P1")
                    incomplete.pop(field)
                    state = self.assert_rejected(state, incomplete)
                state = self.assert_rejected(state, {**self.returning("P1"), "content": {}})
            self.assertEqual(state["returns_used"], 0)
            self.assertEqual(state["feedback"], [])

    def test_return_budget_checked_before_allocation_and_never_completes(self):
        for budget in (0, 1, 2):
            with self.subTest(budget=budget):
                state = self.reach(self.start("cognition", max_returns=budget), "P4")
                for _ in range(budget):
                    state = self.submit(state, self.returning("P3"))
                    state = self.submit(state)
                actor_count = len(state["actors"])
                slots = dict(state["slots"])
                state = self.submit(state, self.returning("P1"))
                self.assertEqual(state["status"], "blocked")
                self.assertEqual(state["reason"], "return_budget_exhausted")
                self.assertEqual(state["returns_used"], budget)
                self.assertEqual(len(state["actors"]), actor_count)
                self.assertEqual(state["slots"], slots)
                self.assertNotIn("effective.P4", state["slots"])
                self.assertEqual(len(state["feedback"]), budget + 1)
                self.assertFalse(state["artifacts"][state["feedback"][-1]]["content"]["accepted"])
                self.assert_serial(state)

    def test_runtime_failure_and_cancel_survive_reopen_without_allocating(self):
        for kind in ("development", "cognition"):
            for action in ("runtime_failed", "cancel_run"):
                for running in (False, True):
                    with self.subTest(kind=kind, action=action, running=running):
                        state = self.submit(self.start(kind))
                        activation_id = state["current_activation"]
                        if running:
                            state = controller.begin_activation(self.store, activation_id, state["version"])
                        artifacts = copy.deepcopy(state["artifacts"])
                        actor_count = len(state["actors"])
                        if action == "cancel_run":
                            final = controller.cancel_run(self.store, "Operator stopped")
                            self.assertEqual(controller.cancel_run(self.store, "Repeated stop"), final)
                            self.assertEqual(final["status"], "cancelled")
                        else:
                            final = controller.runtime_failed(self.store, activation_id, state["version"], "Adapter failed")
                            self.assertEqual(final["status"], "failed")
                        self.assertEqual(controller.inspect_run(self.store), final)
                        self.assertEqual(final["activations"][activation_id]["status"], "failed")
                        self.assertEqual(final["artifacts"], artifacts)
                        self.assertEqual(len(final["actors"]), actor_count)
                        self.assert_serial(final)
                        with self.assertRaises(controller.ConflictError):
                            controller.begin_activation(self.store, activation_id, final["version"])
                        with self.assertRaises(controller.ConflictError):
                            controller.submit_result(self.store, activation_id, final["version"], self.result(state), "late-session", "late-command")
                        self.assertEqual(controller.inspect_run(self.store), final)

    def test_reopen_running_run_and_preserve_pattern_snapshot(self):
        pattern = json.loads((controller.PATTERN_DIR / "cognition.json").read_text())
        self.store = self.root / "snapshot.sqlite"
        state = controller.start_run(self.store, pattern, "Purpose", self.root)
        original = copy.deepcopy(pattern)
        pattern["phases"][0]["role"] = "Caller changed it"
        state = controller.begin_activation(self.store, state["current_activation"], state["version"])
        reopened = controller.inspect_run(self.store)
        self.assertEqual(reopened, state)
        self.assertEqual(reopened["pattern"], original)
        self.assertEqual(self.activation(reopened)["status"], "running")
        self.assertEqual(self.activation(self.submit(reopened))["phase"], "P2")

    def test_one_run_per_store_and_invalid_budgets(self):
        state = self.start()
        with self.assertRaises(controller.ConflictError):
            controller.start_run(self.store, controller.PATTERN_DIR / "cognition.json", "Other", self.root)
        self.assertEqual(controller.inspect_run(self.store), state)
        for budget in (-1, True, 1.5):
            with self.subTest(budget=budget), self.assertRaises(controller.ControllerError):
                controller.start_run(self.root / "invalid.sqlite", state["pattern"], "Purpose", self.root, max_returns=budget)
        self.assertFalse((self.root / "invalid.sqlite").exists())


if __name__ == "__main__":
    unittest.main()
