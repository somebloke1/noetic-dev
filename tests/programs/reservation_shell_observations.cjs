const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../..'),env={...process.env};delete env.USER_PROVIDED_PASSWORD;
 const browser=await chromium.launch({headless:true,env,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://fixture/**',route=>route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(root,'scripts/web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'')}));await page.goto('http://fixture/');
  await page.addScriptTag({content:`window.$=id=>document.getElementById(id);window.allRuns=[];window.fixture={effort:'0.3',positions:[{ordinal:'0.3',effort:'0.3',intent:'Owned effort',status:'active',environment:{cwd:'/owned'}}],sessions:[{id:'reserved',ordinal:'0.3.0.2',effort_root:'0.3',identity_origin:'ordinal-reserved',target:null,status:'failed',title:'Reserved startup',error:'Exact startup refusal',updated_at:'3'},{id:'original',ordinal:'0.3.0.2',original_ordinal:'0.3.0.2',effort_root:null,identity_origin:'legacy-unadopted',target:null,status:'failed',title:'Original conversation',updated_at:'2'},{id:'native',ordinal:'0.3',effort_root:'0.3',target:{ordinal:'0.3',instantiation:1,session:2},status:'failed',title:'Exact conversation',updated_at:'1'}]};window.opens=[];window.NoeticSessions={state:()=>fixture,open:value=>opens.push(value),refresh:()=>{}};window.fetchJSON=async()=>({});sessionStorage.setItem('noetic-shell-view',JSON.stringify({route:'attention'}));$('private-workspace').hidden=false;`});
  await page.addScriptTag({path:path.join(root,'scripts/web/shell.js')});
  const content=page.locator('#shell-content');
  let reserved=content.locator('.record-row').filter({hasText:'Reserved startup'});
  assert.match(await reserved.innerText(),/Reserved position.*native context unobserved/);
  assert.doesNotMatch(await reserved.innerText(),/Original namespace|inst-/);
  assert.match(await content.locator('.record-row').filter({hasText:'Original conversation'}).innerText(),/Original namespace.*unadopted/,'ordinal collision does not adopt original');
  assert.match(await content.locator('.record-row').filter({hasText:'Exact conversation'}).innerText(),/inst-1.*session 2/);
  assert.match(await content.innerText(),/coverage: Application.*startup reservations/i);
  await reserved.focus();await page.evaluate(()=>document.dispatchEvent(new CustomEvent('noetic:sessions',{detail:fixture})));
  assert.equal(await page.evaluate(()=>document.activeElement.textContent.includes('Reserved startup')),true,'unchanged poll preserves row focus');
  await reserved.click();assert.deepEqual(await page.evaluate(()=>opens.at(-1)),{id:'reserved'});
  await page.evaluate(()=>NoeticUI.navigate('history'));
  assert.match(await content.locator('.record-row').filter({hasText:'Reserved startup'}).innerText(),/Reserved position.*native context unobserved/);
  await content.locator('.record-row').filter({hasText:'Original conversation'}).click();assert.deepEqual(await page.evaluate(()=>opens.at(-1)),{id:'original'});
  await page.evaluate(()=>NoeticUI.navigate('workspaces'));
  const entry=content.locator('.work-entry').filter({hasText:'Reserved startup'});
  assert.match(await entry.innerText(),/Reserved position.*native context unobserved/);
  assert.doesNotMatch(await entry.innerText(),/Original namespace|Retained conversation/);
  assert.match(await content.locator('.summary-strip').innerText(),/2 retained observations/);
  await content.locator('.attention-entry').filter({hasText:'Reserved startup'}).getByRole('button',{name:'Inspect reserved position',exact:true}).click();assert.deepEqual(await page.evaluate(()=>opens.at(-1)),{id:'reserved'});
  await page.evaluate(()=>NoeticUI.navigate('history'));await content.locator('.record-row').filter({hasText:'Exact conversation'}).click();
  assert.deepEqual(await page.evaluate(()=>opens.at(-1)),{ordinal:'0.3',instantiation:1,session:2,effort_root:'0.3'});
  assert.deepEqual(errors,[]);console.log('PASS reservation shell: exact native/original/reservation attribution, coverage, overview, unchanged poll and original open targets');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
