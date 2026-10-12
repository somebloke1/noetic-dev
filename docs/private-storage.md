# Private Noetic State

Noetic's current harness/application creates new managed directories as `0700`
and files as `0600`, even with caller umask `022` or `002`. It never changes the
process umask, workspace source permissions, or existing ancestor modes.
This protects against ordinary other OS accounts through POSIX permissions;
it does not isolate root or processes running as the same user. It is not
encryption and does not recall existing copies or backups.

## APIs

- `ensure_private_directory(path) -> Path`: create missing components as `0700`.
  Existing directories remain unchanged; a broad selected directory emits an
  actionable migration warning. Existing unrelated ancestors are not chmodded.
- `open_private(path, mode='w', encoding='utf-8') -> file`: use with `with` or
  close explicitly. Owned managed regular files become `0600` before truncation
  or writing; binary modes ignore encoding. Links and foreign ownership decline.
- `create_private_sqlite(path) -> Path`: precreate `0600` before SQLite/native
  Telos opens it. Existing bytes and modes remain untouched, with a warning for
  broad modes. SQLite creates new journal/WAL/SHM sidecars using the DB mode.
- `inspect_tree(root) -> dict`: read-only counts, bytes, relative-path SHA-256
  inventory, modes needing protection, and skipped entries.
- `protect_tree(root) -> dict`: explicit offline migration with before/after
  reports, changed count and content-preservation check. Directories become
  `0700`; regular files become `0600`, preserving only existing owner execute
  (`0700`) for executable state helpers during this explicit migration.

## Explicit Migration

Stop writers first. Select a directory containing **only Noetic-owned state**,
not a workspace, home, source checkout, or external user-managed Telos store.
The commands reject home/ancestor roots and source/workspace markers, but cannot
infer ownership intent from arbitrary directory names. Selecting the root is
the operator's scope declaration. Never run recursive protection over home.

```sh
python3 -B -m scripts.noetic_storage inspect /selected/noetic-state
python3 -B -m scripts.noetic_storage protect /selected/noetic-state
python3 -B -m scripts.noetic_storage inspect /selected/noetic-state
```

`inspect` is the dry run. Exit status is `0` for a fully private inventory, `1`
for entries needing protection or skipped entries, and `2` for an error.
`protect` reports the same status from its final inventory. Symlinks, foreign
owners, special files and hard-linked files are skipped without following them.
A symlink/foreign-owned root is rejected. No path traversal follows symlinks.
Migration changes metadata only; hashes and byte counts must match afterward.
It is not an atomic transaction; an I/O error can leave a partially protected
tree, so inspect again before retrying. Do not migrate while writers are active.

For default storage, include both `runs` and sibling `telos.sqlite3` by selecting
their **state-only parent**, commonly `.runtime`. Existing broad SQLite sidecars
also require this explicit offline migration. No actual production `.runtime`
was migrated as part of this implementation.

## Coverage And Limits

Covered write points: current harness task/options/exports/prompts/results,
activation diffs, captured model/command stdout/stderr, controller and outer
SQLite journals, summaries, semantic DB creation, application driver metadata,
locks/logs, and Python-mediated native Telos DB creation. Telos build/source
artifacts retain their original permission policy. External databases are not
automatically chmodded. Existing broadly accessible directories emit warnings,
not a claim that migration has happened.

The standalone legacy `noetic_develop.py`/`noetic_changes.py` writers, lexical
`noetic_memory.py` cache, batch writer and M0 `cognitional_event_journal.py` JSONL
writer are outside this unit's permitted edit list. Their direct use is not
covered by the full file-mode guarantee. The current harness precreates its
diff files privately before calling the shared diff writer. Provider-owned Pi
and OpenCode session stores are outside Noetic's managed store. The JS Telos
adapter is internal; private creation is established by its Python caller.

Permissions are mode-level evidence, not an ACL audit or a second-account login
test. Migration hashes are content-preservation evidence, not encrypted storage.
The application-session token and HTTP authentication belong to a separate unit.
Top-level CLI wiring is left to the lead; this module provides its own entry point.
