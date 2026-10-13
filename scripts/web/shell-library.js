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
  const views = {}, catalogues = new Map(), costDrafts = new Map();
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
    if (host.querySelector("#cost-estimation-skill")) views.usage?.costSkill?.capture();
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
      views[route] = {host, key:null, signature:null,tab:views[route]?.tab};
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
      tabs(host, [["definitions","Definitions",definitions.length],["instances","Instances",instances.length],["observations","Observations",typeof allRuns !== "undefined" ? allRuns.length : 0]], mode, id => {views[route].tab = id; renderCatalogue(context, data);});
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
      if(chosen.backend === "opermem-reviewed"){content.append(note("Independent worker and reviewer. Scoped GUI editors include Question, Insight, Formulation, Reflection, Conditional structure, Checking and Judgment. Other operations retain native capacity; inspect the operation selector for current editor availability and native prerequisites. An explicitly registered backing and native prerequisites remain required; editor availability does not establish admission."));details(content,"Fourteen native operation prerequisites",chosen.operations);}
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
    const hasNative=row=>Boolean(row.native_session_file), reserved=row=>!hasNative(row) && !row.target && Boolean(row.effort_root || row.identity_origin === "ordinal-reserved");
    const native=sessions.filter(hasNative), reservations=sessions.filter(reserved), unobserved=sessions.filter(row=>!hasNative(row) && !reserved(row));
    const signature = JSON.stringify([scopeKey(),typeof allRuns !== "undefined" ? allRuns.length : 0,sessions.map(row => [row.id,row.target,row.status,row.model,row.updated_at,row.error,row.native_session_file,row.identity_origin,row.effort_root])]);
    if (state.signature === signature) return; state.signature = signature;
    const diagnostics = get("diagnostics-page"); if (diagnostics && context.host.contains(diagnostics)) get("legacy-storage").append(diagnostics);
    clear(context.host);
    scopeToolbar(context.host);
    const metrics = el("div", "lib-metrics");
    for (const [name,count] of [["Retained native contexts",native.length],["Startup reservations",reservations.length],["Running native contexts",native.filter(row=>row.status === "running").length],["Executions",typeof allRuns !== "undefined" ? allRuns.length : 0],...(unobserved.length?[["Native context unobserved",unobserved.length]]:[])]) { const card = el("div", "panel lib-metric"); card.append(el("span", "", name),el("strong", "", String(count))); metrics.append(card); } context.host.append(metrics);
    const layout = el("div", "lib-catalogue-layout"), card = panel("Native contexts & startup observations", "Recorded backing and exact inspection"); layout.append(card); context.host.append(layout);
    const content = body(card);
    for (const [group,rows] of [["Retained native contexts",native],["Startup reservations",reservations],["Native context unobserved",unobserved]]) {
     if (rows.length) content.append(el("h3", "", `${group} · ${rows.length}`));
     for (const session of rows) {
      const row = el("article", "lib-runtime-row"), text = el("div");
      const target = session.target || {};
      const identity=reserved(session)?`${session.ordinal || session.id} · Reserved position · native context unobserved`:target.ordinal?`${target.ordinal} · context ${target.instantiation}/${target.session}${hasNative(session)?'':' · native context unobserved'}`:hasNative(session)?`${session.ordinal || session.id} · Original namespace · unadopted`:`${session.ordinal || session.id} · Native context unobserved`;
      text.append(el("span", "lib-mono", identity),el("strong", "", session.title || "Untitled record"),el("small", "", `${session.model || "Model unknown"} · ${session.status || "Status unknown"}`));
      row.append(text, action(hasNative(session)?"Inspect / control":reserved(session)?"Inspect startup observation":"Inspect retained observation", async () => { if (window.NoeticSessions) await window.NoeticSessions.open(session.target ? {...session.target,effort_root:session.effort_root} : {id:session.id}); UI.navigate("agentics"); })); content.append(row);
     }
    }
    if (!sessions.length) placeholder(content,"No retained runtime observations",selection.effort_root ? "Open a conversation in this effort to begin native work." : "Choose an effort or create one, then open a conversation to begin native work.");
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
      content.append(note("Provider configuration is maintained outside this interface."));
      const availability = panel("Selection and qualification", "Dispatch resolution"), availabilityBody = body(availability); host.append(availability);
      availabilityBody.append(note(config.profile_notice || "Configured identity does not establish authentication or availability."));
      availabilityBody.append(el("h3", "", "Structured work"),note("Model and thinking choices are set in structured work's Model settings. Opening the form does not change provider settings or running sessions. New work supports an explicit client/model override."),action("Open structured work",()=>openWork()));
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
    content.append(note("Explicit overrides → NOETIC_LOCAL_* environment → optional NOETIC_LOCAL_CONFIG → defaults.")); values(content,{namespace:config.namespace_path,telos:config.telos_database}); content.append(note("This interface inspects configuration. Set execution overrides in New work."),action("Open structured work",()=>openWork())); details(content,"Full observed settings",config);
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
      const row = action("",()=>{ const select=get("artifact-select"); select.value = artifact.id; select.dispatchEvent(new Event("change",{bubbles:true})); if (typeof switchView === "function") switchView("controller"); revealArtifact(artifact.id); });row.className = "lib-run-row";
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
  function revealArtifact(id) {
    const select = get("artifact-select"), content = get("artifact-content");
    if (!select || !content || UI.route() !== "artifacts" || select.value !== id || !content.isConnected) return;
    const key = scopeKey(), runId = (typeof selectedDetail !== "undefined" && selectedDetail?.status?.run_id) || null;
    requestAnimationFrame(()=>{
      if (UI.route() !== "artifacts" || key !== scopeKey() || runId !== ((typeof selectedDetail !== "undefined" && selectedDetail?.status?.run_id) || null) || select.value !== id || !content.isConnected) return;
      const rect = select.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) return;
      if (rect.top < 0 || rect.bottom > innerHeight || content.getBoundingClientRect().top >= innerHeight) select.scrollIntoView({block:"start"});
      content.focus({preventScroll:true});
    });
  }
  function memory(context) {
    const state = base(context), key = scopeKey();
    if (!state.mounted) {
      scopeToolbar(context.host);
      const layout=el("div","lib-catalogue-layout"), native=panel("Retained native memory","Opermem authority"), content=body(native), source=el("div","lib-preserved lib-recall");
      context.host.append(layout);layout.append(source,native);UI.mount("memory-page",source);state.mounted=true;state.native=content;
      content.append(note("Whole retained native packets and receipts preserve their original cut, standing, voices and exclusions. Current admission and eligibility are unobserved. Source recall and external review confer no native promotion."));
      const retained=el("div","lib-native-retained");content.append(retained);state.retained=retained;state.entry=el("div","lib-actions");content.append(state.entry);
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
    if(!runs.length){state.retained.replaceChildren();placeholder(state.retained,"No retained reviewed memory in this scope",scope().effort_root?"Prepare a Question inquiry in this effort with an explicitly registered backing. Other native operations retain their stated editor limitations.":"Choose an effort to prepare a Question inquiry with an explicitly registered backing. Browsing does not start native memory.");}
    state.entry.replaceChildren();
    if(scope().effort_root){
      const prepare=backing=>{if(key!==scopeKey())return;openWork("opermem-reviewed");const operation=get("reviewed-operation");operation.value="question";operation.dispatchEvent(new Event("change",{bubbles:true}));if(backing){const directory=get("reviewed-directory");directory.closest("details").open=true;directory.focus();}};
      state.entry.append(action("Prepare Question inquiry",()=>prepare(false)),action("Manage backings",()=>prepare(true)));
    }else state.entry.append(action("Choose effort",()=>UI.navigate("workspaces")));
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
  function costSkill(content, selection, metric, valid) {
    const section=el("section","lib-cost-skill");section.id="cost-estimation-skill";
    const editor=el("details","lib-source lib-cost-editor");editor.append(el("summary","","Edit cost factors and run skill"));
    const heading=el("div","lib-cost-heading"),link=el("a","","Cost estimation skill");link.href="#cost-estimation-skill";
    link.addEventListener("click",event=>{event.preventDefault();editor.open=true;editor.scrollIntoView({block:"start"});});heading.append(link,el("span","lib-mono","noetic:cost-estimate"));
    const edit=el("a","lib-cost-open","Edit cost factors");edit.href="#cost-estimation-skill";edit.addEventListener("click",event=>{event.preventDefault();editor.open=true;editor.scrollIntoView({block:"start"});});metric.value.parentNode.append(edit);
    const summary=note("Not calculated. Choose a billing basis and supply its factors.");summary.id="cost-estimate-summary";
    const sourceStatus=note("No retrieved rate source yet.");sourceStatus.id="cost-source-status";
    const status=note("Inspecting the maintained application skill.");status.id="cost-skill-status";status.setAttribute("role","status");
    const form=el("form","lib-cost-form"),fields=new Map(),dirty=new Set();let inspection=null,pending=false,restored=false,revisionConflict=false,draftRevision=null,newProfile=false;
    const access=typeof accessVersion === "number" ? accessVersion : 0;
    const draftKey=()=>inspection?.namespace ? JSON.stringify([access,inspection.namespace,selection]) : null;
    function capture(){const key=draftKey();if(!key)return;if(!dirty.size){costDrafts.delete(key);return;}costDrafts.set(key,{values:Object.fromEntries([...fields].map(([name,input])=>[name,input.value])),dirty:[...dirty],profile:profiles.value,revision:draftRevision ?? inspection.revision,newProfile,refresh:refresh.checked,open:editor.open});}
    const identity=el("div","lib-cost-fields");
    function field(parent,name,label,options){const wrapper=el("div","lib-cost-field"),caption=el("label","",label),input=el(options?"select":"input");input.id=`cost-${name.replaceAll(".","-").replaceAll("_","-")}`;caption.htmlFor=input.id;
      if(options)for(const [value,text]of options){const option=el("option","",text);option.value=value;input.append(option);}else{input.type=name.includes(".")?"number":"text";if(input.type==="number"){input.min="0";input.step="any";}}
      if(["provider","model","currency"].includes(name))input.required=true;
      input.addEventListener("input",()=>{dirty.add(name);status.textContent="Unsaved cost factors. Run explicitly to save and recalculate.";capture();});input.addEventListener("change",()=>{dirty.add(name);status.textContent="Unsaved cost factors. Run explicitly to save and recalculate.";capture();});fields.set(name,input);wrapper.append(caption,input);parent.append(wrapper);return input;}
    field(identity,"provider","Provider");field(identity,"model","Model");field(identity,"billing_basis","Billing basis",[["unknown","Unknown"],["api","API-equivalent reference"],["subscription","Subscription allocation"],["local","Local energy"]]);field(identity,"currency","Currency").value="USD";
    const profiles=el("select"),profilesLabel=el("label","","Saved cost profile");profiles.id="cost-profile";profilesLabel.htmlFor=profiles.id;
    const rates=el("fieldset");rates.append(el("legend","","User rate overrides · currency per 1M tokens"));const rateFields=el("div","lib-cost-fields");rates.append(rateFields);
    for(const [name,label]of [["input","Input rate / million"],["output","Output rate / million"],["cache_read","Cache read rate / million"],["cache_write","Cache write rate / million"]])field(rateFields,`overrides.${name}`,label);
    const factors=el("fieldset");factors.append(el("legend","","Explicit estimate factors"));const factorFields=el("div","lib-cost-fields");factors.append(factorFields);
    for(const [name,label]of [["input_multiplier","Input multiplier"],["output_multiplier","Output multiplier"],["allocation_cost","Subscription allocation cost"],["runtime_seconds","Measured runtime seconds"],["power_watts","Power watts"],["electricity_per_kwh","Electricity per kWh"]])field(factorFields,`factors.${name}`,label);
    function basisFields(){const basis=fields.get("billing_basis").value;rates.hidden=basis!=="api";factors.hidden=basis==="unknown";for(const [name,input]of fields){if(!name.startsWith("factors."))continue;const allowed=basis==="api"?["input_multiplier","output_multiplier"]:basis==="subscription"?["allocation_cost"]:basis==="local"?["runtime_seconds","power_watts","electricity_per_kwh"]:[];input.parentNode.hidden=!allowed.includes(name.split(".")[1]);}}
    fields.get("billing_basis").addEventListener("change",basisFields);basisFields();
    const refreshLabel=el("label","lib-cost-refresh"),refresh=el("input");refresh.type="checkbox";refreshLabel.append(refresh,document.createTextNode("Refresh official reference rates"));
    const run=el("button","primary-button","Run cost estimation skill");run.type="submit";run.disabled=true;
    const reload=action("Refresh saved estimates",()=>load(true));
    const evidence=el("details","lib-source");evidence.append(el("summary","","Skill, assumptions, saved factors and receipt"),el("pre"));
    form.append(profilesLabel,profiles,identity,note("Estimates do not establish actual billed cost. Untouched fields preserve saved values; clearing an edited field removes that named override."),rates,factors,refreshLabel,run);
    editor.append(form,evidence);section.append(heading,summary,sourceStatus,status,reload,editor);content.append(section);
    const usable=()=>section.isConnected&&valid();
    function chosen(){return inspection?.profiles?.find(profile=>profile.id===profiles.value);}
    function showEstimate(profile){const estimate=profile?.estimate;if(typeof estimate?.amount==="number"&&Number.isFinite(estimate.amount)){metric.value.textContent=`${estimate.currency} ${estimate.amount.toFixed(6)}${estimate.state==="partial"?" (partial)":""}`;summary.textContent=`${estimate.standing||"Estimated cost"} · ${estimate.currency} ${estimate.amount.toFixed(6)} · ${estimate.covered_records??"unreported"} covered records${estimate.matched_records!=null?` of ${estimate.matched_records} matching records`:""}. ${estimate.missing?.length?`Missing: ${estimate.missing.join(", ")}.`:""}`;}else{metric.value.textContent="Unknown";summary.textContent=`Unknown estimate. ${estimate?.missing?.length?`Missing: ${estimate.missing.join(", ")}.`:"Choose a provider/model, billing basis and its factors."}`;}metric.coverage.textContent=estimate?.billing_basis==="api"?"API-equivalent reference · not an invoice":estimate?.billing_basis==="local"?"User local electricity estimate":estimate?.billing_basis==="subscription"?"User subscription allocation":"Saved factors · not an invoice";
      const fetched=profile?.fetched;sourceStatus.textContent=fetched?`Rate source ${fetched.url} · retrieved ${fetched.retrieved_at}. User overrides remain separate.`:"No retrieved rate source; manual overrides/factors may apply.";const text=JSON.stringify({skill:inspection?.skill,namespace:inspection?.namespace,selection:inspection?.selection,revision:inspection?.revision,profile,receipt:profile?.receipt||inspection?.receipt},null,2);if(evidence.lastChild.textContent!==text)evidence.lastChild.textContent=text;}
    function populate(profile){if(!profile){for(const [name,input]of fields)input.value=name==="currency"?"USD":name==="billing_basis"?"unknown":"";dirty.clear();basisFields();showEstimate(null);return;}for(const [name,input]of fields){const [group,key]=name.split(".");input.value=String(key?profile[group]?.[key]??"":profile[name]??"");}dirty.clear();basisFields();showEstimate(profile);}
    profiles.addEventListener("change",()=>{dirty.clear();draftRevision=inspection?.revision;revisionConflict=false;newProfile=!profiles.value;populate(chosen());if(newProfile){dirty.add("provider");dirty.add("model");refresh.checked=false;status.textContent="New cost profile. Enter its identity and factors; no prior profile values are copied.";}capture();});
    editor.addEventListener("toggle",capture);refresh.addEventListener("change",capture);
    function apply(result,save){inspection=result;const selected=save?result.receipt?.profile_id:profiles.value,signature=JSON.stringify((result.profiles||[]).map(p=>[p.id,p.provider,p.model,p.billing_basis,p.currency]));if(profiles.dataset.signature!==signature){profiles.dataset.signature=signature;const empty=el("option","","New cost profile");empty.value="";profiles.replaceChildren(empty,...(result.profiles||[]).map(profile=>{const option=el("option","",`${profile.provider} / ${profile.model} · ${profile.billing_basis} · ${profile.currency}`);option.value=profile.id;return option;}));}
      profiles.value=selected&&result.profiles?.some(p=>p.id===selected)?selected:!newProfile&&result.profiles?.length===1?result.profiles[0].id:"";if(!dirty.size)populate(chosen());else showEstimate(chosen());if(!chosen())showEstimate(null);run.disabled=!Number.isInteger(result.revision);}
    async function load(explicit=false){if(pending)return;pending=true;try{const result=await fetchJSON(scopedURL("/api/skills/cost-estimate",selection));if(!usable())return;if(inspection?.namespace && inspection.namespace!==result.namespace){capture();dirty.clear();draftRevision=null;revisionConflict=false;restored=false;newProfile=false;profiles.value="";for(const [name,input]of fields)input.value=name==="currency"?"USD":name==="billing_basis"?"unknown":"";refresh.checked=false;basisFields();}apply(result,false);if(!restored){restored=true;const draft=costDrafts.get(draftKey());if(draft){profiles.value=(result.profiles||[]).some(p=>p.id===draft.profile)?draft.profile:"";for(const [name,value] of Object.entries(draft.values))if(fields.has(name))fields.get(name).value=value;for(const name of draft.dirty)dirty.add(name);newProfile=Boolean(draft.newProfile);refresh.checked=draft.refresh;editor.open=draft.open;basisFields();showEstimate(chosen());draftRevision=draft.revision;revisionConflict=draft.revision!==result.revision;}}if(explicit){revisionConflict=false;draftRevision=result.revision;}run.disabled=revisionConflict||!Number.isInteger(result.revision);status.textContent=revisionConflict?"Unsaved factors preserved; saved revision changed. Refresh saved estimates explicitly before running this draft.":dirty.size?"Unsaved cost factors preserved. Run explicitly to save and recalculate.":"Skill inspected locally. Run explicitly to save factors, refresh selected rates and recalculate.";capture();}catch(failure){if(usable())status.textContent=`Cost skill observation unavailable: ${failure.message}. Unsaved factors are preserved.`;}finally{pending=false;}}
    form.addEventListener("submit",async event=>{event.preventDefault();if(pending||revisionConflict||!Number.isInteger(inspection?.revision)||!usable())return;const profile=Object.fromEntries(["provider","model","billing_basis","currency"].map(name=>[name,fields.get(name).value]));profile.overrides={};profile.factors={};for(const name of dirty){const [group,key]=name.split(".");if(!key)continue;const value=fields.get(name).value;profile[group][key]=value===""?null:Number(value);}
      pending=true;run.disabled=true;status.textContent="Running deterministic cost estimation skill…";
      try{const result=await fetchJSON("/api/skills/cost-estimate/execute",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...selection,expected_revision:inspection.revision,profile,refresh_prices:refresh.checked})});if(!usable())return;dirty.clear();capture();draftRevision=result.revision;newProfile=false;apply(result,true);status.textContent=`Cost factors ${result.factor_save||"save outcome unreported"}; rate refresh ${result.refresh?.state||"unreported"}.${result.refresh?.error?` ${result.refresh.error}`:""} Estimate recalculated separately from observed usage.`;}catch(failure){if(usable())status.textContent=`Cost skill run unavailable: ${failure.message}. Unsaved factors are preserved; refresh saved estimates before retrying a revision conflict.`;}finally{pending=false;if(usable())run.disabled=revisionConflict||!Number.isInteger(inspection?.revision);}});
    load();return {capture,observe(projection){const pairs=[...new Map((projection.rows||[]).filter(r=>r.provider&&r.model).map(r=>[`${r.provider}\0${r.model}`,r])).values()];if(pairs.length===1){if(!fields.get("provider").value&&!dirty.has("provider"))fields.get("provider").value=pairs[0].provider;if(!fields.get("model").value&&!dirty.has("model"))fields.get("model").value=pairs[0].model;}}};
  }
  async function usage(context, explicitRefresh = false) {
    const state=base(context),selection=scope(),key=scopeKey(),host=context.host;
    if(state.key!==key||!state.metrics){
      state.key=key;state.generation=(state.generation||0)+1;state.pending=false;state.data=null;state.rows=new Map();clear(host);scopeToolbar(host);
      const card=panel("Token metrics","Native Pi adapter accounting"),content=body(card);host.append(card);
      state.metrics=new Map();const metrics=el("div","lib-metrics lib-usage-metrics");
      for(const [field,label] of [["totalInput","Input incl. cache"],["output","Output tokens"],["cacheRead","Cache reads"],["estimate","Estimated cost"]]){
        const metric=el("div","lib-metric");metric.dataset.field=field;const value=el("strong","",field==="estimate"?"Not calculated":"Unknown"),coverage=el("small");metric.append(el("span","",label),value,coverage);metrics.append(metric);state.metrics.set(field,{value,coverage});
      }
      state.observation=note("Loading accounting observations.");state.observation.id="usage-observation";state.observation.setAttribute("role","status");
      state.coverage=note("");state.coverage.id="usage-coverage";state.cache=note("");state.cache.id="usage-cache-share";
      state.notice=note("Adapter-reported usage; raw provider cache-field presence is unknown. A normalized zero does not establish provider applicability or a zero bill.");state.notice.id="usage-notice";
      const refresh=action("Refresh accounting",()=>{if(active(host,"usage",key))usage(context,true);});
      content.append(metrics,state.observation,refresh,state.coverage,state.cache,state.notice,note("Recorded adapter estimates are available in source details; currency and billing basis are not established here."),note("Structured execution accounting is not displayed here."));
      const source=el("details","lib-source");source.append(el("summary","","Accounting source and coverage"),el("pre"));content.append(source);state.source=source.lastChild;
      state.costSkill=costSkill(content,selection,state.metrics.get("estimate"),()=>views.usage===state&&active(host,"usage",key));
      const list=panel("Exact session coverage","Retained native targets");state.list=body(list);host.append(list);
    }
    if(state.pending)return;state.pending=true;
    const generation=state.generation,valid=()=>views.usage===state&&state.generation===generation&&active(host,"usage",key);
    if(!state.data||explicitRefresh)state.observation.textContent=state.data?"Refreshing accounting; showing last observed records.":"Loading accounting observations; no accounting observed yet.";
    const slow=setTimeout(()=>{if(valid()&&state.pending&&state.data)state.observation.textContent="Accounting refresh is taking longer; showing last observed records.";},1500);
    try{
      const projection=await fetchJSON(scopedURL("/api/usage",selection));if(!valid())return;state.data=projection;state.costSkill.observe(projection);
      const coverage=projection.coverage||{},fields=coverage.fields||{},totals=projection.totals||{};
      for(const [field,metric] of state.metrics){if(field==="estimate")continue;const value=totals[field],known=fields[field]?.known||0,missing=fields[field]?.missing||0;metric.value.textContent=typeof value==="number"&&Number.isFinite(value)?value.toLocaleString("en-US"):"Unknown";metric.coverage.textContent=`${known} known · ${missing} missing records`;}
      state.observation.textContent=`Accounting observed ${projection.observed_at||"at an unreported time"}.`;
      state.coverage.textContent=`${coverage.usage_records||0} accounting observations of ${coverage.records||0} completed assistant records across ${coverage.sessions||0} retained sessions · ${coverage.duplicates||0} repeats excluded.`;
      const share=projection.cache_read_share;state.cache.textContent=typeof share==="number"&&Number.isFinite(share)?`${(share*100).toFixed(1)}% cache reads of reported total input (input + read + write): ${projection.cache_share_input_tokens} tokens over ${projection.cache_share_records} compatible records.`:"Cache share unavailable: compatible input + read + write denominator is zero or unobserved.";
      const sourceText=JSON.stringify(projection,null,2);if(state.source.textContent!==sourceText)state.source.textContent=sourceText;
      const retained=new Map(),rows=(projection.sessions||[]).map(session=>{
        const row=state.rows.get(session.id)||el("article","lib-usage-session");row.dataset.usageSession=session.id;
        if(!row.children.length){row.append(el("strong","lib-mono"),el("p","lib-note"));const source=el("details","lib-source");source.append(el("summary","","Exact accounting records and binding"),el("pre"));row.append(source);}
        const target=session.target,original=!target&&!session.effort_root;
        row.firstChild.textContent=target?`${target.ordinal} · instantiation ${target.instantiation} / session ${target.session}`:original?`Original namespace · unadopted · ${session.original_ordinal||session.ordinal||"ordinal unobserved"} · ${session.id}`:`Position ${session.ordinal||"unobserved"} · ${session.id}`;
        row.children[1].textContent=`${session.usage_records||0} accounting observations · ${session.record_count||0} completed assistant records${session.effort_root?` · effort ${session.effort_root}`:" · no declared effort"}`;
        const sourceText=JSON.stringify({session,records:(projection.rows||[]).filter(record=>record.session_id===session.id)},null,2),pre=row.querySelector("pre");if(pre.textContent!==sourceText)pre.textContent=sourceText;retained.set(session.id,row);return row;
      });state.rows=retained;
      for(const child of [...state.list.children])if(!rows.includes(child))child.remove();rows.forEach((row,index)=>{if(state.list.children[index]!==row)state.list.insertBefore(row,state.list.children[index]||null);});
      if(!rows.length)placeholder(state.list,"No retained native session observations","No accounting has been observed in this scope; absence is not zero usage or free service.");
    }catch(failure){if(valid())state.observation.textContent=`Accounting observation unavailable: ${failure.message}.${state.data?" Showing last observed accounting.":" No accounting observed for this scope."}`;}
    finally{clearTimeout(slow);if(valid())state.pending=false;}
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

  // New-project folder default (O03): in create mode with no explicitly set
  // folder, the visible folder is suggested from the actual configured Projects
  // location plus the project name as typed. Any explicit folder edit —
  // including clearing it — is authoritative; name/location edits then never
  // overwrite it, and existing-project mode never derives a folder.
  (() => {
    const ids = ["developer-project-mode", "developer-project-name", "developer-workspace", "developer-projects-root"];
    if (!ids.every(id => get(id)) || get("developer-project-path-status")) return;
    const folderInput = get("developer-workspace");
    const status = document.createElement("p");
    status.id = "developer-project-path-status";
    status.className = "evidence-note";
    status.setAttribute("role", "status");
    folderInput.after(status);
    // A restored nonempty folder is already a deliberate manual value.
    let manual = folderInput.value !== "";
    const isCreate = () => get("developer-project-mode").value === "create";
    const validName = raw => raw.trim() !== "" && raw !== "." && raw !== ".." && !/[/\\]/.test(raw);
    // Generated folder updates must reach the existing private persistence
    // (bound to the field's input/change listeners) without counting as an
    // explicit manual edit or recursing into this module's own handler.
    const setFolder = value => {
      folderInput.value = value;
      folderInput.dispatchEvent(new Event("input", {bubbles: true}));
    };
    const update = () => {
      if (!isCreate() || manual) {
        status.textContent = manual ? "Folder set explicitly; project name and Projects location edits will not change it."
          : "Open an existing project by folder or name.";
        return;
      }
      const rawName = get("developer-project-name").value;
      // Surrounding whitespace is insignificant exactly as in the existing
      // create POST; a bare "/" root is a real location, not an absent one.
      const rawRoot = get("developer-projects-root").value.trim();
      const root = rawRoot === "/" ? "/" : rawRoot.replace(/\/+$/, "");
      if (root !== "" && !root.startsWith("/") && !root.startsWith("~")) {
        setFolder("");
        status.textContent = "Projects location must be absolute or a ~ home form; a relative Projects location is not supported, so no folder is suggested. Set the folder explicitly to override.";
        return;
      }
      if (!validName(rawName)) {
        setFolder("");
        status.textContent = rawName.trim() === ""
          ? "Project folder appears once a project name is set; or set the folder explicitly."
          : "This project name cannot form a folder (a name must not be '.' or '..' or contain path separators); set the folder explicitly if intended.";
        return;
      }
      const suggested = root === "" ? ""
        : root.endsWith("/") ? root + rawName : root + "/" + rawName;
      setFolder(suggested);
      status.textContent = suggested === ""
        ? "Set a Projects location to suggest a folder, or set the folder explicitly."
        : "Suggested from the current Projects location and project name; edit the folder to override.";
    };
    for (const id of ["developer-project-name", "developer-projects-root"]) {
      for (const event of ["input", "change"]) get(id).addEventListener(event, () => { if (!manual && isCreate()) update(); });
    }
    get("developer-project-mode").addEventListener("change", () => {
      // A folder already shown in another mode stays deliberate.
      if (folderInput.value !== "") manual = true;
      update();
    });
    folderInput.addEventListener("input", event => {
      // Only genuine user edits make the folder authoritative; generated
      // suggestion writes dispatch untrusted input events for persistence.
      if (!event.isTrusted) return;
      manual = true;
      update();
    });
    // An asynchronous refresh may fill an empty Projects location from the API.
    document.addEventListener("noetic:sessions", () => { if (!manual && isCreate()) update(); });
    update();
  })();
})();
