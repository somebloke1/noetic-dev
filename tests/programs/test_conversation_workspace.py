"""Existing effort conversations use exact folders without repository preparation."""

import os
from pathlib import Path
import stat
import subprocess
import unittest
from unittest.mock import patch

from scripts import noetic_projects as projects, noetic_sessions as sessions
from tests.programs import test_noetic_sessions as session_fixture
from tests.programs import test_developer_session_api as api_fixture


class ConversationWorkspaceTests(unittest.TestCase):
    setUp = session_fixture.SessionTests.setUp
    tearDown = session_fixture.SessionTests.tearDown
    wait = session_fixture.SessionTests.wait
    records = session_fixture.SessionTests.records

    def git(self, directory, *args):
        environment = {key: value for key, value in os.environ.items()
                       if key not in {"USER_PROVIDED_PASSWORD", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"}}
        return subprocess.run(["git", "-C", str(directory), *args], check=True,
                              capture_output=True, env={**environment, "GIT_OPTIONAL_LOCKS": "0"}).stdout.strip()

    def snapshot(self, directory):
        return {str(path.relative_to(directory)): (path.read_bytes(), stat.S_IMODE(path.stat().st_mode), path.stat().st_mtime_ns)
                for path in directory.rglob("*") if path.is_file()}

    def parent_repository(self):
        repository = self.workspace
        (repository / "tracked.txt").write_text("committed parent")
        tracked = repository / "package"
        tracked.mkdir()
        (tracked / "code.py").write_text("committed package")
        self.git(repository, "add", ".")
        self.git(repository, "-c", "user.name=Fixture", "-c", "user.email=fixture@localhost",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Fixture base")
        (repository / "tracked.txt").write_text("staged parent")
        self.git(repository, "add", "tracked.txt")
        (repository / "tracked.txt").write_text("dirty parent")
        (repository / "untracked.txt").write_text("untracked parent")
        ordinary = repository / "ordinary" / "chosen folder"
        ordinary.mkdir(parents=True)
        (ordinary / "notes.txt").write_text("existing effort files")
        return repository, tracked, ordinary

    def effort(self, workspace, intent="Conversation fixture"):
        return self.service.create_effort({"intent": intent, "environment": {"cwd": str(workspace)}})["ordinal"]

    def start(self, workspace, effort=None, **options):
        effort = effort or self.effort(workspace)
        item = self.service.create({"workspace": str(workspace), "effort_root": effort,
                                    "prompt": "fixture conversation", **options})
        self.wait(item["id"])
        return self.assert_native(item, workspace, effort)

    def assert_native(self, item, workspace, effort):
        item = self.service.inspect(item["id"])
        self.assertEqual(item["workspace"], str(workspace))
        self.assertEqual(item["ordinal"], effort)
        self.assertEqual(item["effort_root"], effort)
        self.assertEqual(item["target"]["ordinal"], effort)
        self.assertEqual(self.service.position(effort)["environment"]["cwd"], str(workspace))
        started = next(record for record in self.records(item["id"]) if record.get("type") == "pi_started")
        self.assertEqual((Path("/proc") / str(started["pid"]) / "cwd").resolve(), workspace)
        observed = next(record["data"] for record in self.records(item["id"], "event")
                        if record.get("command") == "get_state" and record.get("success"))
        self.assertEqual(item["native_session_id"], observed["sessionId"])
        self.assertEqual(item["native_session_file"], observed["sessionFile"])
        retained = self.service.registry.domain.store().sessions(effort, item["target"]["instantiation"])[item["target"]["session"] - 1]
        self.assertEqual(retained["native_ref"]["session_id"], observed["sessionId"])
        self.assertEqual(retained["native_ref"]["context_file"], observed["sessionFile"])
        self.assertTrue(Path(observed["sessionFile"]).is_file())
        return item

    def test_nested_ordinary_folder_preserves_entire_ancestor_repository(self):
        repository, _, selected = self.parent_repository()
        self.assertEqual(self.git(selected, "rev-parse", "--show-toplevel").decode(), str(repository))
        before = self.snapshot(repository)
        self.start(selected)
        self.assertEqual(self.snapshot(repository), before)
        self.assertFalse((selected / ".git").exists())

    def test_tracked_subdirectory_plain_folder_and_repository_root_are_usable(self):
        repository, tracked, _ = self.parent_repository()
        plain = self.home / "plain folder"
        plain.mkdir()
        (plain / "notes.txt").write_text("plain existing work")
        for workspace in (tracked, plain, repository):
            with self.subTest(workspace=workspace):
                before = self.snapshot(workspace)
                with patch.object(projects, "_git", side_effect=AssertionError("Conversation must not invoke Git")):
                    self.start(workspace)
                self.assertEqual(self.snapshot(workspace), before)
                if workspace != repository:
                    self.assertFalse((workspace / ".git").exists())

    def test_invalid_missing_and_file_folders_have_no_runtime_or_reservation_effects(self):
        missing = self.home / "missing"
        file = self.home / "file"
        file.write_text("preserve")
        invalid = (missing, file, file / "child", Path("/"))
        for workspace in invalid:
            with self.subTest(workspace=workspace, boundary="registration"):
                before = self.snapshot(self.home)
                with patch.object(self.service, "_launch") as launch, patch.object(self.service.registry, "create") as reserve, \
                        patch.object(self.service.registry.domain, "create") as register:
                    with self.assertRaises(sessions.SessionError) as failed:
                        self.effort(workspace)
                    self.assertEqual(failed.exception.status, 400)
                    launch.assert_not_called()
                    reserve.assert_not_called()
                    register.assert_not_called()
                self.assertEqual(self.snapshot(self.home), before)
                self.assertFalse(self.service.registry.domain.path.exists())
                self.assertFalse(self.service.registry.path.exists())
        for workspace in invalid:
            with self.subTest(workspace=workspace, boundary="conversation"):
                # Lower-level declarations can retain a workspace that is no longer usable.
                effort = self.service.registry.domain.create({"intent": "Legacy invalid workspace",
                    "environment": {"cwd": str(workspace)}})["ordinal"]
                before = self.snapshot(self.home)
                with patch.object(self.service, "_launch") as launch, patch.object(self.service.registry, "create") as reserve:
                    with self.assertRaises(sessions.SessionError) as failed:
                        self.service.create({"effort_root": effort, "prompt": "must never launch"})
                    self.assertEqual(failed.exception.status, 400)
                    launch.assert_not_called()
                    reserve.assert_not_called()
                self.assertEqual(self.snapshot(self.home), before)
                self.assertIsNone(self.service.position(effort)["current_instantiation"])
        self.assertFalse(missing.exists())
        self.assertFalse(self.service.registry.path.exists())
        self.assertEqual(file.read_text(), "preserve")

    def test_invalid_folder_values_are_refused_without_creation(self):
        before = self.snapshot(self.home)
        for value in (None, "", "\0bad", Path("/"), "./relative/path", self.home / "missing"):
            with self.subTest(value=value), self.assertRaises(projects.ProjectError):
                projects.validate_workspace(value)
        self.assertEqual(self.snapshot(self.home), before)

    def test_mismatched_and_foreign_effort_workspaces_reject_before_effects(self):
        other = self.home / "other"
        other.mkdir()
        a, b = self.effort(self.workspace, "A"), self.effort(other, "B")
        for fields in ({"effort_root": a, "workspace": str(other)},
                       {"effort_root": a, "ordinal": b, "workspace": str(other)},
                       {"effort_root": a, "workspace": "\0invalid"}):
            with self.subTest(fields=fields):
                before = self.snapshot(self.home)
                with patch.object(self.service, "_launch") as launch, patch.object(self.service.registry, "create") as reserve:
                    with self.assertRaises(sessions.SessionError):
                        self.service.create({"prompt": "must never launch", **fields})
                    launch.assert_not_called()
                    reserve.assert_not_called()
                self.assertEqual(self.snapshot(self.home), before)
        self.assertFalse(self.service.registry.path.exists())

    def test_exact_targets_succession_and_actual_delegator_survive_nested_folder(self):
        repository, _, selected = self.parent_repository()
        before = self.snapshot(repository)
        effort = self.effort(selected)
        first = self.start(selected, effort)
        queued = self.service.bind(first["target"], "prompt", {"message": "retained first recipient"}, effort_root=effort)
        second = self.start(selected, effort)
        self.assertEqual(second["target"]["instantiation"], first["target"]["instantiation"])
        self.assertGreater(second["target"]["session"], first["target"]["session"])
        self.assertNotEqual(second["native_session_id"], first["native_session_id"])
        with self.assertRaises(sessions.SessionError):
            self.service.deliver(queued["id"], effort_root=effort)
        with self.assertRaises(sessions.SessionError):
            self.service.create({"workspace": str(self.home), "prompt": "wrong delegate"}, parent_id=second["id"])
        child = sessions.control(self.runs, second["id"], {"action": "delegate", "prompt": "bounded fixture", "thinking": "low"})
        self.wait(child["id"])
        self.assertEqual(child["workspace"], str(selected))
        self.assertEqual(child["effort_root"], effort)
        self.assertEqual(child["parentTarget"], second["target"])
        started = next(record for record in self.records(child["id"]) if record.get("type") == "pi_started")
        self.assertEqual((Path("/proc") / str(started["pid"]) / "cwd").resolve(), selected)
        mandate = self.service.registry.domain.store().mandates(child["ordinal"])[0]
        self.assertEqual(mandate["delegator"], second["target"])
        self.assertEqual(mandate["origin"], "agent")
        successor = self.start(selected, effort, succession={"predecessor": 1, "handoff": {"reason": "fixture succession"}})
        self.assertEqual(successor["target"]["instantiation"], 2)
        with self.assertRaises(sessions.SessionError):
            self.service.prompt(second["target"], "must not redirect", effort_root=effort)
        self.assertEqual(self.service.detail(first["target"], effort_root=effort)["session"]["native_session_id"], first["native_session_id"])
        self.assertEqual(self.service.registry.domain.store().action(queued["id"], scope=sessions.Scope.effort(effort))["target"], first["target"])
        self.assertEqual(self.snapshot(repository), before)


class ConversationWorkspaceApiTests(unittest.TestCase):
    setUp = api_fixture.DeveloperSessionApiTests.setUp
    tearDown = api_fixture.DeveloperSessionApiTests.tearDown
    stop_server = api_fixture.DeveloperSessionApiTests.stop_server
    request = api_fixture.DeveloperSessionApiTests.request
    wait = session_fixture.SessionTests.wait
    records = session_fixture.SessionTests.records
    git = ConversationWorkspaceTests.git
    snapshot = ConversationWorkspaceTests.snapshot
    parent_repository = ConversationWorkspaceTests.parent_repository
    assert_native = ConversationWorkspaceTests.assert_native

    def test_real_http_start_uses_exact_declared_nested_folder(self):
        repository, _, selected = self.parent_repository()
        before = self.snapshot(repository)
        status, registration = self.request("/api/efforts", {"intent": "HTTP nested effort", "environment": {"cwd": str(selected)}})
        self.assertEqual(status, 201, registration)
        effort = registration["effort"]["ordinal"]
        status, started = self.request("/api/developer-sessions", {"effort_root": effort, "workspace": str(selected), "prompt": "fixture HTTP conversation"})
        self.assertEqual(status, 201, started)
        self.wait(started["session"]["id"])
        self.assert_native(started["session"], selected, effort)
        self.assertEqual(self.snapshot(repository), before)
        self.assertFalse((selected / ".git").exists())


if __name__ == "__main__":
    unittest.main()
