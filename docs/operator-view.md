# Local Operator Workspace

The operator provides continuing developer sessions with ordinary conversation, active steering and real rooted delegation. See [Developer sessions](developer-sessions.md) for project startup, agent tools, persistence and stop/reopen behavior. These external development agents do not assert native Opermem judgments or external-act authority.

Structured development/cognitive patterns remain available under **Tools & structured workflows**. Their orchestration lives in `noetic_application.py`; `noetic_harness.py` owns execution and the kernel owns phases, budgets, contracts, transitions and acceptance. Historical flat activation ordinals retain their original meaning.

GET/HEAD requests do not update original stores, refresh exports or invoke models. Explicit semantic retrieval and supporting summaries may call configured local models. No global client settings or credential stores are edited or exposed.

## Start

From the repository root:

```bash
python3 scripts/noetic_web.py --runs-dir .runtime/runs --port 8765
```

Open the private pairing URL printed to the owner's terminal (`/#token=...`).
The public root displays a locked shell until paired. See [Operator Access](operator-access.md)
for token files, lock/logout and explicit rotation. Stop the HTTP server with Ctrl+C. **Already launched
drivers continue independently**; use Pause or Cancel before stopping the server
if that is your intention. No npm or browser extension is needed. Reading history
needs no model service. Executing work needs the selected Pi/OpenCode client and
its normal provider configuration. Python uses its standard library;
SQLite must have FTS5 for search, as required by `noetic_memory.py`.

The default runs directory is `.runtime/runs` under the current working directory.
The CLI binds to `127.0.0.1` and requires a local operator token for all APIs.
`--port 0` selects an available port and prints the actual pairing URL.
`--token-file PATH` selects the managed token file; by default it is
`RUNS_DIR/../.operator-access/token`. Startup creates/reuses this private token,
but does not create a missing runs directory merely to display an empty register.

## Conversational project sessions

The fresh screen asks **What do you want to build?**. **Open / Create project**
registers a distinct effort from its declared intent and environment. Create-new
accepts an absent/empty folder; open-existing preserves files and prepares Git.
Repository preparation uses the maintained project helper; worktrees are not a
user prerequisite.

**Projects / efforts** reads enduring positions independently of conversations.
An empty effort remains navigable. Its ordinal tree represents genuine parentage,
with exact instantiation/context selectors underneath each position. Closed,
failed and superseded contexts remain accessible. Position selection opens its
responsibility/history view; context selection opens that particular native
journal. Selection and drafts persist in this browser tab. Refresh follows the
selected exact context and cannot change an action's recipient.

**New conversation** starts a new native context at the selected ordinal.
**Reopen agent** resumes the selected retained native context; it resubmits no
old prompt. Under **Responsibility handoff**, a successor requires explicit
responsibility and context handoff and keeps the same ordinal. Old recipients
remain exact: sending to a superseded context reports an error. **Stop work**
clears queues before abort; **Close agent** cleans up its selected owned process,
including historical processes. Steering, follow-up, dialogs, source links and
real delegated child contexts retain their exact effort/session scope.

**0 · Application root** reads the logical root and history without inventing a
running model. **Application history** deliberately traverses all efforts.
History and native journal pages continue until exhaustion, including records
beyond the first 100/500 entries. Original root-local histories appear under
**Original namespaces · unadopted**, with their own labels and journals; they are
not automatically merged or adopted. Session metadata and original events
remain under **Session details & evidence**.

Structured workflows, Memory and Purposes currently have **application-wide /
unassigned** scope, shown explicitly in their pages and workflow register. Their
global APIs and deliberate functionality remain available. Selecting an effort
does not claim ownership of those results; explicit mapping is a later backend
unit.

## Structured workflow surfaces

Open **Tools & structured workflows → Recorded workflows** and expand **Recorded workflows & attention** for the historical register. These controls retain the controller behavior described below.

The first screen is a compact agent-session workspace, following noetic-pi's
selected-agent main panel and secondary observability surfaces. A scrollable
Sessions rail selects one task. Its progress strip shows the current phase,
agent role/ordinal and configured model, with real **Continue**, **Next step**,
**Pause after step** and **Stop task** controls when the shared controller supports
them. Failed, uncertain and pending stop/pause states remain actionable signals.
The main pane shows assistant/tool activity. Tool inputs/outputs expand on demand; transcript metadata and complete raw/normalized
records are under **Details & evidence → Transcript records**. Structured responses
show substantive content once, omit empty protocol fields and missing timestamp
placeholders, and retain actual completion/retry states. Identical assistant/final
bodies are coalesced; distinct responses remain visible. The raw retained contract
stays inspectable.

**Follow current agent** follows new activations. Choosing an older agent disables
following and preserves that selection during polling. The selected session's
agent list retains the kernel's assigned ordinals (`0.0`, `0.1`, ...). These are
flat activation ordinals; no persistent root agent or delegation parentage is
invented. Legacy journal runs use their actual worker/reviewer transcripts and
recorded work/verify/review progress. No controller lifecycle controls are shown
for those runs, and unfinished journal state does not assert process liveness.

**Details & evidence** opens task criteria, source paths, timestamps, purpose links,
controller/artifact evidence, reports, comparisons and the event timeline. The
initial screen and fresh session selection keep this drawer closed. Memory,
Purposes, History and Models and services remain in the rail's **Tools** expander.
On narrow windows **Sessions** opens the rail; selecting a session closes it.
Evidence and model text use DOM `textContent`, never executable HTML.

- **New structured workflow:** a task composer, project folder, workflow and explicit
  client/model profile. Development can select its real host check through the implementation agent; a JSON verification argv is an optional override.
  Model, Review & checks, Execution limits, and Purpose & sources occupy one focused settings pane at a time. Inactive workflow/client drafts are retained. Settings remain frozen per run.
  The composer launches an actual backend task; it does not imply interactive
  chat or prompt steering. **Reuse setup** prepares a separate editable task.
- **Profiles:** Pi `openai-codex/gpt-6.1-sol` and OpenCode `openai/gpt-6.1-sol`
  are the Sol 6.1 starter routes verified in the configured client inventories.
  The initial form selects Pi Sol 6.1 with high thinking. Neither configured
  LiteLLM inventory lists a Sol 6.1 alias, so those presets are omitted. Use
  Custom client/model for an explicitly configured route; no alias or fallback
  is substituted. Empty QA model inherits the selected main model. Profiles and
  configured limits do not establish current authentication, availability or
  exercised context capacity.
- **Purposes:** list/read native Telos aggregates, deliberately create a purpose,
  and select it for a new pattern. The default database is `RUNS_DIR/../telos.sqlite3`;
  `create_server` may receive explicit `telos_db` and `telos_source` keyword arguments.
  Reads use a temporary SQLite backup before calling the real core, so opening or
  migrating the core cannot mutate the original. An absent DB stays absent on GET.
  Purpose editing/deletion and forced completion are not exposed.
- **Population/history:** filter runs by state, pattern, text and actor role; inspect
  actor ID, ordinal, phase, generation, visit, lifecycle, session reference and
  configured model/provider. Session inspection adds observed model/provider only
  where the retained transcript records them. Missing observations stay explicit.
- **Phases and recurrence:** current role inputs/criteria, accepted or effective
  outputs, historical attempts, subject-specific QA findings and remediation,
  cognitive returns with source/target/reason/question. Raw JSON is secondary.
- **Compare artifacts:** side-by-side immutable content and current standing. The
  left pane is horizontally resizable on desktop; phone comparison stacks.
- **Agent output:** structured Pi/OpenCode assistant, tool and final/step-finish
  activity with recorded timestamps, plus a bounded raw fallback. There is no PTY,
  editable prompt, or interactive input. Retired sessions remain readable; closing
  the session view never pauses or terminates the run.
- **Needs attention:** failed/blocked/intervention state, returns and failed QA
  reports link to their owning run, activation and artifact. Historic findings are
  not represented as current unresolved defects; current kernel state remains shown.
- **Persistence:** tab-scoped sessionStorage form drafts (including task/source text), filters,
  selected run, view and per-run evidence selections survive reload. Background
  refresh does not overwrite form edits or force the transcript to its bottom.
  Text is not sent to a model merely by entering it or selecting a view.
  Lock preserves drafts/selections but clears pairing and displayed evidence;
  logout also forgets drafts/selections. Neither writes to localStorage.

## Reuse Setup

Select a readable harness run and choose **Reuse setup**, separate from execution
controls. The authenticated `GET /api/runs/ID/reuse-setup` reads frozen `options.json`
and controller purpose/workspace/external inputs. Confirm replacement of the current
New pattern draft; declining, a failed read, an unsupported setup, a changed run
selection or edits during the read leave the draft intact. Nothing starts or advances.

The result is an **editable draft, not resumed/cloned**, visibly naming its source
run. Profile becomes Custom. Purpose text, workspace reference, client/model/QA model,
thinking, whole-second timeout, zero-inclusive budgets and JSON verification argv
are copied without clamping or shell splitting. Only exact `{ref: "..."}` sources
that round-trip through the one-reference-per-line field are supported, including
spaces inside references, ordering and duplicates. Rich content, arbitrary external
inputs, missing/inconsistent required options, generic/kernel-only histories,
out-of-form values and changed historical pattern definitions are rejected as a whole.
The source must match today's built-in development/cognition definition (including
the harness's Telos binding when present); this is not historical pattern replay.

A missing/null main model remains blank and visibly unresolved, requiring an explicit
model before normal submission. Missing/null QA model is blank with an inheritance
notice; null cognitive verification remains blank/null. Empty-string model values
are not silently converted to null. Workspace means its current contents, not a snapshot.
Telos selection is always cleared, including an already-selected UI choice. The old
chain is identified only as source information: its frozen governing snapshot,
subgoal and `goal_ref` are not copied. Choose a current purpose explicitly if wanted;
the task text is not automatically rewritten to reconcile old and new purpose semantics.

Source information and warnings remain with the tab draft through edits and reload,
are hidden while locked and forgotten on logout. They are never launch parameters.
Only **Start task** uses normal validation, shared capacity and active-workspace
exclusion to create a new UUID and fresh role sessions. No origin history is modified.

## Driver Ownership

Start calls `harness.start(max_activations=0)`, receives the actual run ID and then
launches `python -B -m scripts.noetic_application drive ...` as an independent
process. It inherits normal provider environment variables but not
`USER_PROVIDED_PASSWORD`. Its stdout/stderr stay in `RUN/application-driver.log`;
structured requested/running/held/terminal/failed observations and error messages
are retained in `application-driver.json`. These observations never override SQLite.

The child inherits an already-held `application-driver.lock`, closing the queued
launch gap, and the harness holds its own `driver.lock` while executing. Read-only
lock probes distinguish an owned driver from a merely stored `active` kernel.
Ownership does not prove model progress. Server/browser exit does not kill children;
reopening the same runs root observes existing locks and evidence. No startup scan
automatically restarts a driver. Unexpected child failure remains visible; a running
reservation without an owner requires intervention, not GUI relaunch. The GUI does
not attempt even envelope-based recovery of orphaned running reservations; use the
existing harness reconciliation path deliberately if appropriate.

Start and advance are serialized across GUI servers sharing one runs root. Any
active pattern in the same canonical Git workspace prevents another GUI start,
including a held or uncertain run. A conflict names the existing run. Distinct
workspaces can execute concurrently. This is not coordination with unrelated CLI
jobs using another runs directory.

**Pause after current activation** writes the harness's durable `pause.requested`.
The driver checks it before beginning its next ready reservation; it does not
interrupt a currently running actor, verification or result submission. The GUI
distinguishes request from an applied/held checkpoint. **Advance one activation**
and **Advance until held or terminal** explicitly clear the pause through
`harness.resume`, then launch the driver with a one-activation or unbounded count.
Kernel return/remediation budgets remain enforced. Legacy and terminal runs do not
offer these controls. Driver errors are not a reason to fabricate a terminal state.

## Reading Evidence

- The left register lists readable runs newest first. Select a run to inspect its
  goal, last-observed state, workspace, goal reference, and recorded Telos link.
- When `RUN/controller.sqlite3` exists, `noetic_controller.inspect_run` supplies
  authoritative status, pattern, machine state, phase, generation, visits, return
  and remediation budgets, and current actor/activation/ordinal. Neither
  `controller.json` nor an outer `accepted` label overrides this snapshot.
- The controller phase strip retains the persisted phase IDs and roles. Cognitive
  P1/P2/P3/P4 are attentiveness/intelligence/reasonableness/responsibility, not aliases
  for the four development phases. Cognitive `completed` means the pattern
  completed, not generic QA acceptance or Telos completion.
- **Controller evidence** lists every actor in numeric ordinal order with its
  lifecycle, session reference, generation and visit. Select an activation to inspect
  its bindings, criteria, lifecycle events and retained files. A session reference
  absent from the kernel is labeled not committed, not inferred from a log.
- Typed artifacts display actual JSON content plus producer, activation, digest,
  input bindings and derivation. Their labels distinguish current `accepted.*` and
  `effective.*` slots, current subject/feedback, external inputs, and historical or
  partial work. Returns preserve old content while invalidating effective slots.
- Actual kernel transitions and events appear as an ordered list with event IDs,
  kernel versions, from/to states, trigger, guard, action, and return/slot data.
  This is the committed history, not a diagram of possible pattern transitions.
- For legacy runs without a kernel, work, verification, and review outcomes come from journal projection, not from
  timers or inferred progress. `unfinished` does not mean a process is still alive.
  An `accepted` legacy label means a review was recorded, not approval by the view.
- The event timeline shows actual sequence numbers, timestamps, kinds, outcomes,
  and expandable JSON event data. Nested `controller.event` records show the inner
  transition or lifecycle meaning, rather than repeating a generic wrapper label.
  Outer events and reports remain evidence, not replacements for kernel authority.
- Reports include the worker report, reviewer report, task, and the review
  evidence retained in `review.recorded`. The retained review can remain available
  when `review.md` has disappeared or changed.
- Reports also select `changes.diff` and `changes.json`: changes observed during
  a development run, not proof of worker authorship. Read the manifest for hashes,
  omitted binary/oversized content, and unavailable-baseline notices. Unavailable
  evidence is not a no-change result; older runs may have neither artifact.
- Command logs offer work, verify, and review stdout/stderr. Missing, empty,
  unreadable, and truncated files are distinguished. Reports and logs are displayed
  as text, including HTML-looking content; Markdown/HTML is not executed or rendered.
- The register and selected detail refresh about every five seconds without changing
  the run, evidence view, actor, artifact or retained-file selections. Expanded
  event data remains open across updates. Manual refresh is also available. Fetch errors are
   visible; previously fetched evidence stays labeled with its fetch timestamp, except
   authentication failure locks and removes all private displayed evidence. A
  selected run that disappears is not silently replaced by another run. A failed
  detail refresh disables execution controls until fresh authority is available.
- Search is literal lexical retrieval over goals, `work.md`, `review.md`, and
  retained review evidence, using the existing memory component. All whitespace-
  separated terms must match. Results include the source path and event sequence
  where applicable; selecting a hit opens that run and its corresponding evidence
  view. Search results are labeled search-time snapshots; submit again to refresh.
  Lexical search is unchanged, including its journal-derived state labels. Open
  the selected run for current kernel state.

## Memory And Services

The Memory view uses unchanged `/api/search` for lexical retrieval. Semantic search
is a separate explicit POST using `LocalClient(load_settings())`,
`noetic_semantic.index_runs` and `search`, with a persistent derived
`RUNS_DIR/.semantic.sqlite3` cache and a local request lock. There is no polling
inference or lexical fallback. Source/model identity changes fail explicitly;
**Explicitly rebuild semantic vectors** authorizes reindexing. Results display
source ID, artifact ID, state, byte offsets and similarity as relevance, not truth.

**Summarize selected run** calls `noetic_local.summarize_run`, optionally saving
`summary.json` and its observation receipt. The result shows non-authority, model,
coverage/omissions and unverified citation status. It cannot advance the kernel.
Unavailable models/credentials produce visible errors, not empty success.

Models and services displays configured profiles, role defaults and local settings
without credential values. Explicit health refresh only reads Qwen
`:8742/health`, Ollama `:11434/api/ps`, and LiteLLM `:3333/health/liveliness`.
Results are cached in the HTTP process and timestamped. No authentication probe,
model inference or service discovery fills a dropdown.

## Cancellation

Only an active kernel displays **Cancel pattern**. The confirmation names the run
and explains that requesting a stop does not accept or complete its work. A request
can return while the driver still owns execution: the UI then says **cancellation
requested; kernel still active**. Only a subsequently observed terminal kernel
state is shown as terminal. Kernel status alone is never used as proof of process
ownership or progress. If the request response fails, refresh authority rather than assuming it
did or did not take effect. Terminal and legacy runs cannot be cancelled here.

## Python And HTTP API

`create_server(runs_dir: Path | str, host: str = "127.0.0.1", port: int = 8765,
*, telos_db: Path | None = None, telos_source: Path | None = None, access_token: str | None = None)
-> ThreadingHTTPServer` creates but does not start the server. Tests can use
`port=0`, start `serve_forever()` on a thread, then call `shutdown()` and
`server_close()`. `main(argv: list[str] | None = None) -> int` provides the CLI.
Without an explicit `access_token`, the library generates an ephemeral in-memory
token without writing a token file. Trusted callers use `server.token` and
`server.pairing_url`; neither property is exposed by HTTP.

Successful API responses include `observed_at` (UTC; cached health retains its
original observation time, or null before the first check). GET and HEAD are
read-only. All API methods require `Authorization: Bearer TOKEN` before dispatch,
including HEAD and unknown routes. Missing/wrong tokens return generic 401.
Responses use `Cache-Control: no-store`. All actions require JSON and a
same-origin request when `Origin` is present. JSON bodies are bounded to 64 KiB,
except cancellation's 1 KiB bound. All unlisted POSTs and all PUT/PATCH/DELETEs
remain 405 after authentication, including POST `/api/runs`.

| Endpoint | Response |
| --- | --- |
| `GET /api/runs` | `{runs, warnings, runs_dir, observed_at}`. Summaries contain `run_id`, `goal`, `state`, `directory`, `last_event_at`, `goal_ref`, and `telos`, plus the authoritative kernel summary fields below when present. |
| `GET /api/runs/ID` | `{status, controller, controller_path, cancel_requested, events, artifacts, journal_path, artifact_limit_bytes, observed_at}`. `controller` is the unmodified `inspect_run` state or `null` for legacy runs. `events` remain ordered outer journal records. |
| `GET /api/runs/ID/reuse-setup` | Read-only `{source_run_id, source_telos_chain, fields, warnings, observed_at}` for an editable new draft. Unsupported/unrepresentable setup returns 422 with a reason and no partial fields. POST is not supported. |
| `GET /api/runs/ID/activations/ACT/logs/NAME` | One bounded retained file: `{run_id, activation_id, name, source_path, text, truncated, artifact_limit_bytes, observed_at}`. `ACT` must exist in the kernel. |
| `GET /api/runs/ID/activations/ACT/transcript` | Normalized `entries`, `observed_models`, `observed_sessions`, `unparsed_lines`, configured client/model information, and raw `text`/`byte_start` for the trailing bounded actor-log window. |
| `GET /api/runs/ID/sessions/work/transcript` and `/sessions/review/transcript` | Authenticated read-only normalized legacy worker/reviewer output, with a bounded trailing raw window. Client comes from retained role metadata or `program.started`; the role model comes from its recorded command when available. No process or driver is attached. |
| `GET /api/search?q=WORDS&limit=20` | `{query, matches, indexed_entries, limit, observed_at}`. `limit` is clamped to 1-100. Matches use the existing memory shape: `run_id`, `goal`, `state`, `field`, `source`, `source_path`, `event_sequence`, `snippet`. |
| `GET /api/configuration` | Configured profiles, role defaults, launch limits, local settings, purpose DB and driver lifetime. No model or health call. |
| `GET /api/diagnostics` | Cached health only; never initiates a health or inference request. |
| `GET /api/goals` and `/api/goals/ID` | Native Telos aggregates from a read-only source snapshot. No original DB creation or migration. |
| `POST /api/application/start` | New-run fields below; creates a held kernel then a detached driver. HTTP 202 returns `run_id`, initial `controller`, `status: requested`, `message`, and child `pid`. Creation/launch failures retain a run ID when one was created. |
| `POST /api/runs/ID/advance` | `{"mode":"one"}` or `{"mode":"all"}`. HTTP 202 requests background advance; owned, uncertain or terminal runs return 409. |
| `POST /api/runs/ID/pause` | `{}`. HTTP 202 requests a durable after-current checkpoint; subsequent detail reports whether it applied. |
| `POST /api/runs/ID/cancel` | Requires `Content-Type: application/json`, body `{"confirm":true}` (at most 1024 bytes), and same-origin when a browser `Origin` header is present. Calls `noetic_harness.cancel`; returns `{run_id, cancel_requested, controller, message, observed_at}`. HTTP 202 means the returned kernel is still active; HTTP 200 means the returned kernel is terminal, not necessarily cancelled if another terminal transition won the race. |
| `POST /api/goals` | `{"goal":"..."}` deliberately creates a real native Telos purpose, HTTP 201. |
| `POST /api/memory/semantic` | `{"query":"...","limit":20,"reindex":false}`. Explicit indexing/search; returns `index`, `results`, cache path and non-authority notice. Identity mismatch requires explicit reindex. |
| `POST /api/runs/ID/summary` | `{"save":false}` calls the local supporting summarizer. Returns native summary/coverage data, never a verdict. |
| `POST /api/diagnostics/refresh` | `{}` reads only the three known health endpoints and replaces the cached observation. |

Start accepts `pattern`, `task`, `workspace`, `sources` (string references), `verify`
(JSON argv array or null), `client`, `model`, `qa_model`, `thinking`, `timeout`,
`max_returns`, `max_remediations` and optional `telos_chain`. GUI budgets range from
0 to 20; per-command timeout from 1 to 7200 seconds. The harness receives sources
as `inputs.sources: [{ref: ...}]`. Pattern/client and verification are validated
before creation. The application prepares the selected project and owns its development task worktree.

Kernel-backed summaries and detail `status` add `state_source: "controller.sqlite3"`,
`controller_version`, `pattern` (name), `pattern_kind`, `machine_state`,
`current_phase`, `generation`, `visit`, `returns_used`, `max_returns`,
`max_remediations`, `current_activation`, `current_actor`, and `current_ordinal`.
`state` is the kernel status. Detail `status.journal_state` retains the outer label.
Other journal fields, including raw review evidence, are preserved. Without SQLite,
`status` remains the original runtime projection, even if a JSON export exists.
The phase at termination is the kernel's terminal position, not ongoing activity.
The full `controller` object carries all actors, activations, typed artifacts,
slots, feedback, visits, pattern and ordered events. See `executive-controller.md`.

Summaries additionally carry `workspace`, `population` and linked `attention` items.
Both summary and detail contain `application`: driver activity/reason, configuration,
lock observations, pause requested/applied, `can_advance`, and retained driver
metadata. None of these runtime observations rewrite the controller object.

Each lexical search calls `noetic_memory.index_runs` on a new in-memory SQLite connection,
then `noetic_memory.search`; the connection is closed after the request. Out-of-root
sources are removed from that disposable index before matching. No on-disk memory
index, journal entry, or other authoritative history is created or updated.

Run IDs must be one path segment and resolve inside the selected root. The run's
journal, kernel and exposed artifacts must resolve inside that run directory. There is no
arbitrary file-download endpoint or directory listing. Only these artifact names
are read for detail responses:

```text
task.md  work.md  review.md
changes.diff      changes.json
work.stdout.log    work.stderr.log
verify.stdout.log  verify.stderr.log
review.stdout.log  review.stderr.log
```

An available artifact is `{source_path, text, truncated}`; an unreadable/disallowed
artifact is `{error}`; missing artifacts are omitted. Each file is limited to its
first 262144 bytes, labeled when truncated. Invalid UTF-8 is replaced for display.
The journal's retained review and event JSON remain available independently.

Actor files are requested individually, not all loaded into detail responses.
Only these fixed names beneath `RUN/activations/ACT/` are available; the resolved
activation directory must stay inside its run and each file inside that directory:

```text
actor.stdout.log   actor.stderr.log
verify.stdout.log  verify.stderr.log
prompt.txt        model-result.json  submission.json
changes.json      changes.diff
```

The same 262144-byte bound and UTF-8 replacement apply. Missing actor files or
unknown activations return 404; unlisted filenames return 400. There is no path
parameter accepting arbitrary logs, sessions or workspace files.
Structured transcripts use the latest complete-line window within that byte bound;
the ordinary raw file endpoint still returns the prefix. Unrecognized and partial
lines remain in the raw window. Model/provider labels are never invented to fill
missing transcript fields.

Errors return JSON `{error}`: malformed IDs/limits 400, path escapes 403, missing
runs/routes 404, unavailable/conflicting run actions 409, non-JSON actions 415,
malformed/unreadable run details or action/local-service failures 422, and other source/index
failures 500. Corrupt runs are omitted from the register with warnings rather than
hiding readable runs. A present but corrupt kernel never falls back to a JSON export
or the outer label. Search inherits the memory component's skip-and-log behavior
for corrupt runs.

## Checks And Limits

```bash
python3 -B -m unittest tests.programs.test_noetic_web tests.programs.test_controller_view -v
python3 -B -m unittest tests.programs.test_application_gui tests.programs.test_noetic_harness tests.programs.test_harness_integration -v
node --check scripts/web/app.js
node tests/programs/reuse_setup.cjs # Requires Playwright available to Node; fresh headless Chromium
```

These implementation tests use temporary SQLite journals, local test-authored
work/verify commands, labeled report/review fixtures, and actual loopback HTTP
requests. They cover assets, list/detail projection, refreshed lexical retrieval
and attribution, missing/corrupt data, path containment, bounded logs, and unchanged
source bytes/mtimes/file inventory (including an existing disk index). No live
models or Telos services are used. Telos links in tests are explicit fixtures, not
claims of live integration.

`test_controller_view.py` uses actual temporary SQLite kernels, fixture submissions
covering a ten-actor development remediation and six-actor cognitive return,
loopback HTTP requests, and the actual cancellation helper without running any
models or driver processes. It checks stale-export/outer-label precedence, current
state refresh, typed content and bindings, actor ordinals/session references,
bounded contained logs, legacy/missing/corrupt sources, declined/rejected requests,
completed-run cancellation rejection, and request-versus-terminal semantics under
a temporary driver lock. Source bytes, mtimes and inventory are compared across
reads. With Node installed, an executable DOM adapter checks rendering, nested
transition labels, confirmation wiring and preserved selections; it is not a
browser trial or accessibility audit.

`test_application_gui.py` runs actual detached Python drivers and temporary Git
workspaces with a test-only `invoke_actor` substitution. It exercises full launch,
one/all advance, after-current pause, same-workspace conflicts, concurrent different
workspaces, reconnect after HTTP shutdown, cancellation, start/background errors,
orphaned running reservations, Pi/OpenCode transcript normalization and legacy
unsupported actions. Actual Telos core tests use a temporary database; embedding,
summary and health tests use a mock local HTTP server. They check cache reuse,
identity mismatch/reindex, non-authoritative summary coverage, no background
inference, source preservation and the mobile/DOM contracts. No real models are
called, no real histories are changed, and no donor APM is launched.

The kernel state itself is one committed SQLite snapshot. This is not a cross-file
snapshot: concurrent kernel, journal, cancellation marker and report writes can
be observed at different instants. Kernel event versions do not have timestamps;
outer journal timestamps indicate export/observation time. Register refresh reads
journals and kernels; detail includes full event history and typed artifact content
plus bounded legacy files; search rebuilds the complete lexical index each time.
It is intended for local run collections, not large-scale paginated history. Search
does not index command logs or change artifacts. Truncated report suffixes may therefore match search
without appearing in the bounded report preview; the attributed local file remains
the full source. Polling and command exit status cannot establish semantic success.

The focused `test_reuse_setup_*` application checks exercise authenticated mapping,
read-only inventory/byte/mtime preservation, unsupported histories, normal new UUID
creation, initially unbound sessions, test-authored fresh session identities and
unchanged origin history. `reuse_setup.cjs` runs production assets/HTTP in fresh
Chromium with temporary model-free harness histories and labeled Telos fixtures.
It checks confirmation, focus, exact fields, source preservation, delayed config and
purpose reads, rapid selection, in-flight edits, reload, mobile visibility and
lock/logout privacy. Its only start POST is intercepted and labeled; real background
launch/guard behavior is covered by the Python fixtures, not by a live provider trial.

Independent QA, the live-model GUI trial, donor capability comparison and CLI/
packaging wiring belong to the lead. Implementation self-captures are not an
independent QA result. There is no PTY/chat clone, global model configuration
editor, arbitrary goal editing/deletion, or large-history pagination in this unit.
