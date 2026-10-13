import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts import noetic_opermem as bridge


class OperationHostCaptureTests(unittest.TestCase):
    def setUp(self):
        root = os.environ.get('NOETIC_CAPTURE_TEST_ROOT')
        if root:
            self.root = Path(root) / self._testMethodName
            self.root.mkdir(parents=True, mode=0o700)
        else:
            tmp = tempfile.TemporaryDirectory()
            self.addCleanup(tmp.cleanup)
            self.root = Path(tmp.name)
        self.store = self.root / 'store'
        self.store.mkdir(mode=0o700)
        self.transcript = self.root / 'transcript'
        self.transcript.mkdir(mode=0o700)

    def host(self, body):
        path = self.root / 'fake-host'
        path.write_text('#!/usr/bin/python3\nimport json,sys\n' + body)
        path.chmod(0o700)
        return path

    def captured(self, host):
        directory = Path(host.capture_dir)
        self.assertNotEqual(directory, self.transcript)
        self.assertEqual(directory.parent, self.transcript.parent)
        self.assertEqual(list(self.transcript.iterdir()), [])
        return directory

    def test_first_eof_keeps_unicode_candidate_and_actual_exit_stderr(self):
        binary = self.host('request=sys.stdin.buffer.readline()\nsys.stderr.buffer.write(b"opermem-operation-host: invalid-request\\n")\nsys.exit(65)\n')
        candidate = 'Candidate — α\nretained without normalization.'
        with self.assertRaises(RuntimeError) as raised:
            with bridge.OperationHost(binary, self.store, self.transcript) as host:
                host.exchange('note-insight', {'body': {'text': candidate}})
        capture = self.captured(host)
        request = json.loads((capture / '0001-request.raw').read_bytes())
        self.assertEqual(request['payload']['body']['text'], candidate)
        self.assertEqual((capture / '0001-response.raw').read_bytes(), b'')
        self.assertEqual((capture / 'stderr.raw').read_bytes(), b'opermem-operation-host: invalid-request\n')
        self.assertEqual(json.loads((capture / 'process.json').read_text())['returncode'], 65)
        self.assertIn('response-eof', str(raised.exception))
        self.assertIn('65', str(raised.exception))
        self.assertIn('invalid-request', str(raised.exception))
        self.assertIn(str(capture), str(raised.exception))

    def test_oversized_response_keeps_first_overshoot_bytes(self):
        binary = self.host('sys.stdin.buffer.readline()\nsys.stdout.buffer.write(b"x" * 524289)\nsys.stdout.buffer.flush()\n')
        with self.assertRaises(RuntimeError) as raised:
            with bridge.OperationHost(binary, self.store, self.transcript) as host:
                host.exchange('health', {})
        capture = self.captured(host)
        self.assertEqual((capture / '0001-response.raw').read_bytes(), b'x' * 524289)
        self.assertIn('response-oversized', str(raised.exception))
        self.assertEqual(json.loads((capture / 'process.json').read_text())['returncode'], 0)

    def test_malformed_response_retains_raw_decoding_failure(self):
        binary = self.host('sys.stdin.buffer.readline()\nsys.stdout.buffer.write(b"{bad JSON}\\n")\nsys.stdout.buffer.flush()\n')
        with self.assertRaises(RuntimeError) as raised:
            with bridge.OperationHost(binary, self.store, self.transcript) as host:
                host.exchange('health', {})
        capture = self.captured(host)
        self.assertEqual((capture / '0001-response.raw').read_bytes(), b'{bad JSON}\n')
        self.assertIn('response-json-invalid', str(raised.exception))
        self.assertEqual(json.loads((capture / 'process.json').read_text())['returncode'], 0)

    def test_success_keeps_existing_response_and_native_directory_empty(self):
        binary = self.host('request=json.loads(sys.stdin.buffer.readline())\nresponse={"request_id":request["request_id"],"correlation_id":request["correlation_id"],"class":"success","kind":"health","payload":{"ok":True}}\nprint(json.dumps(response),flush=True)\n')
        with bridge.OperationHost(binary, self.store, self.transcript) as host:
            result = host.exchange('health', {})
        capture = self.captured(host)
        self.assertEqual(result['payload'], {'ok': True})
        self.assertEqual(json.loads((capture / '0001-response.raw').read_bytes()), result)
        self.assertEqual(json.loads((capture / 'process.json').read_text())['returncode'], 0)

    @unittest.skipUnless(os.environ.get('OPERMEM_OPERATION_HOST'), 'requires selected native host')
    def test_current_native_multiline_input_refusal_keeps_evidence(self):
        binary = Path(os.environ['OPERMEM_OPERATION_HOST'])
        with self.assertRaises(RuntimeError) as raised:
            with bridge.OperationHost(binary, self.store, self.transcript) as host:
                context = host.context(bridge.purpose_for('question', None))
                kind, payload = bridge.contextual_command(context, 'question', None,
                    {'question_kind': 'how', 'text': 'Fresh CAP1 boundary question.'}, 'cap1-new-question')
                question = host.exchange(kind, payload)
                parent = question['payload']['outputs'][0]['id']
                context = host.context(bridge.purpose_for('insight', parent))
                kind, payload = bridge.contextual_command(context, 'insight', parent,
                    {'text': 'Complete candidate — α\nlimits unverified.'}, 'cap1-new-multiline-insight')
                host.exchange(kind, payload)
        capture = Path(host.capture_dir)
        self.assertEqual(json.loads((capture / '0006-request.raw').read_bytes())['payload']['body']['text'],
                         'Complete candidate — α\nlimits unverified.')
        self.assertEqual((capture / '0006-response.raw').read_bytes(), b'')
        self.assertEqual(json.loads((capture / 'process.json').read_text())['returncode'], 65)
        self.assertIn(b'invalid-request', (capture / 'stderr.raw').read_bytes())
        self.assertIn(str(capture), str(raised.exception))


if __name__ == '__main__':
    unittest.main()
