# Application effort, ordinal and discipline scope

The persistent global ordinal namespace is the prior operational environment for
agent identity, genuine delegation authority, accountability, functional
relationships and complete correlated history. Absolute ordinals are primary
user, agent and API addresses. This contract follows the owner's corrections,
the [ordinal backbone amendment](/home/dgk/.local/share/noetic-dev-work/01a12d60-2652-7002-b924-501dca4d6a08/generality-coupling-review/ordinal-backbone-amendment.md),
[development steering intent](/home/dgk/.local/share/noetic-dev-work/01a12d60-2652-7002-b924-501dca4d6a08/generality-coupling-review/development-steering-intent.md)
and [recovery contract](recovery-contract.md).

`scripts/noetic_scope.py` is the first canonical persistent domain unit. It
establishes these relationships through SQLite fields, foreign keys, explicit
mandates and transactionally allocated positions. Conversational/controller
adapters, UI navigation, tools and installed application integration are still
pending. Existing conversation roots and run-local actor labels do not yet
become the global backbone merely because this module exists. Complete product
delivery and human judgment of usefulness remain separate acceptance outcomes.

## Persistent namespace and ownership

| Owner | Owned records and required correspondence |
|---|---|
| Application | One persistent namespace with logical root `0`, many effort branches and first-class global history. Installation configuration belongs to its declared installation scope. |
| Effort | Exactly one stable effort-root ordinal, declared intent, explicit environment revisions, genuine descendants, discipline instances and retained histories. Different intents can share a directory without becoming one effort. |
| Agent position | An absolute ordinal and one actual parent except `0`; explicit owning effort except `0`; durable mandate versions, instantiations, successions and sessions. A discipline-owned position also names its instance. |
| Mandate version | What was entrusted, origin, responsible parent ordinal and parent mandate version, source reference, actual delegating instantiation/session when present, or explicit human-origin reference. Earlier versions remain retained. |
| Instantiation | One ordinal position, sequence selector, received mandate version, exact native agent reference and, on succession, explicit predecessor and context/responsibility handoff. At most one current instantiation per position. |
| Session | One ordinal/instantiation, session selector, exact client-native context reference and independent status. Several retained sessions can belong to one instantiation; only one is designated current. |
| Discipline instance | One already existing effort, actual initiating ordinal, optional exact initiating target, frozen definition identity/version, instance intent/environment and optional parent instance. |
| Discipline participant | A genuine delegation position inside the same effort branch, under a recorded parent descended from the instance initiator. Its position names the owning instance; the discipline view refers to that same position. |
| Execution | A particular use of one discipline instance with an exact native run reference. Reuse, retry and resume need not create a new effort, definition or instance. |
| Activation/result | An execution/instance association and responsible participant's exact ordinal/instantiation/session plus native activation/result/source references. Native status and semantic standing retain their own authority. |
| Action binding | An immutable exact target, native session reference, received mandate version and effective environment snapshot. Later succession or environment changes cannot rewrite the selected target. |
| Historical adoption | Globally qualified source namespace, original ordinal/parent if actually known, original native/source references, adopted global position or exact target and adoption time. Adoption is distinct from historical delegation. |

`0` always means the application root. Effort roots are allocated as `0.0`,
`0.1`, `0.2`; children of `0.0` begin `0.0.0`, `0.0.1`. Allocation is monotonic
for every parent and occurs in the same transaction as mandate and history
writes. Closing a position never deletes, reuses or renumbers it. Replacing an
occupant preserves the position and adds succession records. New responsibility
under different actual parentage requires a new position and an accountable
transfer event; there is no cosmetic reparenting operation.

The namespace persists with application-owned state through reopen, restart,
backup restoration and host replacement. An internal namespace identifier
qualifies independent source namespaces; supporting database record IDs and
native UUIDs do not replace ordinal addressing. Effort-local visual abbreviations
must preserve absolute operational targets. Changing the namespace scheme would
require an explicit migration decision and preserved historical addressing.

The logical root has a persisted human-origin mandate without implying any
running provider or invented past agent call. Human creation/assignment and
executed agent delegation are different origins. Actual agent delegation requires
an exact current delegator at the stated parent position. Its retained mandate
establishes delegative authority and accountability within its stated limits.
Human authority, controller contracts, environment permissions and native
Opermem semantic authority coexist with it. Parentage alone does not affirm a
cognitive judgment or expand operating-system permissions. The module records
mandate content and structural scope; interpreting the substantive adequacy of a
mandate or result remains with the responsible human/native contracts.

## Operational addressing and scope

| Operation | Required address and resolution |
|---|---|
| Create an effort | Explicit intent/environment and a human-origin assignment or actual root-agent delegation. Allocate one enduring effort-root branch. Opening a folder or starting a session does not silently allocate a different effort. |
| Read a position | Absolute ordinal returns responsibility, ownership, mandate and designated current instantiation; it remains meaningful when never instantiated or dormant. |
| Delegate | Absolute parent ordinal, operation scope, explicit mandate/origin and actual exact delegator for agent-origin calls. Allocate a genuine child within the parent's effort. |
| Instantiate/succeed | Absolute ordinal; succession explicitly names the current predecessor and responsibility/context handoff. New native context and resumed native context must be recorded truthfully. |
| Prompt/steer/stop/reopen | Absolute ordinal first, then resolved instantiation and session selectors. Return/preserve the exact target through delivery. Historical selection names both retained selectors explicitly. |
| Queue an action | Persist the resolved exact target and native/context/environment references before runtime delivery. A successor does not receive the predecessor's queued instruction by substitution. |
| Instantiate a discipline | Existing effort-root ordinal, actual initiating ordinal and definition/version. Nested instances name the parent instance and are initiated by an actual participant there. |
| Correlate execution/activation | Instance/run plus genuine participant exact target; ownership, parentage, instance and source references must agree. Preserve native execution and cognitive contracts. |
| Read application history | Traverse from `0` without requiring project selection. All A/B/R branches and retained events, instantiations and sessions remain reachable, including failures, closure, supersession and adoption. |
| Read effort/agent/discipline/session history | Traverse the same global records through a branch or typed instance relation. Exact instantiation/session filters apply to one ordinal, excluding coincidentally equal selectors at descendants. |
| Coordinate across efforts | Explicit application operation under a retained root mandate version, naming intended effort roots and separate resolved environments. Record each instruction and its coordinating event. A live root runtime is required only for a claimed agent-origin operation. |
| Record/use artifacts or capabilities | Responsible ordinal, exact instantiation/session where applicable, definition/use/result and source references. Reuse preserves native provenance, standing and conditions. |
| Develop/recover Noetic | External development authority, tools and records operate independently of product root `0`, product sessions, histories and semantic transitions. |

An effort-scoped operation targeting another effort's ordinal is a mismatch and
is rejected. `Scope.effort("0.0")` cannot resolve or allocate in `0.1`.
`Scope.application(("0.0", "0.1"), root_mandate_version=1)` deliberately names
both effort environments under the recorded root mandate; `0.2` is still outside
that operation. Root mandate version changes require renewed explicit scope.
These checks resolve membership and intended routing; they do not introduce an
organizational security system or owner approval ceremony.

A bare ordinal requests its enduring position/history or expressly designated
current runtime. It never selects an arbitrary historical session. Exact targets
are structured `Target(ordinal, instantiation, session)` records. There is no
settled suffix grammar. `resolve` requires a current open runtime when selectors
are omitted; both explicit selectors can resolve a closed, failed or superseded
historical session. `bind_action` stores the exact selected target; `action`
retrieves it unchanged. A future delivery adapter must use that binding, report
stale/unavailable delivery honestly and never silently re-resolve to a successor.

## Domain API for the next integration unit

Storage is an explicitly supplied application-owned SQLite path. The module has
no recovery-checkout, semantic-store, cwd, provider or service default. It uses
existing private-storage helpers for missing directory/database creation. Each
public operation opens its own connection; `BEGIN IMMEDIATE` serializes writers
and allocation plus all corresponding records commit or roll back together.
Read traversals use a transaction snapshot. Existing stores are not migrated by
construction.

```python
from pathlib import Path
from scripts.noetic_scope import Scope, ScopeStore

source = {"journal": "owner-directions", "event": "create-application"}
human = {"owner": "actual-owner-reference"}
store = ScopeStore(
    Path("/explicit/application-state/ordinals.sqlite3"),
    root_mandate={"purpose": "Coordinate the owner's declared efforts"},
    human_ref=human,
    source_ref=source,
)
a = store.create_effort(
    intent="Investigate A", environment={"cwd": "/explicit/effort-a"},
    mandate={"purpose": "Pursue A in its declared environment"},
    origin="human", human_ref=human, source_ref=source,
)
scope = Scope.effort(a["ordinal"])
instance = store.instantiate(
    a["ordinal"], scope=scope,
    native_ref={"client": "actual-client", "agent_id": "actual-agent-id"},
    source_ref=source,
)
target = store.open_session(
    a["ordinal"], instance["sequence"], scope=scope,
    native_ref={"client": "actual-client", "session_id": "actual-native-session",
                "context_file": "/explicit/native-context"},
    source_ref=source,
)
child = store.delegate(
    a["ordinal"], scope=scope, mandate={"purpose": "Research A"},
    origin="agent", delegator=target, source_ref=source,
)
```

The example's native references must come from the actual selected client;
registering them does not launch or verify a process. Reopen the same application
namespace with `ScopeStore(the_same_explicit_path)`; first creation requires the
human root mandate/source and creates no root runtime.

| API group | Public methods and retained fields |
|---|---|
| Position/effort/mandate | `create_effort`, `position`, `delegate`, `revise_mandate`, `mandates`, `close_position`; public effort identity is its root ordinal. |
| Environment | `set_environment`, `environments`; revisions remain retained and queued bindings preserve their selected snapshot. |
| Instantiation/session | `instantiate`, `instantiations`, `open_session`, `sessions`, `set_session_status`, `resolve`; exact native references remain separate from ordinal selectors. |
| Action/coordination | `bind_action`, `action`, `coordinate`; bindings do not imply delivered/completed work, and coordination records separately named environments. |
| Discipline/use | `create_discipline`, `discipline`, `create_execution`, `record_activation`; returned instance/execution record IDs identify uses, while all agents retain ordinal addresses. |
| History/traversal | `record_event`, `history`, `branch`; append-only event/source references and allocation order remain inspectable. |
| Legacy correspondence | `register_legacy_namespace`, `legacy_namespace`, `adopt_legacy`, `legacy_mappings`; originals, missing parentage and adoption time remain explicit. |

`history` and `branch` return `records` and `next_after`. Continue with the
returned cursor until an empty page; the cursor is a monotonic history sequence
or allocation sequence, not a timestamp or ordinal lexical order. Filters apply
before pagination. Instantiation/session lists retain all records in sequence
order. `legacy_mappings` uses its returned record `id` as the next `after` cursor.
Scoped read methods reject foreign ownership; unscoped read traversals are
explicit application-wide inspection. Runtime transcripts need not be copied
into this database: durable native journal/event/context references are retained,
and missing historical detail must be disclosed by its adapter.

Status belongs to its subject. A session may be failed while its effort remains
continuing; a superseded instantiation remains historical. Closing a domain
position is a recorded lifecycle change and does not itself stop a process.
Actual process ownership, reopen/stop delivery, controller state transitions and
native semantic operations remain adapter responsibilities in the next unit.

## Existing history and adoption

The current conversational registry allocates fresh UUID/root-local `0` for each
conversation; the controller uses independent run-local `0.N` actor labels.
Those are source namespaces with real native records. Two old roots both named
`0`, including roots with the same cwd, remain distinct historical identities.

Register each actual source namespace with its native store reference. Adoption
then names its original ordinal, original parent only if recorded, original
session/actor/context/event references, destination absolute ordinal or exact
target and current adoption time. The mapping records `historical_delegation:
false`; current adoption does not claim that today's global root performed a
past delegation. Allocate current responsibilities with their genuine current
mandates separately. Legacy missing/ambiguous ancestry remains missing/ambiguous.
No real-history migration, source rewriting or automatic replay is part of this
first unit; tests exercise disposable fixtures only.

## Independent development and native functional contracts

Noetic development, recovery and every development sub-effort use independently
operable external coordination, source control, tests, packaging and repair
records. Product experiments can provide evidence without becoming an authority
or a prerequisite for repairing the application. A recovery effort represented
as R inside the product is distinct from the external coordinator developing
Noetic. No host path, model, port, service or recovery purpose becomes a universal
consumer assumption.

The namespace makes functional relationships addressable and accountable.
Definition/version describes available capacity; instance/execution describes a
particular use; activation and result references describe actual operation and
retained effects. These remain distinct relations inside the same environment.
Ordinal depth expresses lineage; it does not quantify productive capacity or
native semantic standing. P1–P4 remains cognitive form alongside SAEProj, while
Opermem's fourteen typed operations and semantic authority remain independent.
A controller receipt or recorded result does not promote Opermem standing.
Human judgment of cognitive adequacy and useful retained/reused understanding
continues to govern the synthesis.

## Bounded acceptance and delivery order

Disposable tests for this first canonical unit exercise unrelated efforts A/B
and separately represented R, monotonic persistence and real concurrent callers,
forced transaction rollback, human assignment versus actual delegation, several
sessions and succession at one position, frozen exact queued targets, two
cognitive discipline instances and one nested development instance, correlated
native activation/result references, complete paginated global/branch histories,
foreign-scope rejection and qualified adoption of two old roots `0` plus a
run-local actor label. These domain checks establish no running provider, real
history migration or complete UI delivery.

The next unit associates current conversational and discipline actors through
this allocator/resolver while preserving original namespaces and accepted native
controller behavior. Then ordinal-first targeting and exact historical
selection must agree across UI, APIs, agent tools, action delivery, history,
recall, purposes and result application. Installed application state/configuration
and independent external development must remain explicit and independently
operable throughout. The final A/B/R product trial must demonstrate those actual
interfaces and meaningful work across sessions; a passing module test is not
that product trial. Each bounded material implementation receives exactly one
independent, constructive, proportionate QA pass under project governance.

Structured runs that select an owned purpose retain its complete reference
(`owner` namespace/kind/ordinal, `store_id`, `db_path`, `chain_id`, `source`) and
the explicitly configured purpose resolver (namespace path, purposes root,
legacy path and native source). The application resolves this selection before
task-worktree preparation. The harness validates it before execution binding or
actors, freezes it in run options and canonical execution options, and includes
the reference in the frozen governing input and native association journal.
Custom purpose roots and native sources remain explicit; cwd and bare chain IDs
cannot supply ownership or resolver configuration.

Resume, continued execution and purpose synchronization revalidate the retained
canonical assignment, reference/configuration and actual configured owner,
store/source and chain through read-only purpose resolution. Changed native goal
content does not rewrite frozen governing inputs. A refusal preserves native
records, controller artifacts, receipts and retained task work; restoring the
declared configuration permits legitimate continuation. Controller completion,
Telos subgoal synchronization and native cognitive standing remain distinct.

No-purpose scoped runs remain usable. Unassigned historical runs retain their
explicit bare-chain Telos behavior without acquiring owned references. An older
scoped run whose purpose binding is unavailable remains inspectable and
cancellable, with cleanup and retained work preserved; continued purpose work
requires a fresh run with an explicit complete binding. This does not classify
its historical evidence as foreign or corrupt, adopt it retrospectively, or
create a new purpose implicitly.

Confidence is high in ordinal-first identity, accountable delegation and global
history; concrete adapter evidence will refine delivery details while preserving
these invariants. The chosen global `0` namespace is the canonical implementation
for this unit. A future alternative needs a substantive migration decision, not
a presentation preference.
