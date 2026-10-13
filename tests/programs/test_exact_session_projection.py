import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.noetic_scope import Scope, ScopeStore
from scripts.noetic_sessions import SessionError, SessionService


class ExactSessionProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="noetic-exact-projection-")
        self.home = Path(self.temp.name)
        self.service = SessionService(self.home / "runs", namespace_path=self.home / "namespace.sqlite3", pi_command=["/bin/false"])
        self.root = self.service.create_effort({"intent": "Retained fixture", "environment": {"cwd": str(self.home)}})["ordinal"]
        self.other = self.service.create_effort({"intent": "Sibling fixture", "environment": {"cwd": str(self.home)}})["ordinal"]
        self.store = self.service.registry.domain.store()
        self.scope = Scope.effort(self.root)
        self.store.instantiate(self.root, scope=self.scope, native_ref={"fixture": "no-provider"}, source_ref={"fixture": "exact-projection"})

    def tearDown(self):
        self.temp.cleanup()

    def retained(self, number, status="closed"):
        row = self.service.registry.create(self.home, f"Retained {number}", "fixture", "off", [], ordinal=self.root, effort_root=self.root)
        target = self.store.open_session(self.root, 1, scope=self.scope, native_ref={"registry_id": row["id"], "fixture": "no-provider"}, source_ref={"fixture": "exact-projection"})
        self.service.registry.update(row["id"], instantiation=1, session_selector=target.session, status="closed" if status != "open" else "idle")
        if status != "open":
            self.store.set_session_status(target, status, scope=self.scope, source_ref={"fixture": "exact-projection"})
        return self.service.registry.get(row["id"]), target

    def test_list_and_exact_selection_never_materialize_retained_histories(self):
        rows = [self.retained(i)[0] for i in range(200)]
        with patch.object(ScopeStore, "sessions", side_effect=AssertionError("exact read loaded entire session history")), patch.object(ScopeStore, "instantiations", side_effect=AssertionError("exact read loaded entire instantiation history")):
            selected = self.service.select(rows[0]["target"], effort_root=self.root)
            self.assertEqual(selected["id"], rows[0]["id"])
            result = self.service.list()
        self.assertEqual({row["id"] for row in result}, {row["id"] for row in rows})
        self.assertTrue(all(row["domain_status"] == "closed" and not row["is_current"] and not row["broker_owned"] for row in result))
        self.assertTrue(all(not row["can_reopen"] and not row["process"]["cleanup_confirmed"] for row in result), "unknown process ownership must not grant reopen")

    def test_retained_current_and_foreign_scope_rules_remain_exact(self):
        old, target = self.retained(1)
        current, current_target = self.retained(2, "open")
        self.assertEqual(self.service.select(target.as_dict(), effort_root=self.root)["id"], old["id"])
        self.assertEqual(self.service.select(self.root, effort_root=self.root, current=True)["id"], current["id"])
        with self.assertRaises(SessionError) as superseded:
            self.service.select(target.as_dict(), effort_root=self.root, current=True)
        self.assertEqual(superseded.exception.status, 409)
        with self.assertRaises(SessionError) as foreign:
            self.service.select(current_target.as_dict(), effort_root=self.other)
        self.assertEqual(foreign.exception.status, 400)
        inspected = self.service.inspect(current["id"])
        self.assertEqual(inspected["target"], current_target.as_dict())
        self.assertTrue(inspected["is_current"])
        self.assertEqual(inspected["status"], "interrupted", "domain designation does not invent broker liveness")
        self.assertFalse(inspected["broker_owned"])

    def test_native_registry_equality_and_legacy_identity_remain_required(self):
        first, target = self.retained(1)
        second, _ = self.retained(2)
        with self.store._write() as db:
            db.execute("UPDATE sessions SET native_ref=? WHERE ordinal=? AND instantiation=? AND sequence=?", ('{"registry_id":"' + second["id"] + '"}', self.root, 1, target.session))
        with self.assertRaises(SessionError) as mismatch:
            self.service.select(target.as_dict(), effort_root=self.root)
        self.assertEqual(mismatch.exception.status, 409)
        legacy = self.service.registry.create(self.home, "Original source", "fixture", "off", [], ordinal="0.1", effort_root=None)
        inspected = self.service.inspect(legacy["id"])
        self.assertEqual(inspected["id"], legacy["id"])
        self.assertEqual(inspected["original_ordinal"], legacy["original_ordinal"])
        self.assertIsNone(inspected["target"])
        self.assertFalse(inspected["is_current"])
        with self.assertRaises(SessionError):
            self.service.select(legacy["id"], current=True)

    def test_exact_projection_is_one_fresh_namespace_snapshot(self):
        row, target = self.retained(1)
        context = self.store.resolve_context(self.root, scope=self.scope, instantiation=1, session=target.session)
        self.assertEqual(context["target"], target.as_dict())
        self.assertEqual(context["session"]["native_ref"]["registry_id"], row["id"])
        self.assertEqual(context["instantiation"]["sequence"], 1)
        self.store.revise_mandate(self.root, scope=self.scope, mandate={"purpose": "Changed fixture"}, origin="human", human_ref={"owner": "fixture"}, source_ref={"fixture": "freshness"})
        fresh = self.store.resolve_context(self.root, scope=self.scope, instantiation=1, session=target.session)
        self.assertEqual(fresh["position"]["mandate_version"], 2)
        self.assertEqual(fresh["position"]["mandate"]["mandate"], {"purpose": "Changed fixture"})
        self.assertEqual(context["position"]["mandate_version"], 1)


if __name__ == "__main__":
    unittest.main()
