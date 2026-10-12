"""Bounded, offline, private run snapshots. Never resume actors or follow references."""

import argparse
from contextlib import ExitStack, closing, contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import tempfile
import zipfile

from scripts.noetic_storage import ensure_private_directory, open_private, create_private_sqlite, inspect_tree

MAX_BYTES = 256 * 1024 * 1024
MAX_FILES = 4096
MANIFEST = "SHA256.json"
RETAINED = {
    "task.md", "options.json", "work.md", "review.md", "work.json", "review.json",
    "changes.json", "changes.diff", "prompt.txt", "response.json",
    "submission.json", "model-result.json", "final-response.txt",
    "actor-process.json", "verify-process.json", "actor-ownership.json", "verify-ownership.json",
}


def safe_name(name):
    if (not isinstance(name, str) or not name or "\\" in name
            or any(ord(c) < 32 for c in name) or PurePosixPath(name).is_absolute()
            or any(p in ("", ".", "..") for p in name.split("/"))):
        raise ValueError(f"Invalid bundle path: {name!r}")
    return name


def private_directory(path):
    path = ensure_private_directory(path)
    if stat.S_IMODE(path.stat().st_mode) != 0o700:
        raise ValueError(f"Select a private 0700 directory: {path}")
    return path


def read_regular(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError(f"Symlink input: {path}")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
        raise ValueError(f"Not a bounded regular file: {path}")
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("File exceeds bundle limit")
    return data


def write_bundle(output, files, metadata):
    if MANIFEST in files or len(files) > MAX_FILES or sum(map(len, files.values())) > MAX_BYTES:
        raise ValueError("Bundle exceeds limits or uses reserved manifest name")
    for name in files:
        safe_name(name)
    manifest = {**metadata, "files": {name: hashlib.sha256(data).hexdigest()
                                     for name, data in sorted(files.items())}}
    with open_private(output, "xb") as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in {**files, MANIFEST: json.dumps(manifest, sort_keys=True).encode()}.items():
                entry = zipfile.ZipInfo(name)
                entry.external_attr = (stat.S_IFREG | 0o600) << 16
                archive.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED)
    return manifest


def read_bundle(path, kind):
    files = {}
    with zipfile.ZipFile(Path(path)) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_FILES + 1 or sum(e.file_size for e in entries) > MAX_BYTES + 1024 * 1024:
            raise ValueError("Bundle exceeds limits")
        for entry in entries:
            safe_name(entry.filename)
            mode = entry.external_attr >> 16
            if (entry.filename in files or entry.is_dir() or entry.flag_bits & 1
                    or stat.S_IFMT(mode) not in (0, stat.S_IFREG)):
                raise ValueError("Duplicate, link, encrypted or non-file bundle entry")
            files[entry.filename] = archive.read(entry)
    raw_manifest = files.pop(MANIFEST)
    if len(raw_manifest) > 1024 * 1024 or sum(map(len, files.values())) > MAX_BYTES:
        raise ValueError("Bundle exceeds limits")
    manifest = json.loads(raw_manifest)
    if manifest.get("format") != kind or manifest.get("version") != 1:
        raise ValueError("Unsupported bundle format/version")
    if manifest.get("files") != {n: hashlib.sha256(d).hexdigest() for n, d in files.items()}:
        raise ValueError("Bundle checksum mismatch")
    return files, manifest


def extract_files(root, files):
    for name, data in files.items():
        safe_name(name)
        with open_private(Path(root) / name, "xb") as stream:
            stream.write(data)


@contextmanager
def quiescent_run(run, allow_held=False):
    """Hold cooperative driver locks, checking authority without runtime mutations."""
    run = Path(run)
    report = inspect_tree(run)
    if report["skipped"]:
        raise ValueError("Run contains links, special files or foreign-owned entries")
    with ExitStack() as stack:
        for name in ("application-driver.lock", "driver.lock"):
            stream = stack.enter_context(open_private(run / name, "a"))
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("Run has an owned driver; stop it before maintenance") from exc
        check_run(run, allow_held)
        yield
        check_run(run, allow_held)


def check_run(run, allow_held=False):
    from scripts import noetic_run, noetic_controller, noetic_harness
    run = Path(run)
    events = noetic_run.read_events(run)
    summary = noetic_run.project(events)
    if events[0]["data"].get("version") != 1 or summary["run_id"] != run.name:
        raise ValueError("Unsupported journal version or mismatched run identity")
    unfinished = any("state" not in step for step in summary["steps"].values())
    cleanup_confirmed = False
    if (run / "controller.sqlite3").exists():
        state = noetic_controller.inspect_run(run / "controller.sqlite3")
        if state.get("schema_version") != 1:
            raise ValueError("Unsupported controller schema")
        statuses = [a["status"] for a in state["activations"].values()]
        if "running" in statuses:
            raise ValueError("Running activation; operator intervention required")
        if state["status"] == "active":
            current = state["activations"].get(state["current_activation"], {})
            if not allow_held or current.get("status") != "ready":
                raise ValueError("Held-ready run requires --allow-held")
        elif state["status"] not in ("completed", "cancelled", "failed", "blocked"):
            raise ValueError("Unsupported controller status")
        if (run / "options.json").exists():
            cleanup = noetic_harness.process_info(run, state)
            if not cleanup["cleanup_confirmed"]:
                raise ValueError("Process cleanup unconfirmed; operator intervention required")
            # Only harness step observations covered by cumulative ownership can
            # replace a missing exit observation. Never manufacture step.finished.
            cleanup_confirmed = all(name in cleanup["processes"] for name, step in summary["steps"].items()
                                    if "state" not in step)
    elif summary["state"] not in ("accepted", "rejected", "awaiting_review", "failed", "interrupted", "timed_out", "cancelled"):
        raise ValueError("Run has no quiescent terminal event")
    if unfinished and not cleanup_confirmed:
        raise ValueError("Unfinished process observation; operator intervention required")
    return summary


def sqlite_backup(source, target, telos=False):
    read_regular(source)
    with closing(sqlite3.connect(Path(source).absolute().as_uri() + "?mode=ro", uri=True)) as src:
        if telos and src.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() != ("2",):
            raise ValueError("Only Telos schema 2 snapshots are supported")
        with closing(sqlite3.connect(create_private_sqlite(target))) as dst:
            src.backup(dst)
            if dst.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ValueError("SQLite integrity check failed")
            dst.execute("PRAGMA journal_mode=DELETE")


def retained(name):
    parts = PurePosixPath(name).parts
    if len(parts) != 1 and not (len(parts) == 3 and parts[0] == "activations"
                               and re.fullmatch(r"activation-[0-9]+", parts[1])):
        return False
    leaf = parts[-1]
    if leaf == "options.json":
        return len(parts) == 1
    return leaf in RETAINED or bool(re.fullmatch(r"(?:work|verify|review|actor)(?:\.stdout\.log|\.stderr\.log|-prompt\.txt)", leaf))


def export_run(run, output, *, allow_held=False, telos_db=None):
    run, output = Path(run).absolute(), Path(output).absolute()
    if output.is_relative_to(run):
        raise ValueError("Archive output must be outside the run")
    with quiescent_run(run, allow_held), tempfile.TemporaryDirectory() as temporary:
        files = {}
        for name in ("events.sqlite3", "controller.sqlite3"):
            if (run / name).exists():
                target = Path(temporary) / name
                sqlite_backup(run / name, target)
                files[f"run/{name}"] = read_regular(target)
        for path in run.rglob("*"):
            name = path.relative_to(run).as_posix()
            if path.is_file() and retained(name):
                files[f"run/{name}"] = read_regular(path)
                if len(files) > MAX_FILES or sum(map(len, files.values())) > MAX_BYTES:
                    raise ValueError("Run exceeds archive limits")
        if telos_db is not None:
            target = Path(temporary) / "telos.sqlite3"
            sqlite_backup(telos_db, target, telos=True)
            files["private-telos/telos.sqlite3"] = read_regular(target)
        return write_bundle(output, files, {
            "format": "noetic-run-archive", "version": 1, "run_id": run.name,
            "controller_schema": 1 if "run/controller.sqlite3" in files else None,
            "telos_schema": 2 if telos_db is not None else None,
            "privacy": "FULL PRIVATE TELOS DATABASE" if telos_db is not None else "PRIVATE RUN ONLY",
            "historical_paths": "References are historical; import does not remap or resume work",
        })


def import_run(archive, root):
    files, manifest = read_bundle(archive, "noetic-run-archive")
    run_id = manifest.get("run_id", "")
    if not re.fullmatch(r"[a-fA-F0-9]{32}", run_id):
        raise ValueError("Invalid run identity")
    if manifest.get("controller_schema") != (1 if "run/controller.sqlite3" in files else None):
        raise ValueError("Incompatible controller schema")
    has_telos = "private-telos/telos.sqlite3" in files
    if manifest.get("telos_schema") != (2 if has_telos else None):
        raise ValueError("Incompatible Telos schema")
    for name in files:
        if name == "private-telos/telos.sqlite3":
            continue
        if not name.startswith("run/") or (name[4:] not in ("events.sqlite3", "controller.sqlite3") and not retained(name[4:])):
            raise ValueError("Unexpected archive payload")
    root = Path(root).absolute()
    private_directory(root.parent)
    if root.exists() or root.is_symlink():
        raise FileExistsError("Restore requires a new root; no state overwrite")
    with tempfile.TemporaryDirectory(prefix=".noetic-restore-", dir=root.parent) as temporary:
        stage = Path(temporary) / "restored"
        private_directory(stage)
        mapped = {("runs/" + run_id + "/" + n[4:] if n.startswith("run/") else n): d for n, d in files.items()}
        extract_files(stage, mapped)
        check_run(stage / "runs" / run_id, allow_held=True)
        if has_telos:
            sqlite_backup(stage / "private-telos/telos.sqlite3", Path(temporary) / "check.sqlite3", telos=True)
        os.rename(stage, root)
    return {"root": str(root), "run": str(root / "runs" / run_id), "privacy": manifest["privacy"], "advanced": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("run", type=Path)
    export.add_argument("output", type=Path)
    export.add_argument("--allow-held", action="store_true")
    export.add_argument("--telos-db", type=Path, help="Explicit FULL private database snapshot, not just this run")
    restore = commands.add_parser("import")
    restore.add_argument("archive", type=Path)
    restore.add_argument("root", type=Path, help="New private root only")
    args = parser.parse_args(argv)
    try:
        result = (export_run(args.run, args.output, allow_held=args.allow_held, telos_db=args.telos_db)
                  if args.command == "export" else import_run(args.archive, args.root))
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, zipfile.BadZipFile) as exc:
        parser.exit(2, f"archive: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
