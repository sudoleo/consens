import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { JSDOM } from 'jsdom';
import { ROOT } from './helpers/appWindow.mjs';

const source = readFileSync(path.join(ROOT, 'static/js/admin.js'), 'utf8');
const template = readFileSync(path.join(ROOT, 'templates/admin.html'), 'utf8');
const gemini = 'google/gemini-3.5-flash-lite';
const mistral = 'mistralai/mistral-small-2603';

function boot() {
    const window = new JSDOM(template, { runScripts: 'outside-only', url: 'https://consens.io/admin' }).window;
    window.eval(`var globalModelsData = ${JSON.stringify({
        source_verification_model: gemini,
        source_verification_fallback_model: '',
        _meta: {source_verification_default: gemini, source_verification_models: [
            {id: gemini, label: 'Gemini 3.5 Flash-Lite'}, {id: mistral, label: '<b>Mistral Small 4</b>'}
        ]}
    })};
    function meta() { return globalModelsData._meta; }
    ${source.slice(source.indexOf('function currentSourceVerificationModel()'), source.indexOf('function currentJudgeModels()'))}
    window.readSelected = currentSourceVerificationModel;
    window.readFallback = currentSourceVerificationFallbackModel;
    window.renderSource = renderSourceVerificationSelect;
    window.replaceSaved = value => { globalModelsData.source_verification_model = value; };
    window.replaceSavedFallback = value => { globalModelsData.source_verification_fallback_model = value; };
    renderSourceVerificationSelect(true);`);
    return window;
}

describe('Admin source-check model', () => {
    it('shows the Gemini default and renders model labels as text', () => {
        const window = boot();
        expect(window.readSelected()).toBe(gemini);
        const select = window.document.getElementById('sourceVerificationModelSelect');
        expect(select.selectedOptions[0].textContent).toContain('default');
        expect(select.querySelector('b')).toBeNull();
        expect(select.textContent).toContain('<b>Mistral Small 4</b>');
        window.close();
    });

    it('keeps a draft choice during rerenders and discards it when saved data reloads', () => {
        const window = boot();
        window.document.getElementById('sourceVerificationModelSelect').value = mistral;
        window.renderSource();
        expect(window.readSelected()).toBe(mistral);
        window.replaceSaved(gemini);
        window.renderSource(true);
        expect(window.readSelected()).toBe(gemini);
        window.close();
    });

    it('defaults fallback to Disabled and prevents selecting the primary model twice', () => {
        const window = boot();
        const select = window.document.getElementById('sourceVerificationFallbackModelSelect');
        expect(window.readFallback()).toBe('');
        expect(select.selectedOptions[0].textContent).toBe('Disabled');
        expect([...select.options].find(option => option.value === gemini).disabled).toBe(true);
        expect([...select.options].find(option => option.value === mistral).disabled).toBe(false);
        expect(select.querySelector('b')).toBeNull();
        window.close();
    });

    it('preserves a Disabled draft instead of restoring a previously saved fallback', () => {
        const window = boot();
        window.replaceSavedFallback(mistral);
        window.renderSource(true);
        expect(window.readFallback()).toBe(mistral);
        window.document.getElementById('sourceVerificationFallbackModelSelect').value = '';
        window.renderSource();
        expect(window.readFallback()).toBe('');
        window.renderSource(true);
        expect(window.readFallback()).toBe(mistral);
        window.close();
    });

    it('sends the chosen source model through the existing admin save request', async () => {
        const window = boot();
        for (const tier of ['free', 'pro']) {
            for (const provider of ['gemini', 'mistral']) {
                const select = window.document.createElement('select');
                select.dataset.watchTier = tier; select.dataset.provider = provider;
                select.appendChild(new window.Option('model', 'model'));
                window.document.body.appendChild(select);
            }
            const select = window.document.createElement('select');
            select.dataset.watchConsensusTier = tier;
            select.appendChild(new window.Option('Gemini', 'Gemini'));
            window.document.body.appendChild(select);
        }
        window.document.getElementById('sourceVerificationModelSelect').value = mistral;
        window.renderSource();
        window.document.getElementById('sourceVerificationFallbackModelSelect').value = gemini;
        const requests = [];
        window.fetch = async (url, options) => { requests.push({url, ...options}); return {ok: true}; };
        window.eval(`const auth = {currentUser: {getIdToken: async () => 'test-token'}};
            const providers = [];
            function consensusListValues() { return []; }
            function currentPresetModels() { return {}; }
            function currentDeepThinkModel() { return 'Gemini'; }
            function currentJudgeModels() { return {}; }
            function currentProJudgeModels() { return {}; }
            function currentJudgeFamilies() { return {}; }
            function currentChatMemoryModels() { return {}; }
            function setStatus() {}
            function clearDirty() {}
            async function fetchModels() {}
            ${source.slice(source.indexOf('async function saveModels()'), source.indexOf("document.getElementById('saveBtn')"))}
            window.saveSource = saveModels;`);
        await window.saveSource();
        expect(requests).toHaveLength(1);
        expect(requests[0].url).toBe('/api/admin/models');
        expect(JSON.parse(requests[0].body).source_verification_model).toBe(mistral);
        expect(JSON.parse(requests[0].body).source_verification_fallback_model).toBe(gemini);
        window.close();
    });
});
