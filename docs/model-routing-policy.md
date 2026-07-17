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

This repository slice adds the canonical machine policy, strict schemas, and a protected-review broker adapter that starts one persistent external genus-router MCP stdio process through the official MCP client. The broker verifies the external tool contract, submits only protected-review dimensions, validates every returned decision and model reference before one bounded LiteLLM invocation, and requires external `report_outcome` acknowledgement before success or reroute. Route evidence binds the external component SHA. Deployment and an exact-SHA protected canary remain required before this implementation can be cited as a recurring live trace. The OpenCode contract remains `runtime_adapter_ready=false`; this slice does not claim live OpenCode, protected Pi, embedding, or ASR adapters are fully migrated.

The broker and trusted external genus-router process both receive the scoped LiteLLM credential. Genus-router uses it only for the canonical `/v1/models` availability check; the bounded Pi subprocess uses it for the selected model invocation. Unrelated broker environment values are not forwarded to genus-router.

Accepted target policy:

- LiteLLM endpoint: `local-litellm` at the authoritative deployed address `http://172.22.10.160:3333`; alternate or direct-provider endpoints are forbidden. Because this endpoint uses HTTP with a bearer token, the broker fails startup and rechecks immediately before every model invocation unless the kernel reports the exact address as a local route over `lo`.
- Credential name: `LITELLM_API_KEY` / systemd credential `litellm_api_key`.
- Generative routes: `codex/gpt-5.6-sol`, `codex/gpt-5.6-terra`, `codex/gpt-5.6-luna`, and limited `claude-fable-5` for high-value review, research, or design only.
- Embedding route: `snowflake-arctic-embed2`.
- ASR route: `qwen3-asr`.
- OpenCode routed-session contract: one routed model turn per session, static title required, JSON event log required, tools disabled, provider allowlist restricted to `litellm`, and outcome reporting required per route decision.
- Broker route-evidence contract: protected review attempts must follow Terra -> Sol -> Luna candidate order, record every outcome, preserve high reasoning, and bind every model reference to the local LiteLLM `/v1/responses` endpoint.

Missing runtime adapters remain open work under Issue #29. This implementation must not be cited as evidence that live broker genus-router route/outcome reporting recurs in deployment until its exact-SHA canary passes, or that ASR readiness, embedding migration, live OpenCode routing, or protected Pi routing has completed.
