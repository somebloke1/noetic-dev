"""Implementation regression tests for the local Linux process boundary."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from scripts import noetic_application as application
from scripts import noetic_controller as controller
from scripts import noetic_harness as harness
from scripts import noetic_processes as processes
from scripts import noetic_release as release
from scripts import noetic_run as runtime
from tests.programs.test_noetic_harness import result_for


@unittest.skipUnless(sys.platform == "linux", "Linux process identity")
class ProcessBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        with redirect_stdout(io.StringIO()):
            self.run, self.state = harness.start("cognition", "bounded task", self.root,
                                                 self.root / "runs", max_activations=0)
        self.activation = self.state["current_activation"]
        self.directory = self.run / "activations" / self.activation
        self.directory.mkdir(parents=True, mode=0o700)
        self.owner = self.directory / "actor-ownership.json"

    def wait_for(self, predicate):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.02)
        self.fail("subprocess checkpoint not reached")

    def test_large_stdin_no_prompt_in_argv_environment_or_observation(self):
        prompt = "private-payload-marker\n" + "abc\u03bb" * 1024 * 1024
        code = ("import sys,hashlib,os; data=sys.stdin.buffer.read(); "
                "assert 'USER_PROVIDED_PASSWORD' not in os.environ; "
                "assert not any('private-payload-marker' in v for v in os.environ.values()); "
                "print(hashlib.sha256(data).hexdigest())")
        environment = dict(os.environ, USER_PROVIDED_PASSWORD="test-only-value")
        original = environment.copy()
        observed = harness._execute(self.run, self.directory, self.root, "actor",
                                    [sys.executable, "-c", code], 10, environment, stdin_text=prompt)
        self.assertEqual(observed["state"], "passed")
        self.assertEqual(environment, original)
        self.assertEqual((self.directory / "actor.stdout.log").read_text().strip(),
                         hashlib.sha256(prompt.encode()).hexdigest())
        self.assertNotIn(prompt, json.dumps(observed))
        self.assertEqual(self.owner.stat().st_mode & 0o777, 0o600)
        owner = json.loads(self.owner.read_text())
        self.assertEqual(set(owner["identity"]), {"pid", "pgid", "start_ticks", "boot_id"})
        self.assertTrue(processes.inspect(self.owner)["cleanup_confirmed"])

    def test_unread_large_stdin_does_not_block_cancel_or_timeout(self):
        prompt = "private-marker" * 1024 * 1024
        for cancel in (True, False):
            with self.subTest(cancel=cancel), ThreadPoolExecutor(max_workers=1) as pool:
                self.owner.unlink(missing_ok=True)
                (self.run / "cancel.requested").unlink(missing_ok=True)
                started = time.monotonic()
                future = pool.submit(harness._execute, self.run, self.directory, self.root, "actor",
                                     [sys.executable, "-c", "import time; time.sleep(60)"],
                                     10 if cancel else 0.3, None, prompt)
                self.wait_for(self.owner.exists)
                pid = json.loads(self.owner.read_text())["identity"]["pid"]
                self.assertNotIn(b"private-marker", Path(f"/proc/{pid}/cmdline").read_bytes())
                if cancel:
                    (self.run / "cancel.requested").touch()
                    with self.assertRaises(harness.Cancelled):
                        future.result(timeout=5)
                else:
                    self.assertEqual(future.result(timeout=5)["state"], "timed_out")
                self.assertLess(time.monotonic() - started, 5)
                self.assertTrue(processes.inspect(self.owner)["cleanup_confirmed"])

    def test_mismatched_stale_unknown_identity_never_signalled(self):
        child = processes.spawn([sys.executable, "-c", "import time; time.sleep(60)"],
                                cwd=self.root, env=None, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, ownership_path=self.owner)
        try:
            original = json.loads(self.owner.read_text())
            for field, value, expected in (("start_ticks", original["identity"]["start_ticks"] + 1, "mismatched"),
                                           ("boot_id", "old-boot", "unknown"), ("pid", -1, "unknown")):
                record = {**original, "identity": {**original["identity"], field: value}}
                processes.save(self.owner, record)
                with patch.object(processes.os, "killpg", side_effect=AssertionError("must not signal")):
                    result = processes.reconcile(self.owner, terminate=True, timeout=0.1)
                self.assertEqual(result["state"], expected)
                self.assertFalse(result["cleanup_confirmed"])
                self.assertIsNone(child.poll())
            self.owner.unlink()
            with patch.object(processes.os, "killpg", side_effect=AssertionError("must not signal")):
                self.assertEqual(processes.reconcile(self.owner, terminate=True)["state"], "unknown")
        finally:
            runtime.stop_process(child)

    def test_prior_boot_confirms_cleanup_without_probing_reused_pid_or_group(self):
        current_boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        prior_boot = "174c596d-b64e-4714-96dd-94e406945d4c"
        self.assertNotEqual(current_boot, prior_boot)
        owner = {"pid": os.getpid(), "pgid": os.getpid(), "start_ticks": 1, "boot_id": prior_boot}
        processes.save(self.owner, {"identity": owner, "state": "spawned"})
        original = self.owner.read_bytes()
        with patch.object(processes, "identity", side_effect=AssertionError("No current PID lookup")), \
                patch.object(processes.os, "killpg", side_effect=AssertionError("No group probe or signal")):
            observed = processes.inspect(self.owner)
            self.assertEqual(observed["state"], "boot_ended")
            self.assertTrue(observed["cleanup_confirmed"])
            self.assertEqual(observed["current_boot_id"], current_boot)
            self.assertEqual(observed["identity"], owner)
            self.assertNotIn("returncode", observed)
            reconciled = processes.reconcile(self.owner, terminate=True)
        self.assertEqual(reconciled["state"], "boot_ended")
        self.assertEqual(self.owner.read_bytes(), original)

    def test_invalid_recorded_or_current_boot_identity_fails_closed(self):
        boot = "174c596d-b64e-4714-96dd-94e406945d4c"
        owner = {"pid": os.getpid(), "pgid": os.getpid(), "start_ticks": 1, "boot_id": boot}
        bad_boots = (None, "", "old-boot", boot.replace("-", ""), boot.upper(),
                     "00000000-0000-0000-0000-000000000000", "174c596d-b64e-1714-96dd-94e406945d4c")
        with patch.object(processes, "identity", side_effect=AssertionError("No PID lookup")), \
                patch.object(processes.os, "killpg", side_effect=AssertionError("No group probe or signal")):
            for value in bad_boots:
                with self.subTest(recorded_boot=value):
                    processes.save(self.owner, {"identity": {**owner, "boot_id": value}})
                    result = processes.inspect(self.owner)
                    self.assertEqual(result["state"], "unknown")
                    self.assertFalse(result["cleanup_confirmed"])
            processes.save(self.owner, {"identity": owner})
            read_text = Path.read_text
            for value in bad_boots[1:]:
                with self.subTest(current_boot=value), patch.object(Path, "read_text", autospec=True,
                        side_effect=lambda path, *args, **kwargs: value if str(path) ==
                        "/proc/sys/kernel/random/boot_id" else read_text(path, *args, **kwargs)):
                    result = processes.inspect(self.owner)
                    self.assertEqual(result["state"], "unknown")
                    self.assertFalse(result["cleanup_confirmed"])
            for bad in ({k: v for k, v in owner.items() if k != "boot_id"},
                        {**owner, "pid": True}, {**owner, "pgid": owner["pid"] + 1},
                        {**owner, "start_ticks": 0}, {**owner, "extra": "ambiguous"}):
                with self.subTest(identity=bad):
                    processes.save(self.owner, {"identity": bad})
                    self.assertFalse(processes.inspect(self.owner)["cleanup_confirmed"])

    def test_code_only_gate_accepts_prior_boot_without_changing_terminal_history(self):
        self.state = controller.begin_activation(self.run / "controller.sqlite3", self.activation, self.state["version"])
        self.state = controller.cancel_run(self.run / "controller.sqlite3", "Prior boot fixture")
        owner = {"pid": os.getpid(), "pgid": os.getpid(), "start_ticks": 1,
                 "boot_id": "174c596d-b64e-4714-96dd-94e406945d4c"}
        processes.save(self.owner, {"identity": owner})
        before = {p.relative_to(self.run): p.read_bytes() for p in self.run.rglob("*") if p.is_file()}
        with patch.object(processes, "identity", side_effect=AssertionError("No PID lookup")), \
                patch.object(processes.os, "killpg", side_effect=AssertionError("No group probe or signal")):
            report = release._check_code_state(self.root / "runs", False)
            self.assertTrue(report["historical_cleanup_confirmed"])
            self.assertEqual(report["unknown_ownership_records"], 0)
            self.assertEqual(harness.inspect(self.run), self.state)
        self.assertEqual(before, {p.relative_to(self.run): p.read_bytes()
                                 for p in self.run.rglob("*") if p.is_file()})
        for bad in ("old-boot", Path("/proc/sys/kernel/random/boot_id").read_text().strip()):
            processes.save(self.owner, {"identity": {**owner, "boot_id": bad}})
            with patch.object(processes, "identity", return_value={**owner, "boot_id": bad}), \
                    patch.object(processes.os, "killpg"):
                with self.assertRaisesRegex(ValueError, "cleanup unconfirmed"):
                    release._check_code_state(self.root / "runs", False)
        processes.save(self.owner, {"identity": owner})
        runtime.record(self.run, "step.started", {"step": f"{self.activation}/actor"})
        with self.assertRaisesRegex(ValueError, "Unfinished process observation"):
            release._check_code_state(self.root / "runs", False)

    def test_absent_group_is_safe_and_not_success(self):
        child = processes.spawn([sys.executable, "-c", "pass"], cwd=self.root, env=None,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, ownership_path=self.owner)
        child.wait(timeout=5)
        self.state = controller.begin_activation(self.run / "controller.sqlite3", self.activation, self.state["version"])
        real_killpg = os.killpg
        def observe_only(pgid, sig):
            self.assertEqual(sig, 0)
            return real_killpg(pgid, sig)
        with patch.object(processes.os, "killpg", side_effect=observe_only):
            self.assertTrue(processes.reconcile(self.owner, terminate=True)["cleanup_confirmed"])
            state = harness.cancel(self.run)
        self.assertEqual(state["status"], "cancelled")
        self.assertTrue(application.runtime_info(self.run, state)["cleanup_confirmed"])

    def test_unknown_cancel_remains_unconfirmed_and_never_replays(self):
        self.state = controller.begin_activation(self.run / "controller.sqlite3", self.activation, self.state["version"])
        with patch.object(processes.os, "killpg", side_effect=AssertionError("unknown identity")):
            state = harness.cancel(self.run)
            self.assertEqual(state["status"], "active")
            info = application.runtime_info(self.run, state)
            self.assertFalse(info["cleanup_confirmed"])
            self.assertIn("only a request", info["reason"])
            with patch.object(harness, "invoke_actor", side_effect=AssertionError("no replay")):
                state = harness.drive(self.run)[1]
            self.assertEqual(state["status"], "failed")
            self.assertIn("runtime_uncertain", state["reason"])
            self.assertFalse(application.runtime_info(self.run, state)["cleanup_confirmed"])

    def test_legacy_stdin_and_literal_generic_argv_preserve_caller_environment(self):
        code = "import sys,os; assert 'USER_PROVIDED_PASSWORD' not in os.environ; print(sys.argv[1]); print(sys.stdin.read())"
        argv = [sys.executable, "-c", code, "literal-user-argument"]
        with patch.dict(os.environ, {"USER_PROVIDED_PASSWORD": "test-only-value"}):
            original = os.environ.copy()
            self.assertEqual(runtime.execute_step(self.run, self.root, "legacy", argv, 5,
                                                  stdin_text="generated private prompt"), "passed")
            self.assertEqual(dict(os.environ), original)
        self.assertEqual((self.run / "legacy.stdout.log").read_text(),
                         "literal-user-argument\ngenerated private prompt\n")
        event = runtime.project(runtime.read_events(self.run))["steps"]["legacy"]
        self.assertEqual(event["argv"], argv)
        self.assertNotIn("generated private prompt", json.dumps(event))

    def test_never_started_run_has_no_groups_to_clean(self):
        with patch.object(processes, "inspect", side_effect=AssertionError("no process started")):
            info = harness.process_info(self.run, self.state)
            self.assertEqual(info, {"cleanup_confirmed": True, "state": "not_started", "processes": {}})
            state = harness.cancel(self.run)
            self.assertEqual(state["status"], "cancelled")
            self.assertTrue(application.runtime_info(self.run, state)["cleanup_confirmed"])

    def test_completed_run_confirms_every_started_actor_and_verify_group_absent(self):
        state = self.state
        expected = set()
        while state["status"] == "active":
            activation = state["current_activation"]
            directory = self.run / "activations" / activation
            directory.mkdir(parents=True, mode=0o700, exist_ok=True)
            state = controller.begin_activation(self.run / "controller.sqlite3", activation, state["version"])
            for name in ("actor", "verify"):
                observed = harness._execute(self.run, directory, self.root, name, [sys.executable, "-c", "pass"], 5)
                self.assertEqual(observed["state"], "passed")
                expected.add(f"{activation}/{name}")
            state = controller.submit_result(self.run / "controller.sqlite3", activation, state["version"],
                                             result_for(state), f"fixture:{activation}", f"fixture:{activation}")
            info = harness.process_info(self.run, state)
            self.assertEqual(set(info["processes"]), expected)
            self.assertTrue(info["cleanup_confirmed"])
            self.assertTrue(all(value["state"] == "absent" for value in info["processes"].values()))
        self.assertEqual(state["status"], "completed")
        self.assertEqual(len(expected), 8)
        self.assertEqual(application.runtime_info(self.run, state)["activity"], "terminal")
        with patch.object(harness, "invoke_actor", side_effect=AssertionError("no replay")):
            self.assertEqual(harness.cancel(self.run), state)
            self.assertEqual(harness.drive(self.run)[1]["status"], "completed")

    def test_legacy_completed_history_with_missing_records_is_unknown_not_running(self):
        # Kernel-only fixture: no OS actors were invoked, like pre-ownership history.
        state = self.state
        expected = set()
        while state["status"] == "active":
            activation = state["current_activation"]
            state = controller.begin_activation(self.run / "controller.sqlite3", activation, state["version"])
            expected.add(f"{activation}/actor")
            if activation == self.activation:
                runtime.record(self.run, "step.started", {"step": f"{activation}/verify"})
                expected.add(f"{activation}/verify")
            state = controller.submit_result(self.run / "controller.sqlite3", activation, state["version"],
                                             result_for(state), f"fixture:{activation}", f"fixture:{activation}")
        with patch.object(processes.os, "killpg", side_effect=AssertionError("unknown history must not signal")):
            cleanup = harness.process_info(self.run, state, terminate=True)
            self.assertEqual(set(cleanup["processes"]), expected)
            self.assertFalse(cleanup["cleanup_confirmed"])
            self.assertTrue(all(value["state"] == "unknown" for value in cleanup["processes"].values()))
            info = application.runtime_info(self.run, state)
            self.assertEqual(info["activity"], "terminal")
            self.assertFalse(info["cleanup_confirmed"])
            self.assertIn("does not establish an active process", info["reason"])
            self.assertEqual(harness.cancel(self.run), state)

    def test_previous_orphan_group_stays_unconfirmed_across_ready_and_cancel(self):
        libc = ctypes.CDLL(None, use_errno=True)
        previous = ctypes.c_int()
        self.assertEqual(libc.prctl(37, ctypes.byref(previous), 0, 0, 0), 0)
        self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)
        self.addCleanup(lambda: libc.prctl(36, previous.value, 0, 0, 0))
        for name in ("actor", "verify"):
            with self.subTest(step=name), redirect_stdout(io.StringIO()):
                run, state = harness.start("cognition", "orphan fixture", self.root, self.root / "runs", max_activations=0)
                activation = state["current_activation"]
                directory = run / "activations" / activation
                directory.mkdir(parents=True, mode=0o700)
                state = controller.begin_activation(run / "controller.sqlite3", activation, state["version"])
                if name == "verify":
                    harness._execute(run, directory, self.root, "actor", [sys.executable, "-c", "pass"], 5)
                # The parent waits for its child's PID output before exiting.
                # stop_process kills the descendant; only this test reaps it.
                code = ("import os,time; r,w=os.pipe(); pid=os.fork()\n"
                        "if pid == 0:\n os.close(r); print(os.getpid(),flush=True); os.write(w,b'1'); os.close(w); time.sleep(60)\n"
                        "else:\n os.close(w); os.read(r,1); os.close(r); os._exit(0)")
                orphan = None
                try:
                    observed = harness._execute(run, directory, self.root, name, [sys.executable, "-c", code], 5)
                    orphan = int((directory / f"{name}.stdout.log").read_text().strip())
                    self.assertEqual(observed["state"], "passed")
                    owner = directory / f"{name}-ownership.json"
                    self.assertEqual(processes.inspect(owner)["state"], "uncertain")
                    state = controller.submit_result(run / "controller.sqlite3", activation, state["version"],
                                                     result_for(state), "fixture:orphan", "fixture:orphan")
                    self.assertEqual(state["activations"][state["current_activation"]]["status"], "ready")
                    cleanup = harness.process_info(run, state)
                    self.assertFalse(cleanup["cleanup_confirmed"])
                    self.assertEqual(cleanup["processes"][f"{activation}/{name}"]["state"], "uncertain")
                    real_killpg = os.killpg
                    def observe_only(pgid, sig):
                        self.assertEqual(sig, 0, "missing leader cannot authorize termination")
                        return real_killpg(pgid, sig)
                    with patch.object(processes.os, "killpg", side_effect=observe_only):
                        state = harness.cancel(run)
                    self.assertEqual(state["status"], "active")
                    info = application.runtime_info(run, state)
                    self.assertFalse(info["cleanup_confirmed"])
                    self.assertIn("only a request", info["reason"])
                    self.assertEqual(os.waitpid(orphan, 0)[0], orphan)
                    orphan = None
                    self.assertEqual(processes.inspect(owner)["state"], "absent")
                    state = harness.cancel(run)
                    self.assertEqual(state["status"], "cancelled")
                    self.assertTrue(application.runtime_info(run, state)["cleanup_confirmed"])
                    with patch.object(harness, "invoke_actor", side_effect=AssertionError("no replay")):
                        self.assertEqual(harness.drive(run)[1]["status"], "cancelled")
                finally:
                    if orphan is not None:
                        os.kill(orphan, signal.SIGKILL)
                        os.waitpid(orphan, 0)

    def test_crashed_driver_owned_child_controlled_cancel_and_no_replay(self):
        # Adopt only this test's orphan so its zombie can be reaped deterministically.
        libc = ctypes.CDLL(None, use_errno=True)
        previous = ctypes.c_int()
        self.assertEqual(libc.prctl(37, ctypes.byref(previous), 0, 0, 0), 0)
        self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)
        self.addCleanup(lambda: libc.prctl(36, previous.value, 0, 0, 0))
        self.state = controller.begin_activation(self.run / "controller.sqlite3", self.activation, self.state["version"])
        code = ("import sys; from pathlib import Path; from scripts import noetic_harness as h; "
                f"run=Path({str(self.run)!r}); directory=Path({str(self.directory)!r}); "
                "\nwith h._driver_lock(run):\n"
                f" h._execute(run,directory,Path({str(self.root)!r}),'actor',"
                "[sys.executable,'-c','import time; time.sleep(60)'],90,stdin_text='private task')")
        driver = subprocess.Popen([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[2],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        pid = None
        reaper = None
        try:
            self.wait_for(self.owner.exists)
            pid = json.loads(self.owner.read_text())["identity"]["pid"]
            driver.kill()
            driver.wait(timeout=5)
            self.assertEqual(processes.inspect(self.owner)["state"], "owned")
            info = application.runtime_info(self.run, self.state)
            self.assertFalse(info["cleanup_confirmed"])
            self.assertFalse(info["can_advance"])
            reaper = threading.Thread(target=lambda: os.waitpid(pid, 0))
            reaper.start()
            state = harness.cancel(self.run)
            reaper.join(timeout=5)
            self.assertFalse(reaper.is_alive())
            self.assertEqual(state["status"], "cancelled")
            self.assertTrue(application.runtime_info(self.run, state)["cleanup_confirmed"])
            with patch.object(harness, "invoke_actor", side_effect=AssertionError("no replay")):
                self.assertEqual(harness.drive(self.run)[1]["status"], "cancelled")
        finally:
            if driver.poll() is None:
                driver.kill()
                driver.wait()
            driver.stderr.close()
            if pid is not None and processes.inspect(self.owner)["state"] == "owned":
                os.killpg(pid, signal.SIGKILL)
                if reaper is None:
                    os.waitpid(pid, 0)
            if reaper is not None:
                reaper.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
