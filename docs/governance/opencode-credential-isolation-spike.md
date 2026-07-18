# OpenCode Credential-Isolation Spike

Issue #65 permits one bounded, source-free OpenCode model turn. This inert slice neither executes it nor establishes recurring behavior, adapter readiness, or delivery evidence.

## Honesty Boundary

`config/opencode-session-policy.json` remains `runtime_adapter_ready=false` and `status=contract-only`. The result schema enforces `evidence_class=non-evidence` and `report_outcome_id=null`; no spike artifact is readiness evidence.

The controller pins:

- OpenCode version `1.17.20` and binary SHA-256 `373af49ceba30c1b64e964463a64f8065103f942f240933a955f6c461e1a67f6`;
- genus-router component `f2b839b0cfc737c4c1f0a46d3d519d414529545c`;
- LiteLLM `http://172.22.10.160:3333/v1/responses`, reached only through a pidfd- and listener-bound connection to the pinned `litellm.service` process; and
- the standard-model set from `config/model-policy.json` and the pinned router's sophistication-dependent ordering.

The request is `test`, `trivial`, and `isolated`. The pinned trivial pool orders Luna, Terra, Sol; policy drift fails before `route_task`, and decision drift fails before execution. Classification is never changed to force a model.

## Phase Separation

The only supported order is:

```text
tokenless route process -> credential-owning execute parent -> tokenless outcome process
```

Route and outcome units deny IP networking and credential access. Only the execute unit declares `LoadCredential=litellm_api_key`.

`noetic-opencode-spike` runs tokenless phases; non-login `llm-svc` runs execute. The root orchestrator serializes phases across separate mode-0700 state. Router phases bind `non-evidence-router-state`, whose root-owned classifier enforces non-evidence, contract-only, not-ready storage separate from production.

The execute parent hashes and fd-binds immutable binaries into Bubblewrap. It clears the environment, unshares user/PID/IPC/UTS/network namespaces, disables nested user namespaces, mounts private runtime filesystems and no source, and gives OpenCode only a dummy loopback relay authorization.

The parent accepts one exact `/v1/responses` request, rejects drift/tools/replay/extra requests, and constructs a fresh upstream body. Before buffering and flushing authorization it verifies the root-owned LiteLLM artifacts, process/cgroup/start time, listener inode, pidfd, address, and connected peer.

Upstream SSE must contain one completed assistant text item, no refusal/tool, the routed model, and exact nonce. A sanitized stream and OpenCode's exact three JSON events must independently agree.

OpenCode uses `steps=2`; version 1.17.20 injects a maximum-step warning at `steps=1`. A credential-free probe confirmed one request and three events but attempted unrelated Cloudflare egress, so execution must remain network-unshared.

## Irreversibility

Atomic claims precede irreversible actions and existing state blocks replay. Execute residue is conservative and never retries the turn. Outcome durably reaches `report-issued` before the call; later invocations never call again, instead reconciling one exact isolated-log record or failing `outcome-report-unresolved`. Observed acknowledgements are `reported`; log recovery is `reconciled`. Preserve all failed state.

The root-only orchestrator serializes three oneshot units and attempts outcome after controlled execute failure. Installation starts nothing.

## Installation Contract

After merge and all protected gates pass, a trusted root operator can install an exact repository commit and exact OpenCode binary:

```bash
sudo deploy/install-opencode-spike.sh <noetic-source> <40-character-noetic-sha> <opencode-1.17.20-binary>
```

Installation verifies the Git object; pinned OpenCode, router, and LiteLLM identities; runtime permissions; active service; and existing systemd credential. It writes no credential and performs no model/router call. The mode-0700 orchestrator is a separate one-time invocation.

## Synthetic Validation

Default tests use local fakes only. `NOETIC_OPENCODE_TEST_BINARY` opts into the pinned binary inside Bubblewrap against a fake upstream, without credential or external network. No test calls genus-router, LiteLLM, or systemd.
