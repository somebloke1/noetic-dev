# Application cost estimation skill

`noetic:cost-estimate` is a maintained deterministic application skill in
`scripts/noetic_costs.py`. It reads selected native accounting, optionally retrieves
official rates, saves user factors and calculates estimates. It makes no model
generation requests and installs no developer-global skill.

## Invocation

Inspect `GET /api/skills/cost-estimate?effort_root=FULL_ROOT` or explicit
`?scope=application`. Inspection returns the runnable skill's contract, current
profiles and local calculations without retrieving prices or creating cost state.

Run `POST /api/skills/cost-estimate/execute` using the application's existing
authenticated, same-origin JSON action contract. For example:

```json
{
  "effort_root": "0.0",
  "expected_revision": 0,
  "refresh_prices": true,
  "profile": {
    "provider": "openai-codex",
    "model": "gpt-6.1-sol",
    "billing_basis": "api",
    "currency": "USD",
    "overrides": {"input": 2},
    "factors": {"input_multiplier": 1, "output_multiplier": 1}
  }
}
```

The example declares an API-equivalent estimate, not a subscription bill. Use the
revision from current inspection; stale revisions return a conflict without
overwriting another edit. Provider and model are exact observed identities.
Profile IDs are local hashes of provider, model, billing basis and currency,
within the configured namespace and explicit selection. They are not native
session or canonical ordinal identities.

The same maintained functions `inspect(app, selection, accounting=projection)`
and `execute(app, request, accounting=projection)` are reusable by application
consumers. The projection is `scripts.noetic_usage.project(service, selection)`;
its source standing, field availability, actual model identity and deduplication
remain independent of monetary calculation.

## Factors and unknown values

`overrides` accepts input, output, cache_read and cache_write rates, each in the
declared currency per million tokens. `factors` accepts input_multiplier,
output_multiplier, allocation_cost, runtime_seconds, power_watts and
electricity_per_kwh. Values must be finite and nonnegative. An omitted field
preserves its saved value; explicit null clears only that named field. Zero is an
explicit value, not a missing factor.

- `api` calculates an API-equivalent estimate over compatible completed rows for
  the exact model/provider. Pi input excludes cache; cache reads and writes have
  separate rates, while output already includes reasoning. Per-category user
  multipliers apply once. Unknown positive-quantity rates or token quantities
  leave rows unpriced; the result discloses covered and matched records. Known
  zero quantities can contribute zero without an irrelevant rate.
- `subscription` uses an explicitly supplied allocation_cost for that
  scope/model. It does not infer a billing period or allocation from usage.
- `local` requires supplied measured runtime_seconds, power_watts and
  electricity_per_kwh. Energy cost is seconds × watts / 3,600,000 × price per kWh;
  hardware and other costs remain excluded.
- `unknown` keeps the estimate unavailable and names the missing billing basis.

API results use base rates and only explicit user multipliers. Source context,
speed/tier and regional qualifications are returned as source_notes and
pricing_conditions; they are not silently applied or inferred. Users can supply
the appropriate multipliers or override rates for their chosen comparison.
Recorded adapter cost, configured model cost zero and an estimate are distinct
from actual billed cost.

## Retrieval, persistence and evidence

Explicit `refresh_prices` currently supports exact gpt-6.1-sol, USD, an OpenAI
provider identity and the API-equivalent basis. It retrieves the maintained
official model Markdown URL, bounded to 64 KiB and twelve seconds, parses the
four text-token rate categories, and retains source URL, retrieval time, raw
source and digest. Unsupported identities/bases remain editable with manual
factors. Retrieval uses no provider credential.

Fetched snapshots, explicit overrides and factors are saved separately in
Noetic-owned `.cost-estimates.json` under the configured runs root. Refetch
preserves overrides. Fetch or parse failure preserves the last good snapshot
and its date, while reporting the failed attempt separately. Retrieval occurs
outside the application mutation lock; commit rereads the current revision
under that existing cross-process lock, then atomically replaces cost-only state.
Native journals, sessions, history, model configuration and bindings are not
rewritten.

Results independently report refresh.state and factor_save. Each saved profile
retains a receipt with exact selection, skill/version, settings revision, time
and calculated estimate. API estimates include a usage digest and source
session/sequence/response-digest references. Inspection can recalculate from
current retained accounting; the last saved receipt remains the earlier saved
calculation. Neither estimates nor coverage claim that all framework work has
structured accounting.
