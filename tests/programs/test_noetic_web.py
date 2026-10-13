"""Local HTTP implementation checks; fixtures are test-authored, not model work or QA."""

from contextlib import closing, redirect_stdout
import http.client
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from urllib.parse import urlencode
from unittest.mock import patch

from scripts import noetic_run as runtime
from scripts import noetic_web as web


class OperatorViewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runs = self.root / "runs"
        plan = {
            "goal": "Test-authored amber instrument goal <script>not HTML</script>",
            "goal_ref": "telos:test-chain",
            "work": [sys.executable, "-B", "-c", "print('test-authored work stdout')"],
            "verify": [sys.executable, "-B", "-c", "import sys; print('test-authored verify stderr', file=sys.stderr)"],
        }
        with redirect_stdout(io.StringIO()):
            self.run, _ = runtime.run_plan(plan, self.root, self.runs)
        (self.run / "work.md").write_text("Test-authored worker amber findings <img src=x onerror=alert(1)>", encoding="utf-8")
        (self.run / "review.md").write_text("Test-authored amber review with retainedmarker evidence.", encoding="utf-8")
        (self.run / "task.md").write_text("Test-authored operator task", encoding="utf-8")
        (self.run / "changes.diff").write_text("# Test-authored observed changes\n-old\n+new\n", encoding="utf-8")
        (self.run / "changes.json").write_text('{"status": "available", "changes": []}', encoding="utf-8")
        (self.run / "not-selected.txt").write_text("not exposed by the operator", encoding="utf-8")
        runtime.record(self.run, "telos.linked", {"chain_id": "test-chain", "subgoal_id": "test-subgoal"})
        runtime.review_run(self.run, "accept", "test-authored-reviewer", self.run / "review.md")
        runtime.record(self.run, "telos.result", {"chain_id": "test-chain", "subgoal_id": "test-subgoal", "subgoal_status": "complete"})
        # An existing derived on-disk index must not be opened or replaced by the web view.
        (self.runs / ".memory.sqlite3").write_bytes(b"existing derived index sentinel")
        self.server = web.create_server(self.runs, port=0)
        self.server.RequestHandlerClass.log_message = lambda *args: None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, path, method="GET"):
        if method in ("GET", "HEAD") and path.startswith(("/api/runs", "/api/search")):
            path += ("&" if "?" in path else "?") + "scope=application"
        with closing(http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)) as connection:
            connection.request(method, path)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()

    def api(self, path, expected=200, method="GET"):
        status, headers, body = self.request(path, method)
        self.assertEqual(status, expected, body)
        self.assertIn("application/json", headers["Content-Type"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        return json.loads(body)

    def search(self, query, **params):
        return self.api("/api/search?" + urlencode({"q": query, **params}))

    def snapshot_sources(self):
        return {str(path.relative_to(self.runs)): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.runs.rglob("*") if path.is_file()}

    def test_root_assets_and_read_only_routes(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertNotEqual(self.server.server_port, 0)
        for route, name, mime in (("/", "index.html", "text/html"),
                                  ("/index.html", "index.html", "text/html"),
                                  ("/app.js", "app.js", "text/javascript"),
                                  ("/style.css", "style.css", "text/css")):
            with self.subTest(route=route):
                code, headers, body = self.request(route)
                self.assertEqual(code, 200)
                self.assertIn(mime, headers["Content-Type"])
                self.assertEqual(body, (web.WEB_DIR / name).read_bytes())
                self.assertEqual(int(headers["Content-Length"]), len(body))
        code, headers, body = self.request("/", "HEAD")
        self.assertEqual(code, 200)
        self.assertEqual(body, b"")
        self.assertGreater(int(headers["Content-Length"]), 0)
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            self.assertIn("Read-only", self.api("/api/runs", 405, method)["error"])
        for route in ("/events.sqlite3", "/noetic_web.py", f"/api/runs/{self.run.name}/work.md"):
            self.api(route, 400 if route.startswith("/api/runs/") else 404)

    def test_list_and_details_are_actual_journal_projection(self):
        listing = self.api("/api/runs")
        self.assertEqual(listing["runs_dir"], str(self.runs))
        self.assertEqual(listing["warnings"], [])
        self.assertEqual(len(listing["runs"]), 1)
        summary = listing["runs"][0]
        self.assertEqual(summary["run_id"], self.run.name)
        self.assertEqual(summary["state"], "accepted")
        self.assertEqual(summary["telos"]["chain_id"], "test-chain")
        detail = self.api(f"/api/runs/{self.run.name}")
        events = runtime.read_events(self.run)
        self.assertEqual(detail["events"], events)
        self.assertEqual(detail["status"], runtime.project(events))
        self.assertEqual(summary["last_event_at"], events[-1]["occurred_at"])
        self.assertIn("observed_at", detail)
        self.assertEqual(detail["journal_path"], str(self.run / "events.sqlite3"))
        self.assertEqual(detail["status"]["review"]["reviewer"], "test-authored-reviewer")
        self.assertEqual({e["data"]["step"] for e in events if e["kind"] == "step.finished"}, {"work", "verify"})
        self.assertIn("<img src=x", detail["artifacts"]["work.md"]["text"])
        self.assertEqual(detail["artifacts"]["work.stdout.log"]["text"], "test-authored work stdout\n")
        self.assertIn("test-authored verify stderr", detail["artifacts"]["verify.stderr.log"]["text"])
        self.assertNotIn("not-selected.txt", detail["artifacts"])
        self.assertNotIn("review.stdout.log", detail["artifacts"])
        for name in ("changes.diff", "changes.json"):
            self.assertEqual(detail["artifacts"][name]["text"], (self.run / name).read_text())
            self.assertIn(f'<option value="{name}">', (web.WEB_DIR / "index.html").read_text())

    def test_new_runs_and_new_events_appear_on_refresh(self):
        with redirect_stdout(io.StringIO()):
            new = runtime.create_run({"goal": "Test-authored unfinished run"}, self.root, self.runs)
        listing = self.api("/api/runs")
        self.assertEqual([r["run_id"] for r in listing["runs"]], [new.name, self.run.name])
        self.assertEqual(listing["runs"][0]["state"], "unfinished")
        runtime.record(new, "step.started", {"step": "work", "stdout": "work.stdout.log", "stderr": "work.stderr.log"})
        runtime.record(new, "run.finished", {"state": "failed"})
        detail = self.api(f"/api/runs/{new.name}")
        self.assertEqual(detail["status"]["state"], "failed")
        self.assertEqual(detail["events"], runtime.read_events(new))

    def test_search_refreshes_real_evidence_with_attribution(self):
        result = self.search("amber")
        self.assertEqual({m["source"] for m in result["results"]}, {"goal", "work", "review", "review.recorded.evidence"})
        self.assertEqual(result["index"]["entries"], 4)
        self.assertFalse(result["authoritative"])
        self.assertTrue(all(m["ownership"] == "unassigned-legacy" and m["semantic_authority"] == "none" for m in result["results"]))
        for match in result["results"]:
            self.assertEqual(match["run_id"], self.run.name)
            self.assertEqual(match["state"], "accepted")
            self.assertEqual(Path(match["source_path"]).parent, self.run)
        (self.run / "work.md").write_text("Test-authored newlyindexedmarker", encoding="utf-8")
        self.assertEqual(self.search("newlyindexedmarker")["results"][0]["source"], "work")
        (self.run / "review.md").unlink()
        match = self.search("retainedmarker")["results"][0]
        self.assertEqual(match["source"], "review.recorded.evidence")
        self.assertEqual(match["source_path"], str(self.run / "events.sqlite3"))
        event = next(e for e in runtime.read_events(self.run) if e["sequence"] == match["event_sequence"])
        self.assertEqual(event["kind"], "review.recorded")
        self.assertEqual(self.search("no-such-evidence")["results"], [])
        self.api("/api/search?q=", 400)
        self.assertEqual(len(self.search("test", limit=1)["results"]), 1)
        with patch.object(self.server.application, "lexical", wraps=self.server.application.lexical) as bounded:
            self.search("test", limit=1000)
            bounded.assert_called_once_with("test", {"kind": "application"}, 100)
        self.api("/api/search?q=test&limit=bad", 400)

    def test_missing_and_corrupt_runs_have_controlled_responses(self):
        self.api("/api/runs/missing", 404)
        damaged = self.runs / "damaged"
        damaged.mkdir()
        (damaged / "events.sqlite3").write_bytes(b"not a sqlite database")
        self.assertIn("Run ownership cannot authorize", self.api("/api/runs/damaged", 403)["error"])
        listing = self.api("/api/runs")
        self.assertEqual([r["run_id"] for r in listing["runs"]], [self.run.name])
        self.assertTrue(any("damaged" in warning for warning in listing["warnings"]))
        self.assertTrue(self.search("amber")["results"])
        with closing(sqlite3.connect(self.run / "events.sqlite3")) as connection:
            with connection:
                connection.execute("UPDATE events SET data = '[]' WHERE sequence = 1")
        self.api(f"/api/runs/{self.run.name}", 422)
        self.assertEqual(self.api("/api/runs")["runs"], [])

    def test_missing_root_is_not_created(self):
        missing = self.root / "not-created"
        with web.create_server(missing, port=0) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with closing(http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)) as connection:
                    for route, field in (("/api/runs?scope=application", "runs"), ("/api/search?q=amber&scope=application", "results")):
                        connection.request("GET", route)
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        self.assertEqual(json.loads(response.read())[field], [])
            finally:
                server.shutdown()
                thread.join(timeout=5)
        self.assertFalse(missing.exists())

    def test_path_escape_rejected_for_runs_artifacts_and_search(self):
        for identifier in ("..", "%2e%2e", "%2e%2e%2foutside", "%2Ftmp", "nested/run", "bad%5crun", "%00", ""):
            with self.subTest(identifier=identifier):
                self.api("/api/runs/" + identifier, 404 if identifier == "nested/run" else 400)
        self.api("/%2e%2e/noetic_run.py", 404)
        outside_runs = self.root / "outside-runs"
        with redirect_stdout(io.StringIO()):
            outside = runtime.create_run({"goal": "Test-authored outsideonlymarker"}, self.root, outside_runs)
        (self.runs / outside.name).symlink_to(outside, target_is_directory=True)
        self.api(f"/api/runs/{outside.name}", 403)
        self.assertEqual([r["run_id"] for r in self.api("/api/runs")["runs"]], [self.run.name])
        self.api("/api/search?q=outsideonlymarker", 403)
        external_report = self.root / "external.md"
        external_report.write_text("Test-authored outsidereportmarker", encoding="utf-8")
        (self.run / "work.md").unlink()
        (self.run / "work.md").symlink_to(external_report)
        detail = self.api(f"/api/runs/{self.run.name}")
        self.assertIn("outside", detail["artifacts"]["work.md"]["error"])
        self.assertNotIn("text", detail["artifacts"]["work.md"])
        self.api("/api/search?q=outsidereportmarker", 403)
        (self.run / "events.sqlite3").unlink()
        (self.run / "events.sqlite3").symlink_to(outside / "events.sqlite3")
        self.api(f"/api/runs/{self.run.name}", 403)

    def test_large_and_non_utf8_logs_are_explicitly_bounded(self):
        (self.run / "work.stdout.log").write_bytes(b"a" * (web.ARTIFACT_LIMIT + 50))
        (self.run / "work.stderr.log").write_bytes(b"stderr \xff")
        artifacts = self.api(f"/api/runs/{self.run.name}")["artifacts"]
        self.assertTrue(artifacts["work.stdout.log"]["truncated"])
        self.assertEqual(len(artifacts["work.stdout.log"]["text"]), web.ARTIFACT_LIMIT)
        self.assertEqual(artifacts["work.stderr.log"]["text"], "stderr \ufffd")
        self.assertFalse(artifacts["work.stderr.log"]["truncated"])

    def test_all_reads_preserve_source_journals_and_existing_index(self):
        before = self.snapshot_sources()
        for _ in range(2):
            self.api("/api/runs")
            self.api(f"/api/runs/{self.run.name}")
            self.search("amber")
        self.api("/api/runs/missing", 404)
        self.api(f"/api/runs/{self.run.name}", 405, "POST")
        self.assertEqual(self.snapshot_sources(), before)


if __name__ == "__main__":
    unittest.main()
