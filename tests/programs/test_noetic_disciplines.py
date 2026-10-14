"""Disposable canonical scopes and actual model-free client processes."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout, closing
from functools import wraps
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts import noetic_controller as controller
from scripts import noetic_disciplines as disciplines
from scripts import noetic_harness as harness
from scripts import noetic_projects as projects
from scripts.noetic_scope import Scope, ScopeError, ScopeStore, Target
from tests.programs.test_noetic_harness import result_for, protocol, process_command


def frozen_v1_development(test):
    @wraps(test)
    def run_legacy(self):
        current = json.loads((controller.PATTERN_DIR / 'development.json').read_text())
        legacy = {key: value for key, value in current.items() if key != 'delegation'}
        legacy['version'] = 1
        digest = hashlib.sha256(json.dumps(legacy, sort_keys=True, ensure_ascii=True, allow_nan=False).encode()).hexdigest()
        self.assertEqual(digest, '8cb8f909044d920cadd906529faa536866f707441b83a4f3a869b53cf65a9f63')
        directory = self.root / 'frozen-v1-patterns'
        directory.mkdir()
        (directory / 'development.json').write_text(json.dumps(legacy))
        with patch.object(controller, 'PATTERN_DIR', directory):
            test(self)
        self.assertEqual(current['version'], 2)
        for run in self.runs.iterdir():
            if not (run / 'controller.sqlite3').is_file():
                continue
            frozen = (run / 'options.json').read_bytes()
            self.assertNotIn('delegation_version', json.loads(frozen))
            before = harness.inspect(run)
            self.assertEqual(before['pattern'], legacy)
            with redirect_stdout(io.StringIO()):
                _, state = harness.drive(run, max_activations=1)
            self.assertEqual(state['status'], before['status'])
            if before['status'] == 'active':
                self.assertGreater(state['version'], before['version'])
            self.assertEqual(state['pattern'], legacy)
            self.assertEqual((run / 'options.json').read_bytes(), frozen)
            self.assertEqual(disciplines.correspondence(run)['definition_ref']['version'], digest)
    return run_legacy


RPC_FIXTURE = r'''
import json,os,sys,time,uuid
from pathlib import Path
assert 'USER_PROVIDED_PASSWORD' not in os.environ
args=sys.argv[1:]
def opt(name): return args[args.index(name)+1]
sid=str(uuid.uuid4()); path=Path(opt('--session-dir'))/(sid+'.jsonl')
path.write_text(json.dumps({'type':'session','id':sid})+'\n')
def emit(x): print(json.dumps(x),flush=True)
for line in sys.stdin:
    req=json.loads(line); kind=req['type']
    data={}
    if kind=='get_state':
        data={'sessionId':sid if os.environ.get('MISSING_ID')!='1' else None,'sessionFile':str(path),
              'model':{'provider':opt('--model').split('/')[0],'id':opt('--model').split('/')[-1]},'thinkingLevel':'high'}
    elif kind=='prompt':
        import sqlite3
        with sqlite3.connect(os.environ['FIXTURE_NAMESPACE']) as db:
            assert any(json.loads(r[0]).get('session_id')==sid for r in db.execute('SELECT native_ref FROM sessions'))
        if os.environ.get('HOLD'):
            Path(os.environ['HOLD']+'.started').touch()
            while not Path(os.environ['HOLD']).exists(): time.sleep(.02)
        if os.environ.get('EFFECT'):
            p=Path(os.environ['EFFECT']);p.write_text(p.read_text()+'x' if p.exists() else 'x')
        emit({'type':'response','id':req['id'],'command':kind,'success':True,'data':{}})
        emit({'type':'agent_start'}); emit({'type':'agent_end','willRetry':False})
        emit({'type':'agent_settled'}); continue
    elif kind=='get_messages':
        text=os.environ['FIXTURE_RESULT']; data={'messages':[{'role':'assistant','stopReason':'stop','content':[{'type':'text','text':text}]}]}
        with path.open('a') as f: f.write(json.dumps(data)+'\n')
    emit({'type':'response','id':req['id'],'command':kind,'success':True,'data':data})
'''


class DisciplineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / 'workspace'; self.workspace.mkdir()
        env = dict(os.environ); env.pop('USER_PROVIDED_PASSWORD', None)
        subprocess.run(['git', 'init', str(self.workspace)], env=env, check=True, capture_output=True)
        (self.workspace / 'product.txt').write_text('baseline\n')
        self.runs = self.root / 'runs'
        self.namespace = self.root / 'ordinals.sqlite3'
        self.store = ScopeStore(self.namespace, root_mandate={'purpose':'fixture owner'},
                                human_ref={'fixture':'human'}, source_ref={'fixture':'init'})
        self.efforts = [self.store.create_effort(intent=name, environment={'cwd':str(self.workspace)},
            mandate={'purpose':name}, origin='human', human_ref={'fixture':'human'}, source_ref={'fixture':name})
            for name in ('A','B','R')]
        self.adapter = disciplines.Disciplines(self.namespace)
        self.rpc = self.root / 'rpc.py'; self.rpc.write_text(RPC_FIXTURE)
        self.calls=[]
        guard=patch.object(harness,'actor_command',side_effect=self.command);guard.start();self.addCleanup(guard.stop)

    def instance(self, effort=0, name='one', **kwargs):
        owner=self.efforts[effort]
        return self.adapter.create_instance(command_id=name, effort_root=owner['ordinal'],
            initiator=kwargs.pop('initiator',owner['ordinal']), pattern=kwargs.pop('pattern','cognition'),
            intent=name, environment=owner['environment'], **kwargs)

    def request(self, instance, **kwargs):
        return {'namespace_path':str(self.namespace),'effort_root':instance['effort'],
                'discipline_id':instance['id'],'environment':instance['environment'],
                'origin':'human','human_ref':{'fixture':'owner'},**kwargs}

    def start(self, instance=None, **kwargs):
        with redirect_stdout(io.StringIO()):
            return harness.start(kwargs.pop('pattern','cognition'), 'bounded fixture task', self.workspace,
                self.runs, model='fixture/model', scope_request=self.request(instance) if instance else None, **kwargs)

    def command(self, run_dir, state, options, prompt):
        activation=state['activations'][state['current_activation']]
        self.calls.append((run_dir.name,activation['id']))
        result=result_for(state)
        if options['client']=='pi':
            env=dict(os.environ);env.update(FIXTURE_RESULT=json.dumps(result),FIXTURE_NAMESPACE=str(self.namespace),USER_PROVIDED_PASSWORD='public-test-sentinel')
            return [sys.executable,str(self.rpc),'--mode','json','-p','--model','fixture/model'],env
        return process_command(protocol(json.dumps(result),'opencode',f'{run_dir.name}-{activation["id"]}'))

    @frozen_v1_development
    def test_effort_meaning_reaches_fresh_workers_and_reviewers_without_replacing_task(self):
        task = 'For this task, depart from the standing intention and compare seven alternatives.'
        for index in (0, 1):
            instance = self.instance(index, f'context-{index}', pattern='development')
            with redirect_stdout(io.StringIO()):
                run, state = harness.start('development', task, self.workspace, self.runs,
                    model='fixture/model', scope_request=self.request(instance), max_activations=2)
            context = json.loads((run/'options.json').read_text())['scope']['effort_context']
            self.assertEqual(context['ordinal'], self.efforts[index]['ordinal'])
            self.assertEqual(context['intent'], self.efforts[index]['intent'])
            self.assertEqual(context['mandate'], self.efforts[index]['mandate'])
            for activation in ('activation-0', 'activation-1'):
                prompt = (run/'activations'/activation/'prompt.txt').read_text()
                payload = json.loads(prompt[prompt.index('\n\n{')+2:])
                self.assertEqual(payload['purpose'], task)
                self.assertEqual(payload['input_artifacts']['external.purpose']['content'], task)
                self.assertEqual(payload['responsibility']['effort_context'], context)
                self.assertNotIn('external.governing', payload['input_artifacts'])
                self.assertIn('declared intention, not verified source evidence or a current runtime inventory', prompt)
                self.assertIn('latest explicit task may depart from the standing effort intention', prompt)

    def test_effort_context_survives_restart_and_cognitive_return_without_rewriting_prior_prompt(self):
        instance = self.instance(name='frozen-context')
        run, _ = self.start(instance, max_activations=1)
        first = run/'activations/activation-0/prompt.txt'; original = first.read_bytes()
        context = json.loads((run/'options.json').read_text())['scope']['effort_context']
        with self.store._write() as db:
            db.execute('UPDATE efforts SET intent=? WHERE ordinal=?', ('Later declared intention', instance['effort']))
        base_result = result_for
        def returning_result(state):
            activation = state['activations'][state['current_activation']]
            if activation['phase'] == 'P3' and not state['returns_used']:
                return {'outcome':'return','target':'P1','reason':'Missing observation',
                        'question':'Which observation distinguishes these?', 'content':{'conditions':['Unresolved']}}
            return base_result(state)
        self.adapter = disciplines.Disciplines(self.namespace)
        with patch(f'{__name__}.result_for', side_effect=returning_result), redirect_stdout(io.StringIO()):
            _, state = harness.drive(run)
        self.assertEqual(state['status'], 'completed'); self.assertEqual(state['returns_used'], 1)
        self.assertEqual(first.read_bytes(), original)
        for path in sorted((run/'activations').glob('*/prompt.txt')):
            prompt = path.read_text(); payload = json.loads(prompt[prompt.index('\n\n{')+2:])
            self.assertEqual(payload['responsibility']['effort_context'], context)
            self.assertNotIn('Later declared intention', prompt)
        self.assertEqual(disciplines.validate_binding(run)['effort_context'], context)

    def test_old_scoped_execution_and_unassigned_history_do_not_invent_effort_context(self):
        run, _ = self.start(self.instance(name='old-shape'), max_activations=0)
        options = json.loads((run/'options.json').read_text()); binding = options['scope']
        binding.pop('effort_context')
        (run/'options.json').write_text(json.dumps(options))
        with sqlite3.connect(run/'events.sqlite3') as db:
            db.execute("UPDATE events SET data=? WHERE kind='scope.bound'", (json.dumps(binding),))
        with self.store._write() as db:
            native = json.loads(db.execute('SELECT native_ref FROM executions WHERE id=?', (binding['execution_id'],)).fetchone()[0])
            native.pop('effort_context')
            db.execute('UPDATE executions SET native_ref=? WHERE id=?', (json.dumps(native), binding['execution_id']))
        self.assertEqual(disciplines.validate_binding(run), binding)
        with redirect_stdout(io.StringIO()): harness.drive(run, 1)
        prompt = (run/'activations/activation-0/prompt.txt').read_text()
        payload = json.loads(prompt[prompt.index('\n\n{')+2:])
        self.assertIsNone(payload['responsibility']['effort_context'])
        self.assertIn('No owning effort intention snapshot was recorded for this execution', prompt)
        legacy, _ = self.start(max_activations=1)
        prompt = (legacy/'activations/activation-0/prompt.txt').read_text()
        payload = json.loads(prompt[prompt.index('\n\n{')+2:])
        self.assertNotIn('responsibility', payload)

    def test_a_b_r_two_instances_repeated_executions_and_native_source_accountability(self):
        a1=self.instance(name='a-one');a2=self.instance(name='a-two')
        b=self.instance(1,'b');r=self.instance(2,'r')
        runs=[self.start(i,client='pi' if index==0 else 'opencode') for index,i in enumerate((a1,a2,b,r,a1))]
        positions=[];executions=[]
        for (run,state),instance in zip(runs,(a1,a2,b,r,a1)):
            self.assertEqual(state['status'],'completed')
            c=disciplines.correspondence(run,namespace_path=self.namespace,effort_root=instance['effort'])
            self.assertEqual(c['correlation_status'],'assigned');self.assertEqual(c['discipline_id'],instance['id'])
            self.assertEqual(len(c['participants']),4);executions.append(c['execution_id'])
            for p in c['participants']:
                positions.append(p['ordinal']);self.assertTrue(p['ordinal'].startswith(instance['initiator']+'.'))
                self.assertEqual(p['origin'],'human');self.assertIsNotNone(p['target'])
                self.assertEqual(p['position_status'],'closed');self.assertEqual(p['session_status'],'closed')
                self.assertEqual(p['native_agent_ref']['actor_id'],state['activations'][p['activation_id']]['actor_id'])
                native=p['native_session_ref'];self.assertEqual(state['activations'][p['activation_id']]['session_ref'],native['client']+':'+native['session_id'])
                prompt=(run/'activations'/p['activation_id']/'prompt.txt').read_text()
                payload=json.loads(prompt[prompt.index('\n\n{')+2:])
                self.assertEqual(payload['responsibility']['ordinal'],p['ordinal'])
                self.assertEqual(payload['responsibility']['effort_root'],instance['effort'])
                if native['client']=='pi':
                    self.assertTrue(Path(native['context_file']).exists());self.assertEqual(native['observation'],'rpc-get_state-before-prompt')
                    self.assertEqual(payload['responsibility']['target'],p['target'])
                else:self.assertIsNone(native['context_file'])
            history=self.adapter.inspect_execution(json.loads((run/'options.json').read_text())['scope'],run)['history']
            artifacts=[e for e in history if e['kind']=='structured-controller-event' and e['data']['artifact']]
            self.assertTrue(any(e['data']['artifact']['produced_by'] for e in artifacts))
            self.assertTrue(any(e['data']['controller_event']['kind']=='command.accepted' for e in history if e['kind']=='structured-controller-event'))
        self.assertEqual(len(set(positions)),20);self.assertEqual(len(set(executions)),5)
        self.assertIsNone(self.store.position('0')['current_instantiation'])
        self.assertEqual(self.store.position(self.efforts[0]['ordinal'])['status'],'open')

    def test_wrong_effort_environment_definition_and_stale_initiator_reject_before_run_effects(self):
        instance=self.instance();request=self.request(instance)
        for override in ({'effort_root':self.efforts[1]['ordinal']},{'environment':{'cwd':str(self.root)}},
                         {'discipline_id':999}):
            with self.assertRaises(ScopeError):
                harness.start('cognition','task',self.workspace,self.runs,scope_request={**request,**override},max_activations=0)
        with self.assertRaises(ScopeError):
            harness.start('development','task',self.workspace,self.runs,scope_request=request,max_activations=0)
        scope=Scope.effort(instance['effort']);pos=instance['initiator']
        occupant=self.store.instantiate(pos,scope=scope,native_ref={'fixture':'actual fixture actor'},source_ref={'fixture':'native'})
        old=self.store.open_session(pos,occupant['sequence'],scope=scope,native_ref={'session_id':'old-native-fixture'},source_ref={'fixture':'observed'})
        self.store.open_session(pos,occupant['sequence'],scope=scope,native_ref={'session_id':'new-native-fixture'},source_ref={'fixture':'observed'})
        with self.assertRaises(ScopeError):
            harness.start('cognition','task',self.workspace,self.runs,scope_request=self.request(instance,origin='agent',human_ref=None,delegator=old.as_dict()),max_activations=0)
        self.assertFalse(self.runs.exists());self.assertFalse(self.calls)

    def test_agent_assignment_nested_actual_participant_and_later_staleness(self):
        effort=self.efforts[0]['ordinal'];scope=Scope.effort(effort)
        actor=self.store.instantiate(effort,scope=scope,native_ref={'fixture':'actor'},source_ref={'fixture':'actual'})
        initiator=self.store.open_session(effort,actor['sequence'],scope=scope,native_ref={'session_id':'initial-fixture'},source_ref={'fixture':'actual'})
        instance=self.instance(initiating_target=initiator.as_dict())
        with redirect_stdout(io.StringIO()):
            run,state=harness.start('cognition','task',self.workspace,self.runs,model='fixture/model',max_activations=0,
                scope_request=self.request(instance,origin='agent',human_ref=None,delegator=initiator.as_dict()))
        activation=state['activations'][state['current_activation']]
        binding=json.loads((run/'options.json').read_text())['scope']
        _,state=harness.drive(run,1)
        participant=self.adapter.lookup(run,activation['id'])
        self.assertIsNotNone(self.adapter.target(run,activation['id']))
        self.store.open_session(effort,actor['sequence'],scope=scope,native_ref={'session_id':'successive-fixture'},source_ref={'fixture':'new actual context'})
        self.assertEqual(self.adapter.participant(binding,run,activation)['ordinal'],participant['ordinal'])
        before_calls=len(self.calls)
        _,failed=harness.drive(run)
        self.assertEqual(failed['status'],'failed');self.assertIn('before effects',failed['reason'])
        self.assertEqual(len(self.calls),before_calls)
        self.assertEqual(len(disciplines.correspondence(run)['participants']),1)
        mandate=self.store.mandates(participant['ordinal'])[0]
        self.assertEqual(mandate['origin'],'agent');self.assertEqual(mandate['delegator'],initiator.as_dict())

    def test_pause_resume_envelope_replay_restart_and_uncertain_effect_no_duplicate(self):
        instance=self.instance();run,state=self.start(instance,max_activations=0)
        harness.pause(run);self.assertEqual(harness.drive(run)[1],state);self.assertFalse(self.calls)
        harness.resume(run)
        submit=controller.submit_result
        with patch.object(controller,'submit_result',side_effect=RuntimeError('before delivery')):
            with self.assertRaisesRegex(RuntimeError,'before delivery'):harness.drive(run,1)
        self.assertEqual(len(self.calls),1)
        envelope=json.loads((run/'activations/activation-0/submission.json').read_text())
        before=disciplines.correspondence(run)['participants'][0]['ordinal']
        state=harness.drive(run,0)[1]
        self.assertEqual(len(self.calls),1);self.assertEqual(disciplines.correspondence(run)['participants'][0]['ordinal'],before)
        submit(run/'controller.sqlite3',**envelope)
        self.adapter=disciplines.Disciplines(self.namespace)
        _,completed=harness.drive(run)
        self.assertEqual(completed['status'],'completed');self.assertEqual(len(self.calls),4)
        self.assertEqual(len(disciplines.correspondence(run)['participants']),4)
        run2,state2=self.start(instance,max_activations=0)
        def fault(run,state,options):
            (self.workspace/'retained-effect').write_text('effect')
            raise RuntimeError('crash after effect')
        with patch.object(harness,'invoke_actor',side_effect=fault):
            with self.assertRaisesRegex(RuntimeError,'crash after effect'):harness.drive(run2)
        with patch.object(harness,'invoke_actor') as invoke:
            failed=harness.drive(run2)[1];invoke.assert_not_called()
        self.assertEqual(failed['status'],'failed');self.assertIn('no automatic replay',failed['reason'])
        p=disciplines.correspondence(run2)['participants'][0]
        self.assertIsNone(p['target']);self.assertIsNone(p['native_session_ref']);self.assertEqual(p['position_status'],'closed')
        self.assertEqual((self.workspace/'retained-effect').read_text(),'effect')

    def test_canonical_commit_cache_gap_concurrent_replay_and_conflicting_reuse(self):
        instance=self.instance();run,state=self.start(instance,max_activations=0)
        binding=json.loads((run/'options.json').read_text())['scope'];activation=state['activations'][state['current_activation']]
        original=self.adapter.participant(binding,run,activation)
        with closing(sqlite3.connect(self.adapter.cache)) as db, db:db.execute('DELETE FROM commands')
        with ThreadPoolExecutor(max_workers=4) as pool:
            values=list(pool.map(lambda _:disciplines.Disciplines(self.namespace).participant(binding,run,activation),range(4)))
        self.assertEqual({v['ordinal'] for v in values},{original['ordinal']})
        with self.assertRaises(ScopeError):self.adapter.participant(binding,run,{**activation,'role':'changed'})
        again=self.instance();self.assertEqual(again['id'],instance['id'])
        with self.assertRaises(ScopeError):self.instance(pattern='development')
        harness.drive(run,1)
        with closing(sqlite3.connect(self.adapter.cache)) as db, db:db.execute('DELETE FROM commands')
        harness.drive(run,0)
        self.assertEqual(len(disciplines.correspondence(run)['participants']),1)

    def test_actual_rpc_live_context_before_prompt_missing_identity_cancel_and_legacy(self):
        instance=self.instance();run,state=self.start(instance,client='pi',max_activations=0)
        hold=self.root/'gate'
        with patch.dict(os.environ,{'HOLD':str(hold)}):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(harness.drive,run,1)
                deadline=time.monotonic()+10
                while not Path(str(hold)+'.started').exists() and time.monotonic()<deadline:time.sleep(.02)
                self.assertTrue(Path(str(hold)+'.started').exists())
                live=disciplines.correspondence(run)['participants'][0]
                self.assertEqual(live['session_status'],'open');self.assertIsNotNone(live['target'])
                self.assertTrue(Path(live['native_session_ref']['context_file']).exists())
                nested=self.instance(name='actual-nested',initiator=live['ordinal'],
                    initiating_target=live['target'],parent_instance=instance['id'])
                nested_run,nested_state=self.start(nested,max_activations=1)
                self.assertEqual(nested['initiator'],live['ordinal'])
                self.assertEqual(disciplines.correspondence(nested_run)['discipline_id'],nested['id'])
                self.assertEqual(nested['parent_instance'],instance['id'])
                harness.cancel(run)
                cancelled=future.result(timeout=10)[1]
        self.assertEqual(cancelled['status'],'cancelled');self.assertEqual(disciplines.correspondence(run)['participants'][0]['session_status'],'failed')
        with patch.dict(os.environ,{'MISSING_ID':'1'}):bad,failed=self.start(instance,client='pi')
        self.assertEqual(failed['status'],'failed');p=disciplines.correspondence(bad)['participants'][0]
        self.assertIsNone(p['target']);self.assertEqual(p['position_status'],'closed')
        legacy,_=self.start(max_activations=0)
        self.assertEqual(disciplines.correspondence(legacy)['correlation_status'],'unassigned')
        with self.assertRaises(ScopeError):disciplines.correspondence(legacy,effort_root=instance['effort'])
        with self.assertRaises(ScopeError):disciplines.correspondence(run,effort_root=self.efforts[1]['ordinal'])
        (run/'options.json').unlink()
        with self.assertRaises(ScopeError):disciplines.correspondence(run)

    @frozen_v1_development
    def test_development_review_has_exact_subject_and_all_participants_have_same_true_parent(self):
        instance=self.instance(pattern='development')
        run,state=self.start(instance,pattern='development',verify=[sys.executable,'-c','pass'])
        self.assertEqual(state['status'],'completed')
        c=disciplines.correspondence(run);self.assertEqual(len(c['participants']),8)
        for participant in c['participants']:
            pos=self.store.position(participant['ordinal'])
            self.assertEqual(pos['parent'],instance['initiator'])
        history=self.adapter.inspect_execution(json.loads((run/'options.json').read_text())['scope'],run)['history']
        reviews=[e for e in history if e['kind']=='structured-controller-event' and e['data']['artifact'] and e['data']['artifact']['type']=='qa.review']
        self.assertTrue(reviews)
        for review in reviews:
            self.assertIsNotNone(review['session']);self.assertTrue(review['data']['artifact']['input_bindings']['subject'])
            self.assertIn('native memory standing unchanged',review['data']['semantic_authority'])


    @frozen_v1_development
    def test_maintained_prepared_worktree_keeps_effort_environment_and_rejects_unrelated_preparation(self):
        instance=self.instance(pattern='development')
        readonly=disciplines.Disciplines(self.namespace,readonly=True)
        readonly.validate(self.request(instance),'development',self.workspace)
        owned=projects.task_worktree(self.workspace,work_root=self.root/'owned')
        work=Path(owned['workspace'])
        assignment={**self.request(instance),'preparation':owned}
        with redirect_stdout(io.StringIO()):
            run,state=harness.start('development','prepared task',work,self.runs,model='fixture/model',
                verify=[sys.executable,'-c','pass'],scope_request=assignment)
        self.assertEqual(state['status'],'completed')
        c=disciplines.correspondence(run)
        self.assertEqual(c['environment'],{'cwd':str(self.workspace)})
        self.assertEqual(c['native_run']['execution_workspace'],str(work))
        self.assertEqual(c['native_run']['preparation']['base_commit'],owned['base_commit'])
        other=self.root/'other';other.mkdir();projects.prepare_project(other)
        other_preparation=projects.task_worktree(other,work_root=self.root/'other-owned')
        for bad in ({**owned,'project':str(other)},other_preparation,
                    {**owned,'base_commit':'0'*40},{**owned,'initial_files':{}}):
            with self.assertRaises(ScopeError):
                readonly.validate({**self.request(instance),'preparation':bad},'development',work)
        self.assertEqual(self.store.discipline(instance['id'])['environment'],{'cwd':str(self.workspace)})

    def test_readonly_correspondence_preserves_original_target_and_cli_has_no_store_mutation(self):
        instance=self.instance();run,state=self.start(instance,max_activations=0)
        activation=state['activations'][state['current_activation']]
        binding=json.loads((run/'options.json').read_text())['scope']
        self.adapter.participant(binding,run,activation)
        child_env=dict(os.environ);child_env.pop('USER_PROVIDED_PASSWORD',None)
        observed=subprocess.run([sys.executable,'-c',"import json,uuid;print(json.dumps({'client':'fixture','session_id':str(uuid.uuid4()),'context_file':None,'source':'actual-fixture-stdout'}))"],
                                capture_output=True,text=True,check=True,env=child_env)
        self.adapter.observed(binding,run,activation,json.loads(observed.stdout))
        c=disciplines.correspondence(run);participant=c['participants'][0]
        scoped=Scope.effort(instance['effort']);target=Target(**participant['target'])
        # A different retained context must not rewrite the activation's exact correspondence.
        replacement=self.store.open_session(target.ordinal,target.instantiation,scope=scoped,
                    native_ref={'session_id':'a-later-native-context'},source_ref={'fixture':'another context'})
        self.assertNotEqual(replacement,target)
        before=self.namespace.read_bytes();cache_before=self.adapter.cache.read_bytes()
        after=disciplines.correspondence(run,namespace_path=self.namespace,effort_root=instance['effort'])
        self.assertEqual(after['participants'][0]['target'],participant['target'])
        readonly=disciplines.Disciplines(self.namespace,readonly=True)
        with self.assertRaises(ScopeError):readonly.validate({**self.request(instance),'effort_root':self.efforts[1]['ordinal']},'cognition',self.workspace)
        child_env=dict(os.environ);child_env.pop('USER_PROVIDED_PASSWORD',None);child_env['NOETIC_APP_HOME']=str(self.root/'unused-app-home')
        output=subprocess.run([sys.executable,'-m','scripts.noetic_disciplines','--namespace-path',str(self.namespace),'inspect',str(run)],
                              capture_output=True,text=True,env=child_env,check=True)
        self.assertEqual(json.loads(output.stdout)['participants'][0]['target'],participant['target'])
        self.assertEqual(self.namespace.read_bytes(),before);self.assertEqual(self.adapter.cache.read_bytes(),cache_before)
        self.assertFalse((self.root/'unused-app-home').exists())
        assignment=self.root/'assignment.json';assignment.write_text(json.dumps(self.request(instance)))
        task=self.root/'task.md';task.write_text('explicit CLI fixture')
        started=subprocess.run([sys.executable,'-m','scripts.noetic_harness','start','cognition',str(task),'--workspace',str(self.workspace),
                 '--runs-dir',str(self.runs),'--scope-request',str(assignment),'--max-activations','0'],capture_output=True,text=True,env=child_env)
        self.assertEqual(started.returncode,2,started.stderr)
        self.assertIn('Kernel status: active',started.stdout)

    def test_readonly_preflight_rejects_request_namespace_before_instance_lookup(self):
        instance=self.instance()
        foreign=self.root/'foreign.sqlite3'
        ScopeStore(foreign,root_mandate={'purpose':'other namespace'},human_ref={'fixture':'other'},source_ref={'fixture':'other'})
        readonly=disciplines.Disciplines(self.namespace,readonly=True)
        with patch.object(readonly.store,'discipline',side_effect=AssertionError('Instance IDs must not be read')):
            with self.assertRaisesRegex(ScopeError,'configured namespace'):
                readonly.validate({**self.request(instance),'namespace_path':str(foreign)},'cognition',self.workspace)

    def test_corrupt_binding_rejects_before_effects_exports_controls_and_canonical_reads(self):
        instance=self.instance()
        for change_journal in (False,True):
            with self.subTest(change_journal=change_journal):
                run,state=self.start(instance,max_activations=0)
                original=json.loads((run/'options.json').read_text())
                edited=json.loads(json.dumps(original));edited['scope']['environment']={'cwd':str(self.root)}
                (run/'options.json').write_text(json.dumps(edited))
                if change_journal:
                    with closing(sqlite3.connect(run/'events.sqlite3')) as db,db:
                        db.execute("UPDATE events SET data=? WHERE kind='scope.bound'",(json.dumps(edited['scope']),))
                snapshots={name:(run/name).read_bytes() for name in ('controller.sqlite3','events.sqlite3','controller.json','work.md')}
                before_calls=len(self.calls)
                for operation in (lambda:harness.drive(run,1),lambda:harness._export(run,state),
                                  lambda:harness.pause(run),lambda:harness.resume(run),lambda:harness.cancel(run)):
                    with self.assertRaises(ScopeError):operation()
                with self.assertRaises(ScopeError):disciplines.correspondence(run,namespace_path=self.namespace)
                with self.assertRaises(ScopeError):self.adapter.participant(edited['scope'],run,state['activations'][state['current_activation']])
                self.assertEqual(len(self.calls),before_calls)
                self.assertFalse((run/'activations').exists())
                for name,data in snapshots.items():self.assertEqual((run/name).read_bytes(),data)
                # Original accepted authority remains recoverable without current initiator or baseline reauthorization.
                (run/'options.json').write_text(json.dumps(original))
                if change_journal:
                    with closing(sqlite3.connect(run/'events.sqlite3')) as db,db:
                        db.execute("UPDATE events SET data=? WHERE kind='scope.bound'",(json.dumps(original['scope']),))
                self.assertEqual(disciplines.validate_binding(run),original['scope'])
                self.assertEqual(harness.drive(run,1)[1]['status'],'active')

if __name__=='__main__':unittest.main()
