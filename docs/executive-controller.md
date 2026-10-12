# Executive Controller

`scripts/noetic_controller.py` is a deterministic, SQLite-persisted serial
activation kernel shared by two declarative state-machine patterns. It reserves
real role work for an external adapter. It does not launch models, processes, QA
agents, or tools. Role names do not themselves establish that work occurred.
The adapter must execute the reserved role and supply actual observed changes
and check evidence for implementation results.

## Public API

```python
start_run(
    store_path: Path,
    pattern: dict | str | Path,
    purpose: str,
    workspace: Path,
    max_remediations: int = 1,
    max_returns: int = 1,
    inputs: dict | None = None,
) -> dict
inspect_run(store_path: Path) -> dict
begin_activation(store_path: Path, activation_id: str, expected_version: int) -> dict
submit_result(
    store_path: Path,
    activation_id: str,
    expected_version: int,
    result: dict,
    session_ref: str,
    command_id: str,
) -> dict
runtime_failed(
    store_path: Path, activation_id: str, expected_version: int, reason: str,
) -> dict
cancel_run(store_path: Path, reason: str) -> dict
result_contract(state: dict) -> dict | None
```

Use `PATTERN_DIR / "development.json"` or `PATTERN_DIR / "cognition.json"`.
A dictionary is also accepted and detached from caller mutations. The complete
pattern is persisted, so reopening a run uses its original table and contracts.
The workspace and store's parent directory must already exist. Each store file
contains one run and cannot be restarted or overwritten by `start_run`.

All methods return state dictionaries; `result_contract` instead returns the
current role's JSON Schema, or `None` for a terminal run. `ControllerError`
(a `ValueError`) covers invalid requests, `InvalidResultError` covers malformed
role results, and `ConflictError` covers stale versions, lifecycle violations,
session reuse, and conflicting command delivery. Filesystem/SQLite errors
propagate. No rejected operation changes committed run state or receipts.

## Adapter Protocol

```python
from pathlib import Path
from scripts.noetic_controller import (
    PATTERN_DIR, begin_activation, result_contract, start_run, submit_result,
)

store = Path("run.sqlite")
state = start_run(store, PATTERN_DIR / "development.json", "Purpose", Path.cwd(),
                  inputs={"sources": [{"ref": "requirements.md"}]})
activation = state["activations"][state["current_activation"]]
state = begin_activation(store, activation["id"], state["version"])
contract = result_contract(state)
bound_artifacts = {
    slot: state["artifacts"][artifact_id]
    for slot, artifact_id in activation["input_bindings"].items()
}
# The adapter now invokes activation['role'] in a FRESH runtime session,
# passes the purpose, workspace, criteria, bound artifacts and contract,
# parses the structured result, and records a stable command ID for delivery.
# result and session_ref below come from that actual runtime invocation.
# state = submit_result(store, activation['id'], state['version'],
#                       result, session_ref, command_id)
```

There is exactly one `current_activation` while the run is active. It is an ID
into `state["activations"]`, not an activation object. Activation fields include
`id`, `actor_id`, `ordinal`, `role`, `phase`, `mode`, `generation`, `visit`,
`status`, `session_ref`, `input_bindings`, `criteria`, `output_type`, and
`result_contract`. Mode is `produce`, `review`, or `operate`. Review activations
also carry `qa_framing`. The adapter must follow these reservations, not choose
the next role itself.

Actors and activations are kernel-assigned (`actor-0`, `activation-0`, etc.),
with monotonically allocated ordinals `0.0`, `0.1`, ... per store. Every
activation has a new actor. All actors require distinct, nonempty runtime
`session_ref` values, including remediation authors and independent reviewers.
The runtime supplies identity as the separate submission argument; identity
fields in role result objects are rejected. The kernel can check equality of
runtime references, not whether a runtime actually isolated model context.

`begin_activation` changes `ready` to `running`; only a running activation can
submit. An accepted result retires the actor/activation and follows the table
to allocate its successor or terminate. `runtime_failed` marks a ready or
running activation failed and stops the run without advancing. `cancel_run`
fails the current reservation and terminates with `cancelled`; repeating a
cancellation is a no-op retaining the original reason. Other terminal runs
cannot be cancelled. There is no automatic runtime retry or resurrection:
after reopening a running reservation the adapter must reconcile its runtime,
submit the result, or report failure rather than launch duplicate work.

## State And Delivery

`state["status"]` is `active`, `completed`, `blocked`, `failed`, or `cancelled`.
`machine_state` identifies the controller substate; `phase_index` indexes the
persisted pattern's phases. `version` starts at 1 and increments once for each
accepted begin, result, failure, or cancellation. Each successor is reserved in
the same version/transaction as the result that caused it.

The SQLite `run` table stores state JSON, including actors, activations,
artifacts, slots, feedback and ordered transition events. The `commands` table
stores each accepted result's canonical request and original response state.
`BEGIN IMMEDIATE` serializes local writers. State, artifacts, transition events,
new reservations, and the command receipt commit or roll back together.

An exact retry of `submit_result` with the same `command_id`, activation ID,
original expected version, result and session reference returns its **original
response state**, even after later progress or termination. JSON object key
order does not matter. It does not rewind the store. Use `inspect_run` for
the latest state after replay. Reusing that command ID with different arguments
is a conflict; a new command with a stale version is also a conflict. Rejected
commands do not consume IDs. `last_receipt` describes the last accepted result
in a returned state. Begin/failure calls use version checks, not result-command
receipts; after an interrupted call, inspect before deciding what to do next.

Artifacts have immutable `type`, `content`, SHA-256 `digest` of canonical UTF-8
JSON content (sorted keys, compact separators, ASCII escaping), `produced_by`
actor ID, `activation_id`, phase/generation/visit, `input_bindings`,
`derived_from` artifact IDs, `partial`, and `origin`. IDs are store-local.
Acceptance changes slots, never artifact contents. Returned dictionaries are
detached snapshots; changing one cannot mutate the store.

Purpose and `inputs` are explicit external artifacts (`external.purpose`,
`external.sources`, and `external.<input-name>`). Sources default to an empty
array; `inputs` cannot override purpose. External artifacts have null producers.
No file is implicitly read as evidence. Each phase declares typed required
input slots, and allocation checks those slots against nonpartial artifacts.
Runtime artifacts derive from the exact IDs bound to that activation. Additional
external input requirements may be declared, but all must be supplied at start.

## Development Pattern

Kind `verified_sequence` has exactly these phases and required content fields:

| Phase | Role | Content Fields |
| --- | --- | --- |
| `design_intent` | `intent_designer` | `objective: string`, `scope: array`, `acceptance_criteria: array` |
| `abstract_design` | `abstract_designer` | `components: array`, `interfaces: array`, `decision: string` |
| `implementation_procedure_design` | `procedure_designer` | `steps: array` |
| `implementation` | `implementer` | `report: string`, `changes: array`, `verification: array` |

Each phase starts `pending -> producing`, accepts
`{"outcome": "produced", "content": {...}}`, then enters `qa_review` with a
fresh `independent_qa` actor bound to that exact subject artifact. Each phase
gets initial generation 0 and initial QA even when `max_remediations=0`.
Every later phase binds **all accepted prior phase artifacts**, plus purpose
and sources. Drafts cannot fill accepted slots.

QA returns this shape (`outcome` may replace `verdict`; both must agree if given):

```json
{
  "subject_artifact_id": "artifact-2",
  "verdict": "fail",
  "report": "Compared the subject against the explicit acceptance criteria.",
  "findings": [{"description": "A concrete requirement is missing.", "blocking": true}]
}
```

`findings` is always an array; every finding has a nonempty description and a
boolean `blocking`. A pass with any blocking finding is rejected. Nonblocking
findings may accompany a pass. A pass binds `accepted.<phase>` to the reviewed
subject and advances, or completes after implementation QA. The kernel validates
structure and linkage, not semantic truth or the sufficiency of claimed evidence.

A fail while `generation < max_remediations` enters `remediating` with a fresh
author, incremented generation, the previous `subject`, and `feedback.qa` bound
to the failed review artifact. Production then allocates a fresh QA actor for
the new subject. The per-phase generation resets to 0 at the next phase. An
exhausted failure yields `blocked`, with reason `remediations_exhausted:<phase>`;
there is no accepted slot for that phase and no further allocation.

QA framing is reasoned, critical, constructive and non-perfectionistic: assess
material defects and proportionate risks against explicit criteria, offer
practical remediation, and avoid speculative hardening or downstream QA.

## Cognitive Pattern

Kind `recurrent_operations` distinguishes these operations:

| Phase | Role | Content Fields | Ordinary Outcome | Return Targets |
| --- | --- | --- | --- | --- |
| `P1` | `attentiveness` | `observations: array`, `questions: array`, `evidence_refs: array` | `advance` | None |
| `P2` | `intelligence` | `hypotheses: array` | `advance` | `P1` |
| `P3` | `reasonableness` | `judgment: string`, `grounds: array`, `conditions: array` | `advance` | `P1`, `P2` |
| `P4` | `responsibility` | `decision: string`, `rationale: string`, `next_actions: array` | `complete` | `P1`, `P2`, `P3` |

Each visit enters `pending -> operating`. Ordinary outcomes carry `content`
with the fields above and bind `effective.<phase>`. Every operation gets purpose
and sources, plus all current prior effective artifacts. Content fields are
lightweight types; arrays may contain structured evidence, changes, or actions.
Additional content fields are allowed. No array is independently checked for
semantic completeness. Top-level result fields are limited to the role contract.

```json
{
  "outcome": "return",
  "content": {"conditions": ["The current evidence cannot settle the hypothesis."]},
  "target": "P1",
  "reason": "A decisive observation is missing.",
  "question": "Which observed result would distinguish the explanations?"
}
```

A return requires nonempty partial content, an allowed target, nonempty reason,
and nonempty question. Known content fields keep their types, but no completed
judgment or decision is required. The controller records a partial stage
artifact and a typed `cognition.feedback` artifact containing the source,
target, reason, question, partial artifact ID, and whether budget allowed return.

Before allocating a target, it checks the run-wide `max_returns` budget. An
accepted return increments `returns_used`, removes the target and all downstream
`effective.*` bindings, increments the target's visit number (first visit is 1),
and reserves a fresh actor at that target. Historical artifacts and feedback
remain intact. The latest `feedback.return` is bound into ensuing visits, and
normal forward traversal then rebuilds the invalidated slots. Partial artifacts
are never placed into effective slots.

If exhausted, it records the partial work and feedback with `accepted: false`,
then terminates `blocked` with reason `return_budget_exhausted`, without a new
actor, budget increment, or slot invalidation. Invalid return targets or malformed
returns are rejected without any history, budget, or state changes. Neither
return nor exhaustion fabricates a completed judgment.

## Transition Scope

The JSON tables declare `from`, `on`, named fixed `guard`, fixed `action`, and
`to` for every pattern transition. Both kinds share allocation, persistence,
identity, artifact, delivery, and transition dispatch code. Pattern dictionaries
can customize roles, criteria, output types, additional content fields and
external inputs while preserving the four phase IDs, required content fields,
prior-phase bindings, fixed kind table and allowed backedges. There is no
arbitrary expression language, generic DAG, distributed lease, publication,
authorization, or model invocation layer.

Focused verification: `python -m unittest discover -s tests/programs -p test_noetic_controller.py`.
Tests exercise actual temporary SQLite stores with structured fixture results;
they do not claim live-role delivery. Lead-owned driver integration and its one
independent QA pass remain separate.
