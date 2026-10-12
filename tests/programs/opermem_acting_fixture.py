"""Actual external command evidence and native prospective plan, kept distinct."""
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import sys

from scripts import noetic_opermem as bridge, noetic_run as runtime, noetic_act_observation as evidence
from scripts import noetic_opermem_acting as acting
from tests.programs.opermem_decision_fixture import evaluation, decision

ACTION = "Write the disposable comparison result."


def native_plan(binary, store, transcripts, root):
    evaluated, question, basis, options, _ = evaluation(binary, store, transcripts, root / "checking")
    chosen, _, _ = decision(binary, store, transcripts, evaluated, basis, options)
    response, _ = bridge.submit(binary, store, transcripts, "planning", None,
        {"steps": [{"position": 1, "action": ACTION, "condition": "The external host independently authorizes this disposable task."},
                   {"position": 2, "action": "Retain actual comparison evidence."}]}, "acting-plan",
        decision_id=chosen, judgment_basis_ids=basis)
    plan = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "plan")
    planning, _ = bridge.retrieve(binary, store, transcripts, bridge.purpose_for("planning", None, decision_id=chosen, judgment_basis_ids=basis))
    steps = [x for x in planning["supplied_whole_residues"] if x["kind"] == "plan-step"]
    selected = next(x["residue_id"]["id"] for x in steps if x["retrieval_voice"]["position"] == 1)
    return plan, selected, chosen, basis, question, options


def external_work(root, *, failed=False, verify_failed=False, launch_failed=False):
    workspace = root / "external-workspace"
    workspace.mkdir()
    code = "from pathlib import Path; import sys; p=Path('result.txt');p.write_text('failed comparison' if " + repr(failed) + " else 'comparison retained');print(p.read_text());print('retained diagnostic',file=sys.stderr);sys.exit(" + str(7 if failed else 0) + ")"
    argv = [str(root / "absent-executable")] if launch_failed else [sys.executable, "-c", code]
    verification = [sys.executable, "-c", "import sys;sys.exit(" + str(9 if verify_failed else 0) + ")"]
    with redirect_stdout(io.StringIO()):
        run = runtime.create_run({"goal": "Host-authorized disposable comparison", "work": argv, "verify": verification}, workspace, root / "external-runs")
        state = runtime.execute_step(run, workspace, "work", argv, 10, env={k:v for k,v in os.environ.items() if k != "USER_PROVIDED_PASSWORD"})
        if state == "passed":
            state = runtime.execute_step(run, workspace, "verify", verification, 10, env={k:v for k,v in os.environ.items() if k != "USER_PROVIDED_PASSWORD"})
        runtime.record(run, "run.finished", {"state": "awaiting_review" if state == "passed" else state})
    return run


def prose(*, failed=False, verify_failed=False):
    if failed:
        return {"observed_act": "  Attempted the disposable comparison.\n", "outcome": "Work wrote failed comparison and exited7.\n", "deviation": "  Work attempted the comparison but failed; the plan does not prove execution dispatch.\n"}
    return {"observed_act": ACTION, "outcome": "Work wrote comparison retained and exited0; verification exited" + ("9 (failed)." if verify_failed else "0.")}


def archived(root, source, value):
    archive = root / "external-evidence"
    manifest = evidence.capture(source, archive)
    sha = evidence.digest((archive / "manifest.json").read_bytes())
    return archive, sha, acting.bind(value, archive, sha), manifest
