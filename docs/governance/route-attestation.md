# Protected Route Attestation

The protected Agent Review workflow produces exact-run route evidence. A separate trusted local operator makes that evidence durably revalidatable after the source pull request merges.

## Operation

`scripts/governance/route_attestation.py` discovers completed successful Agent Review runs after the configured bootstrap run. For each unattested run it:

1. requires one exact run attempt, retained artifact, stable pull-request record, and review job;
2. derives the candidate and protected-base SHAs from the artifact name and stable PR endpoint;
3. makes a fresh credential-free clone of `somebloke1/noetic-dev`;
4. checks out the exact protected base in detached mode;
5. executes that base's `route_evidence.py`, which downloads and validates the exact artifact and live ruleset; and
6. writes a private atomic receipt under `~/.local/state/noetic-dev/route-attestations/`.

The user systemd timer invokes the operator every ten minutes. Install it only after the implementation has merged and `/opt/noetic-dev-agent-review/current` points to that protected release:

```bash
deploy/install-route-attestation-user.sh <implementation-agent-review-run-id>
```

The argument is the successful Agent Review run for the implementation PR itself. That bootstrap run used the previous protected-base validator and is deliberately excluded; only later canaries are eligible for automated receipts.

The operator persists a private verified run cursor. It advances only across successful runs with valid receipts and refuses to continue if GitHub's bounded workflow-run inventory no longer contains that cursor. A long outage therefore becomes an explicit truncation failure rather than silently dropping eligible runs.

Installation is an operator action, not an isolation boundary against the invoking Unix account. The script uses a fixed shell, refuses shell/loader injection variables, derives the account home from the passwd database, and sanitizes the GitHub authentication probe. Invoke it only from the trusted operator account; the recurring systemd service is the hardened runtime boundary.

The unit stores no token. It uses the operator account's existing GitHub CLI authentication to read Actions artifacts and administrator-visible ruleset state. The repository-scoped self-hosted runner cannot read that account's home or receipt directory.

## Trust Boundary

The receipt proves that the protected-base validator accepted a specific repository, workflow ID/path, run attempt, review job, PR, candidate SHA, base SHA, artifact ID/name/digest, ruleset snapshot, router component, LiteLLM invocation, and acknowledged outcome. It is local durable evidence, not a GitHub merge check and not an artifact signature.

GitHub Actions App ID `15368` is shared by every Actions workflow in the repository. Binding required contexts to that App does not authenticate a workflow path. This public user-owned repository cannot use native required-workflow or push-path rules. A distinct merge-gate trust root requires either an organization required workflow or a separately hosted GitHub App whose private key is unavailable to candidate Actions.
