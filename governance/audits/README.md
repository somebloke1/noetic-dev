# Governance Audits

This directory stores audit artifacts for existing ungoverned work.

## Audit naming convention

```text
governance/audits/<YYYYMMDD>-<topic>/
```

## Current freeze state

- `existing-work-freeze.json` is active.
- The bootstrap audit covers the ten pre-existing PRs/branches known when issue #23 began.
- Until that audit is actually completed and verified, publication remains blocked and no new PR-opening/publication claim is authoritative.

## Audit procedure

1. List open PRs, branches, and issues using `gh` CLI.
2. Record state, labels, and dependencies.
3. For each PR/branch, decide explicitly: close, rebase, cherry-pick, recreate, or abandon.
4. Store raw JSON dumps, summary markdown, and decisions.
5. Set `existing-work-freeze.json` to `complete` only after the audit artifact exists and is independently reviewed.

## Tools

```bash
gh pr list --state open --json number,title,headRefName,baseRefName,headRefOid,isDraft,reviewDecision,statusCheckRollup,closingIssuesReferences
gh issue list --state all --json number,title,state,labels
git log --graph --oneline --decorate --all
```
