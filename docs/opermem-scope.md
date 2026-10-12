# Owned reviewed Opermem lifecycle

This source module provides explicit preparation and correspondence for an actual
event-only reviewed task. Public native runner, recall, application catalog, UI
and package integration are subsequent work. It creates no controller history and
does not change native operation standing.

`scripts.noetic_opermem_scope.definition()` exposes the maintained reusable
`noetic:opermem-reviewed` descriptor, content-derived version, actual native
program IDs, operation parameters and consistent worker/inquirer/reviewer role
instructions. An explicit `OpermemScope.create_instance` creates a particular
discipline within an already existing effort. A preparation selects an existing
compatible instance; it never silently creates an effort or discipline. Every
execution and participant belongs to that exact instance and effort.

## Preparation before effects

Construct `OpermemScope(namespace_path)` with an absolute path to an existing
canonical namespace. Construction and validation are read-only. Explicit
instance creation, store registration and execution preparation use the accepted
correlation-cache algorithm with a separate adapter label and command keys.
Canonical events recover committed actions after a cache transaction failure.

`bind_store(command_id, effort_root, store_path, host)` registers a canonical
native directory and host file within the declared Noetic namespace. Registration
does not initialize or contact the native host. Registration serializes duplicate
and alias ownership checks within that namespace. Other namespaces are not
claimed as host-global ownership authorities. Its identifier is Noetic metadata;
there is no observed native UUID or workspace/scope identity yet. Pre-existing
native history stays unassigned.

`prepare_execution(request, task, workspace, runs_dir, store_ref, operation,
inquiry, client, ...)` validates:

- Exact namespace, effort, compatible instance, environment and workspace.
- Human origin with its reference, or the actual exact current initiating agent
  target, never both.
- Exact registered store/host selection and maintained client controls.
- Optional complete owned purpose reference and explicit resolver configuration.
- Explicit source selections and optional exact native occasion selector.

Only then does it reserve the canonical execution and fsync its immutable
`.opermem-preparations/<UUID>/binding.json`. The anticipated event-only run path is
explicitly a reservation. No run journal, native host, checking command, agent
session or controller is implied. Each binding freezes task bytes/hash,
assignment, declared/effective environment, full purpose/reference resolver,
models/controls and exact operation. Explicit host-source capture is bounded to
1 MiB and retains original paths, hashes and bytes. It is external host evidence;
bootstrap ExperienceId1 is never represented as substantive native experience.

The caller must finish preparation before native initialization or other external
effects. Unit1 does not wrap or invoke those native effects. Caller-owned failure
can be retained with `preparation_failed(binding, actual_diagnostic)` without a
fabricated run or session.

## Optional reviewed-executor hooks

Pass `lifecycle=adapter.lifecycle(binding)` and the exact prepared run UUID,
workspace/task/client/mode/model/controls into `noetic_develop.develop`. The
initial read-only launch guard refuses substitutions before run creation and
derives any native Telos fields from the complete owned reference. Existing
execution without a lifecycle keeps its original behavior.

The three effect-boundary callbacks are:

1. `run_created`: compare the actual native program, task, workspace, plan and
   frozen governing aggregate; retain canonical attachment, immutable run copy,
   one scope binding and optional full purpose binding before Telos begin or
   actors.
2. `before_actor`: revalidate assignment/purpose/store, reserve a genuine ordinal
   with the actual work/inquirer/reviewer mandate, and append responsibility to
   its prompt. An attempted step cannot be executed again through this hook.
3. `after_actor`: run in a finally path, inspect the actual captured client stream
   and journal events, and correlate native identity independently of successful
   report completion. It adds no process transport or provider request.

Pi's actual JSON session header and OpenCode's actual sessionID are the observed
identities. Only that evidence creates an instantiation/session. Failed startup
without a header retains an ordinal reservation, target=null and exact launch
diagnostics. Header followed by failure retains an actual failed session.
Conflicting identities remain unavailable. Malformed output does not establish
completion, although an unambiguous actual header remains recorded. A reviewer
cannot reuse the worker's native session. Context-file references remain absent
because this JSON CLI surface does not expose them.

The complete original owned purpose identity/configuration is retained and
revalidated before dispatch, verification and native Telos result recording.
Mutable goal content at the same valid identity does not rewrite the frozen
original governing context. No-purpose owned work remains supported; scoped bare
Telos selection is rejected. Native result completion can remain delayed with
the existing `defer_telos_result` option; receipt gates belong to the native wiring
unit.

## Inspection and explicit correlation recovery

`correspondence(binding)` and `inspect_preparations(effort_root=...)` are read-only.
They distinguish prepared/failed preparations, actual attached run status,
participant reservations, genuine native targets and exact retained observations.
Missing or changed assigned evidence reports unavailable; it cannot become an
unassigned legacy run. Inspection preserves original full purpose identity even
when its current source is unavailable. It makes no current semantic eligibility
claim.

`recover_preparation(execution_id)` explicitly reconstructs missing preparation
metadata from canonical retained bytes. Repeating `after_actor` can finish an
interrupted identity/cache write from original captured evidence. These operations
never execute work, verification, native submission or external acts. Historical
correspondence does not require today's initiating session still be current;
new dispatch requires current authority. No legacy adoption engine is included.

The new tests use actual disposable subprocesses that emit clearly identified
Pi/OpenCode protocol fixtures, plus isolated actual Telos source and databases.
They exercise composition ownership and failure/recovery boundaries; they do not
claim a provider session, native Opermem deposit, installation delivery or human
cognitive adequacy.
