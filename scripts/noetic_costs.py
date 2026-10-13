"""Deterministic application cost skill; observations and human factors stay separate."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
from urllib import request
import uuid

from scripts.noetic_application import ApplicationError
from scripts.noetic_storage import open_private


RATE_KEYS = ("input", "output", "cache_read", "cache_write")
FACTOR_KEYS = ("input_multiplier", "output_multiplier", "allocation_cost", "runtime_seconds",
               "power_watts", "electricity_per_kwh")
PRICE_SOURCES = {"gpt-6.1-sol": "https://developers.openai.com/api/docs/models/gpt-6.1-sol.md"}
SKILL = {
    "id": "noetic:cost-estimate", "version": "1", "label": "Cost estimation skill",
    "execution": "Deterministic application callable; no model generation",
    "instructions": [
        "Choose an exact provider/model, currency and API-equivalent, subscription-allocation or local-energy basis.",
        "Edit user rates per million tokens or named factors. Omitted fields preserve values; explicit null clears them.",
        "Run explicitly to save factors, optionally retrieve official API rates, and recalculate an estimate.",
        "Fetched rates never replace user overrides. Failed retrieval retains the previous good snapshot and its date.",
        "Estimates do not establish actual billed cost. Missing factors or compatible usage remain unavailable.",
    ],
    "allowed_effects": ["Read selected retained accounting", "Bounded official-rate HTTPS retrieval",
                        "Save cost-only factors, snapshots and receipts", "Calculate qualified estimates"],
    "rate_unit": "currency per 1M tokens", "rate_fields": list(RATE_KEYS),
    "factor_fields": list(FACTOR_KEYS), "billing_bases": ["api", "subscription", "local", "unknown"],
    "supported_refresh_models": list(PRICE_SOURCES),
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def parse_rates(markdown):
    section = markdown.split("## Pricing", 1)
    if len(section) != 2:
        raise ValueError("Pricing section unavailable")
    section = section[1].split("### Text tokens", 1)
    if len(section) != 2:
        raise ValueError("Text-token pricing table unavailable")
    table = section[1].split("\n## ", 1)[0]
    labels = {"Input": "input", "Cached input": "cache_read", "Cache writes": "cache_write", "Output": "output"}
    rates = {}
    for line in table.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0] not in labels:
            continue
        key = labels[cells[0]]
        if key in rates or cells[2] != "1M tokens" or not re.fullmatch(r"\$\d+(?:\.\d+)?", cells[1]):
            raise ValueError("Ambiguous or unsupported rate/units")
        value = float(cells[1][1:])
        if not _number(value):
            raise ValueError("Rate is not finite")
        rates[key] = value
    if set(rates) != set(RATE_KEYS):
        raise ValueError("Complete input/cache-read/cache-write/output rates unavailable")
    return rates


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def retrieve_rates(provider, model, currency, basis):
    if basis != "api" or currency != "USD" or provider not in ("openai", "openai-codex") or model not in PRICE_SOURCES:
        return {"state": "unsupported", "error": "Official refresh supports the named OpenAI model in USD API-equivalent basis; manual factors remain available."}
    url = PRICE_SOURCES[model]
    attempt = {"url": url, "retrieved_at": _now()}
    try:
        opener = request.build_opener(_NoRedirect())
        with opener.open(request.Request(url, headers={"Accept": "text/markdown"}), timeout=12) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("Rate source exceeds 64 KiB")
        attempt["sha256"] = hashlib.sha256(raw).hexdigest()
        attempt["raw_text"] = raw.decode("utf-8")
        rates = parse_rates(attempt["raw_text"])
        notes = [line.strip()[2:] for line in attempt["raw_text"].splitlines() if line.startswith("- ")]
        conditions = {}
        if "more than 272K input tokens are priced at 2x input and cache rates and 1.5x output" in attempt["raw_text"]:
            conditions = {"long_context_threshold": 272000, "long_input_multiplier": 2, "long_output_multiplier": 1.5}
        return {"state": "retrieved", "snapshot": {
            **attempt, "rates": rates, "currency": "USD", "parser_version": "openai-text-table-1",
            "conditions": conditions, "source_notes": notes,
            "assumptions": ["Standard API list-rate equivalent, not an actual bill; speed/tier/regional changes need explicit factors."]}}
    except (OSError, ValueError, UnicodeError) as exc:
        return {"state": "failed", "error": f"Official rate retrieval failed: {exc}", "attempt": attempt}


def _identity(app, selection):
    app.operation_scope(selection)
    with closing(sqlite3.connect(Path(app.namespace_path).resolve().as_uri() + "?mode=ro", uri=True)) as db:
        row = db.execute("SELECT value FROM metadata WHERE key='namespace'").fetchone()
    if not row or not row[0]:
        raise ApplicationError(422, "Cost skill needs the configured application namespace")
    return {"namespace": row[0], "namespace_path": str(app.namespace_path), "selection": selection}


def _state(app):
    path = app.root / ".cost-estimates.json"
    if not path.exists():
        return {"version": 1, "scopes": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("scopes"), dict):
        raise ApplicationError(422, "Unsupported cost-estimate state")
    return data


def _scope_key(identity):
    return _json({"namespace": identity["namespace"], "selection": identity["selection"]})


def _profile_key(profile):
    return hashlib.sha256(_json([profile[key] for key in ("provider", "model", "billing_basis", "currency")]).encode()).hexdigest()


def _effective(profile):
    fetched = profile.get("fetched", {})
    rates = dict(fetched.get("rates", {})) if fetched.get("currency") == profile["currency"] else {}
    rates.update(profile.get("overrides", {}))
    return rates


def _estimate(profile, accounting):
    factors, basis = profile.get("factors", {}), profile["billing_basis"]
    result = {"state": "unknown", "amount": None, "currency": profile["currency"], "billing_basis": basis,
              "standing": "estimate, not actual billed cost", "missing": [], "covered_records": 0}
    if basis == "unknown":
        result["missing"] = ["Declared billing basis"]
    elif basis == "subscription":
        if "allocation_cost" in factors:
            result.update(state="known", amount=factors["allocation_cost"], assumptions=["User-supplied allocation for this scope/model; period is not inferred"])
        else:
            result["missing"] = ["allocation_cost"]
    elif basis == "local":
        required = ("runtime_seconds", "power_watts", "electricity_per_kwh")
        result["missing"] = [key for key in required if key not in factors]
        if not result["missing"]:
            amount = factors["runtime_seconds"] * factors["power_watts"] / 3600000 * factors["electricity_per_kwh"]
            result.update(state="known", amount=amount, assumptions=["User-supplied measured duration/power and electricity rate; hardware and other costs excluded"])
    else:
        rates = _effective(profile)
        rows = [row for row in (accounting or {}).get("rows", [])
                if row.get("provider") == profile["provider"] and row.get("model") == profile["model"]]
        total, covered, missing = 0.0, 0, set()
        fields = {"input": "input", "output": "output", "cache_read": "cacheRead", "cache_write": "cacheWrite"}
        for row in rows:
            absent = {field for field in fields.values() if not _number(row.get(field))}
            absent.update(key + " rate" for key, field in fields.items() if _number(row.get(field)) and row[field] > 0 and key not in rates)
            if absent:
                missing.update(absent)
                continue
            input_multiplier = factors.get("input_multiplier", 1)
            output_multiplier = factors.get("output_multiplier", 1)
            total += sum(row[field] * rates.get(key, 0) * (output_multiplier if key == "output" else input_multiplier)
                         for key, field in fields.items()) / 1000000
            covered += 1
        result.update(covered_records=covered, matched_records=len(rows), missing=sorted(missing),
                      assumptions=profile.get("fetched", {}).get("assumptions", ["User rate API-equivalent estimate; pricing conditions are user-supplied"]),
                      rates_used=rates, factors_used=factors,
                      source_notes=profile.get("fetched", {}).get("source_notes", []),
                      pricing_conditions=profile.get("fetched", {}).get("conditions", {}),
                      factor_notice="Only explicit user multipliers are applied; context/tier/regional adjustments are not inferred.",
                      usage_digest=hashlib.sha256(_json(rows).encode()).hexdigest(),
                      usage_sources=[{key: row.get(key) for key in ("session_id", "sequence", "response_id_sha256", "provider", "model")} for row in rows])
        if covered:
            result.update(state="known" if covered == len(rows) else "partial", amount=total)
        elif not rows:
            result["missing"] = ["Retained compatible usage for the exact provider/model"]
    if result["amount"] is not None and not _number(result["amount"]):
        result.update(state="unknown", amount=None, missing=["Finite estimate; factors overflowed"])
    return result


def _view(identity, entry, accounting):
    profiles = [{**profile, "effective_rates": _effective(profile), "estimate": _estimate(profile, accounting)}
                for profile in entry.get("profiles", {}).values()]
    return {"skill": SKILL, **identity, "revision": entry.get("revision", 0), "profiles": profiles,
            "estimates": [{"profile_id": profile["id"], **profile["estimate"]} for profile in profiles],
            "usage_coverage": (accounting or {}).get("coverage"), "usage_notice": (accounting or {}).get("notice")}


def _accounting_scope(accounting, selection):
    if accounting is not None and accounting.get("selection", selection) != selection:
        raise ApplicationError(422, "Accounting projection differs from the selected cost scope")


def inspect(app, selection, *, accounting=None):
    identity = _identity(app, selection)
    _accounting_scope(accounting, selection)
    return _view(identity, _state(app)["scopes"].get(_scope_key(identity), {}), accounting)


def _patch(body):
    allowed = {"scope", "effort_root", "expected_revision", "profile", "refresh_prices"}
    if set(body) - allowed or type(body.get("expected_revision")) is not int or body["expected_revision"] < 0 or type(body.get("refresh_prices", False)) is not bool:
        raise ApplicationError(400, "Cost skill requires explicit revision, profile and optional boolean refresh")
    profile = body.get("profile")
    fields = {"provider", "model", "billing_basis", "currency", "overrides", "factors"}
    if not isinstance(profile, dict) or set(profile) - fields:
        raise ApplicationError(400, "Unknown cost profile field")
    for key in ("provider", "model"):
        value = profile.get(key)
        if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 256 or any(ord(c) < 32 for c in value):
            raise ApplicationError(400, f"Cost profile needs exact {key}")
    if profile.get("billing_basis") not in SKILL["billing_bases"] or not isinstance(profile.get("currency"), str) or not re.fullmatch("[A-Z]{3}", profile["currency"]):
        raise ApplicationError(400, "Declare supported billing basis and three-letter currency")
    for field, keys in (("overrides", RATE_KEYS), ("factors", FACTOR_KEYS)):
        patch = profile.get(field, {})
        if not isinstance(patch, dict) or set(patch) - set(keys) or any(value is not None and not _number(value) for value in patch.values()):
            raise ApplicationError(400, f"{field} must contain finite nonnegative numbers or explicit null")
    return profile


def execute(app, body, *, accounting=None, retrieve=retrieve_rates):
    patch = _patch(body)
    selection = app.selection(body)
    identity = _identity(app, selection)
    _accounting_scope(accounting, selection)
    key = _scope_key(identity)
    with app.mutation():
        state = _state(app)
        current = state["scopes"].get(key, {"revision": 0, "profiles": {}})
        if current["revision"] != body["expected_revision"]:
            raise ApplicationError(409, "Cost factors changed; read current values before saving")
    refresh = retrieve(patch["provider"], patch["model"], patch["currency"], patch["billing_basis"]) if body.get("refresh_prices") else {"state": "not_requested"}
    with app.mutation():
        state = _state(app)
        current = state["scopes"].get(key, {"revision": 0, "profiles": {}})
        if current["revision"] != body["expected_revision"]:
            raise ApplicationError(409, "Cost factors changed during retrieval; no edit was overwritten")
        profile_key = _profile_key(patch)
        profile = dict(current["profiles"].get(profile_key, {"id": profile_key, "overrides": {}, "factors": {}}))
        profile.update({key: patch[key] for key in ("provider", "model", "billing_basis", "currency")})
        for field in ("overrides", "factors"):
            values = dict(profile.get(field, {}))
            for name, value in patch.get(field, {}).items():
                if value is None:
                    values.pop(name, None)
                else:
                    values[name] = value
            profile[field] = values
        if refresh["state"] == "retrieved":
            profile["fetched"] = refresh["snapshot"]
        profile["last_refresh"] = refresh
        profile["updated_at"] = _now()
        current["profiles"][profile_key] = profile
        current["revision"] += 1
        receipt = {"skill_ref": {"id": SKILL["id"], "version": SKILL["version"]}, **identity,
                   "revision": current["revision"], "profile_id": profile_key, "recorded_at": _now(),
                   "refresh_state": refresh["state"], "estimate": _estimate(profile, accounting)}
        profile["receipt"] = receipt
        state["scopes"][key] = current
        path = app.root / ".cost-estimates.json"
        temporary = path.with_name(f".cost-estimates.{uuid.uuid4().hex}.tmp")
        try:
            with open_private(temporary) as stream:
                stream.write(_json(state) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return {**_view(identity, current, accounting), "refresh": refresh, "factor_save": "saved", "receipt": receipt}
