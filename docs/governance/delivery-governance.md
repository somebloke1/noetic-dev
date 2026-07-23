# Delivery Governance

## Purpose

Define the machine-readable delivery vocabulary, state/authority transitions, model profiles, command registry, issue status, evidence manifest contract, and fail-closed gates that govern noetic-dev's publication pipeline.

## Scope

All changes first integrate through protected `dev`. Promotion from exact `dev` to
protected `main` requires explicit repository-owner authorization and the stronger
release governance pipeline. This document is the authoritative specification;
the JSON policy files under `governance/` are the machine-readable enforcement.

## Vocabulary

| Term | Definition |
|------|------------|
| Validation | A structural/formatting check that reports pass/fail. Does not test semantics. |
| Test | A genuine positive or adversarial test that exercises behavior. |
| QA pass | An adversarial evaluation by a distinct model with read-only source access and, until a credential broker exists, no Pi tools. |
| Implementation generation | One distinct commit-producing pass by an implementer or remediator. |
| Candidate SHA | The full 40-character SHA of the commit to be reviewed and merged. |
| Evidence manifest | A machine-readable record of all evidence for a delivery decision. |
| Publication SHA | The full 40-character main SHA after merging a candidate. |
| Trusted runner | A runner whose provenance is verified from authenticated GitHub API captures and an independently verified protected-integration receipt outside the candidate manifest. |
| External protected evidence | Runner-captured GitHub, approval, freeze, and post-merge evidence supplied by a separately protected required integration; caller-supplied JSON is advisory during bootstrap. |

## State machine

The delivery state machine is defined in `governance/state-machine.json`. Key states:

- All work starts as `UNGOVERNED_EXISTING` and must be audited.
- A feature candidate moves through `IMPLEMENTING → CANDIDATE_PINNED → VALIDATING + QA_RUNNING → QA_PASSED → INDEPENDENT_REVIEW_PENDING → READY_TO_INTEGRATE_DEV → MERGED_TO_DEV → POST_DEV_VALIDATING`.
- Validated `dev` work then waits at `MAIN_PROMOTION_PENDING`. Only the repository owner may move an exact dev SHA to `MAIN_PROMOTION_AUTHORIZED`; the promotion candidate repeats pinning, validation, paired QA, and independent review before `READY_TO_MERGE → MERGED_TO_MAIN → PUBLICATION_READY → PUBLISHED`.
- `BLOCKED`, `ABORTED`, and `ROLLED_BACK` are terminal or holding states.

## Authority model

| Role | Authority |
|------|-----------|
| Planner | Read-only; produces plans. Cannot implement, QA, remediate, approve, or publish. |
| Implementer | Modifies files in issue worktree. Cannot QA or publish. |
| Remediator | Same as implementer, for remediation. |
| Validator | Records command exit codes. Cannot approve. |
| QA | Exactly one adversarial pass per generation. Read-only source mount; no tools until a credential broker exists. |
| Independent reviewer | Fable or Sol through LiteLLM at high reasoning, separate from PR author, implementation, and QA identities. |
| Publisher | Deterministic execution only after gates pass. |
| Owner | Human repository owner; exclusively authorizes an exact dev SHA for promotion to main. |

## Implementation:QA pairing

Every implementation or remediation generation receives exactly one distinct adversarial QA pass. This ratio is invariant:

- One implementation pass → one QA pass with `qa_for_pass_id` matching the `implementation_pass_id`.
- One remediation pass → one new QA pass with a fresh `qa_for_pass_id`.
- Two implementations for one QA or one QA for two implementations is rejected.
- Self-review or self-QA is rejected.

## Fail-closed gates

### Protected dev integration gate

A feature candidate may integrate to `dev` only when its linked issue is active,
its PR targets current protected `dev`, the required ruleset checks pass against
the exact head SHA, all review threads are resolved, exactly one independent
adversarial QA pass exists for each implementation/remediation generation, and
the independent reviewer accepts the final candidate. Integration is squash-only.
This gate establishes integration evidence, not release or publication authority.
The executable mode is `--gate-mode dev-integration`; it requires `dev` consistently
in the manifest and protected provenance and never requires owner promotion evidence.

### Main-promotion readiness gate

A PR candidate is ready to merge only when ALL of the following hold:

1. PR is not a draft.
2. PR title does not begin with `[WIP]`, `WIP:`, `Draft:`, `Do not merge:`, or `Checkpoint:`.
3. PR base is `main`, the promotion head is the exact owner-authorized `dev` SHA,
   and that SHA passed protected post-integration validation on `dev`.
4. Linked issue exists and has a canonical `status:*` label.
5. Linked issue status is not `status:blocked` or `status:checkpointed`.
6. Candidate SHA is a full 40-character SHA equal to PR head SHA.
7. Base SHA matches QA base SHA.
8. Required validations passed (exit code 0).
9. Required tests passed (exit code 0).
10. Implementation:QA pass cardinality is exactly 1:1.
11. QA used read-only source mount, no context files, no tools before a credential broker exists, candidate tree unchanged.
12. QA verdict is `pass`.
13. External protected high-reasoning Fable or Sol approval evidence exists, is not by PR author or implementation/QA identity, is after candidate pinning, and is for exactly the final candidate SHA.
14. External protected runner provenance binds repository, workflow, run/job, artifact digest, manifest digest, policy SHA, candidate SHA, and separate checkouts, and is captured by a separately protected required integration.
15. All workflow action refs are pinned to full SHAs, and docker/action, job container, and service images are pinned by immutable digests.

The owner authorization is not a manifest boolean. Protected external evidence
must bind repository owner `somebloke1`, an exact issue #32 comment, protected-dev
validation SHA/time, authenticated GitHub comment ID/source, author and `OWNER`
association, exact affirmative body naming both the authorized dev SHA and expected
old main SHA, comment creation time, and the exact dev SHA.
Those fields must derive from a canonical-digest-bound authenticated GitHub
`issues/comments/<id>` response envelope captured strictly after comment creation
and before candidate pinning; duplicated caller fields cannot substitute for it.
The same protected authorization record fixes the operation to
`fast-forward`, source `refs/heads/dev`, target `refs/heads/main`, and an expected
old main SHA identical to the reviewed promotion base plus an expected main SHA
identical to the authorized dev SHA before any ref update is attempted.
Authorization must strictly follow dev validation and strictly precede
main-promotion candidate pinning. The executable mode is `--gate-mode main-promotion`.
The protected integration captures authenticated branch, applied-rules, ruleset,
and validation-run API response envelopes after authorization and before pinning.
Their response digests and derived claims are bound into a strict
`protected_attestation_receipt`. The repository gate never trusts a receipt
`verified` flag: it sends the receipt and independently recomputed expected claims
as canonical JSON to the fixed
`/usr/local/libexec/noetic-dev/verify-delivery-attestation` verifier. Every path
component and the executable must be root-owned and non-writable by group/other;
missing, unsafe, oversized, timed-out, failed, or nonzero verification blocks the
gate. The verifier is a separately deployed protected-integration dependency and
must verify the receipt proof, issuer/key, validity interval, and exact expected
claims before returning zero. Its absence remains an explicit bootstrap blocker.
After every promotion-PR check passes, the root-owned protected publisher at
`/usr/local/libexec/noetic-dev/promote-main` executes the registered
`main.promote_exact` operation as root only. It independently verifies the protected owner
authorization receipt, clean exact-dev checkout, fixed canonical remote,
current remote
heads, and strict fast-forward ancestry before invoking the fixed
`/usr/bin/git push --porcelain` executable with
`--force-with-lease=refs/heads/main:<expected-old-main-sha>` and the exact
`<authorized-dev-sha>:refs/heads/main` refspec. The lease supplies compare-and-swap
semantics; the authenticated post-main run, compare, and branch responses prove
that the result was a fast-forward to that same SHA. A squash, rebase, merge commit,
wrong lease, wrong source/target, nonzero command, or missing command record blocks
the `MERGED_TO_MAIN` transition and publication. Its structured execution record is
digest-bound into the protected integration attestation; manifest-provided command
hashes alone are never accepted as proof that the push occurred.
`deploy/install-main-publisher.sh` is the source for the fixed root-owned stage-0
installer `/usr/local/sbin/noetic-dev-install-main-publisher`; a candidate checkout
must never be executed directly as root. The stage-0 executable must itself be
installed from a separately protected policy SHA before use. It rejects every
other invocation path and requires direct privileged Bash mode (`/usr/bin/bash -p`),
whose absolute interpreter and privileged startup ignore `PATH` and `BASH_ENV`
injection before script checks. It fetches the canonical repository's full current protected
`dev` history into a fresh bare repository, requires the requested candidate to be
the exact current `dev` head, and requires the pinned policy SHA to be a distinct
ancestor of that candidate. It archive-extracts only the policy SHA. Candidate
bytes are never installed or executed by the publisher.

Before installation, the fixed root-protected attestation verifier validates a
signed `install-main-publisher` authorization receipt. Its expected claims bind
the repository and protected source ref; policy and candidate commit/tree SHAs;
the stage-0 installer path and digest; verifier path and digest; and digests of the
launcher, publisher, delivery gate, and every direct policy dependency. Every path
component from the installer, verifier, key, and installed files through `/` is
checked with non-dereferencing metadata and must be root-owned, non-symlink, and
non-writable by group or other. Existing and absent publisher-root ancestors are
validated non-dereferentially before every directory creation, release move, or
launcher installation. The executable leaves must also be regular and
executable. A candidate-controlled digest, same policy/candidate SHA, non-ancestor
policy, mixed release, or invalid receipt blocks before installation.

The installer reconstructs the policy commit's exact Git tree, rejects all
symlinks, and stores the protected policy at
`/opt/noetic-dev-main-publisher/policy-releases/<policy-sha>/<candidate-sha>` with
the exact Git archive under `repository/` and the authorization receipt and
canonical installation manifest outside that tree. It then installs
the policy launcher mode `0700` and atomically selects that policy/candidate pair.
At every invocation the launcher accepts only this two-SHA release shape, starts
isolated Python with an empty environment, and supplies the fixed installation
manifest path itself. The protected publisher reconstructs and compares the complete
receipt-bound Git policy tree, then re-hashes the stage-0 installer, verifier,
fixed launcher, policy entrypoint, gate, and direct dependencies; proves
the manifest candidate equals the promotion candidate; and re-verifies the stored
authorization receipt before running any candidate-supplied gate inputs. It never
accepts an installation path, SSH key path, or agent socket from its caller.

This candidate cannot serve as its own protected policy release. The corrected
publisher must first land on protected `dev`, then a distinct protected successor
candidate may use that earlier SHA as policy. Until that bootstrap and receipt
exist, exact-SHA main promotion remains blocked. This deployment does not
establish the separate attestation verifier or publication authority by itself.
The separately provisioned
`/etc/noetic-dev/main-publisher/deploy-key` must be a nonempty root-owned regular
file with mode `0400`; every parent is root-owned, non-symlink, and non-writable by
group or other. The installer and publisher derive its public half noninteractively
with fixed `/usr/bin/ssh-keygen`. Fetch and push disable SSH agents and default
identities and use only that fixed key. Its OpenSSH SHA-256 fingerprint and DeployKey
ID must equal the independently attested, write-enabled publisher capability and are
recorded in execution evidence.
Replacement objects are disabled and the extracted archive must reconstruct the
protected policy commit's exact tree. Every symlink is rejected before installation, and
both publisher entrypoints must be regular files, so immutable-tree verification
cannot be converted into mutable external content by later dereference. The
publisher rejects hidden index flags and unsafe
local Git configuration, then fetches and pushes only the fixed canonical SSH URL
from a fresh temporary bare repository under an isolated Git/SSH environment.
Before touching any remote ref, the publisher must derive a passing complete
`main-promotion` pre-merge delivery gate, not merely validate owner authorization.
It also requires an independently verified protected capability receipt binding
the exact candidate/base SHAs to a specific write-enabled DeployKey ID and SSH fingerprint
that live branch-protection evidence authorizes to bypass the PR and required-check
barriers for this fast-forward without permitting force pushes. Current live
`main` protection has no such actor, so the operation remains an explicit bootstrap
blocker; installing the launcher does not make promotion executable or weaken
protection.

### Publication gate

Publication requires ALL of the following:

1. Protected main is fast-forwarded to the exact owner-authorized, validated dev SHA; squash, rebase, and merge commits are forbidden.
2. `merge_result_sha` recorded.
3. Post-merge validation and tests pass against main.
4. `publication_sha` is the full 40-char main SHA.
5. Trusted runner provenance verified from authenticated API captures and an independently verified protected-integration receipt, not from manifest assertions.
6. Independent high-reasoning Fable or Sol approval exists in external protected evidence.
7. Protected post-merge push-to-main evidence binds the command outputs to the main SHA and merge method.
8. The protected existing-work freeze artifact is complete; the manifest cannot override it.
9. No branch-name publication: only full SHAs.

Post-main evidence is not a method/SHA assertion. It consists of authenticated,
canonical-digest-bound GitHub API envelopes for the successful Governance `push`
run on `main`, the protected `main` branch readback, and the comparison from the
pre-promotion main base to the candidate. Publication derives the exact SHA from
those response bodies and accepts fast-forward only when the old main SHA is the
merge base, the candidate is strictly ahead and not behind, and protected main
equals that candidate after the successful run. The complete post-main evidence
digest is a required protected-receipt claim, so pre-merge receipts cannot be
replayed for publication.

Freeze completion additionally requires protected external review evidence whose
audit digest matches `existing-work-freeze.json`, whose verdict is `pass`, and
whose reviewed candidate SHA and evidence URL are explicit. A locally asserted
`complete` value or caller-controlled manifest cannot satisfy this gate.
The complete freeze artifact must record the same exact review-comment URL and
review time; publication compares both to the protected evidence and requires the
review time to follow inventory capture.
Protected freeze-review evidence also authenticates the GitHub PR number, exact
head/base refs, head SHA, and sole linked issue #32; matching caller assertions
without those GitHub API bindings are rejected.
The protected integration must retain an authenticated GitHub PR API response
envelope with request URL/status/ID, capture time, protected principal, canonical
response digest, and normalized response body. Review fields are derived from that
body, and the envelope digest is an explicit protected-receipt claim.
The protected artifact and protected-receipt claim digest include owner promotion
authorization and freeze-review objects, so either object is substitution-evident.
The roadmap may checkpoint D2 and remove conflict C2 only when the completed freeze
hash-binds `governance/audits/d2-protected-freeze-review.json`. That artifact must
derive the reviewed candidate from an authenticated PR response, derive the exact
integration SHA from a later authenticated protected-`dev` branch response, include
that integration SHA in D2 commit evidence, and pass the fixed protected receipt
verifier. Local freeze, roadmap, evidence-list, or digest edits alone cannot advance
the transition.
Because a Git-tracked inventory necessarily records the remote PR head before its
own successor is pushed, protected completion must also embed an authenticated
GitHub comparison proving that exact inventory head is an ancestor of the reviewed
candidate. The protected receipt binds the audit digest, both candidate SHAs, and
the comparison-envelope digest; an unrelated or rewritten snapshot is rejected.
While the freeze is `repair_authorized`, `dev-integration` admits only issue #32,
PR #67, branch `issue-32-canonical-roadmap` targeting `dev`, with exactly the sole
linked issue #32. Active freeze state blocks every dev integration; main promotion
remains blocked until the freeze is complete. A `complete` value lifts restrictions
in neither gate mode unless the schema-valid local freeze derives the independently
verified protected D2 review and exact protected-dev integration evidence.

### Branch-name publication

Publication using a branch name (e.g., `main`, `latest`) is always forbidden. Only full 40-character SHAs may be published.

## Evidence manifest

Every governed candidate produces an evidence manifest at `.governance/runs/<run_id>/manifest.json`; `dev-integration` binds its base and provenance to protected `dev`, while `main-promotion` binds them to protected `main` and additionally requires exact owner authorization. The schema is defined in `governance/schemas/evidence-manifest.schema.json`. A dev-integration manifest establishes integration evidence only, not release authority.

QA evidence is represented as `qa.records[]`, not as a single prose report. Each implementation/remediation pass ID must have exactly one QA record with distinct implementation and QA identities, matching that generation's candidate/base/tree bindings, a protected READY probe record hash, and a protected QA execution record hash. Earlier generations may bind to earlier candidate SHAs; the final pass must bind to `repo.candidate_sha`. The canonical manifest digest is `sha256(canonical_json(manifest_without_/policy/runner_attestation/artifact/manifest_sha256))`; no other fields are removed during hashing.

### Authoritative provenance

Authoritative mode requires:

1. Protected policy ref exists and is independently protected.
2. Delivery gate runs from protected policy checkout.
3. Candidate checkout is separate from policy checkout.
4. Runner provenance verified through authenticated GitHub API captures plus the fixed protected-integration receipt verifier.
5. Artifact digest and canonical manifest digest verified.
6. Protected QA execution record generated outside QA/model control.
7. Probe and QA execution records match, with no QA tools until a credential broker exists.
8. Branch protection requires the governance checks.
9. Independent high-reasoning Fable or Sol reviewer approval exists after candidate SHA and is bound to the final candidate SHA.
10. Provider credentials cross a broker/capability boundary before tools are re-enabled for authoritative QA.

### Bootstrap advisory mode

Before authoritative conditions exist:

- Manifests are advisory only.
- `policy.trusted_runner` in a manifest is advisory only and must not be used to establish authority.
- Caller-supplied external evidence JSON is also advisory until a separately protected required integration captures or attests it and branch protection requires that integration.
- Local validation/tests may produce diagnostics.
- Publication, deployment, tagging, and merge-readiness remain `BLOCKED`.
- Branch-name publication is always forbidden.
- Candidate workflows run `dev` checks and agent review, but both are advisory until independently verified; `branch_protection_requires_governance` and `independent_agent_review_process_established` remain false in `governance/bootstrap-status.json`. The protected policy ref, trusted runner provenance, and credential broker are also unresolved.
- The D2 inventory remains review-pending. Protected external evidence must bind an independent exact-candidate review to its digest before the freeze may complete; the distinct protected trust root and post-main evidence also remain mandatory.

## Model profiles

Model profiles are defined in `governance/model-profiles.json`. Each role maps to a verified model. Models not in the profile or in the disallowed list are rejected.

## Development-system reconciliation wave

Git/GitHub coordination is part of developing noetic-dev, not a runtime feature of the developed application. Run a reconciliation wave after every branch, PR, review, check, merge, or issue-state transition, and periodically while open work remains:

1. Sol at high reasoning inventories every local worktree/branch/commit and every open GitHub issue, PR, project item, review thread, required check, and workflow run.
2. The orchestrator derives dependency order from actual base/head SHAs and linked issues. Stacked PRs are processed serially from their earliest prerequisite.
3. Fable at high reasoning reviews the next immutable PR snapshot. Sol may serve as reviewer only under a distinct reviewer role/run identity and never review its own implementation or QA work.
4. A finding produces `changes-needed` and a separate remediation generation; the changed SHA receives a fresh independent review.
5. Issue labels are authoritative lifecycle state: `ready` before work, `in_progress` while a branch/PR exists, `blocked` or `checkpointed` only with a named condition, and `done` only after verified merge/closure.
6. Project status is the coordination projection: active implementation or remediation is `In Progress`; a pushed immutable candidate awaiting checks, review, or merge is `In Review`; unstarted dependency-ready work is `Ready`; named blockers and explicit pauses are `Blocked`; only merged/closed accepted work is `Done`.
7. Actions are recorded distinctly as queued, in progress, completed-success, completed-failure, cancelled, or missing. A successful validator is never reported as tests, review, merge readiness, or publication.
8. The orchestrator updates metadata only from authoritative evidence and records every unresolved remote protection, credential, identity, or infrastructure condition without converting it into a human-action dependency.

The wave preserves all review and process gates. Delegation replaces the actor, not the requirement.

## Command registry

Commands are registered in `governance/command-registry.json`. Only registered commands can satisfy validation, test, or gate requirements. `validate_repo.py` is always a validation, never a test. Model prose saying "tests passed" is ignored.

## Issue status

Issue status is managed through canonical machine-readable labels following the `status:<value>` pattern. Prose comments cannot override labels. Issues with `status:blocked` or `status:checkpointed` cannot be closed.

## Workflow requirements

GitHub Actions workflows must:

- Use pinned full-SHA action refs (never mutable tags like `@v4`, `@v5`) and immutable docker/job-container/service image digests.
- Run repository validation and genuine tests separately.
- Treat the candidate PR workflow as advisory only; it must not claim protected delivery-gate authority or call base-policy scripts that may not exist during bootstrap.
- Establish a separate protected required workflow/repository integration before authoritative merge readiness can be claimed.
- Run post-merge validation on `push` to `main`; publication additionally requires protected post-merge evidence.
- Use minimal read permissions.

## Rollback

Revert a governance correction commit with a normal reviewed PR. Keep feature-publication freeze active until a replacement gate exists. Do not weaken branch protection except through independently approved governance rollback.
