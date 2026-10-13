#!/usr/bin/env python3
"""Edit a static HTML transcript with an embedded, lossless JSON source model."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from fractions import Fraction
import fcntl
import html
import json
import os
from pathlib import Path
import re
import tempfile
import uuid


MARKER = '<script id="narrative-document-model" type="application/json">'
FIELDS = {'utc', 'sender', 'recipient', 'source', 'original', 'translation', 'narrative'}
ID_PATTERN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z')


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def validate_strings(value, fields):
    if not isinstance(value, dict) or set(value) - fields:
        raise ValueError('payload must be an object with supported fields')
    for key, item in value.items():
        if key == 'metadata':
            if not isinstance(item, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                                 for k, v in item.items()):
                raise ValueError('metadata must map strings to strings')
        elif not isinstance(item, str):
            raise ValueError(f'{key} must be a string')


def read_document(path):
    text = path.read_text(encoding='utf-8')
    if text.count(MARKER) != 1:
        raise ValueError('not a narrative document: embedded model missing or ambiguous')
    body = text.split(MARKER, 1)[1].split('</script>', 1)[0]
    model = json.loads(body)
    if model.get('schema') != 1 or not isinstance(model.get('revision'), int):
        raise ValueError('unsupported narrative document model')
    return model


def escaped(value):
    return html.escape(value, quote=True)


def render(model):
    meta = model['document']
    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             f'<title>{escaped(meta["title"])}</title>',
             '<style>body{font-family:system-ui,sans-serif;max-width:72rem;margin:auto;padding:1.5rem;line-height:1.5;color:#18212b;background:#fff}article{border-top:1px solid #b6c1cb;padding:1rem 0}pre,p{white-space:pre-wrap;overflow-wrap:anywhere}pre{font:inherit;background:#f1f4f6;padding:1rem}a{color:#12569b}small{display:block}h2{font-size:1.15rem}summary{cursor:pointer}dt{font-weight:600}dd{margin-left:1rem}</style></head><body><header>',
             f'<h1>{escaped(meta["title"])}</h1>',
             f'<p>Revision {model["revision"]} · Updated {escaped(model["updated_utc"])} · {len(model["entries"])} entries</p>']
    for label in ('coverage', 'gaps'):
        parts.append(f'<p><strong>{label.title()}:</strong> {escaped(meta.get(label, "Unspecified"))}</p>')
    parts.append('</header><main aria-label="Conversation entries">')
    for entry in model['entries']:
        eid = escaped(entry['id'])
        parts.extend([f'<article id="{eid}" data-entry-id="{eid}" data-seq="{entry["seq"]}">',
                      f'<h2><a href="#{eid}">{eid}</a></h2>',
                      f'<small>UTC: {escaped(entry["utc"])} · Sender: {escaped(entry["sender"])} · Recipient: {escaped(entry["recipient"])}</small>',
                      f'<small>Source: {escaped(entry["source"])} · Order: {entry["seq"]}</small>'])
        if entry.get('metadata'):
            parts.append('<dl>')
            for key, value in entry['metadata'].items():
                parts.append(f'<dt>{escaped(key)}</dt><dd>{escaped(value)}</dd>')
            parts.append('</dl>')
        for label in ('narrative', 'translation'):
            if entry[label]:
                parts.append(f'<p><strong>{label.title()}:</strong> {escaped(entry[label])}</p>')
        parts.append(f'<details><summary>Original message (verbatim)</summary><pre>{escaped(entry["original"])}</pre></details></article>')
    parts.append('</main>')
    # Script raw-text parsing ignores JSON quoting; escape every opening bracket.
    data = json.dumps(model, ensure_ascii=True, separators=(',', ':')).replace('<', '\\u003c')
    parts.append(MARKER + data + '</script></body></html>\n')
    return ''.join(parts)


@contextmanager
def locked(path):
    with path.with_name(path.name + '.lock').open('a', encoding='utf-8') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def atomic_write(path, model):
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    if path.exists() and not mode & 0o222:
        raise ValueError('document is read-only')
    descriptor, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='') as output:
            output.write(render(model))
            output.flush()
            os.fsync(output.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def find_entry(model, eid):
    for entry in model['entries']:
        if entry['id'] == eid:
            return entry
    raise ValueError(f'entry not found: {eid}')


def sequence(entries, before=None, after=None):
    if before is not None and after is not None:
        raise ValueError('choose before or after, not both')
    if not entries:
        if before is not None or after is not None:
            raise ValueError('insertion anchor not found')
        return '1'
    index = len(entries)
    anchor = before if before is not None else after
    if anchor is not None:
        matches = [i for i, entry in enumerate(entries) if entry['id'] == anchor]
        if not matches:
            raise ValueError(f'insertion anchor not found: {anchor}')
        index = matches[0] + (after is not None)
    low = Fraction(entries[index - 1]['seq']) if index else None
    high = Fraction(entries[index]['seq']) if index < len(entries) else None
    return str((low + high) / 2 if low is not None and high is not None
               else high - 1 if high is not None else low + 1)


def apply_operation(model, op):
    if not isinstance(op, dict):
        raise ValueError('operation must be an object')
    action = op.get('op')
    allowed = {'insert': {'op', 'entry', 'before', 'after'},
               'update': {'op', 'id', 'patch', 'before', 'after'},
               'delete': {'op', 'id'}, 'meta': {'op', 'patch'}}
    if action not in allowed or set(op) - allowed[action]:
        raise ValueError('unsupported operation or operation fields')
    for key in ('id', 'before', 'after'):
        if key in op and not isinstance(op[key], str):
            raise ValueError(f'{key} must be a string')
    if action == 'meta':
        patch = op.get('patch', {})
        validate_strings(patch, {'title', 'coverage', 'gaps'})
        model['document'].update(patch)
        return {'op': action}
    if action == 'insert':
        payload = op.get('entry', {})
        validate_strings(payload, FIELDS | {'id', 'metadata'})
        eid = payload.get('id', str(uuid.uuid4()))
        used = {e['id'] for e in model['entries']} | {t['entry']['id'] for t in model['tombstones']}
        if not ID_PATTERN.fullmatch(eid) or eid in used or eid == 'narrative-document-model':
            raise ValueError('entry ID invalid, reserved, or already used')
        entry = {key: ('unknown' if key in {'utc', 'sender', 'recipient', 'source'} else '') for key in FIELDS}
        entry.update(payload)
        entry.update(id=eid, seq=sequence(model['entries'], op.get('before'), op.get('after')))
        model['entries'].append(entry)
    else:
        eid = op.get('id')
        entry = find_entry(model, eid)
        previous = dict(entry)
        if action == 'delete':
            model['entries'].remove(entry)
            model['tombstones'].append({'revision': model['revision'] + 1, 'entry': previous})
        else:
            patch = op.get('patch', {})
            validate_strings(patch, FIELDS | {'metadata'})
            entry.update(patch)
            if 'before' in op or 'after' in op:
                entry['seq'] = sequence([e for e in model['entries'] if e['id'] != eid],
                                        op.get('before'), op.get('after'))
        model['audit'].append({'op': action, 'revision': model['revision'] + 1, 'previous': previous})
    model['entries'].sort(key=lambda e: Fraction(e['seq']))
    return {'op': action, 'id': eid}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'list', 'show', 'insert', 'update', 'delete', 'apply'])
    parser.add_argument('path', type=Path)
    parser.add_argument('id', nargs='?')
    parser.add_argument('--payload', type=Path)
    parser.add_argument('--title', default='Conversation transcript')
    parser.add_argument('--expected-revision', type=int)
    position = parser.add_mutually_exclusive_group()
    position.add_argument('--before')
    position.add_argument('--after')
    args = parser.parse_args()
    path = args.path.expanduser().resolve()
    try:
        if args.command in {'update', 'delete', 'show'} and args.id is None:
            raise ValueError('entry ID required')
        if args.command in {'insert', 'update', 'apply'} and args.payload is None:
            raise ValueError('--payload required')
        payload = json.loads(args.payload.read_text(encoding='utf-8')) if args.payload else None
        with locked(path):
            if args.command == 'init':
                if path.exists():
                    raise ValueError('refusing to overwrite existing document')
                model = {'schema': 1, 'revision': 0, 'updated_utc': utc_now(),
                         'document': {'title': args.title}, 'entries': [], 'audit': [], 'tombstones': []}
                atomic_write(path, model)
                result = {'path': str(path), 'revision': 0}
            else:
                model = read_document(path)
                if args.command == 'list':
                    result = {'revision': model['revision'], 'entries': [{'id': e['id'], 'seq': e['seq']} for e in model['entries']]}
                elif args.command == 'show':
                    result = {'revision': model['revision'], 'entry': find_entry(model, args.id)}
                else:
                    if args.expected_revision is not None and args.expected_revision != model['revision']:
                        raise ValueError(f'stale revision: expected {args.expected_revision}, found {model["revision"]}')
                    if args.command == 'apply':
                        operations = payload
                        if not isinstance(operations, list) or not operations:
                            raise ValueError('apply payload must be a nonempty operation array')
                    else:
                        op = {'op': args.command}
                        if args.id is not None:
                            op['id'] = args.id
                        if payload is not None:
                            op['entry' if args.command == 'insert' else 'patch'] = payload
                        for key in ('before', 'after'):
                            if getattr(args, key) is not None:
                                op[key] = getattr(args, key)
                        operations = [op]
                    receipts = [apply_operation(model, op) for op in operations]
                    model['revision'] += 1
                    model['updated_utc'] = utc_now()
                    atomic_write(path, model)
                    result = {'path': str(path), 'revision': model['revision'], 'operations': receipts}
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'error: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
