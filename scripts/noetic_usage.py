"""Read native Pi accounting observations without changing retained evidence."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math

from scripts.noetic_sessions import SessionError


FIELDS = ("input", "output", "cacheRead", "cacheWrite", "cacheWrite1h", "reasoning", "totalTokens", "totalInput")
NOTICE = ("Adapter-reported Pi usage: input excludes cache; output already includes reasoning. "
          "Normalized cache zero does not establish raw provider field presence or cache applicability. "
          "Recorded adapter cost is a rate calculation with unverified currency/billing basis, not a bill.")


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def tokens(value):
    return value if type(value) is int and value >= 0 else None


def project(service, selection):
    registry = service.registry
    result = {"selection": dict(selection), "observed_at": datetime.now(timezone.utc).isoformat(),
              "source_domain": "native-pi-adapter", "sessions": [], "rows": [], "warnings": [],
              "structured_accounting": "not included", "notice": NOTICE}
    coverage = {"sessions": 0, "records": 0, "usage_records": 0, "duplicates": 0, "missing_response_ids": 0,
                "fields": {name: {"known": 0, "missing": 0} for name in FIELDS}}
    result["coverage"] = coverage
    selected = {}
    effort = selection.get("effort_root") if selection["kind"] == "effort" else None
    if registry.path.exists():
        with closing(registry.connect(readonly=True)) as db:
            db.execute("BEGIN")
            for source in db.execute("SELECT id,effort_root FROM sessions ORDER BY created_at,id"):
                if effort is not None and source["effort_root"] != effort:
                    continue
                try:
                    item, _ = service._select(source["id"], effort_root=effort)
                    if item["id"] != source["id"]:
                        raise SessionError(409, "Native registry binding changed")
                except (SessionError, ValueError, KeyError) as exc:
                    result["warnings"].append({"session_id": source["id"], "kind": "unavailable-binding", "detail": str(exc)})
                    continue
                view = {key: item.get(key) for key in ("id", "ordinal", "original_ordinal", "effort_root", "target", "identity_origin")}
                view.update(record_count=0, usage_records=0)
                result["sessions"].append(view)
                selected[item["id"]] = view
            seen = set()
            for sid, view in selected.items():
                for event in db.execute("SELECT sequence,at,record FROM events WHERE session_id=? ORDER BY sequence", (sid,)):
                    try:
                        record = json.loads(event["record"])
                    except (ValueError, TypeError):
                        result["warnings"].append({"session_id": sid, "sequence": event["sequence"], "kind": "unparsed-event"})
                        continue
                    if not isinstance(record, dict) or record.get("type") != "message_end":
                        continue
                    message = record.get("message")
                    if not isinstance(message, dict) or message.get("role") != "assistant":
                        continue
                    response_id = message.get("responseId")
                    if isinstance(response_id, str) and response_id:
                        identity = (sid, response_id)
                        if identity in seen:
                            coverage["duplicates"] += 1
                            continue
                        seen.add(identity)
                    else:
                        coverage["missing_response_ids"] += 1
                        result["warnings"].append({"session_id": sid, "sequence": event["sequence"], "kind": "source-sequence-identity", "detail": "Response identity absent; cross-sequence replay cannot be deduplicated."})
                    view["record_count"] += 1
                    observed = message.get("usage")
                    if not isinstance(observed, dict):
                        observed = {}
                    else:
                        view["usage_records"] += 1
                    row = {"session_id": sid, "sequence": event["sequence"], "at": event["at"],
                           "provider": message.get("provider") if isinstance(message.get("provider"), str) else None,
                           "model": message.get("model") if isinstance(message.get("model"), str) else None,
                           "api": message.get("api") if isinstance(message.get("api"), str) else None,
                           "response_id_sha256": hashlib.sha256(response_id.encode()).hexdigest() if isinstance(response_id, str) and response_id else None}
                    row.update({name: tokens(observed.get(name)) for name in FIELDS if name != "totalInput"})
                    inputs = [row[name] for name in ("input", "cacheRead", "cacheWrite")]
                    row["totalInput"] = sum(inputs) if all(value is not None for value in inputs) else None
                    row["missing_fields"] = [name for name in FIELDS if row[name] is None]
                    cost = observed.get("cost")
                    row["adapter_cost"] = ({key: value for key, value in cost.items() if key in ("input", "output", "cacheRead", "cacheWrite", "total") and number(value) is not None}
                                           if isinstance(cost, dict) else None)
                    result["rows"].append(row)
    coverage["sessions"] = len(result["sessions"])
    coverage["records"] = len(result["rows"])
    coverage["usage_records"] = sum(item["usage_records"] for item in result["sessions"])
    totals = {}
    for name in FIELDS:
        known = [row[name] for row in result["rows"] if row[name] is not None]
        coverage["fields"][name] = {"known": len(known), "missing": len(result["rows"]) - len(known)}
        totals[name] = sum(known) if known else None
    compatible = [row for row in result["rows"] if row["totalInput"] is not None]
    denominator = sum(row["totalInput"] for row in compatible)
    result.update(totals=totals, cache_share_input_tokens=denominator if compatible else None,
                  cache_share_records=len(compatible),
                  cache_read_share=sum(row["cacheRead"] for row in compatible) / denominator if denominator else None)
    return result
