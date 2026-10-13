"use strict";

const $ = (id) => document.getElementById(id);
const tokenKey = "noetic-operator-token";
let operatorToken = "";
let accessVersion = 0;
const fragmentToken = new URLSearchParams(location.hash.slice(1)).get("token");
if (fragmentToken !== null) history.replaceState(null, "", location.pathname + location.search);
try {
  operatorToken = fragmentToken ?? sessionStorage.getItem(tokenKey) ?? "";
  if (operatorToken) sessionStorage.setItem(tokenKey, operatorToken);
} catch (_) { operatorToken = fragmentToken || ""; }
let savedUI = {};
try { savedUI = JSON.parse(sessionStorage.getItem("noetic-workspace-v1") || "{}"); } catch (_) { /* Storage is optional. */ }
const initialForms = { ...savedUI.forms };
let selectedId = savedUI.selectedId || null;
let selectedDetail = null;
let detailVersion = 0;
let refreshPending = false;
let listSignature = "";
let timelineSignature = "";
let kernelSignature = "";
let actorLogVersion = 0;
const cancelling = new Set();
let allRuns = [];
let configuration = null;
let sessionVersion = 0;
let sessionSignature = "";
let workbenchSignature = "";
let currentPage = savedUI.page || "developer";
let reuseVersion = 0;
let draftVersion = 0;
let developerSelection = {};
try { developerSelection = JSON.parse(sessionStorage.getItem("noetic-developer-view") || "{}"); } catch (_) {}
let selectedEffort = developerSelection.effort || null;
let selectedNative = developerSelection.selected || null;
let effortEnvironment = null, effortPositions = [];
let operationMode = savedUI.operationMode || (selectedEffort ? "effort" : "application");
let operationVersion = 0, recallTargetVersion = 0, purposeVersion = 0, purposeDraftVersion = 0, memoryVersion = 0;
let startPending = false, developerSubjectVersion = 0;
let reviewedVersion = 0, reviewedLoading = false, reviewedDefinition = null;
let reviewedSources = [], reviewedLaunch = null;
const isReviewed = () => $("start-pattern").value === "opermem-reviewed";
const operationSelection = () => operationMode === "effort" && selectedEffort ? {effort_root:selectedEffort} : {scope:"application"};
const operationKey = () => JSON.stringify(operationSelection());
const scopedURL = (path, selection = operationSelection()) => {
  const url = new URL(path, location.origin);
  for (const [key,value] of Object.entries(selection)) url.searchParams.set(key,value);
  return url.pathname + url.search;
};
const operationValid = (version, key) => version === operationVersion && key === operationKey();
let runRegister = {selection:operationSelection(),status:"unobserved",observedAt:null,warnings:[],error:""};
function observeRuns(update, notify = true) {
  runRegister = {...runRegister,...update};
  if (notify) document.dispatchEvent(new CustomEvent("noetic:runs", {detail:{runs:allRuns,observation:runRegister}}));
}
window.NoeticRuns = {state:()=>({...runRegister,selection:{...runRegister.selection},warnings:[...runRegister.warnings],runs:allRuns}),refresh,scope:mode=>changeOperationScope(mode)};
function scopeControls() {
  setOptions("operation-scope", [["application","Application · all efforts and original histories"], ...selectedEffort ? [["effort",`Effort ${selectedEffort} · ${effortPositions.find(row=>row.ordinal===selectedEffort)?.intent || "selected responsibility"}`]] : []], operationMode);
  $("operation-scope").value = operationMode;
  text("legacy-scope-banner", operationMode === "effort" && selectedEffort ? `Effort ${selectedEffort} · workflows, purposes and recall use explicit ownership. Original unassigned histories remain in Application scope.` : "Application scope · all declared efforts and original unassigned histories. Select an effort to start structured work.");
  const native = operationMode === "effort" && selectedNative?.effort_root === selectedEffort;
  $("memory-target").querySelector('[value="ordinal"]').disabled = !native || !selectedNative.ordinal;
  $("memory-target").querySelector('[value="session"]').disabled = !native || !selectedNative.instantiation;
  if ($("memory-target").selectedOptions[0]?.disabled || operationMode !== "effort") $("memory-target").value = "effort";
  if (operationMode === "effort" && effortEnvironment) $("start-workspace").value = effortEnvironment.cwd;
  $("start-submit").disabled = startPending || operationMode !== "effort" || !effortEnvironment || window.NoeticDrafts && !window.NoeticDrafts.ready() || isReviewed() && (!reviewedReady() || !$("reviewed-store").value);
}
function changeOperationScope(mode, previous = operationKey()) {
  if (previous !== JSON.stringify(mode === "effort" && selectedEffort ? {effort_root:selectedEffort} : {scope:"application"})) window.NoeticDrafts?.leave();
  if (previous !== JSON.stringify(mode === "effort" && selectedEffort ? {effort_root:selectedEffort} : {scope:"application"})) window.NoeticPurposeDrafts?.leave();
  operationMode = mode === "effort" && selectedEffort ? "effort" : "application";
  savedUI.operationMode = operationMode;
  if (operationKey() !== previous) {
    ++operationVersion; ++purposeVersion; ++memoryVersion; ++detailVersion; ++sessionVersion; ++actorLogVersion; ++reuseVersion;
    ++reviewedVersion; reviewedLaunch = null; reviewedSources = [];$("reviewed-parent-id").value="";$("reviewed-warrant-id").value="";$("reviewed-condition-ids").value="";$("reviewed-formulation-id").value="";$("reviewed-checking-spec").value="";$("reviewed-checking-context").value="";$("reviewed-judgment-ids").value="";$("reviewed-practical-question-id").value="";$("reviewed-option-ids").value="";
    $("reviewed-selected-sources").replaceChildren(); $("reviewed-launch-list").replaceChildren();text("reviewed-launch-status","Launch observations not yet read in this scope.");
    $("reviewed-store").replaceChildren(node("option", "Select backing explicitly")); $("reviewed-store").firstChild.value = "";
    delete $("reviewed-store").dataset.options; text("reviewed-store-status", "Scope changed. Select a backing explicitly.");
    $("reviewed-result").hidden = true; $("reviewed-evidence").hidden = true; $("reviewed-evidence-content").replaceChildren();
    selectedId = null; selectedDetail = null; listSignature = "";
    observeRuns({selection:operationSelection(),status:"unobserved",observedAt:null,warnings:[],error:""},false); renderRuns([]);
    $("selected-run").hidden = true; $("workspace-result").hidden = true; $("workspace-file-view").hidden = true;
    $("memory-results").replaceChildren(); text("memory-status", "Scope changed. Search explicitly."); text("memory-coverage", ""); error("memory-error", "");
    $("purpose-list").replaceChildren(); text("purpose-status", "Scope changed. Refresh purposes explicitly."); text("purpose-database", ""); error("purpose-error", "");
    setOptions("start-purpose", [["","No Telos link"]], ""); delete initialForms["start-purpose"];
    text("start-result", ""); error("start-error", ""); text("summary-content", ""); text("summary-coverage", "");
    text("workspace-apply-result", ""); text("action-result", ""); text("cancel-note", ""); error("action-error", ""); error("cancel-error", "");
  }
  if (operationKey() !== previous) {window.NoeticDrafts?.enter();window.NoeticPurposeDrafts?.enter();}
  scopeControls(); persistUI();
  if (isReviewed() && operatorToken) loadReviewedSetup();
  if (operatorToken && !$("private-workspace").hidden) refresh();
}
window.NoeticEffort = {
  select(root, target) {
    window.NoeticDrafts?.capture();
  window.NoeticPurposeDrafts?.capture();
    ++developerSubjectVersion;
    const previous = operationKey(), previousTarget = JSON.stringify(selectedNative); selectedEffort = root; selectedNative = target;
    if (JSON.stringify(target) !== previousTarget) {
      ++recallTargetVersion;
      if ($("memory-target").value !== "effort") { ++memoryVersion; $("memory-results").replaceChildren(); text("memory-status", "Recall subject changed. Search explicitly."); }
    }
    effortEnvironment = effortPositions.find(row=>row.ordinal===root)?.environment || null;
    const mode = root ? "effort" : "application";
    // Compare the prior scope before replacing its effort pointer.
    operationMode = mode;
    if (operationKey() !== previous) changeOperationScope(mode,previous);
    else { scopeControls(); persistUI(); }
  },
  catalogue(positions) { effortPositions = positions; effortEnvironment = positions.find(row=>row.ordinal===selectedEffort)?.environment || null; scopeControls(); },
  selection: operationSelection, version: () => operationVersion
};
function actorIdentity(actor, correspondence = selectedDetail?.correspondence) {
  const participant = correspondence?.participants?.find(row=>row.activation_id === actor.id || actor.actor_id && row.actor_id === actor.actor_id);
  return participant ? `${participant.ordinal}${participant.target ? ` · context ${participant.target.instantiation}/${participant.target.session}` : " · native context unobserved"}` : `Original actor ${actor.ordinal}`;
}
const formIds = ["reviewed-store", "reviewed-parent-id", "reviewed-warrant-id", "reviewed-condition-ids", "reviewed-formulation-id", "reviewed-checking-spec", "reviewed-checking-context", "reviewed-judgment-ids", "reviewed-practical-question-id", "reviewed-option-ids", "reviewed-sources", "reviewed-operation", "start-pattern", "start-workspace", "start-task", "start-sources", "start-verify", "start-profile", "start-client", "start-model", "start-qa-model", "start-thinking", "start-timeout", "start-remediations", "start-returns", "start-purpose", "memory-mode", "memory-query", "purpose-goal", "run-filter", "status-filter", "pattern-filter", "role-filter"];
const selectionIds = ["actor-select", "artifact-select", "actor-log-select", "report-select", "log-select", "phase-select", "session-select", "compare-left", "compare-right"];

function persistUI() {
  window.NoeticDrafts?.capture();
  window.NoeticPurposeDrafts?.capture();
  savedUI.selectedId = selectedId;
  savedUI.page = currentPage;
  savedUI.forms = Object.fromEntries(formIds.map((id) => [id, $(id).value]));
  if (selectedDetail) {
    savedUI.runs ||= {};
    savedUI.runs[selectedId] = { ...savedUI.runs[selectedId], follow: $("follow-current").checked, ...Object.fromEntries(selectionIds.map((id) => [id, $(id).value])) };
  }
  try { sessionStorage.setItem("noetic-workspace-v1", JSON.stringify(savedUI)); } catch (_) { /* No storage must not stop work. */ }
}

function lockAccess(forget = false, replacementToken = "") {
  persistUI();
  operatorToken = "";
  ++accessVersion;
  try {
    sessionStorage.removeItem(tokenKey);
    if (replacementToken) sessionStorage.setItem(tokenKey, replacementToken);
    if (forget) sessionStorage.removeItem("noetic-workspace-v1");
  } catch (_) { /* Storage is optional. */ }
  $("private-workspace").hidden = true;
  $("private-workspace").replaceChildren();
  $("access-token").value = "";
  // Reload discards private DOM, in-flight renderers and payloads, retaining only tab drafts on lock.
  location.reload();
}

async function unlockAccess() {
  if (!operatorToken) return;
  const version = accessVersion;
  try {
    await fetchJSON("/api/runs?scope=application");
    if (version !== accessVersion) return;
    try { sessionStorage.setItem(tokenKey, operatorToken); } catch (_) { /* Storage is optional. */ }
    $("private-workspace").hidden = false;
    renderReuseNotice();
    $("access-form").hidden = true;
    $("access-lock").hidden = false;
    text("access-status", "Local operator connected");
    offerPreviousDrafts();
    loadConfiguration();
    refresh();
    window.NoeticSessions?.refresh();
  } catch (_) {
    if (version !== accessVersion) return;
    text("access-status", "Unable to pair. Check the server and local operator token.");
  }
}

function offerPreviousDrafts() {
  try {
    $("previous-drafts").hidden = localStorage.getItem("noetic-workspace-v1") === null;
  } catch (_) {
    $("previous-drafts").hidden = false;
    $("import-previous-drafts").disabled = true;
    $("forget-previous-drafts").disabled = true;
    text("previous-drafts-status", "Previous draft storage is unavailable. No previous drafts have been changed. Check browser storage access and reload to retry.");
  }
}

function importPreviousDrafts() {
  if (!operatorToken || $("private-workspace").hidden) return;
  if (!window.confirm("Import previous drafts and replace this tab's saved forms and view selections?")) return;
  try {
    const raw = localStorage.getItem("noetic-workspace-v1");
    if (raw === null) throw new Error();
    const legacy = JSON.parse(raw);
    const object = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
    if (!object(legacy)) throw new Error();
    const imported = {};
    const pages = ["developer", "workspace", "new", "history", "memory", "purposes", "diagnostics"];
    const views = ["phases", "session", "compare", "controller", "timeline", "reports", "logs"];
    if (Object.hasOwn(legacy, "selectedId")) {
      if (legacy.selectedId !== null && typeof legacy.selectedId !== "string") throw new Error();
      imported.selectedId = legacy.selectedId;
    }
    if (Object.hasOwn(legacy, "page")) {
      if (!pages.includes(legacy.page)) throw new Error();
      imported.page = legacy.page;
    }
    if (Object.hasOwn(legacy, "forms")) {
      if (!object(legacy.forms)) throw new Error();
      imported.forms = {};
      for (const id of formIds) {
        if (!Object.hasOwn(legacy.forms, id)) continue;
        if (typeof legacy.forms[id] !== "string") throw new Error();
        imported.forms[id] = legacy.forms[id];
      }
    }
    if (Object.hasOwn(legacy, "positions")) {
      if (!object(legacy.positions)) throw new Error();
      imported.positions = {};
      for (const page of pages) {
        if (!Object.hasOwn(legacy.positions, page)) continue;
        const position = legacy.positions[page];
        if (!Number.isFinite(position) || position < 0) throw new Error();
        imported.positions[page] = position;
      }
    }
    if (Object.hasOwn(legacy, "runs")) {
      if (!object(legacy.runs)) throw new Error();
      imported.runs = Object.create(null);
      for (const [id, selections] of Object.entries(legacy.runs)) {
        if (["__proto__", "constructor", "prototype"].includes(id) || !object(selections)) throw new Error();
        const allowed = {};
        for (const key of selectionIds) {
          if (!Object.hasOwn(selections, key)) continue;
          if (typeof selections[key] !== "string") throw new Error();
          allowed[key] = selections[key];
        }
        if (Object.hasOwn(selections, "view")) {
          if (!views.includes(selections.view)) throw new Error();
          allowed.view = selections.view;
        }
        imported.runs[id] = allowed;
      }
    }
    if (!Object.keys(imported).length) throw new Error();
    const copy = JSON.stringify(imported);
    sessionStorage.setItem(tokenKey, operatorToken);
    sessionStorage.setItem("noetic-workspace-v1", copy);
    if (sessionStorage.getItem(tokenKey) !== operatorToken
        || sessionStorage.getItem("noetic-workspace-v1") !== copy
        || localStorage.getItem("noetic-workspace-v1") !== raw) throw new Error();
    localStorage.removeItem("noetic-workspace-v1");
    // Do not persist the current form over the verified import during reload.
    operatorToken = "";
    ++accessVersion;
    $("private-workspace").hidden = true;
    $("private-workspace").replaceChildren();
    location.reload();
  } catch (_) {
    text("previous-drafts-status", "Previous drafts could not be imported. The original entry has not been removed. Check its format and browser storage access before retrying.");
  }
}

function forgetPreviousDrafts() {
  if (!operatorToken || $("private-workspace").hidden) return;
  if (!window.confirm("Permanently forget previous drafts from this browser? This cannot be undone.")) return;
  try {
    localStorage.removeItem("noetic-workspace-v1");
    $("previous-drafts").hidden = true;
  } catch (_) {
    text("previous-drafts-status", "Previous drafts could not be removed. Check browser storage access before retrying.");
  }
}

function switchPage(page, focusTarget = null) {
  savedUI.positions ||= {};
  if (page !== currentPage) savedUI.positions[currentPage] = $("run-detail").scrollTop;
  const changed = currentPage !== page;
  const moveFocus = Boolean(focusTarget);
  currentPage = page;
  $("effort-operation-controls").hidden = !["workspace","new","history","memory","purposes"].includes(page);
  scopeControls();
  for (const button of document.querySelectorAll("[data-page]")) {
    const active = button.dataset.page === page;
    button.setAttribute("aria-pressed", String(active));
    $(`${button.dataset.page}-page`).hidden = !active;
  }
  text("summary-selection", selectedId ? `Selected run: ${selectedId}` : "Select a run before summarizing.");
  $("summary-generate").disabled = !selectedId || selectedDetail?.backend === "opermem-reviewed";
  if (changed) $("run-detail").scrollTop = savedUI.positions[page] || 0;
  if (moveFocus) $(focusTarget).focus();
  persistUI();
  document.dispatchEvent(new CustomEvent("noetic:page", {detail:{page}}));
}

function text(id, value) {
  const element = $(id);
  const next = String(value ?? "Not recorded");
  if (element.textContent !== next) element.textContent = next;
}

function node(tag, value, className) {
  const element = document.createElement(tag);
  if (value !== undefined) element.textContent = String(value);
  if (className) element.className = className;
  return element;
}

function replaceContents(id, items) {
  const parent = $(id);
  const focused = document.activeElement;
  const key = [...parent.querySelectorAll("button")].includes(focused) ? focused?.dataset?.focusKey : null;
  const position = parent.scrollTop;
  const retained = new Map([...parent.children].filter((item) => item.dataset.renderKey).map((item) => [item.dataset.renderKey, item]));
  items = items.map((item) => {
    const previous = retained.get(item.dataset.renderKey);
    return previous?.textContent === item.textContent ? previous : item;
  });
  parent.replaceChildren(...items);
  parent.scrollTop = position;
  if (key) [...parent.querySelectorAll("button")].find((button) => button.dataset.focusKey === key)?.focus({ preventScroll: true });
}

function error(id, message) {
  text(id, message || "");
  $(id).hidden = !message;
}

function date(value) {
  if (!value) return "Not recorded";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function title(goal) {
  return goal.split(/\r?\n/).find((line) => line.trim()) || goal;
}

function tone(value) {
  if (["accepted", "accept", "passed", "complete", "completed"].includes(value)) return "good";
  if (["failed", "rejected", "reject", "timed_out", "interrupted", "blocked", "cancelled"].includes(value)) return "bad";
  return "pending";
}

async function fetchJSON(url, options = {}) {
  if (/^\/api\/runs(?:[/?]|$)/.test(url)) {
    const parsed = new URL(url,location.origin);
    const declared = parsed.searchParams.has("effort_root") || parsed.searchParams.has("scope");
    if (!declared && options.method !== "POST") url = scopedURL(url);
    if (options.method === "POST") {
      const body = JSON.parse(options.body || "{}");
      if (!Object.hasOwn(body,"effort_root") && !Object.hasOwn(body,"scope")) options = {...options,body:JSON.stringify({...body,...operationSelection()})};
    }
  }
  if (!operatorToken) throw new Error("Local operator is locked.");
  const version = accessVersion;
  const controller = new AbortController();
  const milliseconds = options.method === "POST" ? 180000 : 45000;
  const timeout = setTimeout(() => controller.abort(), milliseconds);
  try {
    const response = await fetch(url, { ...options, headers: { ...options.headers, Authorization: `Bearer ${operatorToken}` }, cache: "no-store", signal: controller.signal });
    if (version !== accessVersion) throw new Error("Local operator is locked.");
    if (response.status === 401) { lockAccess(); throw new Error("Local operator pairing required."); }
    const body = await response.json();
    if (version !== accessVersion) throw new Error("Local operator is locked.");
    if (!response.ok) {
      const failure = new Error(body.error || `HTTP ${response.status}`);
      failure.runId = body.run_id;
      throw failure;
    }
    return body;
  } catch (failure) {
    if (failure.name === "AbortError") throw new Error("Request timed out; the server action may still be running. Refresh before repeating it.");
    throw failure;
  } finally {
    clearTimeout(timeout);
  }
}

function renderRuns(runs) {
  allRuns = runs;
  const roles = [...new Set(runs.flatMap((run) => (run.population || []).map((actor) => actor.role)))].sort();
  setOptions("role-filter", [["", "All roles"], ...roles.map((role) => [role, role])], "");
  if (initialForms["role-filter"] && roles.includes(initialForms["role-filter"])) {
    $("role-filter").value = initialForms["role-filter"];
    delete initialForms["role-filter"];
  }
  const filtered = runs.filter((run) => (!$("status-filter").value || run.state === $("status-filter").value)
    && (!$("pattern-filter").value || (run.pattern || "legacy") === $("pattern-filter").value)
    && (!$("role-filter").value || (run.population || []).some((actor) => actor.role === $("role-filter").value))
    && JSON.stringify([run.goal, run.run_id, run.workspace, run.population]).toLowerCase().includes($("run-filter").value.toLowerCase()));
  const signature = JSON.stringify(filtered.map((run) => ({ ...run, application: { ...run.application, observed_at: null } })));
  if (signature !== listSignature) {
    const focused = document.activeElement?.dataset?.runId;
    listSignature = signature;
    const items = filtered.map((run) => {
      const button = node("button", undefined, "run-option");
      button.type = "button";
      button.dataset.runId = run.run_id;
      const header = node("span", undefined, "run-option-heading");
      header.append(node("span", run.state.replaceAll("_", " "), `state ${tone(run.state)}`),
        node("span", run.run_id.slice(0, 8), "short-id"));
      button.append(header, node("span", title(run.goal), "run-option-goal"), node("small", run.correspondence?.effort_root ? `Effort ${run.correspondence.effort_root} · discipline ${run.correspondence.discipline_id} / execution ${run.correspondence.execution_id}` : "Original namespace · unassigned"),
        node("span", `${run.current_phase ? run.current_phase + " · " : ""}${run.last_event_at ? new Date(run.last_event_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "No activity recorded"}`, "run-option-time"));

      button.addEventListener("click", () => selectRun(run.run_id));
      return button;
    });
    $("run-list").replaceChildren(...(items.length ? items : [node("p", "No readable runs in this directory.", "rail-note")]));
    if (focused) [...$("run-list").children].find((item) => item.dataset.runId === focused)?.focus({ preventScroll: true });
    renderPopulation(filtered);
  }
  for (const button of $("run-list").querySelectorAll("button")) {
    button.setAttribute("aria-current", String(button.dataset.runId === selectedId));
  }
  text("run-count", `${filtered.length} / ${runs.length}`);
  document.dispatchEvent(new CustomEvent("noetic:runs", {detail:{runs,observation:runRegister}}));
}

function switchView(view, reveal = false) {
  const inspecting = view !== "session";
  $("session-view").hidden = false;
  for (const button of document.querySelectorAll("[data-view]")) {
    const active = button.dataset.view === view;
    button.setAttribute("aria-pressed", String(active));
    if (button.dataset.view !== "session") $(`${button.dataset.view}-view`).hidden = !active;
  }
  $("evidence-drawer").open = inspecting;
  if (reveal) (inspecting ? $("evidence-drawer") : $("session-view")).scrollIntoView({ block: "start", behavior: "instant" });
  if (selectedId) {
    savedUI.runs ||= {};
    savedUI.runs[selectedId] = { ...savedUI.runs[selectedId], view };
  }
  persistUI();
}

async function selectRun(id, evidence = null) {
  ++reuseVersion;
  persistUI();
  const changed = id !== selectedId;
  selectedId = id;
  selectedDetail = null;
  timelineSignature = "";
  kernelSignature = "";
  workbenchSignature = "";
  sessionSignature = "";
  ++sessionVersion;
  ++actorLogVersion;
  if (changed) {
    $("reviewed-evidence-content").replaceChildren(); $("reviewed-evidence").open=false; $("reviewed-review").open=false; text("reviewed-recovery-status", "");
    $("follow-current").checked = savedUI.runs?.[id]?.follow !== false;
    $("session-agent-list").replaceChildren();
    $("session-select").replaceChildren();
    delete $("session-select").dataset.options;
    $("actor-select").replaceChildren();
    $("artifact-select").replaceChildren();
    delete $("actor-select").dataset.options;
    delete $("artifact-select").dataset.options;
    text("actor-log-text", "");
    error("cancel-error", "");
    error("action-error", "");
    error("reuse-error", "");
    text("action-result", "");
  }
  $("structured-register") && ($("structured-register").open = true);
  switchPage("workspace");
  if (changed) $("run-detail").scrollTop = 0;
  $("operator-rail").classList.remove("navigation-open");
  $("toggle-navigation").setAttribute("aria-expanded", "false");
  text("toggle-navigation", "Sessions");
  $("selected-run").hidden = true;
  $("empty-state").hidden = true;
  for (const button of $("run-list").querySelectorAll("button")) {
    button.setAttribute("aria-current", String(button.dataset.runId === id));
  }
  if (evidence) {
    const source = evidence.source;
    if (["work.md", "review.md", "review.recorded.evidence"].includes(source)) {
      $("report-select").value = source === "review.recorded.evidence" ? "review.recorded" : source;
      switchView("reports");
    } else {
      switchView("timeline");
    }
  }
  await loadDetail();
  if (selectedId !== id) return;
  if (evidence && selectedDetail?.backend === "opermem-reviewed") {
    if (evidence.source_ref?.step) {$("session-select").value=evidence.source_ref.step;$("follow-current").checked=false;switchView("session",true);await loadSession();}
    else {$("evidence-drawer").open=true;$("reviewed-evidence").open=true;$("reviewed-evidence").scrollIntoView({block:"start"});}
    persistUI();return;
  }
  if (evidence && !evidence.activation_id && !evidence.artifact_id) {
    switchView(["work.md", "review.md", "review.recorded.evidence"].includes(evidence.source) ? "reports" : "timeline", true);
  }
  if (evidence?.activation_id) {
    $("follow-current").checked = false;
    $("session-select").value = evidence.activation_id;
    $("actor-select").value = evidence.activation_id;
    renderActor();
    text("actor-log-text", "");
  }
  if (evidence?.artifact_id) {
    $("artifact-select").value = evidence.artifact_id;
    switchView("controller", true);
    renderArtifact();
    loadActorLog();
  } else if (evidence?.activation_id) {
    switchView("session", true);
    loadSession(true);
    loadActorLog();
  }
  persistUI();
}

function renderEvidence(prefix, source) {
  if (!selectedDetail) return;
  const { artifacts, status, events, journal_path: journalPath } = selectedDetail;
  let artifact = artifacts[source];
  if (source === "review.recorded") {
    const reviewEvent = [...events].reverse().find((event) => event.kind === "review.recorded");
    artifact = status.review && reviewEvent ? {
      text: status.review.evidence,
      source_path: `${journalPath} / event #${reviewEvent.sequence} / review.recorded.evidence`,
    } : null;
  }
  text(`${prefix}-source`, artifact?.source_path || source);
  text(`${prefix}-note`, !artifact ? "Not recorded or not retained for this run."
    : artifact.error ? `Cannot read this evidence: ${artifact.error}`
    : artifact.truncated ? `Showing the first ${(selectedDetail.artifact_limit_bytes || 1048576).toLocaleString()} bytes. Full evidence remains in the local file.`
    : artifact.text === "" ? "File exists and is empty." : "Retained text; not an independent validation by this interface.");
  text(`${prefix}-text`, artifact?.text || "");
}

const eventWindows = new Map();
function renderEventWindow(id, events, createRow) {
  const list = $(id);
  let state = eventWindows.get(id);
  if (!state || state.run !== selectedId || state.list !== list) {
    $(`${id}-disclosure`)?.remove();
    const controls = node("div", undefined, "section-heading event-disclosure"), coverage = node("span", undefined, "source"), more = node("button", "Load earlier events", "secondary-button");
    controls.id = `${id}-disclosure`; coverage.setAttribute("role", "status"); more.type = "button";
    controls.append(coverage, more); list.before(controls);
    state = {run:selectedId, list, controls, coverage, more, count:12, all:false, start:Math.max(0,events.length-12), total:events.length, rows:new Map()};
    eventWindows.set(id, state);
    more.addEventListener("click", () => {
      const current = eventWindows.get(id); current.count = Math.max(current.count, current.events.length-current.start) + 12; current.all = current.count >= current.events.length;
      renderEventWindow(id, current.events, current.createRow);
    });
  }
  if (state.all) state.count = Math.max(state.count, events.length);
  const inspecting = list.contains(document.activeElement) || Boolean(list.querySelector("details[open]"));
  const start = Math.max(0, events.length-state.count);
  state.start = inspecting ? Math.min(state.start, start) : start;
  state.total = events.length; state.events = events; state.createRow = createRow;
  const retained = new Map(), rows = events.slice(state.start).map((event, index) => {
    const identity = String(event.id ?? event.sequence ?? state.start+index), signature = JSON.stringify(event), previous = state.rows.get(identity);
    const row = previous?.signature === signature ? previous.row : createRow(event);
    retained.set(identity, {row, signature}); return row;
  });
  state.rows = retained;
  for (const child of [...list.children]) if (!rows.includes(child)) child.remove();
  rows.forEach((row, index) => { if (list.children[index] !== row) list.insertBefore(row, list.children[index] || null); });
  state.coverage.textContent = state.start ? `Showing latest ${rows.length} of ${events.length} events. Earlier events remain available.` : `Showing all ${events.length} events.`;
  state.more.textContent = state.start ? `Load earlier ${Math.min(12,state.start)} events` : "All events shown"; state.more.disabled = state.start === 0;
}

function eventMeaning(event) {
  const inner = event.kind === "controller.event" ? event.data : event;
  const data = inner.data || {};
  const heading = inner.kind === "transition"
    ? `${data.phase}: ${data.from} -> ${data.to} / ${data.on}` : inner.kind;
  const label = Object.entries(data).map(([key, value]) =>
    `${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`).join(" / ");
  return { heading, label, data, inner };
}

function setOptions(id, entries, fallback) {
  const select = $(id);
  const signature = JSON.stringify(entries);
  if (select.dataset.options === signature) return;
  const previous = select.value;
  select.replaceChildren(...entries.map(([value, label]) => {
    const option = node("option", label);
    option.value = value;
    return option;
  }));
  select.value = entries.some(([value]) => value === previous) ? previous : fallback || entries[0]?.[0] || "";
  select.dataset.options = signature;
}

function artifactStanding(state, artifact) {
  if (artifact.partial) return "Partial / not accepted or effective";
  const slots = Object.entries(state.slots).filter(([, id]) => id === artifact.id).map(([slot]) => slot);
  if (slots.some((slot) => slot.startsWith("accepted."))) return `Current accepted / ${slots.join(", ")}`;
  if (slots.some((slot) => slot.startsWith("effective."))) return `Current effective / ${slots.join(", ")}`;
  if (artifact.origin === "external") return `External input / ${slots.join(", ")}`;
  if (state.subject_artifact_id === artifact.id) return "Current subject / not accepted";
  if (state.review_artifact_id === artifact.id || state.feedback.at(-1) === artifact.id) return "Current feedback / not a phase result";
  return "Historical / not a current accepted or effective result";
}

function renderArtifact() {
  const state = selectedDetail?.controller;
  const artifact = state?.artifacts[$("artifact-select").value];
  if (!artifact) return;
  text("artifact-standing", artifactStanding(state, artifact));
  text("artifact-provenance", `${artifact.id} / ${artifact.type} / producer ${artifact.produced_by || "external"} / activation ${artifact.activation_id || "none"} / phase ${artifact.phase || "none"} / generation ${artifact.generation ?? "n/a"} / visit ${artifact.visit ?? "n/a"}`);
  text("artifact-content", JSON.stringify(artifact.content, null, 2));
  const { content, ...metadata } = artifact;
  text("artifact-data", JSON.stringify(metadata, null, 2));
}

function renderActor() {
  const state = selectedDetail?.controller;
  const activation = state?.activations[$("actor-select").value];
  if (!activation) return;
  const actor = state.actors[activation.actor_id];
  text("actor-summary", `${actorIdentity(activation)} / ${actor.id} / ${activation.role} / ${activation.phase} / ${activation.mode} / generation ${activation.generation} / visit ${activation.visit} / activation ${activation.status} / actor ${actor.status} / session ${actor.session_ref || "not committed"}`);
  text("actor-data", JSON.stringify({ actor, activation,
    lifecycle_events: state.events.filter((event) => event.data.activation_id === activation.id),
  }, null, 2));
  for (const item of $("actor-list").children) {
    const current = String(item.dataset.activation === activation.id);
    item.setAttribute("aria-current", current);
    item.querySelector("button")?.setAttribute("aria-current", current);
  }
}

async function loadActorLog() {
  const id = selectedId;
  const activation = $("actor-select").value;
  const name = $("actor-log-select").value;
  const version = ++actorLogVersion;
  if (!selectedDetail || !activation) {
    $("session-transcript").replaceChildren(node("p", "No agent output retained for this session yet.", "output-empty"));
    text("session-note", "Waiting for agent output");
    return;
  }
  const source = `${id} / ${activation} / ${name}`;
  if ($("actor-log-source").dataset.selection !== source) {
    $("actor-log-source").dataset.selection = source;
    text("actor-log-text", "");
    text("actor-log-source", source);
    text("actor-log-note", "Reading retained file...");
  }
  try {
    const result = await fetchJSON(`/api/runs/${encodeURIComponent(id)}/activations/${encodeURIComponent(activation)}/logs/${encodeURIComponent(name)}`);
    if (version !== actorLogVersion || id !== selectedId) return;
    text("actor-log-source", result.source_path);
    text("actor-log-text", result.text);
    text("actor-log-note", `${result.truncated ? `First ${result.artifact_limit_bytes.toLocaleString()} bytes; truncated.` : result.text === "" ? "File exists and is empty." : "Retained text, not independent validation."} Fetched ${date(result.observed_at)}.`);
  } catch (failure) {
    if (version !== actorLogVersion || id !== selectedId) return;
    text("actor-log-text", "");
    text("actor-log-source", source);
    text("actor-log-note", `Cannot read retained file: ${failure.message}`);
  }
}

function renderController(detail) {
  const state = detail.controller;
  $("controller-summary").hidden = false;
  $("controller-tab").hidden = !state;
  $("legacy-execution").hidden = Boolean(state);
  if (!state) {
    if ($("controller-tab").getAttribute("aria-pressed") === "true") switchView("session");
    return;
  }
  const phase = state.pattern.phases[state.phase_index];
  const current = state.activations[state.current_activation];
  text("controller-source", `${detail.controller_path} / authoritative snapshot; outer journal label: ${detail.status.journal_state}`);
  text("controller-version", `KERNEL VERSION ${state.version}`);
  text("controller-pattern", `${state.pattern.name || state.pattern.kind} / ${state.pattern.kind}`);
  text("controller-machine", `${state.status} / ${state.machine_state}${state.reason ? ` / ${state.reason}` : ""}`);
  text("controller-phase", `${phase.id} / ${phase.role} / index ${state.phase_index}${state.status !== "active" ? " (terminal position)" : ""}`);
  text("controller-generation", `Generation ${state.generation} / visit ${state.visits[phase.id]}`);
  text("controller-budgets", `Remediations: generation ${state.generation} of ${state.max_remediations} per phase; returns: ${state.returns_used} of ${state.max_returns} run-wide`);
  text("controller-actor", current ? `${current.actor_id} / ${actorIdentity(current)} / ${current.id} / ${current.role} / ${current.status}` : "None / kernel is terminal");
  $("cancel-pattern").hidden = state.status !== "active" && detail.application?.cleanup_confirmed === true;
  text("cancel-pattern", state.status === "active" ? "Stop task" : "Clean up processes");
  $("cancel-pattern").disabled = cancelling.has(selectedId);
  text("cancel-note", state.status !== "active" ? `Kernel terminal state: ${state.status}. Cleanup does not change this outcome. Only known ownership can be terminated; zombies require parent reaping.`
    : detail.cancel_requested ? "Cancellation requested; awaiting the driver. The kernel is still active."
    : "Cancellation requests the harness to stop this pattern; it does not accept work.");

  const signature = JSON.stringify(state);
  if (signature !== kernelSignature) {
    kernelSignature = signature;
    const prefix = state.pattern.kind === "verified_sequence" ? "accepted" : "effective";
    $("controller-phases").replaceChildren(...state.pattern.phases.map((item, index) => {
      const li = node("li");
      if (index === state.phase_index && state.status === "active") li.setAttribute("aria-current", "step");
      li.append(node("h4", `${item.id} / ${item.role}`), node("p", `Visits: ${state.visits[item.id]}${index === state.phase_index ? " / kernel position" : ""}`),
        node("p", `${prefix}.${item.id}: ${state.slots[`${prefix}.${item.id}`] || "not bound"}`));
      return li;
    }));
    const activations = Object.values(state.activations).sort((a, b) => a.ordinal.localeCompare(b.ordinal, "en", { numeric: true }));
    text("actor-count", `${Object.keys(state.actors).length} ACTORS / ${activations.length} ACTIVATIONS`);
    setOptions("actor-select", activations.map((a) => [a.id, `${actorIdentity(a)} / ${a.phase} / ${a.role} / ${a.status}`]), state.current_activation || activations.at(-1)?.id);
    $("actor-list").replaceChildren(...activations.map((a) => {
      const li = node("li");
      li.dataset.activation = a.id;
      const button = node("button", `${actorIdentity(a)} / ${a.actor_id} / ${a.phase} / ${a.role}`);
      button.type = "button";
      button.addEventListener("click", () => {
        $("actor-select").value = a.id;
        renderActor();
        loadActorLog();
        button.focus();
      });
      const actor = state.actors[a.actor_id];
      const lifecycle = state.events.filter((e) => e.data.activation_id === a.id &&
        (e.kind.startsWith("activation.") || ["runtime.failed", "run.cancelled"].includes(e.kind)))
        .map((e) => `${e.kind} (v${e.version})`).join(" -> ");
      li.append(button, node("p", `${a.id} / ${a.mode} / generation ${a.generation} / visit ${a.visit} / activation ${a.status} / actor ${actor.status}${a.id === state.current_activation ? " / CURRENT" : ""}`),
        node("p", `Session: ${actor.session_ref || "not committed"}`, "source"), node("p", lifecycle));
      if (a.failure_reason) li.append(node("p", a.failure_reason, "bad"));
      return li;
    }));
    const artifacts = Object.values(state.artifacts).sort((a, b) => a.id.localeCompare(b.id, "en", { numeric: true }));
    text("artifact-count", `${artifacts.length} ARTIFACTS`);
    setOptions("artifact-select", artifacts.map((a) => [a.id, `${a.id} / ${a.type} / ${artifactStanding(state, a)}`]),
      state.subject_artifact_id || state.slots[`${prefix}.${phase.id}`] || artifacts.at(-1)?.id);
    const open = new Set([...$("controller-events").querySelectorAll("details[open]")].map((item) => item.dataset.eventId));
    text("transition-count", `${state.events.filter((e) => e.kind === "transition").length} TRANSITIONS / ${state.events.length} EVENTS`);
    renderEventWindow("controller-events", state.events, (event) => {
      const li = node("li");
      const meta = node("div", undefined, "event-meta");
      meta.append(node("span", event.id, "event-number"), node("span", `Version ${event.version}`));
      const body = node("div", undefined, "event-body");
      const meaning = eventMeaning(event);
      const raw = node("details");
      raw.dataset.eventId = event.id;
      raw.open = open.has(event.id);
      raw.append(node("summary", "Kernel event data"), node("pre", JSON.stringify(event, null, 2)));
      body.append(node("h4", meaning.heading), node("p", meaning.label), raw);
      li.append(meta, body);
      return li;
    });
  }
  renderActor();
  renderArtifact();
  if (!$("controller-view").hidden) loadActorLog();
}

function renderDetail(detail) {
  $("reviewed-result").hidden = detail.backend !== "opermem-reviewed";
  $("reviewed-evidence").hidden = detail.backend !== "opermem-reviewed";
  if (detail.backend === "opermem-reviewed") { renderReviewedDetail(detail); return; }
  $("summary-generate").disabled = false;
  queueMicrotask(() => document.dispatchEvent(new CustomEvent("noetic:run-detail", {detail:{run:detail}})));
  const readingPosition = $("run-detail").scrollTop;
  const status = detail.status;
  text("run-id", status.run_id);
  text("run-goal", title(status.goal));
  text("task-body", status.goal);
  text("run-state", status.state.replaceAll("_", " "));
  $("run-state").className = `state ${tone(status.state)}`;
  const notes = {
    accepted: "Acceptance is recorded in the journal. This interface does not approve work.",
    rejected: "The recorded review rejected this run. Inspect the review evidence.",
    awaiting_review: "Independent acceptance has not been recorded. Inspect the recorded verification coverage.",
    unfinished: "No terminal event. The process may be running or may have stopped; liveness is unknown.",
  };
  text("state-note", detail.controller
    ? detail.controller.pattern.kind === "recurrent_operations"
      ? "Kernel-authoritative cognitive pattern state. P1-P4 are attentiveness, intelligence, reasonableness and responsibility, not development phases. Completed does not mean generic QA acceptance or Telos completion."
      : "Kernel-authoritative development pattern state. Accepted phase bindings record subject-specific QA; completion is not approval by this interface or Telos completion."
    : notes[status.state] || "Recorded outcome only. Inspect the event sequence and command logs for context.");
  text("last-event", date(status.last_event_at));
  text("detail-observed", date(detail.observed_at));
  text("workspace", status.workspace);
  text("goal-ref", status.goal_ref || "No goal reference recorded");
  text("telos-chain", status.telos?.chain_id || "No link recorded");
  text("telos-subgoal", status.telos?.subgoal_id || "No link recorded");
  text("telos-result", status.telos_error ? `Result synchronization error: ${status.telos_error}`
    : status.telos_result ? `Recorded Telos result: ${status.telos_result.subgoal_status || status.telos_result.state}`
    : "No Telos result recorded. This view does not query or update the chain.");

  const outcomes = ["work", "verify", "review"].map((step) => {
    const recorded = status.steps[step];
    const value = step === "review" && status.review ? status.review.verdict
      : recorded ? (recorded.state || "started; no finish recorded") : "not recorded";
    const outcome = node("div", undefined, "outcome");
    outcome.append(node("h4", step), node("p", value, tone(value)));
    if (recorded?.returncode != null) outcome.append(node("small", `Exit ${recorded.returncode}`));
    if (step === "review" && status.review) outcome.append(node("small", status.review.reviewer));
    return outcome;
  });
  $("outcomes").replaceChildren(...outcomes);
  renderController(detail);
  renderWorkbench(detail);
  text("event-count", `${detail.events.length} EVENTS`);
  text("journal-source", detail.journal_path);
  const signature = JSON.stringify(detail.events);
  if (signature !== timelineSignature) {
    const openEvents = new Set([...$("timeline").querySelectorAll("details[open]")].map((item) => item.dataset.sequence));
    timelineSignature = signature;
    renderEventWindow("timeline", detail.events, (event) => {
      const item = node("li");
      const meta = node("div", undefined, "event-meta");
      meta.append(node("span", `#${String(event.sequence).padStart(2, "0")}`, "event-number"),
        node("time", date(event.occurred_at)));
      const time = meta.querySelector("time");
      time.dateTime = event.occurred_at;
      const body = node("div", undefined, "event-body");
      const meaning = eventMeaning(event);
      body.append(node("h4", meaning.heading));
      const data = event.data;
      const label = event.kind === "controller.event" ? `${meaning.inner.id} / kernel v${meaning.inner.version} / ${meaning.label}`
        : [data.step, data.state, data.verdict,
          data.returncode != null ? `exit ${data.returncode}` : null, data.error].filter(Boolean).join(" / ");
      if (label) body.append(node("p", label, tone(data.verdict || data.state)));
      const raw = node("details");
      raw.dataset.sequence = String(event.sequence);
      raw.open = openEvents.has(String(event.sequence));
      raw.append(node("summary", "Event data"), node("pre", JSON.stringify(data, null, 2)));
      body.append(raw);
      item.append(meta, body);
      return item;
    });
  }
  renderEvidence("report", $("report-select").value);
  renderEvidence("log", $("log-select").value);
  $("empty-state").hidden = true;
  $("selected-run").hidden = false;
  $("run-detail").scrollTop = readingPosition;
}

async function loadDetail() {
  const id = selectedId;
  if (!id) return;
  const version = ++detailVersion;
  try {
    const detail = await fetchJSON(`/api/runs/${encodeURIComponent(id)}`);
    if (version !== detailVersion || id !== selectedId) return;
    const first = !selectedDetail;
    selectedDetail = detail;
    renderDetail(detail);
    if (first) {
      const selections = savedUI.runs?.[id] || {};
      $("follow-current").checked = selections.follow !== false;
      for (const key of selectionIds) {
        if (key === "session-select" && $("follow-current").checked) continue;
        if (selections[key] && [...$(key).children].some((option) => option.value === selections[key])) $(key).value = selections[key];
      }
      workbenchSignature = ""; renderWorkbench(detail);
      switchView("session");
      renderActor(); renderArtifact(); renderPhase(); renderComparison();
    }
    if (currentPage === "workspace") loadSession();
    error("detail-error", "");
  } catch (failure) {
    if (version !== detailVersion || id !== selectedId) return;
    error("detail-error", `Cannot refresh run ${id}: ${failure.message}${selectedDetail ? " Showing previously fetched evidence." : ""}`);
    $("cancel-pattern").disabled = true;
    for (const name of ["advance-one", "advance-all", "pause-pattern"]) $(name).disabled = true;
  }
}

async function refresh() {
  if (!operatorToken || $("private-workspace").hidden || refreshPending) return;
  refreshPending = true;
  $("refresh").disabled = true;
  const scopeVersion = operationVersion;
  observeRuns({selection:operationSelection(),status:"loading"});
  try {
    const result = await fetchJSON(scopedURL("/api/runs"));
    if (scopeVersion !== operationVersion) return;
    text("runs-root", result.runs_dir);
    text("run-warning", result.warnings.join(" "));
    $("run-warning").hidden = result.warnings.length === 0;
    if (!selectedId && result.runs.length) selectedId = result.runs[0].run_id;
    error("fetch-error", "");
    observeRuns({status:"observed",observedAt:result.observed_at || new Date().toISOString(),warnings:result.warnings,error:""},false);
    renderRuns(result.runs);
    text("poll-status", `Updated ${new Date((result.observed_at || Date.now())).toLocaleTimeString()} · 5s refresh`);
  } catch (failure) {
    if (scopeVersion === operationVersion) {
      error("fetch-error", `Cannot refresh the run register: ${failure.message} Previously fetched evidence may be stale.`);
      observeRuns({status:"unavailable",error:failure.message});
    }
  } finally {
    if (scopeVersion === operationVersion) {
      await loadDetail();
      if (isReviewed()) await loadReviewedLaunches();
    }
    $("refresh").disabled = false;
    refreshPending = false;
    if (scopeVersion !== operationVersion) queueMicrotask(refresh);
  }
}

$("refresh").addEventListener("click", refresh);
for (const button of document.querySelectorAll("[data-view]")) {
  button.addEventListener("click", () => {
    switchView(button.dataset.view, true);
    if (button.dataset.view === "controller") loadActorLog();
    if (button.dataset.view === "session") loadSession(true);
  });
}
$("artifact-select").addEventListener("change", renderArtifact);
$("actor-select").addEventListener("change", () => { renderActor(); loadActorLog(); });
$("actor-log-select").addEventListener("change", loadActorLog);
$("cancel-pattern").addEventListener("click", async () => {
  const id = selectedId, scopeVersion = operationVersion;
  if (!selectedDetail?.controller || cancelling.has(id)) return;
  const active = selectedDetail.controller.status === "active";
  if (!window.confirm(active
    ? `Cancel pattern for run ${id}? This requests the harness to stop; it does not accept or complete the work.`
    : `Clean up processes for run ${id}? Only known ownership is terminated. The terminal outcome is unchanged; zombies cannot be reaped by signalling.`)) return;
  cancelling.add(id);
  $("cancel-pattern").disabled = true;
  error("cancel-error", "");
  text("cancel-note", active ? "Sending cancellation request; terminal state is not yet known." : "Checking process cleanup; terminal outcome is unchanged.");
  try {
    const result = await fetchJSON(`/api/runs/${encodeURIComponent(id)}/cancel`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirm: true }),
    });
    if (id === selectedId && scopeVersion === operationVersion) text("cancel-note", result.message);
  } catch (failure) {
    if (id === selectedId && scopeVersion === operationVersion) error("cancel-error", `Cancellation response unavailable: ${failure.message} Refreshing authority; do not assume cancellation completed.`);
  } finally {
    cancelling.delete(id);
    if (id === selectedId && scopeVersion === operationVersion) await loadDetail();
  }
});
$("report-select").addEventListener("change", () => renderEvidence("report", $("report-select").value));
$("log-select").addEventListener("change", () => renderEvidence("log", $("log-select").value));

function renderPopulation(runs) {
  const population = [], attention = [], history = [];
  for (const run of runs) {
    for (const actor of (run.population || []).filter((a) => !$("role-filter").value || a.role === $("role-filter").value)) {
      const button = node("button", `${actorIdentity(actor,run.correspondence)} / ${actor.actor_id} / ${actor.role}`, "population-item");
      button.type = "button";
      button.dataset.focusKey = `${run.run_id}/${actor.id}`;
      button.dataset.renderKey = button.dataset.focusKey;
      button.append(node("span", `${run.run_id.slice(0, 8)} / ${actor.phase} / g${actor.generation} / visit ${actor.visit} / ${actor.status}`),
        node("span", `Configured: ${actor.client || "not recorded"} / ${actor.configured_model || "client default"}`),
        node("span", `Session: ${actor.session_ref || "not committed"}`));
      button.addEventListener("click", () => selectRun(run.run_id, { activation_id: actor.id }));
      population.push(button);
    }
    for (const finding of run.attention || []) {
      const button = node("button", `${finding.kind}: ${finding.message}`, "attention-item");
      button.type = "button";
      button.dataset.focusKey = `${run.run_id}/${finding.artifact_id || finding.kind}`;
      button.dataset.renderKey = button.dataset.focusKey;
      button.append(node("span", `${run.run_id.slice(0, 8)} / ${finding.phase || run.current_phase || "run"} / current kernel ${run.state}`));
      button.addEventListener("click", () => selectRun(run.run_id, finding));
      attention.push(button);
    }
    const row = node("article", undefined, "history-row");
    row.dataset.renderKey = run.run_id;
    const button = node("button", title(run.goal));
    button.type = "button";
    button.dataset.focusKey = run.run_id;
    button.addEventListener("click", () => selectRun(run.run_id));
    row.append(button, node("p", `${run.run_id} / ${run.pattern || "legacy"} / ${run.state} / ${run.current_phase || "journal"}`, "source"),
      node("p", `${run.population?.length || 0} recorded actors / driver ${run.application?.activity || "unknown"} / ${run.workspace || "workspace not recorded"}`));
    history.push(row);
  }
  replaceContents("population-list", population.length ? population : [node("p", "No matching recorded actors.", "rail-note")]);
  text("population-count", `(${population.length})`);
  replaceContents("attention-feed", attention.length ? attention : [node("p", "No matching material findings recorded.", "rail-note")]);
  replaceContents("history-list", history.length ? history : [node("p", "No runs match the register filters.")]);
}

function renderSessionAgents(entries) {
  replaceContents("session-agent-list", entries.map(([id, label, status]) => {
    const button = node("button", undefined, "agent-option");
    button.type = "button";
    button.dataset.focusKey = id;
    button.dataset.renderKey = `${selectedId}/${id}`;
    button.setAttribute("aria-current", String($("session-select").value === id));
    button.append(node("span", label), node("small", status));
    button.addEventListener("click", () => {
      $("session-select").value = id; $("follow-current").checked = false;
      renderSessionAgents(entries); persistUI(); loadSession();
    });
    return button;
  }));
  for (const button of $("session-agent-list").querySelectorAll("button")) button.setAttribute("aria-current", String(button.dataset.focusKey === $("session-select").value));
}

let handoffVersion = 0;
async function loadProjectHandoff() {
  const id = selectedId, version = ++handoffVersion, scopeVersion = operationVersion;
  $("workspace-result").hidden = true; $("workspace-apply").hidden = true;
  if (!id || !selectedDetail?.controller) return;
  try {
    const value = await fetchJSON(`/api/runs/${id}/project-changes`);
    if (id !== selectedId || version !== handoffVersion || scopeVersion !== operationVersion) return;
    $("workspace-result").hidden = false;
    $("workspace-result-summary").replaceChildren(...(value.summary ? [window.NoeticRichText ? window.NoeticRichText(value.summary, {id, kind:"run", selection:operationSelection(), viewVersion:operationVersion}) : node("pre", value.summary)] : []));
    $("workspace-result-review").hidden = !value.review;
    text("workspace-review-report", value.review?.report || "");
    $("workspace-review-open").dataset.activation = value.review?.activation_id || "";
    text("workspace-result-location", value.owned_worktree ? `Project: ${value.project}\nTask files: ${value.workspace}` : `Project / task folder: ${value.workspace}`);
    text("workspace-result-status", value.reason || (value.applied ? "Changes applied to the project." : "Reviewed task output retained."));
    text("workspace-result-checks", (value.verification || []).map(check => `${check.state || "recorded"}: ${JSON.stringify(check.argv)}`).join("\n"));
    text("workspace-result-files", JSON.stringify(value.changes, null, 2));
    $("workspace-apply").hidden = !value.eligible || value.applied;
  } catch (failure) {
    if (id === selectedId && version === handoffVersion && scopeVersion === operationVersion) text("workspace-apply-result", `Project changes unavailable: ${failure.message}`);
  }
}

function renderCognitiveContinuation(detail) {
  const section = $("cognitive-continuation"), body = $("cognitive-continuation-body");
  const state = detail?.controller;
  const applicable = Boolean(state && state.pattern?.kind === "recurrent_operations" && state.status === "blocked");
  section.hidden = !applicable;
  if (!applicable) { body.replaceChildren(); return; }
  const feedbacks = Object.values(state.artifacts || {}).filter((a) => a.type === "cognition.feedback");
  const feedback = feedbacks.at(-1);
  const content = feedback?.content && typeof feedback.content === "object" && !Array.isArray(feedback.content) ? feedback.content : null;
  const rows = [node("p", `Kernel terminal state: blocked / ${state.reason || "reason not recorded"}.${state.reason === "return_budget_exhausted" ? " The return budget was exhausted; this interface does not restart the kernel." : ""}`)];
  rows.push(node("p", content
    ? `Newest return feedback (${feedback.id}) reason: ${typeof content.reason === "string" && content.reason ? content.reason : "not recorded"} Question: ${typeof content.question === "string" && content.question ? content.question : "not recorded"}`
    : "No cognition.feedback artifact is retained for this blocked state; no reason or question is inferred here."));
  const sourcesId = state.slots?.["external.sources"];
  const sourcesArtifact = sourcesId ? state.artifacts?.[sourcesId] : null;
  const count = Array.isArray(sourcesArtifact?.content) ? sourcesArtifact.content.length : null;
  rows.push(node("p", sourcesId && count !== null
    ? `Current external.sources binding ${sourcesId}: ${count} recorded source entries${count === 0 ? " (empty)." : "."} No sources are acquired by this view.`
    : `Current external.sources binding is not readable (${sourcesId || "slot not bound"}); no source count is inferred.`));
  const partialId = typeof content?.partial_artifact_id === "string" ? content.partial_artifact_id : null;
  const partial = partialId ? state.artifacts?.[partialId] : null;
  const hypotheses = Array.isArray(partial?.content?.hypotheses) ? partial.content.hypotheses : [];
  rows.push(node("p", partialId
    ? `Partial artifact ${partialId}: partial proposal, unverified, not accepted or effective in the kernel. ${hypotheses.length ? hypotheses.filter((h) => h && typeof h === "object").map((h) => `Proposal: ${typeof h.proposal === "string" ? h.proposal : ""} Basis: ${typeof h.basis === "string" ? h.basis : "not recorded"} Status: ${typeof h.status === "string" ? h.status : "not recorded"}`).join(" ") : "No readable proposal content is retained; no proposal is invented here."}`
    : "No partial artifact is referenced by the newest feedback."));
  const actions = node("div", undefined, "reviewed-row");
  for (const target of [partialId, feedback?.id].filter(Boolean)) {
    const button = node("button", `Inspect artifact ${target} provenance`);
    button.type = "button";
    button.addEventListener("click", () => { $("artifact-select").value = target; renderArtifact(); switchView("controller", true); });
    actions.append(button);
  }
  body.replaceChildren(...rows, actions);
}

function renderWorkbench(detail) {
  renderCognitiveContinuation(detail);
  if (detail.backend === "opermem-reviewed") { renderReviewedDetail(detail); return; }
  if (detail.backend !== "opermem-reviewed") loadProjectHandoff();
  const state = detail.controller;
  for (const id of ["phases-tab", "compare-tab"]) $(id).hidden = !state;
  $("session-tab").hidden = false;
  $("controller-summary").hidden = false;
  const info = detail.application || {};
  const config = info.configuration || {};
  text("primary-model", config.model || "Model in transcript");
  text("steering-note", state ? "Instructions are fixed. Pause at a checkpoint to hold this workflow." : "Recorded output · start a controller task for lifecycle controls.");
  if (!state) {
    for (const id of ["advance-one", "advance-all", "pause-pattern", "cancel-pattern"]) $(id).hidden = true;
    const steps = detail.status.steps;
    const available = ["work", "review"].filter(role => detail.artifacts[`${role}.stdout.log`] || steps[role]);
    setOptions("session-select", available.map(role => [role, role === "work" ? "Worker" : "Reviewer"]), available.includes("work") ? "work" : available.at(-1));
    if ($("follow-current").checked && available.length) $("session-select").value = available.includes("work") ? "work" : available.at(-1);
    renderSessionAgents(available.map(role => [role, role === "work" ? "Worker" : "Reviewer", steps[role]?.state || "recorded"]));
    text("primary-progress", ["work", "verify", "review"].map(role => `${role}: ${steps[role]?.state || "pending"}`).join(" · "));
    text("primary-agent", $("session-select").value === "review" ? "Reviewer" : "Worker");
    text("driver-activity", "Legacy journal; no controller lifecycle controls.");
    text("primary-attention", detail.status.state === "rejected" ? "Review rejected this task. Inspect the reviewer output." : "");
    $("primary-attention").hidden = detail.status.state !== "rejected";
    return;
  }
  const current = state.activations[state.current_activation];
  const phase = state.pattern.phases[state.phase_index];
  text("primary-progress", `${phase.id} · ${phase.role} · ${info.activity || state.status}`);
  text("primary-agent", current ? `Agent ${actorIdentity(current)} · ${current.role}` : "Agents finished");
  text("primary-attention", ["failed", "intervention", "cancel_requested", "pause_requested"].includes(info.activity) ? info.reason : state.reason || "");
  $("primary-attention").hidden = !$("primary-attention").textContent;
  const pending = cancelling.has(selectedId);
  for (const id of ["advance-one", "advance-all"]) {
    $(id).hidden = state.status !== "active";
    $(id).disabled = !info.can_advance || pending;
  }
  $("pause-pattern").hidden = state.status !== "active";
  $("pause-pattern").disabled = info.pause_requested || detail.cancel_requested || pending;
  text("driver-activity", `Driver: ${info.activity || "not observed"} / ${info.reason || "No runtime observation"}${info.observed_at ? ` / observed ${date(info.observed_at)}` : ""}`);
  text("driver-data", JSON.stringify(info, null, 2));
  const signature = JSON.stringify([state.version, state.pattern, info.configuration, info.activity, detail.status.run_id]);
  if (signature !== workbenchSignature) {
    workbenchSignature = signature;
    const actors = Object.values(state.activations).sort((a, b) => a.ordinal.localeCompare(b.ordinal, "en", { numeric: true }));
    const finishedWorker = state.status === "completed" ? [...actors].reverse().find(a => !["qa", "review"].includes(a.mode)) : null;
    const defaultActor = finishedWorker?.id || state.current_activation || actors.at(-1)?.id;
    setOptions("session-select", actors.map((a) => [a.id, `${actorIdentity(a)} · ${a.role} · ${a.status}`]), defaultActor);
    if ($("follow-current").checked) $("session-select").value = defaultActor || "";
    renderSessionAgents(actors.map(a => [a.id, `${actorIdentity(a)} · ${a.role}`, a.status]));
    setOptions("phase-select", state.pattern.phases.map((phase) => [phase.id, `${phase.id} / ${phase.role}`]), state.pattern.phases[state.phase_index].id);
    const artifacts = Object.values(state.artifacts).sort((a, b) => a.id.localeCompare(b.id, "en", { numeric: true }));
    const entries = artifacts.map((a) => [a.id, `${a.id} / ${a.type} / generation ${a.generation ?? "external"} / visit ${a.visit ?? "external"}`]);
    setOptions("compare-left", entries, artifacts.at(-2)?.id);
    setOptions("compare-right", entries, artifacts.at(-1)?.id);
    text("phase-kind", state.pattern.kind === "recurrent_operations" ? "COGNITIVE OPERATIONS / RETURNS" : "FOUR DEVELOPMENT PHASES / INDEPENDENT QA");
    renderPhase();
    renderComparison();
  }
}

function evidenceBlock(artifact, label) {
  const block = node("article", undefined, "evidence-block");
  block.dataset.renderKey = `${artifact.id}/${label}`;
  block.append(node("h4", label), node("p", `${artifact.id} / ${artifact.type} / ${artifactStanding(selectedDetail.controller, artifact)}`, "source"),
    node("pre", JSON.stringify(artifact.content, null, 2)));
  const inspect = node("button", "Inspect provenance and compare");
  inspect.type = "button";
  inspect.dataset.focusKey = artifact.id;
  inspect.addEventListener("click", () => {
    $("artifact-select").value = artifact.id;
    $("compare-right").value = artifact.id;
    const prior = Object.values(selectedDetail.controller.artifacts).filter((a) => a.type === artifact.type && a.id !== artifact.id);
    if (prior.length) $("compare-left").value = prior.at(-1).id;
    renderArtifact(); renderComparison(); switchView("compare", true);
  });
  block.append(inspect);
  return block;
}

function renderPhase() {
  const state = selectedDetail?.controller;
  if (!state) return;
  const phase = state.pattern.phases.find((p) => p.id === $("phase-select").value);
  if (!phase) return;
  const actors = Object.values(state.activations).filter((a) => a.phase === phase.id)
    .sort((a, b) => a.ordinal.localeCompare(b.ordinal, "en", { numeric: true }));
  const current = state.activations[state.current_activation];
  const latest = current?.phase === phase.id ? current : actors.at(-1);
  text("phase-actionability", current?.phase === phase.id
    ? `${actorIdentity(current)} / ${current.role} / ${current.mode} / ${current.status}. ${selectedDetail.application?.reason || "Inspect current inputs and criteria."}`
    : `Viewing ${phase.id}, visits ${state.visits[phase.id]}. Kernel position: ${state.pattern.phases[state.phase_index].id} / ${state.status}.`);
  const inputs = [node("p", phase.criteria.join("\n"), "evidence-note")];
  const bindings = latest?.input_bindings || Object.fromEntries(Object.keys(phase.required_inputs).filter((key) => state.slots[key]).map((key) => [key, state.slots[key]]));
  for (const [slot, ref] of Object.entries(bindings)) inputs.push(evidenceBlock(state.artifacts[ref], slot));
  replaceContents("phase-inputs", inputs);
  const prefix = state.pattern.kind === "verified_sequence" ? "accepted" : "effective";
  const bound = state.slots[`${prefix}.${phase.id}`];
  const outputs = Object.values(state.artifacts).filter((a) => a.phase === phase.id && !["qa.review", "cognition.feedback"].includes(a.type));
  outputs.sort((a, b) => Number(b.id === bound) - Number(a.id === bound));
  replaceContents("phase-outputs", outputs.length ? outputs.map((a) => evidenceBlock(a, `${a.id === bound ? "Current result" : "Retained attempt"} / generation ${a.generation} / visit ${a.visit}`)) : [node("p", "No phase output committed yet.", "evidence-note")]);
  const history = actors.map((actor) => {
    const row = node("article", undefined, "evidence-block");
    row.dataset.renderKey = actor.id;
    const button = node("button", `${actorIdentity(actor)} / ${actor.role} / generation ${actor.generation} / visit ${actor.visit} / ${actor.status}`);
    button.type = "button";
    button.dataset.focusKey = actor.id;
    button.addEventListener("click", () => { $("session-select").value = actor.id; $("follow-current").checked = false; switchView("session", true); loadSession(true); });
    row.append(button, node("p", actor.session_ref || "Session reference not committed", "source"));
    if (actor.failure_reason) row.append(node("p", actor.failure_reason, "bad"));
    const reviews = Object.values(state.artifacts).filter((a) => a.activation_id === actor.id && ["qa.review", "cognition.feedback"].includes(a.type));
    for (const artifact of reviews) {
      const content = artifact.content;
      if (artifact.type === "qa.review") {
        row.append(node("h4", `QA ${content.verdict || content.outcome} / subject ${content.subject_artifact_id}`), node("p", content.report));
        for (const finding of content.findings) row.append(node("p", `${finding.blocking ? "Blocking" : "Nonblocking"}: ${finding.description}`, finding.blocking ? "bad" : "evidence-note"));
      } else {
        row.append(node("h4", `Return ${content.from} -> ${content.target} / ${content.accepted ? "budget allowed" : "budget exhausted"}`),
          node("p", `Reason: ${content.reason}`), node("p", `Question: ${content.question}`));
      }
    }
    return row;
  });
  replaceContents("phase-history", history.length ? history : [node("p", "This phase has not been visited.")]);
}

function renderComparison() {
  const state = selectedDetail?.controller;
  if (!state) return;
  for (const side of ["left", "right"]) {
    const artifact = state.artifacts[$(`compare-${side}`).value];
    text(`compare-${side}-standing`, artifact ? `${artifact.type} / ${artifactStanding(state, artifact)} / producer ${artifact.produced_by || "external"}` : "Select an artifact");
    text(`compare-${side}-text`, artifact ? JSON.stringify(artifact.content, null, 2) : "");
  }
}

function substantiveContent(value) {
  if (value == null || (typeof value === "string" && !value.trim())) return undefined;
  if (Array.isArray(value)) {
    const items = value.map(substantiveContent).filter(item => item !== undefined);
    return items.length ? items : undefined;
  }
  if (typeof value === "object") {
    const fields = Object.entries(value).map(([key, item]) => [key, substantiveContent(item)]).filter(([, item]) => item !== undefined);
    return fields.length ? Object.fromEntries(fields) : undefined;
  }
  return value;
}

function readableOutput(value) {
  if (typeof value !== "string") return JSON.stringify(value, null, 2);
  try {
    const result = JSON.parse(value);
    if (result && typeof result === "object" && !Array.isArray(result)) {
      if (result.content && typeof result.content === "object") {
        const fields = Object.entries(substantiveContent(result.content) || {});
        return fields.map(([key, item]) => {
          const body = typeof item === "string" ? item : Array.isArray(item) && item.every(part => typeof part === "string")
            ? item.join("\n") : JSON.stringify(item, null, 2);
          return fields.length === 1 ? body : `${key.replaceAll("_", " ")}\n${body}`;
        }).join("\n\n");
      }
      if (typeof result.report === "string") return result.report;
    }
  } catch (_) { /* Plain assistant text is the primary output. */ }
  return value;
}

function finalText(entry) {
  return entry.content.final?.content?.filter(part => part.type === "text").map(part => part.text).join("\n") || "";
}

function primaryTranscript(entries) {
  const articles = [];
  let response = null;
  for (const entry of entries) {
    if (entry.kind === "assistant" && response?.preview) {
      const index = articles.indexOf(response.article);
      if (index >= 0) articles.splice(index, 1);
      response = null;
    }
    const duplicateFinal = entry.kind === "final" && response && finalText(entry) === response.text;
    const article = transcriptEntry(entry, Boolean(duplicateFinal));
    if (!article) continue;
    if (duplicateFinal) response.article.append(...article.childNodes);
    else articles.push(article);
    if (entry.kind === "assistant") response = { text: entry.content, article };
    else if (entry.kind === "assistant_delta") response = { preview: true, article };
    else if (entry.kind === "final") response = null;
  }
  if (["completed", "accepted"].includes(selectedDetail?.status.state)) {
    const tools = articles.filter(article => article.dataset.entryKind === "tool");
    const outputs = articles.filter(article => article.dataset.entryKind !== "tool");
    if (tools.length) { const history = node("details"); history.append(node("summary", "Observed tool history"), ...tools); outputs.push(history); }
    return outputs;
  }
  return articles;
}

function transcriptEntry(entry, omitResponse = false) {
  const article = node("article");
  article.dataset.entryKind = entry.kind;
  const at = entry.timestamp ? ` · ${date(entry.timestamp)}` : "";
  const data = entry.content;
  if (entry.kind === "tool") {
    const state = data.state || {};
    const result = data.result || data.partialResult;
    const output = state.output ?? (Array.isArray(result?.content) ? result.content.map((part) => part.text || "").join("\n") : result);
    const status = state.status || (data.isError ? "error" : entry.event_type.endsWith("start") ? "started" : entry.event_type.endsWith("end") ? "finished" : "update");
    article.append(node("h4", `Tool ${data.tool || data.toolName || "not named"} / ${status}${at}`));
    const input = data.args || state.input;
    if (input) {
      const details = node("details");
      details.append(node("summary", "Tool input"), node("pre", JSON.stringify(input, null, 2)));
      article.append(details);
    }
    if (output != null) {
      const details = node("details");
      details.append(node("summary", "Tool output"), node("pre", typeof output === "string" ? output : JSON.stringify(output, null, 2), "tool-output"));
      article.append(details);
    }
    if (state.error) article.append(node("p", state.error, "bad"));
  } else if (entry.kind === "final") {
    const final = data.final;
    article.append(node("h4", `${data.willRetry ? "Retry requested" : "Final response"}${final?.stopReason ? ` · ${final.stopReason}` : ""}${at}`));
    if (data.willRetry) article.append(node("p", "Runtime reported willRetry; this is not a completed controller result.", "warning"));
    const body = readableOutput(finalText(entry));
    if (!omitResponse && body.trim()) article.append(window.NoeticRichText ? window.NoeticRichText(body, {id:selectedId, kind:"run", selection:operationSelection(), viewVersion:operationVersion}) : node("pre", body));
  } else if (entry.kind === "step_finished") {
    article.append(node("h4", `Step finished / ${data.reason || "reason not recorded"}${at}`));
    if (data.tokens) article.append(node("p", `Recorded tokens: ${JSON.stringify(data.tokens)}`, "source"));
  } else {
    const body = readableOutput(data);
    if (typeof body !== "string" || !body.trim()) return null;
    article.append(node("h4", `${entry.kind === "assistant_delta" ? "Assistant / partial stream" : entry.kind}${at}`), window.NoeticRichText ? window.NoeticRichText(body, {id:selectedId, kind:"run", selection:operationSelection(), viewVersion:operationVersion}) : node("pre", body));
  }
  return article;
}

async function loadSession(reveal = false) {
  const id = selectedId, activation = $("session-select").value;
  const version = ++sessionVersion;
  if (!selectedDetail || !activation) {
    $("session-transcript").replaceChildren(node("p", "No agent output retained for this session yet.", "output-empty"));
    text("session-note", "Waiting for agent output");
    return;
  }
  const key = `${id}/${activation}`;
  if ($("session-transcript").dataset.selection !== key) {
    $("session-transcript").dataset.selection = key;
    $("session-transcript").replaceChildren();
    $("session-transcript").scrollTop = 0;
    text("session-raw", ""); text("session-normalized", ""); text("session-model", "Reading observed model identity...");
    text("session-note", "Reading retained transcript...");
    sessionSignature = "";
  }
  try {
    const route = selectedDetail.controller ? `activations/${encodeURIComponent(activation)}` : `sessions/${encodeURIComponent(activation)}`;
    const result = await fetchJSON(`/api/runs/${encodeURIComponent(id)}/${route}/transcript`);
    if (version !== sessionVersion || id !== selectedId) return;
    const actor = selectedDetail.controller?.activations[activation] || { mode: activation === "review" ? "review" : "work", session_ref: result.observed_sessions.join(", ") };
    const config = result.configuration || selectedDetail.application?.configuration || {};
    const model = actor.mode === "review" ? config.qa_model || config.model : config.model;
    text("session-model", `Configured: ${config.client || "not recorded"} / ${model || "client default"}. Observed: ${result.observed_models.length ? result.observed_models.map((m) => `${m.provider || "provider not observed"}/${m.model || "model not observed"}`).join(", ") : "model/provider not present in this transcript window"}. Kernel session: ${actor.session_ref || "not committed"}. Transcript sessions: ${result.observed_sessions.join(", ") || "not in window"}.`);
    if (!selectedDetail.controller) text("primary-model", config.model || result.observed_models.map(m => m.model).filter(Boolean).join(", ") || "Model not recorded");
    text("session-note", `${result.entries.length} activities · updated ${new Date(result.observed_at).toLocaleTimeString()}${result.truncated ? " · recent output window" : ""}`);
    const signature = JSON.stringify(result.entries);
    if (signature !== sessionSignature) {
      sessionSignature = signature;
      const position = $("session-transcript").scrollTop;
      const articles = primaryTranscript(result.entries);
      $("session-transcript").replaceChildren(...(articles.length ? articles : [node("p", result.entries.length ? "No substantive agent output yet." : result.text.trim() || "Waiting for agent output…", "output-empty")]));
      $("session-transcript").scrollTop = position;
    }
    text("session-raw", result.text);
    text("session-normalized", JSON.stringify(result.entries, null, 2));
    if (reveal && !$("session-view").hidden) $("session-view").scrollIntoView({ block: "start", behavior: "instant" });
  } catch (failure) {
    if (version !== sessionVersion || id !== selectedId) return;
    text("session-note", `Output unavailable: ${failure.message}`);
    if (!$("session-transcript").children.length) $("session-transcript").replaceChildren(node("p", "No retained output available yet. Details includes reports and logs.", "output-empty"));
  }
  persistUI();
}

async function performAction(action, body) {
  const id = selectedId, scopeVersion = operationVersion;
  if (!id || cancelling.has(id)) return;
  cancelling.add(id);
  error("action-error", "");
  text("action-result", `${action} requested; awaiting the server response.`);
  if (selectedDetail) renderWorkbench(selectedDetail);
  try {
    const result = await fetchJSON(`/api/runs/${encodeURIComponent(id)}/${action}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    if (id === selectedId && scopeVersion === operationVersion) text("action-result", result.message);
  } catch (failure) {
    if (id === selectedId && scopeVersion === operationVersion) error("action-error", failure.message);
  } finally {
    cancelling.delete(id);
    if (id === selectedId && scopeVersion === operationVersion) await loadDetail();
  }
}

function renderReuseNotice() {
  const reuse = savedUI.reuseSetup;
  text("reuse-notice", reuse ? `Source run: ${reuse.source_run_id}. Historical Telos chain: ${reuse.source_telos_chain || "none"}. ${reuse.warnings.join(" ")}` : "");
  $("reuse-notice").hidden = !reuse;
  $("reuse-details").hidden = !reuse;
}

async function reuseSetup() {
  const id = selectedId, version = ++reuseVersion, draft = draftVersion;
  if (!id) return;
  error("reuse-error", "");
  try {
    const setup = await fetchJSON(`/api/runs/${encodeURIComponent(id)}/reuse-setup`);
    if (version !== reuseVersion || id !== selectedId) return;
    if (draft !== draftVersion) throw new Error("Draft edited while reading setup. Retry to replace it explicitly.");
    const f = setup.fields;
    if (f.backend === "opermem-reviewed") {
      if (!window.confirm(`Replace the editable draft from ${id}? Current backing and purpose will be cleared. Nothing starts.`)) return;
      $("start-pattern").value = f.pattern; $("start-task").value = f.task; $("start-client").value = f.client;
      $("start-model").value = f.model || ""; $("start-qa-model").value = f.qa_model || "";
      $("start-thinking").value = f.thinking || "high"; $("start-profile").value = "";
      $("reviewed-operation").value = f.operation; $("reviewed-parent-id").value="";$("reviewed-warrant-id").value="";$("reviewed-condition-ids").value="";$("reviewed-formulation-id").value="";$("reviewed-checking-spec").value="";$("reviewed-checking-context").value="";$("reviewed-judgment-ids").value="";$("reviewed-practical-question-id").value="";$("reviewed-option-ids").value=""; $("reviewed-store").value = ""; $("start-purpose").value = "";
      $("reviewed-sources").value = f.sources.filter(x=>typeof x === "string").join("\n");
      reviewedSources = f.sources.filter(x=>typeof x === "object").map(x=>({...x})); renderReviewedSources();
      ++draftVersion; savedUI.reuseSetup = {source_run_id:setup.source_run_id,warnings:setup.warnings}; renderReuseNotice();
      error("start-error", ""); text("start-result", "Editable unbound draft. Select current backing and optional purpose before launch.");
      updateComposer(); switchPage("new", "start-task"); return;
    }
    const values = { "start-pattern": f.pattern, "start-client": f.client, "start-task": f.task,
      "start-workspace": f.workspace, "start-model": f.model ?? "", "start-qa-model": f.qa_model ?? "",
      "start-thinking": f.thinking, "start-timeout": String(f.timeout), "start-returns": String(f.max_returns),
      "start-remediations": String(f.max_remediations), "start-verify": f.verify === null ? "" : JSON.stringify(f.verify),
      "start-sources": f.sources.join("\n"), "start-profile": "", "start-purpose": "" };
    // Check browser normalization/choices before touching any part of the live draft.
    for (const [key, value] of Object.entries(values)) {
      const field = $(key).cloneNode(true);
      field.value = value;
      if (field.value !== value || (value !== "" && !field.checkValidity())) throw new Error(`Unsupported form value: ${key}. Draft unchanged.`);
    }
    if (JSON.stringify(values["start-sources"].split(/\r?\n/).map(v => v.trim()).filter(Boolean)) !== JSON.stringify(f.sources)) {
      throw new Error("Sources cannot round-trip exactly. Draft unchanged.");
    }
    if (!window.confirm(`Replace the current New pattern draft with setup from ${id}?\nEditable draft, not resumed/cloned. Telos selection will be cleared. Nothing starts.`)) return;
    for (const [key, value] of Object.entries(values)) { $(key).value = value; delete initialForms[key]; }
    ++draftVersion;
    savedUI.reuseSetup = { source_run_id: setup.source_run_id, source_telos_chain: setup.source_telos_chain, warnings: setup.warnings };
    renderReuseNotice();
    error("start-error", ""); text("start-result", "");
    updateComposer();
    switchPage("new", "start-task");
  } catch (failure) {
    if (version === reuseVersion && id === selectedId) error("reuse-error", failure.message);
  }
}

async function loadConfiguration() {
  try {
    configuration = await fetchJSON("/api/configuration");
    setOptions("start-profile", [["", "Custom client/model"], ...configuration.profiles.map((profile) => [profile.id, profile.label])]);
    text("configuration-notice", `${configuration.profile_notice} ${configuration.driver_lifetime}`);
    $("configured-profiles").replaceChildren(...configuration.profiles.map((profile) => {
      const row = node("article", undefined, "profile-row");
      row.append(node("h4", profile.label), node("p", `${profile.client} / ${profile.model}`, "source"));
      return row;
    }));
    text("configuration-details", JSON.stringify({ limits: configuration.limits, roles: configuration.role_defaults, local_support: configuration.local }, null, 2));
    const priorProfiles = {
      "pi-direct": { client: "pi", model: "openai-codex/gpt-6-astra", current: "pi-direct" },
      "opencode-direct": { client: "opencode", model: "openai/gpt-6-astra", current: "opencode-direct" },
      "pi-litellm": { client: "pi", model: "litellm/codex/gpt-6-astra", current: "pi-direct" },
      "opencode-litellm": { client: "opencode", model: "litellm/codex/gpt-6-astra", current: "opencode-direct" },
    };
    const prior = priorProfiles[initialForms["start-profile"]];
    const legacy = prior && initialForms["start-client"] === prior.client && initialForms["start-model"] === prior.model;
    const starter = configuration.profiles.find((p) => p.id === (legacy ? prior.current : initialForms["start-profile"]));
    if (starter && !$("start-profile").value && initialForms["start-client"] === starter.client
        && $("start-client").value === initialForms["start-client"]
        && $("start-model").value === initialForms["start-model"]
        && (legacy || starter.model === initialForms["start-model"])) {
      $("start-profile").value = starter.id;
      $("start-model").value = starter.model;
      persistUI();
    }
    if (!savedUI.forms?.["start-model"] && $("start-client").value === "pi" && $("start-model").value === "openai-codex/gpt-6.1-sol") $("start-profile").value = "pi-direct";
    delete initialForms["start-profile"];
    window.NoeticDrafts?.restoreChoice("start-profile", [...$("start-profile").options].map(x=>x.value));
    updateComposer();
    document.dispatchEvent(new CustomEvent("noetic:configuration", {detail:configuration}));
  } catch (failure) {
    text("configuration-notice", `Configuration unavailable: ${failure.message}. Custom model fields remain editable.`);
  }
}

async function loadPurposes() {
  const scopeVersion = operationVersion, scopeKey = operationKey(), request = ++purposeVersion;
  const selection = operationSelection(); error("purpose-error", "");
  try {
    const result = await fetchJSON(scopedURL("/api/goals", {...selection,...selection.scope ? {include_legacy:"true"} : {}}));
    if (!operationValid(scopeVersion,scopeKey) || request !== purposeVersion) return;
    text("purpose-database", JSON.stringify(result.stores));
    text("purpose-status", `${result.purposes.length} native purposes · ${result.coverage} coverage${result.namespace_registered === false ? " · application namespace not registered" : ""}`);
    const eligible = result.purposes.filter(item=>operationMode === "effort" && item.reference.owner.kind === "effort" && item.reference.owner.ordinal === selectedEffort);
    setOptions("start-purpose", [["","No Telos link"], ...eligible.map(item=>[JSON.stringify(item.reference), `${item.native.chain.primaryGoal} · ${item.reference.store_id} / ${item.native.chain.status}`])]);
    if (initialForms["start-purpose"] && eligible.some(item=>JSON.stringify(item.reference) === initialForms["start-purpose"])) $("start-purpose").value = initialForms["start-purpose"];
    delete initialForms["start-purpose"];
    window.NoeticDrafts?.restoreChoice("start-purpose", [...$("start-purpose").options].map(x=>x.value));
    scopeControls();
    $("purpose-list").replaceChildren(...result.purposes.map(item=>{
      const ref = item.reference, article = node("article",undefined,"evidence-block");
      const button = node("button",`Use purpose: ${item.native.chain.primaryGoal}`); button.type = "button";
      button.disabled = !eligible.includes(item);
      button.addEventListener("click",()=>{ if (!operationValid(scopeVersion,scopeKey)) return; ++draftVersion; $("start-purpose").value = JSON.stringify(ref); switchPage("new");persistUI(); });
      const details = node("details"), contents = node("pre",JSON.stringify(item,null,2));
      const read = node("button","Refresh exact native purpose"); read.type = "button";
      read.addEventListener("click",async()=>{
        try { const value = await fetchJSON(scopedURL(`/api/goals/${encodeURIComponent(ref.chain_id)}`,{...selection,store_id:ref.store_id,...selection.scope ? {include_legacy:"true"} : {}})); if (operationValid(scopeVersion,scopeKey) && contents.isConnected) contents.textContent = JSON.stringify(value,null,2); }
        catch (failure) { if (operationValid(scopeVersion,scopeKey)) error("purpose-error",failure.message); }
      });
      details.append(node("summary","Native purpose, ownership and source references"),read,contents);
      article.append(node("h3",item.native.chain.primaryGoal),button,node("p",`${ref.owner.kind} ${ref.owner.ordinal || ""} · ${ref.store_id} · ${ref.chain_id} / ${item.native.chain.status}`,"source"),details);return article;
    }));persistUI();
  } catch (failure) { if (operationValid(scopeVersion,scopeKey)) error("purpose-error",`Purposes unavailable, not an empty history: ${failure.message}`); }
}
function renderMemoryMatches(matches, semanticMode) {
  const selection = operationSelection(), scopeVersion = operationVersion, scopeKey = operationKey();
  $("memory-results").replaceChildren(...(matches.length ? matches.map(match=>{
    const article = node("article",undefined,"search-result");
    const owner = match.effort_root ? `Effort ${match.effort_root} · ${match.ordinal || "source"}${match.target ? ` · context ${match.target.instantiation}/${match.target.session}` : ""}` : "Original namespace · unassigned";
    const button = node("button",`${owner} · ${match.source || match.artifact_type || "evidence"}`);button.type = "button";
    button.disabled = !match.run_id && !match.registry_id;
    button.addEventListener("click",()=>{
      if (!operationValid(scopeVersion,scopeKey)) return;
      if (match.run_id) selectRun(match.run_id,match);
      else if (match.registry_id) window.NoeticSessions.open(match.target ? {...match.target,effort_root:match.effort_root} : {id:match.registry_id});
    });
    if (selection.effort_root && match.source_id && match.source_text_sha256) {
      const use = node("button", "Select source for inquiry draft"); use.type = "button";
      use.addEventListener("click", ()=>{
        if (!operationValid(scopeVersion,scopeKey)) return;
        if (!reviewedSources.some(x=>x.source_id === match.source_id)) reviewedSources.push({source_id:match.source_id,source_text_sha256:match.source_text_sha256,selection:{kind:"effort",effort_root:selection.effort_root}});
        ++draftVersion; $("start-pattern").value = "opermem-reviewed"; renderReviewedSources(); updateComposer();persistUI();
        text("memory-status", "Qualified source selected for the editable draft. Launch will revalidate its original identity and digest.");
      }); article.append(use);
    }
    const details = node("details");details.append(node("summary","Exact source and retained ownership"),node("pre",JSON.stringify(match,null,2)));
    article.append(button,node("p",match.field === "canonical-history" ? `Retained ${match.source} record. Expand the exact source below.` : match.snippet || match.text || "","snippet"),node("p",`${match.source_id || match.source_path} · ${match.disposition || match.state || "retained source"}${semanticMode && typeof match.score === "number" ? ` · relevance ${match.score.toFixed(4)}` : " · lexical source snapshot"}`,"source"),details);return article;
  }) : [node("p","No matching evidence in the selected scope.")]));
}

let settingsPane = "model";
function showSettings(name = settingsPane) {
  settingsPane = name;
  $("advanced-settings").hidden = false;
  for (const panel of document.querySelectorAll("[data-settings-panel]")) panel.hidden = panel.dataset.settingsPanel !== name;
  for (const button of document.querySelectorAll("[data-settings]")) button.setAttribute("aria-current", String(button.dataset.settings === name));
}
function updateComposer() {
  scopeControls();
  const development = $("start-pattern").value === "development", reviewed = isReviewed();
  $("reviewed-setup").hidden = !reviewed;
  text("start-execution-note", reviewed ? "Start instantiates the reviewed discipline in this effort. Its original preparation precedes native and actor effects." : "Start creates a discipline instance in the selected effort. The controller prepares its project context.");
  $("review-settings-tab").hidden = !(development || reviewed);
  $("cognition-limits").hidden = development || reviewed;
  if (reviewed) { if (!reviewedDefinition && !reviewedLoading) loadReviewedSetup(); reviewedOperation(); }
  else $("start-submit").disabled = startPending || operationMode !== "effort" || !effortEnvironment || window.NoeticDrafts && !window.NoeticDrafts.ready();
  $("verify-field").hidden = !development;
  $("review-settings-tab").hidden = !(development || reviewed);
  $("development-limits").hidden = !development;
  $("cognition-limits").hidden = development || reviewed;
  $("custom-model-fields").hidden = Boolean($("start-profile").value);
  $("pi-thinking-field").hidden = $("start-client").value !== "pi";
  text("start-effective-model", `${$("start-client").value} · ${$("start-model").value}${$("start-client").value === "pi" ? " · " + $("start-thinking").value : ""}${development ? " · review " + ($("start-qa-model").value || "inherits main") : ""}`);
  if (!development && !reviewed && settingsPane === "review" && !$("advanced-settings").hidden) showSettings("model");
}

function initWorkbench() {
  $("reviewed-refresh").addEventListener("click", loadReviewedSetup);
  $("reviewed-operation").addEventListener("change",()=>{++draftVersion;reviewedOperation();});
  for(const id of ["reviewed-parent-id","reviewed-warrant-id","reviewed-condition-ids","reviewed-formulation-id","reviewed-checking-spec","reviewed-checking-context","reviewed-judgment-ids","reviewed-practical-question-id","reviewed-option-ids"])$(id).addEventListener("input",()=>{++draftVersion;reviewedOperation();});
  $("reviewed-store").addEventListener("change", ()=>{ ++draftVersion; $("reviewed-parent-id").value="";$("reviewed-warrant-id").value="";$("reviewed-condition-ids").value="";$("reviewed-formulation-id").value="";$("reviewed-checking-spec").value="";$("reviewed-checking-context").value="";$("reviewed-judgment-ids").value="";$("reviewed-practical-question-id").value="";$("reviewed-option-ids").value="";reviewedOperation(); });
  $("reviewed-register").addEventListener("click", registerReviewedStore);
  for (const kind of ["contribution", "correlation"]) $("reviewed-recover-"+kind).addEventListener("click", ()=>recoverReviewed(kind));
  for (const id of formIds) {
    if (savedUI.forms?.[id] != null && !["start-profile", "start-purpose", "role-filter"].includes(id)) $(id).value = savedUI.forms[id];
    $(id).addEventListener("input", persistUI);
    if (id === "purpose-goal") $(id).addEventListener("input", () => ++purposeDraftVersion);
    $(id).addEventListener("change", persistUI);
    if (id.startsWith("start-")) {
      for (const event of ["input", "change"]) $(id).addEventListener(event, () => { ++draftVersion; delete initialForms[id]; });
    }
  }
  $("operation-scope").addEventListener("change",()=>changeOperationScope($("operation-scope").value));
  $("memory-query").addEventListener("input",()=>{ ++memoryVersion; $("memory-results").replaceChildren(); text("memory-status","Query changed. Search explicitly."); text("memory-coverage",""); });
  $("memory-target").addEventListener("change",()=>{ ++recallTargetVersion; ++memoryVersion; $("memory-results").replaceChildren();text("memory-status","Selection changed. Search explicitly."); });
  for (const id of selectionIds) $(id).addEventListener("change", persistUI);
  for (const button of document.querySelectorAll("[data-page]")) button.addEventListener("click", () => switchPage(button.dataset.page));
  for (const id of ["run-filter", "status-filter", "pattern-filter", "role-filter"]) $(id).addEventListener("input", () => renderRuns(allRuns));
  $("empty-new").addEventListener("click", () => switchPage("new", "start-task"));
  $("toggle-navigation").addEventListener("click", () => {
    const open = $("operator-rail").classList.toggle("navigation-open");
    $("toggle-navigation").setAttribute("aria-expanded", String(open));
    text("toggle-navigation", open ? "Hide sessions" : "Sessions");
  });
  $("start-create-purpose").addEventListener("click", () => { switchPage("purposes", "purpose-goal"); loadPurposes(); });
  $("start-load-purposes").addEventListener("click", loadPurposes);
  $("reuse-setup").addEventListener("click", reuseSetup);
  $("workspace-review-open").addEventListener("click", () => {
    const activation = $("workspace-review-open").dataset.activation;
    if (activation) { $("session-select").value = activation; $("follow-current").checked = false; loadSession(); }
  });
  $("workspace-file-close").addEventListener("click", () => { $("workspace-file-view").hidden = true; });
  $("workspace-apply").addEventListener("click", async () => {
    const id = selectedId, scopeVersion = operationVersion;
    if (!id || !confirm("Apply these reviewed task changes to the recorded project? Existing source drift is checked before copying.")) return;
    $("workspace-apply").disabled = true;
    try {
      const value = await fetchJSON(`/api/runs/${id}/apply`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({confirm:true})});
      if (id === selectedId && scopeVersion === operationVersion) { text("workspace-apply-result", value.reason || "Reviewed changes applied to the recorded project."); await loadProjectHandoff(); }
    } catch (failure) { if (id === selectedId && scopeVersion === operationVersion) text("workspace-apply-result", failure.message); }
    finally { $("workspace-apply").disabled = false; }
  });
  $("purposes-refresh").addEventListener("click", loadPurposes);
  $("start-profile").addEventListener("change", () => {
    const profile = configuration?.profiles.find((p) => p.id === $("start-profile").value);
    if (profile) { $("start-client").value = profile.client; $("start-model").value = profile.model; persistUI(); }
    updateComposer();
  });
  for (const id of ["start-client", "start-model"]) $(id).addEventListener("change", () => { $("start-profile").value = ""; persistUI(); updateComposer(); });
  $("advance-one").addEventListener("click", () => performAction("advance", { mode: "one" }));
  $("advance-all").addEventListener("click", () => performAction("advance", { mode: "all" }));
  $("pause-pattern").addEventListener("click", () => performAction("pause", {}));
  $("phase-select").addEventListener("change", renderPhase);
  $("session-select").addEventListener("change", () => { $("follow-current").checked = false; workbenchSignature = ""; renderWorkbench(selectedDetail); persistUI(); loadSession(); });
  $("follow-current").addEventListener("change", () => { workbenchSignature = ""; renderWorkbench(selectedDetail); persistUI(); loadSession(); });
  $("evidence-drawer").addEventListener("toggle", () => {
    if ($("evidence-drawer").open && !document.querySelector('.view-controls [aria-pressed="true"]:not(#session-tab)')) switchView(selectedDetail?.controller ? "controller" : "reports");
  });
  for (const side of ["left", "right"]) $(`compare-${side}`).addEventListener("change", renderComparison);
  $("session-logs").addEventListener("click", () => {
    if (selectedDetail?.controller) { $("actor-select").value = $("session-select").value; switchView("controller", true); renderActor(); loadActorLog(); }
    else { $("log-select").value = `${$("session-select").value || "work"}.stdout.log`; switchView("logs", true); renderEvidence("log", $("log-select").value); }
  });
  $("start-task").addEventListener("keydown", event => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing || event.keyCode === 229 || event.defaultPrevented) return;
    event.preventDefault();
    const submit = $("start-submit");
    if (event.repeat || startPending || submit.disabled) return;
    event.currentTarget.form.requestSubmit(submit);
  });
  $("start-form").addEventListener("submit", async event=>{
    event.preventDefault();if (startPending || window.NoeticDrafts && !window.NoeticDrafts.ready()) return;
    const scopeVersion = operationVersion, scopeKey = operationKey(), draft = draftVersion, subject = developerSubjectVersion;
    const selection = operationSelection(), environment = effortEnvironment && structuredClone(effortEnvironment);
    startPending = true;scopeControls();error("start-error","");text("start-result","Creating the selected discipline instance and launching its driver…");
    try {
      if (isReviewed()) { await startReviewed({scopeVersion,scopeKey,draft,subject,selection,environment}); return; }
      if (!selection.effort_root || !environment) throw new Error("Select a registered effort before starting structured work.");
      const payload = { pattern:$("start-pattern").value, task:$("start-task").value, workspace:environment.cwd,
        sources:$("start-sources").value.split(/\r?\n/).map(v=>v.trim()).filter(Boolean),
        verify:$("start-pattern").value === "development" && $("start-verify").value.trim() ? JSON.parse($("start-verify").value) : null,
        client:$("start-client").value,model:$("start-model").value,qa_model:$("start-pattern").value === "development" ? $("start-qa-model").value || null : null,
        thinking:$("start-thinking").value,timeout:Number($("start-timeout").value),
        max_returns:$("start-pattern").value === "cognition" ? Number($("start-returns").value) : 1,
        max_remediations:$("start-pattern").value === "development" ? Number($("start-remediations").value) : 1,
        ...selection,environment,origin:"human",human_ref:{origin:"local-human-operator"},
        ...$("start-purpose").value ? {purpose_ref:JSON.parse($("start-purpose").value)} : {} };
      const instance = await fetchJSON("/api/disciplines",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({command_id:crypto.randomUUID(),...selection,initiator:selection.effort_root,pattern:payload.pattern,intent:payload.task,environment})});
      const result = await fetchJSON("/api/application/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...payload,discipline_id:instance.discipline.id})});
      if (operationValid(scopeVersion,scopeKey)) {
        text("start-result",`${result.run_id}: ${result.message}`);
        if (draft === draftVersion && subject === developerSubjectVersion) await selectRun(result.run_id);
      }
      await refresh();
    } catch (failure) {
      if (operationValid(scopeVersion,scopeKey)) { error("start-error",failure.message);text("start-result",failure.runId ? `Retained run ${failure.runId}; inspect its register before retrying.` : "No successful start response. Refresh scoped history before retrying."); }
      await refresh();
    } finally { startPending = false;updateComposer();persistUI(); }
  });
  $("purpose-form").addEventListener("submit",async event=>{
    event.preventDefault();const scopeVersion = operationVersion,scopeKey = operationKey(),draft = draftVersion, goalDraft = purposeDraftVersion;
    const selection = operationSelection(),goal = $("purpose-goal").value;
    if(purposeCreatePending||!window.NoeticPurposeDrafts?.ready()){error("purpose-error","Verify the current purpose draft owner before creating.");return;}purposeCreatePending=true;
    $("purpose-create").disabled = true;error("purpose-error","");
    try {
      const result = await fetchJSON("/api/goals",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({goal,...selection,origin_ref:{origin:"local-human-operator"},source_ref:{surface:"browser-purpose-form"}})});
      if (!operationValid(scopeVersion,scopeKey)) return;
      await loadPurposes();if (!operationValid(scopeVersion,scopeKey)) return;
      const choose = draft === draftVersion && goalDraft === purposeDraftVersion && selection.effort_root;
      if (choose) { delete initialForms["start-purpose"]; ++draftVersion;$("start-purpose").value = JSON.stringify(result.purpose.reference); }
      text("purpose-status",`Created ${result.purpose.reference.chain_id} in ${result.purpose.reference.store_id}${choose ? " · selected for structured work" : " · choose explicitly"}.`);persistUI();
    } catch (failure) { if (operationValid(scopeVersion,scopeKey)) error("purpose-error",failure.message); }
    finally { purposeCreatePending=false;window.NoeticPurposeDrafts?.render(); }
  });
  $("memory-form").addEventListener("submit",async event=>{
    event.preventDefault();const scopeVersion = operationVersion,scopeKey = operationKey(),targetVersion = recallTargetVersion,request = ++memoryVersion;
    if($("memory-target").value!=="effort" && (operationMode!=="effort" || $("memory-target").selectedOptions[0]?.disabled)){error("memory-error","The requested recall subject is unavailable. Select its owning effort and exact position/context first; no broader search was run.");return;}
    $("memory-submit").disabled = true;error("memory-error","");
    const semanticMode = $("memory-mode").value === "semantic",query = $("memory-query").value;
    const base = operationSelection(),kind = operationMode === "effort" ? $("memory-target").value : "application";
    const selection = kind === "application" ? {kind} : {kind,effort_root:selectedEffort,...kind !== "effort" ? {ordinal:selectedNative.ordinal} : {},...kind === "session" ? {instantiation:selectedNative.instantiation,session:selectedNative.session} : {}};
    const valid = ()=>operationValid(scopeVersion,scopeKey) && request === memoryVersion && targetVersion === recallTargetVersion && query === $("memory-query").value;
    text("memory-status",semanticMode ? "Explicit scoped semantic search in progress. No lexical fallback." : "Searching selected retained sources…");
    try {
      const result = semanticMode ? await fetchJSON("/api/memory/semantic",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query,reindex:$("memory-reindex").checked,limit:20,selection})}) : await fetchJSON(scopedURL("/api/search",{...base,q:query,limit:20,...selection.ordinal ? {ordinal:selection.ordinal} : {},...kind === "session" ? {instantiation:selection.instantiation,session:selection.session} : {}}));
      if (!valid()) return;renderMemoryMatches(result.results,semanticMode);
      text("memory-status",`${result.results.length} results · ${result.status || "retained sources"} · ${semanticMode ? result.notice : "Derived lexical source evidence"}. Results are not auto-refreshed.`);
      text("memory-coverage",JSON.stringify({selection:result.selection,identity:result.identity,coverage:result.coverage,diagnostics:result.diagnostics},null,2));
    } catch (failure) { if (valid()) {error("memory-error",failure.message);text("memory-status","Search unavailable; no fallback. Prior results are stale.");} }
    finally { $("memory-submit").disabled = false; }
  });
  $("summary-generate").addEventListener("click", async () => {
    const id = selectedId, scopeVersion = operationVersion;
    if (!id) return;
    $("summary-generate").disabled = true; error("summary-error", ""); text("summary-coverage", `Requesting non-authoritative support for ${id}...`);
    try {
      const result = await fetchJSON(`/api/runs/${encodeURIComponent(id)}/summary`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ save: $("summary-save").checked }) });
      if (id !== selectedId || scopeVersion !== operationVersion) return;
      text("summary-content", result.text);
      text("summary-coverage", `${id} / ${result.notice} / model ${result.model} / saved ${result.saved} / citations verified ${result.citations_verified} / coverage: ${JSON.stringify(result.coverage)}`);
    } catch (failure) { if (id === selectedId && scopeVersion === operationVersion) error("summary-error", failure.message); }
    finally { $("summary-generate").disabled = !selectedId || selectedDetail?.backend === "opermem-reviewed"; }
  });
  $("diagnostics-refresh").addEventListener("click", async () => {
    $("diagnostics-refresh").disabled = true; error("diagnostics-error", "");
    try {
      const result = await fetchJSON("/api/diagnostics/refresh", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      text("diagnostics-status", `Health observed ${date(result.observed_at)}. Cached until explicit refresh; no inference.`);
      $("diagnostics-results").replaceChildren(...result.services.map((service) => {
        const row = node("article", undefined, "profile-row");
        row.append(node("h4", `${service.name}: ${service.available ? "health endpoint available" : "unavailable"}`), node("p", service.url, "source"),
          node("p", service.error || `HTTP ${service.http_status}`));
        if (service.loaded_models) row.append(node("pre", JSON.stringify(service.loaded_models, null, 2)));
        return row;
      }));
    } catch (failure) { error("diagnostics-error", failure.message); }
    finally { $("diagnostics-refresh").disabled = false; }
  });
  $("start-form").addEventListener("invalid", event => {
    const panel = event.target.closest("[data-settings-panel]");
    if (panel) { showSettings(panel.dataset.settingsPanel); if (event.target.id === "start-model") $("custom-model-fields").hidden = false; }
  }, true);
  $("start-change-model").addEventListener("click", () => showSettings("model"));
  $("start-close-settings").addEventListener("click", () => { $("advanced-settings").hidden = true; });
  for (const button of document.querySelectorAll("[data-settings]")) button.addEventListener("click", () => showSettings(button.dataset.settings));
  for (const id of ["start-thinking", "start-qa-model"]) $(id).addEventListener("input", updateComposer);
  $("start-pattern").addEventListener("change", updateComposer);
  updateComposer();
  text("diagnostics-status", "Not checked in this browser. Refresh explicitly; no inference is used.");
  switchPage(currentPage);
}

const structuredDraftFields = ["start-task","start-pattern","start-sources","start-verify","start-profile","start-client","start-model","start-qa-model","start-thinking","start-timeout","start-remediations","start-returns","reviewed-operation","reviewed-sources"];
const structuredBindings = ["reviewed-store","reviewed-parent-id","reviewed-warrant-id","reviewed-condition-ids","reviewed-formulation-id","reviewed-checking-spec","reviewed-checking-context","reviewed-judgment-ids","reviewed-practical-question-id","reviewed-option-ids","start-purpose"];
const structuredDrafts = (() => {
  let owner = null, generation = 0, pending = false, conflict = "", desired = {}, invalid = new Set();
  const defaults = {};
  const storage = savedUI.structuredDrafts && typeof savedUI.structuredDrafts === "object" ? savedUI.structuredDrafts : {};
  const values = ids => Object.fromEntries(ids.map(id=>[id,$(id).value]));
  const validOwner = () => owner && owner.scope === operationKey();
  const substantive = fields => ["start-task","start-sources","start-verify","reviewed-sources"].some(id=>String(fields?.[id] || "").trim());
  const keyFor = (namespace,effort) => JSON.stringify([namespace,effort]);
  function render() {
    text("structured-draft-status", conflict || (pending ? "Checking draft ownership in the current namespace…" : owner ? `Editable draft · Effort ${owner.effort} · namespace ${owner.namespace}${invalid.size ? " · saved references require current selection" : ""}. Results and launch receipts are not restored as draft readiness.` : "No effort owns this editor. Select an effort; unassigned saved text remains separate."));
    $("start-form").inert = pending || !owner;
    $("unassigned-draft").hidden = !savedUI.unassignedStructuredDraft;
    if (savedUI.unassignedStructuredDraft) text("unassigned-draft-text", JSON.stringify(savedUI.unassignedStructuredDraft.fields,null,2));
    text("copy-unassigned-draft", owner ? `Copy task, source text and settings into Effort ${owner.effort}` : "Select an effort before copying draft text");
    $("copy-unassigned-draft").disabled = pending || !owner;
  }
  function capture() {
    if (!validOwner() || pending) return;
    const previous = storage[owner.key];
    storage[owner.key] = {fields:{...values(structuredDraftFields),...Object.fromEntries(structuredDraftFields.filter(id=>id in desired).map(id=>[id,desired[id]]))},bindings:{...values(structuredBindings),...Object.fromEntries(structuredBindings.filter(id=>id in desired).map(id=>[id,desired[id]]))},sources:structuredClone(reviewedSources),modified:previous?.modified || Boolean($("start-task").value.trim()),namespace:owner.namespace,effort:owner.effort};
    savedUI.structuredDrafts = storage;
    savedUI.structuredDraftOwner = {namespace:owner.namespace,effort:owner.effort};
  }
  function leave() {
    capture(); ++generation; owner = null; desired = {}; invalid.clear(); conflict = ""; pending = true;
    reviewedSources = [];
    for (const id of [...structuredDraftFields,...structuredBindings]) $(id).value = defaults[id] ?? "";
    renderReviewedSources(); render();
  }
  function restoreChoice(id, entries) {
    if (!validOwner() || !(id in desired)) return;
    const value = desired[id];
    if (!value || entries.includes(value)) { $(id).value = value; delete desired[id]; invalid.delete(id); }
    else {
      let option = [...$(id).options].find(x=>x.value===value);
      if (!option) { option = node("option",`Saved reference unavailable · ${value}`); option.value=value; option.disabled=true; $(id).append(option); }
      $(id).value=value; invalid.add(id);
    }
    render();
  }
  async function enter() {
    const request = ++generation, access = accessVersion, scope = operationKey(), effort = operationSelection().effort_root;
    if (!effort || !operatorToken) { pending=false;owner=null;render();updateComposer();return; }
    pending=true;render();scopeControls();
    try {
      const witness = await fetchJSON(scopedURL("/api/disciplines",{scope:"application",limit:1}));
      if (request!==generation || access!==accessVersion || scope!==operationKey()) return;
      if (!witness.namespace_registered || typeof witness.namespace_id!=="string" || !witness.namespace_id) throw new Error("Application namespace is not registered");
      const namespace=witness.namespace_id,key=keyFor(namespace,effort),draft=storage[key];
      owner={namespace,effort,key,scope};desired={};invalid.clear();conflict="";
      for (const id of [...structuredDraftFields,...structuredBindings]) $(id).value=defaults[id] ?? "";
      if (draft && draft.namespace===namespace && draft.effort===effort) {
        for (const id of structuredDraftFields) if (typeof draft.fields?.[id]==="string") $(id).value=draft.fields[id];
        desired={...Object.fromEntries(structuredBindings.map(id=>[id,String(draft.bindings?.[id] || "")]))};
        for (const id of ["start-profile","reviewed-operation"]) if (draft.fields?.[id]) desired[id]=draft.fields[id];
        for(const id of ["reviewed-parent-id","reviewed-warrant-id","reviewed-condition-ids","reviewed-formulation-id","reviewed-checking-spec","reviewed-checking-context","reviewed-judgment-ids","reviewed-practical-question-id","reviewed-option-ids"]){$(id).value=desired[id];delete desired[id];}
        reviewedSources=(draft.sources || []).filter(source=>source.selection?.kind==="effort" && source.selection.effort_root===effort).map(source=>structuredClone(source));
      } else reviewedSources=[];
      for (const id of [...structuredDraftFields,...structuredBindings]) delete initialForms[id];
      pending=false;renderReviewedSources();render();updateComposer();
      restoreChoice("start-profile", [...$("start-profile").options].map(x=>x.value));
      if (isReviewed()) { invalid.add("reviewed-store");loadReviewedSetup(); }
      else { delete desired["reviewed-store"]; }
      if (desired["start-purpose"]) { invalid.add("start-purpose");loadPurposes(); }
      else { delete desired["start-purpose"]; }
      persistUI();scopeControls();
    } catch (failure) {
      if (request!==generation || access!==accessVersion || scope!==operationKey()) return;
      pending=false;owner=null;conflict=`Draft ownership unavailable: ${failure.message}. Retry ownership before starting work.`;render();scopeControls();
    }
  }
  function init() {
    for (const id of [...structuredDraftFields,...structuredBindings]) {
      const element=$(id);
      defaults[id]=element.tagName==="SELECT" ? [...element.options].find(x=>x.defaultSelected)?.value ?? element.options[0]?.value ?? "" : element.defaultValue;
      element.addEventListener("input",edit);element.addEventListener("change",edit);
    }
    if (!savedUI.structuredDraftOwner && substantive(savedUI.forms) && !savedUI.unassignedStructuredDraft) savedUI.unassignedStructuredDraft={fields:Object.fromEntries(structuredDraftFields.map(id=>[id,String(savedUI.forms?.[id] ?? defaults[id] ?? "")]))};
    for (const id of [...structuredDraftFields,...structuredBindings]) { $(id).value=defaults[id];delete initialForms[id]; }
    $("copy-unassigned-draft").addEventListener("click",()=>{
      if (!validOwner() || pending || !savedUI.unassignedStructuredDraft) return;
      if (storage[owner.key]?.modified || substantive(values(structuredDraftFields))) { conflict="Draft conflict: this effort has edited work. It was preserved; the unassigned original is still available.";render();return; }
      for (const id of structuredDraftFields) if (typeof savedUI.unassignedStructuredDraft.fields[id]==="string") $(id).value=savedUI.unassignedStructuredDraft.fields[id];
      for (const id of structuredBindings) $(id).value="";
      desired={};invalid.clear();reviewedSources=[];conflict="";storage[owner.key]={modified:true};++draftVersion;renderReviewedSources();updateComposer();persistUI();render();
    });
    $("retry-draft-owner").addEventListener("click",()=>enter());
    leave();enter();
  }
  function edit(event) {
    if (!validOwner() || pending) return;
    delete desired[event.target.id];invalid.delete(event.target.id);conflict="";
    storage[owner.key] ||= {};storage[owner.key].modified=true;
    capture();render();scopeControls();persistUI();
  }
  return {init,capture,leave,enter,ready:()=>Boolean(validOwner() && !pending && !invalid.size),restoreChoice};
})();
window.NoeticDrafts = structuredDrafts;
let purposeCreatePending=false;
const purposeDrafts=(()=>{
  const drafts=savedUI.purposeDrafts && typeof savedUI.purposeDrafts==="object"?savedUI.purposeDrafts:{};
  let owner=null,generation=0,pending=false,problem="";
  const ready=()=>Boolean(owner && owner.scope===operationKey() && owner.access===accessVersion && !pending);
  function render(){text("purpose-draft-owner",problem || (pending?"Checking purpose draft ownership…":owner?`Purpose draft · ${owner.selection.effort_root?"Effort "+owner.selection.effort_root:"Application"} · namespace ${owner.namespace}. Creating is an explicit action in this owner.`:"Purpose draft owner unobserved. Retry before creating."));$("purpose-goal").disabled=!ready();$("purpose-create").disabled=!ready()||purposeCreatePending;$("purpose-unassigned").hidden=!savedUI.unassignedPurposeDraft;text("purpose-unassigned-text",savedUI.unassignedPurposeDraft||"");text("purpose-copy-unassigned",owner?`Copy purpose text into ${owner.selection.effort_root?"Effort "+owner.selection.effort_root:"Application"}`:"Verify an owner before copying");$("purpose-copy-unassigned").disabled=!ready();}
  function capture(){if(!ready())return;drafts[owner.key]={text:$("purpose-goal").value,namespace:owner.namespace,selection:owner.selection};savedUI.purposeDrafts=drafts;savedUI.purposeDraftOwner={namespace:owner.namespace,selection:owner.selection};}
  function leave(){capture();++generation;owner=null;pending=true;problem="";$("purpose-goal").value="";render();}
  async function enter(){capture();const request=++generation,access=accessVersion,scope=operationKey(),selection=operationSelection();pending=true;problem="";owner=null;$("purpose-goal").value="";render();if(!operatorToken){pending=false;render();return;}try{const witness=await fetchJSON(scopedURL("/api/disciplines",{scope:"application",limit:1}));if(request!==generation||access!==accessVersion||scope!==operationKey())return;if(!witness.namespace_registered||typeof witness.namespace_id!=="string"||!witness.namespace_id)throw new Error("Application namespace unregistered");const namespace=witness.namespace_id,key=JSON.stringify([namespace,selection]);owner={namespace,key,scope,selection,access};const draft=drafts[key];$("purpose-goal").value=draft?.namespace===namespace&&JSON.stringify(draft.selection)===JSON.stringify(selection)?draft.text||"":"";pending=false;render();persistUI();}catch(failure){if(request!==generation||access!==accessVersion||scope!==operationKey())return;pending=false;problem=`Purpose ownership unavailable: ${failure.message}. Retry before creating.`;render();}}
  function init(){if(!savedUI.purposeDraftOwner&&savedUI.forms?.["purpose-goal"]&&!savedUI.unassignedPurposeDraft)savedUI.unassignedPurposeDraft=String(savedUI.forms["purpose-goal"]);delete initialForms["purpose-goal"];$("purpose-goal").value="";$("purpose-goal").addEventListener("input",()=>{capture();persistUI();});$("purpose-retry-owner").addEventListener("click",enter);$("purpose-copy-unassigned").addEventListener("click",()=>{if(!ready()||!savedUI.unassignedPurposeDraft)return;if($("purpose-goal").value.trim()){problem="Purpose draft conflict: edited text was preserved; unassigned original remains available.";render();return;}$("purpose-goal").value=savedUI.unassignedPurposeDraft;++purposeDraftVersion;problem="";capture();render();persistUI();});enter();}
  return {init,capture,leave,enter,ready,render};
})();
window.NoeticPurposeDrafts=purposeDrafts;


initWorkbench();
structuredDrafts.init();purposeDrafts.init();
$("import-previous-drafts").addEventListener("click", importPreviousDrafts);
$("forget-previous-drafts").addEventListener("click", forgetPreviousDrafts);
window.addEventListener("hashchange", () => {
  const token = new URLSearchParams(location.hash.slice(1)).get("token");
  if (token === null) return;
  history.replaceState(null, "", location.pathname + location.search);
  if (operatorToken) {
    // Replacing a pairing discards its private DOM and in-flight renderers before reopening.
    lockAccess(false, token);
    return;
  }
  operatorToken = token;
  ++accessVersion;
  unlockAccess();
});
$("access-form").addEventListener("submit", (event) => {
  event.preventDefault();
  operatorToken = $("access-token").value.trim();
  $("access-token").value = "";
  ++accessVersion;
  unlockAccess();
});
$("access-lock").addEventListener("click", () => lockAccess());
$("access-logout").addEventListener("click", () => lockAccess(true));
unlockAccess();
setInterval(refresh, 5000);


function reviewedSelectors(required = false) {
  const operation=$("reviewed-operation").value || "question";
  if(operation==="question")return {};
  const u64=value=>/^[1-9][0-9]*$/.test(value)&&value.length<=20&&BigInt(value)<=18446744073709551615n;
  if(operation==="judgment"){
    const warrant=$("reviewed-warrant-id").value.trim(),conditions=$("reviewed-condition-ids").value.split(/\r?\n/).map(value=>value.trim()).filter(Boolean);
    if(!u64(warrant)||!conditions.length||conditions.some((value,index)=>!u64(value)||index>0&&BigInt(value)<=BigInt(conditions[index-1]))){if(required)throw new Error("Enter the exact positive decimal warrant ID and complete strictly increasing condition IDs, one per line (u64). Native authority checks the complete set and eligibility.");return null;}
    return {warrant_id:warrant,condition_ids:conditions};
  }
  if(operation==="practical-question"){const judgments=$("reviewed-judgment-ids").value.split(/\r?\n/).map(value=>value.trim()).filter(Boolean);
    if(!judgments.length||judgments.some((value,index)=>!u64(value)||index>0&&BigInt(value)<=BigInt(judgments[index-1]))){if(required)throw new Error("Enter the exact positive decimal live Judgment IDs you select, one per line in strictly increasing order (u64). Native authority checks each Judgment's kind, whole retained context and current eligibility; IDs are never sorted, coalesced or inferred.");return null;}
    return {judgment_ids:judgments};}
  if(operation==="practical-inquiry"){const question=$("reviewed-practical-question-id").value.trim();
    if(!u64(question)){if(required)throw new Error("Enter the exact positive decimal active PracticalQuestion ID (u64) you select in this backing. Native authority checks the whole retained question, its Judgment basis and current cut; nothing is inferred or carried from other editors.");return null;}
    return {practical_question_id:question};}
  if(operation==="deliberation"){const question=$("reviewed-practical-question-id").value.trim(),options=$("reviewed-option-ids").value.split(/\r?\n/).map(value=>value.trim()).filter(Boolean);
    if(!u64(question)||options.length<2||options.some((value,index)=>!u64(value)||index>0&&BigInt(value)<=BigInt(options[index-1]))){if(required)throw new Error("Enter the exact positive decimal active PracticalQuestion ID (u64) and the complete current Option set for deliberation: at least two exact positive decimal Option IDs, one per line in strictly increasing order without duplicates. Native authority checks that every Option belongs to the same Question, the whole retained Judgment basis and the current cut; the complete set is never sorted, coalesced or inferred.");return null;}
    return {practical_question_id:question,option_ids:options};}
  if(operation==="checking"){const condition=$("reviewed-parent-id").value.trim(),warrant=$("reviewed-warrant-id").value.trim();
    if(!u64(condition)||!u64(warrant)){if(required)throw new Error("Enter the exact positive decimal warrant-condition ID and warrant ID (u64) in this backing. Native authority checks ancestry, closed evidence and eligibility.");return null;}
    return {parent_id:condition,warrant_id:warrant};}
  if(!["insight","formulation","reflection","conditional-structure"].includes(operation)){if(required)throw new Error("The selected operation's scoped editor is unavailable.");return null;}
  const parent=$("reviewed-parent-id").value.trim();
  if(!/^[1-9][0-9]*$/.test(parent)||parent.length>20||BigInt(parent)>18446744073709551615n){if(required)throw new Error("Enter the exact positive decimal native parent ID (u64) in this backing.");return null;}
  if(operation==="conditional-structure"){const formulation=$("reviewed-formulation-id").value.trim();if(!u64(formulation)){if(required)throw new Error("Enter the exact positive decimal native Formulation anchor ID (u64) in this backing.");return null;}return {parent_id:parent,formulation_id:formulation};}
  return {parent_id:parent};
}
function reviewedReady() {return reviewedSelectors()!==null;}
function reviewedOperation() {
  const operation=$("reviewed-operation").value || "question",parents={insight:"Question ID · intelligence-question",formulation:"Insight ID · unverified-insight-trace",reflection:"Formulation ID · formulation-hypothesis","conditional-structure":"Reflection ID · reflection-question",checking:"Condition ID · warrant condition"},descriptor=reviewedDefinition?.operations.find(x=>x.id===operation);
  $("reviewed-formulation-fields").hidden=operation!=="conditional-structure";
  $("reviewed-warrant-fields").hidden=!["judgment","checking"].includes(operation);
  $("reviewed-judgment-fields").hidden=operation!=="judgment";
  $("reviewed-practical-fields").hidden=operation!=="practical-question";
  $("reviewed-practical-question-fields").hidden=!["practical-inquiry","deliberation"].includes(operation);
  $("reviewed-options-fields").hidden=operation!=="deliberation";
  $("reviewed-checking-fields").hidden=operation!=="checking";
  $("reviewed-parent-fields").hidden=!parents[operation];text("reviewed-parent-label",parents[operation] || "Exact native parent ID");
  text("reviewed-operation-note",operation==="question"?"Initial question inquiry. Substantive task and selected sources are external evidence; native authority governs admission.":operation==="judgment"?"Judgment uses an exact conditional-structure warrant and its complete checked condition set. Task and sources remain external evidence; native authority governs evidence, ancestry, eligibility and admission.":operation==="checking"?"Checking uses one exact unchecked warrant condition and its warrant in the selected backing, with an explicit closed checking specification and retained whole context. The host validates binding and hashes and captures command evidence; native authority admits evidence-observation. A passed test and this editor never affirm judgment.":operation==="practical-question"?"Practical question asks, from the exact live Judgments you select, what to investigate or do next toward the effort purpose. Selected yea, nay and perchance voices and their limits stay whole; retrieved voices are never contribution-validated here. The explicit task is editable and asking grants no decision, plan or act authority; native eligibility governs admission.":operation==="practical-inquiry"?"Practical inquiry proposes one candidate course from the selected active PracticalQuestion toward the effort purpose. The exact selected question, its retained Judgment basis and the current native cut stay authoritative; one proposal is retained per inquiry, and further alternatives need a fresh inquiry. The task stays editable, and asking grants no decision, plan or act authority.":operation==="deliberation"?"Deliberation compares the entire current Option set for the selected active PracticalQuestion, with your explicit criteria, trade-offs, objections and value scale authored in the task. Native authority checks the complete set, every Option's same-Question membership, the whole retained Judgment basis and the current cut, and retains a native Evaluation from one current unverified insight trace for each Option; no winner, decision, plan, action or fulfillment follows, and the Question itself is unchanged. The task stays editable.":parents[operation]?`${operation[0].toUpperCase()+operation.slice(1)} uses the exact ${parents[operation]} in the selected backing. Task and selected sources remain external evidence; native authority governs eligibility and admission.`:`Native capacity retained. This operation needs ${[...(descriptor?.inputs || []),...(descriptor?.evidence_inputs || [])].join(", ") || "its native prerequisites"}. Its scoped input editor is unavailable in this increment. Select a supported operation to continue.`);
  $("start-submit").disabled=startPending||operationMode!=="effort"||!effortEnvironment||window.NoeticDrafts && !window.NoeticDrafts.ready()||!reviewedReady()||!$("reviewed-store").value||operation==="checking"&&!["reviewed-checking-spec","reviewed-checking-context"].every(id=>/^\/\S/.test($(id).value.trim()));
}
function renderReviewedSources() {
  $("reviewed-selected-sources").replaceChildren(...reviewedSources.map(source=>{
    const row = node("div",undefined,"reviewed-source"); const remove = node("button","Remove"); remove.type="button";
    remove.addEventListener("click",()=>{ reviewedSources=reviewedSources.filter(x=>x !== source); ++draftVersion; renderReviewedSources();persistUI(); });
    row.append(node("span",source.source_id),remove);return row;
  }));
}
async function loadReviewedSetup() {
  const version = ++reviewedVersion, scopeVersion=operationVersion, key=operationKey(), selection=operationSelection();
  reviewedLoading = true;
  try {
    const [catalog, backings] = await Promise.all([fetchJSON(scopedURL("/api/disciplines",selection)),fetchJSON(scopedURL("/api/opermem/stores",selection))]);
    if (version !== reviewedVersion || !operationValid(scopeVersion,key)) return;
    reviewedDefinition = catalog.definitions.find(x=>x.backend === "opermem-reviewed");
    setOptions("reviewed-operation", (reviewedDefinition?.operations || []).map(x=>[x.id,x.id[0].toUpperCase()+x.id.slice(1)]),"question");
    setOptions("reviewed-store",[["","Select backing explicitly"],...backings.stores.map(x=>[x.store_ref.id,x.store_ref.directory])],"");
    window.NoeticDrafts?.restoreChoice("reviewed-operation", (reviewedDefinition?.operations || []).map(x=>x.id));
    window.NoeticDrafts?.restoreChoice("reviewed-store", backings.stores.map(x=>x.store_ref.id));
    text("reviewed-store-status",backings.component?.available ? "Registered backings only. Current native standing remains unobserved." : backings.component?.reason || "Native component availability unobserved.");
    await loadReviewedLaunches();
  } catch (failure) { if (operationValid(scopeVersion,key)) text("reviewed-store-status",`Backing selection unavailable: ${failure.message}`); }
  finally { reviewedLoading=false; if (operationValid(scopeVersion,key) && isReviewed()) reviewedOperation(); }
}
async function registerReviewedStore() {
  const scopeVersion=operationVersion,key=operationKey(),selection=operationSelection();
  const directory=$("reviewed-directory").value.trim();
  $("reviewed-register").disabled=true;
  try {
    if (!selection.effort_root) throw new Error("Select an existing effort first.");
    const result=await fetchJSON("/api/opermem/stores",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({command_id:crypto.randomUUID(),...selection,directory})});
    if (!operationValid(scopeVersion,key)) return;
    await loadReviewedSetup(); if (!operationValid(scopeVersion,key)) return;
    $("reviewed-store").value=result.store_ref.id; $("reviewed-directory").closest("details").open=false; ++draftVersion; reviewedOperation();
    text("reviewed-store-status","Backing explicitly registered and selected. Native memory has not started.");
  } catch (failure) { if (operationValid(scopeVersion,key)) text("reviewed-store-status",`Registration unavailable: ${failure.message}`); }
  finally { $("reviewed-register").disabled=false; }
}
async function loadReviewedLaunches() {
  const scopeVersion=operationVersion,key=operationKey(),selection=operationSelection();
  try {
    const result=await fetchJSON(scopedURL("/api/application/launches",selection));
    if (!operationValid(scopeVersion,key)) return;
    const host=$("reviewed-launch-list"),signature=JSON.stringify(result.launches);
    if (host.dataset.signature !== signature) {
      host.dataset.signature=signature;
      const existing=new Map([...host.children].map(x=>[x.dataset.launchId,x]));
      for(const launch of result.launches){
        let row=existing.get(launch.launch_id);existing.delete(launch.launch_id);
        if(!row){row=node("article",undefined,"reviewed-launch");row.dataset.launchId=launch.launch_id;row.append(node("p"));const exact=node("details");exact.append(node("summary","Original launch identity and process evidence"),node("pre"));row.append(exact);host.append(row);}
        row.firstChild.textContent=`${launch.status} · ${launch.prepared_observed ? "original preparation observed" : "no execution claim"} · driver ${launch.driver_owned ? "owned" : "not owned"}`;
        const pre=row.querySelector("pre"),data=JSON.stringify(launch,null,2);if(pre.textContent!==data)pre.textContent=data;
        if(launch.run_id && !row.querySelector("button")){const inspect=node("button","Inspect original execution");inspect.type="button";inspect.addEventListener("click",()=>{if(operationValid(scopeVersion,key))selectRun(launch.run_id);});row.append(inspect);}
      }
      for(const row of existing.values())row.remove();
    }
    if(!result.launches.length && !host.textContent.trim())host.replaceChildren(node("p","No retained launch commands in this scope."));
    text("reviewed-launch-status",`Launch commands observed · ${result.launches.length} retained in this scope. Observation does not start work.`);
    if($("start-result").textContent.startsWith("Launch observation unavailable:"))text("start-result","");
    if (reviewedLaunch && reviewedLaunch.scopeKey===key) {
      const launch=result.launches.find(x=>x.launch_id===reviewedLaunch.id);
      if (launch) {
        text("start-result",`${launch.launch_id}: ${launch.status}. ${launch.run_id ? "Original run "+launch.run_id : "Preparation not yet observed; no execution claimed."}`);
        if (launch.run_id && reviewedLaunch.draft===draftVersion && reviewedLaunch.subject===developerSubjectVersion && !reviewedLaunch.selected) {reviewedLaunch.selected=true;await selectRun(launch.run_id);}
      }
    }
  } catch (failure) {if (operationValid(scopeVersion,key)) text("reviewed-launch-status",`Launch observation unavailable: ${failure.message}. Refresh retained commands before retrying.`);}
}
async function startReviewed({scopeVersion,scopeKey,draft,subject,selection,environment}) {
  if (!selection.effort_root || !environment) throw new Error("Select a registered effort first.");
  const operation=$("reviewed-operation").value || "question",selectors=reviewedSelectors(true);
  const checking=operation==="checking"?{checking_spec:$("reviewed-checking-spec").value.trim(),checking_context:$("reviewed-checking-context").value.trim()}:null;
  if(checking&&(!/^\/\S/.test(checking.checking_spec)||!/^\/\S/.test(checking.checking_context)))throw new Error("Checking requires explicit absolute checking-specification and retained checking-context source paths; the result and provenance are host-captured, not selected.");
  const task=$("start-task").value, store_id=$("reviewed-store").value;
  if (!store_id) throw new Error("Select a backing explicitly.");
  const sources=[...$("reviewed-sources").value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean),...reviewedSources];
  const assignment={backend:"opermem-reviewed",...selection,initiator:selection.effort_root,environment,origin:"human",human_ref:{origin:"local-human-operator"}};
  const payload={backend:"opermem-reviewed",command_id:crypto.randomUUID(),...selection,environment,origin:assignment.origin,human_ref:assignment.human_ref,task,workspace:environment.cwd,store_id,sources,mode:"inquiry",operation,selectors,...(checking||{}),client:$("start-client").value,model:$("start-model").value || null,qa_model:$("start-qa-model").value || null,timeout:Number($("start-timeout").value),...$("start-client").value==="pi" ? {thinking:$("start-thinking").value} : {},...$("start-purpose").value ? {purpose_ref:JSON.parse($("start-purpose").value)} : {}};
  const instance=await fetchJSON("/api/disciplines",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...assignment,command_id:crypto.randomUUID(),intent:task})});
  // Instance creation is useful retained work; a changed scope or edited draft does not authorize its launch.
  if (!operationValid(scopeVersion,scopeKey) || draft!==draftVersion || subject!==developerSubjectVersion) return;
  const result=await fetchJSON("/api/application/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...payload,discipline_id:instance.discipline.id})});
  if (!operationValid(scopeVersion,scopeKey)) return;
  reviewedLaunch={id:result.launch_id,scopeKey,draft,subject,selected:false};
  text("start-result",`${result.launch_id}: ${result.status}. ${result.run_id ? "Original run "+result.run_id : "No execution claim until original preparation is observed."}`);
  $("reviewed-launches").open=true; await loadReviewedLaunches(); await refresh();
}
function renderCapturedSources(host, artifact, runId) {
  let panel=[...host.children].find(x=>x.dataset.key==="captured-source-preview");
  if(!panel){panel=node("details");panel.dataset.key="captured-source-preview";host.append(panel);}
  const signature=JSON.stringify([runId,artifact||null]);
  if(panel.dataset.signature===signature)return;
  panel.dataset.signature=signature;
  const unavailable=message=>panel.replaceChildren(node("summary","Captured host source preview · unavailable"),node("p",message,"source"));
  if(!artifact||artifact.error||typeof artifact.text!=="string"||artifact.truncated){
    unavailable(!artifact?"No retained raw text for opermem-scope.json was observed for this run, so no captured host source preview is available."
      :artifact.error?`Captured opermem-scope.json read error: ${artifact.error}; no captured host source preview is available.`
      :artifact.truncated?"Captured opermem-scope.json is truncated; a captured host source preview is unavailable to avoid misleading partial captured text."
      :"Captured opermem-scope.json carries no raw text; no captured host source preview is available.");return;
  }
  let rows;try{const parsed=JSON.parse(artifact.text);rows=parsed&&Array.isArray(parsed.host_sources)?parsed.host_sources:null;}catch{rows=null;}
  if(!rows){unavailable("Captured opermem-scope.json is malformed (no readable host_sources array); no captured host source preview is available.");return;}
  const records=rows.filter(r=>r&&typeof r.path==="string"&&typeof r.sha256==="string"&&typeof r.bytes_base64==="string");
  if(!records.length){unavailable("Captured opermem-scope.json retains no host source records; no captured host source preview is available.");return;}
  const decode=rec=>{
    const where=`${rec.path} · recorded sha256 ${rec.sha256}`;
    if(rec.kind!=="external-host-evidence"||rec.native_retained_experience!==false)return {error:`${where} · preview unavailable: unsupported captured record qualification; no captured text is shown.`};
    if(!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(rec.bytes_base64))return {error:`${where} · preview unavailable: invalid base64 captured bytes; no captured text is shown.`};
    let bytes;try{bytes=[...atob(rec.bytes_base64)].map(c=>c.charCodeAt(0));}catch{return {error:`${where} · preview unavailable: invalid base64 captured bytes; no captured text is shown.`};}
    if(bytes.includes(0))return {error:`${where} · preview unavailable: captured bytes contain binary NUL and are not rendered as text.`};
    try{return {text:new TextDecoder("utf-8",{fatal:true}).decode(new Uint8Array(bytes))};}
    catch{return {error:`${where} · preview unavailable: captured bytes are not valid UTF-8 text; no decoded text is shown.`};}
  };
  panel.replaceChildren(node("summary","Captured host source preview · external host evidence · historical captured bytes · not native Experience; no current file fetch"));
  const chosen=records.find(r=>r.path===panel.dataset.selected)||records[0];
  panel.dataset.selected=chosen.path;
  const select=node("select");select.className="source";select.setAttribute("aria-label","Captured host source record");
  for(const r of records){const option=node("option",r.path);option.value=r.path;option.selected=r===chosen;select.append(option);}
  const locator=node("p",undefined,"source"),pre=node("pre");
  const show=()=>{
    const rec=records.find(r=>r.path===select.value)||records[0];panel.dataset.selected=rec.path;
    const decoded=decode(rec);
    if(decoded.error){locator.textContent=decoded.error;pre.replaceChildren();}
    else{locator.textContent=`${rec.path} · recorded sha256 ${rec.sha256} · external host evidence / historical captured bytes / not native Experience; no current file fetch.`;pre.textContent=decoded.text;}
  };
  select.addEventListener("change",show);
  panel.append(select,locator,pre);show();
}
function renderRawArtifact(host, name, artifact) {
  if (!artifact || artifact.error || typeof artifact.text !== "string") {
    const message = !artifact ? `No retained raw text for ${name} observed. No rounded native projection is substituted.`
      : artifact.error ? `${artifact.source_path || name} · read error: ${artifact.error}. No rounded native projection is substituted.`
      : `${artifact.source_path || name} · retained artifact carries no raw text. No rounded native projection is substituted.`;
    host.replaceChildren(node("p", message, "source"));return;
  }
  const note = `${artifact.source_path || name} · ${artifact.truncated ? "truncated to the first 1048576 bytes; full original remains in the local file" : artifact.text === "" ? "file exists and is empty" : "retained original bytes"} · historical evidence only; current Opermem standing is assessed separately.`;
  if (host.children.length === 2 && host.children[0].textContent === note && host.children[1].textContent === artifact.text) return;
  const pre = node("pre");pre.textContent = artifact.text;
  host.replaceChildren(node("p", note, "source"), pre);
}
function renderReviewedDetail(detail) {
  queueMicrotask(()=>document.dispatchEvent(new CustomEvent("noetic:run-detail",{detail:{run:detail}})));
  const {status,application:info,correspondence,preparation,population}=detail;
  text("run-id",`${correspondence.effort_root} · discipline ${correspondence.discipline_id} · execution ${correspondence.execution_id} · ${status.run_id}`);
  text("run-goal",status.goal);text("task-body",status.goal);text("run-state",status.state);text("state-note","External review, native disposition and purpose synchronization are separate observations.");
  text("workspace",preparation.workspace);text("goal-ref",preparation.purpose_ref ? JSON.stringify(preparation.purpose_ref) : "No purpose linked");text("last-event",detail.events.at(-1)?.occurred_at || "No journal event");text("detail-observed",date(detail.observed_at));
  for(const field of ["controller-pattern","controller-machine","controller-phase","controller-generation","controller-budgets","controller-actor","controller-source","cancel-note","telos-chain","telos-subgoal","telos-result"])text(field,"Not applicable to reviewed inquiry; original evidence above.");
  $("controller-phases").replaceChildren();
  const n=info.native;
  const driverSummary={...info,native:{...n,receipt:"Inspect the opermem-receipt.json raw row for observed source and qualification; historical evidence only."}};
  text("driver-data",JSON.stringify(driverSummary,null,2));
  text("event-count",`${detail.events.length} retained events`);text("journal-source",preparation.run_dir);
  const eventSignature=JSON.stringify(detail.events);if(timelineSignature!==eventSignature){timelineSignature=eventSignature;renderEventWindow("timeline",detail.events,event=>{const item=node("li");item.append(node("p","Browser projection of a parsed journal event row; the original journal remains locally retained.","source"),node("pre",JSON.stringify(event,null,2)));return item;});}
  renderEvidence("report",$("report-select").value);renderEvidence("log",$("log-select").value);
  $("controller-summary").hidden=false;$("legacy-execution").hidden=true;$("workspace-result").hidden=true;$("workspace-apply").hidden=true;
  for(const id of ["advance-one","advance-all","pause-pattern","cancel-pattern","phases-tab","compare-tab","controller-tab"])$(id).hidden=true;
  const identity=p=>`${p.ordinal}${p.target ? ` · context ${p.target.instantiation}/${p.target.session}` : " · native target unobserved"} · ${p.role}`;
  const actors=population || [];setOptions("session-select",actors.map(p=>[p.role,identity(p)]),"work");
  renderSessionAgents(actors.map(p=>[p.role,identity(p),p.status]));
  text("primary-agent",identity(actors.find(p=>p.role===$("session-select").value)||{ordinal:"unobserved",role:"participant"}));
  text("primary-model",`${info.configuration.client} · ${info.configuration.model || "client default"} · review ${info.configuration.qa_model || "inherits main"}`);
  text("primary-progress",`${preparation.operation} · ${status.state}`);text("driver-activity",info.reason);text("steering-note",info.unavailable_controls);
  $("primary-attention").hidden=true;
  text("reviewed-progress",`${info.driver?.launch_id || "Launch mapping unavailable"} · ${info.driver?.status || info.activity}. Driver ownership ${info.driver?.driver_owned ? "observed" : "not observed"}; this does not establish model progress.`);
  $("reviewed-dispositions").replaceChildren(...[`External review: ${info.review.outcome || "not recorded"}`,`Native: ${n.disposition}`,`Telos: ${n.telos_error ? "synchronization error" : n.telos ? "result retained" : preparation.purpose_ref ? "not synchronized" : "no link"}`].map(x=>node("span",x)));
  const report=(detail.artifacts["work.md"]?.text || "No substantive report retained yet.").split("OPERMEM_CONTRIBUTION_JSON:")[0].trim();
  if ($("reviewed-report").dataset.text!==report){$("reviewed-report").dataset.text=report;$("reviewed-report").replaceChildren(window.NoeticRichText ? window.NoeticRichText(report,{id:status.run_id,kind:"run",selection:operationSelection(),viewVersion:operationVersion}) : node("pre",report));}
  text("reviewed-review-text",detail.artifacts["review.md"]?.text || "No external review retained yet.");
  $("reviewed-recover-contribution").hidden=!info.actions.recover_contribution;
  $("reviewed-recover-correlation").hidden=!info.actions.recover_correlation;
  const host=$("reviewed-evidence-content");
  for(const name of ["opermem-link.json","opermem-scope.json","opermem-receipt.json","opermem-pending.json"]){let item=[...host.children].find(x=>x.dataset.key===name);if(!item){item=node("details");item.dataset.key=name;item.append(node("summary",`${name} · retained original raw text (historical bytes, not current Opermem standing)`),node("div",undefined,"raw-artifact"));host.append(item);}renderRawArtifact(item.lastChild,name,detail.artifacts[name]);}
  renderCapturedSources(host, detail.artifacts["opermem-scope.json"], status.run_id);
  const link={...correspondence,native_link:"Inspect the whole opermem-link.json raw row for observed source and qualification; historical evidence only."};
  const rows=[["Preparation summary (browser projection)",preparation],["Actual participants and correspondence summary",link],["Launch and separate dispositions",driverSummary],["Ordered events (browser projection; original journal locally retained)",detail.events]];
  for(const [label,value] of rows){let item=[...host.children].find(x=>x.dataset.key===label);if(!item){item=node("details");item.dataset.key=label;item.append(node("summary",label),node("pre"));host.append(item);}const data=JSON.stringify(value,null,2);if(item.lastChild.textContent!==data)item.lastChild.textContent=data;}
  text("summary-selection",status.run_id);$("summary-generate").disabled=true;
  $("empty-state").hidden=true;$("selected-run").hidden=false;$("session-tab").hidden=false;
}
async function recoverReviewed(kind) {
  const id=selectedId,version=operationVersion,key=operationKey();
  const button=$("reviewed-recover-"+kind);button.disabled=true;
  try {const result=await fetchJSON(`/api/runs/${encodeURIComponent(id)}/recover-${kind}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(operationSelection())});if(id===selectedId && operationValid(version,key)){text("reviewed-recovery-status",`Retained ${kind} recovery recorded. Native: ${result.application?.native?.disposition || "inspect original evidence"}. ${result.actors_replayed === false ? "No actors replayed." : "Original correspondence restored."}`);await loadDetail();}}
  catch(failure){if(id===selectedId && operationValid(version,key))text("reviewed-recovery-status",`Recovery unavailable: ${failure.message}`);}
  finally{button.disabled=false;}
}
