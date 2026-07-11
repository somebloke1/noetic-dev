# Telos delegation-dispatch contract

**Status:** M0 executable contract for [issue #9](https://github.com/somebloke1/noetic-dev/issues/9). No runtime dispatcher, Telos mutation, agent spawn, repository effect, or network effect is authorized here.

## Ownership invariant

Telos remains the teleological owner of the goal chain, objective, reproductive clause, governing principles, sub-goal status, purpose amendments, and final result adjudication. The controller owns only the structural run lifecycle, deterministic scheduling, effect intents, and causal execution evidence it is authorized to enact.

A delegated sub-goal is `delegated-pending`: it is not independently active in Telos and is not owned by the controller. A successful controller result does **not** complete the sub-goal. It reports evidence to Telos; Telos performs P3 judgment and P4 responsibility, then separately records `complete`, `blocked`, an amendment, or further work.

## Verified donor seam

Telos already contains the beginnings of this boundary:

- `packages/core/src/model.ts` and `continuation.ts` include `delegated-pending` and deliberately exclude it from locally actionable continuation states;
- `packages/core/src/schema.ts` contains `delegations` and append-only `delegation_events` tables linked to chain, sub-goal, and project;
- the current rows carry contract JSON, worktree, wave, and status, but the inspected core manager has no lifecycle that enforces status vocabulary, expiry, replay, authority attenuation, controller identity, or result ownership.

This contract harvests that schema intent without modifying or depending on the donor runtime.

## Delegation contract

`telos.delegation/v0` pins:

- Telos owner identity: chain, sub-goal, project, reproductive-clause version, and objective digest;
- objective, governing principles, acceptance references, and requested outcome;
- immutable program version and graph digest;
- one controller run identity at expected version zero;
- narrowed subject and command scope plus forbidden effects;
- issuer, permissions, not-before, expiry, and revocation evidence;
- bounded retry/idempotency and cancellation/expiry policy;
- exact controller-command and canonical-event contract versions.

The canonical contract digest is included on every dispatch, callback, interaction, cancellation, amendment, and result. Mutable ambient goal text, a process environment, or a workspace path is never authority.

## Dispatch and replay

`controller-binding.json` maps the contract to existing controller v0 commands:

1. `run.create` uses `dispatch:{delegation_id}:{contract_digest}` and carries only pinned refs.
2. Duplicate delivery returns the original command receipt and run ID; it cannot create a second run.
3. `run.start` occurs only after accepted creation for the same run/digest.
4. Interactions return as canonical `decision_request` events and resolve through scoped `interaction.resolve`.
5. Purpose changes are append-only Telos amendments plus `contract.amend`; they never rewrite the baseline contract.
6. Cancellation uses a stable `run.abort` key and aggregate expected version. A cancellation/terminal-result race resolves by the controller journal; terminal state is never reopened.
7. Expired or revoked authority cannot dispatch, start, resume, amend, resolve, publish, or cancel under the stale grant.

Retries are bounded attempts to deliver the same intent, not new delegations. A new purpose/program/scope creates a new contract digest and requires explicit Telos authority.

## Results and interactions

`telos.delegation-result/v0` reports controller status, evidence references, causal final event, interaction reference where needed, and the exact delegation digest/run identity. Strict fields prohibit a result from smuggling `sub_goal_status`, replacement objective, new principles, or authority expansion back into Telos.

`requires_decision` must point to a durable interaction. Terminal statuses must point to a controller final event. Results are idempotent and attributable; repeated delivery does not repeat Telos adjudication.

## Authority and privacy

The allowed command scope must equal the delegation authority permissions and be a subset of the canonical Telos row in `controller/v0/authority-matrix.json`. Internal scheduler/lease/reconcile commands, attempt callbacks, QA adjudication, and effect receipts are forbidden to delegated Telos authority.

Objectives, principles, summaries, and evidence references are scanned for secret-shaped values. Full prompts, credentials, tokens, contact data, and private artifacts remain behind opaque references. Delegation and result summaries never become broad authority merely because they pass through a trusted sink.

## Compatibility and promotion

Changing owner semantics, digest canonicalization, authority equality, lifecycle outcomes, expiry behavior, or result/Telos ownership is breaking and requires a new major version. The eventual Telos adapter must migrate donor rows explicitly, enforce unique idempotency and active-delegation constraints transactionally, and replay these fixtures before activation.

Stage implementation remains blocked until this contract and the parent controller/event contracts are accepted. Every runtime stage receives its own implementation plus exactly one adversarial QA pass.
