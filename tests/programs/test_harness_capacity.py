"""Real competing driver processes and kernels; model results are test fixtures.

Reasoned, critical, constructive, non-perfectionistic checks of concrete admission
criteria. No live models, production runtime writes, or delegated QA.
"""

from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts import noetic_application as application
from scripts import noetic_disciplines as disciplines
from scripts.noetic_scope import ScopeStore
from scripts import noetic_harness as harness
from tests.programs.test_noetic_harness import response_for


def fixture_actor(run, state, options):
    """Mock model result, real owned/reaped actor process, then hold the driver."""
    root = run.parent.parent
    name = Path(state["workspace"]).name
    directory = run / "activations" / state["current_activation"]
    assert harness._execute(run, directory, Path(state["workspace"]), "actor",
                            [sys.executable, "-c", "pass"], 5)["state"] == "passed"
    if options.get("scope"):
        harness._observe_native(run, state, options, {"client": options["client"], "session_id": f"fixture-{state['current_activation']}",
            "context_file": None, "observation": "test-authored-capacity-fixture"})
    (root / f"{name}.actor").write_text(str(os.getpid()))
    deadline = time.monotonic() + 30
    while not (root / "release-actor").exists():
        if time.monotonic() > deadline:
            raise RuntimeError("Fixture actor gate timed out")
        time.sleep(.01)
    result = response_for(state)
    result["session_ref"] = options["client"] + f":fixture-{state['current_activation']}"
    return result


def scoped_body(root, workspace, task="Fixture"):
    namespace = root / "ordinals.sqlite3"
    store = ScopeStore(namespace, root_mandate={"purpose": "Fixture capacity coordination"},
                       human_ref={"fixture": "human"}, source_ref={"fixture": "setup"})
    effort = store.create_effort(intent=task, environment={"cwd": str(workspace)}, mandate={"purpose": task},
        origin="human", human_ref={"fixture": "human"}, source_ref={"fixture": "effort"})
    instance = disciplines.Disciplines(namespace).create_instance(command_id=workspace.name,
        effort_root=effort["ordinal"], initiator=effort["ordinal"], pattern="cognition", intent=task, environment=effort["environment"])
    return {"pattern": "cognition", "workspace": str(workspace), "task": task, "effort_root": effort["ordinal"],
            "discipline_id": instance["id"], "environment": instance["environment"], "origin": "human", "human_ref": {"fixture": "human"}}


def contender(mode, root, workspace):
    """Run in a separate interpreter, including GUI's real descriptor handoff."""
    root, workspace = Path(root), Path(workspace)
    harness.invoke_actor = fixture_actor
    original = subprocess.Popen

    def spawn(argv, **kwargs):
        if "scripts.noetic_application" in argv:
            args = argv[argv.index("scripts.noetic_application") + 2:]
            code = ("import sys; from scripts import noetic_application as a; "
                    "from tests.programs.test_harness_capacity import fixture_actor; "
                    "a.harness.invoke_actor = fixture_actor; "
                    "raise SystemExit(a.driver_main(sys.argv[1], None if sys.argv[2]=='all' "
                    "else int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])))")
            argv = [sys.executable, "-B", "-c", code, *args]
        return original(argv, **kwargs)

    (root / f"{workspace.name}.ready").touch()
    while not (root / "go").exists():
        time.sleep(.01)
    verify = [sys.executable, "-c",
              "import pathlib,time; r=pathlib.Path(" + repr(str(root)) + "); "
              "(r/(pathlib.Path.cwd().name+'.verify')).touch(); "
              "exec(\"while not (r/'release-verify').exists(): time.sleep(.01)\")"]
    if mode == "cli":
        return harness.main(["start", "cognition", str(root / "task.txt"), "--workspace", str(workspace),
                             "--runs-dir", str(root / "runs"), "--max-activations", "1", "--verify", *verify])
    with patch.object(application.subprocess, "Popen", side_effect=spawn):
        app = application.Application(root / "runs", namespace_path=root / "ordinals.sqlite3")
        try:
            app.start({**scoped_body(root, workspace), "verify": verify})
        except application.ApplicationError as exc:
            print(f"HTTP {exc.status}: {exc}", file=sys.stderr)
            return 1
        return app.children[0].wait()


class CapacityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        environment = patch.dict(os.environ, {"NOETIC_APP_HOME": ""})
        environment.start(); self.addCleanup(environment.stop)
        self.runs = self.root / "runs"
        self.runs.mkdir(mode=0o700)
        (self.root / "task.txt").write_text("Model-free capacity fixture")
        self.children = []
        self.addCleanup(self.cleanup)

    def cleanup(self):
        (self.root / "go").touch()
        (self.root / "release-actor").touch()
        (self.root / "release-verify").touch()
        for child in self.children:
            child.communicate(timeout=35)

    def wait_for(self, predicate):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.02)
        self.fail("Fixture process did not reach expected state")

    def launch(self, mode, name):
        workspace = self.root / name
        workspace.mkdir()
        subprocess.run(["git", "init", "-q", str(workspace)], check=True, capture_output=True)
        code = ("import sys; from tests.programs.test_harness_capacity import contender; "
                "raise SystemExit(contender(*sys.argv[1:]))")
        child = subprocess.Popen([sys.executable, "-B", "-c", code, mode, str(self.root), str(workspace)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                 env={key: value for key, value in os.environ.items() if key != "USER_PROVIDED_PASSWORD"})
        self.children.append(child)
        return child

    def held(self, name):
        workspace = self.root / name
        workspace.mkdir()
        subprocess.run(["git", "init", "-q", str(workspace)], check=True, capture_output=True)
        with redirect_stdout(io.StringIO()):
            return harness.start("cognition", "Held fixture", workspace, self.runs, max_activations=0)[0]

    def test_simultaneous_cli_gui_limit_and_verification_checkpoint_release(self):
        for index in range(6):
            self.launch("gui" if index % 2 else "cli", f"work-{index}")
        self.wait_for(lambda: len(list(self.root.glob("*.ready"))) == 6)
        (self.root / "go").touch()
        self.wait_for(lambda: len(list(self.root.glob("*.actor"))) +
                      sum(p.poll() is not None for p in self.children) == 6)
        self.assertEqual(len(list(self.root.glob("*.actor"))), 2)
        self.assertEqual(len(list(self.runs.glob("*/controller.sqlite3"))), 2)
        for child in self.children:
            if child.poll() is not None:
                _, error = child.communicate()
                self.assertEqual(child.returncode, 1)
                self.assertIn("limit 2", error)
                self.assertIn(str(self.runs), error)
                self.assertIn("no work queued", error)
        held = self.held("held-work")
        before = harness.inspect(held)
        with self.assertRaises(harness.CapacityBusy):
            harness.drive(held)
        self.assertEqual(harness.inspect(held), before)
        self.assertFalse((held / "activations/activation-0").exists())
        # Both admitted drivers keep their slots during real verifier processes.
        (self.root / "release-actor").touch()
        self.wait_for(lambda: len(list(self.root.glob("*.verify"))) == 2)
        with self.assertRaises(harness.CapacityBusy):
            with harness.driver_slot(self.runs):
                self.fail("Verification released driver admission")
        for store in self.runs.glob("*/controller.sqlite3"):
            if store.parent != held:
                harness.pause(store.parent)
        (self.root / "release-verify").touch()
        for child in self.children:
            child.wait(timeout=20)
        with harness.driver_slot(self.runs), harness.driver_slot(self.runs):
            pass
        # Explicit retry advances the same untouched reservation, not a replay.
        with patch.object(harness, "invoke_actor", side_effect=fixture_actor):
            _, after = harness.drive(held, 1)
        self.assertEqual(after["current_activation"], "activation-1")

    def test_gui_handoff_saturation_and_crash_release(self):
        (self.runs / "harness-capacity.json").write_text('{"max_active_drivers":1}')
        child = self.launch("gui", "owner")
        (self.root / "go").touch()
        self.wait_for(lambda: (self.root / "owner.actor").exists())
        driver_pid = int((self.root / "owner.actor").read_text())
        # The spawning parent has closed its slot descriptor; the child still owns it.
        held = self.held("other")
        harness.pause(held)
        with self.assertRaises(application.ApplicationError) as caught:
            application.Application(self.runs).advance(held, {"mode": "all"}, selection={"kind": "application"})
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(caught.exception.run_id, held.name)
        self.assertTrue((held / "pause.requested").exists())
        with self.assertRaises(application.ApplicationError) as caught:
            application.Application(self.runs, namespace_path=self.root / "ordinals.sqlite3").start(
                scoped_body(self.root, self.root / "other", "Refused"))
        self.assertEqual(caught.exception.status, 409)
        self.assertIn("limit 1", str(caught.exception))
        self.assertIsNone(caught.exception.run_id)
        refused = self.launch("cli", "refused")
        _, error = refused.communicate(timeout=10)
        self.assertIn("limit 1", error)
        self.assertEqual(len(list(self.runs.glob("*/controller.sqlite3"))), 2)
        # Actor process was already reaped; kill only the fixture driver at its gate.
        os.kill(driver_pid, 9)
        child.wait(timeout=10)
        with harness.driver_slot(self.runs):
            pass
        state = harness.inspect(next(p.parent for p in self.runs.glob("*/controller.sqlite3") if p.parent != held))
        self.assertEqual(state["activations"][state["current_activation"]]["status"], "running")

    def test_config_validation_shared_scope_and_independent_roots(self):
        for text in ('{}', '[]', '{"max_active_drivers":true}', '{"max_active_drivers":0}',
                     '{"max_active_drivers":-1}', '{"max_active_drivers":1.5}',
                     '{"max_active_drivers":"2"}', '{"max_active_drivers":2,"extra":1}',
                     '{"max_active_drivers":1,"max_active_drivers":2}', 'broken'):
            with self.subTest(text=text):
                (self.runs / "harness-capacity.json").write_text(text)
                with self.assertRaisesRegex(ValueError, "Invalid harness capacity configuration"):
                    with harness.driver_slot(self.runs):
                        self.fail("Invalid policy admitted")
        (self.runs / "harness-capacity.json").write_text('{"max_active_drivers":1}')
        alias = self.root / "alias"
        alias.symlink_to(self.runs, target_is_directory=True)
        with harness.driver_slot(self.runs):
            with self.assertRaises(harness.CapacityBusy):
                with harness.driver_slot(alias):
                    self.fail("Alias bypassed root limit")
            with harness.driver_slot(self.root / "independent-runs"):
                pass
            held = self.held("held")
            harness.pause(held)
            harness.drive(held)
            harness.cancel(held)


if __name__ == "__main__":
    unittest.main()
