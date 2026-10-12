# Process Ownership

## Prompt Delivery

Generated harness and legacy development/review prompts enter Pi/OpenCode through
stdin, never argv or environment variables. `client_command` and `actor_command`
return flags only; callers supply the generated text to `stdin_text` on
`execute_step` or `_execute`. Literal user-supplied generic command argv is unchanged.
Existing private prompt artifacts remain available for observation.

The shared `scripts/noetic_processes.py:spawn` stages UTF-8 text in an anonymous
0600 temporary file inside the private observation directory, rewinds it, and
passes its descriptor as stdin. This avoids both argv size limits and blocked
pipe writers: an actor that never reads stdin cannot block the cancellation loop.
The parent closes its descriptor after spawning; the child owns its inherited
descriptor until exit. Input preparation uses local disk and happens before spawn.
The helper copies the environment and removes `USER_PROVIDED_PASSWORD` without
mutating the caller's mapping or process environment.

Installed versions were verified locally: Pi 0.85.1 and OpenCode 1.18.29.
Pi's installed `@earendil-works/pi-coding-agent/dist/main.js` lines 51-65 read
non-TTY stdin, and lines 702-710 pass it to initial-message construction.
Pi trims outer whitespace; generated prompts do not depend on it.
OpenCode's installed binary embeds `chunk-rsfx87v5.js`: its `run [message..]`
handler reads `process.stdin.isTTY ? undefined : await Bun.stdin.text()` and
passes the merged text to `session.prompt`. Both versions' help/version commands
were checked. Models, thinking flags, tool permissions and session-result parsing
are unchanged. No live inference is required by the regression tests.

## Ownership APIs

`spawn` immediately records `PID`, `PGID`, Linux `/proc/PID/stat` start ticks and
public boot ID in `NAME-ownership.json`, alongside spawn time/state. The record is
atomically replaced, fsynced before use, and private through existing file helpers.
It contains no environment, credentials or raw command dump. A recording failure
stops the original child rather than knowingly leaving an unrecorded process.

`inspect(path)` first validates the recorded identity and current kernel boot ID
as canonical lowercase version-4 UUIDs. On the same boot it reads only that
recorded PID's public stat and probes that one group with signal 0. Results are
`owned`, `absent`, `mismatched`, `boot_ended`, `unknown` or `uncertain`, with an
explicit `cleanup_confirmed` boolean. A well-formed identity from a different
valid boot yields `boot_ended`, `cleanup_confirmed: true` and `current_boot_id`:
processes belonging to that boot cannot remain alive. This path neither reads
the reused numeric PID's stat nor probes/signals its group. It establishes current
cleanup, never an actor's historical exit status, task success or cancellation.
`reconcile(path, terminate=True, timeout=3)` rechecks identity before TERM and KILL,
waits for at most the configured interval, and privately records the final
observation in `NAME-ownership-cleanup.json`. Missing/malformed identity, a reused
PID, a different boot or a missing group leader with surviving group members is
never authority to signal. An absent group or a verified ended boot confirms
cleanup. Missing/malformed boot IDs and incomplete/ambiguous identity remain
`unknown` with unconfirmed cleanup.

`noetic_harness.process_info` combines actor and optional verification observations
for **every started activation**, keyed by `ACTIVATION/actor` or `ACTIVATION/verify`
in `processes`. A ready successor or terminal kernel status never establishes
cleanup of earlier groups. Missing actor ownership, or missing verification
ownership when step events/logs establish an attempt, remains explicitly `unknown`.
Only a run with no started activations is `not_started`; otherwise cleanup requires
every relevant group to be confirmed absent or its recorded boot ended, including
historical groups.
`python -m scripts.noetic_harness cancel RUN`
requests a live driver's normal cancellation; with the driver lock available it
attempts bounded ownership-checked cleanup itself. Unknown cleanup remains an
explicit request/uncertainty, not a successful cancellation. Reopening an uncertain
running reservation still fails honestly without replay. Already absent groups
can yield cancellation or runtime failure, never classified success. Completed
runs are not cancelled or replayed.

The existing application's `runtime_info` supplies `process_cleanup` and
`cleanup_confirmed`, and its reason distinguishes a cancel request from confirmed
cleanup. Terminal kernel history with unknown ownership stays terminal, without
claiming either a live process or confirmed cleanup. Kernel policy and the
HTTP/frontend expose the same ownership-checked action.

## Terminal Cleanup And Maintenance

`noetic harness cancel RUN` and confirmed `POST /api/runs/ID/cancel` also reconcile
completed, cancelled and failed runs without changing their terminal outcome or
creating a new cancellation request. The UI labels this action **Clean up processes**
when terminal cleanup is unconfirmed. Active-driver cancellation remains a request;
only the lock owner manages its children. Repeating an action can refresh cleanup
evidence, but cannot reap zombies or authorize signalling uncertain ownership.

HTTP returns 202 while the kernel remains active, otherwise 200 for the observed
terminal outcome, with separate `cleanup_confirmed` and `process_cleanup` fields.
Neither HTTP 200 nor CLI cancel exit 0 means all processes are absent; CLI output
explicitly reports cleanup separately from kernel status.

Archive/export and release maintenance checks require cumulative confirmed cleanup
for harness runs, in addition to the existing controller and cooperative-lock gates.
The explicit release-only `--code-only` path is distinct: terminal legacy missing
ownership can remain unknown while immutable code is switched. It still refuses
known live groups, busy locks, running activations and unfinished observations;
it neither changes `process_info` nor weakens the archive/export gate. See
`docs/release-and-archives.md` for external-state adoption and rollback.
A crashed step may retain its missing exit status after actual cleanup; maintenance
can then pass these gates without inventing a `step.finished` event. Passing these
gates alone does not establish that a packaged update or rollback works; those
paths require separate execution from the standalone release artifact. Uncovered unfinished
steps and generic legacy runs retain the conservative unfinished-observation gate.
Archives retain actor/verifier ownership records so same-host validation does not
lose cleanup evidence. Ownership remains local to its recorded boot; missing or
malformed ownership does not become confirmed merely through archival. A valid
different kernel boot establishes ended lifetime independently of archival.

## Limits

This is local Linux process ownership, not a supervisor or a process namespace.
There is a small crash window between OS spawn and durable identity recording;
missing records are refused, not guessed. Public stat checks and group signals
are not an atomic OS operation. Descendants that deliberately leave the group
are outside this unit. Zombies can keep a group present until its parent/init
reaps them; that remains unconfirmed rather than being reported as absent.
No global process scans, environment reads, fencing or credentials are used.
Recorded observations establish process facts, not semantic task success.

Implementation regression tests cover actual multi-megabyte stdin, an actor that
does not read input, bounded timeout/cancel, argv privacy, caller environment
preservation, original generic argv, private identity files, a killed driver and
owned surviving child, mismatch/stale/missing refusal, absent-group cancellation,
earlier orphan/zombie groups across advance-to-ready and cancellation, completed
all-groups-absent and never-started runs, and no replay. Independent QA is
separately owned by the lead.
