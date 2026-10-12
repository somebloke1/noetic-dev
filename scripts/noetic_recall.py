"""Read-only, ownership-first derived recall over explicit application stores."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from contextlib import closing
import json
import hashlib
from pathlib import Path
import sqlite3

from scripts import noetic_local as local
from scripts import noetic_run as runtime
from scripts.noetic_scope import ScopeError

COLLECTOR = "owned-native-journal-current-controller-v2"


def _open(path):
    path = Path(path).expanduser().resolve()
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("BEGIN")
    return db


def _selection(selection):
    if not isinstance(selection, dict):
        raise ScopeError("Recall selection must be an object")
    value = dict(selection)
    kind = value.get("kind")
    allowed = {"kind", "effort_root", "ordinal", "instantiation", "session"}
    if set(value) - allowed or kind not in ("application", "effort", "ordinal", "session"):
        raise ScopeError("Declare application, effort, ordinal or exact session recall scope")
    if kind == "application" and set(value) != {"kind"}:
        raise ScopeError("Application recall does not accept narrower selectors")
    if kind == "effort" and set(value) != {"kind", "effort_root"}:
        raise ScopeError("Effort recall requires its explicit root")
    if kind in ("ordinal", "session") and not isinstance(value.get("ordinal"), str):
        raise ScopeError("Ordinal recall requires an absolute ordinal")
    if kind == "session":
        if any(type(value.get(key)) is not int or value[key] < 1 for key in ("instantiation", "session")):
            raise ScopeError("Exact session recall requires both positive selectors")
    elif {"instantiation", "session"} & value.keys():
        raise ScopeError("Session selectors require exact session scope")
    return value


def _resolve(db, selection):
    metadata = dict(db.execute("SELECT key,value FROM metadata"))
    if metadata.get("schema") != "1" or not metadata.get("namespace"):
        raise ScopeError("Unsupported or incomplete canonical namespace")
    positions = {row["ordinal"]: dict(row) for row in db.execute("SELECT * FROM positions")}
    efforts = {row[0] for row in db.execute("SELECT ordinal FROM efforts")}
    kind = selection["kind"]
    root = selection.get("effort_root")
    if root is not None and (root not in efforts or positions.get(root, {}).get("effort") != root):
        raise ScopeError("Effort root does not exist in this namespace")
    ordinal = selection.get("ordinal", root if kind == "effort" else "0")
    if ordinal not in positions:
        raise ScopeError("Ordinal does not exist in this namespace")
    if root is not None and positions[ordinal]["effort"] != root:
        raise ScopeError("Recall target belongs to a different effort")
    if kind == "application":
        selected = set(positions)
    elif kind == "effort":
        selected = {key for key, row in positions.items() if row["effort"] == root}
    elif kind == "session":
        selected = {ordinal}
    else:
        selected = {ordinal}
        while True:
            children = {key for key, row in positions.items() if row["parent"] in selected}
            if children <= selected:
                break
            selected |= children
    sessions = {}
    for row in db.execute("SELECT s.*, i.current_session, i.status AS instantiation_status "
                          "FROM sessions s JOIN instantiations i "
                          "ON s.ordinal=i.ordinal AND s.instantiation=i.sequence"):
        item = dict(row)
        item["native_ref"] = json.loads(item["native_ref"])
        target = (item["ordinal"], item["instantiation"], item["sequence"])
        item["current"] = (positions[item["ordinal"]]["current_instantiation"] == item["instantiation"]
                           and item["current_session"] == item["sequence"])
        sessions[target] = item
    exact = ((ordinal, selection["instantiation"], selection["session"]) if kind == "session" else None)
    if exact is not None and exact not in sessions:
        raise ScopeError("Exact session does not exist in this namespace")
    return metadata["namespace"], positions, selected, sessions, exact


def _owner(namespace, position=None, target=None, *, current=None, status=None):
    return {"namespace": namespace, "effort_root": position["effort"] if position else None,
            "ordinal": position["ordinal"] if position else None, "target": target,
            "ownership": "assigned" if position else "unassigned-legacy",
            "current": current, "historical": None if current is None else not current,
            "position_status": position["status"] if position else None, "session_status": status,
            "authoritative": False, "semantic_authority": "none"}


def _source(text, *, source_id, source_path, source, source_ref, owner, **fields):
    return {**owner, **fields, "source_id": source_id, "source_path": str(source_path),
            "source": source, "source_ref": source_ref, "source_text_sha256": local.digest(text), "text": text}


def _conversation(record, direction):
    kind = record.get("type")
    if direction == "command" and kind in ("prompt", "steer", "follow_up"):
        return "requested", record.get("message", "")
    if kind == "message_end":
        message = record.get("message", {})
        content = message.get("content", [])
        if isinstance(content, str):
            text = content
        else:
            text = "\n".join(part.get("text", "") for part in content
                             if isinstance(part, dict) and part.get("type") == "text")
        if message.get("errorMessage"):
            text += "\n" + message["errorMessage"]
        return "retained-message", text
    if kind in ("protocol_error", "broker_failed", "auto_retry_end"):
        return "failure-observation", local.canonical(record)
    return None, None


def _opermem_claim(run_dir):
    with closing(_open(run_dir / "events.sqlite3")) as db:
        rows = db.execute("SELECT json_extract(data,'$.namespace_path') AS namespace_path, "
            "json_extract(data,'$.effort_root') AS effort_root, json_extract(data,'$.execution_id') AS execution_id "
            "FROM events WHERE kind='scope.bound'").fetchall()
    if rows:
        if len(rows) != 1:
            raise ScopeError("Owned Opermem run has conflicting scope metadata")
        return dict(rows[0])
    return {} if (run_dir / "opermem-scope.json").exists() else None


def _opermem_participants(adapter, binding):
    """Only retained identity metadata; no client stdout or report is opened."""
    participants = []
    for step in ("work", "review"):
        event = adapter._event("run:" + binding["run_id"] + ":participant:" + step)
        if event is None:
            continue
        position = adapter.store.position(event["ordinal"])
        session_event = adapter._event("run:" + binding["run_id"] + ":native:" + step + ":session")
        observation = adapter._event("run:" + binding["run_id"] + ":observation:" + step)
        target, native, status = None, None, None
        if session_event:
            target = {"ordinal": event["ordinal"], "instantiation": session_event["instantiation"], "session": session_event["session"]}
            session = next(s for s in adapter.store.sessions(target["ordinal"], target["instantiation"])
                           if s["sequence"] == target["session"])
            native, status = session["native_ref"], session["status"]
        participants.append({"step": step, "ordinal": position["ordinal"], "target": target,
            "native_session_ref": native, "session_status": status,
            "observation": observation["data"] if observation else None})
    return participants


def _opermem_sources(run_dir, correlation, namespace, positions, selected, sessions, exact, selection):
    from scripts import noetic_develop as develop
    root = correlation["effort_root"]
    if correlation["namespace"] != namespace["id"] or correlation["namespace_path"] != namespace["path"]:
        raise ScopeError("Owned Opermem run belongs to another declared namespace")
    if root not in positions or positions[root]["effort"] != root:
        raise ScopeError("Owned Opermem effort is absent from the declared namespace")
    if selection["kind"] != "application" and not any(positions[o]["effort"] == root for o in selected):
        return []
    result = []
    for part in correlation["participants"]:
        target = part["target"]
        key = (target["ordinal"], target["instantiation"], target["session"]) if target else None
        if part["ordinal"] not in selected or exact and key != exact:
            continue
        native = sessions.get(key)
        owner = _owner(namespace, positions[part["ordinal"]], target,
                       current=native["current"] if native else None, status=native["status"] if native else None)
        observed = part["observation"]
        if observed is None:
            continue
        path = Path(observed["stdout"])
        if target and (observed.get("native_ref") != part["native_session_ref"] or observed.get("target") != target):
            raise ScopeError("Actual selected participant observation correspondence is incomplete")
        raw = path.read_bytes() if path.exists() else b""
        if hashlib.sha256(raw).hexdigest() != observed["stdout_sha256"]:
            raise ScopeError("Captured selected actor evidence changed or is unavailable")
        actual = [e for e in runtime.read_events(run_dir) if e["kind"] in ("step.started", "step.finished") and e["data"]["step"] == part["step"]]
        if actual != observed["step_events"]:
            raise ScopeError("Selected actor events differ from retained observation")
        if target and part["session_status"] == "closed":
            text = develop.parse_transcript(path, part["native_session_ref"]["client"])["text"]
            report = run_dir / (part["step"] + ".md")
            if report.exists() and report.read_text() != text + "\n":
                raise ScopeError("Derived actor report differs from its captured native session")
        else:
            text = local.canonical(observed)
        result.append(_source(text, source_id=f"{run_dir.name}:opermem:{part['step']}", source_path=path,
            source="opermem-actor-report" if target else "opermem-reservation-observation",
            source_ref={"stdout_sha256": observed["stdout_sha256"], "step": part["step"]}, owner=owner,
            field="opermem-actor", collection="retained-actual-session", run_id=run_dir.name,
            source_namespace={"kind": "native-client", "session_id": part["native_session_ref"]["session_id"] if target else None}))
    # Run-global evidence belongs to the execution initiator, never either actor.
    if exact is None and correlation["initiator"] in selected:
        owner = _owner(namespace, positions[correlation["initiator"]])
        link = correlation["native_link"]
        entries = [("native-context", link["context"], "whole-historical-native-packets"),
                   ("host-source-occasion", {"sources": correlation["host_sources"], "occasion": correlation["occasion_selection"],
                    "native_retained_experience": False}, "explicit-host-evidence")]
        for field, value, collection in entries:
            result.append(_source(local.canonical(value), source_id=f"{run_dir.name}:opermem:{field}",
                source_path=run_dir / "opermem-link.json", source=field,
                source_ref={"execution_id": correlation["execution_id"]}, owner=owner, field=field,
                collection=collection, run_id=run_dir.name, source_namespace={"kind": "store-qualified-opermem",
                    **correlation["native_store_identity"], "run_id": run_dir.name},
                native_semantic_authority="retained packet only; no current admission or promotion"))
    return result


def collect(*, namespace_path, sessions_home, runs_dir, selection):
    """Resolve ownership before reading text. Errors remain visible in coverage."""
    selection = _selection(selection)
    namespace_path = Path(namespace_path).expanduser().resolve()
    sessions_home, runs_dir = Path(sessions_home).resolve(), Path(runs_dir).resolve()
    sources, diagnostics = [], []
    coverage = {"canonical": "complete-retained-records-including-correlated-controller-history", "developer_journal": "complete", "controller": "current-bindings-only",
                "native_context": "references-only", "developer_events_scanned": 0,
                "streaming_events_excluded": 0, "unassigned_excluded": 0, "foreign_excluded": 0,
                "controller_excluded_artifacts": 0}

    def diagnostic(component, path, error):
        diagnostics.append({"component": component, "path": str(path), "error": str(error)})

    opermem_executions = {}
    namespace_registered = namespace_path.exists()
    if not namespace_registered and selection["kind"] == "application":
        namespace = {"id": None, "path": str(namespace_path)}
        positions, selected, sessions, exact = {}, set(), {}, None
        coverage["canonical"] = "not-registered"
    else:
        try:
            with closing(_open(namespace_path)) as db:
                namespace_id, positions, selected, sessions, exact = _resolve(db, selection)
                namespace = {"id": namespace_id, "path": str(namespace_path)}
                for row in db.execute("SELECT e.id, d.effort, json_extract(e.native_ref,'$.run_dir') AS run_dir, "
                        "json_extract(e.native_ref,'$.initiator') AS initiator FROM executions e JOIN disciplines d ON d.id=e.discipline_id "
                        "WHERE json_extract(e.native_ref,'$.version')='noetic-opermem-preparation/v1'"):
                    opermem_executions[row["run_dir"]] = dict(row)
                for ordinal in sorted(selected):
                    position = positions[ordinal]
                    after = 0
                    while True:
                        sql = "SELECT * FROM history WHERE ordinal=? AND sequence>?"
                        args = [ordinal, after]
                        if exact:
                            sql += " AND instantiation=? AND session=?"
                            args += [exact[1], exact[2]]
                        rows = db.execute(sql + " ORDER BY sequence LIMIT 500", args).fetchall()
                        if not rows:
                            break
                        after = rows[-1]["sequence"]
                        for event in rows:
                            if event["kind"] == "native-event":
                                continue
                            target = ({"ordinal": ordinal, "instantiation": event["instantiation"], "session": event["session"]}
                                      if event["session"] is not None else None)
                            session = sessions.get((ordinal, event["instantiation"], event["session"]))
                            owner = _owner(namespace, position, target, current=session["current"] if session else None,
                                           status=session["status"] if session else None)
                            sources.append(_source(event["data"], source_id=f"{namespace_id}:history:{event['sequence']}",
                                source_path=namespace_path, source=event["kind"],
                                source_ref=json.loads(event["source_ref"]), owner=owner,
                                event_sequence=event["sequence"], occurred_at=event["at"], field="canonical-history",
                                collection="historical-observation", record_status="as-recorded-at-occurrence"))
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
            raise ScopeError(f"Cannot resolve declared recall namespace {namespace_path}: {exc}") from exc

    registry_path = sessions_home / "developer-sessions" / "sessions.sqlite3"
    try:
        with closing(_open(registry_path)) as db:
            columns = {row[1] for row in db.execute("PRAGMA table_info(sessions)")}
            required = {"id", "ordinal", "status", "native_session_id", "native_session_file"}
            if not required <= columns:
                raise ScopeError("Unsupported developer registry schema")
            fields = ["id", "root_id", "parent_id", "ordinal", "status", "native_session_id", "native_session_file"]
            fields += [key for key in ("global_ordinal", "effort_root", "instantiation", "session_selector") if key in columns]
            identities = [dict(row) for row in db.execute("SELECT " + ",".join(fields) + " FROM sessions ORDER BY id")]
            retained_ids = {item["id"] for item in identities}
            for target_key, item in sessions.items():
                registry_id = item["native_ref"].get("registry_id")
                if target_key[0] in selected and (exact is None or target_key == exact) and registry_id and registry_id not in retained_ids:
                    diagnostic("developer-session", registry_path, f"Retained canonical target {target_key} has unavailable registry source {registry_id}")
                    coverage["developer_journal"] = "partial"
            for item in identities:
                try:
                    ordinal = item.get("global_ordinal") or item["ordinal"]
                    root = item.get("effort_root")
                    selectors = (item.get("instantiation"), item.get("session_selector"))
                    if root is None and selectors == (None, None) and not item.get("global_ordinal"):
                        if selection["kind"] != "application":
                            coverage["unassigned_excluded"] += 1
                            continue
                        owner = _owner(namespace)
                    else:
                        if not namespace_registered:
                            raise ScopeError("Registry claims assigned ownership but the declared namespace is not registered")
                        position = positions.get(ordinal)
                        if position is None or position["effort"] != root:
                            raise ScopeError("Registry ownership has no matching canonical position/effort")
                        if ordinal not in selected:
                            coverage["foreign_excluded"] += 1
                            continue
                        target_key = (ordinal, *selectors)
                        if exact and target_key != exact:
                            continue
                        if selectors == (None, None):
                            owner = _owner(namespace, position, status=item["status"])
                        else:
                            native = sessions.get(target_key)
                            if native is None:
                                raise ScopeError("Registry exact target is absent from canonical sessions")
                            ref = native["native_ref"]
                            if ref.get("registry_id") != item["id"] or ref.get("session_id") != item["native_session_id"]:
                                raise ScopeError("Registry native identity disagrees with canonical session")
                            target = {"ordinal": ordinal, "instantiation": selectors[0], "session": selectors[1]}
                            owner = _owner(namespace, position, target, current=native["current"], status=native["status"])
                    after = 0
                    while True:
                        events = db.execute("SELECT * FROM events WHERE session_id=? AND sequence>? ORDER BY sequence LIMIT 500",
                                            (item["id"], after)).fetchall()
                        if not events:
                            break
                        after = events[-1]["sequence"]
                        for event in events:
                            coverage["developer_events_scanned"] += 1
                            record = json.loads(event["record"])
                            disposition, text = _conversation(record, event["direction"])
                            if disposition is None:
                                coverage["streaming_events_excluded"] += 1
                                continue
                            if isinstance(text, str) and text.strip():
                                sources.append(_source(text, source_id=f"developer:{registry_path}:{item['root_id']}:{item['id']}:{event['sequence']}",
                                    source_path=registry_path, source=record.get("type"), owner=owner,
                                    source_ref={"journal": str(registry_path), "session_id": item["id"], "sequence": event["sequence"],
                                                "native_context": item["native_session_file"], "native_session_id": item["native_session_id"]},
                                    event_sequence=event["sequence"], occurred_at=event["at"], field="developer-conversation",
                                    disposition=disposition, native_status=item["status"], registry_id=item["id"],
                                    source_namespace={"journal": str(registry_path), "root_id": item["root_id"]},
                                    original_ordinal=item["ordinal"], original_parent_id=item["parent_id"]))
                except (ScopeError, sqlite3.Error, ValueError, KeyError, TypeError, AttributeError) as exc:
                    diagnostic("developer-session", registry_path, f"{item['id']}: {exc}")
                    coverage["developer_journal"] = "partial"
    except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
        if not namespace_registered and not registry_path.exists():
            coverage["developer_journal"] = "not-created"
        else:
            diagnostic("developer-registry", registry_path, exc)
            coverage["developer_journal"] = "unavailable"

    try:
        candidates = sorted(path for path in runs_dir.iterdir() if path.is_dir()
                            and ((path / "controller.sqlite3").exists() or (path / "events.sqlite3").exists()))
    except OSError as exc:
        candidates = []
        if not namespace_registered and not runs_dir.exists():
            coverage["runs"] = "not-created"
        else:
            diagnostic("runs", runs_dir, exc)
    for run_dir in candidates:
        try:
            from scripts import noetic_opermem as opermem
            if not (run_dir / "controller.sqlite3").exists():
                claim = _opermem_claim(run_dir)
                execution = opermem_executions.get(str(run_dir))
                if claim is not None or execution is not None:
                    if claim and claim["namespace_path"] != str(namespace_path):
                        if execution is not None:
                            raise ScopeError("Selected canonical Opermem execution has changed namespace metadata")
                        coverage["foreign_excluded"] += 1
                        continue
                    root = execution["effort"] if execution else claim.get("effort_root")
                    if selection["kind"] != "application" and not any(positions[o]["effort"] == root for o in selected):
                        coverage["foreign_excluded"] += 1
                        continue
                    if execution is None:
                        raise ScopeError("Claimed owned Opermem run lacks canonical execution identity")
                    adapter = opermem._scope_adapter(namespace_path)
                    with adapter.store._connection() as db:
                        row = db.execute("SELECT native_ref FROM executions WHERE id=?", (execution["id"],)).fetchone()
                    binding = {**json.loads(row[0]), "execution_id": execution["id"]}
                    participants = _opermem_participants(adapter, binding)
                    eligible = [part for part in participants if part["ordinal"] in selected and
                        (exact is None or part.get("target") == {"ordinal": exact[0], "instantiation": exact[1], "session": exact[2]})]
                    if not eligible and not (exact is None and binding["initiator"] in selected):
                        continue
                    owned = opermem.owned_run(run_dir)
                    if owned is None or owned[1] != binding:
                        raise ScopeError("Selected owned Opermem run differs from canonical execution identity")
                    link = owned[2]
                    correlation = {"effort_root": binding["effort_root"], "namespace": binding["namespace"],
                        "namespace_path": binding["namespace_path"], "initiator": binding["initiator"],
                        "execution_id": binding["execution_id"], "participants": eligible, "native_link": link,
                        "host_sources": binding["host_sources"], "occasion_selection": binding["occasion_selection"],
                        "native_store_identity": {"directory": link["store"],
                            "workspace_id": link["context"]["pinned_canonical_cut"]["workspace_id"],
                            "authority_scope_id": link["context"]["pinned_canonical_cut"]["authority_scope_id"]}}
                    sources.extend(_opermem_sources(run_dir, correlation, namespace, positions, selected, sessions, exact, selection))
                    coverage["native_context"] = "whole-historical-packets-with-store-qualified-ownership"
                    continue
            if (run_dir / "controller.sqlite3").exists():
                try:
                    from scripts.noetic_disciplines import correspondence
                except ImportError as exc:
                    raise ScopeError("Structured ownership adapter unavailable; controller content excluded") from exc
                correlation = correspondence(run_dir, namespace_path=namespace_path)
                if correlation["correlation_status"] == "assigned":
                    if correlation["namespace"] != namespace:
                        raise ScopeError("Structured run belongs to another namespace")
                    root = correlation["effort_root"]
                    if root not in positions or positions[root]["effort"] != root:
                        raise ScopeError("Structured run effort missing from canonical namespace")
                    if selection["kind"] != "application" and not any(positions[o]["effort"] == root for o in selected):
                        coverage["foreign_excluded"] += 1
                        continue
                    participants = {part["activation_id"]: part for part in correlation["participants"]}
                    if selection["kind"] in ("ordinal", "session") and not any(
                            part["ordinal"] in selected and (exact is None or part.get("target") ==
                            {"ordinal": exact[0], "instantiation": exact[1], "session": exact[2]})
                            for part in participants.values()):
                        continue
                else:
                    if selection["kind"] != "application":
                        coverage["unassigned_excluded"] += 1
                        continue
                    participants = {}
                collected = local.controller_sources(run_dir)
                coverage["controller_excluded_artifacts"] += collected["excluded_artifacts"]
                state = local.controller.inspect_run(run_dir / "controller.sqlite3")
                for source in collected["sources"]:
                    artifact = state["artifacts"][source["artifact_id"]]
                    part = participants.get(artifact["activation_id"])
                    if correlation["correlation_status"] == "assigned":
                        if part is None and artifact["activation_id"] is not None:
                            raise ScopeError("Controller artifact participant correspondence incomplete")
                        if selection["kind"] in ("ordinal", "session"):
                            if part is None or part["ordinal"] not in selected:
                                continue
                            if exact and part.get("target") != {"ordinal": exact[0], "instantiation": exact[1], "session": exact[2]}:
                                continue
                        position = positions[part["ordinal"]] if part else positions[root]
                        target = part.get("target") if part else None
                        native = sessions.get((target["ordinal"], target["instantiation"], target["session"])) if target else None
                        owner = _owner(namespace, position, target, current=native["current"] if native else None,
                                       status=native["status"] if native else None)
                    else:
                        owner = _owner(namespace)
                    sources.append({**source, **owner, "field": "controller-artifact", "collection": "current-bindings-only",
                                    "controller_scope": source["scope"], "scope": selection,
                                    "source_ref": {"controller_store": source["source_path"], "artifact_id": source["artifact_id"],
                                                   "event_id": source["event_id"], "activation_id": artifact["activation_id"]},
                                    "correlation": correlation, "partial": artifact["partial"],
                                    "source_namespace": {"kind": "native-controller", "run_id": run_dir.name, "run_dir": str(run_dir)},
                                    "source_text_sha256": local.digest(source["text"])})
            else:
                if selection["kind"] != "application":
                    coverage["unassigned_excluded"] += 1
                    continue
                events = runtime.read_events(run_dir)
                status = runtime.project(events)
                entries = [("goal", run_dir / "events.sqlite3", events[0]["sequence"], status["goal"])]
                for field in ("work", "review"):
                    path = run_dir / (field + ".md")
                    if path.exists():
                        entries.append((field, path, None, path.read_text(encoding="utf-8")))
                if status["review"]:
                    event = next(e for e in reversed(events) if e["kind"] == "review.recorded")
                    entries.append(("review.recorded.evidence", run_dir / "events.sqlite3", event["sequence"], status["review"]["evidence"]))
                for field, path, sequence, text in entries:
                    if text.strip():
                        sources.append(_source(text, source_id=f"{run_dir.name}:legacy:{field}:{sequence}", source_path=path,
                            source=field, source_ref={"path": str(path), "sequence": sequence}, owner=_owner(namespace),
                            field="legacy-run", run_id=status["run_id"], state=status["state"], event_sequence=sequence,
                            source_namespace={"kind": "legacy-run", "run_id": status["run_id"], "run_dir": str(run_dir)}))
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, AttributeError) as exc:
            diagnostic("structured-run" if (run_dir / "controller.sqlite3").exists() else "legacy-run", run_dir, exc)
    if namespace_registered and exact is None:
        from scripts.noetic_opermem_scope import OpermemScope
        adapter = OpermemScope(namespace_path)
        for execution in opermem_executions.values():
            if execution["initiator"] not in selected:
                continue
            try:
                with adapter.store._connection() as db:
                    attached = db.execute("SELECT 1 FROM history WHERE execution_id=? AND kind='opermem-run-attached'", (execution["id"],)).fetchone()
                    if attached:
                        continue
                    row = db.execute("SELECT native_ref FROM executions WHERE id=?", (execution["id"],)).fetchone()
                binding = {**json.loads(row[0]), "execution_id": execution["id"]}
                prepared = adapter.correspondence(binding)
                sources.append(_source(local.canonical(prepared),
                    source_id=f"{namespace['id']}:opermem-preparation:{prepared['execution_id']}",
                    source_path=namespace_path, source="opermem-preparation", source_ref={"execution_id": prepared["execution_id"]},
                    owner=_owner(namespace, positions[execution["initiator"]]), field="preparation-observation", collection="retained-reservation-only"))
            except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
                diagnostic("opermem-preparation", namespace_path, exc)
    identity = {"collector": COLLECTOR, "namespace": namespace, "selection": selection,
                "sessions_home": str(sessions_home), "runs_dir": str(runs_dir)}
    return {"identity": identity, "selection": selection, "sources": sources, "diagnostics": diagnostics,
            "coverage": coverage, "status": "partial" if diagnostics else "complete-with-declared-exclusions" if namespace_registered else "unregistered-legacy-only",
            "authoritative": False, "collected_at": datetime.now(timezone.utc).isoformat(),
            "namespace_registered": namespace_registered,
            "notice": ("Derived source investigation; retained Opermem packets preserve historical standing and confer no current admission or semantic promotion." if namespace_registered else
                       "Application namespace not registered; only source-qualified unassigned legacy material is eligible.")}


def add_scope_arguments(parser):
    parser.add_argument("--namespace-path", type=Path)
    parser.add_argument("--sessions-home", type=Path)
    parser.add_argument("--scope", choices=("application", "effort", "ordinal", "session"))
    parser.add_argument("--effort-root")
    parser.add_argument("--ordinal")
    parser.add_argument("--instantiation", type=int)
    parser.add_argument("--session", type=int)


def selection_from_args(args):
    return _selection({"kind": args.scope, **{key: getattr(args, key) for key in
        ("effort_root", "ordinal", "instantiation", "session") if getattr(args, key) is not None}})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, required=True)
    add_scope_arguments(parser)
    args = parser.parse_args(argv)
    try:
        if args.namespace_path is None or args.sessions_home is None:
            raise ScopeError("Scoped recall requires explicit --namespace-path and --sessions-home")
        result = collect(namespace_path=args.namespace_path, sessions_home=args.sessions_home,
                         runs_dir=args.runs_dir, selection=selection_from_args(args))
        print(local.canonical(result))
        return 0
    except (ScopeError, OSError, sqlite3.Error) as exc:
        print(local.canonical({"status": "unavailable", "error": str(exc), "authoritative": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
