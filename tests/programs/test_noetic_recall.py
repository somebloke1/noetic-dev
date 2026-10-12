"""Disposable native SQLite/Registry and HTTP boundary checks; no model or real state."""
from contextlib import closing, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from scripts import noetic_local as local
from scripts import noetic_memory as memory
from scripts import noetic_recall as recall
from scripts import noetic_run as runtime
from scripts import noetic_semantic as semantic
from scripts import noetic_sessions as native
from scripts.noetic_scope import Scope, ScopeError, ScopeStore, Target


class ScopedRecallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="noetic-owned-recall-")
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.runs = self.home / "runs"
        self.runs.mkdir(mode=0o700)
        self.path = self.home / "namespace.sqlite3"
        self.source = {"fixture": "native-store"}
        self.human = {"owner": "fixture-human"}
        self.store = ScopeStore(self.path, root_mandate={"purpose": "fixture root"},
                                human_ref=self.human, source_ref=self.source)
        self.a = self.effort("Aonly")
        self.b = self.effort("Bforeign")
        self.registry = native.Registry(self.home, namespace_path=self.path)
        self.first = self.session(self.a, "Aonly first")
        self.other = self.session(self.b, "Bforeign final")

    def effort(self, intent):
        return self.store.create_effort(intent=intent, environment={"cwd": str(self.home)},
            mandate={"purpose": intent}, origin="human", human_ref=self.human, source_ref=self.source)["ordinal"]

    def session(self, ordinal, text, root=None):
        item = self.registry.create(self.home, "fixture title", "fixture/model", "high", ["unused"],
                                    ordinal=ordinal, effort_root=root or ordinal)
        context = self.home / (item["id"] + ".jsonl")
        context.write_text(json.dumps({"type": "session", "id": item["id"]}) + "\n")
        self.registry.update(item["id"], native_session_id=item["id"], native_session_file=str(context))
        self.registry.attach(item["id"], {"sessionId": item["id"], "sessionFile": str(context)})
        self.registry.event(item["id"], "command", {"type": "prompt", "message": text + " requested"})
        self.registry.event(item["id"], "event", {"type": "message_update", "assistantMessageEvent": {"delta": "streamghost"}})
        self.registry.event(item["id"], "event", {"type": "message_end", "message": {
            "role": "assistant", "content": [{"type": "text", "text": text}]}})
        return self.registry.get(item["id"])

    def collect(self, selection):
        return recall.collect(namespace_path=self.path, sessions_home=self.home, runs_dir=self.runs, selection=selection)

    def owned(self, root=None):
        return self.collect({"kind": "effort", "effort_root": root or self.a})

    def results(self, collection, query):
        with closing(sqlite3.connect(":memory:")) as db:
            memory.index_scoped(db, collection)
            return memory.search_scoped(db, query, identity=collection["identity"])

    def test_same_folder_efforts_and_exact_reopened_historical_sessions(self):
        scope = Scope.effort(self.a)
        self.store.set_session_status(Target(**self.first["target"]), "failed", scope=scope, source_ref=self.source)
        second = self.session(self.a, "Areopened final")
        child = self.store.delegate(self.a, scope=scope, mandate={"purpose": "child"}, origin="human",
                                    human_ref=self.human, source_ref=self.source)["ordinal"]
        nested = self.session(child, "Adescendant final", root=self.a)
        collection = self.owned()
        self.assertFalse(collection["diagnostics"])
        self.assertFalse(self.results(collection, "Bforeign")["results"])
        first = self.results(collection, "first")["results"]
        self.assertTrue(first)
        self.assertTrue(all(row["historical"] and row["session_status"] == "failed" for row in first))
        exact = self.collect({"kind": "session", **self.first["target"], "effort_root": self.a})
        self.assertTrue(self.results(exact, "first")["results"])
        self.assertFalse(self.results(exact, "Areopened")["results"])
        self.assertFalse(self.results(exact, "Adescendant")["results"])
        # Same numeric selectors at a descendant do not join exact-session recall.
        self.assertEqual(nested["target"]["session"], self.first["target"]["session"])
        self.assertNotEqual(second["target"]["session"], self.first["target"]["session"])
        self.assertFalse(self.results(collection, "streamghost")["results"])
        self.assertEqual({row["effort_root"] for row in collection["sources"]}, {self.a})
        for row in self.results(exact, "first")["results"]:
            self.assertEqual(row["target"], self.first["target"])
            self.assertTrue(row["source_ref"]["sequence"])
            self.assertEqual(row["semantic_authority"], "none")

    def test_all_journal_pages_and_invalid_scope_fail_before_content_collection(self):
        with closing(self.registry.connect()) as db, db:
            db.executemany("INSERT INTO events(session_id,at,direction,record) VALUES(?,?,?,?)",
                [(self.first["id"], native.now(), "event", json.dumps({"type": "message_end", "message": {
                    "content": [{"type": "text", "text": f"pagefixture {index}"}]}})) for index in range(1105)])
        result = self.owned()
        self.assertGreater(result["coverage"]["developer_events_scanned"], 1105)
        tail = self.results(result, "pagefixture 1104")["results"]
        self.assertEqual(len(tail), 1)
        self.assertGreater(tail[0]["event_sequence"], 1000)
        self.assertEqual(tail[0]["source_ref"]["session_id"], self.first["id"])
        with self.assertRaisesRegex(ScopeError, "different effort"):
            self.collect({"kind": "session", **self.other["target"], "effort_root": self.a})
        with self.assertRaisesRegex(ScopeError, "does not exist"):
            self.collect({"kind": "ordinal", "ordinal": self.a + ".999", "effort_root": self.a})

    def test_readonly_explicit_namespace_and_missing_corrupt_disclosure(self):
        before = self.path.read_bytes()
        with patch.dict(os.environ, {"NOETIC_APP_HOME": str(self.home / "unrelated")}):
            collection = self.owned()
        self.assertEqual(collection["identity"]["namespace"]["path"], str(self.path))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse((self.home / "unrelated").exists())
        missing = self.home / "missing.sqlite3"
        with self.assertRaisesRegex(ScopeError, "Cannot resolve"):
            recall.collect(namespace_path=missing, sessions_home=self.home, runs_dir=self.runs, selection={"kind": "effort", "effort_root": self.a})
        self.assertFalse(missing.exists())
        damaged = self.home / "corrupt.sqlite3"
        damaged.write_bytes(b"not SQLite")
        with self.assertRaises(ScopeError):
            recall.collect(namespace_path=damaged, sessions_home=self.home, runs_dir=self.runs, selection={"kind": "application"})
        self.registry.path.write_bytes(b"not SQLite")
        result = self.owned()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["coverage"]["developer_journal"], "unavailable")
        self.assertEqual(result["diagnostics"][0]["component"], "developer-registry")

    def test_registry_native_mismatch_is_disclosed_without_foreign_fallback(self):
        with closing(self.registry.connect()) as db, db:
            db.execute("UPDATE sessions SET native_session_id='mismatched' WHERE id=?", (self.first["id"],))
        result = self.owned()
        self.assertTrue(result["diagnostics"])
        self.assertFalse(any(source.get("registry_id") == self.first["id"] for source in result["sources"]))
        self.assertFalse(self.results(result, "Bforeign")["results"])

    def test_application_retains_legacy_unassigned_with_scope_exclusion(self):
        with redirect_stdout(io.StringIO()):
            legacy = runtime.create_run({"goal": "legacyorphan retained"}, self.home, self.runs)
        (legacy / "work.md").write_text("legacyorphan report")
        row = self.registry.create(self.home, "legacy", "fixture/model", "high", ["unused"],
                                   ordinal="0", effort_root=None)
        self.registry.event(row["id"], "command", {"type": "prompt", "message": "legacyconversation retained"})
        scoped = self.owned()
        self.assertFalse(self.results(scoped, "legacyorphan")["results"])
        self.assertGreaterEqual(scoped["coverage"]["unassigned_excluded"], 2)
        application = self.collect({"kind": "application"})
        self.assertTrue(self.results(application, "Bforeign")["results"])
        unassigned = self.results(application, "legacyorphan")["results"]
        self.assertTrue(unassigned)
        self.assertTrue(all(row["ownership"] == "unassigned-legacy" and row["effort_root"] is None for row in unassigned))
        self.assertTrue(self.results(application, "legacyconversation")["results"])

    def test_application_before_registration_is_source_qualified_legacy_only_without_writes(self):
        from scripts import noetic_controller as controller
        unregistered = self.home / "fresh" / "namespace.sqlite3"
        legacy_home = self.home / "legacy-home"
        registry = native.Registry(legacy_home, namespace_path=unregistered)
        item = registry.create(self.home, "legacy", "fixture/model", "high", ["unused"],
                               ordinal="0", effort_root=None)
        registry.event(item["id"], "command", {"type": "prompt", "message": "preregconversation retained"})
        legacy_runs = legacy_home / "runs"
        with redirect_stdout(io.StringIO()):
            run_dir = runtime.create_run({"goal": "prereglegacy retained"}, self.home, legacy_runs)
        controller.start_run(run_dir / "controller.sqlite3", controller.PATTERN_DIR / "cognition.json",
                             "preregcontroller retained", self.home)
        before = {str(path.relative_to(legacy_home)): path.read_bytes() for path in legacy_home.rglob("*") if path.is_file()}
        result = recall.collect(namespace_path=unregistered, sessions_home=legacy_home,
                                runs_dir=legacy_runs, selection={"kind": "application"})
        self.assertFalse(result["diagnostics"])
        self.assertEqual(result["status"], "unregistered-legacy-only")
        self.assertEqual(result["coverage"]["canonical"], "not-registered")
        self.assertEqual(result["identity"]["namespace"], {"id": None, "path": str(unregistered)})
        self.assertTrue(self.results(result, "preregconversation")["results"])
        self.assertTrue(self.results(result, "preregcontroller")["results"])
        self.assertTrue(all(source["ownership"] == "unassigned-legacy" and source["ordinal"] is None
                            and source["effort_root"] is None for source in result["sources"]))
        self.assertFalse(unregistered.exists())
        self.assertFalse(unregistered.parent.exists())
        self.assertEqual(before, {str(path.relative_to(legacy_home)): path.read_bytes() for path in legacy_home.rglob("*") if path.is_file()})
        # Existing records claiming assignment cannot become legacy when their declared namespace is absent.
        invalid = recall.collect(namespace_path=unregistered, sessions_home=self.home,
                                 runs_dir=self.runs, selection={"kind": "application"})
        self.assertEqual(invalid["status"], "partial")
        self.assertTrue(any("claims assigned" in row["error"] for row in invalid["diagnostics"]))
        self.assertFalse(invalid["sources"])
        self.assertFalse(unregistered.exists())

    def test_lexical_cache_scope_requires_reindex_and_cli_has_coverage(self):
        a, b = self.owned(), self.owned(self.b)
        with closing(sqlite3.connect(self.home / "recall-cache.sqlite3")) as db:
            memory.index_scoped(db, a)
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                memory.index_scoped(db, b)
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                memory.search_scoped(db, "Bforeign", identity=b["identity"])
            memory.index_scoped(db, b, reindex=True)
            self.assertFalse(memory.search_scoped(db, "Aonly", identity=b["identity"])["results"])
            self.assertTrue(memory.search_scoped(db, "Bforeign", identity=b["identity"])["results"])
        command = [sys.executable, "-m", "scripts.noetic_memory", "search", "Aonly", "--runs-dir", str(self.runs),
            "--namespace-path", str(self.path), "--sessions-home", str(self.home), "--scope", "effort", "--effort-root", self.a]
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True,
            timeout=15, env={key: value for key, value in os.environ.items() if key != "USER_PROVIDED_PASSWORD"})
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["results"])
        self.assertIn("coverage", payload)
        self.assertFalse(payload["authoritative"])

    def structured(self, root, marker):
        from scripts import noetic_controller as controller
        from scripts import noetic_disciplines as disciplines
        from scripts import noetic_harness as harness
        adapter = disciplines.Disciplines(self.path)
        instance = adapter.create_instance(command_id=marker, effort_root=root, initiator=root,
            pattern="cognition", intent=marker, environment={"cwd": str(self.home)})
        request = {"namespace_path": str(self.path), "effort_root": root, "discipline_id": instance["id"],
                   "environment": instance["environment"], "origin": "human", "human_ref": self.human}
        with redirect_stdout(io.StringIO()):
            run_dir, state = harness.start("cognition", marker, self.home, self.runs,
                model="fixture/model", max_activations=0, scope_request=request)
        binding = json.loads((run_dir / "options.json").read_text())["scope"]
        store = run_dir / "controller.sqlite3"
        targets = []
        for content in ({"observations": [marker + " evidence"], "questions": [], "evidence_refs": []},
                        {"hypotheses": [marker + " hypothesis"]}):
            activation = state["activations"][state["current_activation"]]
            adapter.participant(binding, run_dir, activation)
            target = adapter.observed(binding, run_dir, activation, {
                "client": "fixture", "session_id": run_dir.name + activation["id"],
                "activation_id": activation["id"], "actor_id": activation["actor_id"]})
            targets.append(target)
            state = controller.begin_activation(store, activation["id"], state["version"])
            state = controller.submit_result(store, activation["id"], state["version"],
                {"outcome": "advance", "content": content}, "fixture:" + activation["id"], marker + activation["id"])
            adapter.sync(binding, run_dir, state)
        return run_dir, targets

    def test_actual_structured_correspondence_exact_participant_and_foreign_store_not_read(self):
        a_run, a_targets = self.structured(self.a, "Astructured")
        b_run, b_targets = self.structured(self.b, "Bstructured")
        result = self.owned()
        self.assertFalse(result["diagnostics"])
        sources = [source for source in result["sources"] if source["field"] == "controller-artifact"]
        self.assertTrue(sources)
        self.assertEqual({source["run_id"] for source in sources}, {a_run.name})
        hypotheses = [source for source in sources if source["artifact_type"] == "cognition.P2"]
        self.assertTrue(hypotheses)
        self.assertTrue(all(source["collection"] == "current-bindings-only" and source["semantic_authority"] == "none" for source in hypotheses))
        exact = self.collect({"kind": "session", **a_targets[1], "effort_root": self.a})
        self.assertTrue(self.results(exact, "Astructured hypothesis")["results"])
        self.assertFalse(self.results(exact, "Astructured evidence")["results"])
        self.assertFalse(self.results(exact, "Bstructured")["results"])
        ordinal = self.collect({"kind": "ordinal", "ordinal": a_targets[1]["ordinal"], "effort_root": self.a})
        self.assertTrue(self.results(ordinal, "hypothesis")["results"])
        b_run.joinpath("controller.sqlite3").write_bytes(b"foreign corrupt store must not be read")
        self.assertFalse(self.owned()["diagnostics"])
        global_result = self.collect({"kind": "application"})
        self.assertTrue(any(row["component"] == "structured-run" and row["path"] == str(b_run) for row in global_result["diagnostics"]))
        options_path = a_run / "options.json"
        options = json.loads(options_path.read_text())
        del options["scope"]
        options_path.write_text(json.dumps(options))
        missing = self.owned()
        self.assertTrue(any(row["path"] == str(a_run) and "Incomplete" in row["error"] for row in missing["diagnostics"]))
        self.assertFalse(any(row["field"] == "controller-artifact" for row in missing["sources"]))
        self.assertEqual(missing["status"], "partial")

    def test_semantic_http_boundary_cache_identity_byte_cuts_and_unavailable(self):
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.extend(body["input"])
                payload = json.dumps({"data": [{"index": index, "embedding": [1, 0, 0]}
                                              for index in range(len(body["input"]))]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        settings = local.Settings(base_url=f"http://127.0.0.1:{server.server_port}/v1", dimensions=3,
                                  embedding_api_key_env="", chunk_bytes=128)
        client = local.LocalClient(settings)
        self.structured(self.a, "Aonlystructured")
        self.structured(self.b, "Bforeignstructured")
        a, b = self.owned(), self.owned(self.b)
        self.assertFalse(a["diagnostics"])
        self.assertFalse(b["diagnostics"])
        with closing(sqlite3.connect(":memory:")) as db:
            index = semantic.index_scoped(db, a, client)
            self.assertTrue(index["embedding_requests"])
            self.assertFalse(any("Bforeign" in text for text in calls))
            before = len(calls)
            with self.assertRaisesRegex(local.LocalError, "identity mismatch"):
                semantic.index_scoped(db, b, client)
            with self.assertRaisesRegex(local.LocalError, "identity mismatch"):
                semantic.search(db, "Bforeign", client, identity=b["identity"])
            with self.assertRaisesRegex(local.LocalError, "requires the declared"):
                semantic.search(db, "Aonly", client)
            self.assertEqual(len(calls), before)
            self.assertEqual(semantic.index_scoped(db, a, client)["embedding_requests"], 0)
            rows = semantic.search(db, "Aonly", client, identity=a["identity"])
            original = {source["source_id"]: source for source in a["sources"]}
            for row in rows:
                self.assertEqual(row["snippet"], original[row["source_id"]]["text"].encode()[row["byte_start"]:row["byte_end"]].decode())
                self.assertFalse(row["authoritative"])
                self.assertEqual(row["effort_root"], self.a)
            calls.clear()
            semantic.index_scoped(db, b, client, reindex=True)
            self.assertFalse(any("Aonly" in text for text in calls))
            rows = semantic.search(db, "Bforeign", client, identity=b["identity"])
            self.assertTrue(rows)
            self.assertEqual({row["effort_root"] for row in rows}, {self.b})
        server.shutdown()
        thread.join()
        # Deliberately closed fake endpoint: clear provider failure, lexical remains usable.
        server.server_close()
        with closing(sqlite3.connect(":memory:")) as db:
            with self.assertRaises(local.LocalError):
                semantic.index_scoped(db, a, client)
        self.assertTrue(self.results(a, "Aonly")["results"])


if __name__ == "__main__":
    unittest.main()
