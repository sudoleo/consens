export function createPromptConfigPanel(request) {
    const panel = document.getElementById('tab-configuration');
    const form = document.getElementById('promptConfigForm');
    const fields = document.getElementById('promptConfigFields');
    const status = document.getElementById('promptConfigStatus');
    const meta = document.getElementById('promptConfigMeta');
    const save = document.getElementById('savePromptConfigBtn');
    const reload = document.getElementById('reloadPromptConfigBtn');
    const zone = document.getElementById('promptReferenceTimezone');
    const catalog = document.getElementById('promptCatalog');
    let user = null, generation = 0, saved = null, busy = false, cacheSeconds = 30;

    // System prompts are code-owned: the admin only edits the timezone;
    // prompts are rendered read-only from the catalog.
    function draft() {
        return { reference_timezone: zone.value.trim() };
    }
    function dirty() {
        return saved && zone.value.trim() !== saved.reference_timezone;
    }
    function renderCatalog(entries) {
        catalog.replaceChildren(...(entries || []).map(entry => {
            const details = document.createElement('details');
            details.className = 'prompt-config-editor prompt-catalog-entry';
            details.dataset.promptKey = entry.key;
            const summary = document.createElement('summary');
            summary.textContent = entry.label;
            const usedFor = document.createElement('p');
            usedFor.className = 'section-hint';
            usedFor.textContent = entry.used_for;
            const source = document.createElement('p');
            source.className = 'prompt-catalog-source';
            const code = document.createElement('code');
            code.textContent = entry.source;
            source.append('Source: ', code);
            const text = document.createElement('pre');
            text.className = 'prompt-catalog-text';
            text.id = `prompt-${entry.key}`;
            text.tabIndex = 0;
            text.textContent = entry.text;
            details.append(summary, usedFor, source, text);
            return details;
        }));
    }
    function message(text, error = false) {
        status.textContent = text;
        status.classList.toggle('is-error', error);
    }
    function sync() {
        fields.disabled = busy || !saved || !user;
        save.disabled = busy || !user || !saved || (!dirty() && saved.revision > 0);
        reload.disabled = busy || !user;
        panel.classList.toggle('is-dirty', Boolean(dirty()));
        document.getElementById('promptConfigDirty').hidden = !dirty();
    }
    function display(config) {
        saved = config;
        zone.value = config.reference_timezone;
        meta.textContent = config.revision
            ? `Revision ${config.revision}${config.updated_at ? ' · Saved ' + new Date(config.updated_at).toLocaleString() : ''}`
            : 'Using app defaults · No saved configuration yet';
        meta.title = config.updated_by ? `Last saved by ${config.updated_by}` : '';
    }
    async function load() {
        if (!user || busy) return;
        const token = generation;
        busy = true; sync(); message('Loading configuration…');
        try {
            const result = await request('GET', '/api/admin/prompt-config');
            if (token !== generation) return;
            cacheSeconds = result.cache_seconds;
            renderCatalog(result.prompts_readonly);
            display(result.config);
            message('');
        } catch (error) {
            if (token === generation) message(error.message, true);
        } finally {
            if (token === generation) { busy = false; sync(); }
        }
    }
    async function submit(event) {
        event.preventDefault();
        if (!saved || !user || busy) return;
        if (!form.reportValidity()) return;
        const token = generation;
        const payload = { revision: saved.revision, config: draft() };
        busy = true; sync(); message('Saving configuration…');
        try {
            const result = await request('PUT', '/api/admin/prompt-config', payload);
            if (token !== generation) return;
            display(result.config);
            message(`Saved. New requests use this configuration within ${cacheSeconds} seconds.`);
        } catch (error) {
            if (token === generation) message(error.message, true);
        } finally {
            if (token === generation) { busy = false; sync(); }
        }
    }
    form.addEventListener('submit', submit);
    form.addEventListener('input', () => { message(''); sync(); });
    reload.addEventListener('click', load);
    window.addEventListener('beforeunload', event => {
        if (!dirty()) return;
        event.preventDefault(); event.returnValue = '';
    });
    sync();
    return {
        setUser(uid) {
            generation++;
            user = uid;
            saved = null;
            busy = false;
            zone.value = '';
            catalog.replaceChildren();
            meta.textContent = '';
            message(uid ? '' : 'Log in as an admin to edit configuration.');
            sync();
            if (uid) return load();
        },
    };
}
