import tempfile
import unittest
import sqlite3
from unittest.mock import patch
from pathlib import Path
from scripts.noetic_scope import ScopeStore


class HistoryNamespaceWitnessTests(unittest.TestCase):
    def test_current_read_namespace_not_cached_constructor_value(self):
        with tempfile.TemporaryDirectory(prefix='noetic-history-witness-') as home:
            store = ScopeStore(Path(home) / 'namespace.sqlite3', root_mandate={'purpose':'Fixture'}, human_ref={'fixture':True}, source_ref={'fixture':True})
            namespace = store.namespace
            store.namespace = 'deliberately-stale-constructor-value'
            page = store.history()
            self.assertEqual(page['namespace_id'], namespace)
            self.assertEqual(page['next_after'], page['records'][-1]['sequence'])
            empty = store.history(after=page['next_after'])
            self.assertEqual(empty['namespace_id'], namespace)
            self.assertEqual(empty['records'], [])
            self.assertEqual(empty['next_after'], page['next_after'])
            self.assertNotIn('namespace_id', store.branch(), 'only history contract extended')

    def test_namespace_and_rows_share_wal_read_snapshot(self):
        with tempfile.TemporaryDirectory(prefix='noetic-history-wal-') as home:
            store = ScopeStore(Path(home) / 'namespace.sqlite3', root_mandate={'purpose':'Fixture'}, human_ref={'fixture':True}, source_ref={'fixture':True})
            with sqlite3.connect(store.path) as db:
                db.execute('PRAGMA journal_mode=WAL')
            original = store._position
            namespace = store.namespace
            committed = False
            def position(db, ordinal):
                nonlocal committed
                value = original(db, ordinal)
                if not committed:
                    committed = True
                    with store._write() as writer:
                        writer.execute("UPDATE metadata SET value=? WHERE key='namespace'", ('owned-new-namespace',))
                        store._event(writer, '0', 'owned-concurrent-event', {'fixture':True}, {'fixture':'WAL'})
                return value
            with patch.object(store, '_position', side_effect=position):
                page = store.history()
            self.assertEqual(page['namespace_id'], namespace)
            self.assertNotIn('owned-concurrent-event', [row['kind'] for row in page['records']])
            fresh = store.history()
            self.assertEqual(fresh['namespace_id'], 'owned-new-namespace')
            self.assertIn('owned-concurrent-event', [row['kind'] for row in fresh['records']])


if __name__ == '__main__':
    unittest.main()
