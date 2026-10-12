# Explicit effort ownership of native Telos purposes

`scripts/noetic_purposes.py` routes an explicitly requested purpose to a native
Telos database owned by an already registered Noetic effort or by logical
application responsibility `0`. It preserves the native chain/subgoal UUIDs,
aggregate, transitions and source evidence. Ordinary work requires no goalchain.
This adapter implements ownership and resolution; it does not launch work or
decide native lifecycle transitions.

The [effort scope contract](effort-scope.md) supplies the persistent namespace,
effort roots and application mandate. Folder, process, session and model identity
do not select a purpose owner. A and B sharing a cwd have different databases;
an explicitly registered trial R has its own database. External Noetic
development and recovery coordination remains independent of these product
records.

## Store selection and identity

Construction requires an explicit `namespace_path`. Neither construction nor
reads initialize that namespace. The optional `purposes_root` defaults to
`namespace_path.parent / "purposes"`; it does not consult `NOETIC_APP_HOME`.
The application consumer selects the installation-owned namespace path before
constructing the adapter. `source` selects the maintained Telos source tree or
its bundled `.mjs` factory, using the existing Telos configuration precedence.
No provider, GPU or service is required.

| Owner | Native store relative to `purposes_root` |
|---|---|
| Effort `0.N` | `<namespace UUID>/efforts/0.N/telos.sqlite3` |
| Application `0` | `<namespace UUID>/application/telos.sqlite3` |
| Legacy history | Explicit `legacy_db`, retained as `legacy-unassigned` |

No native schema or semantic state is copied into a second authoritative store.
Owned databases are initialized only on explicit purpose creation, by the real
Telos factory. Its native `global` scope means global **within that database**.
Noetic ownership is the namespace, owner and store reference around that native
aggregate. The service's older database remains unassigned history; neither
recovery chains nor ordinary consumer chains are automatically reassigned.
The existing `noetic goal` routes remain deliberately legacy operations.

The complete purpose reference has this JSON shape:

```json
{
  "owner": {"namespace": "<persistent namespace UUID>", "kind": "effort", "ordinal": "0.0"},
  "store_id": "<namespace UUID>/efforts/0.0/telos.sqlite3",
  "db_path": "/explicit/application/state/purposes/<namespace UUID>/efforts/0.0/telos.sqlite3",
  "chain_id": "<native chain UUID>",
  "source": "/explicit/configured/telos-core.mjs"
}
```

Application ownership uses `kind: "application"`, ordinal `0`. Legacy references
use `kind: "legacy-unassigned"`, null namespace/ordinal, and their original
database path. Scoped resolution rejects those references. Native scope/status
strings and provenance inside the aggregate remain unchanged.

The reference includes a stable relative store identity and explicit current
locators. Resolution validates all ownership/store fields and the configured
component source. A bare chain ID is insufficient; a caller-supplied helper path
cannot override configured native authority. Relocation requires a reference
obtained from the adapter at the deliberately selected new location, preserving
the original native provenance. Copying a namespace and its stores preserves
their identities; selecting an unrelated namespace cannot borrow its chains.

## Python consumer contract

```python
from scripts.noetic_purposes import Purposes
from scripts.noetic_scope import Scope
from scripts import noetic_telos

purposes = Purposes(
    namespace_path="/explicit/application/state/ordinals.sqlite3",
    source="/explicit/configured/telos-core.mjs",
    legacy_db="/explicit/retained/service-telos.sqlite3",
)
scope = Scope.effort("0.0")  # must already be a registered effort root
created = purposes.create(
    "Investigate the declared effort",
    scope=scope,
    origin_ref={"human": "actual-origin-reference"},
    source_ref={"request": "actual-request-reference"},
)
report = purposes.list(scope=scope)
selected = purposes.resolve(created["reference"], scope=scope)
binding = purposes.resolve_run(created["reference"], scope=scope)
link = noetic_telos.begin_run(
    binding["chain_id"], actual_run_dir, binding["db_path"], binding["source"]
)
```

| Method | Result / scope |
|---|---|
| `create(goal, *, scope, owner=None, origin_ref, source_ref)` | One purpose item. Effort scope defaults to that effort. Application scope defaults to owner `0`; an explicit effort owner must be named in its targets. |
| `list(*, scope, include_legacy=False)` | A report over the selected effort, or root-owned purposes plus the application scope's explicitly named efforts. Legacy inclusion requires application scope and configured `legacy_db`. |
| `list_unassigned()` | Explicitly selected legacy history only. It works before namespace registration and creates no namespace/store. |
| `resolve(reference, *, scope)` | One exact owned purpose item, after validating owner, namespace, store, source and native chain presence. |
| `resolve_run(reference, *, scope)` | `{chain_id, db_path, source, purpose_ref}` for existing native run integration. |

Each purpose item is `{reference, native, ownership_event}`. `native` is the
unchanged Telos aggregate. `ownership_event` preserves the canonical namespace
creation event, responsible origin and source reference; it is null for legacy
history or a chain introduced directly through native tooling without that
Noetic event. Null evidence is not an invented actor or runtime occurrence.
The exact native database and its aggregate provenance remain investigable.

Creation first commits the native chain, then appends its ownership/source event
through `ScopeStore.record_event`. These are separate durable boundaries. If
the second boundary fails, `PurposeError.code == "ownership_record_failed"`
includes the already-created chain's complete `reference`. The caller must
reconcile that retained chain; automatically retrying creation would create
another chain. No command idempotency or atomic cross-database commit is claimed.

Application operations use an explicit
`Scope.application(target_efforts, root_mandate_version=N)` and validate the
current recorded root mandate. Logical root ownership needs no live root model.
Effort scope rejects foreign stores, even when their folders match or callers
alter a reference's owner field. The run consumer must resolve its execution's
owning scope first and pass that same scope to `resolve_run`, retain `purpose_ref`
with its binding, and use the returned exact database/chain for native begin and
record. Listing a foreign purpose does not grant implicit cross-effort routing.

## Availability, reads and lifecycle evidence

A report is `{purposes, stores, coverage}`. Each store includes its owner,
store ID, database path and `status`: `available`, `absent` or `error`. `error`
adds `{code, message}`. `coverage` is `partial` when any selected store cannot
be read; other available stores retain their results. `complete` means that
the **selected** sources were read or explicitly absent, not that all application
efforts or all native tables were collected.

An absent fresh store returns explicit absence and no purposes. An existing
empty, malformed or incomplete database is an error; it is not silently
initialized on read. SQLite integrity/references, the native store's identity and
every required table from the maintained native `SCHEMA_V2_SQL` are checked
before invoking its migrating factory on a read snapshot or writable creation.
Missing session/delegation/project tables are corruption even when a particular
chain aggregate could be read without them. An unavailable configured
component is `native_unavailable`; a failed native child is `native_error`.
Absent/corrupt namespaces and scope mismatches raise `PurposeError` directly.
No reported error is converted to an apparently empty successful result.

Native listing uses the existing SQLite snapshot read adapter. The selected
native file is not migrated, rewritten or assigned a new owner. Native aggregates
and original source references are retained; they are not summarized into a
universal lifecycle status. `resolve_run` performs no native transition. Existing
`noetic_telos.begin_run` and `record_result` keep subgoal identity, native receipt
evidence, committed-memory-deposit gating and independent run/chain completion.
The adapter adds no pause/resume/completion implementation; those transitions
remain governed by the native component.

## Module CLI

Global options precede the command: `--namespace-path PATH` is required
(`--namespace` is an alias), with optional `--purposes-root PATH`,
`--legacy-db PATH`, `--source PATH`.

```bash
python -m scripts.noetic_purposes --namespace-path /explicit/state/ordinals.sqlite3 \
  --source /explicit/telos-core.mjs list --effort 0.0

python -m scripts.noetic_purposes --namespace-path /explicit/state/ordinals.sqlite3 \
  --source /explicit/telos-core.mjs create 'Declared purpose' --effort 0.0 \
  --origin-ref '{"human":"actual-person"}' --source-ref '{"request":"actual-request"}'

python -m scripts.noetic_purposes --namespace-path /explicit/state/ordinals.sqlite3 \
  --source /explicit/telos-core.mjs list --application --root-mandate-version 1 \
  --target-effort 0.0 --target-effort 0.1

python -m scripts.noetic_purposes --namespace-path /explicit/unregistered/ordinals.sqlite3 \
  --legacy-db /explicit/retained/telos.sqlite3 --source /explicit/telos-core.mjs list-unassigned
```

`resolve REF_JSON` and `resolve-run REF_JSON` use the complete reference and the
same explicit scope flags. Application creation can add `--owner 0.N` when that
effort is named with `--target-effort`; default application owner is `0`.
Output is JSON. Exit codes are 0 for complete success, 1 for a partial listing,
and 2 for a rejected operation; the latter emits a structured error on stderr.

## Bounded verification

`tests/programs/test_noetic_purposes.py` builds and runs the actual maintained
Telos component in disposable stores. It also invokes its source factory.
Checks cover A/B sharing a cwd, separately registered R, deliberate root ownership,
fresh-process resolution/listing, native UUID preservation, foreign-chain/store/
source rejection, absent versus corrupt/incomplete/unavailable results, preserved
legacy bytes and source evidence, no read-side registration, explicit namespace
override despite inherited `NOETIC_APP_HOME`, refusal and byte preservation after
deleting each managed table from stores created by both actual factories, and exclusion of the development
credential from native children. A disposable reviewed run exercises the existing
receipt gate with controlled memory receipt envelopes; it does not claim an actual
Opermem submission. Subgoal completion leaves the primary native chain active.

This component proof does not establish Application/UI delivery, scheduled
continuation, arbitrary native mutation coverage or human judgment of usefulness.
The coordinator owns the separate independent QA pass and consumer integration.
