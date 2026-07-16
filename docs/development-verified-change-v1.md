# development.verified-change/v1

This bounded provider-free adapter accepts one strict attributed development packet and one separately supplied frozen-valid M0 or M1 trace. It validates packet shape and lineage, recomputes the canonical source digest, invokes exactly the selected frozen reducer, binds the packet to that reducer's projection, preserves the complete source projection unchanged, and derives a terminal program projection. It does not implement a generic cognitive-program engine or a shared source lifecycle.

## Evidence and determination boundary

The packet's P1 attention and P2 insight objects are opaque attributed products. Their IDs and digests do not establish attentiveness, observation quality, insight, truth, feasibility, or the absence of judgment. The implementation procedure and final candidate are also attributed references; the adapter does not load or execute their bytes.

P3 reasonableness evidence is only the terminal QA adjudication attributed by the validated source trace. P4 responsibility evidence is only the terminal Telos adjudication attributed by that source under the recursively governing purpose. `FAIL`, `PASS`, `succeeded`, and `complete` remain source-fixture declarations. The adapter does not authenticate actors, establish genuinely independent QA, infer semantic quality, claim actual cognition, or certify responsible judgment.

The three deterministic gates determine only structural lineage and equality:

1. `attention_to_insight_lineage` records the P1 packet, P2 packet, and shared question as `structurally_bound`.
2. `procedure_to_implementation_lineage` records the P2-to-procedure and procedure-to-final references as `structurally_bound`.
3. `final_implementation_binding` records all six terminal source equality fields as `source_equal`.

The remaining gates are `attributed_semantic`: `verification`, profile-specific `remediation`, `controller_result`, and `telos_adjudication`. The M0 remediation gate is exactly `{"represented":false}`; it has no synthetic zero budget. The M1 remediation gate preserves the source projection's exact `remediation_budget` and `remediation_generation`. Controller result and Telos adjudication remain separate, and only the Telos gate carries the source-attributed `complete` disposition.

## Strict packet

The source trace is never embedded in the packet. The closed root has exactly:

- `schema_version`, fixed to `development.verified-change.packet/v1`
- `program_id`, fixed to `development.verified-change`
- `program_version`, fixed to `v1`
- `program_instance_id` and `governing_purpose_id`
- `execution_profile`
- `attention_packet`, `insight_packet`, and `implementation_procedure`
- `final_implementation`
- `source_trace_digest` and `source_trace_version`

`attention_packet` has exactly `packet_id`, `producer_actor_id`, `evidence_id`, `evidence_digest`, and `question_id`. `insight_packet` has exactly `packet_id`, `producer_actor_id`, `insight_digest`, `attention_packet_id`, and `question_id`. The latter two references must equal P1.

`implementation_procedure` has exactly `artifact_id`, `artifact_digest`, `producer_actor_id`, and `insight_packet_id`; its insight reference must equal the P2 packet ID. The P1 packet ID, P2 packet ID, and procedure artifact ID all use the common `product-*` format and must be pairwise distinct. Producer IDs and digests need not be distinct.

`final_implementation` has exactly `generation`, `accepted_event_id`, `candidate_id`, `candidate_digest`, `implementer_actor_id`, `verification_obligation_id`, and `implementation_procedure_artifact_id`. The procedure reference must equal the prior artifact ID. Every other final field must equal the selected source projection's terminal accepted generation; generation is integer 1 for M0 and integer 2 for M1, never a boolean.

Strict JSON rejects duplicate keys, floating-point values, non-finite constants, nulls, non-string object keys, unsupported direct Python values, and unknown or missing fields. Digests are lowercase `sha256:` plus 64 hexadecimal digits.

Draft 2020-12 validation is structural only: it closes shapes, fixed values, patterns, and profile-local conditions. It does not enforce cross-field equality, lineage, pairwise distinctness, canonical source digest equality, or source-projection bindings. A packet is accepted only after both structural schema validation where used and the paired standard-library validate_and_project(packet, source_trace) semantic/cross-field validation; the reducer is the executable authority for those invariants.

The structural [Draft 2020-12 packet schema](../spec/programs/development.verified-change/v1/development-verified-change-packet.schema.json) and the [program contract](../spec/programs/development.verified-change/v1/program-contract.json) record their respective boundaries. Neither substitutes Draft validation for the reducer-owned linked invariants.

## Explicit source profiles

`m0-direct-pass` accepts only `noetic.m0.telos-adjudication-trace/v0` through `scripts.m0_trace.validate_and_project`. Its full unchanged projection retains one generation, one source-attributed QA `PASS`, controller result, and separate Telos adjudication. The program terminal generation is 1.

`m1-bounded-remediation` accepts only `noetic.m1.telos-recoverability-trace/v0` through `scripts.m1_trace.validate_and_project`. Its full unchanged projection retains generation-1 `FAIL` and finding, the exact remediation event and `authorized=1`, `consumed=1`, `remaining=0` budget, generation-2 `PASS`, generation-2-only controller success/result, and full ordered Telos evidence. The program terminal generation is 2.

The implementation has an explicit branch for each profile and invokes only that branch's existing reducer. It does not copy, refactor, parameterize, flatten, or extract M0/M1 transitions, and it has no variable-length trace machine.

## Source and program binding

`source_trace_digest` is `SHA-256` over compact, ASCII, lexicographically sorted canonical JSON bytes of the complete parsed source trace, including one final LF. Object property order and source formatting therefore do not affect the digest, while every parsed source value does.

Before any program projection is returned, the selected frozen reducer must accept the source. Reducer rejection becomes a controlled program-validation error. The packet's `program_instance_id` must equal source projection `binding.program_id`, its `governing_purpose_id` must equal source projection `delegation.purpose`, and all final fields except the procedure reference must equal the source terminal acceptance. The complete reducer result is embedded unchanged as `source_trace_projection`.

The terminal projection is strict `development.verified-change.projection/v1` at `telos_adjudicated`. It preserves the packet products, final implementation, source version and digest, source projection, and all seven gates. Canonical output is compact lexicographically sorted ASCII JSON with one final LF.

## Pure reducer and CLI

`validate_and_project(packet, source_trace)` is pure over its two arguments. It does not read files, inspect environment or clock, use randomness, spawn a subprocess, call a model/network/database, write data, or mutate either input. It does not execute a candidate, inspect artifact bytes, run tests or Git, publish, deploy, schedule, persist, recover a process, or update Telos.

The CLI alone reads supplied paths. Non-check mode accepts exactly packet and source paths and writes only canonical projection bytes to standard output. Check mode accepts exactly packet, source, and expected projection paths:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/development_verified_change.py --check \
  spec/programs/development.verified-change/v1/golden/valid-bounded-remediation-packet.json \
  spec/m1/v0/golden/valid-telos-recoverability-trace.json \
  spec/programs/development.verified-change/v1/golden/expected-projection.json
```

The committed golden is M1-backed because it exercises the maximum fixed path. M0 support is constructed from the existing M0 golden in tests; no second program golden is committed.
