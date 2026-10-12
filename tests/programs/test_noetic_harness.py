"""Real SQLite and local protocol processes; no live model calls or delegated QA."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts import noetic_controller as controller
from scripts import noetic_harness as harness
from scripts import noetic_run as runtime


def result_for(state, verdict="pass"):
    activation = state["activations"][state["current_activation"]]
    if activation["mode"] == "review":
        return {"subject_artifact_id": activation["input_bindings"]["subject"], "verdict": verdict,
                "report": "Compared this subject to its explicit criteria.",
                "findings": [] if verdict == "pass" else [{"description": "A stated criterion is missing.", "blocking": True}]}
    schema = controller.result_contract(state)
    schema = schema.get("oneOf", [schema])[0]
    content = {name: [] if field["type"] == "array" else "Observed fixture evidence"
               for name, field in schema["properties"]["content"]["properties"].items()}
    return {"outcome": schema["properties"]["outcome"]["const"], "content": content}


def response_for(state, result=None):
    return {"result": result if result is not None else result_for(state),
            "session_ref": f"opencode:fixture-{state['current_activation']}"}


def protocol(text, client, session, reason="stop"):
    if client == "opencode":
        return [{"type": "text", "sessionID": session, "part": {"id": "text", "messageID": "final", "text": text}},
                {"type": "step_finish", "sessionID": session, "part": {"messageID": "final", "reason": reason}}]
    return [{"type": "session", "id": session}, {"type": "agent_end", "willRetry": False, "messages": [
        {"role": "assistant", "stopReason": reason, "content": [{"type": "text", "text": text}]}]}]


def process_command(events, prelude=""):
    return [sys.executable, "-c", "import sys; assert sys.stdin.read(); " + prelude + "print(" + repr("\n".join(json.dumps(e) for e in events)) + ")"], None


class HarnessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        subprocess.run(["git", "init", str(self.workspace)], check=True, capture_output=True)
        (self.workspace / "product.txt").write_text("baseline\n")
        self.runs = self.root / "runs"
        execute = harness._execute

        def no_live_models(run_dir, directory, workspace, name, argv, *args, **kwargs):
            if name == "actor" and Path(argv[0]).name in ("opencode", "pi"):
                raise AssertionError("Tests must replace live model commands")
            return execute(run_dir, directory, workspace, name, argv, *args, **kwargs)

        guard = patch.object(harness, "_execute", side_effect=no_live_models)
        guard.start()
        self.addCleanup(guard.stop)

    def start(self, pattern="development", **kwargs):
        options = {"verify": [sys.executable, "-c", "pass"]} if pattern == "development" else {}
        options.update(kwargs)
        with redirect_stdout(io.StringIO()):
            return harness.start(pattern, "Deliver the bounded task", self.workspace, self.runs,
                                 model="provider/model", **options)

    def reserved(self, state):
        return state["activations"][state["current_activation"]]

    def actor(self, run_dir, state, options):
        return response_for(state)

    def wait_for(self, condition):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.02)
        self.fail("Local process did not reach the expected checkpoint")

    def test_full_development_all_phases_remediate_with_actual_verification_and_fresh_protocol_sessions(self):
        calls = []

        def command(run_dir, state, options, prompt):
            activation = self.reserved(state)
            calls.append((activation.copy(), prompt))
            verdict = "fail" if activation["generation"] == 0 else "pass"
            result = result_for(state, verdict)
            prelude = ""
            if harness._implementation(activation):
                result["content"].update(changes=["invented-path"], verification=[{"returncode": 0, "claim": "passed"}])
                prelude = f"from pathlib import Path; Path('product.txt').write_text({str(activation['generation'])!r}); "
            if activation["mode"] == "review" and activation["phase"] == "implementation":
                subject = state["artifacts"][activation["input_bindings"]["subject"]]["content"]
                self.assertEqual(subject["verification"][0]["returncode"], 7 if activation["generation"] == 0 else 0)
                self.assertEqual([item["path"] for item in subject["changes"]], ["product.txt", "verification.txt"])
                self.assertIn('"returncode": 7' if activation["generation"] == 0 else '"returncode": 0', prompt)
            return process_command(protocol(json.dumps(result), options["client"], activation["id"]), prelude)

        verify = [sys.executable, "-c", "from pathlib import Path; print('real check'); "
                  "value = Path('product.txt').read_text(); Path('verification.txt').write_text(value); "
                  "raise SystemExit(0 if value == '1' else 7)"]
        with patch.object(harness, "actor_command", side_effect=command):
            run_dir, state = self.start(verify=verify, max_remediations=1)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(len(calls), 16)
        phases = [phase["id"] for phase in state["pattern"]["phases"]]
        self.assertEqual([a["phase"] for a, _ in calls], [phase for phase in phases for _ in range(4)])
        self.assertEqual([a["mode"] for a, _ in calls], ["produce", "review", "produce", "review"] * 4)
        self.assertEqual(len({a["session_ref"] for a in state["actors"].values()}), 16)
        for activation, prompt in calls:
            self.assertIn(activation["ordinal"], prompt)
            self.assertIn(activation["role"], prompt)
            self.assertIn("result_schema", prompt)
            directory = run_dir / "activations" / activation["id"]
            for name in ("prompt.txt", "actor.stdout.log", "actor.stderr.log", "actor-process.json",
                         "response.json", "final-response.txt", "model-result.json", "submission.json", "changes.json"):
                self.assertTrue((directory / name).exists(), name)
            if harness._implementation(activation):
                raw = json.loads((directory / "model-result.json").read_text())
                submitted = json.loads((directory / "submission.json").read_text())["result"]
                self.assertEqual(raw["content"]["changes"], ["invented-path"])
                self.assertNotEqual(raw["content"]["verification"], submitted["content"]["verification"])
        self.assertEqual(json.loads((run_dir / "controller.json").read_text()), state)
        self.assertEqual(harness.inspect(run_dir), state)
        events = runtime.read_events(run_dir)
        self.assertEqual([e["data"]["version"] for e in events if e["kind"] == "controller.state"], list(range(1, state["version"] + 1)))
        self.assertEqual([e["data"] for e in events if e["kind"] == "controller.event"], state["events"])
        self.assertEqual(runtime.project(events)["state"], "completed")
        self.assertFalse(any(e["kind"] == "review.recorded" for e in events))
        self.assertIn("development.implementation", (run_dir / "work.md").read_text())

    def test_cognitive_backedge_partial_feedback_and_rebuilt_bindings(self):
        visits = []

        def actor(run_dir, state, options):
            activation = self.reserved(state)
            visits.append((activation, harness.actor_prompt(run_dir, state)))
            if activation["phase"] == "P3" and not state["returns_used"]:
                return response_for(state, {"outcome": "return", "target": "P1", "reason": "Missing observation",
                                            "question": "Which observation distinguishes these?", "content": {"conditions": ["Unresolved"]}})
            return response_for(state)

        with patch.object(harness, "invoke_actor", side_effect=actor):
            run_dir, state = self.start("cognition")
        self.assertEqual(state["status"], "completed")
        self.assertEqual([a["phase"] for a, _ in visits], ["P1", "P2", "P3", "P1", "P2", "P3", "P4"])
        rebuilt, prompt = visits[3]
        self.assertEqual(rebuilt["visit"], 2)
        self.assertNotIn("effective.P1", rebuilt["input_bindings"])
        self.assertIn("Which observation distinguishes these?", prompt)
        self.assertIn("feedback_history", prompt)
        partial = next(a for a in state["artifacts"].values() if a["partial"])
        self.assertNotIn("judgment", partial["content"])
        self.assertEqual(partial["content"], {"conditions": ["Unresolved"]})
        old = visits[1][0]["input_bindings"]["effective.P1"]
        self.assertNotEqual(old, state["slots"]["effective.P1"])
        self.assertIn(old, state["artifacts"])
        self.assertEqual(runtime.project(runtime.read_events(run_dir))["state"], "completed")

    def test_exhausted_qa_and_cognitive_return_are_blocked_not_accepted(self):
        def actor(run_dir, state, options):
            if self.reserved(state)["mode"] == "review":
                return response_for(state, result_for(state, "fail"))
            if self.reserved(state)["phase"] == "P2":
                return response_for(state, {"outcome": "return", "target": "P1", "reason": "Missing data",
                                            "question": "What was observed?", "content": {"hypotheses": []}})
            return response_for(state)

        with patch.object(harness, "invoke_actor", side_effect=actor):
            for pattern in ("development", "cognition"):
                run_dir, state = self.start(pattern, max_remediations=0, max_returns=0)
                self.assertEqual(state["status"], "blocked")
                self.assertEqual(runtime.project(runtime.read_events(run_dir))["state"], "blocked")

    def test_checkpoint_ready_resume_and_frozen_options(self):
        calls = []

        def actor(run_dir, state, options):
            calls.append((state["current_activation"], options))
            return response_for(state)

        with patch.object(harness, "invoke_actor", side_effect=actor):
            run_dir, state = self.start("cognition", max_activations=1, thinking="high")
            frozen = (run_dir / "options.json").read_bytes()
            self.assertEqual(state["status"], "active")
            self.assertEqual(self.reserved(state)["status"], "ready")
            self.assertFalse(any(e["kind"] == "run.finished" for e in runtime.read_events(run_dir)))
            self.assertEqual(harness.drive(run_dir, 0)[1], state)
            _, state = harness.drive(run_dir)
        self.assertEqual(state["status"], "completed")
        self.assertEqual([a for a, _ in calls], [f"activation-{i}" for i in range(4)])
        self.assertEqual((run_dir / "options.json").read_bytes(), frozen)
        self.assertTrue(all(options["thinking"] == "high" for _, options in calls))
        with patch.object(harness, "invoke_actor") as actor:
            self.assertEqual(harness.drive(run_dir)[1], state)
            actor.assert_not_called()
        self.assertEqual(len([e for e in runtime.read_events(run_dir) if e["kind"] == "run.finished"]), 1)

    def test_missing_envelope_failure_and_completed_envelope_recovery(self):
        run_dir, state = self.start("cognition", max_activations=0)
        controller.begin_activation(run_dir / "controller.sqlite3", state["current_activation"], state["version"])
        with patch.object(harness, "invoke_actor") as actor:
            _, failed = harness.drive(run_dir)
        actor.assert_not_called()
        self.assertEqual(failed["status"], "failed")
        self.assertIn("runtime_uncertain", failed["reason"])

        verify = [sys.executable, "-c", "from pathlib import Path; "
                  "p = Path('checks.txt'); p.write_text(p.read_text() + 'check' if p.exists() else 'check')"]
        run_dir, state = self.start("cognition", max_activations=0, verify=verify)
        with patch.object(harness, "invoke_actor", side_effect=self.actor) as actor, \
                patch.object(controller, "submit_result", side_effect=RuntimeError("crash before delivery")):
            with self.assertRaisesRegex(RuntimeError, "crash before delivery"):
                harness.drive(run_dir, 1)
            self.assertEqual(actor.call_count, 1)
        running = harness.inspect(run_dir)
        envelope = json.loads((run_dir / "activations/activation-0/submission.json").read_text())
        self.assertEqual(self.reserved(running)["status"], "running")
        with patch.object(harness, "invoke_actor") as actor:
            _, recovered = harness.drive(run_dir, 0)
        actor.assert_not_called()
        self.assertEqual(self.reserved(recovered)["phase"], "P2")
        self.assertEqual((self.workspace / "checks.txt").read_text(), "check")
        self.assertEqual(controller.submit_result(run_dir / "controller.sqlite3", **envelope), recovered)
        self.assertEqual(harness.inspect(run_dir), recovered)

    def test_crash_after_actor_effect_is_uncertain_not_replayed(self):
        with patch.object(harness, "invoke_actor", side_effect=self.actor):
            run_dir, _ = self.start(max_activations=6)

        def crash(run_dir, state, options):
            (self.workspace / "product.txt").write_text("effect before crash")
            raise RuntimeError("after actor fault injection")

        with patch.object(harness, "invoke_actor", side_effect=crash), self.assertRaisesRegex(RuntimeError, "after actor"):
            harness.drive(run_dir)
        directory = run_dir / "activations/activation-6"
        self.assertTrue((directory / "changes.json").exists())
        self.assertFalse((directory / "submission.json").exists())
        with patch.object(harness, "invoke_actor") as actor:
            _, state = harness.drive(run_dir)
        actor.assert_not_called()
        self.assertEqual(state["status"], "failed")
        self.assertEqual((self.workspace / "product.txt").read_text(), "effect before crash")

    def test_crash_after_commit_exports_latest_authority_without_old_actor_replay(self):
        run_dir, _ = self.start("cognition", max_activations=0)
        submit = controller.submit_result

        def crash(*args, **kwargs):
            submit(*args, **kwargs)
            raise RuntimeError("after commit")

        with patch.object(harness, "invoke_actor", side_effect=self.actor), patch.object(controller, "submit_result", side_effect=crash):
            with self.assertRaisesRegex(RuntimeError, "after commit"):
                harness.drive(run_dir, 1)
        with patch.object(harness, "invoke_actor") as actor:
            _, state = harness.drive(run_dir, 0)
        actor.assert_not_called()
        self.assertEqual(self.reserved(state)["phase"], "P2")
        self.assertEqual(json.loads((run_dir / "controller.json").read_text()), state)

    def test_role_permissions_thinking_and_private_prompt_for_both_clients(self):
        run_dir, _ = self.start(max_activations=0)
        options = json.loads((run_dir / "options.json").read_text())
        options["qa_model"] = "provider/qa-model"
        phases = []

        def actor(run_dir, state, opts):
            phases.append(state)
            return response_for(state)

        with patch.object(harness, "invoke_actor", side_effect=actor):
            harness.drive(run_dir)
            self.start("cognition", max_activations=1)
        environment_before = dict(os.environ)
        for state in phases:
            activation = self.reserved(state)
            for client in ("opencode", "pi"):
                with self.subTest(phase=activation["phase"], mode=activation["mode"], client=client):
                    argv, env = harness.actor_command(run_dir, state, {**options, "client": client}, "Prompt -- with spaces")
                    self.assertNotIn("Prompt -- with spaces", argv)
                    self.assertNotIn("Prompt -- with spaces", json.dumps(env))
                    flag = "--variant" if client == "opencode" else "--thinking"
                    self.assertEqual(argv[argv.index(flag) + 1], "high")
                    self.assertEqual(argv[argv.index("--model") + 1], "provider/qa-model" if activation["mode"] == "review" else "provider/model")
                    for flag in ("--continue", "--resume", "--session"):
                        self.assertNotIn(flag, argv)
                    if client == "opencode":
                        agent = argv[argv.index("--agent") + 1]
                        permissions = json.loads(env["OPENCODE_CONFIG_CONTENT"])["agent"][agent]["permission"]
                        self.assertEqual(permissions["*"], "deny")
                        self.assertEqual(permissions.get("edit"), "allow" if harness._implementation(activation) else "deny")
                        self.assertEqual(permissions.get("bash"), "allow" if harness._implementation(activation) or activation["mode"] == "review" else None)
                    else:
                        tools = argv[argv.index("--tools") + 1].split(",")
                        self.assertEqual("edit" in tools, harness._implementation(activation))
                        self.assertEqual("write" in tools, harness._implementation(activation))
                        self.assertEqual("bash" in tools, harness._implementation(activation) or activation["mode"] == "review")
        self.assertEqual(dict(os.environ), environment_before)
        review_prompt = harness.actor_prompt(run_dir, phases[1])
        self.assertIn("do not demand future-phase implementation", review_prompt)
        self.assertIn("non-perfectionistic", review_prompt)
        self.assertIn("Do not delegate", review_prompt)

    def test_readonly_product_mutation_refused_and_not_reverted(self):
        for position, pattern in ((0, "development"), (1, "development"), (0, "cognition")):
            with patch.object(harness, "invoke_actor", side_effect=self.actor):
                run_dir, _ = self.start(pattern, max_activations=position)

            def mutating(run_dir, state, options):
                (self.workspace / "product.txt").write_text(f"changed by {run_dir.name}")
                return response_for(state)

            with patch.object(harness, "invoke_actor", side_effect=mutating):
                _, state = harness.drive(run_dir)
            self.assertEqual(state["status"], "failed")
            self.assertIn("Read-only actor changed product", state["reason"])
            self.assertEqual((self.workspace / "product.txt").read_text(), f"changed by {run_dir.name}")
            self.assertNotIn("accepted.design_intent", state["slots"])

    def test_run_bookkeeping_excluded_from_product_mutation_check(self):
        self.runs = self.workspace / "runs"
        with patch.object(harness, "invoke_actor", side_effect=self.actor):
            run_dir, state = self.start("cognition")
        self.assertEqual(state["status"], "completed")
        for directory in (run_dir / "activations").iterdir():
            manifest = json.loads((directory / "changes.json").read_text())
            self.assertEqual(manifest["changes"], [])

    def test_strict_single_object_parser(self):
        for text in ('{"outcome":"advance","content":{}}', '```json\n{"content":{}}\n```'):
            self.assertIsInstance(harness.parse_result(text), dict)
        for text in ('ACCEPT\n{}', '{} trailing', '{}\n{}', '[]', '{"a":',
                     '```\n{}\n```', '```json\n{}\n```\nprose', '{"a":NaN}', '{"a":1e999}', '{"a":1,"a":2}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                harness.parse_result(text)

    def test_protocol_final_json_and_sessions_with_errors_or_truncation_refused(self):
        for client in ("opencode", "pi"):
            for failure in (None, "length", "error", "prose", "truncated", "empty-session"):
                run_dir, state = self.start("cognition", client=client, max_activations=0)
                result = result_for(state)
                text = "```json\n" + json.dumps(result) + "\n```" if failure != "prose" else "ACCEPT\nAll good"
                events = protocol(text, client, "" if failure == "empty-session" else "fresh", "length" if failure == "length" else "stop")
                if failure == "error":
                    events += [{"type": "error"}]
                if failure == "truncated":
                    events += [{"type": "step_start", "sessionID": "fresh", "part": {"messageID": "unfinished"}}] if client == "opencode" else [{"type": "agent_start"}]
                with patch.object(harness, "actor_command", return_value=process_command(events)):
                    _, state = harness.drive(run_dir, 1)
                with self.subTest(client=client, failure=failure):
                    self.assertEqual(state["status"], "active" if failure is None else "failed")
                    if failure is None:
                        self.assertEqual(state["actors"]["actor-0"]["session_ref"], f"{client}:fresh")

    def test_execution_does_not_forward_development_sudo_password(self):
        run_dir, state = self.start("cognition", max_activations=0)
        events = protocol(json.dumps(result_for(state)), "opencode", "fresh-no-sudo")
        argv, _ = process_command(events, "import os; assert 'USER_PROVIDED_PASSWORD' not in os.environ; ")
        supplied = {**os.environ, "USER_PROVIDED_PASSWORD": "development-only-test-fixture"}
        with patch.object(harness, "actor_command", return_value=(argv, supplied)):
            _, state = harness.drive(run_dir, 1)
        self.assertEqual(state["status"], "active")
        self.assertEqual(supplied["USER_PROVIDED_PASSWORD"], "development-only-test-fixture")

    def test_kernel_refuses_wrong_subject_schema_and_session_reuse(self):
        for failure in ("subject", "schema", "session"):
            def actor(run_dir, state, options):
                response = response_for(state)
                if self.reserved(state)["mode"] == "review":
                    if failure == "subject":
                        response["result"]["subject_artifact_id"] = "artifact-wrong"
                    elif failure == "schema":
                        response["result"] = {"outcome": "pass"}
                    else:
                        response["session_ref"] = "opencode:fixture-activation-0"
                return response

            with patch.object(harness, "invoke_actor", side_effect=actor):
                _, state = self.start()
            self.assertEqual(state["status"], "failed")
            self.assertIn("Result refused", state["reason"])
            self.assertNotIn("accepted.design_intent", state["slots"])

    def test_process_start_failure_nonzero_and_timeout_are_recorded(self):
        for argv, timeout in ((["/no-such-noetic-fixture-executable"], 5),
                              ([sys.executable, "-c", "raise SystemExit(6)"], 5),
                              ([sys.executable, "-c", "import time; time.sleep(30)"], 0.1)):
            run_dir, _ = self.start("cognition", max_activations=0, timeout=timeout)
            with patch.object(harness, "actor_command", return_value=(argv, None)):
                _, state = harness.drive(run_dir)
            self.assertEqual(state["status"], "failed")
            observation = json.loads((run_dir / "activations/activation-0/actor-process.json").read_text())
            self.assertIn(observation["state"], ("failed", "timed_out"))
            self.assertTrue(any(e["kind"] == "step.finished" for e in runtime.read_events(run_dir)))

    def test_cancel_and_cooperative_lock_stop_real_process(self):
        run_dir, _ = self.start("cognition", max_activations=0)
        argv = [sys.executable, "-c", "import time; time.sleep(30)"]
        with patch.object(harness, "actor_command", return_value=(argv, None)), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(harness.drive, run_dir)
            self.wait_for(lambda: any(e["kind"] == "step.started" for e in runtime.read_events(run_dir)))
            pid = next(e["data"]["pid"] for e in runtime.read_events(run_dir) if e["kind"] == "step.started")
            with self.assertRaises(harness.DriverBusy):
                harness.drive(run_dir)
            harness.cancel(run_dir)
            _, state = future.result(timeout=8)
        self.assertEqual(state["status"], "cancelled")
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        self.assertEqual(harness.cancel(run_dir), state)
        self.assertEqual(runtime.project(runtime.read_events(run_dir))["state"], "cancelled")
        self.assertEqual(json.loads((run_dir / "activations/activation-0/actor-process.json").read_text())["state"], "cancelled")

    def test_sigterm_and_ctrl_c_cancel_callable_driver_and_reap_group(self):
        for signum in (signal.SIGTERM, signal.SIGINT):
            run_dir, _ = self.start("cognition", max_activations=0)
            child_code = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); time.sleep(30)"
            script = ("from pathlib import Path; import sys; from scripts import noetic_harness as h; "
                      f"h.actor_command=lambda *args: ([sys.executable, '-c', {child_code!r}], None); "
                      f"h.drive(Path({str(run_dir)!r}))")
            process = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                self.wait_for(lambda: any(e["kind"] == "step.started" for e in runtime.read_events(run_dir)))
                pid = next(e["data"]["pid"] for e in runtime.read_events(run_dir) if e["kind"] == "step.started")
                process.send_signal(signum)
                _, error = process.communicate(timeout=8)
                self.assertEqual(process.returncode, 0, error.decode())
                self.assertEqual(harness.inspect(run_dir)["status"], "cancelled")
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()

    def test_cancel_paused_run_and_optional_cognitive_verify(self):
        run_dir, _ = self.start("cognition", max_activations=0)
        self.assertEqual(harness.cancel(run_dir)["status"], "cancelled")
        with patch.object(harness, "invoke_actor") as actor:
            harness.drive(run_dir)
        actor.assert_not_called()
        with patch.object(harness, "invoke_actor", side_effect=self.actor):
            run_dir, state = self.start("cognition", max_activations=1, verify=[sys.executable, "-c", "raise SystemExit(4)"])
        content = state["artifacts"][state["slots"]["effective.P1"]]["content"]
        self.assertEqual(content["runtime_verification"][0]["returncode"], 4)
        self.assertEqual(state["status"], "active")

    def test_cli_checkpoint_inspect_and_validation(self):
        task = self.root / "task.txt"
        task.write_text("Inspect the explicit task")
        with redirect_stdout(io.StringIO()):
            result = harness.main(["start", "cognition", str(task), "--workspace", str(self.workspace),
                                   "--runs-dir", str(self.runs), "--max-activations", "0", "--thinking", "high"])
        self.assertEqual(result, 2)
        run_dir = next(self.runs.iterdir())
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(harness.main(["inspect", str(run_dir), "--json"]), 0)
        self.assertEqual(json.loads(output.getvalue()), harness.inspect(run_dir))
        automatic, state = self.start(verify=None, max_activations=0)
        self.assertEqual(state["status"], "active")
        self.assertEqual(json.loads((automatic / "options.json").read_text())["verification_mode"], "worker-selected")
        with self.assertRaises(ValueError):
            self.start("cognition", max_activations=-1)
        self.assertTrue((run_dir / "controller.sqlite3").is_file())


if __name__ == "__main__":
    unittest.main()
