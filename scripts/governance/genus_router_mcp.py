#!/usr/bin/env python3
"""Persistent official MCP client for the external genus-router process."""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import json
import os
import stat
import threading
from pathlib import Path
from typing import Any

TASK_KINDS = [
    "plan", "design", "orchestrate", "triage", "implement", "test", "review", "debug",
    "refactor", "research", "document", "summarize", "embed", "asr",
]


class GenusRouterError(RuntimeError):
    pass


class GenusRouterToolError(GenusRouterError):
    def __init__(self, tool: str, payload: Any) -> None:
        super().__init__(f"genus-router {tool} failed")
        self.tool = tool
        self.payload = payload


def tool_result_json(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    for content in getattr(result, "content", []):
        text = getattr(content, "text", None)
        if isinstance(text, str):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    raise GenusRouterError("genus-router tool result did not contain one JSON object")


def tool_error_json(result: Any) -> dict[str, Any]:
    for content in getattr(result, "content", []):
        text = getattr(content, "text", None)
        if isinstance(text, str) and "{" in text:
            try:
                parsed = json.loads(text[text.index("{"):])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    raise GenusRouterError("genus-router tool error did not contain one JSON object")


def validate_tools(tools: Any) -> None:
    listed = getattr(tools, "tools", None)
    if not isinstance(listed, list):
        raise GenusRouterError("genus-router tool discovery response is invalid")
    names = [getattr(tool, "name", None) for tool in listed]
    if any(type(name) is not str for name in names) or len(names) != len(set(names)):
        raise GenusRouterError("genus-router tool names are invalid or duplicated")
    by_name = dict(zip(names, listed, strict=True))
    if set(by_name) != {"list_genera", "report_outcome", "route_task"}:
        raise GenusRouterError("genus-router tool set is not canonical")
    schema = getattr(by_name["route_task"], "inputSchema", None)
    if not isinstance(schema, dict) or schema.get("additionalProperties") is not False:
        raise GenusRouterError("genus-router route_task schema is not closed")
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise GenusRouterError("genus-router route_task properties are invalid")
    forbidden = {"model", "reasoning_effort", "routing_profile"}
    if forbidden.intersection(properties):
        raise GenusRouterError("genus-router route_task permits caller-selected execution authority")
    if schema.get("required") != ["task_kind", "complexity"]:
        raise GenusRouterError("genus-router route_task required fields changed")
    expected = {
        "task_kind": ("string", None),
        "complexity": ("string", None),
        "prior_failure": ("boolean", False),
        "awaited": ("boolean", False),
        "high_value": ("boolean", False),
        "independent_approval": ("boolean", False),
        "blast_radius": ("string", "isolated"),
        "task_summary": ("string", ""),
        "exclude_models": ("array", []),
    }
    if set(properties) != set(expected):
        raise GenusRouterError("genus-router route_task property set changed")
    for name, (expected_type, expected_default) in expected.items():
        field = properties[name]
        if not isinstance(field, dict) or field.get("type") != expected_type:
            raise GenusRouterError(f"genus-router route_task {name} type changed")
        if expected_default is not None and (
            type(field.get("default")) is not type(expected_default) or field.get("default") != expected_default
        ):
            raise GenusRouterError(f"genus-router route_task {name} default changed")
    if properties["task_kind"].get("enum") != TASK_KINDS:
        raise GenusRouterError("genus-router route_task task_kind enum changed")
    if properties["complexity"].get("enum") != ["trivial", "routine", "complex"]:
        raise GenusRouterError("genus-router route_task complexity enum changed")
    if properties["blast_radius"].get("enum") != ["isolated", "interface", "systemic"]:
        raise GenusRouterError("genus-router route_task blast_radius enum changed")
    if properties["task_summary"].get("maxLength") != 500:
        raise GenusRouterError("genus-router route_task summary bound changed")
    if properties["exclude_models"].get("items") != {"type": "string"}:
        raise GenusRouterError("genus-router route_task exclusions changed")


class GenusRouterMCP:
    def __init__(
        self,
        command: Path,
        config: Path,
        component_sha: str,
        *,
        litellm_token: str | None = None,
        health_interval: float = 5.0,
        timeout: int = 30,
    ) -> None:
        if not command.is_absolute() or not config.is_absolute():
            raise GenusRouterError("genus-router command and config paths must be absolute")
        if not component_sha.isascii() or len(component_sha) != 40 or any(char not in "0123456789abcdef" for char in component_sha):
            raise GenusRouterError("genus-router component SHA must be a full lowercase SHA")
        self.command = command
        self.config = config
        self.component_sha = component_sha
        self.litellm_token = litellm_token
        self.health_interval = health_interval
        self.timeout = timeout
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._session: Any = None
        self._stop: asyncio.Event | None = None
        self._serve_task: asyncio.Task[Any] | None = None
        self._startup_error: BaseException | None = None

    def _validate_identity(self) -> None:
        self._validate_identity_directories()
        manifest_path = self.config.parent.parent / "component-manifest.json"
        try:
            manifest = json.loads(
                self._immutable_bytes(manifest_path),
                object_pairs_hook=lambda pairs: self._unique_object(pairs),
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GenusRouterError("genus-router component manifest is unavailable") from error
        expected = {"component_sha", "command_sha256", "config_sha256", "genus_table_sha256"}
        if type(manifest) is not dict or set(manifest) != expected or manifest.get("component_sha") != self.component_sha:
            raise GenusRouterError("genus-router component manifest is invalid")
        for path, field in (
            (self.command, "command_sha256"),
            (self.config, "config_sha256"),
            (self.config.parent / "genus_models.csv", "genus_table_sha256"),
        ):
            digest = hashlib.sha256(self._immutable_bytes(path)).hexdigest()
            if type(manifest.get(field)) is not str or manifest[field] != digest:
                raise GenusRouterError(f"genus-router {field} does not match the manifest")

    def _validate_identity_directories(self) -> None:
        for directory in {self.command.parent, self.config.parent, self.config.parent.parent}:
            try:
                metadata = os.stat(directory)
            except OSError as error:
                raise GenusRouterError("genus-router identity directory is unavailable") from error
            if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o022:
                raise GenusRouterError("genus-router identity directory is not root-owned and immutable")

    @staticmethod
    def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise GenusRouterError(f"duplicate component manifest key: {key}")
            result[key] = value
        return result

    @staticmethod
    def _immutable_bytes(path: Path) -> bytes:
        flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError as error:
            raise GenusRouterError("genus-router identity artifact is unavailable") from error
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise GenusRouterError("genus-router identity artifact is not a regular file")
            if metadata.st_uid != 0 or metadata.st_mode & 0o022:
                raise GenusRouterError("genus-router identity artifact is not root-owned and immutable")
            chunks = []
            total = 0
            while chunk := os.read(descriptor, 65_536):
                total += len(chunk)
                if total > 16_777_216:
                    raise GenusRouterError("genus-router identity artifact is oversized")
                chunks.append(chunk)
            return b"".join(chunks)
        except OSError as error:
            raise GenusRouterError("genus-router identity artifact is unreadable") from error
        finally:
            os.close(descriptor)

    def start(self) -> None:
        if self._thread is not None:
            raise GenusRouterError("genus-router client is already started")
        if not self.command.is_file() or not os.access(self.command, os.X_OK) or not self.config.is_file():
            raise GenusRouterError("genus-router executable or config is unavailable")
        self._validate_identity()
        self._thread = threading.Thread(target=self._thread_main, name="genus-router-mcp", daemon=True)
        self._thread.start()
        if not self._ready.wait(self.timeout):
            self.close()
            raise GenusRouterError("genus-router MCP initialization timed out")
        if self._startup_error is not None:
            raise GenusRouterError("genus-router MCP initialization failed") from self._startup_error

    def close(self) -> None:
        if self._loop is not None and self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)
        elif self._loop is not None and self._serve_task is not None:
            self._loop.call_soon_threadsafe(self._serve_task.cancel)
        if self._thread is not None:
            self._thread.join(self.timeout)
            if self._thread.is_alive():
                raise GenusRouterError("genus-router MCP shutdown timed out")
        self._thread = None

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self._loop is None or self._session is None or self._thread is None or not self._thread.is_alive():
            raise GenusRouterError("genus-router MCP session is unavailable")
        future = asyncio.run_coroutine_threadsafe(self._call_tool(name, arguments), self._loop)
        try:
            return future.result(self.timeout)
        except concurrent.futures.TimeoutError as error:
            future.cancel()
            raise GenusRouterError(f"genus-router {name} timed out") from error
        except GenusRouterError:
            raise
        except BaseException as error:
            raise GenusRouterError(f"genus-router {name} transport failed") from error

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = await self._session.call_tool(name, arguments)
        if getattr(result, "isError", False):
            raise GenusRouterToolError(name, tool_error_json(result))
        return tool_result_json(result)

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._serve())
        except BaseException as error:
            self._startup_error = error
            self._ready.set()

    async def _serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._serve_task = asyncio.current_task()
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        environment = {key: os.environ[key] for key in ("HOME", "PATH") if key in os.environ}
        token = self.litellm_token
        if token is not None:
            try:
                encoded = token.encode("utf-8")
            except UnicodeEncodeError as error:
                raise GenusRouterError("genus-router LiteLLM credential is not valid UTF-8") from error
            if not token or len(encoded) > 16_384 or any(ord(char) < 0x20 or ord(char) == 0x7F for char in token):
                raise GenusRouterError("genus-router LiteLLM credential is invalid")
            environment["LITELLM_API_KEY"] = token
        params = StdioServerParameters(
            command=str(self.command),
            args=["--config", str(self.config)],
            env=environment,
            cwd=self.config.parent.parent,
        )
        with open(os.devnull, "w", encoding="utf-8") as errlog:
            async with stdio_client(params, errlog=errlog) as (read, write), ClientSession(read, write) as session:
                await session.initialize()
                validate_tools(await session.list_tools())
                self._session = session
                self._stop = asyncio.Event()
                self._ready.set()
                while True:
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=self.health_interval)
                        break
                    except TimeoutError:
                        validate_tools(await session.list_tools())
                self._session = None

    def __enter__(self) -> GenusRouterMCP:
        self.start()
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any) -> None:
        self.close()
