"""Bounded implementation checks, not independent QA; live trial is explicit opt-in."""

from contextlib import closing, redirect_stdout
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from scripts import noetic_controller as controller
from scripts import noetic_local as local
from scripts import noetic_run as runtime
from scripts import noetic_semantic as semantic


def legacy_fixture(root, runs, goal="Bicycle punctures need a tire patch."):
    with redirect_stdout(io.StringIO()):
        run_dir = runtime.create_run({"goal": goal}, root, runs)
    (run_dir / "work.md").write_text("Tomato seedlings need sunlight and water.", encoding="utf-8")
    (run_dir / "review.md").write_text("Bread dough needs yeast and flour.", encoding="utf-8")
    return run_dir


def submit_fixture(store, result):
    state = controller.inspect_run(store)
    activation_id = state["current_activation"]
    state = controller.begin_activation(store, activation_id, state["version"])
    return controller.submit_result(store, activation_id, state["version"], result,
                                    f"fixture-session:{activation_id}", f"fixture-command:{activation_id}")


def controller_fixture(root, runs, kind="development"):
    with redirect_stdout(io.StringIO()):
        run_dir = runtime.create_run({"goal": "Nonsecret fixture: document bicycle repair."}, root, runs)
    controller.start_run(run_dir / "controller.sqlite3", controller.PATTERN_DIR / f"{kind}.json",
                         "Nonsecret test-authored fixture: document bicycle puncture repair.", root)
    return run_dir


def design_result(objective):
    return {"outcome": "produced", "content": {"objective": objective, "scope": ["fixture only"],
                                               "acceptance_criteria": ["Explain patching a puncture"]}}


def review_result(state, verdict="pass"):
    return {"subject_artifact_id": state["subject_artifact_id"], "verdict": verdict,
            "report": "Test-authored fixture review, not independent QA evidence.",
            "findings": [] if verdict == "pass" else [{"description": "Missing patch instructions", "blocking": True}]}


class LocalSupportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runs = self.root / "runs"
        self.calls = []
        self.failure = None
        self.delay = 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.calls.append((self.path, data))
                if owner.delay:
                    time.sleep(owner.delay)
                status = 503 if owner.failure == "http" else 200
                if owner.failure == "http":
                    body = b"private gateway body fixture-key MUST NOT BE SHOWN"
                elif owner.failure == "json":
                    body = b"not json; fixture-key"
                elif owner.failure == "shape":
                    body = b'{"data": [null], "choices": []}'
                elif self.path == "/v1/chat/completions":
                    prompt = json.loads(data["messages"][-1]["content"]) if data["messages"][-1]["content"].startswith("{") else None
                    text = "Fixture supporting summary"
                    if prompt:
                        text += " [" + prompt["sources"][0]["source_id"] + "]"
                    body = json.dumps({"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                                       "usage": {"completion_tokens": 12}}).encode()
                else:
                    vectors = []
                    for index, text in enumerate(data["input"]):
                        lowered = text.lower()
                        values = [float(any(term in lowered for term in terms)) for terms in
                                  (("bicycle", "tire", "puncture"), ("tomato", "seedling"), ("bread", "yeast"))]
                        if not any(values):
                            values = [1, 1, 1]
                        if owner.failure == "dimension":
                            values.pop()
                        elif owner.failure == "nan":
                            values[0] = float("nan")
                        elif owner.failure == "infinity":
                            values[0] = float("inf")
                        elif owner.failure == "zero":
                            values = [0, 0, 0]
                        vectors.append({"index": index, "embedding": values})
                    if owner.failure == "index":
                        vectors[0]["index"] = 99
                    if owner.failure == "count":
                        vectors = []
                    body = json.dumps({"data": list(reversed(vectors))}).encode()
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        self.environment = patch.dict("os.environ", {"LITELLM_API_KEY": "fixture-key"}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.settings = local.Settings(base_url=f"http://127.0.0.1:{server.server_port}/v1", dimensions=3)
        self.client = local.LocalClient(self.settings)
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)

    def test_batching_query_prefix_order_and_normalization(self):
        inputs = ["bicycle", "tomato", "bread", "bicycle tomato", "bread"]
        vectors = self.client.embed(inputs)
        self.assertEqual([len(call[1]["input"]) for call in self.calls], [2, 2, 1])
        self.assertEqual(vectors[:3], [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        self.assertTrue(all(math.isclose(math.hypot(*v), 1) for v in vectors))
        self.client.embed(["tire repair"], query=True)
        self.assertEqual(self.calls[-1][1]["input"], ["query: tire repair"])
        self.assertEqual(self.calls[0][1]["input"], inputs[:2])

    def test_utf8_chunking_and_oversize_rejection_before_requests(self):
        text = "alpha\n" + "\u03bb\U0001f30d" * 700
        parts = list(semantic.chunks(text, 31))
        self.assertEqual("".join(part[2] for part in parts), text)
        for start, end, part in parts:
            self.assertLessEqual(end - start, 31)
            self.assertEqual(text.encode()[start:end].decode(), part)
        with self.assertRaises(local.LocalError):
            self.client.embed(["x" * (self.settings.input_byte_limit + 1)])
        with self.assertRaises(local.LocalError):
            self.client.embed(["x" * self.settings.input_byte_limit], query=True)
        for invalid in ([""], [" "], [None]):
            with self.assertRaises(local.LocalError):
                self.client.embed(invalid, query=True)
        self.assertEqual(self.calls, [])
        for change in ({"timeout": float("nan")}, {"batch_size": 17}, {"max_tokens": 2049},
                       {"chunk_bytes": 3000}, {"dimensions": 0}):
            with self.assertRaises(local.LocalError):
                replace(self.settings, **change)

    def test_http_and_protocol_failures_are_controlled_without_retry(self):
        for failure in ("http", "json", "shape", "dimension", "nan", "infinity", "zero", "index", "count"):
            with self.subTest(failure=failure):
                self.failure = failure
                before = len(self.calls)
                with self.assertRaises(local.LocalError) as caught:
                    self.client.embed(["bicycle"])
                self.assertEqual(len(self.calls), before + 1)
                self.assertNotIn("fixture-key", str(caught.exception))
                self.assertNotIn("private gateway body", str(caught.exception))
        self.failure = None
        with patch.dict("os.environ", {}, clear=True), self.assertRaisesRegex(local.LocalError, "credential"):
            self.client.embed(["bicycle"])

    def test_timeout_is_bounded_and_no_retry(self):
        self.delay = 0.15
        client = local.LocalClient(replace(self.settings, timeout=0.03))
        with self.assertRaisesRegex(local.LocalError, "timed out"):
            client.embed(["bicycle"])
        self.assertEqual(len(self.calls), 1)

    def test_config_environment_and_explicit_precedence(self):
        config = self.root / "config.json"
        config.write_text(json.dumps({"access": {"base_url": self.settings.base_url}, "inference": {"model": "configured-text"},
                                      "embedding": {"model": "configured-embed", "dimensions": 3,
                                                    "source_model_layer_sha256": "fixture-model-revision"}}))
        settings = local.load_settings(config)
        self.assertEqual(settings.text_model, "configured-text")
        self.assertEqual(settings.embedding_model, "configured-embed")
        self.assertEqual(settings.source_model_layer_sha256, "fixture-model-revision")
        with patch.dict("os.environ", {"NOETIC_LOCAL_TEXT_MODEL": "env-text", "NOETIC_LOCAL_DIMENSIONS": "5"}):
            self.assertEqual(local.load_settings(config).text_model, "env-text")
            self.assertEqual(local.load_settings(config, text_model="explicit").text_model, "explicit")
            self.assertEqual(local.load_settings(config).dimensions, 5)

    def test_incremental_cache_reuses_duplicate_text_updates_and_deletes(self):
        run_dir = legacy_fixture(self.root, self.runs)
        with patch.object(local.memory, "index_runs", wraps=local.memory.index_runs) as collector:
            first = semantic.index_runs(self.db, self.runs, self.client)
        collector.assert_called_once()
        self.assertEqual((first["chunks"], first["embedded_texts"], first["embedding_requests"]), (3, 3, 2))
        second = semantic.index_runs(self.db, self.runs, self.client)
        self.assertEqual(second["embedded_texts"], 0)
        self.assertEqual(len(self.calls), 2)
        (run_dir / "review.md").write_text((run_dir / "work.md").read_text())
        result = semantic.index_runs(self.db, self.runs, self.client)
        self.assertEqual((result["chunks"], result["unique_texts"], result["embedded_texts"]), (3, 2, 0))
        (run_dir / "work.md").write_text("Fresh bicycle patching instructions")
        self.assertEqual(semantic.index_runs(self.db, self.runs, self.client)["embedded_texts"], 1)
        runtime.record(run_dir, "run.finished", {"state": "awaiting_review"})
        self.assertEqual(semantic.index_runs(self.db, self.runs, self.client)["embedded_texts"], 0)
        results = semantic.search(self.db, "tire repair", self.client)
        self.assertTrue(all(row["state"] == "awaiting_review" for row in results))
        (run_dir / "work.md").unlink()
        self.assertEqual(semantic.index_runs(self.db, self.runs, self.client)["chunks"], 2)
        shutil.rmtree(run_dir)
        self.assertEqual(semantic.index_runs(self.db, self.runs, self.client)["chunks"], 0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM semantic_vectors").fetchone()[0], 0)

    def test_identity_changes_refuse_mixing_and_explicit_reindex(self):
        legacy_fixture(self.root, self.runs)
        semantic.index_runs(self.db, self.runs, self.client)
        for change in ({"embedding_model": "other-alias"}, {"source_model_layer_sha256": "revision-2"},
                       {"pooling": "other"}, {"preprocessing_version": "v2"}, {"chunk_bytes": 512}):
            client = local.LocalClient(replace(self.settings, **change))
            before = len(self.calls)
            with self.assertRaisesRegex(local.LocalError, "identity mismatch"):
                semantic.index_runs(self.db, self.runs, client)
            with self.assertRaisesRegex(local.LocalError, "identity mismatch"):
                semantic.search(self.db, "bicycle", client)
            self.assertEqual(len(self.calls), before)
        client = local.LocalClient(replace(self.settings, preprocessing_version="v2"))
        self.assertEqual(semantic.index_runs(self.db, self.runs, client, reindex=True)["embedded_texts"], 3)
        self.assertEqual(semantic.index_runs(self.db, self.runs, client)["embedded_texts"], 0)
        self.assertEqual(json.loads(self.db.execute("SELECT identity FROM semantic_meta").fetchone()[0])["preprocessing"], "v2")

    def test_failed_refresh_keeps_cache_but_does_not_return_stale_results(self):
        run_dir = legacy_fixture(self.root, self.runs)
        semantic.index_runs(self.db, self.runs, self.client)
        before = list(self.db.iterdump())
        (run_dir / "work.md").write_text("Changed document")
        self.failure = "http"
        with self.assertRaises(local.LocalError):
            semantic.index_runs(self.db, self.runs, self.client)
        self.assertEqual(list(self.db.iterdump()), before)
        output = io.StringIO()
        with redirect_stdout(output):
            status = semantic.main(["search", "bicycle", "--runs-dir", str(self.runs),
                                    "--base-url", self.settings.base_url, "--dimensions", "3", "--json"])
        self.assertEqual(status, 1)
        self.assertFalse(json.loads(output.getvalue())["lexical_fallback"])
        self.assertNotIn("private gateway body", output.getvalue())

    def test_ranking_attribution_and_no_accidental_authority_database_write(self):
        run_dir = legacy_fixture(self.root, self.runs)
        semantic.index_runs(self.db, self.runs, self.client)
        results = semantic.search(self.db, "tire repair", self.client, limit=1)
        self.assertEqual(results[0]["source"], "run.created.plan.goal")
        self.assertEqual(results[0]["event_sequence"], 1)
        self.assertEqual(results[0]["source_path"], str(run_dir / "events.sqlite3"))
        self.assertIn(run_dir.name, results[0]["source_id"])
        self.assertEqual(results[0]["scope"], "current")
        self.assertFalse(results[0]["authoritative"])
        with closing(sqlite3.connect(run_dir / "events.sqlite3")) as db:
            before = list(db.iterdump())
            with self.assertRaisesRegex(local.LocalError, "separate --db"):
                semantic.index_runs(db, self.runs, self.client)
            self.assertEqual(list(db.iterdump()), before)

    def test_cached_vectors_must_be_finite_correct_dimension_and_normalized(self):
        legacy_fixture(self.root, self.runs)
        semantic.index_runs(self.db, self.runs, self.client)
        for invalid in ([1, 0], [2, 0, 0], [float("nan"), 0, 0]):
            with self.db:
                self.db.execute("UPDATE semantic_vectors SET vector=?", (json.dumps(invalid),))
            with self.assertRaises(local.LocalError):
                semantic.index_runs(self.db, self.runs, self.client)
        self.assertEqual(semantic.index_runs(self.db, self.runs, self.client, reindex=True)["embedded_texts"], 3)

    def test_cli_success_refreshes_and_json_diagnostics_do_not_dump_vectors(self):
        legacy_fixture(self.root, self.runs)
        common = ["--base-url", self.settings.base_url, "--dimensions", "3"]
        output = io.StringIO()
        with redirect_stdout(output):
            status = semantic.main(["search", "tire repair", "--runs-dir", str(self.runs), "--limit", "1", "--json", *common])
        self.assertEqual(status, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["index"]["embedded_texts"], 3)
        self.assertEqual(result["results"][0]["field"], "goal")
        output = io.StringIO()
        with redirect_stdout(output):
            status = local.main(["diagnose", "embedding", *common])
        self.assertEqual(status, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["dimensions"], 3)
        self.assertTrue(result["finite"])
        self.assertNotIn("vectors", result)
        self.failure = "shape"
        with self.assertRaises(local.LocalError):
            self.client.complete("nonsecret fixture")

    def test_current_controller_bindings_and_their_qa_not_stale_exports(self):
        run_dir = controller_fixture(self.root, self.runs)
        store = run_dir / "controller.sqlite3"
        state = submit_fixture(store, design_result("STALE_REJECTED_DESIGN"))
        stale_id = state["subject_artifact_id"]
        submit_fixture(store, review_result(state, "fail"))
        state = submit_fixture(store, design_result("Current accepted bicycle patch instructions"))
        current_id = state["subject_artifact_id"]
        state = submit_fixture(store, review_result(state))
        (run_dir / "work.md").write_text("STALE_EXPORTED_HISTORY")
        sources = local.collect_runs(self.runs)[0]
        self.assertEqual(sources["sources"][0]["source"], "external.purpose")
        text = local.canonical(sources)
        self.assertNotIn("STALE_", text)
        self.assertNotIn(stale_id, [source["artifact_id"] for source in sources["sources"]])
        self.assertIn(current_id, [source["artifact_id"] for source in sources["sources"]])
        self.assertEqual(sum(source["artifact_type"] == "qa.review" for source in sources["sources"]), 1)
        for source in sources["sources"]:
            self.assertEqual(source["source_path"], str(store))
            self.assertTrue(source["event_id"].startswith("event-"))
        self.assertGreater(sources["excluded_artifacts"], 0)
        semantic.index_runs(self.db, self.runs, self.client)
        self.assertEqual(controller.inspect_run(store), state)
        self.assertNotIn("STALE_", local.canonical(self.calls))

    def test_cognitive_return_invalidates_effective_artifact_in_cache(self):
        run_dir = controller_fixture(self.root, self.runs, "cognition")
        store = run_dir / "controller.sqlite3"
        state = submit_fixture(store, {"outcome": "advance", "content": {
            "observations": ["OLD_OBSERVATION"], "questions": [], "evidence_refs": []}})
        old = state["slots"]["effective.P1"]
        semantic.index_runs(self.db, self.runs, self.client)
        submit_fixture(store, {"outcome": "return", "content": {"hypotheses": ["Need more evidence"]},
                               "target": "P1", "reason": "Insufficient observation", "question": "Which patch?"})
        semantic.index_runs(self.db, self.runs, self.client)
        results = semantic.search(self.db, "bicycle", self.client)
        self.assertNotIn(old, [row["artifact_id"] for row in results])
        self.assertFalse(any("OLD_OBSERVATION" in row["snippet"] for row in results))

    def test_summary_coverage_saved_observation_and_no_authority_mutation(self):
        run_dir = controller_fixture(self.root, self.runs)
        store = run_dir / "controller.sqlite3"
        state = submit_fixture(store, design_result("Bicycle repair " * 3000))
        state = submit_fixture(store, review_result(state))
        controller_before = store.read_bytes()
        (run_dir / "work.md").write_text("HISTORICAL_EXPORT_NOT_INPUT")
        (run_dir / "telos-link.json").write_text('{"fixture": "unchanged"}')
        result = local.summarize_run(run_dir, self.client, save=True, max_input_bytes=4000)
        self.assertTrue(result["model_generated"])
        self.assertFalse(result["authoritative"])
        self.assertFalse(result["advances_state"])
        self.assertFalse(result["citations_verified"])
        self.assertTrue(result["observation_recorded"])
        self.assertGreater(result["coverage"]["truncated_sources"] + result["coverage"]["omitted_sources"], 0)
        self.assertLessEqual(result["coverage"]["prompt_bytes"], 4000)
        request = self.calls[-1][1]
        self.assertFalse(request["chat_template_kwargs"]["enable_thinking"])
        self.assertEqual(request["max_tokens"], 512)
        self.assertNotIn("HISTORICAL_EXPORT", local.canonical(request))
        self.assertEqual(store.read_bytes(), controller_before)
        self.assertEqual(controller.inspect_run(store), state)
        self.assertEqual((run_dir / "telos-link.json").read_text(), '{"fixture": "unchanged"}')
        events = runtime.read_events(run_dir)
        self.assertEqual(events[-1]["kind"], "local.summary.observed")
        self.assertEqual(events[-1]["data"]["sha256"], local.digest((run_dir / "summary.json").read_text()))
        self.assertNotIn("observation_recorded", json.loads((run_dir / "summary.json").read_text()))
        sources = local.collect_runs(self.runs)[0]["sources"]
        self.assertFalse(any(source["source_path"].endswith("summary.json") for source in sources))

    def test_summary_without_observation_journal_and_failed_append_reported(self):
        run_dir = controller_fixture(self.root, self.runs)
        journal = run_dir / "events.sqlite3"
        journal.unlink()
        result = local.summarize_run(run_dir, self.client, save=True)
        self.assertTrue(result["saved"])
        self.assertFalse(result["observation_recorded"])
        self.assertFalse(journal.exists())
        journal.write_bytes(b"not a SQLite journal")
        result = local.summarize_run(run_dir, self.client, save=True)
        self.assertTrue(result["saved"])
        self.assertFalse(result["observation_recorded"])
        self.assertIn("observation_warning", result)
        self.assertEqual(journal.read_bytes(), b"not a SQLite journal")

    def test_legacy_summary_retained_review_and_no_save_is_read_only(self):
        run_dir = legacy_fixture(self.root, self.runs)
        runtime.record(run_dir, "run.finished", {"state": "awaiting_review"})
        runtime.review_run(run_dir, "reject", "fixture reviewer", run_dir / "review.md")
        (run_dir / "review.md").unlink()
        before = (run_dir / "events.sqlite3").read_bytes()
        result = local.summarize_run(run_dir, self.client)
        self.assertEqual(result["storage"], "legacy")
        self.assertIn("review.recorded.evidence", [source["source"] for source in result["sources"]])
        self.assertEqual((run_dir / "events.sqlite3").read_bytes(), before)
        self.assertFalse((run_dir / "summary.json").exists())
        self.assertEqual(runtime.project(runtime.read_events(run_dir))["state"], "rejected")

    def test_corrupt_controller_never_falls_back_to_legacy_and_empty_runs_need_no_model(self):
        self.assertEqual(semantic.index_runs(self.db, self.runs, self.client)["chunks"], 0)
        self.assertEqual(semantic.search(self.db, "bicycle", self.client), [])
        self.assertEqual(self.calls, [])
        run_dir = legacy_fixture(self.root, self.runs)
        (run_dir / "controller.sqlite3").write_text("not SQLite")
        with self.assertRaises(sqlite3.Error):
            local.summarize_run(run_dir, self.client)
        self.assertEqual(self.calls, [])


def live_trial(config=None):
    """Exactly one tiny embedding-search trial and one Qwen summary; no real-run writes."""
    settings = local.load_settings(config, base_url="http://127.0.0.1:3333/v1", max_tokens=512, timeout=60, batch_size=2)
    client = local.LocalClient(settings)
    with tempfile.TemporaryDirectory(prefix="noetic-local-trial-", dir="/tmp/opencode") as temporary:
        root = Path(temporary)
        run_dir = legacy_fixture(root, root / "retrieval-runs")
        started = time.monotonic()
        with closing(sqlite3.connect(root / "semantic.sqlite3")) as db:
            indexed = semantic.index_runs(db, run_dir.parent, client)
            matches = semantic.search(db, "How do I fix a flat bicycle tire?", client, limit=3)
            elapsed = round(time.monotonic() - started, 3)
            cached = semantic.index_runs(db, run_dir.parent, client)
        summary_run = controller_fixture(root, root / "summary-runs")
        store = summary_run / "controller.sqlite3"
        state = submit_fixture(store, design_result("Explain removing the tire, locating the puncture, and applying a patch."))
        before = submit_fixture(store, review_result(state))
        summary = local.summarize_run(summary_run, client)
        unchanged = controller.inspect_run(store) == before and not (summary_run / "summary.json").exists()
        return {"fixture_only": True, "embedding_seconds": elapsed, "indexed_documents": indexed["chunks"],
                "document_embedding_requests": indexed["embedding_requests"], "cache_refresh_embedding_requests": cached["embedding_requests"],
                "embedding_dimensions": settings.dimensions, "matches": matches, "summary": summary,
                "controller_unchanged": unchanged, "limits": "Tiny functional trial only; not a quality or throughput benchmark."}


if __name__ == "__main__":
    if "--live-trial" in sys.argv:
        try:
            print(local.canonical(live_trial(sys.argv[2] if len(sys.argv) > 2 else None)))
        except (local.LocalError, OSError, sqlite3.Error) as exc:
            print(local.canonical({"error": str(exc) if isinstance(exc, local.LocalError) else "Fixture trial failed", "no_retry": True}))
            raise SystemExit(1)
    else:
        unittest.main()
