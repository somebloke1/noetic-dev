#!/usr/bin/env python3
"""Capture bounded checking evidence before models; validate without re-execution."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

VERSION = "noetic-checking-manifest/v1"
SPEC_VERSION = "noetic-checking-spec/v1"
OBS_VERSION = "noetic-checking-observations/v1"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate checking JSON field")
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def residue(context, kind, identity):
    found = [item for item in context["supplied_whole_residues"]
             if item["residue_id"] == {"kind": kind, "id": identity}]
    if len(found) != 1 or found[0]["liveness"] not in ("live", "current"):
        raise ValueError("checking requires exact live residue")
    return found[0]


def binding(context, condition_id, warrant_id):
    if any(type(i) is not int or not 0 < i < 2**64 for i in (condition_id, warrant_id)):
        raise ValueError("checking anchors must be positive u64")
    if context["operation"] != "checking":
        raise ValueError("checking context required")
    condition = residue(context, "warrant-condition", condition_id)
    warrant = residue(context, "warrant", warrant_id)
    if condition["retrieval_voice"]["state"] != "unchecked":
        raise ValueError("first checking slice requires unchecked condition")
    relation = [r for r in condition["ancestry"] if r["kind"] == "has-condition"
                and r["other"] == warrant["residue_id"] and r["endpoint_role"] == "to"]
    if len(relation) != 1:
        raise ValueError("condition does not belong to explicit warrant")
    for item in (condition, warrant):
        if digest(canonical(item["content"])) != item["content_sha256"]:
            raise ValueError("whole native residue content hash mismatch")
        if item["pinned_cut_binding"] != context["pinned_canonical_cut"]:
            raise ValueError("whole native residue cut binding mismatch")
    text = condition["retrieval_voice"]["text"]
    if not isinstance(text, str) or not text or text != text.strip():
        raise ValueError("invalid whole condition text")
    conditions = warrant["retrieval_voice"]["conditions"]
    if (text not in conditions or condition["content"]["command"]["payload"]["conditions"] != conditions
            or warrant["content"]["command"]["payload"]["conditions"] != conditions):
        raise ValueError("whole warrant condition text binding mismatch")
    return {"id": condition_id, "warrant_id": warrant_id, "text": text,
            "text_sha256": digest(text.encode()), "object_version": condition["object_version"],
            "warrant_version": warrant["object_version"],
            "condition_content_sha256": condition["content_sha256"],
            "warrant_content_sha256": warrant["content_sha256"]}


def validate_spec(spec, context, condition_id, warrant_id):
    fields = {"version", "condition", "command", "selected_tests", "predicates", "sources", "scope"}
    if not isinstance(spec, dict) or set(spec) != fields or spec["version"] != SPEC_VERSION:
        raise ValueError("invalid closed checking specification")
    if spec["condition"] != binding(context, condition_id, warrant_id):
        raise ValueError("condition specification binding mismatch")
    command = spec["command"]
    if set(command) != {"argv", "cwd", "timeout_seconds", "environment"}:
        raise ValueError("invalid exact command specification")
    if (not isinstance(command["argv"], list) or not command["argv"]
            or any(not isinstance(a, str) or not a or "\0" in a for a in command["argv"])
            or not Path(command["argv"][0]).is_absolute()
            or not Path(command["cwd"]).is_absolute()
            or type(command["timeout_seconds"]) not in (int, float)
            or not math.isfinite(command["timeout_seconds"])
            or not 0 < command["timeout_seconds"] <= 900):
        raise ValueError("absolute exact command and bounded timeout required")
    environment = command["environment"]
    if (not isinstance(environment, dict) or "USER_PROVIDED_PASSWORD" in environment
            or any(not isinstance(k, str) or not k or "=" in k or "\0" in k
                   or not isinstance(v, str) or "\0" in v for k, v in environment.items())):
        raise ValueError("explicit public environment required without development credential")
    selected = spec["selected_tests"]
    if (not isinstance(selected, list) or not selected or len(set(selected)) != len(selected)
            or any(not isinstance(t, str) or not t.strip() for t in selected)):
        raise ValueError("nonempty unique selected test identities required")
    predicates = spec["predicates"]
    if not isinstance(predicates, list) or not predicates:
        raise ValueError("explicit checking predicates required")
    ids = []
    covered = set()
    for predicate in predicates:
        if (set(predicate) != {"id", "test_ids", "expected_observation"}
                or not isinstance(predicate["id"], str) or not predicate["id"].strip()
                or not isinstance(predicate["expected_observation"], str)
                or not predicate["expected_observation"].strip()
                or not isinstance(predicate["test_ids"], list) or not predicate["test_ids"]
                or len(set(predicate["test_ids"])) != len(predicate["test_ids"])
                or not set(predicate["test_ids"]) <= set(selected)):
            raise ValueError("invalid exact predicate/test mapping")
        ids.append(predicate["id"])
        covered.update(predicate["test_ids"])
    if len(set(ids)) != len(ids) or covered != set(selected):
        raise ValueError("duplicate or missing checking predicate")
    if not isinstance(spec["scope"], str) or not spec["scope"].strip():
        raise ValueError("explicit bounded scope required")
    sources = spec["sources"]
    if not isinstance(sources, list) or not sources:
        raise ValueError("source and command dependency hashes required")
    names = []
    for source in sources:
        if set(source) != {"path", "sha256", "role"} or not Path(source["path"]).is_absolute():
            raise ValueError("invalid source fingerprint")
        if (not isinstance(source["sha256"], str) or len(source["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in source["sha256"])
                or not isinstance(source["role"], str) or not source["role"].strip()):
            raise ValueError("invalid source digest or role")
        names.append(source["path"])
    if len(set(names)) != len(names) or command["argv"][0] not in names:
        raise ValueError("duplicate source or missing executable fingerprint")


def outcome(spec, execution, stdout):
    unknown = {p["id"]: "indeterminate" for p in spec["predicates"]}
    tests = []
    try:
        observed = json.loads(stdout, object_pairs_hook=_unique)
        if set(observed) != {"version", "tests", "observations"} or observed["version"] != OBS_VERSION:
            raise ValueError("invalid observation report")
        tests = observed["tests"]
        if not isinstance(tests, list):
            raise ValueError("invalid tests")
        names = []
        for test in tests:
            if set(test) != {"id", "status"} or test["status"] not in ("passed", "failed", "error", "skipped"):
                raise ValueError("invalid test observation")
            names.append(test["id"])
        if len(set(names)) != len(names) or set(names) - set(spec["selected_tests"]):
            raise ValueError("substituted or duplicate tests")
        states = {t["id"]: t["status"] for t in tests}
        if not execution["completed"]:
            return "indeterminate", unknown, tests
        values = {}
        for predicate in spec["predicates"]:
            statuses = [states.get(t) for t in predicate["test_ids"]]
            values[predicate["id"]] = ("unfulfilled" if "failed" in statuses else
                "fulfilled" if all(s == "passed" for s in statuses) else "indeterminate")
        result = ("unfulfilled" if "unfulfilled" in values.values() else
                  "fulfilled" if all(s == "fulfilled" for s in values.values()) else "indeterminate")
        if result == "fulfilled" and execution["returncode"] != 0:
            result = "indeterminate"
        return result, values, tests
    except (ValueError, TypeError, KeyError, UnicodeError):
        return "indeterminate", unknown, []


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate observation field")
        result[key] = value
    return result


def capture(spec_path, context, condition_id, warrant_id, directory):
    spec_path = Path(spec_path).resolve(strict=True)
    spec = load(spec_path)
    validate_spec(spec, context, condition_id, warrant_id)
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    source_records = []
    for index, source in enumerate(spec["sources"]):
        data = Path(source["path"]).read_bytes()
        if digest(data) != source["sha256"]:
            raise ValueError("source hash differs from registered checking specification")
        reference = f"source-{index}.bin"
        (directory / reference).write_bytes(data)
        source_records.append({**source, "reference": reference})
    command = spec["command"]
    execution = {"performed": True, "completed": True, "returncode": None, "error": None}
    try:
        completed = subprocess.run(command["argv"], cwd=command["cwd"], env=command["environment"],
            capture_output=True, timeout=command["timeout_seconds"])
        stdout, stderr = completed.stdout, completed.stderr
        execution["returncode"] = completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        execution.update(completed=False, error="timeout")
    except OSError as exc:
        stdout, stderr = b"", str(exc).encode()
        execution.update(performed=False, completed=False, error="launch-error")
    result, predicates, tests = outcome(spec, execution, stdout)
    artifacts = {}
    for name, data in (("stdout.bin", stdout), ("stderr.bin", stderr),
                       ("spec.json", canonical(spec)), ("context.json", canonical(context))):
        (directory / name).write_bytes(data)
        artifacts[name] = {"sha256": digest(data), "bytes": len(data)}
    manifest = {"version": VERSION, "condition": spec["condition"],
                "context_sha256": artifacts["context.json"]["sha256"],
                "pinned_cut": context["pinned_canonical_cut"], "spec_sha256": artifacts["spec.json"]["sha256"],
                "spec_path": str(spec_path), "command": command, "execution": execution,
                "result": result, "predicate_results": predicates, "tests": tests,
                "counts": {"selected": len(spec["selected_tests"]), "observed": len(tests), "executed": sum(t["status"] != "skipped" for t in tests),
                           **{s: sum(t["status"] == s for t in tests)
                              for s in ("passed", "failed", "error", "skipped")}},
                "sources": source_records, "artifacts": artifacts, "scope": spec["scope"]}
    (directory / "manifest.json").write_bytes(canonical(manifest))
    (directory / "manifest.sha256").write_text(digest(canonical(manifest)) + "\n")
    revalidate(directory, context, current=True)
    return manifest


def revalidate(directory, context=None, *, current=True, expected_manifest_sha256=None):
    directory = Path(directory).resolve(strict=True)
    raw = (directory / "manifest.json").read_bytes()
    expected = expected_manifest_sha256 or (directory / "manifest.sha256").read_text().strip()
    if digest(raw) != expected:
        raise ValueError("checking manifest hash mismatch")
    manifest = load(directory / "manifest.json")
    if raw != canonical(manifest) or manifest["version"] != VERSION:
        raise ValueError("noncanonical checking manifest")
    for name, info in manifest["artifacts"].items():
        if name not in ("stdout.bin", "stderr.bin", "context.json", "spec.json"):
            raise ValueError("unexpected checking artifact")
        data = (directory / name).read_bytes()
        if digest(data) != info["sha256"] or len(data) != info["bytes"]:
            raise ValueError("retained checking artifact hash mismatch")
    if set(manifest["artifacts"]) != {"stdout.bin", "stderr.bin", "context.json", "spec.json"}:
        raise ValueError("missing checking artifact")
    retained_context = load(directory / "context.json")
    spec = load(directory / "spec.json")
    bound = manifest["condition"]
    validate_spec(spec, retained_context, bound["id"], bound["warrant_id"])
    if context is not None and context != retained_context:
        raise ValueError("checking whole context changed")
    result, predicates, tests = outcome(spec, manifest["execution"], (directory / "stdout.bin").read_bytes())
    counts = {"selected": len(spec["selected_tests"]), "observed": len(tests), "executed": sum(t["status"] != "skipped" for t in tests),
              **{s: sum(t["status"] == s for t in tests) for s in ("passed", "failed", "error", "skipped")}}
    if (manifest["condition"] != spec["condition"] or manifest["command"] != spec["command"]
            or manifest["scope"] != spec["scope"] or manifest["result"] != result
            or manifest["predicate_results"] != predicates or manifest["tests"] != tests
            or manifest["counts"] != counts or manifest["pinned_cut"] != retained_context["pinned_canonical_cut"]
            or manifest["context_sha256"] != digest(canonical(retained_context))
            or manifest["spec_sha256"] != digest(canonical(spec))):
        raise ValueError("checking result, condition, context or command binding mismatch")
    if len(manifest["sources"]) != len(spec["sources"]):
        raise ValueError("checking source coverage mismatch")
    for index, (record, source) in enumerate(zip(manifest["sources"], spec["sources"])):
        if record != {**source, "reference": f"source-{index}.bin"}:
            raise ValueError("checking source binding mismatch")
        if digest((directory / record["reference"]).read_bytes()) != source["sha256"]:
            raise ValueError("retained source hash mismatch")
        if current and digest(Path(source["path"]).read_bytes()) != source["sha256"]:
            raise ValueError("current source hash mismatch")
    if current and canonical(load(manifest["spec_path"])) != canonical(spec):
        raise ValueError("registered checking specification changed")
    return manifest


def contribution(directory, context, condition_id, warrant_id, expected_manifest_sha256, *, current=True):
    manifest = revalidate(directory, context, current=current,
                          expected_manifest_sha256=expected_manifest_sha256)
    if manifest["condition"] != binding(context, condition_id, warrant_id):
        raise ValueError("checking condition identity mismatch")
    if not manifest["execution"]["performed"]:
        raise ValueError("unexecuted command cannot supply host-execution provenance")
    provenance = {"version": "opermem-checking-provenance/v2",
        "evidence_authority": "host-captured-command-and-exact-retained-artifacts",
        "condition_id": condition_id, "condition_text_sha256": manifest["condition"]["text_sha256"],
        "computed_result": manifest["result"], "manifest_sha256": expected_manifest_sha256,
        "manifest_reference": "checking-evidence/manifest.json",
        "separately_captured_host_tool_execution_performed": True,
        "model_assertion_used_as_evidence": False,
        "original_source_path_standing": "descriptive-host-observed"}
    warrant = {"id": warrant_id, "kind": "warrant"}
    return {"condition_id": condition_id, "result": manifest["result"], "provenance": provenance,
            "fingerprints": [{"dependency": warrant, "source": warrant, "status": "current",
                "method": "sha256-host-retained-manifest-declared-warrant-anchor", "method_version": 1,
                "current_value": expected_manifest_sha256,
                "provenance": "Declared retained warrant anchor; external paths are descriptive, not registered sources."}]}


def command_for(context, contribution, key):
    condition = residue(context, "warrant-condition", contribution["condition_id"])
    identities = {("warrant-condition", contribution["condition_id"]): condition["object_version"]}
    for fp in contribution["fingerprints"]:
        for field in ("dependency", "source"):
            identity = fp[field]
            identities[(identity["kind"], identity["id"])] = residue(context, identity["kind"], identity["id"])["object_version"]
    order = {"warrant": 0, "warrant-condition": 1}
    expected = [{"kind": kind, "id": identity, "version": version}
                for (kind, identity), version in sorted(identities.items(), key=lambda p: (order[p[0][0]], p[0][1]))]
    return "check-condition", {"body": contribution, "command_version": 1,
        "expected_object_versions": expected, "idempotency_key": key}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256")
    args = parser.parse_args(argv)
    manifest = revalidate(args.evidence, expected_manifest_sha256=args.expected_manifest_sha256)
    print(json.dumps({"result": manifest["result"], "counts": manifest["counts"],
                      "immutable_evidence_revalidated": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
