const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const root = path.resolve(__dirname,'../..');
  const index = fs.readFileSync(path.join(root,'scripts/web/index.html'),'utf8');
  const html=index.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'');
  const positions = [{ordinal:'0',parent:null,status:'open'}, {ordinal:'0.0',parent:'0',effort:'0.0',intent:'Alpha',current_instantiation:2,origin:'human',environment:{cwd:'/fixture/alpha'}}, {ordinal:'0.0.0',parent:'0.0',effort:'0.0',origin:'human',current_instantiation:1}, {ordinal:'0.1',parent:'0',effort:'0.1',intent:'Beta',current_instantiation:1,origin:'human',environment:{cwd:'/fixture/beta'}}];
  const retained = {id:'retained',ordinal:'0.0',effort_root:'0.0',target:{ordinal:'0.0',instantiation:1,session:1},title:'Retained exact Alpha',workspace:'/fixture/alpha',model:'fixture/model',thinking:'high',status:'closed',is_current:false,broker_owned:false,domain_status:'superseded'};
  const current = {...retained,id:'current',target:{ordinal:'0.0',instantiation:2,session:1},title:'Current Alpha',status:'idle',is_current:true,broker_owned:true,domain_status:'open'};
  const beta = {...current,id:'beta',ordinal:'0.1',effort_root:'0.1',target:{ordinal:'0.1',instantiation:1,session:1},title:'Current Beta',workspace:'/fixture/beta'};
  const child={...retained,id:'child',ordinal:'0.0.0',target:{ordinal:'0.0.0',instantiation:1,session:1},title:'Evidence review · closed',domain_status:'closed'};
  const originalRoot={...retained,id:'native-root',ordinal:'0',original_ordinal:'0',effort_root:null,target:null,identity_origin:'legacy-unadopted',parent_id:null,domain_status:null};
  const original={...originalRoot,id:'native-original',ordinal:'0.1',original_ordinal:'0.1',parent_id:'native-root',title:'Original native child'};
  const sessions=[retained,current,beta,child,originalRoot,original], calls=[];
  const env={...process.env};delete env.USER_PROVIDED_PASSWORD;
  const browser=await chromium.launch({headless:true,env,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
    page.on('pageerror',error=>{errors.push(error.message);console.error('fixture-pageerror',error.message);});
    await page.route('http://fixture/**',async route=>{
      const url=new URL(route.request().url()),body=route.request().postDataJSON();calls.push({path:url.pathname,query:Object.fromEntries(url.searchParams),body,method:route.request().method()});
      let result={};
      if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
      if(url.pathname==='/api/ordinals/0/branch')result={records:positions,next_after:0};
      else if(url.pathname.endsWith('/history'))result={records:url.pathname==='/api/ordinals/0/history' ? [{ordinal:'0.1',effort:'0.1',kind:'structured-controller-event',at:'fixture observation',data:{controller_event:{kind:'cognition.returned',data:{target:'P2'}}}}] : [],next_after:0};
      else if(url.pathname.startsWith('/api/ordinals/')){const position=positions.find(item=>item.ordinal===url.pathname.split('/')[3]);result={position:position.ordinal==='0.0.0' ? {...position,intent:'Alpha effort intent',mandate:{mandate:{title:'Evidence review',purpose:'Review evidence and preserve uncertainty'}}} : position};}
      else if(url.pathname==='/api/preview-info')result={};
      else if(url.pathname==='/api/developer-sessions')result={sessions,projects_root:'/fixture'};
      else if(route.request().method()==='POST')result={stopped:true};
      else {const ordinal=url.pathname.split('/')[3],instantiation=Number(url.searchParams.get('instantiation'));const session=sessions.find(item=>item.ordinal===ordinal&&item.target?.instantiation===instantiation)||sessions.find(item=>item.id===ordinal);result={session,events:url.searchParams.get('after')==='0' ? Array.from({length:40},(_,i)=>({sequence:i+1,record:{type:'message_end',message:{role:i%2?'assistant':'user',content:'Transcript message '+i+' '+('Detailed source evidence and a concrete next instruction. '.repeat(18)),stopReason:'stop'}}})) : [],next_after:40};}
      await route.fulfill({contentType:'application/json',body:JSON.stringify(result)});
    });
    await page.goto('http://fixture/');
    await page.addScriptTag({content:`const $=id=>document.getElementById(id);let operatorToken='fixture',accessVersion=0,operationVersion=0,selectedId=null;const operationSelection=()=>({});const scopedURL=p=>p;const switchPage=()=>{};const fetchJSON=async(p,options)=>{const r=await fetch(p,options);return r.json();};const node=(tag,value,cls)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;if(cls)e.className=cls;return e;};const text=(id,value)=>$(id).textContent=value;const error=(id,value)=>{text(id,value);$(id).hidden=!value;};let allRuns=[];$('private-workspace').hidden=false;`});
    await page.addStyleTag({path:path.join(root,'scripts/web/style.css')});
    await page.addStyleTag({path:path.join(root,'scripts/web/shell-agentics.css')});
    await page.addScriptTag({path:path.join(root,'scripts/web/shell.js')});
    await page.addScriptTag({path:path.join(root,'scripts/web/sessions.js')});
    await page.addScriptTag({path:path.join(root,'scripts/web/shell-agentics.js')});
    await page.waitForFunction(()=>NoeticSessions.state().sessions.length===6);
    await page.evaluate(()=>{NoeticUI.navigate('agentics');});
    await page.evaluate(()=>NoeticSessions.open({ordinal:'0.0',instantiation:2,session:1,effort_root:'0.0'}));
    const gap=()=>page.locator('#developer-transcript').evaluate(e=>e.scrollHeight-e.scrollTop-e.clientHeight);
    await page.locator('#developer-transcript').evaluate(e=>e.scrollTop=e.scrollHeight);await page.waitForTimeout(50);
    assert.ok(await gap()<2,'initial exact transcript follows latest');
    await page.setViewportSize({width:1280,height:720});await page.waitForTimeout(80);
    assert.ok(await gap()<2,'latest-following transcript remains at bottom across window reflow');
    await page.evaluate(()=>NoeticSessions.refresh());assert.ok(await gap()<2,'unchanged poll retains latest after reflow');
    await page.locator('#developer-transcript').evaluate(e=>e.scrollTop=100);await page.waitForTimeout(50);
    await page.setViewportSize({width:1440,height:1000});await page.waitForTimeout(80);
    assert.ok(await gap()>400,'earlier reader is not forced tolatest on reflow');
    await page.evaluate(()=>NoeticSessions.refresh());assert.ok(await gap()>400,'poll preserves earlier reader');
    await page.getByRole('separator',{name:'Resize agentics tree and conversation'}).focus();await page.keyboard.press('ArrowRight');await page.waitForTimeout(80);assert.ok(await gap()>400,'earlier reader retained across pane resize');
    await page.locator('#developer-transcript').evaluate(e=>e.scrollTop=e.scrollHeight);await page.waitForTimeout(50);
    await page.getByRole('separator',{name:'Resize agentics tree and conversation'}).focus();await page.keyboard.press('ArrowRight');await page.waitForTimeout(80);
    assert.ok(await gap()<2,'following latest retained across pane resize');
    assert.deepEqual(await page.evaluate(()=>NoeticSessions.state().selected),{ordinal:'0.0',instantiation:2,session:1,effort_root:'0.0'});
    assert.equal(calls.some(call=>call.method!=='GET'),false);
    assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,checks:['latest-window-reflow','latest-pane-reflow','earlier-reader-retention','unchanged-poll-continuity','exact-target-unchanged']}));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
