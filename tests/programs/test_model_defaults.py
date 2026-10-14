"""Installation defaults and native provider registration, without model inference."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from scripts import noetic_model_defaults as models
from scripts import noetic_develop as develop
from scripts.noetic_opermem_application import ReviewedApplication
from types import SimpleNamespace
from contextlib import nullcontext


class ModelDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.node = shutil.which("node")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "local.json"
        self.pi = self.root / "pi"
        self.pi.mkdir()
        self.secret = "owned-fixture-key-not-a-credential"
        self.pi_models = self.pi / "models.json"
        self.pi_models.write_text(json.dumps({"providers": {"llama.cpp": {"apiKey": self.secret}}}))
        self.data = {"product": {"client": "pi", "model": "noetic-local/qwen3.6-a3b", "thinking": "off",
            "provider": {"name": "noetic-local", "base_url": "http://127.0.0.1:8742/v1",
                "api": "openai-completions", "api_key_provider": "llama.cpp", "context_window": 57344,
                "max_tokens": 4096, "input": ["text", "image"], "reasoning": False}}}
        self.config.write_text(json.dumps(self.data))
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"NOETIC_LOCAL_CONFIG": str(self.config), "PI_CODING_AGENT_DIR": str(self.pi)}, clear=True).start()

    def test_nonstring_choices_refuse_before_fallback(self):
        for field in ("client", "model", "qa_model", "thinking"):
            for value in (42, [], {}):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    models.new_options(**{field: value})

    def test_unconfigured_parent_model_before_legacy(self):
        self.config.write_text('{"inference":{}}')
        selected = models.new_options(parent={"model":"old-parent/model", "thinking":"low"}, legacy_model="legacy/default")
        self.assertEqual(selected["model"], "old-parent/model")
        self.assertEqual(selected["thinking"], "low")
        self.assertIsNone(selected["qa_model"])

    def test_cold_registration_cache_concurrent_writers(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        barrier = threading.Barrier(2)
        replace = os.replace
        def simultaneous(source, target):
            barrier.wait(timeout=5)
            return replace(source, target)
        directory = self.root / "cold-shared"
        with patch.object(models.os, "replace", side_effect=simultaneous):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(models.pi_launch, "noetic-local/qwen3.6-a3b", directory, {}) for _ in range(2)]
                values = [future.result(timeout=8) for future in futures]
        self.assertEqual(values[0][0], values[1][0])
        self.assertEqual((directory / "noetic-model-provider.mjs").read_text(), models.EXTENSION_SOURCE)
        self.assertEqual(list(directory.glob("*.tmp")), [])

    def test_native_model_compat_and_credential_reference_pass_through(self):
        reference = "$OWNED_NATIVE_KEY"
        self.pi_models.write_text(json.dumps({"providers":{"llama.cpp":{"apiKey":reference}}}))
        extra, environment = models.pi_launch("noetic-local/qwen3.6-a3b", self.root/"registration", {})
        script = """let registration;const m=await import(process.argv[1]);await m.default({registerProvider:(name,config)=>registration=config});const model=registration.models[0];if(model.compat?.maxTokensField!=='max_tokens'||model.compat?.supportsStore!==false||model.compat?.supportsDeveloperRole!==false||model.compat?.supportsReasoningEffort!==false)throw Error('model compatibility missing');if(registration.apiKey!==process.env.NOETIC_MODEL_PROVIDER_API_KEY_REF)throw Error('native credential reference altered');"""
        self.assertIsNotNone(self.node, "Node must be available on PATH before fixture isolation")
        result = subprocess.run([self.node, "--input-type=module", "-e", script, Path(extra[1]).as_uri()], env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_configured_public_profile_and_capabilities(self):
        value = models.product_configuration()
        self.assertTrue(value["configured"])
        self.assertEqual(value["default"], {"client": "pi", "model": "noetic-local/qwen3.6-a3b", "thinking": "off"})
        self.assertEqual(value["profiles"][0]["model"], value["default"]["model"])
        self.assertEqual(value["capabilities"]["context_window"], 57344)
        self.assertEqual(value["capabilities"]["max_tokens"], 4096)
        self.assertNotIn(self.secret, json.dumps(value))

    def test_omitted_main_qa_and_parent_inheritance(self):
        value = models.new_options()
        self.assertEqual(value, {"client": "pi", "model": "noetic-local/qwen3.6-a3b", "qa_model": "noetic-local/qwen3.6-a3b", "thinking": "off"})
        parent = {"model": "pi-other/old-frozen", "thinking": "high"}
        original = json.dumps(parent)
        child = models.new_options(parent=parent)
        self.assertEqual(child["model"], parent["model"])
        self.assertEqual(child["thinking"], parent["thinking"])
        self.assertEqual(json.dumps(parent), original)

    def test_explicit_models_and_thinking_are_unchanged(self):
        value = models.new_options(client="opencode", model="openai/explicit", qa_model="openai/review", thinking="high")
        self.assertEqual(value, {"client": "opencode", "model": "openai/explicit", "qa_model": "openai/review", "thinking": "high"})
        with self.assertRaisesRegex(ValueError, "client"):
            models.new_options(client="opencode")

    def test_unconfigured_installation_retains_legacy_defaults(self):
        self.config.write_text(json.dumps({"inference": {"model": "support-only"}}))
        self.assertFalse(models.product_configuration()["configured"])
        value = models.new_options(legacy_client="opencode", legacy_model=None)
        self.assertEqual(value, {"client": "opencode", "model": None, "qa_model": None, "thinking": "high"})
        self.assertEqual(models.new_options(legacy_model="old/pi")["model"], "old/pi")

    def test_non_qwen_installation_is_configurable(self):
        self.data["product"]["model"] = "noetic-local/other-explicit"
        self.config.write_text(json.dumps(self.data))
        self.assertEqual(models.new_options()["model"], "noetic-local/other-explicit")

    def test_missing_or_bad_configuration_never_falls_back(self):
        self.config.unlink()
        with self.assertRaisesRegex(ValueError, "configuration"):
            models.new_options()
        for provider in ({}, {**self.data["product"]["provider"], "max_tokens": 57345},
                         {**self.data["product"]["provider"], "base_url": "http://user:secret@host/v1"}):
            self.data["product"]["provider"] = provider
            self.config.write_text(json.dumps(self.data))
            with self.assertRaises(ValueError):
                models.product_configuration()

    def test_registration_uses_existing_credential_without_global_mutation(self):
        before = self.pi_models.read_bytes()
        env = {"PATH": "/usr/bin:/bin", "NOETIC_LOCAL_CONFIG": str(self.config), "PI_CODING_AGENT_DIR": str(self.pi)}
        extra, changed = models.pi_launch("noetic-local/qwen3.6-a3b", self.root / "registration", env)
        self.assertEqual(extra[0], "--extension")
        extension = Path(extra[1])
        self.assertTrue(extension.is_file())
        self.assertNotIn(self.secret, extension.read_text())
        self.assertNotIn(self.secret, json.dumps(extra))
        self.assertEqual(self.pi_models.read_bytes(), before)
        self.assertEqual(env, {"PATH": "/usr/bin:/bin", "NOETIC_LOCAL_CONFIG": str(self.config), "PI_CODING_AGENT_DIR": str(self.pi)})
        script = """const m=await import(process.argv[1]);let value;await m.default({registerProvider:(name,config)=>{value={name,...config};}});if(value.models[0].id!=='qwen3.6-a3b'||value.models[0].contextWindow!==57344||value.models[0].maxTokens!==4096||value.api!=='openai-completions'||value.baseUrl!=='http://127.0.0.1:8742/v1'||!value.apiKey)throw Error('registration mismatch');console.log(JSON.stringify({provider:value.name,model:value.models[0].id,context:value.models[0].contextWindow,max:value.models[0].maxTokens,api:value.api,input:value.models[0].input}));"""
        self.assertIsNotNone(self.node, "Node must be available on PATH before fixture isolation")
        result = subprocess.run([self.node, "--input-type=module", "-e", script, extension.as_uri()], env=changed, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(self.secret, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["model"], "qwen3.6-a3b")

    def test_missing_native_key_refuses_selected_route(self):
        self.pi_models.write_text('{"providers":{}}')
        with self.assertRaisesRegex(ValueError, "credential"):
            models.pi_launch("noetic-local/qwen3.6-a3b", self.root / "registration", dict(os.environ))
        self.assertFalse((self.root / "registration").exists())

    def test_unrelated_explicit_route_has_no_provider_side_effect(self):
        extra, environment = models.pi_launch("openai-codex/old-frozen", self.root / "unused", {"UNCHANGED": "yes"})
        self.assertEqual(extra, [])
        self.assertEqual(environment, {"UNCHANGED": "yes"})
        self.assertFalse((self.root / "unused").exists())

    def test_new_reviewed_preparation_resolves_before_freeze(self):
        service = ReviewedApplication.__new__(ReviewedApplication)
        service.app = SimpleNamespace(mutation=nullcontext)
        service.launch_dir = lambda command: self.root / "new-launch"
        class Captured(Exception): pass
        body = {"command_id": "new", "task": "fixture", "model": None, "qa_model": None}
        original = dict(body)
        with patch.object(service, "preflight", side_effect=Captured) as prepare:
            with self.assertRaises(Captured): service.start(body)
        self.assertEqual(prepare.call_args.args[0]["model"], "noetic-local/qwen3.6-a3b")
        self.assertEqual(prepare.call_args.args[0]["qa_model"], "noetic-local/qwen3.6-a3b")
        self.assertEqual(body, original)

    def test_old_retained_reviewed_command_does_not_resolve_defaults(self):
        service = ReviewedApplication.__new__(ReviewedApplication)
        service.app = SimpleNamespace(mutation=nullcontext)
        directory = self.root / "old-launch"; directory.mkdir()
        service.launch_dir = lambda command: directory
        body = {"command_id": "old", "model": None, "qa_model": None}
        with patch.object(service, "retained_command", return_value={"retained": True}) as retained:
            self.assertEqual(service.start(body), {"retained": True})
        self.assertEqual(retained.call_args.args[1], body)

    def test_new_standalone_develop_thinking_before_actor_and_explicit_control(self):
        class Captured(Exception): pass
        for controls, expected in ((None, "off"), ({"reasoning_effort":"low"}, "low")):
            with patch.object(develop.runtime, "execute_step", side_effect=Captured) as execute:
                with self.assertRaises(Captured):
                    develop.develop("Owned unsent default fixture", self.root, self.root/"runs", None,
                                    inquiry=True, worker_controls=controls)
            command = execute.call_args.args[3]
            self.assertEqual(command[command.index("--model")+1], "noetic-local/qwen3.6-a3b")
            self.assertEqual(command[command.index("--thinking")+1], expected)
            self.assertIn("--extension", command)

    def test_development_native_command_registers_only_configured_model(self):
        command, env = develop.client_command("pi", "owned fixture", "worker", "noetic-local/qwen3.6-a3b", run_dir=self.root / "run")
        self.assertIn("--extension", command)
        self.assertEqual(command[command.index("--model") + 1], "noetic-local/qwen3.6-a3b")
        old, _ = develop.client_command("pi", "owned fixture", "worker", "openai-codex/old-frozen")
        self.assertNotIn("--extension", old)


if __name__ == "__main__":
    unittest.main()
