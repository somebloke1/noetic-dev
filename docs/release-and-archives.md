# Private Releases and Run Archives

These standalone module commands implement bounded owner-operated delivery, not
publication or an automatic updater. Noetic remains all rights reserved under the
unchanged `LICENSE.md`. The exact Telos MIT notice in
`docs/THIRD_PARTY_NOTICES.txt` is copied byte-for-byte, including its source wording.
The assembler checks this documentation baseline by SHA-256; this is not signing,
a trust root, license clearance or permission to redistribute.

## Requirements

- POSIX Linux, Python 3.10+ with `venv` and pip available, and Node 24 for Telos.
  Build, install/update and rollback check major version 24 and import
  `node:sqlite` to verify `DatabaseSync` availability, without opening a database.
  Syntax compatibility alone (for example on Node 18) is insufficient.
- An explicitly selected private app directory, not a checkout, ordinary home,
  donor repository, global installation or existing runtime state directory.
- Provider clients, accounts, credentials and models supplied separately by the
  owner. No Python/Node runtimes, provider clients or credentials are bundled.
- An actual core-dependency-free `noetic_dev-VERSION-py3-none-any.whl` containing these
   modules and the packaged runtime/web assets. Current source version is 0.3.0;
   version is read from the wheel, not invented here. Bounded independent acceptance
   and exact installed-release limits are recorded in
   [release requirements](release-requirements.md#evidence-boundary), not inferred
   from the version number alone.
  The one admitted optional dependency is `mcp>=1.0; extra == "genus"` with
  `Provides-Extra: genus` declared. Equivalent quote and whitespace spelling is
  accepted; other requirements or compound/platform markers are refused. The
  core installation needs no SDK. The owner supplies the optional official MCP
  SDK separately when selecting the genus integration.
- An actual bundled `telos-core.mjs` and its matching ESM/node24 SHA-256 manifest.
  Installed use does not need donor TypeScript, tsx or a developer checkout.

## Assemble and Install

All asset paths are explicit; documents can be repeated with `--doc`. ZIP is the
single supported container. The build validates wheel RECORD hashes, metadata,
format and the complete required runtime asset set (including harness,
application, access, local/semantic modules, their runtime dependencies, both
patterns, and HTML/JS/CSS), Telos manifest fields/hash and JavaScript syntax
(`node --check`), and legal baseline. It does not execute supplied code or
establish the provenance of an arbitrary wheel. Use the actual owner-built wheel
and reviewed Telos bundle.

```sh
python -m scripts.noetic_release build /private/delivery/noetic.zip \
  --wheel /private/build/noetic_dev-0.3.0-py3-none-any.whl \
  --telos-module /private/components/telos-core.mjs \
  --telos-manifest /private/components/telos-core.manifest.json \
  --license-file LICENSE.md --notices docs/THIRD_PARTY_NOTICES.txt \
  --doc docs/getting-started.md --doc docs/release-and-archives.md
```

The ZIP includes the bootstrap modules copied from that same wheel, so the
recipient can install directly from it without extracting into a checkout:

```sh
PYTHONPATH=/private/delivery/noetic.zip python3 -m scripts.noetic_release install \
  /private/delivery/noetic.zip --home /private/noetic-app
/private/noetic-app/bin/noetic --help
```

Only local wheel installation is used (`venv --copies`, pip `--no-index --no-deps`).
The optional extra metadata is retained, but installation selects no extras and
installs no SDK, provider clients or services.
No global configuration or `~/.local/bin` entry is changed. `--python` selects an
existing Python executable. Python venv support must already be installed; this
tool does not elevate or install system packages.

Layout:

```text
APP_HOME/
  bin/noetic                       # private launcher, 0700
  current -> releases/VERSION-DIGEST
  releases/VERSION-DIGEST/          # retained code, wheel, assets and venv
  state/                           # private data, outside versioned code
```

The launcher selects bundled Telos through `NOETIC_TELOS_SOURCE` by default;
an explicit environment override still works. `NOETIC_APP_HOME` and
`NOETIC_STATE_HOME` are exposed for operator scripts. Selected installed releases
preserve the caller's working directory, including relative task and data paths.
The launcher removes `PYTHONPATH` and `PYTHONHOME` and uses the selected release's
isolated interpreter; provider environment and explicit token paths remain
operator supplied. The top-level installed
`serve` and `list` commands default to `NOETIC_STATE_HOME/runs`; an explicit
`--runs-dir` still wins. Other data commands retain their existing explicit-path
interfaces. Select persistent data paths explicitly for those commands:

```sh
/private/noetic-app/bin/noetic serve \
  --runs-dir /private/noetic-app/state/runs \
  --token-file /private/noetic-app/state/.operator-access/token
```

Core authentication prints the private pairing URL. Keep that URL and token
private. For Telos operations select `--db /private/noetic-app/state/telos.sqlite3`.
Do not put data in `current`, a release directory or the working directory by
relying on an unrelated command's defaults. Do not move an installed app home:
venv scripts and the launcher contain its installation path.

## Update and Rollback

Stop the server/launchers and quiesce independent drivers before maintenance.
Closing the browser or stopping the web server alone does not stop independent
drivers. These commands are not a service manager and cannot prevent an operator
or a noncooperating process from starting new work during maintenance.

```sh
/private/noetic-app/current/venv/bin/python -m scripts.noetic_release status \
  --home /private/noetic-app
/private/noetic-app/current/venv/bin/python -m scripts.noetic_release install \
  /private/delivery/next.zip --home /private/noetic-app --allow-held
/private/noetic-app/current/venv/bin/python -m scripts.noetic_release rollback \
  0.3.0-0123456789abcdef --home /private/noetic-app --allow-held
```

Use an actual ID returned by `status`. Install is also the update command; previous
releases are retained. A release ID is wheel version plus a 16-hex manifest digest,
so different bundles of one version coexist. Rollback selects a retained code
directory and checks its payload checksums/schema before switching the pointer.
It also compares actual installed package files in that release's venv against
the wheel, including modules and patterns. Only the installer-rewritten wheel
`RECORD` is excluded; installer-added metadata/bytecode is not wheel payload.
Missing or changed installed payload refuses the switch, without repairing code
or changing the current pointer or run history. Install performs the same check.
There is no state downgrade, database migration, actor replay or model invocation.
Installation runs venv/pip, Node's capability and syntax checks, isolated Python
package-path inspection and the installed CLI's `--help` smoke check, never Telos
operations or models.

Ordinary maintenance checks journals beneath the selected `APP_HOME/state`, holds
known cooperative execution locks, refuses running activations and unfinished
process observations, and supports controller schema 1 only. `--allow-held` explicitly
permits an unowned schema-1 active run whose current activation is ready. This
preserves that reservation unchanged; it does not run it. Non-controller journals
must have a supported terminal observation. Unknown schemas are refused.
State outside this home is not discovered unless explicitly adopted below. No automatic rollback is
attempted after a process/power failure; inspect `status` before retrying. A failed
pre-switch installation removes its new code directory, never selected state.
If launcher writing has begun before a failed pointer switch, the previous
launcher bytes and mode are restored; an initial installation removes its newly
written launcher. Once the pointer selects the new release, that release and
launcher are retained if writing the maintenance result subsequently fails.
The next install recognizes only the exact generated v2 launcher or its exact
v1 predecessor for the same app home and persisted adoption binding. Modified
or unrecognized launchers are refused. Rollback switches code selection; it
does not downgrade the managed launcher generation.

## Bounded Legacy Adoption

For a legacy uv installation whose actual state is outside the release home,
adoption binds a **new dedicated code home** to that existing state. It does not
copy, relocate, replay, migrate, delete or recursively chmod history, read provider
configuration into the new installation, update uv, or change a public launcher.
The operator must stop the old GUI and all writers/launchers before the operation
and keep them stopped until the desired launcher is selected. Existing driver,
application and capacity locks are held read-only during code-only maintenance;
missing locks are not created. Existing recorded process ownership is inspected
independently of task or controller history. These are cooperative checks, not a
host-wide quiescence claim or prevention of a noncooperating/new writer.

Use a freshly built ZIP containing this adoption implementation, not a previously
prepared 0.3.0 ZIP. The release version alone does not identify its implementation.
For the reported 0.2.0 uv layout, substitute a new private code home and the new
artifact path in this example:

```sh
PYTHONPATH=/private/delivery/new-noetic.zip python3 -B -S -m scripts.noetic_release install \
  /private/delivery/new-noetic.zip --home /private/noetic-adopted \
  --code-only \
  --adopt-state /home/dgk/workspace/synthesis-worktrees/feature-cognitional-event-journal/.runtime \
  --legacy-launcher /home/dgk/.local/share/uv/tools/noetic-dev/bin/noetic \
  --legacy-cwd /home/dgk/workspace/synthesis-worktrees/feature-cognitional-event-journal
/private/noetic-adopted/bin/noetic release status
/private/noetic-adopted/bin/noetic list --json
```

`--legacy-launcher` must name the retained original executable, **not** the public
symlink that the operator will later switch. Preserve its uv environment in place.
`--legacy-cwd` records the original working/configuration root for explicit
`rollback legacy` selection. Only that selection changes to the retained cwd
and invokes the original launcher with its historical startup checks. Normal
selected releases preserve the caller's cwd and bind the adopted store through
`NOETIC_STATE_HOME`; adoption does not make the recovery checkout their working
environment. This launcher change does not unify command-specific data defaults
or establish project/effort scope resolution.
No provider environment values are captured or copied; the operator supplies the
same intended runtime environment when starting the application.

`adoption.json` stores these absolute paths in the new home. Every later update
and rollback uses the bound external state, even from outside the checkout. The
explicitly adopted state path may be absent; code-only maintenance retains that
binding without creating an empty substitute. Ordinary maintenance still refuses
a missing external root. Modern release help/version and release status remain
available when the legacy cwd or historical state is unavailable. Operations
that require a particular journal retain their existing missing-journal error.
The current `list` implementation returns `[]` for an unavailable runs directory
without creating it; it does not yet distinguish absent from empty history.
No `APP_HOME/state` is created for an adopted installation. Installed
`noetic release` defaults `--home` to its own `NOETIC_APP_HOME`.

Use `--code-only` for each repair-code install or rollback that must remain
independent of retained product history. The bootstrap does not import the run,
controller or harness modules, read product databases, interpret cognitive/task
completion, or require historical semantic transitions. Corrupt, unreadable,
unsupported and incomplete journals/controllers, held reservations and retained
SQLite WAL/SHM/recovery sidecars do not prevent code activation. No history is
created, migrated, repaired, checkpointed, replayed or discarded. `--allow-held`
controls ordinary maintenance only; code-only maintenance does not assess held
reservations.

Code-only maintenance inventories the existing selected tree without reading
historical file contents, acquires its existing cooperative locks read-only, and
inspects all existing `*-ownership.json` records, including records outside
recognized runs. Busy locks, known live owned groups, and malformed, mismatched
or uncertain recorded ownership remain concrete process-safety blockers. Valid
ownership from a different verified kernel boot confirms ended process lifetime
without probing or signalling reused PIDs/groups. Missing or malformed boot IDs
remain unconfirmed. The operator must stop writers and resolve concrete process
blockers independently; historical completion or corruption cannot establish
process absence. An inaccessible directory prevents complete lock/ownership
inventory and is refused. Existing state ownership and unsupported-entry checks
are retained; links and special or foreign-owned entries are refused.

A missing selected state root remains absent after successful or failed code-only
maintenance. No replacement state directory is created, including for an initial
explicit adoption. The operator is responsible for the absent root's actual
availability and for stopping processes whose identity is not recorded in the
accessible selected tree. Maintenance cannot discover those processes or inspect
locks under an absent/inaccessible store. Preparing or selecting repair code does
not establish that the retained data is compatible with that code. Incoming and
retained release payload, installed interpreter and managed launcher checks still
apply. Archive/export, migration and ordinary maintenance retain their existing
state and cleanup gates.

Results and `status.last_maintenance` always say **code updated, historical
cleanup unconfirmed** for code-only operations. They report `retained_state` as
`available` or `absent`, `history_assessment: not_performed`,
`data_compatibility: unknown`, and the actual process-inspection scope: existing
ownership records and cooperative locks only. `ownership_records_inspected`
counts inspected existing records. `unknown_ownership_records` is `null` because
missing identities cannot be counted without interpreting potentially broken
histories. `historical_cleanup_confirmed` remains false even when every inspected
recorded group has ended. This is a bounded maintenance observation, not a live
cleanup certification, compatibility judgment or claim of healed history.
Existing controller states and `process_info` semantics are not changed.

After the lead's independent acceptance and an operator-selected bounded backup
procedure, the operator may explicitly switch the public launcher to
`/private/noetic-adopted/bin/noetic`. This implementation does not perform that
switch. Do not use the strict archive command as a claimed backup if its cleanup
gate refuses the legacy history. Data backup/privacy migration remain separate
operations, not side effects or prerequisites manufactured by code adoption.

Start the new GUI with the same invocation shape as the prior installation:

```sh
/private/noetic-adopted/bin/noetic serve \
  --runs-dir /home/dgk/workspace/synthesis-worktrees/feature-cognitional-event-journal/.runtime/runs \
  --port 8765
```

New GUI startup is separate from adoption: it may create an operator token and
print a private pairing URL. Keep that output private; adoption itself starts no
server and generates no token. Existing broad state permissions are not repaired.

When the installed product cannot start, invoke the incoming ZIP's bootstrap
from an unrelated directory with an available Python interpreter. Its code-only
maintenance uses the persisted installation binding and does not require the
selected product to import successfully:

```sh
PYTHONPATH=/private/delivery/repair.zip python3 -B -S -m scripts.noetic_release install \
  /private/delivery/repair.zip --home /private/noetic-adopted --code-only
PYTHONPATH=/private/delivery/repair.zip python3 -B -S -m scripts.noetic_release rollback \
  RETAINED_RELEASE_ID --home /private/noetic-adopted --code-only
```

With writers stopped and the installed CLI available, subsequent code maintenance is:

```sh
/private/noetic-adopted/bin/noetic release install /private/delivery/next.zip --code-only
/private/noetic-adopted/bin/noetic release rollback RETAINED_RELEASE_ID --code-only
/private/noetic-adopted/bin/noetic release rollback legacy --code-only
```

`rollback legacy` makes the private wrapper execute the retained original
launcher in its original cwd; it does not reinstall, validate or repair the old uv
environment. Use the original explicit `serve --runs-dir ... --port 8765` arguments
when restarting it. Because 0.2.0 need not provide release maintenance, select a
managed release again using the standalone ZIP command with explicit `--home`.
The operator can also restore the public symlink to the preserved original uv
launcher. Neither route downgrades data or reverses writes made during later
application use. An interrupted/failed adoption may leave a partial new code home;
its external binding is saved before the state gate, so a retry cannot silently
fall back to an empty state directory. Inspect `status`; if the binding is intact,
retry ordinary `install --code-only` with that home (without adoption flags).
Otherwise use a new home, without moving or modifying old state.

## Export and Restore

```sh
python -m scripts.noetic_archive export /private/runs/RUN_ID /private/run.zip \
  --allow-held
python -m scripts.noetic_archive import /private/run.zip /private/new-restored-root
```

Export one actual quiescent run, not a runs collection. Authoritative
`events.sqlite3` and (where present) `controller.sqlite3` use SQLite's backup API;
raw WAL/SHM files and the stale `controller.json` projection are not copied.
The snapshot contains `SHA256.json` with per-file hashes, schema, identity and
privacy labels. No actor/model is invoked and no historical data is rewritten.

The retained-file allowlist is `task.md`, work/review Markdown and JSON,
`changes.json`, `changes.diff`, prompt/response/submission/model-result JSON or
text, `final-response.txt`, actor/verify process observations, and
work/verify/review/actor stdout/stderr logs and `*-prompt.txt`. These may occur at
the run root or under `activations/activation-N/`. Other files are excluded,
including driver bookkeeping, operator tokens, provider configuration, client
session stores and arbitrary workspace copies. Paths embedded in journals,
prompts, diffs and records remain historical strings and are never followed.
Retained content itself can contain private source or secrets previously written
by an actor; this is not a content redactor. Review content before sharing it.

The run-root `options.json` is also retained byte-for-byte: it is frozen run
execution input, not provider credential configuration. It preserves model/client
selection, verification commands, budgets and historical Telos paths for
inspection and an operator's explicit advance. Import never reads those paths,
loads provider credentials or resumes the run. Before explicitly advancing a
restored run, inspect its workspace, verification commands and Telos references:
the harness can use those historical locations, and explicit advance can invoke
actors or synchronize Telos. A completed, unlinked harness run can be explicitly
advanced with zero actor invocations. Operator token files, provider credential
stores and client session stores remain excluded; no source options are rewritten.

An optional full Telos database snapshot requires an explicit separate path:

```sh
python -m scripts.noetic_archive export /private/runs/RUN_ID /private/full.zip \
  --allow-held --telos-db /private/isolated-telos.sqlite3
```

This is labeled **FULL PRIVATE TELOS DATABASE**, not a run-scoped Telos export.
It includes all goals/history in that selected schema-2 database. Stop all its
writers first. Its SQLite backup is consistent, but the run and Telos databases
are not a single cross-database transaction. Restore places it separately at
`NEW_ROOT/private-telos/telos.sqlite3`, never merges it into a live store and
never automatically opens it with Telos.

Import requires a new destination root, creates `NEW_ROOT/runs/RUN_ID`, preserves
IDs/history, verifies checksums and schemas, rejects collisions, traversal,
links, duplicate entries and unsupported files, and creates directories/files
as 0700/0600. Existing destinations are refused even when empty. Export also
refuses symlinks, hard links, foreign-owned entries and special files in the run.
No outside workspace content or credential store is followed/copied. New work is
explicit: restored workspace references are not remapped and no ready reservation
is automatically advanced.

## Bounds and Interfaces

Bundles allow at most 4096 payload files and 256 MiB uncompressed payload, plus
up to 1 MiB for the manifest on read. Processing uses memory; large histories
need another owner-approved workflow rather than silently dropping data. Checksums
detect corruption, not authenticity. There is no network downloader, signer,
DRM, billing, license modification, global installer, cleanup daemon or model call.

Python APIs:

- `noetic_release.build_release(output, *, wheel, telos_module, telos_manifest, license_file, notices, docs)`
- `noetic_release.install_release(archive, home, *, allow_held=False, python=sys.executable, code_only=False, adopt_state=None, legacy_launcher=None, legacy_cwd=None)`
- `noetic_release.rollback(home, release, *, allow_held=False, code_only=False)`
- `noetic_release.status(home)`
- `noetic_archive.export_run(run, output, *, allow_held=False, telos_db=None)`
- `noetic_archive.import_run(archive, root)`
- Both modules expose `main(argv=None)` for later top-level CLI wiring.

Implementation tests (use a Python with pip/setuptools and venv support):
`/usr/bin/python3 -m unittest discover -s tests/programs -p test_release_archive.py`.
Tests build the actual wheel in `/tmp/opencode`, use
actual kernel journals and isolated private installations, and require Node 24
with the actual bundled Telos core. Coverage includes held/completed harness
options, zero-actor completed advance, missing required wheel assets with valid
RECORDs, changed/deleted installed modules and patterns, and rejected Node
capabilities (negative capability responses are mocked). No models, user live
state, donor changes or global installation are involved. These are implementation
checks, not independent QA or release acceptance.
