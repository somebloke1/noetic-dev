# Explicit scope recall

`scripts.noetic_recall` collects derived investigation sources from declared
application stores. It resolves the canonical namespace, effort membership,
parent relations and exact historical selectors before reading eligible text.
A shared directory never establishes shared effort ownership. Explicit
`namespace_path` takes precedence over inherited installation environment.
Collection uses read-only SQLite connections and never creates/adopts canonical
records, starts models, or rewrites native journals.

## Available collection

| Source | Included material | Boundary |
|---|---|---|
| Canonical namespace | Complete paginated selected history, including retained correlated controller records | Historical observations preserve source references and occurrence times. Recorded artifact content remains its original type and occurrence; it is not a current semantic claim. |
| Developer Registry | Every selected journal page; requested prompts/steering/follow-ups, final `message_end` text and retained failure observations | Streaming starts/updates and repeated RPC transcript responses are excluded. Requests remain distinct from retained messages. Native context files are referenced, not ingested. |
| Structured executions | Actual `noetic_disciplines.correspondence` ownership plus current native controller bindings and their QA references | Exact sessions require an exact canonical participant target. Controller projections are labelled `current-bindings-only`; historical canonical observations remain separately labelled. Partial flags and native artifact types are retained. |
| Unassigned legacy | Native controller/legacy artifacts and unadopted developer journals | Only explicit application scope includes them, with `ownership: unassigned-legacy`, absent effort/target and original source references. No inferred adoption or delegation. |

A bare ordinal investigates its validated position and descendants across retained
sessions. Exact session scope includes one ordinal and both retained selectors;
matching selector numbers at descendants are excluded. Application scope includes
all declared canonical branches without requiring effort selection.

Responses include the declared selection, namespace/source identity, collection
time, source content hashes, diagnostics and coverage. A corrupt namespace or a missing namespace for effort/ordinal/exact-session
selection is an unavailable error. Explicit application selection before namespace
registration collects only source-qualified unassigned legacy records, reports
`canonical: not-registered` and a namespace identity with `id: null`, and creates
no namespace. This identity implies no root `0` or past global ownership.
Records claiming assigned ownership while their namespace is absent are excluded
with explicit partial diagnostics. Missing/corrupt stores and incomplete correspondence
produce partial coverage and explicit diagnostics; they never trigger a foreign
or legacy fallback. Canonical history may remain available when its referenced
native store cannot be read. Native context coverage is explicitly references
only. Search cannot establish comprehensive native history, current process
state, cognitive validity or native semantic standing.

## Consumer API

```python
from scripts import noetic_recall, noetic_memory, noetic_semantic

collection = noetic_recall.collect(
    namespace_path=namespace_path, sessions_home=sessions_home,
    runs_dir=runs_dir,
    selection={"kind": "effort", "effort_root": "0.0"},
)
index = noetic_memory.index_scoped(connection, collection, reindex=False)
result = noetic_memory.search_scoped(
    connection, query, identity=collection["identity"], limit=20,
)

# Explicit optional embedding service; report index diagnostics alongside hits.
index = noetic_semantic.index_scoped(
    semantic_connection, collection, client, reindex=False,
)
hits = noetic_semantic.search(
    semantic_connection, query, client, limit=20,
    identity=collection["identity"],
)
```

Selections are `{kind: application}`, `{kind: effort, effort_root: ...}`,
`{kind: ordinal, ordinal: ..., effort_root?: ...}` or
`{kind: session, ordinal: ..., instantiation: ..., session: ..., effort_root?: ...}`.
Exact selectors are positive integers. APIs receiving a collection consume its
already resolved sources; consumers must obtain that collection from this
collector and display its coverage/diagnostics with their results.

Both scoped indexes compare the namespace ID/path, exact selection, source roots
and collector semantics. Semantic identity additionally retains the existing
embedding model/layer/tokenizer/preprocessing/chunk identity. A different identity
requires explicit `reindex=True` or a separate cache. Scoped semantic search
requires its expected collection identity before even embedding the query.
Chunk byte offsets address the extracted/serialized UTF-8 source text identified
by `source_text_sha256`; they are not raw SQLite file offsets. Original journal
sequences and artifact references identify the native record.
Embedding failure preserves the prior cache; no implicit lexical substitution
occurs. Lexical investigation works independently of models, GPU or providers.

## Module CLI

Supply actual installation-owned paths; `sessions-home` is the parent of
`developer-sessions/sessions.sqlite3`.

```sh
python -m scripts.noetic_recall --namespace-path "$NAMESPACE" \
  --sessions-home "$SESSION_HOME" --runs-dir "$RUNS" \
  --scope application

python -m scripts.noetic_memory search "retained question" \
  --namespace-path "$NAMESPACE" --sessions-home "$SESSION_HOME" \
  --runs-dir "$RUNS" --scope effort --effort-root 0.0

python -m scripts.noetic_memory search "earlier findings" \
  --namespace-path "$NAMESPACE" --sessions-home "$SESSION_HOME" \
  --runs-dir "$RUNS" --scope session --ordinal 0.0.0 \
  --instantiation 1 --session 1

python -m scripts.noetic_semantic index \
  --namespace-path "$NAMESPACE" --sessions-home "$SESSION_HOME" \
  --runs-dir "$RUNS" --scope effort --effort-root 0.0 \
  --db "$SEMANTIC_CACHE" --config "$LOCAL_CONFIG"
```

Scoped CLI calls use an in-memory disposable cache unless `--db` is explicit.
Changed identities on persistent caches require `index --reindex`; lexical search
also permits explicit `--reindex`. `noetic_memory` and `noetic_semantic` calls
without `--scope` preserve the prior run-only compatibility behavior and embedding
identity. That compatibility collector is service-wide current controller/legacy
collection, has no effort filtering, and omits developer journals. Application
and interface integration is a separate consumer unit.

Every hit is derived source evidence. Similarity, FTS relevance, controller
acceptance and QA retain their distinct meanings. This unit supplies no Opermem
typed context, standing transitions, deposition, propagation or whole-residue
contract, and cannot replace those native operations.

## Bounded verification

`tests/programs/test_noetic_recall.py` uses disposable canonical SQLite stores,
actual Registry APIs, maintained structured correspondence and model-free
controller artifacts. It exercises same-folder A/B separation, reopened failed
history, exact descendant exclusions, more than 1,100 journal events, source
references, legacy application history, missing/corrupt stores and incomplete
mapping. A local fake HTTP endpoint observes embedding request bodies, cache
segregation/reindex and UTF-8 cuts without loading a model or contacting a
provider. Existing lexical/current-controller and embedding compatibility tests
remain separate regression evidence. These checks establish a derived recall
unit, not useful cognitive value or complete application delivery.
