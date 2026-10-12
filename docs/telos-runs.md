# Telos-Linked Runs

`scripts/noetic_telos.py` connects noetic run journals to the **existing Telos
CoreGoalChainManager**. The small Node subprocess imports
`createPiCoreGoalChainStore` from a standalone Telos ES module or from
`packages/pi-runtime/src/core-goal-chain-store.ts` in an explicit source root.
It calls the same factory with `{dbPath}` in either mode. It does not implement
another goal engine or use the live OpenCode goalchain store.

## Pattern Harness

The primary integration is the real controller, not the legacy work/review task:

```sh
noetic harness start development task.md --workspace /path/to/project \
  --client pi --model openai-codex/gpt-6-astra --thinking high \
  --telos-chain CHAIN_ID --telos-db /path/to/project/.runtime/telos.sqlite3 \
  --telos-source /path/to/components/telos-core.mjs \
  --verify python3 -m unittest discover -s tests
```

The same Telos arguments apply to `start cognition`; verification is optional
there. The driver fetches the genuine aggregate before work and binds its master
purpose, essential principles, and reproductive clause as **`external.governing`**.
A run-local pattern copy requires that artifact in all four phases, including
reviewers, remediation authors, and cognitive returns. `external.purpose` and
the journal goal remain the original bounded task, so the association is stable.
Neither a `--goal-ref` label nor a prefixed task substitutes for this binding.

`begin_run` creates/reuses the run's subgoal before the first actor. Frozen source
and DB options survive `advance`; the governing artifact is not refreshed midrun.
The driver updates the result after driving, terminal outcomes, or checkpoints,
using current `controller.sqlite3` authority, not the exported JSON or a legacy
accepted label. See [harness runtime](harness-runtime.md) for APIs and budgets.

| Current authority | Run subgoal disposition | Meaning |
| --- | --- | --- |
| Controller `completed`, `verified_sequence` | `complete` | `four_phase_qa_completion`: design intent, abstract design, implementation procedure design, and implementation passed their phase-specific QA. |
| Controller `completed`, `recurrent_operations` | `complete` | `responsible_cognitive_completion`: the current P1/P2/P3 artifacts support the terminal P4 output. No generic QA is invented. |
| Controller active, failed, blocked, or cancelled | `active` | No completion boundary was reached; actual state/reason are retained. |
| Controller corrupt or missing its typed completion boundary | Error, no result write | Never fall back to a legacy accepted label. |
| No controller database | Legacy rules below | Accepted command/task runs still require their actual legacy review. |

The kernel is authoritative about accepted transitions; the bridge does not
rejudge content or manufacture `review.recorded`. The **master chain is never
completed** by a run result. Completion describes the selected pattern, not
universal success, full product acceptance, or exhaustive correctness.

## Result Retry

Telos and the run databases do not share a transaction. A result-write failure
appends a separate `telos.error`; it does not erase kernel completion or rerun
actors. `noetic harness start/advance` exits **1** when that sync gap remains,
even if it also reports `Kernel status: completed`. Retry only metadata:

```sh
noetic goal record CHAIN_ID SUBGOAL_ID RUN_DIR --db /path/to/telos.sqlite3 \
  --source /path/to/components/telos-core.mjs
```

Use the retained `telos.linked` IDs. A successful retry appends `telos.result`,
clearing the current error projection while retaining its history. Repeating the
same result does not duplicate Telos notes or run observations. If the core write
succeeded but observation writing failed, retry fills the observation without
repeating the core learning. Advancing an already-completed run also retries sync
without executing an actor, but `goal record` is the explicit result-only path.

## Prerequisites And Isolation

- Node 24 on `PATH`.
- A bundled `.mjs` component, or a local Telos checkout with
  `node_modules/tsx/dist/loader.mjs` already installed.
- Source selection: `--source`, then `NOETIC_TELOS_SOURCE`, then `~/workspace/telos`.
  Both the option and environment variable accept a source directory or `.mjs` file.
- The default database is `.runtime/telos.sqlite3` under the invoking working
  directory, so an installed CLI never writes into its package directory. Use `--db`
  for another project's isolated file or a temporary test database. Never point it
  at a live runtime store.
- Every factory invocation supplies the absolute database path. Telos's native
  global-store default and `TELOS_STATE_DIR` are not used. `scope: "global"` means
  global **inside this isolated file**, avoiding project foreign-key registration.

No model calls, donor edits, package installs, global configuration changes,
live-session migration, or full Telos migration are part of this connection.

## Standalone Component

On the build machine, use the existing Telos checkout's esbuild installation:

```sh
noetic goal bundle --source /path/to/telos --output /path/to/components/telos-core.mjs
```

From this repository without installing noetic, use
`python3 -m scripts.noetic goal bundle` with the same options. Both options are
required for bundling; `--source .` builds from the current directory. The command
runs `<source>/node_modules/esbuild/bin/esbuild` on the existing factory with
`--bundle --target=node24 --format=esm --platform=node`, leaving Node builtins
external. It does not install dependencies or edit the donor checkout.

The output module exports the actual `createPiCoreGoalChainStore`. Its adjacent
`telos-core.manifest.json` contains the module SHA256, source path, entrypoint,
build target, and the identity **built from current source including possible
uncommitted changes**. This describes current working contents, not a pristine
commit or release. The CLI returns JSON with `module`, `manifest`, and `sha256`.
Output parent directories are created as needed; existing output files are replaced.

Deploy the `.mjs` wherever components are kept and retain the manifest for build
identity. The manifest is not a runtime gate. The module is independently deployable,
not vendored into the noetic Python package. After relocation, select it explicitly:

```sh
export NOETIC_TELOS_SOURCE=/path/to/deployed/telos-core.mjs
noetic doctor
noetic goal create "Realize noetic-dev incrementally" --db /path/to/project/.runtime/telos.sqlite3
```

Module mode launches plain Node without `--import tsx`. The bundled Telos runtime
needs Node 24 and the selected SQLite database (created if absent), not the source
tree, tsx, esbuild, Pi SDK, or OpenCode. The noetic CLI still needs its Python
installation and packaged bridge. `doctor` reports `telos_mode` as `module` or
`source`, `telos_factory_present` for the selected entrypoint, and
`telos_loader_required`; `telos_loader_present` is `null` in module mode because
tsx is inapplicable. Doctor checks presence, not module exports or Node compatibility.

## CLI

Run from this repository root; commands emit JSON. Substitute IDs returned by
Telos and an actual existing noetic run directory for the example placeholders.

```sh
python3 scripts/noetic_telos.py create "Realize noetic-dev incrementally" --source /home/dgk/workspace/telos
python3 scripts/noetic_telos.py get CHAIN_ID --source /home/dgk/workspace/telos
python3 scripts/noetic_telos.py attach CHAIN_ID .runtime/runs/RUN_ID --source /home/dgk/workspace/telos
python3 scripts/noetic_telos.py record CHAIN_ID SUBGOAL_ID .runtime/runs/RUN_ID --source /home/dgk/workspace/telos
python3 scripts/noetic_run.py events .runtime/runs/RUN_ID
```

`create` creates an active master goalchain with no run subgoals yet. `attach`
associates an already-created run, including an already-accepted run, and records
its current disposition. Repeating it for the same chain and journal `run_id`
with the same goal reuses the subgoal, even after relocating the archive or copying
its Telos database. `record` refreshes the disposition of that exact run's subgoal;
a mismatched run/subgoal pair or changed goal under the same run ID is rejected. Options
belong after the subcommand. A zero CLI exit means the bridge operation succeeded,
not that the run was accepted.

## Python API

```python
from pathlib import Path
from scripts import noetic_run, noetic_telos

db = Path(".runtime/telos.sqlite3").resolve()
source = Path("/home/dgk/workspace/telos")
aggregate = noetic_telos.create_goal("Realize noetic-dev incrementally", db, source)
chain_id = aggregate["chain"]["chainId"]

# Usually the harness calls these automatically around controller execution:
link = noetic_telos.begin_run(chain_id, run_dir, db, source)
# Drive the real controller, then record its current typed result.
result = noetic_telos.record_result(chain_id, link["subgoal_id"], run_dir, db, source)
reopened = noetic_telos.get_goal(chain_id, db, source)
```

- `bundle_goal_store(source, output)` builds the standalone component and returns
  absolute `module` and `manifest` paths plus `sha256`; it does not open a database.
- Every runtime API's `source` argument also accepts the bundled `.mjs` path.
- `create_goal(goal, db=DEFAULT_DB, source=None)` returns the native Telos aggregate.
- `get_goal(chain_id, db=DEFAULT_DB, source=None)` reopens that aggregate. Its keys
  are `chain`, `reproductiveClause`, `subGoals`, and `records`, using Telos's native
  camelCase field names. A missing chain raises `ValueError`.
- `begin_run(chain_id, run_dir, db=DEFAULT_DB, source=None)` requires an existing
  noetic journal. It returns `chain_id`, `subgoal_id`, `db_path`, `source`,
  `artifact_path`, and `journal_path`, and appends these as a `telos.linked` event
  through `noetic_run.record` when they differ from the latest link. Repeating
  the call at the same location with the same database and source does not duplicate
  that link or reset an already-completed subgoal.
- `record_result(chain_id, subgoal_id, run_dir, db=DEFAULT_DB, source=None)` reads
  the journal for run identity and reads `controller.sqlite3` whenever present.
  It never accepts a caller-supplied success flag. It returns the link plus
  `run_id`, `state`, `reviewer`, `verdict`, `artifact_path` (the current run
  directory), `journal_path`, and `subgoal_status`.

Controller results additionally carry `authority`, `reason`, `pattern` (name,
kind, version), `controller_version`, `completion_boundary`, `terminal_artifact`,
`terminal_output`, `governing_artifact_id`, and `actor_refs`. Terminal references
include artifact ID/type/digest and producer/activation IDs. For development the
terminal artifact is the final typed QA report, and the terminal output is its
accepted implementation subject; for cognition both reference P4. Noncompleted
runs have null terminal references and completion boundary. Actor references
retain ordinal, role, phase, mode, status, activation ID (`id`), actor ID,
session reference, and result artifact ID, including earlier remediation/return
visits. Controller `reviewer`/`verdict` are null: there is no generic review.

The result note in Telos records begins `noetic.run.result ` followed by JSON.
For **legacy runs without a controller**, only `state == "accepted"` with an actual accepting review, named reviewer, and
nonempty retained evidence completes **that run's subgoal**. Failed, rejected,
unfinished, awaiting-review, or accepted-without-review results remain active.
Command exit zero never supplies semantic acceptance. The master chain is never
completed by this bridge. Completion retains the result note as a Telos learning;
all dispositions also get a chain note. Repeating an identical disposition does
not duplicate the note or status update.

## Archive Relocation

New subgoal objectives use `noetic run RUN_ID\nGOAL`, independent of the archive
location. Matching also recognizes the previously persisted canonical form
`noetic run RUN_ID at ABSOLUTE_RUN_DIRECTORY\nGOAL`. Both forms check the complete
goal text, retaining the existing objective's trailing-whitespace trimming. Run IDs
are scoped to the selected chain; a different goal under the same ID is an error,
not a reason to create or complete a different subgoal. If multiple subgoals already
match that run ID, both `attach` and `record` report ambiguity without selecting,
deleting, or merging them, even when `record` supplies one of their subgoal IDs.

Copy the archive with its journal and retained artifacts, and select the original
or copied Telos database with `--db`. Use SQLite's backup API to copy an open database,
not a naive copy of its live database/WAL files. Reattach using the existing chain
ID, or record using the existing chain and subgoal IDs. No prior objective, Telos
note, event (including `run.created.workspace`), or review text is rewritten.
Historic paths remain historic. New result notes carry the current artifact and
journal paths; new `telos.linked` and `telos.result` observations carry the current
paths, database, and component source. Repeating the operation at that location is
idempotent. Include `controller.sqlite3` when archiving a harness run and use its
backup API too if open. Relocation does not supply acceptance or bypass the typed
controller boundary (or the review requirement for a legacy run). `goal record`
can select relocated DB/source paths without rewriting frozen run options.

## Checks And Limits

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.programs.test_noetic_telos -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.programs.test_harness_integration -v
```

The tests use the actual local factory with temporary SQLite databases and real
local command runs. They exercise both source mode and an esbuild-built module
relocated away from its build directory, including create/get/attach/record and
linked development. Bundle checks inspect the hash, exported factory, builtin-only
imports, and plain-Node launch with no client/build tools on runtime `PATH`.
Relocation checks seed legacy objectives through the core manager, back up SQLite
databases, and copy accepted and nonaccepted command-run archives. They check stable
subgoal reuse, preserved history, current paths, repeat idempotence, and refusal of
changed goals and ambiguous historical duplicates in both runtime modes.
Review evidence in tests is explicitly test-authored, not a claim of independent
product QA. Integration checks skip with an explicit reason if Node 24 or the
source factory is unavailable; source tests additionally require tsx and bundle
tests require esbuild. No model is invoked. Building from changed Telos sources
requires rerunning these checks; the manifest does not certify compatibility.

Harness integration checks run fixture actors through the real kernel and driver,
with actual source and bundled Telos stores. They exercise phase-wide governing
bindings, cognitive returns, development remediation, distinct completion,
noncompletion, corrupt authority refusal, result retry/idempotence, and CLI errors.
They are implementation checks, not the lead-owned independent integration QA.

This is cooperative local integration, not a multi-writer transaction or
reconciliation system. Telos and run-journal writes are separate; retrying an
attachment normally reuses its run association and fills in a missing observable
link. Moving a run directory does not change its identity; changing its recorded
run ID or goal is not relocation. No automatic historical-duplicate cleanup is provided.
The bridge relies on the controller's typed boundary or the legacy review contract;
it does not independently authenticate reviewers or rejudge their findings.

## Legacy Task Integration

`develop`/`inquire` remain legacy task utilities, not the original pattern harness.
Pass an existing chain to that agent workflow to fetch its governing purpose,
link the run before execution, and record its reviewed outcome automatically:

```sh
python3 scripts/noetic_develop.py task.md --workspace . \
  --client opencode --model openai/gpt-6-astra \
  --telos-chain CHAIN_ID --telos-db .runtime/telos.sqlite3 \
  --telos-source /home/dgk/workspace/telos \
  --verify python3 -m unittest discover -s tests
```

The development runner defaults its Telos database to the selected workspace's
`.runtime/telos.sqlite3`. `--telos-source` also accepts a bundled `.mjs`, or omit it
to use `NOETIC_TELOS_SOURCE`. It fetches the purpose before work, then links the run
and makes that purpose available to worker and reviewer. Failed or unreviewed
outcomes are retained without completing the subgoal. A Telos result-write
failure is separately visible in status and makes the development CLI exit
nonzero; it does not erase an independently accepted review. Use `record` to
retry that metadata write without rerunning the work.
