# Bounded Batch Workflows

`noetic batch` carries a small, explicit set of tasks through the existing
`develop` / `inquire` runtime, sequentially. Each child retains its own work,
verification, independent review, and event journal. The controller does not plan
with a model, approve work, retry effects, or mark the governing goalchain complete.

## Manifest

Write a JSON manifest with a name and 1 to 32 tasks:

```json
{
  "name": "Small feature delivery",
  "tasks": [
    {
      "id": "inspect",
      "program": "inquire",
      "task": "tasks/inspect.md",
      "depends_on": []
    },
    {
      "id": "implement",
      "program": "develop",
      "task": "tasks/implement.md",
      "depends_on": ["inspect"],
      "verify": ["python3", "-m", "unittest", "discover", "-s", "tests"]
    }
  ]
}
```

Task IDs must be unique nonempty strings. Every dependency must name a task in
the manifest; cycles are errors. Each task file must be a nonempty UTF-8 file,
with its path resolved relative to the manifest, not the workspace or shell's
current directory. `program` is either `develop` or `inquire`.

`verify` is a nonempty command argument array, required for development and
optional for inquiry. It runs in the selected workspace, without an implicit
shell. The controller checks argument shape and executable availability before
starting any child. It does not run the verification during preflight or infer
file arguments inside arbitrary commands. Files produced by earlier tasks may
be consumed by later verification commands; the executable itself must already
exist. Shell scripts can be selected explicitly, for example `["sh", "check.sh"]`.

The execution order is a stable topological order: after each selected task,
choose the first dependency-ready task in original manifest order. Dependencies
must have accepted child journals before their dependents execute. An unrelated
task is not an escape hatch around a failure: any nonaccepted child stops the
whole batch.

## Run

```sh
noetic batch run ./delivery.json \
  --workspace /path/to/project \
  --runs-dir /path/to/project/.runtime/runs \
  --batches-dir /path/to/project/.runtime/batches \
  --client opencode \
  --model provider/model \
  --telos-chain EXISTING_CHAIN_ID \
  --telos-source /path/to/telos/bundled.mjs
```

`--client pi` is also supported. Optional flags are `--review-model`, `--timeout`
(seconds per process, default 900), `--goal-ref`, and `--telos-db`. Telos is
optional; when used, the source may be a source directory with its installed
tsx loader or a bundled `.mjs` file. Telos's default source is resolved once at
batch creation. The database defaults to `WORKSPACE/.runtime/telos.sqlite3`.
The existing chain is passed to each child through `develop`, which owns its
Telos association and result. The batch never changes parent-chain status.

Workspace defaults to the current directory; the two output roots default to
`WORKSPACE/.runtime/runs` and `WORKSPACE/.runtime/batches`. Explicit absolute
paths make it straightforward to use the same runs root in the UI and memory.

All tasks, files, dependency relationships, verification arrays, and local
execution prerequisites are checked before work starts. The controller then
prints a new `BATCH_DIR`, containing `batch.json`: frozen task text, task order,
batch UUID, and resolved execution options. The file is flushed before launching
any child. Changes to the original manifest, task files, or invoking directory
do not change an existing batch. Do not edit `batch.json` to steer execution;
create a new batch for revised inputs.

Children are stored **directly in the common runs root**, not inside the batch
directory. Their IDs are `uuid5(batch_uuid, task_id).hex`. Existing UI, run
listing, and memory discovery therefore need no batch-specific storage changes:

```sh
noetic list --runs-dir /path/to/project/.runtime/runs
noetic serve --runs-dir /path/to/project/.runtime/runs
```

## Status And Resume

```sh
noetic batch status /path/to/batches/BATCH_UUID
noetic batch status /path/to/batches/BATCH_UUID --json
noetic batch resume /path/to/batches/BATCH_UUID
```

Status reads the child journals afresh. There is no cached success flag, batch
state database, or batch acceptance event. JSON includes batch identity, state,
and ordered tasks with child IDs, directories, observed states, and dispositions.

| Observed Child | Resume Behavior |
| --- | --- |
| Accepted with recorded review evidence | Skip without invoking a model |
| Child directory absent | Execute once, only after dependencies are accepted |
| Failed, rejected, timed out, interrupted | Hold; preserve evidence; no automatic rerun |
| Awaiting review or unfinished | Hold; work may still be running or effects may already exist |
| Existing path without a journal, or unreadable/mismatched journal | Hold; needs explicit disposition |
| Accepted but a Telos synchronization error is recorded | Hold for synchronization disposition; never repeat accepted work |

Batch state is `ready` when further execution is possible, `held` when any
existing child needs disposition, and `complete` only when every child is
accepted without an outstanding Telos error. `complete` is a derived batch
summary, not a claim that the master goal has been achieved. A complete resume
performs zero model invocations and does not require the clients to remain
installed. `status` reports observations, not process liveness or ownership.

`run` and `resume` return exit code 0 only for a complete batch; held batches and
errors return 1. A successfully read `status` returns 0 even for a held batch;
use its JSON state when scripting. A launcher failure before creating any child
returns an error rather than fabricating an outcome. Such an absent child
remains eligible on a later explicit resume.

Inspect held runs with `noetic status CHILD_DIR` and `noetic events CHILD_DIR`,
including their logs and changes. An awaiting-review run can receive an actual
separately obtained review through the existing `noetic review` command. Once
the child journal records acceptance, resume can observe it without changing
`batch.json`. For failed, rejected, or ambiguous effects, resolve the workspace
state explicitly and use a new scoped task/batch when more work is authorized.
Do not delete old child directories to force execution; retain them as evidence.

## Limits

- At most 32 tasks, one child at a time. No scheduler, model planner, retry policy,
  automatic repair, or new approval mechanism.
- Execution is POSIX-only. A cooperative `flock` on `BATCH_DIR/.execution.lock`
  rejects concurrent controllers for that batch. The OS releases the lock when
  the controller exits; a leftover lock file is harmless and must not be deleted
  to bypass an active controller. This does not serialize different batches or
  unrelated tools working in the same workspace.
- Interrupted children are not resumed at an internal step. Existing ambiguous
  effects require disposition, even if the process that produced them has exited.
- Frozen inputs are not a workspace snapshot. The controller does not snapshot
  client installations, configured default models, environment, Telos content,
  or arbitrary verification dependencies. Select explicit models for repeatable
  routing. Local prerequisites for remaining work are rechecked on resume.
- Task files should state useful acceptance criteria and artifact paths. Each
  declared dependency supplies its accepted run directory and controller-observed
  verification/reviewer result to both the next worker and reviewer. OpenCode
  permits access to those context directories. Reports are read on demand rather
  than pasted wholesale. These are historical observations, not new authority;
  no model rewrites later task text or the frozen manifest.

## Python API

`scripts.noetic_batch.create_batch(manifest, workspace, runs_dir, batches_dir,
client="opencode", model=None, review_model=None, timeout=900, goal_ref=None,
telos_chain=None, telos_db=None, telos_source=None)` preflights and freezes inputs,
returning a `Path` without launching work. `resume_batch(batch_dir)` executes
eligible children and returns a journal-derived status dictionary.
`batch_status(batch_dir)` is read-only.

`scripts.noetic_run.create_run(..., run_id=None)` and
`scripts.noetic_develop.develop(..., inquiry=False, run_id=None)` accept a known
32-hex UUID for deterministic children. Omitted IDs still generate fresh random
UUIDs. Invalid IDs fail before directory creation, and existing run directories
are never overwritten.

Focused, model-free checks:

```sh
python3 -m unittest discover -s tests/programs -p 'test_noetic_batch.py' -v
```

These tests use temporary directories, actual SQLite journals, mocked launchers,
and test-authored client protocol commands. They are implementation checks, not
independent approval of a delivery or a real model-driven batch demonstration.
