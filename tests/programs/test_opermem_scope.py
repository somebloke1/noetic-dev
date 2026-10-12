"""Owned event-only execution using actual disposable protocol-fixture processes."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import noetic_develop as develop, noetic_run as runtime
from scripts import noetic_telos as telos, noetic_purpose_binding as purposes
from scripts.noetic_purposes import Purposes
from scripts.noetic_scope import Scope, ScopeError, ScopeStore
from scripts.noetic_opermem_scope import OpermemScope, definition


class OwnedLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="opermem-scope-telos-")
        cls.addClassCleanup(cls.build.cleanup)
        cls.source = Path(cls.build.name) / "native.mjs"
        telos.bundle_goal_store(telos.source_path(), cls.source)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="opermem-owned-fixture-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cwd = self.root / "same-cwd"
        self.cwd.mkdir()
        self.runs = self.root / "runs"
        self.namespace = self.root / "state/ordinals.sqlite3"
        self.store = ScopeStore(self.namespace, root_mandate={"purpose": "fixture coordination"},
                                human_ref={"fixture": "human"}, source_ref={"fixture": "root"})
        self.efforts = [self.store.create_effort(intent=name, environment={"cwd": str(self.cwd)},
            mandate={"purpose": name}, origin="human", human_ref={"fixture": "human"},
            source_ref={"fixture": name})["ordinal"] for name in ("A", "B", "recovery")]
        self.adapter = OpermemScope(self.namespace)
        self.instances = [self.adapter.create_instance(command_id=name, effort_root=owner,
            initiator=owner, intent=name, environment={"cwd": str(self.cwd)}, origin="human",
            human_ref={"fixture": "human"}) for name, owner in zip(("A", "B", "R"), self.efforts)]
        self.native_stores = [self.adapter.bind_store(command_id=name, effort_root=owner,
            store_path=self.root / (name + "-native"), host=Path(sys.executable))
            for name, owner in zip(("A", "B", "R"), self.efforts)]
        self.calls = []

    def request(self, index=0, instance=None, **extra):
        instance = instance or self.instances[index]
        return {"namespace_path": str(self.namespace), "effort_root": self.efforts[index],
                "discipline_id": instance["id"], "environment": {"cwd": str(self.cwd)},
                "origin": "human", "human_ref": {"fixture": "human"}, **extra}

    def prepare(self, index=0, **extra):
        return self.adapter.prepare_execution(self.request(index), task="Inspect fixture evidence",
            workspace=self.cwd, runs_dir=self.runs, store_ref=self.native_stores[index],
            operation="question", inquiry=True, client="pi", **extra)

    def command(self, failure=None, client="pi", same_session=False):
        def fixture(actual_client, prompt, role, model, run_dir=None, workspace=None, context_dirs=()):
            self.calls.append(role)
            sid = "fixture-shared" if same_session else "fixture-" + role
            text = "Fixture source observations." if role != "reviewer" else "ACCEPT\nCompared fixture evidence."
            if actual_client == "pi":
                events = [{"type": "session", "id": sid}, {"type": "agent_end", "willRetry": False,
                    "messages": [{"role": "assistant", "stopReason": "stop",
                                  "content": [{"type": "text", "text": text}]}]}]
            else:
                events = [{"type": "text", "sessionID": sid,
                           "part": {"id": "part", "messageID": "final", "text": text}},
                          {"type": "step_finish", "sessionID": sid,
                           "part": {"messageID": "final", "reason": "stop"}}]
            code = "import sys; p=sys.stdin.read(); assert 'responsibility' in p; print(" + repr(
                "\n".join(json.dumps(e) for e in events)) + ")"
            if role != "reviewer":
                if failure == "header-failed":
                    code = "import sys; sys.stdin.read(); print(" + repr(json.dumps(events[0])) + "); sys.exit(2)"
                elif failure == "no-header":
                    code = "import sys; sys.stdin.read(); sys.exit(2)"
                elif failure == "launch":
                    return [str(self.root / "missing-executable")], None
                elif failure == "conflict":
                    identity = {"type": "session", "id": "fixture-conflicting"} if actual_client == "pi" else {"sessionID": "fixture-conflicting"}
                    code += "; print(" + repr(json.dumps(identity)) + ")"
                elif failure == "malformed":
                    code += "; print('invalid json')"
                elif failure == "native-error":
                    code += "; print('{\"type\":\"error\"}')"
                elif failure == "unfinished":
                    code += "; print('{\"type\":\"message_start\"}')"
            return [sys.executable, "-c", code], None
        return fixture

    def execute(self, binding, failure=None, same_session=False):
        lifecycle = self.adapter.lifecycle(binding)
        with patch.object(develop, "client_command", side_effect=self.command(failure, same_session=same_session)), redirect_stdout(io.StringIO()):
            return develop.develop(binding["task"]["text"], self.cwd, self.runs, None,
                client=binding["client"], inquiry=True, run_id=binding["run_id"], lifecycle=lifecycle,
                defer_telos_result=True)

    def test_a_b_r_and_multiple_instances_have_actual_work_review_participants(self):
        second = self.adapter.create_instance(command_id="A-second", effort_root=self.efforts[0],
            initiator=self.efforts[0], intent="Second independent instance", environment={"cwd": str(self.cwd)},
            origin="human", human_ref={"fixture": "human"})
        bindings = [self.prepare(i) for i in range(3)]
        bindings.append(self.adapter.prepare_execution(self.request(instance=second), task="Inspect fixture evidence",
            workspace=self.cwd, runs_dir=self.runs, store_ref=self.native_stores[0], operation="question", inquiry=True, client="pi"))
        ordinals = []
        for binding in bindings:
            run, state = self.execute(binding)
            self.assertEqual(state["state"], "accepted")
            observed = self.adapter.correspondence(binding)
            self.assertEqual(observed["run_status"], "accepted")
            self.assertEqual([p["step"] for p in observed["participants"]], ["work", "review"])
            for participant in observed["participants"]:
                ordinals.append(participant["ordinal"])
                self.assertTrue(participant["ordinal"].startswith(binding["effort_root"] + "."))
                self.assertEqual(participant["origin"], "human")
                self.assertIsNotNone(participant["target"])
                self.assertEqual(participant["session_status"], "closed")
                self.assertIsNone(participant["native_session_ref"]["context_file"])
                self.assertFalse((run / "controller.sqlite3").exists())
                self.assertIn(participant["ordinal"], (run / (participant["step"] + "-prompt.txt")).read_text())
        self.assertEqual(len(set(ordinals)), 8)
        self.assertEqual(len({b["execution_id"] for b in bindings}), 4)
        self.assertIsNone(self.store.position("0")["current_instantiation"])
        self.assertEqual(definition()["id"], "noetic:opermem-reviewed")
        self.assertEqual({r["id"] for r in definition()["descriptor"]["roles"]}, {"worker", "inquirer", "reviewer"})

    def test_failures_retain_exact_identity_or_only_reservation(self):
        for failure, has_target in (("header-failed", True), ("no-header", False), ("launch", False),
                                    ("conflict", False), ("malformed", True), ("native-error", True), ("unfinished", True)):
            with self.subTest(failure=failure):
                binding = self.prepare()
                run, state = self.execute(binding, failure)
                self.assertEqual(state["state"], "failed")
                part, = self.adapter.correspondence(binding)["participants"]
                self.assertEqual(part["target"] is not None, has_target)
                if has_target:
                    self.assertEqual(part["session_status"], "failed")
                else:
                    self.assertEqual(self.store.instantiations(part["ordinal"]), [])
                self.assertFalse((run / "review.stdout.log").exists())

    def test_opencode_and_same_worker_reviewer_identity_are_checked(self):
        binding = self.adapter.prepare_execution(self.request(), task="Inspect fixture evidence", workspace=self.cwd,
            runs_dir=self.runs, store_ref=self.native_stores[0], operation="insight", inquiry=True, client="opencode")
        _, state = self.execute(binding)
        self.assertEqual(state["state"], "accepted")
        self.assertEqual({p["native_session_ref"]["client"] for p in self.adapter.correspondence(binding)["participants"]}, {"opencode"})
        bad = self.prepare()
        _, state = self.execute(bad, same_session=True)
        self.assertNotEqual(state["state"], "accepted")
        review = self.adapter.correspondence(bad)["participants"][-1]
        self.assertIsNone(review["target"])

    def test_scoped_development_executes_actual_verification_before_fresh_review(self):
        binding = self.adapter.prepare_execution(self.request(), task="Inspect fixture evidence", workspace=self.cwd,
            runs_dir=self.runs, store_ref=self.native_stores[0], operation="insight", inquiry=False, client="opencode")
        sentinel = self.cwd / "verification-occurred"
        code = "from pathlib import Path; assert Path(" + repr(str(Path(binding["run_dir"]) / "opermem-scope.json")) + ").exists(); Path(" + repr(str(sentinel)) + ").write_text('actual fixture check')"
        with patch.object(develop, "client_command", side_effect=self.command()), redirect_stdout(io.StringIO()):
            run, state = develop.develop(binding["task"]["text"], self.cwd, self.runs, [sys.executable, "-c", code],
                client="opencode", run_id=binding["run_id"], lifecycle=self.adapter.lifecycle(binding))
        self.assertEqual(state["state"], "accepted")
        self.assertEqual(state["steps"]["verify"]["returncode"], 0)
        self.assertEqual(sentinel.read_text(), "actual fixture check")
        self.assertEqual(self.calls, ["worker", "reviewer"])
        events = runtime.read_events(run)
        self.assertLess(next(e["sequence"] for e in events if e["kind"] == "scope.bound"),
                        next(e["sequence"] for e in events if e["kind"] == "step.started"))

    def test_read_only_preflight_rejects_before_preparation_and_effects(self):
        untouched = self.root / "not-created"
        for changed in ({"effort_root": self.efforts[1]}, {"discipline_id": 999}, {"origin": "legacy"},
                        {"environment": {"cwd": str(self.root)}}, {"human_ref": None}):
            with self.subTest(changed=changed), self.assertRaises((ValueError, KeyError)):
                self.adapter.prepare_execution({**self.request(), **changed}, task="Task", workspace=self.cwd,
                    runs_dir=untouched, store_ref=self.native_stores[0], operation="question", inquiry=True, client="pi")
        for kwargs in ({"workspace": self.root}, {"store_ref": self.native_stores[1]},
                       {"store_ref": {**self.native_stores[0], "host": str(self.root / "foreign")}},
                       {"purpose_ref": {"chain_id": "bare"}}, {"client": "unknown"}):
            values = dict(task="Task", workspace=self.cwd, runs_dir=untouched, store_ref=self.native_stores[0],
                          operation="question", inquiry=True, client="pi")
            values.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises((ValueError, KeyError)):
                self.adapter.prepare_execution(self.request(), **values)
        self.assertFalse(untouched.exists())
        self.assertTrue(all(not Path(ref["directory"]).exists() for ref in self.native_stores))

    def test_store_alias_conflict_serializes_within_declared_namespace(self):
        actual = self.root / "shared-store"
        actual.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(actual, target_is_directory=True)
        def register(index):
            try:
                return OpermemScope(self.namespace).bind_store(command_id="race-" + str(index),
                    effort_root=self.efforts[index], store_path=actual if index == 0 else alias, host=Path(sys.executable))
            except ScopeError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(register, (0, 1)))
        self.assertEqual(sum(result is not None for result in results), 1)

    def test_agent_mandate_uses_actual_target_and_stale_assignment_refuses(self):
        root = self.efforts[0]
        scope = Scope.effort(root)
        inst = self.store.instantiate(root, scope=scope, native_ref={"fixture": "actual fixture actor"}, source_ref={"fixture": "instantiation"})
        target = self.store.open_session(root, inst["sequence"], scope=scope, native_ref={"session_id": "fixture-initiator"}, source_ref={"fixture": "session"})
        request = self.request(origin="agent", human_ref=None, delegator=target.as_dict())
        binding = self.adapter.prepare_execution(request, task="Inspect fixture evidence", workspace=self.cwd,
            runs_dir=self.runs, store_ref=self.native_stores[0], operation="question", inquiry=True, client="pi")
        self.execute(binding)
        for part in self.adapter.correspondence(binding)["participants"]:
            mandate = self.store.mandates(part["ordinal"])[0]
            self.assertEqual(mandate["origin"], "agent")
            self.assertEqual(mandate["delegator"], target.as_dict())
        self.store.open_session(root, inst["sequence"], scope=scope, native_ref={"session_id": "fixture-successor"}, source_ref={"fixture": "session"})
        with self.assertRaises(ScopeError):
            self.adapter.validate_request(request, self.cwd)
        self.assertEqual(len(self.adapter.correspondence(binding)["participants"]), 2)

    def test_cache_deletion_recovery_does_not_duplicate_or_execute(self):
        binding = self.prepare()
        run, state = self.execute(binding)
        original = self.adapter.correspondence(binding)
        cache = self.namespace.with_name(self.namespace.name + ".correlation.sqlite3")
        cache.unlink()
        self.adapter.recover_preparation(binding["execution_id"])
        self.adapter.lifecycle(binding).after_actor(run, "work", "pi")
        self.adapter.lifecycle(binding).after_actor(run, "review", "pi")
        self.assertEqual(original, self.adapter.correspondence(binding))
        self.assertEqual(self.calls, ["inquirer", "reviewer"])
        with self.assertRaisesRegex(ScopeError, "already"):
            self.adapter.lifecycle(binding).before_actor(run, "work", "inquirer", "pi", "again")

    def test_canonical_commit_before_cache_failure_recovers_original_reservation(self):
        original = ScopeStore.create_execution
        def committed_then_failed(store, *args, **kwargs):
            original(store, *args, **kwargs)
            raise RuntimeError("fixture cache gap after canonical commit")
        run_id = "a" * 32
        with patch.object(ScopeStore, "create_execution", committed_then_failed):
            with self.assertRaisesRegex(RuntimeError, "cache gap"):
                self.prepare(run_id=run_id)
        self.assertFalse((self.runs / run_id).exists())
        binding = self.prepare(run_id=run_id)
        self.assertEqual(len(self.adapter.inspect_preparations(effort_root=self.efforts[0])), 1)
        _, state = self.execute(binding)
        self.assertEqual(state["state"], "accepted")
        self.assertEqual(self.calls, ["inquirer", "reviewer"])
        self.assertEqual(len(self.adapter.correspondence(binding)["participants"]), 2)

    def test_changed_captured_evidence_is_unavailable_without_legacy_fallback(self):
        binding = self.prepare()
        run, _ = self.execute(binding)
        (run / "work.stdout.log").write_text('{"type":"session","id":"substitution"}\n')
        with self.assertRaisesRegex(ScopeError, "evidence"):
            self.adapter.correspondence(binding)
        report, = self.adapter.inspect_preparations(effort_root=self.efforts[0])
        self.assertEqual(report["correlation_status"], "unavailable")

    def test_preparation_only_failure_and_host_sources_remain_inspectable_read_only(self):
        source = self.cwd / "given.txt"
        source.write_text("Actual external fixture evidence\n")
        binding = self.prepare(source_paths=(source,), occasion={"kind": "experience", "id": 1})
        self.adapter.preparation_failed(binding, "fixture host could not start")
        self.assertFalse(Path(binding["run_dir"]).exists())
        before = self.namespace.read_bytes()
        cache = self.namespace.with_name(self.namespace.name + ".correlation.sqlite3")
        cache_bytes = cache.read_bytes()
        report = self.adapter.correspondence(binding)
        self.assertEqual(report["run_status"], "preparation-failed")
        self.assertEqual(report["participants"], [])
        self.assertEqual(report["host_sources"][0]["kind"], "external-host-evidence")
        self.assertEqual(len(self.adapter.inspect_preparations(effort_root=self.efforts[0])), 1)
        self.assertEqual(self.namespace.read_bytes(), before)
        self.assertEqual(cache.read_bytes(), cache_bytes)

    def test_owned_purpose_identity_mutable_content_and_restoration(self):
        adapter = Purposes(self.namespace, purposes_root=self.root / "purposes", source=self.source)
        refs = [adapter.create(name, scope=Scope.effort(owner), origin_ref={"fixture": "human"},
            source_ref={"fixture": "source"})["reference"] for owner, name in zip(self.efforts[:2], ("A purpose", "B purpose"))]
        config = purposes.configuration(adapter)
        with self.assertRaises(ValueError):
            self.prepare(purpose_ref=refs[1], purpose_config=config)
        binding = self.prepare(purpose_ref=refs[0], purpose_config=config)
        original_ref = deepcopy(binding["purpose_ref"])
        run, state = self.execute(binding)
        self.assertEqual(state["state"], "accepted")
        governing = json.loads((run / "telos-context.json").read_text())
        self.assertEqual(governing["purpose_ref"], original_ref)
        self.assertEqual(governing["primary_goal"], "A purpose")
        db_path = Path(refs[0]["db_path"])
        with closing(sqlite3.connect(db_path)) as db, db:
            db.execute("UPDATE chains SET primary_goal=? WHERE chain_id=?", ("Changed native purpose", refs[0]["chain_id"]))
        self.adapter.validate_binding(binding)
        self.assertEqual(json.loads((run / "telos-context.json").read_text()), governing)
        actual_source = self.source.read_bytes()
        self.source.unlink()
        try:
            with self.assertRaises(ValueError):
                self.adapter.validate_binding(binding)
            self.assertEqual(self.adapter.correspondence(binding)["purpose_ref"], original_ref)
        finally:
            self.source.write_bytes(actual_source)
        self.adapter.validate_binding(binding)
        changed = deepcopy(binding)
        changed["purpose_ref"]["chain_id"] = refs[1]["chain_id"]
        with self.assertRaises(ScopeError):
            self.adapter.validate_binding(changed)

    def test_frozen_binding_substitution_prevents_child_or_telos_start(self):
        binding = self.prepare()
        altered = deepcopy(binding)
        altered["store_ref"]["directory"] = str(self.root / "foreign")
        with patch.object(develop, "client_command") as client:
            with self.assertRaises(ScopeError):
                develop.develop("Inspect fixture evidence", self.cwd, self.runs, None, client="pi", inquiry=True,
                    run_id=binding["run_id"], lifecycle=self.adapter.lifecycle(altered))
        client.assert_not_called()
        self.assertFalse(Path(binding["run_dir"]).exists())

    def test_legacy_develop_without_lifecycle_is_unchanged(self):
        def fixture(*args, **kwargs):
            role = args[2]
            events = [{"type": "session", "id": "legacy-fixture-" + role},
                {"type": "agent_end", "willRetry": False, "messages": [{"role": "assistant", "stopReason": "stop",
                 "content": [{"type": "text", "text": "Observed" if role == "inquirer" else "ACCEPT\nFixture check"}]}]}]
            return [sys.executable, "-c", "print(" + repr("\n".join(json.dumps(e) for e in events)) + ")"], None
        with patch.object(develop, "client_command", side_effect=fixture), redirect_stdout(io.StringIO()):
            run, state = develop.develop("Legacy inquiry", self.cwd, self.runs, None, client="pi", inquiry=True)
        self.assertEqual(state["state"], "accepted")
        self.assertFalse((run / "opermem-scope.json").exists())
        self.assertFalse(any(event["kind"] == "scope.bound" for event in runtime.read_events(run)))


if __name__ == "__main__":
    unittest.main()
