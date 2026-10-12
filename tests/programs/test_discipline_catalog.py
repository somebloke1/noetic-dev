"""Read-only discipline catalog at the authenticated HTTP boundary."""
from contextlib import closing
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from scripts import noetic_disciplines as disciplines
from scripts import noetic_web as web
from scripts.noetic_scope import Scope, ScopeStore


class DisciplineCatalogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.namespace = self.root / 'namespace.sqlite3'
        self.server = web.create_server(self.root / 'runs', port=0, namespace_path=self.namespace)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)

    def request(self, path, expected=200, *, paired=True, method='GET'):
        headers = {'Authorization': f'Bearer {self.server.token}'} if paired else {}
        with closing(http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)) as connection:
            connection.request(method, path, headers=headers)
            response = connection.getresponse()
            body = response.read()
            self.assertEqual(response.status, expected, body)
            return json.loads(body) if body else None

    def setup_instances(self):
        store = ScopeStore(self.namespace, root_mandate={'purpose': 'catalog fixture'},
            human_ref={'fixture': 'human'}, source_ref={'fixture': 'setup'})
        owners = [store.create_effort(intent=name, environment={'cwd': str(self.root)},
            mandate={'purpose': name}, origin='human', human_ref={'fixture': 'human'},
            source_ref={'fixture': name}) for name in ('A', 'B', 'empty')]
        instances = []
        for owner in owners[:2]:
            instances.append(store.create_discipline(owner['ordinal'], scope=Scope.effort(owner['ordinal']),
                initiator=owner['ordinal'], definition_ref=disciplines.definition('cognition'), intent=owner['intent'],
                source_ref={'fixture': 'instance'}))
        scope = Scope.effort(owners[0]['ordinal'])
        participant = store.delegate(owners[0]['ordinal'], scope=scope, mandate={'purpose': 'nested initiator'},
            origin='human', human_ref={'fixture': 'human'}, source_ref={'fixture': 'participant'}, discipline_id=instances[0]['id'])
        nested = store.create_discipline(owners[0]['ordinal'], scope=scope, initiator=participant['ordinal'],
            definition_ref=disciplines.definition('development'), intent='nested fixture', parent_instance=instances[0]['id'],
            source_ref={'fixture': 'nested'})
        execution = store.create_execution(nested['id'], scope=scope, native_ref={'run_id': 'actual-fixture-run'},
            source_ref={'fixture': 'execution'})
        return owners, instances, nested, execution

    def snapshot(self):
        return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob('*') if p.is_file()}

    def test_absent_namespace_is_declared_without_registration(self):
        before = self.snapshot()
        result = self.request('/api/disciplines?scope=application')
        self.assertFalse(result['namespace_registered'])
        self.assertIsNone(result['namespace_id'])
        self.assertEqual(result['instances'], [])
        self.assertEqual({d['pattern'] for d in result['definitions']}, {'cognition', 'development'})
        for item in result['definitions']:
            self.assertEqual(item['definition_ref'], disciplines.definition(item['pattern']))
            self.assertTrue(item['definition']['phases'])
        self.request('/api/disciplines?effort_root=0.0', 422)
        self.assertEqual(before, self.snapshot())

    def test_scoped_actual_instances_nested_executions_and_pagination(self):
        owners, instances, nested, execution = self.setup_instances()
        before = self.snapshot()
        a = self.request('/api/disciplines?effort_root=' + owners[0]['ordinal'])
        b = self.request('/api/disciplines?effort_root=' + owners[1]['ordinal'])
        self.assertEqual([i['id'] for i in a['instances']], [instances[0]['id'], nested['id']])
        self.assertEqual([i['id'] for i in b['instances']], [instances[1]['id']])
        self.assertEqual(a['instances'][1], {**nested, 'executions': [execution]})
        self.assertEqual(a['instances'][0], {**instances[0], 'executions': []})
        global_page = self.request('/api/disciplines?scope=application&limit=1')
        self.assertEqual(global_page['instances'][0]['id'], instances[0]['id'])
        next_page = self.request('/api/disciplines?scope=application&after=' + str(global_page['next_after']))
        self.assertEqual([i['id'] for i in next_page['instances']], [instances[1]['id'], nested['id']])
        self.assertIsNone(next_page['next_after'])
        self.assertEqual(self.request('/api/disciplines?effort_root=' + owners[2]['ordinal'])['instances'], [])
        self.assertEqual(self.request('/api/disciplines?scope=application&after=999')['instances'], [])
        self.assertTrue(a['namespace_registered'])
        self.assertEqual(a['selection'], {'kind': 'effort', 'effort_root': owners[0]['ordinal']})
        self.assertEqual(before, self.snapshot())

    def test_selection_auth_and_query_errors(self):
        self.setup_instances()
        before = self.snapshot()
        self.request('/api/disciplines?scope=application', 401, paired=False)
        for query in ('', '?scope=application&effort_root=0.0', '?scope=', '?scope=unknown',
                      '?scope=application&limit=0', '?scope=application&limit=1001', '?scope=application&after=-1',
                      '?scope=application&limit=no', '?scope=application&scope=application',
                      '?scope=application&namespace_path=foreign', '?scope=application&effort_root='):
            self.request('/api/disciplines' + query, 400)
        for ordinal in ('0.999', '0.00', 'foreign', '0.0.0'):
            self.request('/api/disciplines?effort_root=' + ordinal, 422)
        self.assertEqual(before, self.snapshot())

    def test_cursor_signed64_boundary_before_namespace_read(self):
        for registered in (False, True):
            if registered:
                self.setup_instances()
            with self.subTest(registered=registered):
                before = self.snapshot()
                self.request('/api/disciplines?scope=application&after=9223372036854775808', 400)
                result = self.request('/api/disciplines?scope=application&after=9223372036854775807')
                self.assertEqual(result['instances'], [])
                self.assertIsNone(result['next_after'])
                self.assertEqual(result['after'], 9223372036854775807)
                self.assertEqual(result['namespace_registered'], registered)
                self.assertEqual(before, self.snapshot())

    def test_malformed_namespace_fails_without_repair(self):
        self.namespace.write_bytes(b'not sqlite')
        before = self.snapshot()
        self.request('/api/disciplines?scope=application', 422)
        self.assertEqual(before, self.snapshot())
        self.namespace.unlink()
        with sqlite3.connect(self.namespace) as db:
            db.execute('CREATE TABLE metadata(key TEXT,value TEXT)')
            db.execute("INSERT INTO metadata VALUES('schema','wrong')")
        before = self.snapshot()
        self.request('/api/disciplines?scope=application', 422)
        self.assertEqual(before, self.snapshot())

    def test_fixed_shell_assets_public_mime_and_no_arbitrary_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for route, (name, mime) in web.STATIC_ASSETS.items():
                target = base / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'fixture asset')
            with patch.object(web, 'WEB_DIR', base):
                for route, (_, mime) in web.STATIC_ASSETS.items():
                    with closing(http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)) as connection:
                        connection.request('GET', route)
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        self.assertTrue(response.getheader('Content-Type').startswith(mime))
                        if mime == 'font/woff2':
                            self.assertNotIn('charset', response.getheader('Content-Type'))
                        self.assertEqual(response.read(), b'fixture asset')
                self.request('/fonts/unlisted.woff2', 401, paired=False)
                self.request('/fonts/unlisted.woff2', 404)
                self.request('/fonts/../namespace.sqlite3', 404)
