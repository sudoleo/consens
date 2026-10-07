export function createPromptConfigPanel(request) {
    const panel = document.getElementById('tab-configuration');
    const form = document.getElementById('promptConfigForm');
    const fields = document.getElementById('promptConfigFields');
    const status = document.getElementById('promptConfigStatus');
    const meta = document.getElementById('promptConfigMeta');
    const save = document.getElementById('savePromptConfigBtn');
    const reload = document.getElementById('reloadPromptConfigBtn');
    const zone = document.getElementById('promptReferenceTimezone');
    const delegation = document.getElementById('delegationConfig');
    const catalog = document.getElementById('promptCatalog');
    const delegationInputs = new Map();
    let user = null, generation = 0, saved = null, busy = false, cacheSeconds = 30;

    // System prompts are code-owned: the admin only edits timezone and
    // delegation settings; prompts are rendered read-only from the catalog.
    function draft() {
        return { reference_timezone: zone.value.trim(),
            ...(saved?.delegation ? { delegation: Object.fromEntries([...delegationInputs].map(([key, input]) =>
                [key, input.type === 'checkbox' ? input.checked : Number(input.value)])) } : {}) };
    }
    function dirty() {
        return saved && (zone.value.trim() !== saved.reference_timezone
            || (saved.delegation && JSON.stringify(draft().delegation) !== JSON.stringify(saved.delegation)));
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
        delegationInputs.forEach((input, key) => {
            if (input.type === 'checkbox') input.checked = config.delegation?.[key] === true;
            else input.value = config.delegation?.[key] ?? '';
        });
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
            delegationInputs.clear(); delegation.replaceChildren();
            delegation.hidden = !result.config.delegation;
            const budgetNote = document.createElement('p');
            budgetNote.className = 'section-hint';
            budgetNote.textContent = 'Agent Chat uses the daily token budget in Limits. Active responses have no time, round, search or cost cap. Worker concurrency and message sizes below still apply.';
            delegation.append(budgetNote);
            const legacyLimits = new Set(['max_calls', 'max_tools', 'seconds', 'max_tokens', 'max_cost_nano_usd',
                'max_messages', 'context_chars', 'worker_calls', 'max_searches']);
            const labels = { enabled: 'Allow delegation', max_calls: 'Model calls per run', max_tools: 'Coordination calls per run',
                seconds: 'Run duration (seconds)', max_tokens: 'Shared token budget', max_cost_nano_usd: 'Shared cost budget (nanodollars; 1 USD = 1,000,000,000)',
                max_agents: 'Unreviewed workers at once', max_parallel: 'Workers running at once', max_messages: 'Messages per run',
                context_chars: 'Context per session (characters)', message_chars: 'Message length (characters)', worker_calls: 'Model calls per worker',
                max_searches: 'Web searches per run' };
            for (const [key, value] of Object.entries(result.config.delegation || {})) {
                // Prompt texts are shown in the read-only catalog, never as inputs.
                if (typeof value !== 'boolean' && typeof value !== 'number') continue;
                const label = document.createElement('label'); label.htmlFor = `delegation-${key}`; label.textContent = labels[key] || key;
                const input = document.createElement('input'); input.id = label.htmlFor;
                // Preserve old configuration for legacy/evaluation callers, but
                // don't offer ineffective run caps as Agent Chat settings.
                label.hidden = input.hidden = legacyLimits.has(key);
                if (typeof value === 'boolean') input.type = 'checkbox';
                else if (typeof value === 'number') {
                    input.type = 'number'; input.step = '1'; input.required = true;
                    const limits = result.delegation_limits?.[key];
                    if (limits) { input.min = limits[0]; input.max = limits[1]; }
                }
                delegationInputs.set(key, input); delegation.append(label, input);
            }
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
        if ([...delegationInputs.values()].some(input => !input.checkValidity())) delegation.closest('details').open = true;
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
            delegationInputs.clear(); delegation.replaceChildren(); delegation.hidden = true;
            catalog.replaceChildren();
            meta.textContent = '';
            message(uid ? '' : 'Log in as an admin to edit configuration.');
            sync();
            if (uid) return load();
        },
    };
}
