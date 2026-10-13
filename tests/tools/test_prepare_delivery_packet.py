import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[2] / 'scripts/tools/prepare_delivery_packet.py'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DeliveryPacketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.templates = self.base / 'F007-delivery'
        self.templates.mkdir()
        self.old = self.make_unit('F007', '0.3.0-current')
        self.candidate = self.make_unit('F010', '0.3.0-candidate')
        self.output = self.base / 'F010-delivery'
        self.status = self.base / 'status.json'
        evidence = self.templates / 'deployed-verification.json'
        evidence.write_text(json.dumps({'release': 'releases/0.3.0-current',
                                       'archive_sha256': self.old['archive_sha256']}))
        self.status.write_text(json.dumps({'installed_release': '0.3.0-current',
            'current_source_base': str(self.base / 'F007/source-final'),
            'current_frozen_manifest': str(self.base / 'F007/frozen-source-sha256.json'),
            'last_deployment_evidence': str(evidence)}))
        self.deploy = (
            "from pathlib import Path\n"
            "OUT=Path(__file__).resolve().parent\nBASE=OUT.parent\nCANDIDATE=BASE/'F007'\n"
            "previous='unused fixture'\nassert previous=='releases/0.3.0-old'\n"
            "prior_build=json.loads((BASE/'F006/payload-verification.json').read_text())\n"
            "assert sha(prior_archive)=='" + '1' * 64 + "'\n"
            "protected='literal λ with spaces'\nraise RuntimeError('TEMPLATE MUST NOT EXECUTE')\n")
        self.smoke = ("from pathlib import Path\nBASE = Path(__file__).resolve().parent.parent / 'F007'\n"
                      "protected='unchanged smoke'\nraise RuntimeError('MUST NOT EXECUTE')\n")
        self.maintenance = b"raise RuntimeError('MUST NOT EXECUTE')\r\n# untouched bytes\r\n"
        (self.templates / 'deploy.py').write_bytes(self.deploy.encode())
        (self.templates / 'final-smoke.py').write_bytes(self.smoke.encode())
        (self.templates / 'session-maintenance.py').write_bytes(self.maintenance)

    def make_unit(self, name, release):
        unit = self.base / name
        (unit / 'source-final/scripts').mkdir(parents=True)
        source = unit / 'source-final/scripts/example.py'
        source.write_text('raise RuntimeError("SOURCE MUST NOT EXECUTE")\n')
        manifest = unit / 'frozen-source-sha256.json'
        manifest.write_text(json.dumps({'scripts/example.py': digest(source)}))
        archive = unit / 'archive.zip'
        archive.write_bytes(('inert archive ' + name).encode())
        wheel = unit / 'package.whl'
        wheel.write_bytes(('inert wheel ' + name).encode())
        payload = {'release': release, 'archive': str(archive), 'archive_sha256': digest(archive),
                   'wheel': str(wheel), 'wheel_sha256': digest(wheel),
                   'source_manifest': str(manifest), 'source_manifest_sha256': digest(manifest),
                   'source_files': 1, 'only_accepted_overlays': True}
        (unit / 'payload-verification.json').write_text(json.dumps(payload))
        return payload

    def run_cli(self, success=True):
        result = subprocess.run([sys.executable, str(CLI), '--status', str(self.status),
            '--candidate', str(self.base / 'F010'), '--templates', str(self.templates),
            '--output', str(self.output)], capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        if not success:
            self.assertTrue(result.stderr.startswith('error: '), result.stderr)
        return json.loads(result.stdout) if success else result

    def input_hashes(self):
        return {str(p.relative_to(self.base)): digest(p) for p in self.base.rglob('*')
                if p.is_file() and self.output not in p.parents}

    def test_exact_five_substitutions_and_no_execution(self):
        before = self.input_hashes()
        summary = self.run_cli()
        receipt = json.loads(Path(summary['receipt']).read_text())
        expected = self.deploy.replace("CANDIDATE=BASE/'F007'", "CANDIDATE=BASE/'F010'")
        expected = expected.replace("assert previous=='releases/0.3.0-old'",
                                    "assert previous=='releases/0.3.0-current'")
        expected = expected.replace("BASE/'F006/payload-verification.json'",
                                    "BASE/'F007/payload-verification.json'")
        expected = expected.replace('1' * 64, self.old['archive_sha256'])
        self.assertEqual((self.output / 'deploy.py').read_bytes(), expected.encode())
        self.assertEqual((self.output / 'final-smoke.py').read_bytes(),
                         self.smoke.replace("/ 'F007'", "/ 'F010'").encode())
        self.assertEqual((self.output / 'session-maintenance.py').read_bytes(), self.maintenance)
        self.assertEqual(before, self.input_hashes())
        self.assertEqual(receipt['state'], 'PREPARED ONLY')
        self.assertEqual(receipt['substitutions'], 5)
        self.assertEqual(receipt['source_acceptance'], 'external; not inferred')
        self.assertEqual(summary['state'], receipt['state'])
        self.assertEqual(summary['substitutions'], receipt['substitutions'])
        self.assertNotIn('input_sha256', summary)
        self.assertEqual(set(p.name for p in self.output.iterdir()),
                         {'deploy.py', 'final-smoke.py', 'session-maintenance.py', 'preparation.json'})

    def test_existing_output_is_preserved(self):
        self.output.mkdir()
        sentinel = self.output / 'evidence.txt'
        sentinel.write_text('existing evidence')
        self.run_cli(success=False)
        self.assertEqual(sentinel.read_text(), 'existing evidence')
        self.assertEqual([p.name for p in self.output.iterdir()], ['evidence.txt'])

    def test_corrupt_candidate_and_prior_receipts_refuse_before_output(self):
        archive = Path(self.candidate['archive'])
        original = archive.read_bytes()
        archive.write_bytes(b'corrupt')
        self.run_cli(success=False)
        self.assertFalse(self.output.exists())
        archive.write_bytes(original)
        data = json.loads(self.status.read_text())
        data['installed_release'] = '0.3.0-mismatched'
        self.status.write_text(json.dumps(data))
        self.run_cli(success=False)
        self.assertFalse(self.output.exists())

    def test_source_manifest_mismatch_and_template_ambiguity(self):
        source = self.base / 'F010/source-final/scripts/example.py'
        original = source.read_bytes()
        source.write_bytes(b'changed')
        self.run_cli(success=False)
        self.assertFalse(self.output.exists())
        source.write_bytes(original)
        deploy = self.templates / 'deploy.py'
        deploy.write_text(self.deploy + "CANDIDATE=BASE/'F007'\n")
        self.run_cli(success=False)
        self.assertFalse(self.output.exists())
        self.assertEqual(deploy.read_text(), self.deploy + "CANDIDATE=BASE/'F007'\n")

    def test_template_candidate_mismatch_and_parent_refusal(self):
        smoke = self.templates / 'final-smoke.py'
        smoke.write_text(self.smoke.replace("/ 'F007'", "/ 'OTHER'"))
        self.run_cli(success=False)
        self.assertFalse(self.output.exists())
        smoke.write_text(self.smoke)
        self.output = self.base / 'different-parent/F010-delivery'
        self.output.parent.mkdir()
        self.run_cli(success=False)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
