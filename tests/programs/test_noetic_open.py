"""Implementation checks: ephemeral loopback GUI, synthetic tokens, mocked browser handoff."""

from contextlib import closing, redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from scripts import noetic
from scripts import noetic_access as access
from scripts import noetic_release as release
from scripts import noetic_run as runtime
from scripts import noetic_web as web


TOKEN = "synthetic-owner-token-" + "a" * 32
ROOT = Path(__file__).resolve().parents[2]


class NoeticOpenTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="noetic-open-", dir="/tmp/opencode")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runs = self.root / ".runtime/runs"
        for context in (patch.dict(os.environ, {"NOETIC_STATE_HOME": ""}),
                        patch.object(Path, "cwd", return_value=self.root)):
            context.start()
            self.addCleanup(context.stop)

    def call(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                code = noetic.main(["open", *map(str, args)])
            except SystemExit as exc:
                code = exc.code
        output = stdout.getvalue() + stderr.getvalue()
        self.assertNotIn(TOKEN, output)
        self.assertNotIn("#token=", output)
        self.assertNotIn("Traceback", output)
        return code, stdout.getvalue(), stderr.getvalue()

    def token_file(self, relative=".runtime/.operator-access/token", content=TOKEN):
        path = self.root / relative
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        path.write_text(content + "\n", encoding="ascii")
        path.chmod(0o600)
        return path

    def inventory(self):
        # Reads can change atime; bytes, ownership, modes, links and write times must not change.
        result = {}
        for path in [self.root, *self.root.rglob("*")]:
            info = path.lstat()
            result[str(path.relative_to(self.root))] = (
                info.st_mode, info.st_uid, info.st_gid, info.st_nlink, info.st_size,
                info.st_mtime_ns, info.st_ctime_ns, path.read_bytes() if path.is_file() else None,
            )
        return result

    def start_server(self, server=None):
        server = server or web.create_server(self.runs, port=0, access_token=TOKEN)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def test_selectors_defaults_environment_and_explicit_override(self):
        cases = [
            ({}, [], self.runs, None, 8765),
            ({"NOETIC_STATE_HOME": str(self.root / "bound state")}, [],
             self.root / "bound state/runs", None, 8765),
            ({"NOETIC_STATE_HOME": str(self.root / "ignored")},
             ["--runs-dir", str(self.root / "selected/runs"), "--port", "9876"],
             self.root / "selected/runs", None, 9876),
            ({"NOETIC_STATE_HOME": str(self.root / "ignored"), "HOME": str(self.root)},
             ["--runs-dir=~/selected/runs", "--token-file=~/owner/token", "--port=8765"],
             self.root / "selected/runs", Path("~/owner/token"), 8765),
        ]
        before = self.inventory()
        for env, args, runs, token_file, port in cases:
            with self.subTest(args=args, env=env), patch.dict(os.environ, env):
                with patch.object(web, "open_workspace") as handoff:
                    self.assertEqual(self.call(*args)[0], 0)
                handoff.assert_called_once_with(token_file or runs.parent / ".operator-access/token", port)
        self.assertEqual(self.inventory(), before)

    def test_open_rejects_zero_or_invalid_port_before_reading_token(self):
        before = self.inventory()
        with patch.object(access, "read_token") as read_token:
            for port in ("0", "-1", "65536", "not-a-port"):
                with self.subTest(port=port):
                    code, stdout, stderr = self.call("--port", port)
                    self.assertEqual(code, 2)
                    self.assertEqual(stdout, "")
                    self.assertIn("--port", stderr)
            read_token.assert_not_called()
        self.assertEqual(self.inventory(), before)

    def test_serve_environment_token_creation_then_readonly_open(self):
        state = self.root / "bound state"
        with patch.dict(os.environ, {"NOETIC_STATE_HOME": str(state)}):
            with patch.object(access, "generate_token", return_value=TOKEN), \
                    patch.object(web.ThreadingHTTPServer, "serve_forever", side_effect=KeyboardInterrupt), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(noetic.main(["serve", "--port", "0"]), 0)
            path = state / ".operator-access/token"
            self.assertEqual(access.read_token(path), TOKEN)
            server = self.start_server(web.create_server(state / "runs", port=0, access_token=TOKEN))
            before = self.inventory()
            with patch.object(web.subprocess, "run") as browser:
                self.assertEqual(self.call("--port", server.server_port)[0], 0)
                browser.assert_called_once()
            self.assertEqual(self.inventory(), before)
            self.assertFalse((state / "runs").exists())

    def test_missing_token_and_parent_are_not_created_or_inferred(self):
        custom = self.token_file("home/.local/share/noetic-dev/operator-access/token")
        # An installed service's custom token is not a fallback for the serve default.
        for path in (None, self.root / "absent/parent/token", custom.with_name("missing")):
            with self.subTest(path=path), patch.object(web.subprocess, "run") as browser:
                before = self.inventory()
                code, stdout, stderr = self.call(*(["--token-file", path] if path else []))
                self.assertEqual(code, 1)
                self.assertEqual(stdout, "")
                self.assertIn("missing", stderr)
                self.assertIn("--token-file", stderr)
                browser.assert_not_called()
                self.assertEqual(self.inventory(), before)

    def test_invalid_content_and_permissions_are_not_repaired(self):
        cases = [(b"short\n", 0o600, 0o700), (TOKEN.encode() + b"\nextra", 0o600, 0o700),
                 (b"\xff\n", 0o600, 0o700), (TOKEN.encode(), 0o644, 0o700),
                 (TOKEN.encode(), 0o600, 0o777)]
        for index, (content, mode, parent_mode) in enumerate(cases):
            path = self.token_file(f"invalid-{index}/token")
            path.write_bytes(content)
            path.chmod(mode)
            path.parent.chmod(parent_mode)
            with self.subTest(index=index), patch.object(web.subprocess, "run") as browser:
                before = self.inventory()
                code, stdout, stderr = self.call("--token-file", path)
                self.assertEqual(code, 1)
                self.assertEqual(stdout, "")
                self.assertIn("operator token", stderr)
                self.assertEqual(self.inventory(), before)
                browser.assert_not_called()

    def test_existing_token_owner_validation_is_reused(self):
        path = self.token_file()
        before = self.inventory()
        with patch.object(access.os, "getuid", return_value=os.getuid() + 1):
            code, _, stderr = self.call("--token-file", path)
        self.assertEqual(code, 1)
        self.assertIn("owner-controlled", stderr)
        self.assertEqual(self.inventory(), before)

    def test_unavailable_listener_does_not_open_browser(self):
        self.token_file()
        before = self.inventory()
        # Reserve a real ephemeral port without listening, rather than probing production.
        with closing(socket.socket()) as unavailable, patch.object(web.subprocess, "run") as browser:
            unavailable.bind(("127.0.0.1", 0))
            code, stdout, stderr = self.call("--port", unavailable.getsockname()[1])
            browser.assert_not_called()
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Cannot reach the local GUI", stderr)
        self.assertIn("--port", stderr)
        self.assertEqual(self.inventory(), before)

    def test_gui_rejects_stale_but_well_formed_token_before_browser_handoff(self):
        self.token_file(content="b" * 43)
        server = self.start_server()
        before = self.inventory()
        with patch.object(web.subprocess, "run") as browser:
            code, stdout, stderr = self.call("--port", server.server_port)
            browser.assert_not_called()
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("rejected this operator token", stderr)
        self.assertIn("--token-file", stderr)
        self.assertEqual(self.inventory(), before)

    def test_readiness_failure_does_not_follow_redirects_or_use_environment_proxy(self):
        self.token_file()
        requests = []
        status = 302

        class Handler(BaseHTTPRequestHandler):
            def do_HEAD(self):
                requests.append((self.command, self.path, self.headers.get("Authorization")))
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Location", f"http://localhost:{self.server.server_port}/redirected")
                self.end_headers()

            def log_message(self, *args):
                pass

        server = self.start_server(ThreadingHTTPServer(("127.0.0.1", 0), Handler))
        before = self.inventory()
        proxy = f"http://localhost:{server.server_port}"
        with patch.dict(os.environ, {"http_proxy": proxy, "HTTP_PROXY": proxy, "no_proxy": "", "NO_PROXY": ""}):
            for status in (302, 503):
                with self.subTest(status=status), patch.object(web.subprocess, "run") as browser:
                    code, stdout, stderr = self.call("--port", server.server_port)
                    self.assertEqual(code, 1)
                    self.assertEqual(stdout, "")
                    self.assertIn(f"HTTP {status}", stderr)
                    browser.assert_not_called()
        self.assertEqual(requests, [("HEAD", "/api/runs", f"Bearer {TOKEN}")] * 2)
        self.assertEqual(self.inventory(), before)

    def test_custom_service_path_and_readonly_success_handoff(self):
        path = self.token_file("home/.local/share/noetic-dev/operator-access/token")
        runtime.create_run({"goal": "Synthetic opener history"}, self.root, self.runs)
        server = self.start_server()
        before = self.inventory()
        with patch.dict(os.environ, {"NOETIC_STATE_HOME": str(self.root / "ignored")}), \
                patch.object(access, "load_token", side_effect=AssertionError("Opener must not create tokens")), \
                patch.object(web.subprocess, "run") as browser:
            code, stdout, stderr = self.call("--runs-dir", self.runs, "--token-file", path,
                                             "--port", server.server_port)
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Browser handoff requested", stdout)
        self.assertIn("does not confirm a rendered or authenticated tab", stdout)
        command = browser.call_args.args[0]
        self.assertEqual(command[:3], [sys.executable, "-I", "-c"])
        self.assertEqual(command[-1], server.pairing_url)
        self.assertNotIn("?", command[-1])
        self.assertEqual(browser.call_args.kwargs, dict(
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=15, check=True))
        self.assertEqual(self.inventory(), before)
        self.assertFalse((self.runs.parent / ".operator-access").exists())

    def test_mocked_browser_in_real_child_cannot_leak_url_on_false_exception_or_success(self):
        self.token_file()
        server = self.start_server()
        before = self.inventory()
        real_run = subprocess.run
        for outcome in ("return False", "raise RuntimeError(url)", "return True"):
            # Only webbrowser.open is synthetic. The child process and stdout/stderr
            # descriptors are real; no desktop browser is launched by these checks.
            fixture = (
                "import os, sys, webbrowser\n"
                "def synthetic_open(url, **kwargs):\n"
                "    print(url, flush=True)\n"
                "    print(url, file=sys.stderr, flush=True)\n"
                "    os.write(1, url.encode())\n"
                "    os.write(2, url.encode())\n"
                f"    {outcome}\n"
                "webbrowser.open = synthetic_open\n"
            )

            def browser_child(command, **kwargs):
                self.assertEqual(command[-1], server.pairing_url)
                self.assertEqual(kwargs, dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                              stderr=subprocess.DEVNULL, timeout=15, check=True))
                return real_run([*command[:3], fixture + command[3], *command[4:]], **kwargs)

            with self.subTest(outcome=outcome), patch.object(web.subprocess, "run", side_effect=browser_child):
                code, stdout, stderr = self.call("--port", server.server_port)
                self.assertEqual(code, 0 if outcome == "return True" else 1)
                if code:
                    self.assertEqual(stdout, "")
                    self.assertIn("local graphical session", stderr)
                else:
                    self.assertEqual(stderr, "")
                    self.assertIn("Browser handoff requested", stdout)
                self.assertEqual(self.inventory(), before)

    def test_launcher_error_and_timeout_do_not_print_exception_with_pairing_url(self):
        self.token_file()
        server = self.start_server()
        before = self.inventory()
        for error in (OSError(server.pairing_url), subprocess.TimeoutExpired(server.pairing_url, 15)):
            with self.subTest(error=type(error).__name__), patch.object(web.subprocess, "run", side_effect=error):
                code, stdout, stderr = self.call("--port", server.server_port)
                self.assertEqual(code, 1)
                self.assertEqual(stdout, "")
                self.assertIn("Browser handoff failed or was refused", stderr)
                self.assertEqual(self.inventory(), before)

    def test_wheel_opener_and_release_bootstrap_import_without_checkout_or_install(self):
        source = self.root / "source"
        shutil.copytree(ROOT / "scripts", source / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("pyproject.toml", "LICENSE.md"):
            shutil.copyfile(ROOT / name, source / name)
        built = subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-build-isolation", "--no-deps",
                                "--no-index", "--wheel-dir", str(self.root), str(source)],
                               capture_output=True, text=True, timeout=60)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        wheel = next(self.root.glob("*.whl"))
        version, bootstrap = release.wheel_info(wheel.read_bytes(), wheel.name)
        self.assertEqual(version, noetic.VERSION)
        bootstrap_zip = self.root / "bootstrap.zip"
        with zipfile.ZipFile(bootstrap_zip, "w") as archive:
            for name, content in bootstrap.items():
                archive.writestr(name, content)
        env = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "PYTHONHOME")}
        for archive, module, args in (
                (wheel, "scripts.noetic", ["open", "--help"]),
                (wheel, "scripts.noetic", ["serve", "--help"]),
                (bootstrap_zip, "scripts.noetic_release", ["--help"])):
            with self.subTest(module=module, args=args):
                result = subprocess.run([sys.executable, "-B", "-S", "-m", module, *args],
                                        env={**env, "PYTHONPATH": str(archive)}, cwd=self.root,
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("usage:", result.stdout)


if __name__ == "__main__":
    unittest.main()
