"""Client protocol and semantic-review gates for actual development runs."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import noetic_develop as development
from scripts import noetic_run as runtime


def opencode(text, session="session-1", reason="stop", message="message-final"):
    return [
        {"type": "text", "sessionID": session, "part": {"id": "part-1", "messageID": message, "text": text}},
        {"type": "step_finish", "sessionID": session, "part": {"messageID": message, "reason": reason}},
    ]


class DevelopmentTests(unittest.TestCase):
    def test_profile_control_reaches_worker_process_and_unsupported_controls_stop(self):
        def command(client, prompt, role, model, run_dir=None, workspace=None, context_dirs=()):
            expected = ["--thinking", "high"] if role == "inquirer" else []
            text = "Inspected source." if role == "inquirer" else "ACCEPT\nInspected fixture source."
            events = [{"type": "session", "id": role},
                      {"type": "agent_end", "willRetry": False, "messages": [
                          {"role": "assistant", "stopReason": "stop", "content": [{"type": "text", "text": text}]}]}]
            code = ("import sys; assert sys.argv[1:] == " + repr(expected)
                    + "; assert sys.stdin.read(); print(" + repr("\n".join(json.dumps(e) for e in events)) + ")")
            return [sys.executable, "-c", code], None
        with patch.object(development, "client_command", side_effect=command), redirect_stdout(io.StringIO()):
            run, state = development.develop("Inspect sources", self.root, self.root / "runs", None,
                                             client="pi", inquiry=True,
                                             worker_controls={"reasoning_effort": "high"})
        self.assertEqual(state["state"], "accepted")
        self.assertEqual(runtime.read_events(run)[1]["data"]["worker_controls"], {"reasoning_effort": "high"})
        with patch.object(development, "client_command") as launch:
            with self.assertRaisesRegex(ValueError, "profile controls"):
                development.develop("Inspect sources", self.root, self.root / "runs", None,
                                    client="pi", inquiry=True, worker_controls={"temperature": 0.2})
        launch.assert_not_called()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.transcript = self.root / "output.jsonl"

    def parse(self, events, client="opencode"):
        self.transcript.write_text("\n".join(json.dumps(event) for event in events))
        return development.parse_transcript(self.transcript, client)

    def test_only_final_assistant_text_counts(self):
        events = opencode("ACCEPT\nEarlier unrelated text", reason="tool-calls", message="earlier")
        events += opencode("REJECT\nActual defect", message="final")
        self.assertEqual(self.parse(events)["text"], "REJECT\nActual defect")
        events.insert(2, {"type": "tool_use", "sessionID": "session-1", "part": {"state": {"output": "ACCEPT"}}})
        self.assertEqual(self.parse(events)["text"], "REJECT\nActual defect")

    def test_incomplete_or_error_transcripts_cannot_supply_success(self):
        for events in ([], opencode("ACCEPT", reason="length"), opencode("ACCEPT") + [{"type": "error"}], opencode("ACCEPT")[:1]):
            with self.subTest(events=events), self.assertRaises(ValueError):
                self.parse(events)
        errors = [{"type": "session", "id": "pi-session"}, {"type": "agent_end", "messages": [
            {"role": "assistant", "stopReason": "error", "content": []},
        ], "willRetry": False}]
        with self.assertRaises(ValueError):
            self.parse(errors, "pi")
        with self.assertRaisesRegex(ValueError, "unfinished later"):
            self.parse(opencode("ACCEPT\nOld result") + [
                {"type": "step_start", "sessionID": "session-1", "part": {"messageID": "unfinished"}},
            ])

    def test_pi_final_assistant_and_retry_boundary(self):
        events = [{"type": "session", "id": "pi-session"}, {"type": "agent_end", "willRetry": True, "messages": []}]
        events += [{"type": "agent_end", "willRetry": False, "messages": [
            {"role": "assistant", "stopReason": "stop", "content": [{"type": "text", "text": "ACCEPT\nRead source"}]},
        ]}]
        self.assertEqual(self.parse(events, "pi")["text"], "ACCEPT\nRead source")

    def test_reviewer_command_is_fresh_and_has_no_write_or_shell_tools(self):
        command, env = development.client_command("opencode", "Review", "reviewer", "provider/model", self.root)
        policy = json.loads(env["OPENCODE_CONFIG_CONTENT"])["agent"]["noetic-reviewer"]["permission"]
        self.assertEqual(policy["*"], "deny")
        self.assertNotIn("edit", policy)
        self.assertNotIn("bash", policy)
        self.assertNotIn("--session", command)
        self.assertIn("--pure", command)
        command, _ = development.client_command("pi", "Review", "reviewer", None)
        self.assertIn("read,grep,find,ls", command)
        self.assertNotIn("--continue", command)

    def test_real_process_work_verify_and_review_gates(self):
        for verdict, expected in (("ACCEPT\nInspected source and checks: correct.", "accepted"),
                                  ("REJECT\nConcrete requirement missing.", "rejected"),
                                  ("Looks good", "awaiting_review")):
            with self.subTest(verdict=verdict):
                def command(client, prompt, role, model, run_dir=None, workspace=None, context_dirs=()):
                    events = opencode("Implemented and checked." if role == "worker" else verdict, session=role)
                    code = "import sys; assert sys.stdin.read(); print(" + repr("\n".join(json.dumps(event) for event in events)) + ")"
                    if role == "worker":
                        code = "from pathlib import Path; Path('result.txt').write_text('real'); " + code
                    return [sys.executable, "-c", code], None
                with patch.object(development, "client_command", side_effect=command), redirect_stdout(io.StringIO()):
                    run_dir, result = development.develop("Create result.txt", self.root, self.root / "runs",
                        [sys.executable, "-c", "from pathlib import Path; assert Path('result.txt').read_text() == 'real'"])
                self.assertEqual(result["state"], expected)
                self.assertTrue((run_dir / "work.md").exists())
                self.assertTrue((run_dir / "review.md").exists())
                self.assertEqual(runtime.project(runtime.read_events(run_dir)), result)
                prompt = (run_dir / "review-prompt.txt").read_text()
                for name in ("changes.diff", "changes.json"):
                    self.assertIn(str(run_dir / name), prompt)
                self.assertEqual(json.loads((run_dir / "changes.json").read_text())["status"], "unavailable")

    def test_git_evidence_after_work_and_verification_including_failures(self):
        subprocess.run(["git", "init", str(self.root)], check=True, capture_output=True)
        (self.root / ".gitignore").write_text(".runtime/\n")
        for failure in (None, "work", "verify", "transcript"):
            with self.subTest(failure=failure):
                (self.root / "result.txt").write_text("dirty baseline\n")
                (self.root / "verification.txt").unlink(missing_ok=True)

                def command(client, prompt, role, model, run_dir=None, workspace=None, context_dirs=()):
                    events = opencode("Implemented" if role == "worker" else "ACCEPT\nRead source and logs.", session=role)
                    code = "print(" + repr("\n".join(json.dumps(event) for event in events)) + ")"
                    if role == "worker":
                        code = "from pathlib import Path; Path('result.txt').write_text('after work\\n'); " + code
                        if failure == "work":
                            code += "; raise SystemExit(2)"
                        elif failure == "transcript":
                            code += "; print('invalid json')"
                    else:
                        assert run_dir is not None
                        self.assertIn(str(run_dir / "changes.diff"), prompt)
                        self.assertIn("verification.txt", (run_dir / "changes.diff").read_text())
                    return [sys.executable, "-c", code], None

                verify = [sys.executable, "-c", "from pathlib import Path; Path('verification.txt').write_text('checked'); "
                          + ("raise SystemExit(3)" if failure == "verify" else "pass")]
                with patch.object(development, "client_command", side_effect=command), redirect_stdout(io.StringIO()):
                    run_dir, result = development.develop("Work", self.root, self.root / ".runtime/runs", verify)
                self.assertEqual(result["state"], "accepted" if failure is None else "failed")
                manifest = json.loads((run_dir / "changes.json").read_text())
                self.assertEqual(manifest["status"], "available")
                expected = {"result.txt"} if failure in ("work", "transcript") else {"result.txt", "verification.txt"}
                self.assertEqual({entry["path"] for entry in manifest["changes"]}, expected)
                self.assertIn("-dirty baseline\n+after work\n", (run_dir / "changes.diff").read_text())

    def test_zero_exit_model_error_does_not_run_verification(self):
        def command(*args, **kwargs):
            return [sys.executable, "-c", "print('{\"type\":\"error\",\"sessionID\":\"s\"}')"], None
        with patch.object(development, "client_command", side_effect=command), redirect_stdout(io.StringIO()):
            run_dir, result = development.develop("Work", self.root, self.root / "runs", [sys.executable, "-c", "raise SystemExit(99)"])
        self.assertEqual(result["state"], "failed")
        self.assertNotIn("verify", result["steps"])
        self.assertTrue(any(event["kind"] == "program.error" for event in runtime.read_events(run_dir)))

    def test_client_workspace_is_explicit_and_process_pwd_matches_cwd(self):
        command, _ = development.client_command("opencode", "Work", "worker", None, workspace=self.root)
        self.assertEqual(command[command.index("--dir") + 1], str(self.root))
        plan = {"goal": "Observe selected workspace", "work": [sys.executable, "-c",
            "import os; assert os.getcwd() == os.environ['PWD']; print(os.getcwd())"],
            "verify": [sys.executable, "-c", "pass"]}
        with patch.dict("os.environ", {"PWD": "/incorrect/invoking/directory"}), redirect_stdout(io.StringIO()):
            run_dir, result = runtime.run_plan(plan, self.root, self.root / "runs")
        self.assertEqual(result["state"], "awaiting_review")
        self.assertEqual((run_dir / "work.stdout.log").read_text().strip(), str(self.root))

    def test_read_only_inquiry_has_fresh_review_without_inventing_project_checks(self):
        roles, prompts = [], []
        def command(client, prompt, role, model, run_dir=None, workspace=None, context_dirs=()):
            roles.append(role)
            prompts.append(prompt)
            text = "P1 Observations: source facts. P2 Interpretation: hypothesis. P3 Judgment: uncertain. P4 Recommendation: inspect."
            if role == "reviewer":
                text = "ACCEPT\nCompared the report to the supplied sources."
            events = opencode(text, session=role)
            return [sys.executable, "-c", "print(" + repr("\n".join(json.dumps(event) for event in events)) + ")"], None
        with patch.object(development, "client_command", side_effect=command), redirect_stdout(io.StringIO()):
            run_dir, result = development.develop("Explain the sources", self.root, self.root / "runs", None, inquiry=True)
        self.assertEqual(result["state"], "accepted")
        self.assertEqual(roles, ["inquirer", "reviewer"])
        self.assertNotIn("verify", result["steps"])
        self.assertIn("not requested for read-only inquiry", prompts[-1])
        events = runtime.read_events(run_dir)
        self.assertTrue(any(e["kind"] == "verification.not_requested" for e in events))
        self.assertTrue(any(e["kind"] == "program.started" and e["data"]["program"] == "inquiry.reviewed/v1" for e in events))
        for client in ("opencode", "pi"):
            command, env = development.client_command(client, "Inquire", "inquirer", None)
            if client == "opencode":
                permission = json.loads(env["OPENCODE_CONFIG_CONTENT"])["agent"]["noetic-inquirer"]["permission"]
                self.assertNotIn("edit", permission)
                self.assertNotIn("bash", permission)
            else:
                self.assertIn("read,grep,find,ls", command)
        with self.assertRaises(ValueError):
            development.develop("Implement", self.root, self.root / "runs", None)

    def test_dependency_evidence_reaches_both_sessions_without_changing_task(self):
        plan = {"goal": "Prior work", "work": [sys.executable, "-c", "print('observed')"],
                "verify": [sys.executable, "-c", "print('checked')"]}
        with redirect_stdout(io.StringIO()):
            prior, _ = runtime.run_plan(plan, self.root, self.root / "prior")
        evidence = prior / "review.md"
        evidence.write_text("ACCEPT\nTest-authored evidence for prior work.")
        runtime.review_run(prior, "accept", "prior-reviewer", evidence)
        calls = []
        def command(client, prompt, role, model, run_dir=None, workspace=None, context_dirs=()):
            calls.append((role, prompt, context_dirs))
            text = "Used prior evidence." if role == "inquirer" else "ACCEPT\nCompared the prior observations."
            return [sys.executable, "-c", "print(" + repr("\n".join(json.dumps(e) for e in opencode(text, session=role))) + ")"], None
        with patch.object(development, "client_command", side_effect=command), redirect_stdout(io.StringIO()):
            run_dir, result = development.develop("Interpret prior work", self.root, self.root / "runs", None,
                inquiry=True, dependency_runs={"prior": str(prior)})
        self.assertEqual(result["state"], "accepted")
        self.assertEqual(result["goal"], "Interpret prior work")
        for role, prompt, context_dirs in calls:
            self.assertIn(str(prior), prompt)
            self.assertIn('"returncode": 0', prompt)
            self.assertIn("historical observations", prompt)
            self.assertEqual(context_dirs, (prior,))
        _, environment = development.client_command("opencode", "Read", "inquirer", None, context_dirs=(prior,))
        permissions = json.loads(environment["OPENCODE_CONFIG_CONTENT"])["agent"]["noetic-inquirer"]["permission"]
        self.assertEqual(permissions["external_directory"][str(prior) + "/**"], "allow")
        self.assertNotIn("edit", permissions)
        self.assertNotIn("bash", permissions)
        with redirect_stdout(io.StringIO()):
            failed, _ = runtime.run_plan({**plan, "work": [sys.executable, "-c", "raise SystemExit(1)"]}, self.root, self.root / "prior")
        with self.assertRaisesRegex(ValueError, "not accepted"):
            development.develop("Blocked", self.root, self.root / "not-created", None, inquiry=True,
                                dependency_runs={"failed": str(failed)})
        self.assertFalse((self.root / "not-created").exists())


if __name__ == "__main__":
    unittest.main()
