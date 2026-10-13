"""Local HTTP, temporary Git projects and live model-free brokers."""
from contextlib import closing
import http.client
import json
from pathlib import Path
import sys
import threading
import time
import unittest

from scripts import noetic_release as release, noetic_web as web, noetic_run as runtime
from tests.programs import test_noetic_sessions as session_fixture
FIXTURE = session_fixture.FIXTURE


class DeveloperSessionApiTests(unittest.TestCase):
    def setUp(self):
        session_fixture.SessionTests.setUp(self)
        self.app_home = self.home / "app"
        self.runs = self.app_home / "state" / "runs"
        self.server = web.create_server(self.runs, port=0, session_command=[sys.executable, str(FIXTURE)], namespace_path=self.runs / "ordinals.sqlite3")
        self.service = self.server.developer_sessions
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.stop_server()
        session_fixture.SessionTests.tearDown(self)

    def stop_server(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=5)

    def request(self, path, body=None, *, stale_header=False, method=None):
        headers = {"Content-Type": "application/json"}
        if stale_header:
            headers["Authorization"] = "stale synthetic operator header"
        with closing(http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=25)) as client:
            client.request(method or ("POST" if body is not None else "GET"), path,
                           body=json.dumps(body) if body is not None else None, headers=headers)
            response = client.getresponse()
            return response.status, json.loads(response.read())

    def start(self, prompt="hello", **options):
        effort = options.pop("effort_root", None)
        if effort is None:
            status, registered = self.request("/api/efforts", {"intent": prompt, "environment": {"cwd": str(self.workspace)}})
            self.assertEqual(status, 201, registered)
            effort = registered["effort"]["ordinal"]
        status, result = self.request("/api/developer-sessions", {"workspace": str(self.workspace), "effort_root": effort, "prompt": prompt, **options})
        self.assertEqual(status, 201, result)
        return result["session"]

    def wait(self, sid, state="idle"):
        return session_fixture.SessionTests.wait(self, sid, state)

    def test_failed_reservation_diagnostics_are_readable_only_in_its_declared_effort(self):
        missing_context = self.home / "missing-context.py"
        missing_context.write_text(FIXTURE.read_text().replace('"sessionFile": str(path)', '"sessionFile": None'))
        self.service.pi_command = [sys.executable, str(missing_context)]
        effort = self.service.create_effort({"intent": "missing native reference", "environment": {"cwd": str(self.workspace)}})["ordinal"]
        status, failure = self.request("/api/developer-sessions", {"effort_root": effort, "prompt": "must never run"})
        self.assertEqual(status, 409, failure)
        self.assertEqual(failure["error"], "Pi did not provide a valid planned native context reference; prompt was not sent.")
        reserved = self.service.list(effort)[0]
        route = f"/api/developer-sessions/{reserved['id']}?effort_root={effort}"
        status, detail = self.request(route)
        self.assertEqual(status, 200, detail)
        self.assertEqual(detail["session"]["error"], failure["error"])
        self.assertIsNone(detail["session"]["target"])
        self.assertEqual(detail["session"]["identity_origin"], "ordinal-reserved")
        self.assertTrue(detail["events"])
        other = self.service.create_effort({"intent": "foreign", "environment": {"cwd": str(self.workspace)}})["ordinal"]
        self.assertEqual(self.request(f"/api/developer-sessions/{reserved['id']}?effort_root={other}")[0], 400)
        self.assertEqual(self.request(f"/api/developer-sessions/{reserved['id']}/prompt", {"effort_root": effort, "message": "must never run"})[0], 409)
        self.assertEqual(self.request(f"/api/developer-sessions/{reserved['id']}/reopen", {"effort_root": effort})[0], 409)
        self.assertFalse(any(e["record"].get("type") == "prompt" for e in detail["events"]))

    def test_ordinal_http_exact_history_scope_and_queued_succession(self):
        first = self.start()
        self.wait(first["id"])
        ordinal, effort = first["ordinal"], first["effort_root"]
        status, root = self.request("/api/ordinals/0")
        self.assertEqual(status, 200, root)
        self.assertIsNone(root["position"]["current_instantiation"])
        status, binding = self.request("/api/actions", {"target": first["target"], "kind": "prompt", "payload": {"message": "never successor"}, "effort_root": effort})
        self.assertEqual(status, 200, binding)
        successor = self.start(effort_root=effort, succession={"predecessor": 1, "handoff": {"reason": "fixture succession"}})
        self.wait(successor["id"])
        self.assertEqual(self.request(f"/api/actions/{binding['id']}/deliver", {"effort_root": effort})[0], 409)
        target = first["target"]
        status, history = self.request(f"/api/developer-sessions/{ordinal}?instantiation={target['instantiation']}&session={target['session']}&effort_root={effort}")
        self.assertEqual(status, 200, history)
        self.assertEqual(history["session"]["id"], first["id"])
        other = self.start("B")
        status, mismatch = self.request(f"/api/developer-sessions/{other['ordinal']}/prompt", {"message": "reject A to B", "effort_root": effort})
        self.assertEqual(status, 400, mismatch)
        status, sent = self.request(f"/api/developer-sessions/{ordinal}/prompt", {"message": "correct successor", "effort_root": effort})
        self.assertEqual(status, 200, sent)
        self.assertEqual(sent["target"], successor["target"])
        self.assertEqual(sent["native_ref"]["session_id"], successor["native_session_id"])
        status, branch = self.request("/api/ordinals/0/branch?limit=2")
        self.assertEqual(status, 200, branch)
        self.assertEqual(len(branch["records"]), 2)
        status, later = self.request(f"/api/ordinals/0/branch?limit=2&after={branch['next_after']}")
        self.assertEqual(status, 200, later)
        self.assertTrue(later["records"])

    def test_local_read_empty_registry_and_open_existing_never_create_project(self):
        self.assertFalse(self.runs.exists())
        self.assertEqual(self.request("/api/developer-sessions", stale_header=True)[0], 200)
        self.assertFalse(self.runs.exists())
        self.assertEqual(self.request("/api/developer-sessions")[1]["sessions"], [])
        self.assertFalse(self.runs.exists())
        missing = self.home / "missing-project"
        status, _ = self.request("/api/developer-sessions", {"workspace": str(missing), "prompt": "build"})
        self.assertEqual(status, 400)
        self.assertFalse(missing.exists())
        self.assertFalse(self.runs.exists())

    def test_create_project_performs_git_init_then_real_root_and_preserves_existing_files(self):
        target = self.home / "new-app"
        status, result = self.request("/api/developer-projects", {"directory": str(target), "prompt": "Build my app", "title": "My app", "model": "custom/selected-model", "thinking": "low"})
        self.assertEqual(status, 201, result)
        self.assertTrue((target / ".git").is_dir())
        self.assertEqual(result["session"]["workspace"], str(target))
        self.assertEqual(result["session"]["ordinal"], "0.0")
        self.assertEqual(result["session"]["model"], "custom/selected-model")
        self.assertEqual(result["session"]["title"], "My app")
        (target / "user-file.txt").write_bytes(b"preserve exact existing bytes")
        before = {str(path.relative_to(target)): path.read_bytes() for path in target.rglob("*") if path.is_file()}
        status, _ = self.request("/api/developer-projects", {"directory": str(target), "prompt": "overwrite?"})
        self.assertEqual(status, 409)
        self.assertEqual({str(path.relative_to(target)): path.read_bytes() for path in target.rglob("*") if path.is_file()}, before)
        invalid = self.home / "invalid-app"
        status, _ = self.request("/api/developer-projects", {"directory": str(invalid), "prompt": "build", "thinking": "unknown"})
        self.assertEqual(status, 400)
        self.assertFalse(invalid.exists())

    def test_project_names_use_explicit_location_and_open_preserves_existing_folder(self):
        target = self.home / "named-app"
        status, result = self.request("/api/developer-projects", {"directory":"named-app", "projects_root":str(self.home), "prompt":"build"})
        self.assertEqual(status, 201, result)
        self.assertEqual(result["session"]["workspace"], str(target))
        existing = self.home / "existing-normal"
        existing.mkdir(); (existing / "owner.txt").write_bytes(b"keep")
        effort = self.service.create_effort({"intent": "change existing", "environment": {"cwd": str(existing)}})["ordinal"]
        status, result = self.request("/api/developer-sessions", {"workspace":str(existing), "effort_root": effort, "prompt":"change app"})
        self.assertEqual(status, 201, result)
        self.assertFalse((existing / ".git").exists())
        self.assertEqual((existing / "owner.txt").read_bytes(), b"keep")
        invalid = self.home / "invalid-location"
        status, _ = self.request("/api/developer-projects", {"directory":str(invalid), "projects_root":{}, "prompt":"build"})
        self.assertEqual(status, 400)
        self.assertFalse(invalid.exists())

    def test_registered_project_source_view_is_authenticated_bounded_and_read_only(self):
        item = self.start()
        target = self.workspace / "app.py"
        target.write_text("print('usable source')\n")
        source = target.read_bytes(), target.stat().st_mtime_ns
        route = f"/api/developer-sessions/{item['id']}/file?path=app.py"
        self.assertEqual(self.request(route, stale_header=True)[0], 200)
        status, result = self.request(route)
        self.assertEqual(status, 200, result)
        self.assertEqual(result["text"], "print('usable source')\n")
        self.assertEqual((target.read_bytes(), target.stat().st_mtime_ns), source)
        legacy = runtime.create_run({"goal":"Legacy actual project"}, self.workspace, self.runs)
        status, historical = self.request(f"/api/runs/{legacy.name}/project-file?path=app.py&scope=application")
        self.assertEqual(status, 200, historical)
        self.assertEqual(historical["text"], result["text"])
        self.assertEqual(self.request(f"/api/developer-sessions/{item['id']}/file?path=../outside")[0], 400)
        self.assertEqual(self.request(f"/api/developer-sessions/{item['id']}/file?path=.git/config")[0], 400)
        (self.workspace / "large").write_bytes(b'x' * (256 * 1024 + 1))
        self.assertEqual(self.request(f"/api/developer-sessions/{item['id']}/file?path=large")[0], 413)
        (self.workspace / "binary").write_bytes(b'\xff')
        self.assertEqual(self.request(f"/api/developer-sessions/{item['id']}/file?path=binary")[0], 415)

    def test_live_broker_blocks_real_maintenance_then_shutdown_reopen_preserves_ownership(self):
        item = self.start("slow root")
        with self.assertRaisesRegex(ValueError, "Owned state lock"):
            with release.maintenance(self.app_home, False, code_only=True):
                self.fail("live broker permitted code maintenance")
        self.assertTrue(self.service.inspect(item["id"])["broker_owned"])
        status, _ = self.request(f"/api/developer-sessions/{item['id']}/shutdown", {})
        self.assertEqual(status, 200)
        self.wait(item["id"], "closed")
        deadline = time.monotonic() + 5
        while self.service.inspect(item["id"])["broker_owned"] and time.monotonic() < deadline:
            time.sleep(.05)
        with release.maintenance(self.app_home, False, code_only=True):
            observed = release._check_code_state(self.app_home / "state", False)
        self.assertFalse(self.service.inspect(item["id"])["broker_owned"])
        self.assertTrue(self.service.inspect(item["id"])["process"]["cleanup_confirmed"])
        self.assertEqual(observed["history_assessment"], "not_performed")
        self.assertFalse(observed["historical_cleanup_confirmed"])
        status, reopened = self.request(f"/api/developer-sessions/{item['id']}/reopen", {})
        self.assertEqual(status, 200, reopened)
        self.assertEqual(reopened["session"]["id"], item["id"])
        self.assertTrue(reopened["session"]["broker_owned"])
        self.assertNotEqual(reopened["session"]["process"]["identity"], item["process"]["identity"])

    def test_real_http_steer_delegate_and_restart_reconnect_without_actor_restart(self):
        root = self.start("slow root")
        sid = root["id"]
        self.assertEqual(self.request(f"/api/developer-sessions/{sid}/prompt", {"message": "steer", "mode": "steer"})[0], 200)
        self.assertEqual(self.request(f"/api/developer-sessions/{sid}/stop", {})[1]["stopped"], True)
        status, child = self.request(f"/api/developer-sessions/{sid}/delegate", {"prompt": "bounded task", "thinking": "low"})
        self.assertEqual(status, 200, child)
        self.assertEqual(child["ordinal"], "0.0.0")
        self.assertEqual(child["parent_id"], sid)
        self.stop_server()
        self.server = web.create_server(self.runs, port=0, session_command=[sys.executable, str(FIXTURE)], namespace_path=self.runs / "ordinals.sqlite3")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        status, reopened_view = self.request(f"/api/developer-sessions/{sid}")
        self.assertEqual(status, 200, reopened_view)
        self.assertEqual(reopened_view["session"]["process"]["identity"], root["process"]["identity"])
        self.assertTrue(reopened_view["session"]["broker_owned"])
        self.assertEqual(len(reopened_view["tree"]), 2)
        self.assertEqual(self.request(f"/api/developer-sessions/{sid}/prompt", {"message": "unknown", "mode": "telepathy"})[0], 400)
        self.assertEqual(self.request(f"/api/developer-sessions/{sid}/stop", {"unknown": True})[0], 400)
        self.assertEqual(self.request(f"/api/developer-sessions/{sid}/prompt", {"message": "must not run"}, method="PUT")[0], 405)


if __name__ == "__main__":
    unittest.main()
