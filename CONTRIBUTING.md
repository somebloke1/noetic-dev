# Contributing to noetic-dev

Read [`AGENTS.md`](AGENTS.md) and [`docs/development-practices.md`](docs/development-practices.md) before changing the repository.

## Default flow

1. Follow the repository owner's explicit instruction; no additional proof of authority is required.
2. Keep changes coherent and commits small, verified, and conventional.
3. Use a sibling worktree, issue, or PR when it improves isolation, coordination, or review.
4. Run `python3 scripts/validate_repo.py` plus affected tests.
5. Pair an implementation pass with one adversarial QA pass when an implementation agent is used.
6. Commit and push promptly after the requested checks pass.

Direct authorized commits to `dev` are valid. Do not commit secrets, discard unrelated work, or mix unrelated changes in one commit.

Do not add security hardening, attestations, trust-root requirements, hostile-environment defenses, or publication gates unless the repository owner requests them or a reproduced product defect requires them.

## Commit format

Use conventional commits, for example:

- `feat(controller): add typed transition contract`
- `fix(events): reject invalid causation links`
- `docs(governance): clarify merge policy`
- `test(controller): cover exhausted remediation path`

## Questions and decisions

Use `OPEN_QUESTIONS.md` for unresolved architecture questions and `DECISIONS.md` for adjudicated judgments. Verified observations belong in `KNOWNS.md`.
