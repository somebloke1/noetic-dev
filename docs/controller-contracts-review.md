# Adversarial review: controller v0 contracts

**Issue:** [#6](https://github.com/somebloke1/noetic-dev/issues/6)

**Pairing:** one implementation generation → exactly one adversarial QA pass

**Scope:** contracts, examples, dependency-free validation, and CI only; no runtime effects

## Verdict

**PASS FOR V0 CONTRACT REVIEW; NOT AUTHORIZATION TO IMPLEMENT EFFECTS.**

The independent pass re-derived the required invariants from the artifacts rather than trusting the primary validator. It identified one privacy hardening gap: mixed-case payload keys could evade a lowercase deny pattern. The same QA pass required lower-snake-case payload keys, rechecked the attack, and closed the finding. No blocker remains. Stage A must still enforce behavioral properties in the reducer/store; these schemas do not claim runtime proof.

## Evidence and attack vectors

| Vector | Adversarial check | Result |
|---|---|---|
| Authority gaps | Evaluated the complete actor × command Cartesian product; required each cell to occur in exactly one of allow/deny; challenged adapter, implementation-agent, QA-agent, and controller privilege boundaries. | Pass: coverage is complete and disjoint; adapter is receipt-only; implementation cannot self-adjudicate; QA cannot publish or schedule; delegation is explicitly attenuation-only and denial emits no transition. |
| Transition completeness | Compared command/event aggregate enums with tables; independently checked unique `(state,event)` reducer keys, declared states, terminal monotonicity, nonterminal exits, and reachability. | Pass: Run, Node, Attempt, Gate, Interaction, Publication, and Effect are covered; every state is reachable and no terminal state has an exit. |
| Schema drift | Compared schema versions, actor/command/aggregate enums, authority commands, strict roots, and required causation fields. | Pass: controller v0 identifiers and cross-artifact vocabularies agree. |
| Privacy | Mutated a valid event once for every prohibited key family at the payload root and nested under a benign wrapper, then challenged mixed-case key variants. | Pass after one in-pass remediation: payload names are constrained to lower snake case before deny-pattern evaluation; the recursive dependency-free check detects nested names; Stage A retains encoded/obfuscated-value redaction tests. |
| Implementation:QA cardinality | Inspected the program-schema conditional for both implementation and remediation, then checked the pinned policy and valid graph. | Pass at contract level: those kinds require verification and the policy is `exactly_one_per_implementation_generation`; storage/replay cardinality remains a Stage A property. |
| Graph/barrier safety | Validated positive graph semantics and required the negative cycle fixture to fail for its declared reason. | Pass: control graph is acyclic, each node belongs to exactly one matching barrier, and backward barrier dependencies are rejected. |
| Runtime-neutrality | Enumerated every changed path and rejected changes outside `.github/`, `docs/`, `scripts/`, and `spec/`. | Pass: no database, network, agent, git-effect, ContextForge, LiteLLM, tmux, PTY, or browser implementation was introduced. |

The paired QA command also ran the validator under `python3 -O` so contract checks cannot disappear through optimized-away `assert` statements.

## Deliberate v0 boundaries

1. Command payloads remain generic until command-specific schemas are introduced before their corresponding effect adapter.
2. The dependency-free validator checks the UTC RFC 3339 form used by fixtures, not every legal date-time variant.
3. Quorum parameters and bounded-loop constructs are not yet represented; unsupported forms fail validation rather than receiving implicit semantics.
4. JSON Schema blocks sensitive field names at the event payload root; recursive and encoded-value defenses remain mandatory reducer/ingress tests.
5. Exact QA cardinality, expected-version races, idempotency, fencing, and atomic event/outbox intent require executable Stage A model/property tests.
6. Publication-specific expected workspace/base/head/remote revisions must be defined in the command-specific publication contract before repository adapter work.

These are explicit stage boundaries, not silent waivers. Any proposal to broaden authority, weaken exact QA pairing, introduce runtime effects, or bypass versioned contracts requires a new issue and a new implementation:QA pair.
