# M0 Telos-to-adjudication reference trace

This experimental composition-root proof freezes one provider-free path from a Telos delegation to a separate Telos terminal adjudication. It is a reference integration slice, not the production controller or Telos dispatcher.

## Boundary

The proof uses only Python's standard library and repository JSON. It performs no model, network, MCP, database, environment-authority, repository-mutation, or filesystem-write operation. `validate_and_project()` is a pure reduction over its argument: it has no clock, randomness, mutable global state, or external effect. The CLI only reads the supplied fixtures and writes a projection to standard output when not in check mode.

The delegation's validity is evaluated against attributed record timestamps, never the machine clock. All timestamps are strict whole-second RFC 3339 UTC values ending in `Z`; each causal successor must be later than its predecessor and earlier than the delegation expiry.

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

The accepted generation creates one named verification obligation. One delegated QA identity, distinct from the attributed implementer and every other delegated actor, must attribute `PASS` to that generation, candidate digest, and obligation before the controller can record success. The result then reports the accepted-generation, QA, and success event identifiers as evidence. Only the delegated Telos identity may append the terminal `complete` disposition, and no record is accepted after it.

Every record repeats the same delegation, delegation digest, goal-chain, sub-goal, program, run, generation, and correlation binding. Every non-root record names exactly its immediate causal predecessor. The delegation digest is recomputed from canonical delegation identity, authority, actor, event, and validity material. The delegation grants only the actions needed by this trace; the implementer identity has no event-writing action, the controller has no Telos action, and the initial Telos authorization does not delegate re-delegation.

Strict shapes reject unknown or missing fields at every level. Strict JSON rejects duplicate keys, floats, non-finite numbers, and nulls. Typed checks prevent a JSON boolean from serving as generation `1`. IDs, digests, versions, operations, conclusions, run outcomes, and dispositions are closed vocabularies or constrained formats.

## Semantic responsibility

The reducer does not decide whether implementation work is correct, whether QA's conclusion is wise, or whether Telos ought to complete the sub-goal. It validates that `PASS`, `succeeded`, and `complete` are attributed to the authorized identities and bound evidence. Those remain semantic conclusions made by QA, the controller, and Telos respectively.

In particular, `controller.result.reported` has no sub-goal-status field. Strict shape rejection prevents the controller from setting or implying one. The projection reaches state `telos_adjudicated` only after the separate Telos record and presents `complete` solely as that Telos actor's attributed disposition.

## Artifacts and use

- [`../spec/m0/v0/telos-adjudication-trace.schema.json`](../spec/m0/v0/telos-adjudication-trace.schema.json) describes strict document shapes.
- [`../spec/m0/v0/trace-contract.json`](../spec/m0/v0/trace-contract.json) freezes ordering, authority, state, canonicalization, and semantic boundaries.
- [`../spec/m0/v0/golden/valid-telos-adjudication-trace.json`](../spec/m0/v0/golden/valid-telos-adjudication-trace.json) is the one valid M0 input.
- [`../spec/m0/v0/golden/expected-projection.json`](../spec/m0/v0/golden/expected-projection.json) is its canonical byte projection.

Run the reference check with:

```bash
python3 scripts/m0_trace.py --check \
  spec/m0/v0/golden/valid-telos-adjudication-trace.json \
  spec/m0/v0/golden/expected-projection.json
```

The check requires the expected projection file itself to be canonical ASCII JSON: lexicographically sorted keys, no insignificant whitespace, compact separators, and one final LF. This makes the projection byte-stable across processes and `PYTHONHASHSEED` values.
