## Purpose

Closes #

Relevant knowns/decisions:

## Scope

- In scope:
- Out of scope:

## P1 — Evidence attended to

## P2 — Design/insight

## Validation

- [ ] `python3 scripts/validate_repo.py` — repository invariant validation
- [ ] `python3 scripts/governance/check_delivery_gate.py --check-pinning-only .github/workflows/governance.yml` — workflow action pinning validation

## Tests

- [ ] `python3 -m unittest discover -s tests -v` — genuine positive and adversarial tests pass
- [ ] Governance tests:
  - [ ] `tests/governance/test_command_registry.py`
  - [ ] `tests/governance/test_delivery_gate.py`
  - [ ] `tests/governance/test_evidence_manifest.py`
  - [ ] `tests/governance/test_state_machine.py`
  - [ ] `tests/governance/test_workflow_pinning.py`

## QA

- [ ] One adversarial QA pass completed against pinned candidate SHA
- [ ] QA used read-only source mount, no context files, no write tools
- [ ] QA verdict: pass
- [ ] QA gated by protected execution record

## Candidate SHA

- Candidate commit SHA: <!-- full 40-char SHA -->
- Candidate tree OID: <!-- full 40-char tree OID -->

## Human approval

- [ ] Independent human reviewer approved after candidate SHA
- [ ] Approver is not PR author and not implementation identity

## P4 — Responsible enactment

- [ ] Merge-readiness gate passed
- [ ] Post-merge publication SHA recorded (after merge to main)
- [ ] Branch-name publication forbidden — only full SHA publication
- [ ] Rollback path stated
- [ ] No secrets or local state included
- [ ] Documentation/governance updated where required

## Risks and rollback
