# noetic-dev integration and delivery roadmap

**Status:** Step-3 integration plan; execution evidence remains separate

**Governing inputs:** `initial-user-msg.md`, `AGENTS.md`, `SYNTHESIS.md`,
`docs/original-intent-traceability.md`,
`docs/full-portfolio-capability-map.md`, accepted decisions, conditioning open
questions, the immutable retained-residue appendix
`docs/workspace-residue-inventory-2026-08-01.md` SHA-256
`3d1cd70fccd61db2c1af7a0bb220741ced0c80a207018851cd6d1c7f49a83f5c`, and the
corrected Step-2 Git/workspace inventory in chain 90.

## 1. Outcome and plan boundary

This roadmap orders the practical construction of noetic-dev while also
dispositioning the current Git/worktree residue. Its critical path is the first
authentic slice:

```text
human authorization
  -> Telos purpose and typed dispatch
  -> deterministic runtime-neutral controller
  -> minimal versioned cognitive program
  -> bounded real effect and frozen implementation generation
  -> exactly one independent adversarial QA
  -> attributed causal events and provenance-preserving semantic memory
  -> separate critical judgment and Telos adjudication
  -> replay, recovery, and rollback
```

The roadmap does not make the current Git portfolio, issue 32, PR 67,
ContextForge, delivery governance, model routing, or release machinery the end.
Those mechanisms condition protected integration or supply bounded evidence.
Independent contract, donor, component, runtime, and research work proceeds when
its own prerequisites are met.

The plan has two simultaneous responsibilities:

1. **Construction:** establish a stable executable base, then expand to the
   complete development-and-cognitive framework.
2. **Reconciliation:** integrate only coherent verified existing work and leave
   every other item with an exact retained identity, blocker, owner boundary,
   and resume condition.

## 2. Governing execution rules

1. Issues are authoritative work units. Every implementation begins in a fresh
   sibling worktree from a freshly verified target branch and states scope,
   non-goals, acceptance commands, dependencies, produced artifacts, risk, and
   rollback.
2. A generation is the immutable output of exactly one implementation or
   remediation pass. It freezes an exact commit/tree or content manifest and
   receives exactly one independent, attributable, adversarial QA pass. Commits
   and PRs may contain a generation but may neither split one pass across QA
   identities nor collapse outputs from multiple passes under one QA. Every
   material compatibility integration, donor reconciliation, conflict
   resolution, base replay/merge, or remediation is its own pass and generation.
   A rejected or transcriptless generation is consumed.
3. Structural checks, semantic QA, human authorization, controller state, and
   Telos adjudication remain distinct evidence. No successful check implies the
   others.
4. Squash merge is the default for one coherent issue. Rebase merge is used only
   when every commit is independently useful and verified; rebasing a published,
   shared, retained, or already reviewed branch is forbidden. Merge commits are
   reserved for campaigns where topology itself is evidence.
5. noetic-dev feature work targets governed autonomous integration branch `dev`
   under its current remote rules; only `main` is required to be protected. No
   promotion to protected `main`, tag, or release occurs until its separate
   trust, authority, license, exact-SHA, recovery, and rollback gates pass.
6. Component repositories retain their own governance. Planned targets are Telos
   `main`, ContextForge `dev-root`, and the default protected integration branch
   established for each new independent component. A fresh remote/policy check
   must confirm the target before work begins.
7. Dirty roots, stashes, user-global configuration, runtime databases, credentials,
   generated state, and unrelated work are never bulk-staged, reset, cleaned, or
   silently absorbed.
8. A branch is deleted only after the exact head is merged or explicitly retained
   elsewhere, all linked worktrees are terminal and clean, no unique evidence is
   lost, and the issue/PR records the deletion. No current tag requires action.

## 3. Dependency tranches

### T0 - Accepted base and safe reconciliation

**Purpose:** make the current constitutional and inventory work durable without
mixing blocked candidate or user-local residue.

**Dependencies:** accepted capability map and this Step-3 plan.

**Deliverables:**

- one noetic-dev child issue under issue 32 for the founding-scope,
  traceability, capability-map, roadmap, and ledger convergence;
- a clean sibling worktree from the freshly verified `origin/dev` integration
  target;
- explicit-path transfer of only the selected composition-root files;
- one frozen integrated documentation generation, one independent QA pass, and a
  squash PR to `dev`; and
- recorded dispositions for PRs 66/67 and every retained Step-2 item.

**Exit gate:** the governed `dev` PR is green and merged, or is blocked with its
exact immutable candidate and failed gate recorded. No dependent architecture
work waits for the merge if its accepted contracts can be developed
independently.

### T1 - Adjudicated boundaries and component initialization

**Purpose:** enact the minimum decisions already accepted as
`dec-20260801-0006` through `dec-20260801-0009`, not postpone them behind another
planning phase.

**Dependencies:** accepted constitution and this roadmap. T0 merge is required
for protected root integration but not for read-only donor work or disposable
contract prototypes.

| Boundary | Accepted selection | Current immutable input or honest absence |
|---|---|---|
| Telos dispatch | Existing `somebloke1/telos`; new dispatcher starts from freshly verified clean target `a8f6c253bb091562a9982b22217ebc4e78b1aa5b` unless the remote has legitimately advanced | Exact clean local remote-tracking input; unpublished local commits are residue, not prerequisites |
| Controller and private state | New `somebloke1/noetic-controller`; TypeScript/Node implementation with private `controller.sqlite` command/state store and transactional outbox | Canonical component absent/unpinned; noetic-pi donor `683b53b06714d0aadd49c5852140b708c5abba69` |
| Cognitive programs | New `somebloke1/noetic-programs` for `bounded-change-inquiry/v1` and later `development_pipeline.v1` | Canonical component absent/unpinned; cognitive-disciplines donor `923686521b78a4c0cb2e86a23a6eb5d4f9e0c5e4` plus noetic-pi donor above |
| Causal events and memory | New `somebloke1/noetic-evidence` with separately testable `journal` and `memory` packages; journal is the sole append authority; memory is a rebuildable derived projection | Canonical component absent/unpinned; SQLite 3.45.1-compatible stores selected; noetic-pi donor above |
| First runtime/effect/model adapter | New `somebloke1/noetic-opencode-adapter`; OpenCode 1.18.9 first runtime; kernel-peer local admission plus deterministic one-file effect executor; genus-router then LiteLLM for model calls | Component absent/unpinned; local OpenCode binary SHA-256 `7c4d91c84d2bfdeabb59257e3490c5e5acb08f2aacb3e42f3ddc296a1c3f1aca` |
| Second adapter | New `somebloke1/noetic-pi-adapter`; Pi 0.80.3 | Component absent/unpinned; local Pi binary SHA-256 `af302f231437eaf6f37691bce4b34234fcb626bcb5eb3910d4fc3f6519bf78ca` |
| Versioned skills/agents | New `somebloke1/noetic-resources` | Canonical component absent/unpinned; cognitive-disciplines and Telos clean inputs are donors only |
| Model-substrate deployment contracts | New `somebloke1/noetic-model-substrate`; genus-router remains the independent selector and LiteLLM the universal access boundary | Component absent/unpinned; genus-router `f2b839b0cfc737c4c1f0a46d3d519d414529545c` and LiteLLM 1.81.10 are local evidence pins |
| Later observer/attach/semantic adapters | New `somebloke1/noetic-observer`, `somebloke1/noetic-attach-tmux`, `somebloke1/noetic-serena-adapter`, and `somebloke1/noetic-mentality` | All absent/unpinned; initialization waits for their tranche but the home is selected |
| Model selection/access | genus-router revision `f2b839b0cfc737c4c1f0a46d3d519d414529545c`; LiteLLM 1.81.10; every invocation accesses models through LiteLLM | Exact local evidence pins, pending fresh source/package provenance before composition |

Controller state and journal append are intentionally separate. Telos/controller
outboxes deliver stable event IDs at least once; the single journal writer
deduplicates and positions them. `noetic-evidence/memory` keys every derived
record to source event IDs/positions. The local human principal is admitted over
a mode-0700 Unix socket using kernel peer credentials; a versioned authorization
binds UID, purpose, issue/worktree, repository/base/tree, one-file allowlist,
expiry/revocation, remediation budget, and rollback digest. Actor capabilities
are single-use and run/generation/pass-bound; QA is read-only and receives no
effect token.

**Initialization boundary:** each absent repository is created only through its
own issue and one implementation pass/generation with conventional commit
`chore(repo): initialize <component> contract package`, deterministic tests, and
exactly one independent QA. Its governed `main` is established by squash merge.
Only the resulting full commit SHA may replace `absent/unpinned` in the root
component manifest. Initializing multiple repositories is multiple generations
and multiple pairings, never one campaign QA.

**Decision integration commit:**
`docs(architecture): select first-slice component boundaries`, included in T0's
single integration generation.

**Gate:** repository validation plus independent QA must confirm the exact T0
candidate carries decisions 0006-0009, their reversibility/non-claims, the local
evidence pins, and the explicit absence of canonical SHAs. T2 begins per component
only after that component's initialization SHA exists.

### T2 - Versioned connective contracts

**Purpose:** let independently testable components develop in parallel without
runtime coupling.

**Dependencies:** the minimum relevant T1 decisions. Contract issues may proceed
in parallel when their boundaries do not depend on an unresolved choice.

| Issue/commit boundary | Planned root artifacts | Acceptance gate |
|---|---|---|
| `spec(authority): define identity and delegation contracts` | authority, principal/actor identity, Telos delegation/result/cancellation/reconciliation schemas and fixtures | Unknown versions/roles/fields, stale/expired authority, duplicate delivery, and identity conflation fail closed |
| `spec(control): define controller and cognitive-program contracts` | controller state/transitions, work/dependency roles, generation/pass identity, minimal `bounded-change-inquiry/v1` packets and evolution rules | Property tests cover legal/illegal transitions; P1-P4 reports remain attributed semantic evidence; exact QA cardinality is enforceable |
| `spec(evidence): define event journal and memory contracts` | causal-event envelope, append/replay protocol, controller-store boundary, semantic-memory provenance and privacy contracts | Causal identity, temporal scope, redaction, idempotent append, restart retrieval, and replay equivalence have adversarial fixtures |
| `spec(runtime): define effect runtime and composition contracts` | workspace patch/effect, runtime/model adapter, routing/outcome, component manifest, compatibility and rollback schemas | Stale base, path escape, symlink, duplicate effect, credential leakage, wrong model route, incompatible pins, and rollback mismatch fail closed |

Each row is a separate issue, implementation pass/generation, conventional
commit, independent QA pass, and squash PR to noetic-dev `dev`. A final contract-
compatibility issue is itself one new integration implementation pass and
generation: it binds the exact merged SHAs, adds cross-contract tests, receives
exactly one attributable independent QA, and does not reopen independently
accepted semantics without a later new generation.

### T3 - Parallel component construction

**Purpose:** implement the smallest real components against T2 contracts.

**Dependencies:** each component depends only on its relevant accepted contracts.

| Component track | Home and donor | First implementation boundary | Component gate |
|---|---|---|---|
| Telos dispatcher | Telos; delegation schema and goalchain core donors | `feat(dispatch): enact typed replay-safe delegations` from the freshly verified accepted Telos target; no unpublished residue is a prerequisite unless a separate source-backed decision proves one exact commit necessary | At-least-once delivery, deduplication, retry, cancellation, crash restart, replay-safe result, reconciliation, and separate adjudication |
| Portable controller | `somebloke1/noetic-controller`; noetic-pi APM is donor only | `feat(controller): implement durable bounded run lifecycle` | Legal waves/dependencies, exact implementation/QA/remediation identity, cancellation, exhaustion, stale writer, restart, rebuild, and no semantic-truth claim |
| Minimal cognitive program | `somebloke1/noetic-programs`; cognitive-disciplines is donor | `feat(program): add bounded change inquiry v1` | Attributed P1-P4 packets run over fake and reference adapters; structural validation cannot assert semantic adequacy |
| Canonical journal | `somebloke1/noetic-evidence` `journal` package; APM/event donors only | `feat(events): persist and replay attributed causal events` | Atomic/idempotent append, causality, concurrency, crash recovery, redaction, version evolution, and deterministic replay |
| Semantic memory | `somebloke1/noetic-evidence` `memory` package; noetic-pi session-search donor | `feat(memory): retain provenance-linked inquiry summaries` | Restart-safe store/retrieve with source-event links, temporal scope, uncertainty, privacy, retention, and no BM25-as-semantic-search overclaim |
| Runtime/effect/model adapter | `somebloke1/noetic-opencode-adapter`; exact OpenCode 1.18.9 local evidence pin in T1 | `feat(runtime): execute scoped reversible workspace effects` | Exact runtime/model provenance, no direct credentials, genus-router selection, LiteLLM invocation, bounded effect, cancellation, and inverse patch |

Every component uses its own issue-linked worktree, repository tests, one exact
implementation:QA pairing, and repository-native governed PR. Telos dispatcher
work targets freshly verified `main` with squash merge and proceeds independently
of its six unpublished historical commits. Those commits are reconciled or
retained on a separate track. Newly created component repositories establish a
governed default integration branch before their first merge. Donor repositories
are not modified to simulate extraction.

### T4 - Pinned integration skeleton

**Purpose:** compose exact independently verified component revisions without
moving runtime authority into the root.

**Dependencies:** one accepted revision from each T3 load-bearing component.

**Implementation boundaries:**

1. one pass/generation and QA for
   `build(compose): pin first-slice component revisions`;
2. one later pass/generation and QA for
   `test(integration): verify cross-component contracts and recovery`; and
3. one later pass/generation and QA for
   `docs(runbook): define first-slice rollback and evidence capture`.

The three generations may share a tracking issue but cannot share one QA or be
collapsed into a retrospectively declared generation. Each uses a conventional
commit. If they share a final squash PR, assembling or materially resolving that
combined tree is a fourth, distinct integration implementation pass/generation
that freezes the exact PR tree and receives exactly one attributable independent
QA. The three component pairings remain individually attributable; the required
combined-tree QA neither replaces them nor adds a second QA to any earlier
generation. The root owns pins, configuration, composition, and proof; the
journal component remains the append authority and the controller owns only its
local command/state store.

**Exit gate:** a clean disposable environment resolves exact pins, rejects
incompatible versions, starts without user-global configuration, preserves and
replays evidence, survives forced restart, and restores a known-good checkpoint.

### T5 - First authentic vertical slice

**Purpose:** prove the load-bearing whole with one real reversible effect.

**Dependencies:** T4 and the exact acceptance contract in
`docs/full-portfolio-capability-map.md` section 6.

**Effect:** apply one allowlisted patch to one declared file in a disposable issue
worktree, run one deterministic test, and mechanically verify the inverse patch.

**Mandatory run:** authenticated human authorization -> Telos purpose/delegation
-> dispatcher -> controller -> `bounded-change-inquiry/v1` P1-P4 packets ->
frozen implementation -> one independent read-only QA -> event/memory persistence
-> separate Telos reconciliation/adjudication -> restart retrieval -> rollback.

**Mandatory remediation lineage drill:** the run intentionally submits one bounded
candidate that violates a declared acceptance condition without escaping the
disposable worktree. It has a distinct initial-implementation pass ID and frozen
generation ID. Its sole attributable read-only QA must reject that exact identity.
The rejected pass and generation IDs are consumed and persisted. One materially
changed remediation has a new remediation-pass ID and distinct generation ID and
receives exactly one fresh, distinct, attributable read-only QA. The controller,
canonical events, semantic memory, and Telos result history must each preserve
both pass IDs, both generation IDs, both QA IDs/verdicts, the causal remediation
edge, and the final separate adjudication. A no-op refreeze, reused QA identity,
or post-hoc record cannot satisfy this drill.

**Other failure drills:** duplicate delegation/result, expiry/revocation,
cancellation, wrong actor, zero/duplicate/stale/self QA, stale base/tree,
path/symlink escape, crash at each persistence/effect boundary, wrong model route,
direct-provider bypass, event append conflict, memory provenance loss, replay
divergence, and inverse mismatch.

**Exit gate:** one exact run evidence bundle proves all mandatory events, the
two-generation rejection/remediation lineage, and every falsification drill.
Synthetic traces, manually assembled records, service startup, and controller-
only schedules remain non-evidence.

### T6 - Complete development program and observable operation

Run these bounded issues in parallel after the T5 base is stable:

| Issue/home | Prerequisite and commit | Target/merge and one-generation QA | Gate, rollback, and non-claim |
|---|---|---|---|
| Full development program in `somebloke1/noetic-programs` | T5 plus canonical crosswalk; `feat(program): implement development pipeline v1` | Component governed branch, squash; one implementation pass/generation and one independent QA | Four phases, fake/reference runtimes, frozen generations, bounded remediation, exact QA lineage, and separate adjudication pass; rollback pins the minimal program; no donor pipeline is called portable |
| Read-only observer in `somebloke1/noetic-observer` | Canonical journal and T5 evidence; `feat(observe): project causal run state` | Component governed branch, squash; one pass/generation and one independent QA | Live/replayed causal state, missing evidence, readiness, census, and QA lineage match journal truth with privacy and no command authority; rollback removes observer pin only |
| tmux attach adapter in `somebloke1/noetic-attach-tmux` | Stable runtime identity contract; `feat(attach): add tmux agent visibility` | Component governed branch, squash; one pass/generation and one independent QA | Identity, isolation, reconnect, command length, teardown, restart, and recovery pass; rollback detaches adapter; attach is not observability or control authority |
| Semantic-memory expansion in `somebloke1/noetic-evidence` `memory` package | T5 provenance memory; `feat(memory): add cross-session semantic retrieval` | Component governed branch, squash; one pass/generation and one independent QA | Summaries, embeddings, similarity retrieval, source provenance, uncertainty, temporal scope, privacy, retention, deletion, restart, and negative queries pass; rollback pins T5 memory |

Browser PTY and privileged observability controls remain deferred production
integrations until their accepted triggers hold.

### T7 - Portability and complete local model substrate

| Issue/home | Prerequisite and commit | Target/merge and one-generation QA | Gate, rollback, and non-claim |
|---|---|---|---|
| Second runtime/client adapter in `somebloke1/noetic-pi-adapter` | T5 reference contracts and Pi 0.80.3 evidence pin; `feat(runtime): add second conforming adapter` | Component governed branch, squash; one pass/generation and one independent QA | The unchanged authentic slice passes with exact runtime/model/effect evidence; rollback removes the second pin; one adapter never proves portability |
| LiteLLM-only machine/prose convergence in noetic-dev | Accepted routing policy and exact current profiles; `fix(models): enforce LiteLLM-only profiles` | noetic-dev `dev`, squash; one pass/generation and one independent QA | Direct-provider profile IDs/credentials/bypasses fail closed and fixtures remain secret-free; rollback restores the prior known-good policy pin, not direct access |
| Vision classification/routing in genus-router | Versioned vision task/capability contract; `feat(routing): register vision task genus` | freshly verified genus-router `main`, squash; one pass/generation and one independent QA | Unknown/contradictory capabilities, unavailable models, reroute, and outcome feedback pass; rollback reverts the route and preserves vision as unsupported |
| ASR LiteLLM registration in `somebloke1/noetic-model-substrate` | Exact local ASR model/service identity; `config(models): register ASR through LiteLLM` | Component governed `main`, squash; one pass/generation and one independent QA after its T1 initialization | Registry, auth isolation, transcription, timeout, failure/reroute, and outcome evidence pass; rollback restores prior registry and reports ASR unavailable |
| Embedding/ASR bypass removal in each affected caller component | Accepted LiteLLM routes; per component `fix(models): remove direct modality bypass` | One separate issue, pass/generation, QA, and squash PR per affected component | Static and runtime tests prove no direct endpoint/credential path; rollback pins the previous caller while marking it nonconforming, never silently re-enables bypass |
| Four-modality integration proof in noetic-dev | Accepted generative, vision, embedding, and ASR component revisions; `test(substrate): prove four governed modalities` | noetic-dev `dev`, squash; one integration pass/generation and one independent QA | Real tasks bind classification, selected/actual model, LiteLLM request, result, failure/reroute, and outcome for all four; rollback restores prior pins; availability or one request is non-evidence |

### T8 - Parallel research and optional adapters

| Issue/home | Prerequisite and commit | Target/merge and one-generation QA | Gate, rollback, and non-claim |
|---|---|---|---|
| SAE/GEH target-governance decision in saeproj | Current no-upstream state; `docs(governance): select saeproj research integration target` | Fresh issue/branch from local `main`; one deliberation implementation pass/generation and one independent QA; record whether `main` is accepted, establish the approved upstream/rules, and squash merge to accepted `main` only after that decision permits it | Exact remote/target, ownership, branch policy, research artifact boundaries, rollback, and non-publication state are explicit; rejection leaves all research retained and blocks only saeproj merges |
| SAE/GEH evidence package in saeproj | Accepted target-governance decision plus research-owner separation of geometry, benchmark, and governance artifacts; `research(geh): package operation-probe evidence` | Fresh research issue/branch targeting accepted saeproj `main`, squash; one pass/generation and one reproducibility QA | Controls, content invariance, transfer, negative results, provenance, and calibrated confidence reproduce; rollback reverts the evidence PR while preserving raw research; no GEH or production-model claim |
| Versioned SAE/GEH feedback seam in noetic-dev | Accepted qualified research artifact; `spec(research): define cognition evidence feedback` | noetic-dev `dev`, squash; one pass/generation and one independent QA | Schema preserves model/data/experiment identity, confidence, negative evidence, and non-gating semantics; rollback removes the pin; no proxy result changes the constitution |
| Serena lifecycle adapter in `somebloke1/noetic-serena-adapter` | Stable target-root/identity contract; `feat(serena): manage project-scoped semantic agents` | Component governed branch, squash; one pass/generation and one independent QA | Create/status/verify/remove, root identity, ports, restart, failure, and cleanup pass without ContextForge dependence; rollback removes adapter pin |
| mentality authorization/versioning in `somebloke1/noetic-mentality` | Ledger scope and actor contract; `feat(governance): bind repository ledger authority` | Component governed branch, squash; one pass/generation and one independent QA | Repository scope, statuses, attribution, concurrency, transport authorization, backup, recovery, and runtime-independent visibility pass; rollback pins prior read-only behavior |
| Versioned skills and semantic-agent packages in `somebloke1/noetic-resources` | Accepted authority/tool declaration contract and source-inspected cognitive-disciplines/Telos/local resource donors; `feat(resources): package versioned cognitive agents and skills` | Resource component governed branch, squash; one pass/generation and one independent QA | Package identity, instruction/source provenance, declared tools/effects, runtime compatibility, update/rollback, secret absence, and rejection of implicit authority pass; rollback pins the prior resource manifest; packaged instructions are not cognition or authorization |
| Additional client adapter, one issue per Pi/Claude/Codex/Gemini/Goose/Kilo/VS Code/desktop surface | Measured user value and common adapter contract; create `somebloke1/noetic-<client>-adapter`; `feat(runtime): add <client> adapter` | Adapter component governed branch, squash; one pass/generation and one independent QA per client | Exact version/config, tool/resource visibility, identity, cancellation, routing, isolated home, cleanup, and conformance pass; rollback removes only that adapter; discovery is not parity |
| ContextForge promotion evaluation in noetic-dev | Measured multi-host/shared-continuity need that plain MCP cannot meet; `docs(transport): adjudicate ContextForge promotion` | noetic-dev `dev`, squash; one deliberation implementation pass/generation and one independent QA | Replaceability, authority, privacy, security, recovery, failure, and end-to-end evidence support an accepted decision; rollback retains plain MCP; absent need leaves ContextForge optional |

### T9 - Survival, release, and publication

**Dependencies:** complete-system gates, not merely T5.

| Issue/home | Prerequisite and commit | Target/merge and one-generation QA | Gate, rollback, and non-claim |
|---|---|---|---|
| Lifecycle/removal hardening in noetic-dev integration proof | All pinned components; `test(lifecycle): prove composition survival` | noetic-dev `dev`, squash; one integration pass/generation and one independent QA | Clean install, isolation, stop/restart, upgrade, forced failure, replay, rollback, uninstall/removal, and known-good restoration pass; rollback pins prior manifest |
| License and release-boundary adjudication in noetic-dev | Complete component/license inventory; `docs(release): adjudicate licensing and authority` | noetic-dev `dev`, squash; one deliberation implementation pass/generation and one independent QA | Every component and artifact has a compatible disposition; current authority/security/privacy risks and non-claims are recorded; no license means no publication |
| Main-target review compatibility on noetic-dev `dev` | Current protected `main@29196a67349537d6f8a8a711df11b86da0430857` lacks `scripts/governance/request_agent_review.py`, while the default-branch `pull_request_target` workflow checks out the main base and invokes that absent path (`k-20260713-0003`); `fix(governance): bootstrap main-target review client` | noetic-dev `dev`, squash; one bounded implementation generation and one independent QA before any release promotion PR | Bind the review workflow and client bytes to the exact accepted `dev` generation, keep candidate code non-executable, and prove with an actual disposable main-target canary that Agent Review and validation run without a missing-main-path failure or red required check. Rollback reverts the compatibility generation on `dev`; failure blocks only promotion and may not weaken main protection or required checks |
| Exact release candidate in noetic-dev | Complete-system gates, accepted main-target review compatibility, and current protected-main policy; `chore(release): freeze noetic-dev <version> candidate` | noetic-dev `dev`, squash; one release implementation pass/generation and one independent exact-SHA QA | Immutable component manifest, clean rebuild, all integration/lifecycle tests, evidence digests, rollback point, and post-merge checks pass; failed candidate remains untagged |
| Human-approved promotion to protected `main` | Exact accepted `dev` release candidate, accepted main-target review compatibility with a fresh green canary, and fresh user approval; `chore(release): promote noetic-dev <version> to main` | Freeze one distinct promotion integration pass/generation at the exact dev-derived candidate; obtain exactly one attributable independent promotion QA; use a squash PR under the current main policy, with no force push and rebase only if a later recorded policy explicitly permits it | Protected `main` has the exact approved candidate tree after the merge, while publication evidence binds the dev candidate SHA, tree, merge result, method, and user approval; post-promotion verification is operational evidence, not another QA pass; only then create the signed/versioned tag. A revert PR and previous manifest are rollback; promotion does not retroactively re-QA feature generations |

Publication trust blockers condition only these release rows; they do not
invalidate or pause the independently runnable framework.

## 4. Immediate Step-4 Git integration plan

This table governs existing residue. “Retain” is a deliberate disposition, not
an unworked promise. Exact worktree paths, full heads, upstream/ahead/behind
observations, dirty-manifest digests, stash OIDs/parents, repeated configuration
status groups, missing registrations, and non-secret client/runtime identities
are bound by `docs/workspace-residue-inventory-2026-08-01.md` SHA-256
`3d1cd70fccd61db2c1af7a0bb220741ced0c80a207018851cd6d1c7f49a83f5c` and are
incorporated into every retention row below.

| Item | Exact known state | Step-4 action | Commit/PR/merge or retention reason |
|---|---|---|---|
| noetic-dev constitutional/inventory work in root | `main@29196a67349537d6f8a8a711df11b86da0430857` with modified `ABEYANT_INTENTIONS.md`, `DECISIONS.md`, `KNOWNS.md`, `OPEN_QUESTIONS.md`, `README.md`, and `SYNTHESIS.md`; untracked `docs/original-intent-traceability.md`, `docs/full-portfolio-capability-map.md`, this `ROADMAP.md`, and the residue appendix | Issue #80 transferred and reconciled those ten paths from `origin/dev@1195c88f6160e4e15f430fd3f67fcb5eda19f559`, then expanded its authoritative final-tree scope to `AGENTS.md` and `docs/cognitive-backbone.md` when QA proved those current projections required reconciliation. Consumed predecessors are exactly `da96142df2e6025a6ef7ba027f98fa167697a542`/tree `906a7240eca87d029f91863730d8eb87af0eb96b`, `2f21693128cb12404173666ccfc4f5eba7fbc13a`/tree `f0881741fdedcb03c04f83d650330983b026798e`, `1f946ae6b3406ff2154cdab3b40e72c5f8a18d7b`/tree `83a9fbb58a883217e7361b927b05ff8c1456fb56`, and `9c14c18612fcb6191002767d0cd6311331b553fc`/tree `2670f55e1338110d35b2855205bf1f1b9910196b`; each received exactly one `REJECTED` QA and may not advance. Freeze only a fresh successor, then obtain exactly one QA before a squash PR to `dev` | Every frozen generation has exactly one QA. A commit cannot embed its own stable SHA/tree, so live issue #80 is the sole mutable record binding the checked-out successor identity and pending/final QA state; Git ancestry and this row bind all consumed predecessors. Rejected generations are never amended or retrospectively accepted. The final PR may retain their lineage because squash integration publishes only the independently accepted successor tree |
| noetic-dev validator coverage gaps derived by issue #80 QA | `validate_repo.py` accepts an adversarial invalid ledger status and declares 103 required files through a 102-path-unique list | Track only in issue #81; do not broaden the issue #80 documentation remediation into validator implementation | Issue #81 owns finite per-ledger status validation, duplicate required-path rejection, tests, one frozen generation, and one independent QA. Issue #80 still verifies its actual statuses and receives no claim that this follow-up is fixed |
| Root `.serena/` | Untracked local semantic-tool metadata/cache | Retain untouched and exclude from every stage | User/tool-local state; no accepted product contract or cleanup ownership |
| Root `docs/user/emergent_probability.txt` | Untracked user-provided source with separate provenance/licensing concern | Retain untouched and exclude from public commit | It informs reasoning but is not required to publish the accepted decisions; licensing/provenance is unresolved |
| noetic-dev PR 67 | Remote-tracking head `37b24e09e685dec09d7a6289c83209ff63e6843c` blocked; local `3d3c1d45d05de69d4f3cb1de6fb137dd6b2e0e6f` is one unpushed commit with no valid planned QA or fresh authorization | Do not push or merge. After the T0 PR is accepted, comment with supersession/harvest rationale and close the PR unless current owner evidence establishes a still-needed bounded successor | Preserve branch/worktree and both exact SHAs as governance donor evidence; resume only through a fresh issue, material implementation pass, authorization, QA, and current checks; no branch deletion while unique commits remain |
| noetic-dev PR 66 / issue-65 prototype | Behind/failing paused non-evidence at `issue-65-opencode-spike@8fcb1c509b14f10f1f7e2ef2363ffb98996fa46b` | Do not merge. Link its useful `development.verified-change/v1` fixture from the T1/T2 issue, then close the stale PR with prototype/non-evidence rationale | Preserve exact branch until fixture pin/extraction is accepted; resume only as a new bounded program/conformance issue; no cleanup before reachability is recorded |
| noetic-dev issue 32 | Portfolio umbrella with stale candidate ordering | Update, do not close: link the accepted capability map, this roadmap, child issues, superseded PR dispositions, and parallel tracks | Coordination issue remains open until complete-system rows are delegated or explicitly conditioned |
| noetic-dev issue-27 worktree | `issue-27-terra-canary@161b262b2321444d4fb322931b640483d0a14eb2`, tracking its same-named remote snapshot, with six modified governance/review paths | Retain untouched | Resume only under issue 27 after fresh remote/check review and a new bounded implementation generation; do not mix with T0 or issue 29 |
| noetic-dev issue-29 worktree | `issue-29-routed-governance-remediation@c60f8e48a17e88db5d00322f675a02a4b17ceeaa`, tracking its same-named remote snapshot, with dirty audit compression, schemas, routing, runner, and tests | Retain untouched | Resume only under issue 29 after separating audit, schema, routing, and runner concerns into attributable generations; no bulk staging or opportunistic merge |
| noetic-dev project-agent worktree | `chore/opencode-project-agents@29196a67349537d6f8a8a711df11b86da0430857` with staged `.opencode/README.md`, `noetic-qa.md`, and `noetic-tracer.md` | Retain staged index/worktree unchanged | Resume only through its existing project-agent issue/QA and a fresh current `dev` base; user-global agents and T0 docs remain out of scope |
| genus-router local main | Clean `4ff584e2e5d190b7e25dc0a4607c494a50069b83`, one commit behind local remote-tracking merged `f2b839b0cfc737c4c1f0a46d3d519d414529545c` | Freshly query/fetch, verify clean fast-forward and tests/checks, then fast-forward local `main` only | No commit, PR, push, or branch deletion; abort if remote identity or dirt differs |
| cognitive-disciplines | Clean `main@923686521b78a4c0cb2e86a23a6eb5d4f9e0c5e4`, equal to inspected upstream | No Git mutation; pin as donor evidence in T1/T2 | Already reconciled; future changes require a component issue |
| Telos six local commits | `main@951f3a9c1e9eec2e64848e44a61e050a9dc56464`, with historical commits `315e8605c46031fa214a0ae26e944b25ea6d1ec7`, `974beb6505959ff1e1afe02a5bc6bfd866bd946b`, `42633d6e00903d77f0570115d72aa93418e895a1`, `a44c0437c8a3d21cc07ecd8275e48defafc27e78`, `920c4edaf05212f0263322462746736730c7bcbc`, and `951f3a9c1e9eec2e64848e44a61e050a9dc56464` beyond local `origin/main`; 35 tracked and 89 untracked dirty paths overlay the branch | Preserve dirty root and all refs. Do not certify historical passes by regrouping commits under new QA. For each still-material change, create a fresh issue/worktree from current accepted Telos `main`, replay or reimplement it in one attributable pass/generation, run one QA, and squash PR to `main`; otherwise retain the exact historical commit with rationale | Reconciliation is parallel and cannot gate the dispatcher unless one exact commit is separately proven prerequisite. Do not mix dirty continuation/model/toolbridge work or infer dispatcher behavior |
| Telos dirty overlay/live deployment drift | Extensive unpublished work and divergent Pi/OpenCode deployment | Retain; inventory into bounded component/runtime issues after T1 | Not one coherent generation; dispatcher is absent and must be new work, not inferred from dirt |
| noetic-pi and its worktrees | Donor head `683b53b06714d0aadd49c5852140b708c5abba69`; appendix records 16 worktrees including one missing registration, five stash OIDs, every full HEAD, and each dirty-manifest digest | No commit, merge, push, stash action, cleanup, prune, or export revival | Pin source invariants/fixtures read-only; resume only through a bounded extraction issue in the selected component home; each residue row retains its appendix identity and status-specific resume rule |
| noetic-pi-docker | `main@30de068b651c35a475a282e2c8dabe883b77c1a0`, equal to inspected `origin/main`, with ten dirty/untracked routing, reconnect, agent-manager, terminal, backup, and test paths | Retain without Git mutation | Prior product/deployment fixture, not noetic-dev basis; resume only through a deployment-evidence issue that excludes backup/runtime residue and receives its own generation/QA |
| pi2 | `main@17cdb45b5711a6ae76888350ff5d89c5f2a24c89`, distinct from inspected `origin/main@a3039a2458ba7af766b50005e15f67d6b04c9e5d`, with deleted `.envrc`, modified runtime database/log, and one untracked `.envrc` backup | Retain without fetch-integrate, cleanup, commit, or push | tmux/attach donor only; resume via read-only pinning and a new attach-component issue, never by committing runtime database/log or environment residue |
| saeproj and related research | `pi2-governance-adoption@fcc4bc465cd82256cec3d6cfc7e6958510291c9d`, dirty-manifest SHA-256 `e8ec071a5f984a2b5ed17b42f7cb4479e22ac568dd3df5be847bf86bdda32f52`, stash `8641ab98e253c39d845034ef48e6d502e62b3aed`, no configured upstream; appendix records other retained heads | No bulk integration or stash action. First execute the T8 target-governance issue; create research-owned evidence issues only when geometry, benchmark, and governance changes can be separated | Research remains active/non-gating; preserve stash, v3 authority, untracked v4 uncertainty, and negative results; resume under the T8 evidence package |
| ContextForge issue 396 overlay | `codex/issue-396-4445-required-families@bb4e6a5974f2b22265c76b1e1bbef0883a6c1613`, 17 tracked dirty paths, diff SHA-256 `4e4b66ba6408df84160d4b9795073d63dade64e01dfab4f3a2f4df74ddf62fb4`; pass-18 transcript matches but distinct implementer/QA identities are absent | Do not commit or push this generation. Step 5 resumes with a necessary material successor (for example the recorded Serena/root or user-frontdoor gap), a new exact implementation identity, and exactly one attributable QA | The existing snapshot is consumed/unverified evidence; a no-op refreeze cannot manufacture valid pairing |
| ContextForge PR 392 and root | PR conflicts; root `codex/issue-389-cf-catalog-service-truth@834badb9f64371539e44a0f4f674c56b7ee7d0cf` is two local commits ahead with dirty-manifest SHA-256 `7e777b556cb3382c87fdd1101bdf1df5c023c88d1a0e5c8f02c5b7f807321939` and stale topology | Retain untouched and separate from noetic-dev; comment/close only under its own issue authority | Optional transport estate, not a noetic-dev integration candidate; exact ahead commits and status rows are in the appendix |
| ContextForge stashes, branches, detached/terminal worktrees, repeated `.codex` changes | Appendix records every full worktree path/branch/HEAD/status, stash OIDs `7da6ff47aa306c622547fe7575913754fd6c961b`, `77a9f44033a71f5c4c8bb8689a9fd6772b45109f`, `22179e41f8d833da983797fca36703339853048b`, and 23-path config-group SHA-256 `ea5fa0c00da360a4f4a542a9f828934506e081a1178dcc57467d436cded83d6e` | Retain; do not prune, apply/drop stash, reset, rebase, force-push, or delete | Each appendix row resumes only through its owning issue plus reachability/ownership/QA check; repeated status is not cleanup authority |
| Client/global configs and runtime services | Appendix records executable paths/versions for Pi/OpenCode/Claude/Codex/Goose/VS Code/tmux/Kilo, unopened config paths, point-in-time process PIDs, and system unit names | Read-only evidence only during Step 4; do not edit/open/hash config values or rely on stale PIDs | User-global/runtime state is outside repository delivery; later adapter trials use isolated homes/config and refresh their own non-secret identity |
| Accidental credential observation and tree `a904ff5a5d50dab0fdcc5b626756c8b8b433f527` | Delegated process violation; no refs/index/worktree changed | Record only; do not use the value, rotate credentials, recover the object, or create a security detour | Existing user decision governs; unreachable object is non-authoritative residue |

## 5. Step-4 execution gates and checkpoints

### Before any mutation

1. Check the authorization window and blind-alley timer.
2. Re-query GitHub and remote refs for the exact repository being changed; do not
   generalize a stale Step-2 snapshot.
3. Record branch, HEAD, tree, upstream, ahead/behind, status, stashes, worktrees,
   open PR/check state, and selected file manifest.
4. Stop on unexpected changes and preserve them.

### Per implementation generation

1. Create/link the issue and fresh sibling worktree.
2. State accepted claim, non-claims, threats, tests, rollback, and exact file set.
3. Implement one coherent concern and run deterministic local checks.
4. Freeze commit/tree/content digests.
5. Dispatch exactly one independent QA with the claim but not the implementer's
   self-assessment; record task identity, transcript, and verdict.
6. On rejection, consume the generation and create one materially changed
   successor only if P3/P4 reassessment still warrants it.
7. Push only the accepted branch, open/update its linked PR, require current
   protected checks, and merge only the exact accepted candidate.

### After merge

1. Verify the governed target contains the accepted result and rerun required
   post-integration checks.
2. Record the merge SHA, method, issue closure, retained branch/worktree state,
   and rollback point.
3. Delete a branch/worktree only under rule 8 in section 2.
4. Do not promote `dev` to `main` or tag merely because a feature PR merged.

## 6. Conflict, failure, and rollback policy

- **Base advanced before QA:** preserve the old branch/ref and create a fresh
  issue branch/worktree from the current target, then replay the bounded change as
  one new implementation pass/generation with relevant tests and one fresh QA.
  Do not rebase a published, shared, retained, or reviewed branch, and never carry
  a stale verdict across material tree changes.
- **Content conflict:** stop automatic integration, identify which authority owns
  each side, preserve both source identities, and make a bounded semantic
  resolution as one new implementation pass/generation with tests and one QA. Do
  not prefer the newer or larger branch by default.
- **Dirty/unexpected worktree:** stop immediately. Do not stash, clean, reset,
  checkout, or relocate another actor's work. Create a separate clean worktree or
  record a blocker.
- **Remote/protection drift:** stop push/merge, record the current API/ref/check
  evidence, and revise only the dependent action.
- **Failed QA/check:** candidate remains unmerged. Preserve its exact identity and
  failure evidence; do not rerun the same consumed QA generation.
- **Partial publication:** reconcile branch/PR/merge state read-only before any
  retry; use idempotent GitHub operations and never rebase or force-push any
  published, shared, retained, or reviewed branch. Create and preserve a fresh
  successor ref instead.
- **Bad merged feature:** use a new issue-linked revert PR to the governed target,
  preserving history and evidence. Do not rewrite or hard-reset.
- **Bad component composition:** pin the previous known-good component manifest,
  replay the journal to the checkpoint, verify inverse effects, and preserve the
  failed manifest/evidence for diagnosis.

## 7. Step 5 - Bounded ContextForge continuity

Step 5 begins only after Step 4 has either integrated or explicitly blocked its
eligible actions. It does not preempt T1/T2 architecture work.

1. Re-verify issue-396
   `bb4e6a5974f2b22265c76b1e1bbef0883a6c1613` and 17-path overlay SHA-256
   `4e4b66ba6408df84160d4b9795073d63dade64e01dfab4f3a2f4df74ddf62fb4`
   without treating pass 18 as valid pairing.
2. Select one still-material user-frontdoor/Serena-root successor from the
   recorded frontier; define its bounded acceptance and non-claims.
3. Make a material successor in the issue-396 worktree, freeze a new exact
   implementation generation, and obtain exactly one independent attributable QA.
4. Only an accepted successor may be coherently committed, pushed, and proposed
   to ContextForge `dev-root` through its own issue/PR governance.
5. Run fresh isolated Pi/OpenCode user sessions only after code and configuration
   gates pass; prove selected service visibility, callability, root identity,
   cross-client non-suppression, cleanup, and LiteLLM-only behavior.
6. Keep removal-journal work, PR 392, root residue, old worktrees, and unrelated
   lifecycle changes separate unless their own issue and pairing gates activate.

## 8. Completion criteria for this roadmap

Step 4 is complete when every item in section 4 is either integrated through its
accepted protected path or retained with the stated exact reason and resumption
condition, and all actions/checkpoints are recorded. The roadmap itself is
complete only when the complete-system gates in
`docs/original-intent-traceability.md` hold together against exact component
identities. Until then, each tranche creates a stable recyclable basis for the
next without redefining partial success as the whole.
