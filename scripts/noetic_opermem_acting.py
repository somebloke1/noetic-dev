"""Exact native act artifacts bound to a retained external occurrence."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path

if __package__:
    from scripts import noetic_opermem_judgment as native, noetic_act_observation as evidence
else:
    import noetic_opermem_judgment as native
    import noetic_act_observation as evidence


def artifact(value):
    if (not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > 24576
            or any(c != "\n" and unicodedata.category(c) == "Cc" for c in value)):
        raise ValueError("native exact artifact requires nonblank UTF-8 text <=24576 bytes, with LF as the only control character")


def contribution(value):
    if not isinstance(value, dict) or set(value) not in ({"observed_act", "outcome"}, {"observed_act", "outcome", "deviation"}):
        raise ValueError("acting contribution requires exact observed_act, outcome and optional deviation")
    for text in value.values():
        artifact(text)
    if sum(len(text.encode("utf-8")) for text in value.values()) > 32768:
        raise ValueError("native combined acting artifacts exceed32768 UTF-8 bytes")
    return value


def bind(value, archive: Path, manifest_sha256: str):
    contribution(value)
    if archive is None or not isinstance(manifest_sha256, str) or len(manifest_sha256) != 64:
        raise ValueError("frozen observation archive and exact manifest SHA256 required")
    manifest = evidence.revalidate(archive, manifest_sha256, current=False)
    if not manifest["selected"]["occurred"]:
        raise ValueError("launch failure is retained evidence, not an occurred act for native observation")
    return {**value, "observation": {"manifest_sha256": manifest_sha256,
                                   "finish_sequence": manifest["selected"]["finish_sequence"]}}


def validate_bound(value, archive: Path, manifest_sha256: str):
    if not isinstance(value, dict) or "observation" not in value:
        raise ValueError("host observation binding required")
    prose = {key: text for key, text in value.items() if key != "observation"}
    if bind(prose, archive, manifest_sha256) != value:
        raise ValueError("observation differs from the frozen manifest/selected event binding")
    return prose


def copy_archive(source: Path, destination: Path, manifest_sha256: str):
    manifest = evidence.revalidate(source, manifest_sha256, current=False)
    destination.mkdir(mode=0o700)
    for name in ["manifest.json", *manifest["files"]]:
        target = destination / name
        with target.open("xb") as stream:
            stream.write((source / name).read_bytes())
        target.chmod(0o600)
    evidence.revalidate(destination, manifest_sha256, current=False)
    return manifest


def residue(context, kind, identity):
    native.u64(identity, kind)
    matches = [item for item in context["supplied_whole_residues"]
               if item["residue_id"] == {"kind": kind, "id": identity}]
    if len(matches) != 1 or matches[0]["liveness"] not in ("current", "live", "eligible"):
        raise ValueError("required eligible whole native acting residue unavailable")
    item = matches[0]
    native.u64(item["object_version"], "object version")
    encoded = json.dumps(item["content"], ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode()
    if hashlib.sha256(encoded).hexdigest() != item["content_sha256"] or item["pinned_cut_binding"] != context["pinned_canonical_cut"]:
        raise ValueError("whole native acting residue content/cut binding mismatch")
    return item


def material(context, plan_id, step_id):
    if context["operation"] != "acting":
        raise ValueError("native acting context required")
    plan, step = residue(context, "plan", plan_id), residue(context, "plan-step", step_id)
    for item in (plan, step):
        if item["retrieval_voice"]["state"] not in ("planned", "in-progress") or item["retrieval_voice"]["executable"] is not True:
            raise ValueError("native plan/step must be prospectively executable")
    if native.related(step, "has-step", "to", "plan") != [plan_id]:
        raise ValueError("selected native step must belong to the selected plan")
    return plan, step


def command_for(context, value, key, *, plan_id, step_id, observation_evidence, observation_manifest_sha256):
    prose = validate_bound(value, observation_evidence, observation_manifest_sha256)
    plan, step = material(context, plan_id, step_id)
    matching = prose["observed_act"] == step["retrieval_voice"]["action"]
    if matching == ("deviation" in prose):
        raise ValueError("native deviation must be absent for an exact planned-action match and present for a mismatch")
    expected = [{**item["residue_id"], "version": item["object_version"]} for item in (plan, step)]
    return "observe-act", {"body": {"plan_id": plan_id, "step_id": step_id, **prose},
                           "command_version": 1, "expected_object_versions": expected, "idempotency_key": key}


def binding(context, plan_id, step_id, manifest_sha256, manifest, run_id):
    encoded = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {"version": "noetic-acting-binding/v1", "observing_run_id": run_id,
            "native_context_sha256": evidence.digest(encoded), "pinned_canonical_cut": context["pinned_canonical_cut"],
            "plan_id": plan_id, "step_id": step_id, "manifest_sha256": manifest_sha256,
            "selected": manifest["selected"], "source_run_dir": manifest["source_run_dir"],
            "evidence_mode": "archival", "correlation": "retrospective-selected-plan-step; original dispatch unestablished"}
