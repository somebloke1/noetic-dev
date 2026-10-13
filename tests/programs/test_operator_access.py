"""Local HTTP/bootstrap checks, temporary stores and mocked native/browser effects."""
from contextlib import closing, redirect_stdout, redirect_stderr
import http.client
import io
import json
import os
import shutil
import subprocess
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from scripts import noetic, noetic_web as web, noetic_run as runtime, noetic_controller as controller


class NoAuthBackend(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="noauth1-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.runs = self.root / "runs"
        self.server = web.create_server(self.runs, port=0)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, route, method="GET", body=None, headers=None):
        with closing(http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)) as conn:
            conn.request(method, route, body=body, headers=headers or {})
            response = conn.getresponse()
            self.assertEqual(response.getheader("Cache-Control"), "no-store")
            self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))
            return response.status, response.read()

    def inventory(self):
        return {str(p.relative_to(self.root)): (p.stat().st_mode, p.stat().st_mtime_ns,
                p.read_bytes() if p.is_file() else None) for p in self.root.rglob("*")}

    def test_plain_and_stale_header_get_head(self):
        for headers in ({}, {"Authorization": "Bearer stale-synthetic-header"}, {"Authorization": "unrelated"}):
            for method in ("GET", "HEAD"):
                for route, expected in (("/", 200), ("/api/runs?scope=application", 200),
                                        ("/api/unknown", 404), ("/api/usage", 400), ("/api/access", 404)):
                    with self.subTest(method=method, route=route, headers=bool(headers)):
                        status, body = self.request(route, method, headers=headers)
                        self.assertEqual(status, expected, body)
                        if method == "HEAD":
                            self.assertEqual(body, b"")
        self.assertFalse(self.runs.exists())

    def test_history_and_explicit_pause_without_token(self):
        run = runtime.create_run({"goal": "synthetic retained history"}, self.root, self.runs)
        controller.start_run(run / "controller.sqlite3", controller.PATTERN_DIR / "cognition.json",
                             "synthetic retained history", self.root)
        route = f"/api/runs/{run.name}?scope=application"
        status, body = self.request(route)
        self.assertEqual(status, 200, body)
        self.assertIn(b"synthetic retained history", body)
        status, body = self.request(f"/api/runs/{run.name}/pause", "POST",
                                    '{"scope":"application"}', {"Content-Type": "application/json"})
        self.assertEqual(status, 202, body)
        self.assertTrue((run / "pause.requested").is_file())

    def test_malformed_size_content_origin_refusal(self):
        with patch.object(self.server.application, "start") as start:
            for body, headers, expected in (
                ("{}", {}, 415), ("{", {"Content-Type": "application/json"}, 400),
                ("[]", {"Content-Type": "application/json"}, 400),
                ("{}", {"Content-Type": "application/json", "Origin": "http://foreign.invalid"}, 403),
                ("{}", {"Content-Type": "application/json", "Content-Length": "65537"}, 400),
            ):
                status, result = self.request("/api/application/start", "POST", body, headers)
                self.assertEqual(status, expected, result)
            start.assert_not_called()
        self.assertFalse(self.runs.exists())

    def test_invalid_attachment_refusal(self):
        with patch.object(self.server.developer_sessions, "_launch") as launch:
            status, result = self.request("/api/developer-sessions", "POST",
                '{"effort_root":"0.0","prompt":"not sent","attachments":null}',
                {"Content-Type": "application/json"})
            self.assertEqual(status, 400, result)
            launch.assert_not_called()
        self.assertFalse(self.runs.exists())

    def test_foreign_reserved_native_context_refusal(self):
        service = self.server.developer_sessions
        reserved = service.registry.create(self.root, "reserved", "fixture/model", "low", ["never-run"],
                                           ordinal="0.0", effort_root="0.0")
        before = self.inventory()
        with patch.object(service, "deliver") as deliver, patch.object(service, "_launch") as launch:
            status, body = self.request(f"/api/developer-sessions/{reserved['id']}/prompt", "POST",
                '{"effort_root":"0.1","message":"must not deliver"}', {"Content-Type": "application/json"})
            self.assertEqual(status, 400, body)
            self.assertIn(b"does not own", body)
            deliver.assert_not_called()
            launch.assert_not_called()
        self.assertEqual(self.inventory(), before)

    def test_serve_has_no_token_or_file_side_effect(self):
        before = self.inventory()
        stdout = io.StringIO()
        with patch.object(web.ThreadingHTTPServer, "serve_forever", side_effect=KeyboardInterrupt), redirect_stdout(stdout):
            self.assertEqual(web.main(["--runs-dir", str(self.runs), "--port", "0"]), 0)
        self.assertIn("http://127.0.0.1:", stdout.getvalue())
        self.assertNotIn("#token=", stdout.getvalue())
        self.assertNotIn("pairing", stdout.getvalue().lower())
        self.assertNotIn("access", web.__dict__)
        self.assertFalse(hasattr(self.server, "token"))
        self.assertEqual(self.inventory(), before)

    def test_open_plain_static_probe_and_no_file_side_effect(self):
        before = self.inventory()
        with patch.object(web, "run_summaries", side_effect=AssertionError("No run-list readiness")), \
                patch.object(web.subprocess, "run") as browser, redirect_stdout(io.StringIO()):
            self.assertEqual(web.main(["open", "--runs-dir", str(self.runs), "--port", str(self.server.server_port)]), 0)
        args, options = browser.call_args
        self.assertEqual(args[0][-1], f"http://127.0.0.1:{self.server.server_port}/")
        self.assertEqual(options["stdin"], web.subprocess.DEVNULL)
        self.assertEqual(options["stdout"], web.subprocess.DEVNULL)
        self.assertEqual(self.inventory(), before)

    def test_port_and_environment_selector_routing(self):
        before = self.inventory()
        with patch.dict(os.environ, {"NOETIC_STATE_HOME": str(self.root / "bound state")}):
            with patch.object(web, "open_workspace") as handoff:
                self.assertEqual(noetic.main(["open", "--port", "9876"]), 0)
                handoff.assert_called_once_with(9876)
        for port in ("0", "-1", "65536", "not-a-port"):
            with patch.object(web, "open_workspace") as handoff, redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    web.main(["open", "--port", port])
                self.assertEqual(result.exception.code, 2)
                handoff.assert_not_called()
        self.assertEqual(self.inventory(), before)

    def test_obsolete_token_file_cli_refusal(self):
        before = self.inventory()
        with patch.object(web.ThreadingHTTPServer, "serve_forever", side_effect=KeyboardInterrupt), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
            web.main(["--token-file", str(self.root / "not-read"), "--port", "0"])
        self.assertEqual(result.exception.code, 2)
        self.assertEqual(self.inventory(), before)


class OperatorWorkspaceUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node is needed for the executable workspace contract")
    def test_plain_bootstrap_requests_and_retained_draft_ownership(self):
        payload = {"script": (web.WEB_DIR / "app.js").read_text(), "html": (web.WEB_DIR / "index.html").read_text()}
        result = subprocess.run(["node", "-e", UI_CONTRACT], input=json.dumps(payload), text=True,
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


UI_CONTRACT = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
let input = '';
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', async () => {
  const fixture = JSON.parse(input);
  const token = 'synthetic-obsolete-value-never-needed';
  assert.doesNotMatch(fixture.html, /id="access-(?:token|form|lock|logout)"/);
  assert.doesNotMatch(fixture.html, /<div\b(?=[^>]*\bid="private-workspace")(?=[^>]*\bhidden(?:=|\s|>))[^>]*>/);
  function launch(hash = '', stored = new Map(), legacy = new Map(), failLegacyRead = false) {
    const elements = new Map();
    function element(tagName = 'div') { return {
      tagName:tagName.toUpperCase(), defaultValue:'', hidden:false, children:[], handlers:{}, dataset:{}, attributes:{}, style:{}, scrollTop:0,
      get value() { return this._value ?? this.children[0]?.value ?? ''; }, set value(value) { this._value=value; },
      get firstChild() { return this.children[0] || null; },
      get lastChild() { return this.children.at(-1) || null; },
      get options() { return this.children; },
      get selectedOptions() { return this.children.filter(child => child.value === this.value); },
      append(...items) { for (const item of items) { item.parentElement=this; this.children.push(item); if(item.id) elements.set(item.id,item); } },
      closest(selector) { for(let current=this;current;current=current.parentElement) if(selector==="[data-settings-panel='purpose']" && current.dataset.settingsPanel==='purpose') return current; return null; },
      addEventListener(k, fn) { this.handlers[k] = fn; },
      replaceChildren(...items) { this.children=items; if(this.tagName==='SELECT') delete this._value; },
      querySelectorAll() { return []; },
      querySelector(selector) { const value=selector.match(/^\[value="([^"]+)"\]$/)?.[1]; return this.children.find(child=>value!==undefined ? child.value===value : child.tagName===selector.toUpperCase()) || null; },
      setAttribute(k,v) { this.attributes[k]=String(v); }, getAttribute(k) { return this.attributes[k] ?? null; },
      classList:{remove(){},toggle(){return true;}}, focus(){}, scrollIntoView(){}
    }; }
    for (const match of fixture.html.matchAll(/<([a-z0-9-]+)\b[^>]*\bid="([^"]+)"[^>]*>/g)) { const item=element(match[1]); item.hidden=/\shidden(?:=|\s|>)/.test(match[0]); elements.set(match[2],item); }
    const sourceLabel = /<label\b[^>]*\bfor="start-sources"[^>]*>/.test(fixture.html) ? element('label') : null;
    assert.match(fixture.html, /<div\b[^>]*data-settings-panel="purpose"[^>]*>[\s\S]*?<select\b[^>]*id="start-purpose"/);
    const purposePanel=element('div'); purposePanel.dataset.settingsPanel='purpose'; purposePanel.append(elements.get('start-purpose'));
    for (const match of fixture.html.matchAll(/<select\b[^>]*id="([^"]+)"[^>]*>([\s\S]*?)<\/select>/g)) {
      const select=elements.get(match[1]);
      for(const option of match[2].matchAll(/<option\b[^>]*value="([^"]*)"[^>]*>/g)) { const child=element('option'); child.value=option[1]; select.append(child); }
    }
    let reloads = 0;
    const requests = [], replaced = [], handlers = {}, legacyAccess = [], sessionReads = [], sessionWrites = [];
    const sandbox = {URL, URLSearchParams, AbortController, structuredClone, console, CustomEvent: class { constructor(type,options) { this.type=type; Object.assign(this,options); } }, queueMicrotask, setTimeout: () => 1, clearTimeout() {}, setInterval() {},
      window: {confirm: () => true, addEventListener(name, handler) { handlers[name] = handler; }},
      location: {hash, pathname: '/', search: '', origin:'http://127.0.0.1:8765', reload() { reloads++; }},
      history: {replaceState(...args) { replaced.push(args); sandbox.location.hash = ''; }},
      localStorage: {
        getItem(key) { legacyAccess.push('read'); if (failLegacyRead) throw new Error('Unavailable previous-draft storage'); return legacy.get(key) ?? null; },
        removeItem(key) { legacyAccess.push('remove'); legacy.delete(key); },
        setItem() { assert.fail('No localStorage writes'); }
      },
      sessionStorage: {getItem(k) { sessionReads.push(k); return stored.get(k); }, setItem(k,v) { sessionWrites.push(k); stored.set(k,v); }, removeItem: k => stored.delete(k)},
      document: {getElementById: k => elements.get(k), createElement: element, dispatchEvent:()=>true,
        querySelector: selector => selector === 'label[for="start-sources"]' ? sourceLabel : null, querySelectorAll: () => []},
      fetch: (url, options) => { requests.push({url, options}); return new Promise(() => {}); }};
    vm.createContext(sandbox);
    vm.runInContext(fixture.script, sandbox);
    return {sandbox, stored, legacy, legacyAccess, sessionReads, sessionWrites, elements, requests, replaced, run: s => vm.runInContext(s, sandbox), reloads: () => reloads,
      navigate(hash) { sandbox.location.hash = hash; handlers.hashchange(); }};
  }
  async function ready(app) {
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(app.elements.get('private-workspace').hidden, false);
    assert.ok(app.requests.every(r => !r.options?.headers?.Authorization));
    assert.ok(app.requests.every(r => r.url !== '/api/access'));
    assert.equal(app.sessionReads.includes('noetic-operator-token'), false);
    assert.equal(app.sessionWrites.includes('noetic-operator-token'), false);
  }
  for (const [hash, stored] of [['', new Map()], ['#token='+token, new Map()], ['', new Map([['noetic-operator-token',token]])], ['#run-detail', new Map()]]) {
    const app = launch(hash, stored);
    await ready(app);
    assert.equal(app.stored.has('noetic-operator-token'), false);
    assert.equal(app.sandbox.location.hash, hash.startsWith('#token=') ? '' : hash);
    assert.equal(app.reloads(), 0);
    assert.equal(app.requests.filter(r => r.options?.method === 'POST').length, 0);
  }
  const available = launch();
  await ready(available);
  available.sandbox.fetch = async (url, options) => {
    available.requests.push({url,options});
    return {status:503,ok:false,json:async()=>({error:'Synthetic execution read unavailable'})};
  };
  await assert.rejects(available.run('fetchJSON("/api/runs?scope=application")'), /Synthetic execution read unavailable/);
  assert.equal(available.elements.get('private-workspace').hidden, false);
  assert.equal(available.reloads(),0);
  available.sandbox.fetch = async (url, options) => {
    available.requests.push({url,options});
    return {status:200,ok:true,json:async()=>({runs:[]})};
  };
  assert.equal((await available.run('fetchJSON("/api/runs?scope=application")')).runs.length,0);
  available.run('fetchJSON("/api/goals",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"})');
  assert.equal(available.requests.at(-1).options.headers['Content-Type'],'application/json');
  assert.ok(available.requests.every(r=>!r.options?.headers?.Authorization));
  const draftKey = 'noetic-workspace-v1';
  const privateDraft = 'SYNTHETIC UNSENT PREVIOUS DRAFT';
  const legacyState = {selectedId:'previous-run', page:'new', forms:{'start-task':privateDraft,
    'start-workspace':'/synthetic/previous', 'access-token':'must-not-import'}, positions:{new:120},
    runs:{'previous-run':{view:'reports', 'report-select':'work.md', payload:'must-not-import'}},
    token:'must-not-import', privatePayload:'must-not-import'};
  const raw = JSON.stringify(legacyState);
  const upgrade = launch('', new Map(), new Map([[draftKey, raw]]));
  assert.ok(!upgrade.legacyAccess.includes('remove'), 'Startup never deletes previous drafts');
  assert.equal(upgrade.legacy.get(draftKey), raw);
  assert.equal(upgrade.elements.get('previous-drafts').hidden, false);
  assert.equal(upgrade.elements.get('start-task').value, '');
  await ready(upgrade);
  assert.equal(upgrade.elements.get('previous-drafts').hidden, false);
  assert.equal(upgrade.elements.get('start-task').value, '', 'Bootstrap does not import automatically');
  assert.equal(upgrade.legacy.get(draftKey), raw);
  assert.ok([...upgrade.elements.values()].every(el => !String(el.textContent).includes(privateDraft)));
  upgrade.sandbox.window.confirm = () => false;
  upgrade.elements.get('import-previous-drafts').handlers.click();
  upgrade.elements.get('forget-previous-drafts').handlers.click();
  assert.equal(upgrade.legacy.get(draftKey), raw);
  upgrade.sandbox.window.confirm = () => true;
  const expected = {selectedId:'previous-run', page:'new', forms:{'start-task':privateDraft,
    'start-workspace':'/synthetic/previous'}, positions:{new:120},
    runs:{'previous-run':{view:'reports', 'report-select':'work.md'}}};
  upgrade.sandbox.localStorage.removeItem = key => {
    assert.equal(upgrade.stored.has('noetic-operator-token'), false, 'No credential is required for explicit migration');
    assert.deepEqual(JSON.parse(upgrade.stored.get(draftKey)), expected, 'Allowed state saved before legacy removal');
    upgrade.legacy.delete(key);
  };
  upgrade.elements.get('import-previous-drafts').handlers.click();
  assert.equal(upgrade.legacy.has(draftKey), false);
  assert.equal(upgrade.reloads(), 1);
  const imported = launch('', upgrade.stored, upgrade.legacy);
  assert.equal(imported.elements.get('start-task').value, '', 'Migration does not assign the prior draft to an effort');
  assert.equal(imported.run('savedUI.unassignedStructuredDraft.fields["start-task"]'), privateDraft);
  assert.equal(imported.run('currentPage'), 'new');
  assert.equal(imported.run('selectedId'), 'previous-run');
  assert.ok(imported.requests.every(r => !r.options?.headers?.Authorization));
  assert.equal(imported.elements.get('private-workspace').hidden, false);

  imported.elements.get('copy-unassigned-draft').handlers.click();
  assert.equal(imported.elements.get('start-task').value, '', 'Copy requires a verified effort owner');
  imported.sandbox.fetch = (url, options) => {
    imported.requests.push({url, options});
    if (url === '/api/disciplines?scope=application&limit=1') {
      return Promise.resolve({status:200, ok:true, json:async () => ({namespace_registered:true, namespace_id:'fixture-namespace'})});
    }
    return new Promise(() => {});
  };
  imported.run('selectedEffort="0.0"; operationMode="effort"');
  await imported.run('window.NoeticDrafts.enter()');
  assert.equal(imported.elements.get('start-task').value, '', 'Owner verification alone does not adopt text');
  assert.equal(imported.elements.get('copy-unassigned-draft').disabled, false);
  imported.elements.get('copy-unassigned-draft').handlers.click();
  assert.equal(imported.elements.get('start-task').value, privateDraft);
  const owned = JSON.parse(imported.stored.get(draftKey));
  assert.deepEqual(owned.structuredDraftOwner, {namespace:'fixture-namespace', effort:'0.0'});
  assert.equal(owned.structuredDrafts[JSON.stringify(['fixture-namespace','0.0'])].fields['start-task'], privateDraft);
  assert.equal(owned.unassignedStructuredDraft.fields['start-task'], privateDraft, 'Original remains available after copying');
  for (const id of ['start-purpose','reviewed-store','reviewed-parent-id','reviewed-warrant-id','reviewed-condition-ids','reviewed-formulation-id']) {
    assert.equal(imported.elements.get(id).value, '', 'Copy does not import qualified binding ' + id);
  }
  imported.elements.get('start-task').value = 'Edited effort draft';
  imported.elements.get('copy-unassigned-draft').handlers.click();
  assert.equal(imported.elements.get('start-task').value, 'Edited effort draft');
  assert.match(imported.elements.get('structured-draft-status').textContent, /Draft conflict/);
  assert.ok(imported.requests.every(r => !r.options?.headers?.Authorization));
  assert.equal(imported.requests.filter(r => r.options?.method === 'POST').length, 0, 'Draft adoption never starts work');

  for (const bad of ['{broken:' + privateDraft, 'null', '[]', JSON.stringify({forms:{'start-task':42}})]) {
    const malformed = launch('', new Map(), new Map([[draftKey, bad]]));
    await ready(malformed);
    malformed.elements.get('import-previous-drafts').handlers.click();
    assert.equal(malformed.legacy.get(draftKey), bad);
    assert.equal(malformed.reloads(), 0);
    assert.match(malformed.elements.get('previous-drafts-status').textContent, /original entry has not been removed/);
    assert.ok(!malformed.elements.get('previous-drafts-status').textContent.includes(privateDraft));
  }
  for (const mode of ['write-failure', 'readback-mismatch', 'local-read-failure', 'remove-failure', 'changed-entry']) {
    const unavailable = launch('', new Map(), new Map([[draftKey, raw]]));
    await ready(unavailable);
    if (mode === 'write-failure') unavailable.sandbox.sessionStorage.setItem = () => {throw new Error(privateDraft);};
    if (mode === 'readback-mismatch') unavailable.sandbox.sessionStorage.getItem = () => null;
    if (mode === 'local-read-failure') unavailable.sandbox.localStorage.getItem = () => {throw new Error(privateDraft);};
    if (mode === 'remove-failure') unavailable.sandbox.localStorage.removeItem = () => {throw new Error(privateDraft);};
    if (mode === 'changed-entry') {
      unavailable.sandbox.sessionStorage.setItem = (key, value) => {
        unavailable.stored.set(key, value);
        unavailable.legacy.set(draftKey, raw + ' ');
      };
    }
    unavailable.elements.get('import-previous-drafts').handlers.click();
    assert.equal(unavailable.legacy.get(draftKey), mode === 'changed-entry' ? raw + ' ' : raw, mode);
    assert.equal(unavailable.reloads(), 0, mode);
    assert.ok(!unavailable.elements.get('previous-drafts-status').textContent.includes(privateDraft));
  }
  const blocked = launch('', new Map(), new Map([[draftKey, raw]]), true);
  await ready(blocked);
  assert.equal(blocked.legacy.get(draftKey), raw);
  assert.equal(blocked.elements.get('import-previous-drafts').disabled, true);
  assert.ok(!blocked.elements.get('previous-drafts-status').textContent.includes(privateDraft));
  for (const action of ['forget-previous-drafts']) {
    const leaving = launch('', new Map(), new Map([[draftKey, raw]]));
    await ready(leaving);
    leaving.elements.get('start-task').value = 'Current tab draft';
    leaving.elements.get(action).handlers.click();
    assert.equal(leaving.legacy.has(draftKey), action !== 'forget-previous-drafts');
    if (action === 'forget-previous-drafts') {
      assert.equal(leaving.elements.get('start-task').value, 'Current tab draft');
      assert.equal(leaving.reloads(), 0);
    }
  }
});
"""
