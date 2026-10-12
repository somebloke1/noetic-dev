"""Development embedder implementation checks using disposable HTTP endpoints."""

import argparse
from contextlib import closing
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from scripts import noetic_local as local
from scripts import noetic_semantic as semantic


class Endpoint:
    def __init__(self):
        self.calls = []
        self.status = 200
        self.raw = None
        self.delay = 0
        self.location = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.calls.append({"path": self.path, "authorization": self.headers.get("Authorization"),
                                    "content_type": self.headers.get("Content-Type"), "payload": payload})
                if owner.delay:
                    time.sleep(owner.delay)
                if self.path.endswith("/embeddings"):
                    response = {"data": [{"index": i, "embedding": [3, 4, 0]}
                                         for i in reversed(range(len(payload["input"])))]}
                else:
                    response = {"choices": [{"message": {"content": "Public fixture support"},
                                             "finish_reason": "stop"}]}
                raw = owner.raw if owner.raw is not None else json.dumps(response).encode()
                try:
                    self.send_response(owner.status)
                    if owner.location:
                        self.send_header("Location", owner.location)
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}/v1"

    def close(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()


class DevelopmentEmbedderTests(unittest.TestCase):
    def setUp(self):
        self.text = Endpoint()
        self.addCleanup(self.text.close)
        self.embed = Endpoint()
        self.addCleanup(self.embed.close)
        self.environment = patch.dict("os.environ", {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.legacy = local.Settings(base_url=self.text.base_url, dimensions=3)

    def dedicated(self, **changes):
        return replace(self.legacy, embedding_base_url=self.embed.base_url,
                       embedding_api_key_env="", **changes)

    def test_legacy_identity_and_configured_key_requirement(self):
        self.assertEqual(local.digest(local.canonical(local.Settings().embedding_identity())),
                         "7adbd1f8e33c4bb25b53ba69d51bb3e4add3dcddc7e951eb40f6071f4916a2da")
        client = local.LocalClient(self.legacy)
        for operation in (lambda: client.embed(["public fixture"]), lambda: client.complete("public fixture")):
            with self.assertRaisesRegex(local.LocalError, "credential"):
                operation()
        self.assertEqual(client.requests, 0)
        self.assertEqual(self.text.calls, [])
        with patch.dict("os.environ", {"LITELLM_API_KEY": "public-legacy-key"}):
            client.embed(["public fixture"])
            client.complete("public fixture")
        self.assertEqual([call["path"] for call in self.text.calls], ["/v1/embeddings", "/v1/chat/completions"])
        self.assertTrue(all(call["authorization"] == "Bearer public-legacy-key" for call in self.text.calls))
        self.assertEqual(self.embed.calls, [])

    def test_no_auth_embedding_without_any_completion_key(self):
        client = local.LocalClient(self.dedicated())
        self.assertEqual(client.embed(["public fixture"]), [[0.6, 0.8, 0.0]])
        self.assertIsNone(self.embed.calls[0]["authorization"])
        with self.assertRaisesRegex(local.LocalError, "credential"):
            client.complete("public fixture")
        self.assertEqual(self.text.calls, [])
        self.assertEqual(client.requests, 1)

    def test_targets_and_unrelated_text_credential_are_separate(self):
        settings = self.dedicated(embedding_model="noetic-snowflake-embed:latest", batch_size=2)
        client = local.LocalClient(settings)
        with patch.dict("os.environ", {"LITELLM_API_KEY": "public-unrelated-completion-sentinel"}):
            result = client.embed(["one", "two", "three"], query=True)
            client.complete("public fixture")
        self.assertEqual(result, [[0.6, 0.8, 0.0]] * 3)
        self.assertEqual([call["payload"]["input"] for call in self.embed.calls],
                         [["query: one", "query: two"], ["query: three"]])
        for call in self.embed.calls:
            self.assertEqual(call["path"], "/v1/embeddings")
            self.assertIsNone(call["authorization"])
            self.assertEqual(call["content_type"], "application/json")
            self.assertEqual(call["payload"]["model"], settings.embedding_model)
            self.assertEqual(call["payload"]["encoding_format"], "float")
        self.assertEqual(self.text.calls[0]["path"], "/v1/chat/completions")
        self.assertEqual(self.text.calls[0]["authorization"], "Bearer public-unrelated-completion-sentinel")
        self.assertEqual(self.text.calls[0]["payload"]["model"], self.legacy.text_model)

    def test_embedding_key_is_required_and_sent_only_to_embedding_endpoint(self):
        settings = replace(self.dedicated(), embedding_api_key_env="PUBLIC_EMBEDDING_KEY")
        client = local.LocalClient(settings)
        with patch.dict("os.environ", {"LITELLM_API_KEY": "public-text-key"}):
            with self.assertRaisesRegex(local.LocalError, "credential"):
                client.embed(["public fixture"])
            self.assertEqual(self.embed.calls, [])
            self.assertEqual(client.requests, 0)
            with patch.dict("os.environ", {"PUBLIC_EMBEDDING_KEY": "public-embedding-key"}):
                client.embed(["public fixture"])
                client.complete("public fixture")
        self.assertEqual(self.embed.calls[0]["authorization"], "Bearer public-embedding-key")
        self.assertEqual(self.text.calls[0]["authorization"], "Bearer public-text-key")

    def test_independent_credential_can_use_shared_endpoint(self):
        client = local.LocalClient(replace(self.legacy, embedding_api_key_env="PUBLIC_EMBEDDING_KEY"))
        with patch.dict("os.environ", {"PUBLIC_EMBEDDING_KEY": "public-embedding-key"}):
            client.embed(["public fixture"])
        self.assertEqual(self.text.calls[0]["authorization"], "Bearer public-embedding-key")
        self.assertEqual(client.settings.embedding_identity(), self.legacy.embedding_identity())

    def test_unset_embedding_credential_preserves_inheritance(self):
        client = local.LocalClient(replace(self.legacy, embedding_base_url=self.embed.base_url))
        with self.assertRaisesRegex(local.LocalError, "credential"):
            client.embed(["public fixture"])
        with patch.dict("os.environ", {"LITELLM_API_KEY": "public-inherited-key"}):
            client.embed(["public fixture"])
        self.assertEqual(self.embed.calls[0]["authorization"], "Bearer public-inherited-key")

    def test_config_environment_explicit_and_cli_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text(json.dumps({"access": {"base_url": self.text.base_url},
                                          "embedding": {"base_url": self.embed.base_url, "api_key_env": "",
                                                        "model": "configured-model"}}))
            loaded = local.load_settings(config)
            self.assertEqual((loaded.embedding_base_url, loaded.embedding_api_key_env), (self.embed.base_url, ""))
            with patch.dict("os.environ", {"NOETIC_LOCAL_CONFIG": str(config)}):
                self.assertEqual(local.load_settings(), loaded)
            with patch.dict("os.environ", {"NOETIC_LOCAL_EMBEDDING_BASE_URL": "https://env.example/v1",
                                            "NOETIC_LOCAL_EMBEDDING_API_KEY_ENV": "PUBLIC_ENV_KEY",
                                            "NOETIC_LOCAL_EMBEDDING_MODEL": "env-model"}):
                inherited = local.load_settings(config)
                self.assertEqual(inherited.embedding_base_url, "https://env.example/v1")
                self.assertEqual(inherited.embedding_api_key_env, "PUBLIC_ENV_KEY")
                overridden = local.load_settings(config, embedding_base_url=self.embed.base_url,
                                                 embedding_api_key_env="", embedding_model="explicit-model")
                self.assertEqual((overridden.embedding_base_url, overridden.embedding_api_key_env,
                                  overridden.embedding_model), (self.embed.base_url, "", "explicit-model"))
                parser = argparse.ArgumentParser()
                local.add_settings_arguments(parser)
                args = parser.parse_args(["--config", str(config), "--embedding-base-url", self.embed.base_url,
                                          "--embedding-api-key-env", "", "--embedding-model", "cli-model"])
                cli = local.settings_from_args(args)
                self.assertEqual((cli.embedding_base_url, cli.embedding_api_key_env, cli.embedding_model),
                                 (self.embed.base_url, "", "cli-model"))
            with patch.dict("os.environ", {"NOETIC_LOCAL_EMBEDDING_API_KEY_ENV": ""}):
                self.assertEqual(local.load_settings().embedding_api_key_env, "")

    def test_example_is_explicit_development_profile(self):
        settings = local.load_settings(Path(__file__).resolve().parents[2] / "config/development-local-support.example.json")
        self.assertEqual(settings.base_url, local.Settings().base_url)
        self.assertEqual(settings.embedding_base_url, "http://127.0.0.1:11435/v1")
        self.assertEqual(settings.embedding_api_key_env, "")
        self.assertEqual(settings.embedding_model, "noetic-snowflake-embed:latest")
        self.assertEqual(settings.dimensions, 1024)
        self.assertEqual(settings.source_model_layer_sha256, local.SNOWFLAKE_LAYER)

    def test_embedding_url_and_credential_settings_are_validated(self):
        for url in ("", "ftp://localhost/v1", "http:///v1", "http://user:password@localhost/v1", "http://@localhost/v1",
                    "http://localhost/v1?query=1", "http://localhost/v1#fragment", "http://localhost:bad/v1",
                    "http://localhost:70000/v1", " http://localhost/v1", "http://localhost/v\t1", 42):
            with self.subTest(url=url), self.assertRaises(local.LocalError):
                replace(self.legacy, embedding_base_url=url)
        for value in (42, False, " "):
            with self.subTest(value=value), self.assertRaises(local.LocalError):
                replace(self.legacy, embedding_api_key_env=value)
        self.assertIsNone(self.legacy.embedding_base_url)
        self.assertIsNone(self.legacy.embedding_api_key_env)

    def test_actual_embedding_identity_and_disposable_cache_boundary(self):
        settings = self.dedicated()
        identity = settings.embedding_identity()
        self.assertEqual(identity["base_url"], self.embed.base_url)
        self.assertEqual(identity["endpoint"], "/embeddings")
        self.assertEqual(replace(settings, base_url="https://text.example/v1").embedding_identity(), identity)
        self.assertEqual(replace(settings, embedding_api_key_env="PUBLIC_OTHER_KEY").embedding_identity(), identity)
        self.assertEqual(replace(settings, embedding_base_url=self.embed.base_url + "/").embedding_identity(), identity)
        with tempfile.TemporaryDirectory() as directory, closing(sqlite3.connect(":memory:")) as db:
            first = semantic.index_runs(db, Path(directory), local.LocalClient(settings))
            self.assertEqual(first["identity"]["base_url"], self.embed.base_url)
            for changed in (replace(settings, embedding_base_url=self.text.base_url),
                            replace(settings, embedding_model="different-model")):
                with self.assertRaisesRegex(local.LocalError, "identity mismatch"):
                    semantic.index_runs(db, Path(directory), local.LocalClient(changed))
                with self.assertRaisesRegex(local.LocalError, "identity mismatch"):
                    semantic.search(db, "public fixture", local.LocalClient(changed))
        self.assertEqual(self.embed.calls + self.text.calls, [])

    def test_no_auth_request_retains_input_and_settings_bounds(self):
        client = local.LocalClient(self.dedicated())
        for texts, query in (([" "], False), ([None], False), (["x" * 1025], False), (["x" * 1024], True)):
            with self.subTest(texts=texts, query=query), self.assertRaises(local.LocalError):
                client.embed(texts, query=query)
        self.assertEqual(client.requests, 0)
        for change in ({"timeout": 0}, {"timeout": 121}, {"timeout": float("nan")}, {"batch_size": 17},
                       {"dimensions": 8193}, {"max_tokens": 2049}, {"chunk_bytes": 1025}):
            with self.subTest(change=change), self.assertRaises(local.LocalError):
                replace(self.legacy, **change)

    def test_http_and_response_errors_omit_bodies_without_retry(self):
        client = local.LocalClient(self.dedicated())
        for status, raw in ((503, b"private-response-sentinel"), (200, b"private-response-sentinel"),
                            (200, b"[]"), (200, b'{"data":[null]}'),
                            (200, b'{"data":[{"index":0,"embedding":[0,0,0]}]}'),
                            (200, b'{"data":[{"index":0,"embedding":[1,2]}]}'),
                            (200, b'{"data":[{"index":0,"embedding":[NaN,1,2]}]}'),
                            (200, b'{"data":[{"index":1,"embedding":[1,2,3]}]}'),
                            (200, b'{"data":[]}'), (200, b"x" * (4 * 1024 * 1024 + 1))):
            with self.subTest(status=status, size=len(raw)):
                self.embed.status, self.embed.raw = status, raw
                before = len(self.embed.calls)
                with self.assertRaises(local.LocalError) as caught:
                    client.embed(["public fixture"])
                self.assertNotIn("private-response-sentinel", str(caught.exception))
                self.assertEqual(len(self.embed.calls), before + 1)
        self.assertEqual(self.text.calls, [])

    def test_redirect_does_not_send_to_another_target(self):
        self.embed.status = 307
        self.embed.location = self.text.base_url + "/embeddings"
        with self.assertRaises(local.LocalError):
            local.LocalClient(self.dedicated()).embed(["public fixture"])
        self.assertEqual(len(self.embed.calls), 1)
        self.assertEqual(self.text.calls, [])

    def test_timeout_remains_bounded_without_retry(self):
        self.embed.delay = 0.15
        client = local.LocalClient(self.dedicated(timeout=0.03))
        with self.assertRaisesRegex(local.LocalError, "timed out"):
            client.embed(["public fixture"])
        self.assertEqual(len(self.embed.calls), 1)
        self.assertEqual(client.requests, 1)


if __name__ == "__main__":
    unittest.main()
