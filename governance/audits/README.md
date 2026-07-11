# Governance Audits

This directory stores audit artifacts for existing ungoverned work.

## Audit naming convention

```text
governance/audits/<YYYYMMDD>-<topic>/
```

## Current audits

- None yet. First audit will be the governance correction bootstrap audit of existing PRs and branches.

## Audit procedure

1. List open PRs, branches, and issues using `gh` CLI.
2. Record state, labels, and dependencies.
3. For each PR/branch, decide explicitly: close, rebase, cherry-pick, recreate, or abandon.
4. Store raw JSON dumps, summary markdown, and decisions.

## Tools

```bash
gh pr list --state open --json number,title,headRefName,baseRefName,headRefOid,isDraft,reviewDecision,statusCheckRollup,closingIssuesReferences
gh issue list --state all --json number,title,state,labels
git log --graph --oneline --decorate --all
```
