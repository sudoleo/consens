import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import { JSDOM } from 'jsdom';
import { ROOT } from './helpers/appWindow.mjs';

const template = readFileSync(path.join(ROOT, 'templates/admin.html'), 'utf8')
    .replace('{% include "partials/admin_prompt_config.html" %}', readFileSync(path.join(ROOT, 'templates/partials/admin_prompt_config.html'), 'utf8'));
const source = readFileSync(path.join(ROOT, 'static/js/admin-prompt-config.js'), 'utf8');
const config = { revision: 4, reference_timezone: 'Europe/Berlin', prompts: { agent: 'Agent instructions', answers: 'Answer instructions', consensus: 'Synthesis instructions' } };
const defaults = { reference_timezone: 'Europe/Berlin', prompts: { agent: 'Default agent', answers: 'Default answers', consensus: 'Default synthesis' } };

function boot(request) {
    const dom = new JSDOM(template, { runScripts: 'outside-only', url: 'https://consens.io/admin#configuration' });
    dom.window.eval(source.replace('export function', 'function'));
    const panel = dom.window.createPromptConfigPanel(request);
    return { dom, window: dom.window, doc: dom.window.document, panel };
}
function change(window, id, value) {
    const field = window.document.getElementById(id);
    field.value = value;
    field.dispatchEvent(new window.Event('input', { bubbles: true }));
}
function submit(window) {
    window.document.getElementById('promptConfigForm').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
}
function loaded() { return { config: structuredClone(config), defaults, max_prompt_chars: 10000, cache_seconds: 30 }; }

describe('Admin prompt configuration', () => {
    it('hides retired chat caps while preserving legacy values when saving current settings', async () => {
        const delegation = { enabled: true, max_calls: 32, seconds: 300, max_cost_nano_usd: 3000000000,
            max_parallel: 2, max_agents: 4, message_chars: 4000 };
        const request = vi.fn(async (method, _path, body) => method === 'GET'
            ? { ...loaded(), config: { ...config, delegation } }
            : { config: { ...body.config, revision: 5 } });
        const { window, doc, panel } = boot(request);
        await panel.setUser('admin');
        expect(doc.getElementById('delegation-seconds').hidden).toBe(true);
        expect(doc.getElementById('delegation-max_parallel').hidden).toBe(false);
        expect(doc.getElementById('delegationConfig').textContent).toContain('daily token budget');
        change(window, 'delegation-max_parallel', '3');
        submit(window);
        await vi.waitFor(() => expect(doc.getElementById('promptConfigStatus').textContent).toContain('Saved.'));
        expect(request.mock.calls[1][2].config.delegation).toEqual({ ...delegation, max_parallel: 3 });
        window.close();
    });
    it('loads, edits, saves exactly one config with its revision, and restores defaults as a draft', async () => {
        const request = vi.fn(async (method, _path, body) => method === 'GET' ? loaded() : { config: { ...body.config, revision: 5 } });
        const { window, doc, panel } = boot(request);
        await panel.setUser('admin');
        expect(doc.getElementById('savePromptConfigBtn').disabled).toBe(true);
        change(window, 'prompt-agent', '<script>literal prompt</script>');
        expect(doc.getElementById('promptConfigDirty').hidden).toBe(false);
        expect(doc.querySelector('#tab-configuration script')).toBeNull();
        submit(window);
        expect(doc.getElementById('promptConfigFields').disabled).toBe(true);
        await vi.waitFor(() => expect(doc.getElementById('promptConfigStatus').textContent).toContain('Saved.'));
        expect(request.mock.calls[1]).toEqual(['PUT', '/api/admin/prompt-config', { revision: 4, config: {
            reference_timezone: 'Europe/Berlin', prompts: { ...config.prompts, agent: '<script>literal prompt</script>' },
        } }]);
        expect(doc.getElementById('promptConfigDirty').hidden).toBe(true);
        doc.querySelector('[data-reset-prompt="agent"]').click();
        expect(doc.getElementById('prompt-agent').value).toBe(defaults.prompts.agent);
        expect(doc.getElementById('promptConfigDirty').hidden).toBe(false);
        expect(request).toHaveBeenCalledTimes(2);
        window.close();
    });

    it('keeps the draft after conflict or failure and allows explicit reload', async () => {
        const request = vi.fn(async method => { if (method === 'PUT') throw new Error('Configuration changed in another session.'); return loaded(); });
        const { window, doc, panel } = boot(request);
        await panel.setUser('admin');
        change(window, 'prompt-agent', 'My unsaved draft');
        submit(window);
        await vi.waitFor(() => expect(doc.getElementById('promptConfigStatus').textContent).toContain('another session'));
        expect(doc.getElementById('prompt-agent').value).toBe('My unsaved draft');
        expect(doc.getElementById('promptConfigDirty').hidden).toBe(false);
        doc.getElementById('reloadPromptConfigBtn').click();
        await vi.waitFor(() => expect(doc.getElementById('prompt-agent').value).toBe(config.prompts.agent));
        expect(doc.getElementById('promptConfigDirty').hidden).toBe(true);
        window.close();
    });

    it('does not enable saving after a failed load or apply a stale login response', async () => {
        let resolve;
        const request = vi.fn().mockRejectedValueOnce(new Error('Admin privileges required')).mockImplementationOnce(() => new Promise(done => { resolve = done; }));
        const { window, doc, panel } = boot(request);
        await panel.setUser('member');
        expect(doc.getElementById('promptConfigStatus').textContent).toBe('Admin privileges required');
        expect(doc.getElementById('savePromptConfigBtn').disabled).toBe(true);
        const pending = panel.setUser('admin');
        panel.setUser(null);
        resolve(loaded());
        await pending;
        expect(doc.getElementById('prompt-agent').value).toBe('');
        expect(doc.getElementById('promptConfigFields').disabled).toBe(true);
        window.close();
    });

    it('opens a collapsed editor when its required prompt is empty', async () => {
        const request = vi.fn(async () => loaded());
        const { window, doc, panel } = boot(request);
        await panel.setUser('admin');
        change(window, 'prompt-consensus', '');
        submit(window);
        expect(doc.getElementById('prompt-consensus').closest('details').open).toBe(true);
        expect(request).toHaveBeenCalledTimes(1);
        window.close();
    });
});

describe('Central default and personal Consensus instructions', () => {
    const appUi = readFileSync(path.join(ROOT, 'static/app-ui.js'), 'utf8');
    const query = readFileSync(path.join(ROOT, 'static/js/query-send.js'), 'utf8');
    const preferences = appUi.slice(0, appUi.indexOf('/**'));
    const choose = query.slice(query.indexOf('  function currentSystemPrompt()'), query.indexOf('  function createUsage('));

    it.each([null, '', 'Please respond briefly and precisely, focusing only on the essentials.',
        'Please answer thoroughly and precisely, explaining your reasoning and covering the relevant details. Do not oversimplify. Do not ask any follow-up or clarifying questions; answer directly with the information available.',
    ])('lets the server choose the central default for %s', saved => {
        const dom = new JSDOM('', { runScripts: 'outside-only', url: 'https://consens.io/app' });
        if (saved !== null) dom.window.localStorage.setItem('systemPrompt', saved);
        dom.window.eval(preferences + choose);
        expect(dom.window.currentSystemPrompt()).toBe('');
        dom.window.close();
    });

    it('preserves an explicitly customized personal prompt', () => {
        const dom = new JSDOM('', { runScripts: 'outside-only', url: 'https://consens.io/app' });
        dom.window.localStorage.setItem('systemPrompt', 'Answer in concise German.');
        dom.window.eval(preferences + choose);
        expect(dom.window.currentSystemPrompt()).toContain('Today is ');
        expect(dom.window.currentSystemPrompt()).toContain('Answer in concise German.');
        expect(dom.window.localStorage.getItem('systemPrompt')).toBe('Answer in concise German.');
        dom.window.close();
    });
});
