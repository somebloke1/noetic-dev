# Open Questions

<!-- governance-crud:start id=oq-20260711-0001 -->
## oq-20260711-0001: Which client surfaces must the unified framework target as first-class?

- Ledger: open-questions
- Status: superseded
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-08-01
- Tags: clients,scope,mcp
- Source: Superseded by source-grounded runtime-adapter question created 2026-08-01
- Confidence: 0.7

Historical question retained for provenance. The original binary client-scope framing was dissolved by separating event-derived observability, attach, and runtime adapters, then superseded by `oq-20260801-0001`. That successor is now answered for the first local slice by `dec-20260801-0006` and `dec-20260801-0009`: OpenCode 1.18.9 is the first target and Pi 0.80.3 the second-adapter target. Their canonical adapter repositories remain `absent/unpinned`, so selection does not establish readiness, portability, or package-source/release attestation. Other clients remain measured later candidates.
<!-- governance-crud:end id=oq-20260711-0001 -->

<!-- governance-crud:start id=oq-20260711-0002 -->
## oq-20260711-0002: Which license should noetic-dev use before public release?

- Ledger: open-questions
- Status: open
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-08-01
- Tags: license,release,governance
- Confidence: 0.9

The noetic-dev composition root is already a public, versioned repository and currently has no selected open-source license. Resolve licensing before any release, package publication, or external redistribution. The release decision must inventory the selected independently versioned component repositories and donor-derived artifacts, establish compatible per-component licenses, distinguish specification/composition licensing from implementation licensing, and bind the result to the exact T9 release candidate. Apache-2.0, MIT, and other candidates remain unadjudicated; current public visibility does not itself grant reuse rights or satisfy release readiness.
<!-- governance-crud:end id=oq-20260711-0002 -->

<!-- governance-crud:start id=oq-20260713-0001 -->
## oq-20260713-0001: Which retained frozen snapshots remain semantically valid after current governance changes?

- Ledger: open-questions
- Status: open
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: P2,P3,audit,semantic-review,freeze
- Source: Existing-work inventory 2026-07-13
- Confidence: high

The structural dispositions preserve or recreate candidates but do not establish semantic acceptance. Each retained snapshot still needs a current exact-SHA diff review against protected dev, current P1-P4/controller contracts, clause-v8 LiteLLM/genus-router policy, and the independently verified implementation:QA record. In particular, determine whether PR #2 duplicates or conflicts with current governance docs, whether PRs #17-#19 encode assumptions invalidated by delivery schema v2, and which portions of PR #20 remain factually current.
<!-- governance-crud:end id=oq-20260713-0001 -->

<!-- governance-crud:start id=oq-20260713-0002 -->
## oq-20260713-0002: Which services consume the exposed Qwen backend credential?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-07-13
- Tags: P1,P4,security,credential-rotation,qwen,litellm
- Source: Credential exposure incident 2026-07-13
- Confidence: high

Answered by explicit user judgment on 2026-07-13: ignore the embedded Qwen backend key observation because it is not a high-risk scenario in this environment. No consumer mapping or credential rotation is required for this issue. Continue to avoid repeating the value in durable records or responses.
<!-- governance-crud:end id=oq-20260713-0002 -->

<!-- governance-crud:start id=oq-20260713-0003 -->
## oq-20260713-0003: How can verified model-governance artifacts be promoted without violating the freeze?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-13
- Updated: 2026-08-01
- Tags: P2,P4,model-governance,freeze,promotion,branching
- Source: Authority reconciliation 2026-07-13
- Confidence: high

Answered and superseded as a live gate by `dec-20260715-0007`, `dec-20260801-0005`, and the current `ROADMAP.md`. Verified current policy/model artifacts move only through a fresh issue-linked worktree from governed `dev`, one immutable implementation/integration generation, exactly one attributable independent QA, current checks, and squash merge; the old freeze does not gate independent architecture/component work. genus-router revision `f2b839b0cfc737c4c1f0a46d3d519d414529545c` is already merged in its repository and is the selected local evidence pin. T0 integrates current constitutional artifacts; T7 separately reconciles LiteLLM-only profiles and complete modality evidence. Historical frozen candidates remain donor evidence and receive no retroactive acceptance.
<!-- governance-crud:end id=oq-20260713-0003 -->

<!-- governance-crud:start id=oq-20260715-0001 -->
## oq-20260715-0001: What authorized non-interactive elevation channel will install and verify the immutable agent-review release?

- Ledger: open-questions
- Status: open
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-15
- Updated: 2026-07-15
- Tags: P4,noetic-dev,agent-review,deployment,elevation,AR-11,blocker
- Source: chain-49/subgoal-704;systemctl show noetic-dev-agent-review-broker.service noetic-dev-actions-runner.service;stat /opt/noetic-dev-agent-review /run/noetic-dev /var/lib/noetic-dev-runner
- Confidence: high

At 2026-07-15T16:14Z the current shell had neither USER_SUPPLIED_PASSWORD nor passwordless sudo. Production services and the GitHub runner remain active, but the verified remediation cannot be installed as a root-owned immutable release, the protected socket and runner internals cannot be reprobed, and restart/rollback/credential-denial gates cannot be rerun without authorized non-interactive elevation. Governance forbids requesting a password or triggering an interactive/GUI prompt. Resolution requires either a future USER_SUPPLIED_PASSWORD channel used only through non-interactive stdin, a narrowly scoped passwordless deployment mechanism, or an independently operated deployment that returns exact AR-11 evidence.
<!-- governance-crud:end id=oq-20260715-0001 -->

<!-- governance-crud:start id=oq-20260801-0001 -->
## oq-20260801-0001: Which runtime is the first local reference-adapter target and how is its evidence pinned?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-08-01
- Updated: 2026-08-01
- Tags: runtime,client,adapter,pinning,portability
- Source: initial-user-msg.md;SYNTHESIS.md;dec-20260801-0001;dec-20260801-0004
- Confidence: high

Answered for the first authentic local slice by `dec-20260801-0006` and `dec-20260801-0009`: OpenCode 1.18.9 is the first headless reference-adapter target, with local binary evidence SHA-256 `7c4d91c84d2bfdeabb59257e3490c5e5acb08f2aacb3e42f3ddc296a1c3f1aca`; Pi 0.80.3 is the second-adapter target, with local binary evidence SHA-256 `af302f231437eaf6f37691bce4b34234fcb626bcb5eb3910d4fc3f6519bf78ca`. New `somebloke1/noetic-opencode-adapter` and `somebloke1/noetic-pi-adapter` remain `absent/unpinned`. These reversible local evidence pins are not package-source/release attestations, implemented adapters, runtime readiness, or portability proof. Separate initialization, connective-contract, isolated-configuration, and authentic conformance generations remain mandatory.
<!-- governance-crud:end id=oq-20260801-0001 -->

<!-- governance-crud:start id=oq-20260801-0002 -->
## oq-20260801-0002: May observability surfaces exercise privileged control?

- Ledger: open-questions
- Status: open
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-08-01
- Updated: 2026-08-01
- Tags: observability,control,authority,web,tui
- Source: dec-20260711-0004;dec-20260711-0006;dec-20260801-0002
- Confidence: high

The first event-derived web/TUI observability plane is read-only. Determine whether any later surface may approve gates, steer Telos, dispatch or cancel delegations, or invoke effects. Any affirmative answer requires authenticated principals, typed commands, scoped capabilities, expiry/revocation, audit events, separation from projections and independent adversarial verification. The open question does not defer read-only observability.
<!-- governance-crud:end id=oq-20260801-0002 -->

<!-- governance-crud:start id=oq-20260801-0003 -->
## oq-20260801-0003: What authority, effect, persistence, and event-privacy contracts govern live execution?

- Ledger: open-questions
- Status: open
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-08-01
- Updated: 2026-08-01
- Tags: authority,effects,persistence,events,privacy,recovery
- Source: SYNTHESIS.md;dec-20260801-0002;initial-user-msg.md
- Confidence: high

Before production effects, define authenticated principals; scoped repository/workspace/tool/model capabilities; independent QA identity; effect idempotency; cancellation; stale-writer and concurrency behavior; append-only event consistency; semantic-memory privacy, retention and redaction; compatibility/versioning; recovery/replay; and rollback. Resolve only the minimum contract needed for the first vertical slice, preserving explicit extension points rather than blocking all architecture work.
<!-- governance-crud:end id=oq-20260801-0003 -->
