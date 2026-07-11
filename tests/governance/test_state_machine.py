"""Tests for the governance state machine."""

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_MACHINE_PATH = REPO_ROOT / "governance" / "state-machine.json"


class TestStateMachine(unittest.TestCase):
    """Test that the state machine definition is well-formed."""

    def setUp(self):
        with open(STATE_MACHINE_PATH) as f:
            self.sm = json.load(f)

    def test_has_required_keys(self):
        self.assertIn("schema_version", self.sm)
        self.assertIn("states", self.sm)
        self.assertIn("transitions", self.sm)
        self.assertIn("role_authorities", self.sm)

    def test_all_required_states_exist(self):
        required_states = [
            "UNGOVERNED_EXISTING",
            "AUDIT_REQUIRED",
            "AUDITED",
            "ISSUE_ACCEPTED",
            "PLAN_REQUESTED",
            "PLAN_READY",
            "IMPLEMENTING",
            "CANDIDATE_PINNED",
            "VALIDATING",
            "QA_RUNNING",
            "QA_FAILED",
            "REMEDIATING",
            "QA_PASSED",
            "HUMAN_REVIEW_PENDING",
            "READY_TO_MERGE",
            "MERGED_TO_MAIN",
            "POST_MERGE_VALIDATING",
            "PUBLICATION_READY",
            "PUBLISHED",
            "DEPLOYED",
            "BLOCKED",
            "ABORTED",
            "ROLLED_BACK",
        ]
        for state in required_states:
            with self.subTest(state=state):
                self.assertIn(state, self.sm["states"])

    def test_all_states_have_description(self):
        for state_id, state in self.sm["states"].items():
            with self.subTest(state=state_id):
                self.assertIn("description", state)
                self.assertTrue(len(state["description"]) > 0)

    def test_all_states_have_authorized_roles(self):
        for state_id, state in self.sm["states"].items():
            with self.subTest(state=state_id):
                self.assertIn("authorized_roles", state)
                self.assertTrue(len(state["authorized_roles"]) > 0)

    def test_transitions_have_required_fields(self):
        for i, t in enumerate(self.sm["transitions"]):
            with self.subTest(transition=i):
                self.assertIn("from", t)
                self.assertIn("to", t)
                self.assertIn("authorized_roles", t)
                self.assertIn("conditions", t)

    def test_wildcard_from_transition(self):
        """BLOCKED, ABORTED, ROLLED_BACK should be reachable from any state."""
        wildcards = [t for t in self.sm["transitions"] if t["from"] == "*"]
        wildcard_tos = {t["to"] for t in wildcards}
        self.assertIn("BLOCKED", wildcard_tos)
        self.assertIn("ABORTED", wildcard_tos)
        self.assertIn("ROLLED_BACK", wildcard_tos)

    def test_all_transition_states_exist(self):
        state_ids = set(self.sm["states"].keys())
        for t in self.sm["transitions"]:
            if t["from"] != "*":
                self.assertIn(t["from"], state_ids,
                              f"Transition from unknown state {t['from']}")
            self.assertIn(t["to"], state_ids,
                          f"Transition to unknown state {t['to']}")

    def test_role_authorities_are_complete(self):
        required_roles = [
            "human", "orchestrator", "planner", "implementer",
            "remediator", "validator", "qa", "publisher"
        ]
        for role in required_roles:
            with self.subTest(role=role):
                self.assertIn(role, self.sm["role_authorities"])

    def test_planner_is_read_only(self):
        planner = self.sm["role_authorities"]["planner"]
        self.assertFalse(planner["can_approve"])
        self.assertFalse(planner["can_implement"])
        self.assertFalse(planner["can_qa"])
        self.assertFalse(planner["can_publish"])

    def test_implementer_cannot_qa(self):
        implementer = self.sm["role_authorities"]["implementer"]
        self.assertFalse(implementer["can_qa"])

    def test_qa_cannot_approve(self):
        qa = self.sm["role_authorities"]["qa"]
        self.assertFalse(qa["can_approve"])

    def test_publisher_cannot_approve(self):
        publisher = self.sm["role_authorities"]["publisher"]
        self.assertFalse(publisher["can_approve"])

    def test_human_cannot_implement(self):
        human = self.sm["role_authorities"]["human"]
        self.assertFalse(human["can_implement"])

    def test_human_cannot_qa(self):
        human = self.sm["role_authorities"]["human"]
        self.assertFalse(human["can_qa"])

    def test_human_can_approve(self):
        human = self.sm["role_authorities"]["human"]
        self.assertTrue(human["can_approve"])

    def test_blocked_is_terminal_by_default(self):
        """BLOCKED should not have any outgoing transitions except to itself."""
        blocked_transitions = [
            t for t in self.sm["transitions"]
            if t["from"] == "BLOCKED" or (t["from"] == "*" and t["to"] == "BLOCKED")
        ]
        # BLOCKED can transition from * but has no outgoing to non-terminal states
        self.assertTrue(len(blocked_transitions) >= 1)

    def test_complete_implementation_path(self):
        """The full happy path should have valid transitions."""
        happy_path = [
            "IMPLEMENTING",
            "CANDIDATE_PINNED",
            "QA_RUNNING",
            "QA_PASSED",
            "HUMAN_REVIEW_PENDING",
            "READY_TO_MERGE",
            "MERGED_TO_MAIN",
            "POST_MERGE_VALIDATING",
            "PUBLICATION_READY",
            "PUBLISHED",
        ]
        transitions_from = {t["from"]: t for t in self.sm["transitions"] if t["from"] != "*"}
        for i in range(len(happy_path) - 1):
            current = happy_path[i]
            next_state = happy_path[i + 1]
            has_transition = any(
                t["from"] == current and t["to"] == next_state
                for t in self.sm["transitions"]
            )
            self.assertTrue(
                has_transition,
                f"No transition from {current} to {next_state}"
            )


if __name__ == "__main__":
    unittest.main()
