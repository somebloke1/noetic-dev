# Application effort consumer contract

The HTTP application and developer sessions share the exact resolved canonical
namespace path. An explicit `namespace_path` server argument takes priority;
otherwise the maintained session adapter selects installation-owned state or the
supplied runs root. The current working directory never selects an effort.

## Structured work

An effort already registered through the session/effort controller owns each new
structured application run. The application does not create an effort when a
folder is selected. Instantiate a maintained discipline through
`POST /api/disciplines`:

```json
{
  "command_id": "human-request-unique-key",
  "effort_root": "0.0",
  "initiator": "0.0",
  "pattern": "development",
  "intent": "Implement the requested change",
  "environment": {"cwd": "/absolute/source/project"}
}
```

The response is `{discipline: ...}` with an integer `id`, actual frozen
`definition_ref`, owning `effort`, `initiator` and `environment`. Optional
`initiating_target` names an exact actual agent target; `parent_instance` names a
real containing instance. Definition identity/version comes from the maintained
pattern, rather than a caller-supplied label.

`POST /api/application/start` carries existing task/client/model/verification
options and `effort_root`, `discipline_id`, the instance's exact `environment`,
and its assignment origin. Human assignment requires `origin: "human"` and a
nonempty `human_ref` object. Agent assignment requires `origin: "agent"` and
`delegator: {ordinal, instantiation, session}` naming the instance initiator's
actual current target. It cannot also claim human origin. Caller namespace paths
are rejected. Bare `telos_chain` options are rejected; attach a complete
`purpose_ref` returned by the purpose adapter.

The adapter validates the source project, frozen definition, effort and exact
initiator through the discipline adapter's read-only preflight before preparing
a project or launching a process. Development still uses the maintained
controller-owned worktree preparation. The actual preparation result is passed
to the harness as execution correspondence, preserving the effort's declared
source environment and the exact execution workspace, baseline and destination.
Existing active work in the same source project prevents concurrent starts even
when those starts select different efforts. The native harness owns execution,
participant allocation, checkpoint transitions and native identity observation.

## Run investigation and control

Every HTTP run read requires `?effort_root=0.0`, or explicit
`?scope=application` for retained global history. This applies to list/detail,
reuse setup, project files/changes, activation logs/transcripts and retained
legacy worker/reviewer transcripts. Ownership is checked before content is read.
Run list and detail responses carry `correspondence`, including assigned versus
unassigned status, namespace, owning effort, instance/execution and participants'
exact targets/native references. Global history includes honestly unassigned
legacy runs; it does not adopt them or fabricate ancestry. Unresolved mappings
are excluded with warnings and partial coverage.

Run action bodies carry `effort_root` or `scope: "application"`, plus the existing
exact action fields: advance `mode`, Apply/cancel `confirm`, summary `save`, or
pause with no additional fields. Ownership is checked before any process,
inference or file effect. The selected run identifier and retained controller
version/activation contracts remain authoritative. Apply keeps the existing
baseline, drift, review and backup requirements; effort separation does not
weaken concurrent workspace protection. Explicit application mode retains
investigation/control of unassigned native controller histories.

## Purposes

`GET /api/goals` uses the same effort/application selector. It returns
`purposes`, `stores` and `coverage`. Each purpose retains the native aggregate
under `native` and a complete `reference` containing owner namespace/kind/ordinal,
store identity/path, native chain ID and configured component source. Store
status is `available`, `absent` or `error`; partial/native-unavailable results keep
the source error. Browsing initializes neither namespace nor native stores.

Global purpose history optionally includes the explicitly configured legacy
store with `include_legacy=true`; those references remain unassigned and read
only. `GET /api/goals/<chain_id>` may additionally select `store_id` in application
scope. Ambiguous IDs are rejected instead of choosing the first aggregate.

`POST /api/goals` requires `goal`, an owning effort/application selector,
nonempty `origin_ref` and `source_ref`. Optional `owner` must be inside the
explicit scope. It returns `{purpose: {reference, native, ownership_event}}`.
The complete reference is validated against configured namespace, owner, native
store and source before binding its exact database/chain into a harness run.
Native Telos completion and typed-memory receipt rules remain authoritative;
completed work does not silently complete its primary governing chain.

## Recall

`GET /api/search?q=...` performs service-free lexical recall using explicit
`effort_root` or `scope=application`. Add `ordinal` for ordinal history, and both
positive `instantiation`/`session` selectors for exact retained session recall.
An optional effort root must own that exact target.

`POST /api/memory/semantic` accepts `query`, optional `limit`/`reindex`, and either
one direct effort/application selector or a `selection` object:

```json
{"kind":"session","effort_root":"0.0","ordinal":"0.0.1","instantiation":1,"session":1}
```

Supported kinds are application, effort, ordinal and session. Collection resolves
canonical ownership before reading sources, then uses the maintained scoped
lexical/semantic APIs. Semantic cache identity includes actual namespace,
selection and source roots before any embedding request. Different scopes use
different derived caches; embedding identity changes still require explicit
reindexing. Invalid or foreign selectors are rejected before inference or cache
creation. Missing embedding capability produces its explicit source error.

Recall reports identity, selection, coverage, diagnostics and status. It includes
paged retained developer observations and scoped current controller bindings;
it discloses retained native-context references, excluded/incomplete sources and
current-versus-historical distinctions. Application recall before namespace
registration can investigate genuinely unassigned legacy records with explicit
`unregistered-legacy-only` status. It does not infer a root or initialize stores.
Ranking, summaries and controller QA never confer native semantic standing.

## Bounded evidence

`tests/programs/test_effort_application.py` exercises disposable real HTTP servers,
actual local model-free Pi RPC processes, A/B/R ownership with shared cwd,
per-effort native Telos stores and exact binding, lexical and fake HTTP embedding
scope isolation, stale/foreign rejection before effects, source worktree
preparation, checkpoint continuation and reviewed Apply. Existing application
and capacity fixtures retain their useful behavioral checks under explicit scope.
These checks verify the consumer boundary; they do not establish human cognitive
adequacy or complete application delivery.

## Reviewed native inquiry

The catalog includes `opermem-reviewed` (`noetic:opermem-reviewed` with the maintained
exact descriptor/version), real reusable instances, and operation-specific inputs.
The application starts read-only inquiry, defaulting to `question`; the descriptor's
fourteen operation capacity still requires each operation's actual native ancestors
and closed evidence. Existing controller development retains its worktree and Apply
workflow. Reviewed inquiry has no Apply, pause, Stop, or continuing conversation
contract. A reserved participant is not a native session; a closed client process
session cannot acquire conversational authority from appearing in history.

Installation configuration selects an absolute `NOETIC_OPERMEM_HOST` (or explicit
`create_server(..., opermem_host=...)`). `GET /api/configuration` inspects file and
platform readiness without starting a native host. The host requires its regular
executable sibling `opermem-child`. There is no native backing inferred from cwd,
recovery history, browsing or application startup.

`GET /api/opermem/stores?effort_root=ORDINAL` lists canonical registrations, retained
qualified native identities and unobserved current standing. `POST` on that endpoint
requires `{command_id, effort_root, directory}` with an explicit absolute backing
directory. Registration binds the installation host to the existing effort and
writes correspondence only; native bootstrap occurs during explicit execution.

`POST /api/disciplines` selects `backend: "opermem-reviewed"`, command identity,
existing effort/initiator, intent, exact environment and explicit human or agent
origin. Human origin carries `human_ref`; agent origin carries the current exact
`delegator`. The adapter checks actual canonical authority. A GUI label is not an
agent delegator.

`POST /api/application/start` selects that backend and requires `command_id`, existing
`effort_root`, `discipline_id`, exact `environment`, origin evidence, `workspace`, task
and registered `store_id`. Optional fields are `definition_ref`, sources (explicit
absolute retained file selections or `{source_id, source_text_sha256, selection?}`
from scoped recall, total <=1 MiB), operation, operation-specific
`selectors`, client/model/qa_model/thinking/timeout, full `purpose_ref`, and original
qualification packet. Purpose configuration is resolved on the server. Namespace,
raw Telos chain/database/source and native host/store overrides are refused. Selected
files inside application history require their owning effort before content reads.
A recall selector resolves the complete qualified source through the accepted collector;
its optional exact ordinal/session selection must belong to the present effort. The
original text fingerprint must still match. The frozen qualified record is retained
whole as a private external source JSON file; callers cannot substitute source text.
The source bytes remain external evidence; they do not become bootstrap experience
content or native semantic standing.

Checking additionally selects absolute `checking_spec` and `checking_context` source
paths. The maintained closed-spec and whole-context validators check the declared
anchors, command, bounded scope, selected tests, predicates and source hashes before
dispatch. Command cwd must match the declared workspace. The retained context source
is historical external evidence; the driver retrieves and validates the actual
native context again before the maintained checking capture executes. It is not a
caller override of native authority.

### Checking preparation example

A fresh closed specification and retained whole native context can be prepared from
an explicit editable recipe; no spec JSON is hand-edited and no old artifact
references are reused. Global flags precede the subcommand, `--command` takes the
exact argv last, and preparation never executes the command, captures evidence,
submits, admits or judges. Select an existing unchecked native condition whose
bounded claim is that an unexecuted required test cannot fulfill Checking.
`CONDITION` and `WARRANT` are its exact IDs in `STORE`. From a source checkout,
replace `noetic` with `python3 -m scripts.noetic` from the repository root.
`RUNS` may be absent (the command creates it privately) or an existing directory
owned by you with mode `0700`. `FRESH_DIR` must not exist; its parent must already
exist. Create neither the output directory nor a public run-history directory:

```sh
noetic opermem --host HOST --store STORE --runs-dir RUNS \
  prepare-checking \
  --parent-id CONDITION --warrant-id WARRANT \
  --output FRESH_DIR --cwd PROJECT \
  --scope "Only the exact selected unittest identities." \
  --timeout-seconds 10 \
  --test tests.programs.test_noetic_opermem_checking.CheckingCaptureTests.test_missing_selected_test_cannot_fulfill \
  --predicate exact "missing selected test yields indeterminate, never fulfilled" tests.programs.test_noetic_opermem_checking.CheckingCaptureTests.test_missing_selected_test_cannot_fulfill \
  --source /absolute/python actual-python \
  --source /absolute/scripts/noetic_checking_tests.py test-runner \
  --source /absolute/scripts/noetic_opermem_checking.py checking-module \
  --source /absolute/tests/programs/test_noetic_opermem_checking.py assertion-source \
  --environment LANG C.UTF-8 --environment PYTHONDONTWRITEBYTECODE 1 \
  --command /absolute/python /absolute/scripts/noetic_checking_tests.py --module-dir /absolute/project --module-dir /absolute/project/tests/programs tests.programs.test_noetic_opermem_checking.CheckingCaptureTests.test_missing_selected_test_cannot_fulfill
```

`FRESH_DIR` receives `spec.json` (closed `noetic-checking-spec/v1`), `context.json`
(the inner whole native context, not a CLI wrapper) and a descriptive
`preparation.json` receipt naming the actual retrieval transcript and selected
host/store route. The route is descriptive provenance; matching numeric IDs or cut
values in another store do not establish the same residue. These phases are
distinct: **preparation** writes the closed recipe artifacts only; **executable
capture evidence** happens later when the host runs the exact command and retains
manifest, stdout, stderr and sources; **native evidence admission** submits that
captured contribution through the existing checked condition; and any **Judgment**
over the admitted result, together with human valuation of its worth, remains a
separate later act. An unexecuted selected test never fulfills a condition; a
source file that changes after preparation is rejected by the existing application
preflight and capture before any effects. The output directory must be fresh;
existing directories are rejected unchanged. This proves bounded artifact
preparation only — not checking success, production readiness or whole-framework
standing.

Acting selects native plan/step IDs plus either an owned `observed_run_id` (optional
`observed_step` work/verify/review), or `observation_evidence` with its original
`observation_manifest_sha256`. The archive's original source run must retain owned
application correspondence in the selected effort. Scope and maintained occurrence
validation precede launch. Acting observes the retained occurrence; it never launches
or repeats that original external act. An unassigned archive needs a future explicit
source correspondence contract and is unavailable to this owned application path.

### Launch receipts and interruption

The HTTP action returns 202 without waiting for work/review. Its first response may
be a **queued launch receipt** with `run_id` and `execution_id` null. Those fields
become actual identities only when `run_task(..., on_prepared=...)` observes the one
original preparation. The callback never allocates a second execution. Concurrent
same-command/same-frozen-request calls retain one receipt, driver, preparation and
worker/reviewer pair. Same command with a changed request conflicts. Preflight runs
before capacity admission and again inside the independent driver.

`GET /api/application/launches?effort_root=ORDINAL` and
`GET /api/application/launches/LAUNCH_ID?effort_root=ORDINAL` report the durable frozen
request digest, driver lock, actual PID/start-ticks/boot/group evidence and original
prepared observation. A process lock establishes ownership, not model progress.
The independent driver survives server/browser disconnection. There is no automatic
restart when its effects become uncertain.

An fsynced immutable `prepared-observation.json` precedes the derived receipt update.
Inspection can recover the actual relation in memory if that update is lost; explicit
correlation recovery can restore the derived receipt. If the original callback
record is missing, its derived mapping cannot authorize correlation. The application
reports a gap and never guesses from shared cwd, timestamp or newest run. Canonical
preparations remain visible even when native startup fails before journal creation.

### History, recall and recovery

Existing run list/detail and runtime population show the same canonical ownership,
actual preparations and real reserved/observed work/review participants. Foreign
assignments are refused before content. Corrupt assigned history stays diagnostic;
it cannot fall through as unassigned legacy. Legacy history remains available only
at explicit application scope. Review acceptance, retained native receipt and Telos
synchronization are distinct dispositions. Retained packets keep original cut,
standing, voices and exclusions; current native admission is unobserved.

`POST /api/runs/RUN_ID/recover-correlation` with `effort_root` restores only retained
correspondence/preparation/derived receipt. `recover-contribution` delegates to the
accepted `resume_run` receipt-first path: original pending native command replay when
needed, or receipt-only Telos synchronization. Neither reexecutes checking, actors,
or original external action. Active driver ownership refuses recovery. Original host
and purpose source must remain available; the application never replaces them with
the latest release's components.

Scoped lexical and semantic APIs use the accepted recall collector. Exact work session
recall returns its own captured report, without reviewer output or execution-global
native/task evidence. Lexical inspection remains usable without embeddings. Reuse
setup produces an editable unbound draft preserving task/source selections and safe
settings, while clearing effort, instance, backing, purpose, targets and predecessor
selectors. A new command identity and current authority must be selected and validated
at launch.

### Private native component closure

Private release build accepts optional `--opermem-host`, `--opermem-child`,
`--opermem-manifest`, `--opermem-notices` together. Stage exact copied pair bytes as
single-link regular files; Cargo's hardlinked build artifacts do not satisfy the
established archive input gate. The component manifest pins both hashes, source/binary
evidence references, Linux x86_64 GNU and glibc >=2.39 requirements. SQLite is bundled;
system libc/libgcc_s/libm/loader remain host dependencies. The archive retains the
existing 256 MiB aggregate cap and exact allowed component paths. Installation restores
0700 on the two exact executables, validates their hashes/platform and retains older
releases. Component notices describe the private owner boundary and do not assign a
redistribution license to Opermem. Existing Noetic/Telos notices are unchanged.

New explicit registrations use the installation's selected host. Existing registrations
keep their original canonical absolute host path across `current` changes; no silent
retarget or historical rewrite occurs. Missing historical components are a concrete
recovery limitation. The required wheel/import closure includes the scope helper,
application transport and maintained checking test runner. Disposable verification
covers the actual isolated archive/installed HTTP/native path without donor imports,
models or provider calls. This proves bounded composition delivery, not whole-framework
completion, all-platform qualification or human cognitive value.
