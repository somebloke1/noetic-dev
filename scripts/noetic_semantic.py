"""Disposable semantic retrieval over actual run artifacts; never semantic truth."""

from __future__ import annotations

import argparse
from contextlib import closing
import heapq
import json
from pathlib import Path
import sqlite3
import time

from scripts import noetic_local as local
from scripts.noetic_storage import create_private_sqlite


def chunks(text: str, byte_limit: int):
    """Contiguous UTF-8 chunks with exact byte offsets, without splitting codepoints."""
    if type(byte_limit) is not int or byte_limit < 4:
        raise local.LocalError("Chunk limit must be at least four bytes")
    raw = text.encode("utf-8")
    offset = 0
    while offset < len(raw):
        text_chunk = raw[offset:offset + byte_limit].decode("utf-8", errors="ignore")
        end = offset + len(text_chunk.encode("utf-8"))
        if text_chunk.strip():
            yield offset, end, text_chunk
        offset = end


def index_runs(connection: sqlite3.Connection, runs_dir: Path, client: local.LocalClient, *, reindex: bool = False, collection=None) -> dict:
    """Refresh atomically. Identity changes require explicit reindex; no mixed vectors."""
    identity = {**client.settings.embedding_identity(), "collector": "current-controller-or-legacy-v1",
                "runs_dir": str(Path(runs_dir).resolve()), "scope": "current"}
    if collection is not None:
        identity = {**client.settings.embedding_identity(), **collection["identity"]}
    encoded = local.canonical(identity)
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    expected = {"semantic_meta", "semantic_vectors", "semantic_chunks"}
    if tables and tables != expected:
        raise local.LocalError("Not a noetic semantic cache; choose a separate --db path")
    stored = connection.execute("SELECT identity FROM semantic_meta WHERE id=1").fetchone() if tables else None
    mismatch = stored is not None and stored[0] != encoded
    if mismatch and not reindex:
        raise local.LocalError("Embedding/source identity mismatch; run index --reindex explicitly")
    if tables and stored is None and not reindex:
        raise local.LocalError("Cache identity missing; run index --reindex explicitly")
    runs = local.collect_runs(runs_dir) if collection is None else [{"sources": collection["sources"]}]
    desired = []
    unique = {}
    for run in runs:
        for source in run["sources"]:
            metadata = {key: value for key, value in source.items() if key not in ("text", "goal")}
            metadata["source_text_sha256"] = local.digest(source["text"])
            for start, end, text in chunks(source["text"], client.settings.chunk_bytes):
                text_hash = local.digest(text)
                unique[text_hash] = text
                chunk_id = local.digest(local.canonical([source["source_path"], source["source_id"], start, end]))
                desired.append((chunk_id, text_hash, local.canonical({**metadata, "byte_start": start, "byte_end": end})))
    cached = {}
    if tables and not reindex:
        for text_hash, text, encoded_vector in connection.execute("SELECT text_hash, text, vector FROM semantic_vectors"):
            if text_hash in unique:
                if text != unique[text_hash]:
                    raise local.LocalError("Cache text identity mismatch; rebuild the derived cache")
                cached[text_hash] = local.vector(json.loads(encoded_vector), client.settings.dimensions, require_unit=True)
    missing = [key for key in unique if key not in cached]
    requests_before = client.requests
    # Batches are computed before committing any cache changes; failures leave the old cache intact.
    for offset in range(0, len(missing), client.settings.batch_size):
        batch = missing[offset:offset + client.settings.batch_size]
        vectors = client.embed([unique[key] for key in batch])
        cached.update(zip(batch, vectors))
    with connection:
        connection.execute("CREATE TABLE IF NOT EXISTS semantic_meta (id INTEGER PRIMARY KEY CHECK(id=1), identity TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS semantic_vectors (text_hash TEXT PRIMARY KEY, text TEXT NOT NULL, vector TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS semantic_chunks (chunk_id TEXT PRIMARY KEY, text_hash TEXT NOT NULL, metadata TEXT NOT NULL)")
        if reindex:
            connection.execute("DELETE FROM semantic_vectors")
        connection.execute("DELETE FROM semantic_chunks")
        connection.executemany("INSERT INTO semantic_chunks VALUES (?, ?, ?)", desired)
        connection.executemany("INSERT OR REPLACE INTO semantic_vectors VALUES (?, ?, ?)",
                               ((key, unique[key], local.canonical(cached[key])) for key in missing))
        connection.execute("DELETE FROM semantic_vectors WHERE text_hash NOT IN (SELECT text_hash FROM semantic_chunks)")
        connection.execute("INSERT OR REPLACE INTO semantic_meta VALUES (1, ?)", (encoded,))
    return {"runs": len(runs) if collection is None else len({source.get("run_id") for source in collection["sources"] if source.get("run_id")}), "chunks": len(desired), "unique_texts": len(unique), "embedded_texts": len(missing),
            "embedding_requests": client.requests - requests_before, "reindexed": reindex,
            "identity": identity, "authoritative": False, "scope": "current" if collection is None else collection["selection"],
            **({key: collection[key] for key in ("diagnostics", "coverage", "status")} if collection is not None else {})}


def index_scoped(connection, collection, client, *, reindex=False):
    return index_runs(connection, Path(collection["identity"]["runs_dir"]), client,
                      reindex=reindex, collection=collection)


def search(connection: sqlite3.Connection, query: str, client: local.LocalClient, limit: int = 20, *, identity=None) -> list[dict]:
    """Search a refreshed cache. Cosine similarity is relevance, not evidence quality."""
    row = connection.execute("SELECT identity FROM semantic_meta WHERE id=1").fetchone()
    if row is None:
        raise local.LocalError("Cache has no identity; index first")
    stored_identity = json.loads(row[0])
    if identity is not None and stored_identity != {**client.settings.embedding_identity(), **identity}:
        raise local.LocalError("Recall scope/source identity mismatch; refresh the requested scope")
    if stored_identity.get("collector") != "current-controller-or-legacy-v1" and identity is None:
        raise local.LocalError("Scoped semantic search requires the declared collection identity")
    if any(stored_identity.get(key) != value for key, value in client.settings.embedding_identity().items()):
        raise local.LocalError("Embedding identity mismatch; index --reindex before searching")
    if not query.strip():
        raise local.LocalError("Semantic query must be nonempty")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise local.LocalError("Search limit must be between 1 and 100")
    if not connection.execute("SELECT 1 FROM semantic_chunks LIMIT 1").fetchone():
        return []
    query_vector = client.embed([query], query=True)[0]

    def scored():
        for chunk_id, metadata, text, encoded_vector in connection.execute(
            "SELECT c.chunk_id, c.metadata, v.text, v.vector FROM semantic_chunks c "
            "JOIN semantic_vectors v ON c.text_hash=v.text_hash"
        ):
            doc_vector = local.vector(json.loads(encoded_vector), client.settings.dimensions, require_unit=True)
            score = max(-1.0, min(1.0, sum(a * b for a, b in zip(query_vector, doc_vector))))
            yield {**json.loads(metadata), "chunk_id": chunk_id, "score": score,
                   "snippet": text, "authoritative": False}

    return heapq.nsmallest(limit, scored(), key=lambda row: (-row["score"], row["source_id"], row["chunk_id"]))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("index", "search"):
        command = commands.add_parser(name)
        command.add_argument("--runs-dir", type=Path, required=True)
        command.add_argument("--db", type=Path)
        command.add_argument("--json", action="store_true", help="JSON is also the default output")
        local.add_settings_arguments(command)
        if name == "index":
            command.add_argument("--reindex", action="store_true", help="Explicitly replace vectors for a new identity")
        else:
            command.add_argument("query")
            command.add_argument("--limit", type=int, default=20)
    from scripts import noetic_recall as recall
    for command in commands.choices.values():
        recall.add_scope_arguments(command)
    args = parser.parse_args(argv)
    try:
        started = time.monotonic()
        client = local.LocalClient(local.settings_from_args(args))
        collection = None
        if args.scope:
            if args.namespace_path is None or args.sessions_home is None:
                raise local.LocalError("Scoped recall requires explicit --namespace-path and --sessions-home")
            collection = recall.collect(namespace_path=args.namespace_path, sessions_home=args.sessions_home,
                runs_dir=args.runs_dir, selection=recall.selection_from_args(args))
        elif any(getattr(args, key) is not None for key in ("namespace_path", "sessions_home", "effort_root", "ordinal", "instantiation", "session")):
            raise local.LocalError("Ownership selectors require an explicit --scope")
        db = args.db or (":memory:" if collection is not None else
                        args.runs_dir / ".semantic.sqlite3" if args.runs_dir.is_dir() else ":memory:")
        if db != ":memory:":
            db = create_private_sqlite(db)
        with closing(sqlite3.connect(db, timeout=5)) as connection:
            result = index_runs(connection, args.runs_dir, client, reindex=getattr(args, "reindex", False), collection=collection)
            if args.command == "search":
                result = {"index": result, "results": search(connection, args.query, client, args.limit, identity=collection["identity"] if collection is not None else None)}
            result.update(authoritative=False, notice="Derived semantic relevance only; not semantic truth or QA.",
                          elapsed_seconds=round(time.monotonic() - started, 3))
            print(local.canonical(result))
        return 0
    except (local.LocalError, OSError, sqlite3.Error, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(local.canonical({"status": "unavailable", "error": str(exc) if isinstance(exc, (local.LocalError, recall.ScopeError)) else "Cannot read sources or refresh the semantic cache",
                               "authoritative": False, "lexical_fallback": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
