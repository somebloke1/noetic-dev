"""Exact decimal selector transport; native eligibility remains native."""
from copy import deepcopy
from unittest.mock import Mock
import unittest
from tests.programs import test_opermem_parent_selectors as parent_fixture
from scripts import noetic_opermem_application as reviewed

class JudgmentSelectorTests(unittest.TestCase):
    setUp = parent_fixture.ParentSelectorTests.setUp

    def body(self, warrant, conditions):
        body=parent_fixture.ParentSelectorTests.body(self,'judgment',None)
        body['selectors']={'warrant_id':warrant,'condition_ids':conditions}
        return body

    def test_exact_set_survives_freeze_args_and_replay(self):
        body=self.body(str(2**64-1),[str(2**53+1),str(2**64-1)])
        original=deepcopy(body);frozen=self.service.preflight(body)
        exact={'warrant_id':2**64-1,'condition_ids':[2**53+1,2**64-1]}
        self.assertEqual(frozen['body']['selectors'],exact)
        self.assertEqual(frozen['native_purpose'],{'operation':'judgment',**exact})
        args=reviewed.args_for(self.root,frozen)
        self.assertEqual(args.warrant_id,exact['warrant_id'])
        self.assertEqual(args.condition_ids,exact['condition_ids'])
        self.assertEqual(self.service.preflight(frozen['body']),frozen)
        self.assertEqual(body,original)
        directory=self.service.launch_dir('fixture');directory.mkdir(parents=True)
        self.service.retained_command=Mock(side_effect=lambda directory,body:body)
        retained=self.service.start(body)
        self.assertEqual(retained['selectors'],exact)
        self.assertEqual(body,original)

    def test_invalid_scalars_and_complete_sets_rejected(self):
        invalid=['0','01','+1','-1','1e2','1.0',' 1','１',str(2**64),True,1.0,2**64]
        for value in invalid:
            with self.subTest(warrant=value),self.assertRaises(ValueError):
                self.service.preflight(self.body(value,['1']))
            with self.subTest(condition=value),self.assertRaises(ValueError):
                self.service.preflight(self.body('1',[value]))
        for values in [[],['2','1'],['1','1'],'1,2',None]:
            with self.subTest(conditions=values),self.assertRaises(ValueError):
                self.service.preflight(self.body('1',values))
        self.assertEqual(self.service.preflight(self.body(1,[2,3]))['native_purpose']['condition_ids'],[2,3])

if __name__=='__main__':unittest.main()
