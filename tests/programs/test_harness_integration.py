"""Implementation checks: genuine Telos/core SQLite, fixture actors, no model calls or QA claim."""

from contextlib import closing, redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import noetic
from scripts import noetic_controller as controller
from scripts import noetic_harness as harness
from scripts import noetic_run as runtime
from scripts import noetic_telos as telos
from tests.programs import test_noetic_harness as harness_fixtures
from tests.programs import test_noetic_telos as telos_fixtures


class HarnessIntegrationTests(unittest.TestCase):
    bundled = False

    @classmethod
    def setUpClass(cls):
        # Reuse the real source/relocated-bundle availability setup, not its tests.
        telos_fixtures.TelosRunTests.setUpClass.__func__(cls)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        subprocess.run(["git", "init", str(self.workspace)], check=True, capture_output=True)
        self.db = self.root / "telos.sqlite3"
        self.aggregate = telos.create_goal("Preserve the master purpose, not just this task", self.db, self.source)
        self.chain = self.aggregate["chain"]["chainId"]
        self.task = "  Deliver the bounded task\nKeep the run association stable.\n"
        guard = patch.object(harness, "actor_command", side_effect=AssertionError("No live actors in integration tests"))
        guard.start()
        self.addCleanup(guard.stop)

    def start(self, pattern="cognition", **kwargs):
        options = {"verify": [sys.executable, "-c", "pass"]} if pattern == "development" else {}
        options.update(kwargs)
        with redirect_stdout(io.StringIO()):
            return harness.start(pattern, self.task, self.workspace, self.root / "runs",
                                 telos_chain=self.chain, telos_db=self.db, telos_source=self.source, **options)

    def status(self, run):
        return runtime.project(runtime.read_events(run))

    def aggregate_now(self):
        return telos.get_goal(self.chain, self.db, self.source)

    def test_all_phase_bindings_frozen_snapshot_and_distinct_completion_boundaries(self):
        canonical = {name: (controller.PATTERN_DIR / f"{name}.json").read_bytes()
                     for name in ("development", "cognition")}
        for pattern, boundary, count in (("development", "four_phase_qa_completion", 10),
                                          ("cognition", "responsible_cognitive_completion", 6)):
            calls = []

            def actor(run, state, options):
                activation = state["activations"][state["current_activation"]]
                link = self.status(run)["telos"]
                if not calls:
                    subgoal = next(goal for goal in self.aggregate_now()["subGoals"]
                                   if goal["subGoalId"] == link["subgoal_id"])
                    self.assertEqual(subgoal["status"], "active")
                    self.assertEqual(subgoal["objective"], f"noetic run {run.name}\n{self.task}".strip())
                self.assertEqual(state["purpose"], self.task)
                bindings = activation["input_bindings"]
                governing = state["artifacts"][bindings["external.governing"]]
                self.assertNotEqual(bindings["external.purpose"], governing["id"])
                self.assertEqual(governing["content"]["primary_goal"], self.aggregate["chain"]["primaryGoal"])
                self.assertEqual(governing["content"]["essential_principles"],
                                 self.aggregate["reproductiveClause"]["essentialPrinciples"])
                self.assertTrue(governing["content"]["essential_principles"])
                self.assertIn(json.dumps(governing["content"]["primary_goal"]), harness.actor_prompt(run, state))
                calls.append(activation)
                if activation["mode"] == "review" and activation["phase"] == "implementation" and not activation["generation"]:
                    return harness_fixtures.response_for(state, harness_fixtures.result_for(state, "fail"))
                if activation["phase"] == "P2" and not state["returns_used"]:
                    return harness_fixtures.response_for(state, {
                        "outcome": "return", "target": "P1", "reason": "Missing observation",
                        "question": "Which source supports this?", "content": {"hypotheses": []},
                    })
                return harness_fixtures.response_for(state)

            with patch.object(harness, "invoke_actor", side_effect=actor):
                run, state = self.start(pattern, max_activations=1)
                self.assertEqual(self.status(run)["telos_result"]["state"], "active")
                frozen = (run / "options.json").read_bytes()
                snapshot = state["artifacts"][state["slots"]["external.governing"]]
                with patch.dict(os.environ, {"NOETIC_TELOS_SOURCE": str(self.root / "missing")}), \
                        patch.object(telos, "get_goal", side_effect=AssertionError("Advance must not refresh purpose")):
                    _, state = harness.drive(run)
            self.assertEqual(state["status"], "completed")
            self.assertEqual(len(calls), count)
            self.assertEqual((run / "options.json").read_bytes(), frozen)
            self.assertEqual(state["artifacts"][snapshot["id"]], snapshot)
            result = self.status(run)["telos_result"]
            self.assertEqual((result["state"], result["subgoal_status"]), ("completed", "complete"))
            self.assertEqual(result["completion_boundary"], boundary)
            self.assertEqual(result["pattern"], {key: state["pattern"][key] for key in ("name", "kind", "version")})
            self.assertEqual(result["controller_version"], state["version"])
            self.assertEqual(result["terminal_artifact"]["id"], state["last_receipt"]["artifact_id"])
            self.assertEqual(result["terminal_artifact"]["type"], "qa.review" if pattern == "development" else "cognition.P4")
            self.assertEqual(len({ref["session_ref"] for ref in result["actor_refs"]}), count)
            self.assertTrue(all(ref["result_artifact_id"] for ref in result["actor_refs"]))
            self.assertIsNone(result["reviewer"])
            self.assertIsNone(result["verdict"])
            self.assertFalse(any(e["kind"] == "review.recorded" for e in runtime.read_events(run)))
            aggregate = self.aggregate_now()
            self.assertEqual(aggregate["chain"]["status"], "active")
            note = [json.loads(record["details"].removeprefix("noetic.run.result "))
                    for record in aggregate["records"] if record["details"].startswith("noetic.run.result ")][-1]
            self.assertEqual(note["completion_boundary"], boundary)
            self.assertEqual(note["actor_refs"], result["actor_refs"])
            self.assertEqual(canonical[pattern], (controller.PATTERN_DIR / f"{pattern}.json").read_bytes())

    def test_current_noncompleted_authority_overrides_stale_generic_acceptance(self):
        for status in ("active", "failed", "blocked", "cancelled"):
            with self.subTest(status=status):
                run, state = self.start("development", max_activations=0, max_remediations=0)
                if status == "failed":
                    controller.runtime_failed(run / "controller.sqlite3", state["current_activation"], state["version"], "test fault")
                elif status == "cancelled":
                    harness.cancel(run)
                elif status == "blocked":
                    with patch.object(harness, "invoke_actor", side_effect=lambda r, s, o: harness_fixtures.response_for(
                            s, harness_fixtures.result_for(s, "fail"))):
                        harness.drive(run)
                # Deliberately contradictory legacy observation: never controller authority.
                runtime.record(run, "review.recorded", {"verdict": "accept", "reviewer": "fixture", "evidence": "stale label"})
                (run / "controller.json").write_text('{"status":"completed"}')
                result = telos.record_result(self.chain, self.status(run)["telos"]["subgoal_id"], run, self.db, self.source)
                self.assertEqual((result["state"], result["subgoal_status"]), (status, "active"))
                self.assertIsNone(result["completion_boundary"])
                self.assertIsNone(result["terminal_artifact"])
        self.assertTrue(all(goal["status"] == "active" for goal in self.aggregate_now()["subGoals"]))

    def test_corrupt_controller_and_missing_typed_boundary_cannot_fall_back(self):
        for corruption in ("sqlite", "state", "boundary"):
            with patch.object(harness, "invoke_actor", side_effect=lambda r, s, o: harness_fixtures.response_for(s)):
                run, _ = self.start(max_activations=0)
                link = self.status(run)["telos"]
                # Complete only in the kernel, before recording to Telos.
                state = harness.inspect(run)
                while state["status"] == "active":
                    state = controller.begin_activation(run / "controller.sqlite3", state["current_activation"], state["version"])
                    state = controller.submit_result(run / "controller.sqlite3", state["current_activation"], state["version"],
                        harness_fixtures.result_for(state), f"fixture:{state['current_activation']}", f"fixture:{state['version']}")
            runtime.record(run, "review.recorded", {"verdict": "accept", "reviewer": "fixture", "evidence": "not kernel evidence"})
            if corruption == "sqlite":
                (run / "controller.sqlite3").write_bytes(b"not sqlite")
            else:
                if corruption == "boundary":
                    state["slots"].pop("effective.P4")
                with closing(sqlite3.connect(run / "controller.sqlite3")) as connection, connection:
                    connection.execute("UPDATE run SET state = ?", (json.dumps(state) if corruption == "boundary" else "{}",))
            before = self.aggregate_now()
            with self.assertRaisesRegex(ValueError, "Cannot read controller result"):
                telos.record_result(self.chain, link["subgoal_id"], run, self.db, self.source)
            self.assertEqual(self.aggregate_now(), before)
            with redirect_stderr(io.StringIO()):
                self.assertEqual(noetic.main(["goal", "record", self.chain, link["subgoal_id"], str(run),
                                              "--db", str(self.db), "--source", str(self.source)]), 1)
            self.assertIn("telos_error", self.status(run))

    def test_fetch_or_begin_failure_prevents_actors_and_begin_can_retry(self):
        with patch.object(telos, "get_goal", side_effect=ValueError("unavailable")), \
                patch.object(harness, "invoke_actor") as actor, self.assertRaisesRegex(ValueError, "unavailable"):
            self.start()
        actor.assert_not_called()
        self.assertFalse((self.root / "runs").exists())
        with patch.object(telos, "begin_run", side_effect=ValueError("link write failed")), \
                patch.object(harness, "invoke_actor") as actor, self.assertRaisesRegex(ValueError, "association failed"):
            self.start()
        actor.assert_not_called()
        run = next(path.parent for path in (self.root / "runs").glob("*/controller.sqlite3"))
        self.assertEqual(harness.inspect(run)["activations"]["activation-0"]["status"], "ready")
        self.assertIn("telos_error", self.status(run))
        harness.drive(run, 0)
        self.assertNotIn("telos_error", self.status(run))
        self.assertEqual(len(self.aggregate_now()["subGoals"]), 1)

    def test_result_write_failure_visible_cli_and_record_retry_without_actor_replay(self):
        run, _ = self.start(max_activations=0)
        bridge = telos._bridge

        def unavailable(operation, *args, **kwargs):
            if operation == "record":
                raise ValueError("temporary result write failure")
            return bridge(operation, *args, **kwargs)

        output, errors = io.StringIO(), io.StringIO()
        with patch.object(harness, "invoke_actor", side_effect=lambda r, s, o: harness_fixtures.response_for(s)) as actors, \
                patch.object(telos, "_bridge", side_effect=unavailable), redirect_stdout(output), redirect_stderr(errors):
            self.assertEqual(noetic.main(["harness", "advance", str(run)]), 1)
        self.assertEqual(actors.call_count, 4)
        self.assertEqual(harness.inspect(run)["status"], "completed")
        self.assertIn("Kernel status: completed", output.getvalue())
        self.assertIn("not synchronized", errors.getvalue())
        self.assertIn("telos_error", self.status(run))
        self.assertEqual(self.aggregate_now()["subGoals"][0]["status"], "active")
        before = runtime.read_events(run)
        link = self.status(run)["telos"]
        command = ["goal", "record", self.chain, link["subgoal_id"], str(run),
                   "--db", str(self.db), "--source", str(self.source)]
        with patch.object(harness, "invoke_actor") as actor, redirect_stdout(io.StringIO()):
            self.assertEqual(noetic.main(command), 0)
            after = runtime.read_events(run)
            aggregate = self.aggregate_now()
            self.assertEqual(noetic.main(command), 0)
            self.assertEqual(noetic.main(["harness", "advance", str(run)]), 0)
        actor.assert_not_called()
        self.assertEqual(after[:-1], before)
        self.assertEqual(after[-1]["kind"], "telos.result")
        self.assertEqual(runtime.read_events(run), after)
        self.assertEqual(self.aggregate_now(), aggregate)
        self.assertNotIn("telos_error", self.status(run))
        self.assertEqual(aggregate["subGoals"][0]["status"], "complete")
        self.assertEqual(aggregate["chain"]["status"], "active")

    def test_core_write_then_observation_failure_retries_idempotently(self):
        run, _ = self.start(max_activations=0)
        record = runtime.record

        def fail_observation(directory, kind, data):
            if kind == "telos.result":
                raise OSError("observation unavailable after core write")
            return record(directory, kind, data)

        with patch.object(harness, "invoke_actor", side_effect=lambda r, s, o: harness_fixtures.response_for(s)), \
                patch.object(runtime, "record", side_effect=fail_observation):
            harness.drive(run)
        before = self.aggregate_now()
        self.assertEqual(before["subGoals"][0]["status"], "complete")
        self.assertIn("telos_error", self.status(run))
        link = self.status(run)["telos"]
        telos.record_result(self.chain, link["subgoal_id"], run, self.db, self.source)
        self.assertEqual(self.aggregate_now(), before)
        self.assertNotIn("telos_error", self.status(run))

    def test_completed_controller_relocation_retains_identity_and_references(self):
        with patch.object(harness, "invoke_actor", side_effect=lambda r, s, o: harness_fixtures.response_for(s)):
            run, state = self.start()
        original = self.status(run)["telos_result"]
        moved = self.root / "archive" / run.name
        shutil.copytree(run, moved)
        link = telos.begin_run(self.chain, moved, self.db, self.source)
        result = telos.record_result(self.chain, link["subgoal_id"], moved, self.db, self.source)
        self.assertEqual(result["subgoal_id"], original["subgoal_id"])
        self.assertEqual(result["actor_refs"], original["actor_refs"])
        self.assertEqual(result["artifact_path"], str(moved))
        self.assertEqual(result["controller_version"], state["version"])
        self.assertEqual(len(self.aggregate_now()["subGoals"]), 1)
        before = runtime.read_events(moved)
        telos.record_result(self.chain, link["subgoal_id"], moved, self.db, self.source)
        self.assertEqual(runtime.read_events(moved), before)

    def test_legacy_record_still_requires_actual_legacy_review(self):
        plan = runtime.validate_plan({"goal": self.task, "work": [sys.executable, "-c", "pass"],
                                      "verify": [sys.executable, "-c", "pass"], "timeout_seconds": 10})
        with redirect_stdout(io.StringIO()):
            run, _ = runtime.run_plan(plan, self.workspace, self.root / "runs")
        link = telos.begin_run(self.chain, run, self.db, self.source)
        self.assertEqual(telos.record_result(self.chain, link["subgoal_id"], run, self.db, self.source)["subgoal_status"], "active")
        evidence = run / "review.md"
        evidence.write_text("Fixture review of the recorded process output; not independent product QA.")
        runtime.review_run(run, "accept", "fixture-reviewer", evidence)
        result = telos.record_result(self.chain, link["subgoal_id"], run, self.db, self.source)
        self.assertEqual((result["state"], result["subgoal_status"]), ("accepted", "complete"))
        self.assertNotIn("completion_boundary", result)
        self.assertEqual(self.aggregate_now()["chain"]["status"], "active")


class HarnessBundleIntegrationTests(HarnessIntegrationTests):
    bundled = True


if __name__ == "__main__":
    unittest.main()
