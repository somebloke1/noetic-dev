"""Disposable empirical fixtures for the canonical global ordinal domain."""

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.noetic_scope import Scope, ScopeError, ScopeStore, Target


SOURCE = {"journal": "fixture", "event": "owner-direction"}
HUMAN = {"owner": "fixture-human"}
MANDATE = {"purpose": "Useful work", "limits": "declared effort environments"}


def concurrent_child(args):
    path, root, index = args
    return ScopeStore(path).delegate(root, scope=Scope.effort(root), mandate=MANDATE,
                                     origin="human", human_ref=HUMAN,
                                     source_ref={"fixture": index})["ordinal"]


class OrdinalScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "application" / "scope.sqlite3"
        self.store = ScopeStore(self.path, root_mandate=MANDATE, human_ref=HUMAN, source_ref=SOURCE)
        self.a = self.effort("A", "/unrelated/a")
        self.b = self.effort("B", "/unrelated/b")
        self.r = self.effort("R", "/external/recovery")
        self.scope = Scope.effort(self.a["ordinal"])

    def tearDown(self):
        self.temp.cleanup()

    def effort(self, intent, cwd):
        return self.store.create_effort(intent=intent, environment={"cwd": cwd},
                                        mandate=MANDATE, origin="human", human_ref=HUMAN,
                                        source_ref=SOURCE)

    def child(self, parent=None, **kwargs):
        return self.store.delegate(parent or self.a["ordinal"], scope=self.scope,
                                   mandate=MANDATE, origin="human", human_ref=HUMAN,
                                   source_ref=SOURCE, **kwargs)

    def runtime(self, ordinal=None):
        ordinal = ordinal or self.a["ordinal"]
        instance = self.store.instantiate(ordinal, scope=self.scope, native_ref={"client": "fixture", "agent": ordinal},
                                          source_ref=SOURCE)
        return self.store.open_session(ordinal, instance["sequence"], scope=self.scope,
                                       native_ref={"client": "fixture", "session_id": "native-" + ordinal,
                                                   "context_file": "/fixture/" + ordinal}, source_ref=SOURCE)

    def test_root_efforts_persistence_and_closed_positions_never_recycled(self):
        self.assertEqual([self.a["ordinal"], self.b["ordinal"], self.r["ordinal"]], ["0.0", "0.1", "0.2"])
        root = self.store.position("0")
        self.assertIsNone(root["current_instantiation"])
        self.assertEqual(root["origin"], "human")
        self.assertEqual(root["mandate"]["human_ref"], HUMAN)
        first = self.child()
        self.store.close_position(first["ordinal"], scope=self.scope, source_ref=SOURCE)
        reopened = ScopeStore(self.path)
        self.assertEqual(reopened.namespace, self.store.namespace)
        second = reopened.delegate("0.0", scope=self.scope, mandate=MANDATE, origin="human",
                                    human_ref=HUMAN, source_ref=SOURCE)
        self.assertEqual((first["ordinal"], second["ordinal"]), ("0.0.0", "0.0.1"))
        self.assertEqual(reopened.position(first["ordinal"])["status"], "closed")
        self.assertEqual(self.effort("same cwd, different intent", "/unrelated/a")["ordinal"], "0.3")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.path.parent.stat().st_mode & 0o777, 0o700)

    def test_actual_process_concurrency_and_transaction_rollback(self):
        with ProcessPoolExecutor(max_workers=4) as pool:
            ordinals = list(pool.map(concurrent_child, [(str(self.path), "0.0", i) for i in range(16)]))
        self.assertEqual(set(ordinals), {f"0.0.{i}" for i in range(16)})
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TRIGGER fail_allocation BEFORE INSERT ON history WHEN NEW.kind='delegated' BEGIN SELECT RAISE(ABORT,'fixture rollback'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.child()
        self.assertEqual(len(self.store.branch("0.0")["records"]), 17)
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TRIGGER fail_allocation")
        self.assertEqual(self.child()["ordinal"], "0.0.16")

    def test_effort_scope_rejects_foreign_positions_everywhere(self):
        for operation in (
            lambda: self.store.position("0.1", scope=self.scope),
            lambda: self.store.delegate("0.1", scope=self.scope, mandate=MANDATE, origin="human", human_ref=HUMAN, source_ref=SOURCE),
            lambda: self.store.instantiate("0.1", scope=self.scope, native_ref={"agent": "foreign"}, source_ref=SOURCE),
            lambda: self.store.create_discipline("0.1", initiator="0.1", scope=self.scope,
                                                 definition_ref={"id": "P1-P4", "version": "1"}, intent="foreign", source_ref=SOURCE),
            lambda: self.store.resolve("0.1", scope=self.scope),
            lambda: self.store.branch("0.1", scope=self.scope),
            lambda: self.store.history("0.1", scope=self.scope),
        ):
            with self.assertRaises(ScopeError):
                operation()
        with self.assertRaises(ScopeError):
            self.store.delegate("0", scope=self.scope, mandate=MANDATE, origin="human", human_ref=HUMAN, source_ref=SOURCE)

    def test_genuine_delegation_records_exact_actual_delegator_and_mandate_versions(self):
        with self.assertRaises(ScopeError):
            self.store.delegate("0.0", scope=self.scope, mandate=MANDATE, origin="agent", source_ref=SOURCE)
        live = self.runtime()
        child = self.store.delegate("0.0", scope=self.scope, mandate={"purpose": "Research A", "conditions": ["A only"]},
                                    origin="agent", delegator=live, source_ref=SOURCE)
        self.assertEqual(child["parent"], "0.0")
        self.assertEqual(child["mandate"]["delegator"], live.as_dict())
        self.assertEqual(child["mandate"]["origin"], "agent")
        self.assertIsNone(child["mandate"]["human_ref"])
        self.assertEqual(child["mandate"]["parent_mandate_version"], 1)
        amended = self.store.revise_mandate(child["ordinal"], scope=self.scope,
                                            mandate={"purpose": "Research then review A"}, origin="human",
                                            human_ref=HUMAN, source_ref=SOURCE)
        self.assertEqual(amended["mandate_version"], 2)
        self.assertEqual(len(self.store.mandates(child["ordinal"], scope=self.scope)), 2)
        self.store.set_session_status(live, "closed", scope=self.scope, source_ref=SOURCE)
        with self.assertRaises(ScopeError):
            self.store.delegate("0.0", scope=self.scope, mandate=MANDATE, origin="agent", delegator=live, source_ref=SOURCE)

    def test_exact_sessions_succession_and_queued_action_cannot_redirect(self):
        first = self.runtime()
        action = self.store.bind_action("0.0", scope=self.scope, kind="prompt", payload={"text": "first occupant"}, source_ref=SOURCE)
        second_session = self.store.open_session("0.0", 1, scope=self.scope,
                                                 native_ref={"client": "fixture", "session_id": "second-context"}, source_ref=SOURCE)
        self.assertEqual(second_session, Target("0.0", 1, 2))
        self.assertEqual(self.store.resolve("0.0", scope=self.scope, instantiation=1, session=1), first)
        with self.assertRaises(ScopeError):
            self.store.instantiate("0.0", scope=self.scope, native_ref={"agent": "replacement"}, source_ref=SOURCE)
        successor = self.store.instantiate("0.0", scope=self.scope, native_ref={"agent": "replacement"},
                                           predecessor=1, handoff={"responsibility": "continue A", "context": "new"}, source_ref=SOURCE)
        self.assertEqual(successor["predecessor"], 1)
        current = self.store.open_session("0.0", 2, scope=self.scope,
                                          native_ref={"client": "fixture", "session_id": "third-context"}, source_ref=SOURCE)
        self.assertEqual(self.store.resolve("0.0", scope=self.scope), current)
        bound = self.store.action(action["id"], scope=self.scope)
        self.assertEqual(bound["target"], first.as_dict())
        self.assertEqual(bound["native_ref"]["session_id"], "native-0.0")
        self.assertEqual(bound["environment"], {"cwd": "/unrelated/a"})
        self.assertEqual(self.store.sessions("0.0", 1, scope=self.scope)[0]["native_ref"]["context_file"], "/fixture/0.0")
        self.assertEqual(self.store.instantiations("0.0", scope=self.scope)[0]["status"], "superseded")
        self.assertTrue(any(e["kind"] == "instantiated" for e in self.store.history("0.0", instantiation=1)["records"]))
        self.assertTrue(any(e["kind"] == "succeeded" for e in self.store.history("0.0", instantiation=2)["records"]))
        with self.assertRaises(ScopeError):
            self.store.resolve("0.0", scope=self.scope, session=1)
        with self.assertRaises(ScopeError):
            self.store.action(action["id"], scope=Scope.effort("0.1"))

    def test_root_coordination_retains_separate_named_effort_environments(self):
        scope = Scope.application(("0.0", "0.1"), root_mandate_version=1)
        event = self.store.coordinate(scope=scope, instructions=[{"ordinal": "0.0", "instruction": "Research A"},
                                                               {"ordinal": "0.1", "instruction": "Build B"}],
                                      origin="human", human_ref=HUMAN, source_ref=SOURCE)
        self.assertEqual([x["environment"]["cwd"] for x in event["data"]["instructions"]], ["/unrelated/a", "/unrelated/b"])
        self.assertEqual(event["data"]["root_mandate_version"], 1)
        self.assertEqual(event["data"]["origin"], "human")
        self.assertIsNone(self.store.position("0")["current_instantiation"])
        with self.assertRaises(ScopeError):
            self.store.coordinate(scope=scope, instructions=[{"ordinal": "0.2", "instruction": "wrong effort"}],
                                  origin="human", human_ref=HUMAN, source_ref=SOURCE)
        self.store.set_environment("0.0", scope=self.scope, environment={"cwd": "/a/revised"}, source_ref=SOURCE)
        self.assertEqual(event["data"]["instructions"][0]["environment"]["cwd"], "/unrelated/a")
        self.assertEqual(len(self.store.environments("0.0", scope=self.scope)), 2)

    def test_nested_discipline_positions_execution_and_native_refs_agree(self):
        initiator = self.runtime()
        first = self.store.create_discipline("0.0", scope=self.scope, initiator="0.0", initiating_target=initiator,
                                            definition_ref={"id": "P1-P4", "version": "native-1"}, intent="Investigate A", source_ref=SOURCE)
        second = self.store.create_discipline("0.0", scope=self.scope, initiator="0.0",
                                             definition_ref={"id": "P1-P4", "version": "native-1"}, intent="Another inquiry", source_ref=SOURCE)
        self.assertNotEqual(first["id"], second["id"])
        actor = self.store.delegate("0.0", scope=self.scope, mandate=MANDATE, origin="agent", delegator=initiator,
                                    discipline_id=first["id"], source_ref=SOURCE)
        actor_target = self.runtime(actor["ordinal"])
        nested = self.store.create_discipline("0.0", scope=self.scope, initiator=actor["ordinal"],
                                             definition_ref={"id": "development", "version": "1"}, intent="Implement insight",
                                             parent_instance=first["id"], source_ref=SOURCE)
        nested_actor = self.store.delegate(actor["ordinal"], scope=self.scope, mandate=MANDATE, origin="agent",
                                           delegator=actor_target, discipline_id=nested["id"], source_ref=SOURCE)
        nested_target = self.runtime(nested_actor["ordinal"])
        execution = self.store.create_execution(nested["id"], scope=self.scope, native_ref={"controller_run": "run-1"}, source_ref=SOURCE)
        activation = self.store.record_activation(execution["id"], scope=self.scope, participant=nested_target,
                                                  native_ref={"activation": "activation-7", "native_operation": "uninterpreted"},
                                                  result_ref={"artifact": "result-1", "standing": "native-only"}, source_ref=SOURCE)
        self.assertEqual(activation["target"], nested_target.as_dict())
        self.assertEqual(activation["discipline_id"], nested["id"])
        self.assertEqual(nested_actor["effort"], "0.0")
        self.assertEqual(nested_actor["parent"], actor["ordinal"])
        with self.assertRaises(ScopeError):
            self.child(discipline_id=9999)
        with self.assertRaises(ScopeError):
            self.store.record_activation(execution["id"], scope=self.scope, participant=initiator,
                                         native_ref={"activation": "wrong"}, source_ref=SOURCE)
        history = self.store.history("0", discipline_id=nested["id"])["records"]
        self.assertTrue(any(e["kind"] == "activation" and e["source_ref"] == SOURCE for e in history))
        foreign = self.store.create_discipline("0.1", scope=Scope.effort("0.1"), initiator="0.1",
                                              definition_ref={"id": "P1-P4", "version": "native-1"}, intent="B inquiry", source_ref=SOURCE)
        with self.assertRaises(ScopeError):
            self.store.history("0.0", scope=self.scope, discipline_id=foreign["id"])
        with self.assertRaises(ScopeError):
            self.child(discipline_id=foreign["id"])

    def test_global_and_exact_history_pagination_retains_failed_closed_superseded(self):
        live = self.runtime()
        self.store.set_session_status(live, "failed", scope=self.scope, source_ref={"native_event": "failure-1"})
        self.store.open_session("0.0", 1, scope=self.scope, native_ref={"session": "recovered"}, source_ref=SOURCE)
        child = self.child()
        self.store.close_position(child["ordinal"], scope=self.scope, source_ref=SOURCE)
        for index in range(12):
            self.store.record_event("0.1", scope=Scope.effort("0.1"), kind="native-observation",
                                     data={"i": index}, source_ref={"native_event": index})
        records, cursor = [], 0
        while True:
            page = self.store.history("0", after=cursor, limit=3)
            if not page["records"]:
                break
            records.extend(page["records"])
            self.assertGreater(page["next_after"], cursor)
            cursor = page["next_after"]
        self.assertEqual(records, self.store.history("0", limit=1000)["records"])
        self.assertEqual(len({e["sequence"] for e in records}), len(records))
        self.assertEqual({e["effort"] for e in records}, {None, "0.0", "0.1", "0.2"})
        exact = self.store.history("0.0", instantiation=1, session=1)["records"]
        self.assertTrue(any(e["source_ref"] == {"native_event": "failure-1"} for e in exact))
        self.assertEqual(self.store.sessions("0.0", 1)[0]["status"], "failed")
        branch, after = [], 0
        while True:
            page = self.store.branch("0", after=after, limit=2)
            if not page["records"]:
                break
            branch.extend(page["records"])
            after = page["next_after"]
        self.assertEqual({p["ordinal"] for p in branch}, {"0", "0.0", "0.1", "0.2", child["ordinal"]})

    def test_explicit_legacy_namespaces_adopt_two_roots_and_run_local_labels_truthfully(self):
        for namespace in ("conversation:old-a", "conversation:old-b", "controller:run-c"):
            self.store.register_legacy_namespace(namespace, native_ref={"store": namespace}, source_ref=SOURCE)
        for namespace, old, new, context in (("conversation:old-a", "0", "0.0", "old-native-a"),
                                              ("conversation:old-b", "0", "0.1", "old-native-b"),
                                              ("controller:run-c", "0.1", "0.0", "actor-1")):
            self.store.adopt_legacy(namespace, old, new, scope=Scope.effort(new),
                                    native_ref={"session_or_actor": context, "original_date": "2025-01-01"},
                                    source_ref={"historical_journal": namespace, "missing_parentage": True})
        mappings = self.store.legacy_mappings()
        self.assertEqual(ScopeStore(self.path).legacy_namespace("conversation:old-a")["native_ref"], {"store": "conversation:old-a"})
        self.assertEqual(len(mappings), 3)
        self.assertEqual({m["namespace"] for m in mappings}, {"conversation:old-a", "conversation:old-b", "controller:run-c"})
        self.assertTrue(all(m["adopted_at"] and m["original_parent"] is None for m in mappings))
        self.assertEqual(self.store.position("0.0")["origin"], "human")
        adoption = [e for e in self.store.history("0")["records"] if e["kind"] == "legacy-adopted"]
        self.assertEqual(len(adoption), 3)
        self.assertTrue(all(e["data"]["historical_delegation"] is False for e in adoption))
        with self.assertRaises(ScopeError):
            self.store.adopt_legacy("unknown", "0", "0.0", scope=self.scope, native_ref={"old": "missing"}, source_ref=SOURCE)
        self.assertEqual(len(self.store.legacy_mappings()), 3)

    def test_invalid_addresses_selectors_and_root_creation_fail_without_partial_state(self):
        for ordinal in ("0.00", "0.-1", "1", "0.1*", "0.1/2", "", None):
            with self.assertRaises(ScopeError):
                self.store.position(ordinal)
        for after in (-1, True, "1"):
            with self.assertRaises(ScopeError):
                self.store.history("0", after=after)
        with self.assertRaises(ScopeError):
            ScopeStore(Path(self.temp.name) / "unmandated.sqlite3")
        with self.assertRaises(ScopeError):
            self.store.delegate("0.0", scope=self.scope, mandate=MANDATE, origin="human", source_ref=SOURCE)
        self.assertEqual(self.child()["ordinal"], "0.0.0")


if __name__ == "__main__":
    unittest.main()
