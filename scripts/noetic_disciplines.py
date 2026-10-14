"""Correlate maintained controller occurrences with the canonical ordinal domain."""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import noetic_controller as controller
from scripts import noetic_projects as projects
from scripts.noetic_scope import Scope, ScopeError, ScopeStore, Target
from scripts.noetic_storage import create_private_sqlite


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)


def definition(pattern):
    if pattern not in {"cognition", "development"}:
        raise ScopeError("Only maintained cognition/development definitions are executable")
    data = json.loads((controller.PATTERN_DIR / f"{pattern}.json").read_text())
    return {"id": f"noetic:{pattern}", "version": hashlib.sha256(_json(data).encode()).hexdigest(),
            "pattern_version": data["version"]}


class _ReadOnlyScopeStore(ScopeStore):
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve(strict=True)
        with self._connection() as db:
            metadata = dict(db.execute("SELECT key,value FROM metadata"))
            if metadata.get("schema") != "1" or not metadata.get("namespace"):
                raise ScopeError("Application namespace is incomplete or unsupported")
            self.namespace = metadata["namespace"]

    @contextmanager
    def _connection(self):
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, isolation_level=None)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            yield db

    @contextmanager
    def _write(self):
        raise ScopeError("Read-only scope validation cannot perform a domain mutation")
        yield


class Disciplines:
    def __init__(self, namespace_path, *, readonly=False):
        self.path = Path(namespace_path).expanduser().resolve(strict=True)
        self.readonly = readonly
        self.store = _ReadOnlyScopeStore(self.path) if readonly else ScopeStore(self.path)
        self.cache = self.path.with_name(self.path.name + ".correlation.sqlite3")
        if readonly:
            return
        with closing(sqlite3.connect(create_private_sqlite(self.cache))) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS commands (key TEXT PRIMARY KEY, request TEXT NOT NULL, response TEXT NOT NULL)")

    def _source(self, key, request):
        return {"adapter": "structured-disciplines", "namespace": self.store.namespace,
                "command_key": key, "request_digest": hashlib.sha256(_json(request).encode()).hexdigest()}

    def _event_for(self, key):
        after = 0
        while True:
            page = self.store.history(after=after, limit=1000)
            if not page["records"]:
                return None
            for event in page["records"]:
                source = event["source_ref"]
                if source.get("adapter") == "structured-disciplines" and source.get("command_key") == key:
                    return event
            after = page["next_after"]

    def _recover(self, event, operation):
        if operation == "discipline":
            return self.store.discipline(event["discipline_id"])
        if operation == "execution":
            return {"id": event["execution_id"], "discipline_id": event["discipline_id"],
                    "native_ref": event["data"]["native_ref"]}
        if operation == "delegate":
            return self.store.position(event["ordinal"])
        if operation == "instantiate":
            return next(i for i in self.store.instantiations(event["ordinal"])
                        if i["sequence"] == event["instantiation"])
        if operation == "session":
            return {"ordinal": event["ordinal"], "instantiation": event["instantiation"], "session": event["session"]}
        return event

    def once(self, key, request, operation, effect):
        if self.readonly:
            raise ScopeError("Read-only correlation cannot perform a mutation")
        if not isinstance(key, str) or not key.strip():
            raise ScopeError("A nonempty correlation command key is required")
        request = {"operation": operation, "request": request}
        encoded, source = _json(request), self._source(key, request)
        # Canonical events recover a committed domain act if this cache transaction dies.
        with closing(sqlite3.connect(self.cache, timeout=30)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT request,response FROM commands WHERE key=?", (key,)).fetchone()
            if row:
                if row[0] != encoded:
                    raise ScopeError("Correlation command was already used with a different request")
                return json.loads(row[1])
            event = self._event_for(key)
            if event:
                if any(event["source_ref"].get(k) != v for k, v in source.items()):
                    raise ScopeError("Canonical correlation command was already used with a different request")
                response = self._recover(event, operation)
            else:
                response = effect(source)
                if isinstance(response, Target):
                    response = response.as_dict()
            db.execute("INSERT INTO commands VALUES(?,?,?)", (key, encoded, _json(response)))
            return response

    def create_instance(self, *, command_id, effort_root, initiator, pattern, intent, environment,
                        initiating_target=None, parent_instance=None):
        if not isinstance(command_id, str) or not command_id.strip():
            raise ScopeError("Instance command_id must be nonempty text")
        scope = Scope.effort(effort_root)
        target = Target(**initiating_target) if initiating_target else None
        request = {"effort_root": effort_root, "initiator": initiator, "definition_ref": definition(pattern),
                   "intent": intent, "environment": environment, "initiating_target": initiating_target,
                   "parent_instance": parent_instance}
        def create(source):
            owner = self.store.position(effort_root, scope=scope)
            if owner["environment"] != environment:
                raise ScopeError("Instance environment must explicitly match the owning effort environment")
            return self.store.create_discipline(effort_root, scope=scope, initiator=initiator,
                definition_ref=request["definition_ref"], intent=intent, initiating_target=target,
                parent_instance=parent_instance, source_ref=source)
        return self.once(f"instance:{command_id}", request, "discipline", create)

    def _workspace(self, environment, workspace, preparation):
        cwd = environment.get("cwd")
        if not isinstance(cwd, str) or not Path(cwd).is_absolute():
            raise ScopeError("Instance environment requires an explicit absolute cwd")
        project, workspace = Path(cwd).resolve(strict=True), Path(workspace).resolve(strict=True)
        if preparation is None:
            if project != workspace:
                raise ScopeError("Workspace must be the declared local instance environment cwd")
            return
        if not isinstance(preparation, dict) or not {"project", "workspace", "owned_worktree", "base_commit", "initial_files"} <= preparation.keys():
            raise ScopeError("Prepared execution requires the maintained task_worktree correspondence")
        prepared_project = Path(preparation["project"]).resolve(strict=True)
        prepared_workspace = Path(preparation["workspace"]).resolve(strict=True)
        worktree = Path(preparation["owned_worktree"]).resolve(strict=True)
        if prepared_project != project or prepared_workspace != workspace or not workspace.is_relative_to(worktree):
            raise ScopeError("Prepared project/workspace differs from the declared execution")
        repository = Path(os.fsdecode(projects._git(project, "rev-parse", "--show-toplevel").stdout).strip()).resolve()
        actual_tree = Path(os.fsdecode(projects._git(worktree, "rev-parse", "--show-toplevel").stdout).strip()).resolve()
        def common(path):
            value = Path(os.fsdecode(projects._git(path, "rev-parse", "--git-common-dir").stdout).strip())
            return (path / value).resolve() if not value.is_absolute() else value.resolve()
        listed = projects._git(repository, "worktree", "list", "--porcelain").stdout.decode().splitlines()
        listed_trees = {Path(line.removeprefix("worktree ")).resolve() for line in listed if line.startswith("worktree ")}
        if (worktree == repository or actual_tree != worktree or worktree not in listed_trees or
                common(project) != common(worktree) or workspace != worktree / project.relative_to(repository)):
            raise ScopeError("Prepared workspace is not the source project's actual owned Git worktree")
        head = projects._git(worktree, "rev-parse", "HEAD^{commit}").stdout.decode().strip()
        if head != preparation["base_commit"] or projects.working_files(workspace) != preparation["initial_files"]:
            raise ScopeError("Prepared execution baseline differs from the retained task preparation")

    def validate(self, request, pattern, workspace, *, current=True):
        if not isinstance(request, dict) or set(request) - {
                "namespace_path", "effort_root", "discipline_id", "environment", "origin", "human_ref", "delegator", "preparation"}:
            raise ScopeError("Unknown structured scope request field")
        required = {"namespace_path", "effort_root", "discipline_id", "environment", "origin"}
        if not required <= request.keys():
            raise ScopeError("Structured scope requires namespace, effort, instance, environment and origin")
        if Path(request["namespace_path"]).expanduser().resolve(strict=True) != self.path:
            raise ScopeError("Requested namespace path differs from the configured namespace")
        scope = Scope.effort(request["effort_root"])
        instance = self.store.discipline(request["discipline_id"], scope=scope)
        if instance["definition_ref"] != definition(pattern):
            raise ScopeError("The maintained definition/version differs from this instance")
        if instance["environment"] != request.get("environment"):
            raise ScopeError("Explicit execution environment differs from the frozen instance")
        self._workspace(instance["environment"], workspace, request.get("preparation"))
        self.store.position(instance["initiator"], scope=scope)
        if request.get("origin") == "human":
            if request.get("delegator") is not None or not isinstance(request.get("human_ref"), dict) or not request["human_ref"]:
                raise ScopeError("Human assignment requires its reference and cannot claim an agent delegator")
        elif request.get("origin") == "agent":
            if request.get("human_ref") is not None:
                raise ScopeError("Agent assignment cannot claim human origin")
            target = Target(**request["delegator"])
            if target.ordinal != instance["initiator"]:
                raise ScopeError("Actual delegator must be this instance's initiating ordinal")
            actual = self.store.resolve(target.ordinal, scope=scope,
                                        **({} if current else {"instantiation": target.instantiation, "session": target.session}))
            if actual != target:
                raise ScopeError("Exact initiating target is stale")
        else:
            raise ScopeError("Execution assignment origin must be human or agent")
        return instance

    def execution(self, request, run_dir, options):
        instance = self.validate(request, options["pattern"], options["workspace"])
        owner = self.store.position(instance["effort"], scope=Scope.effort(instance["effort"]))
        effort_context = {"ordinal": owner["ordinal"], "intent": owner["intent"],
                          "mandate": owner["mandate"], "environment_version": owner["environment_version"]}
        native = {"run_id": run_dir.name, "run_dir": str(run_dir),
                  "controller_store": str(run_dir / "controller.sqlite3"), "options": options,
                  "execution_workspace": options["workspace"], "preparation": request.get("preparation"),
                  "assignment": request, "effort_context": effort_context,
                  "delegation_version": options.get("delegation_version"),
                  "delegation_capability": (controller.PATTERN_DIR / f"{options['pattern']}.json").is_file()
                      and json.loads((controller.PATTERN_DIR / f"{options['pattern']}.json").read_text())
                          .get("delegation", {}).get("version")}
        record = self.once(f"run:{run_dir.name}:execution", {"assignment": request, "native_ref": native},
            "execution", lambda source: self.store.create_execution(instance["id"],
                scope=Scope.effort(instance["effort"]), native_ref=native, source_ref=source))
        return {**request, "namespace_path": str(self.path), "namespace": self.store.namespace, "execution_id": record["id"],
                "initiator": instance["initiator"], "definition_ref": instance["definition_ref"],
                "effort_context": effort_context}

    def participant(self, binding, run_dir, activation):
        validate_binding(run_dir, namespace_path=self.path, binding=binding)
        scope = Scope.effort(binding["effort_root"])
        mandate = {"purpose": "Execute the controller's reserved function", "role": activation["role"],
                   "activation": activation, "run_id": run_dir.name, "environment": binding["environment"],
                   "definition_ref": binding["definition_ref"], "preparation": binding.get("preparation"),
                   "bounds": "Only this controller reservation",
                   "origin": binding["origin"]}
        request = {"binding": binding, "mandate": mandate}
        return self.once(f"run:{run_dir.name}:participant:{activation['id']}", request, "delegate", lambda source:
            self.store.delegate(binding["initiator"], scope=scope, mandate=mandate,
                origin=binding["origin"], human_ref=binding.get("human_ref"),
                delegator=Target(**binding["delegator"]) if binding.get("delegator") else None,
                discipline_id=binding["discipline_id"], source_ref=source))

    def observed(self, binding, run_dir, activation, native_ref):
        validate_binding(run_dir, namespace_path=self.path, binding=binding)
        participant = self.lookup(run_dir, activation["id"])
        if participant is None:
            raise ScopeError("Native observation requires its prior genuine participant reservation")
        ordinal, scope = participant["ordinal"], Scope.effort(binding["effort_root"])
        base = f"run:{run_dir.name}:native:{activation['id']}"
        identity = {"client": native_ref["client"], "session_id": native_ref["session_id"],
                    "actor_id": activation["actor_id"], "activation_id": activation["id"], "run_id": run_dir.name}
        instance = self.once(base + ":instance", {"ordinal": ordinal, "native_ref": identity}, "instantiate",
            lambda source: self.store.instantiate(ordinal, scope=scope, native_ref=identity, source_ref=source))
        return self.once(base + ":session", {"ordinal": ordinal, "native_ref": native_ref}, "session",
            lambda source: self.store.open_session(ordinal, instance["sequence"], scope=scope,
                                                   native_ref=native_ref, source_ref=source))

    def lookup(self, run_dir, activation_id):
        event = self._event_for(f"run:{Path(run_dir).name}:participant:{activation_id}")
        return self.store.position(event["ordinal"]) if event else None

    def target(self, run_dir, activation_id):
        event = self._event_for(f"run:{Path(run_dir).name}:native:{activation_id}:session")
        return Target(event["ordinal"], event["instantiation"], event["session"]) if event else None

    def event(self, binding, run_dir, key, kind, data, *, activation=None, exact=True):
        validate_binding(run_dir, namespace_path=self.path, binding=binding)
        participant = self.lookup(run_dir, activation["id"]) if activation else None
        ordinal = participant["ordinal"] if participant else binding["initiator"]
        target = self.target(run_dir, activation["id"]) if participant and exact else None
        request = {"ordinal": ordinal, "target": target.as_dict() if target else None, "kind": kind, "data": data}
        return self.once(f"run:{run_dir.name}:event:{key}", request, "event", lambda source:
            self.store.record_event(ordinal, scope=Scope.effort(binding["effort_root"]), kind=kind, data=data,
                target=target, discipline_id=binding["discipline_id"], execution_id=binding["execution_id"],
                source_ref={**source, "native_run": str(run_dir), "controller_store": str(run_dir / "controller.sqlite3")}))

    def sync(self, binding, run_dir, state):
        validate_binding(run_dir, namespace_path=self.path, binding=binding)
        scope = Scope.effort(binding["effort_root"])
        for activation in state["activations"].values():
            participant = self.lookup(run_dir, activation["id"])
            if participant is None:
                continue
            target = self.target(run_dir, activation["id"])
            if target:
                native = {"run_id": run_dir.name, "actor_id": activation["actor_id"], "activation_id": activation["id"],
                          "activation_dir": str(run_dir / "activations" / activation["id"])}
                self.once(f"run:{run_dir.name}:activation:{activation['id']}", {"target": target.as_dict(), "native_ref": native},
                    "event", lambda source: self.store.record_activation(binding["execution_id"], scope=scope,
                                                 participant=target, native_ref=native, source_ref=source))
            self.event(binding, run_dir, f"activation:{activation['id']}:{activation['status']}:{'observed' if target else 'unavailable'}",
                       "structured-activation-status", {"activation": activation, "native_identity": "observed" if target else "unavailable"},
                       activation=activation)
            if activation["status"] in {"retired", "failed"}:
                if target:
                    status = "closed" if activation["status"] == "retired" else "failed"
                    self.once(f"run:{run_dir.name}:close-session:{activation['id']}", {"target": target.as_dict(), "status": status},
                              "event", lambda source: self.store.set_session_status(target, status, scope=scope, source_ref=source))
                self.once(f"run:{run_dir.name}:close-position:{activation['id']}", {"ordinal": participant["ordinal"]},
                          "event", lambda source: self.store.close_position(participant["ordinal"], scope=scope, source_ref=source))
        for event in state["events"]:
            data = event["data"]
            activation_id = data.get("activation_id")
            artifact = state["artifacts"].get(data.get("artifact_id"))
            if artifact:
                activation_id = artifact["activation_id"]
            activation = state["activations"].get(activation_id)
            # A reservation has no participant until genuine assignment occurs.
            if activation:
                if self.lookup(run_dir, activation["id"]) is None:
                    if event["kind"] not in {"runtime.failed", "run.cancelled"}:
                        continue
                    activation = None
                elif self.target(run_dir, activation["id"]) is None and activation["status"] != "failed":
                    continue
            self.event(binding, run_dir, f"controller:{event['id']}", "structured-controller-event",
                       {"controller_event": event, "artifact": artifact,
                        "semantic_authority": "controller structure only; native memory standing unchanged"}, activation=activation)

        for event in runtime_events(run_dir):
            if event["kind"] not in {"step.started", "step.finished", "driver.paused", "driver.error", "process.cleanup"}:
                continue
            activation = state["activations"].get(event["data"].get("activation_id")) if event["kind"].startswith("step.") else None
            self.event(binding, run_dir, f"native:{event['sequence']}", "structured-native-event",
                       {"native_event": event, "source": str(run_dir / "events.sqlite3")}, activation=activation, exact=False)

    def inspect_execution(self, binding, run_dir):
        instance = self.store.discipline(binding["discipline_id"], scope=Scope.effort(binding["effort_root"]))
        records, after = [], 0
        while True:
            page = self.store.history(instance["effort"], discipline_id=instance["id"], after=after, limit=1000)
            if not page["records"]:
                break
            records.extend(e for e in page["records"] if e["execution_id"] == binding["execution_id"])
            after = page["next_after"]
        return {"binding": binding, "instance": instance, "history": records,
                "authority": "canonical ordinal history and native controller; last-known observations",
                "run_dir": str(run_dir)}


def runtime_events(run_dir):
    with closing(sqlite3.connect((Path(run_dir) / "events.sqlite3").as_uri() + "?mode=ro", uri=True)) as db:
        return [{"sequence": sequence, "occurred_at": at, "kind": kind, "data": json.loads(data)}
                for sequence, at, kind, data in db.execute("SELECT sequence,occurred_at,kind,data FROM events ORDER BY sequence")]


def _binding_records(db, path, run_dir, binding):
    namespace = db.execute("SELECT value FROM metadata WHERE key='namespace'").fetchone()
    if namespace is None or namespace[0] != binding["namespace"]:
        raise ScopeError("Run namespace identity mismatch")
    instance = db.execute("SELECT * FROM disciplines WHERE id=?", (binding["discipline_id"],)).fetchone()
    execution = db.execute("SELECT * FROM executions WHERE id=?", (binding["execution_id"],)).fetchone()
    if instance is None or execution is None or instance["effort"] != binding["effort_root"] or execution["discipline_id"] != instance["id"]:
        raise ScopeError("Incomplete or inconsistent canonical execution ownership")
    native_run = json.loads(execution["native_ref"])
    if (native_run["run_id"] != run_dir.name or Path(native_run["run_dir"]).resolve() != run_dir or
            Path(native_run["controller_store"]).resolve() != run_dir / "controller.sqlite3"):
        raise ScopeError("Canonical native execution differs from the requested run")
    assignment = native_run["assignment"]
    if not isinstance(assignment, dict) or Path(assignment["namespace_path"]).expanduser().resolve(strict=True) != path:
        raise ScopeError("Canonical assignment names a different namespace")
    expected = {**assignment, "namespace_path": str(path), "namespace": namespace[0],
                "execution_id": execution["id"], "initiator": instance["initiator"],
                "definition_ref": json.loads(instance["definition_ref"])}
    if "effort_context" in native_run:
        expected["effort_context"] = native_run["effort_context"]
    if (binding != expected or assignment["effort_root"] != instance["effort"] or
            assignment["discipline_id"] != instance["id"] or assignment["environment"] != json.loads(instance["environment"]) or
            assignment.get("preparation") != native_run.get("preparation")):
        raise ScopeError("Frozen run binding differs from its canonical execution assignment")
    return namespace, instance, execution, native_run


def validate_binding(run_dir, *, options=None, namespace_path=None, binding=None):
    """Check retained assignment authority without reauthorizing historical work."""
    run_dir = Path(run_dir).resolve(strict=True)
    try:
        if options is None:
            options_path = run_dir / "options.json"
            options = json.loads(options_path.read_text()) if options_path.exists() else {}
        selected = options.get("scope")
        if binding is not None and selected != binding:
            raise ScopeError("Supplied binding differs from the retained run options")
        if selected is not None:
            if not isinstance(selected, dict):
                raise ScopeError("Malformed structured run scope")
            path = Path(namespace_path or selected["namespace_path"]).expanduser().resolve(strict=True)
            if path != Path(selected["namespace_path"]).expanduser().resolve(strict=True):
                raise ScopeError("Requested namespace path differs from the run's declared namespace")
        with closing(sqlite3.connect((run_dir / "events.sqlite3").as_uri() + "?mode=ro", uri=True)) as journal:
            declared = [json.loads(row[0]) for row in journal.execute("SELECT data FROM events WHERE kind='scope.bound'")]
        if selected is not None and len(declared) != 1:
            raise ScopeError("Scoped run requires one retained native scope binding")
        if declared and (selected is None or declared[0] != selected):
            raise ScopeError("Incomplete or changed scoped run options")
        if selected is None:
            return None
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN")
            _binding_records(db, path, run_dir, selected)
        return selected
    except (OSError, KeyError, TypeError, ValueError, sqlite3.Error) as exc:
        if isinstance(exc, ScopeError):
            raise
        raise ScopeError(f"Incomplete or corrupt structured binding: {exc}") from exc


def correspondence(run_dir, *, namespace_path=None, effort_root=None):
    """Read canonical correspondence before a consumer reads or ranks run content.

    Unassigned legacy returns explicitly; malformed or incomplete assigned records
    fail. This helper neither creates a store/cache nor adopts historical runs.
    """
    run_dir = Path(run_dir).resolve(strict=True)
    try:
        options_path = run_dir / "options.json"
        options = json.loads(options_path.read_text()) if options_path.exists() else {}
        binding = options.get("scope")
        if binding is not None:
            if not isinstance(binding, dict):
                raise ScopeError("Malformed structured run scope")
            if effort_root is not None and binding["effort_root"] != effort_root:
                raise ScopeError("Requested effort does not own this run")
        validate_binding(run_dir, options=options, namespace_path=namespace_path)
        if binding is None:
            if effort_root is not None:
                raise ScopeError("Unassigned run has no requested effort ownership")
            return {"correlation_status": "unassigned", "namespace": None, "effort_root": None,
                    "discipline_id": None, "execution_id": None, "participants": [],
                    "native_run": {"run_id": run_dir.name, "run_dir": str(run_dir)},
                    "coverage": "Legacy native history; no fabricated application adoption"}
        if not isinstance(binding, dict):
            raise ScopeError("Malformed structured run scope")
        if effort_root is not None and binding["effort_root"] != effort_root:
            raise ScopeError("Requested effort does not own this run")
        path = Path(namespace_path or binding["namespace_path"]).expanduser().resolve(strict=True)
        if namespace_path is not None and path != Path(binding["namespace_path"]).expanduser().resolve():
            raise ScopeError("Requested namespace path differs from the run's declared namespace")
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN")
            namespace, instance, execution, native_run = _binding_records(db, path, run_dir, binding)
            participants, sources = [], []
            for event in db.execute("SELECT * FROM history WHERE discipline_id=? ORDER BY sequence", (instance["id"],)):
                source = json.loads(event["source_ref"])
                key = source.get("command_key", "")
                if source.get("adapter") != "structured-disciplines" or not key.startswith(f"run:{run_dir.name}:"):
                    continue
                sources.append({"history_sequence": event["sequence"], **source})
                if event["kind"] != "delegated" or not key.startswith(f"run:{run_dir.name}:participant:"):
                    continue
                position = db.execute("SELECT * FROM positions WHERE ordinal=?", (event["ordinal"],)).fetchone()
                if position is None or position["effort"] != instance["effort"] or position["discipline_id"] != instance["id"]:
                    raise ScopeError("Participant ownership differs from execution")
                mandate = db.execute("SELECT mandate FROM mandates WHERE ordinal=? AND version=1", (position["ordinal"],)).fetchone()
                activity = json.loads(mandate[0])["activation"]
                observed = None
                for candidate in db.execute("SELECT * FROM history WHERE ordinal=? AND kind='session-opened' ORDER BY sequence", (position["ordinal"],)):
                    ref = json.loads(candidate["source_ref"])
                    if ref.get("command_key") == f"run:{run_dir.name}:native:{activity['id']}:session":
                        observed = candidate
                        break
                occupant = db.execute("SELECT * FROM instantiations WHERE ordinal=? AND sequence=?",
                                      (position["ordinal"], observed["instantiation"] if observed else position["current_instantiation"])).fetchone()
                session = db.execute("SELECT * FROM sessions WHERE ordinal=? AND instantiation=? AND sequence=?",
                                     (position["ordinal"], observed["instantiation"], observed["session"])).fetchone() if observed else None
                if observed and (occupant is None or session is None):
                    raise ScopeError("Canonical native participant target is incomplete")
                target = {"ordinal": position["ordinal"], "instantiation": session["instantiation"], "session": session["sequence"]} if session else None
                participants.append({"ordinal": position["ordinal"], "origin": position["origin"],
                    "activation_id": activity["id"], "actor_id": activity["actor_id"], "target": target,
                    "native_agent_ref": json.loads(occupant["native_ref"]) if occupant else None,
                    "native_session_ref": json.loads(session["native_ref"]) if session else None,
                    "position_status": position["status"], "session_status": session["status"] if session else None,
                    "source_refs": [{"history_sequence": event["sequence"], **source}]})
            return {"correlation_status": "assigned", "namespace": {"id": namespace[0], "path": str(path)},
                    "effort_root": instance["effort"], "discipline_id": instance["id"], "execution_id": execution["id"],
                    "definition_ref": json.loads(instance["definition_ref"]), "environment": json.loads(instance["environment"]),
                    "native_run": native_run, "participants": participants, "source_refs": sources,
                    "coverage": "Canonical correlation and retained native references; context-file availability is client-specific"}
    except (OSError, KeyError, TypeError, ValueError, sqlite3.Error) as exc:
        if isinstance(exc, ScopeError):
            raise
        raise ScopeError(f"Incomplete or corrupt structured correlation: {exc}") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace-path", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("instance")
    create.add_argument("request", type=Path)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "instance":
            adapter = Disciplines(args.namespace_path)
            result = adapter.create_instance(**json.loads(args.request.read_text()))
        else:
            result = correspondence(args.run_dir, namespace_path=args.namespace_path)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        parser.exit(1, f"noetic disciplines failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
