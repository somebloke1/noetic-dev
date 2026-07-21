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
<!-- governance-crud:start id=k-20260717-0001 -->
## k-20260717-0001: Protected dev and ruleset state after issue 51

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-17
- Updated: 2026-07-17
- Tags: protected-route,github,ruleset,P1
- Source: GitHub REST API queried 2026-07-17
- Confidence: high

Observed 2026-07-17: GitHub API reports dev at cfd6a612491a777fc9aad3aa3cd68ca2cb348fe3 and protected=true. Repository ruleset 19122088 is active for refs/heads/dev, has no bypass actors, reports current_user_can_bypass=never, requires pull requests, blocks deletion/non-fast-forward, and requires agent-review plus four governance contexts bound to GitHub Actions integration 15368. Sources: GET /repos/somebloke1/noetic-dev/branches/dev, /rulesets/19122088, and /rules/branches/dev.
<!-- governance-crud:end id=k-20260717-0001 -->

<!-- governance-crud:start id=k-20260717-0002 -->
## k-20260717-0002: Merged Agent Review runs lose embedded PR association

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-17
- Updated: 2026-07-17
- Tags: protected-route,artifact,provenance,P1
- Source: GitHub REST GET actions/runs/29614049806, artifacts, pulls/56
- Confidence: high

Agent Review run 29614049806 remains completed/successful with exact head dafc54c5496cb09dce8dd3bb974d72b2dd2382df, workflow ID 312422987, attempt 1, and retained artifact 8419811231 digest sha256:ede829e6586cad1d4ed708e1c554451dd880435774cf146dc2c2e7d13e4f498c, but its run API now returns pull_requests: []. The stable PR endpoint /pulls/56 still returns exact historical head and base f0a5c02315eb1d1c26849545bc9fa459bdaf4ec0 after merge. The current validator depends on run.pull_requests and therefore cannot durably revalidate this run post-merge.
<!-- governance-crud:end id=k-20260717-0002 -->

<!-- governance-crud:start id=k-20260717-0003 -->
## k-20260717-0003: Production review broker and router remain active

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-17
- Updated: 2026-07-17
- Tags: protected-route,runtime,genus-router,P1
- Source: systemctl show/status/cat, readlink, stat, pip check, genus-router --check-config
- Confidence: high

System systemd units noetic-dev-agent-review-broker.service and noetic-dev-actions-runner.service were active/running with NRestarts=0 on 2026-07-17. /opt/noetic-dev-agent-review/current resolves to release ddda78670fc564f19b7bab3e02e06cb2b71387c9. Broker command pins genus-router component f2b839b0cfc737c4c1f0a46d3d519d414529545c; its manifest is root-owned/read-only, pip check passed, and genus-router --check-config reported ok with local-litellm and 20 genera.
<!-- governance-crud:end id=k-20260717-0003 -->

<!-- governance-crud:start id=k-20260717-0004 -->
## k-20260717-0004: Personal repository lacks a native distinct workflow trust root

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-17
- Updated: 2026-07-17
- Tags: github,trust-boundary,check-source,P1
- Source: Official GitHub documentation and live API research 2026-07-17
- Confidence: high

GitHub Actions App integration 15368 identifies all repository Actions workflows, so integration-bound context names do not distinguish the protected workflow from a candidate-created same-name workflow. Native required-workflow rules are organization/enterprise controls and are unavailable for this user-owned public repository; public personal repositories also cannot use push file-path restrictions. Strong available alternatives are transfer to a Team organization or a separately credentialed GitHub App hosted outside candidate Actions. Sources: official GitHub ruleset/required-workflow/GitHub App docs and live repository API behavior.
<!-- governance-crud:end id=k-20260717-0004 -->

<!-- governance-crud:start id=k-20260718-0001 -->
## k-20260718-0001: Superseded D2 portfolio and branch-protection snapshot

- Ledger: knowns
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-18
- Updated: 2026-07-20
- Tags: D2,github,portfolio,branch-protection,P1
- Source: GitHub REST/GraphQL reads and local Git inspection captured at 2026-07-18T23:20:48Z
- Confidence: high

This historical snapshot was superseded after PR #67 opened and protected `dev` advanced. Its 12-PR count and branch SHAs must not be used as current portfolio evidence. The branch-protection observations remain historical inputs, not a current inventory receipt.
<!-- governance-crud:end id=k-20260718-0001 -->

<!-- governance-crud:start id=k-20260719-0001 -->
## k-20260719-0001: Candidate-authenticated D2 portfolio capture awaits protected receipt

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-19
- Updated: 2026-07-21
- Tags: D2,github,portfolio,P1,receipt-pending
- Source: Authenticated GitHub GraphQL response envelopes captured by `scripts/governance/capture_d2_inventory.py` and stored in `governance/audits/20260718-d2-portfolio/inventory.json`
- Confidence: high for the candidate capture and its declared non-authority; independently protected verification remains pending

The candidate-authenticated response bodies captured at `2026-07-21T15:40:44.332775+00:00` derive 2 open pull requests, 11 branch refs, and 5 open issues for repository ID `1297462728` (`somebloke1/noetic-dev`), with `main@29196a67349537d6f8a8a711df11b86da0430857` and `dev@1195c88f6160e4e15f430fd3f67fcb5eda19f559`. Each compressed response is bound by raw-body, canonical-response, and envelope digests plus request identity, pagination, and capture chronology. The artifact explicitly records `pending_protected_receipt`; it does not complete the D2 audit or independently authorize the bounded repair.
<!-- governance-crud:end id=k-20260719-0001 -->
