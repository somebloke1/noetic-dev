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
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-08-02
- Tags: backbone,synthesis,recommendation,telos,smc
- Superseded by: dec-20260802-0001
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
- Updated: 2026-08-02
- Tags: notation,canonical,form,p1-p4,ecn,recommendation,awaiting-ratification
- Superseded by: dec-20260802-0001
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
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: litellm,genus-router,model-access,model-selection,substrate,recommendation
- Confidence: 0.82

User question (2026-07-11): whether to consolidate model access to LiteLLM (substantial work already invested; single body to maintain). Verified from genus-router/config/router.yaml + genus_models.csv. Confidence 0.82.

TWO DIFFERENT LAYERS (do not conflate):
- Model ACCESS/normalization = LiteLLM's job: provider auth, keys, rate limits, retries, OpenAI-compatible normalization across heterogeneous providers. ONE maintenance body.
- Model SELECTION = genus-router's job: task-shape -> genus -> ranked candidate models + fallbacks; deterministic; task text non-authoritative. genus-router does NOT access models; it returns a model reference.
They are complementary and sit at different layers, not competitors.

VERIFIED CURRENT STATE: genus-router already routes ALL 13 registered models (codex/gpt-5.x, glm-5/turbo/4.7, deepseek-v4, minimax-m3, qwen3.6-a3b, snowflake-arctic-embed2, local-embedder) through a SINGLE endpoint `local-litellm` (openai-compatible, base_url http://172.22.10.160:3333). So the user has DE FACTO already consolidated access to LiteLLM; the schema still models endpoints as plural (interface_type/base_url/token_env/availability per endpoint).

RECOMMENDATION: YES - ratify LiteLLM as the primary model-ACCESS/normalization body for chat/completion models. It is real work already done, gives one OpenAI-compatible surface, and matches the current config. BUT preserve genus-router's stated principle: 'LiteLLM is one registered endpoint, not the architectural boundary.' Keep the endpoint-pluralism abstraction so you can register a direct llama.cpp/ollama endpoint if/when LiteLLM adds latency, becomes a single point of failure, or is suboptimal for a given interface.

NUANCE - local inference + non-chat interfaces: embeddings (snowflake-arctic-embed2) and ASR (Qwen3-ASR) are latency/throughput-sensitive and may be better DIRECT than proxied through LiteLLM. Recommend: route chat/completion through LiteLLM by default; make embeddings/ASR a measured config choice via the same endpoint abstraction (direct vs proxied), not a hard commitment. LiteLLM being up must not be a hard precondition for local embedding/ASR unless you accept that coupling.

NET: consolidate ACCESS to LiteLLM (single body, already done), keep SELECTION in genus-router, and keep the escape hatch open. This is consistent with genus-router's design and adds one maintenance surface, not a new architectural boundary.
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
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-08-02
- Tags: orchestration,apm,executive-plane,deterministic,telos,layering,harvest,correction
- Superseded by: dec-20260802-0001
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

<!-- governance-crud:start id=dec-20260802-0001 -->
## dec-20260802-0001: Ratify P1-P4 as the canonical form under human authority

- Ledger: decisions
- Status: accepted
- Repository: somebloke1/noetic-dev
- Created: 2026-08-02
- Updated: 2026-08-02
- Tags: constitution,P1-P4,human-authority,telos,cognition
- Source: Explicit user P4 ratification on 2026-08-02; founding charge; verified current foundational sources under `saeproj/docs/foundational/`
- Confidence: high

Ratify `R(P1 -> P2 -> P3 -> P4 -> R)` as noetic-dev's canonical cognitive form, with the fixed human gloss `P1 be attentive`, `P2 be intelligent`, `P3 be reasonable`, and `P4 be responsible`. ECN `^?` and `^!` remain optional sought/enacted modality annotations rather than a competing notation.

P1-P4 names recurrent authentic operations, not deterministic states, agent roles, software layers, or components. No component maps one-to-one to a P-level. Structural validation may establish form, attribution, and transition legality, but it cannot establish insight, judgment, responsibility, consciousness, or self-affirmation.

Human responsibility is irreducible at the framework governance boundary. Agents may produce attributed evidence, insights, judgments, and recommendations; they must not be personified as the responsible subject. Telos durably mediates humanly authorized purpose and continuation, but Telos is not P4 and does not replace human responsibility. The deterministic controller governs legal execution mechanics without becoming cognition or semantic authority.

This decision ratifies only the constitutional form and authority boundary. It does not claim that current M0/M1 fixtures, protected delivery governance, Telos continuation, or any runtime/component implements authentic P1-P4 cognition. Runtime, model, persistence, component, and trajectory claims require separate bounded decisions and evidence.

This decision supersedes `dec-20260711-0002`, `dec-20260711-0003`, and `dec-20260711-0008` as governing decisions. Their source observations and donor lessons remain historical evidence, but their direct equations of Telos, agents, roles, artifacts, or software layers with P-levels are not authoritative. Controller, program, and component topology will be re-adjudicated separately from this constitutional act.

Current foundational source locations were verified under `saeproj/docs/foundational/`; this observation does not rewrite the frozen historical wording or paths in `initial-user-msg.md`.
<!-- governance-crud:end id=dec-20260802-0001 -->
