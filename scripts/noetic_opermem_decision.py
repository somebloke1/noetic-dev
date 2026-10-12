"""Decision and planning composition over explicit native admissions."""
from __future__ import annotations

if __package__:
    from scripts import noetic_opermem_judgment as native, noetic_opermem_practical as packets
else:
    import noetic_opermem_judgment as native
    import noetic_opermem_practical as packets

OPERATIONS = ("decision", "planning")
# Frozen operation-host CanonicalLimits; Rust still validates every command.
MAX_TEXT_BYTES = 8192
MAX_ITEMS = 128


def text(value):
    if (not isinstance(value, str) or not value or value != value.strip()
            or len(value.encode("utf-8")) > MAX_TEXT_BYTES):
        raise ValueError("native scalar text must be nonempty, trimmed and at most 8192 UTF-8 bytes")


def contribution(value, operation):
    fields = {"selected_option_id", "rejected", "intention"} if operation == "decision" else {"steps"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("incorrect decision/planning contribution fields")
    if operation == "decision":
        native.u64(value["selected_option_id"], "selected option ID")
        rejected = value["rejected"]
        if not isinstance(rejected, list) or not rejected or len(rejected) > MAX_ITEMS:
            raise ValueError("rejected requires bounded complete native rejected option reasons")
        for item in rejected:
            if not isinstance(item, dict) or set(item) != {"option_id", "reason"}:
                raise ValueError("incorrect rejected option fields")
            native.u64(item["option_id"], "rejected option ID")
            text(item["reason"])
        native.ids([item["option_id"] for item in rejected], "rejected option IDs")
        if value["selected_option_id"] in [item["option_id"] for item in rejected]:
            raise ValueError("selected option cannot also be rejected")
        intention = value["intention"]
        if not isinstance(intention, dict) or intention.get("kind") not in ("active", "abeyant"):
            raise ValueError("intention must be active or abeyant")
        expected = {"kind", "trigger"} if intention["kind"] == "abeyant" else {"kind"}
        if set(intention) != expected:
            raise ValueError("incorrect issued intention fields")
        if intention["kind"] == "abeyant":
            text(intention["trigger"])
    else:
        steps = value["steps"]
        if not isinstance(steps, list) or not steps or len(steps) > MAX_ITEMS:
            raise ValueError("steps must be a nonempty bounded ordered array")
        for position, step in enumerate(steps, 1):
            if (not isinstance(step, dict) or set(step) not in ({"position", "action"}, {"position", "action", "condition"})
                    or type(step["position"]) is not int or step["position"] != position):
                raise ValueError("plan positions must be contiguous positive u16 values starting at 1")
            text(step["action"])
            if "condition" in step:
                text(step["condition"])
    return value


def compose_context(packets_):
    cut, _ = packets.packet_material(packets_)
    return {"context_composition_version": "noetic-decision-context/v1", "operation": "decision",
            "pinned_canonical_cut": cut, "native_context_packets": packets_}


def lookup(context):
    if "native_context_packets" not in context:
        return context
    cut, whole = packets.packet_material(context["native_context_packets"])
    if cut != context["pinned_canonical_cut"]:
        raise ValueError("native decision envelope cut mismatch")
    return {"pinned_canonical_cut": cut, "supplied_whole_residues": whole}


def residue(context, kind, identity):
    return native.residue(lookup(context), kind, identity)


def basis_material(context, basis):
    native.ids(basis, "judgment basis IDs")
    return [residue(context, "judgment", identity) for identity in basis]


def decision_material(context, evaluation_id, basis, predecessor=None, predecessor_evaluation=None):
    evaluation = residue(context, "evaluation", evaluation_id)
    voice = evaluation["retrieval_voice"]
    question_id = voice["practical_question_id"]
    question = residue(context, "practical-question", question_id)
    if question["retrieval_voice"]["judgment_ids"] != basis:
        raise ValueError("decision requires the entire retained native judgment basis")
    options = [pair["option_id"] for pair in voice["options"]]
    native.ids(options, "evaluated option IDs")
    if (sorted(native.related(evaluation, "evaluates", "from", "option")) != options
            or sorted(native.related(question, "option-for", "to", "option")) != options):
        raise ValueError("decision requires the entire current evaluated native option set")
    objects = basis_material(context, basis) + [evaluation]
    for identity in options:
        option = residue(context, "option", identity)
        if option["retrieval_voice"]["practical_question_id"] != question_id:
            raise ValueError("evaluated option belongs to a different question")
        objects.append(option)
    if predecessor is not None:
        old = residue(context, "decision", predecessor)
        old_voice = old["retrieval_voice"]
        if (old_voice["lifecycle"] not in ("live", "flagged")
                or old_voice["evaluation_id"] == evaluation_id
                or old_voice["judgment_basis_ids"] != basis):
            raise ValueError("supersession requires a live eligible predecessor from a different evaluation with the same basis")
        if predecessor_evaluation is not None and old_voice["evaluation_id"] != predecessor_evaluation:
            raise ValueError("predecessor evaluation anchor differs from retained native decision")
        # The selected native supplement admits and binds the predecessor's own question.
        supplement = context["native_context_packets"][1]
        if supplement["operation"] == "decision":
            old_evaluation = native.residue(supplement, "evaluation", old_voice["evaluation_id"])
            if old_evaluation["retrieval_voice"]["practical_question_id"] != question_id:
                raise ValueError("predecessor belongs to a different practical question")
        objects.append(old)
    return objects, options


def planning_material(context, decision_id, basis):
    decision = residue(context, "decision", decision_id)
    voice = decision["retrieval_voice"]
    if voice["lifecycle"] != "live" or voice["judgment_basis_ids"] != basis:
        raise ValueError("planning requires a live decision and its entire retained judgment basis")
    if sorted(native.related(decision, "grounded-in-judgment", "from", "judgment")) != basis:
        raise ValueError("decision judgment ancestry mismatch")
    intentions = native.related(decision, "issues-intention", "from", "intention")
    if len(intentions) != 1:
        raise ValueError("decision must issue exactly one native intention")
    intention = residue(context, "intention", intentions[0])
    if (intention["retrieval_voice"]["decision_id"] != decision_id
            or intention["retrieval_voice"]["state"] not in ("active", "surfaced")):
        raise ValueError("planning requires an active or surfaced native intention; abeyant is inapplicable")
    return basis_material(context, basis) + [decision, intention], intentions[0]


def material(context, operation, *, evaluation_id=None, decision_id=None, judgment_basis_ids=None,
             supersedes_decision_id=None, predecessor_evaluation_id=None):
    if context["operation"] != operation or operation not in OPERATIONS:
        raise ValueError("applicable native decision/planning context required")
    if operation == "decision":
        return decision_material(context, evaluation_id, judgment_basis_ids,
                                 supersedes_decision_id, predecessor_evaluation_id)
    return planning_material(context, decision_id, judgment_basis_ids)


def command_for(context, operation, value, key, **anchors):
    contribution(value, operation)
    objects, selected_material = material(context, operation, **anchors)
    body = {"judgment_basis_ids": anchors["judgment_basis_ids"], **value}
    if operation == "decision":
        selected = value["selected_option_id"]
        if selected not in selected_material or [r["option_id"] for r in value["rejected"]] != [i for i in selected_material if i != selected]:
            raise ValueError("choice and rejected reasons must account for exactly the entire evaluated option set")
        body["evaluation_id"] = anchors["evaluation_id"]
        if anchors.get("supersedes_decision_id") is not None:
            body["supersedes_decision_id"] = anchors["supersedes_decision_id"]
    else:
        body.update(decision_id=anchors["decision_id"], intention_id=selected_material)
    order = {"intention": 0, "judgment": 1, "decision": 2, "evaluation": 3, "option": 4}
    objects.sort(key=lambda item: (order[item["residue_id"]["kind"]], item["residue_id"]["id"]))
    expected = [{**item["residue_id"], "version": item["object_version"]} for item in objects]
    return {"decision": "decide", "planning": "plan"}[operation], {
        "body": body, "command_version": 1, "expected_object_versions": expected, "idempotency_key": key}
