## Purpose

Closes #

Relevant knowns/decisions:

## Scope

- In scope:
- Out of scope:

## P1 — Evidence attended to

## P2 — Design/insight

## Validation (not tests)

- [ ] `python3 scripts/validate_repo.py` — repository invariant validation only
- [ ] `python3 scripts/governance/check_delivery_gate.py --check-pinning-only .github/workflows` — all-workflow action/container/service digest pinning validation only
- [ ] `python3 scripts/governance/check_evidence_manifest.py <manifest>` — manifest validation only

## Genuine tests

- [ ] `python3 -m unittest discover -s tests -v` — positive and adversarial behavior tests pass
- [ ] Negative fixtures reject the intended defect, not an incidental missing prerequisite

## Implementation/QA pairing

- [ ] Candidate SHA pinned: <!-- full 40-char SHA -->
- [ ] Candidate tree OID pinned: <!-- full 40-char tree OID -->
- [ ] Each implementation/remediation pass has exactly one distinct QA record
- [ ] QA ran against the immutable candidate SHA/base/tree
- [ ] QA protected READY probe record hash: <!-- sha256 -->
- [ ] QA protected execution record hash: <!-- sha256 -->
- [ ] QA used read-only source mount, isolated scratch/home, no host credentials, and no tools until a credential broker exists

## Independent Agent Review

- [ ] Independent Sol reviewer used the closed approval profile at xhigh reasoning
- [ ] Reviewer approved after candidate SHA pinning and against exactly the final candidate SHA
- [ ] Approver is not PR author, implementer, remediator, QA, publisher, or orchestrator identity

## Merge readiness

- [ ] Required validations passed separately from tests
- [ ] Required tests passed separately from validations
- [ ] Protected policy checkout was separate from candidate checkout
- [ ] Trusted runner provenance verified from external protected evidence through GitHub API or artifact attestation
- [ ] Delivery gate passed from separately protected policy code/integration (candidate workflow and caller-supplied JSON are advisory only during bootstrap)

## Publication (post-merge only)

- [ ] Merge result SHA recorded (full 40-char main SHA)
- [ ] Post-merge validation and tests passed against main SHA
- [ ] Publication SHA recorded (full 40-char SHA; branch names forbidden)
- [ ] Existing-work freeze/audit is complete in the protected freeze artifact, or publication remains blocked
- [ ] Independent Sol/xhigh approval and trusted-runner provenance remain valid

## P4 — Responsible enactment

- [ ] No PR/publish/merge claim is made from advisory local evidence alone
- [ ] No secrets or local state included
- [ ] Rollback path stated

## Risks and rollback
