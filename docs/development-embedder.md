# Development embedding endpoint

The explicit host DEVELOPMENT profile in `config/development-local-support.example.json`
selects `http://127.0.0.1:11435/v1/embeddings` and model
`noetic-snowflake-embed:latest`. Its 1024-dimensional identity retains the existing
Snowflake source layer, tokenizer, pooling and preprocessing declarations. This
profile is optional installation configuration; the client has no implicit
configuration file and retains its existing defaults.

The application calls `load_settings()`. Select a configuration file through
`NOETIC_LOCAL_CONFIG=/absolute/path/to/development-local-support.json` in its
process environment. CLI callers can instead pass `--config PATH`; Python callers
can pass `load_settings(PATH, **overrides)`. Choosing a file loads settings only.
An embedding request requires an explicit application or CLI operation.

Settings precedence is non-`None` explicit Python arguments or supplied CLI flags,
then `NOETIC_LOCAL_*` environment values, then the selected JSON file, then defaults.
An explicit configuration path takes precedence over `NOETIC_LOCAL_CONFIG`.
Empty strings remain explicit values; JSON `null` for either optional embedding
setting means inheritance, subject to higher-precedence values.

| Setting | Python | CLI | Environment | JSON | Default |
|---|---|---|---|---|---|
| Embedding base URL | `embedding_base_url` | `--embedding-base-url` | `NOETIC_LOCAL_EMBEDDING_BASE_URL` | `embedding.base_url` | `None`: use `base_url` |
| Embedding credential environment name | `embedding_api_key_env` | `--embedding-api-key-env` | `NOETIC_LOCAL_EMBEDDING_API_KEY_ENV` | `embedding.api_key_env` | `None`: use `api_key_env` |
| Embedding model | `embedding_model` | `--embedding-model` | `NOETIC_LOCAL_EMBEDDING_MODEL` | `embedding.model` | `noetic-snowflake-embed` |

Supply the API base URL, such as `http://127.0.0.1:11435/v1`, because the client
appends `/embeddings`. URLs require HTTP(S), a hostname, a valid port when present,
and no embedded credentials, query or fragment. Trailing slashes are stripped.

The embedding credential setting has three precise meanings:

- Omitted or `None`: inherit the completion credential environment name, including
  when an embedding base URL is supplied separately. The selected variable must
  contain a value before a request is sent.
- Empty string (`""`): explicit no authentication. No credential is read and no
  `Authorization` header is sent, even if `LITELLM_API_KEY` is present.
- Nonempty name, such as `NOETIC_EMBEDDING_KEY`: require that environment variable
  and send its value as the embedding request's Bearer credential. The JSON file
  contains the variable name, never its secret value. A missing or empty credential
  fails before sending any request.

The DEVELOPMENT example explicitly selects no authentication. Text completion
continues to use `access.base_url`, `access.api_key_env` and `inference.model`.
Loading this profile neither starts a model host nor invokes text inference. The
port-3333 completion settings in the example retain the legacy route selection;
they do not establish that a completion service is available.

One explicit diagnostic can verify the selected embedder:

```sh
python -m scripts.noetic_local diagnose embedding \
  --config config/development-local-support.example.json \
  --text 'Public development embedder diagnostic.'
```

Alternatively, select the endpoint without a file:

```sh
python -m scripts.noetic_local diagnose embedding \
  --embedding-base-url http://127.0.0.1:11435/v1 \
  --embedding-api-key-env '' \
  --embedding-model noetic-snowflake-embed:latest
```

The cache identity records the effective embedding base URL, `/embeddings`, model
and the existing source/vector/preprocessing identity fields. Completion endpoint
changes do not change this identity when the embedding endpoint is explicit.
Credential selection does not describe a vector space and is excluded. Unset
embedding settings preserve the legacy identity exactly. Changing the effective
embedding endpoint or model requires explicit cache reindexing; it cannot reuse
vectors under a mismatching identity. Existing byte budgets, batch bounds,
finite/nonzero L2 normalization, response size limit, timeout and refusal of
redirects remain enforced.
