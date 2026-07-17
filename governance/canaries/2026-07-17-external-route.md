# External Route Canary Procedure

This procedure exercises the live external routing path introduced by issue #51. It does not itself claim that an execution has occurred.

Accept one execution only when external records bind an exact candidate SHA and request to protected CI, genus-router `route_task`, one canonical LiteLLM model invocation, acknowledged genus-router `report_outcome`, and validated route evidence. The route, invocation evidence, and outcome must carry the same immutable `decision_id`; records from separate executions cannot be combined. Broker-local routing claims and controlled test fixtures do not satisfy the procedure.
