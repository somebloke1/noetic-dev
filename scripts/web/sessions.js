"use strict";

(() => {
  let saved = {};
  try { saved = JSON.parse(sessionStorage.getItem("noetic-developer-view") || "{}"); } catch (_) {}
  let selected = saved.selected && typeof saved.selected === "object" ? saved.selected : null;
  let effort = saved.effort || null;
  let positions = [], historyRecords = [], applicationEvents = [];
  let historyObservation = {status:"unobserved",observed:false,error:null};
  let historyCache = null, returnsCache = null;
  let observeReturns = false;
  let newConversation = Boolean(saved.newConversation);
  let applicationHistory = Boolean(saved.applicationHistory);
  let projectBrowsing = Boolean(saved.projectBrowsing && !selected && !applicationHistory), projectPath = projectBrowsing ? saved.projectPath || null : null, returnContext = null;
  const drafts = saved.drafts && typeof saved.drafts === "object" ? saved.drafts : {};
  let selectionVersion = 0;
  let promptRevision = 0;
  let allSessions = [];
  let detail = null;
  let events = [];
  let cursor = 0;
  let pending = false;
  let actionPending = false;
  let observationError = false;
  const fields = ["developer-projects-root", "developer-workspace", "developer-project-name", "developer-project-mode", "developer-model", "developer-thinking", "developer-prompt", "developer-mode"];
  const persist = () => {
    drafts[key(selected)] = $("developer-prompt").value;
    const value = {selected, effort, newConversation, applicationHistory, projectBrowsing, projectPath, drafts, fields: Object.fromEntries(fields.map(id => [id, $(id).value]))};
    try { sessionStorage.setItem("noetic-developer-view", JSON.stringify(value)); } catch (_) {}
  };
  for (const id of fields) {
    if (typeof saved.fields?.[id] === "string") $(id).value = saved.fields[id];
    $(id).addEventListener("input", () => { if (id === "developer-prompt") ++promptRevision; persist(); });
    $(id).addEventListener("change", persist);
  }
  const state = () => JSON.parse(JSON.stringify({positions, sessions:allSessions, selected, effort, detail,
    history:historyRecords, historyObservation, events, newConversation, applicationHistory, projectBrowsing, projectPath, returnContext, applicationEvents, observationError}));
  const notify = () => document.dispatchEvent(new CustomEvent("noetic:sessions", {detail:state()}));
  const active = () => operatorToken && !$('private-workspace').hidden;
  const post = (path, body = {}) => fetchJSON(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const key = target => target ? JSON.stringify(target) : "new";
  const address = target => target?.id && !target.ordinal ? target.id : target.ordinal;
  const scope = target => target?.effort_root ? {effort_root: target.effort_root,
    ...(target.instantiation ? {instantiation: target.instantiation, session: target.session} : {})} : {};
  const endpoint = (action, target = selected) => `/api/developer-sessions/${encodeURIComponent(address(target))}${action ? "/"+action : ""}`;
  const sessionTarget = item => item.target ? {...item.target, effort_root: item.effort_root} : {id: item.id, ...(item.effort_root ? {effort_root:item.effort_root} : {})};
  const exact = target => Boolean(target?.instantiation || target?.id);
  const same = (a,b) => key(a) === key(b);
  const query = values => new URLSearchParams(values).toString();
  async function pages(path, field, values = {}, valid = () => true, inspect = () => {}) {
    const rows = []; let after = Number(values.after || 0);
    while (valid()) {
      const result = await fetchJSON(`${path}?${query({...values, after, limit: field === "events" ? 500 : 100})}`);
      if (!valid()) return null;
      inspect(result);
      rows.push(...(result[field] || []));
      if (!(result[field]?.length) || !result.next_after || result.next_after <= after) return {result, rows};
      after = result.next_after;
    }
    return null;
  }
  async function historyPages(path, values, retained, cache, valid, reset) {
    const binding = JSON.stringify([path,values,accessVersion]);
    let append = Boolean(cache?.namespace_id && cache.binding === binding);
    const restart = Symbol("history namespace changed");
    for (let attempt=0;attempt<2;attempt++) {
      let namespace, first = true;
      try {
        const value = await pages(path,"records",{...values,after:append?cache.cursor:0},valid,result=>{
          const observed = typeof result.namespace_id === "string" && result.namespace_id ? result.namespace_id : null;
          if (first) {
            first = false; namespace = observed;
            if (append && namespace !== cache.namespace_id) { append=false; reset(); throw restart; }
          } else if (namespace !== observed) { reset(); throw new Error("History namespace changed during pagination; refresh to observe complete history."); }
        });
        if (!value) return null;
        return {rows:append ? retained.concat(value.rows) : value.rows,
          cache:namespace ? {binding,namespace_id:namespace,cursor:value.result.next_after || 0} : null};
      } catch (failure) {
        if (failure !== restart) throw failure;
      }
    }
    throw new Error("History namespace changed repeatedly; refresh to observe complete history.");
  }
  const content = (message) => typeof message?.content === "string" ? message.content :
    (Array.isArray(message?.content) ? message.content.filter(block => block.type === "text").map(block => block.text || "").join("\n") : "");
  const reservedSource = item => Boolean(item && !item.target && (item.identity_origin === "ordinal-reserved" || item.effort_root));
  const originalSource = item => Boolean(item && !reservedSource(item) && (item.identity_origin === "legacy-unadopted" || !item.target && !item.effort_root));
  const sourceQualifier = item => originalSource(item) ? " · original namespace · unadopted" : "";
  const ordinalSort = (a, b) => a.ordinal.localeCompare(b.ordinal, "en", {numeric: true});

  function safeLink(label, reference, session = detail?.session) {
    const external = /^https?:\/\//i.test(reference);
    if (!external && (!session || /^(?:[a-z][a-z0-9+.-]*:|#)/i.test(reference) && !/^\//.test(reference))) return node("span", label);
    const link = node("a", label);
    if (external) { link.href = reference; link.target = "_blank"; link.rel = "noopener noreferrer"; return link; }
    const location = /:(\d+)(?::\d+)?$/.exec(reference);
    const cleaned = reference.replace(/:\d+(?::\d+)?$/, "");
    const run = session.kind === "run";
    const prefix = run ? "workspace" : "developer";
    const target = sessionTarget(session), version = selectionVersion;
    link.href = run ? scopedURL(`/api/runs/${encodeURIComponent(session.id)}/project-file?path=${encodeURIComponent(cleaned)}`,session.selection || operationSelection()) : `${endpoint("file", target)}?${query({...scope(target), path: cleaned})}`;
    link.addEventListener("click", async event => {
      event.preventDefault();
      try {
        const result = await fetchJSON(link.getAttribute("href"));
        if ((!run && version !== selectionVersion) || (run && (session.viewVersion !== operationVersion || session.id !== selectedId))) return;
        const pre = $(`${prefix}-file-text`);
        const lines = location ? result.text.split("\n") : null;
        const index = lines ? Number(location[1]) - 1 : -1;
        error(run ? "action-error" : "developer-error", "");
        text(`${prefix}-file-path`, location ? `${result.path}:${location[1]}` : result.path);
        if (lines && index >= 0 && index < lines.length) {
          // Concatenated span text equals the returned source byte-for-byte; only the requested line is marked.
          const head = document.createElement("span"); head.textContent = lines.slice(0, index).join("\n") + (index ? "\n" : "");
          const mark = document.createElement("mark");
          const tail = document.createElement("span");
          const hasFollowingLine = index + 1 < lines.length;
          mark.textContent = lines[index] + (lines[index] === "" && hasFollowingLine ? "\n" : "");
          tail.textContent = (lines[index] !== "" && hasFollowingLine ? "\n" : "") + lines.slice(index + 1).join("\n");
          pre.replaceChildren(head, mark, tail);
          $(`${prefix}-file-view`).hidden = false;
          mark.scrollIntoView({block: "center"});
        } else {
          pre.textContent = result.text;
          $(`${prefix}-file-view`).hidden = false;
          if (lines) error(run ? "action-error" : "developer-error", `Line ${location[1]} is not present in ${cleaned}.`);
        }
        pre.focus({preventScroll: true});
      } catch (failure) { if (run ? session.viewVersion === operationVersion && session.id === selectedId : version === selectionVersion) error(run ? "action-error" : "developer-error", failure.message); }
    });
    return link;
  }

  function inline(textValue, session) {
    const holder = node("span"), pattern = /\[([^\]\n]+)\]\(([^\s)]+)\)|`([^`\n]+)`|\*\*([^*\n]+)\*\*|https?:\/\/[^\s<>]+/g;
    let start = 0;
    for (const match of textValue.matchAll(pattern)) {
      holder.append(document.createTextNode(textValue.slice(start, match.index)));
      if (match[1]) holder.append(safeLink(match[1], match[2], session));
      else if (match[3]) holder.append(node("code", match[3]));
      else if (match[4]) holder.append(node("strong", match[4]));
      else holder.append(safeLink(match[0], match[0].replace(/[.,;]$/, ""), session));
      start = match.index + match[0].length;
    }
    holder.append(document.createTextNode(textValue.slice(start))); return holder;
  }

  function markdown(value, session = detail?.session) {
    const holder = node("div", undefined, "developer-markdown");
    let code = null, list = null;
    for (const line of value.split("\n")) {
      if (/^\s*```/.test(line)) {
        if (code) { holder.append(node("pre", code.join("\n"))); code = null; }
        else code = [];
        list = null; continue;
      }
      if (code) { code.push(line); continue; }
      const heading = /^(#{1,6})\s+(.*)/.exec(line), bullet = /^\s*([-*]|(\d+)\.)\s+(.*)/.exec(line);
      if (heading) { const el = node(`h${Math.min(heading[1].length+2,6)}`); el.append(inline(heading[2], session)); holder.append(el); list = null; }
      else if (bullet) {
        const ordered = bullet[2] !== undefined;
        if (!list || list.tagName !== (ordered ? "OL" : "UL")) { list = node(ordered ? "ol" : "ul"); if (ordered) list.start = Number(bullet[2]); holder.append(list); }
        const el = node("li"); if (ordered) el.value = Number(bullet[2]);
        el.append(inline(bullet[3], session)); list.append(el);
      }
      else { list = null; if (line.trim()) { const el = node("p"); el.append(inline(line, session)); holder.append(el); } }
    }
    if (code) holder.append(node("pre", code.join("\n")));
    return holder;
  }
  window.NoeticRichText = markdown;

  let copySnapshot = null;
  const copyStatus = node("small"); copyStatus.id="developer-copy-status"; copyStatus.setAttribute("role","status");
  function controlIcon(kind="copy") {
    const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");
    for(const [name,value] of Object.entries({viewBox:"0 0 24 24",width:"16",height:"16",fill:"none",stroke:"currentColor","stroke-width":"1.6","stroke-linecap":"round","stroke-linejoin":"round","aria-hidden":"true",focusable:"false"}))svg.setAttribute(name,value);
    svg.innerHTML=({copy:'<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M15 5V4H4v11h1"/>',check:'<path d="m5 12 4 4L19 6"/>',stop:'<rect x="6" y="6" width="12" height="12" rx="1"/>',delegate:'<circle cx="6" cy="5" r="2"/><circle cx="18" cy="7" r="2"/><circle cx="18" cy="18" r="2"/><path d="M6 7v7a4 4 0 0 0 4 4h6M8 5h5a5 5 0 0 1 5 5"/>',close:'<path d="m6 6 12 12M18 6 6 18"/>',root:'<path d="M12 20V4m-6 6 6-6 6 6"/>'})[kind];return svg;
  }
  function copyControl(label, value) {
    const button=node("button",undefined,"noetic-copy");button.type="button";button.title=label;button.setAttribute("aria-label",label);button.append(controlIcon());let request=0;
    button.addEventListener("click",async()=>{const version=selectionVersion,attempt=++request,payload=value();if(payload==null)return;button.replaceChildren(controlIcon());delete button.dataset.copied;button.setAttribute("aria-busy","true");try{await navigator.clipboard.writeText(payload);if(version===selectionVersion && attempt===request){copyStatus.textContent=`${label.replace(/^Copy /,"Copied ")} to clipboard.`;if(button.isConnected){button.replaceChildren(controlIcon("check"));button.dataset.copied="true";}}}catch(failure){if(version===selectionVersion && attempt===request){copyStatus.textContent="Clipboard unavailable. Allow clipboard access and retry; selection and draft are preserved.";if(button.isConnected)button.title=copyStatus.textContent;}}finally{if(attempt===request)button.removeAttribute("aria-busy");}});return button;
  }
  const copySession=copyControl("Copy session",()=>copySnapshot),copyCoverage=node("small");
  const copyActions=node("div",undefined,"developer-copy-actions");copyActions.append(copyCoverage,copyStatus);$("developer-transcript").before(copyActions);$("developer-header").querySelector(".developer-actions").append(copySession);
  for(const [id,kind] of [["developer-stop","stop"],["developer-delegate","delegate"],["developer-close","close"],["developer-root","root"]]){const button=$(id),label=button.textContent;button.title=label;button.setAttribute("aria-label",label);button.classList.add("noetic-icon-action");button.replaceChildren(controlIcon(kind));}
  function copyBlocks(article) {
    for(const block of article.querySelectorAll(".developer-markdown p,.developer-markdown pre,.developer-markdown li,.developer-markdown h3,.developer-markdown h4,.developer-markdown h5,.developer-markdown h6")) {
      const value=block.textContent;
      if(block.tagName==="PRE"){const source=node("code",value,"noetic-code-source");block.replaceChildren(source);block.classList.add("noetic-code-block");}
      else block.classList.add("noetic-copy-prose");
      block.append(copyControl("Copy block",()=>value));
    }
  }

  function composer() {
    const project = !selected && !effort && !projectBrowsing;
    const starting = newConversation || Boolean(selected && !exact(selected));
    const disabled = projectBrowsing || applicationHistory || selected?.ordinal === "0" || reservedSource(detail?.session);
    $("developer-form").hidden = disabled || Boolean(!project && !starting && !detail);
    $("developer-project-fields").hidden = !project;
    for (const id of ["developer-workspace", "developer-model"]) $(id).required = project;
    $("developer-mode").hidden = $("developer-mode-label").hidden = project || starting || disabled;
    text("developer-prompt-label", project ? "Describe the app or work you want done" : starting ? "Start a new conversation at this position" : `Message this exact context${sourceQualifier(detail?.session)}`);
    text("developer-submit", project ? $("developer-project-mode").value === "create" ? "Create project and start" : "Open project and start" : starting ? "Start conversation" : "Send");
    $("developer-submit").disabled = actionPending || disabled || Boolean(!project && !starting && (!detail || !detail.session.broker_owned));
    $("developer-new").disabled = !effort || actionPending;
  }

  function railButton(label, subtitle, target, className) {
    const button = node("button", undefined, className); button.type = "button";
    button.setAttribute("aria-current", String(same(selected, target)));
    button.append(node("span", label), node("small", subtitle));
    button.addEventListener("click", () => select(target)); return button;
  }
  function renderRail() {
    const roots = positions.filter(item => item.effort === item.ordinal).sort(ordinalSort);
    $("developer-session-list").replaceChildren(...roots.map(item => {
      const target = {ordinal:item.ordinal, effort_root:item.ordinal};
      const button = railButton(`${item.ordinal} · ${item.intent}`, item.environment?.cwd || "", target, "developer-project-item");
      button.dataset.effortRoot = item.ordinal; button.setAttribute("aria-current", String(effort === item.ordinal));
      return button;
    }));
    if (!roots.length) $("developer-session-list").append(node("p", "No registered efforts yet.", "rail-note"));
    const tree = positions.filter(item => item.effort === effort).sort(ordinalSort), rows = [];
    for (const item of tree) {
      const button = railButton(`${item.ordinal} · ${item.intent || "Position"}`, "Responsibility and history", {ordinal:item.ordinal,effort_root:effort}, "developer-agent-item");
      button.dataset.ordinal = item.ordinal;
      button.style.paddingLeft = `${10+(item.ordinal.split(".").length-2)*12}px`; rows.push(button);
      for (const context of allSessions.filter(row => row.ordinal === item.ordinal && row.effort_root === effort)) {
        const target = sessionTarget(context);
        const child = railButton(`${context.target ? `Context ${target.instantiation}/${target.session}` : "Failed start / native source"} · ${context.title}`, `${context.status}${context.is_current ? " · current" : " · retained"}${context.domain_status === "superseded" ? " · superseded" : ""}`, target, "developer-context-item");
        child.dataset.sessionId = context.id; child.dataset.agentId = context.id;
        child.style.paddingLeft = `${22+(item.ordinal.split(".").length-2)*12}px`; rows.push(child);
      }
    }
    $("developer-agent-list").replaceChildren(...rows);
    $("developer-legacy-list").replaceChildren(...allSessions.filter(row => row.identity_origin === "legacy-unadopted").map(item => {
      const button = railButton(`${item.original_ordinal || item.ordinal} · ${item.title}`, "Original namespace · unadopted", {id:item.id}, "developer-context-item");
      button.dataset.sessionId = item.id; return button;
    }));
  }
  let historyView = "", historyRows = new Map(), historyWindow = null, historyControls = null;
  function historyContext(record, target) {
    if (!target || !record.effort) return null;
    const native = allSessions.find(item => item.effort_root === record.effort && item.target?.ordinal === target.ordinal && item.target.instantiation === target.instantiation && item.target.session === target.session);
    if (native) return {native:native.id};
    const source = record.source_ref || {}, ref = record.data?.native_ref || {};
    const run = ref.run_id || source.native_run?.split("/").filter(Boolean).at(-1) || /^run:([^:]+)/.exec(source.command_key || "")?.[1];
    const activation = ref.activation_id || record.data?.activation?.id || /(?:^|:)(?:activation|close-session):([^:]+)/.exec(source.command_key || "")?.[1] || /^run:[^:]+:native:([^:]+):/.exec(source.command_key || "")?.[1];
    return run ? {run,activation} : null;
  }
  function renderHistory() {
    $("developer-history-panel").hidden = !applicationHistory && !(selected && !exact(selected));
    text("developer-history-heading", applicationHistory ? "Application history · all efforts" : `Position ${selected?.ordinal || ""} · responsibility and history`);
    const view = JSON.stringify([selectionVersion, applicationHistory, selected, effort, historyCache?.namespace_id]);
    const list = $("developer-history-list");
    if (!historyControls) {
      const controls = node("div",undefined,"history-controls"), searchLabel = node("label","Find event or source"), search = node("input"), kindLabel = node("label","Event kind"), kind = node("select");
      search.id = "developer-history-query"; search.type = "search"; searchLabel.htmlFor = search.id;
      kind.id = "developer-history-kind"; kindLabel.htmlFor = kind.id;
      const coverage = node("p",undefined,"source"), more = node("button","Load earlier events"), clear = node("button","Clear filters");
      coverage.id = "developer-history-coverage"; coverage.setAttribute("role","status"); more.id = "developer-history-more"; clear.id = "developer-history-clear"; more.type = clear.type = "button";
      more.className = clear.className = "secondary-button";
      controls.append(searchLabel,search,kindLabel,kind,clear,coverage,more); list.before(controls);
      historyControls = {search,kind,coverage,more};
      const filter = () => { historyWindow.count = 12; historyWindow.all = false; historyWindow.start = null; renderHistory(); };
      search.addEventListener("input",filter); kind.addEventListener("change",filter);
      clear.addEventListener("click",()=>{search.value = ""; kind.value = ""; filter(); search.focus();});
      more.addEventListener("click",()=>{historyWindow.count = Math.max(historyWindow.count,historyWindow.filtered.length-historyWindow.start)+12; historyWindow.all = historyWindow.count >= historyWindow.filtered.length; renderHistory();});
    }
    if (historyView !== view) { historyView = view; historyRows.clear(); historyWindow = {count:12,all:false,start:null}; historyControls.search.value = ""; historyControls.kind.value = ""; }
    const kinds = [...new Set(historyRecords.map(record=>record.kind).filter(Boolean))].sort(), kindSignature = JSON.stringify(kinds);
    if (historyControls.kind.dataset.signature !== kindSignature) {
      const selectedKind = historyControls.kind.value;
      historyControls.kind.replaceChildren(...[["","All event kinds"],...kinds.map(value=>[value,value])].map(([value,label])=>{const option = node("option",label); option.value = value; return option;}));
      historyControls.kind.value = kinds.includes(selectedKind) ? selectedKind : ""; historyControls.kind.dataset.signature = kindSignature;
    }
    const query = historyControls.search.value.toLowerCase(), kind = historyControls.kind.value;
    const filtered = historyRecords.filter(record=>(!kind || record.kind === kind) && (!query || JSON.stringify(record).toLowerCase().includes(query)));
    historyWindow.filtered = filtered;
    if (historyWindow.all) historyWindow.count = Math.max(historyWindow.count,filtered.length);
    const start = Math.max(0,filtered.length-historyWindow.count), inspecting = list.contains(document.activeElement) || list.querySelector("details[open]");
    historyWindow.start = historyWindow.start !== null && inspecting ? Math.min(historyWindow.start,start) : start;
    const visible = filtered.slice(historyWindow.start);
    const observation = historyObservation;
    const availability = observation.status === "loading" ? "Refreshing retained history; showing last observed records." : observation.status === "error" ? "History refresh unavailable; showing last observed records." : "Complete earlier history remains available.";
    historyControls.coverage.textContent = observation.observed ? `Showing latest ${visible.length} of ${filtered.length} matching events · ${historyRecords.length} total events. ${availability}` : observation.status === "error" ? "History observation unavailable. No retained history has been observed for this selection." : observation.status === "loading" ? "Loading retained history. No observation yet for this selection." : "Retained history not yet observed for this selection.";
    historyControls.more.disabled = !observation.observed || historyWindow.start === 0;
    historyControls.more.textContent = !observation.observed ? "Earlier history awaits observation" : historyWindow.start ? `Load earlier ${Math.min(12,historyWindow.start)} events` : "All matching events shown";
    const retained = new Map();
    const rows = visible.map(record => {
      const identity = JSON.stringify([record.sequence, record.ordinal, record.effort]);
      const target = record.target || (record.instantiation && record.session ? {ordinal:record.ordinal,instantiation:record.instantiation,session:record.session} : null);
      const context = historyContext(record,target);
      const previous = historyRows.get(identity), signature = JSON.stringify([record,context]);
      if (previous?.signature === signature) { retained.set(identity, previous); return previous.row; }
      const row = previous?.row || node("article", undefined, "history-row");
      const evidence = previous?.evidence || node("details");
      if (!previous) evidence.append(node("summary", "Record and source references"), node("pre"));
      evidence.querySelector("pre").textContent = JSON.stringify(record,null,2);
      for (const child of [...row.children]) if (child !== evidence) child.remove();
      const heading = node("strong", `${record.ordinal || record.target?.ordinal || "0"} · ${record.kind}`); row.insertBefore(heading,evidence.parentNode === row ? evidence : null);
      if (context?.native) {
        const button = railButton(`Open context ${target.instantiation}/${target.session}`, "Exact retained native conversation", {...target,effort_root:record.effort}, ""); row.insertBefore(button,evidence.parentNode === row ? evidence : null);
      } else if (context?.run) {
        const button = node("button",`Inspect execution context ${target.instantiation}/${target.session}`); button.type = "button";
        button.append(node("small",`${context.run}${context.activation ? ` · ${context.activation}` : " · retained execution source"}`));
        button.addEventListener("click",()=>selectRun(context.run,context.activation ? {activation_id:context.activation} : null)); row.insertBefore(button,evidence.parentNode === row ? evidence : null);
      } else if (target) row.insertBefore(node("p","Native conversation backing unavailable for this exact context. Inspect retained source references.","source"),evidence.parentNode === row ? evidence : null);
      if (!evidence.parentNode) row.append(evidence); retained.set(identity, {row, evidence, signature}); return row;
    });
    historyRows = retained;
    for (const child of [...list.children]) if (!rows.includes(child)) child.remove();
    rows.forEach((row, index) => { if (list.children[index] !== row) list.insertBefore(row, list.children[index] || null); });
    if (!filtered.length) list.append(node("p", !observation.observed ? observation.status === "error" ? "Retained history observation is unavailable for this selection." : "Waiting for retained history observation." : historyRecords.length ? "No events match these filters." : positions.length ? "No retained events observed in this view." : "No registered application namespace observed. Open / Create project to declare an effort; original histories remain unadopted."));
  }

  let transcriptView = -1, transcriptRows = new Map();
  const transcriptContainer = $("developer-transcript"), transcriptBox = {width:transcriptContainer.clientWidth,height:transcriptContainer.clientHeight};
  let transcriptFollowing = true;
  const transcriptReflowing = () => transcriptBox.width !== transcriptContainer.clientWidth || transcriptBox.height !== transcriptContainer.clientHeight;
  const transcriptAtBottom = () => transcriptContainer.scrollHeight-transcriptContainer.scrollTop-transcriptContainer.clientHeight < 100;
  transcriptContainer.addEventListener("scroll",()=>{
    if (transcriptContainer.clientHeight && !transcriptReflowing()) transcriptFollowing = transcriptAtBottom();
  });
  new ResizeObserver(()=>{
    if (transcriptContainer.clientHeight && transcriptFollowing) transcriptContainer.scrollTop = transcriptContainer.scrollHeight;
    transcriptBox.width = transcriptContainer.clientWidth; transcriptBox.height = transcriptContainer.clientHeight;
  }).observe(transcriptContainer);
  function conversation() {
    const transcriptSignature = JSON.stringify([selected,events,detail.session.status,detail.session.workspace,detail.session.title,detail.session.identity_origin,detail.session.original_ordinal,detail.session.effort_root,detail.session.target]);
    if ($("developer-transcript").dataset.signature === transcriptSignature) return;
    const messages = [], entries = [], tools = new Map(), dialogs = new Map();
    const toolAt = (id, sequence) => {
      const identity = id || `unidentified:${sequence}`;
      if (!tools.has(identity)) {
        const tool = {key:`tool:${identity}`, id, name:"Unknown tool", state:"requested", started:false};
        tools.set(identity,tool); entries.push({tool});
      }
      return tools.get(identity);
    };
    let partial = null;
    for (const event of events) {
      const record = event.record || {};
      if (record.type === "message_start" && record.message?.role === "assistant") partial = {blocks: new Map()};
      if (record.type === "message_update") {
        const update = record.assistantMessageEvent || {};
        if (update.type === "text_delta") {
          partial ||= {blocks: new Map()};
          partial.blocks.set(update.contentIndex || 0, (partial.blocks.get(update.contentIndex || 0) || "") + update.delta);
        }
      }
      const agentEnvelope = record.message?.role === "custom" && record.message.customType === "noetic-agent-message" && record.message.details?.provenance?.origin === "agent" ? record.message.details : null;
      if (record.type === "message_end" && (["user", "assistant"].includes(record.message?.role) || agentEnvelope)) {
        const message = record.message, rendered = content(message);
        const omitted=Array.isArray(message.content)?message.content.filter(block=>!["text","toolCall"].includes(block.type)).map(block=>`[non-text ${block.type || "content"} omitted]`):[];
        if (rendered || message.errorMessage || omitted.length) {
          const item = {key:event.sequence, role:message.role, text:agentEnvelope?.message || rendered || message.errorMessage || "", outcome:message.stopReason,
            copyText:[agentEnvelope?.message || rendered || message.errorMessage || "",...omitted].filter(Boolean).join("\n"), sender:agentEnvelope?.provenance.sender, binding_id:agentEnvelope?.binding_id, recipient:agentEnvelope?.provenance.recipient};
          messages.push(item); entries.push({message:item});
        }
        if (message.role === "assistant" && Array.isArray(message.content)) for (const block of message.content) {
          if (block.type !== "toolCall") continue;
          const tool = toolAt(block.id,event.sequence); tool.name = block.name || tool.name; tool.args = block.arguments ?? tool.args;
        }
        if (message.role === "assistant") partial = null;
      }
      if (["tool_execution_start","tool_execution_update","tool_execution_end"].includes(record.type)) {
        const tool = toolAt(record.toolCallId,event.sequence);
        tool.name = record.toolName || tool.name; tool.args = record.args ?? tool.args;
        if (record.type === "tool_execution_start") { tool.started = true; tool.state = "running"; }
        else if (record.type === "tool_execution_update") { tool.state = "running"; tool.result = record.partialResult; }
        else { tool.state = record.isError ? "error" : "finished"; tool.result = record.result; }
      }
      if (record.type === "extension_ui_request" && ["select", "confirm", "input", "editor"].includes(record.method)) dialogs.set(record.id, record);
      if (record.type === "extension_ui_response") dialogs.delete(record.id);
      if (record.type === "agent_settled") dialogs.clear();
    }
    const container = transcriptContainer, atBottom = transcriptReflowing() ? transcriptFollowing : transcriptAtBottom();
    transcriptFollowing = atBottom;
    if (transcriptView !== selectionVersion) { transcriptView = selectionVersion; transcriptRows.clear(); }
    const retained = new Map(), rows = entries.map(({message,tool}) => {
      const identity = tool?.key || `message:${message.key}`, signature = JSON.stringify([tool || message,sourceQualifier(detail.session),detail.session.ordinal,detail.session.original_ordinal]);
      const previous = transcriptRows.get(identity);
      let article = previous?.article;
      if (tool) {
        if (!article) {
          article = node("article",undefined,"developer-message tool"); article.dataset.toolCallId = tool.id || "";
          const evidence = node("details"); evidence.append(node("summary","Arguments & output"),node("strong","Arguments"),node("pre",undefined,"tool-arguments"),node("strong","Output"),node("pre",undefined,"tool-output"));
          article.append(node("h3"),node("small",undefined,"tool-summary"),evidence);
          for(const [selector,label] of [[".tool-arguments","Copy arguments"],[".tool-output","Copy output"]]){const pre=article.querySelector(selector),heading=node("div",undefined,"noetic-tool-heading");pre.previousElementSibling.before(heading);heading.append(pre.previousElementSibling,copyControl(label,()=>article.querySelector(selector).textContent));}
        }
        const state = tool.state === "error" ? "Failed" : tool.state === "finished" ? "Completed" : tool.state === "requested" ? "Requested · execution unobserved" : ["running","starting"].includes(detail.session.status) ? "Running" : "Completion unobserved";
        const heading = `${tool.name} · ${state}${!tool.started && tool.state !== "requested" ? " · start unobserved" : ""}`;
        if (article.querySelector("h3").textContent !== heading) article.querySelector("h3").textContent = heading;
        const args = tool.args === undefined ? "Arguments unobserved" : JSON.stringify(tool.args,null,2);
        const summary = typeof tool.args?.command === "string" ? tool.args.command : typeof tool.args?.path === "string" ? tool.args.path : tool.args === undefined ? "Arguments unobserved" : JSON.stringify(tool.args);
        const preview = summary.replace(/\s+/g," ").slice(0,160);
        if (article.querySelector(".tool-summary").textContent !== preview) article.querySelector(".tool-summary").textContent = preview;
        let output = "No output observed.";
        if (tool.result !== undefined) output = Array.isArray(tool.result?.content) ? tool.result.content.map(block=>block.type === "text" ? block.text || "" : `[${block.type || "non-text"} output]`).join("\n") || "No text output." : typeof tool.result === "string" ? tool.result : JSON.stringify(tool.result,null,2);
        for (const [selector,value] of [[".tool-arguments",args],[".tool-output",output]]) if (article.querySelector(selector).textContent !== value) article.querySelector(selector).textContent = value;
      } else if (!previous || previous.signature !== signature) {
        article = node("article", undefined, `developer-message ${message.role}`);
        article.dataset.messageSequence = message.key;
        const heading = message.sender ? `Agent ${message.sender.ordinal} · instantiation ${message.sender.instantiation} · session ${message.sender.session}` : message.role === "user" ? "You" : `Agent ${detail.session.original_ordinal && originalSource(detail.session) ? detail.session.original_ordinal : detail.session.ordinal}${sourceQualifier(detail.session)}`;
        article.append(node("h3", heading), message.role === "assistant" ? markdown(message.text) : node("pre", message.text),copyControl("Copy message",()=>message.copyText));
        if(!message.text)article.append(node("p",message.copyText,"source"));
        copyBlocks(article);
        if (message.sender) article.append(node("small", `Message ${message.binding_id} · to ${message.recipient.ordinal} · instantiation ${message.recipient.instantiation} · session ${message.recipient.session}`));
        if (["error", "aborted"].includes(message.outcome)) article.append(node("small", message.outcome));
      }
      retained.set(identity,{article,signature}); return article;
    });
    if (partial?.blocks.size) {
      const article = node("article", undefined, "developer-message assistant streaming");
      article.append(node("h3", `Agent ${originalSource(detail.session) ? detail.session.original_ordinal || detail.session.ordinal : detail.session.ordinal}${sourceQualifier(detail.session)} · streaming`), node("pre", [...partial.blocks.values()].join("\n")));
      rows.push(article);
    }
    const session=detail.session,identity=session.target?`Application position ${session.ordinal} · instantiation ${session.target.instantiation} · session ${session.target.session}`:`Original namespace · unadopted · ordinal ${session.original_ordinal || session.ordinal}`;
    const snapshotRows=entries.map(({message,tool})=>message?`[${message.sender?`Agent ${message.sender.ordinal} / ${message.sender.instantiation} / ${message.sender.session}`:message.role}]\n${message.copyText}`:`[Tool ${tool.name} · ${tool.state}]\nArguments:\n${tool.args===undefined?"Arguments unobserved":JSON.stringify(tool.args,null,2)}\nOutput:\n${["finished","error"].includes(tool.state)?(typeof tool.result==="string"?tool.result:Array.isArray(tool.result?.content)?tool.result.content.map(block=>block.type==="text"?block.text||"":`[non-text ${block.type||"output"} omitted]`).join("\n"):tool.result===undefined?"No output observed":JSON.stringify(tool.result,null,2)):"[Incomplete tool output excluded]"}`);
    copySnapshot=reservedSource(session) ? null : [`${identity} · native ID ${session.id}\nCompleted retained conversation snapshot ${new Date().toISOString()}${observationError?" · last observed; refresh unavailable":""}`,`${messages.length} completed messages · ${tools.size} distinct tools`,...snapshotRows,...(partial?.blocks.size?["[Streaming assistant text excluded]"]:[])].join("\n\n");
    copyCoverage.textContent=`${messages.length} completed messages · ${tools.size} distinct tools${partial?.blocks.size?" · streaming text excluded":""}`;copySession.disabled=reservedSource(session);
    transcriptRows = retained;
    for (const child of [...container.children]) if (!rows.includes(child)) child.remove();
    rows.forEach((row,index)=>{if(container.children[index] !== row) container.insertBefore(row,container.children[index] || null);});
    if (atBottom) container.scrollTop = container.scrollHeight;
    const lastTool = [...tools.values()].at(-1);
    const result = $("developer-result");
    result.hidden = !["idle", "closed"].includes(detail.session.status) || !messages.some(message => message.role === "assistant");
    if (!result.hidden) {
      result.replaceChildren(node("strong", "Project / task location"), node("p", detail.session.workspace));
      const command = [...tools.values()].reverse().find(tool => tool.name === "bash" && typeof tool.args?.command === "string");
      if (command) result.append(node("small", `Last observed command · ${command.state}`), node("pre", command.args.command));
      const final = [...messages].reverse().find(message => message.role === "assistant");
      const previews = [...(final?.text || "").matchAll(/https?:\/\/[^\s<>\])]+/g)].map(match => match[0]);
      if (previews.length) { result.append(node("small", "Reported links")); for (const reference of [...new Set(previews)].slice(0,8)) result.append(safeLink(reference, reference)); }
    }
    text("developer-progress", lastTool ? `${lastTool.name} · ${lastTool.state}` : "");
    const holder = $("developer-dialogs"), signature = JSON.stringify([...dialogs.values()]);
    if (holder.dataset.signature !== signature) {
      holder.dataset.signature = signature;
      holder.replaceChildren(...[...dialogs.values()].map(dialog => {
        const form = node("form", undefined, "developer-dialog");
        form.append(node("h3", dialog.title || "Agent request"));
        if (dialog.message) form.append(node("p", dialog.message));
        let input;
        if (dialog.method === "select") {
          input = node("select");
          for (const option of dialog.options || []) { const element = node("option", option); element.value = option; input.append(element); }
        } else if (dialog.method !== "confirm") {
          input = node(dialog.method === "editor" ? "textarea" : "input"); input.value = dialog.prefill || ""; input.placeholder = dialog.placeholder || "";
        }
        if (input) { input.setAttribute("aria-label", dialog.title || "Response"); form.append(input); }
        const submit = node("button", dialog.method === "confirm" ? "Confirm" : "Send response"); submit.type = "submit"; form.append(submit);
        const cancel = node("button", dialog.method === "confirm" ? "Decline" : "Cancel"); cancel.type = "button"; form.append(cancel);
        const recipient = {...selected}, version = selectionVersion;
        const respond = async cancelled => {
          try { await post(endpoint("dialog", recipient), {...scope(recipient), id: dialog.id, ...(dialog.method === "confirm" ? {confirmed: !cancelled} : cancelled ? {cancelled: true} : {value: input.value})}); await refresh(); }
          catch (failure) { if (version === selectionVersion) error("developer-error", failure.message); }
        };
        form.addEventListener("submit", event => { event.preventDefault(); respond(false); });
        cancel.addEventListener("click", () => respond(true));
        return form;
      }));
    }
    $("developer-transcript").dataset.signature = transcriptSignature;
  }

  function renderDetail() {
    $("developer-empty").hidden = Boolean(selected || applicationHistory || projectBrowsing);
    $("developer-header").hidden = !detail || newConversation || applicationHistory;
    $("developer-transcript").hidden = !detail || newConversation || applicationHistory;
    $("developer-form").hidden = applicationHistory || selected?.ordinal === "0" || Boolean(detail?.session.effort_root && !detail.session.target);
    renderHistory();
    copyActions.hidden=!detail||newConversation||applicationHistory||reservedSource(detail?.session);copySession.disabled=copyActions.hidden;copySession.hidden=copyActions.hidden;
    if (!detail) { copySnapshot=null;copyStatus.textContent="";text("developer-attention", ""); $("developer-attention").hidden = true; composer(); notify(); return; }
    const item = detail.session;
    text("developer-heading", item.title); text("developer-location", item.workspace); text("developer-status", item.status);
    const position = positions.find(row => row.ordinal === item.ordinal);
    const assignment = item.ordinal === item.effort_root ? "root" : position?.origin === "human" ? "human assignment" : position?.origin === "agent" ? "delegate" : "assignment origin unobserved";
    text("developer-ordinal", item.target ? `Agent ${item.ordinal} · ${assignment}` : item.effort_root ? `Position ${item.ordinal} · failed native start` : `Original ordinal ${item.original_ordinal || item.ordinal} · unadopted`);
    text("developer-context", item.target ? `Instantiation ${item.target.instantiation} / context ${item.target.session}${item.is_current ? " · current" : " · retained"}` : item.effort_root ? "Reservation retained · no invented native context" : "Original namespace · no declared effort");
    text("developer-model-status", `${item.target ? "" : "Requested: "}${item.model} · ${item.thinking}`);
    text("developer-attention", (originalSource(item) ? `Original namespace · unadopted. Actions address native session ${item.id}. ` : "") + (item.error || (item.domain_status === "superseded" ? "Retained exact context. Sending never redirects to a successor." : item.status === "needs_input" ? "The agent has a request below." : item.status === "interrupted" ? "Process interrupted. Reopen explicitly to continue the retained context." : "")));
    $("developer-attention").hidden = !$("developer-attention").textContent;
    $("developer-stop").disabled = !item.broker_owned || actionPending;
    $("developer-close").disabled = !item.broker_owned || actionPending;
    $("developer-delegate").disabled = !item.broker_owned || !item.is_current || actionPending;
    $("developer-reopen").hidden = item.broker_owned; $("developer-reopen").disabled = !item.can_reopen || actionPending;
    $("developer-root").hidden = !item.effort_root || item.ordinal === item.effort_root;
    $("developer-succeed").disabled = !item.is_current || actionPending;
    text("developer-details", JSON.stringify(item,null,2));
    if ($("developer-evidence").open) text("developer-events", JSON.stringify(events,null,2));
    conversation(); composer(); notify();
  }

  async function select(target, options = {}) {
    saveDelegateDraft();
    drafts[key(selected)] = $("developer-prompt").value;
    selected = target; effort = target?.effort_root || null;
    projectBrowsing=Boolean(options.browse);projectPath=projectBrowsing ? options.project || null : null;
    window.NoeticEffort?.select(effort,target);
    applicationHistory = Boolean(options.history); newConversation = Boolean(options.newConversation);
    $("developer-prompt").value = options.draft ?? drafts[key(target)] ?? "";
    error("developer-error", ""); observationError = false;
    detail = null; events = []; historyRecords = []; historyCache = null; historyObservation = {status:"unobserved",observed:false,error:null}; cursor = 0; transcriptFollowing = true; ++selectionVersion;
    $("developer-file-view").hidden = true; $("developer-result").hidden = true;
    $("developer-transcript").dataset.signature = "";
    $("developer-transcript").replaceChildren(); $("developer-dialogs").replaceChildren();
    $("developer-dialogs").dataset.signature = ""; $("developer-evidence").open = false;
    $("developer-delegate-form").hidden = true; $("developer-succession-form").hidden = true;
    text("developer-ack", ""); switchPage("developer"); persist(); renderRail(); renderDetail();
    await refresh();
  }

  async function refresh(options = {}) {
    if (!active() || pending) return;
    pending = true;
    const version = selectionVersion, target = selected && {...selected}, access = accessVersion;
    const valid = () => version === selectionVersion && access === accessVersion && active();
    const readingHistory = Boolean(applicationHistory || (target && !exact(target)));
    let historyReadPending = readingHistory;
    if (readingHistory && (!historyObservation.observed || options === true || options.explicit || options.type === "click")) { historyObservation = {...historyObservation,status:"loading",error:null}; renderHistory(); }
    const slowHistory = readingHistory ? setTimeout(()=>{if(valid() && historyReadPending){historyObservation={...historyObservation,status:"loading"};renderHistory();}},1500) : null;
    try {
      const branch = await pages("/api/ordinals/0/branch", "records", {}, valid);
      if (!branch) return;
      const roots = branch.rows.filter(row => row.effort === row.ordinal);
      positions = branch.rows;
      window.NoeticEffort?.catalogue(positions);
      if (target?.ordinal && target.ordinal !== "0" && !roots.some(row => row.ordinal === target.ordinal)) {
        const describedPosition = await fetchJSON(`/api/ordinals/${encodeURIComponent(target.ordinal)}?${query(scope(target))}`);
        if (!valid()) return;
        positions = positions.map(row => row.ordinal === target.ordinal ? describedPosition.position : row);
      }
      const result = await fetchJSON("/api/developer-sessions");
      if (!valid()) return; allSessions = result.sessions;
      if (!$("developer-projects-root").value) $("developer-projects-root").value = result.projects_root;
      if (target && exact(target)) {
        const value = await pages(endpoint("", target), "events", {...scope(target),after:cursor}, valid);
        if (!value) return; detail = value.result; events.push(...value.rows); cursor = value.result.next_after || cursor;
      } else if (target || applicationHistory) {
        const value = await historyPages(`/api/ordinals/${encodeURIComponent(applicationHistory ? "0" : target.ordinal)}/history`, applicationHistory ? {} : scope(target), historyRecords, historyCache, valid,()=>{
          historyRecords=[]; historyCache=null; historyObservation={status:"loading",observed:false,error:null};
          if(applicationHistory){applicationEvents=[];returnsCache=null;} renderHistory(); notify();
        });
        if (!value) return; historyRecords = value.rows; historyCache = value.cache;
        historyObservation = {status:"observed",observed:true,error:null}; historyReadPending = false;
        if (applicationHistory) {applicationEvents = value.rows;returnsCache = null;}
      }
      if (observeReturns && !applicationHistory) {
        const value = await historyPages("/api/ordinals/0/history", {}, applicationEvents, returnsCache, valid,()=>{applicationEvents=[];returnsCache=null;notify();});
        if (!value) return; applicationEvents = value.rows; returnsCache = value.cache;
      }
      if (observationError) { error("developer-error", ""); observationError = false; }
      renderRail(); renderDetail();
    } catch (failure) {
      if (valid()) {
        observationError = true; error("developer-error", `Observation unavailable: ${failure.message}`);
        if (historyReadPending) { historyObservation = {...historyObservation,status:"error",error:failure.message}; renderHistory(); }
        for (const action of ["stop","close","delegate","reopen","succeed"]) $("developer-"+action).disabled = true;
        $("developer-submit").disabled = Boolean(selected); notify();
      }
    } finally { clearTimeout(slowHistory);pending = false; if (version !== selectionVersion && active()) queueMicrotask(refresh); }
  }

  async function act(action) {
    if (!selected || !exact(selected) || actionPending) return;
    const target = {...selected}; actionPending = true; renderDetail();
    try {
      const result = await post(endpoint(action,target), scope(target));
      if (same(target,selected)) text("developer-ack", action === "stop" ? result.stopped ? "Queues cleared; Pi reports idle with no pending messages." : "Stop acknowledged; observe the actual state." : action === "shutdown" ? "Shutdown requested; waiting for owned process cleanup." : "Agent reopened in its retained context; no previous prompt resubmitted.");
    } catch (failure) { if (same(target,selected)) error("developer-error", failure.message); }
    finally { actionPending = false; await refresh(); renderDetail(); }
  }

  $("developer-prompt").addEventListener("keydown", event => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing || event.keyCode === 229 || event.defaultPrevented) return;
    event.preventDefault();
    const submit = $("developer-submit");
    if (event.repeat || actionPending || submit.disabled) return;
    event.currentTarget.form.requestSubmit(submit);
  });
  $("developer-form").addEventListener("submit", async event => {
    event.preventDefault(); if (actionPending || projectBrowsing) return;
    const target = selected && {...selected}, version = selectionVersion, revision = promptRevision, prompt = $("developer-prompt").value;
    const starting = newConversation || Boolean(target && !exact(target));
    actionPending = true; composer(); error("developer-error", "");
    try {
      if (!target || starting) {
        const template = target && allSessions.find(row => row.ordinal === target.ordinal && row.is_current);
        const body = {prompt, model:template?.model || $("developer-model").value, thinking:template?.thinking || $("developer-thinking").value};
        if (template?.title) body.title = template.title;
        else if (!target && $("developer-project-name").value.trim()) body.title = $("developer-project-name").value;
        if ($("developer-projects-root").value.trim()) body.projects_root = $("developer-projects-root").value.trim();
        let result;
        if (target) result = await post("/api/developer-sessions", {...body,effort_root:target.effort_root,ordinal:target.ordinal});
        else if ($("developer-project-mode").value === "create") result = await post("/api/developer-projects", {...body,directory:$("developer-workspace").value,intent:prompt});
        else {
          const folder = $("developer-workspace").value.trim(), root = body.projects_root;
          const cwd = folder.startsWith("/") ? folder : root ? `${root.replace(/\/$/, "")}/${folder}` : null;
          if (!cwd) throw new Error("Choose an absolute project folder or a Projects location for its name.");
          const registered = await post("/api/efforts", {intent:prompt,environment:{cwd}});
          result = await post("/api/developer-sessions", {...body,effort_root:registered.effort.ordinal});
        }
        if (version === selectionVersion) {
          const draft = revision === promptRevision && $("developer-prompt").value === prompt ? "" : $("developer-prompt").value;
          $("developer-prompt").value = draft;
          const landing = select(sessionTarget(result.session), {draft}), landingVersion = selectionVersion;
          await landing;
          if (landingVersion === selectionVersion) text("developer-ack", "Prompt accepted. Follow actual output and settled state here.");
        }
      } else {
        const mode = $("developer-mode").value;
        await post(endpoint("prompt",target), {...scope(target),message:prompt,mode});
        if (version === selectionVersion) text("developer-ack", mode === "steer" ? "Steering accepted; Pi applies it after the current tool turn." : mode === "follow_up" ? "Follow-up accepted or queued; delivery and completion appear in the conversation." : "Prompt accepted; completion is observed separately.");
      }
      if (version === selectionVersion && revision === promptRevision && $("developer-prompt").value === prompt) { $("developer-prompt").value = ""; persist(); }
    } catch (failure) { if (version === selectionVersion) error("developer-error",failure.message); }
    finally { actionPending = false; composer(); await refresh(); }
  });
  $("developer-file-close").addEventListener("click", () => { $("developer-file-view").hidden = true; });
  $("developer-project-mode").addEventListener("change", composer);
  $("developer-project-open").addEventListener("click", () => select(null));
  $("developer-new").addEventListener("click", () => { if (effort) select({ordinal:selected?.ordinal || effort,effort_root:effort},{newConversation:true}); });
  $("developer-global-root").addEventListener("click", () => select({ordinal:"0"}));
  $("developer-global-history").addEventListener("click", () => select(null,{history:true}));
  $("developer-succeed").addEventListener("click", () => { $("developer-succession-form").hidden = false; });
  $("developer-succession-cancel").addEventListener("click", () => { $("developer-succession-form").hidden = true; });
  $("developer-succession-form").addEventListener("submit", async event => {
    event.preventDefault(); if (!detail?.session.is_current || actionPending) return;
    const target = {...selected}, version = selectionVersion;
    const body = {effort_root:target.effort_root,ordinal:target.ordinal,title:detail.session.title,prompt:$("developer-succession-context").value,
      succession:{predecessor:target.instantiation,handoff:{responsibility:$("developer-succession-responsibility").value,context:$("developer-succession-context").value}}};
    actionPending = true;
    try { const result = await post("/api/developer-sessions",body); if (version === selectionVersion) await select(sessionTarget(result.session)); }
    catch (failure) { if (version === selectionVersion) error("developer-error",failure.message); }
    finally { actionPending = false; await refresh(); }
  });
  $("developer-stop").addEventListener("click", () => act("stop"));
  $("developer-close").addEventListener("click", () => act("shutdown"));
  $("developer-reopen").addEventListener("click", () => act("reopen"));
  $("developer-root").addEventListener("click", () => {
    const root = allSessions.find(row => row.ordinal === effort && row.is_current);
    select(root ? sessionTarget(root) : {ordinal:effort,effort_root:effort});
  });
  const delegateDrafts = new Map();
  let delegateOwner = null;
  const delegateKey = target => JSON.stringify([accessVersion,target]);
  function saveDelegateDraft() {
    if (delegateOwner !== delegateKey(selected)) return;
    const prior = delegateDrafts.get(delegateOwner) || {};
    delegateDrafts.set(delegateOwner,{...prior,task:$("developer-delegate-task").value,thinking:$("developer-delegate-thinking").value});
  }
  $("developer-delegate").addEventListener("click", () => {
    delegateOwner = delegateKey(selected);
    const draft = delegateDrafts.get(delegateOwner) || {};
    $("developer-delegate-task").value = draft.task || "";
    $("developer-delegate-thinking").value = draft.thinking || "low";
    error("developer-error",draft.failure || "");
    text("developer-ack",draft.result || "");
    $("developer-delegate-form").hidden = false; $("developer-delegate-task").focus();
  });
  $("developer-delegate-task").addEventListener("input",saveDelegateDraft);
  $("developer-delegate-thinking").addEventListener("change",saveDelegateDraft);
  $("developer-delegate-cancel").addEventListener("click", () => { saveDelegateDraft(); $("developer-delegate-form").hidden = true; });
  $("developer-delegate-form").addEventListener("submit", async event => {
    event.preventDefault(); if (actionPending || !selected || delegateOwner !== delegateKey(selected)) return;
    saveDelegateDraft();
    const target = {...selected}, version = selectionVersion, access = accessVersion, owner = delegateOwner;
    const submitted = {...delegateDrafts.get(owner)};
    const valid = () => version === selectionVersion && access === accessVersion;
    actionPending = true; $("developer-delegate-submit").disabled = true;
    try {
      const child = await post(endpoint("delegate",target), {...scope(target),prompt:submitted.task,thinking:submitted.thinking});
      const latest = delegateDrafts.get(owner) || submitted;
      const result = `Delegate ${child.ordinal} accepted the task; inspect its actual outcome.`;
      delegateDrafts.set(owner,{...latest,task:latest.task===submitted.task?"":latest.task,failure:"",result});
      if (!valid()) return;
      $("developer-delegate-task").value = delegateDrafts.get(owner).task;
      $("developer-delegate-form").hidden = true;
      await select(sessionTarget(child)); text("developer-ack",result);
    } catch (failure) {
      delegateDrafts.set(owner,{...(delegateDrafts.get(owner)||submitted),failure:failure.message,result:""});
      if (valid()) error("developer-error",failure.message);
    }
    finally { actionPending = false; $("developer-delegate-submit").disabled = false; await refresh(); renderDetail(); }
  });
  $("developer-evidence").addEventListener("toggle", () => { if ($("developer-evidence").open) text("developer-events", JSON.stringify(events, null, 2)); });
  $("refresh").addEventListener("click", refresh);
  function browseProject(project) {
    if (selected && !projectBrowsing) {
      const item=detail?.session || allSessions.find(row=>selected.id ? row.id===selected.id : row.ordinal===selected.ordinal && (!selected.instantiation || row.target?.instantiation===selected.instantiation && row.target?.session===selected.session));
      const label=exact(selected) && item && !reservedSource(item) && (item.target || originalSource(item)) ? item.target ? `Return to conversation · Effort ${item.effort_root} · ${item.ordinal} · ${item.target.instantiation}/${item.target.session}` : `Return to original native conversation · ${item.id} · original ${item.original_ordinal || item.ordinal}` : `Return to ${selected.ordinal || item?.ordinal ? "position " + (selected.ordinal || item.ordinal) : "retained record " + selected.id}`;
      returnContext={target:{...selected},history:applicationHistory,label};
    }
    return select(null,{browse:true,project});
  }
  window.NoeticSessions = {refresh,open:select,state,browseProject,
    returnToContext:()=>returnContext ? select({...returnContext.target},{history:returnContext.history}) : Promise.resolve(),
    observeReturns: () => { observeReturns = true; return refresh(); }};
  composer(); renderDetail();
  setInterval(refresh, 1200);
  if (active()) refresh();
})();
