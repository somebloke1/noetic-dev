"""Actual native many-judgment practical question and three distinct courses."""
from scripts import noetic_opermem as bridge
from tests.programs.opermem_judgment_fixture import checked_warrant, proposed_judgment


COURSES = [
    ("Inspect the current repository bindings directly.", "Trace: direct inspection compares each current binding with its actual source."),
    ("Reconstruct bindings from retained command receipts.", "Trace: retained receipt bytes can reconstruct the original accepted identifiers."),
    ("Compare independently regenerated protocol manifests.", "Trace: regeneration exposes mismatches between retained and present protocol material."),
]


def practical_question(binary, store, transcripts, root, *, key="practical-fixture"):
    root.mkdir(parents=True, exist_ok=True)
    warrant, conditions = checked_warrant(binary, store, transcripts, root, count=2, key=key)
    judgments = []
    for i in range(2):
        response, _ = bridge.submit(binary, store, transcripts, "judgment", None, proposed_judgment(),
            key + "judgment-" + str(i), warrant_id=warrant, condition_ids=conditions)
        judgments.append(next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "judgment"))
    judgments.sort()
    response, _ = bridge.submit(binary, store, transcripts, "practical-question", None,
        {"text": "Given both bounded judgments, how should retained bindings be investigated?"}, key + "question",
        judgment_ids=judgments)
    question = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "practical-question")
    return question, judgments


def courses(binary, store, transcripts, question, *, count=3, traces=True, key="courses"):
    options, insights = [], []
    for index, (course, insight) in enumerate(COURSES[:count]):
        response, _ = bridge.submit(binary, store, transcripts, "practical-inquiry", None,
            {"text": course}, key + "option-" + str(index), practical_question_id=question)
        option = next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "option")
        options.append(option)
        if traces:
            response, _ = bridge.submit(binary, store, transcripts, "practical-insight", None,
                {"text": insight}, key + "insight-" + str(index), practical_question_id=question, option_id=option)
            insights.append(next(x["id"] for x in response["payload"]["outputs"] if x["kind"] == "unverified-practical-insight-trace"))
    return sorted(options), sorted(insights)


def deliberation():
    return {"criteria": ["All selected courses address retained bindings.", "Each course has an actual current native insight trace."],
            "trade_offs": ["Direct inspection costs source-reading time.", "Receipt reconstruction depends on retained bytes."],
            "objections_and_responses": ["Objection: regeneration can drift. Response: compare exact retained and current manifests."],
            "value_scale": "Prefer reproducible understanding and explicit uncertainty over apparent completeness."}
