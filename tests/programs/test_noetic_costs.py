import contextlib
import http.client
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest import mock

from scripts import noetic_costs as costs
from scripts.noetic_application import ApplicationError


MARKDOWN = """# Supported model
## Pricing
### Text tokens
| Metric | Price | Unit |
| --- | ---: | --- |
| Input | $2 | 1M tokens |
| Cached input | $0.1 | 1M tokens |
| Cache writes | $2.5 | 1M tokens |
| Output | $10 | 1M tokens |

- Fast mode prices are 2x Standard.
"""


class App:
    def __init__(self, directory):
        self.root = Path(directory)
        self.namespace_path = self.root / "ordinals.sqlite3"
        with sqlite3.connect(self.namespace_path) as db:
            db.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT)")
            db.execute("INSERT INTO metadata VALUES('namespace','fixture-namespace')")

    def operation_scope(self, selection):
        if selection not in ({"kind": "application"}, {"kind": "effort", "effort_root": "0.0"},
                             {"kind": "effort", "effort_root": "0.1"}):
            raise ApplicationError(422, "Unknown fixture scope")

    def selection(self, body):
        return ({"kind": "effort", "effort_root": body["effort_root"]} if "effort_root" in body
                else {"kind": body["scope"]})

    @contextlib.contextmanager
    def mutation(self):
        yield


class CostsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.app = App(self.temporary.name)
        self.scope = {"kind": "effort", "effort_root": "0.0"}

    def request(self, **profile):
        return {"effort_root": "0.0", "expected_revision": 0, "refresh_prices": False,
                "profile": {"provider": "openai-codex", "model": "gpt-6.1-sol",
                            "billing_basis": "api", "currency": "USD", **profile}}

    def retrieved(self, provider, model, currency, basis):
        return {"state": "retrieved", "snapshot": {
            "rates": costs.parse_rates(MARKDOWN), "currency": "USD", "url": "https://fixture.invalid/model.md",
            "retrieved_at": "2026-10-13T01:00:00Z", "sha256": "fixture-sha", "raw_text": MARKDOWN,
            "assumptions": ["Standard API list-rate equivalent, not an actual bill"]}}

    def test_strict_rate_parser(self):
        self.assertEqual(costs.parse_rates(MARKDOWN), {"input": 2, "cache_read": .1, "cache_write": 2.5, "output": 10})
        for altered in (MARKDOWN.replace("1M tokens", "1K tokens", 1),
                        MARKDOWN.replace("| Output | $10 | 1M tokens |", ""),
                        MARKDOWN.replace("| Output | $10 | 1M tokens |", "| Output | $10 | 1M tokens |\n| Output | $12 | 1M tokens |")):
            with self.assertRaises(ValueError):
                costs.parse_rates(altered)

    def test_retrieval_raw_snapshot_parse_failure_and_unsupported_basis(self):
        with mock.patch.object(costs.request, "build_opener") as build:
            build.return_value.open.return_value = io.BytesIO(MARKDOWN.encode())
            result = costs.retrieve_rates("openai-codex", "gpt-6.1-sol", "USD", "api")
            self.assertEqual(result["state"], "retrieved")
            self.assertEqual(result["snapshot"]["raw_text"], MARKDOWN)
            self.assertEqual(result["snapshot"]["sha256"], hashlib.sha256(MARKDOWN.encode()).hexdigest())
            self.assertEqual(build.return_value.open.call_count, 1)
            unsupported = costs.retrieve_rates("openai-codex", "gpt-6.1-sol", "USD", "subscription")
            self.assertEqual(unsupported["state"], "unsupported")
            self.assertEqual(build.return_value.open.call_count, 1)
            build.return_value.open.return_value = io.BytesIO(b"Changed non-table source")
            failed = costs.retrieve_rates("openai", "gpt-6.1-sol", "USD", "api")
            self.assertEqual(failed["state"], "failed")
            self.assertEqual(failed["attempt"]["raw_text"], "Changed non-table source")

    def test_read_only_inspection_unknown_and_local_factors(self):
        result = costs.inspect(self.app, self.scope)
        self.assertEqual(result["revision"], 0)
        self.assertEqual(result["profiles"], [])
        self.assertFalse((self.app.root / ".cost-estimates.json").exists())
        result = costs.execute(self.app, self.request(billing_basis="local", factors={"runtime_seconds": 3600}))
        self.assertEqual(result["profiles"][0]["estimate"]["state"], "unknown")
        request = self.request(billing_basis="local", factors={"power_watts": 500, "electricity_per_kwh": .2})
        request["expected_revision"] = 1
        result = costs.execute(self.app, request)
        self.assertAlmostEqual(result["profiles"][0]["estimate"]["amount"], .1)

    def test_refresh_preserves_overrides_and_revision_conflict(self):
        request = self.request(overrides={"input": 1})
        request["refresh_prices"] = True
        result = costs.execute(self.app, request, retrieve=self.retrieved)
        profile = result["profiles"][0]
        self.assertEqual(profile["effective_rates"]["input"], 1)
        self.assertEqual(profile["effective_rates"]["output"], 10)
        with self.assertRaises(ApplicationError) as error:
            costs.execute(self.app, request, retrieve=lambda *args: self.fail("Stale request fetched"))
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(costs.inspect(self.app, self.scope)["revision"], 1)

    def test_failed_refresh_retains_snapshot_and_saves_factors(self):
        request = self.request(overrides={"cache_read": .03})
        request["refresh_prices"] = True
        first = costs.execute(self.app, request, retrieve=self.retrieved)
        request = self.request(factors={"output_multiplier": 2})
        request.update(expected_revision=1, refresh_prices=True)
        second = costs.execute(self.app, request, retrieve=lambda *args: {"state": "failed", "error": "fixture parse failure"})
        self.assertEqual(second["refresh"]["state"], "failed")
        self.assertEqual(second["factor_save"], "saved")
        self.assertEqual(second["profiles"][0]["fetched"], first["profiles"][0]["fetched"])
        self.assertEqual(second["profiles"][0]["overrides"], {"cache_read": .03})
        self.assertEqual(second["profiles"][0]["factors"], {"output_multiplier": 2})

    def test_scope_isolation_and_invalid_factor_before_write(self):
        costs.execute(self.app, self.request(billing_basis="subscription", factors={"allocation_cost": 7}))
        self.assertEqual(costs.inspect(self.app, {"kind": "effort", "effort_root": "0.1"})["profiles"], [])
        before = (self.app.root / ".cost-estimates.json").read_bytes()
        for value in (True, -1, float("nan"), float("inf"), 10 ** 1000):
            request = self.request(overrides={"input": value})
            request["expected_revision"] = 1
            with self.assertRaises(ApplicationError):
                costs.execute(self.app, request)
        self.assertEqual((self.app.root / ".cost-estimates.json").read_bytes(), before)
        with self.assertRaises(ApplicationError):
            costs.execute(self.app, self.request(), accounting={"selection": {"kind": "application"}, "rows": []})
        self.assertEqual((self.app.root / ".cost-estimates.json").read_bytes(), before)

    def test_additive_usage_matching_and_explicit_clear(self):
        accounting = {"rows": [{"provider": "openai-codex", "model": "gpt-6.1-sol",
                                "input": 100, "output": 10, "cacheRead": 40, "cacheWrite": 0}]}
        request = self.request(overrides={"input": 1, "output": 2})
        request["refresh_prices"] = True
        result = costs.execute(self.app, request, accounting=accounting, retrieve=self.retrieved)
        self.assertAlmostEqual(result["profiles"][0]["estimate"]["amount"], .000124)
        request = self.request(overrides={"input": None})
        request["expected_revision"] = 1
        result = costs.execute(self.app, request, accounting=accounting)
        self.assertNotIn("input", result["profiles"][0]["overrides"])
        self.assertEqual(result["profiles"][0]["effective_rates"]["input"], 2)
        accounting["rows"][0]["model"] = "other-model"
        self.assertEqual(costs.inspect(self.app, self.scope, accounting=accounting)["profiles"][0]["estimate"]["state"], "unknown")

    def test_partial_usage_and_overflow_remain_qualified(self):
        accounting = {"rows": [{"provider": "openai-codex", "model": "gpt-6.1-sol", "input": 10,
                                "output": 0, "cacheRead": 0, "cacheWrite": 0},
                               {"provider": "openai-codex", "model": "gpt-6.1-sol", "input": 10,
                                "output": 1, "cacheRead": None, "cacheWrite": 0}]}
        result = costs.execute(self.app, self.request(overrides={"input": 2}), accounting=accounting)
        estimate = result["profiles"][0]["estimate"]
        self.assertEqual(estimate["state"], "partial")
        self.assertEqual(estimate["covered_records"], 1)
        self.assertEqual(estimate["matched_records"], 2)
        self.assertAlmostEqual(estimate["amount"], .00002)
        self.assertIn("cacheRead", estimate["missing"])
        request = self.request(billing_basis="local", factors={"runtime_seconds": 1e308, "power_watts": 1e308, "electricity_per_kwh": 1})
        request["expected_revision"] = 1
        result = costs.execute(self.app, request)
        self.assertEqual(result["profiles"][1]["estimate"]["state"], "unknown")


class CostRoutesTests(unittest.TestCase):
    def test_inspect_explicit_execute_and_native_evidence_preservation(self):
        from scripts import noetic_web as web
        from scripts.noetic_sessions import SessionService
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs, namespace = root / "runs", root / "namespace.sqlite3"
            service = SessionService(runs, namespace_path=namespace)
            effort = service.create_effort({"intent": "Cost route fixture", "environment": {"cwd": directory}})["ordinal"]
            before = namespace.read_bytes()
            server = web.create_server(runs, namespace_path=namespace, port=0)
            server.RequestHandlerClass.log_message = lambda *args: None
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def call(path, body=None):
                    with contextlib.closing(http.client.HTTPConnection(*server.server_address, timeout=10)) as connection:
                        headers = {}
                        if body is not None:
                            headers["Content-Type"] = "application/json"
                        connection.request("GET" if body is None else "POST", path,
                                           body=None if body is None else json.dumps(body), headers=headers)
                        response = connection.getresponse()
                        return response.status, json.loads(response.read())
                self.assertEqual(call("/api/skills/cost-estimate")[0], 400)
                self.assertEqual(call("/api/skills/cost-estimate?effort_root=" + effort + "&effort_root=" + effort)[0], 400)
                code, read = call("/api/skills/cost-estimate?effort_root=" + effort)
                self.assertEqual(code, 200, read)
                self.assertEqual(read["skill"]["id"], "noetic:cost-estimate")
                self.assertFalse((runs / ".cost-estimates.json").exists())
                body = {"effort_root": effort, "expected_revision": 0, "refresh_prices": False,
                        "profile": {"provider": "fixture-provider", "model": "fixture-model", "currency": "USD",
                                    "billing_basis": "subscription", "factors": {"allocation_cost": 7}}}
                code, saved = call("/api/skills/cost-estimate/execute", body)
                self.assertEqual(code, 200, saved)
                self.assertEqual(saved["profiles"][0]["estimate"]["amount"], 7)
                self.assertEqual(call("/api/skills/cost-estimate/execute", body)[0], 409)
                self.assertEqual(namespace.read_bytes(), before)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
