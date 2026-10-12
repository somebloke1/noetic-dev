#!/usr/bin/env python3
"""Run goal-directed work, verify it, and retain evidence for separate review."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
import uuid

if __package__:
    from scripts import noetic_processes as processes
    from scripts.noetic_storage import create_private_sqlite, ensure_private_directory, open_private
else:
    import noetic_processes as processes
    from noetic_storage import create_private_sqlite, ensure_private_directory, open_private


def validate_plan(plan: object, require_verify: bool = True) -> dict:
    if not isinstance(plan, dict):
        raise ValueError("plan must be a JSON object")
    required = {"goal", "work"} | ({"verify"} if require_verify else set())
    allowed = required | {"goal_ref", "timeout_seconds", "verify"}
    if not required <= plan.keys() or plan.keys() - allowed:
        raise ValueError("plan requires goal, work, verify; optional goal_ref, timeout_seconds")
    for key in ("goal", "goal_ref"):
        if key in plan and (not isinstance(plan[key], str) or not plan[key].strip()):
            raise ValueError(f"{key} must be a nonempty string")
    for key in ("work", "verify"):
        if key not in plan:
            continue
        argv = plan[key]
        if not isinstance(argv, list) or not argv or any(
            not isinstance(arg, str) or "\0" in arg for arg in argv
        ) or not argv[0]:
            raise ValueError(f"{key} must be a nonempty command argument array")
    timeout = plan.get("timeout_seconds", 900)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout_seconds must be a finite positive number")
    return {**plan, "timeout_seconds": timeout}


def append_event(connection: sqlite3.Connection, kind: str, data: dict) -> None:
    connection.execute(
        "INSERT INTO events (occurred_at, kind, data) VALUES (?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), kind, json.dumps(data, sort_keys=True)),
    )


def record(run_dir: Path, kind: str, data: dict) -> None:
    with closing(sqlite3.connect(create_private_sqlite(run_dir / "events.sqlite3"))) as connection:
        with connection:
            append_event(connection, kind, data)


def read_events(run_dir: Path) -> list[dict]:
    uri = (run_dir / "events.sqlite3").resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        return [
            {"sequence": seq, "occurred_at": at, "kind": kind, "data": json.loads(data)}
            for seq, at, kind, data in connection.execute(
                "SELECT sequence, occurred_at, kind, data FROM events ORDER BY sequence"
            )
        ]


def project(events: list[dict]) -> dict:
    if not events or events[0]["kind"] != "run.created":
        raise ValueError("run has no creation event")
    created = events[0]["data"]
    result = {
        "run_id": created["run_id"],
        "goal": created["plan"]["goal"],
        "goal_ref": created["plan"].get("goal_ref"),
        "workspace": created["workspace"],
        "state": "unfinished",
        "steps": {},
        "review": None,
    }
    for event in events[1:]:
        kind, data = event["kind"], event["data"]
        if kind in ("step.started", "step.finished"):
            result["steps"][data["step"]] = data
        elif kind == "run.finished":
            result["state"] = data["state"]
        elif kind == "review.recorded":
            result["state"] = "accepted" if data["verdict"] == "accept" else "rejected"
            result["review"] = data
        elif kind == "telos.linked":
            result["telos"] = data
        elif kind == "telos.result":
            result["telos_result"] = data
            result.pop("telos_error", None)
        elif kind == "telos.error":
            result["telos_error"] = data["error"]
    result["last_event_at"] = events[-1]["occurred_at"]
    return result


def list_runs(runs_dir: Path) -> list[dict]:
    runs = []
    try:
        children = list(runs_dir.iterdir())
    except FileNotFoundError:
        return []
    for run_dir in children:
        try:
            if not run_dir.is_dir() or not (run_dir / "events.sqlite3").is_file():
                continue
            events = read_events(run_dir)
            status = project(events)
            created_at = datetime.fromisoformat(events[0]["occurred_at"])
            if created_at.tzinfo is None:
                raise ValueError("creation timestamp has no timezone")
            runs.append((created_at, {
                "run_id": status["run_id"], "goal": status["goal"],
                "state": status["state"], "directory": str(run_dir.resolve()),
            }))
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, AttributeError) as exc:
            print(f"Skipping run {run_dir}: {exc}", file=sys.stderr)
    runs.sort(key=lambda item: (item[0], item[1]["directory"]), reverse=True)
    return [summary for _, summary in runs]


def stop_process(process: subprocess.Popen) -> None:
    # A synchronous step owns its process group, including any surviving children.
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
    process.wait()


def execute_step(run_dir: Path, workspace: Path, step: str, argv: list[str], timeout: float, env: dict | None = None, *, stdin_text: str | None = None) -> str:
    started = time.monotonic()
    process = None
    environment = dict(os.environ if env is None else env)
    environment["PWD"] = str(workspace.resolve())
    detail = {"step": step, "argv": argv, "stdout": f"{step}.stdout.log", "stderr": f"{step}.stderr.log"}
    state, returncode, error = "failed", None, None
    with open_private(run_dir / detail["stdout"], "wb") as stdout, open_private(run_dir / detail["stderr"], "wb") as stderr:
        try:
            process = processes.spawn(
                argv, cwd=workspace, stdout=stdout, stderr=stderr, env=environment,
                stdin_text=stdin_text, ownership_path=run_dir / f"{step}-ownership.json",
            )
            record(run_dir, "step.started", {**detail, "pid": process.pid})
            returncode = process.wait(timeout=timeout)
            state = "passed" if returncode == 0 else "failed"
        except subprocess.TimeoutExpired:
            state, error = "timed_out", f"step exceeded {timeout:g} seconds"
        except KeyboardInterrupt:
            state, error = "interrupted", "operator interrupted execution"
        except OSError as exc:
            error = str(exc)
        finally:
            if process is not None:
                stop_process(process)
                returncode = process.returncode
            stdout.flush()
            stderr.flush()
            os.fsync(stdout.fileno())
            os.fsync(stderr.fileno())
    record(run_dir, "step.finished", {
        **detail, "state": state, "returncode": returncode, "error": error,
        "duration_seconds": round(time.monotonic() - started, 3),
    })
    return state


def create_run(plan: dict, workspace: Path, runs_dir: Path, run_id: str | None = None) -> Path:
    if run_id is not None and (not isinstance(run_id, str) or len(run_id) != 32 or any(
        char not in "0123456789abcdefABCDEF" for char in run_id
    )):
        raise ValueError("run_id must be a 32-character hexadecimal UUID")
    workspace = workspace.resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError("workspace must be a directory")
    ensure_private_directory(runs_dir)
    runs_dir = runs_dir.resolve()
    run_dir = runs_dir / (run_id if run_id is not None else uuid.uuid4().hex)
    run_dir.mkdir(mode=0o700)
    ensure_private_directory(run_dir)
    with closing(sqlite3.connect(create_private_sqlite(run_dir / "events.sqlite3"))) as connection:
        with connection:
            connection.execute(
                "CREATE TABLE events (sequence INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL, "
                "kind TEXT NOT NULL, data TEXT NOT NULL)"
            )
            append_event(connection, "run.created", {
                "version": 1, "run_id": run_dir.name, "workspace": str(workspace), "plan": plan,
            })
    print(f"Run: {run_dir}", flush=True)
    return run_dir


def run_plan(plan: dict, workspace: Path, runs_dir: Path) -> tuple[Path, dict]:
    plan = validate_plan(plan)
    workspace = workspace.resolve(strict=True)
    run_dir = create_run(plan, workspace, runs_dir)
    state = "unfinished"
    try:
        for step in ("work", "verify"):
            print(f"{step}: running (logs in {run_dir})", flush=True)
            state = execute_step(run_dir, workspace, step, plan[step], plan["timeout_seconds"])
            if state != "passed":
                break
        else:
            state = "awaiting_review"
    except KeyboardInterrupt:
        state = "interrupted"
    except (OSError, sqlite3.Error) as exc:
        state = "failed"
        record(run_dir, "run.error", {"error": str(exc)})
    record(run_dir, "run.finished", {"state": state})
    return run_dir, project(read_events(run_dir))


def review_run(run_dir: Path, verdict: str, reviewer: str, evidence: Path) -> dict:
    if verdict not in ("accept", "reject") or not reviewer.strip():
        raise ValueError("review requires accept/reject and a named reviewer")
    text = evidence.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("review evidence must not be empty")
    # Store the review itself, not just a pathname that can disappear after a restart.
    data = {
        "verdict": verdict, "reviewer": reviewer, "evidence": text,
        "evidence_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    uri = (run_dir / "events.sqlite3").resolve().as_uri() + "?mode=rw"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            last = connection.execute("SELECT data FROM events WHERE kind = 'run.finished' ORDER BY sequence DESC LIMIT 1").fetchone()
            reviewed = connection.execute("SELECT 1 FROM events WHERE kind = 'review.recorded' LIMIT 1").fetchone()
            if last is None or json.loads(last[0])["state"] != "awaiting_review" or reviewed:
                raise ValueError("only an awaiting_review run can receive a review")
            append_event(connection, "review.recorded", data)
    return project(read_events(run_dir))


def render_status(run_dir: Path, status: dict, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(status, indent=2, sort_keys=True))
        return
    print(f"Goal: {status['goal']}\nState: {status['state']}\nRun: {run_dir.resolve()}")
    if status["goal_ref"]:
        print(f"Goal reference: {status['goal_ref']}")
    if status.get("telos"):
        print(f"Telos: {status['telos']['chain_id']} / {status['telos']['subgoal_id']}")
    if status.get("telos_error"):
        print(f"Telos result not synchronized: {status['telos_error']}")
    for step, detail in status["steps"].items():
        state = detail.get("state", "started; no finish recorded")
        print(f"  {step}: {state} (exit {detail.get('returncode', 'unknown')})")
        if detail.get("error"):
            print(f"    {detail['error']}")
        print(f"    stdout: {run_dir / detail['stdout']}\n    stderr: {run_dir / detail['stderr']}")
    if status["review"]:
        print(f"Reviewer: {status['review']['reviewer']}")
    elif status["state"] == "awaiting_review":
        print("Awaiting independent review; inspect the recorded verification coverage. This is not acceptance.")
    elif status["state"] == "unfinished":
        print("No terminal event: work may still be running or may have been interrupted. Nothing is retried.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="execute work then verification from a plan")
    run.add_argument("plan", type=Path)
    run.add_argument("--workspace", type=Path, default=Path.cwd())
    run.add_argument("--runs-dir", type=Path, help="default: WORKSPACE/.runtime/runs")
    listing = commands.add_parser("list", help="discover recorded runs, newest first")
    listing.add_argument("--runs-dir", type=Path, required=True)
    listing.add_argument("--json", action="store_true")
    status = commands.add_parser("status", help="show durable last-observed state and log paths")
    status.add_argument("run_dir", type=Path)
    status.add_argument("--json", action="store_true")
    events = commands.add_parser("events", help="export actual events as JSON Lines")
    events.add_argument("run_dir", type=Path)
    review = commands.add_parser("review", help="record a separately obtained review")
    review.add_argument("run_dir", type=Path)
    review.add_argument("--verdict", choices=("accept", "reject"), required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            def interrupt(signum, frame):
                raise KeyboardInterrupt
            previous = signal.signal(signal.SIGTERM, interrupt)
            try:
                run_dir, result = run_plan(
                    json.loads(args.plan.read_text(encoding="utf-8")), args.workspace,
                    args.runs_dir or args.workspace / ".runtime/runs",
                )
            finally:
                signal.signal(signal.SIGTERM, previous)
            render_status(run_dir, result)
            return 0 if result["state"] == "awaiting_review" else 1
        if args.command == "list":
            runs = list_runs(args.runs_dir)
            if args.json:
                print(json.dumps(runs, indent=2, sort_keys=True))
            else:
                for run in runs:
                    print(f"ID: {run['run_id']}\nGoal: {run['goal']}\nState: {run['state']}\nRun: {run['directory']}\n")
        elif args.command == "events":
            for event in read_events(args.run_dir):
                print(json.dumps(event, sort_keys=True))
        elif args.command == "review":
            render_status(args.run_dir, review_run(args.run_dir, args.verdict, args.reviewer, args.evidence))
        else:
            render_status(args.run_dir, project(read_events(args.run_dir)), args.json)
        return 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"noetic run failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
