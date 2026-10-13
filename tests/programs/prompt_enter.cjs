// Disposable DOM/API fixtures using production frontend handlers; no service or actor runs.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
  const root=path.resolve(__dirname,'../..'),env={...process.env};delete env.USER_PROVIDED_PASSWORD;
  const browser=await chromium.launch({headless:true,env,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});
  try {
    const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
    const html=fs.readFileSync(path.join(root,'scripts/web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'');
    await page.route('http://127.0.0.1:49151/**',route=>route.fulfill({contentType:route.request().url().endsWith('/')?'text/html':'text/plain',body:route.request().url().endsWith('/')?html:''}));
    await page.goto('http://127.0.0.1:49151/');
    await page.addScriptTag({path:path.join(root,'scripts/web/app.js')});
    await page.addScriptTag({path:path.join(root,'scripts/web/sessions.js')});
    await page.evaluate(()=>{
      operatorToken='fixture';document.getElementById('private-workspace').hidden=false;
      window.fixture={posts:[],hold:false,sessions:[{id:'alpha',ordinal:'0.0',effort_root:'0.0',target:{ordinal:'0.0',instantiation:2,session:3},title:'Fixture Alpha',workspace:'/fixture/alpha',status:'idle',is_current:true,broker_owned:true},{id:'beta',ordinal:'0.1',effort_root:'0.1',target:{ordinal:'0.1',instantiation:1,session:1},title:'Fixture Beta',workspace:'/fixture/beta',status:'idle',is_current:true,broker_owned:true}]};
      fixture.positions=[{ordinal:'0',status:'open'},{ordinal:'0.0',effort:'0.0',parent:'0',intent:'Fixture Alpha',environment:{cwd:'/fixture/alpha'}},{ordinal:'0.1',effort:'0.1',parent:'0',intent:'Fixture Beta',environment:{cwd:'/fixture/beta'}}];
      for(const id of ['developer-page','new-page'])document.body.append(document.getElementById(id));
      switchPage=name=>{document.getElementById('developer-page').hidden=name!=='developer';document.getElementById('new-page').hidden=name!=='new';};
      refresh=async()=>{};
      fetchJSON=async(url,options={})=>{
        const pathname=new URL(url,location.href).pathname;
        if(options.method==='POST') {
          fixture.posts.push({url,body:JSON.parse(options.body)});
          if(fixture.hold)await new Promise(resolve=>fixture.release=resolve);
          if(pathname==='/api/disciplines')return {discipline:{id:'fixture-discipline'}};
          if(pathname==='/api/application/start')throw new Error('Fixture intercept: no actor launched');
          return {accepted:true};
        }
        if(pathname==='/api/disciplines')return {namespace_registered:true,namespace_id:'fixture-enter-namespace',definitions:[]};
        if(pathname==='/api/ordinals/0/branch')return {records:fixture.positions,next_after:0};
        if(pathname.endsWith('/history'))return {records:[],next_after:0};
        if(pathname.startsWith('/api/ordinals/'))return {position:fixture.positions.find(p=>p.ordinal===pathname.split('/')[3])};
        if(pathname==='/api/developer-sessions')return {sessions:fixture.sessions,projects_root:'/fixture'};
        return {session:fixture.sessions.find(s=>s.ordinal===pathname.split('/')[3]),events:[],next_after:0};
      };
    });
    await page.evaluate(()=>NoeticSessions.open({ordinal:'0.0',effort_root:'0.0',instantiation:2,session:3}));
    const prompt=page.locator('#developer-prompt');await prompt.fill('Fixture exact prompt');
    if(process.env.NOETIC_ENTER_BASELINE==='1') {
      await prompt.press('Enter');assert.equal(await prompt.inputValue(),'Fixture exact prompt\n');assert.equal(await page.evaluate(()=>fixture.posts.length),0);
      console.log(JSON.stringify({baseline:true,checks:['enter-inserts-newline-without-submit']}));return;
    }
    const settle=()=>page.waitForFunction(()=>!document.getElementById('developer-submit').disabled);
    const posts=()=>page.evaluate(()=>fixture.posts);
    const suppressed=async(field,options)=>{await field.evaluate((el,options)=>el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true,...options})),options);};
    await prompt.press('Shift+Enter');assert.equal(await prompt.inputValue(),'Fixture exact prompt\n');assert.equal((await posts()).length,0);
    await suppressed(prompt,{isComposing:true});await suppressed(prompt,{keyCode:229});await suppressed(prompt,{repeat:true});assert.equal((await posts()).length,0);
    await prompt.fill('');await prompt.press('Enter');assert.equal((await posts()).length,0,'required prompt validation retained');
    await prompt.fill('Fixture exact prompt');await page.evaluate(()=>document.getElementById('developer-submit').disabled=true);await prompt.press('Enter');assert.equal((await posts()).length,0);await page.evaluate(()=>document.getElementById('developer-submit').disabled=false);
    await page.evaluate(()=>fixture.hold=true);await prompt.press('Enter');await page.waitForFunction(()=>fixture.posts.length===1);
    assert.deepEqual((await posts())[0],{url:'/api/developer-sessions/0.0/prompt',body:{effort_root:'0.0',instantiation:2,session:3,message:'Fixture exact prompt',mode:'prompt'}});
    await prompt.press('Enter');await suppressed(prompt,{repeat:true});assert.equal((await posts()).length,1,'pending and repeat cannot duplicate');
    await prompt.fill('Newer draft');await page.evaluate(()=>{fixture.hold=false;fixture.release();});await settle();assert.equal(await prompt.inputValue(),'Newer draft','later draft survives Enter submission acknowledgment');
    await prompt.fill('Scoped Alpha');await page.evaluate(()=>fixture.hold=true);await prompt.press('Enter');await page.waitForFunction(()=>fixture.posts.length===2);
    await page.evaluate(()=>NoeticSessions.open({ordinal:'0.1',effort_root:'0.1',instantiation:1,session:1}));await prompt.fill('Beta unsent');await page.evaluate(()=>{fixture.hold=false;fixture.release();});await settle();assert.equal(await prompt.inputValue(),'Beta unsent','selection change preserves new context draft');
    assert.equal((await posts())[1].body.effort_root,'0.0');
    await prompt.fill('Fixture Beta');await prompt.press('Enter');await page.waitForFunction(()=>fixture.posts.length===3);await settle();assert.equal(await prompt.inputValue(),'');
    await page.evaluate(()=>{switchPage('new');NoeticEffort.catalogue(fixture.positions);NoeticEffort.select('0.0',{ordinal:'0.0'});});await page.waitForFunction(()=>NoeticDrafts.ready());await page.evaluate(()=>{document.getElementById('start-profile').value='';document.getElementById('start-model').value='fixture/model';document.getElementById('start-pattern').value='cognition';document.getElementById('start-task').focus();});
    const task=page.locator('#start-task');await task.fill('Structured fixture');await task.press('Shift+Enter');assert.equal(await task.inputValue(),'Structured fixture\n');
    await suppressed(task,{isComposing:true});await suppressed(task,{repeat:true});assert.equal((await posts()).length,3);
    await task.fill('');await task.press('Enter');assert.equal((await posts()).length,3);
    await task.fill('Structured fixture');await page.evaluate(()=>{document.getElementById('start-submit').disabled=true;});await task.press('Enter');assert.equal((await posts()).length,3);await page.evaluate(()=>{document.getElementById('start-submit').disabled=false;fixture.hold=true;});
    await task.press('Enter');await page.waitForFunction(()=>fixture.posts.length===4);await task.press('Enter');await suppressed(task,{repeat:true});assert.equal((await posts()).length,4);
    assert.equal((await posts())[3].body.effort_root,'0.0');
    await page.evaluate(()=>{NoeticEffort.select('0.1',{ordinal:'0.1'});});await page.waitForFunction(()=>NoeticDrafts.ready());await task.fill('New Beta structured draft');await page.evaluate(()=>{fixture.hold=false;fixture.release();});await page.waitForFunction(()=>!document.getElementById('start-submit').disabled);
    const start=(await posts()).find(p=>p.url==='/api/application/start');assert.equal(start.body.task,'Structured fixture');assert.equal(start.body.effort_root,'0.0');assert.equal(start.body.workspace,'/fixture/alpha');assert.equal(await task.inputValue(),'New Beta structured draft');assert.equal(await page.locator('#start-error').textContent(),'','old scope error does not leak');
    // Other textareas keep their existing newline behavior.
    await page.evaluate(()=>showSettings('purpose'));await page.locator('#start-sources').fill('Source fixture');await page.locator('#start-sources').press('Enter');assert.equal(await page.locator('#start-sources').inputValue(),'Source fixture\n');
    assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,checks:['enter-exact-submit','shift-enter-newline','ime-and-repeat-guard','form-validation','disabled-and-pending-guard','new-draft-preserved','selection-version-preserved','structured-exact-scope','structured-new-draft-preserved','other-textarea-unchanged']}));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
