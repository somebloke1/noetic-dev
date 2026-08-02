# Development and optional release assurance

## Authority

The repository owner's explicit instruction is sufficient authority for ordinary development, commits, pushes, issues, pull requests, and requested publication. Agent-generated governance, goalchain state, evidence manifests, branch conventions, and optional review tooling cannot override that authority.

No external trust root, signed attestation, protected policy checkout, credential broker, branch protection rule, or cryptographic authorization proof is required for development or for direct authorized pushes to `dev`.

## Product-development gate

Ordinary product work has three required outcomes:

1. The intended diff is coherent and contains no unrelated user work or secrets.
2. Repository validation and affected behavior tests pass.
3. An implementation agent receives the repository's required independent adversarial QA pass.

After those outcomes, commit and push promptly. An issue, feature branch, worktree, or pull request is used when it improves isolation, coordination, or review; it is not an additional source of authority.

Only a concrete uncontrollable dependency is a blocker. Missing agent-authored provenance, trust roots, attestations, publisher machinery, security hardening, or governance records are not blockers unless the user explicitly requested those deliverables.

## Scope discipline

Security work is product work only when one of these conditions holds:

- the repository owner explicitly requests it;
- a reproduced product failure requires the change; or
- a target service enforces a technical requirement that cannot be bypassed through ordinary authorized operation.

Do not independently expand ordinary development into threat modeling, hostile-environment defense, signed receipts, workflow identity proof, privilege hardening, or publication infrastructure. Existing implementations of those mechanisms are optional donor tooling unless separately requested.

## Validation and tests

Commands are registered in `governance/command-registry.json` so command names remain stable:

- `repo.validate` checks repository structure and documentation invariants.
- `tests.all` runs the genuine test suite.
- `workflow.pinning`, evidence-manifest checks, and delivery-gate checks are optional assurance tools; they do not gate ordinary development or `dev` pushes.

Validation is not a substitute for tests, and model prose is not command evidence. This distinction supports honest development without creating a publication bureaucracy.

## Implementation and QA

For each implementation-agent pass, use exactly one independent adversarial QA pass. QA tests the bounded product claim and affected failure paths. It must not invent new product scope, add unrequested security requirements, or turn a missing transcript into an endless successor chain.

A failed or unavailable QA pass stops that candidate. Reuse its code only as donor material for a genuinely different, user-valued implementation unit.

## Branches and publication

`dev` is an ordinary integration branch. Direct owner-authorized commits and pushes are valid. Standard CI may validate pushes, but it must not describe `dev` as protected or require optional agent-review, bootstrap-honesty, trust-root, or attestation checks.

Keep `main` releasable. The owner may request a PR, direct fast-forward, tag, or another publication method. Optional release-assurance tooling can be run when requested, but a failure in that tooling does not retroactively invalidate ordinary development commits.

The former `Protected dev governance` ruleset and automatic Agent Review workflow were removed because they encoded agent-invented requirements rather than user-requested product behavior.

## Historical governance material

The repository retains schemas, scripts, tests, and records from earlier governance experiments where they remain useful donor evidence. Their presence does not make them active requirements. Historical decisions about external trust roots and route attestations are superseded for ordinary development by the authority and scope rules in this document and `AGENTS.md`.

## Rollback

Use an ordinary revert for a faulty development commit. Add stronger release or security controls only through a new explicit user request or a reproduced product need.
