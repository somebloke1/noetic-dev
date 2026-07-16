# M1 bounded Telos recoverability reference trace

This experimental composition-root proof freezes one provider-free sibling path beside M0. One semantic implementation generation receives a fixture-attributed QA `FAIL`, one predeclared remediation generation receives a fixture-attributed QA `PASS`, the controller reports success for generation 2 only, and a separate fixture-attributed Telos record adjudicates the complete lineage. This is a fixed reference integration slice, not a production controller or a generic retry mechanism.

## Boundary

The reducer uses Python's standard library and repository JSON. M1 imports only M0's public strict-JSON loading and canonical-byte utilities; M1 owns its state progression, delegation digest, validation error, semantic binding checks, remediation accounting, and projection. It performs no model, genus-router, LiteLLM, network, MCP, database, environment-authority, repository-mutation, external lookup, or filesystem-write operation. `validate_and_project()` is a pure reduction over its argument, with no clock, randomness, mutable global state, or external effect. The CLI only reads supplied files and writes the canonical projection to standard output outside check mode.

All authority, candidate, finding, QA, controller, and Telos content is declared inside the fixture. Validation establishes deterministic internal structure, attribution, binding, cardinality, evidence, and order only. It does not establish external identity provenance, authentication, signatures, origin, real-world authorization, semantic correctness, or an externally independent QA principal. Terms such as `authorized`, `accepted`, `FAIL`, `PASS`, `succeeded`, and `complete` name fixture records and conclusions; they are not independent evidence that those claims are true outside the fixture.

This trace demonstrates recovery from one structurally attributed QA failure. It does not demonstrate process or machine crash recovery, persistence recovery, scheduling, dispatch, effects, publication, or operator intervention.

## Frozen reduction

The only accepted record sequence is:

1. `telos.delegation.authorized` at generation 1
2. `controller.run.created` at generation 1
3. `controller.run.started` at generation 1
4. `controller.implementation_generation.accepted` at generation 1
5. `qa.verification.adjudicated` with `FAIL` and one opaque finding at generation 1
6. `controller.remediation_generation.started` at generation 2
7. `controller.implementation_generation.accepted` at generation 2
8. `qa.verification.adjudicated` with `PASS` and no finding at generation 2
9. `controller.run.succeeded` at generation 2
10. `controller.result.reported` at generation 2
11. `telos.sub_goal.adjudicated` at generation 2

The semantic generation sequence is exactly `[1,1,1,1,1,2,2,2,2,2,2]`; it changes only on the remediation-start record. Every non-root record has exactly its immediate predecessor as `caused_by`. Event IDs are unique, timestamps strictly increase inside the fixture-declared delegation interval, and no record is accepted after terminal adjudication.

Every record carries the same delegation, digest, goal-chain, sub-goal, program, run, and correlation binding. The generation component changes at the one fixed transition. The delegation digest covers the root record's fixture-declared identity, initial generation, actor/action mapping, validity, and exact policy `{"max_remediation_generations":1}`. Remediation consumption is derived from the sole remediation event as `authorized=1`, `consumed=1`, and `remaining=0`; remediation payloads cannot supply counters.

## Failure and remediation binding

Generation 1 creates one candidate and one verification obligation. Exactly one QA event binds that acceptance, candidate ID and digest, and obligation. Its conclusion is exactly `FAIL`, and its closed payload carries exactly one opaque `finding_id` and `finding_digest`. No severity, narrative, waiver, or semantic interpretation is represented.

The immediately following remediation event has ordinal 1, targets the failed generation plus one, and cites the exact failed acceptance, QA event, verification obligation, finding ID, and finding digest. No second remediation, waiver, force-completion, counter override, or expanded scope fits the fixed eleven-record shape.

Generation 2 creates a candidate ID, candidate digest, accepted-event ID, and verification-obligation ID distinct from generation 1. Its acceptance cites both the remediation event and the superseded generation-1 acceptance. Exactly one generation-2 QA event binds only generation-2 evidence, concludes exactly `PASS`, and rejects finding fields. The same fixture-declared QA actor ID may carry both QA records, but that ID is structurally distinct from all other fixture actor IDs; this remains an internal declaration, not proof of authenticated independence.

## Split terminal evidence

Controller success is legal only after the generation-2 `PASS` and binds only generation-2 acceptance, candidate, digest, obligation, and QA event. The controller result's evidence is exactly generation-2 acceptance, generation-2 QA, and run success. Closed payload shapes prevent the controller from adding a sub-goal status or Telos disposition.

Telos adjudication is a separate final record under the fixture-declared Telos actor ID. Its evidence is exactly the ordered full history: generation-1 acceptance, generation-1 QA failure, remediation start, generation-2 acceptance, generation-2 QA pass, run success, and controller result. Only that record carries fixture-attributed disposition `complete`.

## Artifacts and use

- [`../spec/m1/v0/telos-recoverability-trace.schema.json`](../spec/m1/v0/telos-recoverability-trace.schema.json) fixes the eleven strict record shapes.
- [`../spec/m1/v0/trace-contract.json`](../spec/m1/v0/trace-contract.json) freezes event, role, generation, transition, budget, evidence, and boundary rules.
- [`../spec/m1/v0/golden/valid-telos-recoverability-trace.json`](../spec/m1/v0/golden/valid-telos-recoverability-trace.json) is the one valid M1 input.
- [`../spec/m1/v0/golden/expected-projection.json`](../spec/m1/v0/golden/expected-projection.json) is its canonical deterministic projection.

Run the reference check with:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/m1_trace.py --check \
  spec/m1/v0/golden/valid-telos-recoverability-trace.json \
  spec/m1/v0/golden/expected-projection.json
```

The expected projection must itself be compact lexicographically sorted ASCII JSON with one final LF. The projection preserves stable binding and delegation, derived remediation budget, ordered generation history, generation-2-only controller success and result, and the separate full-lineage Telos adjudication. It is byte-stable across input object order, processes, and `PYTHONHASHSEED` values.
