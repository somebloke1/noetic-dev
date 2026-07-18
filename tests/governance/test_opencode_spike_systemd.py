"""Static deployment contracts for the inert OpenCode spike."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SYSTEMD = ROOT / "deploy" / "systemd"


class TestOpenCodeSpikeDeployment(unittest.TestCase):
    def setUp(self) -> None:
        self.route = (SYSTEMD / "noetic-dev-opencode-spike-route.service").read_text(encoding="utf-8")
        self.execute = (SYSTEMD / "noetic-dev-opencode-spike-execute.service").read_text(encoding="utf-8")
        self.outcome = (SYSTEMD / "noetic-dev-opencode-spike-outcome.service").read_text(encoding="utf-8")

    def test_only_execute_process_receives_the_systemd_credential(self):
        self.assertNotIn("LoadCredential=", self.route)
        self.assertNotIn("LoadCredential=", self.outcome)
        self.assertIn("LoadCredential=litellm_api_key", self.execute)
        for unit in (self.route, self.outcome):
            self.assertIn("InaccessiblePaths=-/etc/credstore -/run/credentials", unit)
            self.assertIn("IPAddressDeny=any", unit)
            self.assertIn("RestrictAddressFamilies=AF_UNIX", unit)
            self.assertIn("UnsetEnvironment=CREDENTIALS_DIRECTORY LITELLM_API_KEY", unit)
            self.assertIn("BindPaths=/var/lib/noetic-opencode-spike/router-state:", unit)
        self.assertIn("IPAddressDeny=any", self.execute)
        self.assertIn("IPAddressAllow=127.0.0.0/8", self.execute)
        self.assertIn("IPAddressAllow=172.22.10.160/32", self.execute)
        self.assertIn("RestrictAddressFamilies=AF_UNIX AF_INET", self.execute)

    def test_route_execute_and_outcome_are_distinct_hardened_processes(self):
        self.assertIn("run_opencode_spike.py route ", self.route)
        self.assertIn("run_opencode_spike.py execute", self.execute)
        self.assertIn("run_opencode_spike.py outcome ", self.outcome)
        for unit in (self.route, self.execute, self.outcome):
            self.assertIn("Type=oneshot", unit)
            self.assertIn("NoNewPrivileges=true", unit)
            self.assertIn("PrivateTmp=true", unit)
            self.assertIn("ProtectSystem=strict", unit)
            self.assertIn("CapabilityBoundingSet=", unit)
            self.assertIn("KillMode=control-group", unit)
            self.assertNotIn("[Install]", unit)
        self.assertIn("Before=noetic-dev-opencode-spike-execute.service", self.route)
        self.assertIn("Before=noetic-dev-opencode-spike-outcome.service", self.execute)

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

    def test_root_orchestrator_is_serial_irreversible_and_reports_execute_failure(self):
        script = (ROOT / "deploy" / "run-opencode-spike.sh").read_text(encoding="utf-8")
        self.assertIn('test "$(id -u)" -eq 0', script)
        self.assertIn("/usr/bin/flock -n 9", script)
        self.assertIn("existing state blocks replay", script)
        self.assertIn("OpenCode spike router state blocks replay", script)
        route = script.index('/usr/bin/systemctl start "$route_unit"')
        execute = script.index('/usr/bin/systemctl start "$execute_unit"')
        outcome = script.index('/usr/bin/systemctl start "$outcome_unit"')
        self.assertLess(route, execute)
        self.assertLess(execute, outcome)
        self.assertIn('start "$execute_unit" || execute_status=$?', script)
        self.assertIn('start "$outcome_unit" || outcome_status=$?', script)
        self.assertIn('"$state/route.json" "$execute_state/route.json"', script)
        self.assertIn('"$execute_state/result.json" "$state/result.json"', script)
        self.assertNotIn("rm -rf", script)
        completed = subprocess.run(["/bin/sh", "-n", str(ROOT / "deploy" / "run-opencode-spike.sh")], check=False)
        self.assertEqual(completed.returncode, 0)

    def test_installer_is_exact_sha_inert_and_does_not_read_a_token(self):
        path = ROOT / "deploy" / "install-opencode-spike.sh"
        installer = path.read_text(encoding="utf-8")
        self.assertIn("373af49ceba30c1b64e964463a64f8065103f942f240933a955f6c461e1a67f6", installer)
        self.assertIn("f2b839b0cfc737c4c1f0a46d3d519d414529545c", installer)
        self.assertIn('git -C "$noetic_source" archive "$noetic_sha"', installer)
        self.assertIn('install -o root -g root -m 0555 "$opencode_source" "$staged_opencode"', installer)
        self.assertIn('"$staged_opencode" --version', installer)
        self.assertIn('install -o root -g root -m 0555 "$staged_opencode" "$opencode_runtime/opencode"', installer)
        self.assertIn('"$archive/scripts/governance/genus_router_mcp.py" "$runtime/genus_router_mcp.py"', installer)
        self.assertIn("router_client_sha256", installer)
        self.assertIn("verify-router", installer)
        self.assertIn("router_identity_sha256", installer)
        self.assertIn("litellm-peer-manifest.json", installer)
        self.assertIn("verify-peer", installer)
        self.assertIn("litellm_peer_identity_sha256", installer)
        self.assertIn("litellm_peer_manifest_sha256", installer)
        self.assertIn("find /opt/litellm/.venv -xdev", installer)
        self.assertIn("useradd --system --gid noetic-opencode-spike", installer)
        self.assertIn('router_state=$spike_home/router-state', installer)
        self.assertIn('execute_state=$spike_home/execute-state', installer)
        self.assertIn('install -o root -g root -m 0700', installer)
        self.assertIn("systemctl daemon-reload", installer)
        self.assertNotIn("systemctl start", installer)
        self.assertNotIn("systemctl restart", installer)
        self.assertNotIn("systemctl enable", installer)
        self.assertNotIn("cat /etc/credstore", installer)
        completed = subprocess.run(["/bin/bash", "-n", str(path)], check=False)
        self.assertEqual(completed.returncode, 0)

    def test_policy_and_docs_remain_explicitly_non_evidence(self):
        policy = json.loads((ROOT / "config" / "opencode-session-policy.json").read_text(encoding="utf-8"))
        self.assertFalse(policy["runtime_adapter_ready"])
        self.assertEqual(policy["status"], "contract-only")
        docs = (ROOT / "docs" / "governance" / "opencode-credential-isolation-spike.md").read_text(encoding="utf-8")
        self.assertIn("does not execute the turn", docs)
        self.assertIn("evidence_class=non-evidence", docs)
        self.assertIn("route-policy-order-conflict", docs)
        self.assertIn("route-model-order-invalid", docs)
        self.assertIn("does not reinterpret the repository's standard-model set", docs)
        self.assertIn("must not be rerun outside the network-unshared sandbox", docs)


if __name__ == "__main__":
    unittest.main()
