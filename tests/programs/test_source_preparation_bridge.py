"""Deterministic maintained tests for the exact source preparation bridge.

Temp canonical ScopeStore/Registry, the real Application collector and the real
narrow HTTP GET route; no live dependency, no native process and no launch.
"""

import hashlib
import http.client
import json
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import noetic_application as application
from scripts import noetic_sessions as native
from scripts import noetic_web as web
from scripts.noetic_scope import ScopeStore

# Actual retained answer: event 50498, native session and exact 266-byte UTF-8 text.
TEXT = ("**Question:** What should the current UI preserve so a reviewer can meaningfully return to a prepared "
        "research question later without launching a model?\n\n**Source basis:** The README names preparation and "
        "return as the purpose but does not specify what must persist.")
DIGEST = hashlib.sha256(TEXT.encode()).hexdigest()
assert len(TEXT.encode()) == 266
SESSION = "20e8fd0c-3023-4b03-8186-3cfc283f51f8"
SEQUENCE = 50498
SOURCE = {"fixture": "owned source bridge"}
HUMAN = {"owner": "fixture-human"}


class SourcePreparationBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="sourcebridge-tests-")
        home = Path(cls.temp.name)
        cls.addClassCleanup(cls.temp.cleanup)
        runs = home / "runs"
        runs.mkdir()
        path = home / "namespace.sqlite3"
        store = ScopeStore(path, root_mandate={"purpose": "fixture"}, human_ref=HUMAN, source_ref=SOURCE)
        root = None
        for index in range(7):
            root = store.create_effort(intent=f"fixture{index}", environment={"cwd": str(home)},
                                       mandate={"purpose": "fixture"}, origin="human", human_ref=HUMAN,
                                       source_ref=SOURCE)["ordinal"]
        assert root == "0.6", root
        cls.root = root
        cls.registry = native.Registry(runs, namespace_path=path)
        item = cls.registry.create(home, "retained fixture", "fixture/model", "high", ["unused"], ordinal=root, effort_root=root)
        with closing(cls.registry.connect()) as db, db:
            db.execute("UPDATE sessions SET id=?,root_id=? WHERE id=?", (SESSION, SESSION, item["id"]))
        context = home / (SESSION + ".jsonl")
        context.write_text(json.dumps({"type": "session", "id": SESSION}) + "\n")
        cls.registry.update(SESSION, native_session_id=SESSION, native_session_file=str(context))
        cls.registry.attach(SESSION, {"sessionId": SESSION, "sessionFile": str(context)})
        cls.record = {"type": "message_end", "message": {"role": "assistant",
            "content": [{"type": "text", "text": TEXT}], "stopReason": "stop"}}
        with closing(cls.registry.connect()) as db, db:
            db.execute("INSERT INTO events(sequence,session_id,at,direction,record) VALUES(?,?,?,?,?)",
                       (SEQUENCE, SESSION, "2026-10-13T22:00:00Z", "event", json.dumps(cls.record)))
        cls.registry.correlate(SESSION)
        cls.item = cls.registry.get(SESSION)
        cls.selection = {"kind": "session", **cls.item["target"], "effort_root": root}
        cls.app = application.Application(runs, namespace_path=path, sessions_home=runs)
        collection = cls.app.collect(cls.selection)
        cls.collected = [source for source in collection["sources"]
                         if source.get("source_ref", {}).get("sequence") == SEQUENCE][0]
        cls.expected = {"selection": cls.selection, "registry_id": SESSION, "native_session_id": SESSION,
                        "sequence": SEQUENCE, "source_text_sha256": DIGEST}
        cls.server = web.create_server(runs, port=0, namespace_path=path)
        thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        thread.start()
        # Single bounded cleanup: stop serving BEFORE joining, otherwise join blocks forever (LIFO order).
        def stop_server():
            cls.server.shutdown()
            cls.server.server_close()
            thread.join(timeout=5)
        cls.addClassCleanup(stop_server)

    def read(self, **changes):
        return self.app.source_preparation(**{**self.expected, **changes})

    def refusal(self, **changes):
        with self.assertRaises((application.ApplicationError, native.SessionError)):
            self.read(**changes)

    def test_exact_projection_returns_collector_source_with_266_byte_text(self):
        source = self.read()["source"]
        self.assertEqual(source, self.collected)
        self.assertEqual(len(source["text"].encode()), 266)
        self.assertEqual(source["text"], TEXT)
        self.assertEqual(source["source_text_sha256"], DIGEST)
        self.assertEqual(source["source_ref"]["sequence"], SEQUENCE)
        self.assertEqual(source["source_ref"]["native_session_id"], SESSION)
        self.assertEqual(source["authoritative"], False)
        self.assertEqual(source["semantic_authority"], "none")
        self.assertEqual(source["field"], "developer-conversation")
        self.assertEqual(source["disposition"], "retained-message")

    def test_changed_digest_refuses(self):
        self.refusal(source_text_sha256="f" * 64)

    def test_foreign_effort_refuses(self):
        self.refusal(selection={**self.selection, "effort_root": "0.5"})

    def test_missing_event_refuses(self):
        self.refusal(sequence=50499)

    def test_wrong_registry_refuses(self):
        self.refusal(registry_id="missing")

    def test_wrong_native_identity_refuses(self):
        self.refusal(native_session_id="wrong")

    def test_broader_scope_refuses(self):
        self.refusal(selection={"kind": "application"})

    def test_malformed_selectors_refuse(self):
        for changes in ({"sequence": True}, {"sequence": 0}, {"sequence": "50498"},
                        {"selection": {**self.selection, "instantiation": True}},
                        {"selection": {**self.selection, "ordinal": "zero"}},
                        {"source_text_sha256": DIGEST.upper()},
                        {"native_session_id": ""}):
            with self.subTest(changes=changes):
                self.refusal(**changes)

    def test_ambiguous_collector_source_refuses(self):
        collection = self.app.collect(self.selection)
        matches = [source for source in collection["sources"] if source.get("source_ref", {}).get("sequence") == SEQUENCE]
        with patch.object(self.app, "collect", return_value={**collection, "sources": matches + matches}):
            self.refusal()

    def test_error_envelope_refuses(self):
        errored = {"type": "message_end", "message": {"role": "assistant",
                   "content": self.record["message"]["content"], "errorMessage": "error", "stopReason": "error"}}
        with closing(self.registry.connect()) as db, db:
            db.execute("UPDATE events SET record=? WHERE sequence=?", (json.dumps(errored), SEQUENCE))
        try:
            self.refusal()
        finally:
            with closing(self.registry.connect()) as db, db:
                db.execute("UPDATE events SET record=? WHERE sequence=?", (json.dumps(self.record), SEQUENCE))

    def test_unassigned_collector_source_refuses(self):
        collection = self.app.collect(self.selection)
        matches = [source for source in collection["sources"] if source.get("source_ref", {}).get("sequence") == SEQUENCE]
        unassigned = [{**source, "ownership": "unassigned"} for source in matches]
        with patch.object(self.app, "collect", return_value={**collection, "sources": unassigned}):
            self.refusal()

    def test_non_object_event_record_refuses(self):
        with closing(self.registry.connect()) as db, db:
            db.execute("UPDATE events SET record=? WHERE sequence=?", (json.dumps(["not", "an", "object"]), SEQUENCE))
        try:
            self.refusal()
        finally:
            with closing(self.registry.connect()) as db, db:
                db.execute("UPDATE events SET record=? WHERE sequence=?", (json.dumps(self.record), SEQUENCE))

    def test_unsupported_text_block_refuses(self):
        malformed = {"type": "message_end", "message": {"role": "assistant",
                     "content": [{"type": "text", "text": 7}], "stopReason": "stop"}}
        with closing(self.registry.connect()) as db, db:
            db.execute("UPDATE events SET record=? WHERE sequence=?", (json.dumps(malformed), SEQUENCE))
        try:
            self.refusal()
        finally:
            with closing(self.registry.connect()) as db, db:
                db.execute("UPDATE events SET record=? WHERE sequence=?", (json.dumps(self.record), SEQUENCE))

    def test_unsupported_event_types_refuse(self):
        replacements = [
            {"type": "message_update", "message": self.record["message"]},
            {"type": "message_end", "message": {"role": "custom", "customType": "noetic-agent-message",
                "details": {"provenance": {"origin": "agent", "sender": self.item["target"],
                                           "recipient": self.item["target"]}}, "content": TEXT}},
            {"type": "message_end", "message": {"role": "assistant", "content": [], "stopReason": "stop"}},
        ]
        for record in replacements:
            with self.subTest(record=record["type"]):
                with closing(self.registry.connect()) as db, db:
                    db.execute("UPDATE events SET record=? WHERE sequence=?", (json.dumps(record), SEQUENCE))
                try:
                    self.refusal()
                finally:
                    with closing(self.registry.connect()) as db, db:
                        db.execute("UPDATE events SET record=? WHERE sequence=?", (json.dumps(self.record), SEQUENCE))

    def http_get(self, params):
        with closing(http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)) as connection:
            connection.request("GET", "/api/source-preparation?" + urlencode(params))
            response = connection.getresponse()
            return response.status, json.loads(response.read())

    def test_http_get_yields_same_exact_collector_source(self):
        params = {**self.selection, "registry_id": SESSION, "native_session_id": SESSION,
                  "sequence": SEQUENCE, "source_text_sha256": DIGEST}
        params.pop("kind")
        status, result = self.http_get(params)
        self.assertEqual(status, 200)
        self.assertEqual(result["source"], self.collected)

    def test_http_rejects_missing_duplicate_unknown_and_malformed(self):
        base = {**self.selection, "registry_id": SESSION, "native_session_id": SESSION,
                "sequence": SEQUENCE, "source_text_sha256": DIGEST}
        base.pop("kind")
        cases = [
            {key: value for key, value in base.items() if key != "ordinal"},
            {**base, "unknown": "x"},
            {**base, "instantiation": "x"},
            {**base, "sequence": "0"},
            {**base, "source_text_sha256": "Z" * 64},
            {**base, "ordinal": ""},
        ]
        for params in cases:
            with self.subTest(params=params):
                status, result = self.http_get(params)
                self.assertGreaterEqual(status, 400)
        query = urlencode(base) + "&ordinal=0.6"
        with closing(http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)) as connection:
            connection.request("GET", "/api/source-preparation?" + query)
            response = connection.getresponse()
            self.assertGreaterEqual(response.status, 400)
            response.read()


if __name__ == "__main__":
    unittest.main()
