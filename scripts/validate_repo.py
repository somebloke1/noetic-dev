#!/usr/bin/env python3
"""Dependency-free validation for noetic-dev's composition-root invariants."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "README.md",
    "AGENTS.md",
    "SYNTHESIS.md",
    "KNOWNS.md",
    "DECISIONS.md",
    "OPEN_QUESTIONS.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "docs/cognitive-backbone.md",
    "docs/development-practices.md",
    # Governance files (issue #23)
    "docs/governance/delivery-governance.md",
    "governance/state-machine.json",
    "governance/model-profiles.json",
    "governance/command-registry.json",
    "governance/issue-status.json",
    "governance/schemas/evidence-manifest.schema.json",
    "governance/schemas/command-registry.schema.json",
    "governance/schemas/issue-status.schema.json",
    "governance/schemas/model-profiles.schema.json",
    "governance/schemas/state-machine.schema.json",
    "governance/schemas/qa-execution-record.schema.json",
    "governance/schemas/qa-probe-record.schema.json",
    "governance/schemas/existing-work-freeze.schema.json",
    "governance/audits/README.md",
    "governance/audits/existing-work-freeze.json",
    "scripts/governance/__init__.py",
    "scripts/governance/hash_tree.py",
    "scripts/governance/json_schema.py",
    "scripts/governance/collect_evidence.py",
    "scripts/governance/check_evidence_manifest.py",
    "scripts/governance/check_delivery_gate.py",
    "scripts/governance/run_isolated_pi.py",
    "scripts/governance/agent_review_broker.py",
    "scripts/governance/request_agent_review.py",
    # Governance test files
    "tests/governance/__init__.py",
    "tests/governance/test_command_registry.py",
    "tests/governance/test_delivery_gate.py",
    "tests/governance/test_evidence_manifest.py",
    "tests/governance/test_state_machine.py",
    "tests/governance/test_workflow_pinning.py",
    "tests/governance/test_run_isolated_pi.py",
    "tests/governance/test_agent_review.py",
]
TEXT_SUFFIXES = {".md", ".py", ".yml", ".yaml", ".json", ".txt"}
FROZEN_PROVENANCE = {Path("initial-user-msg.md")}
LINK_RE = re.compile(r"\[[^\]]+\]\((?!https?://|mailto:|#)([^)]+)\)")
ANCHOR_RE = re.compile(r"governance-crud:(?:start|end) id=([a-z]+-[0-9-]+)")


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def main() -> int:
    failures: list[str] = []

    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            fail(f"missing required file: {relative}", failures)

    anchor_counts: dict[str, int] = {}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or ".git" in path.parts or path.suffix not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(ROOT)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if relative not in FROZEN_PROVENANCE and line.rstrip() != line:
                fail(f"{relative}:{number}: trailing whitespace", failures)
            if line.startswith(("<<<<<<<", "=======", ">>>>>>>")):
                fail(f"{relative}:{number}: unresolved merge marker", failures)
        if path.suffix == ".md":
            for target in LINK_RE.findall(text):
                clean = target.split("#", 1)[0]
                if not clean:
                    continue
                resolved = (path.parent / clean).resolve()
                if ROOT not in resolved.parents and resolved != ROOT:
                    fail(f"{relative}: local link escapes repository: {target}", failures)
                elif not resolved.exists():
                    fail(f"{relative}: broken local link: {target}", failures)
        for anchor in ANCHOR_RE.findall(text):
            anchor_counts[anchor] = anchor_counts.get(anchor, 0) + 1

    for anchor, count in anchor_counts.items():
        if count != 2:
            fail(f"governance anchor {anchor!r} occurs {count} times; expected start+end", failures)

    for json_path in sorted((ROOT / "governance").rglob("*.json")):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(f"{json_path.relative_to(ROOT)}: invalid JSON: {exc}", failures)
            continue
        schema_ref = data.get("$schema") if isinstance(data, dict) else None
        if schema_ref and schema_ref.startswith(("./", "../")):
            schema_path = (json_path.parent / schema_ref).resolve()
            if ROOT not in schema_path.parents and schema_path != ROOT:
                fail(f"{json_path.relative_to(ROOT)}: schema reference escapes repository: {schema_ref}", failures)
            elif not schema_path.exists():
                fail(f"{json_path.relative_to(ROOT)}: missing referenced schema: {schema_ref}", failures)

    if failures:
        print("Repository validation failed:", file=sys.stderr)
        for item in failures:
            print(f"- {item}", file=sys.stderr)
        return 1

    print(f"Repository validation passed ({len(REQUIRED)} required files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
