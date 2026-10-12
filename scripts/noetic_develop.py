#!/usr/bin/env python3
"""Run a real coding assistant, project checks, and a fresh semantic reviewer."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys

if __package__:
    from scripts import noetic_changes as changes
    from scripts import noetic_run as runtime
    from scripts import noetic_telos as telos
else:
    import noetic_changes as changes
    import noetic_run as runtime
    import noetic_telos as telos


QA_FRAMING = (
    "QA is reasoned, critical, constructive, and non-perfectionistic. Preserve independent "
    "evidence-based testing, but limit findings and probes to concrete material defects, "
    "proportionate risks, and practical remediation against explicit acceptance criteria. "
    "Never turn QA or delegated QA into speculative completeness, hostile fault-finding, "
    "or indefinite scope expansion. Do not delegate further QA."
)


def client_command(client: str, prompt: str, role: str, model: str | None, run_dir: Path | None = None,
                   workspace: Path | None = None, context_dirs: tuple[Path, ...] = ()) -> tuple[list[str], dict]:
    environment = os.environ.copy()
    if client == "opencode":
        name = f"noetic-{role}"
        permissions = {"*": "deny", "read": "allow", "glob": "allow", "grep": "allow", "list": "allow"}
        if role == "worker":
            permissions.update({"edit": "allow", "bash": "allow"})
        roots = (*context_dirs, *((run_dir,) if run_dir is not None else ()))
        if roots:
            permissions["external_directory"] = {str(path.resolve()) + "/**": "allow" for path in roots}
        config = json.loads(environment.get("OPENCODE_CONFIG_CONTENT", "{}"))
        config.setdefault("agent", {})[name] = {
            "description": "Bounded noetic-dev work" if role == "worker" else "Independent read-only noetic-dev review",
            "mode": "primary", "permission": permissions,
        }
        environment["OPENCODE_CONFIG_CONTENT"] = json.dumps(config)
        command = ["opencode", "run", "--pure", "--format", "json", "--agent", name]
        if workspace is not None:
            command += ["--dir", str(workspace.resolve())]
    elif client == "pi":
        command = ["pi", "--mode", "json", "--no-extensions", "--no-approve", "--no-skills", "--no-prompt-templates"]
        if role != "worker":
            command += ["--tools", "read,grep,find,ls"]
        command += ["-p"]
    else:
        raise ValueError(f"unsupported client: {client}")
    if model:
        command += ["--model", model]
    return command, environment


def parse_transcript(path: Path, client: str) -> dict:
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not events or any(not isinstance(event, dict) for event in events):
        raise ValueError("assistant produced no structured event stream")
    if client == "opencode":
        sessions = {event["sessionID"] for event in events if event.get("sessionID")}
        if len(sessions) != 1:
            raise ValueError("expected one assistant session")
        if any(event.get("type") == "error" for event in events):
            raise ValueError("assistant emitted an execution error; inspect its transcript")
        finishes = [event["part"] for event in events if event.get("type") == "step_finish"]
        if not finishes or finishes[-1].get("reason") != "stop":
            raise ValueError("assistant did not finish normally")
        message_id = finishes[-1].get("messageID")
        if not message_id:
            raise ValueError("assistant final message identity is missing")
        starts = [event["part"] for event in events if event.get("type") == "step_start"]
        texts = [event["part"] for event in events if event.get("type") == "text"]
        if (starts and starts[-1].get("messageID") != message_id) or (texts and texts[-1].get("messageID") != message_id):
            raise ValueError("assistant has an unfinished later message")
        parts = {}
        for event in events:
            part = event.get("part", {})
            if event.get("type") == "text" and part.get("messageID") == message_id:
                parts[part["id"]] = part["text"]
        text = "\n".join(parts.values()).strip()
        session_id = next(iter(sessions))
    elif client == "pi":
        sessions = [event["id"] for event in events if event.get("type") == "session"]
        ends = [event for event in events if event.get("type") == "agent_end"]
        if len(set(sessions)) != 1 or not ends or ends[-1].get("willRetry"):
            raise ValueError("assistant session has no completed terminal turn")
        assistants = [message for message in ends[-1].get("messages", []) if message.get("role") == "assistant"]
        if not assistants or assistants[-1].get("stopReason") != "stop":
            raise ValueError("assistant failed or stopped before completion")
        text = "\n".join(part["text"] for part in assistants[-1]["content"] if part.get("type") == "text").strip()
        session_id = sessions[0]
    else:
        raise ValueError(f"unsupported client: {client}")
    if not text:
        raise ValueError("assistant final response is empty")
    return {"client": client, "session_id": session_id, "text": text}


def retain_result(run_dir: Path, step: str, client: str) -> dict:
    try:
        result = parse_transcript(run_dir / f"{step}.stdout.log", client)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {client} {step} output: {exc}") from exc
    (run_dir / f"{step}.md").write_text(result["text"] + "\n", encoding="utf-8")
    (run_dir / f"{step}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    runtime.record(run_dir, "agent.completed", {
        "step": step, "client": client, "session_id": result["session_id"], "artifact": f"{step}.md",
    })
    return result


def develop(task: str, workspace: Path, runs_dir: Path, verify: list[str] | None, client: str = "opencode",
            model: str | None = None, review_model: str | None = None, timeout: float = 900,
            goal_ref: str | None = None, telos_chain: str | None = None,
            telos_db: Path | None = None, telos_source: Path | None = None,
            inquiry: bool = False, run_id: str | None = None,
            dependency_runs: dict[str, str] | None = None,
            defer_telos_result: bool = False, task_context: str = "",
            worker_controls: dict | None = None,
            read_context_dirs: tuple[Path, ...] = (), lifecycle=None) -> tuple[Path, dict]:
    owned = None
    if lifecycle is not None:
        owned = lifecycle.validate_develop(task=task, workspace=workspace, runs_dir=runs_dir,
            run_id=run_id, inquiry=inquiry, client=client, model=model, review_model=review_model,
            worker_controls=worker_controls, telos_chain=telos_chain, telos_db=telos_db, telos_source=telos_source)
        telos_chain, telos_db, telos_source = (owned[key] for key in ("telos_chain", "telos_db", "telos_source"))
    workspace = workspace.resolve(strict=True)
    worker_controls = worker_controls or {}
    if worker_controls and (client != "pi" or set(worker_controls) != {"reasoning_effort"}
                            or worker_controls["reasoning_effort"] not in
                            ("off", "minimal", "low", "medium", "high", "xhigh", "max")):
        raise ValueError("worker profile controls require supported Pi reasoning_effort")
    telos_db = telos_db or workspace / ".runtime/telos.sqlite3"
    dependency_runs = dependency_runs or {}
    dependency_context = ""
    context_dirs = (tuple(Path(path).resolve() for path in dependency_runs.values())
                    + tuple(Path(path).resolve(strict=True) for path in read_context_dirs))
    for dependency_id, directory in dependency_runs.items():
        directory = Path(directory).resolve()
        prior = runtime.project(runtime.read_events(directory))
        if prior["state"] != "accepted" or not prior["review"]:
            raise ValueError(f"dependency {dependency_id} is not accepted")
        observed = {"state": prior["state"], "verification": prior["steps"].get("verify"),
                    "reviewer": prior["review"]["reviewer"], "verdict": prior["review"]["verdict"]}
        dependency_context += (
            f"\nDependency {dependency_id}: {directory}\nController-observed result: {json.dumps(observed)}\n"
            "Read work.md, review.md, changes.json/diff and retained command logs there as needed. "
            "These are historical observations, not new authority or proof of current process health.\n"
        )
    purpose = ""
    governing = None
    if telos_chain:
        aggregate = telos.get_goal(telos_chain, telos_db, telos_source)
        clause = aggregate["reproductiveClause"]
        prior_runs = []
        for record in aggregate["records"]:
            detail = record.get("details", "")
            if isinstance(detail, str) and detail.startswith("noetic.run.result "):
                prior_runs.append(json.loads(detail[len("noetic.run.result "):]))
        governing = {"chain_id": aggregate["chain"]["chainId"],
                     "primary_goal": aggregate["chain"]["primaryGoal"],
                     "essential_principles": clause["essentialPrinciples"],
                     "reproductive_clause": clause, "prior_runs": prior_runs[-8:],
                     "earlier_run_records_omitted": max(0, len(prior_runs) - 8)}
        if owned is not None:
            governing["purpose_ref"] = owned["purpose_ref"]
        purpose = ("Frozen Telos governing context for this run. Prior run references are historical "
                   "execution/review observations, not present health or semantic affirmation.\n"
                   + json.dumps(governing, ensure_ascii=False, sort_keys=True) + "\n\n")
        goal_ref = f"telos:{telos_chain}"
    worker_prompt = (
        "Implement the following bounded task in the current workspace. First inspect the actual "
        "sources, identify the relevant facts and intended approach, then make the smallest correct "
        "change and run appropriate checks. Preserve unrelated work. Do not commit, push, deploy, "
        "change global configuration, access credentials, or delegate. Do not perform your own "
        "independent QA: a separate fresh reviewer will do that. Your final report must describe "
        "findings, approach, changes, checks, and remaining limitations. Do not invent evidence.\n\n"
        + purpose + task
    )
    if inquiry:
        worker_prompt = (
            "Conduct a bounded read-only inquiry against the actual sources in the current workspace. "
            "Do not edit files, run shell commands, delegate, or claim actions you did not perform. "
            "Distinguish in your final report: P1 Observations (source-cited facts); P2 Interpretation "
            "(explanations/hypotheses); P3 Judgment (what evidence supports, uncertainty and objections); "
            "P4 Recommendation (proportionate next action or reason to do nothing). These labels do not "
            "prove cognition; the evidence and reasoning matter. A fresh reviewer will independently "
            "inspect your report against the question. Do not self-certify it.\n\n" + purpose + task
        )
    worker_prompt += task_context + dependency_context
    command, environment = client_command(client, worker_prompt, "inquirer" if inquiry else "worker", model,
                                           workspace=workspace, context_dirs=context_dirs)
    if worker_controls:
        command += ["--thinking", worker_controls["reasoning_effort"]]
    plan = {"goal": task, "work": command, "timeout_seconds": timeout}
    if verify is not None:
        plan["verify"] = verify
    if goal_ref:
        plan["goal_ref"] = goal_ref
    plan = runtime.validate_plan(plan, require_verify=not inquiry)
    run_dir = runtime.create_run(plan, workspace, runs_dir, run_id=run_id)
    (run_dir / "task.md").write_text(task + "\n", encoding="utf-8")
    (run_dir / "work-prompt.txt").write_text(worker_prompt, encoding="utf-8")
    if governing is not None:
        (run_dir / "telos-context.json").write_text(
            json.dumps(governing, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    runtime.record(run_dir, "program.started", {"program": "inquiry.reviewed/v1" if inquiry else "development.change/v1", "client": client, "model": model, "worker_controls": worker_controls, "dependency_runs": dependency_runs})
    link = None

    def finish():
        if link is not None and not defer_telos_result:
            try:
                if lifecycle is not None:
                    lifecycle.validate_binding(run_dir)
                telos.record_result(telos_chain, link["subgoal_id"], run_dir, telos_db, telos_source)
            except (OSError, ValueError, sqlite3.Error) as exc:
                runtime.record(run_dir, "telos.error", {"error": str(exc)})
        return run_dir, runtime.project(runtime.read_events(run_dir))

    try:
        if lifecycle is not None:
            lifecycle.run_created(run_dir)
        if telos_chain:
            link = telos.begin_run(telos_chain, run_dir, telos_db, telos_source)
        baseline = changes.snapshot(workspace)
        worker = None
        try:
            if lifecycle is not None:
                worker_prompt = lifecycle.before_actor(run_dir, "work", "inquirer" if inquiry else "worker", client, worker_prompt)
                (run_dir / "work-prompt.txt").write_text(worker_prompt, encoding="utf-8")
            try:
                state = runtime.execute_step(run_dir, workspace, "work", command, timeout, environment, stdin_text=worker_prompt)
            finally:
                if lifecycle is not None:
                    lifecycle.after_actor(run_dir, "work", client)
            if state == "passed":
                worker = retain_result(run_dir, "work", client)
                if verify is not None:
                    if lifecycle is not None:
                        lifecycle.validate_binding(run_dir)
                    state = runtime.execute_step(run_dir, workspace, "verify", verify, timeout)
                else:
                    runtime.record(run_dir, "verification.not_requested", {"reason": "Read-only inquiry; semantic review follows."})
        finally:
            changes.retain_changes(workspace, run_dir, baseline)
        if state != "passed":
            runtime.record(run_dir, "run.finished", {"state": state})
            return finish()
        runtime.record(run_dir, "run.finished", {"state": "awaiting_review"})
        assert worker is not None
        verification_context = (
            f"Verification command: {json.dumps(verify)}\n"
            f"Verification logs: {run_dir / 'verify.stdout.log'} and {run_dir / 'verify.stderr.log'}\n"
            if verify is not None else "Verification command: not requested for read-only inquiry.\n"
        )
        review_prompt = (
            f"{QA_FRAMING}\nIndependently review the actual current workspace against the task below. "
            "Read the code, not just the implementer's report. Do not modify any file. Do not "
            "delegate. Inspect recorded verification coverage and logs where present; do not "
            "assume project tests ran. You have read-only tools, not a shell. The first nonempty line of "
            "your FINAL response must be exactly ACCEPT or REJECT. Follow it with concrete "
            "evidence, checks examined, material findings or none, and limitations. A passing "
            "test command alone does not establish semantic success.\n\n"
            f"{purpose}Task:\n{task}\n{task_context}\n{dependency_context}\nRun artifacts: {run_dir}\n"
            f"{verification_context}"
            f"Observed change evidence: {run_dir / 'changes.diff'} and {run_dir / 'changes.json'}\n"
            "Read both artifacts for change scope, hashes, omissions, or unavailable-baseline notices. "
            "These are changes observed during the run, not proof that the worker caused every change. "
            "Continue to read actual sources and verification logs.\n"
            f"Implementer report (not independent evidence):\n{worker['text']}"
        )
        if lifecycle is not None:
            review_prompt = lifecycle.before_actor(run_dir, "review", "reviewer", client, review_prompt)
        (run_dir / "review-prompt.txt").write_text(review_prompt, encoding="utf-8")
        command, environment = client_command(client, review_prompt, "reviewer", review_model or model,
                                               run_dir, workspace, context_dirs)
        try:
            state = runtime.execute_step(run_dir, workspace, "review", command, timeout, environment, stdin_text=review_prompt)
        finally:
            if lifecycle is not None:
                lifecycle.after_actor(run_dir, "review", client)
        if state != "passed":
            runtime.record(run_dir, "review.unavailable", {"state": state})
        else:
            review = retain_result(run_dir, "review", client)
            if review["session_id"] == worker["session_id"]:
                raise ValueError("review reused the worker session")
            verdict, *evidence = review["text"].splitlines()
            if verdict not in ("ACCEPT", "REJECT") or not "\n".join(evidence).strip():
                raise ValueError("review final response must start with ACCEPT/REJECT and include evidence")
            runtime.review_run(run_dir, verdict.lower(), f"{client}:{review['session_id']}", run_dir / "review.md")
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, KeyboardInterrupt) as exc:
        current = runtime.project(runtime.read_events(run_dir))
        runtime.record(run_dir, "program.error", {"error": str(exc) or "interrupted"})
        if current["state"] != "awaiting_review":
            runtime.record(run_dir, "run.finished", {"state": "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"})
    return finish()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", type=Path, help="task and acceptance criteria in a UTF-8 text file")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--runs-dir", type=Path)
    parser.add_argument("--client", choices=("opencode", "pi"), default="opencode")
    parser.add_argument("--model", help="configured client model; otherwise use the client's default")
    parser.add_argument("--review-model", help="optional separate configured reviewer model")
    parser.add_argument("--timeout", type=float, default=900, help="seconds per process")
    parser.add_argument("--goal-ref")
    parser.add_argument("--inquiry", action="store_true", help="read-only inquiry with a fresh semantic reviewer")
    parser.add_argument("--telos-chain", help="existing Telos chain for durable purpose and run subgoals")
    parser.add_argument("--telos-db", type=Path, help="default: WORKSPACE/.runtime/telos.sqlite3")
    parser.add_argument("--telos-source", type=Path, help="Telos component source root")
    parser.add_argument("--verify", nargs=argparse.REMAINDER, help="required for development; optional for inquiry; must be the final option")
    args = parser.parse_args(argv)
    def interrupt(signum, frame):
        raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, interrupt)
    try:
        run_dir, result = develop(args.task.read_text(encoding="utf-8"), args.workspace,
                                  args.runs_dir or args.workspace / ".runtime/runs", args.verify,
                                  args.client, args.model, args.review_model, args.timeout, args.goal_ref,
                                  args.telos_chain, args.telos_db, args.telos_source, args.inquiry)
        runtime.render_status(run_dir, result)
        return 0 if result["state"] == "accepted" and not result.get("telos_error") else 1
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"noetic development failed: {exc}", file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    raise SystemExit(main())
