# Open Questions

<!-- governance-crud:start id=oq-20260711-0001 -->
## oq-20260711-0001: Which client surfaces must the unified framework target as first-class?

- Ledger: open-questions
- Status: open
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: clients,scope,mcp
- Confidence: 0.7

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
- Repository: /home/dgk/workspace/synthesis
- Created: 2026-07-11
- Updated: 2026-07-11
- Tags: license,release,governance
- Confidence: 0.9

The composition root is being initialized as a private repository with all rights reserved until the owner selects a license. Resolve before any public release or external redistribution. Candidate evaluation should consider whether independently versioned components may use different licenses and whether the composition/specification layer should favor Apache-2.0, MIT, or another license.
<!-- governance-crud:end id=oq-20260711-0002 -->
