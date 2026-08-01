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

<!-- governance-crud:start id=k-20260713-0001 -->
## k-20260713-0001: Live noetic-dev runner and broker services are online under system scope

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: P1,github,runner,systemd,issue-29
- Source: GitHub REST repos/somebloke1/noetic-dev/actions/runners; systemctl system/user status 2026-07-13
- Confidence: high

Read-only verification on 2026-07-13 found GitHub runner noetic-dev-local-01 online and idle at version 2.335.1 with self-hosted/Linux/X64/noetic-dev/terra-review labels. System units noetic-dev-actions-runner.service and noetic-dev-agent-review-broker.service are active; superseded user units are disabled/inactive. The system runner handled three agent-review jobs, all failed. This verifies substrate availability, not semantic-review correctness.
<!-- governance-crud:end id=k-20260713-0001 -->

<!-- governance-crud:start id=k-20260713-0002 -->
## k-20260713-0002: Live dev and main protections require different check contracts

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: P1,github,branch-protection,dev,main
- Source: GitHub REST branch protection for somebloke1/noetic-dev branches dev and main
- Confidence: high

On 2026-07-13 dev required strict GitHub-Actions-bound checks Repository validation (candidate), Workflow pinning validation (candidate), and Genuine tests (candidate), zero approvals, admin enforcement, linear history, and conversation resolution. Main required strict GitHub-Actions-bound validate plus one approval with the same admin/linear/conversation protections. dev did not yet require agent-review.
<!-- governance-crud:end id=k-20260713-0002 -->

<!-- governance-crud:start id=k-20260713-0003 -->
## k-20260713-0003: Default-branch pull_request_target can trigger for main but current policy checkout may block bootstrap

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: P1,github,pull_request_target,bootstrap,promotion,corrected
- Source: GitHub repository contents/default-branch APIs; https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target
- Confidence: high

Correction: main is 2 commits behind dev, and dev is the repository default branch. GitHub documents that pull_request_target loads its workflow from the repository default branch, not the PR merge commit; dev's active agent-review workflow includes target branches main and dev, so it can trigger for a PR targeting main. However, that workflow explicitly checks out github.event.pull_request.base.sha and executes policy/scripts/governance/request_agent_review.py from that checkout. GitHub returned Not Found for that client on main. Therefore the current workflow can trigger for a main-targeting PR but cannot execute its request client from the protected main base SHA.
<!-- governance-crud:end id=k-20260713-0003 -->

<!-- governance-crud:start id=k-20260713-0004 -->
## k-20260713-0004: Existing-work audit surface contains ten original PRs, one orphan branch, and later PR 28

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: P1,audit,freeze,pull-requests,branches,issue-29
- Source: GitHub pull/branch/check/files APIs; exact candidate files; governance/audits/existing-work-freeze.json
- Confidence: high

Read-only GitHub inventory on 2026-07-13 found eleven open PRs. The original freeze cohort is PRs #2, #4, and #15-#22, with exact heads 6c8de72, 54b3e83, 5be6cf0, 250f9b4, c6040ce, d424533, 7ba81b1, 7e6a0e6, 69704c8, and feebb06. Branch issue-11-cognitive-programs at e25083c exists without a PR and is stacked after feebb06. PR #28 at 161b262 is later canary work based on dev and is not part of the original ten-PR count. The freeze artifact still says known_open_pr_count=10 and has no completed audit directory. Historical candidate checks are legacy validate and/or Copilot checks, not current routed protected review evidence. PR #21 explicitly permits direct_local/direct_provider access and requires direct-local embeddings and ASR, contradicting current mandatory LiteLLM governance.
<!-- governance-crud:end id=k-20260713-0004 -->

<!-- governance-crud:start id=k-20260713-0005 -->
## k-20260713-0005: PR 28 agent-review failure was semantic, not runner or broker transport failure

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: P1,pr-28,agent-review,terra,runner,broker,stale-base
- Source: GitHub run/job logs and check/status APIs; systemd/readlink; local exact worktree diff and focused tests
- Confidence: high

GitHub run 29267105671/job 86875248027 checked out protected dev policy 33e8bbd2, passed admission, reached the system broker, completed a real GPT-5.6 Terra high-reasoning review, and returned changes-needed for PR #28 head 161b262. The sole finding was that candidate authority status bound only head SHA and could survive a changed base. The requester exited 1 as designed. Production broker and runner services are active, with production release current -> 22ead0edd2a2190eb167956a878c97aff50208d2. GitHub shows no commit status on 161b262 because the production release predates PR #28's candidate authority publisher; only the GitHub Actions agent-review check failed. The local PR #28 worktree contains uncommitted remediation that adds base_ref binding, a base-specific authority context, immediate base-ref SHA and strict-protection checks before publication, and edited-event retriggering. Its focused 29 tests pass locally, but it has no independent QA and still invokes Pi through direct openai-codex rather than mandatory genus-router/LiteLLM.
<!-- governance-crud:end id=k-20260713-0005 -->

<!-- governance-crud:start id=k-20260713-0006 -->
## k-20260713-0006: Qwen3-ASR substrate exists but is inactive and absent from LiteLLM

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: P1,asr,qwen3-asr,litellm,systemd,gpu
- Source: Authenticated LiteLLM model list; systemctl/status/unit metadata; bounded qwen-asr journal; nvidia-smi
- Confidence: high

Authenticated LiteLLM /v1/models on 2026-07-13 returned 26 IDs; qwen3-asr was absent and qwen3.6-a3b was the only Qwen-like ID. System qwen-asr.service exists, is disabled/inactive, targets Qwen/Qwen3-ASR-1.7B on localhost:8642, and historical July 8 logs prove it previously loaded 3.87 GiB, completed startup, advertised transcription support, and exposed /v1/audio/transcriptions. It previously suffered transient Hugging Face DNS/cache lookup failures before later loading successfully. Current qwen-it occupies GPUs 1 and 2; ASR is not registered through LiteLLM and no current transcription was performed.
<!-- governance-crud:end id=k-20260713-0006 -->

<!-- governance-crud:start id=k-20260713-0007 -->
## k-20260713-0007: Qwen instruct backend credential is embedded in a world-readable unit and was exposed

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: P1,security,credential-exposure,qwen,systemd,incident
- Source: systemctl unit readback and stat metadata 2026-07-13; session tool transcript
- Confidence: high

During authorized read-only inspection, systemctl cat qwen-it.service emitted a nonempty backend API key because it is embedded directly in ExecStart. The unit is root-owned mode 0644, so the credential is locally world-readable; the command output also placed it in this session's tool transcript. The value is intentionally omitted here. Treat the credential as compromised. No service or credential mutation was performed.
<!-- governance-crud:end id=k-20260713-0007 -->

<!-- governance-crud:start id=k-20260713-0008 -->
## k-20260713-0008: Model governance is verified locally but not promoted to either protected component base

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: P1,model-governance,promotion,genus-router,noetic-dev,blocked
- Source: GitHub genus-router PR #5 readback; git object verification at noetic-dev ad726a2; root canonical-file search
- Confidence: high

Genus-router PR #5 remains open at exact head d085a6d8e1ea33a2d8e764e8d313120ce7a0da76 against main 178a602; its body records 48 checks, two paired routed QA generations, mandatory local-litellm, the governed model set, and fail-closed ASR readiness. In noetic-dev, verified local checkpoint ad726a2089460576827298f77d616853127b5dd1 contains docs/model-routing-policy.md and config/model-policy.json plus protected route-evidence schema v2. Neither is on a protected remote base: genus-router PR #5 is unmerged, and noetic-dev Issue #29 remains unpushed under the freeze. Root main still has stale direct-access wording in README.md, SYNTHESIS.md, and AGENTS.md. Therefore the policy is adjudicated and locally verified but not yet fully promoted.
<!-- governance-crud:end id=k-20260713-0008 -->

<!-- governance-crud:start id=k-20260714-0001 -->
## k-20260714-0001: Genus-router Issue 6 duplicate protected QA lifecycles

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: genus-router,issue-6,qa,evidence,governance
- Source: /home/dgk/workspace/genus-router-worktrees/issue-4-model-policy/state/{decisions,outcomes}.jsonl; /tmp/opencode/genus-router-runtime/state/{decisions,outcomes}.jsonl; protected artifact hashes
- Confidence: high

Verified against local routing ledgers and preserved artifacts on 2026-07-14. Generation 156f920 had two complete overlapping Terra/high lifecycles: Issue #4 ledger decisions d-20260714-000090/000091 with reported artifact SHA-256 f9195aabdddec5b23a13282130357583882ce942806f9a6e2b9d32b779581458, then runtime decisions d-20260714-000012/000013 with preserved artifact SHA-256 d13330371b3e5c3b98f76c42179259a692d92aa56eb7ccbbf142e24401bb6c38. Generation efc0daf likewise had runtime decisions d-20260714-000014/000015 and d-20260714-000016/000017; reported artifact SHA-256 041080d7e8cecda42e976ee7b5c7af157af461e69aadedecf344fe9be3f9c87b was overwritten by preserved SHA-256 8415ee7ac44efdccfa36e919bef5881a4c487d21b49be98592a321627225917a. Reused run IDs/output paths caused artifact overwrite. Both immutable generations violated the exact implementation:QA pairing invariant and must not be represented as exactly paired.
<!-- governance-crud:end id=k-20260714-0001 -->

<!-- governance-crud:start id=k-20260714-0002 -->
## k-20260714-0002: Issue #6 generation 2f328e1 received duplicate protected QA and failed review

- Ledger: knowns
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: genus-router,issue-6,qa,duplicate,policy
- Source: /tmp/opencode/genus-router-runtime/state/decisions.jsonl; /tmp/opencode/genus-router-runtime/state/outcomes.jsonl; /tmp/opencode/genus-router-issue6-2f328e1-qa/genus-router-issue6-2f328e1-qa-20260714-001/protected/qa-execution-record.json
- Confidence: high

Superseded by `k-20260714-0003`, which records the same duplicate QA event with the verified overlapping lifecycle pairing, timestamps, surviving artifact binding, and overwritten hash. Retained only as audit history.
<!-- governance-crud:end id=k-20260714-0002 -->

<!-- governance-crud:start id=k-20260714-0003 -->
## k-20260714-0003: Issue 6 generation 2f328e1 received overlapping protected QA lifecycles

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: genus-router,issue-6,qa,duplicate-lifecycle,config-policy
- Source: /tmp/opencode/genus-router-runtime/state/decisions.jsonl; /tmp/opencode/genus-router-runtime/state/outcomes.jsonl; /tmp/opencode/genus-router-issue6-2f328e1-qa/genus-router-issue6-2f328e1-qa-20260714-001/protected/qa-execution-record.json
- Confidence: high

Protected runtime evidence advanced from 17 decisions/17 outcomes to 21/21 for immutable genus-router generation 2f328e1eb115b2418d1b828a6c1e877164fa760e. The preserved lifecycle uses readiness decision d-20260714-000018 and execution decision d-20260714-000020; its authoritative record SHA-256 is 00d7a581f7875ae290f9ec901d42c1f80739248fd6d06dabb9383467c6de5a2f and its final text is CHANGES_NEEDED. A concurrent lifecycle used d-20260714-000019 and d-20260714-000021, reported record SHA-256 058a25958ab713f43376b0695e93894ac299f1d0c00d36e104b0fd6a55602b69, and was overwritten by the later-finishing preserved lifecycle. The preserved findings show mutable Fable upstream identity and mutable fable_eligibility.model can weaken canonical model and reasoning invariants.
<!-- governance-crud:end id=k-20260714-0003 -->

<!-- governance-crud:start id=k-20260714-0004 -->
## k-20260714-0004: Fresh Issue 6 replacement 938b924 failed its single protected QA

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: genus-router,issue-6,qa,policy,identity
- Source: /tmp/opencode/genus-router-issue6-938b924-qa/genus-router-issue6-938b924-qa-20260714-001/protected/qa-execution-record.json; /tmp/opencode/genus-router-runtime/state/decisions.jsonl; /tmp/opencode/genus-router-runtime/state/outcomes.jsonl
- Confidence: high

Generation 938b924896a300ce3ed0ae46ea2cbdf2f06574ab received exactly one atomically locked Terra/high QA lifecycle: readiness d-20260714-000022 and execution d-20260714-000023. Artifact 535762c02a81454886fd8b852526d2a64fd920b3e19dd6f39a46730db620b339 is bound to tree e57ae6bc103206b9d9dbff4d9cb1495109a98d22 and returns CHANGES_NEEDED. Verified gaps are mutable endpoint base/interface, mutable non-Sol/Fable upstream IDs, self-consistent modality substitution, mutable per-model endpoint paths, and capability tiers accepted in orders that runtime does not consume.
<!-- governance-crud:end id=k-20260714-0004 -->

<!-- governance-crud:start id=k-20260714-0005 -->
## k-20260714-0005: Fresh Issue 6 replacement 938b924 failed its sole protected QA

- Ledger: knowns
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: genus-router,issue-6,qa,config-policy,identity
- Source: /tmp/opencode/genus-router-issue6-938b924-qa/genus-router-issue6-938b924-qa-20260714-001/protected/qa-execution-record.json; /tmp/opencode/genus-router-runtime/state/decisions.jsonl; /tmp/opencode/genus-router-runtime/state/outcomes.jsonl
- Confidence: high

Superseded by `k-20260714-0004`, which records the same sole-QA failure for 938b924. Retained as duplicate audit history only.
<!-- governance-crud:end id=k-20260714-0005 -->

<!-- governance-crud:start id=k-20260714-0006 -->
## k-20260714-0006: Issue 6 remediation c757fb6 passed its sole protected QA

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: genus-router,issue-6,qa,pass,identity
- Source: /tmp/opencode/genus-router-issue6-c757fb6-qa/genus-router-issue6-c757fb6-qa-20260714-001/protected/qa-execution-record.json; /tmp/opencode/genus-router-runtime/state/decisions.jsonl; /tmp/opencode/genus-router-runtime/state/outcomes.jsonl
- Confidence: high

Immutable genus-router candidate c757fb6782c3126d30177c5cd0b7a9ee1fb6cab7 received exactly one atomically locked Terra/high lifecycle from a 23/23 baseline: readiness d-20260714-000024 and execution d-20260714-000025. Both outcomes succeeded. Artifact b62490d07d2fc6b3f2bbbb1af58909e3b7176299ab0c67bee789d59befe21a2f binds tree 6cc73d28c532a50efe63b75b6d590c05317e3516 with unchanged before/after trees, no tools or writes, and final verdict PASS after endpoint, identity, alias, modality, path, capability, schema, and approval-path attacks.
<!-- governance-crud:end id=k-20260714-0006 -->

<!-- governance-crud:start id=k-20260714-0007 -->
## k-20260714-0007: Issue 6 remediation c757fb6 passed its sole protected QA

- Ledger: knowns
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: genus-router,issue-6,qa,pass,xhigh
- Source: /tmp/opencode/genus-router-issue6-c757fb6-qa/genus-router-issue6-c757fb6-qa-20260714-001/protected/qa-execution-record.json; /tmp/opencode/genus-router-runtime/state/decisions.jsonl; /tmp/opencode/genus-router-runtime/state/outcomes.jsonl
- Confidence: high

Superseded by `k-20260714-0006`, which records the same sole-QA PASS for c757fb6. Retained as duplicate audit history only.
<!-- governance-crud:end id=k-20260714-0007 -->

<!-- governance-crud:start id=k-20260714-0008 -->
## k-20260714-0008: Genus-router PR 7 is exact-head QA green and CI green

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: genus-router,issue-6,pr-7,ci,protection
- Source: https://github.com/somebloke1/genus-router/pull/7; https://github.com/somebloke1/genus-router/actions/runs/29377305433
- Confidence: high

PR https://github.com/somebloke1/genus-router/pull/7 is OPEN and MERGEABLE at exact protected head c757fb6782c3126d30177c5cd0b7a9ee1fb6cab7. Required `quality` run 29377305433 passed config validation, 104 tests, Ruff, mypy, and MCP stdio smoke. Main protection requires strict quality, linear history, admin enforcement, and resolved conversations; it requires no separate review count. The branch and remote head match and the worktree is clean.
<!-- governance-crud:end id=k-20260714-0008 -->

<!-- governance-crud:start id=k-20260714-0009 -->
## k-20260714-0009: Genus-router PR 7 merged with exact protected QA tree

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: genus-router,issue-6,pr-7,merge,protected-main
- Source: https://github.com/somebloke1/genus-router/pull/7; https://github.com/somebloke1/genus-router/issues/6
- Confidence: high

PR https://github.com/somebloke1/genus-router/pull/7 was squash-merged to protected main as 6a6487f2ccf69046e48ef7b38af2533e885ae7c4. Its tree 6cc73d28c532a50efe63b75b6d590c05317e3516 exactly equals the independently reviewed c757fb6 candidate tree. Issue #6 closed at 2026-07-14T23:52:33Z. Main protection remains strict quality, admin enforcement, linear history, and conversation resolution with force pushes/deletions disabled.
<!-- governance-crud:end id=k-20260714-0009 -->

<!-- governance-crud:start id=k-20260714-0010 -->
## k-20260714-0010: Genus-router Issue 6 merged with exact protected QA tree

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: genus-router,issue-6,pr-7,merge,qa-tree
- Source: https://github.com/somebloke1/genus-router/pull/7; genus-router origin/main
- Confidence: high

PR https://github.com/somebloke1/genus-router/pull/7 merged through protected main at commit 6a6487f2ccf69046e48ef7b38af2533e885ae7c4. Its tree 6cc73d28c532a50efe63b75b6d590c05317e3516 exactly equals the sole-QA PASS candidate tree. Issue https://github.com/somebloke1/genus-router/issues/6 closed. Main protection remained strict quality, linear history, admin enforcement, and conversation resolution with force pushes/deletions disabled.
<!-- governance-crud:end id=k-20260714-0010 -->

<!-- governance-crud:start id=k-20260714-0011 -->
## k-20260714-0011: Genus-router PR 7 merged without reviewed-tree drift

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: genus-router,issue-6,pr-7,merge,tree-identity
- Source: https://github.com/somebloke1/genus-router/pull/7; https://github.com/somebloke1/genus-router/issues/6
- Confidence: high

PR https://github.com/somebloke1/genus-router/pull/7 is MERGED as squash commit 6a6487f2ccf69046e48ef7b38af2533e885ae7c4 and Issue #6 is CLOSED. `origin/main^{tree}` is 6cc73d28c532a50efe63b75b6d590c05317e3516, exactly equal to protected PASS candidate c757fb6's tree. Main branch protections remained unchanged after merge.
<!-- governance-crud:end id=k-20260714-0011 -->

<!-- governance-crud:start id=k-20260714-0012 -->
## k-20260714-0012: Genus-router Issue #8 generation 6b20f4c received duplicate overlapping QA lifecycles and is process-invalid

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: P1,genus-router,issue-8,qa,duplicate-lifecycle,process-invalid
- Source: /tmp/opencode/genus-router-runtime/state/decisions.jsonl; /tmp/opencode/genus-router-runtime/state/outcomes.jsonl; /tmp/opencode/genus-router-issue8-6b20f4c-qa/genus-router-issue8-6b20f4c-qa-20260714-001/protected/qa-execution-record.json
- Confidence: 1.0

Verified from `/tmp/opencode/genus-router-runtime/state/{decisions,outcomes}.jsonl`: immutable candidate `6b20f4c30ca4aebee50dabd3225dac1f9c0d454c`, tree `5867e27dedde0ab10d7f9530a78c8e3fc343b60a`, received two overlapping Terra/high authoritative QA lifecycles rather than exactly one: readiness/execution `d-20260715-000001/000002` and `d-20260715-000003/000004`. Both decision/outcome pairs completed. Both processes wrote the same run path, so the latter artifact overwrote the former. The current artifact SHA-256 is `5f76f3459c97c3e588e7b62c56d2ec92f397ceb84e2720bf6cdb685912e7588d`, bound to `d-20260715-000003/000004`, and returns `CHANGES_NEEDED`; an earlier command reported overwritten artifact hash `daf731ef490d1f37944fb1beab44137e0a74e6bcc82f491d08efdd728daf4bfc`. Candidate 6b20f4c cannot satisfy exact implementation:QA accounting. Current QA findings are FIFO/device blocking before regular-file validation, acceptance of control/non-ASCII header values, uncaught Unicode header encoding, and non-portable/conditional secure-open flags. A fresh remediation generation is required and must receive one atomically serialized lifecycle.
<!-- governance-crud:end id=k-20260714-0012 -->

<!-- governance-crud:start id=k-20260714-0013 -->
## k-20260714-0013: Genus-router Issue #8 generation 6b20f4c has duplicate QA lifecycles and blocking credential defects

- Ledger: knowns
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: P1,genus-router,issue-8,qa,duplicate-record
- Source: /home/dgk/workspace/synthesis/KNOWNS.md
- Confidence: 1.0

Superseded as a duplicate record of canonical verified known `k-20260714-0012`; retain only for audit history.
<!-- governance-crud:end id=k-20260714-0013 -->

<!-- governance-crud:start id=k-20260714-0014 -->
## k-20260714-0014: Genus-router Issue #8 remediation 96a2143 received exactly one QA lifecycle and needs further changes

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: P1,genus-router,issue-8,qa,credential-security,changes-needed
- Source: /tmp/opencode/genus-router-issue8-96a2143-qa/genus-router-issue8-96a2143-qa-20260715-001/protected/qa-execution-record.json; /tmp/opencode/genus-router-runtime/state/decisions.jsonl; /tmp/opencode/genus-router-runtime/state/outcomes.jsonl
- Confidence: 1.0

Immutable remediation `96a2143748c9ea0a63723b02b3a3f5209943f9e1`, tree `725b84515b1ecaf10b89afacad2fee2b38e3eeed`, received exactly one atomically guarded Terra/high QA lifecycle from runtime-ledger baseline 29/29: readiness `d-20260715-000005` and execution `d-20260715-000006`, both with one invocation and one recorded success outcome. Artifact SHA-256 `a28b5719bf6716cbf08e6bed54666d99be109b0b5045b3fdad2bb7f1d59b69a1` is bound to unchanged before/after tree and returns CHANGES_NEEDED. Prior FIFO/control/non-ASCII/missing-flag findings are closed. Remaining blockers: a valid availability cache bypasses later malformed/revoked credential validation; file reads do not prove a stable complete snapshot across concurrent truncation/short reads; and close errors occur outside OSError translation and can prevent the second descriptor cleanup. A new remediation generation is required; do not dispatch QA again for 96a2143.
<!-- governance-crud:end id=k-20260714-0014 -->

<!-- governance-crud:start id=k-20260714-0015 -->
## k-20260714-0015: Exact genus-router Issue #8 candidate 00c0b66 QA returned CHANGES_NEEDED

- Ledger: knowns
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: genus-router,issue-8,qa,duplicate-record
- Source: /home/dgk/workspace/synthesis/KNOWNS.md
- Confidence: 1.0

Superseded as a duplicate of canonical verified known `k-20260714-0016`, which records the same exact `00c0b66` QA lifecycle with the full protected decision/outcome, artifact, source-inspection, and non-promotion evidence. Retained only as audit history.
<!-- governance-crud:end id=k-20260714-0015 -->

<!-- governance-crud:start id=k-20260714-0016 -->
## k-20260714-0016: Genus-router Issue #8 remediation 00c0b66 received exactly one QA lifecycle and needs further changes

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: P1,genus-router,issue-8,qa,credential-security,changes-needed
- Source: /tmp/opencode/genus-router-issue8-00c0b66-qa/genus-router-issue8-00c0b66-qa-20260715-001/protected/qa-execution-record.json; /tmp/opencode/genus-router-runtime/state/decisions.jsonl; /tmp/opencode/genus-router-runtime/state/outcomes.jsonl; /home/dgk/workspace/genus-router-worktrees/issue-8-systemd-credential/src/genus_router/availability.py
- Confidence: 1.0

Immutable remediation `00c0b666c148578415f2913ecafa349e5f2520fd`, tree `754539b754e605e39ac56014005b44195c9615aa`, received exactly one atomically guarded Terra/high QA lifecycle from runtime-ledger baseline 31/31: readiness `d-20260715-000007` and execution `d-20260715-000008`, each with one invocation and one recorded success outcome. Protected artifact SHA-256 `b2b92b04047eab08d2dc9f5db4553aa99649aa00683b6340f4da2ca625afb0a2` is bound to unchanged before/after tree, authoritative no-tools isolation, and verdict `CHANGES_NEEDED`. Source inspection confirms four blockers: direct environment credentials lack the 4096-byte bound; cache state retains unsalted token SHA-256 derivatives; endpoints sharing one token environment load it independently and can use mixed snapshots; and cache identity omits source provenance, allowing same-token direct/file or file-replacement transitions to reuse stale availability. Runtime ledgers now contain exactly 33 decisions and 33 outcomes. Do not dispatch QA again for `00c0b66`; create a fresh remediation generation.
<!-- governance-crud:end id=k-20260714-0016 -->

<!-- governance-crud:start id=k-20260714-0017 -->
## k-20260714-0017: Genus-router Issue #8 remediation 727f032 received exactly one QA lifecycle and needs further changes

- Ledger: knowns
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: genus-router,issue-8,qa,duplicate-record
- Source: /home/dgk/workspace/synthesis/KNOWNS.md
- Confidence: 1.0

Superseded as a duplicate of canonical verified known `k-20260714-0018`, which records the same exact `727f032` QA lifecycle with full source, artifact, tree, ledger, and blocker evidence. Retained only as audit history.
<!-- governance-crud:end id=k-20260714-0017 -->

<!-- governance-crud:start id=k-20260714-0018 -->
## k-20260714-0018: Genus-router Issue #8 remediation 727f032 received exactly one QA lifecycle and needs further changes

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: P1,genus-router,issue-8,qa,credential-snapshot,changes-needed
- Source: /tmp/opencode/genus-router-issue8-727f032-qa/genus-router-issue8-727f032-qa-20260715-001/protected/qa-execution-record.json; /tmp/opencode/genus-router-runtime/state/decisions.jsonl; /tmp/opencode/genus-router-runtime/state/outcomes.jsonl; /home/dgk/workspace/genus-router-worktrees/issue-8-systemd-credential/src/genus_router/availability.py
- Confidence: 1.0

Immutable remediation `727f0322b782c694b5c6830cb3d369d82490c173`, tree `f58685b41b87a4102d590de78f134453a11e0044`, received exactly one atomically guarded Terra/high QA lifecycle from runtime-ledger baseline 33/33: readiness `d-20260715-000009` and execution `d-20260715-000010`, each with one invocation and one recorded success outcome. Protected artifact SHA-256 `b78ba4b2d87abde997a8a373c7f711298d84a907bda5c795af4a83fef8f242e8` is bound to unchanged before/after tree, authoritative no-tools isolation, and verdict `CHANGES_NEEDED`. Source inspection confirms two blockers: different token-environment names that alias one actual credential path can still observe mixed snapshots because deduplication is by token-env name only; and `get_models()` computes `min()` before its exception boundary, so an empty endpoint map raises uncaught `ValueError`. Runtime ledgers now contain exactly 35 decisions and 35 outcomes. Do not dispatch QA again for `727f032`; create a fresh remediation generation.
<!-- governance-crud:end id=k-20260714-0018 -->

<!-- governance-crud:start id=k-20260714-0019 -->
## k-20260714-0019: Genus-router Issue #8 remediation cbd1f34 received exactly one QA lifecycle and needs further changes

- Ledger: knowns
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: genus-router,issue-8,qa,duplicate-record
- Source: /home/dgk/workspace/synthesis/KNOWNS.md
- Confidence: 1.0

Superseded as a duplicate of canonical verified known `k-20260714-0021`, which records the same exact `cbd1f34` QA lifecycle, artifact, three blockers, and 37/37 ledger accounting. Retained only as audit history.
<!-- governance-crud:end id=k-20260714-0019 -->

<!-- governance-crud:start id=k-20260714-0020 -->
## k-20260714-0020: Genus-router Issue #8 remediation cbd1f34 received exactly one QA lifecycle and needs further changes

- Ledger: knowns
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: genus-router,issue-8,qa,duplicate-record
- Source: /home/dgk/workspace/synthesis/KNOWNS.md
- Confidence: 1.0

Superseded as a duplicate of canonical verified known `k-20260714-0021`, which records the same exact `cbd1f34` QA lifecycle, artifact, three blockers, and 37/37 ledger accounting. Retained only as audit history.
<!-- governance-crud:end id=k-20260714-0020 -->

<!-- governance-crud:start id=k-20260714-0021 -->
## k-20260714-0021: Genus-router Issue #8 remediation cbd1f34 received exactly one QA lifecycle and needs further changes

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: P1,genus-router,issue-8,qa,cache-identity,credential-logging,changes-needed
- Source: /tmp/opencode/genus-router-issue8-cbd1f34-qa/genus-router-issue8-cbd1f34-qa-20260715-001/protected/qa-execution-record.json; /tmp/opencode/genus-router-runtime/state/decisions.jsonl; /tmp/opencode/genus-router-runtime/state/outcomes.jsonl
- Confidence: 1.0

Immutable remediation `cbd1f341a64d3370bd6b6978817cc6538f4248b3`, tree `69e231943dd10d982d0651a7540770ef2a84fd91`, received exactly one atomically guarded Terra/high QA lifecycle from runtime-ledger baseline 35/35: readiness `d-20260715-000011` and execution `d-20260715-000012`, each with one invocation and one recorded success outcome. Protected artifact SHA-256 `fad8e74542fd74b5c9f457a34ef2aae504515c865126ed86a7483381caa1620a` is authoritative, no-tools, bound to unchanged before/after tree, and returns `CHANGES_NEEDED`. QA found three blockers: `_validate_token` scans arbitrarily large direct values before applying its bound; availability cache identity omits mutable endpoint/model-reference configuration and can return stale models after map changes; and logging the caught HTTP exception object can retain a credential-bearing traceback or request in `LogRecord.args`. Runtime ledgers now contain exactly 37 decisions and 37 outcomes. Do not dispatch QA again for `cbd1f34`; create a fresh remediation generation.
<!-- governance-crud:end id=k-20260714-0021 -->

<!-- governance-crud:start id=k-20260714-0022 -->
## k-20260714-0022: Issue #8 generation 5eabac4 is process-invalid after overlapping QA lifecycles

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: P1,qa,issue-8,process-invalid,genus-router
- Source: /tmp/opencode/genus-router-runtime/state/{decisions,outcomes}.jsonl and /tmp/opencode/genus-router-issue8-5eabac4-qa/genus-router-issue8-5eabac4-qa-20260715-001/protected/qa-execution-record.json
- Confidence: high

Verified against the protected runtime ledgers, candidate Git objects, surviving protected artifact, and live process state on 2026-07-15. Candidate `5eabac4d9b28c42f8f783bfd409ec36c99039a90` has tree `89432bc8f6f0625ebd42831236ee8a5538dba640` and passed 152 local tests, Ruff, strict mypy, config validation, MCP smoke, and clean detached-tree checks. It is nevertheless process-invalid: two overlapping routed QA lifecycles used the same QA identity/output path and created decisions `d-20260715-000013` through `d-20260715-000016` with four matching outcomes, rather than one readiness/execution pair. The shared output path retained only one protected artifact after concurrent overwrite; its current SHA-256 is `f59040b9641866c55179980599c093a675bcb106d4251ee3c6cc27e1311e69d9`, binding candidate/tree, prompt SHA-256 `53580b81adb90553a5724dff89d819f8ef7041de1b2b9b2fae1046889f31223b`, Terra/high, no tools, read-only unchanged source, and `CHANGES_NEEDED`. Its concrete findings concern hostile string length underreporting, endpoint/model-reference mutation across awaits storing results under an earlier configuration identity, and the maximum-token-plus-trailing-newline file boundary. Do not push, promote, or QA this generation again; create a fresh remediation generation and exactly one uniquely guarded lifecycle.
<!-- governance-crud:end id=k-20260714-0022 -->

<!-- governance-crud:start id=k-20260714-0023 -->
## k-20260714-0023: Issue #8 generation 5eabac4 is process-invalid after overlapping QA lifecycles

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: P1,genus-router,issue-8,qa,process-invalid,implementation-qa
- Source: commit 5eabac4; tree 89432bc8; /tmp/opencode/genus-router-runtime/state/{decisions,outcomes}.jsonl entries d-20260715-000013..000016; protected artifact f59040b9641866c55179980599c093a675bcb106d4251ee3c6cc27e1311e69d9
- Confidence: high

Verified against genus-router commit/tree, exact detached checks, protected QA files, command output, and runtime JSONL ledgers on 2026-07-15.

Candidate 5eabac4d9b28c42f8f783bfd409ec36c99039a90, tree 89432bc8f6f0625ebd42831236ee8a5538dba640, passed 152 tests, Ruff, strict mypy, config startup validation, authenticated MCP stdio smoke, clean diff, and exact detached materialization. It is nevertheless not promotable and must not receive another QA lifecycle.

Two overlapping successful routed QA lifecycles used the same qa_for_pass/run identity. The router ledgers now contain readiness decisions d-20260715-000013 and d-20260715-000014 plus execution decisions d-20260715-000015 and d-20260715-000016, with one outcome for each. Their shared output path collided: command output reported protected execution hashes 0a78c60381d056e8bc170d061d4af0c7c463c68a7e6a32a587cce3cd7e212a3 and f59040b9641866c55179980599c093a675bcb106d4251ee3c6cc27e1311e69d9; only the f590... artifact remains at the path. The surviving record binds probe d-20260715-000013 and execution d-20260715-000015, exact SHA/tree, Terra/high, no tools, read-only isolation, and CHANGES_NEEDED.

The surviving QA text identifies three remediation inputs: an async endpoint/model-reference snapshot race that can cache B-derived models under A's identity; an adversarial str-subclass length-underreport bypass; and rejection of a 4096-byte token followed by a normalized newline. Because the generation's implementation:QA accounting is 1:2 and its protected outputs collided, these findings may inform a fresh independently implemented generation but cannot validate 5eabac4.

Earlier local dispatch failures (test-created ignored files in a candidate, absent GENUS_ROUTER_CONFIG, and one wrong workdir) created no router decisions. Future QA dispatches must use a never-executed clean detached candidate, explicit GENUS_ROUTER_CONFIG=/tmp/opencode/genus-router-runtime/config/router.yaml, one unique output/run identity, and no retry while any matching process or ledger activity exists.
<!-- governance-crud:end id=k-20260714-0023 -->

<!-- governance-crud:start id=k-20260714-0024 -->
## k-20260714-0024: Issue #8 generation 35c4820 received exactly one QA lifecycle and needs changes

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: P1,genus-router,issue-8,qa,changes-needed,implementation-qa
- Source: /tmp/opencode/genus-router-issue8-35c4820-qa/genus-router-issue8-35c4820-qa-20260715-001/protected/qa-execution-record.json and runtime decisions/outcomes d-20260715-000017/000018
- Confidence: high

Verified on 2026-07-15 against commit/tree, deterministic command output, protected artifact, candidate checkout, and runtime ledgers. Fresh candidate `35c4820bfb3bf8e2dfe7218ee70adebd90a67e2e`, tree `956cd56f2414b6767663fabc937db31eefb7a4db`, is based directly on `cbd1f341a64d3370bd6b6978817cc6538f4248b3`, not process-invalid `5eabac4`. It passed 157 tests, Ruff, strict mypy, config startup validation, authenticated MCP stdio smoke, and clean detached materialization.

Exactly one routed Terra/high QA lifecycle used readiness decision `d-20260715-000017` and execution decision `d-20260715-000018`, with one outcome each. Protected artifact SHA-256 `7319dd62caffb759ab4b05e867ff1312326911c5733684e6309dafb0c2152be9` binds prompt SHA-256 `8ab0ba8eee2c175d5d9873cb68465bc87964071a49f70f381f61293d29efca05`, exact candidate/tree, no tools, read-only unchanged source, and `CHANGES_NEEDED`. Ledgers contain exactly 43 decisions and 43 outcomes.

The three concrete blockers are: shallow mapping copies retain endpoint/reference objects that can be mutated with `object.__setattr__` across awaits while the old configuration identity is stored; a gateway model ID containing the credential can place credential material in `_cached_models`; and `O_NOFOLLOW` on only the final file component allows symlinked parent-directory traversal. This candidate must not be re-reviewed or promoted.
<!-- governance-crud:end id=k-20260714-0024 -->

<!-- governance-crud:start id=k-20260714-0025 -->
## k-20260714-0025: Exact 35c4820 Issue #8 QA found three remaining security blockers

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: P1,genus-router,issue-8,qa,security,cache,symlink
- Source: /tmp/opencode/genus-router-issue8-35c4820-qa/genus-router-issue8-35c4820-qa-20260715-001/protected/qa-execution-record.json and runtime ledger entries d-20260715-000017/000018
- Confidence: high

Verified 2026-07-15 against commit/tree, deterministic command output, protected runtime ledgers, clean detached candidate, and the protected QA artifact. Fresh branch generation `35c4820bfb3bf8e2dfe7218ee70adebd90a67e2e`, tree `956cd56f2414b6767663fabc937db31eefb7a4db`, is based directly on `cbd1f34` rather than process-invalid `5eabac4`. It passed 157 tests, Ruff, strict mypy, config startup validation, authenticated MCP stdio smoke, and clean diff/materialization.

Exactly one routed Terra/high QA lifecycle ran: readiness decision `d-20260715-000017` and execution decision `d-20260715-000018`, each with one invocation and one outcome. The ledgers contain exactly 43 decisions and 43 outcomes. Protected execution artifact SHA-256 `7319dd62caffb759ab4b05e867ff1312326911c5733684e6309dafb0c2152be9` binds prompt SHA-256 `8ab0ba8eee2c175d5d9873cb68465bc87964071a49f70f381f61293d29efca05`, exact candidate/tree/base, no tools, unchanged read-only source, and `CHANGES_NEEDED`.

The three blockers are: (1) mapping copies are shallow, so retained frozen `ModelEndpoint`/`ModelReference` values can be mutated with `object.__setattr__` during an await and used under the pre-mutation configuration identity; (2) an upstream model ID equal to a credential can be stored verbatim in `_cached_models`; (3) `O_NOFOLLOW` on the final component still follows symlinked parent directories. This generation must not be re-reviewed or promoted.
<!-- governance-crud:end id=k-20260714-0025 -->

<!-- governance-crud:start id=k-20260714-0026 -->
## k-20260714-0026: Issue #8 generation 0b2b36a exact QA returned CHANGES_NEEDED

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: issue-8,qa,genus-router,security,implementation-qa
- Source: qa-execution-record:b2a7820c592a8fbfd03ce26c410b884b01818b5f04f84ff979a3d4b931711c1b
- Confidence: high

Verified artifact /tmp/opencode/genus-router-issue8-0b2b36a-qa/genus-router-issue8-0b2b36a-qa-20260715-001/protected/qa-execution-record.json has SHA-256 b2a7820c592a8fbfd03ce26c410b884b01818b5f04f84ff979a3d4b931711c1b and binds candidate 0b2b36a1c7e0a7df6e5b66560369fc20291b2fc3, tree 1afe9d5f96e70c7e6262df2ff80c73208638bda1, base 35c4820bfb3bf8e2dfe7218ee70adebd90a67e2e, prompt 107611690e17717f66dc072a4c68dfee23fa6943c528ddeccadb7453523e5df4, Terra/high, readiness d-20260715-000019, and execution d-20260715-000020 with exactly one outcome each. The authority candidate remained clean and exact. Verdict CHANGES_NEEDED identified two blockers: endpoint/reference fields are not validated/materialized as exact immutable primitives, allowing hostile str subclasses or arbitrary objects to change destination after cache identity is formed; and model IDs accept hostile str subclasses, allowing overridden containment to bypass credential-disclosure rejection and persist secrets in return/cache state.
<!-- governance-crud:end id=k-20260714-0026 -->

<!-- governance-crud:start id=k-20260714-0027 -->
## k-20260714-0027: Issue #8 generation 0b2b36a consumed one exact QA lifecycle and needs exact primitive hardening

- Ledger: knowns
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: issue-8,genus-router,qa,security,credential-isolation,cache-integrity
- Source: /tmp/opencode/genus-router-issue8-0b2b36a-qa/genus-router-issue8-0b2b36a-qa-20260715-001/protected/qa-execution-record.json
- Confidence: high

Duplicate of verified entry k-20260714-0026, which is the canonical record for candidate 0b2b36a and its sole exact Terra/high QA lifecycle. No additional evidence is asserted here.
<!-- governance-crud:end id=k-20260714-0027 -->

<!-- governance-crud:start id=k-20260714-0028 -->
## k-20260714-0028: Issue #8 generation 505209c is process-invalid after duplicate overlapping QA lifecycles

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: issue-8,genus-router,qa,process-invalid,implementation-qa,security
- Source: runtime-ledgers:d-20260715-000021..d-20260715-000024
- Confidence: high

Verified from command output, runtime ledgers, protected files, and candidate Git state. Candidate 505209cdb859cdbe68de112ec83633b03192ff49 (tree ddb904ecc72a3bae785f1b621ba17b5a1c5bb740) was dispatched twice under the same run/role/pass identity, producing readiness decisions d-20260715-000021 and d-20260715-000022 plus execution decisions d-20260715-000023 and d-20260715-000024, each with one outcome. The shared protected path was overwritten: the first command reported execution SHA256 c72dbdb6f3d302793c8333e0ccc68d508154df8894e8a556fea8c6a9e3e99136; the surviving execution is SHA256 1d4dcb4b188474a395492073ff4a043655afe8d3b98ba5103b5bf02c910282e0 and surviving probe SHA256 b9c913543c009461c30f19477a5d9e3ee39f8132ed4defb84b238f76f818b9fe. Therefore this generation violates implementation:QA 1:1, neither lifecycle validates it, and it must not be promoted or rerun. The surviving non-authoritative CHANGES_NEEDED text is actionable research only: partial credential derivatives can enter return/cache state; credential-bearing configured model/upstream IDs can enter cached configuration even when unmatched; and absolute token_env values escape CREDENTIALS_DIRECTORY joining. The candidate remained clean and exact.
<!-- governance-crud:end id=k-20260714-0028 -->

<!-- governance-crud:start id=k-20260714-0029 -->
## k-20260714-0029: Issue #8 generation 505209c is process-invalid after duplicate QA dispatch

- Ledger: knowns
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: issue-8,genus-router,qa,process-invalid,duplicate-dispatch,security
- Source: runtime-ledgers:d-20260715-000021..d-20260715-000024
- Confidence: high

Duplicate of canonical verified entry k-20260714-0028, which records the process-invalid duplicate QA dispatch for candidate 505209c and the informative-only surviving findings. No additional evidence is asserted here.
<!-- governance-crud:end id=k-20260714-0029 -->

<!-- governance-crud:start id=k-20260714-0030 -->
## k-20260714-0030: Issue #8 generation e52a70a consumed its sole Fable xhigh QA attempt without a verdict

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: issue-8,genus-router,qa,fable,xhigh,timeout,unverified
- Source: runtime-ledgers:d-20260715-000025..d-20260715-000028
- Confidence: high

Verified from the clean authority candidate, trusted merged genus-router runtime 6a6487f, append-only ledgers, and gate process output. Fresh candidate e52a70a3aa48bd5e2e117c219cc46e1468eb31c6 (tree a27bd73ac7ce357707a73259cdc2095339a13367, base 0b2b36a1c7e0a7df6e5b66560369fc20291b2fc3) passed 191 tests, Ruff, strict mypy, config validation, and authenticated MCP smoke. Two earlier harness attempts failed before model invocation: the first rejected unsupported independent_approval against an old installed router and created no decisions; the second rejected a config lacking merged independent_approval and created no decisions. A third pre-model harness attempt created decisions d-20260715-000025/000026 but invoked no model; both outcomes were recorded failure. The sole substantive QA lifecycle then routed LiteLLM-served claude-fable-5, invoked Pi with --thinking xhigh and xhigh->max mapping, completed readiness d-20260715-000027 successfully, and started execution d-20260715-000028. Execution timed out after 900 seconds and recorded failure; no semantic verdict or execution artifact exists. This generation has consumed its one independent QA attempt, remains UNVERIFIED, must not be rerun or promoted, and cannot serve as a continuation base.
<!-- governance-crud:end id=k-20260714-0030 -->

<!-- governance-crud:start id=k-20260714-0031 -->
## k-20260714-0031: Issue #8 generation 32ab7c5 received one Sol xhigh gate and needs further changes

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-14
- Updated: 2026-07-14
- Tags: P1,genus-router,issue-8,qa,sol-xhigh,credential-security,changes-needed
- Source: /tmp/opencode/genus-router-issue8-32ab7c5-sol-xhigh-gate/protected/gate-execution-record.json; /tmp/opencode/genus-router-runtime/state/decisions.jsonl; /tmp/opencode/genus-router-runtime/state/outcomes.jsonl
- Confidence: 1.0

Immutable genus-router candidate `32ab7c5896cf70b784122fca30575d443c201580`, tree `e7d1cae1f1f9588ffe80f155ce03757bb8471b0d`, received exactly one LiteLLM-served Sol/xhigh adversarial lifecycle from runtime-ledger baseline 53/53: readiness `d-20260715-000029` and execution `d-20260715-000030`, each with one invocation and one success outcome. Protected artifact SHA-256 `049f98321f51e94769ec2546feabc0107bd68f2b5ab431e414a9270cae6cd15e` binds the unchanged before/after candidate tree, records no-tools/private-namespace isolation, and returns `CHANGES_NEEDED`. Six verified remediation classes remain: stale cache retention across cancellation/source rotation; fragmented and hashed credential derivatives; weaker derivative checking for configuration/cache identities; incoherent alias replacement snapshots; uncaught malformed exact-dataclass and huge-number exceptions retaining stale cache; and empty-endpoint/overlapping-request races. Runtime ledgers now contain exactly 55 decisions and 55 outcomes. Do not dispatch QA again for `32ab7c5`; create a fresh remediation generation.
<!-- governance-crud:end id=k-20260714-0031 -->

<!-- governance-crud:start id=k-20260715-0001 -->
## k-20260715-0001: Issue #8 generation f7dd22f consumed one Sol xhigh attempt without a semantic verdict

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P1,genus-router,issue-8,qa,sol-xhigh,incomplete-stream,unverified
- Source: /tmp/opencode/genus-router-issue8-f7dd22f-sol-xhigh-gate/protected/gate-failure-reconciliation.json; /tmp/opencode/genus-router-runtime/state/decisions.jsonl; /tmp/opencode/genus-router-runtime/state/outcomes.jsonl
- Confidence: 1.0

Immutable genus-router candidate `f7dd22fb39b226dda5029bdbdf8e26e0c603aeb4`, tree `e35c3526f42d123b1bf5c78dfa6aad290f25b129`, received exactly one LiteLLM-served Sol/xhigh lifecycle from runtime baseline 55/55. Readiness `d-20260715-000031` succeeded. Substantive execution `d-20260715-000032` ended with `stopReason=error` and `OpenAI Responses stream ended before a terminal response event`; the route outcome is failure and there is no terminal assistant text or semantic verdict. Ledgers reconcile at 57/57, the exact candidate remained clean/unchanged, and the harness had completed its credential-leakage check before parsing failed. Protected failure-reconciliation artifact SHA-256 is `934ba7f9f9f2b87ce51f1d571111872e76f6398dce09ea44fccbcceaeaa7c994`; execution stdout SHA-256 is `6d9f668bff82c70b775d34d16a961a6fc716db60e807ff2a7d2a581882ba9bb9`. Candidate `f7dd22f` is UNVERIFIED, its QA attempt is consumed, and it must not be rerun, promoted, or used as a continuation base. Nonterminal model reasoning is not adjudication and is not recorded as a finding.
<!-- governance-crud:end id=k-20260715-0001 -->

<!-- governance-crud:start id=k-20260715-0002 -->
## k-20260715-0002: Issue #8 generation b9beb4c consumed one Sol xhigh attempt at the repeated stream boundary

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P1,genus-router,issue-8,qa,sol-xhigh,incomplete-stream,unverified,recurrence
- Source: /tmp/opencode/genus-router-issue8-b9beb4c-sol-xhigh-gate/protected/gate-failure-reconciliation.json; /tmp/opencode/genus-router-runtime/state/decisions.jsonl; /tmp/opencode/genus-router-runtime/state/outcomes.jsonl
- Confidence: 1.0

Immutable genus-router candidate `b9beb4c490bc2494975ad16902c07ea27241f957`, tree `fab4655c9b15fe27f2a9d6fe3821afe307eb0ebd`, received exactly one LiteLLM-served Sol/xhigh lifecycle from baseline 57/57. Readiness `d-20260715-000033` succeeded; substantive execution `d-20260715-000034` ended after approximately 900 seconds with `stopReason=error`, `OpenAI Responses stream ended before a terminal response event`, no terminal assistant text, and no semantic verdict. The execution outcome is failure, ledgers reconcile at 59/59, the candidate remained unchanged, and credential-leakage checking completed before parse failure. Protected failure-reconciliation artifact SHA-256 is `7a13b7c4c297d2abba4e8d230d3d5f2e457e67f4ff9770ceb20b083fe015be67`; execution stdout SHA-256 is `88719d905424816f05f7575021a11aaf70b3ac98872970034dd662d13ce0806d`. This is the second consecutive Sol/xhigh substantive stream to end at the same boundary, now with a reduced 19.2 KB prompt. Candidate `b9beb4c` is UNVERIFIED and consumed; do not rerun, promote, or continue from it, and do not treat nonterminal model reasoning as a finding.
<!-- governance-crud:end id=k-20260715-0002 -->

<!-- governance-crud:start id=k-20260715-0003 -->
## k-20260715-0003: Issue #8 generation 65f57ca consumed one Fable xhigh attempt at the harness timeout

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P1,genus-router,issue-8,qa,fable-xhigh,timeout,unverified,gate-transport
- Source: /tmp/opencode/genus-router-issue8-65f57ca-fable-xhigh-gate/protected/gate-failure-reconciliation.json; /tmp/opencode/genus-router-runtime/state/decisions.jsonl; /tmp/opencode/genus-router-runtime/state/outcomes.jsonl; local Pi pi-ai source inspection
- Confidence: 1.0

Immutable genus-router candidate `65f57caafa23d89ace6abbc6f6229ea6f9d2ea21`, tree `f7e32dcb7d440746be3c618fb709169fcf678b7d`, received exactly one LiteLLM-served Fable/xhigh lifecycle from baseline 59/59. Readiness `d-20260715-000035` returned exact READY. Substantive execution `d-20260715-000036` hit the harness's 900-second subprocess timeout before a terminal result; outcome is failure and there is no semantic verdict or persisted execution stream. Ledgers reconcile at 61/61 and the candidate remained unchanged. Protected failure-reconciliation SHA-256 is `2ac6cba8ac7e91d38c75a76e54a6795d1fd28d0a74e078a457a6a8b40206980c`. Candidate `65f57ca` is UNVERIFIED and consumed; do not rerun, promote, or continue from it. Pi source inspection verifies that the Fable xhigh mapping (`reasoning_effort=max`) is separate from the custom model's current `maxTokens=32768`, so a future fresh gate may preserve truthful xhigh while bounding output tokens to fit the service window.
<!-- governance-crud:end id=k-20260715-0003 -->

<!-- governance-crud:start id=k-20260715-0004 -->
## k-20260715-0004: Issue #8 generation a294477 received one completed bounded-output Sol xhigh gate and needs changes

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P1,genus-router,issue-8,qa,sol-xhigh,changes-needed,bounded-output
- Source: /tmp/opencode/genus-router-issue8-a294477-fable-xhigh-gate/protected/gate-execution-record.json; /tmp/opencode/genus-router-runtime/state/decisions.jsonl; /tmp/opencode/genus-router-runtime/state/outcomes.jsonl; source readback
- Confidence: 1.0

Immutable genus-router candidate `a2944779c9d8af1dc07657491a2cd353be6a2b0f`, tree `4d93c92694f8aaf2b9d03dca9bf446f9f8456c85`, received one substantive LiteLLM-served xhigh lifecycle from baseline 61/61. Fable readiness `d-20260715-000037` failed before substantive review; Sol readiness `d-20260715-000038` returned READY; Sol/xhigh execution `d-20260715-000039` completed successfully with custom `maxTokens=8192`. Protected artifact SHA-256 `4b2323deb7ac1cb97b5e5cfcc62084edaceff36a6be0f6c9d7af893d2ee2d7cc` binds the unchanged exact tree, private no-tools isolation, and verdict `CHANGES_NEEDED`; ledgers reconcile at 64/64. The artifact reports six blocker classes: cache-hit source verification, path replacement after secure open, fragmented configured/cache identity, fragmentation split across configuration and response, noncanonical Base64 pad-bit aliases, and empty endpoints reading missing `model_refs`. Source inspection shows pre-cache-hit verification already exists at line 74, so the first standalone reproduction must be adversarially tested rather than accepted; the remaining classes map to concrete code paths. Candidate `a294477` is consumed and must not be rerun or promoted.
<!-- governance-crud:end id=k-20260715-0004 -->

<!-- governance-crud:start id=k-20260715-0005 -->
## k-20260715-0005: Issue #8 generation 8c7b723 received one bounded-output Sol xhigh gate and exposed speculative-contract escalation

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P1,genus-router,issue-8,qa,sol-xhigh,changes-needed,threat-model
- Source: /tmp/opencode/genus-router-issue8-8c7b723-xhigh-gate/protected/gate-execution-record.json; https://github.com/somebloke1/genus-router/issues/8; spec/initial_design.md; systemd credential API source evidence
- Confidence: 1.0

Immutable candidate `8c7b72305b0d546e63d0dd6983f0e5fd9fcf8053`, tree `f37f3fb6dff9992e673c22d2fa055e19e914ef6a`, received one substantive bounded-output Sol/xhigh gate after Fable readiness failure: `d-20260715-000040/000041/000042`. Protected artifact SHA-256 `c91235747dc0a43fc43e66907658a432fb9af2b445e13b151cbd3beb08cdeb93` binds unchanged tree and verdict `CHANGES_NEEDED`; ledgers reconcile at 67/67. Findings require detecting decorated arbitrary fragments, preserving cross-field multiplicity, combining mixed raw/hex/Base64 transforms, and proving a pathname cannot change after the final descriptor observation. GitHub Issue #8 instead requires precedence, bounded file/systemd reads, invalid/unreadable/nonregular rejection, no value export/exposure, and preserved routing. The binding spec defines a single-user local service and a TTL model-availability cache. Official systemd discussion states `$CREDENTIALS_DIRECTORY` credentials are stable and immutable for the service lifetime and not reloaded in place. Thus the artifact verifies failure against the supplied overbroad contract, not a requirement that belongs to Issue #8's actual threat model.
<!-- governance-crud:end id=k-20260715-0005 -->

<!-- governance-crud:start id=k-20260715-0006 -->
## k-20260715-0006: Minimum-contract genus-router Issue #8 candidate 0acf889 passed its sole Sol xhigh adversarial gate

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P1,genus-router,issue-8,qa,sol-xhigh,pass,systemd-credential
- Source: /tmp/opencode/genus-router-issue8-0acf889-xhigh-gate-002/protected/gate-execution-record.json; /tmp/opencode/genus-router-issue8-0acf889-xhigh-gate/protected/predispatch-failure-reconciliation.json
- Confidence: 1.0

Candidate `0acf889af7bb7f2897c934159afda3d8d961d5f1`, tree `aeda9347b0c9ba437e8066bc2b4a4f834825aa3d`, is based directly on merged `6a6487f2ccf69046e48ef7b38af2533e885ae7c4`. Deterministic evidence: 128 tests passed, Ruff passed, strict mypy passed, config validation passed, `git diff --check` passed, and live authenticated LiteLLM availability returned five registered models with `LITELLM_API_KEY` removed from the child environment and only `$CREDENTIALS_DIRECTORY/litellm_api_key` present. Its one independent semantic gate used Fable readiness failure `d-20260715-000043`, Sol xhigh readiness success `d-20260715-000044`, and exact Sol xhigh substantive execution `d-20260715-000045`; protected artifact SHA-256 `93b44c2e4e2a7d5e8df15ff6406698365ee870e43d4dc1c0c1e5cb0823c77050` returned `PASS`, binds the exact candidate/tree, records one substantive invocation, and verifies unchanged trees before/after. Prompt SHA-256 is `a94f68e1d6a9f084f4292edff97ed3b5b93a0988a6aad608f431925f79836769`; harness SHA-256 is `4d1510ef23d49b632f7cd4d09bc335fb4df446a990634fbe3d61ade103ddca33`. Router ledgers reconcile at 70 decisions and 70 outcomes. An earlier harness launch failed before route/model dispatch because `GENUS_ROUTER_CONFIG` was absent; its preserved reconciliation SHA-256 is `3a069743b65040fb8ccdd201d4100a75af0ed013b1c9c27bcb6156b4df15ad94` and correctly records zero substantive invocations and no consumed QA pass.
<!-- governance-crud:end id=k-20260715-0006 -->

<!-- governance-crud:start id=k-20260715-0007 -->
## k-20260715-0007: genus-router Issue #8 merged through protected PR #10 with the exact gated tree

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P1,genus-router,issue-8,pr-10,merge,protected-main
- Source: https://github.com/somebloke1/genus-router/pull/10; https://github.com/somebloke1/genus-router/issues/8; GitHub branch protection API; local origin/main readback
- Confidence: 1.0

GitHub PR #10 `https://github.com/somebloke1/genus-router/pull/10` merged at 2026-07-15T07:51:01Z as squash commit `4ff584e2e5d190b7e25dc0a4607c494a50069b83`, parent `6a6487f2ccf69046e48ef7b38af2533e885ae7c4`, tree `aeda9347b0c9ba437e8066bc2b4a4f834825aa3d`. The merge tree exactly equals the protected PASS candidate tree from `0acf889af7bb7f2897c934159afda3d8d961d5f1`. Required GitHub `quality` completed SUCCESS before merge. Issue #8 closed at 2026-07-15T07:51:02Z. Post-merge branch-protection readback still requires strict `quality` from GitHub Actions with enforce-admins, required linear history, conversation resolution, no force pushes, and no deletions. No protections were weakened.
<!-- governance-crud:end id=k-20260715-0007 -->

<!-- governance-crud:start id=k-20260715-0008 -->
## k-20260715-0008: Post-Issue-8 subtree inventory identifies exact merged, duplicate, dirty, and genuinely unmerged lines

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P1,subtree-inventory,noetic-dev,genus-router,git,github,worktrees
- Source: parallel read-only git/GitHub inventory for subgoal-813; exact local refs and GitHub API snapshot 2026-07-15
- Confidence: 1.0

Read-only parallel inventory at 2026-07-15 covered all noetic-dev and genus-router local/remote branches, registered worktrees, GitHub PRs/issues, exact HEADs/trees, ancestry, and dirtiness. genus-router `origin/main` is `4ff584e2e5d190b7e25dc0a4607c494a50069b83`, tree `aeda9347b0c9ba437e8066bc2b4a4f834825aa3d`; merged PR head trees #2/#5/#7/#10 exactly equal their squash merge trees. Issue #6 v1 and Issue #8 v1-v9 are clean distinct candidate trees whose issue-level intent is superseded by merged v2/v10. No genus-router worktree is dirty. noetic-dev has 17 local branches/worktrees, 12 open PRs, and a legacy dependency chain #2 -> #4/#15 -> #16 -> #17 -> #18 -> #19 -> #20 -> #21 -> #22 -> Issue #11 branch. PRs #28 and #31 are sibling `dev` lines and both have successful deterministic checks but failed `agent-review`. Merged source branches `issue-23-governance-correction` and `issue-25-agent-review-canary` have exact final-tree equivalents on `origin/dev`; local-only `issue-29-model-routing-policy` has an exact tree equivalent at PR #31 ancestor `01aa791a21f27db2ae2140edf49db5661532e234`. The synthesis root has pre-existing governance/user changes. The Issue #27 worktree has six uncommitted tracked changes not present at PR #28, either Issue #29 tip, or `origin/dev`; these must not be disturbed. All other noetic worktrees are clean.
<!-- governance-crud:end id=k-20260715-0008 -->

<!-- governance-crud:start id=k-20260715-0009 -->
## k-20260715-0009: PR-orchestrator run terminally classified all 12 current noetic-dev PR snapshots

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P1,pr-orchestrator,noetic-dev,pr-31,review,changes-needed
- Source: GitHub processor comments 4980534795 and 4980663728-4980666087; review 4704089413; complete paginated API readback
- Confidence: 1.0

The serial pr-orchestrator run used QUIET_TIMER=60 and policy `sha256:dd91c0026830f9e6908c06be3591ee202a050b6525f26d5b546afc9977829312`. Hard stops passed; complete paginated inventory verified 12 open PRs and complete files/commits/reviews/threads/checks. Exact PR #31 snapshot `4177a9d` received one independent OpenCode general-agent review after canonical claim comment `4980534795`; the child loaded `pr-reviewer`, ran 246 unittest/pytest tests plus 330 subtests and focused adversarial checks, and posted commit-bound review `4704089413`. Verdict `changes-needed` found fixed `authoritative_qa` classification for all non-QA Pi roles, explicitly incomplete OpenCode/curator/modality migration, and absent exact-head production/live review. The canonical comment was reconciled to terminal changes-needed. Current processor markers now exist for every unchanged snapshot: changes-needed on #31, #2, #4, #15, #16, #17, #18; blocked-policy on #28, #19, #20, #21, #22. Fresh inventory found all snapshots unchanged and zero actionable current snapshots under this fingerprint. No PR was repaired or merged inside the orchestrator run.
<!-- governance-crud:end id=k-20260715-0009 -->

<!-- governance-crud:start id=k-20260715-0010 -->
## k-20260715-0010: PR #31 and the verified routing remediation have incompatible single-PR byte bounds

- Ledger: knowns
- Status: verified
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P1,noetic-dev,pr-31,agent-review,diff-bound,remediation,publication-topology
- Source: git diff --binary 33e8bbd2c483dab0abbb85cb5b00079e4a01b8dc 4177a9d9b6f9e39ee3dd831ccef354ddaf1f5d68;git diff --binary 33e8bbd2c483dab0abbb85cb5b00079e4a01b8dc 6bd55d94147eed6cca50c0601b58172b97fb6a24;git diff --binary 4177a9d9b6f9e39ee3dd831ccef354ddaf1f5d68 6bd55d94147eed6cca50c0601b58172b97fb6a24;scripts/governance/agent_review_broker.py;scripts/governance/model_routing.py;https://github.com/somebloke1/noetic-dev/pull/31
- Confidence: high

Verified at 2026-07-15T16:07Z from exact Git object identities. Protected dev base 33e8bbd to remote PR #31 head 4177a9d is 724,398 binary-diff bytes, below the head's 725,000 capture limit and 750,000 assembled-input limit. The same base to independently PASSed remediation tree 6bd55d94 is 813,262 bytes, above both limits. The remediation alone from 4177a9d to 6bd55d94 is 179,992 bytes. GitHub still reports PR #31 OPEN/UNSTABLE at 4177a9d; agent-review failed against production rollback 22ead0e, whose broker limit is 200,000 bytes. Runner and broker services are active and the repository runner is online/idle.

At 2026-07-15T16:13Z, PR #31 metadata was reconciled and independently read back without changing its head or base: the body now identifies the Fable/Sol result as historical old-contract evidence, requires explicit independent_approval=true under closed LiteLLM-served Sol/xhigh before merge, names rollback release 22ead0e and the concrete byte-limit failure, and records the bounded follow-up topology. The PR remained OPEN/UNSTABLE at head 4177a9d; the three protected candidate checks remained successful and agent-review remained failed.
<!-- governance-crud:end id=k-20260715-0010 -->

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
