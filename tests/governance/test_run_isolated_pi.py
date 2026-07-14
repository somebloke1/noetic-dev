"""Tests for the Pi isolation dispatcher policy surface."""

from __future__ import annotations

import argparse
import inspect
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
GOV_SCRIPTS = str(ROOT / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

import run_isolated_pi as isolated_pi  # noqa: E402
from run_isolated_pi import (  # noqa: E402
    PI_JSONL_EVENT_TYPES,
    QA_TOOL_ALLOWLIST,
    ROLE_TOOL_ALLOWLISTS,
    _candidate_git_metadata_ro_mounts,
    _claim_decision_id,
    _clean_env,
    _credential_interface,
    _non_evidence_record,
    _pi_models_config,
    _write_tools_observed,
    build_bwrap_command,
    main,
    materialize_candidate_checkout,
    parse_pi_jsonl_final_assistant,
    resolve_scoped_credentials,
    run_routed_pi_lifecycle,
    validate_candidate_checkout,
    validate_model,
    validate_tools,
)

SOL = "codex/gpt-5.6-sol"
TERRA = "codex/gpt-5.6-terra"
LUNA = "codex/gpt-5.6-luna"


def model_ref(model: str) -> dict[str, str]:
    return {
        "model_id": model,
        "endpoint_id": "local-litellm",
        "upstream_model_id": model,
        "interface_type": "openai-compatible",
        "base_url": "http://172.22.10.160:3333",
        "endpoint_path": "/v1/responses",
        "token_env": "LITELLM_API_KEY",
        "reasoning_effort": "high",
    }


def decision(model: str = TERRA, number: int = 1) -> dict[str, object]:
    order = [TERRA, SOL, LUNA]
    remaining = order[order.index(model):]
    return {
        "availability": "verified",
        "decision_id": f"d-20260713-{number:06d}",
        "effective_complexity": "complex",
        "fable_eligible": False,
        "fallback_refs": [model_ref(item) for item in remaining[1:]],
        "fallbacks": remaining[1:],
        "genus": "Complex Code Review",
        "genus_code": "REVIEW-COMPLEX",
        "model": model,
        "model_ref": model_ref(model),
        "rationale": ["protected authoritative QA fixture"],
        "sophistication": "complex",
    }


def assistant_message(text: str) -> dict[str, object]:
    return {
        "role": "assistant",
        "content": [{"type": "thinking", "thinking": "bounded"}, {"type": "text", "text": text}],
        "stopReason": "stop",
        "provider": "local-litellm",
        "model": TERRA,
        "usage": {"input": 1, "output": 1, "cost": {"total": 0}},
        "timestamp": 1,
    }


def pi_jsonl(text: str) -> str:
    message = assistant_message(text)
    events = [
        {"type": "session", "version": 3, "id": "session-fixture", "timestamp": "2026-07-14T00:00:00Z", "cwd": "/tmp/scratch"},
        {"type": "agent_start"},
        {"type": "turn_start"},
        {"type": "message_start", "message": {"role": "assistant", "content": []}},
        {"type": "message_end", "message": message},
        {"type": "turn_end", "message": message},
        {"type": "agent_end", "messages": [{"role": "user", "content": "prompt"}, message], "willRetry": False},
    ]
    return "".join(json.dumps(event, separators=(",", ":")) + "\n" for event in events)


class FakeService:
    def __init__(self, decisions: list[dict[str, object]], report_result=None) -> None:
        self.decisions = list(decisions)
        self.inputs: list[dict[str, object]] = []
        self.outcomes: list[dict[str, object]] = []
        self.report_result = report_result

    async def route_task(self, payload):
        self.inputs.append(payload)
        return self.decisions.pop(0)

    def report_outcome(self, payload):
        self.outcomes.append(payload)
        return self.report_result if self.report_result is not None else {"recorded": True}


class TestRunIsolatedPiPolicy(unittest.TestCase):
    _decision_counter = 1000

    @classmethod
    def next_decision(cls, model: str = TERRA):
        cls._decision_counter += 1
        return decision(model, cls._decision_counter)

    @unittest.skipUnless(shutil.which("pi"), "Pi 0.80.3 is required")
    def test_installed_pi_0803_contract_explicitly_disables_tools_and_parses_file_arg(self):
        pi = shutil.which("pi")
        self.assertIsNotNone(pi)
        version = subprocess.run([pi, "--version"], capture_output=True, text=True, check=True).stdout.strip()
        help_text = subprocess.run([pi, "--help"], capture_output=True, text=True, check=True).stdout
        self.assertEqual(version, "0.80.3")
        self.assertIn("--no-tools, -nt", help_text)
        cli_js = Path(pi).resolve()
        args_module = cli_js.parent / "cli" / "args.js"
        script = (
            f'import {{parseArgs}} from {json.dumps(args_module.as_uri())};'
            'console.log(JSON.stringify(parseArgs(["--no-tools","@/tmp/prompt.md"])));'
        )
        parsed = json.loads(subprocess.run(
            ["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True
        ).stdout)
        self.assertIs(parsed["noTools"], True)
        self.assertEqual(parsed["fileArgs"], ["/tmp/prompt.md"])
        self.assertEqual(parsed["messages"], [])

    def test_only_public_routed_lifecycle_holds_authority(self):
        self.assertTrue(callable(run_routed_pi_lifecycle))
        self.assertIsNone(run_routed_pi_lifecycle.__closure__)
        for name in [
            "_CAPABILITY_MARKER", "_ACTIVE_CAPABILITIES", "_mint_routed_invocation",
            "_consume_routed_invocation", "_run_isolated", "dispatch_pi", "run_ready_probe",
            "_route_and_run_pi", "_make_routed_pi_lifecycle", "_worker_lifecycle",
        ]:
            self.assertFalse(hasattr(isolated_pi, name), name)
        parameters = inspect.signature(build_bwrap_command).parameters
        self.assertNotIn("decision", parameters)
        self.assertNotIn("route_evidence", parameters)
        self.assertNotIn("api_key", parameters)

    def test_public_lifecycle_crosses_fresh_isolated_worker_process(self):
        captured = {}

        def run(command, **kwargs):
            captured["command"] = command
            captured["env"] = kwargs["env"]
            Path(command[-1]).write_text(json.dumps({
                "probe_record": None,
                "execution_record": {"actual_invocation": {"authority_process": "fresh-isolated-worker"}},
                "stdout": "events",
                "stderr": "",
            }), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = root / "prompt.md"
            prompt.write_text("Review", encoding="utf-8")
            with mock.patch("run_isolated_pi.subprocess.run", side_effect=run):
                result = run_routed_pi_lifecycle(
                    role="validator", run_id="run", role_run_id="validator-1", tools=[],
                    prompt_file=prompt, candidate_dir=None, qa_for_pass_id=None,
                    candidate_sha="d" * 40, base_sha="c" * 40, candidate_tree_oid="",
                    timeout=1, decision_claim_dir=root / "claims",
                )
        self.assertEqual(captured["command"][1], "-I")
        self.assertEqual(captured["command"][3], "--routed-worker")
        self.assertEqual(result.execution_record["actual_invocation"]["authority_process"], "fresh-isolated-worker")
        self.assertNotIn("UNRELATED_SECRET", captured["env"])

    def test_cross_process_decision_claim_is_atomic_and_durable(self):
        with tempfile.TemporaryDirectory() as directory:
            claim_dir = Path(directory) / "claims"
            _claim_decision_id(claim_dir, "d-20260713-999991")
            with self.assertRaisesRegex(RuntimeError, "replayed"):
                _claim_decision_id(claim_dir, "d-20260713-999991")
            script = (
                "import sys; from pathlib import Path; "
                f"sys.path.insert(0,{str(GOV_SCRIPTS)!r}); "
                "from run_isolated_pi import _claim_decision_id; "
                f"_claim_decision_id(Path({str(claim_dir)!r}), 'd-20260713-999991')"
            )
            child = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        self.assertNotEqual(child.returncode, 0)
        self.assertIn("replayed", child.stderr)

    def test_decision_claim_rejects_pathlike_or_malformed_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            claim_dir = Path(directory) / "claims"
            for decision_id in ["../escape", "/tmp/escape", "d-20260713-1", ""]:
                with self.subTest(decision_id=decision_id), self.assertRaisesRegex(
                    RuntimeError, "unsafe"
                ):
                    _claim_decision_id(claim_dir, decision_id)

    def test_helper_children_receive_scrubbed_environments(self):
        calls = []

        def run(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0, "0.80.3\n" if command[0] == "pi" else "a" * 40 + "\n", "")

        with mock.patch.dict(os.environ, {"UNRELATED_SECRET": "sentinel"}, clear=False), \
                mock.patch("run_isolated_pi.subprocess.run", side_effect=run):
            isolated_pi.get_pi_version()
            isolated_pi.get_policy_sha()
        self.assertEqual(len(calls), 2)
        for _command, kwargs in calls:
            self.assertIn("env", kwargs)
            self.assertNotIn("UNRELATED_SECRET", kwargs["env"])
            self.assertNotIn("LITELLM_API_KEY", kwargs["env"])

    def test_parser_extracts_one_final_assistant_text(self):
        self.assertEqual(parse_pi_jsonl_final_assistant(pi_jsonl("READY abc123def4567890")), "READY abc123def4567890")
        self.assertIn("session", PI_JSONL_EVENT_TYPES)
        self.assertIn("agent_end", PI_JSONL_EVENT_TYPES)

    def test_parser_rejects_malformed_nonfinite_unknown_ambiguous_and_tool_outputs(self):
        cases = [
            "not-json\n",
            '{"type":"agent_start","x":NaN}\n',
            '{"type":"future_relevant_event"}\n',
            pi_jsonl("one") + pi_jsonl("two"),
            json.dumps({"type": "tool_execution_start", "toolName": "write"}) + "\n",
        ]
        duplicate = pi_jsonl("ok").replace('{"type":"agent_start"}', '{"type":"agent_start","type":"agent_start"}', 1)
        cases.append(duplicate)
        for stream in cases:
            with self.subTest(stream=stream[:60]), self.assertRaises(RuntimeError):
                parse_pi_jsonl_final_assistant(stream)

    def test_qa_tool_allowlist_is_empty_and_fails_before_routing(self):
        self.assertEqual(QA_TOOL_ALLOWLIST, set())
        ok, message, _tools = validate_tools("qa", "read")
        self.assertFalse(ok)
        self.assertIn("cannot use tools", message)

    @unittest.skipUnless(shutil.which("bwrap") or shutil.which("bubblewrap"), "bubblewrap is required")
    def test_bwrap_copies_actual_held_config_fd_payload_read_only(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            node_prefix = root / "node" / "v24.0.0"
            pi_bin = node_prefix / "bin" / "pi"
            pi_bin.parent.mkdir(parents=True)
            pi_bin.write_text("#!/bin/sh\n", encoding="utf-8")
            with tempfile.TemporaryFile() as prompt, tempfile.TemporaryFile() as config:
                prompt.write(b"prompt")
                prompt.seek(0)
                config.write(b'{"sentinel":"exact-config"}')
                config.seek(0)
                with mock.patch("run_isolated_pi.shutil.which", side_effect=lambda name: "/usr/bin/bwrap" if name == "bwrap" else str(pi_bin)):
                    command = build_bwrap_command(
                        ["/bin/sh", "-c", "test ! -w /tmp/pi-agent/models.json && cat /tmp/pi-agent/models.json"],
                        candidate_dir=None,
                        prompt_fd=prompt.fileno(),
                        cwd=None,
                        pi_config_fd=config.fileno(),
                    )
                result = subprocess.run(
                    command, pass_fds=(prompt.fileno(), config.fileno()), capture_output=True, text=True
                )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '{"sentinel":"exact-config"}')
        self.assertIn("--ro-bind-data", command)

    def test_direct_provider_credentials_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "direct provider credential"):
            _clean_env({"OPENAI_API_KEY": "secret"})

    def test_exact_generated_config_has_one_canonical_provider_and_model(self):
        config = _pi_models_config(model_ref(TERRA))
        self.assertEqual(list(config["providers"]), ["local-litellm"])
        self.assertEqual(config["providers"]["local-litellm"]["models"][0]["id"], TERRA)
        malformed = model_ref(TERRA)
        malformed["endpoint_path"] = "/v1/chat/completions"
        with self.assertRaisesRegex(RuntimeError, "Responses endpoint"):
            _pi_models_config(malformed)

    def test_scoped_credentials_and_interface_remain_bounded(self):
        ok, message, creds = resolve_scoped_credentials(["GH_TOKEN"])
        self.assertFalse(ok)
        self.assertEqual(creds, {})
        self.assertIn("not an allowed provider credential", message)
        interface = _credential_interface({"LITELLM_API_KEY": "secret"}, [], "qa")
        self.assertTrue(interface["tools_disabled_for_authoritative_qa"])
        self.assertFalse(interface["available_to_tools"])

    def test_model_and_role_policy_surfaces_remain_fail_closed(self):
        ok, message = validate_model("unsupported/model")
        self.assertFalse(ok)
        self.assertIn("not in allowed profiles", message)
        self.assertNotIn("implementer", ROLE_TOOL_ALLOWLISTS)
        self.assertNotIn("remediator", ROLE_TOOL_ALLOWLISTS)

    def test_write_tool_observation_is_derived_from_events(self):
        self.assertTrue(_write_tools_observed('{"tool_name":"write"}\n'))
        self.assertFalse(_write_tools_observed('{"tool_name":"read"}\n'))

    def test_cli_rejects_static_model_authorization_for_real_execution(self):
        argv = [
            "run_isolated_pi.py", "--run-id", "run-1", "--role", "qa",
            "--role-run-id", "qa-1", "--model", TERRA, "--prompt", "unused",
        ]
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", argv), mock.patch("sys.stderr", stderr):
            self.assertEqual(main(), 1)
        self.assertIn("cannot authorize routed Pi execution", stderr.getvalue())

    def _init_candidate_repo(self, root: Path) -> str:
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
        (root / "tracked.txt").write_text("clean\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True)
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()

    def _commit_file(self, root: Path, relative_path: str, content: str, message: str) -> str:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", relative_path], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", message], cwd=root, check=True, capture_output=True)
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()

    def test_validate_candidate_checkout_requires_clean_git_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._init_candidate_repo(root)
            expected_tree = subprocess.check_output(["git", "rev-parse", f"{sha}^{{tree}}"], cwd=root, text=True).strip()
            ok, message, tree = validate_candidate_checkout(root, sha)
            self.assertTrue(ok, message)
            self.assertEqual(tree, expected_tree)

            (root / "tracked.txt").write_text("dirty\n", encoding="utf-8")
            ok, message, _tree = validate_candidate_checkout(root, sha)
            self.assertFalse(ok)
            self.assertIn("dirty or has untracked files", message)

    def test_validate_candidate_checkout_rejects_untracked_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._init_candidate_repo(root)
            (root / "untracked.txt").write_text("untracked\n", encoding="utf-8")
            ok, message, _tree = validate_candidate_checkout(root, sha)
            self.assertFalse(ok)
            self.assertIn("dirty or has untracked files", message)

    def test_validate_candidate_checkout_rejects_ignored_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_candidate_repo(root)
            sha = self._commit_file(root, ".gitignore", "ignored.log\n", "ignore logs")
            (root / "ignored.log").write_text("ignored but visible\n", encoding="utf-8")
            ok, message, _tree = validate_candidate_checkout(root, sha)
            self.assertFalse(ok)
            self.assertIn("ignored untracked entries", message)
            self.assertIn("ignored.log", message)

    def test_validate_candidate_checkout_rejects_assume_unchanged_modified_tracked_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._init_candidate_repo(root)
            subprocess.run(["git", "update-index", "--assume-unchanged", "tracked.txt"], cwd=root, check=True)
            (root / "tracked.txt").write_text("hidden dirty\n", encoding="utf-8")
            ok, message, _tree = validate_candidate_checkout(root, sha)
            self.assertFalse(ok)
            self.assertIn("assume-unchanged or skip-worktree", message)
            self.assertIn("tracked.txt", message)

    def test_validate_candidate_checkout_rejects_skip_worktree_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._init_candidate_repo(root)
            subprocess.run(["git", "update-index", "--skip-worktree", "tracked.txt"], cwd=root, check=True)
            ok, message, _tree = validate_candidate_checkout(root, sha)
            self.assertFalse(ok)
            self.assertIn("assume-unchanged or skip-worktree", message)
            self.assertIn("tracked.txt", message)

    @unittest.skipUnless(shutil.which("bwrap") or shutil.which("bubblewrap"), "bubblewrap is required")
    def test_materialize_candidate_checkout_creates_private_verified_tree(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as private_tmp:
            root = Path(tmp)
            sha = self._init_candidate_repo(root)
            expected_tree = subprocess.check_output(["git", "rev-parse", f"{sha}^{{tree}}"], cwd=root, text=True).strip()
            private_dir, private_tree = materialize_candidate_checkout(root, sha, Path(private_tmp))
            self.assertNotEqual(private_dir.resolve(), root.resolve())
            self.assertEqual(private_tree, expected_tree)
            ok, message, tree = validate_candidate_checkout(private_dir, sha)
            self.assertTrue(ok, message)
            self.assertEqual(tree, expected_tree)

            (root / "tracked.txt").write_text("source mutated after materialization\n", encoding="utf-8")
            self.assertEqual((private_dir / "tracked.txt").read_text(encoding="utf-8"), "clean\n")

    @unittest.skipUnless(shutil.which("bwrap") or shutil.which("bubblewrap"), "bubblewrap is required")
    def test_materialize_candidate_checkout_revalidates_source_inside_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as private_tmp:
            root = Path(tmp)
            sha = self._init_candidate_repo(root)
            (root / "untracked.txt").write_text("late mutation\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "untracked files"):
                materialize_candidate_checkout(root, sha, Path(private_tmp))

    @unittest.skipUnless(shutil.which("bwrap") or shutil.which("bubblewrap"), "bubblewrap is required")
    def test_materialize_candidate_checkout_confines_core_fsmonitor(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as private_tmp:
            base = Path(tmp)
            root = base / "candidate"
            root.mkdir()
            sha = self._init_candidate_repo(root)
            marker = base / "host-fsmonitor-marker"
            callback = base / "fsmonitor.sh"
            callback.write_text(f"#!/bin/sh\nprintf marker > {marker}\nexit 0\n", encoding="utf-8")
            callback.chmod(0o755)
            subprocess.run(["git", "config", "core.fsmonitor", str(callback)], cwd=root, check=True)

            expected_tree = subprocess.check_output(["git", "rev-parse", f"{sha}^{{tree}}"], cwd=root, text=True).strip()
            private_dir, private_tree = materialize_candidate_checkout(root, sha, Path(private_tmp))

            self.assertFalse(marker.exists(), "source-local core.fsmonitor escaped bootstrap confinement")
            self.assertEqual(private_tree, expected_tree)
            ok, message, tree = validate_candidate_checkout(private_dir, sha)
            self.assertTrue(ok, message)
            self.assertEqual(tree, expected_tree)

    @unittest.skipUnless(shutil.which("bwrap") or shutil.which("bubblewrap"), "bubblewrap is required")
    def test_materialize_candidate_checkout_does_not_execute_uploadpack_hook_on_host(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as private_tmp:
            base = Path(tmp)
            root = base / "candidate"
            root.mkdir()
            sha = self._init_candidate_repo(root)
            marker = base / "host-uploadpack-marker"
            hook = base / "pack-objects-hook.sh"
            hook.write_text(
                "#!/bin/sh\n"
                f"printf marker > {marker}\n"
                "exec git pack-objects \"$@\"\n",
                encoding="utf-8",
            )
            hook.chmod(0o755)
            subprocess.run(["git", "config", "uploadpack.packObjectsHook", str(hook)], cwd=root, check=True)

            expected_tree = subprocess.check_output(["git", "rev-parse", f"{sha}^{{tree}}"], cwd=root, text=True).strip()
            private_dir, private_tree = materialize_candidate_checkout(root, sha, Path(private_tmp))

            self.assertFalse(marker.exists(), "source-local uploadpack.packObjectsHook escaped bootstrap confinement")
            self.assertEqual(private_tree, expected_tree)
            ok, message, tree = validate_candidate_checkout(private_dir, sha)
            self.assertTrue(ok, message)
            self.assertEqual(tree, expected_tree)

    @unittest.skipUnless(shutil.which("bwrap") or shutil.which("bubblewrap"), "bubblewrap is required")
    def test_materialize_candidate_checkout_does_not_execute_source_smudge_filter(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as private_tmp:
            base = Path(tmp)
            root = base / "candidate"
            root.mkdir()
            marker = Path(private_tmp) / "filter-marker"
            filter_script = root / "hostile-filter.sh"
            filter_script.write_text(
                "#!/bin/sh\n"
                f"printf marker > {marker}\n"
                "cat\n",
                encoding="utf-8",
            )
            filter_script.chmod(0o755)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
            subprocess.run(["git", "config", "filter.hostile.smudge", str(filter_script)], cwd=root, check=True)
            (root / ".gitattributes").write_text("payload.txt filter=hostile\n", encoding="utf-8")
            (root / "payload.txt").write_text("payload\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitattributes", "payload.txt", "hostile-filter.sh"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "add filtered payload"], cwd=root, check=True, capture_output=True)
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()

            private_dir, _private_tree = materialize_candidate_checkout(root, sha, Path(private_tmp))

            self.assertFalse(marker.exists(), "source-local smudge filter executed during materialization")
            self.assertEqual((private_dir / "payload.txt").read_text(encoding="utf-8"), "payload\n")

    @unittest.skipUnless(shutil.which("bwrap") or shutil.which("bubblewrap"), "bubblewrap is required")
    def test_materialize_candidate_checkout_does_not_execute_source_process_filter(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as private_tmp:
            base = Path(tmp)
            root = base / "candidate"
            root.mkdir()
            marker = Path(private_tmp) / "process-filter-marker"
            filter_script = root / "hostile-process-filter.sh"
            filter_script.write_text(
                "#!/bin/sh\n"
                "while read line; do\n"
                f"  printf marker > {marker}\n"
                "  case \"$line\" in\n"
                "    command=*) printf 'status=success\\n\\n' ;;\n"
                "    '') printf '\\n' ;;\n"
                "  esac\n"
                "done\n",
                encoding="utf-8",
            )
            filter_script.chmod(0o755)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
            (root / ".gitattributes").write_text("payload.txt filter=hostile\n", encoding="utf-8")
            (root / "payload.txt").write_text("payload\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitattributes", "payload.txt", "hostile-process-filter.sh"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "add process filtered payload"], cwd=root, check=True, capture_output=True)
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            subprocess.run(["git", "config", "filter.hostile.process", str(filter_script)], cwd=root, check=True)

            private_dir, _private_tree = materialize_candidate_checkout(root, sha, Path(private_tmp))

            self.assertFalse(marker.exists(), "source-local process filter executed during materialization")
            self.assertEqual((private_dir / "payload.txt").read_text(encoding="utf-8"), "payload\n")

    def test_candidate_git_metadata_mounts_exclude_git_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            common = base / "repo" / ".git"
            gitdir = common / "worktrees" / "candidate"
            candidate = base / "candidate"
            gitdir.mkdir(parents=True)
            (common / "objects").mkdir(parents=True)
            (common / "refs").mkdir()
            candidate.mkdir()
            (candidate / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
            (gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (gitdir / "index").write_bytes(b"DIRC")
            (gitdir / "commondir").write_text("../..\n", encoding="utf-8")
            (gitdir / "gitdir").write_text(f"{candidate / '.git'}\n", encoding="utf-8")
            (common / "config").write_text("[filter \"hostile\"]\n", encoding="utf-8")

            mounts = _candidate_git_metadata_ro_mounts(candidate)

            self.assertIn(gitdir / "HEAD", mounts)
            self.assertIn(gitdir / "index", mounts)
            self.assertIn(common / "objects", mounts)
            self.assertNotIn(gitdir, mounts)
            self.assertNotIn(common, mounts)
            self.assertNotIn(common / "config", mounts)

    def test_candidate_git_metadata_rejects_unowned_commondir(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            common = base / "repo" / ".git"
            gitdir = common / "worktrees" / "candidate"
            candidate = base / "candidate"
            gitdir.mkdir(parents=True)
            candidate.mkdir()
            (candidate / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
            (gitdir / "commondir").write_text(str(base), encoding="utf-8")
            (gitdir / "gitdir").write_text(f"{candidate / '.git'}\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "external commondir"):
                _candidate_git_metadata_ro_mounts(candidate)

    def test_candidate_git_metadata_rejects_foreign_worktree_backlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            common = base / "victim" / ".git"
            gitdir = common / "worktrees" / "victim-worktree"
            candidate = base / "impostor"
            victim = base / "victim-worktree"
            gitdir.mkdir(parents=True)
            candidate.mkdir()
            victim.mkdir()
            (candidate / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
            (gitdir / "gitdir").write_text(f"{victim / '.git'}\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "backlink does not identify candidate"):
                _candidate_git_metadata_ro_mounts(candidate)

    def test_record_only_is_non_evidence(self):
        args = argparse.Namespace(
            run_id="run-1",
            role="qa",
            role_run_id="qa-run-1",
            qa_for_pass_id="impl-1",
            model="openai-codex/gpt-5.6-terra",
            candidate_sha="d" * 40,
            base_sha="c" * 40,
        )
        record = _non_evidence_record(args, "qa_primary", ["read"])
        self.assertTrue(record["record_only"])
        self.assertEqual(record["evidence_class"], "non-evidence")
        self.assertNotEqual(record["actual_invocation"]["exit_code"], None)


if __name__ == "__main__":
    unittest.main()
