const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const root = path.resolve(__dirname, '../..');
  const browser = await chromium.launch({headless:true, executablePath:process.env.NOETIC_TEST_CHROMIUM || undefined});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const html = fs.readFileSync(path.join(root,'scripts/web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'');
    await page.setContent(html);
    const definitions = ['cognition','development'].map(pattern => ({pattern,definition_ref:{id:`noetic:${pattern}`,version:'test-source-hash',pattern_version:1},definition:JSON.parse(fs.readFileSync(path.join(root,`scripts/patterns/${pattern}.json`),'utf8'))}));
    await page.evaluate(definitions => {
      const host = document.getElementById('shell-content'), parked = new Set();
      document.getElementById('private-workspace').hidden = false;
      document.getElementById('legacy-storage').hidden = true;
      window.fixture = {route:'',sessions:[],selection:{scope:'application'},requests:[],definitions,instances:[],pending:null};
      window.operationSelection = () => fixture.selection;
      window.scopedURL = (path, selection) => `${path}?${new URLSearchParams(selection).toString()}`;
      window.configuration = {profiles:[{id:'actual',label:'Exact fixture selection',client:'pi',model:'fixture/<img src=x onerror=alert(1)>'}],local:{embedding_model:'fixture/embed',dimensions:1024},limits:{timeout_seconds:[1,7200]},role_defaults:{producer:'selected model'}};
      window.allRuns = [];
      window.selectedDetail = null;
      window.fetchJSON = async (url, options) => {
        fixture.requests.push({url,method:options?.method || 'GET'});
        if (fixture.pending) return new Promise(resolve => {fixture.resolve=resolve;});
        return {definitions:fixture.definitions,instances:fixture.instances,next_after:null};
      };
      window.loadPurposes = () => {fixture.requests.push({url:'/api/goals',method:'GET'});};
      window.switchPage = () => {};
      window.NoeticUI = {
        handlers:{},register(route,handler){this.handlers[route]=handler;},
        heading(data){document.getElementById('shell-page-title').textContent=data.title;},
        element(tag,cls='',text){const node=document.createElement(tag);node.className=cls;if(text!==undefined)node.textContent=text;return node;},
        button(text,action,cls=''){const node=this.element('button',cls,text);node.type='button';node.addEventListener('click',action);return node;},
        icon(){return this.element('span','','◇');},badge(text){return this.element('span','badge',text);},
        mount(id,parent){const node=document.getElementById(id);if(node){parent.append(node);node.hidden=false;parked.add(node);}return node;},
        snapshot(){return {sessions:fixture.sessions};},
        refresh(){return this.handlers[fixture.route]?.({host,route:fixture.route,snapshot:this.snapshot()});},
        navigate(route){if(route!==fixture.route){for(const node of parked){document.getElementById('legacy-storage').append(node);node.hidden=true;}parked.clear();host.replaceChildren();}fixture.route=route;host.dataset.route=route;return this.refresh();}
      };
    }, definitions);
    await page.addScriptTag({path:path.join(root,'scripts/web/shell-library.js')});
    await page.addStyleTag({path:path.join(root,'scripts/web/shell-library.css')});
    assert.equal(await page.evaluate(()=>Object.keys(NoeticUI.handlers).length),12);
    await page.evaluate(()=>NoeticUI.navigate('disciplines'));
    assert.equal(await page.locator('#shell-content #effort-operation-controls').count(),1);
    assert.equal(await page.locator('.lib-definition-card').count(),2);
    assert.equal(await page.locator('.lib-definition-card').first().locator('h3').textContent(),'Cognition');
    await page.locator('.lib-tabs button').nth(1).click();
    assert.equal(await page.locator('#shell-content #effort-operation-controls').count(),1);
    assert.match(await page.locator('#shell-content').textContent(),/No discipline instances/);
    await page.evaluate(()=>NoeticUI.navigate('roles'));
    assert.equal(await page.locator('.lib-template').count(),8);
    assert.match(await page.locator('.lib-contract').first().textContent(),/Attend to supplied and observed data/);
    await page.evaluate(()=>NoeticUI.navigate('prompts'));
    assert.match(await page.locator('#shell-content').textContent(),/standalone editable template catalog is not exposed/);
    await page.evaluate(()=>NoeticUI.navigate('models'));
    assert.match(await page.locator('#shell-content').textContent(),/fixture\/<img/);
    assert.equal(await page.locator('#shell-content img').count(),0);
    await page.evaluate(()=>NoeticUI.navigate('memory'));
    await page.locator('#memory-query').fill('Unsent recall draft');
    await page.evaluate(()=>NoeticUI.refresh());
    assert.equal(await page.locator('#memory-query').inputValue(),'Unsent recall draft');
    await page.evaluate(()=>NoeticUI.navigate('runtime'));
    await page.evaluate(()=>{fixture.sessions=[{id:'exact-one',target:{ordinal:'0.1',instantiation:2,session:3},title:'Exact target',model:'fixture/model',status:'running'}];NoeticUI.refresh();});
    assert.equal(await page.locator('#diagnostics-page').count(),1);
    assert.match(await page.locator('#shell-content').textContent(),/0\.1 · context 2\/3/);
    await page.evaluate(()=>{fixture.selection={effort_root:'0.1'};fixture.sessions[0].effort_root='0.1';fixture.sessions.push({id:'other-effort',effort_root:'0.2',title:'Different effort session'});NoeticUI.refresh();});
    assert.equal(await page.locator('.lib-runtime-row').count(),1);
    assert.equal(await page.locator('#shell-content #effort-operation-controls').count(),1);
    assert.doesNotMatch(await page.locator('#shell-content').textContent(),/Different effort session/);
    await page.evaluate(()=>{fixture.selection={scope:'application'};});
    await page.evaluate(()=>NoeticUI.navigate('usage'));
    assert.equal(await page.getByText('Unknown',{exact:true}).count(),4);
    assert.equal(await page.locator('#shell-content #effort-operation-controls').count(),1);
    await page.evaluate(()=>{fixture.selection={effort_root:'0.1'};NoeticUI.refresh();});
    assert.equal(await page.locator('.lib-runtime-row').count(),1);
    assert.doesNotMatch(await page.locator('#shell-content').textContent(),/other-effort/);
    await page.evaluate(()=>{fixture.sessions.push({id:'scoped-two',effort_root:'0.1',target:{ordinal:'0.1.0',instantiation:1,session:2}});NoeticUI.refresh();});
    assert.equal(await page.locator('.lib-runtime-row').count(),2);
    assert.equal(await page.locator('#shell-content #effort-operation-controls').count(),1);
    await page.evaluate(()=>{fixture.selection={scope:'application'};});
    await page.evaluate(()=>NoeticUI.navigate('runtime'));
    assert.equal(await page.locator('#shell-content #diagnostics-page').count(),1);
    await page.evaluate(()=>NoeticUI.navigate('new-work'));
    await page.locator('#start-task').fill('Preserved work draft');
    await page.evaluate(()=>NoeticUI.navigate('configuration'));
    await page.evaluate(()=>NoeticUI.navigate('new-work'));
    assert.equal(await page.locator('#start-task').inputValue(),'Preserved work draft');
    await page.evaluate(()=>{fixture.selection={effort_root:'0.2'};fixture.pending=true;NoeticUI.navigate('disciplines');});
    await page.waitForFunction(()=>Boolean(fixture.resolve));
    await page.evaluate(()=>NoeticUI.navigate('usage'));
    await page.evaluate(()=>{fixture.resolve({definitions:fixture.definitions,instances:[],next_after:null});fixture.pending=null;});
    await page.waitForFunction(()=>document.getElementById('shell-page-title').textContent==='Usage metrics');
    assert.equal(await page.locator('.lib-definition-card').count(),0);
    await page.evaluate(()=>NoeticUI.navigate('purposes'));
    await page.evaluate(()=>NoeticUI.navigate('artifacts'));
    await page.evaluate(()=>NoeticUI.navigate('executions'));
    assert.equal(await page.locator('#workspace-apply').count(),1);
    assert.ok(await page.locator('.lib-execution-detail').evaluate(node=>node.classList.contains('lib-preserved')));
    assert.equal(await page.locator('#reuse-setup').evaluate(node=>getComputedStyle(node).borderRadius),'6px');
    assert.equal(await page.locator('.run-caption').evaluate(node=>getComputedStyle(node).display),'flex');
    const requests = await page.evaluate(()=>fixture.requests);
    assert.ok(requests.some(request=>request.url.includes('effort_root=0.2')));
    assert.ok(requests.every(request=>request.method==='GET'));
    assert.deepEqual(errors,[]);
    console.log('PASS real-browser library contracts, scoped/stale reads, exact target rendering, draft/DOM preservation, honest accounting, and no passive model calls');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
