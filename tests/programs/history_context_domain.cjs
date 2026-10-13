const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../..'),source=fs.readFileSync(path.join(root,'scripts/web/sessions.js'),'utf8'),env={...process.env};delete env.USER_PROVIDED_PASSWORD;
 const browser=await chromium.launch({headless:true,env,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent(fs.readFileSync(path.join(root,'scripts/web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,''));
  await page.addScriptTag({content:`const $=id=>document.getElementById(id),node=(tag,value,cls)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;if(cls)e.className=cls;return e;},text=(id,value)=>$(id).textContent=value;let selectionVersion=1,applicationHistory=false,selected={ordinal:'0.1.6',effort_root:'0.1'},effort='0.1',positions=[selected],newConversation=false,actionPending=false,detail=null;const exact=t=>Boolean(t?.id||t?.instantiation),sourceQualifier=()=>'';let allSessions=[{id:'native-exact',effort_root:'0.0',target:{ordinal:'0.0.2',instantiation:2,session:3}},{id:'original-collision',ordinal:'0.1.6',original_ordinal:'0.1.6',target:null,effort_root:null}];let historyRecords=[{sequence:1,ordinal:'0.0.2',effort:'0.0',instantiation:2,session:3,kind:'session-status',data:{status:'closed'},source_ref:{adapter:'developer-sessions'}},{sequence:2,ordinal:'0.1.6',effort:'0.1',instantiation:1,session:1,kind:'structured-activation-status',data:{activation:{id:'activation-6',actor_id:'actor-6'}},source_ref:{adapter:'structured-disciplines',native_run:'/retained/runs/243cb453909f48b08e76f52993ddc50f'}},{sequence:3,ordinal:'0.1.8',effort:'0.1',instantiation:1,session:1,kind:'session-status',data:{status:'closed'},source_ref:{adapter:'unknown-client'}}];function railButton(label,subtitle,target,cls){const b=node('button',label,cls);b.type='button';b.onclick=()=>window.opened=target;return b;}function selectRun(run,evidence){window.structuredOpened={run,evidence};}document.body.append($('developer-history-panel'));`});
  await page.addScriptTag({content:source.slice(source.indexOf('  let historyView ='),source.indexOf('  let transcriptView ='))});
  await page.addScriptTag({content:source.slice(source.indexOf('  function composer()'),source.indexOf('  function railButton('))});
  await page.evaluate(()=>renderHistory());
  const structured=page.locator('.history-row').nth(1),unknown=page.locator('.history-row').nth(2);
  assert.equal(await structured.getByRole('button',{name:/Inspect execution/}).count(),1,'structured history routes to actual source execution');
  await structured.getByRole('button',{name:/Inspect execution/}).click();
  assert.deepEqual(await page.evaluate(()=>structuredOpened),{run:'243cb453909f48b08e76f52993ddc50f',evidence:{activation_id:'activation-6'}});
  assert.equal(await page.evaluate(()=>window.opened),undefined,'structured inspection does not select a native recipient');
  await page.evaluate(()=>{historyRecords[1].data={status:'closed'};historyRecords[1].source_ref={adapter:'structured-disciplines',command_key:'run:243cb453909f48b08e76f52993ddc50f:close-session:activation-6'};renderHistory();});
  await structured.getByRole('button',{name:/Inspect execution/}).click();
  assert.deepEqual(await page.evaluate(()=>structuredOpened),{run:'243cb453909f48b08e76f52993ddc50f',evidence:{activation_id:'activation-6'}},'closed context keeps exact activation through retained source key');
  assert.equal(await unknown.locator('button').count(),0,'unknown backing does not imply native addressability');
  assert.match(await unknown.textContent(),/Native conversation backing.*unavailable/);
  await page.evaluate(()=>{allSessions.push({id:'foreign-collision',effort_root:'0.2',target:{ordinal:'0.1.8',instantiation:1,session:1}});renderHistory();});
  assert.equal(await unknown.locator('button').count(),0,'foreign ownership does not infer native membership from equal target text');
  await page.locator('.history-row').first().getByRole('button',{name:/Open context 2\/3/}).click();
  assert.deepEqual(await page.evaluate(()=>opened),{ordinal:'0.0.2',instantiation:2,session:3,effort_root:'0.0'});
  await page.evaluate(()=>{selected={ordinal:'0.1.6',effort_root:'0.1',instantiation:1,session:1};composer();});
  assert.equal(await page.locator('#developer-form').evaluate(e=>e.hidden),true,'unobserved exact context has no native message composer');
  await page.evaluate(()=>{detail={session:{broker_owned:true}};composer();});
  assert.equal(await page.locator('#developer-form').evaluate(e=>e.hidden),false);assert.equal(await page.locator('#developer-submit').isEnabled(),true);
  await page.evaluate(()=>{detail=null;selected={id:'original-collision'};composer();});
  assert.equal(await page.locator('#developer-form').evaluate(e=>e.hidden),true);
  await page.evaluate(()=>{detail={session:{broker_owned:false}};composer();});assert.equal(await page.locator('#developer-form').evaluate(e=>e.hidden),false);
  await page.evaluate(()=>{detail=null;selected={ordinal:'0.1',effort_root:'0.1'};composer();});assert.equal(await page.locator('#developer-form').evaluate(e=>e.hidden),false,'position new-conversation choice survives');
  assert.deepEqual(errors,[]);console.log('PASS qualified native / structured execution / unavailable source routing; exact unobserved composer hidden, native and project controls retained');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
