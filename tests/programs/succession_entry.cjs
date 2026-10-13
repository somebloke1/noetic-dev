const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const root = path.resolve(__dirname,'../..');
  const index = fs.readFileSync(path.join(root,'scripts/web/index.html'),'utf8');
  const developer = index.slice(index.lastIndexOf('<section',index.indexOf('id="developer-page"')), index.lastIndexOf('<div',index.indexOf('id="workspace-page"')));
  const html = `<!doctype html><html><head><meta charset="utf-8"></head><body><main id="host"></main><div id="private-workspace">${developer}</div>${['developer-project-open','developer-new','developer-global-root','developer-global-history','refresh'].map(id=>`<button id="${id}">${id}</button>`).join('')}${['developer-session-list','developer-agent-list','developer-legacy-list'].map(id=>`<div id="${id}"></div>`).join('')}</body></html>`;
  // Explicit disposable browser fixtures; no runtime stores or provider calls.
  const positions = [{ordinal:'0',parent:null,status:'open'}, {ordinal:'0.0',parent:'0',effort:'0.0',intent:'Alpha',current_instantiation:2,origin:'human',environment:{cwd:'/fixture/alpha'}}, {ordinal:'0.0.0',parent:'0.0',effort:'0.0',origin:'human',current_instantiation:1}, {ordinal:'0.1',parent:'0',effort:'0.1',intent:'Beta',current_instantiation:1,origin:'human',environment:{cwd:'/fixture/beta'}}];
  const retained = {id:'retained',ordinal:'0.0',effort_root:'0.0',target:{ordinal:'0.0',instantiation:1,session:1},title:'Retained exact Alpha',workspace:'/fixture/alpha',model:'fixture/model',thinking:'high',status:'closed',is_current:false,broker_owned:false,domain_status:'superseded'};
  const current = {...retained,id:'current',target:{ordinal:'0.0',instantiation:2,session:1},title:'Current Alpha',status:'idle',is_current:true,broker_owned:true,domain_status:'open'};
  const beta = {...current,id:'beta',ordinal:'0.1',effort_root:'0.1',target:{ordinal:'0.1',instantiation:1,session:1},title:'Current Beta',workspace:'/fixture/beta'};
  const child={...retained,id:'child',ordinal:'0.0.0',target:{ordinal:'0.0.0',instantiation:1,session:1},title:'Evidence review · closed',domain_status:'closed'};
  const sessions=[retained,current,beta,child], calls=[];
  const history=[{sequence:1,ordinal:'0',kind:'application-created',source_ref:{path:'fixture-source-1'}},{sequence:2,ordinal:'0.0',effort:'0.0',target:{ordinal:'0.0',instantiation:1,session:1},kind:'effort-created',source_ref:{path:'fixture-source-2'}}];
  const returns=[{sequence:3,ordinal:'0.0',effort:'0.0',kind:'structured-controller-event',data:{controller_event:{kind:'cognition.returned',data:{target:'P2'}}}}];
  const childEnv={...process.env};delete childEnv.USER_PROVIDED_PASSWORD;
  const browser=await chromium.launch({headless:true,env:childEnv,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
    page.on('pageerror',error=>{errors.push(error.message);console.error('fixture-pageerror',error.message);});
    await page.route('http://fixture/**',async route=>{
      const url=new URL(route.request().url()),body=route.request().postDataJSON();calls.push({path:url.pathname,query:Object.fromEntries(url.searchParams),body,method:route.request().method()});
      let result={};
      if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
      if(url.pathname==='/api/ordinals/0/branch')result={records:positions,next_after:0};
      else if(url.pathname.endsWith('/history'))result={records:url.pathname==='/api/ordinals/0/history' ? [...history,...returns] : history.filter(row=>row.ordinal===url.pathname.split('/')[3]),next_after:0};
      else if(url.pathname.startsWith('/api/ordinals/')){const position=positions.find(item=>item.ordinal===url.pathname.split('/')[3]);result={position:position.ordinal==='0.0.0' ? {...position,intent:'Alpha effort intent',mandate:{mandate:{title:'Evidence review',purpose:'Review evidence and preserve uncertainty'}}} : position};}
      else if(url.pathname==='/api/developer-sessions')result={sessions,projects_root:'/fixture'};
      else if(route.request().method()==='POST')result={stopped:true};
      else {const ordinal=url.pathname.split('/')[3],instantiation=Number(url.searchParams.get('instantiation'));const session=sessions.find(item=>item.ordinal===ordinal&&item.target.instantiation===instantiation)||sessions.find(item=>item.id===ordinal);result={session,events:url.searchParams.get('after')==='0' ? Array.from({length:2637},(_,i)=>({sequence:i+1,record:{type:'fixture_raw_evidence',source:'Complete raw fixture evidence '+ 'x'.repeat(400)}})) : [],next_after:2637};}
      await route.fulfill({contentType:'application/json',body:JSON.stringify(result)});
    });
    await page.goto('http://fixture/');
    await page.addScriptTag({content:`const $=id=>document.getElementById(id);let operatorToken='fixture',accessVersion=0,operationVersion=0,selectedId=null;const operationSelection=()=>({});const scopedURL=p=>p;const switchPage=()=>{};const fetchJSON=async(p,options)=>{const r=await fetch(p,options);return r.json();};const node=(tag,value,cls)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;if(cls)e.className=cls;return e;};const text=(id,value)=>$(id).textContent=value;const error=(id,value)=>{text(id,value);$(id).hidden=!value;};window.NoeticUI={element:(tag,cls,value)=>node(tag,value,cls),button:(value,action,cls)=>{const b=node('button',value,cls);b.type='button';b.onclick=action;return b;},mount:(id,host)=>{host.append($(id));$(id).hidden=false;},heading:options=>{window.lastHeading=options;},register:(route,handler)=>window.agenticsRender=handler};`});
    await page.addStyleTag({path:path.join(root,'scripts/web/style.css')});
    await page.addStyleTag({path:path.join(root,'scripts/web/shell-agentics.css')});
    await page.addScriptTag({path:path.join(root,'scripts/web/sessions.js')});
    await page.addScriptTag({path:path.join(root,'scripts/web/shell-agentics.js')});
    await page.waitForFunction(()=>NoeticSessions.state().sessions.length===4);
    await page.evaluate(()=>agenticsRender({host:document.getElementById('host'),snapshot:NoeticSessions.state()}));
    await page.evaluate(()=>NoeticSessions.open({ordinal:'0.0',instantiation:2,session:1,effort_root:'0.0'}));
    await page.evaluate(()=>document.getElementById('developer-evidence').open=true);
    const ordering=await page.locator('#developer-evidence').evaluate(e=>({first:e.children[0].tagName,retainedIndex:[...e.children].findIndex(n=>n.id==='agentics-retained-details'),rawIndex:[...e.children].findIndex(n=>n.id==='developer-events'),height:e.scrollHeight}));
    assert.equal(ordering.first,'SUMMARY','outer disclosure retains its summary first');
    assert(ordering.retainedIndex<ordering.rawIndex,'handoff group precedes accumulated raw evidence');
    assert.equal(await page.locator('#agentics-retained-details').evaluate(e=>e.firstElementChild.tagName),'DETAILS','handoff is first retained action');
    await page.locator('#developer-evidence').evaluate(e=>e.scrollTop=0);
    const evidenceBox=await page.locator('#developer-evidence').boundingBox(),handoffBox=await page.getByText('Responsibility handoff',{exact:true}).boundingBox();
    assert(handoffBox.y>=evidenceBox.y&&handoffBox.y+handoffBox.height<=evidenceBox.y+evidenceBox.height,'handoff entry starts within evidence viewport before raw');
    await page.getByText('Responsibility handoff',{exact:true}).click();
    await page.getByRole('button',{name:'Start successor with handoff',exact:true}).click();
    assert.equal(await page.locator('#developer-succession-form').isVisible(),true);
    assert.deepEqual(await page.evaluate(()=>NoeticSessions.state().selected),{ordinal:'0.0',instantiation:2,session:1,effort_root:'0.0'},'entry retains exact predecessor');
    await page.getByLabel('Responsibility entrusted to successor').fill('Fixture responsibility');await page.getByLabel('Context handoff / first instruction').fill('Fixture context');
    assert.equal(await page.getByRole('button',{name:'Entrust and start successor',exact:true}).isVisible(),true,'separate explicit commitment remains');
    await page.locator('#developer-succession-cancel').click();assert.equal(await page.locator('#developer-succession-form').isVisible(),false);
    assert.match(await page.locator('#developer-events').textContent(),/"sequence":\s*2637/,'complete raw source retained');
    await page.evaluate(()=>NoeticSessions.refresh());
    assert.equal(await page.getByText('Responsibility handoff',{exact:true}).evaluate(e=>e.parentElement.open),true,'poll retains action disclosure');
    assert.equal(calls.filter(c=>c.method==='POST').length,0,'entry and cancel do not commit');assert.deepEqual(errors,[]);
    console.log('PASS succession entry: outer summary first, handoff before2637raw rows, exact predecessor, explicit form/commit/cancel, no writes, poll disclosure');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
