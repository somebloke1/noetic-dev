# Model selection and access composition

**Issue:** [#10](https://github.com/somebloke1/noetic-dev/issues/10)

**Status:** M0 executable contract. No model invocation, probe, config write, route promotion, or provider call is authorized.

## Boundary

```text
program/Telos declares task dimensions
        ↓
genus-router selects a pinned model + ordered fallbacks from a pinned availability snapshot
        ↓
controller invokes only through the selected endpoint adapter under bounded policy
        ↓
LiteLLM-normalized chat (primary) OR direct specialized/local/provider endpoint
```

Selection and access are different responsibilities. Genus-router cannot invoke a model, resolve credentials, infer availability from a successful selection, or make provider-specific objects part of controller state. LiteLLM normalizes primary chat access; it does not own task classification, genus policy, controller authority, or the noetic-dev domain boundary.

## Verified donor evidence

The current genus-router already provides valuable mechanisms:

- `routing.py` is pure/config-driven and deterministically selects the first surviving ranked candidate;
- `config.py` has endpoint/model references and keeps local LiteLLM as a compatibility view rather than a hard architectural limit;
- `availability.py` checks registered model lists; and
- `server.py` records decisions, model refs, fallbacks, exclusions, and outcomes.

The contract hardens observed gaps:

- availability is currently a unioned set cached in memory, with only `verified|unverified`; one endpoint failure can make the whole snapshot unknown;
- decisions do not pin registry/policy digests, availability snapshot ID/time/expiry, or per-endpoint evidence;
- returned refs expose concrete base URL and token-env details rather than opaque adapter references;
- fallback candidates are not cryptographically tied to registry/availability evidence;
- the current registry places embedding models behind LiteLLM even though specialized direct local access must remain possible.

Telos evidence in `docs/litellm-current-recommendation.md` also constrains claims: bounded Qwen scenarios do not establish general user-global agent-loop safety; contaminated prior evidence is invalid; high-cost/provider routes remain blocked. This M0 contract therefore records `promotion_status` and does not promote any live route.

## Endpoint registry

`noetic.model-endpoint-registry/v0` separates endpoint identity from model identity.

Endpoints declare:

- `access_kind`: `litellm_normalized`, `direct_local`, or `direct_provider`;
- interface type: chat, responses, embeddings, or ASR;
- opaque `base_url_ref` and optional `credential_ref` resolved only by an adapter;
- locality, capabilities, allowed privacy classes, cost class, bounded health policy, and enabled status.

Models bind a stable public `model_ref` to endpoint/upstream reference, modalities, capabilities, promotion status, and policy tags. The reference is provenance, not permission to invoke.

The default contract requires:

1. at least one LiteLLM-normalized primary chat endpoint;
2. a direct-local embedding endpoint; and
3. a direct-local ASR endpoint.

This preserves specialized paths while keeping LiteLLM the normal chat access body.

## Reproducible selection

`noetic.model-selection/v0` records:

- declared routing dimensions and capability/privacy requirements;
- registry ID/version/digest and policy version/digest;
- an immutable availability snapshot with observed/expiry time and per-endpoint evidence;
- selected candidate, ordered fallbacks, and explicit exclusions;
- a selection-only invocation policy with bounded attempts/time/cost and adapter-only secret resolution.

A selected `available` model must appear in a nonexpired observation for the same endpoint and registry digest. `unverified` is permitted only when endpoint policy explicitly allows it; it is never silently upgraded to verified. Fallbacks are ordered pinned candidates from the same registry/snapshot and cannot be improvised after failure.

## Failure and privacy

A failed attempt records outcome against the decision ID, excludes that model, and requests a new selection with `prior_failure=true`; it does not mutate the old record. Provider errors do not reveal raw URLs, headers, credential values, private prompts, or provider response objects in canonical events. Only config/env references cross the deterministic boundary.

Direct local paths must fail closed when their health evidence is stale. LiteLLM may allow an explicitly `unverified` static decision for low-risk policy, but invocation remains a separately authorized controller action and current route-promotion gates still apply.

ContextForge is unchanged. It may later transport genus-router or adapter tools, but this contract neither removes existing dependencies nor makes ContextForge or LiteLLM the domain boundary.

## Evolution

Changing digest semantics, access kinds, privacy/cost meanings, snapshot freshness, selection/fallback ordering, or secret resolution is breaking. Runtime implementation must replay fixtures, prove direct/LiteLLM parity where claimed, preserve local specialized endpoints, and receive its own implementation:QA pair.
