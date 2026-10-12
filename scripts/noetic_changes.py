"""Read-only working-file snapshots and observed run changes (not authorship proof)."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess


TEXT_LIMIT = 256 * 1024
NOTICE = "Changes observed during the run; not proof that the worker caused every change."


def snapshot(workspace: Path, previous_paths=()) -> dict:
    """Keep bounded text in memory, hashing full contents without modifying Git."""
    try:
        probe = subprocess.run(["git", "-C", str(workspace), "rev-parse", "--is-inside-work-tree"],
                               capture_output=True, check=False)
        if probe.returncode or probe.stdout.strip() != b"true":
            return {"files": None, "reason": "Git working-tree baseline unavailable (not a Git workspace)."}
        listed = subprocess.run(["git", "-C", str(workspace), "ls-files", "--cached", "--others",
                                 "--exclude-standard", "-z"], capture_output=True, check=True)
        paths = {os.fsdecode(path) for path in listed.stdout.split(b"\0") if path}
        files = {}
        # Keep observing baseline paths even if ignore rules change during work.
        for name in sorted(paths | set(previous_paths)):
            path = workspace / name
            try:
                mode = path.lstat().st_mode
            except FileNotFoundError:
                continue
            entry = {"sha256": None, "size": None, "mode": stat.S_IMODE(mode),
                     "kind": "file", "omission_reason": None, "text": None}
            if stat.S_ISLNK(mode):
                content = os.fsencode(os.readlink(path))
                entry.update(kind="symlink", sha256=hashlib.sha256(content).hexdigest(), size=len(content))
            elif stat.S_ISREG(mode):
                digest, size, chunks = hashlib.sha256(), 0, []
                with path.open("rb") as stream:
                    while chunk := stream.read(65536):
                        digest.update(chunk)
                        size += len(chunk)
                        if size <= TEXT_LIMIT:
                            chunks.append(chunk)
                entry.update(sha256=digest.hexdigest(), size=size)
                content = b"".join(chunks)
            else:
                entry.update(kind="unsupported", omission_reason="Not a regular file or symlink (e.g. submodule); content not captured.")
                files[name] = entry
                continue
            if entry["size"] > TEXT_LIMIT:
                entry["omission_reason"] = f"Content exceeds {TEXT_LIMIT} bytes."
            else:
                try:
                    if b"\0" in content:
                        raise ValueError("binary")
                    entry["text"] = content.decode("utf-8")
                except (UnicodeDecodeError, ValueError):
                    entry["omission_reason"] = "Binary or non-UTF-8 content."
            files[name] = entry
        return {"files": files, "reason": None}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"files": None, "reason": f"Working-file snapshot unavailable: {exc}"}


def retain_changes(workspace: Path, run_dir: Path, before: dict) -> None:
    after = snapshot(workspace, before["files"] or ()) if before["files"] is not None else before
    reason = before["reason"] or after["reason"]
    manifest = {"notice": NOTICE, "status": "unavailable" if reason else "available",
                "reason": reason, "hash_algorithm": "sha256", "text_limit_bytes": TEXT_LIMIT,
                "changes": None if reason else []}
    diff = [f"# {NOTICE}\n"]
    if reason:
        diff.append(f"# Unavailable evidence: {reason}\n")
    else:
        old_files, new_files = before["files"], after["files"]
        assert old_files is not None and new_files is not None
        for name in sorted(old_files.keys() | new_files.keys()):
            old, new = old_files.get(name), new_files.get(name)
            if old == new:
                continue
            omission = next((entry["omission_reason"] for entry in (old, new)
                             if entry and entry["omission_reason"]), None)
            change = {"path": name, "status": "added" if old is None else "deleted" if new is None else "modified",
                      "before": {k: v for k, v in old.items() if k != "text"} if old else None,
                      "after": {k: v for k, v in new.items() if k != "text"} if new else None,
                      "diff_omission_reason": omission}
            manifest["changes"].append(change)
            label = json.dumps(name, ensure_ascii=True)
            if omission:
                diff.append(f"# Omitted {label}: {omission}\n")
                continue
            diff.append(f"# {change['status']} {label}; metadata and hashes in changes.json\n")
            lines = difflib.unified_diff((old["text"] if old else "").splitlines(keepends=True),
                                         (new["text"] if new else "").splitlines(keepends=True),
                                         fromfile="a/" + label if old else "/dev/null",
                                         tofile="b/" + label if new else "/dev/null")
            for line in lines:
                diff.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
        if not manifest["changes"]:
            diff.append("# No changes observed in selected working files.\n")
    (run_dir / "changes.diff").write_text("".join(diff), encoding="utf-8")
    (run_dir / "changes.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
