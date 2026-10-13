"""Bounded, model-free implementation checks for local operator pairing."""

from contextlib import closing, ExitStack, redirect_stderr, redirect_stdout
import http.client
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from scripts import noetic_access as access
from scripts import noetic_controller as controller
from scripts import noetic_run as runtime
from scripts import noetic_web as web


class OperatorAccessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runs = self.root / "runs"
        self.server = web.create_server(self.runs, port=0)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, path, method="GET", token=None, headers=None, body=None):
        headers = dict(headers or {})
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        with closing(http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)) as client:
            client.request(method, path, body=body, headers=headers)
            response = client.getresponse()
            return response.status, dict(response.getheaders()), response.read()

    def test_all_private_routes_guard_before_processing_including_head_and_unknown(self):
        reads = ["/api", "/api/runs", "/api/runs/private", "/api/runs/private/activations/a/logs/prompt.txt",
                 "/api/runs/private/activations/a/transcript", "/api/search?q=private&limit=bad",
                 "/api/configuration", "/api/diagnostics", "/api/goals", "/api/goals/private", "/api/unknown",
                 "/%61pi/runs"]
        actions = ["/api/application/start", "/api/goals", "/api/memory/semantic", "/api/diagnostics/refresh",
                   *[f"/api/runs/private/{name}" for name in ("advance", "pause", "cancel", "summary")], "/api/unknown"]
        with ExitStack() as stack:
            mocks = [stack.enter_context(patch.object(web, name)) for name in
                     ("run_summaries", "run_detail", "actor_log", "search_runs", "run_path")]
            mocks += [stack.enter_context(patch.object(self.server.application, name)) for name in
                      ("configuration", "diagnostics", "goals", "start", "create_goal", "memory", "summary", "advance")]
            for token in (None, "wrong-token", "non-ascii-\u00e9"):
                for method, routes in (("GET", reads), ("HEAD", reads), ("POST", actions),
                                       ("PUT", ["/api/unknown"]), ("OPTIONS", ["/api/runs"]), ("UNLISTED", ["/api/new"])):
                    for route in routes:
                        with self.subTest(token=bool(token), method=method, route=route):
                            code, headers, body = self.request(route, method, token, body="invalid JSON")
                            self.assertEqual(code, 401)
                            self.assertEqual(headers["Cache-Control"], "no-store")
                            self.assertNotIn("Access-Control-Allow-Origin", headers)
                            self.assertEqual(body, b"" if method == "HEAD" else b'{"error": "Local operator pairing required."}')
            for mock in mocks:
                mock.assert_not_called()
        self.assertFalse(self.runs.exists())

    def test_paired_history_and_action_and_retained_origin_json_checks(self):
        run = runtime.create_run({"goal": "synthetic confidential prompt"}, self.root, self.runs)
        controller.start_run(run / "controller.sqlite3", controller.PATTERN_DIR / "cognition.json",
                             "synthetic confidential prompt", self.root)
        route = f"/api/runs/{run.name}?scope=application"
        self.assertEqual(self.request(route)[0], 401)
        code, _, body = self.request(route, token=self.server.token)
        self.assertEqual(code, 200)
        self.assertIn(b"synthetic confidential prompt", body)
        self.assertNotIn(self.server.token.encode(), body)
        self.assertEqual(self.request(route, "HEAD", self.server.token)[::2], (200, b""))
        action = f"/api/runs/{run.name}/pause"
        headers = {"Content-Type": "application/json"}
        self.assertEqual(self.request(action, "POST", headers=headers, body="{}")[0], 401)
        self.assertFalse((run / "pause.requested").exists())
        self.assertEqual(self.request(action, "POST", self.server.token, {**headers, "Origin": "http://other.invalid"}, "{}")[0], 403)
        self.assertEqual(self.request(action, "POST", self.server.token, body="{}")[0], 415)
        self.assertFalse((run / "pause.requested").exists())
        self.assertEqual(self.request(action, "POST", self.server.token,
                                      {**headers, "Origin": f"http://127.0.0.1:{self.server.server_port}"}, '{"scope":"application"}')[0], 202)
        self.assertTrue((run / "pause.requested").exists())
        self.assertEqual(self.request("/api/unknown", token=self.server.token)[0], 404)

    def test_public_shell_no_secret_paths_or_request_logging(self):
        output = io.StringIO()
        with redirect_stderr(output):
            for path in ("/", "/index.html", "/app.js", "/style.css"):
                code, _, body = self.request(path)
                self.assertEqual(code, 200)
                self.assertNotIn(self.server.token.encode(), body)
                self.assertNotIn(str(self.root).encode(), body)
            code, _, body = self.request("/api/unknown?token=" + self.server.token)
            self.assertEqual(code, 401)
            self.assertNotIn(self.server.token.encode(), body)
            self.request("/api/runs", token=self.server.token)
        self.assertNotIn(self.server.token, output.getvalue())
        self.assertIn(f"/#token={self.server.token}", self.server.pairing_url)
        self.assertFalse(self.runs.exists())
        with web.create_server(self.runs, port=0) as other:
            self.assertNotEqual(other.token, self.server.token)
        with web.create_server(self.runs, port=0, access_token=self.server.token) as other:
            self.assertEqual(other.token, self.server.token)
        with self.assertRaises(ValueError):
            web.create_server(self.runs, port=0, access_token="")


class TokenFileTests(unittest.TestCase):
    def test_permissions_reuse_and_explicit_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for mask in (0o022, 0o002):
                path = root / str(mask) / "private" / "token"
                previous = os.umask(mask)
                try:
                    token = access.load_token(path)
                finally:
                    os.umask(previous)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE(path.parent.parent.stat().st_mode), 0o700)
                self.assertEqual(access.load_token(path), token)
                path.chmod(0o644)
                with self.assertRaisesRegex(ValueError, "explicitly chmod 600"):
                    access.load_token(path)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
                path.chmod(0o600)
                self.assertEqual(access.load_token(path), token)
                link = path.with_name("link")
                link.symlink_to(path)
                with self.assertRaisesRegex(ValueError, "not a symlink"):
                    access.load_token(link)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)

    def test_cli_default_and_selected_file_reuse_without_real_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for selected in (None, root / "selected" / "token"):
                argv = ["--runs-dir", str(root / "state" / "runs"), "--port", "0"]
                if selected:
                    argv += ["--token-file", str(selected)]
                token_file = selected or root / "state" / ".operator-access" / "token"
                tokens = []
                for _ in range(2):
                    output = io.StringIO()
                    with patch.object(web.ThreadingHTTPServer, "serve_forever", side_effect=KeyboardInterrupt), redirect_stdout(output):
                        self.assertEqual(web.main(argv), 0)
                    tokens.append(access.load_token(token_file))
                    self.assertIn("/#token=" + tokens[-1], output.getvalue())
                self.assertEqual(*tokens)
                self.assertFalse((root / "state" / "runs").exists())

    @unittest.skipUnless(shutil.which("node"), "Node is needed for the executable pairing contract")
    def test_ui_pairing_fragment_headers_lock_logout_and_auth_failure(self):
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
  const token = 'synthetic-pairing-token-with-32-characters';
  assert.match(fixture.html, /<input\b(?=[^>]*\bid="access-token")(?=[^>]*\btype="password")[^>]*>/);
  assert.match(fixture.html, /local operator token, not provider credential/);
  assert.match(fixture.html, /<div\b(?=[^>]*\bid="private-workspace")(?=[^>]*\bhidden(?:=|\s|>))[^>]*>/);
  function launch(hash = '', stored = new Map(), legacy = new Map()) {
    const elements = new Map();
    function element(tagName = 'div') { return {
      tagName, hidden:true, children:[], handlers:{}, dataset:{}, attributes:{}, style:{}, scrollTop:0,
      get value() { return this._value ?? this.children[0]?.value ?? ''; }, set value(value) { this._value=value; },
      get firstChild() { return this.children[0] || null; },
      get selectedOptions() { return this.children.filter(child => child.value === this.value); },
      append(...items) { this.children.push(...items); },
      addEventListener(k, fn) { this.handlers[k] = fn; },
      replaceChildren(...items) { this.children=items; if(this.tagName==='select') delete this._value; },
      querySelectorAll() { return []; },
      querySelector(selector) { const value=selector.match(/^\[value="([^"]+)"\]$/)?.[1]; return this.children.find(child=>child.value===value) || null; },
      setAttribute(k,v) { this.attributes[k]=String(v); }, getAttribute(k) { return this.attributes[k] ?? null; },
      classList:{remove(){},toggle(){return true;}}, focus(){}, scrollIntoView(){}
    }; }
    for (const match of fixture.html.matchAll(/<([a-z0-9-]+)\b[^>]*\bid="([^"]+)"[^>]*>/g)) elements.set(match[2], element(match[1]));
    for (const match of fixture.html.matchAll(/<select\b[^>]*id="([^"]+)"[^>]*>([\s\S]*?)<\/select>/g)) {
      const select=elements.get(match[1]);
      for(const option of match[2].matchAll(/<option\b[^>]*value="([^"]*)"[^>]*>/g)) { const child=element('option'); child.value=option[1]; select.append(child); }
    }
    let reloads = 0;
    const requests = [], replaced = [], handlers = {}, legacyAccess = [];
    const sandbox = {URL, URLSearchParams, AbortController, console, CustomEvent: class { constructor(type,options) { this.type=type; Object.assign(this,options); } }, queueMicrotask, setTimeout: () => 1, clearTimeout() {}, setInterval() {},
      window: {confirm: () => true, addEventListener(name, handler) { handlers[name] = handler; }},
      location: {hash, pathname: '/', search: '', origin:'http://127.0.0.1:8765', reload() { reloads++; }},
      history: {replaceState(...args) { replaced.push(args); sandbox.location.hash = ''; }},
      localStorage: {
        getItem(key) { legacyAccess.push('read'); return legacy.get(key) ?? null; },
        removeItem(key) { legacyAccess.push('remove'); legacy.delete(key); },
        setItem() { assert.fail('No localStorage writes'); }
      },
      sessionStorage: {getItem: k => stored.get(k), setItem: (k,v) => stored.set(k,v), removeItem: k => stored.delete(k)},
      document: {getElementById: k => elements.get(k), createElement: element, dispatchEvent:()=>true, querySelectorAll: () => []},
      fetch: (url, options) => { requests.push({url, options}); return new Promise(() => {}); }};
    vm.createContext(sandbox);
    vm.runInContext(fixture.script, sandbox);
    return {sandbox, stored, legacy, legacyAccess, elements, requests, replaced, run: s => vm.runInContext(s, sandbox), reloads: () => reloads,
      navigate(hash) { sandbox.location.hash = hash; handlers.hashchange(); }};
  }
  const locked = launch();
  assert.equal(locked.requests.length, 0);
  assert.equal(locked.elements.get('private-workspace').hidden, true);
  locked.navigate('#run-detail');
  assert.equal(locked.requests.length, 0, 'Ordinary view fragments do not pair');
  let finishPairing;
  locked.sandbox.fetch = (url, options) => {
    locked.requests.push({url, options});
    return new Promise(resolve => { finishPairing = resolve; });
  };
  locked.navigate('#token=' + token);
  assert.equal(locked.sandbox.location.hash, '', 'Same-document secret is removed synchronously');
  assert.equal(locked.requests[0].options.headers.Authorization, 'Bearer ' + token);
  assert.equal(locked.elements.get('private-workspace').hidden, true);
  finishPairing({status:200, ok:true, json:async () => ({runs:[]})});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(locked.elements.get('private-workspace').hidden, false);
  assert.equal(locked.stored.get('noetic-operator-token'), token);
  locked.elements.get('private-workspace').children = ['Old private view'];
  locked.elements.get('start-task').value = 'Retained draft';
  const replacement = token + '-replacement';
  let finishOld;
  locked.sandbox.fetch = () => new Promise(resolve => { finishOld = resolve; });
  const oldRequest = locked.run('fetchJSON("/api/runs")');
  locked.navigate('#token=' + replacement);
  assert.equal(locked.sandbox.location.hash, '');
  assert.equal(locked.elements.get('private-workspace').hidden, true);
  assert.equal(locked.elements.get('private-workspace').children.length, 0);
  assert.equal(locked.reloads(), 1);
  assert.equal(locked.stored.get('noetic-operator-token'), replacement);
  finishOld({status:200, ok:true, json:async () => ({private:'old evidence'})});
  await assert.rejects(oldRequest, /locked/);
  const reopened = launch('', locked.stored);
  assert.equal(reopened.requests[0].options.headers.Authorization, 'Bearer ' + replacement);
  assert.equal(reopened.elements.get('start-task').value, 'Retained draft');
  assert.equal(reopened.elements.get('private-workspace').hidden, true);
  // Replacement while the old pairing itself is in flight must not unlock old DOM.
  const racing = launch();
  let finishOldPairing;
  racing.sandbox.fetch = () => new Promise(resolve => { finishOldPairing = resolve; });
  racing.navigate('#token=' + token);
  racing.navigate('#token=' + replacement);
  finishOldPairing({status:200, ok:true, json:async () => ({runs:[]})});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(racing.elements.get('private-workspace').hidden, true);
  assert.equal(racing.stored.get('noetic-operator-token'), replacement);
  const paired = launch('#token=' + token);
  assert.equal(paired.sandbox.location.hash, '');
  assert.equal(paired.replaced[0][2], '/');
  assert.equal(paired.stored.get('noetic-operator-token'), token);
  assert.equal(paired.requests[0].options.headers.Authorization, 'Bearer ' + token);
  paired.run('fetchJSON("/api/goals", {method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"})');
  assert.equal(paired.requests.at(-1).options.headers.Authorization, 'Bearer ' + token);
  assert.equal(paired.requests.at(-1).options.headers['Content-Type'], 'application/json');
  assert.ok(paired.requests.every(r => !r.url.includes(token)));
  paired.elements.get('start-task').value = 'Private draft';
  paired.elements.get('private-workspace').children = ['Private history'];
  paired.elements.get('access-lock').handlers.click();
  assert.equal(paired.reloads(), 1);
  assert.equal(paired.elements.get('private-workspace').hidden, true);
  assert.equal(paired.elements.get('private-workspace').children.length, 0);
  assert.equal(paired.stored.has('noetic-operator-token'), false);
  assert.equal(JSON.parse(paired.stored.get('noetic-workspace-v1')).forms['start-task'], 'Private draft');
  const resumed = launch('', paired.stored);
  assert.equal(resumed.requests.length, 0);
  assert.equal(resumed.elements.get('start-task').value, 'Private draft');
  resumed.elements.get('access-token').value = token;
  resumed.elements.get('access-form').handlers.submit({preventDefault() {}});
  assert.equal(resumed.elements.get('access-token').value, '');
  assert.equal(resumed.requests[0].options.headers.Authorization, 'Bearer ' + token);
  resumed.elements.get('access-logout').handlers.click();
  assert.equal(resumed.stored.size, 0);
  const success = launch('#token=' + token);
  success.sandbox.fetch = (url, options) => {
    success.requests.push({url, options});
    return success.requests.length === 2
      ? Promise.resolve({status:200, ok:true, json:async () => ({runs:[]})}) : new Promise(() => {});
  };
  await success.run('unlockAccess()');
  assert.equal(success.elements.get('private-workspace').hidden, false);
  assert.equal(success.elements.get('access-form').hidden, true);
  assert.equal(success.elements.get('access-lock').hidden, false);
  assert.ok(success.requests.every(r => r.options.headers.Authorization === 'Bearer ' + token));
  const failed = launch('#token=' + token);
  failed.sandbox.fetch = async () => ({status:401});
  await assert.rejects(failed.run('fetchJSON("/api/runs")'), /pairing required/);
  assert.equal(failed.reloads(), 1);
  assert.equal(failed.elements.get('private-workspace').hidden, true);
  assert.equal(failed.stored.has('noetic-operator-token'), false);
  const stale = launch('#token=' + token);
  let resolve;
  stale.sandbox.fetch = () => new Promise(r => {resolve = r;});
  const pending = stale.run('fetchJSON("/api/runs")');
  stale.run('lockAccess()');
  resolve({status:200, ok:true, json:async () => ({private:'cached evidence'})});
  await assert.rejects(pending, /locked/);

  const draftKey = 'noetic-workspace-v1';
  const privateDraft = 'SYNTHETIC UNSENT PREVIOUS DRAFT';
  const legacyState = {selectedId:'previous-run', page:'new', forms:{'start-task':privateDraft,
    'start-workspace':'/synthetic/previous', 'access-token':'must-not-import'}, positions:{new:120},
    runs:{'previous-run':{view:'reports', 'report-select':'work.md', payload:'must-not-import'}},
    token:'must-not-import', privatePayload:'must-not-import'};
  const raw = JSON.stringify(legacyState);
  async function pair(app) {
    let first = true;
    app.sandbox.fetch = (url, options) => {
      app.requests.push({url, options});
      if (!first) return new Promise(() => {});
      first = false;
      return Promise.resolve({status:200, ok:true, json:async () => ({runs:[]})});
    };
    app.elements.get('access-token').value = token;
    app.elements.get('access-form').handlers.submit({preventDefault() {}});
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(app.elements.get('private-workspace').hidden, false);
  }
  const upgrade = launch('', new Map(), new Map([[draftKey, raw]]));
  assert.equal(upgrade.legacyAccess.length, 0, 'Unpaired startup never reads/deletes legacy drafts');
  assert.equal(upgrade.legacy.get(draftKey), raw);
  assert.equal(upgrade.elements.get('previous-drafts').hidden, true);
  assert.equal(upgrade.elements.get('start-task').value, '');
  upgrade.elements.get('import-previous-drafts').handlers.click();
  upgrade.elements.get('forget-previous-drafts').handlers.click();
  assert.equal(upgrade.legacyAccess.length, 0, 'Migration actions require successful pairing');
  await pair(upgrade);
  assert.equal(upgrade.elements.get('previous-drafts').hidden, false);
  assert.equal(upgrade.elements.get('start-task').value, '', 'Pairing does not import automatically');
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
    assert.equal(upgrade.stored.get('noetic-operator-token'), token, 'Pairing retained before legacy removal');
    assert.deepEqual(JSON.parse(upgrade.stored.get(draftKey)), expected, 'Allowed state saved before legacy removal');
    upgrade.legacy.delete(key);
  };
  upgrade.elements.get('import-previous-drafts').handlers.click();
  assert.equal(upgrade.legacy.has(draftKey), false);
  assert.equal(upgrade.reloads(), 1);
  assert.equal(upgrade.elements.get('private-workspace').hidden, true);
  const imported = launch('', upgrade.stored, upgrade.legacy);
  assert.equal(imported.elements.get('start-task').value, privateDraft);
  assert.equal(imported.run('currentPage'), 'new');
  assert.equal(imported.run('selectedId'), 'previous-run');
  assert.equal(imported.requests[0].options.headers.Authorization, 'Bearer ' + token);
  assert.equal(imported.elements.get('private-workspace').hidden, true);

  for (const bad of ['{broken:' + privateDraft, 'null', '[]', JSON.stringify({forms:{'start-task':42}})]) {
    const malformed = launch('', new Map(), new Map([[draftKey, bad]]));
    await pair(malformed);
    malformed.elements.get('import-previous-drafts').handlers.click();
    assert.equal(malformed.legacy.get(draftKey), bad);
    assert.equal(malformed.reloads(), 0);
    assert.match(malformed.elements.get('previous-drafts-status').textContent, /original entry has not been removed/);
    assert.ok(!malformed.elements.get('previous-drafts-status').textContent.includes(privateDraft));
  }
  for (const mode of ['write-failure', 'readback-mismatch', 'token-write-failure', 'local-read-failure', 'remove-failure', 'changed-entry']) {
    const unavailable = launch('', new Map(), new Map([[draftKey, raw]]));
    await pair(unavailable);
    if (mode === 'write-failure') unavailable.sandbox.sessionStorage.setItem = () => {throw new Error(privateDraft);};
    if (mode === 'readback-mismatch') unavailable.sandbox.sessionStorage.getItem = () => null;
    if (mode === 'token-write-failure') {
      unavailable.sandbox.sessionStorage.setItem = (key, value) => {
        if (key === 'noetic-operator-token') throw new Error(privateDraft);
        unavailable.stored.set(key, value);
      };
    }
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
  const blocked = launch('', new Map(), new Map([[draftKey, raw]]));
  blocked.sandbox.localStorage.getItem = () => {throw new Error(privateDraft);};
  await pair(blocked);
  assert.equal(blocked.legacy.get(draftKey), raw);
  assert.equal(blocked.elements.get('import-previous-drafts').disabled, true);
  assert.ok(!blocked.elements.get('previous-drafts-status').textContent.includes(privateDraft));
  for (const action of ['access-lock', 'access-logout', 'forget-previous-drafts']) {
    const leaving = launch('', new Map(), new Map([[draftKey, raw]]));
    await pair(leaving);
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
