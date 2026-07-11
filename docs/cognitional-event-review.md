# Adversarial review: canonical cognitional event v0

**Issue:** [#8](https://github.com/somebloke1/noetic-dev/issues/8)

**Pairing:** one implementation generation → exactly one adversarial QA pass

**Scope:** schema, class/authority matrix, fixtures, validation, and CI only

## Verdict

**PASS FOR M0 CONTRACT REVIEW; NOT AUTHORIZATION TO IMPLEMENT A SINK, UI, OR CONTROL SURFACE.**

The independent QA pass validated positive fixtures with a Draft 2020-12 implementation and attacked the semantic rules separately through generated mutations. No unresolved blocker remains.

## Adversarial vectors

| Vector | Attack | Result |
|---|---|---|
| Semantic authority leakage | Made a P4 report claim `enacted`; made a cognitive agent author a domain transition; relabeled domain truth as diagnostic/effect status. | Rejected. Cognition remains attributed report; only an authorized controller event enacts structural truth. |
| P1–P4 fidelity | Generated all four phase/operation pairs and a recursive return with greater iteration/depth. | Passed. Canonical pairs hold, modality is explicit, governing purpose is required, and no false one-way phase-order rule blocks recurrence. |
| Schema evolution | Changed major version and added an unknown root field. | Rejected by fail-closed semantic validation and strict JSON Schema. |
| Privacy | Tried mixed-case credential keys, nested private-artifact keys, bearer text, URL credentials, and provider-key shapes. Removed evidence from a sensitive-reference event. | Rejected. Recursive checks cover key/value forms; sensitive-reference events require passed redaction and at least one opaque digest-bearing reference. |
| Transport parity | Recomputed canonical digest, compared direct/ContextForge receipts, then changed authority while reusing the old receipt digest. | Untampered profiles passed; authority mutation changed the digest and failed semantic validation. Sink metadata remains receipt-only. |
| P1–P4/domain compatibility | Compared canonical domain prefixes to controller aggregate enums/tables and checked the domain fixture against a declared controller event. | Passed; no aggregate vocabulary drift. |
| Runtime neutrality | Enumerated changed paths. | Passed: only `.github/`, `docs/`, `scripts/`, and `spec/` changed. |

The validator was also run with `python3 -O`; its checks do not depend on optimized-away `assert` statements.

## Deliberate boundaries

1. Canonical digest v0 uses UTF-8 JSON with recursively sorted keys, compact separators, and unescaped Unicode. A cross-language adapter stage must either prove byte parity or adopt a separately versioned standard canonicalization profile before durable external use.
2. JSON Schema constrains top-level payload names; the dependency-free validator recursively checks nested keys and representative secret-shaped values. Runtime ingress must reuse or strengthen those checks rather than trusting schema alone.
3. The ContextForge receipt is a parity contract, not evidence that a current ContextForge API already implements this sink. Issue #14 must inventory the actual attachment mechanism without disrupting current services.
4. `occurred_at` and `recorded_at` are audit metadata, not transition ordering authority. Stream position and causal identity remain authoritative within a stream.
5. An event records that an operation/report/transition occurred. It does not prove semantic correctness, predict recurrence, or authorize later action by itself.
6. Observability projections and privileged controls remain issue #12 work; this PR creates neither.

Any relaxation of assertion scopes, privacy/reference requirements, P1–P4 mappings, or sink digest parity requires a new contract version and a new implementation:QA pair.
