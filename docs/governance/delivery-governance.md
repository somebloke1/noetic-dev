# Delivery Governance

## Purpose

Define the machine-readable delivery vocabulary, state/authority transitions, model profiles, command registry, issue status, evidence manifest contract, and fail-closed gates that govern noetic-dev's publication pipeline.

## Scope

All changes merged to `main` and published must pass through the governance pipeline. This document is the authoritative specification; the JSON policy files under `governance/` are the machine-readable enforcement.

## Vocabulary

| Term | Definition |
|------|------------|
| Validation | A structural/formatting check that reports pass/fail. Does not test semantics. |
| Test | A genuine positive or adversarial test that exercises behavior. |
| QA pass | An adversarial evaluation by a distinct model with read-only source access. |
| Implementation generation | One distinct commit-producing pass by an implementer or remediator. |
| Candidate SHA | The full 40-character SHA of the commit to be reviewed and merged. |
| Evidence manifest | A machine-readable record of all evidence for a delivery decision. |
| Publication SHA | The full 40-character main SHA after merging a candidate. |
| Trusted runner | A CI runner whose provenance is verifiable through GitHub APIs and/or signed attestations. |

## State machine

The delivery state machine is defined in `governance/state-machine.json`. Key states:

- All work starts as `UNGOVERNED_EXISTING` and must be audited.
- A candidate moves through `IMPLEMENTING → CANDIDATE_PINNED → VALIDATING + QA_RUNNING → QA_PASSED → HUMAN_REVIEW_PENDING → READY_TO_MERGE → MERGED_TO_MAIN → PUBLICATION_READY → PUBLISHED`.
- `BLOCKED`, `ABORTED`, and `ROLLED_BACK` are terminal or holding states.

## Authority model

| Role | Authority |
|------|-----------|
| Planner | Read-only; produces plans. Cannot implement, QA, remediate, approve, or publish. |
| Implementer | Modifies files in issue worktree. Cannot QA or publish. |
| Remediator | Same as implementer, for remediation. |
| Validator | Records command exit codes. Cannot approve. |
| QA | Exactly one adversarial pass per generation. Read-only source mount. |
| Human reviewer | Separate from PR author and implementation identities. |
| Publisher | Deterministic execution only after gates pass. |

## Implementation:QA pairing

Every implementation or remediation generation receives exactly one distinct adversarial QA pass. This ratio is invariant:

- One implementation pass → one QA pass with `qa_for_pass_id` matching the `implementation_pass_id`.
- One remediation pass → one new QA pass with a fresh `qa_for_pass_id`.
- Two implementations for one QA or one QA for two implementations is rejected.
- Self-review or self-QA is rejected.

## Fail-closed gates

### PR-head readiness gate

A PR candidate is ready to merge only when ALL of the following hold:

1. PR is not a draft.
2. PR title does not begin with `[WIP]`, `WIP:`, `Draft:`, `Do not merge:`, or `Checkpoint:`.
3. PR base is `main`.
4. Linked issue exists and has a canonical `status:*` label.
5. Linked issue status is not `status:blocked` or `status:checkpointed`.
6. Candidate SHA is a full 40-character SHA equal to PR head SHA.
7. Base SHA matches QA base SHA.
8. Required validations passed (exit code 0).
9. Required tests passed (exit code 0).
10. Implementation:QA pass cardinality is exactly 1:1.
11. QA used read-only source mount, no context files, no write tools observed, candidate tree unchanged.
12. QA verdict is `pass`.
13. Human approval exists, is not by PR author, not by implementation identity, and is after the candidate SHA.
14. All workflow action refs are pinned to full SHAs.

### Publication gate

Publication requires ALL of the following:

1. PR merged to main via squash/rebase.
2. `merge_result_sha` recorded.
3. Post-merge validation and tests pass against main.
4. `publication_sha` is the full 40-char main SHA.
5. Trusted runner provenance verified (GitHub artifact attestation or authenticated API).
6. Independent human approval exists.
7. No branch-name publication: only full SHAs.

### Branch-name publication

Publication using a branch name (e.g., `main`, `latest`) is always forbidden. Only full 40-character SHAs may be published.

## Evidence manifest

Every governed delivery produces an evidence manifest at `.governance/runs/<run_id>/manifest.json`. The schema is defined in `governance/schemas/evidence-manifest.schema.json`.

QA evidence is represented as `qa.records[]`, not as a single prose report. Each implementation/remediation pass ID must have exactly one QA record with distinct implementation and QA identities, matching candidate/base/tree bindings, a protected READY probe record hash, and a protected QA execution record hash. The canonical manifest digest is `sha256(canonical_json(manifest_without_/policy/runner_attestation/artifact/manifest_sha256))`; no other fields are removed during hashing.

### Authoritative provenance

Authoritative mode requires:

1. Protected policy ref exists and is independently protected.
2. Delivery gate runs from protected policy checkout.
3. Candidate checkout is separate from policy checkout.
4. Runner provenance verified through GitHub API and/or signed artifact attestations.
5. Artifact digest and canonical manifest digest verified.
6. Protected QA execution record generated outside QA/model control.
7. Probe and QA execution records match.
8. Branch protection requires the governance checks.
9. Independent human reviewer approval exists after candidate SHA.

### Bootstrap advisory mode

Before authoritative conditions exist:

- Manifests are advisory only.
- `policy.trusted_runner` must be `false` unless a captured GitHub API or signed artifact-attestation payload verifies the run, job, artifact digest, candidate SHA, protected policy SHA, and separate checkouts.
- Local validation/tests may produce diagnostics.
- Publication, deployment, tagging, and merge-readiness remain `BLOCKED`.
- Branch-name publication is always forbidden.
- The existing-work freeze in `governance/audits/existing-work-freeze.json` blocks publication until an actual audit artifact is completed and reviewed.

## Model profiles

Model profiles are defined in `governance/model-profiles.json`. Each role maps to a verified model. Models not in the profile or in the disallowed list are rejected.

## Command registry

Commands are registered in `governance/command-registry.json`. Only registered commands can satisfy validation, test, or gate requirements. `validate_repo.py` is always a validation, never a test. Model prose saying "tests passed" is ignored.

## Issue status

Issue status is managed through canonical machine-readable labels following the `status:<value>` pattern. Prose comments cannot override labels. Issues with `status:blocked` or `status:checkpointed` cannot be closed.

## Workflow requirements

GitHub Actions workflows must:

- Use pinned full-SHA action refs (never mutable tags like `@v4`, `@v5`).
- Run delivery gate from protected policy code.
- Run validation and genuine tests separately.
- Run post-merge validation on `push` to `main`.
- Use minimal read permissions.

## Rollback

Revert a governance correction commit with a normal reviewed PR. Keep feature-publication freeze active until a replacement gate exists. Do not weaken branch protection except through independently approved governance rollback.
