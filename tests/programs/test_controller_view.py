"""Implementation checks with temporary kernels and a DOM contract, not live work or QA."""

from contextlib import closing
import fcntl
import http.client
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from scripts import noetic_controller as controller
from scripts import noetic_harness as harness
from scripts import noetic_run as runtime
from scripts import noetic_web as web


class ControllerViewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runs = self.root / "runs"
        self.server = web.create_server(self.runs, port=0)
        self.server.RequestHandlerClass.log_message = lambda *args: None
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, route, expected=200, method="GET", body=None, headers=None, scoped=True):
        if scoped and method in ("GET", "HEAD") and route.startswith(("/api/runs", "/api/search")):
            route += ("&" if "?" in route else "?") + "scope=application"
        if scoped and method == "POST" and route.startswith("/api/runs/") and isinstance(body, str):
            try:
                data = json.loads(body)
            except ValueError:
                pass
            else:
                if isinstance(data, dict):
                    body = json.dumps({"scope": "application", **data})
        with closing(http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)) as connection:
            connection.request(method, route, body=body, headers=headers or {})
            response = connection.getresponse()
            content = response.read()
            self.assertEqual(response.status, expected, content)
            self.assertEqual(response.getheader("Cache-Control"), "no-store")
            return json.loads(content) if content else None

    def start(self, pattern="development", **budgets):
        run = runtime.create_run({"goal": "Test-authored operator fixture", "work": ["unused"]}, self.root, self.runs)
        (run / "options.json").write_text(json.dumps({"pattern": pattern, "telos_chain": None}))
        state = controller.start_run(run / "controller.sqlite3", controller.PATTERN_DIR / f"{pattern}.json",
                                     "Test-authored operator fixture", self.root, **budgets)
        return run, state

    def submit(self, run, state, result=None, verdict="pass"):
        activation = state["activations"][state["current_activation"]]
        if result is None:
            phase = state["pattern"]["phases"][state["phase_index"]]
            if activation["mode"] == "review":
                result = {"subject_artifact_id": state["subject_artifact_id"], "verdict": verdict,
                          "report": "Fixture check against explicit criteria",
                          "findings": [] if verdict == "pass" else [{"description": "Fixture missing result", "blocking": True}]}
            else:
                result = {"outcome": "produced" if activation["mode"] == "produce" else
                          "complete" if phase["id"] == "P4" else "advance",
                          "content": {key: "Fixture <script>not HTML</script>" if kind == "string" else
                                      [f"fixture {phase['id']} visit {activation['visit']}"]
                                      for key, kind in phase["content_fields"].items()}}
        store = run / "controller.sqlite3"
        if activation["status"] == "ready":
            state = controller.begin_activation(store, activation["id"], state["version"])
        return controller.submit_result(store, activation["id"], state["version"], result,
                                        f"fixture:{activation['id']}", f"command:{activation['id']}")

    def development(self):
        run, state = self.start()
        while state["status"] == "active":
            a = state["activations"][state["current_activation"]]
            fail = a["phase"] == "implementation" and a["generation"] == 0 and a["mode"] == "review"
            state = self.submit(run, state, verdict="fail" if fail else "pass")
        return run, state

    def cognition(self):
        run, state = self.start("cognition")
        state = self.submit(run, state)
        state = self.submit(run, state, {
            "outcome": "return", "target": "P1", "reason": "Fixture needs measurement",
            "question": "What is the measured value?", "content": {"hypotheses": ["Partial fixture hypothesis"]},
        })
        returned = state
        while state["status"] == "active":
            state = self.submit(run, state)
        return run, returned, state

    def snapshot(self):
        return {str(path.relative_to(self.runs)): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.runs.rglob("*") if path.is_file()}

    def detail(self, run):
        return self.request(f"/api/runs/{run.name}")

    def test_missing_scope_is_rejected_without_mutating_controller(self):
        run, state = self.start()
        before = self.snapshot()
        with patch.object(web.harness, "cancel", wraps=harness.cancel) as cancel:
            for method in ("GET", "HEAD"):
                for route in ("/api/runs", f"/api/runs/{run.name}", "/api/search?q=fixture"):
                    self.request(route, 400, method, scoped=False)
            self.request(f"/api/runs/{run.name}/cancel", 400, "POST", '{"confirm":true}',
                         {"Content-Type": "application/json"}, scoped=False)
            cancel.assert_not_called()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(controller.inspect_run(run / "controller.sqlite3"), state)

    def cancel(self, run, expected=200, **kwargs):
        return self.request(f"/api/runs/{run.name}/cancel", expected, "POST",
                            kwargs.get("body", '{"confirm":true}'),
                            kwargs.get("headers", {"Content-Type": "application/json"}))

    def test_kernel_authority_refreshes_despite_stale_export_and_outer_acceptance(self):
        run, state = self.start()
        (run / "controller.json").write_text(json.dumps({**state, "status": "completed"}))
        runtime.record(run, "review.recorded", {"verdict": "accept", "reviewer": "fixture", "evidence": "Stale outer evidence"})
        first = self.detail(run)
        self.assertEqual(first["controller"], state)
        self.assertEqual(first["status"]["state"], "active")
        self.assertEqual(first["status"]["journal_state"], "accepted")
        state = self.submit(run, state)
        current = self.detail(run)
        self.assertEqual(current["controller"], controller.inspect_run(run / "controller.sqlite3"))
        self.assertEqual(current["status"]["machine_state"], "qa_review")
        self.assertEqual(current["status"]["current_actor"], "actor-1")
        self.assertEqual(current["status"]["current_ordinal"], "0.1")
        summary = self.request("/api/runs")["runs"][0]
        self.assertEqual(summary["state"], "active")
        self.assertEqual(summary["machine_state"], "qa_review")
        self.assertEqual(summary["current_phase"], "design_intent")
        self.assertEqual(summary["controller_version"], state["version"])
        self.assertEqual(summary["current_ordinal"], "0.1")
        state = controller.runtime_failed(run / "controller.sqlite3", state["current_activation"], state["version"], "Fixture failed")
        self.assertEqual(self.detail(run)["controller"], state)
        self.assertEqual(self.request("/api/runs")["runs"][0]["state"], "failed")

    def test_development_ordinals_phases_remediation_artifacts_and_events(self):
        run, state = self.development()
        for event in state["events"]:
            runtime.record(run, "controller.event", event)
        detail = self.detail(run)
        self.assertEqual(detail["controller"], state)
        self.assertEqual(detail["status"]["state"], "completed")
        self.assertIsNone(detail["status"]["current_actor"])
        actors = sorted(state["actors"].values(), key=lambda a: int(a["ordinal"].split(".")[1]))
        self.assertEqual([a["ordinal"] for a in actors], [f"0.{i}" for i in range(10)])
        self.assertTrue(all(a["status"] == "retired" and a["session_ref"] for a in actors))
        self.assertEqual(len({a["session_ref"] for a in actors}), 10)
        self.assertEqual(len([s for s in state["slots"] if s.startswith("accepted.")]), 4)
        subject = state["artifacts"][state["slots"]["accepted.implementation"]]
        self.assertEqual(subject["generation"], 1)
        self.assertEqual(subject["type"], "development.implementation")
        self.assertIn("<script>", subject["content"]["report"])
        failed = next(a for a in state["artifacts"].values() if a["type"] == "qa.review" and a["content"]["verdict"] == "fail")
        self.assertNotEqual(failed["content"]["subject_artifact_id"], subject["id"])
        self.assertEqual([e["data"] for e in detail["events"] if e["kind"] == "controller.event"], state["events"])

    def test_cognitive_returns_partial_historical_and_current_effective(self):
        run, returned, state = self.cognition()
        self.assertEqual(returned["returns_used"], 1)
        self.assertNotIn("effective.P1", returned["slots"])
        detail = self.detail(run)
        self.assertEqual(detail["controller"], state)
        activations = sorted(state["activations"].values(), key=lambda a: a["ordinal"])
        self.assertEqual([a["phase"] for a in activations], ["P1", "P2", "P1", "P2", "P3", "P4"])
        self.assertEqual(state["visits"], {"P1": 2, "P2": 2, "P3": 1, "P4": 1})
        partial = next(a for a in state["artifacts"].values() if a["partial"])
        self.assertNotIn(partial["id"], state["slots"].values())
        feedback = state["artifacts"][state["feedback"][-1]]
        self.assertTrue(feedback["content"]["accepted"])
        self.assertEqual(feedback["content"]["question"], "What is the measured value?")
        event = next(e for e in state["events"] if e["kind"] == "cognition.returned")
        historical = event["data"]["invalidated"]["effective.P1"]
        self.assertIn(historical, state["artifacts"])
        self.assertNotEqual(historical, state["slots"]["effective.P1"])
        self.assertEqual(len([s for s in state["slots"] if s.startswith("effective.")]), 4)
        self.assertFalse(any(s.startswith("accepted.") for s in state["slots"]))

    def test_legacy_missing_corrupt_and_outside_controller(self):
        run = runtime.create_run({"goal": "Legacy fixture"}, self.root, self.runs)
        (run / "controller.json").write_text('{"status":"completed"}')
        detail = self.detail(run)
        self.assertIsNone(detail["controller"])
        self.assertEqual(detail["status"], runtime.project(runtime.read_events(run)))
        self.cancel(run, 409)
        self.request("/api/runs/missing", 404)
        broken, _ = self.start()
        (broken / "controller.sqlite3").write_bytes(b"not sqlite")
        self.assertIn("Cannot read local evidence", self.request(f"/api/runs/{broken.name}", 422)["error"])
        self.cancel(broken, 422)
        listing = self.request("/api/runs")
        self.assertEqual([r["run_id"] for r in listing["runs"]], [run.name])
        self.assertTrue(any(broken.name in warning for warning in listing["warnings"]))
        malformed, _ = self.start()
        with closing(sqlite3.connect(malformed / "controller.sqlite3")) as connection:
            with connection:
                connection.execute("UPDATE run SET state = '{}' WHERE id = 1")
        self.request(f"/api/runs/{malformed.name}", 422)
        outside = self.root / "outside.sqlite3"
        controller.start_run(outside, controller.PATTERN_DIR / "cognition.json", "Outside fixture", self.root)
        (broken / "controller.sqlite3").unlink()
        (broken / "controller.sqlite3").symlink_to(outside)
        self.request(f"/api/runs/{broken.name}", 403)
        self.cancel(broken, 403)

    def test_named_actor_files_are_bounded_and_contained(self):
        run, state = self.start()
        activation = state["current_activation"]
        directory = run / "activations" / activation
        directory.mkdir(parents=True)
        route = f"/api/runs/{run.name}/activations/{activation}/logs/"
        for name in web.ACTOR_ARTIFACT_NAMES:
            (directory / name).write_text(f"Fixture {name} <img src=x>")
            result = self.request(route + name)
            self.assertEqual(result["text"], f"Fixture {name} <img src=x>")
            self.assertEqual(result["activation_id"], activation)
            self.assertFalse(result["truncated"])
        (directory / "actor.stdout.log").write_bytes(b"x" * (web.ARTIFACT_LIMIT + 10))
        result = self.request(route + "actor.stdout.log")
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["text"]), web.ARTIFACT_LIMIT)
        (directory / "actor.stderr.log").write_bytes(b"fixture \xff")
        self.assertEqual(self.request(route + "actor.stderr.log")["text"], "fixture \ufffd")
        (directory / "prompt.txt").unlink()
        self.request(route + "prompt.txt", 404)
        for name in ("options.json", "response.json", "..%2Fprompt.txt", "%2Fetc%2Fpasswd"):
            self.request(route + name, 400)
        unknown = run / "activations" / "activation-999"
        unknown.mkdir()
        (unknown / "prompt.txt").write_text("Not in kernel")
        self.request(f"/api/runs/{run.name}/activations/activation-999/logs/prompt.txt", 404)
        self.request(f"/api/runs/{run.name}/activations/%2e%2e/logs/prompt.txt", 400)
        external = self.root / "external.txt"
        external.write_text("Outside evidence")
        (directory / "prompt.txt").symlink_to(external)
        self.request(route + "prompt.txt", 403)
        other, other_state = self.start()
        (other / "activations").symlink_to(run / "activations", target_is_directory=True)
        self.request(f"/api/runs/{other.name}/activations/{other_state['current_activation']}/logs/actor.stdout.log", 403)

    def test_get_head_and_rejected_controls_never_mutate_stores(self):
        run, state = self.start()
        directory = run / "activations" / state["current_activation"]
        directory.mkdir(parents=True)
        (directory / "prompt.txt").write_text("Fixture prompt")
        (self.runs / ".memory.sqlite3").write_bytes(b"Disk index sentinel")
        before = self.snapshot()
        origin = f"http://127.0.0.1:{self.server.server_port}"
        with patch.object(web.harness, "cancel", wraps=harness.cancel) as cancel:
            for method in ("GET", "HEAD"):
                for route in ("/api/runs", f"/api/runs/{run.name}", "/api/search?q=fixture",
                              f"/api/runs/{run.name}/activations/activation-0/logs/prompt.txt"):
                    self.request(route, method=method)
                self.request(f"/api/runs/{run.name}/cancel", 400, method)
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                self.request(f"/api/runs/{run.name}", 405, method)
            for method in ("PUT", "PATCH", "DELETE"):
                self.request(f"/api/runs/{run.name}/cancel", 405, method)
            self.cancel(run, 415, headers={"Content-Type": "text/plain"})
            for body in ('{}', '[]', 'not json', '{"confirm":false}', '{"confirm":1}', '{"confirm":true,"task":"new"}'):
                self.cancel(run, 400, body=body)
            self.cancel(run, 400, body="x" * 1025)
            for rejected in ("http://elsewhere.invalid", "null", origin.replace("http:", "https:")):
                self.cancel(run, 403, headers={"Content-Type": "application/json", "Origin": rejected})
            cancel.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_explicit_cancel_and_terminal_cleanup_preserve_outcomes(self):
        run, _ = self.start()
        origin = f"http://127.0.0.1:{self.server.server_port}"
        with patch.object(web.harness, "cancel", wraps=harness.cancel) as cancel:
            result = self.cancel(run, headers={"Content-Type": "application/json", "Origin": origin})
            cancel.assert_called_once_with(run)
        self.assertTrue(result["cancel_requested"])
        self.assertEqual(result["controller"]["status"], "cancelled")
        self.assertEqual(self.detail(run)["controller"]["status"], "cancelled")
        completed, _ = self.development()
        for terminal in (completed, run):
            before = harness.inspect(terminal)
            result = self.cancel(terminal)
            self.assertEqual(result["controller"], before)
            self.assertEqual(result["cleanup_confirmed"], terminal == run)
            self.assertIn("terminal outcome unchanged", result["message"])
        self.assertFalse((completed / "cancel.requested").exists())

    def test_cancel_request_is_not_terminal_while_driver_owns_run(self):
        run, state = self.start("cognition")
        state = controller.begin_activation(run / "controller.sqlite3", state["current_activation"], state["version"])
        # A cooperative driver lock, with no processes or model calls.
        with (run / "driver.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.cancel(run, 202)
            self.assertTrue(result["cancel_requested"])
            self.assertEqual(result["controller"], state)
            self.assertIn("still active", result["message"])
            detail = self.detail(run)
            self.assertTrue(detail["cancel_requested"])
            self.assertEqual(detail["status"]["state"], "active")
            self.cancel(run, 202)
        self.assertEqual(controller.inspect_run(run / "controller.sqlite3"), state)

    @unittest.skipUnless(shutil.which("node"), "Node is needed only for the executable DOM contract")
    def test_dom_contract_renders_kernel_history_and_preserves_selections(self):
        development, _ = self.development()
        cognitive, returned, _ = self.cognition()
        active, _ = self.start("cognition")
        legacy = runtime.create_run({"goal": "Legacy fixture"}, self.root, self.runs)
        for event in controller.inspect_run(cognitive / "controller.sqlite3")["events"]:
            runtime.record(cognitive, "controller.event", event)
        development_detail, cognitive_detail = self.detail(development), self.detail(cognitive)
        returned_detail = {**cognitive_detail, "controller": returned,
                           "status": {**cognitive_detail["status"], **web.controller_summary(returned)}}
        payload = {"html": (web.WEB_DIR / "index.html").read_text(), "script": (web.WEB_DIR / "app.js").read_text(),
                   "development": development_detail, "cognitive": cognitive_detail, "returned": returned_detail,
                   "active": self.detail(active), "legacy": self.detail(legacy), "runs": self.request("/api/runs")["runs"]}
        self.assertNotIn("innerHTML", payload["script"])
        self.assertNotIn("insertAdjacentHTML", payload["script"])
        result = subprocess.run(["node", "-e", DOM_CONTRACT], input=json.dumps(payload), text=True,
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


# A deliberately small DOM adapter executes the shipped rendering functions.
# It checks the contract, not browser layout, accessibility audits, or model work.
DOM_CONTRACT = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
let input = '';
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', async () => {
  const fixture = JSON.parse(input);
  class Element {
    constructor(tag) { this.tagName=tag.toUpperCase(); this.defaultValue=''; this.children=[]; this.dataset={}; this.attributes={}; this.handlers={}; this.hidden=false; this._text=''; this.classList={remove(){},toggle(){return true;}}; }
    set textContent(value) { this.replaceChildren(); this._text=String(value); }
    get textContent() { return this._text+this.children.map(child=>child.textContent).join(''); }
    set value(value) { this._value=value; }
    get value() { return this._value ?? this.children[0]?.value ?? ''; }
    set id(value) { this.attributes.id=String(value); elements.set(String(value),this); }
    get id() { return this.attributes.id || ''; }
    get options() { return this.children; }
    get selectedOptions() { return this.children.filter(child=>child.value===this.value); }
    get nodeType() { return 1; }
    get childNodes() {
      const owner=this;
      this._textNode ||= {nodeType:3, parentNode:this,
        get textContent() { return owner._text; }, set textContent(value) { owner._text=String(value); },
        replaceWith(item) { owner._text=''; owner.insertBefore(item,owner.children[0] || null); }};
      return this._text ? [this._textNode,...this.children] : [...this.children];
    }
    get firstChild() { return this.childNodes[0] || null; }
    get lastChild() { return this.childNodes.at(-1) || null; }
    append(...items) { for(const item of items) this.insertBefore(item,null); }
    replaceChildren(...items) { for(const child of this.children) child.parentNode=null; this.children=[]; this._text=''; if(this.tagName==='SELECT') delete this._value; this.append(...items); }
    insertBefore(item,reference) {
      if(item===reference) return item;
      if(item.parentNode) item.parentNode.children=item.parentNode.children.filter(child=>child!==item);
      const index=reference ? this.children.indexOf(reference) : this.children.length;
      this.children.splice(index<0 ? this.children.length : index,0,item); item.parentNode=this;
      if(item.id) elements.set(item.id,item); return item;
    }
    before(...items) { if(this.parentNode) for(const item of items) this.parentNode.insertBefore(item,this); }
    replaceWith(item) { if(this.parentNode) { this.parentNode.insertBefore(item,this); this.remove(); } }
    remove() { if(this.parentNode) this.parentNode.children=this.parentNode.children.filter(child=>child!==this); this.parentNode=null; if(this.id && elements.get(this.id)===this) elements.delete(this.id); }
    contains(item) { return this===item || this.children.some(child=>child.contains(item)); }
    setAttribute(key,value) { if(key==='id') this.id=value; else this.attributes[key]=String(value); }
    getAttribute(key) { return this.attributes[key] ?? null; }
    hasAttribute(key) { return Object.hasOwn(this.attributes,key); }
    removeAttribute(key) { delete this.attributes[key]; }
    addEventListener(key,handler) { this.handlers[key]=handler; }
    focus() {}
    scrollIntoView() {}
    querySelectorAll(selector) {
      const descendants=this.children.flatMap(child=>[child,...child.querySelectorAll('*')]);
      return descendants.filter(child=>selector==='*' || child.tagName===selector.toUpperCase() || (selector==='details[open]' && child.tagName==='DETAILS' && child.open));
    }
    querySelector(selector) {
      const value=selector.match(/^\[value="([^"]+)"\]$/)?.[1];
      return value==null ? this.querySelectorAll(selector)[0] || null : this.children.find(child=>child.value===value) || null;
    }
  }
  const elements = new Map(), views = [], pages = [];
  const documentRoot = new Element('body');
  for (const match of fixture.html.matchAll(/<([a-z0-9-]+)\b([^>]*)>/g)) {
    const element = new Element(match[1]);
    for (const attr of match[2].matchAll(/([a-z-]+)="([^"]*)"/g)) {
      element.setAttribute(attr[1], attr[2]);
      if (attr[1] === 'id') elements.set(attr[2], element);
      if (attr[1] === 'data-view') { element.dataset.view = attr[2]; views.push(element); }
      if (attr[1] === 'data-page') { element.dataset.page = attr[2]; pages.push(element); }
      if (attr[1] === 'value') element.value = element.defaultValue = attr[2];
    }
    element.hidden = /\bhidden\b/.test(match[2]);
    documentRoot.append(element);
  }
  for (const match of fixture.html.matchAll(/<select\b[^>]*id="([^"]+)"[^>]*>([\s\S]*?)<\/select>/g)) {
    const select = elements.get(match[1]);
    for (const option of match[2].matchAll(/<option\b[^>]*value="([^"]*)"[^>]*>/g)) {
      const child = new Element('option'); child.value = option[1]; select.append(child);
    }
  }
  const el = id => { assert.ok(elements.has(id), `Missing DOM id ${id}`); return elements.get(id); };
  const requests = [], storage = new Map();
   const sandbox = { fixture, console, AbortController, structuredClone, URL, URLSearchParams, MutationObserver: class { observe() {} }, CustomEvent: class { constructor(type, options) { this.type=type; Object.assign(this,options); } }, queueMicrotask, setTimeout: () => 1, clearTimeout() {}, setInterval() {},
    location: {hash: '#run-detail', pathname: '/', search: '', origin: 'http://127.0.0.1:8765', reload() {}},
    history: {replaceState() {}},
    localStorage: {removeItem() {}},
    sessionStorage: {getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key)},
    window: { confirm: () => false, addEventListener() {} },
    fetch: (url, options) => { requests.push({url, options}); return new Promise(() => {}); },
    document: { addEventListener() {}, dispatchEvent: () => true, getElementById: id=>elements.get(id) || null, createElement: tag => new Element(tag),
      querySelector: selector => selector === 'label[for="start-sources"]' ? documentRoot.children.find(child=>child.tagName==='LABEL' && child.getAttribute('for')==='start-sources') || null : null,
      querySelectorAll: selector => selector === '[data-page]' ? pages : views } };
  vm.createContext(sandbox);
  vm.runInContext(fixture.script, sandbox);
  const run = code => vm.runInContext(code, sandbox);
  const transcriptTool = run('transcriptEntry({kind:"tool", event_type:"tool_use", timestamp:1700000000000, content:{tool:"read", state:{status:"completed", input:{filePath:"fixture.txt"}, output:"Fixture data\\nSecond line"}}})');
  assert.match(transcriptTool.textContent, /Tool read \/ completed/);
  assert.match(transcriptTool.textContent, /Fixture data\nSecond line/);
  assert.deepEqual(transcriptTool.querySelectorAll('summary').map(item=>item.textContent), ['Tool input', 'Tool output']);
  const transcriptFinal = run('transcriptEntry({kind:"final",content:{final:{stopReason:"stop",content:[{type:"text",text:"Fixture final answer"}]}}})');
  assert.match(transcriptFinal.textContent, /Final response · stop/);
  assert.match(transcriptFinal.textContent, /Fixture final answer/);
  const show = name => {
    run(`selectedDetail = fixture.${name}; selectedId = selectedDetail.status.run_id; renderDetail(selectedDetail);`);
    for(const id of ['controller-events','timeline']) {
      const more=elements.get(`${id}-disclosure`)?.querySelector('button');
      while(more && !more.disabled) more.handlers.click();
    }
  };
  el('report-select').value = 'changes.diff';
  el('log-select').value = 'verify.stderr.log';
  el('actor-log-select').value = 'prompt.txt';
  show('development');
  assert.equal(el('run-state').textContent, 'completed');
  assert.equal(el('actor-list').children.length, 10);
  assert.match(el('actor-list').textContent, /0\.9.*actor-9/);
  assert.match(el('actor-list').textContent, /activation.ready.*activation.running.*activation.retired/);
  assert.match(el('actor-list').textContent, /fixture:activation-9/);
  assert.match(el('artifact-standing').textContent, /Current accepted/);
   assert.equal(el('cancel-pattern').hidden, false);
   assert.equal(el('cancel-pattern').textContent, 'Clean up processes');
   assert.match(el('cancel-note').textContent, /zombies require parent reaping/);
   fixture.development.application.cleanup_confirmed = true;
   show('development');
   assert.equal(el('cancel-pattern').hidden, true);
   fixture.development.application.cleanup_confirmed = false;
  assert.equal(el('legacy-execution').hidden, true);
  assert.match(el('controller-events').textContent, /qa_review -> remediating \/ fail/);
  assert.match(el('phase-kind').textContent, /DEVELOPMENT/);
  assert.match(el('phase-history').textContent, /QA fail/);
  assert.match(el('phase-outputs').textContent, /Current result/);
  el('start-task').value = 'Unsaved task must survive refresh';
  el('compare-left').value = 'artifact-8';
  el('compare-right').value = 'artifact-10';
  run('renderComparison(); switchPage("new"); persistUI()');
  show('development');
  assert.equal(el('new-page').hidden, false);
  assert.equal(el('start-task').value, 'Unsaved task must survive refresh');
  assert.match(el('compare-left-standing').textContent, /Historical/);
  assert.match(el('compare-right-standing').textContent, /Current accepted/);
  const persisted = JSON.parse(storage.get('noetic-workspace-v1'));
  assert.equal(persisted.page, 'new');
  assert.equal(persisted.forms['start-task'], 'Unsaved task must survive refresh');
  assert.equal(persisted.runs[fixture.development.status.run_id]['compare-right'], 'artifact-10');
  assert.equal(requests.filter(r => r.options?.method === 'POST').length, 0, 'Background rendering does not infer or mutate');
  run('switchPage("workspace")');
  run('renderRuns(fixture.runs)');
  const completed = el('run-list').children.find(row=>row.dataset.runId===fixture.development.status.run_id);
  assert.ok(completed, 'Exact original run remains reachable in the list');
  assert.match(completed.textContent, /completed/);
  assert.match(completed.textContent, /implementation/);
  assert.match(completed.textContent, /Original namespace · unassigned/);
  assert.match(el('controller-generation').textContent, /Generation 1/);
  run('switchView("controller")');
  el('actor-select').value = 'activation-0';
  el('artifact-select').value = 'artifact-2';
  show('returned');
  assert.match(el('artifact-standing').textContent, /Historical/);
  assert.match(el('controller-budgets').textContent, /returns: 1 of 1/);
  el('artifact-select').value = 'artifact-3';
  run('renderArtifact()');
  assert.match(el('artifact-standing').textContent, /Partial/);
  assert.match(el('artifact-content').textContent, /Partial fixture hypothesis/);
  const raw = el('controller-events').querySelectorAll('details')[0];
  raw.open = true;
  show('cognitive');
  assert.equal(el('actor-select').value, 'activation-0');
  assert.equal(el('artifact-select').value, 'artifact-3');
  assert.equal(el('actor-log-select').value, 'prompt.txt');
  assert.equal(el('report-select').value, 'changes.diff');
  assert.equal(el('log-select').value, 'verify.stderr.log');
  assert.equal(el('controller-view').hidden, false);
  assert.equal(el('controller-events').querySelectorAll('details')[0].open, true);
  assert.equal(el('actor-list').children.length, 6);
  assert.match(el('state-note').textContent, /not development phases.*does not mean generic QA acceptance/);
  assert.match(el('controller-events').textContent, /cognition.returned.*invalidated/);
  assert.match(el('timeline').textContent, /P2: operating -> pending \/ return/);
  assert.match(el('controller-phases').textContent, /P1 \/ attentiveness/);
  el('phase-select').value = 'P2';
  run('renderPhase()');
  assert.match(el('phase-history').textContent, /Return P2 -> P1/);
  assert.match(el('phase-history').textContent, /What is the measured value/);
  run('switchView("session")');
  const beforeClose = requests.length;
  run('switchView("phases")');
  assert.equal(requests.length, beforeClose, 'Leaving transcript inspection never stops work');
  assert.equal(el('phases-view').hidden, false);
  el('artifact-select').value = fixture.cognitive.controller.slots['effective.P1'];
  run('renderArtifact()');
  assert.match(el('artifact-standing').textContent, /Current effective/);
  show('active');
  assert.equal(el('cancel-pattern').hidden, false);
  assert.match(el('controller-actor').textContent, /actor-0 \/ Original actor 0\.0 \/ activation-0/);
  const before = requests.length;
  await el('cancel-pattern').handlers.click();
  assert.equal(requests.length, before, 'Declined confirmation must not request cancellation');
  sandbox.window.confirm = () => true;
  const cancellation = el('cancel-pattern').handlers.click();
  const request = requests.at(-1);
  assert.equal(request.url, `/api/runs/${fixture.active.status.run_id}/cancel`);
  assert.equal(request.options.method, 'POST');
  assert.equal(request.options.headers['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(request.options.body), {confirm: true, scope:'application'});
  assert.match(el('cancel-note').textContent, /terminal state is not yet known/);
  fixture.active.cancel_requested = true;
  show('active');
  assert.equal(el('run-state').textContent, 'active');
  assert.match(el('cancel-note').textContent, /still active/);
   assert.equal(el('cancel-pattern').disabled, true);
   show('development');
   const cleanup = el('cancel-pattern').handlers.click();
   assert.equal(requests.at(-1).url, `/api/runs/${fixture.development.status.run_id}/cancel`);
   assert.match(el('cancel-note').textContent, /terminal outcome is unchanged/);
  show('legacy');
  assert.equal(el('controller-summary').hidden, false);
  assert.equal(el('primary-progress').textContent, 'work: pending · verify: pending · review: pending');
  assert.equal(el('primary-agent').textContent, 'Worker');
  for (const id of ['advance-one','advance-all','pause-pattern','cancel-pattern','controller-tab','phases-tab','compare-tab']) {
    assert.equal(el(id).hidden, true, `Legacy history has no controller control ${id}`);
  }
  assert.equal(el('controller-view').hidden, true);
  assert.equal(el('legacy-execution').hidden, false);
  assert.equal(el('run-state').textContent, 'unfinished');
}).on('error', error => { throw error; });
"""


if __name__ == "__main__":
    unittest.main()
