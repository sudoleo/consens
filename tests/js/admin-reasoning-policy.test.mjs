import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { JSDOM } from 'jsdom';
import { ROOT } from './helpers/appWindow.mjs';

const source = readFileSync(path.join(ROOT, 'static/js/admin.js'), 'utf8');
const template = readFileSync(path.join(ROOT, 'templates/admin.html'), 'utf8');
const preview = value => Object.fromEntries(['answers', 'deep', 'synthesis', 'helpers'].map(key => [key, value]));

function boot() {
    const dom = new JSDOM(template, { runScripts: 'outside-only', url: 'https://consens.io/admin' });
    const data = {
        reasoning_policy: { profile: 'existing', models: {} },
        _meta: { reasoning: { controls: [
            { model: 'grok-4.3', provider: 'grok', label: 'Grok 4.3', deep_model: true, supported: true, note: 'Low cap',
                previews: { existing: preview({ effort: 'high' }), economy: preview({ effort: 'low' }) } },
            { model: 'kimi-k3', provider: 'kimi', label: '<script>unsafe</script>', supported: false, note: 'Required reasoning',
                previews: { existing: preview({ enabled: true }), economy: preview({ enabled: true }) } },
        ] } },
    };
    dom.window.eval(`let globalModelsData = ${JSON.stringify(data)};
        function markDirty() { document.getElementById('adminSavebar').classList.add('is-dirty'); }
        ${source.slice(source.indexOf('function meta() {'), source.indexOf('function currentPresetModels() {'))}
        renderReasoningControls();
        window.getDraft = () => globalModelsData.reasoning_policy;
    `);
    return dom.window;
}

function change(window, element, value) {
    element.value = value;
    element.dispatchEvent(new window.Event('change', { bubbles: true }));
}

describe('Admin reasoning policy', () => {
    it('previews savings, preserves protected models and serializes a quality exception', () => {
        const window = boot();
        const doc = window.document;
        change(window, doc.getElementById('reasoningProfile'), 'economy');
        expect(doc.getElementById('reasoningSummary').textContent).toContain('1 of 2 models changed');
        expect(doc.querySelector('.reasoning-budget-changed').textContent).toContain('effort: low');
        expect(doc.querySelectorAll('#reasoningControls select')).toHaveLength(1);
        const protectedToggle = doc.getElementById('reasoningShowProtected');
        protectedToggle.checked = true;
        protectedToggle.dispatchEvent(new window.Event('change', { bubbles: true }));
        expect(doc.querySelectorAll('#reasoningControls tbody tr')).toHaveLength(2);
        expect(doc.getElementById('reasoningControls').textContent).toContain('<script>unsafe</script>');
        expect(doc.querySelector('#reasoningControls script')).toBeNull();
        expect(doc.getElementById('adminSavebar').classList.contains('is-dirty')).toBe(true);
        change(window, doc.querySelector('#reasoningControls select'), 'existing');
        expect(window.getDraft().models['grok-4.3']).toBe('existing');
        expect(doc.getElementById('reasoningSummary').textContent).toContain('0 of 2 models changed');
        change(window, doc.querySelector('#reasoningControls select'), '');
        expect(window.getDraft().models['grok-4.3']).toBeUndefined();
        expect(doc.getElementById('reasoningSummary').textContent).toContain('1 of 2 models changed');
        window.close();
    });

    it('changing the preview scope does not dirty the saved configuration', () => {
        const window = boot();
        change(window, window.document.getElementById('reasoningScope'), 'helpers');
        expect(window.document.getElementById('adminSavebar').classList.contains('is-dirty')).toBe(false);
        expect(window.getDraft().profile).toBe('existing');
        change(window, window.document.getElementById('reasoningScope'), 'deep');
        expect(window.document.querySelectorAll('#reasoningControls tbody tr')).toHaveLength(1);
        expect(window.document.getElementById('adminSavebar').classList.contains('is-dirty')).toBe(false);
        window.close();
    });
});
