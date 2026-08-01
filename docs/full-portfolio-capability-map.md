# Full-portfolio capability map and authentic-slice gate

**Status:** Step-2 output and Step-3 planning input, not an implementation-readiness claim
**Evidence date:** 2026-08-01
**Authority:** `initial-user-msg.md`, `SYNTHESIS.md`,
`docs/original-intent-traceability.md`, accepted decisions, conditioning open
questions, foundational cognitive sources, and source-inspected donor projects

## 1. Purpose and claim boundary

This map assigns every material dimension of the original noetic-dev intent a
canonical authority or proposed contract home, concrete donor evidence, a
maturity state, dependencies, a success gate, and a reasoned disposition. It is
the expansion gate for a new integration plan. It does not make the issue-32
roadmap authoritative, select a production runtime, accept dirty donor work, or
claim that noetic-dev already has an integrated runtime.

The current verified judgment is asymmetric:

- noetic-dev has an accepted cognitive constitution and thin composition-root
  boundary;
- Telos, noetic-pi, cognitive-disciplines, genus-router, mentality, Serena,
  ContextForge, and the client/deployment projects provide substantial donors;
- the canonical dispatcher, portable controller, minimal integrated cognitive
  program, causal-event append authority, semantic-memory component,
  authenticated effect boundary, and authentic end-to-end slice are absent;
- governance and portfolio reconciliation may gate protected integration or
  publication, but may not gate independent contract, donor, component, or
  authentic-runtime work; and
- complete-system success remains broader than the first authentic slice and
  includes two runtime adapters, all four model modalities, observability,
  attach, development-pipeline conformance, clean composition, and release.

## 2. Evidence and identity boundary

The repository identities below are local observations. No fetch was performed,
so `origin/*` names are local remote-tracking snapshots rather than claims about
current GitHub state.

| Project/worktree | Inspected local identity | Evidence condition |
|---|---|---|
| noetic-dev composition root | `main@29196a67349537d6f8a8a711df11b86da0430857`, equal to local `origin/main` | Dirty governance/traceability work; not an immutable candidate |
| issue-32 roadmap | `issue-32-canonical-roadmap@3d3c1d45d05de69d4f3cb1de6fb137dd6b2e0e6f` | One local commit beyond local `origin/issue-32-canonical-roadmap@37b24e09e685dec09d7a6289c83209ff63e6843c`; unmerged and blocked |
| issue-65 OpenCode spike | `issue-65-opencode-spike@8fcb1c5` | Bounded non-evidence prototype; unmerged |
| Telos | `main@951f3a9c1e9eec2e64848e44a61e050a9dc56464` | Six local commits beyond local upstream plus extensive dirty work; retain |
| noetic-pi | `public-export-launch-prep-20260430@683b53b06714d0aadd49c5852140b708c5abba69` | Extensive dirty donor tree; retain and inspect selectively |
| cognitive-disciplines | `main@923686521b78a4c0cb2e86a23a6eb5d4f9e0c5e4` | Clean at inspected upstream |
| genus-router | `main@4ff584e2e5d190b7e25dc0a4607c494a50069b83` | Clean and one commit behind local `origin/main@f2b839b0cfc737c4c1f0a46d3d519d414529545c` |
| saeproj | `pi2-governance-adoption@fcc4bc465cd82256cec3d6cfc7e6958510291c9d` | Dirty active research, no configured upstream, one stash; retain |
| ContextForge issue 396 | `bb4e6a5974f2b22265c76b1e1bbef0883a6c1613` | Seventeen tracked dirty paths; pass-18 transcript exists but independent implementer/QA identities are not attributable |

Maturity terms are: **authoritative** (accepted contract or judgment),
**reusable donor** (source-tested mechanism worth re-instantiating),
**prototype** (bounded evidence without production authority), **research**
(qualified empirical/theoretical inquiry), **runtime-only** (observed local
deployment/configuration), and **absent** (required canonical capability is not
implemented).

Disposition terms are: **integrate now** (composition-root authority or clean
contract work), **bounded extraction** (re-instantiate selected invariants),
**retain** (preserve in its independent home), **defer** (sequence a production
integration without parking the capability track), and **deprecate** (stop using
the project or pattern as an active architectural basis).

## 3. Complete capability matrix

| Capability / telos | Canonical authority or proposed exact home | Existing implementation and evidence | Maturity and dependency | Executable success gate | Disposition |
|---|---|---|---|---|---|
| Complete noetic-dev product | This composition root owns canonical contracts under planned `spec/`, component pins under planned `config/components/`, composition under planned `compose/`, and integration proof under planned `tests/integration/` | `AGENTS.md`, `SYNTHESIS.md`, `docs/original-intent-traceability.md`, `DECISIONS.md` | Authoritative constitution; integrated product absent. Depends on every material row below | A clean environment resolves exact pins and passes the authentic slice plus all complete-system gates without donor coupling | Integrate constitution now; build incrementally |
| P1-P4 recurrent form | `docs/cognitive-backbone.md` and the machine-facing contracts planned under `spec/cognition/` | Foundational corpus under `saeproj/docs/foundational/`; cognitive-disciplines packets and validators | Authoritative form; reusable/prototype program donors | Operations are recurrent, differentiated, attributed, and separately evidenced; labels or deterministic states cannot stand in for cognition | Integrate now |
| Human authorization and responsibility | Root authority contract planned at `spec/authority/authorization.v1.schema.json`; Telos mediates the authorized purpose; the first local slice uses the bounded kernel-peer/Unix-socket contract in `dec-20260801-0008` | Goalchains, principles, reproductive clauses, and accepted human semantic boundary | Authoritative boundary plus selected local contract; remote/multi-user production authority remains conditioned by `oq-20260801-0003` | A real trace binds an authenticated human principal, end, scope, expiry/revocation, and separate final adjudication | Implement the selected local contract; keep broader production authority open |
| Telos purpose continuity | Telos repository, pinned by the root | `packages/core/src/model.ts`, goalchain persistence/tools, Pi and OpenCode projections | Reusable donor and accepted teleological spine | Purpose, principles, clause, provenance, and continuation survive restart and remain separable from execution and semantic truth | Retain and version interface |
| Typed delegation and dispatcher | Telos repository; root contract planned at `spec/telos/delegation.v1.schema.json` | `packages/core/src/schema.ts` has delegation records and `delegated-pending`; `packages/core/src/continuation.ts` does not enact delegated work | Dispatcher absent; schema donor. Depends on authority, controller admission, result, cancellation, and event contracts | At-least-once delivery is durably keyed, deduplicated, retryable, cancellable, crash-resumable, replay-safe, reconcilable, and separately adjudicable | Bounded implementation in Telos after connective contracts |
| Goalchain continuity tools | Telos core plus runtime-neutral MCP surface; root pins its contract/version | Current goalchain CRUD, provenance, continuation, mutation, compaction, and runtime projections | Reusable donor; not a dispatcher or controller | The same exact goalchain is readable and safely continuable across selected runtimes with provenance and no implicit effect authority | Retain; extract/runtime-neutralize only where evidence requires |
| Deterministic executive controller | Root contract planned under `spec/controller/`; canonical implementation home is new `somebloke1/noetic-controller` | noetic-pi APM: `packages/apm/src/plan.ts`, wave lifecycle, dependency roles, transactions, recovery, ordinals, and tests | Canonical implementation absent/unpinned; donor pinned at `683b53b06714d0aadd49c5852140b708c5abba69`. Depends on connective contracts, selected SQLite state/outbox, event consistency, and effect port | Property/fault tests cover legality, waves, ordinals, exact QA/remediation cardinality, duplicate admission, cancellation, exhaustion, stale writers, restart, rebuild, and deterministic recovery without semantic-truth claims | Initialize home, then bounded superior re-instantiation; do not lift APM wholesale |
| Typed work and identity | Root schemas planned at `spec/controller/work-unit.v1.schema.json` and `spec/identity/actor.v1.schema.json` | noetic-pi dependency roles and ordinal identities; candidate governance exact pass/generation identities | Mixed donor/prototype; authenticated actor binding absent | Unknown roles/transitions fail closed; principal, actor, runtime, model, component, run, generation, and pass identities remain distinct and attributable | Define contracts before implementation |
| Minimal cognitive program | Root program contract planned at `spec/programs/bounded-change-inquiry/v1/`; canonical implementation home is new `somebloke1/noetic-programs` | cognitive-disciplines cycle/packet donor pinned at `923686521b78a4c0cb2e86a23a6eb5d4f9e0c5e4`; frozen M0/M1 traces are conformance fixtures only | Canonical integrated program absent/unpinned; donor/prototype evidence | The program runs over fake and reference runtimes, emits attributed P1-P4 packets, preserves questions/evidence/judgments, and participates in the first authentic slice | Initialize and implement before, not after, the first authentic slice |
| `development_pipeline.v1` | Root canonical contract planned at `spec/programs/development-pipeline/v1/`; implementation home is `somebloke1/noetic-programs` | `initial-user-msg.md` names `design_intent -> abstract_design -> implementation_procedure_design -> implementation`; `docs/original-intent-traceability.md` positionally normalizes it to canonical `design_intentions -> design -> implementation_procedure -> implementation`; noetic-pi `packages/apm/src/plan.ts` currently implements only the first three accepted/donor-current phases; the issue-65 candidate separately defines the `development.verified-change/v1` prototype | Rich donor plus prototype; canonical portable program absent/unpinned. Depends on controller and minimal-program lessons | All four canonical phases run through common contracts over fake and reference runtimes with frozen generations, bounded remediation, exact QA pairing, source-name provenance, and separate adjudication | Bounded extraction after first slice; active, not abeyant |
| Independent implementation:QA pairing | `AGENTS.md`, `docs/development-practices.md`, controller transition contract, and event lineage schema | Candidate governance cardinality/identity checks; noetic-pi instead creates one QA agent per implementation wave | Authoritative policy plus candidate enforcement; noetic-pi donor mismatch | Every frozen implementation/remediation generation has exactly one separately identified, read-only, candidate-bound adversarial QA pass; zero, duplicate, stale, writable, shared, or self-authored QA fails closed | Integrate invariant now; correct donor behavior |
| Critical judgment and adjudication | Cognitive-program P3 report plus separate Telos P4 disposition contract planned under `spec/judgment/` | noetic-pi QA/adjudication donors and frozen trace separation | Reusable donor; canonical contracts absent | Controller success cannot complete the purpose; semantic claims remain attributed evidence until an authorized, separately recorded disposition | Define with program and Telos result contracts |
| Attributed causal-event envelope | Root schema planned at `spec/events/cognitional-event.v1.schema.json` | noetic-pi volatile event bus, APM event rows, and M0/M1 attributed fixtures are insufficient donors | Canonical envelope absent. Depends on identity, privacy, versioning, and temporal-scope decisions | Events require version, event ID, causal parent, correlation/run, principal/actor, P1-P4 attribution, component/runtime/model identity, generation/pass, temporal scope, evidence refs, redacted payload digest, and journal position | Integrate contract now |
| Canonical event append/replay authority | New `somebloke1/noetic-evidence` `journal` package is the selected sole canonical append authority; root pins it and controller-local state remains separate | APM SQLite transactions are donors; noetic-pi event append can be swallowed and its bus is volatile | Canonical implementation absent/unpinned; SQLite 3.45.1-compatible single-writer journal, idempotent append, and at-least-once outboxes selected by `dec-20260801-0007` | Atomic local append, idempotent delivery, causal completeness, concurrent-writer handling, crash-at-boundary recovery, deterministic replay, schema evolution, redaction, and read-only projections pass | Initialize and implement independently; never claim cross-service exactly-once |
| Controller-local command/state persistence | `somebloke1/noetic-controller` owns private `controller.sqlite` behind `spec/storage/controller-store.v1.schema.json`, with transactional outbox; it is not the causal-event authority | noetic-pi APM schema/transactions/rebuild behavior | Selected design; canonical implementation absent/unpinned; SQLite 3.45.1-compatible | State reconstructs from accepted commands plus canonical event positions; outbox retries stable event IDs; divergence and stale writers fail closed | Initialize and bounded extraction |
| Semantic session memory | New `somebloke1/noetic-evidence` `memory` package owns derived `memory.sqlite`; provenance contract planned at `spec/memory/semantic-memory.v1.schema.json` | noetic-pi `packages/session-search/src/store.ts` stores sessions, summaries, labels, embeddings, and BM25 retrieval | Selected home/design; canonical implementation absent/unpinned; semantic similarity retrieval and canonical-event integration incomplete | First slice persists and retrieves a provenance-linked reason/evidence summary after restart; complete gate adds cross-session summarization, embeddings, semantic retrieval, retention, privacy, temporal scope, uncertainty, and deletion behavior | Initialize and bounded extraction; do not call BM25 alone semantic search |
| Replay, recovery, and rollback | Cross-component contracts in root; each stateful component owns local recovery; root owns integrated proof and known-good pins | APM retries/transactions/reconciliation; ContextForge rollback/lifecycle donors; Git inverse patch is a safe first effect | Mixed donor; integrated proof absent | Forced duplicate, cancellation, crash at every persistence/effect boundary, result replay, rebuild, upgrade, inverse effect, and exact known-good restoration preserve one coherent history | Contract and test from first slice onward |
| Workspace/effect authority | Root effect contract planned at `spec/effects/workspace-patch.v1.schema.json`; `somebloke1/noetic-opencode-adapter` owns the selected deterministic first effect executor, separate from agents | ContextForge authorization, stale-plan, write-set, lifecycle, and verification donors; issue-65 tokenless handoff fixture | Selected bounded local contract in `dec-20260801-0008`; canonical implementation absent/unpinned; remote production authority remains open | Kernel-peer admission plus base/tree, declared root/path allowlist, symlink policy, patch bound, expiry/revocation, idempotency, credential isolation, inverse effect, and postcondition are mechanically enforced | Initialize and implement bounded local contract; expand authority before production |
| First reference runtime adapter | New `somebloke1/noetic-opencode-adapter`; root contract planned under `spec/runtime/runtime-adapter.v1.schema.json` | OpenCode 1.18.9 local binary SHA-256 `7c4d91c84d2bfdeabb59257e3490c5e5acb08f2aacb3e42f3ddc296a1c3f1aca`; Telos integration and issue-65 tokenless prototype exist, but candidate policy remains `runtime_adapter_ready: false` | OpenCode selected and locally pinned by `dec-20260801-0006/0009`; canonical adapter absent/unpinned and not runtime-ready | Exact adapter executes the authentic slice with scoped effects, credential isolation, runtime/model provenance, cancellation, event emission, and restart behavior | Initialize and build; selection is not readiness |
| Portability and second adapter | New `somebloke1/noetic-pi-adapter` conforms to the same root contract | Pi 0.80.3 local binary SHA-256 `af302f231437eaf6f37691bce4b34234fcb626bcb5eb3910d4fc3f6519bf78ca`; other client evidence varies from donor to absent | Pi selected second-adapter target; canonical adapter absent/unpinned; complete-system requirement not needed to begin first slice | The same authentic slice passes without semantic or effect-contract changes on two independent adapters | Active post-slice tranche, not parked |
| Client inventory | Root compatibility matrix; adapters remain external components | Pi rich donor; OpenCode prototype; ContextForge harnesses for Codex/Claude/Gemini; Goose research; Kilo/VS Code equivalent absent; desktop configuration is runtime-only | Mixed prototype/research/runtime-only/absent | Each claimed client has exact version, config, tool/resource visibility, routing, cancellation, identity, cleanup, and conformance evidence | Retain candidates; add only by measured value |
| Model selection and universal access | genus-router independently owns honest selection; LiteLLM owns all model invocation; new `somebloke1/noetic-model-substrate` owns secret-free registration/deployment contracts; root binds exact pins/config | genus-router `f2b839b0cfc737c4c1f0a46d3d519d414529545c`; LiteLLM 1.81.10 local evidence; candidate model policy | Reusable donor plus accepted policy; canonical substrate component absent/unpinned and configuration drift exists | Every model invocation classifies/selects via genus-router, invokes only through LiteLLM, records exact selected and actual model identity, reports outcome, and proves failure/reroute behavior | Initialize substrate home; reconcile policy before integration |
| Generative/reasoning substrate | Replaceable servers behind LiteLLM, selected by genus-router | Candidate policy and local LiteLLM routes; direct endpoints still exist in donors | Mixed reusable config/runtime-only | Real task proves select, LiteLLM invocation, exact model evidence, bounded failure/reroute, and outcome feedback | Integrate after configuration convergence |
| Vision substrate | Replaceable multimodal server behind LiteLLM; genus-router must gain an explicit vision genus/task contract | Founding source reports llama.cpp Qwen vision; inspected genus-router task kinds/registry lack vision | Runtime-only/prototype; governed route absent | Real image task proves registered vision capability, honest selection, LiteLLM-only invocation, result evidence, failure/reroute, and outcome feedback | Active complete-system track; add explicit route |
| Embedding substrate | Replaceable embedding server behind LiteLLM; genus-router selects embedding capability | Snowflake Arctic Embed2 local route/config; donor session-search uses direct endpoints in places | Runtime-only/reusable config with bypasses | Real embedding request uses canonical LiteLLM route, records model/version/vector contract, handles failure/reroute, and feeds provenance-preserving memory | Reconcile and integrate |
| ASR/audio substrate | Replaceable ASR service behind LiteLLM; genus-router selects ASR capability | Qwen3-ASR loopback service and router expectation; inspected LiteLLM registry lacks matching model | Runtime-only with a static integration break | Real audio transcription proves registered route, LiteLLM invocation, model/result evidence, failure/reroute, and outcome feedback | Repair route before capability claim |
| Serena semantic agents | New `somebloke1/noetic-serena-adapter`; root records versioned attachment metadata only | ContextForge create/status/verify/remove scripts, dynamic ports, systemd, and records | Selected home absent/unpinned; reusable donor; current issue-396 wrong-root successor remains unresolved | Stable target-bound canonical root, create/status/verify/remove, identity, port, restart, failure, and cleanup pass without transport coupling | Initialize later; bounded extraction/integration |
| mentality governance | New `somebloke1/noetic-mentality`; root defines ledger usage and authorization scope | FastMCP governance CRUD and current project ledgers | Selected home absent/unpinned; reusable donor; transport authorization/scoping needs proof | Repository scope, finite statuses, attribution, concurrent updates, transport authorization, backup/recovery, and runtime-independent visibility pass | Initialize later and pin interface |
| Skills and semantic agents | New `somebloke1/noetic-resources`; root manifest pins compatibility and authority | cognitive-disciplines plugin, local skills, OpenCode/Claude agent resources | Selected home absent/unpinned; mixed reusable donor/prototype | Package identity, instruction provenance, declared tools/effects, runtime compatibility, no implicit authority, and conformance tests are explicit | Initialize and bounded extraction; do not bake user-global config into product |
| Read-only observability | New `somebloke1/noetic-observer` consumes canonical events; root owns projection contracts and integrated proof | noetic-pi web observability/endpoints and TUI/web donors | Selected home absent/unpinned; reusable donor; canonical composition absent | Real and replayed event views explain causal state, missing evidence, readiness/blocking, agent census, and QA lineage while enforcing privacy and exposing no command authority | Initialize after event journal; privileged control deferred |
| Attach/live visibility | New `somebloke1/noetic-attach-tmux`; browser PTY remains optional | pi2 tmux donor and noetic-pi browser PTY donor | Selected home absent/unpinned; reusable donor; integrated proof absent | Identity, isolation, reconnect, command-length, teardown, restart, and recovery pass; attach cannot become event or governance authority | Initialize and bounded tmux extraction; defer browser production integration |
| noetic-pi-docker product instance | Remains its own repository/product evidence; root records provenance only | Reproducible Pi deployment and operational probes | Prototype/runtime-only prior product instance | Exact basis/product identities remain distinct; startup never satisfies noetic-dev architecture or portability gates | Retain as deployment fixture; never use as composition basis |
| SAE/GEH research | saeproj independently owns research; root owns a versioned evidence-qualified feedback seam | Foundational theory, empirical controls, negative results, proxy geometry; actual cognition-specific validity unresolved | Active research, explicitly non-gating for first runtime | Reproducible operation discrimination, content-invariance, transfer, controls, negative results, calibrated confidence, and useful downstream change; production registration requires separate judgment | Retain active research; defer only unproven production model use |
| ContextForge optional transport | External ContextForge/cf-controlplane adapter only; plain MCP remains default | Strong lifecycle/authorization/policy/verification donors and current 4445 harness; issue-396 dirty evidence is not accepted authority | Reusable donor/prototype, outside backbone | Promotion requires measured multi-host/shared-continuity need, replaceability, authorization, privacy, security, recovery, and accepted end-to-end evidence | Bounded extraction; otherwise retain/deprecate backbone role |
| Lifecycle, deployment, removal, and release | Root owns component manifest, compatibility, release policy, and integration proof; components own local lifecycle | ContextForge lifecycle/removal donors; noetic-pi-docker operations; candidate delivery governance | Mixed donor/advanced blocked prototype; authoritative release path absent | Clean install, health, stop/restart, upgrade, rollback, uninstall/removal journal, license, exact-SHA QA, protected trust, immutable release identity, and known-good recovery pass | Develop in parallel; release remains blocked until gates pass |
| Security, privacy, credentials, and effect boundaries | Root contracts and threat decisions; deterministic executors/adapters enforce least authority | issue-65 credential-isolation fixture; ContextForge authorization donors; current memory/raw-session risks | Prototype/donor; production contracts absent and conditioned by `oq-20260801-0003` | Agents receive no provider/Git/SSH/host credentials; effects are scoped and revocable; events/memory are redacted, retained, and deleted by policy; bypasses fail closed | Resolve minimum slice contract before real effect; expand before release |

## 4. Contradictions and corrections carried into planning

The following are blockers or explicit corrections, not silent roadmap details:

1. The issue-32 roadmap's D5 can currently pass without a minimal cognitive
   program or provenance-preserving semantic memory, while D6 schedules programs
   afterward. That ordering contradicts the accepted executable spine and is not
   accepted as the next integration plan.
2. D3a currently depends wholly on D2 even though D2 publication authority is
   blocked by an external trust dependency. Governance may block merge/release,
   but donor characterization, component decisions, contract design, and
   independently testable implementation proceed in parallel.
3. The roadmap assigns a durable controller journal and later assigns a root
   state/event journal without one append authority. The corrected design keeps
   controller-local command/state persistence separate from one canonical causal
   event append/replay authority; the root owns contracts and proof, not runtime
   appends.
4. OpenCode 1.18.9 is selected as the first local reference runtime by
   `dec-20260801-0006/0009`, but its candidate policy remains `contract-only` and
   the canonical adapter is absent. Selection and a local binary digest do not
   establish runtime readiness or source/release provenance.
5. `config/model-policy.json` forbids direct provider access while several
   `governance/model-profiles.json` roles name `openai-codex/*`. The candidate D2
   machine/prose convergence gate is therefore not green.
6. noetic-pi's per-wave QA behavior does not satisfy exact one-QA-per-frozen-
   implementation/remediation-generation policy and cannot be adopted unchanged.
7. Vision has no inspected genus-router task/registry entry; ASR is selected by
   genus-router but absent from the inspected LiteLLM registry; direct embedding
   and ASR callers remain in donor/runtime surfaces. Complete multimodal claims
   remain false.
8. Telos has delegation schema and guard state but no dispatcher; its continuation
   path does not make `delegated-pending` work actionable.
9. noetic-pi event rows/bus and frozen M0/M1 traces are donors/fixtures, not an
   authenticated durable causal-event authority.
10. ContextForge authorization and lifecycle work, including the issue-396 dirty
    worktree, remains optional donor evidence until a valid exact pairing and
    later promotion judgment exist.

## 5. Corrected dependency and tranche order

The order distinguishes a critical architecture/runtime path from parallel
conditioning work. It intentionally prevents D2, ContextForge, portfolio audit,
or publication machinery from becoming the project telos.

```text
accepted constitution and traceability
              |
              v
minimum P3/P4 decisions -----------------------------------------+
(component homes, first runtime, authority/effects,              |
 event writer, persistence/privacy, compatibility, rollback)     |
              |                                                  |
              v                                                  |
versioned connective contracts                                   |
              |                                                  |
       +------+------+-------------+----------------+             |
       |             |             |                |             |
       v             v             v                v             |
Telos dispatcher  controller  minimal program  journal+memory    |
       |             |             |                |             |
       +------+------+-------------+----------------+             |
              |                                                  |
              v                                                  |
first runtime/effect/model adapter                               |
              |                                                  |
              v                                                  |
pinned integration skeleton -> authentic slice -> first stable base
              |
       +------+------+----------------+----------------+
       |             |                |                |
       v             v                v                v
development.v1  observability+attach  second adapter  all modalities
       |             |                |                |
       +------+------+----------------+----------------+
              |
              v
clean reconstruction, lifecycle, hardening, release

Parallel from the accepted base:
  governance/source convergence (gates protected integration/publication only)
  donor characterization and conformance fixtures
  SAE/GEH research and feedback seam
  bounded client/runtime trials
  bounded ContextForge evaluation
```

The minimum decisions and contracts should be small enough to permit parallel
component work. They must not attempt to settle every future privacy, client, or
model question before the first slice.

## 6. First authentic vertical slice

### 6.1 Bounded purpose and effect

The reference slice enacts one reversible, allowlisted patch to one declared file
in a disposable issue worktree, runs one deterministic test, and retains a
mechanically verified inverse patch. The effect is real but bounded: agents may
propose artifacts, while a deterministic executor alone can apply the authorized
patch after checking principal, purpose, base/tree identity, root, path allowlist,
expiry/revocation, patch bounds, idempotency, and postconditions.

The slice is not merely patch-and-test delivery. It must execute a minimal
versioned `bounded-change-inquiry/v1` cognitive program before implementation:

| Operation | Required attributed packet |
|---|---|
| P1 attentiveness | Observed authority, target/base/tree, source evidence, current behavior, test evidence, uncertainties, and evidence references |
| P2 intelligence | At least one change hypothesis, proposed design, expected consequences, inverse effect, and unresolved questions |
| P3 reasonableness | Independent critical judgment of evidential sufficiency, alternatives, risks, falsifiers, and whether the design warrants action |
| P4 responsibility | Attributed action recommendation under the authorized end, scope, reversibility, and residual uncertainty; it does not impersonate the human authority or final Telos adjudication |

The accepted program output freezes the implementation generation. One
implementer produces the candidate effect with no QA, approval, publication, or
out-of-scope authority. Exactly one separately identified, read-only QA pass
attempts to falsify that generation. A rejected QA may create one bounded
remediation generation, which receives exactly one fresh QA pass. The controller
reports structural success or exhaustion; Telos separately reconciles and records
the final disposition under the humanly authorized purpose.

### 6.2 Required event and memory evidence

At minimum, the canonical journal records:

```text
telos.purpose.authorized
telos.delegation.created
dispatcher.delivery.attempted
controller.run.admitted
program.operation.reported        # one attributed event for each P1-P4 packet
controller.implementation.started
effect.proposed
effect.authorized
effect.applied
qa.verification.started
qa.verification.adjudicated
controller.result.reported
memory.summary.persisted
memory.summary.retrieved
telos.result.reconciled
telos.sub_goal.adjudicated
effect.rolled_back
```

Each event satisfies the envelope gate in the matrix. After a forced restart, a
new session must retrieve the prior purpose, evidence, P3 judgment, P4
recommendation, QA disposition, and effect/rollback state through the semantic-
memory port with links to source events and explicit uncertainty. The first slice
does not prove complete embedding/search quality, but it does force durable,
provenance-preserving semantic memory to participate rather than accepting a
post-hoc log.

### 6.3 Mandatory falsification tests

1. Reject unknown versions, fields, identities, roles, transitions, and
   incompatible component pins.
2. Deliver the same delegation and result twice; admit one run and apply one
   effect.
3. Crash at every persistence/effect boundary and reconstruct controller state,
   event history, memory provenance, and effect status.
4. Reject zero, duplicate, shared, stale, self-authored, writable-source, or
   wrong-candidate QA records.
5. Reject undeclared paths, stale base/tree identities, symlinks, oversized
   patches, expired/revoked authority, and repeat application.
6. Prove agents receive no provider, GitHub, SSH, or host credentials and cannot
   bypass the selected runtime, genus-router, or LiteLLM boundaries.
7. Bind genus selection to the actual LiteLLM request/model and retained outcome.
8. Prove structural validators cannot assert semantic adequacy, actual cognition,
   or responsible judgment.
9. Prove causal completeness, append idempotency, redaction, replay equivalence,
   and read-only projection behavior.
10. Prove the inverse effect restores the exact pre-effect tree while preserving
    both effect and rollback in history.

Synthetic traces, manually assembled records, controller-only schedules,
successful service startup, or an unverified harness cannot satisfy this gate.

## 7. Complete-system expansion after the first stable slice

The first slice is a stable recyclable base, not the complete product. Completion
still requires:

- the full four-phase `development_pipeline.v1` over common program/controller
  contracts;
- a second independent runtime/client adapter running the same authentic slice;
- real generative/reasoning, vision, embedding, and ASR tasks through
  genus-router and LiteLLM with outcome feedback;
- provenance-preserving cross-session summarization, embeddings, semantic search,
  temporal scope, privacy, retention, uncertainty, and deletion;
- read-only event-derived web/TUI observability and tmux-first attach;
- clean reconstruction, component upgrade, failure injection, rollback, removal,
  and known-good restoration;
- active SAE/GEH research with reproducible controls and an evidence-qualified
  feedback seam, without smuggling proxy results into production claims; and
- license, security/authority adjudication, exact implementation:QA evidence,
  protected release, immutable identity, and post-integration verification.

## 8. Step-3 acceptance gate

A revised integration plan is valid only when it:

1. cites this map and assigns every row an active tranche, conditioning open
   question, or one of the true deferrals in
   `docs/original-intent-traceability.md`;
2. preserves the corrected parallel/critical-path order rather than making D2 or
   ContextForge a global prerequisite;
3. places the minimal cognitive program, canonical events, and semantic memory
   inside the first authentic slice;
4. names the selected first runtime, second-adapter track, sole event append
   authority, controller-local persistence, exact current runtime/donor pins, and
   every new component home; an honestly absent component must be marked
   `absent/unpinned` with a one-generation initialization gate that produces its
   first real immutable SHA before dependent integration, never an invented pin;
5. reconciles LiteLLM-only policy, model profiles, explicit vision routing, and
   the ASR registry before claiming substrate convergence;
6. gives every implementation/remediation generation exactly one independent,
   attributable QA pass and treats unattributable transcripts as blockers rather
   than evidence; and
7. separates protected integration/publication gates from independent component
   progress and leaves unrelated or unverified dirty work undisturbed.

Until those conditions hold, the existing issue-32 roadmap remains useful donor
evidence but is rejected as the complete current Step-3 plan.
