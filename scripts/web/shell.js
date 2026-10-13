"use strict";
(() => {
// Derived from the captured published C icon component.
const REFERENCE_ICONS = {
  "activity": "<path d=\"M4 12h3l2.2-6 4.1 12 2.2-6H20\"></path>",
  "archive": "<path d=\"M4 7h16v13H4zM3 4h18v3H3z\"></path><path d=\"M9 11h6\"></path>",
  "branch": "<circle cx=\"6\" cy=\"5\" r=\"2\"></circle><circle cx=\"18\" cy=\"7\" r=\"2\"></circle><circle cx=\"18\" cy=\"18\" r=\"2\"></circle><path d=\"M6 7v7a4 4 0 0 0 4 4h6M8 5h5a5 5 0 0 1 5 5v6\"></path>",
  "chevron": "<path d=\"m9 18 6-6-6-6\"></path>",
  "clock": "<circle cx=\"12\" cy=\"12\" r=\"9\"></circle><path d=\"M12 7v5l3 2\"></path>",
  "command": "<path d=\"M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z\"></path>",
  "cube": "<path d=\"m12 3 8 4.5v9L12 21l-8-4.5v-9z\"></path><path d=\"m4 7.5 8 4.5 8-4.5M12 12v9\"></path>",
  "database": "<ellipse cx=\"12\" cy=\"5\" rx=\"8\" ry=\"3\"></ellipse><path d=\"M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7\"></path>",
  "file": "<path d=\"M6 3h8l4 4v14H6z\"></path><path d=\"M14 3v5h4M9 13h6M9 17h5\"></path>",
  "grid": "<rect x=\"3\" y=\"3\" width=\"7\" height=\"7\" rx=\"1\"></rect><rect x=\"14\" y=\"3\" width=\"7\" height=\"7\" rx=\"1\"></rect><rect x=\"3\" y=\"14\" width=\"7\" height=\"7\" rx=\"1\"></rect><rect x=\"14\" y=\"14\" width=\"7\" height=\"7\" rx=\"1\"></rect>",
  "layers": "<path d=\"m12 3 9 5-9 5-9-5z\"></path><path d=\"m3 12 9 5 9-5M3 16l9 5 9-5\"></path>",
  "more": "<circle cx=\"5\" cy=\"12\" r=\"1\" fill=\"currentColor\"></circle><circle cx=\"12\" cy=\"12\" r=\"1\" fill=\"currentColor\"></circle><circle cx=\"19\" cy=\"12\" r=\"1\" fill=\"currentColor\"></circle>",
  "pause": "<path d=\"M8 6v12M16 6v12\"></path>",
  "play": "<path d=\"m8 5 11 7-11 7z\"></path>",
  "plus": "<path d=\"M12 5v14M5 12h14\"></path>",
  "search": "<circle cx=\"11\" cy=\"11\" r=\"7\"></circle><path d=\"m20 20-4-4\"></path>",
  "settings": "<circle cx=\"12\" cy=\"12\" r=\"3\"></circle><path d=\"M19.4 15a1.8 1.8 0 0 0 .4 2l.1.1-2.8 2.8-.1-.1a1.8 1.8 0 0 0-2-.4 1.8 1.8 0 0 0-1.1 1.7V21h-4v-.1A1.8 1.8 0 0 0 8.8 19a1.8 1.8 0 0 0-2 .4l-.1.1-2.8-2.8.1-.1a1.8 1.8 0 0 0 .4-2A1.8 1.8 0 0 0 2.7 13H2V9h.7a1.8 1.8 0 0 0 1.7-1.1 1.8 1.8 0 0 0-.4-2l-.1-.1L6.7 3l.1.1a1.8 1.8 0 0 0 2 .4A1.8 1.8 0 0 0 10 1.8V1h4v.8a1.8 1.8 0 0 0 1.1 1.7 1.8 1.8 0 0 0 2-.4l.1-.1L20 5.8l-.1.1a1.8 1.8 0 0 0-.4 2A1.8 1.8 0 0 0 21.2 9h.8v4h-.8a1.8 1.8 0 0 0-1.8 2Z\"></path>",
  "spark": "<path d=\"m12 2 1.4 5.1L18 9l-4.6 1.9L12 16l-1.4-5.1L6 9l4.6-1.9zM5 16l.7 2.3L8 19l-2.3.7L5 22l-.7-2.3L2 19l2.3-.7z\"></path>",
  "terminal": "<rect x=\"3\" y=\"4\" width=\"18\" height=\"16\" rx=\"2\"></rect><path d=\"m7 9 3 3-3 3M13 16h4\"></path>",
  "users": "<circle cx=\"9\" cy=\"8\" r=\"3\"></circle><circle cx=\"17\" cy=\"9\" r=\"2.5\"></circle><path d=\"M3 20c.4-4 2.3-6 6-6s5.6 2 6 6M15 15c3.6-.5 5.6 1.2 6 4\"></path>",
  "warning": "<path d=\"M12 3 2.8 20h18.4z\"></path><path d=\"M12 9v5M12 17.5v.1\"></path>"
};
function referenceIcon(name, size = 18) {
  return `<svg aria-hidden="true" class="icon" fill="none" height="${size}" viewBox="0 0 24 24" width="${size}">${REFERENCE_ICONS[name] || ""}</svg>`;
}

const routes = new Map(), mounted = new Set();
const el = (tag, className = '', value) => {const e=document.createElement(tag);e.className=className;if(value!==undefined)e.textContent=value;return e;};
const button = (value, action, className='') => {const b=el('button',className,value);b.type='button';if(action)b.addEventListener('click',action);return b;};
const icon = (name, size=18) => {const holder=document.createElement('template');holder.innerHTML=referenceIcon(name,size);return holder.content.firstElementChild;};
const badge = (value, tone='neutral') => el('span',`status-badge ${tone}`,value);
let view = {route:'workspaces',subview:''}, snapshotData = {}, projectFilter = null, suppressPage = false, generation=0;
let portfolioQuery='',portfolioLimit=12,commandMode='';
let effortDraft=null,effortDraftNotice='',effortSync=null,effortInputs=null;
let placeHistory=[],placeReady=false,restoring=false,frameOwner=null;
try {view={...view,...JSON.parse(sessionStorage.getItem('noetic-shell-view')||'{}')};}catch(_){}
const nav = [
 ['workspaces','Workspaces','grid'],['agentics','Agentics','branch'],null,
 ['runtime','Native agent runtime','terminal'],['models','Model registry','cube'],null,
 ['disciplines','Disciplines','layers'],['prompts','Prompt templates','file'],['roles','Roles','users'],null,
 ['memory','Typed memory','database'],['usage','Usage metrics','activity'],['artifacts','Artifacts','archive']
];
const sidebarRoutes=new Set(['workspaces','agentics','history','attention','closed','new-effort','executions','new-work','purposes']);
const labels=Object.fromEntries(nav.filter(Boolean).map(x=>[x[0],x[1]]));Object.assign(labels,{configuration:'Configuration',executions:'Executions','new-work':'Entrust work',purposes:'Purpose & limits','new-effort':'New effort',history:'Recent activity',attention:'Attention',closed:'Closed conversations'});
const snapshot=()=>({...snapshotData,projectFilter});
const roots=()=> (snapshotData.positions||[]).filter(p=>p.effort===p.ordinal).sort((a,b)=>a.ordinal.localeCompare(b.ordinal,'en',{numeric:true}));
const currentEffort=()=>roots().find(p=>p.ordinal===snapshotData.effort);
function effortCatalogue(){const all=roots(),matching=all.filter(p=>(!projectFilter||p.environment?.cwd===projectFilter)&&(!portfolioQuery||`${p.ordinal} ${p.intent||''} ${p.environment?.cwd||''}`.toLowerCase().includes(portfolioQuery))),shown=matching.slice(0,portfolioLimit),selected=currentEffort();return{all,matching,shown,pin:selected&&!shown.includes(selected)?selected:null};}
function discloseEfforts(){portfolioLimit+=12;renderSidebar();render();}
const scopedSessions=()=> (snapshotData.sessions||[]).filter(s=>!snapshotData.effort||s.effort_root===snapshotData.effort);
const shortPath=p=>String(p||'').replace(/\/$/,'').split('/').pop();
const warningSession=s=>['failed','needs_input','interrupted','blocked'].includes(s.status)||Boolean(s.error);
const sessionTarget=s=>s.target?{...s.target,effort_root:s.effort_root}:{id:s.id};
const reservedSession=s=>Boolean(s && !s.target && (s.identity_origin==='ordinal-reserved' || s.effort_root));
const sessionIdentity=s=>s.target?`Position ${s.ordinal} · inst-${s.target.instantiation} · session ${s.target.session}`:reservedSession(s)?`Reserved position · native context unobserved${s.effort_root?` · Effort ${s.effort_root}`:''}`:'Original namespace · unadopted';
function mount(id, host){const e=$(id);if(!e)return null;mounted.add(e);host.append(e);e.hidden=false;return e;}
function park(){for(const e of mounted){$('legacy-storage').append(e);e.hidden=true;}mounted.clear();}
function backToEffortTarget(){
  // Effective preparation owner only: current operation selection, an actual effort root, matching the observed session effort.
  if(view.route!=='purposes'&&view.route!=='new-work')return '';
  const owner=window.NoeticEffort?.selection?.()?.effort_root;
  if(!owner||owner!==snapshotData.effort)return '';
  return roots().some(row=>row.ordinal===owner)?owner:'';
}
const FRAME_ROUTES=['workspaces','agentics','executions','artifacts','memory','usage'];
function frameEffort(){
 if(!FRAME_ROUTES.includes(view.route))return null;
 const effort=currentEffort();if(!effort)return null;
 if(view.route==='workspaces'||view.route==='agentics')return effort;
 const selection=window.NoeticEffort?.selection?.();
 if(!selection||selection.scope==='application')return null;
 if(selection.effort_root&&selection.effort_root!==effort.ordinal)return null;
 return effort;
}
function renderFrame(){
 const effort=frameEffort(),tabs=$('shell-tabs');
 if(!effort){if(frameOwner){tabs.replaceChildren();frameOwner=null;}tabs.hidden=true;}
 else{
  if(frameOwner!==effort.ordinal){frameOwner=effort.ordinal;tabs.replaceChildren();
   for(const [label,route] of [['Overview','workspaces'],['Agentics','agentics'],['Executions','executions'],['Artifacts','artifacts'],['Memory','memory'],['Tokens','usage']]){const b=button(label,()=>navigate(route));b.dataset.frameRoute=route;tabs.append(b);}}
  tabs.hidden=false;
  for(const b of tabs.children)b.classList.toggle('active',b.dataset.frameRoute===view.route);
 }
 $('shell-breadcrumb-root').textContent=effort?`Effort ${effort.ordinal}${effort.intent?` · ${effort.intent}`:''}`:['history','attention','closed'].includes(view.route)?'Application records':sidebarRoutes.has(view.route)?'Development portfolio':['runtime'].includes(view.route)?'Runtime control':['models','configuration'].includes(view.route)?'Installation':['disciplines','prompts','roles'].includes(view.route)?'Reusable libraries':'Application records';
 $('shell-breadcrumb-choice').textContent=view.route==='workspaces'&&currentEffort()?currentEffort().intent:labels[view.route];
 $('shell-sidebar').hidden=!sidebarRoutes.has(view.route)&&!effort;
 $('noetic-shell').classList.toggle('without-portfolio-sidebar',!sidebarRoutes.has(view.route)&&!effort);
}
function capturePlace(){
 if(restoring||!placeReady)return;
 const place={route:view.route,subview:view.subview,target:snapshotData.selected?JSON.parse(JSON.stringify(snapshotData.selected)):null,history:Boolean(snapshotData.applicationHistory),newConversation:Boolean(snapshotData.newConversation),browse:Boolean(snapshotData.projectBrowsing),project:snapshotData.projectPath||null,projectFilter,query:portfolioQuery,limit:portfolioLimit,mainScroll:$('run-detail').scrollTop,sidebarScroll:$('shell-sidebar').scrollTop,operation:window.NoeticEffort?.selection?.()?JSON.parse(JSON.stringify(window.NoeticEffort.selection())):null};
 place.signature=JSON.stringify([place.route,place.subview,place.target,place.history,place.newConversation,place.browse,place.project,place.projectFilter,place.query,place.limit,place.operation]);
 if(placeHistory.length&&placeHistory[placeHistory.length-1].signature===place.signature)return;
 placeHistory.push(place);if(placeHistory.length>8)placeHistory.shift();
}
function placeLabel(place){
 const scope=place.browse?(place.project?`Project ${shortPath(place.project)}`:'Your Work'):place.target?`${place.target.id?`native ${place.target.id}`:`position ${place.target.ordinal}`}${place.history?' · history':''}`:'Your Work';
 return `${labels[place.route]||place.route} · ${scope}`;
}
const placeScopeTuple=place=>JSON.stringify([place.target,place.history,place.newConversation,place.browse,place.project]);
const currentScopeTuple=()=>JSON.stringify([snapshotData.selected?JSON.parse(JSON.stringify(snapshotData.selected)):null,Boolean(snapshotData.applicationHistory),Boolean(snapshotData.newConversation),Boolean(snapshotData.projectBrowsing),snapshotData.projectPath||null]);
function returnToPrevious(){
 const place=placeHistory.pop();if(!place)return;
 const originGeneration=generation;
 restoring=true;
 try{
  if(placeScopeTuple(place)!==currentScopeTuple()){
   suppressPage=true;
   try{const pending=window.NoeticSessions.open(place.target?{...place.target}:null,{history:place.history,newConversation:place.newConversation,browse:place.browse,project:place.project||undefined});
    pending.catch(failure=>{if(generation===originGeneration&&view.route===place.route&&placeScopeTuple(place)===currentScopeTuple())notice(failure.message);});
   }finally{suppressPage=false;}
  }
  projectFilter=place.projectFilter;portfolioQuery=place.query;$('portfolio-query').value=place.query;portfolioLimit=place.limit;
  const operation=place.operation||{},mode=operation.scope==='application'||!operation.effort_root?'application':'effort';
  const observed=window.NoeticRuns?.state?.().selection,observedMode=observed&&observed.scope!=='application'&&observed.effort_root?'effort':'application';
  if(mode!==observedMode)window.NoeticRuns?.scope(mode);
  navigate(place.route);
  const scrollGeneration=generation;
  requestAnimationFrame(()=>{if(generation===scrollGeneration&&view.route===place.route&&placeScopeTuple(place)===currentScopeTuple()){$('run-detail').scrollTop=place.mainScroll;$('shell-sidebar').scrollTop=place.sidebarScroll;}});
 }finally{restoring=false;render();}
}
function heading({eyebrow='',title='',description='',actions=[]}){
 $('shell-eyebrow').textContent=eyebrow;$('shell-page-title').textContent=title;$('shell-description').textContent=description;
 const entries=(Array.isArray(actions)?actions:[actions]).filter(Boolean),prior=snapshotData.returnContext;if(prior && (snapshotData.projectBrowsing || JSON.stringify(snapshotData.selected)!==JSON.stringify(prior.target))){const resume=button(prior.label,()=>{window.NoeticSessions.returnToContext();navigate('agentics');},'secondary-button');resume.dataset.returnContext='true';entries.unshift(resume);}
 const effortOwner=backToEffortTarget();
 if(effortOwner){const target=effortOwner;const back=button(`Back to effort ${target}`,()=>{if(backToEffortTarget()===target&&(view.route==='purposes'||view.route==='new-work'))navigate('workspaces');},'secondary-button');back.dataset.backToEffort='true';entries.push(back);}
 const place=placeHistory[placeHistory.length-1];
 if(place&&!restoring){const previous=button(`Return to previous · ${placeLabel(place)}`,returnToPrevious,'secondary-button');previous.dataset.returnLocation='true';entries.unshift(previous);}
 const focusedReturn=document.activeElement?.dataset.returnContext==='true';
 const focusedBack=document.activeElement?.dataset.backToEffort==='true';
 const focusedLocation=document.activeElement?.dataset.returnLocation==='true';
 $('shell-actions').replaceChildren(...entries);if(focusedReturn)$('shell-actions').querySelector('[data-return-context]')?.focus({preventScroll:true});else if(focusedBack)$('shell-actions').querySelector('[data-back-to-effort]')?.focus({preventScroll:true});else if(focusedLocation)$('shell-actions').querySelector('[data-return-location]')?.focus({preventScroll:true});
}
function notice(value){$('shell-global-error').textContent=value||'';$('shell-global-error').hidden=!value;}
function renderObservationStatus(){
 const unavailable=Boolean(snapshotData.observationError),message=unavailable?'Session observations unavailable. Previously fetched conversations may be stale.':'';
 $('shell-observation-error').textContent=message;$('shell-observation-error').hidden=!message;
 $('shell-health').textContent=unavailable||!$('fetch-error').hidden?'Observation unavailable · retained data':'Observations available';
}
function render(){
 if($('private-workspace').hidden)return;
 renderObservationStatus();
 const handler=routes.get(view.route);if(!handler)return;
 const host=$('shell-content');host.dataset.route=view.route;
 Promise.resolve(handler({host,snapshot:snapshot(),route:view.route,subview:view.subview})).catch(e=>{if(host.dataset.route===view.route)notice(e.message);});
}
function navigate(route,options={}){
 if(!labels[route])route='workspaces';
 const changed=route!==view.route;
 if(changed&&!options.fromChoice&&!restoring&&placeReady)capturePlace();
 view={route,subview:options.subview??(changed?'':view.subview)};generation++;
 if(changed){park();$('shell-content').replaceChildren();$('shell-content').className='';for(const key of Object.keys($('shell-content').dataset))delete $('shell-content').dataset[key];$('run-detail').scrollTop=0;}
 $('shell-content').dataset.route=route;$('noetic-shell').classList.toggle('without-portfolio-sidebar',!sidebarRoutes.has(route));$('shell-sidebar').hidden=!sidebarRoutes.has(route);
 for(const b of $('shell-navigation').querySelectorAll('[data-route]')){b.classList.toggle('active',b.dataset.route===route||route==='executions'&&b.dataset.route==='workspaces');b.setAttribute('aria-current',String(b.classList.contains('active')));}
 $('shell-settings').classList.toggle('active',route==='configuration');
 $('shell-project-scope').replaceChildren();notice('');
 try{sessionStorage.setItem('noetic-shell-view',JSON.stringify(view));}catch(_){}
 document.title=`noetic-dev / ${labels[route]}`;renderFrame();renderSidebar();render();
}
window.NoeticUI={register:(route,handler)=>{routes.set(route,handler);if(view.route===route)render();},navigate,heading,mount,element:el,button,icon,badge,snapshot,refresh:render,notice,route:()=>view.route};
for(const item of nav){if(!item){$('shell-navigation').append(el('div','rail-divider'));continue;}const [route,label,iconName]=item;const b=button('',()=>navigate(route),'rail-button');b.dataset.route=route;b.title=label;b.setAttribute('aria-label',label);b.append(icon(iconName));$('shell-navigation').append(b);}
$('shell-settings').append(icon('settings'));$('shell-settings').addEventListener('click',()=>navigate('configuration'));
$('shell-account').addEventListener('click',()=>{const d=$('shell-command-dialog');$('shell-command-query').value='';renderCommand('access');d.showModal();});
$('portfolio-options').append(icon('more'));$('portfolio-options').addEventListener('click',()=>openCommand());
$('shell-new-effort').prepend(icon('plus'));$('shell-new-effort').addEventListener('click',()=>navigate('new-effort'));
$('shell-installation').prepend(icon('cube'));$('shell-installation').addEventListener('click',()=>navigate('configuration'));
$('shell-search').append(icon('search'));
$('portfolio-query').addEventListener('input',()=>{portfolioQuery=$('portfolio-query').value.toLowerCase();portfolioLimit=12;renderSidebar();render();});
$('portfolio-clear').addEventListener('click',()=>{$('portfolio-query').value='';portfolioQuery='';portfolioLimit=12;renderSidebar();render();$('portfolio-query').focus();});
$('portfolio-more').addEventListener('click',discloseEfforts);
for(const b of document.querySelectorAll('[data-shell-view]')){b.className='view-item';b.prepend(icon(b.dataset.shellView==='attention'?'activity':b.dataset.shellView==='history'?'clock':'archive'));b.addEventListener('click',()=>navigate(b.dataset.shellView));}
function resize(id,property,min,max,start){const handle=$(id);handle.classList.add('shell-resizer');handle.setAttribute('aria-valuemin',min);handle.setAttribute('aria-valuemax',max);let width=start;const apply=value=>{width=Math.max(min,Math.min(max,value));$('noetic-shell').style.setProperty(property,width+'px');handle.setAttribute('aria-valuenow',width);};handle.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();apply(width+(e.key==='ArrowRight'?12:-12));}});handle.addEventListener('pointerdown',e=>{e.preventDefault();const x=e.clientX,initial=width;document.body.classList.add('resizing-panes');const move=v=>apply(initial+v.clientX-x),stop=()=>{document.removeEventListener('pointermove',move);document.removeEventListener('pointerup',stop);document.body.classList.remove('resizing-panes');};document.addEventListener('pointermove',move);document.addEventListener('pointerup',stop,{once:true});});}
resize('rail-resizer','--rail-width',56,104,64);resize('sidebar-resizer','--sidebar-width',200,360,248);
async function chooseProject(project){capturePlace();projectFilter=project;portfolioQuery='';$('portfolio-query').value='';portfolioLimit=12;let loading;suppressPage=true;try{loading=window.NoeticSessions.browseProject(project);}finally{suppressPage=false;}navigate('workspaces',{fromChoice:true});await loading;}
async function chooseEffort(effort){capturePlace();projectFilter=effort.environment?.cwd||null;let loading;suppressPage=true;try{loading=window.NoeticSessions.open({ordinal:effort.ordinal,effort_root:effort.ordinal});}finally{suppressPage=false;}navigate('workspaces',{fromChoice:true});await loading;}
function renderSidebar(){
 const all=roots(),signature=JSON.stringify([all,snapshotData.sessions?.map(s=>[s.id,s.status,s.error]),snapshotData.effort,projectFilter,portfolioQuery,portfolioLimit]);if($('shell-sidebar').dataset.signature===signature)return;$('shell-sidebar').dataset.signature=signature;
 const projects=[...new Set(all.map(p=>p.environment?.cwd).filter(Boolean))];
 if(projectFilter&&!projects.includes(projectFilter))projectFilter=null;
 const filter=$('shell-filter');filter.replaceChildren();const head=el('div','scope-control-heading');head.append(el('span','','PROJECTS'),button('Portfolio',()=>chooseProject(null)));filter.append(head);
 function filterRow(name,meta,path,count){const b=button('',()=>chooseProject(path),`${path?'project-scope-row':'portfolio-scope-row'} ${projectFilter===path?'selected':''}`);const copy=el('span');copy.append(el('strong','',name),el('small','',meta));b.append(el('span','scope-radio'),copy);if(count!==undefined)b.append(el('span','scope-effort-count',count));return b;}
 filter.append(filterRow('Development portfolio',`${projects.length} projects · ${all.length} efforts`,null));const branch=el('div','scope-tree-branch');for(const path of projects)branch.append(filterRow(shortPath(path),path,path,all.filter(p=>p.environment?.cwd===path).length));filter.append(branch);const note=el('div','scope-filter-note');note.append(icon('search',12),el('span','','Choose a project to browse its efforts, then choose an effort to work. Return keeps the exact prior context.'));filter.append(note);
 const catalogue=effortCatalogue(),visible=catalogue.shown;$('shell-effort-count').textContent=catalogue.matching.length;
 $('portfolio-coverage').textContent=`Showing ${visible.length} of ${catalogue.matching.length} matches · ${all.length} efforts total${catalogue.pin?' · selected effort pinned separately':''}`;
 $('portfolio-more').disabled=visible.length>=catalogue.matching.length;$('portfolio-more').textContent=$('portfolio-more').disabled?'All matches shown':`Show ${Math.min(12,catalogue.matching.length-visible.length)} more efforts`;
 function effortRow(p){const sessions=(snapshotData.sessions||[]).filter(s=>s.effort_root===p.ordinal),attention=sessions.filter(warningSession).length;const b=button('',()=>chooseEffort(p),`effort-item ${snapshotData.effort===p.ordinal?'selected':''}`);b.dataset.effort=p.ordinal;const copy=el('span','effort-copy');copy.append(el('span','effort-name',p.intent),el('span','effort-meta',`${p.ordinal} · ${attention?attention+' needs attention':sessions.filter(s=>s.broker_owned).length?sessions.filter(s=>s.broker_owned).length+' active':sessions.length+' retained observations'}`));b.append(el('span',`status-dot ${attention?'amber':'violet'}`),copy);return b;}
 $('shell-efforts').replaceChildren(...visible.map(effortRow));
 if(!visible.length)$('shell-efforts').append(el('p','empty-note','No efforts match this view.'));
 if(catalogue.pin){const pin=el('div','effort-pin');pin.append(el('small','','Selected effort · outside shown matches'),effortRow(catalogue.pin));$('shell-efforts').append(pin);}
 const count=(snapshotData.sessions||[]).filter(warningSession).length;$('shell-attention-count').textContent=count||'';$('shell-attention-count').className=count?'count-badge':'';$('shell-attention-count').title=`${count} recorded session requests or startup failures`;
}
function card(kicker,title,action){const p=el('section','panel'),h=el('header','panel-heading'),titles=el('div');titles.append(el('span','panel-kicker',kicker),el('h2','',title));h.append(titles);if(action)h.append(action);p.append(h);return p;}
function action(value,fn){return button(value,fn,'text-action');}
const runObservation=()=>window.NoeticRuns?.state()||{selection:window.NoeticEffort?.selection?.()||{scope:'application'},status:'unobserved',warnings:[],runs:[]};
function executionBlockers(limit=null,effort=null){
 const observation=runObservation(),scope=observation.selection.effort_root?`Effort ${observation.selection.effort_root}`:'Application · all efforts and original histories';
 const p=card('RECORDED STATES','Recorded execution blockers',limit===null?null:action('Open Attention',()=>navigate('attention')));
 p.append(el('p','source',`Execution coverage: ${scope}${effort?` · displayed blockers: Effort ${effort}`:''}`));
 const status=observation.status==='observed'?`Observed ${observation.observedAt||'on the latest successful read'}`:observation.status==='loading'?`Loading run register.${observation.observedAt?' Showing the previous successful observation.':' No observation yet.'}`:observation.status==='unavailable'?`Run register unavailable: ${observation.error}. ${observation.observedAt?'Previously fetched observations are stale.':'No successful observation yet.'}`:'Run register not yet observed.';
 p.append(el('p','field-note',status));
 if(observation.warnings.length)p.append(el('p','inline-attention',`Incomplete coverage: ${observation.warnings.join(' ')}`));
 const blockers=observation.runs.filter(r=>['blocked','failed'].includes(r.state)&&(!effort||r.correspondence?.effort_root===effort));
 for(const r of limit===null?blockers:blockers.slice(0,limit)){const row=button('',()=>{navigate('executions');selectRun(r.run_id);},'record-row execution-blocker');row.dataset.runId=r.run_id;row.append(badge(r.state,'warning'),el('strong','',r.goal||r.run_id),el('small','mono',`${r.run_id} · ${r.correspondence?.effort_root?`Effort ${r.correspondence.effort_root}`:'Original namespace · unassigned'}`));p.append(row);}
 if(!blockers.length&&observation.status==='observed')p.append(el('p','empty-note',effort?`No blocked or failed executions observed for Effort ${effort} in this coverage.`:'No blocked or failed executions observed in this coverage.'));
 if(limit!==null&&blockers.length>limit)p.append(action(`Inspect all ${blockers.length} recorded blockers`,()=>navigate('attention')));
 p.append(el('p','field-note','Recorded blocked or failed states invite inspection; they do not establish an outstanding human obligation. Historical review findings remain in exact execution evidence.'));
 return p;
}
function openSession(s){window.NoeticSessions.open(sessionTarget(s));navigate('agentics');}
function overview({host}){
 const effort=currentEffort(),sessions=scopedSessions(),positions=(snapshotData.positions||[]).filter(p=>p.effort===effort?.ordinal);
 heading({eyebrow:effort?`Effort ${effort.status} / Ordinal ${effort.ordinal}`:'APPLICATION WORKSPACE',title:effort?.intent||(projectFilter?`Project · ${shortPath(projectFilter)}`:'Development portfolio'),description:effort?.mandate?.mandate?.objective||effort?.intent||(projectFilter?`${projectFilter} · Choose an effort to establish its work context. Prior exact context remains available through Return.`:'Choose a project or an effort to begin. Original histories remain accessible in Application records.'),actions:[button('New effort',()=>navigate('new-effort'),'secondary-button'),...(effort?[button('Entrust work',()=>navigate('new-work'),'primary-button')]:[])]});
 $('shell-breadcrumb-choice').textContent=effort?.intent||(projectFilter?shortPath(projectFilter):'Workspaces');
 renderFrame();if(effort)$('shell-project-scope').replaceChildren(el('span','scope-label','PROJECT SCOPE'),badge(shortPath(effort.environment?.cwd)));
 const signature=JSON.stringify([effort,sessions,positions,allRuns,runObservation(),projectFilter,portfolioQuery,portfolioLimit,snapshotData.observationError]);if(host.dataset.signature===signature)return;host.dataset.signature=signature;host.className='overview-content';host.replaceChildren();
 if(!effort){const catalogue=effortCatalogue(),p=card('YOUR WORK','Choose an effort',button('New effort',()=>navigate('new-effort'),'primary-button'));p.append(el('p','empty-note',`Showing ${catalogue.shown.length} of ${catalogue.matching.length} matching efforts · ${catalogue.all.length} total. Find effort in the sidebar searches full ordinals, intentions and project paths.`));const list=el('div','portfolio-cards');for(const r of catalogue.shown){const b=button('',()=>chooseEffort(r),'portfolio-effort-card');b.append(el('span','mono',r.ordinal),el('strong','',r.intent),el('small','',r.environment?.cwd||'Environment unavailable'));list.append(b);}if(!list.children.length)list.append(el('p','empty-note',catalogue.all.length?'No efforts match this view. Clear the search or project filter to browse the catalogue.':'Create an effort to establish its intent and environment. You can begin a conversation when ready.'));p.append(list);if(catalogue.shown.length<catalogue.matching.length)p.append(button('Show more efforts',discloseEfforts,'secondary-button'));host.append(p);return;}
 const left=el('div','overview-main'),right=el('div','overview-aside');host.append(left,right);
 const metrics=el('section','summary-strip');for(const [label,value,note]of[['Responsibility',effort.intent,`Persistent position ${effort.ordinal}`],['Environment',shortPath(effort.environment?.cwd),`Revision ${effort.environment_version||1} · declared environment`],['Effort activity',`${sessions.length} retained observations`,`${sessions.filter(s=>s.broker_owned).length} owned processes observed`]]){const c=el('div');c.append(el('span','',label),el('strong','',value),el('small','mono',note));metrics.append(c);}left.append(metrics);
 const work=card('CURRENT WORK','Execution activity',action('Inspect executions',()=>navigate('executions')));const list=el('div','execution-list');
 const ordered=[...sessions].sort((a,b)=>Number(warningSession(b))-Number(warningSession(a))||String(b.updated_at).localeCompare(String(a.updated_at)));
 for(const s of ordered.slice(0,3)){const row=el('article','work-entry');const header=el('div','work-entry-heading'),copy=el('div');copy.append(button(s.title||'Session',()=>openSession(s),'work-title'),el('small','mono',sessionIdentity(s)));header.append(el('span','ordinal-tile',s.ordinal),copy,badge(s.status,warningSession(s)?'warning':s.broker_owned?'success':'neutral'));row.append(header);const mandate=positions.find(p=>p.ordinal===s.ordinal);if(mandate?.mandate?.mandate){const m=el('div','mandate-block');m.append(el('span','mandate-label','MANDATE'),el('p','',mandate.mandate.mandate.objective||mandate.mandate.mandate.responsibility||s.title));row.append(m);}if(s.error)row.append(el('div','inline-attention',s.error));else row.append(el('div','work-observation',reservedSession(s)?'Startup reservation · native context unobserved':s.broker_owned?'Native process owned · inspect current output':'Retained conversation · open to inspect or continue explicitly'));list.append(row);}
 if(!sessions.length){list.append(el('p','empty-note','No conversations have been started for this effort.'),button('Start conversation',()=>{window.NoeticSessions.open({ordinal:effort.ordinal,effort_root:effort.ordinal},{newConversation:true});navigate('agentics');},'secondary-button'));}work.append(list);left.append(work);
 const lineage=card('ACCOUNTABILITY','Agentics lineage',action('Open full tree',()=>navigate('agentics')));const lines=el('div','lineage-list');for(const p of positions){const b=button('',()=>{window.NoeticSessions.open({ordinal:p.ordinal,effort_root:effort.ordinal});navigate('agentics');},'lineage-row');b.append(el('span','mono',p.ordinal),el('strong','',p.intent||p.mandate?.mandate?.objective||sessions.find(s=>s.ordinal===p.ordinal)?.title||(p.origin==='human'?'Assigned responsibility':'Delegated responsibility')),el('small','',p.current_instantiation?`Current instantiation ${p.current_instantiation}`:'Dormant position'));lines.append(b);}lineage.append(lines);left.append(lineage);
 const attention=card('CONTEXTS & STARTUP','Session requests & startup failures',action('Open Attention',()=>navigate('attention')));const needs=sessions.filter(warningSession);for(const s of needs.slice(0,3)){const row=el('div','attention-entry');row.append(el('span','attention-type',s.status.replaceAll('_',' ')),el('h3','',s.title),el('p','',s.error||'Inspect the retained observation before continuing.'),action(reservedSession(s)?'Inspect reserved position':'Inspect exact session',()=>openSession(s)));attention.append(row);}if(!needs.length)attention.append(el('p','empty-note',snapshotData.observationError?'Session observations are unavailable. Retained observations may be stale.':'No session requests or failures observed.'));right.append(attention,executionBlockers(3,effort.ordinal));
 const results=card('LATEST','Evidence & results',action('View artifacts',()=>navigate('artifacts')));const runs=allRuns.filter(r=>r.correspondence?.effort_root===effort.ordinal);for(const r of runs.slice(0,3)){const row=button('',()=>{selectRun(r.run_id);navigate('executions');},'result-row');row.append(icon('file'),el('strong','',r.goal||r.run_id),badge(r.state));results.append(row);}if(!runs.length)results.append(el('p','empty-note','No structured results recorded in this effort. Conversation returns remain with their exact sessions.'));right.append(results);
 const purpose=card('CONTINUATION','Purpose & limits',action('Inspect purposes',()=>navigate('purposes')));purpose.append(el('p','empty-note','Inspect owned purposes or create an explicit Telos link for continuing work.'));right.append(purpose);
}
routes.set('workspaces',overview);
function newEffort({host}){
 heading({eyebrow:'NEW RESPONSIBILITY',title:'New effort',description:'Declare the intention and project environment. Its ordinal persists across conversations.',actions:[]});if(host.dataset.ready==='effort')return;host.dataset.ready='effort';host.className='new-effort-content';
 const p=card('EFFORT SCOPE','What are you working toward?'),form=el('form','effort-create-form');
const inputs={};for(const [id,label,placeholder,tag]of[['effort-intent','Effort intention','Build a shared reading list','textarea'],['effort-directory','Project folder','/path/to/project','input']]){const l=el('label','',label);l.htmlFor=id;const input=el(tag);inputs[id]=input;input.id=id;input.required=true;input.placeholder=placeholder;if(tag==='textarea')input.rows=3;form.append(l,input);}
 if(!effortDraft)effortDraft={intent:'',cwd:'',pending:null};
 if(!effortDraft.cwd&&!effortDraft.pending&&!inputs['effort-directory'].value){
  const folder=window.NoeticUI?.snapshot?.().projectFilter||roots().find(row=>row.ordinal===snapshotData.effort)?.environment?.cwd||'';
  if(folder)effortDraft.cwd=folder;
 }
 inputs['effort-intent'].value=effortDraft.intent;inputs['effort-directory'].value=effortDraft.cwd;
 form.append(el('p','field-note','Register an existing folder without starting a model. Several efforts may share a folder and retain separate intentions.'));
 const submit=button('Create effort',null,'primary-button');submit.type='submit';const status=el('p','form-status');status.setAttribute('role','status');status.setAttribute('aria-live','polite');form.append(submit,status);
 const showStatus=message=>{status.textContent=message||'';};
 const syncPending=()=>{const pending=effortDraft&&effortDraft.pending;const unchanged=Boolean(pending&&effortDraft.intent===pending.rawIntent&&effortDraft.cwd===pending.rawCwd);
  const busy=Boolean(pending&&pending.sending),created=Boolean(pending&&pending.created&&!pending.sending);submit.disabled=busy||(created&&unchanged);submit.setAttribute('aria-busy',String(busy));submit.setAttribute('aria-disabled',String(submit.disabled));if(busy)showStatus('Creating effort…');else if(created)showStatus(pending.refreshError?`Effort ${pending.ordinal||'created'} was created, but refreshing the workspace failed: ${pending.refreshError}. The draft is kept; submitting the same effort again is disabled to avoid a duplicate.`:`Effort created${pending.ordinal?` as ${pending.ordinal}`:''}.`);else if(pending&&pending.error)showStatus(`Creating the effort failed: ${pending.error}. The draft is retained; submit again to retry.`);else if(effortDraftNotice)showStatus(effortDraftNotice);else showStatus('');};
 syncPending();effortSync=syncPending;effortInputs=inputs;
 const capture=()=>{effortDraft.intent=inputs['effort-intent'].value;effortDraft.cwd=inputs['effort-directory'].value;effortDraftNotice='';syncPending();};
 for(const id of ['effort-intent','effort-directory'])inputs[id].addEventListener('input',capture);
 form.addEventListener('submit',e=>{e.preventDefault();const d=effortDraft||(effortDraft={intent:'',cwd:'',pending:null});  if(d.pending&&(d.pending.sending||(d.pending.created&&d.intent===d.pending.rawIntent&&d.cwd===d.pending.rawCwd)))return;effortDraftNotice='';capture();
  const pending={rawIntent:d.intent,rawCwd:d.cwd,contextEffort:snapshotData.effort??null,generation,intent:d.intent.trim(),cwd:d.cwd.trim(),sending:true,created:false,error:'',refreshError:''};d.pending=pending;syncPending();
  (async()=>{const syncIfAttached=()=>{if(view.route==='new-effort'){render();if(effortInputs){effortInputs['effort-intent'].value=effortDraft?effortDraft.intent:'';effortInputs['effort-directory'].value=effortDraft?effortDraft.cwd:'';}if(effortSync)effortSync();}};
   try{const response=await fetchJSON('/api/efforts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({intent:pending.intent,environment:{cwd:pending.cwd},human_ref:{origin:'local-operator'},source_ref:{kind:'desktop-effort-form'}})});
    pending.sending=false;pending.created=true;pending.ordinal=response?.effort?.ordinal||'';syncIfAttached();
    let observation=null;
    try{observation=await window.NoeticSessions.observedRefresh();}catch(f){if(!pending.ordinal)pending.refreshError=f.message;}
    const sameContext=generation===pending.generation&&view.route==='new-effort'&&(snapshotData.effort??null)===pending.contextEffort;
    const unchanged=effortDraft===d&&d.intent===pending.rawIntent&&d.cwd===pending.rawCwd;
    if(sameContext&&unchanged){
     const state=window.NoeticSessions.state();
     const observationFailed=Boolean(observation&&!observation.observed||state.observationError);
     const observed=!observationFailed&&(state.positions||[]).some(row=>row.ordinal===pending.ordinal&&row.effort===row.ordinal);
     if(observed){await chooseEffort(response.effort);if(effortDraft===d&&d.intent===pending.rawIntent&&d.cwd===pending.rawCwd)effortDraft=null;}
     else pending.refreshError=observationFailed?`Effort ${pending.ordinal||'created'} keeps its registration receipt and unsent draft; the post-mutation observation was unavailable and duplicate submission stays prevented.`:'the created effort was not observed after refresh';
    }else if(unchanged){d.intent='';d.cwd='';effortDraftNotice=`Effort created${pending.ordinal?` as ${pending.ordinal}`:''}.`;}
    syncIfAttached();
   }catch(f){pending.sending=false;pending.error=f.message;syncIfAttached();}
  })();
 });p.append(form);host.replaceChildren(p);
 const create=card('NEW PROJECT','Create a folder and start work');create.append(el('p','empty-note','Use the project conversation flow to create a new project and begin with a first instruction.'),button('Create project and conversation',()=>{window.NoeticSessions.open(null);$('developer-project-mode').value='create';$('developer-project-mode').dispatchEvent(new Event('change',{bubbles:true}));navigate('agentics');},'secondary-button'));host.append(create);
}
routes.set('new-effort',newEffort);
function recordsView({host,route}){
 heading({eyebrow:'APPLICATION RECORDS',title:labels[route],description:route==='history'?'Correlated activity across enduring positions and exact contexts.':route==='closed'?'Retained efforts and conversations remain inspectable.':'Inspect session requests, startup failures and separately scoped recorded execution blockers.',actions:[button('Refresh',()=>{window.NoeticSessions.refresh();if(route==='attention')window.NoeticRuns?.refresh();},'secondary-button')]});
 const list=route==='attention'?(snapshotData.sessions||[]).filter(warningSession):route==='closed'?(snapshotData.sessions||[]).filter(s=>s.status==='closed'):[...(snapshotData.sessions||[])].sort((a,b)=>String(b.updated_at).localeCompare(String(a.updated_at)));
 const signature=JSON.stringify([list,route,route==='attention'?runObservation():null,snapshotData.observationError]);if(host.dataset.signature===signature)return;const active=host.contains(document.activeElement)?document.activeElement:null,focusedRun=active?.dataset.runId,focusedScope=active?.getAttribute('aria-label')==='Execution observation scope';host.dataset.signature=signature;host.className='records-content';const p=card('CONTEXTS & STARTUP',route==='closed'?'Closed conversations':route==='attention'?'Session requests & startup failures':'Latest context and startup observations');if(route==='attention')p.append(el('p','source','Registry coverage: Application · retained native contexts and startup reservations'),el('p','field-note',snapshotData.observationError?'Session observations unavailable. Previously fetched conversations may be stale.':'Latest registry observation; the sidebar badge counts these recorded session requests and startup failures.'));for(const s of list){const row=button('',()=>openSession(s),'record-row');row.append(el('span','ordinal-tile',s.ordinal||s.original_ordinal),el('strong','',s.title),el('small','mono',sessionIdentity(s)),badge(s.status,warningSession(s)?'warning':'neutral'));p.append(row);}if(!list.length)p.append(el('p','empty-note',route==='attention'?(snapshotData.observationError?'No retained session requests to display.':'No session requests or failures observed.'):'No matching observations.'));host.replaceChildren(p);
 if(route==='attention'){const controls=el('label','scope-control','Execution observation scope '),select=el('select');select.setAttribute('aria-label','Execution observation scope');for(const [value,label]of[['application','Application · all efforts and original histories'],...snapshotData.effort?[['effort',`Effort ${snapshotData.effort}`]]:[]]){const option=el('option','',label);option.value=value;select.append(option);}select.value=runObservation().selection.effort_root?'effort':'application';select.addEventListener('change',()=>window.NoeticRuns?.scope(select.value));controls.append(select);host.append(controls,executionBlockers());if(focusedScope)select.focus({preventScroll:true});else if(focusedRun)[...host.querySelectorAll('[data-run-id]')].find(row=>row.dataset.runId===focusedRun)?.focus({preventScroll:true});}
 if(route==='history'){const b=button('Open global ordinal history',()=>{window.NoeticSessions.open(null,{history:true});navigate('agentics');},'secondary-button');host.append(b);}if(route==='closed')p.append(el('p','field-note','Effort lifecycle closure is not exposed by the current application. Closing a session does not close its effort.'));
}
for(const route of ['history','attention','closed'])routes.set(route,recordsView);
function renderCommand(mode=commandMode){
 commandMode=mode;
 const query=$('shell-command-query').value.toLowerCase(),holder=$('shell-command-results');holder.replaceChildren();
 const items=mode==='access'?[['Lock workspace',()=> $('access-lock').click()],['Log out',()=> $('access-logout').click()]]:[...Object.entries(labels).map(([r,label])=>[label,()=>navigate(r)]),...roots().map(p=>[`${p.ordinal} · ${p.intent}`,()=>chooseEffort(p)]),...(snapshotData.positions||[]).filter(p=>p.effort!==p.ordinal).map(p=>[`${p.ordinal} · ${p.intent||'Position'}`,()=>{window.NoeticSessions.open({ordinal:p.ordinal,...p.effort?{effort_root:p.effort}:{}});navigate('agentics');}])];
 for(const [label,fn]of items.filter(([label])=>label.toLowerCase().includes(query)))holder.append(button(label,()=>{$('shell-command-dialog').close();fn();},'command-result'));if(!holder.children.length)holder.append(el('p','empty-note','No matches.'));
}
function openCommand(){renderCommand('');$('shell-command-dialog').showModal();$('shell-command-query').focus();}
$('shell-search').addEventListener('click',openCommand);$('shell-command').addEventListener('click',openCommand);$('shell-breadcrumb-choice').addEventListener('click',openCommand);$('shell-command-query').addEventListener('input',()=>renderCommand());
document.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();if($('shell-command-dialog').open)$('shell-command-dialog').close();else openCommand();}});
document.addEventListener('noetic:sessions',e=>{snapshotData=e.detail||{};if(snapshotData.projectBrowsing)projectFilter=snapshotData.projectPath||null;else if(snapshotData.selected){const owner=roots().find(row=>row.ordinal===snapshotData.effort);projectFilter=owner?.environment?.cwd||null;}renderFrame();renderSidebar();render();});
new MutationObserver(renderObservationStatus).observe($('fetch-error'),{attributes:true,attributeFilter:['hidden'],childList:true,subtree:true,characterData:true});
document.addEventListener('noetic:runs',()=>{renderFrame();if(['workspaces','history','attention','purposes','new-work'].includes(view.route))render();});
document.addEventListener('noetic:page',e=>{if(suppressPage)return;const map={developer:'agentics',workspace:'executions',new:'new-work',history:'history',memory:'memory',purposes:'purposes',diagnostics:'configuration'};const next=map[e.detail.page];if(next&&next!==view.route)navigate(next);});
let paired=false;
new MutationObserver(()=>{const visible=!$('private-workspace').hidden;if(visible&&!paired){paired=true;snapshotData=window.NoeticSessions?.state?.()||{};if(snapshotData.projectBrowsing)projectFilter=snapshotData.projectPath||null;navigate(view.route);placeReady=true;fetchJSON('/api/preview-info').then(data=>{if(data.fixture_mode||data.fixture||data.demo||data.preview||data.mode){$('shell-preview-label').hidden=false;$('shell-preview-label').textContent='Demonstration records · isolated preview';$('shell-notice').hidden=false;$('shell-notice').textContent='Demonstration records · isolated local preview';}}).catch(()=>{});}}).observe($('private-workspace'),{attributes:true,attributeFilter:['hidden']});
if(!$('private-workspace').hidden){paired=true;snapshotData=window.NoeticSessions?.state?.()||{};if(snapshotData.projectBrowsing)projectFilter=snapshotData.projectPath||null;navigate(view.route);placeReady=true;}
})();
