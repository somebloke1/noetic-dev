# Exact coordination event helper

`scripts/tools/coordination_event.py` uses Python 3's standard library and POSIX
`fcntl`. It prepares one original body for selected recipients, prints native-call
arguments, and appends caller-confirmed originals to an existing per-role
`coordination-backfill.jsonl`. It does not call a messaging API or edit a transcript.

```sh
TOOL=scripts/tools/coordination_event.py
PACKET=/absolute/path/owned-packet
python3 "$TOOL" prepare "$PACKET/draft.json" \
  --sender /root/example \
  --recipient /root/peer-a --recipient /root/peer-b \
  --body-file "$PACKET/body.txt"
python3 "$TOOL" dispatch "$PACKET/draft.json"
```

Use each printed `{target, message}` object as arguments to a **direct** native
`collaboration.send_message` call. Collaboration tools cannot be called from
`functions.exec` or a local script. The draft preserves UTF-8 body bytes decoded as
text, including CRLF, tabs, trailing spaces, quotes and Unicode. A draft is private
preparation; it never enters backfill automatically. `prepare` refuses overwrite.
The output parent directory must exist. `--body-file -` reads raw UTF-8 stdin.

After successful native dispatch, capture only the recipients actually dispatched:

```sh
python3 "$TOOL" record "$PACKET/coordination-backfill.jsonl" \
  --draft "$PACKET/draft.json" --recipient /root/peer-a --confirmed
python3 "$TOOL" record "$PACKET/coordination-backfill.jsonl" \
  --draft "$PACKET/draft.json" --recipient /root/peer-b --confirmed
```

If all prepared recipients were dispatched, one `--all-recipients --confirmed`
operation captures every route. This is the caller's report; the helper cannot
verify native transport receipts. Existing failed attempts or legacy records are
preserved without reinterpretation. Use existing recording practices for failed
attempts rather than recording them through this confirmed-route command.

Original `timestamp` defaults to `unknown`. `prepared_at` is the actual local
preparation clock; `recorded_at` is the actual local capture clock. Neither becomes
a send time. `--timestamp` accepts a separately known source time; use a separate
draft when original send times differ. `--evidence-time` records an explicitly
supplied observation time independently from all three fields. The tool neither
reconstructs lost originals nor discovers or redacts credentials: supply only the
exact authorized text that belongs in the transcript.

Every route stores singular `sender`, `recipient`, `body`, `timestamp` fields
compatible with the narrator's existing importer. `event_id` and
`local_record_id` identify local records, **not native messages**. Recipient order
within the immutable draft determines route suffixes; full names and namespaces
remain intact. Re-recording the same draft/route appends nothing. A reused local
ID with different original content fails before mutation. A new draft retains a
legitimate repeated identical message. Deduplication never guesses from body text.

Capture preserves the prior ledger's exact bytes and appends a JSON line per new
route. Cooperating writers use `LEDGER.lock`; a temporary sibling is atomically
replaced so readers see a complete snapshot. Malformed ledgers, conflicting IDs
and read-only ledgers are refused. Do not remove active lock files or mix this
writer with writers that ignore its lock. No transcript lock or revision is used.

The prepare receipt supplies `event_id`. Print a single narrator copy:

```sh
python3 "$TOOL" copy "$PACKET/coordination-backfill.jsonl" \
  --event-id local-event-REPLACE_WITH_RECEIPT
```

Send the printed `{target, message}` through the direct native tool. The narrator
copy contains the exact shared original body once and each intended route with
its separate timestamp/provenance. Do not recursively copy this transcript copy.
The singular ledger records remain the narrator's import substrate.

One prepared body can serve a unicast, selected multicast or explicit broadcast;
one capture can converge many confirmed routes; one narrator copy can represent
those routes losslessly. Native dispatch still costs one call per recipient.
Preparation, dispatch, capture and rendering remain distinct operations.

These are practical analogies to the functional correspondences in the supplied
Lonergan excerpt, not claims that his text specifies messaging or proves future
reuse. A helper is a completed means; its use incurs recurring work. Count actual
successful uses and necessary dispatches when judging its value. UTF-8 byte counts
are not token counts, provider usage or evidence of paid-cache behavior.

```sh
python3 -m unittest discover -s tests/tools -p test_coordination_event.py -v
```
