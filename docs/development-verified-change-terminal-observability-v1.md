# development.verified-change terminal observability/v1

This provider-free terminal read model accepts only an in-memory object already produced upstream as `development.verified-change.projection/v1`. `derive_terminal_observability(projection)` performs bounded compatibility checks needed to select one of the two frozen profiles and returns a fresh `development.verified-change.terminal-observability/v1` dictionary. It is a projection-only observer, not another source validator.

## Claim boundary

The observer checks exact consumed shapes, selected field types, fixed program and profile versions, terminal projection states, deterministic gate markers, and source-attribution gate markers. These checks prevent version confusion and unsafe field selection. They do not authenticate that CLI input came from the accepted upstream reducer.

The observer never accepts a packet or source trace. It does not import or call the program, M0, or M1 reducers; recompute a digest; compare linked IDs or digests; or revalidate source event order, cardinality, evidence order, remediation arithmetic, QA conclusions, controller outcomes, or Telos dispositions. Input JSON formatting need not be canonical because the pure contract begins after parsing.

`PASS`, `FAIL`, `succeeded`, and `complete` remain source-attributed declarations. IDs and digests remain opaque references. The read model establishes no semantic correctness, evidence sufficiency, actor identity, independent QA, authentic provenance, live state, or external effect.

## Exact read model

The closed top level contains only `schema_version`, `scope`, `subject`, `evidence`, `qa`, `remediation`, `controller`, `telos`, and `explicit_unknowns`.

`scope` is fixed to:

- `view_kind: terminal_projection`
- `claim_boundary: structural_or_source_attributed_only`
- `live_operational_data: not_present`
- `input_provenance: upstream_precondition_not_authenticated`

`subject` copies the program ID, version, instance, execution profile, projection state, and governing purpose. Its `source` copies the trace version and digest, source projection version and state, and the exact profile-specific binding. M0 therefore retains binding `generation`; M1 does not synthesize it.

`evidence` copies attention, insight, procedure, and final implementation unchanged beneath fixed `evidence_status` labels. It also copies the three deterministic lineage gates unchanged. These are opaque fixture-attributed products or references, not loaded artifact content.

`qa.generation_history` is the only presentation normalization:

- M0 becomes one item containing source `accepted_generation`, source `qa_adjudication`, and the accepted generation number.
- M1 is an unchanged copy of the two source history items, including the generation-1 finding and generation-2 remediation and supersession references.

`qa.terminal_verification` copies the accepted terminal verification gate unchanged. Normalizing history shape does not infer a causal edge or strengthen any conclusion.

`remediation` copies the profile gate exactly. M0 is exactly `{"represented": false}`; no zero budget, empty generation, null, or "not needed" interpretation is added. M1 retains the represented marker, source attribution, exact budget, and exact remediation generation.

`controller` copies only the source-attributed controller-result gate. It gains no disposition, sub-goal status, readiness, recommendation, or action. `telos.delegation` wraps the unchanged source delegation with fixed source-attribution markers, while `telos.adjudication` copies the source-attributed Telos gate. Only the copied Telos adjudication can carry the source declaration `complete`.

The exact ordered `explicit_unknowns` are:

1. `artifact_availability_and_content`
2. `semantic_correctness`
3. `authenticated_actor_identity`
4. `genuinely_independent_qa`
5. `live_runtime_state`
6. `readiness_blockage_or_critical_path`
7. `current_command_authority`
8. `external_effect_execution`
9. `causality_not_preserved_in_projection`

## Causal and operational boundary

Only event and evidence references already present in selected projection fields survive. The observer does not add raw event types, timestamps, immediate `caused_by` edges, a general causal graph, liveness, readiness, blockage, current status, critical path, dependency or queue state, durations, freshness, health, progress, actions, recommendations, command authority, or provenance truth.

The pure function does not mutate input and returns fresh nested values. It uses no file, environment, clock, randomness, process, Git, provider, model, network, MCP, database, controller, scheduler, or write effect.

## CLI and golden

The CLI reads exactly one projection path. Non-check mode emits sorted-key, two-space-indented ASCII JSON with one final LF. `--check` reads one additional expected read-model path and compares exact canonical presentation bytes. Validation and I/O failures return 1 with one controlled stderr message and no stdout or traceback; argument failures return 2.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/development_verified_change_observe.py --check \
  spec/programs/development.verified-change/v1/golden/expected-projection.json \
  spec/programs/development.verified-change/v1/golden/expected-terminal-observability.json
```

The sole committed read-model golden derives directly from the accepted M1 program projection. Tests construct the M0 program projection from accepted M0 artifacts through the accepted adapter; no M0 input schema or additional golden is introduced.

The machine-readable [terminal observability contract](../spec/programs/development.verified-change/v1/terminal-observability-contract.json) freezes the field order, labels, profile shapes, compatibility boundary, and forbidden inferences.
