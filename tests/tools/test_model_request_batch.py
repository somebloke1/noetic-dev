from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest


CLI = Path(__file__).resolve().parents[2] / 'scripts/tools/model_request_batch.py'


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.input = self.root / 'requests.json'
        self.output = self.root / 'results'
        self.seen = []
        self.active = 0
        self.maximum = 0
        self.lock = threading.Lock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                raw = self.rfile.read(int(self.headers['Content-Length']))
                payload = json.loads(raw)
                with owner.lock:
                    owner.seen.append(payload)
                    owner.active += 1
                    owner.maximum = max(owner.maximum, owner.active)
                time.sleep(0.1)
                text = payload['messages'][0]['content']
                if text == 'HTTP error':
                    body = b'local fixture error\r\n'
                    status = 503
                elif text == 'invalid JSON response':
                    body = b'not-json'
                    status = 200
                elif text == 'truncated HTTP body':
                    body = b'partial{"'
                    status = 200
                else:
                    content = ('</think>\r\n{\"candidate\":\"unsupported\",\"limit\":\"still open\"}'
                               if text != 'non-leading boundary' else 'prefix </think> remains')
                    body = json.dumps({'id': 'fixture-provider-id', 'model': 'fixture-model',
                        'choices': [{'message': {'role': 'assistant', 'content': content},
                                     'finish_reason': 'stop'}],
                        'usage': {'prompt_tokens': 4, 'completion_tokens': 3, 'total_tokens': 7,
                                  'prompt_tokens_details': {'cached_tokens': 0}}}).encode()
                    status = 200
                self.send_response(status)
                if text == 'truncated HTTP body':
                    self.send_header('Content-Length', str(len(body) + 100))
                self.end_headers()
                self.wfile.write(body)
                with owner.lock:
                    owner.active -= 1

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f'http://127.0.0.1:{self.server.server_port}/v1/chat/completions'

    def item(self, identity, content):
        return {'id': identity, 'metadata': {'source': 'owned local fixture, not provider benchmark'},
                'request': {'model': 'fixture-model', 'messages': [{'role': 'user', 'content': content}],
                            'temperature': 0, 'max_tokens': 128, 'stream': False}}

    def run_cli(self, items, success=True, concurrency=2):
        self.input.write_text(json.dumps(items, ensure_ascii=False))
        result = subprocess.run([sys.executable, str(CLI), '--requests', str(self.input),
            '--endpoint', self.endpoint, '--output', str(self.output),
            '--concurrency', str(concurrency), '--timeout', '3'], capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        if not success and not result.stdout:
            self.assertTrue(result.stderr.startswith('error: '), result.stderr)
        return json.loads(result.stdout) if result.stdout else result

    def records(self):
        return [json.loads(path.read_text()) for path in sorted(self.output.glob('*.receipt.json'))]

    def test_parallel_exact_requests_raw_and_annotated_views(self):
        content = '  full::ordinal-00000000123 λ\r\n"quoted" tail  '
        items = [self.item('scope/human::00000000123', content), self.item('scope/human::00000000124', content)]
        summary = self.run_cli(items)
        self.assertEqual(self.maximum, 2)
        self.assertEqual(self.seen, [item['request'] for item in items])
        self.assertEqual(summary['response_count'], 2)
        self.assertEqual(summary['failure_count'], 0)
        records = self.records()
        self.assertEqual([record['request_id'] for record in records], [item['id'] for item in items])
        for record in records:
            raw = Path(record['raw_response_path']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), record['raw_response_sha256'])
            parsed = json.loads(raw)
            self.assertEqual(record['original_content'], parsed['choices'][0]['message']['content'])
            self.assertTrue(record['original_content'].startswith('</think>\r\n'))
            self.assertEqual(record['derived_json']['candidate'], 'unsupported')
            self.assertEqual(record['semantic_status'], 'unassessed candidate')
            self.assertEqual(record['transformations'][0]['removed_prefix'], '</think>\r\n')
            self.assertEqual(record['usage'], parsed['usage'])
            self.assertEqual(record['usage_source'], 'response-reported; not independently verified')
            self.assertEqual(record['provider_response_id'], 'fixture-provider-id')
        self.assertNotIn('original_content', summary)

    def test_partial_failures_preserve_raw_and_do_not_retry(self):
        summary = self.run_cli([self.item('good', 'ok'), self.item('bad', 'HTTP error'),
                                self.item('malformed', 'invalid JSON response'),
                                self.item('truncated', 'truncated HTTP body')], success=False)
        self.assertEqual(len(self.seen), 4)
        self.assertEqual(summary['response_count'], 1)
        self.assertEqual(summary['failure_count'], 3)
        records = self.records()
        self.assertEqual([record['transport_status'] for record in records],
                         ['response', 'http_error', 'invalid_response', 'request_error'])
        self.assertEqual(Path(records[1]['raw_response_path']).read_bytes(), b'local fixture error\r\n')
        self.assertEqual(Path(records[2]['raw_response_path']).read_bytes(), b'not-json')
        self.assertEqual(Path(records[3]['raw_response_path']).read_bytes(), b'partial{"')
        self.assertIsNone(records[1]['usage'])

    def test_only_known_leading_boundary_is_removed(self):
        self.run_cli([self.item('literal', 'non-leading boundary')])
        record = self.records()[0]
        self.assertEqual(record['original_content'], 'prefix </think> remains')
        self.assertEqual(record['derived_content'], record['original_content'])
        self.assertEqual(record['transformations'], [])
        self.assertEqual(record['json_parse'], 'failed')
        self.assertEqual(record['semantic_status'], 'unassessed candidate')

    def test_duplicate_ids_and_existing_output_refuse_before_network(self):
        self.run_cli([self.item('same', 'one'), self.item('same', 'two')], success=False)
        self.assertEqual(self.seen, [])
        self.assertFalse(self.output.exists())
        self.output.mkdir()
        sentinel = self.output / 'original'
        sentinel.write_text('retained evidence')
        self.run_cli([self.item('unique', 'one')], success=False)
        self.assertEqual(self.seen, [])
        self.assertEqual(sentinel.read_text(), 'retained evidence')

    def test_concurrency_refusal_and_input_fidelity(self):
        self.run_cli([self.item('one', 'one')], success=False, concurrency=33)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.seen, [])


    def test_existing_response_view_preserves_source_without_network(self):
        source = self.root / 'existing.response.json'
        raw = json.dumps({'id': 'existing-provider-id', 'model': 'fixture-model',
            'choices': [{'message': {'content': '</think>\n{"wrong":true}'},
                         'finish_reason': 'stop'}]}).encode()
        source.write_bytes(raw)
        result = subprocess.run([sys.executable, str(CLI), '--view-response', str(source),
            '--output', str(self.output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        record = json.loads(Path(summary['receipt_path']).read_text())
        self.assertEqual(source.read_bytes(), raw)
        self.assertEqual(Path(record['raw_response_path']).read_bytes(), raw)
        self.assertEqual(record['source_response_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(record['derived_json'], {'wrong': True})
        self.assertEqual(record['semantic_status'], 'unassessed candidate')
        self.assertFalse(record['network_activity'])
        self.assertIsNone(record['usage'])
        self.assertNotIn('request_elapsed_seconds', record)
        self.assertEqual(self.seen, [])

    def test_invalid_existing_response_retains_raw(self):
        source = self.root / 'partial.response.bin'
        source.write_bytes(b'partial source')
        result = subprocess.run([sys.executable, str(CLI), '--view-response', str(source),
            '--output', str(self.output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        summary = json.loads(result.stdout)
        record = json.loads(Path(summary['receipt_path']).read_text())
        self.assertEqual(record['artifact_status'], 'invalid_response')
        self.assertEqual(Path(record['raw_response_path']).read_bytes(), b'partial source')
        self.assertEqual(self.seen, [])


if __name__ == '__main__':
    unittest.main()
