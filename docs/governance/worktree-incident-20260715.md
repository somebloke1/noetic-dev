# Worktree administration incident: 2026-07-15

## Verified facts

An archive-export test inherited a live linked-worktree `GIT_DIR`, set a temporary
`GIT_WORK_TREE` and alternate index, then ran nested tests that invoked `git init`
and repository-local `git config`. Git persisted the temporary worktree path,
fixture identity, and executable filter in the shared common config. Three later
archive exports and two restored/synchronized copies also carried `.git` files
pointing to the same linked-worktree administration directory.

This created split-brain behavior: Git discovered from physical `main` used the
primary `main` index against a temporary export, while Git discovered from any
copied pointer used one shared feature-branch HEAD and index against distinct
physical trees. The canonical linked-worktree pointer and backlink remained
reciprocal; `git worktree repair` was therefore neither needed nor appropriate.

## Correction

The correction used a quiescent maintenance window, repeated stable baselines, a
complete isolated-restore-checked recovery archive, exact removal of four
contaminated config records, and quarantine-by-rename of five copied pointers.
Refs, reflogs, HEADs, index semantics and final bytes, registered worktrees,
tracked/dirty/untracked/ignored files, and the alternate synthetic index were
preserved. Protected history was not rewritten. An independent non-mutating QA
pass contemporaneously reported unchanged topology and archive-restore checks.

The archive and detailed verification output remain host-local under
`/home/dgk/noetic-dev-recovery-20260720T005900Z` and
`/home/dgk/noetic-dev-recovery-20260720T011121Z`; they are not tracked by this
repository or attached to this PR. A future clone therefore cannot independently
replay those checks from this document. The following names and hashes are audit
locators for the contemporaneous host-local evidence, not a durable attestation.

The host-local correction archive is
`noetic-dev-live-state.tar` with SHA-256
`3e0a67a6bf357c346e48fc9356f3997464d3dc51d08cc8f18e46f96f6e8dfd0e`.
The contemporaneously recorded final primary and issue-29 index SHA-256 values are
`229db10e268f6df8e0300818483e2cca235fc2783cce439f416e4e4f0abee46f`
and `5348f7659cff9e68fe4faf1db39ac1f38a7b12ea80c26d66565e4f1053a87028`.
The five noncanonical pointers were preserved under the quarantine suffix
`.git.noetic-quarantine-20260720T005900Z` rather than deleted.
That suffix records `2026-07-20T00:59:00Z` in UTC, which was still July 19 on
the host's local calendar; it records the completed correction, not a future
planned action.

## Preventive rule

Temporary candidate materialization must be a neutral standalone repository or a
real registered worktree. Never copy a `.git` file, attach an archive export to
live worktree administration, or run nested Git tests with inherited `GIT_*`
topology/config variables. Run `scripts/governance/check_worktree.py` before work.

Worktrees are transient delivery resources, not storage. Once adversarial QA
accepts a generation, commit and push it, complete the PR and protected review,
merge it, and remove the worktree immediately. Incomplete work is represented by
an issue and explicit blocker, not by an indefinitely retained finished worktree.
