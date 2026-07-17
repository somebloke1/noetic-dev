# External Route Canary Procedure

This procedure exercises the live external routing path introduced by issue #51. It does not itself claim that an execution has occurred.

The authoritative record is the successful protected Agent Review run and its 90-day `agent-review-<pr>-<head-sha>/agent-review-result.json` artifact. Validate it with `python3 scripts/governance/route_evidence.py --run-id <run-id> --pr-number <pr> --head-sha <head-sha>`. The validator queries GitHub to require the exact repository, protected workflow path and event, successful run conclusion, `dev` PR, candidate SHA, and unexpired run-bound artifact; it downloads that artifact itself rather than accepting caller-supplied JSON, then checks the wrapper SHA, canonical router component, classification, decisions, one invocation per decision, acknowledged outcomes, and shared immutable `decision_id`. The router's root-owned `state/decisions.jsonl` and `state/outcomes.jsonl` are corroborating host records retained with the deployed component.

Accept one execution only when those records bind the exact candidate request to protected CI, genus-router `route_task`, canonical LiteLLM invocation, and genus-router `report_outcome`. Records from separate executions cannot be combined. Broker-local routing claims and controlled test fixtures do not satisfy the procedure.
