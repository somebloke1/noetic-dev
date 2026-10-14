"""Local operator application services. Harness owns execution; kernels own policy."""

from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
import re
import shutil
import uuid
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
from urllib import request, error

from scripts import noetic_controller as controller
from scripts import noetic_disciplines as disciplines
from scripts import noetic_memory as memory
from scripts import noetic_model_defaults as model_defaults
from scripts import noetic_recall as recall
from scripts import noetic_opermem_application as reviewed
from scripts.noetic_efforts import Efforts
from scripts.noetic_scope import Scope, ScopeError
from scripts import noetic_harness as harness
from scripts import noetic_local as local
from scripts import noetic_projects as projects
from scripts import noetic_purpose_binding as purpose_binding
from scripts import noetic_run as runtime
from scripts import noetic_semantic as semantic
from scripts import noetic_telos as telos
from scripts.noetic_storage import create_private_sqlite, ensure_private_directory, open_private


PROFILES = [
    {"id": "pi-direct", "label": "Pi / direct Codex subscription", "client": "pi", "model": "openai-codex/gpt-6.1-sol"},
    {"id": "opencode-direct", "label": "OpenCode / direct subscription", "client": "opencode", "model": "openai/gpt-6.1-sol"},
]
HEALTH_ENDPOINTS = {"Qwen": "http://127.0.0.1:8742/health", "Ollama": "http://127.0.0.1:11434/api/ps",
                    "LiteLLM": "http://127.0.0.1:3333/health/liveliness"}
SAFE_OPTIONS = ("pattern", "client", "model", "qa_model", "thinking", "timeout", "verify", "max_returns", "max_remediations", "telos_chain",
                "project", "owned_worktree", "workspace_base_commit", "verification_mode")


class ApplicationError(ValueError):
    def __init__(self, status, message, run_id=None):
        super().__init__(message)
        self.status, self.run_id = status, run_id


def now():
    return datetime.now(timezone.utc).isoformat()


def contained(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ApplicationError(403, "Evidence path is outside its selected scope.")
    return resolved


def read_json(path, root, default=None):
    source = contained(path, root)
    if not source.exists():
        return default
    return json.loads(source.read_text(encoding="utf-8"))


def write_driver(run, data):
    path = contained(run / "application-driver.json", run)
    temporary = path.with_suffix(".tmp")
    with open_private(temporary) as stream:
        stream.write(json.dumps(data, ensure_ascii=True) + "\n")
    temporary.replace(path)


def lock_held(path, root):
    path = contained(path, root)
    try:
        with path.open("rb") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(stream, fcntl.LOCK_UN)
    except FileNotFoundError:
        pass
    return False


def runtime_info(run, state, *, app=None, selection=None):
    if state is None:
        if app is not None and app.namespace_path.exists():
            binding = app.reviewed().binding(run.name, selection)
            if binding is not None:
                correlation = app.reviewed().authority(run.name, selection)
                return app.reviewed().runtime(binding, correlation)
        elif (run / "opermem-scope.json").exists():
            # Public legacy helper has no caller selection; use only its exact retained owner.
            owned_run = reviewed.native.owned_run(run)
            if owned_run:
                binding = owned_run[1]
                owner = {"kind": "effort", "effort_root": binding["effort_root"]}
                service = Application(run.parent, namespace_path=binding["namespace_path"]).reviewed()
                return service.runtime(binding, service.authority(run.name, owner))
    options = read_json(run / "options.json", run, {})
    config = {key: options.get(key) for key in SAFE_OPTIONS}
    if state is not None:
        config["project"] = options.get("project") or state["workspace"]
        config["execution_workspace"] = state["workspace"]
    if state is None:
        return {"supported": False, "activity": "unsupported", "reason": "Legacy run: no shared controller.", "configuration": config}
    driver = read_json(run / "application-driver.json", run, {})
    owned = lock_held(run / "application-driver.lock", run)
    executing = lock_held(run / "driver.lock", run)
    pause = contained(run / "pause.requested", run).exists()
    cancel = contained(run / "cancel.requested", run).exists()
    activation = state["activations"].get(state["current_activation"])
    uncertain = bool(activation and activation["status"] == "running" and not (owned or executing))
    cleanup = harness.process_info(run, state)
    if state["status"] != "active":
        activity, reason = "terminal", f"Kernel is {state['status']}."
    elif cancel:
        activity, reason = "cancel_requested", "Cancellation requested; kernel remains active."
    elif owned or executing:
        activity, reason = ("pause_requested", "Pause requested; current activation may finish before checkpoint.") if pause else (
            "running", "A driver holds an execution lock; this does not establish model progress.")
    elif uncertain:
        activity, reason = "intervention", "No driver owns the running reservation. Do not relaunch uncertain actor effects."
        if driver.get("error"):
            reason += " Background failure: " + driver["error"]
    elif driver.get("status") == "failed":
        activity, reason = "failed", driver.get("error", "Background driver failed before advancing.")
    else:
        activity, reason = "held", "Paused at a ready reservation." if pause else "No driver owns this ready reservation; advance explicitly."
    if cancel:
        reason += " Process cleanup confirmed." if cleanup["cleanup_confirmed"] else " Process cleanup is not confirmed; cancellation is only a request."
    elif state["status"] != "active" and not cleanup["cleanup_confirmed"]:
        reason += " Process cleanup is unconfirmed; uncertain ownership history does not establish an active process."
    return {"supported": True, "activity": activity, "reason": reason, "driver": driver,
            "gui_driver_owned": owned, "harness_driver_owned": executing, "pause_requested": pause,
            "pause_applied": pause and state["status"] == "active" and not (owned or executing) and not uncertain,
            "can_advance": state["status"] == "active" and not (owned or executing or cancel or uncertain),
            "configuration": config, "process_cleanup": cleanup,
            "cleanup_confirmed": cleanup["cleanup_confirmed"], "observed_at": now()}


def reuse_setup(run, state, status):
    """Project representable frozen setup only; never repair history or execute it."""
    def unsupported(reason):
        raise ApplicationError(422, f"Reuse setup unsupported: {reason} Draft unchanged.")

    options = read_json(run / "options.json", run)
    if state is None or not isinstance(options, dict):
        unsupported("a readable harness controller and frozen options are required.")
    required = {"pattern", "client", "thinking", "timeout", "verify", "max_returns", "max_remediations"}
    if not required <= options.keys() or options.keys() - (required | {
            "model", "qa_model", "goal_ref", "telos_chain", "telos_db", "telos_source",
            "project", "owned_worktree", "workspace_base_commit", "verification_mode", "scope",
            "purpose_ref", "purpose_config"}):
        unsupported("missing or unknown frozen options.")
    pattern = options["pattern"]
    if pattern not in ("development", "cognition") or options["client"] not in ("pi", "opencode"):
        unsupported("pattern or client is outside the New pattern choices.")
    current = read_json(controller.PATTERN_DIR / f"{pattern}.json", controller.PATTERN_DIR)
    chain = options.get("telos_chain")
    if chain is not None and (not isinstance(chain, str) or not chain.strip()):
        unsupported("invalid historical Telos chain.")
    if chain:
        for phase in current["phases"]:
            phase["required_inputs"]["external.governing"] = "external.governing"
    if state["pattern"] != current:
        unsupported("historical pattern differs from the current built-in definition; it cannot be copied as that pattern.")
    for key in ("max_returns", "max_remediations"):
        if type(options[key]) is not int or not 0 <= options[key] <= 20 or options[key] != state[key]:
            unsupported(f"{key} is inconsistent or outside form bounds 0-20.")
    timeout = options["timeout"]
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 1 <= timeout <= 7200 or timeout != int(timeout):
        unsupported("timeout is outside the form's whole-second bounds 1-7200.")
    fields = {key: options.get(key) for key in required | {"model", "qa_model"}}
    fields.update(task=state["purpose"], workspace=state["workspace"], telos_chain=None)
    for key in ("task", "workspace", "model", "qa_model", "thinking"):
        value = fields[key]
        if key in ("model", "qa_model") and value is None:
            continue
        if (not isinstance(value, str) or not value.strip() or "\0" in value or "\r" in value
                or (key != "task" and "\n" in value)):
            unsupported(f"{key} cannot round-trip through its form field.")
    if status["goal"] != fields["task"] or status["workspace"] != fields["workspace"]:
        unsupported("journal and controller purpose/workspace disagree.")
    verify = fields["verify"]
    if (verify is not None and (not isinstance(verify, list) or not verify
            or any(not isinstance(arg, str) or "\0" in arg for arg in verify))):
        unsupported("verification is not representable as JSON argv for this pattern.")
    mode = "supplied" if verify is not None else "worker-selected" if pattern == "development" else "not-requested"
    if options.get("verification_mode", mode) != mode:
        unsupported("verification mode conflicts with the frozen pattern/check options.")
    external = {slot: state["artifacts"][ref] for slot, ref in state["slots"].items() if slot.startswith("external.")}
    expected = {"external.purpose", "external.sources"} | ({"external.governing"} if chain else set())
    if set(external) != expected or any(a["type"] != slot or a["origin"] != "external" for slot, a in external.items()):
        unsupported("arbitrary or inconsistent external inputs cannot be represented.")
    if external["external.purpose"]["content"] != fields["task"]:
        unsupported("external purpose disagrees with controller purpose.")
    if chain and external["external.governing"]["content"].get("chain_id") != chain:
        unsupported("frozen governing input disagrees with the historical Telos chain.")
    try:
        events = disciplines.runtime_events(run)
        declared = [event["data"] for event in events if event["kind"] == "purpose.bound"]
        governing = external.get("external.governing", {}).get("content", {})
        if "purpose_ref" in options or "purpose_config" in options or declared or "purpose_ref" in governing:
            assignment = disciplines.validate_binding(run, options=options)
            if assignment is None:
                unsupported("owned purpose has no retained execution assignment.")
            expected = {key: options.get(key) for key in purpose_binding.FIELDS}
            canonical = disciplines.correspondence(run)["native_run"]["options"]
            if (any(options.get(key) != canonical.get(key) for key in purpose_binding.FIELDS)
                    or len(declared) != 1 or declared[0] != expected):
                unsupported("owned purpose differs from its retained execution or native association.")
            reference, config = options.get("purpose_ref"), options.get("purpose_config")
            if (not isinstance(reference, dict)
                    or set(reference) != {"owner", "store_id", "db_path", "chain_id", "source"}
                    or reference["owner"] != {"namespace": assignment["namespace"], "kind": "effort",
                                              "ordinal": assignment["effort_root"]}
                    or not isinstance(reference["chain_id"], str) or not reference["chain_id"].strip()):
                unsupported("invalid historical owned purpose reference.")
            if (not isinstance(config, dict)
                    or set(config) != {"namespace_path", "purposes_root", "legacy_db", "source"}
                    or config["namespace_path"] != assignment["namespace_path"]
                    or any(not isinstance(config[key], str) or not config[key]
                           for key in ("namespace_path", "purposes_root", "source"))
                    or (config["legacy_db"] is not None
                        and (not isinstance(config["legacy_db"], str) or not config["legacy_db"]))):
                unsupported("invalid historical purpose resolver configuration.")
            # Draft projection checks frozen ownership, without requiring the old native store/component.
            adapter = purpose_binding.Purposes(config["namespace_path"], purposes_root=config["purposes_root"],
                                               legacy_db=config["legacy_db"], source=config["source"])
            store = adapter._store(assignment["namespace"], assignment["effort_root"])
            if (purpose_binding.configuration(adapter) != config
                    or any(reference[key] != value for key, value in store.items())
                    or reference["source"] != config["source"]
                    or any(options.get(option) != reference[key]
                           for option, key in (("telos_chain", "chain_id"), ("telos_db", "db_path"), ("telos_source", "source")))
                    or governing.get("purpose_ref") != reference):
                unsupported("owned purpose disagrees with its historical resolver, Telos selection or governing input.")
            if any(event["kind"] == "telos.linked" and any(event["data"].get(key) != reference[key]
                    for key in ("chain_id", "db_path", "source")) for event in events):
                unsupported("native Telos association disagrees with the historical owned purpose.")
    except ApplicationError:
        raise
    except (OSError, KeyError, TypeError, ValueError, sqlite3.Error) as exc:
        unsupported(f"unreadable historical purpose binding: {exc}")
    sources = external["external.sources"]["content"]
    if not isinstance(sources, list) or any(
            not isinstance(source, dict) or set(source) != {"ref"}
            or not isinstance(source["ref"], str) or not source["ref"]
            or source["ref"] != source["ref"].strip() or any(c in source["ref"] for c in "\r\n\0")
            for source in sources):
        unsupported("only ref-only sources that round-trip exactly through one-reference-per-line are supported; rich sources/content are not flattened.")
    fields["sources"] = [source["ref"] for source in sources]
    warnings = [
        "Editable draft, not resumed/cloned. No execution or historical sessions/artifacts are copied.",
        "Launch uses the current built-in pattern, not a frozen historical pattern. This source matches the current definition.",
        "Workspace is a reference to its current contents, not a snapshot.",
        "Telos selection cleared. Choose a current purpose explicitly if wanted; the old governing snapshot and subgoal are not copied. Task text is unchanged, not rewritten to a new purpose.",
        "goal_ref is not copied.",
    ]
    if options.get("project") is not None:
        project = options["project"]
        if not isinstance(project, str) or not project.strip() or any(char in project for char in "\0\r\n") or not Path(project).is_absolute():
            unsupported("source project cannot round-trip through its folder field.")
        owned = options.get("owned_worktree")
        if owned is not None:
            base = options.get("workspace_base_commit")
            if (not isinstance(owned, str) or not Path(owned).is_absolute()
                    or not Path(state["workspace"]).is_relative_to(Path(owned))
                    or not isinstance(base, str) or len(base) not in (40, 64)
                    or any(char not in "0123456789abcdef" for char in base)):
                unsupported("owned task workspace metadata is inconsistent.")
            warnings.append(f"Prior task edits remain in {state['workspace']}. A new development task isolates the current source project again; it does not merge or copy prior task edits.")
        fields["workspace"] = project
    elif options.get("owned_worktree") is not None or options.get("workspace_base_commit") is not None:
        unsupported("owned task workspace has no recorded source project.")
    if fields["model"] is None:
        warnings.append("Main model was missing or null: left blank and unresolved. Choose a model before launch; no profile default was substituted.")
    if fields["qa_model"] is None:
        warnings.append("QA model was missing or null: left blank; normal launch inherits the selected main model.")
    return {"source_run_id": run.name, "source_telos_chain": chain, "fields": fields, "warnings": warnings}


def workspace_path(value, projects_root=None):
    try:
        return projects.prepare_project(value, create=True, projects_root=projects_root)
    except projects.ProjectError as exc:
        raise ApplicationError(exc.status, str(exc)) from exc


def record_project(run, project, owned=None):
    options = read_json(run / "options.json", run)
    options["project"] = str(project)
    if owned:
        options.update(owned_worktree=owned["owned_worktree"], workspace_base_commit=owned["base_commit"])
        with open_private(run / "project-baseline.json") as stream:
            stream.write(json.dumps({"project": str(project), "workspace": owned["workspace"],
                                     "files": owned["initial_files"], "selected_paths": owned["selected_paths"]}, ensure_ascii=True) + "\n")
    temporary = run / "options.json.tmp"
    with open_private(temporary) as stream:
        stream.write(json.dumps(options, ensure_ascii=True) + "\n")
    temporary.replace(run / "options.json")
    runtime.record(run, "application.project.prepared", {
        "project": str(project), "workspace": owned["workspace"] if owned else str(project),
        "owned_worktree": owned["owned_worktree"] if owned else None,
        "base_commit": owned["base_commit"] if owned else None,
        "excluded_paths": owned["excluded_paths"] if owned else [],
    })


class Application:
    def __init__(self, runs_dir, *, telos_db=None, telos_source=None, work_root=None, namespace_path=None, sessions_home=None, purposes_root=None, opermem_host=None):
        self.root = Path(runs_dir).resolve()
        self.telos_db = Path(telos_db or self.root.parent / "telos.sqlite3").resolve()
        self.telos_source = telos_source
        self.purposes_root = purposes_root
        self.opermem_host = opermem_host
        self.work_root = work_root
        self.namespace_path = Efforts(self.root, namespace_path=namespace_path).path
        self.sessions_home = Path(sessions_home or self.root).resolve()
        self.actions = threading.RLock()
        self.memory_lock = threading.Lock()
        self.health_lock = threading.Lock()
        self.health = None
        self.children = []

    def selection(self, values):
        effort = values.get("effort_root")
        mode = values.get("scope")
        if effort is not None:
            if mode not in (None, "effort"):
                raise ApplicationError(400, "Choose one effort or explicit application scope.")
            return {"kind": "effort", "effort_root": effort}
        if mode == "application":
            return {"kind": "application"}
        raise ApplicationError(400, "Choose an effort_root or explicit scope=application for retained global history.")

    def operation_scope(self, selection):
        try:
            with closing(sqlite3.connect(self.namespace_path.as_uri() + "?mode=ro", uri=True)) as db:
                metadata = dict(db.execute("SELECT key,value FROM metadata"))
                if metadata.get("schema") != "1" or not metadata.get("namespace"):
                    raise ScopeError("Application namespace is incomplete or unsupported")
                roots = tuple(row[0] for row in db.execute("SELECT ordinal FROM efforts ORDER BY ordinal"))
                if selection["kind"] == "effort":
                    root = selection["effort_root"]
                    if root not in roots:
                        raise ScopeError("Selected effort does not exist in this application namespace")
                    return Scope.effort(root)
                version = db.execute("SELECT mandate_version FROM positions WHERE ordinal='0'").fetchone()
                if version is None:
                    raise ScopeError("Application root mandate is unavailable")
                return Scope.application(roots, root_mandate_version=version[0])
        except (OSError, sqlite3.Error, ScopeError) as exc:
            raise ApplicationError(422, f"Cannot resolve application scope at {self.namespace_path}: {exc}") from exc

    def reviewed(self):
        return reviewed.ReviewedApplication(self)

    def run_authority(self, run, selection):
        contained(run, self.root)
        if self.namespace_path.exists():
            try:
                native = self.reviewed().authority(run.name, selection)
                if native is not None:
                    return native
                # A foreign assigned native run never reaches content inspection.
                if selection["kind"] == "effort" and self.reviewed().binding(run.name, {"kind": "application"}) is not None:
                    raise ApplicationError(403, "Requested effort does not own this run", run.name)
            except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                if isinstance(exc, ApplicationError):
                    raise
                raise ApplicationError(403, f"Owned reviewed correspondence unavailable: {exc}", run.name) from exc
        contained(run / "options.json", run)
        contained(run / "events.sqlite3", run)
        if selection["kind"] == "effort":
            self.operation_scope(selection)
        try:
            return disciplines.correspondence(run, namespace_path=self.namespace_path,
                                               effort_root=selection.get("effort_root"))
        except ScopeError as exc:
            raise ApplicationError(403, f"Run ownership cannot authorize this selection: {exc}", run.name) from exc

    def discipline_catalog(self, selection, *, after=0, limit=100):
        if type(after) is not int or not 0 <= after <= 9223372036854775807 or type(limit) is not int or not 1 <= limit <= 1000:
            raise ApplicationError(400, "Catalog after must be between 0 and 9223372036854775807 and limit must be between 1 and 1000.")
        definitions = []
        for pattern in ("cognition", "development"):
            data = json.loads((controller.PATTERN_DIR / f"{pattern}.json").read_text(encoding="utf-8"))
            reference = {"id": f"noetic:{pattern}",
                         "version": hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=True,
                                                              allow_nan=False).encode()).hexdigest(),
                         "pattern_version": data["version"]}
            definitions.append({"pattern": pattern, "definition_ref": reference, "definition": data})
        definitions.append(reviewed.catalog_definition())
        result = {"namespace_path": str(self.namespace_path), "namespace_registered": False,
                  "namespace_id": None, "selection": selection, "definitions": definitions,
                  "instances": [], "after": after, "limit": limit, "next_after": None}
        if selection["kind"] == "application" and not self.namespace_path.exists():
            return result
        scope = self.operation_scope(selection)
        try:
            store = disciplines.Disciplines(self.namespace_path, readonly=True).store
            with store._read() as db:
                store._scope(db, store._position(db, scope.effort_root or "0"), scope)
                roots = (scope.effort_root,) if scope.effort_root else scope.target_efforts
                if roots:
                    placeholders = ",".join("?" for _ in roots)
                    rows = db.execute(f"SELECT id FROM disciplines WHERE effort IN ({placeholders}) AND id>? ORDER BY id LIMIT ?",
                                      (*roots, after, limit + 1)).fetchall()
                    for row in rows[:limit]:
                        instance = store._discipline(db, row[0])
                        executions = [store._execution(db, execution[0]) for execution in db.execute(
                            "SELECT id FROM executions WHERE discipline_id=? ORDER BY id", (instance["id"],))]
                        result["instances"].append({**instance, "executions": executions})
                    if len(rows) > limit:
                        result["next_after"] = result["instances"][-1]["id"]
                result.update(namespace_registered=True, namespace_id=store.namespace)
            return result
        except (OSError, sqlite3.Error, ScopeError) as exc:
            raise ApplicationError(422, f"Cannot read discipline catalog: {exc}") from exc

    def create_discipline(self, body):
        if body.get("backend", body.get("pattern")) == reviewed.BACKEND:
            return self.reviewed().create(body)
        allowed = {"command_id", "effort_root", "initiator", "pattern", "intent", "environment", "initiating_target", "parent_instance"}
        required = {"command_id", "effort_root", "initiator", "pattern", "intent", "environment"}
        if set(body) - allowed or not required <= set(body):
            raise ApplicationError(400, "Discipline requires its command, existing effort, initiator, maintained pattern, intent and environment.")
        scope = self.operation_scope({"kind": "effort", "effort_root": body["effort_root"]})
        try:
            store = disciplines.Disciplines(self.namespace_path, readonly=True).store
            initiator = store.position(body["initiator"], scope=scope)
            owner = store.position(body["effort_root"], scope=scope)
            if initiator["status"] != "open" or owner["environment"] != body["environment"]:
                raise ScopeError("Discipline requires an open initiating position and the owning effort's exact environment")
            if body.get("initiating_target") is not None:
                if store.resolve(body["initiator"], scope=scope).as_dict() != body["initiating_target"]:
                    raise ScopeError("Discipline initiating target is stale or belongs to another position")
            if body.get("parent_instance") is not None:
                store.discipline(body["parent_instance"], scope=scope)
                if initiator["discipline_id"] != body["parent_instance"]:
                    raise ScopeError("Nested discipline requires an actual parent-instance participant")
            disciplines.definition(body["pattern"])
            if not isinstance(body["intent"], str) or not body["intent"].strip() or "\0" in body["intent"]:
                raise ScopeError("Discipline intent must be nonempty text")
            if not isinstance(body["command_id"], str) or not body["command_id"].strip():
                raise ScopeError("Discipline command_id must be nonempty text")
            return {"discipline": disciplines.Disciplines(self.namespace_path).create_instance(**body)}
        except (ScopeError, KeyError, TypeError) as exc:
            raise ApplicationError(422, f"Cannot instantiate discipline: {exc}") from exc

    def collect(self, selection):
        try:
            self.check_sources()
            return recall.collect(namespace_path=self.namespace_path, sessions_home=self.sessions_home,
                                  runs_dir=self.root, selection=selection)
        except ScopeError as exc:
            raise ApplicationError(422, f"Cannot collect selected recall sources: {exc}") from exc

    def source_preparation(self, *, selection, registry_id, native_session_id, sequence, source_text_sha256):
        """Read one exact retained assistant answer as its one qualified collector source."""
        def refuse(status, message):
            raise ApplicationError(status, message)
        if not isinstance(selection, dict) or selection.get("kind") != "session":
            refuse(400, "Source preparation requires an exact session selection; broader scopes are not supported.")
        ordinal = selection.get("ordinal")
        if not isinstance(ordinal, str) or not re.fullmatch(r"0(?:\.[0-9]+)*", ordinal):
            refuse(400, "Source preparation requires a valid exact ordinal selector.")
        for name, value in (("instantiation", selection.get("instantiation")), ("session", selection.get("session")), ("sequence", sequence)):
            if type(value) is not int or value < 1:
                refuse(400, f"Source preparation requires a complete positive integer {name}.")
        effort_root = selection.get("effort_root")
        if not isinstance(effort_root, str) or not effort_root.strip():
            refuse(400, "Source preparation requires an explicit effort_root.")
        for name, value in (("registry_id", registry_id), ("native_session_id", native_session_id)):
            if not isinstance(value, str) or not value.strip():
                refuse(400, f"Source preparation requires a nonempty {name}.")
        if not isinstance(source_text_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", source_text_sha256):
            refuse(400, "Source preparation requires an exact lowercase 64-character expected source digest.")
        from scripts import noetic_sessions as native_sessions
        service = native_sessions.SessionService(self.sessions_home, namespace_path=self.namespace_path)
        target = {"ordinal": ordinal, "instantiation": selection["instantiation"], "session": selection["session"]}
        item = service.select(target, effort_root=effort_root, current=False)
        if (item["id"] != registry_id or item["native_session_id"] != native_session_id
                or item["target"] != target or item["effort_root"] != effort_root):
            refuse(409, "Selected context does not match the observed registry, native identity, exact target or owning effort; no source prepared.")
        rows = service.registry.events(item["id"], after=sequence - 1, limit=1)
        if len(rows) != 1 or rows[0]["sequence"] != sequence:
            refuse(404, "Exact retained event was not observed; no source prepared.")
        record = rows[0]["record"]
        message = record.get("message") if isinstance(record, dict) else None
        if (not isinstance(record, dict) or record.get("type") != "message_end" or not isinstance(message, dict) or message.get("role") != "assistant"
                or message.get("errorMessage") or message.get("stopReason") in ("error", "aborted")):
            refuse(415, "Retained event is not a supported completed assistant answer; no source prepared.")
        content = message.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    if not isinstance(block.get("text"), str):
                        refuse(415, "Retained assistant answer carries an unsupported text block; no source prepared.")
                    parts.append(block["text"])
            text = "\n".join(parts)
        else:
            text = ""
        if not text:
            refuse(415, "Retained assistant answer carries no supported complete text; no source prepared.")
        try:
            collection = self.collect(dict(selection))
        except ApplicationError as exc:
            raise ApplicationError(exc.status, f"Cannot collect the selected exact source: {exc}") from exc
        matches = [source for source in collection.get("sources", [])
                   if source.get("field") == "developer-conversation" and source.get("disposition") == "retained-message"
                   and source.get("source") == "message_end" and source.get("registry_id") == item["id"]
                   and source.get("source_ref", {}).get("session_id") == item["id"]
                   and source.get("source_ref", {}).get("native_session_id") == native_session_id
                   and source.get("source_ref", {}).get("sequence") == sequence
                   and source.get("target") == item["target"] and source.get("effort_root") == effort_root
                   and source.get("ownership") == "assigned"]
        if len(matches) != 1:
            refuse(409, "Exact collector source is missing or ambiguous; no source prepared.")
        source = matches[0]
        if source.get("source_text_sha256") != source_text_sha256:
            refuse(409, "Expected source digest does not match the retained collector source; no source prepared.")
        if source.get("text") != text:
            refuse(409, "Retained event text does not equal the collected source text; no source prepared.")
        return {"source": source}

    def lexical(self, query, selection, limit=20):
        if not isinstance(query, str) or not query.strip():
            raise ApplicationError(400, "Enter an explicit lexical query.")
        collection = self.collect(selection)
        with closing(sqlite3.connect(":memory:")) as connection:
            index = memory.index_scoped(connection, collection)
            return {**memory.search_scoped(connection, query, identity=collection["identity"], limit=limit), "index": index}

    @contextmanager
    def mutation(self):
        with self.actions:
            ensure_private_directory(self.root)
            with open_private(self.root / ".application.lock", "a") as stream:
                fcntl.flock(stream, fcntl.LOCK_EX)
                yield

    def project_for_run(self, run, state):
        options = read_json(run / "options.json", run, {})
        return Path(options.get("project") or state["workspace"]).resolve()

    def check_workspace(self, workspace, except_run=None):
        for run in self.root.iterdir():
            if run == except_run or not run.is_dir():
                continue
            store = run / "controller.sqlite3"
            if not store.exists():
                continue
            contained(store, self.root)
            state = controller.inspect_run(store)
            if self.project_for_run(run, state) == workspace and state["status"] == "active":
                raise ApplicationError(409, f"Workspace already has active pattern {run.name}; advance or cancel that run first.", run.name)

    @contextmanager
    def admission(self, run_id=None):
        try:
            with harness.driver_slot(self.root) as slot:
                yield slot
        except harness.CapacityBusy as exc:
            raise ApplicationError(409, str(exc), run_id) from exc

    def start(self, body):
        if body.get("backend", body.get("pattern")) == reviewed.BACKEND:
            return self.reviewed().start(body)
        allowed = {"pattern", "task", "workspace", "sources", "verify", "client", "model", "qa_model", "thinking",
                   "max_returns", "max_remediations", "timeout", "projects_root", "effort_root", "discipline_id",
                   "origin", "human_ref", "delegator", "environment", "purpose_ref"}
        if set(body) - allowed:
            raise ApplicationError(400, "Unknown new-run option.")
        if not isinstance(body.get("workspace"), str) or not body["workspace"].strip():
            raise ApplicationError(400, "Choose a project folder.")
        task = body.get("task")
        if not isinstance(task, str) or not task.strip():
            raise ApplicationError(400, "Task text is required.")
        pattern = body.get("pattern", "development")
        if pattern not in ("development", "cognition") or body.get("client", "pi") not in ("pi", "opencode"):
            raise ApplicationError(400, "Select development/cognition and Pi/OpenCode.")
        verify = body.get("verify")
        if verify is not None and (not isinstance(verify, list) or not verify or any(not isinstance(arg, str) or "\0" in arg for arg in verify)):
            raise ApplicationError(400, "Verification must be a nonempty JSON argv array or null, not shell syntax.")
        for key in ("max_returns", "max_remediations"):
            if type(body.get(key, 1)) is not int or not 0 <= body.get(key, 1) <= 20:
                raise ApplicationError(400, f"{key} must be an integer from 0 to 20.")
        timeout = body.get("timeout", 900)
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 1 <= timeout <= 7200:
            raise ApplicationError(400, "Timeout must be 1 to 7200 seconds per command.")
        for key in ("model", "qa_model", "thinking", "telos_chain"):
            if body.get(key) is not None and (not isinstance(body[key], str) or "\0" in body[key]):
                raise ApplicationError(400, f"{key} must be text.")
        try:
            model_options = model_defaults.new_options(**{key: body.get(key) for key in ("client", "model", "qa_model", "thinking")})
        except ValueError as exc:
            raise ApplicationError(400, f"Cannot select new-run model defaults: {exc}") from exc
        sources = body.get("sources", [])
        if not isinstance(sources, list) or any(not isinstance(ref, str) or not ref.strip() for ref in sources):
            raise ApplicationError(400, "Source references must be an array of nonempty strings; no implicit file ingestion.")
        if body.get("projects_root") is not None and (not isinstance(body["projects_root"], str) or not body["projects_root"].strip()):
            raise ApplicationError(400, "Choose an absolute projects location.")
        selection = self.selection(body)
        scope = self.operation_scope(selection)
        if selection["kind"] != "effort" or "discipline_id" not in body:
            raise ApplicationError(400, "New structured work requires an existing effort and discipline instance.")
        scope_request = {key: body[key] for key in ("effort_root", "discipline_id", "origin", "human_ref", "delegator", "environment") if key in body}
        scope_request["namespace_path"] = str(self.namespace_path)
        try:
            project = projects._directory(body["workspace"], body.get("projects_root"))
        except projects.ProjectError as exc:
            raise ApplicationError(exc.status, str(exc)) from exc
        try:
            disciplines.Disciplines(self.namespace_path, readonly=True).validate(scope_request, pattern, project)
        except (ScopeError, KeyError, TypeError) as exc:
            raise ApplicationError(422, f"Cannot start selected discipline: {exc}") from exc
        resolver = self.purposes() if body.get("purpose_ref") is not None else None
        purpose = resolver.resolve_run(body["purpose_ref"], scope=scope) if resolver else None
        kwargs = {key: body[key] for key in ("pattern", "verify", "client", "model", "qa_model", "thinking", "max_returns", "max_remediations", "timeout") if key in body}
        kwargs.update(model_options)
        kwargs.update(pattern=pattern, task=task,
                      runs_dir=self.root, max_activations=0, inputs={"sources": [{"ref": ref} for ref in sources]},
                      telos_db=purpose["db_path"] if purpose else self.telos_db,
                      telos_source=purpose["source"] if purpose else self.telos_source, scope_request=scope_request)
        if purpose:
            kwargs["telos_chain"] = purpose["chain_id"]
            kwargs["purpose_ref"] = purpose["purpose_ref"]
            kwargs["purpose_config"] = purpose_binding.configuration(resolver)
        with self.mutation(), self.admission() as slot:
            project = workspace_path(body["workspace"], body.get("projects_root"))
            self.check_workspace(project)
            owned = None
            if pattern == "development":
                excluded = (self.root.parent,) if self.root.parent.name == ".runtime" else (self.root,)
                try:
                    owned = projects.task_worktree(project, work_root=self.work_root, exclude=excluded)
                except projects.ProjectError as exc:
                    raise ApplicationError(exc.status, str(exc)) from exc
            if owned:
                kwargs["scope_request"] = {**scope_request, "preparation": owned}
            kwargs["workspace"] = Path(owned["workspace"]) if owned else project
            prior = set(self.root.iterdir())
            try:
                run, state = harness.start(**kwargs)
                record_project(run, project, owned)
            except Exception as exc:
                created = [p for p in set(self.root.iterdir()) - prior if p.is_dir() and (p / "events.sqlite3").is_file()]
                for run in created:
                    if (run / "options.json").is_file():
                        record_project(run, project, owned)
                    write_driver(run, {"status": "failed", "error": str(exc)[:2000], "finished_at": now()})
                raise ApplicationError(422, f"Pattern creation failed: {exc}", created[0].name if created else None) from exc
            return self._launch(run, state, None, slot)

    def advance(self, run, body, *, selection):
        self.run_authority(run, selection)
        if body not in ({"mode": "one"}, {"mode": "all"}):
            raise ApplicationError(400, 'Advance requires {"mode":"one"} or {"mode":"all"}.')
        with self.mutation():
            state = controller.inspect_run(contained(run / "controller.sqlite3", run))
            info = runtime_info(run, state)
            if not info["can_advance"]:
                raise ApplicationError(409, info["reason"])
            self.check_workspace(self.project_for_run(run, state), run)
            with self.admission(run.name) as slot:
                harness.resume(run)
                return self._launch(run, state, 1 if body["mode"] == "one" else None, slot)

    def _launch(self, run, state, maximum, slot):
        if state["status"] != "active":
            raise ApplicationError(409, "Pattern is already terminal.", run.name)
        lock = open_private(run / "application-driver.lock", "a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            write_driver(run, {"status": "requested", "requested_at": now(), "max_activations": maximum})
            environment = os.environ.copy()
            environment.pop("USER_PROVIDED_PASSWORD", None)
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            with open_private(run / "application-driver.log", "ab") as output:
                child = subprocess.Popen(
                    [sys.executable, "-B", "-m", "scripts.noetic_application", "drive", str(run),
                     "all" if maximum is None else str(maximum), str(lock.fileno()), str(slot.fileno())],
                    cwd=Path(__file__).resolve().parents[1], env=environment, stdin=subprocess.DEVNULL,
                    stdout=output, stderr=output, start_new_session=True, pass_fds=(lock.fileno(), slot.fileno()))
            self.children = [p for p in self.children if p.poll() is None] + [child]
            # Reap without tying driver lifetime to the HTTP process.
            threading.Thread(target=child.wait, daemon=True).start()
        except (OSError, ValueError) as exc:
            write_driver(run, {"status": "failed", "error": f"Driver could not start: {exc}", "finished_at": now()})
            raise ApplicationError(422, f"Driver could not start: {exc}", run.name) from exc
        finally:
            lock.close()
        return {"run_id": run.name, "controller": state, "action": "advance", "status": "requested",
                "message": "Independent driver launched. Reconnect to observe its lock, checkpoint or error.", "pid": child.pid}

    def project_changes(self, run, *, selection):
        self.run_authority(run, selection)
        options = read_json(run / "options.json", run, {})
        state = controller.inspect_run(contained(run / "controller.sqlite3", run))
        project = Path(options.get("project") or state["workspace"]).resolve()
        workspace = Path(state["workspace"]).resolve()
        receipt = read_json(run / "project-apply.json", run, {})
        result = {"run_id": run.name, "project": str(project), "workspace": str(workspace),
                  "owned_worktree": options.get("owned_worktree"), "eligible": False,
                  "applied": receipt.get("status") == "applied", "reason": "", "changes": [], "verification": []}
        def refuse(reason):
            result["reason"] = reason
            return result
        if not options.get("owned_worktree"):
            return refuse("This run has no controller-owned development workspace.")
        if state["pattern"]["kind"] != "verified_sequence" or state["status"] != "completed":
            return refuse("Only independently reviewed completed development work can be applied.")
        info = runtime_info(run, state)
        if info["gui_driver_owned"] or info["harness_driver_owned"] or not info["cleanup_confirmed"]:
            return refuse("Task process cleanup is unconfirmed; retained work remains available.")
        subject_id = state["slots"].get("accepted.implementation")
        subject = state["artifacts"].get(subject_id)
        reviews = [item for item in state["artifacts"].values() if item["type"] == "qa.review"
                   and item["content"].get("subject_artifact_id") == subject_id and item["content"].get("verdict") == "pass"]
        if not subject or not reviews:
            return refuse("A subject-specific independent implementation review is required.")
        result["summary"] = subject["content"].get("report", "")
        result["review"] = {"verdict": "pass", "report": reviews[-1]["content"]["report"], "activation_id": reviews[-1]["activation_id"]}
        verification = subject["content"].get("verification", [])
        if not verification or any(item.get("state") != "passed" or item.get("returncode") != 0 or not item.get("argv") for item in verification):
            return refuse("A successfully executed host check is required before applying work.")
        recorded = read_json(run / "activations" / subject["activation_id"] / "verify-process.json", run)
        if recorded not in verification:
            return refuse("Retained verification process evidence does not match the accepted implementation.")
        result["verification"] = verification
        result["test_instructions"] = [{"argv": item["argv"], "cwd": str(project)} for item in verification]
        if result["applied"]:
            result["changes"] = receipt.get("changes", [])
            return refuse("Reviewed changes were already applied; retained task files remain available.")
        baseline = read_json(run / "project-baseline.json", run)
        if not baseline or baseline.get("project") != str(project) or baseline.get("workspace") != str(workspace):
            return refuse("The original project baseline is unavailable; task files remain retained for review.")
        before = baseline["files"]
        try:
            names = set(baseline["selected_paths"]) | set(projects.selected_paths(workspace))
            current = {name: projects.fingerprint(workspace / name) for name in names}
            changed = {name for name in names if before.get(name) != current[name]}
            approved = {item["path"]: item for item in subject["content"].get("changes", [])}
            for name in sorted(changed):
                relative = Path(name)
                if relative.is_absolute() or any(part in ("..", ".git") for part in relative.parts):
                    return refuse(f"Unsupported task path: {name}. Retained task files were preserved.")
                old, new = before.get(name), current[name]
                result["changes"].append({"path": name, "status": "added" if old is None else "deleted" if new is None else "modified",
                                          "task_path": str(workspace / name), "project_path": str(project / name), "after": new})
                if any(item and item["kind"] != "file" for item in (old, new)):
                    return refuse(f"Apply supports ordinary files only: {name}. Retained task work was preserved.")
                artifact = approved.get(name)
                if not artifact:
                    return refuse(f"Task file changed without accepted implementation evidence: {name}.")
                for key, fingerprint in (("before", old), ("after", new)):
                    saved = artifact.get(key)
                    saved = {field: saved[field] for field in ("kind", "sha256", "mode")} if saved else None
                    if saved != fingerprint:
                        return refuse(f"Task file differs from independently reviewed content: {name}.")
                target = project / name
                if any(parent.is_symlink() or (parent.exists() and not parent.is_dir()) for parent in target.parents if parent != project and parent.is_relative_to(project)):
                    return refuse(f"Source parent path changed or is unsupported: {name}.")
                if projects.fingerprint(target) != old:
                    return refuse(f"Source file changed since task preparation: {name}. Both source and task work were preserved.")
        except (OSError, projects.ProjectError) as exc:
            return refuse(f"Cannot inspect retained project changes: {exc}")
        if not result["changes"]:
            return refuse("No reviewed source file changes to apply.")
        result.update(eligible=True, reason="Reviewed source changes can be applied explicitly; source branch and index are preserved.")
        return result

    def apply_changes(self, run, body, *, selection):
        self.run_authority(run, selection)
        if body != {"confirm": True} or type(body.get("confirm")) is not bool:
            raise ApplicationError(400, 'Apply requires {"confirm":true}.')
        with self.mutation():
            result = self.project_changes(run, selection=selection)
            if not result["eligible"]:
                raise ApplicationError(409, result["reason"], run.name)
            project, workspace = Path(result["project"]), Path(result["workspace"])
            self.check_workspace(project, run)
            baseline = read_json(run / "project-baseline.json", run)["files"]
            backup = Path(result["owned_worktree"]).with_name(Path(result["owned_worktree"]).name + "-apply-" + uuid.uuid4().hex)
            ensure_private_directory(backup)
            applied = []
            try:
                for change in result["changes"]:
                    name = change["path"]
                    target = project / name
                    saved = backup / name
                    if projects.fingerprint(target) != baseline.get(name):
                        raise ApplicationError(409, f"Source file changed before apply: {name}.", run.name)
                    if target.exists():
                        saved.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(target, saved)
                        if projects.fingerprint(saved) != baseline.get(name):
                            raise ApplicationError(409, f"Source file changed while backing up: {name}.", run.name)
                for change in result["changes"]:
                    name = change["path"]
                    target = project / name
                    if any(parent.is_symlink() or (parent.exists() and not parent.is_dir()) for parent in target.parents if parent != project and parent.is_relative_to(project)):
                        raise ApplicationError(409, f"Source parent path changed during apply: {name}.", run.name)
                    if projects.fingerprint(target) != baseline.get(name):
                        raise ApplicationError(409, f"Source file changed during apply: {name}.", run.name)
                    if projects.fingerprint(workspace / name) != change["after"]:
                        raise ApplicationError(409, f"Task file changed during apply: {name}.", run.name)
                    if change["status"] == "deleted":
                        target.unlink()
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        temporary = target.with_name(target.name + ".noetic-apply-" + uuid.uuid4().hex)
                        try:
                            shutil.copy2(workspace / name, temporary)
                            if projects.fingerprint(temporary) != change["after"]:
                                raise ApplicationError(409, f"Task file changed while copying: {name}.", run.name)
                            if projects.fingerprint(target) != baseline.get(name):
                                raise ApplicationError(409, f"Source file changed while copying: {name}.", run.name)
                            temporary.replace(target)
                        finally:
                            temporary.unlink(missing_ok=True)
                    applied.append((change, change["after"]))
            except (OSError, ApplicationError) as exc:
                restored = []
                restore_errors = []
                for change, fingerprint in reversed(applied):
                    target = project / change["path"]
                    try:
                        if projects.fingerprint(target) != fingerprint:
                            continue
                        saved = backup / change["path"]
                        if saved.exists():
                            shutil.copy2(saved, target)
                        else:
                            target.unlink(missing_ok=True)
                        restored.append(change["path"])
                    except OSError as restore_exc:
                        restore_errors.append({"path": change["path"], "error": str(restore_exc)})
                with open_private(run / "project-apply.json") as stream:
                    stream.write(json.dumps({"status": "failed", "error": str(exc), "backup": str(backup),
                                             "restored_paths": restored, "restore_errors": restore_errors}) + "\n")
                raise ApplicationError(409, f"Apply failed: {exc}. Task work and source backups remain at {backup}.", run.name) from exc
            receipt = {"status": "applied", "applied_at": now(), "changes": result["changes"], "backup": str(backup)}
            with open_private(run / "project-apply.json") as stream:
                stream.write(json.dumps(receipt) + "\n")
            runtime.record(run, "application.project.applied", receipt)
            return {**result, "eligible": False, "applied": True, "message": f"Applied {len(applied)} reviewed file changes to {project}. Task work remains retained.", "backup": str(backup)}

    def purposes(self):
        try:
            from scripts.noetic_purposes import Purposes
        except ImportError as exc:
            raise ApplicationError(503, "Effort purpose adapter is unavailable in this source installation.") from exc
        return Purposes(self.namespace_path, purposes_root=self.purposes_root, legacy_db=self.telos_db, source=self.telos_source)

    def goals(self, selection, *, include_legacy=False):
        if selection["kind"] == "application" and not self.namespace_path.exists():
            return {**self.purposes().list_unassigned(), "namespace_path": str(self.namespace_path),
                    "namespace_registered": False}
        return self.purposes().list(scope=self.operation_scope(selection), include_legacy=include_legacy)

    def create_goal(self, body):
        allowed = {"goal", "scope", "effort_root", "owner", "origin_ref", "source_ref"}
        if set(body) - allowed or not isinstance(body.get("goal"), str) or not body["goal"].strip():
            raise ApplicationError(400, "A nonempty goal and explicit owning scope are required.")
        scope = self.operation_scope(self.selection(body))
        return {"purpose": self.purposes().create(body["goal"], scope=scope, owner=body.get("owner"),
                                                 origin_ref=body.get("origin_ref"), source_ref=body.get("source_ref"))}

    def check_sources(self):
        # Collectors are local-library APIs, so enforce the HTTP scope before calling them.
        if not self.root.exists():
            return
        for run in self.root.iterdir():
            if not run.is_dir():
                continue
            contained(run, self.root)
            for name in ("controller.sqlite3", "events.sqlite3", "work.md", "review.md"):
                contained(run / name, run)

    def memory(self, body):
        if set(body) - {"query", "limit", "reindex", "selection", "scope", "effort_root"} or not isinstance(body.get("query"), str) or not body["query"].strip():
            raise ApplicationError(400, "Enter an explicit semantic query and scope.")
        if type(body.get("reindex", False)) is not bool:
            raise ApplicationError(400, "reindex must be boolean.")
        if type(body.get("limit", 20)) is not int or not 1 <= body.get("limit", 20) <= 100:
            raise ApplicationError(400, "Semantic limit must be 1 to 100.")
        if "selection" in body and {"scope", "effort_root"} & body.keys():
            raise ApplicationError(400, "Use one recall selection.")
        selection = body["selection"] if "selection" in body else self.selection(body)
        with self.memory_lock:
            collection = self.collect(selection)
            client = local.LocalClient(local.load_settings())
            key = hashlib.sha256(local.canonical(collection["identity"]).encode()).hexdigest()
            cache = contained(self.root / f".semantic-{key}.sqlite3", self.root)
            with closing(sqlite3.connect(create_private_sqlite(cache), timeout=5)) as connection:
                index = semantic.index_scoped(connection, collection, client, reindex=body.get("reindex", False))
                results = semantic.search(connection, body["query"], client, body.get("limit", 20), identity=collection["identity"])
            return {"index": index, "results": results, "cache": str(cache), "authoritative": False,
                    **{key: collection[key] for key in ("identity", "selection", "coverage", "diagnostics", "status")},
                    "notice": "Derived semantic relevance, not truth or QA. No lexical fallback."}

    def summary(self, run, body, *, selection):
        self.run_authority(run, selection)
        if set(body) - {"save"} or type(body.get("save", False)) is not bool:
            raise ApplicationError(400, "Summary accepts only boolean save.")
        self.check_sources()
        contained(run / "summary.json", run)
        return local.summarize_run(run, local.LocalClient(local.load_settings()), save=body.get("save", False))

    def configuration(self):
        settings = asdict(local.load_settings())
        try:
            product = model_defaults.product_configuration()
        except ValueError as exc:
            raise ApplicationError(400, f"Cannot read installation model defaults: {exc}") from exc
        notice = "Installation model defaults apply to new untouched preparation; explicit choices and retained work keep their selected models. Registration is not a live availability observation." if product["configured"] else "Sol 6.1 direct starter selections; configured inventories have no Sol 6.1 LiteLLM alias. Use Custom client/model for an explicitly configured route. Selections are not proof of current authentication or availability."
        return {"profiles": product["profiles"] + PROFILES, "product_models": product, "profile_notice": notice,
                "limits": {"max_returns": 20, "max_remediations": 20, "timeout_seconds": [1, 7200],
                           "pi_astra_configured_context": 272000, "pi_astra_configured_max_output": 128000},
                "role_defaults": {"producer": "selected model", "cognitive_operator": "selected model",
                                  "independent_qa": "QA model, or selected model when empty", "thinking": product["default"]["thinking"] if product["configured"] else "high",
                                  "context": "Fresh frozen role context per activation; no interactive chat input."},
                "opermem": reviewed.host_configuration(self.opermem_host),
                "local": settings, "telos_database": str(self.telos_db), "namespace_path": str(self.namespace_path),
                "driver_lifetime": "Independent Python process survives browser/server closure; reconnect to the same runs directory. No automatic restart of interrupted actors."}

    def diagnostics(self, refresh=False):
        with self.health_lock:
            if refresh:
                rows = []
                opener = request.build_opener(request.ProxyHandler({}), local._NoRedirect())
                for name, url in HEALTH_ENDPOINTS.items():
                    row = {"name": name, "url": url, "observed_at": now()}
                    try:
                        with opener.open(url, timeout=2) as response:
                            row.update(available=response.status == 200, http_status=response.status)
                            if name == "Ollama":
                                data = json.loads(response.read(64 * 1024))
                                row["loaded_models"] = [{key: model.get(key) for key in ("name", "model", "size", "size_vram", "expires_at")}
                                                        for model in data.get("models", [])]
                    except (OSError, ValueError, TypeError, AttributeError, error.URLError, local.LocalError):
                        row.update(available=False, error="Health endpoint unavailable or unreadable; no inference attempted.")
                    rows.append(row)
                self.health = {"services": rows, "observed_at": now(), "inference": False}
            return self.health or {"services": [], "observed_at": None, "notice": "Not checked. Refresh explicitly; no model calls populate this view."}


def transcript(text, client):
    """Normalize bounded Pi/OpenCode JSONL observations; never infer a session result."""
    entries, models, sessions = [], [], []
    malformed = 0
    for line in text.splitlines():
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError()
        except ValueError:
            malformed += 1
            continue
        kind = event.get("type", "unknown")
        message = event.get("message", {})
        part = event.get("part", {})
        timestamp = event.get("timestamp") or message.get("timestamp") or part.get("time", {}).get("start")
        session = event.get("sessionID") or (event.get("id") if kind == "session" else None)
        if session and session not in sessions:
            sessions.append(session)
        for candidate in (event, message, part):
            model = candidate.get("model") or candidate.get("modelID")
            provider = candidate.get("provider") or candidate.get("providerID")
            if isinstance(model, dict):
                provider, model = model.get("providerID"), model.get("modelID")
            if model or provider:
                identity = {"model": model, "provider": provider}
                if identity not in models:
                    models.append(identity)
        value, category = None, kind
        if client == "pi":
            if kind in ("message_end", "message_start") and message.get("role") == "assistant":
                pieces = [p.get("text", "") for p in message.get("content", []) if p.get("type") == "text"]
                value, category = "\n".join(pieces), "assistant"
            elif kind == "message_update":
                delta = event.get("assistantMessageEvent", {})
                if delta.get("type") == "text_delta":
                    value, category = delta.get("delta"), "assistant_delta"
            elif kind.startswith("tool_execution_"):
                value = {key: event[key] for key in ("toolName", "toolCallId", "args", "result", "partialResult", "isError") if key in event}
                category = "tool"
            elif kind == "agent_end":
                messages = [m for m in event.get("messages", []) if m.get("role") == "assistant"]
                value = {"willRetry": event.get("willRetry", False), "final": messages[-1] if messages else None}
                category = "final"
        else:
            if kind == "text":
                value, category = part.get("text"), "assistant"
            elif kind == "tool_use":
                value, category = {key: part[key] for key in ("tool", "callID", "state") if key in part}, "tool"
            elif kind == "step_finish":
                value, category = {key: part[key] for key in ("reason", "tokens", "cost") if key in part}, "step_finished"
        if kind == "error":
            value, category = event.get("error", event), "error"
        if value is not None:
            if category == "assistant_delta" and entries and entries[-1]["kind"] == category:
                entries[-1]["content"] += value
            else:
                entries.append({"index": len(entries), "kind": category, "event_type": kind, "timestamp": timestamp, "content": value})
    return {"entries": entries, "observed_models": models, "observed_sessions": sessions,
            "unparsed_lines": malformed, "notice": "Transcript observations, not controller authority. Partial/unrecognized lines remain in the raw log."}


def driver_main(run, maximum, lock_fd, slot_fd):
    run = Path(run).resolve()
    os.environ.pop("USER_PROVIDED_PASSWORD", None)
    with os.fdopen(lock_fd, "a"), os.fdopen(slot_fd, "a") as slot:
        started = now()
        write_driver(run, {"status": "running", "pid": os.getpid(), "started_at": started, "max_activations": maximum})
        try:
            _, state = harness.drive(run, maximum, _slot=slot)
            write_driver(run, {"status": "held" if state["status"] == "active" else state["status"], "pid": os.getpid(),
                               "started_at": started, "finished_at": now(), "controller_version": state["version"],
                               "max_activations": maximum})
            return 0
        except Exception as exc:
            write_driver(run, {"status": "failed", "pid": os.getpid(), "started_at": started,
                               "finished_at": now(), "error": f"{type(exc).__name__}: {exc}"[:2000]})
            return 1


if __name__ == "__main__":
    if len(sys.argv) != 6 or sys.argv[1] != "drive":
        raise SystemExit("Internal driver entrypoint: drive RUN all|COUNT LOCK_FD SLOT_FD")
    raise SystemExit(driver_main(sys.argv[2], None if sys.argv[3] == "all" else int(sys.argv[3]),
                                int(sys.argv[4]), int(sys.argv[5])))
