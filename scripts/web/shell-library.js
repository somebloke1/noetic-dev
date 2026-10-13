"use strict";

(() => {
  const UI = window.NoeticUI;
  if (!UI) return;
  const el = (tag, cls, value) => UI.element(tag, cls, value);
  const get = id => document.getElementById(id);
  const action = (text, onClick, cls = "secondary-button") => UI.button(text, onClick, cls);
  const titles = {runtime:"Runtime control",models:"Models",disciplines:"Disciplines",prompts:"Prompt templates",roles:"Roles",memory:"Typed memory",usage:"Usage metrics",artifacts:"Artifacts",configuration:"Configuration",executions:"Executions","new-work":"Start structured work",purposes:"Telos purposes"};
  const descriptions = {
    runtime:"Observe exact native sessions and retained execution state. Open a target to control its work.",
    models:"Inspect exact configured model identities and local support settings.",
    disciplines:"Versioned cognitive and development programs with explicit roles, inputs, outputs, and stopping conditions.",
    prompts:"Inspect maintained instruction contracts and their required inputs.",
    roles:"Inspect the obligations and output contracts of maintained discipline roles.",
    memory:"Inspect native semantic authority separately from supporting source recall.",
    usage:"Inspect native conversation accounting coverage for the selected scope.",
    artifacts:"Inspect retained outputs, provenance, checks, independent review, and project changes.",
    configuration:"Inspect installation settings, role defaults, and execution limits.",
    executions:"Follow structured execution, inspect evidence, and control the selected workflow.",
    "new-work":"Instantiate a maintained discipline in the selected effort and start its execution.",
    purposes:"Read and create native Telos purposes in their explicit owning scope."
  };
  const choices = {disciplines:null,roles:null,prompts:null,models:null};
  const views = {}, catalogues = new Map();
  let catalogueGeneration = 0;
  const runCatalogues = new WeakMap();
  const scope = () => typeof operationSelection === "function" ? operationSelection() : {scope:"application"};
  const scopeKey = () => JSON.stringify(scope());
  const active = (host, route, key) => host.dataset.route === route && key === scopeKey();
  function panel(title, kicker = "") {
    const card = el("section", "panel lib-panel");
    const header = el("div", "panel-header");
    const text = el("div");
    if (kicker) text.append(el("span", "panel-kicker", kicker));
    text.append(el("h2", "", title)); header.append(text); card.append(header);
    return card;
  }
  function body(card) { const node = el("div", "lib-panel-body"); card.append(node); return node; }
  function note(text, tone = "") { return el("p", `lib-note ${tone}`, text); }
  function values(parent, object) {
    const list = el("dl", "lib-values");
    for (const [label, value] of Object.entries(object || {})) {
      const row = el("div"); row.append(el("dt", "", label.replaceAll("_", " ")), el("dd", "", typeof value === "object" ? JSON.stringify(value) : String(value ?? "Unknown"))); list.append(row);
    }
    parent.append(list);
  }
  function details(parent, label, value) {
    const node = el("details", "lib-source"); node.append(el("summary", "", label), el("pre", "", JSON.stringify(value, null, 2))); parent.append(node);
  }
  function placeholder(parent, title, text) {
    const empty = el("div", "lib-empty"); empty.append(el("h3", "", title), el("p", "", text)); parent.append(empty);
  }
  function clear(host) {
    const controls=get("effort-operation-controls");
    if (controls && host.contains(controls)) get("legacy-storage").append(controls);
    host.replaceChildren();
  }
  function tabs(host, options, selected, onChange) {
    const nav = el("nav", "lib-tabs", ""); nav.setAttribute("aria-label", "Library views");
    for (const [id, label, count] of options) {
      const button = action(label, () => onChange(id)); button.className = selected === id ? "active" : "";
      button.setAttribute("aria-pressed", String(selected === id)); if (count != null) button.append(el("span", "", String(count))); nav.append(button);
    }
    host.append(nav);
  }
  function openWork(pattern) {
    const field = get("start-pattern"); if (field && pattern) { field.value = pattern; field.dispatchEvent(new Event("change", {bubbles:true})); }
    if (typeof switchPage === "function") switchPage("new");
    UI.navigate("new-work");
  }
  function base({host, route}) {
    host.dataset.route = route;
    UI.heading({eyebrow:["models","configuration"].includes(route) ? "Installation" : ["disciplines","prompts","roles"].includes(route) ? "Application library" : route === "runtime" ? "Live runtime" : "Application records",title:titles[route],description:descriptions[route]});
    if (host.dataset.libraryView !== route || !host.firstElementChild) {
      clear(host); host.dataset.libraryView = route;
      views[route] = {host, key:null, signature:null};
    }
    if (host.contains(get("effort-operation-controls"))) get("effort-operation-controls").hidden=false;
    return views[route];
  }
  function mounts(context, ids) {
    const state = base(context);
    if (!state.mounted) {
      scopeToolbar(context.host);
      const content = el("div", "lib-preserved"); context.host.append(content);
      for (const id of ids) UI.mount(id, content);
      state.mounted = true;
    }
    for (const id of ids) { const node = get(id); if (node && context.host.contains(node)) node.hidden = false; }
    get("effort-operation-controls").hidden = false;
    return state;
  }
  function scopeToolbar(host) {
    const toolbar=el("div","lib-scope-toolbar");host.append(toolbar);UI.mount("effort-operation-controls",toolbar);
  }
  async function catalogue(context) {
    const {host, route} = context, state = base(context), key = scopeKey(), selection = scope();
    UI.heading({eyebrow:"Application library",title:titles[route],description:descriptions[route],actions:[action("Refresh library",()=>{catalogues.delete(scopeKey());state.loaded=false;clear(host);catalogue(context);})]});
    if (host.contains(get("effort-operation-controls"))) get("effort-operation-controls").hidden=false;
    if (state.key === key && state.loaded) return;
    state.key = key; state.loaded = true;
    clear(host); scopeToolbar(host);
    placeholder(host, "Loading maintained definitions", "Reading the selected scope…");
    const generation = ++catalogueGeneration;
    try {
      let result = catalogues.get(key);
      if (!result) {
        result = await fetchJSON(scopedURL("/api/disciplines", {...selection, limit:1000}));
        const instances = [...(result.instances || [])];
        let after = result.next_after;
        while (after != null) {
          if (!active(host, route, key) || generation !== catalogueGeneration) return;
          const page = await fetchJSON(scopedURL("/api/disciplines", {...selection, limit:1000, after}));
          instances.push(...(page.instances || []));
          if (page.next_after == null || page.next_after <= after) break;
          after = page.next_after;
        }
        result = {...result, instances}; catalogues.set(key, result);
      }
      if (!active(host, route, key) || generation !== catalogueGeneration) return;
      state.result = result; renderCatalogue(context, result);
    } catch (failure) {
      if (!active(host, route, key) || generation !== catalogueGeneration) return;
      clear(host); placeholder(host, "Library unavailable", failure.message);
      host.append(action("Retry", () => { state.loaded = false; catalogue(context); }));
    }
  }
  function renderCatalogue(context, data) {
    const {host, route} = context;
    clear(host);
    scopeToolbar(host);
    const definitions = data.definitions || [], instances = data.instances || [];
    const phases = definitions.flatMap(entry => (entry.definition.phases || []).map(phase => ({...phase,pattern:entry.pattern,definition_ref:entry.definition_ref})));
    if (route === "disciplines") {
      const mode = views[route].tab || "definitions";
      tabs(host, [["definitions","Definitions",definitions.length],["instances","Instances",instances.length],["observations","Observations",instances.reduce((n, row) => n + (row.executions || []).length, 0)]], mode, id => {views[route].tab = id; renderCatalogue(context, data);});
      if (mode === "instances") {
        const card = panel("Effort-bound instances", "Recorded responsibility"), content = body(card); host.append(card);
        for (const instance of instances) {
          const row = el("article", "lib-record"); row.append(el("strong", "", instance.intent), el("p", "lib-mono", `Effort ${instance.effort} · discipline ${instance.id} · ${instance.definition_ref.id}`));
          values(row, {initiator:instance.initiator,parent_instance:instance.parent_instance,created_at:instance.created_at,executions:(instance.executions || []).length}); details(row, "Instance and exact bindings", instance); content.append(row);
        }
        if (!instances.length) placeholder(content, "No discipline instances", "Start structured work in an effort to instantiate a maintained program.");
        return;
      }
      if (mode === "observations") {
        renderRunCatalogue(host, "Recorded executions"); return;
      }
      const layout = el("div", "lib-catalogue-layout"), list = el("div", "lib-card-grid"); layout.append(list); host.append(layout);
      const chosen = definitions.find(row => row.pattern === choices.disciplines) || definitions[0];
      for (const entry of definitions) {
        const card = action("", () => {choices.disciplines = entry.pattern; renderCatalogue(context, data);}); card.className = `lib-definition-card ${entry === chosen ? "selected" : ""}`;
        const top = el("div", "lib-card-top"); top.append(UI.icon("layers"), UI.badge("Maintained", "green"), el("span", "lib-mono", `v${entry.definition.version}`));
        card.append(top, el("h3", "", label(entry.pattern)), el("p", "", entry.definition.kind.replaceAll("_", " ")));
        const chips = el("div", "lib-chips"); for (const phase of entry.definition.phases || []) chips.append(el("span", "", label(phase.role))); card.append(chips, el("footer", "", `${instances.filter(row => row.definition_ref.id === entry.definition_ref.id).length} instances · inspect definition →`)); list.append(card);
      }
      if (!chosen) { placeholder(list, "No maintained programs", "The server returned no definitions."); return; }
      const detail = panel(label(chosen.pattern), "Selected definition"); detail.classList.add("lib-detail"); layout.append(detail);
      const content = body(detail); content.append(UI.badge("Definition only", "purple"));
      const sequence = el("ol", "lib-phase-sequence"); for (const phase of chosen.definition.phases || []) sequence.append(el("li", "", `${phase.id} · ${label(phase.role)}`)); content.append(sequence);
      if(chosen.backend === "opermem-reviewed"){content.append(note("Independent worker and reviewer. Initial GUI inquiry supports Question; other operations retain native capacity and need their scoped editors and prerequisites."));details(content,"Fourteen native operation prerequisites",chosen.operations);}
      values(content, {kind:chosen.definition.kind,pattern_version:chosen.definition_ref.pattern_version,phases:(chosen.definition.phases || []).length,transitions:(chosen.definition.transitions || []).length});
      const start = action("Instantiate in effort", () => openWork(chosen.pattern), "primary-button"); start.disabled = !scope().effort_root; content.append(start);
      if (start.disabled) content.append(note("Select an effort to start work."));
      content.append(note("Definitions are maintained in source; this interface reads their contracts.")); details(content,"Full versioned definition",chosen);
      return;
    }
    const layout = el("div", "lib-catalogue-layout"), list = el("div", "lib-list"); host.append(layout); layout.append(list);
    const chosen = phases.find(row => `${row.pattern}/${row.id}` === choices[route]) || phases[0];
    const title = route === "roles" ? "Maintained role contracts" : "Maintained instruction contracts";
    list.append(el("span", "panel-kicker", "Reusable library"), el("h2", "", title));
    for (const phase of phases) {
      const button = action("", () => {choices[route] = `${phase.pattern}/${phase.id}`; renderCatalogue(context, data);}); button.className = `lib-template ${phase === chosen ? "selected" : ""}`;
      button.append(el("span", "lib-template-icon", route === "roles" ? phase.id : "↳"));
      const text = el("span"); text.append(el("small", "lib-mono", `${phase.pattern} / ${phase.id}`), el("strong", "", label(phase.role)), el("p", "", (phase.criteria || [])[0] || phase.output_type)); button.append(text, el("span", "", "›")); list.append(button);
    }
    if (!chosen) {placeholder(list,"No maintained contracts","The server returned no phase contracts.");return;}
    const detail = panel(label(chosen.role), `${chosen.pattern} · ${chosen.id} · version ${chosen.definition_ref.pattern_version}`); detail.classList.add("lib-detail"); layout.append(detail);
    const content = body(detail); content.append(el("span", "panel-kicker", route === "roles" ? "Role obligations" : "Instruction contract"));
    for (const criterion of chosen.criteria || []) content.append(el("p", "lib-contract", criterion));
    content.append(el("h3", "", "Required inputs")); values(content, chosen.required_inputs);
    content.append(el("h3", "", "Output contract")); values(content, {type:chosen.output_type,...chosen.content_fields});
    if (chosen.return_targets) values(content,{return_targets:chosen.return_targets});
    content.append(note(route === "roles" ? "Roles are defined by the maintained program. Start its discipline to invoke them." : "A standalone editable template catalog is not exposed. These are the maintained criteria used by discipline execution."));
    content.append(action("Use discipline", () => openWork(chosen.pattern))); details(content,"Exact maintained phase",chosen);
  }
  function label(value) { return String(value || "Unknown").replaceAll("_", " ").replace(/\b\w/g, char => char.toUpperCase()); }
  function runtime(context) {
    const state = base(context), snapshot = context.snapshot || UI.snapshot();
    const selection=scope(), sessions=(snapshot.sessions || []).filter(row=>!selection.effort_root || row.effort_root===selection.effort_root);
    const signature = JSON.stringify([scopeKey(),typeof allRuns !== "undefined" ? allRuns.length : 0,sessions.map(row => [row.id,row.target,row.status,row.model,row.updated_at,row.error])]);
    if (state.signature === signature) return; state.signature = signature;
    const diagnostics = get("diagnostics-page"); if (diagnostics && context.host.contains(diagnostics)) get("legacy-storage").append(diagnostics);
    clear(context.host);
    scopeToolbar(context.host);
    const metrics = el("div", "lib-metrics");
    for (const [name,count] of [["Retained sessions",sessions.length],["Running",sessions.filter(row=>row.status === "running").length],["Executions",typeof allRuns !== "undefined" ? allRuns.length : 0]]) { const card = el("div", "panel lib-metric"); card.append(el("span", "", name),el("strong", "", String(count))); metrics.append(card); } context.host.append(metrics);
    const layout = el("div", "lib-catalogue-layout"), card = panel("Native sessions", "Exact retained targets"); layout.append(card); context.host.append(layout);
    const content = body(card);
    for (const session of sessions) {
      const row = el("article", "lib-runtime-row"), text = el("div");
      const target = session.target || {};
      text.append(el("span", "lib-mono", target.ordinal ? `${target.ordinal} · context ${target.instantiation}/${target.session}` : session.ordinal || session.id),el("strong", "", session.title || "Untitled session"),el("small", "", `${session.model || "Model unknown"} · ${session.status || "Status unknown"}`));
      row.append(text, action("Inspect / control", async () => { if (window.NoeticSessions) await window.NoeticSessions.open(session.target ? {...session.target,effort_root:session.effort_root} : {id:session.id}); UI.navigate("agentics"); })); content.append(row);
    }
    if (!sessions.length) placeholder(content,"No retained sessions","Create an effort and open a conversation to begin native work.");
    const side = panel("Structured work", "Controller authority"), sideBody = body(side); layout.append(side);
    sideBody.append(note("Pause, advance, cancel, and Apply controls belong to the selected recorded execution."), action("Open executions", () => UI.navigate("executions")),action("Start structured work", () => openWork("development")));
    const health = el("div", "lib-runtime-health"); context.host.append(health); UI.mount("diagnostics-page", health);
  }
  async function configured(context) {
    const state = base(context), {host, route} = context;
    let config = typeof configuration !== "undefined" ? configuration : null;
    if (!config && !state.loading) {
      state.loading = true;
      try { config = await fetchJSON("/api/configuration"); }
      catch (failure) { if (host.dataset.route === route) {host.replaceChildren(); placeholder(host,"Configuration unavailable",failure.message);} state.loading = false; return; }
      state.loading = false;
    }
    if (!config || host.dataset.route !== route) return;
    const signature = JSON.stringify(config); if (state.signature === signature) return; state.signature = signature; host.replaceChildren();
    if (route === "models") {
      const card = panel("Provider and model specifications", "Configured selections"), content = body(card); host.append(card);
      const groups = el("div", "lib-card-grid lib-model-grid"); content.append(groups);
      const local = config.local || {};
      const models = [...(config.profiles || []).map(profile=>({name:profile.label,model:profile.model,kind:"Code assist",data:profile})),...local.text_model ? [{name:"Local supporting text",model:local.text_model,kind:"Supporting text",data:{base_url:local.base_url,model:local.text_model}}] : [],...local.embedding_model ? [{name:"Semantic recall",model:local.embedding_model,kind:"Embedding",data:{base_url:local.embedding_base_url || local.base_url,model:local.embedding_model,dimensions:local.dimensions,source_model:local.source_model,api_key_env:local.embedding_api_key_env ?? local.api_key_env}}] : []];
      for (const model of models) {
        const item = el("article", "lib-model-card"); item.append(UI.badge(model.kind,"purple"),el("small", "", model.name),el("h3", "lib-mono", model.model),note("Configured selection · availability unverified")); details(item,"Inspect specification",model.data); groups.append(item);
      }
      if (!models.length) placeholder(content,"No configured identities","The server returned no model selections.");
      content.append(note("Provider configuration is maintained outside this interface. New work supports an explicit client/model override."),action("Configure next work",()=>openWork()));
      const availability = panel("Selection and qualification", "Dispatch resolution"), availabilityBody = body(availability); host.append(availability);
      availabilityBody.append(note(config.profile_notice || "Configured identity does not establish authentication or availability."));
      return;
    }
    const layout = el("div", "lib-catalogue-layout"), grid = el("div", "lib-card-grid"); host.append(layout); layout.append(grid);
    for (const [title,kicker,value] of [["Role defaults","Application",config.role_defaults],["Model selections","Installation",config.profiles],["Execution limits","Controller",config.limits],["Local support","Source recall",config.local]]) {
      const card = panel(title,kicker), content = body(card);
      if (Array.isArray(value)) for (const profile of value) values(content,{[profile.label]:profile.model});
      else if (title === "Local support") {values(content,{text_model:value?.text_model,embedding_model:value?.embedding_model,dimensions:value?.dimensions,base_url:value?.base_url});details(content,"Local support settings",value);}
      else values(content,value);
      grid.append(card);
    }
    const detail = panel("Configuration source", "Effective inspection"), content = body(detail); layout.append(detail);
    content.append(note("Explicit overrides → NOETIC_LOCAL_* environment → optional NOETIC_LOCAL_CONFIG → defaults.")); values(content,{namespace:config.namespace_path,telos:config.telos_database}); content.append(note("This interface inspects configuration. Set execution overrides in New work."),action("Configure next work",()=>openWork())); details(content,"Full observed settings",config);
  }
  function renderRunCatalogue(host, heading = "Retained executions") {
    let catalogue = runCatalogues.get(host);
    if (!catalogue || !host.contains(catalogue.card)) {
      const card = panel(heading,"Selected observation scope"), content = body(card), controls = el("div","lib-execution-controls"), label = el("label","","Find execution by ID, task or state"), search = el("input","lib-execution-query"), coverage = el("p","lib-note lib-execution-coverage"), pin = el("p","lib-note lib-execution-pin"), list = el("div","lib-execution-list");
      search.type = "search"; label.append(search); coverage.setAttribute("role","status");
      catalogue = {card,key:scopeKey(),limit:12,search,coverage,pin,list,rows:new Map()}; runCatalogues.set(host,catalogue);
      const clear = action("Clear search",()=>{search.value="";catalogue.limit=12;renderRunCatalogue(host,heading);search.focus();},"secondary-button lib-execution-clear");
      const more = action("Show more executions",()=>{catalogue.limit+=12;renderRunCatalogue(host,heading);},"secondary-button lib-execution-more"); catalogue.more = more;
      const inspect = action("Inspect selected execution",()=>{const id=typeof selectedId !== "undefined" ? selectedId : null;UI.navigate("executions");requestAnimationFrame(()=>revealExecution(id));},"secondary-button"); catalogue.inspect = inspect;
      search.addEventListener("input",()=>{catalogue.limit=12;renderRunCatalogue(host,heading);}); controls.append(label,clear,inspect); content.append(controls,coverage,pin,list,more); host.append(card);
    }
    if (catalogue.key !== scopeKey()) {catalogue.key=scopeKey();catalogue.limit=12;catalogue.search.value="";}
    const runs = typeof allRuns !== "undefined" ? allRuns : [];
    const id = typeof selectedId !== "undefined" ? selectedId : null, query = catalogue.search.value.trim().toLowerCase();
    const matching = runs.filter(run=>!query || JSON.stringify([run.run_id,run.goal,run.state,run.correspondence?.effort_root || "original namespace"]).toLowerCase().includes(query));
    const shown = matching.slice(0,catalogue.limit), selected = runs.find(run=>run.run_id===id), pin = selected && !shown.some(run=>run.run_id===id) ? selected : null;
    catalogue.coverage.textContent = `Showing ${shown.length} of ${matching.length} matching executions · ${runs.length} total retained observations.${pin ? " One selected execution is shown separately." : ""}`;
    catalogue.pin.hidden = !pin; catalogue.pin.textContent = pin ? `Selected execution pinned separately: ${pin.run_id}${matching.includes(pin) ? " · outside the current window" : " · does not match this query"}.` : "";
    catalogue.more.disabled = shown.length >= matching.length; catalogue.more.textContent = catalogue.more.disabled ? "All matching executions shown" : "Show more executions";
    catalogue.inspect.hidden = !id || !selectedDetail || selectedDetail.status?.run_id !== id;
    const retained = new Map(), wanted = [...shown,...pin ? [pin] : []].map(run=>{
      let row = catalogue.rows.get(run.run_id);
      if (!row) {
        const element = el("article","lib-execution-row"), button = action("",()=>{if(typeof selectRun === "function")selectRun(run.run_id);const state=views.executions;if(state)state.revealedRun=null;UI.navigate("executions");}); button.className = "lib-run-row"; button.dataset.runId = run.run_id;
        const text = el("span"), task = el("strong","lib-run-preview"), owner = el("small","lib-mono"), status = UI.badge("Unknown",""), evidence = el("details","lib-source"), source = el("pre");
        text.append(task,owner);button.append(text,status,el("span","","›"));evidence.append(el("summary","","Full task"),source);element.append(button,evidence);row={element,button,task,owner,status,source};
      }
      for(const [element,value] of [[row.task,run.goal || run.run_id],[row.owner,`${run.run_id} · ${run.correspondence?.effort_root ? `effort ${run.correspondence.effort_root}` : "original namespace"}`],[row.status,run.state || "Unknown"],[row.source,run.goal || "Task description unobserved."]])if(element.textContent!==value)element.textContent=value;
      row.button.setAttribute("aria-current",String(run.run_id===id));retained.set(run.run_id,row);return row.element;
    });
    const focused = catalogue.list.contains(document.activeElement) ? document.activeElement : null;
    for(const child of [...catalogue.list.children])if(!wanted.includes(child))child.remove();
    wanted.forEach((row,index)=>{if(catalogue.list.children[index]!==row)catalogue.list.insertBefore(row,catalogue.list.children[index] || null);});
    catalogue.rows = retained;if(focused?.isConnected && document.activeElement!==focused)focused.focus({preventScroll:true});
    if (!wanted.length) placeholder(catalogue.list,runs.length ? "No executions match this query" : "No recorded executions",runs.length ? "Clear the search to browse retained observations." : "Start structured work in a selected effort.");
    return catalogue.list;
  }
  function revealExecution(id) {
    const target = get("selected-run");
    if (!id || UI.route() !== "executions" || selectedId !== id || selectedDetail?.status?.run_id !== id || !target?.isConnected || target.hidden) return;
    target.tabIndex = -1; target.scrollIntoView({block:"start"}); target.focus({preventScroll:true});
  }
  function revealNewExecution(state) {
    const id = typeof selectedId !== "undefined" ? selectedId : null;
    if (!id || !selectedDetail || selectedDetail.status?.run_id !== id || state.revealedRun === id) return;
    state.revealedRun = id; const key = scopeKey();
    requestAnimationFrame(()=>{if(key===scopeKey() && !get("shell-content")?.querySelector(".lib-execution-query:focus"))revealExecution(id);});
  }
  function executions(context) {
    const state = base(context);
    if (!state.mounted) {
      scopeToolbar(context.host);
      const register = el("div","lib-execution-register"), detail = el("div","lib-preserved lib-execution-detail"); context.host.append(register,detail); state.register = register;
      UI.mount("workspace-page",detail); state.mounted = true;
    }
    get("workspace-page").hidden = false;
    get("effort-operation-controls").hidden = false;
    renderRunCatalogue(state.register); revealNewExecution(state);
  }
  function artifacts(context) {
    const state = base(context);
    if (!state.mounted) {
      scopeToolbar(context.host);
      const card = panel("Retained artifacts","Exact selected execution"), content = body(card); context.host.append(card); state.list = content;
      const detail = el("div","lib-preserved lib-artifact-detail"); context.host.append(detail); UI.mount("workspace-page",detail); state.mounted = true;
    }
    get("workspace-page").hidden = false;
    get("effort-operation-controls").hidden = false;
    const detail = typeof selectedDetail !== "undefined" ? selectedDetail : null;
    const signature = JSON.stringify([detail?.status?.run_id,detail?.controller?.artifacts,detail?.artifacts]);
    if (state.signature === signature) return; state.signature = signature; state.list.replaceChildren();
    if (!detail) {placeholder(state.list,"Select a recorded execution","Artifacts retain their original run, version, actor, and acceptance context.");state.list.append(action("Browse executions",()=>UI.navigate("executions")));return;}
    const typed = Object.values(detail.controller?.artifacts || {});
    for (const artifact of typed) {
      const row = action("",()=>{ get("artifact-select").value = artifact.id; get("artifact-select").dispatchEvent(new Event("change",{bubbles:true})); if (typeof switchView === "function") switchView("controller"); });row.className = "lib-run-row";
      const text = el("span"); text.append(el("strong","",artifact.type),el("small","lib-mono",`${artifact.id} · ${artifact.phase} · generation ${artifact.generation} · ${artifact.produced_by || "actor unknown"}`));row.append(text,UI.badge(artifact.partial ? "Partial" : "Retained",""),el("span","","›"));state.list.append(row);
    }
    for (const name of Object.keys(detail.artifacts || {})) {
      const report = [...get("report-select").options].some(option=>option.value === name);
      const log = [...get("log-select").options].some(option=>option.value === name);
      const row = action(name,()=>{const field = get(report ? "report-select" : "log-select");field.value=name;field.dispatchEvent(new Event("change",{bubbles:true}));if (typeof switchView === "function") switchView(report ? "reports" : "logs");});row.disabled=!report&&!log;row.className="lib-run-row";state.list.append(row);
    }
    if (!typed.length && !Object.keys(detail.artifacts || {}).length) placeholder(state.list,"No retained outputs","This execution has not produced readable artifacts.");
    if (typeof switchView === "function") switchView(typed.length ? "controller" : "reports");
  }
  function memory(context) {
    const state = base(context), key = scopeKey();
    if (!state.mounted) {
      scopeToolbar(context.host);
      const layout=el("div","lib-catalogue-layout"), native=panel("Retained native memory","Opermem authority"), content=body(native), source=el("div","lib-preserved lib-recall");
      context.host.append(layout);layout.append(source,native);UI.mount("memory-page",source);state.mounted=true;state.native=content;
      content.append(note("Whole retained native packets and receipts preserve their original cut, standing, voices and exclusions. Current admission and eligibility are unobserved. Source recall and external review confer no native promotion."));
      const retained=el("div","lib-native-retained");content.append(retained);state.retained=retained;
      get("retrieval-heading").textContent="Source recall";
    }
    get("memory-page").hidden=false;get("effort-operation-controls").hidden=false;
    const runs=(typeof allRuns !== "undefined" ? allRuns : []).filter(x=>x.backend === "opermem-reviewed" && (!scope().effort_root || x.correspondence?.effort_root===scope().effort_root));
    const signature=JSON.stringify([key,runs.map(x=>[x.run_id,x.state,x.application?.configuration?.store_id])]);
    if (state.signature===signature) return;state.signature=signature;
    if(state.key!==key){state.retained.replaceChildren();state.key=key;}
    const old=new Map([...state.retained.children].map(x=>[x.dataset.runId,x]));
    const retainedIds=new Set(runs.map(run=>run.run_id));
    for(const [id,item] of old)if(!retainedIds.has(id)){item.remove();old.delete(id);}
    let next=state.retained.firstElementChild;
    for(const run of runs){
      let item=old.get(run.run_id);old.delete(run.run_id);
      if(!item){
        item=el("article","lib-native-record");item.dataset.runId=run.run_id;
        item.append(el("strong","",run.goal || run.run_id),el("p","lib-mono",`Effort ${run.correspondence.effort_root} · execution ${run.correspondence.execution_id}`));
        const contents=el("div"), disclosure=el("details","lib-source");disclosure.append(el("summary","","Inspect original native packets & receipt"),contents);item.append(disclosure);
        disclosure.addEventListener("toggle",()=>{if(disclosure.open)inspectNativeRecord(item,run,key);});
      }
      if(item.querySelector("details").open && item.dataset.loadedState!==run.state)inspectNativeRecord(item,run,key);
      if(item!==next)state.retained.insertBefore(item,next);
      next=item.nextElementSibling;
    }
    for(const item of old.values())item.remove();
    if(!runs.length){state.retained.replaceChildren();placeholder(state.retained,"No retained reviewed memory in this scope","Select an effort and launch a reviewed inquiry with an explicitly registered backing. Browsing does not start native memory.");}
  }
  async function inspectNativeRecord(item,run,key) {
    if(item.dataset.loading)return;item.dataset.loading="true";
    const version=typeof operationVersion !== "undefined" ? operationVersion : 0,contents=item.querySelector("details").lastChild;
    try {
      const detail=await fetchJSON(scopedURL(`/api/runs/${encodeURIComponent(run.run_id)}`,scope()));
      if(key!==scopeKey() || !item.isConnected || (typeof operationVersion !== "undefined" && version!==operationVersion))return;
      const rows=[["Original operation and backing",{operation:detail.preparation.operation,backing:detail.preparation.store_ref.directory,native_disposition:detail.application.native.disposition,current_native_eligibility:"unobserved"}],
        ["Whole original context: cut, packets, voices, exclusions",detail.correspondence.native_link],
        ["Retained native receipt",detail.application.native.receipt],
        ["Original evidence and backing identity",{host_sources:detail.preparation.host_sources,native_store_identity:detail.correspondence.native_store_identity}]];
      for(const [label,value] of rows){let record=[...contents.children].find(x=>x.dataset.key===label);if(!record){record=el("details","lib-source");record.dataset.key=label;record.append(el("summary","",label),el("pre"));contents.append(record);}const text=JSON.stringify(value ?? null,null,2);if(record.lastChild.textContent!==text)record.lastChild.textContent=text;}
      if(!contents.querySelector("button"))contents.append(action("Investigate original execution",()=>{if(key===scopeKey()){selectRun(run.run_id);UI.navigate("executions");}}));
      item.dataset.loadedState=detail.status.state;
    }catch(failure){if(key===scopeKey() && item.isConnected){let error=contents.querySelector(".lib-note");if(!error){error=note("");contents.append(error);}error.textContent=`Retained evidence unavailable: ${failure.message}`;}}
    finally{delete item.dataset.loading;}
  }
  function usage(context) {
    const state = base(context), selection=scope();
    const sessions=(context.snapshot?.sessions || UI.snapshot().sessions || []).filter(row=>!selection.effort_root || row.effort_root===selection.effort_root);
    const signature = JSON.stringify([scopeKey(),sessions.map(row=>[row.id,row.model,row.target])]); if (signature === state.signature) return; state.signature=signature;clear(context.host);scopeToolbar(context.host);
    const card = panel("Token metrics","Native accounting coverage"), content=body(card);context.host.append(card);
    const metrics=el("div","lib-metrics");for(const name of ["Input tokens","Output tokens","Cache reads","Cost"]){const metric=el("div","lib-metric");metric.append(el("span","",name),el("strong","","Unknown"));metrics.append(metric);}content.append(metrics,note("The current observation API does not expose native token or cost accounting."));
    content.append(note("Structured execution accounting is not displayed here."));
    const list=panel("Exact session coverage","Retained targets"), listBody=body(list);context.host.append(list);
    for(const session of sessions){const row=el("div","lib-runtime-row");row.append(el("span","lib-mono",session.target ? `${session.target.ordinal} · ${session.target.instantiation}/${session.target.session}` : session.id),el("span","",session.model || "Model unknown"),UI.badge("Accounting unknown",""));listBody.append(row);}
    if (!sessions.length) placeholder(listBody,"No retained session observations","Usage remains unknown until native accounting is exposed.");
  }
  for (const route of Object.keys(titles)) UI.register(route, context => {
    if (context.route === "runtime") return runtime(context);
    if (["models","configuration"].includes(route)) return configured(context);
    if (["disciplines","roles","prompts"].includes(route)) return catalogue(context);
    if (route === "executions") return executions(context);
    if (route === "artifacts") return artifacts(context);
    if (route === "memory") return memory(context);
    if (route === "usage") return usage(context);
    if (route === "new-work") return mounts(context,["new-page"]);
    if (route === "purposes") {const state=mounts(context,["purposes-page"]);if(!state.loaded){state.loaded=true;if(typeof loadPurposes === "function") loadPurposes();}}
  });
  document.addEventListener("noetic:configuration",()=>{const host=get("shell-content");if(host && ["models","configuration"].includes(host.dataset.route)) UI.refresh();});
  document.addEventListener("noetic:runs",()=>{const host=get("shell-content");if(host && ["runtime","artifacts","executions","usage","memory"].includes(host.dataset.route)) UI.refresh();});
  document.addEventListener("noetic:run-detail",()=>{const host=get("shell-content");if(host && ["artifacts","executions"].includes(host.dataset.route)) UI.refresh();});
})();
