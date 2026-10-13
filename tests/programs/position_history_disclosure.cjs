const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../..'),source=fs.readFileSync(path.join(root,'scripts/web/sessions.js'),'utf8'),env={...process.env};delete env.USER_PROVIDED_PASSWORD;
 const browser=await chromium.launch({headless:true,env,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent(fs.readFileSync(path.join(root,'scripts/web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,''));await page.addStyleTag({path:path.join(root,'scripts/web/style.css')});await page.addStyleTag({path:path.join(root,'scripts/web/shell-agentics.css')});
  await page.addScriptTag({content:`const $=id=>document.getElementById(id);const node=(tag,value,cls)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;if(cls)e.className=cls;return e;};const text=(id,value)=>$(id).textContent=value;let allSessions=[{id:'native-fixture',effort_root:'0.0',target:{ordinal:'0.0',instantiation:1,session:1}}];let historyObservation={status:"observed",observed:true,error:null};let selectionVersion=1,applicationHistory=false,selected={ordinal:'0.0',effort_root:'0.0'},effort='0.0',positions=[selected],historyRecords=[];const exact=t=>Boolean(t?.id||t?.instantiation);function railButton(label,subtitle,target,cls){const button=node('button',label,cls);button.type='button';button.onclick=()=>window.opened=target;return button;}window.eventRecord=n=>({sequence:n,ordinal:'0.0',effort:'0.0',kind:n%2?'native.message':'context.recorded',source_ref:'source-'+n,instantiation:1,session:1});historyRecords=Array.from({length:4168},(_,i)=>eventRecord(i+1));document.body.append($('developer-history-panel'));`});
  await page.addScriptTag({content:source.slice(source.indexOf('  let historyView ='),source.indexOf('  let transcriptView ='))});
  await page.evaluate(()=>renderHistory());
  assert.equal(await page.locator('.history-row').count(),12,'initial4168 history rows bounded tolatest12');
  assert.match(await page.locator('#developer-history-coverage').textContent(),/12.*4168/s);
  assert.deepEqual(await page.locator('.history-row pre').evaluateAll(rows=>rows.map(row=>JSON.parse(row.textContent).sequence)),Array.from({length:12},(_,i)=>4157+i));
  await page.locator('.history-row summary').first().click();await page.locator('.history-row summary').first().focus();
  await page.evaluate(()=>{window.inspectedRow=document.querySelector('.history-row');window.inspectedSummary=inspectedRow.querySelector('summary');historyRecords.push(...Array.from({length:30},(_,i)=>eventRecord(4169+i)));renderHistory();});
  assert.equal(await page.locator('.history-row').count(),42,'active inspection retains older suffix across burst');
  assert.equal(await page.evaluate(()=>document.activeElement===inspectedSummary),true);assert.equal(await page.evaluate(()=>inspectedRow.querySelector('details').open),true);
  await page.locator('#developer-history-more').click();assert.equal(await page.locator('.history-row').count(),54,'one earlier12 click advances from current shown suffix');
  await page.locator('#developer-history-query').fill('source-2"');
  assert.equal(await page.locator('.history-row').count(),1,'exact source-ref search reaches oldoffpage record');
  assert.equal(await page.locator('.history-row pre').evaluate(row=>JSON.parse(row.textContent).sequence),2);
  await page.locator('.history-row button').click();assert.deepEqual(await page.evaluate(()=>opened),{ordinal:'0.0',instantiation:1,session:1,effort_root:'0.0'},'exact retained context link preserved');
  await page.locator('#developer-history-query').focus();await page.evaluate(()=>renderHistory());assert.equal(await page.evaluate(()=>document.activeElement.id),'developer-history-query');assert.equal(await page.locator('#developer-history-query').inputValue(),'source-2"');
  await page.locator('#developer-history-clear').click();await page.locator('#developer-history-kind').selectOption('native.message');
  assert.match(await page.locator('#developer-history-coverage').textContent(),/2099.*4198/s,'kind matching count distinct from fullhistory');
  assert.equal(await page.locator('.history-row').count(),12);
  await page.locator('#developer-history-clear').click();
  await page.evaluate(()=>{++selectionVersion;applicationHistory=true;selected=null;effort=null;historyRecords=Array.from({length:41},(_,i)=>eventRecord(i+1));renderHistory();});
  assert.equal(await page.locator('.history-row').count(),12,'new application binding resets initial window');
  while(await page.locator('#developer-history-more').isEnabled())await page.locator('#developer-history-more').click();
  assert.deepEqual(await page.locator('.history-row pre').evaluateAll(rows=>rows.map(row=>JSON.parse(row.textContent).sequence)),Array.from({length:41},(_,i)=>i+1),'complete ordered history remains reachable');
  await page.evaluate(()=>{historyRecords.push(eventRecord(42));renderHistory();});assert.equal(await page.locator('.history-row').count(),42,'explicit full disclosure includes later event');
  assert.equal(await page.evaluate(()=>historyRecords.length),42,'source array unchanged');
  await page.locator('#developer-history-query').fill('no matching source');assert.equal(await page.locator('.history-row').count(),0);assert.match(await page.locator('#developer-history-coverage').textContent(),/0.*42/s);
  assert.deepEqual(errors,[]);console.log('PASS history: latest12/4168, full source order, active inspection/burst and earlier12, kind/source filtering, exact links, query focus, binding reset, full disclosure');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
