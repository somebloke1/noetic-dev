"""Real retained execution evidence, including failed and unlaunched commands."""

from contextlib import closing, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import noetic_act_observation as observation
from scripts import noetic_run as runtime


class ActObservationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.environment = {key: value for key, value in os.environ.items() if key != "USER_PROVIDED_PASSWORD"}

    def create(self, code="from pathlib import Path; Path('answer').write_text('42'); print('created')", argv=None):
        command = argv or [sys.executable, "-c", code]
        with redirect_stdout(io.StringIO()):
            run_dir = runtime.create_run({"goal": "Retain actual command evidence", "goal_ref": "declared:goal",
                                          "work": command}, self.workspace, self.root / "runs")
        return run_dir, command

    def execute(self, run_dir, command, step="work", timeout=5):
        return runtime.execute_step(run_dir, self.workspace, step, command, timeout, env=self.environment)

    def capture(self, run_dir):
        directory = self.root / ("evidence-" + run_dir.name)
        manifest = observation.capture(run_dir, directory)
        frozen = observation.digest((directory / "manifest.json").read_bytes())
        return directory, manifest, frozen

    def source_bytes(self, run_dir):
        return {path.name: (path.read_bytes(), path.stat().st_mode) for path in run_dir.iterdir() if path.is_file()}

    def test_success_read_only_no_reexecution_and_private_archive(self):
        run_dir, command = self.create("from pathlib import Path; p=Path('count'); p.write_text(p.read_text()+'x' if p.exists() else 'x'); print('actual')")
        self.assertEqual(self.execute(run_dir, command), "passed")
        before = self.source_bytes(run_dir)
        with patch('subprocess.Popen', side_effect=AssertionError('capture attempted execution')):
            directory, manifest, frozen = self.capture(run_dir)
            self.assertEqual(observation.revalidate(directory, frozen, current=True), manifest)
        self.assertEqual((self.workspace / "count").read_text(), "x")
        self.assertEqual(self.source_bytes(run_dir), before)
        self.assertTrue(manifest["selected"]["occurred"])
        self.assertEqual(manifest["selected"]["argv"], command)
        self.assertEqual(manifest["run"]["state"], "unfinished")
        self.assertEqual(manifest["run"]["goal_ref"], "declared:goal")
        self.assertIn("work.json", manifest["unavailable_optional"])
        self.assertEqual((directory / "work.stdout.log").read_bytes(), b"actual\n")
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in directory.iterdir()))
        exported = json.loads((directory / "events.json").read_bytes())
        self.assertEqual([row["sequence"] for row in exported], [1, 2, 3])
        self.assertEqual(json.loads(exported[1]["data_json"])["argv"], command)
        with closing(sqlite3.connect((run_dir / "events.sqlite3").as_uri() + "?mode=ro", uri=True)) as db:
            original_cells = [row[0] for row in db.execute("SELECT data FROM events ORDER BY sequence")]
        self.assertEqual([row["data_json"] for row in exported], original_cells)

    def test_nonzero_failure_retains_exact_binary_outputs(self):
        run_dir, command = self.create("import os; os.write(1,b'partial\\x00\\xff'); os.write(2,b'failed\\n'); raise SystemExit(7)")
        self.assertEqual(self.execute(run_dir, command), "failed")
        directory, manifest, frozen = self.capture(run_dir)
        self.assertTrue(manifest["selected"]["occurred"])
        self.assertEqual(manifest["selected"]["returncode"], 7)
        self.assertEqual((directory / "work.stdout.log").read_bytes(), b"partial\x00\xff")
        self.assertEqual((directory / "work.stderr.log").read_bytes(), b"failed\n")
        observation.revalidate(directory, frozen)

    def test_timeout_preserves_output_and_occurred_execution(self):
        run_dir, command = self.create("import time; print('started',flush=True); time.sleep(30)")
        self.assertEqual(self.execute(run_dir, command, timeout=0.2), "timed_out")
        directory, manifest, frozen = self.capture(run_dir)
        self.assertTrue(manifest["selected"]["occurred"])
        self.assertEqual(manifest["selected"]["state"], "timed_out")
        self.assertIn(b"started", (directory / "work.stdout.log").read_bytes())
        observation.revalidate(directory, frozen)

    def test_spawn_failure_is_not_execution_occurrence(self):
        run_dir, command = self.create(argv=[str(self.root / "missing-executable")])
        self.assertEqual(self.execute(run_dir, command), "failed")
        directory, manifest, frozen = self.capture(run_dir)
        self.assertFalse(manifest["selected"]["occurred"])
        self.assertIsNone(manifest["selected"]["start_sequence"])
        self.assertIsNone(manifest["selected"]["returncode"])
        self.assertTrue(manifest["selected"]["error"])
        self.assertEqual((directory / "work.stdout.log").read_bytes(), b"")
        observation.revalidate(directory, frozen)

    def test_verify_failure_after_success_and_optional_develop_evidence(self):
        run_dir, command = self.create()
        runtime.record(run_dir, "program.started", {"program": "development.change/v1", "client": "pi", "model": "retained-model"})
        self.assertEqual(self.execute(run_dir, command), "passed")
        runtime.record(run_dir, "agent.completed", {"step": "work", "client": "pi", "session_id": "recorded-session", "artifact": "work.md"})
        (run_dir / "work.md").write_bytes(b"Exact report\n")
        (run_dir / "work.json").write_bytes(b'{"session_id":"recorded-session","text":"Exact report"}\n')
        (run_dir / "changes.json").write_bytes(b'{"status":"unavailable","reason":"no baseline"}\n')
        self.assertEqual(self.execute(run_dir, [sys.executable, "-c", "print('bad verification'); raise SystemExit(9)"], step="verify"), "failed")
        runtime.record(run_dir, "run.finished", {"state": "failed"})
        directory, manifest, frozen = self.capture(run_dir)
        self.assertEqual(manifest["selected"]["state"], "passed")
        self.assertEqual(manifest["run"]["state"], "failed")
        self.assertEqual(manifest["run"]["steps"]["verify"]["returncode"], 9)
        self.assertEqual((directory / "work.json").read_bytes(), (run_dir / "work.json").read_bytes())
        self.assertIn(b"recorded-session", (directory / "events.json").read_bytes())
        observation.revalidate(directory, frozen)

    def test_review_evidence_and_acceptance_are_separate_from_selected_act(self):
        run_dir, command = self.create()
        self.execute(run_dir, command)
        runtime.record(run_dir, "run.finished", {"state": "awaiting_review"})
        review = self.root / "review.txt"
        review.write_text("Independent observed evidence\n")
        runtime.review_run(run_dir, "accept", "recorded-reviewer", review)
        directory, manifest, frozen = self.capture(run_dir)
        self.assertEqual(manifest["run"]["state"], "accepted")
        self.assertEqual(manifest["run"]["review"]["evidence"], review.read_text())
        self.assertIn("review.md", manifest["unavailable_optional"])
        observation.revalidate(directory, frozen)

    def test_unfinished_and_reused_step_refuse_unbound_logs(self):
        run_dir, command = self.create()
        runtime.record(run_dir, "step.started", {"step": "work", "argv": command, "stdout": "work.stdout.log", "stderr": "work.stderr.log", "pid": 123})
        with self.assertRaisesRegex(ValueError, "unfinished"):
            self.capture(run_dir)
        second, command = self.create("print('first')")
        self.execute(second, command)
        self.execute(second, [sys.executable, "-c", "print('second')"])
        with self.assertRaisesRegex(ValueError, "repeated"):
            self.capture(second)

    def test_source_drift_equivalent_restore_and_archive_survival(self):
        run_dir, command = self.create()
        self.execute(run_dir, command)
        directory, manifest, frozen = self.capture(run_dir)
        log = run_dir / "work.stdout.log"
        original = log.read_bytes()
        log.write_bytes(b"substituted")
        with self.assertRaisesRegex(ValueError, "drift"):
            observation.revalidate(directory, frozen, current=True)
        observation.revalidate(directory, frozen)
        log.unlink()
        log.write_bytes(original)
        observation.revalidate(directory, frozen, current=True)
        runtime.record(run_dir, "run.finished", {"state": "awaiting_review"})
        with self.assertRaisesRegex(ValueError, "drift"):
            observation.revalidate(directory, frozen, current=True)
        shutil.rmtree(run_dir)
        self.assertEqual(observation.revalidate(directory, frozen), manifest)
        with self.assertRaises(FileNotFoundError):
            observation.revalidate(directory, frozen, current=True)

    def test_wrong_manifest_and_changed_missing_truncated_archive_bytes(self):
        run_dir, command = self.create()
        self.execute(run_dir, command)
        directory, _, frozen = self.capture(run_dir)
        with self.assertRaisesRegex(ValueError, "manifest hash"):
            observation.revalidate(directory, "0" * 64)
        log = directory / "work.stdout.log"
        original = log.read_bytes()
        for changed in (b"other", original[:-1]):
            log.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, "hash/length"):
                observation.revalidate(directory, frozen)
        log.unlink()
        with self.assertRaises(FileNotFoundError):
            observation.revalidate(directory, frozen)

    def test_missing_source_evidence_unsupported_source_and_capture_drift(self):
        absent = self.root / "absent-source"
        with self.assertRaises(FileNotFoundError):
            observation.capture(absent, self.root / "unused")
        self.assertFalse(absent.exists())
        run_dir, command = self.create()
        self.execute(run_dir, command)
        (run_dir / "work.stdout.log").unlink()
        with self.assertRaisesRegex(ValueError, "missing required"):
            self.capture(run_dir)
        unsupported, command = self.create()
        self.execute(unsupported, command)
        runtime.record(unsupported, "program.started", {"program": "controller/v1"})
        with self.assertRaisesRegex(ValueError, "unsupported controller"):
            self.capture(unsupported)
        drift, command = self.create()
        self.execute(drift, command)
        read = observation._read
        changed = False
        def change_after_read(path):
            nonlocal changed
            result = read(path)
            if path == drift / "work.stdout.log" and not changed:
                changed = True
                path.write_bytes(b"changed during snapshot")
            return result
        with patch.object(observation, "_read", side_effect=change_after_read):
            with self.assertRaisesRegex(ValueError, "changed during capture"):
                self.capture(drift)
        self.assertFalse((self.root / ("evidence-" + drift.name)).exists())

    def test_source_metadata_substitution_bounds_and_destination_separation(self):
        run_dir, command = self.create()
        self.execute(run_dir, command)
        with self.assertRaisesRegex(ValueError, "separate"):
            observation.capture(run_dir, run_dir / "archive")
        log = run_dir / "work.stdout.log"
        with log.open('wb') as stream:
            stream.truncate(observation.FILE_LIMIT + 1)
        with self.assertRaisesRegex(ValueError, "bounded regular"):
            self.capture(run_dir)
        log.write_bytes(b"restored")
        with closing(sqlite3.connect(run_dir / "events.sqlite3")) as db:
            finish = runtime.read_events(run_dir)[-1]["data"]
            finish["argv"] = ["substituted"]
            db.execute("UPDATE events SET data=? WHERE kind='step.finished'", (json.dumps(finish),))
            db.commit()
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.capture(run_dir)

    def test_wal_refused_without_source_sidecars_or_missing_database_creation(self):
        run_dir, command = self.create()
        self.execute(run_dir, command)
        with closing(sqlite3.connect(run_dir / "events.sqlite3")) as db:
            db.execute("PRAGMA journal_mode=WAL")
        before = self.source_bytes(run_dir)
        with self.assertRaisesRegex(ValueError, "journal"):
            self.capture(run_dir)
        self.assertEqual(self.source_bytes(run_dir), before)
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaises(FileNotFoundError):
            observation.capture(empty, self.root / "unused")
        self.assertEqual(list(empty.iterdir()), [])

    def test_oversized_serialized_manifest_refuses_before_publication(self):
        run_dir, command = self.create(argv=[sys.executable, "-c", "pass"])
        oversized_argv = command + ["x" * (8 * 1024 * 1024 + 1024)]
        self.assertEqual(self.execute(run_dir, oversized_argv), "failed")
        self.assertFalse(any(event["kind"] == "step.started" for event in runtime.read_events(run_dir)))
        destination = self.root / "unpublished-manifest"
        with self.assertRaisesRegex(ValueError, "manifest.*limit"):
            observation.capture(run_dir, destination)
        self.assertFalse(destination.exists())

    def test_total_limit_includes_manifest_for_capture_and_revalidation(self):
        run_dir, command = self.create(argv=[sys.executable, "-c", "print('real')"])
        self.assertEqual(self.execute(run_dir, command), "passed")
        seed, manifest, _ = self.capture(run_dir)
        base = sum(record["bytes"] for record in manifest["files"].values())
        remaining = observation.TOTAL_LIMIT - base - 512
        optional = ("task.md", "work-prompt.txt", "work.md", "work.json")
        for name in optional:
            size = min(remaining, observation.FILE_LIMIT)
            with (run_dir / name).open("wb") as stream:
                stream.truncate(size)
            remaining -= size
        self.assertEqual(remaining, 0)
        destination = self.root / "unpublished-total"
        with self.assertRaisesRegex(ValueError, "total.*limit"):
            observation.capture(run_dir, destination)
        self.assertFalse(destination.exists())
        # A caller-frozen archive from before the repair must also be refused.
        for name in optional:
            shutil.copyfile(run_dir / name, seed / name)
            content = (seed / name).read_bytes()
            manifest["files"][name] = {"bytes": len(content), "sha256": observation.digest(content)}
            manifest["unavailable_optional"].remove(name)
        raw = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
        (seed / "manifest.json").write_bytes(raw)
        files_bytes = sum(record["bytes"] for record in manifest["files"].values())
        self.assertLess(files_bytes, observation.TOTAL_LIMIT)
        self.assertGreater(files_bytes + len(raw), observation.TOTAL_LIMIT)
        with self.assertRaisesRegex(ValueError, "oversized"):
            observation.revalidate(seed, observation.digest(raw))


if __name__ == "__main__":
    unittest.main()
