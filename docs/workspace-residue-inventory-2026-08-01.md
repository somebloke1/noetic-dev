# Retained-residue resumability index - 2026-08-01

**Snapshot observed through:** 2026-08-01T09:47:03Z
**Historical full-source SHA-256:** `3d1cd70fccd61db2c1af7a0bb220741ced0c80a207018851cd6d1c7f49a83f5c`
**Publication status:** redacted public index

This document is the public, non-secret commitment and resumption contract for
the full local forensic inventory used by `ROADMAP.md`. The full source was
published in a consumed PR predecessor before this minimization and may remain
reachable in public Git history. Its digest binds the exact worktree paths,
branch and HEAD identities, status rows, stash parentage and subjects, additional
retained heads, repeated configuration paths, executable locations, process
observations, and system-unit observations. This current projection no longer
repeats those details but does not claim to erase their historical disclosure.

The source snapshot was independently reproduced before redaction. Redaction
changes disclosure, not ownership, reachability, QA state, or cleanup authority.
No row in the source is accepted implementation evidence merely because its
digest is committed here.

## 1. Aggregate commitments

| Inventory class | Public commitment | Required interpretation |
|---|---|---|
| Registered worktrees | 82 rows: 79 present and 3 missing registrations | Retain all. Missing registrations are not prune authorization; present rows may be clean or dirty and remain issue-owned |
| Synthesis root | 13 status rows; status-manifest SHA-256 `28b57b45407c541f02c213f00f8c927c5c59052c523541f3be72626f40418703` | Preserve the unrelated root overlay until every represented item is integrated or explicitly retained |
| Stashes | 11 identities with base/additional-parent bindings in the historical full source | Do not apply, pop, drop, rewrite, or count as integration evidence without a stash-specific issue and fresh QA |
| Additional retained heads | 12 identities in the historical full source | Retain until reachability, ownership, replacement and QA are adjudicated |
| Repeated ContextForge configuration status | 23 status rows; row-set SHA-256 `ea5fa0c00da360a4f4a542a9f828934506e081a1178dcc57467d436cded83d6e`; repeated single-row manifest SHA-256 `89b883123e5c5e55e3cb5df6f4dd83ddb8e54ece978c465b8f82fc03a0d89bbf` | Repetition is not cleanup authority and says nothing about configuration contents |
| ContextForge issue-396 frontier | 17-path dirty overlay; status-manifest SHA-256 `e8fb1c1fab8f771adc3c7ba595638b031c128fb605eab6f2058fbe6f0f6df73b`; diff SHA-256 `4e4b66ba6408df84160d4b9795073d63dade64e01dfab4f3a2f4df74ddf62fb4` | Retained unverified continuation material, not accepted noetic-dev or ContextForge evidence |
| Client/runtime observation | Versions and capability conclusions are projected in `DECISIONS.md`; local executable/config paths, process IDs and unit observations remain only in the historical full source | Point-in-time readiness evidence only; never authorization to edit user-global configuration |

Dirty-manifest digests commit to byte-sorted
`XY<TAB>relative-path<LF>` status rows, not file contents. The public index does
not disclose absolute paths, local account names, process IDs, executable paths,
configuration paths, stash subjects, or complete branch/worktree topology.

## 2. Resumption contract

Before mutating any retained item, its owning issue must independently refresh
only that item's current repository identity, reachability, remote relationship,
status manifest, authorization and implementation:QA state. The refresh becomes
a new issue-scoped record; it does not rewrite this historical snapshot.

- Dirty work resumes only in a fresh issue-linked worktree and frozen generation.
- Clean detached work resumes only after ownership and reachability adjudication.
- Missing registrations remain retained until a dedicated cleanup check proves
  that no unique evidence, process or recovery path depends on them.
- Stashes remain opaque retained objects until an owner-specific recovery issue.
- Rejected or transcriptless candidates remain non-evidence even if reachable.
- Runtime observations must be re-derived without reading credentials or private
  configuration values and receive an adapter-specific authority/cleanup gate.

## 3. Minimization and verification boundary

The historical full source may be compared against the published digest by an
authorized local operator. It must not be copied again into issues, pull
requests, logs, public artifacts or generated documentation. Reviewers can
verify the current public contract from the aggregate counts and digests above;
item-specific work can verify a narrowly disclosed opaque identity through its
owning issue.

The complete source remains recyclable operational evidence, not product
content. This index is sufficient for public governance because it preserves
tamper evidence, category counts, blockers and resumption criteria while keeping
workstation topology and runtime details private.
