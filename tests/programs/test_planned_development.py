"""Helper controls and a disposable canonical/controller/RPC protocol journey.

Actor launch and provider responses are fixtures; historical state is untouched.
"""
import copy, hashlib, json, os, sqlite3, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import noetic_harness as h

PLAN = {
    "version": 1, "max_dispatches": 2,
    "tasks": [
        {"id": "alpha", "responsibility": "Implement alpha module", "prompt": "Implement alpha only.",
         "outputs": ["alpha.py"], "ownership": ["alpha.py"],
         "checks": [["python3", "-c", "print('alpha ok')"]], "dependencies": [],
         "model": "inherit", "thinking": "inherit", "max_dispatches": 1},
        {"id": "beta", "responsibility": "Integrate beta runner", "prompt": "Integrate using alpha outputs.",
         "outputs": ["beta.py"], "ownership": ["beta.py"],
         "checks": [["python3", "-c", "print('beta ok')"]], "dependencies": ["alpha"],
         "model": "inherit", "thinking": "inherit", "max_dispatches": 1},
    ],
}
OPTIONS = {"client": "pi", "model": "openai-codex/gpt-6.1-sol", "thinking": "high", "qa_model": None,
           "pattern": "development", "delegation_version": 1,
           "scope": {"effort_root": "0.900", "namespace": "fixture-namespace"}}
OWNER = {"run_id": "maintained-run", "activation_id": "activation-1", "namespace": "fixture-namespace"}
TARGET = {"ordinal": "0.900.4", "instantiation": 1, "session": 1}


class Bridge:
    def __init__(self, root):
        self.parent_target = dict(TARGET)
        self.owner = dict(OWNER)
        self.workspace = str(root)
        self.model = OPTIONS["model"]
        self.thinking = "high"
        self.children, self.reads, self.calls = [], [], []
        self.service = self

    def create_actor_child(self, parent_target, **kw):
        self.calls.append(dict(kw))
        task = kw["task"]
        target = {"ordinal": f"0.900.4.{len(self.children)}", "instantiation": 1, "session": 1}
        binding = {"owner": self.owner, "parent_target": dict(TARGET), "task": copy.deepcopy(task)}
        session = {"id": f"child-{len(self.children)}", "target": target, "status": "running",
                   "model": kw["model"], "thinking": kw["thinking"], "actor_binding": binding}
        self.children.append({"session": session, "events": [], "actor_binding": binding})
        return copy.deepcopy(session)

    def snapshot(self):
        return copy.deepcopy({"owner": self.owner, "parent_target": self.parent_target,
                              "children": self.children, "inspected_task_ids": self.reads})

    def finish(self, task_id):
        child = next(c for c in self.children if c["actor_binding"]["task"]["id"] == task_id)
        child["session"]["status"] = "idle"
        child["events"] = [
            {"sequence": 1, "direction": "event",
             "record": {"type": "message_end", "message": {"role": "assistant", "stopReason": "stop",
                                                           "content": [{"type": "text", "text": "done"}]}}},
            {"sequence": 2, "direction": "event", "record": {"type": "agent_end"}},
            {"sequence": 3, "direction": "event", "record": {"type": "agent_settled"}}]

    def inspect(self, task_id):
        self.reads.append(task_id)


class PlannedDevelopmentTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        self.setUpJournal()

    def setUpJournal(self):
        database = sqlite3.connect(self.root / "events.sqlite3")
        database.execute("CREATE TABLE events (sequence INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL, "
                         "kind TEXT NOT NULL, data TEXT NOT NULL)")
        database.close()

    def policy(self, plan=PLAN, options=OPTIONS):
        return h.DelegationPolicy(self.root, owner=dict(OWNER), parent_ordinal=TARGET["ordinal"],
                                  plan=copy.deepcopy(plan), options=copy.deepcopy(options),
                                  workspace=str(self.root))

    def dispatch(self, policy, bridge, task_id, **extra):
        return policy({"action": "delegate", "task_id": task_id, "parentTarget": dict(TARGET),
                       "effort_root": "0.900", **extra}, bridge)

    def test_plan_validation_positive_and_refusals(self):
        validated = h.validate_delegation_plan(copy.deepcopy(PLAN), OPTIONS)
        self.assertEqual(validated, PLAN)
        for change in ({}, {"steps": ["serial only"]}, {"max_dispatches": 0}):
            with self.assertRaises(ValueError):
                h.validate_delegation_plan(change, OPTIONS)
        for change in ("duplicate", "overlap", "cycle", "unknown_dependency", "empty_model",
                       "bad_thinking", "task_budget"):
            plan = copy.deepcopy(PLAN)
            if change == "duplicate":
                plan["tasks"][1]["id"] = "alpha"
            if change == "overlap":
                plan["tasks"][1]["ownership"] = ["alpha.py"]
            if change == "cycle":
                plan["tasks"][0]["dependencies"] = ["beta"]
            if change == "unknown_dependency":
                plan["tasks"][0]["dependencies"] = ["ghost"]
            if change == "empty_model":
                plan["tasks"][0]["model"] = ""
            if change == "bad_thinking":
                plan["tasks"][0]["thinking"] = "invented"
            if change == "task_budget":
                plan["tasks"][0]["max_dispatches"] = 0
            with self.assertRaises(ValueError):
                h.validate_delegation_plan(plan, OPTIONS)
        with self.assertRaises(ValueError):
            h.validate_delegation_plan(PLAN, {**OPTIONS, "client": "opencode"})

    def test_positive_dependency_idempotency_and_gate_receipt(self):
        bridge, policy = Bridge(self.root), self.policy()
        alpha = self.dispatch(policy, bridge, "alpha")
        self.assertEqual(alpha["target"]["ordinal"], "0.900.4.0")
        self.assertEqual(bridge.calls[0]["model"], OPTIONS["model"])
        self.assertTrue(bridge.calls[0]["task"]["source_ref"]["plan_sha256"])
        self.assertIn("ownership", bridge.calls[0]["task"]["mandate"])
        self.assertEqual(self.dispatch(policy, bridge, "alpha")["id"], alpha["id"])
        self.assertEqual(len(bridge.calls), 1)
        with self.assertRaises(ValueError):
            self.dispatch(policy, bridge, "beta")
        bridge.finish("alpha")
        with self.assertRaises(ValueError):
            self.dispatch(policy, bridge, "beta")
        bridge.inspect("alpha")
        beta = self.dispatch(policy, bridge, "beta")
        self.assertEqual(len(bridge.calls), 2)
        bridge.finish("beta")
        bridge.inspect("beta")
        result = {"outcome": "produced", "content": {
            "report": "incorporated", "changes": [], "verification": [],
            "delegation_results": [{"task_id": "alpha", "target": alpha["target"]},
                                   {"task_id": "beta", "target": beta["target"]}]}}
        receipt = policy.complete(bridge, result)
        self.assertEqual(receipt["plan_sha256"], hashlib.sha256(
            json.dumps(PLAN, sort_keys=True).encode()).hexdigest())
        self.assertEqual(result["content"]["delegation_receipt"], receipt)
        continuation = self.policy()
        self.assertEqual(self.dispatch(continuation, bridge, "alpha")["id"], alpha["id"])
        self.assertEqual(len(bridge.calls), 2)

    def test_unknown_changed_partial_and_check_refusals(self):
        bridge, policy = Bridge(self.root), self.policy()
        attempted = []

        def uncertain(*args, **kwargs):
            attempted.append(kwargs)
            raise TimeoutError("delegation effects unknown")

        bridge.create_actor_child = uncertain
        with self.assertRaises(TimeoutError):
            self.dispatch(policy, bridge, "alpha")
        self.assertEqual(self.policy()._state.get("alpha", {}).get("status"), "unknown")
        with self.assertRaises(ValueError):
            self.dispatch(self.policy(), bridge, "alpha")
        self.assertEqual(bridge.calls, [])
        plan = copy.deepcopy(PLAN)
        plan["tasks"][0]["prompt"] = "changed"
        with self.assertRaises(ValueError):
            self.policy(plan)
        self.assertEqual(len(attempted), 1)

        isolated = Path(self._temporary.name) / "partial-case"
        isolated.mkdir()
        self.root = isolated
        self.setUpJournal()
        bridge = Bridge(self.root)
        policy = self.policy()
        alpha = self.dispatch(policy, bridge, "alpha")
        with self.assertRaises(ValueError):
            policy.complete(bridge, {"content": {"delegation_results": []}})
        bridge.finish("alpha")
        bridge.inspect("alpha")
        with self.assertRaises(ValueError):
            policy.complete(bridge, {"content": {"delegation_results": [
                {"task_id": "alpha", "target": alpha["target"]},
                {"task_id": "beta", "target": {"ordinal": "0.900.4.1"}}]}})

    def test_failed_declared_check_blocks_dependent(self):
        plan = copy.deepcopy(PLAN)
        plan["tasks"][0]["checks"] = [["python3", "-c", "raise SystemExit(9)"]]
        bridge, policy = Bridge(self.root), self.policy(plan)
        self.dispatch(policy, bridge, "alpha")
        bridge.finish("alpha")
        bridge.inspect("alpha")
        with self.assertRaises(ValueError):
            self.dispatch(policy, bridge, "beta")
        self.assertEqual(len(bridge.calls), 1)

    def test_request_override_and_foreign_refusals(self):
        bridge, policy = Bridge(self.root), self.policy()
        with self.assertRaises(ValueError):
            self.dispatch(policy, bridge, "ghost")
        with self.assertRaises(ValueError):
            self.dispatch(policy, bridge, "alpha", model="other/model")
        foreign = Bridge(self.root)
        foreign.parent_target = {"ordinal": "0.999.1", "instantiation": 1, "session": 1}
        with self.assertRaises(ValueError):
            self.dispatch(policy, foreign, "alpha")
        self.assertEqual(bridge.calls, [])

    def test_latest_child_cycle_must_finish_normally(self):
        bridge = Bridge(self.root)
        self.dispatch(self.policy(), bridge, "alpha")
        bridge.finish("alpha")
        child = bridge.children[0]
        self.assertTrue(h.DelegationPolicy._child_finished(child))
        for status in ("failed", "interrupted", "running"):
            changed = copy.deepcopy(child)
            changed["session"]["status"] = status
            self.assertFalse(h.DelegationPolicy._child_finished(changed))
        for tail in ([{"type": "agent_start"}], [{"type": "error"}],
                     [{"type": "agent_start"}, {"type": "agent_end"}, {"type": "agent_settled"}]):
            changed = copy.deepcopy(child)
            changed["events"].extend({"record": record} for record in tail)
            self.assertFalse(h.DelegationPolicy._child_finished(changed))

    def test_legacy_prompt_and_command_unchanged_without_delegation(self):
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as runs:
            run, state = h.start("development", "Legacy fixture", Path(workspace), Path(runs),
                                 client="pi", model=None, max_activations=0)
            options = json.loads((run / "options.json").read_text())
            self.assertNotIn("delegation_version", options)
            self.assertIn("Do not delegate", h.actor_prompt(run, state, options))
            argv, _ = h.actor_command(run, state, options, h.actor_prompt(run, state, options))
            self.assertNotIn("--model", argv)
            self.assertNotIn("--extension", argv)



RPC_ACTOR = r'''
import json, os, socket, sys, uuid
from pathlib import Path
def option(name):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv else None
sid = str(uuid.uuid4())
path = Path(option('--session-dir')) / (sid+'.jsonl')
path.write_text(json.dumps({'type':'session','id':sid,'cwd':os.getcwd()})+'\n')
def emit(record):
    print(json.dumps(record), flush=True)
def request(action, **values):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
        channel.connect(os.environ['NOETIC_SESSION_SOCKET'])
        channel.sendall(json.dumps({'action':action, **values}).encode()+b'\n')
        response = json.loads(channel.makefile('rb').readline())
    if not response['success']:
        raise RuntimeError(response)
    return response['data']
for line in sys.stdin:
    command = json.loads(line)
    if command['type']=='get_state':
        provider, model = option('--model').split('/', 1)
        data = {'sessionId':sid, 'sessionFile':str(path), 'model':{'provider':provider,'id':model}, 'thinkingLevel':'high'}
    elif command['type']=='prompt':
        payload=json.loads(command['message'][command['message'].index('\n\n{')+2:])
        activation=payload['activation']
        if activation['mode']=='review':
            answer={'subject_artifact_id':activation['input_bindings']['subject'], 'verdict':'pass', 'report':'Fixture checked exact subject', 'findings':[]}
        else:
            fields=payload['result_schema']['properties']['content']['properties']
            content={key: ([] if field.get('type')=='array' else {} if field.get('type')=='object' else 'Bounded fixture evidence') for key,field in fields.items()}
            if activation['phase']=='implementation_procedure_design':
                content['steps']=[{'delegation_plan':json.loads(os.environ['FIXTURE_PLAN'])}]
            if activation['phase']=='implementation':
                identity=request('identity')
                outcomes=[]
                for task in json.loads(os.environ['FIXTURE_PLAN'])['tasks']:
                    child=request('delegate', task_id=task['id'], parentTarget=identity['target'], effort_root=identity['effort_root'])
                    observed=request('wait', target=child['target'], timeout=0)
                    assert observed['session']['target']==child['target']
                    outcomes.append({'task_id':task['id'], 'target':child['target']})
                content['delegation_results']=outcomes
            answer={'outcome':'produced', 'content':content}
        text=json.dumps(answer)
        emit({'type':'response','id':command['id'],'success':True,'data':{}})
        emit({'type':'agent_start'})
        emit({'type':'message_end','message':{'role':'assistant','stopReason':'stop','content':[{'type':'text','text':text}]}})
        emit({'type':'agent_end'})
        emit({'type':'agent_settled'})
        continue
    elif command['type']=='get_messages':
        data={'messages':[{'role':'assistant','stopReason':'stop','content':[{'type':'text','text':text}]}]}
    else:
        data={}
    emit({'type':'response','id':command['id'],'success':True,'data':data})
'''


class FullPlannedFlowTests(unittest.TestCase):
    def test_real_controller_scope_rpc_bridge_and_two_owned_children(self):
        import subprocess
        from unittest.mock import patch
        from scripts import noetic_disciplines as disciplines, noetic_sessions as sessions
        from scripts.noetic_scope import ScopeStore
        from scripts.noetic_efforts import Scope
        with tempfile.TemporaryDirectory(prefix="planned-full-flow-") as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            subprocess.run(["git", "init", str(workspace)], check=True, capture_output=True)
            (workspace / "README.md").write_text("fixture product\n")
            namespace = root / "namespace.sqlite3"
            store = ScopeStore(namespace, root_mandate={"purpose": "Fixture"}, human_ref={"fixture": True}, source_ref={"fixture": True})
            effort = store.create_effort(intent="Two disjoint owned tasks", environment={"cwd": str(workspace)}, mandate={"purpose": "Fixture"}, origin="human", human_ref={"fixture": True}, source_ref={"fixture": True})
            adapter = disciplines.Disciplines(namespace)
            instance = adapter.create_instance(command_id="fixture", effort_root=effort["ordinal"], initiator=effort["ordinal"], pattern="development", intent="Fixture", environment=effort["environment"])
            assignment = {"namespace_path": str(namespace), "effort_root": effort["ordinal"], "discipline_id": instance["id"], "environment": effort["environment"], "origin": "human", "human_ref": {"fixture": True}}
            script = root / "rpc.py"
            script.write_text(RPC_ACTOR)
            original_command = h.actor_command
            launches = []

            def command(run_dir, state, options, prompt):
                argv, environment = original_command(run_dir, state, options, prompt)
                environment = dict(os.environ if environment is None else environment)
                environment["FIXTURE_PLAN"] = json.dumps(PLAN)
                return [sys.executable, str(script), *argv[1:]], environment

            def launch(service, sid):
                launches.append(sid)
                item = service.registry.get(sid)
                path = service.registry.directory(sid) / "fixture-native.jsonl"
                path.write_text(json.dumps({"type": "session", "id": sid, "cwd": str(workspace)}) + "\n")
                provider, model = item["model"].split("/", 1)
                service.registry.update(sid, native_session_id=sid, native_session_file=str(path), status="idle", runtime={"model": {"provider": provider, "id": model}, "thinkingLevel": item["thinking"]})
                service.registry.attach(sid, {"sessionId": sid, "sessionFile": str(path)})

            def child_prompt(service, sid, message, **kwargs):
                item = service.registry.get(sid)
                task = item["actor_binding"]["task"]
                for output in task["mandate"]["outputs"]:
                    (workspace / output).write_text("# Completed fixture task " + task["id"] + "\n")
                for event in ({"type": "agent_start"}, {"type": "message_end", "message": {"role": "assistant", "stopReason": "stop", "content": [{"type": "text", "text": "Completed " + task["id"]}]}}, {"type": "turn_end"}, {"type": "agent_end"}, {"type": "agent_settled"}):
                    service.registry.event(sid, "event", event)
                service.registry.update(sid, status="idle")
                return {"accepted": True}

            with patch.object(h, "actor_command", side_effect=command), patch.object(sessions.SessionService, "_launch", launch), patch.object(sessions.SessionService, "prompt", child_prompt), patch.object(sessions.processes, "inspect", return_value={"state": "owned", "cleanup_confirmed": False}):
                run, state = h.start("development", "Implement the two declared tasks", workspace, root / "runs", verify=[sys.executable, "-c", "pass"], client="pi", model="fixture/parent", thinking="high", scope_request=assignment, timeout=10)
                self.assertEqual(state["status"], "completed", json.dumps(state.get("events", [])[-4:]))
                self.assertEqual(len(launches), 2)
                artifact = state["artifacts"][state["slots"]["accepted.implementation"]]
                receipt = artifact["content"]["delegation_receipt"]
                self.assertEqual(set(receipt["tasks"]), {"alpha", "beta"})
                self.assertTrue(all(task["checks"][0]["returncode"] == 0 for task in receipt["tasks"].values()))
                implementation = next(a for a in state["activations"].values() if a["phase"] == "implementation" and a["mode"] == "produce")
                parent = adapter.target(run, implementation["id"])
                self.assertTrue(all(task["target"]["ordinal"].startswith(parent.ordinal + ".") for task in receipt["tasks"].values()))
                self.assertEqual({item["path"] for item in artifact["content"]["changes"]}, {"alpha.py", "beta.py"})
                children = [row for row in store.branch(parent.ordinal, scope=Scope.effort(effort["ordinal"]))["records"]
                            if row["parent"] == parent.ordinal]
                self.assertEqual(len(children), 2)


if __name__ == "__main__":
    unittest.main()
