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

## Current Slice

This repository slice adds the canonical machine policy at `config/model-policy.json`, the strict schema at `governance/schemas/model-policy.schema.json`, and contract tests. It deliberately does not claim live OpenCode, Pi, broker, embedding, or ASR adapters are fully migrated.

Accepted target policy:

- LiteLLM endpoint: `local-litellm` at `http://172.22.10.160:3333`.
- Credential name: `LITELLM_API_KEY` / systemd credential `litellm_api_key`.
- Generative routes: `codex/gpt-5.6-sol`, `codex/gpt-5.6-terra`, `codex/gpt-5.6-luna`, and limited `claude-fable-5`.
- Embedding route: `snowflake-arctic-embed2`.
- ASR route: `qwen3-asr`.

Missing runtime adapters remain open work under Issue #29. This policy must not be cited as evidence that ASR readiness, embedding migration, OpenCode routing, broker routing, or protected Pi routing has completed.
