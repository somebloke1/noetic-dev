# Delivery packet preparation

`scripts/tools/prepare_delivery_packet.py` prepares a new review packet from the
integrator's proven delivery templates and exact current/candidate artifact
receipts. It uses Python 3's standard library. The integrator retains ownership
of smoke checks, maintenance and deployment.

```sh
BASE=/absolute/path/integrator-packet
python3 scripts/tools/prepare_delivery_packet.py \
  --status "$BASE/status.json" \
  --templates "$BASE/F007-delivery" \
  --candidate "$BASE/F010" \
  --output "$BASE/F010-delivery-draft"
```

The candidate's `payload-verification.json` must already exist. Candidate,
template directory and new output directory must share the status file's parent,
because these templates use sibling-relative paths. Choose an output basename
that preserves the recipient's ownership and does not exist. Existing paths and
evidence are refused. A result is `PREPARED ONLY`; source acceptance is external
and never inferred from a packaging receipt. Template code is parsed for syntax
without import or execution. The helper makes local file reads and writes only.

Inputs are bound through the current status's `installed_release`,
`current_source_base`, `current_frozen_manifest` and `last_deployment_evidence`.
The current payload's release/archive must match that receipt. Both prior and
candidate archive, wheel, source manifest and every listed source file must match
their exact declared hashes. This confirms artifact correspondence with existing
receipts; it does not repeat source QA or establish live installed behavior.
The generated deploy script retains its own exact previous-pointer assertion.

Exactly five line spans change:

| Template | Field | Value source |
| --- | --- | --- |
| `deploy.py` | `CANDIDATE` sibling basename | Explicit candidate directory |
| `deploy.py` | Exact previous release assertion | Current status bound to prior payload/deployment receipt |
| `deploy.py` | `prior_build` sibling payload path | Current status's source unit |
| `deploy.py` | Prior archive SHA assertion | Bound prior payload and actual archive bytes |
| `final-smoke.py` | `BASE` sibling basename | Explicit candidate directory |

Every other template byte is retained. `session-maintenance.py` is copied
verbatim. Unknown formats, ambiguous matches and disagreement between the two
template candidate names are refused before output creation. Original line
endings outside those spans are preserved. Existing environment filtering,
idle checks, native IDs, rollback/finally, wrapper/configuration preservation and
history/run/native checks remain the template's exact bytes.

The new directory contains those three scripts plus `preparation.json`, which
records actual local preparation time, input/output hashes and exact old/new
field values. Stdout returns a short receipt reference; errors use `error:` on
stderr and exit 1. Validation precedes directory creation. A filesystem failure
during writing can leave an owned incomplete packet for inspection; the helper
does not remove or overwrite it. Only a complete preparation receipt describes
a finished packet.

Read the preparation receipt and corresponding input evidence before using the
packet. Live status may change after preparation; the copied previous-pointer
assertion remains the execution boundary. Template assumptions belong to the
integrator's actual maintenance workflow. This helper does not discover newer
templates, alter services or authorize their execution.

This applies a reusable transformation to repeated packet construction. Actual
future uses determine whether construction and upkeep are worthwhile; no provider
token, paid-cache or throughput claim follows from generating a packet.

```sh
python3 -m unittest discover -s tests/tools -p test_prepare_delivery_packet.py -v
```
