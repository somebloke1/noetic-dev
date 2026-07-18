#!/usr/bin/python3 -I
"""Validate completed protected-route runs from their exact protected base."""

from __future__ import annotations

import sys

if sys.path:
    sys.path.pop(0)

import argparse
import ctypes
import fcntl
import hashlib
import json
import os
import pwd
import re
import secrets
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from route_evidence import (
    AGENT_REVIEW_WORKFLOW_ID,
    ARTIFACT_DIGEST,
    REPOSITORY,
    REPOSITORY_ID,
    _timestamp,
    _valid_artifact,
    _valid_review_job,
    github_json,
    github_json_pages,
    parse_json_strict,
)

REMOTE_URL = "https://github.com/somebloke1/noetic-dev.git"
ARTIFACT_NAME = re.compile(r"^agent-review-([1-9][0-9]*)-([a-f0-9]{40})$")
RECEIPT_FIELDS = {
    "schema_version", "repository", "run_id", "run_attempt", "workflow_id", "job_id",
    "pr_number", "head_sha", "base_sha", "artifact_id", "artifact_name",
    "artifact_digest", "artifact_size", "run_head_sha", "run_head_branch", "pr_state",
    "pr_merged", "validator_sha256", "result", "validated_at",
}
RENAME_NOREPLACE = 1
LIBC = ctypes.CDLL(None, use_errno=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", type=bounded_ascii_id)
    parser.add_argument("--after-run-id", type=bounded_ascii_id, default=0)
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path.home() / ".local/state/noetic-dev/route-attestations",
    )
    args = parser.parse_args()
    if args.run_id is not None and args.run_id <= 0:
        parser.error("--run-id must be positive")
    if args.after_run_id < 0:
        parser.error("--after-run-id cannot be negative")

    try:
        cursor = load_cursor(args.state_dir, args.after_run_id) if args.run_id is None else 0
        runs = select_runs(args.run_id, cursor, args.state_dir)
        if not runs:
            print("No unattested successful Agent Review run")
            return 0
    except (OSError, ValueError, TypeError, AttributeError, subprocess.TimeoutExpired) as error:
        print(f"protected route attestation failed: {error}", file=sys.stderr)
        return 1
    failed = False
    blocked = False
    progress = cursor
    for run in runs:
        try:
            receipt = args.state_dir / f"run-{run['id']}-attempt-{run['run_attempt']}.json"
            if os.path.lexists(receipt):
                validate_existing_receipt(receipt, run["id"], run["run_attempt"])
            else:
                receipt = attest_run(run, args.state_dir)
        except (OSError, ValueError, TypeError, AttributeError, subprocess.TimeoutExpired) as error:
            failed = True
            blocked = True
            print(f"run {run['id']} attestation failed: {error}", file=sys.stderr)
        else:
            print(f"Protected route attestation recorded: {receipt}")
            if not blocked:
                progress = run["id"]
    if args.run_id is None and progress > cursor:
        write_cursor(args.state_dir, progress)
    return 1 if failed else 0


def bounded_ascii_id(value: str) -> int:
    if re.fullmatch(r"[1-9][0-9]*", value) is None:
        raise argparse.ArgumentTypeError("identifier must be positive ASCII decimal")
    parsed = int(value)
    if parsed > 9_223_372_036_854_775_807:
        raise argparse.ArgumentTypeError("identifier is out of range")
    return parsed


def select_runs(run_id: int | None, after_run_id: int, state_dir: Path) -> list[dict[str, Any]]:
    if run_id is not None:
        run = github_json(f"repos/{REPOSITORY}/actions/runs/{run_id}")
        candidates = [run]
    else:
        candidates_by_id: dict[tuple[int, int], dict[str, Any]] = {}
        conflicted: set[tuple[int, int]] = set()
        pages = github_json_pages(
            f"repos/{REPOSITORY}/actions/workflows/{AGENT_REVIEW_WORKFLOW_ID}/runs"
            "?per_page=100"
        )
        for response in pages:
            page_runs = response.get("workflow_runs") if isinstance(response, dict) else None
            if not isinstance(page_runs, list):
                raise ValueError("Agent Review run inventory is invalid")
            for candidate in page_runs:
                if not isinstance(candidate, dict):
                    print("skipping malformed Agent Review inventory record", file=sys.stderr)
                    continue
                identity = (candidate.get("id"), candidate.get("run_attempt"))
                if type(identity[0]) is not int or type(identity[1]) is not int:
                    print("skipping malformed Agent Review run identity", file=sys.stderr)
                    continue
                if identity in conflicted:
                    continue
                previous = candidates_by_id.get(identity)
                if previous is not None and previous != candidate:
                    print("skipping conflicting Agent Review run identity", file=sys.stderr)
                    candidates_by_id.pop(identity, None)
                    conflicted.add(identity)
                    continue
                candidates_by_id[identity] = candidate
        candidates = list(candidates_by_id.values())
        if after_run_id > 0 and not any(
            candidate.get("id") == after_run_id for candidate in candidates
        ):
            raise ValueError("Agent Review inventory is truncated before the verified cursor")
    selected = []
    ordered = sorted(candidates, key=lambda item: item.get("id", 0))
    pending = [
        run["id"] for run in ordered
        if type(run.get("id")) is int
        and run["id"] > after_run_id
        and run.get("status") != "completed"
    ]
    terminal_ceiling = min(pending) if pending else None
    for run in ordered:
        if not isinstance(run, dict) or type(run.get("id")) is not int:
            print("skipping malformed Agent Review run", file=sys.stderr)
            continue
        if run["id"] <= after_run_id:
            continue
        if terminal_ceiling is not None and run["id"] >= terminal_ceiling:
            continue
        attempt = run.get("run_attempt")
        if type(attempt) is not int or attempt <= 0:
            print(f"skipping Agent Review run {run['id']} with invalid attempt", file=sys.stderr)
            continue
        receipt = state_dir / f"run-{run['id']}-attempt-{attempt}.json"
        if (
            run.get("workflow_id") == AGENT_REVIEW_WORKFLOW_ID
            and run.get("path") == ".github/workflows/agent-review.yml"
            and run.get("event") == "pull_request_target"
            and run.get("status") == "completed"
            and run.get("conclusion") == "success"
        ):
            selected.append(run)
    return selected


def load_cursor(state_dir: Path, bootstrap: int) -> int:
    path = state_dir / "cursor.json"
    if not os.path.lexists(path):
        return bootstrap
    parent = os.lstat(path.parent)
    if parent.st_uid != os.getuid() or parent.st_mode & 0o777 != 0o700:
        raise ValueError("attestation cursor directory is unsafe")
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_mode & 0o777 != 0o600
            or metadata.st_nlink != 1
            or metadata.st_size > 4096
        ):
            raise ValueError("attestation cursor is unsafe")
        payload = parse_json_strict(os.read(descriptor, 4097))
    finally:
        os.close(descriptor)
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_version", "repository", "run_id"}
        or payload.get("schema_version") != "1"
        or payload.get("repository") != REPOSITORY
        or type(payload.get("run_id")) is not int
        or payload["run_id"] < bootstrap
    ):
        raise ValueError("attestation cursor is invalid")
    return payload["run_id"]


def write_cursor(state_dir: Path, run_id: int) -> None:
    state_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(state_dir, 0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".cursor-", dir=state_dir)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        payload = json.dumps(
            {"schema_version": "1", "repository": REPOSITORY, "run_id": run_id},
            sort_keys=True, separators=(",", ":"),
        ).encode("ascii") + b"\n"
        os.write(descriptor, payload)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, state_dir / "cursor.json")
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def attest_run(run: dict[str, Any], state_dir: Path) -> Path:
    if type(run.get("id")) is not int or run["id"] <= 0:
        raise ValueError("selected run identity is invalid")
    if type(run.get("run_attempt")) is not int or run["run_attempt"] != 1:
        raise ValueError("selected run attempt is invalid")
    before = load_attestation_context(run["id"])
    if before["run_attempt"] != run["run_attempt"]:
        raise ValueError("selected run changed before attestation")
    validator_digest = validate_from_protected_base(
        before["run_id"], before["pr_number"], before["head_sha"], before["base_sha"]
    )
    after = load_attestation_context(run["id"])
    if before != after:
        raise ValueError("protected run metadata changed during attestation")
    receipt = {
        "schema_version": "1",
        **after,
        "validator_sha256": validator_digest,
        "result": "valid",
        "validated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    receipt_path = state_dir / f"run-{after['run_id']}-attempt-{after['run_attempt']}.json"
    write_receipt(receipt_path, receipt)
    return receipt_path


def load_attestation_context(run_id: int) -> dict[str, Any]:
    run = github_json(f"repos/{REPOSITORY}/actions/runs/{run_id}")
    artifacts = github_json(f"repos/{REPOSITORY}/actions/runs/{run_id}/artifacts")
    listed = artifacts.get("artifacts") if isinstance(artifacts, dict) else None
    if (
        not isinstance(artifacts, dict)
        or type(artifacts.get("total_count")) is not int
        or artifacts.get("total_count") != 1
        or not isinstance(listed, list)
        or len(listed) != 1
    ):
        raise ValueError("run does not have exactly one retained artifact")
    artifact = listed[0]
    artifact_name = artifact.get("name") if isinstance(artifact, dict) else None
    match = ARTIFACT_NAME.fullmatch(artifact_name) if isinstance(artifact_name, str) else None
    if match is None:
        raise ValueError("retained artifact name does not bind a PR and candidate SHA")
    pr_number = int(match.group(1))
    head_sha = match.group(2)

    pull = github_json(f"repos/{REPOSITORY}/pulls/{pr_number}")
    jobs = github_json(f"repos/{REPOSITORY}/actions/runs/{run_id}/jobs?filter=latest")
    listed_jobs = jobs.get("jobs") if isinstance(jobs, dict) else None
    head = pull.get("head") if isinstance(pull, dict) else None
    base = pull.get("base") if isinstance(pull, dict) else None
    if (
        not isinstance(run, dict)
        or type(run.get("id")) is not int
        or run.get("id") != run_id
        or type(run.get("run_attempt")) is not int
        or run.get("run_attempt") != 1
        or type(run.get("workflow_id")) is not int
        or run.get("workflow_id") != AGENT_REVIEW_WORKFLOW_ID
        or run.get("path") != ".github/workflows/agent-review.yml"
        or run.get("event") != "pull_request_target"
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or not isinstance(run.get("repository"), dict)
        or type(run["repository"].get("id")) is not int
        or run["repository"].get("id") != REPOSITORY_ID
        or run["repository"].get("full_name") != REPOSITORY
        or not isinstance(run.get("head_repository"), dict)
        or type(run["head_repository"].get("id")) is not int
        or run["head_repository"].get("id") != REPOSITORY_ID
        or run["head_repository"].get("full_name") != REPOSITORY
        or not isinstance(pull, dict)
        or type(pull.get("number")) is not int
        or pull.get("number") != pr_number
        or pull.get("draft") is not False
        or pull.get("state") != "closed"
        or pull.get("merged") is not True
        or not isinstance(head, dict)
        or not isinstance(head.get("ref"), str)
        or head.get("sha") != head_sha
        or not isinstance(head.get("repo"), dict)
        or type(head["repo"].get("id")) is not int
        or head["repo"].get("id") != REPOSITORY_ID
        or head["repo"].get("full_name") != REPOSITORY
        or not isinstance(base, dict)
        or base.get("ref") != "dev"
        or not isinstance(base.get("sha"), str)
        or re.fullmatch(r"[a-f0-9]{40}", base["sha"]) is None
        or not isinstance(base.get("repo"), dict)
        or type(base["repo"].get("id")) is not int
        or base["repo"].get("id") != REPOSITORY_ID
        or base["repo"].get("full_name") != REPOSITORY
        or run.get("head_branch") != head.get("ref")
        or not isinstance(run.get("head_sha"), str)
        or run.get("head_sha") not in {head_sha, base["sha"]}
        or not isinstance(jobs, dict)
        or type(jobs.get("total_count")) is not int
        or jobs.get("total_count") != 1
        or not isinstance(listed_jobs, list)
        or len(listed_jobs) != 1
        or not _valid_review_job(listed_jobs[0], run_id, head_sha, base["sha"])
        or not _valid_artifact(artifact, run_id, head_sha, f"agent-review-{pr_number}-{head_sha}")
    ):
        raise ValueError("run, PR, job, or artifact metadata is invalid")
    return {
        "repository": REPOSITORY,
        "run_id": run_id,
        "run_attempt": run["run_attempt"],
        "workflow_id": run["workflow_id"],
        "job_id": listed_jobs[0]["id"],
        "pr_number": pr_number,
        "head_sha": head_sha,
        "base_sha": base["sha"],
        "artifact_id": artifact["id"],
        "artifact_name": artifact["name"],
        "artifact_digest": artifact["digest"],
        "artifact_size": artifact["size_in_bytes"],
        "run_head_sha": run["head_sha"],
        "run_head_branch": run["head_branch"],
        "pr_state": pull["state"],
        "pr_merged": pull["merged"],
    }


def validate_from_protected_base(run_id: int, pr_number: int, head_sha: str, base_sha: str) -> str:
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    environment = {
        "HOME": str(home),
        "GH_CONFIG_DIR": str(home / ".config/gh"),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "NO_COLOR": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    with tempfile.TemporaryDirectory(prefix="noetic-route-attestation-") as directory:
        checkout = Path(directory) / "repository"
        clone = subprocess.run(
            [
                "/usr/bin/git", "clone", "--filter=blob:none", "--no-checkout", "--no-local",
                REMOTE_URL, str(checkout),
            ],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
            check=False,
        )
        if clone.returncode != 0:
            raise ValueError("protected repository clone failed")
        detached = subprocess.run(
            [
                "/usr/bin/git", "--no-replace-objects", "-C", str(checkout),
                "checkout", "--detach", base_sha,
            ],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
            check=False,
        )
        if detached.returncode != 0:
            raise ValueError("protected base checkout failed")
        validator = checkout / "scripts/governance/route_evidence.py"
        if not validator.is_file() or validator.is_symlink():
            raise ValueError("protected base does not contain the route validator")
        validator_digest = hashlib.sha256(validator.read_bytes()).hexdigest()
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            validation = subprocess.run(
                [
                    "/usr/bin/python3", "-I", str(validator), "--run-id", str(run_id),
                    "--pr-number", str(pr_number), "--head-sha", head_sha,
                ],
                cwd=checkout,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                timeout=120,
                check=False,
            )
            if stdout.tell() > 65_536 or stderr.tell() > 65_536:
                raise ValueError("protected-base route validator output is oversized")
            stdout.seek(0)
            stderr.seek(0)
            if (
                validation.returncode != 0
                or stdout.read() != b"Protected route evidence is valid\n"
                or stderr.read() != b""
            ):
                raise ValueError("protected-base route validator rejected the run")
        return validator_digest


def validate_existing_receipt(path: Path, run_id: int, attempt: int) -> None:
    parent_path = os.lstat(path.parent)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        parent = os.fstat(directory)
        if (
            not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.getuid()
            or parent.st_mode & 0o777 != 0o700
            or (parent.st_dev, parent.st_ino) != (parent_path.st_dev, parent_path.st_ino)
        ):
            raise ValueError("existing attestation receipt directory is unsafe")
        descriptor = os.open(
            path.name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=directory
        )
        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_mode & 0o777 != 0o600
                or metadata.st_nlink != 1
                or metadata.st_size > 65_536
            ):
                raise ValueError("existing attestation receipt is unsafe")
            chunks = []
            remaining = 65_537
            while remaining:
                chunk = os.read(descriptor, remaining)
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            current = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
            current_parent = os.lstat(path.parent)
            if (
                (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino)
                or current.st_nlink != 1
                or (current_parent.st_dev, current_parent.st_ino)
                != (parent.st_dev, parent.st_ino)
            ):
                raise ValueError("attestation receipt changed during validation")
        finally:
            os.close(descriptor)
    finally:
        os.close(directory)
    if len(raw) > 65_536:
        raise ValueError("existing attestation receipt is oversized")
    receipt = parse_json_strict(raw)
    if not _valid_receipt(receipt, run_id, attempt):
        raise ValueError("existing attestation receipt is invalid")


def _valid_receipt(receipt: Any, run_id: int, attempt: int) -> bool:
    return not (
        not isinstance(receipt, dict)
        or set(receipt) != RECEIPT_FIELDS
        or receipt.get("schema_version") != "1"
        or receipt.get("repository") != REPOSITORY
        or type(receipt.get("run_id")) is not int
        or receipt.get("run_id") != run_id
        or type(receipt.get("run_attempt")) is not int
        or receipt.get("run_attempt") != attempt
        or type(receipt.get("workflow_id")) is not int
        or receipt.get("workflow_id") != AGENT_REVIEW_WORKFLOW_ID
        or type(receipt.get("job_id")) is not int
        or receipt["job_id"] <= 0
        or type(receipt.get("pr_number")) is not int
        or receipt["pr_number"] <= 0
        or not isinstance(receipt.get("head_sha"), str)
        or re.fullmatch(r"[a-f0-9]{40}", receipt["head_sha"]) is None
        or not isinstance(receipt.get("base_sha"), str)
        or re.fullmatch(r"[a-f0-9]{40}", receipt["base_sha"]) is None
        or receipt["base_sha"] == receipt["head_sha"]
        or type(receipt.get("artifact_id")) is not int
        or receipt["artifact_id"] <= 0
        or receipt.get("artifact_name")
        != f"agent-review-{receipt['pr_number']}-{receipt['head_sha']}"
        or not isinstance(receipt.get("artifact_digest"), str)
        or ARTIFACT_DIGEST.fullmatch(receipt["artifact_digest"]) is None
        or type(receipt.get("artifact_size")) is not int
        or not 0 < receipt["artifact_size"] <= 1_048_576
        or not isinstance(receipt.get("run_head_sha"), str)
        or receipt["run_head_sha"] not in {receipt["head_sha"], receipt["base_sha"]}
        or not isinstance(receipt.get("run_head_branch"), str)
        or not receipt["run_head_branch"]
        or type(receipt.get("pr_merged")) is not bool
        or not (
            (receipt.get("pr_state") == "open" and receipt["pr_merged"] is False)
            or (receipt.get("pr_state") == "closed" and receipt["pr_merged"] is True)
        )
        or not isinstance(receipt.get("validator_sha256"), str)
        or re.fullmatch(r"[a-f0-9]{64}", receipt["validator_sha256"]) is None
        or receipt.get("result") != "valid"
        or _timestamp(receipt.get("validated_at")) is None
    )


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    if (
        type(receipt.get("run_id")) is not int
        or type(receipt.get("run_attempt")) is not int
        or not _valid_receipt(receipt, receipt["run_id"], receipt["run_attempt"])
    ):
        raise ValueError("attestation receipt payload is invalid")
    if os.path.lexists(path.parent) and path.parent.is_symlink():
        raise ValueError("attestation receipt directory is unsafe")
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(path.parent, 0o700)
    parent_path = os.lstat(path.parent)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    lock_name = path.name + ".lock"
    lock_descriptor: int | None = None
    lock_acquired = False
    receipt_descriptor: int | None = None
    temporary_name: str | None = None
    try:
        parent = os.fstat(directory)
        if (
            not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.getuid()
            or parent.st_mode & 0o777 != 0o700
            or (parent.st_dev, parent.st_ino) != (parent_path.st_dev, parent_path.st_ino)
        ):
            raise ValueError("attestation receipt path is unsafe")
        try:
            os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError("attestation receipt path already exists")
        lock_descriptor = os.open(
            lock_name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600,
            dir_fd=directory,
        )
        lock_metadata = os.fstat(lock_descriptor)
        if (
            not stat.S_ISREG(lock_metadata.st_mode)
            or lock_metadata.st_uid != os.getuid()
            or lock_metadata.st_mode & 0o777 != 0o600
            or lock_metadata.st_nlink != 1
        ):
            raise ValueError("attestation receipt lock is unsafe")
        try:
            fcntl.flock(lock_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("attestation receipt is already being written") from error
        lock_acquired = True
        os.ftruncate(lock_descriptor, 0)
        os.write(lock_descriptor, f"{os.getpid()}\n".encode("ascii"))
        os.fsync(lock_descriptor)
        try:
            os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError("attestation receipt path appeared during locking")
        temporary_name = f".route-attestation-{secrets.token_hex(16)}"
        receipt_descriptor = os.open(
            temporary_name,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        raw = json.dumps(
            receipt, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ).encode("ascii") + b"\n"
        written = 0
        while written < len(raw):
            written += os.write(receipt_descriptor, raw[written:])
        os.fsync(receipt_descriptor)
        temporary = os.stat(temporary_name, dir_fd=directory, follow_symlinks=False)
        anonymous = os.fstat(receipt_descriptor)
        if (temporary.st_dev, temporary.st_ino) != (anonymous.st_dev, anonymous.st_ino):
            raise ValueError("attestation receipt temporary file changed")
        _rename_noreplace(directory, temporary_name, path.name)
        temporary_name = None
        published = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        current_parent = os.lstat(path.parent)
        if (
            (published.st_dev, published.st_ino) != (anonymous.st_dev, anonymous.st_ino)
            or published.st_nlink != 1
            or published.st_uid != os.getuid()
            or published.st_mode & 0o777 != 0o600
            or (current_parent.st_dev, current_parent.st_ino)
            != (parent.st_dev, parent.st_ino)
        ):
            os.unlink(path.name, dir_fd=directory)
            raise ValueError("attestation receipt publication was not exclusive")
        os.fsync(directory)
    finally:
        if receipt_descriptor is not None:
            os.close(receipt_descriptor)
        if temporary_name is not None:
            try:
                os.unlink(temporary_name, dir_fd=directory)
            except FileNotFoundError:
                pass
        if lock_descriptor is not None:
            if lock_acquired:
                try:
                    fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(lock_descriptor)
        os.close(directory)


def _rename_noreplace(directory: int, source: str, destination: str) -> None:
    result = LIBC.renameat2(
        ctypes.c_int(directory), ctypes.c_char_p(os.fsencode(source)),
        ctypes.c_int(directory), ctypes.c_char_p(os.fsencode(destination)),
        ctypes.c_uint(RENAME_NOREPLACE),
    )
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), destination)


if __name__ == "__main__":
    raise SystemExit(main())
