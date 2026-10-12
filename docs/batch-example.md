# Worked Batch Example

Use the installed `noetic` command in a disposable project workspace on POSIX,
with `python3` and your configured client (`opencode` or `pi`) on `PATH`.
The following three input files belong in that workspace. Task-file paths are
relative to the manifest; artifact and verification paths use the workspace.

`tasks/produce.md`:

```text
Create only batch-artifact.txt containing exactly "Hello from noetic.\n"
(one line ending in a newline, without quotation marks). Preserve other files.
Run the supplied verification. Do not commit, push, or change configuration.
```

`tasks/examine.md`:

```text
Perform a read-only inquiry into batch-artifact.txt in the workspace.
Read the actual file, report its exact content and whether it is one
newline-terminated line matching "Hello from noetic.\n". Cite the artifact
as evidence and report any mismatch. Do not modify workspace files, commit,
push, or change configuration. Do not infer correctness from an exit code.
```

`batch.json`:

```json
{
  "name": "Produce and examine a greeting",
  "tasks": [
    {
      "id": "produce",
      "program": "develop",
      "task": "tasks/produce.md",
      "depends_on": [],
      "verify": ["python3", "-c", "from pathlib import Path; import sys; sys.exit(0 if Path('batch-artifact.txt').read_bytes() == b'Hello from noetic.\\n' else 1)"]
    },
    {
      "id": "examine",
      "program": "inquire",
      "task": "tasks/examine.md",
      "depends_on": ["produce"]
    }
  ]
}
```

Replace the client/model placeholders with configured selections, then run from
the workspace. The required development `verify` array runs without an implicit
shell. Children execute sequentially; `examine` starts only after `produce` has
an accepted child journal with recorded review evidence.

```sh
noetic batch run ./batch.json --workspace "$PWD" \
  --client '<opencode-or-pi>' \
  --model '<work-model-id>' \
  --review-model '<review-model-id>'

# Use the directory printed as "Batch:" by run, including its UUID.
BATCH_DIR='/absolute/path/to/workspace/.runtime/batches/BATCH_UUID'
noetic batch status "$BATCH_DIR"
noetic batch resume "$BATCH_DIR"
```

Resume skips accepted children with no outstanding Telos error. It executes
absent children only when their dependencies are accepted. Existing nonaccepted
or ambiguous children hold the batch for explicit disposition, not automatic
retry. Inspect the reported child directory with `noetic status CHILD_DIR` and
`noetic events CHILD_DIR`; preserve its evidence.

Status reflects recorded observations, not live process health. Batch `complete`
summarizes accepted children, not completion of the master goal. Neither an exit
code nor the byte check establishes general semantic truth; independent review
and the inquiry's cited observations remain distinct evidence. See
[Batch Workflows](batch-workflows.md) for frozen-input and recovery details.
