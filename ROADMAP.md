# noetic-dev Delivery Roadmap

**Status:** Canonical aggregate delivery plan, version 2
**Exact checkpoint:** `dev@15b9ae66ff316abf28a5041c465e95baef5e82f9` on 2026-07-18
**Portfolio authority:** [GitHub issue #32](https://github.com/somebloke1/noetic-dev/issues/32)
**Machine index:** [`governance/roadmap.json`](governance/roadmap.json)
**Policy snapshot:** freeze=repair_authorized; publication=blocked; delivery_gate=external_dependency_missing

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

Schema version 2 closes the stage, parallel-track, unresolved-conflict, and checkpoint-evidence
catalogs. Adding, removing, or reassigning one of those identities requires an
explicit schema/validator successor and migration tests, not an in-place mutation.
The machine index also pins the SHA-256 of this entire document, so scope,
non-claims, and explanatory prose cannot drift outside the paired contract.
The schema also pins the exact D2 and D9 policy gates rather than searching for
keywords.

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

Protected `dev` is the feature-integration branch. Promotion of an exact validated
`dev` SHA to protected `main` requires explicit repository-owner approval and the
stronger release gate. `checkpointed` remains an integration claim, never a
publication or release claim.

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
- **Evidence refs:** `commit:29196a67349537d6f8a8a711df11b86da0430857`,
  `commit:15b9ae66ff316abf28a5041c465e95baef5e82f9`,
  `issue:https://github.com/somebloke1/noetic-dev/issues/32`.
- **Bounded claim:** the thin composition root, governance vocabulary, validation,
  tests, and issue/PR practices exist at the exact baseline.
- **Non-claim:** the review-pending existing-work audit does not resolve the
  distinct release trust root or establish publication authority.
- **Exit gate:** Repository and governance artifacts are present at the exact
  baseline without claiming publication readiness.

### D1a - Fixed provider-free reference proofs [checkpointed]

- **Dependencies:** D0.
- **Evidence refs:** `commit:f5efd668304a7dbade20bd20704ed4930cbecef9`,
  `commit:0ab63d8fac1ceadfaca72717e62ff1d564c81e0e`,
  `commit:38c2812eca31983e39f8705f7bc7aed05df31329`,
  `commit:b846efa0392eda96a58e1b6d099c9e39385cac58`.
- **Bounded claim:** M0 direct-pass, M1 bounded remediation,
  `development.verified-change/v1`, and terminal observability/status projections
  are integrated as deterministic reference artifacts.
- **Non-claim:** no dispatch, scheduling, persistence, real authority, live state,
  tool effect, or crash recovery is proved.
- **Exit gate:** Frozen M0, M1, verified-change, and terminal projection contracts
  remain present with all documented non-claims.

### D1b - Protected-review routing and attestation slice [checkpointed]

- **Dependencies:** D0.
- **Evidence refs:** `commit:58c4c791d7f39c0a6eca0dc7b1ddfd8bb67d02b2`,
  `pull_request:https://github.com/somebloke1/noetic-dev/pull/64`,
  `workflow_run:https://github.com/somebloke1/noetic-dev/actions/runs/29629152718`,
  `commit:15b9ae66ff316abf28a5041c465e95baef5e82f9`.
- **Bounded claim:** protected review can route through the external genus-router
  and LiteLLM policy, and a trusted local operator can retain bounded route
  attestation evidence.
- **Non-claim:** this is not general runtime migration, cryptographic workflow-path
  provenance, or publication authority.
- **Exit gate:** The bounded protected-review route and attestation slice is present
  while its trust and runtime non-claims remain explicit.

### D2 - Governance and source convergence [next]

- **Dependencies:** D0, D1a, D1b.
- **Evidence refs:** `artifact:governance/audits/20260718-d2-portfolio/inventory.json`,
  `issue:https://github.com/somebloke1/noetic-dev/issues/32`.
- **Scope:** integrate the accepted convergence decisions and their machine/prose
  projections:
  - protected `dev` feature integration followed by owner-authorized promotion of
    an exact validated dev SHA to protected `main`;
  - complete 12-PR/26-branch/20-issue inventory awaiting protected independent
    review while publication remains blocked;
  - ratified P1-P4 canonical notation with fixed human gloss and optional ECN
    modality markers;
  - mandatory LiteLLM access for every noetic-dev model invocation, including
    embeddings and ASR, with genus-router retaining model selection;
  - issue #32 as portfolio coordination, this roadmap as aggregate order, labels as
    lifecycle state, and Git/PR/check/QA records as implementation evidence.
- **Exit gate:** Accepted authority and branch-flow decisions, reviewed freeze
  disposition, consistent machine and prose policy, synchronized issue 32 and
  roadmap, green validation, and paired independent QA.

### D3a - Donor characterization and design decisions [planned]

- **Dependencies:** D2.
- **Evidence refs:** none.
- **Scope:** pin donor and component SHAs; select conformance fixtures; decide the
  controller home and component-reference mechanism; choose the first reference
  runtime; define principal authentication, authorization, credential boundaries,
  independently bound QA identity, effect capabilities, expiry/revocation,
  persistence consistency, event privacy/redaction, and compatibility policy.
- **Exit gate:** Pinned donor characterization and accepted decisions cover
  component homes, runtime, persistence, identity, effects, privacy, compatibility,
  and rollback implications.

### D3b - Versioned connective contracts [planned]

- **Dependencies:** D3a.
- **Evidence refs:** none.
- **Scope:** version controller state/transitions, work and typed dependency roles,
  delegation/result/cancellation, delivery/idempotency/reconciliation, authority,
  event envelope, storage/effect ports, and component pin manifests.
- **Exit gate:** Versioned schemas, fixtures, evolution rules, property tests, and
  adversarial QA cover controller, delegation, authority, event, effect, storage,
  and pin contracts.

### D4a - Portable executive controller [planned]

- **Dependencies:** D3b.
- **Evidence refs:** none.
- **Home:** an independently testable controller component referenced by this root.
- **Scope:** deterministic wave sequencing, typed dependency legality, ordinal
  identity, QA/remediation accounting, effect and commit boundaries, controlled
  cancellation/exhaustion, durable journal/rebuild, and one reference persistence
  implementation with fault injection.
- **Exit gate:** A durable reference controller passes conformance, scheduling,
  duplicate, restart, stale-writer, cancellation, exhaustion, and recovery tests
  without claiming deterministic semantic judgment.

### D4b - Telos delegation dispatcher [planned]

- **Dependencies:** D3b.
- **Evidence refs:** none.
- **Home:** Telos, with a pinned interface consumed by this composition root.
- **Scope:** at-least-once delivery with durable idempotency keys, deduplicated
  admission, replay-safe results, cancellation, retries, and reconciliation. Do
  not claim impossible cross-system exactly-once execution.
- **Exit gate:** At-least-once delegated delivery is idempotently admitted,
  replay-safe, cancellable, crash-resumable, reconcilable, and separately
  adjudicable by Telos.

### D4c - Selected runtime and model adapters [planned]

- **Dependencies:** D3b.
- **Evidence refs:** none.
- **Scope:** implement only the reference runtime, scoped tool/effect path,
  independently bound QA path, and policy-compliant model routes needed by D5.
  Broader OpenCode, Pi, embedding, and ASR migration remains separately tracked.
- **Exit gate:** The selected runtime and scoped effect and QA paths enforce
  principal, credential, routing, outcome, expiry, and duplicate-effect boundaries.

### D4d - Pinned integration skeleton [planned]

- **Dependencies:** D4a, D4b, D4c.
- **Evidence refs:** none.
- **Home:** this composition root.
- **Scope:** add the minimum `compose/` binding, exact component manifest, durable
  state/event journal, compatibility checks, cross-component contract tests, and
  rollback procedure needed before a live claim.
- **Exit gate:** A clean environment resolves exact compatible component pins,
  preserves and replays durable evidence, passes cross-component contracts, and
  rolls back to a known-good checkpoint.

### D5 - Authentic bounded vertical slice [planned]

- **Dependencies:** D4d.
- **Evidence refs:** none.
- **Scope:** execute one bounded real effect from authenticated Telos delegation
  through dispatcher, controller, implementer, independent QA, replay-safe result,
  and separate Telos adjudication.
- **Exit gate:** One bounded authenticated effect survives forced retries,
  duplicates, crash/restart, cancellation, replay, QA, separate Telos adjudication,
  and rollback under exact pins.

### D6 - Cognitive programs [planned]

- **Dependencies:** D5.
- **Evidence refs:** none.
- **Scope:** independently version one cognitive discipline, then the general
  development pipeline over the controller. Preserve selected donor invariants and
  fixtures without importing donor runtime coupling.
- **Exit gate:** One discipline and then the development pipeline conform across
  fake and reference runtimes without donor runtime coupling.

### D7 - Read-only live observability [planned]

- **Dependencies:** D5, D6.
- **Evidence refs:** none.
- **Scope:** derive current state, causal history, readiness/blocking, critical
  path, agent census, and QA lineage from persisted cognitional events. Deliver a
  read-only web or TUI surface first.
- **Exit gate:** Read-only views replay real persisted events, explain causal state
  and missing evidence, enforce privacy, and expose no command authority.

### D8 - Attach and composition hardening [planned]

- **Dependencies:** D7.
- **Evidence refs:** none.
- **Scope:** reproduce the full composition from clean state, test upgrades and
  rollback, and add tmux-native attach as the default live-visibility adapter.
  Browser PTY remains optional and non-load-bearing.
- **Exit gate:** Clean install, restart, upgrade, rollback, identity, reconnect,
  isolation, command-length, and security drills pass against exact pins.

### D9 - Release and publication [planned]

- **Dependencies:** D2, D8.
- **Evidence refs:** none.
- **Scope:** resolve licensing, complete the final existing-work and security audit,
  establish the distinct protected trust root required by current governance,
  verify protected `main`, and publish only an exact post-merge SHA.
- **Exit gate:** License, audit, distinct protected trust root, protected main,
  post-merge evidence, independent approval, rollback, and immutable tag bind one
  full main SHA.

## 6. Parallel non-gating tracks

- **T1 - saeproj research:** May improve models and evaluation but cannot gate D2-D9.
- **T2 - Client trials:** May inform D3a; changing the selected reference runtime requires an accepted decision.
- **T3 - ContextForge evaluation:** May advance only from a demonstrated multi-host requirement; plain MCP remains the default.
- **T4 - Issue 65 OpenCode experiment:** Remains non-evidence even if merged; production readiness requires a separately scoped successor.

## 7. Explicit unresolved conflicts

The machine index records which stages these conflicts block:

- **C2 - D2 portfolio audit awaits protected independent review and integration:** resolve in D2; blocks D3a, D9.
- **C5 - first production reference runtime is not selected:** resolve in D3a; blocks D4c, D5.
- **C6 - principal effect persistence and event privacy semantics are undecided:** resolve in D3a; blocks D3b, D5, D7.
- **C7 - privileged observability controls lack an authority model:** resolve in D3a; blocks none.
- **C8 - license and distinct release trust root are unresolved:** resolve in D9; blocks D9.

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
