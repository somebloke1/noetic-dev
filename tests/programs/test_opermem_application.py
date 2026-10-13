"""Real authenticated HTTP and independent model-free client processes with native Rust."""
from contextlib import closing
from copy import deepcopy
import http.client
import hashlib
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

from scripts import noetic_application as appmod, noetic_opermem as native, noetic_opermem_application as reviewed
from scripts import noetic_web as web
from scripts.noetic_scope import ScopeStore


def client(client, prompt, role, model, run_dir=None, workspace=None, context_dirs=()):
    """Transport fixture only: real two fresh processes, actual session headers and logs."""
    root = Path(os.environ['REVIEWED_FIXTURE_ROOT'])
    calls = root / 'calls.jsonl'
    token = Path(run_dir).name if run_dir else role
    operation = os.environ.get('REVIEWED_FIXTURE_OPERATION', 'question')
    value = json.loads(os.environ.get('REVIEWED_FIXTURE_VALUE', json.dumps({'question_kind': 'how', 'text': 'What follows from explicitly selected evidence?'})))
    report = 'ACCEPT\nCompared explicit sources.' if role == 'reviewer' else 'Useful investigation from source evidence.\n' + native.MARKER + json.dumps(value)
    session = 'actual-' + token + '-' + role
    code = """
import json,os,sys,time
from pathlib import Path
prompt=sys.stdin.read();assert 'USER_PROVIDED_PASSWORD' not in os.environ
root=Path(os.environ['REVIEWED_FIXTURE_ROOT'])
with (root/'calls.jsonl').open('a') as f:f.write(json.dumps({'pid':os.getpid(),'role':sys.argv[1]})+'\\n')
(root/(sys.argv[1]+'.waiting')).touch()
if os.environ.get('REVIEWED_FIXTURE_HOLD'):
 while not (root/'release').exists():time.sleep(.01)
if os.environ.get('REVIEWED_FIXTURE_FAIL')=='no-header':sys.exit(2)
print(json.dumps({'type':'text','sessionID':sys.argv[2],'part':{'id':'text','messageID':'final','text':sys.argv[3]}}),flush=True)
if os.environ.get('REVIEWED_FIXTURE_FAIL')=='header':sys.exit(2)
print(json.dumps({'type':'step_finish','sessionID':sys.argv[2],'part':{'messageID':'final','reason':'stop'}}),flush=True)
"""
    return [sys.executable, '-c', code, role, session, report], None


@unittest.skipUnless(os.environ.get('OPERMEM_OPERATION_HOST'), 'requires accepted actual native pair')
class ReviewedApplicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='reviewed-app-');self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name);self.cwd = self.root/'project';self.cwd.mkdir()
        self.namespace = self.root/'namespace.sqlite3';self.runs=self.root/'runs'
        self.store=ScopeStore(self.namespace, root_mandate={'purpose':'fixture root'},human_ref={'fixture':'human'},source_ref={'fixture':'root'})
        self.efforts=[self.store.create_effort(intent=name,environment={'cwd':str(self.cwd)},mandate={'purpose':name},origin='human',human_ref={'fixture':'human'},source_ref={'fixture':name}) for name in ('A','B','R')]
        self.host=Path(os.environ['OPERMEM_OPERATION_HOST'])
        self.server=web.create_server(self.runs,port=0,namespace_path=self.namespace,opermem_host=self.host)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close)
        env=patch.dict(os.environ,{'REVIEWED_FIXTURE_ROOT':str(self.root)},clear=False);env.start();self.addCleanup(env.stop)
        popen=subprocess.Popen
        def launch(argv,**kwargs):
            if 'scripts.noetic_opermem_application' in argv:
                i=argv.index('scripts.noetic_opermem_application'); _,directory,fd,slot=argv[i+1:]
                code="import os,sys;from scripts import noetic_develop as d,noetic_opermem_application as a;from tests.programs.test_opermem_application import client;d.client_command=client\noriginal_save=a.save\ndef save(path,value):\n if os.environ.get('REVIEWED_FIXTURE_CALLBACK_GAP') and path.name=='receipt.json' and value.get('status')=='prepared':raise OSError('fixture lost derived preparation receipt update')\n return original_save(path,value)\na.save=save\nraise SystemExit(a.drive(sys.argv[1],int(sys.argv[2]),int(sys.argv[3])))"
                argv=[sys.executable,'-B','-c',code,directory,fd,slot]
            return popen(argv,**kwargs)
        transport=patch.object(reviewed.subprocess,'Popen',side_effect=launch);transport.start();self.addCleanup(transport.stop)
        self.addCleanup(self.finish)
        self.instances=[];self.refs=[]
        for i,effort in enumerate(self.efforts):
            self.instances.append(self.request('/api/disciplines',201,{'backend':reviewed.BACKEND,'command_id':'instance-'+str(i),'effort_root':effort['ordinal'],'initiator':effort['ordinal'],'intent':'read sources','environment':effort['environment'],'origin':'human','human_ref':{'fixture':'human'}})['discipline'])
            self.refs.append(self.request('/api/opermem/stores',201,{'command_id':'backing-'+str(i),'effort_root':effort['ordinal'],'directory':str(self.root/('native-'+str(i)))})['store_ref'])
        self.source=self.cwd/'source.md';self.source.write_text('Substantive externally selected source evidence.')

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(5)

    def finish(self):
        (self.root/'release').touch()
        for child in self.server.application.children:child.wait(timeout=25)

    def request(self,path,expected=200,body=None):
        with closing(http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=20)) as connection:
            connection.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,
                               {'Content-Type':'application/json'})
            response=connection.getresponse();data=json.loads(response.read())
            self.assertEqual(response.status,expected,data);return data

    def body(self,index=0,command='launch',**extras):
        return {'backend':reviewed.BACKEND,'command_id':command,'effort_root':self.efforts[index]['ordinal'],
                'discipline_id':self.instances[index]['id'],'environment':self.efforts[index]['environment'],
                'origin':'human','human_ref':{'fixture':'human'},'workspace':str(self.cwd),'task':'Investigate selected sources.',
                'store_id':self.refs[index]['id'],'client':'opencode','sources':[str(self.source)],**extras}

    def wait(self,fn):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            value=fn()
            if value:return value
            time.sleep(.02)
        self.fail('Actual disposable process did not reach expected state')

    def completed(self,launch,index=0):
        path='/api/application/launches/'+launch['launch_id']+'?effort_root='+self.efforts[index]['ordinal']
        return self.wait(lambda: r if (r:=self.request(path))['status'] in ('finished','failed') and not r['driver_owned'] else None)

    def test_async_idempotent_and_restart_mapping_without_replay(self):
        with patch.dict(os.environ,{'REVIEWED_FIXTURE_HOLD':'1'}):
            receipts=[]
            threads=[threading.Thread(target=lambda:receipts.append(self.request('/api/application/start',202,self.body()))) for _ in range(4)]
            started=time.monotonic()
            for t in threads:t.start()
            for t in threads:t.join(10)
            self.assertEqual(len(receipts),4);self.assertLess(time.monotonic()-started,10)
            self.assertEqual(len({r['launch_id'] for r in receipts}),1)
            self.wait(lambda:(self.root/'inquirer.waiting').exists())
            self.assertEqual(len(self.server.application.children),1)
            launch=receipts[0]
            self.request('/api/application/start',409,self.body(task='changed request'))
            current=self.request('/api/application/launches/'+launch['launch_id']+'?effort_root='+self.efforts[0]['ordinal'])
            self.assertTrue(current['execution_claim']);self.assertTrue(current['driver_owned'])
            self.assertEqual(current['process']['state'],'owned')
            before=self.request('/api/runs?effort_root='+self.efforts[0]['ordinal'])['runs']
            self.assertEqual(len(before),1);self.assertEqual(before[0]['run_id'],current['run_id'])
            # Close the actual HTTP owner while real actors remain held, then reconnect.
            original_children=list(self.server.application.children)
            self.close()
            self.server=web.create_server(self.runs,port=0,namespace_path=self.namespace,opermem_host=self.host)
            self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
            retained=self.request('/api/application/start',202,self.body())
            self.assertEqual(retained['launch_id'],launch['launch_id']);self.assertEqual(self.server.application.children,[])
            self.assertTrue(retained['driver_owned'])
            (self.root/'release').touch()
            for child in original_children:child.wait(timeout=25)
        result=self.completed(launch);self.assertEqual(result['status'],'finished')
        calls=[json.loads(x) for x in (self.root/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(len(calls),2);self.assertEqual(len({x['pid'] for x in calls}),2)
        directory=self.runs/'.opermem-launches'/launch['launch_id'];(directory/'receipt.json').unlink()
        restored=self.request('/api/application/launches/'+launch['launch_id']+'?effort_root='+self.efforts[0]['ordinal'])
        self.assertEqual(restored['run_id'],result['run_id']);self.assertEqual(restored['status'],'uncertain')
        self.request('/api/runs/'+result['run_id']+'/recover-correlation',body={'effort_root':self.efforts[0]['ordinal']})
        self.assertTrue((directory/'receipt.json').exists());self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()),2)
        preparation=self.runs/'.opermem-preparations'/result['run_id']/'binding.json'
        original_preparation=preparation.read_bytes();preparation.unlink()
        self.request('/api/runs/'+result['run_id']+'/recover-correlation',body={'effort_root':self.efforts[0]['ordinal']})
        self.assertEqual(preparation.read_bytes(),original_preparation)
        self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()),2)
        restarted=appmod.Application(self.runs,namespace_path=self.namespace,opermem_host=self.host)
        self.assertEqual(restarted.reviewed().launches({'kind':'effort','effort_root':self.efforts[0]['ordinal']})['launches'][0]['run_id'],result['run_id'])

    def test_three_efforts_separate_stores_population_recall_and_reuse(self):
        records=[]
        for i in range(3):
            launch=self.request('/api/application/start',202,self.body(i,'launch-'+str(i)))
            completed=self.completed(launch,i);self.assertEqual(completed['status'],'finished',completed)
            records.append(completed['run_id'])
            detail=self.request('/api/runs/'+completed['run_id']+'?effort_root='+self.efforts[i]['ordinal'])
            self.assertEqual(len(detail['population']),2);self.assertTrue(all(p['target'] for p in detail['population']))
            self.assertTrue(detail['application']['native']['receipt_retained'])
            self.assertFalse(detail['application']['review']['native_acceptance_equivalent'])
            self.assertEqual(detail['correspondence']['native_store_identity']['workspace_id'],1)
            self.assertEqual(detail['correspondence']['store_ref']['id'],self.refs[i]['id'])
            self.assertEqual(len(self.request('/api/runs?effort_root='+self.efforts[i]['ordinal'])['runs']),1)
            self.request('/api/runs/'+completed['run_id']+'?effort_root='+self.efforts[(i+1)%3]['ordinal'],403)
        detail=self.request('/api/runs/'+records[0]+'?effort_root='+self.efforts[0]['ordinal'])
        target=detail['population'][0]['target']
        exact=self.request('/api/search?q=investigation&ordinal='+target['ordinal']+'&instantiation='+str(target['instantiation'])+'&session='+str(target['session']))
        self.assertNotIn('Compared explicit sources.',json.dumps(exact))
        reuse=self.request('/api/runs/'+records[0]+'/reuse-setup?effort_root='+self.efforts[0]['ordinal'])
        self.assertEqual(reuse['fields']['task'],self.body()['task']);self.assertEqual(reuse['fields']['sources'],[str(self.source)])
        for field in ('effort_root','discipline_id','store_id','purpose_ref','target','command_id'):self.assertIsNone(reuse['fields'][field])
        run=self.runs/records[0]
        (run/'opermem-scope.json').write_text('{}')
        listed=self.request('/api/runs?effort_root='+self.efforts[0]['ordinal'])
        self.assertEqual(listed['runs'][0]['state'],'unavailable');self.assertTrue(listed['warnings'])

    def test_refusals_before_effects_and_real_startup_failure_history(self):
        bad=[{'effort_root':self.efforts[1]['ordinal']},{'store_id':self.refs[1]['id']}, {'discipline_id':999},
             {'environment':{'cwd':str(self.root)}},{'human_ref':None},{'selectors':{'parent_id':-1},'operation':'insight'},
             {'selectors':{'warrant_id':1}},{'namespace_path':str(self.namespace)},{'telos_chain':'bare'},
             {'mode':'development'},{'sources':[str(self.root/'missing')]},{'purpose_ref':{'chain_id':'fake'}}]
        for mutation in bad:
            with self.subTest(mutation=mutation):self.request('/api/application/start',422,self.body(**mutation))
        self.assertFalse((self.root/'calls.jsonl').exists());self.assertFalse((self.runs/'.opermem-launches').exists())
        self.assertTrue(all(not Path(ref['directory']).exists() for ref in self.refs))
        # A real executable pair whose host refuses startup, never substituted native success.
        badpair=self.root/'broken';badpair.mkdir()
        host=badpair/'opermem-operation-host';host.write_text('#!/bin/sh\nexit 2\n');host.chmod(0o700)
        child=badpair/'opermem-child';child.write_text('#!/bin/sh\nexit 2\n');child.chmod(0o700)
        self.server.application.opermem_host=host
        ref=self.request('/api/opermem/stores',201,{'command_id':'broken','effort_root':self.efforts[0]['ordinal'],'directory':str(self.root/'broken-store')})['store_ref']
        launch=self.request('/api/application/start',202,self.body(command='startup-failure',store_id=ref['id']))
        result=self.completed(launch);self.assertEqual(result['status'],'failed');self.assertIsNotNone(result['run_id'])
        self.assertFalse((self.runs/result['run_id']/'events.sqlite3').exists())
        listed=self.request('/api/runs?effort_root='+self.efforts[0]['ordinal'])['runs']
        self.assertEqual(len(listed),1);self.assertEqual(listed[0]['state'],'preparation-failed');self.assertEqual(listed[0]['population'],[])
        detail=self.request('/api/runs/'+result['run_id']+'?effort_root='+self.efforts[0]['ordinal'])
        self.assertEqual(detail['status']['state'],'preparation-failed')

    def test_no_header_actor_failure_is_reservation_and_recovery_has_zero_actors(self):
        with patch.dict(os.environ,{'REVIEWED_FIXTURE_FAIL':'no-header'}):
            launch=self.request('/api/application/start',202,self.body());result=self.completed(launch)
        detail=self.request('/api/runs/'+result['run_id']+'?effort_root='+self.efforts[0]['ordinal'])
        self.assertEqual(len(detail['population']),1);self.assertIsNone(detail['population'][0]['target'])
        self.assertEqual(detail['population'][0]['status'],'reserved')
        self.request('/api/runs/'+result['run_id']+'/pause',409,{'effort_root':self.efforts[0]['ordinal']})
        self.request('/api/runs/'+result['run_id']+'/recover-contribution',422,{'effort_root':self.efforts[0]['ordinal']})
        self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()),1)

    def test_owned_full_purpose_and_receipt_only_telos_recovery(self):
        source=Path(os.environ.get('NOETIC_TEST_TELOS_SOURCE',Path(__file__).resolve().parents[2]/'.runtime/components/telos-core.mjs'))
        copied=self.root/'telos.mjs';shutil.copyfile(source,copied)
        self.server.application.telos_source=copied
        self.server.application.purposes_root=self.root/'purposes'
        a=self.request('/api/goals',201,{'goal':'Actual bounded application inquiry','effort_root':self.efforts[0]['ordinal'],'origin_ref':{'fixture':'human'},'source_ref':{'fixture':'purpose'}})['purpose']['reference']
        b=self.request('/api/goals',201,{'goal':'Separate B purpose','effort_root':self.efforts[1]['ordinal'],'origin_ref':{'fixture':'human'},'source_ref':{'fixture':'purpose'}})['purpose']['reference']
        self.request('/api/application/start',422,self.body(purpose_ref=b))
        launch=self.request('/api/application/start',202,self.body(purpose_ref=a));result=self.completed(launch)
        self.assertEqual(result['status'],'finished',result)
        run=self.runs/result['run_id'];before=(self.root/'calls.jsonl').read_bytes()
        original=json.loads((run/'opermem-receipt.json').read_text())
        with patch.object(native,'OperationHost',side_effect=AssertionError('receipt-only recovery must issue zero native host calls')):
            detail=self.request('/api/runs/'+run.name+'/recover-contribution',body={'effort_root':self.efforts[0]['ordinal']})
        self.assertEqual(detail['exit_code'],0);self.assertFalse(detail['actors_replayed'])
        self.assertEqual((self.root/'calls.jsonl').read_bytes(),before)
        self.assertEqual(json.loads((run/'opermem-receipt.json').read_text())['response']['payload'],original['response']['payload'])
        from scripts import noetic_run as runtime
        telos_events=[e for e in runtime.read_events(run) if e['kind']=='telos.result']
        self.assertLessEqual(len(telos_events),1)
        # Genuine pending receipt replay after later native drift: no actor or checking rerun.
        (run/'opermem-receipt.json').unlink()
        native.submit(self.host,Path(self.refs[0]['directory']),self.root/'drift','question',None,{'question_kind':'what','text':'Later independent native drift.'},'application-drift')
        detail=self.request('/api/runs/'+run.name+'/recover-contribution',body={'effort_root':self.efforts[0]['ordinal']})
        self.assertEqual(detail['exit_code'],0);self.assertEqual((self.root/'calls.jsonl').read_bytes(),before)
        replay=json.loads((run/'opermem-receipt.json').read_text())['response']['payload']
        for key in ('receipt_id','exact_result'):self.assertEqual(replay[key],original['response']['payload'][key])

    def test_checking_spec_source_preflight_and_actual_command_forwarding(self):
        from scripts import noetic_opermem_checking as checking
        from tests.programs.test_noetic_opermem_checking import CheckingCaptureTests
        store=Path(self.refs[0]['directory']);parent=None
        for operation,contribution,role in [('question',{'question_kind':'how','text':'How is checking bounded?'},'question'),('insight',{'text':'Unchecked trace.'},'unverified insight trace'),('formulation',{'text':'Unchecked hypothesis.'},'versioned formulation/hypothesis'),('reflection',{'text':'Is this correct?'},'reflection question')]:
            response,_=native.submit(self.host,store,self.root/'native-seed',operation,parent,contribution,'app-seed-'+operation)
            parent=next(x['id'] for x in response['payload']['outputs'] if x['role']==role)
            if operation=='formulation':formulation=parent
        response,_=native.submit(self.host,store,self.root/'native-seed','conditional-structure',parent,{'conditions':['Bounded application checking command executes once']},'app-warrant',formulation_id=formulation)
        warrant=next(x['id'] for x in response['payload']['outputs'] if x['role']=='warrant');condition=next(x['id'] for x in response['payload']['outputs'] if x['kind']=='warrant-condition')
        self.context_ids=(condition,warrant);self.context,_=native.retrieve(self.host,store,self.root/'native-seed',native.purpose_for('checking',condition,warrant_id=warrant))
        # Existing exact specification builder; authoring fixture is not a replacement production validator.
        spec=CheckingCaptureTests.specification(self,"from pathlib import Path; p=Path('checked-once'); assert not p.exists(); p.write_text('once')")
        value=checking.load(spec);value['command']['cwd']=str(self.cwd);spec.write_bytes(checking.canonical(value))
        context=self.root/'checking-context.json';context.write_text(json.dumps(self.context))
        body=self.body(operation='checking',selectors={'parent_id':condition,'warrant_id':warrant},checking_spec=str(spec),checking_context=str(context))
        malformed=deepcopy(value);malformed['command']['environment']['USER_PROVIDED_PASSWORD']='public invalid sentinel'
        spec.write_bytes(checking.canonical(malformed));self.request('/api/application/start',422,body)
        self.assertFalse((self.cwd/'checked-once').exists());self.assertFalse((self.root/'calls.jsonl').exists())
        spec.write_bytes(checking.canonical(value))
        launch=self.request('/api/application/start',202,body);result=self.completed(launch)
        self.assertEqual(result['status'],'finished',result);self.assertEqual((self.cwd/'checked-once').read_text(),'once')
        run=self.runs/result['run_id'];self.assertTrue((run/'checking-evidence/manifest.json').exists())
        with patch.object(checking,'capture',side_effect=AssertionError('checking recovery must never rerun command')),patch.object(native,'OperationHost',side_effect=AssertionError('receipt-only native forbidden')):
            self.request('/api/runs/'+run.name+'/recover-contribution',body={'effort_root':self.efforts[0]['ordinal']})
        self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()),2)

    def test_acting_scoped_retained_occurrence_forwarding(self):
        from tests.programs import opermem_acting_fixture as fixture
        # A genuine already reviewed owned occurrence; acting observes that retained external work.
        initial=self.request('/api/application/start',202,self.body(command='occurrence'));completed=self.completed(initial)
        occurred=self.runs/completed['run_id'];before=(occurred/'events.sqlite3').read_bytes()
        plan,step,*_=fixture.native_plan(self.host,Path(self.refs[0]['directory']),self.root/'plan-native',self.root/'plan-fixture')
        prose={'observed_act':'Observed the actual retained inquiry process.','outcome':'The subprocess completed and emitted a retained report.','deviation':'The prospective plan did not establish original dispatch of this inquiry.'}
        body=self.body(command='observe',operation='acting',selectors={'plan_id':plan,'step_id':step},observed_run_id=occurred.name)
        foreign=self.body(1,command='foreign-occurrence',operation='acting',selectors={'plan_id':plan,'step_id':step},observed_run_id=occurred.name)
        self.request('/api/application/start',403,foreign)
        with patch.dict(os.environ,{'REVIEWED_FIXTURE_VALUE':json.dumps(prose)}):
            launch=self.request('/api/application/start',202,body);result=self.completed(launch)
        self.assertEqual(result['status'],'finished',result)
        self.assertEqual((occurred/'events.sqlite3').read_bytes(),before)
        detail=self.request('/api/runs/'+result['run_id']+'?effort_root='+self.efforts[0]['ordinal'])
        self.assertTrue(detail['application']['native']['receipt_retained'])
        archive=self.runs/result['run_id']/'observation-evidence';digest=hashlib.sha256((archive/'manifest.json').read_bytes()).hexdigest()
        # Frozen archived occurrence takes the same scoped source gate without reexecuting the observed actors.
        frozen=self.server.application.reviewed().preflight(self.body(command='archive-draft',operation='acting',selectors={'plan_id':plan,'step_id':step},observation_evidence=str(archive),observation_manifest_sha256=digest))
        self.assertEqual(frozen['operation_evidence']['observation_manifest_sha256'],digest)

    def test_scoped_recall_selection_freezes_whole_source_and_reuse_remains_unbound(self):
        initial=self.request('/api/application/start',202,self.body(command='original-source'));result=self.completed(initial)
        results=self.request('/api/search?q=investigation&effort_root='+self.efforts[0]['ordinal'])['results']
        actual=next(s for s in results if s.get('field')=='opermem-actor' and s['source_id'].endswith(':work'))
        selection={'source_id':actual['source_id'],'source_text_sha256':actual['source_text_sha256']}
        self.request('/api/application/start',422,self.body(1,command='foreign-source',sources=[selection]))
        bad={**selection,'source_text_sha256':'0'*64}
        self.request('/api/application/start',422,self.body(command='stale-source',sources=[bad]))
        launch=self.request('/api/application/start',202,self.body(command='reuse-source',sources=[selection]));next_result=self.completed(launch)
        self.assertEqual(next_result['status'],'finished',next_result)
        detail=self.request('/api/runs/'+next_result['run_id']+'?effort_root='+self.efforts[0]['ordinal'])
        source=detail['preparation']['host_sources'][0]
        import base64
        packet=json.loads(base64.b64decode(source['bytes_base64']))
        self.assertEqual(packet['source']['source_id'],actual['source_id']);self.assertEqual(packet['source']['source_text_sha256'],actual['source_text_sha256'])
        self.assertFalse(packet['native_retained_experience']);self.assertIn('Useful investigation',packet['source']['text'])
        draft=self.request('/api/runs/'+next_result['run_id']+'/reuse-setup?effort_root='+self.efforts[0]['ordinal'])['fields']
        self.assertEqual(draft['sources'],[selection]);self.assertIsNone(draft['effort_root']);self.assertIsNone(draft['target'])

    def test_launch_failure_and_original_callback_gap_recover_with_zero_effects(self):
        body=self.body(command='driver-startup-failure')
        with patch.object(reviewed.subprocess,'Popen',side_effect=OSError('fixture driver startup refused')):
            failed=self.request('/api/application/start',202,body)
        self.assertEqual(failed['status'],'failed');self.assertIsNone(failed['run_id']);self.assertIsNone(failed['execution_id'])
        self.assertEqual(self.request('/api/application/start',202,body)['launch_id'],failed['launch_id'])
        self.assertEqual(self.server.application.children,[])
        with patch.dict(os.environ,{'REVIEWED_FIXTURE_CALLBACK_GAP':'1'}):
            launch=self.request('/api/application/start',202,self.body(command='callback-gap'));result=self.completed(launch)
        self.assertEqual(result['status'],'failed');self.assertTrue(result['prepared_observed']);self.assertTrue(result['execution_claim'])
        self.assertFalse((self.root/'calls.jsonl').exists());self.assertFalse(Path(self.refs[0]['directory']).exists())
        self.assertFalse((self.runs/result['run_id']/'events.sqlite3').exists())
        directory=self.runs/'.opermem-launches'/launch['launch_id'];original=(directory/'prepared-observation.json').read_bytes()
        (directory/'receipt.json').unlink()
        correlation=self.request('/api/runs/'+result['run_id']+'/recover-correlation',body={'effort_root':self.efforts[0]['ordinal']})
        self.assertEqual(correlation['status']['state'],'preparation-failed')
        self.assertEqual((directory/'prepared-observation.json').read_bytes(),original)
        self.assertFalse((self.root/'calls.jsonl').exists());self.assertFalse(Path(self.refs[0]['directory']).exists())
        self.assertEqual(len(self.request('/api/runs?effort_root='+self.efforts[0]['ordinal'])['runs']),1)
