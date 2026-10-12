"""Disposable HTTP ownership checks with actual local Pi RPC and native Telos."""
from contextlib import closing
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from scripts import noetic_application as application
from scripts import noetic_controller as controller
from scripts import noetic_disciplines as disciplines
from scripts import noetic_harness as harness
from scripts import noetic_local as local
from scripts import noetic_web as web
from scripts.noetic_scope import Scope, ScopeStore
from tests.programs.test_noetic_harness import result_for

RPC = r'''
import json,os,sys,uuid,time
from pathlib import Path
assert 'USER_PROVIDED_PASSWORD' not in os.environ
args=sys.argv[1:];sid=str(uuid.uuid4());folder=Path(args[args.index('--session-dir')+1]);path=folder/(sid+'.jsonl')
path.write_text(json.dumps({'type':'session','id':sid})+'\n')
def emit(x):print(json.dumps(x),flush=True)
for line in sys.stdin:
 r=json.loads(line);kind=r['type'];data={}
 if kind=='get_state':data={'sessionId':sid,'sessionFile':str(path),'model':{'provider':'fixture','id':'model'},'thinkingLevel':'high'}
 elif kind=='prompt':
  import sqlite3
  with sqlite3.connect(os.environ['FIXTURE_NAMESPACE']) as db:assert any(json.loads(x[0]).get('session_id')==sid for x in db.execute('SELECT native_ref FROM sessions'))
  if os.environ.get('FIXTURE_HOLD'):
   hold=Path(os.environ['FIXTURE_HOLD']);hold.with_suffix('.waiting').touch()
   while not hold.exists():time.sleep(.01)
  if os.environ.get('FIXTURE_WRITE'):Path('product.txt').write_text('reviewed fixture change\n')
  emit({'type':'response','id':r['id'],'command':kind,'success':True,'data':{}})
  emit({'type':'agent_end','willRetry':False});emit({'type':'agent_settled'});continue
 elif kind=='get_messages':
  data={'messages':[{'role':'assistant','stopReason':'stop','content':[{'type':'text','text':os.environ['FIXTURE_RESULT']}]}]}
  with path.open('a') as f:f.write(json.dumps(data)+'\n')
 emit({'type':'response','id':r['id'],'command':kind,'success':True,'data':data})
'''


def rpc_command(run, state, options, prompt):
    activation = state['activations'][state['current_activation']]
    result = result_for(state)
    if 'content' in result:
        result['content'] = {key: state['purpose'] if isinstance(value, str) else value for key, value in result['content'].items()}
    if options['pattern'] == 'development' and activation['phase'] == 'implementation' and activation['mode'] == 'produce':
        result['verification_argv'] = [sys.executable, '-c', "from pathlib import Path; assert Path('product.txt').read_text() == 'reviewed fixture change\\n'"]
    environment = {key: value for key, value in os.environ.items() if key != 'USER_PROVIDED_PASSWORD'}
    environment.update(FIXTURE_RESULT=json.dumps(result), FIXTURE_NAMESPACE=options['scope']['namespace_path'])
    if state['purpose'].startswith('holding') and activation['id'] == 'activation-0':
        environment['FIXTURE_HOLD'] = str(run / 'fixture-release')
    if options['pattern'] == 'development' and activation['phase'] == 'implementation' and activation['mode'] == 'produce':
        environment['FIXTURE_WRITE'] = '1'
    return [sys.executable, os.environ['EFFORT_RPC_FIXTURE'], '--mode', 'json', '-p', '--model', 'fixture/model'], environment


class EffortApplicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name);self.project = self.root / 'project';self.project.mkdir()
        env = {key: value for key, value in os.environ.items() if key != 'USER_PROVIDED_PASSWORD'}
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True, env=env, capture_output=True)
        (self.project / 'product.txt').write_text('uncommitted original\n')
        self.namespace = self.root / 'namespace.sqlite3';self.runs = self.root / 'runs'
        self.store = ScopeStore(self.namespace, root_mandate={'purpose': 'fixture human coordination'},
            human_ref={'fixture': 'human'}, source_ref={'fixture': 'setup'})
        self.efforts = [self.store.create_effort(intent=name,environment={'cwd': str(self.project)},
            mandate={'purpose':name},origin='human',human_ref={'fixture':'human'},source_ref={'fixture':name}) for name in ('A','B','R')]
        rpc = self.root / 'rpc.py';rpc.write_text(RPC)
        environment = patch.dict(os.environ, {'NOETIC_APP_HOME':'', 'EFFORT_RPC_FIXTURE': str(rpc)})
        environment.start();self.addCleanup(environment.stop)
        self.server = web.create_server(self.runs,port=0,namespace_path=self.namespace,telos_db=self.root/'legacy.sqlite3')
        self.server.application.work_root = self.root / 'worktrees'
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.close)
        original = subprocess.Popen
        def process(argv, **kwargs):
            if isinstance(argv,list) and 'scripts.noetic_application' in argv:
                index=argv.index('scripts.noetic_application');_,run,maximum,fd,slot=argv[index+1:]
                code="import sys; from scripts import noetic_application as a; from tests.programs.test_effort_application import rpc_command; a.harness.actor_command=rpc_command; raise SystemExit(a.driver_main(sys.argv[1],None if sys.argv[2]=='all' else int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4])))"
                argv=[sys.executable,'-B','-c',code,run,maximum,fd,slot]
            return original(argv,**kwargs)
        driver=patch.object(application.subprocess,'Popen',side_effect=process);driver.start();self.addCleanup(driver.stop)
        self.addCleanup(self.finish)

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(5)

    def finish(self):
        for run in self.runs.glob('*'):
            if run.is_dir():(run/'fixture-release').touch()
        for child in self.server.application.children:child.wait(timeout=20)

    def request(self, path, expected=200, body=None, server=None):
        server=server or self.server
        with closing(http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=30)) as connection:
            connection.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,
                {'Authorization':f'Bearer {server.token}','Content-Type':'application/json'})
            response=connection.getresponse();data=json.loads(response.read());self.assertEqual(response.status,expected,data);return data

    def instance(self, index=0, pattern='cognition'):
        owner=self.efforts[index]
        return self.request('/api/disciplines',201,{'command_id':str(__import__('uuid').uuid4()),'effort_root':owner['ordinal'],
            'initiator':owner['ordinal'],'pattern':pattern,'intent':owner['intent'],'environment':owner['environment']})['discipline']

    def start(self,index=0,pattern='cognition',task=None,**extra):
        instance=self.instance(index,pattern)
        return self.request('/api/application/start',202,{'effort_root':self.efforts[index]['ordinal'],'discipline_id':instance['id'],
            'environment':instance['environment'],'origin':'human','human_ref':{'fixture':'explicit assignment'},
            'pattern':pattern,'workspace':str(self.project),'task':task or f"distincttoken{index} useful fixture",'client':'pi',
            'model':'fixture/model',**extra})

    def detail(self,run,index=0):
        return self.request(f"/api/runs/{run}?effort_root={self.efforts[index]['ordinal']}")

    def wait(self, predicate):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            result=predicate()
            if result:return result
            time.sleep(.02)
        self.fail('Fixture did not reach expected state')

    def terminal(self,run,index=0):
        return self.wait(lambda:(d if d['controller']['status']!='active' and not d['application']['gui_driver_owned'] else None)
                         if (d:=self.detail(run,index)) else None)

    def test_a_b_r_actual_rpc_run_ownership_and_all_content_effect_gates(self):
        records=[]
        for index in range(3):
            run=self.start(index)['run_id'];detail=self.terminal(run,index)
            self.assertEqual(detail['controller']['status'],'completed');records.append(run)
            self.assertEqual(detail['correspondence']['namespace']['path'],str(self.namespace))
            self.assertTrue(all(p['target'] is not None for p in detail['correspondence']['participants']))
            listed=self.request(f"/api/runs?effort_root={self.efforts[index]['ordinal']}")
            self.assertEqual([r['run_id'] for r in listed['runs']],[run])
        self.assertEqual(len(self.request('/api/runs?scope=application')['runs']),3)
        target=self.detail(records[0])['correspondence']['participants'][-1]['target']
        exact=self.request(f"/api/search?effort_root={self.efforts[0]['ordinal']}&ordinal={target['ordinal']}&instantiation={target['instantiation']}&session={target['session']}&q=distincttoken0")
        self.assertTrue(exact['results'])
        self.assertTrue(all(row['target']==target for row in exact['results']))
        foreign=self.efforts[1]['ordinal'];run=records[0];directory=self.runs/run
        before={str(p):p.read_bytes() for p in directory.rglob('*') if p.is_file()}
        reads=('', '/reuse-setup','/project-file?path=product.txt','/project-changes','/activations/activation-0/transcript',
               '/activations/activation-0/logs/prompt.txt','/sessions/work/transcript')
        with patch.object(application.local,'LocalClient',side_effect=AssertionError('Must reject before inference')):
            for suffix in reads:
                path=f'/api/runs/{run}{suffix}';path+=('&' if '?' in path else '?')+f'effort_root={foreign}'
                self.request(path,403)
            for action,body in (('advance',{'mode':'all'}),('pause',{}),('cancel',{'confirm':True}),('apply',{'confirm':True}),('summary',{'save':True})):
                self.request(f'/api/runs/{run}/{action}',403,{**body,'effort_root':foreign})
        self.assertEqual(before,{str(p):p.read_bytes() for p in directory.rglob('*') if p.is_file()})
        self.assertEqual(self.request('/api/configuration')['namespace_path'],str(self.server.developer_sessions.registry.domain.path))
        self.request('/api/application/start',400,{'workspace':str(self.project),'task':'unassigned new work'})

    def test_stale_agent_and_foreign_instance_reject_before_preparation_or_actor(self):
        owner=self.efforts[0]['ordinal'];scope=Scope.effort(owner)
        occupant=self.store.instantiate(owner,scope=scope,native_ref={'fixture':'declared local actor'},source_ref={'fixture':'native'})
        old=self.store.open_session(owner,occupant['sequence'],scope=scope,native_ref={'session_id':'old-fixture'},source_ref={'fixture':'native'})
        discipline_body={'command_id':'stale-instance','effort_root':owner,'initiator':owner,'pattern':'cognition',
            'intent':'stale creation','environment':self.efforts[0]['environment'],'initiating_target':old.as_dict()}
        self.store.open_session(owner,occupant['sequence'],scope=scope,native_ref={'session_id':'current-fixture'},source_ref={'fixture':'native'})
        self.request('/api/disciplines',422,discipline_body)
        self.request('/api/disciplines',422,{**discipline_body,'initiator':self.efforts[1]['ordinal']})
        self.assertFalse(self.namespace.with_name(self.namespace.name+'.correlation.sqlite3').exists())
        instance=self.instance()
        body={'effort_root':owner,'discipline_id':instance['id'],'environment':instance['environment'],'origin':'agent',
            'delegator':old.as_dict(),'workspace':str(self.project),'task':'stale request','pattern':'cognition','client':'pi'}
        before=self.namespace.read_bytes()
        with patch.object(application.projects,'task_worktree',side_effect=AssertionError('Reject before worktree preparation')), \
                patch.object(application.subprocess,'Popen',side_effect=AssertionError('Reject before actor or driver')):
            self.request('/api/application/start',422,body)
            self.request('/api/application/start',422,{**body,'effort_root':self.efforts[1]['ordinal']})
        self.assertEqual(self.namespace.read_bytes(),before)
        self.assertFalse(self.runs.exists());self.assertFalse((self.root/'worktrees').exists())

    def test_owned_worktree_preparation_review_apply_and_same_cwd_exclusion(self):
        holding=self.start(task='holding source ownership')['run_id'];held=self.runs/holding
        self.wait(lambda:(held/'fixture-release.waiting').exists())
        instance=self.instance(1,'development')
        self.request('/api/application/start',409,{'effort_root':self.efforts[1]['ordinal'],'discipline_id':instance['id'],
            'environment':instance['environment'],'origin':'human','human_ref':{'fixture':'human'},'pattern':'development',
            'workspace':str(self.project),'task':'another effort same source','client':'pi','model':'fixture/model'})
        self.request(f'/api/runs/{holding}/pause',202,{'effort_root':self.efforts[0]['ordinal']})
        (held/'fixture-release').touch();self.wait(lambda:self.detail(holding)['application']['pause_applied'])
        self.request(f'/api/runs/{holding}/advance',202,{'effort_root':self.efforts[0]['ordinal'],'mode':'all'})
        self.terminal(holding)
        run=self.start(pattern='development')['run_id'];detail=self.terminal(run)
        self.assertEqual(detail['controller']['status'],'completed',detail['controller']['reason'])
        self.assertNotEqual(detail['controller']['workspace'],str(self.project))
        self.assertEqual((self.project/'product.txt').read_text(),'uncommitted original\n')
        changes=self.request(f'/api/runs/{run}/project-changes?effort_root={self.efforts[0]["ordinal"]}')
        self.assertTrue(changes['eligible'],changes['reason'])
        applied=self.request(f'/api/runs/{run}/apply',body={'effort_root':self.efforts[0]['ordinal'],'confirm':True})
        self.assertTrue(applied['applied']);self.assertEqual((self.project/'product.txt').read_text(),'reviewed fixture change\n')

    def test_purposes_native_owner_stores_and_exact_binding(self):
        from scripts import noetic_telos as telos
        if not shutil.which('node') or not (telos.source_path()/'node_modules/tsx/dist/loader.mjs').is_file():self.skipTest('Native Telos not available')
        references=[]
        for index in range(3):
            owner=self.efforts[index]['ordinal']
            absent=self.request(f'/api/goals?effort_root={owner}');self.assertEqual(absent['stores'][0]['status'],'absent')
            reference=self.request('/api/goals',201,{'effort_root':owner,'goal':f'purpose{index}',
                'origin_ref':{'fixture':'human'},'source_ref':{'fixture':'purpose'}})['purpose']['reference'];references.append(reference)
            listed=self.request(f'/api/goals?effort_root={owner}')
            self.assertEqual([p['reference'] for p in listed['purposes']],[reference])
        self.assertEqual(len({ref['db_path'] for ref in references}),3)
        foreign=self.instance(1)
        body={'effort_root':self.efforts[1]['ordinal'],'discipline_id':foreign['id'],'environment':foreign['environment'],
            'origin':'human','human_ref':{'fixture':'human'},'workspace':str(self.project),'task':'wrong purpose',
            'pattern':'cognition','purpose_ref':references[0]}
        self.request('/api/application/start',422,body)
        self.request('/api/application/start',422,{**body,'purpose_ref':{}})
        self.assertFalse(self.runs.exists())
        run=self.start(purpose_ref=references[0])['run_id'];detail=self.terminal(run)
        self.assertEqual(detail['status']['telos']['db_path'],references[0]['db_path'])
        self.assertEqual(detail['status']['telos']['chain_id'],references[0]['chain_id'])
        native=self.request(f"/api/goals/{references[0]['chain_id']}?effort_root={self.efforts[0]['ordinal']}")['purpose']['native']
        self.assertEqual(native['chain']['status'],'active')
        shutil.copy2(references[0]['db_path'],references[1]['db_path'])
        chain=references[0]['chain_id']
        self.request(f'/api/goals/{chain}?scope=application',409)
        selected=self.request(f"/api/goals/{chain}?scope=application&store_id={references[1]['store_id']}")
        self.assertEqual(selected['purpose']['reference']['owner']['ordinal'],self.efforts[1]['ordinal'])

    def test_lexical_semantic_exact_scope_and_preinference_rejection(self):
        for index in range(3):
            self.terminal(self.start(index)['run_id'],index)
        for index in range(3):
            owner=self.efforts[index]['ordinal']
            result=self.request(f'/api/search?effort_root={owner}&q=distincttoken{index}')
            self.assertTrue(result['results']);self.assertTrue(all(row['effort_root']==owner for row in result['results']))
            self.assertFalse(self.request(f'/api/search?effort_root={owner}&q=distincttoken{(index+1)%3}')['results'])
        calls=[]
        class Embeddings(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));calls.append(body)
                data=json.dumps({'data':[{'index':i,'embedding':[1,0,0]} for i in range(len(body['input']))]}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        with ThreadingHTTPServer(('127.0.0.1',0),Embeddings) as embedder:
            thread=threading.Thread(target=embedder.serve_forever,daemon=True);thread.start()
            try:
                settings=local.Settings(base_url=f'http://127.0.0.1:{embedder.server_port}/v1',dimensions=3)
                with patch.object(local,'load_settings',return_value=settings),patch.dict(os.environ,{'LITELLM_API_KEY':'public-fixture-key'}):
                    caches=[]
                    for effort in self.efforts:
                        result=self.request('/api/memory/semantic',body={'query':'fixture','effort_root':effort['ordinal']})
                        caches.append(result['cache']);self.assertTrue(result['results'])
                        self.assertTrue(all(row['effort_root']==effort['ordinal'] for row in result['results']))
                    self.assertEqual(len(set(caches)),3)
                    before=len(calls)
                    self.request('/api/memory/semantic',422,{'query':'fixture','effort_root':'0.999'})
                    self.assertEqual(len(calls),before)
            finally:embedder.shutdown();thread.join(5)

    def test_retained_legacy_global_reads_before_namespace_registration(self):
        home=self.root/'pre-registration';runs=home/'runs';workspace=self.root/'legacy-project';workspace.mkdir()
        run,_=harness.start('cognition','legacyunassignedtoken',workspace,runs,max_activations=0)
        namespace=home/'declared-absent.sqlite3'
        server=web.create_server(runs,port=0,namespace_path=namespace,telos_db=home/'legacy.sqlite3')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            result=self.request('/api/runs?scope=application',server=server)
            self.assertEqual(result['runs'][0]['correspondence']['correlation_status'],'unassigned')
            self.request(f'/api/runs/{run.name}?scope=application',server=server)
            goals=self.request('/api/goals?scope=application&include_legacy=true',server=server)
            self.assertFalse(goals['namespace_registered'])
            self.assertEqual(goals['stores'][0]['status'],'absent')
            self.assertEqual(goals['stores'][0]['owner']['kind'],'legacy-unassigned')
            self.assertFalse((home/'legacy.sqlite3').exists())
            result=self.request('/api/search?scope=application&q=legacyunassignedtoken',server=server)
            self.assertTrue(result['results']);self.assertEqual(result['status'],'unregistered-legacy-only')
            self.request('/api/search?effort_root=0.0&q=legacyunassignedtoken',422,server=server)
            self.assertFalse(namespace.exists());self.assertFalse((runs/'developer-sessions').exists())
        finally:server.shutdown();server.server_close();thread.join(5)
