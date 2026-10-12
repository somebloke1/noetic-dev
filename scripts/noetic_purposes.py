"""Explicit Noetic ownership around native Telos stores and unchanged aggregates."""

from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import uuid

from scripts import noetic_telos as telos
from scripts.noetic_scope import Scope, ScopeStore


# Required tables of maintained Telos SCHEMA_V2_SQL; no native schema is created here.
_NATIVE_TABLES = frozenset({
    "meta", "projects", "project_roots", "chains", "sub_goals", "records", "sessions",
    "clause_versions", "project_identity_events", "delegations", "delegation_events",
})


class PurposeError(ValueError):
    def __init__(self, code, message, *, reference=None):
        super().__init__(message)
        self.code = code
        self.reference = reference

    def as_dict(self):
        result = {"code": self.code, "message": str(self)}
        if self.reference is not None:
            result["reference"] = self.reference
        return result


class Purposes:
    """A registered namespace and explicit owner select a native store.

    Construction and reads never register a namespace or initialize native state.
    The namespace's schema-1 identity/ownership fields are read without invoking
    ScopeStore's constructor, which also creates tables and opens a write txn.
    """

    def __init__(self, namespace_path, *, purposes_root=None, legacy_db=None, source=None):
        self.namespace_path = Path(namespace_path).expanduser().resolve()
        self.purposes_root = (Path(purposes_root).expanduser().resolve() if purposes_root is not None
                              else self.namespace_path.parent / "purposes")
        self.legacy_db = Path(legacy_db).expanduser().resolve() if legacy_db is not None else None
        self.source = telos.source_path(source)

    def _namespace(self, scope, owner=None):
        if not isinstance(scope, Scope):
            raise PurposeError("scope_required", "An explicit operation Scope is required")
        try:
            self.namespace_path.stat()
        except FileNotFoundError as exc:
            raise PurposeError("namespace_absent", "Application namespace has not been registered") from exc
        except OSError as exc:
            raise PurposeError("namespace_unavailable", str(exc)) from exc
        try:
            with closing(sqlite3.connect(self.namespace_path.as_uri() + "?mode=ro", uri=True)) as db:
                db.execute("BEGIN")
                metadata = dict(db.execute("SELECT key,value FROM metadata"))
                namespace = metadata.get("namespace")
                if metadata.get("schema") != "1" or str(uuid.UUID(namespace)) != namespace:
                    raise PurposeError("namespace_corrupt", "Unsupported or incomplete application namespace")
                root = db.execute("SELECT parent,effort,mandate_version FROM positions WHERE ordinal='0'").fetchone()
                if root is None or root[:2] != (None, None):
                    raise PurposeError("namespace_corrupt", "Application root identity is incomplete")
                efforts = {row[0] for row in db.execute(
                    "SELECT e.ordinal FROM efforts e JOIN positions p ON p.ordinal=e.ordinal "
                    "WHERE p.effort=e.ordinal AND p.parent='0'")}
                if scope.effort_root is not None:
                    ordinals = [scope.effort_root]
                else:
                    if scope.root_mandate_version != root[2]:
                        raise PurposeError("scope_mismatch", "Application scope names a stale root mandate")
                    ordinals = ["0", *scope.target_efforts]
                if any(ordinal != "0" and ordinal not in efforts for ordinal in ordinals) or (
                    scope.effort_root == "0"
                ):
                    raise PurposeError("scope_mismatch", "Purpose scope requires an already registered effort root")
                if owner is not None and owner not in ordinals:
                    raise PurposeError("scope_mismatch", "Operation scope does not own the requested purpose store")
                return namespace, ordinals
        except PurposeError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
            raise PurposeError("namespace_corrupt", f"Cannot read application namespace: {exc}") from exc

    def _store(self, namespace, ordinal):
        kind = "application" if ordinal == "0" else "effort"
        relative = Path(namespace) / ("application" if ordinal == "0" else f"efforts/{ordinal}") / "telos.sqlite3"
        path = self.purposes_root / relative
        if self.legacy_db == path:
            raise PurposeError("scope_mismatch", "Legacy history cannot be used as an owned purpose store")
        return {"owner": {"namespace": namespace, "kind": kind, "ordinal": ordinal},
                "store_id": relative.as_posix(), "db_path": str(path)}

    def _legacy(self):
        return {"owner": {"namespace": None, "kind": "legacy-unassigned", "ordinal": None},
                "store_id": "legacy-unassigned", "db_path": str(self.legacy_db)}

    def _component(self):
        paths = ((self.source,) if self.source.suffix == ".mjs" and not self.source.is_dir() else (
            self.source / "node_modules/tsx/dist/loader.mjs",
            self.source / "packages/pi-runtime/src/core-goal-chain-store.ts"))
        if shutil.which("node") is None or any(not path.is_file() for path in paths):
            raise PurposeError("native_unavailable", f"Telos requires Node 24 and configured component {self.source}")

    def _read_native(self, store):
        path = Path(store["db_path"])
        try:
            info = path.lstat()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise PurposeError("store_unavailable", str(exc)) from exc
        try:
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise PurposeError("store_corrupt", "Native store must be a single-link regular database")
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
                db.execute("BEGIN")
                if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise PurposeError("store_corrupt", "Native SQLite integrity check failed")
                tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                missing = _NATIVE_TABLES - tables
                if missing:
                    raise PurposeError("store_corrupt", "Native Telos store is incomplete; missing tables: "
                                       + ", ".join(sorted(missing)))
                if db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() is None:
                    raise PurposeError("store_corrupt", "Native Telos schema identity is missing")
                if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise PurposeError("store_corrupt", "Native Telos references are incomplete")
        except PurposeError:
            raise
        except sqlite3.Error as exc:
            raise PurposeError("store_corrupt", f"Cannot read native store: {exc}") from exc
        self._component()
        try:
            return telos.list_goals(path, self.source)
        except (OSError, ValueError, sqlite3.Error) as exc:
            raise PurposeError("native_error", f"Native Telos read failed: {exc}") from exc

    def _reference(self, store, native):
        return {**store, "chain_id": native["chain"]["chainId"], "source": str(self.source)}

    def _evidence(self, reference):
        if reference["owner"]["kind"] == "legacy-unassigned":
            return None
        try:
            with closing(sqlite3.connect(self.namespace_path.as_uri() + "?mode=ro", uri=True)) as db:
                db.row_factory = sqlite3.Row
                for row in db.execute("SELECT * FROM history WHERE ordinal=? AND kind='purpose-created' ORDER BY sequence",
                                      (reference["owner"]["ordinal"],)):
                    event = dict(row)
                    event["data"] = json.loads(event["data"])
                    recorded = event["data"].get("purpose_ref", {})
                    if all(recorded.get(key) == reference[key] for key in ("owner", "store_id", "chain_id")):
                        event["source_ref"] = json.loads(event["source_ref"])
                        return event
        except (sqlite3.Error, ValueError, TypeError, AttributeError) as exc:
            raise PurposeError("namespace_corrupt", f"Purpose ownership evidence is unreadable: {exc}") from exc
        return None

    def _purpose(self, store, native):
        reference = self._reference(store, native)
        return {"reference": reference, "native": native, "ownership_event": self._evidence(reference)}

    def list(self, *, scope, include_legacy=False):
        namespace, ordinals = self._namespace(scope)
        if include_legacy and scope.effort_root is not None:
            raise PurposeError("scope_mismatch", "Unassigned legacy history requires explicit application scope")
        stores = [self._store(namespace, ordinal) for ordinal in ordinals]
        if include_legacy:
            if self.legacy_db is None:
                raise PurposeError("legacy_unconfigured", "No legacy native store was explicitly selected")
            stores.append(self._legacy())
        return self._list_stores(stores)

    def list_unassigned(self):
        """Inspect explicitly selected legacy history, including before registration."""
        if self.legacy_db is None:
            raise PurposeError("legacy_unconfigured", "No legacy native store was explicitly selected")
        return self._list_stores([self._legacy()])

    def _list_stores(self, stores):
        result = {"purposes": [], "stores": [], "coverage": "complete"}
        for store in stores:
            try:
                aggregates = self._read_native(store)
                purposes = [] if aggregates is None else [self._purpose(store, native) for native in aggregates]
                result["purposes"].extend(purposes)
                result["stores"].append({**store, "status": "absent" if aggregates is None else "available"})
            except PurposeError as exc:
                result["coverage"] = "partial"
                result["stores"].append({**store, "status": "error", "error": exc.as_dict()})
        return result

    def create(self, goal, *, scope, owner=None, origin_ref, source_ref):
        if not isinstance(goal, str) or not goal.strip() or "\0" in goal:
            raise PurposeError("invalid_goal", "Purpose goal must be nonempty text")
        for name, value in (("Origin reference", origin_ref), ("Source reference", source_ref)):
            if not isinstance(value, dict) or not value:
                raise PurposeError("invalid_reference", f"{name} must be a nonempty object")
            try:
                json.dumps(value, allow_nan=False)
            except (TypeError, ValueError) as exc:
                raise PurposeError("invalid_reference", f"{name} is not JSON data") from exc
        owner = owner if owner is not None else (scope.effort_root if isinstance(scope, Scope) and scope.effort_root else "0")
        namespace, _ = self._namespace(scope, owner)
        store = self._store(namespace, owner)
        self._component()
        self._read_native(store)
        try:
            native = telos.create_goal(goal, store["db_path"], self.source)
        except (OSError, ValueError, sqlite3.Error) as exc:
            raise PurposeError("native_error", f"Native Telos creation failed: {exc}") from exc
        reference = self._reference(store, native)
        # Native creation and namespace evidence are separate durable boundaries.
        try:
            event = ScopeStore(self.namespace_path).record_event(
                owner, scope=scope, kind="purpose-created", data={"purpose_ref": reference, "origin_ref": origin_ref},
                source_ref=source_ref)
        except (OSError, ValueError, sqlite3.Error) as exc:
            raise PurposeError("ownership_record_failed", f"Native chain exists but ownership event failed: {exc}",
                               reference=reference) from exc
        return {"reference": reference, "native": native, "ownership_event": event}

    def resolve(self, reference, *, scope):
        if not isinstance(reference, dict) or set(reference) != {"owner", "store_id", "db_path", "chain_id", "source"}:
            raise PurposeError("invalid_reference", "Use the complete owned purpose reference, not a bare chain ID")
        owner = reference["owner"]
        if not isinstance(owner, dict) or set(owner) != {"namespace", "kind", "ordinal"}:
            raise PurposeError("invalid_reference", "Purpose reference requires explicit namespace and owner")
        if owner["kind"] not in ("application", "effort"):
            raise PurposeError("scope_mismatch", "Unassigned legacy chains cannot bind scoped work")
        namespace, _ = self._namespace(scope, owner["ordinal"])
        expected = self._store(namespace, owner["ordinal"])
        if any(reference[key] != expected[key] for key in expected) or reference["source"] != str(self.source):
            raise PurposeError("scope_mismatch", "Purpose reference does not match configured ownership/store/source")
        if not isinstance(reference["chain_id"], str) or not reference["chain_id"]:
            raise PurposeError("invalid_reference", "Purpose reference requires its native chain ID")
        aggregates = self._read_native(expected)
        if aggregates is None:
            raise PurposeError("store_absent", "Selected owned native store is absent")
        for native in aggregates:
            if native["chain"]["chainId"] == reference["chain_id"]:
                return self._purpose(expected, native)
        raise PurposeError("chain_not_found", "Native chain does not exist in the selected owner's store")

    def resolve_run(self, reference, *, scope):
        purpose = self.resolve(reference, scope=scope)
        ref = purpose["reference"]
        return {"chain_id": ref["chain_id"], "db_path": ref["db_path"], "source": str(self.source), "purpose_ref": ref}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace-path", "--namespace", dest="namespace", type=Path, required=True)
    parser.add_argument("--purposes-root", type=Path)
    parser.add_argument("--legacy-db", type=Path)
    parser.add_argument("--source", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list-unassigned", help="Explicit legacy history; namespace registration is not required")
    for name in ("list", "create", "resolve", "resolve-run"):
        command = commands.add_parser(name)
        selection = command.add_mutually_exclusive_group(required=True)
        selection.add_argument("--effort")
        selection.add_argument("--application", action="store_true")
        command.add_argument("--root-mandate-version", type=int)
        command.add_argument("--target-effort", action="append", default=[])
        if name == "list":
            command.add_argument("--include-legacy", action="store_true")
        elif name == "create":
            command.add_argument("goal")
            command.add_argument("--owner")
            command.add_argument("--origin-ref", type=json.loads, required=True)
            command.add_argument("--source-ref", type=json.loads, required=True)
        else:
            command.add_argument("reference", type=json.loads, help="Complete purpose reference as JSON")
    args = parser.parse_args(argv)
    try:
        adapter = Purposes(args.namespace, purposes_root=args.purposes_root, legacy_db=args.legacy_db, source=args.source)
        if args.command == "list-unassigned":
            result = adapter.list_unassigned()
            print(json.dumps(result, sort_keys=True))
            return 1 if result["coverage"] == "partial" else 0
        if args.effort and (args.root_mandate_version is not None or args.target_effort):
            raise PurposeError("scope_mismatch", "Effort scope cannot name application mandate/targets")
        scope = (Scope.effort(args.effort) if args.effort else
                 Scope.application(args.target_effort, root_mandate_version=args.root_mandate_version))
        if args.command == "list":
            result = adapter.list(scope=scope, include_legacy=args.include_legacy)
        elif args.command == "create":
            result = adapter.create(args.goal, scope=scope, owner=args.owner,
                                    origin_ref=args.origin_ref, source_ref=args.source_ref)
        else:
            result = (adapter.resolve_run if args.command == "resolve-run" else adapter.resolve)(args.reference, scope=scope)
        print(json.dumps(result, sort_keys=True))
        return 1 if result.get("coverage") == "partial" else 0
    except (OSError, ValueError) as exc:
        error = exc.as_dict() if isinstance(exc, PurposeError) else {"code": "invalid_scope", "message": str(exc)}
        print(json.dumps({"error": error}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
