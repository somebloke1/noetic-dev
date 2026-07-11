# Cognitive program adversarial review

**Implementation:** issue #11 cognitive-program contracts

**Review count:** 1 implementation : 1 adversarial QA

| Threat | Attack | Disposition |
|---|---|---|
| Phase collapse | label a P2 formulation as P3 truth | Reject operation/phase mismatch and require evidence for P3 judgment. |
| Evidence smuggling | judge from hypothesis alone | Reject: P3 consumes evidence with provenance; artifact policy is invariant. |
| Self-authorization | program executes controller command/effect | Reject: `propose_only`, allowlisted intents, and stage effect authority `none`. |
| Unbounded loop | remediation recursively creates itself | Reject: bounded attempts/generations; exhaustion requests controller interaction. |
| Provider coupling | program pins model/vendor/URL | Reject: model request allows capabilities and policy class only. |
| Privacy leakage | inline secret or full reasoning in events | Reject: reference-only secrets and minimal attributed reports. |
| QA drift | one implementer receives zero/many or implementing QA | Reject: exact 1:1 generation cardinality, role count parity, independent non-implementing QA. |
| Telos capture | program changes objective/scope | Reject: immutable delegation/digest references; Telos remains owner. |

## Findings

1. **High — program/controller authority ambiguity. Corrected.** Propose-only authority and zero stage effect authority are now explicit and executable.
2. **High — P3 could be reached without evidence. Corrected.** Judgment stages require evidence and the artifact policy cannot be weakened.
3. **High — implementation QA could drift despite prose. Corrected.** Both invariant string and manifest role-count parity are validated.
4. **Medium — endpoint fields could leak into programs. Corrected.** Any model-request key beyond capabilities/policy class is rejected.
5. **Medium — remediation could become a blind alley. Corrected.** Bounded generation/attempt policies end in controller interaction.
6. **Medium — agent reports could be mistaken for enacted truth. Corrected.** Documentation and event class keep reports attributed and non-authoritative.

## Residual risks

Compilation from a manifest to the controller DAG, distinct actor identity for QA, provenance integrity, and semantic quality require runtime/model tests. The M0 contract does not claim these effects exist.

**Judgment:** acceptable for stacked M0 review after all validators and Governance CI pass. No runtime execution is authorized.
