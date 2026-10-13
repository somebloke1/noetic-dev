const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{const root=path.resolve(__dirname,'../..'),source=fs.readFileSync(path.join(root,'scripts/web/app.js'),'utf8'),env={...process.env};delete env.USER_PROVIDED_PASSWORD;
const browser=await chromium.launch({headless:true,env,executablePath:process.env.NOETIC_TEST_CHROMIUM||undefined});try{const p=await browser.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.setContent(fs.readFileSync(path.join(root,'scripts/web/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,''));
await p.addScriptTag({content:`const $=id=>document.getElementById(id),text=(id,v)=>{$(id).textContent=v;},node=(tag,v)=>{const e=document.createElement(tag);if(v!==undefined)e.textContent=v;return e;};let startPending=false,draftVersion=0,operationMode='effort',effortEnvironment={cwd:'/w'},reviewedDefinition=null;`});
const grab=n=>{const s=source.indexOf(`function ${n}(`),e=source.indexOf('\n}\n',s);if(s<0||e<0)throw new Error('cannot extract '+n);return source.slice(s,e+3);};
await p.addScriptTag({content:[grab('reviewedSelectors'),grab('reviewedReady'),grab('reviewedOperation')].join('\n')});
// exact actual listener statements from initWorkbench
const line=s=>{const i=source.indexOf(s),e=source.indexOf('\n',i);if(i<0||e<0)throw new Error('cannot find '+s);return source.slice(i,e+1);};
await p.addScriptTag({content:line('$("reviewed-operation").addEventListener("change"')+line('for(const id of ["reviewed-parent-id"')+line('$("reviewed-store").addEventListener("change"')});
// operation choices include practical-question as the definition catalog supplies
await p.evaluate(()=>{const s=document.getElementById('reviewed-operation');s.append(new Option('Practical-question','practical-question'));s.value='practical-question';document.getElementById('reviewed-store').append(new Option('backing-1','backing-1'));});

// field displayed for practical-question; explicit editable concern; no checking refs; polarity preserved
reviewedOperationDisplayed:{await p.evaluate(()=>reviewedOperation());
  assert.equal(await p.evaluate(()=>document.getElementById('reviewed-practical-fields').hidden),false,'practical fields shown');
  const note=await p.locator('#reviewed-operation-note').textContent();
  assert.match(note,/what to investigate or do next/);assert.match(note,/yea, nay and perchance/);assert.match(note,/no decision, plan or act authority/);assert.match(note,/never contribution-validated/);
  assert.equal(await p.evaluate(()=>document.getElementById('reviewed-checking-fields').hidden),true,'no checking refs');
  assert.equal(await p.evaluate(()=>document.getElementById('reviewed-judgment-fields').hidden),true,'no judgment condition refs');}

// exact string IDs transported; valid draft enables start
await p.evaluate(()=>{document.getElementById('reviewed-judgment-ids').value='9007199254740993\n18446744073709551615';document.getElementById('reviewed-store').value='backing-1';reviewedOperation();});
const selected=await p.evaluate(()=>reviewedSelectors());
assert.deepEqual(selected,{judgment_ids:['9007199254740993','18446744073709551615']});
assert.equal(await p.evaluate(()=>JSON.stringify(reviewedSelectors())),'{"judgment_ids":["9007199254740993","18446744073709551615"]}','exact JSON strings');
assert.deepEqual(await p.evaluate(()=>reviewedSelectors().judgment_ids.map(v=>typeof v)),['string','string'],'never Number-rounded');
assert.equal(await p.evaluate(()=>document.getElementById('start-submit').disabled),false,'valid draft enables start');

// invalid drafts stay editable/repairable, start disabled, error explicit
for(const [value,label] of [['2\n1','unsorted'],['1\n1','duplicate'],['0','zero'],['01','leading zero'],['18446744073709551616','overflow'],['1.0','malformed'],['','empty']]){
  await p.evaluate(v=>{document.getElementById('reviewed-judgment-ids').value=v;reviewedOperation();},value);
  assert.equal(await p.evaluate(()=>reviewedReady()),false,label+' rejected');
  assert.equal(await p.evaluate(()=>document.getElementById('start-submit').disabled),true,label+' disables start');
  assert.equal(await p.evaluate(()=>document.getElementById('reviewed-judgment-ids').value),value,label+' draft stays editable');
  await assert.rejects(()=>p.evaluate(()=>reviewedSelectors(true)),/strictly increasing|positive decimal/,label+' explicit required error');
}

// backing change clears selected IDs (actual listener), draft repairable afterwards
await p.evaluate(()=>{document.getElementById('reviewed-judgment-ids').value='9007199254740993';document.getElementById('reviewed-store').dispatchEvent(new Event('change',{bubbles:true}));});
assert.equal(await p.evaluate(()=>document.getElementById('reviewed-judgment-ids').value),'','backing change clears selected Judgment IDs');

// question operation: no selectors, practical fields hidden
await p.evaluate(()=>{document.getElementById('reviewed-operation').value='question';document.getElementById('reviewed-operation').dispatchEvent(new Event('change',{bubbles:true}));});
assert.deepEqual(await p.evaluate(()=>reviewedSelectors()),{});
assert.equal(await p.evaluate(()=>document.getElementById('reviewed-practical-fields').hidden),true,'practical fields hidden for question');

// scope reset, reuse clearing and structured draft restoration hooks present in actual source
const scopeSlice=source.slice(source.indexOf('function changeOperationScope'),source.indexOf('window.NoeticEffort'));
assert.match(scopeSlice,/\$\("reviewed-judgment-ids"\)\.value=""/,'scope reset clears selected Judgment IDs');
const reuseSlice=source.slice(source.indexOf('async function reuseSetup'),source.indexOf('async function',source.indexOf('async function reuseSetup')+10));
assert.match(reuseSlice,/\$\("reviewed-judgment-ids"\)\.value=""/,'reuse clears selected Judgment IDs');
assert.match(source,/const structuredBindings = \[[^\]]*"reviewed-judgment-ids"/,'structured draft bindings retain the field');
assert.match(source,/for\(const id of \["reviewed-parent-id","reviewed-warrant-id","reviewed-condition-ids","reviewed-formulation-id","reviewed-checking-spec","reviewed-checking-context","reviewed-judgment-ids"\]\)\{\$\(id\)\.value=desired\[id\]/,'owned draft restores editable references');

assert.deepEqual(errors,[]);
console.log('PASS practical-question selectors: exact u64 strings, lifecycle clearing/restoration, invalid-draft states, polarity-preserving concern, no checking refs');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
