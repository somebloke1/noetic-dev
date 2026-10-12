# Projects and development task workspaces

## Choose a project

A project can be an ordinary folder. No existing Git repository, branch, initial commit, or user-created worktree is required.

`scripts.noetic_projects.create_project(directory, projects_root=None)` creates a missing or empty project folder and initializes Git. An existing nonempty folder is refused with HTTP-compatible status 409; choose Open for that folder.

`prepare_project(directory, create=False, projects_root=None)` opens an existing folder, initializes Git if needed, and preserves its files. It refuses a missing folder unless creation is explicitly requested. A bare name resolves beneath the chosen absolute projects location, default `~/workspace`; an absolute folder path is accepted directly. Relative multi-component paths are refused. A folder that merely inherits a parent's repository is refused with the actual parent root in the reason. Explicitly created independent nested repositories and existing independent nested repositories are supported.

`ProjectError` carries `status` (400 for invalid preparation, 409 for a conflicting Create choice). Conversational root sessions use the prepared project folder directly.

## Development patterns

`Application.start` accepts the chosen project as `workspace`, optionally `projects_root`. Development patterns prepare a detached controller-owned worktree under `~/.local/share/noetic-dev-work/task-worktrees/<id>`. Cognition retains its existing read-only behavior in the project folder.

The owned task area is private and outside adopted `.runtime` state. Tracked working contents, staged/unstaged working contents, deleted paths, untracked files, ignored local files and symlinks are copied without staging, stashing, resetting, committing user contents, or advancing the source branch. Symlinks retain their link targets; this is file isolation, not a filesystem sandbox. Adopted run state is excluded from the task copy. Preparation failures retain the partial worktree and report its path.

For an unborn repository, Git creates an empty machine-authored detached seed using `commit-tree`. It contains no user files and does not create or advance an owner branch. The source repository can remain without HEAD after both task completion and Apply.

Frozen `options.json` records `project`, `owned_worktree`, and `workspace_base_commit`; the controller's existing `workspace` remains the actual execution folder. `project-baseline.json` retains original fingerprints and selected paths. The existing event journal records preparation. Source-project single-active-pattern policy and host capacity apply before another task worktree is prepared. Advance reuses the actual retained task workspace. Cancellation and completion retain task work. Reuse setup selects the original project and exact model settings; it prepares another isolated task and does not silently copy unmerged previous task edits. Older runs without project metadata keep their existing workspace behavior.

## Checks

An explicit `verify` argv remains supported. With development `verify=null` or omitted, the harness's worker-selected mode requires the implementation actor to return a concrete check argv. The host executes it in the actual task workspace before independent review. Missing, malformed, or unlaunched checks fail concretely; a proposed command alone is not verification. The application accepts the frozen verification-mode marker and keeps exact saved custom models. Apply uses accepted host observations and retained process evidence, including in automatic mode.

## Review and explicit Apply

`Application.project_changes(run)` is read-only. Its response includes:

- Original `project`, actual `workspace`, and `owned_worktree`.
- `eligible`, `applied`, and a concrete `reason`.
- Substantive accepted worker `summary`, separate independent `review`, actual `verification`, and `test_instructions` (argv and project cwd).
- Changed `path`, `status`, `task_path`, `project_path`, and the reviewed `after` fingerprint for each selected source file.

The HTTP integration exposes GET `/api/runs/<id>/project-changes` and POST `/api/runs/<id>/apply` with exactly `{"confirm":true}`. Route authentication and browser interaction remain in the operator/session integration.

Apply requires a completed development controller, confirmed process cleanup, the accepted implementation's subject-specific independent passing review, successfully executed host checks with matching retained evidence, and the original recorded baseline. Each changed file must match the accepted implementation's before/after manifest, and the source file must still match its original baseline. Changes to ordinary files are supported, including additions, deletions, binary contents and mode changes. Changed symlinks, unsupported file types, source drift, conflicting additions, and task edits made after review are refused with both copies retained.

Apply changes only the selected reviewed files. Unrelated source edits, the source branch and staged index remain intact. It never commits, publishes or automatically merges. Source backups remain in a private sibling of the owned task workspace, outside run state. A retained `project-apply.json` receipt and event identify the result. Partial copy failures restore already-written files when those files still match the application writes; concurrent newer external edits are preserved. The failure receipt records restorations and restoration errors, with the backup path available for recovery. Source and reviewed task fingerprints are checked before mutation and again around file copying; this is not a transactional multi-file filesystem merge.

Task worktrees and backups are retained for review; no automatic deletion is introduced. Old runs without an owned task baseline cannot use Apply. If remediation's accepted manifest does not account for a file's complete change from the original project baseline, Apply refuses that file rather than treating unrelated earlier edits as reviewed. A manual review of the retained task files is then required.

## Focused verification

`env -u USER_PROVIDED_PASSWORD python -B -m unittest tests.programs.test_noetic_projects -v` uses temporary real Git repositories and real detached drivers/check subprocesses with a model-free actor fixture. It exercises new/open/invalid folders, naming, nested repositories, dirty/staged/untracked/ignored source preservation, unborn seeds, owned-worktree retention, cancellation/reuse, capacity, explicit and worker-selected verification, reviewed Apply, conflicts and partial-copy recovery. No real provider is contacted or source checkout branch/index committed.
