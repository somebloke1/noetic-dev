# Goal-directed live runs

The first live noetic-dev workflow executes a work command, runs a separate verification command, and waits for an independently obtained review. It records actual process results rather than replaying declarations from a fixture. It requires Python 3.10+ and no service, model, package installation, or credentials of its own.

## Run it

From this checkout:

```bash
python3 scripts/noetic_run.py run config/workflows/check-repository.json
```

The command prints the new run directory immediately. It then checks this actual checkout and runs its tests. Logs and an append-only SQLite event journal live in `.runtime/runs/<run-id>/`. The directory is ignored by Git. In another terminal, or after restarting the client:

```bash
python3 scripts/noetic_run.py list --runs-dir .runtime/runs
python3 scripts/noetic_run.py list --runs-dir .runtime/runs --json
python3 scripts/noetic_run.py status .runtime/runs/<run-id>
python3 scripts/noetic_run.py status .runtime/runs/<run-id> --json
python3 scripts/noetic_run.py events .runtime/runs/<run-id>
```

`events` exports JSON Lines. Each committed event has a sequence number, timestamp, kind, and payload. Status is rebuilt from those events. Work and verification stdout/stderr are separate files so large command output does not become prompt context or database payload.

`list` discovers immediate child run directories, newest creation event first, showing each run's ID, goal, last-observed state, and absolute directory. `--json` returns an array with `run_id`, `goal`, `state`, and `directory` fields. Missing or empty directories produce an empty list without creating anything. Non-run entries are ignored; damaged journals are reported on stderr and skipped.

Both commands exiting zero yields **awaiting_review**, not success or acceptance. A separate reviewer inspects the actual artifacts, command output, and goal. Record that review with:

```bash
python3 scripts/noetic_run.py review .runtime/runs/<run-id> \
  --verdict accept --reviewer reviewer-session-id --evidence review.txt
```

Use `--verdict reject` for rejection. The evidence file must contain the review's reasoning, checks, and results, not merely a verdict. Its contents and SHA-256 are retained in the event journal. Review is allowed exactly once, only after both commands pass. A failed or unfinished run cannot be approved through this command.

## Run your work

A plan is a JSON object with:

```json
{
  "goal": "A concrete user-valued outcome and acceptance criteria",
  "goal_ref": "Optional Telos chain/subgoal or issue reference",
  "work": ["your-worker-command", "argument"],
  "verify": ["your-test-command", "argument"],
  "timeout_seconds": 900
}
```

`work` can invoke an existing coding-assistant CLI, a build, or another executable. `verify` should run the project's relevant checks. Use `--workspace /path/to/project` to choose the command working directory and `--runs-dir /path/to/runs` to put records elsewhere. Relative command arguments resolve against the workspace; the plan path and an explicit runs directory resolve against the invoking shell's directory. Commands are argument arrays, not shell strings; pipes and redirection are not implicitly evaluated. Standard input is closed, so use noninteractive commands.

This is a deterministic outer controller, not a replacement for an agent runtime. Agents can attend to sources, form proposals, and act inside the work step; tests provide environmental feedback; a separate reviewer supplies judgment. Those cognitive operations are not inferred from step labels or process exit codes. `goal_ref` is a reference, not a Telos API integration or permission to complete a goalchain.

## Failure and limits

- Work failure prevents verification from starting. Verification failure prevents review. Missing executables, timeouts, and normal interrupts retain failed step evidence.
- Timeout applies to each command. On POSIX, each step owns a new process group; cancellation terminates that group. Synchronous commands must not leave background services running. On other platforms only the immediate child is terminated.
- SQLite commits events transactionally. Completed command logs are flushed and fsynced. This is process-restart persistence, not a claim of machine-loss recovery for arbitrary filesystem or hardware failure.
- A hard-killed runner may leave children running and an `unfinished` record. Status is last-observed state, not a live health probe. Inspect the workspace and processes before starting new work. There is deliberately no automatic retry or resume of potentially non-idempotent commands.
- The controller does not sandbox commands, supply model routing, change client configuration, make commits, push, merge, or deploy. Commands retain the invoking user's permissions and configured runtime policies. Use an appropriate worktree and existing client permissions for editing tasks.
- Plans and command output are local records, not automatically sanitized or published. Do not place credentials in arguments or review evidence.
- Reviews are attributed statements, not authenticated identities or an automatic proof of independence. A zero-exit verifier is not semantic QA. A review accepts the recorded run; it does not seal the workspace against subsequent edits or certify that an agent's zero exit means its goal was accomplished.

The frozen M0/M1 reducers and the bounded cognitional-event journal remain useful conformance examples. They are not used as live event admission rules: their complete-trace digest and predeclared final candidate do not fit work whose results are not known yet. This live runner is the smallest composition of process execution, durable observations, a status view, and independent review. Generic scheduling, automatic remediation, shared memory, and web/TUI rendering are not prerequisites to use it.
