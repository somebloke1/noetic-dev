# Adversarial completeness review: controller donor inventory

**Reviewed artifact:** `docs/controller-donor-conformance-inventory.md`

## Verdict

**PASS WITH GAPS EXPLICITLY PROMOTED TO M0 WORK.** The inventory covers the strongest donor families and distinguishes preservation from improvement and negative fixtures. It avoids treating test volume as correctness. The gaps below must appear in #6/#8 or later M0 acceptance criteria.

## Coverage review

| Vector | Covered fixture families | Judgment |
|---|---|---|
| transition safety | TR-01..08 | strong; atomicity/version races are correctly new gaps |
| scheduling | SC-01..07 | strong; quorum and DAG legibility are new |
| QA/remediation | QA-01..09 | strong; exact cardinality must be newly enforced |
| workspace/publication | WS-01..09 | strong; remote races need stronger fixtures |
| recovery/liveness | RC-01..08 | strong; crash-boundary and stale-fence properties are new |
| variants | OR-01..06 | adequate for M0 |
| cognitive programs | CP-01..06 | broad; semantic quality itself remains intentionally outside deterministic fixtures |
| events/authority/privacy | EV-01..07 | donor evidence weak; gaps correctly explicit |
| runtime attach | AD-01..04 | enough to protect kernel portability |

## Binding completeness findings

### C1. Add randomized interleaving seeds

Example fixtures alone will miss races. Stage A/B tests must generate duplicate commands, shuffled ready nodes, stale expected versions, effect retries, and crash points. Persist failing seeds.

### C2. Add negative authority fixtures before adapters

The donor largely validates role/phase, not a full authority lattice. #6 must enumerate denied actor×command cells before any real runtime adapter can dispatch.

### C3. Define evidence equivalence for donor comparison

Shadow parity cannot require byte-identical events because noetic-dev intentionally changes structure. Define equivalence at invariant level: accepted/rejected command, causal settlement, artifact digest, QA outcome, and successor eligibility.

### C4. Separate diagnostic continuity from domain correctness

Donor snapshot/status/diagnose tests are useful, but should not force noetic-dev to preserve redundant truth planes. Port only explanation obligations and causal links, not donor payload shape.

### C5. Add public-repository threat fixtures

The repository is now public. M0 security tests must cover untrusted PR payloads, Actions permissions, secret absence, path traversal, malicious artifact names, and event redaction. Do not run untrusted PR code with write tokens.

### C6. ContextForge parity requires a live dependency inventory

EV-05 cannot be authored solely from controller donors. Issue #14 must provide current consumers, transforms, auth, and failure modes before sink parity is complete. No decommission action is authorized.

## Sampling verification

The review sampled exact donor tests across:

- implementation transition/composition/recovery/containment suites;
- orchestration runtime, variant workspace, git workspace, case history, and corrective-package integration;
- state-machine graph/source/handler correspondence;
- plan, phronesis, EP audit, and succession ideal-conformance suites;
- pi2 state-machine, census, tmux, prompt bootstrap, and succession flow.

Pinned counts are evidence of inventory scale only: noetic-pi-docker has 101 APM test files / 2,261 test cases at the frozen commit; pi2 has 25 / 458. Counts do not establish adequacy.

## Required downstream links

- #6 consumes TR, SC, QA, RC, EV authority/idempotency fixtures.
- #8 consumes EV privacy/schema/sink fixtures.
- #9 consumes Telos authority/delegation fixtures.
- #10 consumes model reproducibility evidence.
- #11 consumes CP fixtures.
- #12 consumes EV-07 and graph legibility obligations.
- #13 consumes AD fixtures.
- #14 supplies ContextForge dependency evidence for EV-05.

No implementation should claim donor parity until each selected fixture records provenance, expected divergence, and adversarial QA evidence.
