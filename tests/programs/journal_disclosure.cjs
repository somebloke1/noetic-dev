const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../..'),source=fs.readFileSync(path.join(root,'scripts/web/app.js'),'utf8');
 const section=(start,end)=>source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)));
 const env={...process.env};delete env.USER_PROVIDED_PASSWORD;
 const browser=await chromium.launch({headless:true,env,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent(fs.readFileSync(path.join(root,'scripts/web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,''));
  await page.addStyleTag({path:path.join(root,'scripts/web/style.css')});
  await page.addScriptTag({content:`const $=id=>document.getElementById(id);const node=(tag,value,cls)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;if(cls)e.className=cls;return e;};const text=(id,value)=>$(id).textContent=value;const date=value=>value;const title=value=>value;const tone=value=>'';let selectedId='fixture-run',selectedDetail, kernelSignature='',timelineSignature='';const cancelling=new Set();const renderActor=()=>{},renderArtifact=()=>{},loadActorLog=()=>{},renderWorkbench=()=>{},renderEvidence=()=>{},switchView=()=>{};const actorIdentity=a=>a.id;const renderSessionAgents=()=>{};const operationSelection=()=>({scope:'application'});`});
  const helper=source.includes('function renderEventWindow(')?section('const eventWindows =','function eventMeaning('):'';
  await page.addScriptTag({content:helper+section('function eventMeaning(','function renderArtifact(')+section('function renderController(','async function loadDetail(')+section('function renderReviewedDetail(','async function recoverReviewed(')});
  const pattern=JSON.parse(fs.readFileSync(path.join(root,'scripts/patterns/cognition.json'),'utf8'));
  await page.evaluate(pattern=>{
   const kernelEvent=n=>({id:`event-${n}`,version:n,kind:'transition',data:{phase:'P1',from:'inquiry',to:'reflection',on:'fixture'}});
   const state={pattern,phase_index:0,status:'active',machine_state:'fixture',version:38,generation:0,visits:Object.fromEntries(pattern.phases.map(p=>[p.id,1])),max_remediations:1,returns_used:0,max_returns:2,current_activation:null,activations:{},actors:{},artifacts:{chosen:{id:'chosen',type:'fixture',phase:'P1',produced_by:'fixture',generation:0},other:{id:'other',type:'fixture',phase:'P2',produced_by:'fixture',generation:0}},slots:{},feedback:[],events:Array.from({length:38},(_,i)=>kernelEvent(i+1))};
   window.fixtureDetail={controller:state,controller_path:'/fixture/controller.sqlite3',journal_path:'/fixture/events.jsonl',observed_at:'fixture',status:{run_id:'fixture-run',goal:'Fixture',state:'blocked',workspace:'/fixture',journal_state:'blocked',steps:{}},events:state.events.map((event,i)=>({sequence:i+1,occurred_at:'2026-10-12T00:00:00Z',kind:'controller.event',data:event})),artifacts:{}};
   document.body.append($('workspace-page'));selectedDetail=fixtureDetail;renderDetail(selectedDetail);$('artifact-select').value='chosen';
   document.querySelector('#private-workspace').hidden=false;document.querySelector('#run-detail').hidden=false;document.querySelector('#selected-run').hidden=false;document.querySelector('#evidence-drawer').open=true;document.querySelector('#controller-view').hidden=false;document.querySelector('#timeline-view').hidden=false;
  },pattern);
  assert.equal(await page.locator('#controller-events > li').count(),12,'initial kernel history bounded');
  assert.equal(await page.locator('#timeline > li').count(),12,'initial journal history bounded');
  assert.match(await page.locator('#controller-events-disclosure').innerText(),/12 of 38/);
  await page.locator('#controller-events details summary').first().click();await page.locator('#controller-events details summary').first().focus();
  await page.evaluate(()=>{window.retained=document.querySelector('#controller-events li');window.retainedSummary=retained.querySelector('summary');const event={id:'event-39',version:39,kind:'transition',data:{phase:'P1',from:'reflection',to:'responsibility',on:'fixture'}};fixtureDetail.controller.events.push(event);fixtureDetail.controller.version=39;fixtureDetail.events.push({sequence:39,occurred_at:'2026-10-12T00:00:00Z',kind:'controller.event',data:event});renderDetail(fixtureDetail);});
  assert.equal(await page.evaluate(()=>document.querySelector('#controller-events li')===retained),true,'focused earliest visible event retained across appended poll');
  assert.equal(await page.evaluate(()=>document.activeElement===retainedSummary),true,'event focus survives changed poll');
  assert.equal(await page.evaluate(()=>retained.querySelector('details').open),true);
  assert.match(await page.locator('#controller-events-disclosure').innerText(),/13 of 39/);
  assert.equal(await page.locator('#artifact-select').inputValue(),'chosen');
  for(const id of ['controller-events','timeline']){
   while(await page.locator(`#${id}-disclosure button`).isEnabled())await page.locator(`#${id}-disclosure button`).click();
   assert.equal(await page.locator(`#${id} > li`).count(),39,'complete history reachable');
  }
  assert.equal(await page.locator('#artifact-select').inputValue(),'chosen','load earlier preserves selected artifact');
  assert.deepEqual(await page.evaluate(()=>[...document.querySelectorAll('#controller-events details')].map(e=>e.dataset.eventId)),Array.from({length:39},(_,i)=>`event-${i+1}`));
  assert.deepEqual(await page.evaluate(()=>[...document.querySelectorAll('#timeline details')].map(e=>Number(e.dataset.sequence))),Array.from({length:39},(_,i)=>i+1));
  await page.evaluate(()=>renderDetail(fixtureDetail));assert.equal(await page.locator('#timeline > li').count(),39,'poll preserves disclosed amount');
  assert.equal(await page.evaluate(()=>fixtureDetail.events.length),39,'source journal intact');
  await page.evaluate(()=>{const list=document.createElement('ol');list.id='burst-events';document.body.append(list);window.burstEvents=Array.from({length:38},(_,i)=>({id:i+1}));window.burstRow=event=>{const row=node('li');row.dataset.id=event.id;const details=node('details');details.append(node('summary',`Event ${event.id}`),node('pre',String(event.id)));row.append(details);return row;};renderEventWindow('burst-events',burstEvents,burstRow);});
  await page.locator('#burst-events summary').first().click();await page.locator('#burst-events summary').first().focus();
  await page.evaluate(()=>{burstEvents.push(...Array.from({length:30},(_,i)=>({id:i+39})));renderEventWindow('burst-events',burstEvents,burstRow);});
  assert.equal(await page.locator('#burst-events > li').count(),42);
  await page.locator('#burst-events-disclosure button').click();
  assert.equal(await page.locator('#burst-events > li').count(),54,'one Load earlier click adds12older rows after retained30event burst');
  assert.equal(await page.locator('#burst-events > li').first().getAttribute('data-id'),'15');
  await page.evaluate(()=>{selectedId='reviewed-run';selectedDetail={backend:'opermem-reviewed',status:{run_id:'reviewed-run',goal:'Reviewed fixture',state:'blocked'},correspondence:{effort_root:'0.0',discipline_id:1,execution_id:1},preparation:{workspace:'/fixture',run_dir:'/fixture',operation:'question'},population:[],application:{configuration:{client:'fixture'},native:{disposition:'unobserved'},review:{},actions:{}},events:Array.from({length:8},(_,i)=>({sequence:i+1,kind:'fixture',data:{index:i+1}})),artifacts:{}};renderDetail(selectedDetail);});
  assert.equal(await page.locator('#timeline > li').count(),8);
  await page.evaluate(()=>{selectedDetail.events.push(...Array.from({length:32},(_,i)=>({sequence:i+9,kind:'fixture',data:{index:i+9}})));renderDetail(selectedDetail);});
  assert.equal(await page.locator('#timeline > li').count(),12,'initial small history does not grow unbounded on polling');
  while(await page.locator('#timeline-disclosure button').isEnabled())await page.locator('#timeline-disclosure button').click();
  assert.equal(await page.locator('#timeline > li').count(),40,'reviewed native journal remains fully reachable');
  assert.deepEqual(await page.evaluate(()=>[...document.querySelectorAll('#timeline li pre')].map(e=>JSON.parse(e.textContent).sequence)),Array.from({length:40},(_,i)=>i+1));
  assert.deepEqual(errors,[]);console.log('PASS journal disclosure: initial12, complete39, exact order, appended active inspection, focus/open retention, selected artifact and polling');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
