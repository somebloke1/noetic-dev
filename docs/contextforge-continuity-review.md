# Adversarial review: ContextForge continuity inventory

**Issue:** [#14](https://github.com/somebloke1/noetic-dev/issues/14)

**Pairing:** one research implementation → exactly one adversarial completeness pass

## Verdict

**PASS WITH RECORDED SECURITY/OPERABILITY FOLLOW-UPS. CONTEXTFORGE MUST REMAIN OPERATIONAL.**

The review independently re-enumerated live client attachments, user unit files, project/cache state, credential-file modes/key names, and changed paths. It identified one documentation weakness during the pass: the structured migration gate named caches and project state but did not explicitly require discovery of **hidden consumers**. The same pass amended the gate and rechecked it. No completeness blocker remains for the inventory; CF-001–CF-005 remain real follow-up risks, not waived findings.

## Adversarial vectors

| Vector | Challenge | Judgment |
|---|---|---|
| Current consumers | Parsed current Pi/OpenCode configs without printing Authorization values and compared six ContextForge attachments in each. | Complete for configured entries. Pi Serena is correctly recorded as direct/local. |
| Hidden consumers | Enumerated all ContextForge user unit files, seven project-Serena units, Pi cache aliases, noetic-pi project state, and development harness. | Static config cannot prove no external consumer; inventory therefore forbids “unused” cleanup and now explicitly gates on hidden-consumer discovery. |
| Credential boundary | Checked only file modes, ignored/tracked status, key names, and nonempty booleans. | CF-001 confirmed: ignored web-search env is 0664 with secret-named values. No value was emitted. Separate governed remediation required. |
| Shared blast radius | Compared Pi/OpenCode service sets with the one host gateway and bridge topology. | CF-005 high: gateway failure removes six families in both clients; direct Serena is not a substitute. |
| Stale configuration | Compared current Pi config with richer cache aliases and inspected noetic-pi `drift=unknown`. | Cache/project state cannot authorize cleanup or prove current attachment. Live config/readback wins. |
| Surface confusion | Compared host 4444/systemd with Docker 4445/sidecars. | Distinct authority/evidence surfaces; no silent fallback permitted. |
| False migration assumptions | Searched continuity invariants/gates for parity, client-visible fixtures, authority, hidden fallback, failure injection, and tested rollback. | Migration is not authorized by architectural demotion or by presence of a candidate direct path. |
| No-mutation claim | Enumerated this worktree's changed paths and rechecked gateway active state. | Only docs/spec/validator/CI paths changed; no service/config/runtime mutation occurred. |

## Findings disposition

- **CF-001 high:** credential-file permissions — create separate security remediation; do not print/rotate values implicitly.
- **CF-002 medium:** dirty/ahead operational checkout — capture provenance before rebuild/migration claims; never clean as inventory side effect.
- **CF-003 medium:** stale aliases/unknown drift — reconcile only with current config plus client-visible proof.
- **CF-004 medium:** GitHub bridge historical restarts — investigate bounded cause; current HTTP 200 activity prevents false present-failure claim.
- **CF-005 high:** shared gateway blast radius — require per-edge parity, failure injection, and rollback before any attachment change.

No finding authorizes decommissioning, restarting, chmod, config rewrite, token rotation, service registration, or migration in this PR.
