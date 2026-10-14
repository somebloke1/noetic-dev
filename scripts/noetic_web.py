#!/usr/bin/env python3
"""Local controller-backed operator workspace with explicit harness actions."""

from __future__ import annotations

import argparse
import http.client
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from urllib.parse import parse_qs, unquote, urlsplit

if __package__:
    from scripts import noetic_application as application
    from scripts import noetic_attachments as attachments
    from scripts import noetic_usage as usage
    from scripts import noetic_costs as costs
    from scripts.noetic_scope import ScopeError
    from scripts import noetic_controller as controller
    from scripts import noetic_harness as harness
    from scripts import noetic_memory as memory
    from scripts import noetic_sessions as developer_sessions
    from scripts import noetic_run as runtime
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import noetic_application as application
    from scripts import noetic_attachments as attachments
    from scripts import noetic_usage as usage
    from scripts import noetic_costs as costs
    from scripts.noetic_scope import ScopeError
    import noetic_controller as controller
    import noetic_harness as harness
    import noetic_memory as memory
    from scripts import noetic_sessions as developer_sessions
    import noetic_run as runtime


ARTIFACT_NAMES = (
    "task.md", "work.md", "review.md",
    "changes.diff", "changes.json",
    "work.stdout.log", "work.stderr.log",
    "verify.stdout.log", "verify.stderr.log",
    "review.stdout.log", "review.stderr.log",
)
ARTIFACT_LIMIT = 256 * 1024
ACTOR_ARTIFACT_NAMES = (
    "actor.stdout.log", "actor.stderr.log", "verify.stdout.log", "verify.stderr.log",
    "prompt.txt", "model-result.json", "submission.json", "changes.json", "changes.diff",
)
WEB_DIR = Path(__file__).resolve().with_name("web")
STATIC_ASSETS = {
    "/": ("index.html", "text/html"),
    "/index.html": ("index.html", "text/html"),
    "/app.js": ("app.js", "text/javascript"),
    "/sessions.js": ("sessions.js", "text/javascript"),
    "/style.css": ("style.css", "text/css"),
    "/shell.js": ("shell.js", "text/javascript"),
    "/shell-agentics.js": ("shell-agentics.js", "text/javascript"),
    "/shell-agentics.css": ("shell-agentics.css", "text/css"),
    "/shell-library.js": ("shell-library.js", "text/javascript"),
    "/shell-library.css": ("shell-library.css", "text/css"),
    "/fonts/inter-latin.woff2": ("fonts/inter-latin.woff2", "font/woff2"),
    "/fonts/dm-mono-latin.woff2": ("fonts/dm-mono-latin.woff2", "font/woff2"),
    "/fonts/dm-mono-medium-latin.woff2": ("fonts/dm-mono-medium-latin.woff2", "font/woff2"),
}
SOURCE_ERRORS = (OSError, sqlite3.Error, ValueError, KeyError, IndexError, TypeError, AttributeError, RuntimeError)


class RequestError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def path_segment(value: str, label: str) -> None:
    if (not isinstance(value, str) or not value or value in (".", "..")
            or any(char in value for char in "/\\")
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise RequestError(400, f"{label} must be one path segment.")


def run_path(runs_dir: Path, run_id: str) -> Path:
    """Resolve one run identifier, never an arbitrary filesystem path."""
    path_segment(run_id, "Run ID")
    path = (runs_dir / run_id).resolve()
    if path == runs_dir or not path.is_relative_to(runs_dir):
        raise RequestError(403, "Run is outside the selected runs directory.")
    if not path.is_dir() and not (runs_dir / ".opermem-preparations" / run_id / "binding.json").is_file():
        raise RequestError(404, "Run or preparation not found.")
    if not (path / "events.sqlite3").resolve().is_relative_to(path):
        raise RequestError(403, "Journal is outside its run directory.")
    return path


def read_controller(path: Path) -> dict | None:
    store = path / "controller.sqlite3"
    if not store.exists() and not store.is_symlink():
        return None
    if not store.resolve().is_relative_to(path):
        raise RequestError(403, "Controller is outside its run directory.")
    state = controller.inspect_run(store)
    # Validate the view's required shape, not the kernel's transition rules.
    if state["status"] not in ("active", "completed", "blocked", "failed", "cancelled"):
        raise ValueError("Invalid controller status")
    for key in ("actors", "activations", "artifacts", "slots", "visits"):
        if not isinstance(state[key], dict):
            raise ValueError(f"Invalid controller {key}")
    phase = state["pattern"]["phases"][state["phase_index"]]["id"]
    state["visits"][phase]
    if not isinstance(state["events"], list):
        raise ValueError("Invalid controller events")
    for activation in state["activations"].values():
        state["actors"][activation["actor_id"]]
    if state["current_activation"] is not None:
        state["activations"][state["current_activation"]]
    return state


def controller_summary(state: dict) -> dict:
    phase = state["pattern"]["phases"][state["phase_index"]]["id"]
    activation = state["activations"].get(state["current_activation"])
    return {
        "state": state["status"], "state_source": "controller.sqlite3",
        "controller_version": state["version"], "pattern": state["pattern"].get("name", state["pattern"]["kind"]),
        "pattern_kind": state["pattern"]["kind"], "machine_state": state["machine_state"],
        "current_phase": phase, "generation": state["generation"], "visit": state["visits"][phase],
        "returns_used": state["returns_used"], "max_returns": state["max_returns"],
        "max_remediations": state["max_remediations"], "current_activation": state["current_activation"],
        "current_actor": activation["actor_id"] if activation else None,
        "current_ordinal": activation["ordinal"] if activation else None,
    }


def read_run(runs_dir: Path, run_id: str) -> tuple[Path, list[dict], dict, dict | None]:
    path = run_path(runs_dir, run_id)
    events = runtime.read_events(path)
    if any(not isinstance(event["data"], dict) for event in events):
        raise ValueError("event data must be an object")
    status = runtime.project(events)
    if status["run_id"] != run_id or not isinstance(status["goal"], str):
        raise ValueError("run identity or goal is invalid")
    kernel = read_controller(path)
    if kernel is not None:
        status = {**status, "journal_state": status["state"], **controller_summary(kernel)}
    return path, events, status, kernel


def run_summaries(runs_dir: Path, *, app=None, selection=None) -> tuple[list[dict], list[str]]:
    runs, included, warnings = [], set(), []
    if app and app.namespace_path.exists():
        native_rows, native_warnings = app.reviewed().summaries(selection)
        runs.extend(native_rows)
        warnings.extend(native_warnings)
        included.update((runs_dir / row["run_id"]).resolve() for row in native_rows)
    children = sorted(runs_dir.iterdir()) if runs_dir.exists() else []
    for candidate in children:
        if candidate.resolve() in included or not candidate.is_dir() or not (candidate / "events.sqlite3").exists():
            continue
        try:
            correlation = app.run_authority(candidate, selection) if app else None
            path, _, status, kernel = read_run(runs_dir, candidate.name)
            summary = {"run_id": candidate.name, "directory": str(path), "goal": status["goal"], "state": status["state"]}
            info = application.runtime_info(path, kernel)
            config = info["configuration"]
            population = []
            if kernel:
                for actor in kernel["activations"].values():
                    model = (config.get("qa_model") or config.get("model")) if actor["mode"] == "review" else config.get("model")
                    population.append({**{key: actor.get(key) for key in (
                        "id", "actor_id", "ordinal", "role", "phase", "generation", "visit", "status", "session_ref")},
                        "configured_model": model, "configured_provider": model.split("/")[0] if model and "/" in model else None,
                        "client": config.get("client")})
            attention = []
            if kernel:
                if kernel["status"] in ("blocked", "failed") or info["activity"] in ("failed", "intervention"):
                    attention.append({"kind": info["activity"], "message": kernel.get("reason") or info["reason"],
                                      "activation_id": kernel["current_activation"]})
                for artifact in kernel["artifacts"].values():
                    content = artifact["content"]
                    if artifact["type"] == "qa.review" and content.get("verdict", content.get("outcome")) == "fail":
                        attention.append({"kind": "QA findings", "artifact_id": artifact["id"], "activation_id": artifact["activation_id"],
                                          "message": content["report"], "phase": artifact["phase"]})
                    elif artifact["type"] == "cognition.feedback":
                        attention.append({"kind": "Return", "artifact_id": artifact["id"], "activation_id": artifact["activation_id"],
                                          "message": f"{content['from']} -> {content['target']}: {content['reason']}", "phase": artifact["phase"]})
            runs.append({**summary, "last_event_at": status["last_event_at"], "workspace": status["workspace"],
                         "application": info, "population": population, "attention": attention, "correspondence": correlation,
                         "goal_ref": status["goal_ref"], "telos": status.get("telos"),
                         **(controller_summary(kernel) if kernel is not None else {})})
            included.add(path)
        except application.ApplicationError as exc:
            included.add(candidate.resolve())
            if not (selection and selection["kind"] == "effort" and any(reason in str(exc) for reason in (
                    "Requested effort does not own this run", "Unassigned run has no requested effort ownership"))):
                warnings.append(f"Run {candidate.name}: {exc}")
            continue
        except (RequestError, *SOURCE_ERRORS):
            continue
    if runs_dir.exists():
        for child in sorted(runs_dir.iterdir()):
            if child.is_dir() and (child / "events.sqlite3").exists() and child.resolve() not in included:
                warnings.append(f"Run {child.name} is unreadable, malformed, or outside the selected root; omitted.")
    runs.sort(key=lambda row: (row["last_event_at"], row["run_id"]), reverse=True)
    return runs, warnings


def run_detail(runs_dir: Path, run_id: str, *, app=None, selection=None) -> dict:
    if app and app.namespace_path.exists() and app.reviewed().binding(run_id, selection) is not None:
        return app.reviewed().detail(run_id, selection)
    path, events, status, kernel = read_run(runs_dir, run_id)
    artifacts = {}
    for name in ARTIFACT_NAMES:
        source = path / name
        try:
            if not source.resolve().is_relative_to(path):
                raise ValueError("Artifact is outside its run directory.")
            with source.open("rb") as stream:
                content = stream.read(ARTIFACT_LIMIT + 1)
            artifacts[name] = {
                "source_path": str(source),
                "text": content[:ARTIFACT_LIMIT].decode("utf-8", errors="replace"),
                "truncated": len(content) > ARTIFACT_LIMIT,
            }
        except FileNotFoundError:
            continue
        except (OSError, ValueError, RuntimeError) as exc:
            artifacts[name] = {"error": str(exc)}
    return {"status": status, "events": events, "artifacts": artifacts, "controller": kernel,
            "application": application.runtime_info(path, kernel),
            "controller_path": str(path / "controller.sqlite3") if kernel is not None else None,
            "cancel_requested": (path / "cancel.requested").exists() if kernel is not None else False,
            "journal_path": str(path / "events.sqlite3"), "artifact_limit_bytes": ARTIFACT_LIMIT}


def actor_log(runs_dir: Path, run_id: str, activation_id: str, name: str, *, tail: bool = False) -> dict:
    path_segment(activation_id, "Activation ID")
    if name not in ACTOR_ARTIFACT_NAMES:
        raise RequestError(400, "Unknown actor log filename.")
    path = run_path(runs_dir, run_id)
    kernel = read_controller(path)
    if kernel is None or activation_id not in kernel["activations"]:
        raise RequestError(404, "Activation not found in the controller.")
    directory = (path / "activations" / activation_id).resolve()
    source = directory / name
    if not directory.is_relative_to(path) or not source.resolve().is_relative_to(directory):
        raise RequestError(403, "Actor log is outside its activation directory.")
    try:
        with source.open("rb") as stream:
            offset = 0
            if tail:
                size = stream.seek(0, 2)
                offset = max(0, size - ARTIFACT_LIMIT)
                stream.seek(offset)
                if offset:
                    stream.readline(ARTIFACT_LIMIT)
                    offset = stream.tell()
            content = stream.read(ARTIFACT_LIMIT + 1)
    except FileNotFoundError:
        raise RequestError(404, "Actor log not retained.") from None
    return {"run_id": run_id, "activation_id": activation_id, "name": name,
            "artifact_limit_bytes": ARTIFACT_LIMIT, "source_path": str(source),
            "text": content[:ARTIFACT_LIMIT].decode("utf-8", errors="replace"),
            "truncated": offset > 0 or len(content) > ARTIFACT_LIMIT, "byte_start": offset}


def legacy_transcript(runs_dir: Path, run_id: str, role: str) -> dict:
    if role not in ("work", "review"):
        raise RequestError(404, "Worker or reviewer session not found.")
    path, events, _, kernel = read_run(runs_dir, run_id)
    if kernel is not None:
        raise RequestError(404, "Use the controller activation transcript for this run.")
    source = path / f"{role}.stdout.log"
    if not source.resolve().is_relative_to(path):
        raise RequestError(403, "Session log is outside its run directory.")
    try:
        with source.open("rb") as stream:
            size = stream.seek(0, 2)
            offset = max(0, size - ARTIFACT_LIMIT)
            stream.seek(offset)
            if offset:
                stream.readline(ARTIFACT_LIMIT)
                offset = stream.tell()
            content = stream.read(ARTIFACT_LIMIT + 1)
    except FileNotFoundError:
        raise RequestError(404, "Session output not retained.") from None
    config = next((event["data"] for event in reversed(events)
                   if event["kind"] == "program.started"), {})
    retained = application.read_json(path / f"{role}.json", path, {})
    client = retained.get("client") or config.get("client")
    command = next((event["data"].get("argv", []) for event in reversed(events)
                    if event["kind"] == "step.started" and event["data"].get("step") == role), [])
    model = config.get("model") if role == "work" else None
    if "--model" in command and command.index("--model") + 1 < len(command):
        model = command[command.index("--model") + 1]
    text = content[:ARTIFACT_LIMIT].decode("utf-8", errors="replace")
    return {"run_id": run_id, "role": role, "source_path": str(source), "text": text,
            "byte_start": offset, "truncated": offset > 0 or len(content) > ARTIFACT_LIMIT,
            "artifact_limit_bytes": ARTIFACT_LIMIT,
            "configuration": {"client": client, "model": model, "qa_model": None},
            **application.transcript(text, client)}


def search_runs(runs_dir: Path, query: str, limit: int = 20) -> dict:
    with closing(sqlite3.connect(":memory:")) as connection:
        memory.index_runs(connection, runs_dir)
        # The existing indexer discovers local files. Exclude out-of-root sources
        # from this disposable index before matching or applying the result limit.
        for rowid, run_id, source_path in connection.execute(
            "SELECT rowid, run_id, source_path FROM memory"
        ).fetchall():
            try:
                path = run_path(runs_dir, run_id)
                source = Path(source_path)
                allowed = (source.parent == path and source.name in
                           ("events.sqlite3", "work.md", "review.md")
                           and source.resolve().is_relative_to(path))
            except (RequestError, *SOURCE_ERRORS):
                allowed = False
            if not allowed:
                connection.execute("DELETE FROM memory WHERE rowid = ?", (rowid,))
        count = connection.execute("SELECT count(*) FROM memory").fetchone()[0]
        matches = memory.search(connection, query, limit)
    return {"query": query, "matches": matches, "indexed_entries": count, "limit": limit}


def project_file(workspace, reference):
    if not isinstance(reference, str) or not reference.strip() or "\0" in reference or len(reference) > 4096:
        raise RequestError(400, "Choose a project file.")
    base = Path(workspace).resolve()
    target = (base / reference).resolve()
    if not target.is_relative_to(base) or ".git" in target.relative_to(base).parts:
        raise RequestError(400, "File is outside the selected project content.")
    if not target.is_file():
        raise RequestError(404, "Project file not found.")
    with target.open("rb") as stream:
        data = stream.read(256 * 1024 + 1)
    if len(data) > 256 * 1024:
        raise RequestError(413, "Project file exceeds the source-view limit (256 KiB).")
    try:
        value = data.decode("utf-8")
    except UnicodeDecodeError:
        raise RequestError(415, "Source view supports UTF-8 text files.") from None
    return {"path": str(target), "text": value}


def create_server(runs_dir: Path | str, host: str = "127.0.0.1", port: int = 8765,
                  *, telos_db: Path | None = None, telos_source: Path | None = None,
                  session_command: list[str] | None = None, namespace_path: Path | None = None, opermem_host: Path | None = None) -> ThreadingHTTPServer:
    """Create, but do not start, the server. Port 0 asks the OS for a free port."""
    root = Path(runs_dir).expanduser().resolve()
    sessions = developer_sessions.SessionService(root, pi_command=session_command, namespace_path=namespace_path)
    app = application.Application(root, telos_db=telos_db, telos_source=telos_source, opermem_host=opermem_host,
                                  namespace_path=sessions.registry.domain.path, sessions_home=root)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args) -> None:
            pass

        def send_error(self, code, message=None, explain=None) -> None:
            self.json_response(code, {"error": self.responses.get(code, ("Request failed",))[0]})

        def respond(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def json_response(self, status: int, payload: dict) -> None:
            self.respond(status, json.dumps(payload, ensure_ascii=True).encode("utf-8"),
                         "application/json; charset=utf-8")

        def do_GET(self) -> None:
            try:
                url = urlsplit(self.path)
                path = unquote(url.path)
                if path in STATIC_ASSETS:
                    name, content_type = STATIC_ASSETS[path]
                    if content_type.startswith("text/"):
                        content_type += "; charset=utf-8"
                    self.respond(200, (WEB_DIR / name).read_bytes(), content_type)
                    return
                params = parse_qs(url.query)
                effort_root = params.get("effort_root", [None])[0]
                def cursor(name, default=None):
                    try:
                        return int(params[name][0]) if name in params else default
                    except ValueError:
                        raise RequestError(400, f"{name} must be an integer.") from None
                if path == "/api/opermem/stores":
                    selection = app.selection({key: params[key][0] for key in ("scope", "effort_root") if key in params})
                    result = app.reviewed().registrations(selection)
                elif path == "/api/application/launches":
                    selection = app.selection({key: params[key][0] for key in ("scope", "effort_root") if key in params})
                    result = app.reviewed().launches(selection)
                elif path.startswith("/api/application/launches/"):
                    launch_id = path.rsplit("/", 1)[1]
                    if len(launch_id) != 64 or any(c not in "0123456789abcdef" for c in launch_id):
                        raise RequestError(400, "Invalid launch receipt identity")
                    selection = app.selection({key: params[key][0] for key in ("scope", "effort_root") if key in params})
                    result = app.reviewed().launch_receipt(root / ".opermem-launches" / launch_id, selection)
                elif path == "/api/disciplines":
                    params = parse_qs(url.query, keep_blank_values=True)
                    if set(params) - {"scope", "effort_root", "after", "limit"} or any(len(value) != 1 or not value[0] for value in params.values()):
                        raise RequestError(400, "Catalog accepts one nonempty scope, effort_root, after and limit value.")
                    selection = app.selection({key: params[key][0] for key in ("scope", "effort_root") if key in params})
                    result = app.discipline_catalog(selection, after=cursor("after", 0), limit=cursor("limit", 100))
                elif path == "/api/efforts":
                    page = sessions.branch("0", after=cursor("after", 0), limit=cursor("limit", 100))
                    result = {**page, "namespace_path": str(sessions.registry.domain.path)}
                elif path.startswith("/api/ordinals/"):
                    suffix = path[len("/api/ordinals/"):].split("/")
                    ordinal = suffix[0]
                    if len(suffix) == 1:
                        result = {"position": sessions.position(ordinal, effort_root=effort_root)}
                    elif len(suffix) == 2 and suffix[1] in ("history", "branch"):
                        options = {"effort_root": effort_root, "after": cursor("after", 0), "limit": cursor("limit", 100)}
                        if suffix[1] == "history":
                            options.update(instantiation=cursor("instantiation"), session=cursor("session"))
                        result = getattr(sessions, suffix[1])(ordinal, **options)
                    else:
                        raise RequestError(404, "Unknown ordinal read.")
                elif path == "/api/skills/cost-estimate":
                    params = parse_qs(url.query, keep_blank_values=True)
                    if set(params) - {"scope", "effort_root"} or any(len(value) != 1 or not value[0] for value in params.values()):
                        raise RequestError(400, "Cost skill accepts one explicit nonempty scope or effort_root.")
                    selection = app.selection({key: value[0] for key, value in params.items()})
                    app.operation_scope(selection)
                    result = costs.inspect(app, selection, accounting=usage.project(sessions, selection))
                elif path == "/api/usage":
                    params = parse_qs(url.query, keep_blank_values=True)
                    if set(params) - {"scope", "effort_root"} or any(len(value) != 1 or not value[0] for value in params.values()):
                        raise RequestError(400, "Usage accepts one explicit nonempty scope or effort_root.")
                    selection = app.selection({key: value[0] for key, value in params.items()})
                    app.operation_scope(selection)
                    result = usage.project(sessions, selection)
                elif path == "/api/developer-sessions":
                    result = {"sessions": sessions.list(effort_root), "namespace_path": str(sessions.registry.domain.path), "runs_dir": str(root), "projects_root": str(developer_sessions.projects.DEFAULT_PROJECT_ROOT)}
                elif path.startswith("/api/developer-sessions/"):
                    suffix = path[len("/api/developer-sessions/"):].split("/")
                    sid = suffix[0]
                    if "instantiation" in params or "session" in params:
                        sid = {"ordinal": sid, "instantiation": cursor("instantiation"), "session": cursor("session")}
                    params = parse_qs(url.query)
                    if len(suffix) == 2 and suffix[1] == "file":
                        item = sessions.select(sid, effort_root=effort_root)
                        result = project_file(item["workspace"], params.get("path", [""])[0])
                    elif len(suffix) == 1:
                        try:
                            after = int(params.get("after", ["0"])[0])
                        except ValueError:
                            raise RequestError(400, "Event cursor must be an integer.") from None
                        result = sessions.detail(sid, after, effort_root=effort_root, limit=cursor("limit", 500))
                    else:
                        raise RequestError(404, "Not found.")
                elif path == "/api/runs":
                    selection = app.selection({key: params[key][0] for key in ("scope", "effort_root") if key in params})
                    if selection["kind"] == "effort":
                        app.operation_scope(selection)
                    runs, warnings = run_summaries(root, app=app, selection=selection)
                    result = {"runs": runs, "warnings": warnings, "runs_dir": str(root), "selection": selection,
                              "coverage": "partial" if warnings else "complete"}

                elif path.startswith("/api/runs/"):
                    parts = path[len("/api/runs/"):].split("/")
                    selection = app.selection({key: params[key][0] for key in ("scope", "effort_root") if key in params})
                    correlation = app.run_authority(run_path(root, parts[0]), selection)
                    if correlation.get("backend") == application.reviewed.BACKEND:
                        if len(parts) == 1:
                            result = run_detail(root, parts[0], app=app, selection=selection)
                        elif len(parts) == 2 and parts[1] == "reuse-setup":
                            result = app.reviewed().reuse(parts[0], selection)
                        elif len(parts) == 4 and parts[1] == "sessions" and parts[3] == "transcript":
                            if parts[2] not in ("work", "review"):
                                raise RequestError(400, "Choose the actual work or review participant")
                            participant = next((p for p in correlation["participants"] if p["step"] == parts[2]), None)
                            if participant is None or participant["observation"] is None:
                                raise RequestError(404, "Participant has no observed transcript")
                            source = application.contained(Path(participant["observation"]["stdout"]), root / parts[0])
                            text = source.read_text()[:ARTIFACT_LIMIT]
                            result = {"role": parts[2], "target": participant["target"], "text": text, **application.transcript(text, participant["native_session_ref"]["client"] if participant["native_session_ref"] else None)}
                        else:
                            raise RequestError(409, "Reviewed inquiry has no controller Apply or conversational continuation")
                    elif len(parts) == 2 and parts[1] == "reuse-setup":
                        run, _, status, kernel = read_run(root, parts[0])
                        result = application.reuse_setup(run, kernel, status)
                    elif len(parts) == 2 and parts[1] == "project-file":
                        _, _, status, kernel = read_run(root, parts[0])
                        result = project_file(kernel["workspace"] if kernel else status["workspace"], parse_qs(url.query).get("path", [""])[0])
                    elif len(parts) == 2 and parts[1] == "project-changes":
                        result = app.project_changes(run_path(root, parts[0]), selection=selection)
                    elif len(parts) == 5 and parts[1] == "activations" and parts[3] == "logs":
                        result = actor_log(root, parts[0], parts[2], parts[4])
                    elif len(parts) == 4 and parts[1] == "activations" and parts[3] == "transcript":
                        result = actor_log(root, parts[0], parts[2], "actor.stdout.log", tail=True)
                        config = application.runtime_info(run_path(root, parts[0]), read_controller(run_path(root, parts[0])))["configuration"]
                        result.update(application.transcript(result["text"], config.get("client")))
                        result["configuration"] = config
                    elif len(parts) == 4 and parts[1] == "sessions" and parts[3] == "transcript":
                        result = legacy_transcript(root, parts[0], parts[2])
                    else:
                        result = run_detail(root, path[len("/api/runs/"):])
                    result["correspondence"] = correlation
                elif path == "/api/configuration":
                    result = app.configuration()
                elif path == "/api/diagnostics":
                    result = app.diagnostics()
                elif path == "/api/goals" or path.startswith("/api/goals/"):
                    selection = app.selection({key: params[key][0] for key in ("scope", "effort_root") if key in params})
                    include_legacy = params.get("include_legacy", ["false"])[0]
                    if include_legacy not in ("true", "false"):
                        raise RequestError(400, "include_legacy must be true or false.")
                    result = app.goals(selection, include_legacy=include_legacy == "true")
                    if path.startswith("/api/goals/"):
                        goal_id = path[len("/api/goals/"):]
                        matched = [item for item in result["purposes"] if item["reference"]["chain_id"] == goal_id
                                   and ("store_id" not in params or item["reference"]["store_id"] == params["store_id"][0])]
                        if len(matched) != 1:
                            if not matched and result["coverage"] != "complete":
                                raise RequestError(422, "Purpose lookup has unavailable source stores; inspect scoped purposes for their errors.")
                            raise RequestError(404 if not matched else 409, "Purpose absent or ambiguous; select its owning store.")
                        result = {"purpose": matched[0], "coverage": result["coverage"]}
                elif path == "/api/search":
                    params = parse_qs(url.query, keep_blank_values=True)
                    try:
                        limit = max(1, min(100, int(params.get("limit", ["20"])[0])))
                    except ValueError:
                        raise RequestError(400, "Search limit must be an integer.") from None
                    if "ordinal" in params:
                        selection = {"kind": "session" if "instantiation" in params or "session" in params else "ordinal",
                                     "ordinal": params["ordinal"][0]}
                        if effort_root is not None:
                            selection["effort_root"] = effort_root
                        if selection["kind"] == "session":
                            selection.update(instantiation=cursor("instantiation"), session=cursor("session"))
                    else:
                        selection = app.selection({key: params[key][0] for key in ("scope", "effort_root") if key in params})
                    result = app.lexical(params.get("q", [""])[0], selection, limit)
                elif path == "/api/source-preparation":
                    names = ("ordinal", "instantiation", "session", "effort_root", "registry_id", "native_session_id", "sequence", "source_text_sha256")
                    if set(params) != set(names) or any(len(values) != 1 or not values[0].strip() for values in params.values()):
                        raise RequestError(400, "Source preparation accepts exactly one nonempty ordinal, instantiation, session, effort_root, registry_id, native_session_id, sequence and source_text_sha256 parameter.")
                    def selector(name, value, minimum=1):
                        try:
                            number = int(value)
                        except ValueError:
                            raise RequestError(400, f"{name} must be an integer.") from None
                        if number < minimum:
                            raise RequestError(400, f"{name} must be a positive integer.")
                        return number
                    result = app.source_preparation(selection={"kind": "session", "ordinal": params["ordinal"][0],
                        "instantiation": selector("instantiation", params["instantiation"][0]), "session": selector("session", params["session"][0]),
                        "effort_root": params["effort_root"][0]}, registry_id=params["registry_id"][0],
                        native_session_id=params["native_session_id"][0], sequence=selector("sequence", params["sequence"][0]),
                        source_text_sha256=params["source_text_sha256"][0])
                else:
                    raise RequestError(404, "Not found.")
                result = {**result}
                result.setdefault("observed_at", datetime.now(timezone.utc).isoformat())
                self.json_response(200, result)
            except (RequestError, application.ApplicationError, developer_sessions.SessionError) as exc:
                self.json_response(exc.status, {"error": str(exc)})
            except ScopeError as exc:
                self.json_response(422, {"error": f"Cannot resolve selected scope: {exc}"})
            except SOURCE_ERRORS as exc:
                code = 422
                self.json_response(code, {"error": f"Cannot read local evidence: {exc}"})

        do_HEAD = do_GET

        def do_POST(self) -> None:
            try:
                url = urlsplit(self.path)
                path_name = unquote(url.path)
                parts = path_name.split("/")
                run_action = len(parts) == 5 and parts[1:3] == ["api", "runs"] and parts[4] in ("cancel", "pause", "advance", "summary", "apply", "recover-correlation", "recover-contribution")
                session_action = path_name in ("/api/efforts", "/api/legacy-adoptions", "/api/actions", "/api/developer-sessions", "/api/developer-projects") or (
                    len(parts) == 5 and parts[1:3] == ["api", "actions"] and parts[4] == "deliver") or (
                    len(parts) == 5 and parts[1:3] == ["api", "developer-sessions"]
                    and parts[4] in ("prompt", "stop", "shutdown", "reopen", "delegate", "dialog"))
                application_action = path_name in ("/api/opermem/stores", "/api/application/start", "/api/disciplines", "/api/goals", "/api/memory/semantic", "/api/diagnostics/refresh", "/api/skills/cost-estimate/execute")
                if self.command != "POST" or url.query or not (run_action or application_action or session_action):
                    raise RequestError(405, "Read-only route; use an explicit application action endpoint.")
                origin = self.headers.get("Origin")
                if origin is not None and origin != f"http://{self.headers.get('Host')}":
                    raise RequestError(403, "Actions require a same-origin request.")
                if self.headers.get_content_type() != "application/json":
                    raise RequestError(415, "Actions require application/json.")
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    raise RequestError(400, "Invalid JSON request length.") from None
                chat_frame = session_action and (path_name in ("/api/developer-sessions", "/api/developer-projects")
                    or (len(parts) == 5 and parts[1:3] == ["api", "developer-sessions"] and parts[4] == "prompt"))
                limit = attachments.MAX_FRAME_BYTES if chat_frame else (1024 if run_action and parts[4] == "cancel" else 65536)
                if not 0 < length <= limit or self.headers.get("Transfer-Encoding"):
                    raise RequestError(400, f"Send a JSON object of at most {limit} bytes.")
                try:
                    body = json.loads(self.rfile.read(length))
                except (ValueError, UnicodeError):
                    raise RequestError(400, "Invalid JSON request.") from None
                if not isinstance(body, dict):
                    raise RequestError(400, "Request must be a JSON object.")
                if chat_frame and length > 65536:
                    files = body.get("attachments")
                    if not isinstance(files, list) or not files:
                        raise RequestError(400, f"Send a JSON object of at most 65536 bytes unless it carries nonempty attachments within {attachments.MAX_FRAME_BYTES} bytes.")
                code = 200
                if session_action:
                    if path_name == "/api/efforts":
                        result, code = {"effort": sessions.create_effort(body)}, 201
                    elif path_name == "/api/legacy-adoptions":
                        result = sessions.adopt_legacy(body)
                    elif path_name == "/api/actions":
                        if set(body) - {"target", "kind", "payload", "effort_root"}:
                            raise RequestError(400, "Unknown bound action option.")
                        result = sessions.bind(body.get("target"), body.get("kind"), body.get("payload"), effort_root=body.get("effort_root"))
                    elif parts[1:3] == ["api", "actions"]:
                        if set(body) - {"effort_root"}:
                            raise RequestError(400, "Unknown delivery scope option.")
                        try:
                            action_id = int(parts[3])
                        except ValueError:
                            raise RequestError(400, "Action ID must be an integer.") from None
                        result = sessions.deliver(action_id, effort_root=body.get("effort_root"))
                    elif path_name in ("/api/developer-sessions", "/api/developer-projects"):
                        creator = sessions.create_project if path_name == "/api/developer-projects" else sessions.create
                        result, code = {"session": creator(body)}, 201
                    else:
                        sid, action = parts[3], parts[4]
                        body = dict(body)
                        effort_root = body.pop("effort_root", None)
                        if "instantiation" in body or "session" in body:
                            sid = {"ordinal": sid, "instantiation": body.pop("instantiation", None), "session": body.pop("session", None)}
                        if action in ("stop", "shutdown", "reopen"):
                            if body:
                                raise RequestError(400, "This session action accepts an empty object.")
                            result = getattr(sessions, action)(sid, effort_root=effort_root)
                        elif action == "prompt":
                            if set(body) - {"message", "mode", "attachments"}:
                                raise RequestError(400, "Unknown prompt option.")
                            if "attachments" in body and body["attachments"] is None:
                                raise RequestError(400, "Attachments must be a list when present; omit the field to send none.")
                            result = sessions.prompt(sid, body.get("message"), body.get("mode", "prompt"), effort_root=effort_root,
                                **({"attachments": body["attachments"]} if "attachments" in body else {}))
                        else:
                            allowed = {"prompt", "title", "model", "thinking"} if action == "delegate" else {"id", "value", "confirmed", "cancelled"}
                            if set(body) - allowed:
                                raise RequestError(400, "Unknown session action option.")
                            item = sessions.select(sid, effort_root=effort_root, current=True)
                            result = developer_sessions.control(root, item["id"], {"action": action, "parentTarget": item["target"], **body}, timeout=45)
                        if action == "reopen":
                            result = {"session": result}
                elif application_action:
                    if path_name == "/api/skills/cost-estimate/execute":
                        selection = app.selection(body)
                        app.operation_scope(selection)
                        result = costs.execute(app, body, accounting=usage.project(sessions, selection))
                    elif path_name == "/api/opermem/stores":
                        result, code = app.reviewed().register(body), 201
                    elif path_name == "/api/application/start":
                        result, code = app.start(body), 202
                    elif path_name == "/api/disciplines":
                        result, code = app.create_discipline(body), 201
                    elif path_name == "/api/goals":
                        result, code = app.create_goal(body), 201
                    elif path_name == "/api/memory/semantic":
                        result = app.memory(body)
                    else:
                        if body:
                            raise RequestError(400, "Health refresh accepts an empty JSON object.")
                        result = app.diagnostics(refresh=True)
                elif run_action:
                    selection = app.selection(body)
                    path_segment(parts[3], 'Run ID')
                    if parts[4] == 'recover-correlation' and app.namespace_path.exists() and app.reviewed().binding(parts[3], selection) is not None:
                        correlation = {'backend': application.reviewed.BACKEND}
                    else:
                        correlation = app.run_authority(run_path(root, parts[3]), selection)
                    body = {key: value for key, value in body.items() if key not in ("scope", "effort_root")}
                    result = None
                    if correlation.get("backend") == application.reviewed.BACKEND:
                        if parts[4] not in ("recover-correlation", "recover-contribution") or body:
                            raise RequestError(409, "Reviewed inquiry supports explicit correlation/contribution recovery; controller and conversation controls are unavailable")
                        result = app.reviewed().recover(parts[3], selection, parts[4].removeprefix("recover-"))
                    elif parts[4].startswith("recover-"):
                        raise RequestError(409, "This run has no owned reviewed recovery contract")
                    elif parts[4] != "cancel":
                        path = run_path(root, parts[3])
                        kernel = read_controller(path)
                        if parts[4] == "apply":
                            result = app.apply_changes(path, body, selection=selection)
                        elif parts[4] == "summary":
                            result = app.summary(path, body, selection=selection)
                        elif kernel is None:
                            raise RequestError(409, "Legacy run: controller actions unsupported.")
                        elif parts[4] == "advance":
                            result, code = app.advance(path, body, selection=selection), 202
                        else:
                            if body or kernel["status"] != "active":
                                raise RequestError(409, "Pause needs an active pattern and an empty JSON object.")
                            result = {"controller": harness.pause(path), "action": "pause", "status": "requested",
                                      "message": "Pause requested after the current activation; observe the held checkpoint."}
                            code = 202
                if result is not None:
                    result["observed_at"] = datetime.now(timezone.utc).isoformat()
                    self.json_response(code, result)
                    return
                if set(body) != {"confirm"} or body["confirm"] is not True:
                    raise RequestError(400, "Cancellation requires {\"confirm\": true}.")
                path = run_path(root, parts[3])
                kernel = read_controller(path)
                if kernel is None:
                    raise RequestError(409, "Legacy run: controller cleanup unsupported.")
                state = harness.cancel(path)
                pending = state["status"] == "active"
                cleanup = harness.process_info(path, state)
                self.json_response(202 if pending else 200, {
                    "run_id": parts[3], "cancel_requested": (path / "cancel.requested").exists(),
                    "controller": state, "process_cleanup": cleanup,
                    "cleanup_confirmed": cleanup["cleanup_confirmed"],
                    "message": ("Cancellation requested; awaiting the driver. The kernel is still active." if pending
                    else f"Kernel is {state['status']}; terminal outcome unchanged.") +
                    (" Process cleanup confirmed." if cleanup["cleanup_confirmed"] else
                     " Process cleanup unconfirmed. Only known ownership can be terminated; zombies require parent reaping."),
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                })
            except (RequestError, application.ApplicationError, developer_sessions.SessionError) as exc:
                self.json_response(exc.status, {"error": str(exc), "run_id": getattr(exc, "run_id", None)})
            except ScopeError as exc:
                self.json_response(422, {"error": f"Cannot resolve selected scope: {exc}"})
            except SOURCE_ERRORS as exc:
                self.json_response(422, {"error": f"Cannot apply local action: {exc}"})

        do_PUT = do_DELETE = do_PATCH = do_POST

    server = ThreadingHTTPServer((host, port), Handler)
    server.application = app
    server.developer_sessions = sessions
    return server


def open_workspace(port: int) -> None:
    """Check the static local page, then request a plain browser handoff."""
    destination = f"http://127.0.0.1:{port}/"
    try:
        # HTTPConnection neither uses environment proxies nor follows redirects.
        with closing(http.client.HTTPConnection("127.0.0.1", port, timeout=5)) as client:
            client.request("HEAD", "/")
            with client.getresponse() as response:
                status = response.status
                content_type = response.getheader("Content-Type", "").split(";", 1)[0]
    except (OSError, http.client.HTTPException):
        raise ValueError(f"Cannot reach the local GUI at {destination}. Check that it is running and --port matches its listener; no service was started.") from None
    if status != 200 or content_type != "text/html":
        raise ValueError(f"Local GUI readiness check failed (HTTP {status}). Check the running GUI and --port; redirects are not followed and no browser was opened.")
    try:
        subprocess.run([
            sys.executable, "-I", "-c",
            "import sys, webbrowser; sys.exit(0 if webbrowser.open(sys.argv[1], new=2) else 1)",
            destination,
        ], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=15, check=True)
    except (OSError, subprocess.SubprocessError):
        raise ValueError("Browser handoff failed or was refused. Run noetic open from your local graphical session and check the default browser (or BROWSER), then retry. No browser handoff was confirmed.") from None
    print(f"Browser handoff requested for {destination} This does not confirm a rendered tab.")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    opening = bool(argv and argv[0] == "open")
    parser = argparse.ArgumentParser(description=(
        "Request a browser handoff to the already-running local GUI. "
        "Match the serve selectors; no GUI or model is started."
        if opening else __doc__))
    parser.add_argument("--runs-dir", type=Path, default=Path.cwd() / ".runtime/runs")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv[1:] if opening else argv)
    minimum_port = 1 if opening else 0
    if not minimum_port <= args.port <= 65535:
        parser.error(f"--port must be between {minimum_port} and 65535" +
                     ("; select the running GUI's actual port" if opening else ""))
    try:
        if opening:
            open_workspace(args.port)
            return 0
        with create_server(args.runs_dir, port=args.port) as server:
            print(f"noetic-dev workspace: http://127.0.0.1:{server.server_port}/", flush=True)
            print(f"Operator workspace runs: {args.runs_dir.expanduser().resolve()}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
        return 0
    except (OSError, ValueError) as exc:
        print(f"noetic {'open' if opening else 'operator'} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
