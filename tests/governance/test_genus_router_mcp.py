"""Tests for the persistent external genus-router MCP client boundary."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path
from types import SimpleNamespace

GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

from genus_router_mcp import TASK_KINDS, GenusRouterError, GenusRouterMCP, tool_error_json, tool_result_json, validate_tools


def route_schema() -> dict:
    return {
        "additionalProperties": False,
        "required": ["task_kind", "complexity"],
        "properties": {
            "task_kind": {"type": "string", "enum": list(TASK_KINDS)},
            "complexity": {"type": "string", "enum": ["trivial", "routine", "complex"]},
            "prior_failure": {"type": "boolean", "default": False},
            "awaited": {"type": "boolean", "default": False},
            "high_value": {"type": "boolean", "default": False},
            "independent_approval": {"type": "boolean", "default": False},
            "blast_radius": {"type": "string", "default": "isolated", "enum": ["isolated", "interface", "systemic"]},
            "task_summary": {"type": "string", "default": "", "maxLength": 500},
            "exclude_models": {"type": "array", "default": [], "items": {"type": "string"}},
        },
    }


class TestGenusRouterMCP(unittest.TestCase):
    def test_tool_result_accepts_structured_or_text_json_only(self):
        self.assertEqual(tool_result_json(SimpleNamespace(structuredContent={"recorded": True})), {"recorded": True})
        result = SimpleNamespace(structuredContent=None, content=[SimpleNamespace(text='{"recorded":true}')])
        self.assertEqual(tool_result_json(result), {"recorded": True})
        with self.assertRaises(GenusRouterError):
            tool_result_json(SimpleNamespace(structuredContent=None, content=[SimpleNamespace(text="not-json")]))
        error = SimpleNamespace(content=[SimpleNamespace(text='Error executing tool route_task: {"error":"no_candidates"}')])
        self.assertEqual(tool_error_json(error), {"error": "no_candidates"})

    def test_tool_discovery_requires_exact_set_and_closed_route_schema(self):
        tools = SimpleNamespace(tools=[
            SimpleNamespace(name="route_task", inputSchema=route_schema()),
            SimpleNamespace(name="report_outcome", inputSchema={}),
            SimpleNamespace(name="list_genera", inputSchema={}),
        ])
        validate_tools(tools)
        for mutation in ("extra", "duplicate", "open", "authority", "required", "false-default", "task-enum"):
            listed = list(tools.tools)
            schema = route_schema()
            if mutation == "extra":
                listed.append(SimpleNamespace(name="other", inputSchema={}))
            elif mutation == "duplicate":
                listed.append(SimpleNamespace(name="route_task", inputSchema=schema))
            elif mutation == "open":
                schema["additionalProperties"] = True
            elif mutation == "authority":
                schema["properties"]["model"] = {"type": "string"}
            elif mutation == "false-default":
                schema["properties"]["prior_failure"]["default"] = 0
            elif mutation == "task-enum":
                schema["properties"]["task_kind"]["enum"].append("forged")
            else:
                schema["required"] = ["complexity", "task_kind"]
            listed[0] = SimpleNamespace(name="route_task", inputSchema=schema)
            with self.subTest(mutation=mutation), self.assertRaises(GenusRouterError):
                validate_tools(SimpleNamespace(tools=listed))

    def test_configuration_requires_absolute_paths_and_full_sha(self):
        with self.assertRaises(GenusRouterError):
            GenusRouterMCP(Path("genus-router"), Path("config.yaml"), "a" * 40)
        with self.assertRaises(GenusRouterError):
            GenusRouterMCP(Path("/bin/true"), Path("/config.yaml"), "short")

    def test_litellm_token_is_explicitly_scoped_to_mcp_process(self):
        client = GenusRouterMCP(Path("/bin/true"), Path("/config.yaml"), "a" * 40, litellm_token="scoped-test-token")
        self.assertEqual(client.litellm_token, "scoped-test-token")

    def test_component_manifest_binds_command_and_config_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = root / "bin" / "genus-router"
            config = root / "config" / "router.yaml"
            command.parent.mkdir()
            config.parent.mkdir()
            command.write_text("#!/bin/sh\n", encoding="utf-8")
            command.chmod(0o500)
            config.write_text("routing: {}\n", encoding="utf-8")
            config.chmod(0o400)
            manifest = {
                "component_sha": "a" * 40,
                "command_sha256": hashlib.sha256(command.read_bytes()).hexdigest(),
                "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
            }
            manifest_path = root / "component-manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            manifest_path.chmod(0o400)
            client = GenusRouterMCP(command, config, "a" * 40)
            real_fstat = os.fstat

            def root_owned(descriptor):
                values = list(real_fstat(descriptor))
                values[4] = 0
                return os.stat_result(values)

            with mock.patch("genus_router_mcp.os.fstat", side_effect=root_owned), mock.patch.object(
                client, "_validate_identity_directories"
            ):
                client._validate_identity()
                config.chmod(0o600)
                config.write_text("routing: changed\n", encoding="utf-8")
                with self.assertRaises(GenusRouterError):
                    client._validate_identity()

                config.chmod(0o400)
                manifest_path.chmod(0o600)
                manifest_path.write_text('{"component_sha":"b","component_sha":"' + "a" * 40 + '"}', encoding="utf-8")
                manifest_path.chmod(0o400)
                with self.assertRaises(GenusRouterError):
                    client._validate_identity()

            with self.assertRaisesRegex(GenusRouterError, "root-owned"):
                client._validate_identity()

    def test_initialization_timeout_cancels_and_joins_thread(self):
        class SlowClient(GenusRouterMCP):
            def _validate_identity(self):
                return

            def _thread_main(self):
                async def wait_forever():
                    self._loop = asyncio.get_running_loop()
                    self._serve_task = asyncio.current_task()
                    await asyncio.Event().wait()

                try:
                    asyncio.run(wait_forever())
                except BaseException as error:
                    self._startup_error = error
                    self._ready.set()

        client = SlowClient(Path("/bin/true"), Path("/etc/hosts"), "a" * 40, timeout=0.05)
        with self.assertRaisesRegex(GenusRouterError, "initialization timed out"):
            client.start()
        self.assertIsNone(client._thread)
        self.assertFalse(any(thread.name == "genus-router-mcp" and thread.is_alive() for thread in threading.enumerate()))


if __name__ == "__main__":
    unittest.main()
