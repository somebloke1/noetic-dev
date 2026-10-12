# Use noetic-dev

Noetic provides continuing developer agents for your projects. Open your configured
application with `noetic open` and pair through the owner's private access URL.
The application address, model selections and provider access belong to your
installation. See [operator access](operator-access.md).

## Create or open a project

1. In **Workspaces**, choose **New effort**. An effort records what you are working
   toward and the project environment that supports it.
2. For an existing project, enter **Effort intention** and its absolute **Project
   folder**, then choose **Create effort**. This registers the effort without
   starting a model. Select **Start conversation** to describe the first task;
   opening prepares the repository while preserving existing files.
3. For a new project, choose **Create project and conversation**. In **Project
   choice**, use **Create a new project** with an absent or empty folder. Enter
   the project/task name, folder and first instruction, review **Model & project
   location**, then choose **Create project and start**. The same composer offers
   **Open existing project** and **Open project and start** for an existing folder.
4. Read the conversation and actual tool progress in **Agentics**. Send a prompt
   to the selected context, steer active work or queue a follow-up. The agent can
   discover and run relevant checks; conversational work needs no prewritten JSON
   check command. No manually created worktree is required.

Different intentions can share a folder while retaining separate efforts. The
selected client needs its normal provider configuration; configured model
availability does not establish actual access. Noetic does not edit credential
stores or start model services. Explicit custom model choices are preserved.

## Reviewed Opermem inquiry

Select an existing effort, open **Entrust work**, and choose **Reviewed Opermem
inquiry**. Explicitly register or select that effort's backing directory. Describe
the question and select bounded absolute source files. **Question** is the initial
GUI operation; the operation capacity descriptors explain their
prerequisites and unavailable input editors. Optional purpose and independent
review model choices remain in task settings.

Start returns a retained asynchronous launch command. Its original preparation
and execution appear when observed. Inspect the actual worker/reviewer ordinals
and exact contexts, useful report, external review, native contribution/receipt,
and separate Telos result. **Details & evidence** retains the original preparation,
whole native packets at their cut, ordered events, and source fingerprints.
Offered recovery restores retained contribution or original correspondence without
relaunching actors. Reviewed Pause, Stop, Apply, and conversational continuation
are unavailable; development Apply remains in the development workflow.

**Typed memory** discloses retained native packets and receipts for the selected
scope. Their original standing and provenance remain historical; current native
eligibility is unobserved. **Source recall** can select qualified source identity
and digest for an editable inquiry draft. Launch revalidates those selections.
**Reuse setup** clears backing and purpose authority; select current bindings
explicitly before launching another inquiry.

## Positions, sessions and continuing work

`0` is the dormant logical application root, with no native model occupant.
Effort roots are persistent absolute ordinals such as `0.0`, `0.1` and `0.2`;
children of `0.0` begin `0.0.0`, `0.0.1`. These identify enduring responsibilities,
not conversations. Human assignment and genuine agent delegation remain distinct.

Select an effort in **Workspaces**, then use **Agentics** to inspect its **Tree**,
**Sessions** and **Returns**. A position retains its mandate, environment and
current occupant. Choose a session row to select its exact **instantiation** and
**session**. **Context** opens **Context & session evidence**, including retained
records and **Responsibility handoff**. **Start successor with handoff** requires
both the responsibility entrusted and context/first instruction; it changes the
occupant while preserving the ordinal and predecessor record. Starting another
conversation at a position creates a fresh native context without creating a new
effort or declaring succession.

**Delegate agent responsibility** starts a genuine child from the selected current
agent with a bounded task. **Stop work** clears queued work before abort.
**Close agent** shuts down its process; **Reopen agent** explicitly resumes the
selected retained context. Reconnection retains sessions, while process loss
requires explicit reopening. Instructions bound to an exact recipient never
redirect to a successor; an unavailable or superseded target reports failure.
Closing a session does not close its effort.

For application-wide inspection, use **Agentics → Sessions** with **Portfolio
topology**, clear the position search and any project filter. Original unadopted
sessions remain inspectable by their native identities; they are not silently
assigned to an effort. **Recent activity → Open global ordinal history** traverses
the global records. See [effort scope](effort-scope.md) and
[developer sessions](developer-sessions.md) for the canonical relationships.

## Structured work, purpose and recall

From a selected effort, **Entrust work** opens **Start structured work**.
**Disciplines** describes the maintained cognitive/development programs and their
recorded instances; **Executions** controls a particular recorded use. A scoped
start creates a discipline instance with explicit human origin. For development,
the controller prepares a task worktree from the declared project. Cognition
remains read-only in the declared project workspace. Participants retain genuine
ordinal positions and exact contexts within that effort.

**Purpose & limits** opens **Telos purposes**. Owned purpose links retain the
complete owner/store/chain reference. They and local supporting services are
optional; ordinary project conversations require no manual Telos database setup.
**Typed memory** distinguishes native semantic authority from supporting source
recall. Recall can select an effort, position or exact native context; relevance
and coverage remain inspectable and do not establish verified conclusions.

On record and library pages, **Operation scope → Application · all efforts and
original histories** deliberately exposes application-wide and unassigned
component evidence. Select an effort for structured starts, owned purposes and
scoped recall. Inspecting an old unassigned run does not adopt it or reconstruct
past global delegation. **Artifacts**, **Native agent runtime** (the **Runtime
control** page), **Model registry** (the **Models** page) and **Configuration**
expose retained outputs, observed processes and configured selections.

## Install or run from source

Python 3.10+ is required. The Python runtime has no third-party dependencies.
Use the source entrypoint without installing anything:

```bash
python3 -m scripts.noetic --help
python3 -m scripts.noetic doctor
```

Or install into a chosen virtual environment with `python3 -m pip install .`,
then use `noetic` from any working directory. The package includes the browser
assets, both JSON pattern tables, and the Node bridge. `doctor` reports local
executable/component availability; it does not call models or claim credentials
are working.

## Scoped session CLI

CLI calls use the same scope and exact selectors:

```bash
noetic sessions register-effort --workspace /path/to/project --intent "Build the app"
# Use the ordinal returned by registration; these examples assume it is 0.0.
noetic sessions start --effort-root 0.0 "Implement the first feature"
noetic sessions show 0.0 --effort-root 0.0 --instantiation 1 --session 1
noetic sessions prompt 0.0 --effort-root 0.0 --instantiation 1 --session 1 "Continue"
noetic sessions history 0 --after 0 --limit 100
```

Use each returned `next_after` for the next history page. Starting again at the
same effort/ordinal creates another conversation; it does not register another
effort. Exact historical instructions fail if their target is superseded rather
than redirecting to a successor. See [developer sessions](developer-sessions.md).

## Advanced component CLI

The harness examples below omit application effort correspondence. They operate
as deliberately unassigned component runs with their own run directories and,
where supplied, bare Telos chain links. They do not register an application effort
or acquire owned purpose references. Use **Entrust work** in a selected effort for
application-scoped execution. Inspect unassigned records through Application
operation scope. These CLI examples execute in the supplied `--workspace`; choose
a checkout where edits are intended. Application-scoped development instead uses
the controller-prepared task worktree described above; application-scoped cognition
remains read-only in the declared project workspace.

Model identities in the examples are explicit sample selections. Substitute a
model configured for your chosen client and available to you. `doctor` and the
application's **Models** view inspect configuration, not successful provider access.

### Development Pattern

Use a project checkout where edits are intended. Create `task.md` with a concrete
goal, acceptance criteria, relevant paths, and scope limits. Then:

```bash
noetic harness start development task.md --workspace /path/to/project \
  --client pi --model openai-codex/gpt-6.1-sol --thinking high \
  --qa-model openai-codex/gpt-6.1-sol --max-remediations 1 \
  --verify python3 -m unittest discover -s tests
```

There are exactly four development phases, in this order:

1. **Design intent**: objective, scope, and observable acceptance criteria.
2. **Abstract design**: components, interfaces, and design decision.
3. **Implementation procedure design**: ordered implementation and verification steps.
4. **Implementation**: product edits and actual retained check evidence.

Every phase has an author followed by a fresh phase-specific QA actor. The
ordinary path uses eight actors. A failed review may allocate a fresh remediation
author and fresh QA, up to `--max-remediations` extra pairs **per phase**; budget
exhaustion blocks rather than accepts. Accepted prior artifacts govern later
phases. Planning QA checks planning criteria, not unperformed future implementation.

Omit `--qa-model` to use the same configured model with fresh sessions for both
roles. LiteLLM requires an explicitly configured exact model route. See
[operator profiles](operator-view.md) for configuration.

`--verify` is a shell-free argv and must be the final option. It runs after every
implementation author. Actual command exits, logs, and observed changes replace
model-claimed verification in the QA subject. Even failed checks reach QA as
evidence; the kernel applies its typed verdict and remediation budget. Exit zero
from a model or check alone is never semantic completion.

### Cognitive Pattern

```bash
noetic harness start cognition question.md --workspace /path/to/project \
  --client pi --model openai-codex/gpt-6.1-sol --thinking high \
  --max-returns 1 --max-activations 2
```

P1 **attentiveness** records observations/questions/evidence, P2 **intelligence**
forms hypotheses, P3 **reasonableness** judges grounds and conditions, and P4
**responsibility** decides with rationale and next actions. These are not aliases
for the four development phases, nor headings on one worker's report.

Each operation has a fresh actor and typed input/output bindings. An allowed
return preserves partial work, reason, and question, invalidates affected current
bindings, and revisits an earlier operation. `--max-returns` is a whole-run budget.
Completion is the current P4 boundary, not an invented generic independent QA
review. All cognitive actors are read-only; `--verify` is optional.

### Checkpoint And Inspect

The command prints a durable run directory. `controller.sqlite3` is authority;
`controller.json`, `work.md`, and outer journal events are retained projections.
Each activation retains prompts, transcripts, session identity, result envelope,
and available change/check evidence. A quiet Git workspace is currently required
for read-only actor change checks. Existing dirty files are preserved; changes
observed during a run are not proof of exclusive actor authorship.

```bash
noetic harness inspect /path/to/project/.runtime/runs/RUN_ID --json
noetic harness advance /path/to/project/.runtime/runs/RUN_ID --max-activations 1
noetic harness cancel /path/to/project/.runtime/runs/RUN_ID
```

`--max-activations 0` starts at a ready checkpoint without a model call.
`advance` uses saved options, pattern, governing artifacts, and the kernel's
reservation; it never rereads the task or silently retries uncertain actor effects.
Running activations with a complete saved submission can reconcile without
reexecution; those without it fail explicitly as uncertain. See
[harness runtime](harness-runtime.md) for recovery and cancellation boundaries.

Start/advance exit 0 on completed-and-synchronized, 2 at an active checkpoint,
and 1 on failed/blocked/cancelled or a Telos sync gap. These are controller outcomes,
not claims that all framework goals have been achieved.

### Durable Purpose

Telos integration requires Node 24 and a Telos component. For an independently
deployable component, build once using the existing Telos checkout's esbuild:

```bash
noetic goal bundle --source /path/to/telos --output /path/to/components/telos-core.mjs
```

This bundles the real factory as Node 24/ESM and writes an adjacent
`telos-core.manifest.json` with SHA256 and current-source identity, including
possible uncommitted changes. Deploy the module and manifest separately from the
noetic Python package. At runtime the component needs neither the donor checkout
nor tsx, esbuild, Pi SDK, or OpenCode. Node 24 and the selected database remain.
The harness itself still needs a configured coding-assistant client.

For an unassigned component run, create a project-local goal using the deployed
module and an explicit database:

```bash
noetic goal create "Maintain this project's intended behavior" \
  --db /path/to/project/.runtime/telos.sqlite3 --source /path/to/components/telos-core.mjs
```

Use the returned chain ID on subsequent runs:

```bash
noetic harness start development task.md --workspace /path/to/project \
  --client pi --model openai-codex/gpt-6.1-sol --thinking high \
  --telos-chain CHAIN_ID --telos-source /path/to/components/telos-core.mjs \
  --verify python3 -m unittest discover -s tests
```

The genuine aggregate is fetched before work. Master purpose and principles are
bound as a distinct **`external.governing`** artifact to **every phase**, including
QA, remediation, and returned visits. The bounded task remains unchanged in
`external.purpose` and the run association. `begin_run` links before the first
actor, and the genuine Telos core retains the actual controller result.

Only that run subgoal completes: at all four development QA boundaries or at
responsible cognitive completion, respectively. The master goal never completes
automatically. Active, failed, blocked, and cancelled runs do not close subgoals;
a corrupt controller is an error, never a fallback to legacy acceptance.

The harness defaults its database to the workspace's `.runtime/telos.sqlite3`;
override with `--telos-db`. Options and governing snapshot are frozen for advance.
Alternatively, set `NOETIC_TELOS_SOURCE` to the module path and omit the source
options. `noetic doctor` reports module mode without requiring tsx. The original
source-directory mode remains available with tsx installed in that checkout.
Neither mode migrates or mutates the live client goalchain.

A failed result write is separately visible as `telos.error` and a nonzero harness
exit, even when the controller completed. Retry `noetic goal record CHAIN_ID
SUBGOAL_ID RUN_DIR --db DB --source SOURCE` without reexecuting actors. Repeated
successful recording is idempotent. See [Telos-linked runs](telos-runs.md).

## Observe and retrieve

For the web application, use the private pairing URL printed by `noetic serve`.
Its local operator token is distinct from all model credentials. Plain bookmarks
open a locked shell until paired. See [operator access](operator-access.md) and
[private storage](private-storage.md) before migrating older broad-permission state.

Optional local support is explicit, never an execution gate:

```bash
noetic local diagnose embedding --config config/local-models.json
noetic local summary /path/to/run --config config/local-models.json
noetic semantic search "related work" --runs-dir /path/to/runs --config config/local-models.json
```

Summaries are labeled model-generated and non-authoritative. Semantic scores
indicate relevance, not truth or QA. Both preserve source identity and leave
controller state unchanged. See [local capabilities](local-capabilities.md).

```bash
noetic list --runs-dir /path/to/project/.runtime/runs
noetic status /path/to/project/.runtime/runs/RUN_ID
noetic search "relevant words" --runs-dir /path/to/project/.runtime/runs
noetic serve --runs-dir /path/to/project/.runtime/runs --port 8765
```

For a separately operated source instance, choose an unused port and private
state; `8765` above is an example. Open the address printed by `serve` and pair
privately to inspect outcomes, event timelines, purpose links, reports and command
logs. Search returns snippets with exact source paths.
It is lexical search over actual retained text, not embeddings or invented memory.
The index is disposable and refreshed; journals remain authoritative.

The GUI and CLI use the same harness and authoritative SQLite controller. In
**Executions**, inspect the selected run and request pause after its current
activation, advance one/all, cancel or apply retained project work. Pause does not
interrupt the actor: wait for the held ready successor before advancing. A driver lock is not proof of model progress, and a
configured profile or health response is not proof of authentication or continuing
availability. Consult the [operator view](operator-view.md); inspect state before
starting a replacement run.

## Legacy Utilities

`noetic develop`, `noetic inquire`, and `noetic batch` retain their old task-level
work/review behavior. They are **not the original pattern harness**: a single
report with P1-P4 headings is not recurrent cognitive operations, and a worker
plus final review is not four-phase development. `run`/`review` are also preserved
for explicit command tasks. See [agent workflows](agent-workflows.md),
[bounded task batches](batch-workflows.md), and [command runs](live-runs.md).

## Supported boundaries

- Controlled development trial `07b2162319ee4a1d8ea43497437f4c54` completed four
  phases with ten Pi actors, direct authors/proxy QA, and implementation remediation.
  The trial deliberately overwrote the first implementation after its real edit;
  this proves controlled fault recovery, not a naturally occurring author defect.
  Cognitive trial `690bab0bab384ad69b29f633036960e3` completed six actual OpenCode
  operations P1/P2/P1/P2/P3/P4. Pi 0.85.1 and both access routes also have bounded
  tool-continuation checks. These do not prove every capability or future run.
- Kernel/driver, CLI/Telos/packaging, local support, and application GUI have scoped
  independent acceptance. Integration QA exercised the genuine Telos factory and
  relocated module with temporary databases, including installed-wheel execution.
- Real source-GUI run `41f4a996beeb41f5a736f07f3087178d` completed four development
  phases with eight fresh Pi actors, native Astra authors and proxy QA, without
  remediation. Its project check also passed independently afterward.
- Installed production-GUI run `4cd0d3f4757f4d9e83b37b58a5e95caf` paused while P1
  was actually running, held at the unexecuted P2 successor, then resumed to typed
  P4 completion with four distinct Pi sessions. Separate production GUI operations
  completed real semantic search and a Qwen summary without changing checked
  controller/journal/Telos state. Search reused a warm index; summary coverage was
  bounded and disclosed. Neither proves cold-index latency or semantic truth.
- Parent-session restart is unnecessary: OpenCode agent configuration is scoped
  to newly started child processes. No global client configuration is modified.
- Workers use normal local permissions, not a sandbox. Use ordinary project
  isolation. Reviews are attributed evidence, not authenticated identity proofs.
- Model routing remains the selected client's configured responsibility. This
  release does not implement genus-router selection or local vision/ASR pipelines.
  [Local hosting](local-models.md) is separately checked. CPU-vector retrieval and
  supporting summaries are integrated, but are not an automatic distiller or
  authority-bearing controller input.
- The tool does not commit, push, merge, or deploy automatically.

See [agent workflows](agent-workflows.md), [Telos-linked runs](telos-runs.md),
[live runs](live-runs.md), [session memory](session-memory.md), and the
[operator view](operator-view.md) for detailed interfaces and failure behavior.
