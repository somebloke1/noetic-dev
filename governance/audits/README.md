# Governance Audits

This directory stores audit artifacts for existing ungoverned work.

## Audit naming convention

```text
governance/audits/<YYYYMMDD>-<topic>/
```

## Current freeze state

- `existing-work-freeze.json` is complete.
- `20260718-d2-portfolio/` covers the 12 open PRs, 26 branches, and 20 open
  issues captured at `2026-07-18T23:20:48Z`.
- The owner authorized one bounded D2 reconciliation PR. Publication remains
  blocked by the distinct release-trust requirements in `bootstrap-status.json`,
  not by the completed existing-work audit.

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
