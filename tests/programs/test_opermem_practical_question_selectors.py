"""Exact practical-question judgment_ids transport; native eligibility remains native."""
from copy import deepcopy
from unittest.mock import Mock
import unittest
from tests.programs import test_opermem_parent_selectors as parent_fixture
from scripts import noetic_opermem_application as reviewed


class PracticalQuestionSelectorTests(unittest.TestCase):
    setUp = parent_fixture.ParentSelectorTests.setUp

    def body(self, judgment_ids):
        body = parent_fixture.ParentSelectorTests.body(self, 'practical-question', None)
        body['selectors'] = {'judgment_ids': judgment_ids}
        return body

    def test_exact_high_u64_subset_survives_freeze_args_and_replay(self):
        body = self.body(['9007199254740993', '18446744073709551615'])
        original = deepcopy(body)
        frozen = self.service.preflight(body)
        exact = {'judgment_ids': [9007199254740993, 18446744073709551615]}
        self.assertEqual(frozen['body']['selectors'], exact)
        self.assertEqual(frozen['native_purpose'], {'operation': 'practical-question', **exact})
        self.assertIs(type(frozen['body']['selectors']['judgment_ids'][0]), int)
        self.assertIs(type(frozen['native_purpose']['judgment_ids'][0]), int)
        args = reviewed.args_for(self.root, frozen)
        self.assertEqual(args.judgment_ids, exact['judgment_ids'])
        self.assertIs(type(args.judgment_ids[0]), int)
        self.assertEqual(self.service.preflight(frozen['body']), frozen)
        self.assertEqual(body, original)
        directory = self.service.launch_dir('fixture')
        directory.mkdir(parents=True)
        self.service.retained_command = Mock(side_effect=lambda directory, body: body)
        retained = self.service.start(body)
        self.assertEqual(retained['selectors'], exact)
        self.assertEqual(body, original)

    def test_invalid_scalars_collections_and_order_rejected(self):
        invalid = ['0', '01', '+1', '-1', '1e2', '1.0', ' 1', '１', str(2**64), True, 1.0, 2**64]
        for value in invalid:
            with self.subTest(judgment=value), self.assertRaises(ValueError):
                self.service.preflight(self.body([value, str(2**64 - 1)]))
        for values in [[], '1', None, True, 9007199254740993, {'judgment_ids': [1]}, ['2', '1'], ['1', '1'], ['1,2']]:
            with self.subTest(judgments=values), self.assertRaises(ValueError):
                self.service.preflight(self.body(values))
        self.assertEqual(self.service.preflight(self.body([2**53 + 1, 2**64 - 2]))['native_purpose']['judgment_ids'],
                         [2**53 + 1, 2**64 - 2])


if __name__ == '__main__':
    unittest.main()
