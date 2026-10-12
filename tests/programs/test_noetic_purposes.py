"""Disposable ownership checks against the actual native Telos component."""

from contextlib import closing, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import noetic_run as runtime
from scripts import noetic_telos as telos
from scripts.noetic_scope import Scope, ScopeStore
from scripts.noetic_purposes import PurposeError, Purposes


class PurposeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native_source = telos.source_path()
        cls.build = tempfile.TemporaryDirectory(prefix="purpose-native-")
        cls.addClassCleanup(cls.build.cleanup)
        cls.source = Path(cls.build.name) / "native.mjs"
        # Failure is a concrete dependency blocker, never mocked native success.
        telos.bundle_goal_store(cls.native_source, cls.source)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="purpose-owned-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.namespace_path = self.root / "app/state/ordinals.sqlite3"
        self.store = ScopeStore(self.namespace_path, root_mandate={"purpose": "Coordinate trials"},
                                human_ref={"person": "test-owner"}, source_ref={"test": "root"})
        self.efforts = [self.store.create_effort(
            intent=name, environment={"cwd": str(self.root / "same-cwd")},
            mandate={"purpose": name}, origin="human", human_ref={"person": "test-owner"},
            source_ref={"test": name})["ordinal"] for name in ("A", "B", "R")]
        self.global_scope = Scope.application(self.efforts, root_mandate_version=1)
        self.legacy_db = self.root / "legacy/telos.sqlite3"
        self.adapter = Purposes(self.namespace_path, source=self.source, legacy_db=self.legacy_db)
        environment = patch.dict(os.environ, {"NOETIC_APP_HOME": str(self.root / "inherited-app"),
                                              "TELOS_STATE_DIR": str(self.root / "unused-native-state")})
        environment.start()
        self.addCleanup(environment.stop)
        self.addCleanup(lambda: self.assertFalse((self.root / "inherited-app").exists()))
        self.addCleanup(lambda: self.assertFalse((self.root / "unused-native-state").exists()))

    def create(self, ordinal, goal="Purpose"):
        scope = self.global_scope if ordinal == "0" else Scope.effort(ordinal)
        return self.adapter.create(goal, scope=scope, origin_ref={"human": "test-owner"},
                                   source_ref={"test": "purpose-creation"})

    def cli(self, *arguments):
        env = os.environ.copy()
        env.pop("USER_PROVIDED_PASSWORD", None)
        return subprocess.run([sys.executable, "-m", "scripts.noetic_purposes", "--namespace",
                               str(self.namespace_path), "--source", str(self.source),
                               "--legacy-db", str(self.legacy_db), *arguments],
                              capture_output=True, text=True, timeout=30, env=env)

    def test_same_directory_owners_reopen_and_application_aggregation(self):
        created = [self.create(owner, name) for owner, name in zip([*self.efforts, "0"], ["A", "B", "R", "Global"])]
        references = [item["reference"] for item in created]
        self.assertEqual(len({item["db_path"] for item in references}), 4)
        self.assertEqual(len({item["chain_id"] for item in references}), 4)
        fresh = Purposes(self.namespace_path, source=self.source, legacy_db=self.legacy_db)
        for owner, original in zip([*self.efforts, "0"], created):
            scope = self.global_scope if owner == "0" else Scope.effort(owner)
            reopened = fresh.resolve(original["reference"], scope=scope)
            self.assertEqual(reopened["native"], original["native"])
            self.assertEqual(reopened["ownership_event"]["source_ref"], {"test": "purpose-creation"})
            self.assertEqual(reopened["ownership_event"]["data"]["origin_ref"], {"human": "test-owner"})
            resolved = self.cli("resolve-run", json.dumps(original["reference"]),
                                *( ["--application", "--root-mandate-version", "1"] if owner == "0"
                                   else ["--effort", owner]))
            self.assertEqual(resolved.returncode, 0, resolved.stderr)
            self.assertEqual(json.loads(resolved.stdout)["db_path"], original["reference"]["db_path"])
        read = self.cli("list", "--application", "--root-mandate-version", "1",
                        "--target-effort", self.efforts[0], "--target-effort", self.efforts[1],
                        "--target-effort", self.efforts[2])
        self.assertEqual(read.returncode, 0, read.stderr)
        result = json.loads(read.stdout)
        self.assertEqual(result["coverage"], "complete")
        self.assertEqual({p["reference"]["chain_id"] for p in result["purposes"]},
                         {p["chain_id"] for p in references})
        selected = fresh.list(scope=Scope.effort(self.efforts[0]))
        self.assertEqual([p["native"]["chain"]["primaryGoal"] for p in selected["purposes"]], ["A"])

    def test_foreign_chain_store_owner_namespace_and_bare_uuid_refused(self):
        a, b = self.efforts[:2]
        purpose = self.create(a)
        ref = purpose["reference"]
        for altered in (ref, {**ref, "owner": {**ref["owner"], "ordinal": b}},
                        {**ref, "db_path": str(self.legacy_db)},
                        {**ref, "source": str(self.root / "foreign-native.mjs")},
                        {**ref, "owner": {**ref["owner"], "namespace": "foreign"}}, ref["chain_id"]):
            with self.subTest(reference=altered), self.assertRaises(PurposeError):
                self.adapter.resolve_run(altered, scope=Scope.effort(b))
        owned_b = self.create(b)["reference"]
        with self.assertRaises(PurposeError) as missing:
            self.adapter.resolve({**owned_b, "chain_id": ref["chain_id"]}, scope=Scope.effort(b))
        self.assertEqual(missing.exception.code, "chain_not_found")

    def test_reads_leave_namespace_legacy_and_absent_stores_unchanged(self):
        before = self.namespace_path.read_bytes()
        legacy = telos.create_goal("External recovery history", self.legacy_db, self.source)
        legacy_before = self.legacy_db.read_bytes()
        report = self.adapter.list(scope=self.global_scope, include_legacy=True)
        self.assertEqual(self.namespace_path.read_bytes(), before)
        self.assertEqual(self.legacy_db.read_bytes(), legacy_before)
        result = subprocess.run([sys.executable, "-m", "scripts.noetic_purposes", "--namespace-path",
                                 str(self.root / "missing/ordinals.sqlite3"), "--source", str(self.source),
                                 "--legacy-db", str(self.legacy_db), "list-unassigned"],
                                capture_output=True, text=True, timeout=30,
                                env={k: v for k, v in os.environ.items() if k != "USER_PROVIDED_PASSWORD"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["purposes"][0]["native"], legacy)
        self.assertFalse((self.root / "missing").exists())
        self.assertFalse(self.adapter.purposes_root.exists())
        self.assertEqual([s["status"] for s in report["stores"]], ["absent"] * 4 + ["available"])
        unassigned = report["purposes"][0]
        self.assertEqual(unassigned["reference"]["owner"]["kind"], "legacy-unassigned")
        self.assertEqual(unassigned["native"], legacy)
        self.assertIsNone(unassigned["ownership_event"])
        with self.assertRaises(PurposeError):
            self.adapter.resolve_run(unassigned["reference"], scope=self.global_scope)
        with self.assertRaises(PurposeError):
            self.adapter.list(scope=Scope.effort(self.efforts[0]), include_legacy=True)
        missing = Purposes(self.root / "missing/ordinals.sqlite3", source=self.source)
        with self.assertRaises(PurposeError) as absent:
            missing.list(scope=Scope.effort(self.efforts[0]))
        self.assertEqual(absent.exception.code, "namespace_absent")
        self.assertFalse((self.root / "missing").exists())
        unregistered = Purposes(self.root / "missing/ordinals.sqlite3", legacy_db=self.legacy_db, source=self.source)
        historical = unregistered.list_unassigned()
        self.assertEqual(historical["purposes"][0]["native"], legacy)
        self.assertEqual(historical["purposes"][0]["reference"]["owner"]["kind"], "legacy-unassigned")
        self.assertFalse((self.root / "missing").exists())
        self.assertEqual(self.legacy_db.read_bytes(), legacy_before)

    def test_absent_corrupt_incomplete_and_unavailable_are_distinct(self):
        a = self.efforts[0]
        absent = self.adapter.list(scope=Scope.effort(a))
        self.assertEqual(absent["stores"][0]["status"], "absent")
        purpose = self.create(a)
        db_path = Path(purpose["reference"]["db_path"])
        original = db_path.read_bytes()
        for contents in (b"corrupt", b""):
            db_path.write_bytes(contents)
            report = self.adapter.list(scope=Scope.effort(a))
            self.assertEqual(report["coverage"], "partial")
            self.assertEqual(report["stores"][0]["error"]["code"], "store_corrupt")
            self.assertEqual(report["purposes"], [])
            self.assertEqual(db_path.read_bytes(), contents)
            with self.assertRaises(PurposeError):
                self.create(a)
        db_path.write_bytes(original)
        with closing(sqlite3.connect(db_path)) as db:
            with db:
                db.execute("DROP TABLE records")
        report = self.adapter.list(scope=Scope.effort(a))
        self.assertEqual(report["stores"][0]["error"]["code"], "store_corrupt")
        db_path.write_bytes(original)
        unavailable = Purposes(self.namespace_path, source=self.root / "missing-module.mjs")
        report = unavailable.list(scope=Scope.effort(a))
        self.assertEqual(report["stores"][0]["error"]["code"], "native_unavailable")
        self.assertEqual(db_path.read_bytes(), original)

    def test_existing_effort_and_explicit_current_application_scope_required(self):
        before = self.namespace_path.read_bytes()
        for scope in (Scope.effort("0.99"), Scope.effort("0"),
                      Scope.application([self.efforts[0]], root_mandate_version=2)):
            with self.subTest(scope=scope), self.assertRaises(PurposeError):
                self.adapter.create("Refuse", scope=scope, origin_ref={"human": "test"},
                                    source_ref={"test": "rejected"})
        with self.assertRaises(PurposeError):
            self.adapter.create("Refuse", scope=Scope.effort(self.efforts[0]), owner="0",
                                origin_ref={"human": "test"}, source_ref={"test": "rejected"})
        with self.assertRaises(PurposeError):
            self.adapter.create("Refuse", scope=Scope.application([], root_mandate_version=1),
                                owner=self.efforts[0], origin_ref={"human": "test"},
                                source_ref={"test": "rejected"})
        self.assertEqual(self.namespace_path.read_bytes(), before)
        self.assertFalse(self.adapter.purposes_root.exists())

    def test_every_factory_managed_table_is_required_before_read_or_create(self):
        a = self.efforts[0]
        scope = Scope.effort(a)
        for source in (self.source, self.native_source):
            with self.subTest(source=source):
                adapter = Purposes(self.namespace_path, purposes_root=self.root / source.name, source=source)
                purpose = adapter.create("Native completeness", scope=scope, origin_ref={"human": "test"},
                                         source_ref={"test": "all-native-tables"})
                db_path = Path(purpose["reference"]["db_path"])
                original = db_path.read_bytes()
                with closing(sqlite3.connect(db_path)) as db:
                    tables = [row[0] for row in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
                self.assertIn("sessions", tables)
                for table in tables:
                    with self.subTest(table=table):
                        db_path.write_bytes(original)
                        with closing(sqlite3.connect(db_path)) as db:
                            with db:
                                db.execute('DROP TABLE "' + table.replace('"', '""') + '"')
                        incomplete = db_path.read_bytes()
                        namespace_before = self.namespace_path.read_bytes()
                        report = adapter.list(scope=scope)
                        self.assertEqual(report["coverage"], "partial")
                        self.assertEqual(report["stores"][0]["status"], "error")
                        self.assertEqual(report["stores"][0]["error"]["code"], "store_corrupt")
                        self.assertEqual(report["purposes"], [])
                        with self.assertRaises(PurposeError) as refused:
                            adapter.create("Do not repair implicitly", scope=scope, origin_ref={"human": "test"},
                                           source_ref={"test": "rejected"})
                        self.assertEqual(refused.exception.code, "store_corrupt")
                        self.assertEqual(db_path.read_bytes(), incomplete)
                        self.assertEqual(self.namespace_path.read_bytes(), namespace_before)
                db_path.write_bytes(original)
                self.assertEqual(adapter.resolve(purpose["reference"], scope=scope)["native"], purpose["native"])

    def test_resolved_binding_preserves_run_subgoal_and_memory_receipt_order(self):
        a = self.efforts[0]
        purpose = self.create(a)
        binding = self.adapter.resolve_run(purpose["reference"], scope=Scope.effort(a))
        plan = runtime.validate_plan({"goal": "Owned result", "work": [sys.executable, "-c", "print(42)"],
                                      "verify": [sys.executable, "-c", "assert 6 * 7 == 42"], "timeout_seconds": 10})
        with redirect_stdout(io.StringIO()):
            run_dir = runtime.create_run(plan, self.root, self.root / "runs")
        native_args = (binding["chain_id"], run_dir, binding["db_path"], binding["source"])
        link = telos.begin_run(*native_args)
        self.assertEqual(telos.begin_run(*native_args)["subgoal_id"], link["subgoal_id"])
        for step in ("work", "verify"):
            self.assertEqual(runtime.execute_step(run_dir, self.root, step, plan[step], 10), "passed")
        runtime.record(run_dir, "run.finished", {"state": "awaiting_review"})
        evidence = self.root / "evidence.txt"
        evidence.write_text("Observed work output and passing arithmetic verification.")
        runtime.review_run(run_dir, "accept", "fixture-independent-reviewer", evidence)
        (run_dir / "opermem-link.json").write_text(json.dumps({"operation": "retain"}))
        def record():
            return telos.record_result(binding["chain_id"], link["subgoal_id"], run_dir,
                                       binding["db_path"], binding["source"])
        pending = record()
        self.assertEqual(pending["subgoal_status"], "active")
        self.assertEqual(pending["opermem"]["submission"], "pending")
        (run_dir / "opermem-receipt.json").write_text(json.dumps({"response": {
            "class": "success", "kind": "command-accepted", "payload": {"receipt_id": "fixture-native-receipt"}}}))
        completed = record()
        self.assertEqual(completed["subgoal_status"], "complete")
        reopened = self.adapter.resolve(purpose["reference"], scope=Scope.effort(a))["native"]
        self.assertEqual(reopened["chain"]["chainId"], binding["chain_id"])
        self.assertEqual(reopened["chain"]["status"], "active")
        self.assertEqual([(s["subGoalId"], s["status"]) for s in reopened["subGoals"]],
                         [(link["subgoal_id"], "complete")])
        self.assertTrue(any("fixture-native-receipt" in r["details"] for r in reopened["records"]))

    def test_native_source_runtime_and_development_credential_exclusion(self):
        node = shutil.which("node")
        wrapper = self.root / "bin/node"
        wrapper.parent.mkdir()
        wrapper.write_text(f"#!{sys.executable}\nimport os,sys\n"
                           "assert 'USER_PROVIDED_PASSWORD' not in os.environ\n"
                           f"os.execv({node!r}, [{node!r}, *sys.argv[1:]])\n")
        wrapper.chmod(0o700)
        adapter = Purposes(self.namespace_path, source=self.native_source)
        with patch.dict(os.environ, {"PATH": str(wrapper.parent) + os.pathsep + os.environ["PATH"],
                                     "USER_PROVIDED_PASSWORD": "development-sentinel"}):
            created = adapter.create("Native source", scope=Scope.effort(self.efforts[0]),
                                     origin_ref={"human": "test"}, source_ref={"test": "source-runtime"})
            reopened = adapter.resolve(created["reference"], scope=Scope.effort(self.efforts[0]))
        self.assertEqual(reopened["native"], created["native"])


if __name__ == "__main__":
    unittest.main()
