"""Native practical inquiry, unverified insight and complete deliberation composition."""
from __future__ import annotations

if __package__:
    from scripts import noetic_opermem_judgment as native
else:
    import noetic_opermem_judgment as native


OPERATIONS = ("practical-inquiry", "practical-insight", "deliberation")


def packet_material(packets):
    cut = packets[0]["pinned_canonical_cut"]
    merged = {}
    bindings = ("object_version", "liveness", "standing", "retrieval_voice", "content",
                "content_sha256", "pinned_cut_binding", "ancestry")
    for packet in packets:
        if packet["pinned_canonical_cut"] != cut:
            raise ValueError("native practical context packets must share the exact cut")
        for item in packet["supplied_whole_residues"]:
            identity = item["residue_id"]
            key = identity["kind"], identity["id"]
            if key in merged and any(merged[key][field] != item[field] for field in bindings):
                raise ValueError("native practical context residue binding mismatch")
            merged.setdefault(key, item)
    return cut, list(merged.values())


def compose_context(operation, packets):
    cut, _ = packet_material(packets)
    return {"context_composition_version": "noetic-practical-context/v1", "operation": operation,
            "pinned_canonical_cut": cut, "native_context_packets": packets}


def residue(context, kind, identity):
    if context["operation"] == "practical-inquiry":
        return native.residue(context, kind, identity)
    cut, whole = packet_material(context["native_context_packets"])
    if cut != context["pinned_canonical_cut"]:
        raise ValueError("native practical envelope cut mismatch")
    return native.residue({"pinned_canonical_cut": cut, "supplied_whole_residues": whole}, kind, identity)


def contribution(value, operation):
    fields = {"criteria", "trade_offs", "objections_and_responses", "value_scale"} if operation == "deliberation" else {"text"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("incorrect practical contribution fields")
    text = value["value_scale"] if operation == "deliberation" else value["text"]
    if not isinstance(text, str) or not text or text != text.strip():
        raise ValueError("practical contribution text must be nonempty and trimmed")
    if operation == "deliberation":
        for name in ("criteria", "trade_offs", "objections_and_responses"):
            values = value[name]
            if (not isinstance(values, list) or not values
                    or any(not isinstance(v, str) or not v or v != v.strip() for v in values)
                    or any(a >= b for a, b in zip(values, values[1:]))):
                raise ValueError(f"{name} must be nonempty trimmed strings in strictly sorted unique order")
    return value


def question_material(context, identity):
    question = residue(context, "practical-question", identity)
    if question["retrieval_voice"]["state"] != "active":
        raise ValueError("active native practical question required")
    judgments = native.ids(question["retrieval_voice"]["judgment_ids"], "retained judgment IDs")
    if sorted(native.related(question, "grounds-practical-question", "to", "judgment")) != judgments:
        raise ValueError("whole practical question judgment ancestry mismatch")
    for judgment in judgments:
        residue(context, "judgment", judgment)
    return question


def option_material(context, question_id, option_id):
    option = residue(context, "option", option_id)
    if (option["retrieval_voice"]["practical_question_id"] != question_id
            or native.related(option, "option-for", "from", "practical-question") != [question_id]):
        raise ValueError("option must belong to the explicit practical question")
    return option


def material(context, operation, question_id, *, option_id=None, option_ids=None):
    if context["operation"] != operation or operation not in OPERATIONS:
        raise ValueError("applicable native practical context required")
    question = question_material(context, question_id)
    if operation == "practical-inquiry":
        return [question], None
    if operation == "practical-insight":
        return [question, option_material(context, question_id, option_id)], None
    native.ids(option_ids, "option IDs")
    if len(option_ids) < 2:
        raise ValueError("deliberation requires at least two native options")
    entire = sorted(native.related(question, "option-for", "to", "option"))
    if entire != option_ids:
        raise ValueError("deliberation option IDs must equal the entire current native question option set")
    objects, pairs = [question], []
    for identity in entire:
        option = option_material(context, question_id, identity)
        _, whole = packet_material(context["native_context_packets"])
        traces = [item for item in whole
                  if item["residue_id"]["kind"] == "unverified-practical-insight-trace"
                  and item["liveness"] == "current"
                  and item["retrieval_voice"]["practical_question_id"] == question_id
                  and item["retrieval_voice"]["option_id"] == identity]
        if len(traces) != 1:
            raise ValueError("deliberation requires one unique current native unverified trace per option")
        trace = residue(context, "unverified-practical-insight-trace", traces[0]["residue_id"]["id"])
        if (native.related(trace, "intelligibility-for", "from", "option") != [identity]
                or native.related(trace, "in-context-of", "from", "practical-question") != [question_id]):
            raise ValueError("whole practical trace ancestry mismatch")
        pairs.append({"option_id": identity, "insight_id": trace["residue_id"]["id"]})
        objects.extend((option, trace))
    return objects, pairs


def command_for(context, operation, value, key, *, practical_question_id,
                option_id=None, option_ids=None):
    contribution(value, operation)
    objects, pairs = material(context, operation, practical_question_id, option_id=option_id, option_ids=option_ids)
    body = {"practical_question_id": practical_question_id, **value}
    if operation == "practical-insight":
        body["option_id"] = option_id
    if operation == "deliberation":
        body["options"] = pairs
    order = {"option": 0, "practical-question": 1, "unverified-practical-insight-trace": 2}
    objects.sort(key=lambda item: (order[item["residue_id"]["kind"]], item["residue_id"]["id"]))
    expected = [{**item["residue_id"], "version": item["object_version"]} for item in objects]
    kind = {"practical-inquiry": "inquire-into-courses", "practical-insight": "grasp-possible-course",
            "deliberation": "deliberate"}[operation]
    return kind, {"body": body, "command_version": 1, "expected_object_versions": expected,
                  "idempotency_key": key}
