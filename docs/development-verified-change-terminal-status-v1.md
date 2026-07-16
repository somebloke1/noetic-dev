# development.verified-change terminal status/v1

This provider-free status read model accepts only an in-memory object already accepted upstream as `development.verified-change.terminal-observability/v1`. `derive_terminal_status(observability)` returns a fresh `development.verified-change.terminal-status/v1` dictionary that explains what terminal status can and cannot be derived from that input.

## Claim boundary

The status observer checks exact consumed terminal-observability shapes, fixed versions, profile-specific controller and Telos payloads, QA history, remediation shape, and the ordered explicit unknowns. It prevents version confusion and unsafe field selection. It does not authenticate that CLI input came from the upstream observer.

The observer never accepts a packet, source trace, or program projection. It does not import or call the program, M0, M1, or terminal-observability reducers; recompute a digest; dereference artifacts; compare linked IDs or digests; or revalidate source event order, remediation arithmetic, QA conclusions, controller outcomes, or Telos dispositions.

`PASS`, `FAIL`, `succeeded`, and `complete` remain source-attributed declarations. The read model establishes no semantic correctness, evidence sufficiency, actor identity, independent QA, authentic provenance, live state, command authority, external effect, or causal completeness.

## Exact read model

The closed top level contains only `schema_version`, `scope`, `subject`, `controller_status`, `telos_status`, `qa_status`, `remediation_status`, `operational_status`, `references`, and `explicit_unknowns`.

`scope` is fixed to:

- `view_kind: terminal_status_explanation`
- `claim_boundary: terminal_observability_projection_only`
- `live_operational_data: not_present`
- `input_provenance: upstream_precondition_not_authenticated`

`controller_status` is sourced only from `controller.result`. It exposes run outcome and copied result/event references. It explicitly carries no Telos disposition and no command authority.

`telos_status` is sourced only from `telos.adjudication.adjudication`. It exposes disposition and copied result/event references. It explicitly carries no controller success inference and no command authority.

`qa_status` summarizes generation history and terminal verification by copied IDs and conclusions only. `finding_present` and `remediation_reference_present` are structural field-presence flags, not judgments about truth or independence.

`remediation_status` preserves the profile distinction: M0 remains represented false with no zero budget inferred; M1 preserves source-attributed budget and generation.

`operational_status` has four fixed entries: `readiness`, `current_command_authority`, `critical_path`, and `causal_graph`. Each is `not_derivable_from_terminal_projection` with a reason and supporting unknown token.

The pure function does not mutate input and returns fresh nested values. It uses no file, environment, clock, randomness, process, Git, provider, model, network, MCP, database, controller, scheduler, or write effect.

## CLI and golden

The CLI reads exactly one terminal-observability path as UTF-8 JSON. Non-check mode emits sorted-key, two-space-indented ASCII JSON with one final LF. `--check` reads one additional expected-status path and compares exact canonical presentation bytes. Validation and I/O failures return 1 with one controlled stderr message and no stdout or traceback; argument failures return 2.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/development_verified_change_status.py --check \
  spec/programs/development.verified-change/v1/golden/expected-terminal-observability.json \
  spec/programs/development.verified-change/v1/golden/expected-terminal-status.json
```

The sole committed status golden derives directly from the accepted M1 terminal-observability golden. Tests construct M0 terminal-observability through accepted upstream adapters; no M0 status golden is committed.

The machine-readable [terminal status contract](../spec/programs/development.verified-change/v1/terminal-status-contract.json) freezes the field order, labels, profile shapes, compatibility boundary, and forbidden inferences.
