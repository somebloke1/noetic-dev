# Adversarial review: model selection/access v0

**Issue:** [#10](https://github.com/somebloke1/noetic-dev/issues/10)

**Pairing:** one implementation generation → exactly one adversarial QA pass

## Verdict

**PASS FOR M0 CONTRACT REVIEW; NO LIVE ROUTE OR MODEL INVOCATION AUTHORIZED.**

Positive registry/selection fixtures passed Draft 2020-12 validation. The independent mutation pass found no unresolved blocker.

| Vector | Attack | Result |
|---|---|---|
| Selection/access conflation | Set `selection_only=false`. | Rejected. Genus-router selects; a separately authorized adapter invokes. |
| Stale availability | Decided after snapshot expiry and changed snapshot registry digest. | Rejected. Availability is pinned, expiring, per-endpoint evidence. |
| Provenance | Changed registry digest independently of the registry. | Rejected; selection must bind registry/policy identity and digest. |
| Fallback drift | Added an unregistered fallback after selection. | Rejected. Only ordered pinned candidates from the same record may be tried. |
| Provider leakage | Replaced opaque URL/credential refs with a concrete URL and raw value. | Rejected. Adapter-only config/env references cross the boundary. |
| Specialized local loss | Removed direct-local embedding and ASR endpoints independently. | Rejected. Both remain required even with LiteLLM-primary chat. |
| Capability/privacy | Requested audio or restricted privacy on the chat endpoint. | Rejected as capability/privacy mismatch. |
| Unsafe promotion | Marked the selected model blocked while updating registry digest. | Rejected. Selection cannot bypass promotion policy. |
| Runtime neutrality | Enumerated changed paths. | Only schema/docs/validator/CI paths changed; no model, LiteLLM, genus-router, ContextForge, or client config was touched. |

The validator passed under `python3 -O`; enforcement does not depend on optimized-away assertions.

## Boundaries

1. The current genus-router availability client unions endpoint results and lacks durable snapshot identity; runtime adoption requires a separate implementation and migration.
2. Current Telos evidence does not establish any LiteLLM route as safe for user-global Pi/OpenCode agent loops. This contract records provenance; it does not promote routes.
3. Opaque config/env references still require an adapter-owned registry and redaction policy; canonical events must not expose resolved values.
4. Cost classes are policy buckets, not billing truth. Runtime invocation needs measured cost/usage receipts.
5. ContextForge continuity findings remain unchanged; transport placement is separate from model selection/access semantics.
