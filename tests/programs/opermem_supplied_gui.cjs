const {chromium}=require(process.env.NOETIC_PLAYWRIGHT||'playwright');
const {spawn}=require('node:child_process');const {once}=require('node:events');const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../..'),output=process.env.NOETIC_GUI_EVIDENCE;assert.ok(output);fs.mkdirSync(output,{recursive:true});
 const env={...process.env,PYTHONDONTWRITEBYTECODE:'1'};delete env.USER_PROVIDED_PASSWORD;
 const fixture=spawn('python',['-B','-u','-m','tests.programs.opermem_supplied_gui_fixture'],{cwd:root,env,stdio:['pipe','pipe','pipe']});
 let bytes='',errors='',info;fixture.stdout.on('data',x=>bytes+=x);fixture.stderr.on('data',x=>errors+=x);
 const command=action=>fixture.stdin.write(JSON.stringify({action})+'\n');let browser,page;
 try{
  for(let i=0;i<200&&!info;i++){try{info=JSON.parse(bytes.split('\n')[0])}catch(_){}if(!info)await new Promise(r=>setTimeout(r,30));}assert.ok(info,errors);
  browser=await chromium.launch({headless:true,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});page=await browser.newPage({viewport:{width:1440,height:1000}});const pageErrors=[];page.on('pageerror',e=>pageErrors.push(e.message));
  const api=async(route,body)=>{const r=await page.request.fetch(info.url+route,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+info.token},...(body?{data:body}:{})});assert.ok(r.ok(),await r.text());return r.json();};
  await page.goto(info.url+'/#token='+encodeURIComponent(info.token));await page.locator('#shell-efforts [data-effort="0.0"]').waitFor();await page.locator('#shell-efforts [data-effort="0.0"]').click();await page.waitForFunction(()=>document.getElementById('shell-page-title').textContent==='River station inquiry');await page.waitForTimeout(300);
  await page.evaluate(()=>{switchPage('new');NoeticUI.navigate('new-work');});await page.locator('#start-pattern').selectOption('opermem-reviewed');await page.locator('#reviewed-setup').waitFor({state:'visible'});
  await page.locator('#reviewed-operation option').nth(13).waitFor({state:'attached'});assert.equal(await page.locator('#reviewed-operation option').count(),14);
  await page.locator('#reviewed-operation').selectOption('checking');assert.equal(await page.locator('#start-submit').isDisabled(),true);assert.match(await page.locator('#reviewed-operation-note').textContent(),/checking_spec.*checking_context/);await page.locator('#reviewed-operation').selectOption('question');
  await page.locator('#reviewed-setup details').first().locator('summary').click();await page.locator('#reviewed-directory').fill(info.backing);await page.locator('#reviewed-register').click();await page.waitForFunction(()=>!!document.getElementById('reviewed-store').value);
  assert.equal(fs.existsSync(info.backing),false,'browsing/registration bootstrapped memory');
  await page.locator('#start-task').fill('How should the station report uncertainty when the selected daily sample evidence is incomplete?');await page.locator('#reviewed-sources').fill(info.source);
  await page.locator('#start-change-model').click();await page.locator('#start-profile').selectOption('');await page.locator('#start-client').selectOption('opencode');await page.locator('#start-model').fill('fixture/independent');await page.locator('#start-close-settings').click();
  await page.screenshot({path:path.join(output,'composer.png'),fullPage:false});await page.locator('#start-submit').click();
  await page.waitForFunction(()=>document.getElementById('start-result').textContent.includes('Original run'));
  await page.waitForFunction(()=>document.getElementById('reviewed-progress').textContent.includes('Driver ownership observed'));
  assert.match(await page.locator('#run-id').textContent(),/0\.0 · discipline.*execution/);assert.equal(await page.locator('#cancel-pattern').isVisible(),false);
  assert.match(await page.locator('#steering-note').textContent(),/Pause, Stop, Apply and conversational continuation/);
  const heldRun=await page.evaluate(()=>selectedId);
  await page.evaluate(()=>NoeticUI.navigate('memory'));await page.locator('.lib-native-record').first().locator('summary').first().click();
  await page.locator('.lib-native-record').getByText('Retained native receipt',{exact:true}).waitFor();
  const receipt=page.locator('.lib-native-record details').filter({has:page.locator('summary').getByText('Retained native receipt',{exact:true})});
  command('release');await page.waitForFunction(()=>[...document.querySelectorAll('.lib-native-record [data-key]')].some(d=>d.dataset.key==='Retained native receipt' && d.querySelector('pre').textContent!=='null'));
  await page.evaluate(id=>selectRun(id),heldRun);
  await page.waitForFunction(()=>document.getElementById('reviewed-report').textContent.includes('Useful investigation'));
  await page.waitForFunction(()=>document.getElementById('reviewed-dispositions').textContent.includes('receipt-retained'));
  const first=await page.evaluate(()=>selectedId);const detail=await api('/api/runs/'+first+'?effort_root=0.0');assert.equal(detail.population.length,2);assert.notDeepEqual(detail.population[0].target,detail.population[1].target);
  await page.locator('#evidence-drawer > summary').click();await page.locator('#reviewed-evidence > summary').click();await page.locator('#reviewed-evidence-content details').nth(2).locator('summary').click();
  await page.evaluate(()=>refresh());assert.equal(await page.locator('#reviewed-evidence').getAttribute('open'),'');assert.equal(await page.locator('#reviewed-evidence-content details').nth(2).getAttribute('open'),'');
  await page.locator('#reviewed-recover-contribution').click();await page.waitForFunction(()=>document.getElementById('reviewed-recovery-status').textContent.includes('No actors replayed'));
  await page.locator('#session-select').selectOption('review');await page.waitForFunction(()=>document.getElementById('session-transcript').textContent.includes('ACCEPT'));assert.match(await page.locator('#primary-agent').textContent(),/context/);
  await page.screenshot({path:path.join(output,'result-evidence.png'),fullPage:false});
  await page.evaluate(()=>NoeticUI.navigate('memory'));await page.locator('.lib-native-record').first().locator('summary').first().click();await page.locator('.lib-native-record').getByText('Retained native receipt',{exact:true}).waitFor();
  await page.locator('#memory-query').fill('Useful');await page.locator('#memory-submit').click();await page.locator('#memory-results .search-result').first().waitFor();await page.getByRole('button',{name:'Select source for inquiry draft'}).first().click();
  await page.evaluate(()=>{switchPage('new');NoeticUI.navigate('new-work');});assert.equal(await page.locator('#reviewed-selected-sources .reviewed-source').count(),1);await page.locator('#start-task').fill('What follow-up question does the original investigation leave open?');
  await page.evaluate(()=>NoeticUI.navigate('memory'));await page.screenshot({path:path.join(output,'typed-memory.png'),fullPage:false});
  // A/B/R reuse and delayed request checks exercise the exact same cwd with distinct owners.
  let releaseRoute, readyRoute, finishedRoute, intercepted=false;
  const ready=new Promise(r=>readyRoute=r),finished=new Promise(r=>finishedRoute=r);
  await page.route('**/api/opermem/stores?effort_root=0.0',async route=>{
    if(intercepted){await route.continue();return;}intercepted=true;
    const response=await route.fetch();readyRoute();await new Promise(r=>releaseRoute=r);await route.fulfill({response});finishedRoute();
  });
  await page.evaluate(()=>{void loadReviewedSetup();});await ready;
  await page.evaluate(()=>{NoeticEffort.select('0.1',null);NoeticUI.refresh();});releaseRoute();await finished;await page.unroute('**/api/opermem/stores?effort_root=0.0');await page.waitForTimeout(150);
  assert.equal(await page.locator('.lib-native-record').count(),0);assert.equal(await page.locator('#reviewed-selected-sources .reviewed-source').count(),0);assert.equal(await page.locator('#reviewed-store').inputValue(),'');
  await page.evaluate(()=>{NoeticEffort.select('0.2',null);NoeticUI.refresh();});assert.equal(await page.locator('.lib-native-record').count(),0);
  await page.evaluate(()=>{NoeticEffort.select('0.0',null);NoeticUI.navigate('executions');});await page.evaluate(id=>selectRun(id),first);
  page.once('dialog',d=>d.accept());await page.locator('#reuse-setup').click();await page.locator('#reviewed-setup').waitFor({state:'visible'});assert.equal(await page.locator('#reviewed-store').inputValue(),'');assert.equal(await page.locator('#start-purpose').inputValue(),'');assert.equal(await page.locator('#start-task').inputValue(),detail.status.goal);
  // Actual rejected actor and retained correlation recovery use accepted fixture boundaries.
  command('failure');await page.locator('#reviewed-refresh').click();await page.waitForFunction(()=>document.getElementById('reviewed-store').options.length>1);await page.locator('#reviewed-store').selectOption({index:1});await page.locator('#start-submit').click();
  await page.waitForFunction(()=>document.getElementById('run-state').textContent==='failed');assert.match(await page.locator('#session-select').textContent(),/native target unobserved/);
  command('gap');await page.evaluate(()=>{switchPage('new');NoeticUI.navigate('new-work');});await page.locator('#start-task').fill('Inspect retained correspondence failure.');await page.locator('#start-submit').click();await page.waitForFunction(()=>document.getElementById('run-state').textContent==='preparation-failed');
  await page.locator('#reviewed-recover-correlation').click();await page.waitForFunction(()=>document.getElementById('reviewed-recovery-status').textContent.length>0);
  await page.route('**/api/application/launches?*',r=>r.abort());await page.evaluate(()=>loadReviewedLaunches());assert.match(await page.locator('#start-result').textContent(),/observation unavailable/);await page.unroute('**/api/application/launches?*');await page.evaluate(()=>loadReviewedLaunches());
  const calls=fs.readFileSync(path.join(info.root,'calls.jsonl'),'utf8').trim().split('\n').map(JSON.parse);assert.equal(calls.length,3,'recovery relaunched actors');assert.notEqual(calls[0].pid,calls[1].pid);
  assert.deepEqual(pageErrors,[]);fs.writeFileSync(path.join(output,'browser-result.json'),JSON.stringify({passed:true,assertions:'actual asynchronous question/native receipt; distinct actors/targets; retained exact evidence; fourteen capacity; scoped recall/draft/reuse; A/B/R cancellation; actor failure; correlation recovery; disconnection; no replay',first_run:first,population:detail.population,calls},null,2));console.log('PASS reviewed supplied GUI');
 }catch(error){if(page){fs.writeFileSync(path.join(output,'failure-state.json'),JSON.stringify(await page.evaluate(()=>({route:NoeticUI.route(),page:currentPage,error:document.getElementById('shell-notice').textContent,detail:document.getElementById('detail-error').textContent,form:document.getElementById('new-page').outerHTML,errors:document.getElementById('start-error').textContent})),null,2));await page.screenshot({path:path.join(output,'failure.png'),fullPage:false});}throw error;}finally{if(browser)await browser.close();if(info)command('stop');fixture.stdin.end();await once(fixture,'exit').catch(()=>{});if(errors)fs.writeFileSync(path.join(output,'fixture.log'),errors);}
})().catch(e=>{console.error(e);process.exitCode=1;});
