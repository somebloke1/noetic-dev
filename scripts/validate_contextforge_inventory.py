#!/usr/bin/env python3
"""Validate the static ContextForge continuity inventory without probing live services."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "spec" / "infrastructure" / "contextforge-continuity.json"
DOC_PATH = ROOT / "docs" / "contextforge-continuity-inventory.md"
REVIEW_PATH = ROOT / "docs" / "contextforge-continuity-review.md"
SECRET_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?:sk-|xai-|hf_|tgp_v1_)[A-Za-z0-9_-]{16,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot load {path.relative_to(ROOT)}: {error}") from error


def main() -> int:
    try:
        inventory = load(INVENTORY_PATH)
        ensure(inventory["schema_version"] == "noetic.contextforge-continuity/v0", "inventory version drift")
        ensure(inventory["conclusion"] == "retain_operationally_not_architectural_backbone", "continuity conclusion drift")
        ensure(inventory["mutation_performed"] is False, "inventory falsely records a mutation")

        surfaces = {surface["surface"]: surface for surface in inventory["live_surfaces"]}
        ensure(set(surfaces) == {"host_live", "development_docker"}, "live/development surface coverage drift")
        ensure(surfaces["host_live"]["gateway"] != surfaces["development_docker"]["gateway"], "surfaces silently collapsed")
        ensure(surfaces["host_live"]["health_status"] == 200, "host health observation missing")
        ensure(surfaces["development_docker"]["isolation"] == "successor_test_surface_not_live_fallback", "development fallback rule weakened")

        consumers = {consumer["consumer"]: consumer for consumer in inventory["consumers"]}
        expected_consumers = {"pi_runtime", "opencode_runtime", "noetic_pi_project_state", "noetic_dev_current_session", "contextforge_operator_and_test_harness"}
        ensure(set(consumers) == expected_consumers, "consumer inventory drift")
        shared_six = {"chrome-devtools", "context7", "github", "mentality", "playwright", "web-search"}
        ensure(set(consumers["pi_runtime"]["services"]) == shared_six, "Pi service coverage drift")
        ensure(set(consumers["opencode_runtime"]["services"]) == shared_six, "OpenCode service coverage drift")
        ensure(any("Serena" in item or "serena" in item for item in consumers["pi_runtime"]["exceptions"]), "direct Serena exception omitted")
        ensure("recorded_project_binding_not_live_client_proof" == consumers["noetic_pi_project_state"]["attachment"], "historical state overstated")

        services = {service["service"]: service for service in inventory["host_services"]}
        expected_services = {"gateway", "mentality", "chrome-devtools", "ssh-tmux", "context7", "playwright", "exa-search", "github", "web-search", "serena-cf-controlplane"}
        ensure(set(services) == expected_services, "host service inventory drift")
        ensure(services["gateway"]["port"] == 4444, "host gateway port drift")
        ensure({services[name]["port"] for name in expected_services - {"gateway"}} == set(range(9100, 9109)), "host bridge port coverage drift")
        ensure(inventory["project_serena_units"]["active"] < inventory["project_serena_units"]["unit_files"], "inactive Serena unit omitted")

        auth = inventory["authentication"]
        ensure("ephemeral server-scoped token" in auth["pi_wrapper"], "wrapper token attenuation omitted")
        ensure(set(auth["wrapper_permissions"]) == {"servers.use", "tools.read", "tools.execute", "resources.read", "prompts.read"}, "wrapper permission drift")
        ensure("values not inspected" in auth["opencode"].lower(), "credential non-disclosure omitted")

        findings = {finding["id"]: finding for finding in inventory["findings"]}
        ensure(set(findings) == {"CF-001", "CF-002", "CF-003", "CF-004", "CF-005"}, "finding coverage drift")
        ensure(findings["CF-001"]["severity"] == "high" and "0664" in findings["CF-001"]["finding"], "credential permission finding weakened")
        ensure(findings["CF-005"]["severity"] == "high" and "shared gateway" in findings["CF-005"]["finding"], "blast-radius finding weakened")

        invariants = " ".join(inventory["continuity_invariants"]).lower()
        for phrase in ("do not stop", "development docker", "verified parity", "direct serena", "not the default", "no canonical-event"):
            ensure(phrase in invariants, f"continuity invariant missing: {phrase}")
        ensure(len(inventory["migration_gates"]) >= 6, "migration gates incomplete")
        gates = " ".join(inventory["migration_gates"]).lower()
        for phrase in ("hidden fallback", "tested rollback", "one independently reviewable", "authority"):
            ensure(phrase in gates, f"migration gate missing: {phrase}")

        document = DOC_PATH.read_text(encoding="utf-8").lower()
        for phrase in (
            "must remain operational", "no service, process", "explicit non-contextforge exception",
            "mode **0664**", "dirty", "single point", "not event-sink proof", "until those gates pass",
        ):
            ensure(phrase in document, f"inventory document omits {phrase!r}")
        ensure(REVIEW_PATH.is_file(), "missing adversarial continuity review")

        combined = INVENTORY_PATH.read_text(encoding="utf-8") + DOC_PATH.read_text(encoding="utf-8") + REVIEW_PATH.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            ensure(not pattern.search(combined), "credential-like value found in continuity artifacts")
    except (AssertionError, KeyError, TypeError, OSError) as error:
        print(f"ContextForge inventory validation failed: {error}", file=sys.stderr)
        return 1
    print("ContextForge continuity inventory validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
