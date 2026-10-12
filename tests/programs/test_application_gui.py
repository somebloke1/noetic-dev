"""Model-free HTTP/application implementation checks; no independent QA or real-run writes."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from scripts import noetic_application as application
from scripts import noetic_controller as controller
from scripts import noetic_disciplines as disciplines
from scripts.noetic_scope import ScopeStore
from scripts import noetic_harness as harness
from scripts import noetic_local as local
from scripts import noetic_run as runtime
from scripts import noetic_telos as telos
from scripts import noetic_web as web
from tests.programs.test_noetic_harness import result_for


def fixture_actor(run, state, options):
    """Invoked only by test child processes in temporary Git workspaces."""
    assert "USER_PROVIDED_PASSWORD" not in os.environ
    actor = state["activations"][state["current_activation"]]
    sources = state["artifacts"][state["slots"]["external.sources"]]["content"]
    refs = [source["ref"] for source in sources]
    if "fixture:check-env" in refs:
        assert os.environ.get("FIXTURE_PROVIDER_KEY") == "normal-env"
    directory = run / "activations" / actor["id"]
    # These tests replace model inference, not process ownership. Retain a real,
    # reaped no-op actor before testing unrelated driver/checkpoint behavior.
    observed = harness._execute(run, directory, Path(state["workspace"]), "actor",
                                [sys.executable, "-c", "pass"], 5)
    assert observed["state"] == "passed"
    if "fixture:block" in refs and actor["id"] == "activation-0":
        (run / "fixture.waiting").write_text("Waiting in a model-free actor")
        deadline = time.monotonic() + 15
        while not (run / "fixture.release").exists() and time.monotonic() < deadline:
            time.sleep(.02)
    if "fixture:crash" in refs:
        raise RuntimeError("Test-authored background boundary failure; no actor replay")
    phase = state["pattern"]["phases"][state["phase_index"]]
    if actor["mode"] == "review":
        result = {"subject_artifact_id": state["subject_artifact_id"], "verdict": "pass", "report": "Fixture criteria check", "findings": []}
    else:
        result = {"outcome": "produced" if actor["mode"] == "produce" else "complete" if actor["phase"] == "P4" else "advance",
                  "content": {key: "Fixture result" if kind == "string" else [] for key, kind in phase["content_fields"].items()}}
    if "fixture:return" in refs and actor["phase"] == "P2" and actor["visit"] == 1:
        result = {"outcome": "return", "target": "P1", "reason": "Fixture requires another measurement",
                  "question": "What is the observed measurement?", "content": {"hypotheses": ["Fixture partial explanation"]}}
    if options["client"] == "pi":
        assistant = {"role": "assistant", "model": "fixture-observed-model", "provider": "fixture-provider", "timestamp": 1700000000000,
                     "content": [{"type": "text", "text": json.dumps(result)}], "stopReason": "stop"}
        records = [{"type": "session", "id": f"fixture-{actor['id']}"},
                   {"type": "tool_execution_start", "toolName": "read", "args": {"path": "fixture.txt"}, "timestamp": 1700000000000},
                   {"type": "tool_execution_end", "toolName": "read", "result": {"content": [{"text": "Fixture data"}]}, "isError": False},
                   {"type": "message_end", "message": assistant}, {"type": "agent_end", "messages": [assistant]}]
    else:
        records = [{"type": "step_start", "sessionID": f"fixture-{actor['id']}", "timestamp": 1700000000000, "part": {"messageID": "message-1"}},
                   {"type": "tool_use", "part": {"tool": "read", "state": {"status": "completed", "input": {"filePath": "fixture.txt"}, "output": "Fixture data"}}},
                   {"type": "text", "part": {"id": "part-1", "messageID": "message-1", "text": json.dumps(result)}},
                   {"type": "step_finish", "part": {"reason": "stop", "messageID": "message-1"}}]
    (directory / "actor.stdout.log").write_text("\n".join(json.dumps(row) for row in records) + "\n")
    (directory / "prompt.txt").write_text("Fixture frozen role context")
    if options.get("scope"):
        harness._observe_native(run, state, options, {"client": options["client"], "session_id": f"fixture-{actor['id']}",
            "context_file": str(directory / "actor.stdout.log"), "observation": "test-authored-fake-client-output"})
    return {"result": result, "session_ref": f"{options['client']}:fixture-{actor['id']}"}


class ApplicationGuiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        environment = patch.dict(os.environ, {"NOETIC_APP_HOME": ""})
        environment.start()
        self.addCleanup(environment.stop)
        self.runs = self.root / "runs"
        self.workspace = self.git_workspace("workspace")
        self.db = self.root / "purpose-db" / "telos.sqlite3"
        self.namespace = self.runs / "ordinals.sqlite3"
        store = ScopeStore(self.namespace, root_mandate={"purpose": "Fixture human coordination"},
                           human_ref={"fixture": "human"}, source_ref={"fixture": "setup"})
        self.effort = store.create_effort(intent="GUI compatibility fixture", environment={"cwd": str(self.workspace)},
            mandate={"purpose": "GUI fixture"}, origin="human", human_ref={"fixture": "human"}, source_ref={"fixture": "setup"})
        self.server = web.create_server(self.runs, port=0, telos_db=self.db, namespace_path=self.namespace)
        self.server.application.work_root = self.root / "worktrees"
        self.server.RequestHandlerClass.log_message = lambda *args: None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        original = subprocess.Popen

        def fixture_process(argv, **kwargs):
            if "scripts.noetic_application" in argv:
                index = argv.index("scripts.noetic_application")
                _, run, maximum, fd, slot_fd = argv[index + 1:]
                code = ("import sys; from scripts import noetic_application as a; from tests.programs.test_application_gui import fixture_actor; "
                        "a.harness.invoke_actor = fixture_actor; "
                        "raise SystemExit(a.driver_main(sys.argv[1], None if sys.argv[2] == 'all' else int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])))")
                argv = [sys.executable, "-B", "-c", code, run, maximum, fd, slot_fd]
            return original(argv, **kwargs)

        self.spawn = patch.object(application.subprocess, "Popen", side_effect=fixture_process)
        self.spawn.start()
        self.addCleanup(self.spawn.stop)
        self.addCleanup(self.finish_children)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)

    def finish_children(self):
        for run in self.runs.glob("*"):
            if run.is_dir() and (run / "fixture.waiting").exists():
                (run / "fixture.release").write_text("Test cleanup release")
        for child in self.server.application.children:
            child.wait(timeout=20)

    def git_workspace(self, name):
        path = self.root / name
        path.mkdir()
        subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True)
        (path / "fixture.txt").write_text("Fixture data")
        return path

    def request(self, route, expected=200, method="GET", data=None, headers=None, server=None):
        server = server or self.server
        if method in ("GET", "HEAD") and route.startswith(("/api/runs", "/api/goals", "/api/search")):
            route += ("&" if "?" in route else "?") + "scope=application"
        if method == "POST" and isinstance(data, dict):
            data = dict(data)
            if route.startswith("/api/runs/") or route in ("/api/goals", "/api/memory/semantic"):
                data.setdefault("scope", "application")
            if route == "/api/goals":
                data.update(origin_ref={"fixture": "human"}, source_ref={"fixture": "create-purpose"})
            if route == "/api/application/start" and isinstance(data.get("workspace"), str) and data.get("task"):
                effort = self.effort
                requested_workspace = Path(data["workspace"]).resolve()
                if requested_workspace != self.workspace:
                    effort = ScopeStore(self.namespace).create_effort(intent="Separate GUI fixture project", environment={"cwd": str(requested_workspace)},
                        mandate={"purpose": "GUI fixture"}, origin="human", human_ref={"fixture": "human"}, source_ref={"fixture": "other-project"})
                instance = disciplines.Disciplines(self.namespace).create_instance(command_id=str(__import__('uuid').uuid4()),
                    effort_root=effort["ordinal"], initiator=effort["ordinal"], pattern=data.get("pattern", "development"),
                    intent=data["task"], environment=effort["environment"])
                data.update(effort_root=effort["ordinal"], discipline_id=instance["id"], environment=instance["environment"],
                            origin="human", human_ref={"fixture": "explicit-human-assignment"})
                data.pop("telos_chain", None)
        with closing(http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=30)) as connection:
            connection.request(method, route, body=json.dumps(data) if data is not None else None,
                               headers={"Authorization": f"Bearer {server.token}", **(headers if headers is not None else {"Content-Type": "application/json"})})
            response = connection.getresponse()
            body = response.read()
            self.assertEqual(response.status, expected, body)
            return json.loads(body) if body else None

    def start(self, **options):
        body = {"pattern": "cognition", "workspace": str(self.workspace), "task": "Model-free GUI fixture",
                "client": "pi", "model": "fixture/configured-model", "sources": [], **options}
        return self.request("/api/application/start", 202, "POST", body)

    def wait_for(self, predicate):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(.03)
        self.fail("Temporary driver did not reach the expected fixture state")

    def detail(self, run_id):
        return self.request(f"/api/runs/{run_id}")

    def terminal(self, run_id):
        return self.wait_for(lambda: (d if d["controller"]["status"] != "active" and not d["application"]["gui_driver_owned"] else None)
                             if (d := self.detail(run_id)) else None)

    def test_start_full_development_and_cognition_with_real_background_drivers(self):
        profiles = self.request("/api/configuration")["profiles"]
        with patch.dict(os.environ, {"USER_PROVIDED_PASSWORD": "must-not-inherit", "FIXTURE_PROVIDER_KEY": "normal-env"}):
            result = self.start(client=profiles[0]["client"], model=profiles[0]["model"], pattern="development", verify=[sys.executable, "-c", "assert 2 + 2 == 4"], qa_model="fixture/qa-model", sources=["fixture:check-env"])
        detail = self.terminal(result["run_id"])
        self.assertEqual(detail["controller"]["status"], "completed")
        self.assertEqual(len(detail["controller"]["actors"]), 8)
        (self.runs / result["run_id"] / "pause.requested").write_text("Fixture request overtaken by terminal state")
        self.assertFalse(self.detail(result["run_id"])["application"]["pause_applied"])
        summary = self.request("/api/runs")["runs"][0]
        self.assertEqual(summary["population"][0]["configured_model"], profiles[0]["model"])
        self.assertEqual(summary["population"][1]["configured_model"], "fixture/qa-model")
        result = self.start(sources=["fixture:return"], client=profiles[1]["client"], model=profiles[1]["model"])
        detail = self.terminal(result["run_id"])
        state = detail["controller"]
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["returns_used"], 1)
        self.assertEqual(len(state["actors"]), 6)
        self.assertEqual(detail["application"]["activity"], "terminal")
        summary = next(r for r in self.request("/api/runs")["runs"] if r["run_id"] == result["run_id"])
        self.assertTrue(all(actor["configured_model"] == profiles[1]["model"] for actor in summary["population"]))
        feed = summary["attention"]
        self.assertEqual(feed[0]["kind"], "Return")

    def test_pause_after_current_then_advance_one_all_and_workspace_exclusion(self):
        result = self.start(sources=["fixture:block"])
        run_id = result["run_id"]
        run = self.runs / run_id
        self.wait_for(lambda: (run / "fixture.waiting").exists())
        self.request("/api/application/start", 409, "POST", {"workspace": str(self.workspace), "task": "Duplicate", "pattern": "cognition"})
        second = self.start(workspace=str(self.git_workspace("other-workspace")))
        self.terminal(second["run_id"])
        self.request(f"/api/runs/{run_id}/pause", 202, "POST", {})
        self.assertEqual(self.detail(run_id)["application"]["activity"], "pause_requested")
        (run / "fixture.release").write_text("Release current actor")
        held = self.wait_for(lambda: d if (d := self.detail(run_id))["application"]["pause_applied"] else None)
        self.assertEqual(held["controller"]["current_activation"], "activation-1")
        self.assertEqual(held["controller"]["activations"]["activation-0"]["status"], "retired")
        self.assertEqual(held["controller"]["activations"]["activation-1"]["status"], "ready")
        self.request(f"/api/runs/{run_id}/advance", 202, "POST", {"mode": "one"})
        advanced = self.wait_for(lambda: d if (d := self.detail(run_id))["application"]["activity"] == "held"
                                 and d["controller"]["current_activation"] == "activation-2" else None)
        self.assertFalse(advanced["application"]["pause_requested"])
        self.request(f"/api/runs/{run_id}/advance", 202, "POST", {"mode": "all"})
        self.assertEqual(self.terminal(run_id)["controller"]["status"], "completed")
        self.request(f"/api/runs/{run_id}/advance", 409, "POST", {"mode": "one"})

    def test_capacity_http_refusal_creates_no_phantom_run(self):
        first = self.start(sources=["fixture:block"])
        second = self.start(workspace=str(self.git_workspace("second")), sources=["fixture:block"])
        for result in (first, second):
            self.wait_for(lambda: (self.runs / result["run_id"] / "fixture.waiting").exists())
        before = set(self.runs.glob("*/controller.sqlite3"))
        result = self.request("/api/application/start", 409, "POST", {
            "pattern": "cognition", "task": "Refused before creation",
            "workspace": str(self.git_workspace("third"))})
        self.assertIn("limit 2", result["error"])
        self.assertIn(str(self.runs), result["error"])
        self.assertIn("no work queued", result["error"])
        self.assertFalse(result.get("run_id"))
        self.assertEqual(set(self.runs.glob("*/controller.sqlite3")), before)

    def test_reconnect_and_cancel_do_not_depend_on_web_server_lifetime(self):
        result = self.start(sources=["fixture:block"])
        run_id = result["run_id"]
        run = self.runs / run_id
        self.wait_for(lambda: (run / "fixture.waiting").exists())
        self.close_server()
        with web.create_server(self.runs, port=0) as reopened:
            reopened.RequestHandlerClass.log_message = lambda *args: None
            thread = threading.Thread(target=reopened.serve_forever, daemon=True)
            thread.start()
            try:
                observed = self.request(f"/api/runs/{run_id}", server=reopened)
                self.assertTrue(observed["application"]["gui_driver_owned"])
                self.request(f"/api/runs/{run_id}/advance", 409, "POST", {"mode": "all"}, server=reopened)
                self.request(f"/api/runs/{run_id}/cancel", 202, "POST", {"confirm": True}, server=reopened)
                self.assertEqual(self.request(f"/api/runs/{run_id}", server=reopened)["application"]["activity"], "cancel_requested")
                (run / "fixture.release").write_text("Release to cancellation boundary")
                self.wait_for(lambda: self.request(f"/api/runs/{run_id}", server=reopened)["controller"]["status"] == "cancelled")
            finally:
                reopened.shutdown()
                thread.join(5)
        self.assertEqual(controller.inspect_run(run / "controller.sqlite3")["status"], "cancelled")
        self.wait_for(lambda: all(child.poll() is not None for child in self.server.application.children))
        with harness.driver_slot(self.runs), harness.driver_slot(self.runs):
            pass

    def test_background_failure_and_ambiguous_effects_are_visible_and_not_replayed(self):
        result = self.start(sources=["fixture:crash"])
        detail = self.wait_for(lambda: d if (d := self.detail(result["run_id"]))["application"]["driver"].get("status") == "failed" else None)
        self.wait_for(lambda: not self.detail(result["run_id"])["application"]["gui_driver_owned"])
        detail = self.detail(result["run_id"])
        self.assertIn("boundary failure", detail["application"]["driver"]["error"])
        self.assertEqual(detail["application"]["activity"], "intervention")
        before = detail["controller"]
        self.request(f"/api/runs/{result['run_id']}/advance", 409, "POST", {"mode": "all"})
        self.assertEqual(self.detail(result["run_id"])["controller"], before)
        self.request(f"/api/runs/{result['run_id']}/cancel", 200, "POST", {"confirm": True})

    def test_spawn_failure_retains_run_id_and_error_without_claiming_work(self):
        with patch.object(application.subprocess, "Popen", side_effect=OSError("Fixture process launch unavailable")):
            # Workspace validation itself uses subprocess.run, so isolate only the launch boundary.
            with patch.object(application, "workspace_path", return_value=self.workspace):
                result = self.request("/api/application/start", 422, "POST", {"workspace": str(self.workspace), "task": "Fixture", "pattern": "cognition"})
        self.assertTrue(result["run_id"])
        detail = self.detail(result["run_id"])
        self.assertEqual(detail["application"]["activity"], "failed")
        self.assertEqual(detail["controller"]["activations"]["activation-0"]["status"], "ready")
        with harness.driver_slot(self.runs), harness.driver_slot(self.runs):
            pass

    def test_invalid_launch_json_origin_and_legacy_controls(self):
        for payload in ({"task": "No workspace"}, {"task": "Invalid verify", "workspace": str(self.workspace), "verify": []},
                        {"task": "Bad budget", "workspace": str(self.workspace), "pattern": "cognition", "max_returns": -1},
                        {"task": "Shell", "workspace": str(self.workspace), "verify": "rm something"}):
            self.request("/api/application/start", 400, "POST", payload)
        for route in ("/api/application/start", "/api/goals", "/api/memory/semantic", "/api/diagnostics/refresh"):
            self.request(route, 415, "POST", {}, headers={"Content-Type": "text/plain"})
            self.request(route, 403, "POST", {}, headers={"Content-Type": "application/json", "Origin": "http://elsewhere.invalid"})
        run = runtime.create_run({"goal": "Legacy fixture"}, self.workspace, self.runs)
        for action, body in (("pause", {}), ("advance", {"mode": "one"})):
            self.request(f"/api/runs/{run.name}/{action}", 409, "POST", body)
        self.assertFalse((run / "controller.sqlite3").exists())

    def test_structured_pi_opencode_and_raw_transcripts_for_retired_sessions(self):
        for client in ("pi", "opencode"):
            result = self.start(client=client)
            run_id = result["run_id"]
            self.terminal(run_id)
            response = self.request(f"/api/runs/{run_id}/activations/activation-0/transcript")
            self.assertTrue(response["observed_sessions"])
            self.assertTrue(any(e["kind"] == "assistant" for e in response["entries"]))
            self.assertTrue(any(e["kind"] == "tool" for e in response["entries"]))
            if client == "pi":
                self.assertEqual(response["observed_models"][0]["model"], "fixture-observed-model")
                self.assertTrue(any(e["kind"] == "final" for e in response["entries"]))
            else:
                self.assertEqual(response["observed_models"], [])
            source = self.runs / run_id / "activations/activation-0/actor.stdout.log"
            source.write_text("not yet complete\n" + source.read_text() + '{"partial"')
            response = self.request(f"/api/runs/{run_id}/activations/activation-0/transcript")
            self.assertEqual(response["unparsed_lines"], 2)
            self.assertIn("partial", response["text"])
            self.request(f"/api/runs/{run_id}/activations/activation-999/transcript", 404)

    def test_goal_create_select_read_uses_real_telos_and_get_never_initializes(self):
        self.assertFalse(self.db.exists())
        result = self.request("/api/goals")
        self.assertTrue(all(store["status"] == "absent" for store in result["stores"]))
        self.assertFalse(self.db.parent.exists())
        if not (telos.source_path() / "node_modules/tsx/dist/loader.mjs").is_file() or not shutil.which("node"):
            self.skipTest("Native Telos source/Node unavailable for the create/read fixture")
        result = self.request("/api/goals", 201, "POST", {"goal": "Test-authored governing purpose"})
        reference = result["purpose"]["reference"]
        chain = reference["chain_id"]
        database = Path(reference["db_path"])
        before = (database.read_bytes(), database.stat().st_mtime_ns)
        goals = self.request("/api/goals")["purposes"]
        self.assertEqual(goals[0]["native"]["chain"]["chainId"], chain)
        self.assertEqual(self.request(f"/api/goals/{chain}")["purpose"], goals[0])
        self.assertEqual((database.read_bytes(), database.stat().st_mtime_ns), before)
        # New work binds the selected effort's native purpose store.
        effort_goal = self.server.application.create_goal({"goal": "Fixture governing effort purpose", "effort_root": self.effort["ordinal"],
            "origin_ref": {"fixture": "human"}, "source_ref": {"fixture": "purpose"}})["purpose"]
        chain = effort_goal["reference"]["chain_id"]
        run = self.start(purpose_ref=effort_goal["reference"])
        detail = self.terminal(run["run_id"])
        self.assertIn("external.governing", detail["controller"]["slots"])
        self.assertEqual(detail["status"]["telos"]["chain_id"], chain)
        self.assertEqual(self.request(f"/api/goals/{chain}")["purpose"]["native"]["chain"]["status"], "active")

    def test_legacy_worker_reviewer_transcripts_are_authenticated_bounded_readonly(self):
        run = runtime.create_run({"goal": "Historical agent task"}, self.workspace, self.runs)
        runtime.record(run, "program.started", {"client": "pi", "model": "fixture/explicit"})
        for role in ("work", "review"):
            runtime.record(run, "step.started", {"step": role, "argv": ["pi", "--model", "fixture/explicit"]})
            content = {"type": "message_end", "message": {"role": "assistant", "model": "fixture/observed",
                       "content": [{"type": "text", "text": f"{role} useful output <script>literal</script>"}]}}
            (run / f"{role}.stdout.log").write_text("x" * web.ARTIFACT_LIMIT + "\n" + json.dumps(content) + "\n")
            (run / f"{role}.json").write_text(json.dumps({"client": "pi", "session_id": f"fixture-{role}"}))
        snapshot = lambda: {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in run.iterdir() if p.is_file()}
        before = snapshot()
        for role in ("work", "review"):
            route = f"/api/runs/{run.name}/sessions/{role}/transcript"
            self.request(route, 401, headers={"Authorization": ""})
            response = self.request(route)
            self.assertTrue(response["truncated"])
            self.assertGreater(response["byte_start"], 0)
            self.assertEqual(response["configuration"]["model"], "fixture/explicit")
            self.assertEqual(response["entries"][0]["kind"], "assistant")
            self.assertIn(f"{role} useful output", response["entries"][0]["content"])
            self.request(route, method="HEAD")
            self.request(route, 405, "POST", {})
        self.assertEqual(snapshot(), before)
        self.request(f"/api/runs/{run.name}/sessions/unknown/transcript", 404)
        (run / "review.stdout.log").unlink()
        self.request(f"/api/runs/{run.name}/sessions/review/transcript", 404)
        (run / "work.stdout.log").unlink()
        (run / "work.stdout.log").symlink_to(self.workspace / "fixture.txt")
        self.request(f"/api/runs/{run.name}/sessions/work/transcript", 403)

    def test_memory_summary_and_diagnostics_are_explicit_with_mock_local_http(self):
        run = self.start()
        self.terminal(run["run_id"])
        calls = []

        class LocalHandler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                calls.append(self.path)
                data = {"models": [{"name": "fixture-embedding", "size_vram": 12, "secret": "not-exposed"}]}
                self.send(data)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append((self.path, body))
                if self.path.endswith("/embeddings"):
                    self.send({"data": [{"index": i, "embedding": [1, 0, 0]} for i in range(len(body["input"]))]})
                else:
                    self.send({"choices": [{"message": {"content": "Fixture non-authoritative summary"}, "finish_reason": "stop"}]})

            def send(self, data):
                encoded = json.dumps(data).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        with ThreadingHTTPServer(("127.0.0.1", 0), LocalHandler) as service:
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{service.server_port}"
            settings = local.Settings(base_url=url + "/v1", dimensions=3)
            try:
                with patch.object(local, "load_settings", return_value=settings), patch.dict(os.environ, {"LITELLM_API_KEY": "fixture-key"}), \
                        patch.object(application, "HEALTH_ENDPOINTS", {"Qwen": url + "/health", "Ollama": url + "/api/ps", "LiteLLM": url + "/health/liveliness"}):
                    config = self.request("/api/configuration")
                    self.assertEqual(len(config["profiles"]), 2)
                    self.request("/api/diagnostics")
                    self.request("/api/runs")
                    self.detail(run["run_id"])
                    self.assertEqual(calls, [])
                    health = self.request("/api/diagnostics/refresh", 200, "POST", {})
                    self.assertEqual(len(calls), 3)
                    self.assertNotIn("secret", json.dumps(health))
                    self.assertEqual(self.request("/api/diagnostics")["observed_at"], health["observed_at"])
                    self.assertEqual(len(calls), 3)
                    first = self.request("/api/memory/semantic", 200, "POST", {"query": "Fixture"})
                    self.assertTrue(first["results"])
                    self.assertTrue(all("namespace" in result for result in first["results"]))
                    self.assertIn("byte_start", first["results"][0])
                    self.assertTrue(Path(first["cache"]).exists())
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        results = list(executor.map(lambda _: self.request("/api/memory/semantic", 200, "POST", {"query": "Fixture"}), range(2)))
                    self.assertTrue(all(r["index"]["embedded_texts"] == 0 for r in results))
                    with patch.object(local, "load_settings", return_value=replace(settings, embedding_model="changed-identity")):
                        self.assertIn("identity mismatch", self.request("/api/memory/semantic", 422, "POST", {"query": "Fixture"})["error"])
                        self.request("/api/memory/semantic", 200, "POST", {"query": "Fixture", "reindex": True})
                    store = self.runs / run["run_id"] / "controller.sqlite3"
                    before = store.read_bytes()
                    summary = self.request(f"/api/runs/{run['run_id']}/summary", 200, "POST", {"save": True})
                    self.assertFalse(summary["authoritative"])
                    self.assertFalse(summary["advances_state"])
                    self.assertIn("coverage", summary)
                    self.assertEqual(store.read_bytes(), before)
                    self.assertTrue((store.parent / "summary.json").exists())
            finally:
                service.shutdown()
                thread.join(5)

    def test_unavailable_local_support_is_an_error_without_lexical_fallback(self):
        run = self.start()
        self.terminal(run["run_id"])
        with patch.dict(os.environ, {}, clear=True):
            result = self.request("/api/memory/semantic", 422, "POST", {"query": "fixture"})
            self.assertIn("credential", result["error"])
            self.assertNotIn("results", result)
            self.request(f"/api/runs/{run['run_id']}/summary", 422, "POST", {})

    def test_mobile_and_workbench_dom_structure_contract(self):
        html = (web.WEB_DIR / "index.html").read_text()
        css = (web.WEB_DIR / "style.css").read_text()
        for page in ("workspace", "new", "history", "memory", "purposes", "diagnostics"):
            self.assertIn(f'data-page="{page}"', html)
            self.assertIn(f'id="{page}-page"', html)
        for view in ("phases", "session", "compare"):
            self.assertIn(f'aria-controls="{view}-view"', html)
        self.assertIn('aria-controls="operator-rail"', html)
        self.assertIn(".run-rail.navigation-open { display: block; }", css)
        self.assertIn("@media (max-width: 760px)", css)
        self.assertIn(".form-grid, .phase-columns { grid-template-columns: minmax(0, 1fr); }", css)
        self.assertIn("resize: horizontal", css)
        self.assertIn('id="session-transcript" class="transcript" tabindex="0"', html)
        self.assertNotIn("requires a wider viewport", html)

    def test_reuse_setup_exact_mapping_readonly_auth_and_new_run_guards(self):
        task = "  Exact purpose\nwith acceptance criteria and trailing spaces  "
        refs = ["docs/a file.md", "https://example.invalid/a?q=two words", "docs/a file.md"]
        for pattern in ("development", "cognition"):
            run, _ = harness.start(pattern, task, self.workspace, self.runs,
                client="opencode", model="fixture/main", qa_model="fixture/qa", thinking="high",
                verify=[sys.executable, "-c", "assert 'two words' == 'two words'"] if pattern == "development" else None,
                max_returns=0, max_remediations=0, timeout=123, max_activations=0,
                goal_ref="fixture:old-goal", inputs={"sources": [{"ref": ref} for ref in refs]})
            route = f"/api/runs/{run.name}/reuse-setup"
            snapshot = lambda: {str(p.relative_to(self.runs)): (p.read_bytes(), p.stat().st_mtime_ns)
                                for p in self.runs.rglob("*") if p.is_file()}
            before = snapshot()
            with patch.object(harness, "start", side_effect=AssertionError("GET must not start")), \
                    patch.object(harness, "drive", side_effect=AssertionError("GET must not drive")), \
                    patch.object(harness, "resume", side_effect=AssertionError("GET must not resume")), \
                    patch.object(application.subprocess, "Popen", side_effect=AssertionError("GET must not spawn")):
                self.request(route, 401, headers={"Authorization": ""})
                self.request(route, method="HEAD")
                setup = self.request(route)
                self.request(route, 405, "POST", {})
            self.assertEqual(snapshot(), before)
            fields = setup["fields"]
            self.assertEqual(fields["task"], task)
            self.assertEqual(fields["workspace"], str(self.workspace))
            self.assertEqual(fields["sources"], refs)
            self.assertEqual(fields["max_returns"], 0)
            self.assertEqual(fields["max_remediations"], 0)
            self.assertEqual(fields["timeout"], 123)
            self.assertEqual(fields["client"], "opencode")
            self.assertEqual(fields["model"], "fixture/main")
            self.assertEqual(fields["qa_model"], "fixture/qa")
            self.assertIsNone(fields["telos_chain"])
            self.assertNotIn("goal_ref", fields)
            self.assertIn("not resumed/cloned", " ".join(setup["warnings"]))
            self.request("/api/application/start", 409, "POST", fields)
            def historical_actor(run, state, options):
                return {"result": result_for(state),
                        "session_ref": f"opencode:fixture-origin-{state['current_activation']}"}

            with patch.object(harness, "invoke_actor", side_effect=historical_actor):
                _, historical = harness.drive(run)
            old_sessions = {actor["session_ref"] for actor in historical["actors"].values()}
            origin = snapshot()
            result = self.request("/api/application/start", 202, "POST", fields)
            self.assertNotEqual(result["run_id"], run.name)
            self.assertTrue(all(a["session_ref"] is None for a in result["controller"]["actors"].values()))
            detail = self.terminal(result["run_id"])
            self.assertEqual(detail["controller"]["status"], "completed")
            self.assertTrue(all(a["session_ref"].startswith("opencode:fixture-") for a in detail["controller"]["actors"].values()))
            self.assertTrue(old_sessions.isdisjoint(a["session_ref"] for a in detail["controller"]["actors"].values()))
            self.assertEqual({k: v for k, v in snapshot().items() if k in origin and k.startswith(run.name + "/")},
                             {k: v for k, v in origin.items() if k.startswith(run.name + "/")})

    def test_reuse_setup_rejects_unrepresentable_history_without_guessing(self):
        run, state = harness.start("cognition", "Fixture", self.workspace, self.runs, max_activations=0)
        status = runtime.project(runtime.read_events(run))
        path = run / "options.json"
        options = json.loads(path.read_text())
        setup = application.reuse_setup(run, state, status)
        self.assertIsNone(setup["fields"]["model"])
        self.assertIsNone(setup["fields"]["qa_model"])
        self.assertIsNone(setup["fields"]["verify"])
        self.assertIn("unresolved", " ".join(setup["warnings"]))
        for change in ({"client": "other"}, {"pattern": "generic"}, {"timeout": .5}, {"timeout": 1.5},
                       {"max_returns": 21}, {"max_returns": None}, {"max_remediations": True},
                       {"max_returns": 0}, {"verify": []}, {"thinking": None}, {"model": "line\nbreak"},
                       {"qa_model": ""}, {"unknown": 1}):
            with self.subTest(change=change):
                path.write_text(json.dumps({**options, **change}))
                self.request(f"/api/runs/{run.name}/reuse-setup", 422)
        path.write_text(json.dumps(options))
        source = state["artifacts"][state["slots"]["external.sources"]]
        for content in ([{"ref": "x", "content": "must not drop"}], ["x"], [{"ref": " x"}], [{"ref": "x\ny"}], {"ref": "x"}):
            source["content"] = content
            with self.assertRaisesRegex(application.ApplicationError, "ref-only sources"):
                application.reuse_setup(run, state, status)
        source["content"] = []
        state["slots"]["external.other"] = state["slots"]["external.sources"]
        with self.assertRaisesRegex(application.ApplicationError, "arbitrary or inconsistent"):
            application.reuse_setup(run, state, status)
        del state["slots"]["external.other"]
        state["pattern"]["name"] = "Historical pattern"
        with self.assertRaisesRegex(application.ApplicationError, "historical pattern differs"):
            application.reuse_setup(run, state, status)
        path.unlink()
        self.request(f"/api/runs/{run.name}/reuse-setup", 422)
        legacy = runtime.create_run({"goal": "Legacy fixture"}, self.workspace, self.runs)
        self.request(f"/api/runs/{legacy.name}/reuse-setup", 422)

    def test_reuse_setup_telos_snapshot_is_notice_only(self):
        aggregate = {"chain": {"chainId": "fixture-old-chain", "primaryGoal": "Old governing purpose"},
                     "reproductiveClause": {"essentialPrinciples": ["Fixture old principle"]}}
        with patch.object(telos, "get_goal", return_value=aggregate), patch.object(harness, "_sync_telos"):
            run, state = harness.start("cognition", "Unchanged orienting question", self.workspace, self.runs,
                                       max_activations=0, telos_chain="fixture-old-chain", telos_db=self.db)
        setup = self.request(f"/api/runs/{run.name}/reuse-setup")
        self.assertEqual(setup["source_telos_chain"], "fixture-old-chain")
        self.assertEqual(setup["fields"]["task"], state["purpose"])
        self.assertIsNone(setup["fields"]["telos_chain"])
        self.assertNotIn("Old governing purpose", json.dumps(setup))
        self.assertNotIn("Fixture old principle", json.dumps(setup))


if __name__ == "__main__":
    unittest.main()
