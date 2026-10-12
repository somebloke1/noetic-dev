# Local Model Hosting

Verified on `o11-ubuntu`, 2026-09-07. The user explicitly authorized working
local inference and embedding support. These are distinct capabilities, not
replacements for every primary agent or strong semantic role.

`config/local-models.json` records the deployed hosting contract and measured
checks. Installed `noetic local` and `noetic semantic` commands load its
client-facing settings explicitly with `--config`; the GUI also exposes real
semantic search and Qwen summaries. They do not configure services or replace
primary models. See [local capabilities](local-capabilities.md).
No global Pi/OpenCode models or existing model-policy files were changed.

## Responsibilities

| Capability | Model | Intended responsibility |
| --- | --- | --- |
| Optional local inference | `qwen3.6-a3b` | Text inference, supporting session summaries, and available vision support. Not a guaranteed substitute for strong reasoning, semantic judgment, or independent authoritative review. |
| Local embeddings | `noetic-snowflake-embed` | Snowflake Arctic vectors for semantic indexing, retrieval, and context ranking. Does not generate summaries or judge evidence. |
| ASR | None required by this unit | Speech transcription is separate. `qwen-asr.service` remains disabled/inactive. |

Qwen's supporting-summary role is grounded in the donor noetic-pi
`packages/session-search/src/summarizer.ts`; its embedding client is
`packages/session-search/src/embedder.ts`. Those adapters still have legacy
direct endpoints, and the summarizer uses a stale `qwen3.5` request name. They
are not wired or migrated by this hosting change.

The current `scripts/noetic_memory.py` remains a service-free SQLite FTS5
lexical index, as documented in `session-memory.md`. A healthy embedder does
not make that index semantic. Actual CPU-vector semantic retrieval and supporting
summaries are integrated through separate modules described in [local capabilities](local-capabilities.md),
not an automatic distiller or authority-bearing controller input.
Consumers must explicitly select/configure these support routes. The user's
new local-support authorization is not vetoed by the older restricted
generative-model policy; it does not authorize changing primary agent models.

## Access

Preferred client base URL: `http://172.22.10.160:3333/v1`, through LiteLLM with
the existing `LITELLM_API_KEY`. This address is local to the host. Loopback
`http://127.0.0.1:3333/v1` was used for implementation verification.

| Operation | Model field | Path | Backend |
| --- | --- | --- | --- |
| Text / vision chat | `qwen3.6-a3b` | `/chat/completions` | llama.cpp, `127.0.0.1:8742/v1` |
| Embeddings | `noetic-snowflake-embed` | `/embeddings` | Ollama, `127.0.0.1:11434`, alias `noetic-snowflake-embed:latest` |

The Qwen proxy route was already correct and passed a real authenticated
completion. The only proxy config addition was the noetic CPU embedding
route. Existing `snowflake-arctic-embed2` and all other routes/authentication
settings were preserved. Direct backend access is for host diagnostics here,
not a requirement for portable clients. No credentials belong in this file
or the JSON manifest; do not dump installed units or service environments.

## Inference Loading

System unit `/etc/systemd/system/qwen-it.service` runs
`/usr/local/bin/llama-server` as `llm-svc`. It is now enabled at boot to keep
the local inference service available without a manual post-reboot start.

Both model files were already installed under:

```text
/home/dgk/.cache/huggingface/hub/models--bartowski--Qwen_Qwen3.6-35B-A3B-GGUF/
```

- `current_model.gguf` resolves to `Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf`,
  22,285,080,192 bytes. A3B means active parameters, not a 3B-sized weight set.
- `mmproj-Qwen_Qwen3.6-35B-A3B-f16.gguf`, 899,283,296 bytes, is the vision
  projector. Successful loading was logged; image inference was not tested.

The installed configuration was retained:

```text
CUDA_VISIBLE_DEVICES=1,2
--n-gpu-layers 99 --tensor-split 4,4
--ctx-size 393216 --parallel 6
--cache-type-k q8_0 --cache-type-v q8_0 --flash-attn on
--batch-size 512 --ubatch-size 512 --threads 5
--image-min-tokens 1024
```

The total context is split into **six 65,536-token slots**. Input, output,
and image use must fit one slot; this is not 393,216 tokens per request.
Six advertised slots do not establish throughput for six full-context jobs.
Start supporting summarization conservatively, with one request at a time,
bounded output, and chunking for inputs that exceed the slot budget.

The server retains reasoning on with unlimited reasoning budget. The short
functional check explicitly used `chat_template_kwargs.enable_thinking=false`,
temperature zero, and `max_tokens=128`. Choose request-level output/reasoning
budgets for actual summary jobs rather than assuming this short probe proves
their latency or quality. The installed `--no-cache-prompt` flag also does
not mean zero host caching: startup logs report an 8,192 MiB RAM prompt cache
and context checkpoints. No caching settings were changed.

The host has two 24 GiB RTX 3090s with NV4 connectivity. They were both
recognized before repair. After loading and the checks, total GPU use was
15,082 / 14,280 MiB, with 9,045 / 9,847 MiB free. Only llama-server appeared
as a compute process. These are snapshots, not peak-memory guarantees.
The 1660 SUPER remains the display GPU. About 44 GiB system RAM was available
at the final sample; 7.3 GiB swap was in use, so neither startup nor these
measurements establish a no-paging guarantee.

The reproduced failure was filesystem traversal, not missing weights or
out-of-memory: `/home/dgk/.cache` had `user:llm-svc:--x` masked by `mask::---`.
The owner applied only:

```bash
setfacl -n -m m::--x /home/dgk/.cache
```

All other ACL entries, including `group::---` and `other::---`, were preserved.
The existing restart loop loaded the model/projector in about 36 seconds;
no Qwen restart or launch-argument edit was needed. The old restart count
remained 173 while its PID and healthy state stayed stable. The tracked
host unit differs from the installed one; do not overwrite it wholesale.

## CPU Embeddings

Ollama stays GPU-capable for other users/models. Its system unit and model
store remain `/etc/systemd/system/ollama.service` and
`/usr/share/ollama/.ollama/models`. Only a new noetic-owned alias was created:

```dockerfile
FROM snowflake-arctic-embed2:latest
PARAMETER num_gpu 0
PARAMETER num_ctx 8192
```

This reuses the existing 566.7M-parameter F16 Snowflake model, with
1,024-dimensional vectors and an 8,192-token input limit. The weight layer is:

```text
sha256:8c625c9569c3c799f5f9595b5a141f91d224233055608189d66746347c14e613
```

CPU placement is persisted in the alias manifest, not merely requested by a
startup warmup. It survived an explicit unload/reload check with no placement
options in the embedding request. The proxy supplies `keep_alive: 4h` and
`truncate: false`; callers should chunk/reject oversized inputs rather than
silently truncate. Start with two-input batches, the tested batch size;
long-input and larger-batch performance are not measured here.

The alias loads on demand and expires after idle keep-alive. Persistent CPU
policy does not mean permanently resident weights. No Ollama restart, global
GPU disable, or new preload hook was needed. The old catalog's CPU warmup of
`local-embedder` remains unchanged. Existing callers of raw Snowflake or other
aliases can still load onto GPUs; use the noetic route to obtain this CPU
default. Callers should not override its placement parameters.

Keep embedding identity with an index: source artifact, dimensions,
tokenization, preprocessing, pooling, and normalization. Alias spelling or
CPU placement alone need not require rebuilding when that identity is
unchanged. A different model, dimension, or embedding pipeline requires
re-embedding/rebuilding, even if two models have equal dimensions. Never mix
Snowflake's vectors with GTE ModernBERT's 768-dimensional vectors. The latter
remains a separate healthy Goose user service on port 8091.

## Startup And Checks

1. Ensure the existing model paths are accessible to `llm-svc` and both
   3090s are available. Qwen and Ollama are independent backends and may start
   in parallel; an embedding operation does not require Qwen readiness.
2. Keep `qwen-it.service`, `ollama.service`, and `litellm.service` enabled.
   Wait for the backend needed by each operation, not just proxy liveness.
   The Qwen boot-enable change is installed but an actual reboot was not tested.
3. The noetic embedding alias persists on disk and loads on its first request.
   A warmup is optional; it must not be mistaken for the CPU-placement policy.
4. Leave `qwen-asr.service` disabled/inactive unless a separate transcription
   requirement authorizes its GPU allocation. No ASR startup is part of this unit.

Non-inference checks:

```bash
systemctl show qwen-it.service ollama.service litellm.service qwen-asr.service \
  -p Id -p ActiveState -p SubState -p UnitFileState -p MainPID -p NRestarts
getfacl -p /home/dgk/.cache
curl --noproxy '*' --max-time 5 -fsS http://127.0.0.1:8742/health
curl --noproxy '*' --max-time 5 -fsS http://127.0.0.1:11434/api/ps
curl --noproxy '*' --max-time 5 -fsS http://127.0.0.1:3333/health/liveliness
OLLAMA_HOST=http://127.0.0.1:11434 ollama show noetic-snowflake-embed --parameters
nvidia-smi --query-gpu=index,name,memory.used,memory.free --format=csv
```

If these existing services are stopped, an authorized host operator can use
`sudo systemctl start qwen-it.service ollama.service litellm.service`; this is not
an installer or a reason to restart healthy services. For an explicit real client
check, use `noetic local diagnose embedding --config /path/to/config/local-models.json`
or `noetic local diagnose text --config /path/to/config/local-models.json` with the
existing gateway credential in the environment. These invoke models; `noetic doctor`
does not. Health/liveliness responses alone prove neither model authentication nor
future availability.

The host's bounded diagnostic makes real local calls. It requires the existing
`LITELLM_API_KEY` in the environment for proxy modes. Do not source or print
password/authentication files. For authenticated native Qwen metadata it uses
`QWEN_API_KEY` if supplied, otherwise consumes the installed unit's existing
key only in memory. It does not print tokens, full responses, or vectors.

```bash
python3 -B /home/dgk/workspace/home_tech_assistant/operations/localhost/bin/verify-noetic-local-models.py --mode qwen
python3 -B /home/dgk/workspace/home_tech_assistant/operations/localhost/bin/verify-noetic-local-models.py --mode proxy-embedding
```

Measured implementation checks, not independent QA:

| Check | Result |
| --- | --- |
| Authenticated native Qwen identity | `qwen3.6-a3b` |
| Authenticated `/slots` | Six entries, each `n_ctx=65536` |
| One real LiteLLM text completion | Exactly `LOCAL_MODEL_OK`; 22 prompt tokens, 4 output tokens; metadata plus completion check 0.369 seconds |
| Direct alias embeddings | Two finite, normalized 1,024-dimensional vectors; initial check 2.094 seconds |
| Proxy embeddings after unloading only the alias | Same dimensions/norms, `size_vram=0`, context 8192; reload check 2.132 seconds |
| Warm proxy embeddings | Same checks, 0.189 seconds |
| Proxy model catalog after restart | Qwen, original Snowflake route, and new noetic route all advertised |
| CPU alias residency | 1,167,593,472 bytes reported by Ollama; zero VRAM |

No image request, full-context request, six-way concurrent load, summary-quality
evaluation, maximum-length embedding, or bulk indexing benchmark was performed.
Hosting was already independently accepted when the subsequent local-support QA
accepted its client-facing integration. Later production GUI evidence confirms
real CPU-vector semantic retrieval and a Qwen supporting summary, not merely
healthy endpoints. That search used a warm derived index; cold first-index latency
and general retrieval/summary quality remain unestablished. These limits do not
prevent use of the proven routes, but must not be represented as tested.

## Host Authority

All host-operation sources are under
`/home/dgk/workspace/home_tech_assistant/operations/localhost/`:

- `GOOSE_LOCAL_MODELS.md`: updated context and local-hosting record.
- `ollama/noetic-snowflake-embed.Modelfile`: reproducible CPU alias definition.
- `litellm/config.yaml`: tracked copy with only the additive embedding route.
- `litellm/install_noetic_embedding_route.py`: narrow installer for the root
  `/etc/litellm/config.yaml`; validates all existing settings/routes remain
  unchanged, refuses a conflicting alias, and offers an idempotent `--check`.
- `bin/verify-noetic-local-models.py`: bounded real-request verification.

The alias was created with `OLLAMA_HOST=http://127.0.0.1:11434 ollama create
noetic-snowflake-embed -f <Modelfile path>` using only existing layers. The
installer ran with LiteLLM's venv Python through authorized noninteractive
sudo, followed by one `litellm.service` restart and `systemctl enable
qwen-it.service`. Elevation consumed `USER_PROVIDED_PASSWORD` through stdin
only; no password value was printed or persisted. No downloads or unrelated
model/config changes were made.
