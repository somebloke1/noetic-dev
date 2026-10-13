# Static narrative document tools

Python 3 standard library; Linux/macOS `fcntl` locking. One self-contained HTML
file stores the readable transcript and its JSON source model. No JavaScript,
remote assets, or server is needed to read it. Run from the repository root:

```sh
TOOL=scripts/tools/narrative_document.py
DOC=/absolute/path/conversation.html
python3 "$TOOL" init "$DOC" --title 'Conversation transcript'
python3 "$TOOL" list "$DOC"
python3 "$TOOL" show "$DOC" entry-001
python3 "$TOOL" insert "$DOC" --payload entry.json
python3 "$TOOL" insert "$DOC" --before entry-001 --payload entry.json
python3 "$TOOL" insert "$DOC" --after entry-001 --payload entry.json
python3 "$TOOL" update "$DOC" entry-001 --payload patch.json --expected-revision 3
python3 "$TOOL" delete "$DOC" entry-001 --expected-revision 4
python3 "$TOOL" apply "$DOC" --payload operations.json --expected-revision 5
```

`init` refuses to overwrite. Parent directories must exist. Mutation receipts,
lists, and individual entries are JSON on stdout; errors go to stderr with exit
status 1. `--expected-revision` is optional on mutations after initialization.
Use the revision returned by `list`, `show`, or the previous mutation.

An insertion payload (`entry.json`) is an object:

```json
{
  "id": "entry-001",
  "utc": "2026-10-12T22:42:00Z",
  "sender": "agent-a",
  "recipient": "agent-b",
  "source": "exact-copy routing record",
  "original": "Exact original text, including whitespace.\n",
  "translation": "Readable translation of that text.",
  "narrative": "Context, clearly distinguished from the original.",
  "metadata": {"source_path": "/path/to/source", "line": "12", "trace_id": "trace-1"}
}
```

All fields are strings except `metadata`, a string-to-string map. Missing identity
generates a UUID. Other missing fields default to empty text, or `unknown` for
UTC, sender, recipient, and source. Unknown timestamps are represented explicitly;
the tool does not infer times or translate messages. `original` is retained exactly
in embedded JSON and displayed in an expandable original-message section. HTML
characters are escaped; payloads never inject markup.

IDs match `[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}`; the model-script ID is reserved.
IDs are unique for the document's lifetime, including deleted entries. Each article
has `id="ENTRY_ID"`, `data-entry-id="ENTRY_ID"`, and `data-seq="FRACTION"`.
Identity is separate from order: insertion uses the midpoint between adjacent
exact rational keys or an edge key plus/minus one. Existing keys and IDs stay
unchanged. Default insertion appends. Ordering follows these keys, so import in
chronological order or provide an explicit anchor.

An update payload (`patch.json`) contains just the changed content fields. An
update preserves identity and order. Add `--before OTHER_ID` or `--after OTHER_ID`
to explicitly move it; self-anchors are rejected. Changed prior entries remain in
the embedded audit; deletion also retains the entire entry in tombstones.

Batch payload (`operations.json`):

```json
[
  {"op": "meta", "patch": {"coverage": "All exact copied messages", "gaps": "Encrypted native bodies unavailable"}},
  {"op": "insert", "entry": {"id": "new-001", "utc": "unknown", "original": "Exact message"}},
  {"op": "update", "id": "entry-001", "patch": {"translation": "Revised translation"}},
  {"op": "insert", "before": "new-001", "entry": {"id": "new-000", "original": "Earlier message"}},
  {"op": "delete", "id": "entry-001"}
]
```

Batches are ordered operations and commit atomically once, with one revision
increment. A failed operation leaves the HTML unchanged. `meta` accepts `title`,
`coverage`, and `gaps`, displayed in the header. Sidecar `DOC.lock` serializes
cooperating writers; do not delete it while writers are active. Writes use a
temporary sibling followed by atomic replacement. Read-only documents are refused.
An external generator must use the same lock or avoid writing concurrently.

Embedded model contract: one exact
`<script id="narrative-document-model" type="application/json">` marker containing
`{"schema":1,"revision":0,"updated_utc":"...","document":{"title":"..."},"entries":[],"audit":[],"tombstones":[]}`.
Entries have all seven content fields above plus `id` and canonical `seq` strings;
`metadata` is optional. JSON escapes every `<` as `\u003c` to keep closing-script
text inert. The Python module exposes `render(model)` and `read_document(path)`
for a compatible generator. Preserve this model when editing; visible HTML alone
does not change the source model.

Verification:

```sh
python3 -m unittest discover -s tests/tools -p test_narrative_document.py -v
```
