const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../..'),env={...process.env};delete env.USER_PROVIDED_PASSWORD;
 const browser=await chromium.launch({headless:true,env,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});
 const positions=[{ordinal:'0',parent:null},{ordinal:'0.0',effort:'0.0',intent:'Alpha',environment:{cwd:'/fixture/alpha'}},{ordinal:'0.1',effort:'0.1',intent:'Beta',environment:{cwd:'/fixture/beta'}}],held=[],calls=[];
 const rows=(ordinal,n)=>Array.from({length:n},(_,i)=>({sequence:i+1,ordinal,effort:ordinal==='0'?null:ordinal,kind:'fixture-event',data:{evidence:`retained-${ordinal}-${i+1}`},source_ref:{fixture:'no-provider'}}));
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://fixture/**',async route=>{
   const request=route.request(),url=new URL(request.url());calls.push({path:url.pathname,method:request.method()});
   if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(root,'scripts/web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'')});
   let result={};
   if(url.pathname==='/api/ordinals/0/branch')result={records:positions,next_after:0};
   else if(url.pathname==='/api/developer-sessions')result={sessions:[],projects_root:'/fixture'};
   else if(url.pathname.endsWith('/history')){
    if(Number(url.searchParams.get('after'))>0)return route.fulfill({contentType:'application/json',body:JSON.stringify({records:[],next_after:Number(url.searchParams.get('after'))})});
    const response=await new Promise(resolve=>held.push({resolve,ordinal:url.pathname.split('/')[3]}));
    return route.fulfill({status:response.status||200,contentType:'application/json',body:JSON.stringify(response.body)});
   }else if(url.pathname.startsWith('/api/ordinals/'))result={position:positions.find(r=>r.ordinal===url.pathname.split('/')[3])};
   return route.fulfill({contentType:'application/json',body:JSON.stringify(result)});
  });
  await page.goto('http://fixture/');
  await page.addScriptTag({content:`const $=id=>document.getElementById(id),node=(tag,value,cls)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;if(cls)e.className=cls;return e;},text=(id,value)=>$(id).textContent=value,error=(id,value)=>{text(id,value);$(id).hidden=!value;};let operatorToken='fixture',accessVersion=0;const switchPage=()=>{$('developer-page').hidden=false;};const fetchJSON=async(p,options)=>{const r=await fetch(p,options),v=await r.json();if(!r.ok)throw new Error(v.error||'fixture failure');return v;};$('private-workspace').hidden=false;document.body.append($('developer-page'));`});
  await page.addScriptTag({path:path.join(root,'scripts/web/sessions.js')});
  await page.waitForFunction(()=>NoeticSessions.state().positions.length===3);
  await page.evaluate(()=>{NoeticSessions.open(null,{history:true});});
  await page.waitForFunction(()=>document.getElementById('developer-history-coverage').textContent.length>0);
  assert.match(await page.locator('#developer-history-coverage').textContent(),/not yet observed|Loading retained history/,'pending first read does not claim zero observed events');
  assert.doesNotMatch(await page.locator('#developer-history-list').textContent(),/No retained events/);
  const next=async()=>{await page.waitForFunction(()=>true);for(let i=0;i<100&&!held.length;i++)await new Promise(r=>setTimeout(r,10));assert.ok(held.length,'owned held history read exists');return held.shift();};
  (await next()).resolve({body:{records:rows('0',20),next_after:20}});
  await page.waitForFunction(()=>NoeticSessions.state().history.length===20);
  assert.equal(await page.locator('.history-row').count(),12);
  await page.locator('.history-row summary').first().click();await page.locator('.history-row summary').first().focus();
  const priorCaption=await page.locator('#developer-history-coverage').textContent();
  await page.evaluate(()=>{window.inspected=document.querySelector('.history-row summary');NoeticSessions.refresh();});
  const stale=await next();assert.equal(await page.locator('#developer-history-coverage').textContent(),priorCaption,'ordinary quick poll retains observed caption');await page.waitForFunction(()=>document.getElementById('developer-history-coverage').textContent.includes('Refreshing retained history'),{timeout:3000});assert.equal(await page.evaluate(()=>document.activeElement===inspected),true);
  stale.resolve({status:503,body:{error:'owned history read unavailable'}});
  await page.waitForFunction(()=>document.getElementById('developer-error').textContent.includes('owned history read unavailable'));
  assert.match(await page.locator('#developer-history-coverage').textContent(),/unavailable.*last observed/s);assert.equal(await page.locator('.history-row').count(),12);assert.equal(await page.evaluate(()=>document.activeElement===inspected&&inspected.parentElement.open),true);
  await page.evaluate(()=>{NoeticSessions.open({ordinal:'0.1',effort_root:'0.1'});});
  const empty=await next();assert.equal(empty.ordinal,'0.1');assert.equal(await page.locator('.history-row').count(),0);assert.doesNotMatch(await page.locator('#developer-history-coverage').textContent(),/20/);
  empty.resolve({body:{records:[],next_after:0}});
  await page.waitForFunction(()=>document.getElementById('developer-history-list').textContent.includes('No retained events observed'));
  assert.match(await page.locator('#developer-history-coverage').textContent(),/0 of 0/);
  await page.evaluate(()=>{NoeticSessions.refresh();});const old=await next();
  await page.evaluate(()=>{NoeticSessions.open({ordinal:'0.0',effort_root:'0.0'});});old.resolve({body:{records:rows('0.1',69),next_after:69}});
  const current=await next();assert.equal(current.ordinal,'0.0');assert.doesNotMatch(await page.locator('#developer-history-coverage').textContent(),/69/);current.resolve({body:{records:rows('0.0',5),next_after:5}});
  await page.waitForFunction(()=>NoeticSessions.state().history.length===5);assert.equal(await page.locator('.history-row').count(),5);assert.equal(await page.evaluate(()=>NoeticSessions.state().history.every(r=>r.ordinal==='0.0')),true);
  await page.evaluate(()=>{NoeticSessions.open({ordinal:'0.1',effort_root:'0.1'});});(await next()).resolve({status:503,body:{error:'owned first read unavailable'}});
  await page.waitForFunction(()=>document.getElementById('developer-error').textContent.includes('owned first read unavailable'));
  assert.match(await page.locator('#developer-history-coverage').textContent(),/unavailable.*No retained history has been observed/s);assert.doesNotMatch(await page.locator('#developer-history-list').textContent(),/No retained events/);
  assert.equal(calls.some(r=>r.method!=='GET'),false);assert.deepEqual(errors,[]);console.log('PASS ordinary history caption retention, genuine slow refresh, complete prior records/focus, initial/error/empty and stale scope guards');
 }finally{for(const read of held)read.resolve({body:{records:[],next_after:0}});await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
