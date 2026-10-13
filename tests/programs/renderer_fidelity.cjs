const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const root = path.resolve(__dirname, '../..');
  const index = fs.readFileSync(path.join(root, 'scripts/web/index.html'), 'utf8');
  const html = index.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, '');
  const SOURCE_LINES = Array.from({length: 200}, (_, i) => `source line ${i + 1}`);
  SOURCE_LINES[99] = 'X'.repeat(4000);
  SOURCE_LINES[149] = 'OB15-TARGET-LINE exact source line150';
  const SOURCE_TEXT = SOURCE_LINES.join('\n');
  const SHORT_TEXT = 'only line one\nonly line two\nonly line three';
  const fileBodies = {'/fixture/source.cjs': SOURCE_TEXT, '/fixture/short.cjs': SHORT_TEXT, '/fixture/plain.cjs': 'plain alpha\nplain beta'};
  const devSession = {id: 'dev-x', ordinal: '0.0', target: {ordinal: '0.0', instantiation: 2, session: 1}, effort_root: '0.0', title: 'Dev session', workspace: '/fixture', model: 'fixture/model', thinking: 'high', status: 'idle', is_current: true, broker_owned: true, domain_status: 'open'};
  const runSession = {id: 'run-x', kind: 'run', title: 'Run session', workspace: '/fixture', status: 'running', viewVersion: 0};
  const sessions = [devSession, runSession];
  const env = {...process.env}; delete env.USER_PROVIDED_PASSWORD;
  const browser = await chromium.launch({headless: true, env, executablePath: process.env.NOETIC_TEST_CHROMIUM || undefined});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}}), errors = [], fileCalls = [];
    page.on('pageerror', error => { errors.push(error.message); console.error('fixture-pageerror', error.message); });
    let gate = null; // optional delayed reply for the late-file-replay qualification
    await page.route('http://fixture/**', async route => {
      const url = new URL(route.request().url());
      let result = {};
      if (url.pathname === '/') return route.fulfill({contentType: 'text/html', body: html});
      if (url.pathname === '/api/ordinals/0/branch') result = {records: [{ordinal: '0.0', effort: '0.0', origin: 'human', current_instantiation: 2}], next_after: 0};
      else if (url.pathname === '/api/preview-info') result = {};
      else if (url.pathname === '/api/developer-sessions') result = {sessions, projects_root: '/fixture'};
      else if (url.pathname === '/api/developer-sessions/0.0') result = {session: devSession, events: [{sequence: 1, record: {type: 'message_end', message: {role: 'assistant', content: 'See [source](/fixture/source.cjs:150) and [column](/fixture/source.cjs:150:7) and [short](/fixture/short.cjs:150) and [plain](/fixture/plain.cjs) and https://example.invalid/doc.'}}}], next_after: 0};
      else if (url.pathname === '/api/developer-sessions/run-x') result = {session: runSession, events: [{sequence: 1, record: {type: 'message_end', message: {role: 'assistant', content: 'Run inspect [rsource](/fixture/source.cjs:150).'}}}], next_after: 0};
      else if (url.pathname.startsWith('/api/runs/') && url.pathname.endsWith('/project-file')) {
        const requested = url.searchParams.get('path'); fileCalls.push(requested);
        if (gate) await gate; gate = null;
        result = {path: requested, text: fileBodies[requested] ?? ''};
      }
      else if (url.pathname.includes('/file')) {
        const requested = url.searchParams.get('path'); fileCalls.push(requested);
        if (gate) await gate; gate = null;
        result = {path: requested, text: fileBodies[requested] ?? ''};
      }
      await route.fulfill({contentType: 'application/json', body: JSON.stringify(result)});
    });
    await page.goto('http://fixture/');
    await page.addScriptTag({content: `const $=id=>document.getElementById(id);var operatorToken='fixture',accessVersion=0,var_operationVersionPlaceholder=0,selectedId='run-x';var operationVersion=0;const operationSelection=()=>({});const scopedURL=p=>p;const switchPage=(page)=>{document.querySelectorAll('[data-page]').forEach(b=>{$(b.dataset.page+'-page').hidden=b.dataset.page!==page;});};const fetchJSON=async(p,options)=>{const r=await fetch(p,options);return r.json();};const node=(tag,value,cls)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;if(cls)e.className=cls;return e;};const text=(id,value)=>$(id).textContent=value;const error=(id,value)=>{text(id,value);$(id).hidden=!value;};let allRuns=[];$('private-workspace').hidden=false;`});
    await page.addStyleTag({path: path.join(root, 'scripts/web/style.css')});
    await page.addStyleTag({path: path.join(root, 'scripts/web/shell-agentics.css')});
    await page.addScriptTag({path: path.join(root, 'scripts/web/shell.js')});
    await page.addScriptTag({path: path.join(root, 'scripts/web/sessions.js')});
    await page.addScriptTag({path: path.join(root, 'scripts/web/shell-agentics.js')});
    await page.evaluate(() => NoeticUI.navigate('agentics'));
    await page.waitForFunction(() => Boolean(window.NoeticRichText));

    // OB14: markdown ordered/unordered transitions, nonsequential supplied identities, fenced code fidelity.
    const lists = await page.evaluate(() => {
      const host = NoeticRichText([
        'intro',
        '7. seven',
        '8. eight',
        '- dash one',
        '- dash two',
        '3. three again',
        '```',
        'fenced | line one',
        '7. not a list item',
        '```',
        '- dash three',
        'plain tail'
      ].join('\n'));
      return [...host.children].map(el => ({
        tag: el.tagName,
        start: el.start ?? null,
        items: el.tagName === 'OL' || el.tagName === 'UL' ? [...el.children].map(li => ({value: li.value ?? null, text: li.textContent})) : undefined,
        text: el.tagName === 'OL' || el.tagName === 'UL' ? undefined : el.textContent
      }));
    });
    assert.deepEqual(lists.filter(el => el.tag === 'OL').map(el => [el.start, el.items.map(item => [item.value, item.text])]),
      [[7, [[7, 'seven'], [8, 'eight']]], [3, [[3, 'three again']]]], 'ordered lists keep supplied nonsequential identities via native start/value');
    assert.deepEqual(lists.filter(el => el.tag === 'UL').map(el => el.items.map(item => item.text)),
      [['dash one', 'dash two'], ['dash three']], 'unordered lists stay separate across ordered transitions');
    assert.deepEqual(lists.filter(el => el.tag === 'PRE').map(el => el.text), ['fenced | line one\n7. not a list item'], 'fenced code text is preserved verbatim');
    assert.deepEqual(lists.filter(el => el.tag === 'P').map(el => el.text), ['intro', 'plain tail'], 'paragraph text preserved');

    // OB15 developer session: open transcript with mixed links.
    await page.evaluate(() => NoeticSessions.open({ordinal: '0.0', instantiation: 2, session: 1, effort_root: '0.0'}));
    await page.waitForFunction(() => document.querySelector('#developer-transcript a'));
    const link = page.locator('#developer-transcript a', {hasText: 'source'});
    await link.click();
    await page.waitForFunction(() => !document.getElementById('developer-file-view').hidden);
    assert.equal(await page.locator('#developer-file-path').textContent(), '/fixture/source.cjs:150', 'source-view identity keeps cleaned path with requested line');
    assert.equal(await page.locator('#developer-file-text').textContent(), SOURCE_TEXT, 'returned source text preserved byte-for-byte');
    assert.equal(await page.locator('#developer-file-text mark').textContent(), 'OB15-TARGET-LINE exact source line150', 'requested line 150 is marked');
    const markedVisible = await page.locator('#developer-file-text mark').evaluate(el => { const r = el.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; });
    assert.ok(markedVisible, 'marked line is revealed within the source view');
    assert.equal(await page.evaluate(() => document.activeElement && document.activeElement.id), 'developer-file-text', 'existing pre target receives focus');
    await page.setViewportSize({width: 520, height: 600}); await page.waitForTimeout(80);
    await page.locator('#developer-file-close').click();
    await page.locator('#developer-transcript a', {hasText: 'source'}).first().click();
    await page.waitForFunction(() => document.querySelectorAll('#developer-file-text mark').length === 1);
    const narrow = await page.evaluate(() => {
      const mark = document.querySelector('#developer-file-text mark').getBoundingClientRect();
      const pre = document.getElementById('developer-file-text').getBoundingClientRect();
      return {inside: mark.top >= pre.top - 1 && mark.bottom <= pre.bottom + 1, mark, pre};
    });
    assert.ok(narrow.inside, `mark revealed within visible pre area at narrow width (mark ${JSON.stringify({t: narrow.mark.top, b: narrow.mark.bottom})}, pre ${JSON.stringify({t: narrow.pre.top, b: narrow.pre.bottom})})`);
    await page.setViewportSize({width: 1440, height: 1000}); await page.waitForTimeout(80);
    await page.locator('#developer-file-close').click();

    // Column suffix retains the same line accurately.
    await page.locator('#developer-transcript a', {hasText: 'column'}).click();
    await page.waitForFunction(() => document.querySelectorAll('#developer-file-text mark').length === 1);
    assert.equal(await page.locator('#developer-file-text mark').textContent(), 'OB15-TARGET-LINE exact source line150', 'column suffix still maps to line 150');
    assert.equal(await page.locator('#developer-file-path').textContent(), '/fixture/source.cjs:150', 'column suffix retains line in identity');
    await page.locator('#developer-file-close').click();

    // Unavailable location: explicit notice, exact path preserved.
    await page.locator('#developer-transcript a', {hasText: 'short'}).click();
    await page.waitForFunction(() => !document.getElementById('developer-error').hidden);
    assert.match(await page.locator('#developer-error').textContent(), /Line 150 is not present in \/fixture\/short\.cjs\./, 'explicit unavailable-location notice');
    assert.equal(await page.locator('#developer-file-path').textContent(), '/fixture/short.cjs:150', 'unavailable notice keeps exact cleaned path with requested line');
    await page.locator('#developer-file-close').click();

    // Ordinary local reference without location unchanged.
    await page.locator('#developer-transcript a', {hasText: 'plain'}).click();
    await page.waitForFunction(() => document.getElementById('developer-file-path').textContent === '/fixture/plain.cjs');
    assert.equal(await page.locator('#developer-file-text mark').count(), 0, 'no marking without a location suffix');
    assert.equal(await page.locator('#developer-file-text').textContent(), fileBodies['/fixture/plain.cjs'], 'plain source text preserved');
    assert.ok(await page.evaluate(() => document.getElementById('developer-error').hidden), 'no error for a plain reference');
    await page.locator('#developer-file-close').click();

    // External URLs are unchanged anchors and are never fetched through the file route.
    const external = await page.evaluate(() => { const host = NoeticRichText('[ext](https://example.invalid/doc)', {kind: 'developer'}); const a = host.querySelector('a'); return {href: a.getAttribute('href'), target: a.target, rel: a.rel}; });
    assert.deepEqual(external, {href: 'https://example.invalid/doc', target: '_blank', rel: 'noopener noreferrer'}, 'external URL anchor unchanged');

    // Late file reply under changed owner must not reveal.
    let releaseGate; gate = new Promise(resolve => { releaseGate = resolve; });
    await page.locator('#developer-transcript a', {hasText: 'source'}).first().click();
    await page.evaluate(() => NoeticSessions.open({ordinal: '0.0', instantiation: 2, session: 1, effort_root: '0.0'}));
    await page.waitForFunction(() => NoeticSessions.state().selected !== null);
    releaseGate();
    await page.waitForTimeout(150);
    assert.ok(await page.evaluate(() => document.getElementById('developer-file-view').hidden), 'late reply after selection change stays hidden');

    // Run qualification: same safeLink behavior through the run branch.
    await page.evaluate(() => NoeticSessions.open({id: 'run-x'}));
    await page.waitForFunction(() => [...document.querySelectorAll('#developer-transcript a')].some(a => a.textContent === 'rsource'));
    await page.locator('#developer-transcript a', {hasText: 'rsource'}).click();
    await page.waitForFunction(() => !document.getElementById('workspace-file-view').hidden);
    assert.equal(await page.locator('#workspace-file-path').textContent(), '/fixture/source.cjs:150', 'run branch keeps requested line in source identity');
    assert.equal(await page.locator('#workspace-file-text mark').textContent(), 'OB15-TARGET-LINE exact source line150', 'run branch marks line 150');
    await page.locator('#workspace-file-view').evaluate(el => {el.hidden = true;});

    assert.equal(fileCalls.every(value => !value.endsWith(':150') && !value.endsWith(':150:7')), true, 'backend always receives the cleaned path');
    assert.deepEqual(errors, [], 'no page errors');
    console.log('renderer_fidelity: all acceptance checks passed');
  } finally { await browser.close(); }
})().catch(failure => { console.error('renderer_fidelity FAILED:', failure.message); process.exit(1); });
