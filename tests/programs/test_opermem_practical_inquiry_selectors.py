"""Exact practical-inquiry practical_question_id transport; native eligibility remains native."""
from copy import deepcopy
from pathlib import Path
import os
from subprocess import run
from unittest.mock import Mock
import unittest
from tests.programs import test_opermem_parent_selectors as parent_fixture
from scripts import noetic_opermem_application as reviewed

ROOT = Path(__file__).resolve().parents[2]


class PracticalInquirySelectorTests(unittest.TestCase):
    setUp = parent_fixture.ParentSelectorTests.setUp

    def body(self, question):
        body = parent_fixture.ParentSelectorTests.body(self, 'practical-inquiry', None)
        body['selectors'] = {'practical_question_id': question}
        return body

    def test_exact_high_u64_survives_freeze_args_and_replay(self):
        body = self.body('9007199254740993')
        original = deepcopy(body)
        frozen = self.service.preflight(body)
        exact = {'practical_question_id': 9007199254740993}
        self.assertEqual(frozen['body']['selectors'], exact)
        self.assertEqual(frozen['native_purpose'], {'operation': 'practical-inquiry', **exact})
        self.assertIs(type(frozen['body']['selectors']['practical_question_id']), int)
        self.assertIs(type(frozen['native_purpose']['practical_question_id']), int)
        args = reviewed.args_for(self.root, frozen)
        self.assertEqual(args.practical_question_id, exact['practical_question_id'])
        self.assertIs(type(args.practical_question_id), int)
        self.assertEqual(self.service.preflight(frozen['body']), frozen)
        self.assertEqual(body, original)
        directory = self.service.launch_dir('fixture')
        directory.mkdir(parents=True)
        self.service.retained_command = Mock(side_effect=lambda directory, body: body)
        retained = self.service.start(body)
        self.assertEqual(retained['selectors'], {'practical_question_id': 9007199254740993})
        self.assertEqual(body, original)

    def test_max_u64_exact(self):
        body = self.body('18446744073709551615')
        frozen = self.service.preflight(body)
        self.assertEqual(frozen['body']['selectors'], {'practical_question_id': 18446744073709551615})
        self.assertEqual(frozen['native_purpose']['practical_question_id'], 18446744073709551615)

    def test_invalid_scalars_collections_rejected(self):
        for value in ['0', '01', '+1', '-1', '1e2', '1.0', ' 1', '１', str(2**64), True, 1.0, 2**64,
                      ['9007199254740993'], None, {'practical_question_id': 1}]:
            with self.subTest(question=value), self.assertRaises(ValueError):
                self.service.preflight(self.body(value))
        body = parent_fixture.ParentSelectorTests.body(self, 'practical-inquiry', None)
        body['selectors'] = {'parent_id': '1'}
        with self.assertRaises(ValueError):
            self.service.preflight(body)

    @unittest.skipUnless(os.environ.get('NOETIC_TEST_CHROMIUM'), 'requires explicit browser fixture runtime')
    def test_browser_editor_subprocess(self):
        env = dict(os.environ)
        env.pop('USER_PROVIDED_PASSWORD', None)
        target = ROOT / 'tests' / 'programs' / 'opermem_practical_inquiry_editor.cjs'
        completed = run(['node', str(target)], cwd=str(ROOT), env=env, shell=False,
                        capture_output=True, text=True, timeout=90)
        output = (completed.stdout + '\n' + completed.stderr)[-2000:]
        print(output)
        self.assertEqual(completed.returncode, 0, f'browser editor fixture failed:\n{output}')


if __name__ == '__main__':
    unittest.main()
