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
    await page.addScriptTag({path:process.env.NOETIC_TOOLS_SOURCE || path.join(root,'scripts/web/sessions.js')});
    await page.evaluate(()=>{
      operatorToken='fixture';document.getElementById('private-workspace').hidden=false;
      window.fixture={posts:[],hold:false,events:[],sessions:[{id:'alpha',ordinal:'0.0',effort_root:'0.0',target:{ordinal:'0.0',instantiation:2,session:3},title:'Fixture Alpha',workspace:'/fixture/alpha',status:'idle',is_current:true,broker_owned:true},{id:'beta',ordinal:'0.1',effort_root:'0.1',target:{ordinal:'0.1',instantiation:1,session:1},title:'Fixture Beta',workspace:'/fixture/beta',status:'idle',is_current:true,broker_owned:true}]};
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
        if(pathname==='/api/ordinals/0/branch')return {records:fixture.positions,next_after:0};
        if(pathname.endsWith('/history'))return {records:[],next_after:0};
        if(pathname.startsWith('/api/ordinals/'))return {position:fixture.positions.find(p=>p.ordinal===pathname.split('/')[3])};
        if(pathname==='/api/developer-sessions')return {sessions:fixture.sessions,projects_root:'/fixture'};
        const after=Number(new URL(url,location.href).searchParams.get('after')||0);return {session:fixture.sessions.find(s=>s.ordinal===pathname.split('/')[3]),events:fixture.events.filter(e=>e.sequence>after),next_after:fixture.events.at(-1)?.sequence||0};
      };
    });
    await page.evaluate(()=>{fixture.sessions[0].status='running';fixture.events=[{sequence:1,record:{type:'message_end',message:{role:'user',content:'Fixture investigate'}}},{sequence:2,record:{type:'message_end',message:{role:'assistant',content:[{type:'text',text:'Checking fixture'},{type:'toolCall',id:'tool-A',name:'bash',arguments:{command:'fixture --check'}}]}}},{sequence:3,record:{type:'tool_execution_start',toolCallId:'tool-A',toolName:'bash',args:{command:'fixture --check'}}}];});
    await page.evaluate(()=>NoeticSessions.open({ordinal:'0.0',effort_root:'0.0',instantiation:2,session:3}));
    if(process.env.NOETIC_TOOLS_BASELINE==='1'){assert.equal(await page.locator('[data-tool-call-id]').count(),0);console.log(JSON.stringify({baseline:true,checks:['journal-tool-start-omitted-from-conversation']}));return;}
    const tool=page.locator('[data-tool-call-id="tool-A"]');
    assert.equal(await tool.count(),1,'message toolCall and execution correlated into one row');
    assert.match(await tool.locator('h3').textContent(),/bash · Running/);assert.equal(await tool.locator('details').evaluate(e=>e.open),false);
    assert.match(await tool.locator('.tool-summary').textContent(),/fixture --check/);
    const order=await page.locator('#developer-transcript > article').evaluateAll(rows=>rows.map(e=>e.dataset.toolCallId||e.dataset.messageSequence));assert.deepEqual(order,['1','2','tool-A']);
    await tool.locator('summary').click();await tool.locator('summary').focus();const original=await tool.elementHandle();
    await page.evaluate(()=>{fixture.events.push({sequence:4,record:{type:'tool_execution_update',toolCallId:'tool-A',toolName:'bash',args:{command:'fixture --check'},partialResult:{content:[{type:'text',text:'Fixture partial output <script>literal</script>'}]}}});});
    await page.waitForFunction(()=>document.querySelector('.tool-output')?.textContent.includes('Fixture partial output'),null,{timeout:5000});
    assert.equal(await original.evaluate(e=>e.isConnected&&e.querySelector('details').open),true,'partial poll retains open node');assert.equal(await tool.locator('summary').evaluate(e=>e===document.activeElement),true);
    assert.equal(await tool.locator('script').count(),0,'output is text');
    await page.evaluate(()=>{fixture.events.push({sequence:5,record:{type:'tool_execution_end',toolCallId:'tool-A',toolName:'bash',isError:false,result:{content:[{type:'text',text:'Fixture final output'}]}}},{sequence:6,record:{type:'message_end',message:{role:'assistant',content:'Fixture completed'}}});});
    await page.evaluate(()=>NoeticSessions.refresh());assert.match(await tool.locator('h3').textContent(),/Completed/);assert.equal(await tool.locator('.tool-output').textContent(),'Fixture final output');assert.equal(await original.evaluate(e=>e.isConnected),true);
    await tool.locator('summary').click();
    await page.evaluate(()=>{fixture.events.push({sequence:7,record:{type:'tool_execution_start',toolCallId:'tool-B',toolName:'read',args:{path:'/fixture/missing'}}},{sequence:8,record:{type:'tool_execution_end',toolCallId:'tool-B',toolName:'read',isError:true,result:{content:[{type:'text',text:'Fixture missing file'}]}}},{sequence:9,record:{type:'tool_execution_end',toolCallId:'tool-C',toolName:'bash',isError:false,result:{content:[{type:'text',text:'Retained end without start'}]}}},{sequence:10,record:{type:'tool_execution_start',toolCallId:'tool-D',toolName:'write',args:{path:'/fixture/interrupted'}}},{sequence:11,record:{type:'message_end',message:{role:'assistant',content:[{type:'toolCall',id:'tool-E',name:'read',arguments:{path:'/fixture/requested'}}]}}});fixture.sessions[0].status='idle';});
    await page.evaluate(()=>NoeticSessions.refresh());assert.equal(await tool.locator('details').evaluate(e=>e.open),false,'explicit collapse survives new events');
    const failure=page.locator('[data-tool-call-id="tool-B"]');assert.match(await failure.locator('h3').textContent(),/Failed/);assert.match(await failure.locator('.tool-summary').textContent(),/fixture\/missing/);await failure.locator('summary').click();assert.match(await failure.locator('.tool-output').textContent(),/Fixture missing file/);
    assert.match(await page.locator('[data-tool-call-id="tool-C"] h3').textContent(),/Completed · start unobserved/);
    assert.match(await page.locator('[data-tool-call-id="tool-D"] h3').textContent(),/Completion unobserved/);
    assert.match(await page.locator('[data-tool-call-id="tool-E"] h3').textContent(),/Requested · execution unobserved/);
    const finalOrder=await page.locator('#developer-transcript > article').evaluateAll(rows=>rows.map(e=>e.dataset.toolCallId||e.dataset.messageSequence));assert.deepEqual(finalOrder,['1','2','tool-A','6','tool-B','tool-C','tool-D','tool-E']);
    await page.evaluate(()=>{fixture.sessions[1].status='closed';fixture.events=[{sequence:1,record:{type:'tool_execution_start',toolCallId:'tool-A',toolName:'read',args:{path:'/fixture/beta'}}},{sequence:2,record:{type:'tool_execution_end',toolCallId:'tool-A',toolName:'read',isError:false,result:{content:[{type:'text',text:'Beta historical output'}]}}}];});
    await page.evaluate(()=>NoeticSessions.open({ordinal:'0.1',effort_root:'0.1',instantiation:1,session:1}));assert.equal(await page.locator('[data-tool-call-id]').count(),1);assert.equal(await tool.locator('details').evaluate(e=>e.open),false,'same call id in another session does not transfer disclosure');assert.doesNotMatch(await page.locator('#developer-transcript').textContent(),/Fixture final|Fixture missing/);assert.equal(await tool.locator('.tool-output').textContent(),'Beta historical output');assert.match(await tool.locator('h3').textContent(),/read · Completed/);
    assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,checks:['chronological-tool-rows','message-call-deduplication','running-partial-final-output','failure-visible','missing-start-and-end-honesty','requested-execution-unobserved','historical-session','session-call-id-isolation','tool-disclosure-and-focus-retention','explicit-collapse','safe-output-text']}));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
