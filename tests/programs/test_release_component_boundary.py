"""Release metadata inspection must remain independent of application execution."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ReleaseComponentBoundaryTests(unittest.TestCase):
    def test_standalone_import_and_native_metadata_exclude_execution_modules(self):
        code = r"""
import sys
sys.path.insert(0, sys.argv[1])
forbidden = {"scripts.noetic_run", "scripts.noetic_controller", "scripts.noetic_harness",
             "scripts.noetic_opermem", "scripts.noetic_opermem_application"}
def reject(event, args):
    if event == "import" and args[0] in forbidden:
        raise AssertionError("Execution module imported during release inspection: " + args[0])
sys.addaudithook(reject)
from scripts import noetic_release, noetic_opermem_component as component
assert not forbidden.intersection(sys.modules)
assert "scripts/noetic_opermem_component.py" in noetic_release.BOOTSTRAP
raw = bytearray(64)
raw[:6] = b"\x7fELF\x02\x01"
raw[18:20] = b"\x3e\x00"
files = {name: bytes(raw) for name in component.EXECUTABLES}
manifest = component.component_manifest(files, {"fixture": "unchanged private component contract"})
component.validate_component(files, manifest)
try:
    component.validate_component({**files, component.EXECUTABLES[1]: b"changed"}, manifest)
except ValueError:
    pass
else:
    raise AssertionError("Changed executable bytes accepted")
assert not forbidden.intersection(sys.modules)
print("standalone release/native metadata boundary PASS")
"""
        environment = {key: value for key, value in os.environ.items() if key != "USER_PROVIDED_PASSWORD"}
        result = subprocess.run([sys.executable, "-I", "-c", code, str(ROOT)],
                                cwd=ROOT, env=environment, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("boundary PASS", result.stdout)

    def test_application_preserves_component_api(self):
        from scripts import noetic_opermem_application as application
        from scripts import noetic_opermem_component as component
        for name in ("COMPONENT", "EXECUTABLES", "component_manifest", "validate_component",
                     "check_platform", "host_configuration"):
            self.assertIs(getattr(application, name), getattr(component, name))
