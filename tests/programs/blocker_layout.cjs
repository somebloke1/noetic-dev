const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../..'),source=fs.readFileSync(path.join(root,'scripts/web/shell.js'),'utf8'),env={...process.env};delete env.USER_PROVIDED_PASSWORD;
 const browser=await chromium.launch({headless:true,env,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});
 try{
  const page=await browser.newPage({viewport:{width:1024,height:768}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent('<div id="host" style="width:319px"></div>');await page.addStyleTag({path:path.join(root,'scripts/web/style.css')});
  await page.addScriptTag({content:`const el=(tag,cls,value)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(value!==undefined)e.textContent=value;return e;},button=(value,fn,cls)=>{const e=el('button',cls,value);e.type='button';e.onclick=fn;return e;},action=(value,fn)=>button(value,fn,''),badge=(value,tone)=>el('span','badge '+tone,value),card=(kicker,title)=>{const e=el('section','panel');e.append(el('h2','',title));return e;},navigate=route=>window.currentRoute=route,selectRun=id=>window.inspected=id;window.NoeticRuns={state:()=>({selection:{scope:'effort',effort_root:'0.1'},status:'observed',observedAt:'fixture',warnings:[],runs:[{run_id:'1225adf95666409b94d915f863ee716c',state:'blocked',goal:'Keep the exact recorded blocker and its owning human effort clearly readable before choosing the next action.',correspondence:{effort_root:'0.1'}}]})};`});
  await page.addScriptTag({content:source.slice(source.indexOf('const runObservation='),source.indexOf('function effortTabs()'))});
  await page.evaluate(()=>document.getElementById('host').append(executionBlockers(3,'0.1')));
  for(const [width,height,cardWidth] of [[1024,768,319],[1440,1000,333]]){
   await page.setViewportSize({width,height});await page.evaluate(w=>document.getElementById('host').style.width=w+'px',cardWidth);
   const geometry=await page.locator('[data-run-id]').evaluate(e=>{const row=e.getBoundingClientRect(),title=e.querySelector('strong').getBoundingClientRect(),identity=e.querySelector('small').getBoundingClientRect();return {row:{width:row.width,height:row.height,right:row.right},title:{width:title.width,top:title.top,bottom:title.bottom},identity:{top:identity.top,right:identity.right}};});
   assert.ok(geometry.title.width>100,'blocker title has a readable column at '+width);assert.ok(geometry.identity.top>=geometry.title.bottom,'full qualified identity is on a separate row');assert.ok(geometry.identity.right<=geometry.row.right,'full identity stays inside its row');
  }
  await page.locator('[data-run-id]').click();assert.equal(await page.evaluate(()=>inspected),'1225adf95666409b94d915f863ee716c');assert.equal(await page.evaluate(()=>currentRoute),'executions');assert.match(await page.locator('[data-run-id] small').textContent(),/1225adf95666409b94d915f863ee716c.*Effort 0\.1/);
  assert.deepEqual(errors,[]);console.log('PASS blocker title width/full identity separate row at1024/1440; exact target/action/source retained');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
