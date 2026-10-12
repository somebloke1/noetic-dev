# Searchable session memory

After restarting a client, search the actual retained noetic-dev runs:

```bash
python3 scripts/noetic_memory.py search "run discovery" --runs-dir .runtime/runs
python3 scripts/noetic_memory.py search "run discovery" --runs-dir .runtime/runs --json --limit 10
python3 scripts/noetic_memory.py index --runs-dir .runtime/runs
```

This standard-library Python CLI requires SQLite with FTS5 enabled. It does not
call models, generate summaries, use semantic embeddings, or require a service.
Search is lexical: each whitespace-separated term is quoted literally for FTS5
and combined with AND within one artifact. FTS5 handles case and tokenization;
punctuation is generally a token separator, not exact substring matching.
Operators such as `OR`, wildcards, and column filters are not query syntax.
Empty input returns no results. Limits default to 20 and are clamped to 1-100.

## Sources and results

### Controller runs

Directories containing `controller.sqlite3` are discovered directly, even without
`events.sqlite3` or derived reports. `noetic_controller.inspect_run` reads the
current persisted state read-only. Indexed text consists of JSON content from:

- Current `external.*`, `accepted.*`, and `effective.*` slot-bound artifacts.
- Typed `qa.review` artifacts linked to the exact currently accepted subjects.

The goal is the controller's purpose; state is its recorded status. Controller
results use the artifact type as `field` (for example, `cognition.P2`) and
`binding:artifact-id` as `source` (for example, `effective.P2:artifact-3`). Linked
QA uses `qa.for.<subject-id>:<review-id>`. `source_path` identifies the absolute
`controller.sqlite3` path; `event_sequence` is null, not a legacy journal event.
Artifact IDs are local to that database, and `run_id` is the run directory name.

Controller `work.md`, `review.md`, `controller.json`, and legacy event projections
are not indexed. They may be missing, stale, or contain historical artifacts.
Other superseded, invalidated, partial, and unbound artifacts (including pending
unaccepted development drafts) are excluded. A present controller store takes
precedence over legacy sources; an unreadable or unsupported store is diagnosed
and skipped, never replaced by stale exports. A current `cognition.P2` binding
still contains hypotheses, not affirmed judgments; an accepted development
binding records controller acceptance, not independent proof of correctness.

### Legacy runs

Runs without a controller store retain the existing `noetic_run.list_runs`
discovery; goals and current recorded states come from `noetic_run.read_events`
and `noetic_run.project`. Indexed text consists of:

- The recorded run goal, attributed to the creation event in `events.sqlite3`.
- `work.md` worker findings, when present in the run directory.
- `review.md` reviewer reports, when present in the run directory.
- The projected review's retained event evidence if the report is missing,
  unreadable, or differs from that evidence (ignoring surrounding whitespace).

Identical report and retained evidence text is indexed once, attributed to the
report file. Differing texts are separate sources, not competing state claims.
Deleting a report does not erase evidence still retained in the journal.
No findings are inferred from command exit codes or missing reports. Generic
runtime runs without Markdown reports still expose their goals and any recorded
review evidence. Command logs and assistant transcripts are not indexed.

Each result includes `run_id`, `goal`, `state`, `field`, `source`, absolute
`source_path`, `event_sequence` (null for files), and a matching `snippet`.
Matches are marked with square brackets and ordered by FTS5 relevance. Legacy
event sequence numbers identify the exact journal record; inspect it using:

```bash
python3 scripts/noetic_run.py events .runtime/runs/<run-id>
python3 scripts/noetic_run.py status .runtime/runs/<run-id> --json
```

For both storage kinds, state means last recorded state, not live process health
or independent proof of correctness. Controller `completed` means the kernel
pattern completed, not generic acceptance or Telos completion. For legacy runs,
a report can exist before a review verdict is recorded.

## Disposable Index

Every search fully refreshes the derived index before querying. Explicit `index`
performs the same refresh without searching. Rebuilding replaces all entries in
one transaction: repeated refreshes do not accumulate duplicates, and changed
states, edited reports, and deleted or corrupt runs do not leave old index hits.
Corrupt journals and unreadable reports are diagnosed on stderr while valid
sources remain searchable. A missing runs directory returns no results and is
not created.

The default database is `RUNS_DIR/.memory.sqlite3`; for a missing directory the
default is an empty in-memory database. Supply `--db PATH` to either command for
a dedicated index elsewhere; its parent directory must already exist. Use a
separate disposable database, never a run journal or another application's DB.
An explicit database is replaced with the selected runs directory's derived
entries on each refresh, not merged across roots. Deleting the index is safe:
controller databases and legacy journals/report files remain the sources. The
index contains copies of their text and should be treated with the same care as
those files; derived controller reports are not current authority.

Reusable functions are `index_runs(connection, runs_dir) -> int` and
`search(connection, query, limit=20) -> list[dict]`. Call the former before the
latter to refresh; the CLI does this automatically. Both use caller-owned SQLite
connections. SQL values and the quoted MATCH expression are parameterized.

Full refresh favors simple stale-entry removal over incremental performance.
Concurrent journal/report writes are not a cross-file snapshot; another search
refreshes again. This is local lexical recall, not complete historical revision
search or a replacement for reviewing original evidence.

## Implementation Checks

```bash
python3 -B -m unittest tests.programs.test_noetic_memory -v
```

Tests execute real `noetic_run` work and verification commands and real
controller transitions in temporary directories. Fresh CLI processes retrieve
P2 content from a copied controller store after reports and its legacy journal
are removed; other checks cover stale exports, return invalidation, development
acceptance/QA linkage, and corrupt-store precedence. Commands, role results,
worker reports, and reviewer evidence are explicitly test-authored, not model
output or independent review. No model calls or external services are used.
