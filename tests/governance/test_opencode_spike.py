"""Synthetic tests for the one-turn OpenCode credential-isolation spike."""

from __future__ import annotations

import copy
import json
import os
import shutil
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE = str(ROOT / "scripts" / "governance")
if GOVERNANCE not in sys.path:
    sys.path.insert(0, GOVERNANCE)

import run_opencode_spike as spike  # noqa: E402
from json_schema import load_json_strict, validate_schema  # noqa: E402


MODEL = "codex/gpt-5.6-luna"
DECISION_ID = "d-20260718-000001"
NONCE = "0123456789abcdef0123456789abcdef"
PROMPT = f"Respond with exactly READY {NONCE} and nothing else."
EXPECTED_TEXT = f"READY {NONCE}"
ROUTER_IDENTITY = "1" * 64
ROUTER_CLASSIFICATION = "2" * 64


def model_ref(model: str) -> dict[str, str]:
    return spike.expected_model_ref(model)


def route_decision() -> dict:
    return {
        "availability": "unverified",
        "decision_id": DECISION_ID,
        "effective_complexity": "trivial",
        "fable_eligible": False,
        "fallback_refs": [model_ref(model) for model in spike.TRIVIAL_ROUTE_MODELS[1:]],
        "fallbacks": list(spike.TRIVIAL_ROUTE_MODELS[1:]),
        "genus": "Test Generation",
        "genus_code": "TEST-GEN",
        "independent_approval_eligible": False,
        "model": MODEL,
        "model_ref": model_ref(MODEL),
        "rationale": ["synthetic route"],
        "routing_profile": "standard",
        "sophistication": "trivial",
    }


def route_record() -> dict:
    return {
        "schema_version": "1",
        "component_sha": spike.COMPONENT_SHA,
        "router_identity_sha256": ROUTER_IDENTITY,
        "router_state_classification_sha256": ROUTER_CLASSIFICATION,
        "classification": dict(spike.ROUTE_ARGUMENTS),
        "decision": route_decision(),
    }


def system_prompt(model: str = MODEL) -> str:
    return "\n".join(
        [
            "Return only the exact text requested by the user. Never call a tool.",
            f"You are powered by the model named {model}. The exact model ID is litellm/{model}",
            "Here is some useful information about the environment you are running in:",
            "<env>",
            "  Working directory: /work",
            "  Workspace root folder: /",
            "  Is directory a git repo: no",
            "  Platform: linux",
            "  Today's date: Sat Jul 18 2026",
            "</env>",
        ]
    )


def child_body() -> dict:
    return {
        "model": MODEL,
        "input": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": json.dumps(PROMPT)},
        ],
        "stream": True,
        "store": False,
        "include": ["reasoning.encrypted_content"],
        "reasoning": {"effort": "high", "summary": "auto"},
        "max_output_tokens": 1_024,
    }


def opencode_jsonl(text: str = EXPECTED_TEXT) -> bytes:
    common = {"sessionID": "ses_1", "messageID": "msg_1"}
    events = [
        {
            "type": "step_start",
            "timestamp": 1,
            "sessionID": "ses_1",
            "part": {**common, "id": "part_1", "type": "step-start"},
        },
        {
            "type": "text",
            "timestamp": 2,
            "sessionID": "ses_1",
            "part": {
                **common,
                "id": "part_2",
                "type": "text",
                "text": text,
                "time": {"start": 1, "end": 2},
                "metadata": {"openai": {"itemId": spike.CLEAN_MESSAGE_ID}},
            },
        },
        {
            "type": "step_finish",
            "timestamp": 3,
            "sessionID": "ses_1",
            "part": {
                **common,
                "id": "part_3",
                "type": "step-finish",
                "reason": "stop",
                "cost": 0,
                "tokens": {"total": 2, "input": 1, "output": 1, "reasoning": 0, "cache": {"read": 0, "write": 0}},
            },
        },
    ]
    return b"".join(spike.canonical_json(event) + b"\n" for event in events)


def success_result() -> dict:
    result = spike._base_result()
    result.update(
        {
            "execution_status": "success",
            "failure_code": None,
            "router_identity_sha256": ROUTER_IDENTITY,
            "route_decision_id": DECISION_ID,
            "route_reference_sha256": "a" * 64,
            "routed_model": MODEL,
            "opencode_version": spike.OPENCODE_VERSION,
            "opencode_sha256": spike.OPENCODE_SHA256,
            "static_title": f"noetic-{DECISION_ID}",
            "title_sha256": "b" * 64,
            "config_sha256": "c" * 64,
            "json_event_log_sha256": "d" * 64,
            "upstream_response_sha256": "e" * 64,
            "litellm_peer_identity_sha256": "9" * 64,
            "model_turn_count": 1,
            "bridge_request_count": 1,
            "upstream_request_count": 1,
            "parsed_upstream_completion": True,
            "output_text": EXPECTED_TEXT,
            "nonce_sha256": "f" * 64,
            "nonce_matched": True,
            "isolation": {key: key != "host_source_mounted" for key in spike.ISOLATION_FIELDS},
            "claim_state": "request-issued",
            "request_issued": True,
        }
    )
    return result


def failure_result() -> dict:
    result = spike._base_result()
    result.update({"route_decision_id": DECISION_ID, "router_identity_sha256": ROUTER_IDENTITY, "route_reference_sha256": "a" * 64, "routed_model": MODEL, "failure_code": "credential-directory-invalid", "claim_state": "claimed"})
    return result


def append_outcome(path: Path, arguments: dict) -> None:
    record = {"decision": {"decision_id": DECISION_ID}, "decision_id": DECISION_ID, "notes": arguments["notes"], "outcome": arguments["outcome"], "ts": "2026-07-18T00:00:00+00:00"}
    with path.open("ab") as handle:
        handle.write(spike.canonical_json(record) + b"\n")


class FakeRouter:
    def __init__(self, route: dict | None = None, acknowledgement: dict | None = None, outcomes_path: Path | None = None) -> None:
        self.route = route
        self.acknowledgement = acknowledgement or {"recorded": True}
        self.outcomes_path = outcomes_path
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def call_tool(self, name: str, arguments: dict) -> dict:
        self.calls.append((name, arguments))
        if name == "route_task":
            if self.route is None:
                raise AssertionError("unexpected route call")
            return copy.deepcopy(self.route)
        if self.outcomes_path is not None:
            append_outcome(self.outcomes_path, arguments)
        return copy.deepcopy(self.acknowledgement)


class RouterFactory:
    def __init__(self, router: FakeRouter) -> None:
        self.router = router
        self.arguments: list[tuple[tuple, dict]] = []

    def __call__(self, *args, **kwargs):
        self.arguments.append((args, kwargs))
        return self.router


class TestStrictContracts(unittest.TestCase):
    def test_route_decision_is_exact_and_fail_closed(self):
        self.assertEqual(spike.validate_route_decision(route_decision())["model"], MODEL)
        mutations = []
        for field, value in (
            ("model", spike.STANDARD_MODELS[0]),
            ("fallbacks", list(reversed(spike.TRIVIAL_ROUTE_MODELS[1:]))),
            ("availability", "verified"),
            ("sophistication", "routine"),
            ("routing_profile", "other"),
        ):
            item = route_decision()
            item[field] = value
            mutations.append(item)
        extra = route_decision()
        extra["extra"] = True
        mutations.append(extra)
        bad_ref = route_decision()
        bad_ref["model_ref"]["base_url"] = "https://provider.example"
        mutations.append(bad_ref)
        for value in mutations:
            with self.subTest(value=value), self.assertRaises(spike.SpikeError):
                spike.validate_route_decision(value)

    def test_router_component_manifest_binds_command_config_table_and_interpreter(self):
        command = b"router-command"
        config = b"router-config"
        table = b"router-table"
        interpreter = b"python-runtime"
        manifest = {
            "component_sha": spike.COMPONENT_SHA,
            "command_sha256": spike.sha256(command),
            "config_sha256": spike.sha256(config),
            "genus_table_sha256": spike.sha256(table),
        }
        raw_manifest = spike.canonical_json(manifest)
        files = {
            spike.ROUTER_ROOT / "component-manifest.json": raw_manifest,
            spike.ROUTER_COMMAND: command,
            spike.ROUTER_CONFIG: config,
            spike.ROUTER_CONFIG.parent / "genus_models.csv": table,
            Path("/usr/bin/python3.12"): interpreter,
        }
        with mock.patch(
            "run_opencode_spike._root_owned_file_bytes",
            side_effect=lambda path, **_kwargs: files[path],
        ), mock.patch(
            "run_opencode_spike._validate_root_owned_symlink",
            return_value=Path("/usr/bin/python3.12"),
        ):
            identity = spike.validate_router_component_identity()
            self.assertRegex(identity, r"^[a-f0-9]{64}$")
            files[spike.ROUTER_COMMAND] = b"substituted"
            with self.assertRaises(spike.SpikeError) as raised:
                spike.validate_router_component_identity()
        self.assertEqual(raised.exception.code, "router-manifest-digest-mismatch")

    def test_litellm_peer_manifest_binds_all_root_owned_runtime_artifacts(self):
        artifacts = {
            spike.LITELLM_SERVICE_UNIT: b"unit",
            spike.LITELLM_LAUNCHER: b"launcher",
            spike.LITELLM_CONFIG: b"config",
            Path("/usr/bin/python3.12"): b"python",
        }
        manifest = {
            "schema_version": "1",
            "service_unit": str(spike.LITELLM_SERVICE_UNIT),
            "service_unit_sha256": spike.sha256(artifacts[spike.LITELLM_SERVICE_UNIT]),
            "launcher": str(spike.LITELLM_LAUNCHER),
            "launcher_sha256": spike.sha256(artifacts[spike.LITELLM_LAUNCHER]),
            "config": str(spike.LITELLM_CONFIG),
            "config_sha256": spike.sha256(artifacts[spike.LITELLM_CONFIG]),
            "python": "/usr/bin/python3.12",
            "python_sha256": spike.sha256(artifacts[Path("/usr/bin/python3.12")]),
            "uid": 994,
            "gid": 981,
            "cgroup": spike.LITELLM_CGROUP,
            "cmdline": [
                "/opt/litellm/.venv/bin/python",
                str(spike.LITELLM_LAUNCHER),
                "--config",
                str(spike.LITELLM_CONFIG),
                "--host",
                "0.0.0.0",
                "--port",
                str(spike.LITELLM_PORT),
            ],
            "host": spike.LITELLM_HOST,
            "port": spike.LITELLM_PORT,
        }
        files = {spike.LITELLM_PEER_MANIFEST: spike.canonical_json(manifest), **artifacts}
        with mock.patch(
            "run_opencode_spike._root_owned_file_bytes",
            side_effect=lambda path, **_kwargs: files[path],
        ):
            observed, digest = spike.validate_litellm_peer_manifest()
            self.assertEqual(observed, manifest)
            self.assertRegex(digest, r"^[a-f0-9]{64}$")
            files[spike.LITELLM_CONFIG] = b"substituted"
            with self.assertRaises(spike.SpikeError) as raised:
                spike.validate_litellm_peer_manifest()
        self.assertEqual(raised.exception.code, "litellm-peer-manifest-digest-mismatch")

    def test_child_body_requires_one_source_free_toolless_request(self):
        self.assertEqual(spike.validate_child_request_body(child_body(), MODEL, PROMPT), child_body())
        mutations = []
        for field, value in (
            ("model", "codex/gpt-5.6-sol"),
            ("stream", False),
            ("store", True),
            ("max_output_tokens", 2_048),
            ("max_output_tokens", 1024.0),
            ("reasoning", {"effort": "low", "summary": "auto"}),
        ):
            item = child_body()
            item[field] = value
            mutations.append(item)
        injected = child_body()
        injected["input"][0]["content"] += "\nInstructions from: /repo/AGENTS.md"
        mutations.append(injected)
        extra_message = child_body()
        extra_message["input"].append({"role": "user", "content": "source"})
        mutations.append(extra_message)
        tools = child_body()
        tools["tools"] = []
        mutations.append(tools)
        for value in mutations:
            with self.subTest(value=value), self.assertRaises(spike.SpikeError):
                spike.validate_child_request_body(value, MODEL, PROMPT)

    def test_config_and_bwrap_are_closed(self):
        config = spike.build_opencode_config(MODEL, 31_337)
        self.assertEqual(config["agent"][spike.AGENT_NAME]["steps"], 2)
        self.assertEqual(config["agent"][spike.AGENT_NAME]["tools"], {"*": False})
        self.assertEqual(config["provider"]["litellm"]["options"]["apiKey"], spike.DUMMY_API_KEY)
        command = spike.build_bwrap_command(
            opencode_fd=10,
            controller_fd=11,
            control_directory=Path("/tmp/synthetic-control"),
            relay_port=31_337,
            config=config,
            model=MODEL,
            title=f"noetic-{DECISION_ID}",
            prompt=PROMPT,
            library_paths=[],
        )
        joined = "\x00".join(command)
        for value in ("--unshare-user", "--unshare-pid", "--unshare-net", "--disable-userns", "--clearenv", "--ro-bind-fd"):
            self.assertIn(value, command)
        self.assertNotIn(str(ROOT), joined)
        self.assertNotIn(spike.TOKEN_ENV, joined)
        self.assertNotIn(spike.CREDENTIAL_NAME, joined)

class TestHTTPAndControlBoundaries(unittest.TestCase):
    def request_bytes(self, payload: dict | None = None, headers: list[tuple[str, str]] | None = None) -> bytes:
        body = spike.canonical_json(payload or child_body())
        values = headers or [
            ("Host", "127.0.0.1:31337"),
            ("Content-Type", "application/json"),
            ("Authorization", f"Bearer {spike.DUMMY_API_KEY}"),
            ("Content-Length", str(len(body))),
            ("Connection", "close"),
        ]
        return b"POST /v1/responses HTTP/1.1\r\n" + b"".join(
            f"{name}: {value}\r\n".encode("ascii") for name, value in values
        ) + b"\r\n" + body

    def parse_request(self, raw: bytes):
        server, client = socket.socketpair()
        try:
            client.sendall(raw)
            client.shutdown(socket.SHUT_WR)
            return spike.read_child_http_request(
                server,
                expected_host="127.0.0.1:31337",
                expected_model=MODEL,
                expected_prompt=PROMPT,
            )
        finally:
            server.close()
            client.close()

    def test_http_accepts_only_the_exact_request(self):
        parsed = self.parse_request(self.request_bytes())
        self.assertEqual(parsed.payload, child_body())
        self.assertEqual(parsed.headers["authorization"], f"Bearer {spike.DUMMY_API_KEY}")

    def test_http_rejects_ambiguous_framing_and_authority(self):
        body = spike.canonical_json(child_body())
        cases = [
            self.request_bytes(headers=[
                ("Host", "127.0.0.1:31337"),
                ("Content-Type", "application/json"),
                ("Authorization", f"Bearer {spike.DUMMY_API_KEY}"),
                ("Content-Length", str(len(body))),
                ("Content-Length", str(len(body))),
            ]),
            self.request_bytes(headers=[
                ("Host", "127.0.0.1:31337"),
                ("Content-Type", "application/json"),
                ("Authorization", f"Bearer {spike.DUMMY_API_KEY}"),
                ("Content-Length", str(len(body))),
                ("Transfer-Encoding", "chunked"),
            ]),
            self.request_bytes(headers=[
                ("Host", "attacker.invalid"),
                ("Content-Type", "application/json"),
                ("Authorization", f"Bearer {spike.DUMMY_API_KEY}"),
                ("Content-Length", str(len(body))),
            ]),
            self.request_bytes(headers=[
                ("Host", "127.0.0.1:31337"),
                ("Content-Type", "application/json"),
                ("Authorization", "Bearer real-looking-token"),
                ("Content-Length", str(len(body))),
            ]),
            self.request_bytes() + b"GET /second HTTP/1.1\r\n\r\n",
        ]
        for raw in cases:
            with self.subTest(raw=raw[:100]), self.assertRaises(spike.SpikeError):
                self.parse_request(raw)

class TestUpstreamAndEventValidation(unittest.TestCase):
    def test_sse_accepts_one_exact_completion(self):
        raw = spike.synthesize_clean_sse(MODEL, EXPECTED_TEXT)
        self.assertEqual(spike.parse_upstream_sse(raw, MODEL, EXPECTED_TEXT), EXPECTED_TEXT)
        response = spike.UpstreamHTTPResponse(200, [("Content-Type", "text/event-stream")], raw)
        validated = spike.validate_upstream_response(
            response,
            token=b"synthetic-secret",
            expected_model=MODEL,
            expected_text=EXPECTED_TEXT,
        )
        self.assertEqual(validated.text, EXPECTED_TEXT)
        self.assertEqual(spike.parse_upstream_sse(validated.clean_body, MODEL, EXPECTED_TEXT), EXPECTED_TEXT)

    def test_sse_rejects_wrong_model_tool_refusal_sequence_and_missing_done(self):
        valid = spike.synthesize_clean_sse(MODEL, EXPECTED_TEXT)
        cases = [
            valid.replace(MODEL.encode(), b"codex/gpt-5.6-sol"),
            valid.replace(b'"response.output_text.delta"', b'"response.function_call_arguments.delta"'),
            valid.replace(b'"type":"message"', b'"type":"refusal"', 1),
            valid.replace(b'"sequence_number":4', b'"sequence_number":99', 1),
            valid.replace(b"data: [DONE]\n\n", b""),
            valid.replace(b"data: {\"content_index\":0,\"item_id\":\"msg_noetic_spike\",\"output_index\":0,\"part\":{\"annotations\":[],\"text\":\"READY 0123456789abcdef0123456789abcdef\",\"type\":\"output_text\"},\"sequence_number\":6,\"type\":\"response.content_part.done\"}\n\n", b""),
        ]
        for raw in cases:
            with self.subTest(raw=raw[:80]), self.assertRaises(spike.SpikeError):
                spike.parse_upstream_sse(raw, MODEL, EXPECTED_TEXT)

    def test_upstream_response_rejects_token_reflection_and_protocol_variants(self):
        raw = spike.synthesize_clean_sse(MODEL, EXPECTED_TEXT)
        cases = [
            spike.UpstreamHTTPResponse(201, [("Content-Type", "text/event-stream")], raw),
            spike.UpstreamHTTPResponse(200, [("Content-Type", "application/json")], raw),
            spike.UpstreamHTTPResponse(200, [("Content-Type", "text/event-stream"), ("Content-Encoding", "gzip")], raw),
            spike.UpstreamHTTPResponse(200, [("Content-Type", "text/event-stream"), ("X-Token", "synthetic-secret")], raw),
        ]
        for response in cases:
            with self.subTest(response=response), self.assertRaises(spike.SpikeError):
                spike.validate_upstream_response(
                    response,
                    token=b"synthetic-secret",
                    expected_model=MODEL,
                    expected_text=EXPECTED_TEXT,
                )

    def test_authenticated_transport_revalidates_pid_listener_owner_and_connected_peer(self):
        pidfd, keepalive = os.pipe()
        connected = mock.Mock()
        connected.getpeername.return_value = (spike.LITELLM_HOST, spike.LITELLM_PORT)
        connected.getsockname.return_value = (spike.LITELLM_HOST, 45_000)
        manifest = {"uid": os.getuid()}
        transport = spike.AuthenticatedLiteLLMTransport(
            socket=connected,
            pidfd=pidfd,
            pid=123,
            start_time=456,
            listener_inode=789,
            manifest=manifest,
            identity_sha256="9" * 64,
        )
        try:
            with mock.patch("run_opencode_spike._proc_identity", return_value=(123, 456)), mock.patch(
                "run_opencode_spike._litellm_listener_inode", return_value=789
            ), mock.patch("run_opencode_spike._process_owns_socket") as owns:
                transport.revalidate()
                owns.assert_called_once_with(123, 789)
            with mock.patch("run_opencode_spike._proc_identity", return_value=(123, 456)), mock.patch(
                "run_opencode_spike._litellm_listener_inode", return_value=790
            ), self.assertRaises(spike.SpikeError) as raised:
                transport.revalidate()
            self.assertEqual(raised.exception.code, "litellm-listener-changed")
        finally:
            transport.close()
            os.close(keepalive)

    @mock.patch("run_opencode_spike.http.client.HTTPConnection")
    @mock.patch("run_opencode_spike.open_authenticated_litellm_transport")
    def test_upstream_sender_has_one_fixed_destination_and_authorization_header(
        self,
        transport_factory: mock.Mock,
        connection_type: mock.Mock,
    ):
        body = spike.synthesize_clean_sse(MODEL, EXPECTED_TEXT)

        class Response:
            status = 200

            def __init__(self):
                self.sent = False

            def getheaders(self):
                return [("Content-Type", "text/event-stream")]

            def read(self, _size):
                if self.sent:
                    return b""
                self.sent = True
                return body

        transport = transport_factory.return_value
        transport.socket = mock.Mock()
        transport.identity_sha256 = "9" * 64
        connection = connection_type.return_value
        events = []
        transport.revalidate.side_effect = lambda: events.append("peer")
        connection.endheaders.side_effect = lambda _body: events.append("send")
        connection.getresponse.return_value = Response()
        request = spike.canonical_upstream_request(MODEL, PROMPT)
        response = spike.forward_upstream(request, b"synthetic-secret")
        transport_factory.assert_called_once_with()
        transport.revalidate.assert_called_once_with()
        self.assertEqual(events, ["peer", "send"])
        connection_type.assert_called_once_with("172.22.10.160", 3333, timeout=spike.UPSTREAM_TIMEOUT_SECONDS)
        connection.putrequest.assert_called_once_with("POST", "/v1/responses", skip_host=True, skip_accept_encoding=True)
        self.assertIn(mock.call("Authorization", "Bearer synthetic-secret"), connection.putheader.call_args_list)
        connection.endheaders.assert_called_once_with(request)
        self.assertEqual(response.body, body)
        connection.close.assert_called_once_with()

    @mock.patch("run_opencode_spike.time.monotonic", side_effect=[0.0, 61.0])
    @mock.patch("run_opencode_spike.http.client.HTTPConnection")
    @mock.patch("run_opencode_spike.open_authenticated_litellm_transport")
    def test_upstream_sender_enforces_total_deadline(
        self,
        transport_factory: mock.Mock,
        connection_type: mock.Mock,
        _clock: mock.Mock,
    ):
        transport_factory.return_value.socket = mock.Mock()
        transport_factory.return_value.identity_sha256 = "9" * 64
        with self.assertRaises(spike.SpikeError) as raised:
            spike.forward_upstream(spike.canonical_upstream_request(MODEL, PROMPT), b"synthetic-secret")
        self.assertEqual(raised.exception.code, "upstream-timeout")
        connection_type.return_value.getresponse.assert_not_called()
        connection_type.return_value.close.assert_called_once_with()

    def test_opencode_jsonl_corroborates_exactly_one_turn(self):
        self.assertEqual(spike.parse_opencode_jsonl(opencode_jsonl(), EXPECTED_TEXT), (EXPECTED_TEXT, 1))
        cases = [
            opencode_jsonl() + opencode_jsonl().splitlines(keepends=True)[1],
            opencode_jsonl().replace(b'"msg_1"', b'"msg_2"', 1),
            opencode_jsonl().replace(EXPECTED_TEXT.encode(), b"WRONG", 1),
            opencode_jsonl().replace(spike.CLEAN_MESSAGE_ID.encode(), b"msg_wrong", 1),
            opencode_jsonl().replace(b'"reason":"stop"', b'"reason":"tool-calls"', 1),
            opencode_jsonl().replace(b'"cost":0', b'"cost":NaN', 1),
        ]
        for raw in cases:
            with self.subTest(raw=raw[:100]), self.assertRaises(spike.SpikeError):
                spike.parse_opencode_jsonl(raw, EXPECTED_TEXT)

class TestPersistenceAndPhases(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("NOETIC_OPENCODE_TEST_BINARY"), "exact OpenCode binary not requested")
    def test_real_opencode_binary_completes_one_synthetic_network_isolated_turn(self):
        source = Path(os.environ["NOETIC_OPENCODE_TEST_BINARY"])
        self.assertEqual(spike.sha256(source.read_bytes()), spike.OPENCODE_SHA256)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "opencode"
            controller = root / "run_opencode_spike.py"
            shutil.copyfile(source, binary)
            shutil.copyfile(Path(spike.__file__), controller)
            binary.chmod(0o555)
            controller.chmod(0o555)
            state = root / "state"
            spike.atomic_create_json(state / "route.json", route_record())
            credential_dir = root / "credentials"
            credential_dir.mkdir(mode=0o700)
            credential = credential_dir / spike.CREDENTIAL_NAME
            credential.write_bytes(b"synthetic-secret")
            credential.chmod(0o600)

            def fake_upstream(body: bytes, token: bytes) -> spike.UpstreamHTTPResponse:
                self.assertEqual(token, b"synthetic-secret")
                payload = spike.validate_upstream_request_body(body)
                prompt = payload["input"][0]["content"][0]["text"]
                text = prompt.removeprefix("Respond with exactly ").removesuffix(" and nothing else.")
                clean = spike.synthesize_clean_sse(MODEL, text)
                return spike.UpstreamHTTPResponse(
                    200,
                    [("Content-Type", "text/event-stream")],
                    clean,
                    peer_identity_sha256="9" * 64,
                )

            with mock.patch.object(spike, "OPENCODE_PATH", binary), mock.patch.object(
                spike, "CONTROLLER_PATH", controller
            ):
                result = spike.execute_phase(
                    state_dir=state,
                    input_dir=state,
                    input_reader=spike.read_private_json,
                    environment={"CREDENTIALS_DIRECTORY": str(credential_dir)},
                    upstream_sender=fake_upstream,
                    expected_uid=os.getuid(),
                )
            self.assertEqual(result["execution_status"], "success", result)
            self.assertEqual(result["model_turn_count"], 1)
            self.assertEqual(result["bridge_request_count"], 1)
            self.assertEqual(result["upstream_request_count"], 1)

    def test_route_phase_claims_before_call_and_blocks_replay(self):
        router = FakeRouter(route_decision())
        factory = RouterFactory(router)
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            decisions = Path(directory) / "decisions.jsonl"
            decisions.write_text("{}\n", encoding="ascii")
            decisions.chmod(0o600)
            result = spike.route_phase(
                state_dir=state,
                decisions_path=decisions,
                router_factory=factory,
                policy_validator=lambda _path: None,
                identity_validator=lambda *_args: ROUTER_IDENTITY,
                classification_validator=lambda _path: ROUTER_CLASSIFICATION,
                environment={"HOME": "/nonexistent"},
            )
            self.assertEqual(result, route_record())
            self.assertEqual(router.calls, [("route_task", dict(spike.ROUTE_ARGUMENTS))])
            self.assertEqual(factory.arguments[0][1], {"litellm_token": None})
            with self.assertRaises(spike.SpikeError):
                spike.route_phase(
                    state_dir=state,
                    decisions_path=decisions,
                    router_factory=factory,
                    policy_validator=lambda _path: None,
                    identity_validator=lambda *_args: ROUTER_IDENTITY,
                    classification_validator=lambda _path: ROUTER_CLASSIFICATION,
                    environment={"HOME": "/nonexistent"},
                )
            self.assertEqual(len(router.calls), 1)

    def test_execute_without_credential_persists_failure_without_invocation(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            spike.atomic_create_json(state / "route.json", route_record())
            sender = mock.Mock(side_effect=AssertionError("must not invoke"))
            result = spike.execute_phase(state_dir=state, input_dir=state, input_reader=spike.read_private_json, environment={}, upstream_sender=sender, expected_uid=os.getuid())
            self.assertEqual(result["execution_status"], "failure")
            self.assertEqual(result["failure_code"], "credential-directory-invalid")
            self.assertEqual(result["claim_state"], "claimed")
            self.assertFalse(result["request_issued"])
            sender.assert_not_called()

    def test_execute_replay_preserves_conservative_request_issued_residue(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            spike.atomic_create_json(state / "route.json", route_record())
            spike.create_claim(state / "execute.claim", DECISION_ID, "execute")
            spike.mark_claim_issued(state / "execute.claim", DECISION_ID, "execute")
            result = spike.execute_phase(state_dir=state, input_dir=state, input_reader=spike.read_private_json, environment={}, expected_uid=os.getuid())
            self.assertEqual(result["failure_code"], "execute-replay-blocked")
            self.assertEqual(result["claim_state"], "request-issued")
            self.assertTrue(result["request_issued"])
            self.assertEqual(result["model_turn_count"], 1)
            self.assertEqual(result["bridge_request_count"], 1)
            self.assertEqual(result["upstream_request_count"], 1)

    def test_outcome_is_tokenless_at_most_once_and_updates_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, handoff = root / "state", root / "handoff"
            state.mkdir(mode=0o700)
            route_raw = spike.atomic_create_json(handoff / "route.json", route_record())
            result = failure_result()
            result["route_reference_sha256"] = spike.sha256(route_raw)
            spike.atomic_create_json(handoff / "result.json", result)
            outcomes = Path(directory) / "outcomes.jsonl"
            outcomes.touch()
            outcomes.chmod(0o600)
            router = FakeRouter(acknowledgement={"recorded": True}, outcomes_path=outcomes)
            factory = RouterFactory(router)
            updated = spike.outcome_phase(
                state_dir=state,
                input_dir=handoff,
                input_reader=spike.read_private_json,
                outcomes_path=outcomes,
                router_factory=factory,
                identity_validator=lambda *_args: ROUTER_IDENTITY,
                classification_validator=lambda _path: ROUTER_CLASSIFICATION,
                environment={"HOME": "/nonexistent"},
            )
            self.assertEqual(updated["outcome_status"], "reported")
            self.assertTrue(updated["report_outcome_acknowledged"])
            self.assertIsNotNone(updated["report_outcome_record_sha256"])
            self.assertIsNone(updated["report_outcome_id"])
            self.assertEqual(spike.claim_states(state / "outcome.claim", "outcome", DECISION_ID), ["claimed", "report-issued"])
            self.assertEqual(router.calls[0][0], "report_outcome")
            self.assertEqual(router.calls[0][1]["outcome"], "failure")
            with self.assertRaises(spike.SpikeError):
                spike.outcome_phase(
                    state_dir=state,
                    input_dir=handoff,
                    input_reader=spike.read_private_json,
                    outcomes_path=outcomes,
                    router_factory=factory,
                    identity_validator=lambda *_args: ROUTER_IDENTITY,
                    classification_validator=lambda _path: ROUTER_CLASSIFICATION,
                    environment={"HOME": "/nonexistent"},
                )
            self.assertEqual(len(router.calls), 1)

    def test_outcome_reconciles_without_retry_and_rejects_missing_or_fabricated_state(self):
        for case in ("recorded", "missing", "fabricated"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                state, handoff = root / "state", root / "handoff"
                route_raw = spike.atomic_create_json(handoff / "route.json", route_record())
                authoritative = failure_result()
                authoritative["route_reference_sha256"] = spike.sha256(route_raw)
                spike.atomic_create_json(handoff / "result.json", authoritative)
                result = success_result() if case == "fabricated" else dict(authoritative)
                result.update({"route_reference_sha256": spike.sha256(route_raw), "outcome_status": "report-issued"})
                spike.atomic_create_json(state / "result.json", result)
                spike.create_claim(state / "outcome.claim", DECISION_ID, "outcome")
                spike.mark_claim_issued(state / "outcome.claim", DECISION_ID, "outcome")
                outcomes = Path(directory) / "outcomes.jsonl"
                outcomes.touch()
                outcomes.chmod(0o600)
                if case == "recorded":
                    append_outcome(outcomes, {"outcome": "failure", "notes": "OpenCode credential-isolated non-evidence spike failed: credential-directory-invalid"})
                router = FakeRouter()
                arguments = {"state_dir": state, "input_dir": handoff, "input_reader": spike.read_private_json, "outcomes_path": outcomes, "router_factory": RouterFactory(router), "identity_validator": lambda *_args: ROUTER_IDENTITY, "classification_validator": lambda _path: ROUTER_CLASSIFICATION, "environment": {"HOME": "/nonexistent"}}
                if case == "recorded":
                    updated = spike.outcome_phase(**arguments)
                    self.assertEqual(updated["outcome_status"], "reconciled")
                    self.assertFalse(updated["report_outcome_acknowledged"])
                    self.assertIsNotNone(updated["report_outcome_record_sha256"])
                else:
                    error = "outcome-input-invalid" if case == "fabricated" else "outcome-report-unresolved"
                    with self.assertRaisesRegex(spike.SpikeError, error):
                        spike.outcome_phase(**arguments)
                self.assertEqual(router.calls, [])

    def test_result_validator_and_schema_preserve_non_evidence(self):
        schema = load_json_strict(ROOT / "governance" / "schemas" / "opencode-spike-record.schema.json")
        failure = spike._base_result()
        success = success_result()
        for value in (failure, success):
            self.assertEqual(spike.validate_result_record(value), value)
            self.assertEqual(validate_schema(value, schema), [])
        for field, value in (
            ("runtime_adapter_ready", True),
            ("evidence_class", "evidence"),
            ("outcome_status", "reconciled"),
            ("report_outcome_record_sha256", "a" * 64),
            ("report_outcome_id", "claimed-id"),
            ("model_turn_count", 2),
            ("output_text", "WRONG"),
        ):
            item = success_result()
            item[field] = value
            with self.subTest(field=field), self.assertRaises(spike.SpikeError):
                spike.validate_result_record(item)
            self.assertNotEqual(validate_schema(item, schema), [])


if __name__ == "__main__":
    unittest.main()
