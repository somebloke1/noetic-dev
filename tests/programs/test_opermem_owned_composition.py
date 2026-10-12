"""Isolated real Rust/Telos boundaries; disposable client streams are protocol fixtures."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import noetic_develop as develop, noetic_opermem as bridge, noetic_run as runtime
from scripts import noetic_recall as recall, noetic_purpose_binding as purposes
from scripts.noetic_scope import Scope, ScopeStore
from scripts.noetic_opermem_scope import OpermemScope
from scripts.noetic_purposes import Purposes


@unittest.skipUnless(os.environ.get("OPERMEM_OPERATION_HOST") and os.environ.get("NOETIC_TEST_TELOS_SOURCE"), "requires frozen actual Rust and isolated Telos fixture source")
class OwnedCompositionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="owned-composition-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cwd = self.root / "same-workspace"
        self.cwd.mkdir()
        self.runs = self.root / "runs"
        self.namespace = self.root / "namespace/ordinals.sqlite3"
        self.binary = Path(os.environ["OPERMEM_OPERATION_HOST"]).resolve(strict=True)
        self.source = self.root / "telos.mjs"
        shutil.copyfile(os.environ["NOETIC_TEST_TELOS_SOURCE"], self.source)
        self.canonical = ScopeStore(self.namespace, root_mandate={"purpose": "fixture root"}, human_ref={"fixture": "human"}, source_ref={"fixture": "root"})
        self.adapter = OpermemScope(self.namespace)
        self.purposes = Purposes(self.namespace, purposes_root=self.root / "purposes", source=self.source)
        self.config = purposes.configuration(self.purposes)
        self.efforts, self.instances, self.stores, self.refs = [], [], [], []
        for name in ("A", "B", "R"):
            root = self.canonical.create_effort(intent=name, environment={"cwd": str(self.cwd)}, mandate={"purpose": name}, origin="human", human_ref={"fixture": "human"}, source_ref={"fixture": name})["ordinal"]
            self.efforts.append(root)
            self.instances.append(self.adapter.create_instance(command_id=name, effort_root=root, initiator=root, intent=name, environment={"cwd": str(self.cwd)}, origin="human", human_ref={"fixture": "human"}))
            self.stores.append(self.adapter.bind_store(command_id=name, effort_root=root, store_path=self.root / (name + "-native"), host=self.binary))
            self.refs.append(self.purposes.create(name + " real purpose", scope=Scope.effort(root), origin_ref={"fixture": "human"}, source_ref={"fixture": name})["reference"])
        self.task = self.cwd / "task.md"
        self.task.write_text("Inspect the explicitly selected host evidence.")
        self.calls = []
        self.operation = "question"
        self.value = {"question_kind": "how", "text": "What follows from the selected host evidence?"}
        self.failure = None
        self.before_review = None

    def request(self, index=0):
        return {"namespace_path": str(self.namespace), "effort_root": self.efforts[index], "discipline_id": self.instances[index]["id"], "environment": {"cwd": str(self.cwd)}, "origin": "human", "human_ref": {"fixture": "human"}}

    def write(self, name, value):
        path = self.root / (name + ".json")
        path.write_text(json.dumps(value))
        return str(path)

    def args(self, index=0, extra=()):
        return ["--host", str(self.binary), "--store", self.stores[index]["directory"], "--runs-dir", str(self.runs), "run", str(self.task), "--workspace", str(self.cwd), "--operation", self.operation, "--inquiry", "--client", "opencode", "--scope-request", self.write("request", self.request(index)), "--store-ref", self.write("store", self.stores[index]), "--purpose-ref", self.write("purpose", self.refs[index]), "--purpose-config", self.write("config", self.config), *extra]

    def client(self, client, prompt, role, model, run_dir=None, workspace=None, context_dirs=()):
        if run_dir is None:
            prepared = [p for root in self.efforts for p in self.adapter.inspect_preparations(effort_root=root) if p.get("run_status") == "prepared"]
            self.assertEqual(len(prepared), 1)
            run_dir = self.runs / prepared[0]["run_id"]
        run_dir = Path(run_dir)
        self.calls.append((run_dir.name, role))
        if role == "reviewer":
            self.assertIsNotNone(bridge.owned_run(run_dir, revalidate_purpose=True))
        if role == "reviewer" and self.before_review:
            self.before_review(run_dir)
        text = bridge.MARKER + json.dumps(self.value) if role != "reviewer" else "ACCEPT\nFixture reviewer compared retained evidence."
        session = "fixture-" + run_dir.name + "-" + role
        events = [{"type": "text", "sessionID": session, "part": {"id": "text", "messageID": "final", "text": text}}, {"type": "step_finish", "sessionID": session, "part": {"messageID": "final", "reason": "stop"}}]
        check = "import sys,json;from pathlib import Path;p=sys.stdin.read();assert 'responsibility' in p;link=json.loads(Path(" + repr(str(run_dir / "opermem-link.json")) + ").read_text());assert link['owned_execution']['execution_id'];"
        code = check + "print(" + repr("\n".join(json.dumps(e) for e in events)) + ")"
        if role != "reviewer" and self.failure == "header":
            code = check + "print(" + repr(json.dumps(events[0])) + "); sys.exit(2)"
        elif role != "reviewer" and self.failure == "no-header":
            code = check + "sys.exit(2)"
        return [sys.executable, "-c", code], None

    def run_owned(self, index=0, extra=()):
        with patch.object(develop, "client_command", side_effect=self.client), redirect_stdout(io.StringIO()):
            result = bridge.main(self.args(index, extra))
        # UUID lexical order does not imply execution order.
        preparations = self.adapter.inspect_preparations(effort_root=self.efforts[index])
        run = self.runs / preparations[-1]["run_id"]
        return result, run

    def recalled(self, kind, **kwargs):
        return recall.collect(namespace_path=self.namespace, sessions_home=self.root / "sessions", runs_dir=self.runs, selection={"kind": kind, **kwargs})

    def resume(self, run):
        with redirect_stdout(io.StringIO()), patch.object(develop, "client_command", side_effect=AssertionError("actor recovery forbidden")):
            return bridge.resume_run(run, self.binary, Path(json.loads((run / "opermem-link.json").read_text())["store"]), self.runs / ".opermem-transcripts")

    def test_a_b_r_actual_store_identity_and_exact_actor_recall(self):
        runs = []
        for index in range(3):
            result, run = self.run_owned(index, ("--source", str(self.task)))
            self.assertEqual(result, 0)
            runs.append(run)
            observed = bridge.owned_correspondence(run)
            self.assertEqual(observed["native_store_identity"]["workspace_id"], 1)
            self.assertEqual(observed["native_store_identity"]["authority_scope_id"], 1)
            self.assertEqual(len(observed["participants"]), 2)
            self.assertFalse(observed["host_sources"][0]["native_retained_experience"])
        self.assertEqual(len({bridge.owned_correspondence(run)["native_store_identity"]["directory"] for run in runs}), 3)
        observed = bridge.owned_correspondence(runs[0])
        target = observed["participants"][0]["target"]
        exact = self.recalled("session", ordinal=target["ordinal"], instantiation=target["instantiation"], session=target["session"])
        actors = [s for s in exact["sources"] if s["field"] == "opermem-actor"]
        self.assertEqual(len(actors), 1)
        self.assertIn(bridge.MARKER, actors[0]["text"])
        self.assertFalse(any(s["field"] in ("native-context", "host-source-occasion") for s in exact["sources"]))
        self.assertNotIn("Fixture reviewer", "\n".join(s["text"] for s in exact["sources"]))
        effort = self.recalled("effort", effort_root=self.efforts[0])
        packets = [s for s in effort["sources"] if s["field"] == "native-context"]
        self.assertEqual(len(packets), 1)
        self.assertEqual(json.loads(packets[0]["text"]), observed["native_link"]["context"])
        self.assertTrue(all(s.get("run_id") not in {r.name for r in runs[1:]} for s in effort["sources"]))
        self.assertFalse((runs[0] / "controller.sqlite3").exists())

    def test_wrong_scope_purpose_store_refuses_before_native_or_mkdir(self):
        mutations = [{"effort_root": self.efforts[1]}, {"discipline_id": 999}, {"environment": {"cwd": str(self.root)}}, {"human_ref": None}]
        for changed in mutations:
            args = self.args()
            args[args.index("--scope-request") + 1] = self.write("bad-request", {**self.request(), **changed})
            with self.subTest(changed=changed), patch.object(bridge, "retrieve", side_effect=AssertionError("native effect")), self.assertRaises((ValueError, KeyError)), redirect_stdout(io.StringIO()):
                bridge.main(args)
        for field, value in (("--purpose-ref", self.refs[1]), ("--store-ref", self.stores[1]), ("--purpose-config", {**self.config, "namespace_path": str(self.root / "wrong")})):
            args = self.args()
            args[args.index(field) + 1] = self.write("bad-input", value)
            with self.subTest(field=field), patch.object(bridge, "retrieve", side_effect=AssertionError("native effect")), self.assertRaises(ValueError), redirect_stdout(io.StringIO()):
                bridge.main(args)
        for field, value in (("--workspace", self.root), ("--store", self.root / "wrong-store"), ("--host", Path(sys.executable))):
            args = self.args()
            args[args.index(field) + 1] = str(value)
            with self.subTest(field=field), patch.object(bridge, "retrieve", side_effect=AssertionError("native effect")), self.assertRaises(ValueError), redirect_stdout(io.StringIO()):
                bridge.main(args)
        self.assertFalse(self.runs.exists())
        self.assertTrue(all(not Path(s["directory"]).exists() for s in self.stores))
        self.assertEqual(self.adapter.inspect_preparations(effort_root=self.efforts[0]), [])

    def test_actor_failure_retains_truthful_native_session_and_failed_preparation(self):
        for failure in ("header", "no-header"):
            self.failure = failure
            status, run = self.run_owned()
            self.assertEqual(status, 1)
            observed = bridge.owned_correspondence(run)
            self.assertEqual(len(observed["participants"]), 1)
            self.assertEqual(observed["participants"][0]["target"] is not None, failure == "header")
            self.assertFalse((run / "opermem-receipt.json").exists())
        bad_host = self.root / "not-executable-host"
        bad_host.write_bytes(b"actual unexecutable fixture")
        foreign = self.adapter.bind_store(command_id="startup", effort_root=self.efforts[0], store_path=self.root / "startup-store", host=bad_host)
        args = self.args()
        args[args.index("--host") + 1] = str(bad_host)
        args[args.index("--store") + 1] = foreign["directory"]
        args[args.index("--store-ref") + 1] = self.write("startup-ref", foreign)
        with self.assertRaises(PermissionError), redirect_stdout(io.StringIO()):
            bridge.main(args)
        prepared = self.adapter.inspect_preparations(effort_root=self.efforts[0])[-1]
        self.assertEqual(prepared["run_status"], "preparation-failed")
        self.assertEqual(prepared["participants"], [])
        self.assertFalse((self.runs / prepared["run_id"]).exists())
        before = self.namespace.read_bytes()
        result = self.recalled("effort", effort_root=self.efforts[0])
        self.assertTrue(any(s["field"] == "preparation-observation" for s in result["sources"]))
        self.assertEqual(self.namespace.read_bytes(), before)

    def test_receipt_only_sync_source_restoration_and_corruption_gates(self):
        status, run = self.run_owned()
        self.assertEqual(status, 0)
        binding = bridge.owned_run(run)[1]
        cache = self.namespace.with_name(self.namespace.name + ".correlation.sqlite3")
        cache.unlink()
        calls = list(self.calls)
        with patch.object(bridge, "OperationHost", side_effect=AssertionError("receipt-only native command forbidden")):
            self.assertEqual(self.resume(run), 0)
        self.assertEqual(self.calls, calls)
        original_source = self.source.read_bytes()
        self.source.unlink()
        try:
            with self.assertRaises(ValueError), patch.object(bridge, "OperationHost", side_effect=AssertionError("native forbidden")):
                self.resume(run)
            self.assertEqual(bridge.owned_correspondence(run)["purpose_ref"], self.refs[0])
        finally:
            self.source.write_bytes(original_source)
        with sqlite3.connect(self.refs[0]["db_path"]) as db:
            db.execute("UPDATE chains SET primary_goal=? WHERE chain_id=?", ("mutable updated purpose", self.refs[0]["chain_id"]))
        self.assertEqual(self.resume(run), 0)
        link_path = run / "opermem-link.json"
        original = link_path.read_bytes()
        bad = json.loads(original)
        bad["store"] = self.stores[1]["directory"]
        link_path.write_text(json.dumps(bad))
        with self.assertRaisesRegex(ValueError, "canonical correspondence"), patch.object(bridge, "OperationHost", side_effect=AssertionError("native forbidden")):
            self.resume(run)
        collected = self.recalled("application")
        self.assertTrue(any(d["component"] == "legacy-run" and d["path"] == str(run) for d in collected["diagnostics"]))
        self.assertFalse(any(s.get("field") == "legacy-run" and s.get("run_id") == run.name for s in collected["sources"]))
        link_path.write_bytes(original)
        receipt_path = run / "opermem-receipt.json"
        original_receipt = receipt_path.read_bytes()
        malformed = json.loads(original_receipt)
        malformed["response"]["payload"]["receipt_id"] += 1
        receipt_path.write_text(json.dumps(malformed))
        with self.assertRaisesRegex(ValueError, "original owned native receipt"), patch.object(bridge, "OperationHost", side_effect=AssertionError("native forbidden")):
            self.resume(run)
        receipt_path.write_bytes(original_receipt)
        work = run / "work.md"
        actual = work.read_bytes()
        work.write_text("forged actor report")
        with self.assertRaisesRegex(ValueError, "Actor report"), patch.object(bridge, "OperationHost", side_effect=AssertionError("native forbidden")):
            self.resume(run)
        work.write_bytes(actual)
        self.assertEqual(len(self.adapter.correspondence(binding)["participants"]), 2)

    def test_committed_question_replay_after_drift_and_receipt_deletion(self):
        original_write = Path.write_text
        def fail_receipt(path, *args, **kwargs):
            if path.name == "opermem-receipt.json":
                raise OSError("fixture interruption after real native commit")
            return original_write(path, *args, **kwargs)
        with patch.object(Path, "write_text", fail_receipt), self.assertRaises(OSError):
            self.run_owned()
        prepared = self.adapter.inspect_preparations(effort_root=self.efforts[0])[-1]
        run = self.runs / prepared["run_id"]
        self.assertTrue((run / "opermem-pending.json").exists())
        bridge.submit(self.binary, Path(self.stores[0]["directory"]), self.root / "drift", "question", None, {"question_kind": "what", "text": "Unrelated drift."}, "fixture-drift")
        self.assertEqual(self.resume(run), 0)
        receipt = json.loads((run / "opermem-receipt.json").read_text())
        self.assertEqual(receipt["response"]["class"], "idempotency-replay")
        (run / "opermem-receipt.json").unlink()
        self.assertEqual(self.resume(run), 0)
        self.assertEqual(json.loads((run / "opermem-receipt.json").read_text())["response"]["payload"], receipt["response"]["payload"])

    def test_owned_acting_and_outcome_recurrence_never_reexecute_external_act(self):
        from tests.programs import opermem_acting_fixture as fixture
        store = Path(self.stores[0]["directory"])
        plan, step, _, _, _, _ = fixture.native_plan(self.binary, store, self.root / "native-plan-transcripts", self.root / "native-plan")
        external = fixture.external_work(self.root, failed=True)
        before = (external / "events.sqlite3").read_bytes()
        self.operation, self.value = "acting", fixture.prose(failed=True)
        status, run = self.run_owned(extra=("--plan-id", str(plan), "--step-id", str(step), "--observed-run", str(external)))
        self.assertEqual(status, 0)
        self.assertEqual((external / "events.sqlite3").read_bytes(), before)
        receipt = json.loads((run / "opermem-receipt.json").read_text())
        outcome = next(x["id"] for x in receipt["response"]["payload"]["outputs"] if x["kind"] == "outcome-as-experience")
        shutil.rmtree(external)
        (run / "opermem-receipt.json").unlink()
        bridge.submit(self.binary, store, self.root / "drift", "question", None, {"question_kind": "what", "text": "Drift after actual observation."}, "acting-drift")
        self.assertEqual(self.resume(run), 0)
        self.operation, self.value = "question", {"question_kind": "how", "text": "What follows from the actual failed occurrence?"}
        status, recurrence = self.run_owned(extra=("--occasion-kind", "outcome-as-experience", "--occasion-id", str(outcome)))
        self.assertEqual(status, 0)
        correlated = bridge.owned_correspondence(recurrence)
        self.assertEqual(correlated["occasion_selection"], {"kind": "outcome-as-experience", "id": outcome})
        self.assertTrue(any(item["kind"] == "outcome-as-experience" for item in correlated["native_link"]["context"]["supplied_whole_residues"]))

    def test_prepared_callback_exactly_once_and_failure_before_native_effects(self):
        original = bridge.run_task
        observed = []
        def fail(binding):
            observed.append(deepcopy(binding))
            self.assertEqual(json.loads(Path(binding["preparation_path"]).read_text()), binding)
            self.assertFalse(Path(binding["run_dir"]).exists())
            raise RuntimeError("fixture prepared observer unavailable")
        with patch.object(bridge, "run_task", side_effect=lambda args: original(args, on_prepared=fail)), patch.object(bridge, "retrieve", side_effect=AssertionError("native effect")), self.assertRaisesRegex(RuntimeError, "observer unavailable"), redirect_stdout(io.StringIO()):
            bridge.main(self.args())
        self.assertEqual(len(observed), 1)
        inspected = self.adapter.inspect_preparations(effort_root=self.efforts[0])
        self.assertEqual(len(inspected), 1)
        self.assertEqual(inspected[0]["run_status"], "preparation-failed")
        self.assertEqual(inspected[0]["execution_id"], observed[0]["execution_id"])
        self.assertFalse(Path(self.stores[0]["directory"]).exists())
        observed.clear()
        with patch.object(bridge, "run_task", side_effect=lambda args: original(args, on_prepared=lambda binding: observed.append(binding))):
            status, run = self.run_owned()
        self.assertEqual(status, 0)
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0], bridge.owned_run(run)[1])

    def test_owned_checking_reservation_precedes_actual_command_and_review(self):
        from tests.programs.test_noetic_opermem_checking import CheckingCaptureTests
        parent = None
        for operation, contribution, role in [
            ("question", {"question_kind": "how", "text": "How is checking bounded?"}, "question"),
            ("insight", {"text": "Fixture unchecked trace."}, "unverified insight trace"),
            ("formulation", {"text": "Fixture unchecked hypothesis."}, "versioned formulation/hypothesis"),
            ("reflection", {"text": "Is the fixture hypothesis correct?"}, "reflection question")]:
            response, _ = bridge.submit(self.binary, Path(self.stores[0]["directory"]), self.root / "checking-native", operation, parent, contribution, "owned-checking-" + operation)
            parent = next(x["id"] for x in response["payload"]["outputs"] if x["role"] == role)
            if operation == "formulation":
                formulation = parent
        response, _ = bridge.submit(self.binary, Path(self.stores[0]["directory"]), self.root / "checking-native", "conditional-structure", parent, {"conditions": ["Exact owned command observation"]}, "owned-warrant", formulation_id=formulation)
        warrant = next(x["id"] for x in response["payload"]["outputs"] if x["role"] == "warrant")
        condition = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "warrant-condition")
        self.context_ids = (condition, warrant)
        self.context, _ = bridge.retrieve(self.binary, Path(self.stores[0]["directory"]), self.root / "checking-native", bridge.purpose_for("checking", condition, warrant_id=warrant))
        body = "from pathlib import Path; assert len(list(Path(" + repr(str(self.runs / ".opermem-preparations")) + ").glob('*/binding.json'))) == 1; Path(" + repr(str(self.root / "command-once")) + ").write_text('actual checking command')"
        spec = CheckingCaptureTests.specification(self, body)
        self.operation = "checking"
        status, run = self.run_owned(extra=("--parent-id", str(condition), "--warrant-id", str(warrant), "--checking-spec", str(spec)))
        self.assertEqual(status, 0)
        self.assertEqual((self.root / "command-once").read_text(), "actual checking command")
        self.assertTrue((run / "checking-evidence/manifest.json").is_file())
        self.assertEqual(len(bridge.owned_correspondence(run)["participants"]), 2)
        with patch.object(bridge.noetic_opermem_checking, "capture", side_effect=AssertionError("checking reexecution forbidden")), patch.object(bridge, "OperationHost", side_effect=AssertionError("receipt-only native forbidden")):
            self.assertEqual(self.resume(run), 0)

    def test_review_purpose_loss_blocks_deposit_and_restoration_recovers_without_actors(self):
        original = self.source.read_bytes()
        self.before_review = lambda run: self.source.unlink()
        try:
            status, run = self.run_owned()
            self.assertEqual(status, 1)
            self.assertEqual(runtime.project(runtime.read_events(run))["state"], "accepted")
            self.assertFalse((run / "opermem-pending.json").exists())
            self.assertFalse((run / "opermem-receipt.json").exists())
        finally:
            self.source.write_bytes(original)
        calls = list(self.calls)
        self.assertEqual(self.resume(run), 0)
        self.assertEqual(self.calls, calls)

    def test_explicit_instance_store_commands_and_real_agent_mandate(self):
        request = {"namespace_path": str(self.namespace), "command_id": "public-second", "effort_root": self.efforts[0], "initiator": self.efforts[0], "intent": "Second actual reusable instance", "environment": {"cwd": str(self.cwd)}, "origin": "human", "human_ref": {"fixture": "human"}}
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(bridge.main(["create-instance", self.write("new-instance", request)]), 0)
        self.instances[0] = json.loads(output.getvalue())
        scope = Scope.effort(self.efforts[0])
        inst = self.canonical.instantiate(self.efforts[0], scope=scope, native_ref={"fixture": "actual external agent"}, source_ref={"fixture": "agent"})
        target = self.canonical.open_session(self.efforts[0], inst["sequence"], scope=scope, native_ref={"session_id": "fixture-parent-agent"}, source_ref={"fixture": "agent-session"})
        actual = self.request
        with patch.object(self, "request", side_effect=lambda index=0: {**actual(index), "origin": "agent", "human_ref": None, "delegator": target.as_dict()}):
            status, run = self.run_owned()
        self.assertEqual(status, 0)
        for participant in bridge.owned_correspondence(run)["participants"]:
            self.assertEqual(self.canonical.mandates(participant["ordinal"])[0]["delegator"], target.as_dict())
        newstore = self.root / "public-store"
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(bridge.main(["--host", str(self.binary), "--store", str(newstore), "bind-store", "--namespace-path", str(self.namespace), "--effort-root", self.efforts[0], "--command-id", "public-store"]), 0)
        self.assertFalse(newstore.exists())
        self.assertEqual(json.loads(output.getvalue())["effort_root"], self.efforts[0])

    def test_optional_owned_purpose_and_partial_or_bare_telos_refusal(self):
        def omit(args, *flags):
            args = list(args)
            for flag in flags:
                index = args.index(flag)
                del args[index:index + 2]
            return args
        for removed in ("--purpose-ref", "--purpose-config"):
            with self.subTest(partial=removed), patch.object(bridge, "retrieve", side_effect=AssertionError("native forbidden")), self.assertRaisesRegex(ValueError, "both complete"), redirect_stdout(io.StringIO()):
                bridge.main(omit(self.args(), removed))
        for field, value in (("--telos-chain", "bare"), ("--telos-db", self.root / "bare.sqlite3"), ("--telos-source", self.source)):
            with self.subTest(bare=field), patch.object(bridge, "retrieve", side_effect=AssertionError("native forbidden")), self.assertRaisesRegex(ValueError, "bare Telos"), redirect_stdout(io.StringIO()):
                bridge.main([*omit(self.args(), "--purpose-ref", "--purpose-config"), field, str(value)])
        self.assertFalse(self.runs.exists())
        with patch.object(develop, "client_command", side_effect=self.client), redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.main(omit(self.args(), "--purpose-ref", "--purpose-config")), 0)
        prepared = self.adapter.inspect_preparations(effort_root=self.efforts[0])[-1]
        run = self.runs / prepared["run_id"]
        binding = bridge.owned_run(run)[1]
        self.assertTrue(all(binding[key] is None for key in ("purpose_ref", "purpose_config", "telos_chain", "telos_db", "telos_source")))
        self.assertIsNone(bridge.owned_correspondence(run)["purpose_ref"])
        self.assertNotIn("telos.linked", [e["kind"] for e in runtime.read_events(run)])
        with patch.object(bridge, "OperationHost", side_effect=AssertionError("receipt-only native forbidden")):
            self.assertEqual(self.resume(run), 0)
        (run / "opermem-receipt.json").unlink()
        self.assertEqual(self.resume(run), 0)

    def test_recall_selection_precedes_foreign_or_other_actor_source_reads(self):
        _, run_a = self.run_owned(0)
        _, run_b = self.run_owned(1)
        owned_a = bridge.owned_correspondence(run_a)
        target = owned_a["participants"][0]["target"]
        reviewer = Path(owned_a["participants"][1]["observation"]["stdout"])
        foreign = {Path(p["observation"]["stdout"]) for p in bridge.owned_correspondence(run_b)["participants"]}
        unselected = self.adapter.prepare_execution(self.request(1), task="Excluded preparation", workspace=self.cwd,
            runs_dir=self.runs, store_ref=self.stores[1], operation="question", inquiry=True, client="opencode")
        Path(unselected["preparation_path"]).unlink()
        for path in foreign:
            path.unlink()
        original_bytes, original_text = Path.read_bytes, Path.read_text
        reads = []
        def read_bytes(path, *args, **kwargs):
            if path in foreign or path == reviewer:
                reads.append(path)
            return original_bytes(path, *args, **kwargs)
        def read_text(path, *args, **kwargs):
            if path in foreign or path == reviewer:
                reads.append(path)
            return original_text(path, *args, **kwargs)
        with patch.object(Path, "read_bytes", read_bytes), patch.object(Path, "read_text", read_text):
            effort = self.recalled("effort", effort_root=self.efforts[0])
            self.assertFalse(any(path in foreign for path in reads))
            self.assertFalse(any(str(run_b) in d["path"] for d in effort["diagnostics"]))
            reviewer.unlink()
            reads.clear()
            exact = self.recalled("session", **target)
            self.assertEqual(reads, [])
            self.assertFalse(any(d["component"] in ("opermem-preparation", "legacy-run") for d in exact["diagnostics"]))
            self.assertEqual([s["source_ref"]["step"] for s in exact["sources"] if s["field"] == "opermem-actor"], ["work"])
