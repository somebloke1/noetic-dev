"""Static deployment-contract tests for the local review services."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UNITS = ROOT / "deploy" / "systemd"


class TestAgentReviewSystemd(unittest.TestCase):
    def test_production_socket_is_canonical(self):
        paths = [
            ROOT / ".github" / "workflows" / "agent-review.yml",
            ROOT / "scripts" / "governance" / "agent_review_broker.py",
            ROOT / "scripts" / "governance" / "request_agent_review.py",
        ]
        for path in paths:
            with self.subTest(path=path):
                content = path.read_text()
                self.assertIn("/run/noetic-dev/agent-review.sock", content)
                self.assertNotIn("/run/user/1000/noetic-dev-agent-review.sock", content)

    def test_broker_uses_immutable_release_and_dedicated_identity(self):
        unit = (UNITS / "noetic-dev-agent-review-broker.service").read_text()
        self.assertIn("User=noetic-review-broker", unit)
        self.assertIn("Group=noetic-agent-review", unit)
        self.assertIn("WorkingDirectory=/opt/noetic-dev-agent-review/current", unit)
        self.assertIn("/run/noetic-dev/agent-review.sock", unit)
        self.assertIn("HOME=/var/lib/noetic-agent-review", unit)
        self.assertIn("ProtectHome=true", unit)
        self.assertIn("runtime/mcp/bin/python3", unit)
        self.assertIn("f2b839b0cfc737c4c1f0a46d3d519d414529545c/bin/genus-router", unit)
        self.assertIn("--genus-router-sha f2b839b0cfc737c4c1f0a46d3d519d414529545c", unit)
        self.assertIn("LoadCredential=litellm_api_key", unit)
        self.assertIn("f2b839b0cfc737c4c1f0a46d3d519d414529545c/state", unit)
        self.assertNotIn("/home/dgk", unit)

    def test_mcp_client_dependency_is_exactly_pinned(self):
        requirements = (ROOT / "deploy" / "requirements-agent-review.txt").read_text().splitlines()
        self.assertEqual(requirements, ["mcp==1.28.1"])

    def test_runner_cannot_reach_broker_credentials(self):
        unit = (UNITS / "noetic-dev-actions-runner.service").read_text()
        self.assertIn("User=noetic-github-runner", unit)
        self.assertIn("SupplementaryGroups=noetic-agent-review", unit)
        self.assertIn("WorkingDirectory=/var/lib/noetic-dev-runner/actions-runner", unit)
        self.assertIn("HOME=/var/lib/noetic-dev-runner/home", unit)
        self.assertIn("InaccessiblePaths=/var/lib/noetic-agent-review /home/dgk", unit)
        self.assertIn("ExecStart=/var/lib/noetic-dev-runner/actions-runner/bin/runsvc.sh", unit)
        self.assertIn("KillMode=process", unit)
        self.assertIn("KillSignal=SIGTERM", unit)
        self.assertIn("TimeoutStopSec=5min", unit)
        self.assertNotIn("/var/tmp", unit)


if __name__ == "__main__":
    unittest.main()
