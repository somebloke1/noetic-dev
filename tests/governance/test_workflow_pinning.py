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


def workflow_job_blocks(content: str) -> dict[str, str]:
    """Extract top-level job bodies from the repository's workflow subset."""
    lines = content.splitlines(keepends=True)
    jobs_start = lines.index("jobs:\n")
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines[jobs_start + 1 :]:
        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            current = line.strip()[:-1]
            blocks[current] = [line]
        elif current is not None:
            blocks[current].append(line)
    return {name: "".join(body) for name, body in blocks.items()}


def ci_workflow_errors(content: str) -> list[str]:
    jobs = workflow_job_blocks(content)
    errors: list[str] = []
    expected = {"validate", "tests", "post-merge-validation"}
    if set(jobs) != expected:
        errors.append("CI job set must be exactly validate, tests, and post-merge-validation")
        return errors
    if "run: python3 scripts/validate_repo.py" not in jobs["validate"]:
        errors.append("validate job must run repository validation")
    if "python3 -m unittest" in jobs["validate"]:
        errors.append("validate job must not run the test suite")
    if "needs: [validate]" not in jobs["tests"]:
        errors.append("tests job must depend on validate")
    if "run: python3 -m unittest discover -s tests -v" not in jobs["tests"]:
        errors.append("tests job must run the genuine test suite")
    if "scripts/validate_repo.py" in jobs["tests"]:
        errors.append("tests job must not substitute repository validation")
    post_merge = jobs["post-merge-validation"]
    validation = post_merge.find("run: python3 scripts/validate_repo.py")
    tests = post_merge.find("run: python3 -m unittest discover -s tests -v")
    if validation < 0 or tests < 0 or validation >= tests:
        errors.append("branch validation must run repository validation before tests")
    if "--check-pinning-only" in content or "test_workflow_pinning" in content:
        errors.append("workflow pinning must not be restored as a CI gate")
    return errors


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

    def test_ci_workflow_does_not_gate_on_bootstrap_or_trust_root(self):
        content = (WORKFLOWS_DIR / "governance.yml").read_text()
        self.assertNotIn("policy/scripts/governance", content)
        self.assertNotIn("--check-bootstrap-blocked", content)
        self.assertNotIn("--check-pinning-only", content)
        self.assertNotIn("external integration", content.lower())
        self.assertNotIn("  workflow-pinning:", content)
        self.assertNotIn("test_workflow_pinning", content)

    def test_ci_requires_validation_before_genuine_tests(self):
        content = (WORKFLOWS_DIR / "governance.yml").read_text()
        self.assertEqual([], ci_workflow_errors(content))

    def test_ci_graph_regressions_are_rejected(self):
        content = (WORKFLOWS_DIR / "governance.yml").read_text()
        validation = "run: python3 scripts/validate_repo.py"
        tests = "run: python3 -m unittest discover -s tests -v"
        variants = {
            "missing_dependency": content.replace("    needs: [validate]\n", ""),
            "swapped_commands": content.replace(validation, "COMMAND_A").replace(tests, validation).replace("COMMAND_A", tests),
            "renamed_pinning_gate": content.replace(
                "  post-merge-validation:\n",
                "  assurance-check:\n    runs-on: ubuntu-latest\n    steps:\n      - run: python3 -m unittest tests.governance.test_workflow_pinning\n\n  post-merge-validation:\n",
            ),
        }
        for name, candidate in variants.items():
            with self.subTest(name=name):
                self.assertTrue(ci_workflow_errors(candidate))

    def test_validator_checkout_does_not_persist_credentials(self):
        content = (WORKFLOWS_DIR / "governance.yml").read_text()
        validator = content.index("Validate repository contracts")
        checkout = content.rindex("uses: actions/checkout@", 0, validator)
        self.assertIn("persist-credentials: false", content[checkout:validator])
        self.assertNotIn("Validate worktree administration", content)

    def test_dev_runs_normal_ci_without_protection_claims(self):
        governance = (WORKFLOWS_DIR / "governance.yml").read_text()
        self.assertIn("branches: [main, dev]", governance)
        self.assertIn("github.ref == 'refs/heads/dev'", governance)
        self.assertNotIn("protected branch", governance.lower())
        self.assertNotIn("bootstrap honesty", governance.lower())


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
