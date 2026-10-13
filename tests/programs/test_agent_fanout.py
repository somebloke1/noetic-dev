"""Bounded native fanout uses exact snapshots and ordinary per-recipient delivery."""
import json
import os
from pathlib import Path
import subprocess
import unittest
import threading
from unittest.mock import patch
from tests.programs import test_native_effort_context as context_fixture
from tests.programs import test_noetic_sessions as broker_fixture
from scripts import noetic_sessions as sessions


class FanoutTests(unittest.TestCase):
    def setUp(self):
        context_fixture.NativeEffortContextTests.setUp(self)
        self.broker.action_lock=threading.RLock()

    def create_child(self, parent=None, effort=None):
        parent = parent or self.service.registry.get(self.item['id'])
        effort = effort or self.effort
        store = self.service.registry.domain.store()
        position = store.delegate(parent['ordinal'], scope=sessions.Scope.effort(effort),
            mandate={'task':'fixture'}, origin='human', human_ref={'fixture':'human'}, source_ref={'fixture':'child'})
        row = self.service.registry.create(self.cwd,'Child','unused','off',[],parent['id'],ordinal=position['ordinal'],effort_root=effort)
        self.service.registry.attach(row['id'],{'sessionId':row['id'],'sessionFile':str(self.root/(row['id']+'.jsonl'))})
        return self.service.registry.get(row['id'])

    def accepted(self, binding_id, **kwargs):
        binding=self.service.registry.domain.store().action(binding_id,scope=sessions.Scope.effort(self.effort))
        return {'accepted':True,'binding_id':binding_id,'target':binding['target'],'provenance':binding['payload']['provenance'],'completion':'observe agent_settled'}

    def test_multicast_dedup_self_scope_and_partial_failure(self):
        child=self.create_child(); source=self.service.registry.get(self.item['id'])
        other=self.service.registry.create(self.cwd,'Other','unused','off',[],ordinal=self.other,effort_root=self.other)
        self.service.registry.attach(other['id'],{'sessionId':other['id'],'sessionFile':str(self.root/'other.jsonl')})
        other=self.service.registry.get(other['id'])
        with patch.object(self.service,'deliver',side_effect=self.accepted) as deliver:
            result=self.broker.handle({'action':'multicast','targets':[child['target'],child['target'],source['target'],other['target']], 'message':'one body','mode':'follow_up'})
        self.assertEqual(deliver.call_count,1)
        self.assertEqual([row['status'] for row in result['results']],['accepted','failed'])
        self.assertEqual([row['reason'] for row in result['excluded']],['duplicate','self'])
        accepted=result['results'][0]['data']
        self.assertEqual(accepted['provenance']['sender'],source['target'])
        self.assertEqual(accepted['provenance']['recipient'],child['target'])
        self.assertEqual(accepted['provenance']['fanout']['batch_id'],result['batch_id'])
        records=[e['record'] for e in self.service.registry.events(source['id'],limit=1000)]
        self.assertEqual(sum(r.get('type')=='agent_fanout_started' for r in records),1)
        self.assertEqual(sum(r.get('type')=='agent_fanout_recipient' for r in records),2)

    def test_empty_invalid_and_explicit_self(self):
        source=self.service.registry.get(self.item['id'])
        with patch.object(self.service,'deliver',side_effect=self.accepted) as deliver:
            self.assertEqual(self.broker.handle({'action':'multicast','targets':[],'message':'empty','mode':'follow_up'})['results'],[])
            self.assertEqual(deliver.call_count,0)
            with self.assertRaises(sessions.SessionError):
                self.broker.handle({'action':'multicast','targets':['0.0'],'message':'wrong selector','mode':'follow_up'})
            result=self.broker.handle({'action':'multicast','targets':[source['target']],'include_self':True,'message':'explicit self','mode':'steer'})
            self.assertEqual(result['results'][0]['status'],'accepted')

    def test_broadcast_population_snapshot_and_successor_failure(self):
        a=self.create_child();b=self.create_child();grandchild=self.create_child(a)
        with patch.object(self.service,'deliver',side_effect=self.accepted):
            direct=self.broker.handle({'action':'broadcast','population':'direct_children','message':'direct','mode':'follow_up'})
            self.assertEqual(direct['recipients'],[a['target'],b['target']])
            descendants=self.broker.handle({'action':'broadcast','population':'descendants','message':'descendants','mode':'follow_up'})
            self.assertEqual(descendants['recipients'],[a['target'],b['target'],grandchild['target']])
        frozen=[]
        mutation_lock=threading.Lock()
        original=self.service.message
        def send(sender,recipient,*args,**kwargs):
            with mutation_lock:
                if not frozen:
                    frozen.append(True)
                    self.create_child()
                    replacement=self.service.registry.create(self.cwd,'Replacement','unused','off',[],ordinal=b['ordinal'],effort_root=self.effort)
                    self.service.registry.attach(replacement['id'],{'sessionId':replacement['id'],'sessionFile':str(self.root/'replacement.jsonl')})
            return original(sender,recipient,*args,**kwargs)
        with patch.object(self.service,'message',side_effect=send),patch.object(self.service,'deliver',side_effect=self.accepted):
            result=self.broker.handle({'action':'broadcast','population':'direct_children','message':'frozen','mode':'follow_up'})
        self.assertEqual(result['recipients'],[a['target'],b['target']])
        self.assertEqual([r['status'] for r in result['results']],['accepted','failed'])
        self.assertEqual(result['results'][1]['target'],b['target'])
        with self.assertRaises(sessions.SessionError):
            self.broker.handle({'action':'broadcast','population':'application','message':'wrong','mode':'follow_up'})

    def test_effort_population_excludes_unobserved_and_requires_explicit_scope(self):
        child=self.create_child();grandchild=self.create_child(child)
        store=self.service.registry.domain.store()
        reserved=store.delegate(self.effort,scope=sessions.Scope.effort(self.effort),mandate={'task':'not observed'},origin='human',human_ref={'fixture':'human'},source_ref={'fixture':'reserve'})
        snapshot=store.native_message_population(sessions.Target(**child['target']),scope=sessions.Scope.effort(self.effort),population='effort')
        source=self.service.registry.get(self.item['id'])
        self.assertEqual(snapshot['recipients'],[source['target'],grandchild['target']])
        self.assertNotIn(reserved['ordinal'],[r['ordinal'] for r in snapshot['recipients']])
        empty=store.native_message_population(sessions.Target(**grandchild['target']),scope=sessions.Scope.effort(self.effort),population='direct_children')
        self.assertEqual(empty['recipients'],[])
        with self.assertRaises(sessions.SessionError):
            self.broker.handle({'action':'broadcast','message':'no population','mode':'follow_up'})
        with self.assertRaises(sessions.SessionError):
            self.broker.handle({'action':'multicast','targets':[child['target']]*129,'message':'too many','mode':'follow_up'})

    def test_failed_delivery_retains_binding_without_retry(self):
        child=self.create_child()
        with patch.object(self.service,'deliver',side_effect=sessions.SessionError(409,'fixture unavailable')) as deliver:
            result=self.broker.handle({'action':'multicast','targets':[child['target']],'message':'one attempt','mode':'follow_up'})
        row=result['results'][0]
        self.assertEqual(deliver.call_count,1)
        self.assertEqual(row['status'],'failed')
        self.assertEqual(row['outcome'],'uncertain')
        binding=self.service.registry.domain.store().action(row['binding_id'],scope=sessions.Scope.effort(self.effort))
        self.assertEqual(binding['target'],child['target'])
        self.assertEqual(binding['payload']['message'],'one attempt')


class NativeFanoutTests(unittest.TestCase):
    setUp=broker_fixture.SessionTests.setUp
    tearDown=broker_fixture.SessionTests.tearDown
    create=broker_fixture.SessionTests.create
    wait=broker_fixture.SessionTests.wait
    register_effort=broker_fixture.SessionTests.register_effort
    records=broker_fixture.SessionTests.records

    def test_actual_tools_deliver_exact_envelopes_once(self):
        parent=self.create();self.wait(parent['id'])
        children=[self.service.create({'prompt':'child','thinking':'low'},parent_id=parent['id']) for _ in range(2)]
        for child in children:self.wait(child['id'])
        script="""
const {default:extension}=await import(process.argv[1]);const tools=new Map();
extension({registerTool:t=>tools.set(t.name,t),registerCommand(){},on(){}});
const params={targets:JSON.parse(process.argv[2]),message:'shared original',mode:'follow_up'};
const response=await tools.get('agent_multicast_send').execute('fixture',params);
console.log(JSON.stringify({names:[...tools.keys()],response:response.details}));
"""
        env={k:v for k,v in os.environ.items() if k!='USER_PROVIDED_PASSWORD'}
        env['NOETIC_SESSION_SOCKET']=str(sessions.socket_path(self.runs,parent['id']))
        completed=subprocess.run(['node','--input-type=module','-e',script,sessions.EXTENSION.as_uri(),json.dumps([c['target'] for c in children])],env=env,capture_output=True,text=True,check=True,timeout=30)
        result=json.loads(completed.stdout)
        self.assertIn('agent_send',result['names']);self.assertIn('agent_broadcast_send',result['names'])
        self.assertEqual([r['status'] for r in result['response']['results']],['accepted','accepted'])
        for child in children:
            self.wait(child['id'])
            received=[r for r in self.records(child['id']) if r.get('type')=='agent_message_received']
            matches=[r for r in received if r['provenance'].get('fanout',{}).get('batch_id')==result['response']['batch_id']]
            self.assertEqual(len(matches),1)
            self.assertEqual(matches[0]['provenance']['sender'],parent['target'])
            self.assertEqual(matches[0]['provenance']['recipient'],child['target'])

if __name__=='__main__':unittest.main()
