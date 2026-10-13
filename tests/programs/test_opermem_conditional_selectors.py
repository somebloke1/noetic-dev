"""Exact two-anchor transport; native conditional admission remains native."""
from copy import deepcopy
from unittest.mock import Mock
import unittest
from tests.programs import test_opermem_parent_selectors as parent_fixture
from scripts import noetic_opermem_application as reviewed

class ConditionalSelectorTests(unittest.TestCase):
    setUp = parent_fixture.ParentSelectorTests.setUp

    def body(self, reflection, formulation):
        body = parent_fixture.ParentSelectorTests.body(self, 'conditional-structure', reflection)
        body['selectors']['formulation_id'] = formulation
        return body

    def test_exact_two_anchors_survive_freeze_args_and_replay(self):
        body = self.body(str(2**64-1), str(2**53+1))
        original = deepcopy(body)
        frozen = self.service.preflight(body)
        exact = {'parent_id': 2**64-1, 'formulation_id': 2**53+1}
        self.assertEqual(frozen['body']['selectors'], exact)
        self.assertEqual(frozen['native_purpose'], {'operation':'conditional-structure', 'reflection_id':2**64-1, 'formulation_id':2**53+1})
        args = reviewed.args_for(self.root, frozen)
        self.assertEqual((args.parent_id, args.formulation_id), (2**64-1, 2**53+1))
        self.assertEqual(self.service.preflight(frozen['body']), frozen)
        directory = self.service.launch_dir('fixture'); directory.mkdir(parents=True)
        self.service.retained_command = Mock(side_effect=lambda directory, body: body)
        self.assertEqual(self.service.start(body)['selectors'], exact)
        self.assertEqual(body, original)

    def test_both_anchors_reject_invalid_transport_values(self):
        for value in ['0','01','+1','-1','1e2','1.0',' 1','１',str(2**64),True,1.0,2**64,None]:
            with self.subTest(reflection=value), self.assertRaises(ValueError):
                self.service.preflight(self.body(value, '2'))
            with self.subTest(formulation=value), self.assertRaises(ValueError):
                self.service.preflight(self.body('1', value))
        self.assertEqual(self.service.preflight(self.body(1, 2))['body']['selectors'], {'parent_id':1,'formulation_id':2})

if __name__ == '__main__': unittest.main()
