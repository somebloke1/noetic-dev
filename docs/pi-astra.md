# Pi and Astra access

Pi 0.85.1 includes `openai-codex/gpt-6-astra` for direct OpenAI subscription
access. This is distinct from `openai/gpt-6-astra`, which uses metered API-key
access. Keep provider identities separate: they select different authentication
and transport implementations.

The two required paths are:

| Client selection | API | Subscription authentication owner |
| --- | --- | --- |
| Pi `openai-codex/gpt-6-astra` | `openai-codex-responses` | Pi's supported OpenAI/Codex OAuth flow |
| Pi `litellm/codex/gpt-6-astra` | `openai-responses` | LiteLLM's `chatgpt` provider |
| OpenCode `openai/gpt-6-astra` | Native subscription integration | OpenCode's supported subscription flow |
| OpenCode `litellm/codex/gpt-6-astra` | OpenAI Responses through LiteLLM | LiteLLM's `chatgpt` provider |

Direct Pi uses the built-in model; no custom direct-provider entry is needed.
For the routed path, merge the model row in `config/pi-astra-models.json` into
the existing `providers.litellm.models` array. It is a model fragment, not a
replacement for the user's provider configuration. Preserve the existing
LiteLLM endpoint and gateway credential configuration. Never copy subscription
tokens into Pi's LiteLLM provider or redirect Pi's Codex OAuth transport to the
proxy.

The fragment uses Pi's conservative built-in Astra context default of 272,000
and output maximum of 128,000 tokens. The host LiteLLM route advertises larger
context capacity, but this client profile does not assume that capacity has
been exercised. Unsupported `off` and `minimal` levels are disabled for the
proxy; high/xhigh/max are explicitly mapped. Pi's built-in direct profile owns
its native thinking-level policy.

On this host, LiteLLM already maps public alias `codex/gpt-6-astra` to
`chatgpt/gpt-6-astra`, in Responses mode. The service, not noetic-dev or Pi,
owns the subscription refresh and persistence lifecycle. No new proxy, copied
auth store, or LiteLLM upgrade is needed for this model addition.

For Pi configuration inherited from older releases,
`compat.sendSessionIdHeader: false` becomes
`compat.sessionAffinityFormat: "openai-nosession"`. Existing provider/API
defaults for other models must not be changed globally.

Run a fresh Pi process after updating the package/models. No parent OpenCode
restart is required. Both examples below use already configured authentication:

```bash
pi --mode json --no-extensions --no-approve --model openai-codex/gpt-6-astra --thinking high -p "Read the requested project file and report its contents."
pi --mode json --no-extensions --no-approve --model litellm/codex/gpt-6-astra --thinking high -p "Read the requested project file and report its contents."
```

For harness work, select the same model IDs through the Pi adapter. Structured
terminal messages and tool-call continuations must be checked independently of
CLI exit codes: Pi JSON mode may exit zero after a model error. Tests must not
inspect, print, or copy either subscription credential store.

## Local verification

On 2026-09-07, Pi 0.85.1 completed a real read-tool call and then returned an
unseen file line through both `openai-codex/gpt-6-astra` and
`litellm/codex/gpt-6-astra`. Their recorded APIs were respectively
`openai-codex-responses` and `openai-responses`; both ended with `stop`, not
an error. OpenCode 1.18.29 completed the same tool-continuation probe through
both `openai/gpt-6-astra` and `litellm/codex/gpt-6-astra`.

Raw local probe records are under `.runtime/astra-probe/`. These establish
functional text/tool continuation on the configured host, not every capability,
context limit, model variant, or future authentication lifetime. Independent QA
is recorded separately from these implementation checks.
