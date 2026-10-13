import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[2] / 'scripts/tools/coordination_event.py'


class CoordinationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.body = '  λ <script> & "quote"\r\nline two\n\t尾  '
        (self.root / 'body.txt').write_bytes(self.body.encode('utf-8'))
        self.ledger = self.root / 'coordination-backfill.jsonl'

    def run_cli(self, *args, success=True):
        result = subprocess.run([sys.executable, str(CLI), *map(str, args)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return json.loads(result.stdout) if success else result

    def prepare(self, name='draft.json', recipients=('agent-a', 'agent-b')):
        path = self.root / name
        args = ['prepare', path, '--sender', '/root/origin', '--body-file', self.root / 'body.txt']
        for recipient in recipients:
            args.extend(['--recipient', recipient])
        self.run_cli(*args, '--evidence-time', 'unknown')
        return path, json.loads(path.read_text())

    def record(self, draft, *args, success=True):
        return self.run_cli('record', self.ledger, '--draft', draft, '--confirmed',
                            *args, success=success)

    def rows(self):
        return [json.loads(line) for line in self.ledger.read_text().splitlines()]

    def test_prepare_is_lossless_and_has_no_delivery_effect(self):
        path, draft = self.prepare(recipients=('scope::agent-001', 'scope::agent-002'))
        self.assertFalse(self.ledger.exists())
        self.assertEqual(draft['body'], self.body)
        self.assertEqual(draft['timestamp'], 'unknown')
        self.assertEqual(draft['evidence_time'], 'unknown')
        self.assertEqual(draft['state'], 'prepared')
        self.assertTrue(draft['prepared_at'].endswith('+00:00'))
        dispatches = self.run_cli('dispatch', path)
        self.assertEqual(dispatches, [{'target': target, 'message': self.body}
                                     for target in draft['recipients']])
        self.run_cli('prepare', path, '--sender', 'x', '--recipient', 'y',
                     '--body-file', self.root / 'body.txt', success=False)
        self.assertEqual(json.loads(path.read_text()), draft)

    def test_confirmed_selection_and_existing_bytes(self):
        legacy = b'{"sender":"legacy","recipient":"old","body":"original","timestamp":"unknown"}\n'
        self.ledger.write_bytes(legacy)
        path, draft = self.prepare()
        self.run_cli('record', self.ledger, '--draft', path, '--all-recipients', success=False)
        self.assertEqual(self.ledger.read_bytes(), legacy)
        receipt = self.record(path, '--recipient', 'agent-b')
        self.assertEqual(receipt['appended'], 1)
        self.assertTrue(self.ledger.read_bytes().startswith(legacy))
        row = self.rows()[-1]
        self.assertEqual((row['sender'], row['recipient'], row['body']),
                         ('/root/origin', 'agent-b', self.body))
        self.assertEqual(row['timestamp'], 'unknown')
        self.assertEqual(row['delivery_evidence'], 'caller-confirmed; native transport receipt not validated')
        self.assertNotEqual(row['recorded_at'], row['timestamp'])
        self.assertEqual(row['local_record_id'], draft['event_id'] + ':1')
        copy = self.run_cli('copy', self.ledger, '--event-id', draft['event_id'])
        self.assertEqual(copy['target'], '/root/ui_three_hour_narrator')
        envelope = json.loads(copy['message'].split('\n', 1)[1])
        self.assertEqual(envelope['body'], self.body)
        self.assertEqual([r['recipient'] for r in envelope['routes']], ['agent-b'])

    def test_idempotence_conflicts_and_repeated_legitimate_messages(self):
        path, draft = self.prepare()
        self.record(path, '--all-recipients')
        before = self.ledger.read_bytes()
        self.assertEqual(self.record(path, '--all-recipients')['appended'], 0)
        self.assertEqual(self.ledger.read_bytes(), before)
        draft['body'] += 'changed'
        path.write_text(json.dumps(draft))
        self.record(path, '--all-recipients', success=False)
        self.assertEqual(self.ledger.read_bytes(), before)
        other, _ = self.prepare('other.json')
        self.assertEqual(self.record(other, '--all-recipients')['appended'], 2)
        self.assertEqual(len(self.rows()), 4)
        self.assertEqual(len({r['local_record_id'] for r in self.rows()}), 4)

    def test_refusals_leave_ledger_unchanged(self):
        path, _ = self.prepare()
        self.record(path, '--recipient', 'unknown-agent', success=False)
        self.assertFalse(self.ledger.exists())
        self.ledger.write_bytes(b'{malformed}\n')
        before = self.ledger.read_bytes()
        self.record(path, '--all-recipients', success=False)
        self.assertEqual(self.ledger.read_bytes(), before)
        self.ledger.write_text('{"body":"legacy"}\n')
        self.ledger.chmod(0o444)
        self.record(path, '--all-recipients', success=False)
        self.assertEqual(self.ledger.read_text(), '{"body":"legacy"}\n')

    def test_concurrent_appends_and_shared_body_copy(self):
        drafts = [self.prepare(f'draft-{i}.json')[0] for i in range(6)]
        processes = [subprocess.Popen([sys.executable, str(CLI), 'record', str(self.ledger),
                                      '--draft', str(path), '--all-recipients', '--confirmed'],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     for path in drafts]
        for process in processes:
            _, error = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, error)
        self.assertEqual(len(self.rows()), 12)
        self.assertEqual(len({r['local_record_id'] for r in self.rows()}), 12)
        event = json.loads(drafts[0].read_text())
        copy = self.run_cli('copy', self.ledger, '--event-id', event['event_id'])
        envelope = json.loads(copy['message'].split('\n', 1)[1])
        self.assertEqual(envelope['body'], self.body)
        self.assertEqual(len(envelope['routes']), 2)
        self.assertEqual(copy['message'].count(json.dumps(self.body, ensure_ascii=False)), 1)


if __name__ == '__main__':
    unittest.main()
