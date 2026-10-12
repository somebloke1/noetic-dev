# Harness Runtime

`noetic harness` delegates to `scripts/noetic_harness.py`, which drives the actual
shared SQLite kernel described in [executive controller](executive-controller.md).
It executes only the reservation at
`state["activations"][state["current_activation"]]`. The adapter has no phase
progression table, remediation policy, or cognitive return policy. Those remain
in the persisted kernel pattern. Its only phase-specific execution privilege is
workspace editing for a `produce` activation in `implementation`.

## Commands

```bash
noetic harness start development TASK_FILE \
  --workspace /path/to/project --runs-dir /path/to/runs \
  --client opencode --model openai/gpt-6.1-sol --thinking high \
  --max-remediations 1 --max-returns 1

noetic harness start cognition TASK_FILE \
  --workspace /path/to/project --runs-dir /path/to/runs \
  --client pi --model openai-codex/gpt-6-astra --thinking high \
  --max-returns 1 --max-activations 2

noetic harness advance RUN_DIR --max-activations 1
noetic harness inspect RUN_DIR --json
noetic harness cancel RUN_DIR
```

From source, replace `noetic` with `python3 -m scripts.noetic`. The wheel includes
both `scripts/patterns/*.json` tables. Development means design intent, abstract
design, implementation procedure design, and implementation, each with fresh
author and QA sessions (eight on the ordinary path). `--max-remediations` limits
additional author/QA pairs **per phase**. Cognition means P1 attentiveness,
P2 intelligence, P3 reasonableness, and P4 responsibility, with `--max-returns`
limiting returns **across the run**. These are distinct patterns, not phase aliases.

Models must already be configured in the selected client. Optional `--qa-model`
selects a separate development reviewer model; otherwise QA uses `--model`.
The model name is passed through unchanged, including direct or proxy routes.
`--thinking` becomes Pi `--thinking` or OpenCode `--variant` without splitting
the final prompt argument. No global configuration is changed. `--timeout`
defaults to 900 seconds **per subprocess**, not per whole pattern.
Pi 0.85.1 native subscription access uses `openai-codex/gpt-6-astra`; the
already configured LiteLLM route uses `litellm/codex/gpt-6-astra`. For example,
`--client pi --model openai-codex/gpt-6-astra --qa-model litellm/codex/gpt-6-astra`
selects direct authors and proxy reviewers. See [Pi/Astra](pi-astra.md) for the
provider distinction; the harness neither copies credentials nor configures routes.

`--verify` is an optional argv override, without a shell, and must be the final
option. For development without this override, each implementation author discovers
or creates task checks and selects their exact command in a required top-level
`verification_argv` JSON array. No test command is required before a new app exists.
The host validates the argv and executes it in the actual task workspace after the
author, including remediation authors. It replaces model verification claims with
actual command, exit status, log paths, and observed changes before fresh independent
QA. A supplied override runs unchanged instead of worker selection.

Missing/malformed worker-selected argv fails with an actionable reason before QA
or submission. A command that cannot launch also fails there, retaining the launch
error and empty logs. Executed nonzero exits and timeouts are retained as evidence
for QA. The kernel, not the driver, chooses whether QA's typed verdict triggers
remediation or blocks the run. Command selection and exit zero do not establish
test adequacy or complete coverage; the reviewer judges the retained evidence
against the accepted criteria.
For cognition a supplied verification command runs after each operation, including
partial returns, and is recorded as `content.runtime_verification`. It is an
explicit user command, not a grant of shell tools to cognitive actors.

`--max-activations N` checkpoints after at most N newly executed or recovered
activations, leaving a real **ready** reservation. Zero starts without invoking a
model. Recovery of an already-running complete envelope is reconciled even with
a zero budget; it performs no actor or verification effects. `advance` reuses the
frozen options and the kernel's saved pattern. It does not reread the task file or
accept changed model, verification, or budget configuration. The optional
`--goal-ref` alone is retained in the outer plan only and performs no Telos mutation.

Exit codes for start/advance are 0 for kernel `completed` with no Telos sync error,
2 for an active checkpoint, and 1 for blocked, failed, cancelled, or a Telos sync
failure (even when the pattern completed). Inspect returns 0 on a successful
read and reports any sync error on stderr; its JSON remains pure kernel state.
Cancel returns 0 on a successful request, or 1 if a Telos sync error remains.
A cancellation request may return while the driver is still stopping its child;
inspect again for the kernel's terminal status.

## Shared Driver Capacity

Cooperating CLI and GUI harness drivers using the **same resolved runs root**
share a default limit of **2 active drivers**. Optional `RUNS_ROOT/harness-capacity.json`
sets the policy for every caller; there is no environment or per-run override:

```json
{"max_active_drivers": 2}
```

The file must contain exactly that key with a positive integer (not a boolean,
fraction, or string). Invalid configuration refuses admission. An absent file
means 2. To change it safely, stop new launches from every CLI/GUI using this root,
wait for every driver to exit or checkpoint, then replace the file atomically and
resume launches. Do not edit/remove the configuration during active driving, or
delete/replace `.harness-slot-*.lock` files: their stable inodes are the lock scope.
This is an offline operator policy, not a live-resize interface. Increase the limit
only on evidence from ordinary useful work, not as a host-capacity guarantee.

Linux nonblocking cooperative file locks reject excess requests promptly, without
queuing or replay. CLI reports failure (exit 1); GUI reports HTTP 409 with the root,
limit, and manual retry guidance rather than launched-success. Start admission is
before kernel creation; advance admission is before a ready activation becomes
running. Existing held runs remain available for explicit advance. A driver owns
one slot across sequential actors and verification, releasing it when driving
ends, including pause/checkpoint, failure, cancellation cleanup, or driver death.
Held-ready kernels alone, inspect, pause, cancel, and zero-activation creation do
not consume slots. GUI reserves before spawning and transfers the lock descriptor
to its detached driver, so closing the server does not release that driver's slot.

This bounds cooperating **harness drivers**, not every orphan/descendant, generic
external workflow, local inference service, GPU, or host-wide compute. Abrupt driver
death releases its slot even if a descendant survives; existing ownership and
uncertainty checks still apply and must not be read as a global orphan quota.
Different runs roots have independent limits. Existing per-run and GUI workspace
guards remain in force; this adds no cross-root workspace exclusion.

## Governing Telos Snapshot

Optional start arguments `--telos-chain CHAIN_ID --telos-db DB --telos-source SOURCE`
fetch the genuine aggregate before work. Source accepts a Telos checkout or a
bundled `.mjs`; the default DB is `WORKSPACE/.runtime/telos.sqlite3`. The selected
absolute source and DB paths are frozen in `options.json` for advance.

The kernel receives the unchanged task as `external.purpose`, plus a distinct
`external.governing` artifact containing `chain_id`, `primary_goal`,
`essential_principles`, and the native `reproductive_clause`. A run-local copy of
the pattern requires that artifact at every phase, including QA, remediation,
and returned visits. Bundled pattern files are not changed. The task and outer
plan goal stay stable for Telos run association. `--goal-ref` is not this artifact.

`begin_run` links the run before any actor starts. A failed fetch/link prevents
actor execution; advance can retry a failed link from the saved ready state.
Every drive exit, including a checkpoint, records the current controller result;
idle cancellation also records it. Advance does not refresh the governing snapshot.
See [Telos-linked runs](telos-runs.md) for completion semantics and result-only retry.

## Python API

```python
from pathlib import Path
from scripts.noetic_harness import start, drive, inspect, cancel

run_dir, state = start(
    pattern="development",
    task="Implement the bounded task and explicit criteria here",
    workspace=Path("/path/to/project"),
    runs_dir=Path("/path/to/runs"),
    verify=None,  # Implementation author selects task checks; optional exact argv override.
    client="pi",
    model="openai-codex/gpt-6.1-sol",
    qa_model=None,
    thinking="high",
    max_remediations=1,
    max_returns=1,
    max_activations=0,
    timeout=900,
    inputs={"sources": [{"ref": "requirements.md", "content": "Explicit evidence"}]},
    goal_ref=None,
    telos_chain=None,  # Or an existing genuine Telos chain ID.
    telos_db=None,
    telos_source=None,  # Source directory or bundled .mjs.
)
run_dir, state = drive(run_dir, max_activations=1)
state = inspect(run_dir)
state = cancel(run_dir)
```

`task` is text, not a filename, in the Python API. `start` and `drive` both return
`(Path, kernel_state)`. Inspect and cancel return the actual kernel state, not an
outer journal projection. Telos sync success/error is observed separately through
`noetic_run.project(noetic_run.read_events(run_dir))` as `telos_result`/`telos_error`;
it never changes kernel status. `invoke_actor(run_dir, state, options)` is the model-free
test/trial replacement boundary; it returns
`{"result": <kernel JSON result>, "session_ref": "client:actual-session-id"}`.
Production obtains that identity only from `noetic_develop.parse_transcript`, not
from model-authored result fields. `actor_command` is a narrower protocol-process
test seam; production uses `noetic_develop.client_command`.

## Actor Contract

Every invocation starts a new CLI process/session, without continue/resume/session
reuse flags. The prompt includes the controller ordinal, role, mode, phase,
generation, visit, exact typed input artifacts, phase criteria, feedback history,
and the current `result_contract` JSON Schema. Worker-selected implementation
prompts extend their detached runtime schema with `verification_argv`; the host
retains this proposal in `model-result.json` and removes the extension before the
canonical controller submission. Fixed programs and core result contracts stay
unchanged. `options.json.verification_mode` is `worker-selected`, `supplied`, or
`not-requested`; older options infer it from the saved pattern and verify value.
It does not ask an actor to name
the next activation. Cognitive returns are allowed only by the operation-specific
schema and preserve partial reason/question feedback without forcing a completed
judgment. Development QA names the exact `subject_artifact_id` and supplies
`verdict`, `report`, and typed `findings`.

The final model response must be exactly one JSON object, optionally wrapped in
one `json` code fence. Prose, ACCEPT lines, concatenated objects, duplicate keys,
nonfinite numbers, execution-error streams, and incomplete terminal responses are
refused. The kernel validates the operation-specific content and linkage before
accepting the persisted result envelope. A parse/contract failure stops the run
as `failed`, not as a synthesized QA verdict.

Only implementation authors get edit/write and bash tools. Planning authors and
cognitive operators receive read/search tools. Independent QA gets read/search
and bash for evidence-based checks, but no edit/write/apply-patch tools. Its prompt
forbids product mutation, formatting, installation, snapshot updates, and further
delegation. QA is reasoned, critical, constructive, and non-perfectionistic,
limited to material defects, proportionate risks, and practical remediation
against this phase's criteria. Planning QA must not demand implementation or
tests belonging to a future phase.

Before/after snapshots refuse any read-only actor's result if product files
changed. Changes are retained and **not reverted**. These checks need an available
Git working-file baseline, so read-only roles currently require a Git workspace.
The helper observes tracked and unignored working files, including dirty baseline
files; ignored generated caches are outside that evidence. Use a quiet workspace
for actor execution: concurrent product edits cannot be attributed to an actor
and conservatively cause refusal. This is cooperative role discipline, not an
OS sandbox: QA bash is constrained by the prompt and observed change gate.

The development-only `USER_PROVIDED_PASSWORD` is removed from actor and
verification subprocess environments. Runtime execution does not inherit the
development agent's sudo credential or gain authority to elevate itself.

The host verification command is separate from role permissions. Its effects are
included in implementation change evidence. Cognitive verification
runs after the read-only actor's change gate and may produce user-requested test
artifacts. The driver does not infer correctness from exit zero.

## Retained Evidence

The root is a normal `noetic_run.create_run` directory containing:

- `events.sqlite3`: outer observation journal via `noetic_run.record`.
- `controller.sqlite3`: authoritative shared kernel state and command receipts.
- `options.json`: runtime options frozen at start, never rewritten by advance.
- `task.md`: original bounded task text, distinct from the Telos master purpose.
- `controller.json`: full kernel export after each accepted transition.
- `work.md`: aggregated typed artifacts with provenance and partial-work labels.
- `driver.lock`: retained inode for the cooperative exclusive driver lock.
- `cancel.requested`: durable operator request, when requested through cancel.
- `pause.requested`: durable GUI pause request, checked before the next ready activation.

Each `activations/activation-N/` retains `prompt.txt`, `actor.stdout.log` (the
actual structured transcript), `actor.stderr.log`, `actor-process.json`, parsed
`response.json`, `final-response.txt`, `model-result.json`, `changes.json`,
`changes.diff`, and the complete `submission.json` envelope when available.
Verification has separate `verify.stdout.log`, `verify.stderr.log`, and
`verify-process.json`. Failures retain the evidence available up to the failure;
an unstarted process or unparseable result cannot have complete response files.

Implementation submissions replace model-claimed `changes` and `verification`
with actual observations; the raw model JSON remains separately preserved.
`change_evidence` also records availability, omissions, and manifest/diff paths.
Observed changes are not proof of exclusive authorship. The manifest excludes
this run's bookkeeping if the run directory is inside the workspace. The reused
helper's raw diff can contain that bookkeeping; prefer an external runs directory
or ignore the runtime directory in the project to avoid noisy raw diffs.

`controller.state` observations contain actual complete kernel snapshots;
`controller.event` observations preserve the kernel event IDs and data. Export
reconciliation uses SQLite authority and fills missing observations on advance.
The two databases are not an atomic cross-database transaction. A crash may omit
an intermediate snapshot, but the latest state and ordered kernel events remain
recoverable. Outer observations never allocate or advance roles.

Terminal `run.finished` uses exactly `completed`, `blocked`, `failed`, or
`cancelled`. A completed development pattern includes its phase-specific QA
passes; a completed cognitive pattern means its cognitive completion transition.
Neither is automatically generic acceptance or Telos master-goal completion.
The adapter never calls the legacy `review_run` or fabricates its acceptance.

## Cancellation And Recovery

The GUI's pause-after-current action does not interrupt a running actor. The
driver finishes and submits the current activation, then holds before executing
the ready successor. GUI advance or `noetic harness advance RUN_DIR` clears that
held pause and uses the saved reservation. There is no CLI `pause` subcommand.
Requested pause and applied hold are distinct; owning a driver lock alone does
not establish model progress or liveness.

The local Linux/POSIX adapter holds a nonblocking `flock` for the whole drive.
A second driver raises `DriverBusy`. Cancel writes a request without taking
ownership of the first driver's child. The driver polls at 50 ms intervals and
uses the existing `noetic_run.stop_process` to stop the process group, including
surviving children. SIGTERM and Ctrl-C install the same cleanup path for callable
driving on the main thread. In a worker thread, use `cancel(run_dir)` instead of
process signals. Cleanup may take the helper's two-second termination grace.

`submission.json` is written atomically only after the actor response, change
gate, and requested verification are complete. It contains the original expected
version, result, transcript-derived session reference, and stable command ID.
Reopening a running activation with this envelope submits it without rerunning
the actor or verification; the kernel provides idempotent command delivery.
After an interrupted post-commit export, inspect the kernel instead of treating
the stale JSON projection as authority.

A running activation **without** a complete envelope becomes kernel `failed`
with `runtime_uncertain` and an explicit no-auto-replay reason. Even a complete
transcript alone does not prove the verification/change-check sequence finished.
Unexpected exceptions at the test seam can simulate this after-actor window.
There is no automatic reconstruction of a missing envelope, retry of side effects,
or resurrection of a failed run. After an uncatchable kill or host crash, an
operator must reconcile any orphan runtime process and workspace effects before
starting a new run; the driver does not kill a possibly reused historical PID.

## Verification Scope

```bash
python -m unittest discover -s tests/programs -p test_noetic_harness.py
python -m unittest tests.programs.test_harness_dynamic_checks
python -m unittest tests.programs.test_harness_integration tests.programs.test_noetic_cli
```

Tests use real temporary SQLite stores and mocked actor/protocol commands,
including real local subprocesses for transcript parsing, verification, failures,
timeouts, cooperative cancellation, SIGTERM, and Ctrl-C. They cover all four
development phases with remediation, failed-check QA evidence, cognitive backedges
and rebuilding, session separation, typed parsing, product mutation refusal,
checkpoints, and no-replay recovery. Integration tests also use the actual Telos
source factory and relocated bundle with temporary databases and fixture actor
results through this driver and kernel. They cover every governing binding,
distinct completion boundaries, stale legacy acceptance, corruption refusal,
record-only retry, relocation, idempotence, and CLI sync-gap reporting. These tests
call no live models. Separate independent integration QA accepted the scoped
CLI/Telos/packaging unit, including installed-wheel tests against the genuine
relocated Telos module and temporary databases.

The independently accepted kernel/driver's bounded live development trial
`07b2162319ee4a1d8ea43497437f4c54` used ten fresh Pi actors with direct authors,
proxy QA, and implementation remediation. Cognitive trial
`690bab0bab384ad69b29f633036960e3` completed P1/P2/P1/P2/P3/P4 with six fresh
OpenCode actors. The development trial deliberately overwrote the first author's
real edit before verification: controlled fault recovery, not a natural author
defect. Neither trial proves every task or model capability.

Separate application QA accepted a real source-GUI four-phase development run
`41f4a996beeb41f5a736f07f3087178d`: eight fresh Pi actors, native Astra authors,
proxy QA, and no remediation. Later installed-production GUI evidence for
`4cd0d3f4757f4d9e83b37b58a5e95caf` establishes pause requested during an actual
running P1 actor, an unexecuted ready P2 successor, and resume to typed P4
completion. These close the specific GUI operation gaps, not general semantic
correctness, authentication lifetime, or uninterrupted model availability.
