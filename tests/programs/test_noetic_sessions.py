import concurrent.futures
from contextlib import closing, redirect_stdout
import json
import hashlib
import io
import sqlite3
import uuid
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts import noetic_sessions as sessions

FIXTURE = Path(__file__).with_name("fixtures") / "fake_pi_rpc.py"


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="noetic-session-tests-")
        self.home = Path(self.temporary.name)
        self.workspace = self.home / "workspace"
        self.workspace.mkdir()
        subprocess.run(["git", "init", "-q", str(self.workspace)], check=True,
                       env={k: v for k, v in os.environ.items() if k != "USER_PROVIDED_PASSWORD"})
        self.runs = self.home / "runs"
        self.service = sessions.SessionService(self.runs, pi_command=[sys.executable, str(FIXTURE)], namespace_path=self.runs / "ordinals.sqlite3")

    def tearDown(self):
        for item in self.service.list():
            if item["broker_owned"]:
                try:
                    self.service.shutdown(item["id"])
                except sessions.SessionError:
                    pass
        deadline = time.monotonic() + 8
        while any(item["broker_owned"] for item in self.service.list()) and time.monotonic() < deadline:
            time.sleep(.05)
        for item in self.service.list():
            if item["broker_owned"]:
                raise AssertionError("fixture broker did not exit")
            socket_dir = sessions.socket_path(self.runs, item["id"]).parent
            (socket_dir / "control.sock").unlink(missing_ok=True)
            socket_dir.rmdir()
        self.temporary.cleanup()

    def create(self, prompt="hello", **options):
        effort = options.pop("effort_root", None) or self.register_effort(prompt)
        return self.service.create({"workspace": str(self.workspace), "effort_root": effort, "prompt": prompt, **options})

    def wait(self, sid, state="idle"):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            item = self.service.inspect(sid)
            if item["status"] == state:
                return item
            time.sleep(.02)
        self.fail(f"session never reached {state}: {self.service.inspect(sid)}")

    def records(self, sid, direction=None):
        return [event["record"] for event in self.service.registry.events(sid)
                if direction is None or event["direction"] == direction]

    def register_effort(self, intent="A", workspace=None):
        return self.service.create_effort({"intent": intent, "environment": {"cwd": str(workspace or self.workspace)}})["ordinal"]

    def test_effort_position_survives_new_native_conversations_and_exact_binding(self):
        effort = self.register_effort()
        first = self.create(effort_root=effort)
        self.wait(first["id"])
        binding = self.service.bind(first["target"], "prompt", {"message": "old queued"}, effort_root=effort)
        second = self.create(effort_root=effort)
        self.wait(second["id"])
        self.assertEqual(first["ordinal"], second["ordinal"])
        self.assertEqual(first["target"]["instantiation"], second["target"]["instantiation"])
        self.assertNotEqual(first["target"]["session"], second["target"]["session"])
        self.assertNotEqual(first["native_session_id"], second["native_session_id"])
        with self.assertRaisesRegex(sessions.SessionError, "superseded"):
            self.service.deliver(binding["id"], effort_root=effort)
        self.assertEqual(self.service.registry.domain.store().action(binding["id"], scope=sessions.Scope.effort(effort))["target"], first["target"])
        self.assertNotIn("old queued", str(self.records(second["id"])))
        self.assertEqual(self.service.detail(first["target"], effort_root=effort)["session"]["id"], first["id"])
        self.assertEqual(self.service.position("0")["current_instantiation"], None)
        self.assertEqual(len(self.service.branch("0")["records"]), 2)

    def test_module_cli_registration_primary_selectors_history_and_native_start(self):
        common = ["--runs-dir", str(self.runs), "--namespace-path", str(self.runs / "ordinals.sqlite3")]
        def invoke(arguments):
            output = io.StringIO()
            with patch.object(sessions, "SessionService", return_value=self.service), redirect_stdout(output):
                self.assertEqual(sessions.main([*common, *arguments]), 0)
            return json.loads(output.getvalue())
        effort = invoke(["register-effort", "--workspace", str(self.workspace), "--intent", "CLI A"])["ordinal"]
        item = invoke(["start", "--effort-root", effort, "CLI native work"])
        self.wait(item["id"])
        target = item["target"]
        exact = ["--effort-root", effort, "--instantiation", str(target["instantiation"]), "--session", str(target["session"])]
        selected = invoke(["show", item["ordinal"], *exact])
        self.assertEqual(selected["session"]["id"], item["id"])
        sent = invoke(["prompt", item["ordinal"], "CLI exact followup", *exact])
        self.assertEqual(sent["target"], target)
        self.assertTrue(invoke(["history", effort, "--effort-root", effort])["records"])
        self.assertEqual(invoke(["position", "0"])["ordinal"], "0")
        self.assertEqual(invoke(["list", "--effort-root", effort])[0]["target"], target)
        self.assertTrue(invoke(["shutdown", item["ordinal"], *exact])["shutdown_requested"])
        self.wait(item["id"], "closed")

    def test_namespace_configuration_is_independent_of_agent_cwd_and_explicit_path_wins(self):
        configured = self.home / "configured-app"
        with patch.dict(os.environ, {"NOETIC_APP_HOME": str(configured)}):
            service = sessions.SessionService(self.home / "other-source-runs")
            self.assertEqual(service.registry.domain.path, configured / "state" / "ordinals.sqlite3")
            self.assertFalse(configured.exists())
            isolated = sessions.SessionService(self.runs, namespace_path=self.home / "explicit" / "ordinals.sqlite3")
            effort = isolated.create_effort({"intent": "isolated", "environment": {"cwd": str(self.workspace)}})
            self.assertEqual(effort["ordinal"], "0.0")
            self.assertFalse(configured.exists())
            self.assertIsNone(isolated.position("0")["current_instantiation"])

    def test_native_handshake_rejects_missing_context_before_mapping_or_prompt(self):
        fixture_source = FIXTURE.read_text()
        for index, reference in enumerate(("None", "''", "123", "'relative.jsonl'")):
            with self.subTest(reference=reference):
                fixture = self.home / f"missing-context-{index}.py"
                fixture.write_text(fixture_source.replace('"sessionFile": str(path)', f'"sessionFile": {reference}'))
                self.service.pi_command = [sys.executable, str(fixture)]
                effort = self.register_effort(f"missing planned context {index}")
                with self.assertRaises(sessions.SessionError):
                    self.create(effort_root=effort)
                item = next(row for row in self.service.list() if row["effort_root"] == effort)
                self.assertEqual(item["status"], "failed")
                self.assertIsNone(item["target"])
                self.assertIsNone(item["native_session_file"])
                self.assertFalse(item["broker_owned"])
                self.assertTrue(item["process"]["cleanup_confirmed"])
                self.assertFalse(item["can_reopen"])
                self.assertIsNone(self.service.position(effort)["current_instantiation"])
                self.assertFalse(any(r.get("type") == "prompt" for r in self.records(item["id"], "command")))
                self.assertTrue(any(r["kind"] == "native-start-failed" for r in self.service.history(effort, effort_root=effort)["records"]))

    def test_nonexistent_planned_native_context_is_accepted_and_reopens_exactly(self):
        fixture = self.home / "planned-context.py"
        fixture.write_text(FIXTURE.read_text().replace('"sessionFile": str(path)',
            '"sessionFile": str(path), "plannedContextExists": path.exists()'))
        self.service.pi_command = [sys.executable, str(fixture)]
        item = self.create("persist after planned context")
        self.assertFalse(item["runtime"]["plannedContextExists"])
        self.wait(item["id"])
        target, native = item["target"], item["native_session_file"]
        self.assertTrue(Path(native).exists())
        self.service.shutdown(target)
        self.wait(item["id"], "closed")
        deadline = time.monotonic() + 5
        while self.service.inspect(item["id"])["broker_owned"] and time.monotonic() < deadline:
            time.sleep(.05)
        reopened = self.service.reopen(target, effort_root=item["effort_root"])
        self.assertEqual(reopened["target"], target)
        self.assertEqual(reopened["native_session_file"], native)
        self.assertTrue(reopened["runtime"]["plannedContextExists"])
        self.service.prompt(target, "continue original", effort_root=item["effort_root"])
        self.wait(item["id"])
        self.assertEqual([m["content"] for m in json.loads(Path(native).read_text()) if m["role"] == "user"],
                         ["persist after planned context", "continue original"])

    def test_failed_native_start_keeps_reservation_without_invented_context(self):
        effort = self.register_effort("failed launch")
        self.service.pi_command = [str(self.home / "missing-native-client")]
        with self.assertRaises(sessions.SessionError):
            self.create(effort_root=effort)
        failed = self.service.list()[0]
        self.assertEqual(failed["status"], "failed")
        self.assertIsNone(failed["target"])
        self.assertIsNone(failed["native_session_id"])
        self.assertEqual(failed["identity_origin"], "ordinal-reserved")
        self.assertIsNone(self.service.position(effort)["current_instantiation"])
        linked = [r for r in self.service.history("0")["records"] if r["kind"] == "native-start-failed"]
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0]["source_ref"]["session_id"], failed["id"])
        self.assertIsNone(linked[0]["data"]["target"])
        with self.assertRaisesRegex(sessions.SessionError, "No observed native context"):
            self.service.reopen(failed["id"])

    def test_real_succession_retains_queued_original_target_and_closed_context(self):
        effort = self.register_effort()
        first = self.create(effort_root=effort)
        self.wait(first["id"])
        binding = self.service.bind(first["target"], "prompt", {"message": "queued predecessor"}, effort_root=effort)
        successor = self.create(effort_root=effort, succession={"predecessor": first["target"]["instantiation"],
                               "handoff": {"responsibility": "continue A", "context": "new native conversation"}})
        self.wait(successor["id"])
        self.assertEqual(successor["ordinal"], first["ordinal"])
        self.assertEqual(successor["target"]["instantiation"], 2)
        with self.assertRaises(sessions.SessionError):
            self.service.deliver(binding["id"], effort_root=effort)
        with self.assertRaisesRegex(sessions.SessionError, "superseded"):
            self.service.reopen(first["target"], effort_root=effort)
        instance = self.service.registry.domain.store().instantiations(effort)[1]
        self.assertEqual(instance["predecessor"], 1)
        self.assertEqual(instance["handoff"]["context"], "new native conversation")
        self.assertNotIn("queued predecessor", str(self.records(successor["id"])))
        self.assertTrue(Path(first["native_session_file"]).exists())

    def test_explicit_legacy_adoption_is_idempotent_preserves_original_sources_and_parentage(self):
        registry = self.service.registry
        registry.initialize()
        before_records, native_hashes, ids = {}, {}, []
        root_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        for index, sid in enumerate([*root_ids, str(uuid.uuid4())]):
            ids.append(sid)
            native = self.home / (sid + ".jsonl")
            native.write_text(json.dumps({"original-session": sid, "messages": ["preserve original"]}))
            native_hashes[str(native)] = hashlib.sha256(native.read_bytes()).hexdigest()
            parent = root_ids[0] if index == 2 else None
            root = root_ids[0] if index == 2 else sid
            label = "0.1" if parent else "0"
            with closing(sqlite3.connect(registry.path)) as db, db:
                db.execute("INSERT INTO sessions(id,root_id,parent_id,ordinal,workspace,title,model,thinking,command,status,native_session_file,native_session_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (sid, root, parent, label, str(self.workspace), "legacy", sessions.DEFAULT_MODEL, "high", json.dumps([sys.executable,str(FIXTURE)]), "closed", str(native), sid, sessions.now(),sessions.now()))
            for number in range(7):
                registry.event(sid, "event", {"type": "original", "number": number})
            before_records[sid] = registry.events(sid)
        a, b = self.register_effort("A"), self.register_effort("B")
        domain = registry.domain.store()
        child = domain.delegate(a, scope=sessions.Scope.effort(a), mandate={"purpose": "adopt actual historical child"},
            origin="human", human_ref={"origin": "fixture-owner"}, source_ref={"fixture": "legacy-adoption"})["ordinal"]
        for sid, effort, ordinal in [(ids[0],a,a), (ids[1],b,b), (ids[2],a,child)]:
            body = {"session_id": sid, "effort_root": effort, "ordinal": ordinal}
            adopted = self.service.adopt_legacy(body)
            again = self.service.adopt_legacy(body)
            self.assertEqual(adopted["mapping"], again["mapping"])
            self.assertEqual(adopted["mapping"]["original_parent"], "0" if sid == ids[2] else None)
            self.assertEqual(adopted["session"]["original_ordinal"], "0.1" if sid == ids[2] else "0")
            after_records = registry.events(sid)
            self.assertEqual([{k:v for k,v in r.items() if k != "correlated"} for r in before_records[sid]],
                             [{k:v for k,v in r.items() if k != "correlated"} for r in after_records])
            traversed, after = [], 0
            while True:
                page = self.service.detail(adopted["session"]["target"], after, limit=2)
                if not page["events"]:
                    break
                traversed.extend(page["events"]); after=page["next_after"]
            self.assertEqual(len(traversed), 7)
        self.assertEqual(len(domain.legacy_mappings()), 3)
        self.assertEqual({p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in native_hashes}, native_hashes)
        adoptions = [r for r in self.service.history("0", limit=1000)["records"] if r["kind"] == "legacy-adopted"]
        self.assertTrue(all(r["data"]["historical_delegation"] is False for r in adoptions))
        self.assertEqual(len({r["data"]["namespace"] for r in adoptions}), 2)

    def test_cross_effort_rejection_and_literal_global_root(self):
        a = self.create(effort_root=self.register_effort("A"))
        b = self.create(effort_root=self.register_effort("B"))
        r = self.register_effort("R")
        with self.assertRaises(sessions.SessionError):
            self.service.prompt(b["ordinal"], "wrong scope", effort_root=a["effort_root"])
        with self.assertRaisesRegex(sessions.SessionError, "instantiation"):
            self.service.prompt("0", "no fabricated provider")
        self.assertEqual(self.service.position(r)["intent"], "R")
        child = sessions.control(self.runs, a["id"], {"action": "delegate", "prompt": "actual child", "thinking": "low"})
        mandate = self.service.registry.domain.store().mandates(child["ordinal"])[0]
        self.assertEqual(mandate["origin"], "agent")
        self.assertEqual(mandate["delegator"], a["target"])
        self.assertEqual(child["workspace"], a["workspace"])
        native_start = next(r for r in self.records(child["id"]) if r.get("type") == "pi_started")
        self.assertEqual(str((Path("/proc") / str(native_start["pid"]) / "cwd").resolve()), a["workspace"])
        self.assertEqual(child["parentTarget"], a["target"])
        self.assertEqual(child["effort_root"], a["effort_root"])
        with self.assertRaises(sessions.SessionError):
            sessions.control(self.runs, a["id"], {"action": "read", "target": b["ordinal"]})
        pages, after = [], 0
        while True:
            page = self.service.history("0", after=after, limit=2)
            if not page["records"]:
                break
            pages.extend(page["records"]); after = page["next_after"]
        self.assertTrue(any(row["kind"] == "native-event" and row["source_ref"].get("sequence") for row in pages))

    def test_real_process_streaming_followup_and_gui_reconnect_preserve_context(self):
        item = self.create("slow root")
        self.assertEqual(item["ordinal"], "0.0")
        self.assertIsNone(item["parent_id"])
        self.assertNotEqual(item["id"], item["ordinal"])
        self.assertTrue(item["broker_owned"])
        with self.assertRaisesRegex(sessions.SessionError, "streamingBehavior"):
            self.service.prompt(item["id"], "bad concurrent plain prompt")
        self.service.prompt(item["id"], "steering text", "steer")
        self.service.prompt(item["id"], "following text", "follow_up")
        restarted_server = sessions.SessionService(self.runs, namespace_path=self.runs / "ordinals.sqlite3")
        self.assertTrue(restarted_server.inspect(item["id"])["broker_owned"])
        self.wait(item["id"])
        messages = [record["message"] for record in self.records(item["id"])
                    if record.get("type") == "message_end"]
        self.assertEqual([m["content"] for m in messages if m["role"] == "user"],
                         ["slow root", "steering text", "following text"])
        deltas = [record["assistantMessageEvent"]["delta"] for record in self.records(item["id"])
                  if record.get("type") == "message_update"]
        self.assertTrue(all(delta == "real\u2028fixture\u2029delta" for delta in deltas))
        self.assertEqual(self.records(item["id"])[-1]["type"], "agent_settled")
        self.assertEqual(restarted_server.detail(item["id"])["session"]["native_session_id"], item["id"])

    def test_stop_clears_queue_before_abort_and_does_not_run_queued_work(self):
        item = self.create("slow root")
        self.service.prompt(item["id"], "must not run", "follow_up")
        stopped = self.service.stop(item["id"])
        self.assertTrue(stopped["stopped"])
        self.assertEqual(stopped["queue_cleared"]["followUp"], ["must not run"])
        commands = self.records(item["id"], "command")
        kinds = [record["type"] for record in commands]
        index = kinds.index("clear_queue")
        self.assertEqual(kinds[index:index+3], ["clear_queue", "abort", "get_state"])
        time.sleep(.1)
        messages = [record["message"]["content"] for record in self.records(item["id"])
                    if record.get("type") == "message_end" and record["message"]["role"] == "user"]
        self.assertEqual(messages, ["slow root"])
        self.service.prompt(item["id"], "new explicit work")
        self.wait(item["id"])

    def test_rooted_delegation_messages_and_monotonic_concurrent_ordinals(self):
        root = self.create()
        self.wait(root["id"])
        child = sessions.control(self.runs, root["id"], {"action": "delegate", "prompt": "child task", "thinking": "low"})
        self.assertEqual(child["ordinal"], "0.0.0")
        self.assertEqual(child["parent_id"], root["id"])
        self.assertEqual(child["model"], root["model"])
        self.assertEqual(child["thinking"], "low")
        grandchild = sessions.control(self.runs, child["id"], {"action": "delegate", "prompt": "nested task", "thinking": "high"})
        self.assertEqual(grandchild["ordinal"], "0.0.0.0")
        result = sessions.control(self.runs, root["id"], {"action": "wait", "target": "0.0.0", "timeout": 5})
        self.assertEqual(result["session"]["status"], "idle")
        sessions.control(self.runs, child["id"], {"action": "message", "target": "parent", "message": "child outcome", "mode": "follow_up"})
        self.wait(root["id"])
        self.assertTrue(any(r.get("type") == "message_end" and r["message"].get("customType") == "noetic-agent-message" and r["message"].get("details", {}).get("message") == "child outcome" for r in self.records(root["id"])))
        other = self.create("other root")
        self.assertEqual(other["ordinal"], "0.1")
        with self.assertRaisesRegex(sessions.SessionError, "does not own"):
            sessions.control(self.runs, root["id"], {"action": "read", "target": other["id"]})
        def reserve(index):
            return self.service.create({"prompt": str(index), "thinking": "low"}, parent_id=root["id"])
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            children = list(pool.map(reserve, range(4)))
        self.assertEqual({item["ordinal"] for item in children}, {"0.0.1", "0.0.2", "0.0.3", "0.0.4"})
        self.assertEqual(len({item["id"] for item in children}), 4)

    def test_explicit_reopen_after_shutdown_retains_native_context_and_identity(self):
        item = self.create("first context")
        self.wait(item["id"])
        native = item["native_session_file"]
        self.service.shutdown(item["id"])
        self.wait(item["id"], "closed")
        deadline = time.monotonic() + 5
        while self.service.inspect(item["id"])["broker_owned"] and time.monotonic() < deadline:
            time.sleep(.05)
        reopened = self.service.reopen(item["id"])
        self.assertEqual(reopened["id"], item["id"])
        self.assertEqual(reopened["native_session_file"], native)
        self.service.prompt(item["id"], "second context")
        self.wait(item["id"])
        messages = json.loads(Path(native).read_text())
        self.assertEqual([m["content"] for m in messages if m["role"] == "user"], ["first context", "second context"])

    def test_broker_restart_never_automatically_restarts_agent_and_reused_pid_refused(self):
        item = self.create("slow root")
        os.kill(item["process"]["identity"]["pid"], signal.SIGKILL)
        deadline = time.monotonic() + 5
        while self.service.inspect(item["id"])["broker_owned"] and time.monotonic() < deadline:
            time.sleep(.05)
        interrupted = self.service.inspect(item["id"])
        self.assertEqual(interrupted["status"], "interrupted")
        self.assertFalse(interrupted["broker_owned"])
        before = self.records(item["id"])
        self.assertEqual(self.service.detail(item["id"])["session"]["status"], "interrupted")
        self.assertEqual(self.records(item["id"]), before)
        with patch.object(sessions.processes, "inspect", return_value={"state": "mismatched", "cleanup_confirmed": False}):
            with self.assertRaisesRegex(sessions.SessionError, "cleanup is unconfirmed"):
                self.service.reopen(item["id"])

    def test_actual_extension_dialog_drives_needs_input_and_response(self):
        item = self.create("dialog")
        self.wait(item["id"], "needs_input")
        state = sessions.control(self.runs, item["id"], {"action": "state"})
        self.assertEqual(state["dialogs"][0]["id"], "dialog-1")
        with self.assertRaisesRegex(sessions.SessionError, "boolean"):
            sessions.control(self.runs, item["id"], {"action": "dialog", "id": "dialog-1", "confirmed": "yes"})
        sessions.control(self.runs, item["id"], {"action": "dialog", "id": "dialog-1", "confirmed": True})
        self.wait(item["id"])
        with self.assertRaisesRegex(sessions.SessionError, "no longer pending"):
            sessions.control(self.runs, item["id"], {"action": "dialog", "id": "dialog-1", "confirmed": True})

    def test_failed_prompt_status_error_and_development_credential_exclusion(self):
        with patch.dict(os.environ, {"USER_PROVIDED_PASSWORD": "public-test-sentinel"}):
            item = self.create()
        self.wait(item["id"])
        with self.assertRaisesRegex(sessions.SessionError, "fixture rejected"):
            self.service.prompt(item["id"], "reject")
        self.assertEqual(self.service.inspect(item["id"])["status"], "idle")
        self.assertNotIn("public-test-sentinel", json.dumps(self.records(item["id"])))
        self.assertNotIn("public-test-sentinel", (self.service.registry.directory(item["id"]) / "broker.log").read_text())

    def test_managed_extension_executes_real_delegation_and_read_tools(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node not installed")
        root = self.create("root extension")
        self.wait(root["id"])
        environment = {key: value for key, value in os.environ.items() if key != "USER_PROVIDED_PASSWORD"}
        environment["NOETIC_SESSION_SOCKET"] = str(sessions.socket_path(self.runs, root["id"]))
        environment["NOETIC_SESSION_ORDINAL"] = root["ordinal"]
        script = """
            const {default: extension} = await import(process.argv[1]);
            const tools = new Map();
            extension({registerTool: tool => tools.set(tool.name, tool), registerCommand(){}, on(){}});
            if (tools.size !== 4) throw new Error('expected four coordination tools');
            const delegated = await tools.get('agent_delegate').execute('test', {prompt:'tool delegated task', thinking:'low'});
            const child = delegated.details;
            const completed = await tools.get('agent_wait').execute('test', {target:child.target, timeout:5});
            const tree = await tools.get('agent_read').execute('test', {});
            const sent = await tools.get('agent_send').execute('test', {target:child.ordinal, message:'tool followup', mode:'follow_up'});
            console.log(JSON.stringify({child, status:completed.details.session.status, tree:tree.details, sent:sent.details}));
        """
        output = subprocess.run([node, "--input-type=module", "-e", script, sessions.EXTENSION.as_uri()],
                                env=environment, capture_output=True, timeout=15, check=True)
        result = json.loads(output.stdout)
        self.assertEqual(result["child"]["ordinal"], "0.0.0")
        self.assertEqual(result["child"]["parent_id"], root["id"])
        self.assertEqual(result["status"], "idle")
        self.assertTrue(result["sent"]["accepted"])
        self.assertEqual(len(result["tree"]), 2)

    def test_private_files_and_short_socket_for_long_runs_root(self):
        long_root = self.home / ("a" * 100) / ("b" * 100)
        registry = sessions.Registry(long_root, namespace_path=long_root / "ordinals.sqlite3")
        effort = registry.domain.create({"intent": "short socket", "environment": {"cwd": str(self.workspace)}})
        item = registry.create(self.workspace, "short socket", sessions.DEFAULT_MODEL, "high", ["pi"], ordinal=effort["ordinal"], effort_root=effort["ordinal"])
        self.assertLess(len(str(sessions.socket_path(long_root, item["id"])).encode()), 108)
        self.assertEqual(registry.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(registry.directory(item["id"]).stat().st_mode & 0o777, 0o700)
        sessions.socket_path(long_root, item["id"]).parent.rmdir()


class InstalledPiTests(unittest.TestCase):
    def test_offline_installed_pi_rpc_state_extension_load_and_shutdown_without_prompt(self):
        executable = shutil.which("pi")
        if not executable:
            self.skipTest("Pi not installed")
        with tempfile.TemporaryDirectory(prefix="noetic-pi-offline-") as directory:
            environment = {key: value for key, value in os.environ.items() if key != "USER_PROVIDED_PASSWORD"}
            environment["NOETIC_SESSION_SOCKET"] = str(Path(directory) / "unused.sock")
            environment["NOETIC_SESSION_ORDINAL"] = "0"
            commands = [{"id": "state", "type": "get_state"}, {"id": "commands", "type": "get_commands"}]
            child = subprocess.run([executable, "--offline", "--mode", "rpc", "--no-session", "--no-approve",
                                    "--model", sessions.DEFAULT_MODEL, "--thinking", "high", "--no-extensions", "-e", str(sessions.EXTENSION)],
                                   cwd=directory, env=environment, input=b"".join(json.dumps(c).encode()+b"\n" for c in commands),
                                   capture_output=True, timeout=30)
            self.assertEqual(child.returncode, 0, child.stderr.decode())
            records = [json.loads(line) for line in child.stdout.split(b"\n") if line]
            responses = {r["id"]: r for r in records if r.get("type") == "response"}
            self.assertTrue(responses["state"]["success"])
            self.assertFalse(responses["state"]["data"]["isStreaming"])
            self.assertEqual(responses["state"]["data"]["model"]["id"], "gpt-6.1-sol")
            self.assertIn("noetic-agents", [c["name"] for c in responses["commands"]["data"]["commands"]])
            self.assertFalse(any(r.get("type") == "agent_start" for r in records))


if __name__ == "__main__":
    unittest.main()
