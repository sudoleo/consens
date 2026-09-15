export function createPromptConfigPanel(request) {
    const panel = document.getElementById('tab-configuration');
    const form = document.getElementById('promptConfigForm');
    const fields = document.getElementById('promptConfigFields');
    const status = document.getElementById('promptConfigStatus');
    const meta = document.getElementById('promptConfigMeta');
    const save = document.getElementById('savePromptConfigBtn');
    const reload = document.getElementById('reloadPromptConfigBtn');
    const zone = document.getElementById('promptReferenceTimezone');
    const keys = ['agent', 'answers', 'consensus'];
    const inputs = Object.fromEntries(keys.map(key => [key, document.getElementById(`prompt-${key}`)]));
    let user = null, generation = 0, saved = null, defaults = null, busy = false, cacheSeconds = 30;

    function draft() {
        return { reference_timezone: zone.value.trim(), prompts: Object.fromEntries(keys.map(key => [key, inputs[key].value])) };
    }
    function dirty() {
        return saved && (zone.value.trim() !== saved.reference_timezone || keys.some(key => inputs[key].value !== saved.prompts[key]));
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
        keys.forEach(key => { inputs[key].value = config.prompts[key]; });
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
            defaults = result.defaults;
            cacheSeconds = result.cache_seconds;
            keys.forEach(key => { inputs[key].maxLength = result.max_prompt_chars; });
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
        keys.forEach(key => { if (!inputs[key].checkValidity()) inputs[key].closest('details').open = true; });
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
    panel.querySelectorAll('[data-reset-prompt]').forEach(button => {
        button.addEventListener('click', () => {
            if (!defaults || busy) return;
            inputs[button.dataset.resetPrompt].value = defaults.prompts[button.dataset.resetPrompt];
            message('Default restored in the draft. Save to apply.'); sync();
        });
    });
    window.addEventListener('beforeunload', event => {
        if (!dirty()) return;
        event.preventDefault(); event.returnValue = '';
    });
    sync();
    return {
        setUser(uid) {
            generation++;
            user = uid;
            saved = defaults = null;
            busy = false;
            zone.value = '';
            keys.forEach(key => { inputs[key].value = ''; });
            meta.textContent = '';
            message(uid ? '' : 'Log in as an admin to edit configuration.');
            sync();
            if (uid) return load();
        },
    };
}
