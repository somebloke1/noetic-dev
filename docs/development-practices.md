# noetic-dev development practices

**Working summary:** explicit user authority is sufficient for ordinary development. Prefer small verified conventional commits, use isolation and review in proportion to the change, never commit secrets, and do not let agent-created process block authorized product work.

## 1. Sources of truth

- The user's latest explicit instruction defines authority and may define the unit of work directly.
- GitHub issues and pull requests provide useful coordination and review records when the work benefits from them; they are not mandatory authorization layers.
- GitHub Project tracks coordination fields; it does not replace issues or PRs.
- `KNOWNS.md` records verified evidence; `DECISIONS.md` records judgment; `OPEN_QUESTIONS.md` records uncertainty.
- Goalchain state carries active purpose and learnings across sessions but cannot override direct user authority.

## 2. Branches and worktrees

- `dev` is the ordinary integration branch. Direct commits and pushes to `dev` are valid when explicitly authorized by the user.
- Keep `main` releasable. Use a PR or direct promotion according to the user's instruction and the actual repository configuration; do not invent additional protection requirements.
- Branch names: `issue-<number>-<short-slug>`; administrative branches may use `chore/<slug>`.
- Create feature worktrees as siblings, never nested in this repository:

  ```bash
  mkdir -p ../synthesis-worktrees
  git worktree add ../synthesis-worktrees/issue-42-event-schema -b issue-42-event-schema main
  ```

- Keep one coherent concern per worktree. An issue number is recommended for shared coordination, not required for authority.
- Before work, run `python3 scripts/governance/check_worktree.py --repo .`; stop on unsafe inherited Git controls, shared config contamination, a non-reciprocal backlink, or duplicate administration pointers.
- The default duplicate-pointer check examines only the selected root and its direct sibling directories, with a hard 4,096-entry budget; use explicit repeated `--scan-root` values for other controlled locations.
- Never copy a `.git` file or attach an archive export to live worktree administration. Use a neutral standalone repository or a registered worktree.
- Worktrees are transient delivery resources, not storage. After verification, commit and push promptly; complete any requested PR review, then remove worktrees that are no longer needed.
- Keep unfinished intent and blockers in the issue rather than retaining a completed worktree indefinitely.
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

When an implementation issue is useful, it should state:

- why the work serves noetic-dev's primary goal;
- scope and non-goals;
- acceptance criteria and verification commands;
- dependencies and produced artifacts;
- component and cognitional phase (`P1`–`P4`);
- implementation risk and rollback path.

Use child issues only for genuinely independent units. A blocker must name a concrete uncontrollable dependency; unfinished agent-authored governance, missing attestations, and unrequested security machinery are not blockers.

## 5. Pull requests and QA

- A PR should link its issue when one exists.
- Keep PRs small enough for adversarial review; split by interface boundary or independent acceptance gate.
- For every implementation agent/pass, pair exactly one adversarial QA agent/pass. QA tests claims against code, commands, tests, and acceptance criteria rather than prose plausibility.
- Required local checks: repository validation, affected tests, secret hygiene, and inspection of the intended diff. Additional release or security gates apply only when requested.
- Authors do not self-approve. Review approval becomes stale after material changes and must be refreshed.

## 6. Merge policy

- **Squash merge (default):** one issue, coherent change, noisy or iterative branch history. Squash title is a conventional commit and preserves issue closure.
- **Rebase merge:** only when each commit is independently coherent, verified, and useful in permanent history.
- **Merge commit:** reserved for coordinated campaigns or integration branches where preserving topology and component boundaries is itself evidence.
- Do not knowingly merge failing relevant tests or unresolved requested review findings. Follow actual branch rules rather than assuming protections that do not exist.
- Delete merged feature branches unless they are retained as documented release/support lines.

## 7. GitHub Actions

- CI should be deterministic and dependency-light.
- Pin third-party actions before public release when release hardening is in scope; pinning is not a prerequisite for ordinary authorized development.
- Do not expose secrets through workflows.
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
