# Model qualification at the composition boundary

`noetic genus` collects schema 6 qualification evidence from an explicitly
configured external genus-router MCP server. The consumer supplies the task
characterization, exact available model inventory, verified same-model aliases,
and its chosen model and rationale. The adapter calls `describe_dimensions`,
`align_models`, and `select_models`, in that order. It performs no inference,
provider availability probes, or catalog/rating updates.

Install the optional official MCP client with `pip install '.[genus]'` into the
Python environment running noetic. Genus remains independently installed and
configured. Other noetic commands and saved-packet validation require no MCP SDK.

Prepare UTF-8 task text, a JSON inventory such as `["gpt-6.1-sol"]`, and a JSON
characterization:

```json
{
  "task_class_id": "code_generation",
  "requirements": {"code": 1.5},
  "weights": {"token_efficiency": 3},
  "rationale": "Implement a bounded composition adapter and verify its boundary.",
  "acceptance_criteria": ["Qualification evidence survives into the run record."]
}
```

Task classes and dimensions must exist in the configured server's contract.
Requirements are positive finite numbers up to 1,000,000; efficiency weights are
integers from 1 through 5. The characterization is a caller-authored hypothesis.
An optional `qualification_policy` selects `provisional` or `conservative`;
omitting it retains the donor's default and returned warnings. Provisional
qualification compares uncertain means and does not establish measured fitness.

```sh
noetic genus \
  --task task.txt \
  --characterization characterization.json \
  --inventory inventory.json \
  --model gpt-6.1-sol \
  --reason 'Use the exact model configured for this work.' \
  --config /path/to/genus/catalog.yaml \
  --output qualification.json \
  -- /path/to/genus/venv/bin/genus-router
```

The command after `--` is an argument vector, executed by the official MCP stdio
client. The adapter appends `--config` and the absolute catalog path. Pass config
through noetic's `--config`; do not duplicate it in the external command. Requests
have a 30-second response timeout. No project-specific client registration or
donor import is needed.

`--aliases aliases.json` optionally supplies a one-to-one map from canonical
catalog IDs to exact client names. Supply only independently verified aliases
for the same model. Noetic and genus do not discover endpoint identity by
calling a provider. Noetic does not infer an alias from a model family or similar
name. Sol 6.1 cannot be aliased to Astra or an older Sol identity.

The packet contains `packet_version`, `schema_version`, a SHA256 digest of the
exact UTF-8 task text, the full characterization, inventory, verified aliases,
external server argv/config, and the complete raw `contract`, `alignment`, and
`selection` responses. Raw selection retains profile controls and revisions,
qualification estimates, uncertainty, warnings, review signals, null scores,
exclusions, and missing evidence. `consumer_decision` records `chosen_model`,
`rationale`, `qualification_support`, canonical identity, and the matching raw
`selected_evidence` when present.

An empty alignment remains `{}` in `select_models.model_aliases`; `null` would
select the donor's entire catalog. If the chosen model is unmatched, its support
is `catalog_unmatched` and the independent consumer choice remains recorded.
Other support values are `qualified`, `qualification_unknown`, `excluded`,
`qualified_unranked`, or `not_selected`. Noetic does not manufacture a model,
rating, profile, or alias to resolve a gap. The schema 6 catalog inspected for
this composition lacks both `gpt-6.1-sol` and
`openai-codex/gpt-6.1-sol`; these identities therefore remain unmatched.

The Python boundary is:

```python
packet = await generate_packet(
    task_text, characterization, models,
    chosen_model=model, reason=reason,
    server_command=argv, config=catalog_path, aliases=verified_aliases,
)
validated = validate_packet(packet, task_text, model)
```

`validate_packet` returns the entire packet or raises `ValueError` for a task or
choice mismatch, malformed evidence, or inconsistent qualification support. A
consumer can validate and retain this packet before work begins. The packet
provides worker qualification evidence; a reviewer's model choice requires its
own characterization and decision.

Run deterministic tests without a provider:

```sh
python -m unittest tests.programs.test_noetic_genus -v
```

Real MCP boundary tests run when the test interpreter has the SDK and both
`GENUS_TEST_COMMAND` (a JSON argument array) and `GENUS_TEST_CONFIG` are set:

```sh
GENUS_TEST_COMMAND='["/path/to/genus/venv/bin/genus-router"]' \
GENUS_TEST_CONFIG=/path/to/genus/catalog.yaml \
/path/to/python-with-mcp -m unittest tests.programs.test_noetic_genus -v
```

The live test expects the schema 6 donor catalog's unmatched Sol 6.1 identities
and a qualified `claude-opus-4-8` control. `GENUS_TEST_CONTROL` can override that
control for another compatible catalog. Tests compare catalog bytes before and
after the calls and retain the returned controls and qualification uncertainty.
Absent SDK or explicit donor configuration produces a clear skip.
