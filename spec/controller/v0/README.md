# Controller contract v0

This directory is the executable, runtime-neutral contract boundary for the noetic-dev controller. It defines strict command/event envelopes, the program graph, complete actor-command authority decisions, aggregate transition tables, and positive/negative examples. It does not authorize external effects.

## Versioning and compatibility

Each artifact carries an independent `controller.* /v0` schema version and an immutable versioned `$id` where JSON Schema applies.

- Additive optional fields may be introduced within v0 only when old readers safely ignore them or the envelope remains strict through an explicitly versioned extension point.
- New enum values, newly required fields, changed meanings, relaxed authority, and changed transition outcomes are breaking changes and require a new contract version.
- Readers reject unknown major versions and unknown fields in strict envelopes.
- Active runs pin program and graph versions; migration creates a new version or an authorized, compatibility-checked amendment.
- CI checks enum, actor, aggregate, transition, example, and policy parity to prevent schema drift.

## Authority and effects

The authority matrix is fail-closed. Delegation may narrow issuer permissions but never broaden them. A denied command yields no domain event or effect intent. Adapters may report effect receipts but cannot create domain authority. External effects are outside v0 and remain prohibited until their adapter stages are separately approved.

## Privacy

Broad event payloads must not contain secrets, credentials, tokens, passwords, full prompts, private artifacts, phone numbers, or critical-contact data. Such material is redacted and represented only by an authorized opaque reference with separate access control. The schema blocks sensitive top-level payload field names; dependency-free validation and Stage A property tests recursively challenge nested payloads and encoded variants.

## Validation

Run:

```bash
python3 scripts/validate_controller_specs.py
```

The validator checks strict schemas, complete authority decisions, transition determinism/reachability/terminality, graph acyclicity and barrier coverage, exact implementation-generation QA policy, privacy fixtures, and compatibility-policy presence without third-party dependencies.
