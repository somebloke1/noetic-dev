"""Creation parent remains historical while assignment and parent actors change."""
from contextlib import closing
import unittest
from tests.programs import test_native_effort_context as context_fixture
from scripts import noetic_sessions as sessions

class NativeCreationParentTests(unittest.TestCase):
    setUp = context_fixture.NativeEffortContextTests.setUp
    def child(self):
        store=self.service.registry.domain.store()
        target=self.service.registry.get(self.item['id'])['target']
        position=store.delegate(self.effort,scope=sessions.Scope.effort(self.effort),mandate={'task':'Child task'},origin='agent',delegator=sessions.Target(**target),source_ref={'fixture':'create-child'})
        item=self.service.registry.create(self.cwd,'Child','unused','off',[],self.item['id'],ordinal=position['ordinal'],effort_root=self.effort)
        self.service.registry.attach(item['id'],{'sessionId':item['id'],'sessionFile':str(self.root/'child.jsonl')})
        return self.service.registry.get(item['id'])

    def test_creation_parent_survives_revision_and_succession(self):
        child=self.child();store=self.service.registry.domain.store()
        first=self.service.current_context(child['id'])
        old_target=self.service.registry.get(self.item['id'])['target']
        self.assertEqual(first['creation_parent']['target'],old_target)
        self.assertEqual(first['creation_parent']['native_registry_id'],self.item['id'])
        self.assertEqual(first['position']['logical_parent'],self.effort)
        store.revise_mandate(child['ordinal'],scope=sessions.Scope.effort(self.effort),mandate={'task':'Human revised'},origin='human',human_ref={'fixture':'human'},source_ref={'fixture':'revise'})
        successor=self.service.registry.create(self.cwd,'Successor','unused','off',[],ordinal=self.effort,effort_root=self.effort,succession={'predecessor':1,'handoff':{'text':'Continue'}})
        self.service.registry.attach(successor['id'],{'sessionId':successor['id'],'sessionFile':str(self.root/'successor.jsonl')})
        changed=self.service.current_context(child['id'])
        self.assertIsNone(changed['position']['mandate']['delegator'])
        self.assertEqual(changed['creation_parent'],first['creation_parent'])
        self.assertNotEqual(changed['creation_parent']['target'],self.service.registry.get(successor['id'])['target'])
        new_target=self.service.registry.get(successor['id'])['target']
        store.revise_mandate(child['ordinal'],scope=sessions.Scope.effort(self.effort),mandate={'task':'New parent assignment'},origin='agent',delegator=sessions.Target(**new_target),source_ref={'fixture':'new-assignment'})
        latest=self.service.current_context(child['id'])
        self.assertEqual(latest['position']['mandate']['delegator'],new_target)
        self.assertEqual(latest['creation_parent'],first['creation_parent'])

    def test_no_parent_and_unresolved_parent_are_explicit(self):
        context=self.service.current_context(self.item['id'])
        self.assertEqual(context['creation_parent']['state'],'not-recorded')
        self.assertIsNone(context['creation_parent']['target'])
        child=self.child()
        with closing(self.service.registry.connect()) as db,db:
            db.execute('UPDATE sessions SET session_selector=99 WHERE id=?',(self.item['id'],))
        context=self.service.current_context(child['id'])
        self.assertEqual(context['creation_parent']['state'],'unresolved')
        self.assertEqual(context['creation_parent']['native_registry_id'],self.item['id'])
        self.assertIsNone(context['creation_parent']['target'])

if __name__=='__main__':unittest.main()
