"""Static deployment contracts for the inert OpenCode spike."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SYSTEMD = ROOT / "deploy" / "systemd"


class TestOpenCodeSpikeDeployment(unittest.TestCase):
    def setUp(self) -> None:
        self.route = (SYSTEMD / "noetic-dev-opencode-spike-route.service").read_text(encoding="utf-8")
        self.execute = (SYSTEMD / "noetic-dev-opencode-spike-execute.service").read_text(encoding="utf-8")
        self.outcome = (SYSTEMD / "noetic-dev-opencode-spike-outcome.service").read_text(encoding="utf-8")
        self.installer = (ROOT / "deploy" / "install-opencode-spike.sh").read_text(encoding="utf-8")
        self.orchestrator = (ROOT / "deploy" / "run-opencode-spike.sh").read_text(encoding="utf-8")

    def test_only_execute_process_receives_the_systemd_credential(self):
        self.assertNotIn("LoadCredential=", self.route)
        self.assertNotIn("LoadCredential=", self.outcome)
        self.assertIn("LoadCredential=litellm_api_key", self.execute)
        for unit in (self.route, self.outcome):
            self.assertIn("InaccessiblePaths=-/etc/credstore -/run/credentials", unit)
            self.assertIn("IPAddressDeny=any", unit)
            self.assertIn("RestrictAddressFamilies=AF_UNIX", unit)
            self.assertIn("UnsetEnvironment=CREDENTIALS_DIRECTORY LITELLM_API_KEY", unit)
            self.assertIn("BindPaths=/var/lib/noetic-opencode-spike/non-evidence-router-state:", unit)
        self.assertIn("IPAddressDeny=any", self.execute)
        self.assertIn("IPAddressAllow=127.0.0.0/8", self.execute)
        self.assertIn("IPAddressAllow=172.22.10.160/32", self.execute)
        self.assertIn("RestrictAddressFamilies=AF_UNIX AF_INET", self.execute)

    def test_units_pin_runtime_router_and_state_paths(self):
        component = "f2b839b0cfc737c4c1f0a46d3d519d414529545c"
        for unit in (self.route, self.outcome):
            self.assertIn(f"genus-router/{component}/bin/genus-router", unit)
            self.assertIn(f"--genus-router-sha {component}", unit)
        for unit in (self.route, self.execute, self.outcome):
            self.assertIn("/opt/noetic-dev-agent-review/opencode-spike-runtime/run_opencode_spike.py", unit)
            self.assertNotIn("User=noetic-review-broker", unit)
        for unit in (self.route, self.outcome):
            self.assertIn("User=noetic-opencode-spike", unit)
            self.assertIn("Group=noetic-opencode-spike", unit)
            self.assertIn("/var/lib/noetic-opencode-spike/state", unit)
        self.assertIn("User=llm-svc", self.execute)
        self.assertIn("Group=llm-svc", self.execute)
        self.assertIn("/var/lib/noetic-opencode-spike/execute-state", self.execute)
        for unit in (self.execute, self.outcome):
            self.assertIn("ReadOnlyPaths=/var/lib/noetic-opencode-spike/handoff-state", unit)

    def test_router_state_has_a_root_owned_non_evidence_classifier(self):
        self.assertIn('"storage_scope":"isolated-spike-only"', self.installer)
        self.assertIn('install -d -o root -g root -m 0755 "$router_state"', self.installer)
        self.assertIn('install -d -o root -g root -m 0755 "$handoff_state"', self.installer)
        self.assertIn('chmod 0444 "$router_state/classification.json"', self.installer)

    def test_root_handoff_is_exclusive_no_follow_and_never_installs_into_service_state(self):
        self.assertNotIn("/usr/bin/install -o", self.orchestrator)
        self.assertIn("iflag=nofollow,nonblock,fullblock", self.orchestrator)
        self.assertIn("oflag=excl,nofollow", self.orchestrator)

    def test_installation_requires_protected_exact_revision_and_runtime_binding(self):
        self.assertIn("https://github.com/somebloke1/noetic-dev.git", self.installer)
        self.assertIn("$root/current/scripts/governance/route_attestation.py", self.installer)
        self.assertIn("protected-review-receipt.json", self.installer)
        self.assertIn("verify-runtime", self.installer)

if __name__ == "__main__":
    unittest.main()
