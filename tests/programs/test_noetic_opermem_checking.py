"""Bounded host capture, exact evidence binding, and real native replay."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import noetic_opermem as bridge
from scripts import noetic_opermem_checking as checking
from scripts import noetic_run


def fixture_context(text="Exact bounded checking predicate"):
    cut = {"authority_generation": 9}
    payload = {"conditions": [text]}
    def item(kind, identity, voice):
        content = {"command": {"payload": payload}, "id": {"kind": kind, "id": identity}}
        return {"residue_id": {"kind": kind, "id": identity}, "kind": kind,
                "object_version": 1, "liveness": "live", "content": content,
                "content_sha256": checking.digest(checking.canonical(content)),
                "pinned_cut_binding": cut, "retrieval_voice": voice, "ancestry": []}
    condition = item("warrant-condition", 20, {"text": text, "state": "unchecked"})
    warrant = item("warrant", 10, {"conditions": [text]})
    condition["ancestry"] = [{"kind": "has-condition", "other": warrant["residue_id"], "endpoint_role": "to"}]
    return {"operation": "checking", "pinned_canonical_cut": cut,
            "supplied_whole_residues": [warrant, condition]}


class CheckingCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.context = fixture_context()
        self.context_ids = (20, 10)
        self.counter = 0

    def specification(self, test_body="assert 2 + 2 == 4", *, selected=None):
        module = self.root / "bounded_case.py"
        module.write_text("import unittest\nclass ExactCase(unittest.TestCase):\n    def test_exact(self):\n        " + test_body + "\n")
        runner = Path(checking.__file__).with_name("noetic_checking_tests.py").resolve()
        python = Path(sys.executable).resolve()
        test_id = "bounded_case.ExactCase.test_exact"
        selected = selected or [test_id]
        sources = [{"path": str(path), "sha256": checking.digest(path.read_bytes()), "role": role}
                   for path, role in ((python, "actual Python"), (runner, "actual test runner"), (module, "bounded assertions"))]
        value = {"version": checking.SPEC_VERSION, "condition": checking.binding(self.context, *self.context_ids),
                 "command": {"argv": [str(python), str(runner), "--module-dir", str(self.root), test_id],
                             "cwd": str(self.root), "timeout_seconds": 10,
                             "environment": {"LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}},
                 "selected_tests": selected, "predicates": [{"id": "exact", "test_ids": selected,
                                                             "expected_observation": "actual assertion succeeds"}],
                 "sources": sources, "scope": "Only the exact executed assertion."}
        path = self.root / "spec.json"
        path.write_bytes(checking.canonical(value))
        return path

    def capture(self, spec):
        self.counter += 1
        directory = self.root / f"evidence-{self.counter}"
        result = checking.capture(spec, self.context, *self.context_ids, directory)
        return directory, result

    def test_real_assertion_outcomes_and_exact_bytes(self):
        for body, expected, count in (("assert 2 + 2 == 4", "fulfilled", "passed"),
                                      ("assert 2 + 2 == 5", "unfulfilled", "failed"),
                                      ("self.skipTest('required predicate skipped')", "indeterminate", "skipped"),
                                      ("raise RuntimeError('unknown observation')", "indeterminate", "error")):
            with self.subTest(body=body):
                path, manifest = self.capture(self.specification(body))
                self.assertEqual(manifest["result"], expected)
                self.assertEqual(manifest["counts"][count], 1)
                self.assertEqual(manifest["counts"]["executed"], 0 if count == "skipped" else 1)
                self.assertEqual(manifest["execution"]["returncode"], 1 if count in ("failed", "error") else 0)
                self.assertEqual(checking.revalidate(path), manifest)
                digest = checking.digest((path / "manifest.json").read_bytes())
                contribution = checking.contribution(path, self.context, *self.context_ids, digest)
                self.assertEqual(contribution["result"], expected)
                self.assertFalse(contribution["provenance"]["model_assertion_used_as_evidence"])
                stdout = (path / "stdout.bin").read_bytes()
                self.assertEqual(manifest["artifacts"]["stdout.bin"]["sha256"], checking.digest(stdout))
                self.assertEqual(manifest["artifacts"]["stdout.bin"]["bytes"], len(stdout))

    def test_missing_selected_test_cannot_fulfill(self):
        path, result = self.capture(self.specification(selected=["bounded_case.ExactCase.test_exact", "required.unexecuted.test"]))
        self.assertEqual(result["result"], "indeterminate")
        self.assertEqual(result["counts"]["selected"], 2)
        self.assertEqual(result["counts"]["observed"], 1)
        self.assertEqual(checking.revalidate(path)["result"], "indeterminate")

    def test_substitution_duplicate_bare_zero_timeout_and_unexecuted(self):
        spec = checking.load(self.specification())
        passed = {"version": checking.OBS_VERSION, "tests": [{"id": spec["selected_tests"][0], "status": "passed"}], "observations": []}
        execution = {"performed": True, "completed": True, "returncode": 0, "error": None}
        for observed in (b"", b"zero exit is enough", checking.canonical({**passed, "tests": passed["tests"] * 2}),
                         checking.canonical({**passed, "tests": [{"id": "substitute", "status": "passed"}]})):
            self.assertEqual(checking.outcome(spec, execution, observed)[0], "indeterminate")
        self.assertEqual(checking.outcome(spec, {**execution, "returncode": 1}, checking.canonical(passed))[0], "indeterminate")
        spec["command"]["timeout_seconds"] = 0.1
        spec["command"]["argv"] = [str(Path(sys.executable).resolve()), "-c", "import time;time.sleep(2)"]
        path = self.root / "timeout-spec.json"
        path.write_bytes(checking.canonical(spec))
        directory, manifest = self.capture(path)
        self.assertEqual((manifest["result"], manifest["execution"]["error"]), ("indeterminate", "timeout"))
        spec["command"]["argv"][0] = str(self.root / "not-executable")
        missing = self.root / "not-executable"
        missing.write_bytes(b"exact unexecutable bytes")
        spec["sources"].append({"path": str(missing), "sha256": checking.digest(missing.read_bytes()), "role": "unexecutable fixture"})
        path.write_bytes(checking.canonical(spec))
        directory, manifest = self.capture(path)
        self.assertEqual((manifest["result"], manifest["execution"]["performed"]), ("indeterminate", False))
        with self.assertRaisesRegex(ValueError, "unexecuted"):
            checking.contribution(directory, self.context, *self.context_ids,
                                  checking.digest((directory / "manifest.json").read_bytes()))

    def test_closed_bindings_reject_before_execution(self):
        spec = checking.load(self.specification())
        mutations = [lambda s: s["condition"].update(text="substitution"),
                     lambda s: s["condition"].update(text_sha256="0" * 64),
                     lambda s: s["condition"].update(id=99),
                     lambda s: s["condition"].update(warrant_id=99),
                     lambda s: s["predicates"].append(deepcopy(s["predicates"][0])),
                     lambda s: s.update(predicates=[]),
                     lambda s: s["command"]["environment"].update(USER_PROVIDED_PASSWORD="public sentinel"),
                     lambda s: s.update(extra="not allowed")]
        for mutation in mutations:
            changed = deepcopy(spec)
            mutation(changed)
            with self.assertRaises(ValueError):
                checking.validate_spec(changed, self.context, *self.context_ids)
        changed = deepcopy(self.context)
        changed["supplied_whole_residues"][1]["content"]["id"]["id"] = 99
        with self.assertRaisesRegex(ValueError, "content hash"):
            checking.validate_spec(spec, changed, *self.context_ids)

    def test_hash_result_context_and_source_revalidation_and_archival_replay(self):
        directory, _ = self.capture(self.specification())
        expected = checking.digest((directory / "manifest.json").read_bytes())
        changed = deepcopy(self.context)
        changed["pinned_canonical_cut"]["authority_generation"] = 10
        with self.assertRaisesRegex(ValueError, "context changed"):
            checking.revalidate(directory, changed, expected_manifest_sha256=expected)
        original = (directory / "stdout.bin").read_bytes()
        (directory / "stdout.bin").write_bytes(b"substitute")
        with self.assertRaisesRegex(ValueError, "artifact hash"):
            checking.revalidate(directory, expected_manifest_sha256=expected)
        (directory / "stdout.bin").write_bytes(original)
        module = self.root / "bounded_case.py"
        module.unlink()
        with self.assertRaises(OSError):
            checking.revalidate(directory, expected_manifest_sha256=expected)
        self.assertEqual(checking.revalidate(directory, current=False, expected_manifest_sha256=expected)["result"], "fulfilled")
        manifest = checking.load(directory / "manifest.json")
        manifest["result"] = "unfulfilled"
        (directory / "manifest.json").write_bytes(checking.canonical(manifest))
        with self.assertRaisesRegex(ValueError, "manifest hash"):
            checking.revalidate(directory, current=False, expected_manifest_sha256=expected)
        with self.assertRaisesRegex(ValueError, "binding mismatch"):
            checking.revalidate(directory, current=False,
                expected_manifest_sha256=checking.digest((directory / "manifest.json").read_bytes()))

    def test_native_reference_order_and_closed_positive_anchors(self):
        directory, _ = self.capture(self.specification())
        contribution = checking.contribution(directory, self.context, *self.context_ids,
            checking.digest((directory / "manifest.json").read_bytes()))
        kind, command = checking.command_for(self.context, contribution, "key")
        self.assertEqual(kind, "check-condition")
        self.assertEqual(command["expected_object_versions"], [
            {"id": 10, "kind": "warrant", "version": 1},
            {"id": 20, "kind": "warrant-condition", "version": 1}])
        for condition, warrant in ((None, 10), (True, 10), (0, 10), (20, True), (20, 0), (2**64, 10)):
            with self.assertRaises(ValueError):
                bridge.purpose_for("checking", condition, warrant_id=warrant)
        self.assertEqual(bridge.purpose_for("checking", 20, warrant_id=10),
                         {"operation": "checking", "condition_id": 20, "warrant_id": 10})


@unittest.skipUnless(os.environ.get("OPERMEM_OPERATION_HOST"), "requires QA-accepted actual Rust host")
class CheckingNativeBoundaryTests(unittest.TestCase):
    specification = CheckingCaptureTests.specification
    capture = CheckingCaptureTests.capture
    def setUp(self):
        CheckingCaptureTests.setUp(self)
        self.binary = Path(os.environ["OPERMEM_OPERATION_HOST"]).resolve()
        self.store = self.root / "native-store"
        self.transcripts = self.root / "native-transcripts"
        parent = None
        for operation, contribution, role in [
            ("question", {"question_kind": "how", "text": "How is checking bounded?"}, "question"),
            ("insight", {"text": "Trace: exact test evidence may answer a condition."}, "unverified insight trace"),
            ("formulation", {"text": "Hypothesis: native checking retains exact evidence."}, "versioned formulation/hypothesis"),
            ("reflection", {"text": "Is this hypothesis correct?"}, "reflection question")]:
            response, _ = bridge.submit(self.binary, self.store, self.transcripts, operation, parent, contribution, "fixture-" + operation)
            parent = next(o["id"] for o in response["payload"]["outputs"] if o["role"] == role)
            if operation == "formulation":
                formulation = parent
        response, _ = bridge.submit(self.binary, self.store, self.transcripts, "conditional-structure", parent,
            {"conditions": ["Exact bounded checking predicate"]}, "fixture-warrant", formulation_id=formulation)
        warrant = next(o["id"] for o in response["payload"]["outputs"] if o["role"] == "warrant")
        condition = next(o["id"] for o in response["payload"]["outputs"] if o["kind"] == "warrant-condition")
        self.context_ids = (condition, warrant)
        self.context, _ = bridge.retrieve(self.binary, self.store, self.transcripts,
            bridge.purpose_for("checking", condition, warrant_id=warrant))

    def test_actual_rust_outcomes_full_descriptor_restart_and_exact_resume(self):
        directory, manifest = self.capture(self.specification("assert 2 + 2 == 5"))
        expected = checking.digest((directory / "manifest.json").read_bytes())
        contribution = checking.contribution(directory, self.context, *self.context_ids, expected)
        run = noetic_run.create_run({"goal": "Bound checking", "work": ["true"], "verify": ["true"]}, self.root, self.root / "runs")
        import shutil
        shutil.copytree(directory, run / "checking-evidence")
        noetic_run.record(run, "run.finished", {"state": "awaiting_review"})
        (run / "review.md").write_text("ACCEPT\nExact host negative assertion inspected.\n")
        noetic_run.review_run(run, "accept", "test:independent-reviewer", run / "review.md")
        (run / "opermem-link.json").write_text(json.dumps({"host": str(self.binary), "store": str(self.store.resolve()),
            "operation": "checking", "parent_id": self.context_ids[0], "warrant_id": self.context_ids[1],
            "context": self.context, "checking_manifest_sha256": expected}))
        (run / "work.md").write_text(bridge.MARKER + '{"result":"fulfilled"}\nModel assertion is ignored.')
        response, _ = bridge.submit(self.binary, self.store, self.transcripts, "checking", self.context_ids[0],
            contribution, f"noetic-{run.name}-checking", self.context, pending_path=run / "opermem-pending.json",
            warrant_id=self.context_ids[1], checking_evidence=run / "checking-evidence", checking_manifest_sha256=expected)
        self.assertEqual(contribution["result"], "unfulfilled")
        self.assertEqual(response["class"], "success")
        current, _ = bridge.retrieve(self.binary, self.store, self.transcripts,
            bridge.purpose_for("checking", self.context_ids[0], warrant_id=self.context_ids[1]))
        texts = [json.loads(item["content"]["command"]["payload"]["provenance"]) for item in current["supplied_whole_residues"]
                 if item["kind"] == "evidence-record"]
        self.assertIn(contribution["provenance"], texts)
        with patch.object(checking.subprocess, "run", side_effect=AssertionError("replay must not execute tests")), redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.resume_run(run, self.binary, self.store, self.transcripts), 0)
        replay = checking.load(run / "opermem-receipt.json")
        self.assertEqual(replay["response"]["class"], "idempotency-replay")
        self.assertEqual(replay["response"]["payload"]["receipt_id"], response["payload"]["receipt_id"])
        self.assertEqual(replay["contribution"], contribution)


    def test_actual_review_pipeline_capture_precedes_actor_and_receipt_precedes_telos(self):
        from types import SimpleNamespace
        task = self.root / "task.md"
        task.write_text("Inspect exact host evidence; result remains host-derived.")
        spec = self.specification("assert 2 + 2 == 5")
        roles = []
        captured_hash = None
        def local_actor(client, prompt, role, model, run_dir=None, workspace=None, context_dirs=()):
            nonlocal captured_hash
            self.assertEqual(client, "opencode")
            self.assertEqual(len(context_dirs), 1)
            evidence = context_dirs[0]
            manifest = checking.revalidate(evidence)
            self.assertEqual(manifest["result"], "unfulfilled")
            self.assertIn("HOST-CAPTURED", prompt)
            self.assertIn(str(evidence), prompt)
            captured_hash = checking.digest((evidence / "manifest.json").read_bytes())
            roles.append(role)
            text = ('OPERMEM_CONTRIBUTION_JSON: {"result":"fulfilled"}' if role == "inquirer"
                    else "ACCEPT\nInspected host-captured negative assertion and read-only report.")
            events = [{"type": "text", "sessionID": role, "part": {"id": role, "messageID": role, "text": text}},
                      {"type": "step_finish", "sessionID": role, "part": {"messageID": role, "reason": "stop"}}]
            return [sys.executable, "-c", "print(" + repr("\n".join(json.dumps(event) for event in events)) + ")"], {}
        synchronized = []
        real_sync = bridge.sync_telos
        def sync(run):
            synchronized.append((run / "opermem-receipt.json").exists())
            return real_sync(run)
        source = Path(__file__).resolve().parents[2] / ".runtime/components/telos-recovery-20261011.mjs"
        if not source.is_file():
            self.skipTest("actual Telos receipt synchronization requires local source module")
        telos_db = self.root / "telos.sqlite3"
        aggregate = bridge.noetic_telos.create_goal("isolated checking receipt fixture", telos_db, source)
        (self.root / "runs").mkdir(mode=0o700)
        args = SimpleNamespace(task=task, workspace=self.root, runs_dir=self.root / "runs", verify=None,
            client="opencode", model="test:local-process", review_model="test:local-review-process", timeout=10,
            inquiry=True, qualification=None, thinking=None, host=self.binary, store=self.store,
            operation="checking", parent_id=self.context_ids[0], warrant_id=self.context_ids[1], formulation_id=None,
            checking_spec=spec, telos_chain=aggregate["chain"]["chainId"], telos_db=telos_db, telos_source=source)
        with patch.object(bridge.noetic_develop, "client_command", side_effect=local_actor), patch.object(bridge, "sync_telos", side_effect=sync), redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.run_task(args), 0)
        self.assertEqual(roles, ["inquirer", "reviewer"])
        self.assertEqual(synchronized, [True])
        after = bridge.noetic_telos.get_goal(args.telos_chain, telos_db, source)
        self.assertEqual(after["chain"]["status"], "active")
        self.assertEqual(len(after["subGoals"]), 1)
        self.assertEqual(after["subGoals"][0]["status"], "complete")
        run = next(path for path in args.runs_dir.iterdir() if (path / "opermem-receipt.json").exists())
        receipt = checking.load(run / "opermem-receipt.json")
        self.assertEqual(receipt["contribution"]["result"], "unfulfilled")
        self.assertEqual(receipt["contribution"]["provenance"]["manifest_sha256"], captured_hash)
        events = noetic_run.read_events(run)
        verify = [event for event in events if event["kind"] == "step.started" and event["data"].get("step") == "verify"]
        self.assertEqual(len(verify), 1)
        self.assertEqual(noetic_run.project(events)["state"], "accepted")
        _, environment = bridge.noetic_develop.client_command("opencode", "read", "inquirer", "test:local", workspace=self.root, context_dirs=(run / "checking-evidence",))
        permissions = json.loads(environment["OPENCODE_CONFIG_CONTENT"])["agent"]["noetic-inquirer"]["permission"]
        self.assertEqual(permissions["*"], "deny")
        self.assertEqual(permissions["external_directory"][str(run / "checking-evidence") + "/**"], "allow")
        self.assertNotIn("bash", permissions)


    def native_outcome(self, body, expected):
        directory, _ = self.capture(self.specification(body))
        manifest_hash = checking.digest((directory / "manifest.json").read_bytes())
        contribution = checking.contribution(directory, self.context, *self.context_ids, manifest_hash)
        self.assertEqual(contribution["result"], expected)
        kind, payload = checking.command_for(self.context, contribution, "outcome-" + expected)
        stale = deepcopy(payload)
        stale["expected_object_versions"][0]["version"] = 999
        stale["idempotency_key"] = "stale-outcome-" + expected
        transcript = bridge.fresh_transcript(self.transcripts)
        with self.assertRaises(RuntimeError):
            with bridge.OperationHost(self.binary, self.store, transcript) as host:
                host.context(bridge.purpose_for("checking", self.context_ids[0], warrant_id=self.context_ids[1]))
                host.exchange(kind, stale)
        response, _ = bridge.submit(self.binary, self.store, self.transcripts, "checking", self.context_ids[0],
            contribution, "outcome-" + expected, self.context, warrant_id=self.context_ids[1],
            checking_evidence=directory, checking_manifest_sha256=manifest_hash)
        self.assertEqual(response["class"], "success")
        current, _ = bridge.retrieve(self.binary, self.store, self.transcripts,
            bridge.purpose_for("checking", self.context_ids[0], warrant_id=self.context_ids[1]))
        evidence = next(item for item in current["supplied_whole_residues"] if item["kind"] == "evidence-record")
        self.assertEqual(evidence["content"]["command"]["payload"]["result"], expected)
        self.assertEqual(json.loads(evidence["content"]["command"]["payload"]["provenance"]), contribution["provenance"])

    def test_actual_native_fulfilled(self):
        self.native_outcome("assert 2 + 2 == 4", "fulfilled")

    def test_actual_native_skip_indeterminate(self):
        self.native_outcome("self.skipTest('required exact predicate skipped')", "indeterminate")
