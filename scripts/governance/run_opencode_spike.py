#!/usr/bin/env python3
"""One-time, non-evidence OpenCode credential-isolation spike controller."""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import math
import os
import re
import resource
import select
import secrets
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


COMPONENT_SHA = "f2b839b0cfc737c4c1f0a46d3d519d414529545c"
RUNTIME_ROOT = Path("/opt/noetic-dev-agent-review")
ROUTER_ROOT = RUNTIME_ROOT / "genus-router" / COMPONENT_SHA
ROUTER_COMMAND = ROUTER_ROOT / "bin" / "genus-router"
ROUTER_PYTHON = ROUTER_ROOT / "bin" / "python3"
ROUTER_CONFIG = ROUTER_ROOT / "config" / "router.yaml"
ROUTER_DECISIONS = ROUTER_ROOT / "state" / "decisions.jsonl"
ROUTER_OUTCOMES = ROUTER_ROOT / "state" / "outcomes.jsonl"
ROUTER_STATE_CLASSIFICATION = ROUTER_ROOT / "state" / "classification.json"
STATE_DIR = Path("/var/lib/noetic-opencode-spike/state")
EXECUTE_STATE_DIR = Path("/var/lib/noetic-opencode-spike/execute-state")
HANDOFF_STATE_DIR = Path("/var/lib/noetic-opencode-spike/handoff-state")
CONTROLLER_PATH = RUNTIME_ROOT / "opencode-spike-runtime" / "run_opencode_spike.py"
LITELLM_PEER_MANIFEST = RUNTIME_ROOT / "opencode-spike-runtime" / "litellm-peer-manifest.json"
OPENCODE_PATH = RUNTIME_ROOT / "opencode" / "1.17.20" / "opencode"
BWRAP_PATH = Path("/usr/bin/bwrap")
PYTHON_PATH = Path("/usr/bin/python3")
OPENCODE_VERSION = "1.17.20"
OPENCODE_SHA256 = "373af49ceba30c1b64e964463a64f8065103f942f240933a955f6c461e1a67f6"
LITELLM_HOST = "172.22.10.160"
LITELLM_PORT = 3333
LITELLM_BASE_URL = f"http://{LITELLM_HOST}:{LITELLM_PORT}"
LITELLM_PATH = "/v1/responses"
LITELLM_SERVICE_UNIT = Path("/etc/systemd/system/litellm.service")
LITELLM_LAUNCHER = Path("/opt/litellm/.venv/bin/litellm")
LITELLM_CONFIG = Path("/etc/litellm/config.yaml")
LITELLM_CGROUP = "/system.slice/litellm.service"
TOKEN_ENV = "LITELLM_API_KEY"
CREDENTIAL_NAME = "litellm_api_key"
PROTOCOL = "noetic-opencode-spike/1"
DUMMY_API_KEY = "noetic-dummy"
AGENT_NAME = "noetic-one-turn"
CLEAN_RESPONSE_ID = "resp_noetic_spike"
CLEAN_MESSAGE_ID = "msg_noetic_spike"
MAX_HEADER_BYTES = 16_384
MAX_CHILD_BODY_BYTES = 65_536
MAX_UPSTREAM_BODY_BYTES = 262_144
MAX_EVENT_LOG_BYTES = 65_536
MAX_STDERR_BYTES = 65_536
MAX_CONTROL_BYTES = 393_216
MAX_CREDENTIAL_BYTES = 16_384
MAX_ROUTER_LOG_BYTES = 67_108_864
CONTROL_TIMEOUT_SECONDS = 20.0
CHILD_INPUT_TIMEOUT_SECONDS = 5.0
UPSTREAM_TIMEOUT_SECONDS = 60.0
SANDBOX_TIMEOUT_SECONDS = 120.0
DECISION_ID = re.compile(r"^d-[0-9]{8}-[0-9]{6}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
SHA256_HEX = re.compile(r"^[a-f0-9]{64}$")
CAPABILITY = re.compile(r"^[a-f0-9]{64}$")
HEADER_NAME = re.compile(rb"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
NONCE = re.compile(r"^[a-f0-9]{32}$")
STANDARD_MODELS = [
    "codex/gpt-5.6-sol",
    "codex/gpt-5.6-terra",
    "codex/gpt-5.6-luna",
]
TRIVIAL_ROUTE_MODELS = [
    "codex/gpt-5.6-luna",
    "codex/gpt-5.6-terra",
    "codex/gpt-5.6-sol",
]
ROUTE_ARGUMENTS = {
    "task_kind": "test",
    "complexity": "trivial",
    "blast_radius": "isolated",
    "awaited": True,
    "high_value": False,
    "independent_approval": False,
    "prior_failure": False,
    "exclude_models": [],
    "task_summary": "OpenCode source-free one-turn non-evidence spike",
}
NON_EVIDENCE_ROUTER_STATE = {
    "evidence_class": "non-evidence",
    "policy_status": "contract-only",
    "runtime_adapter_ready": False,
    "schema_version": "1",
    "storage_scope": "isolated-spike-only",
}
DECISION_FIELDS = {
    "availability",
    "decision_id",
    "effective_complexity",
    "fable_eligible",
    "fallback_refs",
    "fallbacks",
    "genus",
    "genus_code",
    "independent_approval_eligible",
    "model",
    "model_ref",
    "rationale",
    "routing_profile",
    "sophistication",
}
MODEL_REF_FIELDS = {
    "model_id",
    "endpoint_id",
    "upstream_model_id",
    "interface_type",
    "base_url",
    "endpoint_path",
    "token_env",
    "reasoning_effort",
}
RESULT_FIELDS = {
    "schema_version",
    "evidence_class",
    "runtime_adapter_ready",
    "policy_status",
    "execution_status",
    "failure_code",
    "component_sha",
    "router_identity_sha256",
    "route_decision_id",
    "route_reference_sha256",
    "routed_model",
    "opencode_version",
    "opencode_sha256",
    "static_title",
    "title_sha256",
    "config_sha256",
    "json_event_log_sha256",
    "upstream_response_sha256",
    "litellm_peer_identity_sha256",
    "model_turn_count",
    "bridge_request_count",
    "upstream_request_count",
    "parsed_upstream_completion",
    "output_text",
    "nonce_sha256",
    "nonce_matched",
    "isolation",
    "claim_state",
    "request_issued",
    "outcome_status",
    "report_outcome_acknowledged",
    "report_outcome_acknowledgement_sha256",
    "report_outcome_record_sha256",
    "report_outcome_id",
}
ISOLATION_FIELDS = {
    "bwrap",
    "clear_environment",
    "credential_parent_only",
    "network_unshared",
    "user_namespace",
    "pid_namespace",
    "ipc_namespace",
    "uts_namespace",
    "nested_userns_disabled",
    "private_proc",
    "tmpfs_state",
    "host_source_mounted",
}
ALLOWED_SSE_EVENTS = {
    "response.created",
    "response.in_progress",
    "response.output_item.added",
    "response.content_part.added",
    "response.output_text.delta",
    "response.output_text.done",
    "response.content_part.done",
    "response.reasoning_summary_part.added",
    "response.reasoning_summary_text.delta",
    "response.reasoning_summary_text.done",
    "response.reasoning_summary_part.done",
    "response.output_item.done",
    "response.completed",
}
FORBIDDEN_EVENT_TYPES = {
    "response.failed",
    "response.incomplete",
    "response.error",
    "response.refusal.delta",
    "response.refusal.done",
    "response.function_call_arguments.delta",
    "response.function_call_arguments.done",
}
FORBIDDEN_ITEM_TYPES = {
    "function_call",
    "function_call_output",
    "computer_call",
    "web_search_call",
    "file_search_call",
    "image_generation_call",
    "refusal",
}


class SpikeError(RuntimeError):
    def __init__(self, code: str) -> None:
        if not re.fullmatch(r"[a-z0-9-]{1,80}", code):
            code = "internal-error"
        super().__init__(code)
        self.code = code


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SpikeError(code)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SpikeError("duplicate-json-key")
        result[key] = value
    return result


def strict_json_loads(raw: str | bytes) -> Any:
    def finite(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise SpikeError("non-finite-json-number")
        return parsed

    try:
        return json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_float=finite,
            parse_constant=lambda _value: (_ for _ in ()).throw(SpikeError("non-finite-json-number")),
        )
    except SpikeError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SpikeError("invalid-json") from error


def canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise SpikeError("unserializable-json") from error


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_all(descriptor: int, raw: bytes) -> None:
    offset = 0
    while offset < len(raw):
        written = os.write(descriptor, raw[offset:])
        if written <= 0:
            raise SpikeError("short-write")
        offset += written


def _open_private_directory(path: Path, *, create: bool = False) -> int:
    if create:
        try:
            os.mkdir(path, 0o700)
        except FileExistsError:
            pass
        except OSError as error:
            raise SpikeError("state-directory-unavailable") from error
    try:
        before = os.lstat(path)
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
        after = os.fstat(descriptor)
    except OSError as error:
        raise SpikeError("state-directory-unsafe") from error
    if (
        not stat.S_ISDIR(after.st_mode)
        or after.st_uid != os.getuid()
        or after.st_mode & 0o777 != 0o700
        or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
    ):
        os.close(descriptor)
        raise SpikeError("state-directory-unsafe")
    return descriptor


def atomic_create_bytes(path: Path, raw: bytes) -> None:
    require(path.name not in {"", ".", ".."}, "invalid-state-path")
    directory = _open_private_directory(path.parent, create=True)
    temporary = f".spike-{secrets.token_hex(16)}"
    descriptor: int | None = None
    linked = False
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory,
        )
        os.fchmod(descriptor, 0o600)
        _write_all(descriptor, raw)
        os.fsync(descriptor)
        try:
            os.link(
                temporary,
                path.name,
                src_dir_fd=directory,
                dst_dir_fd=directory,
                follow_symlinks=False,
            )
        except FileExistsError as error:
            raise SpikeError("state-already-exists") from error
        linked = True
        os.unlink(temporary, dir_fd=directory)
        temporary = ""
        published = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        opened = os.fstat(descriptor)
        require(
            stat.S_ISREG(published.st_mode)
            and published.st_uid == os.getuid()
            and published.st_mode & 0o777 == 0o600
            and published.st_nlink == 1
            and (published.st_dev, published.st_ino) == (opened.st_dev, opened.st_ino),
            "state-publication-unsafe",
        )
        os.fsync(directory)
    except SpikeError:
        if linked:
            try:
                os.unlink(path.name, dir_fd=directory)
            except OSError:
                pass
        raise
    except OSError as error:
        raise SpikeError("state-write-failed") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary:
            try:
                os.unlink(temporary, dir_fd=directory)
            except OSError:
                pass
        os.close(directory)


def atomic_create_json(path: Path, payload: Any) -> bytes:
    raw = canonical_json(payload) + b"\n"
    atomic_create_bytes(path, raw)
    return raw


def atomic_replace_json(path: Path, payload: Any) -> bytes:
    read_private_bytes(path, 262_144)
    directory = _open_private_directory(path.parent)
    temporary = f".spike-replace-{secrets.token_hex(16)}"
    descriptor: int | None = None
    raw = canonical_json(payload) + b"\n"
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory,
        )
        os.fchmod(descriptor, 0o600)
        _write_all(descriptor, raw)
        os.fsync(descriptor)
        os.replace(temporary, path.name, src_dir_fd=directory, dst_dir_fd=directory)
        temporary = ""
        os.fsync(directory)
    except OSError as error:
        raise SpikeError("state-replace-failed") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary:
            try:
                os.unlink(temporary, dir_fd=directory)
            except OSError:
                pass
        os.close(directory)
    return raw


def read_private_bytes(path: Path, maximum: int) -> bytes:
    directory = _open_private_directory(path.parent)
    descriptor: int | None = None
    try:
        descriptor = os.open(
            path.name,
            os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory,
        )
        metadata = os.fstat(descriptor)
        require(
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_uid == os.getuid()
            and metadata.st_mode & 0o777 == 0o600
            and metadata.st_nlink == 1
            and metadata.st_size <= maximum,
            "state-file-unsafe",
        )
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        require(len(raw) <= maximum, "state-file-oversized")
        current = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        require(
            current.st_nlink == 1
            and (current.st_dev, current.st_ino) == (metadata.st_dev, metadata.st_ino),
            "state-file-changed",
        )
        return raw
    except FileNotFoundError as error:
        raise SpikeError("state-file-missing") from error
    except SpikeError:
        raise
    except OSError as error:
        raise SpikeError("state-file-unreadable") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory)


def read_private_json(path: Path, maximum: int = 262_144) -> tuple[Any, bytes]:
    raw = read_private_bytes(path, maximum)
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, "state-json-framing-invalid")
    return strict_json_loads(raw[:-1]), raw


def create_claim(path: Path, decision_id: str, kind: str) -> None:
    payload = {"decision_id": decision_id, "kind": kind, "state": "claimed"}
    atomic_create_bytes(path, canonical_json(payload) + b"\n")


def claim_states(path: Path, kind: str, decision_id: str) -> list[str]:
    issued_state = {"execute": "request-issued", "outcome": "report-issued"}.get(kind)
    require(issued_state is not None, "claim-kind-invalid")
    raw = read_private_bytes(path, 8_192)
    require(raw.endswith(b"\n"), "claim-framing-invalid")
    records = [strict_json_loads(line) for line in raw.splitlines()]
    states: list[str] = []
    for record in records:
        require(
            type(record) is dict
            and set(record) == {"decision_id", "kind", "state"}
            and record["decision_id"] == decision_id
            and record["kind"] == kind
            and record["state"] in {"claimed", issued_state},
            "claim-invalid",
        )
        states.append(record["state"])
    require(states in (["claimed"], ["claimed", issued_state]), "claim-state-invalid")
    return states


def mark_claim_issued(path: Path, decision_id: str, kind: str) -> None:
    issued_state = {"execute": "request-issued", "outcome": "report-issued"}.get(kind)
    require(issued_state is not None and claim_states(path, kind, decision_id) == ["claimed"], "claim-state-invalid")
    directory = _open_private_directory(path.parent)
    descriptor: int | None = None
    try:
        descriptor = os.open(
            path.name,
            os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory,
        )
        metadata = os.fstat(descriptor)
        require(
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_uid == os.getuid()
            and metadata.st_mode & 0o777 == 0o600
            and metadata.st_nlink == 1,
            "claim-invalid",
        )
        record = {"decision_id": decision_id, "kind": kind, "state": issued_state}
        _write_all(descriptor, canonical_json(record) + b"\n")
        os.fsync(descriptor)
        os.fsync(directory)
    except SpikeError:
        raise
    except OSError as error:
        raise SpikeError("claim-update-failed") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory)


def fsync_router_log(path: Path) -> None:
    descriptor: int | None = None
    directory: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
        metadata = os.fstat(descriptor)
        require(
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_uid == os.getuid()
            and not metadata.st_mode & 0o022
            and metadata.st_nlink == 1
            and 0 < metadata.st_size <= MAX_ROUTER_LOG_BYTES,
            "router-log-unsafe",
        )
        os.fsync(descriptor)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
        os.fsync(directory)
    except SpikeError:
        raise
    except OSError as error:
        raise SpikeError("router-log-fsync-failed") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if directory is not None:
            os.close(directory)


def assert_no_credential_environment(environment: Mapping[str, str] | None = None) -> None:
    env = environment if environment is not None else os.environ
    for key in env:
        upper = key.upper()
        credential_like = upper == "CREDENTIALS_DIRECTORY" or upper in {
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
        } or upper.endswith(("_API_KEY", "_TOKEN", "_PASSWORD", "_SECRET", "_CREDENTIAL"))
        require(not credential_like, "credential-present-in-tokenless-phase")


def expected_model_ref(model: str) -> dict[str, str]:
    return {
        "model_id": model,
        "endpoint_id": "local-litellm",
        "upstream_model_id": model,
        "interface_type": "openai-compatible",
        "base_url": LITELLM_BASE_URL,
        "endpoint_path": LITELLM_PATH,
        "token_env": TOKEN_ENV,
        "reasoning_effort": "high",
    }


def _valid_bounded_text(value: Any, maximum: int) -> bool:
    return (
        type(value) is str
        and 1 <= len(value) <= maximum
        and value.isprintable()
        and "\n" not in value
        and "\r" not in value
    )


def validate_route_decision(decision: Any) -> dict[str, Any]:
    require(type(decision) is dict and set(decision) == DECISION_FIELDS, "route-decision-fields-invalid")
    require(type(decision["decision_id"]) is str and DECISION_ID.fullmatch(decision["decision_id"]) is not None, "route-decision-id-invalid")
    require(decision["genus_code"] == "TEST-GEN" and decision["genus"] == "Test Generation", "route-genus-invalid")
    require(decision["effective_complexity"] == "trivial" and decision["sophistication"] == "trivial", "route-sophistication-invalid")
    require(decision["routing_profile"] == "standard", "route-profile-invalid")
    require(decision["availability"] == "unverified", "route-availability-invalid")
    require(decision["fable_eligible"] is False and decision["independent_approval_eligible"] is False, "route-eligibility-invalid")
    require(type(decision["model"]) is str and decision["model"] == TRIVIAL_ROUTE_MODELS[0], "route-model-order-invalid")
    require(type(decision["fallbacks"]) is list and decision["fallbacks"] == TRIVIAL_ROUTE_MODELS[1:], "route-model-order-invalid")
    require(type(decision["model_ref"]) is dict and type(decision["fallback_refs"]) is list, "route-model-reference-invalid")
    references = [decision["model_ref"], *decision["fallback_refs"]]
    require(len(references) == len(TRIVIAL_ROUTE_MODELS), "route-reference-count-invalid")
    for model, reference in zip(TRIVIAL_ROUTE_MODELS, references, strict=True):
        require(type(reference) is dict and set(reference) == MODEL_REF_FIELDS, "route-model-reference-invalid")
        require(reference == expected_model_ref(model), "route-model-reference-invalid")
    rationale = decision["rationale"]
    require(type(rationale) is list and 1 <= len(rationale) <= 16, "route-rationale-invalid")
    require(all(_valid_bounded_text(item, 500) for item in rationale), "route-rationale-invalid")
    return decision


def validate_route_record(record: Any) -> dict[str, Any]:
    require(
        type(record) is dict
        and set(record) == {"schema_version", "component_sha", "router_identity_sha256", "router_state_classification_sha256", "classification", "decision"},
        "route-record-fields-invalid",
    )
    require(record["schema_version"] == "1" and record["component_sha"] == COMPONENT_SHA, "route-record-identity-invalid")
    require(type(record["router_identity_sha256"]) is str and SHA256_HEX.fullmatch(record["router_identity_sha256"]), "route-record-identity-invalid")
    require(type(record["router_state_classification_sha256"]) is str and SHA256_HEX.fullmatch(record["router_state_classification_sha256"]), "route-record-identity-invalid")
    require(record["classification"] == ROUTE_ARGUMENTS, "route-classification-invalid")
    validate_route_decision(record["decision"])
    return record


def _router_factory(command: Path, config: Path, component_sha: str, *, litellm_token: None) -> Any:
    script_dir = str(Path(__file__).resolve().parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from genus_router_mcp import GenusRouterMCP

    return GenusRouterMCP(command, config, component_sha, litellm_token=litellm_token)


def validate_router_arguments(command: Path, config: Path, component_sha: str) -> None:
    require(command == ROUTER_COMMAND, "router-command-not-canonical")
    require(config == ROUTER_CONFIG, "router-config-not-canonical")
    require(component_sha == COMPONENT_SHA, "router-component-not-canonical")


def _root_owned_file_bytes(path: Path, *, maximum: int, executable: bool = False) -> bytes:
    _validate_immutable_ancestors(path)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
        metadata = os.fstat(descriptor)
        require(
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_uid == 0
            and not metadata.st_mode & 0o022
            and metadata.st_nlink == 1,
            "root-identity-file-unsafe",
        )
        if executable:
            require(bool(metadata.st_mode & 0o111), "root-identity-file-not-executable")
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        require(len(raw) <= maximum, "root-identity-file-oversized")
        return raw
    except SpikeError:
        raise
    except OSError as error:
        raise SpikeError("root-identity-file-unavailable") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def validate_non_evidence_router_state(path: Path = ROUTER_STATE_CLASSIFICATION) -> str:
    raw = _root_owned_file_bytes(path, maximum=1_024)
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, "router-state-classification-invalid")
    require(strict_json_loads(raw[:-1]) == NON_EVIDENCE_ROUTER_STATE, "router-state-classification-invalid")
    return sha256(raw)


def read_root_json(path: Path) -> tuple[Any, bytes]:
    raw = _root_owned_file_bytes(path, maximum=262_144)
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, "handoff-json-framing-invalid")
    return strict_json_loads(raw[:-1]), raw


def _validate_root_owned_symlink(path: Path) -> Path:
    _validate_immutable_ancestors(path)
    try:
        metadata = os.lstat(path)
        target = os.readlink(path)
    except OSError as error:
        raise SpikeError("root-identity-link-unavailable") from error
    require(stat.S_ISLNK(metadata.st_mode) and metadata.st_uid == 0, "root-identity-link-unsafe")
    resolved = (path.parent / target).resolve(strict=True) if not os.path.isabs(target) else Path(target).resolve(strict=True)
    _validate_immutable_ancestors(resolved)
    return resolved


def validate_router_component_identity(
    command: Path = ROUTER_COMMAND,
    config: Path = ROUTER_CONFIG,
    component_sha: str = COMPONENT_SHA,
) -> str:
    validate_router_arguments(command, config, component_sha)
    manifest_path = ROUTER_ROOT / "component-manifest.json"
    table_path = config.parent / "genus_models.csv"
    manifest_raw = _root_owned_file_bytes(manifest_path, maximum=16_384)
    manifest = strict_json_loads(manifest_raw)
    require(
        type(manifest) is dict
        and set(manifest) == {"component_sha", "command_sha256", "config_sha256", "genus_table_sha256"}
        and manifest["component_sha"] == component_sha,
        "router-manifest-invalid",
    )
    command_raw = _root_owned_file_bytes(command, maximum=1_048_576, executable=True)
    config_raw = _root_owned_file_bytes(config, maximum=1_048_576)
    table_raw = _root_owned_file_bytes(table_path, maximum=1_048_576)
    require(
        manifest["command_sha256"] == sha256(command_raw)
        and manifest["config_sha256"] == sha256(config_raw)
        and manifest["genus_table_sha256"] == sha256(table_raw),
        "router-manifest-digest-mismatch",
    )
    interpreter = _validate_root_owned_symlink(ROUTER_PYTHON)
    interpreter_raw = _root_owned_file_bytes(interpreter, maximum=64 * 1024 * 1024, executable=True)
    identity = {
        "component_manifest_sha256": sha256(manifest_raw),
        "component_sha": component_sha,
        "interpreter_path": str(interpreter),
        "interpreter_sha256": sha256(interpreter_raw),
    }
    return sha256(canonical_json(identity))


def validate_pinned_route_policy(config: Path, *, expected_uid: int = 0) -> None:
    identity = open_immutable_identity(config, expected_uid=expected_uid, executable=False, maximum=1_048_576)
    try:
        os.lseek(identity.descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        remaining = 1_048_577
        while remaining:
            chunk = os.read(identity.descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        require(len(raw) <= 1_048_576, "router-policy-oversized")
    except OSError as error:
        raise SpikeError("router-policy-unreadable") from error
    finally:
        identity.close()
    matches = re.findall(rb'(?m)^[ \t]+trivial:[ \t]*(\[[^\r\n]+\])[ \t]*$', raw)
    require(len(matches) == 1, "router-policy-trivial-pool-invalid")
    models = strict_json_loads(matches[0])
    require(
        type(models) is list and all(type(model) is str for model in models),
        "router-policy-trivial-pool-invalid",
    )
    require(models == TRIVIAL_ROUTE_MODELS, "route-policy-order-conflict")


def route_phase(
    *,
    state_dir: Path = STATE_DIR,
    command: Path = ROUTER_COMMAND,
    config: Path = ROUTER_CONFIG,
    component_sha: str = COMPONENT_SHA,
    decisions_path: Path = ROUTER_DECISIONS,
    router_factory: Callable[..., Any] = _router_factory,
    policy_validator: Callable[[Path], None] = validate_pinned_route_policy,
    identity_validator: Callable[[Path, Path, str], str] = validate_router_component_identity,
    classification_validator: Callable[[Path], str] = validate_non_evidence_router_state,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    assert_no_credential_environment(environment)
    validate_router_arguments(command, config, component_sha)
    router_identity = identity_validator(command, config, component_sha)
    require(type(router_identity) is str and SHA256_HEX.fullmatch(router_identity), "router-identity-invalid")
    classification_sha = classification_validator(ROUTER_STATE_CLASSIFICATION)
    require(type(classification_sha) is str and SHA256_HEX.fullmatch(classification_sha), "router-state-classification-invalid")
    policy_validator(config)
    route_path = state_dir / "route.json"
    atomic_create_json(
        state_dir / "route.claim",
        {"component_sha": component_sha, "kind": "route", "state": "claimed"},
    )
    with router_factory(command, config, component_sha, litellm_token=None) as router:
        decision = router.call_tool("route_task", dict(ROUTE_ARGUMENTS))
    validate_route_decision(decision)
    fsync_router_log(decisions_path)
    record = {
        "schema_version": "1",
        "component_sha": component_sha,
        "router_identity_sha256": router_identity,
        "router_state_classification_sha256": classification_sha,
        "classification": dict(ROUTE_ARGUMENTS),
        "decision": decision,
    }
    atomic_create_json(route_path, record)
    return record


def read_systemd_credential(environment: Mapping[str, str] | None = None) -> bytearray:
    env = environment if environment is not None else os.environ
    require(TOKEN_ENV not in env, "ambient-token-forbidden")
    raw_directory = env.get("CREDENTIALS_DIRECTORY")
    require(type(raw_directory) is str and raw_directory.startswith("/") and "\x00" not in raw_directory, "credential-directory-invalid")
    directory: int | None = None
    descriptor: int | None = None
    try:
        directory = os.open(raw_directory, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
        descriptor = os.open(
            CREDENTIAL_NAME,
            os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory,
        )
        metadata = os.fstat(descriptor)
        require(
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_nlink == 1
            and not metadata.st_mode & 0o022
            and 0 < metadata.st_size <= MAX_CREDENTIAL_BYTES,
            "credential-file-unsafe",
        )
        chunks: list[bytes] = []
        remaining = MAX_CREDENTIAL_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(4_096, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
    except SpikeError:
        raise
    except OSError as error:
        raise SpikeError("credential-unavailable") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if directory is not None:
            os.close(directory)
    require(0 < len(raw) <= MAX_CREDENTIAL_BYTES, "credential-size-invalid")
    require(all(byte >= 0x20 and byte != 0x7F for byte in raw), "credential-control-character")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise SpikeError("credential-not-utf8") from error
    require(text.encode("utf-8") == raw, "credential-not-canonical-utf8")
    return bytearray(raw)


@dataclass
class OpenedIdentity:
    path: Path
    descriptor: int
    sha256: str
    version: str | None

    def close(self) -> None:
        os.close(self.descriptor)


def _hash_descriptor(descriptor: int, maximum: int) -> str:
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    total = 0
    while True:
        chunk = os.read(descriptor, 65_536)
        if not chunk:
            break
        total += len(chunk)
        require(total <= maximum, "identity-file-oversized")
        digest.update(chunk)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return digest.hexdigest()


def open_immutable_identity(
    path: Path,
    *,
    expected_uid: int = 0,
    executable: bool,
    maximum: int,
) -> OpenedIdentity:
    if expected_uid == 0:
        _validate_immutable_ancestors(path)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
        metadata = os.fstat(descriptor)
    except OSError as error:
        raise SpikeError("identity-file-unavailable") from error
    try:
        require(
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_uid == expected_uid
            and not metadata.st_mode & 0o222
            and metadata.st_nlink == 1,
            "identity-file-unsafe",
        )
        if executable:
            require(bool(metadata.st_mode & 0o111), "identity-file-not-executable")
        digest = _hash_descriptor(descriptor, maximum)
        return OpenedIdentity(path=path, descriptor=descriptor, sha256=digest, version=None)
    except BaseException:
        os.close(descriptor)
        raise


def _validate_immutable_ancestors(path: Path) -> None:
    require(path.is_absolute() and path == Path(os.path.normpath(path)), "identity-path-invalid")
    current = Path(path.anchor)
    for part in path.parts[1:-1]:
        current /= part
        try:
            metadata = os.lstat(current)
        except OSError as error:
            raise SpikeError("identity-ancestor-unavailable") from error
        require(
            stat.S_ISDIR(metadata.st_mode)
            and metadata.st_uid == 0
            and not metadata.st_mode & 0o022,
            "identity-ancestor-unsafe",
        )


def verify_opencode_identity(
    path: Path = OPENCODE_PATH,
    *,
    expected_uid: int = 0,
    version_runner: Callable[[int], tuple[int, bytes, bytes]] | None = None,
) -> OpenedIdentity:
    require(path == OPENCODE_PATH or expected_uid != 0, "opencode-path-not-canonical")
    identity = open_immutable_identity(path, expected_uid=expected_uid, executable=True, maximum=268_435_456)
    try:
        require(identity.sha256 == OPENCODE_SHA256, "opencode-sha256-mismatch")
        if version_runner is None:
            def version_runner(descriptor: int) -> tuple[int, bytes, bytes]:
                try:
                    with tempfile.TemporaryDirectory(prefix="noetic-opencode-version-", dir="/tmp") as home:
                        completed = subprocess.run(
                            [f"/proc/self/fd/{descriptor}", "--version"],
                            env={
                                "HOME": home,
                                "PATH": "/usr/bin:/bin",
                                "XDG_CONFIG_HOME": f"{home}/config",
                                "XDG_DATA_HOME": f"{home}/data",
                                "XDG_CACHE_HOME": f"{home}/cache",
                                "XDG_STATE_HOME": f"{home}/state",
                            },
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            pass_fds=(descriptor,),
                            timeout=10,
                            check=False,
                        )
                except (OSError, subprocess.TimeoutExpired) as error:
                    raise SpikeError("opencode-version-check-failed") from error
                return completed.returncode, completed.stdout, completed.stderr
        returncode, stdout, stderr = version_runner(identity.descriptor)
        require(
            returncode == 0
            and stdout == (OPENCODE_VERSION + "\n").encode("ascii")
            and stderr == b"",
            "opencode-version-mismatch",
        )
        identity.version = OPENCODE_VERSION
        return identity
    except BaseException:
        identity.close()
        raise


def build_opencode_config(model: str, relay_port: int) -> dict[str, Any]:
    require(model in STANDARD_MODELS, "config-model-invalid")
    require(type(relay_port) is int and 1_024 <= relay_port <= 65_535, "relay-port-invalid")
    model_name = f"litellm/{model}"
    return {
        "$schema": "https://opencode.ai/config.json",
        "share": "disabled",
        "autoupdate": False,
        "snapshot": False,
        "enabled_providers": ["litellm"],
        "provider": {
            "litellm": {
                "npm": "@ai-sdk/openai",
                "name": "Noetic one-turn relay",
                "options": {
                    "baseURL": f"http://127.0.0.1:{relay_port}/v1",
                    "apiKey": DUMMY_API_KEY,
                    "setCacheKey": False,
                    "timeout": 60_000,
                    "headerTimeout": 5_000,
                    "chunkTimeout": 5_000,
                },
                "models": {
                    model: {
                        "id": model,
                        "name": model,
                        "attachment": False,
                        "reasoning": True,
                        "temperature": False,
                        "tool_call": False,
                        "limit": {"context": 128_000, "output": 1_024},
                        "variants": {
                            "high": {
                                "reasoningEffort": "high",
                                "reasoningSummary": "auto",
                                "include": ["reasoning.encrypted_content"],
                                "store": False,
                            }
                        },
                    }
                },
            }
        },
        "model": model_name,
        "small_model": model_name,
        "default_agent": AGENT_NAME,
        "agent": {
            AGENT_NAME: {
                "description": "Bounded source-free one-turn responder",
                "mode": "primary",
                "model": model_name,
                "variant": "high",
                "prompt": "Return only the exact text requested by the user. Never call a tool.",
                "steps": 2,
                "tools": {"*": False},
                "permission": "deny",
            },
            "title": {"disable": True},
            "summary": {"disable": True},
            "compaction": {"disable": True},
        },
        "permission": "deny",
        "tools": {"*": False},
        "mcp": {},
        "plugin": [],
        "skills": {"paths": [], "urls": []},
        "instructions": [],
        "formatter": False,
        "lsp": False,
        "compaction": {"auto": False, "prune": False},
        "experimental": {"openTelemetry": False},
    }


def build_opencode_command(model: str, title: str, prompt: str) -> list[str]:
    require(model in STANDARD_MODELS, "command-model-invalid")
    require(type(title) is str and re.fullmatch(r"noetic-d-[0-9]{8}-[0-9]{6}", title) is not None, "command-title-invalid")
    require(type(prompt) is str and re.fullmatch(r"Respond with exactly READY [a-f0-9]{32} and nothing else\.", prompt) is not None, "command-prompt-invalid")
    return [
        "/runtime/opencode",
        "--pure",
        "run",
        "--dir",
        "/work",
        "--agent",
        AGENT_NAME,
        "--model",
        f"litellm/{model}",
        "--variant",
        "high",
        "--format",
        "json",
        "--title",
        title,
        prompt,
    ]


def build_bwrap_command(
    *,
    opencode_fd: int,
    controller_fd: int,
    control_directory: Path,
    relay_port: int,
    config: dict[str, Any],
    model: str,
    title: str,
    prompt: str,
    library_paths: Sequence[Path] | None = None,
) -> list[str]:
    require(control_directory.is_absolute(), "control-directory-invalid")
    libraries = list(library_paths) if library_paths is not None else [Path("/lib"), Path("/lib64")]
    command = [
        str(BWRAP_PATH),
        "--unshare-user",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--unshare-net",
        "--disable-userns",
        "--assert-userns-disabled",
        "--die-with-parent",
        "--new-session",
        "--cap-drop",
        "ALL",
        "--clearenv",
        "--hostname",
        "noetic-opencode",
        "--uid",
        "0",
        "--gid",
        "0",
        "--dir",
        "/usr",
        "--ro-bind",
        "/usr",
        "/usr",
    ]
    for library in libraries:
        if library.exists():
            command.extend(["--dir", str(library), "--ro-bind", str(library), str(library)])
    command.extend(
        [
            "--dir",
            "/proc",
            "--proc",
            "/proc",
            "--dir",
            "/dev",
            "--dev",
            "/dev",
            "--dir",
            "/tmp",
            "--tmpfs",
            "/tmp",
            "--dir",
            "/home",
            "--tmpfs",
            "/home",
            "--dir",
            "/home/opencode",
            "--dir",
            "/xdg",
            "--tmpfs",
            "/xdg",
            "--dir",
            "/xdg/config",
            "--dir",
            "/xdg/data",
            "--dir",
            "/xdg/cache",
            "--dir",
            "/xdg/state",
            "--dir",
            "/work",
            "--tmpfs",
            "/work",
            "--dir",
            "/runtime",
            "--ro-bind-fd",
            str(opencode_fd),
            "/runtime/opencode",
            "--ro-bind-fd",
            str(controller_fd),
            "/runtime/run_opencode_spike.py",
            "--dir",
            "/parent-bridge",
            "--ro-bind",
            str(control_directory),
            "/parent-bridge",
        ]
    )
    environment = {
        "HOME": "/home/opencode",
        "XDG_CONFIG_HOME": "/xdg/config",
        "XDG_DATA_HOME": "/xdg/data",
        "XDG_CACHE_HOME": "/xdg/cache",
        "XDG_STATE_HOME": "/xdg/state",
        "TMPDIR": "/tmp",
        "PATH": "/usr/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PWD": "/work",
        "OPENCODE_DB": ":memory:",
        "OPENCODE_AUTH_CONTENT": "{}",
        "OPENCODE_CONFIG_CONTENT": canonical_json(config).decode("ascii"),
        "OPENCODE_CONFIG_DIR": "/xdg/config/opencode",
        "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
        "OPENCODE_DISABLE_DEFAULT_PLUGINS": "1",
        "OPENCODE_DISABLE_CLAUDE_CODE": "1",
        "OPENCODE_DISABLE_CLAUDE_CODE_PROMPT": "1",
        "OPENCODE_DISABLE_CLAUDE_CODE_SKILLS": "1",
        "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
        "OPENCODE_DISABLE_AUTOUPDATE": "1",
        "OPENCODE_DISABLE_MODELS_FETCH": "1",
        "OPENCODE_DISABLE_AUTOCOMPACT": "1",
        "OPENCODE_DISABLE_PRUNE": "1",
        "OPENCODE_DISABLE_LSP_DOWNLOAD": "1",
        "OPENCODE_PURE": "1",
        "OPENCODE_TEST_MANAGED_CONFIG_DIR": "/no-managed-config",
    }
    for key, value in environment.items():
        command.extend(["--setenv", key, value])
    command.extend(
        [
            "--chdir",
            "/work",
            "--",
            str(PYTHON_PATH),
            "/runtime/run_opencode_spike.py",
            "sandbox-relay",
            "--control-socket",
            "/parent-bridge/control.sock",
            "--relay-port",
            str(relay_port),
            "--model",
            model,
            "--title",
            title,
            "--prompt",
            prompt,
        ]
    )
    return command


def _text_from_input_content(content: Any) -> str:
    if type(content) is str:
        return content
    require(type(content) is list and len(content) == 1, "child-input-content-invalid")
    part = content[0]
    require(type(part) is dict and set(part) == {"type", "text"} and part["type"] == "input_text" and type(part["text"]) is str, "child-input-content-invalid")
    return part["text"]


def validate_child_system_prompt(system_text: str, expected_model: str) -> None:
    lines = system_text.splitlines()
    custom_prompt = "Return only the exact text requested by the user. Never call a tool."
    require(len(lines) == 10 and lines[0] == custom_prompt, "child-system-source-detected")
    tail = lines[-9:]
    require(
        len(system_text.encode("utf-8")) <= 32_768
        and system_text.count(custom_prompt) == 1
        and tail[:7]
        == [
            f"You are powered by the model named {expected_model}. The exact model ID is litellm/{expected_model}",
            "Here is some useful information about the environment you are running in:",
            "<env>",
            "  Working directory: /work",
            "  Workspace root folder: /",
            "  Is directory a git repo: no",
            "  Platform: linux",
        ]
        and re.fullmatch(
            r"  Today's date: (Mon|Tue|Wed|Thu|Fri|Sat|Sun) "
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) [ 0-3][0-9] [0-9]{4}",
            tail[7],
        )
        is not None
        and tail[8] == "</env>",
        "child-system-source-detected",
    )
    for marker in ("\nInstructions from:", "/home/dgk/", "synthesis-worktrees", "initial-user-msg.md"):
        require(marker not in system_text, "child-system-source-detected")


def validate_child_request_body(payload: Any, expected_model: str, expected_prompt: str) -> dict[str, Any]:
    require(type(payload) is dict, "child-body-not-object")
    required = {"model", "input", "stream", "store", "include", "reasoning", "max_output_tokens"}
    require(set(payload) == required, "child-body-fields-invalid")
    require(type(payload["model"]) is str and payload["model"] == expected_model, "child-model-mismatch")
    require(payload["stream"] is True and payload["store"] is False, "child-stream-contract-invalid")
    require(type(payload["include"]) is list and payload["include"] == ["reasoning.encrypted_content"], "child-include-invalid")
    require(type(payload["reasoning"]) is dict and payload["reasoning"] == {"effort": "high", "summary": "auto"}, "child-reasoning-invalid")
    require(type(payload["max_output_tokens"]) is int and payload["max_output_tokens"] == 1_024, "child-output-limit-invalid")
    items = payload["input"]
    require(type(items) is list and len(items) == 2, "child-input-count-invalid")
    system_item, user_item = items
    require(type(system_item) is dict and set(system_item) == {"role", "content"}, "child-system-invalid")
    require(system_item["role"] in {"system", "developer"}, "child-system-invalid")
    system_text = _text_from_input_content(system_item["content"])
    require(1 <= len(system_text.encode("utf-8")) <= 32_768, "child-system-invalid")
    validate_child_system_prompt(system_text, expected_model)
    require(type(user_item) is dict and set(user_item) == {"role", "content"} and user_item["role"] == "user", "child-user-invalid")
    require(_text_from_input_content(user_item["content"]) == json.dumps(expected_prompt), "child-user-prompt-mismatch")
    raw = canonical_json(payload)
    require(b"CRITICAL - MAXIMUM STEPS REACHED" not in raw, "max-steps-prompt-detected")
    for marker in (b'"type":"input_file"', b'"type":"input_image"', b'"type":"file"', b'"tools"'):
        require(marker not in raw, "child-source-or-tool-detected")
    return payload


def canonical_upstream_request(model: str, prompt: str) -> bytes:
    require(type(model) is str and model in STANDARD_MODELS, "upstream-model-invalid")
    require(
        type(prompt) is str
        and re.fullmatch(r"Respond with exactly READY [a-f0-9]{32} and nothing else\.", prompt) is not None,
        "upstream-prompt-invalid",
    )
    payload = {
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "max_output_tokens": 1_024,
        "model": model,
        "reasoning": {"effort": "high"},
        "store": False,
        "stream": True,
    }
    return canonical_json(payload)


def validate_upstream_request_body(body: bytes) -> dict[str, Any]:
    payload = strict_json_loads(body)
    require(type(payload) is dict, "upstream-request-invalid")
    require(
        set(payload) == {"input", "max_output_tokens", "model", "reasoning", "store", "stream"}
        and type(payload.get("model")) is str
        and payload["model"] in STANDARD_MODELS
        and type(payload["max_output_tokens"]) is int
        and payload["max_output_tokens"] == 1_024
        and type(payload["reasoning"]) is dict
        and payload["reasoning"] == {"effort": "high"}
        and payload["store"] is False
        and payload["stream"] is True,
        "upstream-request-invalid",
    )
    items = payload["input"]
    require(type(items) is list and len(items) == 1 and type(items[0]) is dict, "upstream-request-invalid")
    item = items[0]
    require(set(item) == {"role", "content"} and item["role"] == "user", "upstream-request-invalid")
    content = item["content"]
    require(type(content) is list and len(content) == 1 and type(content[0]) is dict, "upstream-request-invalid")
    part = content[0]
    require(set(part) == {"type", "text"} and part["type"] == "input_text" and type(part["text"]) is str, "upstream-request-invalid")
    require(body == canonical_upstream_request(payload["model"], part["text"]), "upstream-request-not-canonical")
    return payload


@dataclass(frozen=True)
class ParsedHTTPRequest:
    headers: dict[str, str]
    body: bytes
    payload: dict[str, Any]


def _read_socket_until(sock: socket.socket, marker: bytes, maximum: int, deadline: float) -> bytes:
    data = bytearray()
    while marker not in data:
        require(len(data) < maximum, "http-header-oversized")
        remaining = deadline - time.monotonic()
        require(remaining > 0, "http-input-timeout")
        sock.settimeout(min(remaining, 0.5))
        try:
            chunk = sock.recv(min(4_096, maximum + 1 - len(data)))
        except socket.timeout:
            continue
        except OSError as error:
            raise SpikeError("http-input-read-failed") from error
        require(bool(chunk), "http-input-truncated")
        data.extend(chunk)
    return bytes(data)


def read_child_http_request(
    sock: socket.socket,
    *,
    expected_host: str,
    expected_model: str,
    expected_prompt: str,
) -> ParsedHTTPRequest:
    deadline = time.monotonic() + CHILD_INPUT_TIMEOUT_SECONDS
    received = _read_socket_until(sock, b"\r\n\r\n", MAX_HEADER_BYTES, deadline)
    header_raw, body = received.split(b"\r\n\r\n", 1)
    require(b"\n" not in header_raw.replace(b"\r\n", b""), "http-line-framing-invalid")
    lines = header_raw.split(b"\r\n")
    require(lines and lines[0] == b"POST /v1/responses HTTP/1.1", "http-request-target-invalid")
    headers: dict[str, str] = {}
    counts: dict[str, int] = {}
    for line in lines[1:]:
        require(line and not line.startswith((b" ", b"\t")) and b":" in line, "http-header-invalid")
        name_raw, value_raw = line.split(b":", 1)
        require(HEADER_NAME.fullmatch(name_raw) is not None, "http-header-name-invalid")
        require(all(byte >= 0x20 and byte != 0x7F for byte in value_raw), "http-header-value-invalid")
        try:
            name = name_raw.decode("ascii").lower()
            value = value_raw.decode("ascii").strip(" \t")
        except UnicodeDecodeError as error:
            raise SpikeError("http-header-not-ascii") from error
        counts[name] = counts.get(name, 0) + 1
        require(counts[name] == 1, "http-duplicate-header")
        headers[name] = value
    require(counts.get("content-length") == 1, "http-content-length-missing")
    require(re.fullmatch(r"[0-9]+", headers["content-length"]) is not None, "http-content-length-invalid")
    length = int(headers["content-length"])
    require(0 < length <= MAX_CHILD_BODY_BYTES, "http-body-size-invalid")
    for forbidden in ("transfer-encoding", "upgrade", "trailer", "expect"):
        require(forbidden not in headers, "http-forbidden-framing-header")
    require("upgrade" not in headers.get("connection", "").lower(), "http-upgrade-forbidden")
    require(headers.get("host") == expected_host, "http-host-invalid")
    require(headers.get("content-type") == "application/json", "http-content-type-invalid")
    require(headers.get("authorization") == f"Bearer {DUMMY_API_KEY}", "http-child-authorization-invalid")
    while len(body) < length:
        remaining = deadline - time.monotonic()
        require(remaining > 0, "http-input-timeout")
        sock.settimeout(min(remaining, 0.5))
        try:
            chunk = sock.recv(min(4_096, length - len(body)))
        except socket.timeout:
            continue
        except OSError as error:
            raise SpikeError("http-input-read-failed") from error
        require(bool(chunk), "http-body-truncated")
        body += chunk
    require(len(body) == length, "http-pipelined-bytes")
    payload = strict_json_loads(body)
    validate_child_request_body(payload, expected_model, expected_prompt)
    return ParsedHTTPRequest(headers=headers, body=body, payload=payload)


class OneRequestGate:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.count = 0

    def claim(self) -> None:
        with self._lock:
            require(self.count == 0, "second-relay-request")
            self.count = 1


@dataclass(frozen=True)
class UpstreamHTTPResponse:
    status: int
    headers: list[tuple[str, str]]
    body: bytes
    peer_identity_sha256: str | None = None


@dataclass(frozen=True)
class ValidatedUpstream:
    text: str
    clean_body: bytes
    upstream_sha256: str


def _safe_event_id(value: Any) -> str:
    require(type(value) is str and SAFE_ID.fullmatch(value) is not None, "sse-identifier-invalid")
    return value


def _reject_dangerous_response_value(value: Any) -> None:
    if type(value) is dict:
        for key, item in value.items():
            lower = key.lower()
            require(lower not in {"refusal", "tool_calls", "function_call", "function_calls"}, "sse-tool-or-refusal")
            if lower == "type" and type(item) is str:
                require(item not in FORBIDDEN_ITEM_TYPES and not item.startswith("response.refusal"), "sse-tool-or-refusal")
            _reject_dangerous_response_value(item)
    elif type(value) is list:
        for item in value:
            _reject_dangerous_response_value(item)


def _validate_response_identity(response: Any, expected_model: str, response_id: str | None, status: str) -> str:
    require(type(response) is dict, "sse-response-invalid")
    identity = _safe_event_id(response.get("id"))
    if response_id is not None:
        require(identity == response_id, "sse-response-id-mismatch")
    require(response.get("model") == expected_model, "sse-model-mismatch")
    require(response.get("status") == status, "sse-response-status-invalid")
    return identity


def _validate_completed_message(item: Any, message_id: str, expected_text: str) -> None:
    require(type(item) is dict, "sse-message-invalid")
    require(item.get("type") == "message" and item.get("id") == message_id, "sse-message-invalid")
    require(item.get("role") == "assistant" and item.get("status") == "completed", "sse-message-invalid")
    content = item.get("content")
    require(type(content) is list and len(content) == 1 and type(content[0]) is dict, "sse-final-text-count-invalid")
    part = content[0]
    require(part.get("type") == "output_text" and part.get("text") == expected_text, "sse-final-text-invalid")
    require(not any(key in part for key in ("refusal", "tool_call", "function_call")), "sse-tool-or-refusal")


def parse_upstream_sse(raw: bytes, expected_model: str, expected_text: str) -> str:
    require(0 < len(raw) <= MAX_UPSTREAM_BODY_BYTES, "sse-size-invalid")
    require(b"\r" not in raw and b"\x00" not in raw and raw.endswith(b"\n\n"), "sse-framing-invalid")
    blocks = raw[:-2].split(b"\n\n")
    require(blocks and all(block for block in blocks), "sse-framing-invalid")
    events: list[dict[str, Any]] = []
    done_count = 0
    for index, block in enumerate(blocks):
        require(b"\n" not in block and block.startswith(b"data: "), "sse-data-line-invalid")
        data = block[6:]
        if data == b"[DONE]":
            done_count += 1
            require(index == len(blocks) - 1, "sse-done-order-invalid")
            continue
        require(done_count == 0, "sse-event-after-done")
        event = strict_json_loads(data)
        require(type(event) is dict and type(event.get("type")) is str, "sse-event-invalid")
        require(event["type"] in ALLOWED_SSE_EVENTS and event["type"] not in FORBIDDEN_EVENT_TYPES, "sse-event-type-invalid")
        _reject_dangerous_response_value(event)
        events.append(event)
    require(done_count == 1 and events, "sse-done-invalid")
    require(events[0]["type"] == "response.created" and events[-1]["type"] == "response.completed", "sse-order-invalid")
    sequence: int | None = None
    response_id: str | None = None
    in_progress = False
    message_id: str | None = None
    content_added = False
    text_done = False
    content_done = False
    message_done = False
    completed = False
    deltas: list[str] = []
    reasoning_ids: set[str] = set()
    reasoning_done: set[str] = set()
    reasoning_state: dict[str, dict[str, Any]] = {}
    for event in events:
        number = event.get("sequence_number")
        require(type(number) is int and not isinstance(number, bool) and number >= 0, "sse-sequence-invalid")
        if sequence is not None:
            require(number == sequence + 1, "sse-sequence-invalid")
        sequence = number
        kind = event["type"]
        require(not completed or kind == "response.completed", "sse-event-after-completion")
        if kind == "response.created":
            require(response_id is None, "sse-created-duplicate")
            response_id = _validate_response_identity(event.get("response"), expected_model, None, "in_progress")
            continue
        require(response_id is not None, "sse-created-missing")
        if kind == "response.in_progress":
            require(not in_progress and message_id is None, "sse-in-progress-order-invalid")
            _validate_response_identity(event.get("response"), expected_model, response_id, "in_progress")
            in_progress = True
            continue
        require(in_progress, "sse-in-progress-missing")
        if kind == "response.output_item.added":
            item = event.get("item")
            require(type(item) is dict, "sse-output-item-invalid")
            item_type = item.get("type")
            if item_type == "reasoning":
                identity = _safe_event_id(item.get("id"))
                require(identity not in reasoning_ids and message_id is None, "sse-reasoning-order-invalid")
                reasoning_ids.add(identity)
                reasoning_state[identity] = {
                    "part_added": False,
                    "text_done": False,
                    "part_done": False,
                    "deltas": [],
                }
                continue
            require(item_type == "message" and message_id is None, "sse-final-text-count-invalid")
            message_id = _safe_event_id(item.get("id"))
            require(item.get("role") == "assistant" and item.get("status") == "in_progress", "sse-message-invalid")
            require(item.get("content") in (None, []), "sse-message-invalid")
            continue
        if kind.startswith("response.reasoning_summary_"):
            identity = event.get("item_id")
            require(identity in reasoning_ids and identity not in reasoning_done and message_id is None, "sse-reasoning-order-invalid")
            state = reasoning_state[identity]
            require(event.get("summary_index") == 0, "sse-reasoning-invalid")
            if kind == "response.reasoning_summary_part.added":
                require(not state["part_added"], "sse-reasoning-order-invalid")
                part = event.get("part")
                require(
                    part is None
                    or (type(part) is dict and part.get("type") == "summary_text" and part.get("text") in (None, "")),
                    "sse-reasoning-invalid",
                )
                state["part_added"] = True
                continue
            if kind == "response.reasoning_summary_text.delta":
                delta = event.get("delta")
                require(state["part_added"] and not state["text_done"] and type(delta) is str and delta != "", "sse-reasoning-order-invalid")
                state["deltas"].append(delta)
                require(len("".join(state["deltas"]).encode("utf-8")) <= 32_768, "sse-reasoning-invalid")
                continue
            if kind == "response.reasoning_summary_text.done":
                require(
                    state["part_added"]
                    and not state["text_done"]
                    and event.get("text") == "".join(state["deltas"]),
                    "sse-reasoning-order-invalid",
                )
                state["text_done"] = True
                continue
            require(kind == "response.reasoning_summary_part.done", "sse-reasoning-order-invalid")
            require(state["text_done"] and not state["part_done"], "sse-reasoning-order-invalid")
            part = event.get("part")
            require(
                part is None
                or (
                    type(part) is dict
                    and part.get("type") == "summary_text"
                    and part.get("text") == "".join(state["deltas"])
                ),
                "sse-reasoning-invalid",
            )
            state["part_done"] = True
            continue
        if kind == "response.content_part.added":
            require(message_id is not None and not content_added and not text_done, "sse-content-order-invalid")
            require(event.get("item_id") == message_id, "sse-message-id-mismatch")
            part = event.get("part")
            require(type(part) is dict and part.get("type") == "output_text" and part.get("text") in (None, ""), "sse-content-part-invalid")
            content_added = True
            continue
        if kind == "response.output_text.delta":
            require(content_added and not text_done and event.get("item_id") == message_id, "sse-text-order-invalid")
            delta = event.get("delta")
            require(type(delta) is str and delta != "", "sse-text-delta-invalid")
            deltas.append(delta)
            require(len("".join(deltas).encode("utf-8")) <= 4_096, "sse-text-oversized")
            continue
        if kind == "response.output_text.done":
            require(content_added and not text_done and event.get("item_id") == message_id, "sse-text-order-invalid")
            require(event.get("text") == "".join(deltas) == expected_text, "sse-final-text-invalid")
            text_done = True
            continue
        if kind == "response.content_part.done":
            require(text_done and not content_done and event.get("item_id") == message_id, "sse-content-order-invalid")
            part = event.get("part")
            require(type(part) is dict and part.get("type") == "output_text" and part.get("text") == expected_text, "sse-content-part-invalid")
            content_done = True
            continue
        if kind == "response.output_item.done":
            item = event.get("item")
            require(type(item) is dict, "sse-output-item-invalid")
            if item.get("type") == "reasoning":
                identity = item.get("id")
                require(identity in reasoning_ids and identity not in reasoning_done and message_id is None, "sse-reasoning-order-invalid")
                state = reasoning_state[identity]
                require(not state["part_added"] or state["part_done"], "sse-reasoning-order-invalid")
                reasoning_done.add(identity)
                continue
            require(text_done and content_done and not message_done and message_id is not None, "sse-message-order-invalid")
            _validate_completed_message(item, message_id, expected_text)
            message_done = True
            continue
        if kind == "response.completed":
            require(message_done and not completed and reasoning_ids == reasoning_done, "sse-completion-order-invalid")
            response = event.get("response")
            _validate_response_identity(response, expected_model, response_id, "completed")
            output = response.get("output")
            require(type(output) is list and 1 <= len(output) <= 8, "sse-completed-output-invalid")
            messages = [item for item in output if type(item) is dict and item.get("type") == "message"]
            require(len(messages) == 1, "sse-final-text-count-invalid")
            completed_reasoning: set[str] = set()
            for item in output:
                require(type(item) is dict and item.get("type") in {"reasoning", "message"}, "sse-tool-or-refusal")
                if item.get("type") == "reasoning":
                    completed_reasoning.add(_safe_event_id(item.get("id")))
            require(
                completed_reasoning == reasoning_ids
                and len(completed_reasoning) == len(output) - 1
                and output[-1] is messages[0],
                "sse-completed-output-invalid",
            )
            _validate_completed_message(messages[0], message_id, expected_text)
            completed = True
            continue
        raise SpikeError("sse-event-unhandled")
    require(completed and "".join(deltas) == expected_text, "sse-completion-missing")
    return expected_text


def synthesize_clean_sse(model: str, text: str) -> bytes:
    response_id = CLEAN_RESPONSE_ID
    message_id = CLEAN_MESSAGE_ID
    base = {
        "id": response_id,
        "object": "response",
        "created_at": 1,
        "status": "in_progress",
        "model": model,
        "output": [],
        "service_tier": "default",
        "usage": None,
    }
    item = {
        "id": message_id,
        "type": "message",
        "status": "completed",
        "role": "assistant",
        "content": [{"type": "output_text", "annotations": [], "text": text}],
    }
    completed = {
        **base,
        "status": "completed",
        "output": [item],
        "usage": {
            "input_tokens": 1,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 1,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 2,
        },
    }
    events = [
        {"type": "response.created", "response": base, "sequence_number": 0},
        {"type": "response.in_progress", "response": base, "sequence_number": 1},
        {
            "type": "response.output_item.added",
            "item": {**item, "status": "in_progress", "content": []},
            "output_index": 0,
            "sequence_number": 2,
        },
        {
            "type": "response.content_part.added",
            "content_index": 0,
            "item_id": message_id,
            "output_index": 0,
            "part": {"type": "output_text", "annotations": [], "text": ""},
            "sequence_number": 3,
        },
        {
            "type": "response.output_text.delta",
            "content_index": 0,
            "delta": text,
            "item_id": message_id,
            "output_index": 0,
            "sequence_number": 4,
        },
        {
            "type": "response.output_text.done",
            "content_index": 0,
            "item_id": message_id,
            "output_index": 0,
            "text": text,
            "sequence_number": 5,
        },
        {
            "type": "response.content_part.done",
            "content_index": 0,
            "item_id": message_id,
            "output_index": 0,
            "part": {"type": "output_text", "annotations": [], "text": text},
            "sequence_number": 6,
        },
        {"type": "response.output_item.done", "item": item, "output_index": 0, "sequence_number": 7},
        {"type": "response.completed", "response": completed, "sequence_number": 8},
    ]
    return b"".join(b"data: " + canonical_json(event) + b"\n\n" for event in events) + b"data: [DONE]\n\n"


def validate_upstream_response(
    response: UpstreamHTTPResponse,
    *,
    token: bytes,
    expected_model: str,
    expected_text: str,
) -> ValidatedUpstream:
    require(type(response.status) is int and response.status == 200, "upstream-status-invalid")
    require(0 < len(response.headers) <= 100, "upstream-headers-invalid")
    content_types: list[str] = []
    total = 0
    for name, value in response.headers:
        require(type(name) is str and type(value) is str, "upstream-header-invalid")
        encoded = (name + ":" + value).encode("utf-8", errors="strict")
        total += len(encoded)
        require(total <= MAX_HEADER_BYTES and token not in encoded, "upstream-header-invalid")
        require(all(ord(char) >= 0x20 and ord(char) != 0x7F for char in name + value), "upstream-header-invalid")
        if name.lower() == "content-type":
            content_types.append(value.strip().lower())
        require(name.lower() != "content-encoding", "upstream-content-encoding-forbidden")
    require(content_types == ["text/event-stream"], "upstream-content-type-invalid")
    require(0 < len(response.body) <= MAX_UPSTREAM_BODY_BYTES, "upstream-body-size-invalid")
    require(token not in response.body, "upstream-token-reflection")
    text = parse_upstream_sse(response.body, expected_model, expected_text)
    clean = synthesize_clean_sse(expected_model, text)
    return ValidatedUpstream(text=text, clean_body=clean, upstream_sha256=sha256(response.body))


def validate_litellm_peer_manifest(path: Path = LITELLM_PEER_MANIFEST) -> tuple[dict[str, Any], str]:
    raw = _root_owned_file_bytes(path, maximum=65_536)
    manifest = strict_json_loads(raw)
    fields = {
        "schema_version", "service_unit", "service_unit_sha256", "launcher", "launcher_sha256",
        "config", "config_sha256", "python", "python_sha256", "uid", "gid", "cgroup",
        "cmdline", "host", "port",
    }
    require(type(manifest) is dict and set(manifest) == fields, "litellm-peer-manifest-invalid")
    require(
        manifest["schema_version"] == "1"
        and manifest["service_unit"] == str(LITELLM_SERVICE_UNIT)
        and manifest["launcher"] == str(LITELLM_LAUNCHER)
        and manifest["config"] == str(LITELLM_CONFIG)
        and manifest["cgroup"] == LITELLM_CGROUP
        and manifest["host"] == LITELLM_HOST
        and manifest["port"] == LITELLM_PORT
        and type(manifest["uid"]) is int
        and type(manifest["gid"]) is int
        and manifest["uid"] > 0
        and manifest["gid"] > 0,
        "litellm-peer-manifest-invalid",
    )
    expected_cmdline = [
        "/opt/litellm/.venv/bin/python",
        str(LITELLM_LAUNCHER),
        "--config",
        str(LITELLM_CONFIG),
        "--host",
        "0.0.0.0",
        "--port",
        str(LITELLM_PORT),
    ]
    require(manifest["cmdline"] == expected_cmdline, "litellm-peer-manifest-invalid")
    python_path = Path(manifest["python"])
    require(python_path.is_absolute(), "litellm-peer-manifest-invalid")
    artifacts = (
        (LITELLM_SERVICE_UNIT, "service_unit_sha256", False, 1_048_576),
        (LITELLM_LAUNCHER, "launcher_sha256", True, 1_048_576),
        (LITELLM_CONFIG, "config_sha256", False, 4_194_304),
        (python_path, "python_sha256", True, 64 * 1024 * 1024),
    )
    for artifact, field, executable, maximum in artifacts:
        digest = sha256(_root_owned_file_bytes(artifact, maximum=maximum, executable=executable))
        require(manifest[field] == digest, "litellm-peer-manifest-digest-mismatch")
    return manifest, sha256(canonical_json(manifest))


def _proc_identity(pid: int, manifest: dict[str, Any]) -> tuple[int, int]:
    proc = Path("/proc") / str(pid)
    try:
        metadata = os.stat(proc)
        cmdline_raw = (proc / "cmdline").read_bytes()
        cgroup_lines = (proc / "cgroup").read_text(encoding="ascii").splitlines()
        stat_raw = (proc / "stat").read_text(encoding="ascii")
        executable = os.readlink(proc / "exe")
    except (OSError, UnicodeDecodeError) as error:
        raise SpikeError("litellm-peer-process-unavailable") from error
    try:
        cmdline = [item.decode("utf-8", errors="strict") for item in cmdline_raw.rstrip(b"\0").split(b"\0")]
    except UnicodeDecodeError as error:
        raise SpikeError("litellm-peer-process-invalid") from error
    require(
        metadata.st_uid == manifest["uid"]
        and metadata.st_gid == manifest["gid"]
        and cmdline == manifest["cmdline"]
        and f"0::{manifest['cgroup']}" in cgroup_lines
        and Path(executable) == Path(manifest["python"]),
        "litellm-peer-process-invalid",
    )
    try:
        suffix = stat_raw.rsplit(")", 1)[1].split()
        start_time = int(suffix[19])
    except (IndexError, ValueError) as error:
        raise SpikeError("litellm-peer-process-invalid") from error
    require(start_time > 0, "litellm-peer-process-invalid")
    return pid, start_time


def _find_litellm_process(manifest: dict[str, Any]) -> tuple[int, int]:
    matches: list[tuple[int, int]] = []
    try:
        entries = list(os.scandir("/proc"))
    except OSError as error:
        raise SpikeError("litellm-peer-process-unavailable") from error
    for entry in entries:
        if not entry.name.isascii() or not entry.name.isdecimal():
            continue
        try:
            matches.append(_proc_identity(int(entry.name), manifest))
        except SpikeError:
            continue
    require(len(matches) == 1, "litellm-peer-process-count-invalid")
    return matches[0]


def _litellm_listener_inode(expected_uid: int) -> int:
    try:
        lines = Path("/proc/net/tcp").read_text(encoding="ascii").splitlines()[1:]
    except (OSError, UnicodeDecodeError) as error:
        raise SpikeError("litellm-listener-unavailable") from error
    port = f"{LITELLM_PORT:04X}"
    allowed_addresses = {"00000000", "A00A16AC"}
    matches: list[int] = []
    for line in lines:
        fields = line.split()
        if len(fields) < 10 or ":" not in fields[1]:
            continue
        address, observed_port = fields[1].split(":", 1)
        try:
            uid = int(fields[7])
            inode = int(fields[9])
        except ValueError:
            continue
        if fields[3] == "0A" and observed_port == port and address in allowed_addresses and uid == expected_uid:
            matches.append(inode)
    require(len(matches) == 1 and matches[0] > 0, "litellm-listener-count-invalid")
    return matches[0]


def _process_owns_socket(pid: int, inode: int) -> None:
    target = f"socket:[{inode}]"
    try:
        observed = [os.readlink(entry.path) for entry in os.scandir(f"/proc/{pid}/fd")]
    except OSError as error:
        raise SpikeError("litellm-listener-owner-unavailable") from error
    require(observed.count(target) == 1, "litellm-listener-owner-invalid")


@dataclass
class AuthenticatedLiteLLMTransport:
    socket: socket.socket
    pidfd: int
    pid: int
    start_time: int
    listener_inode: int
    manifest: dict[str, Any]
    identity_sha256: str

    def revalidate(self) -> None:
        poller = select.poll()
        poller.register(self.pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
        require(not poller.poll(0), "litellm-peer-exited")
        require(_proc_identity(self.pid, self.manifest) == (self.pid, self.start_time), "litellm-peer-process-changed")
        require(_litellm_listener_inode(self.manifest["uid"]) == self.listener_inode, "litellm-listener-changed")
        _process_owns_socket(self.pid, self.listener_inode)
        require(
            self.socket.getpeername() == (LITELLM_HOST, LITELLM_PORT)
            and self.socket.getsockname()[0] == LITELLM_HOST,
            "litellm-connected-peer-invalid",
        )

    def close(self) -> None:
        try:
            self.socket.close()
        finally:
            os.close(self.pidfd)


def open_authenticated_litellm_transport() -> AuthenticatedLiteLLMTransport:
    manifest, manifest_digest = validate_litellm_peer_manifest()
    require(os.getuid() == manifest["uid"] and os.getgid() == manifest["gid"], "litellm-peer-identity-user-invalid")
    pid, start_time = _find_litellm_process(manifest)
    listener_inode = _litellm_listener_inode(manifest["uid"])
    _process_owns_socket(pid, listener_inode)
    try:
        pidfd = os.pidfd_open(pid, 0)
    except OSError as error:
        raise SpikeError("litellm-peer-pidfd-unavailable") from error
    connected = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        connected.settimeout(UPSTREAM_TIMEOUT_SECONDS)
        connected.bind((LITELLM_HOST, 0))
        connected.connect((LITELLM_HOST, LITELLM_PORT))
        identity = sha256(canonical_json({
            "listener_inode": listener_inode,
            "manifest_sha256": manifest_digest,
            "pid": pid,
            "start_time": start_time,
        }))
        transport = AuthenticatedLiteLLMTransport(
            socket=connected,
            pidfd=pidfd,
            pid=pid,
            start_time=start_time,
            listener_inode=listener_inode,
            manifest=manifest,
            identity_sha256=identity,
        )
        transport.revalidate()
        return transport
    except BaseException:
        connected.close()
        os.close(pidfd)
        raise


def forward_upstream(body: bytes, token: bytes) -> UpstreamHTTPResponse:
    validate_upstream_request_body(body)
    require(
        type(token) is bytes
        and 0 < len(token) <= MAX_CREDENTIAL_BYTES
        and all(byte >= 0x20 and byte != 0x7F for byte in token),
        "credential-invalid",
    )
    try:
        token_text = token.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise SpikeError("credential-not-utf8") from error
    deadline = time.monotonic() + UPSTREAM_TIMEOUT_SECONDS
    transport = open_authenticated_litellm_transport()
    connection = http.client.HTTPConnection(LITELLM_HOST, LITELLM_PORT, timeout=UPSTREAM_TIMEOUT_SECONDS)
    connection.sock = transport.socket
    try:
        connection.putrequest("POST", LITELLM_PATH, skip_host=True, skip_accept_encoding=True)
        connection.putheader("Host", f"{LITELLM_HOST}:{LITELLM_PORT}")
        connection.putheader("Authorization", f"Bearer {token_text}")
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Accept", "text/event-stream")
        connection.putheader("Content-Length", str(len(body)))
        connection.putheader("Connection", "close")
        transport.revalidate()
        connection.endheaders(body)
        remaining = deadline - time.monotonic()
        require(remaining > 0, "upstream-timeout")
        if connection.sock is not None:
            connection.sock.settimeout(remaining)
        response = connection.getresponse()
        headers = response.getheaders()
        chunks: list[bytes] = []
        total = 0
        while True:
            remaining = deadline - time.monotonic()
            require(remaining > 0, "upstream-timeout")
            if connection.sock is not None:
                connection.sock.settimeout(remaining)
            chunk = response.read(min(65_536, MAX_UPSTREAM_BODY_BYTES + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            require(total <= MAX_UPSTREAM_BODY_BYTES, "upstream-body-size-invalid")
            chunks.append(chunk)
        return UpstreamHTTPResponse(
            status=response.status,
            headers=headers,
            body=b"".join(chunks),
            peer_identity_sha256=transport.identity_sha256,
        )
    except SpikeError:
        raise
    except (socket.timeout, TimeoutError) as error:
        raise SpikeError("upstream-timeout") from error
    except (OSError, http.client.HTTPException) as error:
        raise SpikeError("upstream-request-failed") from error
    finally:
        connection.close()
        transport.close()


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        try:
            chunk = sock.recv(remaining)
        except (OSError, socket.timeout) as error:
            raise SpikeError("control-channel-read-failed") from error
        require(bool(chunk), "control-channel-truncated")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def send_frame(sock: socket.socket, payload: Any) -> None:
    raw = canonical_json(payload)
    require(0 < len(raw) <= MAX_CONTROL_BYTES, "control-frame-size-invalid")
    try:
        sock.sendall(struct.pack("!I", len(raw)) + raw)
    except (OSError, socket.timeout) as error:
        raise SpikeError("control-channel-write-failed") from error


def recv_frame(sock: socket.socket) -> dict[str, Any]:
    size = struct.unpack("!I", _recv_exact(sock, 4))[0]
    require(0 < size <= MAX_CONTROL_BYTES, "control-frame-size-invalid")
    payload = strict_json_loads(_recv_exact(sock, size))
    require(type(payload) is dict, "control-frame-invalid")
    return payload


def _decode_frame_body(frame: dict[str, Any], prefix: str) -> bytes:
    encoded = frame.get(f"{prefix}_b64")
    digest = frame.get(f"{prefix}_sha256")
    require(type(encoded) is str and type(digest) is str and SHA256_HEX.fullmatch(digest) is not None, "control-frame-body-invalid")
    try:
        raw = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as error:
        raise SpikeError("control-frame-body-invalid") from error
    require(base64.b64encode(raw).decode("ascii") == encoded and sha256(raw) == digest, "control-frame-body-invalid")
    return raw


def _http_error(sock: socket.socket, status: int) -> None:
    phrase = "Bad Request" if status == 400 else "Bad Gateway"
    body = phrase.encode("ascii") + b"\n"
    raw = (
        f"HTTP/1.1 {status} {phrase}\r\n"
        "Content-Type: text/plain\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii") + body
    try:
        sock.sendall(raw)
    except OSError:
        pass


@dataclass
class RelayState:
    request_count: int = 0
    error_code: str | None = None


def relay_one_request(
    listener: socket.socket,
    control: socket.socket,
    *,
    relay_port: int,
    expected_model: str,
    expected_prompt: str,
    state: RelayState,
) -> None:
    gate = OneRequestGate()
    connection: socket.socket | None = None
    try:
        connection, address = listener.accept()
        listener.close()
        require(type(address) is tuple and address[0] == "127.0.0.1", "relay-peer-invalid")
        gate.claim()
        state.request_count = gate.count
        request = read_child_http_request(
            connection,
            expected_host=f"127.0.0.1:{relay_port}",
            expected_model=expected_model,
            expected_prompt=expected_prompt,
        )
        send_frame(
            control,
            {
                "type": "request",
                "body_sha256": sha256(request.body),
                "body_b64": base64.b64encode(request.body).decode("ascii"),
            },
        )
        control.settimeout(UPSTREAM_TIMEOUT_SECONDS + CONTROL_TIMEOUT_SECONDS)
        frame = recv_frame(control)
        if frame.get("type") != "response" or set(frame) != {"type", "response_sha256", "response_b64"}:
            _http_error(connection, 502)
            raise SpikeError("parent-response-invalid")
        body = _decode_frame_body(frame, "response")
        require(0 < len(body) <= MAX_UPSTREAM_BODY_BYTES, "parent-response-invalid")
        headers = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/event-stream\r\n"
            "Cache-Control: no-store\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        connection.sendall(headers + body)
    except SpikeError as error:
        state.error_code = error.code
        if connection is not None:
            _http_error(connection, 400)
    except (OSError, socket.timeout):
        state.error_code = "relay-io-failed"
        if connection is not None:
            _http_error(connection, 400)
    finally:
        try:
            listener.close()
        except OSError:
            pass
        if connection is not None:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()


def _sandbox_environment() -> dict[str, str]:
    allowed = {
        "HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_CACHE_HOME",
        "XDG_STATE_HOME",
        "TMPDIR",
        "PATH",
        "LANG",
        "LC_ALL",
        "PWD",
        "OPENCODE_DB",
        "OPENCODE_AUTH_CONTENT",
        "OPENCODE_CONFIG_CONTENT",
        "OPENCODE_CONFIG_DIR",
        "OPENCODE_DISABLE_PROJECT_CONFIG",
        "OPENCODE_DISABLE_DEFAULT_PLUGINS",
        "OPENCODE_DISABLE_CLAUDE_CODE",
        "OPENCODE_DISABLE_CLAUDE_CODE_PROMPT",
        "OPENCODE_DISABLE_CLAUDE_CODE_SKILLS",
        "OPENCODE_DISABLE_EXTERNAL_SKILLS",
        "OPENCODE_DISABLE_AUTOUPDATE",
        "OPENCODE_DISABLE_MODELS_FETCH",
        "OPENCODE_DISABLE_AUTOCOMPACT",
        "OPENCODE_DISABLE_PRUNE",
        "OPENCODE_DISABLE_LSP_DOWNLOAD",
        "OPENCODE_PURE",
        "OPENCODE_TEST_MANAGED_CONFIG_DIR",
    }
    require(TOKEN_ENV not in os.environ and "CREDENTIALS_DIRECTORY" not in os.environ, "sandbox-credential-present")
    require(set(os.environ).issubset(allowed), "sandbox-environment-not-closed")
    return {key: os.environ[key] for key in sorted(allowed) if key in os.environ}


def _run_bounded_opencode(command: list[str], environment: dict[str, str]) -> tuple[int, bytes, bytes]:
    old_limit = resource.getrlimit(resource.RLIMIT_FSIZE)
    hard_limit = old_limit[1]
    output_limit = max(MAX_EVENT_LOG_BYTES, MAX_STDERR_BYTES)
    if hard_limit != resource.RLIM_INFINITY:
        output_limit = min(output_limit, hard_limit)
    if old_limit[0] != resource.RLIM_INFINITY:
        output_limit = min(output_limit, old_limit[0])
    resource.setrlimit(resource.RLIMIT_FSIZE, (output_limit, hard_limit))
    try:
        return _run_bounded_opencode_with_limit(command, environment)
    finally:
        resource.setrlimit(resource.RLIMIT_FSIZE, old_limit)


def _run_bounded_opencode_with_limit(command: list[str], environment: dict[str, str]) -> tuple[int, bytes, bytes]:
    with tempfile.TemporaryFile(dir="/tmp") as stdout, tempfile.TemporaryFile(dir="/tmp") as stderr:
        try:
            process = subprocess.Popen(
                command,
                env=environment,
                cwd="/work",
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
                close_fds=True,
            )
            try:
                returncode = process.wait(timeout=SANDBOX_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired as error:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise SpikeError("opencode-timeout") from error
        except SpikeError:
            raise
        except OSError as error:
            raise SpikeError("opencode-start-failed") from error
        require(stdout.tell() <= MAX_EVENT_LOG_BYTES and stderr.tell() <= MAX_STDERR_BYTES, "opencode-output-oversized")
        stdout.seek(0)
        stderr.seek(0)
        return returncode, stdout.read(), stderr.read()


def sandbox_relay_phase(control_socket: Path, relay_port: int, model: str, title: str, prompt: str) -> int:
    raw_capability = sys.stdin.buffer.read(66)
    require(len(raw_capability) == 65 and raw_capability.endswith(b"\n"), "capability-input-invalid")
    try:
        capability = raw_capability[:-1].decode("ascii")
    except UnicodeDecodeError as error:
        raise SpikeError("capability-input-invalid") from error
    require(CAPABILITY.fullmatch(capability) is not None, "capability-input-invalid")
    require(model in STANDARD_MODELS and control_socket == Path("/parent-bridge/control.sock"), "sandbox-arguments-invalid")
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    listener.settimeout(CONTROL_TIMEOUT_SECONDS)
    try:
        listener.bind(("127.0.0.1", relay_port))
        listener.listen(1)
    except OSError as error:
        listener.close()
        raise SpikeError("relay-listener-failed") from error
    control = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    control.settimeout(CONTROL_TIMEOUT_SECONDS)
    try:
        control.connect(str(control_socket))
        send_frame(
            control,
            {"type": "hello", "protocol": PROTOCOL, "capability": capability, "relay_port": relay_port},
        )
        acknowledgement = recv_frame(control)
        require(acknowledgement == {"type": "hello-ack", "protocol": PROTOCOL}, "handshake-ack-invalid")
        state = RelayState()
        relay = threading.Thread(
            target=relay_one_request,
            kwargs={
                "listener": listener,
                "control": control,
                "relay_port": relay_port,
                "expected_model": model,
                "expected_prompt": prompt,
                "state": state,
            },
            name="noetic-opencode-relay",
        )
        relay.start()
        returncode, stdout, stderr = _run_bounded_opencode(build_opencode_command(model, title, prompt), _sandbox_environment())
        relay.join(CONTROL_TIMEOUT_SECONDS)
        if relay.is_alive():
            listener.close()
            relay.join(1)
            state.error_code = "relay-timeout"
        send_frame(
            control,
            {
                "type": "sandbox-result",
                "returncode": returncode,
                "relay_request_count": state.request_count,
                "relay_error": state.error_code,
            },
        )
        _write_all(sys.stdout.fileno(), stdout)
        _write_all(sys.stderr.fileno(), stderr)
        return 0 if returncode == 0 and state.request_count == 1 and state.error_code is None else 1
    finally:
        try:
            listener.close()
        except OSError:
            pass
        control.close()


def _peer_credentials(sock: socket.socket) -> tuple[int, int, int]:
    require(hasattr(socket, "SO_PEERCRED"), "peer-credentials-unavailable")
    try:
        raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    except OSError as error:
        raise SpikeError("peer-credentials-unavailable") from error
    return struct.unpack("3i", raw)


def _parent_pid(pid: int) -> int:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
        suffix = raw.rsplit(")", 1)[1].split()
        return int(suffix[1])
    except (OSError, ValueError, IndexError, UnicodeDecodeError) as error:
        raise SpikeError("peer-process-unverifiable") from error


def verify_relay_peer(sock: socket.socket, sandbox_pid: int) -> None:
    pid, uid, gid = _peer_credentials(sock)
    require(uid == os.getuid() and gid == os.getgid() and pid > 0, "relay-peer-credentials-invalid")
    current = pid
    for _ in range(64):
        if current == sandbox_pid:
            return
        require(current > 1, "relay-peer-not-sandbox-descendant")
        current = _parent_pid(current)
    raise SpikeError("relay-peer-not-sandbox-descendant")


def parse_opencode_jsonl(raw: bytes, expected_text: str) -> tuple[str, int]:
    require(0 < len(raw) <= MAX_EVENT_LOG_BYTES and raw.endswith(b"\n"), "event-log-framing-invalid")
    lines = raw.splitlines()
    require(len(lines) == 3, "event-count-invalid")
    events = [strict_json_loads(line) for line in lines]
    require([event.get("type") if type(event) is dict else None for event in events] == ["step_start", "text", "step_finish"], "event-order-invalid")
    session_id: str | None = None
    message_id: str | None = None
    part_ids: set[str] = set()
    for event in events:
        require(type(event) is dict and set(event) == {"type", "timestamp", "sessionID", "part"}, "event-fields-invalid")
        require(type(event["timestamp"]) is int and not isinstance(event["timestamp"], bool) and event["timestamp"] > 0, "event-timestamp-invalid")
        require(type(event["sessionID"]) is str and event["sessionID"].startswith("ses_") and SAFE_ID.fullmatch(event["sessionID"]), "event-session-invalid")
        if session_id is None:
            session_id = event["sessionID"]
        require(event["sessionID"] == session_id, "event-session-mismatch")
        part = event["part"]
        require(type(part) is dict, "event-part-invalid")
        require(part.get("sessionID") == session_id, "event-part-session-mismatch")
        require(type(part.get("messageID")) is str and SAFE_ID.fullmatch(part["messageID"]), "event-message-id-invalid")
        if message_id is None:
            message_id = part["messageID"]
        require(part["messageID"] == message_id, "event-message-id-mismatch")
        require(type(part.get("id")) is str and SAFE_ID.fullmatch(part["id"]) and part["id"] not in part_ids, "event-part-id-invalid")
        part_ids.add(part["id"])
    start, text, finish = (event["part"] for event in events)
    require(set(start) == {"id", "sessionID", "messageID", "type"} and start["type"] == "step-start", "step-start-invalid")
    require(
        set(text) == {"id", "sessionID", "messageID", "type", "text", "time", "metadata"}
        and text["type"] == "text",
        "text-event-invalid",
    )
    metadata = text["metadata"]
    require(
        type(metadata) is dict
        and metadata == {"openai": {"itemId": CLEAN_MESSAGE_ID}},
        "text-event-metadata-invalid",
    )
    require(text["text"] == expected_text, "event-text-mismatch")
    require(
        type(text["time"]) is dict
        and set(text["time"]) == {"start", "end"}
        and all(type(text["time"][key]) is int and text["time"][key] >= 0 for key in ("start", "end"))
        and text["time"]["end"] >= text["time"]["start"],
        "text-event-time-invalid",
    )
    require(set(finish) == {"id", "sessionID", "messageID", "type", "reason", "cost", "tokens"} and finish["type"] == "step-finish", "step-finish-invalid")
    require(finish["reason"] == "stop", "step-finish-reason-invalid")
    require(type(finish["cost"]) in {int, float} and not isinstance(finish["cost"], bool) and math.isfinite(finish["cost"]) and finish["cost"] >= 0, "step-finish-cost-invalid")
    tokens = finish["tokens"]
    require(type(tokens) is dict and set(tokens) in ({"input", "output", "reasoning", "cache"}, {"total", "input", "output", "reasoning", "cache"}), "step-finish-tokens-invalid")
    require(type(tokens["cache"]) is dict and set(tokens["cache"]) == {"read", "write"}, "step-finish-tokens-invalid")
    values = [tokens[key] for key in ("input", "output", "reasoning")] + [tokens["cache"][key] for key in ("read", "write")]
    if "total" in tokens:
        values.append(tokens["total"])
    require(all(type(value) in {int, float} and not isinstance(value, bool) and math.isfinite(value) and value >= 0 for value in values), "step-finish-tokens-invalid")
    return text["text"], 1


def _empty_isolation() -> dict[str, bool]:
    return {
        "bwrap": False,
        "clear_environment": False,
        "credential_parent_only": False,
        "network_unshared": False,
        "user_namespace": False,
        "pid_namespace": False,
        "ipc_namespace": False,
        "uts_namespace": False,
        "nested_userns_disabled": False,
        "private_proc": False,
        "tmpfs_state": False,
        "host_source_mounted": False,
    }


def _base_result() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "evidence_class": "non-evidence",
        "runtime_adapter_ready": False,
        "policy_status": "contract-only",
        "execution_status": "failure",
        "failure_code": "execution-not-started",
        "component_sha": COMPONENT_SHA,
        "router_identity_sha256": None,
        "route_decision_id": None,
        "route_reference_sha256": None,
        "routed_model": None,
        "opencode_version": None,
        "opencode_sha256": None,
        "static_title": None,
        "title_sha256": None,
        "config_sha256": None,
        "json_event_log_sha256": None,
        "upstream_response_sha256": None,
        "litellm_peer_identity_sha256": None,
        "model_turn_count": 0,
        "bridge_request_count": 0,
        "upstream_request_count": 0,
        "parsed_upstream_completion": False,
        "output_text": None,
        "nonce_sha256": None,
        "nonce_matched": False,
        "isolation": _empty_isolation(),
        "claim_state": "none",
        "request_issued": False,
        "outcome_status": "pending",
        "report_outcome_acknowledged": False,
        "report_outcome_acknowledgement_sha256": None,
        "report_outcome_record_sha256": None,
        "report_outcome_id": None,
    }


def validate_result_record(result: Any) -> dict[str, Any]:
    require(type(result) is dict and set(result) == RESULT_FIELDS, "result-fields-invalid")
    require(
        result["schema_version"] == "1"
        and result["evidence_class"] == "non-evidence"
        and result["runtime_adapter_ready"] is False
        and result["policy_status"] == "contract-only"
        and result["component_sha"] == COMPONENT_SHA
        and result["report_outcome_id"] is None,
        "result-honesty-invalid",
    )
    require(result["execution_status"] in {"success", "failure"}, "result-status-invalid")
    require(result["failure_code"] is None or (type(result["failure_code"]) is str and re.fullmatch(r"[a-z0-9-]{1,80}", result["failure_code"])), "result-failure-code-invalid")
    for field in (
        "route_reference_sha256",
        "router_identity_sha256",
        "opencode_sha256",
        "title_sha256",
        "config_sha256",
        "json_event_log_sha256",
        "upstream_response_sha256",
        "litellm_peer_identity_sha256",
        "nonce_sha256",
        "report_outcome_acknowledgement_sha256",
        "report_outcome_record_sha256",
    ):
        require(result[field] is None or (type(result[field]) is str and SHA256_HEX.fullmatch(result[field])), "result-digest-invalid")
    require(result["route_decision_id"] is None or (type(result["route_decision_id"]) is str and DECISION_ID.fullmatch(result["route_decision_id"])), "result-decision-id-invalid")
    require(result["routed_model"] is None or result["routed_model"] in STANDARD_MODELS, "result-model-invalid")
    require(result["opencode_version"] in {None, OPENCODE_VERSION}, "result-binary-version-invalid")
    require(result["static_title"] is None or (type(result["static_title"]) is str and re.fullmatch(r"noetic-d-[0-9]{8}-[0-9]{6}", result["static_title"])), "result-title-invalid")
    require(result["output_text"] is None or (type(result["output_text"]) is str and len(result["output_text"]) <= 128), "result-output-invalid")
    for field in ("model_turn_count", "bridge_request_count", "upstream_request_count"):
        require(type(result[field]) is int and not isinstance(result[field], bool) and result[field] in {0, 1}, "result-count-invalid")
    for field in ("parsed_upstream_completion", "nonce_matched", "request_issued", "report_outcome_acknowledged"):
        require(type(result[field]) is bool, "result-boolean-invalid")
    require(type(result["isolation"]) is dict and set(result["isolation"]) == ISOLATION_FIELDS and all(type(value) is bool for value in result["isolation"].values()), "result-isolation-invalid")
    require(result["claim_state"] in {"none", "claimed", "request-issued"}, "result-claim-state-invalid")
    require(result["request_issued"] is (result["claim_state"] == "request-issued"), "result-request-state-invalid")
    require(result["outcome_status"] in {"pending", "report-issued", "reported", "reconciled"}, "result-outcome-status-invalid")
    require(
        (
            result["outcome_status"] in {"pending", "report-issued"}
            and result["report_outcome_acknowledged"] is False
            and result["report_outcome_acknowledgement_sha256"] is None
            and result["report_outcome_record_sha256"] is None
        )
        or (
            result["outcome_status"] == "reported"
            and result["report_outcome_acknowledged"] is True
            and type(result["report_outcome_acknowledgement_sha256"]) is str
            and type(result["report_outcome_record_sha256"]) is str
        )
        or (
            result["outcome_status"] == "reconciled"
            and result["report_outcome_acknowledged"] is False
            and result["report_outcome_acknowledgement_sha256"] is None
            and type(result["report_outcome_record_sha256"]) is str
        ),
        "result-outcome-ack-invalid",
    )
    if result["execution_status"] == "success":
        require(result["failure_code"] is None, "result-success-failure-code")
        require(
            result["route_decision_id"] is not None
            and result["router_identity_sha256"] is not None
            and result["route_reference_sha256"] is not None
            and result["routed_model"] is not None
            and result["opencode_version"] == OPENCODE_VERSION
            and result["opencode_sha256"] == OPENCODE_SHA256
            and result["static_title"] is not None
            and result["title_sha256"] is not None
            and result["config_sha256"] is not None
            and result["json_event_log_sha256"] is not None
            and result["upstream_response_sha256"] is not None
            and result["litellm_peer_identity_sha256"] is not None
            and result["nonce_sha256"] is not None
            and result["model_turn_count"] == 1
            and result["bridge_request_count"] == 1
            and result["upstream_request_count"] == 1
            and result["parsed_upstream_completion"] is True
            and type(result["output_text"]) is str
            and re.fullmatch(r"READY [a-f0-9]{32}", result["output_text"]) is not None
            and result["nonce_matched"] is True
            and result["claim_state"] == "request-issued"
            and all(result["isolation"][key] for key in ISOLATION_FIELDS - {"host_source_mounted"})
            and result["isolation"]["host_source_mounted"] is False,
            "result-success-contract-invalid",
        )
    else:
        require(type(result["failure_code"]) is str, "result-failure-code-invalid")
    return result


def _sandbox_metrics(
    *,
    route: dict[str, Any],
    route_raw: bytes,
    token: bytearray,
    claim_path: Path,
    result: dict[str, Any],
    upstream_sender: Callable[[bytes, bytes], UpstreamHTTPResponse],
    expected_uid: int,
) -> None:
    decision = route["decision"]
    decision_id = decision["decision_id"]
    model = decision["model_ref"]["upstream_model_id"]
    nonce = secrets.token_hex(16)
    require(NONCE.fullmatch(nonce) is not None, "nonce-generation-invalid")
    prompt = f"Respond with exactly READY {nonce} and nothing else."
    expected_text = f"READY {nonce}"
    title = f"noetic-{decision_id}"
    relay_port = 30_000 + secrets.randbelow(30_000)
    config = build_opencode_config(model, relay_port)
    result.update(
        {
            "static_title": title,
            "title_sha256": sha256(title.encode("ascii")),
            "config_sha256": sha256(canonical_json(config)),
            "nonce_sha256": sha256(nonce.encode("ascii")),
        }
    )
    opencode: OpenedIdentity | None = None
    controller: OpenedIdentity | None = None
    control_directory: Path | None = None
    control_path: Path | None = None
    listener: socket.socket | None = None
    control: socket.socket | None = None
    process: subprocess.Popen[bytes] | None = None
    try:
        opencode = verify_opencode_identity(path=OPENCODE_PATH, expected_uid=expected_uid)
        controller = open_immutable_identity(
            CONTROLLER_PATH,
            expected_uid=expected_uid,
            executable=True,
            maximum=2_097_152,
        )
        result["opencode_version"] = opencode.version
        result["opencode_sha256"] = opencode.sha256
        control_directory = Path(tempfile.mkdtemp(prefix="noetic-opencode-spike-", dir="/tmp"))
        os.chmod(control_directory, 0o700)
        control_path = control_directory / "control.sock"
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.settimeout(CONTROL_TIMEOUT_SECONDS)
        listener.bind(str(control_path))
        os.chmod(control_path, 0o600)
        listener.listen(1)
        command = build_bwrap_command(
            opencode_fd=opencode.descriptor,
            controller_fd=controller.descriptor,
            control_directory=control_directory,
            relay_port=relay_port,
            config=config,
            model=model,
            title=title,
            prompt=prompt,
        )
        require(TOKEN_ENV not in "\x00".join(command) and CREDENTIAL_NAME not in "\x00".join(command), "credential-leaked-to-sandbox-command")
        require(bytes(token) not in "\x00".join(command).encode("utf-8"), "credential-leaked-to-sandbox-command")
        process = subprocess.Popen(
            command,
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            pass_fds=(opencode.descriptor, controller.descriptor),
            close_fds=True,
            start_new_session=True,
        )
        capability = secrets.token_hex(32)
        require(CAPABILITY.fullmatch(capability) is not None, "capability-generation-invalid")
        require(process.stdin is not None, "sandbox-stdin-unavailable")
        process.stdin.write(capability.encode("ascii") + b"\n")
        process.stdin.flush()
        process.stdin.close()
        process.stdin = None
        try:
            control, _address = listener.accept()
        except (OSError, socket.timeout) as error:
            raise SpikeError("relay-handshake-timeout") from error
        control.settimeout(CONTROL_TIMEOUT_SECONDS)
        verify_relay_peer(control, process.pid)
        hello = recv_frame(control)
        require(
            type(hello) is dict
            and set(hello) == {"type", "protocol", "capability", "relay_port"}
            and hello["type"] == "hello"
            and hello["protocol"] == PROTOCOL
            and hello["relay_port"] == relay_port
            and type(hello["capability"]) is str
            and secrets.compare_digest(hello["capability"], capability),
            "relay-handshake-invalid",
        )
        result["isolation"].update({
            "bwrap": True,
            "clear_environment": True,
            "credential_parent_only": True,
            "network_unshared": True,
            "user_namespace": True,
            "pid_namespace": True,
            "ipc_namespace": True,
            "uts_namespace": True,
            "nested_userns_disabled": True,
            "private_proc": True,
            "tmpfs_state": True,
            "host_source_mounted": False,
        })
        listener.close()
        try:
            control_path.unlink()
        except FileNotFoundError:
            pass
        send_frame(control, {"type": "hello-ack", "protocol": PROTOCOL})
        request_frame = recv_frame(control)
        if request_frame.get("type") == "sandbox-result":
            relay_error = request_frame.get("relay_error")
            require(
                type(relay_error) is str and re.fullmatch(r"[a-z0-9-]{1,80}", relay_error) is not None,
                "relay-request-frame-invalid",
            )
            raise SpikeError(relay_error)
        require(set(request_frame) == {"type", "body_sha256", "body_b64"} and request_frame.get("type") == "request", "relay-request-frame-invalid")
        result["bridge_request_count"] = 1
        child_body = _decode_frame_body(request_frame, "body")
        child_payload = strict_json_loads(child_body)
        validate_child_request_body(child_payload, model, prompt)
        upstream_body = canonical_upstream_request(model, prompt)
        mark_claim_issued(claim_path, decision_id, "execute")
        result["claim_state"] = "request-issued"
        result["request_issued"] = True
        result["upstream_request_count"] = 1
        result["model_turn_count"] = 1
        response = upstream_sender(upstream_body, bytes(token))
        require(
            type(response.peer_identity_sha256) is str
            and SHA256_HEX.fullmatch(response.peer_identity_sha256) is not None,
            "litellm-peer-identity-missing",
        )
        result["litellm_peer_identity_sha256"] = response.peer_identity_sha256
        validated = validate_upstream_response(response, token=bytes(token), expected_model=model, expected_text=expected_text)
        result["parsed_upstream_completion"] = True
        result["upstream_response_sha256"] = validated.upstream_sha256
        send_frame(
            control,
            {
                "type": "response",
                "response_sha256": sha256(validated.clean_body),
                "response_b64": base64.b64encode(validated.clean_body).decode("ascii"),
            },
        )
        final_frame = recv_frame(control)
        require(
            type(final_frame) is dict
            and set(final_frame) == {"type", "returncode", "relay_request_count", "relay_error"}
            and final_frame["type"] == "sandbox-result"
            and final_frame["returncode"] == 0
            and final_frame["relay_request_count"] == 1
            and final_frame["relay_error"] is None,
            "sandbox-result-invalid",
        )
        try:
            stdout, stderr = process.communicate(timeout=SANDBOX_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as error:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
            raise SpikeError("sandbox-timeout") from error
        require(len(stdout) <= MAX_EVENT_LOG_BYTES and len(stderr) <= MAX_STDERR_BYTES, "sandbox-output-oversized")
        result["json_event_log_sha256"] = sha256(stdout)
        require(process.returncode == 0 and stderr == b"", "opencode-process-failed")
        output, turns = parse_opencode_jsonl(stdout, expected_text)
        require(turns == 1 and output == validated.text, "opencode-corroboration-mismatch")
        result["output_text"] = output
        result["nonce_matched"] = output == expected_text
        require(result["nonce_matched"], "nonce-output-mismatch")
    finally:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        if process is not None:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        if control is not None:
            try:
                send_frame(control, {"type": "abort"})
            except SpikeError:
                pass
            control.close()
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
        if opencode is not None:
            opencode.close()
        if controller is not None:
            controller.close()
        if control_path is not None:
            try:
                control_path.unlink()
            except FileNotFoundError:
                pass
        if control_directory is not None:
            shutil.rmtree(control_directory, ignore_errors=True)


def execute_phase(
    *,
    state_dir: Path = EXECUTE_STATE_DIR,
    input_dir: Path = HANDOFF_STATE_DIR,
    input_reader: Callable[[Path], tuple[Any, bytes]] = read_root_json,
    environment: Mapping[str, str] | None = None,
    upstream_sender: Callable[[bytes, bytes], UpstreamHTTPResponse] = forward_upstream,
    expected_uid: int = 0,
) -> dict[str, Any]:
    result = _base_result()
    result_path = state_dir / "result.json"
    token: bytearray | None = None
    try:
        route, route_raw = input_reader(input_dir / "route.json")
        validate_route_record(route)
        decision = route["decision"]
        decision_id = decision["decision_id"]
        result.update(
            {
                "route_decision_id": decision_id,
                "router_identity_sha256": route["router_identity_sha256"],
                "route_reference_sha256": sha256(route_raw),
                "routed_model": decision["model"],
            }
        )
        claim_path = state_dir / "execute.claim"
        try:
            create_claim(claim_path, decision_id, "execute")
        except SpikeError as error:
            if error.code != "state-already-exists":
                raise
            states = claim_states(claim_path, "execute", decision_id)
            result["claim_state"] = states[-1]
            result["request_issued"] = states[-1] == "request-issued"
            if result["request_issued"]:
                result["bridge_request_count"] = 1
                result["upstream_request_count"] = 1
                result["model_turn_count"] = 1
            raise SpikeError("execute-replay-blocked") from error
        result["claim_state"] = "claimed"
        token = read_systemd_credential(environment)
        _sandbox_metrics(
            route=route,
            route_raw=route_raw,
            token=token,
            claim_path=claim_path,
            result=result,
            upstream_sender=upstream_sender,
            expected_uid=expected_uid,
        )
        result["execution_status"] = "success"
        result["failure_code"] = None
    except SpikeError as error:
        result["execution_status"] = "failure"
        result["failure_code"] = error.code
    except BaseException:
        result["execution_status"] = "failure"
        result["failure_code"] = "internal-error"
    finally:
        if token is not None:
            for index in range(len(token)):
                token[index] = 0
        validate_result_record(result)
        atomic_create_json(result_path, result)
    return result


def isolated_outcome_record_sha256(path: Path, decision_id: str, outcome: str, notes: str) -> str | None:
    try:
        raw = read_private_bytes(path, MAX_ROUTER_LOG_BYTES)
    except SpikeError as error:
        if error.code == "state-file-missing":
            return None
        raise
    if raw == b"":
        return None
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, "outcome-log-invalid")
    record = strict_json_loads(raw[:-1])
    require(
        type(record) is dict
        and set(record) == {"decision", "decision_id", "notes", "outcome", "ts"}
        and record["decision_id"] == decision_id
        and type(record["decision"]) is dict
        and record["decision"].get("decision_id") == decision_id
        and record["outcome"] == outcome
        and record["notes"] == notes
        and _valid_bounded_text(record["ts"], 128),
        "outcome-log-invalid",
    )
    return sha256(raw)


def outcome_phase(
    *,
    state_dir: Path = STATE_DIR,
    input_dir: Path = HANDOFF_STATE_DIR,
    input_reader: Callable[[Path], tuple[Any, bytes]] = read_root_json,
    command: Path = ROUTER_COMMAND,
    config: Path = ROUTER_CONFIG,
    component_sha: str = COMPONENT_SHA,
    outcomes_path: Path = ROUTER_OUTCOMES,
    router_factory: Callable[..., Any] = _router_factory,
    identity_validator: Callable[[Path, Path, str], str] = validate_router_component_identity,
    classification_validator: Callable[[Path], str] = validate_non_evidence_router_state,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    assert_no_credential_environment(environment)
    validate_router_arguments(command, config, component_sha)
    router_identity = identity_validator(command, config, component_sha)
    require(type(router_identity) is str and SHA256_HEX.fullmatch(router_identity), "router-identity-invalid")
    classification_sha = classification_validator(ROUTER_STATE_CLASSIFICATION)
    require(type(classification_sha) is str and SHA256_HEX.fullmatch(classification_sha), "router-state-classification-invalid")
    route, route_raw = input_reader(input_dir / "route.json")
    validate_route_record(route)
    require(
        route["router_identity_sha256"] == router_identity
        and route["router_state_classification_sha256"] == classification_sha,
        "router-identity-changed",
    )
    authoritative, _result_raw = input_reader(input_dir / "result.json")
    validate_result_record(authoritative)
    result_path = state_dir / "result.json"
    try:
        result, _state_raw = read_private_json(result_path)
        persisted = True
    except SpikeError as error:
        if error.code != "state-file-missing":
            raise
        result, persisted = dict(authoritative), False
    validate_result_record(result)
    decision_id = route["decision"]["decision_id"]
    require(
        authoritative["route_decision_id"] == decision_id
        and authoritative["router_identity_sha256"] == router_identity
        and authoritative["route_reference_sha256"] == sha256(route_raw)
        and authoritative["outcome_status"] == "pending"
        and all(result[field] == authoritative[field] for field in RESULT_FIELDS - {"outcome_status", "report_outcome_acknowledged", "report_outcome_acknowledgement_sha256", "report_outcome_record_sha256"})
        and result["outcome_status"] in {"pending", "report-issued"},
        "outcome-input-invalid",
    )
    outcome = "success" if result["execution_status"] == "success" else "failure"
    notes = (
        "OpenCode credential-isolated non-evidence spike completed"
        if outcome == "success"
        else f"OpenCode credential-isolated non-evidence spike failed: {result['failure_code']}"
    )
    require(_valid_bounded_text(notes, 1_000), "outcome-notes-invalid")
    claim_path = state_dir / "outcome.claim"
    if result["outcome_status"] == "report-issued":
        require(persisted, "outcome-state-invalid")
        require(claim_states(claim_path, "outcome", decision_id) == ["claimed", "report-issued"], "claim-state-invalid")
        record_sha = isolated_outcome_record_sha256(outcomes_path, decision_id, outcome, notes)
        require(record_sha is not None, "outcome-report-unresolved")
        fsync_router_log(outcomes_path)
        require(isolated_outcome_record_sha256(outcomes_path, decision_id, outcome, notes) == record_sha, "outcome-log-changed")
        result["outcome_status"] = "reconciled"
        result["report_outcome_record_sha256"] = record_sha
        validate_result_record(result)
        atomic_replace_json(result_path, result)
        return result
    require(not persisted, "outcome-state-invalid")
    create_claim(claim_path, decision_id, "outcome")
    mark_claim_issued(claim_path, decision_id, "outcome")
    result["outcome_status"] = "report-issued"
    validate_result_record(result)
    atomic_create_json(result_path, result)
    with router_factory(command, config, component_sha, litellm_token=None) as router:
        acknowledgement = router.call_tool(
            "report_outcome",
            {"decision_id": decision_id, "outcome": outcome, "notes": notes},
        )
    require(type(acknowledgement) is dict and acknowledgement == {"recorded": True}, "outcome-ack-invalid")
    fsync_router_log(outcomes_path)
    record_sha = isolated_outcome_record_sha256(outcomes_path, decision_id, outcome, notes)
    require(record_sha is not None, "outcome-log-invalid")
    result["outcome_status"] = "reported"
    result["report_outcome_acknowledged"] = True
    result["report_outcome_acknowledgement_sha256"] = sha256(canonical_json(acknowledgement))
    result["report_outcome_record_sha256"] = record_sha
    result["report_outcome_id"] = None
    validate_result_record(result)
    atomic_replace_json(result_path, result)
    return result


def _add_router_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--genus-router-command", type=Path, required=True)
    parser.add_argument("--genus-router-config", type=Path, required=True)
    parser.add_argument("--genus-router-sha", required=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    route_parser = subparsers.add_parser("route")
    _add_router_arguments(route_parser)
    subparsers.add_parser("execute")
    outcome_parser = subparsers.add_parser("outcome")
    _add_router_arguments(outcome_parser)
    verify_router_parser = subparsers.add_parser("verify-router")
    _add_router_arguments(verify_router_parser)
    subparsers.add_parser("verify-peer")
    sandbox_parser = subparsers.add_parser("sandbox-relay", help=argparse.SUPPRESS)
    sandbox_parser.add_argument("--control-socket", type=Path, required=True)
    sandbox_parser.add_argument("--relay-port", type=int, required=True)
    sandbox_parser.add_argument("--model", required=True)
    sandbox_parser.add_argument("--title", required=True)
    sandbox_parser.add_argument("--prompt", required=True)
    args = parser.parse_args(argv)
    try:
        if args.mode == "route":
            route_phase(
                command=args.genus_router_command,
                config=args.genus_router_config,
                component_sha=args.genus_router_sha,
            )
            return 0
        if args.mode == "execute":
            result = execute_phase()
            return 0 if result["execution_status"] == "success" else 1
        if args.mode == "outcome":
            outcome_phase(
                command=args.genus_router_command,
                config=args.genus_router_config,
                component_sha=args.genus_router_sha,
            )
            return 0
        if args.mode == "verify-router":
            print(validate_router_component_identity(
                command=args.genus_router_command,
                config=args.genus_router_config,
                component_sha=args.genus_router_sha,
            ))
            return 0
        if args.mode == "verify-peer":
            _manifest, identity = validate_litellm_peer_manifest()
            print(identity)
            return 0
        if args.mode == "sandbox-relay":
            return sandbox_relay_phase(args.control_socket, args.relay_port, args.model, args.title, args.prompt)
        raise SpikeError("mode-invalid")
    except SpikeError as error:
        print(f"OpenCode spike {args.mode} failed: {error.code}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
