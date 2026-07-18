# OpenCode Credential-Isolation Spike

Issue #65 defines one bounded, source-free OpenCode model turn. This repository slice supplies an inert deployment contract and synthetic validation surface. It does not execute the turn, establish recurring behavior, promote an adapter, or produce protected-delivery evidence.

## Honesty Boundary

The canonical policy remains `runtime_adapter_ready=false` and `status=contract-only` in `config/opencode-session-policy.json`. Every result is permanently labeled `evidence_class=non-evidence`, uses `report_outcome_id=null`, and is validated by `governance/schemas/opencode-spike-record.schema.json`. A successful experiment could inform later work, but neither its record nor these artifacts may be cited as readiness evidence.

The controller pins:

- OpenCode version `1.17.20` and binary SHA-256 `373af49ceba30c1b64e964463a64f8065103f942f240933a955f6c461e1a67f6`;
- genus-router component `f2b839b0cfc737c4c1f0a46d3d519d414529545c`;
- LiteLLM `http://172.22.10.160:3333/v1/responses` with a kernel-local `lo` route required immediately before authorization is sent; and
- the standard-model set from `config/model-policy.json` and the pinned router's sophistication-dependent ordering.

The source-free request is classified honestly as `test`, `trivial`, and `isolated`. The pinned router's `trivial` sophistication pool orders Luna, Terra, Sol, so the controller requires Luna as the selected model and Terra then Sol as fallbacks. `route-policy-order-conflict` fails before `route_task` if that pinned ordering changes, while `route-model-order-invalid` rejects a decision that does not implement it. The controller does not reinterpret the repository's standard-model set as a universal ranking or change classification to force a preferred model.

## Phase Separation

The only supported order is:

```text
tokenless route process -> credential-owning execute parent -> tokenless outcome process
```

`deploy/systemd/noetic-dev-opencode-spike-route.service` and `deploy/systemd/noetic-dev-opencode-spike-outcome.service` cannot access systemd credentials, deny IP networking, and launch the exact external router component. Only `deploy/systemd/noetic-dev-opencode-spike-execute.service` declares `LoadCredential=litellm_api_key`.

All three oneshots use the dedicated `noetic-opencode-spike` identity rather than the persistent review broker's credential-bearing identity. The root orchestrator runs them serially with `KillMode=control-group`, so no process from one phase remains when the next phase starts. Route and outcome bind a private router-state directory over the pinned component's canonical state path inside their mount namespaces; this preserves the component identity while preventing the spike from reading or changing the production router log.

The execute parent opens and hashes immutable OpenCode and controller files, then binds those open file descriptors into Bubblewrap. Bubblewrap clears the environment, unshares user, PID, IPC, UTS, and network namespaces, disables nested user namespaces, mounts private `/proc`, `/tmp`, HOME, XDG, and `/work` filesystems, and mounts no project source. OpenCode receives only a dummy relay authorization value. Its private network contains a single loopback listener connected to the trusted parent by an authenticated AF_UNIX control channel.

The parent accepts one exact OpenCode `/v1/responses` request. It rejects extra fields, tools, sources, a wrong model, a noncanonical system prompt, a maximum-step reminder, replay, ambiguous HTTP framing, and more than one request. It then constructs a new source-free upstream request rather than forwarding the OpenCode body. The real bearer token remains in the parent and is injected only into one fixed-host HTTP request after the local-route check.

The upstream SSE stream must form one contiguous, completed response with one assistant text item, no refusal or tool item, the routed model, and the exact nonce. The parent removes reasoning and provider metadata by synthesizing a minimal validated SSE stream for OpenCode. OpenCode's JSONL must independently contain exactly `step_start`, `text`, and `step_finish` for one message and the same nonce.

OpenCode uses `steps=2` because version 1.17.20 computes `isLastStep` before its first model request; `steps=1` injects `CRITICAL - MAXIMUM STEPS REACHED` into that request. A network-observation probe with a synthetic local response showed one request and the expected three JSON events at `steps=2`, but also attempted unrelated Cloudflare connections. That probe used no real credential or model endpoint. It must not be rerun outside the network-unshared sandbox; the deployment contract blocks those external attempts.

## Irreversibility

Private atomic claims are created before routing, execution, upstream issuance, and outcome reporting. Existing state blocks replay. If a process crashes after an irreversible boundary, a later execute attempt records conservative `request-issued` residue when possible but never retries the turn. Outcome reporting is at-most-once because the external router has no transactional idempotency key. Operators must preserve failed state for diagnosis rather than deleting it and pretending the spike did not occur.

The root-only `deploy/run-opencode-spike.sh` serializes the three oneshot units. It always attempts the outcome phase after a controlled execute failure. The installer places immutable runtime files and units but deliberately neither enables nor starts them.

## Installation Contract

After merge and all protected gates pass, a trusted root operator can install an exact repository commit and exact OpenCode binary:

```bash
sudo deploy/install-opencode-spike.sh <noetic-source> <40-character-noetic-sha> <opencode-1.17.20-binary>
```

Installation verifies the Git object, OpenCode version and digest, canonical external-router deployment, Bubblewrap, local-route tooling, system identity, and an existing nonempty systemd credential. It installs and hashes the controller and its router client together, writes no credential, and performs no model, router, or service operation. The installed `/usr/local/sbin/noetic-dev-opencode-spike` is mode `0700`; invoking it is a separate, explicit one-time operation.

## Synthetic Validation

`tests/governance/test_opencode_spike.py` uses only local files, socket pairs, fake router objects, synthetic SSE, and mocked subprocess/network boundaries by default. An opt-in test runs the exact pinned OpenCode binary inside Bubblewrap against an in-process fake upstream by setting `NOETIC_OPENCODE_TEST_BINARY`; it has no credential and no external network. `tests/governance/test_opencode_spike_systemd.py` checks static credential and process separation. No test calls genus-router, LiteLLM, systemd, or an external network endpoint.
