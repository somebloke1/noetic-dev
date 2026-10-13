"""Implementation tests using actual wheels, journals and local private installs; no models."""

from contextlib import closing
import base64
import csv
from email.parser import BytesParser
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import select
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
import zipfile

from scripts import noetic_archive as archive, noetic_release as release
from scripts import noetic_controller as controller, noetic_run as runtime, noetic_telos as telos
from scripts import noetic_harness as harness
from scripts.noetic_storage import open_private, ensure_private_directory

ROOT = Path(__file__).resolve().parents[2]


class ReleaseArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="noetic-release-tests-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.build_root = Path(cls.temporary.name)
        source = cls.build_root / "source"
        source.mkdir(mode=0o700)
        shutil.copytree(ROOT / "scripts", source / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("pyproject.toml", "LICENSE.md"):
            shutil.copyfile(ROOT / name, source / name)
        subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-build-isolation", "--no-deps",
                        "--no-index", "--wheel-dir", str(cls.build_root), str(source)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cls.wheel = next(cls.build_root.glob("*.whl"))
        cls.core = ROOT / ".runtime/components/telos-core.mjs"
        cls.bundle = cls.build_root / "release.zip"
        cls.manifest = release.build_release(cls.bundle, wheel=cls.wheel, telos_module=cls.core,
            telos_manifest=cls.core.with_suffix(".manifest.json"), license_file=ROOT / "LICENSE.md",
            notices=ROOT / "docs/THIRD_PARTY_NOTICES.txt", docs=[ROOT / "docs/release-and-archives.md"])

    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=self.build_root)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def run_fixture(self):
        run = runtime.create_run({"goal": "Retain actual kernel history"}, self.root, self.root / "runs")
        state = controller.start_run(run / "controller.sqlite3", controller.PATTERN_DIR / "cognition.json",
                                     "Retain history", self.root)
        with open_private(run / "task.md", "w") as stream:
            stream.write("Original retained artifact\n")
        return run, state

    def test_archive_real_wal_journals_preserve_ids_and_history(self):
        run, state = self.run_fixture()
        with closing(sqlite3.connect(run / "controller.sqlite3")) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            controller.cancel_run(run / "controller.sqlite3", "Operator stopped work")
            expected = controller.inspect_run(run / "controller.sqlite3")
            runtime.record(run, "run.finished", {"state": "cancelled"})
            with open_private(run / ".operator-access/token", "w") as stream:
                stream.write("DO NOT EXPORT")
            output = self.root / "run.zip"
            archive.export_run(run, output)
        files, _ = archive.read_bundle(output, "noetic-run-archive")
        self.assertNotIn("run/.operator-access/token", files)
        self.assertFalse(any(n.endswith(("-wal", "-shm")) for n in files))
        restored = archive.import_run(output, self.root / "restored")
        new_run = Path(restored["run"])
        self.assertEqual(new_run.name, run.name)
        self.assertEqual(controller.inspect_run(new_run / "controller.sqlite3"), expected)
        self.assertEqual(runtime.read_events(new_run), runtime.read_events(run))
        self.assertEqual((new_run / "task.md").read_bytes(), (run / "task.md").read_bytes())
        for path in (self.root / "restored").rglob("*"):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700 if path.is_dir() else 0o600)
        with self.assertRaises(FileExistsError):
            archive.import_run(output, self.root / "restored")

    def test_harness_options_preserved_for_held_restore_and_unknown_cleanup_rejected(self):
        with patch.object(harness, "invoke_actor", side_effect=AssertionError("No actor may run")) as actor:
            run, state = harness.start("cognition", "Archive frozen execution inputs", self.root,
                self.root / "runs", max_activations=0, model="historical-model",
                telos_db=self.root / "historical-telos.sqlite3", telos_source=self.core)
            options = (run / "options.json").read_bytes()
            for name in (".operator-access/token", ".provider/config.json", "credentials.json"):
                with open_private(run / name, "w") as stream:
                    stream.write("excluded private credential fixture")
            held_events = runtime.read_events(run)
            held = self.root / "held-options.zip"
            archive.export_run(run, held, allow_held=True)
            files, _ = archive.read_bundle(held, "noetic-run-archive")
            self.assertEqual(files["run/options.json"], options)
            self.assertFalse(any("credential" in name or "token" in name or ".provider" in name for name in files))
            restored = Path(archive.import_run(held, self.root / "held-restored")["run"])
            self.assertEqual((restored / "options.json").read_bytes(), options)
            self.assertEqual(harness.inspect(restored), state)
            self.assertEqual(runtime.read_events(restored), held_events)
            self.assertEqual(json.loads(options)["telos_db"], str(self.root / "historical-telos.sqlite3"))

            # Submit deterministic fixture results through the real controller,
            # not an actor or a replacement production runtime.
            for phase in state["pattern"]["phases"]:
                activation = state["current_activation"]
                state = controller.begin_activation(run / "controller.sqlite3", activation, state["version"])
                content = {key: [] if kind == "array" else "Archive test fixture"
                           for key, kind in phase["content_fields"].items()}
                state = controller.submit_result(run / "controller.sqlite3", activation, state["version"],
                    {"outcome": "complete" if phase["id"] == "P4" else "advance", "content": content},
                    f"fixture:{activation}", f"fixture:{activation}")
            harness.drive(run)
            self.assertEqual(state["status"], "completed")
            completed_events = runtime.read_events(run)
            completed = self.root / "completed-options.zip"
            # Controller-only submissions provide no actor ownership evidence.
            # Actual completed-process export/restore is covered by cleanup integration.
            with self.assertRaisesRegex(ValueError, "cleanup unconfirmed"):
                archive.export_run(run, completed)
            self.assertEqual(harness.inspect(run), state)
            self.assertEqual(runtime.read_events(run), completed_events)
            actor.assert_not_called()

    def test_held_running_owned_and_unknown_schema_refusals(self):
        run, state = self.run_fixture()
        output = self.root / "held.zip"
        with self.assertRaisesRegex(ValueError, "allow-held"):
            archive.export_run(run, output)
        with open_private(run / "driver.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, "owned driver"):
                archive.export_run(run, output, allow_held=True)
        archive.export_run(run, output, allow_held=True)
        restored = archive.import_run(output, self.root / "restored")
        self.assertEqual(controller.inspect_run(Path(restored["run"]) / "controller.sqlite3"), state)
        controller.begin_activation(run / "controller.sqlite3", state["current_activation"], state["version"])
        with self.assertRaisesRegex(ValueError, "Running activation"):
            archive.export_run(run, self.root / "running.zip", allow_held=True)
        with closing(sqlite3.connect(run / "controller.sqlite3")) as db:
            state["schema_version"] = 999
            db.execute("UPDATE run SET state=?", (json.dumps(state),))
            db.commit()
        with self.assertRaisesRegex(ValueError, "schema"):
            archive.export_run(run, self.root / "unknown.zip", allow_held=True)

    def test_bundle_checksums_paths_links_and_formats(self):
        run, _ = self.run_fixture()
        (run / "outside").symlink_to(self.root)
        with self.assertRaises(ValueError):
            archive.export_run(run, self.root / "linked.zip", allow_held=True)
        files, manifest = archive.read_bundle(self.bundle, "noetic-private-release")
        for name, data in (("../outside", b"bad"), ("run/task.md", b"changed")):
            bad = self.root / ("traversal.zip" if name.startswith("..") else "corrupt.zip")
            with zipfile.ZipFile(bad, "w") as stream:
                for key, content in files.items():
                    stream.writestr(key, content)
                stream.writestr(name, data)
                stream.writestr(archive.MANIFEST, json.dumps(manifest))
            with self.assertRaises(ValueError):
                archive.read_bundle(bad, "noetic-private-release")
        with self.assertRaises(ValueError):
            archive.read_bundle(self.bundle, "noetic-run-archive")

    def test_actual_install_update_rollback_without_checkout_or_state_overwrite(self):
        home = self.root / "private app"
        env = {**os.environ, "PYTHONPATH": str(self.bundle)}
        subprocess.run([sys.executable, "-m", "scripts.noetic_release", "install", str(self.bundle),
                        "--home", str(home)], env=env, cwd=self.root, check=True, stdout=subprocess.PIPE)
        first = release.status(home)["current"]
        wrapper = home / "bin/noetic"
        result = subprocess.run([str(wrapper), "--help"], cwd=self.root, check=True, capture_output=True, text=True)
        self.assertIn("serve", result.stdout)
        with open_private(home / "state/.operator-access/token", "w") as stream:
            stream.write("private pairing token")
        run = runtime.create_run({"goal": "Held private state"}, self.root, home / "state/runs")
        controller.start_run(run / "controller.sqlite3", controller.PATTERN_DIR / "cognition.json", "Hold", self.root)
        original = (run / "controller.sqlite3").read_bytes()
        extra = self.root / "additional.md"
        extra.write_text("Second private delivery of the same code version")
        second_bundle = self.root / "second.zip"
        release.build_release(second_bundle, wheel=self.wheel, telos_module=self.core,
            telos_manifest=self.core.with_suffix(".manifest.json"), license_file=ROOT / "LICENSE.md",
            notices=ROOT / "docs/THIRD_PARTY_NOTICES.txt", docs=[extra])
        with self.assertRaisesRegex(ValueError, "allow-held"):
            release.install_release(second_bundle, home)
        subprocess.run([sys.executable, "-m", "scripts.noetic_release", "install", str(second_bundle),
                        "--home", str(home), "--allow-held"], env={**env, "PYTHONPATH": str(second_bundle)},
                       cwd=self.root, check=True, stdout=subprocess.PIPE)
        second = release.status(home)["current"]
        self.assertNotEqual(first, second)
        installed = next((home / "releases" / first / "venv/lib").glob("python*/site-packages"))
        for name in ("scripts/patterns/cognition.json", "scripts/noetic_harness.py"):
            path = installed / name
            content = path.read_bytes()
            for missing in (True, False):
                with self.subTest(installed_file=name, missing=missing):
                    if missing:
                        path.unlink()
                    else:
                        path.write_bytes(content + b"\n# changed fixture\n")
                    try:
                        with self.assertRaisesRegex(ValueError, "Installed runtime file"):
                            release.rollback(home, first, allow_held=True)
                        self.assertEqual(release.status(home)["current"], second)
                        self.assertEqual((run / "controller.sqlite3").read_bytes(), original)
                        self.assertEqual((home / "state/.operator-access/token").read_text(), "private pairing token")
                    finally:
                        with open_private(path, "wb") as stream:
                            stream.write(content)
        with patch.object(release.subprocess, "run", return_value=subprocess.CompletedProcess(
                ["node", "--version"], 0, stdout="v18.20.8\n")):
            with self.assertRaisesRegex(ValueError, "Node 24"):
                release.rollback(home, first, allow_held=True)
        self.assertEqual(release.status(home)["current"], second)
        self.assertEqual((run / "controller.sqlite3").read_bytes(), original)
        with open_private(run / "application-driver.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, "owned driver"):
                release.rollback(home, first, allow_held=True)
        release.rollback(home, first, allow_held=True)
        self.assertEqual(release.status(home)["current"], first)
        self.assertTrue((home / "releases" / second).is_dir())
        self.assertEqual((home / "state/.operator-access/token").read_text(), "private pairing token")
        self.assertEqual((run / "controller.sqlite3").read_bytes(), original)
        self.assertEqual(stat.S_IMODE(wrapper.stat().st_mode), 0o700)
        if shutil.which("node") and subprocess.check_output(["node", "--version"], text=True).startswith("v24."):
            result = subprocess.run([str(wrapper), "goal", "create", "Private bundled core", "--db", str(home / "state/telos.sqlite3")],
                                    cwd=self.root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def adopted_launcher_fixture(self):
        cwd = self.root / "legacy config root"
        cwd.mkdir()
        external = self.root / "retained history"
        run = runtime.create_run({"goal": "Retained terminal history"}, cwd, external / "runs")
        runtime.record(run, "run.finished", {"state": "accepted"})
        with open_private(external / "operator-access/token", "w") as stream:
            stream.write("synthetic retained token")
        legacy = self.root / "legacy environment/bin/noetic"
        legacy.parent.mkdir(parents=True)
        legacy.write_text('#!/bin/sh\nprintf "legacy:%s\\n" "$PWD"\n')
        legacy.chmod(0o700)
        home = self.root / "adopted app"
        release.install_release(self.bundle, home, code_only=True, adopt_state=external,
                                legacy_launcher=legacy, legacy_cwd=cwd)
        return home, external, cwd, legacy, run

    def previous_launcher(self, home, binding):
        text = ("#!/bin/sh\n# noetic-private-launcher-v1\nset -eu\numask 077\n"
                f"APP_HOME={shlex.quote(str(home))}\n"
                'RELEASE=$(readlink -f "$APP_HOME/current")\n'
                'export NOETIC_TELOS_SOURCE="${NOETIC_TELOS_SOURCE:-$RELEASE/components/telos-core.mjs}"\n'
                'export NOETIC_APP_HOME="$APP_HOME"\n'
                'export NOETIC_STATE_HOME="$APP_HOME/state"\n'
                'unset PYTHONPATH PYTHONHOME\n'
                'exec "$RELEASE/venv/bin/python" -I -m scripts.noetic "$@"\n')
        if binding:
            text = text.replace('RELEASE=$(readlink -f "$APP_HOME/current")\n',
                f'cd {shlex.quote(binding["legacy_cwd"])}\n'
                f'if [ ! -d {shlex.quote(str(Path(binding["state"]) / "runs"))} ]; then\n'
                '  printf "%s\\n" "Adopted external state/runs is missing; refusing an empty replacement" >&2\n'
                '  exit 2\nfi\n'
                'if [ "$(readlink "$APP_HOME/current")" = legacy ]; then\n'
                f'  exec {shlex.quote(binding["legacy_launcher"])} "$@"\nfi\n'
                'RELEASE=$(readlink -f "$APP_HOME/current")\n')
            text = text.replace('export NOETIC_STATE_HOME="$APP_HOME/state"',
                                f'export NOETIC_STATE_HOME={shlex.quote(binding["state"])}')
        return text

    def additional_bundle(self, name):
        doc = self.root / (name + ".md")
        doc.write_text(name)
        bundle = self.root / (name + ".zip")
        release.build_release(bundle, wheel=self.wheel, telos_module=self.core,
            telos_manifest=self.core.with_suffix(".manifest.json"), license_file=ROOT / "LICENSE.md",
            notices=ROOT / "docs/THIRD_PARTY_NOTICES.txt", docs=[doc])
        return bundle

    def test_adopted_launcher_preserves_caller_and_missing_legacy_history(self):
        home, external, cwd, legacy, historical = self.adopted_launcher_fixture()
        wrapper = home / "bin/noetic"
        before = {str(p.relative_to(external)): p.read_bytes() for p in external.rglob("*") if p.is_file()}
        legacy_bytes = legacy.read_bytes()
        selected = release.status(home)["current"]
        env = {**os.environ, "PYTHONPATH": str(self.root / "unrelated modules"),
               "PYTHONHOME": str(self.root / "absent Python home"),
               "NOETIC_APP_HOME": "wrong-home", "NOETIC_STATE_HOME": "wrong-state",
               "NOETIC_TELOS_SOURCE": "", "NOETIC_LOCAL_GENERATE_MODEL": "retained-custom-model"}

        def installed(directory, *args):
            return subprocess.run([str(wrapper), *map(str, args)], cwd=directory, env=env,
                                  capture_output=True, text=True)

        # Observe the shell boundary, then execute the actual selected interpreter.
        python = home / "releases" / selected / "venv/bin/python"
        original_python = python.with_name("launcher-test-python")
        probe = self.root / "launcher-environment.txt"
        python.rename(original_python)
        try:
            python.write_text('#!/bin/sh\nprintf "%s\\n" "$PWD" "$NOETIC_APP_HOME" '
                '"$NOETIC_STATE_HOME" "$NOETIC_TELOS_SOURCE" "$OPENAI_API_KEY" '
                '"$NOETIC_LOCAL_CONFIG" "${PYTHONPATH-unset}" "${PYTHONHOME-unset}" "$@" > '
                + shlex.quote(str(probe)) + '\nexec ' + shlex.quote(str(original_python)) + ' "$@"\n')
            python.chmod(0o700)
            result = subprocess.run([str(wrapper), "--version"], cwd=self.root,
                env={**env, "OPENAI_API_KEY": "synthetic-provider-binding",
                     "NOETIC_LOCAL_CONFIG": "relative-provider-config.json"},
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(probe.read_text().splitlines(), [str(self.root), str(home), str(external),
                str(home / "releases" / selected / "components/telos-core.mjs"),
                "synthetic-provider-binding", "relative-provider-config.json", "unset", "unset",
                "-I", "-m", "scripts.noetic", "--version"])
        finally:
            python.unlink(missing_ok=True)
            original_python.rename(python)

        for name in ("consumer A", "consumer B"):
            caller = self.root / name
            caller.mkdir()
            local = runtime.create_run({"goal": name}, caller, caller / "relative runs")
            runtime.record(local, "run.finished", {"state": "accepted"})
            with self.subTest(caller=name):
                result = installed(caller, "status", local.relative_to(caller), "--json")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["workspace"], str(caller))
                self.assertEqual(json.loads(result.stdout)["goal"], name)
            with self.subTest(default_workspace=name):
                (caller / "task.md").write_text("Caller task " + name)
                result = installed(caller, "harness", "start", "cognition", "task.md",
                                   "--runs-dir", "held runs", "--max-activations", "0",
                                   "--model", "retained-custom-model")
                self.assertEqual(result.returncode, 2, result.stderr)
                held = next((caller / "held runs").iterdir())
                self.assertEqual(runtime.project(runtime.read_events(held))["workspace"], str(caller))
                self.assertEqual((held / "task.md").read_text(), "Caller task " + name + "\n")
                self.assertEqual(json.loads((held / "options.json").read_text())["model"], "retained-custom-model")
            with self.subTest(bindings=name):
                result = installed(caller, "release", "status")
                self.assertEqual(result.returncode, 0, result.stderr)
                observed = json.loads(result.stdout)
                self.assertEqual(observed["home"], str(home))
                self.assertEqual(observed["state"], str(external))
                self.assertEqual(observed["current"], selected)
                result = installed(caller, "doctor")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["telos_source"],
                                 str(home / "releases" / selected / "components/telos-core.mjs"))
                custom = {**env, "NOETIC_TELOS_SOURCE": str(self.core)}
                result = subprocess.run([str(wrapper), "doctor"], cwd=caller, env=custom,
                                        capture_output=True, text=True)
                self.assertEqual(json.loads(result.stdout)["telos_source"], str(self.core))
        release.rollback(home, "legacy", code_only=True)
        self.assertEqual(installed(self.root, "--version").stdout.strip(), f"legacy:{cwd}")
        release.rollback(home, selected, code_only=True)
        for missing in ("cwd", "state", "both"):
            moved_cwd, moved_state = self.root / "unavailable cwd", self.root / "unavailable state"
            if missing in ("cwd", "both"):
                cwd.rename(moved_cwd)
            if missing in ("state", "both"):
                external.rename(moved_state)
            try:
                for command in (("--help",), ("--version",), ("release", "status")):
                    with self.subTest(missing=missing, command=command):
                        result = installed(self.root, *command)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        if command == ("--version",):
                            self.assertEqual(result.stdout.strip(), "noetic-dev 0.3.0")
                if missing in ("state", "both"):
                    with self.subTest(missing=missing, operation="events"):
                        result = installed(self.root, "events", historical)
                        self.assertEqual(result.returncode, 1, result.stderr)
                        self.assertIn("noetic run failed:", result.stderr)
                    with self.subTest(missing=missing, operation="list"):
                        result = installed(self.root, "list", "--json")
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(json.loads(result.stdout), [])
                    self.assertFalse(external.exists())
                self.assertFalse((home / "state").exists())
                if missing in ("cwd", "both"):
                    self.assertFalse(cwd.exists())
            finally:
                if moved_cwd.exists():
                    moved_cwd.rename(cwd)
                if moved_state.exists():
                    moved_state.rename(external)
        self.assertEqual({str(p.relative_to(external)): p.read_bytes() for p in external.rglob("*") if p.is_file()}, before)
        self.assertEqual(legacy.read_bytes(), legacy_bytes)

    def test_managed_launcher_upgrade_refusal_and_pre_switch_failure(self):
        home, external, cwd, legacy, _ = self.adopted_launcher_fixture()
        wrapper = home / "bin/noetic"
        before = release.status(home)
        prior = self.previous_launcher(home, before["adoption"])
        wrapper.write_text(prior)
        wrapper.chmod(0o700)
        update = self.additional_bundle("upgrade fixture")
        state_bytes = {str(p.relative_to(external)): p.read_bytes() for p in external.rglob("*") if p.is_file()}
        pending_pointer = home / ".current-next"
        pending_pointer.write_text("fixture unfinished pointer")
        with self.assertRaisesRegex(ValueError, "Unfinished pointer operation"):
            release.install_release(update, home, code_only=True)
        self.assertEqual(pending_pointer.read_text(), "fixture unfinished pointer")
        pending_pointer.unlink()
        self.assertEqual(wrapper.read_text(), prior)
        self.assertEqual(stat.S_IMODE(wrapper.stat().st_mode), 0o700)
        self.assertEqual(release.status(home)["current"], before["current"])
        self.assertEqual(release.status(home)["releases"], before["releases"])
        for text in (prior + "# customization\n", prior.replace("launcher-v1", "launcher-v0")):
            wrapper.write_text(text)
            with self.assertRaisesRegex(ValueError, "unmanaged"):
                release.install_release(update, home, code_only=True)
            self.assertEqual(wrapper.read_text(), text)
            self.assertEqual(release.status(home)["current"], before["current"])
        wrapper.write_text(prior)
        release.install_release(update, home, code_only=True)
        modern = wrapper.read_bytes()
        self.assertIn(b"noetic-private-launcher-v2", modern)
        next_bundle = self.additional_bundle("idempotent wrapper fixture")
        wrapper.write_bytes(modern + b"# customization\n")
        with self.assertRaisesRegex(ValueError, "unmanaged"):
            release.install_release(next_bundle, home, code_only=True)
        wrapper.write_bytes(modern)
        release.install_release(next_bundle, home, code_only=True)
        self.assertEqual(wrapper.read_bytes(), modern)
        self.assertEqual({str(p.relative_to(external)): p.read_bytes() for p in external.rglob("*") if p.is_file()}, state_bytes)

    def test_plain_launcher_initial_failure_and_v1_upgrade(self):
        home = self.root / "plain app"
        home.mkdir(mode=0o700)
        pending_pointer = home / ".current-next"
        pending_pointer.write_text("fixture unfinished pointer")
        with self.assertRaisesRegex(ValueError, "Unfinished pointer operation"):
            release.install_release(self.bundle, home)
        self.assertFalse((home / "bin/noetic").exists())
        self.assertIsNone(release.status(home)["current"])
        self.assertEqual(release.status(home)["releases"], [])
        self.assertEqual(pending_pointer.read_text(), "fixture unfinished pointer")
        pending_pointer.unlink()
        release.install_release(self.bundle, home)
        wrapper = home / "bin/noetic"
        wrapper.write_text(self.previous_launcher(home, {}))
        update = self.additional_bundle("plain launcher upgrade")
        release.install_release(update, home)
        self.assertIn(b"noetic-private-launcher-v2", wrapper.read_bytes())
        result = subprocess.run([str(wrapper), "--version"], cwd=self.root,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "noetic-dev 0.3.0")

    def test_standalone_legacy_adoption_update_and_rollback(self):
        external = self.root / "external state"
        cwd = self.root / "legacy config root"
        cwd.mkdir()
        run = runtime.create_run({"goal": "Legacy terminal history"}, cwd, external / "runs")
        state = controller.start_run(run / "controller.sqlite3", controller.PATTERN_DIR / "cognition.json",
                                     "Legacy history", cwd)
        for phase in state["pattern"]["phases"]:
            activation = state["current_activation"]
            state = controller.begin_activation(run / "controller.sqlite3", activation, state["version"])
            content = {key: [] if kind == "array" else "Legacy fixture"
                       for key, kind in phase["content_fields"].items()}
            state = controller.submit_result(run / "controller.sqlite3", activation, state["version"],
                {"outcome": "complete" if phase["id"] == "P4" else "advance", "content": content},
                f"fixture:{activation}", f"fixture:{activation}")
        runtime.record(run, "run.finished", {"state": "completed"})
        (run / "options.json").write_text('{}\n')
        directory = run / "activations/activation-1"
        directory.mkdir(parents=True, mode=0o700)
        (directory / "verify-process.json").write_text('{"state":"completed"}\n')
        for name in ("driver.lock", "application-driver.lock"):
            (run / name).touch()
        # Public launcher and old environment are separate from the new code home.
        legacy = self.root / "uv environment/bin/noetic"
        legacy.parent.mkdir(parents=True)
        legacy.write_text('#!/bin/sh\nprintf "legacy:%s\\n" "$PWD"\n')
        legacy.chmod(0o700)
        public = self.root / "public-noetic"
        public.symlink_to(legacy)
        original_launcher = legacy.read_bytes()
        before = {str(p.relative_to(external)): p.read_bytes() for p in external.rglob("*") if p.is_file()}
        events = runtime.read_events(run)
        cleanup = harness.process_info(run, state)
        self.assertFalse(cleanup["cleanup_confirmed"])
        self.assertTrue(all(p["state"] == "unknown" for p in cleanup["processes"].values()))
        external.chmod(0o775)
        home = self.root / "adopted app"
        env = {k: v for k, v in os.environ.items() if k not in ("NOETIC_APP_HOME", "NOETIC_STATE_HOME")}
        env["PYTHONPATH"] = str(self.bundle)

        def cli(*args, success=True):
            result = subprocess.run([sys.executable, "-B", "-S", "-m", "scripts.noetic_release", *map(str, args)],
                                    cwd=self.root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode == 0, success, result.stderr)
            return result

        adoption = ("install", self.bundle, "--home", home, "--adopt-state", external,
                    "--legacy-launcher", legacy, "--legacy-cwd", cwd)
        cli(*adoption, success=False)
        self.assertFalse(home.exists())
        other = self.root / "other"
        other.mkdir()
        overlap = other / ".." / external.name / "code-home"
        rejected = cli("install", self.bundle, "--home", overlap, "--adopt-state", external,
                       "--legacy-launcher", legacy, "--legacy-cwd", cwd, "--code-only", success=False)
        self.assertIn("must be disjoint", rejected.stderr)
        self.assertFalse((external / "code-home").exists())
        self.assertEqual(before, {str(p.relative_to(external)): p.read_bytes()
                                 for p in external.rglob("*") if p.is_file()})
        blocked_home = self.root / "blocked adoption"
        with (run / "driver.lock").open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            cli("install", self.bundle, "--home", blocked_home, "--adopt-state", external,
                "--legacy-launcher", legacy, "--legacy-cwd", cwd, "--code-only", success=False)
        self.assertEqual(release.status(blocked_home)["state"], str(external))
        self.assertIsNone(release.status(blocked_home)["current"])
        cli("install", self.bundle, "--home", blocked_home, success=False)
        self.assertFalse((blocked_home / "state").exists())
        cli(*adoption, "--code-only")
        first = release.status(home)["current"]
        wrapper = home / "bin/noetic"

        def installed(*args):
            return subprocess.run([str(wrapper), *map(str, args)], cwd=self.root, env=env,
                                  check=True, capture_output=True, text=True).stdout

        observed = json.loads(installed("release", "status"))
        self.assertEqual(observed["state"], str(external))
        self.assertEqual(observed["adoption"]["legacy_cwd"], str(cwd))
        self.assertEqual(observed["last_maintenance"]["message"], "code updated, historical cleanup unconfirmed")
        self.assertIsNone(observed["last_maintenance"]["unknown_ownership_records"])
        self.assertEqual(observed["last_maintenance"]["history_assessment"], "not_performed")
        self.assertFalse((home / "state").exists())
        self.assertEqual(json.loads(installed("list", "--json")), runtime.list_runs(external / "runs"))
        self.assertEqual([json.loads(line) for line in installed("events", run).splitlines()], events)
        self.assertEqual(json.loads(installed("status", run, "--json")), runtime.project(events))
        self.assertEqual(os.readlink(public), str(legacy))
        self.assertEqual(legacy.read_bytes(), original_launcher)
        # Actual installed GUI, both the reported explicit invocation shape and
        # its bound default, with synthetic access material outside retained state.
        for paths in (("--runs-dir", str(external / "runs")), ()):
            server = subprocess.Popen([str(wrapper), "serve", *paths, "--port", "0",
                                       "--token-file", str(self.root / "test-access/token")],
                                      cwd=self.root, env=env, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True)
            try:
                self.assertTrue(select.select([server.stdout], [], [], 10)[0], "GUI did not start")
                line = server.stdout.readline()
                self.assertIn("http://127.0.0.1:", line, "GUI pairing line missing")
                base, token = line.strip().split("http://", 1)[1].split("/#token=")
                request = Request(f"http://{base}/api/runs/{run.name}", headers={"Authorization": f"Bearer {token}"})
                with urlopen(request, timeout=10) as response:
                    detail = json.load(response)
                self.assertEqual(detail["controller"], state)
                self.assertEqual(detail["events"], events)
                self.assertFalse(detail["application"]["cleanup_confirmed"])
            finally:
                server.terminate()
                server.communicate(timeout=10)

        extra = self.root / "adoption-update.md"
        extra.write_text("Another code-only delivery")
        second_bundle = self.root / "adoption-update.zip"
        release.build_release(second_bundle, wheel=self.wheel, telos_module=self.core,
            telos_manifest=self.core.with_suffix(".manifest.json"), license_file=ROOT / "LICENSE.md",
            notices=ROOT / "docs/THIRD_PARTY_NOTICES.txt", docs=[extra])
        cli("install", second_bundle, "--home", home, success=False)
        installed("release", "install", second_bundle, "--code-only")
        second = release.status(home)["current"]
        self.assertNotEqual(first, second)
        cli("rollback", first, "--home", home, success=False)
        installed("release", "rollback", first, "--code-only")
        cli("rollback", "legacy", "--home", home, "--code-only")
        self.assertEqual(installed("--version").strip(), f"legacy:{cwd}")
        cli("rollback", second, "--home", home, "--code-only")
        self.assertEqual(json.loads(installed("list", "--json")), runtime.list_runs(external / "runs"))
        with self.assertRaisesRegex(ValueError, "cleanup unconfirmed"):
            archive.export_run(run, self.root / "still-refused.zip")
        self.assertEqual(controller.inspect_run(run / "controller.sqlite3"), state)
        after_cleanup = harness.process_info(run, state)
        self.assertFalse(after_cleanup["cleanup_confirmed"])
        self.assertEqual({k: v["state"] for k, v in cleanup["processes"].items()},
                         {k: v["state"] for k, v in after_cleanup["processes"].items()})
        self.assertEqual({str(p.relative_to(external)): p.read_bytes() for p in external.rglob("*") if p.is_file()}, before)
        self.assertEqual(stat.S_IMODE(external.stat().st_mode), 0o775)
        self.assertEqual(legacy.read_bytes(), original_launcher)
        self.assertEqual(os.readlink(public), str(legacy))

        # The persisted external binding governs future operations, not an empty home/state.
        moved = self.root / "temporarily unavailable fixture"
        external.rename(moved)
        try:
            cli("rollback", first, "--home", home, "--code-only")
            self.assertEqual(release.status(home)["last_maintenance"]["retained_state"], "absent")
            cli("rollback", second, "--home", home, "--code-only")
            missing = subprocess.run([str(wrapper), "events", str(run)], cwd=self.root, env=env,
                                     capture_output=True, text=True)
            self.assertEqual(missing.returncode, 1)
            self.assertIn("noetic run failed:", missing.stderr)
            self.assertFalse((home / "state").exists())
            self.assertFalse(external.exists())
        finally:
            moved.rename(external)
        with (run / "driver.lock").open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            cli("rollback", first, "--home", home, "--code-only", success=False)
        pending = runtime.create_run({"goal": "Known running activation"}, cwd, external / "runs")
        active = controller.start_run(pending / "controller.sqlite3", controller.PATTERN_DIR / "cognition.json", "Active", cwd)
        controller.begin_activation(pending / "controller.sqlite3", active["current_activation"], active["version"])
        cli("rollback", first, "--home", home, "--code-only")
        controller.cancel_run(pending / "controller.sqlite3", "fixture finished")
        runtime.record(pending, "step.started", {"step": "unfinished", "argv": ["fixture"]})
        cli("rollback", second, "--home", home, "--code-only")
        runtime.record(pending, "step.finished", {"step": "unfinished", "state": "failed", "returncode": 1})
        from scripts import noetic_processes as processes
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
        try:
            ownership = run / "activations/activation-1/actor-ownership.json"
            ownership.parent.mkdir(parents=True, exist_ok=True)
            processes.save(ownership, {"identity": processes.identity(child.pid)})
            cli("rollback", first, "--home", home, "--code-only", success=False)
            self.assertIsNone(child.poll(), "maintenance must not terminate a process")
        finally:
            child.terminate()
            child.wait(timeout=10)
        self.assertEqual(release.status(home)["current"], second)

    def test_external_code_repair_preserves_broken_history_without_product_imports(self):
        home, external, cwd, legacy, run = self.adopted_launcher_fixture()
        first = release.status(home)["current"]
        wrapper = home / "bin/noetic"
        wrapper_bytes = wrapper.read_bytes()
        (external / "provider-config.json").write_text('{"model":"retained-owner-model"}\n')
        # Deliberately invalid SQLite and arbitrary unsupported retained schemas.
        (run / "events.sqlite3").write_bytes(b"corrupt journal\x00")
        with closing(sqlite3.connect(run / "controller.sqlite3")) as db:
            db.execute("CREATE TABLE run (id INTEGER PRIMARY KEY, state TEXT NOT NULL)")
            db.execute("INSERT INTO run VALUES (1, ?)", ('{"schema_version":999,"status":"running"}',))
            db.commit()
        (run / "events.sqlite3-wal").write_bytes(b"retained recovery sidecar")
        (run / "events.sqlite3").chmod(0)
        before = {str(p.relative_to(external)): (p.stat().st_mode, p.read_bytes())
                  for p in external.rglob("*") if p.is_file() and p.name != "events.sqlite3"}
        env = {k: v for k, v in os.environ.items() if k != "USER_PROVIDED_PASSWORD"}
        update = self.additional_bundle("external broken-history repair")
        env["PYTHONPATH"] = str(update)
        # Guard imports in the incoming archive process: semantic modules must
        # not load merely to activate verified repair code.
        guard = ('import sys; '
                 'sys.addaudithook(lambda event, args: '
                 '(_ for _ in ()).throw(RuntimeError("product import forbidden")) '
                 'if event == "import" and args[0] in '
                 '("scripts.noetic_run", "scripts.noetic_controller", "scripts.noetic_harness") else None); '
                 'from scripts.noetic_release import main; sys.exit(main(sys.argv[1:]))')

        def external_command(*args, success=True):
            result = subprocess.run([sys.executable, "-B", "-S", "-c", guard, *map(str, args)],
                                    cwd=self.root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode == 0, success, result.stderr)
            return result

        with self.assertRaises((ValueError, sqlite3.Error, PermissionError)):
            release.install_release(update, home)
        external_command("install", update, "--home", home, "--code-only")
        second = release.status(home)["current"]
        self.assertNotEqual(first, second)
        observed = release.status(home)["last_maintenance"]
        self.assertEqual(observed["history_assessment"], "not_performed")
        self.assertEqual(observed["data_compatibility"], "unknown")
        self.assertEqual(observed["retained_state"], "available")
        self.assertFalse(observed["historical_cleanup_confirmed"])
        self.assertEqual(observed["ownership_records_inspected"], 0)
        self.assertIsNone(observed["unknown_ownership_records"])
        external_command("rollback", first, "--home", home, "--code-only")
        self.assertEqual(release.status(home)["current"], first)
        external_command("rollback", "legacy", "--home", home, "--code-only")
        result = subprocess.run([str(wrapper), "--version"], cwd=self.root, env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"legacy:{cwd}")
        external_command("rollback", second, "--home", home, "--code-only")
        result = subprocess.run([str(wrapper), "--version"], cwd=self.root, env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "noetic-dev 0.3.0")
        self.assertEqual(wrapper.read_bytes(), wrapper_bytes)
        self.assertFalse((home / "state").exists())
        self.assertEqual(before, {str(p.relative_to(external)): (p.stat().st_mode, p.read_bytes())
                                 for p in external.rglob("*") if p.is_file() and p.name != "events.sqlite3"})
        self.assertEqual(stat.S_IMODE((run / "events.sqlite3").stat().st_mode), 0)
        (run / "events.sqlite3").chmod(0o600)
        self.assertEqual((run / "events.sqlite3").read_bytes(), b"corrupt journal\x00")

    def test_code_repair_retains_absent_adopted_store_without_replacement(self):
        home, external, cwd, legacy, _ = self.adopted_launcher_fixture()
        first = release.status(home)["current"]
        wrapper = home / "bin/noetic"
        wrapper_bytes = wrapper.read_bytes()
        moved = self.root / "unavailable retained store"
        external.rename(moved)
        before = {str(p.relative_to(moved)): p.read_bytes() for p in moved.rglob("*") if p.is_file()}
        update = self.additional_bundle("absent-history repair")
        release.install_release(update, home, code_only=True)
        second = release.status(home)["current"]
        release.rollback(home, first, code_only=True)
        release.rollback(home, second, code_only=True)
        self.assertEqual(release.status(home)["last_maintenance"]["retained_state"], "absent")
        with self.assertRaisesRegex(ValueError, "missing"):
            release.rollback(home, first)
        new_home = self.root / "new adoption with absent store"
        release.install_release(self.bundle, new_home, code_only=True, adopt_state=external,
                                legacy_launcher=legacy, legacy_cwd=cwd)
        self.assertEqual(release.status(new_home)["state"], str(external))
        self.assertEqual(release.status(new_home)["last_maintenance"]["retained_state"], "absent")
        # A pre-switch failure also must not create an adopted replacement.
        failed = self.root / "failed absent adoption"
        with patch.object(release, "_switch", side_effect=ValueError("fixture pointer failure")):
            with self.assertRaisesRegex(ValueError, "fixture pointer failure"):
                release.install_release(self.bundle, failed, code_only=True, adopt_state=external,
                                        legacy_launcher=legacy, legacy_cwd=cwd)
        self.assertIsNone(release.status(failed)["current"])
        self.assertFalse((failed / "bin/noetic").exists())
        for selected in (home, new_home, failed):
            self.assertFalse((selected / "state").exists())
        self.assertFalse(external.exists())
        self.assertEqual(wrapper.read_bytes(), wrapper_bytes)
        self.assertEqual(before, {str(p.relative_to(moved)): p.read_bytes() for p in moved.rglob("*") if p.is_file()})

    def test_code_only_plain_history_is_unassessed_even_with_retained_wal(self):
        run = runtime.create_run({"goal": "Plain legacy process"}, self.root, self.root / "runs")
        runtime.record(run, "step.started", {"step": "work", "pid": 123})
        from scripts import noetic_processes as processes
        with patch.object(processes.os, "killpg", side_effect=AssertionError("No identity means no group probe")):
            report = release._check_code_state(self.root / "runs", False)
        self.assertFalse(report["historical_cleanup_confirmed"])
        self.assertIsNone(report["unknown_ownership_records"])
        self.assertEqual(report["history_assessment"], "not_performed")
        self.assertEqual(report["ownership_records_inspected"], 0)
        with closing(sqlite3.connect(run / "events.sqlite3")) as db:
            db.execute("PRAGMA journal_mode=WAL")
            runtime.append_event(db, "run.finished", {"state": "accepted"})
            db.commit()
            before = {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}
            release._check_code_state(self.root / "runs", False)
            self.assertEqual({p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}, before)
        before = {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}
        release._check_code_state(self.root / "runs", False)
        self.assertEqual({p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}, before)

    def test_code_repair_preserves_live_busy_and_unverifiable_process_exclusion(self):
        home, external, _, _, run = self.adopted_launcher_fixture()
        first = release.status(home)["current"]
        update = self.additional_bundle("blocked repair")
        wrapper = home / "bin/noetic"
        before_wrapper = wrapper.read_bytes()
        (run / "events.sqlite3").write_bytes(b"broken history must not bypass process safety")
        lock_path = run / "driver.lock"
        lock_path.touch()
        from scripts import noetic_processes as processes
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                                 start_new_session=True)
        ownership = run / "actor-ownership.json"

        def refused():
            before = {str(p.relative_to(external)): p.read_bytes() for p in external.rglob("*") if p.is_file()}
            with self.assertRaisesRegex(ValueError, "Owned state lock|owned group"):
                release.install_release(update, home, code_only=True)
            with self.assertRaisesRegex(ValueError, "Owned state lock|owned group"):
                release.rollback(home, first, code_only=True)
            self.assertEqual(release.status(home)["current"], first)
            self.assertEqual(release.status(home)["releases"], [first])
            self.assertEqual(wrapper.read_bytes(), before_wrapper)
            self.assertEqual(before, {str(p.relative_to(external)): p.read_bytes()
                                     for p in external.rglob("*") if p.is_file()})

        try:
            processes.save(ownership, {"identity": processes.identity(child.pid)})
            self.assertEqual(processes.inspect(ownership)["state"], "owned")
            refused()
            self.assertIsNone(child.poll(), "maintenance must not terminate a live actor")
        finally:
            child.terminate()
            child.wait(timeout=10)
        ownership.unlink()
        with lock_path.open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            refused()
        ownership.write_text('{"identity":"malformed process record"}')
        refused()
        self.assertFalse((home / "state").exists())

    def test_release_rejects_mismatched_component_and_wheel_record(self):
        files, manifest = archive.read_bundle(self.bundle, "noetic-private-release")
        files["components/telos-core.mjs"] += b"\n// changed\n"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            release.validate_assets(files, manifest)
        with zipfile.ZipFile(self.wheel) as original:
            corrupt = self.root / self.wheel.name
            with zipfile.ZipFile(corrupt, "w") as modified:
                for item in original.infolist():
                    data = original.read(item)
                    modified.writestr(item, data + b"\n" if item.filename == "scripts/noetic.py" else data)
        with self.assertRaisesRegex(ValueError, "RECORD checksum"):
            release.wheel_info(corrupt.read_bytes(), corrupt.name)

    def wheel_with_dependencies(self, requirements=(), extras=()):
        with zipfile.ZipFile(self.wheel) as wheel:
            files = {name: wheel.read(name) for name in wheel.namelist()}
        metadata = next(name for name in files if name.endswith(".dist-info/METADATA"))
        meta = BytesParser().parsebytes(files[metadata])
        for header, values in (("Requires-Dist", requirements), ("Provides-Extra", extras)):
            del meta[header]
            for value in values:
                meta[header] = value
        files[metadata] = meta.as_bytes()
        record = next(name for name in files if name.endswith(".dist-info/RECORD"))
        rows = list(csv.reader(io.StringIO(files[record].decode())))
        digest = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(files[metadata]).digest()).decode().rstrip("=")
        amended = io.StringIO()
        csv.writer(amended).writerows([row[0], digest, str(len(files[metadata]))] if row[0] == metadata else row
                                     for row in rows)
        files[record] = amended.getvalue().encode()
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as wheel:
            for name, content in files.items():
                wheel.writestr(name, content)
        return output.getvalue()

    def test_wheel_accepts_only_dependency_free_core_and_declared_optional_genus_sdk(self):
        with zipfile.ZipFile(self.wheel) as wheel:
            metadata = next(name for name in wheel.namelist() if name.endswith(".dist-info/METADATA"))
            meta = BytesParser().parsebytes(wheel.read(metadata))
        self.assertEqual(meta.get_all("Provides-Extra"), ["genus"])
        self.assertIn(meta.get_all("Requires-Dist"),
                      [['mcp>=1.0; extra == "genus"'], ["mcp >=1.0 ; extra == 'genus'"]])
        self.assertEqual(release.wheel_info(self.wheel.read_bytes(), self.wheel.name)[0], "0.3.0")
        self.assertEqual(release.wheel_info(self.wheel_with_dependencies(), self.wheel.name)[0], "0.3.0")
        for requirement in ('mcp>=1.0; extra == "genus"', "mcp >= 1.0 ; extra=='genus'"):
            with self.subTest(requirement=requirement):
                data = self.wheel_with_dependencies([requirement], ["genus"])
                self.assertEqual(release.wheel_info(data, self.wheel.name)[0], "0.3.0")
        cases = [
            (["mcp>=1.0"], ["genus"]),
            (['mcp>=1.0; extra == "genus"'], []),
            (['mcp>=1.0; extra == "other"'], ["other"]),
            (['mcp>=1.0; extra != "genus"'], ["genus"]),
            (['mcp>=1.0; extra in "genus"'], ["genus"]),
            (['mcp>=1.0; extra == ""'], ["genus"]),
            (['mcp>=1.0; python_version >= "3.10"'], ["genus"]),
            (['mcp>=1.0; extra == "genus" or python_version >= "3.10"'], ["genus"]),
            (['mcp>=1.0; extra == "genus" and python_version >= "3.10"'], ["genus"]),
            (['mcp>=1.0; "genus" == extra'], ["genus"]),
            (['mcp>=1.0; (extra == "genus")'], ["genus"]),
            (['mcp>=1.0; extra == "genus"; python_version >= "3.10"'], ["genus"]),
            (['mcp>=1.0; extra == "genus\''], ["genus"]),
            (['mcp>=2.0; extra == "genus"'], ["genus"]),
            (['other>=1.0; extra == "genus"'], ["genus"]),
            (['mcp[client]>=1.0; extra == "genus"'], ["genus"]),
            (['mcp>=1.0; extra == "genus"', "required>=1.0"], ["genus"]),
        ]
        for requirements, extras in cases:
            with self.subTest(requirements=requirements, extras=extras):
                with self.assertRaisesRegex(ValueError, "dependency-free"):
                    release.wheel_info(self.wheel_with_dependencies(requirements, extras), self.wheel.name)

    def test_optional_genus_sdk_is_not_installed_with_private_release(self):
        with zipfile.ZipFile(self.wheel) as wheel:
            metadata = next(name for name in wheel.namelist() if name.endswith(".dist-info/METADATA"))
            requirements = BytesParser().parsebytes(wheel.read(metadata)).get_all("Requires-Dist")
        home = self.root / "optional-sdk-app"
        release.install_release(self.bundle, home)
        python = home / "current/venv/bin/python"
        result = subprocess.run([str(python), "-I", "-c",
            "import importlib.metadata as m, importlib.util as u, json, sys; "
            "assert m.requires('noetic-dev') == json.loads(sys.argv[1]); "
            "assert m.metadata('noetic-dev').get_all('Provides-Extra') == ['genus']; "
            "assert u.find_spec('mcp') is None; "
            "import scripts.noetic_genus", json.dumps(requirements)], check=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        result = subprocess.run([str(home / "bin/noetic"), "--help"], cwd=self.root,
                                check=True, capture_output=True, text=True)
        self.assertIn("serve", result.stdout)

    def test_wheel_requires_every_runtime_asset_even_with_valid_record(self):
        with zipfile.ZipFile(self.wheel) as wheel:
            original = {name: wheel.read(name) for name in wheel.namelist()}
        record = next(name for name in original if name.endswith(".dist-info/RECORD"))
        rows = list(csv.reader(io.StringIO(original[record].decode())))
        for missing in release.REQUIRED_ASSETS:
            with self.subTest(missing=missing):
                amended = io.StringIO()
                csv.writer(amended).writerows(row for row in rows if row[0] != missing)
                output = io.BytesIO()
                with zipfile.ZipFile(output, "w") as wheel:
                    for name, content in original.items():
                        if name != missing:
                            wheel.writestr(name, amended.getvalue().encode() if name == record else content)
                with self.assertRaisesRegex(ValueError, "Wheel missing runtime asset"):
                    release.wheel_info(output.getvalue(), self.wheel.name)

    def test_node24_and_sqlite_capability_required_before_install_or_build(self):
        home = self.root / "not-installed"
        output = self.root / "not-built.zip"
        old_node = subprocess.CompletedProcess(["node", "--version"], 0, stdout="v18.20.8\n")
        with patch.object(release.subprocess, "run", return_value=old_node):
            with self.assertRaisesRegex(ValueError, "Node 24"):
                release.install_release(self.bundle, home)
            with self.assertRaisesRegex(ValueError, "Node 24"):
                release.build_release(output, wheel=self.wheel, telos_module=self.core,
                    telos_manifest=self.core.with_suffix(".manifest.json"), license_file=ROOT / "LICENSE.md",
                    notices=ROOT / "docs/THIRD_PARTY_NOTICES.txt", docs=[ROOT / "docs/release-and-archives.md"])
        self.assertFalse(home.exists())
        self.assertFalse(output.exists())
        with patch.object(release.subprocess, "run", side_effect=[
                subprocess.CompletedProcess(["node", "--version"], 0, stdout="v24.1.0\n"),
                subprocess.CalledProcessError(1, ["node", "-e", "import node:sqlite"])]):
            with self.assertRaisesRegex(ValueError, "node:sqlite"):
                release.install_release(self.bundle, home)
        self.assertFalse(home.exists())
        release.check_node24()

    def test_plain_run_terminal_requirement_and_archive_schema(self):
        run = runtime.create_run({"goal": "Plain journal"}, self.root, self.root / "runs")
        output = self.root / "plain.zip"
        with self.assertRaisesRegex(ValueError, "terminal"):
            archive.export_run(run, output)
        runtime.record(run, "run.finished", {"state": "awaiting_review"})
        archive.export_run(run, output)
        files, manifest = archive.read_bundle(output, "noetic-run-archive")
        manifest.pop("files")
        manifest["controller_schema"] = 999
        bad = self.root / "unknown.zip"
        archive.write_bundle(bad, files, manifest)
        with self.assertRaisesRegex(ValueError, "schema"):
            archive.import_run(bad, self.root / "restored")
        link = self.root / "zip-link.zip"
        with zipfile.ZipFile(link, "w") as stream:
            entry = zipfile.ZipInfo("run/task.md")
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            stream.writestr(entry, "../../outside")
        with self.assertRaisesRegex(ValueError, "link"):
            archive.read_bundle(link, "noetic-run-archive")

    def test_explicit_full_telos_snapshot(self):
        if not shutil.which("node") or not subprocess.check_output(["node", "--version"], text=True).startswith("v24."):
            self.skipTest("Node 24 required for actual Telos DB fixture")
        run, _ = self.run_fixture()
        db = self.root / "isolated-telos.sqlite3"
        goal = telos.create_goal("Private archive fixture", db, self.core)
        output = self.root / "telos-run.zip"
        manifest = archive.export_run(run, output, allow_held=True, telos_db=db)
        self.assertEqual(manifest["privacy"], "FULL PRIVATE TELOS DATABASE")
        restored = archive.import_run(output, self.root / "restored")
        copied = Path(restored["root"]) / "private-telos/telos.sqlite3"
        with closing(sqlite3.connect(db)) as left, closing(sqlite3.connect(copied)) as right:
            self.assertEqual(left.execute("SELECT * FROM chains").fetchall(), right.execute("SELECT * FROM chains").fetchall())


if __name__ == "__main__":
    unittest.main()
