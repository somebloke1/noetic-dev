# noetic-dev Delivery Roadmap

**Status:** Canonical aggregate delivery plan, version 1
**Exact checkpoint:** `dev@15b9ae66ff316abf28a5041c465e95baef5e82f9` on 2026-07-18
**Portfolio authority:** [GitHub issue #32](https://github.com/somebloke1/noetic-dev/issues/32)
**Machine index:** [`governance/roadmap.json`](governance/roadmap.json)

This roadmap turns the architecture in [`SYNTHESIS.md`](SYNTHESIS.md) into a
dependency-ordered delivery program with explicit exit gates. It supersedes issue
#5 and its branch as execution-order authority; that work remains donor evidence.
A candidate edit is not authoritative merely because it exists. The last copy
merged through the then-effective governed branch flow is authoritative.

## 1. Authority and persistence

No single artifact should silently answer every kind of question.

| Artifact | Authority | Does not override |
|---|---|---|
| [`AGENTS.md`](AGENTS.md) and accepted [`DECISIONS.md`](DECISIONS.md) entries | Invariants, adjudicated architecture, and policy | Verified counterevidence or a later explicit decision |
| This roadmap | Aggregate dependency order, stage boundaries, exit gates, and exact checkpoints | Accepted decisions, issue lifecycle labels, or verification evidence |
| GitHub issue #32 | Portfolio coordination and disposition | Bounded child-issue scope or merged repository contracts |
| Bounded issues and `status:*` labels | Accepted work scope and lifecycle state | Architecture or evidence |
| Pull requests, CI, and QA records | Candidate, review, merge, and test evidence | The meaning assigned by contracts and decisions |
| [`KNOWNS.md`](KNOWNS.md), [`DECISIONS.md`](DECISIONS.md), and [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) | Verified facts, judgments, and uncertainty respectively | Each other's distinct operation |
| Goalchains | Purpose, active continuity, and learnings across sessions | Git-tracked portfolio status or completion evidence |

If these sources conflict, stage advancement stops. The conflict is recorded in
the appropriate ledger and resolved by an issue-scoped decision and repository
change. Prose does not override machine lifecycle state.

Durability uses four layers:

1. `ROADMAP.md` stores the human-readable plan in Git.
2. `governance/roadmap.json` stores the machine-checked checkpoint and graph.
3. GitHub issues, PRs, checks, and QA artifacts store executable work and evidence.
4. Goalchains mirror active purpose and residue, but are not the project source of truth.

`scripts/validate_repo.py` rejects a missing roadmap, an invalid machine record,
unknown or cyclic dependencies, checkpointed stages without evidence, a `next`
stage whose prerequisites are not checkpointed, or drift between the JSON stage
index and the headings below.

## 2. Status and completion semantics

- `checkpointed`: present at the exact baseline with bounded evidence. It does
  not mean production-ready, published, or complete under the delivery state
  machine.
- `next`: the single convergence gate that must be resolved before later stages.
- `planned`: ordered but not authorized as implemented or complete.
- `blocked`: explicitly stopped by a named unresolved condition.

An implementation stage is not complete from prose, a local branch, or a green
candidate alone. Its exit gate requires the then-effective target branch, exact
merged SHA, linked issue and PR, CI results, one independent adversarial QA pass
per implementation generation, and any stage-specific evidence. A follow-up
checkpoint change records the merged evidence; a candidate must not predict its
own eventual squash or rebase SHA.

The repository currently contains contradictory `dev` integration and `main`
delivery rules. Until D2 resolves them, `checkpointed` means only that the
bounded artifact is present at the exact `dev` baseline. It is not a publication
or release claim.

## 3. Exact checkpoint and non-claims

The baseline contains three bounded foundations:

- Repository and governance bootstrap, including issue/PR discipline, policy
  contracts, tests, and protected-review infrastructure.
- Fixed provider-free M0 and M1 traces, `development.verified-change/v1`, and
  terminal observability/status projections.
- A protected-review genus-router/LiteLLM and route-attestation slice.

These foundations do **not** establish a production Telos dispatcher, portable
executive controller, authenticated runtime authority, general cognitive-program
engine, live cognitional-event plane, attach layer, reproducible multi-component
composition, or release trust root. M0/M1 and their projections remain fixed
conformance fixtures rather than disguised runtime implementations.

Issue #65 remains a bounded non-evidence OpenCode experiment even if its own
change later merges. Production readiness requires a separately scoped successor
with its own evidence and gates.

## 4. Dependency graph

```text
D0 ---> D1a ---+
  +---> D1b ---+--> D2 --> D3a --> D3b
                                      +--> D4a --+
                                      +--> D4b --+--> D4d --> D5 --> D6 --> D7 --> D8 --> D9
                                      +--> D4c --+
```

D4a-D4c may proceed in parallel only after D3b. D4d binds their exact merged
component revisions before any live vertical-slice claim. Research and trials
listed later are parallel but cannot silently satisfy a stage gate.

## 5. Delivery stages

### D0 - Repository and governance bootstrap [checkpointed]

- **Dependencies:** none.
- **Bounded claim:** the thin composition root, governance vocabulary, validation,
  tests, and issue/PR practices exist at the exact baseline.
- **Evidence:** bootstrap commit `29196a67349537d6f8a8a711df11b86da0430857`,
  checkpoint commit `15b9ae66ff316abf28a5041c465e95baef5e82f9`,
  and issue #32.
- **Non-claim:** the active existing-work freeze and bootstrap publication record
  are not thereby resolved.
- **Checkpoint gate:** repository artifacts and their bounded contracts are present
  at the exact baseline; later governance convergence remains D2.

### D1a - Fixed provider-free reference proofs [checkpointed]

- **Dependencies:** D0.
- **Bounded claim:** M0 direct-pass, M1 bounded remediation,
  `development.verified-change/v1`, and terminal observability/status projections
  are integrated as deterministic reference artifacts.
- **Evidence:** integration commits `f5efd668304a7dbade20bd20704ed4930cbecef9`,
  `0ab63d8fac1ceadfaca72717e62ff1d564c81e0e`,
  `38c2812eca31983e39f8705f7bc7aed05df31329`, and
  `b846efa0392eda96a58e1b6d099c9e39385cac58`.
- **Non-claim:** no dispatch, scheduling, persistence, real authority, live state,
  tool effect, or crash recovery is proved.
- **Checkpoint gate:** frozen contracts, fixtures, reducers, and read models are
  present and retain their documented non-claims.

### D1b - Protected-review routing and attestation slice [checkpointed]

- **Dependencies:** D0.
- **Bounded claim:** protected review can route through the external genus-router
  and LiteLLM policy, and a trusted local operator can retain bounded route
  attestation evidence.
- **Evidence:** route-attestation integration commit
  `58c4c791d7f39c0a6eca0dc7b1ddfd8bb67d02b2`, retained canary PR #64,
  workflow run `29629152718`, and checkpoint commit
  `15b9ae66ff316abf28a5041c465e95baef5e82f9`.
- **Non-claim:** this is not general runtime migration, cryptographic workflow-path
  provenance, or publication authority.
- **Checkpoint gate:** the bounded review route and attestation slice is present;
  its residual trust limits remain explicit.

### D2 - Governance and source convergence [next]

- **Dependencies:** D0, D1a, D1b.
- **Scope:** resolve rather than paper over current authority drift:
  - autonomous `dev` integration versus the `main`-based delivery state machine;
  - the active existing-work freeze and stale bootstrap-status record;
  - P1-P4 decision metadata versus the still-unratified notation document;
  - endpoint pluralism in decision 0005 versus mandatory LiteLLM machine policy;
  - stale phase, routing, migration, and abeyant-plan statements;
  - issue #32, this roadmap, issue labels, and goalchain precedence.
- **Exit gate:** accepted decisions name one branch flow and authority matrix; the
  audit freeze is completed or explicitly superseded with reviewed evidence;
  machine policies and prose agree; unresolved choices are in
  `OPEN_QUESTIONS.md`; issue #32 and the roadmap checkpoint agree; repository
  validation and the generation's independent QA pass.

### D3a - Donor characterization and design decisions [planned]

- **Dependencies:** D2.
- **Scope:** pin donor and component SHAs; select conformance fixtures; decide the
  controller home and component-reference mechanism; choose the first reference
  runtime; define principal authentication, authorization, credential boundaries,
  independently bound QA identity, effect capabilities, expiry/revocation,
  persistence consistency, event privacy/redaction, and compatibility policy.
- **Exit gate:** each choice has an accepted decision, falsifiers, rollback or
  migration implications, and a pinned donor characterization suite. No controller
  implementation starts from an unrecorded assumption.

### D3b - Versioned connective contracts [planned]

- **Dependencies:** D3a.
- **Scope:** version controller state/transitions, work and typed dependency roles,
  delegation/result/cancellation, delivery/idempotency/reconciliation, authority,
  event envelope, storage/effect ports, and component pin manifests.
- **Exit gate:** schemas and fixtures are versioned; invalid ordering, authority,
  replay, cancellation, and compatibility cases fail closed; property/model tests
  and independent adversarial QA pass; component homes and evolution rules are
  explicit.

### D4a - Portable executive controller [planned]

- **Dependencies:** D3b.
- **Home:** an independently testable controller component referenced by this root.
- **Scope:** deterministic wave sequencing, typed dependency legality, ordinal
  identity, QA/remediation accounting, effect and commit boundaries, controlled
  cancellation/exhaustion, durable journal/rebuild, and one reference persistence
  implementation with fault injection.
- **Exit gate:** conformance against M0/M1 plus scheduling, duplicate, restart,
  stale writer, cancellation, exhaustion, and recovery tests. Semantic judgment
  remains attributed to agents rather than encoded as deterministic truth.

### D4b - Telos delegation dispatcher [planned]

- **Dependencies:** D3b.
- **Home:** Telos, with a pinned interface consumed by this composition root.
- **Scope:** at-least-once delivery with durable idempotency keys, deduplicated
  admission, replay-safe results, cancellation, retries, and reconciliation. Do
  not claim impossible cross-system exactly-once execution.
- **Exit gate:** a `delegated-pending` goal can be admitted without duplicate work,
  resumed after crash, cancelled under authority, and returned for separate Telos
  adjudication; ambiguous effects reconcile or fail closed.

### D4c - Selected runtime and model adapters [planned]

- **Dependencies:** D3b.
- **Scope:** implement only the reference runtime, scoped tool/effect path,
  independently bound QA path, and policy-compliant model routes needed by D5.
  Broader OpenCode, Pi, embedding, and ASR migration remains separately tracked.
- **Exit gate:** principal and credential boundaries are tested; every model call
  follows the accepted route/invoke/outcome policy; direct bypass, model drift,
  duplicate effect, expired capability, and outcome-report failure fail closed.

### D4d - Pinned integration skeleton [planned]

- **Dependencies:** D4a, D4b, D4c.
- **Home:** this composition root.
- **Scope:** add the minimum `compose/` binding, exact component manifest, durable
  state/event journal, compatibility checks, cross-component contract tests, and
  rollback procedure needed before a live claim.
- **Exit gate:** a clean environment resolves exact component revisions, starts the
  bounded composition, rejects incompatible contracts, preserves/replays evidence,
  and rolls back without losing the last known-good checkpoint.

### D5 - Authentic bounded vertical slice [planned]

- **Dependencies:** D4d.
- **Scope:** execute one bounded real effect from authenticated Telos delegation
  through dispatcher, controller, implementer, independent QA, replay-safe result,
  and separate Telos adjudication.
- **Exit gate:** exact pins and principals are recorded; retries, duplicates,
  crash/restart, cancellation, stale results, audit replay, and rollback are forced;
  every effect is bounded and attributable; the final claim survives one paired
  adversarial QA pass and the then-effective protected integration gates.

### D6 - Cognitive programs [planned]

- **Dependencies:** D5.
- **Scope:** independently version one cognitive discipline, then the general
  development pipeline over the controller. Preserve selected donor invariants and
  fixtures without importing donor runtime coupling.
- **Exit gate:** program lifecycle, packets, evidence, recursion, semantic gates,
  and QA/remediation mapping conform across a fake runtime and the D5 reference
  runtime. `development.verified-change/v1` remains a bounded fixture adapter, not
  the generic engine.

### D7 - Read-only live observability [planned]

- **Dependencies:** D5, D6.
- **Scope:** derive current state, causal history, readiness/blocking, critical
  path, agent census, and QA lineage from persisted cognitional events. Deliver a
  read-only web or TUI surface first.
- **Exit gate:** reconnect/replay is deterministic; redaction and tenant/authority
  boundaries are tested; views identify missing or contradictory events rather
  than inventing state; no command authority is exposed. Privileged control needs
  a separate accepted threat model and decision.

### D8 - Attach and composition hardening [planned]

- **Dependencies:** D7.
- **Scope:** reproduce the full composition from clean state, test upgrades and
  rollback, and add tmux-native attach as the default live-visibility adapter.
  Browser PTY remains optional and non-load-bearing.
- **Exit gate:** clean install, restart, upgrade, rollback, identity, reconnect,
  command-length, isolation, and security drills pass against exact component pins.
  Attach loss cannot corrupt controller state or event evidence.

### D9 - Release and publication [planned]

- **Dependencies:** D2, D8.
- **Scope:** resolve licensing, complete the final existing-work and security audit,
  establish the distinct protected trust root required by current governance,
  verify protected `main`, and publish only an exact post-merge SHA.
- **Exit gate:** the authoritative delivery and publication gates pass without
  advisory substitutions; post-merge validation, recovery and security evidence,
  independent approval, artifact provenance, license, release notes, rollback, and
  an immutable tag all bind the same full `main` SHA.

## 6. Parallel non-gating tracks

- **T1 - saeproj research:** improve model cognition and evaluation without gating
  D2-D9.
- **T2 - client trials:** compare OpenCode, Pi, and other candidates for usability;
  changing the D3a reference runtime still requires an explicit decision.
- **T3 - ContextForge:** retain as evidence and use only if a concrete multi-host
  transport requirement survives comparison with plain MCP.
- **T4 - issue #65:** preserve as a source-free, no-tools, non-evidence OpenCode
  experiment. Merge does not promote it to runtime evidence; a successor must do so.

## 7. Explicit unresolved conflicts

The machine index records which stages these conflicts block:

1. `C1`: `dev` integration and `main` delivery policy disagree.
2. `C2`: the active freeze/bootstrap records lag the represented portfolio state.
3. `C3`: P1-P4 is operationally canonical but formally awaits ratification.
4. `C4`: endpoint pluralism conflicts with mandatory LiteLLM access policy.
5. `C5`: the first production reference runtime is not selected.
6. `C6`: principal, effect, persistence, and event-privacy semantics are undecided.
7. `C7`: privileged observability controls have no accepted authority model.
8. `C8`: license and distinct release trust root remain unresolved.

These are gates, not invitations to guess.

## 8. Change protocol

1. Verify current repository and GitHub facts at exact SHAs; record new facts in
   `KNOWNS.md` rather than this roadmap.
2. Record architectural or policy changes in `DECISIONS.md`, and unresolved choices
   in `OPEN_QUESTIONS.md`.
3. Update the bounded issue, this document, and `governance/roadmap.json` together
   when order, status, dependencies, evidence, or gates change.
4. Run repository validation, affected tests, and exactly one independent
   adversarial QA pass for each implementation/remediation generation.
5. After integration, use a follow-up checkpoint change to record the actual merged
   SHA and durable issue/PR/CI/QA evidence.
6. Update issue #32 for portfolio visibility. Git history remains the durable audit;
   GitHub metadata coordinates execution but does not replace it.

## 9. Deprecation and replacement rules

- Issue #5 and its roadmap branch are donor evidence, not current ordering authority.
- M0/M1 and terminal projections remain conformance fixtures; do not evolve them
  into the controller by accretion.
- Do not block delivery on unlocking the noetic-pi export. Re-instantiate verified
  invariants behind portable contracts.
- ContextForge is not the integration backbone unless a demonstrated requirement
  and accepted decision promote it.
- Terminal and browser PTY mechanisms are attach adapters, not the observability or
  controller core.
- Retire a donor or legacy path only after its accepted successor has parity,
  migration, and rollback evidence.
