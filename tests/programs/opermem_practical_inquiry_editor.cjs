const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{const root=path.resolve(__dirname,'../..'),source=fs.readFileSync(path.join(root,'scripts/web/app.js'),'utf8'),env={...process.env};delete env.USER_PROVIDED_PASSWORD;
const browser=await chromium.launch({headless:true,env,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});try{const p=await browser.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.setContent(fs.readFileSync(path.join(root,'scripts/web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,''));
await p.addScriptTag({content:`const $=id=>document.getElementById(id),text=(id,v)=>{$(id).textContent=v;},node=(tag,v)=>{const e=document.createElement(tag);if(v!==undefined)e.textContent=v;return e;};let startPending=false,draftVersion=0,operationMode='effort',effortEnvironment={cwd:'/w'},reviewedDefinition=null;`});
// whole actual interval reviewedSelectors→renderReviewedSources (not per-function heuristics)
const interval=source.slice(source.indexOf('function reviewedSelectors('),source.indexOf('function renderReviewedSources'));
assert.match(interval,/practical-inquiry/,'extracted interval contains practical-inquiry selectors');
await p.addScriptTag({content:interval});
// exact actual listener statements from initWorkbench
const line=s=>{const i=source.indexOf(s),e=source.indexOf('\n',i);if(i<0||e<0)throw new Error('cannot find '+s);return source.slice(i,e+1);};
await p.addScriptTag({content:line('$("reviewed-operation").addEventListener("change"')+line('for(const id of ["reviewed-parent-id"')+line('$("reviewed-store").addEventListener("change"')});
await p.evaluate(()=>{const s=document.getElementById('reviewed-operation');s.append(new Option('Practical-question','practical-question'));s.append(new Option('Practical-inquiry','practical-inquiry'));s.value='practical-inquiry';document.getElementById('reviewed-store').append(new Option('backing-1','backing-1'));});

// field visible only for practical-inquiry; C3 practical-question/Checking/Judgment fields stay hidden; explicit typed-domain note
await p.evaluate(()=>reviewedOperation());
assert.equal(await p.evaluate(()=>document.getElementById('reviewed-practical-question-fields').hidden),false,'practical-inquiry field shown');
assert.equal(await p.evaluate(()=>document.getElementById('reviewed-practical-fields').hidden),true,'C3 Judgment-ID field hidden');
assert.equal(await p.evaluate(()=>document.getElementById('reviewed-checking-fields').hidden),true,'no checking refs');
const note=await p.locator('#reviewed-operation-note').textContent();
assert.match(note,/selected active PracticalQuestion/);assert.match(note,/one candidate course/);assert.match(note,/fresh inquiry/);assert.match(note,/no decision, plan or act authority/);

// exact high u64 scalar stays a JSON string; valid draft enables start
await p.evaluate(()=>{document.getElementById('reviewed-practical-question-id').value='9007199254740993';document.getElementById('reviewed-store').value='backing-1';reviewedOperation();});
assert.equal(await p.evaluate(()=>JSON.stringify(reviewedSelectors())),'{"practical_question_id":"9007199254740993"}','exact scalar string');
assert.equal(await p.evaluate(()=>typeof reviewedSelectors().practical_question_id),'string','never Number-rounded');
assert.equal(await p.evaluate(()=>document.getElementById('start-submit').disabled),false,'valid draft enables start');
await p.evaluate(()=>{document.getElementById('reviewed-practical-question-id').value='18446744073709551615';reviewedOperation();});
assert.equal(await p.evaluate(()=>JSON.stringify(reviewedSelectors())),'{"practical_question_id":"18446744073709551615"}','max u64 exact');

// invalid/missing drafts stay repairable, start disabled, required error explicit
for(const [value,label] of [['','missing'],['0','zero'],['01','leading zero'],['18446744073709551616','overflow'],['1.0','malformed'],['true','malformed'],['9007199254740993 ','trailing handled by trim then valid']]){
  await p.evaluate(v=>{document.getElementById('reviewed-practical-question-id').value=v;reviewedOperation();},value);
  const valid=label.includes('trailing');
  assert.equal(await p.evaluate(()=>reviewedReady()),valid,label);
  assert.equal(await p.evaluate(()=>document.getElementById('start-submit').disabled),!valid,label+' start state');
  assert.equal(await p.evaluate(()=>document.getElementById('reviewed-practical-question-id').value),value,label+' draft stays editable');
  if(!valid)await assert.rejects(()=>p.evaluate(()=>reviewedSelectors(true)),/positive decimal active PracticalQuestion/,label+' explicit required error');
}

// backing change clears the ID (actual listener)
await p.evaluate(()=>{document.getElementById('reviewed-practical-question-id').value='9007199254740993';document.getElementById('reviewed-store').dispatchEvent(new Event('change',{bubbles:true}));});
assert.equal(await p.evaluate(()=>document.getElementById('reviewed-practical-question-id').value),'','backing change clears selected PracticalQuestion ID');

// C3 practical-question editor unchanged
await p.evaluate(()=>{document.getElementById('reviewed-operation').value='practical-question';document.getElementById('reviewed-operation').dispatchEvent(new Event('change',{bubbles:true}));});
assert.equal(await p.evaluate(()=>document.getElementById('reviewed-practical-question-fields').hidden),true,'new field hidden for practical-question');
assert.equal(await p.evaluate(()=>document.getElementById('reviewed-practical-fields').hidden),false,'C3 field intact for practical-question');
await p.evaluate(()=>{document.getElementById('reviewed-judgment-ids').value='9007199254740993\n18446744073709551615';});
assert.deepEqual(await p.evaluate(()=>reviewedSelectors()),{judgment_ids:['9007199254740993','18446744073709551615']},'C3 selectors intact');

// actual owned draft capture/leave/other-effort/restore lifecycle via structuredDrafts
await p.addScriptTag({content:`let savedUI={},initialForms={},accessVersion=1,operatorToken='fixture',draftEffort='A',developerSubjectVersion=0,reviewedSources=[],reviewedLaunch=null;
function operationKey(){return 'effort:'+draftEffort;}function operationSelection(){return {kind:'effort',effort_root:draftEffort};}
function scopedURL(x){return x;}function scopeControls(){}function persistUI(){}function updateComposer(){}function isReviewed(){return true;}function renderReviewedSources(){}
function loadReviewedSetup(){structuredDrafts.restoreChoice('reviewed-store',['backing-1']);structuredDrafts.restoreChoice('reviewed-operation',['question','practical-question','practical-inquiry']);}function loadPurposes(){}
function operationValid(){return true;}async function loadReviewedLaunches(){}async function refresh(){}async function fetchJSON(url,options){if(!options)return {namespace_registered:true,namespace_id:'fixture-ns'};return url==='/api/disciplines'?{discipline:{id:'fixture-discipline'}}:{launch_id:'fixture-launch',status:'queued'};}`});
await p.addScriptTag({content:source.slice(source.indexOf('const structuredDraftFields ='),source.indexOf('let purposeCreatePending='))});
await p.evaluate(async()=>{structuredDrafts.init();await structuredDrafts.enter();});
await p.evaluate(()=>{$('reviewed-operation').value='practical-inquiry';$('reviewed-store').value='backing-1';$('reviewed-practical-question-id').value='9007199254740993';$('start-task').value='Propose one candidate course toward adequate observation';structuredDrafts.capture();});
const draft=await p.evaluate(()=>savedUI.structuredDrafts[JSON.stringify(['fixture-ns','A'])]);
assert.equal(draft.bindings['reviewed-practical-question-id'],'9007199254740993','owned draft captures exact ID string');
await p.evaluate(()=>structuredDrafts.leave());
assert.equal(await p.evaluate(()=>$('reviewed-practical-question-id').value),'','actual leave clears ID');
await p.evaluate(async()=>{draftEffort='B';await structuredDrafts.enter();});
assert.equal(await p.evaluate(()=>$('reviewed-practical-question-id').value),'','other effort has no inherited ID');
await p.evaluate(async()=>{structuredDrafts.leave();draftEffort='A';await structuredDrafts.enter();});
assert.equal(await p.evaluate(()=>$('reviewed-practical-question-id').value),'9007199254740993','owned draft restores editable ID');
assert.equal(await p.evaluate(()=>$('start-task').value),'Propose one candidate course toward adequate observation');

// actual emitted start payload: scalar string ID, explicit task, no inherited selectors or Checking paths
await p.addScriptTag({content:`window.calls=[];window.fetchJSON=async(url,options)=>{if(!options)return {namespace_registered:true,namespace_id:'fixture-ns'};calls.push({url,body:JSON.parse(options.body)});return url==='/api/disciplines'?{discipline:{id:'fixture-discipline'}}:{launch_id:'fixture-launch',status:'queued'};};`});
await p.addScriptTag({content:source.slice(source.indexOf('async function startReviewed'),source.indexOf('function renderRawArtifact'))});
await p.evaluate(async()=>{if(typeof crypto.randomUUID!=='function')Object.defineProperty(crypto,'randomUUID',{value:()=>'review-probe-command'});$('reviewed-operation').value='practical-inquiry';$('reviewed-operation').dispatchEvent(new Event('change',{bubbles:true}));$('reviewed-practical-question-id').value='9007199254740993';$('reviewed-parent-id').value='999';$('reviewed-warrant-id').value='888';$('reviewed-judgment-ids').value='12\n13';$('reviewed-checking-spec').value='/stale/spec';$('reviewed-checking-context').value='/stale/context';$('start-task').value='Propose one candidate course toward adequate observation';$('start-client').value='pi';$('start-model').value='';$('start-qa-model').value='';$('start-timeout').value='900';$('start-purpose').value='';await startReviewed({scopeVersion:1,scopeKey:operationKey(),draft:draftVersion,subject:developerSubjectVersion,selection:operationSelection(),environment:{cwd:'/w'}});});
const launch=await p.evaluate(()=>calls.find(x=>x.url==='/api/application/start').body);
assert.deepEqual(launch.selectors,{practical_question_id:'9007199254740993'});
assert.equal(typeof launch.selectors.practical_question_id,'string');
assert.equal(launch.task,'Propose one candidate course toward adequate observation');
assert.equal(launch.operation,'practical-inquiry');
for(const key of ['parent_id','warrant_id','condition_ids','judgment_ids','checking_spec','checking_context','option_id'])assert.equal(key in launch,false,'no transported '+key);
assert.equal(await p.evaluate(()=>calls[0].body.selectors),undefined,'instance creation carries no selectors');

// scope reset and reuse clearing present in actual source (runtime leave/clear exercised above)
const scopeSlice=source.slice(source.indexOf('function changeOperationScope'),source.indexOf('window.NoeticEffort'));
assert.match(scopeSlice,/\$\("reviewed-practical-question-id"\)\.value=""/,'scope reset clears selected PracticalQuestion ID');
const reuseSlice=source.slice(source.indexOf('async function reuseSetup'),source.indexOf('async function',source.indexOf('async function reuseSetup')+10));
assert.match(reuseSlice,/\$\("reviewed-practical-question-id"\)\.value=""/,'reuse clears selected PracticalQuestion ID');
assert.match(source,/const structuredBindings = \[[^\]]*"reviewed-practical-question-id"/,'structured draft bindings retain the field');
assert.match(source,/for\(const id of \["reviewed-parent-id","reviewed-warrant-id","reviewed-condition-ids","reviewed-formulation-id","reviewed-checking-spec","reviewed-checking-context","reviewed-judgment-ids","reviewed-practical-question-id"\]\)\{\$\(id\)\.value=desired\[id\]/,'owned draft restores editable references');

assert.deepEqual(errors,[]);
console.log('PASS practical-inquiry: exact scalar u64 string, field visibility, invalid-draft states, backing/leave/effort/restore lifecycle, actual start payload with no inherited selectors, C3 editors intact');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
