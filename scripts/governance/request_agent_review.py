#!/usr/bin/env python3
"""Request one review from the local noetic-dev Terra broker."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path


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
        while chunk := client.recv(65_536):
            chunks.append(chunk)
    response = b"".join(chunks)
    header, separator, response_body = response.partition(b"\r\n\r\n")
    if not separator or b" 200 " not in header.split(b"\r\n", 1)[0]:
        raise RuntimeError(response_body.decode(errors="replace")[:1_000] or "review broker request failed")
    return json.loads(response_body)


def binding(result: dict[str, object]) -> dict[str, object]:
    fields = (
        "repository", "pr_number", "base_sha", "head_sha", "model", "reasoning",
        "reviewed_diff_sha256", "prompt_sha256", "run_url", "authority_context", "authority_status_id",
    )
    return {field: result[field] for field in fields}


def main() -> int:
    parser = argparse.ArgumentParser(description="Request immutable Terra PR review")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--socket", default=os.environ.get("NOETIC_AGENT_REVIEW_SOCKET", "/run/noetic-dev/agent-review.sock"))
    parser.add_argument("--output", default="agent-review-result.json")
    args = parser.parse_args()
    result = request(Path(args.socket), {
        "repository": args.repository,
        "pr_number": args.pr_number,
        "head_sha": args.head_sha,
        "base_sha": args.base_sha,
        "run_url": args.run_url,
    })
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Agent review: {result['verdict']} ({result['model']}, reasoning={result['reasoning']})")
    print("Agent review binding: " + json.dumps(binding(result), sort_keys=True, separators=(",", ":")))
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
