"""Host bridge fixtures; native launch/prompt/process boundaries are mocked."""
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

from scripts import noetic_sessions as sessions
from scripts.noetic_efforts import Scope, Target


class ActorBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="noetic-actor-bridge-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.service = sessions.SessionService(self.home / "runs", namespace_path=self.home / "namespace.sqlite3", pi_command=["/bin/false"])
        self.root = self.service.create_effort({"intent": "Bridge fixture", "environment": {"cwd": str(self.home)}})["ordinal"]
        self.store = self.service.registry.domain.store()
        self.scope = Scope.effort(self.root)
        position = self.store.delegate(self.root, scope=self.scope, mandate={"purpose": "Implementation"}, origin="human", human_ref={"fixture": "controller"}, source_ref={"fixture": True})
        self.ordinal = position["ordinal"]
        self.owner = {"run_id": "fixture-run", "activation_id": "fixture-activation", "namespace": self.store.namespace}
        self.native = {"client": "pi", "session_id": str(uuid.uuid4()), "context_file": str(self.home / "parent.jsonl"), "execution_workspace": str(self.home)}
        Path(self.native["context_file"]).write_text(json.dumps({"type": "session", "id": self.native["session_id"], "cwd": str(self.home)}) + "\n")
        instance = self.store.instantiate(self.ordinal, scope=self.scope, native_ref={**self.native, **self.owner}, source_ref={"fixture": True})
        self.parent = self.store.open_session(self.ordinal, instance["sequence"], scope=self.scope, native_ref=self.native, source_ref={"fixture": True}).as_dict()
        self.policy_calls = []
        self.launched = []
        self.prompted = []
        self.launch_patch = patch.object(self.service, "_launch", side_effect=self.launch)
        self.launch_patch.start()
        self.addCleanup(self.launch_patch.stop)
        self.prompt_patch = patch.object(self.service, "prompt", side_effect=lambda address, message, **kw: self.prompted.append((address, message, kw)) or {"accepted": True})
        self.prompt_patch.start()
        self.addCleanup(self.prompt_patch.stop)
        self.process_patch = patch.object(sessions.processes, "inspect", return_value={"state": "owned", "cleanup_confirmed": False})
        self.process_patch.start()
        self.addCleanup(self.process_patch.stop)

    def launch(self, sid):
        self.launched.append(sid)
        path = self.service.registry.directory(sid) / "fixture-native.jsonl"
        path.write_text(json.dumps({"type": "session", "id": sid, "cwd": str(self.home)}) + "\n")
        self.service.registry.update(sid, native_session_id=sid, native_session_file=str(path), status="idle", runtime={"model": {"provider": "fixture", "id": "child"}})
        self.service.registry.attach(sid, {"sessionId": sid, "sessionFile": str(path)})

    def task(self, task_id="first"):
        return {"id": task_id, "prompt": "Implement " + task_id, "title": task_id,
                "mandate": {"purpose": task_id, "ownership": [task_id + ".py"]},
                "source_ref": {"plan_sha256": "a" * 64, "task_id": task_id}}

    def policy(self, request, bridge):
        self.policy_calls.append(request)
        return self.service.create_actor_child(bridge.parent_target, effort_root=self.root, owner=self.owner,
            task=self.task(request["task_id"]), workspace=str(self.home), model="fixture/child", thinking="low")

    def bridge(self, **changes):
        values = dict(effort_root=self.root, owner=self.owner, workspace=str(self.home), model="fixture/parent", thinking="low", policy=self.policy, parent_ordinal=self.ordinal)
        values.update(changes)
        return sessions.ExternalActorBridge(self.service, **values)

    def bound(self):
        bridge = self.bridge()
        bridge.__enter__()
        self.addCleanup(bridge.__exit__, None, None, None)
        bridge.bind_parent(self.parent, self.native)
        return bridge

    def request(self, bridge, action, **values):
        return bridge.handle({"action": action, "parentTarget": self.parent, "effort_root": self.root, **values})

    def test_passive_socket_unbound_then_bound_without_second_parent(self):
        before = self.store.position(self.ordinal, scope=self.scope)
        bridge = self.bridge()
        with bridge:
            self.assertTrue(Path(bridge.socket_path).exists())
            self.assertEqual(bridge.environment["NOETIC_SESSION_ORDINAL"], self.ordinal)
            self.assertEqual(bridge.environment["NOETIC_EFFORT_ROOT"], self.root)
            self.assertTrue(bridge.environment["NOETIC_ACTOR_BRIDGE"])
            with self.assertRaises(sessions.SessionError):
                bridge.handle({"action": "identity"})
            bridge.bind_parent(self.parent, self.native)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.connect(str(bridge.socket_path))
                connection.sendall(b'{"action":"identity"}\n')
                response = json.loads(connection.makefile("rb").readline())
            self.assertTrue(response["success"])
            self.assertEqual(response["data"]["target"], self.parent)
            self.assertEqual(bridge.snapshot()["children"], [])
        self.assertFalse(Path(bridge.socket_path).exists())
        self.assertEqual(self.service.registry.list(), [])
        after = self.store.position(self.ordinal, scope=self.scope)
        self.assertEqual(after["current_instantiation"], before["current_instantiation"])
        self.assertEqual(len(self.store.sessions(self.ordinal, 1)), 1)
        self.assertEqual(self.launched, [])

    def test_two_real_canonical_children_and_read_only_marks_inspection(self):
        bridge = self.bound()
        first = self.request(bridge, "delegate", task_id="first")
        second = self.request(bridge, "delegate", task_id="second")
        self.assertEqual(len(self.launched), 2)
        self.assertEqual(len(self.prompted), 2)
        self.assertNotEqual(first["target"], second["target"])
        for child in (first, second):
            self.assertTrue(child["ordinal"].startswith(self.ordinal + "."))
            self.assertEqual(self.store.position(child["ordinal"], scope=self.scope)["mandate"]["delegator"], self.parent)
            self.assertEqual(child["model"], "fixture/child")
            self.assertEqual(child["thinking"], "low")
            self.assertEqual(child["native_session_id"], child["id"])
            self.assertTrue(Path(child["native_session_file"]).exists())
            self.assertIsNone(child["parent_id"])
            binding = self.service.registry.get(child["id"])["actor_binding"]
            self.assertEqual(binding["owner"], self.owner)
            self.assertEqual(binding["parent_target"], self.parent)
            self.assertEqual(binding["task"]["source_ref"]["plan_sha256"], "a" * 64)
        self.assertEqual(bridge.snapshot()["inspected_task_ids"], [])
        result = self.request(bridge, "read", target=first["target"])
        self.assertEqual(result["session"]["target"], first["target"])
        self.assertEqual(bridge.snapshot()["inspected_task_ids"], ["first"])
        self.request(bridge, "wait", target=second["target"], timeout=0)
        snapshot = bridge.snapshot()
        self.assertEqual(set(snapshot["inspected_task_ids"]), {"first", "second"})
        self.assertEqual(snapshot["owner"], self.owner)
        self.assertEqual(snapshot["parent_target"], self.parent)
        self.assertEqual(len(snapshot["children"]), 2)
        self.assertTrue(all(set(row) == {"session", "events", "actor_binding"} for row in snapshot["children"]))
        self.assertNotIn("accepted", snapshot)

    def test_internal_snapshot_pages_lifecycle_while_tool_reads_stay_bounded(self):
        bridge = self.bound()
        child = self.request(bridge, "delegate", task_id="first")
        for number in range(1001):
            self.service.registry.event(child["id"], "event", {"type": "message_update", "fixture_sequence": number})
        finished = self.service.registry.event(child["id"], "event", {
            "type": "message_end", "message": {"role": "assistant", "stopReason": "stop"}})
        settled = self.service.registry.event(child["id"], "event", {"type": "agent_end"})

        first_page = self.request(bridge, "read", target=child["target"])
        self.assertEqual(len(first_page["events"]), 500)
        final_page = self.request(bridge, "read", target=child["target"], after=finished - 1)
        self.assertEqual([event["sequence"] for event in final_page["events"]], [finished, settled])
        overview = self.request(bridge, "overview")
        self.assertEqual(len(overview["children"][0]["events"]), 500)

        snapshot = bridge.snapshot()
        events = snapshot["children"][0]["events"]
        self.assertEqual([event["sequence"] for event in events[-2:]], [finished, settled])
        self.assertGreater(len(events), 1000)
        self.assertEqual(snapshot["inspected_task_ids"], ["first"])

        resumed = self.service.registry.event(child["id"], "event", {"type": "agent_start"})
        self.service.registry.update(child["id"], status="running")
        later = bridge.snapshot()["children"][0]
        self.assertEqual(later["events"][-1]["sequence"], resumed)
        self.assertEqual(later["session"]["status"], "running")

    def test_binding_survives_runtime_replacement_and_refuses_child_subdelegation(self):
        bridge = self.bound()
        child = self.request(bridge, "delegate", task_id="first")
        binding = self.service.registry.get(child["id"])["actor_binding"]
        self.service.registry.update(child["id"], runtime={"new": "actual get_state"})
        self.assertEqual(self.service.registry.get(child["id"])["actor_binding"], binding)
        with self.assertRaises(sessions.SessionError):
            self.service.create({"prompt": "Unplanned grandchild", "thinking": "low"}, parent_id=child["id"])
        self.assertEqual(len(self.launched), 1)

    def test_invalid_owner_workspace_route_and_task_refuse_before_allocation(self):
        baseline = len(self.service.registry.list())
        for changes in ({"owner": {**self.owner, "run_id": "foreign"}}, {"owner": {**self.owner, "activation_id": "foreign"}},
                        {"owner": {**self.owner, "namespace": "foreign"}}, {"workspace": str(self.home / "missing")},
                        {"model": ""}, {"thinking": "impossible"}, {"task": {**self.task(), "source_ref": {}}}):
            options = dict(effort_root=self.root, owner=self.owner, task=self.task(), workspace=str(self.home), model="fixture/child", thinking="low")
            options.update(changes)
            with self.subTest(changes=changes), self.assertRaises(sessions.SessionError):
                self.service.create_actor_child(self.parent, **options)
            self.assertEqual(len(self.service.registry.list()), baseline)
        self.assertEqual(self.launched, [])

    def test_stale_and_foreign_parent_and_native_ref_refuse_without_policy(self):
        bridge = self.bound()
        with self.assertRaises(sessions.SessionError):
            self.request(bridge, "delegate", task_id="first", parentTarget={**self.parent, "session": 999})
        with self.assertRaises(sessions.SessionError):
            self.request(bridge, "delegate", task_id="first", effort_root="0.999")
        with self.assertRaises(sessions.SessionError):
            bridge.bind_parent(self.parent, {**self.native, "session_id": str(uuid.uuid4())})
        self.store.set_session_status(Target(**self.parent), "closed", scope=self.scope, source_ref={"fixture": True})
        with self.assertRaises(sessions.SessionError):
            self.request(bridge, "delegate", task_id="first")
        self.assertEqual(self.policy_calls, [])
        self.assertEqual(self.launched, [])

    def test_passive_controls_and_missing_task_refuse(self):
        bridge = self.bound()
        for action in ("prompt", "stop", "message", "multicast", "broadcast", "reopen"):
            with self.subTest(action=action), self.assertRaises(sessions.SessionError):
                self.request(bridge, action)
        with self.assertRaises(sessions.SessionError):
            self.request(bridge, "delegate", prompt="unplanned")
        self.assertEqual(self.policy_calls, [])

    def test_foreign_child_is_unreadable_and_generic_parent_guard_remains(self):
        bridge = self.bound()
        foreign = self.service.registry.create(self.home, "Unowned", "fixture/child", "low", [], ordinal=self.root, effort_root=self.root)
        self.launch(foreign["id"])
        for action in ("read", "wait"):
            with self.subTest(action=action), self.assertRaises(sessions.SessionError):
                self.request(bridge, action, target=foreign["id"], timeout=0)
        self.assertEqual(bridge.snapshot()["children"], [])
        with self.assertRaises(sessions.SessionError) as absent:
            self.service.select(self.parent, effort_root=self.root, current=True)
        self.assertIn("registry backing", str(absent.exception))
        owned = self.request(bridge, "delegate", task_id="first")
        read = self.request(bridge, "read", target=owned["target"])
        self.assertTrue(all(item["id"] != foreign["id"] for item in read.get("tree", [])), "owned read must not return an unowned effort tree")

    def test_ordinary_unmarked_session_still_delegates(self):
        ordinary = self.service.registry.create(self.home, "Ordinary", "fixture/child", "low", [], ordinal=self.root, effort_root=self.root)
        self.launch(ordinary["id"])
        with patch.object(self.service, "message", return_value={"accepted": True}):
            child = self.service.create({"prompt": "Ordinary child", "thinking": "low"}, parent_id=ordinary["id"])
        self.assertEqual(child["parent_id"], ordinary["id"])
        self.assertFalse(child.get("actor_binding"))

    def test_manual_start_cannot_claim_controller_reserved_or_observed_position(self):
        discipline = self.store.create_discipline(self.root, scope=self.scope, initiator=self.root,
            definition_ref={"id": "development", "version": "fixture"}, intent="Controller ownership",
            source_ref={"fixture": "lead139"})
        problems = []
        for observed in (False, True):
            reserved = self.store.delegate(self.root, scope=self.scope,
                mandate={"purpose": "Execute controller reserved function", "role": "implementer", "run_id": "fixture-run"},
                origin="human", human_ref={"fixture": "controller"}, discipline_id=discipline["id"],
                source_ref={"fixture": "lead139"})["ordinal"]
            if observed:
                native = {**self.native, "session_id": str(uuid.uuid4())}
                instance = self.store.instantiate(reserved, scope=self.scope, native_ref={**native, **self.owner}, source_ref={"fixture": "lead139"})
                self.store.open_session(reserved, instance["sequence"], scope=self.scope, native_ref=native, source_ref={"fixture": "lead139"})
            before = self.store.resolve_context(reserved, scope=self.scope) if observed else self.store.position(reserved, scope=self.scope)
            rows, launches, prompts = len(self.service.registry.list()), len(self.launched), len(self.prompted)
            try:
                self.service.create({"effort_root": self.root, "ordinal": reserved, "prompt": "Valid manual start", "model": "fixture/child", "thinking": "low"})
            except sessions.SessionError as exc:
                if exc.status != 409 or not any(word in str(exc).lower() for word in ("controller", "reserved", "controlled")):
                    problems.append((observed, "inaccurate admission feedback", str(exc)))
            else:
                problems.append((observed, "manual Start was admitted"))
            after = self.store.resolve_context(reserved, scope=self.scope) if observed else self.store.position(reserved, scope=self.scope)
            if (len(self.service.registry.list()), len(self.launched), len(self.prompted)) != (rows, launches, prompts):
                problems.append((observed, "registry or native boundary effects"))
            if before != after:
                problems.append((observed, "canonical parent correspondence changed"))
        self.assertEqual(problems, [], "valid manual Start must refuse before row, launch, prompt or parent correspondence effects")

    def test_reserved_ordinal_binding_cannot_be_replaced_by_another_owned_target(self):
        bridge = self.bridge(parent_ordinal=self.root)
        with bridge, self.assertRaises(sessions.SessionError):
            bridge.bind_parent(self.parent, self.native)
        self.assertEqual(self.launched, [])

    def test_external_parent_identity_contract_is_independent_of_adapter_client(self):
        ordinal = self.store.delegate(self.root, scope=self.scope, mandate={"purpose": "Other adapter fixture"},
            origin="human", human_ref={"fixture": "controller"}, source_ref={"fixture": True})["ordinal"]
        native = {**self.native, "client": "fixture-external-adapter", "session_id": str(uuid.uuid4())}
        instance = self.store.instantiate(ordinal, scope=self.scope, native_ref={**native, **self.owner}, source_ref={"fixture": True})
        target = self.store.open_session(ordinal, instance["sequence"], scope=self.scope, native_ref=native, source_ref={"fixture": True}).as_dict()
        with self.bridge(parent_ordinal=ordinal) as bridge:
            bridge.bind_parent(target, native)
            self.assertEqual(bridge.handle({"action": "identity"})["target"], target)
        self.assertEqual(self.launched, [])

    def test_failed_socket_read_delivery_does_not_mark_task_inspected(self):
        bridge = self.bound()
        child = self.request(bridge, "delegate", task_id="first")
        request = {"action": "read", "target": child["target"], "parentTarget": self.parent, "effort_root": self.root}
        with patch.object(sessions.socketserver._SocketWriter, "write", side_effect=BrokenPipeError("fixture delivery failure")):
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.connect(str(bridge.socket_path))
                connection.sendall(json.dumps(request).encode() + b"\n")
                self.assertEqual(connection.makefile("rb").readline(), b"")
        self.assertEqual(bridge.snapshot()["inspected_task_ids"], [], "an undelivered read response is not parent inspection")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.connect(str(bridge.socket_path))
            connection.sendall(json.dumps(request).encode() + b"\n")
            self.assertTrue(json.loads(connection.makefile("rb").readline())["success"])
        deadline = time.monotonic() + 1
        while not bridge.snapshot()["inspected_task_ids"] and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertEqual(bridge.snapshot()["inspected_task_ids"], ["first"])

    def test_unspecified_parent_route_binds_actual_observed_default_without_substitute(self):
        for observed_model in (None, {"provider": "fixture", "id": "actual-default"}):
            with self.subTest(observed_model=observed_model):
                ordinal = self.store.delegate(self.root, scope=self.scope, mandate={"purpose": "Default model fixture"},
                    origin="human", human_ref={"fixture": "controller"}, source_ref={"fixture": True})["ordinal"]
                native = {**self.native, "session_id": str(uuid.uuid4()), "startup_state": {"model": observed_model}}
                instance = self.store.instantiate(ordinal, scope=self.scope, native_ref={**native, **self.owner}, source_ref={"fixture": True})
                target = self.store.open_session(ordinal, instance["sequence"], scope=self.scope, native_ref=native, source_ref={"fixture": True}).as_dict()
                with self.bridge(parent_ordinal=ordinal, model=None) as bridge:
                    if observed_model is None:
                        with self.assertRaises(sessions.SessionError):
                            bridge.bind_parent(target, native)
                        self.assertIsNone(bridge.parent_target)
                    else:
                        bridge.bind_parent(target, native)
                        self.assertEqual(bridge.model, "fixture/actual-default")
                self.assertEqual(self.launched, [])


class ActorBridgeExtensionTests(unittest.TestCase):
    def test_planned_tools_are_bounded_and_ordinary_schema_unchanged(self):
        extension = Path(sessions.EXTENSION).resolve().as_uri()
        code = """
import extension from %s;
function load(planned) {
  process.env.NOETIC_SESSION_SOCKET = '/fixture/not-connected';
  if (planned) process.env.NOETIC_ACTOR_BRIDGE = '1'; else delete process.env.NOETIC_ACTOR_BRIDGE;
  const tools = new Map();
  extension({registerTool:t=>tools.set(t.name,t), registerCommand:()=>{}, on:()=>{}});
  return tools;
}
const planned = load(true), ordinary = load(false);
const plannedSchema = planned.get('agent_delegate').parameters;
if (plannedSchema.required.some(key => !Object.hasOwn(plannedSchema.properties, key))) throw Error('required planned task_id is forbidden by closed properties schema');
if (JSON.stringify([...planned.keys()].sort()) !== JSON.stringify(['agent_delegate','agent_read','agent_wait'])) throw Error('planned tools exceed capability');
if (JSON.stringify(planned.get('agent_delegate').parameters.required) !== JSON.stringify(['task_id'])) throw Error('planned task schema');
if (JSON.stringify(ordinary.get('agent_delegate').parameters.required) !== JSON.stringify(['prompt','thinking'])) throw Error('ordinary schema changed');
if (!ordinary.has('agent_send') || !ordinary.has('agent_multicast_send') || !ordinary.has('agent_broadcast_send')) throw Error('ordinary tools lost');
""" % json.dumps(extension)
        result = subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
