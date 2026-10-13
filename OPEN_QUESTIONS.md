# Open Questions

<!-- governance-crud:start id=oq-20260711-0001 -->
## oq-20260711-0001: Which client surfaces must the unified framework target as first-class?

- Ledger: open-questions
- Status: answered
- Repository: /home/dgk/.codex/worktrees/accepted-source-delivery/feature-cognitional-event-journal
- Created: 2026-07-11
- Updated: 2026-10-13
- Tags: clients,scope,mcp
- Confidence: 0.7

Current reference-client choice is resolved for this campaign: Pi execution with the supplied desktop-browser observability/control interface. Portability and distinct runtime boundaries remain intended; arbitrary agent-loop compatibility is not established. The old pick-a-client approval question does not block development. See dec-20261013-0001, [current goal](/home/dgk/.local/share/noetic-dev-work/01a12d60-2652-7002-b924-501dca4d6a08/goal-refinement-review/goal.md) and [operating plan](/home/dgk/.local/share/noetic-dev-work/01a12d60-2652-7002-b924-501dca4d6a08/team14-strategy/operating-plan.md).

Historical July question (retained verbatim):

The synthesis backbone choice depends on which client surfaces are first-class. PARTIALLY RESOLVED 2026-07-11 by user input + dec-20260711-0004:

USER INPUT: values noetic-pi's web observability paradigm but is uncertain about PTY-terminal embedding; wants a minimalistic + highly-capable + best-expressive client that is also portable/extensible.

RESOLUTION DIRECTION: the client question was partly a false choice. By separating the web observability+control plane (keep, event-driven, client-agnostic - k-0005) from both the terminal multiplexer (demote) and the client runtime, the CLIENT becomes a reversible choice rather than the backbone. Portability and web-observability now coexist.

REMAINING (still user-gated, but now LOW-STAKES): pick the reference client runtime by hands-on feel of minimalism/capability. Default lean = OpenCode (open, extensible, telos-proven, unlocked); Pi retained as rich harvest source; Goose a watch candidate. This no longer blocks architecture; it can be decided after a hands-on trial.

SUPERSEDES the earlier binary 'any MCP client vs Pi-only' framing.
<!-- governance-crud:end id=oq-20260711-0001 -->

<!-- governance-crud:start id=oq-20260711-0002 -->
## oq-20260711-0002: Which license should noetic-dev use before public release?

- Ledger: open-questions
- Status: open
- Repository: /home/dgk/.codex/worktrees/accepted-source-delivery/feature-cognitional-event-journal
- Created: 2026-07-11
- Updated: 2026-10-13
- Tags: license,release,governance
- Confidence: 0.9

Current observed status on 2026-10-13: GitHub reports somebloke1/noetic-dev as PUBLIC; the checked-in LICENSE.md says no open-source license has been selected and all rights are reserved. The old initialization-as-private statement is historical. License selection remains unresolved; this record changes neither licensing nor publication practices. Evidence: [LICENSE.md](/home/dgk/.codex/worktrees/accepted-source-delivery/feature-cognitional-event-journal/LICENSE.md), [GitHub repository](https://github.com/somebloke1/noetic-dev).

Historical July question (retained verbatim):

The composition root is being initialized as a private repository with all rights reserved until the owner selects a license. Resolve before any public release or external redistribution. Candidate evaluation should consider whether independently versioned components may use different licenses and whether the composition/specification layer should favor Apache-2.0, MIT, or another license.
<!-- governance-crud:end id=oq-20260711-0002 -->

<!-- governance-crud:start id=oq-20261013-0001 -->
## oq-20261013-0001: Which remaining workflows deliver qualified cross-session cognitive value?

- Ledger: open-questions
- Status: open
- Repository: /home/dgk/.codex/worktrees/accepted-source-delivery/feature-cognitional-event-journal
- Created: 2026-10-13
- Updated: 2026-10-13
- Tags: cognition,standing,consumer,value
- Confidence: high

Closed-team source, UI and CI acceptance establishes bounded exercised behavior. It does not establish complete workflows for the eight remaining operation editors (including Checking), full persistent lifecycle/history behavior, or human-valued cognitive understanding/reuse across unrelated efforts. Qualify these by actual consumer use while preserving native Opermem standing, provenance and conditions; human judgment remains necessary. Do not treat controller phases or a QA acceptance as semantic promotion.

Separate practical preparation unknowns remain: actual custom-role loading and 16-slot capacity after restart; accepted-worktree Serena coverage; model/task usefulness and effects of the maintained Flash pointers. These do not redefine the overarching mission.

Sources: [goal](/home/dgk/.local/share/noetic-dev-work/01a12d60-2652-7002-b924-501dca4d6a08/goal-refinement-review/goal.md), [strategy evidence](/home/dgk/.local/share/noetic-dev-work/01a12d60-2652-7002-b924-501dca4d6a08/team14-strategy/evidence.md), [pointer acceptance limits](/home/dgk/.local/share/noetic-dev-work/01a12d60-2652-7002-b924-501dca4d6a08/glm53-budget/independent-qa/report.md).
<!-- governance-crud:end id=oq-20261013-0001 -->
