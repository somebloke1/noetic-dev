#!/usr/bin/env python3
"""Run bounded independent nonstreaming model requests and preserve their originals."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def content_view(content):
    view = content
    transformations = []
    if isinstance(content, str) and content.startswith('</think>'):
        end = len('</think>')
        while end < len(content) and content[end] in '\r\n':
            end += 1
        view = content[end:]
        transformations.append({'kind': 'remove-known-leading-assistant-boundary',
                                'removed_prefix': content[:end], 'character_span': [0, end]})
    result = {'original_content': content, 'derived_content': view,
              'transformations': transformations, 'json_parse': 'not-string',
              'semantic_status': 'unassessed candidate'}
    if isinstance(view, str):
        try:
            result['derived_json'] = json.loads(view)
            result['json_parse'] = 'parsed'
        except ValueError:
            result['json_parse'] = 'failed'
    return result


def load_requests(path):
    raw = Path(path).read_bytes()
    items = json.loads(raw)
    if not isinstance(items, list) or not items:
        raise ValueError('requests must be a nonempty JSON array')
    identities = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id']:
            raise ValueError('each request requires a nonempty explicit string id')
        if item['id'] in identities:
            raise ValueError('duplicate local request id')
        identities.add(item['id'])
        payload = item.get('request')
        if not isinstance(payload, dict) or not isinstance(payload.get('model'), str) or not payload['model']:
            raise ValueError('request must include an explicit model')
        if not isinstance(payload.get('messages'), list) or not payload['messages']:
            raise ValueError('request must include messages')
        if payload.get('stream', False) is not False:
            raise ValueError('only nonstreaming requests are supported')
    return raw, items


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def annotate(args):
    source = Path(args.view_response).absolute()
    raw = source.read_bytes()
    output = Path(args.output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('output path already exists')
    output.mkdir()
    raw_path = output / 'original.response.bin'
    with raw_path.open('xb') as stream:
        stream.write(raw)
    receipt_path = output / 'view.receipt.json'
    result = {'source_response_path': str(source), 'source_response_sha256': sha(raw),
              'raw_response_path': str(raw_path), 'raw_response_sha256': sha(raw),
              'local_viewed_at': utc_now(), 'operation': 'annotate existing response artifact',
              'network_activity': False, 'semantic_status': 'unassessed candidate',
              'usage': None, 'usage_source': 'response-reported; not independently verified'}
    try:
        parsed = json.loads(raw)
        choice = parsed['choices'][0]
        message = choice['message']
        if not isinstance(message, dict):
            raise ValueError('choice message is not an object')
        result.update({'provider_response_id': parsed.get('id'), 'returned_model': parsed.get('model'),
                       'usage': parsed.get('usage'), 'finish_reason': choice.get('finish_reason')})
        result.update(content_view(message.get('content')))
        result['artifact_status'] = 'annotated'
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        result['artifact_status'] = 'invalid_response'
        result['error'] = type(exc).__name__ + ': ' + str(exc)
    write_json(receipt_path, result)
    return {'output': str(output), 'operation': result['operation'],
            'receipt_path': str(receipt_path), 'artifact_status': result['artifact_status'],
            'network_activity': False, 'semantic_status': 'unassessed candidate'}


def query(entry, output, endpoint, timeout):
    ordinal, item = entry
    stem = f'{ordinal:04d}-' + sha(item['id'].encode('utf-8'))[:12]
    request_path = output / (stem + '.request.json')
    raw_path = output / (stem + '.response.bin')
    receipt_path = output / (stem + '.receipt.json')
    wire = json.dumps(item['request'], ensure_ascii=False).encode('utf-8')
    with request_path.open('xb') as stream:
        stream.write(wire)
    result = {'request_id': item['id'], 'batch_ordinal': ordinal, 'endpoint': endpoint,
              'requested_model': item['request']['model'], 'caller_metadata': item.get('metadata'),
              'local_started_at': utc_now(), 'request_path': str(request_path),
              'request_sha256': sha(wire), 'receipt_path': str(receipt_path),
              'transport_status': 'request_error', 'usage': None,
              'usage_source': 'response-reported; not independently verified',
              'semantic_status': 'unassessed candidate'}
    raw = None
    started = time.perf_counter()
    try:
        request = urllib.request.Request(endpoint, data=wire,
                                         headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result['http_status'] = response.status
            raw = response.read()
        result['transport_status'] = 'response'
    except urllib.error.HTTPError as exc:
        result['transport_status'] = 'http_error'
        result['http_status'] = exc.code
        try:
            raw = exc.read()
        except http.client.IncompleteRead as partial:
            raw = partial.partial
            result['body_read_error'] = type(partial).__name__ + ': ' + str(partial)
        except (OSError, http.client.HTTPException) as body_error:
            result['body_read_error'] = type(body_error).__name__ + ': ' + str(body_error)
        result['error'] = type(exc).__name__ + ': ' + str(exc)
    except http.client.IncompleteRead as exc:
        raw = exc.partial
        result['error'] = type(exc).__name__ + ': ' + str(exc)
    except (OSError, ValueError, http.client.HTTPException) as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)
    result['request_elapsed_seconds'] = round(time.perf_counter() - started, 6)
    if raw is not None:
        with raw_path.open('xb') as stream:
            stream.write(raw)
        result['raw_response_path'] = str(raw_path)
        result['raw_response_sha256'] = sha(raw)
    if result['transport_status'] == 'response':
        try:
            parsed = json.loads(raw)
            choice = parsed['choices'][0]
            message = choice['message']
            if not isinstance(message, dict):
                raise ValueError('choice message is not an object')
            result.update({'provider_response_id': parsed.get('id'), 'returned_model': parsed.get('model'),
                           'usage': parsed.get('usage'), 'finish_reason': choice.get('finish_reason')})
            result.update(content_view(message.get('content')))
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            result['transport_status'] = 'invalid_response'
            result['error'] = type(exc).__name__ + ': ' + str(exc)
    result['local_finished_at'] = utc_now()
    write_json(receipt_path, result)
    return result


def run(args):
    if not 1 <= args.concurrency <= 32:
        raise ValueError('concurrency must be between 1 and 32')
    if not args.timeout > 0:
        raise ValueError('timeout must be positive')
    address = urllib.parse.urlsplit(args.endpoint)
    if address.scheme not in ('http', 'https') or not address.netloc:
        raise ValueError('endpoint must be a full HTTP(S) chat-completions URL')
    raw, items = load_requests(args.requests)
    output = Path(args.output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('output path already exists')
    output.mkdir()
    with (output / 'requests.input.json').open('xb') as stream:
        stream.write(raw)
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        results = list(executor.map(lambda entry: query(entry, output, args.endpoint, args.timeout),
                                    enumerate(items, 1)))
    summary = {'output': str(output), 'input_sha256': sha(raw), 'request_count': len(items),
               'concurrency_requested': args.concurrency,
               'response_count': sum(result['transport_status'] == 'response' for result in results),
               'failure_count': sum(result['transport_status'] != 'response' for result in results),
               'batch_elapsed_seconds': round(time.perf_counter() - started, 6),
               'semantic_status': 'unassessed candidates', 'automatic_retries': 0,
               'results': [{key: result.get(key) for key in ('request_id', 'batch_ordinal', 'receipt_path',
                           'transport_status', 'request_elapsed_seconds', 'usage', 'finish_reason')}
                           for result in results],
               'measurement_scope': 'local elapsed time and response-reported usage; no throughput/cache baseline'}
    write_json(output / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--requests')
    mode.add_argument('--view-response')
    parser.add_argument('--endpoint')
    parser.add_argument('--output', required=True)
    parser.add_argument('--concurrency', type=int, default=2)
    parser.add_argument('--timeout', type=float, default=45)
    args = parser.parse_args()
    try:
        if args.requests and not args.endpoint:
            raise ValueError('request batches require an explicit endpoint')
        summary = annotate(args) if args.view_response else run(args)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('error: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False))
    return 1 if summary.get('failure_count') or summary.get('artifact_status') == 'invalid_response' else 0


if __name__ == '__main__':
    raise SystemExit(main())
