#!/usr/bin/env python3
"""Capture bounded GraphQL evidence for the candidate D2 inventory."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.governance.hash_tree import canonical_json_sha256  # noqa: E402
from scripts.governance.json_schema import load_json_strict  # noqa: E402


REPOSITORY = "somebloke1/noetic-dev"
REPOSITORY_ID = 1297462728
GRAPHQL_URL = "https://api.github.com/graphql"
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
        response = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("gh api response body was not JSON") from exc
    return status, headers, body, response


def _graphql(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    query = QUERIES[name].strip() + "\n"
    operation = OPERATIONS[name]
    variables = {} if name == "principal" else VARIABLES
    argv = ["gh", "api", "--include", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        argv.extend(["-F", f"{key}={value}"])
    result = subprocess.run(
        argv,
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
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
    if page_info.get("hasNextPage") is not False:
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


def _status_from_labels(labels: list[str]) -> str:
    status_labels = [label for label in labels if label.startswith("status:")]
    return status_labels[0].removeprefix("status:") if len(status_labels) == 1 else "missing"


def _annotation_maps(previous: dict[str, Any]) -> tuple[dict[int, str], dict[str, str]]:
    pr_annotations = {
        item["number"]: item.get("governance_disposition", item.get("disposition", ""))
        for item in previous.get("open_pull_requests", [])
        if type(item) is dict and type(item.get("number")) is int
    }
    branch_annotations = {
        item["name"]: item.get("governance_disposition", item.get("disposition", ""))
        for item in previous.get("branches", [])
        if type(item) is dict and type(item.get("name")) is str
    }
    pr_annotations.setdefault(67, "active bounded D2 roadmap candidate")
    return pr_annotations, branch_annotations


def _repository(data: dict[str, Any]) -> dict[str, Any]:
    repository = data.get("repository")
    if type(repository) is not dict:
        raise RuntimeError("GitHub GraphQL omitted repository identity")
    return repository


def capture(previous: dict[str, Any]) -> dict[str, Any]:
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

    viewer = principal_data.get("viewer")
    if type(viewer) is not dict or viewer.get("login") != "somebloke1":
        raise RuntimeError("authenticated gh principal is not the repository owner")
    pull_repository = _repository(pulls_data)
    branch_repository = _repository(branches_data)
    issue_repository = _repository(issues_data)
    repositories = (pull_repository, branch_repository, issue_repository)
    if any(
        repository.get("databaseId") != REPOSITORY_ID
        or repository.get("nameWithOwner") != REPOSITORY
        or repository.get("defaultBranchRef", {}).get("name") != "dev"
        for repository in repositories
    ):
        raise RuntimeError("GraphQL inventory response repository identity changed")

    pulls_connection = pull_repository["pullRequests"]
    branches_connection = branch_repository["refs"]
    issues_connection = issue_repository["issues"]
    _with_pagination(pulls_envelope, pulls_connection)
    _with_pagination(branches_envelope, branches_connection)
    _with_pagination(issues_envelope, issues_connection)

    pr_annotations, branch_annotations = _annotation_maps(previous)
    pull_items = sorted(pulls_connection["nodes"], key=lambda item: item["number"])
    branch_items = sorted(branches_connection["nodes"], key=lambda item: item["name"])
    issue_items = sorted(issues_connection["nodes"], key=lambda item: item["number"])
    branch_by_name = {item["name"]: item for item in branch_items}

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
                item["number"], "unadjudicated candidate capture"
            ),
        }
        for item in pull_items
    ]
    derived_branches = [
        {
            "name": item["name"],
            "sha": item["target"]["oid"],
            "governance_disposition": branch_annotations.get(
                item["name"], "unadjudicated candidate capture"
            ),
        }
        for item in branch_items
    ]
    derived_issues = []
    for item in issue_items:
        labels_connection = item["labels"]
        if (
            labels_connection["pageInfo"]["hasNextPage"] is not False
            or type(labels_connection.get("totalCount")) is not int
            or labels_connection["totalCount"] != len(labels_connection["nodes"])
        ):
            raise RuntimeError(f"issue {item['number']} label inventory is incomplete")
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
            "main": branch_by_name["main"]["target"]["oid"],
            "dev": branch_by_name["dev"]["target"]["oid"],
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "governance/audits/20260718-d2-portfolio/inventory.json",
    )
    args = parser.parse_args()
    previous = load_json_strict(args.output) if args.output.exists() else {}
    inventory = capture(previous)
    args.output.write_text(
        json.dumps(inventory, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(hashlib.sha256(args.output.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
