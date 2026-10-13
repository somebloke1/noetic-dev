"""Canonical persistent ordinal, effort and exact-target domain; no runtime broker.

Callers supply an application-owned SQLite location explicitly. Agent addresses
are absolute ordinals; instantiation/session selectors are structured integers.
Native references and cognitive semantics remain owned by their source clients.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import uuid

from scripts.noetic_storage import create_private_sqlite


class ScopeError(ValueError):
    """An address, ownership, lineage or exact-target constraint was violated."""


def _text(value, name):
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise ScopeError(f"{name} must be nonempty text")
    return value


def _ordinal(value):
    if not isinstance(value, str) or not re.fullmatch(r"0(?:\.(?:0|[1-9][0-9]*))*", value):
        raise ScopeError("Use an absolute global ordinal rooted at 0")
    return value


def _integer(value, name, minimum=1):
    if type(value) is not int or value < minimum:
        raise ScopeError(f"{name} must be an integer >= {minimum}")
    return value


def _json(value, name, *, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, dict) or not value:
        raise ScopeError(f"{name} must be a nonempty reference/object")
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ScopeError(f"Invalid {name}: {exc}") from exc


def _now():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Target:
    ordinal: str
    instantiation: int
    session: int

    def __post_init__(self):
        _ordinal(self.ordinal)
        _integer(self.instantiation, "Instantiation")
        _integer(self.session, "Session")

    def as_dict(self):
        return {"ordinal": self.ordinal, "instantiation": self.instantiation, "session": self.session}


@dataclass(frozen=True)
class Scope:
    effort_root: str | None
    target_efforts: tuple[str, ...] = ()
    root_mandate_version: int | None = None

    def __post_init__(self):
        if self.effort_root is not None:
            _ordinal(self.effort_root)
            if self.target_efforts or self.root_mandate_version is not None:
                raise ScopeError("Effort scope cannot also specify an application mandate")
        else:
            if not isinstance(self.target_efforts, tuple) or len(set(self.target_efforts)) != len(self.target_efforts):
                raise ScopeError("Application scope names distinct effort-root ordinals")
            for ordinal in self.target_efforts:
                _ordinal(ordinal)
            _integer(self.root_mandate_version, "Root mandate version")

    @classmethod
    def effort(cls, ordinal):
        return cls(ordinal)

    @classmethod
    def application(cls, efforts, *, root_mandate_version):
        return cls(None, tuple(efforts), root_mandate_version)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS positions (
    allocation INTEGER PRIMARY KEY AUTOINCREMENT, ordinal TEXT NOT NULL UNIQUE,
    parent TEXT REFERENCES positions(ordinal),
    effort TEXT REFERENCES efforts(ordinal) DEFERRABLE INITIALLY DEFERRED,
    discipline_id INTEGER REFERENCES disciplines(id), origin TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open', next_child INTEGER NOT NULL DEFAULT 0,
    current_instantiation INTEGER, mandate_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS efforts (
    ordinal TEXT PRIMARY KEY REFERENCES positions(ordinal), intent TEXT NOT NULL,
    environment_version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS environments (
    effort TEXT NOT NULL REFERENCES efforts(ordinal), version INTEGER NOT NULL,
    environment TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY(effort, version)
);
CREATE TABLE IF NOT EXISTS mandates (
    ordinal TEXT NOT NULL REFERENCES positions(ordinal), version INTEGER NOT NULL,
    delegating_ordinal TEXT REFERENCES positions(ordinal), parent_mandate_version INTEGER,
    mandate TEXT NOT NULL, origin TEXT NOT NULL, human_ref TEXT, delegator TEXT,
    source_ref TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY(ordinal, version),
    FOREIGN KEY(delegating_ordinal, parent_mandate_version) REFERENCES mandates(ordinal, version)
);
CREATE TABLE IF NOT EXISTS instantiations (
    ordinal TEXT NOT NULL REFERENCES positions(ordinal), sequence INTEGER NOT NULL,
    predecessor INTEGER, mandate_version INTEGER NOT NULL, handoff TEXT,
    native_ref TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
    current_session INTEGER, created_at TEXT NOT NULL,
    PRIMARY KEY(ordinal, sequence),
    FOREIGN KEY(ordinal, predecessor) REFERENCES instantiations(ordinal, sequence),
    FOREIGN KEY(ordinal, mandate_version) REFERENCES mandates(ordinal, version)
);
CREATE TABLE IF NOT EXISTS sessions (
    ordinal TEXT NOT NULL, instantiation INTEGER NOT NULL, sequence INTEGER NOT NULL,
    native_ref TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL,
    PRIMARY KEY(ordinal, instantiation, sequence),
    FOREIGN KEY(ordinal, instantiation) REFERENCES instantiations(ordinal, sequence)
);
CREATE TABLE IF NOT EXISTS disciplines (
    id INTEGER PRIMARY KEY AUTOINCREMENT, effort TEXT NOT NULL REFERENCES efforts(ordinal),
    initiator TEXT NOT NULL REFERENCES positions(ordinal), initiating_target TEXT,
    parent_instance INTEGER REFERENCES disciplines(id), definition_ref TEXT NOT NULL,
    intent TEXT NOT NULL, environment TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, discipline_id INTEGER NOT NULL REFERENCES disciplines(id),
    native_ref TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ordinal TEXT NOT NULL,
    instantiation INTEGER NOT NULL, session INTEGER NOT NULL, kind TEXT NOT NULL,
    payload TEXT NOT NULL, native_ref TEXT NOT NULL, environment TEXT NOT NULL,
    mandate_version INTEGER NOT NULL, created_at TEXT NOT NULL,
    FOREIGN KEY(ordinal, instantiation, session) REFERENCES sessions(ordinal, instantiation, sequence)
);
CREATE TABLE IF NOT EXISTS history (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT, ordinal TEXT NOT NULL REFERENCES positions(ordinal),
    effort TEXT REFERENCES efforts(ordinal), instantiation INTEGER, session INTEGER,
    discipline_id INTEGER REFERENCES disciplines(id), execution_id INTEGER REFERENCES executions(id),
    kind TEXT NOT NULL, data TEXT NOT NULL, source_ref TEXT NOT NULL, at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS history_ordinal ON history(ordinal, sequence);
CREATE INDEX IF NOT EXISTS history_discipline ON history(discipline_id, sequence);
CREATE TABLE IF NOT EXISTS legacy_namespaces (
    namespace TEXT PRIMARY KEY, native_ref TEXT NOT NULL, source_ref TEXT NOT NULL, registered_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS legacy_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT, namespace TEXT NOT NULL REFERENCES legacy_namespaces(namespace),
    legacy_ordinal TEXT NOT NULL, original_parent TEXT, ordinal TEXT NOT NULL REFERENCES positions(ordinal),
    target TEXT, native_ref TEXT NOT NULL, source_ref TEXT NOT NULL, adopted_at TEXT NOT NULL,
    UNIQUE(namespace, legacy_ordinal, native_ref)
);
"""

_JSON_FIELDS = {"mandate", "human_ref", "delegator", "source_ref", "native_ref", "handoff",
                "environment", "definition_ref", "initiating_target", "payload", "data", "target"}


def _row(row):
    if row is None:
        raise ScopeError("Record does not exist")
    result = dict(row)
    for field in _JSON_FIELDS & result.keys():
        if result[field] is not None:
            result[field] = json.loads(result[field])
    return result


class ScopeStore:
    """One application namespace, with transactionally allocated ordinal positions.

    First creation requires a human-origin root mandate/reference/source. Reopen
    requires only the same explicit storage path and never starts any runtime.
    """

    def __init__(self, path, *, root_mandate=None, human_ref=None, source_ref=None):
        self.path = Path(path).expanduser().absolute()
        create_private_sqlite(self.path)
        with self._connection() as db:
            db.executescript(_SCHEMA)
        with self._write() as db:
            row = db.execute("SELECT value FROM metadata WHERE key='namespace'").fetchone()
            if row is None:
                mandate = _json(root_mandate, "Root mandate")
                human = _json(human_ref, "Human origin")
                source = _json(source_ref, "Source reference")
                db.execute("INSERT INTO metadata VALUES('namespace',?)", (str(uuid.uuid4()),))
                db.execute("INSERT INTO metadata VALUES('schema','1')")
                db.execute("INSERT INTO positions(ordinal,origin,created_at) VALUES('0','human',?)", (_now(),))
                self._mandate(db, "0", 1, mandate, "human", human, None, source)
                self._event(db, "0", "application-created", {"origin": "human", "human_ref": human_ref,
                            "mandate_version": 1}, source_ref)
            elif db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()[0] != "1":
                raise ScopeError("Unsupported ordinal domain schema")
            self.namespace = db.execute("SELECT value FROM metadata WHERE key='namespace'").fetchone()[0]

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def _write(self):
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    @contextmanager
    def _read(self):
        with self._connection() as db:
            db.execute("BEGIN")
            yield db

    def _position(self, db, ordinal):
        return _row(db.execute("SELECT * FROM positions WHERE ordinal=?", (_ordinal(ordinal),)).fetchone())

    def _effort(self, db, ordinal):
        effort = _row(db.execute("SELECT * FROM efforts WHERE ordinal=?", (_ordinal(ordinal),)).fetchone())
        environment = _row(db.execute("SELECT * FROM environments WHERE effort=? AND version=?",
                                      (ordinal, effort["environment_version"])).fetchone())
        return {**effort, "environment": environment["environment"]}

    def _scope(self, db, position, scope):
        if not isinstance(scope, Scope):
            raise ScopeError("An explicit operation Scope is required")
        if scope.effort_root is not None:
            self._effort(db, scope.effort_root)
            if position["effort"] != scope.effort_root:
                raise ScopeError("Operation effort does not own the target ordinal")
        else:
            root = self._position(db, "0")
            if scope.root_mandate_version != root["mandate_version"]:
                raise ScopeError("Application scope names a stale root mandate")
            for effort in scope.target_efforts:
                self._effort(db, effort)
            if position["ordinal"] != "0" and position["effort"] not in scope.target_efforts:
                raise ScopeError("Application operation did not name the target effort")

    def _target(self, db, target, *, current=False):
        if not isinstance(target, Target):
            raise ScopeError("An exact Target is required")
        position = self._position(db, target.ordinal)
        instance = _row(db.execute("SELECT * FROM instantiations WHERE ordinal=? AND sequence=?",
                                   (target.ordinal, target.instantiation)).fetchone())
        session = _row(db.execute("SELECT * FROM sessions WHERE ordinal=? AND instantiation=? AND sequence=?",
                                  (target.ordinal, target.instantiation, target.session)).fetchone())
        if current and (position["status"] != "open" or position["current_instantiation"] != target.instantiation
                        or instance["status"] != "active" or instance["current_session"] != target.session
                        or session["status"] != "open"):
            raise ScopeError("Target is not the current open agent/session")
        return position, instance, session

    def _origin(self, db, parent, origin, human_ref, delegator):
        if origin == "human":
            if delegator is not None:
                raise ScopeError("Human assignment cannot claim an executed agent delegation")
            return _json(human_ref, "Human origin"), None
        if origin == "agent":
            if human_ref is not None or not isinstance(delegator, Target) or delegator.ordinal != parent:
                raise ScopeError("Agent delegation must name its actual exact parent target")
            self._target(db, delegator, current=True)
            return None, _json(delegator.as_dict(), "Delegator")
        raise ScopeError("Origin must be human or agent; legacy adoption is a separate relation")

    def _mandate(self, db, ordinal, version, mandate, origin, human, delegator, source):
        parent = self._position(db, ordinal)["parent"]
        parent_version = self._position(db, parent)["mandate_version"] if parent is not None else None
        if delegator is not None and parent is not None:
            actual = json.loads(delegator)
            parent_version = db.execute("SELECT mandate_version FROM instantiations WHERE ordinal=? AND sequence=?",
                                        (actual["ordinal"], actual["instantiation"])).fetchone()[0]
        db.execute("INSERT INTO mandates VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (ordinal, version, parent, parent_version, mandate, origin, human, delegator, source, _now()))

    def _event(self, db, ordinal, kind, data, source_ref, *, target=None, instantiation=None, discipline_id=None, execution_id=None):
        position = self._position(db, ordinal)
        if target is not None:
            self._target(db, target)
            if target.ordinal != ordinal:
                raise ScopeError("Event target and responsible ordinal differ")
            instantiation = target.instantiation
        elif instantiation is not None:
            _row(db.execute("SELECT * FROM instantiations WHERE ordinal=? AND sequence=?",
                            (ordinal, _integer(instantiation, "Instantiation"))).fetchone())
        if discipline_id is None:
            discipline_id = position["discipline_id"]
        if discipline_id is not None:
            discipline = self._discipline(db, discipline_id)
            if discipline["effort"] != position["effort"]:
                raise ScopeError("Event discipline and responsible effort differ")
        if execution_id is not None:
            execution = self._execution(db, execution_id)
            if execution["discipline_id"] != discipline_id:
                raise ScopeError("Event execution and discipline differ")
        cursor = db.execute("""INSERT INTO history
            (ordinal,effort,instantiation,session,discipline_id,execution_id,kind,data,source_ref,at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (ordinal, position["effort"], instantiation, target.session if target else None,
             discipline_id, execution_id, _text(kind, "Event kind"), _json(data, "Event data"),
             _json(source_ref, "Source reference"), _now()))
        return _row(db.execute("SELECT * FROM history WHERE sequence=?", (cursor.lastrowid,)).fetchone())

    def _allocate(self, db, parent, *, effort, mandate, origin, human, delegator, source_ref, discipline_id=None):
        position = self._position(db, parent)
        if position["status"] != "open":
            raise ScopeError("Cannot delegate from a closed position")
        ordinal = f"{parent}.{position['next_child']}"
        db.execute("UPDATE positions SET next_child=next_child+1 WHERE ordinal=?", (parent,))
        db.execute("""INSERT INTO positions(ordinal,parent,effort,discipline_id,origin,created_at)
                      VALUES(?,?,?,?,?,?)""", (ordinal, parent, effort or ordinal, discipline_id, origin, _now()))
        self._mandate(db, ordinal, 1, _json(mandate, "Mandate"), origin, human, delegator,
                      _json(source_ref, "Source reference"))
        return ordinal

    def _describe(self, db, ordinal):
        position = self._position(db, ordinal)
        position["mandate"] = _row(db.execute("SELECT * FROM mandates WHERE ordinal=? AND version=?",
                                              (ordinal, position["mandate_version"])).fetchone())
        if position["effort"] is not None:
            effort = self._effort(db, position["effort"])
            position.update({"environment": effort["environment"], "intent": effort["intent"],
                             "environment_version": effort["environment_version"]})
        return position

    def position(self, ordinal, *, scope=None):
        with self._read() as db:
            position = self._position(db, ordinal)
            if scope is not None:
                self._scope(db, position, scope)
            return self._describe(db, ordinal)

    def create_effort(self, *, intent, environment, mandate, origin, source_ref, human_ref=None, delegator=None):
        intent = _text(intent, "Effort intent")
        environment = _json(environment, "Environment")
        with self._write() as db:
            human, agent = self._origin(db, "0", origin, human_ref, delegator)
            ordinal = self._allocate(db, "0", effort=None, mandate=mandate, origin=origin, human=human,
                                      delegator=agent, source_ref=source_ref)
            db.execute("INSERT INTO efforts(ordinal,intent) VALUES(?,?)", (ordinal, intent))
            db.execute("INSERT INTO environments VALUES(?,1,?,?)", (ordinal, environment, _now()))
            self._event(db, ordinal, "effort-created", {"intent": intent, "parent": "0", "origin": origin,
                        "environment": json.loads(environment), "mandate_version": 1,
                        "delegator": delegator.as_dict() if delegator else None, "human_ref": human_ref}, source_ref)
            return self._describe(db, ordinal)

    def delegate(self, parent, *, scope, mandate, origin, source_ref, human_ref=None, delegator=None, discipline_id=None):
        with self._write() as db:
            position = self._position(db, parent)
            self._scope(db, position, scope)
            if position["effort"] is None:
                raise ScopeError("Use create_effort for a new root branch")
            human, agent = self._origin(db, parent, origin, human_ref, delegator)
            if discipline_id is not None:
                discipline = self._discipline(db, discipline_id)
                if discipline["effort"] != position["effort"] or not self._descendant(parent, discipline["initiator"]):
                    raise ScopeError("Discipline participant must be delegated within its initiator's effort branch")
            ordinal = self._allocate(db, parent, effort=position["effort"], mandate=mandate, origin=origin,
                                      human=human, delegator=agent, source_ref=source_ref, discipline_id=discipline_id)
            self._event(db, ordinal, "delegated", {"parent": parent, "origin": origin, "mandate_version": 1,
                        "delegator": delegator.as_dict() if delegator else None, "human_ref": human_ref}, source_ref)
            return self._describe(db, ordinal)

    def revise_mandate(self, ordinal, *, scope, mandate, origin, source_ref, human_ref=None, delegator=None):
        with self._write() as db:
            position = self._position(db, ordinal)
            self._scope(db, position, scope)
            human, agent = self._origin(db, position["parent"] or "0", origin, human_ref, delegator)
            version = position["mandate_version"] + 1
            self._mandate(db, ordinal, version, _json(mandate, "Mandate"), origin, human, agent, _json(source_ref, "Source"))
            db.execute("UPDATE positions SET mandate_version=? WHERE ordinal=?", (version, ordinal))
            self._event(db, ordinal, "mandate-revised", {"version": version, "origin": origin,
                        "delegator": delegator.as_dict() if delegator else None, "human_ref": human_ref}, source_ref)
            return self._describe(db, ordinal)

    def mandates(self, ordinal, *, scope=None):
        with self._read() as db:
            position = self._position(db, ordinal)
            if scope is not None:
                self._scope(db, position, scope)
            return [_row(row) for row in db.execute("SELECT * FROM mandates WHERE ordinal=? ORDER BY version", (ordinal,))]

    def set_environment(self, effort, *, scope, environment, source_ref):
        with self._write() as db:
            self._scope(db, self._position(db, effort), scope)
            current = self._effort(db, effort)
            version = current["environment_version"] + 1
            db.execute("INSERT INTO environments VALUES(?,?,?,?)", (effort, version, _json(environment, "Environment"), _now()))
            db.execute("UPDATE efforts SET environment_version=? WHERE ordinal=?", (version, effort))
            self._event(db, effort, "environment-revised", {"version": version, "environment": environment}, source_ref)
            return self._effort(db, effort)

    def environments(self, effort, *, scope=None):
        with self._read() as db:
            position = self._position(db, effort)
            if scope is not None:
                self._scope(db, position, scope)
            self._effort(db, effort)
            return [_row(row) for row in db.execute("SELECT * FROM environments WHERE effort=? ORDER BY version", (effort,))]

    def close_position(self, ordinal, *, scope, source_ref):
        with self._write() as db:
            position = self._position(db, ordinal)
            self._scope(db, position, scope)
            if ordinal == "0":
                raise ScopeError("Application namespace root cannot be closed")
            db.execute("UPDATE positions SET status='closed' WHERE ordinal=?", (ordinal,))
            return self._event(db, ordinal, "position-closed", {"previous_status": position["status"]}, source_ref)

    def instantiate(self, ordinal, *, scope, native_ref, source_ref, predecessor=None, handoff=None):
        with self._write() as db:
            position = self._position(db, ordinal)
            self._scope(db, position, scope)
            if position["status"] != "open":
                raise ScopeError("Cannot instantiate a closed position")
            current = position["current_instantiation"]
            if current is None:
                if predecessor is not None or handoff is not None:
                    raise ScopeError("First instantiation has no predecessor or succession handoff")
            elif type(predecessor) is not int or predecessor != current:
                raise ScopeError("Succession must explicitly name the current predecessor")
            if current is not None:
                _json(handoff, "Succession handoff")
                db.execute("UPDATE instantiations SET status='superseded',current_session=NULL WHERE ordinal=? AND sequence=?", (ordinal, current))
                db.execute("UPDATE sessions SET status='superseded' WHERE ordinal=? AND instantiation=? AND status='open'", (ordinal, current))
            sequence = db.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM instantiations WHERE ordinal=?", (ordinal,)).fetchone()[0]
            db.execute("""INSERT INTO instantiations
                (ordinal,sequence,predecessor,mandate_version,handoff,native_ref,created_at) VALUES(?,?,?,?,?,?,?)""",
                (ordinal, sequence, predecessor, position["mandate_version"], _json(handoff, "Handoff", optional=True),
                 _json(native_ref, "Native agent reference"), _now()))
            db.execute("UPDATE positions SET current_instantiation=? WHERE ordinal=?", (sequence, ordinal))
            self._event(db, ordinal, "instantiated" if current is None else "succeeded",
                        {"instantiation": sequence, "predecessor": predecessor, "handoff": handoff,
                         "mandate_version": position["mandate_version"], "native_ref": native_ref}, source_ref,
                         instantiation=sequence)
            return _row(db.execute("SELECT * FROM instantiations WHERE ordinal=? AND sequence=?", (ordinal, sequence)).fetchone())

    def open_session(self, ordinal, instantiation, *, scope, native_ref, source_ref):
        _integer(instantiation, "Instantiation")
        with self._write() as db:
            position = self._position(db, ordinal)
            self._scope(db, position, scope)
            instance = _row(db.execute("SELECT * FROM instantiations WHERE ordinal=? AND sequence=?", (ordinal, instantiation)).fetchone())
            if position["status"] != "open" or position["current_instantiation"] != instantiation or instance["status"] != "active":
                raise ScopeError("New sessions belong to the current active instantiation")
            sequence = db.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM sessions WHERE ordinal=? AND instantiation=?", (ordinal, instantiation)).fetchone()[0]
            db.execute("UPDATE sessions SET status='superseded' WHERE ordinal=? AND instantiation=? AND status='open'", (ordinal, instantiation))
            db.execute("INSERT INTO sessions(ordinal,instantiation,sequence,native_ref,created_at) VALUES(?,?,?,?,?)",
                       (ordinal, instantiation, sequence, _json(native_ref, "Native session/context reference"), _now()))
            db.execute("UPDATE instantiations SET current_session=? WHERE ordinal=? AND sequence=?", (sequence, ordinal, instantiation))
            target = Target(ordinal, instantiation, sequence)
            self._event(db, ordinal, "session-opened", {"native_ref": native_ref,
                        "predecessor_session": instance["current_session"]}, source_ref, target=target)
            return target

    def set_session_status(self, target, status, *, scope, source_ref):
        if status not in {"open", "closed", "failed", "superseded"}:
            raise ScopeError("Invalid session status")
        with self._write() as db:
            position, instance, session = self._target(db, target)
            self._scope(db, position, scope)
            if status == "open":
                if position["status"] != "open" or position["current_instantiation"] != target.instantiation or instance["status"] != "active":
                    raise ScopeError("Reopen requires the explicitly named current instantiation")
                db.execute("UPDATE sessions SET status='superseded' WHERE ordinal=? AND instantiation=? AND status='open'",
                           (target.ordinal, target.instantiation))
                db.execute("UPDATE instantiations SET current_session=? WHERE ordinal=? AND sequence=?", (target.session, target.ordinal, target.instantiation))
            elif instance["current_session"] == target.session:
                db.execute("UPDATE instantiations SET current_session=NULL WHERE ordinal=? AND sequence=?", (target.ordinal, target.instantiation))
            db.execute("UPDATE sessions SET status=? WHERE ordinal=? AND instantiation=? AND sequence=?",
                       (status, target.ordinal, target.instantiation, target.session))
            return self._event(db, target.ordinal, "session-status", {"status": status, "previous_status": session["status"]}, source_ref, target=target)

    def instantiations(self, ordinal, *, scope=None):
        with self._read() as db:
            position = self._position(db, ordinal)
            if scope is not None:
                self._scope(db, position, scope)
            return [_row(row) for row in db.execute("SELECT * FROM instantiations WHERE ordinal=? ORDER BY sequence", (ordinal,))]

    def sessions(self, ordinal, instantiation, *, scope=None):
        _integer(instantiation, "Instantiation")
        with self._read() as db:
            position = self._position(db, ordinal)
            if scope is not None:
                self._scope(db, position, scope)
            _row(db.execute("SELECT * FROM instantiations WHERE ordinal=? AND sequence=?", (ordinal, instantiation)).fetchone())
            return [_row(row) for row in db.execute("SELECT * FROM sessions WHERE ordinal=? AND instantiation=? ORDER BY sequence", (ordinal, instantiation))]

    def _resolve(self, db, ordinal, scope, instantiation, session):
        position = self._position(db, ordinal)
        self._scope(db, position, scope)
        if session is not None and instantiation is None:
            raise ScopeError("Historical session selection requires an instantiation selector")
        explicit = instantiation is not None and session is not None
        instantiation = position["current_instantiation"] if instantiation is None else _integer(instantiation, "Instantiation")
        if instantiation is None:
            raise ScopeError("Position has no instantiation")
        instance = _row(db.execute("SELECT * FROM instantiations WHERE ordinal=? AND sequence=?", (ordinal, instantiation)).fetchone())
        session = instance["current_session"] if session is None else _integer(session, "Session")
        if session is None:
            raise ScopeError("Instantiation has no designated current session; use exact historical selectors")
        target = Target(ordinal, instantiation, session)
        self._target(db, target, current=not explicit)
        return target

    def resolve(self, ordinal, *, scope, instantiation=None, session=None):
        with self._read() as db:
            return self._resolve(db, ordinal, scope, instantiation, session)

    def resolve_context(self, ordinal, *, scope, instantiation=None, session=None, current=False, include_effort=False):
        with self._read() as db:
            target = self._resolve(db, ordinal, scope, instantiation, session)
            if current and self._resolve(db, ordinal, scope, None, None) != target:
                raise ScopeError("Exact target is superseded; select the intended current session explicitly.")
            _, instance, retained = self._target(db, target)
            result = {"target": target.as_dict(), "position": self._describe(db, ordinal),
                      "instantiation": instance, "session": retained}
            if include_effort:
                owner = result["position"]["effort"]
                result["owning_effort"] = self._describe(db, owner) if owner else None
                result["namespace"] = db.execute("SELECT value FROM metadata WHERE key='namespace'").fetchone()[0]
            return result

    def native_message_population(self, sender, *, scope, population, include_self=False):
        if population not in ("direct_children", "descendants", "effort"):
            raise ScopeError("Select direct_children, descendants, or effort broadcast population")
        with self._read() as db:
            source, _, _ = self._target(db, sender, current=True)
            self._scope(db, source, scope)
            rows = db.execute("SELECT ordinal,parent,allocation FROM positions WHERE effort=? ORDER BY allocation", (source["effort"],)).fetchall()
            parents = {row["ordinal"]: row["parent"] for row in rows}
            selected = set()
            for row in rows:
                ordinal = row["ordinal"]
                if population == "effort" or population == "direct_children" and row["parent"] == sender.ordinal:
                    selected.add(ordinal)
                elif population == "descendants":
                    ancestor, seen = row["parent"], set()
                    while ancestor in parents and ancestor not in seen:
                        if ancestor == sender.ordinal:
                            selected.add(ordinal)
                            break
                        seen.add(ancestor)
                        ancestor = parents[ancestor]
            if include_self:
                selected.add(sender.ordinal)
            else:
                selected.discard(sender.ordinal)
            recipients = []
            for row in rows:
                if row["ordinal"] not in selected:
                    continue
                try:
                    target = self._resolve(db, row["ordinal"], scope, None, None)
                    _, _, retained = self._target(db, target, current=True)
                except ScopeError:
                    continue
                if retained["native_ref"].get("registry_id"):
                    recipients.append(target.as_dict())
            return {"namespace": db.execute("SELECT value FROM metadata WHERE key='namespace'").fetchone()[0],
                    "recipients": recipients}

    def bind_action(self, ordinal, *, scope, kind, payload, source_ref, instantiation=None, session=None):
        with self._write() as db:
            target = self._resolve(db, ordinal, scope, instantiation, session)
            position, instance, selected = self._target(db, target)
            environment = self._effort(db, position["effort"])["environment"] if position["effort"] else {"scope": "application"}
            cursor = db.execute("""INSERT INTO actions
                (ordinal,instantiation,session,kind,payload,native_ref,environment,mandate_version,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)""", (ordinal, target.instantiation, target.session, _text(kind, "Action kind"),
                _json(payload, "Action payload"), _json(selected["native_ref"], "Native session"),
                _json(environment, "Environment"), instance["mandate_version"], _now()))
            self._event(db, ordinal, "action-bound", {"action_id": cursor.lastrowid, "kind": kind,
                        "environment": environment, "mandate_version": instance["mandate_version"]}, source_ref, target=target)
            return self._action(db, cursor.lastrowid)

    def _action(self, db, action_id):
        action = _row(db.execute("SELECT * FROM actions WHERE id=?", (_integer(action_id, "Action ID"),)).fetchone())
        action["target"] = Target(action["ordinal"], action["instantiation"], action["session"]).as_dict()
        return action

    def action(self, action_id, *, scope):
        with self._read() as db:
            action = self._action(db, action_id)
            self._scope(db, self._position(db, action["ordinal"]), scope)
            return action

    def coordinate(self, *, scope, instructions, origin, source_ref, human_ref=None, delegator=None):
        if not isinstance(scope, Scope) or scope.effort_root is not None or not isinstance(instructions, list) or not instructions:
            raise ScopeError("Coordination requires an application scope and named instructions")
        with self._write() as db:
            self._scope(db, self._position(db, "0"), scope)
            self._origin(db, "0", origin, human_ref, delegator)
            resolved = []
            for instruction in instructions:
                if not isinstance(instruction, dict):
                    raise ScopeError("Each instruction names an ordinal and instruction text")
                ordinal = instruction.get("ordinal")
                position = self._position(db, ordinal)
                self._scope(db, position, scope)
                if position["effort"] is None:
                    raise ScopeError("Coordination instructions target declared effort environments")
                resolved.append({"ordinal": ordinal, "effort": position["effort"],
                                 "instruction": _text(instruction.get("instruction"), "Instruction"),
                                 "environment": self._effort(db, position["effort"])["environment"]})
            event = self._event(db, "0", "coordination", {"root_mandate_version": scope.root_mandate_version,
                                "origin": origin, "human_ref": human_ref,
                                "delegator": delegator.as_dict() if delegator else None, "instructions": resolved}, source_ref)
            for instruction in resolved:
                self._event(db, instruction["ordinal"], "coordination-instruction",
                            {**instruction, "coordination_event": event["sequence"], "root_mandate_version": scope.root_mandate_version}, source_ref)
            return event

    def _discipline(self, db, discipline_id):
        return _row(db.execute("SELECT * FROM disciplines WHERE id=?", (_integer(discipline_id, "Discipline ID"),)).fetchone())

    def _execution(self, db, execution_id):
        return _row(db.execute("SELECT * FROM executions WHERE id=?", (_integer(execution_id, "Execution ID"),)).fetchone())

    def create_discipline(self, effort, *, scope, initiator, definition_ref, intent, source_ref, initiating_target=None, parent_instance=None):
        if not isinstance(definition_ref, dict) or not definition_ref.get("id") or not definition_ref.get("version"):
            raise ScopeError("Discipline definition identity and version must both be explicit")
        with self._write() as db:
            self._effort(db, effort)
            position = self._position(db, initiator)
            self._scope(db, position, scope)
            if position["effort"] != effort or position["status"] != "open":
                raise ScopeError("Discipline initiator must belong to its existing open effort branch")
            if initiating_target is not None:
                self._target(db, initiating_target, current=True)
                if initiating_target.ordinal != initiator:
                    raise ScopeError("Initiating target must name the initiating ordinal")
            if parent_instance is not None:
                parent = self._discipline(db, parent_instance)
                if parent["effort"] != effort or position["discipline_id"] != parent_instance:
                    raise ScopeError("Nested discipline must be initiated by a participant in its parent instance")
            environment = self._effort(db, effort)["environment"]
            cursor = db.execute("""INSERT INTO disciplines
                (effort,initiator,initiating_target,parent_instance,definition_ref,intent,environment,created_at)
                VALUES(?,?,?,?,?,?,?,?)""", (effort, initiator,
                _json(initiating_target.as_dict(), "Initiating target") if initiating_target else None,
                parent_instance, _json(definition_ref, "Definition reference"), _text(intent, "Discipline intent"),
                _json(environment, "Environment"), _now()))
            self._event(db, initiator, "discipline-created", {"definition_ref": definition_ref, "intent": intent,
                        "parent_instance": parent_instance}, source_ref, target=initiating_target, discipline_id=cursor.lastrowid)
            return self._discipline(db, cursor.lastrowid)

    def discipline(self, discipline_id, *, scope=None):
        with self._read() as db:
            discipline = self._discipline(db, discipline_id)
            if scope is not None:
                self._scope(db, self._position(db, discipline["effort"]), scope)
            return discipline

    def create_execution(self, discipline_id, *, scope, native_ref, source_ref):
        with self._write() as db:
            discipline = self._discipline(db, discipline_id)
            self._scope(db, self._position(db, discipline["effort"]), scope)
            cursor = db.execute("INSERT INTO executions(discipline_id,native_ref,created_at) VALUES(?,?,?)",
                                (discipline_id, _json(native_ref, "Native execution reference"), _now()))
            self._event(db, discipline["initiator"], "execution-created", {"native_ref": native_ref}, source_ref,
                        discipline_id=discipline_id, execution_id=cursor.lastrowid)
            return self._execution(db, cursor.lastrowid)

    def record_activation(self, execution_id, *, scope, participant, native_ref, source_ref, result_ref=None):
        with self._write() as db:
            execution = self._execution(db, execution_id)
            discipline = self._discipline(db, execution["discipline_id"])
            position, _, session = self._target(db, participant)
            self._scope(db, position, scope)
            if position["effort"] != discipline["effort"] or position["discipline_id"] != discipline["id"]:
                raise ScopeError("Activation participant must belong to its execution's discipline and effort")
            _json(native_ref, "Native activation reference")
            _json(result_ref, "Native result reference", optional=True)
            event = self._event(db, participant.ordinal, "activation", {"target": participant.as_dict(),
                                "native_ref": native_ref, "native_session_ref": session["native_ref"],
                                "result_ref": result_ref}, source_ref, target=participant,
                                discipline_id=discipline["id"], execution_id=execution_id)
            return {**event, "target": participant.as_dict()}

    def record_event(self, ordinal, *, scope, kind, data, source_ref, target=None, discipline_id=None, execution_id=None):
        with self._write() as db:
            self._scope(db, self._position(db, ordinal), scope)
            return self._event(db, ordinal, kind, data, source_ref, target=target,
                               discipline_id=discipline_id, execution_id=execution_id)

    @staticmethod
    def _descendant(ordinal, ancestor):
        return ordinal == ancestor or ordinal.startswith(ancestor + ".")

    def _page(self, table, ordinal, *, scope, after, limit, selectors=None, exact=False, describe_roots=False):
        _integer(after, "Cursor", 0)
        _integer(limit, "Page size")
        key = "sequence" if table == "history" else "allocation"
        with self._read() as db:
            position = self._position(db, ordinal)
            if scope is not None:
                self._scope(db, position, scope)
            clauses = [f"{key}>?", "ordinal=?" if exact else "(ordinal=? OR substr(ordinal,1,?)=?)"]
            parameters = [after, ordinal] if exact else [after, ordinal, len(ordinal) + 1, ordinal + "."]
            if scope is not None and scope.effort_root is None and ordinal == "0":
                clauses.append("(effort IS NULL OR effort IN (" + ",".join("?" for _ in scope.target_efforts) + "))")
                parameters.extend(scope.target_efforts)
            for field, value in (selectors or {}).items():
                if value is not None:
                    _integer(value, field)
                    if field == "discipline_id":
                        discipline = self._discipline(db, value)
                        if scope is not None:
                            self._scope(db, self._position(db, discipline["effort"]), scope)
                        if not self._descendant(discipline["initiator"], ordinal) and not self._descendant(ordinal, discipline["effort"]):
                            raise ScopeError("History branch and discipline effort differ")
                    elif field == "instantiation":
                        _row(db.execute("SELECT * FROM instantiations WHERE ordinal=? AND sequence=?", (ordinal, value)).fetchone())
                    elif field == "session":
                        self._target(db, Target(ordinal, selectors["instantiation"], value))
                    clauses.append(f"{field}=?")
                    parameters.append(value)
            rows = db.execute(f"SELECT * FROM {table} WHERE " + " AND ".join(clauses) + f" ORDER BY {key} LIMIT ?",
                              [*parameters, limit]).fetchall()
            records = [_row(row) for row in rows]
            if describe_roots:
                records = [self._describe(db, row["ordinal"]) if row["effort"] == row["ordinal"] else row for row in records]
            result = {"records": records, "next_after": records[-1][key] if records else after}
            if table == "history":
                result["namespace_id"] = db.execute("SELECT value FROM metadata WHERE key='namespace'").fetchone()[0]
            return result

    def branch(self, ordinal="0", *, scope=None, after=0, limit=100, describe_roots=False):
        return self._page("positions", ordinal, scope=scope, after=after, limit=limit, describe_roots=describe_roots)

    def history(self, ordinal="0", *, scope=None, after=0, limit=100, instantiation=None, session=None, discipline_id=None):
        if session is not None and instantiation is None:
            raise ScopeError("Session history requires an instantiation selector")
        return self._page("history", ordinal, scope=scope, after=after, limit=limit,
                          selectors={"instantiation": instantiation, "session": session, "discipline_id": discipline_id},
                          exact=instantiation is not None)

    def register_legacy_namespace(self, namespace, *, native_ref, source_ref):
        namespace = _text(namespace, "Legacy source namespace")
        with self._write() as db:
            db.execute("INSERT INTO legacy_namespaces VALUES(?,?,?,?)",
                       (namespace, _json(native_ref, "Native namespace reference"), _json(source_ref, "Source"), _now()))
            return _row(db.execute("SELECT * FROM legacy_namespaces WHERE namespace=?", (namespace,)).fetchone())

    def legacy_namespace(self, namespace):
        with self._read() as db:
            return _row(db.execute("SELECT * FROM legacy_namespaces WHERE namespace=?",
                                   (_text(namespace, "Legacy namespace"),)).fetchone())

    def adopt_legacy(self, namespace, legacy_ordinal, ordinal, *, scope, native_ref, source_ref, original_parent=None, target=None):
        _text(legacy_ordinal, "Original source ordinal")
        if original_parent is not None:
            _text(original_parent, "Recorded original parent")
        with self._write() as db:
            _row(db.execute("SELECT * FROM legacy_namespaces WHERE namespace=?", (_text(namespace, "Legacy namespace"),)).fetchone())
            self._scope(db, self._position(db, ordinal), scope)
            if target is not None:
                self._target(db, target)
                if target.ordinal != ordinal:
                    raise ScopeError("Adoption target must name the mapped ordinal")
            cursor = db.execute("""INSERT INTO legacy_mappings
                (namespace,legacy_ordinal,original_parent,ordinal,target,native_ref,source_ref,adopted_at) VALUES(?,?,?,?,?,?,?,?)""",
                (namespace, legacy_ordinal, original_parent, ordinal,
                 _json(target.as_dict(), "Target") if target else None,
                 _json(native_ref, "Original native reference"), _json(source_ref, "Original source reference"), _now()))
            mapping = _row(db.execute("SELECT * FROM legacy_mappings WHERE id=?", (cursor.lastrowid,)).fetchone())
            self._event(db, ordinal, "legacy-adopted", {**mapping, "historical_delegation": False}, source_ref, target=target)
            return mapping

    def legacy_mappings(self, ordinal="0", *, scope=None, after=0, limit=100):
        _integer(after, "Mapping cursor", 0)
        _integer(limit, "Page size")
        with self._read() as db:
            position = self._position(db, ordinal)
            if scope is not None:
                self._scope(db, position, scope)
            clauses = ["id>?", "(ordinal=? OR substr(ordinal,1,?)=?)"]
            params = [after, ordinal, len(ordinal) + 1, ordinal + "."]
            if scope is not None and scope.effort_root is None and ordinal == "0":
                clauses.append("ordinal IN (SELECT ordinal FROM positions WHERE effort IN (" + ",".join("?" for _ in scope.target_efforts) + "))")
                params.extend(scope.target_efforts)
            return [_row(row) for row in db.execute("SELECT * FROM legacy_mappings WHERE " + " AND ".join(clauses) + " ORDER BY id LIMIT ?", [*params, limit])]
