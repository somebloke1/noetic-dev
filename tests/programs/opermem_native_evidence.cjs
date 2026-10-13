const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{const root=path.resolve(__dirname,'../..'),source=fs.readFileSync(path.join(root,'scripts/web/app.js'),'utf8'),env={...process.env};delete env.USER_PROVIDED_PASSWORD;
const browser=await chromium.launch({headless:true,env,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});try{const p=await browser.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.setContent('<!doctype html><html><body><main></main></body></html>');
await p.evaluate(()=>{const ids=['run-id','run-goal','task-body','run-state','state-note','workspace','goal-ref','last-event','detail-observed','controller-pattern','controller-machine','controller-phase','controller-generation','controller-budgets','controller-actor','controller-source','cancel-note','telos-chain','telos-subgoal','telos-result','controller-phases','driver-data','event-count','journal-source','timeline','report-select','log-select','controller-summary','legacy-execution','workspace-result','workspace-apply','advance-one','advance-all','pause-pattern','cancel-pattern','phases-tab','compare-tab','controller-tab','session-select','primary-agent','primary-model','primary-progress','driver-activity','steering-note','primary-attention','reviewed-progress','reviewed-dispositions','reviewed-report','reviewed-review-text','reviewed-recover-contribution','reviewed-recover-correlation','reviewed-evidence-content','summary-selection','summary-generate','empty-state','selected-run','session-tab'];
for(const id of ids){const e=document.createElement(id==='session-select'?'select':id==='controller-phases'||id==='timeline'||id==='reviewed-dispositions'||id==='reviewed-report'||id==='reviewed-recover-contribution'||id==='reviewed-recover-correlation'||id==='reviewed-evidence-content'?'div':'span');e.id=id;document.body.append(e);}
document.getElementById('report-select').value='work.md';});
await p.addScriptTag({content:`const $=id=>document.getElementById(id);let timelineSignature="",selectedId='run1',operationVersion=1;const operationSelection=()=>({effort_root:'0.1'});`});
const grab=n=>{const s=source.indexOf(`function ${n}(`),e=source.indexOf('\n}\n',s);if(s<0||e<0)throw new Error('cannot extract '+n);return source.slice(s,e+3);};
await p.addScriptTag({content:[grab('text'),grab('node'),grab('date'),grab('setOptions'),grab('renderRawArtifact'),grab('renderReviewedDetail')].join('\n')});
await p.addScriptTag({content:`
window.renderEvidence=()=>{};window.renderSessionAgents=()=>{};
window.renderEventWindow=(id,events,createRow)=>{document.getElementById(id).replaceChildren(...events.map(createRow));};
const BIG='10307616488058435121',WARRANT='8478839392319035579';
const texts={
 'opermem-link.json':'{"native_link":{"condition":'+BIG+',"warrant":'+WARRANT+',"max":18446744073709551615,"quoted":"'+BIG+'"}}',
 'opermem-scope.json':'{"scope":{"effort_root":"0.1","condition":"condition'+BIG+'"}}',
 'opermem-receipt.json':'{"receipt":{"condition":"condition'+BIG+'","warrant":"warrant'+WARRANT+'","accepted":true}}',
 'opermem-pending.json':''};
const artifacts={};for(const k of Object.keys(texts))artifacts[k]={source_path:'/runs/r/'+k,text:texts[k],truncated:false};
window.detail={status:{run_id:'run1',goal:'G',state:'complete'},backend:'opermem-reviewed',
 events:[{sequence:1,kind:'started',occurred_at:'2026-10-12T00:00:00Z'}],artifacts,
 correspondence:{effort_root:'0.1',discipline_id:'d',execution_id:'e',native_ref:'nr-7',target:{instantiation:'i1',session:'s1'},native_link:{parent_id:10307616488058436000,warrant_id:8478839392319035000,context:{condition:10307616488058436000}}},
 preparation:{workspace:'/w',purpose_ref:null,operation:'question',run_dir:'/runs/r'},
 population:[{ordinal:'1',role:'worker',status:'done'}],
 application:{driver:{launch_id:'L1',status:'done',driver_owned:true},activity:'a',reason:'r',unavailable_controls:'u',
  native:{receipt:{receipt:{condition:'condition'+BIG,rounded:10307616488058436000}},receipt_retained:true,pending:null,disposition:'receipt-retained',telos:null,telos_error:null,semantic_authority:'Opermem',current_standing:'unobserved'},
  configuration:{client:'pi',model:null,qa_model:null},review:{outcome:null},actions:{recover_contribution:true,recover_correlation:true}}};`});
const D=await p.evaluate(()=>structuredClone(window.detail));
const rawPre=name=>p.evaluate(n=>{const item=[...document.getElementById('reviewed-evidence-content').children].find(x=>x.dataset.key===n);const pre=item?.querySelector('pre');return pre?pre.textContent:null;},name);
const rawNote=name=>p.evaluate(n=>{const item=[...document.getElementById('reviewed-evidence-content').children].find(x=>x.dataset.key===n);const note=item?.querySelector('.raw-artifact > p');return note?note.textContent:null;},name);

// 1. full render: exact raw text in separate pre elements
await p.evaluate(()=>renderReviewedDetail(detail));
for(const name of ['opermem-link.json','opermem-scope.json','opermem-receipt.json','opermem-pending.json']){
  assert.equal(await rawPre(name),D.artifacts[name].text,`${name} pre equals supplied raw text byte-for-byte`);
  assert.match(await rawNote(name),new RegExp(name.replace('.','\\.')+'.*source_path|/runs/r/'+name.replace('.','\\.')),'full source_path shown');
  assert.match(await rawNote(name),/historical evidence only/,'historical-only label');
}
// 2. exact big literals in raw rows; rounded projections never in raw rows
const linkPre=await rawPre('opermem-link.json');
assert.match(linkPre,/"condition":10307616488058435121/);assert.match(linkPre,/"warrant":8478839392319035579/);
assert.match(linkPre,/18446744073709551615/);assert.match(linkPre,/"10307616488058435121"/,'quoted numeric string preserved');
const rawAll=await p.evaluate(()=>[...document.querySelectorAll('#reviewed-evidence-content details pre')].map(x=>x.textContent).join('\n'));
assert.ok(!rawAll.includes('10307616488058436000'),'rounded projection never presented as original');
// structured driver summary points to whole raw row instead of embedding rounded receipt
const driver=await p.locator('#driver-data').textContent();
assert.match(driver,/Inspect the opermem-receipt\.json raw row/);
assert.ok(!driver.includes('10307616488058436000'),'driver-data omits embedded rounded native packet');
// native_link summary points to raw row; participants/target/native_ref summaries intact
const corrRow=await p.evaluate(()=>{const item=[...document.getElementById('reviewed-evidence-content').children].find(x=>x.dataset.key==='Actual participants and correspondence summary');return item.querySelector('pre').textContent;});
assert.match(corrRow,/Inspect the whole opermem-link\.json raw row/);
assert.ok(!corrRow.includes('10307616488058436000'),'correspondence summary omits rounded native packet');
assert.match(corrRow,/nr-7/);assert.match(corrRow,/i1/);assert.match(corrRow,/s1/,'native_ref and target summaries intact');
// dispositions and actor summaries preserved
const disp=await p.locator('#reviewed-dispositions').textContent();
assert.match(disp,/External review/);assert.match(disp,/Native: receipt-retained/);assert.match(disp,/Telos:/);
assert.match(await p.evaluate(()=>[...document.getElementById('session-select').options].map(o=>o.label).join('|')),/^1 · native target unobserved · worker$/);
assert.match(await rawNote('opermem-pending.json'),/file exists and is empty/);
// 3. parsed event rows labelled browser projections
assert.match(await p.locator('#timeline').textContent(),/Browser projection of a parsed journal event row/);
// 4. repeated update: no duplicates, text still exact
await p.evaluate(()=>renderReviewedDetail(detail));
assert.equal(await p.evaluate(()=>document.getElementById('reviewed-evidence-content').children.length),8,'repeated update keeps exactly raw+structured rows');
assert.equal(await rawPre('opermem-link.json'),D.artifacts['opermem-link.json'].text);
// 5. absent artifact: explicit absent state, no fallback to rounded native objects
await p.evaluate(()=>{const d=structuredClone(detail);delete d.artifacts['opermem-link.json'];window.changed=d;renderReviewedDetail(d);});
assert.match(await rawNote('opermem-link.json'),/No retained raw text for opermem-link\.json observed/);
assert.equal(await rawPre('opermem-link.json'),null,'no fabricated pre for absent artifact');
const changedRaw=await p.evaluate(()=>[...document.querySelectorAll('#reviewed-evidence-content details')].filter(x=>x.dataset.key==='opermem-link.json')[0].textContent);
assert.ok(!changedRaw.includes('10307616488058436000'),'absent artifact never falls back to rounded native_link object');
// 6. truncated and error states distinguished
await p.evaluate(()=>{const d=structuredClone(detail);d.artifacts['opermem-scope.json']={source_path:'/runs/r/opermem-scope.json',text:'{"scope":{',truncated:true};d.artifacts['opermem-receipt.json']={source_path:'/runs/r/opermem-receipt.json',error:'EACCES'};renderReviewedDetail(d);});
assert.match(await rawNote('opermem-scope.json'),/truncated to the first 1048576 bytes; full original remains in the local file/);
assert.match(await rawNote('opermem-receipt.json'),/read error: EACCES/);
assert.equal(await rawPre('opermem-scope.json'),'{"scope":{','mid-JSON truncation preserved verbatim');
await p.evaluate(()=>{const d=structuredClone(detail);d.artifacts['opermem-link.json']={source_path:'/runs/r/opermem-link.json'};renderReviewedDetail(d);});
assert.match(await rawNote('opermem-link.json'),/carries no raw text/);
assert.equal(await rawPre('opermem-link.json'),null);
// restore full originals and confirm exact bytes return
await p.evaluate(()=>renderReviewedDetail(detail));
assert.equal(await rawPre('opermem-link.json'),D.artifacts['opermem-link.json'].text);
assert.deepEqual(errors,[],'no page errors');
console.log('PASS exact raw artifact text, big-literal fidelity, state/source labels, repeated update, rounded-projection separation, preserved actors/dispositions');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
