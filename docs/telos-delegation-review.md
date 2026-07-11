# Adversarial review: Telos delegation v0

**Issue:** [#9](https://github.com/somebloke1/noetic-dev/issues/9)

**Pairing:** one implementation generation → exactly one adversarial QA pass

## Verdict

**PASS FOR M0 CONTRACT REVIEW; NO RUNTIME DISPATCH AUTHORIZED.**

Positive fixtures passed Draft 2020-12 validation. The independent mutation pass found no unresolved blocker.

## Vectors

| Vector | Attack | Result |
|---|---|---|
| Confused deputy | Added `scheduler.tick`, broadened authority beyond scope, and changed the controller run identity. | Rejected against the canonical Telos authority row and pinned run scope. |
| Replay and duplicate runs | Replayed stable contract identity, then changed purpose while retaining old objective/result digests. | Same intent remains stable; changed purpose changes the digest and fails old receipts. Duplicate delivery cannot become a second run. |
| Cancellation race | Inspected every terminal transition, cancellation binding, and expected-version rule. | Terminal delegation states have no exits; cancel uses `run.abort`; a terminal run returns its existing result rather than reopening. |
| Expiry/revocation | Moved expiry before creation and supplied a revocation reference. | Dispatch fails closed outside the authority window or after revocation. |
| Stale purpose | Downgraded reproductive-clause version and changed objective without digest update. | Rejected. Immutable purpose identity is explicit. |
| Ownership ambiguity | Added `sub_goal_status=complete` to a successful result and changed run/digest identity. | Strict schema and semantic checks reject it. Controller success never directly completes or blocks a Telos sub-goal. |
| Privacy and bounded recurrence | Injected bearer material into objective/result and raised retry count to 999. | Secret-shaped values and unbounded retries are rejected. |
| Cross-contract/scope | Checked controller authority, canonical event classes, and changed paths. | Contracts agree; no runtime, database, agent, repository, or network effect was introduced. |

The validator also passed under `python3 -O`; its enforcement does not rely on optimized-away assertions.

## Boundaries

1. The inspected Telos donor has delegation tables but no enforcing lifecycle manager; migration/storage uniqueness and transactionality belong to a later Telos adapter issue.
2. The fixture pins reproductive-clause version 5 to prove stale-purpose rejection. Runtime validation must compare against the authoritative current clause, not hard-code version 5.
3. Canonical digest algorithm must remain aligned with the event contract and receive cross-language parity proof before durable dispatch.
4. Authority expiry uses wall-clock timestamps at the boundary; controller leases still use injected monotonic time internally.
5. Publication is not granted in the positive fixture. Any publication request requires explicit narrowed permission plus the controller publication revision contract.
6. No result is semantically self-adjudicating; Telos retains P3/P4 responsibility.
