#!/usr/bin/env python3
"""Connect recorded noetic runs to the existing Telos core in an isolated database."""

from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

if __package__:
    from scripts import noetic_controller as controller
    from scripts import noetic_run as runtime
    from scripts.noetic_storage import create_private_sqlite
else:
    import noetic_controller as controller
    import noetic_run as runtime
    from noetic_storage import create_private_sqlite


DEFAULT_DB = Path(".runtime/telos.sqlite3")


def source_path(source: Path | str | None = None) -> Path:
    return Path(source or os.environ.get("NOETIC_TELOS_SOURCE") or Path.home() / "workspace/telos").expanduser().resolve()


def bundle_goal_store(source: Path | str, output: Path | str) -> dict:
    """Build the existing Telos factory as an independently deployable ES module."""
    source = source_path(source)
    entrypoint = Path("packages/pi-runtime/src/core-goal-chain-store.ts")
    esbuild = source / "node_modules/esbuild/bin/esbuild"
    for path in (source / entrypoint, esbuild):
        if not path.is_file():
            raise ValueError(f"Telos bundle requires the source factory and installed esbuild: missing {path}")
    output = Path(output).expanduser().resolve()
    if output.suffix != ".mjs":
        raise ValueError("Telos bundle output must be an .mjs file")
    output.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.pop("USER_PROVIDED_PASSWORD", None)
    try:
        result = subprocess.run(
            [str(esbuild), str(source / entrypoint), "--bundle", "--target=node24",
             "--format=esm", "--platform=node", "--external:node:*", f"--outfile={output}"],
            cwd=source, capture_output=True, text=True, timeout=120, env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"Telos bundle could not run the source's esbuild: {exc}") from exc
    if result.returncode:
        raise ValueError(f"Telos bundle failed: {result.stderr.strip()}")
    manifest = {
        "module": output.name, "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "source": str(source), "entrypoint": entrypoint.as_posix(),
        "source_identity": "built from current source including possible uncommitted changes",
        "target": "node24", "format": "esm", "platform": "node",
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"module": str(output), "manifest": str(manifest_path), "sha256": manifest["sha256"]}


def _bridge(operation: str, db: Path | str, source: Path | str | None, **data):
    source = source_path(source)
    module_mode = source.suffix == ".mjs" and not source.is_dir()
    loader = source / "node_modules/tsx/dist/loader.mjs"
    factory = source / "packages/pi-runtime/src/core-goal-chain-store.ts"
    for path in ((source,) if module_mode else (loader, factory)):
        if not path.is_file():
            raise ValueError(f"Telos component unavailable: {path}; set --source or NOETIC_TELOS_SOURCE")
    command = ["node"]
    if not module_mode:
        command.extend(["--import", loader.as_uri()])
    command.append(str(Path(__file__).with_name("telos_bridge.mjs")))
    db = create_private_sqlite(Path(db).expanduser())
    environment = os.environ.copy()
    environment.pop("USER_PROVIDED_PASSWORD", None)
    if not module_mode:
        environment["TSX_DISABLE_CACHE"] = "1"
    try:
        result = subprocess.run(
            command,
            input=json.dumps({"operation": operation, "dbPath": str(Path(db).expanduser().resolve()),
                              "source": str(source), **data}),
            capture_output=True, text=True, timeout=30,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        requirements = "Node 24" if module_mode else "Node 24 and the local tsx loader"
        raise ValueError(f"Telos bridge requires {requirements}: {exc}") from exc
    if result.returncode:
        raise ValueError(f"Telos bridge failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def create_goal(goal: str, db: Path | str = DEFAULT_DB, source: Path | str | None = None) -> dict:
    """Create a genuine, active Telos chain, global only within the explicit DB."""
    return _bridge("create", db, source, goal=goal)


def get_goal(chain_id: str, db: Path | str = DEFAULT_DB, source: Path | str | None = None) -> dict:
    """Reopen and return the native Telos aggregate; a missing chain is an error."""
    return _bridge("get", db, source, chainId=chain_id)


def list_goals(db: Path | str = DEFAULT_DB, source: Path | str | None = None) -> list[dict]:
    """Read native aggregates from a SQLite snapshot; never initialize the selected DB."""
    path = Path(db).expanduser().resolve()
    if not path.exists():
        return []
    with tempfile.TemporaryDirectory(prefix="noetic-goal-read-") as temporary:
        snapshot = Path(temporary) / "telos.sqlite3"
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(create_private_sqlite(snapshot))) as copy:
                original.backup(copy)
        return _bridge("list", snapshot, source)


def _run(run_dir: Path | str) -> tuple[Path, list[dict], dict, str]:
    run_dir = Path(run_dir).expanduser().resolve(strict=True)
    events = runtime.read_events(run_dir)
    status = runtime.project(events)
    objective = f"noetic run {status['run_id']}\n{status['goal']}".strip()
    return run_dir, events, status, objective


def _link(run_dir: Path, events: list[dict], association: dict, db, source) -> dict:
    link = {**association, "db_path": str(Path(db).expanduser().resolve()), "source": str(source_path(source)),
            "artifact_path": str(run_dir), "journal_path": str(run_dir / "events.sqlite3")}
    previous = next((event["data"] for event in reversed(events) if event["kind"] == "telos.linked"), None)
    if previous != link:
        runtime.record(run_dir, "telos.linked", link)
    return link


def begin_run(chain_id: str, run_dir: Path | str, db: Path | str = DEFAULT_DB,
              source: Path | str | None = None) -> dict:
    """Associate an already-created run with one Telos subgoal, without accepting it."""
    run_dir, events, _, objective = _run(run_dir)
    association = _bridge("begin", db, source, chainId=chain_id, objective=objective)
    return _link(run_dir, events, association, db, source)


def _controller_result(store: Path) -> dict:
    """Read the kernel's typed boundary, without rejudging or synthesizing review."""
    try:
        state = controller.inspect_run(store)
        pattern = state["pattern"]
        kind = pattern["kind"]
        if kind not in ("verified_sequence", "recurrent_operations") or state["status"] not in (
            "active", "completed", "failed", "blocked", "cancelled",
        ):
            raise ValueError("Unsupported controller pattern or status")
        completed = state["status"] == "completed"
        boundary, terminal, output = None, None, None
        if completed:
            verified = kind == "verified_sequence"
            phase = pattern["phases"][-1]
            output = state["artifacts"][state["slots"][f"{'accepted' if verified else 'effective'}.{phase['id']}"]]
            receipt = state["last_receipt"]
            terminal = state["artifacts"][receipt["artifact_id"]]
            if (state["machine_state"] != "completed" or state["current_activation"] is not None
                    or state["phase_index"] != 3 or receipt["version"] != state["version"]
                    or output["type"] != phase["output_type"] or output["partial"]
                    or terminal["partial"] or terminal["phase"] != phase["id"]
                    or receipt["outcome"] != ("pass" if verified else "complete")):
                raise ValueError("Controller completion lacks its typed terminal boundary")
            if verified:
                if (terminal["type"] != "qa.review"
                        or terminal["content"]["subject_artifact_id"] != output["id"]
                        or terminal["content"].get("verdict", terminal["content"].get("outcome")) != "pass"):
                    raise ValueError("Controller completion lacks terminal phase QA")
                boundary = "four_phase_qa_completion"
            else:
                if terminal["id"] != output["id"] or terminal["type"] != "cognition.P4":
                    raise ValueError("Controller completion lacks responsible P4 output")
                boundary = "responsible_cognitive_completion"
        refs = [{key: artifact[key] for key in ("id", "type", "digest", "activation_id", "produced_by")}
                if artifact is not None else None for artifact in (terminal, output)]
        return {
            "authority": "controller.sqlite3", "state": state["status"], "reason": state["reason"],
            "pattern": {key: pattern[key] for key in ("name", "kind", "version")},
            "controller_version": state["version"], "completion_boundary": boundary,
            "terminal_artifact": refs[0], "terminal_output": refs[1],
            "governing_artifact_id": state["slots"].get("external.governing"),
            "actor_refs": [{key: activation.get(key) for key in (
                "actor_id", "id", "ordinal", "role", "phase", "mode", "status", "session_ref", "result_artifact_id",
            )} for activation in state["activations"].values()],
            "reviewer": None, "verdict": None,
            "subgoal_status": "complete" if completed else "active",
        }
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError, sqlite3.Error) as exc:
        raise ValueError(f"Cannot read controller result: {exc}") from exc


def record_result(chain_id: str, subgoal_id: str, run_dir: Path | str, db: Path | str = DEFAULT_DB,
                   source: Path | str | None = None) -> dict:
    """Record kernel completion when present; otherwise retain legacy reviewed acceptance."""
    run_dir, events, status, objective = _run(run_dir)
    disposition = {
        "run_id": status["run_id"],
        "artifact_path": str(run_dir), "journal_path": str(run_dir / "events.sqlite3"),
    }
    store = run_dir / "controller.sqlite3"
    if store.exists() or store.is_symlink():
        # Even a stale accepted observation cannot override current kernel authority.
        disposition.update(_controller_result(store))
    else:
        review = status["review"]
        accepted = status["state"] == "accepted" and isinstance(review, dict) and (
            review.get("verdict") == "accept" and all(
                isinstance(review.get(key), str) and review[key].strip() for key in ("reviewer", "evidence")
            )
        )
        disposition.update({
            "state": status["state"], "reviewer": review.get("reviewer") if review else None,
            "verdict": review.get("verdict") if review else None,
            "subgoal_status": "complete" if accepted else "active",
        })
    link_path = run_dir / "opermem-link.json"
    if link_path.exists():
        link = json.loads(link_path.read_text(encoding="utf-8"))
        deposit = {"operation": link["operation"], "submission": "pending"}
        receipt_path = run_dir / "opermem-receipt.json"
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))["response"]
            payload = receipt["payload"]
            if not ((receipt["class"] == "success" and receipt["kind"] == "command-accepted")
                    or (receipt["class"] == "idempotency-replay" and payload.get("accepted") is True)):
                raise ValueError("Opermem receipt does not establish a committed contribution")
            deposit.update(submission="committed", receipt_id=payload["receipt_id"])
        disposition["opermem"] = deposit
        if deposit["submission"] != "committed":
            disposition["subgoal_status"] = "active"
    note = "noetic.run.result " + json.dumps({"subgoal_id": subgoal_id, **disposition}, sort_keys=True)
    association = _bridge("record", db, source, chainId=chain_id, subGoalId=subgoal_id,
                          objective=objective, status=disposition["subgoal_status"], note=note)
    result = {**_link(run_dir, events, association, db, source), **disposition}
    if status.get("telos_result") != result or status.get("telos_error"):
        runtime.record(run_dir, "telos.result", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    bundle = commands.add_parser("bundle", help="build a standalone Telos ES module using the source's esbuild")
    bundle.add_argument("--source", type=Path, required=True, help="Telos source root with esbuild installed")
    bundle.add_argument("--output", type=Path, required=True, help="output .mjs path; also writes an adjacent .manifest.json")
    create = commands.add_parser("create", help="create an active Telos master goalchain")
    create.add_argument("goal")
    get = commands.add_parser("get", help="read the native Telos aggregate")
    get.add_argument("chain_id")
    attach = commands.add_parser("attach", help="associate an existing run and record its current result")
    attach.add_argument("chain_id")
    attach.add_argument("run_dir", type=Path)
    record = commands.add_parser("record", help="record a linked run's current result")
    record.add_argument("chain_id")
    record.add_argument("subgoal_id")
    record.add_argument("run_dir", type=Path)
    for command in (create, get, attach, record):
        command.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"isolated database (default: {DEFAULT_DB})")
        command.add_argument("--source", type=Path, help="Telos source root or bundled .mjs; otherwise NOETIC_TELOS_SOURCE or ~/workspace/telos")
    args = parser.parse_args(argv)
    try:
        if args.command == "bundle":
            result = bundle_goal_store(args.source, args.output)
        elif args.command == "create":
            result = create_goal(args.goal, args.db, args.source)
        elif args.command == "get":
            result = get_goal(args.chain_id, args.db, args.source)
        else:
            subgoal_id = args.subgoal_id if args.command == "record" else begin_run(
                args.chain_id, args.run_dir, args.db, args.source,
            )["subgoal_id"]
            result = record_result(args.chain_id, subgoal_id, args.run_dir, args.db, args.source)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        if args.command in ("attach", "record") and (args.run_dir / "controller.sqlite3").exists():
            runtime.record(args.run_dir, "telos.error", {"operation": args.command, "error": str(exc)})
        print(f"noetic Telos failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
