# noetic-dev development practices

**Immutable summary:** use issue-linked feature worktrees/branches, small verified conventional commits, green CI plus adversarial review before PR merge, deliberate squash/rebase/merge policy, protected `main`, and never commit secrets or bypass governance.

## 1. Sources of truth

- GitHub issues define accepted units of work and acceptance criteria.
- Pull requests are the review, QA, and merge record.
- GitHub Project tracks coordination fields; it does not replace issues or PRs.
- `KNOWNS.md` records verified evidence; `DECISIONS.md` records judgment; `OPEN_QUESTIONS.md` records uncertainty.
- Goalchain state carries active purpose and learnings across sessions.

## 2. Branches and worktrees

- `main` is protected and kept releasable. Do not develop directly on it after bootstrap.
- Branch names: `issue-<number>-<short-slug>`; administrative branches may use `chore/<slug>`.
- Create feature worktrees as siblings, never nested in this repository:

  ```bash
  mkdir -p ../synthesis-worktrees
  git worktree add ../synthesis-worktrees/issue-42-event-schema -b issue-42-event-schema main
  ```

- One issue and one coherent concern per worktree. Do not reuse a dirty worktree for another issue.
- Before deleting a worktree, verify its branch is merged or intentionally retained, then run `git worktree remove` and `git worktree prune`.
- Do not share generated state, virtual environments, or mutable databases across concurrent worktrees unless the interface explicitly guarantees isolation.

## 3. Commits

- Use conventional commits: `<type>(<scope>): <imperative summary>`.
- Each commit must be coherent, reviewable, and pass the checks relevant to its change.
- Inspect `git status`, staged diff, and unstaged diff before committing.
- Stage explicit paths; avoid broad `git add -A` when unrelated files exist.
- Never commit secrets, local runtime state, generated credentials, or unresolved merge markers.
- Do not rewrite or discard another actor's work. Never force-push shared branches without explicit coordination.

## 4. Issues

Every implementation issue should state:

- why the work serves noetic-dev's primary goal;
- scope and non-goals;
- acceptance criteria and verification commands;
- dependencies and produced artifacts;
- component and cognitional phase (`P1`–`P4`);
- implementation risk and rollback path.

Use child issues or task lists for independently verifiable units. Blocked issues state the concrete blocker and required successor condition.

## 5. Pull requests and QA

- Every PR links its issue (`Closes #…`) and relevant decision/known IDs.
- Keep PRs small enough for adversarial review; split by interface boundary or independent acceptance gate.
- For every implementation agent/pass, pair exactly one adversarial QA agent/pass. QA tests claims against code, commands, tests, and acceptance criteria rather than prose plausibility.
- Required gates: repository validation, affected tests, secret hygiene, current branch, no unresolved review findings.
- Authors do not self-approve. Review approval becomes stale after material changes and must be refreshed.

## 6. Merge policy

- **Squash merge (default):** one issue, coherent change, noisy or iterative branch history. Squash title is a conventional commit and preserves issue closure.
- **Rebase merge:** only when each commit is independently coherent, verified, and useful in permanent history.
- **Merge commit:** reserved for coordinated campaigns or integration branches where preserving topology and component boundaries is itself evidence.
- Never merge red CI, unresolved blocking review, or an outdated branch. Do not bypass protected `main`.
- Delete merged feature branches unless they are retained as documented release/support lines.

## 7. GitHub Actions

- CI must be deterministic, least-privilege, and dependency-light.
- Pin third-party actions to immutable commit SHAs before public release; during private bootstrap, official actions may temporarily use reviewed major tags with Dependabot enabled.
- Workflows use minimal `permissions`, do not expose secrets to forks, and never run untrusted PR code with write tokens.
- Checks should validate repository invariants first, then component-specific builds/tests as components arrive.

## 8. GitHub Project discipline

Recommended fields:

- Status: Backlog / Ready / In progress / In review / Blocked / Done
- Priority: P0–P3
- Cognitional phase: P1 / P2 / P3 / P4
- Component: form / telos / controller / programs / events / observability / attach / substrate
- Risk: low / medium / high
- Effort: XS / S / M / L / XL

Move items only when the authoritative issue/PR state supports the transition. Avoid decorative status churn.

## 9. Release and rollback

- Tag only verified composition states.
- Version portable contracts explicitly and support expand/migrate/contract evolution for persisted/public schemas.
- Every risky change states rollback instructions before merge.
- The composition root must be able to pin each component to a known-good revision.
