# Opermem-enabled development and inquiry

The runner supplies current whole Opermem context to a real Synthesis worker and
its separate reviewer. It submits the worker's explicit contribution through the
existing Rust operation host after review. Questions, unverified insight traces,
formulation hypotheses, reflection questions, conditional warrants, and their
unchecked conditions retain their native standing. Synthesis performs
repository actions and records reviews; the human owner judges cognitive value.

Use an existing configured Pi or OpenCode model and the rebuilt Opermem binaries.
The operation host requires a private store and fresh private transcripts. The
runner creates new directories with mode 0700; an existing public directory is
rejected. The current Rust host uses fixed bootstrap experience and workspace
identities. They are local markers, not registered repository sources.

Host exchange evidence capture: for each host session the bridge creates a
fresh private sibling `<transcript-name>-bridge` directory next to the native
transcript directory, created exclusively. Bridge captures leave the native
transcript directory empty for its startup validation; the native host then
writes its own transcript. Every exchange retains its exact outgoing canonical request
plus terminating LF as `NNNN-request.raw`, and the raw response bytes actually
read — including a first overshoot chunk, an empty file for EOF, or a malformed
but observed body — as `NNNN-response.raw`, numbered by exchange sequence.
`stderr.raw` holds the host's exact stderr bytes (streamed to disk, so nothing
is lost to pipe backpressure even when an exchange has raised);
`remaining-stdout.raw` retains any trailing unframed stdout bytes after exit
when present; `process.json` records the true returncode and
`shutdown_timed_out`. An exchange can end in distinguishable ways: success
(parsed and correlation/class gated exactly as before), native refusal (a
well-formed envelope the gate rejects, whose exact body determines its standing),
`response-eof` (stdout closed without a complete response),
`response-oversized` (observed bytes exceeded the 524288-byte bound; the capture
includes the first overshoot chunk, at most 65536 bytes, and may omit later bytes),
and `response-json-invalid` (bytes ended with LF but did
not decode). EOF, oversize and decode failures raise RuntimeError with the
outcome label, the process exit status when known, bounded human stderr and the
absolute capture path, chained to the underlying decode error where one exists.
The capture directory is the retrieval location; no native admission, response
normalization or effect inference is derived from it. In particular, exit 65 with
`invalid-request` on stderr and no response is an observed process/input refusal;
it is not a native semantic refusal receipt or proof of zero effects.

```sh
noetic opermem --host /path/to/opermem-operation-host \
  --store /private/opermem-store --runs-dir /private/runs \
  run task.md --workspace /path/to/project \
  --operation insight --parent-id QUESTION_ID \
  --client pi --model openai-codex/gpt-6.1-sol \
  --verify python3 -m unittest tests.relevant
```

`--verify` is last because remaining arguments form the verification command.
For a read-only task, use `--inquiry`; an explicit verification command is optional. For question,
insight, formulation, and reflection, the final worker report must contain one
`OPERMEM_CONTRIBUTION_JSON: {"text":"..."}` line;
questions additionally require `question_kind`. The actor's claim and review
verdict do not promote an insight or formulation into an Opermem judgment.

Operations 4 and 5 use the same reviewed task boundary. Reflection takes a
formulation parent; conditional structure takes a reflection parent and its
formulation as a second explicit anchor:

```sh
noetic opermem --host /path/to/opermem-operation-host \
  --store /private/opermem-store --runs-dir /private/runs \
  run reflection-task.md --workspace /path/to/project \
  --operation reflection --parent-id FORMULATION_ID \
  --client pi --model openai-codex/gpt-6.1-sol --thinking high --inquiry

noetic opermem --host /path/to/opermem-operation-host \
  --store /private/opermem-store --runs-dir /private/runs \
  run warrant-task.md --workspace /path/to/project \
  --operation conditional-structure --parent-id REFLECTION_ID \
  --formulation-id FORMULATION_ID \
  --client pi --model openai-codex/gpt-6.1-sol --thinking high --inquiry
```

The `context` command accepts the same operation and anchor flags. Rust checks
that the reflection belongs to the supplied formulation. Both current native
object versions enter the conditional command; Synthesis does not invent them.
Reflection deposits `{"text":"Is this formulation correct?"}`. Conditional
structure instead requires one report line such as:

```text
OPERMEM_CONTRIBUTION_JSON: {"conditions":["A: inspect the current native anchors","B: compare the replay receipt and residue IDs"]}
```

Conditions must be a nonempty, strictly sorted, duplicate-free array of trimmed
nonempty strings. The adapter retains the actor's exact values and rejects
invalid order or whitespace. A warrant makes conditions addressable; they remain
unchecked. No checking, affirmation, or judgment is performed by operations 4–5.

## Explicit owned reviewed runs

For an assigned run, select an existing canonical effort and compatible reviewed
instance and its explicitly registered native store. Purpose binding is optional;
when selected, retain its complete owned purpose and resolver configuration.
Reusable definitions, instances, prepared executions, participant ordinals and
actual captured client sessions remain different records. Workspace cwd does not
select an effort, instance, purpose or native store.

```sh
noetic opermem create-instance /absolute/instance-request.json
noetic opermem --host /absolute/opermem-operation-host --store /private/A-native \
  bind-store --namespace-path /private/ordinals.sqlite3 --effort-root 0.1 \
  --command-id A-native-registration
noetic opermem --host /absolute/opermem-operation-host --store /private/A-native \
  --runs-dir /private/runs run /absolute/question.md --workspace /absolute/project \
  --operation question --inquiry --client pi \
  --scope-request /absolute/scope-request.json --store-ref /absolute/store-reference.json \
  --purpose-ref /absolute/purpose-reference.json --purpose-config /absolute/purpose-config.json \
  --source /absolute/selected-source.md
noetic opermem inspect --namespace-path /private/ordinals.sqlite3 --effort-root 0.1
```

`create-instance` consumes `namespace_path`, stable `command_id`, `effort_root`,
`initiator`, `intent`, exact effort `environment`, and actual `origin` with either
`human_ref` or exact agent `delegator`; optional `parent_instance` remains explicit.
Its JSON output is the actual instance record. `bind-store` outputs the complete
`store_ref` to retain as JSON; it registers correspondence without starting the
native host or creating its store. Registration serializes path aliases within
the declared canonical namespace. It makes no host-global ownership claim and
assigns no pre-existing native history.

A `scope_request` contains `namespace_path`, `effort_root`, `discipline_id`, exact
`environment`, and actual `origin` with its `human_ref` or `delegator`. The purpose
reference and resolver configuration are either both absent or the complete
records returned by the accepted purpose helper. A partial pair is refused.
Owned work without purpose retains None Telos fields and creates no Telos linkage;
bare legacy Telos flags are refused. When the complete pair is supplied, legacy
Telos flags must agree with that reference. Owned run selection validates read-only
before directory creation, native initialization, checking, Telos linkage or
actor effects. It reserves one execution/UUID and fsyncs immutable preparation
under `.opermem-preparations/UUID/binding.json` before those effects. Actual native
context and the canonical store correspondence are retained in `opermem-link.json`
and canonical history before actor dispatch. Work and review receive genuine
reserved ordinals; session identity is observed only from their captured native
streams. Header then failure retains a failed actual session; missing header or
launch failure creates no session. Preparation-only failures have no fabricated
run journal or controller and remain inspectable.

Each selected `--source` is an explicitly captured external host evidence record,
with original locator, hash and bytes. It can ground a first question and its
explicit occasion correlation. Bootstrap ExperienceId1 has no substantive source
content; captured source bytes are never called native-retained experience.
Actual native workspace/scope IDs (including1) are qualified by their declared
store directory. Different A/B/recovery efforts may share cwd while retaining
separate native stores and owned purposes.

Owned `resume` revalidates complete purpose identity/resolver, store and immutable
ownership before reading contributions, issuing native replay or synchronizing
Telos. The original observed work/review identities and report bytes must agree.
If preparation completed and review accepted but purpose availability blocked
submission before a pending file existed, restoration may reconstruct the exact
command from the original frozen context/report. It still requires that context
for a new effect. Existing occupied native receipt slots permit genuine original
replay after drift, including operations12–14; current export is not required
before their receipt lookup. A persisted owned receipt is checked against its
original canonical receipt identity (or real read-only native slot after a
metadata interruption). Receipt-only recovery issues no actor or native host
commands and creates no duplicate ordinal, native effect or Telos result.

Python consumers use `run_task(args, on_prepared=callback)` for a synchronous
reviewed run. The optional observation callback receives a copy of the actual
immutable preparation immediately before native effects. It is called once;
callback failure retains that original preparation/failure and prevents effects.
There is no automatic restart. The default is `None`. `owned_run(run_dir,
revalidate_purpose=False)` and `owned_correspondence(run_dir)` are read-only
ownership/inspection gates. The correspondence exposes actual work/review
participants, prepared execution, full purpose, declared namespace, store-qualified
native identity and whole historical native link. It does not create controller
files, claim UI/catalog availability or promote native semantic standing.

Scoped recall accepts explicit application, effort, ordinal or exact session
selection through `noetic recall`. Ownership gates precede report/context content.
An exact actor session receives only its own retained report/observations; another
actor's report and execution-level native context/source association are excluded.
Effort/execution inspection may disclose intact historical native packets with
original standing, voice, cut and exclusions. Historical disclosure is not current
native admission. Preparation failures remain visible; legacy unassigned histories
remain application-only and are not adopted or relabeled.

## Purpose and qualification

Bind an existing authorized isolated Telos chain with `--telos-chain CHAIN_ID`,
`--telos-db /private/telos.sqlite3`, and `--telos-source /path/to/telos-core.mjs`.
This command creates no master chain. Each run freezes the current purpose,
essential principles, reproductive clause, and eight most recent retained run
results in `telos-context.json` for both worker and reviewer. Earlier omitted
record count is explicit. A later run obtains a fresh aggregate; prior run paths
remain historical references, not proof of current process health.

The bounded task remains the run goal and Telos subgoal objective. Opermem context
and optional model evidence go into the prompts and separate retained artifacts.
They do not become Telos semantic authority. The master chain remains active;
only the associated run subgoal can complete.

An optional `--qualification /path/to/packet.json` consumes the original schema-6
packet produced by `noetic genus`. It must match the original task text and exact
explicit worker model. The packet is retained unchanged as
`genus-selection.json`, with its full selection response, uncertainty, controls,
and consumer decision. A catalog-unmatched choice remains unmatched even if the
runtime successfully executes it. Reviewer model choice is separate; this worker
packet does not establish reviewer qualification. See [model qualification](model-qualification.md).

The runner applies the selected profile's `reasoning_effort` as Pi's `--thinking`
argument. An explicit `--thinking` must agree with that profile. Other profile
controls, and controls on unsupported clients, fail before launching an actor;
they are not silently discarded. An unmatched explicit Pi choice may also use
`--thinking`. Actual worker controls are retained with the run's model identities.

## Outcomes and recovery

An accepted Synthesis review records the repository task outcome. For an
Opermem-enabled run, Telos additionally requires a committed contribution receipt
before its subgoal completes. Missing submission leaves that subgoal active and
the reviewed task intact. Rust and Telos use separate databases; no shared
transaction or automatic semantic promotion is claimed.

The run retains `opermem-link.json`, the original context transcript, the exact
pending command written before submission, and `opermem-receipt.json`. If Rust
commits before the receipt write is interrupted, replay the same command:

```sh
noetic opermem --host /path/to/opermem-operation-host \
  --store /private/opermem-store --runs-dir /private/runs resume /private/runs/RUN_ID
```

`resume` restores the receipt under the original run/key and retries Telos
metadata without invoking an actor. An existing receipt also permits a Telos-only
retry. A Telos synchronization error remains visible and makes the command return
1 despite reviewed work and a committed Opermem deposit. Repeated successful
metadata synchronization creates no duplicate subgoal or learning.

A changed Opermem context blocks a new submission. An owned accepted run can
reconstruct a missing pending file only from its original immutable context and
actual report; a new context never replaces that preparation. Legacy runs require
their original pending file. The adapter exposes all fourteen native operations.

## Judgment and practical questions

Judgment selects one native sealed warrant and its entire condition set. Supply
positive u64 IDs in strictly increasing numeric order; decimal IDs are parsed
exactly by Python and Rust. A partial set is rejected against the whole warrant's
`has-condition` ancestry. The adapter requires each whole checked condition and
exactly one current linked evidence record, preserving content hashes, native
versions and the pinned cut. Ambiguous or unavailable material requires a fresh
applicable context; the adapter does not pick one evidence record silently.

```sh
noetic opermem --host /path/to/opermem-operation-host \
  --store /private/opermem-store --runs-dir /private/runs \
  run judgment-task.md --workspace /path/to/project \
  --operation judgment --warrant-id WARRANT_ID \
  --condition-ids CONDITION_ID_1 CONDITION_ID_2 \
  --client pi --model openai-codex/gpt-6.1-sol --thinking high --inquiry
```

The actor proposes one exact report contribution:

```text
OPERMEM_CONTRIBUTION_JSON: {"polarity":{"kind":"yea"},"defeat_conditions":["A changed predicate defeats this judgment."],"rationale":"Explain the entire checked snapshot, the polarity and its bounded scope."}
```

`yea` and `nay` polarity objects contain only `kind`. `perchance` additionally
requires integer `confidence_basis_points` from 0 through 10000. Defeat conditions
are a nonempty sorted unique array of trimmed nonempty strings. The exact actor
rationale stays in the report, pending command metadata and receipt contribution;
the native judgment command accepts polarity, defeat conditions, warrant and
evidence snapshot, with no rationale field. Snapshot cardinality derives from
the complete live warrant, including every current condition/evidence pair.
Expected versions include exactly every evidence record, the warrant and every
condition in native CanonicalId order. Rust validates sealing, full snapshot,
polarity, evidence coverage, verifier, fingerprints and ancestry. Successful
repository tests or Synthesis review cannot select or affirm the polarity.

Practical questioning selects an explicit complete set of judgments:

```sh
noetic opermem --host /path/to/opermem-operation-host \
  --store /private/opermem-store --runs-dir /private/runs \
  run practical-question-task.md --workspace /path/to/project \
  --operation practical-question --judgment-ids JUDGMENT_ID_1 JUDGMENT_ID_2 \
  --client pi --model openai-codex/gpt-6.1-sol --thinking high --inquiry
```

Its contribution is `{"text":"Given these judgments, what can be done?"}`.
Each selected whole current judgment retains its native warrant, complete
evidence snapshot, polarity, defeat conditions, standing and ancestry; every
selected judgment enters the command and expected versions. Rust independently
revalidates their judgment material. `--parent-id` is invalid for these two
operations; `context` accepts the same complete anchor flags. Operations12–14 are documented below.

Both operations use separate actor/reviewer roles and the existing task result,
pending command, exact native replay and receipt-before-Telos completion path.
The pending record additionally binds their exact actor contribution, including
judgment rationale, so resume refuses substitutions before native contact.
Context drift after review preserves the task and active pending purpose without
deposit. A crash after native acceptance replays the original immutable receipt
without another actor or duplicated semantic effect.

On resume, an uncommitted pending command still requires the exact reviewed
context. If the current context differs, the adapter reads the native accepted
primary receipt slot in `authority.sqlite3` with SQLite `mode=ro`. The maintained
host/schema-v3 contract pins integration ID and effect-scope version to 1;
workspace/scope come from the fresh native cut, operation numbers follow the
native fourteen-operation order, and IDs are big-endian u64 blobs. The lookup
matches the entire slot including the exact idempotency key and accepted semantic
commit. Missing, unsupported or incomplete lookup refuses submission. An occupied
accepted slot permits only Rust's genuine `idempotency-replay` with matching
original receipt ID and exact result; no SQLite record is synthesized as a
receipt. This distinguishes a crash before native submission from a crash after
native acceptance while preserving the receipt-before-Telos gate.

Disposable Rust/SQLite fixtures exercise five-condition judgment and a practical
question with two actual native judgment parents after fresh host restart.
These are model-free composition checks. The host's coverage/verifier tokens
remain non-probative policy placeholders; checking's declared manifest anchor
does not register external repository sources or prove exhaustive dependencies.
This increment establishes no live fourteen-operation exercise, independent
verifier adequacy, human cognitive value, decision, plan or external-act authority.

## Practical inquiry, insight and deliberation

Operations 9–11 use explicit native anchors and the same reviewed task,
whole-context drift gate, exact native submission, committed replay and Telos
receipt gate. `--parent-id` is invalid for these operations.

| Operation | Host-selected anchors | Actor contribution |
|---|---|---|
| `practical-inquiry` | `--practical-question-id Q` | `{"text":"A possible course of action."}` |
| `practical-insight` | `--practical-question-id Q --option-id O` | `{"text":"Explain how the selected course could work."}` |
| `deliberation` | `--practical-question-id Q --option-ids O1 O2 O3 ...` | `criteria`, `trade_offs`, `objections_and_responses`, `value_scale` |

Practical inquiry creates a native candidate option and increments the practical
question's actual current object version. Practical insight requires that exact
current question and its own current option, producing an unverified trace.
Repeated inquiry obtains fresh versions; previous fixture versions are never
reused as command constants. Course and insight text are nonempty trimmed strings.
Their actor contributions contain reasoning content; selected native IDs,
complete reference sets and versions are host envelope fields.

Deliberation takes the entire current native option set in strictly increasing
numeric u64 order, with at least two options. The adapter checks equality against
whole question `option-for` ancestry, requires every current option and exactly
one current native unverified trace for each, and derives native option/insight
pairs. Missing, partial, foreign or ambiguous material refuses submission. A
second current trace for one option is disclosed as ambiguity. Native Rust checks
the exact whole current option set, trace uniqueness and complete live judgment
ancestry; Synthesis does not select an option, decide or authorize action.

Example actor report:

```text
OPERMEM_CONTRIBUTION_JSON: {"criteria":["All courses address the practical question."],"trade_offs":["Direct inspection costs source-reading time."],"objections_and_responses":["Objection: manifests can drift. Response: compare retained and current bytes."],"value_scale":"Prefer reproducible understanding and explicit uncertainty."}
```

Each array must contain nonempty trimmed strings in strictly sorted unique order;
`value_scale` is one nonempty trimmed string. These exact values enter the native
evaluation. Option/trace pairs come from current native context, rather than
actor-supplied IDs. Expected refs are exactly question for inquiry; option then
question for insight; every option, question, then every practical trace for
deliberation, sorted by native identity enum and numeric u64 within each kind.
Each version is taken from its actual whole native residue.

Native retrieval contracts remain separate. The primary practical-insight
export admits question/option and excludes judgment objects; primary deliberation
admits options/traces/evaluations and excludes question/judgments. To retain whole
judgment ancestry and obtain current question versions for insight/deliberation,
the adapter creates a
`noetic-practical-context/v1` envelope containing intact `native_context_packets`:
the primary export and a supplemental native
`practical-inquiry` export for the exact same question. Each packet keeps its
own operation role, exclusions, standing, whole residue, provenance and pinned
cut verbatim. Packets must share the exact native cut; duplicate residues must
agree on version, content/hash, liveness, standing, voice and ancestry.
Practical inquiry retains its original raw whole native export, which already
admits the question, judgments and candidate options.

An internal lookup combines actual retained residues to construct the command.
That lookup is not emitted as a broader native-admitted residue set. Supplemental
material retains its source operation role and confers no primary operation
authority. The entire explicit envelope is retained for actor/reviewer and bound
to the pending command; any drift blocks fresh submission. Genuine committed
replay uses the accepted native receipt distinction described above, including
after option creation advances the question version.

Disposable real Rust/SQLite fixtures exercise three distinct candidate courses
and traces with two native judgments, complete evaluation/ancestry retrieval
after host restart, question-version progression, exact native refusal paths and
each operation's reviewed drift/precommit/postcommit recovery. Deterministic
fixture actors establish composition behavior; they do not establish model
reasoning quality, human cognitive adequacy or a live fourteen-operation exercise.
The native shadow-only checking/coverage/verifier limitations remain operative.
Operations 12–14, decision, planning and external action remain outside this unit.


## Host-captured checking

Checking takes an initially unchecked condition as `--parent-id` and its explicit
`--warrant-id`. It requires a closed `noetic-checking-spec/v1` JSON specification
and a native host supporting `opermem-checking-provenance/v2`:

```sh
noetic opermem --host /path/to/opermem-operation-host \
  --store /private/opermem-store --runs-dir /private/runs \
  run checking-task.md --workspace /path/to/project \
  --operation checking --parent-id CONDITION_ID --warrant-id WARRANT_ID \
  --checking-spec exact-checking-spec.json --inquiry \
  --client pi --model openai-codex/gpt-6.1-sol --thinking high
```

The host executes the specification's exact argv/cwd in its explicit controlled
public environment **before worker provider contact**. Do not put real provider
credentials or an ambient environment dump in a specification. The spec binds
exact native condition/warrant IDs, versions, content hashes, condition text and
text digest; it declares selected tests, predicate/test mappings, expected
observations, bounded scope and exact source/dependency file digests. Native
residue content hashes, relation, unchecked state and cut bindings are validated.
The whole current typed context and its fresh cut remain intact.

`scripts/noetic_checking_tests.py` runs exact unittest identities and emits
`noetic-checking-observations/v1` with actual per-test results. Each declared
predicate requires all its selected tests to execute and pass. Assertion failure
produces unfulfilled evidence even when the command exits nonzero. Skip, missing
execution, error, timeout, malformed/duplicate/substituted test observations or
an unexplained nonzero exit cannot fulfill a predicate. A launch failure records
indeterminate capture but cannot supply native host-execution provenance.
A bare zero exit supplies no fulfillment evidence. Tests and specifications must
assert the narrow intended observations; the collector does not infer them from
condition prose or a model report.

The retained manifest includes exact command and public environment, completion
and exit status, stdout/stderr bytes and digests, actual selected/executed/skipped
counts, predicate outcomes, current whole context/cut, exact source snapshots and
hashes. Worker and fresh reviewer inspect the pre-existing evidence. Between them
the verification hook only revalidates its pinned manifest, retained artifacts,
registered spec and current source hashes. Before native submission the host
revalidates those bindings and current whole Opermem context again. Checking's
result, full v2 descriptor and fingerprints are constructed by the host; actor
contribution markers are ignored for this operation. `--verify` overrides are
rejected for checking.

A single fingerprint uses the native warrant as a stable, explicitly declared
retained anchor and the manifest digest as its observed value. Native expected
versions include condition and every dependency/source reference, deduplicated
in native identity order. This does not register repository sources or create an
automatic external drift service. Individual selected source/dependency hashes
and retained bytes remain in the manifest. Generated temporary artifacts can be
retained as bytes even after their original paths disappear; current durable
source hashes and historical artifact bindings have different checks.

Exact replay derives the contribution again from the pinned retained evidence
and original whole context, compares the complete persisted pending command,
and replays it under the original key. It invokes no worker, reviewer, checking
command or new deposit. Current external source paths need not still exist for
exact replay. The native receipt is retained before Telos completion. A present
checking receipt is also checked against the host-derived contribution before a
Telos-only retry.

Descriptor validation and repository review acceptance do not prove verifier
independence, exhaustive dependency coverage, an external act, semantic
promotion, or cognitive value. Existing v1 offline checking semantics remain
native and unchanged. Checking already checked conditions and operation7
judgment are separate future units.


## Decision and planning (operations 12–13)

Decision uses `--evaluation-id E --judgment-basis-ids J1 J2 ...`; planning uses
`--decision-id D --judgment-basis-ids J1 J2 ...`. Both require the entire retained
basis in strictly sorted, unique positive u64 order and reject `--parent-id`.
The `context` command accepts the same anchors. Native decision and planning
exports stay intact and raw unless a decision explicitly selects supersession.
Their admitted roles, exclusions, standing, provenance and full cut remain
operative. Referenced ancestors are not automatically admitted whole payloads;
missing roles are not synthesized. Rust revalidates recursive semantic ancestry.

Decision's actor contribution follows the native choice contract:

```text
OPERMEM_CONTRIBUTION_JSON: {"selected_option_id":101,"rejected":[{"option_id":102,"reason":"Defer this alternative pending comparison."},{"option_id":103,"reason":"This alternative requires additional retained source material."}],"intention":{"kind":"active"}}
```

Use actual native IDs from the whole evaluation. Selection plus rejected reasons
must account for exactly all evaluated options, with rejected records in numeric
option-ID order. The selected option cannot also be rejected. The actor chooses
the course and issues either `{"kind":"active"}` or
`{"kind":"abeyant","trigger":"Required prospective trigger text."}`. These are
reasoned proposals; review acceptance does not make a decision adequate or an
intention fulfilled. The host supplies the explicit evaluation/basis and current
native versions. Immediate expected references are exactly the judgments,
optional predecessor decision, evaluation and entire selected/rejected option
set in native kind/ID order; no transitive versions are added.

Optional `--supersedes-decision-id PREDECESSOR` requests deliberate supersession.
The default supplement is a native planning export anchored to that live
predecessor and the same whole basis. The retained predecessor supplies its old
evaluation without requiring the user to reconstruct that relationship. When
an old-evaluation packet is needed, also supply
`--predecessor-evaluation-id OLD_EVALUATION` from retained native receipt/voice or
context. That selector is checked against the whole predecessor; it is never
guessed. Its supplement is native decision retrieval under the old evaluation.
The new evaluation's primary export cannot supply a legal predecessor from a
different evaluation. Both exact packets remain separate in the Noetic-owned
`noetic-decision-context/v1` envelope at the identical full native cut; the
internal lookup union is not emitted as a broader native admission. A disclosed
superseded predecessor remains historical and cannot be superseded again.
Unavailable anchors/export bounds fail explicitly. Native Rust owns predecessor
eligibility, same-question/same-basis and different-evaluation validation.

Planning derives the unique issued intention from the selected whole native
decision, validates the exact whole basis, and accepts only an active or surfaced
live intention. An abeyant intention is inspectable native residue but is refused
for planning. Native trigger capture gaps remain explicit; this runner does not
manufacture a trigger occurrence or surface an intention. The actor supplies:

```text
OPERMEM_CONTRIBUTION_JSON: {"steps":[{"position":1,"action":"Read retained records.","condition":"The external host authorizes this reading."},{"position":2,"action":"Compare actual retained identifiers."}]}
```

Steps preserve array order, contiguous positions `1..N`, required scalar action
text and optional scalar condition text. Omit `condition` when absent; null is
invalid. Text must be nonempty and trimmed, at most 8192 UTF-8 bytes; collections
are bounded to 128 items by the frozen host policy. Text is preserved exactly,
without normalization. Immediate expected references are exactly intention,
every judgment, and decision, in native order. Accepted plans/steps are prospective
residue. A condition text, native acceptance or model-proposed plan grants no
permission to execute an external act. The acting contract below covers operation 14.

Whole reviewed context governs submission. Before commitment, drift or unavailable
current context preserves the reviewed report, pending command and active Telos
purpose without a new effect. Stable pending commands can retry unchanged. After
commitment, supersession may invalidate its own predecessor planning export. For
12–13 only, resume first validates the original pending command/contribution and
uses native health's workspace/scope plus the maintained read-only accepted-slot
lookup before current export. An occupied slot grants only real Rust idempotency
replay matching the exact original receipt ID and result bytes. The lookup never
constructs a receipt or changes native state. Schema-v3 slot IDs are big-endian
u64 blobs, integration/effect-scope version are the host's compiled `1`, and effect
numbers follow native operation order (`12`/`13`). Unsupported/incomplete lookup
fails unavailable. Telos completes only after that native receipt is retained;
receipt-only retries create no second result. Accepted operations 1–11 keep their
existing drift gates, including raw operation-9 context.

Verification uses deterministic local actors, actual frozen Rust subprocesses
and disposable native/Telos stores: three real alternatives/traces and two
judgments, complete choice and conditioned multi-step plan, fresh-process whole
admitted residue, legal supersession/history, native refusal matrices and crash
replay. This does not establish model reasoning quality, human cognitive adequacy,
trigger fulfillment, external execution, operation 14, live deposits, installation
or complete fourteen-operation delivery. Native shadow-only coverage/verifier
placeholders remain non-probative.


## Acting observation and question recurrence (operation 14 → 1)

Acting observes a separately retained external execution. It uses
`--plan-id PLAN --step-id STEP` plus either `--observed-run /path/to/source-run`
(with optional `--observed-step work|verify|review`, default work) or
`--observation-evidence /path/to/frozen-archive --observation-manifest-sha256 HASH`.
The archived form preserves its own selected step and remains usable after the
original source disappears. Acting requires `--inquiry` and no `--verify` command:
the observer and separate reviewer read evidence instead of rerunning the act or
its verification. `context --operation acting --plan-id ... --step-id ...` retrieves
raw native acting context without executing or observing anything.

The accepted `noetic_act_observation.capture` helper snapshots actual retained
Noetic command events/log bytes and optional task, prompt, report, review, change
and purpose files. Missing optional evidence remains missing. Capture checks
source stability; subsequent revalidation is explicitly archival (`current=False`).
A caller may separately request `revalidate(..., current=True)` to check original
source bytes; archived recovery makes no current-source claim. Failed, timed-out
or interrupted work that actually started remains observable. Launch failure is
retained non-occurrence evidence and cannot produce a native act deposit. Original
work/review acceptance or successful verification is not a prerequisite for a
subsequent truthful observation. Recorder evidence does not establish authenticity,
exhaustive history, tool authorship or the intended success of an act.

Before invoking the observer, the host freezes `observation-binding.json` with the
observing run ID, manifest hash, selected event, native context hash/cut and
plan/step. Both observer and reviewer receive the manifest/status and have
read-only access to every file in the complete frozen archive. The observing run
retains that binding and its own archive. Source cwd does not infer effort or agent
ordinal. The selected plan/step correspondence is retrospective: these records
do not retroactively prove dispatch under a native plan, effort or ordinal mandate.
Any genuine original provenance remains preserved in raw evidence.

The actor supplies exact native prose:

```text
OPERMEM_CONTRIBUTION_JSON: {"observed_act":"  Attempted the comparison.\n","outcome":"The command failed with exit7.\n","deviation":"Actual work failed; this differs from the retained planned action.\n"}
```

Artifacts are nonblank UTF-8, individually at most24576 bytes and at most32768
bytes combined. LF and boundary whitespace are preserved exactly; every other
Unicode control character, including tab/CR, is invalid. Do not normalize or
truncate text, or copy planned prose solely to avoid a deviation. Exact equality
of observed_act and the selected native step action requires absent deviation;
inequality requires deviation. Omit absent deviation rather than using null.
The observer and reviewer remain responsible for the interpretation: deterministic
host checks identify the retained occurrence and validate native constraints;
they do not certify prose truth.

The host attaches required `observation:{manifest_sha256,finish_sequence}` metadata
to the immutable contribution/pending/receipt wrapper. These fields are excluded
from native body and exact native result bytes. Archive hash/event substitution,
missing required bytes or failed archival validation refuses deposit. Evidence
failure after review preserves the report and active Telos purpose. Native acting
context remains raw with its original roles, standing, exclusions, provenance and
full cut. Only current plan and selected step enter immediate expected versions,
in native order; no ancestors or sibling steps are synthetically admitted. Rust
revalidates full semantic plan/step/decision/intention/judgment/warrant ancestry.

Native acceptance creates exactly act trace, outcome and outcome-as-experience,
plus deviation when supplied. It neither dispatches work nor automatically
completes a plan/step or effort. Acting joins the existing receipt-first native
replay path used by12–13: the original pending command/contribution and archival
binding must validate before native contact; reconciled health and the full real
accepted-slot lookup permit only genuine original receipt/result replay. Without
an accepted slot, the current whole reviewed context must still export and match.
Drift/unavailability refuses a fresh effect. Recovery invokes no original act,
observer or verification. A retained native receipt precedes Telos completion;
receipt-only repetition makes no second purpose result.

Question now exposes `--occasion-kind experience|outcome-as-experience` and
`--occasion-id ID` through `run`, `context` and `seed-question`. Omitted selectors
preserve bootstrap experience1 and its legacy native command. An explicit
outcome-as-experience requires an exact positive u64 ID. Purpose, parent selection,
expected current native object version, command body and resume link all use that
actual typed occasion. For example:

```sh
noetic opermem --host /path/to/opermem-operation-host \
  --store /private/opermem-store --runs-dir /private/runs \
  run recurrent-question.md --workspace /path/to/project \
  --operation question --occasion-kind outcome-as-experience \
  --occasion-id ACTUAL_NATIVE_OUTCOME_EXPERIENCE_ID --inquiry
```

Retrieving an outcome alone is not recurrence: the subsequent accepted fresh
question must name that exact native outcome-as-experience and its current
version. Failed outcomes may initiate useful inquiry as well as successful ones.
The adapter supports all fourteen native operations, but deterministic fixture
coverage does not establish real model quality, human cognitive adequacy/value,
independent verifier adequacy, exhaustive source registration, actual live
fourteen-operation work, deployment or complete-framework delivery. Native
shadow-only semantics and the external host's execution authority remain distinct.

## Exhausted attempt purpose

When a linked attempt exhausts its initial work and its one causal retry without
native admission, the caller may record a responsible blocked disposition in the
native Telos chain without authorizing another attempt or touching the run:

```sh
noetic goal block CHAIN_ID SUBGOAL_ID /path/to/run \
  --db /absolute/path/telos.sqlite3 --source /absolute/telos-source \
  --reason "Attempt exhausted without native admission; residual report retained"
```

Both `--db` and `--source` are required; there is no default fallback. The
reason is caller-authored, explicit nonblank text; it is not an automatic
exhaustion detection and implies no native Insight, Checking, Judgment, or
authority. The run must already carry a persisted `telos.linked` association
matching the exact chain, subgoal, database, and source; no attach or creation
occurs. Only the active exact attempt may become blocked: completed or pending
subgoals, wrong bindings, and blank reasons are refused before any native
mutation, and no foreign database is created. The native master stays ACTIVE
with the reproductive clause and other subgoals preserved, the target keeps
`completedAt` NULL, and the only residue is one native `goal_blocked` record.
A repeated block with the identical reason is idempotent; the run journal,
events, reports, controller state, and Opermem receipts are never modified.
