# Release Requirements

Proposed bounded private Linux delivery criteria, documented 2026-09-07.
These criteria are not blanket passed tests or permission to ship. Source metadata
is now 0.3.0; accepted deployment evidence identifies installed release
`0.3.0-3428ebd027e005ef`. Bounded completed work is distinguished below from remaining
criteria. Preserve the existing controller, harness, GUI and genuine Telos
integration; no new platform or all-OS installer is required.
See [commercial readiness](commercial-readiness.md) for rights and customer scope.

## Private Artifact

Use an explicit allowlist, not a copy of the worktree:

- Versioned Python wheel with `noetic` entry point, browser assets, patterns and
  Telos bridge; unchanged [Noetic license](../LICENSE.md).
- Genuine separately bundled `telos-core.mjs`, produced from the actual factory
  by [the existing bundler](../scripts/noetic_telos.py), and its module manifest.
- Release manifest: wheel/module versions, hashes and file inventory; actual source
  revisions plus any local changes; bundle inputs and applicable notices; supported
  Linux environment and exercised Python, Node and client versions. The current
  bundler's "current source including possible uncommitted changes" identity is
  not a clean release revision or a complete dependency inventory.
- [Third-party notices](THIRD_PARTY_NOTICES.txt), including exact Telos MIT text,
  and separately owner-approved customer terms before redistribution. This file
  is not those terms and does not change Noetic's license.
- Installer/launcher and user documentation covering prerequisites, stable code,
  configuration and state paths, first launch, model-access ownership, missing
  components, maintenance, backup/restore, uninstall and support limitations.

Python and Node are customer-installed prerequisites, not bundled runtimes.
Python >=3.10 is declared; it is not a tested version matrix. Node 24 is required
for the deployed Telos module. Pi/OpenCode are customer-installed for actor work;
model services, credentials and weights are not included. Exclude runtime journals,
customer projects, local auth/configuration stores and unrelated build leftovers.
Do not inspect or copy credentials to assemble the artifact. An archive of customer
state is a separate customer operation, not part of the software release.

## Acceptance Criteria

1. **Install and first use.** On the declared clean Linux target, install only the
   selected release artifacts and prerequisites. Outside both source checkouts,
   load GUI assets and create/get a genuine Telos purpose without tsx, esbuild or
   a donor checkout. Resolve code, runs root, Telos DB and module consistently
   regardless of working directory; report unwritable paths and missing/incompatible
   prerequisites with a useful next action. Normal use needs no elevation or
   package-directory writes. Windows/macOS support is not implied.
2. **Lifecycle and recovery.** Explain closing the UI versus pausing/cancelling work.
   Demonstrate reconnect and bounded interrupted-run handling with disposable local
   fixtures. A complete saved submission reconciles idempotently without rerunning
   actors/checks; absent or invalid evidence remains uncertain, never automatic
   success or replay. Kernel cancellation is not proof every owned child stopped.
3. **Maintenance.** Stop new launches and establish actual driver/process quiescence
   before replacing code. Retain previous wheel/module versions and document an
   explicit release switch and rollback. Demonstrate a temporary N -> N+1 -> N
   journey; incompatible state changes require a pre-update snapshot and disclosed
   loss of post-snapshot changes, not merely reinstalling an older binary.
4. **Archive and restore.** At a held quiescent checkpoint, retain controller/event
   databases with receipts, options, evidence and applicable shared Telos DB. Account
   for SQLite WAL using an appropriate backup operation. Restore to a new location
   without overwriting runs or launching actors; compare retained state/evidence.
   State exclusions explicitly: customer workspace, external sessions/credentials,
   browser drafts and disposable indexes. Historical inspection is not relocated
   active-workspace continuation. Missing/corrupt required members must not look
   like an empty successful restore.
5. **Capacity and cost honesty.** State the actual admission/enforcement scope and
   show time/recurrence exposure before work. Current source and
   [harness guidance](harness-runtime.md#shared-driver-capacity) implement a default
   two-driver limit across cooperating GUI/CLI callers sharing one resolved runs
   root, not across roots or all descendants. Driver death releases a slot even
   if a descendant survives. Cross-root workspace exclusion and the earlier
   proposed one-summary/one-embedding backend limits are not established by that
   control. None of these numbers is a measured maximum.
   Native/proxy Astra labels may share upstream quotas. If cross-root or
   descendant-inclusive admission is advertised, demonstrate that scope with local
   fixtures, including unresolved owned execution. Otherwise disclose the per-root
   driver scope and operator-managed limits outside it. Report unknown cost as
   unknown, not zero; actor counts/timeouts are not
   hard request or spend caps. Configured Qwen slots do not prove throughput.
6. **External delivery decision.** Owner approves actual recipients/channel, the
   customer grant, selected-file rights and notices, supported model-access claims
   and support/exit terms. Recheck material licenses/provider terms for the actual
   release. These are suggested decisions, not enacted approvals or blockers to
   unrelated development. No public release, source push, visibility/license change,
   customer contact, billing or DRM work is authorized by this document.

## Evidence Boundary

The earlier production-release report's 0.2.0 clean-home failure (missing Telos)
is historical, not the current package assessment. Subsequent release/archive QA
accepted genuine bundled-Telos purpose creation in an isolated installed fixture,
plus bounded archive/restore and rollback checks for its fixed wheel. That is not
a fresh clean-machine acceptance of every later 0.3.0 bundle.

Later accepted deployment evidence identifies `0.3.0-3428ebd027e005ef`, an enabled
GUI service, preserved 19-run history and a recorded managed code rollback/return
exercise. Permissions migration was separately accepted. Data-recovery QA accepted
an administrative same-host offline filesystem-copy trial with byte-identical
backup/restore and read-only installed inspection, not strict archive export or
portable resumed execution. The adopted launcher still depends on the original
workspace/bound runtime existing; 57 historical ownership records remain unknown.
Code rollback does not reverse data changes. No reboot, crash/power-loss,
cross-host or off-device recovery guarantee follows from these checks.

See the [current readiness table](commercial-readiness.md#current-readiness) and
its named accepted reports for the exact scopes. The capacity report's two real
runs and timing sample remain historical evidence, not maximum throughput,
customer effort savings or verified billable costs. These repository doc updates
were not installed or inserted into the retained delivery artifact.

The three source reports are identified in [commercial readiness](commercial-readiness.md).
Their findings were not rerun in this documentation unit. Existing
[getting started](getting-started.md), [operator guidance](operator-view.md) and
[Telos guidance](telos-runs.md) are implementation context, not proof that every
criterion above passes. Release checks should remain reasoned, critical,
constructive and non-perfectionistic, confined to these concrete claims. The lead
pairs this documentation implementation with one independent QA pass; this unit
does not perform legal clearance, production QA or downstream delegation.
