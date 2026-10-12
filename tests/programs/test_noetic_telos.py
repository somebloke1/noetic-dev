"""Focused integration checks using the actual local Telos factory, without models."""

from contextlib import closing, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import noetic_run as runtime
from scripts import noetic_telos as telos
from scripts import noetic_develop as development


class TelosRunTests(unittest.TestCase):
    bundled = False

    @classmethod
    def setUpClass(cls):
        cls.source = telos.source_path()
        if not shutil.which("node"):
            raise unittest.SkipTest("actual Telos integration requires Node 24 on PATH")
        version = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=10)
        if version.returncode or int(version.stdout.strip().lstrip("v").split(".")[0]) < 24:
            raise unittest.SkipTest(f"actual Telos integration requires Node 24; found {version.stdout.strip()}")
        tool = "node_modules/esbuild/bin/esbuild" if cls.bundled else "node_modules/tsx/dist/loader.mjs"
        for relative in ("packages/pi-runtime/src/core-goal-chain-store.ts", tool):
            if not (cls.source / relative).is_file():
                raise unittest.SkipTest(f"actual Telos integration unavailable: {cls.source / relative}")
        if cls.bundled:
            temporary = tempfile.TemporaryDirectory()
            cls.addClassCleanup(temporary.cleanup)
            root = Path(temporary.name)
            output = root / "build/telos-core.mjs"
            result = subprocess.run(
                [sys.executable, "-m", "scripts.noetic", "goal", "bundle",
                 "--source", str(cls.source), "--output", str(output)],
                cwd=Path(telos.__file__).resolve().parents[1],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode:
                raise RuntimeError(f"actual Telos bundle failed: {result.stderr}")
            cls.build_result = json.loads(result.stdout)
            cls.manifest = json.loads(Path(cls.build_result["manifest"]).read_text())
            cls.build_source = cls.source
            deployment = root / "deployment"
            deployment.mkdir()
            cls.source = output.replace(deployment / "relocated core.mjs")
            shutil.rmtree(output.parent)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.db = self.root / ".runtime/telos.sqlite3"
        if self.bundled:
            # Runtime gets only Node on PATH and the relocated module, not build/client tools.
            node = Path(shutil.which("node")).resolve()
            bin_dir = self.root / "bin"
            bin_dir.mkdir()
            (bin_dir / "node").symlink_to(node)
            environment = patch.dict(os.environ, {
                "PATH": str(bin_dir), "HOME": str(self.root), "PYTHONDONTWRITEBYTECODE": "1",
                "NOETIC_TELOS_SOURCE": str(self.source), "TELOS_STATE_DIR": str(self.root / "unused-native-state"),
            }, clear=True)
            environment.start()
            self.addCleanup(environment.stop)
            self.addCleanup(lambda: self.assertFalse((self.root / "unused-native-state").exists()))
        self.plan = runtime.validate_plan({
            "goal": "Produce a local answer and verify its value",
            "work": [sys.executable, "-c", "print(42)"],
            "verify": [sys.executable, "-c", "assert 6 * 7 == 42"],
            "timeout_seconds": 10,
        })
        self.aggregate = telos.create_goal("Realize noetic-dev incrementally", self.db, self.source)
        self.chain_id = self.aggregate["chain"]["chainId"]

    def cli(self, *args, db=None, source=None):
        return subprocess.run(
            [sys.executable, str(Path(telos.__file__).resolve()), *map(str, args),
             "--db", str(db or self.db), "--source", str(source or self.source)],
            capture_output=True, text=True, timeout=60,
        )

    def run_plan(self, failed=False):
        plan = {**self.plan}
        if failed:
            plan["verify"] = [sys.executable, "-c", "raise SystemExit(7)"]
        with redirect_stdout(io.StringIO()):
            return runtime.run_plan(plan, self.root, self.root / "runs")[0]

    def review(self, run_dir, verdict="accept"):
        evidence = run_dir / "review.md"
        evidence.write_text(f"Test review evidence: observed output 42 and inspected the verification log at {run_dir}.\n")
        runtime.review_run(run_dir, verdict, "integration-test-reviewer", evidence)

    def seed_subgoals(self, objectives):
        # Seed persisted legacy data through the core, not the bridge under test.
        factory = self.source if self.bundled else self.source / "packages/pi-runtime/src/core-goal-chain-store.ts"
        command = ["node"]
        if not self.bundled:
            command.extend(["--import", (self.source / "node_modules/tsx/dist/loader.mjs").as_uri()])
        command.extend(["--input-type=module", "--eval", """
            import { readFileSync } from 'node:fs';
            const input = JSON.parse(readFileSync(0, 'utf8'));
            const { createPiCoreGoalChainStore } = await import(input.factory);
            const handle = createPiCoreGoalChainStore({ dbPath: input.db });
            try {
                console.log(JSON.stringify(handle.manager.addSubGoals(input.chain, input.objectives)));
            } finally {
                handle.close();
            }
        """])
        result = subprocess.run(command, input=json.dumps({
            "factory": factory.as_uri(), "db": str(self.db), "chain": self.chain_id, "objectives": objectives,
        }), capture_output=True, text=True, timeout=30, env={**os.environ, "TSX_DISABLE_CACHE": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def copy_database(self, source, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(destination)) as copied:
                original.backup(copied)

    def copy_run(self, run_dir, destination):
        shutil.copytree(run_dir, destination, ignore=shutil.ignore_patterns("events.sqlite3*"))
        self.copy_database(run_dir / "events.sqlite3", destination / "events.sqlite3")
        return destination

    def result_notes(self, aggregate):
        return [json.loads(record["details"].removeprefix("noetic.run.result "))
                for record in aggregate["records"] if record["details"].startswith("noetic.run.result ")]

    def environment_guard(self, wrapper, executable):
        node = Path(shutil.which("node")).resolve()
        wrapper.parent.mkdir(parents=True, exist_ok=True)
        wrapper.write_text(f"#!{node}\n" + """
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
if (Object.hasOwn(process.env, 'USER_PROVIDED_PASSWORD')) process.exit(17);
assert.equal(process.env.OPENAI_API_KEY, 'public-provider-sentinel');
assert.equal(process.env.NOETIC_TEST_RUNTIME, 'deliberate-runtime-value');
assert.equal(process.env.TSX_DISABLE_CACHE ?? '<unset>', process.env.NOETIC_TEST_EXPECTED_TSX);
const result = spawnSync(""" + json.dumps(str(executable)) + """, process.argv.slice(2), { stdio: 'inherit' });
if (result.error) throw result.error;
process.exit(result.status ?? 1);
""")
        wrapper.chmod(0o700)

    def test_factory_child_excludes_development_credential_and_preserves_environment(self):
        node = Path(shutil.which("node")).resolve()
        bin_dir = self.root / "guarded-bin"
        self.environment_guard(bin_dir / "node", node)
        for cache in (None, "public-cache-setting"):
            with self.subTest(cache=cache), patch.dict(os.environ, {
                "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
                "USER_PROVIDED_PASSWORD": "public-development-sentinel",
                "OPENAI_API_KEY": "public-provider-sentinel",
                "NOETIC_TEST_RUNTIME": "deliberate-runtime-value",
                "NOETIC_TEST_EXPECTED_TSX": (cache or "<unset>") if self.bundled else "1",
            }):
                if cache is None:
                    os.environ.pop("TSX_DISABLE_CACHE", None)
                else:
                    os.environ["TSX_DISABLE_CACHE"] = cache
                parent = os.environ.copy()
                aggregate = telos.create_goal("Check the helper environment", self.db, self.source)
                self.assertEqual(telos.get_goal(aggregate["chain"]["chainId"], self.db, self.source), aggregate)
                self.assertTrue(dict(os.environ) == parent, "helper mutated the parent environment")

    def test_create_reopen_and_explicit_isolation(self):
        self.assertTrue(self.db.is_file())
        self.assertEqual(self.aggregate["chain"]["scope"], "global")
        self.assertIsNone(self.aggregate["chain"]["projectId"])
        self.assertEqual(self.aggregate["chain"]["status"], "active")
        self.assertEqual(self.aggregate["subGoals"], [])
        self.assertEqual(telos.get_goal(self.chain_id, self.db, self.source), self.aggregate)
        restarted = self.cli("get", self.chain_id)
        self.assertEqual(restarted.returncode, 0, restarted.stderr)
        self.assertEqual(json.loads(restarted.stdout), self.aggregate)
        other_db = self.root / "other.sqlite3"
        other = telos.create_goal("Separate project", other_db, self.source)
        with self.assertRaisesRegex(ValueError, "not found"):
            telos.get_goal(self.chain_id, other_db, self.source)
        self.assertNotEqual(other["chain"]["chainId"], self.chain_id)
        created = self.cli("create", "CLI master goal")
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertEqual(json.loads(created.stdout)["chain"]["primaryGoal"], "CLI master goal")

    def test_doctor_reports_selected_runtime_mode(self):
        result = subprocess.run(
            [sys.executable, "-m", "scripts.noetic", "doctor"],
            cwd=Path(telos.__file__).resolve().parents[1],
            env={**os.environ, "NOETIC_TELOS_SOURCE": str(self.source)},
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["telos_mode"], "module" if self.bundled else "source")
        self.assertTrue(report["telos_factory_present"])
        self.assertEqual(report["telos_loader_required"], not self.bundled)
        self.assertEqual(report["telos_loader_present"], None if self.bundled else True)

    def test_attach_accepted_run_twice_reuses_subgoal_note_and_link(self):
        self.plan["goal"] += "\n"
        run_dir = self.run_plan()
        self.review(run_dir)
        first = self.cli("attach", self.chain_id, run_dir)
        self.assertEqual(first.returncode, 0, first.stderr)
        linked = json.loads(first.stdout)
        before = telos.get_goal(self.chain_id, self.db, self.source)
        again = self.cli("attach", self.chain_id, run_dir)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(json.loads(again.stdout), linked)
        self.assertEqual(telos.get_goal(self.chain_id, self.db, self.source), before)
        self.assertEqual(len(before["subGoals"]), 1)
        self.assertEqual(before["subGoals"][0]["status"], "complete")
        self.assertEqual(before["chain"]["status"], "active")
        notes = self.result_notes(before)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["state"], "accepted")
        self.assertEqual(notes[0]["reviewer"], "integration-test-reviewer")
        self.assertEqual(notes[0]["artifact_path"], str(run_dir))
        self.assertTrue(Path(notes[0]["journal_path"]).is_file())
        links = [event["data"] for event in runtime.read_events(run_dir) if event["kind"] == "telos.linked"]
        self.assertEqual(links, [{key: linked[key] for key in (
            "chain_id", "subgoal_id", "db_path", "source", "artifact_path", "journal_path",
        )}])

    def test_relocated_accepted_archive_reuses_legacy_and_stable_subgoals(self):
        self.plan["goal"] = "  Produce a local answer\nPreserve this purpose after relocation.\n"
        for legacy in (True, False):
            with self.subTest(legacy=legacy):
                run_dir = self.run_plan()
                self.review(run_dir)
                status = runtime.project(runtime.read_events(run_dir))
                objective = f"noetic run {status['run_id']}" + (f" at {run_dir}" if legacy else "")
                objective = f"{objective}\n{status['goal']}".strip()
                if legacy:
                    subgoal_id = self.seed_subgoals([objective])[0]["subGoalId"]
                    runtime.record(run_dir, "telos.linked", {
                        "chain_id": self.chain_id, "subgoal_id": subgoal_id,
                        "db_path": str(self.db), "source": str(self.source),
                    })
                else:
                    subgoal_id = telos.begin_run(self.chain_id, run_dir, self.db, self.source)["subgoal_id"]
                telos.record_result(self.chain_id, subgoal_id, run_dir, self.db, self.source)
                before = telos.get_goal(self.chain_id, self.db, self.source)
                events = runtime.read_events(run_dir)
                moved = self.copy_run(run_dir, self.root / "relocated archive" / run_dir.name)
                # Cover a copied DB and a location-only move with the same DB path.
                db = moved.parent / "telos.sqlite3" if legacy else self.db
                if legacy:
                    self.copy_database(self.db, db)
                recorded = self.cli("record", self.chain_id, subgoal_id, moved, db=db)
                self.assertEqual(recorded.returncode, 0, recorded.stderr)
                result = json.loads(recorded.stdout)
                self.assertEqual(result["subgoal_id"], subgoal_id)
                self.assertEqual((result["run_id"], result["subgoal_status"]), (status["run_id"], "complete"))
                current = runtime.read_events(moved)
                self.assertEqual(current[:len(events)], events)
                self.assertEqual([event["kind"] for event in current[len(events):]], ["telos.linked", "telos.result"])
                for observation in current[-2:]:
                    self.assertEqual(observation["data"]["artifact_path"], str(moved))
                    self.assertEqual(observation["data"]["journal_path"], str(moved / "events.sqlite3"))
                    self.assertEqual(observation["data"]["db_path"], str(db))
                    self.assertEqual(observation["data"]["source"], str(self.source))
                self.assertEqual(runtime.project(current)["review"], status["review"])
                for name in ("review.md", "work.stdout.log", "verify.stderr.log"):
                    self.assertEqual((moved / name).read_bytes(), (run_dir / name).read_bytes())
                after = telos.get_goal(self.chain_id, db, self.source)
                self.assertEqual(after["subGoals"], before["subGoals"])
                self.assertEqual(next(goal["objective"] for goal in after["subGoals"]
                                      if goal["subGoalId"] == subgoal_id), objective)
                self.assertEqual(after["records"][:-1], before["records"])
                note = self.result_notes(after)[-1]
                self.assertEqual((note["artifact_path"], note["journal_path"]),
                                 (str(moved), str(moved / "events.sqlite3")))
                self.assertEqual(after["chain"]["status"], "active")
                for command in (("attach", self.chain_id, moved), ("record", self.chain_id, subgoal_id, moved)):
                    repeated = self.cli(*command, db=db)
                    self.assertEqual(repeated.returncode, 0, repeated.stderr)
                    self.assertEqual(json.loads(repeated.stdout), result)
                    self.assertEqual(runtime.read_events(moved), current)
                    self.assertEqual(telos.get_goal(self.chain_id, db, self.source), after)
                self.assertEqual(runtime.read_events(run_dir), events)
                if legacy:
                    self.assertEqual(telos.get_goal(self.chain_id, self.db, self.source), before)

    def test_same_run_id_with_changed_goal_refuses_attach_and_record(self):
        for legacy in (True, False):
            with self.subTest(legacy=legacy):
                run_dir = self.run_plan()
                if legacy:
                    objective = f"noetic run {run_dir.name} at {run_dir}\n{self.plan['goal']}"
                    subgoal_id = self.seed_subgoals([objective])[0]["subGoalId"]
                else:
                    subgoal_id = telos.begin_run(self.chain_id, run_dir, self.db, self.source)["subgoal_id"]
                changed_plan = {**self.plan, "goal": self.plan["goal"] + "\nA different purpose"}
                with redirect_stdout(io.StringIO()):
                    changed = runtime.create_run(changed_plan, self.root, self.root / "changed", run_dir.name)
                for step in ("work", "verify"):
                    self.assertEqual(runtime.execute_step(changed, self.root, step, changed_plan[step], 10), "passed")
                runtime.record(changed, "run.finished", {"state": "awaiting_review"})
                self.review(changed)
                before = telos.get_goal(self.chain_id, self.db, self.source)
                events = runtime.read_events(changed)
                for command in (("attach", self.chain_id, changed), ("record", self.chain_id, subgoal_id, changed)):
                    refused = self.cli(*command)
                    self.assertEqual(refused.returncode, 1, refused.stdout)
                    self.assertIn("Run goal does not match", refused.stderr)
                    self.assertEqual(telos.get_goal(self.chain_id, self.db, self.source), before)
                    self.assertEqual(runtime.read_events(changed), events)

    def test_ambiguous_historical_duplicates_are_preserved_and_refused(self):
        run_dir = self.run_plan()
        self.review(run_dir)
        moved = self.copy_run(run_dir, self.root / "relocated" / run_dir.name)
        objectives = [f"noetic run {run_dir.name} at {path}\n{self.plan['goal']}" for path in (run_dir, moved)]
        subgoals = self.seed_subgoals(objectives)
        before = telos.get_goal(self.chain_id, self.db, self.source)
        events = runtime.read_events(moved)
        commands = [("attach", self.chain_id, moved)] + [
            ("record", self.chain_id, goal["subGoalId"], moved) for goal in subgoals
        ]
        for command in commands:
            refused = self.cli(*command)
            self.assertEqual(refused.returncode, 1, refused.stdout)
            self.assertIn("Ambiguous subgoal association", refused.stderr)
            self.assertEqual(telos.get_goal(self.chain_id, self.db, self.source), before)
            self.assertEqual(runtime.read_events(moved), events)

    def test_begin_then_record_requires_review_and_completes_only_that_run(self):
        with redirect_stdout(io.StringIO()):
            run_dir = runtime.create_run(self.plan, self.root, self.root / "runs")
        link = telos.begin_run(self.chain_id, run_dir, self.db, self.source)
        pending = telos.record_result(self.chain_id, link["subgoal_id"], run_dir, self.db, self.source)
        self.assertEqual((pending["state"], pending["subgoal_status"]), ("unfinished", "active"))
        for step in ("work", "verify"):
            self.assertEqual(runtime.execute_step(run_dir, self.root, step, self.plan[step], 10), "passed")
        runtime.record(run_dir, "run.finished", {"state": "awaiting_review"})
        unreviewed = telos.record_result(self.chain_id, link["subgoal_id"], run_dir, self.db, self.source)
        self.assertEqual(unreviewed["subgoal_status"], "active")
        other_run = self.run_plan()
        other = telos.begin_run(self.chain_id, other_run, self.db, self.source)
        self.review(run_dir)
        result = self.cli("record", self.chain_id, link["subgoal_id"], run_dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["subgoal_status"], "complete")
        aggregate = telos.get_goal(self.chain_id, self.db, self.source)
        self.assertEqual({goal["subGoalId"]: goal["status"] for goal in aggregate["subGoals"]},
                         {link["subgoal_id"]: "complete", other["subgoal_id"]: "active"})
        self.assertEqual(aggregate["chain"]["status"], "active")
        self.assertEqual([note["state"] for note in self.result_notes(aggregate)],
                         ["unfinished", "awaiting_review", "accepted"])

    def test_nonaccepted_and_accepted_without_actual_review_stay_active(self):
        for state in ("failed", "awaiting_review", "rejected", "accepted"):
            with self.subTest(state=state):
                run_dir = self.run_plan(failed=state == "failed")
                if state == "rejected":
                    self.review(run_dir, "reject")
                elif state == "accepted":
                    # A state label alone is not review evidence.
                    runtime.record(run_dir, "run.finished", {"state": "accepted"})
                link = telos.begin_run(self.chain_id, run_dir, self.db, self.source)
                result = telos.record_result(self.chain_id, link["subgoal_id"], run_dir, self.db, self.source)
                self.assertEqual((result["state"], result["subgoal_status"]), (state, "active"))
                events = runtime.read_events(run_dir)
                moved = self.copy_run(run_dir, self.root / "relocated" / run_dir.name)
                attached = telos.begin_run(self.chain_id, moved, self.db, self.source)
                self.assertEqual(attached["subgoal_id"], link["subgoal_id"])
                result = telos.record_result(self.chain_id, link["subgoal_id"], moved, self.db, self.source)
                self.assertEqual((result["state"], result["subgoal_status"]), (state, "active"))
                self.assertEqual(runtime.read_events(moved)[:len(events)], events)
                before = telos.get_goal(self.chain_id, self.db, self.source)
                current = runtime.read_events(moved)
                telos.record_result(self.chain_id, link["subgoal_id"], moved, self.db, self.source)
                self.assertEqual(telos.get_goal(self.chain_id, self.db, self.source), before)
                self.assertEqual(runtime.read_events(moved), current)
        aggregate = telos.get_goal(self.chain_id, self.db, self.source)
        self.assertTrue(all(goal["status"] == "active" for goal in aggregate["subGoals"]))
        self.assertEqual(aggregate["chain"]["status"], "active")
        self.assertEqual(len(aggregate["subGoals"]), 4)
        self.assertEqual(len(self.result_notes(aggregate)), 8)

    def test_result_cannot_complete_another_runs_subgoal(self):
        first = self.run_plan()
        second = self.run_plan()
        self.review(second)
        link = telos.begin_run(self.chain_id, first, self.db, self.source)
        before = telos.get_goal(self.chain_id, self.db, self.source)
        with self.assertRaisesRegex(ValueError, "not associated with this run"):
            telos.record_result(self.chain_id, link["subgoal_id"], second, self.db, self.source)
        self.assertEqual(telos.get_goal(self.chain_id, self.db, self.source), before)

    def test_successful_metadata_retry_supersedes_error_without_rerunning_work(self):
        run_dir = self.run_plan()
        self.review(run_dir)
        link = telos.begin_run(self.chain_id, run_dir, self.db, self.source)
        runtime.record(run_dir, "telos.error", {"error": "temporary result-write failure"})
        before = runtime.read_events(run_dir)
        self.assertIn("telos_error", runtime.project(before))
        retried = self.cli("record", self.chain_id, link["subgoal_id"], run_dir)
        self.assertEqual(retried.returncode, 0, retried.stderr)
        events = runtime.read_events(run_dir)
        status = runtime.project(events)
        self.assertEqual(status["telos_result"]["subgoal_status"], "complete")
        self.assertNotIn("telos_error", status)
        self.assertEqual(events[:-1], before)
        self.assertEqual(events[-1]["kind"], "telos.result")
        telos.record_result(self.chain_id, link["subgoal_id"], run_dir, self.db, self.source)
        self.assertEqual(runtime.read_events(run_dir), events)
        output = io.StringIO()
        with redirect_stdout(output):
            runtime.render_status(run_dir, status)
        self.assertNotIn("not synchronized", output.getvalue())

    def test_development_runner_links_before_execution_and_records_reviewed_result(self):
        prompts = []
        def command(client, prompt, role, model, run_dir=None, workspace=None, context_dirs=()):
            prompts.append(prompt)
            text = "Implemented" if role == "worker" else "ACCEPT\nInspected the actual output and test result."
            events = [
                {"type": "text", "sessionID": role, "part": {"id": role, "messageID": role, "text": text}},
                {"type": "step_finish", "sessionID": role, "part": {"messageID": role, "reason": "stop"}},
            ]
            return [sys.executable, "-c", "print(" + repr("\n".join(json.dumps(event) for event in events)) + ")"], None
        with patch.object(development, "client_command", side_effect=command), redirect_stdout(io.StringIO()):
            run_dir, status = development.develop("Produce a checked response", self.root, self.root / "runs",
                [sys.executable, "-c", "print('checked')"], telos_chain=self.chain_id, telos_db=self.db, telos_source=self.source)
        self.assertEqual(status["state"], "accepted")
        self.assertEqual(status["telos_result"]["subgoal_status"], "complete")
        kinds = [event["kind"] for event in runtime.read_events(run_dir)]
        self.assertLess(kinds.index("telos.linked"), kinds.index("step.started"))
        self.assertLess(kinds.index("review.recorded"), kinds.index("telos.result"))
        self.assertTrue(all("Realize noetic-dev incrementally" in prompt for prompt in prompts))
        aggregate = telos.get_goal(self.chain_id, self.db, self.source)
        self.assertEqual(aggregate["chain"]["status"], "active")
        self.assertEqual(aggregate["subGoals"][0]["status"], "complete")


class TelosBundleTests(TelosRunTests):
    """Repeat the run contract against a real bundle relocated away from the build."""

    bundled = True

    def test_source_only_changes_append_current_observations_without_duplicate_notes(self):
        run_dir = self.run_plan()
        self.review(run_dir)
        initial = self.cli("attach", self.chain_id, run_dir)
        self.assertEqual(initial.returncode, 0, initial.stderr)
        before = telos.get_goal(self.chain_id, self.db, self.source)
        relocated_source = self.root / "another core.mjs"
        shutil.copyfile(self.source, relocated_source)
        for source in (relocated_source, self.source):
            events = runtime.read_events(run_dir)
            result = self.cli("attach", self.chain_id, run_dir, source=source)
            self.assertEqual(result.returncode, 0, result.stderr)
            current = runtime.read_events(run_dir)
            self.assertEqual(current[:-2], events)
            self.assertEqual([event["kind"] for event in current[-2:]], ["telos.linked", "telos.result"])
            self.assertTrue(all(event["data"]["source"] == str(source) for event in current[-2:]))
            repeated = self.cli("attach", self.chain_id, run_dir, source=source)
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertEqual(runtime.read_events(run_dir), current)
            self.assertEqual(telos.get_goal(self.chain_id, self.db, source), before)

    def test_bundling_child_excludes_development_credential_and_preserves_environment(self):
        source = self.root / "guarded-source"
        factory = source / "packages/pi-runtime/src/core-goal-chain-store.ts"
        factory.parent.mkdir(parents=True)
        factory.symlink_to(self.build_source / "packages/pi-runtime/src/core-goal-chain-store.ts")
        self.environment_guard(source / "node_modules/esbuild/bin/esbuild",
                               self.build_source / "node_modules/esbuild/bin/esbuild")
        output = self.root / "guarded-core.mjs"
        for cache in (None, "public-cache-setting"):
            with self.subTest(cache=cache), patch.dict(os.environ, {
                "USER_PROVIDED_PASSWORD": "public-development-sentinel",
                "OPENAI_API_KEY": "public-provider-sentinel",
                "NOETIC_TEST_RUNTIME": "deliberate-runtime-value",
                "NOETIC_TEST_EXPECTED_TSX": cache or "<unset>",
            }):
                if cache is None:
                    os.environ.pop("TSX_DISABLE_CACHE", None)
                else:
                    os.environ["TSX_DISABLE_CACHE"] = cache
                parent = os.environ.copy()
                result = telos.bundle_goal_store(source, output)
                self.assertEqual(result["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
                aggregate = telos.create_goal("Use the guarded build", self.db, output)
                self.assertEqual(telos.get_goal(aggregate["chain"]["chainId"], self.db, output), aggregate)
                self.assertTrue(dict(os.environ) == parent, "helper mutated the parent environment")

    def test_bundle_identity_exports_and_only_builtin_imports(self):
        self.assertEqual(self.manifest["sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(self.build_result["sha256"], self.manifest["sha256"])
        self.assertEqual(self.manifest["source"], str(self.build_source))
        self.assertEqual(self.manifest["entrypoint"], "packages/pi-runtime/src/core-goal-chain-store.ts")
        self.assertEqual(self.manifest["source_identity"],
                         "built from current source including possible uncommitted changes")
        self.assertEqual((self.manifest["target"], self.manifest["format"], self.manifest["platform"]),
                         ("node24", "esm", "node"))
        self.assertFalse(Path(self.build_result["module"]).exists())
        self.assertFalse(Path(self.build_result["manifest"]).exists())
        self.assertEqual(list(self.source.parent.iterdir()), [self.source])
        module = self.source.read_text()
        imports = re.findall(r'^import\b[^;]*["\']([^"\']+)["\'];', module, re.MULTILINE)
        self.assertTrue(imports)
        self.assertNotRegex(module, r'\b(?:import|require)\s*\(')
        self.assertTrue(all(name.startswith("node:") for name in imports), imports)
        exported = subprocess.run(
            ["node", "--input-type=module", "--eval",
             "const core = await import(process.argv[1]); console.log(typeof core.createPiCoreGoalChainStore);",
             self.source.as_uri()], capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(exported.returncode, 0, exported.stderr)
        self.assertEqual(exported.stdout.strip(), "function")

    def test_environment_module_uses_plain_node_without_tsx(self):
        for executable in ("tsx", "esbuild", "pi", "opencode"):
            self.assertIsNone(shutil.which(executable))
        with patch.object(telos.subprocess, "run", wraps=subprocess.run) as calls:
            aggregate = telos.create_goal("Use the deployed component", self.db)
            self.assertEqual(telos.get_goal(aggregate["chain"]["chainId"], self.db), aggregate)
        self.assertEqual(calls.call_count, 2)
        for call in calls.call_args_list:
            self.assertEqual(call.args[0], ["node", str(Path(telos.__file__).with_name("telos_bridge.mjs"))])
        result = subprocess.run(
            [sys.executable, "-m", "scripts.noetic", "goal", "get", self.chain_id, "--db", str(self.db)],
            cwd=Path(telos.__file__).resolve().parents[1], capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), self.aggregate)


class TelosConfigurationTests(unittest.TestCase):
    def test_missing_source_reports_limitation_without_creating_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = subprocess.run(
                [sys.executable, str(Path(telos.__file__).resolve()), "create", "Example",
                 "--db", str(root / "telos.sqlite3"), "--source", str(root / "missing")],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("Telos component unavailable", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((root / "telos.sqlite3").exists())

    def test_missing_module_reports_path_and_doctor_does_not_require_tsx(self):
        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory) / "missing.mjs"
            db = Path(directory) / "telos.sqlite3"
            with self.assertRaisesRegex(ValueError, "Telos component unavailable: .*missing.mjs"):
                telos.create_goal("Example", db, module)
            result = subprocess.run(
                [sys.executable, "-m", "scripts.noetic", "doctor"],
                cwd=Path(telos.__file__).resolve().parents[1],
                env={**os.environ, "NOETIC_TELOS_SOURCE": str(module)},
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["telos_mode"], "module")
            self.assertFalse(report["telos_factory_present"])
            self.assertFalse(report["telos_loader_required"])
            self.assertIsNone(report["telos_loader_present"])
            self.assertFalse(db.exists())

    def test_bundle_missing_build_tool_reports_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            factory = root / "packages/pi-runtime/src/core-goal-chain-store.ts"
            factory.parent.mkdir(parents=True)
            factory.touch()
            with self.assertRaisesRegex(ValueError, "installed esbuild: missing .*node_modules/esbuild/bin/esbuild"):
                telos.bundle_goal_store(root, root / "telos-core.mjs")
            self.assertFalse((root / "telos-core.mjs").exists())


if __name__ == "__main__":
    unittest.main()
