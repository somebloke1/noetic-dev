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
  const current = {...retained,id:'current',target:{ordinal:'0.0',instantiation:2,session:1},title:'Current Alpha '+ 'long-native-title'.repeat(20),status:'idle',is_current:true,broker_owned:true,domain_status:'open'};
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
      else {const ordinal=url.pathname.split('/')[3],instantiation=Number(url.searchParams.get('instantiation'));const session=sessions.find(item=>item.ordinal===ordinal&&item.target?.instantiation===instantiation)||sessions.find(item=>item.id===ordinal);result={session,events:url.searchParams.get('after')==='0' ? [{sequence:1,record:{type:'message_end',message:{role:'user',content:'Keep  whitespace\nsecond line'}}},{sequence:2,record:{type:'message_end',message:{role:'assistant',content:[{type:'text',text:'Answer\n```js\n  exact(1);\n```'},{type:'image',mimeType:'image/png'},{type:'toolCall',id:'t',name:'bash',arguments:{command:'echo exact'}}],stopReason:'toolUse'}}},{sequence:3,record:{type:'tool_execution_end',toolCallId:'t',toolName:'bash',result:{content:[{type:'text',text:'FULL '+ 'x'.repeat(100000)}]}}},{sequence:4,record:{type:'message_start',message:{role:'assistant'}}},{sequence:5,record:{type:'message_update',assistantMessageEvent:{type:'text_delta',delta:'unfinished'}}},{sequence:6,record:{type:'message_end',message:{role:'assistant',content:[{type:'image',mimeType:'image/png'}],stopReason:'stop'}}}] : [],next_after:40};}
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
    await page.setViewportSize({width:1024,height:768});await page.locator('.agentics-canvas [data-view=sessions]').click();
    const box=await page.locator('.agentics-viewport').evaluate(e=>({width:e.clientWidth,scroll:e.scrollWidth}));assert.ok(box.scroll<=box.width+1,'session list fits actual narrow pane '+JSON.stringify(box));
    for(const row of await page.locator('.agentics-session-row').all()){const bounds=await row.boundingBox(),pane=await page.locator('.agentics-viewport').boundingBox();assert.ok(bounds.x>=pane.x&&bounds.x+bounds.width<=pane.x+pane.width+1);}
    assert.match(await page.locator('.agentics-session-row').filter({hasText:'Current Alpha'}).textContent(),/long-native-title/);await page.locator('.agentics-session-row[data-session-id=current]').click();assert.deepEqual(await page.evaluate(()=>NoeticSessions.state().selected),{ordinal:'0.0',instantiation:2,session:1,effort_root:'0.0'});
    await page.setViewportSize({width:1440,height:1000});const wider=await page.locator('.agentics-viewport').evaluate(e=>({width:e.clientWidth,scroll:e.scrollWidth}));assert.ok(wider.scroll<=wider.width+1);assert.deepEqual(errors,[]);assert.equal(calls.some(call=>call.method!=='GET'),false);console.log('PASS native session rows wrap within1024/1440 pane while full titles/ordinals/exact targets remain');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
