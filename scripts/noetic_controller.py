"""Persisted, serial role-activation state machine. No model or process execution.

The bundled tables select fixed guards and actions, not executable expressions.
See docs/executive-controller.md for the adapter protocol and result contracts.
"""

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3

if __package__:
    from scripts.noetic_storage import create_private_sqlite
else:
    from noetic_storage import create_private_sqlite


PATTERN_DIR = Path(__file__).with_name("patterns")
QA_FRAMING = (
    "Use reasoned, critical, constructive, non-perfectionistic QA. Independently "
    "check concrete material defects and proportionate risks against the stated "
    "acceptance criteria. Give practical remediation; do not expand into "
    "speculative hardening or delegate downstream QA."
)


class ControllerError(ValueError):
    """An invalid request; no transaction was accepted."""


class ConflictError(ControllerError):
    """Stale state, conflicting command delivery, or wrong activation lifecycle."""


class InvalidResultError(ControllerError):
    """A role result does not satisfy its structural contract."""


def _json(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ControllerError("Expected finite JSON data") from exc


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _pattern(pattern):
    if not isinstance(pattern, dict):
        pattern = json.loads(Path(pattern).read_text(encoding="utf-8"))
    pattern = json.loads(_json(pattern))
    kind = pattern.get("kind")
    if kind not in ("verified_sequence", "recurrent_operations"):
        raise ControllerError("Unsupported pattern kind")
    # This is deliberately a two-kind kernel, not a generic graph interpreter.
    canonical = json.loads((PATTERN_DIR / (
        "development.json" if kind == "verified_sequence" else "cognition.json"
    )).read_text(encoding="utf-8"))
    if pattern.get("transitions") != canonical["transitions"]:
        raise ControllerError("Pattern must use the fixed transition table for its kind")
    phases = pattern.get("phases")
    if not isinstance(phases, list) or len(phases) != 4:
        raise ControllerError("Pattern must declare four phases")
    prefix = "accepted" if kind == "verified_sequence" else "effective"
    prior = {}
    for phase, reference in zip(phases, canonical["phases"]):
        if not isinstance(phase, dict) or phase.get("id") != reference["id"]:
            raise ControllerError("Pattern phase order does not match its kind")
        if not _text(phase.get("role")) or not _text(phase.get("output_type")):
            raise ControllerError("Each phase needs a role and output_type")
        fields = phase.get("content_fields")
        if not isinstance(fields, dict) or not fields or any(
            not _text(key) or value not in ("string", "array", "object")
            for key, value in fields.items()
        ):
            raise ControllerError("Invalid content_fields")
        if any(fields.get(key) != value for key, value in reference["content_fields"].items()):
            raise ControllerError("Required stage content fields cannot be removed")
        required = phase.get("required_inputs")
        if not isinstance(required, dict) or required.get("external.purpose") != "external.purpose":
            raise ControllerError("Every phase requires the external purpose")
        for slot, artifact_type in required.items():
            if not _text(slot) or not _text(artifact_type):
                raise ControllerError("Invalid required input binding")
            if slot.startswith("external."):
                if artifact_type != slot:
                    raise ControllerError("External input types match their slots")
            elif prior.get(slot) != artifact_type:
                raise ControllerError("Required artifacts must refer to typed prior phases")
        if any(required.get(slot) != artifact_type for slot, artifact_type in prior.items()):
            raise ControllerError("Every prior phase must be bound explicitly")
        if not isinstance(phase.get("criteria"), list) or not phase["criteria"] or not all(
            _text(item) for item in phase["criteria"]
        ):
            raise ControllerError("Each phase needs explicit criteria")
        if kind == "recurrent_operations" and phase.get("return_targets") != reference["return_targets"]:
            raise ControllerError("Return targets must be the earlier operations")
        prior[f"{prefix}.{phase['id']}"] = phase["output_type"]
    return pattern


@contextmanager
def _transaction(store_path, create=False):
    if create:
        create_private_sqlite(store_path)
    path = Path(store_path).resolve()
    connection = sqlite3.connect(str(path) if create else path.as_uri() + "?mode=rw", uri=not create)
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            if create:
                connection.execute("CREATE TABLE IF NOT EXISTS run (id INTEGER PRIMARY KEY CHECK (id = 1), state TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS commands (command_id TEXT PRIMARY KEY, request TEXT NOT NULL, response TEXT NOT NULL)")
            yield connection
    finally:
        connection.close()


def _load(connection):
    row = connection.execute("SELECT state FROM run WHERE id = 1").fetchone()
    if row is None:
        raise ControllerError("Store has no run")
    return json.loads(row[0])


def _save(connection, state):
    connection.execute("UPDATE run SET state = ? WHERE id = 1", (_json(state),))
    return state


def _event(state, kind, **data):
    state["events"].append({
        "id": f"event-{len(state['events'])}", "version": state["version"],
        "kind": kind, "data": data,
    })


def _phase(state):
    return state["pattern"]["phases"][state["phase_index"]]


def _artifact(state, artifact_type, content, activation=None, partial=False, bindings=None):
    artifact_id = f"artifact-{len(state['artifacts'])}"
    bindings = dict(bindings if bindings is not None else (activation["input_bindings"] if activation else {}))
    state["artifacts"][artifact_id] = {
        "id": artifact_id, "type": artifact_type, "content": content,
        "digest": hashlib.sha256(_json(content).encode("utf-8")).hexdigest(),
        "produced_by": activation["actor_id"] if activation else None,
        "activation_id": activation["id"] if activation else None,
        "phase": activation["phase"] if activation else None,
        "generation": activation["generation"] if activation else None,
        "visit": activation["visit"] if activation else None,
        "input_bindings": bindings, "derived_from": list(dict.fromkeys(bindings.values())),
        "partial": partial, "origin": "role" if activation else "external",
    }
    _event(state, "artifact.recorded", artifact_id=artifact_id, partial=partial)
    return artifact_id


def _contract(state, activation):
    phase = _phase(state)
    if activation["mode"] == "review":
        return {
            "type": "object", "required": ["subject_artifact_id", "report", "findings"],
            "properties": {
                "subject_artifact_id": {"const": state["subject_artifact_id"]},
                "verdict": {"enum": ["pass", "fail"]},
                "outcome": {"enum": ["pass", "fail"]},
                "report": {"type": "string", "minLength": 1},
                "findings": {"type": "array", "items": {
                    "type": "object", "required": ["description", "blocking"],
                    "properties": {"description": {"type": "string", "minLength": 1}, "blocking": {"type": "boolean"}},
                }},
            },
            "anyOf": [{"required": ["verdict"]}, {"required": ["outcome"]}],
            "additionalProperties": False,
            "description": "Verdict/outcome must agree if both supplied. Blocking findings forbid pass. " + QA_FRAMING,
        }
    content = {
        "type": "object", "required": list(phase["content_fields"]),
        "properties": {name: {"type": kind} for name, kind in phase["content_fields"].items()},
    }
    outcome = "produced" if activation["mode"] == "produce" else (
        "complete" if state["phase_index"] == 3 else "advance"
    )
    ordinary = {
        "type": "object", "required": ["outcome", "content"],
        "properties": {"outcome": {"const": outcome}, "content": content},
        "additionalProperties": False,
    }
    if activation["mode"] != "operate" or not phase["return_targets"]:
        return ordinary
    partial = dict(content)
    partial.pop("required")
    partial["minProperties"] = 1
    return {"oneOf": [ordinary, {
        "type": "object", "required": ["outcome", "content", "target", "reason", "question"],
        "properties": {
            "outcome": {"const": "return"}, "content": partial,
            "target": {"enum": phase["return_targets"]},
            "reason": {"type": "string", "minLength": 1},
            "question": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
        "description": "Partial work only; no completed judgment is required. Return budget is enforced by the controller.",
    }]}


def result_contract(state: dict) -> dict | None:
    """Return a detached JSON Schema for the reserved role, or None at termination."""
    activation_id = state["current_activation"]
    if activation_id is None:
        return None
    return json.loads(_json(state["activations"][activation_id]["result_contract"]))


def _allocate(state, mode):
    if state["current_activation"] is not None:
        raise ControllerError("Cannot allocate over a current activation")
    phase = _phase(state)
    bindings = {}
    for slot, artifact_type in phase["required_inputs"].items():
        artifact_id = state["slots"].get(slot)
        artifact = state["artifacts"].get(artifact_id)
        if artifact is None or artifact["type"] != artifact_type or artifact["partial"]:
            raise ControllerError(f"Missing or mistyped required artifact: {slot}")
        bindings[slot] = artifact_id
    if state["subject_artifact_id"] is not None:
        bindings["subject"] = state["subject_artifact_id"]
    if state["review_artifact_id"] is not None:
        bindings["feedback.qa"] = state["review_artifact_id"]
    if state["feedback"]:
        bindings["feedback.return"] = state["feedback"][-1]
    number = len(state["actors"])
    actor_id, activation_id, ordinal = f"actor-{number}", f"activation-{number}", f"0.{number}"
    role = "independent_qa" if mode == "review" else phase["role"]
    activation = {
        "id": activation_id, "actor_id": actor_id, "ordinal": ordinal, "role": role,
        "phase": phase["id"], "generation": state["generation"],
        "visit": state["visits"][phase["id"]], "mode": mode, "status": "ready",
        "session_ref": None, "input_bindings": bindings, "criteria": phase["criteria"],
        "output_type": "qa.review" if mode == "review" else phase["output_type"],
    }
    if mode == "review":
        activation["qa_framing"] = QA_FRAMING
    activation["result_contract"] = _contract(state, activation)
    state["actors"][actor_id] = {
        "id": actor_id, "ordinal": ordinal, "role": role,
        "activation_id": activation_id, "status": "ready", "session_ref": None,
    }
    state["activations"][activation_id] = activation
    state["current_activation"] = activation_id
    _event(state, "activation.ready", activation_id=activation_id, actor_id=actor_id, phase=phase["id"], mode=mode)


def _guard(state, name):
    return {
        "always": True,
        "has_next": state["phase_index"] < 3,
        "is_last": state["phase_index"] == 3,
        "can_remediate": state["generation"] < state["max_remediations"],
        "remediations_exhausted": state["generation"] >= state["max_remediations"],
        "can_return": state["returns_used"] < state["max_returns"],
        "returns_exhausted": state["returns_used"] >= state["max_returns"],
    }[name]


def _transition(state, event, result=None, artifact_id=None):
    rows = [row for row in state["pattern"]["transitions"]
            if row["from"] == state["machine_state"] and row["on"] == event and _guard(state, row["guard"])]
    if len(rows) != 1:
        raise InvalidResultError(f"No unique transition for {state['machine_state']} / {event}")
    row = rows[0]
    phase = _phase(state)
    state["machine_state"] = row["to"]
    _event(state, "transition", phase=phase["id"], **row)
    action = row["action"]
    if action in ("allocate_producer", "allocate_operator"):
        _allocate(state, "produce" if action == "allocate_producer" else "operate")
    elif action == "allocate_qa":
        state["subject_artifact_id"] = artifact_id
        _allocate(state, "review")
    elif action == "remediate":
        state["generation"] += 1
        _allocate(state, "produce")
    elif action in ("accept_next", "accept_complete", "advance", "complete"):
        verified = action.startswith("accept_")
        slot = f"{'accepted' if verified else 'effective'}.{phase['id']}"
        state["slots"][slot] = state["subject_artifact_id"] if verified else artifact_id
        _event(state, "slot.bound", slot=slot, artifact_id=state["slots"][slot])
        state["subject_artifact_id"] = None
        state["review_artifact_id"] = None
        if action in ("accept_complete", "complete"):
            state["status"] = "completed"
            _event(state, "run.completed")
        else:
            state["phase_index"] += 1
            state["generation"] = 0
            state["visits"][_phase(state)["id"]] += 1
    elif action == "return":
        target_index = next(i for i, item in enumerate(state["pattern"]["phases"]) if item["id"] == result["target"])
        invalidated = {}
        for item in state["pattern"]["phases"][target_index:]:
            slot = f"effective.{item['id']}"
            if slot in state["slots"]:
                invalidated[slot] = state["slots"].pop(slot)
        state["returns_used"] += 1
        state["phase_index"] = target_index
        state["visits"][result["target"]] += 1
        _event(state, "cognition.returned", target=result["target"], feedback_artifact_id=state["feedback"][-1], invalidated=invalidated)
    elif action in ("block_return", "block_remediation"):
        state["status"] = "blocked"
        state["reason"] = "return_budget_exhausted" if action == "block_return" else f"remediations_exhausted:{phase['id']}"
        _event(state, "run.blocked", reason=state["reason"])
    else:
        raise ControllerError(f"Unknown fixed action: {action}")
    if state["machine_state"] == "pending":
        _transition(state, "activate")


def start_run(store_path: Path, pattern: dict | str | Path, purpose: str, workspace: Path,
              max_remediations: int = 1, max_returns: int = 1, inputs: dict | None = None) -> dict:
    """Create one run and reserve its first activation. The store parent must exist."""
    pattern = _pattern(pattern)
    if not _text(purpose):
        raise ControllerError("purpose must be nonempty text")
    if any(type(value) is not int or value < 0 for value in (max_remediations, max_returns)):
        raise ControllerError("Budgets must be nonnegative integers")
    if inputs is None:
        inputs = {}
    if not isinstance(inputs, dict) or "purpose" in inputs or not all(_text(key) for key in inputs):
        raise ControllerError("inputs must map external names to JSON data; purpose is a separate argument")
    inputs = json.loads(_json({"sources": [], **inputs}))
    for phase in pattern["phases"]:
        for slot in phase["required_inputs"]:
            if slot.startswith("external.") and slot != "external.purpose" and slot[9:] not in inputs:
                raise ControllerError(f"Missing external input: {slot}")
    workspace = Path(workspace).resolve()
    if not workspace.is_dir():
        raise ControllerError("workspace must be an existing directory")
    state = {
        "schema_version": 1, "version": 1, "status": "active", "reason": None,
        "pattern": pattern, "purpose": purpose, "workspace": str(workspace),
        "max_remediations": max_remediations, "max_returns": max_returns, "returns_used": 0,
        "phase_index": 0, "generation": 0, "machine_state": "pending",
        "visits": {phase["id"]: (1 if i == 0 else 0) for i, phase in enumerate(pattern["phases"])},
        "current_activation": None, "actors": {}, "activations": {}, "artifacts": {},
        "slots": {}, "subject_artifact_id": None, "review_artifact_id": None,
        "feedback": [], "events": [], "last_receipt": None,
    }
    with _transaction(store_path, create=True) as connection:
        if connection.execute("SELECT 1 FROM run WHERE id = 1").fetchone():
            raise ConflictError("Store already contains a run")
        _event(state, "run.started", pattern=pattern.get("name", pattern["kind"]))
        for name, value in {"purpose": purpose, **inputs}.items():
            slot = f"external.{name}"
            state["slots"][slot] = _artifact(state, slot, value)
        _transition(state, "activate")
        connection.execute("INSERT INTO run (id, state) VALUES (1, ?)", (_json(state),))
    return state


def inspect_run(store_path: Path) -> dict:
    """Read persisted state without creating or changing the store."""
    connection = sqlite3.connect(Path(store_path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return _load(connection)
    finally:
        connection.close()


def _current(state, activation_id, expected_version, statuses):
    if type(expected_version) is not int or state["version"] != expected_version:
        raise ConflictError("Stale expected_version")
    if state["status"] != "active" or state["current_activation"] != activation_id:
        raise ConflictError("Not the current active activation")
    activation = state["activations"][activation_id]
    if activation["status"] not in statuses:
        raise ConflictError(f"Activation is {activation['status']}; expected {statuses}")
    return activation


def begin_activation(store_path: Path, activation_id: str, expected_version: int) -> dict:
    """Atomically change the reserved activation and actor from ready to running."""
    with _transaction(store_path) as connection:
        state = _load(connection)
        activation = _current(state, activation_id, expected_version, ("ready",))
        state["version"] += 1
        activation["status"] = state["actors"][activation["actor_id"]]["status"] = "running"
        _event(state, "activation.running", activation_id=activation_id)
        return _save(connection, state)


def _validate_result(state, activation, result):
    if not isinstance(result, dict):
        raise InvalidResultError("Result must be a JSON object")
    phase = _phase(state)
    outcome = result.get("outcome")
    if activation["mode"] == "review":
        verdict = result.get("verdict", outcome)
        if verdict not in ("pass", "fail") or ("outcome" in result and outcome != verdict):
            raise InvalidResultError("QA verdict/outcome must be pass or fail and agree")
        if set(result) - {"subject_artifact_id", "verdict", "outcome", "report", "findings"}:
            raise InvalidResultError("Unexpected QA result field")
        if result.get("subject_artifact_id") != state["subject_artifact_id"]:
            raise InvalidResultError("QA must name the current subject_artifact_id")
        if not _text(result.get("report")) or not isinstance(result.get("findings"), list):
            raise InvalidResultError("QA requires a report and findings array")
        for finding in result["findings"]:
            if not isinstance(finding, dict) or not _text(finding.get("description")) or type(finding.get("blocking")) is not bool:
                raise InvalidResultError("Each finding requires description and boolean blocking")
            if verdict == "pass" and finding["blocking"]:
                raise InvalidResultError("Blocking findings forbid pass")
        return verdict
    returning = activation["mode"] == "operate" and outcome == "return"
    expected = "produced" if activation["mode"] == "produce" else ("complete" if state["phase_index"] == 3 else "advance")
    if not returning and outcome != expected:
        raise InvalidResultError(f"Expected outcome {expected}")
    allowed = {"outcome", "content", "target", "reason", "question"} if returning else {"outcome", "content"}
    if set(result) - allowed:
        raise InvalidResultError("Unexpected result field; identity comes from the runtime")
    if returning:
        if result.get("target") not in phase["return_targets"]:
            raise InvalidResultError("Invalid return target")
        if not _text(result.get("reason")) or not _text(result.get("question")):
            raise InvalidResultError("A return requires reason and question")
    content = result.get("content")
    if not isinstance(content, dict) or (returning and not content):
        raise InvalidResultError("content must be an object (nonempty for partial returns)")
    types = {"string": str, "array": list, "object": dict}
    for field, kind in phase["content_fields"].items():
        if field not in content and returning:
            continue
        if field not in content or not isinstance(content[field], types[kind]):
            raise InvalidResultError(f"content.{field} must be {kind}")
    return outcome


def submit_result(store_path: Path, activation_id: str, expected_version: int, result: dict,
                  session_ref: str, command_id: str) -> dict:
    """Accept a runtime result once; exact command redelivery returns its original state."""
    if not _text(command_id) or not _text(session_ref):
        raise ControllerError("command_id and runtime session_ref must be nonempty text")
    request = _json({"activation_id": activation_id, "expected_version": expected_version,
                     "result": result, "session_ref": session_ref})
    result = json.loads(request)["result"]
    with _transaction(store_path) as connection:
        receipt = connection.execute("SELECT request, response FROM commands WHERE command_id = ?", (command_id,)).fetchone()
        if receipt is not None:
            if receipt[0] != request:
                raise ConflictError("command_id already accepted with a different request")
            return json.loads(receipt[1])
        state = _load(connection)
        activation = _current(state, activation_id, expected_version, ("running",))
        outcome = _validate_result(state, activation, result)
        if any(actor["session_ref"] == session_ref for actor in state["actors"].values()):
            raise ConflictError("Each actor requires a fresh runtime session; QA cannot reuse another actor's session")
        state["version"] += 1
        actor = state["actors"][activation["actor_id"]]
        actor["session_ref"] = activation["session_ref"] = session_ref
        actor["status"] = activation["status"] = "retired"
        state["current_activation"] = None
        _event(state, "activation.retired", activation_id=activation_id, session_ref=session_ref, outcome=outcome)
        content = result if activation["mode"] == "review" else result["content"]
        artifact_id = _artifact(state, activation["output_type"], content, activation, partial=outcome == "return")
        activation["result_artifact_id"] = artifact_id
        if activation["mode"] == "review":
            state["review_artifact_id"] = artifact_id
        if outcome == "return":
            feedback = {"from": activation["phase"], "target": result["target"],
                        "reason": result["reason"], "question": result["question"],
                        "partial_artifact_id": artifact_id,
                        "accepted": state["returns_used"] < state["max_returns"]}
            bindings = {**activation["input_bindings"], "partial": artifact_id}
            state["feedback"].append(_artifact(state, "cognition.feedback", feedback, activation, bindings=bindings))
        _transition(state, outcome, result, artifact_id)
        state["last_receipt"] = {"command_id": command_id, "activation_id": activation_id,
                                 "artifact_id": artifact_id, "version": state["version"], "outcome": outcome}
        _event(state, "command.accepted", **state["last_receipt"])
        _save(connection, state)
        connection.execute("INSERT INTO commands (command_id, request, response) VALUES (?, ?, ?)",
                           (command_id, request, _json(state)))
        return state


def runtime_failed(store_path: Path, activation_id: str, expected_version: int, reason: str) -> dict:
    """Stop a ready/running activation after runtime failure, never advancing the pattern."""
    if not _text(reason):
        raise ControllerError("Failure reason must be nonempty text")
    with _transaction(store_path) as connection:
        state = _load(connection)
        activation = _current(state, activation_id, expected_version, ("ready", "running"))
        state["version"] += 1
        activation["status"] = state["actors"][activation["actor_id"]]["status"] = "failed"
        activation["failure_reason"] = reason
        state.update(status="failed", machine_state="failed", reason=reason, current_activation=None)
        _event(state, "runtime.failed", activation_id=activation_id, reason=reason)
        return _save(connection, state)


def cancel_run(store_path: Path, reason: str) -> dict:
    """Cancel the run and fail its reservation. Repeated cancellation is a no-op."""
    if not _text(reason):
        raise ControllerError("Cancellation reason must be nonempty text")
    with _transaction(store_path) as connection:
        state = _load(connection)
        if state["status"] == "cancelled":
            return state
        if state["status"] != "active":
            raise ConflictError("Cannot cancel a terminal run")
        state["version"] += 1
        activation = state["activations"][state["current_activation"]]
        activation["status"] = state["actors"][activation["actor_id"]]["status"] = "failed"
        activation["failure_reason"] = f"cancelled: {reason}"
        state.update(status="cancelled", machine_state="cancelled", reason=reason, current_activation=None)
        _event(state, "run.cancelled", activation_id=activation["id"], reason=reason)
        return _save(connection, state)
