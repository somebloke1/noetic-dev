#!/usr/bin/env python3
"""Dependency-free validation for noetic-dev's composition-root invariants."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.governance.json_schema import load_json_strict, validate_schema

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
    # Provider-free M0 Telos-to-adjudication reference trace (issue #33)
    "docs/m0-telos-adjudication-trace.md",
    "spec/m0/v0/telos-adjudication-trace.schema.json",
    "spec/m0/v0/trace-contract.json",
    "spec/m0/v0/golden/valid-telos-adjudication-trace.json",
    "spec/m0/v0/golden/expected-projection.json",
    "scripts/m0_trace.py",
    "tests/m0/__init__.py",
    "tests/m0/test_telos_adjudication_trace.py",
    # Provider-free fixed M1 bounded recoverability reference trace (issue #35)
    "docs/m1-telos-recoverability-trace.md",
    "spec/m1/v0/telos-recoverability-trace.schema.json",
    "spec/m1/v0/trace-contract.json",
    "spec/m1/v0/golden/valid-telos-recoverability-trace.json",
    "spec/m1/v0/golden/expected-projection.json",
    "scripts/m1_trace.py",
    "tests/m1/__init__.py",
    "tests/m1/test_telos_recoverability_trace.py",
    # Provider-free development.verified-change/v1 program adapter (issue #37)
    "docs/development-verified-change-v1.md",
    "spec/programs/development.verified-change/v1/program-contract.json",
    "spec/programs/development.verified-change/v1/development-verified-change-packet.schema.json",
    "spec/programs/development.verified-change/v1/golden/valid-bounded-remediation-packet.json",
    "spec/programs/development.verified-change/v1/golden/expected-projection.json",
    "scripts/development_verified_change.py",
    "tests/programs/__init__.py",
    "tests/programs/test_development_verified_change.py",
    # Provider-free terminal observability read model (issue #39)
    "docs/development-verified-change-terminal-observability-v1.md",
    "spec/programs/development.verified-change/v1/terminal-observability-contract.json",
    "spec/programs/development.verified-change/v1/golden/expected-terminal-observability.json",
    "scripts/development_verified_change_observe.py",
    "tests/programs/test_development_verified_change_observe.py",
    # Provider-free terminal status explanation read model (issue #41)
    "docs/development-verified-change-terminal-status-v1.md",
    "spec/programs/development.verified-change/v1/terminal-status-contract.json",
    "spec/programs/development.verified-change/v1/golden/expected-terminal-status.json",
    "scripts/development_verified_change_status.py",
    "tests/programs/test_development_verified_change_status.py",
    # Mandatory genus-router / LiteLLM model policy (issue #29)
    "config/model-policy.json",
    "config/opencode-session-policy.json",
    "docs/model-routing-policy.md",
    "governance/schemas/model-policy.schema.json",
    "governance/schemas/opencode-session-policy.schema.json",
    "governance/schemas/route-evidence.schema.json",
    "tests/governance/test_model_policy.py",
    "tests/governance/test_opencode_session_policy.py",
    "tests/governance/test_route_evidence.py",
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
    "scripts/governance/genus_router_mcp.py",
    "scripts/governance/request_agent_review.py",
    "scripts/governance/request_agent_review.py",
    "scripts/governance/route_evidence.py",
    "deploy/install-agent-review.sh",
    "deploy/requirements-agent-review.txt",
    "deploy/requirements-agent-review.lock",
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

    policy_path = ROOT / "config/model-policy.json"
    schema_path = ROOT / "governance/schemas/model-policy.schema.json"
    try:
        policy = load_json_strict(policy_path)
        schema = load_json_strict(schema_path)
    except (OSError, ValueError) as exc:
        fail(f"model policy validation failed to load: {exc}", failures)
    else:
        for error in validate_schema(policy, schema):
            fail(f"config/model-policy.json: {error}", failures)

    opencode_policy_path = ROOT / "config/opencode-session-policy.json"
    opencode_schema_path = ROOT / "governance/schemas/opencode-session-policy.schema.json"
    try:
        opencode_policy = load_json_strict(opencode_policy_path)
        opencode_schema = load_json_strict(opencode_schema_path)
    except (OSError, ValueError) as exc:
        fail(f"opencode session policy validation failed to load: {exc}", failures)
    else:
        for error in validate_schema(opencode_policy, opencode_schema):
            fail(f"config/opencode-session-policy.json: {error}", failures)

    if failures:
        print("Repository validation failed:", file=sys.stderr)
        for item in failures:
            print(f"- {item}", file=sys.stderr)
        return 1

    print(f"Repository validation passed ({len(REQUIRED)} required files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
