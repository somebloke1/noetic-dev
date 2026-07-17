# External Route Canary

This candidate binds one protected review to the live external routing path introduced by issue #51.

Acceptance requires the exact candidate SHA to pass protected CI through external genus-router `route_task`, one canonical LiteLLM model invocation per decision, acknowledged genus-router `report_outcome`, and validated route evidence. Broker-local routing claims and controlled test fixtures do not satisfy this canary.
