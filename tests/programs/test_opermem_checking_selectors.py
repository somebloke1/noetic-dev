"""Checking selector transport and closed-evidence preflight; local fixture only.

These fixtures stand in for the retained whole native context; native admission
and real host capture remain covered by the native-boundary tests
(test_noetic_opermem_checking.py with OPERMEM_OPERATION_HOST).
"""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
from unittest.mock import Mock
import unittest

from tests.programs import test_opermem_parent_selectors as parent_fixture
from scripts import noetic_opermem_application as reviewed
from scripts import noetic_opermem_checking as checking


def fixture_context(condition_id, warrant_id, text="Exact bounded checking predicate"):
    """Local copy of the native-context fixture parameterized by exact anchors."""
    cut = {"authority_generation": 9}
    payload = {"conditions": [text]}

    def item(kind, identity, voice):
        content = {"command": {"payload": payload}, "id": {"kind": kind, "id": identity}}
        return {"residue_id": {"kind": kind, "id": identity}, "kind": kind,
                "object_version": 1, "liveness": "live", "content": content,
                "content_sha256": checking.digest(checking.canonical(content)),
                "pinned_cut_binding": cut, "retrieval_voice": voice, "ancestry": []}

    condition = item("warrant-condition", condition_id, {"text": text, "state": "unchecked"})
    warrant = item("warrant", warrant_id, {"conditions": [text]})
    condition["ancestry"] = [{"kind": "has-condition", "other": warrant["residue_id"], "endpoint_role": "to"}]
    return {"operation": "checking", "pinned_canonical_cut": cut,
            "supplied_whole_residues": [warrant, condition]}


class CheckingSelectorTests(parent_fixture.ParentSelectorTests):
    def setUp(self):
        super().setUp()
        self.evidence = tempfile.TemporaryDirectory(prefix='checking-evidence-')
        self.addCleanup(self.evidence.cleanup)
        self.evidence_root = Path(self.evidence.name)
        self.condition_id, self.warrant_id = 2**64 - 1, 2**64 - 2
        self.spec_path, self.context_path = self.write_evidence()

    def write_evidence(self, condition_id=None, warrant_id=None):
        condition_id = self.condition_id if condition_id is None else condition_id
        warrant_id = self.warrant_id if warrant_id is None else warrant_id
        context = fixture_context(condition_id, warrant_id)
        context_path = self.evidence_root / 'context.json'
        context_path.write_bytes(checking.canonical(context))
        module = self.evidence_root / 'bounded_case.py'
        module.write_text("import unittest\nclass ExactCase(unittest.TestCase):\n    def test_exact(self):\n        assert 2 + 2 == 4\n")
        runner = Path(checking.__file__).with_name('noetic_checking_tests.py').resolve()
        python = Path(sys.executable).resolve()
        test_id = 'bounded_case.ExactCase.test_exact'
        sources = [{"path": str(path), "sha256": checking.digest(path.read_bytes()), "role": role}
                   for path, role in ((python, "actual Python"), (runner, "actual test runner"), (module, "bounded assertions"))]
        spec = {"version": checking.SPEC_VERSION,
                "condition": checking.binding(context, condition_id, warrant_id),
                "command": {"argv": [str(python), str(runner), "--module-dir", str(self.evidence_root), test_id],
                            "cwd": str(self.evidence_root), "timeout_seconds": 10,
                            "environment": {"LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}},
                "selected_tests": [test_id],
                "predicates": [{"id": "exact", "test_ids": [test_id], "expected_observation": "actual assertion succeeds"}],
                "sources": sources, "scope": "Only the exact executed assertion."}
        spec_path = self.evidence_root / 'spec.json'
        spec_path.write_bytes(checking.canonical(spec))
        return spec_path, context_path

    def body(self, operation='checking', identity=None):
        if operation != 'checking':
            return parent_fixture.ParentSelectorTests.body(self, operation, identity)
        body = parent_fixture.ParentSelectorTests.body(self, 'checking', str(self.condition_id))
        body['workspace'] = str(self.evidence_root)
        body['selectors']['warrant_id'] = str(self.warrant_id)
        body['checking_spec'] = str(self.spec_path)
        body['checking_context'] = str(self.context_path)
        return body

    def test_exact_anchors_survive_freeze_args_and_replay(self):
        body = self.body(); original = deepcopy(body)
        frozen = self.service.preflight(body)
        exact = {'parent_id': self.condition_id, 'warrant_id': self.warrant_id}
        self.assertEqual(frozen['body']['selectors'], exact)
        self.assertEqual(frozen['native_purpose'], {'operation': 'checking', 'warrant_id': self.warrant_id, 'condition_id': self.condition_id})
        self.assertEqual(frozen['operation_evidence']['paths'], {'checking_spec': str(self.spec_path), 'checking_context': str(self.context_path)})
        directory = self.root / 'checking'; directory.mkdir(mode=0o700)
        args = reviewed.args_for(directory, frozen)
        self.assertEqual((args.parent_id, args.warrant_id), (self.condition_id, self.warrant_id))
        self.assertEqual(args.checking_spec, self.spec_path)
        self.assertEqual(self.service.preflight(frozen['body']), frozen)
        self.assertEqual(body, original)
        launch = self.service.launch_dir('fixture'); launch.mkdir(parents=True)
        self.service.retained_command = Mock(side_effect=lambda directory, body: body)
        retained = self.service.start(body)
        self.assertEqual(retained['selectors'], exact)
        self.assertEqual(body, original)

    def test_mismatch_and_drift_rejected_without_launch(self):
        self.service.start = Mock(side_effect=AssertionError('no launch on rejection'))
        mismatched = self.body(); mismatched['selectors']['parent_id'] = '999'
        with self.assertRaises(ValueError):
            self.service.preflight(mismatched)
        context_path = self.evidence_root / 'drift-context.json'
        context = fixture_context(self.condition_id, self.warrant_id)
        context['supplied_whole_residues'][0]['object_version'] = 2
        context_path.write_bytes(checking.canonical(context))
        drifted = self.body(); drifted['checking_context'] = str(context_path)
        with self.assertRaises(ValueError):
            self.service.preflight(drifted)
        module = self.evidence_root / 'bounded_case.py'
        original = module.read_bytes(); module.write_text(original.decode() + "\n")
        try:
            with self.assertRaisesRegex(ValueError, 'changed before effects'):
                self.service.preflight(self.body())
        finally:
            module.write_bytes(original)

    def test_invalid_scalars_rejected(self):
        for value in ['0', '01', '-1', '1e2', '1.0', ' 1', str(2**64), True, 1.0, 2**64]:
            body = self.body(); body['selectors']['warrant_id'] = value
            with self.subTest(warrant=value), self.assertRaises(ValueError):
                self.service.preflight(body)
            body = self.body(); body['selectors']['parent_id'] = value
            with self.subTest(condition=value), self.assertRaises(ValueError):
                self.service.preflight(body)


if __name__ == '__main__':
    unittest.main()
