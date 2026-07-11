# Controller donor conformance inventory

**Issue:** [#7](https://github.com/somebloke1/noetic-dev/issues/7)
**Purpose:** convert donor behavior and failure lessons into runtime-neutral noetic-dev conformance fixtures. This is an inventory, not copied test code.

## 1. Frozen donor baselines

| Donor | Commit | Evidence scale | Role |
|---|---|---:|---|
| `noetic-pi-docker` | `30de068b651c35a475a282e2c8dabe883b77c1a0` | 101 APM test files; 2,261 `it/test` cases | forward authoritative donor |
| `noetic-pi` | `683b53b06714d0aadd49c5852140b708c5abba69` | historical implementation/export lineage | historical comparison only |
| `pi2` | `17cdb45b5711a6ae76888350ff5d89c5f2a24c89` | 25 files; 458 cases | state-machine, succession, tmux, minimal-bootstrap lineage |

Paths below are relative to the named donor root. Test titles are evidence locators, not specifications to reproduce mechanically.

## 2. Priority vocabulary

- **P0:** kernel safety/liveness/authority; required before external effects.
- **P1:** required before real agents/repositories/programs.
- **P2:** required before observability/attach/release promotion.

Disposition:

- **Preserve:** behavior is a target invariant.
- **Improve:** preserve intent but require a stronger noetic-dev result.
- **Negative:** donor behavior becomes a regression case proving noetic-dev rejects it.
- **Gap:** no sufficient donor fixture exists; create a new fixture.

## 3. Transition and command kernel

| ID | Priority | Disposition | Runtime-neutral obligation | Donor provenance | noetic-dev expectation |
|---|---|---|---|---|---|
| TR-01 | P0 | Improve | accepted transition atomically records causal event | `packages/apm/test/unit/state-machine.test.ts` “updates state AND records event”; `state-machine.ts` | crash injection proves no state-without-event or event-without-state window |
| TR-02 | P0 | Preserve | wrong-state command rejects without mutation and explains required state | implementation/plan/phronesis/EP/succession `transitions.test.ts`, `validation.test.ts`; pi2 `unit/state-machine.test.js` | typed rejection includes aggregate/version/current/allowed transitions |
| TR-03 | P0 | Preserve | malformed payload cannot mutate state | implementation/plan/phronesis/EP/succession `validation.test.ts` | versioned schema errors are deterministic; retry guidance does not imply acceptance |
| TR-04 | P0 | Preserve | terminal states are monotonic and contain live actors/interactions | implementation/plan/phronesis/EP/succession `containment.test.ts` | reopen creates linked generation; no terminal mutation |
| TR-05 | P0 | Gap | duplicate command is exactly-once accepted | partial evidence: orchestration same-variant reselection idempotency in `unit/implement.test.ts` | any duplicate idempotency key returns original receipt, no new events/effects |
| TR-06 | P0 | Gap | optimistic version race has one winner | no complete donor fixture | concurrent same-version commands: one accepted, one typed stale-version rejection |
| TR-07 | P1 | Preserve | graph/source/handler declarations correspond | `state-machines/__tests__/{transition-structure,handler-correspondence,source-conformance}.test.ts` | generated transition tables, reducer, commands, and emitted events remain bijectively checked |
| TR-08 | P1 | Preserve | child→parent composition is declared and valid | `state-machines/__tests__/composition.test.ts`; implementation `composition.test.ts` | composition is graph policy, not hidden callback mutation |

## 4. Dependency and scheduling

| ID | Priority | Disposition | Obligation | Donor provenance | noetic-dev expectation |
|---|---|---|---|---|---|
| SC-01 | P0 | Preserve | unknown, same/later illegal dependencies are rejected | `unit/implement.test.ts`: duplicate/unassigned WUs, same/later wave, unknown dependency | graph validation rejects unknown/cyclic edges; bounded loops require explicit policy |
| SC-02 | P0 | Preserve | ready-set ordering is deterministic under input permutation | `unit/orchestration-runtime.test.ts`: queue position then variant number, tied-order determinism | stable `(barrier, priority, topo rank, node id)` ordering property |
| SC-03 | P0 | Preserve | concurrency never exceeds configured limit | `unit/orchestration-runtime.test.ts`; integration “bounded concurrency K<N” | property test over arbitrary completion/failure order |
| SC-04 | P0 | Preserve | composite barrier waits while children are mixed active/complete | implementation `composition.test.ts` comp-eval-1..3 | barrier policy explains every waiting child/edge |
| SC-05 | P1 | Improve | waves remain legible barriers without forbidding valid DAG parallelism | implementation wave transitions; plan sequential composition | wave projection + critical path + blocked-edge explanation for any graph |
| SC-06 | P1 | Preserve | isolate/fail-fast policies diverge deterministically | implementation `composition.test.ts`; `integration/implementation-orchestration-flow.test.ts`; `unit/implement.test.ts` | policy is versioned and visible; fail-fast settles peers exactly once |
| SC-07 | P1 | Gap | quorum/policy-selected barrier settlement | no donor fixture | declared policy with deterministic settlement and explanation |

## 5. Implementation, QA, remediation, and evidence

| ID | Priority | Disposition | Obligation | Donor provenance | noetic-dev expectation |
|---|---|---|---|---|---|
| QA-01 | P0 | Preserve | all implementation units submitted → QA obligation | implementation `transitions.test.ts` wave-t2a; `composition.test.ts` comp-eval-1 | implementation generation atomically creates exactly one verification obligation |
| QA-02 | P0 | Preserve | QA PASS permits publication checkpoint | wave-t3a/t3b; integration orchestration flow | only settled obligation + structural proof enables publication intent |
| QA-03 | P0 | Preserve | QA FAIL with budget → targeted remediation → fresh QA | wave-t4/t4b, WU-t5/t6; corrective package | remediation generation reopens only blocking work and creates exactly one new obligation |
| QA-04 | P0 | Preserve | exhausted unchanged findings settle blocked, not endless active loop | wave-t5; case-history stable blocked/recurrence tests | recurrence lineage and bounded policy create durable interaction |
| QA-05 | P0 | Preserve | blocking/non-blocking/waived/superseded adjudication remains append-only | `unit/implementation-case-history.test.ts`; corrective package integration | semantic evidence attributed to QA/operator; baseline verdict not rewritten |
| QA-06 | P0 | Gap | exact implementation-generation:QA cardinality under duplicate/retry/crash | no storage-enforced donor fixture | property/storage constraint proves one and only one obligation per generation |
| QA-07 | P1 | Preserve | repeated low-information escalation requires richer evidence | `unit/implementation-case-history.test.ts`; implementation validation | deterministic diagnostic obligation without judging semantic truth in code |
| QA-08 | P1 | Negative | stale correlation routed by agent ID | implementation transitions/validation and corrective package fallback tests | reject stale/mismatched correlation; recovery uses explicit reconciliation command |
| QA-09 | P1 | Preserve | markdown/content cannot alter control flow | phronesis/EP/succession validation | only typed payload fields drive transitions |

## 6. Contract, artifact, and workspace authority

| ID | Priority | Disposition | Obligation | Donor provenance | noetic-dev expectation |
|---|---|---|---|---|---|
| WS-01 | P0 | Preserve | explicit workspace context required for mutation | `unit/git-workspace.test.ts`; variant execution context | workspace handle + fencing token, never ambient cwd/path inference |
| WS-02 | P0 | Preserve | only owned declared outputs satisfy completion | `unit/implement.test.ts`; `integration/variant-execution-context.test.ts` | artifact digest/provenance; unrelated changes cannot satisfy node |
| WS-03 | P0 | Preserve | repository deliverables vs verifier-only/controller/sibling artifacts stay distinct | corrective package integration; blocker-family tests | typed artifact planes, no overlapping output ambiguity |
| WS-04 | P0 | Preserve | scoped amendments compose deterministically and do not leak | `unit/implement.test.ts` invocation→variant→WU overlays; corrective package | append-only baseline/effective contract with authority scope |
| WS-05 | P0 | Preserve | missing/foreign/root-only workspace evidence fails closed | variant execution context; workspace authority audit | no fallback to legacy or ambient path; structured reason |
| WS-06 | P1 | Preserve | managed cleanup never touches unmanaged paths and does not rewrite outcome | variant workspace unit/integration cleanup tests | separate cleanup effect, receipt, retention policy |
| WS-07 | P1 | Improve | commit/stage uses expected workspace/base/head and explicit outputs | `unit/git-workspace.test.ts`; wave commit paths | repository port with revision/fence preconditions and idempotent receipts |
| WS-08 | P1 | Gap | remote branch/check/merge race | donor merge conflict/failure tests are partial | mismatch blocks; no silent rebase/force/bypass; publication effects remain distinct |
| WS-09 | P1 | Preserve | runtime contract dimensions remain distinct | runtime-contract tests; implementation flow continuity/host/runtime/boundary/readiness | typed resource predicates; no single “ready” overclaim |

## 7. Recovery, liveness, and fencing

| ID | Priority | Disposition | Obligation | Donor provenance | noetic-dev expectation |
|---|---|---|---|---|---|
| RC-01 | P0 | Preserve | restart detects active/remediation/QA work lacking actor | implementation recovery and crash-window composition tests | expired lease marks attempt lost; scheduler issues fenced replacement |
| RC-02 | P0 | Improve | bounded retries trip a circuit breaker | `implementation-recovery.ts`; recovery tests | retry policy event + durable interaction; never illegal active limbo |
| RC-03 | P0 | Preserve | limbo/stale bookkeeping classified and surfaced | stalled-wave/corrective package/runtime truth tests | stronger invariant prevents it; classifier remains a defensive fixture |
| RC-04 | P0 | Gap | stale fenced submission after replacement | no donor fixture | stale token cannot mutate; payload retained as rejected evidence |
| RC-05 | P0 | Gap | crash at each event/outbox/effect/receipt boundary | donor non-atomic window tests are partial | model-based fault injection proves convergence/idempotency |
| RC-06 | P1 | Preserve | escalation interactions and notifications recover without creating truth | recovery re-send tests | notification is effect only; interaction/event journal is authority |
| RC-07 | P1 | Improve | idle detection | donor elapsed wall-clock idle tests | injected monotonic lease time; wall clock only audit metadata |
| RC-08 | P1 | Preserve | terminal containment retires/clears actors and interactions | containment tests across all machine families | no live lease on terminal aggregate; cleanup remains separate |

## 8. Orchestration, variants, and publication

| ID | Priority | Disposition | Obligation | Donor provenance | noetic-dev expectation |
|---|---|---|---|---|---|
| OR-01 | P0 | Preserve | variant isolation and authoritative workspace identity | variant context, workspace authority, orchestration integration | every variant has fenced resource scope; no shared mutable authority |
| OR-02 | P0 | Preserve | selection is distinct from merge/publication | implementation composition and manual select/merge tests | independent commands, authority, expected revisions, events, receipts |
| OR-03 | P0 | Preserve | reselection same target idempotent; different target fails closed | `unit/implement.test.ts`; integration selection tests | original decision receipt returned; no timestamp/history rewrite |
| OR-04 | P1 | Preserve | batch vs incremental eligibility and fail-fast bypass | orchestration runtime/unit/integration tests | policies versioned and explainable |
| OR-05 | P1 | Preserve | terminal lineage additive to outcome/actionability | integration blocker-lineage tests | causal lineage separate from lifecycle projection |
| OR-06 | P1 | Preserve | cleanup/retention does not imply or rewrite completion | orchestration flow cleanup/disposition tests | explicit retention/publication/cleanup effects |

## 9. Cognitive-program fixtures

| ID | Priority | Disposition | Obligation | Donor provenance | noetic-dev expectation |
|---|---|---|---|---|---|
| CP-01 | P1 | Preserve | P1→P2→P3→P4 sequence plus bounded recursion to earlier operations | phronesis `transitions.test.ts`, recursion integration | versioned program graph; P1 cannot recurse; limit enforced structurally |
| CP-02 | P1 | Preserve | grounding before active work and minimal bootstrap | phronesis grounding/env-var tests; pi2 prompt/tmux tests | structured context delivery via runtime port, no control state in environment |
| CP-03 | P1 | Preserve | complete state×command matrices | EP audit and succession `completeness.test.ts` | generate matrix from schema; every cell transition/reject/read/no-op explicit |
| CP-04 | P1 | Preserve | synchronization barrier requires both parties | succession transitions/flow | general multi-party gate with idempotent arrivals and crash recovery |
| CP-05 | P1 | Preserve | plan produce→QA→remediation and gated/auto advancement | plan transitions/composition/recovery | program expressed on generic controller primitives, not separate runtime |
| CP-06 | P2 | Preserve | terminal containment and agent retirement for every program | all family containment suites | attempts/leases settle; process cleanup is adapter effect |

## 10. Events, projections, authority, and privacy

| ID | Priority | Disposition | Obligation | Donor provenance | noetic-dev expectation |
|---|---|---|---|---|---|
| EV-01 | P0 | Improve | state transition and event correspond | unit state-machine + source-conformance tests | atomic journal append; projection rebuild equality |
| EV-02 | P0 | Gap | command actor authority denial matrix | partial role/phase validation only | negative fixture for every denied actor×command cell |
| EV-03 | P0 | Gap | event privacy/redaction | no sufficient donor fixture | secrets, critical contact, prompts, private artifacts remain references only |
| EV-04 | P1 | Preserve | causation/correlation and escalation recurrence lineage | case-history/callbacks | immutable IDs and explicit supersession; no fallback routing |
| EV-05 | P1 | Gap | direct sink vs ContextForge parity | no sufficient donor fixture | same canonical events/order/redaction across sinks |
| EV-06 | P1 | Gap | snapshot + tail rebuild and compaction | donor snapshots are diagnostics, not authoritative rebuild | verified snapshot digest, migration and rollback fixtures |
| EV-07 | P1 | Preserve | statuses explain actionability without inlining forensic history | runtime truth status/diagnose tests | read models link to causal events and blocked-edge explanations |

## 11. Runtime/attach adapter fixtures

| ID | Priority | Disposition | Obligation | Donor provenance | noetic-dev expectation |
|---|---|---|---|---|---|
| AD-01 | P1 | Preserve | minimal spawn bootstrap under transport limits | pi2 `unit/phronesis-prompts.test.js`, `unit/tmux.test.js` | runtime adapter receives small identity; full context via structured channel |
| AD-02 | P1 | Preserve | runtime identity and reconnect/heartbeat | pi2 census/health/snapshot tests; noetic-pi connection/recovery | attempt lease identity independent of pane/PTY/client process |
| AD-03 | P2 | Preserve | attach unavailable does not break controller truth | pi2 snapshot “tmux unavailable”; noetic-pi event-driven observability | attach is optional projection/adapter |
| AD-04 | P2 | Gap | headless/visible runtime parity | no cross-client donor fixture | reference fake + at least one headless and one visible adapter contract suite |

## 12. Explicit donor behaviors not to transpose

1. Non-atomic status update followed by actor ID/event update.
2. Agent-ID fallback after correlation mismatch.
3. Arbitrary SQL table/field mutation through a generic state-machine helper.
4. Runtime truth reconstructed from independently mutable lifecycle/readiness/actionability fields.
5. Ambient cwd, absolute paths, tmux panes, PTYs, or client process objects in the domain kernel.
6. Legacy dual carriers, synthesized legacy amendments, or compatibility fallbacks in the initial noetic-dev schema.
7. Treating waves as the only graph topology.
8. Treating “nothing to commit” as success without program-declared no-change evidence.
9. Re-spawn based only on process absence/elapsed wall time without fencing.
10. Notification delivery as proof of transition or authority.

## 13. Transposition process

For each P0/P1 fixture family:

1. cite donor commit, file, and test title;
2. restate the invariant without donor runtime nouns;
3. mark preserve/improve/negative/gap;
4. create a minimal command/event graph fixture;
5. implement against the pure Stage A kernel or fake port;
6. run one paired adversarial QA pass that mutates ordering, duplicates, crashes, stale versions, and denied authority;
7. record divergence rationale if noetic-dev intentionally improves donor behavior.

No donor test file is copied wholesale. Provenance remains evidence; noetic-dev fixtures become the portable contract.
