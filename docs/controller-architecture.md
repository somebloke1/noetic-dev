# noetic-dev executive controller architecture

**Status:** Design proposal for issue #3; implementation is prohibited until adversarial review findings and acceptance gates are resolved.

## 1. Purpose and boundary

The executive controller is noetic-dev's deterministic **how/when** plane. Telos supplies authorized purpose and delegation; the controller decides only structural execution legality and records causal truth; agents perform semantic P1–P4 work.

```text
Telos delegation → command boundary → deterministic controller → effect ports
                                           │
                                           ├─ agent-runtime port
                                           ├─ repository/workspace port
                                           ├─ genus-router model-selection port
                                           ├─ artifact/evidence port
                                           └─ cognitional-event outbox
```

The controller **must not** judge whether prose is insightful, true, or responsible. It may validate schemas, dependencies, authority, lifecycle, artifacts, and proof obligations. Semantic verdicts enter as signed/attributed evidence from an authorized agent or operator and remain auditable.

## 2. Donor evidence and lessons

Primary forward donor: `/home/dgk/workspace/noetic-pi-docker` at `30de068`; historical donor: `/home/dgk/workspace/pi2`.

| Donor evidence | Preserve | Improve in noetic-dev |
|---|---|---|
| `packages/apm/src/state-machine.ts` | phase validation, machine-readable out-of-sequence rejection, transition events | transition validation, state mutation, and event append become one atomic version-checked operation; no dynamic table/field mutation API |
| `implementer/procedure-json.ts` | strict parsing, retired-field rejection, typed dependency roles, binding imperatives | one versioned graph schema; remove parallel `dependencies` ambiguity; model authority/materialization/production separately |
| `implementation-wave-lifecycle.ts` | deterministic ready→QA→remediation→commit sequencing; bounded retries; per-WU findings | represent scheduling as a DAG with optional barrier groups; waves become a legible projection, not the only execution topology |
| `db-schema.ts` and case-history modules | durable QA cases/findings/adjudications, scoped amendments, blocker lineage | typed state enums and referential checks; append-only causal events as authority; generated projections rather than independently mutable truth planes |
| `implementation-recovery.ts` | restart recovery, bounded circuit breakers, explicit limbo/stale classification | durable leases, heartbeats, fencing tokens, idempotency keys, and effect outbox; no agent-id routing fallback for mismatched correlation |
| `git-workspace.ts` / wave commit path | owned-output verification, selective staging, commit proof, worktree isolation | repository is a port; workspace handles—not paths—carry authority; publication is an idempotent effect with receipt |
| orchestration variant/workspace runtime | isolated variants, selection distinct from merge/publication, truthful readiness axes | simplify overlapping lifecycle/readiness/status vocabularies into event-derived projections |
| pi2 `state-machine.js`, `tmux.js`, phronesis bootstrap | minimal spawn bootstrap, project-scoped tmux, visible agents | attach/runtime adapter only; never couple the controller kernel to tmux, PTY, Pi, OpenCode, or browser concerns |

### Donor failure lessons promoted to requirements

1. **No active limbo:** a nonterminal run/node must have a live lease, a durable pending interaction, a scheduled retry, or a deterministic next transition.
2. **No status-as-truth drift:** lifecycle, readiness, and actionability are projections of one causal journal, not independently writable fields.
3. **No flat dependency ambiguity:** launch material, governing context, produced artifacts, and optional context are distinct types.
4. **No verifier/controller plane confusion:** repository deliverables, proof-only artifacts, controller metadata, and sibling-owned outputs remain distinct.
5. **No ambient workspace authority:** authoritative workspace identity is explicit and fenced; absolute/undeclared ambient paths cannot silently become inputs.
6. **No correlation fallback as ordinary routing:** commands require run/node/attempt identity, idempotency key, and current fencing token. Recovery uses explicit reconciliation commands.
7. **No false terminality:** execution completion, selection, publication, cleanup, and evidence retention are separate states.
8. **No unbounded repair recurrence:** retries and remediation are bounded; recurrence lineage prevents indistinguishable loops.
9. **No transition without observability:** accepted commands atomically append domain events; effects and projections carry causation/correlation IDs.
10. **No hidden semantic automation:** deterministic code validates structure; agents judge meaning.

## 3. Core domain model

### 3.1 Aggregates

- **Run** — one authorized execution of a versioned program/graph.
- **Node** — one deterministic unit in the execution graph.
- **Attempt** — one leased agent execution of a node; retries create new attempts rather than mutating history.
- **VerificationObligation** — exactly one adversarial QA obligation created atomically for each implementation attempt. A remediation attempt creates its own new obligation.
- **Gate** — a structural or semantic evidence gate controlling successor readiness.
- **Dependency** — a typed edge between nodes, artifacts, authority, or external resources.
- **Artifact** — immutable identified output plus digest and provenance.
- **WorkspaceLease** — fenced authority over a repository/worktree or other mutable execution scope.
- **Interaction** — durable wait for operator/teleological guidance.
- **Amendment** — append-only, scoped authority changing an effective contract without rewriting its baseline.
- **Publication** — a separately authorized, receipt-bearing external effect (commit, merge, deployment, notification).

### 3.2 Typed dependencies

Every dependency has a `kind`, `source`, `target`, `required_state`, and optional materialization policy:

- `control` — predecessor node/gate must reach a state;
- `artifact` — immutable produced artifact/digest is required;
- `launch_material` — input must be materialized before an attempt lease;
- `governing_context` — authoritative reference supplied to the agent but not treated as a filesystem prerequisite;
- `context` — optional/non-authoritative reference;
- `external_resource` — declared host/service capability with health and freshness policy.

`future_dependency` is not a separate magical category: it is an artifact/control edge whose producer is another node. Cycles are rejected unless expressed as a bounded loop construct with an explicit convergence/exhaustion rule.

### 3.3 Lifecycle states

```text
Run:      draft → validated → ready → running ↔ awaiting_decision
                                      ├→ succeeded
                                      ├→ failed
                                      └→ aborted

Node:     pending → ready → leased → running → submitted → verifying
                                                        ├→ succeeded
                                                        ├→ remediation_ready
                                                        ├→ blocked
                                                        └→ failed
           any nonterminal → aborted

Attempt:  assigned → acknowledged → running → submitted
                                      ├→ lost
                                      ├→ rejected
                                      ├→ accepted
                                      └→ aborted

Gate:     pending → evaluating → passed | failed | exhausted | waived
```

Transitions are named and explicitly enumerated. Terminal states are monotonic. Any reopen is a new attempt/gate generation linked to the superseded one.

## 4. Deterministic transition kernel

A command envelope contains:

```text
command_id, idempotency_key, command_type, aggregate_id,
expected_version, actor, authority, causation_id, correlation_id,
payload, submitted_at
```

Processing is a pure sequence:

1. Load aggregate state and causal version.
2. Authenticate actor and validate scoped authority.
3. Reject duplicate command by idempotency key with the original receipt.
4. Validate expected version and transition preconditions.
5. Reduce command + state into domain events and effect intents.
6. Atomically append events and outbox records; increment version.
7. Update projections transactionally or asynchronously from the same event stream.
8. Execute effects at least once through idempotent ports; record effect receipts/failures as new events.

Exactly-once external effects are not claimed. The system provides **exactly-once command acceptance** and **at-least-once idempotent effect delivery**.

## 5. Scheduler and ordering

### 5.1 Ready-set computation

The scheduler derives a ready set from immutable graph topology plus current event-derived state. A node is ready only when:

- all required control/gate predecessors satisfy their required states;
- launch material and external resource predicates are satisfied;
- no conflicting workspace/resource lease exists;
- concurrency, policy, and authorization constraints permit dispatch;
- its program-specific structural preconditions pass.

Ready nodes are sorted deterministically by `(barrier_order, explicit_priority, topological_rank, node_id)`. Recomputing against identical state yields the same result.

### 5.2 Waves as barrier groups

Waves remain supported as explicit **barrier groups** because they are legible and useful for QA/commit checkpoints. They are not the only topology. Independent nodes may run concurrently; a barrier gate can require all, quorum, policy-selected, or fail-fast settlement. Every policy is declared and versioned.

### 5.3 Implementation:QA pairing

Dispatching an implementation attempt atomically creates one `VerificationObligation`. It cannot reach accepted/succeeded without settlement by a distinct QA attempt. The pairing is cardinality-enforced in storage and conformance tests, not prompt convention. QA independence requires a distinct attempt/context; model diversity may be policy-required but is not assumed automatically.

## 6. Effects and portable ports

The kernel depends only on interfaces:

- `StateStore` / `EventJournal` / `Outbox`;
- `Clock` and deterministic `IdSource` (injectable for tests);
- `AgentRuntimePort` (Pi, OpenCode, Goose, tmux-backed, browser-backed adapters);
- `WorkspacePort` and `RepositoryPort`;
- `ModelSelectorPort` (genus-router) and model-access references (LiteLLM/direct);
- `ArtifactStorePort`;
- `EventSinkPort` (cognitional-event stream, ContextForge where used, direct MCP/HTTP/stdio);
- `NotificationPort` (never part of transition authority).

No port type may leak runtime-specific process, PTY, tmux, browser, or provider objects into the domain kernel.

## 7. Authority and Telos boundary

Telos owns purpose, goal/sub-goal evolution, and authorization windows. It submits a typed delegation containing objective, governing principles, constraints, acceptance policy, and authority scope. The controller may reject structurally invalid or unauthorized delegation; it must not rewrite purpose.

Controller interactions return typed evidence and decision requests to Telos/operator. Contract amendments are append-only and scoped (`node`, `variant`, `run`); the baseline remains immutable. Merge, deployment, destructive cleanup, and scope expansion require separate explicit authority.

## 8. Persistence, recovery, and liveness

- Event journal is append-only and carries aggregate version, actor, causation, correlation, schema version, and timestamp.
- Materialized views are disposable/rebuildable; they are never independent authority.
- Agent attempts hold renewable leases with fencing tokens. Expired leases become `lost`; late submissions with stale fencing are rejected and retained as evidence.
- External effects use outbox records and idempotency keys.
- Restart recovery first reconciles journal/outbox/leases, then deterministically schedules. It does not infer authority from process presence alone.
- Circuit breakers are per effect/attempt class and produce a durable interaction rather than illegal active limbo.
- Every nonterminal aggregate must satisfy a liveness invariant: executable ready work, an unexpired lease, a scheduled retry, or a durable interaction.

## 9. Events and observability

Minimum event families:

- `run.*`, `node.*`, `attempt.*`, `gate.*`;
- `verification_obligation.*`, `finding.*`, `adjudication.*`;
- `dependency.*`, `artifact.*`, `workspace_lease.*`;
- `interaction.*`, `amendment.*`, `publication.*`, `effect.*`;
- `cognition.p1_attending`, `p2_understanding`, `p3_judging`, `p4_deciding` when reported by a cognitive program.

Events distinguish **domain truth** from diagnostic projections. Every UI status links back to causal events. Sensitive payloads are referenced by redacted artifact IDs, never copied into broad event streams.

## 10. Conformance suite to extract from donors

Before product implementation, transpose donor tests into runtime-neutral fixtures covering:

1. valid and invalid transition matrices; out-of-sequence rejection;
2. graph validation, missing launch material, and future-produced dependencies;
3. concurrent ready nodes and deterministic ordering;
4. WU/attempt completion, QA PASS, QA FAIL→remediation→QA, and exhaustion;
5. exact implementation:QA cardinality;
6. owned-output verification, foreign overlap, ignored proof artifacts, contract amendments;
7. workspace mismatch, contamination, commit/index-lock failure, and publication receipts;
8. restart with active/lost/idle attempts; bounded recovery and fencing;
9. active/remediation/escalated limbo and stale bookkeeping;
10. variant isolation, fail-fast/isolate policy, selection distinct from merge/publication;
11. duplicate commands/effects and stale-version submissions;
12. event/projection correspondence and causation lineage;
13. Telos delegation authority and scoped amendments;
14. adapter parity across at least one headless and one visible runtime.

## 11. Staged implementation gates

- **Stage A — executable specification:** schemas, pure transition reducer, graph validator, model-based/property tests; no external effects.
- **Stage B — durable kernel:** SQLite event journal, version checks, idempotency ledger, outbox, rebuildable projections.
- **Stage C — execution adapters:** fake runtime first; then one headless client adapter and workspace/repository adapter.
- **Stage D — program layer:** development pipeline and one cognitive discipline as versioned programs.
- **Stage E — Telos seam:** typed delegation, interactions, and result/evidence propagation.
- **Stage F — observability:** cognitional-event contract and read-only web/TUI projection before act-from controls.
- **Stage G — controlled donor comparison:** replay conformance fixtures and shadow selected donor scenarios; no production cutover until parity plus improvement evidence exists.

Each stage requires its own implementation:QA pairing, green conformance tests, rollback, and a separately reviewable PR.

## 12. Binding amendments from adversarial review

The design incorporates the blocking findings in `controller-adversarial-review.md`; implementation still waits for the concrete schemas/matrices listed there.

### 12.1 Journal, snapshots, and compaction

The causal journal is authoritative but not naively replayed forever. A verified snapshot records aggregate state, journal position, schema/program versions, and a digest. Rebuild tests compare snapshot-plus-tail projection with full fixture replay. Retention/compaction may archive pre-snapshot events only after digest verification, export, and rollback evidence. Migrations are expand/migrate/contract operations with old-reader fixtures.

### 12.2 Graph legibility

Every run exposes a stable barrier/wave projection, critical path, ordered ready set, and a reason for every blocked node/edge. Programs default to explicit barriers; arbitrary graph edges require rationale. Scheduling keys are persisted with the program version so historical order remains explainable.

### 12.3 Authority denial matrix

Before Stage A, define and test a canonical **authority matrix** (actor×command) for `telos`, `operator`, `controller`, `implementation_agent`, `qa_agent`, and `adapter`. Authority has scope, expiry, issuer, and revocation. Delegation can narrow but cannot broaden authority. Adapters transport authority but cannot create it. Negative tests are required for every denied cell.

### 12.4 Repository/publication race semantics

Publication commands carry canonical `expected_workspace_fence`, `expected_base_revision`, `expected_head_revision`, `expected_remote_revision`, and `required_check_policy` fields. Commit, push, PR creation, merge, deployment, and cleanup are separate idempotent effects with receipts. Mismatch produces a durable blocked interaction; the controller never silently rebases, force-pushes, or bypasses branch protection.

### 12.5 Verification generations

An implementation **generation** is one accepted submission from one attempt. Acceptance atomically creates exactly one verification obligation identified by `(node_id, implementation_generation)`. Duplicate delivery returns its existing receipt. A failed verification may authorize a remediation generation, which creates exactly one new obligation. Storage constraints and property tests enforce cardinality.

### 12.6 Privacy, time, model, and program versions

- Events declare `public`, `internal`, or `sensitive_reference`; secrets, full prompts, private artifacts, credentials, and critical-contact data are references only and subject to redaction tests.
- Lease durations use an injected monotonic clock; wall time is audit metadata only.
- Model-selection evidence persists genus request, policy version, availability-snapshot identity, selected reference, and fallbacks.
- Active runs pin immutable program/graph versions; evolution creates a new version or an authorized compatibility-checked amendment.
- ContextForge and a direct in-memory/reference event sink require parity fixtures before transport changes.

## 13. Explicit non-goals

- Recreating noetic-pi's web terminal or tmux mediator in the kernel.
- Making ContextForge the domain boundary or decommissioning ContextForge where tools depend on it.
- Letting the controller perform semantic evaluation with regex/heuristics.
- Claiming exactly-once distributed effects.
- General-purpose distributed workflow orchestration before noetic-dev conformance is proven.
- Coupling Stage A–B progress to saeproj model-training outcomes.
