#!/usr/bin/env python3
"""Execute a bounded, frozen task batch using the existing reviewed-run runtime."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import sys
import uuid

if __package__:
    from scripts import noetic_develop as development
    from scripts import noetic_run as runtime
    from scripts import noetic_telos as telos
else:
    import noetic_develop as development
    import noetic_run as runtime
    import noetic_telos as telos


MAX_TASKS = 32
OPTION_KEYS = {
    "workspace", "runs_dir", "client", "model", "review_model", "timeout", "goal_ref",
    "telos_chain", "telos_db", "telos_source",
}


def task_order(tasks: object, frozen: bool = False) -> list[str]:
    """Validate every task, then choose the first ready manifest entry at each step."""
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= MAX_TASKS:
        raise ValueError(f"tasks must be an array of 1 to {MAX_TASKS} tasks")
    by_id = {}
    for task in tasks:
        required = {"id", "program", "task", "depends_on"} | ({"task_text"} if frozen else set())
        if not isinstance(task, dict) or not required <= task.keys() or task.keys() - required - {"verify"}:
            raise ValueError("each task requires id, program, task, depends_on; optional verify")
        task_id = task["id"]
        if not isinstance(task_id, str) or not task_id.strip() or "\0" in task_id or task_id in by_id:
            raise ValueError("task IDs must be unique, nonempty strings without NUL")
        if task["program"] not in ("develop", "inquire"):
            raise ValueError(f"{task_id}: program must be develop or inquire")
        path = task["task"]
        if not isinstance(path, str) or not path.strip() or "\0" in path or Path(path).is_absolute():
            raise ValueError(f"{task_id}: task must be a relative file path")
        deps = task["depends_on"]
        if not isinstance(deps, list) or any(not isinstance(dep, str) or not dep.strip() for dep in deps):
            raise ValueError(f"{task_id}: depends_on must be an array of task IDs")
        if len(set(deps)) != len(deps):
            raise ValueError(f"{task_id}: duplicate dependencies")
        text = task["task_text"] if frozen else task_id
        plan = {"goal": text, "work": ["opencode", text]}
        if "verify" in task:
            plan["verify"] = task["verify"]
        runtime.validate_plan(plan, require_verify=task["program"] == "develop")
        by_id[task_id] = task
    for task_id, task in by_id.items():
        missing = set(task["depends_on"]) - by_id.keys()
        if missing:
            raise ValueError(f"{task_id}: missing dependencies: {', '.join(sorted(missing))}")
    order = []
    while len(order) < len(tasks):
        ready = next((task_id for task_id, task in by_id.items()
                      if task_id not in order and set(task["depends_on"]) <= set(order)), None)
        if ready is None:
            raise ValueError("task dependencies contain a cycle")
        order.append(ready)
    return order


def validate_options(options: object) -> None:
    if not isinstance(options, dict) or options.keys() != OPTION_KEYS:
        raise ValueError("batch execution options are incomplete or unknown")
    for key in OPTION_KEYS - {"timeout"}:
        value = options[key]
        if value is None and key in {"model", "review_model", "goal_ref", "telos_chain", "telos_source"}:
            continue
        if not isinstance(value, str) or not value.strip() or "\0" in value:
            raise ValueError(f"{key} must be a nonempty string")
    if options["client"] not in ("opencode", "pi"):
        raise ValueError("client must be opencode or pi")
    for key in ("workspace", "runs_dir", "telos_db", "telos_source"):
        if options[key] is not None and not Path(options[key]).is_absolute():
            raise ValueError(f"frozen {key} must be absolute")
    runtime.validate_plan({"goal": "batch", "work": [options["client"]],
                           "timeout_seconds": options["timeout"]}, require_verify=False)


def preflight_execution(options: dict, tasks: list[dict]) -> None:
    """Check local prerequisites without executing commands or consulting a model."""
    if os.name != "posix":
        raise ValueError("batch execution requires POSIX flock")
    workspace = Path(options["workspace"])
    if not workspace.is_dir():
        raise ValueError(f"workspace must be an existing directory: {workspace}")
    runs_dir = Path(options["runs_dir"])
    if any(path.exists() and not path.is_dir() for path in (runs_dir, *runs_dir.parents)):
        raise ValueError(f"runs_dir must be a directory: {runs_dir}")
    commands = [[options["client"]]] + [task["verify"] for task in tasks if "verify" in task]
    if options["telos_chain"]:
        commands.append(["node"])
        source = Path(options["telos_source"])
        files = [source] if source.suffix == ".mjs" and not source.is_dir() else [
            source / "packages/pi-runtime/src/core-goal-chain-store.ts",
            source / "node_modules/tsx/dist/loader.mjs",
        ]
        for path in files:
            if not path.is_file():
                raise ValueError(f"Telos component unavailable: {path}")
        if Path(options["telos_db"]).is_dir():
            raise ValueError("telos_db must be a file path")
    search_path = os.pathsep.join(str((workspace / part).resolve()) for part in os.get_exec_path())
    for command in commands:
        executable = command[0]
        if "/" in executable:
            executable = str(workspace / executable)
        if shutil.which(executable, path=search_path) is None:
            raise ValueError(f"command executable not found or not executable: {command[0]}")


def create_batch(manifest: Path, workspace: Path, runs_dir: Path, batches_dir: Path,
                 client: str = "opencode", model: str | None = None, review_model: str | None = None,
                 timeout: float = 900, goal_ref: str | None = None, telos_chain: str | None = None,
                 telos_db: Path | None = None, telos_source: Path | None = None) -> Path:
    """Preflight and freeze inputs; no child execution occurs in this function."""
    manifest = manifest.expanduser().resolve(strict=True)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.keys() != {"name", "tasks"}:
        raise ValueError("manifest requires only name and tasks")
    if not isinstance(data["name"], str) or not data["name"].strip():
        raise ValueError("batch name must be a nonempty string")
    order = task_order(data["tasks"])
    tasks = []
    for task in data["tasks"]:
        with (manifest.parent / task["task"]).open(encoding="utf-8", newline="") as source:
            text = source.read()
        tasks.append({**task, "task_text": text})
    task_order(tasks, frozen=True)
    workspace = workspace.expanduser().resolve(strict=True)
    options = {
        "workspace": str(workspace), "runs_dir": str(runs_dir.expanduser().resolve()),
        "client": client, "model": model, "review_model": review_model, "timeout": timeout,
        "goal_ref": goal_ref, "telos_chain": telos_chain,
        "telos_db": str((telos_db or workspace / ".runtime/telos.sqlite3").expanduser().resolve()),
        "telos_source": str(telos.source_path(telos_source)) if telos_chain or telos_source else None,
    }
    validate_options(options)
    preflight_execution(options, tasks)
    batch_id = uuid.uuid4().hex
    batch_dir = batches_dir.expanduser().resolve() / batch_id
    batch_dir.mkdir(parents=True)
    frozen = {"version": 1, "batch_id": batch_id, "name": data["name"], "manifest": str(manifest),
              "options": options, "tasks": tasks, "order": order}
    with (batch_dir / "batch.json").open("x", encoding="utf-8") as output:
        output.write(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
        output.flush()
        os.fsync(output.fileno())
    print(f"Batch: {batch_dir}", flush=True)
    return batch_dir


def load_batch(batch_dir: Path) -> dict:
    data = json.loads((batch_dir / "batch.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.keys() != {
        "version", "batch_id", "name", "manifest", "options", "tasks", "order",
    } or data["version"] != 1:
        raise ValueError("invalid batch.json format or version")
    if not isinstance(data["batch_id"], str) or uuid.UUID(data["batch_id"]).hex != data["batch_id"]:
        raise ValueError("invalid batch UUID")
    if not isinstance(data["name"], str) or not data["name"].strip():
        raise ValueError("invalid batch name")
    if task_order(data["tasks"], frozen=True) != data["order"]:
        raise ValueError("frozen task order does not match dependencies")
    validate_options(data["options"])
    if data["options"]["telos_chain"] and not data["options"]["telos_source"]:
        raise ValueError("frozen Telos chain requires its source path")
    return data


def batch_status(batch_dir: Path) -> dict:
    """Project children afresh; batch.json never contains execution outcomes."""
    batch_dir = batch_dir.expanduser().resolve(strict=True)
    data = load_batch(batch_dir)
    tasks = {task["id"]: task for task in data["tasks"]}
    rows = []
    for task_id in data["order"]:
        task = tasks[task_id]
        run_id = uuid.uuid5(uuid.UUID(data["batch_id"]), task_id).hex
        run_dir = Path(data["options"]["runs_dir"]) / run_id
        row = {"id": task_id, "program": task["program"], "depends_on": task["depends_on"],
               "run_id": run_id, "run_dir": str(run_dir), "state": "pending"}
        if os.path.lexists(run_dir):
            if not run_dir.is_dir() or not (run_dir / "events.sqlite3").is_file():
                row.update(state="missing_journal", reason="existing child path has no journal; needs disposition")
            else:
                try:
                    child = runtime.project(runtime.read_events(run_dir))
                    if child["run_id"] != run_id or child["workspace"] != data["options"]["workspace"] or child["goal"] != task["task_text"]:
                        raise ValueError("child creation event does not match frozen task")
                    if child["state"] == "accepted":
                        review = child["review"]
                        if not isinstance(review, dict) or review.get("verdict") != "accept" or any(
                            not isinstance(review.get(key), str) or not review[key].strip()
                            for key in ("reviewer", "evidence")
                        ):
                            raise ValueError("accepted child has no recorded review evidence")
                    row["state"] = child["state"]
                    if child.get("telos_error"):
                        row["reason"] = f"Telos result needs disposition: {child['telos_error']}"
                    elif child["state"] != "accepted":
                        row["reason"] = "existing nonaccepted child needs disposition; never retried automatically"
                except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, AttributeError) as exc:
                    row.update(state="corrupt", reason=f"unreadable child journal; needs disposition: {exc}")
        rows.append(row)
    held = any("reason" in row for row in rows)
    accepted = {row["id"] for row in rows if row["state"] == "accepted" and "reason" not in row}
    state = "held" if held else "complete" if len(accepted) == len(rows) else "ready"
    for row in rows:
        row["disposition"] = (
            "needs_disposition" if "reason" in row else "skip" if row["id"] in accepted else
            "blocked" if held or not set(row["depends_on"]) <= accepted else "ready"
        )
    return {"batch_id": data["batch_id"], "name": data["name"], "batch_dir": str(batch_dir),
            "state": state, "tasks": rows}


def resume_batch(batch_dir: Path) -> dict:
    """Sequential execution under one cooperative lock, with no retries or repairs."""
    if os.name != "posix":
        raise ValueError("batch execution requires POSIX flock")
    import fcntl

    batch_dir = batch_dir.expanduser().resolve(strict=True)
    with (batch_dir / ".execution.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("batch is already executing; retry after the other controller exits") from exc
        data = load_batch(batch_dir)
        status = batch_status(batch_dir)
        if status["state"] != "ready":
            return status
        tasks = {task["id"]: task for task in data["tasks"]}
        options = data["options"]
        preflight_execution(options, [tasks[row["id"]] for row in status["tasks"] if row["state"] == "pending"])
        while status["state"] == "ready":
            row = next(row for row in status["tasks"] if row["disposition"] == "ready")
            task = tasks[row["id"]]
            development.develop(
                task["task_text"], Path(options["workspace"]), Path(options["runs_dir"]), task.get("verify"),
                client=options["client"], model=options["model"], review_model=options["review_model"],
                timeout=options["timeout"], goal_ref=options["goal_ref"], telos_chain=options["telos_chain"],
                telos_db=Path(options["telos_db"]),
                telos_source=Path(options["telos_source"]) if options["telos_source"] else None,
                inquiry=task["program"] == "inquire", run_id=row["run_id"],
                dependency_runs={child["id"]: child["run_dir"] for child in status["tasks"]
                                 if child["id"] in task["depends_on"]},
            )
            # The launcher's return value is not evidence of acceptance.
            status = batch_status(batch_dir)
            if next(child for child in status["tasks"] if child["id"] == row["id"])["state"] == "pending":
                raise ValueError(f"{row['id']}: launcher returned without creating a child journal; stopped")
        return status


def render_status(status: dict, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(status, indent=2, sort_keys=True))
        return
    print(f"Batch: {status['batch_dir']}\nName: {status['name']}\nState: {status['state']}")
    for task in status["tasks"]:
        print(f"  {task['id']}: {task['state']} ({task['disposition']})\n    Run: {task['run_dir']}")
        if task.get("reason"):
            print(f"    {task['reason']}")
    if status["state"] == "held":
        print("Held: inspect child evidence and obtain an explicit disposition. No child is retried.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="preflight, freeze, then execute a new batch")
    run.add_argument("manifest", type=Path)
    run.add_argument("--workspace", type=Path, default=Path.cwd())
    run.add_argument("--runs-dir", type=Path)
    run.add_argument("--batches-dir", type=Path)
    run.add_argument("--client", choices=("opencode", "pi"), default="opencode")
    run.add_argument("--model")
    run.add_argument("--review-model")
    run.add_argument("--timeout", type=float, default=900, help="seconds per child process")
    run.add_argument("--goal-ref")
    run.add_argument("--telos-chain", help="existing governing chain; passed to each child, never completed by batch")
    run.add_argument("--telos-db", type=Path)
    run.add_argument("--telos-source", type=Path, help="Telos source directory or bundled .mjs")
    resume = commands.add_parser("resume", help="skip accepted children; hold all other existing children")
    resume.add_argument("batch_dir", type=Path)
    status = commands.add_parser("status", help="derive current state from child journals")
    status.add_argument("batch_dir", type=Path)
    status.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, interrupt)
    try:
        if args.command == "status":
            render_status(batch_status(args.batch_dir), args.json)
            return 0
        if args.command == "run":
            batch_dir = create_batch(
                args.manifest, args.workspace, args.runs_dir or args.workspace / ".runtime/runs",
                args.batches_dir or args.workspace / ".runtime/batches", args.client, args.model,
                args.review_model, args.timeout, args.goal_ref, args.telos_chain, args.telos_db, args.telos_source,
            )
        else:
            batch_dir = args.batch_dir
        result = resume_batch(batch_dir)
        render_status(result)
        return 0 if result["state"] == "complete" else 1
    except (OSError, ValueError, sqlite3.Error, KeyboardInterrupt) as exc:
        print(f"noetic batch stopped: {str(exc) or 'interrupted; inspect batch status before resuming'}", file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    raise SystemExit(main())
