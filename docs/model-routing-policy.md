# Model Routing Policy

This document freezes the Issue #29 target policy. It is a policy contract, not proof that every runtime adapter has already migrated.

## Invariants

1. Every model invocation goes through LiteLLM.
2. Every generative, coding, or reasoning task is classified and selected through genus-router before invocation.
3. Selection varies with work sophistication; callers do not manually choose fallback or escalation models.
4. The generative set is Sol, Terra, and Luna, with limited high-value use of Claude Fable 5.
5. Capability order is `Sol | Fable > Terra > Luna`.
6. Snowflake Arctic serves embeddings and Qwen3-ASR serves ASR, both through LiteLLM.
7. Direct provider access from noetic-dev callers is forbidden.

## Lifecycle

The finite routed lifecycle is:

```text
classify -> route_task -> invoke through LiteLLM -> report_outcome
```

On failure, the caller reports the failed outcome and requests another route with the same task dimensions, `prior_failure=true`, and the failed model excluded. Outcome-reporting failure stops the lifecycle; it is not permission to bypass genus-router.

The broker review contract limits each route decision to one substantive invocation. After a reported failure, reroute creates a new route decision with its own one-invocation limit; the limit is not a global prohibition on governed reroute.

## Current Slice

This repository slice adds the canonical machine policy at `config/model-policy.json`, the strict schema at `governance/schemas/model-policy.schema.json`, contract tests, and a narrow broker runtime check that admits the `agent_review` model invocation only when the policy still requires local LiteLLM access and includes the broker harness. It deliberately does not claim live OpenCode, protected Pi, embedding, or ASR adapters are fully migrated.

Accepted target policy:

- LiteLLM endpoint: `local-litellm` at `http://127.0.0.1:3333`; non-HTTPS bearer-token traffic is only authorized on the loopback trusted boundary.
- Credential name: `LITELLM_API_KEY` / systemd credential `litellm_api_key`.
- Generative routes: `codex/gpt-5.6-sol`, `codex/gpt-5.6-terra`, `codex/gpt-5.6-luna`, and limited `claude-fable-5` for high-value review, research, or design only.
- Embedding route: `snowflake-arctic-embed2`.
- ASR route: `qwen3-asr`.

Missing runtime adapters remain open work under Issue #29. This policy must not be cited as evidence that ASR readiness, embedding migration, OpenCode routing, full broker genus-router outcome reporting, or protected Pi routing has completed.
