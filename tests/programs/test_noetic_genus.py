"""Read-only qualification packet boundaries, without provider inference."""

import asyncio
from contextlib import asynccontextmanager, redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import noetic_genus as genus
from scripts import noetic


TASK = "Implement a bounded composition adapter.\n"
CHARACTERIZATION = {
    "task_class_id": "code_generation", "requirements": {"code": 1.5},
    "weights": {"token_efficiency": 3}, "rationale": "Scoped implementation work.",
    "acceptance_criteria": ["Read-only calls preserve the evidence."],
}
CONTRACT = {
    "schema_version": 6, "task_classes": {"code_generation": {"revision": 1}},
    "dimensions": {"code": {"kind": "capability"},
                   "token_efficiency": {"kind": "efficiency"}},
    "selection": {"qualification_policy_default": "provisional"},
}


def selection(matches=None, **changes):
    result = {
        "task_class_id": "code_generation", "task_class_revision": 1,
        "requirements": {"code": 1.5}, "weights": {"token_efficiency": 3},
        "matches": [] if matches is None else matches, "unverified_models": [],
        "excluded_models": [], "unranked_models": [], "status": "no_qualified_models",
        "qualification_policy": "provisional", "learning_run_id": None,
        "review_signals": [], "warnings": ["Provisional means are uncertain."],
        "uncertainty_basis": "policy_conditional_approximation_not_calibrated_coverage",
    }
    result.update(changes)
    return result


def match():
    return {
        "model_id": "control", "client_model": "provider/control", "profile_id": "high",
        "profile_revision": 7, "task_rating_revision": 8,
        "task_class_id": "code_generation", "task_class_revision": 1,
        "controls": {"reasoning_effort": "high"}, "score": 3,
        "qualification_policy": "provisional",
        "qualification": {"code": {"status": "qualified", "required": 1.5,
                                     "evidence": [], "model_estimate": {"mean": 2.5}}},
        "task_cost": {"amount": None, "status": "unknown"},
    }


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = responses, []

    async def call_tool(self, name, arguments):
        self.calls.append((name, deepcopy(arguments)))
        class Result:
            isError = False
            content = []
            structuredContent = deepcopy(self.responses[name])
        return Result()


class GenusPacketTests(unittest.TestCase):
    def packet(self, models=None, alignment=None, selected=None, chosen="gpt-6.1-sol", aliases=None):
        models = [chosen] if models is None else models
        alignment = alignment or {
            "model_aliases": {}, "identity_basis": {},
            "unmatched_client_models": sorted(models), "unmapped_router_models": ["control"],
        }
        session = FakeSession({"describe_dimensions": CONTRACT, "align_models": alignment,
                               "select_models": selection() if selected is None else selected})
        @asynccontextmanager
        async def connect(argv):
            yield session
        with patch.object(genus, "_connect", connect):
            packet = asyncio.run(genus.generate_packet(
                TASK, CHARACTERIZATION, models, chosen_model=chosen,
                reason="Use the caller's configured model.", server_command=["external-genus"],
                config="catalog.yaml", aliases=aliases))
        return packet, session

    def test_empty_alignment_is_empty_selection_pool_and_sol_is_unmatched(self):
        for chosen in ("gpt-6.1-sol", "openai-codex/gpt-6.1-sol"):
            packet, session = self.packet(chosen=chosen)
            self.assertEqual([name for name, _ in session.calls],
                             ["describe_dimensions", "align_models", "select_models"])
            self.assertEqual(session.calls[-1][1]["model_aliases"], {})
            self.assertIsNone(packet["selection"]["learning_run_id"])
            self.assertEqual(packet["consumer_decision"]["qualification_support"], "catalog_unmatched")
            self.assertEqual(packet["task_sha256"], hashlib.sha256(TASK.encode()).hexdigest())
            self.assertIs(genus.validate_packet(packet, TASK, chosen), packet)

    def test_empty_inventory_has_no_chosen_model(self):
        with self.assertRaisesRegex(ValueError, "inventory"):
            self.packet(models=[])

    def test_qualified_controls_revisions_and_uncertainty_are_retained(self):
        row = match()
        alignment = {"model_aliases": {"control": "provider/control"},
                     "identity_basis": {"control": "declared"},
                     "unmatched_client_models": [], "unmapped_router_models": []}
        raw = selection([row], status="ranked")
        packet, _ = self.packet(chosen="provider/control", alignment=alignment,
                               selected=raw, aliases={"control": "provider/control"})
        self.assertEqual(packet["selection"], raw)
        self.assertEqual(packet["consumer_decision"]["selected_evidence"], row)
        self.assertEqual(packet["consumer_decision"]["qualification_support"], "qualified")
        self.assertEqual(packet["contract"], CONTRACT)

    def test_consumer_support_preserves_unknown_excluded_and_unranked(self):
        alignment = {"model_aliases": {"control": "provider/control"},
                     "identity_basis": {"control": "declared"},
                     "unmatched_client_models": [], "unmapped_router_models": []}
        for section, assessment, support in (
                ("unverified_models", "unknown", "qualification_unknown"),
                ("excluded_models", "failed", "excluded"),
                ("unranked_models", "qualified", "qualified_unranked")):
            row = match()
            row["qualification"]["code"]["status"] = assessment
            row["score"] = None
            raw = selection(**{section: [row]})
            if section == "unranked_models":
                raw["status"] = "insufficient_efficiency_data"
            packet, _ = self.packet(chosen="provider/control", alignment=alignment,
                                   selected=raw, aliases={"control": "provider/control"})
            self.assertEqual(packet["consumer_decision"]["qualification_support"], support)
            self.assertEqual(packet["selection"], raw)

    def test_public_commands_forward_to_existing_clis(self):
        for command, module in (("genus", genus), ("opermem", noetic.importlib.import_module("scripts.noetic_opermem"))):
            with patch.object(module, "main", return_value=0) as implementation:
                self.assertEqual(noetic.main([command, "--help"]), 0)
                implementation.assert_called_once_with(["--help"])

    def test_binding_rejects_different_task_and_model(self):
        packet, _ = self.packet()
        for task, model in ((TASK + "changed", "gpt-6.1-sol"), (TASK, "gpt-6-astra")):
            with self.assertRaises(ValueError):
                genus.validate_packet(packet, task, model)

    def test_malformed_evidence_fails_before_work(self):
        packet, _ = self.packet()
        for section, key, value in (
                ("contract", "schema_version", 5),
                ("alignment", "model_aliases", None),
                ("selection", "matches", None),
                ("selection", "requirements", {"code": 99}),
                ("consumer_decision", "qualification_support", "qualified"),
                ("selection", "warnings", "unknown")):
            with self.subTest(section=section, key=key):
                malformed = deepcopy(packet)
                malformed[section][key] = value
                with self.assertRaises(ValueError):
                    genus.validate_packet(malformed, TASK, "gpt-6.1-sol")

    def test_invalid_characterization_and_alias_substitution_are_rejected(self):
        for field, value in (("requirements", {"code": float("nan")}),
                             ("weights", {"token_efficiency": True}),
                             ("acceptance_criteria", [])):
            bad = deepcopy(CHARACTERIZATION)
            bad[field] = value
            with patch.dict(CHARACTERIZATION, bad, clear=True):
                with self.assertRaises(ValueError):
                    self.packet()
        with self.assertRaisesRegex(ValueError, "same model"):
            self.packet(aliases={"gpt-6-astra": "gpt-6.1-sol"})

    def test_cli_accepts_external_argv_after_separator(self):
        packet, _ = self.packet()
        async def generate(*args, **kwargs):
            self.assertEqual(kwargs["server_command"], ["python", "-m", "genus_router.server"])
            return packet
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, data in (("characterization", CHARACTERIZATION), ("inventory", ["gpt-6.1-sol"])):
                (root / name).write_text(json.dumps(data))
            (root / "task").write_text(TASK)
            with patch.object(genus, "generate_packet", generate), redirect_stdout(io.StringIO()):
                self.assertEqual(genus.main([
                    "--model", "gpt-6.1-sol", "--reason", "Caller choice", "--characterization",
                    str(root / "characterization"), "--inventory", str(root / "inventory"),
                    "--task", str(root / "task"), "--output", str(root / "packet"),
                    "--config", str(root / "catalog"), "--", "python", "-m", "genus_router.server"]), 0)
            self.assertEqual(json.loads((root / "packet").read_text()), packet)


@unittest.skipUnless(importlib.util.find_spec("mcp") and os.environ.get("GENUS_TEST_COMMAND")
                     and os.environ.get("GENUS_TEST_CONFIG"),
                     "real MCP test needs SDK, GENUS_TEST_COMMAND JSON argv and GENUS_TEST_CONFIG")
class RealGenusMcpTests(unittest.TestCase):
    def test_real_read_only_donor_boundary(self):
        config = Path(os.environ["GENUS_TEST_CONFIG"])
        before = config.read_bytes()
        packet = asyncio.run(genus.generate_packet(
            TASK, CHARACTERIZATION, ["gpt-6.1-sol", "openai-codex/gpt-6.1-sol"],
            chosen_model="gpt-6.1-sol", reason="Consumer choice remains independent.",
            server_command=json.loads(os.environ["GENUS_TEST_COMMAND"]), config=config))
        self.assertEqual(packet["schema_version"], 6)
        self.assertEqual(packet["alignment"]["model_aliases"], {})
        self.assertEqual(packet["selection"]["matches"], [])
        self.assertEqual(packet["consumer_decision"]["qualification_support"], "catalog_unmatched")
        self.assertEqual(before, config.read_bytes())
        self.assertEqual(genus.validate_packet(packet, TASK, "gpt-6.1-sol"), packet)

    def test_real_qualified_control_preserves_donor_evidence(self):
        config = Path(os.environ["GENUS_TEST_CONFIG"])
        before = config.read_bytes()
        model = os.environ.get("GENUS_TEST_CONTROL", "claude-opus-4-8")
        packet = asyncio.run(genus.generate_packet(
            TASK, CHARACTERIZATION, [model], chosen_model=model,
            reason="Exact catalog control for the composition boundary.",
            server_command=json.loads(os.environ["GENUS_TEST_COMMAND"]), config=config))
        decision = packet["consumer_decision"]
        self.assertEqual(decision["qualification_support"], "qualified")
        self.assertEqual(decision["selected_evidence"], packet["selection"]["matches"][0])
        row = decision["selected_evidence"]
        self.assertIsInstance(row["controls"], dict)
        self.assertGreater(row["profile_revision"], 0)
        self.assertIn("capability", row["qualification"]["code"])
        self.assertIn("task_difficulty", row["qualification"]["code"])
        self.assertIn("warnings", packet["selection"])
        self.assertEqual(before, config.read_bytes())


if __name__ == "__main__":
    unittest.main()
