# OpenCode Credential-Isolation Spike

Issue #65 permits one source-free, permanently non-evidence turn:

```text
tokenless route -> credential-owning execute -> tokenless outcome
```

Only `llm-svc` receives the credential. Root publishes bounded no-follow handoffs; outcome must match them. Bubblewrap exposes no source or host network, and its loopback is tested. One tool-free request is corroborated twice.

Claims precede effects. Execute never retries; outcome recovery only reconciles an exact isolated log record.

After merge, the root-owned attestor validates the reviewed repository/SHA/run. Runtime verifies its receipt, manifest, and controller before every phase:

```bash
sudo deploy/install-opencode-spike.sh <source> <reviewed-sha> <opencode> <review-run-id>
```
