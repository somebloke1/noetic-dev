#!/usr/bin/env python3
"""Capture bounded GraphQL evidence for the candidate D2 inventory."""

from __future__ import annotations

import argparse
import base64
import contextlib
import gzip
import hashlib
import json
import math
import os
import pwd
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.governance.hash_tree import canonical_json_sha256  # noqa: E402
from scripts.governance.json_schema import (  # noqa: E402
    load_json_strict,
    parse_json_strict,
    validate_schema,
)


REPOSITORY = "somebloke1/noetic-dev"
REPOSITORY_ID = 1297462728
AUTHORIZED_REPAIR_PR = 67
AUTHORIZED_REPAIR_HEAD = "issue-32-canonical-roadmap"
AUTHORIZED_REPAIR_BASE = "dev"
PULL_URL = re.compile(r"https://github\.com/somebloke1/noetic-dev/pull/([1-9][0-9]*)\Z")
ISSUE_URL = re.compile(r"https://github\.com/somebloke1/noetic-dev/issues/([1-9][0-9]*)\Z")
GRAPHQL_URL = "https://api.github.com/graphql"
GH_BINARY = "/usr/bin/gh"
PYTHON_BINARY = "/usr/bin/python3"
LOCK_HELPER = """import fcntl
import os
import sys

directory = os.open(sys.argv[1], os.O_RDONLY | os.O_DIRECTORY)
fcntl.flock(directory, fcntl.LOCK_EX)
os.write(1, b"1")
os.read(0, 1)
"""
UNADJUDICATED_DISPOSITION = "unadjudicated candidate capture"
REQUIRED_PR_DISPOSITIONS = {
    66: "paused bounded experiment; non-evidence for roadmap readiness; leave issue and PR untouched",
    67: "active bounded D2 roadmap candidate",
}
REQUIRED_BRANCH_DISPOSITIONS = {
    "dev": "protected autonomous integration branch",
    "issue-11-cognitive-programs": "retain donor without PR",
    "issue-27-terra-canary": "preserve stale canary and dirty material",
    "issue-29-broker-lifecycle-evidence": "retain model-governance evidence",
    "issue-29-modality-evidence-record": "retain model-governance evidence",
    "issue-29-modality-readiness": "retain model-governance evidence",
    "issue-29-routed-governance-remediation": "retain remediation donor",
    "issue-29-routed-pi-recovery": "retain closed-PR donor",
    "issue-32-canonical-roadmap": "active bounded D2 roadmap candidate",
    "issue-65-opencode-spike": "paused bounded experiment; leave untouched",
    "main": "protected release branch; user-approved promotion only",
}
ALLOWED_DISPOSITIONS = frozenset(
    {
        UNADJUDICATED_DISPOSITION,
        *REQUIRED_PR_DISPOSITIONS.values(),
        *REQUIRED_BRANCH_DISPOSITIONS.values(),
    }
)
VARIABLES = {"owner": "somebloke1", "name": "noetic-dev"}
REPOSITORY_FIELDS = """
  databaseId
  nameWithOwner
  defaultBranchRef { name target { oid } }
"""
QUERIES = {
    "principal": """
query D2Principal {
  viewer { databaseId login }
}
""",
    "open_pull_requests": f"""
query D2OpenPullRequests($owner: String!, $name: String!) {{
  repository(owner: $owner, name: $name) {{
    {REPOSITORY_FIELDS}
    pullRequests(states: OPEN, first: 100, orderBy: {{field: CREATED_AT, direction: ASC}}) {{
      totalCount
      pageInfo {{ hasNextPage endCursor }}
      nodes {{ number title baseRefName headRefName headRefOid updatedAt url }}
    }}
  }}
}}
""",
    "branches": f"""
query D2Branches($owner: String!, $name: String!) {{
  repository(owner: $owner, name: $name) {{
    {REPOSITORY_FIELDS}
    refs(refPrefix: "refs/heads/", first: 100, orderBy: {{field: ALPHABETICAL, direction: ASC}}) {{
      totalCount
      pageInfo {{ hasNextPage endCursor }}
      nodes {{ name target {{ oid }} }}
    }}
  }}
}}
""",
    "open_issues": f"""
query D2OpenIssues($owner: String!, $name: String!) {{
  repository(owner: $owner, name: $name) {{
    {REPOSITORY_FIELDS}
    issues(states: OPEN, first: 100, orderBy: {{field: CREATED_AT, direction: ASC}}) {{
      totalCount
      pageInfo {{ hasNextPage endCursor }}
      nodes {{
        number
        title
        updatedAt
        url
        labels(first: 100) {{
          totalCount
          pageInfo {{ hasNextPage endCursor }}
          nodes {{ name }}
        }}
      }}
    }}
  }}
}}
""",
}
OPERATIONS = {
    "principal": "D2Principal",
    "open_pull_requests": "D2OpenPullRequests",
    "branches": "D2Branches",
    "open_issues": "D2OpenIssues",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _github_environment() -> dict[str, str]:
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    return {
        "HOME": str(home),
        "GH_CONFIG_DIR": str(home / ".config/gh"),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "NO_COLOR": "1",
    }


def _normalize_external_json(value: Any) -> Any:
    """Copy only exact JSON built-ins; reject subclasses and non-finite values."""
    value_type = type(value)
    if value is None or value_type in {bool, int, str}:
        return value
    if value_type is float:
        if not math.isfinite(value):
            raise ValueError("non-finite external JSON number")
        return value
    if value_type is list:
        return [_normalize_external_json(item) for item in value]
    if value_type is dict:
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("external JSON object key is not a string")
            normalized[key] = _normalize_external_json(item)
        return normalized
    raise ValueError(f"unsupported external JSON type: {value_type.__name__}")


def _parse_included_response(raw: bytes) -> tuple[int, dict[str, str], bytes, Any]:
    separator = b"\r\n\r\n" if b"\r\n\r\n" in raw else b"\n\n"
    try:
        header_block, body = raw.split(separator, 1)
    except ValueError as exc:
        raise RuntimeError("gh api response did not contain an HTTP envelope") from exc
    header_lines = header_block.decode("utf-8").splitlines()
    if not header_lines or not header_lines[0].startswith("HTTP/"):
        raise RuntimeError("gh api response did not begin with an HTTP status")
    try:
        status = int(header_lines[0].split()[1])
    except (IndexError, ValueError) as exc:
        raise RuntimeError("gh api response status was malformed") from exc
    headers: dict[str, str] = {}
    for line in header_lines[1:]:
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()
    try:
        response = _normalize_external_json(parse_json_strict(body))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("gh api response body was not strict JSON") from exc
    return status, headers, body, response


def _graphql(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    query = QUERIES[name].strip() + "\n"
    operation = OPERATIONS[name]
    variables = {} if name == "principal" else VARIABLES
    argv = [GH_BINARY, "api", "--include", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        argv.extend(["-F", f"{key}={value}"])
    try:
        result = subprocess.run(
            argv,
            executable=GH_BINARY,
            cwd=ROOT,
            env=_github_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("trusted GitHub CLI execution failed") from exc
    if result.returncode != 0:
        raise RuntimeError("authenticated gh api GraphQL request failed")
    status, headers, raw_body, response = _parse_included_response(result.stdout)
    if status != 200 or type(response) is not dict or type(response.get("data")) is not dict:
        raise RuntimeError("GitHub GraphQL returned an unexpected response")
    if response.get("errors"):
        raise RuntimeError("GitHub GraphQL returned errors")
    request_id = headers.get("x-github-request-id", "")
    if not request_id:
        raise RuntimeError("GitHub response omitted X-GitHub-Request-Id")
    envelope: dict[str, Any] = {
        "request_url": GRAPHQL_URL,
        "request": {
            "method": "POST",
            "operation_name": operation,
            "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
            "variables": variables,
            "variables_sha256": canonical_json_sha256(variables),
        },
        "status": status,
        "request_id": request_id,
        "fetched_at": _now(),
        "repository": REPOSITORY,
        "repository_id": REPOSITORY_ID,
        "authentication": {
            "method": "gh-cli-oauth-token",
            "principal": "somebloke1",
            "candidate_authenticated": True,
            "protected_verified": False,
        },
        "response_headers": {
            "date": headers.get("date", ""),
        },
        "body_sha256": hashlib.sha256(raw_body).hexdigest(),
        "canonical_response_sha256": canonical_json_sha256(response),
        "response_gzip_base64": base64.b64encode(
            gzip.compress(raw_body, compresslevel=9, mtime=0)
        ).decode("ascii"),
    }
    envelope["response_sha256"] = canonical_json_sha256(envelope)
    return envelope, response["data"]


def _graphql_after(
    name: str, previous_date: datetime | None
) -> tuple[dict[str, Any], dict[str, Any], datetime]:
    for attempt in range(4):
        if attempt:
            time.sleep(1.05)
        envelope, data = _graphql(name)
        response_date = parsedate_to_datetime(envelope["response_headers"]["date"])
        if previous_date is None or response_date > previous_date:
            return envelope, data, response_date
    raise RuntimeError("GitHub response Date did not advance strictly")


def _with_pagination(
    envelope: dict[str, Any], connection: dict[str, Any]
) -> dict[str, Any]:
    nodes = connection.get("nodes")
    page_info = connection.get("pageInfo")
    if type(nodes) is not list or type(page_info) is not dict:
        raise RuntimeError("GitHub GraphQL connection was malformed")
    if (
        page_info.get("hasNextPage") is not False
        or type(connection.get("totalCount")) is not int
    ):
        raise RuntimeError("D2 inventory exceeds its single complete GraphQL page")
    if type(connection.get("totalCount")) is not int or connection["totalCount"] != len(nodes):
        raise RuntimeError("GitHub GraphQL connection count is incomplete")
    envelope["pagination"] = {
        "first": 100,
        "item_count": len(nodes),
        "total_count": connection["totalCount"],
        "has_next_page": False,
        "end_cursor": page_info.get("endCursor"),
    }
    envelope["response_sha256"] = canonical_json_sha256(
        {key: value for key, value in envelope.items() if key != "response_sha256"}
    )
    return envelope


def _validate_derived_snapshot(
    pulls: list[dict[str, Any]], branches: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    try:
        pulls = _normalize_external_json(pulls)
        branches = _normalize_external_json(branches)
    except ValueError as error:
        raise RuntimeError("D2 snapshot is not strict JSON") from error
    if type(pulls) is not list or type(branches) is not list:
        raise RuntimeError("D2 snapshot collections are invalid")
    if any(type(item) is not dict for item in [*pulls, *branches]):
        raise RuntimeError("D2 snapshot contains non-object identities")
    branch_names = [item.get("name") for item in branches]
    if (
        any(type(name) is not str or not name for name in branch_names)
        or len(set(branch_names)) != len(branch_names)
        or any(
            re.fullmatch(r"[a-f0-9]{40}", item.get("sha", "")) is None
            for item in branches
        )
    ):
        raise RuntimeError("D2 branch inventory contains invalid or duplicate identities")
    pull_numbers = [item.get("number") for item in pulls]
    if (
        any(type(number) is not int for number in pull_numbers)
        or len(set(pull_numbers)) != len(pull_numbers)
        or any(
            type(item.get(field)) is not str or not item[field]
            for item in pulls
            for field in ("title", "base", "head", "head_sha", "updated_at", "url")
        )
        or any(
            re.fullmatch(r"[a-f0-9]{40}", item["head_sha"]) is None
            for item in pulls
        )
        or any(
            PULL_URL.fullmatch(item["url"]) is None
            or int(PULL_URL.fullmatch(item["url"]).group(1)) != item["number"]
            for item in pulls
        )
    ):
        raise RuntimeError("D2 pull-request inventory contains invalid or duplicate identities")
    repair = [item for item in pulls if item["number"] == AUTHORIZED_REPAIR_PR]
    if (
        len(repair) != 1
        or repair[0]["head"] != AUTHORIZED_REPAIR_HEAD
        or repair[0]["base"] != AUTHORIZED_REPAIR_BASE
    ):
        raise RuntimeError("bounded D2 repair pull request identity changed")
    branch_by_name = {item["name"]: item for item in branches}
    for pull_request in pulls:
        branch = branch_by_name.get(pull_request["head"])
        if branch is None or branch["sha"] != pull_request["head_sha"]:
            raise RuntimeError(
                f"PR {pull_request['number']} head changed during portfolio capture"
            )
    return branch_by_name


def _validate_derived_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        issues = _normalize_external_json(issues)
    except ValueError as error:
        raise RuntimeError("D2 issue snapshot is not strict JSON") from error
    if type(issues) is not list or any(type(item) is not dict for item in issues):
        raise RuntimeError("D2 issue snapshot contains invalid identities")
    numbers = [item.get("number") for item in issues]
    if (
        any(type(number) is not int for number in numbers)
        or len(set(numbers)) != len(numbers)
        or any(
            type(item.get(field)) is not str or not item[field]
            for item in issues
            for field in ("title", "status", "updated_at", "url")
        )
        or any(
            type(item.get("labels")) is not list
            or any(type(label) is not str for label in item["labels"])
            for item in issues
        )
        or any(
            ISSUE_URL.fullmatch(item["url"]) is None
            or int(ISSUE_URL.fullmatch(item["url"]).group(1)) != item["number"]
            for item in issues
        )
    ):
        raise RuntimeError("D2 issue snapshot contains invalid or duplicate identities")
    return issues


def _status_from_labels(labels: list[str]) -> str:
    status_labels = [label for label in labels if label.startswith("status:")]
    return status_labels[0].removeprefix("status:") if len(status_labels) == 1 else "missing"


def _annotation_maps(previous: dict[str, Any]) -> tuple[dict[int, str], dict[str, str]]:
    pr_annotations = {
        item["number"]: item.get("governance_disposition", item.get("disposition", ""))
        for item in previous.get("open_pull_requests", [])
        if type(item) is dict and type(item.get("number")) is int
        and item.get("governance_disposition", item.get("disposition", ""))
        in ALLOWED_DISPOSITIONS
    }
    branch_annotations = {
        item["name"]: item.get("governance_disposition", item.get("disposition", ""))
        for item in previous.get("branches", [])
        if type(item) is dict and type(item.get("name")) is str
        and item.get("governance_disposition", item.get("disposition", ""))
        in ALLOWED_DISPOSITIONS
    }
    pr_annotations.update(REQUIRED_PR_DISPOSITIONS)
    branch_annotations.update(REQUIRED_BRANCH_DISPOSITIONS)
    return pr_annotations, branch_annotations


def _repository(data: dict[str, Any]) -> dict[str, Any]:
    repository = data.get("repository")
    default = repository.get("defaultBranchRef") if type(repository) is dict else None
    target = default.get("target") if type(default) is dict else None
    if (
        type(repository) is not dict
        or repository.get("databaseId") != REPOSITORY_ID
        or repository.get("nameWithOwner") != REPOSITORY
        or type(default) is not dict
        or default.get("name") != "dev"
        or type(target) is not dict
        or type(target.get("oid")) is not str
        or re.fullmatch(r"[a-f0-9]{40}", target["oid"]) is None
    ):
        raise RuntimeError("GitHub GraphQL omitted repository identity")
    return repository


def capture(previous: dict[str, Any]) -> dict[str, Any]:
    try:
        previous = _normalize_external_json(previous)
    except ValueError as error:
        raise RuntimeError("previous D2 inventory is not strict JSON") from error
    if type(previous) is not dict:
        raise RuntimeError("previous D2 inventory must be an object")
    started_at = _now()
    principal_envelope, principal_data, principal_date = _graphql_after(
        "principal", None
    )
    pulls_envelope, pulls_data, pulls_date = _graphql_after(
        "open_pull_requests", principal_date
    )
    branches_envelope, branches_data, branches_date = _graphql_after(
        "branches", pulls_date
    )
    issues_envelope, issues_data, _issues_date = _graphql_after(
        "open_issues", branches_date
    )
    completed_at = _now()

    try:
        principal_envelope = _normalize_external_json(principal_envelope)
        principal_data = _normalize_external_json(principal_data)
        pulls_envelope = _normalize_external_json(pulls_envelope)
        pulls_data = _normalize_external_json(pulls_data)
        branches_envelope = _normalize_external_json(branches_envelope)
        branches_data = _normalize_external_json(branches_data)
        issues_envelope = _normalize_external_json(issues_envelope)
        issues_data = _normalize_external_json(issues_data)
    except ValueError as error:
        raise RuntimeError("GraphQL inventory response is not strict JSON") from error

    viewer = principal_data.get("viewer") if type(principal_data) is dict else None
    if type(viewer) is not dict or viewer.get("login") != "somebloke1":
        raise RuntimeError("authenticated gh principal is not the repository owner")
    pull_repository = _repository(pulls_data)
    branch_repository = _repository(branches_data)
    issue_repository = _repository(issues_data)
    repositories = (pull_repository, branch_repository, issue_repository)
    default_heads = {
        repository["defaultBranchRef"]["target"]["oid"]
        for repository in repositories
    }
    if len(default_heads) != 1:
        raise RuntimeError("default branch changed during portfolio capture")

    pulls_connection = pull_repository.get("pullRequests")
    branches_connection = branch_repository.get("refs")
    issues_connection = issue_repository.get("issues")
    if any(
        type(connection) is not dict
        for connection in (pulls_connection, branches_connection, issues_connection)
    ):
        raise RuntimeError("GraphQL inventory response omitted a connection")
    _with_pagination(pulls_envelope, pulls_connection)
    _with_pagination(branches_envelope, branches_connection)
    _with_pagination(issues_envelope, issues_connection)

    pr_annotations, branch_annotations = _annotation_maps(previous)
    pull_items = pulls_connection["nodes"]
    branch_items = branches_connection["nodes"]
    issue_items = issues_connection["nodes"]
    if any(
        type(item) is not dict
        or set(item)
        != {
            "number",
            "title",
            "baseRefName",
            "headRefName",
            "headRefOid",
            "updatedAt",
            "url",
        }
        for item in pull_items
    ):
        raise RuntimeError("pull-request inventory contains a malformed node")
    if any(
        type(item) is not dict
        or set(item) != {"name", "target"}
        or type(item.get("target")) is not dict
        or set(item["target"]) != {"oid"}
        for item in branch_items
    ):
        raise RuntimeError("branch inventory contains a malformed node")
    derived_pulls = [
        {
            "number": item["number"],
            "title": item["title"],
            "base": item["baseRefName"],
            "head": item["headRefName"],
            "head_sha": item["headRefOid"],
            "updated_at": item["updatedAt"],
            "url": item["url"],
            "governance_disposition": pr_annotations.get(
                item["number"], UNADJUDICATED_DISPOSITION
            ),
        }
        for item in pull_items
    ]
    derived_branches = [
        {
            "name": item["name"],
            "sha": item["target"]["oid"],
            "governance_disposition": branch_annotations.get(
                item["name"], UNADJUDICATED_DISPOSITION
            ),
        }
        for item in branch_items
    ]
    derived_branch_by_name = _validate_derived_snapshot(
        derived_pulls, derived_branches
    )
    if derived_branch_by_name.get("dev", {}).get("sha") not in default_heads:
        raise RuntimeError("default branch target disagrees with dev branch inventory")
    derived_pulls.sort(key=lambda item: item["number"])
    derived_branches.sort(key=lambda item: item["name"])
    derived_issues = []
    for item in issue_items:
        if type(item) is not dict:
            raise RuntimeError("issue inventory contains a non-object node")
        labels_connection = item.get("labels")
        if (
            type(labels_connection) is not dict
            or type(labels_connection.get("pageInfo")) is not dict
            or type(labels_connection.get("nodes")) is not list
            or set(item) != {"number", "title", "updatedAt", "url", "labels"}
            or type(item.get("number")) is not int
            or any(
                type(item.get(field)) is not str or not item[field]
                for field in ("title", "updatedAt", "url")
            )
            or set(labels_connection) != {"totalCount", "pageInfo", "nodes"}
            or set(labels_connection["pageInfo"]) != {"hasNextPage", "endCursor"}
            or labels_connection["pageInfo"]["hasNextPage"] is not False
            or type(labels_connection.get("totalCount")) is not int
            or labels_connection["totalCount"] != len(labels_connection["nodes"])
            or any(
                type(label) is not dict
                or set(label) != {"name"}
                or type(label["name"]) is not str
                for label in labels_connection["nodes"]
            )
        ):
            raise RuntimeError(f"issue {item.get('number')} label inventory is incomplete")
        labels = [label["name"] for label in labels_connection["nodes"]]
        derived_issues.append(
            {
                "number": item["number"],
                "title": item["title"],
                "labels": labels,
                "status": _status_from_labels(labels),
                "updated_at": item["updatedAt"],
                "url": item["url"],
            }
        )
    derived_issues = _validate_derived_issues(derived_issues)
    derived_issues.sort(key=lambda item: item["number"])

    source_envelopes = {
        "principal": principal_envelope,
        "open_pull_requests": pulls_envelope,
        "branches": branches_envelope,
        "open_issues": issues_envelope,
    }
    required_claims = {
        "repository": REPOSITORY,
        "repository_id": REPOSITORY_ID,
        "capture_started_at": started_at,
        "capture_completed_at": completed_at,
        "response_sha256": {
            name: envelope["response_sha256"]
            for name, envelope in source_envelopes.items()
        },
        "body_sha256": {
            name: envelope["body_sha256"]
            for name, envelope in source_envelopes.items()
        },
    }
    default_branch = branch_repository["defaultBranchRef"]
    return {
        "$schema": "../../schemas/d2-portfolio-audit.schema.json",
        "schema_version": "2",
        "repository": {
            "id": REPOSITORY_ID,
            "full_name": REPOSITORY,
            "default_branch": default_branch["name"],
        },
        "captured_at": completed_at,
        "capture": {
            "started_at": started_at,
            "completed_at": completed_at,
            "collector": "scripts/governance/capture_d2_inventory.py",
            "source_envelopes": source_envelopes,
        },
        "verification": {
            "status": "pending_protected_receipt",
            "required_source": "protected-integration",
            "required_claims_sha256": canonical_json_sha256(required_claims),
            "required_claims": required_claims,
        },
        "refs": {
            "main": derived_branch_by_name["main"]["sha"],
            "dev": derived_branch_by_name["dev"]["sha"],
            "default_branch": default_branch["name"],
        },
        "counts": {
            "open_pull_requests": len(derived_pulls),
            "branches": len(derived_branches),
            "open_issues": len(derived_issues),
        },
        "open_pull_requests": derived_pulls,
        "branches": derived_branches,
        "open_issues": derived_issues,
        "review": {
            "method": "one protected independent adversarial review against the exact D2 candidate and required receipt claims",
            "evidence_location": "protected Agent Review artifact for pull request 67",
            "required_before_inventory_completion": True,
        },
    }


def _inventory_residue_prefix(output: Path) -> str:
    name_digest = hashlib.sha256(os.fsencode(output.name)).hexdigest()
    return f".d2-inventory-{name_digest}."


def _inventory_residues(output: Path) -> list[Path]:
    prefix = _inventory_residue_prefix(output)
    return sorted(
        entry
        for entry in output.parent.iterdir()
        if entry.name.startswith(prefix) and entry.name.endswith(".tmp")
    )


def _display_paths(paths: list[Path]) -> str:
    return ", ".join(repr(str(path)) for path in paths)


@contextlib.contextmanager
def _directory_lock(directory: Path):
    process = subprocess.Popen(
        [PYTHON_BINARY, "-I", "-S", "-c", LOCK_HELPER, str(directory)],
        executable=PYTHON_BINARY,
        cwd="/",
        env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    try:
        if process.stdout is None or process.stdout.read(1) != b"1":
            raise RuntimeError("D2 inventory directory lock failed")
        yield
    finally:
        if process.poll() is None:
            released = False
            if process.stdin is not None:
                try:
                    process.stdin.write(b"1")
                    process.stdin.flush()
                    released = True
                except Exception:
                    pass
            if not released:
                try:
                    process.terminate()
                except Exception:
                    pass
            try:
                process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                    process.wait(timeout=5)
                except Exception:
                    pass
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        for stream in (process.stdin, process.stdout):
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass


def _write_inventory_locked(output: Path, inventory: dict[str, Any]) -> str:
    residues = _inventory_residues(output)
    if residues:
        raise RuntimeError(
            "existing D2 inventory temporary residue requires cleanup: "
            f"{_display_paths(residues)}"
        )
    payload = (json.dumps(inventory, indent=2, ensure_ascii=True) + "\n").encode(
        "utf-8"
    )
    digest = hashlib.sha256(payload).hexdigest()
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=_inventory_residue_prefix(output), suffix=".tmp", dir=output.parent
    )
    temporary = Path(temporary_name)
    try:
        try:
            handle = os.fdopen(descriptor, "wb")
            descriptor = -1
            with handle:
                os.fchmod(handle.fileno(), 0o644)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if temporary.read_bytes() != payload:
            raise OSError("temporary D2 inventory verification failed")
        try:
            os.replace(temporary, output)
        except Exception:
            try:
                committed = not temporary.exists() and output.read_bytes() == payload
            except OSError:
                committed = False
            if not committed:
                raise
    except Exception as original:
        cleanup_error: OSError | None = None
        for _attempt in range(3):
            try:
                temporary.unlink(missing_ok=True)
                cleanup_error = None
                break
            except OSError as exc:
                cleanup_error = exc
        if cleanup_error is not None:
            raise RuntimeError(
                f"D2 inventory write failed ({original}); temporary residue "
                f"requires cleanup: {_display_paths([temporary])}"
            ) from cleanup_error
        raise
    return digest


def _write_inventory_atomic(output: Path, inventory: dict[str, Any]) -> str:
    with _directory_lock(output.parent):
        return _write_inventory_locked(output, inventory)


def _capture_and_write(output: Path) -> str:
    with _directory_lock(output.parent):
        previous = load_json_strict(output) if output.exists() else {}
        inventory = capture(previous)
        schema = load_json_strict(
            ROOT / "governance/schemas/d2-portfolio-audit.schema.json"
        )
        if validate_schema(inventory, schema):
            raise RuntimeError("captured D2 inventory failed schema validation")
        return _write_inventory_locked(output, inventory)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "governance/audits/20260718-d2-portfolio/inventory.json",
    )
    args = parser.parse_args()
    try:
        digest = _capture_and_write(args.output)
    except Exception as exc:
        try:
            print(f"D2 inventory capture failed: {exc}", file=sys.stderr)
        except Exception:
            pass
        return 1
    try:
        print(digest)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
