"""Freeze retained Noetic command evidence without executing or authorizing work."""

from __future__ import annotations

from contextlib import closing
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
import tempfile

if __package__:
    from scripts import noetic_run as runtime
    from scripts.noetic_storage import ensure_private_directory, open_private
else:
    import noetic_run as runtime
    from noetic_storage import ensure_private_directory, open_private


VERSION = "noetic-act-observation/v1"
FILE_LIMIT = 16 * 1024 * 1024
TOTAL_LIMIT = 64 * 1024 * 1024
STEPS = ("work", "verify", "review")
OPTIONAL = ("task.md", "work-prompt.txt", "work.md", "work.json", "review-prompt.txt",
            "review.md", "review.json", "changes.json", "changes.diff", "telos-context.json")
LIMITATIONS = [
    "Retained command evidence is not source authenticity, exhaustive history, or tool authorship proof.",
    "Process completion and run/review acceptance do not establish desired success or native standing.",
    "Changes are observations, not proof of which actor caused them; existing diff omissions remain intact.",
    "No execution permission, native plan/step binding, or inferred agent ordinal/effort is supplied.",
    "Only noetic_run v1 and noetic_develop maintained programs are mapped; other event kinds remain raw.",
    "No environment, ownership sidecars, workspace contents, or unrelated files are collected.",
    "Missing optional evidence remains unavailable; captured logs have no recorder-origin content hashes.",
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate evidence JSON field")
        result[key] = value
    return result


def _read(path: Path) -> tuple[bytes, tuple]:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > FILE_LIMIT:
            raise ValueError(f"required evidence is not a bounded regular file: {path.name}")
        chunks, size = [], 0
        while chunk := os.read(fd, 65536):
            size += len(chunk)
            if size > FILE_LIMIT:
                raise ValueError(f"evidence exceeds {FILE_LIMIT} bytes: {path.name}")
            chunks.append(chunk)
        after = os.fstat(fd)
        signature = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if signature(before) != signature(after) or size != before.st_size:
            raise ValueError("source evidence changed during capture")
        return b"".join(chunks), signature(after)
    finally:
        os.close(fd)


def _describe(events: list[dict], step: str) -> tuple[dict, dict, set[str]]:
    if step not in STEPS:
        raise ValueError("supported selected steps are work, verify, review")
    if not events or events[0].get("kind") != "run.created" or events[0]["data"].get("version") != 1:
        raise ValueError("unsupported source: noetic_run creation version 1 required")
    sequences = [event["sequence"] for event in events]
    if any(type(seq) is not int or seq <= 0 for seq in sequences) or sequences != sorted(set(sequences)):
        raise ValueError("invalid recorded event sequence")
    status = runtime.project(events)
    required = set()
    selected = None
    for name in STEPS:
        starts = [e for e in events if e["kind"] == "step.started" and e["data"].get("step") == name]
        finishes = [e for e in events if e["kind"] == "step.finished" and e["data"].get("step") == name]
        if len(starts) > 1 or len(finishes) > 1:
            raise ValueError("repeated step evidence is ambiguous: log filenames may have been reused")
        for event in starts + finishes:
            data = event["data"]
            if (data.get("stdout") != f"{name}.stdout.log" or data.get("stderr") != f"{name}.stderr.log"
                    or not isinstance(data.get("argv"), list) or not data["argv"]
                    or any(not isinstance(arg, str) or "\0" in arg for arg in data["argv"])):
                raise ValueError("unsupported command evidence schema")
            required.update((data["stdout"], data["stderr"]))
        if starts and finishes and (starts[0]["sequence"] >= finishes[0]["sequence"]
                or any(starts[0]["data"][key] != finishes[0]["data"][key]
                       for key in ("argv", "stdout", "stderr"))):
            raise ValueError("start/finish command evidence mismatch")
        if name != step:
            continue
        if not finishes:
            raise ValueError("selected execution is unfinished or unavailable")
        finish = finishes[0]
        data = finish["data"]
        if (data.get("state") not in ("passed", "failed", "timed_out", "interrupted")
                or not {"returncode", "error", "duration_seconds"} <= data.keys()
                or type(data["duration_seconds"]) not in (int, float)
                or not math.isfinite(data["duration_seconds"]) or data["duration_seconds"] < 0
                or (data["error"] is not None and not isinstance(data["error"], str))):
            raise ValueError("unsupported terminal command evidence schema")
        occurred = bool(starts)
        if occurred and (type(starts[0]["data"].get("pid")) is not int
                or starts[0]["data"]["pid"] <= 0 or type(data["returncode"]) is not int
                or (data["state"] == "passed" and data["returncode"] != 0)):
            raise ValueError("unsupported occurred execution evidence schema")
        if not occurred and (data["state"] != "failed" or data["returncode"] is not None or not data["error"]):
            raise ValueError("missing execution start is not an evidenced launch failure")
        selected = {"step": step, "occurred": occurred,
                    "start_sequence": starts[0]["sequence"] if occurred else None,
                    "finish_sequence": finish["sequence"], "argv": data["argv"],
                    "state": data["state"], "returncode": data["returncode"],
                    "error": data["error"], "duration_seconds": data["duration_seconds"]}
    for event in events:
        if event["kind"] in ("step.started", "step.finished") and event["data"].get("step") not in STEPS:
            raise ValueError("unsupported execution step schema")
        if event["kind"] == "program.started" and event["data"].get("program") not in (
                "development.change/v1", "inquiry.reviewed/v1"):
            raise ValueError("unsupported controller/native-session program schema")
        if event["kind"] == "review.recorded":
            review = event["data"]
            if digest(review["evidence"].encode("utf-8")) != review["evidence_sha256"]:
                raise ValueError("recorded review evidence hash mismatch")
    if selected is None:
        raise ValueError("selected execution is unavailable")
    return status, selected, required


def _snapshot(run_dir: Path, step: str) -> tuple[dict, dict[str, bytes], dict]:
    db = run_dir / "events.sqlite3"
    # WAL readers can create missing shared-memory state. This boundary supports
    # the recorder's rollback-journal DB and explicitly refuses other formats.
    database, db_token = _read(db)
    journal_present = lambda: any(Path(str(db) + suffix).exists() for suffix in ("-wal", "-shm", "-journal"))
    if database[:16] != b"SQLite format 3\0" or database[18:20] != b"\x01\x01" or journal_present():
        raise ValueError("unsupported or actively changing source database journal")
    # Parse a private byte copy so even a concurrently changed journal mode can
    # never cause SQLite to create source sidecars or recover source state.
    with tempfile.TemporaryDirectory(prefix="noetic-act-observation-") as temporary:
        snapshot_dir = Path(temporary)
        snapshot_db = snapshot_dir / "events.sqlite3"
        with open_private(snapshot_db, "xb") as stream:
            stream.write(database)
        with closing(sqlite3.connect(snapshot_db.as_uri() + "?mode=ro&immutable=1", uri=True)) as connection:
            size = connection.execute("SELECT sum(length(CAST(data AS BLOB))) FROM events").fetchone()[0] or 0
            if size > FILE_LIMIT:
                raise ValueError("event evidence exceeds snapshot limit")
            rows = connection.execute("SELECT sequence, occurred_at, kind, data FROM events ORDER BY sequence").fetchall()
        events = runtime.read_events(snapshot_dir)
        exported = [{"sequence": seq, "occurred_at": at, "kind": kind, "data_json": data}
                    for seq, at, kind, data in rows]
        if _decode_events(exported) != events:
            raise ValueError("source event snapshot changed")
        status, selected, required = _describe(events, step)
        names = set(OPTIONAL) | required
        files, tokens, unavailable = {}, {"events.sqlite3": db_token}, []
        for name in sorted(names):
            try:
                content, token = _read(run_dir / name)
            except FileNotFoundError:
                if name in required:
                    raise ValueError(f"missing required execution evidence: {name}") from None
                unavailable.append(name)
                continue
            files[name], tokens[name] = content, token
        database_after, token_after = _read(db)
        if database_after != database or token_after != db_token or journal_present():
            raise ValueError("source events changed during capture")
        files["events.json"] = _canonical(exported)
        if len(files["events.json"]) > FILE_LIMIT or sum(map(len, files.values())) > TOTAL_LIMIT:
            raise ValueError("execution evidence exceeds total snapshot limit")
    description = {"run": status, "selected": selected, "unavailable_optional": unavailable,
                   "required_files": sorted(required | {"events.json"})}
    return description, files, tokens


def _decode_events(exported):
    return [{"sequence": row["sequence"], "occurred_at": row["occurred_at"], "kind": row["kind"],
             "data": json.loads(row["data_json"], object_pairs_hook=_unique)} for row in exported]


def capture(run_dir: Path, evidence_dir: Path, step: str = "work") -> dict:
    """Capture a unique finished retained occurrence; never run its commands."""
    run_dir = Path(run_dir).resolve(strict=True)
    evidence_dir = Path(evidence_dir).absolute()
    destination = evidence_dir.resolve()
    if destination == run_dir or run_dir in destination.parents or destination in run_dir.parents:
        raise ValueError("evidence destination must be separate from the source run")
    first, files, tokens = _snapshot(run_dir, step)
    second, again, next_tokens = _snapshot(run_dir, step)
    if first != second or files != again or tokens != next_tokens:
        raise ValueError("source evidence changed during capture")
    records = {name: {"sha256": digest(content), "bytes": len(content)}
               for name, content in files.items()}
    manifest = {"version": VERSION, "source_run_dir": str(run_dir), **first,
                "files": records, "limits": {"file_bytes": FILE_LIMIT, "total_bytes": TOTAL_LIMIT},
                "limitations": LIMITATIONS}
    serialized = _canonical(manifest)
    if len(serialized) > FILE_LIMIT:
        raise ValueError("observation manifest exceeds file limit")
    if len(serialized) + sum(map(len, files.values())) > TOTAL_LIMIT:
        raise ValueError("observation archive exceeds total snapshot limit")
    ensure_private_directory(evidence_dir.parent)
    evidence_dir.mkdir(mode=0o700)
    ensure_private_directory(evidence_dir)
    for name, content in files.items():
        with open_private(evidence_dir / name, "xb") as stream:
            stream.write(content)
    with open_private(evidence_dir / "manifest.json", "xb") as stream:
        stream.write(serialized)
    return manifest


def revalidate(evidence_dir: Path, expected_manifest_sha256: str, current: bool = False) -> dict:
    """Verify a caller-frozen manifest and archive; optionally compare source bytes."""
    evidence_dir = Path(evidence_dir).resolve(strict=True)
    raw, _ = _read(evidence_dir / "manifest.json")
    if digest(raw) != expected_manifest_sha256:
        raise ValueError("observation manifest hash mismatch")
    manifest = json.loads(raw, object_pairs_hook=_unique)
    if manifest.get("version") != VERSION or raw != _canonical(manifest):
        raise ValueError("unsupported or noncanonical observation manifest")
    files = {}
    allowed = set(OPTIONAL) | {f"{name}.{channel}.log" for name in STEPS for channel in ("stdout", "stderr")} | {"events.json"}
    for name, record in manifest["files"].items():
        if name not in allowed:
            raise ValueError("unsupported evidence archive file")
        content, _ = _read(evidence_dir / name)
        if record != {"sha256": digest(content), "bytes": len(content)}:
            raise ValueError(f"observation evidence hash/length mismatch: {name}")
        files[name] = content
    if len(raw) + sum(map(len, files.values())) > TOTAL_LIMIT or not set(manifest["required_files"]) <= files.keys():
        raise ValueError("missing or oversized required observation evidence")
    events = _decode_events(json.loads(files["events.json"], object_pairs_hook=_unique))
    status, selected, required = _describe(events, manifest["selected"]["step"])
    if (status != manifest["run"] or selected != manifest["selected"]
            or sorted(required | {"events.json"}) != manifest["required_files"]):
        raise ValueError("observation event binding mismatch")
    if current:
        source = Path(manifest["source_run_dir"]).resolve(strict=True)
        observed, original, tokens = _snapshot(source, selected["step"])
        again, next_files, next_tokens = _snapshot(source, selected["step"])
        expected = {key: manifest[key] for key in observed}
        if (observed != expected or original != files or observed != again
                or original != next_files or tokens != next_tokens):
            raise ValueError("original source evidence drifted")
    return manifest
