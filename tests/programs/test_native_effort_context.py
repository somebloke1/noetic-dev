"""Owned native context and actual extension hook, without provider execution."""
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import socketserver
import subprocess
import tempfile
import threading
import unittest

from scripts import noetic_sessions as sessions


class NativeEffortContextTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='native-context-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cwd=self.root/'project';self.cwd.mkdir()
        self.service=sessions.SessionService(self.root/'runs',namespace_path=self.root/'namespace.sqlite3')
        self.effort=self.service.create_effort({'intent':'Find a hidden gem in the neglected projects.', 'environment':{'cwd':str(self.cwd)}})['ordinal']
        self.other=self.service.create_effort({'intent':'A separate purpose', 'environment':{'cwd':str(self.cwd)}})['ordinal']
        self.item=self.service.registry.create(self.cwd,'Fixture','unused','off',[],ordinal=self.effort,effort_root=self.effort)
        self.transcript=self.service.registry.directory(self.item['id'])/'native'/'fixture.jsonl'
        self.service.registry.update(self.item['id'],native_session_file=str(self.transcript))
        self.service.registry.attach(self.item['id'],{'sessionId':'fixture-native','sessionFile':str(self.transcript)})
        self.broker=sessions.Broker.__new__(sessions.Broker)
        self.broker.service=self.service;self.broker.registry=self.service.registry;self.broker.sid=self.item['id']

    def test_context_names_current_and_bound_mandates_and_paths(self):
        before=self.service.registry.path.read_bytes()
        context=self.broker.handle({'action':'context'})
        self.assertEqual(context['effort']['intent'],'Find a hidden gem in the neglected projects.')
        self.assertEqual(context['effort']['mandate']['version'],1)
        self.assertEqual(context['position']['instantiation_mandate_version'],1)
        self.assertEqual(context['working_directory'],str(self.cwd))
        self.assertEqual(context['native_transcript'],str(self.transcript))
        self.assertNotEqual(context['working_directory'],str(self.transcript.parent))
        store=self.service.registry.domain.store()
        store.revise_mandate(self.effort,scope=sessions.Scope.effort(self.effort),mandate={'purpose':'Updated human mandate'},origin='human',human_ref={'fixture':'human'},source_ref={'fixture':'revision'})
        updated=self.broker.handle({'action':'context'})
        self.assertEqual(updated['effort']['mandate']['version'],2)
        self.assertEqual(updated['position']['current_mandate_version'],2)
        self.assertEqual(updated['position']['instantiation_mandate_version'],1)
        self.assertEqual(self.service.registry.path.read_bytes(),before)
        self.assertEqual(self.broker.handle({'action':'overview'})['context'],updated)
        self.assertIsInstance(self.broker.handle({'action':'tree'}),list)

    def test_child_owning_effort_and_unknown_collision(self):
        store=self.service.registry.domain.store()
        child=store.delegate(self.effort,scope=sessions.Scope.effort(self.effort),mandate={'task':'Inspect one project'},origin='human',human_ref={'fixture':'human'},source_ref={'fixture':'delegate'})
        item=self.service.registry.create(self.cwd,'Child','unused','off',[],ordinal=child['ordinal'],effort_root=self.effort)
        self.service.registry.attach(item['id'],{'sessionId':'child-native','sessionFile':str(self.root/'child.jsonl')})
        context=self.service.current_context(item['id'])
        self.assertEqual(context['effort']['ordinal'],self.effort)
        self.assertEqual(context['position']['mandate']['mandate'],{'task':'Inspect one project'})
        legacy=self.service.registry.create(self.cwd,'Original','unused','off',[],ordinal=self.effort,effort_root=None)
        with self.assertRaises(sessions.SessionError):self.service.current_context(legacy['id'])
        with closing(self.service.registry.connect()) as db,db:
            db.execute('UPDATE sessions SET session_selector=99 WHERE id=?',(item['id'],))
        with self.assertRaises(sessions.SessionError):self.service.current_context(item['id'])

    def test_actual_extension_startup_and_default_read(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        broker=self.broker
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                request=json.loads(self.rfile.readline())
                try:result={'success':True,'data':broker.handle(request)}
                except Exception as exc:result={'success':False,'error':str(exc)}
                self.wfile.write(json.dumps(result).encode()+b'\n')
        path=str(self.root/'context.sock');server=socketserver.ThreadingUnixStreamServer(path,Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(lambda:(server.shutdown(),server.server_close(),thread.join(5)))
        script="""
const {default:extension}=await import(process.argv[1]);
const tools=new Map(),hooks=new Map();
extension({registerTool:t=>tools.set(t.name,t),registerCommand(){},on:(name,fn)=>hooks.set(name,fn)});
const input={systemPrompt:'Original system instructions',prompt:'Proceed as instructed'};
const startup=await hooks.get('before_agent_start')(input);
const read=await tools.get('agent_read').execute('test',{});
console.log(JSON.stringify({startup,read:read.details,input}));
"""
        env={k:v for k,v in os.environ.items() if k!='USER_PROVIDED_PASSWORD'}
        env.update(NOETIC_SESSION_SOCKET=path,NOETIC_SESSION_ORDINAL=self.effort,NOETIC_EFFORT_ROOT=self.effort)
        output=subprocess.run([node,'--input-type=module','-e',script,sessions.EXTENSION.as_uri()],env=env,capture_output=True,text=True,timeout=10,check=True)
        result=json.loads(output.stdout)
        self.assertIn('Find a hidden gem',result['startup']['systemPrompt'])
        self.assertIn('Current human instructions',result['startup']['systemPrompt'])
        self.assertEqual(result['input']['prompt'],'Proceed as instructed')
        self.assertEqual(result['read']['context']['effort']['ordinal'],self.effort)
        self.assertEqual(len(result['read']['branch']),1)


if __name__=='__main__':unittest.main()
