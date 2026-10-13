#!/usr/bin/env python3
"""Prepare an inert delivery packet through five exact template substitutions."""

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys


def digest(path):
    with Path(path).open('rb') as stream:
        hasher = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_json(path, inputs):
    path = Path(path)
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f'expected an object: {path}')
    inputs[str(path)] = hashlib.sha256(raw).hexdigest()
    return value


def checked_hash(path, expected, label, inputs):
    actual = digest(path)
    if actual != expected:
        raise ValueError(f'{label} hash mismatch: {path}')
    inputs[str(path)] = actual
    return actual


def verify_payload(unit, label, inputs):
    payload = read_json(unit / 'payload-verification.json', inputs)
    for kind in ('archive', 'wheel'):
        checked_hash(Path(payload[kind]), payload[kind + '_sha256'], label + ' ' + kind, inputs)
    manifest_path = unit / 'frozen-source-sha256.json'
    if Path(payload['source_manifest']).resolve() != manifest_path.resolve():
        raise ValueError(f'{label} source manifest path disagrees with unit')
    checked_hash(manifest_path, payload['source_manifest_sha256'], label + ' source manifest', inputs)
    manifest = read_json(manifest_path, inputs)
    if payload['source_files'] != len(manifest):
        raise ValueError(f'{label} source count disagrees with manifest')
    for name, expected in manifest.items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('source manifest names must stay within source-final')
        checked_hash(unit / 'source-final' / relative, expected, label + ' source', inputs)
    return payload


def change_once(raw, pattern, replacement, label):
    matches = list(re.finditer(pattern, raw, re.MULTILINE))
    if len(matches) != 1:
        raise ValueError(f'expected one {label}; found {len(matches)}')
    match = matches[0]
    changed = raw[:match.start()] + replacement + raw[match.end():]
    return changed, match.group(1).decode('utf-8')


def prepare(args):
    status_path = Path(args.status).resolve()
    base = status_path.parent
    candidate = Path(args.candidate).resolve()
    templates = Path(args.templates).resolve()
    output = Path(args.output).absolute()
    if any(path.parent.resolve() != base for path in (candidate, templates, output)):
        raise ValueError('packet inputs and output must share one parent')
    if output.exists() or output.is_symlink():
        raise ValueError('output directory already exists')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', candidate.name):
        raise ValueError('candidate basename cannot be represented in these templates')
    inputs = {}
    status = read_json(status_path, inputs)
    previous = status['installed_release']
    if not isinstance(previous, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+-]*', previous):
        raise ValueError('installed release must be a single release basename')
    current_source = Path(status['current_source_base']).resolve()
    prior = current_source.parent
    if current_source.name != 'source-final' or prior.parent != base:
        raise ValueError('current source base does not identify a sibling unit')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', prior.name):
        raise ValueError('prior unit basename cannot be represented in these templates')
    if Path(status['current_frozen_manifest']).resolve() != prior / 'frozen-source-sha256.json':
        raise ValueError('status source base and frozen manifest disagree')
    prior_payload = verify_payload(prior, 'prior', inputs)
    if prior_payload['release'] != previous:
        raise ValueError('installed release does not match prior payload')
    deployed = read_json(Path(status['last_deployment_evidence']), inputs)
    if deployed['release'] != 'releases/' + previous or deployed['archive_sha256'] != prior_payload['archive_sha256']:
        raise ValueError('current deployment receipt disagrees with installed payload')
    candidate_payload = verify_payload(candidate, 'candidate', inputs)
    originals = {}
    for name in ('deploy.py', 'final-smoke.py', 'session-maintenance.py'):
        path = templates / name
        originals[name] = path.read_bytes()
        inputs[str(path)] = hashlib.sha256(originals[name]).hexdigest()
    changes = []
    deploy, old_candidate = change_once(originals['deploy.py'],
        rb"^CANDIDATE=BASE/'([^'\r\n]+)'(?=\r?$)",
        ("CANDIDATE=BASE/" + repr(candidate.name)).encode(), 'deploy CANDIDATE')
    changes.append({'field': 'deploy CANDIDATE', 'before': old_candidate, 'after': candidate.name})
    deploy, old_previous = change_once(deploy,
        rb"^assert previous=='([^'\r\n]+)'(?=\r?$)",
        ("assert previous==" + repr('releases/' + previous)).encode(), 'previous release assertion')
    changes.append({'field': 'previous release assertion', 'before': old_previous, 'after': 'releases/' + previous})
    deploy, old_prior = change_once(deploy,
        rb"^prior_build=json.loads\(\(BASE/'([^'\r\n]+)/payload-verification.json'\)\.read_text\(\)\)(?=\r?$)",
        ("prior_build=json.loads((BASE/" + repr(prior.name + '/payload-verification.json') + ").read_text())").encode(),
        'prior payload reference')
    changes.append({'field': 'prior payload reference', 'before': old_prior, 'after': prior.name})
    deploy, old_archive = change_once(deploy,
        rb"^assert sha\(prior_archive\)=='([0-9a-f]{64})'(?=\r?$)",
        ("assert sha(prior_archive)==" + repr(prior_payload['archive_sha256'])).encode(), 'prior archive assertion')
    changes.append({'field': 'prior archive assertion', 'before': old_archive, 'after': prior_payload['archive_sha256']})
    smoke, old_smoke = change_once(originals['final-smoke.py'],
        rb"^BASE = Path\(__file__\)\.resolve\(\)\.parent\.parent / '([^'\r\n]+)'(?=\r?$)",
        ("BASE = Path(__file__).resolve().parent.parent / " + repr(candidate.name)).encode(), 'smoke BASE')
    if old_smoke != old_candidate:
        raise ValueError('template candidate names disagree')
    changes.append({'field': 'smoke BASE', 'before': old_smoke, 'after': candidate.name})
    generated = {'deploy.py': deploy, 'final-smoke.py': smoke,
                 'session-maintenance.py': originals['session-maintenance.py']}
    for name, raw in generated.items():
        ast.parse(raw, filename=name)
    receipt = {'state': 'PREPARED ONLY', 'prepared_at': datetime.now(timezone.utc).isoformat(),
               'output': str(output), 'candidate_unit': str(candidate), 'previous_release': previous,
               'candidate_release_reported': candidate_payload['release'],
               'source_acceptance': 'external; not inferred', 'scripts_executed': False,
               'substitutions': len(changes), 'changes': changes, 'input_sha256': inputs,
               'generated_sha256': {name: hashlib.sha256(raw).hexdigest() for name, raw in generated.items()}}
    output.mkdir()
    for name, raw in generated.items():
        with (output / name).open('xb') as stream:
            stream.write(raw)
    with (output / 'preparation.json').open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('status', 'candidate', 'templates', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        receipt = prepare(args)
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as exc:
        print('error: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps({'state': receipt['state'], 'output': receipt['output'],
                      'substitutions': receipt['substitutions'],
                      'source_acceptance': receipt['source_acceptance'],
                      'receipt': str(Path(receipt['output']) / 'preparation.json')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
