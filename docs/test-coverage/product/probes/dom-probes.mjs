// Explicit audit observations only; not collected by Vitest.
// Inert local markup and synthetic fetch responses, no external requests.
import { readFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { JSDOM } from 'jsdom';

const root = fileURLToPath(new URL('../../../../', import.meta.url));
const dom = new JSDOM('<div id="topicStrip"><a class="topic-strip-cell"></a></div><div id="topicStripRead">Resting</div>', {
  url: 'https://audit.invalid/topics/example', runScripts: 'outside-only',
});
const cell = dom.window.document.querySelector('.topic-strip-cell');
cell.dataset.date = '2026-09-26';
cell.dataset.note = 'Literal <b id="audit-inert-marker">example</b> text';
dom.window.eval(await readFile(path.join(root, 'static/js/topic-page.js'), 'utf8'));
dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));
cell.dispatchEvent(new dom.window.Event('focus'));
const topic = {
  text: dom.window.document.getElementById('topicStripRead').textContent,
  interpreted_markup: !!dom.window.document.getElementById('audit-inert-marker'),
};
dom.window.close();

const { createAdminClient } = await import(pathToFileURL(path.join(root, 'static/js/admin-api.js')));
const originalFetch = globalThis.fetch;
const admin_client = {};
try {
  const request = createAdminClient({ currentUser: { getIdToken: async () => 'audit-fake-token' } });
  const detail = { error_code: 'not_found', message: 'Account was not found' };
  for (const [name, data] of Object.entries({ default_fastapi: { detail }, main_handler: { error: detail }, string_error: { error: detail.message } })) {
    globalThis.fetch = async () => ({ ok: false, status: 404, json: async () => data });
    try {
      await request('GET', '/audit-synthetic-response');
      admin_client[name] = 'No error thrown';
    } catch (error) {
      admin_client[name] = error.message;
    }
  }
} finally {
  globalThis.fetch = originalFetch;
}
console.log(JSON.stringify({ topic, admin_client }, null, 2));
