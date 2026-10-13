const {chromium}=require('playwright'),{spawn}=require('node:child_process'),{once}=require('node:events'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{const root=path.resolve(__dirname,'../..'),env={PATH:process.env.PATH,PYTHONDONTWRITEBYTECODE:'1'},fixture=spawn('python',['-B','-u','-c',`
import json,tempfile,signal,sys
from pathlib import Path
from scripts.noetic_web import create_server
owned=tempfile.TemporaryDirectory(prefix='noetic-effort-drafts-'); p=Path(owned.name)
dirs={}
for name in ['shared','dup','revised','guard','second']:
    d=p/name; d.mkdir(); dirs[name]=str(d)
(p/'runs').mkdir()
server=create_server(p/'runs',port=0,namespace_path=p/'namespace.sqlite3',telos_db=p/'telos.sqlite3',session_command=['/bin/false'])
print(json.dumps({'url':'http://127.0.0.1:'+str(server.server_port),'token':server.token,'dirs':dirs}),flush=True)
def stop(*a):server.server_close();owned.cleanup();sys.exit(0)
signal.signal(signal.SIGTERM,stop);server.serve_forever()
`],{cwd:root,env,stdio:['ignore','pipe','pipe']});let output='',stderr='',info,browser;fixture.stdout.on('data',x=>output+=x);fixture.stderr.on('data',x=>stderr+=x);
try{for(let i=0;i<150&&!info;i++){try{info=JSON.parse(output.split('\n')[0])}catch{}if(!info)await new Promise(r=>setTimeout(r,30));}assert.ok(info,stderr);const dirs=info.dirs,browserEnv={...process.env};delete browserEnv.USER_PROVIDED_PASSWORD;browser=await chromium.launch({headless:true,env:browserEnv,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],postBodies=[];
let holdNext=false,releaseHeld=null,failPosts=false,failRefreshGets=false;
const armHold=()=>{holdNext=true;releaseHeld=null;};
page.on('pageerror',e=>{errors.push(e.message);console.error('effort-pageerror',e.message);});
await page.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url());
 if(req.method()==='POST'&&url.pathname==='/api/efforts'){postBodies.push(JSON.parse(req.postData()));if(holdNext){holdNext=false;await new Promise(r=>releaseHeld=r);}if(failPosts)return route.abort();const real=await route.fetch();return route.fulfill({response:real});}
 if(req.method()!=='GET')return route.abort();
 if(failRefreshGets&&(url.pathname==='/api/developer-sessions'||url.pathname==='/api/ordinals/0/branch'))return route.abort();
 return route.continue();});
await page.goto(info.url+'/#token='+encodeURIComponent(info.token));await page.waitForFunction(()=>window.NoeticSessions&&NoeticSessions.state&&NoeticSessions.state().positions!==undefined);
const openNewEffort=async()=>{await page.evaluate(()=>NoeticUI.navigate('new-effort'));await page.locator('#effort-intent').waitFor({state:'visible'});};
const nav=route=>page.evaluate(r=>NoeticUI.navigate(r),route);
const waitStatus=needle=>page.waitForFunction(n=>{const s=document.querySelector('form.effort-create-form .form-status');return s&&s.textContent.includes(n);},needle,{timeout:8000});
const submitBtn=()=>page.locator('form.effort-create-form button[type="submit"]');
const statusText=()=>page.locator('form.effort-create-form .form-status').textContent();
// First effort, application scope, no registered namespace/persistence/memory: plain navigation and Configuration return retain raw draft text.
await openNewEffort();await page.locator('#effort-intent').fill('  Shared reading list\n');await page.locator('#effort-directory').fill(' '+dirs.shared+' ');
await nav('workspaces');await openNewEffort();
assert.equal(await page.locator('#effort-intent').inputValue(),'  Shared reading list\n','raw intent draft retained across ordinary navigation');
assert.equal(await page.locator('#effort-directory').inputValue(),' '+dirs.shared+' ','raw cwd draft retained across ordinary navigation');
await nav('configuration');await openNewEffort();
assert.equal(await page.locator('#effort-intent').inputValue(),'  Shared reading list\n','raw intent draft retained across configuration return');
// Held success: real backend POST, edits while pending, remount; immutable submitted body, newer draft retained, created ordinal status through remount.
armHold();await submitBtn().click();
await page.waitForFunction(()=>{const b=document.querySelector('form.effort-create-form button[type="submit"]');return b&&b.disabled;});
assert.equal(postBodies.length,1,'exactly one POST while pending');assert.equal(postBodies[0].intent,'Shared reading list','API intent trimmed');assert.equal(postBodies[0].environment.cwd,dirs.shared,'API cwd trimmed');
await page.locator('#effort-intent').fill('  Newer intent  ');await page.locator('#effort-directory').fill(' '+dirs.second+' ');
await nav('workspaces');releaseHeld();await page.waitForTimeout(120);
assert.equal(await page.evaluate(()=>NoeticUI.route()),'workspaces','response must not steal changed navigation');
await openNewEffort();
assert.equal(await page.locator('#effort-intent').inputValue(),'  Newer intent  ','edited pending draft retained after out-of-context success');
assert.equal(await page.locator('#effort-directory').inputValue(),' '+dirs.second+' ','edited pending cwd retained after out-of-context success');
await waitStatus('created');
assert.match(await statusText(),/0\.0/,'real returned effort ordinal shown as created status after remount');
assert.equal(await submitBtn().isDisabled(),false,'edited draft may start a new deliberate draft after created status');
assert.equal(postBodies.length,1,'still exactly one POST');
// Duplicate requestSubmit and custom submit after remount while pending stay one POST.
await page.locator('#effort-intent').fill('Dup intent');await page.locator('#effort-directory').fill(dirs.dup);
armHold();await submitBtn().click();
await page.waitForFunction(()=>{const b=document.querySelector('form.effort-create-form button[type="submit"]');return b&&b.disabled;});
await nav('workspaces');await openNewEffort();
await page.evaluate(()=>document.querySelector('form.effort-create-form').requestSubmit());
await page.evaluate(()=>document.querySelector('form.effort-create-form').dispatchEvent(new Event('submit',{cancelable:true,bubbles:true})));
assert.equal(postBodies.length,2,'duplicate submission after remount stays one POST');
assert.equal(postBodies[1].intent,'Dup intent','submitted body captured once');
releaseHeld();await waitStatus('created');
await page.waitForFunction(()=>document.getElementById('effort-intent').value==='','unchanged submitted draft cleared after out-of-context success',{timeout:8000});
assert.match(await statusText(),/0\.1/,'real effort 0.1 created');
assert.equal(await page.evaluate(()=>NoeticUI.route()),'new-effort','stale request cannot navigate after route away and back');
assert.equal(postBodies.length,2,'no duplicate POST after success');
// Held failure with edits while pending: exact revised text and failure status follow remount; deliberate retry succeeds against the real backend.
await page.locator('#effort-intent').fill('  Retry intent  ');await page.locator('#effort-directory').fill(dirs.revised);
failPosts=true;armHold();await submitBtn().click();
await page.waitForFunction(()=>{const b=document.querySelector('form.effort-create-form button[type="submit"]');return b&&b.disabled;});
await page.locator('#effort-intent').fill('  Retry intent revised  ');
await nav('workspaces');releaseHeld();await page.waitForTimeout(120);
await openNewEffort();await waitStatus('failed');
assert.equal(await page.locator('#effort-intent').inputValue(),'  Retry intent revised  ','exact revised text retained on failure after remount');
assert.equal(await submitBtn().isDisabled(),false,'deliberate retry available after failure');
assert.equal(postBodies.length,3,'failed POST counted once');
failPosts=false;await submitBtn().click();
await page.waitForFunction(o=>NoeticSessions.state().effort===o,'0.2',{timeout:8000});
assert.equal(await page.evaluate(()=>NoeticUI.route()),'workspaces','successful real create opens the created effort 0.2');
assert.equal(postBodies.length,4,'retry POSTed exactly once');
// Refresh failure after successful POST (real API GETs fail at the boundary): identity kept, no duplicate recreation, status follows remount.
await openNewEffort();await page.locator('#effort-intent').fill('  Guard intent  ');await page.locator('#effort-directory').fill(dirs.guard);
failRefreshGets=true;await submitBtn().click();
await waitStatus('refreshing the workspace failed');
assert.equal(postBodies.length,5,'guard submit POSTed exactly once');
assert.equal(await submitBtn().isDisabled(),true,'no duplicate recreation after successful POST with failed refresh');
assert.equal(await page.locator('#effort-intent').inputValue(),'  Guard intent  ','draft retained on refresh failure');
await page.evaluate(()=>document.querySelector('form.effort-create-form button[type="submit"]').click());
assert.equal(postBodies.length,5,'still exactly five POSTs after refresh failure');
failRefreshGets=false;await nav('workspaces');await openNewEffort();
await waitStatus('created');
assert.match(await statusText(),/0\.3/,'created ordinal status kept through remount after refresh failure');
assert.equal(await submitBtn().isDisabled(),true,'unchanged created draft still guarded after remount');
await page.locator('#effort-intent').fill('  Guard intent next  ');
assert.equal(await submitBtn().isDisabled(),false,'edited draft unblocks new deliberate submission');
assert.equal(postBodies.length,5,'editing alone does not POST');
// Late success after navigation and explicit effort B selection cannot steal chosen context.
await page.locator('#effort-intent').fill('Second effort');await page.locator('#effort-directory').fill(dirs.second);
armHold();await submitBtn().click();
await page.waitForFunction(()=>{const b=document.querySelector('form.effort-create-form button[type="submit"]');return b&&b.disabled;});
await page.getByRole('button',{name:/Development portfolio/}).click();await page.locator('#shell-efforts [data-effort="0.2"]').click();
await page.waitForFunction(()=>NoeticSessions.state().effort==='0.2',{timeout:8000});
releaseHeld();await page.waitForTimeout(150);
assert.equal(await page.evaluate(()=>NoeticUI.route()),'workspaces','response did not steal explicit chosen-effort navigation');
assert.equal(await page.evaluate(()=>NoeticSessions.state().effort),'0.2','chosen effort 0.2 context preserved over created 0.5');
assert.equal(postBodies.length,6,'one POST per deliberate submission only');
await openNewEffort();await page.waitForFunction(()=>document.getElementById('effort-intent').value==='','unchanged submitted draft cleared after stolen-context success',{timeout:8000});
await waitStatus('created');
assert.deepEqual(errors,[]);console.log('PASS effort draft continuity: raw retention, held real-backend success/failure with pending edits, remount status continuity, one POST under duplicate/recreated submission, generation/context guard, refresh-failure duplicate guard, first-effort creation');
}finally{if(browser)await browser.close();fixture.kill('SIGTERM');await once(fixture,'exit').catch(()=>{});}})().catch(e=>{console.error(e);process.exitCode=1;});
