# Controller Stage A model/property test plan

Stage A tests the pure kernel and contracts only: no database, agents, git, network, ContextForge, LiteLLM, tmux, PTY, or browser.

## Model

Generate commands against in-memory aggregates with deterministic clock/IDs. Compare the reducer to a simple reference model and persist any failing random seed.

## Required properties

1. **Transition legality:** every accepted event appears in the relevant transition table; terminal states never transition.
2. **Version race:** for concurrent commands with one expected version, at most one is accepted.
3. **Idempotency:** repeating a command/idempotency key returns the same receipt and creates no additional event/effect.
4. **Atomic intent:** an accepted command returns domain events and effect intents together; rejected commands return neither.
5. **Ready-set determinism:** permuting nodes/dependencies does not change sorted ready-node IDs.
6. **Dependency safety:** no node is ready with an unsatisfied required edge or conflicting lease.
7. **Barrier settlement:** `all`, `quorum`, `policy_selected`, and `fail_fast` settle exactly as declared and explain why.
8. **Authority denial:** every denied actor×command cell fails closed with zero domain events.
9. **Authority attenuation:** delegated authority permissions are a subset of issuer permissions and cannot outlive issuer expiry/revocation.
10. **Implementation:QA cardinality:** each accepted implementation generation creates exactly one verification obligation, including duplicate delivery, remediation, and crash replay.
11. **Fencing:** stale attempt/workspace tokens cannot mutate aggregates or authorize publication.
12. **Liveness representation:** every nonterminal aggregate has ready work, a valid lease, a scheduled retry, or a durable interaction.
13. **Privacy classification:** event payloads cannot contain fields named or classified as credentials, passwords, tokens, full prompts, private artifacts, or critical-contact data.
14. **Program pinning:** an active run cannot silently change program version or graph.
15. **Projection explanation:** ready and blocked nodes expose deterministic predecessor/barrier reasons.

## Mutation/adversarial cases

- remove each required command/event field;
- add unknown fields to strict envelopes;
- duplicate IDs and idempotency keys;
- shuffle graph declaration order;
- inject cycles, missing nodes, impossible barriers, and illegal loop shapes;
- deliver submit/receipt after lease replacement;
- crash before event append, after append/before outbox, after effect/before receipt, and after receipt/before projection;
- attempt every denied command as every actor;
- submit QA twice, remediate twice, and replay pre-crash submissions;
- request publication with stale base/head/remote revisions.

## Promotion gate

Stage A passes only when schemas, transition tables, authority matrix, examples, validator, model/property tests, and one adversarial QA pass are merged. Passing example tests alone is insufficient.
