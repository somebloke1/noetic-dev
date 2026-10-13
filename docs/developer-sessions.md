# Developer sessions in the persistent ordinal namespace

State: no production migration/deployment. Browser and CLI are later consumer units.
All routes retain existing bearer token and same-origin action checks.

## Registration and sessions

POST /api/efforts {intent:"A",environment:{cwd:"/absolute/project"},optional mandate/human_ref/source_ref}
-> HTTP201 {effort:{ordinal:"0.0",effort:"0.0",intent,environment,mandate,...}}
No provider starts. One position per enduring effort. Same cwd does not merge intent.

POST /api/developer-sessions {effort_root:"0.0",prompt:"...",optional ordinal/title/model/thinking/projects_root}
-> HTTP201 {session:{id:native-registry-UUID,ordinal:"0.0",effort_root:"0.0",target:{ordinal:"0.0",instantiation:1,session:1},native_session_id,native_session_file,workspace,status,...}}
Repeated calls at the same effort allocate new native conversations and session selectors at its existing position/instantiation. New session does not allocate effort. Ordinal defaults to effort_root; optional ordinal selects an existing position in that effort.
Explicit succession adds succession:{predecessor:1,handoff:{responsibility:"...",context:"..."}}; position remains identical, instantiation increments. Exact old recipients never redirect.

POST /api/developer-projects {directory:"name-or-folder",prompt:"...",optional intent/title/model/thinking/projects_root}
-> HTTP201 {session:...}. Combined explicit Create action prepares a Git repository using the maintained helper, registers human effort intent (defaults to prompt) then opens its first session. Opening an existing folder: register effort using its absolute cwd, then POST developer-sessions; the conversation uses that exact existing folder, including repository subdirectories and ordinary folders beneath an ancestor repository. Conversation startup validates the folder without initializing Git or requiring a repository root or user worktree.

## Reads and navigation

GET /api/developer-sessions[?effort_root=0.0] -> {sessions:[all retained runtime rows including closed/failed/superseded contexts],namespace_path,runs_dir,projects_root}. Without filter, deliberate application-wide runtime catalogue; legacy rows marked legacy-unadopted, target:null.
GET /api/ordinals/{ordinal} -> {position:{ordinal,parent,effort,intent,environment,mandate,current_instantiation,...}}
GET /api/ordinals/{ordinal}/branch?after=0&limit=100[&effort_root=0.0] -> {records:[positions],next_after}
GET /api/ordinals/{ordinal}/history?after=0&limit=100[&effort_root=0.0][&instantiation=1&session=1] -> {records:[canonical correlated events],next_after}. Source refs name native registry journal, session UUID and event sequence; originals are retrieved by session detail.
GET /api/efforts -> same global branch page, namespace_path. Effort positions satisfy record.effort === record.ordinal; child positions remain in the branch page. Use /ordinals/0/branch for primary navigation.
GET /api/developer-sessions/{ordinal}?effort_root=0.0[&instantiation=1&session=1]&after=0&limit=500 -> {session,events,tree,next_after}. Both selectors preserve exact historical context. Bare ordinal selects designated current open runtime. Both selectors required for exact historical navigation. UUID compatibility selects its own exact mapping, never current replacement. tree contains all retained sessions in owning effort.
GET /api/developer-sessions/{ordinal}/file?effort_root=0.0[&instantiation=1&session=1]&path=... -> existing bounded source view from exact selected native workspace.
Literal 0 means application logical root with no fabricated provider; position/history/branch operate directly. Prompt on 0 reports unavailable.
Continue pages with next_after until records/events empty. Cursors are monotonic domain allocation/history sequences or original source event sequences, not timestamps.

## Actions

POST /api/developer-sessions/{ordinal}/prompt {message,mode:"prompt"|"steer"|"follow_up",effort_root:"0.0",optional instantiation/session}
POST /api/developer-sessions/{ordinal}/stop|reopen {effort_root:"0.0",optional instantiation/session}
-> response retains target:{ordinal,instantiation,session},native_ref and binding_id. Reopen is wrapped {session:...}. Empty payload still accepted for UUID compatibility. Bare ordinal resolves current open runtime; to reopen a closed context, supply both selectors (or its native UUID). When a stopped broker's saved native transcript is unavailable, reopen refuses before binding or launch and names the exact conversation. Restore its saved transcript or explicitly open a new conversation at the same ordinal with a new session selector. Retained history and native references remain inspectable; reopen never invents replacement context or replays prompts.
POST /api/developer-sessions/{ordinal}/shutdown {effort_root,optional instantiation/session} -> native cleanup, including a superseded retained owned process; this does not choose a successor.
POST /api/developer-sessions/{ordinal}/delegate {prompt,thinking,effort_root,optional title/model,instantiation/session} -> real child runtime row. Actual selected parentTarget, task mandate, same effort and inherited actual cwd/model/native command retained.
POST /api/developer-sessions/{ordinal}/dialog {id,value|confirmed|cancelled,effort_root,optional instantiation/session} -> existing exact native dialog response.
Foreign effort scope always rejects before delivery. Optional scope omission is deliberate application API compatibility; consumer should always pass selected effort_root for effort actions.

POST /api/actions {target:"0.0"|{ordinal,instantiation,session},kind:"prompt"|"stop",payload:{message,mode}|{operation:"stop"},effort_root:"0.0"}
-> {id,target,native_ref,environment,mandate_version,kind,payload,...}. Bind only; no provider delivery.
POST /api/actions/{id}/deliver {effort_root:"0.0"} -> exact bound recipient or clear unavailable/superseded error. Binding survives sessions/succession unchanged.

## Historical adoption

POST /api/legacy-adoptions {session_id:nativeUUID,effort_root:"0.0",optional ordinal:"0.0.0"}
Explicit/idempotent adoption of a CLOSED old registry context into an existing declared position. Source namespace qualified by original registry path/root UUID, original root/local ordinal/actual parent/native references and adoption time retained. Original row labels/UUID/events/native files preserved; output exposes original_ordinal. No retroactive global-root delegation, no cwd merging, no automatic import/replay. Target namespace and source namespace remain different identities. Current responsibilities must be registered/delegated genuinely before mapping legacy histories.

## Native managed tools

agent_delegate,agent_send,agent_read,agent_wait accept primary absolute ordinals and structured exact selectors. Broker identity supplies actual parentTarget before tool calls. parent selects actual parent; root/effort_root are disclosed aliases for owning effort root. Literal 0 reads global position/branch/history. Agent-origin delegation uses exact current actual parent and retained mandate. Tools confer no Opermem standing.

## Agent message provenance and replies

Managed `agent_send` binds `agent_message` in the canonical action store. Payload is `{message,mode,provenance:{origin:"agent",sender:{ordinal,instantiation,session},recipient:{ordinal,instantiation,session},effort_root,reply_to:{ordinal,instantiation,session},in_reply_to:null|binding_id}}`. The action ID is the message correlation `binding_id`. Sender comes from the actual calling broker; caller mismatch, foreign effort and superseded exact targets reject. Delegation's initial task uses the actual delegator as sender. Accepted bindings never choose a successor on delivery or reply.

The broker transports `/noetic-deliver <binding_id>` through Pi's existing RPC prompt/extension command protocol. The receiving extension obtains the canonical envelope from its own broker and calls Pi `sendMessage` with `customType:"noetic-agent-message"`, `details:{message,mode,provenance,binding_id}` and `deliverAs:"steer"|"followUp"`. Native history/events retain `role:"custom"`; consumers label these messages from `details.provenance.sender`, not as human input. `agent_message_sent` and `agent_message_received` host events retain the same binding and provenance; canonical correlated native-event records preserve them and original journal references.

Installed Pi's `convertToLlm` converts custom messages to provider `user` content and discards custom details. The extension therefore also renders the exact sender, recipient, effort, correlation and reply route in model-visible content. This is a compatibility representation, not an invented provider agent role. Human prompts remain ordinary user messages; textual origin claims do not create canonical provenance.

An addressed response uses `agent_send` with the original exact `provenance.reply_to` and `in_reply_to:binding_id`; the broker verifies that this reply reverses the original sender/recipient. A local chat response does not reach the sender. Unavailable original targets fail explicitly. The guidance does not force replies, answer acknowledgments automatically, or create reply loops. Receipt/queue acceptance does not prove model processing, cooperation, completion or reply.

## Installation/source boundary

Explicit namespace_path to create_server/SessionService/Registry wins. Installed NOETIC_APP_HOME selects $NOETIC_APP_HOME/state/ordinals.sqlite3. Source caller's explicitly supplied runs root otherwise owns ordinals.sqlite3. Brokers receive the resolved path explicitly, independent of agent cwd. Fixtures always inject disposable paths. Session startup does not claim live until observed get_state maps actual native session/context; failed reservations retain no invented target.

## Preserved native behavior and limits

Default model is `openai-codex/gpt-6.1-sol`; explicit custom model/thinking choices remain retained. A startup reporting a different model or native session fails before prompting. Delegates inherit actual parent cwd, model and native command; all source process environments preserve provider settings while excluding `USER_PROVIDED_PASSWORD`.

Native registry and journals remain under the explicit runs root's `developer-sessions/`. Private UUID directories retain Pi native context, RPC command/event records, stderr, broker lock and Linux boot/PID/group/start identity. The SQLite adapter migration adds correspondence columns and a correlation marker; original legacy root/local labels, UUIDs, event payloads/timestamps and native files remain retained. Existing read-only registry inspection does not migrate histories or create an application namespace.

Each detached broker owns an asynchronously correlated, continuously drained LF-delimited Pi RPC stream. Browser/server reconnection does not restart a process. Process loss requires explicit reopen after ownership cleanup is confirmed. Reopen uses the original native UUID/context with the same exact ordinal target; it never replays prompts. Acknowledgment establishes acceptance/queueing only. `agent_settled` establishes settlement. Stop clears steering/follow-up queues before abort. Shutdown cleanup remains available for the actual owned historical process, including a superseded one.

Actual extension dialogs retain exact pending IDs. Provider errors remain visible. Existing release maintenance continues to reject replacement while a broker owns its state lock. This unit establishes developer-session/API/native-tool correspondence only. Browser/CLI navigation, structured cognitive/controller correspondence, selected-scope purposes/recall, installation delivery, full fourteen-operation composition and human cognitive-value judgment are later work. No production histories have been adopted.

Disposable tests exercise A/B and separately represented R, several conversations and explicit succession at one position, immutable queued recipients, native cleanup/reopen, HTTP and actual managed tools, truthful idempotent legacy adoption, preserved source hashes and complete paging. Installed Pi is tested offline without a provider prompt. These checks establish protocol behavior, not a hosted model occurrence.

## Source module CLI

`python -m scripts.noetic_sessions --runs-dir /explicit/runs --namespace-path /explicit/ordinals.sqlite3 register-effort --workspace /absolute/project --intent "A"` registers a human effort.
`... start --effort-root 0.0 "Work"` opens a new session there. `position`, `branch`, `history` and `list` expose primary traversal; branch/history accept `--after`/`--limit` and effort-scoped calls pass `--effort-root`.
`... show 0.0 --effort-root 0.0 --instantiation 1 --session 1` selects exact history. Prompt/stop/reopen/shutdown use the same selector flags. `start --predecessor 1 --handoff '{"responsibility":"Continue A","context":"new native conversation"}'` explicitly succeeds a position. `--ordinal` selects an existing child position. Outer CLI/browser parity belongs to the consumer unit.

## Planned native context and failure diagnostics

The initial native get_state must report a nonempty absolute sessionFile reference before publishing a target or sending the original prompt. A valid planned path can be nonexistent: native persistence is lazy. Missing/malformed references produce a failed reservation with target:null, retained source failure and confirmed native cleanup; reopening never invents a context. Existing exact context-path matching still governs reopen.

A reserved/failed target:null UUID with known effort_root may be read for detail/source events using that exact owning effort_root; a foreign effort rejects. Prompt/delegate/reopen still require observed correspondence. Truly unadopted historical rows remain application-history scoped until explicit adoption.
