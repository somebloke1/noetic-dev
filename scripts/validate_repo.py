#!/usr/bin/env python3
"""Dependency-free validation for noetic-dev's composition-root invariants."""

from __future__ import annotations

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
    "docs/controller-stage-a-test-plan.md",
    "docs/controller-contracts-review.md",
    "scripts/validate_controller_specs.py",
    "spec/controller/v0/README.md",
    "spec/controller/v0/command-envelope.schema.json",
    "spec/controller/v0/event-envelope.schema.json",
    "spec/controller/v0/program-graph.schema.json",
    "spec/controller/v0/authority-matrix.json",
    "spec/controller/v0/transition-tables.json",
    "docs/cognitional-event-contract.md",
    "docs/cognitional-event-review.md",
    "scripts/validate_event_specs.py",
    "spec/events/v0/cognitional-event.schema.json",
    "spec/events/v0/sink-receipt.schema.json",
    "spec/events/v0/event-class-matrix.json",
    "docs/telos-delegation-contract.md",
    "docs/telos-delegation-review.md",
    "scripts/validate_telos_specs.py",
    "spec/telos/v0/delegation.schema.json",
    "spec/telos/v0/delegation-result.schema.json",
    "spec/telos/v0/delegation-transitions.json",
    "spec/telos/v0/controller-binding.json",
    "docs/contextforge-continuity-inventory.md",
    "docs/contextforge-continuity-review.md",
    "scripts/validate_contextforge_inventory.py",
    "spec/infrastructure/contextforge-continuity.json",
    "docs/model-selection-access-contract.md",
    "docs/model-selection-access-review.md",
    "scripts/validate_model_specs.py",
    "spec/models/v0/endpoint-registry.schema.json",
    "spec/models/v0/selection-record.schema.json",
    "docs/attach-adapter-contract.md",
    "docs/attach-adapter-review.md",
    "scripts/validate_attach_specs.py",
    "spec/attach/v0/attach-session.schema.json",
    "spec/attach/v0/adapter-profiles.json",
    "spec/attach/v0/examples/valid-tmux.json",
    "spec/attach/v0/examples/valid-browser-observe.json",
    "spec/attach/v0/examples/invalid-sessions.json",
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

    if failures:
        print("Repository validation failed:", file=sys.stderr)
        for item in failures:
            print(f"- {item}", file=sys.stderr)
        return 1

    print(f"Repository validation passed ({len(REQUIRED)} required files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
