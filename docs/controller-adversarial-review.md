# Adversarial review: noetic-dev executive controller proposal

**Reviewed artifact:** `docs/controller-architecture.md`
**Method:** challenge safety, liveness, determinism, authority, recovery, portability, operability, and scope. A plausible design is not evidence of a correct design.

## Verdict

**PASS WITH REQUIRED AMENDMENTS before implementation.** The architecture is materially superior to a lift-and-shift because it isolates a pure transition kernel, makes authority/version/idempotency explicit, treats effects honestly, generalizes waves into legible barriers over a DAG, and replaces heuristic recovery with leases/fencing. The following findings are binding design gates.

## Blocking findings

### B1. Full event sourcing could become a complexity trap

**Risk:** requiring every projection to replay indefinitely can overbuild Stage B and make migrations/recovery harder than the donor.

**Required amendment:** use an append-only causal journal as authority, but permit versioned snapshots/checkpoints and transactional current-state projections. Specify retention, snapshot verification, and rebuild tests. Do not promise unlimited replay without compaction evidence.

### B2. DAG flexibility can destroy operator legibility

**Risk:** replacing waves with a general graph may make ordering technically expressive but cognitively opaque, undermining the observability goal.

**Required amendment:** every run must expose a barrier/wave projection, ready-set explanation, blocked-edge explanation, and critical path. Programs should default to barriers; arbitrary edges require justification. Deterministic ordering keys must be persisted in the program version.

### B3. Authority model needs a denial matrix

**Risk:** prose boundaries between Telos, controller, agent, QA, operator, and adapters are insufficient to prevent privilege expansion.

**Required amendment:** define a command-by-actor authority matrix, scope inheritance rules, expiry/revocation, and negative conformance tests. Adapters cannot manufacture authority. Amendments cannot broaden authority beyond their issuer.

### B4. Publication effects need repository-race semantics

**Risk:** a fenced workspace can still race remote branch movement, checks, or concurrent merges.

**Required amendment:** publication commands carry expected base/head revisions and branch-protection receipts. Commit creation, push, PR, merge, deployment, and cleanup are separate effects. Remote mismatch becomes a durable blocked interaction, never implicit rebase/force.

### B5. Implementation:QA cardinality is underspecified across retries

**Risk:** “one QA per implementation attempt” can be interpreted as one QA total despite remediation, or can cause duplicate QA obligations after retry.

**Required amendment:** formalize identities: each accepted implementation submission creates exactly one verification generation; remediation creates a new implementation generation and exactly one new verification obligation. Duplicate delivery returns the existing obligation receipt. Property-test cardinality.

## Major non-blocking findings

### M1. Event payload privacy

Add event classification (`public`, `internal`, `sensitive-reference`) and schema-level redaction tests. The critical-contact number, credentials, prompts, and private artifacts must never enter broad event payloads.

### M2. Lease timing and clock behavior

Use injected monotonic-duration semantics for lease expiry and wall-clock timestamps only for audit display. Test clock skew, pause, restart, and delayed submissions.

### M3. Model selection reproducibility

Persist the genus-router request, availability snapshot identity, selected model reference, fallbacks, and policy version. Model availability changes must not rewrite historical rationale.

### M4. Semantic QA independence

A distinct process/context is necessary but may be insufficient when the same model receives implementation context. Add policy hooks for model/provider diversity, context minimization, and blinded evidence, while avoiding a universal diversity requirement before evidence supports it.

### M5. Program evolution

Version program schemas and transition semantics. Active runs pin a program version; migration is explicit. Never mutate an active run's graph in place except through scoped append-only amendments with compatibility validation.

### M6. ContextForge dependency

The event sink must support ContextForge because current tools depend on it, but the kernel must also have a direct in-memory/reference sink for tests and portability. Add parity tests before changing transport.

## Conformance properties

These should be property/model-tested, not only example-tested:

1. Terminal states never transition except through a new linked generation.
2. The same accepted command ID/idempotency key never produces a second domain effect.
3. Identical graph state and policy yield the same ordered ready set.
4. No node becomes ready while a required dependency is unsatisfied.
5. No implementation generation can succeed without exactly one settled QA obligation.
6. A stale fencing token cannot mutate state or publish effects.
7. Every accepted transition has one causal event and every effect receipt links to its intent.
8. Every nonterminal run has ready work, a valid lease, a scheduled retry, or a durable interaction.
9. Projection rebuild yields state equivalent to the verified snapshot plus subsequent events.
10. Authority can only narrow through delegation; broadening requires a new authorized command.

## Required pre-implementation outputs

- versioned command/event JSON schemas;
- actor/command authority matrix;
- state-transition tables and generated diagram;
- dependency and barrier semantics with explanation examples;
- snapshot/compaction and migration policy;
- effect idempotency/receipt contracts;
- donor conformance-fixture inventory with provenance;
- Stage A test plan, including model-based and property tests.

Until these are reviewed, implementation would prematurely freeze attractive but incomplete abstractions.
