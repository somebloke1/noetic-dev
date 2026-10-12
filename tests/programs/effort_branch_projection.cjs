const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const root = path.resolve(__dirname,'../..');
  const index = fs.readFileSync(path.join(root,'scripts/web/index.html'),'utf8');
  const developer = index.slice(index.lastIndexOf('<section',index.indexOf('id="developer-page"')), index.lastIndexOf('<div',index.indexOf('id="workspace-page"')));
  const html = `<!doctype html><html><head><meta charset="utf-8"></head><body><main id="host"></main><div id="private-workspace">${developer}</div>${['developer-project-open','developer-new','developer-global-root','developer-global-history','refresh'].map(id=>`<button id="${id}">${id}</button>`).join('')}${['developer-session-list','developer-agent-list','developer-legacy-list'].map(id=>`<div id="${id}"></div>`).join('')}</body></html>`;
  const positions=[{allocation:1,ordinal:'0',parent:null,status:'open'}];
  for(let i=0;i<200;i++){const ordinal=`0.${i}`;positions.push({allocation:positions.length+1,ordinal,parent:'0',effort:ordinal,intent:`Effort ${i}`,origin:'human',environment:{cwd:`/fixture/project-${i%10}`},environment_version:1,mandate:{mandate:{title:`Mandate ${i}`}}});for(let child=0;child<3;child++)positions.push({allocation:positions.length+1,ordinal:`${ordinal}.${child}`,parent:ordinal,effort:ordinal,origin:'human'});}

  const retained = {id:'retained',ordinal:'0.0',effort_root:'0.0',target:{ordinal:'0.0',instantiation:1,session:1},title:'Retained exact Alpha',workspace:'/fixture/alpha',model:'fixture/model',thinking:'high',status:'closed',is_current:false,broker_owned:false,domain_status:'superseded'};
  const current = {...retained,id:'current',target:{ordinal:'0.0',instantiation:2,session:1},title:'Current Alpha',status:'idle',is_current:true,broker_owned:true,domain_status:'open'};
  const beta = {...current,id:'beta',ordinal:'0.1',effort_root:'0.1',target:{ordinal:'0.1',instantiation:1,session:1},title:'Current Beta',workspace:'/fixture/beta'};
  const child={...retained,id:'child',ordinal:'0.0.0',target:{ordinal:'0.0.0',instantiation:1,session:1},title:'Evidence review · closed',domain_status:'closed'};
  const sessions=[retained,current,beta,child], calls=[];
  const env={...process.env};delete env.USER_PROVIDED_PASSWORD;
  const browser=await chromium.launch({headless:true,env,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
    page.on('pageerror',error=>{errors.push(error.message);console.error('fixture-pageerror',error.message);});
    await page.route('http://fixture/**',async route=>{
      const url=new URL(route.request().url()),body=route.request().postDataJSON();calls.push({path:url.pathname,query:Object.fromEntries(url.searchParams),body,method:route.request().method()});
      let result={};
      if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
      if(url.pathname==='/api/ordinals/0/branch'){const after=Number(url.searchParams.get('after')||0),limit=Number(url.searchParams.get('limit')||100),records=positions.filter(row=>row.allocation>after).slice(0,limit);result={records,next_after:records.at(-1)?.allocation||after};}
      else if(url.pathname.endsWith('/history'))result={records:url.pathname==='/api/ordinals/0/history' ? [{ordinal:'0.1',effort:'0.1',kind:'structured-controller-event',at:'fixture observation',data:{controller_event:{kind:'cognition.returned',data:{target:'P2'}}}}] : [],next_after:0};
      else if(url.pathname.startsWith('/api/ordinals/')){const position=positions.find(item=>item.ordinal===url.pathname.split('/')[3]);result={position:position.ordinal==='0.0.0' ? {...position,intent:'Alpha effort intent',mandate:{mandate:{title:'Evidence review',purpose:'Review evidence and preserve uncertainty'}}} : position};}
      else if(url.pathname==='/api/developer-sessions')result={sessions,projects_root:'/fixture'};
      else if(route.request().method()==='POST')result={stopped:true};
      else {const ordinal=url.pathname.split('/')[3],instantiation=Number(url.searchParams.get('instantiation'));const session=sessions.find(item=>item.ordinal===ordinal&&item.target.instantiation===instantiation)||sessions.find(item=>item.id===ordinal);result={session,events:url.searchParams.get('after')==='0' ? [{sequence:1,record:{type:'message_end',message:{role:'assistant',content:`Transcript for ${session.id}`,stopReason:'stop'}}}] : [],next_after:1};}
      await route.fulfill({contentType:'application/json',body:JSON.stringify(result)});
    });
    await page.goto('http://fixture/');
    await page.addScriptTag({content:`const $=id=>document.getElementById(id);let operatorToken='fixture',accessVersion=0,operationVersion=0,selectedId=null;const operationSelection=()=>({});const scopedURL=p=>p;const switchPage=()=>{};const fetchJSON=async(p,options)=>{const r=await fetch(p,options);return r.json();};const node=(tag,value,cls)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;if(cls)e.className=cls;return e;};const text=(id,value)=>$(id).textContent=value;const error=(id,value)=>{text(id,value);$(id).hidden=!value;};window.NoeticUI={element:(tag,cls,value)=>node(tag,value,cls),button:(value,action,cls)=>{const b=node('button',value,cls);b.type='button';b.onclick=action;return b;},mount:(id,host)=>{host.append($(id));$(id).hidden=false;},heading:options=>{window.lastHeading=options;},register:(route,handler)=>window.agenticsRender=handler};`});
    await page.addStyleTag({path:path.join(root,'scripts/web/style.css')});
    await page.addStyleTag({path:path.join(root,'scripts/web/shell-agentics.css')});
    await page.addScriptTag({path:path.join(root,'scripts/web/sessions.js')});
    await page.addScriptTag({path:path.join(root,'scripts/web/shell-agentics.js')});
    await page.waitForFunction(()=>NoeticSessions.state().sessions.length===4);
    assert.equal(await page.evaluate(()=>NoeticSessions.state().positions.length),801);
    assert.equal(calls.filter(call=>/^\/api\/ordinals\/0\.\d+$/.test(call.path)).length,0,'initial metadata projection has no per-root description fan-out');
    assert.equal(calls.filter(call=>call.path==='/api/ordinals/0/branch').length,10,'complete paginated branch remains reachable');
    positions.find(row=>row.ordinal==='0.199').environment={cwd:'/fixture/updated'};positions.find(row=>row.ordinal==='0.199').environment_version=2;
    calls.length=0;await page.evaluate(()=>NoeticSessions.refresh());
    assert.equal(calls.filter(call=>/^\/api\/ordinals\/0\.\d+$/.test(call.path)).length,0,'unchanged polling has no per-root descriptions');
    assert.equal(await page.evaluate(()=>NoeticSessions.state().positions.find(row=>row.ordinal==='0.199').environment_version),2,'new metadata remains visible without immutable cache');
    await page.evaluate(()=>NoeticSessions.open({ordinal:'0.0.0',effort_root:'0.0'}));
    assert.equal(calls.some(call=>call.path==='/api/ordinals/0.0.0'),true,'selected child still receives exact description');
    assert.equal(calls.some(call=>call.method!=='GET'),false);
    assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,checks:['801-position-addressability','200-root-no-fanout','paginated-metadata-freshness','selected-child-detail','read-only']}));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
