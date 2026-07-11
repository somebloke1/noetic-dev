# Canonical cognitional-event contract

**Status:** M0 executable contract for [issue #8](https://github.com/somebloke1/noetic-dev/issues/8). No sink or UI implementation is authorized by this document.

## Purpose

`noetic.event/v0` is the portable event boundary shared by the deterministic controller, Telos, cognitive programs, observability projections, and future direct/ContextForge sink adapters. It records causal facts without collapsing attributed semantic reports into controller-established truth.

The central distinction is:

```text
cognition_report(P3, actor=A, assertion_scope=reported)
    means: A reported a judgment operation
    does not mean: the controller established the proposition as domain truth
```

A structural state change is authoritative only as a controller-authored `domain_transition` with enacted authority and a causal command. An effect receipt, diagnostic, observation, or semantic report cannot mutate domain state by being displayed or transported.

## Evidence harvested, not hosted

- `noetic-pi-docker/packages/server/src/event-bus.ts` proves the observability value of pushed cycle/agent events and replay, but its browser union is transport-specific, unversioned, buffered to 100 entries, and maps unknown payloads to generic notification text. It is a donor lesson, not the canonical contract.
- `noetic-pi-docker/packages/shared/src/apm-protocol/phronesis.ts` and `packages/apm/src/phronesis.ts` prove P1–P4 operation identity, recursion to prior operations, iteration/pass, and terminal recurrence limits. The canonical envelope therefore does not model P1–P4 as a mandatory one-way event lifecycle.
- `telos/scripts/lib/semantic-shared.mjs` proves multiple secret-value and credential-shape redaction requirements. The canonical event permits summaries and opaque digest-bearing references, not full prompts, secrets, private artifacts, or critical-contact data.
- `docs/cognitive-backbone.md` is authoritative for `P1–P4`, imperative glosses, P4 recursive governance, and optional `sought`/`enacted` modality.

## Contract shape

Every event has:

- immutable identity, type, class, stream position, occurred/recorded times, and producer version;
- typed subject and attributed actor;
- explicit authority reference and assertion scope;
- causation and correlation IDs;
- either a correctly paired P1–P4 cognition object or `null`;
- privacy classification and redaction status;
- bounded opaque evidence references with digest and access classification;
- a small, lower-snake-case payload that excludes sensitive key families.

### Event classes

`event-class-matrix.json` binds each class to prefixes, actors, assertion scopes, and cognition presence:

- `domain_transition` — deterministic structural truth enacted by the controller;
- `cognition_report` — attributed report of a P1–P4 operation, never domain truth by itself;
- `evidence_observation` — observed/reported evidence with references;
- `decision_request` — durable request for P3/P4 action, not an answer;
- `effect_status` — external-effect/transport observation, not a domain transition;
- `diagnostic` — non-authoritative operational projection.

## P1–P4 fidelity

The cognition object binds:

| Phase | Operation | Human imperative |
|---|---|---|
| `p1` | `attending` | be attentive |
| `p2` | `understanding` | be intelligent |
| `p3` | `judging` | be reasonable |
| `p4` | `deciding` | be responsible |

`modality=sought|enacted` carries the useful force of optional ECN `^?`/`^!`. `iteration`, `recursion_depth`, and `parent_operation_event_id` preserve recursive returns. `governing_purpose_ref` is required at every phase so P4 governance is represented without pretending every event was emitted by P4.

An event answers whether a report or transition occurred. It does not encode deterministic destiny or infer that a reported scheme will survive. Recurrence and development are projections over causal series, not authority added to one event.

## Privacy and references

Sensitive material is stored behind an authorized opaque `evidence_ref`; broad streams carry only IDs, SHA-256 digests, relation, and access class. `sensitive_reference` requires `redaction_status=passed`. Redaction failure rejects broad publication. Lower-snake-case key normalization prevents case variants from bypassing deny patterns; Stage A must additionally attack nested values, encoded forms, URLs, bearer forms, environment echoes, and configured secret values.

## Transport parity

The canonical event is transport-independent. Direct and ContextForge adapters receive identical canonical bytes and digest. Sink-local IDs/timestamps belong only in `noetic.event-sink-receipt/v0`. Neither sink may rewrite event class, authority, cognition, privacy, payload, or evidence references.

ContextForge remains operational where currently required, but is not the semantic boundary. If unavailable, direct-sink domain semantics remain unchanged and the adapter records retry/failure; it must not silently drop, reinterpret, or authorize an event.

## Evolution

- Any changed required field, enum meaning, authority rule, class matrix, phase mapping, or digest canonicalization is breaking and requires a new major contract version.
- Additive fields require an explicit versioned extension point; strict v0 envelopes otherwise reject unknown fields.
- Old readers reject unsupported major versions. Durable events are never rewritten in place.
- Producers pin `contract_version`; projections preserve unknown historical events as opaque records rather than inventing semantics.
- Sink adapters must pass the same parity fixture before promotion.

## Validation

Run `python3 scripts/validate_event_specs.py`. The dependency-free validator checks schema/matrix parity, required identity and authority boundaries, P1–P4 pairings, privacy/reference constraints, negative mutations, canonical digest, and direct/ContextForge receipt parity.
