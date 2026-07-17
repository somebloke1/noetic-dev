# External Route Canary Procedure

This procedure exercises the live external routing path introduced by issue #51. It does not itself claim that an execution has occurred.

Accept one execution only when external records bind an exact candidate SHA to protected CI, genus-router `route_task`, one canonical LiteLLM model invocation per decision, acknowledged genus-router `report_outcome`, and validated route evidence. Broker-local routing claims and controlled test fixtures do not satisfy the procedure.
