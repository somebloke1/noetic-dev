# Knowns

<!-- governance-crud:start id=k-20260711-0001 -->
## k-20260711-0001: Project landscape: maturity, recency, and layer roles (verified)

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: landscape,maturity,layers
- Confidence: 0.85

Verified from source files/AGENTS.md/PROJECT.md/git logs on 2026-07-11:

MATURITY + RECENCY:
- noetic-pi: MOST MATURE. 2,069 passing tests (apm 1071 / server 392 / web 499 / shared 38 / codegraph 29 / session-search 40). Self-developing web terminal for pi agents. APM state machine, agent mesh, ordinal identity, live succession, cognitive disciplines (phronesis, EP audit, differentiated-cognition), APM planner pipeline (design_intentions->design->implementation_procedure->implementation, QA/remediation cycles), implementation executor w/ variant-worktree orchestration, session search on LOCAL inference (Qwen summ + Snowflake Arctic embed). Last commit 2026-05-01.
- noetic-pi-docker: containerized deploy basis of noetic-pi (product vs dev-basis split). Active 2026-07-02.
- telos: runtime-pure goalchain (core pure + pi/oc adapters + toolbridge). Goalchains/subgoals/reproductive-clause; 16 canonical tool names; runs in Pi AND OpenCode. 47 test files. Active 2026-07-08. Runs THIS chain.
- genus-router: deterministic MCP model-selection router; config-driven; local LiteLLM as one endpoint. MOST RECENT activity 2026-07-10.
- saeproj: cognitive-model training (SMC/GEH; make operational geometry explicit). Active 2026-06-28.
- cognitive-disciplines: Codex plugin extraction of P1-P4 cycle from noetic curriculum. Active 2026-06-22.
- cf-controlplane/contextforge: MCP gateway aggregation; user calls it messy/not-fruitful. Active 2026-06-25.
- cognitional_notation (ECN grammar): STALE 2026-02; early formalization superseded by living use elsewhere.

LAYER ROLES (stratification, not competition):
- Cognitive theory/notation: saeproj SMC + ECN/P1-P4.
- Model substrate: saeproj training + genus-router selection + local 2x3090 inference.
- Agent operational engine: noetic-pi (APM/mesh/pipelines) - already integrates most disciplines.
- Purpose/evolution: telos goalchains.
- MCP transport/distribution: contextforge (weakest link).
<!-- governance-crud:end id=k-20260711-0001 -->

<!-- governance-crud:start id=k-20260711-0002 -->
## k-20260711-0002: noetic-pi is powerful but not portable; telos+genus-router is the emerging portable axis

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: portability,noetic-pi,telos,genus-router,decisive
- Confidence: 0.8

Verified 2026-07-11 from noetic-pi/PROJECT.md, noetic-pi/OPEN_QUESTIONS.json, genus-router/README.md, noetic-pi-docker/ROOT_PROMPT.md:

NOETIC-PI PORTABILITY IS UNRESOLVED:
- PROJECT.md line 62: 'control-plane extraction remain deferred'.
- 'public-export' extraction saga running since ~2026-04-30 is STUCK: no variant selected/merged/publication-ready; working tree intentionally dirty; selection explicitly separated from merge and publication readiness.
- 'pnpm -r build' blocked by pi-mono toolchain boundary (tsgo not found); noetic-pi is deeply coupled to pi-mono (the Pi coding-agent monorepo) and 'pi-mono must not be modified'.
- Conclusion: noetic-pi is a powerful but ENTANGLED INSTANCE, not a cleanly extractable/reusable backbone. Its proven MECHANISMS are the asset; its packaging is locked.

TELOS+GENUS-ROUTER IS THE EMERGING PORTABLE AXIS:
- genus-router/README: 'It is designed for the telos project first' - telos is its primary declared consumer. genus-router is the user's MOST RECENT active work (2026-07-10).
- telos is runtime-pure core + Pi AND OpenCode adapters + MCP tools; provider-agnostic; portable.
- noetic-pi-docker is the 'forward working instance' of noetic-pi (a product instance), not an extraction of a reusable core.
- Revealed preference: the user's recent center of gravity = telos + genus-router + MCP (portable), not noetic-pi (locked instance).
<!-- governance-crud:end id=k-20260711-0002 -->

<!-- governance-crud:start id=k-20260711-0003 -->
## k-20260711-0003: noetic-pi's APM disciplines + pipeline are cleanly extractable (harvest-not-host verified)

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: extractability,harvest,noetic-pi,apm,verified,decisive
- Confidence: 0.85

Verified 2026-07-11 from noetic-pi/packages/apm/package.json, packages/shared/package.json, grep of packages/apm/src and .pi/extensions:

- packages/apm (carries phronesis, ep-audit, implement/pipeline, lifecycle, condition-evaluator) depends on ONLY: @noetic-pi/shared (workspace types), better-sqlite3, node-pty. No pi-mono, no pi SDK.
- The ONLY pi-mono reference in packages/apm/src is a COMMENT in test-gate.ts documenting that pi-mono is EXCLUDED from the noetic-pi toolchain - it records decoupling, not a dependency.
- @noetic-pi/shared depends only on @sinclair/typebox + ajv (schema libs); not pi-coupled.
- Disciplines communicate over net.* TCP sockets (apm-channel IPC) and browser via SSE - already architecturally decoupled from the pi agent runtime.

IMPLICATION: The pi-mono coupling that blocks noetic-pi's build/export lives at the WEB-TERMINAL/APP layer (hosting pi agents in PTYs), NOT in the discipline/pipeline logic. Therefore 'harvest noetic-pi mechanisms as portable MCP organs' is FEASIBLE, not merely aspirational: the valuable logic (+ its ~1,100 apm tests) already sits behind a clean dependency boundary and an IPC seam. Re-exposing it as an MCP service telos can drive is modest integration work, not a rewrite.

This hardens DECISIONS.md dec-20260711-0002.
<!-- governance-crud:end id=k-20260711-0003 -->

<!-- governance-crud:start id=k-20260711-0004 -->
## k-20260711-0004: Telos is a STEERING spine, not a SPAWNING spine; 'drive organs' needs the host agent or an unbuilt dispatcher

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: telos,spine,delegation,agency,drive,verified,decisive
- Confidence: 0.85

Verified 2026-07-11 from telos/packages/core/src (continuation.ts, model.ts, schema.ts, goal-chain-manager.ts) and packages/pi-runtime/src (goal-continuation.ts, goal-manager.ts, goalchain-*):

TELOS'S ACTUAL AGENCY MODEL:
- Drive mechanism = STEERING, not spawning. pi-runtime GoalContinuation re-injects the host agent loop on idle (Codex-style continuation steering; 2s..15s intervals). core/continuation.ts is a PURE decision function: given chain snapshots it decides shouldContinue + nextSubGoal and emits a continuation MESSAGE. This is exactly what steers THIS agent via CONTINUATION prompts.
- Telos governs the agent it is EMBEDDED IN. It does not itself spawn/dispatch sub-agents to do work.

DELEGATION IS SCHEMA + GUARD, NOT ENACTMENT:
- delegations + delegation_events tables and a 'delegated-pending' sub-goal status exist (first-class data model).
- But 'delegate_context' is only a BOOLEAN GUARD flag: in delegated contexts, mutating goalchain verbs refuse. There is NO delegation dispatcher/manager method that creates a delegation and spawns a worker.
- Confirms the user's own words: 'intent to make it multi-agent in some respect' = nascent/aspirational, not built.

OUTBOUND CAPABILITY IS MINIMAL:
- Only outbound calls: fetch() to a distiller LLM endpoint (compaction/summarization; currently DISABLED per goalchain_capabilities) and child_process spawn of an EDITOR for /goal edit. NO general MCP-client / tool-calling / agent-dispatch capability today.

IMPLICATION (refines dec-20260711-0002): 'Telos spine drives noetic-pi organs over MCP' is NOT literally true of Telos-as-it-exists. Correct statement: Telos is the TELEOLOGICAL GOVERNOR (P4) that steers a HOST AGENT; the host agent (or a to-be-built delegation dispatcher) is what ENACTS calls to MCP organs (P1-P3). The architecture is sound and even more faithful to 'P4 governs recursively' - but the synthesis requires building ONE new seam: delegation/dispatch enactment (which is exactly the user's stated 'make it multi-agent' intent). This is the single genuinely-new build the synthesis needs; everything else is harvest/integration.
<!-- governance-crud:end id=k-20260711-0004 -->

<!-- governance-crud:start id=k-20260711-0005 -->
## k-20260711-0005: noetic-pi's web observability is event/archive-driven and structurally separable from PTY-terminal embedding

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: web,observability,noetic-pi,terminal,separability,client,verified
- Confidence: 0.82

Verified 2026-07-11 from noetic-pi/packages/web/src:

- The web package already SPLITS two concerns into different modules:
  - terminal.ts (+ terminal.test.ts) = xterm.js PTY-terminal embedding over WebSocket. This is the specific mechanism the user is UNCERTAIN about.
  - observability.ts + observability-inquiry-panels.ts + observability-view-model.ts = four first-class inquiry tabs (planning, implementation, differentiated-cognition, emergent-probability) that consume STRUCTURED HTTP endpoints (/observability/inquiry/<id>/archive?type=...) and archives - NOT PTY byte streams.
  - sidebar-*-section.ts = census / agent-tree / backends / implementation / notification-feed sections driven by APM census + SSE events (census:changed etc.), also not PTY.
- main-observability-coordinator.ts is a distinct coordinator from the terminal/agent-presence coordinators.

IMPLICATION: The user's intuition is correct and already latent in the codebase. The VALUE they like (observability of agent-population + discipline + pipeline state) is carried by event/archive-driven panels that are architecturally independent of the terminal-embedding mechanism they are uncertain about. Therefore the web interface can be preserved and elevated as a portable OBSERVABILITY + CONTROL PLANE that consumes structured cognitional events from the spine (telos) and organs (harvested APM), while the PTY-terminal multiplexer is demoted to an optional 'attach a terminal' view rather than the core abstraction. This decouples the web-interface value from any single client and makes the client choice reversible.
<!-- governance-crud:end id=k-20260711-0005 -->

<!-- governance-crud:start id=k-20260711-0006 -->
## k-20260711-0006: pi2 is a tmux-native sibling of noetic-pi: same disciplines family, terminal-native multi-paning instead of browser/PTY

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: pi2,tmux,interface,multi-paning,noetic-pi,phaf,verified
- Confidence: 0.8

Verified 2026-07-11 from ~/workspace/pi2 (PROJECT.md, .method/succession/protocol.md, .pi/extensions/agent-mesh.ts + succession.ts):

- pi2 is a Pi-based agent framework in the SAME conceptual family as noetic-pi: APM, phronesis (renamed PHAF = Phronesis Agent Framework, D011), EP audit (PHAF Developmental Self-Audit, D012), succession, agent-mesh. 435+ tests referenced; last active ~2026-03-13 (older than noetic-pi).
- KEY DIFFERENCE - interface/multi-paning: pi2 makes live agents visible via a PROJECT-SCOPED TMUX SERVER, not a browser. agent-mesh.ts manages a dedicated tmux socket (tmux.sock) + session ('mesh') + .pi/tmux.conf; APM spawns each new agent into a new tmux PANE; succession spawns the successor in an adjacent tmux pane; agents carry TMUX_PANE ids. This is terminal-native multi-agent visibility.
- Constraint noted in pi2 itself: tmux command-length limit (~16KB) forced a minimal-bootstrap spawn pattern (spawn sends ~130-byte identity + role_ack, full curriculum delivered via APM response). Real operational lesson about tmux as a spawn transport.

IMPLICATION for the interface design space (refines dec-0004): the user has TWO working expressions of the same agent-population+disciplines idea with DIFFERENT attach/visibility mechanisms:
  (1) noetic-pi: browser observability plane (event-driven) + browser PTY multiplexer (terminal-in-browser).
  (2) pi2: tmux-native multi-paning (terminal-native, minimalist, no browser).
These are ATTACH/VISIBILITY mechanisms, separable from the durable observability-plane value. tmux multi-paning is the minimalist terminal-native option; browser-PTY is the heavier option. Both sit UNDER the (client-agnostic) observability+control plane, not in competition with it.
<!-- governance-crud:end id=k-20260711-0006 -->

<!-- governance-crud:start id=k-20260711-0007 -->
## k-20260711-0007: APM orchestration-ordering model: deterministic wave-sequenced state machine with typed dependency roles

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: apm,orchestration,ordering,waves,dependency-roles,state-machine,deterministic,verified
- Confidence: 0.83

Verified 2026-07-11 from noetic-pi/packages/shared/src/apm-protocol/implementation.ts + packages/apm/src/implement.ts + implementer/*.ts:\n\nORDERING PRIMITIVES (how multi-agent orchestration is ordered):\n- WORK UNITS (WU) grouped into numbered WAVES (wave_number). Waves are SEQUENCED: a wave runs -> QA -> commit boundary (commit_hash per wave) -> advance to next wave. Wave N completes+commits before N+1.\n- TYPED DEPENDENCY ROLES per WU express ordering legality (not free-form): launch_required (branch-materialized inputs that gate launch), governing_context_refs (authority/contextual references), future_dependencies (produced by later execution - must NOT be required at launch), contextual_refs. Runtime tracks counts of each. This is the DAG/ordering contract; noetic-pi's 'dependency-ontology seam' + 'planner-procedure-total-compliance' campaigns were precisely hardening these so launch/continuity legality holds.\n- QA GATE per wave with remediation cycling (qa_pass, remediation_pass, qaIterations 0-3) and escalation on exhaustion.\n- ORDINAL delegation-tree identity places agents structurally.\n\nDETERMINISTIC / NON-DETERMINISTIC SPLIT (the crux the user flagged): APM does the DETERMINISTIC part - wave sequencing, dependency-role legality checks, spawn/retire, QA gating, commit boundaries (selective staging from WU outputs[]), model selection. AGENTS do the NON-DETERMINISTIC part - implementation, evaluation, escalation (the P1-P4 cognitive work). This matches cognitive-disciplines' own principle: keep deterministic harness mechanics separate from language-model cognitive judgment.\n\nCHARACTERIZATION: ordering is 'sequenced waves + typed dependency-role legality', not an arbitrary DAG scheduler. It is a deterministic executive STATE MACHINE. The user's correction is verified: APM is not an optional sidekick to the disciplines/pipeline tools - the disciplines and the design->implementation pipeline RUN ON it; it is the executive control plane.
<!-- governance-crud:end id=k-20260711-0007 -->

<!-- governance-crud:start id=k-20260713-0008 -->
## k-20260713-0008: Genus-router policy implementation and live modality readiness

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis-worktrees/issue-29-model-routing-policy
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: genus-router,litellm,model-policy,qa,asr,readiness
- Source: genus-router a2d06bb; make check; MCP smoke; QA decision d-20260713-000003; authenticated /v1/models probe
- Confidence: 0.98

Verified 2026-07-13 against genus-router commit a2d06bb, command output, exact config, and one independent routed Fable QA pass. The commit restricts the active registry to Sol, Fable, Terra, Luna, Snowflake Arctic Embed2, and Qwen3-ASR behind sole endpoint local-litellm; `make check` passed 46 tests plus Ruff, mypy, and config validation; MCP smoke succeeded against the live LiteLLM endpoint. QA decision d-20260713-000003 found no core routing or endpoint-boundary code defect and identified one low-severity config defense gap, now pending repair. A fresh authenticated `/v1/models` probe listed Sol, Fable, Terra, Luna, and Snowflake but did not list qwen3-asr. The ASR route therefore fails closed with `NoCandidatesError` under verified availability; this is a deployment-readiness blocker, not silent fallback.
<!-- governance-crud:end id=k-20260713-0008 -->

<!-- governance-crud:start id=k-20260713-0009 -->
## k-20260713-0009: Goalchain semantic curator still bypasses LiteLLM

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis-worktrees/issue-29-model-routing-policy
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: goalchain,opencode,embedding,ollama,litellm,migration,violation
- Source: compact_goal_chain chain-49 output and resolved ~/.config/opencode/opencode.json, 2026-07-13
- Confidence: 1.0

Verified during `compact_goal_chain` on 2026-07-13 and against the resolved OpenCode configuration: the active goalchain curator is enabled with provider `ollama`, host `http://127.0.0.1:11434`, and model `snowflake-arctic-embed2:latest`. The compaction result explicitly reported `Curator: ollama/snowflake-arctic-embed2:latest`. This is a live clause-v7 violation: embedding modality is correct, but access bypasses LiteLLM. Semantic goalchain compaction/ranking must not be invoked again until the curator adapter is migrated to LiteLLM; the noetic-dev harness scope must explicitly include goalchain curation.
<!-- governance-crud:end id=k-20260713-0009 -->

<!-- governance-crud:start id=k-20260714-0001 -->
## k-20260714-0001: Exact-head local broker review executed through Terra

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis-worktrees/issue-29-routed-pi-recovery
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: issue-29,pr-31,agent-review,genus-router,litellm,terra
- Source: https://github.com/somebloke1/noetic-dev/pull/31#issuecomment-4967702974
- Confidence: high

An unprotected local invocation of the PR #31 broker at head 6e381b76289651dd4945563f04ffe7894224c6cf and base 33e8bbd2c483dab0abbb85cb5b00079e4a01b8dc routed through genus-router to codex/gpt-5.6-terra at high reasoning. It produced diff digest a0daf88338256905477085f593b888caebffe89efc252719e5f6251a6636125e, prompt digest c1ea102d3a38742a07cd5bad3a22ea0e38b2075b919763b028043bf51188e320, and changes-needed with one P1 finding about READY-probe outcome semantics. The local result SHA-256 is 084cb1289f31c5e9741fc7e2f5431935641226d71fa2a368d7bb1a4e71af276d; its verified evidence and finding are durably recorded in PR #31 comment 4967702974.
<!-- governance-crud:end id=k-20260714-0001 -->

<!-- governance-crud:start id=k-20260714-0002 -->
## k-20260714-0002: Exact-head review exposed broker and Pi contract scope conflict

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis-worktrees/issue-29-routed-pi-recovery
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: issue-29,pr-31,agent-review,pi,contract-scope
- Source: https://github.com/somebloke1/noetic-dev/pull/31#issuecomment-4968172876
- Confidence: high

An unprotected local PR #31 review at head 1033d24465a8b2a77cdfd5277c5e40e7f571faf8 routed through genus-router to Terra/high and returned changes-needed. Its sole finding is verified against source: the new top-level attempt_contract says one READY phase plus one substantive invocation share a decision, while protected Pi QA intentionally uses separately routed READY and execution operations and the delivery gate rejects shared decision IDs. The result is durable in PR comment 4968172876; result SHA-256 436bdc2513d404eed70e6f09b5df50b85ae36678db8b3da7e68487e2eb6b9a97.
<!-- governance-crud:end id=k-20260714-0002 -->

<!-- governance-crud:start id=k-20260714-0003 -->
## k-20260714-0003: Independent QA found the Pi contract was policy-shaped only

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis-worktrees/issue-29-routed-pi-recovery
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: issue-29,pr-31,qa,pi,runtime-contract
- Source: https://github.com/somebloke1/noetic-dev/pull/31#issuecomment-4968538611
- Confidence: high

Exactly one model-invoking independent QA lifecycle reviewed immutable candidate 09dbe5ef27e14b54d4085b87981c2f27ae5269a7 through protected Pi and Terra/high. It returned changes-needed because authoritative_qa_pi was asserted as policy shape but not consumed by the protected Pi runtime, and the added tests would not reject a duplicate model invocation under one claimed decision. Probe decision d-20260714-000024 and execution decision d-20260714-000025 both completed and reported success; the protected probe and execution record SHA-256 values are 0779ee4adf13cdf54eecd0efd979ae2128ac72184755dfab4507296e53700733 and 02888b51a0e07cbab3823622994adbdf0517486af340d82adcbd5b04bb758adf.
<!-- governance-crud:end id=k-20260714-0003 -->
