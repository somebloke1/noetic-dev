import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from contextlib import closing

from scripts import noetic_usage as usage, noetic_web as web
from scripts.noetic_sessions import SessionService


class NativeUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="noetic-usage-")
        self.home = Path(self.temp.name)
        self.runs = self.home / "runs"
        self.namespace = self.home / "namespace.sqlite3"
        self.service = SessionService(self.runs, namespace_path=self.namespace)
        self.effort = self.service.create_effort({"intent": "Usage fixture", "environment": {"cwd": str(self.home)}})["ordinal"]
        self.other = self.service.create_effort({"intent": "Other fixture", "environment": {"cwd": str(self.home)}})["ordinal"]
        self.owned = self.session(self.effort, self.effort)
        self.original = self.session(self.effort, None)

    def tearDown(self):
        self.temp.cleanup()

    def session(self, ordinal, effort):
        return self.service.registry.create(self.home, "Fixture", "unused-current-default", "off", [], ordinal=ordinal, effort_root=effort)

    def event(self, item, record):
        with closing(self.service.registry.connect()) as db, db:
            db.execute("INSERT INTO events(session_id,at,direction,record) VALUES(?,?,?,?)", (item["id"], "2026-10-13T01:00:00Z", "out", json.dumps(record)))

    def end(self, identity="response-1", fields=None):
        message = {"role": "assistant", "provider": "openai-codex", "model": "gpt-6.1-sol", "api": "openai-codex-responses",
                   "usage": fields if fields is not None else {"input": 100, "output": 20, "cacheRead": 400, "cacheWrite": 50, "reasoning": 10, "cacheWrite1h": 5, "totalTokens": 570, "cost": {"total": 0.123}}}
        if identity is not None:
            message["responseId"] = identity
        return {"type": "message_end", "message": message}

    def project(self, effort=None):
        return usage.project(self.service, {"kind": "application"} if effort is None else {"kind": "effort", "effort_root": effort})

    def test_completed_once_and_pi_categories(self):
        end = self.end()
        self.event(self.owned, end)
        self.event(self.owned, end)
        self.event(self.owned, {**end, "type": "message_update"})
        self.event(self.owned, {"type": "turn_end", "usage": end["message"]["usage"]})
        self.event(self.owned, {"type": "model", "cost": {"input": 999}})
        result = self.project(self.effort)
        self.assertEqual(result["coverage"]["records"], 1)
        self.assertEqual(result["coverage"]["duplicates"], 1)
        self.assertEqual(result["totals"]["totalInput"], 550)
        self.assertEqual(result["totals"]["output"], 20)
        self.assertAlmostEqual(result["cache_read_share"], 400 / 550)
        self.assertEqual(result["rows"][0]["adapter_cost"], {"total": 0.123})
        self.assertEqual(result["rows"][0]["model"], "gpt-6.1-sol")
        self.assertIn("raw provider", result["notice"])

    def test_original_collision_and_per_registry_dedup(self):
        self.event(self.owned, self.end())
        self.event(self.original, self.end())
        self.assertEqual(self.project(self.effort)["totals"]["input"], 100)
        all_rows = self.project()
        self.assertEqual(all_rows["totals"]["input"], 200)
        original = next(row for row in all_rows["sessions"] if row["id"] == self.original["id"])
        self.assertIsNone(original["effort_root"])
        self.assertEqual(original["identity_origin"], "legacy-unadopted")
        self.assertIsNone(self.project(self.other)["totals"]["input"])

    def test_observed_binding_and_changed_registry_target(self):
        self.service.registry.attach(self.owned["id"], {"sessionId": "fixture-native", "sessionFile": str(self.home / "native.jsonl")})
        self.event(self.owned, self.end())
        result = self.project(self.effort)
        observed = next(item for item in result["sessions"] if item["id"] == self.owned["id"])
        self.assertEqual(observed["target"]["ordinal"], self.effort)
        self.assertEqual(result["totals"]["input"], 100)
        with closing(self.service.registry.connect()) as db, db:
            db.execute("UPDATE sessions SET session_selector=99 WHERE id=?", (self.owned["id"],))
        result = self.project(self.effort)
        self.assertIsNone(result["totals"]["input"])
        self.assertTrue(any(item["kind"] == "unavailable-binding" for item in result["warnings"]))

    def test_missing_zero_invalid_and_missing_identity(self):
        self.event(self.owned, self.end(None, {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}))
        self.event(self.owned, self.end("missing", {"input": 5, "output": 2}))
        self.event(self.owned, self.end("invalid", {"input": -1, "output": True, "cacheRead": "20", "cacheWrite": float("nan")}))
        result = self.project(self.effort)
        self.assertIsNone(result["cache_read_share"])
        self.assertEqual(result["totals"]["input"], 5)
        self.assertEqual(result["coverage"]["fields"]["cacheRead"], {"known": 1, "missing": 2})
        self.assertEqual(result["coverage"]["missing_response_ids"], 1)
        self.assertEqual(result["rows"][0]["cacheRead"], 0)
        self.assertIsNone(result["rows"][1]["cacheRead"])
        self.assertTrue(result["warnings"])

    def test_http_explicit_scope_and_read_only_projection(self):
        self.event(self.owned, self.end())
        before = self.service.registry.path.read_bytes()
        server = web.create_server(self.runs, port=0, namespace_path=self.namespace)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def get(path):
                connection = http.client.HTTPConnection(*server.server_address)
                connection.request("GET", path)
                response = connection.getresponse()
                status, body = response.status, json.loads(response.read())
                connection.close()
                return status, body
            self.assertEqual(get("/api/usage")[0], 400)
            self.assertEqual(get("/api/usage?scope=application&scope=application")[0], 400)
            self.assertEqual(get("/api/usage?effort_root=0.999")[0], 422)
            status, result = get("/api/usage?effort_root=" + self.effort)
            self.assertEqual(status, 200, result)
            self.assertEqual(result["totals"]["totalInput"], 550)
            self.assertEqual(self.service.registry.path.read_bytes(), before)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
