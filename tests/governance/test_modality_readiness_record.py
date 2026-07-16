"""Tests for per-modality readiness evidence records."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GOV_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "governance")
if GOV_SCRIPTS not in sys.path:
    sys.path.insert(0, GOV_SCRIPTS)

from check_modality_readiness_record import check  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def valid_record(modality: str = "embed") -> dict:
    model = "snowflake-arctic-embed2" if modality == "embed" else "qwen3-asr"
    path = "/v1/embeddings" if modality == "embed" else "/v1/audio/transcriptions"
    return {
        "schema_version": "1",
        "record_kind": "modality-readiness-record",
        "modality": modality,
        "model": model,
        "endpoint": {"id": "local-litellm", "path": path},
        "route_decision": {
            "decision_id": f"decision-{modality}",
            "model": model,
            "endpoint_id": "local-litellm",
            "endpoint_path": path,
            "route_reference_sha256": "a" * 64,
        },
        "readiness_probe": {
            "probe_id": f"probe-{modality}",
            "passed": True,
            "model": model,
            "endpoint_id": "local-litellm",
            "endpoint_path": path,
            "request_shape_hash": "b" * 64,
            "response_shape_hash": "c" * 64,
            "latency_ms": 250,
        },
        "report_outcome": {
            "outcome_id": f"outcome-{modality}",
            "decision_id": f"decision-{modality}",
            "status": "success",
            "reported_at": "2026-07-16T00:00:00+00:00",
        },
        "generated_at": "2026-07-16T00:00:01+00:00",
    }


class TestModalityReadinessRecord(unittest.TestCase):
    def test_valid_records_are_modality_scoped(self) -> None:
        self.assertEqual(check(valid_record("embed")), [])
        self.assertEqual(check(valid_record("asr")), [])

    def test_record_does_not_include_runtime_readiness_claim(self) -> None:
        record = valid_record()
        self.assertNotIn("ready", record)
        self.assertNotIn("runtime_adapters_ready", record)

    def test_rejects_cross_modality_reuse(self) -> None:
        record = valid_record("embed")
        record["modality"] = "asr"
        errors = check(record)
        self.assertTrue(any("modalities.asr" in error or "/v1/audio/transcriptions" in error for error in errors), errors)

    def test_rejects_unbound_nested_route_probe_and_outcome(self) -> None:
        cases = [
            (("route_decision", "model"), "qwen3-asr"),
            (("readiness_probe", "endpoint_path"), "/v1/audio/transcriptions"),
            (("report_outcome", "decision_id"), "other-decision"),
            (("readiness_probe", "latency_ms"), 0),
            (("readiness_probe", "latency_ms"), -1),
        ]
        for path, value in cases:
            with self.subTest(path=path, value=value):
                record = copy.deepcopy(valid_record())
                target = record
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.assertNotEqual(check(record), [])

    def test_rejects_failed_probe_or_outcome(self) -> None:
        for path, value in [
            (("readiness_probe", "passed"), False),
            (("report_outcome", "status"), "failed"),
        ]:
            with self.subTest(path=path):
                record = copy.deepcopy(valid_record())
                record[path[0]][path[1]] = value
                self.assertNotEqual(check(record), [])

    def test_cli_rejects_duplicate_keys(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            handle.write('{"schema_version":"1","schema_version":"1"}')
            path = Path(handle.name)
        try:
            result = subprocess.run(
                [sys.executable, "scripts/governance/check_modality_readiness_record.py", str(path)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate object key", result.stderr)
        finally:
            path.unlink(missing_ok=True)

    def test_cli_accepts_valid_record(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(valid_record("asr"), handle)
            path = Path(handle.name)
        try:
            result = subprocess.run(
                [sys.executable, "scripts/governance/check_modality_readiness_record.py", str(path)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("validation passed", result.stdout)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
