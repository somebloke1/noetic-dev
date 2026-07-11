#!/usr/bin/env python3
"""Dependency-free semantic validation for cognitive-program contracts."""
from __future__ import annotations
import copy,json,sys
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]; SPEC=ROOT/'spec/programs/v0'; EX=SPEC/'examples'
OPS={'P1':'attend','P2':'understand','P3':'judge','P4':'decide'}
def ensure(c:bool,m:str)->None:
 if not c:raise AssertionError(m)
def load(path:Path)->Any:return json.loads(path.read_text())
def errors(p:dict[str,Any])->list[str]:
 out=[]
 if p.get('schema_version')!='noetic.cognitive-program/v0':out.append('schema version drift')
 cb=p.get('controller_binding',{})
 if cb.get('authority_mode')!='propose_only':out.append('program authority must be propose_only')
 allowed={'capabilities','policy_class'}
 seen=set()
 for s in p.get('stages',[]):
  if s.get('stage_id') in seen:out.append('duplicate stage id')
  seen.add(s.get('stage_id'))
  if OPS.get(s.get('phase'))!=s.get('operation'):out.append('operation-phase mismatch')
  if s.get('effect_authority')!='none':out.append('program stage gained effect authority')
  req=s.get('model_request')
  if req is not None and set(req)-allowed:out.append('model request owns endpoint/provider')
  outputs=set(s.get('outputs',[]));inputs=set(s.get('inputs',[]))
  if ('judgment' in outputs or s.get('phase')=='P3') and 'evidence' not in inputs:out.append('P3 judgment requires evidence')
  if 'decision' in outputs and 'judgment' not in inputs:out.append('P4 decision requires judgment')
 stages={s.get('stage_id'):s for s in p.get('stages',[])}
 for t in p.get('transitions',[]):
  if t.get('source') not in stages or t.get('target') not in stages:out.append('transition endpoint missing')
 ap=p.get('artifact_policy',{})
 if not all(ap.get(k) is True for k in ('evidence_before_judgment','judgment_before_decision','immutable_provenance')):out.append('artifact boundary weakened')
 vp=p.get('verification_policy',{})
 if vp.get('implementation_qa_cardinality')!='1:1_per_generation':out.append('implementation:QA cardinality drift')
 if vp.get('qa_independent_role')!='qa_agent' or vp.get('qa_cannot_implement') is not True:out.append('QA independence weakened')
 roles=[s.get('role') for s in p.get('stages',[])]
 if 'implementer' in roles and roles.count('qa_agent')!=roles.count('implementer'):out.append('implementation:QA stage count drift')
 tp=p.get('termination_policy',{})
 if not 0<=tp.get('max_remediation_generations',99)<=5:out.append('remediation generation bound exceeded')
 if not 1<=tp.get('max_stage_attempts',99)<=10:out.append('stage attempt bound exceeded')
 priv=p.get('privacy',{})
 if priv.get('secret_material')!='reference_only':out.append('secret material must be reference_only')
 if priv.get('event_payloads')!='minimal_attributed_reports':out.append('event privacy weakened')
 return out
def mutate(target:Any,path:str,value:Any)->None:
 parts=path.split('.');cur=target
 for x in parts[:-1]:cur=cur[int(x)] if isinstance(cur,list) else cur[x]
 x=parts[-1]
 if isinstance(cur,list):cur[int(x)]=value
 else:cur[x]=value
def main()->int:
 try:
  schema=load(SPEC/'program-manifest.schema.json');ensure(schema['additionalProperties'] is False,'manifest root not strict')
  valid={n:load(EX/n) for n in ('phronesis.json','verified-change.json')}
  for n,p in valid.items():ensure(not errors(p),f'{n}: {errors(p)}')
  cases=load(EX/'invalid-programs.json')['cases'];seen=set()
  for case in cases:
   ensure(case['name'] not in seen,'duplicate invalid case');seen.add(case['name']);p=copy.deepcopy(valid[case['base']]);mutate(p,*next(iter(case['mutation'].items())));ensure(case['expected_error'] in errors(p),f"{case['name']}: {errors(p)}")
  doc=(ROOT/'docs/cognitive-program-contract.md').read_text().lower()
  for phrase in ('programs propose; the controller disposes','p1','p2','p3','p4','capability request','exactly one','bounded remediation','minimal attributed reports'):ensure(phrase in doc,f'doc missing {phrase}')
  ensure((ROOT/'docs/cognitive-program-review.md').is_file(),'missing adversarial review')
 except (AssertionError,KeyError,TypeError,OSError,json.JSONDecodeError) as e:print(f'Cognitive program validation failed: {e}',file=sys.stderr);return 1
 print('Cognitive program v0 specification validation passed.');return 0
if __name__=='__main__':raise SystemExit(main())
