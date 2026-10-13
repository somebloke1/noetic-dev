import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[2] / 'scripts/tools/narrative_document.py'
spec = importlib.util.spec_from_file_location('narrative_document', CLI)
module = importlib.util.module_from_spec(spec)


class DocumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec.loader.exec_module(module)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'transcript.html'
        self.run_cli('init', '--title', 'Conversation')

    def run_cli(self, command, *args, payload=None, success=True):
        if payload is not None:
            p = Path(self.tmp.name) / 'payload.json'
            p.write_text(json.dumps(payload), encoding='utf-8')
            args = (*args, '--payload', str(p))
        env = os.environ.copy()
        env.pop('USER_PROVIDED_PASSWORD', None)
        result = subprocess.run([sys.executable, str(CLI), command, str(self.path), *args],
                                text=True, capture_output=True, env=env)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return result

    def model(self):
        return module.read_document(self.path)

    def test_order_identity_and_update(self):
        self.run_cli('apply', payload=[{'op': 'insert', 'entry': {'id': 'a', 'original': 'first'}},
                                       {'op': 'insert', 'entry': {'id': 'b', 'original': 'last'}}])
        original = {e['id']: e['seq'] for e in self.model()['entries']}
        for i in range(12):
            self.run_cli('insert', '--before', 'b', payload={'id': f'gap-{i}', 'original': str(i)})
        self.run_cli('update', 'a', payload={'translation': 'Readable first'})
        entries = self.model()['entries']
        self.assertEqual([e['id'] for e in entries], ['a', *[f'gap-{i}' for i in range(12)], 'b'])
        self.assertEqual({e['id']: e['seq'] for e in entries if e['id'] in original}, original)
        self.assertEqual(entries[0]['original'], 'first')
        self.run_cli('update', 'b', '--before', 'a', payload={'narrative': 'Moved'})
        self.assertEqual(self.model()['entries'][0]['id'], 'b')

    def test_verbatim_html_and_deletion(self):
        text = '  <tag>&"\n</script><script>alert(1)</script>\r\nλ  '
        self.run_cli('insert', payload={'id': 'entry-safe', 'original': text, 'translation': text})
        self.assertEqual(self.model()['entries'][0]['original'], text)
        html = self.path.read_text()
        self.assertNotIn('</script><script>alert', html)
        self.assertIn('id="entry-safe" data-entry-id="entry-safe" data-seq="1"', html)
        self.run_cli('delete', 'entry-safe')
        model = self.model()
        self.assertEqual(model['entries'], [])
        self.assertEqual(model['tombstones'][0]['entry']['original'], text)
        self.run_cli('insert', payload={'id': 'entry-safe'}, success=False)

    def test_stale_atomic_batch_and_refusals(self):
        self.run_cli('insert', '--expected-revision', '0', payload={'id': 'a'})
        before = self.path.read_bytes()
        self.run_cli('delete', 'a', '--expected-revision', '0', success=False)
        self.run_cli('apply', payload=[{'op': 'insert', 'entry': {'id': 'b'}},
                                       {'op': 'delete', 'id': 'missing'}], success=False)
        self.run_cli('init', success=False)
        self.assertEqual(self.path.read_bytes(), before)
        self.path.chmod(0o444)
        self.run_cli('update', 'a', payload={'narrative': 'changed'}, success=False)
        self.assertEqual(self.path.read_bytes(), before)

    def test_concurrent_revision_and_batch_metadata(self):
        payload = Path(self.tmp.name) / 'batch.json'
        payload.write_text(json.dumps([{'op': 'meta', 'patch': {'coverage': 'Exact copies', 'gaps': 'Unknown UTC'}},
                                       {'op': 'insert', 'entry': {'id': 'first'}},
                                       {'op': 'insert', 'entry': {'id': 'second'}}]))
        self.run_cli('apply', '--payload', str(payload))
        self.assertEqual(self.model()['revision'], 1)
        self.assertIn('Exact copies', self.path.read_text())
        env = os.environ.copy()
        env.pop('USER_PROVIDED_PASSWORD', None)
        command = [sys.executable, str(CLI), 'delete', str(self.path), 'first', '--expected-revision', '1']
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
                     for _ in range(2)]
        for process in processes:
            process.communicate(timeout=10)
        self.assertEqual(sorted(process.returncode for process in processes), [0, 1])
        self.assertEqual(self.model()['revision'], 2)
        self.assertEqual(len(self.model()['tombstones']), 1)


if __name__ == '__main__':
    unittest.main()
