# Decisions

<!-- governance-crud:start id=dec-20260711-0001 -->
## dec-20260711-0001: Mentality ledger practice for the synthesis effort

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: practice,governance,synthesis
- Confidence: 0.9

Durable memory for the synthesis effort (finding the correct + practically-correct backbone to integrate the user's ~8 projects into one development+cognitive framework).

LEDGER USE (repo=/home/dgk/workspace/synthesis):
- knowns: grounded, verified observations (P1 data / P2 insight). Cite the source file/evidence.
- decisions: adjudicated judgments and choices (P3 judgment / P4 decision). Record rationale + confidence.
- open-questions: unresolved issues needing user input or more evidence.
- abeyant-intentions: deferred work to revisit.

DISCIPLINE (mirrors the user's P1-P4 cognitional model + AGENTS.md separation of activities):
- Record a KNOWN as fact only after verifying against actual source, never from plausible prose (adversarial-verification invariant).
- Keep data-gathering (knowns) separate from judgment (decisions); do not smuggle recommendations into findings.
- Set confidence honestly; downgrade when evidence is thin.
- Treat open-questions as first-class; surfacing a real uncertainty beats a false resolution.
<!-- governance-crud:end id=dec-20260711-0001 -->

<!-- governance-crud:start id=dec-20260711-0002 -->
## dec-20260711-0002: Synthesis backbone: telos spine + SMC cognitive form + harvested noetic-pi organs

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: backbone,synthesis,recommendation,telos,smc
- Confidence: 0.85

ADJUDICATED RECOMMENDATION (confidence 0.85; refined by k-20260711-0004 spine-capacity probe; still conditioned on client-scope oq-20260711-0001).

The correct + practically-correct backbone is HYLOMORPHIC, two coupled backbones re-joined:
- FORM (cognitive backbone): SMC / P1-P4 invariant (Attentiveness->Intelligence->Reasonableness->Responsibility, P4 governs recursively) in ONE canonical notation - the 'periodic table' and the design+evaluation grammar for every layer.
- SPINE (development backbone): telos as the portable teleological governor - runtime-pure core, MCP tools, Pi+OpenCode adapters, evolutionary goalchains (goalchain = durable P4 purpose) - on genus-router for model selection over the 2x3090 local-inference substrate.

WHY NOT noetic-pi as spine: most mature (2,069 tests) but coupled to pi-mono at the web-terminal/app layer and its control-plane extraction/public-export is deferred and stuck. It is the richest DONOR, not a movable spine.

HARVEST IS VERIFIED FEASIBLE (k-20260711-0003): the APM disciplines + pipeline depend only on shared-types + sqlite + node-pty (no pi-mono), communicate over a TCP/IPC seam, and are already decoupled from the pi runtime. Re-exposing them as an MCP service is integration work, not a rewrite.

HOW THE SPINE DRIVES - REFINED (k-20260711-0004): Telos STEERS, it does not SPAWN. It governs the host agent via continuation re-injection; it has a delegations schema + 'delegated-pending' status + delegate_context guard, but NO delegation dispatcher yet and no general outbound MCP-client capability. Correct architecture: Telos=P4 governor; the host agent OR a small to-be-built delegation dispatcher = the P1-P3 enactor that calls MCP organs. This is MORE faithful to 'P4 governs recursively', and it names the ONE genuinely-new component the synthesis must build (the delegation/dispatch enactment seam = the user's own 'make Telos multi-agent' intent). Everything else is harvest/integration.

ORGANS to harvest: cognitive-discipline cycles (phronesis, EP audit, differentiated-cognition); design_intentions->design->implementation_procedure->implementation pipeline with QA/remediation; ordinal delegation-tree identity; session embedding+summarization.

DEMOTE: contextforge -> optional transport only; cognitional_notation + cognitive-disciplines -> fold into one shared canonical-notation + discipline spec.

MIGRATION (scheme of recurrence): keep the stable base (telos + SMC + local inference) durable; build the delegation dispatcher as the single critical new seam; treat noetic-pi as recyclable donor across its clean IPC boundary; never block the spine on unlocking noetic-pi's export.
<!-- governance-crud:end id=dec-20260711-0002 -->

<!-- governance-crud:start id=dec-20260711-0003 -->
## dec-20260711-0003: Canonical notation recommendation: P1-P4 + imperative gloss + optional ECN modal markers

- Ledger: decisions
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-08-01
- Tags: notation,canonical,form,p1-p4,ecn,recommendation,awaiting-ratification
- Source: Superseded by explicit 2026-08-01 ratification and constitutional-form decision
- Confidence: 0.8

Recommendation (confidence 0.8; awaits user P4 ratification). Drafted as docs/cognitive-backbone.md.

RECOMMEND P1-P4 as the canonical, machine/structure-facing notation for the cognitional form, because: (1) noetic-pi already uses p1-p4 functional roles and cognitive-disciplines is built as a 'P1-P4 cycle' - zero migration for the largest surfaces; (2) language-neutral + identifier-safe (ECN letters A/I/R/D are English-specific and 'R' collides with the recursion operator R(...)); (3) numeric order encodes the presuppositional structure and composes (P2->P3); (4) names the operation not an English word, fitting a universal 'periodic table'.

PAIR with a fixed human gloss: P1 be attentive / P2 be intelligent / P3 be reasonable / P4 be responsible (use gloss in prose+prompts, code in identifiers).

FOLD ECN in as OPTIONAL modality annotation only: keep its genuinely-additive operator markers ^! (assertoric/enacted) vs ^? (interrogative/sought), e.g. P3^? = judgment under reflection, P4^! = decision enacted. Retires cognitional_notation as a standalone project while preserving its expressive contribution. Lonergan verbs + AGENTS.md activity phrases become crosswalk rows (valid descriptions, not rival notations).

The mapping is grounded in Lonergan Insight (the-notion-of-judgment: P2 = questions for intelligence What/Why/How-often; P3 = question for reflection 'Is it so?' answered yes/no, a personal commitment) and on_emergent_fidelity (imperatives + R(P1->P2->P3->P4->R), P4 governs recursively - which is why Telos/P4 is the governing spine).

STATUS NOTE: this is a PROPOSED recommendation awaiting the user's irreducible P4 ratification - ratify P1-P4-canonical, or flip the primary surface to ECN letters / verbs; the crosswalk is unchanged either way.
<!-- governance-crud:end id=dec-20260711-0003 -->

<!-- governance-crud:start id=dec-20260711-0004 -->
## dec-20260711-0004: Web interface = portable observability+control plane over cognitional events; client is a reversible runtime choice

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: web,observability,control-plane,client,reversible,events,resolution
- Confidence: 0.78

Refinement prompted by user input (2026-07-11) and grounded in k-20260711-0005. Confidence 0.78.

USER TENSION: likes noetic-pi's web paradigm (untapped observability potential) but is uncertain about embedding PTY terminals in the browser; wants one client that is minimalistic + highly-capable + the best medium for expressing the design, yet portable/extensible.

RESOLUTION (dissolves the tension rather than trading off):
1. SEPARATE the two things noetic-pi currently fuses. Verified (k-0005) that the web package already splits terminal.ts (PTY/xterm) from observability.ts / observability-inquiry-panels / sidebar-*-section (event/archive-driven). The value the user likes is the event-driven observability, NOT the terminal embedding.
2. ELEVATE the web interface to a portable OBSERVABILITY + CONTROL PLANE that consumes structured cognitional events (P1-P4 operation traces, agent census, discipline cycle state, pipeline phase/QA state) from the spine (telos) and organs (harvested APM). DEMOTE the PTY-terminal multiplexer to an optional 'attach a terminal' view.
3. Because the plane consumes events (not PTY streams), it is CLIENT-AGNOSTIC. The client (agent runtime) therefore becomes a REVERSIBLE choice, not the backbone - which is what lets portability and the web-interface value coexist.

'BEST MEDIUM FOR EXPRESSING THE DESIGN' - reframed: the medium of expression is the observability+control plane itself (where the cognitional operations become visible), not the terminal and not any single CLI. The terminal is skeuomorphic; observing cognition is the real medium. This is the 'untapped observability potential' the user senses.

CLIENT criteria once decoupled: MCP-native, extensible (can host telos + emit structured events), minimalistic, headless-capable (so the plane observes without the client BEING the UI). Default lean: OpenCode as the portable reference client (open, extensible, telos already works, not pi-mono-locked); Pi retained as the rich existing instance to harvest from; Goose a watch candidate. The client choice is now low-stakes and can be deferred/hands-on-tested without blocking the architecture.

NEW BUILD IMPLICATION: add a structured cognitional-event schema (the observability plane's input contract) as a near-term artifact; it also doubles as the P1-P4 event vocabulary the whole framework emits. This joins the delegation dispatcher (k-0004) as the small set of genuinely-new components.
<!-- governance-crud:end id=dec-20260711-0004 -->

<!-- governance-crud:start id=dec-20260711-0005 -->
## dec-20260711-0005: Consolidate model ACCESS to LiteLLM; keep model SELECTION in genus-router with endpoint pluralism preserved

- Ledger: decisions
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-13
- Tags: litellm,genus-router,model-access,model-selection,substrate,recommendation
- Confidence: high

Superseded by explicit clause-v7/v8 model governance and dec-20260713-0006. The former endpoint-pluralism escape hatch, direct llama.cpp/Ollama caller access, and possible direct embedding/ASR routes are no longer authorized. genus-router remains the selector, but LiteLLM is now the universal access boundary for every harness and modality.
<!-- governance-crud:end id=dec-20260711-0005 -->

<!-- governance-crud:start id=dec-20260711-0006 -->
## dec-20260711-0006: Interface stack: observability+control plane over tmux-native attach (pi2) as the minimalist default; browser-PTY optional

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: interface,tmux,pi2,observability,attach,control-plane,resolution
- Confidence: 0.76

Refines dec-0004 with the pi2/tmux data point (k-0006). User note: pi2 multi-panes agents via tmux, a different paradigm than noetic-pi's browser/PTY. Confidence 0.76.

THREE-LAYER INTERFACE STACK (resolves the browser-vs-terminal tension the user raised):
1. OBSERVABILITY + CONTROL PLANE (the durable value; client/transport-agnostic): consumes the structured cognitional-event stream (P1-P4 traces, census, discipline-cycle state, pipeline/QA state) from telos + harvested organs. This is the 'best medium for expressing the design' and is where the untapped observability potential lives. It does NOT require a browser - it can render to a web view OR a TUI.
2. ATTACH / LIVE-VISIBILITY mechanism (how you SEE/enter a running agent; swappable, not load-bearing):
   - tmux-native multi-paning (pi2's approach): terminal-native, minimalist, no browser, works over ssh; each agent = a pane in a project-scoped tmux session. VERIFIED real in pi2 (agent-mesh.ts). RECOMMENDED DEFAULT for a minimalist client because it matches the user's stated minimalism and is the lightest way to see many live agents.
   - browser PTY multiplexer (noetic-pi terminal.ts): heavier, needs the web app; keep as OPTIONAL for when a browser is already the surface.
3. CLIENT/runtime: reversible (dec-0004).

WHY tmux as default attach: (a) matches 'minimalistic + terminal-native'; (b) the user already has a working implementation in pi2 to harvest; (c) decouples 'see the agents' from 'run a browser'; (d) composes with the observability plane rendered as a TUI, giving a fully terminal-native option AND a browser option from the SAME event stream. Caveat (k-0006): tmux has a ~16KB spawn-command limit - use pi2's minimal-bootstrap + APM-delivered-curriculum pattern; don't push large prompts through the tmux spawn command.

NET: build the observability+control plane against the event stream once; offer BOTH a tmux-native attach (minimalist default, harvested from pi2) and an optional browser-PTY attach (harvested from noetic-pi). The user's browser-vs-terminal question dissolves: it's a rendering/attach choice under one event-driven plane, not an architecture fork. pi2 becomes a THIRD harvest donor (tmux multi-paning + PHAF disciplines) alongside noetic-pi and telos.

OPEN (user judgment, from prior turn, still live): is the plane read-only observability or also an ACT-from control surface (approve gates, steer goalchains, dispatch delegations)? That choice most shapes plane scope.
<!-- governance-crud:end id=dec-20260711-0006 -->

<!-- governance-crud:start id=dec-20260711-0007 -->
## dec-20260711-0007: Target project = the synthesis workspace, promoted to a THIN composition root (integration home of the framework)

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: target-project,composition-root,integration-home,synthesis,harvest-not-host,recommendation
- Confidence: 0.8

User question (2026-07-11): what is the target project for this synthesis - the current project? where harvested pieces become the synthetic form? Confidence 0.8 (recommendation; user ratification is the P4 act).

RECOMMENDATION: YES - the `synthesis` workspace is the target, but promote it from 'deliberation record' to a THIN COMPOSITION ROOT (the integration/assembly home of the framework). Crucially, it COMPOSES components; it does not ABSORB their code (harvest-not-host applied to the target itself).

THREE DISTINCT ROLES a 'project' plays here (keep them separate):
1. Deliberation/governance record - research, decisions, ledgers, the recommendation. `synthesis` is this today.
2. Composition root / integration home - where the parts are bound into a running whole: the canonical form spec, the config that wires spine+organs+substrate, the framework's own connective tissue, run/deploy. THIS is the 'target project'.
3. Component homes - where each harvestable capability lives and evolves: telos (spine) in the telos repo; disciplines/pipeline MCP services as NEW packages derived from noetic-pi apm; tmux-attach from pi2; etc.

DECISION: roles 1 and 2 unify in the `synthesis` repo (its ledgers/SYNTHESIS.md/docs become the governance+specs of the composition root, exactly like the user's other repos carry in-repo DECISIONS/OPEN_QUESTIONS). Role 3 stays external components the root references (submodule or package dep), NOT copied in.

WHERE EACH NEW/HARVESTED THING LIVES (answers 'where do we bring what is harvested into the synthetic form'):
- Delegation dispatcher -> lives in TELOS (it is the spine component's own new capability).
- Cognitional-event schema (P1-P4 event vocabulary) -> authored IN the synthesis root (framework connective tissue, no single donor owns it). This is the root's spec/ contract.
- Observability + control plane -> the synthesis root (or a package it owns), consuming the event schema; renders web or TUI.
- Disciplines MCP service + pipeline MCP service -> NEW components derived from noetic-pi packages/apm (their own package/repo), referenced by the root.
- tmux multi-paning attach -> harvested from pi2 as a component/adapter, referenced by the root.
- genus-router + LiteLLM + local-inference endpoints -> substrate config bound in the root's config/.

CONCRETE SHAPE (proposed) for synthesis-as-composition-root: docs/ (cognitive-backbone.md form spec, SYNTHESIS.md architecture) + governance ledgers + spec/ (cognitional-event schema) + config/ (endpoint registry, genus-router binding, LiteLLM, 2x3090 endpoints) + compose/ (how spine+organs+planes run together) + component references (telos, disciplines-service, pipeline-service, observability-plane, tmux-attach).

PRACTICAL NEXT STEPS implied: (a) `git init` the synthesis workspace (currently not a repo) so the composition root is versioned; (b) optionally give the FRAMEWORK its own name ('synthesis' names the ACT, not the THING) - user's call; (c) distinguish synthesis-as-basis (development/integration) from the composed running framework (product), mirroring the user's own noetic-pi vs noetic-pi-docker split.

WHY THIN not a swallowing monorepo: preserves portability of each component (telos stays Pi+OpenCode portable; organs stay independently testable with their donor test suites), matches the 'durable planes + swappable peripherals' signature, and avoids re-creating noetic-pi's pi-mono entanglement in a new place.
<!-- governance-crud:end id=dec-20260711-0007 -->

<!-- governance-crud:start id=dec-20260711-0008 -->
## dec-20260711-0008: Elevate the deterministic orchestration controller (harvested APM) to a first-class executive plane between telos and agents

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: orchestration,apm,executive-plane,deterministic,telos,layering,harvest,correction
- Confidence: 0.8

Prompted by user correction (2026-07-11): 'the APM was not just an optional sidekick to the cog discipline and pipeline tools, it was approximating a deterministic state machine for pipelines'; and user question on 'the means of ordering multi-agent orchestration'. Grounded in k-20260711-0007. Confidence 0.8.\n\nCORRECTION TO EARLIER FRAMING: dec-0002 listed noetic-pi's mechanisms as 'organs' harvested by telos, which under-weighted the APM orchestration state machine. Refined model: the framework has TWO different kinds of governance, both necessary and distinct:\n1. TELEOLOGICAL governance = telos (P4): WHY - purpose, goalchains, evolution, reproductive clause. Steers.\n2. EXECUTIVE / ORCHESTRATION governance = the harvested APM state machine: HOW/WHEN - deterministic sequencing of multi-agent work. Controls.\n\nARCHITECTURE LAYERING (ordering lives in the executive plane):\n  telos (teleology, P4)\n  -> delegation dispatcher (the new seam; turns a delegated sub-goal into dispatched work)\n  -> DETERMINISTIC ORCHESTRATION CONTROLLER (harvested APM): decomposes into WUs/waves, enforces typed dependency-role ordering legality, sequences waves, runs QA-gate + remediation cycles, spawns/retires agents by ordinal, commits per wave, selects models via genus-router\n  -> AGENTS doing non-deterministic P1-P4 cognitive work per WU\n  -> observability plane observes the whole via the cognitional-event stream\n\nKEY POINTS:\n- The 'disciplines' organ and the 'design_intentions->design->implementation_procedure->implementation pipeline' are NOT separate from this - they RUN ON the orchestration controller. Pipeline = a specific WU/wave program; disciplines = P1-P4 loops dispatched by the same controller. So the earlier 'two organs' (disciplines, pipeline) are better seen as PROGRAMS running on ONE executive organ.\n- The orchestration controller MUST stay deterministic (structural/harness mechanics); semantic judgment stays with agents. Never collapse the two (matches cognitive-disciplines' governing principle and noetic-pi's hard-won separation).\n- Ordering means: sequenced waves + typed dependency-role legality (launch_required vs governing vs future-produced), QA-gate cycling, commit boundaries. Harvest this whole state machine; do not reinvent it (it carries ~1,100 APM tests and multiple compliance campaigns of hardening).\n\nIMPLICATION for target project (dec-0007): the orchestration controller is a major harvested COMPONENT (from noetic-pi packages/apm), referenced by the composition root, and is where the pipeline + disciplines execute. It is arguably the single most valuable harvest.\n\nOPEN QUESTION raised to user: should the orchestration controller be harvested as-is (deterministic APM state machine as a standalone MCP service) or partially re-expressed? Recommendation: harvest as-is behind an MCP facade first (it is proven); refine later.
<!-- governance-crud:end id=dec-20260711-0008 -->

<!-- governance-crud:start id=dec-20260711-0009 -->
## dec-20260711-0009: Naming boundary: system and GitHub repository noetic-dev; local directory synthesis

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: naming,github,remote,noetic-dev,composition-root
- Confidence: 1.0

Final user decision, 2026-07-11, superseding the brief provisional `abide` name before any remote was created. The composed system/product is named `noetic-dev`. The GitHub remote repository must be `somebloke1/noetic-dev`. The existing local composition-root directory remains `/home/dgk/workspace/synthesis` to preserve session and filesystem continuity; directory name and product/repository name need not match. GitHub Project should also be titled `noetic-dev`.
<!-- governance-crud:end id=dec-20260711-0009 -->

<!-- governance-crud:start id=dec-20260713-0001 -->
## dec-20260713-0001: Promote dev to main through a monotonic two-stage protection transition

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: P3,P4,github,promotion,branch-protection,bootstrap
- Source: k-20260713-0001,k-20260713-0002,k-20260713-0003; GitHub branch protection and workflow APIs; GitHub pull_request_target and required-check documentation
- Confidence: high

Adopt a monotonic bootstrap rather than replacing main protections in one leap. First, while main retains its app-bound legacy validate check, one approval, admin enforcement, strictness, linear history, and conversation resolution, land and verify on protected dev a promotion-compatible workflow: it must emit legacy validate for a main-targeting PR and run agent-review from an immutable protected default-branch policy/client rather than the pre-bootstrap main base. After routed review is live and the publication freeze is cleared, open a dev-to-main bridge PR and require both observed checks plus the existing human approval; merge only under the old main gate. Second, after the new workflows exist on main and the intended GitHub-Actions checks have succeeded in-repository, update main protection in one full PUT to add the app-bound new validation and agent-review checks while retaining legacy validate and one approval; read back and exercise a canary. Only after the canary proves latest-SHA binding and failures block merge may a second atomic PUT remove the legacy validate compatibility check and reduce approvals to zero while preserving all new required checks and other protections. Never create an interval with fewer controls. This decision authorizes design only; the active freeze, failed routed Pi frontier, and failed PR #28 agent-review still block execution.
<!-- governance-crud:end id=dec-20260713-0001 -->

<!-- governance-crud:start id=dec-20260713-0002 -->
## dec-20260713-0002: Classify frozen existing work without clearing the freeze

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: P3,P4,audit,freeze,disposition,stacked-prs
- Source: k-20260713-0004; exact GitHub PR heads/files/checks and branch topology; current model-governance decisions
- Confidence: medium-high

Adopt these audit dispositions, which classify preservation strategy but do not approve or merge content. Retain PR #2 as the first architecture candidate, blocked until agent-review is required on dev, then retarget/rebase and review its exact new SHA. Retain PRs #4, #16, #17, #18, and #19 as a dependency-ordered controller/events/Telos candidate chain; each must be rebased only after its predecessor is accepted and must receive current routed exact-SHA review. Recreate/update PR #15 because its roadmap contains stale model-access and sequencing assumptions, while preserving its useful dependency structure. Preserve PR #20 as time-stamped ContextForge research evidence but recreate/revalidate all live topology, security, and continuity claims before acceptance. Supersede/reject PR #21's exact snapshot because direct provider/local model access contradicts mandatory LiteLLM governance; rewrite Issue #10 from the verified genus-router/LiteLLM policy rather than patching the stale contract. Preserve PR #22's attach ideas but recreate it on an accepted base independent of rejected PR #21. Preserve orphan branch issue-11-cognitive-programs/e25083c only as a recyclable candidate; do not open a PR until controller contracts, routed review, and the freeze permit it. Treat PR #28 separately as blocked canary/remediation work under subgoal-781. Do not close, retarget, rebase, cherry-pick, or merge any candidate until the durable audit artifact is independently reviewed; keep the freeze active.
<!-- governance-crud:end id=dec-20260713-0002 -->

<!-- governance-crud:start id=dec-20260713-0003 -->
## dec-20260713-0003: Preserve PR 28 stale-base remediation but integrate it only with routed review

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: P3,P4,pr-28,stale-base,routing,qa
- Source: k-20260713-0005; AR-12; live dev strict protection; clause-v8 model governance
- Confidence: high

Treat Terra's stale-base finding as requirement-mapped and valid for candidate 161b262, while recognizing that strict branch protection plus an immediate protected-base SHA check and base-specific authority context are the minimum sufficient control. Preserve the current uncommitted remediation as recyclable evidence, not as an accepted generation. Do not commit, deploy, or push it from the dirty PR #28 worktree: it has no paired independent QA and retains forbidden direct provider invocation. Resume only after the genus-router/LiteLLM broker path is independently verified, then re-express the stale-base control on a fresh issue-linked generation from the last verified base, pair it exactly 1:1 with adversarial QA, and rerun exact-SHA semantic review. The production release remains unchanged.
<!-- governance-crud:end id=dec-20260713-0003 -->

<!-- governance-crud:start id=dec-20260713-0004 -->
## dec-20260713-0004: Rotate and remove the exposed Qwen backend credential before ASR deployment work

- Ledger: decisions
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: P3,P4,security,credential-rotation,systemd,litellm
- Source: k-20260713-0007
- Confidence: high

The initial response proposed treating the embedded Qwen backend key as compromised and rotating it before ASR work. The user explicitly adjudicated on 2026-07-13: "Ignore, this is not a high risk scenario." Therefore no rotation, unit credential migration, dependent configuration update, or restart is required on account of this observation. The factual known remains recorded without its value, but it no longer blocks ASR work.
<!-- governance-crud:end id=dec-20260713-0004 -->

<!-- governance-crud:start id=dec-20260713-0005 -->
## dec-20260713-0005: Accept the Qwen unit credential risk and continue ASR work

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: P4,user-adjudication,qwen,asr,security-risk
- Source: User response 2026-07-13 superseding dec-20260713-0004
- Confidence: high

By explicit user judgment, accept the locally world-readable Qwen backend credential as a non-high-risk condition in this environment. Do not rotate it or migrate its delivery as part of noetic-dev/ASR work. Continue to avoid reproducing its value in records and keep ASR verification focused on service readiness, LiteLLM-only registration, and real transcription.
<!-- governance-crud:end id=dec-20260713-0005 -->

<!-- governance-crud:start id=dec-20260713-0006 -->
## dec-20260713-0006: Require genus-router selection and LiteLLM-only model access

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: P3,P4,litellm,genus-router,model-governance,sol,terra,luna,fable,embedding,asr
- Source: Explicit user/clause-v8 authority; genus-router PR #5 d085a6d; noetic-dev verified checkpoint ad726a2
- Confidence: high

Every generative, coding, or reasoning task must be honestly classified and selected through genus-router, with selection varying by sophistication. Every invocation must then use the canonical LiteLLM boundary, including Pi, OpenCode, brokers, bare calls, embeddings, and ASR. The active generative set is Sol, Terra, Luna, and narrowly eligible high-value Fable 5, with capability order Sol | Fable > Terra > Luna; standard models use high reasoning. Snowflake Arctic serves embeddings and Qwen3-ASR serves ASR through LiteLLM. Direct provider URLs, namespaces, credentials, direct llama.cpp/Ollama caller access, static model-profile authorization, and manual escalation are forbidden. The required lifecycle is classify -> route_task -> validate canonical reference -> invoke through LiteLLM -> report_outcome, rerouting only after a recorded failure with exclusions. This supersedes dec-20260711-0005 and governs stale PR #21.
<!-- governance-crud:end id=dec-20260713-0006 -->

<!-- governance-crud:start id=dec-20260714-0001 -->
## dec-20260714-0001: Replace the rejected Issue #6 history from verified origin/main

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: genus-router,issue-6,qa,git,governance
- Source: /tmp/opencode/genus-router-issue6-2f328e1-qa/genus-router-issue6-2f328e1-qa-20260714-001/protected/qa-execution-record.json
- Confidence: high

Do not continue Issue #6 by stacking on 156f920, efc0daf, or 2f328e1. Their QA histories are rejected or violate exact implementation:QA pairing. Create one fresh replacement generation from verified genus-router origin/main, implement the complete governed approval feature plus the two surviving 2f328e1 QA findings, verify deterministically, and dispatch exactly one independently guarded protected QA lifecycle for that replacement SHA.
<!-- governance-crud:end id=dec-20260714-0001 -->

<!-- governance-crud:start id=dec-20260714-0002 -->
## dec-20260714-0002: Gate adjudication uses LiteLLM-served Fable xhigh or Sol xhigh

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: model-governance,gate,litellm,fable,sol,xhigh
- Source: user-instruction:2026-07-15
- Confidence: high

The user explicitly authorized six additional hours of autonomous work and directed that gates be adjudicated by Fable xhigh or Sol xhigh through LiteLLM. For the active Issue #8 generation and subsequent noetic-dev delivery gates, Terra/high is not sufficient gate authority. Model selection and invocation must remain honest and evidenced through genus-router plus LiteLLM; no direct provider endpoint or credential path and no relabeling of model/reasoning level is permitted.
<!-- governance-crud:end id=dec-20260714-0002 -->

<!-- governance-crud:start id=dec-20260715-0001 -->
## dec-20260715-0001: Adopt the minimum true Issue #8 credential threat contract and supersede speculative steganography/path-linearizability requirements

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P3,P4,genus-router,issue-8,threat-model,least-complexity,supersession
- Source: https://github.com/somebloke1/genus-router/issues/8; genus-router spec/initial_design.md; systemd.exec/systemd credential API evidence; repeated protected QA artifacts
- Confidence: 0.95

Accepted for genus-router Issue #8. The authoritative contract is the issue plus binding genus-router design and actual systemd credential semantics: direct environment value has precedence; `${TOKEN_ENV}_FILE` then `$CREDENTIALS_DIRECTORY/<lowercase-token-env>` provide bounded file credentials; empty/whitespace/non-printable/oversized/unreadable/nonregular values fail closed without value exposure; systemd credentials authenticate canonical LiteLLM availability without export; no provider-direct access is introduced; routing behavior and TTL availability semantics remain intact. Config and canonical local LiteLLM are trusted in this single-user service. `$CREDENTIALS_DIRECTORY` is stable/immutable for the service lifetime. The following are superseded as speculative and non-finite: reconstructing arbitrary decorated, mixed-transform, cross-field credential steganography across trusted config and returned model IDs; treating in-memory public availability IDs as persistent secret storage; and guaranteeing a mutable pathname cannot change after the final observation. Reinstantiate a small auditable patch from merged `6a6487f`, retain practical no-symlink/stable-read defenses, generic logging, and direct adversarial tests, then gate this exact actual contract with Fable/Sol xhigh.
<!-- governance-crud:end id=dec-20260715-0001 -->

<!-- governance-crud:start id=dec-20260715-0002 -->
## dec-20260715-0002: Clean only demonstrably integrated or superseded genus-router subtrees; preserve noetic unmerged and dirty lines

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P3,P4,subgoal-813,cleanup,least-disturbance,dependency-order
- Source: k-20260715 subtree inventory; exact git tree and GitHub merge evidence
- Confidence: 0.98

Accepted as the first subgoal-813 adjudication. For genus-router, PR-head branches for Issues #1/#4/#6-v2/#8-v10 are integrated because exact source trees equal protected squash-merge trees; Issue #6 v1 and Issue #8 v1-v9/intermediate candidates are superseded by the closed issues' later exact gated merges. Their clean local worktrees/branches and stale merged/closed remote branches may be removed after final readback; protected gate artifacts and the currently depended-on `6a6487f` gate runtime remain. For noetic-dev, do not bulk-delete or merge: retain the genuinely unmerged legacy stack, Issue #11 branch, PR #28, and PR #31; preserve all dirty synthesis-root and Issue #27 changes. The clean merged-source branches for Issues #23/#25 and the exact-tree duplicate Issue #29 policy branch are eligible for later local cleanup only after a focused noetic adjudication records their exact representation. No branch with unique unmerged work or unknown dirty ownership may be removed.
<!-- governance-crud:end id=dec-20260715-0002 -->

<!-- governance-crud:start id=dec-20260715-0003 -->
## dec-20260715-0003: Remove three clean noetic duplicate worktrees while retaining their still-open governance intentions

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P3,P4,subgoal-813,noetic-dev,tree-equivalence,cleanup
- Source: exact git commit/tree/ancestry readback; GitHub Issues #23/#25 bodies and merge references
- Confidence: 1.0

Accepted under subgoal-813. `issue-23-governance-correction` tip `8517e7e` and merged `dev` commit `04f756c` share exact tree `302f93d`; `issue-25-agent-review-canary` tip `ce1bba1` and merged `dev` commit `33e8bbd` share exact tree `a5d9957`; local-only `issue-29-model-routing-policy` tip `8d4176e` and ancestor `01aa791` of retained PR #31 share exact tree `498abae`, and `01aa791` is an ancestor of the PR #31 head. The three worktrees are clean, so their local branches/worktrees are redundant representations and may be removed without losing content. Issues #23 and #25 remain open: their broader trusted-runner/canary intentions are not proved complete merely because source trees merged. Retain those issue intentions and the active PR #31 line; remove only the duplicate local Git representations. Preserve dirty root and Issue #27 worktrees unchanged.
<!-- governance-crud:end id=dec-20260715-0003 -->

<!-- governance-crud:start id=dec-20260715-0004 -->
## dec-20260715-0004: Order the noetic-dev PR queue by routed-review infrastructure, canary, then legacy dependency spine

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P3,P4,pr-orchestrator,emergent-probability,noetic-dev,ordering
- Source: complete 12-PR paginated inventory; protected policy sources; branch protections; exact dependency/file-overlap graph
- Confidence: 0.95

Accepted for pr-orchestrator v1 with `QUIET_TIMER=60`, `PR_PROC_PATTERN=serial`, repository `github.com/somebloke1/noetic-dev`, and policy fingerprint `sha256:dd91c0026830f9e6908c06be3591ee202a050b6525f26d5b546afc9977829312` from protected `dev@33e8bbd`. Initial order: #31, #28, #2, #4, #15, #16, #17, #18, #19, #20, #21, #22. #31 is first because mandatory genus-router/LiteLLM review routing is the conditioning scheme for trustworthy `agent-review`, protected-dev canary survival, and all later exact-head reviews; its deterministic checks are green, it is mergeable, and Issue #8 now supplies systemd credentials, but production byte-limit failure and missing exact independent approval remain. #28 follows because it is the canary and overlaps #31's broker/review surfaces; its dirty local worktree is preserved and prevents unsafe branch repair. #2 is the legacy root but remains on protected `main` and cannot responsibly advance until the `dev` review scheme functions. #4 unlocks the longest technical successor chain; #15 is its roadmap sibling; #16-#22 follow exact stacked bases. Confidence 0.95. Counterevidence: #31 is large (48 commits/46 files) and therefore high survival risk, but delaying it leaves every downstream review path structurally blocked; its frontier remains recyclable because it is still an unmerged `dev` PR.
<!-- governance-crud:end id=dec-20260715-0004 -->

<!-- governance-crud:start id=dec-20260715-0005 -->
## dec-20260715-0005: Keep PR #31 bounded and publish the verified routing remediation as a follow-up

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P3,P4,noetic-dev,pr-31,agent-review,remediation,publication-topology,least-disturbance
- Source: k-20260715-0010;https://github.com/somebloke1/noetic-dev/pull/31;chain-49/subgoal-704;chain-49/subgoal-813
- Confidence: high

PR #31 must remain at its existing bounded head 4177a9d for exact-head review and protected merge. The independently PASSed routing/governance remediation tree 6bd55d94 must be frozen separately, used as the immutable candidate runtime needed to review PR #31, and published only after PR #31 merges as a follow-up based on updated dev. This preserves reviewability: the PR #31 snapshot is 724,398 bytes, while combining the remediation into that PR would produce an 813,262-byte snapshot beyond both configured capture and model-input bounds. The follow-up delta is 179,992 bytes. This decision authorizes neither an unrequested commit nor a protection bypass; immutable commit, deployment, review, and publication must still follow repository authority and exact implementation:QA evidence.
<!-- governance-crud:end id=dec-20260715-0005 -->

<!-- governance-crud:start id=dec-20260715-0006 -->
## dec-20260715-0006: Ratify autonomous-dev and user-protected-main constituent bundle

- Ledger: decisions
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P4,ratification,github,autonomous-dev,protected-main,goalchain,emergent-probability
- Source: Superseded by explicit user correction and dec-20260715-0007; historical synthesis and QA evidence retained
- Confidence: high

The user explicitly ratified the exact bundle `/tmp/noetic-dev-final-holistic-synthesis.md` plus `/tmp/noetic-dev-github-discipline-amendment-v5.md` after final independent adversarial QA returned PASS at high confidence.

The ratified development topology retains the personal repository `somebloke1/noetic-dev`: protected `dev` is the fully autonomous integration boundary from signed Telos issue intent through branch, commit, push, PR, external trusted CI, one independent terminal-QA attempt per exact generation, separately keyed Telos adjudication, squash merge, and reconciliation; protected `main` is the human release/constitutional boundary using immutable dev-derived promotion snapshots, fresh release CI/QA, exact-generation user approval, and fenced merge-commit promotion preserving dev ancestry.

Ratification authorizes mutation of paused `chain-49` and execution of establishment stages E0-E6. It does not claim controls are deployed: Actions, the live runner, credentials, rulesets, Apps, checks, branches, PRs, or services remain unchanged until their ordered effectuation gates are executed and verified. Framework implementation and legacy PR merges remain blocked until E0-E6 pass.

This decision supersedes conflicting active authority in dec-20260713-0001 (GitHub-Actions/agent-review bootstrap), dec-20260713-0002 (legacy freeze dispositions as the integration path), dec-20260715-0004 (serial legacy PR queue authority), and dec-20260715-0005 (PR #31-first publication topology). Their evidence and historical identities remain preserved as donor material; no branch, PR, worktree, or artifact is deleted without byte-complete capture, restoration proof, and successor disposition.
<!-- governance-crud:end id=dec-20260715-0006 -->

<!-- governance-crud:start id=dec-20260715-0007 -->
## dec-20260715-0007: Use the working credential, autonomous dev, and main-only protection

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P4,github,simplification,autonomous-dev,main-protection,credential
- Source: Explicit user corrections and instruction to simplify, tend the goalchain, represent all work, and proceed; /tmp/noetic-dev-github-discipline-simple.md
- Confidence: high

The user explicitly simplified the ratified GitHub discipline after rejecting the speculative credential/control-plane apparatus. The authoritative operating rule is `/tmp/noetic-dev-github-discipline-simple.md`.

Only `main` branch protection is required. `dev` is the autonomous integration branch. Use the existing working credential for GitHub issues, branches, commits, pushes, PRs, visible QA evidence, and merges into `dev`. If a second credential is ever useful, it is only a simple automation identity, especially to author a main promotion PR that the user can approve; it does not imply a credential architecture.

Represent all work visibly in one authoritative GitHub bootstrap issue and comments on every open PR. Preserve existing refs and dirty material, start fresh implementation from current dev, use exactly one independent adversarial QA attempt per frozen implementation generation, merge coherently to dev, and require the user to approve promotion to protected main.

No credential removal/rotation, Actions shutdown, runner quarantine, five-App system, external check authorities, fenced merge brokers, policy-context rotation, drift control plane, or credential audit is authorized or required. The local E0 capture remains historical evidence only and is not a gate.

This decision supersedes the GitHub/credential mechanics of dec-20260715-0006 and `/tmp/noetic-dev-github-discipline-amendment-v5.md`. It preserves the broader recurrent-trace intention, P1-P4 differentiation, donor preservation, genus-router/LiteLLM model governance, and exact implementation:QA pairing.
<!-- governance-crud:end id=dec-20260715-0007 -->

<!-- governance-crud:start id=dec-20260717-0001 -->
## dec-20260717-0001: Automate route attestation with a trusted local operator

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-17
- Updated: 2026-07-17
- Tags: protected-route,attestation,automation,P3,P4
- Source: Knowns k-20260717-0001 through k-20260717-0004 plus code inventory and GitHub API research
- Confidence: high

Adopt the smallest durable recurrence design: repair route_evidence.py to use the stable PR endpoint instead of run.pull_requests; add one operator that discovers completed Agent Review runs, derives exact PR/head/base/artifact identity, creates a fresh detached checkout of the GitHub-verified protected base, executes that base's existing validator, and writes an atomic canonical receipt; schedule it on the trusted local host using existing local gh authentication without storing a repository workflow credential. Reject a parallel validator and reject repository_dispatch. A workflow_run attester may be added later for OIDC receipt signatures but cannot currently establish administrator-visible no-bypass state.
<!-- governance-crud:end id=dec-20260717-0001 -->

<!-- governance-crud:start id=dec-20260717-0002 -->
## dec-20260717-0002: Bound same-GitHub-Actions-App risk pending a distinct trust root

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-17
- Updated: 2026-07-17
- Tags: github,trust-boundary,residual-risk,P3
- Source: Known k-20260717-0004 and official GitHub required workflow/check/App documentation
- Confidence: high

Do not claim that integration_id 15368 authenticates a workflow path. In this public user-owned repository, native required workflows and push path restrictions are unavailable. A strong resolution requires either transfer to a Team organization with required workflows or a separately hosted GitHub App with its private key outside candidate Actions and a required App-bound check. Defer app registration/service creation because it introduces a new high-value credential and operational service beyond the minimal recurrence repair; retain the risk as explicit and do not treat current required checks as cryptographic workflow provenance.
<!-- governance-crud:end id=dec-20260717-0002 -->

<!-- governance-crud:start id=dec-20260801-0001 -->
## dec-20260801-0001: Make the complete original noetic-dev intent the governing non-abeyant telos

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-08-01
- Updated: 2026-08-01
- Tags: P3,P4,founding-intent,noetic-dev,scope,prime-directive
- Source: initial-user-msg.md;AGENTS.md;SYNTHESIS.md;saeproj/docs/foundational;user-directive:2026-08-01
- Confidence: high

The complete original noetic-dev intention is active and governs every chain, roadmap, issue, integration, and success claim. Build one portable development-and-cognitive framework that operationalizes authentic inquiry and responsible action rather than crowning a donor or optimizing one integration. The active scope includes the P1-P4 cognitive form; human responsibility; Telos-mediated durable purpose and multi-agent delegation; a runtime-neutral deterministic executive controller; cognitive programs and the design-intention-to-implementation pipeline; attributed causal events, semantic session memory, summarization and search; observability and attach; portable runtime/model/workspace/effect adapters; governed local generative, vision, embedding and ASR capability; SAE/GEH research with an explicit feedback seam; clean composition, recovery, rollback and real end-to-end proof. Sequencing or non-gating status does not make an original intention abeyant. Every material dimension must map to an active/planned delivery track, accepted decision, conditioning open question, or an explicitly justified true deferral.
<!-- governance-crud:end id=dec-20260801-0001 -->

<!-- governance-crud:start id=dec-20260801-0002 -->
## dec-20260801-0002: Adopt the noetic-dev constitutional form and load-bearing executable spine

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-08-01
- Updated: 2026-08-01
- Tags: P1,P2,P3,P4,cognitive-constitution,telos,controller,events,memory,vertical-slice
- Source: initial-user-msg.md;docs/cognitive-backbone.md;SYNTHESIS.md;saeproj/docs/foundational/transcendental-method-structured.txt;user-directive:2026-08-01
- Confidence: high

P1-P4 remains noetic-dev's canonical recurrent machine-facing v1 form: be attentive, intelligent, reasonable and responsible, recursively governed by responsible deliberation and decision. The underlying semantic operations remain attributed to humans or agents; Telos durably represents and mediates authorized purpose but does not itself become authentic responsibility. The executable spine is: humanly authorized purpose -> Telos goalchain and typed delegation -> deterministic runtime-neutral controller -> versioned cognitive programs and semantic agents -> implementation plus independent QA -> attributed append-only event and semantic-memory evidence -> separate critical judgment and responsible adjudication -> replay, recovery and rollback. Deterministic mechanics never assert semantic truth; emitted cognition reports remain attributed evidence until judged. The first authentic vertical slice must include a minimal cognitive program and event/memory persistence, not only delivery mechanics.
<!-- governance-crud:end id=dec-20260801-0002 -->

<!-- governance-crud:start id=dec-20260801-0003 -->
## dec-20260801-0003: Keep ContextForge and all infrastructure subordinate and replaceable

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-08-01
- Updated: 2026-08-01
- Tags: contextforge,transport,litellm,genus-router,clients,instruments,architecture-boundary
- Source: initial-user-msg.md;AGENTS.md;SYNTHESIS.md;user-directive:2026-08-01
- Confidence: high

ContextForge is optional compatibility/distribution transport, not the noetic-dev backbone, composition root, teleological governor, controller, event authority or success criterion. Plain MCP stdio/HTTP remains the default when sufficient; ContextForge promotion requires a demonstrated multi-host/shared-continuity need and later adjudication. The current 4445 Pi/OpenCode work is a bounded adapter/harness track and cannot by itself prove complete-system success. LiteLLM is the governed universal model-access boundary and genus-router the honest selector, but neither defines cognition or purpose. OpenCode, Pi, Claude, Codex, Goose, VS Code, tmux, browser PTY, GitHub governance and any model server are replaceable adapters or operational means behind explicit contracts.
<!-- governance-crud:end id=dec-20260801-0003 -->

<!-- governance-crud:start id=dec-20260801-0004 -->
## dec-20260801-0004: Keep all original capability tracks live with differentiated sequencing

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-08-01
- Updated: 2026-08-01
- Tags: portfolio,capability-tracks,clients,memory,multimodal,sae,geh,sequencing
- Source: initial-user-msg.md;SYNTHESIS.md;user-directive:2026-08-01
- Confidence: high

Maintain explicit live tracks and success gates for: Telos dispatch and completion semantics; the portable controller and APM invariants; cognitive disciplines/programs; the full development pipeline; cognitional events and read-only-first observability; semantic session embedding, summarization, retention and search; tmux-first attach and optional browser attachment; at least two runtime/client adapters; genus-router and LiteLLM-governed generative, vision, embedding and ASR substrate; donor characterization and selective superior re-instantiation; and SAE/GEH training and evaluation. Core delivery need not wait for long-horizon model research or every optional client, but non-gating work remains represented and measurable rather than silently parked. SAE/GEH empirical claims retain lower confidence and separate evidence from the philosophical/cognitional constitution.
<!-- governance-crud:end id=dec-20260801-0004 -->

<!-- governance-crud:start id=dec-20260801-0005 -->
## dec-20260801-0005: Bound verification and governance by purpose rather than permit recursive capture

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-08-01
- Updated: 2026-08-01
- Tags: qa,governance,stop-loss,emergent-probability,means-end,development-practice
- Source: AGENTS.md;docs/development-practices.md;docs/user/emergent_probability.txt;user-directive:2026-08-01
- Confidence: high

Preserve exact implementation:QA pairing: each frozen implementation or remediation generation receives exactly one independent adversarial QA pass against its accepted acceptance and threat contract. A rejected or transcriptless generation blocks only dependent continuation; it does not block independent portfolio progress. Repeated rejection triggers explicit P3 scope/threat and means-end reassessment instead of automatically expanding hardening obligations. Delivery governance, portfolio audit, publication trust, ContextForge continuity and residue cleanup condition the work but may not indefinitely prevent independent architecture, donor characterization, contract design or authentic runtime development. Prefer stable reusable bases, bounded recyclable experiments and clear completion/parking semantics over perpetual goal generation.
<!-- governance-crud:end id=dec-20260801-0005 -->

<!-- governance-crud:start id=dec-20260801-0006 -->
## dec-20260801-0006: Select concrete first-slice component homes and runtime adapters

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-08-01
- Updated: 2026-08-01
- Tags: P3,P4,architecture,component-homes,runtime,opencode,pi,first-slice
- Source: initial-user-msg.md;SYNTHESIS.md;docs/full-portfolio-capability-map.md;oq-20260801-0001;chain-90/subgoal-1637;local-version-evidence:2026-08-01
- Confidence: high

For the first authentic noetic-dev slice, select these independently versioned homes under `somebloke1`: Telos retains typed dispatch in `telos`; create `noetic-controller` for the deterministic controller and its private state store; create `noetic-programs` for `bounded-change-inquiry/v1` and later `development_pipeline.v1`; create `noetic-evidence` with separately testable `journal` and `memory` packages; create `noetic-opencode-adapter` for the first runtime, scoped workspace effect executor, and model bridge; create `noetic-resources` for versioned skills and semantic-agent packages; and create `noetic-model-substrate` for secret-free LiteLLM/genus/local-model registration and deployment contracts while genus-router itself remains independent. For later complete-system tranches, create `noetic-pi-adapter`, `noetic-observer`, `noetic-attach-tmux`, `noetic-serena-adapter`, and `noetic-mentality`; additional runtime adapters use `noetic-<client>-adapter` homes unless a later evidence-backed decision selects an existing independent repository. The noetic-dev root owns schemas, pins, composition, and integration proof only. Select OpenCode 1.18.9 as the first reference-runtime target because Telos already projects into it and it is the lean headless candidate; select Pi 0.80.3 as the second-adapter target because it is the richest independent donor/runtime. These are reversible adapter choices, not architectural authorities. Every new component repository has no implementation SHA yet: repository initialization is its first explicit implementation generation, and no composition manifest may call it pinned until that generation receives exactly one independent QA and yields an immutable commit SHA. This decision refines and supersedes only the stale component-home, client-selection, and implementation-readiness projections in `dec-20260711-0004`, `dec-20260711-0006`, and `dec-20260711-0007`; it preserves their accepted thin-root, event-derived-observability, and replaceable-adapter boundaries.
<!-- governance-crud:end id=dec-20260801-0006 -->

<!-- governance-crud:start id=dec-20260801-0007 -->
## dec-20260801-0007: Select first-slice persistence and causal-event authority

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-08-01
- Updated: 2026-08-01
- Tags: P3,P4,persistence,events,journal,memory,sqlite,recovery
- Source: docs/full-portfolio-capability-map.md;docs/original-intent-traceability.md;oq-20260801-0003;noetic-pi donor source;chain-90/subgoal-1637
- Confidence: high

Use SQLite 3.45.1-compatible durable stores for the first local slice. `noetic-controller` owns a private `controller.sqlite` command/state store and transactional outbox; it is not the causal-event authority. `noetic-evidence/journal` is the sole canonical event append/replay authority, owns `journal.sqlite`, uses WAL/foreign keys/strict tables, accepts idempotent versioned appends through one writer service, and assigns journal position. Cross-component delivery is at-least-once: Telos and controller outboxes retry stable event IDs, while the journal deduplicates; do not claim cross-service exactly-once or one distributed transaction. Effects use intent/applied/reconciled events plus idempotent postcondition checks so crash recovery can determine and repair indeterminate boundaries. `noetic-evidence/memory` owns separate derived `memory.sqlite` projections keyed to journal event IDs/positions; it is rebuildable and may not mutate source events. The first slice requires restart-safe provenance-linked summary persistence and retrieval; embeddings and broader semantic similarity remain a complete-system expansion. This selection remains conditioned on adversarial crash/concurrency/privacy tests before production effects.
<!-- governance-crud:end id=dec-20260801-0007 -->

<!-- governance-crud:start id=dec-20260801-0008 -->
## dec-20260801-0008: Select bounded local authority and effect contract for the first slice

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-08-01
- Updated: 2026-08-01
- Tags: P3,P4,authority,effects,identity,credentials,first-slice,rollback
- Source: docs/full-portfolio-capability-map.md;docs/original-intent-traceability.md;oq-20260801-0003;issue-65 credential-isolation donor;ContextForge authorization donors
- Confidence: medium

For the first single-host slice, authenticate the human principal at a mode-0700 Unix-domain admission socket using kernel peer credentials and bind the admitted UID, purpose ID, issue/worktree, repository identity, base/tree SHA, one-file path allowlist, effect class, expiry/revocation, cancellation, remediation budget, and rollback digest into a versioned authorization record. This is a bounded local-host authority contract, not remote/public identity proof. The controller mints single-use, run/generation/pass-bound capabilities for restricted actor processes; implementers can propose one patch but cannot QA, approve, publish, access provider/Git/SSH/host credentials, or write outside the declared effect. QA receives a separately identified read-only candidate view and no effect token. Only `noetic-opencode-adapter`'s deterministic effect executor may apply the authorized patch after base/tree, path, symlink, size, expiry, idempotency, and inverse checks. Telos records purpose and separately reconciles/adjudicates results; neither controller success nor an agent recommendation impersonates final human responsibility. Remote/multi-user production authority remains open and does not block this reversible local proof.
<!-- governance-crud:end id=dec-20260801-0008 -->

<!-- governance-crud:start id=dec-20260801-0009 -->
## dec-20260801-0009: Freeze first-slice runtime and donor input pins without inventing absent component SHAs

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-08-01
- Updated: 2026-08-01
- Tags: P3,P4,pins,components,opencode,pi,litellm,sqlite,donors
- Source: local-git-and-runtime-evidence:2026-08-01;docs/full-portfolio-capability-map.md;dec-20260801-0006
- Confidence: high

Use these exact current inputs for first-slice design and conformance work: Telos clean remote-tracking base `a8f6c253bb091562a9982b22217ebc4e78b1aa5b`; noetic-pi donor `683b53b06714d0aadd49c5852140b708c5abba69`; cognitive-disciplines donor `923686521b78a4c0cb2e86a23a6eb5d4f9e0c5e4`; genus-router accepted remote-tracking revision `f2b839b0cfc737c4c1f0a46d3d519d414529545c`; OpenCode 1.18.9 local reference binary SHA-256 `7c4d91c84d2bfdeabb59257e3490c5e5acb08f2aacb3e42f3ddc296a1c3f1aca`; Pi 0.80.3 second-adapter binary SHA-256 `af302f231437eaf6f37691bce4b34234fcb626bcb5eb3910d4fc3f6519bf78ca`; LiteLLM Python package 1.81.10; and SQLite 3.45.1. These are local evidence pins, not live remote/release attestations. The new canonical component homes selected in dec-20260801-0006 are explicitly `absent/unpinned`; never invent a commit SHA or treat a repository name/version intention as an immutable pin. Each initialization issue must create one minimal independently testable repository generation, obtain exactly one QA, and then update the composition manifest with its real full commit SHA and source/release identity before T2/T3 integration. A fresh remote/package provenance check may replace a local evidence pin only through a recorded new decision/generation.
<!-- governance-crud:end id=dec-20260801-0009 -->
