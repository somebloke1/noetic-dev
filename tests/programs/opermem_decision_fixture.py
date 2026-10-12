"""Disposable actual native evaluation, accountable choice and conditioned steps."""
from scripts import noetic_opermem as bridge
from tests.programs.opermem_practical_fixture import practical_question, courses, deliberation


def evaluation(binary, store, transcripts, root, *, key="decision-fixture"):
    question, judgments = practical_question(binary, store, transcripts, root, key=key)
    options, traces = courses(binary, store, transcripts, question, key=key + "courses")
    response, _ = bridge.submit(binary, store, transcripts, "deliberation", None, deliberation(), key + "evaluation",
        practical_question_id=question, option_ids=options)
    identity = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "evaluation")
    return identity, question, judgments, options, traces


def choice(options, *, abeyant=False):
    return {"selected_option_id": options[0],
            "rejected": [{"option_id": option, "reason": "Defer this candidate while the selected comparison is investigated."}
                         for option in options[1:]],
            "intention": {"kind": "abeyant", "trigger": "Owner supplies the retained manifest."} if abeyant else {"kind": "active"}}


def steps():
    return {"steps": [{"position": 1, "action": "Read retained binding records.",
                       "condition": "The host has authorized reading these records."},
                      {"position": 2, "action": "Compare current and retained identifiers."},
                      {"position": 3, "action": "Retain the comparison and unresolved differences.",
                       "condition": "The comparison is available for host review."}]}


def decision(binary, store, transcripts, evaluation_id, basis, options, *, key="decision", abeyant=False):
    response, _ = bridge.submit(binary, store, transcripts, "decision", None, choice(options, abeyant=abeyant), key,
                               evaluation_id=evaluation_id, judgment_basis_ids=basis)
    decision_id = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "decision")
    intention_id = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "intention")
    return decision_id, intention_id, response
