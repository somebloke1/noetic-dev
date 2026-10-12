"""Compose native judgment/practical-question commands from whole typed context."""
from __future__ import annotations

import hashlib
import json


def u64(value, label):
    if type(value) is not int or not 0 < value < 2**64:
        raise ValueError(f"{label} must be a positive u64")
    return value


def ids(values, label):
    if not isinstance(values, list) or not values:
        raise ValueError(f"{label} requires a nonempty complete ID set")
    for value in values:
        u64(value, label)
    if any(a >= b for a, b in zip(values, values[1:])):
        raise ValueError(f"{label} must be in strictly sorted unique native ID order")
    return values


def validate_contribution(value):
    if not isinstance(value, dict) or set(value) != {"polarity", "defeat_conditions", "rationale"}:
        raise ValueError("judgment contribution requires polarity, defeat_conditions and rationale")
    polarity = value["polarity"]
    if not isinstance(polarity, dict) or polarity.get("kind") not in ("yea", "nay", "perchance"):
        raise ValueError("judgment polarity must be yea, nay or perchance")
    fields = {"kind", "confidence_basis_points"} if polarity["kind"] == "perchance" else {"kind"}
    if set(polarity) != fields:
        raise ValueError("incorrect judgment polarity fields")
    if polarity["kind"] == "perchance" and (type(polarity["confidence_basis_points"]) is not int
            or not 0 <= polarity["confidence_basis_points"] <= 10000):
        raise ValueError("perchance confidence_basis_points must be an integer from 0 through 10000")
    conditions = value["defeat_conditions"]
    if (not isinstance(conditions, list) or not conditions
            or any(not isinstance(text, str) or not text or text != text.strip() for text in conditions)
            or any(a >= b for a, b in zip(conditions, conditions[1:]))):
        raise ValueError("defeat_conditions must be nonempty trimmed strings in strictly sorted unique order")
    if not isinstance(value["rationale"], str) or not value["rationale"].strip():
        raise ValueError("judgment rationale must be nonempty")
    return value


def residue(context, kind, identity):
    u64(identity, kind)
    matches = [item for item in context["supplied_whole_residues"]
               if item["residue_id"] == {"kind": kind, "id": identity}]
    if len(matches) != 1 or matches[0]["liveness"] not in ("current", "live"):
        raise ValueError("required whole live native residue unavailable")
    item = matches[0]
    u64(item["object_version"], "object version")
    content = json.dumps(item["content"], ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode()
    if hashlib.sha256(content).hexdigest() != item["content_sha256"]:
        raise ValueError("whole native residue content hash mismatch")
    if item["pinned_cut_binding"] != context["pinned_canonical_cut"]:
        raise ValueError("whole native residue cut binding mismatch")
    return item


def related(item, relation, role, kind):
    return [edge["other"]["id"] for edge in item["ancestry"]
            if edge["kind"] == relation and edge["endpoint_role"] == role
            and edge["other"]["kind"] == kind]


def judgment_material(context, warrant_id, condition_ids):
    ids(condition_ids, "condition IDs")
    if context["operation"] != "judgment":
        raise ValueError("judgment context required")
    warrant = residue(context, "warrant", warrant_id)
    whole = sorted(related(warrant, "has-condition", "from", "warrant-condition"))
    if whole != condition_ids:
        raise ValueError("condition IDs must equal the selected warrant's entire condition set")
    snapshot, objects, texts = [], [warrant], []
    for identity in whole:
        condition = residue(context, "warrant-condition", identity)
        if (condition["retrieval_voice"]["state"] != "checked"
                or related(condition, "has-condition", "to", "warrant") != [warrant_id]):
            raise ValueError("judgment requires checked conditions of the selected warrant")
        texts.append(condition["retrieval_voice"]["text"])
        current = [item for item in context["supplied_whole_residues"]
                   if item["residue_id"]["kind"] == "evidence-record"
                   and item["liveness"] == "current"
                   and related(item, "checks", "from", "warrant-condition") == [identity]]
        if len(current) != 1:
            raise ValueError("judgment requires exactly one current evidence record per condition")
        evidence = residue(context, "evidence-record", current[0]["residue_id"]["id"])
        if evidence["retrieval_voice"]["condition_id"] != identity:
            raise ValueError("judgment evidence condition mismatch")
        snapshot.append({"condition_id": identity, "evidence_id": evidence["residue_id"]["id"]})
        objects.extend((condition, evidence))
    if sorted(texts) != warrant["retrieval_voice"]["conditions"]:
        raise ValueError("whole warrant condition text mismatch")
    return snapshot, objects


def practical_material(context, judgment_ids):
    ids(judgment_ids, "judgment IDs")
    if context["operation"] != "practical-question":
        raise ValueError("practical-question context required")
    return [residue(context, "judgment", identity) for identity in judgment_ids]


def command_for(context, operation, contribution, key, *, warrant_id=None,
                condition_ids=None, judgment_ids=None):
    if operation == "judgment":
        validate_contribution(contribution)
        snapshot, objects = judgment_material(context, warrant_id, condition_ids)
        body = {"warrant_id": warrant_id, "snapshot": snapshot,
                "polarity": contribution["polarity"], "defeat_conditions": contribution["defeat_conditions"]}
        kind = "make-judgment"
    else:
        objects = practical_material(context, judgment_ids)
        if (not isinstance(contribution, dict) or set(contribution) != {"text"}
                or not isinstance(contribution["text"], str) or not contribution["text"].strip()):
            raise ValueError("practical question requires nonempty text")
        body = {"judgment_ids": judgment_ids, "text": contribution["text"]}
        kind = "raise-practical-question"
    # CanonicalId uses native enum order followed by numeric u64, never lexical tokens.
    order = {"evidence-record": 0, "warrant": 1, "warrant-condition": 2, "judgment": 3}
    objects.sort(key=lambda item: (order[item["residue_id"]["kind"]], item["residue_id"]["id"]))
    expected = [{**item["residue_id"], "version": item["object_version"]} for item in objects]
    return kind, {"body": body, "command_version": 1, "expected_object_versions": expected,
                  "idempotency_key": key}
