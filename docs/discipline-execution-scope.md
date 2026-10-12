# Structured discipline execution scope

`scripts/noetic_disciplines.py` connects maintained cognition/development harness
runs to the canonical `ScopeStore`. The namespace, effort and definition/instance
must already exist. Run UUIDs, controller-local actor labels, artifact identities,
command receipts and submission recovery retain their native meaning.

## Python and CLI contract

```python
from scripts.noetic_disciplines import Disciplines, correspondence
from scripts.noetic_harness import start

adapter = Disciplines('/explicit/app-state/ordinals.sqlite3')
instance = adapter.create_instance(
    command_id='owner-assignment-123', effort_root='0.0', initiator='0.0',
    pattern='cognition', intent='Investigate the stated question',
    environment={'cwd': '/explicit/project'},
)
assignment = {
    'namespace_path': '/explicit/app-state/ordinals.sqlite3',
    'effort_root': '0.0', 'discipline_id': instance['id'],
    'environment': instance['environment'], 'origin': 'human',
    'human_ref': {'owner': 'actual-owner-reference'},
}
run_dir, state = start('cognition', 'The bounded question', workspace, runs_dir,
                       client='pi', model=selected_model,
                       scope_request=assignment)
refs = correspondence(run_dir, namespace_path=adapter.path, effort_root='0.0')
```

Instance creation requires the explicit current owning environment. The stored
instance freezes that environment and the maintained definition identity/version
(content digest plus native pattern version). Replaying the same instance
`command_id` and request returns the original instance; conflicting reuse rejects.
A new execution can use an existing instance without making a new effort or
instance. This bounded adapter supports local `environment.cwd` execution.
`Disciplines(path, readonly=True).validate(request, pattern, workspace)` provides
preparation preflight without schema, namespace or cache mutations.

Development may supply an optional `preparation` object containing the maintained
`projects.task_worktree` result. Its original `project` must match the frozen
instance environment; `workspace` must match the actual execution directory. The
adapter verifies source repository/common-dir correspondence, the listed owned Git
worktree, actual base commit and the retained initial-files baseline. Execution
records retain actual workspace, preparation/baseline and source links. The effort
and instance keep their original project identity. Unrelated worktrees, changed
baselines and mismatched preparation reject before actor execution.

`initiating_target` can name an exact current native participant.
`parent_instance` requires that participant to belong to the parent instance.
An agent-origin execution request uses `origin: agent`, omits `human_ref`, and
supplies `delegator: {ordinal, instantiation, session}` naming the instance's actual
initiator. Scope and definition/environment mismatches reject before actor effects.

```bash
python -m scripts.noetic_disciplines --namespace-path /explicit/ordinals.sqlite3 \
  instance /explicit/instance-request.json
noetic harness start cognition /explicit/task.md --workspace /explicit/project \
  --runs-dir /explicit/runs --client pi --model PROVIDER/MODEL \
  --scope-request /explicit/execution-assignment.json --max-activations 0
python -m scripts.noetic_disciplines --namespace-path /explicit/ordinals.sqlite3 \
  inspect /explicit/runs/RUN_UUID
```

The instance request JSON contains the `create_instance` keyword arguments above.
The execution assignment JSON has the exact `assignment` shape above. Harness
advance/cancel/pause/resume use the frozen native run and assignment; no new
namespace or effort is inferred from cwd or environment variables.

## Responsibility, occurrence and recovery

Each actor receives a genuine child ordinal of the instance initiator before
launch, with its actual role, bound inputs/result contract, definition, environment
and limits in its mandate. Review subject and phase dependency bindings remain
artifact relations. They never create delegation parentage. Every new activation
and execution retains distinct participants, native controller IDs and session IDs.

Human assignment records its explicit human reference. Agent assignment requires
the exact initiator to remain current for each new delegation. Once that target
becomes stale, a new participant fails before launch. A previously committed
reservation replays its earlier authorization without claiming another agent call.
Human assignment is a supported choice when no continuing initiating runtime is
required. Root `0` can remain dormant.

The adjacent `ordinals.sqlite3.correlation.sqlite3` is a serialized command/result
cache. Canonical ordinal records and append-only history remain authority. Each
mutation retains a deterministic native-occurrence key and request digest in its
canonical source reference. A committed canonical act with a lost cache write is
recovered from that event. Cache loss, exact replay and concurrent callers cannot
allocate the same native participant a second time. Conflicting requests reject.

Controller exports correlate native activations, actual process/check observations,
artifacts/digests/input bindings, QA subjects and accepted command receipts. Native
RPC/stream observation attaches an actual instantiation and session; a namespace
reservation alone supplies neither. Terminal activations close their participant
position and close/fail their observed session. Effort status and native memory
standing are independent. Controller QA never promotes native Opermem standing.

Existing envelope replay remains authoritative. Interrupted execution without a
complete envelope retains uncertainty and effects and does not silently rerun.
Pause stops subsequent ready activations; cancellation and confirmed cleanup retain
separate evidence. A failed start without native identity retains its reserved
position and logs without inventing a session. Correlation does not invent missing
legacy history or adopt unscoped runs.

## Maintained runtime evidence

Scoped Pi uses its maintained RPC protocol. `get_state` observes native session ID,
context reference and model before the prompt is sent. The host checks the selected
model, persists `native-observation.json`, and registers the exact target first.
Completion waits for `agent_settled` and obtains the native final messages through
`get_messages`; `agent_end` alone is insufficient. Source-inspected contracts:
installed `@earendil-works/pi-coding-agent/docs/rpc.md`, `docs/rpc-commands.md` and
`dist/modes/print-mode.js`. Print mode's header does not expose a context file.

Scoped OpenCode retains its existing CLI protocol. The host observes `sessionID`
from the live native stream and records it during execution. This CLI seam does
not expose its native context-storage address; `context_file: null` and explicit
coverage preserve that limitation. A failed stream can retain observed identity
without receiving a controller result. Neither adapter claims provider access
from model-free fixture checks.

## Read-only consumer handoff

`correspondence(run_dir, *, namespace_path=None, effort_root=None)` opens native
metadata and the canonical namespace read-only, without creating a cache/store.
Explicit foreign effort/namespace selectors reject. Missing or inconsistent scoped
bindings/records raise `ScopeError`; genuine legacy absence returns
`correlation_status: unassigned`.

`validate_binding` checks the retained run binding against its native journal and
canonical execution assignment before driver effects, correlation mutations,
control changes or exports. Editing both native metadata copies cannot change the
canonical environment, preparation or responsible origin. Read-only preflight
also requires the request namespace to agree with the configured store before
resolving instance IDs. Historical validation checks accepted assignment identity;
it does not reauthorize an obsolete initiating session or recompute a baseline
already changed by accepted work.

Assigned results contain `namespace: {id, path}`, `effort_root`, `discipline_id`,
`execution_id`, `definition_ref`, frozen `environment`, `native_run`, `source_refs`,
and `participants`. Each participant supplies its absolute `ordinal`, `origin`,
`activation_id`, `actor_id`, immutable observed `target` or null, native agent/session
references, position/session statuses and source references. Later native succession
cannot silently replace the activation's historical exact target.

Purpose/recall consumers should validate the selected namespace/effort first, then
join artifacts by activation ID to these exact targets. Unobserved participants
cannot satisfy an exact-session search. Complete canonical history remains available
through `ScopeStore.history` pagination. Sources and last-known native observations
are exposed independently of derived reports.

Application/UI selected-scope launch, purpose routing, recall ranking, result
application and installed release adoption remain later consumer adapters. The
maintained controller supports two serial patterns; this increment does not claim
arbitrary program authoring, parallel role execution, all native memory operations,
provider availability or complete product acceptance. External development remains
independent of product sessions and root responsibility.
