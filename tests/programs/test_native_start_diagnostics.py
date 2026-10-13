"""Retained startup mismatch diagnostics without provider execution."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from scripts import noetic_sessions as sessions


FAKE_PI = r'''
import json, pathlib, sys
args=sys.argv[1:]
def option(name): return args[args.index(name)+1]
sid=option('--session-id');model=option('--model')
case=option('--case')
if case=='exit': raise SystemExit(7)
path=pathlib.Path(option('--session-dir'))/(sid+'.jsonl')
def emit(value): print(json.dumps(value),flush=True)
for line in sys.stdin:
    request=json.loads(line);kind=request['type']
    data={}
    if kind=='get_state':
        observed='amazon-bedrock/us.openai.gpt-5.6-luna' if model=='luna' else model
        provider,mid=observed.split('/',1)
        data={'sessionId':'wrong-native' if case=='native' else sid,'sessionFile':str(path),'model':{'provider':provider,'id':mid},'isStreaming':False,'pendingMessageCount':0}
    emit({'type':'response','id':request.get('id'),'command':kind,'success':True,'data':data})
    if kind=='prompt': emit({'type':'agent_settled'})
'''


class NativeStartDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='start-diagnostics-');self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name);self.cwd=self.home/'work';self.cwd.mkdir(mode=0o700)
        subprocess.run(['git','init','-q',str(self.cwd)],check=True)
        self.fixture=self.home/'fake.py';self.fixture.write_text(FAKE_PI)
        self.service=sessions.SessionService(self.home/'runs',pi_command=[sys.executable,str(self.fixture),'--case','normal'],namespace_path=self.home/'namespace.sqlite3')
        self.effort=self.service.create_effort({'intent':'Fixture','environment':{'cwd':str(self.cwd)}})['ordinal']

    def tearDown(self):
        for item in self.service.list():
            if item['broker_owned']:
                self.service.shutdown(item['id'])
        deadline=time.monotonic()+8
        while any(item['broker_owned'] for item in self.service.list()) and time.monotonic()<deadline:time.sleep(.02)
        for item in self.service.list():
            self.assertFalse(item['broker_owned'])
            directory=sessions.socket_path(self.service.runs_root,item['id']).parent
            (directory/'control.sock').unlink(missing_ok=True);directory.rmdir()

    def start(self,model):
        return self.service.create({'effort_root':self.effort,'prompt':'Fixture prompt','model':model,'thinking':'low'})

    def failed(self):
        item=self.service.registry.list()[-1]
        self.assertEqual(item['status'],'failed');self.assertIsNone(item['target'])
        records=[row['record'] for row in self.service.registry.events(item['id'])]
        self.assertFalse(any(row.get('type')=='prompt' for row in records))
        return item,records

    def test_short_alias_mismatch_reaches_caller_and_retained_failure(self):
        with self.assertRaises(sessions.SessionError) as caught:self.start('luna')
        self.assertEqual(caught.exception.status,409)
        message=str(caught.exception)
        self.assertIn('luna',message);self.assertIn('amazon-bedrock/us.openai.gpt-5.6-luna',message)
        self.assertIn('exact',message);self.assertIn('prompt was not sent',message.lower())
        item,records=self.failed()
        self.assertEqual(item['error'],message)
        self.assertEqual(next(row for row in records if row.get('type')=='native_start_failed')['error'],message)
        self.assertIsNone(item['native_session_file'])

    def test_native_mismatch_is_not_reported_as_model_mismatch(self):
        self.service.pi_command[-1]='native'
        with self.assertRaises(sessions.SessionError) as caught:self.start('openai-codex/gpt-6.1-sol')
        self.assertEqual(caught.exception.status,409)
        self.assertIn('native context',str(caught.exception));self.assertNotIn('model mismatch',str(caught.exception))
        self.failed()

    def test_unexplained_process_exit_retains_generic_diagnostic(self):
        self.service.pi_command[-1]='exit'
        with self.assertRaises(sessions.SessionError) as caught:self.start('openai-codex/gpt-6.1-sol')
        self.assertEqual(caught.exception.status,503)
        self.assertIn('broker failed to start',str(caught.exception))
        self.failed()

    def test_exact_requested_model_still_starts(self):
        item=self.start('openai-codex/gpt-6.1-sol')
        self.assertEqual(item['model'],'openai-codex/gpt-6.1-sol')
        self.assertIsNotNone(item['target'])


if __name__=='__main__':unittest.main()
