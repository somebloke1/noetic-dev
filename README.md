# noetic-dev

**noetic-dev** is a portable development and cognitive framework whose form is the P1–P4 cognitional cycle and whose composition root is this repository (`somebloke1/noetic-dev`; local directory `synthesis`).

This repository is deliberately thin. It owns the canonical contracts, governance, composition, and integration tests; independently testable components remain in their own homes.

## Architecture at a glance

1. **Cognitive form:** P1 attentiveness → P2 intelligence → P3 reasonableness → P4 responsibility, with P4 governing recursively.
2. **Teleological governance:** Telos carries goals, principles, reproductive clauses, and continuation.
3. **Executive governance:** a superior portable re-instantiation of the noetic-pi/pi2 APM invariants, conformance evidence, and failure lessons orders deterministic multi-agent work; this is not a lift-and-shift.
4. **Cognitive programs:** disciplines and development pipelines run on the executive controller while semantic judgment remains with agents.
5. **Observability/control:** structured cognitional events feed web and TUI renderers; tmux and browser PTYs are optional attach mechanisms.
6. **Model substrate:** genus-router selects models; LiteLLM normalizes primary access; direct local endpoints remain possible.
7. **Operational transport:** plain MCP/HTTP/stdio and ContextForge coexist; ContextForge remains maintained wherever current tools depend on it, without becoming the architectural backbone.

## Start here

- [`SYNTHESIS.md`](SYNTHESIS.md) — adjudicated architecture and migration path
- [`docs/cognitive-backbone.md`](docs/cognitive-backbone.md) — canonical P1–P4 form
- [`docs/controller-architecture.md`](docs/controller-architecture.md) — proposed superior executive controller
- [`docs/controller-adversarial-review.md`](docs/controller-adversarial-review.md) — binding pre-implementation review findings
- [`docs/controller-donor-conformance-inventory.md`](docs/controller-donor-conformance-inventory.md) — prioritized donor fixture map
- [`docs/controller-donor-inventory-review.md`](docs/controller-donor-inventory-review.md) — adversarial completeness review
- [`AGENTS.md`](AGENTS.md) — project governance and invariants
- [`docs/development-practices.md`](docs/development-practices.md) — git, worktree, issue, PR, CI, and merge discipline
- [`KNOWNS.md`](KNOWNS.md), [`DECISIONS.md`](DECISIONS.md), [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) — durable evidence and judgment
- [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`SECURITY.md`](SECURITY.md) — contribution and security rules

## Repository role

This is the **composition root**, not a swallowing monorepo. It will own:

- `spec/` — portable contracts such as the cognitional-event vocabulary;
- `config/` — component and model-substrate bindings;
- `compose/` — reproducible integration/deployment composition;
- integration tests and conformance fixtures;
- governance, architecture, and roadmap artifacts.

Telos, the executive controller, cognitive programs, and attach adapters should remain independently testable components referenced here through explicit versioned interfaces.

## Current phase

Architecture and governance bootstrap. The immediate frontier is to specify the superior executive controller before implementation, preserving proven donor invariants while correcting donor coupling and failure modes.

## License

No open-source license has yet been selected. See [`LICENSE.md`](LICENSE.md).
