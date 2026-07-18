# Protected Route Attestation

The protected Agent Review workflow produces exact-run route evidence. A separate trusted local operator makes that evidence durably revalidatable after the source pull request merges.

## Operation

`scripts/governance/route_attestation.py` discovers completed successful Agent Review runs after the configured bootstrap run. Open pull requests are deferred because their live base SHA can advance after the reviewed run, and closed-unmerged pull requests receive a terminal skip disposition. For each eligible unattested run it:

1. requires one exact run attempt, retained artifact, stable pull-request record, and review job;
2. derives the candidate SHA from the artifact name and requires the retained protected-base SHA to equal GitHub's historical PR base SHA;
3. makes a fresh credential-free clone of `somebloke1/noetic-dev`;
4. checks out the exact protected base in detached mode;
5. executes that base's `route_evidence.py`, which verifies the downloaded archive against GitHub's artifact digest and validates its sole evidence file and the live ruleset; and
6. writes a private atomic receipt under `~/.local/state/noetic-dev/route-attestations/`.

The user systemd timer invokes the operator every ten minutes. Install it only after the implementation has merged and `/opt/noetic-dev-agent-review/current` points to that protected release:

```bash
deploy/install-route-attestation-user.sh <implementation-agent-review-run-id>
```

The argument is the successful Agent Review run for the implementation PR itself. That bootstrap run used the previous protected-base validator and is deliberately excluded; only later canaries are eligible for automated receipts.

The installer requires `loginctl` to report `Linger=yes` for the trusted operator account, so the user timer continues after logout. The oneshot service has a 30-minute start timeout, longer than its bounded network, clone, checkout, and validation operations while still preventing an indefinitely wedged invocation.

The operator persists a private verified run cursor. Open PRs defer cursor advancement. Closed-unmerged PRs receive a durable `skipped-run-<run>.json` disposition, while merged successful runs require valid receipts. The operator refuses to continue if GitHub's bounded workflow-run inventory no longer contains the cursor, so a long outage becomes an explicit truncation failure rather than silently dropping eligible runs.

Installation is an operator action, not an isolation boundary against the invoking Unix account. The script uses a fixed shell, refuses shell/loader injection variables, derives the account home from the passwd database, and sanitizes the GitHub authentication probe. Invoke it only from the trusted operator account; the recurring systemd service is the hardened runtime boundary.

The unit stores no token. It uses the operator account's existing GitHub CLI authentication to read Actions artifacts and administrator-visible ruleset state. The repository-scoped self-hosted runner cannot read that account's home or receipt directory.

## Trust Boundary

The receipt records that the identified protected-base validator accepted a specific repository, workflow, run attempt, review job, PR, candidate/base pair, and artifact ID/name/digest after checking the retained route evidence and live ruleset. It does not embed the artifact or ruleset snapshot: independent replay remains limited by the artifact's 90-day retention and mutable GitHub API availability. The receipt is therefore an atomic local acceptance record, not post-expiry proof, a GitHub merge check, or an artifact signature.

GitHub Actions App ID `15368` is shared by every Actions workflow in the repository. Binding required contexts to that App does not authenticate a workflow path. This public user-owned repository cannot use native required-workflow or push-path rules. A distinct merge-gate trust root requires either an organization required workflow or a separately hosted GitHub App whose private key is unavailable to candidate Actions.
