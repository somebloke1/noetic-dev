#!/usr/bin/env python3
"""Add the active protected-branch ruleset snapshot to route evidence."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from json_schema import load_json_strict
from route_evidence import github_json, protected_ci_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    payload = load_json_strict(args.evidence)
    if type(payload) is not dict or payload.get("repository") != "somebloke1/noetic-dev":
        parser.error("evidence wrapper is invalid")
    run = github_json(f"repos/somebloke1/noetic-dev/actions/runs/{args.run_id}")
    applied_rules = github_json("repos/somebloke1/noetic-dev/rules/branches/dev")
    if not isinstance(applied_rules, list) or any(
        not isinstance(rule, dict)
        or type(rule.get("ruleset_id")) is not int
        or not isinstance(rule.get("type"), str)
        for rule in applied_rules
    ):
        parser.error("applicable protected-CI rules are invalid")
    ruleset_ids = sorted({rule["ruleset_id"] for rule in applied_rules})
    if (
        len(ruleset_ids) != 1
        or len(applied_rules) != 4
        or {rule["type"] for rule in applied_rules}
        != {"deletion", "non_fast_forward", "pull_request", "required_status_checks"}
    ):
        parser.error("exactly one applicable protected-CI ruleset is required")
    snapshots = []
    for ruleset_id in ruleset_ids:
        ruleset = github_json(f"repos/somebloke1/noetic-dev/rulesets/{ruleset_id}")
        snapshot = protected_ci_snapshot(args.run_id, run, applied_rules, ruleset)
        if snapshot is not None:
            snapshots.append(snapshot)
    if len(snapshots) != 1:
        parser.error("exactly one applicable protected-CI ruleset is required")
    payload["protected_ci"] = snapshots[0]
    descriptor, temporary = tempfile.mkstemp(prefix="protected-ci-", dir=args.evidence.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, args.evidence)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
