#!/usr/bin/env python3
"""Synthesis execution and review with Opermem operations 1–14 and native typed residue."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import select
import shutil
import sys
import sqlite3
import subprocess
import time
import uuid

if __package__:
    from scripts import noetic_develop, noetic_run, noetic_telos, noetic_opermem_checking, noetic_opermem_judgment, noetic_opermem_practical, noetic_opermem_decision, noetic_opermem_acting, noetic_act_observation
else:
    import noetic_develop
    import noetic_run
    import noetic_telos
    import noetic_opermem_checking
    import noetic_opermem_judgment
    import noetic_opermem_practical
    import noetic_opermem_decision
    import noetic_opermem_acting
    import noetic_act_observation


KINDS = {
    "question": "raise-intelligence-question",
    "insight": "note-insight",
    "formulation": "formulate-understanding",
    "reflection": "question-correctness",
    "conditional-structure": "define-conditional-structure",
    "checking": "check-condition",
    "judgment": "make-judgment",
    "practical-question": "raise-practical-question",
    "practical-inquiry": "inquire-into-courses",
    "practical-insight": "grasp-possible-course",
    "deliberation": "deliberate",
    "decision": "decide",
    "planning": "plan",
    "acting": "observe-act",
}
PARENT_KINDS = {
    "question": ("experience", None),
    "insight": ("intelligence-question", None),
    "formulation": ("unverified-insight-trace", None),
    "reflection": ("formulation-hypothesis", None),
    "conditional-structure": ("reflection-question", None),
    "checking": ("warrant-condition", None),
}
MARKER = "OPERMEM_CONTRIBUTION_JSON: "
CONTEXT_OPERATIONS = ("judgment", "practical-question") + noetic_opermem_practical.OPERATIONS + noetic_opermem_decision.OPERATIONS + ("acting",)


def canonical(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _private_selection(path):
    path = Path(path)
    if path.exists() and (not path.is_dir() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077):
        raise ValueError(f"private directory required: {path}")


def private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = path.resolve(strict=True)
    if path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise ValueError(f"private directory required: {path}")
    return path


class OperationHost:
    def __init__(self, binary: Path, store: Path, transcript: Path):
        binary = binary.resolve(strict=True)
        store = private_dir(store)
        transcript = private_dir(transcript)
        if any(transcript.iterdir()) or transcript == store:
            raise ValueError("transcript must be a fresh empty directory separate from the store")
        self.process = subprocess.Popen([str(binary), str(store), str(transcript)], env={},
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
        self.sequence = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        assert self.process.stdin is not None
        self.process.stdin.close()
        try:
            try:
                status = self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
                raise RuntimeError("Opermem operation host did not exit") from exc
            assert self.process.stderr is not None
            diagnostic = self.process.stderr.read().decode(errors="replace")[:500]
        finally:
            assert self.process.stdout is not None and self.process.stderr is not None
            self.process.stdout.close()
            self.process.stderr.close()
        if status != 0 and exc_type is None:
            raise RuntimeError(f"Opermem operation host exited {status}: {diagnostic}")

    def exchange(self, kind: str, payload: dict) -> dict:
        self.sequence += 1
        frame = {"correlation_id": self.sequence, "expected_architecture_semantics": 1,
                 "expected_policy_version": 1, "expected_schema_version": 3, "kind": kind,
                 "payload": payload, "protocol_version": 1, "request_id": self.sequence}
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write(canonical(frame) + b"\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + 10
        response = bytearray()
        while not response.endswith(b"\n"):
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.process.stdout], [], [], remaining)[0]:
                raise TimeoutError("Opermem operation host response timed out")
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk or len(response) + len(chunk) > 524288:
                raise RuntimeError("Opermem operation host response missing or oversized")
            response.extend(chunk)
        result = json.loads(response)
        if (result.get("request_id") != self.sequence
                or result.get("correlation_id") != self.sequence
                or result.get("class") not in ("success", "idempotency-replay")):
            raise RuntimeError(f"Opermem {kind} refused: {result.get('class')} / {result.get('kind')}")
        return result

    def context(self, purpose: dict) -> dict:
        purpose = dict(purpose)
        predecessor = purpose.pop("supersedes_decision_id", None)
        predecessor_evaluation = purpose.pop("predecessor_evaluation_id", None)
        health = self.exchange("health", {})
        cut = health["payload"]["pinned_canonical_cut"]
        expected = {"expected_architecture_semantics": cut["architecture_semantics"],
                    "expected_contract_version": cut["contract_version"],
                    "expected_epoch": cut["authority_epoch"],
                    "expected_generation": cut["authority_generation"],
                    "expected_policy_generation": cut["policy_generation"],
                    "expected_policy_id": cut["policy_id"],
                    "expected_policy_version": cut["policy_version"],
                    "expected_scope": cut["authority_scope_id"],
                    "expected_workspace": cut["workspace_id"]}
        context = self.exchange("context-export", {
            "answer_mode": "ordinary", "cursor": None, "exact_search": None,
            "expected_cut": expected, "limit": 64, "purpose": purpose,
        })["payload"]
        operation = purpose["operation"]
        if operation in ("practical-insight", "deliberation"):
            packets = [context]
            if operation != "practical-inquiry":
                packets.append(self.exchange("context-export", {
                    "answer_mode": "ordinary", "cursor": None, "exact_search": None,
                    "expected_cut": expected, "limit": 64,
                    "purpose": {"operation": "practical-inquiry",
                                "practical_question_id": purpose["practical_question_id"]},
                })["payload"])
            return noetic_opermem_practical.compose_context(operation, packets)
        if predecessor is not None:
            supplemental_purpose = ({"operation": "decision", "evaluation_id": predecessor_evaluation,
                                     "judgment_basis_ids": purpose["judgment_basis_ids"]}
                                    if predecessor_evaluation is not None else
                                    {"operation": "planning", "decision_id": predecessor,
                                     "judgment_basis_ids": purpose["judgment_basis_ids"]})
            supplemental = self.exchange("context-export", {
                "answer_mode": "ordinary", "cursor": None, "exact_search": None,
                "expected_cut": expected, "limit": 64, "purpose": supplemental_purpose,
            })["payload"]
            return noetic_opermem_decision.compose_context([context, supplemental])
        return context


def purpose_for(operation: str, parent_id: int | None,
                formulation_id: int | None = None, *, warrant_id: int | None = None,
                condition_ids: list[int] | None = None, judgment_ids: list[int] | None = None,
                practical_question_id: int | None = None, option_id: int | None = None,
                option_ids: list[int] | None = None, evaluation_id=None, decision_id=None,
                judgment_basis_ids=None, supersedes_decision_id=None, predecessor_evaluation_id=None, plan_id=None, step_id=None,
                occasion_kind=None, occasion_id=None) -> dict:
    if (occasion_kind is not None or occasion_id is not None) and operation != "question":
        raise ValueError("occasion selectors apply only to question")
    if (plan_id is not None or step_id is not None) and operation != "acting":
        raise ValueError("plan/step IDs apply only to acting")
    if operation == "acting":
        if parent_id is not None:
            raise ValueError("acting requires explicit native plan/step anchors")
        noetic_opermem_judgment.u64(plan_id, "plan ID")
        noetic_opermem_judgment.u64(step_id, "step ID")
    for name, value, applicable in (
        ("evaluation ID", evaluation_id, ("decision",)),
        ("decision ID", decision_id, ("planning",)),
        ("judgment basis IDs", judgment_basis_ids, noetic_opermem_decision.OPERATIONS),
        ("supersedes decision ID", supersedes_decision_id, ("decision",)),
        ("predecessor evaluation ID", predecessor_evaluation_id, ("decision",)),
    ):
        if value is not None and operation not in applicable:
            raise ValueError(f"{name} does not apply to {operation}")
    if predecessor_evaluation_id is not None and supersedes_decision_id is None:
        raise ValueError("predecessor evaluation ID requires an explicit supersedes decision ID")
    if operation in noetic_opermem_decision.OPERATIONS:
        if parent_id is not None:
            raise ValueError("decision/planning require explicit native anchors, not parent ID")
        noetic_opermem_judgment.ids(judgment_basis_ids, "judgment basis IDs")
        anchor = "evaluation_id" if operation == "decision" else "decision_id"
        identity = evaluation_id if operation == "decision" else decision_id
        noetic_opermem_judgment.u64(identity, anchor)
        purpose = {"operation": operation, anchor: identity, "judgment_basis_ids": judgment_basis_ids}
        if supersedes_decision_id is not None:
            noetic_opermem_judgment.u64(supersedes_decision_id, "supersedes decision ID")
            purpose["supersedes_decision_id"] = supersedes_decision_id
        if predecessor_evaluation_id is not None:
            noetic_opermem_judgment.u64(predecessor_evaluation_id, "predecessor evaluation ID")
            purpose["predecessor_evaluation_id"] = predecessor_evaluation_id
    if practical_question_id is not None and operation not in noetic_opermem_practical.OPERATIONS:
        raise ValueError("practical question ID applies only to operations 9–11")
    if option_id is not None and operation != "practical-insight":
        raise ValueError("option ID applies only to practical-insight")
    if option_ids is not None and operation != "deliberation":
        raise ValueError("option IDs apply only to deliberation")
    if operation in noetic_opermem_practical.OPERATIONS:
        if parent_id is not None:
            raise ValueError("practical operations require explicit native anchors, not parent ID")
        noetic_opermem_judgment.u64(practical_question_id, "practical question ID")
    if warrant_id is not None and operation not in ("checking", "judgment"):
        raise ValueError("warrant ID applies only to checking or judgment")
    if condition_ids is not None and operation != "judgment":
        raise ValueError("condition IDs apply only to judgment")
    if judgment_ids is not None and operation != "practical-question":
        raise ValueError("judgment IDs apply only to practical-question")
    if formulation_id is not None and operation != "conditional-structure":
        raise ValueError("formulation ID applies only to conditional-structure")
    if operation in noetic_opermem_decision.OPERATIONS:
        return purpose
    if operation in noetic_opermem_practical.OPERATIONS:
        purpose = {"operation": operation, "practical_question_id": practical_question_id}
        if operation == "practical-insight":
            noetic_opermem_judgment.u64(option_id, "option ID")
            purpose["option_id"] = option_id
        elif operation == "deliberation":
            noetic_opermem_judgment.ids(option_ids, "option IDs")
            if len(option_ids) < 2:
                raise ValueError("deliberation requires at least two native options")
            purpose["option_ids"] = option_ids
        return purpose
    if operation in ("judgment", "practical-question"):
        if parent_id is not None:
            raise ValueError("judgment and practical-question require complete explicit anchors, not parent ID")
        if operation == "judgment":
            noetic_opermem_judgment.u64(warrant_id, "warrant ID")
            noetic_opermem_judgment.ids(condition_ids, "condition IDs")
            return {"operation": operation, "warrant_id": warrant_id, "condition_ids": condition_ids}
        noetic_opermem_judgment.ids(judgment_ids, "judgment IDs")
        return {"operation": operation, "judgment_ids": judgment_ids}
    if operation == "acting":
        return {"operation": "acting", "plan_id": plan_id, "step_id": step_id}
    if operation == "question":
        kind = occasion_kind if occasion_kind is not None else "experience"
        if kind not in ("experience", "outcome-as-experience"):
            raise ValueError("question occasion kind must be experience or outcome-as-experience")
        if kind == "outcome-as-experience" and occasion_id is None:
            raise ValueError("outcome-as-experience requires an explicit occasion ID")
        identity = occasion_id if occasion_id is not None else 1
        noetic_opermem_judgment.u64(identity, "occasion ID")
        return {"operation": "question", "occasion": {"kind": kind, "id": identity}}
    if type(parent_id) is not int or parent_id <= 0:
        raise ValueError(f"{operation} requires a positive parent ID")
    if operation == "checking":
        if type(warrant_id) is not int or not 0 < warrant_id < 2**64:
            raise ValueError("checking requires a positive warrant ID")
        if parent_id >= 2**64:
            raise ValueError("checking condition ID must be a u64")
        return {"operation": operation, "warrant_id": warrant_id, "condition_id": parent_id}
    if operation == "insight":
        return {"operation": "insight", "question_id": parent_id}
    if operation == "formulation":
        return {"operation": "formulation", "insight_id": parent_id}
    if operation == "reflection":
        return {"operation": "reflection", "formulation_id": parent_id}
    if operation == "conditional-structure":
        if type(formulation_id) is not int or formulation_id <= 0:
            raise ValueError("conditional-structure requires a positive formulation ID")
        return {"operation": operation, "reflection_id": parent_id,
                "formulation_id": formulation_id}
    raise ValueError(f"unsupported operation: {operation}")


def parent_from_context(context: dict, operation: str, parent_id: int | None, *,
                        occasion_kind=None, occasion_id=None) -> dict:
    kind, fixed_id = PARENT_KINDS[operation]
    if operation == "question":
        occasion = purpose_for("question", parent_id, occasion_kind=occasion_kind, occasion_id=occasion_id)["occasion"]
        kind, target = occasion["kind"], occasion["id"]
    else:
        target = fixed_id or parent_id
    matches = [item for item in context["supplied_whole_residues"]
               if item["residue_id"] == {"kind": kind, "id": target}]
    if len(matches) != 1 or matches[0]["liveness"] not in ("current", "live"):
        raise ValueError("required live parent residue is unavailable in current Opermem context")
    return matches[0]


def contribution_from_report(report: str, operation: str) -> dict:
    lines = [line[len(MARKER):] for line in report.splitlines() if line.startswith(MARKER)]
    if len(lines) != 1:
        raise ValueError("agent report must contain one Opermem contribution marker")
    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate Opermem contribution field")
            result[key] = value
        return result
    value = json.loads(lines[0], object_pairs_hook=unique_fields)
    if operation == "acting":
        return noetic_opermem_acting.contribution(value)
    if operation in noetic_opermem_decision.OPERATIONS:
        return noetic_opermem_decision.contribution(value, operation)
    if operation in noetic_opermem_practical.OPERATIONS:
        return noetic_opermem_practical.contribution(value, operation)
    if operation == "judgment":
        return noetic_opermem_judgment.validate_contribution(value)
    fields = ({"conditions"} if operation == "conditional-structure" else
              {"text", "question_kind"} if operation == "question" else {"text"})
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("agent contribution has incorrect fields")
    if operation == "conditional-structure":
        conditions = value["conditions"]
        if (not isinstance(conditions, list) or not conditions
                or any(not isinstance(item, str) or not item or item != item.strip()
                       for item in conditions)
                or any(left >= right for left, right in zip(conditions, conditions[1:]))):
            raise ValueError("conditions must be nonempty trimmed strings in strictly sorted unique order")
        return value
    if not isinstance(value["text"], str) or not value["text"].strip():
        raise ValueError("agent contribution text must be nonempty")
    if operation == "question" and value["question_kind"] not in ("what", "why", "how"):
        raise ValueError("question_kind must be what, why, or how")
    return value


def command_for(operation: str, parent_id: int | None, parent: dict, contribution: dict,
                key: str, formulation: dict | None = None, *, occasion_kind=None) -> tuple[str, dict]:
    if operation == "checking" or operation in CONTEXT_OPERATIONS:
        raise ValueError("operation command requires whole native context")
    target = parent["residue_id"]["id"] if operation == "question" else parent_id
    expected = [{"id": target, "kind": parent["residue_id"]["kind"] if operation == "question" else PARENT_KINDS[operation][0],
                 "version": parent["object_version"]}]
    if operation == "question":
        body = {"occasion_id": target, "occasion_sensitivity": "ordinary", **contribution}
        if occasion_kind is not None or parent["residue_id"]["kind"] != "experience":
            body["occasion_kind"] = parent["residue_id"]["kind"]
    elif operation == "conditional-structure":
        if formulation is None:
            raise ValueError("conditional-structure requires current formulation residue")
        formulation_id = formulation["residue_id"]["id"]
        body = {"reflection_id": target, "formulation_id": formulation_id, **contribution}
        # Native IdentityKind ordering places reflection before formulation.
        expected.append({"id": formulation_id, "kind": "formulation-hypothesis",
                         "version": formulation["object_version"]})
    else:
        field = {"insight": "question_id", "formulation": "insight_id",
                 "reflection": "formulation_id"}[operation]
        body = {field: target, **contribution}
    return KINDS[operation], {
        "body": body, "command_version": 1,
        "expected_object_versions": expected,
        "idempotency_key": key,
    }



def validate_context(context: dict, operation: str, parent_id: int | None, *,
                     formulation_id=None, warrant_id=None, condition_ids=None, judgment_ids=None,
                     practical_question_id=None, option_id=None, option_ids=None, evaluation_id=None, decision_id=None,
                     judgment_basis_ids=None, supersedes_decision_id=None, predecessor_evaluation_id=None, plan_id=None, step_id=None,
                     occasion_kind=None, occasion_id=None, observation_evidence=None,
                     observation_manifest_sha256=None):
    if operation == "acting":
        noetic_opermem_acting.material(context, plan_id, step_id)
    elif operation in noetic_opermem_decision.OPERATIONS:
        noetic_opermem_decision.material(context, operation,
            evaluation_id=evaluation_id, decision_id=decision_id, judgment_basis_ids=judgment_basis_ids,
            supersedes_decision_id=supersedes_decision_id, predecessor_evaluation_id=predecessor_evaluation_id)
    elif operation in noetic_opermem_practical.OPERATIONS:
        noetic_opermem_practical.material(context, operation, practical_question_id,
                                         option_id=option_id, option_ids=option_ids)
    elif operation == "judgment":
        noetic_opermem_judgment.judgment_material(context, warrant_id, condition_ids)
    elif operation == "practical-question":
        noetic_opermem_judgment.practical_material(context, judgment_ids)
    else:
        parent_from_context(context, operation, parent_id, occasion_kind=occasion_kind, occasion_id=occasion_id)
        if operation == "conditional-structure":
            parent_from_context(context, "reflection", formulation_id)


def contextual_command(context: dict, operation: str, parent_id: int | None,
                       contribution: dict, key: str, *, formulation_id=None,
                       warrant_id=None, condition_ids=None, judgment_ids=None,
                       practical_question_id=None, option_id=None, option_ids=None, evaluation_id=None, decision_id=None,
                     judgment_basis_ids=None, supersedes_decision_id=None, predecessor_evaluation_id=None, plan_id=None, step_id=None,
                     occasion_kind=None, occasion_id=None, observation_evidence=None,
                     observation_manifest_sha256=None):
    if operation == "acting":
        return noetic_opermem_acting.command_for(context, contribution, key, plan_id=plan_id, step_id=step_id,
            observation_evidence=observation_evidence, observation_manifest_sha256=observation_manifest_sha256)
    if operation in noetic_opermem_decision.OPERATIONS:
        return noetic_opermem_decision.command_for(context, operation, contribution, key,
            evaluation_id=evaluation_id, decision_id=decision_id, judgment_basis_ids=judgment_basis_ids,
            supersedes_decision_id=supersedes_decision_id, predecessor_evaluation_id=predecessor_evaluation_id)
    if operation in noetic_opermem_practical.OPERATIONS:
        return noetic_opermem_practical.command_for(context, operation, contribution, key,
            practical_question_id=practical_question_id, option_id=option_id, option_ids=option_ids)
    if operation in ("judgment", "practical-question"):
        return noetic_opermem_judgment.command_for(context, operation, contribution, key,
            warrant_id=warrant_id, condition_ids=condition_ids, judgment_ids=judgment_ids)
    if operation == "checking":
        return noetic_opermem_checking.command_for(context, contribution, key)
    formulation = (parent_from_context(context, "reflection", formulation_id)
                   if operation == "conditional-structure" else None)
    return command_for(operation, parent_id, parent_from_context(context, operation, parent_id, occasion_kind=occasion_kind, occasion_id=occasion_id),
                       contribution, key, formulation, occasion_kind=occasion_kind)


def fresh_transcript(root: Path) -> Path:
    root = private_dir(root)
    path = root / uuid.uuid4().hex
    path.mkdir(mode=0o700)
    return path


def retrieve(binary: Path, store: Path, transcripts: Path, purpose: dict) -> tuple[dict, Path]:
    transcript = fresh_transcript(transcripts)
    with OperationHost(binary, store, transcript) as host:
        return host.context(purpose), transcript


def submit(binary: Path, store: Path, transcripts: Path, operation: str,
           parent_id: int | None, contribution: dict, key: str,
           expected_context: dict | None = None,
           pending_path: Path | None = None, *,
           formulation_id: int | None = None, warrant_id: int | None = None,
           checking_evidence: Path | None = None,
           checking_manifest_sha256: str | None = None,
           condition_ids: list[int] | None = None,
           judgment_ids: list[int] | None = None, practical_question_id: int | None = None,
           option_id: int | None = None, option_ids: list[int] | None = None, evaluation_id=None, decision_id=None,
           judgment_basis_ids=None, supersedes_decision_id=None, predecessor_evaluation_id=None, plan_id=None, step_id=None,
           occasion_kind=None, occasion_id=None, observation_evidence=None,
           observation_manifest_sha256=None) -> tuple[dict, Path]:
    purpose = purpose_for(operation, parent_id, formulation_id, warrant_id=warrant_id,
                          condition_ids=condition_ids, judgment_ids=judgment_ids,
                          practical_question_id=practical_question_id, option_id=option_id, option_ids=option_ids,
            evaluation_id=evaluation_id, decision_id=decision_id, judgment_basis_ids=judgment_basis_ids,
            supersedes_decision_id=supersedes_decision_id, predecessor_evaluation_id=predecessor_evaluation_id, plan_id=plan_id, step_id=step_id,
            occasion_kind=occasion_kind, occasion_id=occasion_id)
    transcript = fresh_transcript(transcripts)
    with OperationHost(binary, store, transcript) as host:
        context = host.context(purpose)
        if expected_context is not None and context != expected_context:
            raise ValueError("Opermem context changed since actor invocation; contribution not submitted")
        validate_context(context, operation, parent_id, formulation_id=formulation_id,
                         warrant_id=warrant_id, condition_ids=condition_ids, judgment_ids=judgment_ids,
                         practical_question_id=practical_question_id, option_id=option_id, option_ids=option_ids,
            evaluation_id=evaluation_id, decision_id=decision_id, judgment_basis_ids=judgment_basis_ids,
            supersedes_decision_id=supersedes_decision_id, predecessor_evaluation_id=predecessor_evaluation_id, plan_id=plan_id, step_id=step_id,
            occasion_kind=occasion_kind, occasion_id=occasion_id)
        if operation == "checking":
            if checking_evidence is None or checking_manifest_sha256 is None:
                raise ValueError("checking requires host-captured evidence")
            actual = noetic_opermem_checking.contribution(
                checking_evidence, context, parent_id, warrant_id, checking_manifest_sha256)
            if actual != contribution:
                raise ValueError("checking contribution differs from captured evidence")
        kind, payload = contextual_command(context, operation, parent_id, contribution, key,
            formulation_id=formulation_id, warrant_id=warrant_id,
            condition_ids=condition_ids, judgment_ids=judgment_ids,
            practical_question_id=practical_question_id, option_id=option_id, option_ids=option_ids,
            evaluation_id=evaluation_id, decision_id=decision_id, judgment_basis_ids=judgment_basis_ids,
            supersedes_decision_id=supersedes_decision_id, predecessor_evaluation_id=predecessor_evaluation_id, plan_id=plan_id, step_id=step_id,
            occasion_kind=occasion_kind, occasion_id=occasion_id,
            observation_evidence=observation_evidence, observation_manifest_sha256=observation_manifest_sha256)
        if pending_path is not None:
            pending = {"kind": kind, "payload": payload}
            if operation in CONTEXT_OPERATIONS:
                pending["contribution"] = contribution
            with pending_path.open("x", encoding="utf-8") as stream:
                json.dump(pending, stream, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
        return host.exchange(kind, payload), transcript


def native_accepted_receipt(store: Path, operation: str, context: dict, key: str) -> dict | None:
    cut = context["pinned_canonical_cut"]
    workspace = noetic_opermem_judgment.u64(cut["workspace_id"], "workspace")
    scope = noetic_opermem_judgment.u64(cut["authority_scope_id"], "scope")
    # The current host pins integration/effect-scope version 1; native schema-v3
    # stores slot IDs as big-endian u64 blobs. This lookup grants only replay.
    operation_number = tuple(KINDS).index(operation) + 1
    connection = None
    try:
        connection = sqlite3.connect((store / "authority.sqlite3").resolve(strict=True).as_uri()
                                     + "?mode=ro", uri=True, timeout=10)
        rows = connection.execute(
            "SELECT receipt_id,result_bytes FROM primary_receipts "
            "WHERE workspace_id=? AND scope_id=? AND integration_id=? AND effect_kind=? "
            "AND effect_scope_version=? AND idempotency_key=? AND outcome=1 "
            "AND commit_kind=1 AND semantic_commit_id=commit_id",
            (workspace.to_bytes(8, "big"), scope.to_bytes(8, "big"), (1).to_bytes(8, "big"),
             operation_number, (1).to_bytes(8, "big"), key.encode("utf-8"))).fetchall()
    except (OSError, sqlite3.Error) as exc:
        raise ValueError("native committed-receipt lookup unavailable; pending command not submitted") from exc
    finally:
        if connection is not None:
            connection.close()
    if not rows:
        return None
    if (len(rows) != 1 or type(rows[0][0]) is not bytes or len(rows[0][0]) != 8
            or not int.from_bytes(rows[0][0], "big") or type(rows[0][1]) is not bytes or not rows[0][1]):
        raise ValueError("native committed-receipt lookup incomplete; pending command not submitted")
    return {"receipt_id": int.from_bytes(rows[0][0], "big"), "exact_result": rows[0][1].hex()}


def _scope_adapter(namespace):
    if not __package__:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.noetic_opermem_scope import OpermemScope
    return OpermemScope(namespace)


def _json_input(value):
    return json.loads(Path(value).read_text(encoding="utf-8")) if isinstance(value, (str, Path)) else value


def _retain_json(path, value):
    path = Path(path)
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise ValueError("Retained owned native correspondence changed: " + str(path))
        return
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def owned_run(run_dir, *, revalidate_purpose=False):
    """Read-only ownership gate. A damaged assigned run never becomes legacy."""
    run_dir = Path(run_dir).resolve(strict=True)
    declarations = [e["data"] for e in noetic_run.read_events(run_dir) if e["kind"] == "scope.bound"]
    path = run_dir / "opermem-scope.json"
    link_path = run_dir / "opermem-link.json"
    link = json.loads(link_path.read_text()) if link_path.exists() else None
    claimed = path.exists() or bool(declarations) or isinstance(link, dict) and "owned_execution" in link
    if not claimed:
        return None
    if len(declarations) != 1:
        raise ValueError("Owned Opermem run requires its original scope journal association")
    binding = declarations[0]
    adapter = _scope_adapter(binding["namespace_path"])
    adapter.validate_binding(binding, revalidate_purpose=revalidate_purpose)
    adapter.lifecycle(binding)._validate_run(run_dir, revalidate_purpose=revalidate_purpose)
    event = adapter._event("run:" + binding["run_id"] + ":native-bound")
    if event is None or link != event["data"]["link"]:
        raise ValueError("Owned native link is unavailable or differs from canonical correspondence")
    expected = {"namespace_path": binding["namespace_path"], "namespace": binding["namespace"],
                "execution_id": binding["execution_id"], "preparation_path": binding["preparation_path"]}
    if (link.get("owned_execution") != expected or link["store"] != binding["store_ref"]["directory"]
            or link["host"] != binding["store_ref"]["host"] or link["operation"] != binding["operation"]
            or link["repository_workspace"] != binding["workspace"] or str(run_dir) != binding["run_dir"]):
        raise ValueError("Owned native store, operation or execution correspondence changed")
    return adapter, binding, link


def owned_correspondence(run_dir):
    owned = owned_run(run_dir)
    if owned is None:
        return {"correlation_status": "unassigned-legacy", "participants": []}
    adapter, binding, link = owned
    result = adapter.correspondence(binding)
    return {**result, "namespace_path": binding["namespace_path"], "initiator": binding["initiator"],
            "native_store_identity": {"directory": link["store"],
                "workspace_id": link["context"]["pinned_canonical_cut"]["workspace_id"],
                "authority_scope_id": link["context"]["pinned_canonical_cut"]["authority_scope_id"]},
            "context_coverage": "whole historical native packets; original standing/voice/cut/exclusions retained",
            "native_link": link}


def _owned_gate(run_dir, *, participants=False):
    owned = owned_run(run_dir, revalidate_purpose=True)
    if owned and participants:
        observed = owned[0].correspondence(owned[1])["participants"]
        if len(observed) != 2 or any(p["target"] is None or p["session_status"] != "closed" for p in observed):
            raise ValueError("Native deposit/replay requires genuine completed work and review participants")
        for participant in observed:
            report = noetic_develop.parse_transcript(Path(participant["observation"]["stdout"]), participant["native_session_ref"]["client"])
            if (Path(run_dir) / (participant["step"] + ".md")).read_text() != report["text"] + "\n":
                raise ValueError("Actor report differs from its actual retained native session")
    return owned


def _retain_receipt(run_dir):
    owned = _owned_gate(run_dir, participants=True)
    if owned:
        adapter, binding, _ = owned
        receipt = json.loads((Path(run_dir) / "opermem-receipt.json").read_text())
        payload = receipt["response"]["payload"]
        identity = {key: payload[key] for key in ("receipt_id", "exact_result")}
        identity["contribution"] = receipt["contribution"]
        original = adapter._event("run:" + binding["run_id"] + ":native-receipt")
        if original is not None:
            if original["data"] != identity:
                raise ValueError("Receipt differs from its original owned native receipt")
        else:
            actual = native_accepted_receipt(Path(binding["store_ref"]["directory"]), binding["operation"],
                owned[2]["context"], f"noetic-{binding['run_id']}-{binding['operation']}")
            if actual is None or any(identity[key] != value for key, value in actual.items()):
                raise ValueError("Receipt is not the actual committed native slot for this owned execution")
            adapter._record(binding, "native-receipt", "opermem-native-receipt", identity)


class _OwnedNativeLifecycle:
    def __init__(self, adapter, binding, link, archives, qualification):
        self.adapter, self.binding, self.link = adapter, binding, link
        self.base = adapter.lifecycle(binding)
        self.archives, self.qualification = archives, qualification

    def validate_develop(self, **kwargs):
        return self.base.validate_develop(**kwargs)

    def run_created(self, run_dir):
        self.base.run_created(run_dir)
        for source, name, digest in self.archives:
            if digest is None:
                shutil.copytree(source, run_dir / name)
            else:
                noetic_opermem_acting.copy_archive(source, run_dir / name, digest)
        if self.qualification is not None:
            _retain_json(run_dir / "genus-selection.json", self.qualification)
        _retain_json(run_dir / "opermem-link.json", self.link)
        self.adapter._record(self.binding, "native-bound", "opermem-native-bound", {"link": self.link})

    def validate_binding(self, run_dir):
        self.base.validate_binding(run_dir)
        _owned_gate(run_dir)

    def before_actor(self, run_dir, *args, **kwargs):
        _owned_gate(run_dir)
        return self.base.before_actor(run_dir, *args, **kwargs)

    def after_actor(self, run_dir, *args, **kwargs):
        return self.base.after_actor(run_dir, *args, **kwargs)


def _prepare_owned(args, task, worker_controls, purpose):
    request = _json_input(getattr(args, "scope_request", None))
    inputs = (getattr(args, "store_ref", None), getattr(args, "purpose_ref", None), getattr(args, "purpose_config", None))
    if request is None:
        if any(value is not None for value in inputs) or getattr(args, "source", None):
            raise ValueError("Owned store/purpose/source selections require an explicit scope request")
        return None
    if inputs[0] is None:
        raise ValueError("Owned Opermem requires an explicit store_ref")
    if (inputs[1] is None) != (inputs[2] is None):
        raise ValueError("Owned purpose requires both complete purpose_ref and purpose_config")
    if inputs[1] is None and any(value is not None for value in (args.telos_chain, args.telos_db, args.telos_source)):
        raise ValueError("Owned bare Telos linkage requires a complete purpose reference and resolver")
    adapter = _scope_adapter(request["namespace_path"])
    reference = _json_input(inputs[0])
    adapter.validate_request(request, args.workspace)
    adapter.validate_store(reference, request["effort_root"])
    if reference["directory"] != str(args.store.resolve()) or reference["host"] != str(args.host.resolve(strict=True)):
        raise ValueError("Selected native host/store differs from the effort correspondence")
    _private_selection(args.store)
    _private_selection(args.runs_dir)
    if args.timeout <= 0:
        raise ValueError("Actor timeout must be positive")
    if not args.inquiry and not args.verify:
        raise ValueError("Development requires an explicit verification command")
    if args.operation == "checking" and (not args.inquiry or args.verify or args.checking_spec is None):
        raise ValueError("Checking requires read-only inquiry and an exact checking specification")
    if args.operation == "acting":
        if not args.inquiry or args.verify or (args.observed_run is None) == (args.observation_evidence is None):
            raise ValueError("Acting requires one explicit retained occurrence and read-only inquiry")
        if args.observation_evidence is not None and not args.observation_manifest_sha256:
            raise ValueError("Archived occurrence requires its frozen manifest digest")
    # Telos resolver validation and source capture are read-only before reservation.
    from scripts import noetic_purpose_binding as purposes
    purpose_ref, config = _json_input(inputs[1]), _json_input(inputs[2])
    if purpose_ref is not None:
        purposes.prepare(purpose_ref, config, request, chain=args.telos_chain, db=args.telos_db, source=args.telos_source)
    binding = adapter.prepare_execution(request, task=task, workspace=args.workspace,
        runs_dir=args.runs_dir, store_ref=reference, operation=args.operation, inquiry=args.inquiry,
        client=args.client, model=args.model, review_model=args.review_model, worker_controls=worker_controls,
        purpose_ref=purpose_ref, purpose_config=config, source_paths=getattr(args, "source", ()) or (),
        occasion=purpose.get("occasion"))
    adapter._record(binding, "native-requested", "opermem-native-requested", {"purpose": purpose})
    args.telos_chain = binding["telos_chain"]
    args.telos_db = Path(binding["telos_db"]) if binding["telos_db"] is not None else None
    args.telos_source = Path(binding["telos_source"]) if binding["telos_source"] is not None else None
    return adapter, binding


def resume_run(run_dir: Path, binary: Path, store: Path, transcripts: Path) -> int:
    run_dir = run_dir.resolve(strict=True)
    link = json.loads((run_dir / "opermem-link.json").read_text(encoding="utf-8"))
    if link["host"] != str(binary) or link["store"] != str(store):
        raise ValueError("run is bound to a different Opermem host or store")
    owned = _owned_gate(run_dir, participants=True)
    state = noetic_run.project(noetic_run.read_events(run_dir))
    if state["state"] != "accepted":
        raise ValueError("only a reviewed accepted run can resume Opermem submission")
    receipt_path = run_dir / "opermem-receipt.json"
    checked = None
    bound_act = None
    if link["operation"] == "acting":
        bound_act = noetic_opermem_acting.bind(
            contribution_from_report((run_dir / "work.md").read_text(), "acting"),
            run_dir / "observation-evidence", link["observation_manifest_sha256"])
        manifest = noetic_act_observation.revalidate(run_dir / "observation-evidence", link["observation_manifest_sha256"], current=False)
        expected_binding = noetic_opermem_acting.binding(link["context"], link["plan_id"], link["step_id"],
                                                        link["observation_manifest_sha256"], manifest, run_dir.name)
        if json.loads((run_dir / "observation-binding.json").read_text()) != expected_binding:
            raise ValueError("observation binding differs from original context/occurrence/run")
    if link["operation"] == "checking":
        checked = noetic_opermem_checking.contribution(
            run_dir / "checking-evidence", link["context"], link["parent_id"],
            link["warrant_id"], link["checking_manifest_sha256"], current=False)
        if receipt_path.exists() and json.loads(receipt_path.read_text())["contribution"] != checked:
            raise ValueError("persisted checking receipt differs from host-captured contribution")
    if receipt_path.exists():
        if link["operation"] in CONTEXT_OPERATIONS:
            contribution = bound_act if bound_act is not None else contribution_from_report((run_dir / "work.md").read_text(), link["operation"])
            if json.loads(receipt_path.read_text())["contribution"] != contribution:
                raise ValueError("persisted receipt differs from the bound actor contribution")
        _retain_receipt(run_dir)
        state = sync_telos(run_dir)
        print(receipt_path.read_text(encoding="utf-8"))
        return 1 if state.get("telos_error") else 0
    pending_path = run_dir / "opermem-pending.json"
    pending = json.loads(pending_path.read_text(encoding="utf-8")) if pending_path.exists() or owned is None else None
    fields = {"kind", "payload", "contribution"} if link["operation"] in CONTEXT_OPERATIONS else {"kind", "payload"}
    if pending is not None and (set(pending) != fields or pending["kind"] != KINDS[link["operation"]]):
        raise ValueError("invalid persisted Opermem command")
    contribution = checked if checked is not None else bound_act if bound_act is not None else contribution_from_report(
        (run_dir / "work.md").read_text(encoding="utf-8"), link["operation"])
    formulation_id = link.get("formulation_id")
    anchors = {name: link.get(name) for name in ("warrant_id", "condition_ids", "judgment_ids",
                                               "practical_question_id", "option_id", "option_ids", "evaluation_id", "decision_id",
                                               "judgment_basis_ids", "supersedes_decision_id", "predecessor_evaluation_id", "plan_id", "step_id", "occasion_kind", "occasion_id")}
    purpose = purpose_for(link["operation"], link["parent_id"], formulation_id, **anchors)
    expected_kind, expected_payload = contextual_command(
        link["context"], link["operation"], link["parent_id"], contribution,
        f"noetic-{run_dir.name}-{link['operation']}", formulation_id=formulation_id,
        observation_evidence=run_dir / "observation-evidence" if bound_act is not None else None,
        observation_manifest_sha256=link.get("observation_manifest_sha256"), **anchors)
    expected_pending = {"kind": expected_kind, "payload": expected_payload}
    if "contribution" in fields:
        expected_pending["contribution"] = contribution
    if pending is None:
        _retain_json(pending_path, expected_pending)
        pending = expected_pending
    elif pending != expected_pending:
        raise ValueError("persisted Opermem command differs from the bound contribution")
    transcript = fresh_transcript(transcripts)
    with OperationHost(binary, store, transcript) as host:
        committed = None
        if link["operation"] in noetic_opermem_decision.OPERATIONS + ("acting",):
            # Supersession can make its own predecessor export unavailable after commit.
            # An occupied native slot grants exact replay even when current admission changes.
            health = host.exchange("health", {})["payload"]
            committed = native_accepted_receipt(store, link["operation"], health,
                                                pending["payload"]["idempotency_key"])
        if committed is None:
            current_context = host.context(purpose)
            if current_context != link["context"]:
                committed = native_accepted_receipt(store, link["operation"], current_context,
                                                    pending["payload"]["idempotency_key"])
                if committed is None:
                    raise ValueError("Opermem context changed since actor invocation; uncommitted pending command not submitted")
        response = host.exchange(pending["kind"], pending["payload"])
        if committed is not None and (response["class"] != "idempotency-replay"
                or any(response["payload"].get(field) != value for field, value in committed.items())):
            raise ValueError("native response differs from committed receipt; Telos result remains pending")
    receipt_path.write_text(json.dumps({"contribution": contribution, "response": response,
                                        "submit_transcript": str(transcript)},
                                       indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _retain_receipt(run_dir)
    state = sync_telos(run_dir)
    print(json.dumps({"run": str(run_dir), "opermem": response["payload"],
                      "telos_error": state.get("telos_error")}))
    return 1 if state.get("telos_error") else 0


def sync_telos(run_dir: Path) -> dict:
    state = noetic_run.project(noetic_run.read_events(run_dir))
    association = state.get("telos")
    if association:
        try:
            _owned_gate(run_dir)
            if (run_dir / "opermem-receipt.json").exists():
                _retain_receipt(run_dir)
            noetic_telos.record_result(association["chain_id"], association["subgoal_id"], run_dir,
                                       association["db_path"], association["source"])
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
            noetic_run.record(run_dir, "telos.error", {"error": str(exc)})
        state = noetic_run.project(noetic_run.read_events(run_dir))
    return state


def run_task(args, *, on_prepared=None) -> int:
    os.environ.pop("USER_PROVIDED_PASSWORD", None)
    task = args.task.read_text(encoding="utf-8")
    qualification = None
    worker_controls = {}
    if args.qualification:
        if __package__:
            from scripts import noetic_genus
        else:
            import noetic_genus
        qualification = noetic_genus.validate_packet(
            json.loads(args.qualification.read_text(encoding="utf-8")), task, args.model)
        evidence = qualification["consumer_decision"]["selected_evidence"]
        if evidence is not None:
            worker_controls = dict(evidence["controls"])
    if args.thinking:
        if "reasoning_effort" in worker_controls and worker_controls["reasoning_effort"] != args.thinking:
            raise ValueError("explicit thinking differs from the qualified profile")
        worker_controls["reasoning_effort"] = args.thinking
    purpose = purpose_for(args.operation, args.parent_id, args.formulation_id,
                          warrant_id=getattr(args, "warrant_id", None),
                          condition_ids=getattr(args, "condition_ids", None),
                          judgment_ids=getattr(args, "judgment_ids", None),
                          practical_question_id=getattr(args, "practical_question_id", None),
                          option_id=getattr(args, "option_id", None), option_ids=getattr(args, "option_ids", None),
            evaluation_id=getattr(args, "evaluation_id", None), decision_id=getattr(args, "decision_id", None),
            judgment_basis_ids=getattr(args, "judgment_basis_ids", None),
            supersedes_decision_id=getattr(args, "supersedes_decision_id", None),
            predecessor_evaluation_id=getattr(args, "predecessor_evaluation_id", None),
            plan_id=getattr(args, "plan_id", None), step_id=getattr(args, "step_id", None),
            occasion_kind=getattr(args, "occasion_kind", None), occasion_id=getattr(args, "occasion_id", None))
    owned = _prepare_owned(args, task, worker_controls, purpose)
    try:
        if on_prepared is not None:
            if owned is None:
                raise ValueError("Preparation observation requires an explicit owned execution")
            from copy import deepcopy
            on_prepared(deepcopy(owned[1]))
        return _execute_task(args, task, qualification, worker_controls, purpose, owned)
    except Exception as exc:
        if owned:
            owned[0].preparation_failed(owned[1], str(exc) or type(exc).__name__)
        raise


def _execute_task(args, task, qualification, worker_controls, purpose, owned):
    if owned:
        owned[0].validate_binding(owned[1], current=True)
    args.store = private_dir(args.store)
    args.runs_dir = private_dir(args.runs_dir)
    transcripts = args.runs_dir / ".opermem-transcripts"
    context, context_transcript = retrieve(args.host, args.store, transcripts, purpose)
    validate_context(context, args.operation, args.parent_id, formulation_id=args.formulation_id,
        warrant_id=getattr(args, "warrant_id", None), condition_ids=getattr(args, "condition_ids", None),
        judgment_ids=getattr(args, "judgment_ids", None),
        practical_question_id=getattr(args, "practical_question_id", None),
        option_id=getattr(args, "option_id", None), option_ids=getattr(args, "option_ids", None),
            evaluation_id=getattr(args, "evaluation_id", None), decision_id=getattr(args, "decision_id", None),
            judgment_basis_ids=getattr(args, "judgment_basis_ids", None),
            supersedes_decision_id=getattr(args, "supersedes_decision_id", None),
            predecessor_evaluation_id=getattr(args, "predecessor_evaluation_id", None),
            plan_id=getattr(args, "plan_id", None), step_id=getattr(args, "step_id", None),
            occasion_kind=getattr(args, "occasion_kind", None), occasion_id=getattr(args, "occasion_id", None))
    checking = args.operation == "checking"
    acting = args.operation == "acting"
    run_id = owned[1]["run_id"] if owned else uuid.uuid4().hex if checking or acting else None
    captured = None
    manifest_sha256 = None
    if checking:
        if not args.inquiry or args.verify or args.checking_spec is None:
            raise ValueError("checking requires --inquiry --checking-spec and uses retained-evidence verification")
        if owned:
            owned[0].validate_binding(owned[1], current=True)
        captured = args.runs_dir / ".checking-evidence" / run_id
        capture = noetic_opermem_checking.capture(args.checking_spec, context, args.parent_id,
                                                 args.warrant_id, captured)
        if not capture["execution"]["performed"]:
            raise ValueError("checking command did not execute; incomplete capture retained")
        manifest_sha256 = noetic_opermem_checking.digest((captured / "manifest.json").read_bytes())
        args.verify = [sys.executable, str(Path(noetic_opermem_checking.__file__).resolve()),
                       "--evidence", str(captured.resolve()),
                       "--expected-manifest-sha256", manifest_sha256]
    observation_archive = None
    observation_hash = None
    observation = None
    if acting:
        if not args.inquiry or args.verify:
            raise ValueError("acting requires a separate read-only --inquiry and no verification command")
        source = getattr(args, "observed_run", None)
        archive = getattr(args, "observation_evidence", None)
        supplied_hash = getattr(args, "observation_manifest_sha256", None)
        if (source is None) == (archive is None) or (source is not None and supplied_hash is not None):
            raise ValueError("acting requires either --observed-run or --observation-evidence with its frozen manifest hash")
        observation_archive = private_dir(args.runs_dir / ".observation-evidence") / run_id
        if source is not None:
            observation = noetic_act_observation.capture(source, observation_archive, args.observed_step)
            observation_hash = noetic_act_observation.digest((observation_archive / "manifest.json").read_bytes())
        else:
            if supplied_hash is None:
                raise ValueError("archived observation requires --observation-manifest-sha256")
            if args.observed_step != "work":
                raise ValueError("--observed-step selects a source run; archive retains its own selected step")
            observation = noetic_opermem_acting.copy_archive(archive, observation_archive, supplied_hash)
            observation_hash = supplied_hash
        if not observation["selected"]["occurred"]:
            raise ValueError("launch failure evidence retained at " + str(observation_archive) + "; no occurred act to observe")
    observation_binding = None
    observation_binding_path = None
    if acting:
        observation_binding = noetic_opermem_acting.binding(context, args.plan_id, args.step_id,
                                                           observation_hash, observation, run_id)
        observation_binding_path = private_dir(args.runs_dir / ".observation-bindings") / (run_id + ".json")
        with observation_binding_path.open("x", encoding="utf-8") as stream:
            json.dump(observation_binding, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        observation_binding_path.chmod(0o600)
    fields = ('{"observed_act":"...","outcome":"...","deviation":"..."}' if acting else '{"selected_option_id":123,"rejected":[{"option_id":456,"reason":"..."}],"intention":{"kind":"active"}}'
              if args.operation == "decision" else '{"steps":[{"position":1,"action":"...","condition":"..."}]}'
              if args.operation == "planning" else '{"criteria":["..."],"trade_offs":["..."],"objections_and_responses":["..."],"value_scale":"..."}'
              if args.operation == "deliberation" else '{"polarity":{"kind":"yea"},"defeat_conditions":["..."],"rationale":"..."}'
              if args.operation == "judgment" else '{"conditions":["A: ...","B: ..."]}' if args.operation == "conditional-structure" else
              '{"question_kind":"how","text":"..."}' if args.operation == "question" else '{"text":"..."}')
    augmented = (
        "\n\nCurrent Opermem operation context follows as an intact JSON packet. "
        "Its standing, liveness, provenance, exclusions, and pinned cut are operative; "
        "do not present an insight or hypothesis as an affirmed judgment. "
        "The bootstrap experience is a local marker, not verified repository-source identity. "
        "Synthesis controls the external task; this packet grants no permission to act.\n"
        + json.dumps(context, ensure_ascii=False, sort_keys=True) + "\n\n"
        f"After the task, include exactly one line in your final report beginning {MARKER}"
        f"followed by a single-line JSON object shaped {fields}. "
        f"It is your proposed {args.operation} deposit, not a claim of affirmation.\n"
    )
    if owned:
        augmented += ("\nExplicit retained host source evidence and selected native occasion follow. "
                      "These sources are host evidence, not substantive bootstrap experience content. "
                      "The selected native occasion is store-qualified and grants no host action permission.\n"
                      + json.dumps({"host_sources": owned[1]["host_sources"],
                                    "occasion_selection": owned[1]["occasion_selection"]}, ensure_ascii=False, sort_keys=True) + "\n")
    if checking:
        augmented = (
            "\nCurrent whole native checking context; condition remains unchecked before deposit.\n"
            + json.dumps(context, ensure_ascii=False, sort_keys=True) + "\n"
            + f"HOST-CAPTURED evidence retained at {captured.resolve()}; manifest SHA-256 {manifest_sha256}. "
            "Read the exact specification, command byte logs, source snapshots and computed result. "
            "The host has already executed the selected checking command before this inquiry. "
            "Do not run commands or edit files. Explain actual bounded evidence and limitations. "
            "Your report supplies no fulfillment assertion or Opermem contribution; the host computes it. "
            "Review acceptance does not establish independent verifier, exhaustive dependencies, "
            "external act, semantic affirmation or cognitive value.\n")
    if args.operation == "conditional-structure":
        augmented += ("Conditions must be a nonempty array of trimmed nonempty strings in strictly "
                      "sorted unique order. They state what would need checking; they are unchecked.\n")
    if args.operation == "judgment":
        augmented += ("Choose polarity from the actual complete checked warrant and evidence. "
                      "Yea/nay use only kind; perchance additionally requires integer confidence_basis_points "
                      "from 0 through 10000. Defeat conditions must be nonempty, trimmed, sorted and unique. "
                      "Give the rationale for that polarity and its limits. Rationale is retained host report "
                      "metadata; only polarity and defeat conditions enter the native command. "
                      "Task verification and review acceptance do not affirm the proposition.\n")
    if args.operation == "practical-question":
        augmented += ("Address the entire explicit selected judgment set with every whole native residue. "
                      "The practical question creates no decision, plan or act authority.\n")
    if args.operation in noetic_opermem_practical.OPERATIONS:
        if args.operation != "practical-inquiry":
            augmented += ("This Noetic-owned envelope retains separate intact native export packets. "
                      "Primary operation roles and exclusions remain authoritative for that operation. "
                      "Supplemental practical-inquiry supplies question/judgment ancestry at the same native cut; "
                      "it does not promote excluded material into primary operation authority. ")
        augmented += ("Reason in the context of the entire retained judgment basis and native practical question. "
                      "Courses remain candidates; practical insight traces remain unverified. "
                      "Host-selected native IDs and versions are separate from your contribution content. "
                      "Deliberation compares every current option using its unique current native trace; "
                      "criteria, trade_offs, objections_and_responses require nonempty trimmed sorted unique arrays. "
                      "Describe the value_scale explicitly. An evaluation creates no decision, plan or act authority.\n")
    if args.operation in noetic_opermem_decision.OPERATIONS:
        augmented += ("Account for the whole retained native judgment basis. For decision, selected_option_id and "
                      "sorted rejected option reasons must account for exactly every evaluated option. "
                      "Issued intention is {kind:active} or {kind:abeyant,trigger:...}; a trigger is retained text, "
                      "not evidence that it occurred. For planning, the host derives the issued intention from the "
                      "decision; only an active or surfaced intention is applicable. Steps require contiguous "
                      "positions 1..N, trimmed native scalar action text and optional trimmed condition text. "
                      "Each text is bounded to 8192 UTF-8 bytes and each collection to 128 items. "
                      "Optional supersession retains a separate same-cut predecessor native export; its original "
                      "roles, standing and exclusions remain intact. Historical disclosure does not imply current "
                      "eligibility. No recursive ancestor payload admission is claimed. Native acceptance revalidates "
                      "semantic ancestry. A decision, intention, plan or condition grants no external act permission.\n")
    if acting:
        augmented += ("Observe the separately retained external occurrence; do not execute it again. "
                      "This run is a read-only observer followed by a separate reviewer. "
                      "Read the complete frozen archive at " + str(observation_archive.resolve()) + ". "
                      "Archive validation is historical; no current-source claim is inferred. "
                      "The host binds manifest_sha256 and selected finish_sequence separately from your native prose. "
                      "The plan/step correspondence is asserted retrospectively in this observation; "
                      "these records do not prove original dispatch under a plan, effort or ordinal mandate. "
                      "Preserve actual failed verification/work, timeout/interruption and any limits. "
                      "Successful observation review does not make the original act successful. "
                      "Preserve observed_act/outcome/deviation exactly, including LF and boundary whitespace. "
                      "Each artifact is nonblank and <=24576 UTF-8 bytes, total<=32768; every Unicode control "
                      "character other than LF is forbidden. Omit deviation for an exact planned-action text match; "
                      "a mismatch requires a substantive deviation. Never copy planned text to evade that rule. "
                      "Native acceptance creates observation residue, not execution permission or plan completion.\n"
                      + json.dumps({"observation_binding": observation_binding, "retained_manifest": observation}, ensure_ascii=False, sort_keys=True) + "\n")
    if qualification is not None:
        augmented += ("\nOriginal worker model-choice evidence follows. Qualifications are provisional; "
                      "this packet neither invokes a model nor proves provider availability. "
                      "The consumer's explicit choice and any qualification gap remain separate.\n"
                      + json.dumps(qualification, ensure_ascii=False, sort_keys=True) + "\n")
    def native_link(directory):
        link = {"version": 1, "operation": args.operation, "parent_id": args.parent_id,
                "formulation_id": args.formulation_id,
                "store": str(args.store.resolve()), "host": str(args.host.resolve()),
                "context_transcript": str(context_transcript), "context": context,
                "repository_workspace": str(args.workspace.resolve()),
                "worker_model": args.model, "review_model": args.review_model or args.model,
                "worker_controls": worker_controls,
                "worker_qualification": "genus-selection.json" if qualification is not None else None,
                "worker_session": json.loads((directory / "work.json").read_text())["session_id"]
                if (directory / "work.json").exists() else None}
        if checking:
            link.update(warrant_id=args.warrant_id, checking_manifest_sha256=manifest_sha256)
        if args.operation in CONTEXT_OPERATIONS:
            link.update(warrant_id=getattr(args, "warrant_id", None),
                        condition_ids=getattr(args, "condition_ids", None),
                        judgment_ids=getattr(args, "judgment_ids", None),
                        practical_question_id=getattr(args, "practical_question_id", None),
                        option_id=getattr(args, "option_id", None), option_ids=getattr(args, "option_ids", None),
                evaluation_id=getattr(args, "evaluation_id", None), decision_id=getattr(args, "decision_id", None),
                judgment_basis_ids=getattr(args, "judgment_basis_ids", None),
                supersedes_decision_id=getattr(args, "supersedes_decision_id", None),
                predecessor_evaluation_id=getattr(args, "predecessor_evaluation_id", None),
                plan_id=getattr(args, "plan_id", None), step_id=getattr(args, "step_id", None),
                occasion_kind=getattr(args, "occasion_kind", None), occasion_id=getattr(args, "occasion_id", None))
        if args.operation == "question":
            link.update(occasion_kind=getattr(args, "occasion_kind", None), occasion_id=getattr(args, "occasion_id", None))
        if acting:
            link.update(observation_manifest_sha256=observation_hash,
                        observation_source_run=observation["source_run_dir"],
                        observation_selected=observation["selected"], observation_evidence_mode="archival",
                        observation_correlation="retrospective-selected-plan-step; original dispatch unestablished")
        if owned:
            binding = owned[1]
            link.update(version=2, worker_session=None, owned_execution={key: binding[key] for key in
                ("namespace_path", "namespace", "execution_id", "preparation_path")})
        return link

    lifecycle = None
    if owned:
        archives = []
        if checking:
            archives.append((captured, "checking-evidence", None))
        if acting:
            archives.append((observation_archive, "observation-evidence", observation_hash))
        lifecycle = _OwnedNativeLifecycle(*owned, native_link(Path(owned[1]["run_dir"])), archives, qualification)
        if acting:
            original_created = lifecycle.run_created
            def created_with_observation(run_dir):
                original_created(run_dir)
                _retain_json(run_dir / "observation-binding.json", observation_binding)
            lifecycle.run_created = created_with_observation
    run_dir, state = noetic_develop.develop(
        task, args.workspace, args.runs_dir, args.verify, client=args.client,
        model=args.model, review_model=args.review_model, timeout=args.timeout,
        inquiry=args.inquiry, run_id=run_id,
        telos_chain=args.telos_chain, telos_db=args.telos_db, telos_source=args.telos_source,
        defer_telos_result=True, task_context=augmented, worker_controls=worker_controls,
        read_context_dirs=(captured.resolve(),) if checking else (observation_archive.resolve(),) if acting else (),
        lifecycle=lifecycle,
    )
    if checking and not owned:
        shutil.copytree(captured, run_dir / "checking-evidence")
    observation_copy_error = None
    if acting and not owned:
        shutil.copyfile(observation_binding_path, run_dir / "observation-binding.json")
        (run_dir / "observation-binding.json").chmod(0o600)
        try:
            noetic_opermem_acting.copy_archive(observation_archive, run_dir / "observation-evidence", observation_hash)
        except (OSError, ValueError) as exc:
            observation_copy_error = str(exc)
    link = native_link(run_dir)
    if owned:
        _retain_json(run_dir / "opermem-link.json", link)
    else:
        (run_dir / "opermem-link.json").write_text(json.dumps(link, indent=2, sort_keys=True) + "\n")
    if qualification is not None:
        (run_dir / "genus-selection.json").write_text(
            json.dumps(qualification, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if state["state"] != "accepted":
        state = sync_telos(run_dir)
        print(json.dumps({"run": str(run_dir), "state": state["state"],
                          "opermem": "not-submitted"}))
        return 1
    try:
        _owned_gate(run_dir, participants=True)
        if observation_copy_error is not None:
            raise ValueError("frozen observation archive unavailable: " + observation_copy_error)
        contribution = (noetic_opermem_checking.contribution(
            run_dir / "checking-evidence", context, args.parent_id, args.warrant_id, manifest_sha256)
            if checking else contribution_from_report((run_dir / "work.md").read_text(), args.operation))
        if acting:
            contribution = noetic_opermem_acting.bind(contribution, run_dir / "observation-evidence", observation_hash)
        response, submit_transcript = submit(
            args.host, args.store, transcripts, args.operation, args.parent_id, contribution,
            f"noetic-{run_dir.name}-{args.operation}", context,
            pending_path=run_dir / "opermem-pending.json", formulation_id=args.formulation_id,
            warrant_id=getattr(args, "warrant_id", None),
            checking_evidence=run_dir / "checking-evidence" if checking else None,
            checking_manifest_sha256=manifest_sha256,
            condition_ids=getattr(args, "condition_ids", None),
            judgment_ids=getattr(args, "judgment_ids", None),
            practical_question_id=getattr(args, "practical_question_id", None),
            option_id=getattr(args, "option_id", None), option_ids=getattr(args, "option_ids", None),
            evaluation_id=getattr(args, "evaluation_id", None), decision_id=getattr(args, "decision_id", None),
            judgment_basis_ids=getattr(args, "judgment_basis_ids", None),
            supersedes_decision_id=getattr(args, "supersedes_decision_id", None),
            predecessor_evaluation_id=getattr(args, "predecessor_evaluation_id", None),
            plan_id=getattr(args, "plan_id", None), step_id=getattr(args, "step_id", None),
            occasion_kind=getattr(args, "occasion_kind", None), occasion_id=getattr(args, "occasion_id", None),
            observation_evidence=run_dir / "observation-evidence" if acting else None,
            observation_manifest_sha256=observation_hash)
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        state = sync_telos(run_dir)
        print(json.dumps({"run": str(run_dir), "state": state["state"], "opermem": "not-submitted",
                          "submission_error": str(exc), "telos_error": state.get("telos_error")}))
        return 1
    (run_dir / "opermem-receipt.json").write_text(json.dumps({
        "contribution": contribution, "response": response,
        "submit_transcript": str(submit_transcript)}, indent=2, sort_keys=True) + "\n")
    _retain_receipt(run_dir)
    state = sync_telos(run_dir)
    print(json.dumps({"run": str(run_dir), "state": state["state"],
                      "opermem": response["payload"], "telos_error": state.get("telos_error")}))
    return 1 if state.get("telos_error") else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", type=Path)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--runs-dir", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    instance = commands.add_parser("create-instance")
    instance.add_argument("request", type=Path)
    registration = commands.add_parser("bind-store")
    registration.add_argument("--namespace-path", type=Path, required=True)
    registration.add_argument("--effort-root", required=True)
    registration.add_argument("--command-id", required=True)
    inspection = commands.add_parser("inspect")
    inspection.add_argument("--namespace-path", type=Path, required=True)
    inspection.add_argument("--effort-root", required=True)
    seed = commands.add_parser("seed-question")
    seed.add_argument("--text", required=True)
    seed.add_argument("--question-kind", choices=("what", "why", "how"), default="how")
    seed.add_argument("--key", required=True)
    seed.add_argument("--occasion-id", type=int)
    seed.add_argument("--occasion-kind", choices=("experience", "outcome-as-experience"))
    run = commands.add_parser("run")
    run.add_argument("task", type=Path)
    run.add_argument("--workspace", type=Path, required=True)
    run.add_argument("--operation", choices=tuple(KINDS), required=True)
    run.add_argument("--parent-id", type=int)
    run.add_argument("--formulation-id", type=int, help="additional formulation anchor for conditional-structure")
    run.add_argument("--warrant-id", type=int, help="explicit warrant anchor for checking or judgment")
    run.add_argument("--condition-ids", type=int, nargs="+", help="entire sorted native warrant condition set")
    run.add_argument("--judgment-ids", type=int, nargs="+", help="complete sorted selected native judgment basis")
    run.add_argument("--practical-question-id", type=int)
    run.add_argument("--option-id", type=int)
    run.add_argument("--option-ids", type=int, nargs="+")
    run.add_argument("--evaluation-id", type=int)
    run.add_argument("--decision-id", type=int)
    run.add_argument("--judgment-basis-ids", type=int, nargs="+")
    run.add_argument("--supersedes-decision-id", type=int)
    run.add_argument("--predecessor-evaluation-id", type=int)
    run.add_argument("--plan-id", type=int)
    run.add_argument("--step-id", type=int)
    run.add_argument("--occasion-id", type=int)
    run.add_argument("--occasion-kind", choices=("experience", "outcome-as-experience"))
    run.add_argument("--checking-spec", type=Path, help="closed exact checking specification")
    run.add_argument("--observed-run", type=Path)
    run.add_argument("--observed-step", choices=("work", "verify", "review"), default="work")
    run.add_argument("--observation-evidence", type=Path)
    run.add_argument("--observation-manifest-sha256")
    run.add_argument("--client", choices=("pi", "opencode"), default="pi")
    run.add_argument("--model")
    run.add_argument("--thinking", choices=("off", "minimal", "low", "medium", "high", "xhigh", "max"))
    run.add_argument("--review-model")
    run.add_argument("--timeout", type=float, default=900)
    run.add_argument("--inquiry", action="store_true")
    run.add_argument("--telos-chain")
    run.add_argument("--telos-db", type=Path)
    run.add_argument("--telos-source", type=Path)
    run.add_argument("--qualification", type=Path, help="original schema-6 worker qualification packet")
    run.add_argument("--scope-request", type=Path)
    run.add_argument("--store-ref", type=Path)
    run.add_argument("--purpose-ref", type=Path)
    run.add_argument("--purpose-config", type=Path)
    run.add_argument("--source", type=Path, action="append", default=[])
    run.add_argument("--verify", nargs=argparse.REMAINDER)
    context_cmd = commands.add_parser("context")
    context_cmd.add_argument("--operation", choices=tuple(KINDS), required=True)
    context_cmd.add_argument("--parent-id", type=int)
    context_cmd.add_argument("--formulation-id", type=int, help="additional formulation anchor for conditional-structure")
    context_cmd.add_argument("--warrant-id", type=int)
    context_cmd.add_argument("--condition-ids", type=int, nargs="+")
    context_cmd.add_argument("--judgment-ids", type=int, nargs="+")
    context_cmd.add_argument("--practical-question-id", type=int)
    context_cmd.add_argument("--option-id", type=int)
    context_cmd.add_argument("--option-ids", type=int, nargs="+")
    context_cmd.add_argument("--evaluation-id", type=int)
    context_cmd.add_argument("--decision-id", type=int)
    context_cmd.add_argument("--judgment-basis-ids", type=int, nargs="+")
    context_cmd.add_argument("--supersedes-decision-id", type=int)
    context_cmd.add_argument("--predecessor-evaluation-id", type=int)
    context_cmd.add_argument("--plan-id", type=int)
    context_cmd.add_argument("--step-id", type=int)
    context_cmd.add_argument("--occasion-id", type=int)
    context_cmd.add_argument("--occasion-kind", choices=("experience", "outcome-as-experience"))
    resume = commands.add_parser("resume")
    resume.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)
    os.environ.pop("USER_PROVIDED_PASSWORD", None)
    if args.command == "create-instance":
        request = _json_input(args.request)
        adapter = _scope_adapter(request.pop("namespace_path"))
        print(json.dumps(adapter.create_instance(**request), sort_keys=True))
        return 0
    if args.command == "inspect":
        print(json.dumps(_scope_adapter(args.namespace_path).inspect_preparations(effort_root=args.effort_root), sort_keys=True))
        return 0
    if args.host is None or args.store is None:
        parser.error("Native commands require explicit --host and --store")
    args.host = args.host.resolve(strict=True)
    args.store = args.store.resolve()
    if args.command == "bind-store":
        print(json.dumps(_scope_adapter(args.namespace_path).bind_store(command_id=args.command_id,
            effort_root=args.effort_root, store_path=args.store, host=args.host), sort_keys=True))
        return 0
    if args.runs_dir is None:
        parser.error("Native execution requires explicit --runs-dir")
    args.runs_dir = args.runs_dir.resolve()
    if args.command not in ("run", "resume"):
        args.store = private_dir(args.store)
        args.runs_dir = private_dir(args.runs_dir)
    if args.command == "seed-question":
        response, transcript = submit(args.host, args.store, args.runs_dir / ".opermem-transcripts",
                                      "question", None,
                                      {"question_kind": args.question_kind, "text": args.text},
                                      args.key, occasion_kind=args.occasion_kind, occasion_id=args.occasion_id)
        print(json.dumps({"response": response, "transcript": str(transcript)}))
        return 0
    if args.command == "context":
        context, transcript = retrieve(args.host, args.store,
                                       args.runs_dir / ".opermem-transcripts",
                                       purpose_for(args.operation, args.parent_id, args.formulation_id,
                                                   warrant_id=args.warrant_id,
                                                   condition_ids=args.condition_ids, judgment_ids=args.judgment_ids,
                                                   practical_question_id=args.practical_question_id,
                                                   option_id=args.option_id, option_ids=args.option_ids,
                             evaluation_id=args.evaluation_id, decision_id=args.decision_id,
                             judgment_basis_ids=args.judgment_basis_ids,
                             supersedes_decision_id=args.supersedes_decision_id,
                             predecessor_evaluation_id=args.predecessor_evaluation_id,
                             plan_id=args.plan_id, step_id=args.step_id, occasion_kind=args.occasion_kind, occasion_id=args.occasion_id))
        if args.operation in CONTEXT_OPERATIONS:
            validate_context(context, args.operation, args.parent_id, warrant_id=args.warrant_id,
                             condition_ids=args.condition_ids, judgment_ids=args.judgment_ids,
                             practical_question_id=args.practical_question_id,
                             option_id=args.option_id, option_ids=args.option_ids,
                             evaluation_id=args.evaluation_id, decision_id=args.decision_id,
                             judgment_basis_ids=args.judgment_basis_ids,
                             supersedes_decision_id=args.supersedes_decision_id,
                             predecessor_evaluation_id=args.predecessor_evaluation_id,
                             plan_id=args.plan_id, step_id=args.step_id, occasion_kind=args.occasion_kind, occasion_id=args.occasion_id)
        print(json.dumps({"context": context, "transcript": str(transcript)}))
        return 0
    if args.command == "resume":
        return resume_run(args.run_dir, args.host, args.store,
                          args.runs_dir / ".opermem-transcripts")
    if not args.inquiry and not args.verify:
        parser.error("development runs require --verify COMMAND...")
    if args.operation == "checking" and (not args.inquiry or args.verify or not args.checking_spec):
        parser.error("checking requires --inquiry --checking-spec and no --verify override")
    if args.operation != "checking" and args.checking_spec:
        parser.error("--checking-spec applies only to checking")
    if args.operation != "acting" and (args.observed_run or args.observation_evidence or args.observation_manifest_sha256 or args.observed_step != "work"):
        parser.error("observation evidence selectors apply only to acting")
    return run_task(args)


if __name__ == "__main__":
    raise SystemExit(main())
