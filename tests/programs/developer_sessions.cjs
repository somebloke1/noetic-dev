// Real browser, authenticated production routes and detached model-free RPC processes.
const {chromium} = require('playwright');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
 const fixture = spawn('python', ['-B','-u','-c', `
import json, signal, sys, threading, time, sqlite3, uuid
from contextlib import closing
from pathlib import Path
from scripts import noetic_web as web
from tests.programs.test_noetic_sessions import SessionTests, FIXTURE
from tests.programs.test_noetic_projects import ProjectWorkspaceTests
case=SessionTests(); case.setUp(); (case.workspace/'README.md').write_text('Actual project source\\n')
project_case=ProjectWorkspaceTests(); project_case.setUp()
source=project_case.root/'app-project'
pattern_app,pattern_run,task_workspace=project_case.completed_run(source, "from pathlib import Path; Path('checked.py').write_text('print(42)')",automatic=True)
case.runs=pattern_app.root
server=web.create_server(case.runs,port=0,session_command=[sys.executable,str(FIXTURE)],namespace_path=case.runs/"ordinals.sqlite3")
case.service=server.developer_sessions
initial_legacy=str(uuid.uuid4()); registry=case.service.registry; registry.initialize()
initial_source=case.home/'original-native.jsonl'; initial_source.write_text('Original retained native bytes')
with closing(sqlite3.connect(registry.path)) as db, db:
 db.execute("INSERT INTO sessions(id,root_id,parent_id,ordinal,workspace,title,model,thinking,command,status,native_session_file,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(initial_legacy,initial_legacy,None,'0',str(case.workspace),'Pre-registration historical root','fixture/model','high',json.dumps([sys.executable,str(FIXTURE)]),'closed',str(initial_source),'2026-01-01','2026-01-01'))
registry.event(initial_legacy,'event',{'type':'message_end','message':{'role':'assistant','content':'Historical context before global registration','stopReason':'stop'}})
assert not case.service.registry.domain.path.exists()
thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
port=server.server_port; token=server.token
preserved=case.home/'preserved'; preserved.mkdir(); (preserved/'owner.txt').write_bytes(b'owner bytes')
def finish(*_):
 server.shutdown(); server.server_close(); thread.join(5); case.tearDown(); project_case.doCleanups(); sys.exit(0)
signal.signal(signal.SIGTERM,finish)
print(json.dumps({'port':port,'token':token,'workspace':str(case.workspace),'newproject':str(case.home/'new-app'),'preserved':str(preserved),'pattern':pattern_run.name,'pattern_source':str(source),'initial_legacy':initial_legacy,'namespace':str(case.service.registry.domain.path),'initial_source':str(initial_source)}),flush=True)
for line in sys.stdin:
 if line.strip().startswith('fail-start '):
  previous=case.service.pi_command
  try:
   case.service.pi_command=[str(case.home/'missing-native-fixture')]
   case.service.create({'effort_root':line.strip().split(' ',1)[1],'prompt':'Failed responsibility start'})
  except Exception:
   pass
  finally:
   case.service.pi_command=previous
  print('failed-started',flush=True)
 if line.strip().startswith('seed-large '):
  sid=line.strip().split(' ',1)[1]
  for number in range(505):
   case.service.registry.event(sid,'event',{'type':'pagination-fixture','number':number})
  case.service.registry.event(sid,'event',{'type':'message_end','message':{'role':'assistant','content':'Native journal beyond page 500','stopReason':'stop'}})
  legacy=str(uuid.uuid4()); registry=case.service.registry
  with closing(sqlite3.connect(registry.path)) as db, db:
   db.execute("INSERT INTO sessions(id,root_id,parent_id,ordinal,workspace,title,model,thinking,command,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(legacy,legacy,None,'0',str(case.workspace),'Original unrelated root','fixture/model','high',json.dumps([sys.executable,str(FIXTURE)]),'closed','2026-01-01','2026-01-01'))
  registry.event(legacy,'event',{'type':'message_end','message':{'role':'assistant','content':'Original namespace journal remains separate','stopReason':'stop'}})
  print('seeded',flush=True)
 if line.strip()=='restart':
  server.shutdown(); server.server_close(); thread.join(5)
  server=web.create_server(case.runs,port=port,access_token=token,session_command=[sys.executable,str(FIXTURE)],namespace_path=case.runs/"ordinals.sqlite3")
  thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
  print('restarted',flush=True)
`], {cwd:path.resolve(__dirname,'../..'),stdio:['pipe','pipe','pipe'],env:Object.fromEntries(Object.entries(process.env).filter(([key])=>key!=='USER_PROVIDED_PASSWORD'))});
 let browser, stdout='', stderr=''; fixture.stderr.on('data', b=>stderr+=b);
 try {
  const info=await new Promise((resolve,reject)=>{ fixture.stdout.on('data',b=>{stdout+=b;const line=stdout.split('\n').find(l=>l.startsWith('{'));if(line)resolve(JSON.parse(line));});fixture.once('exit',()=>reject(new Error(stderr))); });
  browser=await chromium.launch({headless:true,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});
  const directory=process.env.NOETIC_TEST_SCREENSHOTS||'/tmp/noetic-developer-screenshots';fs.mkdirSync(directory,{recursive:true});
  const context=await browser.newContext({viewport:{width:1440,height:960}});const page=await context.newPage();const errors=[],requests=[];page.on('request',request=>{if(request.url().includes('/api/'))requests.push({url:request.url(),method:request.method(),body:request.method()==='POST'?request.postDataJSON():null});});page.on('pageerror',e=>{errors.push(e.message);console.error('pageerror',e.message);});page.setDefaultTimeout(12000);
  const base=`http://127.0.0.1:${info.port}`;
  const api=async(route,body)=>{const response=await page.request.fetch(base+route,{method:body?'POST':'GET',headers:{Authorization:`Bearer ${info.token}`},...(body?{data:body}:{})});const result=await response.json();assert(response.ok(),JSON.stringify(result));return result;};
  const waitStatus=async(state)=>{await page.waitForFunction(state=>document.querySelector('#developer-status').textContent===state,state);};
  const send=async(message,mode='prompt')=>{await page.locator('#developer-mode').selectOption(mode);await page.locator('#developer-prompt').fill(message);await page.locator('#developer-submit').click();};
  const authenticate=async(p)=>{await p.goto(base);await p.locator('#access-token').fill(info.token);await p.locator('#access-form button').click();await p.locator('#private-workspace').waitFor({state:'visible'});};
  const composerRegression=async()=>{
    const heldResponse=async pattern=>{
      let release,receive;
      const gate=new Promise(resolve=>release=resolve),ready=new Promise(resolve=>receive=resolve);
      await page.route(pattern,async route=>{
        if(route.request().method()!=='POST'){await route.continue();return;}
        const response=await route.fetch();receive(await response.json());await gate;await route.fulfill({response});
      });
      return {ready,release,dispose:()=>page.unroute(pattern)};
    };
    const settled=()=>page.waitForFunction(()=>!document.getElementById('developer-submit').disabled);
    const b=(await api('/api/efforts',{intent:'Composer draft boundary B',environment:{cwd:info.workspace}})).effort;
    const bs=(await api('/api/developer-sessions',{effort_root:b.ordinal,prompt:'Composer existing B',title:'Composer B'})).session;
    await page.locator('#developer-project-open').click();await page.locator('#developer-project-mode').selectOption('existing');await page.locator('#developer-workspace').fill(info.workspace);await page.locator('#developer-project-name').fill('Composer delayed C');await page.locator('#developer-prompt').fill('Composer C initial instruction');
    const delayed=await heldResponse('**/api/developer-sessions');
    try{
      await page.locator('#developer-submit').click();await delayed.ready;
      await page.locator(`[data-effort-root="${b.ordinal}"]`).click();await page.locator(`[data-session-id="${bs.id}"]`).click();await page.locator('#developer-heading').getByText('Composer B',{exact:true}).waitFor();
      const draft='Preserve B unsent responsibility draft';await page.locator('#developer-prompt').fill(draft);delayed.release();await settled();
      assert.equal(await page.locator('#developer-heading').textContent(),'Composer B');assert.equal(await page.locator('#developer-prompt').inputValue(),draft,'delayed project start must preserve switched-context draft');
      await page.reload();await page.locator('#developer-heading').getByText('Composer B',{exact:true}).waitFor();assert.equal(await page.locator('#developer-prompt').inputValue(),draft,'preserved B draft must remain persisted');
      await send(draft);await page.locator('#developer-transcript').getByText('result: '+draft,{exact:true}).waitFor();await settled();assert.equal(await page.locator('#developer-prompt').inputValue(),'','unchanged current-context submission must clear its submitted text');
    }finally{delayed.release();await delayed.dispose();}
    await page.locator('#developer-project-open').click();await page.locator('#developer-project-name').fill('Composer unchanged D');await page.locator('#developer-prompt').fill('Composer D initial instruction');await page.locator('#developer-submit').click();await page.locator('#developer-heading').getByText('Composer unchanged D',{exact:true}).waitFor();await settled();assert.equal(await page.locator('#developer-prompt').inputValue(),'','unchanged project start must clear its submitted text after selecting the new context');
    await page.locator('#developer-new').click();const submitted='New native conversation instruction';await page.locator('#developer-prompt').fill(submitted);
    const newContext=await heldResponse('**/api/developer-sessions');
    try{
      await page.locator('#developer-submit').click();const started=await newContext.ready;
      await page.locator('#developer-prompt').fill('');await page.locator('#developer-prompt').fill(submitted);newContext.release();
      await page.locator('#developer-context').getByText(`Instantiation ${started.session.target.instantiation} / context ${started.session.target.session} · current`,{exact:true}).waitFor();await settled();
      assert.equal(await page.locator('#developer-prompt').inputValue(),submitted,'retyped draft during new-conversation start must survive automatic context selection');
    }finally{newContext.release();await newContext.dispose();}
    const current=(await api('/api/developer-sessions')).sessions.find(row=>row.title==='Composer unchanged D'&&row.is_current);
    const promptResponse=await heldResponse(`**/api/developer-sessions/${current.ordinal}/prompt`);
    try{
      await page.locator('#developer-prompt').fill('Submitted exact-context instruction');await page.locator('#developer-submit').click();await promptResponse.ready;
      const newer='Newer unsent exact-context draft';await page.locator('#developer-prompt').fill(newer);promptResponse.release();await settled();assert.equal(await page.locator('#developer-prompt').inputValue(),newer,'delayed prompt acknowledgment must preserve newer typed input');
      await page.reload();await page.locator('#developer-heading').getByText('Composer unchanged D',{exact:true}).waitFor();assert.equal(await page.locator('#developer-prompt').inputValue(),newer);
    }finally{promptResponse.release();await promptResponse.dispose();}
    assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,checks:['delayed-start-switch-preserves-draft','preserved-draft-persists','unchanged-prompt-clears','unchanged-start-clears-after-selection','new-conversation-retyped-draft-preserved','delayed-prompt-newer-draft-preserved']}));
  };
  await authenticate(page);
  if(process.env.NOETIC_TEST_COMPOSER_ONLY==='1'){await composerRegression();return;}
  assert(await page.locator('#developer-empty').isVisible());assert.equal(await page.locator('#developer-evidence').evaluate(e=>e.open),false);
  await page.locator('#developer-global-root').click();await page.locator('#developer-history-heading').waitFor();assert.equal(fs.existsSync(info.namespace),false);
  await page.locator('#developer-global-history').click();await page.locator('.developer-rail > details summary').click();await page.locator(`[data-session-id="${info.initial_legacy}"]`).click();await page.locator('#developer-transcript').getByText('Historical context before global registration',{exact:true}).waitFor();assert.equal(fs.existsSync(info.namespace),false);assert.equal(fs.readFileSync(info.initial_source,'utf8'),'Original retained native bytes');
  await page.locator('#developer-project-open').click();assert.equal(await page.locator('#developer-submit').isEnabled(),true);
  await page.locator('#developer-workspace').fill(info.workspace);await page.locator('#developer-project-name').fill('My actual project');await page.locator('.developer-model-settings summary').click();await page.locator('#developer-model').fill('custom/selected-model');await page.locator('#developer-prompt').fill('slow browser root');await page.locator('#developer-submit').click();await waitStatus('running');
  const root=(await api('/api/developer-sessions')).sessions.find(row=>row.is_current);assert.equal(root.ordinal,'0.0');assert.equal(root.model,'custom/selected-model');
  await send('steer browser','steer');await page.locator('#developer-ack').getByText('Steering accepted',{exact:false}).waitFor();await send('queued browser','follow_up');await page.locator('#developer-ack').getByText('Follow-up accepted',{exact:false}).waitFor();await page.locator('#developer-stop').click();await waitStatus('idle');
  let detail=await api(`/api/developer-sessions/${root.id}`);const commands=detail.events.filter(e=>e.direction==='command').map(e=>e.record.type);assert(commands.indexOf('clear_queue')<commands.indexOf('abort'));
  assert(!detail.events.some(e=>e.record.type==='message_end'&&e.record.message.role==='user'&&e.record.message.content==='queued browser'));
  await send('useful output <script>literal</script>');await page.locator('#developer-transcript').getByText('result: useful output <script>literal</script>',{exact:false}).waitFor();await waitStatus('idle');assert.equal(await page.locator('#developer-transcript script').count(),0);
  await send('# Build output\n[Open source](README.md)\n[Preview](http://127.0.0.1:4321/)\n[invalid](javascript:bad)\n```sh\npython -m unittest\n```');await waitStatus('idle');await page.locator('#developer-transcript a').getByText('Open source',{exact:true}).click();await page.locator('#developer-file-text').getByText('Actual project source',{exact:false}).waitFor();assert.equal(await page.locator('#developer-transcript a[href^=\"javascript:\"]').count(),0);assert.equal(await page.locator('#developer-transcript a').getByText('Preview',{exact:true}).getAttribute('href'),'http://127.0.0.1:4321/');await page.locator('#developer-file-close').click();

  const delegate=async(task,ordinal)=>{await page.locator('#developer-delegate').click();await page.locator('#developer-delegate-task').fill(task);await page.locator('#developer-delegate-submit').click();await page.locator('#developer-ordinal').getByText(`Agent ${ordinal} · delegate`,{exact:true}).waitFor();await waitStatus('idle');};
  await delegate('first bounded task','0.0.0');await delegate('nested bounded task','0.0.0.0');await page.locator('#developer-root').click();await page.locator('#developer-ordinal').getByText('Agent 0.0 · root',{exact:true}).waitFor();await delegate('second bounded task','0.0.1');
  detail=await api(`/api/developer-sessions/${root.id}`);assert.deepEqual(detail.tree.map(i=>i.ordinal).sort(),['0.0','0.0.0','0.0.0.0','0.0.1']);
  await send('message child context');await waitStatus('idle');await page.locator('#developer-root').click();await page.locator('#developer-ordinal').getByText('Agent 0.0 · root',{exact:true}).waitFor();await send('dialog');await page.locator('#developer-dialogs button').getByText('Confirm',{exact:true}).click();await waitStatus('idle');
  assert.equal(await page.locator('#developer-evidence').evaluate(e=>e.open),false);
  const identity=(await api(`/api/developer-sessions/${root.id}`)).session.process.identity;
  stdout='';fixture.stdin.write('restart\n');await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(new Error(stderr||'restart timeout')),10000);const listen=b=>{if(b.toString().includes('restarted')){fixture.stdout.off('data',listen);clearTimeout(timeout);resolve();}};fixture.stdout.on('data',listen);});
  await page.reload();await page.locator('#developer-ordinal').getByText('Agent 0.0 · root',{exact:true}).waitFor();assert.deepEqual((await api(`/api/developer-sessions/${root.id}`)).session.process.identity,identity);
  await page.locator('#developer-close').click();await waitStatus('closed');await page.locator('#developer-reopen').click();await waitStatus('idle');assert.equal((await api(`/api/developer-sessions/${root.id}`)).session.id,root.id);
  const fresh=await browser.newPage();await authenticate(fresh);assert(await fresh.locator('#developer-empty').isVisible());await fresh.locator(`[data-effort-root="${root.effort_root}"]`).click();await fresh.locator(`[data-session-id="${root.id}"]`).click();await fresh.locator('#developer-transcript').getByText('result: useful output <script>literal</script>',{exact:false}).waitFor();await fresh.close();
  await page.locator('#developer-project-open').click();await page.locator('#developer-project-mode').selectOption('create');await page.locator('#developer-workspace').fill('new-app');if(!await page.locator('#developer-projects-root').isVisible())await page.locator('.developer-model-settings summary').click();await page.locator('#developer-projects-root').fill(path.dirname(info.newproject));await page.locator('#developer-project-name').fill('New app');await page.locator('#developer-prompt').fill('Build my new app');assert.equal(await page.locator('#developer-submit').textContent(),'Create project and start');await page.locator('#developer-submit').click();await page.locator('#developer-heading').getByText('New app',{exact:true}).waitFor();await waitStatus('idle');assert.equal((await api('/api/developer-sessions')).sessions.filter(i=>i.workspace===info.newproject)[0].ordinal,'0.1');assert(fs.existsSync(path.join(info.newproject,'.git')));
  await page.locator('#developer-project-open').click();await page.locator('#developer-project-mode').selectOption('create');await page.locator('#developer-workspace').fill(info.preserved);await page.locator('#developer-prompt').fill('must preserve');await page.locator('#developer-submit').click();await page.locator('#developer-error').getByText('not empty',{exact:false}).waitFor();assert.equal(fs.readFileSync(path.join(info.preserved,'owner.txt'),'utf8'),'owner bytes');
  await page.locator('.tools-menu summary').click();await page.locator('.tools-menu [data-page="new"]').click();
  await page.locator('#start-change-model').click();assert.equal(await page.locator('[data-settings-panel="model"]').isVisible(),true);
  await page.locator('#start-profile').selectOption('');await page.locator('#start-client').selectOption('pi');await page.locator('#start-model').fill('custom/settings-model');await page.locator('#start-model').dispatchEvent('change');
  await page.locator('[data-settings="review"]').click();await page.locator('#start-qa-model').fill('custom/review-model');
  await page.locator('#start-pattern').selectOption('cognition');assert.equal(await page.locator('#review-settings-tab').isVisible(),false);
  await page.locator('[data-settings="limits"]').click();assert.equal(await page.locator('#cognition-limits').isVisible(),true);assert.equal(await page.locator('#development-limits').isVisible(),false);
  await page.locator('#start-pattern').selectOption('development');assert.equal(await page.locator('#cognition-limits').isVisible(),false);await page.locator('[data-settings="review"]').click();assert.equal(await page.locator('#start-qa-model').inputValue(),'custom/review-model');
  await page.locator('[data-settings="model"]').click();await page.locator('#start-client').selectOption('opencode');assert.equal(await page.locator('#pi-thinking-field').isVisible(),false);assert.equal(await page.locator('#start-model').inputValue(),'custom/settings-model');
  await page.locator('#start-profile').selectOption('pi-direct');assert.equal(await page.locator('#custom-model-fields').isVisible(),false);assert.match(await page.locator('#start-effective-model').textContent(),/gpt-6.1-sol/);
  await page.locator('#structured-register > summary').click();await page.locator(`[data-run-id="${info.pattern}"]`).click();
  await page.locator('#workspace-result-summary').waitFor({state:'visible'});const pattern=await api(`/api/runs/${info.pattern}`);const selectedActor=await page.locator('#session-select').inputValue();assert.equal(pattern.controller.activations[selectedActor].mode,'produce');
  assert.match(await page.locator('#workspace-result-location').textContent(),/Task files:/);await page.locator('#workspace-result-summary').getByText('Fixture',{exact:false}).waitFor();
  const plan=await api(`/api/runs/${info.pattern}/project-changes`);assert.equal(plan.eligible,true);assert.equal(fs.existsSync(path.join(info.pattern_source,'checked.py')),false);
  page.once('dialog',dialog=>dialog.accept());await page.locator('#workspace-apply').click();await page.locator('#workspace-apply-result').getByText('applied',{exact:false}).waitFor();assert.equal(fs.readFileSync(path.join(info.pattern_source,'checked.py'),'utf8'),'print(42)');assert.equal((await api(`/api/runs/${info.pattern}/project-changes`)).applied,true);
  await page.locator('#workspace-result-review summary').click();assert.match(await page.locator('#workspace-review-report').textContent(),/Fixture/);
  await page.locator(`[data-effort-root="${root.effort_root}"]`).click();await page.locator(`[data-session-id="${root.id}"]`).click();
  const beforeEfforts=(await api('/api/efforts')).records.filter(row=>row.effort===row.ordinal).length;
  const queued=await api('/api/actions',{target:root.target,effort_root:root.effort_root,kind:'prompt',payload:{message:'never redirect queued',mode:'prompt'}});
  await page.locator('#developer-new').click();await page.locator('#developer-prompt').fill('Second conversation same responsibility');await page.locator('#developer-submit').click();await page.locator('#developer-transcript').getByText('result: Second conversation same responsibility',{exact:true}).waitFor();await waitStatus('idle');
  const second=(await api('/api/developer-sessions?effort_root='+root.effort_root)).sessions.find(row=>row.is_current&&row.ordinal===root.ordinal);
  assert.equal(second.ordinal,root.ordinal);assert.equal(second.target.instantiation,root.target.instantiation);assert.notEqual(second.target.session,root.target.session);
  assert.equal((await api('/api/efforts')).records.filter(row=>row.effort===row.ordinal).length,beforeEfforts);
  const b=(await api('/api/efforts',{intent:'B distinct intent same directory',environment:{cwd:info.workspace}})).effort;
  const bs=(await api('/api/developer-sessions',{effort_root:b.ordinal,prompt:'Effort B conversation'})).session;
  const r=(await api('/api/efforts',{intent:'Independent recovery effort',environment:{cwd:info.preserved}})).effort;
  await page.locator('#refresh').click();await page.locator(`[data-effort-root="${r.ordinal}"]`).click();
  await page.locator('#developer-history-heading').getByText(`Position ${r.ordinal}`,{exact:false}).waitFor();assert.equal(await page.locator('#developer-new').isEnabled(),true);
  assert.equal((await api('/api/developer-sessions?effort_root='+r.ordinal)).sessions.length,0);await page.screenshot({path:path.join(directory,'empty-registered-effort.png')});
  await page.locator('#developer-new').click();await page.locator('#developer-prompt').fill('Recovery in ordinary folder');await page.locator('#developer-submit').click();await page.locator('#developer-transcript').getByText('result: Recovery in ordinary folder',{exact:true}).waitFor();assert.equal(fs.readFileSync(path.join(info.preserved,'owner.txt'),'utf8'),'owner bytes');assert(fs.existsSync(path.join(info.preserved,'.git')));
  await page.locator(`[data-effort-root="${b.ordinal}"]`).click();await page.locator(`[data-session-id="${bs.id}"]`).click();await page.locator('#developer-transcript').getByText('result: Effort B conversation',{exact:true}).waitFor();
  assert.equal((await page.locator('#developer-transcript').innerText()).includes('My actual project'),false);
  await page.locator(`[data-effort-root="${root.effort_root}"]`).click();await page.locator(`[data-session-id="${second.id}"]`).click();
  await page.locator('#developer-header .developer-actions details summary').click();await page.locator('#developer-succeed').click();await page.locator('#developer-succession-responsibility').fill('Continue entrusted responsibility');await page.locator('#developer-succession-context').fill('Explicit successor context handoff');await page.locator('#developer-succession-form button[type=submit]').click();await page.locator('#developer-context').getByText('Instantiation 2 / context 1 · current',{exact:true}).waitFor();await waitStatus('idle');
  const successor=(await api('/api/developer-sessions?effort_root='+root.effort_root)).sessions.find(row=>row.is_current&&row.ordinal===root.ordinal);
  assert.equal(successor.target.instantiation,second.target.instantiation+1);assert.equal(successor.ordinal,root.ordinal);await page.screenshot({path:path.join(directory,'current-successor.png')});
  await page.locator(`[data-session-id="${second.id}"]`).click();await page.locator('#developer-context').getByText(`Instantiation ${second.target.instantiation} / context ${second.target.session} · retained`,{exact:true}).waitFor();
  await send('historical exact target must not redirect');await page.locator('#developer-error').getByText('superseded',{exact:false}).waitFor();
  const rejected=await page.request.post(base+`/api/actions/${queued.id}/deliver`,{headers:{Authorization:`Bearer ${info.token}`},data:{effort_root:root.effort_root}});assert.equal(rejected.ok(),false);
  assert.equal(JSON.stringify((await api(`/api/developer-sessions/${successor.ordinal}?effort_root=${root.effort_root}&instantiation=${successor.target.instantiation}&session=${successor.target.session}`)).events).includes('historical exact target must not redirect'),false);
  const stoppedGate={};let releaseStop;stoppedGate.release=new Promise(resolve=>releaseStop=resolve);
  await page.route(`**/api/developer-sessions/${second.ordinal}/shutdown`,async route=>{stoppedGate.request=route.request();await stoppedGate.release;await route.continue();});
  await page.locator('#developer-close').click();await page.waitForFunction(()=>document.getElementById('developer-close').disabled);await page.locator(`[data-effort-root="${b.ordinal}"]`).click();releaseStop();
  await page.locator(`[data-session-id="${bs.id}"]`).click();await page.locator('#developer-transcript').getByText('result: Effort B conversation',{exact:true}).waitFor();
  await page.unroute(`**/api/developer-sessions/${second.ordinal}/shutdown`);assert.deepEqual(stoppedGate.request.postDataJSON(),{effort_root:root.effort_root,instantiation:second.target.instantiation,session:second.target.session});
  fixture.stdin.write(`seed-large ${root.id}\n`);await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(new Error('seed timeout')),90000);const listener=chunk=>{if(chunk.toString().includes('seeded')){clearTimeout(timeout);fixture.stdout.off('data',listener);resolve();}};fixture.stdout.on('data',listener);});
  await page.locator(`[data-effort-root="${root.effort_root}"]`).click();await page.locator(`[data-session-id="${root.id}"]`).click();await page.locator('#developer-transcript').getByText('Native journal beyond page 500',{exact:true}).waitFor();
  await page.locator('#developer-evidence').evaluate(element=>element.open=true);assert(JSON.parse(await page.locator('#developer-events').textContent()).length>505);
  await page.locator('#developer-global-root').click();await page.locator('#developer-history-heading').getByText('Position 0 ·',{exact:false}).waitFor();assert.equal(await page.locator('#developer-form').isVisible(),false);assert.equal(await page.locator('#developer-model-status').isVisible(),false);
  await page.locator('#developer-global-history').click();await page.locator('#developer-history-heading').getByText('Application history · all efforts',{exact:true}).waitFor();await page.waitForFunction(()=>document.querySelectorAll('#developer-history-list article').length>505);
  await page.screenshot({path:path.join(directory,'application-history.png')});
  assert(requests.some(request=>request.url.includes('/api/ordinals/0/history')&&Number(new URL(request.url).searchParams.get('after'))>100));assert(requests.some(request=>request.url.includes('/api/developer-sessions/'+root.ordinal+'?')&&Number(new URL(request.url).searchParams.get('after'))>500));
  await page.locator('.developer-rail > details summary').click();await page.locator('#developer-legacy-list button').getByText('0 · Original unrelated root',{exact:true}).click();await page.locator('#developer-transcript').getByText('Original namespace journal remains separate',{exact:true}).waitFor();assert.match(await page.locator('#developer-context').textContent(),/no declared effort/);
  await page.locator('.tools-menu [data-page="memory"]').click();assert.match(await page.locator('#legacy-scope-banner').textContent(),/Application-wide \/ unassigned/);assert.equal(await page.locator('#legacy-scope-banner').isVisible(),true);
  fixture.stdin.write(`fail-start ${r.ordinal}\n`);await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(new Error('failed-start fixture timeout')),15000);const listener=chunk=>{if(chunk.toString().includes('failed-started')){clearTimeout(timeout);fixture.stdout.off('data',listener);resolve();}};fixture.stdout.on('data',listener);});
  await page.locator(`[data-effort-root="${r.ordinal}"]`).click();const failed=(await api('/api/developer-sessions?effort_root='+r.ordinal)).sessions.find(row=>!row.target&&row.status==='failed');assert(failed);await page.locator(`[data-session-id="${failed.id}"]`).click();await page.locator('#developer-context').getByText('Reservation retained · no invented native context',{exact:true}).waitFor();assert.equal(await page.locator('#developer-submit').isEnabled(),false);await page.locator('#developer-evidence').evaluate(element=>element.open=true);assert.equal(JSON.parse(await page.locator('#developer-details').textContent()).target,null);assert(JSON.parse(await page.locator('#developer-events').textContent()).length>0);await page.screenshot({path:path.join(directory,'failed-start-history.png')});
  for(const request of requests.filter(request=>request.method==='POST'&&/\/api\/developer-sessions\/0\./.test(new URL(request.url).pathname))){assert(request.body.effort_root);assert(Number.isInteger(request.body.instantiation));assert(Number.isInteger(request.body.session));}
  await page.locator(`[data-effort-root="${root.effort_root}"]`).click();await page.locator(`[data-session-id="${root.id}"]`).click();await page.locator('#developer-heading').getByText('My actual project',{exact:true}).waitFor();await page.locator('#developer-transcript a').getByText('Open source',{exact:true}).waitFor();await page.screenshot({path:path.join(directory,'developer-desktop.png')});await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(directory,'developer-mobile.png')});assert.deepEqual(errors,[]);
  await composerRegression();
  console.log(JSON.stringify({passed:true,checks:['prompt','steer','follow-up','stop-clears-queue','real-rooted-delegation','dialog','server-reconnect','shutdown-reopen','new-browser-history','create-project','existing-file-preservation','markdown-and-source-links','focused-settings-and-inactive-drafts','worker-result-handoff','explicit-reviewed-apply','desktop-mobile','persistent-efforts-samecwd','empty-effort','new-context-same-ordinal','explicit-successor','exact-history-action','switch-preserves-recipient','root0-dormant','global-and-native-pagination','legacy-unadopted','global-unassigned-truth','pre-registration-legacy-preservation','failed-start-scoped-source-investigation'],screenshots:directory}));
 } finally {if(browser)await browser.close();fixture.kill('SIGTERM');if(fixture.exitCode===null)await once(fixture,'exit');if(stderr)process.stderr.write(stderr);}
})().catch(e=>{console.error(e);process.exitCode=1;});
