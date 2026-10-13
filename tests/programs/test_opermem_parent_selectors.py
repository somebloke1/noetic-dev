"""Application selector transport only; native standing remains native."""
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import noetic_opermem_application as reviewed


class ParentSelectorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='parent-selector-'); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.service = reviewed.ReviewedApplication.__new__(reviewed.ReviewedApplication)
        self.service.app = SimpleNamespace(root=self.root, namespace_path=self.root/'namespace.sqlite3', mutation=nullcontext)
        self.ref = {'id':'backing', 'host':str(self.root/'host'), 'directory':str(self.root/'native'), 'effort_root':'0.0'}
        self.service.adapter = SimpleNamespace(validate_request=lambda *a:None, validate_store=lambda ref,*a:ref)
        self.service.registrations = lambda selection:{'stores':[{'store_ref':self.ref}]}
        for target,value in [('host_configuration', {'available':True,'host':str(self.root/'host'),'child':str(self.root/'child')})]:
            context=patch.object(reviewed,target,return_value=value);context.start();self.addCleanup(context.stop)
        context=patch.object(reviewed.native,'_private_selection');context.start();self.addCleanup(context.stop)

    def body(self, operation, identity):
        return {'command_id':'fixture','effort_root':'0.0','discipline_id':'fixture-discipline','task':'Examine selected source.',
                'workspace':str(self.root),'store_id':'backing','operation':operation,'selectors':{'parent_id':identity}}

    def test_full_u64_survives_freeze_args_and_restart(self):
        for operation,key in [('insight','question_id'),('formulation','insight_id'),('reflection','formulation_id')]:
            with self.subTest(operation=operation):
                body=self.body(operation,str(2**64-1)); original=deepcopy(body)
                frozen=self.service.preflight(body)
                self.assertEqual(frozen['body']['selectors']['parent_id'],2**64-1)
                self.assertEqual(frozen['native_purpose'][key],2**64-1)
                directory=self.root/operation;directory.mkdir(mode=0o700)
                args=reviewed.args_for(directory,frozen)
                self.assertEqual(args.parent_id,2**64-1)
                self.assertEqual(self.service.preflight(frozen['body']),frozen)
                self.assertEqual(body,original)

    def test_invalid_decimal_and_out_of_range_fail(self):
        for identity in ['0','-1','+1','1.0','1e3',' 1','01','１',str(2**64),True,1.0,2**64]:
            with self.subTest(identity=identity),self.assertRaises(ValueError):
                self.service.preflight(self.body('insight',identity))
        self.assertEqual(self.service.preflight(self.body('insight',1))['native_purpose']['question_id'],1)

    def test_repeated_start_normalizes_before_retained_comparison(self):
        body=self.body('reflection',str(2**53+1)); directory=self.service.launch_dir('fixture');directory.mkdir(parents=True)
        self.service.retained_command=Mock(side_effect=lambda directory,body:body)
        result=self.service.start(body)
        self.assertEqual(result['selectors']['parent_id'],2**53+1)
        self.assertEqual(body['selectors']['parent_id'],str(2**53+1))
        self.assertEqual(self.service.retained_command.call_count,1)


if __name__=='__main__':unittest.main()
