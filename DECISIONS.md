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
## dec-20260711-0002: noetic-dev backbone: P1-P4 form, Telos teleology, superior executive controller, observable cognitive programs

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis-worktrees/issue-1-architecture
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: noetic-dev,backbone,p1-p4,telos,controller,observability,substrate,current
- Confidence: 0.95

Current adjudicated architecture, refined through dec-20260711-0008/0010/0011. FORM: canonical P1-P4 cognitive grammar, user-ratified. TELEOLOGICAL GOVERNANCE: Telos carries durable purpose, goalchains, principles, and evolution. EXECUTIVE GOVERNANCE: noetic-dev abstracts the deterministic invariants, state transitions, typed dependency semantics, QA/remediation loops, commit/verification boundaries, event vocabulary, conformance evidence, and failure lessons from the noetic-pi/pi2 APM lineage, then re-instantiates a cleaner portable controller superior to the donor implementation. PROGRAMS: cognitive disciplines and development pipelines run on the controller while semantic judgment remains with agents. OBSERVABILITY/CONTROL: structured cognitional events feed web/TUI renderers with tmux/browser attach adapters swappable. MODEL SUBSTRATE: genus-router selection over LiteLLM-normalized access and measured direct local endpoints. TRANSPORT: ContextForge is retained and maintained where current tools depend on it but is not the architecture's organizing backbone. TARGET: this private noetic-dev repository is the thin composition root; independently testable components remain separately versioned. The earlier lift-as-is and ContextForge-decommission implications are explicitly superseded.
<!-- governance-crud:end id=dec-20260711-0002 -->

<!-- governance-crud:start id=dec-20260711-0003 -->
## dec-20260711-0003: Canonical notation ratified: P1-P4 + imperative gloss + optional ECN modal markers

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis-worktrees/issue-1-architecture
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: notation,canonical,form,p1-p4,ecn,ratified
- Confidence: 1.0

RATIFIED by the user on 2026-07-11. P1-P4 is the canonical machine/structure-facing notation for noetic-dev. Reasons: noetic-pi already uses p1-p4 functional roles and cognitive-disciplines is built as a P1-P4 cycle; it is language-neutral, identifier-safe, ordered, and composable. Pair it with the fixed human gloss P1 be attentive / P2 be intelligent / P3 be reasonable / P4 be responsible. Retain ECN's additive ^! (assertoric/enacted) and ^? (interrogative/sought) markers only as optional modality annotation, not as a rival primary notation. `docs/cognitive-backbone.md` is the canonical reference.
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
- Status: accepted
- Repository: /home/dgk/workspace/synthesis-worktrees/issue-1-architecture
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: orchestration,apm,executive-plane,deterministic,telos,layering,harvest,refined
- Confidence: 1.0

Prompted by the user's verified correction that APM was not an optional sidekick but a deterministic pipeline state machine (k-20260711-0007). noetic-dev has two distinct governance planes: (1) Telos provides teleological governance—why, purpose, goalchains, evolution; (2) the executive controller provides deterministic orchestration governance—how and when, including work decomposition, dependency legality, wave/graph scheduling, QA/remediation gates, spawn/retire, verification, and commit boundaries. Cognitive disciplines and development pipelines are programs running on this executive plane, not peer utilities beside it. The controller must keep deterministic harness mechanics separate from non-deterministic agent semantic judgment. The APM is the most valuable donor, but the provisional lift-as-is approach is superseded by dec-20260711-0011: abstract its invariants, contracts, conformance evidence, and failure lessons, then re-instantiate a cleaner portable controller superior to the donor implementation.
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

<!-- governance-crud:start id=dec-20260711-0010 -->
## dec-20260711-0010: ContextForge is demoted architecturally but retained operationally; do not decommission it

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: contextforge,transport,dependency,retain,correction
- Confidence: 1.0

User correction, 2026-07-11. ContextForge is not the noetic-dev integration backbone, but several tools currently used by this environment depend on ContextForge. Therefore: (1) retain and maintain the existing ContextForge service and tool paths; (2) treat it as an operational transport/aggregation dependency where actually used; (3) do not remove, stop, or migrate it merely because it is demoted in the target architecture; (4) any future decommission proposal requires a verified dependency inventory, replacement paths, parity tests, staged migration, and rollback. Architectural demotion means 'not the organizing principle', not 'unnecessary'.
<!-- governance-crud:end id=dec-20260711-0010 -->

<!-- governance-crud:start id=dec-20260711-0011 -->
## dec-20260711-0011: Re-instantiate the APM lessons as a superior portable controller; do not lift the donor as-is

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/synthesis-worktrees/issue-1-architecture
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: controller,apm,abstraction,reinstantiation,superior-design,supersedes-part
- Confidence: 1.0

Final user decision, 2026-07-11, refining dec-20260711-0008. The noetic-pi/pi2 APM is the most valuable donor, but the target is not its current implementation behind an MCP facade. noetic-dev must first abstract the donor's deterministic invariants, state transitions, typed dependency semantics, QA/remediation loops, commit/verification boundaries, observability vocabulary, and accumulated failure lessons; then re-instantiate them in a cleaner, portable controller superior to the donor form. Preserve behavior through extracted conformance fixtures and adversarial tests, not through structural copying. Maintain the deterministic-controller / non-deterministic-agent separation. This supersedes only dec-0008's provisional 'harvest as-is first' recommendation; its elevation of executive governance remains accepted.
<!-- governance-crud:end id=dec-20260711-0011 -->
