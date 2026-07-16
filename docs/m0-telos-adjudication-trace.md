# M0 Telos-to-adjudication reference trace

This experimental composition-root proof freezes one provider-free path through a self-contained fixture from a fixture-declared Telos delegation to a separate, fixture-attributed Telos terminal adjudication. It is a reference integration slice, not the production controller or Telos dispatcher.

## Boundary

The proof uses only Python's standard library and repository JSON. It performs no model, network, MCP, database, environment-authority, repository-mutation, or filesystem-write operation. `validate_and_project()` is a pure reduction over its argument: it has no clock, randomness, mutable global state, or external effect. The CLI only reads the supplied fixtures and writes a projection to standard output when not in check mode.

The delegation's validity is evaluated against attributed record timestamps, never the machine clock. All timestamps are strict whole-second RFC 3339 UTC values ending in `Z`; each causal successor must be later than its predecessor and earlier than the delegation expiry.

The proof establishes deterministic internal structural consistency only. Actor IDs, roles, and delegated actions are declarations inside the same fixture. M0 does not establish their external identity provenance, authentication, signatures, origin, real-world authorization, or an externally independent QA principal. Event and field names such as `authorized`, `authority`, and `delegated` name fixture records; they are not evidence of external authorization.

## Frozen reduction

The only accepted record sequence is:

1. `telos.delegation.authorized`
2. `controller.run.created`
3. `controller.run.started`
4. `controller.implementation_generation.accepted`
5. `qa.verification.adjudicated`
6. `controller.run.succeeded`
7. `controller.result.reported`
8. `telos.sub_goal.adjudicated`

The accepted generation creates one named verification obligation. One fixture-declared QA actor ID, structurally distinct from the attributed implementer and every other fixture-declared actor ID, must carry the attributed `PASS` for that generation, candidate digest, and obligation before the controller can record success. This structural distinction does not establish authenticated external independence. The result then reports the accepted-generation, QA, and success event identifiers as evidence. Only the actor ID declared under the fixture's Telos role may append the terminal `complete` disposition, and no record is accepted after it.

Every record repeats the same delegation, delegation digest, goal-chain, sub-goal, program, run, generation, and correlation binding. Every non-root record names exactly its immediate causal predecessor. The delegation digest is recomputed from canonical fixture-declared identity, actor/action, event, and validity material. The fixture declares only the actions needed by this trace; the implementer actor ID has no event-writing action, the controller actor ID has no Telos action, and the initial Telos record does not declare re-delegation.

Strict shapes reject unknown or missing fields at every level. Strict JSON rejects duplicate keys, floats, non-finite numbers, and nulls. Typed checks prevent a JSON boolean from serving as generation `1`. IDs, digests, versions, operations, conclusions, run outcomes, and dispositions are closed vocabularies or constrained formats.

## Semantic responsibility

The reducer does not decide whether implementation work is correct, whether QA's conclusion is wise, or whether Telos ought to complete the sub-goal. It validates that `PASS`, `succeeded`, and `complete` are attributed to actor IDs consistent with the fixture-declared actor/action mapping and bound evidence. Those remain fixture-attributed semantic conclusions; M0 does not authenticate the actors or externally authorize their conclusions.

In particular, `controller.result.reported` has no sub-goal-status field. Strict shape rejection prevents the controller from setting or implying one. The projection reaches state `telos_adjudicated` only after the separate Telos record and presents `complete` solely as the fixture-attributed disposition recorded under that Telos actor ID.

## Artifacts and use

- [`../spec/m0/v0/telos-adjudication-trace.schema.json`](../spec/m0/v0/telos-adjudication-trace.schema.json) describes strict document shapes.
- [`../spec/m0/v0/trace-contract.json`](../spec/m0/v0/trace-contract.json) freezes ordering, internally declared actor/action constraints, state, canonicalization, and semantic boundaries.
- [`../spec/m0/v0/golden/valid-telos-adjudication-trace.json`](../spec/m0/v0/golden/valid-telos-adjudication-trace.json) is the one valid M0 input.
- [`../spec/m0/v0/golden/expected-projection.json`](../spec/m0/v0/golden/expected-projection.json) is its canonical byte projection.

Run the reference check with:

```bash
python3 scripts/m0_trace.py --check \
  spec/m0/v0/golden/valid-telos-adjudication-trace.json \
  spec/m0/v0/golden/expected-projection.json
```

The check requires the expected projection file itself to be canonical ASCII JSON: lexicographically sorted keys, no insignificant whitespace, compact separators, and one final LF. This makes the projection byte-stable across processes and `PYTHONHASHSEED` values.
