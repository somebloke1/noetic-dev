#!/usr/bin/env python3
"""Request one review from the local noetic-dev Terra broker."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
from pathlib import Path

MAX_RESPONSE_BYTES = 1_048_576


def request(socket_path: Path, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload, separators=(",", ":")).encode()
    wire = (
        b"POST /review HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: "
        + str(len(body)).encode()
        + b"\r\nConnection: close\r\n\r\n"
        + body
    )
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(1_000)
        client.connect(str(socket_path))
        client.sendall(wire)
        chunks = []
        received = 0
        while chunk := client.recv(65_536):
            received += len(chunk)
            if received > MAX_RESPONSE_BYTES:
                raise RuntimeError("review broker response is oversized")
            chunks.append(chunk)
    response = b"".join(chunks)
    header, separator, response_body = response.partition(b"\r\n\r\n")
    if not separator:
        raise RuntimeError("review broker response framing is invalid")
    header_lines = header.split(b"\r\n")
    status_line = header_lines[0]
    if any(not re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+:[\t\x20-\x7e]*", line) for line in header_lines[1:]):
        raise RuntimeError("review broker response header syntax is invalid")
    lengths = [
        line.split(b":", 1)[1].strip()
        for line in header_lines[1:]
        if line.lower().startswith(b"content-length:")
    ]
    if any(line.lower().startswith(b"transfer-encoding:") for line in header_lines[1:]):
        raise RuntimeError("review broker response transfer encoding is forbidden")
    if len(lengths) != 1 or not lengths[0].isdigit() or int(lengths[0]) != len(response_body):
        raise RuntimeError("review broker response length is invalid")
    parsed = json.loads(response_body)
    if b" 200 " in status_line:
        return parsed
    if b" 503 " in status_line and isinstance(parsed, dict) and "route_evidence" in parsed:
        return parsed
    raise RuntimeError(response_body.decode(errors="replace")[:1_000] or "review broker request failed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Request immutable Terra PR review")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--socket", default=os.environ.get("NOETIC_AGENT_REVIEW_SOCKET", "/run/noetic-dev/agent-review.sock"))
    parser.add_argument("--output", default="agent-review-result.json")
    args = parser.parse_args()
    result = request(Path(args.socket), {
        "repository": args.repository,
        "pr_number": args.pr_number,
        "head_sha": args.head_sha,
        "base_sha": args.base_sha,
    })
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if "route_evidence" in result and "verdict" not in result:
        print(f"Agent review failed: {result.get('error', 'routed review exhausted')}", file=sys.stderr)
        return 2
    print(f"Agent review: {result['verdict']} ({result['model']}, reasoning={result['reasoning']})")
    print(result["summary"])
    for finding in result["findings"]:
        location = f"{finding['file']}:{finding['line']}" if finding["line"] else finding["file"]
        print(f"- {finding['severity']} {location}: {finding['message']}")
    return 0 if result["verdict"] == "pass" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Agent review failed: {error}", file=sys.stderr)
        raise SystemExit(2)
