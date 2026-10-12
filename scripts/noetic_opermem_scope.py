"""Owned correspondence for actual event-only reviewed Opermem preparations."""
from __future__ import annotations

import base64
from contextlib import closing
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import os
import sqlite3
import uuid

from scripts import noetic_develop as clients, noetic_run as runtime
from scripts import noetic_purpose_binding as purpose_binding
from scripts.noetic_disciplines import Disciplines, _ReadOnlyScopeStore
from scripts.noetic_scope import Scope, ScopeError, Target
from scripts.noetic_storage import open_private


ADAPTER = "opermem-reviewed"
VERSION = "noetic-opermem-preparation/v1"
OPERATIONS = ("question", "insight", "formulation", "reflection", "conditional-structure", "checking",
              "judgment", "practical-question", "practical-inquiry", "practical-insight", "deliberation",
              "decision", "planning", "acting")
DESCRIPTOR = {
    "name": "Reviewed Opermem task", "version": 1, "kind": "reviewed-operation-composition",
    "description": "An owned external task or inquiry followed by a fresh independent read-only reviewer.",
    "programs": {"inquiry": "inquiry.reviewed/v1", "development": "development.change/v1"},
    "operations": list(OPERATIONS),
    "roles": [
        {"id": "worker", "step": "work", "mode": "development", "tools": "worker",
         "instruction": "Implement the bounded assigned task, preserve unrelated work and supply actual checks; do not self-review or delegate."},
        {"id": "inquirer", "step": "work", "mode": "inquiry", "tools": "read-search",
         "instruction": "Inspect actual sources read-only; distinguish observations, hypotheses, judgments and recommendations."},
        {"id": "reviewer", "step": "review", "mode": "both", "tools": "read-search",
         "instruction": "Independently inspect the assigned task, source evidence and worker report; return ACCEPT or REJECT with concrete evidence."},
    ],
    "bounds": ["Native Opermem alone determines typed standing.", "Completion of work is not completion of its effort.",
               "A participant reservation is not a native session.", "External effects are never replayed by correlation recovery."],
}


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def definition():
    return {"id": "noetic:opermem-reviewed", "version": _digest(DESCRIPTOR), "descriptor": deepcopy(DESCRIPTOR)}


def _absolute(path, *, existing=False):
    path = Path(path).expanduser()
    if not path.is_absolute():
        raise ScopeError("Correspondence paths must be explicit absolute paths")
    return path.resolve(strict=existing)


def _immutable(path, value):
    path = Path(path)
    data = (_json(value) + "\n").encode()
    try:
        with open_private(path, "xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except FileExistsError:
        if path.read_bytes() != data:
            raise ScopeError("Immutable owned correspondence differs from its original preparation")


class _Correlation(Disciplines):
    def _source(self, key, request):
        return {"adapter": ADAPTER, "namespace": self.store.namespace, "command_key": key,
                "request_digest": _digest(request)}

    def _event_for(self, key):
        for event in _history(self.store):
            if event["source_ref"].get("adapter") == ADAPTER and event["source_ref"].get("command_key") == key:
                return event
        return None


def _history(store):
    after = 0
    while True:
        page = store.history(after=after, limit=1000)
        yield from page["records"]
        if not page["records"]:
            return
        after = page["next_after"]


class OpermemScope:
    """Read-only construction; only explicit operations create correlation state."""
    def __init__(self, namespace_path):
        self.path = _absolute(namespace_path, existing=True)
        self.store = _ReadOnlyScopeStore(self.path)

    def _once(self, key, request, operation, effect):
        writer = _Correlation(self.path)
        return writer.once("opermem:" + key, request, operation, lambda source: effect(writer.store, source))

    def _event(self, key):
        return next((e for e in _history(self.store) if e["source_ref"].get("adapter") == ADAPTER
                     and e["source_ref"].get("command_key") == "opermem:" + key), None)

    def _authority(self, request, initiator, scope, *, current):
        if request.get("origin") == "human":
            if request.get("delegator") is not None or not isinstance(request.get("human_ref"), dict) or not request["human_ref"]:
                raise ScopeError("Human assignment requires its reference without an agent delegator")
        elif request.get("origin") == "agent":
            if request.get("human_ref") is not None or not isinstance(request.get("delegator"), dict):
                raise ScopeError("Agent assignment requires its actual exact delegator")
            target = Target(**request["delegator"])
            if target.ordinal != initiator:
                raise ScopeError("Actual delegator must be the discipline initiator")
            actual = self.store.resolve(target.ordinal, scope=scope,
                **({} if current else {"instantiation": target.instantiation, "session": target.session}))
            if actual != target:
                raise ScopeError("Exact discipline initiator is stale")
        else:
            raise ScopeError("Assignment must be explicitly human or agent originated")

    def create_instance(self, *, command_id, effort_root, initiator, intent, environment, origin,
                        human_ref=None, delegator=None, parent_instance=None):
        scope = Scope.effort(effort_root)
        owner = self.store.position(effort_root, scope=scope)
        position = self.store.position(initiator, scope=scope)
        if owner["environment"] != environment or position["status"] != "open":
            raise ScopeError("Instance requires its existing open effort and exact environment")
        request = {"effort_root": effort_root, "initiator": initiator, "intent": intent,
                   "environment": environment, "origin": origin, "human_ref": human_ref,
                   "delegator": delegator, "parent_instance": parent_instance, "definition_ref": definition()}
        self._authority(request, initiator, scope, current=True)
        if parent_instance is not None:
            parent = self.store.discipline(parent_instance, scope=scope)
            if parent["effort"] != effort_root or position["discipline_id"] != parent_instance:
                raise ScopeError("Nested instance requires an actual participant in its parent discipline")
        if not isinstance(command_id, str) or not command_id.strip():
            raise ScopeError("Instance requires a nonempty command identity")
        return self._once("instance:" + command_id, request, "discipline", lambda store, source:
            store.create_discipline(effort_root, scope=scope, initiator=initiator,
                definition_ref=request["definition_ref"], intent=intent, parent_instance=parent_instance,
                initiating_target=Target(**delegator) if delegator else None,
                source_ref={**source, "authority": {k: request[k] for k in ("origin", "human_ref", "delegator")}}))

    def validate_request(self, request, workspace, *, current=True):
        if not isinstance(request, dict) or set(request) - {
                "namespace_path", "effort_root", "discipline_id", "environment", "origin", "human_ref", "delegator", "preparation"}:
            raise ScopeError("Unknown owned reviewed assignment field")
        if not {"namespace_path", "effort_root", "discipline_id", "environment", "origin"} <= request.keys():
            raise ScopeError("Owned assignment requires namespace, effort, discipline, environment and origin")
        if _absolute(request["namespace_path"], existing=True) != self.path:
            raise ScopeError("Assignment namespace differs from its configured namespace")
        if type(request["discipline_id"]) is not int or request["discipline_id"] < 1:
            raise ScopeError("Discipline identity must be a positive integer")
        scope = Scope.effort(request["effort_root"])
        instance = self.store.discipline(request["discipline_id"], scope=scope)
        if instance["definition_ref"] != definition() or instance["environment"] != request["environment"]:
            raise ScopeError("Exact reviewed definition and frozen instance environment are required")
        position = self.store.position(instance["initiator"], scope=scope)
        if current:
            if position["status"] != "open" or self.store.position(instance["effort"], scope=scope)["environment"] != instance["environment"]:
                raise ScopeError("Discipline requires an open initiator and current declared environment")
            Disciplines(self.path, readonly=True)._workspace(instance["environment"], workspace, request.get("preparation"))
        self._authority(request, instance["initiator"], scope, current=current)
        return instance

    def bind_store(self, *, command_id, effort_root, store_path, host):
        scope = Scope.effort(effort_root)
        self.store.position(effort_root, scope=scope)
        directory, binary = _absolute(store_path), _absolute(host, existing=True)
        if not binary.is_file() or (directory.exists() and not directory.is_dir()):
            raise ScopeError("Store directory and actual host file are required")
        if not isinstance(command_id, str) or not command_id.strip():
            raise ScopeError("Store registration requires a command identity")
        reference = {"namespace_path": str(self.path), "namespace": self.store.namespace, "effort_root": effort_root,
                     "directory": str(directory), "authority_db": str(directory / "authority.sqlite3"), "host": str(binary),
                     "id": _digest({"namespace": self.store.namespace, "directory": str(directory)}),
                     "native_identity": None, "lineage": "present correspondence; pre-existing native history unassigned"}
        def register(store, source):
            for event in _history(store):
                if event["kind"] == "opermem-store-bound" and event["source_ref"].get("adapter") == ADAPTER:
                    existing = event["data"]["store_ref"]
                    if existing["directory"] == reference["directory"] and existing != reference:
                        raise ScopeError("Native store locator already corresponds to another effort or host in this namespace")
            return store.record_event(effort_root, scope=scope, kind="opermem-store-bound",
                                      data={"store_ref": reference}, source_ref=source)
        result = self._once("store:" + command_id, reference, "event", register)
        return result["data"]["store_ref"]

    def validate_store(self, reference, effort_root):
        if not isinstance(reference, dict) or reference.get("effort_root") != effort_root:
            raise ScopeError("Native store correspondence belongs to another effort")
        found = any(e["kind"] == "opermem-store-bound" and e["source_ref"].get("adapter") == ADAPTER
                    and e["data"].get("store_ref") == reference for e in _history(self.store))
        if not found or reference["namespace"] != self.store.namespace or reference["namespace_path"] != str(self.path):
            raise ScopeError("Native store correspondence differs from its canonical registration")
        if str(_absolute(reference["directory"])) != reference["directory"] or str(_absolute(reference["host"], existing=True)) != reference["host"]:
            raise ScopeError("Native store or host locator changed")
        return reference

    def prepare_execution(self, request, *, task, workspace, runs_dir, store_ref, operation, inquiry, client,
                          model=None, review_model=None, worker_controls=None, run_id=None,
                          purpose_ref=None, purpose_config=None, source_paths=(), occasion=None):
        instance = self.validate_request(request, workspace)
        self.validate_store(store_ref, request["effort_root"])
        if not isinstance(task, str) or not task.strip() or operation not in OPERATIONS or type(inquiry) is not bool or client not in ("pi", "opencode"):
            raise ScopeError("Exact reviewed task, operation, mode and client are required")
        controls = worker_controls or {}
        if controls and (client != "pi" or set(controls) != {"reasoning_effort"} or controls["reasoning_effort"] not in
                         ("off", "minimal", "low", "medium", "high", "xhigh", "max")):
            raise ScopeError("Only maintained Pi reasoning controls are supported")
        for value in (model, review_model):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ScopeError("Selected models must be explicit text or absent")
        owned_purpose = None
        if purpose_ref is not None or purpose_config is not None:
            owned_purpose = purpose_binding.prepare(purpose_ref, purpose_config, request)
        if occasion is not None and (not isinstance(occasion, dict) or set(occasion) != {"kind", "id"}
                or occasion["kind"] not in ("experience", "outcome-as-experience")
                or type(occasion["id"]) is not int or not 0 < occasion["id"] < 2**64):
            raise ScopeError("Selected occasion requires exact native kind and positive u64 identity")
        sources, size = [], 0
        for selected in source_paths:
            path = _absolute(selected, existing=True)
            with path.open("rb") as stream:
                data = stream.read(1024 * 1024 + 1)
            size += len(data)
            if size > 1024 * 1024:
                raise ScopeError("Explicit retained host sources exceed the bounded 1 MiB preparation")
            sources.append({"kind": "external-host-evidence", "path": str(path), "sha256": hashlib.sha256(data).hexdigest(),
                            "bytes_base64": base64.b64encode(data).decode(), "native_retained_experience": False})
        run_id = run_id or uuid.uuid4().hex
        if not isinstance(run_id, str) or len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
            raise ScopeError("Prepared run identity requires a lowercase hexadecimal UUID")
        root, workspace = _absolute(runs_dir), _absolute(workspace, existing=True)
        base = {"version": VERSION, "namespace": self.store.namespace, "namespace_path": str(self.path),
                "effort_root": instance["effort"], "discipline_id": instance["id"], "initiator": instance["initiator"],
                "definition_ref": instance["definition_ref"], "assignment": deepcopy(request),
                "environment": instance["environment"], "workspace": str(workspace), "runs_dir": str(root),
                "run_id": run_id, "run_dir": str(root / run_id),
                "preparation_path": str(root / ".opermem-preparations" / run_id / "binding.json"),
                "store_ref": deepcopy(store_ref), "operation": operation, "inquiry": inquiry, "client": client,
                "model": model, "review_model": review_model or model, "worker_controls": deepcopy(controls),
                "task": {"text": task, "sha256": hashlib.sha256(task.encode()).hexdigest()},
                "host_sources": sources, "occasion_selection": deepcopy(occasion),
                "purpose_ref": owned_purpose["purpose_ref"] if owned_purpose else None,
                "purpose_config": owned_purpose["purpose_config"] if owned_purpose else None,
                "telos_chain": owned_purpose["telos_chain"] if owned_purpose else None,
                "telos_db": owned_purpose["telos_db"] if owned_purpose else None,
                "telos_source": owned_purpose["telos_source"] if owned_purpose else None}
        record = self._once("run:" + run_id + ":execution", base, "execution", lambda store, source:
            store.create_execution(instance["id"], scope=Scope.effort(instance["effort"]), native_ref=base, source_ref=source))
        binding = {**base, "execution_id": record["id"]}
        _immutable(base["preparation_path"], binding)
        return binding

    def validate_binding(self, binding, *, revalidate_purpose=True, current=False):
        if not isinstance(binding, dict) or binding.get("version") != VERSION:
            raise ScopeError("Owned reviewed preparation is incomplete")
        base = {k: v for k, v in binding.items() if k != "execution_id"}
        with self.store._connection() as db:
            row = db.execute("SELECT discipline_id,native_ref FROM executions WHERE id=?", (binding["execution_id"],)).fetchone()
        if row is None or row[0] != binding["discipline_id"] or json.loads(row[1]) != base:
            raise ScopeError("Retained preparation differs from its canonical execution")
        if binding["namespace_path"] != str(self.path) or binding["namespace"] != self.store.namespace:
            raise ScopeError("Prepared execution belongs to another namespace")
        instance = self.validate_request(binding["assignment"], binding["workspace"], current=current)
        if instance["id"] != binding["discipline_id"] or instance["effort"] != binding["effort_root"] or instance["initiator"] != binding["initiator"]:
            raise ScopeError("Prepared instance correspondence is inconsistent")
        self.validate_store(binding["store_ref"], binding["effort_root"])
        if json.loads(Path(binding["preparation_path"]).read_text()) != binding:
            raise ScopeError("Original immutable preparation is unavailable or changed")
        if revalidate_purpose and binding["purpose_ref"] is not None:
            actual = purpose_binding.prepare(binding["purpose_ref"], binding["purpose_config"], binding["assignment"],
                chain=binding["telos_chain"], db=binding["telos_db"], source=binding["telos_source"])
            if any(binding[key] != value for key, value in actual.items()):
                raise ScopeError("Owned purpose correspondence changed")
        return binding

    def recover_preparation(self, execution_id):
        with self.store._connection() as db:
            row = db.execute("SELECT native_ref FROM executions WHERE id=?", (execution_id,)).fetchone()
        if row is None:
            raise ScopeError("Prepared execution is unavailable")
        base = json.loads(row[0])
        if base.get("version") != VERSION or base.get("namespace") != self.store.namespace:
            raise ScopeError("Execution is not an owned reviewed preparation")
        binding = {**base, "execution_id": execution_id}
        self.validate_request(binding["assignment"], binding["workspace"], current=False)
        self.validate_store(binding["store_ref"], binding["effort_root"])
        _immutable(base["preparation_path"], binding)
        return self.validate_binding(binding)

    def _record(self, binding, key, kind, data, *, ordinal=None, target=None):
        ordinal = ordinal or binding["initiator"]
        return self._once("run:" + binding["run_id"] + ":" + key,
            {"ordinal": ordinal, "target": target, "kind": kind, "data": data}, "event", lambda store, source:
                store.record_event(ordinal, scope=Scope.effort(binding["effort_root"]), kind=kind, data=data,
                    target=Target(**target) if target else None, discipline_id=binding["discipline_id"],
                    execution_id=binding["execution_id"], source_ref=source))

    def preparation_failed(self, binding, error):
        self.validate_binding(binding, revalidate_purpose=False)
        if not isinstance(error, str) or not error.strip():
            raise ScopeError("Preparation failure requires an actual diagnostic")
        return self._record(binding, "preparation-failed:" + _digest(error), "opermem-preparation-failed", {"error": error})

    def lifecycle(self, binding):
        return ReviewedLifecycle(self, deepcopy(binding))

    def correspondence(self, binding):
        self.validate_binding(binding, revalidate_purpose=False)
        run_dir, participants = Path(binding["run_dir"]), []
        for step in ("work", "review"):
            event = self._event("run:" + binding["run_id"] + ":participant:" + step)
            if event is None:
                continue
            position = self.store.position(event["ordinal"])
            session_event = self._event("run:" + binding["run_id"] + ":native:" + step + ":session")
            observation = self._event("run:" + binding["run_id"] + ":observation:" + step)
            target, native, status = None, None, None
            if session_event:
                target = {"ordinal": event["ordinal"], "instantiation": session_event["instantiation"], "session": session_event["session"]}
                session = next(s for s in self.store.sessions(target["ordinal"], target["instantiation"])
                               if s["sequence"] == target["session"])
                native, status = session["native_ref"], session["status"]
                if observation is None or observation["data"].get("native_ref") != native or observation["data"].get("target") != target:
                    raise ScopeError("Actual participant observation correspondence is incomplete")
            if observation:
                evidence = observation["data"]
                path = Path(evidence["stdout"])
                raw = path.read_bytes() if path.exists() else b""
                if hashlib.sha256(raw).hexdigest() != evidence["stdout_sha256"]:
                    raise ScopeError("Captured actor evidence changed or is unavailable")
                actual = [e for e in runtime.read_events(run_dir) if e["kind"] in ("step.started", "step.finished") and e["data"]["step"] == step]
                if actual != evidence["step_events"]:
                    raise ScopeError("Actual actor events differ from the retained observation")
            participants.append({"step": step, "ordinal": position["ordinal"], "origin": position["origin"],
                                 "target": target, "native_session_ref": native, "session_status": status,
                                 "position_status": position["status"], "observation": observation["data"] if observation else None})
        attached = self._event("run:" + binding["run_id"] + ":attached")
        state = "prepared"
        if attached:
            self.lifecycle(binding)._validate_run(run_dir, revalidate_purpose=False)
            state = runtime.project(runtime.read_events(run_dir))["state"]
        failures = [e for e in _history(self.store) if e["execution_id"] == binding["execution_id"]
                    and e["kind"] == "opermem-preparation-failed"]
        if not attached and failures:
            state = "preparation-failed"
        return {"correlation_status": "assigned", "namespace": self.store.namespace, "effort_root": binding["effort_root"],
                "discipline_id": binding["discipline_id"], "definition_ref": binding["definition_ref"],
                "execution_id": binding["execution_id"], "run_id": binding["run_id"], "run_status": state,
                "participants": participants, "store_ref": binding["store_ref"], "host_sources": binding["host_sources"],
                "occasion_selection": binding["occasion_selection"], "purpose_ref": binding["purpose_ref"],
                "preparation_failures": failures,
                "coverage": "Event-only reviewed correspondence; native identity only from captured client stream; no native semantic promotion"}

    def inspect_preparations(self, *, effort_root):
        self.store.position(effort_root, scope=Scope.effort(effort_root))
        with self.store._connection() as db:
            rows = db.execute("SELECT e.id,e.native_ref FROM executions e JOIN disciplines d ON d.id=e.discipline_id WHERE d.effort=? ORDER BY e.id", (effort_root,)).fetchall()
        results = []
        for row in rows:
            base = json.loads(row[1])
            if base.get("version") == VERSION:
                binding = {**base, "execution_id": row[0]}
                try:
                    results.append(self.correspondence(binding))
                except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                    results.append({"execution_id": row[0], "correlation_status": "unavailable", "error": str(exc)})
        return results


def _journal_once(run_dir, kind, data):
    path = Path(run_dir) / "events.sqlite3"
    with closing(sqlite3.connect(path, timeout=30)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT data FROM events WHERE kind=?", (kind,)).fetchall()
        if existing:
            if len(existing) != 1 or json.loads(existing[0][0]) != data:
                raise ScopeError("Retained reviewed journal binding differs from its original correspondence")
        else:
            runtime.append_event(db, kind, data)


class ReviewedLifecycle:
    def __init__(self, adapter, binding):
        self.adapter, self.binding = adapter, binding

    def validate_develop(self, *, task, workspace, runs_dir, run_id, inquiry, client, model,
                         review_model, worker_controls, telos_chain, telos_db, telos_source):
        binding = self.adapter.validate_binding(self.binding, current=True)
        requested = {"task": task, "workspace": str(Path(workspace).resolve()), "runs_dir": str(Path(runs_dir).resolve()),
                     "run_id": run_id, "inquiry": inquiry, "client": client, "model": model,
                     "review_model": review_model or model, "worker_controls": worker_controls or {}}
        expected = {key: binding["task"]["text"] if key == "task" else binding[key] for key in requested}
        if requested != expected:
            raise ScopeError("Actual reviewed launch differs from its immutable prepared execution")
        for supplied, key in ((telos_chain, "telos_chain"), (telos_db, "telos_db"), (telos_source, "telos_source")):
            if supplied is not None and str(supplied) != binding[key]:
                raise ScopeError("Actual Telos selection differs from the complete owned purpose")
        return {key: binding[key] for key in ("telos_chain", "telos_db", "telos_source", "purpose_ref")}

    def _validate_run(self, run_dir, *, revalidate_purpose=True):
        b = self.adapter.validate_binding(self.binding, revalidate_purpose=revalidate_purpose)
        run_dir = Path(run_dir).resolve(strict=True)
        if str(run_dir) != b["run_dir"] or (run_dir / "controller.sqlite3").exists():
            raise ScopeError("Correspondence requires the original actual event-only run")
        if json.loads((run_dir / "opermem-scope.json").read_text()) != b:
            raise ScopeError("Run-owned copy differs from its immutable preparation")
        events = runtime.read_events(run_dir)
        declared = [e["data"] for e in events if e["kind"] == "scope.bound"]
        expected = self.adapter._event("run:" + b["run_id"] + ":attached")
        programs = [e["data"] for e in events if e["kind"] == "program.started"]
        if declared != [b] or expected is None or events[0]["data"] != expected["data"]["created"] or programs != [expected["data"]["program"]]:
            raise ScopeError("Retained run journal differs from its canonical attachment")
        governing = json.loads((run_dir / "telos-context.json").read_text()) if (run_dir / "telos-context.json").exists() else None
        if governing != expected["data"]["governing"]:
            raise ScopeError("Frozen governing aggregate differs from its canonical attachment")
        purpose_events = [e["data"] for e in events if e["kind"] == "purpose.bound"]
        owned = {k: b[k] for k in ("purpose_ref", "purpose_config", "telos_chain", "telos_db", "telos_source")}
        if purpose_events != ([owned] if b["purpose_ref"] else []):
            raise ScopeError("Owned purpose journal association changed")
        for event in events:
            if event["kind"] == "telos.linked" and any(event["data"].get(k) != b[v] for k, v in
                    (("chain_id", "telos_chain"), ("db_path", "telos_db"), ("source", "telos_source"))):
                raise ScopeError("Actual Telos association differs from the owned purpose")
        return events

    def validate_binding(self, run_dir):
        return self._validate_run(run_dir)

    def run_created(self, run_dir):
        b = self.adapter.validate_binding(self.binding, current=True)
        run_dir = Path(run_dir).resolve(strict=True)
        events = runtime.read_events(run_dir)
        programs = [e["data"] for e in events if e["kind"] == "program.started"]
        program = DESCRIPTOR["programs"]["inquiry" if b["inquiry"] else "development"]
        if str(run_dir) != b["run_dir"] or events[0]["data"]["workspace"] != b["workspace"] or events[0]["data"]["plan"]["goal"] != b["task"]["text"]:
            raise ScopeError("Actual created run differs from the prepared task/workspace")
        if len(programs) != 1 or programs[0]["program"] != program or programs[0]["client"] != b["client"] or programs[0]["model"] != b["model"] or programs[0]["worker_controls"] != b["worker_controls"]:
            raise ScopeError("Actual reviewed program differs from its preparation")
        if any(e["kind"] in ("step.started", "step.finished", "telos.linked") for e in events):
            raise ScopeError("Run attachment must precede meaningful effects")
        governing = json.loads((run_dir / "telos-context.json").read_text()) if b["purpose_ref"] else None
        if governing is not None and (governing.get("purpose_ref") != b["purpose_ref"] or governing.get("chain_id") != b["telos_chain"]):
            raise ScopeError("Actual governing context differs from the complete owned purpose")
        self.adapter._record(b, "attached", "opermem-run-attached", {"created": events[0]["data"], "program": programs[0], "governing": governing})
        _immutable(run_dir / "opermem-scope.json", b)
        _journal_once(run_dir, "scope.bound", b)
        if b["purpose_ref"]:
            _journal_once(run_dir, "purpose.bound", {k: b[k] for k in ("purpose_ref", "purpose_config", "telos_chain", "telos_db", "telos_source")})
        self._validate_run(run_dir)

    def before_actor(self, run_dir, step, role, client, prompt):
        events = self._validate_run(run_dir)
        b = self.adapter.validate_binding(self.binding, current=True)
        expected_role = "reviewer" if step == "review" else "inquirer" if b["inquiry"] else "worker"
        if step not in ("work", "review") or role != expected_role or client != b["client"]:
            raise ScopeError("Actual actor role/client differs from its reserved reviewed function")
        if any(e["kind"] in ("step.started", "step.finished") and e["data"]["step"] == step for e in events):
            raise ScopeError("Actor step already attempted; correlation recovery never executes it again")
        if step == "review" and self.adapter._event("run:" + b["run_id"] + ":native:work:session") is None:
            raise ScopeError("Fresh review requires its observed actual worker session")
        mandate = {"purpose": b["task"]["text"], "role": role, "step": step, "run_id": b["run_id"],
                   "definition_ref": b["definition_ref"], "execution_id": b["execution_id"],
                   "environment": b["environment"], "execution_workspace": b["workspace"],
                   "purpose_ref": b["purpose_ref"], "bounds": "Only this actual reviewed step; no delegation"}
        assignment, scope = b["assignment"], Scope.effort(b["effort_root"])
        position = self.adapter._once("run:" + b["run_id"] + ":participant:" + step,
            {"binding": b, "mandate": mandate}, "delegate", lambda store, source:
                store.delegate(b["initiator"], scope=scope, mandate=mandate, origin=assignment["origin"],
                    human_ref=assignment.get("human_ref"), delegator=Target(**assignment["delegator"]) if assignment.get("delegator") else None,
                    discipline_id=b["discipline_id"], source_ref=source))
        responsibility = {"ordinal": position["ordinal"], "target": None, "namespace": b["namespace"],
                          "effort_root": b["effort_root"], "discipline_id": b["discipline_id"],
                          "execution_id": b["execution_id"], "received_mandate": mandate,
                          "native_observation": "reserved; actual client identity not yet observed"}
        return prompt + "\n\n" + _json({"responsibility": responsibility}) + "\n"

    def after_actor(self, run_dir, step, client):
        events = self._validate_run(run_dir, revalidate_purpose=False)
        b = self.binding
        participant = self.adapter._event("run:" + b["run_id"] + ":participant:" + step)
        if participant is None or step not in ("work", "review") or client != b["client"]:
            raise ScopeError("Native observation requires its prior actual participant reservation")
        path = Path(run_dir) / (step + ".stdout.log")
        raw = path.read_bytes() if path.exists() else b""
        identities, malformed, stream_events = set(), False, []
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("non-object native event")
                stream_events.append(event)
                value = event.get("id") if client == "pi" and event.get("type") == "session" else event.get("sessionID") if client == "opencode" else None
                if value is not None:
                    if not isinstance(value, str) or not value.strip():
                        raise ValueError("invalid native identity")
                    identities.add(value)
            except (ValueError, TypeError):
                malformed = True
        observed = [e for e in events if e["kind"] in ("step.started", "step.finished") and e["data"]["step"] == step]
        finish = next((e for e in reversed(observed) if e["kind"] == "step.finished"), None)
        passed = bool(finish and finish["data"]["state"] == "passed")
        ordinal, scope = participant["ordinal"], Scope.effort(b["effort_root"])
        evidence = {"stdout": str(path), "stdout_sha256": hashlib.sha256(raw).hexdigest(),
                    "step_events": observed, "identity_count": len(identities), "malformed_records": malformed}
        if len(identities) != 1:
            self.adapter._record(b, "observation:" + step, "opermem-native-unavailable", evidence, ordinal=ordinal)
            if passed or identities:
                raise ScopeError("Actor emitted missing or conflicting actual native identities")
            return
        identity = next(iter(identities))
        if step == "review":
            original = self.adapter._event("run:" + b["run_id"] + ":native:work:session")
            if original and original["data"]["native_ref"]["session_id"] == identity:
                self.adapter._record(b, "observation:" + step, "opermem-native-unavailable", {**evidence, "error": "review reused worker native session"}, ordinal=ordinal)
                raise ScopeError("Review reused the actual worker native session")
        native = {"client": client, "session_id": identity, "context_file": None, "source": str(path),
                  "stdout_sha256": evidence["stdout_sha256"], "observation": "retained-native-stream",
                  "context_coverage": "This JSON CLI stream exposes session identity without a native context-file reference"}
        base = "run:" + b["run_id"] + ":native:" + step
        instance = self.adapter._once(base + ":instance", {"ordinal": ordinal, "native_ref": native}, "instantiate",
            lambda store, source: store.instantiate(ordinal, scope=scope, native_ref=native, source_ref=source))
        target = self.adapter._once(base + ":session", {"ordinal": ordinal, "native_ref": native}, "session",
            lambda store, source: store.open_session(ordinal, instance["sequence"], scope=scope, native_ref=native, source_ref=source))
        completed, error, result_ref = False, None, None
        if passed and not malformed:
            try:
                if any(event.get("type") == "error" for event in stream_events):
                    raise ValueError("Native stream emitted an execution error")
                if client == "pi":
                    lifecycle = [event["type"] for event in stream_events if event.get("type") in
                        ("agent_start", "turn_start", "message_start", "message_update", "message_end", "turn_end", "agent_end")]
                    if not lifecycle or lifecycle[-1] != "agent_end":
                        raise ValueError("Native Pi stream has an unfinished later turn")
                result = clients.parse_transcript(path, client)
                if result["session_id"] != identity:
                    raise ValueError("Final report native identity differs from observation")
                completed = True
                result_ref = {"source": str(path), "text_sha256": hashlib.sha256(result["text"].encode()).hexdigest()}
            except (ValueError, KeyError, TypeError) as exc:
                error = str(exc)
        self.adapter._once("run:" + b["run_id"] + ":activation:" + step,
            {"target": target, "evidence": evidence, "result_ref": result_ref}, "event", lambda store, source:
                store.record_activation(b["execution_id"], scope=scope, participant=Target(**target),
                    native_ref={"kind": "event-only-reviewed-step", "step": step, **evidence}, source_ref=source, result_ref=result_ref))
        self.adapter._record(b, "observation:" + step, "opermem-native-observed", {"target": target, "native_ref": native,
                             "native_turn_completed": completed, "error": error, **evidence}, ordinal=ordinal, target=target)
        status = "closed" if completed else "failed"
        self.adapter._once(base + ":status", {"target": target, "status": status}, "event", lambda store, source:
            store.set_session_status(Target(**target), status, scope=scope, source_ref=source))
        self.adapter._once(base + ":closed", {"ordinal": ordinal}, "event", lambda store, source:
            store.close_position(ordinal, scope=scope, source_ref=source))
        if passed and not completed:
            raise ScopeError("Native actor returned without a valid completed report: " + (error or "malformed stream"))
