const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{const root=path.resolve(__dirname,'../..'),source=fs.readFileSync(path.join(root,'scripts/web/app.js'),'utf8'),env={...process.env};delete env.USER_PROVIDED_PASSWORD;
const browser=await chromium.launch({headless:true,env,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});try{const p=await browser.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.setContent(fs.readFileSync(path.join(root,'scripts/web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,''));
await p.addScriptTag({content:`const $=id=>document.getElementById(id),text=(id,v)=>{$(id).textContent=v;},node=(tag,v)=>{const e=document.createElement(tag);if(v!==undefined)e.textContent=v;return e;};let startPending=false,draftVersion=0,operationMode='effort',effortEnvironment={cwd:'/w'},reviewedDefinition=null;`});
// whole actual interval reviewedSelectors→renderReviewedSources (not per-function heuristics)
const interval=source.slice(source.indexOf('function reviewedSelectors('),source.indexOf('function renderReviewedSources'));
assert.match(interval,/deliberation/,'extracted interval contains deliberation selectors');
await p.addScriptTag({content:interval});
// exact actual listener statements from initWorkbench
const line=s=>{const i=source.indexOf(s),e=source.indexOf('\n',i);if(i<0||e<0)throw new Error('cannot find '+s);return source.slice(i,e+1);};
await p.addScriptTag({content:line('$("reviewed-operation").addEventListener("change"')+line('for(const id of ["reviewed-parent-id"')+line('$("reviewed-store").addEventListener("change"')});
await p.evaluate(()=>{const s=document.getElementById('reviewed-operation');s.append(new Option('Practical-question','practical-question'));s.append(new Option('Practical-inquiry','practical-inquiry'));s.append(new Option('Deliberation','deliberation'));s.value='deliberation';document.getElementById('reviewed-store').append(new Option('backing-1','backing-1'));});


await p.evaluate(()=>reviewedOperation());
assert.equal(await p.evaluate(()=>$('reviewed-practical-question-fields').hidden),false);
assert.equal(await p.evaluate(()=>$('reviewed-options-fields').hidden),false);
assert.equal(await p.evaluate(()=>$('reviewed-practical-fields').hidden),true);
assert.equal(await p.evaluate(()=>$('reviewed-checking-fields').hidden),true);
const note=await p.locator('#reviewed-operation-note').textContent();
assert.match(note,/entire|complete/i);assert.match(note,/Evaluation/);assert.match(note,/unverified/i);assert.match(note,/winner|decision/i);
await p.evaluate(({question,optionText})=>{$('reviewed-practical-question-id').value=question;$('reviewed-option-ids').value=optionText;$('reviewed-store').value='backing-1';reviewedOperation();},{question:'9007199254740993',optionText:'9007199254740994\n18446744073709551615'});
const exact={practical_question_id:'9007199254740993',option_ids:['9007199254740994','18446744073709551615']};
assert.deepEqual(await p.evaluate(()=>reviewedSelectors()),exact);
assert.equal(await p.evaluate(()=>JSON.stringify(reviewedSelectors())),JSON.stringify(exact));
assert.equal(await p.evaluate(()=>$('start-submit').disabled),false);
const cases=[
  {
    "name": "missing both",
    "question": "",
    "optionText": "",
    "valid": false
  },
  {
    "name": "missing Question",
    "question": "",
    "optionText": "9007199254740994\n18446744073709551615",
    "valid": false
  },
  {
    "name": "missing Option set",
    "question": "9007199254740993",
    "optionText": "",
    "valid": false
  },
  {
    "name": "one Option",
    "question": "9007199254740993",
    "optionText": "9007199254740994",
    "valid": false
  },
  {
    "name": "zero Question",
    "question": "0",
    "optionText": "9007199254740994\n18446744073709551615",
    "valid": false
  },
  {
    "name": "leading-zero Option",
    "question": "9007199254740993",
    "optionText": "01\n18446744073709551615",
    "valid": false
  },
  {
    "name": "overflow Option",
    "question": "9007199254740993",
    "optionText": "9007199254740994\n18446744073709551616",
    "valid": false
  },
  {
    "name": "duplicate Options",
    "question": "9007199254740993",
    "optionText": "9007199254740994\n9007199254740994",
    "valid": false
  },
  {
    "name": "descending Options",
    "question": "9007199254740993",
    "optionText": "18446744073709551615\n9007199254740994",
    "valid": false
  },
  {
    "name": "malformed Option",
    "question": "9007199254740993",
    "optionText": "1.0\n18446744073709551615",
    "valid": false
  },
  {
    "name": "exact high Options",
    "question": "9007199254740993",
    "optionText": "9007199254740994\n18446744073709551615",
    "valid": true
  }
];
for(const row of cases){
  await p.evaluate(({question,optionText})=>{$('reviewed-practical-question-id').value=question;$('reviewed-option-ids').value=optionText;reviewedOperation();},row);
  assert.equal(await p.evaluate(()=>reviewedReady()),row.valid,row.name);
  assert.equal(await p.evaluate(()=>$('start-submit').disabled),!row.valid,row.name);
  assert.equal(await p.evaluate(()=>$('reviewed-practical-question-id').value),row.question,row.name);
  assert.equal(await p.evaluate(()=>$('reviewed-option-ids').value),row.optionText,row.name);
  if(!row.valid)await assert.rejects(()=>p.evaluate(()=>reviewedSelectors(true)),/Option|Question|complete/i,row.name);
}
await p.evaluate(()=>$('reviewed-store').dispatchEvent(new Event('change',{bubbles:true})));
assert.equal(await p.evaluate(()=>$('reviewed-practical-question-id').value),'');
assert.equal(await p.evaluate(()=>$('reviewed-option-ids').value),'');
await p.evaluate(()=>{$('reviewed-operation').value='practical-inquiry';$('reviewed-operation').dispatchEvent(new Event('change',{bubbles:true}));$('reviewed-practical-question-id').value='9007199254740993';});
assert.equal(await p.evaluate(()=>$('reviewed-practical-question-fields').hidden),false);
assert.equal(await p.evaluate(()=>$('reviewed-options-fields').hidden),true);
assert.deepEqual(await p.evaluate(()=>reviewedSelectors()),{practical_question_id:'9007199254740993'});
await p.evaluate(()=>{$('reviewed-operation').value='practical-question';$('reviewed-operation').dispatchEvent(new Event('change',{bubbles:true}));$('reviewed-judgment-ids').value='9007199254740993\n18446744073709551615';});
assert.equal(await p.evaluate(()=>$('reviewed-practical-fields').hidden),false);
assert.equal(await p.evaluate(()=>$('reviewed-options-fields').hidden),true);
assert.deepEqual(await p.evaluate(()=>reviewedSelectors()),{judgment_ids:['9007199254740993','18446744073709551615']});
// actual owned draft capture/leave/other-effort/restore lifecycle via structuredDrafts
await p.addScriptTag({content:`let savedUI={},initialForms={},accessVersion=1,operatorToken='fixture',draftEffort='A',developerSubjectVersion=0,reviewedSources=[],reviewedLaunch=null;
function operationKey(){return 'effort:'+draftEffort;}function operationSelection(){return {kind:'effort',effort_root:draftEffort};}
function scopedURL(x){return x;}function scopeControls(){}function persistUI(){}function updateComposer(){}function isReviewed(){return true;}function renderReviewedSources(){}
function loadReviewedSetup(){structuredDrafts.restoreChoice('reviewed-store',['backing-1']);structuredDrafts.restoreChoice('reviewed-operation',['question','practical-question','practical-inquiry','deliberation']);}function loadPurposes(){}
function operationValid(){return true;}async function loadReviewedLaunches(){}async function refresh(){}async function fetchJSON(url,options){if(!options)return {namespace_registered:true,namespace_id:'fixture-ns'};return url==='/api/disciplines'?{discipline:{id:'fixture-discipline'}}:{launch_id:'fixture-launch',status:'queued'};}`});
await p.addScriptTag({content:source.slice(source.indexOf('const structuredDraftFields ='),source.indexOf('let purposeCreatePending='))});
await p.evaluate(async()=>{structuredDrafts.init();await structuredDrafts.enter();});
await p.evaluate(()=>{$('reviewed-operation').value='deliberation';$('reviewed-store').value='backing-1';$('reviewed-practical-question-id').value='9007199254740993';$('reviewed-option-ids').value='9007199254740994\n18446744073709551615';$('start-task').value='Evaluate complete courses toward adequate observation; static preparation cannot fulfill Checking';structuredDrafts.capture();});
const draft=await p.evaluate(()=>savedUI.structuredDrafts[JSON.stringify(['fixture-ns','A'])]);
assert.equal(draft.bindings['reviewed-practical-question-id'],'9007199254740993','owned draft captures exact ID string');
assert.equal(draft.bindings['reviewed-option-ids'],'9007199254740994\n18446744073709551615','owned draft captures complete Option text');
await p.evaluate(()=>structuredDrafts.leave());
assert.equal(await p.evaluate(()=>$('reviewed-practical-question-id').value),'','actual leave clears ID');
assert.equal(await p.evaluate(()=>$('reviewed-option-ids').value),'','actual leave clears ID Options');
await p.evaluate(async()=>{draftEffort='B';await structuredDrafts.enter();});
assert.equal(await p.evaluate(()=>$('reviewed-practical-question-id').value),'','other effort has no inherited ID');
assert.equal(await p.evaluate(()=>$('reviewed-option-ids').value),'','other effort has no inherited ID Options');
await p.evaluate(async()=>{structuredDrafts.leave();draftEffort='A';await structuredDrafts.enter();});
assert.equal(await p.evaluate(()=>$('reviewed-practical-question-id').value),'9007199254740993','owned draft restores editable ID');
assert.equal(await p.evaluate(()=>$('reviewed-option-ids').value),'9007199254740994\n18446744073709551615','owned draft restores editable ID Options');
assert.equal(await p.evaluate(()=>$('start-task').value),'Evaluate complete courses toward adequate observation; static preparation cannot fulfill Checking');

// Actual emitted complete-set payload, explicit task, no inherited selectors.
await p.addScriptTag({content:`window.calls=[];window.fetchJSON=async(url,options)=>{if(!options)return {namespace_registered:true,namespace_id:'fixture-ns'};calls.push({url,body:JSON.parse(options.body)});return url==='/api/disciplines'?{discipline:{id:'fixture-discipline'}}:{launch_id:'fixture-launch',status:'queued'};};`});
await p.addScriptTag({content:source.slice(source.indexOf('async function startReviewed'),source.indexOf('function renderRawArtifact'))});
await p.evaluate(async()=>{if(typeof crypto.randomUUID!=='function')Object.defineProperty(crypto,'randomUUID',{value:()=>'review-probe-command'});$('reviewed-operation').value='deliberation';$('reviewed-operation').dispatchEvent(new Event('change',{bubbles:true}));$('reviewed-practical-question-id').value='9007199254740993';$('reviewed-option-ids').value='9007199254740994\n18446744073709551615';$('reviewed-parent-id').value='999';$('reviewed-warrant-id').value='888';$('reviewed-judgment-ids').value='12\n13';$('reviewed-checking-spec').value='/stale/spec';$('reviewed-checking-context').value='/stale/context';$('start-task').value='Evaluate complete courses toward adequate observation; static preparation cannot fulfill Checking';$('start-client').value='pi';$('start-model').value='';$('start-qa-model').value='';$('start-timeout').value='900';$('start-purpose').value='';await startReviewed({scopeVersion:1,scopeKey:operationKey(),draft:draftVersion,subject:developerSubjectVersion,selection:operationSelection(),environment:{cwd:'/w'}});});
const launch=await p.evaluate(()=>calls.find(x=>x.url==='/api/application/start').body);
assert.deepEqual(launch.selectors,{practical_question_id:'9007199254740993',option_ids:['9007199254740994','18446744073709551615']});
assert.equal(typeof launch.selectors.practical_question_id,'string');
assert.deepEqual(launch.selectors.option_ids.map(value=>typeof value),['string','string']);
assert.equal(launch.task,'Evaluate complete courses toward adequate observation; static preparation cannot fulfill Checking');
assert.equal(launch.operation,'deliberation');
for(const key of ['parent_id','warrant_id','condition_ids','judgment_ids','checking_spec','checking_context','option_id'])assert.equal(key in launch,false,'no transported '+key);
assert.equal(await p.evaluate(()=>calls[0].body.selectors),undefined,'instance creation carries no selectors');

// scope reset and reuse clearing present in actual source (runtime leave/clear exercised above)
const scopeSlice=source.slice(source.indexOf('function changeOperationScope'),source.indexOf('window.NoeticEffort'));
assert.match(scopeSlice,/\$\("reviewed-practical-question-id"\)\.value=""/,'scope reset clears selected PracticalQuestion ID');
const reuseSlice=source.slice(source.indexOf('async function reuseSetup'),source.indexOf('async function',source.indexOf('async function reuseSetup')+10));
assert.match(reuseSlice,/\$\("reviewed-practical-question-id"\)\.value=""/,'reuse clears selected PracticalQuestion ID');
assert.match(source,/const structuredBindings = \[[^\]]*"reviewed-practical-question-id"/,'structured draft bindings retain the field');
assert.match(source,/for\(const id of \["reviewed-parent-id","reviewed-warrant-id","reviewed-condition-ids","reviewed-formulation-id","reviewed-checking-spec","reviewed-checking-context","reviewed-judgment-ids","reviewed-practical-question-id","reviewed-option-ids"\]\)\{\$\(id\)\.value=desired\[id\]/,'owned draft restores editable references');


assert.match(scopeSlice,/\$\("reviewed-option-ids"\)\.value=""/,'scope reset clears complete Option set');
assert.match(reuseSlice,/\$\("reviewed-option-ids"\)\.value=""/,'reuse clears complete Option set');
assert.match(source,/const structuredBindings = \[[^\]]*"reviewed-option-ids"/,'owned binding includes complete Option set');

assert.deepEqual(errors,[]);
console.log('PASS deliberation: exact complete-set u64 strings, named cases, owned lifecycle and actual payload; C3/C4 intact');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
