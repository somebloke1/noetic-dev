"""Actual disposable native warrant and host-captured checking fixture."""
from scripts import noetic_opermem as bridge
from scripts import noetic_opermem_checking as checking
from tests.programs import test_noetic_opermem_checking as fixtures


def checked_warrant(binary, store, transcripts, root, *, count=5, key="judgment-fixture",
                    assertion="assert 2 + 2 == 4"):
    parent = None
    for operation, contribution, role in [
        ("question", {"text": "How do all retained predicates support this claim?", "question_kind": "how"}, "question"),
        ("insight", {"text": "Trace: predicates can be retained separately."}, "unverified insight trace"),
        ("formulation", {"text": "Hypothesis: all selected exact predicates hold."}, "versioned formulation/hypothesis"),
        ("reflection", {"text": "Do all exact predicates hold?"}, "reflection question")]:
        response, _ = bridge.submit(binary, store, transcripts, operation, parent, contribution, key + operation)
        parent = next(item["id"] for item in response["payload"]["outputs"] if item["role"] == role)
        if operation == "formulation":
            formulation = parent
    response, _ = bridge.submit(binary, store, transcripts, "conditional-structure", parent,
        {"conditions": [f"Predicate {i}: exact bounded assertion" for i in range(count)]},
        key + "warrant", formulation_id=formulation)
    warrant = next(item["id"] for item in response["payload"]["outputs"] if item["kind"] == "warrant")
    conditions = sorted(item["id"] for item in response["payload"]["outputs"] if item["kind"] == "warrant-condition")
    fixture = fixtures.CheckingCaptureTests()
    fixture.root = root
    fixture.counter = 0
    for identity in conditions:
        fixture.context_ids = identity, warrant
        fixture.context, _ = bridge.retrieve(binary, store, transcripts,
            bridge.purpose_for("checking", identity, warrant_id=warrant))
        directory, _ = fixture.capture(fixture.specification(assertion))
        manifest_hash = checking.digest((directory / "manifest.json").read_bytes())
        contribution = checking.contribution(directory, fixture.context, identity, warrant, manifest_hash)
        bridge.submit(binary, store, transcripts, "checking", identity, contribution,
            key + "checking-" + str(identity), fixture.context, warrant_id=warrant,
            checking_evidence=directory, checking_manifest_sha256=manifest_hash)
    return warrant, conditions


def proposed_judgment(kind="yea"):
    polarity = {"kind": kind}
    if kind == "perchance":
        polarity["confidence_basis_points"] = 5000
    return {"polarity": polarity, "defeat_conditions": ["A changed predicate defeats this bounded judgment."],
            "rationale": "The entire native snapshot contains actual bounded predicate results; scope is limited to those assertions."}
