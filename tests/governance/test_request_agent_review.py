"""Tests for preserving broker responses through the Unix-socket workflow client."""

from __future__ import annotations

import json
import socket
import sys
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path

GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

from request_agent_review import request


class TestRequestAgentReview(unittest.TestCase):
    def test_structured_exhaustion_evidence_survives_http_503(self):
        payload = {"error": "exhausted", "route_evidence": {"attempts": [{"x": "y" * 2_000}]}}
        body = json.dumps(payload).encode()
        response = (
            b"HTTP/1.0 503 Service Unavailable\r\nContent-Type: application/json\r\nContent-Length: "
            + str(len(body)).encode() + b"\r\n\r\n" + body
        )
        with tempfile.TemporaryDirectory() as directory:
            socket_path = Path(directory) / "broker.sock"
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(str(socket_path))
            server.listen(1)

            def respond():
                connection, _ = server.accept()
                with connection:
                    connection.recv(65_536)
                    connection.sendall(response)
                server.close()

            thread = threading.Thread(target=respond)
            thread.start()
            result = request(socket_path, {"request": "review"})
            thread.join(timeout=5)
        self.assertEqual(result, payload)

    def test_oversized_response_is_rejected(self):
        fake = mock.Mock()
        fake.__enter__ = mock.Mock(return_value=fake)
        fake.__exit__ = mock.Mock(return_value=False)
        fake.recv.side_effect = [b"x" * 65_536] * 17
        with mock.patch("request_agent_review.socket.socket", return_value=fake), self.assertRaisesRegex(
            RuntimeError, "oversized"
        ):
            request(Path("/tmp/broker.sock"), {"request": "review"})

    def test_transfer_encoding_is_rejected(self):
        body = b'{"error":"exhausted","route_evidence":{}}'
        response = (
            b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: " + str(len(body)).encode()
            + b"\r\nTransfer-Encoding: chunked\r\n\r\n" + body
        )
        fake = mock.Mock()
        fake.__enter__ = mock.Mock(return_value=fake)
        fake.__exit__ = mock.Mock(return_value=False)
        fake.recv.side_effect = [response, b""]
        with mock.patch("request_agent_review.socket.socket", return_value=fake), self.assertRaisesRegex(
            RuntimeError, "transfer encoding"
        ):
            request(Path("/tmp/broker.sock"), {"request": "review"})

        malformed = response.replace(b"Transfer-Encoding:", b"Transfer-Encoding :")
        fake.recv.side_effect = [malformed, b""]
        with mock.patch("request_agent_review.socket.socket", return_value=fake), self.assertRaisesRegex(
            RuntimeError, "header syntax"
        ):
            request(Path("/tmp/broker.sock"), {"request": "review"})


if __name__ == "__main__":
    unittest.main()
