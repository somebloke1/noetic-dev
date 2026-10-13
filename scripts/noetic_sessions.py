"""Persistent external Pi developer sessions and rooted delegation (Linux/POSIX)."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import signal
import socket
import socketserver
import sqlite3
import subprocess
import sys
import threading
import time
import uuid

from scripts import noetic_processes as processes
from scripts import noetic_projects as projects
from scripts.noetic_efforts import Efforts, Scope, ScopeError, Target
from scripts.noetic_storage import create_private_sqlite, ensure_private_directory, open_private

DEFAULT_MODEL = "openai-codex/gpt-6.1-sol"
EXTENSION = Path(__file__).with_name("noetic_session_extension.mjs")
MAX_RECORD = 8 * 1024 * 1024


class SessionError(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def project_location(body):
    if "projects_root" not in body:
        return None
    location = Path(text(body["projects_root"], "Projects location", maximum=4096)).expanduser()
    if not location.is_absolute():
        raise SessionError(400, "Projects location must be an absolute folder path.")
    return location


def now():
    return datetime.now(timezone.utc).isoformat()


def text(value, label, *, maximum=131072):
    if not isinstance(value, str) or not value.strip() or "\0" in value or len(value) > maximum:
        raise SessionError(400, f"{label} must be nonempty text (at most {maximum} characters).")
    return value


def session_id(value):
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise SessionError(400, "Invalid session ID.") from None
    return value


def socket_path(root, sid):
    digest = hashlib.sha256(f"{Path(root).resolve()}:{sid}".encode()).hexdigest()[:32]
    directory = Path("/tmp") / f"noetic-session-{os.getuid()}-{digest}"
    ensure_private_directory(directory)
    return directory / "control.sock"


class Registry:
    def __init__(self, root, *, create=True, namespace_path=None):
        self.domain = Efforts(root, namespace_path=namespace_path)
        self.root = Path(root).resolve() / "developer-sessions"
        self.path = self.root / "sessions.sqlite3"
        if create:
            self.initialize()

    def initialize(self):
        ensure_private_directory(self.root)
        create_private_sqlite(self.path)
        with closing(self.connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, root_id TEXT NOT NULL, parent_id TEXT,
                    ordinal TEXT NOT NULL, children INTEGER NOT NULL DEFAULT 0,
                    workspace TEXT NOT NULL, title TEXT NOT NULL, model TEXT NOT NULL,
                    thinking TEXT NOT NULL, command TEXT NOT NULL, status TEXT NOT NULL,
                    native_session_file TEXT, native_session_id TEXT, runtime TEXT NOT NULL DEFAULT '{}',
                    error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(root_id, ordinal)
                );
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
                    at TEXT NOT NULL, direction TEXT NOT NULL, record TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS session_events ON events(session_id, sequence);
            """)

            columns = {row[1] for row in db.execute("PRAGMA table_info(sessions)")}
            for name, kind in (("effort_root", "TEXT"), ("instantiation", "INTEGER"), ("session_selector", "INTEGER"), ("succession", "TEXT"), ("global_ordinal", "TEXT")):
                if name not in columns:
                    db.execute(f"ALTER TABLE sessions ADD COLUMN {name} {kind}")
            if "correlated" not in {row[1] for row in db.execute("PRAGMA table_info(events)")}:
                db.execute("ALTER TABLE events ADD COLUMN correlated INTEGER NOT NULL DEFAULT 0")

    def connect(self, *, readonly=False):
        if readonly and not self.path.exists():
            raise SessionError(404, "Developer session not found.")
        db = sqlite3.connect(self.path.as_uri() + "?mode=ro" if readonly else self.path, uri=readonly, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def directory(self, sid):
        return ensure_private_directory(self.root / session_id(sid))

    def get(self, sid):
        with closing(self.connect(readonly=True)) as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id(sid),)).fetchone()
        if row is None:
            raise SessionError(404, "Developer session not found.")
        result = dict(row)
        for key in ("command", "runtime"):
            result[key] = json.loads(result[key])
        result["original_ordinal"] = result["ordinal"]
        result["ordinal"] = result.get("global_ordinal") or result["ordinal"]
        result["target"] = ({"ordinal": result["ordinal"], "instantiation": result["instantiation"], "session": result["session_selector"]}
                            if result.get("instantiation") and result.get("session_selector") else None)
        result["effort_root"] = result.get("effort_root")
        result["identity_origin"] = ("historical-adoption" if result.get("global_ordinal") else
                                     "ordinal-native-correspondence" if result["target"] else
                                     "ordinal-reserved" if result["effort_root"] else "legacy-unadopted")
        return result

    def list(self, root_id=None):
        if not self.path.exists():
            return []
        with closing(self.connect(readonly=True)) as db:
            rows = db.execute("SELECT id FROM sessions ORDER BY created_at, id").fetchall()
        return [self.get(row[0]) for row in rows if root_id is None or self.get(row[0])["root_id"] == root_id or self.get(row[0]).get("effort_root") == root_id]

    def create(self, workspace, title, model, thinking, command, parent_id=None, *, ordinal, effort_root, succession=None):
        sid = str(uuid.uuid4())
        self.initialize()
        with closing(self.connect()) as db, db:
            db.execute("""INSERT INTO sessions
                (id,root_id,parent_id,ordinal,workspace,title,model,thinking,command,status,created_at,updated_at,effort_root,succession)
                VALUES (?,?,?,?,?,?,?,?,?,'created',?,?,?,?)""",
                (sid, sid, parent_id, ordinal, str(workspace), title, model, thinking, json.dumps(command), now(), now(), effort_root,
                 json.dumps(succession) if succession else None))
        self.directory(sid)
        self.event(sid, "host", {"type": "session_created", "parent_id": parent_id, "ordinal": ordinal})
        return self.get(sid)

    def attach(self, sid, state):
        with open_private(self.domain.path.with_suffix(".adapter.lock"), "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self._attach(sid, state)

    def _attach(self, sid, state):
        item = self.get(sid)
        store = self.domain.store()
        scope = Scope.effort(item["effort_root"])
        source = {"journal": str(self.path), "session_id": sid, "act": "native-session-observed"}
        if item["target"]:
            store.set_session_status(Target(**item["target"]), "open", scope=scope, source_ref=source)
        else:
            native = {"client": "pi", "session_id": state["sessionId"], "context_file": state.get("sessionFile"), "registry_id": sid}
            position = store.position(item["ordinal"], scope=scope)
            instance = position["current_instantiation"]
            succession = json.loads(item["succession"]) if item.get("succession") else None
            if instance is None or succession:
                instance = store.instantiate(item["ordinal"], scope=scope, native_ref=native, source_ref=source,
                                             predecessor=succession["predecessor"] if succession else None,
                                             handoff=succession["handoff"] if succession else None)["sequence"]
            target = store.open_session(item["ordinal"], instance, scope=scope, native_ref=native, source_ref=source)
            self.update(sid, instantiation=target.instantiation, session_selector=target.session)
        self.correlate(sid)

    def correlate(self, sid):
        item = self.get(sid)
        if not item["target"]:
            return
        with open_private(self.root / "correlation.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with closing(self.connect(readonly=True)) as db:
                rows = db.execute("SELECT * FROM events WHERE session_id=? AND correlated=0 ORDER BY sequence", (sid,)).fetchall()
            for row in rows:
                record = json.loads(row["record"])
                message = record.get("message")
                details = message.get("details") if isinstance(message, dict) else None
                details = details if isinstance(details, dict) else {}
                provenance = record.get("provenance") or details.get("provenance")
                self.domain.store().record_event(item["ordinal"], scope=Scope.effort(item["effort_root"]), kind="native-event",
                    data={"direction": row["direction"], "type": record.get("type"), "native_session_id": item["native_session_id"],
                          **({"provenance": provenance, "binding_id": record.get("binding_id") or details.get("binding_id")} if isinstance(provenance, dict) else {})},
                    source_ref={"journal": str(self.path), "session_id": sid, "sequence": row["sequence"],
                                "native_context": item["native_session_file"]}, target=Target(**item["target"]))
                with closing(self.connect()) as db, db:
                    db.execute("UPDATE events SET correlated=1 WHERE sequence=?", (row["sequence"],))

    def update(self, sid, **values):
        allowed = {"status", "native_session_file", "native_session_id", "runtime", "error", "model", "thinking", "instantiation", "session_selector", "effort_root", "global_ordinal"}
        if not values or set(values) - allowed:
            raise ValueError("Invalid session update")
        values = {**values, "updated_at": now()}
        values = {key: json.dumps(value) if key == "runtime" else value for key, value in values.items()}
        with closing(self.connect()) as db, db:
            db.execute("UPDATE sessions SET " + ",".join(f"{key}=?" for key in values) + " WHERE id=?",
                       [*values.values(), sid])

    def event(self, sid, direction, record):
        with closing(self.connect()) as db, db:
            cursor = db.execute("INSERT INTO events(session_id,at,direction,record) VALUES(?,?,?,?)",
                                (sid, now(), direction, json.dumps(record, ensure_ascii=True)))
            sequence = cursor.lastrowid
        self.correlate(sid)
        return sequence

    def events(self, sid, after=0, limit=500):
        self.get(sid)
        if type(after) is not int or after < 0:
            raise SessionError(400, "Event cursor must be a nonnegative integer.")
        with closing(self.connect(readonly=True)) as db:
            rows = db.execute("SELECT * FROM events WHERE session_id=? AND sequence>? ORDER BY sequence LIMIT ?",
                              (sid, after, min(max(limit, 1), 1000))).fetchall()
        return [{**dict(row), "record": json.loads(row["record"])} for row in rows]


def control(root, sid, request, timeout=30):
    path = socket_path(root, sid)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(timeout)
            connection.connect(str(path))
            connection.sendall(json.dumps(request, ensure_ascii=True).encode() + b"\n")
            with connection.makefile("rb") as reader:
                line = reader.readline(MAX_RECORD + 1)
        if not line or len(line) > MAX_RECORD:
            raise ValueError("Missing or oversized broker response")
        result = json.loads(line)
    except (OSError, ValueError) as exc:
        raise SessionError(409, f"Session broker unavailable; inspect status and explicitly reopen: {exc}") from exc
    if not result.get("success"):
        raise SessionError(result.get("status", 400), result.get("error", "Session command failed."))
    return result.get("data")


class SessionService:
    def __init__(self, runs_root, *, pi_command=None, namespace_path=None):
        self.runs_root = Path(runs_root).resolve()
        self.registry = Registry(self.runs_root, create=False, namespace_path=namespace_path)
        self.pi_command = pi_command

    def inspect(self, sid):
        item, context = self._select(sid)
        ownership = self.registry.directory(sid) / "broker-ownership.json"
        observed = processes.inspect(ownership)
        alive = observed["state"] == "owned"
        if not alive and item["status"] in ("starting", "submitted", "idle", "running", "needs_input", "stopping"):
            item = {**item, "status": "interrupted", "error": "Session process ended; explicit reopen required."}
        correspondence = {"is_current": False, "domain_status": None, "parentTarget": None}
        if item["target"]:
            position, instance, retained = context["position"], context["instantiation"], context["session"]
            correspondence = {"domain_status": retained["status"], "parentTarget": position["mandate"]["delegator"],
                "is_current": position["current_instantiation"] == item["target"]["instantiation"] and
                              instance["current_session"] == item["target"]["session"] and retained["status"] == "open"}
            reopenable = instance["status"] == "active" and retained["status"] != "superseded" and instance["current_session"] in (None, item["target"]["session"])
        else:
            reopenable = False
        return {**item, **correspondence, "broker_owned": alive, "process": observed,
                "needs_attention": item["status"] in ("needs_input", "failed", "interrupted"),
                "can_reopen": reopenable and not alive and observed["cleanup_confirmed"]}

    def current_context(self, sid):
        item, context = self._select(sid, current=True, include_effort=True)
        owner, position = context["owning_effort"], context["position"]
        return {"source": "registered-current-native-context", "namespace": context["namespace"],
                "target": item["target"], "effort_root": item["effort_root"],
                "effort": {key: owner[key] for key in ("ordinal", "intent", "mandate", "environment", "environment_version")},
                "position": {"ordinal": position["ordinal"], "mandate": position["mandate"],
                             "current_mandate_version": position["mandate_version"],
                             "instantiation_mandate_version": context["instantiation"]["mandate_version"]},
                "working_directory": item["workspace"], "native_transcript": item["native_session_file"],
                "transcript_directory": str(self.registry.directory(item["id"]) / "native"),
                "path_meaning": "working_directory is the Pi process cwd; native transcript paths are storage, not the working project"}

    def list(self, root_id=None):
        return [self.inspect(row["id"]) for row in self.registry.list(root_id)]

    def create_project(self, body):
        if not isinstance(body, dict) or set(body) - {"directory", "prompt", "title", "model", "thinking", "projects_root", "intent"}:
            raise SessionError(400, "Unknown new-project option.")
        directory = Path(text(body.get("directory"), "Project folder", maximum=4096)).expanduser()
        projects_root = project_location(body)
        prompt = text(body.get("prompt"), "Prompt")
        model = text(body.get("model", DEFAULT_MODEL), "Model", maximum=256)
        title = text(body.get("title", directory.name), "Project name", maximum=256)
        thinking = body.get("thinking", "high")
        if thinking not in ("off", "minimal", "low", "medium", "high", "xhigh"):
            raise SessionError(400, "Unknown thinking level.")
        try:
            directory = projects.create_project(directory, projects_root=projects_root)
        except projects.ProjectError as exc:
            raise SessionError(exc.status, str(exc)) from exc
        try:
            effort = self.create_effort({"intent": body.get("intent", prompt), "environment": {"cwd": str(directory)}})
            return self.create({"workspace": str(directory), "effort_root": effort["ordinal"], "prompt": prompt, "title": title,
                                "model": model, "thinking": thinking})
        except SessionError as exc:
            raise SessionError(exc.status, f"Project created at {directory}; session could not start: {exc}") from exc

    def create(self, body, *, parent_id=None):
        if not isinstance(body, dict) or set(body) - {"workspace", "prompt", "title", "model", "thinking", "projects_root", "effort_root", "ordinal", "succession", "mandate"}:
            raise SessionError(400, "Unknown developer-session option.")
        succession = body.get("succession")
        if succession is not None and (not isinstance(succession, dict) or set(succession) != {"predecessor", "handoff"} or
                type(succession["predecessor"]) is not int or succession["predecessor"] < 1 or
                not isinstance(succession["handoff"], dict) or not succession["handoff"]):
            raise SessionError(400, "Succession requires an exact positive predecessor and nonempty handoff object.")
        projects_root = project_location(body)
        parent = self.select(parent_id, current=True) if parent_id else None
        effort = parent["effort_root"] if parent else text(body.get("effort_root"), "Effort root")
        try:
            position = self.registry.domain.store().position(body.get("ordinal", effort), scope=Scope.effort(effort))
        except ScopeError as exc:
            raise SessionError(400, str(exc)) from exc
        workspace = Path(parent["workspace"] if parent else position["environment"]["cwd"]).expanduser()
        if not parent and body.get("workspace") not in (None, str(workspace)):
            raise SessionError(400, "Session workspace must match its effort environment.")
        if parent and body.get("workspace") not in (None, parent["workspace"]):
            raise SessionError(400, "Delegates use their parent's workspace.")
        model = text(body.get("model", parent["model"] if parent else DEFAULT_MODEL), "Model", maximum=256)
        thinking = body.get("thinking", parent["thinking"] if parent else "high")
        if thinking not in ("off", "minimal", "low", "medium", "high", "xhigh"):
            raise SessionError(400, "Unknown thinking level.")
        prompt = text(body.get("prompt"), "Prompt")
        title = text(body.get("title", prompt[:80]), "Title", maximum=256)
        try:
            workspace = projects.validate_workspace(workspace, projects_root=projects_root)
        except projects.ProjectError as exc:
            raise SessionError(exc.status, str(exc)) from exc
        command = self.pi_command or (parent["command"] if parent else [shutil.which("pi") or "pi"])
        try:
            if parent:
                position = self.registry.domain.store().delegate(parent["ordinal"], scope=Scope.effort(effort),
                    mandate=body.get("mandate", {"purpose": prompt}), origin="agent", delegator=Target(**parent["target"]),
                    source_ref={"journal": str(self.registry.path), "session_id": parent["id"], "act": "agent-delegate"})
            item = self.registry.create(workspace, title, model, thinking, command, parent["id"] if parent else None,
                                        ordinal=position["ordinal"], effort_root=effort, succession=body.get("succession"))
        except ScopeError as exc:
            raise SessionError(400, str(exc)) from exc
        try:
            self._launch(item["id"])
            if parent:
                self.message(parent["target"], item["id"], prompt, "prompt", effort_root=effort)
            else:
                self.prompt(item["id"], prompt)
        except BaseException as exc:
            self.registry.update(item["id"], error=str(exc)[:2000])
            raise
        return self.inspect(item["id"])

    def _launch(self, sid):
        directory = self.registry.directory(sid)
        item = self.registry.get(sid)
        lock = open_private(directory / "broker.lock", "a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close()
            raise SessionError(409, "A broker already owns this session.") from None
        environment = dict(os.environ)
        environment.pop("USER_PROVIDED_PASSWORD", None)
        self.registry.update(sid, status="starting", error=None)
        try:
            with open_private(directory / "broker.log", "ab") as output:
                child = subprocess.Popen([sys.executable, "-m", "scripts.noetic_sessions", "broker",
                    str(self.runs_root), sid, str(lock.fileno()), str(self.registry.domain.path)], cwd=Path(__file__).resolve().parents[1],
                    env=environment, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                    start_new_session=True, pass_fds=(lock.fileno(),))
            processes.save(directory / "broker-ownership.json", {"identity": processes.identity(child.pid), "state": "spawned"})
            threading.Thread(target=child.wait, daemon=True).start()
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if child.poll() is not None:
                    raise SessionError(503, "Pi broker failed to start; inspect retained broker diagnostics.")
                if socket_path(self.runs_root, sid).exists() and self.registry.get(sid)["status"] == "idle" and self.registry.get(sid)["target"]:
                    return
                time.sleep(.05)
            raise SessionError(503, "Pi broker startup timed out; session was not prompted.")
        except BaseException as exc:
            processes.reconcile(directory / "broker-ownership.json", terminate=True)
            self.registry.update(sid, status="failed", error="Broker launch failed; inspect retained diagnostics.")
            sequence = self.registry.event(sid, "host", {"type": "native_start_failed", "error": str(exc), "target": self.registry.get(sid)["target"]})
            if not self.registry.get(sid)["target"]:
                self.registry.domain.store().record_event(item["ordinal"], scope=Scope.effort(item["effort_root"]),
                    kind="native-start-failed", data={"status": "failed", "target": None, "error": str(exc)},
                    source_ref={"journal": str(self.registry.path), "session_id": sid, "sequence": sequence, "diagnostics": str(directory / "broker.log")})
            raise
        finally:
            lock.close()

    def create_effort(self, body):
        try:
            return self.registry.domain.create(body)
        except ScopeError as exc:
            raise SessionError(400, str(exc)) from exc

    def adopt_legacy(self, body):
        if not isinstance(body, dict) or set(body) - {"session_id", "effort_root", "ordinal", "human_ref", "mandate"}:
            raise SessionError(400, "Unknown historical adoption option.")
        item = self.registry.get(body.get("session_id"))
        effort = text(body.get("effort_root"), "Effort root")
        ordinal = body.get("ordinal", effort)
        store = self.registry.domain.store()
        scope = Scope.effort(effort)
        source = {"journal": str(self.registry.path), "session_id": item["id"], "act": "explicit-legacy-adoption"}
        namespace = "developer-sessions:" + hashlib.sha256(str(self.registry.path).encode()).hexdigest() + ":" + item["root_id"]
        try:
            store.position(ordinal, scope=scope)
            existing, after = [], 0
            while True:
                page = store.legacy_mappings(after=after, limit=1000)
                existing.extend(page)
                if not page:
                    break
                after = page[-1]["id"]
            mapped = next((r for r in existing if r["namespace"] == namespace and r["native_ref"].get("registry_id") == item["id"]), None)
            if mapped:
                if mapped["ordinal"] != ordinal:
                    raise SessionError(409, "Historical source already adopted at a different ordinal.")
                return {"mapping": mapped, "session": self.inspect(item["id"])}
            if item["target"]:
                raise SessionError(409, "Session already has a native ordinal correspondence.")
            if self.inspect(item["id"])["broker_owned"]:
                raise SessionError(409, "Close the legacy native broker before explicit adoption.")
            if not item["native_session_id"] or not item["native_session_file"]:
                raise SessionError(409, "Legacy source lacks observed native context; adoption cannot invent it.")
            try:
                store.legacy_namespace(namespace)
            except ScopeError:
                store.register_legacy_namespace(namespace, native_ref={"journal": str(self.registry.path), "root_id": item["root_id"]}, source_ref=source)
            parent = self.registry.get(item["parent_id"])["original_ordinal"] if item["parent_id"] else None
            position = store.position(ordinal, scope=scope)
            native = {"client": "pi", "session_id": item["native_session_id"], "context_file": item["native_session_file"], "registry_id": item["id"]}
            instance = position["current_instantiation"]
            if instance is None:
                instance = store.instantiate(ordinal, scope=scope, native_ref=native, source_ref=source)["sequence"]
            target = store.open_session(ordinal, instance, scope=scope, native_ref=native, source_ref=source)
            mapping = store.adopt_legacy(namespace, item["original_ordinal"], ordinal, scope=scope, native_ref=native,
                                         source_ref=source, original_parent=parent, target=target)
            self.registry.initialize()
            self.registry.update(item["id"], global_ordinal=ordinal, effort_root=effort,
                                 instantiation=target.instantiation, session_selector=target.session)
            store.set_session_status(target, "failed" if item["status"] == "failed" else "closed", scope=scope, source_ref=source)
            self.registry.correlate(item["id"])
            return {"mapping": mapping, "session": self.inspect(item["id"])}
        except ScopeError as exc:
            raise SessionError(400, str(exc)) from exc

    def position(self, ordinal, *, effort_root=None):
        try:
            return self.registry.domain.store().position(ordinal, scope=self.registry.domain.scope(effort_root))
        except ScopeError as exc:
            raise SessionError(400, str(exc)) from exc

    def branch(self, ordinal="0", *, effort_root=None, after=0, limit=100):
        if not self.registry.domain.path.exists():
            return {"records": [], "next_after": after}
        try:
            return self.registry.domain.store().branch(ordinal, scope=self.registry.domain.scope(effort_root), after=after, limit=limit, describe_roots=True)
        except ScopeError as exc:
            raise SessionError(400, str(exc)) from exc

    def history(self, ordinal="0", *, effort_root=None, after=0, limit=100, instantiation=None, session=None):
        if not self.registry.domain.path.exists():
            return {"records": [], "next_after": after}
        try:
            return self.registry.domain.store().history(ordinal, scope=self.registry.domain.scope(effort_root), after=after,
                limit=limit, instantiation=instantiation, session=session)
        except ScopeError as exc:
            raise SessionError(400, str(exc)) from exc

    def select(self, address, *, effort_root=None, current=False):
        return self._select(address, effort_root=effort_root, current=current)[0]

    def _select(self, address, *, effort_root=None, current=False, include_effort=False):
        try:
            if isinstance(address, str) and not re.fullmatch(r"0(?:\.[0-9]+)*", address):
                item = self.registry.get(address)
                if not item["target"]:
                    if effort_root is not None and item["effort_root"] != effort_root:
                        raise SessionError(400, "Requested effort does not own this reserved or unadopted native context.")
                    if current:
                        raise SessionError(409, "Legacy session requires explicit adoption before ordinal actions.")
                    return item, None
                address = item["target"]
            selectors = address if isinstance(address, dict) else {"ordinal": address}
            scope = self.registry.domain.scope(effort_root)
            store = self.registry.domain.store()
            context = store.resolve_context(selectors["ordinal"], scope=scope,
                instantiation=selectors.get("instantiation"), session=selectors.get("session"), current=current, include_effort=include_effort)
            target, native = context["target"], context["session"]["native_ref"]
            if not native.get("registry_id"):
                raise SessionError(409, "Exact context has no native conversation registry backing; inspect its retained source.")
            item = self.registry.get(native["registry_id"])
            if item["target"] != target:
                raise SessionError(409, "Native context has no matching exact ordinal target.")
            return item, context
        except (ScopeError, KeyError) as exc:
            raise SessionError(409 if current else 400, str(exc)) from exc

    def bind(self, address, kind, payload, *, effort_root=None):
        if kind == "agent_message":
            raise SessionError(400, "Agent messages must originate from an exact sending broker.")
        item = self.select(address, effort_root=effort_root)
        if not item["target"]:
            raise SessionError(409, "No observed native context for this reserved or unadopted session.")
        try:
            return self.registry.domain.store().bind_action(item["ordinal"], scope=self.registry.domain.scope(effort_root),
                kind=kind, payload=payload or {"operation": kind}, source_ref={"adapter": "developer-sessions", "act": "bind-action"},
                instantiation=item["target"]["instantiation"], session=item["target"]["session"])
        except ScopeError as exc:
            raise SessionError(400, str(exc)) from exc

    def deliver(self, action_id, *, effort_root=None):
        try:
            binding = self.registry.domain.store().action(action_id, scope=self.registry.domain.scope(effort_root))
        except ScopeError as exc:
            raise SessionError(400, str(exc)) from exc
        item = self.select(binding["target"], effort_root=effort_root, current=True)
        if binding["native_ref"].get("session_id") != item["native_session_id"] or binding["native_ref"].get("context_file") != item["native_session_file"]:
            raise SessionError(409, "Bound native reference no longer matches the original context.")
        if binding["environment"].get("cwd") != item["workspace"]:
            raise SessionError(409, "Bound effort environment does not match the selected runtime.")
        if binding["kind"] == "agent_message":
            provenance = binding["payload"]["provenance"]
            self.select(provenance["sender"], effort_root=item["effort_root"], current=True)
        request = {"action": binding["kind"], **binding["payload"], "binding_id": action_id}
        data = control(self.runs_root, item["id"], request)
        return {**data, "target": binding["target"], "native_ref": binding["native_ref"], "binding_id": action_id,
                **({"provenance": binding["payload"]["provenance"]} if binding["kind"] == "agent_message" else {})}

    def reopen(self, address, *, effort_root=None):
        selected = self.select(address, effort_root=effort_root)
        target = selected["target"]
        if not target:
            raise SessionError(409, "No observed native context; open a new session at the reserved position explicitly.")
        position = self.position(selected["ordinal"], effort_root=effort_root)
        instances = self.registry.domain.store().instantiations(selected["ordinal"])
        instance = instances[target["instantiation"] - 1]
        retained = self.registry.domain.store().sessions(target["ordinal"], target["instantiation"])[target["session"] - 1]
        if retained["status"] == "superseded":
            raise SessionError(409, "Historical superseded session is unavailable for reopen.")
        if position["current_instantiation"] != target["instantiation"] or instance["status"] != "active":
            raise SessionError(409, "Historical superseded instantiation cannot reopen as its successor.")
        if instance["current_session"] not in (None, target["session"]):
            raise SessionError(409, "Historical superseded session cannot replace the designated current session.")
        binding = self.bind(target, "reopen", {}, effort_root=effort_root)
        item = self.inspect(selected["id"])
        if not item["broker_owned"]:
            if not item["process"]["cleanup_confirmed"]:
                raise SessionError(409, "Prior process cleanup is unconfirmed; refusing a second actor.")
            self._launch(item["id"])
            self.registry.event(item["id"], "host", {"type": "session_reopened", "binding_id": binding["id"]})
        return {**self.inspect(item["id"]), "binding_id": binding["id"], "native_ref": binding["native_ref"]}

    def prompt(self, address, message, mode="prompt", *, effort_root=None):
        if mode not in ("prompt", "steer", "follow_up"):
            raise SessionError(400, "Select prompt, steer, or follow_up.")
        binding = self.bind(address, "prompt", {"message": text(message, "Message"), "mode": mode}, effort_root=effort_root)
        return self.deliver(binding["id"], effort_root=effort_root)

    def message(self, sender, recipient, message, mode="follow_up", *, effort_root=None, in_reply_to=None):
        if mode not in ("prompt", "steer", "follow_up"):
            raise SessionError(400, "Select prompt, steer, or follow_up.")
        source = self.select(sender, effort_root=effort_root, current=True)
        destination = self.select(recipient, effort_root=source["effort_root"], current=True)
        if in_reply_to is not None:
            original = self.registry.domain.store().action(in_reply_to, scope=Scope.effort(source["effort_root"]))
            if (original["kind"] != "agent_message" or original["target"] != source["target"] or
                    original["payload"]["provenance"]["reply_to"] != destination["target"]):
                raise SessionError(409, "Reply does not match the original exact sender and recipient.")
        provenance = {"origin": "agent", "sender": source["target"], "recipient": destination["target"],
                      "effort_root": source["effort_root"], "reply_to": source["target"], "in_reply_to": in_reply_to}
        binding = self.registry.domain.store().bind_action(destination["ordinal"], scope=Scope.effort(source["effort_root"]),
            kind="agent_message", payload={"message": text(message, "Message"), "mode": mode, "provenance": provenance},
            source_ref={"journal": str(self.registry.path), "session_id": source["id"], "act": "agent-send", "sender": source["target"]},
            instantiation=destination["target"]["instantiation"], session=destination["target"]["session"])
        self.registry.event(source["id"], "host", {"type": "agent_message_sent", "binding_id": binding["id"], "provenance": provenance})
        return self.deliver(binding["id"], effort_root=source["effort_root"])

    def stop(self, address, *, effort_root=None):
        binding = self.bind(address, "stop", {}, effort_root=effort_root)
        return self.deliver(binding["id"], effort_root=effort_root)

    def shutdown(self, address, *, effort_root=None):
        # Cleanup uses the retained native owner, including superseded processes.
        item = self.select(address, effort_root=effort_root)
        return control(self.runs_root, item["id"], {"action": "shutdown", "target": item["target"]})

    def detail(self, address, after=0, *, effort_root=None, limit=500):
        item = self.select(address, effort_root=effort_root)
        events = self.registry.events(item["id"], after, limit)
        return {"session": self.inspect(item["id"]), "events": events,
                "next_after": events[-1]["sequence"] if events else after,
                "tree": self.list(item["effort_root"] or item["root_id"])}


class Broker:
    def __init__(self, runs_root, sid, namespace_path=None):
        self.service = SessionService(runs_root, namespace_path=namespace_path)
        self.registry, self.sid = self.service.registry, sid
        self.directory = self.registry.directory(sid)
        self.pending = {}
        self.pending_lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.action_lock = threading.RLock()
        self.closed = threading.Event()
        self.stopping = False
        self.error = None
        self.dialogs = {}
        self.process = None

    def rpc(self, kind, **fields):
        command_id = str(uuid.uuid4())
        event = threading.Event()
        holder = {"event": event}
        with self.pending_lock:
            self.pending[command_id] = holder
        record = {"id": command_id, "type": kind, **fields}
        try:
            self.write(record)
            if not event.wait(20):
                raise SessionError(504, f"Pi did not acknowledge {kind}; outcome remains uncertain.")
            response = holder["response"]
            if not response.get("success"):
                raise SessionError(400, response.get("error", "Pi command failed."))
            return response.get("data")
        finally:
            with self.pending_lock:
                self.pending.pop(command_id, None)

    def write(self, record):
        self.registry.event(self.sid, "command", record)
        try:
            with self.write_lock:
                self.process.stdin.write(json.dumps(record, ensure_ascii=True).encode() + b"\n")
                self.process.stdin.flush()
        except (OSError, ValueError) as exc:
            raise SessionError(409, "Pi process is no longer writable.") from exc

    def read_stdout(self):
        try:
            while line := self.process.stdout.readline(MAX_RECORD + 1):
                if len(line) > MAX_RECORD or not line.endswith(b"\n"):
                    raise ValueError("Pi emitted an oversized or incomplete JSONL record.")
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("Pi emitted a non-object RPC record.")
                self.registry.event(self.sid, "event", record)
                kind = record.get("type")
                if kind == "response":
                    with self.pending_lock:
                        holder = self.pending.get(record.get("id"))
                        if holder is not None:
                            holder["response"] = record
                            holder["event"].set()
                elif kind == "agent_start":
                    self.error = None
                    self.registry.update(self.sid, status="running", error=None)
                elif kind == "message_end" and record.get("message", {}).get("stopReason") == "error":
                    self.error = record["message"].get("errorMessage", "Provider reported an error.")
                elif kind == "auto_retry_end" and not record.get("success"):
                    self.error = record.get("finalError", "Pi retries failed.")
                elif kind == "agent_settled":
                    self.dialogs.clear()
                    self.registry.update(self.sid, status="failed" if self.error else "idle", error=self.error)
                elif kind == "extension_ui_request" and record.get("method") in ("select", "confirm", "input", "editor"):
                    self.dialogs[record["id"]] = record
                    self.registry.update(self.sid, status="needs_input")
                elif kind == "queue_update":
                    state = self.registry.get(self.sid)["runtime"]
                    self.registry.update(self.sid, runtime={**state, "queue": {"steering": record.get("steering", []), "followUp": record.get("followUp", [])}})
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self.error = str(exc)
            self.registry.event(self.sid, "host", {"type": "protocol_error", "error": self.error})
        finally:
            with self.pending_lock:
                for holder in self.pending.values():
                    holder["response"] = {"success": False, "error": "Pi RPC stream ended."}
                    holder["event"].set()
            self.closed.set()

    def read_stderr(self):
        with open_private(self.directory / "pi.stderr.log", "ab") as output:
            while chunk := self.process.stderr.read(4096):
                output.write(chunk)
                output.flush()

    def related(self, target):
        current = self.registry.get(self.sid)
        if isinstance(target, str) and target in ("root", "effort_root"):
            target = current["effort_root"]
        elif target == "parent":
            target = self.service.position(current["ordinal"])["parent"]
        return self.service.select(target, effort_root=current["effort_root"])

    def handle(self, request):
        action = request.get("action")
        if request.get("effort_root") not in (None, self.registry.get(self.sid)["effort_root"]):
            raise SessionError(400, "Broker effort scope does not own the requested caller.")
        if request.get("parentTarget") is not None and request["parentTarget"] != self.registry.get(self.sid)["target"]:
            raise SessionError(409, "Tool parentTarget does not match this broker's exact target.")
        if request.get("binding_id") is not None:
            binding = self.registry.domain.store().action(request["binding_id"], scope=Scope.effort(self.registry.get(self.sid)["effort_root"]))
            if binding["target"] != self.registry.get(self.sid)["target"] or binding["kind"] != action:
                raise SessionError(409, "Bound action does not match this broker's exact target.")
            if any(request.get(key) != value for key, value in binding["payload"].items() if key != "operation"):
                raise SessionError(409, "Bound payload does not match the retained action.")
            self.service.select(binding["target"], current=True)
        if action in ("context", "overview"):
            context = self.service.current_context(self.sid)
            return context if action == "context" else {"context": context, "branch": self.service.list(context["effort_root"])}
        if action == "identity":
            item = self.service.select(self.sid, current=True)
            return {"target": item["target"], "effort_root": item["effort_root"]}
        if action == "agent_delivery":
            item = self.service.select(self.sid, current=True)
            binding = self.registry.domain.store().action(request.get("message_id"), scope=Scope.effort(item["effort_root"]))
            if binding["kind"] != "agent_message" or binding["target"] != item["target"]:
                raise SessionError(409, "Agent message is not addressed to this exact recipient.")
            provenance = binding["payload"]["provenance"]
            self.service.select(provenance["sender"], effort_root=item["effort_root"], current=True)
            self.registry.event(self.sid, "host", {"type": "agent_message_received", "binding_id": binding["id"], "provenance": provenance})
            return {**binding["payload"], "binding_id": binding["id"]}
        if action == "delegate":
            child = self.service.create({key: request[key] for key in ("prompt", "title", "model", "thinking", "mandate") if key in request}, parent_id=self.sid)
            self.registry.event(self.sid, "host", {"type": "agent_delegated", "child_id": child["id"], "ordinal": child["ordinal"], "parentTarget": self.registry.get(self.sid)["target"], "childTarget": child["target"]})
            return child
        if action in ("read", "wait", "message"):
            target = request.get("target", self.sid)
            if target == "parent":
                target = self.service.position(self.registry.get(self.sid)["ordinal"])["parent"]
            if target == "0" and action == "read":
                return {"position": self.service.position("0"), "branch": self.service.branch("0", after=request.get("after", 0)),
                        "history": self.service.history("0", after=request.get("after", 0))}
            target = self.related(target)["id"]
            if action == "message":
                return self.service.message(self.registry.get(self.sid)["target"], target, request.get("message"),
                    request.get("mode", "follow_up"), effort_root=self.registry.get(self.sid)["effort_root"],
                    in_reply_to=request.get("in_reply_to"))
            if action == "wait":
                timeout = request.get("timeout", 30)
                if type(timeout) not in (int, float) or not 0 <= timeout <= 60:
                    raise SessionError(400, "Wait timeout must be 0-60 seconds.")
                deadline = time.monotonic() + timeout
                while self.service.inspect(target)["status"] in ("running", "submitted", "starting", "stopping") and time.monotonic() < deadline:
                    time.sleep(.1)
            return self.service.detail(target, request.get("after", 0))
        if action == "tree":
            return self.service.list(self.registry.get(self.sid)["effort_root"])
        with self.action_lock:
            if action in ("prompt", "agent_message"):
                if action == "agent_message" and request.get("binding_id") is None:
                    raise SessionError(409, "Agent delivery requires a canonical bound message.")
                self.service.select(self.sid, current=True)
                if action == "agent_message":
                    self.service.select(request["provenance"]["sender"], effort_root=self.registry.get(self.sid)["effort_root"], current=True)
                if self.stopping:
                    raise SessionError(409, "Stop is in progress.")
                mode = request.get("mode", "prompt")
                if mode not in ("prompt", "steer", "follow_up"):
                    raise SessionError(400, "Unknown prompt mode.")
                fields = {"message": f"/noetic-deliver {request['binding_id']}" if action == "agent_message" else text(request.get("message"), "Message")}
                if mode != "prompt":
                    fields["streamingBehavior"] = "steer" if mode == "steer" else "followUp"
                prior = self.registry.get(self.sid)["status"]
                with closing(self.registry.connect(readonly=True)) as db:
                    before = db.execute("SELECT COALESCE(MAX(sequence),0) FROM events WHERE session_id=?", (self.sid,)).fetchone()[0]
                if prior in ("idle", "failed"):
                    self.registry.update(self.sid, status="submitted")
                try:
                    data = self.rpc("prompt", **fields)
                    if action == "agent_message":
                        with closing(self.registry.connect(readonly=True)) as db:
                            received = db.execute("""SELECT 1 FROM events WHERE session_id=? AND sequence>? AND direction='host'
                                AND json_extract(record,'$.type')='agent_message_received' AND json_extract(record,'$.binding_id')=? LIMIT 1""",
                                (self.sid, before, request["binding_id"])).fetchone()
                        if not received:
                            raise SessionError(409, "Pi did not fetch the canonical agent envelope; delivery is unconfirmed.")
                except SessionError:
                    if self.registry.get(self.sid)["status"] == "submitted":
                        self.registry.update(self.sid, status=prior)
                    raise
                return {"accepted": True, "mode": mode, "data": data, "completion": "observe agent_settled"}
            if action == "stop":
                self.stopping = True
                self.registry.update(self.sid, status="stopping")
                try:
                    cleared = self.rpc("clear_queue")
                    self.rpc("abort")
                    state = self.rpc("get_state")
                    stopped = not state.get("isStreaming") and not state.get("pendingMessageCount")
                    self.registry.update(self.sid, status="idle" if stopped else "stopping", runtime=state)
                    return {"queue_cleared": cleared, "state": state, "stopped": stopped}
                finally:
                    self.stopping = False
            if action == "state":
                state = self.rpc("get_state")
                self.registry.update(self.sid, runtime=state)
                return {"state": state, "dialogs": list(self.dialogs.values())}
            if action == "dialog":
                dialog_id = request.get("id")
                if dialog_id not in self.dialogs:
                    raise SessionError(409, "Dialog is no longer pending.")
                response = {"type": "extension_ui_response", "id": dialog_id}
                if "cancelled" in request and type(request["cancelled"]) is not bool:
                    raise SessionError(400, "Dialog cancellation must be boolean.")
                if request.get("cancelled"):
                    response["cancelled"] = True
                elif self.dialogs[dialog_id]["method"] == "confirm":
                    if type(request.get("confirmed")) is not bool:
                        raise SessionError(400, "Confirmation must be boolean.")
                    response["confirmed"] = request["confirmed"]
                else:
                    response["value"] = text(request.get("value"), "Dialog response")
                self.write(response)
                self.dialogs.pop(dialog_id)
                self.registry.update(self.sid, status="needs_input" if self.dialogs else "running")
                return {"sent": True}
            if action == "shutdown":
                self.handle({"action": "stop"})
                self.closed.set()
                return {"shutdown_requested": True}
        raise SessionError(400, "Unknown session action.")

    def run(self):
        item = self.registry.get(self.sid)
        path = socket_path(self.service.runs_root, self.sid)
        path.unlink(missing_ok=True)
        environment = dict(os.environ)
        environment.pop("USER_PROVIDED_PASSWORD", None)
        environment["NOETIC_SESSION_SOCKET"] = str(path)
        environment["NOETIC_SESSION_ID"] = self.sid
        environment["NOETIC_SESSION_ORDINAL"] = item["ordinal"]
        environment["NOETIC_EFFORT_ROOT"] = item["effort_root"]
        native = ensure_private_directory(self.directory / "native")
        argv = [*item["command"], "--mode", "rpc", "--session-dir", str(native), "--session-id", self.sid,
                "--model", item["model"], "--thinking", item["thinking"], "--no-extensions", "-e", str(EXTENSION)]
        self.process = subprocess.Popen(argv, cwd=item["workspace"], env=environment, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.registry.event(self.sid, "host", {"type": "pi_started", "pid": self.process.pid})
        threading.Thread(target=self.read_stdout, daemon=True).start()
        threading.Thread(target=self.read_stderr, daemon=True).start()
        broker = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                try:
                    line = self.rfile.readline(MAX_RECORD + 1)
                    if len(line) > MAX_RECORD or not line.endswith(b"\n"):
                        raise SessionError(400, "Invalid broker frame.")
                    request = json.loads(line)
                    if not isinstance(request, dict):
                        raise SessionError(400, "Broker request must be an object.")
                    result = {"success": True, "data": broker.handle(request)}
                except sqlite3.Error as exc:
                    result = {"success": False, "status": 503,
                              "error": f"Session storage operation failed: {exc}. The outcome may be uncertain; inspect retained status before retrying."}
                except (SessionError, OSError, ValueError, TypeError, KeyError) as exc:
                    result = {"success": False, "status": getattr(exc, "status", 400), "error": str(exc)}
                try:
                    self.wfile.write(json.dumps(result, ensure_ascii=True).encode() + b"\n")
                except OSError:
                    pass

        class Server(socketserver.ThreadingUnixStreamServer):
            daemon_threads = True

        server = Server(str(path), Handler)
        os.chmod(path, 0o600)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            state = self.rpc("get_state")
            observed_model = state.get("model", {})
            observed_id = observed_model.get("id")
            observed_route = f"{observed_model.get('provider')}/{observed_id}"
            planned_context = state.get("sessionFile")
            if (not isinstance(planned_context, str) or not planned_context.strip() or "\0" in planned_context or
                    len(planned_context) > 4096 or not Path(planned_context).is_absolute()):
                self.error = "Pi did not provide a valid planned native context reference; prompt was not sent."
                raise SessionError(409, self.error)
            if (item["model"] not in (observed_id, observed_route) or state.get("sessionId") != self.sid or
                    item["native_session_file"] is not None and state.get("sessionFile") != item["native_session_file"]):
                self.error = "Pi selected a different model or native context; prompt was not sent."
                raise SessionError(409, self.error)
            self.registry.update(self.sid, runtime=state, native_session_file=state.get("sessionFile"), native_session_id=state.get("sessionId"))
            self.registry.attach(self.sid, state)
            self.registry.update(self.sid, status="idle")
            self.closed.wait()
        finally:
            self.closed.set()
            server.shutdown()
            server.server_close()
            path.unlink(missing_ok=True)
            self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            status = "failed" if self.error else "closed"
            self.registry.update(self.sid, status=status, error=self.error)
            target = self.registry.get(self.sid)["target"]
            if target:
                store = self.registry.domain.store()
                retained = store.sessions(target["ordinal"], target["instantiation"])[target["session"] - 1]
                domain_status = "superseded" if retained["status"] == "superseded" else status
                store.set_session_status(Target(**target), domain_status, scope=Scope.effort(item["effort_root"]),
                    source_ref={"journal": str(self.registry.path), "session_id": self.sid, "act": "native-process-exited"})
            self.registry.event(self.sid, "host", {"type": "pi_exited", "returncode": self.process.returncode})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("list", "show", "start", "prompt", "stop", "reopen", "shutdown", "broker", "register-effort", "position", "branch", "history"))
    parser.add_argument("--runs-dir", default=os.environ.get("NOETIC_STATE_HOME", ".runtime") + "/runs")
    parser.add_argument("--workspace")
    parser.add_argument("--namespace-path")
    parser.add_argument("--effort-root")
    parser.add_argument("--ordinal")
    parser.add_argument("--instantiation", type=int)
    parser.add_argument("--session", type=int)
    parser.add_argument("--intent")
    parser.add_argument("--predecessor", type=int)
    parser.add_argument("--handoff", help="Explicit succession handoff JSON object")
    parser.add_argument("--after", type=int, default=0)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--thinking", default="high")
    parser.add_argument("arguments", nargs="*")
    args = parser.parse_intermixed_args(argv)
    if args.command == "broker":
        root, sid, lock_fd, namespace_path = args.arguments
        # The launcher's flock is inherited for this broker's complete lifetime.
        lock_fd = int(lock_fd)
        broker = Broker(root, sid, namespace_path)
        signal.signal(signal.SIGTERM, lambda *_: broker.closed.set())
        try:
            broker.run()
        finally:
            os.close(lock_fd)
        return 0
    service = SessionService(args.runs_dir, namespace_path=args.namespace_path)
    try:
        address = args.ordinal or (args.arguments[0] if args.arguments else "0")
        if args.instantiation is not None or args.session is not None:
            address = {"ordinal": address, "instantiation": args.instantiation, "session": args.session}
        if args.command == "register-effort":
            result = service.create_effort({"intent": args.intent or " ".join(args.arguments), "environment": {"cwd": args.workspace}})
        elif args.command == "position":
            result = service.position(address, effort_root=args.effort_root)
        elif args.command in ("branch", "history"):
            options = {"effort_root": args.effort_root, "after": args.after, "limit": args.limit}
            if args.command == "history":
                options.update(instantiation=args.instantiation, session=args.session)
            result = getattr(service, args.command)(args.ordinal or (args.arguments[0] if args.arguments else "0"), **options)
        elif args.command == "list":
            result = service.list(args.effort_root)
        elif args.command == "start":
            body = {"effort_root": args.effort_root, "prompt": " ".join(args.arguments), "model": args.model, "thinking": args.thinking}
            if args.workspace:
                body["workspace"] = args.workspace
            if args.ordinal:
                body["ordinal"] = args.ordinal
            if args.predecessor is not None or args.handoff is not None:
                try:
                    handoff = json.loads(args.handoff or "null")
                except ValueError:
                    raise SessionError(400, "Handoff must be a JSON object.") from None
                body["succession"] = {"predecessor": args.predecessor, "handoff": handoff}
            result = service.create(body)
        elif args.command == "show":
            result = service.detail(address, args.after, effort_root=args.effort_root, limit=args.limit)
        elif args.command == "prompt":
            result = service.prompt(address, " ".join(args.arguments if args.ordinal else args.arguments[1:]), "follow_up", effort_root=args.effort_root)
        else:
            result = getattr(service, args.command)(address, effort_root=args.effort_root)
        print(json.dumps(result, indent=2))
        return 0
    except SessionError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
