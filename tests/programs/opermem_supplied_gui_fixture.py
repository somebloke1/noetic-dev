"""Disposable browser fixture using accepted native executables and independent actor streams."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch

from scripts import noetic_opermem_application as reviewed, noetic_web as web
from scripts.noetic_scope import ScopeStore

assert 'USER_PROVIDED_PASSWORD' not in os.environ
root = Path(tempfile.mkdtemp(prefix='opermem-gui-'))
cwd = root / 'ordinary-project'; cwd.mkdir()
source = cwd / 'observations.md'; source.write_text('The river station records 18 samples each day. Missing samples are labelled explicitly.\n')
ns = root / 'namespace.sqlite3'
canonical = ScopeStore(ns, root_mandate={'purpose':'disposable browser fixture'}, human_ref={'fixture':'human'}, source_ref={'fixture':'setup'})
efforts = [canonical.create_effort(intent=name,environment={'cwd':str(cwd)},mandate={'purpose':name},origin='human',human_ref={'fixture':'human'},source_ref={'fixture':name}) for name in ('River station inquiry','Independent B','Recovery R')]
os.environ['REVIEWED_FIXTURE_ROOT'] = str(root)
os.environ['REVIEWED_FIXTURE_HOLD'] = '1'
original = subprocess.Popen

def launch(argv, **kwargs):
    if 'scripts.noetic_opermem_application' in argv:
        i = argv.index('scripts.noetic_opermem_application'); _,directory,fd,slot = argv[i+1:]
        code = "import os,sys;from scripts import noetic_develop as d,noetic_opermem_application as a;from tests.programs.test_opermem_application import client;d.client_command=client\noriginal_save=a.save\ndef save(path,value):\n if os.environ.get('REVIEWED_FIXTURE_CALLBACK_GAP') and path.name=='receipt.json' and value.get('status')=='prepared':raise OSError('fixture lost derived preparation receipt update')\n return original_save(path,value)\na.save=save\nraise SystemExit(a.drive(sys.argv[1],int(sys.argv[2]),int(sys.argv[3])))"
        argv = [sys.executable,'-B','-c',code,directory,fd,slot]
    return original(argv, **kwargs)

transport = patch.object(reviewed.subprocess,'Popen',side_effect=launch);transport.start()
server = web.create_server(root/'runs',port=0,namespace_path=ns,opermem_host=Path(os.environ['OPERMEM_OPERATION_HOST']),session_command=['/bin/false'])
thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
print(json.dumps({'url':'http://127.0.0.1:'+str(server.server_port),'token':server.token,'root':str(root),'project':str(cwd),'source':str(source),'backing':str(root/'native-A')}),flush=True)
try:
    for line in sys.stdin:
        command = json.loads(line)
        if command['action']=='release': (root/'release').touch(); os.environ.pop('REVIEWED_FIXTURE_HOLD',None)
        elif command['action']=='failure': os.environ['REVIEWED_FIXTURE_FAIL']='no-header'
        elif command['action']=='gap': os.environ.pop('REVIEWED_FIXTURE_FAIL',None);os.environ['REVIEWED_FIXTURE_CALLBACK_GAP']='1'
        elif command['action']=='normal': os.environ.pop('REVIEWED_FIXTURE_FAIL',None);os.environ.pop('REVIEWED_FIXTURE_CALLBACK_GAP',None)
        elif command['action']=='stop': break
finally:
    (root/'release').touch()
    for child in server.application.children: child.wait(timeout=25)
    server.shutdown();server.server_close();thread.join(5);transport.stop()
