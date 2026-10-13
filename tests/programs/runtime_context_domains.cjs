const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../..'),env={...process.env};delete env.USER_PROVIDED_PASSWORD;
 const browser=await chromium.launch({headless:true,env,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent(fs.readFileSync(path.join(root,'scripts/web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,''));
  await page.addScriptTag({content:`let selection={scope:'application'},currentRoute='runtime';const operationSelection=()=>selection;window.allRuns=[];window.records=[{id:'reserved',ordinal:'0.3.0.2',effort_root:'0.3',identity_origin:'ordinal-reserved',target:null,native_session_file:null,title:'Reserved startup',status:'failed'},{id:'original',ordinal:'0.3.0.2',effort_root:null,identity_origin:'legacy-unadopted',target:null,native_session_file:'/owned/original.jsonl',title:'Original conversation',status:'closed'},{id:'native',ordinal:'0.3',effort_root:'0.3',target:{ordinal:'0.3',instantiation:1,session:2},native_session_file:'/owned/native.jsonl',title:'Native conversation',status:'running'},{id:'unknown',ordinal:null,effort_root:null,target:null,native_session_file:null,title:'Unobserved record',status:'starting'}];window.opens=[];window.NoeticSessions={open:async target=>opens.push(target)};const handlers=new Map();window.NoeticUI={element:(tag,cls,value)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(value!==undefined)e.textContent=value;return e;},button:(value,fn,cls)=>{const b=document.createElement('button');b.type='button';b.textContent=value;if(cls)b.className=cls;b.addEventListener('click',fn);return b;},heading:()=>{},mount:(id,host)=>{const e=document.getElementById(id);host.append(e);e.hidden=false;},register:(route,fn)=>handlers.set(route,fn),snapshot:()=>({sessions:records}),route:()=>currentRoute,navigate:route=>{window.destination=route;},refresh:()=>{const host=document.getElementById('shell-content');host.dataset.route=currentRoute;return handlers.get(currentRoute)?.({host,route:currentRoute,snapshot:NoeticUI.snapshot()});}};document.getElementById('private-workspace').hidden=false;`});
  await page.addScriptTag({path:path.join(root,'scripts/web/shell-library.js')});await page.evaluate(()=>NoeticUI.refresh());
  assert.ok((await page.locator('.lib-metric span').allTextContents()).includes('Retained native contexts'),'runtime count must distinguish native backing');
  const metric=name=>page.locator('.lib-metric').filter({has:page.locator('span',{hasText:name})}).locator('strong');
  assert.equal(await metric('Retained native contexts').textContent(),'2');
  assert.equal(await metric('Startup reservations').textContent(),'1');
  assert.equal(await metric('Native context unobserved').textContent(),'1');
  assert.equal(await metric('Running native contexts').textContent(),'1');
  const row=title=>page.locator('.lib-runtime-row').filter({hasText:title});
  assert.match(await row('Reserved startup').innerText(),/Reserved position.*native context unobserved/);
  assert.match(await row('Original conversation').innerText(),/Original namespace.*unadopted/);
  assert.match(await row('Unobserved record').innerText(),/Native context unobserved/);
  await row('Reserved startup').getByRole('button',{name:'Inspect startup observation',exact:true}).click();assert.deepEqual(await page.evaluate(()=>opens.at(-1)),{id:'reserved'});
  await row('Original conversation').getByRole('button',{name:'Inspect / control',exact:true}).click();assert.deepEqual(await page.evaluate(()=>opens.at(-1)),{id:'original'});
  await row('Native conversation').getByRole('button',{name:'Inspect / control',exact:true}).click();assert.deepEqual(await page.evaluate(()=>opens.at(-1)),{ordinal:'0.3',instantiation:1,session:2,effort_root:'0.3'});
  await row('Reserved startup').getByRole('button').focus();await page.evaluate(()=>NoeticUI.refresh());assert.equal(await page.evaluate(()=>document.activeElement.textContent),'Inspect startup observation','unchanged observation preserves focus');
  await page.evaluate(()=>{records[0].native_session_file='/owned/new.jsonl';records[0].target={ordinal:'0.3.0.2',instantiation:1,session:1};return NoeticUI.refresh();});
  assert.equal(await metric('Retained native contexts').textContent(),'3','new native-file observation updates despite unchanged timestamp');
  assert.equal(await metric('Startup reservations').textContent(),'0');
  await page.evaluate(()=>{selection={scope:'effort',effort_root:'0.3'};return NoeticUI.refresh();});assert.equal(await page.locator('.lib-runtime-row').count(),2);
  await page.evaluate(()=>{records=[];return NoeticUI.refresh();});assert.match(await page.locator('#shell-content').innerText(),/No retained runtime observations/);
  assert.deepEqual(errors,[]);console.log('PASS runtime domains: native-file coverage, reservations/unknowns, qualified identity, unchanged exact opens, scope and observation transitions');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
