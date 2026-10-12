# Cognitional event journal v1

The v1 journal is a provider-free persistence leaf for one real consumer: `development.verified-change` under its fixed `m0-direct-pass` profile. It stores the existing attributed M0 event envelope as canonical JSON Lines and reconstructs consumer state through the existing `M0ReplayController`. It does not define a second event vocabulary or transition engine.

## Persistence contract

Each logical record is compact, lexicographically sorted ASCII JSON followed by one LF. Storage admission requires exactly the existing `schema_version`, `event_id`, `event_type`, `occurred_at`, `actor`, `binding`, `caused_by`, and `payload` envelope, the fixed M0 record version, and basic actor, binding, and payload shapes. Event-specific values and cross-record semantics remain terminal reducer responsibilities. The journal is bounded to eight records, 65,536 bytes per record including LF, and 524,288 bytes total.

Every operation rebuilds state from the journal. Before an append opens the file, all existing bytes must be canonical complete records, the existing prefix must replay, and the candidate must be accepted by a fresh controller. A rejected candidate therefore leaves journal bytes unchanged. A successful append is flushed and the file is fsynced before returning its read model.

The contract is single-writer. It adds no lock manager, database, snapshot, checkpoint, rotation, hash chain, signature, scheduler, transport, or model dependency.

## Read model and claims

The deterministic read model reports its versions, fixed consumer ID, record count, replay state, and completion flag. An incomplete prefix reports only `next_event_type`. It is not a successful verified change and has no terminal status.

The eighth event invokes the existing whole-trace `development.verified-change` pipeline transactionally. Only then does the read model expose its unchanged terminal status. Full actor, binding, timestamp, payload, source-digest, and program-packet validation therefore remain owned by the existing reducers rather than by journal byte layout.

Because those checks are terminal, a structurally admitted prefix can still fail completion. Complete logical records are not rewritten; an abandoned prefix starts a separate journal rather than being presented as successful evidence.

Actors, authority, P1-P4 products, QA `PASS`, controller success, and Telos completion remain fixture-attributed declarations. Persistence and replay do not authenticate identities, establish independent QA, infer semantic quality, execute a candidate, or prove cognition or responsible judgment.

## Recovery boundary

Normal inspect and append operations reject a non-LF-terminated tail. Recovery is explicit: after every preceding complete record has parsed canonically and replayed successfully, `recover` truncates only the final unterminated bytes and fsyncs the file. It never skips or truncates a malformed, rejected, or surplus LF-terminated record. Once recovered, callers may retry the next event.

This boundary handles one torn append without rewriting accepted logical history. It does not claim multi-writer coordination or arbitrary corruption repair.

## CLI

The packet must select `m0-direct-pass`; the committed program golden selects M1 and is not a journal input. Given a caller-supplied coherent M0 packet:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/cognitional_event_journal.py inspect \
  packet-m0.json journal.jsonl

PYTHONDONTWRITEBYTECODE=1 python3 scripts/cognitional_event_journal.py append \
  packet-m0.json journal.jsonl next-event.json

PYTHONDONTWRITEBYTECODE=1 python3 scripts/cognitional_event_journal.py recover \
  packet-m0.json journal.jsonl
```

Each successful command writes the deterministic read model to standard output. Validation and I/O failures write a controlled diagnostic to standard error and return exit 1; argument errors return exit 2.

The machine-readable [journal contract](../spec/events/v1/cognitional-event-journal-contract.json) fixes the storage, replay, read-model, recovery, and claim boundaries.
