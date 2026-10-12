// Production HTTP/assets and real detached drivers; every actor is a model-free fixture.
const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');

(async () => {
  const fixture = spawn('python', ['-B', '-u', '-c', `
import json, signal, sys, time
from scripts import noetic_harness as harness, noetic_run as runtime, noetic_web as web
from pathlib import Path
original_server = web.create_server
def fixture_server(root, *args, **kwargs):
    kwargs["namespace_path"] = Path(root) / "ordinals.sqlite3"
    return original_server(root, *args, **kwargs)
web.create_server = fixture_server
from tests.programs.test_application_gui import ApplicationGuiTests
case = ApplicationGuiTests()
case.setUp()
workspace = case.git_workspace('new task workspace')
held, _ = harness.start('cognition', 'Investigate the parser and report useful conclusions', case.workspace, case.runs,
                         model='openai-codex/gpt-6.1-sol', client='pi', max_activations=0)
legacy = runtime.create_run({'goal': 'Explain parser behavior and next development steps'}, case.workspace, case.runs)
runtime.record(legacy, 'program.started', {'client': 'pi', 'model': 'openai-codex/gpt-6.1-sol'})
for role, text in [('work', 'Parser investigation complete. Three useful changes are ready for review.'),
                   ('review', 'Reviewed the parser changes. The acceptance criteria are satisfied. <script>literal text</script>')]:
    runtime.record(legacy, 'step.started', {'step': role, 'argv': ['pi', '--model', 'openai-codex/gpt-6.1-sol']})
    runtime.record(legacy, 'step.finished', {'step': role, 'state': 'passed', 'returncode': 0})
    output = json.dumps({'outcome': 'advance', 'content': {'observations': [text], 'questions': [], 'evidence_refs': []}}) if role == 'work' else text
    message = {'role': 'assistant', 'content': [{'type': 'text', 'text': output}], 'model': 'gpt-6.1-sol', 'provider': 'fixture', 'stopReason': 'stop'}
    records = [{'type': 'session', 'id': f'fixture-{role}'}, {'type': 'message_end', 'message': message}, {'type': 'agent_end', 'messages': [message]}]
    if role == 'work':
        second = {**message, 'content': [{'type': 'text', 'text': json.dumps({'content': {'questions': ['Which parser mode applies?'], 'evidence_refs': ['fixture.txt'], 'changed': False, 'result_count': 0}})}]}
        records += [{'type': 'message_end', 'message': second}, {'type': 'agent_end', 'messages': [second], 'willRetry': True}]
    (legacy / f'{role}.stdout.log').write_text('\\n'.join(json.dumps(row) for row in records))
    (legacy / f'{role}.md').write_text(text)
for i in range(12):
    runtime.create_run({'goal': f'Historical project task {i}'}, case.workspace, case.runs)
source = legacy / 'work.stdout.log'
before = (source.read_bytes(), source.stat().st_mtime_ns)
def finish(*_):
    assert (source.read_bytes(), source.stat().st_mtime_ns) == before
    case.doCleanups()
    sys.exit(0)
signal.signal(signal.SIGTERM, finish)
print(json.dumps({'port': case.server.server_port, 'token': case.server.token, 'held': held.name,
                  'legacy': legacy.name, 'workspace': str(workspace), 'work_raw': source.read_text()}), flush=True)
while True: time.sleep(.1)
`], { cwd: path.resolve(__dirname, '../..'), stdio: ['ignore', 'pipe', 'pipe'], env:Object.fromEntries(Object.entries(process.env).filter(([key])=>!['USER_PROVIDED_PASSWORD','NOETIC_APP_HOME','NOETIC_STATE_HOME'].includes(key))) });
  let browser, output = '', errorsOutput = '';
  fixture.stderr.on('data', chunk => { errorsOutput += chunk; });
  try {
    const info = await new Promise((resolve, reject) => {
      fixture.stdout.on('data', chunk => {
        output += chunk;
        const line = output.split('\n').find(line => line.startsWith('{'));
        if (line) resolve(JSON.parse(line));
      });
      fixture.once('error', reject);
      fixture.once('exit', () => reject(new Error(errorsOutput || 'Fixture exited')));
    });
    const directory = process.env.NOETIC_TEST_SCREENSHOTS || '/tmp/noetic-session-workspace';
    fs.mkdirSync(directory, { recursive: true });
    browser = await chromium.launch({ headless: true, executablePath: process.env.NOETIC_TEST_CHROMIUM || undefined });
    const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
    const errors = [], actions = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (request.method() === 'POST') actions.push({ route: new URL(request.url()).pathname, body: request.postDataJSON() });
    });
    await page.goto(`http://127.0.0.1:${info.port}/`);
    await page.locator('#access-token').fill(info.token);
    await page.locator('#access-form button').click();
    await page.locator('#private-workspace').waitFor({ state: 'visible' });
    await page.locator('.tools-menu > summary').click();
    await page.locator('#structured-register > summary').click();
    await page.locator(`[data-run-id="${info.legacy}"]`).click();
    await page.locator('#session-select option[value=review]').waitFor({state:'attached'});
    await page.locator('#session-select').selectOption('review');
    await page.locator('#session-transcript').getByText('Reviewed the parser changes.', { exact: false }).waitFor();
    assert.equal(await page.locator('#evidence-drawer').evaluate(el => el.open), false);
    assert.equal(await page.locator('#timeline').isVisible(), false);
    assert.equal(await page.locator('#advance-all').isVisible(), false);
    assert.equal(await page.locator('#session-select').inputValue(), 'review');
    assert.equal(await page.locator('#run-list').evaluate(el => {
      const rows = [...el.children].map(row => row.getBoundingClientRect());
      return rows.every((row, i) => !i || row.top >= rows[i - 1].bottom);
    }), true, 'Session rows must scroll without overlapping');
    await page.screenshot({ path: path.join(directory, 'desktop-session.png') });
    await page.locator('#session-select').selectOption('work');
    await page.locator('#session-transcript').getByText('Parser investigation complete.', { exact: false }).waitFor();
    const meaningful = 'Parser investigation complete. Three useful changes are ready for review.';
    const checkPrimary = async () => {
      const primary = await page.locator('#session-transcript').innerText();
      assert.equal(primary.split(meaningful).length - 1, 1, 'Identical assistant/final content must appear once');
      const response = await page.locator('#session-transcript article').filter({ hasText: meaningful }).innerText();
      assert.equal(response.includes('questions'), false);
      assert.equal(response.includes('evidence refs'), false);
      assert.equal(primary.includes('timestamp not recorded'), false);
      assert.match(primary, /Which parser mode applies\?/);
      assert.match(primary, /fixture\.txt/);
      assert.match(primary, /changed\s+false/);
      assert.match(primary, /result count\s+0/);
      assert.match(primary, /Final response · stop/);
      assert.match(primary, /Retry requested · stop/);
      assert.equal(await page.locator('#evidence-drawer').evaluate(el => el.open), false);
      assert.equal(await page.locator('#session-raw').isVisible(), false);
      assert.equal(await page.locator('#session-raw').textContent(), info.work_raw);
      const normalized = JSON.parse(await page.locator('#session-normalized').textContent());
      assert.equal(normalized.length, 4, 'All normalized assistant/final records remain available');
      assert.equal(normalized.filter(entry => entry.kind === 'final').length, 2);
      assert.equal(normalized[0].content.includes('"questions": []'), true);
    };
    await checkPrimary();
    await page.screenshot({ path: path.join(directory, 'desktop-primary-output.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    await checkPrimary();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path: path.join(directory, 'mobile-primary-output.png'), fullPage: true });
    await page.locator('#evidence-drawer > summary').click();
    await page.locator('#transcript-details > summary').click();
    await page.locator('#session-raw').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#session-raw').textContent(), info.work_raw);
    assert.equal(await page.locator('#session-normalized').isVisible(), true);
    await page.locator('#evidence-drawer > summary').click();
    await page.setViewportSize({ width: 1440, height: 960 });
    if (process.env.NOETIC_TEST_PRIMARY_OUTPUT_ONLY === '1') {
      assert.deepEqual(errors, []);
      console.log('PASS useful response once, no empty field/missing-time noise, distinct content and status/retry preserved, exact raw/normalized records accessible in drawer, desktop/mobile; retained bytes/mtime unchanged');
      return;
    }

    await page.evaluate(() => refresh());
    assert.equal(await page.locator('#session-select').inputValue(), 'work');
    assert.equal(await page.locator('#follow-current').isChecked(), false);
    await page.reload();
    await page.locator('#session-transcript').getByText('Parser investigation complete.', { exact: false }).waitFor();
    assert.equal(await page.locator('#session-select').inputValue(), 'work');
    assert.equal(await page.locator('#session-agent-list [aria-current="true"]').getAttribute('data-focus-key'), 'work');
    await page.evaluate(id => selectRun(id, { source: 'work.md' }), info.legacy);
    await page.locator('#report-text').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#evidence-drawer').evaluate(el => el.open), true);
    await page.evaluate(id => selectRun(id), info.legacy);
    assert.equal(await page.locator('#evidence-drawer').evaluate(el => el.open), false);
    await page.locator('#evidence-drawer > summary').click();
    await page.locator('#report-text').waitFor({ state: 'visible' });
    assert.match(await page.locator('#report-text').innerText(), /Parser investigation complete/);
    await page.locator('#evidence-drawer > summary').click();
    await page.locator(`[data-run-id="${info.held}"]`).click();
    await page.locator('#advance-one').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#advance-one').isEnabled(), true);
    await page.locator('#pause-pattern').click();
    await page.waitForFunction(() => document.getElementById('primary-progress').textContent.includes('held'));
    await page.locator('#advance-one').click();
    await page.waitForFunction(() => document.querySelectorAll('#session-select option').length > 1);
    await page.waitForFunction(() => !document.getElementById('advance-all').disabled);
    assert.equal(await page.locator('#session-select').inputValue(), 'activation-1');
    await page.locator('#session-select').selectOption('activation-0');
    await page.locator('#session-transcript').getByText('Final response · stop', { exact: false }).first().waitFor();
    await page.evaluate(() => refresh());
    assert.equal(await page.locator('#session-select').inputValue(), 'activation-0');
    assert.equal(await page.locator('#session-agent-list [aria-current="true"]').getAttribute('data-focus-key'), 'activation-0');
    await page.screenshot({ path: path.join(directory, 'desktop-controller.png') });
    await page.locator('#advance-all').click();
    await page.waitForFunction(() => document.getElementById('run-state').textContent === 'completed');
    assert.equal(await page.locator('#advance-all').isVisible(), false);
    await page.locator('.tools-menu').evaluate(element=>element.open=true);await page.locator('.workspace-navigation [data-page="new"]').click();
    assert.equal(await page.locator('#advanced-settings').isVisible(), false);
    await page.locator('#start-task').fill('Implement a useful parser change with a checked result');
    await page.locator('#start-workspace').fill(info.workspace);
    await page.locator('#start-change-model').click();await page.locator('#start-profile').selectOption('opencode-direct');
    await page.locator('[data-settings=review]').click();await page.locator('#start-verify').fill('["python", "-c", "assert 2 + 2 == 4"]');
    await page.screenshot({ path: path.join(directory, 'desktop-new-task.png') });
    await page.locator('#start-submit').click();
    await page.waitForFunction(() => document.getElementById('run-goal').textContent.includes('Implement a useful parser'));
    await page.waitForFunction(() => document.getElementById('run-state').textContent === 'completed');
    const start = actions.find(action => action.route === '/api/application/start');
    assert.equal(start.body.task, 'Implement a useful parser change with a checked result');
    assert.equal(start.body.client, 'opencode');
    assert.equal(start.body.model, 'openai/gpt-6.1-sol');
    assert.deepEqual(start.body.verify, ['python', '-c', 'assert 2 + 2 == 4']);
    assert.equal(actions.some(action => action.route.endsWith('/pause') && Object.keys(action.body).length === 0), true);
    assert.equal(actions.some(action => action.route.endsWith('/advance') && action.body.mode === 'one'), true);
    assert.equal(actions.some(action => action.route.endsWith('/advance') && action.body.mode === 'all'), true);
    await page.locator('.tools-menu').evaluate(element=>element.open=true);await page.locator('.workspace-navigation [data-page="new"]').click();
    await page.locator('#start-task').fill('Fixture task to stop explicitly');
    await page.locator('#start-pattern').selectOption('cognition');
    await page.locator('[data-settings=purpose]').click();
    await page.locator('#start-sources').fill('fixture:block');
    await page.locator('#start-submit').click();
    await page.waitForFunction(() => document.getElementById('run-goal').textContent.includes('stop explicitly'));
    await page.waitForFunction(() => document.getElementById('primary-progress').textContent.includes('running'));
    page.once('dialog', dialog => dialog.accept());
    await page.locator('#cancel-pattern').click();
    await page.waitForFunction(() => document.getElementById('run-state').textContent === 'cancelled', null, { timeout: 30000 });
    assert.equal(actions.some(action => action.route.endsWith('/cancel') && action.body.confirm === true), true);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('#toggle-navigation').click();
    await page.locator(`[data-run-id="${info.legacy}"]`).click();
    await page.locator('#session-transcript').getByText('Parser investigation complete.', { exact: false }).waitFor();
    assert.equal(await page.locator('#evidence-drawer').evaluate(el => el.open), false);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path: path.join(directory, 'mobile-session.png'), fullPage: true });
    await page.locator('.session-next [data-page="new"]').click();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path: path.join(directory, 'mobile-new-task.png'), fullPage: true });
    await page.locator('#access-lock').click();
    await page.locator('#private-workspace').waitFor({ state: 'hidden' });
    assert.deepEqual(errors, []);
    console.log('PASS pairing, legacy and controller agent selection, output, on-demand evidence, real start/pause/step/continue/stop, exact action payloads, profile identity, narrow layout, lock');
    console.log(`Screenshots: ${directory}`);
  } finally {
    if (browser) await browser.close();
    const exited = once(fixture, 'exit');
    fixture.kill('SIGTERM');
    await exited;
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
