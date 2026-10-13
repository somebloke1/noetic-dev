# Bounded model request batches

`scripts/tools/model_request_batch.py` reuses the team's working standard-library
`urllib` and thread-pool pattern. It accepts independent, nonstreaming
chat-completions requests, captures exact input and raw response bytes, and
produces concise receipts. It makes HTTP model requests only; native collaboration
messages continue through serial direct tools.

The input is a nonempty JSON array with explicit local request IDs:

```json
[
  {
    "id": "linguist/H005-H007/minimal",
    "metadata": {"source_path": "/owned/evidence.json", "source_sha256": "EXACT_HASH"},
    "request": {
      "model": "nemotron-3.5-lightning-q8",
      "messages": [{"role": "user", "content": "A bounded task with the relevant source and required output."}],
      "temperature": 0,
      "max_tokens": 256,
      "stream": false
    }
  }
]
```

```sh
python3 scripts/tools/model_request_batch.py \
  --requests /owned/requests.json \
  --endpoint http://172.22.10.160:8642/v1/chat/completions \
  --output /owned/new-request-packet \
  --concurrency 2 --timeout 45
```

Use a new nonexistent output directory; its parent must exist. Duplicate request
IDs, unsupported streaming and invalid concurrency are refused before network
activity. Each `request` object is posted without model or prompt alteration.
Caller metadata stays local; the helper does not verify or forward source paths.
All original input bytes are retained in `requests.input.json`. Request IDs retain
their full names/namespaces in receipts; filenames use the batch ordinal and an
ID digest. Those are local identifiers, not framework ordinals or native IDs.

Existing response artifacts can be annotated without another model request:

```sh
python3 scripts/tools/model_request_batch.py \
  --view-response /owned/existing.response.json --output /owned/new-derived-view
```

This mode copies the original bytes and records their source path/hash, local
view time, response-reported fields and the same qualified derived view. It
does not infer the original request identity, transport success or elapsed time.
Invalid response bytes are retained with an explicit failure and exit 1. No
network activity occurs.

Default concurrency is two, with an explicit range of 1–32. The access card's
32-slot capacity is reported service configuration, not measured 32-way
throughput. Choose independent tasks that benefit from parallel inquiry. A model
answer remains a candidate under its work owner's judgment and existing QA.
No retries, service changes, tool execution or product-session population occur.
Failures retain their completed siblings and available raw error bodies. Exit 1
reports transport/response failures; semantic correctness is never an exit-code
claim. A write failure can leave an owned partial packet for inspection.

Each request writes the exact posted JSON, original response bytes, their hashes
and a receipt with local timing, provider response identity, finish reason and
the response's untouched `usage`. Missing usage is `null`, never a guessed zero.
No token estimates are substituted for provider-reported counts. Request elapsed
time covers the HTTP attempt/read; batch elapsed time also includes scheduling
and local processing. These are different measurements and provide no cache or
speedup baseline. Inference settings and token budgets remain caller-supplied.

An optional derived view addresses the observed literal `</think>` prefix.
Only that exact leading boundary plus immediately following CR/LF characters
is removed. Receipts retain the untouched original content and the exact removed
prefix/character span. Nonleading occurrences and all remaining characters stay
unchanged. `json_parse: parsed` records acceptance by the local JSON parser.
Its semantic standing remains `unassessed candidate`; it may still omit
limits, invent constraints or contain wrong expected values. Tool calls in a
response remain raw data and are never executed.

Stdout summarizes IDs, receipt paths, transport status, local times and reported
usage; full prompts/responses stay in artifacts. Native transport receipts and
their authority remain separate from these local model records. Use supplied
texts that belong in the request and durable packet; no environment credentials
or authentication headers are collected.

The initial evidence for this helper is the linguist's working two-request
script and the fixer's/validator's observed leading-boundary and semantic-drift
cases. These observations support preserving originals and transformations;
they do not establish the model's accuracy on future tasks.

```sh
python3 -m unittest discover -s tests/tools -p test_model_request_batch.py -v
```

Tests use only an owned local mock HTTP server, with synthetic usage values;
they never call a provider, GPU model, browser or live user context.
