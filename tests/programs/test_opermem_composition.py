"""Joint Rust/Telos fixtures exercise composition; fixture clients are not live agents."""

from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import noetic_develop as development
from scripts import noetic_opermem as bridge
from scripts import noetic_run as runtime
from scripts import noetic_telos as telos


@unittest.skipUnless(os.environ.get("OPERMEM_OPERATION_HOST"), "requires actual Rust host")
class OpermemCompositionTests(unittest.TestCase):
    def setUp(self):
        self.source = telos.source_path(os.environ.get("NOETIC_TEST_TELOS_SOURCE"))
        factory = self.source if self.source.suffix == ".mjs" else self.source / "packages/pi-runtime/src/core-goal-chain-store.ts"
        if not shutil.which("node") or not factory.is_file():
            self.skipTest("requires actual Telos factory and Node 24")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.binary = Path(os.environ["OPERMEM_OPERATION_HOST"]).resolve()
        self.db = self.root / "telos.sqlite3"
        self.aggregate = telos.create_goal("Retain useful work across sessions", self.db, self.source)
        self.chain = self.aggregate["chain"]["chainId"]
        self.store = self.root / "store"
        self.runs = self.root / "runs"
        question, _ = bridge.submit(self.binary, self.store, self.root / "transcripts", "question", None,
                                   {"question_kind": "how", "text": "How can current bindings survive lost exports?"},
                                   "composition-question")
        self.question = question["payload"]["outputs"][0]["id"]
        self.task = self.root / "task.md"
        self.task.write_text("Inspect the current binding boundary; propose a trace.")
        self.prompts = {}
        self.operation = "insight"
        self.parent = self.question
        self.formulation = None
        self.anchors = {}
        self.contribution = {"text": "Fixture trace: current bindings differ from retained exports."}
        self.worker_report = None

    def client(self, client, prompt, role, model, run_dir=None, workspace=None, context_dirs=()):
        self.prompts[role] = prompt
        if self.operation == "acting":
            self.assertEqual(len(context_dirs), 1)
            archive = Path(context_dirs[0])
            manifest = json.loads((archive / "manifest.json").read_text())
            for name in manifest["files"]:
                self.assertTrue((archive / name).is_file())
            self.assertEqual(manifest["selected"]["state"], "failed" if getattr(self, "observed_failed", False) else "passed")
        text = (self.worker_report or bridge.MARKER + json.dumps(self.contribution)
                if role != "reviewer" else "ACCEPT\nFixture reviewer inspected the reported boundary.")
        events = [{"type": "text", "sessionID": role, "part": {"id": "part-1", "messageID": role, "text": text}},
                  {"type": "step_finish", "sessionID": role, "part": {"messageID": role, "reason": "stop"}}]
        code = "import sys; assert sys.stdin.read(); print(" + repr("\n".join(json.dumps(e) for e in events)) + ")"
        return [sys.executable, "-c", code], None

    def args(self):
        args = ["--host", str(self.binary), "--store", str(self.store), "--runs-dir", str(self.runs),
                "run", str(self.task), "--workspace", str(self.root), "--operation", self.operation,
                "--client", "opencode", "--inquiry",
                "--telos-chain", self.chain, "--telos-db", str(self.db), "--telos-source", str(self.source)]
        if self.operation in bridge.CONTEXT_OPERATIONS:
            for name, value in self.anchors.items():
                args += ["--" + name.replace("_", "-")] + ([str(i) for i in value] if isinstance(value, list) else [str(value)])
        elif self.operation != "question":
            args += ["--parent-id", str(self.parent)]
        if self.operation == "conditional-structure":
            args += ["--formulation-id", str(self.formulation)]
        if self.operation == "acting":
            if getattr(self, "archived_input", None):
                args += ["--observation-evidence", str(self.archived_input[0]), "--observation-manifest-sha256", self.archived_input[1]]
            else:
                args += ["--observed-run", str(self.observed_run)]
        if self.operation == "question":
            for name, value in self.anchors.items():
                args += ["--" + name.replace("_", "-"), str(value)]
        return args

    def prepare_reflection(self):
        parent = self.question
        for operation, role in (("insight", "unverified insight trace"),
                                ("formulation", "versioned formulation/hypothesis")):
            response, _ = bridge.submit(self.binary, self.store, self.root / "transcripts",
                                       operation, parent, {"text": "Fixture " + operation + " about retained bindings."},
                                       "composition-" + operation)
            parent = next(item["id"] for item in response["payload"]["outputs"] if item["role"] == role)
        self.operation = "reflection"
        self.parent = self.formulation = parent
        self.contribution = {"text": "Is the retained binding formulation correct?"}

    def prepare_conditional_structure(self):
        self.prepare_reflection()
        response, _ = bridge.submit(self.binary, self.store, self.root / "transcripts", "reflection",
                                   self.formulation, self.contribution, "composition-reflection")
        self.operation = "conditional-structure"
        self.parent = next(item["id"] for item in response["payload"]["outputs"]
                           if item["role"] == "reflection question")
        self.contribution = {"conditions": ["A: inspect current typed anchors", "B: inspect exact replay receipts"]}

    def prepare_judgment(self):
        from tests.programs.opermem_judgment_fixture import checked_warrant, proposed_judgment
        directory = self.root / "checking"
        directory.mkdir()
        warrant, conditions = checked_warrant(self.binary, self.store, self.root / "transcripts", directory, count=2)
        self.operation, self.parent = "judgment", None
        self.anchors = {"warrant_id": warrant, "condition_ids": conditions}
        self.contribution = proposed_judgment()

    def prepare_practical_question(self):
        self.prepare_judgment()
        judgments = []
        for key in ("first-native-judgment", "second-native-judgment"):
            response, _ = bridge.submit(self.binary, self.store, self.root / "transcripts", "judgment", None,
                                       self.contribution, key, **self.anchors)
            judgments.append(next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "judgment"))
        self.operation = "practical-question"
        self.anchors = {"judgment_ids": sorted(judgments)}
        self.contribution = {"text": "Given both judgments, what should be investigated next?"}


    def prepare_practical_operation(self, operation):
        from tests.programs.opermem_practical_fixture import practical_question, courses, deliberation, COURSES
        question, judgments = practical_question(self.binary, self.store, self.root / "transcripts", self.root / "practical-checking")
        self.practical_judgments = judgments
        self.operation, self.parent = operation, None
        self.anchors = {"practical_question_id": question}
        if operation == "practical-inquiry":
            self.contribution = {"text": COURSES[0][0]}
        elif operation == "practical-insight":
            options, _ = courses(self.binary, self.store, self.root / "transcripts", question, count=1, traces=False)
            self.anchors["option_id"] = options[0]
            self.contribution = {"text": COURSES[0][1]}
        else:
            options, _ = courses(self.binary, self.store, self.root / "transcripts", question)
            self.anchors["option_ids"] = options
            self.contribution = deliberation()


    def run_fixture(self):
        with patch.object(development, "client_command", side_effect=self.client), redirect_stdout(io.StringIO()):
            return bridge.main(self.args())

    def latest(self):
        return Path(runtime.list_runs(self.runs)[0]["directory"])

    def test_joint_run_retains_frozen_purpose_and_current_residue(self):
        self.assertEqual(self.run_fixture(), 0)
        run = self.latest()
        snapshot = json.loads((run / "telos-context.json").read_text())
        frozen = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        self.assertIn(frozen, self.prompts["inquirer"])
        self.assertIn(frozen, self.prompts["reviewer"])
        self.assertEqual(snapshot["primary_goal"], self.aggregate["chain"]["primaryGoal"])
        self.assertEqual(snapshot["reproductive_clause"], self.aggregate["reproductiveClause"])
        events = runtime.read_events(run)
        kinds = [e["kind"] for e in events]
        self.assertLess(kinds.index("telos.linked"), kinds.index("step.started"))
        result = runtime.project(events)
        self.assertEqual(result["goal"], self.task.read_text())
        self.assertIn('"standing": "question"', self.prompts["inquirer"])
        self.assertEqual(result["telos_result"]["opermem"]["submission"], "committed")
        self.assertEqual(result["telos_result"]["subgoal_status"], "complete")
        self.assertEqual(telos.get_goal(self.chain, self.db, self.source)["chain"]["status"], "active")
        self.assertEqual(self.run_fixture(), 0)
        fresh = json.loads((self.latest() / "telos-context.json").read_text())
        self.assertIn(run.name, [r["run_id"] for r in fresh["prior_runs"]])

    def test_deposit_failure_preserves_review_but_keeps_telos_active(self):
        with patch.object(bridge, "submit", side_effect=OSError("fixture deposit interrupted")):
            self.assertEqual(self.run_fixture(), 1)
        run = self.latest()
        result = runtime.project(runtime.read_events(run))
        self.assertEqual(result["state"], "accepted")
        self.assertEqual(result["telos_result"]["subgoal_status"], "active")
        self.assertEqual(result["telos_result"]["opermem"]["submission"], "pending")
        self.assertFalse((run / "opermem-receipt.json").exists())

    def test_resume_repairs_deposit_and_telos_without_new_actor_or_effect(self):
        actual_submit = bridge.submit
        def interrupted(*args, **kwargs):
            actual_submit(*args, **kwargs)
            raise OSError("fixture crash after Rust committed")
        with patch.object(bridge, "submit", side_effect=interrupted):
            self.assertEqual(self.run_fixture(), 1)
        run = self.latest()
        before = list(self.prompts)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts"), 0)
        receipt = json.loads((run / "opermem-receipt.json").read_text())
        self.assertEqual(receipt["response"]["class"], "idempotency-replay")
        result = runtime.project(runtime.read_events(run))
        self.assertEqual(result["telos_result"]["subgoal_status"], "complete")
        aggregate = telos.get_goal(self.chain, self.db, self.source)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts"), 0)
        self.assertEqual(telos.get_goal(self.chain, self.db, self.source), aggregate)
        self.assertEqual(list(self.prompts), before)

    def test_missing_chain_prevents_actor_launch(self):
        args = self.args()
        args[args.index("--telos-chain") + 1] = "missing-fixture-chain"
        with patch.object(development, "client_command") as client:
            with self.assertRaisesRegex(ValueError, "not found"):
                bridge.main(args)
        client.assert_not_called()

    def test_telos_sync_failure_is_visible_and_receipt_only_retry_recovers(self):
        with patch.object(telos, "record_result", side_effect=OSError("fixture Telos unavailable")):
            self.assertEqual(self.run_fixture(), 1)
        run = self.latest()
        result = runtime.project(runtime.read_events(run))
        self.assertEqual(result["state"], "accepted")
        self.assertIn("fixture Telos unavailable", result["telos_error"])
        self.assertTrue((run / "opermem-receipt.json").is_file())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts"), 0)
        result = runtime.project(runtime.read_events(run))
        self.assertNotIn("telos_error", result)
        self.assertEqual(result["telos_result"]["subgoal_status"], "complete")

    def test_original_qualification_is_retained_and_task_mismatch_prevents_actor(self):
        from tests.programs.test_noetic_genus import GenusPacketTests, TASK
        self.task.write_text(TASK)
        packet, _ = GenusPacketTests().packet(chosen="gpt-6.1-sol")
        evidence = self.root / "qualification.json"
        evidence.write_text(json.dumps(packet))
        args = self.args() + ["--model", "gpt-6.1-sol", "--qualification", str(evidence)]
        with patch.object(development, "client_command", side_effect=self.client), redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.main(args), 0)
        run = self.latest()
        self.assertEqual(json.loads((run / "genus-selection.json").read_text()), packet)
        self.assertIn('"qualification_support": "catalog_unmatched"', self.prompts["inquirer"])
        self.assertEqual(json.loads((run / "opermem-link.json").read_text())["worker_model"], "gpt-6.1-sol")
        self.task.write_text("Changed task with different acceptance.")
        with patch.object(development, "client_command") as client:
            with self.assertRaisesRegex(ValueError, "task"):
                bridge.main(args)
        client.assert_not_called()

    def test_reviewed_reflection_and_warrant_runs_retain_purpose_and_native_context(self):
        self.prepare_reflection()
        self.assertEqual(self.run_fixture(), 0)
        reflection_run = self.latest()
        response = json.loads((reflection_run / "opermem-receipt.json").read_text())["response"]
        self.parent = next(item["id"] for item in response["payload"]["outputs"]
                           if item["role"] == "reflection question")
        self.operation = "conditional-structure"
        self.contribution = {"conditions": ["A: inspect current typed anchors", "B: inspect exact replay receipts"]}
        self.assertEqual(self.run_fixture(), 0)
        run = self.latest()
        link = json.loads((run / "opermem-link.json").read_text())
        self.assertEqual(link["parent_id"], self.parent)
        self.assertEqual(link["formulation_id"], self.formulation)
        intact = json.dumps(link["context"], ensure_ascii=False, sort_keys=True)
        frozen = json.dumps(json.loads((run / "telos-context.json").read_text()), ensure_ascii=False, sort_keys=True)
        for role in ("inquirer", "reviewer"):
            self.assertIn(intact, self.prompts[role])
            self.assertIn(frozen, self.prompts[role])
            self.assertIn('"standing": "hypothesis"', self.prompts[role])
            self.assertIn('"standing": "reflection-question"', self.prompts[role])
        receipt = json.loads((run / "opermem-receipt.json").read_text())
        self.assertEqual(receipt["contribution"], self.contribution)
        self.assertEqual([item["role"] for item in receipt["response"]["payload"]["outputs"]].count(
            "addressable warrant conditions"), 2)
        result = runtime.project(runtime.read_events(run))
        self.assertEqual(result["goal"], self.task.read_text())
        self.assertEqual(result["telos_result"]["subgoal_status"], "complete")
        self.assertEqual(telos.get_goal(self.chain, self.db, self.source)["chain"]["status"], "active")

    def test_conditional_context_drift_preserves_accepted_task_and_active_subgoal(self):
        self.prepare_conditional_structure()
        def drifting_client(*args, **kwargs):
            if args[2] == "reviewer":
                bridge.submit(self.binary, self.store, self.root / "transcripts", "question", None,
                              {"question_kind": "what", "text": "What changed during review?"}, "review-drift")
            return self.client(*args, **kwargs)
        with patch.object(development, "client_command", side_effect=drifting_client), redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.main(self.args()), 1)
        run = self.latest()
        result = runtime.project(runtime.read_events(run))
        self.assertEqual(result["state"], "accepted")
        self.assertEqual(result["telos_result"]["subgoal_status"], "active")
        self.assertEqual(result["telos_result"]["opermem"]["submission"], "pending")
        self.assertFalse((run / "opermem-pending.json").exists())
        self.assertFalse((run / "opermem-receipt.json").exists())

    def test_ambiguous_conditional_report_preserves_review_without_native_deposit(self):
        self.prepare_conditional_structure()
        self.worker_report = (bridge.MARKER + '{"conditions":["A: first proposed condition"],'
                              '"conditions":["B: second proposed condition"]}')
        purpose = {"operation": "conditional-structure", "reflection_id": self.parent,
                   "formulation_id": self.formulation}
        before, _ = bridge.retrieve(self.binary, self.store, self.root / "transcripts", purpose)
        self.assertEqual(self.run_fixture(), 1)
        run = self.latest()
        self.assertEqual((run / "work.md").read_text().strip(), self.worker_report)
        result = runtime.project(runtime.read_events(run))
        self.assertEqual(result["state"], "accepted")
        self.assertEqual(result["telos_result"]["subgoal_status"], "active")
        self.assertEqual(result["telos_result"]["opermem"]["submission"], "pending")
        self.assertFalse((run / "opermem-pending.json").exists())
        self.assertFalse((run / "opermem-receipt.json").exists())
        after, _ = bridge.retrieve(self.binary, self.store, self.root / "transcripts", purpose)
        self.assertEqual(after, before)

    def test_conditional_crash_replays_native_receipt_before_completing_telos(self):
        self.prepare_conditional_structure()
        actual_submit = bridge.submit
        committed = []
        def interrupted(*args, **kwargs):
            committed.append(actual_submit(*args, **kwargs)[0])
            raise OSError("fixture crash after conditional structure committed")
        with patch.object(bridge, "submit", side_effect=interrupted):
            self.assertEqual(self.run_fixture(), 1)
        run = self.latest()
        result = runtime.project(runtime.read_events(run))
        self.assertEqual(result["state"], "accepted")
        self.assertEqual(result["telos_result"]["subgoal_status"], "active")
        before, _ = bridge.retrieve(self.binary, self.store, self.root / "transcripts",
                                   {"operation": "conditional-structure", "reflection_id": self.parent,
                                    "formulation_id": self.formulation})
        with patch.object(development, "client_command") as client, redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts"), 0)
        client.assert_not_called()
        receipt = json.loads((run / "opermem-receipt.json").read_text())["response"]
        self.assertEqual(receipt["class"], "idempotency-replay")
        self.assertEqual(receipt["payload"]["receipt_id"], committed[0]["payload"]["receipt_id"])
        self.assertEqual(receipt["payload"]["exact_result"], committed[0]["payload"]["exact_result"])
        after, _ = bridge.retrieve(self.binary, self.store, self.root / "transcripts",
                                  {"operation": "conditional-structure", "reflection_id": self.parent,
                                   "formulation_id": self.formulation})
        self.assertEqual(after, before)
        self.assertEqual(runtime.project(runtime.read_events(run))["telos_result"]["subgoal_status"], "complete")
        aggregate = telos.get_goal(self.chain, self.db, self.source)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts"), 0)
        self.assertEqual(telos.get_goal(self.chain, self.db, self.source), aggregate)

    def assert_whole_review_and_receipt(self):
        self.assertEqual(self.run_fixture(), 0)
        run = self.latest()
        link = json.loads((run / "opermem-link.json").read_text())
        packet = json.dumps(link["context"], ensure_ascii=False, sort_keys=True)
        purpose = json.dumps(json.loads((run / "telos-context.json").read_text()), ensure_ascii=False, sort_keys=True)
        for role in ("inquirer", "reviewer"):
            self.assertIn(packet, self.prompts[role])
            self.assertIn(purpose, self.prompts[role])
        self.assertEqual({key: link[key] for key in self.anchors}, self.anchors)
        receipt = json.loads((run / "opermem-receipt.json").read_text())
        self.assertEqual(receipt["contribution"], self.contribution)
        self.assertEqual(runtime.project(runtime.read_events(run))["telos_result"]["subgoal_status"], "complete")
        self.assertEqual(telos.get_goal(self.chain, self.db, self.source)["chain"]["status"], "active")
        return receipt

    def test_reviewed_judgment_keeps_actor_polarity_defeat_conditions_and_rationale(self):
        self.prepare_judgment()
        receipt = self.assert_whole_review_and_receipt()
        context, _ = bridge.retrieve(self.binary, self.store, self.root / "transcripts",
            bridge.purpose_for("practical-question", None, judgment_ids=[next(x["id"] for x in receipt["response"]["payload"]["outputs"] if x["kind"] == "judgment")]))
        whole = next(x for x in context["supplied_whole_residues"] if x["kind"] == "judgment")
        self.assertEqual(whole["retrieval_voice"]["polarity"]["kind"], self.contribution["polarity"]["kind"])
        self.assertEqual(whole["retrieval_voice"]["defeat_conditions"], self.contribution["defeat_conditions"])
        self.assertNotIn("rationale", whole["content"]["command"]["payload"])
        self.assertIn("Task verification and review acceptance do not affirm", self.prompts["reviewer"])

    def test_reviewed_practical_question_preserves_complete_many_judgment_basis(self):
        self.prepare_practical_question()
        self.assert_whole_review_and_receipt()
        for identity in self.anchors["judgment_ids"]:
            self.assertIn(str(identity), self.prompts["reviewer"])

    def assert_new_operation_context_drift(self):
        def drifting(*args, **kwargs):
            if args[2] == "reviewer":
                bridge.submit(self.binary, self.store, self.root / "transcripts", "question", None,
                    {"question_kind": "what", "text": "What changed during the reviewed judgment task?"}, "new-review-drift")
            return self.client(*args, **kwargs)
        with patch.object(development, "client_command", side_effect=drifting), redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.main(self.args()), 1)
        run = self.latest()
        state = runtime.project(runtime.read_events(run))
        self.assertEqual(state["state"], "accepted")
        self.assertEqual(state["telos_result"]["subgoal_status"], "active")
        self.assertEqual(state["telos_result"]["opermem"]["submission"], "pending")
        self.assertTrue((run / "work.md").is_file())
        self.assertFalse((run / "opermem-pending.json").exists())
        self.assertFalse((run / "opermem-receipt.json").exists())

    def test_judgment_context_drift_preserves_task_and_pending_purpose(self):
        self.prepare_judgment()
        self.assert_new_operation_context_drift()

    def test_practical_context_drift_preserves_task_and_pending_purpose(self):
        self.prepare_practical_question()
        self.assert_new_operation_context_drift()

    def assert_new_operation_crash_recovery(self):
        submit = bridge.submit
        committed = []
        def interrupted(*args, **kwargs):
            committed.append(submit(*args, **kwargs)[0])
            raise OSError("fixture interrupted after native acceptance")
        with patch.object(bridge, "submit", side_effect=interrupted):
            self.assertEqual(self.run_fixture(), 1)
        run = self.latest()
        state = runtime.project(runtime.read_events(run))
        self.assertEqual(state["state"], "accepted")
        self.assertEqual(state["telos_result"]["subgoal_status"], "active")
        self.assertFalse((run / "opermem-receipt.json").exists())
        bridge.submit(self.binary, self.store, self.root / "transcripts", "question", None,
            {"question_kind": "what", "text": "What changed after the original native commit?"}, "postcommit-drift")
        purpose = bridge.purpose_for(self.operation, None, **self.anchors)
        before, _ = bridge.retrieve(self.binary, self.store, self.root / "transcripts", purpose)
        pending = json.loads((run / "opermem-pending.json").read_text())
        self.assertEqual(pending["contribution"], self.contribution)
        changed = deepcopy(pending)
        changed["payload"]["expected_object_versions"].pop()
        (run / "opermem-pending.json").write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, "differs"):
            bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts")
        (run / "opermem-pending.json").write_text(json.dumps(pending))
        if self.operation == "judgment":
            changed_contribution = {**self.contribution, "rationale": "Substituted actor rationale"}
            (run / "work.md").write_text(bridge.MARKER + json.dumps(changed_contribution))
            with self.assertRaisesRegex(ValueError, "differs"):
                bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts")
            (run / "work.md").write_text(bridge.MARKER + json.dumps(self.contribution))
        with patch.object(development, "client_command") as actor, redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts"), 0)
        actor.assert_not_called()
        receipt = json.loads((run / "opermem-receipt.json").read_text())
        self.assertEqual(receipt["response"]["class"], "idempotency-replay")
        self.assertEqual(receipt["response"]["payload"]["receipt_id"], committed[0]["payload"]["receipt_id"])
        self.assertEqual(receipt["response"]["payload"]["exact_result"], committed[0]["payload"]["exact_result"])
        self.assertEqual(receipt["contribution"], self.contribution)
        after, _ = bridge.retrieve(self.binary, self.store, self.root / "transcripts", purpose)
        self.assertEqual(after, before)
        self.assertEqual(runtime.project(runtime.read_events(run))["telos_result"]["subgoal_status"], "complete")
        aggregate = telos.get_goal(self.chain, self.db, self.source)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts"), 0)
        self.assertEqual(telos.get_goal(self.chain, self.db, self.source), aggregate)

    def test_judgment_crash_replay_completes_telos_after_original_receipt(self):
        self.prepare_judgment()
        self.assert_new_operation_crash_recovery()

    def test_practical_crash_replay_completes_telos_after_original_receipt(self):
        self.prepare_practical_question()
        self.assert_new_operation_crash_recovery()

    def assert_pending_before_native_submission(self, *, drift):
        exchange = bridge.OperationHost.exchange
        def interrupted(host, kind, payload):
            if kind == bridge.KINDS[self.operation]:
                raise OSError("fixture crash after pending fsync before native submission")
            return exchange(host, kind, payload)
        with patch.object(bridge.OperationHost, "exchange", side_effect=interrupted, autospec=True):
            self.assertEqual(self.run_fixture(), 1)
        run = self.latest()
        report = (run / "work.md").read_bytes()
        self.assertTrue((run / "opermem-pending.json").exists())
        self.assertFalse((run / "opermem-receipt.json").exists())
        self.assertEqual(runtime.project(runtime.read_events(run))["telos_result"]["subgoal_status"], "active")
        if drift:
            bridge.submit(self.binary, self.store, self.root / "transcripts", "question", None,
                {"question_kind": "what", "text": "What changed before the pending command was submitted?"}, "precommit-drift")
        purpose = bridge.purpose_for(self.operation, None, **self.anchors)
        before, _ = bridge.retrieve(self.binary, self.store, self.root / "transcripts", purpose)
        pending = json.loads((run / "opermem-pending.json").read_text())
        self.assertIsNone(bridge.native_accepted_receipt(self.store, self.operation, before,
                                                      pending["payload"]["idempotency_key"]))
        if drift:
            with self.assertRaisesRegex(ValueError, "context changed"):
                bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts")
            self.assertEqual((run / "work.md").read_bytes(), report)
            self.assertFalse((run / "opermem-receipt.json").exists())
            state = runtime.project(runtime.read_events(run))
            self.assertEqual(state["state"], "accepted")
            self.assertEqual(state["telos_result"]["subgoal_status"], "active")
            after, _ = bridge.retrieve(self.binary, self.store, self.root / "transcripts", purpose)
            self.assertEqual(after, before)
        else:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts"), 0)
            receipt = json.loads((run / "opermem-receipt.json").read_text())
            self.assertEqual(receipt["response"]["class"], "success")
            self.assertEqual(runtime.project(runtime.read_events(run))["telos_result"]["subgoal_status"], "complete")

    def test_judgment_uncommitted_resume_refuses_changed_context(self):
        self.prepare_judgment()
        self.assert_pending_before_native_submission(drift=True)

    def test_practical_uncommitted_resume_refuses_changed_context(self):
        self.prepare_practical_question()
        self.assert_pending_before_native_submission(drift=True)

    def test_judgment_uncommitted_resume_accepts_unchanged_context(self):
        self.prepare_judgment()
        self.assert_pending_before_native_submission(drift=False)

    def test_practical_uncommitted_resume_accepts_unchanged_context(self):
        self.prepare_practical_question()
        self.assert_pending_before_native_submission(drift=False)

    def assert_reviewed_practical_operation(self):
        receipt = self.assert_whole_review_and_receipt()
        for role in ("inquirer", "reviewer"):
            for judgment in self.practical_judgments:
                self.assertIn(str(judgment), self.prompts[role])
            self.assertIn("An evaluation creates no decision, plan or act authority", self.prompts[role])
        run = self.latest()
        context = json.loads((run / "opermem-link.json").read_text())["context"]
        if self.operation == "practical-inquiry":
            self.assertEqual(context["context_export_version"], "opermem-trusted-context-export/v2")
            self.assertIn("supplied_whole_residues", context)
        else:
            self.assertEqual(context["context_composition_version"], "noetic-practical-context/v1")
            packets = context["native_context_packets"]
            self.assertEqual(packets[0]["operation"], self.operation)
            self.assertEqual(packets[1]["operation"], "practical-inquiry")
            self.assertEqual(packets[0]["pinned_canonical_cut"], packets[1]["pinned_canonical_cut"])
            self.assertNotIn("supplied_whole_residues", context)
        native_content = json.loads((run / "opermem-pending.json").read_text())["payload"]["body"]
        for field, value in self.contribution.items():
            self.assertEqual(native_content[field], value)
        self.assertEqual(receipt["response"]["class"], "success")

    def test_inquiry_reviewed_whole_context(self):
        self.prepare_practical_operation("practical-inquiry")
        self.assert_reviewed_practical_operation()

    def test_inquiry_review_drift_retains_pending_purpose(self):
        self.prepare_practical_operation("practical-inquiry")
        self.assert_new_operation_context_drift()

    def test_inquiry_uncommitted_drift_refusal(self):
        self.prepare_practical_operation("practical-inquiry")
        self.assert_pending_before_native_submission(drift=True)

    def test_inquiry_unchanged_precommit_retry(self):
        self.prepare_practical_operation("practical-inquiry")
        self.assert_pending_before_native_submission(drift=False)

    def test_inquiry_genuine_committed_replay(self):
        self.prepare_practical_operation("practical-inquiry")
        self.assert_new_operation_crash_recovery()

    def test_possible_course_reviewed_whole_context(self):
        self.prepare_practical_operation("practical-insight")
        self.assert_reviewed_practical_operation()

    def test_possible_course_review_drift_retains_pending_purpose(self):
        self.prepare_practical_operation("practical-insight")
        self.assert_new_operation_context_drift()

    def test_possible_course_uncommitted_drift_refusal(self):
        self.prepare_practical_operation("practical-insight")
        self.assert_pending_before_native_submission(drift=True)

    def test_possible_course_unchanged_precommit_retry(self):
        self.prepare_practical_operation("practical-insight")
        self.assert_pending_before_native_submission(drift=False)

    def test_possible_course_genuine_committed_replay(self):
        self.prepare_practical_operation("practical-insight")
        self.assert_new_operation_crash_recovery()

    def test_deliberation_reviewed_whole_context(self):
        self.prepare_practical_operation("deliberation")
        self.assert_reviewed_practical_operation()

    def test_deliberation_review_drift_retains_pending_purpose(self):
        self.prepare_practical_operation("deliberation")
        self.assert_new_operation_context_drift()

    def test_deliberation_uncommitted_drift_refusal(self):
        self.prepare_practical_operation("deliberation")
        self.assert_pending_before_native_submission(drift=True)

    def test_deliberation_unchanged_precommit_retry(self):
        self.prepare_practical_operation("deliberation")
        self.assert_pending_before_native_submission(drift=False)

    def test_deliberation_genuine_committed_replay(self):
        self.prepare_practical_operation("deliberation")
        self.assert_new_operation_crash_recovery()


    def prepare_decision_planning(self, operation, *, supersession=False):
        from tests.programs.opermem_decision_fixture import evaluation, decision, choice, steps
        from tests.programs.opermem_practical_fixture import deliberation
        evaluated, question, basis, options, _ = evaluation(self.binary, self.store, self.root / "transcripts", self.root / "decision-checking")
        self.operation, self.parent = operation, None
        self.decision_basis = basis
        self.anchors = {"judgment_basis_ids": basis}
        if operation == "decision":
            self.anchors["evaluation_id"] = evaluated
            self.contribution = choice(options)
            if supersession:
                predecessor, _, _ = decision(self.binary, self.store, self.root / "transcripts", evaluated, basis, options)
                response, _ = bridge.submit(self.binary, self.store, self.root / "transcripts", "deliberation", None,
                    deliberation(), "reviewed-renewal", practical_question_id=question, option_ids=options)
                self.anchors.update(evaluation_id=next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "evaluation"),
                                    supersedes_decision_id=predecessor)
        else:
            identity, self.issued_intention, _ = decision(self.binary, self.store, self.root / "transcripts", evaluated, basis, options)
            self.anchors["decision_id"] = identity
            self.contribution = steps()

    def assert_reviewed_decision_planning(self):
        self.assert_whole_review_and_receipt()
        for role in ("inquirer", "reviewer"):
            self.assertIn("grants no external act permission", self.prompts[role])
            self.assertIn('"selected_option_id":123' if self.operation == "decision" else '"steps":[{"position":1', self.prompts[role])
            for judgment in self.decision_basis:
                self.assertIn(str(judgment), self.prompts[role])
        run = self.latest()
        link = json.loads((run / "opermem-link.json").read_text())
        self.assertEqual(link["context"]["context_export_version"], "opermem-trusted-context-export/v2")
        self.assertNotIn("native_context_packets", link["context"])
        native_content = json.loads((run / "opermem-pending.json").read_text())["payload"]["body"]
        for field, value in self.contribution.items():
            self.assertEqual(native_content[field], value)
        if self.operation == "planning":
            self.assertEqual(native_content["intention_id"], self.issued_intention)

    def test_decision_reviewed_whole_context(self):
        self.prepare_decision_planning("decision")
        self.assert_reviewed_decision_planning()

    def test_decision_review_drift_preserves_task_and_purpose(self):
        self.prepare_decision_planning("decision")
        self.assert_new_operation_context_drift()

    def test_decision_uncommitted_drift_refusal(self):
        self.prepare_decision_planning("decision")
        self.assert_pending_before_native_submission(drift=True)

    def test_decision_unchanged_precommit_retry(self):
        self.prepare_decision_planning("decision")
        self.assert_pending_before_native_submission(drift=False)

    def test_decision_genuine_committed_replay(self):
        self.prepare_decision_planning("decision")
        self.assert_new_operation_crash_recovery()

    def test_planning_reviewed_whole_context(self):
        self.prepare_decision_planning("planning")
        self.assert_reviewed_decision_planning()

    def test_planning_review_drift_preserves_task_and_purpose(self):
        self.prepare_decision_planning("planning")
        self.assert_new_operation_context_drift()

    def test_planning_uncommitted_drift_refusal(self):
        self.prepare_decision_planning("planning")
        self.assert_pending_before_native_submission(drift=True)

    def test_planning_unchanged_precommit_retry(self):
        self.prepare_decision_planning("planning")
        self.assert_pending_before_native_submission(drift=False)

    def test_planning_genuine_committed_replay(self):
        self.prepare_decision_planning("planning")
        self.assert_new_operation_crash_recovery()

    def test_supersession_committed_replay_survives_unavailable_predecessor_export(self):
        self.prepare_decision_planning("decision", supersession=True)
        submit, committed = bridge.submit, []
        def interrupted(*args, **kwargs):
            committed.append(submit(*args, **kwargs)[0])
            raise OSError("fixture crash after genuine native supersession")
        with patch.object(bridge, "submit", side_effect=interrupted):
            self.assertEqual(self.run_fixture(), 1)
        run = self.latest()
        self.assertFalse((run / "opermem-receipt.json").exists())
        self.assertEqual(runtime.project(runtime.read_events(run))["telos_result"]["subgoal_status"], "active")
        with self.assertRaises(RuntimeError):
            bridge.retrieve(self.binary, self.store, self.root / "transcripts", bridge.purpose_for("decision", None, **self.anchors))
        bridge.submit(self.binary, self.store, self.root / "transcripts", "question", None,
            {"question_kind": "what", "text": "What changed after supersession committed?"}, "supersession-drift")
        successor = next(x["id"] for x in committed[0]["payload"]["outputs"] if x["kind"] == "decision")
        purpose = bridge.purpose_for("planning", None, decision_id=successor, judgment_basis_ids=self.decision_basis)
        before, _ = bridge.retrieve(self.binary, self.store, self.root / "transcripts", purpose)
        with patch.object(development, "client_command") as actor, redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts"), 0)
        actor.assert_not_called()
        receipt = json.loads((run / "opermem-receipt.json").read_text())
        self.assertEqual(receipt["response"]["class"], "idempotency-replay")
        for field in ("receipt_id", "exact_result"):
            self.assertEqual(receipt["response"]["payload"][field], committed[0]["payload"][field])
        self.assertEqual(runtime.project(runtime.read_events(run))["telos_result"]["subgoal_status"], "complete")
        self.assertEqual(bridge.retrieve(self.binary, self.store, self.root / "transcripts", purpose)[0], before)
        aggregate = telos.get_goal(self.chain, self.db, self.source)
        with patch.object(bridge, "OperationHost") as host, redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts"), 0)
        host.assert_not_called()
        self.assertEqual(telos.get_goal(self.chain, self.db, self.source), aggregate)

    def test_supersession_uncommitted_unavailable_context_never_grants_replay(self):
        self.prepare_decision_planning("decision", supersession=True)
        exchange = bridge.OperationHost.exchange
        def interrupted(host, kind, payload):
            if kind == "decide":
                raise OSError("fixture crash before native supersession")
            return exchange(host, kind, payload)
        with patch.object(bridge.OperationHost, "exchange", side_effect=interrupted, autospec=True):
            self.assertEqual(self.run_fixture(), 1)
        run = self.latest()
        report = (run / "work.md").read_bytes()
        pending = json.loads((run / "opermem-pending.json").read_text())
        external, _ = bridge.submit(self.binary, self.store, self.root / "transcripts", "decision", None,
            self.contribution, "independent-supersession", **self.anchors)
        successor = next(x["id"] for x in external["payload"]["outputs"] if x["kind"] == "decision")
        purpose = bridge.purpose_for("planning", None, decision_id=successor, judgment_basis_ids=self.decision_basis)
        before, _ = bridge.retrieve(self.binary, self.store, self.root / "transcripts", purpose)
        self.assertIsNone(bridge.native_accepted_receipt(self.store, "decision", before, pending["payload"]["idempotency_key"]))
        with patch.object(development, "client_command") as actor, self.assertRaises(RuntimeError):
            bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts")
        actor.assert_not_called()
        self.assertFalse((run / "opermem-receipt.json").exists())
        self.assertEqual((run / "work.md").read_bytes(), report)
        self.assertEqual(runtime.project(runtime.read_events(run))["telos_result"]["subgoal_status"], "active")
        self.assertEqual(bridge.retrieve(self.binary, self.store, self.root / "transcripts", purpose)[0], before)

    def prepare_acting(self, *, failed=False, verify_failed=False):
        from tests.programs.opermem_acting_fixture import native_plan, external_work, prose
        self.plan, self.step, self.chosen_decision, self.acting_basis, self.practical_question, self.acting_options = native_plan(
            self.binary, self.store, self.root / "transcripts", self.root / "acting-native")
        self.observed_run = external_work(self.root, failed=failed, verify_failed=verify_failed)
        self.observed_failed = failed
        self.operation, self.parent = "acting", None
        self.anchors = {"plan_id": self.plan, "step_id": self.step}
        self.contribution = prose(failed=failed, verify_failed=verify_failed)

    def assert_reviewed_acting(self):
        self.assertEqual(self.run_fixture(), 0)
        run = self.latest()
        link = json.loads((run / "opermem-link.json").read_text())
        binding = json.loads((run / "observation-binding.json").read_text())
        self.assertEqual(binding["observing_run_id"], run.name)
        self.assertEqual(binding["manifest_sha256"], link["observation_manifest_sha256"])
        self.assertEqual(link["observation_evidence_mode"], "archival")
        self.assertEqual(link["observation_source_run"], str(self.observed_run))
        self.assertEqual(link["context"]["context_export_version"], "opermem-trusted-context-export/v2")
        frozen = json.dumps(link["context"], ensure_ascii=False, sort_keys=True)
        for role in ("inquirer", "reviewer"):
            self.assertIn(frozen, self.prompts[role])
            self.assertIn("read-only observer", self.prompts[role])
            self.assertIn("asserted retrospectively", self.prompts[role])
            self.assertIn('"observed_act":"..."', self.prompts[role])
            self.assertIn(link["observation_manifest_sha256"], self.prompts[role])
        receipt = json.loads((run / "opermem-receipt.json").read_text())
        self.assertEqual({k:v for k,v in receipt["contribution"].items() if k != "observation"}, self.contribution)
        self.assertEqual(receipt["contribution"]["observation"], {"manifest_sha256": link["observation_manifest_sha256"],
                                                                 "finish_sequence": link["observation_selected"]["finish_sequence"]})
        pending = json.loads((run / "opermem-pending.json").read_text())
        self.assertNotIn("observation", pending["payload"]["body"])
        self.assertEqual(runtime.project(runtime.read_events(run))["telos_result"]["subgoal_status"], "complete")
        self.assertEqual(telos.get_goal(self.chain, self.db, self.source)["chain"]["status"], "active")
        return run, receipt

    def test_acting_success_separate_observer_whole_evidence_and_review(self):
        self.prepare_acting()
        self.assert_reviewed_acting()

    def test_acting_failed_and_deviated_occurrence_can_be_reviewed_and_deposited(self):
        self.prepare_acting(failed=True)
        _, receipt = self.assert_reviewed_acting()
        self.assertEqual(len(receipt["response"]["payload"]["outputs"]), 4)

    def test_acting_failed_original_verification_is_preserved_without_excluding_observation(self):
        self.prepare_acting(verify_failed=True)
        run, _ = self.assert_reviewed_acting()
        manifest = json.loads((run / "observation-evidence/manifest.json").read_text())
        self.assertEqual(manifest["run"]["state"], "failed")
        self.assertEqual(manifest["selected"]["state"], "passed")
        events = json.loads((run / "observation-evidence/events.json").read_text())
        self.assertTrue(any(row["kind"] == "step.finished" and json.loads(row["data_json"]).get("step") == "verify"
                            and json.loads(row["data_json"]).get("returncode") == 9 for row in events))

    def test_acting_review_drift_preserves_observation_and_pending_purpose(self):
        self.prepare_acting()
        self.assert_new_operation_context_drift()

    def test_acting_uncommitted_drift_refusal(self):
        self.prepare_acting()
        self.assert_pending_before_native_submission(drift=True)

    def test_acting_unchanged_precommit_retry_uses_archive_after_original_source_vanishes(self):
        self.prepare_acting()
        exchange = bridge.OperationHost.exchange
        def interrupted(host, kind, payload):
            if kind == "observe-act":
                raise OSError("crash before native act observation")
            return exchange(host, kind, payload)
        with patch.object(bridge.OperationHost, "exchange", side_effect=interrupted, autospec=True):
            self.assertEqual(self.run_fixture(), 1)
        run = self.latest()
        shutil.rmtree(self.observed_run)
        with patch.object(runtime, "execute_step") as execute, patch.object(development, "client_command") as actor, redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts"), 0)
        execute.assert_not_called();actor.assert_not_called()
        self.assertEqual(json.loads((run / "opermem-receipt.json").read_text())["response"]["class"], "success")

    def test_acting_committed_replay_after_drift_uses_original_receipt_and_archive_once(self):
        self.prepare_acting(failed=True)
        submit, committed = bridge.submit, []
        def interrupted(*args, **kwargs):
            committed.append(submit(*args, **kwargs)[0])
            raise OSError("crash after genuine native act observation")
        with patch.object(bridge, "submit", side_effect=interrupted):
            self.assertEqual(self.run_fixture(), 1)
        run = self.latest()
        self.assertFalse((run / "opermem-receipt.json").exists())
        self.assertEqual(runtime.project(runtime.read_events(run))["telos_result"]["subgoal_status"], "active")
        pending = json.loads((run / "opermem-pending.json").read_text())
        changed = deepcopy(pending);changed["contribution"]["observation"]["finish_sequence"] += 1
        (run / "opermem-pending.json").write_text(json.dumps(changed))
        with patch.object(bridge, "OperationHost") as host, self.assertRaisesRegex(ValueError, "differs"):
            bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts")
        host.assert_not_called()
        (run / "opermem-pending.json").write_text(json.dumps(pending))
        bridge.submit(self.binary, self.store, self.root / "transcripts", "question", None,
            {"question_kind": "what", "text": "What changed after act observation?"}, "acting-postcommit-drift")
        purpose = bridge.purpose_for("acting", None, **self.anchors)
        before, _ = bridge.retrieve(self.binary, self.store, self.root / "transcripts", purpose)
        shutil.rmtree(self.observed_run)
        with patch.object(runtime, "execute_step") as execute, patch.object(development, "client_command") as actor, redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts"), 0)
        execute.assert_not_called();actor.assert_not_called()
        receipt = json.loads((run / "opermem-receipt.json").read_text())
        self.assertEqual(receipt["response"]["class"], "idempotency-replay")
        for field in ("receipt_id", "exact_result"):
            self.assertEqual(receipt["response"]["payload"][field], committed[0]["payload"][field])
        self.assertEqual(bridge.retrieve(self.binary, self.store, self.root / "transcripts", purpose)[0], before)
        aggregate = telos.get_goal(self.chain, self.db, self.source)
        with patch.object(bridge, "OperationHost") as host, patch.object(runtime, "execute_step") as execute, redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts"), 0)
        host.assert_not_called();execute.assert_not_called()
        self.assertEqual(telos.get_goal(self.chain, self.db, self.source), aggregate)

    def test_acting_fresh_observer_accepts_frozen_archive_with_no_original_source(self):
        from scripts import noetic_act_observation as evidence
        self.prepare_acting()
        archive = self.root / "preexisting-archive"
        evidence.capture(self.observed_run, archive)
        self.archived_input = archive, evidence.digest((archive / "manifest.json").read_bytes())
        shutil.rmtree(self.observed_run)
        self.assert_reviewed_acting()

    def test_acting_archive_substitution_during_review_preserves_report_and_active_purpose(self):
        self.prepare_acting()
        def substituting(*args, **kwargs):
            result = self.client(*args, **kwargs)
            if args[2] == "reviewer":
                archive = Path(kwargs.get("context_dirs", args[6] if len(args) > 6 else ()) [0])
                (archive / "work.stdout.log").write_bytes(b"substituted source evidence")
            return result
        with patch.object(development, "client_command", side_effect=substituting), redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.main(self.args()), 1)
        run = self.latest()
        self.assertTrue((run / "work.md").is_file())
        self.assertTrue((run / "observation-binding.json").is_file())
        self.assertFalse((run / "opermem-receipt.json").exists())
        self.assertEqual(runtime.project(runtime.read_events(run))["telos_result"]["subgoal_status"], "active")

    def test_reviewed_question_recurrence_is_bound_to_actual_native_outcome_and_replays(self):
        self.prepare_acting()
        _, receipt = self.assert_reviewed_acting()
        outcome = next(x["id"] for x in receipt["response"]["payload"]["outputs"] if x["kind"] == "outcome-as-experience")
        self.operation, self.parent = "question", None
        self.anchors = {"occasion_kind": "outcome-as-experience", "occasion_id": outcome}
        self.contribution = {"question_kind": "what", "text": "What is learned from this actual comparison outcome?"}
        submit, committed = bridge.submit, []
        def interrupted(*args, **kwargs):
            committed.append(submit(*args, **kwargs)[0])
            raise OSError("crash after recurrent question native acceptance")
        with patch.object(bridge, "submit", side_effect=interrupted):
            self.assertEqual(self.run_fixture(), 1)
        run = self.latest()
        link = json.loads((run / "opermem-link.json").read_text())
        self.assertEqual(link["occasion_id"], outcome)
        self.assertEqual(link["occasion_kind"], "outcome-as-experience")
        pending = json.loads((run / "opermem-pending.json").read_text())
        self.assertEqual(pending["payload"]["body"]["occasion_id"], outcome)
        self.assertEqual(pending["payload"]["expected_object_versions"][0]["kind"], "outcome-as-experience")
        with patch.object(runtime, "execute_step") as execute, patch.object(development, "client_command") as actor, redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.runs / ".opermem-transcripts"), 0)
        execute.assert_not_called();actor.assert_not_called()
        replay = json.loads((run / "opermem-receipt.json").read_text())["response"]
        self.assertEqual(replay["class"], "idempotency-replay")
        self.assertEqual(replay["payload"]["receipt_id"], committed[0]["payload"]["receipt_id"])


if __name__ == "__main__":
    unittest.main()
