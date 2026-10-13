"use strict";

(() => {
  let layout, canvas, inspector, viewport, map, tabs, filter, zoomLabel, inspectorHeading, provenance, occupant;
  let headerDelegate;
  let treeDisclosure, treeCoverage, treeMore, treeReveal, treeLimit=40, treeScope="";
  let expandedBranches=new Set(["0"]), lastTreeSelection="";
  let snapshot = {}, view = "tree", zoom = 100, paneWidth = 500, filterEffort = "", find = "", drawingSignature = "";
  const ui = () => window.NoeticUI;
  const el = (tag, cls, value) => ui().element(tag, cls, value);
  const btn = (value, action, cls = "secondary-button") => ui().button(value, action, cls);
  const targetOf = session => session.target ? {...session.target, effort_root:session.effort_root} : {id:session.id};
  const currentAt = ordinal => (snapshot.sessions || []).find(item => item.ordinal === ordinal && item.is_current);
  const occupantContext = ordinal => {
    const position=(snapshot.positions || []).find(item => item.ordinal === ordinal);
    return currentAt(ordinal) || (snapshot.sessions || []).filter(item => item.ordinal === ordinal && item.target && item.target.instantiation === position?.current_instantiation)
      .sort((a,b) => b.target.session - a.target.session)[0];
  };
  const positionTitle = row => {
    const mandate=row.mandate?.mandate || row.mandate;
    return (row.ordinal === row.effort ? row.intent : null) || mandate?.title || occupantContext(row.ordinal)?.title || mandate?.purpose || `Position ${row.ordinal}`;
  };
  const lineage = row => row.origin === "human" ? `Human assignment · under ${row.parent}` : row.origin === "agent" ? `Delegated by ${row.parent}` : `Parent position ${row.parent || "unobserved"}`;
  const stateOf = session => !session ? "dormant" : ["running", "starting"].includes(session.status) ? "running" : ["needs_input", "interrupted"].includes(session.status) ? "waiting" : "dormant";
  const openPosition = position => {
    const current = occupantContext(position.ordinal);
    return window.NoeticSessions.open(current ? targetOf(current) : {ordinal:position.ordinal, ...(position.effort ? {effort_root:position.effort} : {})});
  };
  const positions = () => {
    const rows = [...(snapshot.positions || [])];
    if (!rows.some(row => row.ordinal === "0")) rows.unshift({ordinal:"0",parent:null,status:"dormant"});
    const projects = new Set(rows.filter(row => row.effort === row.ordinal && row.environment?.cwd === snapshot.projectFilter).map(row => row.ordinal));
    let visible = rows.filter(row => row.ordinal === "0" || (!filterEffort || row.effort === filterEffort) && (!snapshot.projectFilter || projects.has(row.effort)));
    if (find) {
      const included = new Set(["0"]);
      for (const row of visible) {
        if (!`${row.ordinal} ${row.intent || ""} ${occupantContext(row.ordinal)?.title || ""}`.toLowerCase().includes(find.toLowerCase())) continue;
        let cursor = row;
        while (cursor && !included.has(cursor.ordinal)) { included.add(cursor.ordinal); cursor = rows.find(parent => parent.ordinal === cursor.parent); }
      }
      visible = visible.filter(row => included.has(row.ordinal));
    }
    return visible.sort((a,b) => a.ordinal.localeCompare(b.ordinal,"en",{numeric:true}));
  };

  function setZoom(value) {
    zoom = Math.min(115,Math.max(40,value)); map.style.zoom = `${zoom}%`; zoomLabel.textContent = `${zoom}%`;
  }
  function fit() {
    setZoom(Math.floor(Math.min(1.15,Math.max(.4,(viewport.clientWidth - 24) / Number(map.dataset.width || 700)))*100));
  }
  function setWidth(value) {
    const max = Math.max(260,Math.min(760,layout.clientWidth-340));
    paneWidth = Math.min(max,Math.max(260,value)); layout.style.setProperty("--tree-pane-width",`${paneWidth}px`);
    layout.querySelector('[role="separator"]').setAttribute("aria-valuenow",String(paneWidth));
  }
  function chooseView(value) {
    view = value; drawingSignature = "";
    for (const item of tabs.children) { item.classList.toggle("active",item.dataset.view === view); item.setAttribute("aria-selected",String(item.dataset.view === view)); }
    if (view === "returns") window.NoeticSessions.observeReturns();
    draw();
  }
  function build(host) {
    layout = el("div","responsibility-layout agentics-layout");
    layout.style.setProperty("--tree-pane-width",`${paneWidth}px`);
    canvas = el("section","panel responsibility-canvas agentics-canvas");
    const toolbar = el("div","canvas-toolbar"); tabs = el("div","view-switcher"); tabs.setAttribute("role","tablist");
    for (const value of ["tree","sessions","returns"]) {
      const item = btn(value[0].toUpperCase()+value.slice(1),() => chooseView(value),value === view ? "active" : "");
      item.dataset.view = value; item.setAttribute("role","tab"); item.setAttribute("aria-selected",String(value === view)); tabs.append(item);
    }
    const tools = el("div","canvas-tools"), legend = el("div","canvas-legend");
    for (const value of ["running","waiting","dormant"]) { const entry = el("span"); entry.append(el("i",`legend-dot ${value}`),document.createTextNode(value[0].toUpperCase()+value.slice(1))); legend.append(entry); }
    const zooms = el("div","zoom-controls"); zooms.setAttribute("aria-label","Tree zoom controls");
    const out = btn("−",() => setZoom(zoom-15),""); out.setAttribute("aria-label","Zoom out");
    zoomLabel = btn(`${zoom}%`,fit,"zoom-value"); zoomLabel.setAttribute("aria-label","Fit visible tree to view");
    const more = btn("+",() => setZoom(zoom+15),""); more.setAttribute("aria-label","Zoom in"); zooms.append(out,zoomLabel,more);
    tools.append(legend,zooms); toolbar.append(tabs,tools);
    const filterBar = el("div","agentics-filter"); filter = el("select","topology-mode"); filter.setAttribute("aria-label","Filter topology by effort");
    filter.addEventListener("change",() => {filterEffort=filter.value; drawingSignature="";draw();});
    const search = el("input","agentics-find"); search.type="search"; search.placeholder="Find position…"; search.setAttribute("aria-label","Find position");
    search.addEventListener("input",() => {find=search.value;drawingSignature="";draw();}); filterBar.append(filter,search);
    treeDisclosure=el("div","agentics-tree-disclosure");treeCoverage=el("span");treeCoverage.id="agentics-tree-coverage";treeCoverage.setAttribute("role","status");
    treeMore=btn("Show more positions",()=>{treeLimit+=40;drawingSignature="";draw();});treeMore.id="agentics-tree-more";treeReveal=btn("Reveal selected",()=>revealSelected());treeReveal.id="agentics-reveal-selected";
    const collapse=btn("Collapse other branches",()=>{expandedBranches=new Set(selectedPath());expandedBranches.add("0");drawingSignature="";draw();});collapse.id="agentics-collapse-other";
    treeDisclosure.append(treeCoverage,treeMore,collapse,treeReveal);
    viewport = el("div","agentics-viewport"); map=el("div","node-map agentics-node-map"); viewport.append(map); canvas.append(toolbar,filterBar,treeDisclosure,viewport);
    const resizer=el("div","pane-resizer inner-resizer"); resizer.tabIndex=0; resizer.setAttribute("role","separator"); resizer.setAttribute("aria-label","Resize agentics tree and conversation"); resizer.setAttribute("aria-orientation","vertical"); resizer.setAttribute("aria-valuemin","260"); resizer.setAttribute("aria-valuemax","760"); resizer.setAttribute("aria-valuenow",String(paneWidth));
    resizer.addEventListener("keydown",event => {if (["ArrowLeft","ArrowRight"].includes(event.key)) {event.preventDefault();setWidth(paneWidth+(event.key === "ArrowRight" ? 20 : -20));}});
    resizer.addEventListener("pointerdown",event => {
      event.preventDefault(); const start=event.clientX,width=paneWidth;
      document.body.classList.add("resizing-panes");
      const move=event => setWidth(width+event.clientX-start), end=() => {window.removeEventListener("pointermove",move);window.removeEventListener("pointerup",end);window.removeEventListener("pointercancel",end);document.body.classList.remove("resizing-panes");};
      window.addEventListener("pointermove",move);window.addEventListener("pointerup",end);window.addEventListener("pointercancel",end);
    });
    inspector=el("aside","panel node-inspector session-terminal agentics-inspector");
    inspectorHeading=el("div","inspector-heading session-heading"); provenance=el("div","agent-topology agentics-provenance"); occupant=el("div","session-context");
    const positionStatus=el("div","inspector-status"); positionStatus.id="agentics-position-status";
    inspector.append(inspectorHeading,positionStatus,provenance,occupant);
    layout.append(canvas,resizer,inspector);host.append(layout);
    new ResizeObserver(()=>{if(view==="tree"&&layout.isConnected){drawingSignature="";draw();}}).observe(viewport);
    ui().mount("developer-page",inspector);
    const evidence=document.getElementById("developer-evidence"), header=document.getElementById("developer-header");
    let retained=document.getElementById("agentics-retained-details");
    if (!retained) {retained=el("div","agentics-retained-details");retained.id="agentics-retained-details";evidence.querySelector(":scope > summary").after(retained);}
    for (const selector of [".section-heading","#developer-location",".session-signals"]) {
      const existing=header.querySelector(selector);if(existing)retained.append(existing);
    }
    const handoff=header.querySelector(".developer-actions details");if(handoff)retained.prepend(handoff);
    retained.append(document.getElementById("developer-result"));
    if (!document.getElementById("agentics-responsibility-details")) {
      const responsibility=el("div","agentics-responsibility-details");responsibility.id="agentics-responsibility-details";evidence.append(responsibility);
    }
    evidence.querySelector(":scope > summary").textContent="Context & session evidence";
    document.getElementById("developer-prompt").placeholder="Direct this exact session…";
    document.getElementById("developer-prompt").rows=3;
    document.getElementById("developer-transcript").classList.add("terminal-transcript");
  }

  function nodeCard(row, x, y) {
    const current = occupantContext(row.ordinal), root = row.ordinal === "0";
    const card=btn("",() => openPosition(row),`responsibility-node${root ? " root" : ""}${snapshot.selected?.ordinal === row.ordinal ? " selected" : ""}`);
    card.dataset.ordinal=row.ordinal; card.style.left=`${x}px`;card.style.top=`${y}px`;
    const top=el("span","node-topline"), badges=el("span","node-badges");badges.append(el("span",`node-state ${stateOf(current)}`));top.append(el("code","",row.ordinal),badges);
    card.append(top,el("strong","",root ? "Application governance" : positionTitle(row)),el("small","",root ? "Logical root · no native occupant" : row.effort === row.ordinal ? "Effort root" : lineage(row)));return card;
  }
  function treeProjection(rows,limit,selectedOrdinal) {
    const byOrdinal=new Map(rows.map(row=>[row.ordinal,row])),included=new Set();
    function includePath(ordinal){while(byOrdinal.has(ordinal)&&!included.has(ordinal)){included.add(ordinal);ordinal=byOrdinal.get(ordinal).parent;}}
    for(const row of rows.slice(0,limit))includePath(row.ordinal);
    if(selectedOrdinal)includePath(selectedOrdinal);
    return rows.filter(row=>included.has(row.ordinal));
  }
  function selectedPath() {
    const byOrdinal=new Map((snapshot.positions||[]).map(row=>[row.ordinal,row])),path=[],seen=new Set();
    let ordinal=snapshot.selected?.ordinal;
    if(ordinal==="0")return ["0"];
    while(byOrdinal.has(ordinal)&&!seen.has(ordinal)){seen.add(ordinal);path.push(ordinal);ordinal=byOrdinal.get(ordinal).parent;}
    if(ordinal==="0")path.push("0");
    return path;
  }
  function revealSelected() {
    const path=selectedPath();if(!path.length)return;
    for(const ordinal of path.slice(1))expandedBranches.add(ordinal);
    drawingSignature="";draw();
    const card=[...map.querySelectorAll('.responsibility-node')].find(node=>node.dataset.ordinal===path[0]);
    if(card){viewport.scrollTop=Math.max(0,card.offsetTop*zoom/100-20);viewport.scrollLeft=0;card.focus({preventScroll:true});}
  }
  function drawTree(matching) {
    const path=selectedPath(),selected=path[0]||"",selection=JSON.stringify(snapshot.selected||null);
    if(selection!==lastTreeSelection){lastTreeSelection=selection;for(const ordinal of path.slice(1))expandedBranches.add(ordinal);}
    treeReveal.disabled=!selected||!matching.some(row=>row.ordinal===selected);
    const byOrdinal=new Map(matching.map(row=>[row.ordinal,row])),children=new Map();
    for(const row of matching){const parent=byOrdinal.has(row.parent)?row.parent:null;if(!children.has(parent))children.set(parent,[]);children.get(parent).push(row);}
    const visible=[],depths=new Map(),seen=new Set();
    function walk(row,depth){if(seen.has(row.ordinal))return;seen.add(row.ordinal);visible.push(row);depths.set(row.ordinal,depth);if(find||expandedBranches.has(row.ordinal))for(const child of children.get(row.ordinal)||[])walk(child,depth+1);}
    for(const row of children.get(null)||[])walk(row,0);
    // Cyclic records remain addressable without inferring a new parent.
    for(const row of matching){let cursor=row,chain=new Set();while(cursor&& !seen.has(cursor.ordinal)&&!chain.has(cursor.ordinal)){chain.add(cursor.ordinal);cursor=byOrdinal.get(cursor.parent);}if(cursor&&chain.has(cursor.ordinal))walk(row,0);}
    const rows=treeProjection(visible,treeLimit,selected),collapsed=matching.length-visible.length,undisclosed=visible.length-rows.length;
    treeCoverage.textContent=`Showing ${rows.length} of ${matching.length} matching positions · ${collapsed} hidden in collapsed branches · ${undisclosed} awaiting disclosure${selected&&!rows.some(row=>row.ordinal===selected)?" · selected position is hidden in this view":""}. Find searches the complete scoped topology.${find?" Search temporarily reveals branches; clear Find to change expansion.":""}`;
    treeMore.disabled=undisclosed===0;treeMore.textContent=treeMore.disabled?"All expanded positions shown":`Show ${Math.min(40,undisclosed)} more positions`;
    const locations=new Map(rows.map((row,index)=>[row.ordinal,{x:40+(depths.get(row.ordinal)||0)*24,y:16+index*102}]));
    const width=Math.max(230,...[...locations.values()].map(p=>p.x+202)),height=Math.max(32,rows.length*102+16);
    map.style.width=`${width}px`;map.style.minWidth="0";map.style.height=`${height}px`;map.dataset.width=String(width);
    const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");svg.setAttribute("width",String(width));svg.setAttribute("height",String(height));svg.classList.add("agentics-connectors");svg.setAttribute("aria-hidden","true");
    for(const row of rows){const parent=locations.get(row.parent),child=locations.get(row.ordinal);if(!parent||!child)continue;const line=document.createElementNS(svg.namespaceURI,"path");if(row.origin==="human")line.classList.add("human-assignment");line.dataset.parent=row.parent;line.dataset.child=row.ordinal;line.setAttribute("d",`M ${parent.x-12} ${parent.y+43} V ${child.y+43} H ${child.x-4}`);svg.append(line);}
    function descendants(ordinal){const found=new Set([ordinal]),pending=[...(children.get(ordinal)||[])];while(pending.length){const row=pending.pop();if(found.has(row.ordinal))continue;found.add(row.ordinal);pending.push(...children.get(row.ordinal)||[]);}return found.size-1;}
    const active=map.contains(document.activeElement)?{ordinal:document.activeElement.dataset.ordinal,branch:document.activeElement.dataset.branch}:null,scrollTop=viewport.scrollTop,scrollLeft=viewport.scrollLeft;
    const nodes=[];for(const row of rows){const p=locations.get(row.ordinal);nodes.push(nodeCard(row,p.x,p.y));const count=descendants(row.ordinal);if(!count)continue;const expanded=Boolean(find||expandedBranches.has(row.ordinal)),toggle=btn(expanded?"−":"+",()=>{if(expandedBranches.has(row.ordinal))expandedBranches.delete(row.ordinal);else expandedBranches.add(row.ordinal);drawingSignature="";draw();},"agentics-branch-toggle");toggle.dataset.branch=row.ordinal;toggle.style.left=`${p.x-32}px`;toggle.style.top=`${p.y+29}px`;toggle.setAttribute("aria-expanded",String(expanded));toggle.setAttribute("aria-label",`${expanded?"Collapse":"Expand"} branch ${row.ordinal} (${count} descendants)`);toggle.title=`${count} descendants${find?" · clear Find to change branch expansion":""}`;toggle.disabled=Boolean(find);const badge=el("small","agentics-descendant-count",`${count} descendants`);badge.style.left=`${p.x}px`;badge.style.top=`${p.y+87}px`;nodes.push(toggle,badge);}
    map.replaceChildren(svg,...nodes);setZoom(zoom);viewport.scrollTop=scrollTop;viewport.scrollLeft=scrollLeft;
    if(active){const selector=active.branch?'.agentics-branch-toggle':'.responsibility-node',key=active.branch?'branch':'ordinal',value=active.branch||active.ordinal;[...map.querySelectorAll(selector)].find(node=>node.dataset[key]===value)?.focus({preventScroll:true});}
  }
  function drawSessions(rows) {
    map.style.cssText="width:100%"; map.dataset.width=String(viewport.clientWidth);
    const selectedOrdinals=new Set(rows.map(row=>row.ordinal));
    const sessions=(snapshot.sessions||[]).filter(item=> {
      const scoped=Boolean(filterEffort||snapshot.projectFilter);
      if(scoped&&(!item.effort_root||!selectedOrdinals.has(item.effort_root)||filterEffort&&item.effort_root!==filterEffort))return false;
      if(!find)return !scoped||selectedOrdinals.has(item.ordinal);
      return item.effort_root ? selectedOrdinals.has(item.ordinal) : `${item.original_ordinal||item.ordinal||""} ${item.title||""} ${item.id||""}`.toLowerCase().includes(find.toLowerCase());
    });
    map.replaceChildren(...sessions.map(item=> {
      const row=btn("",()=>window.NoeticSessions.open(targetOf(item)),"agentics-session-row");row.dataset.sessionId=item.id;
      const target=item.target;row.append(el("code","",item.ordinal||item.original_ordinal||"Native source"),el("strong","",item.title||item.id),el("small","",target ? `Instantiation ${target.instantiation} · session ${target.session} · ${item.is_current ? "current" : "retained"}` : item.effort_root || item.identity_origin==="ordinal-reserved" ? "Reserved position · native context unobserved" : "Original namespace · unadopted"),el("span",`state-pill ${stateOf(item)}`,item.status));
      return row;
    }));
    if(!sessions.length)map.append(el("p","agentics-empty","No retained native sessions in this view."));
  }
  let returnView = "", returnRows = new Map();
  function drawReturns(rows) {
    map.style.cssText=""; map.dataset.width="700";
    const ordinals=new Set(rows.map(row=>row.ordinal));
    const returns=(snapshot.applicationEvents||[]).filter(record=> {
      if ((filterEffort||snapshot.projectFilter||find)&&!ordinals.has(record.ordinal)) return false;
      const event=record.data?.controller_event||record.data?.event||record.data?.record||record.data;
      return /return|retire/.test(record.kind||"") || record.kind==="structured-controller-event"&&/return|retire/.test(event?.kind||event?.type||"");
    });
    const scope=JSON.stringify([snapshot.selected,filterEffort,snapshot.projectFilter,find]);
    if(returnView!==scope){returnView=scope;returnRows.clear();}
    const retained=new Map(), articles=returns.map(record=>{
      const identity=JSON.stringify([record.sequence,record.ordinal,record.effort]);
      const article=returnRows.get(identity)||el("article","agentics-return-row");
      if(!article.children.length){const evidence=el("details");evidence.append(el("summary","","Recorded return evidence"),el("pre"));article.append(el("code"),el("small"),evidence);}
      article.querySelector("code").textContent=`${record.ordinal} · ${record.kind}`;
      article.querySelector("small").textContent=record.at||"";
      const source=JSON.stringify(record,null,2), pre=article.querySelector("pre");if(pre.textContent!==source)pre.textContent=source;
      retained.set(identity,article);return article;
    });
    returnRows=retained;
    for(const child of [...map.children])if(!articles.includes(child))child.remove();
    articles.forEach((article,index)=>{if(map.children[index]!==article)map.insertBefore(article,map.children[index]||null);});
    if(!returns.length)map.append(el("p","agentics-empty",snapshot.observationError ? "Return observation unavailable." : "No recorded controller returns in this view."));
    map.append(el("p","agentics-limit","Return decisions are retained controller evidence. A manual return action is unavailable."));
  }

  function drawInspector() {
    const selected=snapshot.selected, session=snapshot.detail?.session || (selected?.id ? (snapshot.sessions||[]).find(item=>item.id===selected.id) : null);
    const reserved=Boolean(session && !session.target && (session.effort_root || session.identity_origin==="ordinal-reserved"));
    const browsing=Boolean(snapshot.projectBrowsing), projectDraft=!selected&&!snapshot.applicationHistory&&!browsing;
    const original=Boolean(!reserved && (session ? session.identity_origin === "legacy-unadopted" || !session.target && !session.effort_root : selected?.id && !selected.ordinal && !selected.effort_root));
    const ordinal=original ? session?.original_ordinal||session?.ordinal||"Native" : selected?.ordinal||session?.ordinal||"0";
    const row=original||projectDraft||browsing ? null : (snapshot.positions||[]).find(item=>item.ordinal===ordinal), current=original||projectDraft||browsing ? null : occupantContext(ordinal);
    const parent=original && session?.parent_id ? (snapshot.sessions||[]).find(item=>item.id===session.parent_id) : null;
    const root=!original&&!projectDraft&&!browsing && ordinal==="0", exact=!reserved && Boolean(selected?.instantiation||selected?.id);
    const badge=el("div","agent-avatar violet",projectDraft?"+":ordinal), identity=el("div");
    identity.append(el("span","panel-kicker",browsing ? "Project overview · no conversation selected" : projectDraft ? "Project conversation" : reserved ? "Reserved position · native context unobserved" : original ? "Original namespace · unadopted" : exact ? "Exact session" : root ? "Application responsibility" : "Ordinal position"),el("h2","",browsing ? snapshot.projectPath ? `Project ${snapshot.projectPath}` : "Development portfolio" : projectDraft ? "Open or create a project" : reserved ? `Position ${ordinal}` : exact ? `Session ${selected.instantiation ? `${selected.instantiation}/${selected.session}` : selected.id}` : root ? "Application governance" : row ? positionTitle(row) : `Position ${ordinal}`));
    const context=btn("Context",()=>{const evidence=document.getElementById("developer-evidence");evidence.open=!evidence.open;},"session-context-button"); context.disabled=!session&&!row;
    inspectorHeading.replaceChildren(badge,identity,context);
    let viewOwner=inspector.querySelector('.agentics-view-owner');
    if(!viewOwner){viewOwner=el('div','agentics-view-owner');inspectorHeading.after(viewOwner);}
    const outside=Boolean(selected && (filterEffort||find) && (original || !positions().some(position=>position.ordinal===ordinal)));
    viewOwner.hidden=!outside;
    if(outside){const focused=viewOwner.contains(document.activeElement);const clear=btn('Clear topology filters',()=>{filterEffort='';filter.value='';find='';layout.querySelector('.agentics-find').value='';drawingSignature='';draw();});viewOwner.replaceChildren(el('p','agentics-limit',`${original ? 'Original native source '+session?.id : 'Selected position '+ordinal} remains the exact inspection target outside this topology projection.`),clear);if(focused)clear.focus({preventScroll:true});}

    document.getElementById("agentics-position-status").hidden=provenance.hidden=occupant.hidden=projectDraft||browsing;
    document.getElementById("developer-prompt").placeholder=projectDraft?"Describe the app or work you want done…":"Direct this exact session…";
    document.getElementById("agentics-position-status").replaceChildren(el("span",`state-pill ${stateOf(session||current)}`,root ? "Dormant" : session?.status||current?.status||(row?.current_instantiation ? "Native context unobserved" : "Uninstantiated")),el("code","",original ? `Original position ${ordinal} · unadopted` : `Position ${ordinal}`));
    const provenanceHeading=el("div","topology-provenance"), composition=el("div");
    composition.append(el("strong","",original ? session?.parent_id ? "Native parent session" : "Original root session" : root ? "Enduring governance position" : row?.origin === "human" ? "Human assignment" : row?.origin === "agent" ? "Agent delegation" : "Registered responsibility"),el("small","",original ? session?.parent_id ? `${parent?.original_ordinal || parent?.ordinal || "Ordinal unobserved"} · original namespace · ${session.parent_id}` : "Original namespace · unadopted" : row?.parent ? lineage(row) : "Application namespace")); provenanceHeading.append(el("span","panel-kicker",original ? "Original session lineage" : "Agent composition"),composition);
    const mandate=row?.mandate?.mandate || row?.mandate, mandateText=original ? "Original namespace · unadopted. No application mandate is assigned to this native source." : typeof mandate==="string" ? mandate : mandate ? JSON.stringify(mandate) : root ? "Root 0 governs the application namespace." : "Select a position to inspect its mandate.";
    const responsibilityHost=document.getElementById("agentics-responsibility-details");
    const responsibilityKey=JSON.stringify([selected?.ordinal,selected?.effort_root,selected?.instantiation,selected?.session,selected?.id,ordinal,snapshot.applicationHistory]);
    let responsibility=responsibilityHost.querySelector(".agentics-mandate");
    if(responsibilityHost.dataset.identity!==responsibilityKey || !responsibility){
      responsibilityHost.dataset.identity=responsibilityKey;responsibility=el("details","agentics-mandate");
      responsibility.append(el("summary","","Mandate & environment"),el("pre"));
      responsibilityHost.replaceChildren(responsibility,el("small","agentics-limit","Position pruning and mandate editing are unavailable."));
    }
    const mandateSource=mandateText+(row?.environment ? `\n\n${JSON.stringify(row.environment,null,2)}` : "");
    if(responsibility.querySelector("pre").textContent!==mandateSource)responsibility.querySelector("pre").textContent=mandateSource;
    provenance.replaceChildren(provenanceHeading);
    const who=el("div");who.append(el("span","",original ? "Application correspondence" : "Current occupant"),el("strong","",original ? "Unadopted native source" : root ? "No native actor" : row?.current_instantiation ? `Instantiation ${row.current_instantiation} · ${current?.model || "native model unobserved"}` : current?.target ? `Instantiation ${current.target.instantiation} · ${current.model || "native model unobserved"}` : "No instantiation observed"));
    const selectedContext=el("div");selectedContext.append(el("span","","Selected context"),el("strong","",reserved ? `Reserved position ${ordinal} · native context unobserved · record ${session.id}` : exact ? selected.instantiation ? `Instantiation ${selected.instantiation} · session ${selected.session}${session?.is_current ? " · current" : " · retained"}` : `Native session ${selected.id}${original ? " · original namespace · unadopted" : ""}` : "Position history"));occupant.replaceChildren(who,selectedContext);
    inspector.dataset.positionOnly=String(snapshot.applicationHistory||root||reserved||browsing);
    inspector.dataset.exact=String(exact);
  }
  function draw() {
    if(!layout?.isConnected)return;
    const scope=JSON.stringify([filterEffort,snapshot.projectFilter,find]);if(treeScope!==scope){treeScope=scope;treeLimit=40;}
    treeDisclosure.hidden=view!=="tree";
    const roots=(snapshot.positions||[]).filter(row=>row.effort===row.ordinal);
    const optionsSignature=JSON.stringify(roots.map(row=>[row.ordinal,row.intent]));
    if(filter.dataset.signature!==optionsSignature) {
      filter.dataset.signature=optionsSignature; const option=el("option","","Portfolio topology");option.value="";
      filter.replaceChildren(option,...roots.map(row=>{const item=el("option","",`${row.ordinal} · ${row.intent || "Effort"}`);item.value=row.ordinal;return item;}));filter.value=filterEffort;
    }
    if(headerDelegate)headerDelegate.disabled=!snapshot.detail?.session.broker_owned||!snapshot.detail?.session.is_current||snapshot.observationError;
    const rows=positions(), signature=JSON.stringify([rows,snapshot.sessions,snapshot.selected,view,filterEffort,find,treeLimit,[...expandedBranches],snapshot.applicationEvents,snapshot.observationError,snapshot.projectFilter,snapshot.detail?.session,snapshot.projectBrowsing,snapshot.projectPath]);
    if(drawingSignature!==signature) {drawingSignature=signature; if(view==="tree")drawTree(rows);else if(view==="sessions")drawSessions(rows);else drawReturns(rows);drawInspector();}
  }
  function render({host,snapshot:next}) {
    snapshot=next||window.NoeticSessions.state();
    const actions=[btn("Find position",()=>layout.querySelector(".agentics-find").focus())];
    const delegate=btn("+ Delegate agent responsibility",()=>document.getElementById("developer-delegate").click(),"primary-button");
    headerDelegate=delegate; delegate.disabled=!snapshot.detail?.session.broker_owned||!snapshot.detail?.session.is_current||snapshot.observationError;actions.push(delegate);
    ui().heading({eyebrow:`Application namespace · ${positions().length} matching positions`,title:"Agentics",description:"Inspect enduring ordinal positions, genuine delegation lineage, occupants, and exact sessions across efforts.",actions});
    if(!layout?.isConnected||layout.parentNode!==host) {build(host);drawingSignature="";}
    draw();
  }
  document.addEventListener("noetic:sessions",event=>{snapshot={...event.detail,projectFilter:ui().snapshot().projectFilter};if(layout?.isConnected)draw();});
  window.NoeticUI.register("agentics",render);
})();
