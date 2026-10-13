"""Explicit retained-broker coexistence: live recognized brokers, refusal gates, byte preservation."""

from contextlib import redirect_stdout
import fcntl
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import noetic_release as release
from scripts import noetic_processes as processes
from scripts.noetic_storage import open_private

ROOT = Path(__file__).resolve().parents[2]
SESSION_UUID = "4266bdb2-ab8b-4512-8754-9183fec64647"


def broker_cmdline(argv0, runs_root, uuid=SESSION_UUID, fd="4",
                   namespace="/state/runs/ordinals.sqlite3"):
    return "\0".join([argv0, "-m", "scripts.noetic_sessions", "broker",
                      str(runs_root), uuid, fd, namespace, ""]).encode()


class ReleaseBrokerCoexistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="noetic-coexist-tests-")
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
        release.build_release(cls.bundle, wheel=cls.wheel, telos_module=cls.core,
            telos_manifest=cls.core.with_suffix(".manifest.json"), license_file=ROOT / "LICENSE.md",
            notices=ROOT / "docs/THIRD_PARTY_NOTICES.txt", docs=[ROOT / "docs/release-and-archives.md"])

    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=self.build_root)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def additional_bundle(self, name):
        doc = self.root / (name + ".md")
        doc.write_text(name)
        bundle = self.root / (name + ".zip")
        release.build_release(bundle, wheel=self.wheel, telos_module=self.core,
            telos_manifest=self.core.with_suffix(".manifest.json"), license_file=ROOT / "LICENSE.md",
            notices=ROOT / "docs/THIRD_PARTY_NOTICES.txt", docs=[doc])
        return bundle

    def live_broker_fixture(self):
        """Installed release, session directory and a real sleeper holding broker.lock.

        The process's actual cwd and /proc exe are the named release's; only the
        command-line bytes are fixture-provided, because the real broker module
        would open sockets and write product state.
        """
        home = self.root / "app"
        release.install_release(self.bundle, home, code_only=True)
        first = release.status(home)["current"]
        first_bytes = self.release_bytes(home / "releases" / first)
        release_root = home / "releases" / first
        python = release_root / "venv/bin/python"
        site = next((release_root / "venv/lib").glob("python*/site-packages"))
        state = home / "state"
        runs = state / "runs"
        session = runs / "developer-sessions" / SESSION_UUID
        session.mkdir(parents=True)
        alias = str(home / "current" / "venv" / "bin" / "python")
        code = ("import fcntl, sys, time\n"
                f"stream = open({str(session / 'broker.lock')!r}, 'a')\n"
                "fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
                "print('held', flush=True)\n"
                "time.sleep(120)\n")
        child = subprocess.Popen([alias, "-c", code], cwd=str(site), executable=str(python),
                                 stdout=subprocess.PIPE, text=True, start_new_session=True)
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        self.assertEqual(child.stdout.readline().strip(), "held")
        ownership = session / "broker-ownership.json"
        processes.save(ownership, {"identity": processes.identity(child.pid)})
        return {"home": home, "first": first, "first_bytes": first_bytes, "state": state, "runs": runs,
                "session": session, "ownership": ownership, "alias": alias,
                "python": str(python), "site": str(site), "child": child}

    def release_bytes(self, root):
        return {str(p.relative_to(root)): p.read_bytes()
                for p in root.rglob("*") if p.is_file()}

    def test_coexistence_requires_code_only_and_rejects_unusable_named_releases(self):
        fixture = self.live_broker_fixture()
        home, first = fixture["home"], fixture["first"]
        update = self.additional_bundle("coexistence gating")
        with self.assertRaisesRegex(ValueError, "requires --code-only"):
            release.install_release(update, home, coexist=first)
        with self.assertRaisesRegex(ValueError, "requires --code-only"):
            release.rollback(home, first, coexist=first)
        with self.assertRaisesRegex(ValueError, "retained broker release"):
            release.install_release(update, home, code_only=True, coexist="legacy")
        with self.assertRaisesRegex(ValueError, "retained broker release"):
            release.install_release(update, home, code_only=True, coexist="not-a-release")
        with self.assertRaisesRegex(ValueError, "missing"):
            release.install_release(update, home, code_only=True, coexist="9.9.9-0000000000000000")
        # Ordinary code-only behavior is unchanged: the busy broker.lock is the
        # concrete first guard (the owned-group gate is coexist-only).
        with self.assertRaisesRegex(ValueError, "Owned state lock|Known live or unverifiable"):
            release.install_release(update, home, code_only=True)
        self.assertEqual(release.status(home)["current"], first)
        self.assertIsNone(fixture["child"].poll())

    def test_tampered_named_release_is_refused(self):
        fixture = self.live_broker_fixture()
        home, first = fixture["home"], fixture["first"]
        update = self.additional_bundle("tampered retained release")
        # The installed module lives in site-packages, not the extracted root;
        # tampering it must trip the existing installed-payload check.
        target = Path(fixture["site"]) / "scripts/noetic_sessions.py"
        target.write_bytes(target.read_bytes() + b"\n# tampered\n")
        with self.assertRaisesRegex(ValueError, "Installed runtime file changed"):
            release.install_release(update, home, code_only=True, coexist=first)
        self.assertEqual(release.status(home)["current"], first)

    def test_recognized_broker_exemption_preserves_state_and_old_release(self):
        fixture = self.live_broker_fixture()
        home, first, state = fixture["home"], fixture["first"], fixture["state"]
        runs = fixture["runs"]
        cmdline = broker_cmdline(fixture["alias"], runs)
        before = self.release_bytes(state)
        update = self.additional_bundle("coexistence delivery")
        with patch.object(release, "_proc_cmdline", return_value=cmdline):
            result = release.install_release(update, home, code_only=True, coexist=first)
        second = release.status(home)["current"]
        self.assertNotEqual(first, second)
        observed = release.status(home)["last_maintenance"]
        self.assertEqual(observed["mode"], "code-only-coexistence")
        self.assertEqual(observed["message"],
                         "code updated, recognized live brokers preserved, historical cleanup unconfirmed")
        self.assertEqual(observed["history_assessment"], "not_performed")
        self.assertFalse(observed["historical_cleanup_confirmed"])
        self.assertEqual(observed["coexistence"]["broker_release"], first)
        self.assertEqual([b["session"] for b in observed["coexistence"]["recognized_brokers"]], [SESSION_UUID])
        # Old broker release root retained; no copying between installed homes.
        self.assertTrue((home / "releases" / first / "venv/bin/python").is_file())
        self.assertEqual(self.release_bytes(home / "releases" / first), fixture["first_bytes"])
        self.assertEqual(self.release_bytes(state), before)
        self.assertIsNone(fixture["child"].poll(), "recognized broker must not be signalled")
        # Rollback supports naming the old broker release even while current is new,
        # and switching back preserves the same exemptions.
        with patch.object(release, "_proc_cmdline", return_value=cmdline):
            release.rollback(home, first, code_only=True, coexist=first)
            self.assertEqual(release.status(home)["current"], first)
            release.rollback(home, second, code_only=True, coexist=first)
        self.assertEqual(release.status(home)["current"], second)
        self.assertEqual(self.release_bytes(state), before)
        self.assertIsNone(fixture["child"].poll())

    def test_cli_accepts_explicit_option(self):
        fixture = self.live_broker_fixture()
        home, first, runs = fixture["home"], fixture["first"], fixture["runs"]
        update = self.additional_bundle("cli coexistence")
        cmdline = broker_cmdline(fixture["alias"], runs)
        with patch.object(release, "_proc_cmdline", return_value=cmdline):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(release.main(["install", str(update), "--home", str(home),
                                               "--code-only", "--coexist-brokers-from", first]), 0)
        self.assertEqual(json.loads(output.getvalue())["last_maintenance"]["coexistence"]["broker_release"], first)

    def test_wrong_exe_cwd_argv0_and_session_are_refused(self):
        fixture = self.live_broker_fixture()
        home, first, runs = fixture["home"], fixture["first"], fixture["runs"]
        update = self.additional_bundle("recognition gates")
        good = broker_cmdline(fixture["alias"], runs)

        def attempt(cmdline=None, link=None, expect=None, uuid=SESSION_UUID):
            session = fixture["runs"] / "developer-sessions" / uuid
            session.mkdir(parents=True, exist_ok=True)
            processes.save(session / "broker-ownership.json",
                           {"identity": processes.identity(fixture["child"].pid)})
            original_link = release._proc_link
            def actual_link(pid, name):
                if link and name in link:
                    return link[name]
                return original_link(pid, name)
            with patch.object(release, "_proc_cmdline", return_value=cmdline if cmdline else good), \
                 patch.object(release, "_proc_link", side_effect=actual_link):
                with self.assertRaisesRegex(ValueError, expect):
                    release.install_release(update, home, code_only=True, coexist=first)
            self.assertIsNone(fixture["child"].poll())
            shutil.rmtree(session)

        # Real /proc exe is the named release; the fixture child's real cwd is right,
        # so each failure below is caused only by the injected mismatch.
        attempt(link={"exe": "/nonexistent/venv/bin/python"}, expect="executable does not match")
        attempt(link={"cwd": "/nonexistent/site-packages"}, expect="cwd does not match")
        attempt(cmdline=broker_cmdline(fixture["alias"], self.root / "other" / "runs"),
                expect="does not match this session")
        attempt(cmdline=b"/usr/bin/env\0" + good.split(b"\0", 1)[1], expect="argv0")
        attempt(cmdline=good + b"extra\0", expect="namespace")
        attempt(cmdline=broker_cmdline(fixture["alias"], runs, fd="x"), expect="namespace")
        attempt(cmdline=broker_cmdline(fixture["alias"], runs, namespace="relative/namespace"),
                expect="namespace")
        attempt(cmdline=broker_cmdline(fixture["alias"], runs, uuid="00000000-aaaa-4bbb-8ccc-000000000000"),
                expect="does not match this session")
        attempt(uuid="not-a-uuid", expect="Known live or unverifiable owned group")

    def test_wrong_recorded_identity_and_boot_ticks_are_refused(self):
        fixture = self.live_broker_fixture()
        home, first, runs = fixture["home"], fixture["first"], fixture["runs"]
        update = self.additional_bundle("identity gates")
        identity = processes.identity(fixture["child"].pid)
        cmdline = broker_cmdline(fixture["alias"], runs)
        tampered = dict(identity, start_ticks=identity["start_ticks"] + 7)
        processes.save(fixture["ownership"], {"identity": tampered})
        with patch.object(release, "_proc_cmdline", return_value=cmdline):
            # The tampered identity is not recognized, so its live session lock is
            # no longer exempt and maintenance refuses on that concrete blocker.
            with self.assertRaisesRegex(ValueError, "Owned state lock|Known live or unverifiable"):
                release.install_release(update, home, code_only=True, coexist=first)
        self.assertEqual(release.status(home)["current"], first)
        self.assertIsNone(fixture["child"].poll())

    def test_nonbroker_and_other_busy_locks_still_refuse(self):
        fixture = self.live_broker_fixture()
        home, first, runs, state = fixture["home"], fixture["first"], fixture["runs"], fixture["state"]
        update = self.additional_bundle("nonbroker gates")
        # A live nonbroker ownership record is never exempt.
        actor_record = runs / "other-run" / "actor-ownership.json"
        actor_record.parent.mkdir(parents=True)
        processes.save(actor_record, {"identity": processes.identity(fixture["child"].pid)})
        cmdline = broker_cmdline(fixture["alias"], runs)
        with patch.object(release, "_proc_cmdline", return_value=cmdline):
            with self.assertRaisesRegex(ValueError, "Known live or unverifiable owned group"):
                release.install_release(update, home, code_only=True, coexist=first)
        actor_record.unlink()
        # Any other busy lock, even in a session directory, still refuses.
        session = runs / "developer-sessions" / ("00000000-0000-4000-8000-00000000000" + "0")
        session.mkdir(parents=True)
        with (session / "other.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(release, "_proc_cmdline", return_value=cmdline):
                with self.assertRaisesRegex(ValueError, "Owned state lock"):
                    release.install_release(update, home, code_only=True, coexist=first)
        self.assertEqual(release.status(home)["current"], first)
        self.assertIsNone(fixture["child"].poll())

    def test_recheck_before_switch_refuses_changed_identity(self):
        fixture = self.live_broker_fixture()
        home, first, runs = fixture["home"], fixture["first"], fixture["runs"]
        update = self.additional_bundle("recheck gate")
        good = broker_cmdline(fixture["alias"], runs)
        bad = broker_cmdline(fixture["alias"], runs, fd="x")
        calls = {"n": 0}

        def flaky(pid):
            calls["n"] += 1
            # Calls 1-2 (maintenance plan + pre-check) succeed; the pre-switch
            # recheck observes a changed identity and must refuse.
            return good if calls["n"] < 3 else bad

        launcher = home / "bin/noetic"
        original_launcher = launcher.read_bytes() if launcher.exists() or launcher.is_symlink() else None
        original_mode = stat.S_IMODE(launcher.stat().st_mode) if original_launcher is not None else None
        with patch.object(release, "_proc_cmdline", side_effect=flaky):
            with self.assertRaisesRegex(ValueError, "namespace"):
                release.install_release(update, home, code_only=True, coexist=first)
        self.assertEqual(release.status(home)["current"], first)
        if original_launcher is None:
            self.assertFalse(launcher.exists(), "initial install must clean its launcher on refusal")
        else:
            self.assertEqual(launcher.read_bytes(), original_launcher)
            self.assertEqual(stat.S_IMODE(launcher.stat().st_mode), original_mode)
        self.assertIsNone(fixture["child"].poll())

    def test_broker_identity_change_between_checks_refuses_before_switch(self):
        """A different otherwise-valid broker identity between the initial plan
        check and the pre-switch recheck must refuse, keeping the old pointer,
        launcher and release untouched."""
        fixture = self.live_broker_fixture()
        home, first, runs = fixture["home"], fixture["first"], fixture["runs"]
        update = self.additional_bundle("identity snapshot gate")
        good = broker_cmdline(fixture["alias"], runs)
        other = broker_cmdline(fixture["alias"], runs, namespace="/state/runs/other.sqlite3")
        calls = {"n": 0}

        def shifting(pid):
            calls["n"] += 1
            # Calls 1-2 (maintenance plan + pre-stage check) see the original
            # identity; the pre-switch recheck sees another valid one.
            return good if calls["n"] < 3 else other

        launcher = home / "bin/noetic"
        original_launcher = launcher.read_bytes()
        original_mode = stat.S_IMODE(launcher.stat().st_mode)
        with patch.object(release, "_proc_cmdline", side_effect=shifting):
            with self.assertRaisesRegex(ValueError, "changed during maintenance"):
                release.install_release(update, home, code_only=True, coexist=first)
        self.assertEqual(release.status(home)["current"], first)
        # The fixture's own initial install wrote the launcher; refusal must
        # leave its bytes and mode exactly as they were.
        self.assertEqual(launcher.read_bytes(), original_launcher)
        self.assertEqual(stat.S_IMODE(launcher.stat().st_mode), original_mode)
        self.assertEqual(self.release_bytes(home / "releases" / first), fixture["first_bytes"])
        self.assertIsNone(fixture["child"].poll())


if __name__ == "__main__":
    unittest.main()
