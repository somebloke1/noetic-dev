# Contributing to noetic-dev

Read [`AGENTS.md`](AGENTS.md) and [`docs/development-practices.md`](docs/development-practices.md) before changing the repository.

## Required flow

1. Start from an accepted GitHub issue with scope and acceptance criteria.
2. Create an issue-linked feature branch in a sibling git worktree.
3. Keep changes coherent and commits small, verified, and conventional.
4. Run `python3 scripts/validate_repo.py` plus all affected tests.
5. Open a PR that links the issue and relevant decision/known records.
6. Pair implementation with one adversarial QA pass; resolve findings before merge.
7. Merge only with green required checks and current review approval.

Do not commit directly to `main`, commit secrets, bypass checks, or mix unrelated work in one PR.

## Commit format

Use conventional commits, for example:

- `feat(controller): add typed transition contract`
- `fix(events): reject invalid causation links`
- `docs(governance): clarify merge policy`
- `test(controller): cover exhausted remediation path`

## Questions and decisions

Use `OPEN_QUESTIONS.md` for unresolved architecture questions and `DECISIONS.md` for adjudicated judgments. Verified observations belong in `KNOWNS.md`.
