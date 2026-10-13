"""Fresh native Checking preparation: closed recipes, exact native binding, no execution."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts import noetic_opermem as bridge
from scripts import noetic_opermem_checking as checking
from scripts.noetic_opermem_application import ReviewedApplication
from scripts.noetic_scope import ScopeError

REPO = Path(__file__).resolve().parents[2]
HOST = os.environ.get("OPERMEM_OPERATION_HOST")
REAL_TEST = "tests.programs.test_noetic_opermem_checking.CheckingCaptureTests.test_missing_selected_test_cannot_fulfill"
OTHER_TEST = "tests.programs.test_noetic_opermem_checking.CheckingCaptureTests.test_closed_bindings_reject_before_execution"


def native_warrant(binary, store, transcripts, text="Exact bounded checking predicate"):
    """Compose the existing native boundary prerequisites: question to conditional-structure."""
    parent = formulation = None
    for operation, contribution, role in [
            ("question", {"question_kind": "how", "text": "How is checking bounded?"}, "question"),
            ("insight", {"text": "Trace: exact test evidence may answer a condition."}, "unverified insight trace"),
            ("formulation", {"text": "Hypothesis: native checking retains exact evidence."}, "versioned formulation/hypothesis"),
            ("reflection", {"text": "Is this hypothesis correct?"}, "reflection question")]:
        response, _ = bridge.submit(binary, store, transcripts, operation, parent, contribution,
                                    "prep-fixture-" + operation)
        parent = next(o["id"] for o in response["payload"]["outputs"] if o["role"] == role)
        if operation == "formulation":
            formulation = parent
    response, _ = bridge.submit(binary, store, transcripts, "conditional-structure", parent,
                                {"conditions": [text]}, "prep-fixture-warrant", formulation_id=formulation)
    warrant = next(o["id"] for o in response["payload"]["outputs"] if o["role"] == "warrant")
    condition = next(o["id"] for o in response["payload"]["outputs"] if o["kind"] == "warrant-condition")
    context, _ = bridge.retrieve(binary, store, transcripts,
                                 bridge.purpose_for("checking", condition, warrant_id=warrant))
    return condition, warrant, context


class PrepareRecipeValidationTests(unittest.TestCase):
    def test_malformed_recipes_fail_before_native_or_output(self):
        base = {"command": {"argv": ["/bin/true"], "cwd": "/tmp", "timeout_seconds": 10, "environment": {}},
                "selected_tests": ["x"], "predicates": [{"id": "p", "test_ids": ["x"], "expected_observation": "o"}],
                "sources": [{"path": "/bin/true", "role": "r"}], "scope": "s"}
        output = Path(self.enterContext(tempfile.TemporaryDirectory())) / "fresh"
        def mutation(recipe):
            changed = json.loads(json.dumps(base))
            recipe(changed)
            return changed
        cases = [lambda r: r.pop("scope"), lambda r: r.update(extra=1),
                 lambda r: r["command"].pop("environment"),
                 lambda r: r["command"].update(timeout_seconds=0),
                 lambda r: r["command"].update(timeout_seconds=901),
                 lambda r: r["command"].update(argv=[]),
                 lambda r: r["command"].update(argv=[1]),
                 lambda r: r["command"].update(environment=[]),
                 lambda r: r.update(selected_tests="x"),
                 lambda r: r["predicates"][0].update(test_ids="x")]
        for recipe in cases:
            with self.assertRaises(ValueError):
                checking.prepare(mutation(recipe), 20, 10, output, host=None, store=None, transcripts=None)
        self.assertFalse(output.exists())

    def test_cli_rejects_duplicate_environment_names(self):
        stub = Path(sys.executable)
        argv = ["--host", str(stub), "--store", "/tmp/prep-store", "--runs-dir", "/tmp/prep-runs",
                "prepare-checking", "--parent-id", "20", "--warrant-id", "10", "--output", "/tmp/prep-out",
                "--cwd", "/tmp", "--scope", "s", "--environment", "A", "1", "--environment", "A", "2",
                "--test", "t", "--predicate", "p", "o", "t", "--source", "/bin/true", "r",
                "--command", "/bin/true"]
        with self.assertRaises(SystemExit) as raised:
            with redirect_stderr(io.StringIO()):
                bridge.main(argv)
        self.assertEqual(raised.exception.code, 2)


def redirect_output(stream):
    return redirect_stdout(stream)


@unittest.skipUnless(HOST, "requires QA-accepted actual Rust host")
class NativeCheckingPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.binary = Path(HOST).resolve()
        self.store = self.root / "store"
        self.transcripts = self.root / "transcripts"
        self.runs = self.root / "runs"
        self.condition, self.warrant, self.context = native_warrant(
            self.binary, self.store, self.transcripts)
        self.python = Path(sys.executable).resolve()
        self.runner = Path(checking.__file__).with_name("noetic_checking_tests.py").resolve()

    def cli(self, output, *, project=None, tests=(REAL_TEST, "required.unexecuted.test"), predicates=None,
            parent=None, warrant=None, run_tests=None, sources=()):
        project = Path(project) if project else REPO
        argv = [str(self.python), str(self.runner)]
        for module_dir in (project, project / "tests" / "programs"):
            argv += ["--module-dir", str(module_dir)]
        argv += list(run_tests if run_tests is not None else tests)
        predicates = predicates or [
            ("exact", "actual selected identity passes", [tests[0]]),
            ("unexecuted", "never-observed selected test stays indeterminate", ["required.unexecuted.test"])]
        command = ["--host", str(self.binary), "--store", str(self.store), "--runs-dir", str(self.runs),
                   "prepare-checking", "--parent-id", str(self.condition if parent is None else parent),
                   "--warrant-id", str(self.warrant if warrant is None else warrant),
                   "--output", str(output), "--cwd", str(project),
                   "--scope", "Only the exact selected unittest identities in this repository.",
                   "--timeout-seconds", "10", "--environment", "LANG", "C.UTF-8",
                   "--environment", "PYTHONDONTWRITEBYTECODE", "1"]
        for test in tests:
            command += ["--test", test]
        for identifier, expected, test_ids in predicates:
            command += ["--predicate", identifier, expected, *test_ids]
        fixed = [(self.python, "actual Python"), (self.runner, "actual test runner"),
                 (REPO / "scripts" / "noetic_opermem.py", "native bridge"),
                 (REPO / "scripts" / "noetic_opermem_checking.py", "checking module"),
                 (REPO / "tests" / "programs" / "test_noetic_opermem_checking.py", "selected identities")]
        for path, role in (*fixed, *sources):
            command += ["--source", str(path), role]
        command += ["--command", *argv]
        captured = io.StringIO()
        with patch.object(checking.subprocess, "run", side_effect=AssertionError("preparation must not execute the checking command")), \
             patch.object(bridge, "submit", side_effect=AssertionError("preparation must not submit natively")):
            with redirect_output(captured):
                code = bridge.main(command)
        self.assertEqual(code, 0)
        return json.loads(captured.getvalue())

    def test_prepares_closed_spec_inner_context_and_receipt_without_execution(self):
        output = self.root / "fresh"
        reported = self.cli(output)
        self.assertEqual(reported["prepared"], True)
        self.assertEqual(reported["spec_sha256"], checking.digest((output / "spec.json").read_bytes()))
        self.assertEqual(reported["context_sha256"], checking.digest((output / "context.json").read_bytes()))
        spec = checking.load(output / "spec.json")
        context = checking.load(output / "context.json")
        self.assertEqual(context["operation"], "checking")
        self.assertIn("supplied_whole_residues", context)
        checking.validate_spec(spec, context, self.condition, self.warrant)
        self.assertEqual(spec["condition"]["id"], self.condition)
        self.assertEqual(spec["condition"]["warrant_id"], self.warrant)
        for identity in (self.condition, self.warrant):
            self.assertIs(type(identity), int)
            self.assertTrue(0 < identity < 2**64)
        self.assertEqual(spec["command"]["argv"][0], str(self.python))
        self.assertEqual(spec["command"]["cwd"], str(REPO))
        self.assertEqual(len(set(spec["selected_tests"])), len(spec["selected_tests"]))
        receipt = checking.load(output / "preparation.json")
        self.assertEqual(receipt["version"], checking.PREPARATION_VERSION)
        self.assertEqual(receipt["selected_native_route"],
                         {"host": str(self.binary), "store": str(self.store.resolve())})
        self.assertIn("no checking command was executed during preparation", receipt["explicit_limits"][0])
        self.assertTrue(Path(receipt["context_transcript"]).exists())

    def test_existing_output_rejected_and_unchanged(self):
        output = self.root / "existing"
        output.mkdir(mode=0o700)
        (output / "sentinel.txt").write_text("kept")
        with self.assertRaises(FileExistsError):
            self.cli(output)
        self.assertEqual((output / "sentinel.txt").read_text(), "kept")
        self.assertFalse((output / "spec.json").exists())

    def test_invalid_anchors_or_coverage_fail_before_output(self):
        output = self.root / "never"
        with self.assertRaises((ValueError, RuntimeError)):
            self.cli(output, parent=self.warrant)
        self.assertFalse(output.exists())
        with self.assertRaisesRegex(ValueError, "predicate"):
            self.cli(output, predicates=[("exact", "partial mapping", [REAL_TEST])])
        self.assertFalse(output.exists())

    def test_capture_on_prepared_spec_keeps_unexecuted_selected_test_indeterminate(self):
        output = self.root / "fresh"
        self.cli(output, tests=(REAL_TEST, OTHER_TEST), run_tests=(REAL_TEST,),
                 predicates=[("exact", "actual selected identity passes", [REAL_TEST, OTHER_TEST])])
        spec = output / "spec.json"
        evidence = self.root / "evidence"
        manifest = checking.capture(spec, self.context, self.condition, self.warrant, evidence)
        self.assertEqual(manifest["result"], "indeterminate")
        self.assertEqual(manifest["counts"], {"selected": 2, "observed": 1, "executed": 1,
                                              "passed": 1, "failed": 0, "error": 0, "skipped": 0})
        observations = json.loads((evidence / "stdout.bin").read_bytes())
        self.assertEqual(observations["version"], checking.OBS_VERSION)
        self.assertEqual(checking.revalidate(evidence, self.context)["result"], "indeterminate")

    def test_application_operation_evidence_accepts_prepared_pair_and_rejects_stale_source(self):
        project = self.root / "project"
        (project / "tests" / "programs").mkdir(mode=0o700, parents=True)
        (project / "tests" / "programs" / "__init__.py").write_text("")
        module = project / "bounded_case.py"
        module.write_text("import unittest\nclass ExactCase(unittest.TestCase):\n    def test_exact(self):\n        assert 2 + 2 == 4\n")
        output = self.root / "fresh"
        test = "bounded_case.ExactCase.test_exact"
        self.cli(output, project=project, tests=(test,),
                 predicates=[("exact", "actual assertion succeeds", [test])],
                 sources=((module, "fixture assertions"),))
        reviewed = ReviewedApplication.__new__(ReviewedApplication)
        reviewed.app = SimpleNamespace(root=self.root / "elsewhere", run_authority=lambda *a, **k: None)
        body = {"operation": "checking", "checking_spec": str(output / "spec.json"),
                "checking_context": str(output / "context.json"), "workspace": str(project)}
        purpose = {"condition_id": self.condition, "warrant_id": self.warrant}
        evidence = reviewed.operation_evidence(body, {"effort_root": "0.0"}, purpose, None)
        self.assertEqual(set(evidence["paths"]), {"checking_spec", "checking_context"})
        module.write_text(module.read_text() + "\n# stale\n")
        with self.assertRaisesRegex(ScopeError, "changed before effects"):
            reviewed.operation_evidence(body, {"effort_root": "0.0"}, purpose, None)


def redirect_output(stream):
    return redirect_stdout(stream)
