"""Reuse owned-purpose history as an unbound draft in disposable real stores."""
from contextlib import closing, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from scripts import noetic_application as application
from scripts import noetic_controller as controller
from scripts import noetic_disciplines as disciplines
from scripts import noetic_harness as harness
from scripts import noetic_purpose_binding as purpose_binding
from scripts import noetic_run as runtime
from scripts import noetic_telos as telos
from scripts.noetic_purposes import Purposes
from scripts.noetic_scope import Scope, ScopeStore


class PurposeReuseSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="purpose-reuse-native-")
        cls.addClassCleanup(cls.build.cleanup)
        cls.source = Path(cls.build.name) / "configured-telos.mjs"
        telos.bundle_goal_store(telos.source_path(), cls.source)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="purpose-reuse-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.runs = self.root / "runs"
        self.namespace = self.root / "namespace.sqlite3"
        store = ScopeStore(self.namespace, root_mandate={"purpose": "Coordinate fixtures"},
                           human_ref={"fixture": "owner"}, source_ref={"fixture": "root"})
        self.effort = store.create_effort(intent="Fixture effort", environment={"cwd": str(self.workspace)},
            mandate={"purpose": "Fixture purpose"}, origin="human", human_ref={"fixture": "owner"},
            source_ref={"fixture": "effort"})["ordinal"]
        instance = disciplines.Disciplines(self.namespace).create_instance(command_id="fixture", effort_root=self.effort,
            initiator=self.effort, pattern="cognition", intent="Fixture", environment={"cwd": str(self.workspace)})
        self.request = {"namespace_path": str(self.namespace), "effort_root": self.effort,
            "discipline_id": instance["id"], "environment": instance["environment"],
            "origin": "human", "human_ref": {"fixture": "owner"}}
        self.purposes = Purposes(self.namespace, purposes_root=self.root / "custom-purpose-stores", source=self.source)
        self.reference = self.purposes.create("Historical governing purpose", scope=Scope.effort(self.effort),
            origin_ref={"fixture": "owner"}, source_ref={"fixture": "purpose"})["reference"]
        guard = patch.object(harness, "actor_command", side_effect=AssertionError("Fixture must not invoke an actor"))
        guard.start()
        self.addCleanup(guard.stop)

    def start(self, *, owned=True, legacy=False, scoped=False):
        kwargs = {"scope_request": self.request, "purpose_ref": self.reference,
                  "purpose_config": purpose_binding.configuration(self.purposes)} if owned else {}
        if scoped:
            kwargs["scope_request"] = self.request
        if legacy:
            kwargs = {"telos_chain": self.reference["chain_id"], "telos_db": self.reference["db_path"],
                      "telos_source": self.reference["source"]}
        with redirect_stdout(io.StringIO()):
            return harness.start("cognition", "  Bounded task\nwith criteria  ", self.workspace, self.runs,
                client="opencode", model="fixture/main", qa_model="fixture/qa", thinking="high", timeout=123,
                max_returns=0, max_remediations=0, max_activations=0,
                inputs={"sources": [{"ref": "docs/a file.md"}, {"ref": "docs/a file.md"}]}, **kwargs)

    def snapshot(self):
        return {str(p.relative_to(self.root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                for p in self.root.rglob("*") if p.is_file()}

    def reuse(self, run, state):
        status = runtime.project(runtime.read_events(run))
        before = self.snapshot()
        with patch.object(harness, "start", side_effect=AssertionError("Reuse must not start")), \
                patch.object(harness, "drive", side_effect=AssertionError("Reuse must not drive")), \
                patch.object(harness, "resume", side_effect=AssertionError("Reuse must not resume")), \
                patch.object(telos, "_bridge", side_effect=AssertionError("Reuse must not call native Telos")), \
                patch.object(application.subprocess, "Popen", side_effect=AssertionError("Reuse must not spawn")):
            try:
                return application.reuse_setup(run, state, status)
            finally:
                self.assertEqual(self.snapshot(), before)

    def assert_unbound(self, setup, run, state):
        self.assertEqual(setup["source_run_id"], run.name)
        self.assertEqual(setup["fields"], {
            "pattern": "cognition", "client": "opencode", "thinking": "high", "timeout": 123,
            "verify": None, "max_returns": 0, "max_remediations": 0,
            "model": "fixture/main", "qa_model": "fixture/qa", "task": state["purpose"],
            "workspace": str(self.workspace), "telos_chain": None,
            "sources": ["docs/a file.md", "docs/a file.md"]})
        self.assertIn("Choose a current purpose explicitly", " ".join(setup["warnings"]))
        self.assertNotIn("Historical governing purpose", json.dumps(setup))
        for key in ("purpose_ref", "purpose_config", "goal_ref", "subgoal", "sessions", "actors", "scope"):
            self.assertNotIn(key, setup["fields"])

    def test_owned_reference_with_custom_resolver_projects_readonly_unbound_draft(self):
        run, state = self.start()
        setup = self.reuse(run, state)
        self.assert_unbound(setup, run, state)
        self.assertEqual(setup["source_telos_chain"], self.reference["chain_id"])

    def test_unavailable_historical_store_and_component_do_not_block_projection(self):
        run, state = self.start()
        Path(self.reference["db_path"]).unlink()
        retained = self.source.with_suffix(".retained")
        self.source.rename(retained)
        try:
            self.assert_unbound(self.reuse(run, state), run, state)
            self.assertFalse(self.source.exists())
        finally:
            retained.rename(self.source)
        self.assertFalse(Path(self.reference["db_path"]).exists())

    def test_reference_resolver_and_scalar_substitutions_refuse_without_effects(self):
        run, state = self.start()
        path = run / "options.json"
        original = json.loads(path.read_text())
        substitutions = []
        for field, value in (("owner", {**self.reference["owner"], "ordinal": "0.999"}),
                             ("store_id", "foreign/store"), ("db_path", str(self.root / "foreign.sqlite3")),
                             ("chain_id", "foreign-chain"), ("source", str(self.root / "foreign.mjs"))):
            changed = deepcopy(original)
            changed["purpose_ref"][field] = value
            substitutions.append(changed)
        for field, value in (("namespace_path", str(self.root / "foreign-namespace.sqlite3")),
                             ("purposes_root", str(self.root / "foreign")), ("source", "relative.mjs"),
                             ("legacy_db", 123)):
            changed = deepcopy(original)
            changed["purpose_config"][field] = value
            substitutions.append(changed)
        for field in ("purpose_ref", "purpose_config"):
            changed = deepcopy(original)
            changed.pop(field)
            substitutions.append(changed)
            changed = deepcopy(original)
            changed[field] = None
            substitutions.append(changed)
        changed = deepcopy(original)
        changed.pop("purpose_ref")
        changed.pop("purpose_config")
        substitutions.append(changed)
        for field in ("telos_chain", "telos_db", "telos_source", "goal_ref"):
            substitutions.append({**original, field: "foreign"})
        for changed in substitutions:
            with self.subTest(options=changed):
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(application.ApplicationError, "Reuse setup unsupported.*Draft unchanged") as raised:
                    self.reuse(run, state)
                self.assertEqual(raised.exception.status, 422)

    def test_governing_snapshot_and_native_receipt_mismatches_refuse(self):
        run, state = self.start()
        changed = deepcopy(state)
        changed["artifacts"][changed["slots"]["external.governing"]]["content"]["purpose_ref"] = {}
        with self.assertRaisesRegex(application.ApplicationError, "Reuse setup unsupported"):
            self.reuse(run, changed)
        runtime.record(run, "telos.linked", {"chain_id": "foreign", "db_path": self.reference["db_path"],
                                             "source": self.reference["source"]})
        with self.assertRaisesRegex(application.ApplicationError, "Reuse setup unsupported"):
            self.reuse(run, state)

    def test_missing_or_duplicate_owned_receipt_refuses(self):
        run, state = self.start()
        with closing(sqlite3.connect(run / "events.sqlite3")) as db:
            receipt = db.execute("SELECT data FROM events WHERE kind='purpose.bound'").fetchone()[0]
            db.execute("DELETE FROM events WHERE kind='purpose.bound'")
            db.commit()
        with self.assertRaisesRegex(application.ApplicationError, "Reuse setup unsupported"):
            self.reuse(run, state)
        runtime.record(run, "purpose.bound", json.loads(receipt))
        runtime.record(run, "purpose.bound", json.loads(receipt))
        with self.assertRaisesRegex(application.ApplicationError, "Reuse setup unsupported"):
            self.reuse(run, state)

    def test_legacy_bare_chain_and_no_purpose_remain_projectable(self):
        for legacy, scoped in ((False, False), (False, True), (True, False)):
            with self.subTest(legacy=legacy, scoped=scoped):
                run, state = self.start(owned=False, legacy=legacy, scoped=scoped)
                setup = self.reuse(run, state)
                self.assert_unbound(setup, run, state)
                self.assertEqual(setup["source_telos_chain"], self.reference["chain_id"] if legacy else None)

    def test_existing_form_and_frozen_history_refusals_remain(self):
        run, state = self.start()
        path = run / "options.json"
        options = json.loads(path.read_text())
        for change in ({"unknown": 1}, {"client": "other"}, {"timeout": 1.5}, {"max_returns": True},
                       {"max_remediations": 21}, {"verify": []}, {"model": "line\nbreak"}):
            with self.subTest(change=change):
                path.write_text(json.dumps({**options, **change}))
                with self.assertRaisesRegex(application.ApplicationError, "Reuse setup unsupported"):
                    self.reuse(run, state)
        path.write_text(json.dumps(options))
        changed = deepcopy(state)
        changed["pattern"]["name"] = "Historical pattern"
        with self.assertRaisesRegex(application.ApplicationError, "historical pattern differs"):
            self.reuse(run, changed)
        changed = deepcopy(state)
        changed["artifacts"][changed["slots"]["external.sources"]]["content"] = [{"ref": "x", "content": "rich"}]
        with self.assertRaisesRegex(application.ApplicationError, "ref-only sources"):
            self.reuse(run, changed)


if __name__ == "__main__":
    unittest.main()
