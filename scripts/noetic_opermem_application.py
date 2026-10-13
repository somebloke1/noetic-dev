"""Owned reviewed application launch transport; Opermem retains semantic authority."""
from __future__ import annotations

from argparse import Namespace
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import threading
import tempfile

from scripts import noetic_opermem as native, noetic_opermem_scope as owned
from scripts import noetic_processes as processes, noetic_purpose_binding as purposes
from scripts import noetic_run as runtime
from scripts.noetic_scope import Scope, ScopeError
from scripts.noetic_storage import ensure_private_directory, open_private
from scripts.noetic_opermem_component import (COMPONENT, EXECUTABLES, component_manifest,
                                             validate_component, check_platform, host_configuration)

BACKEND = 'opermem-reviewed'
SELECTORS = ('parent_id', 'formulation_id', 'warrant_id', 'condition_ids', 'judgment_ids',
             'practical_question_id', 'option_id', 'option_ids', 'evaluation_id', 'decision_id',
             'judgment_basis_ids', 'supersedes_decision_id', 'predecessor_evaluation_id',
             'plan_id', 'step_id', 'occasion_kind', 'occasion_id')
OPERATION_INPUTS = {
    'question': ('occasion_kind', 'occasion_id'), 'insight': ('parent_id',), 'formulation': ('parent_id',),
    'reflection': ('parent_id',), 'conditional-structure': ('parent_id', 'formulation_id'),
    'checking': ('parent_id', 'warrant_id'), 'judgment': ('warrant_id', 'condition_ids'),
    'practical-question': ('judgment_ids',), 'practical-inquiry': ('practical_question_id',),
    'practical-insight': ('practical_question_id', 'option_id'), 'deliberation': ('practical_question_id', 'option_ids'),
    'decision': ('evaluation_id', 'judgment_basis_ids', 'supersedes_decision_id', 'predecessor_evaluation_id'),
    'planning': ('decision_id', 'judgment_basis_ids'), 'acting': ('plan_id', 'step_id'),
}
EVIDENCE_INPUTS = ('checking_spec', 'checking_context', 'observed_run_id', 'observed_step',
                   'observation_evidence', 'observation_manifest_sha256')


def selector_u64(value, label):
    if isinstance(value, str):
        if not (1 <= len(value) <= 20 and value.isascii() and value.isdecimal() and value[0] != '0'):
            raise ScopeError(f'{label} must be a canonical positive decimal u64')
        value = int(value)
    if type(value) is not int or not 0 < value < 2**64:
        raise ScopeError(f'{label} must be a positive u64')
    return value


def selector_request(body):
    operation = body.get('operation')
    if operation not in ('insight', 'formulation', 'reflection', 'judgment', 'conditional-structure', 'checking', 'practical-question', 'practical-inquiry', 'deliberation'):
        return body
    selectors = body.get('selectors', {})
    if not isinstance(selectors, dict):
        return body
    normalized = deepcopy(body)
    if operation == 'judgment':
        warrant = selector_u64(selectors.get('warrant_id'), 'Warrant ID')
        conditions = selectors.get('condition_ids')
        if not isinstance(conditions, list) or not conditions:
            raise ScopeError('Condition IDs require a nonempty complete ID set')
        conditions = [selector_u64(value, 'Condition ID') for value in conditions]
        if any(a >= b for a, b in zip(conditions, conditions[1:])):
            raise ScopeError('Condition IDs must be in strictly sorted unique native ID order')
        normalized['selectors'].update(warrant_id=warrant, condition_ids=conditions)
    elif operation == 'practical-question':
        judgments = selectors.get('judgment_ids')
        if not isinstance(judgments, list) or not judgments:
            raise ScopeError('Judgment IDs require a nonempty explicitly selected ID list')
        judgments = [selector_u64(value, 'Judgment ID') for value in judgments]
        if any(a >= b for a, b in zip(judgments, judgments[1:])):
            raise ScopeError('Judgment IDs must be in strictly sorted unique native ID order')
        normalized['selectors'].update(judgment_ids=judgments)
    elif operation == 'practical-inquiry':
        normalized['selectors']['practical_question_id'] = selector_u64(selectors.get('practical_question_id'), 'PracticalQuestion ID')
    elif operation == 'deliberation':
        normalized['selectors']['practical_question_id'] = selector_u64(selectors.get('practical_question_id'), 'PracticalQuestion ID')
        options = selectors.get('option_ids')
        if not isinstance(options, list) or len(options) < 2:
            raise ScopeError('Option IDs require the complete current set of at least two explicitly selected IDs')
        options = [selector_u64(value, 'Option ID') for value in options]
        if any(a >= b for a, b in zip(options, options[1:])):
            raise ScopeError('Option IDs must be in strictly sorted unique native ID order')
        normalized['selectors'].update(option_ids=options)
    else:
        normalized['selectors']['parent_id'] = selector_u64(selectors.get('parent_id'), 'Parent ID')
        if operation == 'conditional-structure':
            normalized['selectors']['formulation_id'] = selector_u64(selectors.get('formulation_id'), 'Formulation ID')
        if operation == 'checking':
            normalized['selectors']['warrant_id'] = selector_u64(selectors.get('warrant_id'), 'Warrant ID')
    return normalized


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(native.canonical(value)).hexdigest()


def immutable(path, value):
    data = native.canonical(value) + b'\n'
    if path.exists():
        if path.read_bytes() != data:
            raise ScopeError('Original launch evidence differs from the retained command')
        return
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != data:
                raise ScopeError('Original launch evidence differs from the retained command')
    finally:
        Path(temporary).unlink(missing_ok=True)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save(path, value):
    processes.save(path, value)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def catalog_definition():
    reference = owned.definition()
    return {'backend': BACKEND, 'pattern': BACKEND, 'definition_ref': reference,
            'definition': reference['descriptor'], 'modes': ['inquiry'],
            'capabilities': {'create_instance': True, 'explicit_backing': True, 'independent_review': True,
                             'apply': False, 'pause': False, 'continue_conversation': False},
            'operations': [{'id': op, 'available': True, 'requires_native_prerequisites': True,
                            'inputs': list(OPERATION_INPUTS[op]), 'evidence_inputs': ['checking_spec', 'checking_context'] if op == 'checking' else ['observed_run_id', 'observed_step', 'observation_evidence', 'observation_manifest_sha256'] if op == 'acting' else []} for op in owned.OPERATIONS]}


class ReviewedApplication:
    def __init__(self, app):
        self.app = app
        self.adapter = owned.OpermemScope(app.namespace_path)

    def scope(self, selection):
        return self.app.operation_scope(selection)

    def registrations(self, selection):
        scope = self.scope(selection)
        roots = (scope.effort_root,) if scope.effort_root else scope.target_efforts
        result = []
        for event in owned._history(self.adapter.store):
            if (event['kind'] != 'opermem-store-bound' or event['source_ref'].get('adapter') != owned.ADAPTER
                    or event['effort'] not in roots):
                continue
            ref = event['data']['store_ref']
            try:
                self.adapter.validate_store(ref, ref['effort_root'])
                ready = host_configuration(ref['host'])
                state = 'registered-unverified'
                if not ready['available']:
                    state = 'unavailable'
                observed = [p for p in self.adapter.inspect_preparations(effort_root=ref['effort_root'])
                            if p.get('store_ref', {}).get('id') == ref['id']]
                identities = []
                for preparation in observed:
                    if 'run_id' not in preparation:
                        continue
                    event = self.adapter._event('run:' + preparation['run_id'] + ':native-bound')
                    if event is not None:
                        cut = event['data']['link']['context']['pinned_canonical_cut']
                        identity = {'directory': ref['directory'], 'workspace_id': cut['workspace_id'], 'authority_scope_id': cut['authority_scope_id']}
                        if identity not in identities:
                            identities.append(identity)
                if identities and ready['available']:
                    state = 'registered-observed'
                result.append({'store_ref': ref, 'state': state, 'configuration': ready,
                               'observed_executions': len(observed), 'native_identity': identities[0] if len(identities) == 1 else None,
                               'retained_native_identities': identities, 'current_native_standing': 'unobserved',
                               'notice': ref['lineage']})
            except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
                result.append({'store_ref': ref, 'state': 'unavailable', 'error': str(exc)})
        return {'stores': result, 'selection': selection, 'component': host_configuration(self.app.opermem_host)}

    def register(self, body):
        if set(body) != {'command_id', 'effort_root', 'directory'}:
            raise ScopeError('Backing requires command_id, existing effort_root and explicit absolute directory')
        self.scope({'kind': 'effort', 'effort_root': body['effort_root']})
        directory = Path(body['directory']).expanduser()
        if not directory.is_absolute():
            raise ScopeError('Select an absolute native backing directory')
        ready = host_configuration(self.app.opermem_host)
        if not ready['available']:
            raise ScopeError(ready['reason'])
        with self.app.mutation():
            ref = self.adapter.bind_store(command_id=body['command_id'], effort_root=body['effort_root'],
                                          store_path=directory, host=ready['host'])
        return {'store_ref': ref, 'state': 'registered-unverified', 'native_started': False}

    def create(self, body):
        allowed = {'backend', 'pattern', 'definition_ref', 'command_id', 'effort_root', 'initiator', 'intent',
                   'environment', 'origin', 'human_ref', 'delegator', 'parent_instance'}
        if (set(body) - allowed or any(body.get(k, BACKEND) != BACKEND for k in ('backend', 'pattern'))
                or body.get('definition_ref', owned.definition()) != owned.definition()):
            raise ScopeError('Select the exact maintained reviewed definition')
        values = {k: v for k, v in body.items() if k not in ('backend', 'pattern', 'definition_ref')}
        with self.app.mutation():
            instance = self.adapter.create_instance(**values)
        return {'discipline': instance, 'backend': BACKEND}

    def preflight(self, body):
        body = selector_request(body)
        allowed = {'backend', 'pattern', 'definition_ref', 'command_id', 'effort_root', 'discipline_id', 'environment',
                   'origin', 'human_ref', 'delegator', 'task', 'workspace', 'sources', 'store_id', 'purpose_ref',
                   'operation', 'mode', 'client', 'model', 'qa_model', 'thinking', 'timeout', 'selectors', 'qualification', *EVIDENCE_INPUTS}
        if set(body) - allowed:
            raise ScopeError('Unknown reviewed launch option; namespace/raw Telos/store/host overrides are not accepted')
        if (any(body.get(k, BACKEND) != BACKEND for k in ('backend', 'pattern'))
                or body.get('definition_ref', owned.definition()) != owned.definition()):
            raise ScopeError('Reviewed definition changed; reselect its current instance')
        if (not isinstance(body.get('command_id'), str) or not body['command_id'].strip()
                or len(body['command_id']) > 256 or '\0' in body['command_id']):
            raise ScopeError('Reviewed launch requires a bounded explicit command_id')
        task = body.get('task')
        if not isinstance(task, str) or not task.strip() or '\0' in task or len(task.encode()) > 32768:
            raise ScopeError('Reviewed task requires bounded nonempty text')
        workspace = Path(body.get('workspace', '')).expanduser()
        if not workspace.is_absolute() or not workspace.is_dir():
            raise ScopeError('Choose an existing absolute workspace')
        workspace = workspace.resolve(strict=True)
        assignment = {k: body[k] for k in ('effort_root', 'discipline_id', 'environment', 'origin', 'human_ref', 'delegator') if k in body}
        assignment['namespace_path'] = str(self.app.namespace_path)
        self.adapter.validate_request(assignment, workspace)
        selected = self.registrations({'kind': 'effort', 'effort_root': assignment['effort_root']})
        refs = [r['store_ref'] for r in selected['stores'] if r['store_ref']['id'] == body.get('store_id')]
        if len(refs) != 1:
            raise ScopeError('Select exactly one native store registered to this effort')
        ref = self.adapter.validate_store(refs[0], assignment['effort_root'])
        ready = host_configuration(ref['host'])
        if not ready['available']:
            raise ScopeError(ready['reason'])
        native._private_selection(Path(ref['directory']))
        native._private_selection(self.app.root)
        if body.get('mode', 'inquiry') != 'inquiry':
            raise ScopeError('Application reviewed work currently supports read-only inquiry; development Apply requires the maintained controller')
        operation = body.get('operation', 'question')
        if operation not in owned.OPERATIONS:
            raise ScopeError('Unknown native operation')
        selectors = body.get('selectors', {})
        if not isinstance(selectors, dict) or set(selectors) - set(OPERATION_INPUTS[operation]):
            raise ScopeError('Unknown operation selector')
        selection = {k: selectors.get(k) for k in SELECTORS}
        purpose = native.purpose_for(operation, selection.pop('parent_id'), selection.pop('formulation_id'), **selection)
        timeout = body.get('timeout', 900)
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 1 <= timeout <= 7200:
            raise ScopeError('Timeout must be 1 through 7200 seconds')
        client = body.get('client', 'pi')
        if client not in ('pi', 'opencode'):
            raise ScopeError('Select Pi or OpenCode')
        for key in ('model', 'qa_model'):
            value = body.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip() or any(c in value for c in '\0\r\n')):
                raise ScopeError('Selected models must be explicit text or absent')
        thinking = body.get('thinking')
        if thinking is not None and (client != 'pi' or thinking not in ('off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max')):
            raise ScopeError('Only maintained Pi reasoning controls are supported')
        qualification = body.get('qualification')
        if qualification is not None:
            from scripts import noetic_genus
            packet = noetic_genus.validate_packet(qualification, task, body.get('model'))
            evidence = packet['consumer_decision']['selected_evidence']
            controls = evidence['controls'] if evidence else {}
            if (controls and client != 'pi') or (thinking and 'reasoning_effort' in controls and controls['reasoning_effort'] != thinking):
                raise ScopeError('Qualification controls differ from selected client/thinking')
        frozen_purpose = None
        if body.get('purpose_ref') is not None:
            resolver = self.app.purposes()
            frozen_purpose = purposes.prepare(body['purpose_ref'], purposes.configuration(resolver), assignment)
        sources = body.get('sources', [])
        if not isinstance(sources, list) or len(sources) > 64:
            raise ScopeError('Select at most 64 explicit source paths')
        operation_evidence = self.operation_evidence(body, assignment, purpose, ref)
        fingerprints, recall_sources, total = [], [], 0
        for index, value in enumerate(sources):
            if isinstance(value, dict):
                source = self.recall_source(value, assignment)
                data = native.canonical(source) + b'\n'
                total += len(data)
                if total > 1024 * 1024:
                    raise ScopeError('Explicit host/recall sources exceed 1 MiB')
                path = self.launch_dir(body['command_id']) / 'source-selections' / (str(index) + '.json')
                recall_sources.append({'path': str(path), 'record': source})
                fingerprints.append({'path': str(path), 'sha256': hashlib.sha256(data).hexdigest()})
                continue
            if not isinstance(value, str) or not Path(value).expanduser().is_absolute():
                raise ScopeError('Sources must be explicit absolute retained file selections')
            path = self.source_path(value, assignment)
            if not path.is_file():
                raise ScopeError('Host source selection must be a regular file')
            with path.open('rb') as stream:
                data = stream.read(1024 * 1024 + 1)
            total += len(data)
            if total > 1024 * 1024:
                raise ScopeError('Explicit host sources exceed 1 MiB')
            fingerprints.append({'path': str(path), 'sha256': hashlib.sha256(data).hexdigest()})
        return {'body': deepcopy(body), 'assignment': assignment, 'store_ref': ref,
                'workspace': str(workspace), 'purpose': frozen_purpose, 'source_fingerprints': fingerprints, 'recall_sources': recall_sources,
                'native_purpose': purpose, 'operation_evidence': operation_evidence, 'component': {'host': ready['host'], 'child': ready['child']}}

    def recall_source(self, value, assignment):
        if set(value) - {'source_id', 'source_text_sha256', 'selection'} or not {'source_id', 'source_text_sha256'} <= value.keys():
            raise ScopeError('Recall source requires its exact source identity and original text fingerprint')
        selection = deepcopy(value.get('selection', {'kind': 'effort', 'effort_root': assignment['effort_root']}))
        if not isinstance(selection, dict) or selection.get('kind') not in ('effort', 'ordinal', 'session'):
            raise ScopeError('Owned recall selection must be effort, ordinal or exact session')
        if selection.get('effort_root', assignment['effort_root']) != assignment['effort_root']:
            raise ScopeError('Recall selection belongs to another effort')
        selection['effort_root'] = assignment['effort_root']
        if selection['kind'] in ('ordinal', 'session'):
            self.adapter.store.position(selection.get('ordinal'), scope=Scope.effort(assignment['effort_root']))
        collection = self.app.collect(selection)
        matches = [s for s in collection['sources'] if s['source_id'] == value['source_id']]
        if len(matches) != 1 or matches[0]['source_text_sha256'] != value['source_text_sha256']:
            raise ScopeError('Selected recall source is missing, foreign or changed; refresh the scoped source selection')
        return {'kind': 'external-scoped-recall-evidence', 'selection': selection, 'source': matches[0],
                'native_retained_experience': False, 'authority': 'historical retained source; no current native admission or promotion'}

    def source_path(self, value, assignment):
        if not isinstance(value, str) or not Path(value).expanduser().is_absolute():
            raise ScopeError('Select an explicit absolute source path')
        path = Path(value).expanduser().resolve(strict=True)
        if not path.is_file() and not path.is_dir():
            raise ScopeError('Select an existing regular file or retained archive directory')
        if path.is_relative_to(self.app.root):
            relative = path.relative_to(self.app.root)
            if not relative.parts or relative.parts[0].startswith('.'):
                raise ScopeError('Application internal state is not an explicit source selection')
            self.app.run_authority(self.app.root / relative.parts[0], {'kind': 'effort', 'effort_root': assignment['effort_root']})
        return path

    def operation_evidence(self, body, assignment, purpose, store_ref):
        operation = body.get('operation', 'question')
        selected = {k: body[k] for k in EVIDENCE_INPUTS if body.get(k) is not None}
        if operation not in ('checking', 'acting'):
            if selected:
                raise ScopeError('Closed evidence selectors apply only to checking or acting')
            return None
        if operation == 'checking':
            if set(selected) != {'checking_spec', 'checking_context'}:
                raise ScopeError('Checking requires an explicit closed specification and retained checking context source')
            from scripts import noetic_opermem_checking as checking
            paths = {k: self.source_path(v, assignment) for k, v in selected.items()}
            if any(not p.is_file() or p.stat().st_size > 1024 * 1024 for p in paths.values()):
                raise ScopeError('Checking specification/context require bounded regular source files')
            spec, context = (checking.load(paths[k]) for k in ('checking_spec', 'checking_context'))
            native.validate_context(context, 'checking', purpose['condition_id'], warrant_id=purpose['warrant_id'])
            checking.validate_spec(spec, context, purpose['condition_id'], purpose['warrant_id'])
            fingerprints = [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths.values()]
            for source in spec['sources']:
                path = self.source_path(source['path'], assignment)
                with path.open('rb') as stream:
                    checksum = hashlib.file_digest(stream, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else hashlib.sha256(stream.read()).hexdigest()
                if checksum != source['sha256']:
                    raise ScopeError('Checking source/command dependency changed before effects')
                fingerprints.append({'path': str(path), 'sha256': checksum})
            if Path(spec['command']['cwd']).resolve(strict=True) != Path(body['workspace']).resolve(strict=True):
                raise ScopeError('Checking command cwd must be this execution workspace')
            return {'paths': {k: str(v) for k, v in paths.items()}, 'source_fingerprints': fingerprints}
        if set(selected) - {'observed_run_id', 'observed_step', 'observation_evidence', 'observation_manifest_sha256'}:
            raise ScopeError('Acting accepts only retained occurrence selectors')
        from scripts import noetic_act_observation as observation
        scope = {'kind': 'effort', 'effort_root': assignment['effort_root']}
        run_id = selected.get('observed_run_id')
        if run_id is not None:
            if {'observation_evidence', 'observation_manifest_sha256'} & selected.keys():
                raise ScopeError('Choose a retained run or an immutable archive')
            if not isinstance(run_id, str) or len(run_id) != 32 or any(c not in '0123456789abcdef' for c in run_id):
                raise ScopeError('Select the exact retained occurrence run identity')
            run = self.app.root / run_id
            self.app.run_authority(run, scope)
            manifest, files, _ = observation._snapshot(run, selected.get('observed_step', 'work'))
            if not manifest['selected']['occurred']:
                raise ScopeError('Selected evidence does not establish an occurred external act')
            return {'observed_run': str(run), 'observed_step': selected.get('observed_step', 'work'),
                    'snapshot': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
                    'selected': manifest['selected']}
        if set(selected) != {'observation_evidence', 'observation_manifest_sha256'}:
            raise ScopeError('Archived acting requires explicit evidence path and original manifest digest')
        archive = self.source_path(selected['observation_evidence'], assignment)
        manifest = observation.revalidate(archive, selected['observation_manifest_sha256'], current=False)
        source_run = Path(manifest['source_run_dir'])
        if source_run.parent.resolve() != self.app.root:
            raise ScopeError('Archive source has no retained owned application correspondence')
        self.app.run_authority(source_run, scope)
        if not manifest['selected']['occurred']:
            raise ScopeError('Archive does not establish an occurred external act')
        return {'observation_evidence': str(archive), 'observation_manifest_sha256': selected['observation_manifest_sha256']}

    def launch_dir(self, command_id):
        return self.app.root / '.opermem-launches' / digest({'namespace_path': str(self.app.namespace_path), 'command_id': command_id})

    def start(self, body):
        body = selector_request(body)
        command_id = body.get('command_id')
        if not isinstance(command_id, str) or not command_id.strip() or len(command_id) > 256 or '\0' in command_id:
            raise ScopeError('Reviewed launch requires a bounded explicit command_id')
        directory = self.launch_dir(command_id)
        if directory.exists():
            with self.app.mutation():
                return self.retained_command(directory, body)
        frozen = self.preflight(body)
        with self.app.mutation():
            if directory.exists():
                return self.retained_command(directory, body)
            with self.app.admission() as slot:
                ensure_private_directory(directory)
                immutable(directory / 'assignment.json', {'namespace_path': str(self.app.namespace_path),
                    'namespace': self.adapter.store.namespace, 'effort_root': body['effort_root'],
                    'command_id': body['command_id'], 'request_digest': digest(frozen)})
                immutable(directory / 'request.json', {'request_digest': digest(frozen), 'frozen': frozen,
                    'application': {'runs_dir': str(self.app.root), 'namespace_path': str(self.app.namespace_path),
                                    'telos_db': str(self.app.telos_db), 'telos_source': str(self.app.telos_source) if self.app.telos_source else None,
                                    'purposes_root': str(self.app.purposes_root) if self.app.purposes_root else None,
                                    'opermem_host': str(self.app.opermem_host) if self.app.opermem_host else None}})
                save(directory / 'receipt.json', {'launch_id': directory.name, 'command_id': body['command_id'],
                     'request_digest': digest(frozen), 'backend': BACKEND, 'effort_root': body['effort_root'],
                     'status': 'queued', 'execution_id': None, 'run_id': None, 'queued_at': stamp()})
                lock = open_private(directory / 'driver.lock', 'a')
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    immutable(directory / 'launch-attempt.json', {'attempted_at': stamp(), 'relaunch': False})
                    environment = dict(os.environ)
                    environment.pop('USER_PROVIDED_PASSWORD', None)
                    environment['PYTHONDONTWRITEBYTECODE'] = '1'
                    with open_private(directory / 'driver.log', 'ab') as output:
                        child = subprocess.Popen([sys.executable, '-B', '-m', 'scripts.noetic_opermem_application',
                            'drive', str(directory), str(lock.fileno()), str(slot.fileno())],
                            cwd=Path(__file__).resolve().parents[1], env=environment, stdin=subprocess.DEVNULL,
                            stdout=output, stderr=output, start_new_session=True, pass_fds=(lock.fileno(), slot.fileno()))
                    self.app.children = [p for p in self.app.children if p.poll() is None] + [child]
                    threading.Thread(target=child.wait, daemon=True).start()
                except OSError as exc:
                    receipt = json.loads((directory / 'receipt.json').read_text())
                    save(directory / 'receipt.json', {**receipt, 'status': 'failed', 'error': str(exc), 'finished_at': stamp()})
                finally:
                    lock.close()
        return self.launch_receipt(directory, {'kind': 'effort', 'effort_root': body['effort_root']})

    def retained_command(self, directory, body):
        self.launch_owner(directory, {'kind': 'effort', 'effort_root': body.get('effort_root')})
        original = json.loads((directory / 'request.json').read_text())
        if original['frozen']['body'] != body:
            from scripts.noetic_application import ApplicationError
            raise ApplicationError(409, 'command_id already retains a different reviewed request')
        return self.launch_receipt(directory, {'kind': 'effort', 'effort_root': body['effort_root']})

    def launch_owner(self, directory, selection):
        from scripts.noetic_application import contained, ApplicationError
        contained(directory, self.app.root / '.opermem-launches')
        contained(directory / 'assignment.json', directory)
        header = json.loads((directory / 'assignment.json').read_text())
        if header['namespace_path'] != str(self.app.namespace_path) or header['namespace'] != self.adapter.store.namespace:
            raise ScopeError('Launch belongs to another namespace')
        self.scope(selection)
        if selection['kind'] == 'effort' and header['effort_root'] != selection['effort_root']:
            raise ApplicationError(403, 'Requested effort does not own this launch')
        return header

    def launch_receipt(self, directory, selection, *, restore=False):
        header = self.launch_owner(directory, selection)
        from scripts.noetic_application import contained, lock_held
        contained(directory, self.app.root / '.opermem-launches')
        for name in ('request.json', 'receipt.json', 'prepared-observation.json', 'process.json', 'driver.lock'):
            contained(directory / name, directory)
        original = json.loads((directory / 'request.json').read_text())
        frozen = original['frozen']
        if any(header[key] != expected for key, expected in (('effort_root', frozen['assignment']['effort_root']),
                ('command_id', frozen['body']['command_id']), ('request_digest', original['request_digest']))):
            raise ScopeError('Launch authority header differs from its frozen request')
        if frozen['assignment']['namespace_path'] != str(self.app.namespace_path):
            raise ScopeError('Launch belongs to another namespace')
        self.scope(selection)
        if selection['kind'] == 'effort' and frozen['assignment']['effort_root'] != selection['effort_root']:
            from scripts.noetic_application import ApplicationError
            raise ApplicationError(403, 'Requested effort does not own this launch')
        if original['request_digest'] != digest(frozen):
            raise ScopeError('Frozen launch request changed')
        receipt_path = directory / 'receipt.json'
        receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {
            'launch_id': directory.name, 'command_id': frozen['body']['command_id'], 'request_digest': original['request_digest'],
            'backend': BACKEND, 'effort_root': frozen['assignment']['effort_root'], 'status': 'uncertain', 'execution_id': None, 'run_id': None}
        observation = directory / 'prepared-observation.json'
        if observation.exists():
            original_observation = json.loads(observation.read_text())
            if original_observation['request_digest'] != original['request_digest']:
                raise ScopeError('Preparation observation belongs to a different frozen request')
            binding = original_observation['binding']
            self.adapter.validate_binding(binding, revalidate_purpose=False)
            if (binding['assignment'] != frozen['assignment'] or binding['store_ref'] != frozen['store_ref']
                    or binding['task']['text'] != frozen['body']['task']
                    or binding['workspace'] != frozen['workspace'] or binding['runs_dir'] != str(self.app.root)
                    or binding['operation'] != frozen['body'].get('operation', 'question') or binding['inquiry'] is not True
                    or binding['client'] != frozen['body'].get('client', 'pi')
                    or binding['model'] != frozen['body'].get('model')
                    or binding['review_model'] != (frozen['body'].get('qa_model') or frozen['body'].get('model'))
                    or binding['purpose_ref'] != (frozen['purpose'] or {}).get('purpose_ref')
                    or binding['purpose_config'] != (frozen['purpose'] or {}).get('purpose_config')
                    or [{'path': s['path'], 'sha256': s['sha256']} for s in binding['host_sources']] != frozen['source_fingerprints']):
                raise ScopeError('Original preparation observation differs from its launch')
            receipt.update(execution_id=binding['execution_id'], run_id=binding['run_id'])
            if restore:
                save(receipt_path, receipt)
        else:
            if receipt.get('execution_id') is not None or receipt.get('run_id') is not None:
                receipt.update(status='uncertain', execution_id=None, run_id=None,
                    correlation_gap='Original prepared-observation is unavailable; derived execution mapping cannot authorize correlation.')
        expected_receipt = {'launch_id': directory.name, 'command_id': frozen['body']['command_id'],
                            'request_digest': original['request_digest'], 'backend': BACKEND, 'effort_root': frozen['assignment']['effort_root']}
        if any(receipt.get(k) != v for k, v in expected_receipt.items()):
            raise ScopeError('Launch receipt differs from its frozen command identity')
        process = processes.inspect(directory / 'process.json')
        locked = lock_held(directory / 'driver.lock', directory)
        if receipt['status'] not in ('finished', 'failed') and not locked and (directory / 'launch-attempt.json').exists():
            receipt['status'] = 'uncertain'
            receipt['reason'] = 'No driver owns unresolved launch effects; inspect or explicitly recover retained correspondence. Actors are never automatically relaunched.'
        return {**receipt, 'driver_owned': locked, 'process': process,
                'prepared_observed': observation.exists(), 'execution_claim': receipt.get('execution_id') is not None}

    def launches(self, selection):
        self.scope(selection)
        rows, diagnostics = [], []
        parent = self.app.root / '.opermem-launches'
        for directory in sorted(parent.iterdir()) if parent.exists() else ():
            try:
                rows.append(self.launch_receipt(directory, selection))
            except Exception as exc:
                if getattr(exc, 'status', None) != 403:
                    diagnostics.append({'launch_id': directory.name, 'error': str(exc)})
        return {'launches': rows, 'diagnostics': diagnostics, 'selection': selection}

    def binding(self, run_id, selection):
        """Canonical ownership lookup precedes any task, link, or actor content."""
        self.scope(selection)
        with self.adapter.store._connection() as db:
            rows = db.execute('SELECT e.id,e.native_ref FROM executions e JOIN disciplines d ON d.id=e.discipline_id WHERE ' +
                ('d.effort=?' if selection['kind'] == 'effort' else '1=1'),
                (selection['effort_root'],) if selection['kind'] == 'effort' else ()).fetchall()
        for execution_id, raw in rows:
            base = json.loads(raw)
            if base.get('version') == owned.VERSION and base.get('run_id') == run_id:
                if base.get('runs_dir') != str(self.app.root):
                    raise ScopeError('Reviewed run belongs to another runs directory')
                return {**base, 'execution_id': execution_id}
        return None

    def guard_binding_files(self, binding):
        from scripts.noetic_application import contained
        run = contained(Path(binding['run_dir']), self.app.root)
        contained(Path(binding['preparation_path']), self.app.root)
        for name in ('events.sqlite3', 'options.json', 'opermem-scope.json', 'opermem-link.json',
                     'opermem-receipt.json', 'opermem-pending.json', 'work.stdout.log', 'review.stdout.log',
                     'work.md', 'review.md'):
            contained(run / name, run)

    def authority(self, run_id, selection):
        binding = self.binding(run_id, selection)
        if binding is None:
            return None
        self.guard_binding_files(binding)
        self.adapter.validate_binding(binding, revalidate_purpose=False)
        run = Path(binding['run_dir'])
        correlation = self.adapter.correspondence(binding)
        if (run / 'events.sqlite3').exists():
            result = native.owned_correspondence(run)
        else:
            result = {**correlation, 'namespace_path': binding['namespace_path'], 'initiator': binding['initiator']}
        return {**result, 'backend': BACKEND}

    def summaries(self, selection):
        self.scope(selection)
        roots = [selection['effort_root']] if selection['kind'] == 'effort' else list(self.scope(selection).target_efforts)
        result, warnings = [], []
        for root in roots:
            with self.adapter.store._connection() as db:
                rows = db.execute('SELECT e.id,e.native_ref FROM executions e JOIN disciplines d ON d.id=e.discipline_id WHERE d.effort=? ORDER BY e.id', (root,)).fetchall()
            for execution_id, raw in rows:
                base = json.loads(raw)
                if base.get('version') != owned.VERSION or base.get('runs_dir') != str(self.app.root):
                    continue
                binding = {**base, 'execution_id': execution_id}
                try:
                    correlation = self.authority(base['run_id'], {'kind': 'effort', 'effort_root': root})
                    info = self.runtime(binding, correlation)
                    result.append({'run_id': base['run_id'], 'directory': base['run_dir'], 'backend': BACKEND,
                        'goal': base['task']['text'], 'workspace': base['workspace'], 'state': correlation['run_status'],
                        'last_event_at': self.last_event(binding), 'goal_ref': None, 'telos': base['purpose_ref'],
                        'application': info, 'correspondence': correlation, 'population': self.population(binding, correlation),
                        'attention': [{'kind': 'preparation-failed', 'message': e['data']['error']} for e in correlation['preparation_failures']]})
                except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                    warnings.append('Run ' + base['run_id'] + ': assigned reviewed diagnostic: ' + str(exc))
                    result.append({'run_id': base['run_id'], 'backend': BACKEND, 'state': 'unavailable',
                        'goal': None, 'workspace': None, 'last_event_at': '', 'population': [], 'attention': [],
                        'correspondence': {'correlation_status': 'unavailable', 'execution_id': execution_id, 'effort_root': root, 'error': str(exc)}})
        return result, warnings

    def last_event(self, binding):
        events = list(owned._history(self.adapter.store))
        return next((e.get('at', '') for e in reversed(events) if e.get('execution_id') == binding['execution_id']), '')

    def population(self, binding, correlation):
        return [{'id': p['ordinal'], 'actor_id': p['ordinal'], 'ordinal': p['ordinal'], 'role': p['step'],
                 'status': p['session_status'] or 'reserved', 'target': p['target'], 'session_ref': p['native_session_ref'],
                 'native_session_ref': p['native_session_ref'], 'client': binding['client'],
                 'position_status': p['position_status'], 'observation': p['observation'],
                 'configured_model': binding['review_model'] if p['step'] == 'review' else binding['model'],
                 'backend': BACKEND, 'capabilities': {'transcript': p['observation'] is not None, 'send': False, 'delegate': False, 'resume': False}}
                for p in correlation['participants']]

    def runtime(self, binding, correlation):
        run = Path(binding['run_dir'])
        rows = self.launches({'kind': 'effort', 'effort_root': binding['effort_root']})['launches']
        launch = next((r for r in rows if r.get('run_id') == binding['run_id']), None)
        alive = bool(launch and launch['driver_owned'])
        receipt = json.loads((run / 'opermem-receipt.json').read_text()) if (run / 'opermem-receipt.json').exists() else None
        pending = (run / 'opermem-pending.json').exists()
        state = correlation['run_status']
        projected = runtime.project(runtime.read_events(run)) if (run / 'events.sqlite3').exists() else {}
        activity = 'running' if alive else 'failed' if state == 'preparation-failed' else 'terminal' if state in ('accepted', 'rejected', 'completed', 'failed', 'blocked', 'cancelled') else 'intervention'
        return {'backend': BACKEND, 'supported': True, 'activity': activity, 'can_advance': False,
                'reason': 'Independent reviewed inquiry; driver ownership proves process ownership, not model progress.' if alive else
                          'Inspect retained evidence; no automatic actor continuation. Native recovery is separate from review.',
                'driver': launch, 'configuration': {'pattern': BACKEND, 'mode': 'inquiry', 'operation': binding['operation'],
                    'client': binding['client'], 'model': binding['model'], 'qa_model': binding['review_model'],
                    'workspace': binding['workspace'], 'purpose_ref': binding['purpose_ref'], 'store_id': binding['store_ref']['id']},
                'review': {'outcome': projected.get('review', {}).get('verdict') if projected.get('review') else None, 'run_state': state, 'native_acceptance_equivalent': False},
                'native': {'receipt': receipt, 'receipt_retained': receipt is not None, 'pending': pending,
                           'disposition': 'receipt-retained' if receipt is not None else 'pending' if pending else 'not-submitted',
                           'telos': projected.get('telos_result'), 'telos_error': projected.get('telos_error'),
                           'semantic_authority': 'Opermem', 'current_standing': 'unobserved'},
                'actions': {'inspect': True, 'reuse_setup': True, 'recover_correlation': not alive,
                            'recover_contribution': not alive and (pending or receipt is not None),
                            'pause': False, 'apply': False, 'continue_conversation': False, 'stop': False},
                'unavailable_controls': 'Pause, Stop, Apply and conversational continuation require additional execution contracts.'}

    def detail(self, run_id, selection):
        binding = self.binding(run_id, selection)
        if binding is None:
            raise ScopeError('Selected effort does not own the requested reviewed execution')
        correlation = self.authority(run_id, selection)
        run = Path(binding['run_dir'])
        events = runtime.read_events(run) if (run / 'events.sqlite3').exists() else []
        artifacts = {}
        for name in ('task.md', 'work.md', 'review.md', 'opermem-link.json', 'opermem-scope.json',
                     'opermem-receipt.json', 'opermem-pending.json', 'options.json'):
            path = run / name
            if path.exists():
                from scripts.noetic_application import contained
                contained(path, run)
                with path.open('rb') as stream:
                    data = stream.read(1024 * 1024 + 1)
                artifacts[name] = {'source_path': str(path), 'text': data[:1024 * 1024].decode('utf8', errors='replace'),
                                   'truncated': len(data) > 1024 * 1024}
        return {'status': {'run_id': run_id, 'goal': binding['task']['text'], 'workspace': binding['workspace'],
                          'state': correlation['run_status'], 'backend': BACKEND}, 'backend': BACKEND,
                'events': events, 'artifacts': artifacts, 'controller': None, 'controller_path': None,
                'correspondence': correlation, 'preparation': binding,
                'population': self.population(binding, correlation), 'application': self.runtime(binding, correlation)}

    def reuse(self, run_id, selection):
        binding = self.binding(run_id, selection)
        if binding is None:
            raise ScopeError('Owned reviewed execution not found')
        self.authority(run_id, selection)
        selected_sources = [s['path'] for s in binding['host_sources']]
        launch_root = self.app.root / '.opermem-launches'
        for directory in launch_root.iterdir() if launch_root.exists() else ():
            try:
                self.launch_owner(directory, selection)
            except Exception as exc:
                if getattr(exc, 'status', None) == 403:
                    continue
                raise
            observation = directory / 'prepared-observation.json'
            if observation.exists() and json.loads(observation.read_text())['binding']['run_id'] == run_id:
                selected_sources = deepcopy(json.loads((directory / 'request.json').read_text())['frozen']['body'].get('sources', []))
                break
        return {'source_run_id': run_id, 'fields': {'backend': BACKEND, 'pattern': BACKEND, 'mode': 'inquiry',
            'task': binding['task']['text'], 'workspace': binding['workspace'], 'operation': binding['operation'],
            'client': binding['client'], 'model': binding['model'], 'qa_model': binding['review_model'],
            'thinking': binding['worker_controls'].get('reasoning_effort'),
            'sources': selected_sources, 'effort_root': None, 'discipline_id': None,
            'environment': None, 'origin': None, 'human_ref': None, 'delegator': None, 'store_id': None,
            'purpose_ref': None, 'selectors': {}, 'command_id': None, 'target': None},
            'warnings': ['Editable unbound draft. Reselect current effort, instance, backing, purpose and applicable predecessors; launch validates them again.',
                         'Sources refer to present file contents; original qualified evidence remains in history.']}

    def recover(self, run_id, selection, kind):
        binding = self.binding(run_id, selection)
        if binding is None:
            raise ScopeError('Owned reviewed execution not found')
        if kind not in ('correlation', 'contribution'):
            raise ScopeError('Choose correlation or contribution recovery')
        with self.app.mutation(), self.app.admission(run_id):
            self.guard_binding_files(binding)
            self.adapter.validate_request(binding['assignment'], binding['workspace'], current=False)
            self.adapter.validate_store(binding['store_ref'], binding['effort_root'])
            from scripts.noetic_application import lock_held
            launch_root = self.app.root / '.opermem-launches'
            for directory in launch_root.iterdir() if launch_root.exists() else ():
                try:
                    self.launch_owner(directory, selection)
                except Exception as exc:
                    if getattr(exc, 'status', None) == 403:
                        continue
                    raise
                observation = directory / 'prepared-observation.json'
                from scripts.noetic_application import contained
                contained(observation, directory)
                observed_run = json.loads(observation.read_text())['binding']['run_id'] if observation.exists() else None
                if lock_held(directory / 'driver.lock', directory) and observed_run in (None, run_id):
                    raise ScopeError('The original reviewed driver still owns this execution or unresolved preparation')
            if kind == 'correlation':
                self.adapter.recover_preparation(binding['execution_id'])
            # Lost derived command receipt can only be restored from original callback evidence.
            for directory in (self.app.root / '.opermem-launches').iterdir() if (self.app.root / '.opermem-launches').exists() else ():
                try:
                    self.launch_owner(directory, selection)
                except Exception as exc:
                    if getattr(exc, 'status', None) == 403:
                        continue
                    raise
                observation = directory / 'prepared-observation.json'
                if not observation.exists() or json.loads(observation.read_text())['binding']['run_id'] != run_id:
                    continue
                receipt = self.launch_receipt(directory, selection)
                if receipt.get('run_id') == run_id:
                    if receipt['driver_owned']:
                        raise ScopeError('The original driver still owns this execution')
                    self.launch_receipt(directory, selection, restore=True)
            if kind == 'correlation':
                return self.detail(run_id, selection)
            self.authority(run_id, selection)
            self.adapter.validate_binding(binding, current=True)
            code = native.resume_run(Path(binding['run_dir']), Path(binding['store_ref']['host']),
                Path(binding['store_ref']['directory']), self.app.root / '.opermem-transcripts')
            return {'exit_code': code, 'actors_replayed': False, **self.detail(run_id, selection)}


def args_for(directory, frozen):
    body = frozen['body']
    task_path = directory / 'task.md'
    if task_path.exists() and task_path.read_text() != body['task']:
        raise ScopeError('Frozen launch task changed')
    if not task_path.exists():
        with open_private(task_path, 'x') as stream:
            stream.write(body['task'])
    for selected in frozen['recall_sources']:
        path = Path(selected['path'])
        ensure_private_directory(path.parent)
        immutable(path, selected['record'])
    args = {name: None for name in SELECTORS}
    args.update(body.get('selectors', {}))
    purpose = frozen['purpose'] or {}
    qualification = None
    if body.get('qualification') is not None:
        qualification = directory / 'qualification.json'
        immutable(qualification, body['qualification'])
    args.update(task=task_path, workspace=Path(frozen['workspace']), operation=body.get('operation', 'question'),
        host=Path(frozen['store_ref']['host']), store=Path(frozen['store_ref']['directory']), runs_dir=directory.parent.parent,
        scope_request=frozen['assignment'], store_ref=frozen['store_ref'], purpose_ref=purpose.get('purpose_ref'),
        purpose_config=purpose.get('purpose_config'), telos_chain=purpose.get('telos_chain'),
        telos_db=Path(purpose['telos_db']) if purpose else None, telos_source=Path(purpose['telos_source']) if purpose else None,
        source=[Path(s['path']) for s in frozen['source_fingerprints']], qualification=qualification,
        client=body.get('client', 'pi'), model=body.get('model'), review_model=body.get('qa_model'),
        thinking=body.get('thinking'), timeout=body.get('timeout', 900), inquiry=True, verify=None,
        checking_spec=Path(frozen['operation_evidence']['paths']['checking_spec']) if body.get('operation') == 'checking' else None,
        observed_run=Path(frozen['operation_evidence']['observed_run']) if frozen['operation_evidence'] and 'observed_run' in frozen['operation_evidence'] else None,
        observation_evidence=Path(frozen['operation_evidence']['observation_evidence']) if frozen['operation_evidence'] and 'observation_evidence' in frozen['operation_evidence'] else None,
        observation_manifest_sha256=body.get('observation_manifest_sha256'), observed_step=body.get('observed_step', 'work'))
    return Namespace(**args)


def drive(directory, lock_fd, slot_fd):
    from scripts.noetic_application import Application
    directory = Path(directory).resolve(strict=True)
    os.environ.pop('USER_PROVIDED_PASSWORD', None)
    with os.fdopen(lock_fd, 'a'), os.fdopen(slot_fd, 'a'):
        original = json.loads((directory / 'request.json').read_text())
        frozen = original['frozen']
        receipt = json.loads((directory / 'receipt.json').read_text())
        try:
            immutable(directory / 'process.json', {'identity': processes.identity(os.getpid()), 'observed_at': stamp()})
            app = Application(**original['application'])
            service = ReviewedApplication(app)
            if service.preflight(frozen['body']) != frozen:
                raise ScopeError('Reviewed request/source/configuration changed before driver effects')
            save(directory / 'receipt.json', {**receipt, 'status': 'launch-attempted', 'started_at': stamp()})
            def prepared(binding):
                immutable(directory / 'prepared-observation.json', {'binding': binding, 'request_digest': original['request_digest']})
                # Compare actual captured preparation to the frozen request before native effects.
                service.launch_receipt(directory, {'kind': 'effort', 'effort_root': binding['effort_root']})
                current = json.loads((directory / 'receipt.json').read_text())
                save(directory / 'receipt.json', {**current, 'status': 'prepared', 'run_id': binding['run_id'],
                                                 'execution_id': binding['execution_id'], 'prepared_at': stamp()})
            code = native.run_task(args_for(directory, frozen), on_prepared=prepared)
            current = json.loads((directory / 'receipt.json').read_text())
            save(directory / 'receipt.json', {**current, 'status': 'finished' if code == 0 else 'failed', 'exit_code': code, 'finished_at': stamp()})
            return code
        except Exception as exc:
            current = json.loads((directory / 'receipt.json').read_text())
            save(directory / 'receipt.json', {**current, 'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'[:2000], 'finished_at': stamp()})
            return 1


if __name__ == '__main__':
    if len(sys.argv) != 5 or sys.argv[1] != 'drive':
        raise SystemExit('Internal reviewed driver: drive LAUNCH LOCK_FD SLOT_FD')
    raise SystemExit(drive(sys.argv[2], int(sys.argv[3]), int(sys.argv[4])))
