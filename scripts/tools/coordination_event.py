#!/usr/bin/env python3
"""Prepare exact native-call arguments and capture caller-confirmed originals."""

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import uuid


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def text_field(value, name):
    if not isinstance(value, str) or not value:
        raise ValueError(f'{name} must be a nonempty string')
    return value


def draft_at(path):
    draft = json.loads(Path(path).read_bytes())
    if not isinstance(draft, dict) or draft.get('schema') != 1 or draft.get('state') != 'prepared':
        raise ValueError('expected a schema 1 prepared draft')
    for field in ('event_id', 'sender', 'timestamp', 'prepared_at'):
        text_field(draft.get(field), field)
    if not draft['event_id'].startswith('local-event-'):
        raise ValueError('event_id must use the local-event- namespace')
    if not isinstance(draft.get('body'), str):
        raise ValueError('body must be a string')
    recipients = draft.get('recipients')
    if not isinstance(recipients, list) or not recipients:
        raise ValueError('recipients must be a nonempty list')
    for recipient in recipients:
        text_field(recipient, 'recipient')
    if len(set(recipients)) != len(recipients):
        raise ValueError('duplicate intended recipient')
    if 'evidence_time' in draft and not isinstance(draft['evidence_time'], str):
        raise ValueError('evidence_time must be a string')
    return draft


def atomic_write(path, data, *, replace, mode=0o600):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def ledger_rows(raw):
    rows = []
    for ordinal, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except (ValueError, UnicodeError) as exc:
            raise ValueError(f'invalid ledger JSON at line {ordinal}') from exc
        if not isinstance(row, dict):
            raise ValueError(f'ledger line {ordinal} is not an object')
        rows.append(row)
    return rows


def prepare(args):
    body = sys.stdin.buffer.read() if args.body_file == '-' else Path(args.body_file).read_bytes()
    draft = {'schema': 1, 'state': 'prepared', 'event_id': 'local-event-' + uuid.uuid4().hex,
             'sender': text_field(args.sender, 'sender'), 'recipients': args.recipient,
             'body': body.decode('utf-8'), 'timestamp': args.timestamp, 'prepared_at': utc_now()}
    if args.evidence_time is not None:
        draft['evidence_time'] = args.evidence_time
    if len(set(args.recipient)) != len(args.recipient):
        raise ValueError('duplicate intended recipient')
    for recipient in args.recipient:
        text_field(recipient, 'recipient')
    text_field(args.timestamp, 'timestamp')
    atomic_write(args.output, encoded(draft) + b'\n', replace=False)
    return {'event_id': draft['event_id'], 'state': 'prepared', 'recipients': len(args.recipient),
            'body_utf8_bytes': len(body), 'draft': str(Path(args.output).absolute())}


def selected_recipients(draft, args):
    selected = draft['recipients'] if args.all_recipients else args.recipient
    if len(set(selected)) != len(selected):
        raise ValueError('duplicate selected recipient')
    if any(recipient not in draft['recipients'] for recipient in selected):
        raise ValueError('selected recipient is absent from the prepared draft')
    return selected


def record(args):
    draft = draft_at(args.draft)
    selected = selected_recipients(draft, args)
    event_hash = hashlib.sha256(encoded(draft)).hexdigest()
    path = Path(args.ledger)
    with Path(str(path) + '.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
        if not mode & 0o222:
            raise ValueError('ledger is read-only')
        raw = path.read_bytes() if path.exists() else b''
        existing = ledger_rows(raw)
        identities = {}
        for row in existing:
            identity = row.get('local_record_id')
            if identity is not None:
                if identity in identities:
                    raise ValueError('ledger has duplicate local record IDs')
                identities[identity] = row
            if row.get('event_id') == draft['event_id'] and row.get('event_hash') != event_hash:
                raise ValueError('local event ID conflicts with different prepared content')
        additions = []
        route_ids = []
        for recipient in selected:
            identity = draft['event_id'] + ':' + str(draft['recipients'].index(recipient))
            route_ids.append(identity)
            row = {'sender': draft['sender'], 'recipient': recipient, 'body': draft['body'],
                   'timestamp': draft['timestamp'], 'prepared_at': draft['prepared_at'],
                   'recorded_at': utc_now(), 'event_id': draft['event_id'], 'event_hash': event_hash,
                   'local_record_id': identity,
                   'delivery_evidence': 'caller-confirmed; native transport receipt not validated'}
            if 'evidence_time' in draft:
                row['evidence_time'] = draft['evidence_time']
            if identity in identities:
                prior = {k: v for k, v in identities[identity].items() if k != 'recorded_at'}
                current = {k: v for k, v in row.items() if k != 'recorded_at'}
                if prior != current:
                    raise ValueError('local record ID conflicts with different original content')
            else:
                additions.append(row)
        if additions:
            separator = b'\n' if raw and not raw.endswith(b'\n') else b''
            atomic_write(path, raw + separator + b''.join(encoded(r) + b'\n' for r in additions),
                         replace=True, mode=mode)
        return {'ledger': str(path.absolute()), 'event_id': draft['event_id'],
                'appended': len(additions), 'already_recorded': len(selected) - len(additions),
                'local_record_ids': route_ids, 'delivery_evidence': 'caller-confirmed'}


def dispatch(args):
    draft = draft_at(args.draft)
    recipients = args.recipient or draft['recipients']
    if len(set(recipients)) != len(recipients) or any(r not in draft['recipients'] for r in recipients):
        raise ValueError('dispatch selection must name distinct prepared recipients')
    return [{'target': recipient, 'message': draft['body']} for recipient in recipients]


def copy(args):
    rows = [r for r in ledger_rows(Path(args.ledger).read_bytes()) if r.get('event_id') == args.event_id]
    if not rows:
        raise ValueError('local event is absent from the ledger')
    first = rows[0]
    common = ('sender', 'body', 'prepared_at', 'event_hash')
    if any(any(row.get(key) != first.get(key) for key in common) for row in rows):
        raise ValueError('event routes have conflicting original content')
    envelope = {'sender': first['sender'], 'body': first['body'], 'local_event_id': args.event_id,
                'routes': [{key: row[key] for key in ('recipient', 'timestamp', 'recorded_at',
                                                    'local_record_id', 'delivery_evidence')}
                           for row in rows], 'prepared_at': first['prepared_at']}
    if 'evidence_time' in first:
        envelope['evidence_time'] = first['evidence_time']
    message = ('Exact coordination copy: shared original body, separate intended routes; '
               'local IDs are not native message IDs.\n' +
               json.dumps(envelope, ensure_ascii=False, sort_keys=True))
    return {'target': args.narrator, 'message': message}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare', help='write a private draft; never send or capture delivery')
    p.add_argument('output')
    p.add_argument('--sender', required=True)
    p.add_argument('--recipient', action='append', required=True)
    p.add_argument('--body-file', required=True, help='UTF-8 file, or - for raw UTF-8 stdin')
    p.add_argument('--timestamp', default='unknown', help='actual native send time if independently known')
    p.add_argument('--evidence-time')
    p.set_defaults(action=prepare)
    p = commands.add_parser('dispatch', help='print arguments for direct native calls; never send')
    p.add_argument('draft')
    p.add_argument('--recipient', action='append')
    p.set_defaults(action=dispatch)
    p = commands.add_parser('record', help='append only routes whose dispatch the caller confirms')
    p.add_argument('ledger')
    p.add_argument('--draft', required=True)
    selection = p.add_mutually_exclusive_group(required=True)
    selection.add_argument('--recipient', action='append')
    selection.add_argument('--all-recipients', action='store_true')
    p.add_argument('--confirmed', action='store_true', required=True,
                   help='caller reports native dispatch; this tool cannot verify transport')
    p.set_defaults(action=record)
    p = commands.add_parser('copy', help='print one narrator call with the shared body and exact routes')
    p.add_argument('ledger')
    p.add_argument('--event-id', required=True)
    p.add_argument('--narrator', default='/root/ui_three_hour_narrator')
    p.set_defaults(action=copy)
    args = parser.parse_args()
    try:
        result = args.action(args)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
