const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const {once}=require('node:events');
const assert=require('node:assert/strict');
(async()=>{
 const env={PATH:process.env.PATH,PYTHONDONTWRITEBYTECODE:'1'};
 const fixture=spawn('python',['-B','-u','-c',`
import json,tempfile,signal,sys
from pathlib import Path
from scripts.noetic_web import create_server
root=tempfile.TemporaryDirectory(prefix='noetic-recast-shell-')
p=Path(root.name); project=p/'project'; project.mkdir(); runs=p/'runs'; runs.mkdir()
server=create_server(runs,port=0,namespace_path=p/'ordinals.sqlite3',telos_db=p/'telos.sqlite3',session_command=['/bin/false'])
for intent in ['Investigate export boundaries','Design the same project independently']:
 server.developer_sessions.create_effort({'intent':intent,'environment':{'cwd':str(project)}})
print(json.dumps({'url':'http://127.0.0.1:'+str(server.server_port),'token':server.token,'project':str(project)}),flush=True)
def stop(*args):
 server.server_close(); root.cleanup(); sys.exit(0)
signal.signal(signal.SIGTERM,stop)
server.serve_forever()
`],{cwd:process.env.NOETIC_TEST_REPO||require('node:path').resolve(__dirname,'../..'),env,stdio:['ignore','pipe','pipe']});
 let output='',info;fixture.stdout.on('data',chunk=>{output+=chunk});let errors='';fixture.stderr.on('data',c=>errors+=c);
 let browser;
 try{
  for(let i=0;i<100&&!info;i++){try{info=JSON.parse(output.trim().split('\n')[0])}catch(_){}if(!info)await new Promise(r=>setTimeout(r,50));}
  if(!info)throw new Error('Fixture startup failed: '+errors);
  const browserEnv={...process.env};delete browserEnv.USER_PROVIDED_PASSWORD;
  browser=await chromium.launch({headless:true,env:browserEnv,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),pageErrors=[];page.on('pageerror',e=>pageErrors.push(e.message));
  await page.addInitScript(()=>localStorage.setItem('noetic-workspace-v1','{}'));
  if(process.env.NOETIC_TEST_SHELL)await page.route('**/shell.js',r=>r.fulfill({contentType:'text/javascript',body:require('node:fs').readFileSync(process.env.NOETIC_TEST_SHELL,'utf8')}));
  await page.goto(info.url);await page.locator('#access-token').fill(info.token);await page.getByRole('button',{name:'Unlock',exact:true}).click();
  await page.locator('#shell-efforts [data-effort="0.0"]').waitFor();
  let gate=null,held=0,writeCalls=[];
  await page.route('**/api/**',async route=>{if(route.request().method()!=='GET'){writeCalls.push(route.request().url());return route.abort();}if(gate&&new URL(route.request().url()).pathname==='/api/ordinals/0/branch'){held++;await gate.promise;}await route.continue();});
  const hold=()=>{let release;const promise=new Promise(r=>release=r);gate={promise,release};held=0;};
  const release=()=>{const pending=gate;gate=null;pending.release();};
  hold();await page.locator('#shell-efforts [data-effort="0.0"]').click();
  await page.waitForFunction(()=>NoeticSessions.state().selected?.ordinal==='0.0');
  await page.getByRole('button',{name:'Prompt templates',exact:true}).first().click();
  assert.equal(await page.evaluate(()=>NoeticUI.route()),'prompts');
  release();await page.waitForTimeout(1800);
  assert.equal(await page.evaluate(()=>NoeticUI.route()),'prompts','late effort read must preserve subsequent rail navigation');
  await page.getByRole('button',{name:'Workspaces',exact:true}).first().click();
  hold();await page.locator('#shell-efforts [data-effort="0.0"]').click();
  await page.evaluate(()=>{void NoeticSessions.open({ordinal:'0.1',effort_root:'0.1'});});
  assert.equal(await page.evaluate(()=>NoeticUI.route()),'agentics','later exact position notification must not remain suppressed during read');
  release();await page.waitForTimeout(1800);
  assert.equal(await page.evaluate(()=>NoeticUI.route()),'agentics');
  await page.getByRole('button',{name:'Workspaces',exact:true}).first().click();
  hold();await page.locator('#shell-efforts [data-effort="0.0"]').click();
  await page.locator('#shell-efforts [data-effort="0.1"]').click();
  release();await page.waitForTimeout(1800);
  assert.equal(await page.evaluate(()=>NoeticUI.route()),'workspaces');
  assert.equal(await page.evaluate(()=>NoeticSessions.state().effort),'0.1','latest effort selection remains authoritative');
  assert.equal(await page.locator('#shell-page-title').textContent(),'Design the same project independently');
  await page.locator('#shell-efforts [data-effort="0.0"]').click();await page.waitForTimeout(1500);
  assert.equal(await page.evaluate(()=>NoeticUI.route()),'workspaces');
  assert.equal(await page.locator('#shell-page-title').textContent(),'Investigate export boundaries');
  assert.deepEqual(writeCalls,[],'navigation remains read-only');
  assert.deepEqual(pageErrors,[]);console.log('PASS effort navigation: delayed rail choice, later context page event, latest effort, normal completion, read-only fixture');
 }finally{if(browser)await browser.close();fixture.kill('SIGTERM');await once(fixture,'exit').catch(()=>{});}
})().catch(error=>{console.error(error);process.exitCode=1});
