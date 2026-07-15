# Model routing and access policy

## Invariants

1. Every model invocation goes through LiteLLM. This includes calls made directly by noetic-dev and calls mediated by Pi, OpenCode, brokers, workers, or other coding-assistant harnesses.
2. Every generative, coding, or reasoning task is honestly classified and selected through genus-router before invocation. Selection shall vary with work sophistication.
3. The generative model set is Sol, Terra, and Luna, with limited high-value use of Claude Fable 5. Their capability order is `Sol | Fable > Terra > Luna`. Every Sol, Terra, and Luna invocation uses high reasoning; the adapter also requests high reasoning for eligible Fable review.
4. Snowflake Arctic serves embedding work and Qwen3-ASR serves ASR work. These modality-specific calls also go through LiteLLM.
5. Direct provider access from callers is forbidden. Provider credentials belong behind LiteLLM; noetic-dev dispatchers receive only LiteLLM credentials and model references.

## Mandatory lifecycle

Every routed generative operation follows one finite auditable loop:

```text
classify -> route_task -> invoke through LiteLLM -> report_outcome
```

The one-shot `agent-review` broker has a two-phase attempt under one decision: exactly one deterministic READY probe, then at most one substantive review invocation. Both calls use the selected, validated LiteLLM reference. The probe is evidence that the selected route can serve the bound work unit, not a separate generative task requiring another probe. `report_outcome` records the aggregate broker attempt; a failed phase records failure and causes a new decision with the failed model excluded.

Protected Pi QA has a different finite contract. Its READY probe and QA execution are separate routed operations in one fresh authority worker. Every operation attempt obtains and durably claims its own decision in one non-configurable per-authority namespace independent of output and run paths, invokes that decision at most once, and reports exactly one outcome; a successful attempt binds exactly one invocation. Type-strict contract validation, runtime guards, protected attempt-accounting evidence, and the delivery gate reject boolean/integer confusion, duplicate invocation, duplicate outcome, and decision reuse. The READY operation proves that the isolated harness path can complete a routed inference before QA execution. It does not authorize or claim readiness for the separately selected execution route, whose own failure lifecycle remains fail-closed. Exhausted candidates and outcome-reporting failures produce a schema-validated protected terminal-failure record with ordered decisions, invocation/outcome accounting, immutable candidate binding, and any successful READY record before the dispatcher returns failure. Protected QA terminal evidence requires full candidate, base, and tree identities. The exact broker and Pi contracts are machine-bound in `config/model-policy.json` and consumed by the protected Pi worker.

On failure, the caller reports the failed outcome and calls `route_task` again with the same task kind, complexity, and blast radius, `prior_failure=true`, and the failed model in `exclude_models`. Callers do not manually choose an escalation model.

An identifiable router decision that fails full validation is retained as a zero-invocation rejection, not as valid route authority. Its failed outcome must be recorded before the expected candidate may be excluded and rerouted. If outcome reporting fails, the lifecycle stops with structured failure evidence; protected Pi additionally writes validated terminal evidence before returning failure. A dedicated existing-claim exception alone establishes replay: Pi writes terminal replay evidence with zero invocations and outcomes, does not report a second outcome, and does not reroute. Other claim-infrastructure failures receive one failed outcome attempt and distinct terminal claim-failure evidence, then stop without rerouting. Every terminal record carries a final accounting summary whose counts are canonical decimal strings; Draft-07 binds that type-strict summary to its failure kind, and runtime validation independently recomputes it from exact-integer final-attempt counts.

The caller, not genus-router, is responsible for honest classification. `task_summary` is logging-only and never influences selection.

## Sophistication policy

Classification combines task kind, declared complexity, blast radius, and prior failure. Interface and systemic work impose a minimum sophistication; prior failure raises it further.

| Effective work sophistication | Default eligible tier | Typical work |
|---|---|---|
| Trivial and isolated | Luna | Mechanical transformations, extraction, routine summaries |
| Routine and bounded | Luna, then Terra | Documentation, triage, known-pattern implementation and tests |
| Complex but bounded | Terra, then Sol | Non-trivial implementation, debugging, QA, review, and research |
| Complex and systemic | Sol | Architecture, orchestration, cross-component design, consequential remediation |
| High-value independent judgment | Fable or Sol | Independent semantic review, critical research, or judgment where model-family diversity materially improves confidence |
| Protected independent approval | Sol at xhigh reasoning | Closed approval route, distinct from ordinary high-value judgment and bound to an explicit `independent_approval=true` request |

Fable is not a general-purpose fallback or bulk-work model. It is eligible only for explicitly governed high-value independent review, critical research, or systemic design judgment. Sol remains the default highest-capability engineering and orchestration model.

## Modality policy

| Task modality | Selection |
|---|---|
| Generative/coding/reasoning | Sophistication policy over Sol, Terra, Luna, and narrowly eligible Fable |
| Embedding | Snowflake Arctic through LiteLLM |
| ASR | Qwen3-ASR through LiteLLM |

Embedding and ASR do not use the generative sophistication ranking, but they retain the same LiteLLM-only access invariant and evidence requirements.

## Harness and adapter requirements

Pi, OpenCode, and every other harness are execution surfaces, not independent model selectors. A compliant adapter:

1. obtains a genus-router decision;
2. validates that the returned endpoint is the canonical LiteLLM endpoint and the model is eligible for the role;
3. invokes the returned LiteLLM model reference;
4. records the classification, `decision_id`, endpoint, selected model, fallbacks, and effective sophistication with the execution evidence;
5. reports `success`, `failure`, or `partial` through `report_outcome`;
6. reroutes according to the mandatory failure lifecycle.

The protected `agent-review` task is fixed by policy as `review + complex + interface`, with `high_value=false` and `awaited=true`. The broker cannot choose a model or inflate Fable eligibility. It validates the complete returned reference, translates high reasoning into the selected OpenAI-compatible request shape, invokes LiteLLM directly, validates model output, reports the outcome, and reroutes only after a recorded failure.

Dispatchers must reject direct provider namespaces, direct provider base URLs, and direct provider credentials. A harness-specific model alias is permitted only when it resolves through LiteLLM and remains bound to the genus-router decision.

The local review broker receives only `LITELLM_API_KEY`, preferably as the systemd `litellm_api_key` credential. It never passes that credential to Git, GitHub CLI, Pi, OpenCode, or candidate-controlled code.

## Migration state

The invariants above are the target policy, not a claim that every adapter is complete.

- **Accepted runtime paths:** the candidate local `agent-review` broker and protected Pi authoritative-QA worker. `run_isolated_pi.py` rejects real non-QA execution until callers supply honest task dimensions and compatible evidence contracts. Its broad `--record-only` role surface remains explicitly non-evidentiary. `governance/model-profiles.json` is historical metadata only and cannot authorize runtime selection.
- **Missing adapter:** bounded OpenCode execution, goalchain semantic curation through LiteLLM/Snowflake, modality callers, and independent-approval invocation. Existing direct OpenCode providers and the Ollama goalchain curator remain non-compliant dependencies, not compatibility exceptions.
- **External blocker:** production still runs a rollback broker until an exact reviewed release is installed and exercised. Snowflake is served by canonical LiteLLM, but the governed curator adapter is missing. Exact Qwen3-ASR is not currently advertised by LiteLLM and no noetic-dev ASR caller exists; `qwen3.6-a3b` is not a substitute. The system must not claim ASR readiness until both deployment and a real transcription succeed.

Issue #29 remains open for those missing adapters and external readiness gates. A merged broker/Pi-QA slice does not complete the repository-wide migration.

## Governance

Model prose is never evidence by itself. Every broker review requires its bound readiness phase and aggregate attempt evidence. Every protected Pi READY or execution operation requires separate captured evidence bound to the candidate/work-unit identity, policy commit, distinct route decision, resolved LiteLLM reference, harness configuration, at-most-one invocation per decision, and exactly one per-attempt outcome.

Delivery evidence schema v2 rejects static model-profile authorization. Each protected invocation carries `route_evidence` with the exact classification and ordered attempts; every attempt binds the complete genus-router decision, canonical LiteLLM reference, enacted reasoning, outcome, and confirmation that `report_outcome` succeeded. Authoritative QA uses the non-high-value complex-review contract. Protected independent approval requires the router's closed Sol/xhigh profile and an explicit `independent_approval=true` request; ordinary high-value Fable/Sol judgment is not approval evidence.

This policy governs both development of noetic-dev and the developed noetic-dev system. During migration, existing direct invocations are non-compliant dependencies to remove; they are not compatibility paths to preserve.
