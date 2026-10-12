"""Actual private archive/native pair and installed runtime outside the source checkout."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

from scripts import noetic_release as release, noetic_archive as archive
from scripts import noetic_opermem_application as component
from tests.programs.test_scoped_release_assets import fixture_wheel

ROOT = Path(__file__).resolve().parents[2]


class RequiredOwnedAssetsTests(unittest.TestCase):
    def test_real_omission_gate(self):
        for name in ('scripts/noetic_opermem_scope.py', 'scripts/noetic_opermem_application.py'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'missing runtime asset'):
                release.wheel_info(fixture_wheel(omit=name), 'noetic_dev-0.3.0-py3-none-any.whl')


@unittest.skipUnless(os.environ.get('OPERMEM_OPERATION_HOST'), 'requires accepted actual native pair')
class NativeReleaseTests(unittest.TestCase):
    def test_exact_pair_archive_install_and_real_http_run(self):
        with tempfile.TemporaryDirectory(prefix='native-release-') as temporary:
            root=Path(temporary)
            host=Path(os.environ['OPERMEM_OPERATION_HOST']).resolve(strict=True)
            blobs={name:(host.parent/name).read_bytes() for name in component.EXECUTABLES}
            staged=root/'staged-native';staged.mkdir()
            for name,data in blobs.items():(staged/name).write_bytes(data)
            host=staged/'opermem-operation-host';child=staged/'opermem-child'
            manifest=root/'native.json';manifest.write_text(json.dumps(component.component_manifest(blobs,{'accepted_pair_sha256':{n:hashlib.sha256(v).hexdigest() for n,v in blobs.items()},'qualification':'accepted operation-host/child fixture; source reproducibility unestablished'})))
            wheel=root/'noetic_dev-0.3.0-py3-none-any.whl';wheel.write_bytes(fixture_wheel())
            core=Path(os.environ.get('NOETIC_TEST_TELOS_SOURCE',ROOT/'.runtime/components/telos-core.mjs'))
            args={'wheel':wheel,'telos_module':core,'telos_manifest':core.with_suffix('.manifest.json'),
                  'license_file':ROOT/'LICENSE.md','notices':ROOT/'docs/THIRD_PARTY_NOTICES.txt',
                  'docs':[ROOT/'docs/effort-application.md'],'opermem_host':host,'opermem_child':child,
                  'opermem_manifest':manifest,'opermem_notices':ROOT/'docs/opermem-component-notices.txt'}
            bundle=root/'release.zip';release.build_release(bundle,**args)
            files,metadata=archive.read_bundle(bundle,'noetic-private-release')
            self.assertLess(sum(map(len,files.values())),archive.MAX_BYTES)
            omitted=dict(files);omitted.pop(component.COMPONENT+'/opermem-child')
            with self.assertRaisesRegex(ValueError,'requires exact host, child'):release.validate_assets(omitted,metadata)
            changed=dict(files);changed[component.COMPONENT+'/opermem-child']=b'changed'
            with self.assertRaisesRegex(ValueError,'mismatch'):release.validate_assets(changed,metadata)
            home=root/'installed';result=release.install_release(bundle,home)
            installed=home/'releases'/result['current']
            for name in component.EXECUTABLES:
                path=installed/component.COMPONENT/name
                self.assertEqual(path.read_bytes(),blobs[name]);self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o700)
            self.assertTrue(component.host_configuration(installed/component.COMPONENT/'opermem-operation-host')['available'])
            # Real installed HTTP application dispatches two executable protocol fixtures via PATH.
            bin_dir=root/'fixture-bin';bin_dir.mkdir()
            fixture=bin_dir/'opencode'
            fixture.write_text('''#!'''+sys.executable+'''
import json,os,sys,uuid
from pathlib import Path
assert 'USER_PROVIDED_PASSWORD' not in os.environ
prompt=sys.stdin.read();role=sys.argv[sys.argv.index('--agent')+1]
with Path(os.environ['FIXTURE_CALLS']).open('a') as f:f.write(role+'\\n')
text='ACCEPT\\nActual independent installed reviewer.' if role=='noetic-reviewer' else 'Useful installed source inquiry.\\nOPERMEM_CONTRIBUTION_JSON: '+json.dumps({'question_kind':'how','text':'How do the selected sources support this inquiry?'})
sid='installed-'+str(uuid.uuid4())
print(json.dumps({'type':'text','sessionID':sid,'part':{'id':'text','messageID':'final','text':text}}))
print(json.dumps({'type':'step_finish','sessionID':sid,'part':{'messageID':'final','reason':'stop'}}))
''');fixture.chmod(0o700)
            probe=root/'installed-probe.py'
            probe.write_text('''
from contextlib import closing
import http.client,json,os,sys,threading,time
from pathlib import Path
from scripts import noetic_web, noetic_opermem_application as component
from scripts.noetic_scope import ScopeStore
root=Path.cwd();cwd=root/'project';cwd.mkdir();runs=root/'runs';ns=root/'namespace.sqlite3'
canonical=ScopeStore(ns,root_mandate={'purpose':'isolated installed root'},human_ref={'fixture':'human'},source_ref={'fixture':'setup'})
owner=canonical.create_effort(intent='ordinary project inquiry',environment={'cwd':str(cwd)},mandate={'purpose':'ordinary independent effort'},origin='human',human_ref={'fixture':'human'},source_ref={'fixture':'effort'})
server=noetic_web.create_server(runs,port=0,namespace_path=ns);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
def api(path,body=None):
 with closing(http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=20)) as conn:
  conn.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,{'Authorization':'Bearer '+server.token,'Content-Type':'application/json'})
  response=conn.getresponse();data=json.loads(response.read());assert response.status in (200,201,202),(response.status,data);return data
try:
 definition=next(d for d in api('/api/disciplines?effort_root='+owner['ordinal'])['definitions'] if d.get('backend')==component.BACKEND)
 instance=api('/api/disciplines',{'backend':component.BACKEND,'command_id':'instance','effort_root':owner['ordinal'],'initiator':owner['ordinal'],'intent':'read source','environment':owner['environment'],'origin':'human','human_ref':{'fixture':'human'}})['discipline']
 backing=api('/api/opermem/stores',{'command_id':'backing','effort_root':owner['ordinal'],'directory':str(root/'native')})['store_ref']
 assert not Path(backing['directory']).exists()
 assert str(Path(backing['host']).resolve()).startswith(sys.argv[1]+'/components/')
 task={'backend':component.BACKEND,'command_id':'inquiry','effort_root':owner['ordinal'],'discipline_id':instance['id'],'environment':owner['environment'],'origin':'human','human_ref':{'fixture':'human'},'workspace':str(cwd),'task':'Read the selected project evidence.','store_id':backing['id'],'client':'opencode'}
 launch=api('/api/application/start',task);assert launch['backend']==component.BACKEND
 deadline=time.monotonic()+20
 while time.monotonic()<deadline:
  launch=api('/api/application/launches/'+launch['launch_id']+'?effort_root='+owner['ordinal'])
  if launch['status'] in ('finished','failed') and not launch['driver_owned']:break
  time.sleep(.02)
 assert launch['status']=='finished',launch
 detail=api('/api/runs/'+launch['run_id']+'?effort_root='+owner['ordinal'])
 assert len(detail['population'])==2 and all(p['target'] for p in detail['population']),detail
 assert detail['application']['native']['receipt_retained'],detail
 assert detail['application']['review']['outcome']=='accept',detail
 assert Path(os.environ['FIXTURE_CALLS']).read_text().splitlines()==['noetic-inquirer','noetic-reviewer']
 for name,module in tuple(sys.modules.items()):
  if name=='scripts' or name.startswith('scripts.'):
   assert str(module.__file__).startswith(sys.argv[1]+'/venv/'),(name,module.__file__)
 print('isolated installed actual HTTP inquiry/native receipt PASS')
finally:
 for p in server.application.children:p.wait(timeout=20)
 server.shutdown();server.server_close();thread.join(5)
''')
            elsewhere=root/'outside-checkout';elsewhere.mkdir()
            env={k:v for k,v in os.environ.items() if k not in ('USER_PROVIDED_PASSWORD','PYTHONPATH','PYTHONHOME','NOETIC_OPERMEM_HOST','NOETIC_APP_HOME','NOETIC_STATE_HOME')}
            env.update(NOETIC_OPERMEM_HOST=str(installed/component.COMPONENT/'opermem-operation-host'),
                       PATH=str(bin_dir)+os.pathsep+os.environ['PATH'],FIXTURE_CALLS=str(root/'calls'))
            output=subprocess.run([str(installed/'venv/bin/python'),'-I',str(probe),str(installed)],cwd=elsewhere,env=env,text=True,capture_output=True,timeout=40)
            self.assertEqual(output.returncode,0,output.stdout+output.stderr)
            self.assertIn('actual HTTP inquiry/native receipt PASS',output.stdout)
            # Retained registration stays on its original canonical release host across current changes.
            self.assertTrue(installed.exists())
            from scripts.noetic_opermem_scope import OpermemScope
            from scripts.noetic_scope import Scope
            adapter=OpermemScope(elsewhere/'namespace.sqlite3')
            refs=[e['data']['store_ref'] for e in __import__('scripts.noetic_opermem_scope',fromlist=['_history'])._history(adapter.store) if e['kind']=='opermem-store-bound']
            self.assertEqual(refs[0]['host'],str(installed/component.COMPONENT/'opermem-operation-host'))
