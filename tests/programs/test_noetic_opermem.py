"""Exercise the actual Rust boundary when an operation-host binary is supplied."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
import io
from copy import deepcopy

from scripts import noetic_opermem as bridge
from scripts import noetic_run


class OpermemBoundaryTest(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("OPERMEM_OPERATION_HOST"),
                         "set OPERMEM_OPERATION_HOST to exercise the Rust operation host")
    def test_question_to_unverified_insight_survives_fresh_host(self):
        binary = Path(os.environ["OPERMEM_OPERATION_HOST"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = root / "store"
            transcripts = root / "transcripts"
            before, _ = bridge.retrieve(binary, store, transcripts,
                                        bridge.purpose_for("question", None))
            question, _ = bridge.submit(
                binary, store, transcripts, "question", None,
                {"question_kind": "how", "text": "How can a missing report be recovered?"},
                "boundary-question", before)
            question_id = next(item["id"] for item in question["payload"]["outputs"]
                               if item["role"] == "question")
            insight_context, _ = bridge.retrieve(binary, store, transcripts,
                                                 bridge.purpose_for("insight", question_id))
            question_residue = bridge.parent_from_context(insight_context, "insight", question_id)
            self.assertEqual(question_residue["standing"], "question")
            self.assertTrue(question_residue["source"]["history_complete"])
            pending = root / "pending.json"
            insight, _ = bridge.submit(
                binary, store, transcripts, "insight", question_id,
                {"text": "Trace: index the controller database rather than a missing report."},
                "boundary-insight", insight_context, pending)
            insight_id = next(item["id"] for item in insight["payload"]["outputs"]
                              if item["role"] == "unverified insight trace")
            next_context, _ = bridge.retrieve(binary, store, transcripts,
                                              bridge.purpose_for("formulation", insight_id))
            trace = bridge.parent_from_context(next_context, "formulation", insight_id)
            self.assertEqual(trace["standing"], "unverified")
            self.assertEqual(trace["pinned_cut_binding"], next_context["pinned_canonical_cut"])
            saved = json.loads(pending.read_text(encoding="utf-8"))
            transcript = bridge.fresh_transcript(transcripts)
            with bridge.OperationHost(binary, store, transcript) as host:
                host.context(bridge.purpose_for("insight", question_id))
                replay = host.exchange(saved["kind"], saved["payload"])
            self.assertEqual(replay["class"], "idempotency-replay")
            self.assertEqual(replay["payload"]["receipt_id"], insight["payload"]["receipt_id"])
            with self.assertRaisesRegex(ValueError, "context changed"):
                bridge.submit(binary, store, transcripts, "insight", question_id,
                              {"text": "A second trace from stale context"},
                              "boundary-stale", insight_context)

    @unittest.skipUnless(os.environ.get("OPERMEM_OPERATION_HOST"),
                         "set OPERMEM_OPERATION_HOST to exercise the Rust operation host")
    def test_resume_reconciles_committed_command_with_missing_receipt(self):
        binary = Path(os.environ["OPERMEM_OPERATION_HOST"]).resolve()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = root / "store"
            transcripts = root / "transcripts"
            question, _ = bridge.submit(
                binary, store, transcripts, "question", None,
                {"question_kind": "how", "text": "How can a trace survive interruption?"},
                "resume-question")
            question_id = next(item["id"] for item in question["payload"]["outputs"]
                               if item["role"] == "question")
            context, _ = bridge.retrieve(binary, store, transcripts,
                                         bridge.purpose_for("insight", question_id))
            run_dir = noetic_run.create_run(
                {"goal": "examine interrupted receipt", "work": ["true"], "verify": ["true"]},
                root, root / "runs")
            noetic_run.record(run_dir, "run.finished", {"state": "awaiting_review"})
            evidence = run_dir / "review.md"
            evidence.write_text("ACCEPT\nActual boundary test.\n", encoding="utf-8")
            noetic_run.review_run(run_dir, "accept", "test:reviewer", evidence)
            contribution = {"text": "Trace: the saved command can be replayed after a crash."}
            (run_dir / "work.md").write_text(
                bridge.MARKER + json.dumps(contribution) + "\n", encoding="utf-8")
            (run_dir / "opermem-link.json").write_text(json.dumps({
                "host": str(binary), "store": str(store.resolve()), "operation": "insight",
                "parent_id": question_id, "context": context,
            }), encoding="utf-8")
            accepted, _ = bridge.submit(
                binary, store, transcripts, "insight", question_id, contribution,
                f"noetic-{run_dir.name}-insight", context,
                pending_path=run_dir / "opermem-pending.json")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(bridge.resume_run(run_dir, binary, store, transcripts), 0)
            recovered = json.loads((run_dir / "opermem-receipt.json").read_text())
            self.assertEqual(recovered["response"]["class"], "idempotency-replay")
            self.assertEqual(recovered["response"]["payload"]["receipt_id"],
                             accepted["payload"]["receipt_id"])


class OpermemContributionTests(unittest.TestCase):
    def test_duplicate_json_fields_are_rejected_and_ordinary_inputs_remain_exact(self):
        for operation, payload in (
            ("conditional-structure", '{"conditions":["A: first proposed condition"],"conditions":["B: second proposed condition"]}'),
            ("reflection", '{"text":"First question?","text":"Second question?"}'),
        ):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, "duplicate"):
                bridge.contribution_from_report(bridge.MARKER + payload, operation)
        for operation in ("question", "insight", "formulation", "reflection"):
            value = {"text": "Exact text: café and retained identifiers."}
            if operation == "question":
                value["question_kind"] = "why"
            self.assertEqual(bridge.contribution_from_report(bridge.MARKER + json.dumps(value), operation), value)

    def test_conditional_contribution_is_exact_and_canonical(self):
        value = {"conditions": ["A: inspect the retained cut", "B: compare exact receipts"]}
        self.assertEqual(bridge.contribution_from_report(
            bridge.MARKER + json.dumps(value), "conditional-structure"), value)
        invalid = [None, {}, {"text": "a claim"}, {"conditions": [], "text": "extra"},
                   {"conditions": []}, {"conditions": "condition"}, {"conditions": [None]},
                   {"conditions": [True]}, {"conditions": [""]}, {"conditions": [" "]},
                   {"conditions": [" padded"]}, {"conditions": ["padded "]},
                   {"conditions": ["same", "same"]}, {"conditions": ["z", "a"]}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                bridge.contribution_from_report(bridge.MARKER + json.dumps(value),
                                                "conditional-structure")
        with self.assertRaises(ValueError):
            bridge.contribution_from_report(bridge.MARKER + '{"conditions":["a"]}\n'
                                            + bridge.MARKER + '{"conditions":["b"]}',
                                            "conditional-structure")

    def test_new_anchor_arguments_reject_invalid_or_inapplicable_ids(self):
        for operation, parent, formulation in [
            ("reflection", None, None), ("reflection", True, None), ("reflection", 0, None),
            ("reflection", 1, 2), ("conditional-structure", 1, None),
            ("conditional-structure", 1, True), ("conditional-structure", 1, 0),
            ("conditional-structure", 1, "2"), ("insight", 1, 2),
        ]:
            with self.subTest(operation=operation, parent=parent, formulation=formulation):
                with self.assertRaises(ValueError):
                    bridge.purpose_for(operation, parent, formulation)


@unittest.skipUnless(os.environ.get("OPERMEM_OPERATION_HOST"), "requires actual Rust host")
class OpermemReflectionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.binary = Path(os.environ["OPERMEM_OPERATION_HOST"]).resolve()
        self.store = self.root / "store"
        self.transcripts = self.root / "transcripts"
        parent = None
        for operation, contribution, role in [
            ("question", {"question_kind": "how", "text": "How do exact receipts retain their standing?"}, "question"),
            ("insight", {"text": "Trace: retained IDs may identify a committed contribution."}, "unverified insight trace"),
            ("formulation", {"text": "Hypothesis: replay returns the original receipt and typed residue."}, "versioned formulation/hypothesis"),
        ]:
            response, _ = bridge.submit(self.binary, self.store, self.transcripts, operation,
                                       parent, contribution, "setup-" + operation)
            parent = self.output(response, role)
            if operation == "insight":
                self.insight = parent
        self.formulation = parent

    @staticmethod
    def output(response, role):
        return next(item["id"] for item in response["payload"]["outputs"] if item["role"] == role)

    def reflection(self):
        response, _ = bridge.submit(self.binary, self.store, self.transcripts, "reflection",
                                   self.formulation, {"text": "Is this replay hypothesis correct?"},
                                   "setup-reflection")
        return self.output(response, "reflection question")

    def context(self, operation, parent, formulation=None):
        return bridge.retrieve(self.binary, self.store, self.transcripts,
                               bridge.purpose_for(operation, parent, formulation))[0]

    def test_reflection_and_warrant_preserve_whole_native_standing(self):
        reflection_context = self.context("reflection", self.formulation)
        hypothesis = bridge.parent_from_context(reflection_context, "reflection", self.formulation)
        self.assertEqual(hypothesis["standing"], "hypothesis")
        reflection, _ = bridge.submit(
            self.binary, self.store, self.transcripts, "reflection", self.formulation,
            {"text": "Is replay identical after restarting the host?"}, "native-reflection",
            reflection_context)
        reflection_id = self.output(reflection, "reflection question")
        context = self.context("conditional-structure", reflection_id, self.formulation)
        parent = bridge.parent_from_context(context, "conditional-structure", reflection_id)
        self.assertEqual(parent["standing"], "reflection-question")
        for residue in (parent, bridge.parent_from_context(context, "reflection", self.formulation)):
            self.assertEqual(residue["pinned_cut_binding"], context["pinned_canonical_cut"])
            self.assertTrue(residue["source"]["history_complete"])
        conditions = ["A: the recovered receipt ID is identical", "B: the residue IDs remain identical"]
        pending = self.root / "conditional-pending.json"
        warrant, _ = bridge.submit(
            self.binary, self.store, self.transcripts, "conditional-structure", reflection_id,
            {"conditions": conditions}, "native-warrant", context, pending,
            formulation_id=self.formulation)
        saved = json.loads(pending.read_text())
        self.assertEqual(saved["payload"]["body"], {"formulation_id": self.formulation,
                         "reflection_id": reflection_id, "conditions": conditions})
        self.assertEqual(saved["payload"]["expected_object_versions"], [
            {"id": reflection_id, "kind": "reflection-question", "version": parent["object_version"]},
            {"id": self.formulation, "kind": "formulation-hypothesis", "version": hypothesis["object_version"]},
        ])
        warrant_id = self.output(warrant, "warrant")
        condition_ids = [item["id"] for item in warrant["payload"]["outputs"]
                         if item["role"] == "addressable warrant conditions"]
        self.assertEqual(len(set(condition_ids)), len(conditions))
        for condition_id in condition_ids:
            checking, _ = bridge.retrieve(self.binary, self.store, self.transcripts, {
                "operation": "checking", "warrant_id": warrant_id, "condition_id": condition_id})
            residues = {item["residue_id"]["id"]: item for item in checking["supplied_whole_residues"]}
            self.assertEqual(residues[warrant_id]["standing"], "conditional-warrant")
            self.assertEqual(residues[condition_id]["standing"], "unchecked")
            self.assertFalse(any(item["standing"] == "judgment" for item in residues.values()))

    def test_native_rejects_invalid_anchors_schema_and_versions_without_promotion(self):
        reflection_id = self.reflection()
        another, _ = bridge.submit(self.binary, self.store, self.transcripts, "question", None,
                                  {"question_kind": "why", "text": "Why distinguish unrelated anchors?"}, "other-question")
        question_id = self.output(another, "question")
        context = self.context("conditional-structure", reflection_id, self.formulation)
        valid = {"body": {"formulation_id": self.formulation, "reflection_id": reflection_id,
                          "conditions": ["A: inspect the retained IDs"]}, "command_version": 1,
                 "expected_object_versions": [
                     {"id": reflection_id, "kind": "reflection-question", "version": 1},
                     {"id": self.formulation, "kind": "formulation-hypothesis", "version": 1}],
                 "idempotency_key": "invalid-native"}
        cases = []
        for conditions in ([], ["x", "x"], ["z", "a"], [None], [True], [" padded"]):
            payload = deepcopy(valid)
            payload["body"]["conditions"] = conditions
            cases.append(("conditions", "define-conditional-structure", payload))
        for label, change in (
            ("missing-version", lambda p: p["expected_object_versions"].pop()),
            ("wrong-version", lambda p: p["expected_object_versions"][0].update(version=2)),
            ("unsorted-versions", lambda p: p["expected_object_versions"].reverse()),
            ("extra-schema", lambda p: p["body"].update(text="extra")),
            ("wrong-kind-anchor", lambda p: p["body"].update(reflection_id=question_id)),
            ("unknown-anchor", lambda p: p["body"].update(reflection_id=1)),
        ):
            payload = deepcopy(valid)
            change(payload)
            cases.append((label, "define-conditional-structure", payload))
        for formulation in (1, question_id, True):
            cases.append(("reflection-anchor", "question-correctness", {
                "body": {"formulation_id": formulation, "text": "Is this anchor a formulation?"},
                "command_version": 1,
                "expected_object_versions": [{"id": formulation, "kind": "formulation-hypothesis", "version": 1}],
                "idempotency_key": "invalid-reflection"}))
        second, _ = bridge.submit(self.binary, self.store, self.transcripts, "formulation", self.insight,
                                 {"text": "An unrelated hypothesis from the same insight."}, "other-formulation")
        second_id = self.output(second, "versioned formulation/hypothesis")
        mismatch = deepcopy(valid)
        mismatch["body"]["formulation_id"] = second_id
        mismatch["expected_object_versions"][1]["id"] = second_id
        cases.append(("wrong-ancestry", "define-conditional-structure", mismatch))
        before = self.context("conditional-structure", reflection_id, self.formulation)
        for index, (label, kind, payload) in enumerate(cases):
            payload["idempotency_key"] += str(index)
            with self.subTest(case=label, index=index):
                transcript = bridge.fresh_transcript(self.transcripts)
                with self.assertRaises(RuntimeError), bridge.OperationHost(self.binary, self.store, transcript) as host:
                    host.context({"operation": "conditional-structure", "formulation_id": self.formulation,
                                  "reflection_id": reflection_id})
                    host.exchange(kind, payload)
                after = self.context("conditional-structure", reflection_id, self.formulation)
                self.assertEqual(after, before)

    def test_stale_context_blocks_both_operations_before_pending_write(self):
        reflection_id = self.reflection()
        for operation, parent, formulation, contribution in (
            ("reflection", self.formulation, None, {"text": "Is this still current?"}),
            ("conditional-structure", reflection_id, self.formulation, {"conditions": ["A: context is current"]}),
        ):
            with self.subTest(operation=operation):
                context = self.context(operation, parent, formulation)
                bridge.submit(self.binary, self.store, self.transcripts, "question", None,
                              {"question_kind": "what", "text": "What changed the canonical cut?"}, "drift-" + operation)
                pending = self.root / (operation + "-pending.json")
                with self.assertRaisesRegex(ValueError, "context changed"):
                    bridge.submit(self.binary, self.store, self.transcripts, operation, parent,
                                  contribution, "stale-" + operation, context, pending,
                                  formulation_id=formulation)
                self.assertFalse(pending.exists())

    def test_exact_resume_recovers_each_new_operation_and_rejects_changed_payload(self):
        reflection_id = self.reflection()
        for operation, parent, formulation, contribution in (
            ("reflection", self.formulation, None, {"text": "Does recovery preserve this question?"}),
            ("conditional-structure", reflection_id, self.formulation, {"conditions": ["A: replay retains the same receipt"]}),
        ):
            with self.subTest(operation=operation):
                context = self.context(operation, parent, formulation)
                run = noetic_run.create_run({"goal": "Recover the original " + operation,
                                            "work": ["true"], "verify": ["true"]}, self.root, self.root / "runs")
                noetic_run.record(run, "run.finished", {"state": "awaiting_review"})
                evidence = run / "review.md"
                evidence.write_text("ACCEPT\nFixture inspected the retained command.\n")
                noetic_run.review_run(run, "accept", "fixture:reviewer", evidence)
                report = run / "work.md"
                report.write_text(bridge.MARKER + json.dumps(contribution) + "\n")
                (run / "opermem-link.json").write_text(json.dumps({
                    "host": str(self.binary), "store": str(self.store.resolve()), "operation": operation,
                    "parent_id": parent, "formulation_id": formulation, "context": context}))
                pending = run / "opermem-pending.json"
                accepted, _ = bridge.submit(self.binary, self.store, self.transcripts, operation,
                                           parent, contribution, "noetic-" + run.name + "-" + operation,
                                           context, pending, formulation_id=formulation)
                before = self.context(operation, parent, formulation)
                saved = pending.read_text()
                changed = json.loads(saved)
                changed["payload"]["expected_object_versions"][0]["version"] += 1
                pending.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, "differs"):
                    bridge.resume_run(run, self.binary, self.store, self.transcripts)
                pending.write_text(saved)
                original_report = report.read_text()
                altered = {"conditions": ["B: changed condition"]} if formulation else {"text": "Changed question"}
                report.write_text(bridge.MARKER + json.dumps(altered))
                with self.assertRaisesRegex(ValueError, "differs"):
                    bridge.resume_run(run, self.binary, self.store, self.transcripts)
                report.write_text(original_report)
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.transcripts), 0)
                recovered = json.loads((run / "opermem-receipt.json").read_text())["response"]
                self.assertEqual(recovered["class"], "idempotency-replay")
                self.assertEqual(recovered["payload"]["receipt_id"], accepted["payload"]["receipt_id"])
                self.assertEqual(recovered["payload"]["exact_result"], accepted["payload"]["exact_result"])
                self.assertEqual(self.context(operation, parent, formulation), before)
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.transcripts), 0)
                self.assertEqual(self.context(operation, parent, formulation), before)



class JudgmentContributionTests(unittest.TestCase):
    def test_exact_contribution_and_complete_anchor_contract(self):
        from tests.programs.opermem_judgment_fixture import proposed_judgment
        value = proposed_judgment()
        self.assertEqual(bridge.contribution_from_report(bridge.MARKER + json.dumps(value), "judgment"), value)
        self.assertEqual(bridge.contribution_from_report(bridge.MARKER + json.dumps(proposed_judgment("perchance")), "judgment"), proposed_judgment("perchance"))
        invalid = [None, {}, {**value, "text": "extra"}, {**value, "rationale": " "},
                   {**value, "defeat_conditions": []}, {**value, "defeat_conditions": ["z", "a"]},
                   {**value, "defeat_conditions": ["a", "a"]}, {**value, "defeat_conditions": [" padded"]},
                   {**value, "polarity": {"kind": "yea", "confidence_basis_points": 1}},
                   {**value, "polarity": {"kind": "perchance", "confidence_basis_points": True}},
                   {**value, "polarity": {"kind": "perchance", "confidence_basis_points": 10001}},
                   {**value, "polarity": {"kind": "perchance", "confidence_basis_points": 1.5}}]
        for proposal in invalid:
            with self.subTest(proposal=proposal), self.assertRaises(ValueError):
                bridge.contribution_from_report(bridge.MARKER + json.dumps(proposal), "judgment")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            bridge.contribution_from_report(bridge.MARKER + '{"polarity":{"kind":"yea","kind":"nay"},"defeat_conditions":["x"],"rationale":"x"}', "judgment")
        for values in (None, [], [0], [True], [2**64], [2, 1], [1, 1], [1.0]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                bridge.purpose_for("judgment", None, warrant_id=10, condition_ids=values)
            with self.subTest(values=values), self.assertRaises(ValueError):
                bridge.purpose_for("practical-question", None, judgment_ids=values)
        for operation, anchors in [("insight", {"condition_ids": [1]}),
                                   ("judgment", {"warrant_id": True, "condition_ids": [1]}),
                                   ("judgment", {"warrant_id": 10, "condition_ids": [1], "judgment_ids": [2]}),
                                   ("practical-question", {"judgment_ids": [1], "warrant_id": 10})]:
            with self.assertRaises(ValueError):
                bridge.purpose_for(operation, None, **anchors)
        with self.assertRaises(ValueError):
            bridge.purpose_for("practical-question", 1, judgment_ids=[1])
        self.assertEqual(bridge.purpose_for("judgment", None, warrant_id=2**64-1, condition_ids=[2**53+1, 2**64-2]),
                         {"operation": "judgment", "warrant_id": 2**64-1, "condition_ids": [2**53+1, 2**64-2]})


@unittest.skipUnless(os.environ.get("OPERMEM_OPERATION_HOST"), "requires actual Rust host")
class JudgmentNativeBoundaryTests(unittest.TestCase):
    def setUp(self):
        from tests.programs.opermem_judgment_fixture import checked_warrant
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.binary = Path(os.environ["OPERMEM_OPERATION_HOST"]).resolve()
        self.store, self.transcripts = self.root / "store", self.root / "transcripts"
        self.warrant, self.conditions = checked_warrant(self.binary, self.store, self.transcripts, self.root)
        self.anchors = {"warrant_id": self.warrant, "condition_ids": self.conditions}
        self.purpose = bridge.purpose_for("judgment", None, **self.anchors)
        self.context, _ = bridge.retrieve(self.binary, self.store, self.transcripts, self.purpose)

    def test_five_condition_snapshot_and_many_judgment_basis_after_restart(self):
        from tests.programs.opermem_judgment_fixture import proposed_judgment
        from scripts import noetic_opermem_judgment as composition
        kind, command = bridge.contextual_command(self.context, "judgment", None, proposed_judgment(), "five", **self.anchors)
        self.assertEqual(len(command["body"]["snapshot"]), 5)
        self.assertEqual([x["condition_id"] for x in command["body"]["snapshot"]], self.conditions)
        self.assertEqual([x["kind"] for x in command["expected_object_versions"]],
                         ["evidence-record"] * 5 + ["warrant"] + ["warrant-condition"] * 5)
        self.assertEqual([x["version"] for x in command["expected_object_versions"] if x["kind"] == "warrant-condition"], [2] * 5)
        judgments = []
        for key in ("judgment-first", "judgment-second"):
            response, _ = bridge.submit(self.binary, self.store, self.transcripts, "judgment", None,
                                        proposed_judgment(), key, **self.anchors)
            judgments.append(next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "judgment"))
        basis = sorted(judgments)
        context, _ = bridge.retrieve(self.binary, self.store, self.transcripts,
                                    bridge.purpose_for("practical-question", None, judgment_ids=basis))
        selected = composition.practical_material(context, basis)
        self.assertEqual(len(selected), 2)
        for item in selected:
            self.assertTrue(item["source"]["history_complete"])
            self.assertEqual(item["retrieval_voice"]["warrant_id"], self.warrant)
            self.assertEqual(len(item["retrieval_voice"]["evidence_snapshot"]), 5)
            native_snapshot = item["content"]["command"]["payload"]["evidence_snapshot"]
            self.assertEqual(native_snapshot, [
                {"condition": {"kind": "warrant-condition", "id": claim["condition_id"]},
                 "evidence": {"kind": "evidence-record", "id": claim["evidence_id"]}}
                for claim in command["body"]["snapshot"]])
        practical_kind, practical_command = bridge.contextual_command(context, "practical-question", None,
            {"text": "Given both judgments, what should be investigated next?"}, "practical-refs", judgment_ids=basis)
        mutations = [lambda c: c["expected_object_versions"].pop(),
                     lambda c: c["expected_object_versions"][0].update(version=999),
                     lambda c: c["expected_object_versions"].insert(0, {"kind": "warrant", "id": self.warrant, "version": 1}),
                     lambda c: c["body"]["judgment_ids"].pop()]
        for index, mutation in enumerate(mutations):
            refused = deepcopy(practical_command)
            mutation(refused)
            refused["idempotency_key"] = "practical-refused-" + str(index)
            with self.subTest(index=index), self.assertRaises(RuntimeError):
                with bridge.OperationHost(self.binary, self.store, bridge.fresh_transcript(self.transcripts)) as host:
                    host.context(bridge.purpose_for("practical-question", None, judgment_ids=basis))
                    host.exchange(practical_kind, refused)
        response, _ = bridge.submit(self.binary, self.store, self.transcripts, "practical-question", None,
            {"text": "Given both bounded judgments, what should be investigated next?"}, "practical", context,
            judgment_ids=basis)
        question = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "practical-question")
        restarted, _ = bridge.retrieve(self.binary, self.store, self.transcripts,
                                      {"operation": "practical-inquiry", "practical_question_id": question})
        whole = next(x for x in restarted["supplied_whole_residues"] if x["residue_id"] == {"kind": "practical-question", "id": question})
        self.assertEqual(whole["retrieval_voice"]["judgment_ids"], basis)
        self.assertEqual(sorted(composition.related(whole, "grounds-practical-question", "to", "judgment")), basis)
        self.assertEqual(len([x for x in restarted["supplied_whole_residues"] if x["kind"] == "judgment"]), 2)

    def test_native_snapshot_polarity_version_and_reference_refusals(self):
        from tests.programs.opermem_judgment_fixture import proposed_judgment
        kind, command = bridge.contextual_command(self.context, "judgment", None, proposed_judgment(), "base", **self.anchors)
        mutations = [lambda c: c["body"]["snapshot"].pop(),
                     lambda c: c["body"]["snapshot"][0].update(evidence_id=c["body"]["snapshot"][1]["evidence_id"]),
                     lambda c: c["body"].update(polarity={"kind": "nay"}),
                     lambda c: c["expected_object_versions"][0].update(version=999),
                     lambda c: c["expected_object_versions"].pop(),
                     lambda c: c["expected_object_versions"].insert(0, {"kind": "experience", "id": 1, "version": 1})]
        for index, mutation in enumerate(mutations):
            rejected = deepcopy(command)
            mutation(rejected)
            rejected["idempotency_key"] = "refused-" + str(index)
            with self.subTest(index=index), self.assertRaises(RuntimeError):
                with bridge.OperationHost(self.binary, self.store, bridge.fresh_transcript(self.transcripts)) as host:
                    host.context(self.purpose)
                    host.exchange(kind, rejected)
        after, _ = bridge.retrieve(self.binary, self.store, self.transcripts, self.purpose)
        self.assertEqual(after, self.context)
        with self.assertRaisesRegex(ValueError, "entire condition set"):
            bridge.submit(self.binary, self.store, self.transcripts, "judgment", None, proposed_judgment(),
                          "incomplete", warrant_id=self.warrant, condition_ids=self.conditions[:-1])
        broken = deepcopy(self.context)
        next(x for x in broken["supplied_whole_residues"] if x["kind"] == "evidence-record")["content"]["id"]["id"] = 7
        with self.assertRaisesRegex(ValueError, "content hash"):
            bridge.contextual_command(broken, "judgment", None, proposed_judgment(), "hash", **self.anchors)

    def test_native_legal_nay_and_perchance_remain_actor_authored(self):
        from tests.programs.opermem_judgment_fixture import checked_warrant, proposed_judgment
        for polarity, assertion in (("nay", "assert 2 + 2 == 5"),
                                    ("perchance", "self.skipTest('bounded evidence is indeterminate')")):
            directory = self.root / polarity
            directory.mkdir()
            store = directory / "store"
            warrant, conditions = checked_warrant(self.binary, store, self.transcripts, directory,
                count=2, key=polarity, assertion=assertion)
            proposal = proposed_judgment(polarity)
            response, _ = bridge.submit(self.binary, store, self.transcripts, "judgment", None,
                proposal, "legal-" + polarity, warrant_id=warrant, condition_ids=conditions)
            context, _ = bridge.retrieve(self.binary, store, self.transcripts,
                bridge.purpose_for("judgment", None, warrant_id=warrant, condition_ids=conditions))
            identity = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "judgment")
            whole = next(x for x in context["supplied_whole_residues"] if x["residue_id"] == {"kind": "judgment", "id": identity})
            self.assertEqual(whole["retrieval_voice"]["polarity"]["kind"], polarity)
            self.assertEqual(whole["retrieval_voice"]["defeat_conditions"], proposal["defeat_conditions"])
            if polarity == "perchance":
                self.assertEqual(whole["retrieval_voice"]["polarity"]["confidence_basis_points"], 5000)



class PracticalContributionTests(unittest.TestCase):
    def test_actor_content_and_explicit_complete_anchor_validation(self):
        from tests.programs.opermem_practical_fixture import deliberation
        value = deliberation()
        self.assertEqual(bridge.contribution_from_report(bridge.MARKER + json.dumps(value), "deliberation"), value)
        for operation in ("practical-inquiry", "practical-insight"):
            self.assertEqual(bridge.contribution_from_report(bridge.MARKER + '{"text":"Actual bounded course reasoning."}', operation),
                             {"text": "Actual bounded course reasoning."})
            for wrong in ({"text": " "}, {"text": " padded"}, {"text": True}, {"text": "course", "option_id": 1}):
                with self.subTest(operation=operation, wrong=wrong), self.assertRaises(ValueError):
                    bridge.contribution_from_report(bridge.MARKER + json.dumps(wrong), operation)
        for field in ("criteria", "trade_offs", "objections_and_responses"):
            for invalid in ([], ["same", "same"], ["z", "a"], [" padded"], [True], "not a set"):
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                    bridge.contribution_from_report(bridge.MARKER + json.dumps({**value, field: invalid}), "deliberation")
        for wrong in ({**value, "value_scale": " "}, {**value, "options": []}):
            with self.assertRaises(ValueError):
                bridge.contribution_from_report(bridge.MARKER + json.dumps(wrong), "deliberation")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            bridge.contribution_from_report(bridge.MARKER + '{"text":"first","text":"second"}', "practical-inquiry")
        for operation, anchors in [
            ("practical-inquiry", {}), ("practical-inquiry", {"practical_question_id": True}),
            ("practical-insight", {"practical_question_id": 1}),
            ("practical-insight", {"practical_question_id": 1, "option_id": 2**64}),
            ("deliberation", {"practical_question_id": 1, "option_ids": [1]}),
            ("deliberation", {"practical_question_id": 1, "option_ids": [2, 1]}),
            ("deliberation", {"practical_question_id": 1, "option_ids": [1, True]}),
            ("practical-inquiry", {"practical_question_id": 1, "option_id": 2}),
            ("practical-insight", {"practical_question_id": 1, "option_id": 2, "option_ids": [1, 2]}),
            ("judgment", {"warrant_id": 1, "condition_ids": [1], "practical_question_id": 2}),
        ]:
            with self.subTest(operation=operation, anchors=anchors), self.assertRaises(ValueError):
                bridge.purpose_for(operation, None, **anchors)
        with self.assertRaises(ValueError):
            bridge.purpose_for("practical-inquiry", 1, practical_question_id=2)
        self.assertEqual(bridge.purpose_for("practical-insight", None, practical_question_id=2**64-1, option_id=2**53+1),
                         {"operation": "practical-insight", "practical_question_id": 2**64-1, "option_id": 2**53+1})


@unittest.skipUnless(os.environ.get("OPERMEM_OPERATION_HOST"), "requires actual Rust host")
class PracticalNativeBoundaryTests(unittest.TestCase):
    def setUp(self):
        from tests.programs.opermem_practical_fixture import practical_question, courses
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.binary = Path(os.environ["OPERMEM_OPERATION_HOST"]).resolve()
        self.store, self.transcripts = self.root / "store", self.root / "transcripts"
        self.question, self.judgments = practical_question(self.binary, self.store, self.transcripts, self.root / "checking")
        self.options, self.insights = courses(self.binary, self.store, self.transcripts, self.question)
        self.anchors = {"practical_question_id": self.question, "option_ids": self.options}
        self.purpose = bridge.purpose_for("deliberation", None, **self.anchors)
        self.context, _ = bridge.retrieve(self.binary, self.store, self.transcripts, self.purpose)

    def test_three_whole_alternatives_with_many_judgment_ancestry_after_restart(self):
        from scripts import noetic_opermem_practical as native
        from tests.programs.opermem_practical_fixture import deliberation
        question = native.residue(self.context, "practical-question", self.question)
        primary, supplemental = self.context["native_context_packets"]
        self.assertEqual(primary["operation"], "deliberation")
        self.assertEqual(supplemental["operation"], "practical-inquiry")
        self.assertNotIn("judgment", [item["kind"] for item in primary["supplied_whole_residues"]])
        self.assertNotIn("practical-question", [item["kind"] for item in primary["supplied_whole_residues"]])
        self.assertEqual(primary["pinned_canonical_cut"], supplemental["pinned_canonical_cut"])
        shifted = deepcopy(supplemental)
        shifted["pinned_canonical_cut"]["authority_generation"] += 1
        with self.assertRaisesRegex(ValueError, "exact cut"):
            native.compose_context("deliberation", [primary, shifted])
        self.assertEqual(question["retrieval_voice"]["judgment_ids"], self.judgments)
        self.assertEqual(len(self.options), 3)
        self.assertEqual(len(self.insights), 3)
        for identity in self.judgments:
            judgment = native.residue(self.context, "judgment", identity)
            self.assertTrue(judgment["source"]["history_complete"])
            self.assertEqual(len(judgment["retrieval_voice"]["evidence_snapshot"]), 2)
        for identity in self.insights:
            self.assertEqual(native.residue(self.context, "unverified-practical-insight-trace", identity)["standing"], "unverified")
        kind, command = bridge.contextual_command(self.context, "deliberation", None, deliberation(), "evaluate", **self.anchors)
        self.assertEqual([r["kind"] for r in command["expected_object_versions"]],
                         ["option"] * len(self.options) + ["practical-question"] + ["unverified-practical-insight-trace"] * len(self.insights))
        self.assertEqual(next(r["version"] for r in command["expected_object_versions"] if r["kind"] == "practical-question"), question["object_version"])
        self.assertEqual([p["option_id"] for p in command["body"]["options"]], self.options)
        response, _ = bridge.submit(self.binary, self.store, self.transcripts, "deliberation", None,
                                   deliberation(), "actual-evaluation", self.context, **self.anchors)
        evaluation = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "evaluation")
        restarted, _ = bridge.retrieve(self.binary, self.store, self.transcripts,
            {"operation": "decision", "evaluation_id": evaluation, "judgment_basis_ids": self.judgments})
        whole = bridge.noetic_opermem_judgment.residue(restarted, "evaluation", evaluation)
        self.assertEqual(whole["retrieval_voice"]["options"], command["body"]["options"])
        for field, value in deliberation().items():
            self.assertEqual(whole["retrieval_voice"][field], value)
        self.assertEqual(bridge.noetic_opermem_judgment.residue(restarted, "practical-question", self.question)["retrieval_voice"]["judgment_ids"], self.judgments)
        self.assertEqual(len([r for r in restarted["supplied_whole_residues"] if r["kind"] == "judgment"]), len(self.judgments))

    def test_native_foreign_stale_missing_extra_and_partial_option_refusals(self):
        from tests.programs.opermem_practical_fixture import deliberation
        kind, command = bridge.contextual_command(self.context, "deliberation", None, deliberation(), "reject-base", **self.anchors)
        mutations = [lambda c: c["body"]["options"].pop(),
                     lambda c: c["body"]["options"][0].update(insight_id=c["body"]["options"][1]["insight_id"]),
                     lambda c: c["expected_object_versions"].pop(),
                     lambda c: c["expected_object_versions"][0].update(version=999),
                     lambda c: c["expected_object_versions"].insert(0, {"kind": "judgment", "id": self.judgments[0], "version": 1})]
        for index, mutation in enumerate(mutations):
            changed = deepcopy(command)
            mutation(changed)
            changed["idempotency_key"] = "refusal-" + str(index)
            with self.subTest(index=index), self.assertRaises(RuntimeError):
                with bridge.OperationHost(self.binary, self.store, bridge.fresh_transcript(self.transcripts)) as host:
                    host.context(self.purpose)
                    host.exchange(kind, changed)
        after, _ = bridge.retrieve(self.binary, self.store, self.transcripts, self.purpose)
        self.assertEqual(after, self.context)
        with self.assertRaisesRegex(ValueError, "entire current"):
            bridge.submit(self.binary, self.store, self.transcripts, "deliberation", None, deliberation(),
                          "partial", practical_question_id=self.question, option_ids=self.options[:-1])
        bridge.submit(self.binary, self.store, self.transcripts, "practical-insight", None,
            {"text": "A second current trace creates an explicit native ambiguity."}, "duplicate-trace",
            practical_question_id=self.question, option_id=self.options[0])
        with self.assertRaisesRegex(ValueError, "unique current"):
            bridge.submit(self.binary, self.store, self.transcripts, "deliberation", None, deliberation(),
                          "ambiguous", **self.anchors)

    def test_inquiry_advances_current_question_version_and_invalid_insight_is_refused(self):
        from scripts import noetic_opermem_practical as native
        inquiry_purpose = bridge.purpose_for("practical-inquiry", None, practical_question_id=self.question)
        before, _ = bridge.retrieve(self.binary, self.store, self.transcripts, inquiry_purpose)
        question = native.residue(before, "practical-question", self.question)
        kind, command = bridge.contextual_command(before, "practical-inquiry", None,
            {"text": "Inspect an independent exact source snapshot."}, "fourth-option", practical_question_id=self.question)
        self.assertEqual(command["expected_object_versions"], [{"kind": "practical-question", "id": self.question, "version": question["object_version"]}])
        response, _ = bridge.submit(self.binary, self.store, self.transcripts, "practical-inquiry", None,
            {"text": "Inspect an independent exact source snapshot."}, "fourth-option", before, practical_question_id=self.question)
        option = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "option")
        fresh, _ = bridge.retrieve(self.binary, self.store, self.transcripts,
            bridge.purpose_for("practical-insight", None, practical_question_id=self.question, option_id=option))
        self.assertEqual(native.residue(fresh, "practical-question", self.question)["object_version"], question["object_version"] + 1)
        for index, change in enumerate((lambda c: c["expected_object_versions"].clear(),
            lambda c: c["expected_object_versions"].insert(0, {"kind": "judgment", "id": self.judgments[0], "version": 1}),
            lambda c: None)):
            invalid = deepcopy(command);change(invalid);invalid["idempotency_key"] = "bad-inquiry-" + str(index)
            with self.assertRaises(RuntimeError):
                with bridge.OperationHost(self.binary, self.store, bridge.fresh_transcript(self.transcripts)) as host:
                    host.context(inquiry_purpose)
                    host.exchange(kind, invalid)
        kind, insight = bridge.contextual_command(fresh, "practical-insight", None,
            {"text": "Trace: independent exact source snapshots can expose source drift."}, "fourth-insight",
            practical_question_id=self.question, option_id=option)
        self.assertEqual([r["kind"] for r in insight["expected_object_versions"]], ["option", "practical-question"])
        for index, change in enumerate((lambda c: c["expected_object_versions"].pop(),
            lambda c: c["expected_object_versions"][1].update(version=question["object_version"]),
            lambda c: c["expected_object_versions"].insert(0, {"kind": "judgment", "id": self.judgments[0], "version": 1}),
            lambda c: c["body"].update(option_id=self.question))):
            invalid = deepcopy(insight);change(invalid);invalid["idempotency_key"] = "bad-insight-" + str(index)
            with self.assertRaises(RuntimeError):
                with bridge.OperationHost(self.binary, self.store, bridge.fresh_transcript(self.transcripts)) as host:
                    host.context(bridge.purpose_for("practical-insight", None, practical_question_id=self.question, option_id=option))
                    host.exchange(kind, invalid)
        with self.assertRaisesRegex(ValueError, "context changed"):
            bridge.submit(self.binary, self.store, self.transcripts, "practical-inquiry", None,
                {"text": "A stale reviewed inquiry must remain retained."}, "stale-inquiry", before, practical_question_id=self.question)
        foreign, _ = bridge.submit(self.binary, self.store, self.transcripts, "practical-question", None,
            {"text": "What should a distinct practical question investigate?"}, "foreign-question", judgment_ids=self.judgments)
        foreign_question = next(x["id"] for x in foreign["payload"]["outputs"] if x["kind"] == "practical-question")
        foreign, _ = bridge.submit(self.binary, self.store, self.transcripts, "practical-inquiry", None,
            {"text": "Inspect a separate question's source material."}, "foreign-option", practical_question_id=foreign_question)
        foreign_option = next(x["id"] for x in foreign["payload"]["outputs"] if x["kind"] == "option")
        invalid = deepcopy(insight)
        invalid["body"]["option_id"] = foreign_option
        invalid["expected_object_versions"][0]["id"] = foreign_option
        invalid["idempotency_key"] = "actual-foreign-insight"
        with self.assertRaises(RuntimeError):
            with bridge.OperationHost(self.binary, self.store, bridge.fresh_transcript(self.transcripts)) as host:
                host.context(bridge.purpose_for("practical-insight", None, practical_question_id=self.question, option_id=option))
                host.exchange(kind, invalid)
        fresh, _ = bridge.retrieve(self.binary, self.store, self.transcripts,
            bridge.purpose_for("practical-insight", None, practical_question_id=self.question, option_id=option))
        response, _ = bridge.submit(self.binary, self.store, self.transcripts, "practical-insight", None,
            {"text": "Trace: independent exact source snapshots can expose source drift."}, "fourth-insight", fresh,
            practical_question_id=self.question, option_id=option)
        self.assertEqual(response["class"], "success")


if __name__ == "__main__":
    unittest.main()


class DecisionPlanningContributionTests(unittest.TestCase):
    def test_exact_actor_shapes_and_explicit_anchor_applicability(self):
        from scripts import noetic_opermem_decision as helper
        from tests.programs.opermem_decision_fixture import choice, steps
        maximum = 2**64 - 1
        value = choice([2, maximum])
        self.assertEqual(bridge.contribution_from_report(bridge.MARKER + json.dumps(value), "decision"), value)
        self.assertEqual(bridge.contribution_from_report(bridge.MARKER + json.dumps(steps()), "planning"), steps())
        malformed = [dict(value, selected_option_id=True), dict(value, rejected=[]),
                     dict(value, rejected=[{"option_id": maximum, "reason": " padded "}]),
                     dict(value, intention={"kind": "active", "trigger": "extra"}),
                     dict(value, intention={"kind": "abeyant", "trigger": ""})]
        for bad in malformed:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                helper.contribution(bad, "decision")
        for step in ({"position": True, "action": "A"}, {"position": 2, "action": "A"},
                     {"position": 1, "action": "A", "condition": None},
                     {"position": 1, "action": "é" * 4097}):
            with self.subTest(step=step), self.assertRaises(ValueError):
                helper.contribution({"steps": [step]}, "planning")
        helper.contribution({"steps": [{"position": 1, "action": "é" * 4096}]}, "planning")
        helper.contribution(choice([2, maximum], abeyant=True), "decision")
        for operation, anchors in (("planning", {"evaluation_id": 1}), ("decision", {"decision_id": 1}),
                                   ("decision", {"judgment_basis_ids": [3, 2]}),
                                   ("decision", {"predecessor_evaluation_id": 1}),
                                   ("question", {"supersedes_decision_id": 1})):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                bridge.purpose_for(operation, None, **anchors)


@unittest.skipUnless(os.environ.get("OPERMEM_OPERATION_HOST"), "requires actual Rust host")
class DecisionPlanningNativeBoundaryTests(unittest.TestCase):
    def setUp(self):
        from tests.programs.opermem_decision_fixture import evaluation
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.binary = Path(os.environ["OPERMEM_OPERATION_HOST"]).resolve()
        self.store, self.transcripts = self.root / "store", self.root / "transcripts"
        self.evaluation, self.question, self.basis, self.options, self.traces = evaluation(
            self.binary, self.store, self.transcripts, self.root / "checking")

    def context(self, operation, **anchors):
        return bridge.retrieve(self.binary, self.store, self.transcripts,
            bridge.purpose_for(operation, None, judgment_basis_ids=self.basis, **anchors))[0]

    def test_choice_conditioned_plan_whole_basis_and_restart(self):
        from tests.programs.opermem_decision_fixture import decision, choice, steps
        from scripts import noetic_opermem_decision as helper
        context = self.context("decision", evaluation_id=self.evaluation)
        self.assertNotIn("native_context_packets", context)
        self.assertEqual(len(self.options), 3)
        self.assertEqual(len(self.traces), 3)
        self.assertEqual(len(self.basis), 2)
        kind, payload = bridge.contextual_command(context, "decision", None, choice(self.options), "inspect-choice",
                                                  evaluation_id=self.evaluation, judgment_basis_ids=self.basis)
        self.assertEqual([x["kind"] for x in payload["expected_object_versions"]],
                         ["judgment"] * 2 + ["evaluation"] + ["option"] * 3)
        decision_id, intention, _ = decision(self.binary, self.store, self.transcripts,
                                             self.evaluation, self.basis, self.options)
        planning = self.context("planning", decision_id=decision_id)
        kind, payload = bridge.contextual_command(planning, "planning", None, steps(), "inspect-plan",
                                                  decision_id=decision_id, judgment_basis_ids=self.basis)
        self.assertEqual(payload["body"]["intention_id"], intention)
        self.assertEqual([x["kind"] for x in payload["expected_object_versions"]],
                         ["intention"] + ["judgment"] * 2 + ["decision"])
        response, _ = bridge.submit(self.binary, self.store, self.transcripts, "planning", None, steps(), "three-step-plan",
                                    decision_id=decision_id, judgment_basis_ids=self.basis)
        plan = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "plan")
        restarted = self.context("planning", decision_id=decision_id)
        self.assertEqual(helper.residue(restarted, "decision", decision_id)["retrieval_voice"]["rejected"], choice(self.options)["rejected"])
        whole_plan = next(x for x in restarted["supplied_whole_residues"] if x["residue_id"] == {"kind": "plan", "id": plan})
        self.assertEqual(whole_plan["retrieval_voice"]["judgment_basis_ids"], self.basis)
        retained_steps = sorted([x for x in restarted["supplied_whole_residues"] if x["kind"] == "plan-step"],
                                key=lambda x: x["retrieval_voice"]["position"])
        self.assertEqual([x["retrieval_voice"]["position"] for x in retained_steps], [1, 2, 3])
        self.assertEqual([x["retrieval_voice"]["condition"] for x in retained_steps],
                         [steps()["steps"][0]["condition"], None, steps()["steps"][2]["condition"]])
        for identity in self.basis:
            helper.residue(restarted, "judgment", identity)
        self.assertFalse(restarted["creates_authority"])
        self.assertFalse(restarted["external_act"])

    def test_native_complete_options_basis_versions_positions_and_abeyance_refuse(self):
        from copy import deepcopy
        from tests.programs.opermem_decision_fixture import decision, choice, steps
        context = self.context("decision", evaluation_id=self.evaluation)
        kind, good = bridge.contextual_command(context, "decision", None, choice(self.options), "native-good",
                                               evaluation_id=self.evaluation, judgment_basis_ids=self.basis)
        variants = []
        for mutate in (lambda p: p["body"]["rejected"].pop(),
                       lambda p: p["body"]["judgment_basis_ids"].pop(),
                       lambda p: p["expected_object_versions"].pop(),
                       lambda p: p["expected_object_versions"].append({"kind": "practical-question", "id": self.question, "version": 1}),
                       lambda p: p["expected_object_versions"][0].update(version=999)):
            payload = deepcopy(good);mutate(payload);variants.append(payload)
        for i, payload in enumerate(variants):
            payload["idempotency_key"] = "invalid-choice-" + str(i)
            with self.subTest(i=i), self.assertRaises(RuntimeError):
                with bridge.OperationHost(self.binary, self.store, bridge.fresh_transcript(self.transcripts)) as host:
                    host.context(bridge.purpose_for("decision", None, evaluation_id=self.evaluation, judgment_basis_ids=self.basis))
                    host.exchange(kind, payload)
            self.assertEqual(self.context("decision", evaluation_id=self.evaluation), context)
        decision_id, _, _ = decision(self.binary, self.store, self.transcripts, self.evaluation, self.basis, self.options, abeyant=True)
        planning = self.context("planning", decision_id=decision_id)
        with self.assertRaisesRegex(ValueError, "abeyant"):
            bridge.contextual_command(planning, "planning", None, steps(), "no-abeyant-plan",
                                      decision_id=decision_id, judgment_basis_ids=self.basis)
        # Native authority also refuses a direct correctly shaped plan for this intention.
        intention = next(x for x in planning["supplied_whole_residues"] if x["kind"] == "intention")
        decision_whole = next(x for x in planning["supplied_whole_residues"] if x["kind"] == "decision")
        objects = [intention] + [next(x for x in planning["supplied_whole_residues"] if x["residue_id"] == {"kind": "judgment", "id": i}) for i in self.basis] + [decision_whole]
        direct = {"body": {"decision_id": decision_id, "intention_id": intention["residue_id"]["id"], "judgment_basis_ids": self.basis, **steps()},
                  "command_version": 1, "idempotency_key": "direct-abeyant-plan",
                  "expected_object_versions": [{**x["residue_id"], "version": x["object_version"]} for x in objects]}
        with self.assertRaises(RuntimeError):
            with bridge.OperationHost(self.binary, self.store, bridge.fresh_transcript(self.transcripts)) as host:
                host.context(bridge.purpose_for("planning", None, decision_id=decision_id, judgment_basis_ids=self.basis))
                host.exchange("plan", direct)
        self.assertEqual(self.context("planning", decision_id=decision_id), planning)

    def test_legal_supersession_uses_distinct_native_packet_and_history_stays_historical(self):
        from scripts import noetic_opermem_decision as helper
        from tests.programs.opermem_decision_fixture import decision, choice
        from tests.programs.opermem_practical_fixture import deliberation
        predecessor, _, _ = decision(self.binary, self.store, self.transcripts, self.evaluation, self.basis, self.options)
        same = self.context("decision", evaluation_id=self.evaluation)
        same_anchors = {"evaluation_id": self.evaluation, "judgment_basis_ids": self.basis, "supersedes_decision_id": predecessor}
        same_envelope, _ = bridge.retrieve(self.binary, self.store, self.transcripts, bridge.purpose_for("decision", None, **same_anchors))
        with self.assertRaisesRegex(ValueError, "different evaluation"):
            helper.material(same_envelope, "decision", **same_anchors)
        kind, same_command = bridge.contextual_command(same, "decision", None, choice(self.options), "same-evaluation-supersession",
                                                      evaluation_id=self.evaluation, judgment_basis_ids=self.basis)
        same_command["body"]["supersedes_decision_id"] = predecessor
        old = helper.residue(same, "decision", predecessor)
        same_command["expected_object_versions"].insert(len(self.basis), {**old["residue_id"], "version": old["object_version"]})
        with self.assertRaises(RuntimeError):
            with bridge.OperationHost(self.binary, self.store, bridge.fresh_transcript(self.transcripts)) as host:
                host.context(bridge.purpose_for("decision", None, evaluation_id=self.evaluation, judgment_basis_ids=self.basis))
                host.exchange(kind, same_command)
        self.assertEqual(self.context("decision", evaluation_id=self.evaluation), same)
        response, _ = bridge.submit(self.binary, self.store, self.transcripts, "deliberation", None, deliberation(), "renewed-evaluation",
                                    practical_question_id=self.question, option_ids=self.options)
        evaluation = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "evaluation")
        primary = self.context("decision", evaluation_id=evaluation)
        self.assertFalse(any(x["residue_id"] == {"kind": "decision", "id": predecessor} for x in primary["supplied_whole_residues"]))
        anchors = {"evaluation_id": evaluation, "judgment_basis_ids": self.basis, "supersedes_decision_id": predecessor,
                   "predecessor_evaluation_id": self.evaluation}
        context, _ = bridge.retrieve(self.binary, self.store, self.transcripts, bridge.purpose_for("decision", None, **anchors))
        self.assertEqual([p["operation"] for p in context["native_context_packets"]], ["decision", "decision"])
        helper.material(context, "decision", **anchors)
        by_planning = self.context("decision", evaluation_id=evaluation, supersedes_decision_id=predecessor)
        self.assertEqual(by_planning["native_context_packets"][1]["operation"], "planning")
        helper.material(by_planning, "decision", evaluation_id=evaluation, judgment_basis_ids=self.basis, supersedes_decision_id=predecessor)
        response, _ = bridge.submit(self.binary, self.store, self.transcripts, "decision", None, choice(self.options), "superseding-decision", **anchors)
        successor = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "decision")
        restarted = self.context("planning", decision_id=successor)
        self.assertEqual(helper.residue(restarted, "decision", successor)["retrieval_voice"]["supersedes_decision_id"], predecessor)
        old = self.context("decision", evaluation_id=self.evaluation)
        historical = next(x for x in old["supplied_whole_residues"] if x["residue_id"] == {"kind": "decision", "id": predecessor})
        self.assertEqual(historical["retrieval_voice"]["lifecycle"], "superseded")
        self.assertEqual(historical["liveness"], "superseded")
        exposed, _ = bridge.retrieve(self.binary, self.store, self.transcripts, bridge.purpose_for("decision", None, **anchors))
        with self.assertRaisesRegex(ValueError, "live"):
            helper.material(exposed, "decision", **anchors)


    def test_active_plan_native_positions_exact_refs_and_foreign_intention_refuse(self):
        from copy import deepcopy
        from tests.programs.opermem_decision_fixture import decision, steps
        decision_id, _, _ = decision(self.binary, self.store, self.transcripts, self.evaluation, self.basis, self.options)
        other_decision, other_intention, _ = decision(self.binary, self.store, self.transcripts, self.evaluation, self.basis, self.options, key="other-decision")
        context = self.context("planning", decision_id=decision_id)
        kind, good = bridge.contextual_command(context, "planning", None, steps(), "plan-validation",
                                               decision_id=decision_id, judgment_basis_ids=self.basis)
        variants = []
        for mutate in (lambda p: p["body"]["steps"][1].update(position=3),
                       lambda p: p["body"]["steps"][0].update(position=0),
                       lambda p: p["body"]["steps"][0].update(condition=None),
                       lambda p: p["body"]["judgment_basis_ids"].pop(),
                       lambda p: p["expected_object_versions"].pop(),
                       lambda p: p["expected_object_versions"][0].update(version=999),
                       lambda p: p["expected_object_versions"].append({"kind": "evaluation", "id": self.evaluation, "version": 1})):
            payload = deepcopy(good);mutate(payload);variants.append(payload)
        foreign = deepcopy(good)
        foreign["body"]["intention_id"] = other_intention
        foreign_context = self.context("planning", decision_id=other_decision)
        foreign["expected_object_versions"][0] = next({**x["residue_id"], "version": x["object_version"]} for x in foreign_context["supplied_whole_residues"] if x["residue_id"] == {"kind": "intention", "id": other_intention})
        variants.append(foreign)
        for i, payload in enumerate(variants):
            payload["idempotency_key"] = "invalid-plan-" + str(i)
            with self.subTest(i=i), self.assertRaises(RuntimeError):
                with bridge.OperationHost(self.binary, self.store, bridge.fresh_transcript(self.transcripts)) as host:
                    host.context(bridge.purpose_for("planning", None, decision_id=decision_id, judgment_basis_ids=self.basis))
                    host.exchange(kind, payload)
            self.assertEqual(self.context("planning", decision_id=decision_id), context)
        with self.assertRaises(RuntimeError):
            bridge.retrieve(self.binary, self.store, self.transcripts,
                bridge.purpose_for("planning", None, decision_id=decision_id, judgment_basis_ids=self.basis[:1]))


class ActingRecurrenceContributionTests(unittest.TestCase):
    def test_exact_native_artifacts_and_question_occasion_selectors(self):
        from scripts import noetic_opermem_acting as helper
        value = {"observed_act": "  Exact act\n", "outcome": " Outcome\n ", "deviation": "Exact deviation\n"}
        self.assertEqual(bridge.contribution_from_report(bridge.MARKER + json.dumps(value), "acting"), value)
        for field in value:
            for invalid in ("", " \n", "tab\t", "CR\r", "C1\x85", "é" * 12289):
                bad = dict(value);bad[field] = invalid
                with self.subTest(field=field, invalid=invalid[:10]), self.assertRaises(ValueError):
                    helper.contribution(bad)
        helper.contribution({"observed_act": "é" * 12288, "outcome": "x" * 8192})
        with self.assertRaisesRegex(ValueError, "combined"):
            helper.contribution({"observed_act": "é" * 12288, "outcome": "x" * 8193})
        for anchors in ({"occasion_kind": "outcome-as-experience"}, {"occasion_id": True},
                        {"occasion_id": 2**64}, {"occasion_kind": "outcome"}):
            with self.subTest(anchors=anchors), self.assertRaises(ValueError):
                bridge.purpose_for("question", None, **anchors)
        self.assertEqual(bridge.purpose_for("question", None)["occasion"], {"kind": "experience", "id": 1})
        self.assertEqual(bridge.purpose_for("question", None, occasion_kind="outcome-as-experience", occasion_id=2**64-1)["occasion"]["id"], 2**64-1)
        with self.assertRaises(ValueError):
            bridge.purpose_for("insight", 1, occasion_id=2)
        with self.assertRaises(ValueError):
            bridge.purpose_for("acting", None, plan_id=1, step_id=False)


@unittest.skipUnless(os.environ.get("OPERMEM_OPERATION_HOST"), "requires actual Rust host")
class ActingRecurrenceNativeBoundaryTests(unittest.TestCase):
    def setUp(self):
        from tests.programs.opermem_acting_fixture import native_plan
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.binary = Path(os.environ["OPERMEM_OPERATION_HOST"]).resolve()
        self.store, self.transcripts = self.root / "store", self.root / "transcripts"
        self.plan, self.step, self.decision, self.basis, self.question, self.options = native_plan(self.binary, self.store, self.transcripts, self.root)
        self.anchors = {"plan_id": self.plan, "step_id": self.step}

    def context(self):
        return bridge.retrieve(self.binary, self.store, self.transcripts, bridge.purpose_for("acting", None, **self.anchors))[0]

    def test_actual_success_failed_observation_exact_cardinality_restart_and_recurrence(self):
        from scripts import noetic_opermem_acting as helper, noetic_act_observation as evidence
        from tests.programs.opermem_acting_fixture import external_work, archived, prose
        for failed in (False, True):
            root = self.root / ("failed" if failed else "success");root.mkdir(mode=0o700)
            source = external_work(root, failed=failed)
            archive, sha, bound, manifest = archived(root, source, prose(failed=failed))
            self.assertEqual(manifest["selected"]["state"], "failed" if failed else "passed")
            context = self.context()
            kind, command = bridge.contextual_command(context, "acting", None, bound, "probe-" + str(failed),
                **self.anchors, observation_evidence=archive, observation_manifest_sha256=sha)
            self.assertEqual(command["expected_object_versions"], [{**helper.residue(context, role, identity)["residue_id"],
                "version": helper.residue(context, role, identity)["object_version"]} for role, identity in (("plan", self.plan), ("plan-step", self.step))])
            self.assertNotIn("observation", command["body"])
            response, _ = bridge.submit(self.binary, self.store, self.transcripts, "acting", None, bound, "observe-" + str(failed),
                **self.anchors, observation_evidence=archive, observation_manifest_sha256=sha)
            expected = {"act-trace", "outcome", "outcome-as-experience"} | ({"deviation"} if failed else set())
            self.assertEqual({x["kind"] for x in response["payload"]["outputs"]}, expected)
            self.assertEqual(len(response["payload"]["outputs"]), 4 if failed else 3)
            current = self.context()
            trace = next(x for x in current["supplied_whole_residues"] if x["residue_id"] == next({"kind": x["kind"], "id": x["id"]} for x in response["payload"]["outputs"] if x["kind"] == "act-trace"))
            for field, text in prose(failed=failed).items():
                self.assertEqual(trace["retrieval_voice"][field], text)
            self.assertEqual(helper.residue(current, "plan", self.plan)["retrieval_voice"]["state"], "planned")
            self.assertEqual(helper.residue(current, "plan-step", self.step)["retrieval_voice"]["state"], "planned")
            outcome = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "outcome-as-experience")
            occasion = {"occasion_kind": "outcome-as-experience", "occasion_id": outcome}
            packet, _ = bridge.retrieve(self.binary, self.store, self.transcripts, bridge.purpose_for("question", None, **occasion))
            parent = bridge.parent_from_context(packet, "question", None, **occasion)
            proposal = {"question_kind": "what", "text": "What should recur from this actual retained outcome?"}
            kind, cmd = bridge.contextual_command(packet, "question", None, proposal, "recurrence-probe", **occasion)
            self.assertEqual(cmd["body"]["occasion_id"], outcome)
            self.assertEqual(cmd["expected_object_versions"], [{"kind": "outcome-as-experience", "id": outcome, "version": parent["object_version"]}])
            from copy import deepcopy
            for index, mutate in enumerate((lambda p: p["expected_object_versions"][0].update(version=999),
                                            lambda p: p["body"].update(occasion_kind="experience"))):
                invalid = deepcopy(cmd);mutate(invalid);invalid["idempotency_key"] = "bad-recurrence-" + str(failed) + str(index)
                with self.assertRaises(RuntimeError):
                    with bridge.OperationHost(self.binary, self.store, bridge.fresh_transcript(self.transcripts)) as host:
                        host.context(bridge.purpose_for("question", None, **occasion))
                        host.exchange(kind, invalid)
                self.assertEqual(bridge.retrieve(self.binary, self.store, self.transcripts, bridge.purpose_for("question", None, **occasion))[0], packet)
            recurrent, _ = bridge.submit(self.binary, self.store, self.transcripts, "question", None, proposal, "fresh-recurrence-" + str(failed), **occasion)
            question = next(x["id"] for x in recurrent["payload"]["outputs"] if x["kind"] == "intelligence-question")
            fresh, _ = bridge.retrieve(self.binary, self.store, self.transcripts, bridge.purpose_for("insight", question))
            whole = next(x for x in fresh["supplied_whole_residues"] if x["residue_id"] == {"kind": "intelligence-question", "id": question})
            self.assertEqual(whole["content"]["command"]["payload"]["occasion"], {"kind": "outcome-as-experience", "id": outcome})
            source.rename(source.with_name(source.name + "-removed"))
            evidence.revalidate(archive, sha, current=False)
            with self.assertRaises(OSError):
                evidence.revalidate(archive, sha, current=True)

    def test_native_text_deviation_foreign_stale_missing_extra_and_evidence_refusal(self):
        from copy import deepcopy
        from scripts import noetic_opermem_acting as helper
        from tests.programs.opermem_acting_fixture import external_work, archived, prose
        source = external_work(self.root)
        archive, sha, bound, _ = archived(self.root, source, prose())
        context = self.context()
        kind, good = bridge.contextual_command(context, "acting", None, bound, "good-act", **self.anchors,
                                               observation_evidence=archive, observation_manifest_sha256=sha)
        variants = []
        for mutate in (lambda p: p["body"].update(deviation="No actual difference."),
                       lambda p: p["body"].update(observed_act="Different actual text"),
                       lambda p: p["body"].update(outcome="bad\ttext"),
                       lambda p: p["body"].update(outcome="é" * 12289),
                       lambda p: p["expected_object_versions"].pop(),
                       lambda p: p["expected_object_versions"][0].update(version=999),
                       lambda p: p["expected_object_versions"].append({"kind": "judgment", "id": self.basis[0], "version": 1})):
            payload = deepcopy(good);mutate(payload);variants.append(payload)
        # Another actual native plan's current step is a foreign immediate reference.
        response, _ = bridge.submit(self.binary, self.store, self.transcripts, "planning", None,
            {"steps": [{"position": 1, "action": prose()["observed_act"]}]}, "foreign-plan", decision_id=self.decision, judgment_basis_ids=self.basis)
        other_plan = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "plan")
        other_step = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "plan-step")
        context = self.context()
        foreign = deepcopy(good);foreign["body"]["step_id"] = other_step
        other, _ = bridge.retrieve(self.binary, self.store, self.transcripts, bridge.purpose_for("acting", None, plan_id=other_plan, step_id=other_step))
        foreign["expected_object_versions"][1] = {"kind": "plan-step", "id": other_step, "version": helper.residue(other, "plan-step", other_step)["object_version"]}
        variants.append(foreign)
        for i, payload in enumerate(variants):
            payload["idempotency_key"] = "invalid-act-" + str(i)
            with self.subTest(i=i), self.assertRaises(RuntimeError):
                with bridge.OperationHost(self.binary, self.store, bridge.fresh_transcript(self.transcripts)) as host:
                    host.context(bridge.purpose_for("acting", None, **self.anchors))
                    host.exchange(kind, payload)
            self.assertEqual(self.context(), context)
        altered = deepcopy(bound);altered["observation"]["finish_sequence"] += 1
        with self.assertRaisesRegex(ValueError, "binding"):
            bridge.contextual_command(context, "acting", None, altered, "bad-binding", **self.anchors,
                                      observation_evidence=archive, observation_manifest_sha256=sha)
        raw = (archive / "work.stdout.log").read_bytes()
        (archive / "work.stdout.log").write_bytes(raw + b"substituted")
        with self.assertRaisesRegex(ValueError, "hash"):
            bridge.submit(self.binary, self.store, self.transcripts, "acting", None, bound, "bad-evidence", **self.anchors,
                          observation_evidence=archive, observation_manifest_sha256=sha)
        self.assertEqual(self.context(), context)
        (archive / "work.stdout.log").unlink()
        with self.assertRaises(OSError):
            helper.bind(prose(), archive, sha)

    def test_launch_failure_remains_retained_nonoccurrence_and_cannot_deposit(self):
        from scripts import noetic_act_observation as evidence, noetic_opermem_acting as helper
        from tests.programs.opermem_acting_fixture import external_work, prose
        source = external_work(self.root, launch_failed=True)
        archive = self.root / "launch-failure-evidence"
        manifest = evidence.capture(source, archive)
        sha = evidence.digest((archive / "manifest.json").read_bytes())
        self.assertFalse(manifest["selected"]["occurred"])
        before = self.context()
        with self.assertRaisesRegex(ValueError, "launch failure"):
            helper.bind(prose(), archive, sha)
        self.assertEqual(self.context(), before)
