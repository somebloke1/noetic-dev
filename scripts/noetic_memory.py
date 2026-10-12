#!/usr/bin/env python3
"""Search a disposable lexical index of actual noetic-dev run artifacts."""

from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

if __package__:
    from scripts import noetic_controller as controller
    from scripts import noetic_run as runtime
else:
    import noetic_controller as controller
    import noetic_run as runtime


def _controller_rows(run_dir: Path) -> list[tuple]:
    """Recall current bindings, not the controller's historical Markdown export."""
    path = run_dir / "controller.sqlite3"
    state = controller.inspect_run(path)
    if state.get("schema_version") != 1:
        raise ValueError("Unsupported controller schema")
    artifacts = state["artifacts"]
    selected = list(state["slots"].items())
    accepted = {ref for slot, ref in selected if slot.startswith("accepted.")}
    selected += [("qa.for." + artifact["content"]["subject_artifact_id"], ref)
                 for ref, artifact in artifacts.items()
                 if artifact["type"] == "qa.review"
                 and artifact["content"].get("subject_artifact_id") in accepted]
    rows = []
    for binding, ref in selected:
        artifact = artifacts[ref]
        if artifact["partial"]:
            continue
        text = json.dumps(artifact["content"], ensure_ascii=False, sort_keys=True, allow_nan=False)
        rows.append((run_dir.name, state["purpose"], state["status"], artifact["type"],
                     f"{binding}:{ref}", str(path), None, text))
    return rows


def index_runs(connection: sqlite3.Connection, runs_dir: Path) -> int:
    """Replace this index with current controller/legacy records; return the entry count."""
    rows = []
    runs_dir = Path(runs_dir)
    try:
        children = sorted(runs_dir.iterdir())
    except FileNotFoundError:
        children = []
    for run_dir in children:
        if not run_dir.is_dir() or not (run_dir / "controller.sqlite3").exists():
            continue
        run_dir = run_dir.resolve()
        try:
            rows.extend(_controller_rows(run_dir))
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, AttributeError) as exc:
            print(f"Skipping controller run {run_dir}: {exc}", file=sys.stderr)
    for run in runtime.list_runs(runs_dir):
        run_dir = Path(run["directory"])
        # A present controller store wins even if unreadable; exports are not a fallback.
        if (run_dir / "controller.sqlite3").exists():
            continue
        try:
            events = runtime.read_events(run_dir)
            status = runtime.project(events)
            entries = [("goal", "run.created.plan.goal", run_dir / "events.sqlite3",
                        events[0]["sequence"], status["goal"])]
            reports = {}
            for field in ("work", "review"):
                path = run_dir / f"{field}.md"
                try:
                    reports[field] = path.read_text(encoding="utf-8")
                except FileNotFoundError:
                    continue
                except (OSError, UnicodeError) as exc:
                    print(f"Skipping artifact {path}: {exc}", file=sys.stderr)
                    continue
                entries.append((field, path.name, path, None, reports[field]))
            if status["review"]:
                evidence = status["review"]["evidence"]
                if evidence.strip() != reports.get("review", "").strip():
                    event = next(e for e in reversed(events) if e["kind"] == "review.recorded")
                    entries.append(("review", "review.recorded.evidence", run_dir / "events.sqlite3",
                                    event["sequence"], evidence))
            rows.extend((status["run_id"], status["goal"], status["state"], field,
                         source, str(path), sequence, text)
                        for field, source, path, sequence, text in entries if text.strip())
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, AttributeError) as exc:
            print(f"Skipping run {run_dir}: {exc}", file=sys.stderr)
    with connection:
        connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS memory USING fts5("
            "run_id UNINDEXED, goal UNINDEXED, state UNINDEXED, field UNINDEXED, "
            "source UNINDEXED, source_path UNINDEXED, event_sequence UNINDEXED, text)"
        )
        connection.execute("DELETE FROM memory")
        connection.executemany("INSERT INTO memory VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    return len(rows)


def search(connection: sqlite3.Connection, query: str, limit: int = 20) -> list[dict]:
    """Search an already refreshed index; whitespace-separated literals use AND."""
    terms = query.split()
    if not terms:
        return []
    match = " AND ".join('"' + term.replace('"', '""') + '"' for term in terms)
    cursor = connection.execute(
        "SELECT run_id, goal, state, field, source, source_path, event_sequence, "
        "snippet(memory, 7, '[', ']', ' ... ', 32) AS snippet "
        "FROM memory WHERE memory MATCH ? ORDER BY rank, run_id, source_path, source LIMIT ?",
        (match, max(1, min(100, limit))),
    )
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor]


def index_scoped(connection, collection, *, reindex=False):
    """Refresh only already ownership-resolved sources; identity changes are explicit."""
    encoded = json.dumps(collection["identity"], sort_keys=True, separators=(",", ":"))
    exists = connection.execute("SELECT 1 FROM sqlite_master WHERE name='recall_meta'").fetchone()
    row = connection.execute("SELECT identity FROM recall_meta WHERE id=1").fetchone() if exists else None
    if exists and (row is None or row[0] != encoded) and not reindex:
        raise ValueError("Recall scope/source identity mismatch; explicitly reindex or use a separate cache")
    rows = [(json.dumps({key: value for key, value in source.items() if key != "text"}, sort_keys=True), source["text"])
            for source in collection["sources"]]
    summary = {key: value for key, value in collection.items() if key != "sources"}
    with connection:
        connection.execute("CREATE TABLE IF NOT EXISTS recall_meta (id INTEGER PRIMARY KEY CHECK(id=1), identity TEXT NOT NULL, summary TEXT NOT NULL)")
        connection.execute("CREATE VIRTUAL TABLE IF NOT EXISTS recall_memory USING fts5(metadata UNINDEXED, text)")
        connection.execute("DELETE FROM recall_memory")
        connection.executemany("INSERT INTO recall_memory VALUES (?,?)", rows)
        connection.execute("INSERT OR REPLACE INTO recall_meta VALUES (1,?,?)", (encoded, json.dumps(summary, sort_keys=True)))
    return {**summary, "entries": len(rows), "reindexed": reindex}


def search_scoped(connection, query, *, identity, limit=20):
    """Require the caller's exact declared identity before querying a derived cache."""
    row = connection.execute("SELECT identity,summary FROM recall_meta WHERE id=1").fetchone()
    if row is None or json.loads(row[0]) != identity:
        raise ValueError("Recall scope/source identity mismatch; refresh the requested scope")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Search limit must be between 1 and 100")
    terms = query.split()
    results = []
    if terms:
        match = " AND ".join('"' + term.replace('"', '""') + '"' for term in terms)
        for metadata, snippet in connection.execute(
            "SELECT metadata,snippet(recall_memory,1,'[',']',' ... ',32) FROM recall_memory "
            "WHERE recall_memory MATCH ? ORDER BY rank,rowid LIMIT ?", (match, limit)):
            results.append({**json.loads(metadata), "snippet": snippet, "authoritative": False})
    return {**json.loads(row[1]), "results": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("index", "search"):
        command = commands.add_parser(name)
        command.add_argument("--runs-dir", type=Path, required=True)
        command.add_argument("--db", type=Path)
        if name == "search":
            command.add_argument("query")
            command.add_argument("--limit", type=int, default=20)
            command.add_argument("--json", action="store_true")
    if __package__:
        from scripts import noetic_recall as recall
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from scripts import noetic_recall as recall
    for command in commands.choices.values():
        recall.add_scope_arguments(command)
        command.add_argument("--reindex", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.scope:
            if args.namespace_path is None or args.sessions_home is None:
                raise ValueError("Scoped recall requires explicit --namespace-path and --sessions-home")
            collection = recall.collect(namespace_path=args.namespace_path, sessions_home=args.sessions_home,
                runs_dir=args.runs_dir, selection=recall.selection_from_args(args))
            with closing(sqlite3.connect(args.db or ":memory:")) as connection:
                result = index_scoped(connection, collection, reindex=args.reindex)
                if args.command == "search":
                    result = search_scoped(connection, args.query, identity=collection["identity"], limit=args.limit)
                print(json.dumps(result, sort_keys=True))
            return 0
        if any(getattr(args, key) is not None for key in ("namespace_path", "sessions_home", "effort_root", "ordinal", "instantiation", "session")):
            raise ValueError("Ownership selectors require an explicit --scope")
        # Do not create a missing runs directory just to store derived memory.
        db = args.db or (args.runs_dir / ".memory.sqlite3" if args.runs_dir.is_dir() else ":memory:")
        with closing(sqlite3.connect(db)) as connection:
            count = index_runs(connection, args.runs_dir)
            if args.command == "index":
                print(f"Indexed {count} entries")
            else:
                results = search(connection, args.query, args.limit)
                if args.json:
                    print(json.dumps(results, indent=2, sort_keys=True))
                else:
                    for result in results:
                        event = result["event_sequence"]
                        location = result["source_path"] + (f" (event {event})" if event is not None else "")
                        print(f"Run: {result['run_id']}\nGoal: {result['goal']}\n"
                              f"State: {result['state']}\nField: {result['field']} / {result['source']}\n"
                              f"Source: {location}\n{result['snippet']}\n")
        return 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"noetic memory failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
