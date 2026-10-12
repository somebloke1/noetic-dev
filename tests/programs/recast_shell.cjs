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
`],{cwd:require('node:path').resolve(__dirname,'../..'),env,stdio:['ignore','pipe','pipe']});
 let output='',info;fixture.stdout.on('data',chunk=>{output+=chunk});let errors='';fixture.stderr.on('data',c=>errors+=c);
 let browser;
 try{
  for(let i=0;i<100&&!info;i++){try{info=JSON.parse(output.trim().split('\n')[0])}catch(_){}if(!info)await new Promise(r=>setTimeout(r,50));}
  if(!info)throw new Error('Fixture startup failed: '+errors);
  browser=await chromium.launch({headless:true,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),pageErrors=[];page.on('pageerror',e=>pageErrors.push(e.message));
  await page.addInitScript(()=>localStorage.setItem('noetic-workspace-v1','{}'));
  await page.goto(info.url);await page.locator('#access-token').fill(info.token);await page.getByRole('button',{name:'Unlock',exact:true}).click();
  await page.locator('#shell-efforts [data-effort="0.0"]').waitFor();
  await page.locator('#previous-drafts').waitFor({state:'visible'});assert.equal(await page.locator('#import-previous-drafts').isVisible(),true);assert.equal(await page.locator('#forget-previous-drafts').isVisible(),true);
  assert.equal(await page.locator('#shell-navigation button').count(),10);
  assert.equal(await page.locator('#shell-filter .project-scope-row').count(),1);
  await page.locator('#shell-efforts [data-effort="0.0"]').click();await page.locator('#shell-page-title').filter({hasText:'Investigate export boundaries'}).waitFor();
  await page.waitForTimeout(2700);
  assert.equal(await page.locator('#shell-project-scope .scope-label').count(),1,'scope metadata duplicated by observation');
  await page.route('**/api/developer-sessions',r=>r.abort());await page.route('**/api/runs?*',r=>r.abort());
  await page.evaluate(async()=>{await Promise.all([NoeticSessions.refresh(),refresh()]);});
  await page.locator('#shell-observation-error').waitFor({state:'visible'});await page.locator('#fetch-error').waitFor({state:'visible'});assert.match(await page.locator('#shell-health').textContent(),/unavailable/);
  await page.unroute('**/api/developer-sessions');await page.unroute('**/api/runs?*');await page.evaluate(async()=>{await Promise.all([NoeticSessions.refresh(),refresh()]);});
  await page.locator('#shell-observation-error').waitFor({state:'hidden'});await page.locator('#fetch-error').waitFor({state:'hidden'});assert.equal(await page.locator('#shell-health').textContent(),'Observations available');
  const widths=await page.evaluate(()=>({rail:document.querySelector('.global-rail').getBoundingClientRect().width,sidebar:document.querySelector('.effort-sidebar').getBoundingClientRect().width,viewport:innerWidth,body:document.documentElement.scrollWidth}));
  assert.equal(widths.rail,64);assert.equal(widths.sidebar,248);assert.ok(widths.body<=widths.viewport+1,'shell horizontally overflows');
  await page.locator('#sidebar-resizer').focus();await page.keyboard.press('ArrowRight');assert.equal(await page.locator('#sidebar-resizer').getAttribute('aria-valuenow'),'260');
  await page.getByRole('button',{name:'New effort',exact:true}).first().click();await page.locator('#effort-intent').fill('Independent third responsibility');await page.locator('#effort-directory').fill(info.project);await page.getByRole('button',{name:'Create effort',exact:true}).click();
  await page.locator('#shell-efforts [data-effort="0.2"]').waitFor();await page.locator('#shell-page-title').filter({hasText:'Independent third responsibility'}).waitFor();assert.equal(await page.locator('#shell-page-title').textContent(),'Independent third responsibility');
  const sessions=await page.evaluate(async()=>await fetch('/api/developer-sessions',{headers:{Authorization:'Bearer '+sessionStorage.getItem('noetic-operator-token')}}).then(r=>r.json()));assert.equal(sessions.sessions.length,0,'effort creation invoked a session');
  await page.keyboard.press('Control+k');await page.locator('#shell-command-query').fill('Disciplines');await page.getByRole('button',{name:'Disciplines',exact:true}).last().click();await page.locator('#shell-content[data-route="disciplines"]').waitFor();assert.equal(await page.locator('#shell-sidebar').isVisible(),false);
  await page.getByRole('button',{name:'Workspaces',exact:true}).first().click();await page.getByRole('button',{name:'New effort',exact:true}).first().click();assert.equal(await page.locator('#effort-intent').isVisible(),true,'revisited creation form absent');
  await page.evaluate(()=>document.fonts.ready);assert.ok(await page.evaluate(()=>document.fonts.check('12px Inter')&&document.fonts.check('12px "DM Mono"')));
  assert.deepEqual(pageErrors,[]);console.log('PASS shell: actual effort registration, same-folder isolation, no runtime start, stable polling, navigation, sizing, keyboard resizing, fonts');
 }finally{if(browser)await browser.close();fixture.kill('SIGTERM');await once(fixture,'exit').catch(()=>{});}
})().catch(error=>{console.error(error);process.exitCode=1});
