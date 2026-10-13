"""Owned registry/namespace contention and real broker frame fixtures."""
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from scripts import noetic_sessions as sessions


class RegistryContentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="registry-contention-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.cwd = self.home / "work"
        self.cwd.mkdir(mode=0o700)
        self.service = sessions.SessionService(self.home / "runs", namespace_path=self.home / "namespace.sqlite3")
        self.registry = self.service.registry
        self.effort = self.service.create_effort({"intent": "Fixture", "environment": {"cwd": str(self.cwd)}})["ordinal"]
        self.item = self.registry.create(self.cwd, "Fixture", "openai-codex/gpt-6.1-sol", "off", [], ordinal=self.effort, effort_root=self.effort)
        self.registry.attach(self.item["id"], {"sessionId": self.item["id"], "sessionFile": str(self.home / "native.jsonl")})
        self.legacy = self.registry.create(self.cwd, "Original", "unused", "off", [], ordinal="0", effort_root=None)

    def pending(self):
        with closing(self.registry.connect()) as db, db:
            cursor = db.execute("INSERT INTO events(session_id,at,direction,record) VALUES(?,?,?,?)",
                                (self.item["id"], sessions.now(), "host", json.dumps({"type": "fixture_pending"})))
            return cursor.lastrowid

    def test_namespace_mirror_does_not_hold_registry_writer(self):
        sequence = self.pending()
        entered, release = threading.Event(), threading.Event()
        store_type = type(self.registry.domain.store())
        original = store_type.record_event
        def blocked(store, *args, **kwargs):
            if kwargs["source_ref"]["sequence"] == sequence:
                entered.set()
                if not release.wait(5):
                    raise AssertionError("fixture mirror was not released")
            return original(store, *args, **kwargs)
        connect = self.registry.connect
        def short_connect(**kwargs):
            db = connect(**kwargs)
            db.execute("PRAGMA busy_timeout=100")
            return db
        with patch.object(store_type, "record_event", blocked), patch.object(self.registry, "connect", short_connect):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.registry.correlate, self.item["id"])
                try:
                    self.assertTrue(entered.wait(3))
                    appended = self.registry.event(self.legacy["id"], "host", {"type": "unrelated_append"})
                    self.assertGreater(appended, sequence)
                finally:
                    release.set()
                future.result(timeout=5)
        with closing(self.registry.connect(readonly=True)) as db:
            self.assertEqual(db.execute("SELECT correlated FROM events WHERE sequence=?", (sequence,)).fetchone()[0], 1)

    def test_concurrent_correlation_serializes_snapshot_and_mark(self):
        sequence = self.pending()
        entered, release = threading.Event(), threading.Event()
        observed = []
        store_type = type(self.registry.domain.store())
        original = store_type.record_event
        def blocked(store, *args, **kwargs):
            if kwargs["source_ref"]["sequence"] == sequence:
                observed.append(kwargs["source_ref"])
                entered.set()
                if not release.wait(5):
                    raise AssertionError("fixture mirror was not released")
            return original(store, *args, **kwargs)
        other = sessions.Registry(self.service.runs_root, create=False, namespace_path=self.registry.domain.path)
        with patch.object(store_type, "record_event", blocked), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.registry.correlate, self.item["id"])
            try:
                self.assertTrue(entered.wait(3))
                second = pool.submit(other.correlate, self.item["id"])
            finally:
                release.set()
            first.result(timeout=5)
            second.result(timeout=5)
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0]["session_id"], self.item["id"])

    def test_storage_error_has_a_broker_response_and_broker_survives(self):
        fixture = Path(__file__).with_name("fixtures") / "fake_pi_rpc.py"
        child = self.service.create_effort({"intent": "Broker fixture", "environment": {"cwd": str(self.cwd)}})["ordinal"]
        item = self.registry.create(self.cwd, "Broker", "openai-codex/gpt-6.1-sol", "off", [sys.executable, str(fixture)], ordinal=child, effort_root=child)
        broker = sessions.Broker(self.service.runs_root, item["id"], namespace_path=self.registry.domain.path)
        original = broker.handle
        def handle(request):
            if request.get("action") == "fixture_storage_error":
                raise sqlite3.OperationalError("database is locked")
            return original(request)
        errors = []
        def run():
            try:
                broker.run()
            except Exception as exc:
                errors.append(exc)
        with patch.object(broker, "handle", handle):
            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            try:
                deadline = time.monotonic() + 5
                while self.registry.get(item["id"])["status"] != "idle" and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertEqual(self.registry.get(item["id"])["status"], "idle")
                with self.assertRaises(sessions.SessionError) as caught:
                    sessions.control(self.service.runs_root, item["id"], {"action": "fixture_storage_error"})
                self.assertEqual(caught.exception.status, 503)
                self.assertIn("database is locked", str(caught.exception))
                self.assertIn("outcome", str(caught.exception))
                self.assertEqual(sessions.control(self.service.runs_root, item["id"], {"action": "context"})["target"]["ordinal"], child)
            finally:
                broker.closed.set()
                thread.join(10)
                self.assertFalse(thread.is_alive())
                sessions.socket_path(self.service.runs_root, item["id"]).parent.rmdir()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
