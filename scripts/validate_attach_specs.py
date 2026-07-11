#!/usr/bin/env python3
"""Dependency-free validation for attach adapter contracts."""
from __future__ import annotations
import copy, json, re, sys
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]; SPEC=ROOT/'spec'/'attach'/'v0'
HANDLE=re.compile(r'^adapter:[a-z][a-z0-9_.:-]+$'); ENV=re.compile(r'^env:[A-Z][A-Z0-9_]+$')
SHELL_META=re.compile(r'[;&|`$<>\n\r]')
def ensure(c:bool,m:str)->None:
    if not c: raise AssertionError(m)
def load(name:str)->Any:
    return json.loads((SPEC/name).read_text(encoding='utf-8'))
def errors(value:dict[str,Any],schema:dict[str,Any],current:dict[str,int])->list[str]:
    out=[]; required=set(schema['required']); props=set(schema['properties'])
    out += [f'missing {x}' for x in sorted(required-value.keys())]; out += [f'unknown {x}' for x in sorted(value.keys()-props)]
    if out:return out
    perms=set(value['authority']['permissions'])
    if value['mode']=='observe' and 'send_input' in perms:out.append('observe mode cannot send input')
    if value['mode']=='interactive' and 'send_input' not in perms:out.append('interactive mode requires send_input')
    if value['identity']['workspace_fence']!=current['workspace_fence']:out.append('workspace fence is stale')
    if value['session']['generation']!=current['session_generation']:out.append('session generation is stale')
    if not HANDLE.fullmatch(value['session']['adapter_handle_ref']):out.append('adapter handle must be opaque')
    boot=value['bootstrap']
    if boot['strategy']!='minimal_reference':out.append('bootstrap strategy drift')
    if boot['payload_bytes']>4096:out.append('bootstrap payload exceeds 4096 bytes')
    if len(boot['argv'])>32 or any(len(arg)>256 for arg in boot['argv']):out.append('bootstrap argv exceeds bounds')
    if any(SHELL_META.search(arg) for arg in boot['argv']):out.append('bootstrap argv contains shell metacharacter')
    if any(not ENV.fullmatch(ref) for ref in boot['environment_refs']):out.append('bootstrap environment reference invalid')
    if value['reconnect']['require_same_generation'] is not True or value['reconnect']['require_current_fence'] is not True:out.append('reconnect fence requirement weakened')
    if not 0<=value['reconnect']['max_attempts']<=10:out.append('reconnect attempts out of bounds')
    if value['privacy']['persist_raw_output'] is not False:out.append('raw terminal output persistence is forbidden')
    if value['privacy']['redact_logs'] is not True:out.append('attach logs must be redacted')
    if value['audit']['canonical_event_version']!='noetic.event/v0':out.append('canonical event version drift')
    return out
def set_path(target:dict[str,Any],path:str,value:Any)->None:
    parts=path.split('.'); cur:Any=target
    for part in parts[:-1]:cur=cur[part]
    cur[parts[-1]]=value
def main()->int:
    try:
        schema=load('attach-session.schema.json'); profiles=load('adapter-profiles.json'); cases=load('examples/invalid-sessions.json')
        ensure(schema['additionalProperties'] is False,'attach root must be strict')
        ensure(profiles['default_adapter']=='tmux','tmux default drift')
        ensure(set(profiles['profiles'])=={'tmux','browser_pty'},'adapter profile drift')
        boundary=' '.join(profiles['kernel_boundary']).lower(); parity=' '.join(profiles['parity']).lower()
        for phrase in ('no tmux socket','no tmux socket, pane id, pty object, websocket, browser, process, or terminal buffer','cannot invoke controller commands'):ensure(phrase in boundary,f'kernel boundary missing {phrase}')
        for phrase in ('observe mode never permits input','stale generation','detach ends attachment'):ensure(phrase in parity,f'parity missing {phrase}')
        current=cases['fixture_current_identity']
        for name in ('examples/valid-tmux.json','examples/valid-browser-observe.json'):
            value=load(name); ensure(not errors(value,schema,current),f'{name}: {errors(value,schema,current)}')
        names=set()
        for case in cases['cases']:
            ensure(case['name'] not in names,'duplicate invalid case');names.add(case['name'])
            attacked=copy.deepcopy(load('examples/'+case['base']))
            for path,val in case['mutations'].items():set_path(attacked,path,val)
            found=errors(attacked,schema,current);ensure(case['expected_error'] in found,f"{case['name']}: {found}")
        doc=(ROOT/'docs'/'attach-adapter-contract.md').read_text(encoding='utf-8').lower()
        for phrase in ('never controller execution authority','minimalist default','optional','4096','shell metacharacters','stale browser socket','separate controller command','no contextforge'):ensure(phrase in doc,f'doc missing {phrase}')
        ensure((ROOT/'docs'/'attach-adapter-review.md').is_file(),'missing attach review')
    except (AssertionError,KeyError,TypeError,OSError,json.JSONDecodeError) as e:
        print(f'Attach specification validation failed: {e}',file=sys.stderr);return 1
    print('Attach adapter v0 specification validation passed.');return 0
if __name__=='__main__':raise SystemExit(main())
