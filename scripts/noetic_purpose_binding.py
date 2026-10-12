"""Lossless owned-purpose binding around maintained structured executions."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import noetic_controller as controller
from scripts import noetic_disciplines as disciplines
from scripts.noetic_purposes import Purposes, PurposeError
from scripts.noetic_scope import Scope


FIELDS = ("purpose_ref", "purpose_config", "telos_chain", "telos_db", "telos_source", "goal_ref")


def configuration(adapter):
    return {"namespace_path": str(adapter.namespace_path), "purposes_root": str(adapter.purposes_root),
            "legacy_db": str(adapter.legacy_db) if adapter.legacy_db is not None else None,
            "source": str(adapter.source)}


def resolve(reference, config, assignment):
    if not isinstance(config, dict) or set(config) != {"namespace_path", "purposes_root", "legacy_db", "source"}:
        raise PurposeError("invalid_binding", "Owned purpose requires its complete explicit resolver configuration")
    if not isinstance(assignment, dict) or config["namespace_path"] != assignment.get("namespace_path"):
        raise PurposeError("invalid_binding", "Purpose resolver namespace differs from its execution assignment")
    if any(not isinstance(config[key], str) or not config[key] for key in ("namespace_path", "purposes_root", "source")):
        raise PurposeError("invalid_binding", "Purpose resolver paths must be explicit text")
    if config["legacy_db"] is not None and (not isinstance(config["legacy_db"], str) or not config["legacy_db"]):
        raise PurposeError("invalid_binding", "Purpose resolver legacy path must be explicit text or null")
    adapter = Purposes(config["namespace_path"], purposes_root=config["purposes_root"],
                       legacy_db=config["legacy_db"], source=config["source"])
    if configuration(adapter) != config:
        raise PurposeError("invalid_binding", "Purpose resolver requires its exact configured absolute paths")
    return adapter.resolve_run(reference, scope=Scope.effort(assignment["effort_root"]))


def prepare(reference, config, assignment, *, chain=None, db=None, source=None):
    resolved = resolve(reference, config, assignment)
    for supplied, expected in ((chain, resolved["chain_id"]), (db, resolved["db_path"]), (source, resolved["source"])):
        if supplied is not None and str(supplied) != expected:
            raise PurposeError("invalid_binding", "Telos selection differs from the complete owned purpose reference")
    return {"purpose_ref": deepcopy(resolved["purpose_ref"]), "purpose_config": deepcopy(config),
            "telos_chain": resolved["chain_id"], "telos_db": resolved["db_path"], "telos_source": resolved["source"]}


def validate(run_dir, options):
    """Read canonical assignment, frozen association and actual owner/store/chain."""
    run_dir = Path(run_dir).resolve(strict=True)
    retained = json.loads((run_dir / "options.json").read_text(encoding="utf-8"))
    if any(options.get(key) != retained.get(key) for key in FIELDS):
        raise PurposeError("invalid_binding", "Supplied purpose options differ from the retained run options")
    assignment = disciplines.validate_binding(run_dir, options=options)
    events = disciplines.runtime_events(run_dir)
    declared = [event["data"] for event in events if event["kind"] == "purpose.bound"]
    reference, config = options.get("purpose_ref"), options.get("purpose_config")
    if assignment is not None:
        canonical = disciplines.correspondence(run_dir)["native_run"]["options"]
        if any(options.get(key) != canonical.get(key) for key in FIELDS):
            raise PurposeError("invalid_binding", "Purpose options differ from the canonical execution")
    if reference is None and config is None and not declared:
        if assignment is not None and options.get("telos_chain"):
            raise PurposeError("unbound_legacy", "Scoped historical Telos selection lacks an owned purpose binding; start new explicitly bound work")
        return None
    if assignment is None:
        raise PurposeError("invalid_binding", "Owned purpose requires its retained canonical execution assignment")
    resolved = prepare(reference, config, assignment, chain=options.get("telos_chain"),
                       db=options.get("telos_db"), source=options.get("telos_source"))
    expected = {key: options.get(key) for key in FIELDS}
    if len(declared) != 1 or declared[0] != expected:
        raise PurposeError("invalid_binding", "Owned purpose differs from its retained native association")
    state = controller.inspect_run(run_dir / "controller.sqlite3")
    governing = state["artifacts"].get(state["slots"].get("external.governing"), {}).get("content", {})
    if governing.get("purpose_ref") != reference or governing.get("chain_id") != resolved["telos_chain"]:
        raise PurposeError("invalid_binding", "Controller governing purpose differs from the owned reference")
    for event in events:
        if event["kind"] == "telos.linked" and any(event["data"].get(key) != resolved[option]
                for key, option in (("chain_id", "telos_chain"), ("db_path", "telos_db"), ("source", "telos_source"))):
            raise PurposeError("invalid_binding", "Native Telos association differs from the owned reference")
    return resolved
