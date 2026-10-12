"""Implementation checks using real runtime runs and labeled test-authored evidence."""

from contextlib import closing, redirect_stdout
import io
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from scripts import noetic_controller as controller
from scripts import noetic_memory as memory
from scripts import noetic_run as runtime


class SessionMemoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runs = self.root / "runs"
        self.db = self.root / "memory.sqlite3"

    def make_run(self):
        # Local test-authored commands, not model work or independent review.
        plan = {
            "goal": "Test-authored run discovery goal",
            "work": [sys.executable, "-c", "from pathlib import Path; Path('answer.txt').write_text('42')"],
            "verify": [sys.executable, "-c", "from pathlib import Path; assert Path('answer.txt').read_text() == '42'"],
        }
        with redirect_stdout(io.StringIO()):
            run_dir, status = runtime.run_plan(plan, self.root, self.runs)
        self.assertEqual(status["state"], "awaiting_review")
        (run_dir / "work.md").write_text("Test-authored worker findings: run discovery wrote answer.txt.", encoding="utf-8")
        return run_dir

    def make_controller_run(self, kind="cognition"):
        # Real retained stores with test-authored results, not live roles or QA.
        with redirect_stdout(io.StringIO()):
            retained = runtime.create_run(
                {"goal": "Test-authored legacy envelope goal"}, self.root, self.root / "retained")
        controller.start_run(
            retained / "controller.sqlite3", controller.PATTERN_DIR / f"{kind}.json",
            "Test-authored controller recall purpose", self.root)
        self.runs.mkdir(exist_ok=True)
        return Path(shutil.copytree(retained, self.runs / f"copied-{kind}"))

    def submit(self, run_dir, result):
        store = run_dir / "controller.sqlite3"
        state = controller.inspect_run(store)
        activation_id = state["current_activation"]
        state = controller.begin_activation(store, activation_id, state["version"])
        return controller.submit_result(
            store, activation_id, state["version"], result,
            f"test-authored-session:{activation_id}", f"test-authored-command:{activation_id}")

    def advance_p1(self, run_dir):
        return self.submit(run_dir, {"outcome": "advance", "content": {
            "observations": ["Test-authored observation"], "questions": [], "evidence_refs": []}})

    def cli(self, *args):
        result = subprocess.run(
            [sys.executable, str(Path(memory.__file__).resolve()), *map(str, args),
             "--runs-dir", str(self.runs), "--db", str(self.db)],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def results(self, query="run discovery", *options):
        return json.loads(self.cli("search", query, "--json", *options).stdout)

    def test_fresh_process_retrieval_and_retained_evidence_attribution(self):
        run_dir = self.make_run()
        evidence = self.root / "external-review.md"
        evidence.write_text("Test-authored reviewer evidence: run discovery checked answer.txt equals 42.", encoding="utf-8")
        runtime.review_run(run_dir, "accept", "test-authored-reviewer", evidence)
        evidence.unlink()
        rows = self.results()
        self.assertEqual({row["field"] for row in rows}, {"goal", "work", "review"})
        for row in rows:
            self.assertEqual(row["run_id"], run_dir.name)
            self.assertEqual(row["state"], "accepted")
            self.assertEqual(row["goal"], "Test-authored run discovery goal")
            self.assertIn("[", row["snippet"])
            self.assertEqual(row["source_path"], str(run_dir / ("work.md" if row["field"] == "work" else "events.sqlite3")))
            if row["event_sequence"] is not None:
                event = next(e for e in runtime.read_events(run_dir) if e["sequence"] == row["event_sequence"])
                self.assertEqual(event["kind"], "run.created" if row["field"] == "goal" else "review.recorded")
        text = self.cli("search", "run discovery").stdout
        self.assertIn(str(run_dir / "events.sqlite3"), text)
        self.assertIn("State: accepted", text)

    def test_rebuild_deduplicates_and_refreshes_reports_state_and_deletions(self):
        run_dir = self.make_run()
        self.assertEqual({r["state"] for r in self.results()}, {"awaiting_review"})
        review = run_dir / "review.md"
        review.write_text("Test-authored run discovery review: retainedmarker", encoding="utf-8")
        runtime.review_run(run_dir, "reject", "test-authored-reviewer", review)
        self.cli("index")
        first = self.results()
        self.cli("index")
        self.assertEqual(self.results(), first)
        self.assertEqual(len(first), 3)
        self.assertEqual({r["state"] for r in first}, {"rejected"})
        self.assertEqual(self.results("retainedmarker")[0]["source"], "review.md")
        review.write_text("Test-authored revised review: replacementmarker", encoding="utf-8")
        self.assertEqual(self.results("replacementmarker")[0]["source_path"], str(review))
        self.assertEqual(self.results("retainedmarker")[0]["source"], "review.recorded.evidence")
        review.unlink()
        (run_dir / "work.md").unlink()
        self.assertEqual(self.results("replacementmarker"), [])
        self.assertEqual(self.results("worker findings"), [])
        self.assertEqual(len(self.results("retainedmarker")), 1)
        shutil.rmtree(run_dir)
        self.assertEqual(self.results(), [])

    def test_missing_and_corrupt_runs_do_not_hide_valid_records(self):
        self.assertEqual(self.results(), [])
        self.assertFalse(self.runs.exists())
        run_dir = self.make_run()
        damaged = self.runs / "damaged"
        damaged.mkdir()
        (damaged / "events.sqlite3").write_text("not SQLite", encoding="utf-8")
        result = self.cli("search", "run discovery", "--json")
        self.assertIn(str(damaged), result.stderr)
        self.assertEqual({r["run_id"] for r in json.loads(result.stdout)}, {run_dir.name})
        (run_dir / "events.sqlite3").write_text("now corrupt too", encoding="utf-8")
        self.assertEqual(self.results(), [])

    def test_copied_controller_p2_recall_without_derived_reports_or_event_journal(self):
        run_dir = self.make_controller_run()
        self.advance_p1(run_dir)
        state = self.submit(run_dir, {"outcome": "advance", "content": {
            "hypotheses": ["Test-authored distinctive zephyrlattice recovery hypothesis"]}})
        artifact_id = state["slots"]["effective.P2"]
        # Copy the progressed store, not just its initial reservation.
        retained = self.root / "progressed-retained"
        shutil.copytree(run_dir, retained)
        shutil.rmtree(run_dir)
        shutil.copytree(retained, run_dir)
        (run_dir / "work.md").write_text("Stale zephyrlattice export " * 50, encoding="utf-8")
        (run_dir / "review.md").write_text("Stale zephyrlattice review", encoding="utf-8")
        (run_dir / "controller.json").write_text('{"purpose":"stale zephyrlattice projection"}', encoding="utf-8")
        rows = self.results("zephyrlattice")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["run_id"], run_dir.name)
        self.assertEqual(row["goal"], state["purpose"])
        self.assertEqual(row["state"], "active")
        self.assertEqual(row["source_path"], str(run_dir / "controller.sqlite3"))
        self.assertEqual(row["field"], "cognition.P2")
        self.assertIn("effective.P2", row["source"])
        self.assertIn(artifact_id, row["source"])
        self.assertIsNone(row["event_sequence"])
        self.assertIn("hypothesis", row["snippet"])
        for name in ("work.md", "review.md", "controller.json", "events.sqlite3"):
            (run_dir / name).unlink()
        before = (run_dir / "controller.sqlite3").read_bytes()
        self.assertEqual(self.results("zephyrlattice"), rows)
        self.assertEqual(self.results("legacy envelope"), [])
        text = self.cli("search", "zephyrlattice").stdout
        self.assertIn(str(run_dir / "controller.sqlite3"), text)
        self.assertIn("cognition.P2", text)
        self.assertIn(artifact_id, text)
        self.assertEqual((run_dir / "controller.sqlite3").read_bytes(), before)
        self.assertEqual(controller.inspect_run(run_dir / "controller.sqlite3"), state)

    def test_controller_return_refresh_excludes_invalidated_and_partial_artifacts(self):
        run_dir = self.make_controller_run()
        self.advance_p1(run_dir)
        state = self.submit(run_dir, {"outcome": "advance", "content": {
            "hypotheses": ["Test-authored supersededhypothesis"]}})
        old_id = state["slots"]["effective.P2"]
        self.assertEqual(len(self.results("supersededhypothesis")), 1)
        state = self.submit(run_dir, {"outcome": "return", "target": "P2",
                                     "reason": "Test-authored missing distinction",
                                     "question": "Which explanation fits?",
                                     "content": {"conditions": ["Test-authored partialjudgment"]}})
        self.assertNotIn("effective.P2", state["slots"])
        self.assertEqual(self.results("supersededhypothesis"), [])
        self.assertEqual(self.results("partialjudgment"), [])
        state = self.submit(run_dir, {"outcome": "advance", "content": {
            "hypotheses": ["Test-authored replacementhypothesis"]}})
        self.assertNotEqual(state["slots"]["effective.P2"], old_id)
        (run_dir / "work.md").write_text("supersededhypothesis replacementhypothesis " * 50, encoding="utf-8")
        self.assertEqual(self.results("supersededhypothesis"), [])
        rows = self.results("replacementhypothesis")
        self.assertEqual(len(rows), 1)
        self.assertIn(state["slots"]["effective.P2"], rows[0]["source"])
        self.assertEqual(rows[0]["source_path"], str(run_dir / "controller.sqlite3"))
        self.cli("index")
        self.assertEqual(self.results("replacementhypothesis"), rows)
        shutil.rmtree(run_dir)
        self.assertEqual(self.results("replacementhypothesis"), [])

    def test_controller_development_indexes_accepted_bindings_and_linked_qa_only(self):
        run_dir = self.make_controller_run("development")
        def design(marker):
            return {"outcome": "produced", "content": {"objective": marker,
                    "scope": ["Test-authored fixture"], "acceptance_criteria": ["Retain typed evidence"]}}

        state = self.submit(run_dir, design("rejecteddraftmarker"))
        self.assertEqual(self.results("rejecteddraftmarker"), [])
        self.submit(run_dir, {"subject_artifact_id": state["subject_artifact_id"], "verdict": "fail",
                             "report": "Test-authored rejectedqamarker; not independent QA",
                             "findings": [{"description": "Test-authored missing evidence", "blocking": True}]})
        state = self.submit(run_dir, design("accepteddesignmarker"))
        current_id = state["subject_artifact_id"]
        self.assertEqual(self.results("accepteddesignmarker"), [])
        state = self.submit(run_dir, {"subject_artifact_id": current_id, "verdict": "pass",
                                     "report": "Test-authored acceptedqamarker; not independent QA", "findings": []})
        (run_dir / "work.md").write_text("rejecteddraftmarker rejectedqamarker", encoding="utf-8")
        self.assertEqual(state["slots"]["accepted.design_intent"], current_id)
        row = self.results("accepteddesignmarker")[0]
        self.assertEqual(row["field"], "development.design_intent")
        self.assertIn("accepted.design_intent", row["source"])
        self.assertIn(current_id, row["source"])
        qa = self.results("acceptedqamarker")[0]
        self.assertEqual(qa["field"], "qa.review")
        self.assertIn(f"qa.for.{current_id}", qa["source"])
        self.assertEqual(self.results("rejecteddraftmarker"), [])
        self.assertEqual(self.results("rejectedqamarker"), [])

    def test_corrupt_controller_does_not_fall_back_to_stale_legacy_exports(self):
        legacy = self.make_run()
        run_dir = self.make_controller_run()
        (run_dir / "work.md").write_text("Test-authored corruptfallbackmarker run discovery", encoding="utf-8")
        (run_dir / "controller.sqlite3").write_text("not SQLite", encoding="utf-8")
        result = self.cli("search", "run discovery", "--json")
        self.assertIn(str(run_dir), result.stderr)
        self.assertEqual({row["run_id"] for row in json.loads(result.stdout)}, {legacy.name})
        self.assertEqual(self.results("corruptfallbackmarker"), [])

    def test_literal_queries_empty_input_and_bounded_limits(self):
        run_dir = self.make_run()
        (run_dir / "work.md").write_text("Test-authored punctuation: C++ foo:bar quoted OR baz.", encoding="utf-8")
        for query in ("C++", "foo:bar", '"quoted"', "OR", "baz*", "(baz)"):
            with self.subTest(query=query):
                self.assertEqual(self.results(query)[0]["field"], "work")
        for query in ("", " \t ", "***", "missing OR baz"):
            with self.subTest(query=query):
                self.assertEqual(self.results(query), [])
        with closing(sqlite3.connect(":memory:")) as connection:
            self.assertEqual(memory.index_runs(connection, self.runs), 2)
            self.assertEqual(memory.index_runs(connection, self.runs), 2)
            self.assertEqual(len(memory.search(connection, "test", 0)), 1)
            # Duplicate derived rows only to exercise the upper bound without 100 processes.
            for _ in range(7):
                connection.execute("INSERT INTO memory SELECT * FROM memory")
            self.assertEqual(len(memory.search(connection, "test", 1000)), 100)
        self.assertEqual(len(self.results("test", "--limit", "1")), 1)


if __name__ == "__main__":
    unittest.main()
