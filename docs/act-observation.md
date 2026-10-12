# Retained host act evidence

`scripts.noetic_act_observation.capture(run_dir, evidence_dir, step="work")`
freezes the evidence of one explicitly selected retained `work`, `verify`, or
`review` step. It reads `noetic_run` creation version 1 and maintained
`noetic_develop` programs (`development.change/v1`, `inquiry.reviewed/v1`).
It neither executes recorded argv nor runs tests, models, or shell commands.
It writes a new private archive outside the source run and uses disposable
private byte copies for SQLite parsing; it never opens the source DB in SQLite.

```python
from pathlib import Path
from scripts import noetic_act_observation as evidence

manifest = evidence.capture(Path("/selected/run"), Path("/private/new/archive"))
frozen_hash = evidence.digest(Path("/private/new/archive/manifest.json").read_bytes())
verified = evidence.revalidate(Path("/private/new/archive"), frozen_hash)
```

The caller retains the manifest SHA-256 externally. `revalidate(evidence_dir,
expected_manifest_sha256, current=False)` requires that frozen hash, checks every
retained file's hash and byte count, and reconstructs the run/selected occurrence
from archived events. It needs no original path. `current=True` additionally
compares the original event/content and missing-optional-file bindings. Equivalent
same-byte restoration is allowed; inode identity is used only to detect changes
during capture. Revalidation confers no execution authority or native standing.

The `noetic-act-observation/v1` manifest carries the source run path, projected run
identity/workspace/goal/state/review, selected step and exact argv, occurrence flag,
start/finish sequences, state/returncode/error/duration, required-file names,
missing optional artifacts, archive file hashes/sizes, limits, and limitations.
`events.json` retains ordered sequence/timestamp/kind and the original SQLite
`data` cell text as `data_json`, preserving recorded start/finish, program,
verification, genuine recorded session references, review and other metadata.
These retained event cells are an export, not a byte copy of the SQLite database.
Run/workspace/goal and any recorded agent/session/scope identities remain distinct;
no ordinal, effort, authorship or missing native identity is inferred.

Stdout/stderr are required for recorded steps and retained byte for byte, including
binary/non-UTF-8 output. Optional task/prompt/report/result, review, changes and
Telos-context files are copied only under their maintained known filenames.
Missing optional files remain explicit even when a recorded event references
them. No environment, credentials, process ownership sidecars, workspace file
contents or arbitrary referenced paths are collected. Recorded reports/prompts
can themselves contain sensitive content; the selected archive is owner-private
(0700 directory, 0600 files). Existing change evidence and its omissions are
retained without attributing changes to a worker.

An observed start followed by a finish establishes a **recorded occurred
execution**, including `failed`, `timed_out`, and `interrupted`. A launch failure
with finish/error but no start is captured as `occurred=false`; it must never be
reported as a completed native act. An unfinished selected step, missing required
bytes, inconsistent start/finish, or repeated step records are refused. Repeated
steps reuse log filenames, and the current recorder does not hash their bytes
per occurrence, so no selector can truthfully bind the overwritten files to an
earlier occurrence. The whole run can remain unfinished or fail verification
after successful selected work; run/review acceptance is never a prerequisite.

Capture compares two event/content snapshots and file identities to detect
source changes. Event reads use the existing read-only runtime API plus exact
SQLite event-cell export from a private disposable source-byte copy. Missing source state is not
created. WAL/shared-memory/active rollback journals and unsupported controller or
native-session program formats are explicitly refused. Archives support only
the maintained schemas, not a generic execution framework. Each file, event
export, serialized manifest and source DB read is limited to 16 MiB; retained
files plus the serialized manifest total at most 64 MiB. Capture serializes the
complete manifest and checks both archive limits before creating the destination;
revalidation includes its original serialized bytes in the total. Required
evidence over these bounds is unavailable and capture fails;
it is never truncated. Missing files, unsupported sources and unstable snapshots
raise an exception without manufacturing an occurrence.

Hashes bind archive bytes to the caller-frozen manifest; they do not establish
source authenticity against adversaries, exhaustive history, tool authorship,
desired success, native semantic standing, or permission to act. Operation 14
integration must separately freeze the native context/plan/step and correlate
the executing run with the later observing session. An accepted truthful
observation can describe unsuccessful real work.
