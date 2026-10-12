"""Verify portable GUI assets and maintenance against a real built wheel."""
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

from scripts import noetic_archive as archive, noetic_release as release

ROOT = Path(__file__).resolve().parents[2]
GUI_ASSETS = (
    "index.html", "app.js", "sessions.js", "style.css", "shell.js",
    "shell-agentics.js", "shell-agentics.css", "shell-library.js", "shell-library.css",
    "fonts/inter-latin.woff2", "fonts/dm-mono-latin.woff2",
    "fonts/dm-mono-medium-latin.woff2", "THIRD_PARTY_NOTICES.txt",
)


def clean_environment():
    return {key: value for key, value in os.environ.items()
            if not key.startswith(("PYTHON", "PIP_", "NOETIC_")) and key != "USER_PROVIDED_PASSWORD"}


def omit_wheel_asset(data, omitted):
    with zipfile.ZipFile(io.BytesIO(data)) as wheel:
        files = {name: wheel.read(name) for name in wheel.namelist() if name != omitted}
    record_name = next(name for name in files if name.endswith(".dist-info/RECORD"))
    files.pop(record_name)
    record = io.StringIO(newline="")
    writer = csv.writer(record)
    for name, content in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip("=")
        writer.writerow((name, "sha256=" + digest, len(content)))
    writer.writerow((record_name, "", ""))
    files[record_name] = record.getvalue().encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as wheel:
        for name, content in files.items():
            wheel.writestr(name, content)
    return output.getvalue()


class RecastReleaseAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="noetic-recast-release-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.source = cls.root / "source"
        cls.source.mkdir()
        shutil.copytree(ROOT / "scripts", cls.source / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("pyproject.toml", "LICENSE.md"):
            shutil.copyfile(ROOT / name, cls.source / name)
        subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-build-isolation", "--no-deps",
                        "--no-index", "--wheel-dir", str(cls.root), str(cls.source)],
                       env=clean_environment(), check=True, capture_output=True, timeout=60)
        cls.wheel = next(cls.root.glob("*.whl"))
        cls.wheel_data = cls.wheel.read_bytes()

    def test_built_wheel_preserves_gui_notices_and_all_backend_modules(self):
        with zipfile.ZipFile(self.wheel) as wheel:
            paths = ["scripts/web/" + name for name in GUI_ASSETS]
            paths.extend(str(path.relative_to(self.source)) for path in (self.source / "scripts").glob("*.py"))
            for name in paths:
                with self.subTest(asset=name):
                    self.assertIn(name, wheel.namelist())
                    self.assertEqual(wheel.read(name), (self.source / name).read_bytes())
            for name in GUI_ASSETS:
                if name.endswith(".woff2"):
                    self.assertTrue(wheel.read("scripts/web/" + name).startswith(b"wOF2"))
            notice = wheel.read("scripts/web/THIRD_PARTY_NOTICES.txt").decode()
            self.assertIn("SIL OPEN FONT LICENSE Version 1.1", notice)
            self.assertIn("The Inter Project Authors", notice)
            self.assertIn("DM Mono", notice)

    def test_valid_record_wheel_missing_new_mandatory_assets_is_rejected(self):
        assets = ["scripts/web/" + name for name in GUI_ASSETS if name not in
                  ("index.html", "app.js", "sessions.js", "style.css")]
        assets.extend(("scripts/noetic_purpose_binding.py", "scripts/noetic_opermem.py",
                       "scripts/noetic_opermem_acting.py", "scripts/noetic_act_observation.py"))
        for name in assets:
            with self.subTest(asset=name):
                with self.assertRaisesRegex(ValueError, "Wheel missing runtime asset: " + name):
                    release.wheel_info(omit_wheel_asset(self.wheel_data, name), self.wheel.name)

    def test_private_release_bootstrap_installs_and_serves_from_wheel(self):
        core = ROOT / ".runtime/components/telos-core.mjs"
        bundle = self.root / "private-release.zip"
        release.build_release(bundle, wheel=self.wheel, telos_module=core,
            telos_manifest=core.with_suffix(".manifest.json"), license_file=ROOT / "LICENSE.md",
            notices=ROOT / "docs/THIRD_PARTY_NOTICES.txt", docs=[ROOT / "docs/release-and-archives.md"])
        files, manifest = archive.read_bundle(bundle, "noetic-private-release")
        self.assertEqual(files[manifest["wheel"]], self.wheel_data)
        for name in release.BOOTSTRAP:
            self.assertEqual(files[name], (self.source / name).read_bytes())
        cwd = self.root / "unrelated-cwd"
        cwd.mkdir()
        home = self.root / "private-install"
        env = clean_environment()
        bootstrap = ("import runpy,sys; assert sys.flags.isolated and sys.flags.no_site; "
                     "sys.path.insert(0,sys.argv.pop(1)); "
                     "runpy.run_module('scripts.noetic_release',run_name='__main__')")
        installed = subprocess.run([sys.executable, "-I", "-S", "-c", bootstrap, str(bundle),
                                    "install", str(bundle), "--home", str(home)], cwd=cwd, env=env,
                                   capture_output=True, text=True, timeout=60)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        for command in ([], ["opermem"], ["harness"], ["archive"], ["purposes"]):
            result = subprocess.run([str(home / "bin/noetic"), *command, "--help"],
                                    cwd=cwd, env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
        current = (home / "current").resolve()
        probe = '''
import hashlib,json,sys,threading
from pathlib import Path
from urllib.request import urlopen
from scripts import noetic_web, noetic_opermem, noetic_opermem_acting, noetic_act_observation
from scripts import noetic_purpose_binding
assert noetic_web.WEB_DIR.is_relative_to(Path(sys.prefix))
assert not any("source" in p for p in sys.path)
server = noetic_web.create_server(Path(sys.argv[1]) / "runs", port=0, access_token="a" * 64,
                                  namespace_path=Path(sys.argv[1]) / "ordinals.sqlite3")
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
results = {}
try:
    for route, (name, _) in noetic_web.STATIC_ASSETS.items():
        with urlopen(f"http://127.0.0.1:{server.server_port}{route}", timeout=5) as response:
            results[name] = [hashlib.sha256(response.read()).hexdigest(), response.headers.get_content_type()]
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
print(json.dumps(results, sort_keys=True))
'''
        served = subprocess.run([str(current / "venv/bin/python"), "-I", "-c", probe,
                                 str(home / "state")], cwd=cwd, env=env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(served.returncode, 0, served.stderr)
        observed = json.loads(served.stdout)
        for name in GUI_ASSETS:
            if name == "THIRD_PARTY_NOTICES.txt":
                continue
            kind = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".woff2": "font/woff2"}[Path(name).suffix]
            self.assertEqual(observed[name], [hashlib.sha256((self.source / "scripts/web" / name).read_bytes()).hexdigest(), kind])


if __name__ == "__main__":
    unittest.main()
