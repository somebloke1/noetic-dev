"""Tests for workflow action pinning."""

import json
import unittest
from pathlib import Path

import sys
GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)
from check_delivery_gate import check_pinning


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


class TestWorkflowPinning(unittest.TestCase):
    """Test that GitHub Actions workflows use pinned SHA refs."""

    def test_governance_workflow_is_pinned(self):
        path = WORKFLOWS_DIR / "governance.yml"
        self.assertTrue(path.exists(), "governance.yml not found")
        errors = check_pinning(str(path))
        if errors:
            self.fail(f"Pinning errors found: {errors}")

    def test_all_workflows_are_pinned(self):
        """Check all workflow files for pinning compliance."""
        all_passed = True
        all_errors = []
        for wf in sorted(WORKFLOWS_DIR.glob("*.yml")):
            errors = check_pinning(str(wf))
            if errors:
                all_passed = False
                all_errors.extend(errors)
        if not all_passed:
            self.fail(f"Pinning errors found: {all_errors}")

    def test_no_mutable_tags_in_governance_workflow(self):
        """Specifically check for @v4, @v5 style tags."""
        content = (WORKFLOWS_DIR / "governance.yml").read_text()
        import re
        # Find all uses: patterns
        for match in re.finditer(r"uses:\s+([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)@(\S+)", content):
            action = match.group(1)
            ref = match.group(2)
            # Skip actions/refs that aren't in our repo
            if action.startswith(".") or action.startswith("docker://"):
                continue
            if re.match(r"^v?\d+(\.\d+)*$", ref):
                self.fail(f"Mutable tag found: {action}@{ref}")

    def test_candidate_workflow_does_not_call_base_policy_gate(self):
        content = (WORKFLOWS_DIR / "governance.yml").read_text()
        self.assertNotIn("policy/scripts/governance", content)
        self.assertIn("--check-bootstrap-blocked", content)
        self.assertIn("advisory", content.lower())

    def test_protected_dev_triggers_governance_and_agent_review(self):
        governance = (WORKFLOWS_DIR / "governance.yml").read_text()
        agent_review = (WORKFLOWS_DIR / "agent-review.yml").read_text()
        self.assertIn("branches: [main, dev]", governance)
        self.assertIn("github.ref == 'refs/heads/dev'", governance)
        self.assertIn("branches: [main, dev]", agent_review)
        self.assertIn("--run-url", agent_review)


class TestPinningChecker(unittest.TestCase):
    """Test the pinning checker itself using synthetic workflows."""

    def test_pinned_sha_detected(self):
        content = """
jobs:
  test:
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
"""
        path = Path("/tmp/test_pinned.yml")
        path.write_text(content)
        try:
            errors = check_pinning(str(path))
            self.assertEqual(errors, [])
        finally:
            path.unlink(missing_ok=True)

    def test_mutable_tag_rejected(self):
        content = """
jobs:
  test:
    steps:
      - uses: actions/checkout@v4
"""
        path = Path("/tmp/test_mutable.yml")
        path.write_text(content)
        try:
            errors = check_pinning(str(path))
            self.assertTrue(len(errors) > 0)
            self.assertTrue(any("unpinned" in e for e in errors))
        finally:
            path.unlink(missing_ok=True)

    def test_pinned_and_mixed(self):
        content = """
jobs:
  test:
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
      - uses: actions/setup-python@v5
"""
        path = Path("/tmp/test_mixed.yml")
        path.write_text(content)
        try:
            errors = check_pinning(str(path))
            self.assertTrue(len(errors) > 0)
        finally:
            path.unlink(missing_ok=True)

    def test_short_sha_rejected(self):
        content = """
jobs:
  test:
    steps:
      - uses: actions/checkout@34e11487
"""
        path = Path("/tmp/test_short.yml")
        path.write_text(content)
        try:
            errors = check_pinning(str(path))
            self.assertTrue(len(errors) > 0)
            self.assertTrue(any("unpinned" in e for e in errors))
        finally:
            path.unlink(missing_ok=True)

    def test_job_container_tag_rejected(self):
        content = """
jobs:
  test:
    container: python:3.12
    steps:
      - run: python --version
"""
        path = Path("/tmp/test_container.yml")
        path.write_text(content)
        try:
            errors = check_pinning(str(path))
            self.assertTrue(any("job container" in e and "unpinned" in e for e in errors), errors)
        finally:
            path.unlink(missing_ok=True)

    def test_service_image_tag_rejected(self):
        content = """
jobs:
  test:
    services:
      postgres:
        image: postgres:16
    steps:
      - run: echo ok
"""
        path = Path("/tmp/test_service.yml")
        path.write_text(content)
        try:
            errors = check_pinning(str(path))
            self.assertTrue(any("service" in e and "unpinned" in e for e in errors), errors)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
