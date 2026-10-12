#!/usr/bin/env python3
"""Collect read-only schema 6 genus qualification evidence for a consumer choice."""

from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import hashlib
import json
import math
from pathlib import Path
from typing import Any


PACKET_VERSION = 1


def _name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonblank string")
    return value


def _object(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _names(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    for item in value:
        _name(item, label)
    if len(set(value)) != len(value):
        raise ValueError(f"{label} must not contain duplicates")
    return value


def _aliases(value: Any, models: list[str]) -> dict[str, str]:
    result = _object(value, "verified aliases")
    for canonical, client in result.items():
        _name(canonical, "canonical model")
        _name(client, "client model")
        if client not in models:
            raise ValueError("verified alias target is absent from inventory")
        if client.rsplit("/", 1)[-1] == "gpt-6.1-sol" and canonical.rsplit("/", 1)[-1] != "gpt-6.1-sol":
            raise ValueError("Sol 6.1 aliases must identify the same model")
    if len(set(result.values())) != len(result):
        raise ValueError("verified aliases must be one-to-one")
    return result


def _characterization(value: Any, contract: dict | None = None) -> dict:
    result = _object(value, "characterization")
    task_class = _name(result.get("task_class_id"), "task class")
    _name(result.get("rationale"), "characterization rationale")
    if not _names(result.get("acceptance_criteria"), "acceptance criteria"):
        raise ValueError("acceptance criteria must not be empty")
    for label in ("requirements", "weights"):
        mapping = _object(result.get(label), label)
        if not mapping:
            raise ValueError(f"{label} must not be empty")
        for key, number in mapping.items():
            _name(key, "dimension")
            if label == "requirements":
                valid = type(number) in (int, float) and math.isfinite(number) and 0 < number <= 1e6
            else:
                valid = type(number) is int and 1 <= number <= 5
            if not valid:
                raise ValueError(f"invalid {label} value for {key}")
            if contract is not None:
                dimension = _object(contract.get("dimensions"), "contract dimensions").get(key)
                expected = "capability" if label == "requirements" else "efficiency"
                if not isinstance(dimension, dict) or dimension.get("kind") != expected:
                    raise ValueError(f"{key} must be a registered {expected} dimension")
    if "qualification_policy" in result and result["qualification_policy"] not in ("provisional", "conservative"):
        raise ValueError("invalid qualification policy")
    if contract is not None and task_class not in _object(contract.get("task_classes"), "contract task classes"):
        raise ValueError("task class is not registered in the contract")
    return result


def _decision(chosen: str, reason: str, alignment: dict, selection: dict) -> dict:
    canonical = next((key for key, client in alignment["model_aliases"].items() if client == chosen), None)
    support, evidence = "catalog_unmatched" if canonical is None else "not_selected", None
    for section, status in (("matches", "qualified"), ("unverified_models", "qualification_unknown"),
                            ("excluded_models", "excluded"), ("unranked_models", "qualified_unranked")):
        for row in selection[section]:
            if row["client_model"] == chosen:
                support, evidence = status, row
                break
        if evidence is not None:
            break
    return {"chosen_model": chosen, "rationale": reason, "qualification_support": support,
            "canonical_model_id": canonical, "selected_evidence": evidence}


def validate_packet(packet: Any, task_text: str, chosen_model: str) -> dict:
    """Bind a saved packet to the exact task and choice; reject malformed evidence."""
    value = _object(packet, "qualification packet")
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("qualification packet must contain finite JSON values") from error
    if type(value.get("packet_version")) is not int or value["packet_version"] != PACKET_VERSION:
        raise ValueError("unsupported qualification packet version")
    _name(task_text, "task text")
    if value.get("task_sha256") != hashlib.sha256(task_text.encode("utf-8")).hexdigest():
        raise ValueError("qualification packet task mismatch")
    models = _names(value.get("inventory"), "inventory")
    _name(chosen_model, "chosen model")
    if chosen_model not in models:
        raise ValueError("chosen model is absent from inventory")
    verified = _aliases(value.get("verified_aliases"), models)
    server = _object(value.get("server"), "server")
    argv = server.get("argv")
    if not isinstance(argv, list) or len(argv) < 3:
        raise ValueError("server argv must contain a command and explicit config")
    for arg in argv:
        _name(arg, "server argv")
    config = _name(server.get("config"), "server config")
    if argv[-2:] != ["--config", config]:
        raise ValueError("server argv/config mismatch")
    contract = _object(value.get("contract"), "contract")
    if type(value.get("schema_version")) is not int or value["schema_version"] != 6 or type(contract.get("schema_version")) is not int or contract["schema_version"] != 6:
        raise ValueError("qualification requires schema 6")
    characterization = _characterization(value.get("characterization"), contract)
    alignment = _object(value.get("alignment"), "alignment")
    aligned = _aliases(alignment.get("model_aliases"), models)
    bases = _object(alignment.get("identity_basis"), "alignment identity basis")
    if set(bases) != set(aligned):
        raise ValueError("alignment identity basis mismatch")
    for canonical, client in aligned.items():
        if canonical in verified:
            if client != verified[canonical] or bases[canonical] != "declared":
                raise ValueError("alignment differs from verified alias")
        elif canonical != client or bases[canonical] != "exact":
            raise ValueError("alignment fabricated an alias")
    if any(aligned.get(key) != client for key, client in verified.items()):
        raise ValueError("verified alias missing from alignment")
    unmatched = _names(alignment.get("unmatched_client_models"), "unmatched client models")
    if set(unmatched) != set(models) - set(aligned.values()):
        raise ValueError("alignment inventory mismatch")
    unmapped = _names(alignment.get("unmapped_router_models"), "unmapped router models")
    if set(unmapped) & set(aligned):
        raise ValueError("aligned and unmapped router identities overlap")
    selected = _object(value.get("selection"), "selection")
    for field in ("task_class_id", "requirements", "weights"):
        if selected.get(field) != characterization[field]:
            raise ValueError(f"selection {field} differs from characterization")
    if selected.get("status") not in ("ranked", "partial_efficiency_data", "insufficient_efficiency_data", "no_qualified_models"):
        raise ValueError("invalid selection status")
    if selected.get("qualification_policy") not in ("provisional", "conservative"):
        raise ValueError("invalid selection qualification policy")
    if "qualification_policy" in characterization and selected["qualification_policy"] != characterization["qualification_policy"]:
        raise ValueError("selection qualification policy mismatch")
    _names(selected.get("warnings"), "selection warnings")
    if not isinstance(selected.get("review_signals"), list):
        raise ValueError("selection review signals must be a list")
    _name(selected.get("uncertainty_basis"), "selection uncertainty basis")
    if type(selected.get("task_class_revision")) is not int or selected["task_class_revision"] < 1:
        raise ValueError("invalid task class revision")
    for section in ("matches", "unverified_models", "excluded_models", "unranked_models"):
        rows = selected.get(section)
        if not isinstance(rows, list):
            raise ValueError(f"selection {section} must be a list")
        for row in rows:
            _object(row, "selection evidence row")
            canonical = _name(row.get("model_id"), "evidence model ID")
            if canonical not in aligned or row.get("client_model") != aligned[canonical]:
                raise ValueError("selection evidence is outside aligned inventory")
            _name(row.get("profile_id"), "evidence profile ID")
            if type(row.get("profile_revision")) is not int or row["profile_revision"] < 1:
                raise ValueError("invalid evidence profile revision")
            _object(row.get("controls"), "evidence controls")
            revision = row.get("task_rating_revision")
            if revision is not None and (type(revision) is not int or revision < 1):
                raise ValueError("invalid evidence task rating revision")
            cost = _object(row.get("task_cost"), "evidence task cost")
            amount = cost.get("amount")
            if amount is not None and (type(amount) not in (int, float) or amount < 0):
                raise ValueError("invalid evidence task cost")
            _name(cost.get("status"), "evidence task cost status")
            for field in ("task_class_id", "task_class_revision", "qualification_policy"):
                if row.get(field) != selected[field]:
                    raise ValueError(f"evidence {field} mismatch")
            qualification = _object(row.get("qualification"), "evidence qualification")
            if set(qualification) != set(characterization["requirements"]):
                raise ValueError("evidence qualification dimensions mismatch")
            for dimension, demand in characterization["requirements"].items():
                assessment = _object(qualification[dimension], "qualification assessment")
                if assessment.get("required") != demand or assessment.get("status") not in ("qualified", "unknown", "failed"):
                    raise ValueError("invalid qualification assessment")
                if section in ("matches", "unranked_models") and assessment["status"] != "qualified":
                    raise ValueError("qualified evidence has an unmet requirement")
            if section == "matches" and (type(row.get("score")) not in (int, float) or not 1 <= row["score"] <= 5):
                raise ValueError("invalid qualified score")
            if section in ("unverified_models", "excluded_models") and row.get("score") is not None:
                raise ValueError("unqualified evidence score must be null")
    if len(selected["matches"]) > 3 or (selected["status"] in ("ranked", "partial_efficiency_data")) != bool(selected["matches"]):
        raise ValueError("selection status/matches mismatch")
    decision = _object(value.get("consumer_decision"), "consumer decision")
    if decision.get("chosen_model") != chosen_model:
        raise ValueError("qualification packet choice mismatch")
    reason = _name(decision.get("rationale"), "consumer rationale")
    if decision != _decision(chosen_model, reason, alignment, selected):
        raise ValueError("consumer decision support differs from raw evidence")
    return value


@asynccontextmanager
async def _connect(argv: list[str]):
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as error:
        raise RuntimeError("genus qualification needs the official MCP SDK; install noetic-dev[genus]") from error
    parameters = StdioServerParameters(command=argv[0], args=argv[1:], env={"PYTHONPATH": ""})
    try:
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=30)) as session:
                await session.initialize()
                yield session
    except Exception as error:
        cause = error
        while len(getattr(cause, "exceptions", ())) == 1:
            cause = cause.exceptions[0]
        if isinstance(cause, (ValueError, RuntimeError, OSError)):
            raise cause from error
        raise RuntimeError(f"genus MCP request failed: {cause}") from error


async def _call(session: Any, name: str, arguments: dict) -> dict:
    result = await session.call_tool(name, arguments)
    if result.isError:
        raise ValueError(f"genus {name} failed: {result.content}")
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        data = structured["result"] if set(structured) == {"result"} else structured
    else:
        texts = [item.text for item in result.content if isinstance(getattr(item, "text", None), str)]
        if len(texts) != 1:
            raise ValueError(f"genus {name} did not return one JSON object")
        data = json.loads(texts[0])
    return _object(data, f"genus {name} result")


async def generate_packet(task_text: str, characterization: dict, models: list[str], *,
                          chosen_model: str, reason: str, server_command: list[str],
                          config: str | Path, aliases: dict[str, str] | None = None) -> dict:
    """Ask only describe_dimensions, align_models, and select_models; never infer."""
    _name(task_text, "task text")
    _name(chosen_model, "chosen model")
    _name(reason, "consumer rationale")
    _names(models, "inventory")
    if chosen_model not in models:
        raise ValueError("chosen model is absent from inventory")
    characterization = _characterization(characterization)
    verified = _aliases({} if aliases is None else aliases, models)
    if not isinstance(server_command, list) or not server_command:
        raise ValueError("explicit external server command is required")
    for argument in server_command:
        _name(argument, "server command")
    if any(arg == "--config" or arg.startswith("--config=") for arg in server_command):
        raise ValueError("pass server config separately from the command")
    _name(str(config), "server config")
    config_path = str(Path(config).resolve())
    argv = [*server_command, "--config", config_path]
    async with _connect(argv) as session:
        contract = await _call(session, "describe_dimensions", {})
        if type(contract.get("schema_version")) is not int or contract["schema_version"] != 6:
            raise ValueError("qualification requires schema 6")
        _characterization(characterization, contract)
        alignment = await _call(session, "align_models", {"models": models, "aliases": verified})
        pool = _object(alignment.get("model_aliases"), "alignment model aliases")
        arguments = {key: characterization[key] for key in ("task_class_id", "requirements", "weights")}
        arguments["model_aliases"] = pool
        if "qualification_policy" in characterization:
            arguments["qualification_policy"] = characterization["qualification_policy"]
        selected = await _call(session, "select_models", arguments)
    # Preserve empty alignment explicitly: null means the donor's entire catalog.
    packet = {"packet_version": PACKET_VERSION, "schema_version": 6,
              "task_sha256": hashlib.sha256(task_text.encode("utf-8")).hexdigest(),
              "characterization": characterization, "inventory": models,
              "verified_aliases": verified, "server": {"argv": argv, "config": config_path},
              "contract": contract, "alignment": alignment, "selection": selected}
    for section in ("matches", "unverified_models", "excluded_models", "unranked_models"):
        if not isinstance(selected.get(section), list) or any(not isinstance(row, dict) or "client_model" not in row for row in selected[section]):
            raise ValueError(f"malformed selection {section}")
    packet["consumer_decision"] = _decision(chosen_model, reason, alignment, selected)
    return validate_packet(packet, task_text, chosen_model)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("model", "reason", "characterization", "inventory", "task", "output", "config"):
        parser.add_argument(f"--{option}", required=True)
    parser.add_argument("--aliases", help="JSON file of verified canonical-to-client same-model aliases")
    parser.add_argument("server_command", nargs=argparse.REMAINDER, help="-- external-server [args]")
    args = parser.parse_args(argv)
    command = args.server_command
    if command and command[0] == "--":
        command = command[1:]
    try:
        def load(path):
            return json.loads(Path(path).read_text(encoding="utf-8"))
        packet = asyncio.run(generate_packet(
            Path(args.task).read_text(encoding="utf-8"), load(args.characterization), load(args.inventory),
            chosen_model=args.model, reason=args.reason, server_command=command, config=args.config,
            aliases=load(args.aliases) if args.aliases else None))
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(packet, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))
    print(str(output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
