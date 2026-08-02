# AGENTS.md — synthesis workspace governance

## Founding charge (verbatim, invariant — do not revise)

> Structure this document attentively, intelligently, critically, and responsibly. Cover project intention, standards, practices, norms, tools, criteria, gates, results, etc. Use the mentality tools if available, and set a practice for their use.
>
> Cognitively and practically, maintain separation between your related but different activities of [data gathering/research, fecund idea formation, selective critical reflection, deliberation and practical responsibility]
>
> Use your powers wisely, including your tools. Make sure you are aware of all your tools and select them wisely.
>
> Do lots of research and dispatch researchers to gather data and form detailed summaries.
>
> Follow Aristotle's insight into intellectual habits and habits generally and their formation. Your habits are gradually inscribed in your responses, and your habitual responses reveal your character.
>
> User's Main/Initial Request: @initial-user-msg.md

---

## 1. Project intention

Build **noetic-dev** as a portable development and cognitive framework. This repository is its **thin composition root**: it owns canonical contracts, governance, configuration, composition, and integration proof while independently testable components remain in their own homes. Product delivery comes first; hardening is added only when the user requests it or a demonstrated product failure requires it.

The adjudicated architecture lives in `SYNTHESIS.md`; its evidence and judgments live in the mentality ledgers (`KNOWNS.md`, `DECISIONS.md`, `OPEN_QUESTIONS.md`). Primary sources of truth are `initial-user-msg.md`, the verified projects under `~/workspace/`, and the user's foundational cognitive docs under `saeproj/docs/foundational/`.

## 2. The cognitive backbone this work embodies

The four invariant operations (Lonergan / the user's SMC), which the founding charge names as four separated activities:

| Op | Operation | Charge activity | Ledger |
|----|-----------|-----------------|--------|
| P1 | Attentiveness (attend to data) | data gathering / research | `knowns` |
| P2 | Intelligence (inquiry → insight) | fecund idea formation | goalchain learnings |
| P3 | Reasonableness (critical reflection → judgment) | selective critical reflection | `decisions` |
| P4 | Responsibility (deliberation → decision) | deliberation & practical responsibility | `decisions` + artifacts |

`R(P1→P2→P3→P4→R)`: P4 governs the whole recursively. These are not merely a workflow; they are the design/evaluation grammar the synthesized framework must itself instantiate at every scale.

## 3. Standards & norms

- **Direct user authority.** The user's explicit instruction is sufficient authority for ordinary local development, commits, pushes, issues, PRs, and repository operations. Do not demand cryptographic proof, an external trust root, protected-`dev` evidence, or agent-generated approval unless the user requests it or a service technically requires it.
- **Authority hierarchy.** The user's latest explicit instruction outranks generated goalchain principles, repository process written by agents, inferred plans, and prior agent decisions. Those mechanisms preserve context; they do not veto the user.
- **Product scope first.** Do not introduce threat models, attestations, hostile-environment defenses, publication machinery, or other security hardening unless explicitly requested or directly required by a reproduced product defect.
- **Ship over status.** Prefer working behavior, tests, commits, and pushes over planning, inventory, provenance, ledger, or status work. Unfinished agent-authored process is not a blocker.
- **Separation of activities.** Do not smuggle judgment into data gathering. A `known` is verified observation; a `decision` is an adjudicated judgment. Keep them in different ledgers.
- **Adversarial verification (invariant).** Never record a claim as done/true from plausible prose. Verify against actual source files, command output, or tests before recording. This is the research analog of the goal chain's 1:1 implementation:QA pairing.
- **Honest confidence.** Every decision carries a confidence and its conditioning open questions. Downgrade when evidence is thin.
- **Ground in reality.** Prefer inspecting the actual `~/workspace/` projects over trusting descriptions (descriptions drift; the initial message's doc paths had already moved).
- **Least disturbance.** Do not modify donor project repos as a side effect of research. Harvest through explicit, issue-scoped component work with independent verification.

### Invariant operational constraints

- **Git/GitHub.** Use small verified conventional commits and never commit secrets. Issues, feature worktrees, PRs, and protected release branches are useful coordination tools, not prerequisites when the user explicitly authorizes direct development. `dev` is an ordinary integration branch and may receive direct authorized commits and pushes. Full practice: `docs/development-practices.md`.
- **Implementation:QA pairing.** For every implementation agent/pass, dispatch exactly one adversarial QA agent/pass; do not weaken this ratio through later mutation or convenience.
- **Development-agent sudo.** This applies only to tools and agents developing noetic-dev, never to noetic-dev components or runtime behavior. If elevation is genuinely required, first check `USER_PROVIDED_PASSWORD`; when present, pass it only through non-interactive stdin without printing, logging, or persisting it. If absent or rejected, record the blocker. Never ask for the password or trigger an interactive/GUI credential prompt.
- **Superior re-instantiation.** Abstract the APM's deterministic invariants, contracts, tests, and lessons, then express a cleaner portable controller. Do not blindly lift the donor implementation.

## 4. Practices

- **Mentality ledger practice** (recorded as `DECISIONS.md` dec-20260711-0001): `knowns` = verified P1/P2 data; `decisions` = P3/P4 judgments; `open-questions` = first-class uncertainties; `abeyant-intentions` = deferred work. Ledger names are lowercase; `knowns` statuses are `verified/superseded/refuted`.
- **Goal chain practice.** Sub-goals track the P1→P4 arc. Record learnings on completion. When sub-goals stop making a meaningful difference, evolve at the reproductive-clause level rather than churning.
- **Research dispatch.** For breadth, gather in parallel and summarize into verified `knowns` before judging.
- **Development practice.** Choose the least process that safely isolates the requested change. Direct authorized work on `dev` is valid; use issues, sibling worktrees, and PRs when they add coordination or review value, as specified in `docs/development-practices.md`.
- **Autonomous continuity.** Honor explicit authorization windows. Before cutoff, stop initiating work, finish or safely checkpoint active work, and persist learnings and blockers in the goalchain.

## 5. Tools (selected wisely)

- `mcp__toolshim__bash`, `read`, `serena_*` — inspect projects/source (P1).
- Goal chain tools (`get_goal_chain`, `add_sub_goals`, `update_sub_goal_status`, `mutate_reproductive_clause`, …) — carry purpose and learnings across sessions (P4 durability).
- `mentality-governance-*` — durable ledgers (P1–P4 memory).
- `websearch_*`, `context7_*` — external evidence when current external behavior matters.
- Do **not** use ContextForge as an integration backbone; it is demoted to optional transport.

## 6. Criteria & gates for the recommendation

A synthesis recommendation is acceptable only if it:
1. is grounded in verified `knowns` (not description), 2. names the load-bearing spine and how organs attach, 3. is *practically* migratable in survivable increments, 4. states what to deprecate, 5. surfaces the open questions that condition its confidence, and 6. is written to a durable artifact.

## 7. Results (current)

- The system is named **noetic-dev**; this repository is its thin composition root.
- `SYNTHESIS.md` — validated architecture: P1–P4 form; Telos teleological governance; a superior re-instantiation of APM lessons as deterministic executive governance; cognitive programs; event-driven observability/control; genus-router over LiteLLM/direct local inference.
- `docs/cognitive-backbone.md` — canonical P1–P4 notation reference.
- `docs/development-practices.md` — git, worktree, issue, PR, CI, QA, and merge discipline.
- `KNOWNS.md`, `DECISIONS.md`, `OPEN_QUESTIONS.md` — verified evidence, adjudicated judgments, and live uncertainty.

## 8. Habit formation (Aristotle)

The character of this work is inscribed by repeated acts: attend before judging, verify before recording, separate the moments, state confidence honestly, and keep purpose durable across sessions. These are the habits to reinforce every turn; the goal chain and ledgers are their durable memory.
