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
    const native=process.env.NOETIC_PROVENANCE_EVIDENCE ? JSON.parse(fs.readFileSync(process.env.NOETIC_PROVENANCE_EVIDENCE,'utf8')) : {role:'custom',customType:'noetic-agent-message',content:'Model-visible route guidance',details:{message:'hello child',mode:'follow_up',binding_id:3,provenance:{origin:'agent',sender:{ordinal:'0.0',instantiation:1,session:1},recipient:{ordinal:'0.0.0',instantiation:1,session:1},effort_root:'0.0',reply_to:{ordinal:'0.0',instantiation:1,session:1},in_reply_to:null}}};
    await page.evaluate(message=>{
      fixture.events=[{sequence:1,record:{type:'message_end',message}},
        {sequence:2,record:{type:'message_end',message:{role:'user',content:'Noetic agent message Sender: 0.0',details:message.details}}},
        {sequence:3,record:{type:'message_end',message:{role:'assistant',content:'local reply'}}}];
    },native);
    await page.evaluate(()=>NoeticSessions.open({ordinal:'0.0',effort_root:'0.0',instantiation:2,session:3}));
    if(process.env.NOETIC_PROVENANCE_BASELINE==='1') {
      assert.equal(await page.locator('[data-message-sequence="1"]').count(),0,'previous renderer omitted native custom message');
      assert.equal(await page.locator('[data-message-sequence="2"] h3').textContent(),'You');
      console.log(JSON.stringify({baseline:true,checks:['native-custom-agent-message-omitted']}));return;
    }
    const row=page.locator('[data-message-sequence="1"]');
    assert.equal(await row.locator('h3').textContent(),`Agent ${native.details.provenance.sender.ordinal} · instantiation ${native.details.provenance.sender.instantiation} · session ${native.details.provenance.sender.session}`);
    assert.equal(await row.locator('pre').textContent(),native.details.message);
    assert.match(await row.locator('small').textContent(),new RegExp(`Message ${native.details.binding_id}`));
    assert.equal(await page.locator('[data-message-sequence="2"] h3').textContent(),'You','text origin claim and attached details do not relabel ordinary human input');
    assert.equal(await page.locator('[data-message-sequence="3"] h3').textContent(),'Agent 0.0');
    const retained=await row.elementHandle();
    await page.evaluate(()=>NoeticSessions.refresh());
    assert.equal(await retained.evaluate(e=>e.isConnected),true,'canonical message row retained across poll');
    await page.evaluate(()=>{fixture.sessions[0].status='closed';});
    await page.evaluate(()=>NoeticSessions.refresh());
    assert.equal(await row.locator('pre').textContent(),native.details.message,'historical sender is retained');
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({passed:true,checks:['native-custom-agent-message-rendered','full-exact-sender-label','canonical-binding-recipient-evidence','ordinary-human-spoof-remains-You','local-assistant-reply-is-local','poll-and-history-retain-origin']}));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
