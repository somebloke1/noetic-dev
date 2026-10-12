# Optional Local Support

These stdlib-only modules provide explicit local support, not primary agent
replacement, semantic judgment, independent QA, or controller/Telos authority.
They do not start services, install dependencies, inspect subscription state,
read credential files, or alter model hosting. Installed `noetic local` and
`noetic semantic` commands and the application's Memory controls call these
modules; both CLI integration and application GUI have scoped independent acceptance.

## Entry Points

Use installed `noetic` with the gateway credential already in the
`LITELLM_API_KEY` environment variable. Never put the credential on a command
line or in this repository.

```bash
noetic local diagnose embedding --config /path/to/config/local-models.json
noetic local diagnose text --text "Summarize: this is a nonsecret diagnostic fixture."
noetic local summary /path/to/run --config /path/to/config/local-models.json
noetic local summary /path/to/run --save --max-input-bytes 12000
noetic semantic search "How was this problem addressed?" --runs-dir /path/to/runs --config /path/to/config/local-models.json --limit 5 --json
noetic semantic index --runs-dir /path/to/runs --db /path/to/derived.sqlite3
noetic semantic index --runs-dir /path/to/runs --db /path/to/derived.sqlite3 --reindex
```

From the source checkout, replace `noetic` with `python3 -m scripts.noetic`.
See [model startup and diagnostics](local-models.md#startup-and-checks) for the
existing services. All operations output JSON, including controlled failures (exit code 1).
Semantic search always refreshes first. Failure stops the operation: no silent
lexical fallback, retries, service repair, or stale-result success. The existing
`noetic_memory` lexical search remains separate and service-free. Diagnostics
make actual calls, but embedding diagnostics output dimensions/norm, not vectors.

Python integration points for the main CLI/UI are `load_settings`,
`LocalClient`, `summarize_run`, `collect_runs`, `index_runs`, and `search`.
For semantic calls, pass a dedicated SQLite connection, refresh using
`index_runs(connection, runs_dir, client)` before `search(connection, query,
client, limit)`. Never pass a canonical journal/controller database as the cache.
The CLI rejects databases containing unrelated tables.

## Configuration And Hosting

Precedence is explicit arguments, then `NOETIC_LOCAL_*` environment, then the
optional `--config` JSON (or `NOETIC_LOCAL_CONFIG`), then built-in defaults.
No manifest is implicitly read. The supplied manifest's `access.base_url` is
honored; to use loopback with that manifest, pass `--base-url
http://127.0.0.1:3333/v1`.

| Setting | Default | Override |
| --- | --- | --- |
| Gateway | `http://127.0.0.1:3333/v1` | `--base-url`, `NOETIC_LOCAL_BASE_URL`, `access.base_url` |
| Credential environment name | `LITELLM_API_KEY` | `--api-key-env`, `NOETIC_LOCAL_API_KEY_ENV`, `access.api_key_env` |
| Supporting text | `qwen3.6-a3b` | `--text-model`, `NOETIC_LOCAL_TEXT_MODEL`, `inference.model` |
| Embeddings | `noetic-snowflake-embed` | `--embedding-model`, `NOETIC_LOCAL_EMBEDDING_MODEL`, `embedding.model` |
| Dimensions | 1024 | `--dimensions`, `NOETIC_LOCAL_DIMENSIONS`, `embedding.dimensions` |
| Timeout per request | 60 seconds, maximum 120 | `--timeout`, `NOETIC_LOCAL_TIMEOUT`, `client.timeout` |
| Embedding batch size | 2, maximum 16 | `--batch-size`, `NOETIC_LOCAL_BATCH_SIZE`, `embedding.initial_recommended_batch_size` |
| Text output tokens | 512, maximum 2048 | `--max-tokens`, `NOETIC_LOCAL_MAX_TOKENS`, `client.max_tokens` |
| Chunk bytes | 1024, maximum 1024 | `--chunk-bytes`, `NOETIC_LOCAL_CHUNK_BYTES`, `embedding.chunk_bytes` |

Qwen uses `/chat/completions`, temperature zero, bounded `max_tokens`, and
`chat_template_kwargs.enable_thinking=false` on every request. Snowflake uses
`/embeddings`. The existing CPU-persistent Ollama alias supplies 1024 dimensions
with an 8192-token limit; persistent CPU policy does not mean permanently
resident weights. See [hosting details](local-models.md). The two existing
backends remain independently operated; supporting summaries do not use the
embedder, and retrieval does not use Qwen. No other service or framework is added.
HTTP errors expose status only, never raw bodies; credentials come only from the
named environment variable. Local requests bypass environment HTTP proxies and
refuse redirects rather than forward gateway credentials to another location.

## Source Selection

For a run with `controller.sqlite3`, canonical SQLite state is read directly,
not the potentially stale JSON/Markdown exports. Sources are the current
`accepted.*`/`effective.*` slot bindings, QA artifacts naming those exact
subjects, the purpose, and external inputs. Returned/invalidated outputs,
unaccepted work, old QA subjects, partial returns, and the full event history
are not indexed as current. Controller status and current reservation are
reported separately from artifact claims. Each source retains its path,
artifact ID/type/digest, recording event ID, run state and `scope: current`.
Current means currently bound within that run, not globally current knowledge;
a completed run's bindings still describe that run's past work.

Legacy runs reuse `noetic_memory.index_runs` in an in-memory FTS index strictly
as a source collector, not as a retrieval fallback. Its goal, work, review, and
retained review evidence are labeled with source paths/event sequences. Legacy
collection scans the runs parent, even for a single-run summary, and filters
the resulting sources to the requested run. It has no typed acceptance slots;
`current` means the available reports and retained review, not acceptance of
their claims. Unreadable legacy sources stop refresh rather than silently
produce incomplete success. A corrupt controller never falls back to exports.

## Summaries

The summary prompt contains a bounded snapshot, never whole historical state.
It prioritizes state, purpose, current outputs and their QA. Defaults are 12000
UTF-8 bytes of serialized input, at most 32 sources, and at most 2048 text bytes
per source; `--max-input-bytes` permits 2048 through 32768. JSON escaping counts
toward the bound. Coverage reports eligible/included/omitted sources, truncated
sources, excluded controller artifacts, eligible/included text bytes, and actual
prompt bytes. The model sees coverage and source IDs. The returned source
manifest has exact text hashes and byte coverage; model-written citations are
not independently verified. Output token truncation is reported separately.

The result is labeled `model_generated: true`, `authoritative: false`, and
`advances_state: false`. It is an observation at the cited controller version
or journal sequence, not necessarily the latest state after a concurrent run
advances. Content can be mistaken or omit important nuance. It must not become
a phase artifact, QA input authority, completion judgment, or Telos status.

Without `--save`, no run file or event is changed. With it, only `summary.json`
is written and, if an observation `events.sqlite3` already exists, a
`local.summary.observed` event records its path/hash/model and snapshot source
ID. `observation_recorded` is a return-only receipt, not part of the saved file.
No controller event, slot, status, or Telos state is modified. If observation
append fails, the returned result explicitly says the summary was saved without
the observation. Neither source collector reads the saved summary as evidence.

## Derived Semantic Cache

The default cache is `.semantic.sqlite3` under the runs directory; `--db` selects
a separate disposable path. Nothing here is a second canonical history.
SQLite stores current chunk/source metadata and deduplicated text/vector rows.
Each refresh removes stale/deleted chunks and unreferenced vectors, updates state
metadata without re-embedding unchanged text, and embeds only new unique chunk
text. Identical chunks share a vector while retaining distinct source identities.
Unchanged documents make no embedding requests; search queries are embedded once
per search, not persisted. Similarity is cosine after finite, correct-dimension,
nonzero-norm validation and client L2 normalization. Cached vectors must already
be normalized. Results carry source IDs, byte offsets, ranked snippets and scores;
scores are relevance, not probabilities, truth, or evidence quality.

The [official Snowflake v2 model card](https://huggingface.co/Snowflake/snowflake-arctic-embed-l-v2.0#using-huggingface-transformers)
specifies the literal query-only prefix `query: `, no document prefix, CLS pooling,
and L2 normalization. Chunking is contiguous, UTF-8 codepoint-safe, without
overlap. The byte guard reserves 32 tokens and conservatively budgets six tokens
per input byte for normalization expansion, capped at 1024 bytes. This is not exact tokenizer counting or a
claim to support arbitrary new tokenizers; it deliberately stays well below
Snowflake's 8192-token limit. Query prefixes count against the byte limit;
oversized queries fail rather than silently truncate.

The cache identity includes gateway/route, model ID, source model artifact layer,
dimensions, backend-owned tokenizer and pooling declarations, normalization,
preprocessing/serialization version, query/document prefixes, chunking and input
budgets, collector version, runs root and scope. It never includes the credential.
Changes refuse mixing until explicit `index --reindex`; rebuild failure leaves
the old cache intact but does not return it as a refreshed result.

Additional identity fields are configurable via `embedding.source_model`,
`source_model_layer_sha256`, `tokenizer`, `pooling`, `preprocessing_version`, and
`max_input_tokens`, or their `NOETIC_LOCAL_` uppercase equivalents. These are
deployment declarations, not backend attestation. When changing the model behind
an alias or its tokenizer/pooling pipeline, update this metadata and reindex.
Changing an ID alone is not sufficient to describe a different model faithfully.
Unannounced backend changes behind an unchanged identity cannot be detected.

## Implementation Checks

```bash
python -m unittest discover -s tests/programs -p test_local_support.py -v
```

The tests use a fake HTTP server and deterministic vectors for batching,
timeouts/errors, dimension/nonfinite/norm rejection, identity mismatch/reindex,
incremental caching/deduplication, updates/deletions, current artifact selection,
source attribution, cognitive return invalidation, and summary coverage without
authority mutation. These are implementation tests, not independent QA.

An explicit fixture-only live trial is available to the owner, not run by unit
tests. It creates a temporary three-document legacy corpus, performs one search,
checks a no-embedding cache refresh, and makes exactly one Qwen summary request
over a separate nonsecret test-authored controller snapshot. It changes no real
run state and makes no service changes. A failure stops without retries.

```bash
PYTHONPATH=. python tests/programs/test_local_support.py --live-trial config/local-models.json
```

This tiny trial measures functional latency and provides an inspectable ranking
and summary. It does not establish retrieval quality, summary faithfulness,
bulk throughput, long-context behavior, or authoritative semantic judgment.

### Recorded Fixture Trial

Implementation trial on 2026-09-07 at approximately 17:20 UTC, after the fake-server
unit tests passed, through the existing loopback LiteLLM gateway:

| Check | Observation |
| --- | --- |
| Corpus | Three tiny temporary legacy documents: bicycle punctures, tomato seedlings, bread dough |
| Embedding and one search | 0.771 seconds total, two document batch requests plus one query request; validated 1024-dimensional finite normalized vectors |
| Query | `How do I fix a flat bicycle tire?` |
| Ranking | Bicycle first (cosine 0.5191), bread second (0.0816), tomato third (0.0398) |
| Unchanged refresh | Zero document embedding requests |
| Qwen summary | Exactly one request, 3.051 seconds; 704 prompt tokens, 355 completion tokens; normal stop, no output truncation |
| Summary input | Five sources, 669 source-text bytes, 2009 serialized prompt bytes; no omitted/truncated sources |
| Summary behavior | Named the recorded active abstract-design reservation, cited supplied IDs, and distinguished the fixture QA report from independent QA evidence |
| Mutation | Fixture controller unchanged; no summary saved; temporary corpus removed; no actual run semantic state modified |

The source ordering was subsequently made explicitly purpose-first, and the
maximum embedding input byte guard was reduced from 2040 to 1024 bytes with
more normalization headroom. The tiny trial inputs fit both guards. Both changes
were covered by the unit tests before separate independent QA. These timings are
one local functional sample, not cold-start, concurrency, or performance claims.

Independent local-support QA subsequently accepted the unit, including CLI
dispatch, fake-transport checks, one tiny real embedding/search corpus and one
Qwen summary. Application QA separately checked GUI routing with mock support
services. Later real operations at the installed production GUI
`http://127.0.0.1:8765/` exercised Snowflake semantic search over 18 real runs
and one Qwen summary of a real completed development run, not mock responses.
The warm index reused 113 existing text vectors (121 chunks); the query still
used embeddings, not FTS or lexical fallback. Its 0.373-second GUI completion
does not establish cold first-index latency. The 3.844-second summary included
7 of 11 eligible sources with 3 truncated sources and explicit coverage labels.
Checked controller/journal/Telos state stayed unchanged; the summary was not saved.
These bounded operations establish working support, not exhaustive recall,
summary faithfulness, verified model citations, or ongoing service availability.
