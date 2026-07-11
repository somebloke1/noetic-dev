# noetic-dev governed roadmap

**Authority:** GitHub epic [#5](https://github.com/somebloke1/noetic-dev/issues/5) coordinates work; child issues and PRs are authoritative for scope and completion. This document records dependency order and promotion gates.

## 1. Roadmap invariants

- One accepted issue → one sibling worktree/branch → one coherent PR.
- Every implementation agent/pass creates exactly one adversarial QA agent/pass; remediation generations receive a new paired QA obligation.
- Green CI is necessary but not sufficient: review must verify acceptance criteria and governing decisions.
- `main` remains protected and releasable; no administrative bypass.
- Portable contracts precede runtime adapters; pure kernels precede effects.
- ContextForge remains operationally maintained while dependency inventory proceeds.
- Donor code is evidence. noetic-dev abstracts invariants and re-instantiates superior forms rather than copying donor structure.

## 2. Dependency graph

```text
#1 architecture consolidation ──────────────────────────────────────────┐
   │                                                                    │
   ├─ #3 controller architecture ─┬─ #6 schemas + authority matrix      │
   │                              ├─ #7 donor conformance inventory     │
   │                              ├─ #9 Telos delegation contract       │
   │                              └─ #11 cognitive programs             │
   │                                                                    │
   ├─ #8 cognitional-event schema ───── #12 observability/control       │
   │                                                                    │
   ├─ #10 model selection/access composition                            │
   ├─ #13 tmux/browser attach contracts                                 │
   └─ #14 ContextForge dependency inventory                             │
                                                                        │
#6 + #7 + #8 + #9 ──► M1 executable kernel and durable store            │
M1 + #10 ───────────► M2 execution/model/repository adapters             │
M2 + #11 + #12 ─────► M3 programs and observability                     │
M3 + #13 + #14 ─────► M4 composition, shadow parity, controlled release ┘
```

## 3. M0 — architecture and contracts

| Issue | Deliverable | Worktree / PR boundary | Promotion gate |
|---|---|---|---|
| [#1](https://github.com/somebloke1/noetic-dev/issues/1) | authoritative noetic-dev architecture | `issue-1-architecture`, PR #2 | independent approval + green CI |
| [#3](https://github.com/somebloke1/noetic-dev/issues/3) | superior controller architecture and adversarial review | `issue-3-controller-spec`, stacked PR #4 | blocking review amendments incorporated; independent approval |
| [#6](https://github.com/somebloke1/noetic-dev/issues/6) | command/event schemas, transitions, authority matrix, Stage A tests | dedicated worktree/PR | schemas executable; negative authority/property tests reviewed |
| [#7](https://github.com/somebloke1/noetic-dev/issues/7) | donor conformance-fixture inventory | dedicated research worktree/PR | source provenance + omission QA |
| [#8](https://github.com/somebloke1/noetic-dev/issues/8) | cognitional-event schemas and compatibility/redaction policy | dedicated worktree/PR | direct/ContextForge sink fixtures + privacy QA |
| [#9](https://github.com/somebloke1/noetic-dev/issues/9) | Telos delegation-dispatch contract | dedicated worktree/PR, Telos follow-up separate | ownership/authority/idempotency boundary approved |
| [#10](https://github.com/somebloke1/noetic-dev/issues/10) | genus-router/LiteLLM/direct endpoint composition | dedicated worktree/PR | reproducible selection evidence + endpoint fallback tests |
| [#11](https://github.com/somebloke1/noetic-dev/issues/11) | versioned cognitive-program contracts | dedicated worktree/PR | deterministic/semantic boundary and donor provenance approved |
| [#12](https://github.com/somebloke1/noetic-dev/issues/12) | observability read models and control authority | dedicated worktree/PR | causal explanations + read-only baseline; privileged controls separately gated |
| [#13](https://github.com/somebloke1/noetic-dev/issues/13) | tmux/browser attach contracts | dedicated worktree/PR | kernel independence + reconnect/security tests |
| [#14](https://github.com/somebloke1/noetic-dev/issues/14) | current ContextForge dependency inventory | dedicated research worktree/PR | completeness review; no decommission action |

## 4. M1 — executable deterministic kernel

Create only after #6 and #7 are accepted.

Planned issue boundaries:

1. Pure transition reducer + graph validator + model/property tests.
2. SQLite causal journal, aggregate versions, snapshots, and rebuild tests.
3. Idempotency ledger and transactional outbox with fake effect adapters.
4. Deterministic scheduler, barrier projection, critical-path and blocked-edge explanations.
5. Lease/fencing and recovery kernel.

Each issue is implementation plus exactly one adversarial QA pass. No Pi/OpenCode/tmux/browser/GitHub effects enter M1.

## 5. M2 — portable effect adapters

After M1 conformance:

- fake runtime parity baseline;
- one headless `AgentRuntimePort` adapter;
- workspace/repository adapter with expected-revision and branch-protection receipts;
- genus-router model-selection adapter and LiteLLM/direct references;
- Telos delegation adapter after #9;
- direct and ContextForge event sinks after #8/#14.

Every adapter has contract tests against the same fake/reference port suite.

## 6. M3 — cognitive programs and observability

- Re-instantiate the development pipeline as a versioned controller program.
- Re-instantiate one cognitive discipline first; add others only after the program contract proves adequate.
- Build read-only event-derived observability before act-from control.
- Add web and TUI renderers against shared read-model fixtures.
- Add privileged controls only as typed controller commands covered by the authority matrix.

## 7. M4 — attach, composition, and controlled release

- tmux attach adapter as minimalist default; browser PTY attach remains optional;
- composition manifests pin every component revision;
- shadow selected donor scenarios and compare transition/evidence outcomes;
- preserve ContextForge service continuity;
- run failure injection, restart/recovery, stale-submission, publication-race, and rollback drills;
- resolve license question before public release.

## 8. GitHub Project discipline

The user-created Project is named **`noetic-dev project`**. Once this runtime token exposes `read:project` and `project` scopes, configure:

- Status: Backlog / Ready / In progress / In review / Blocked / Done
- Priority: P0 / P1 / P2 / P3
- Phase: P1 / P2 / P3 / P4
- Component: form / telos / controller / programs / events / observability / attach / substrate
- Risk: low / medium / high
- Effort: XS / S / M / L / XL

Views:

1. **Execution board** grouped by Status, sorted Priority.
2. **Cognitional view** grouped by Phase.
3. **Architecture view** grouped by Component.
4. **Risks and blockers** filtered to high risk or Blocked.
5. **Review queue** filtered to In review.

Project fields are coordination metadata; issue/PR facts remain authoritative. Do not mutate fields without an underlying state change.

## 9. Completion semantics

- Issue “done” means acceptance criteria verified and merged—not merely authored.
- PR “green” means checks passed, not that semantic review passed.
- Milestone completion does not imply product completion.
- noetic-dev is ready for controlled use only after end-to-end composition, conformance, recovery, security, and rollback proof.
