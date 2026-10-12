"""Scoped release assets, isolated from installed packages and source cwd."""
import base64
import csv
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from scripts import noetic_release as release

ROOT = Path(__file__).resolve().parents[2]
SCOPED_ASSETS = ("scripts/noetic_scope.py", "scripts/noetic_efforts.py",
                 "scripts/noetic_disciplines.py", "scripts/noetic_purposes.py",
                 "scripts/noetic_recall.py")


def fixture_wheel(omit=None):
    prefix = "noetic_dev-0.3.0.dist-info/"
    files = {name: (ROOT / name).read_bytes() for name in set(release.REQUIRED_ASSETS)}
    files[prefix + "METADATA"] = b"Metadata-Version: 2.1\nName: noetic-dev\nVersion: 0.3.0\n"
    files[prefix + "WHEEL"] = b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    if omit:
        files.pop(omit)
    record = io.StringIO(newline="")
    writer = csv.writer(record)
    for name, data in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
        writer.writerow((name, "sha256=" + digest, str(len(data))))
    writer.writerow((prefix + "RECORD", "", ""))
    files[prefix + "RECORD"] = record.getvalue().encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as wheel:
        for name, data in files.items():
            wheel.writestr(name, data)
    return output.getvalue()


class ScopedReleaseAssetsTests(unittest.TestCase):
    def test_bootstrap_source_zip_imports_and_quiesces_without_source_or_site_fallback(self):
        with tempfile.TemporaryDirectory(prefix="noetic-bootstrap-") as temporary:
            root = Path(temporary)
            bundle = root / "bootstrap.zip"
            with zipfile.ZipFile(bundle, "w") as archive:
                for name in release.BOOTSTRAP:
                    archive.writestr(name, (ROOT / name).read_bytes())
            env = dict(os.environ)
            for name in ("USER_PROVIDED_PASSWORD", "NOETIC_APP_HOME", "NOETIC_STATE_HOME"):
                env.pop(name, None)
            env["PYTHONPATH"] = str(bundle)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            probe = '''
from pathlib import Path
import sys
from scripts import noetic_harness, noetic_release, noetic_archive, noetic_run
assert sys.flags.no_site
assert not any("site-packages" in p for p in sys.path)
run = noetic_run.create_run({"goal": "Disposable bootstrap maintenance"}, Path.cwd(), Path.cwd() / "runs")
noetic_run.record(run, "run.finished", {"state": "cancelled"})
with noetic_release.quiescent_run(run):
    assert noetic_archive.check_run(run)["state"] == "cancelled"
for name, module in tuple(sys.modules.items()):
    if name == "scripts" or name.startswith("scripts."):
        assert str(module.__file__).startswith(sys.argv[1] + "/"), (name, module.__file__)
print("isolated bootstrap imports and maintenance quiescence PASS")
'''
            result = subprocess.run([sys.executable, "-B", "-S", "-c", probe, str(bundle)],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("maintenance quiescence PASS", result.stdout)

    def test_valid_record_wheel_accepts_all_scoped_assets(self):
        version, bootstrap = release.wheel_info(fixture_wheel(), "noetic_dev-0.3.0-py3-none-any.whl")
        self.assertEqual(version, "0.3.0")
        self.assertEqual(set(bootstrap), set(release.BOOTSTRAP))

    def test_valid_record_wheels_missing_each_scoped_asset_are_rejected(self):
        for asset in SCOPED_ASSETS:
            with self.subTest(asset=asset):
                self.assertIn(asset, release.REQUIRED_ASSETS)
                with self.assertRaisesRegex(ValueError, "Wheel missing runtime asset: " + asset):
                    release.wheel_info(fixture_wheel(asset), "noetic_dev-0.3.0-py3-none-any.whl")


if __name__ == "__main__":
    unittest.main()
