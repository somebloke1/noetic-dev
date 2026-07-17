#!/usr/bin/env python3
"""Add the protected-base ruleset declaration to route evidence."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from json_schema import load_json_strict
from route_evidence import protected_ci_snapshot


def policy_is_canonical(policy: object) -> bool:
    if (
        type(policy) is not dict
        or policy.get("schema_version") != "1"
        or type(policy.get("ruleset")) is not dict
        or type(policy.get("applied_rules")) is not list
    ):
        return False
    ruleset = policy["ruleset"]
    ruleset_id = ruleset.get("id")
    if type(ruleset_id) is not int:
        return False
    applied = [
        {**rule, "ruleset_id": ruleset_id}
        for rule in policy["applied_rules"]
        if isinstance(rule, dict)
    ]
    runtime_ruleset = {
        **ruleset,
        "created_at": "2000-01-01T00:00:00Z",
        "updated_at": "2000-01-01T00:00:00Z",
    }
    return protected_ci_snapshot(
        1, {"created_at": "2000-01-01T00:00:01Z"}, applied, runtime_ruleset
    ) == policy


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    args = parser.parse_args()
    payload = load_json_strict(args.evidence)
    if type(payload) is not dict or payload.get("repository") != "somebloke1/noetic-dev":
        parser.error("evidence wrapper is invalid")
    policy = load_json_strict(args.policy)
    if not policy_is_canonical(policy):
        parser.error("protected-CI policy declaration is invalid")
    payload["protected_ci"] = policy
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
