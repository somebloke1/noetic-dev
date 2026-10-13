"""Deliberation exact explicit complete-set transport; native standing stays native."""
from copy import deepcopy
from pathlib import Path
import os
from subprocess import run
from unittest.mock import Mock
import unittest
from tests.programs import test_opermem_parent_selectors as parent_fixture
from scripts import noetic_opermem_application as reviewed

ROOT = Path(__file__).resolve().parents[2]

class DeliberationSelectorTests(unittest.TestCase):
    setUp = parent_fixture.ParentSelectorTests.setUp

    def body(self, question, options):
        body = parent_fixture.ParentSelectorTests.body(self, 'deliberation', None)
        body['selectors'] = {'practical_question_id': question, 'option_ids': options}
        return body

    def test_exact_u64_set_survives_freeze_args_replay_and_retained_request(self):
        body = self.body('9007199254740993', ['9007199254740994', '18446744073709551615'])
        original = deepcopy(body)
        frozen = self.service.preflight(body)
        exact = {'practical_question_id': 9007199254740993, 'option_ids': [9007199254740994, 18446744073709551615]}
        self.assertEqual(frozen['body']['selectors'], exact)
        self.assertEqual(frozen['native_purpose'], {'operation': 'deliberation', **exact})
        args = reviewed.args_for(self.root, frozen)
        self.assertEqual(args.practical_question_id, exact['practical_question_id'])
        self.assertEqual(args.option_ids, exact['option_ids'])
        self.assertTrue(all(type(value) is int for value in args.option_ids))
        self.assertEqual(self.service.preflight(frozen['body']), frozen)
        self.assertEqual(body, original)
        self.service.launch_dir('fixture').mkdir(parents=True)
        self.service.retained_command = Mock(side_effect=lambda directory, body: body)
        self.assertEqual(self.service.start(body)['selectors'], exact)
        self.assertEqual(body, original)

    def test_invalid_question_and_noncomplete_format_reject_before_launch(self):
        for value in [None, True, 1.0, '0', '01', '+1', '1e2', ' 1', str(2**64), ['1']]:
            with self.subTest(question=value), self.assertRaises(ValueError):
                self.service.preflight(self.body(value, ['1', '2']))
        for options in [None, '1', {'ids': ['1', '2']}, [], ['1'], ['2', '1'], ['1', '1'],
                        ['0', '1'], ['01', '2'], ['1', str(2**64)], [True, '2'], [1.0, '2'], ['1e2', '200']]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.service.preflight(self.body('9007199254740993', options))
        parent_only = self.body('1', ['1', '2'])
        parent_only['selectors'] = {'parent_id': '1', 'option_ids': ['1', '2']}
        with self.assertRaises(ValueError):
            self.service.preflight(parent_only)

    @unittest.skipUnless(os.environ.get('NOETIC_TEST_CHROMIUM'), 'requires explicit browser fixture runtime')
    def test_required_browser_transport(self):
        env = dict(os.environ)
        env.pop('USER_PROVIDED_PASSWORD', None)
        completed = run(['node', str(ROOT / 'tests/programs/opermem_deliberation_editor.cjs')],
                        cwd=str(ROOT), env=env, shell=False, capture_output=True, text=True, timeout=90)
        output = (completed.stdout + '\n' + completed.stderr)[-2000:]
        print(output)
        self.assertEqual(completed.returncode, 0, output)

if __name__ == '__main__':
    unittest.main()
