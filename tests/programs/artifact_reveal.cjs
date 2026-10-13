const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../..'),env={...process.env};delete env.USER_PROVIDED_PASSWORD;
 const browser=await chromium.launch({headless:true,env,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});
 try{
  const page=await browser.newPage({viewport:{width:1024,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent(fs.readFileSync(path.join(root,'scripts/web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,''));
  await page.addStyleTag({path:path.join(root,'scripts/web/style.css')});await page.addStyleTag({path:path.join(root,'scripts/web/shell-library.css')});
  await page.addScriptTag({content:`
   const RUN='run1225adf95666409b94d915f863ee716c';
   const artifact={id:'artifact-4',type:'hypothesis',phase:'review',generation:1,produced_by:'worker',partial:true,content:{title:'Reveal hypothesis',body:'x'.repeat(4000)}};
   let allRuns=[{run_id:RUN,goal:'Blocked retained run',state:'blocked',correspondence:{effort_root:'0.1'}}];
   let selectedId=RUN;
   let selectedDetail={status:{run_id:RUN},controller:{artifacts:{'artifact-4':artifact}},artifacts:{}};
   const selection={scope:'effort',effort_root:'0.1'};const operationSelection=()=>selection;
   window.switchViewCalls=[];window.switchView=view=>{switchViewCalls.push(view);document.getElementById('controller-view').hidden=view!=='controller';document.getElementById('evidence-drawer').open=true;};
   // renderArtifact stub reproduces the actual app.js renderArtifact provenance format verbatim
   // (scripts/web/app.js: artifact.id / type / producer / activation / phase / generation / visit)
   const renderArtifact=()=>{const a=selectedDetail?.controller?.artifacts[document.getElementById('artifact-select').value];if(!a)return;
    const text=(id,v)=>{document.getElementById(id).textContent=v;};
    text('artifact-standing',a.partial?'Partial / not accepted or effective':'Retained');
    text('artifact-provenance',a.id+' / '+a.type+' / producer '+(a.produced_by||'external')+' / activation '+(a.activation_id||'none')+' / phase '+(a.phase||'none')+' / generation '+(a.generation??'n/a')+' / visit '+(a.visit??'n/a'));
    text('artifact-content',JSON.stringify(a.content,null,2));};
   document.getElementById('artifact-select').addEventListener('change',renderArtifact);
   for(const opt of [['artifact-4','artifact-4 / hypothesis'],['artifact-1','artifact-1 / plan']])document.getElementById('artifact-select').append(new Option(opt[1],opt[0]));
   const mounted=new Set(),handlers=new Map();let currentRoute='artifacts';
   window.NoeticUI={element:(tag,cls,value)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(value!==undefined)e.textContent=value;return e;},
    button:(value,fn,cls)=>{const b=document.createElement('button');b.type='button';b.textContent=value;if(cls)b.className=cls;b.addEventListener('click',fn);return b;},
    badge:value=>Object.assign(document.createElement('span'),{textContent:value}),heading:()=>{},
    mount:(id,host)=>{const e=document.getElementById(id);mounted.add(e);host.append(e);e.hidden=false;},
    register:(route,fn)=>handlers.set(route,fn),snapshot:()=>({sessions:[]}),route:()=>currentRoute,
    navigate:route=>{if(route!==currentRoute){for(const e of mounted){document.getElementById('legacy-storage').append(e);e.hidden=true;}mounted.clear();document.getElementById('shell-content').replaceChildren();}currentRoute=route;NoeticUI.refresh();},
    refresh:()=>{const host=document.getElementById('shell-content');host.dataset.route=currentRoute;if(handlers.has(currentRoute))handlers.get(currentRoute)({host,route:currentRoute});}};
   document.getElementById('evidence-drawer').open=true;
   document.getElementById('selected-run').hidden=false;
   document.getElementById('private-workspace').hidden=false;document.getElementById('workspace-page').hidden=false;
   document.getElementById('effort-operation-controls').hidden=false;document.getElementById('shell-content').hidden=false;
   const spacer=document.createElement('div');spacer.style.height='2958px';
   document.getElementById('artifact-count').closest('.section-heading').before(spacer);`});
  await page.addScriptTag({path:path.join(root,'scripts/web/shell-library.js')});await page.evaluate(()=>NoeticUI.refresh());

  const raf=()=>page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  const visible=sel=>page.locator(sel).evaluate(e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,width:r.width,height:r.height,viewport:innerHeight,inFlow:!!e.offsetParent&&getComputedStyle(e).visibility!=='hidden'};});
  // typed artifact row is present with its qualifier and semantic identity
  await page.waitForFunction(()=>document.querySelector('.lib-run-row'));
  assert.match(await page.locator('.lib-run-row').first().textContent(),/artifact-4/);
  assert.match(await page.locator('.lib-run-row').first().textContent(),/Partial/);

  // explicit typed-artifact row command reveals selector region, qualifier and content start
  await page.locator('.lib-run-row').first().click();
  await page.waitForFunction(()=>document.getElementById('artifact-content').textContent.length>0);
  assert.equal(await page.evaluate(()=>document.getElementById('artifact-select').value),'artifact-4','selected artifact ID identifiable');
  assert.match(await page.locator('#artifact-standing').textContent(),/Partial/);
  assert.match(await page.locator('#artifact-provenance').textContent(),/artifact-4 \/ hypothesis \/ producer worker/,'provenance in actual app.js renderArtifact format');
  assert.match(await page.locator('#artifact-content').textContent(),/Reveal hypothesis/,'content unchanged and rendered');
  await raf();
  const select=await visible('#artifact-select'),standing=await visible('#artifact-standing'),content=await visible('#artifact-content');
  assert.ok(select.width>0&&select.height>0&&select.inFlow,'artifact select has nonzero visible box');
  assert.ok(select.top>=0&&select.top<select.viewport,'artifact select visibly inspectable');
  assert.ok(standing.height>0&&standing.inFlow&&standing.top>=0&&standing.top<standing.viewport,'standing qualifier visibly inspectable');
  assert.ok(content.height>0&&content.inFlow&&content.top>=0&&content.top<content.viewport,'content start visibly inspectable in viewport');
  assert.equal(await page.evaluate(()=>document.activeElement.id),'artifact-content','focus lands on the artifact content');
  const before=await page.evaluate(()=>({x:scrollX,y:scrollY}));

  // repeat command re-reveals the currently selected artifact after scrolling away
  await page.evaluate(()=>scrollTo(0,0));
  await page.locator('.lib-run-row').first().click();
  await raf();
  const repeat=await visible('#artifact-content');
  assert.ok(repeat.top>=0&&repeat.top<repeat.viewport,'repeat command re-reveals selected artifact');

  // keyboard activation of the row reveals too
  await page.evaluate(()=>scrollTo(0,0));
  await page.locator('.lib-run-row').first().focus();await page.keyboard.press('Enter');
  await raf();
  const keyboard=await visible('#artifact-content');
  assert.ok(keyboard.top>=0&&keyboard.top<keyboard.viewport,'keyboard row activation reveals content');

  // passive refresh preserves reading position and focus
  await page.evaluate(()=>{document.dispatchEvent(new CustomEvent('noetic:runs'));document.dispatchEvent(new CustomEvent('noetic:run-detail'));});
  await raf();
  assert.deepEqual(await page.evaluate(()=>({x:scrollX,y:scrollY})),before,'passive refresh does not steal scroll');
  assert.equal(await page.evaluate(()=>document.activeElement.id),'artifact-content','passive refresh does not steal focus');

  // deferred reveal cannot affect a later route
  await page.evaluate(()=>scrollTo(0,0));
  await page.evaluate(()=>{document.querySelector('.lib-run-row').click();NoeticUI.navigate('usage');});
  await raf();
  assert.equal(await page.evaluate(()=>NoeticUI.route()),'usage');
  assert.notEqual(await page.evaluate(()=>document.activeElement.id),'artifact-content','deferred reveal does not cross routes');
  assert.deepEqual(await page.evaluate(()=>scrollY),0,'deferred reveal does not scroll a later route');

  // deferred reveal aborted when the effort scope changed between command and frame
  await page.evaluate(()=>{NoeticUI.navigate('artifacts');scrollTo(0,0);});
  await page.evaluate(()=>{document.querySelector('.lib-run-row').click();selection.effort_root='0.9-changed';});
  await raf();
  assert.deepEqual(await page.evaluate(()=>({x:scrollX,y:scrollY})),{x:0,y:0},'changed effort scope after command does not scroll');
  assert.notEqual(await page.evaluate(()=>document.activeElement.id),'artifact-content','changed effort scope after command does not steal focus');
  await page.evaluate(()=>{selection.effort_root='0.1';});

  // deferred reveal aborted when the selected run changed under the same artifact ID after the command
  await page.evaluate(()=>{scrollTo(0,0);document.querySelector('.lib-run-row').click();selectedDetail.status.run_id='run999changedunder-same-id';});
  await raf();
  assert.equal(await page.evaluate(()=>document.getElementById('artifact-select').value),'artifact-4','artifact ID recurs across runs; selector unchanged by guard');
  assert.deepEqual(await page.evaluate(()=>({x:scrollX,y:scrollY})),{x:0,y:0},'changed selected run with same artifact ID does not scroll');
  assert.notEqual(await page.evaluate(()=>document.activeElement.id),'artifact-content','changed selected run with same artifact ID does not steal focus');
  await page.evaluate(()=>{selectedDetail.status.run_id='run1225adf95666409b94d915f863ee716c';});

  // deferred reveal aborted when the artifact selection changed between command and frame
  await page.evaluate(()=>{scrollTo(0,0);document.querySelector('.lib-run-row').click();const s=document.getElementById('artifact-select');s.value='artifact-1';s.dispatchEvent(new Event('change',{bubbles:true}));});
  await raf();
  assert.deepEqual(await page.evaluate(()=>({x:scrollX,y:scrollY})),{x:0,y:0},'changed artifact selection after command does not scroll');
  assert.notEqual(await page.evaluate(()=>document.activeElement.id),'artifact-content','changed artifact selection after command does not steal focus');

  assert.deepEqual(errors,[]);
  console.log('PASS artifact row reveals select region, qualifier and content start, focus lands on content, repeat and keyboard reveal, passive refresh, later-route/effort-scope/selected-run/changed-selection guards');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
