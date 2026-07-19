# Governance Audits

This directory stores audit artifacts for existing ungoverned work.

## Audit naming convention

```text
governance/audits/<YYYYMMDD>-<topic>/
```

## Current freeze state

- `existing-work-freeze.json` is `repair_authorized`: the candidate capture and
  exact-candidate review still await an independently verified protected receipt.
- `20260718-d2-portfolio/` derives 13 open PRs, 26 branches, and 20 open issues
  from digest-bound candidate-authenticated GraphQL response envelopes.
- The owner authorized exactly one bounded D2 reconciliation PR. The exception
  permits that PR only; publication remains blocked by both pending audit review
  and the distinct release-trust requirements in `bootstrap-status.json`.

## Audit procedure

1. Capture bounded PR, branch, and issue GraphQL connections using authenticated
   `gh` CLI requests.
2. Bind raw response bodies, canonical responses, request identity, pagination,
   repository identity, and chronology with SHA-256 digests.
3. For each PR/branch, decide explicitly: close, rebase, cherry-pick, recreate, or abandon.
4. Store compressed response bodies, derived projections, summary markdown, and decisions.
5. Set `existing-work-freeze.json` to `complete` only after a separately protected
   verifier validates the receipt claims and exact-candidate review.

## Tools

```bash
gh pr list --state open --json number,title,headRefName,baseRefName,headRefOid,isDraft,reviewDecision,statusCheckRollup,closingIssuesReferences
gh issue list --state all --json number,title,state,labels
git log --graph --oneline --decorate --all
```
