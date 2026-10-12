# Agent development workflow

## Read-only inquiry

`noetic inquire question.md --workspace /path/to/project --client opencode --model MODEL`
runs the distinct `inquiry.reviewed/v1` program. Both inquirer and fresh reviewer
have read/search tools only. The report distinguishes source observations,
interpretation, critical judgment, and recommended action (P1-P4). These are
attributed cognitive work products, not automatically certified cognition.

Unlike development, inquiry does not require an unrelated test command. It
records `verification.not_requested` explicitly and relies on the separate
source-grounded semantic review. An optional `--verify COMMAND...` can supply a
relevant check. Development still requires verification. Both programs retain
transcripts, change observations, review evidence, and optional Telos linkage.
An accepted recommendation does not execute its proposed action.

`noetic_develop.py` composes an existing coding assistant, deterministic project checks, and a fresh read-only semantic reviewer. It uses the live runner's durable records, not synthetic M0/M1 events.

Write a concrete task and acceptance criteria in a text file, then run from a suitable project checkout:

```bash
python3 /path/to/noetic-dev/scripts/noetic_develop.py task.md \
  --workspace /path/to/project --client opencode \
  --verify python3 -m unittest discover -s tests
```

`--verify` must be the last option; everything after it is the verification command's argument array. `--client pi` uses Pi instead. Both clients must already be installed and configured with working model access. Optional `--model` and `--review-model` select configured client models; omitting them preserves the client's default. noetic-dev does not install providers, read credential files, or change global configuration. `--timeout` bounds each process. `--goal-ref` retains an existing purpose reference.

## What happens

1. Before agent work, the controller snapshots current tracked and nonignored untracked Git working files, including existing dirty work as the baseline. The worker receives the actual task, inspects sources, explains its approach, implements, and checks its work. It is told not to commit, push, deploy, change global configuration, or delegate.
2. The controller captures the complete structured client transcript and selects its terminal assistant message. A model error, missing final response, or truncated turn fails execution even if the CLI exited zero.
3. The supplied verification command runs in the workspace. Failure stops the workflow without acceptance.
4. The controller retains `changes.diff` and `changes.json` after work/verification, including on work or verification failure. A new assistant session receives both paths and reads the task, actual code, worker report, change evidence, and verification logs. It has read/search tools, but no edit or shell tools. It judges the acceptance criteria, not just the test exit code.
5. An explicit final `ACCEPT` or `REJECT` with evidence becomes the attributed review. A missing/invalid verdict or unavailable reviewer leaves `awaiting_review`; the program exits nonzero. There is no automatic retry or self-approval.

The run directory retains `task.md`, work/review prompts, raw stdout/stderr, `work.md`, `review.md`, parsed session identities, and committed controller events. Use `noetic_run.py status RUN_DIRECTORY` or `events RUN_DIRECTORY` to inspect it from a fresh process.

Change evidence describes **changes observed during the run**, not proof that the worker caused every change. The baseline is held in memory; Git is only queried, never committed, reset, cleaned, or frozen. Git ignore rules exclude ignored untracked content such as `.runtime` and dependencies; tracked files remain selected even if ignored. Keep run output ignored (the default `.runtime/runs`) or outside the workspace to avoid recording controller output as observed changes.

`changes.json` lists added/modified/deleted paths with before/after SHA-256 hashes, sizes, kinds, and modes; an absent side is `null`. `changes.diff` includes bounded UTF-8 text changes, with explicit omission notices for binary/non-UTF-8 files or either side over 262144 bytes. Such files still have full-content hashes in the manifest. Symlinks capture their target text, not target file contents. Unsupported entries such as submodule directories have an explicit content omission and no content hash; changes inside them are not captured. Empty-file and metadata-only changes are noted even without text hunks.

Non-Git workspaces continue normally with `status: unavailable`, a reason, and `changes: null`, not a no-change claim. Snapshot errors likewise produce unavailable evidence. Snapshots are sequential observations, not atomic across files; concurrent edits can be included. Abrupt controller termination or artifact-write failure can prevent evidence retention. Review still requires current sources and verification logs, not only this comparison.

## Cognitive and component boundaries

The worker is instructed to distinguish attention to sources, inquiry/approach, and implementation; its report remains an attributed account, not proof of cognition. Project checks supply observations. The separate reviewer supplies semantic judgment. Controller acceptance records that judgment; it does not itself complete Telos goals or prove user value beyond the stated task.

OpenCode uses temporary process-local `noetic-worker` and `noetic-reviewer` primary-agent definitions and `--pure`, disabling external plugins. No running client or global config is changed, so the parent session does not need a restart. Pi disables discovered extensions and project-local resources; models requiring a custom provider extension are not supported by this initial Pi adapter. Both clients retain their native session storage and authentication mechanisms.

These are cooperative local development workflows, not sandboxes. Workers can run shell commands and modify the selected workspace. Review tool restrictions do not prevent the client from writing its own session logs. Use a worktree where edits are intended. The reviewer cannot independently execute shell tests; it inspects controller-run evidence and sources. The implementation's own independent QA remains separate from the review of a task performed by this workflow.

Client/model selection is replaceable and explicit. This adapter does not implement genus-router or pretend to enforce the historical model-policy migration. It executes the selected, already configured client. The root's frozen policy/reference artifacts are unchanged.

For real durable purpose, [Telos-linked runs](telos-runs.md) add `--telos-chain`,
`--telos-db`, and `--telos-source`. The existing Telos core then carries the
run subgoal and reviewed result; the master goalchain stays active.
