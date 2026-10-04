import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-app.js";
import { getAuth, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-auth.js";
import { createAdminClient } from "/static/js/admin-api.js";
import { createPromptConfigPanel } from "/static/js/admin-prompt-config.js";
import { createAgentBudgetPanel } from "/static/js/admin-agent-budget.js";

const app = initializeApp(window.FIREBASE_CONFIG);
const auth = getAuth(app);
const shareAdminRequest = createAdminClient(auth);
const promptConfigPanel = createPromptConfigPanel(shareAdminRequest);
const agentBudgetPanel = createAgentBudgetPanel(shareAdminRequest);

let providers = [];
const limitGroups = [
    {
        title: 'Input / Context Limits',
        fields: [
            ['free_max_words', 'Free input words'],
            ['plus_max_words', 'Plus input words'],
            ['pro_max_words', 'Pro input words']
        ]
    },
    {
        title: 'Output Token Limits',
        fields: [
            ['free_max_tokens', 'Free output tokens'],
            ['plus_max_tokens', 'Plus output tokens'],
            ['pro_max_tokens', 'Pro output tokens'],
            ['reasoning_max_tokens', 'Reasoning output tokens (all tiers, at least the tier limit)']
        ]
    },
    {
        title: 'Consensus Limits',
        fields: [
            ['consensus_max_tokens', 'Consensus output tokens'],
            ['differences_max_tokens', 'Differences output tokens'],
            ['coverage_max_tokens', 'Coverage output tokens']
        ]
    },
    {
        title: 'Consensus Watch Limits',
        fields: [
            ['watch_free_active_limit', 'Free active watches'],
            ['watch_plus_active_limit', 'Plus active watches'],
            ['watch_pro_active_limit', 'Pro active watches'],
            ['watch_max_runs_per_day', 'Global runs per day'],
            ['watch_probe_max_per_day', 'Evidence probes per day (0 = off)'],
            ['watch_daily_interval_requires_pro', 'Daily interval Pro-only (1 = yes, 0 = Free too)'],
            ['watch_plus_daily_interval_allowed', 'Plus may use the daily interval (1 = yes)']
        ]
    },
    {
        title: 'Share Index Quality Filter',
        fields: [
            ['share_min_consensus_chars', 'Min consensus characters'],
            ['share_min_sources', 'Min sources'],
            ['share_min_models', 'Min models consulted'],
            ['share_question_min_chars', 'Min question characters'],
            ['share_question_max_chars', 'Max question characters']
        ]
    }
];
let globalModelsData = {};

// ==============================
// Tabs
// ==============================
const TAB_IDS = ['models', 'consensus', 'configuration', 'limits', 'accounts', 'api', 'shares', 'watches', 'topics', 'seo'];
function activateTab(tabId) {
    if (!TAB_IDS.includes(tabId)) tabId = 'models';
    if (tabId !== 'api') clearIssuedApiKey();
    TAB_IDS.forEach(id => {
        document.getElementById(`tab-${id}`).hidden = id !== tabId;
        const btn = document.querySelector(`.admin-tabs button[data-tab="${id}"]`);
        btn.classList.toggle('active', id === tabId);
        btn.setAttribute('aria-selected', id === tabId ? 'true' : 'false');
    });
    document.getElementById('adminSavebar').hidden = ['topics', 'accounts', 'configuration'].includes(tabId);
    history.replaceState(null, '', `#${tabId}`);
}

document.querySelectorAll('.admin-tabs button').forEach(btn => {
    btn.addEventListener('click', () => activateTab(btn.dataset.tab));
});
activateTab((location.hash || '').replace('#', ''));

// ==============================
// Dirty-Tracking
// ==============================
function markDirty(event) {
    if (event?.target?.closest?.('#agentBudgetForm')) return;
    document.getElementById('adminSavebar').classList.add('is-dirty');
}
function clearDirty() {
    document.getElementById('adminSavebar').classList.remove('is-dirty');
}
// Alle Eingaben in den Konfig-Tabs (nicht Shares) markieren als dirty.
['tab-models', 'tab-consensus', 'tab-limits'].forEach(id => {
    const el = document.getElementById(id);
    el.addEventListener('change', markDirty);
    el.addEventListener('input', markDirty);
});
window.addEventListener('beforeunload', (event) => {
    if (!document.getElementById('adminSavebar').classList.contains('is-dirty')) return;
    event.preventDefault();
    event.returnValue = '';
});
// Aenderungen an den Provider-Listen in die abhaengigen Dropdowns
// (Judges, Consensus-Add) spiegeln.
document.getElementById('tab-models').addEventListener('change', () => {
    renderJudgeSelects();
    renderSourceVerificationSelect();
    renderConsensusAddSelect();
    renderPresetModels();
    renderWatchModelConfig();
});

// ==============================
// Meta-Helfer (Alias-Aufloesung, server-erzwungene Modelle)
// ==============================
// Der Server liefert die Metadaten unter '_meta'; ein Provider heisst 'meta'.
function meta() { return globalModelsData._meta || {}; }
function providerLabel(provider) { return (meta().provider_labels || {})[provider] || provider; }
function dependencyReasons(provider, model) {
    return ((((meta().dependencies || {})[provider] || {})[model]) || []);
}
function labelFor(model) { return (meta().labels || {})[model] || ''; }
// Leer, solange der Server keine Auskunft geben konnte. Dann wird nichts
// behauptet, statt faelschlich "laeuft" oder "laeuft nicht" anzuzeigen.
function providerCredentials() { return meta().provider_credentials || {}; }
// Virtuelle IDs senden ein anderes API-Modell (z. B.
// grok-4.3-no-reasoning -> grok-4.3). Sichtbar machen, sonst sieht man
// zwei fast gleich aussehende Eintraege ohne erkennbaren Unterschied.
function apiModelFor(model) { return (meta().api_models || {})[model] || ''; }
function optionTextFor(model) {
    let text = labelFor(model) || model;
    if (text !== model) text += ` (${model})`;
    const apiModel = apiModelFor(model);
    if (apiModel) text += ` → ${apiModel}`;
    return text;
}
function consensusDescription(value) {
    const alias = (meta().aliases || {})[value];
    if (alias) return `alias → ${alias.provider} · ${alias.label} (${alias.model})`;
    const provider = providers.find(p => (globalModelsData[p] || []).includes(value));
    const label = labelFor(value);
    if (provider) return `${provider}${label && label !== value ? ' · ' + label : ''}`;
    return label && label !== value ? label : '';
}
function chip(kind, text, title) {
    const span = document.createElement('span');
    span.className = 'admin-chip' + (kind ? ` ${kind}` : '');
    span.textContent = text;
    if (title) span.title = title;
    return span;
}

function reasoningText(entry) {
    const value = entry && entry.reasoning;
    if (!value) return 'provider default';
    if (value.effort) return `effort: ${value.effort}`;
    if (value.enabled === false) return 'reasoning disabled';
    if (value.enabled === true) return 'reasoning enabled';
    return Object.entries(value).map(([key, setting]) => `${key}: ${setting}`).join(', ');
}

function renderReasoningOverview() {
    renderReasoningControls();
    const policy = meta().reasoning || {};
    const flowContainer = document.getElementById('reasoningFlowOverview');
    const modelContainer = document.getElementById('reasoningModelOverview');
    if (!flowContainer || !modelContainer) return;

    flowContainer.innerHTML = '';
    (policy.flows || []).forEach(flow => {
        const card = document.createElement('div');
        card.className = 'reasoning-flow-card';
        const name = document.createElement('strong');
        name.textContent = flow.name || '';
        const setting = document.createElement('span');
        setting.className = 'reasoning-flow-setting';
        setting.textContent = flow.setting || '';
        const detail = document.createElement('small');
        detail.textContent = flow.detail || '';
        const code = document.createElement('code');
        code.textContent = flow.code || '';
        card.append(name, setting, detail, code);
        flowContainer.appendChild(card);
    });

    modelContainer.innerHTML = '';
    const header = document.createElement('div');
    header.className = 'reasoning-model-row reasoning-model-head';
    ['Family', 'Request path / model', 'Effective setting', 'Source / API model'].forEach(text => {
        const cell = document.createElement('span');
        cell.textContent = text;
        header.appendChild(cell);
    });
    modelContainer.appendChild(header);

    function appendRow(provider, scope, entry) {
        if (!entry || !entry.model) return;
        const row = document.createElement('div');
        row.className = 'reasoning-model-row';
        const family = document.createElement('span');
        family.textContent = providerLabel(provider);
        const model = document.createElement('span');
        const shownLabel = entry.label && entry.label !== entry.model ? entry.label : entry.model;
        model.textContent = `${scope} · ${shownLabel}`;
        model.title = entry.model;
        const setting = document.createElement('code');
        setting.textContent = reasoningText(entry);
        const source = document.createElement('span');
        const apiSuffix = entry.api_model && entry.api_model !== entry.model
            ? ` · API: ${entry.api_model}`
            : '';
        source.textContent = `${entry.source || 'unknown'}${apiSuffix}`;
        row.append(family, model, setting, source);
        modelContainer.appendChild(row);
    }

    providers.forEach(provider => {
        const answers = (policy.model_answers || {})[provider] || {};
        (globalModelsData[provider] || []).forEach(model => {
            appendRow(provider, 'Answer', answers[model]);
        });
        const judgePolicy = (policy.judges || {})[provider] || {};
        appendRow(provider, 'Standard judge', judgePolicy.standard);
        appendRow(provider, 'Pro judge', judgePolicy.pro);
        appendRow(provider, 'Chat memory', (policy.chat_memory || {})[provider]);
    });
}

function renderReasoningControls() {
    const container = document.getElementById('reasoningControls');
    const profile = document.getElementById('reasoningProfile');
    const scope = document.getElementById('reasoningScope');
    if (!container || !profile || !scope) return;
    const draft = globalModelsData.reasoning_policy || { profile: 'existing', models: {} };
    globalModelsData.reasoning_policy = draft;
    profile.value = draft.profile;
    profile.onchange = () => {
        draft.profile = profile.value;
        markDirty();
        renderReasoningControls();
    };
    scope.onchange = (event) => {
        event.stopPropagation();
        renderReasoningControls();
    };
    const showProtected = document.getElementById('reasoningShowProtected');
    showProtected.onchange = (event) => {
        event.stopPropagation();
        renderReasoningControls();
    };
    showProtected.oninput = event => event.stopPropagation();
    scope.oninput = event => event.stopPropagation();
    container.replaceChildren();
    const table = document.createElement('table');
    table.className = 'reasoning-budget-table';
    const head = table.createTHead().insertRow();
    ['Model / usage', 'Policy', 'Preview for selected request type', 'Why / protection'].forEach(text => {
        const th = document.createElement('th');
        th.scope = 'col';
        th.textContent = text;
        head.appendChild(th);
    });
    const body = table.createTBody();
    let changed = 0;
    let exceptions = 0;
    let protectedModels = 0;
    const controls = ((meta().reasoning || {}).controls || [])
        .filter(control => control.previews?.existing && scope.value in control.previews.existing);
    controls.forEach(control => {
        const override = draft.models[control.model];
        const choice = override || draft.profile;
        const preview = control.previews[choice][scope.value];
        const original = control.previews.existing[scope.value];
        const differs = JSON.stringify(preview) !== JSON.stringify(original);
        if (differs) changed += 1;
        if (override) exceptions += 1;
        if (!control.supported) protectedModels += 1;
        if (!control.supported && !showProtected.checked) return;
        const row = body.insertRow();
        const modelCell = row.insertCell();
        const name = document.createElement('strong');
        name.textContent = control.label;
        name.title = control.model;
        const usage = document.createElement('small');
        const reasons = dependencyReasons(control.provider, control.model);
        usage.textContent = `${providerLabel(control.provider)} · ${reasons.length ? reasons.join(', ') : 'Available in picker'}`;
        modelCell.append(name, usage);
        const policyCell = row.insertCell();
        if (control.supported) {
            const select = document.createElement('select');
            select.dataset.reasoningModel = control.model;
            select.setAttribute('aria-label', `Reasoning policy for ${control.label}`);
            [['', 'Follow default'], ['economy', 'Always use savings'], ['existing', 'Keep existing · quality exception']].forEach(([value, label]) => {
                select.add(new Option(label, value));
            });
            select.value = override || '';
            select.onchange = () => {
                if (select.value) draft.models[control.model] = select.value;
                else delete draft.models[control.model];
                markDirty();
                renderReasoningControls();
                Array.from(container.querySelectorAll('select'))
                    .find(el => el.dataset.reasoningModel === control.model)?.focus();
            };
            policyCell.appendChild(select);
        } else {
            policyCell.textContent = 'Protected / unchanged';
        }
        const valueCell = row.insertCell();
        valueCell.textContent = reasoningText({ reasoning: preview });
        if (differs) {
            const before = document.createElement('small');
            before.textContent = `Previously: ${reasoningText({ reasoning: original })}`;
            valueCell.appendChild(before);
            valueCell.className = 'reasoning-budget-changed';
        }
        row.insertCell().textContent = control.note;
    });
    container.appendChild(table);
    document.getElementById('reasoningSummary').textContent = `${changed} of ${controls.length} models changed vs. original behavior for this request type · ${exceptions} explicit exceptions · ${protectedModels} models protected / unchanged. Low is an effort setting, not a hard token or euro limit.`;
}

function renderWatchModelConfig() {
    const container = document.getElementById('watchModelConfig');
    if (!container) return;
    const currentModels = { free: {}, pro: {} };
    container.querySelectorAll('[data-watch-tier][data-provider]').forEach(select => {
        currentModels[select.dataset.watchTier][select.dataset.provider] = select.value;
    });
    const currentConsensus = {};
    container.querySelectorAll('[data-watch-consensus-tier]').forEach(select => {
        currentConsensus[select.dataset.watchConsensusTier] = select.value;
    });
    container.innerHTML = '';
    ['Provider', 'Free / Plus Watch', 'Pro Watch'].forEach(text => {
        const head = document.createElement('div');
        head.className = 'watch-model-head';
        head.textContent = text;
        container.appendChild(head);
    });
    const premium = new Set(globalModelsData.premium || []);
    const savedModels = globalModelsData.watch_models || {};
    const configured = {
        free: { ...(savedModels.free || {}), ...currentModels.free },
        pro: { ...(savedModels.pro || {}), ...currentModels.pro },
    };
    providers.forEach(provider => {
        const label = document.createElement('div');
        label.className = 'watch-model-provider';
        label.textContent = providerLabel(provider);
        container.appendChild(label);
        ['free', 'pro'].forEach(tier => {
            const select = document.createElement('select');
            select.className = 'watch-model-select';
            select.dataset.watchTier = tier;
            select.dataset.provider = provider;
            const disabled = document.createElement('option');
            disabled.value = '';
            disabled.textContent = 'Disabled';
            select.appendChild(disabled);
            (globalModelsData[provider] || []).forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = optionTextFor(model);
                // Free-Watches duerfen keine Premium-Modelle fahren.
                // Die Eintraege bleiben trotzdem sichtbar, damit die
                // Liste vollstaendig ist und der Grund erkennbar wird.
                if (tier === 'free' && premium.has(model)) {
                    option.disabled = true;
                    option.textContent += ' — Pro only';
                }
                select.appendChild(option);
            });
            select.value = ((configured[tier] || {})[provider]) || '';
            select.addEventListener('change', markDirty);
            container.appendChild(select);
        });
    });

    const consensusLabel = document.createElement('div');
    consensusLabel.className = 'watch-model-provider';
    consensusLabel.textContent = 'Consensus engine';
    container.appendChild(consensusLabel);
    const configuredConsensus = {
        ...(globalModelsData.watch_consensus_models || {}),
        ...currentConsensus,
    };
    const consensusModels = consensusListValues();
    ['free', 'pro'].forEach(tier => {
        const select = document.createElement('select');
        select.className = 'watch-model-select';
        select.dataset.watchConsensusTier = tier;
        consensusModels.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            const description = consensusDescription(model);
            if (description) option.textContent += ` — ${description}`;
            if (tier === 'free' && isLockedConsensusModel(model)) {
                option.disabled = true;
                option.textContent += ' — Pro only';
            }
            select.appendChild(option);
        });
        select.value = configuredConsensus[tier] || '';
        select.addEventListener('change', markDirty);
        container.appendChild(select);
    });

    renderWatchEffectiveRun(container, configured, premium);
}

// Ein Filter, der beim Lauf greift, muss dort sichtbar sein, wo man die
// Auswahl trifft. Sonst steht in der Konfiguration eine Modellzahl und im Lauf
// eine andere -- ohne dass irgendwo steht, welcher Provider warum fehlt.
function watchTierOutcome(configured, premium, tier) {
    const credentials = providerCredentials();
    const running = [];
    const skipped = [];
    providers.forEach(provider => {
        const model = (configured[tier] || {})[provider];
        if (!model) return;
        if (tier === 'free' && premium.has(model)) {
            skipped.push({ provider, model, reason: 'Pro only in the Free tier' });
            return;
        }
        if (credentials[provider] === false) {
            skipped.push({ provider, model, reason: 'no server credential' });
            return;
        }
        running.push({ provider, model });
    });
    return { running, skipped };
}

function renderWatchEffectiveRun(container, configured, premium) {
    const label = document.createElement('div');
    label.className = 'watch-model-provider';
    label.textContent = 'Actually runs';
    container.appendChild(label);
    ['free', 'pro'].forEach(tier => {
        const cell = document.createElement('div');
        cell.className = 'watch-effective-run';
        const outcome = watchTierOutcome(configured, premium, tier);
        const summary = document.createElement('div');
        summary.className = 'watch-effective-summary';
        summary.textContent = outcome.running.length
            ? `${outcome.running.length} providers: ` +
              outcome.running.map(item => item.provider).join(', ')
            : 'No provider left';
        cell.appendChild(summary);
        if (outcome.running.length < 2) {
            cell.appendChild(chip(
                'warn',
                'Needs at least 2',
                'A run with fewer than two answers cannot be compared.',
            ));
        }
        outcome.skipped.forEach(item => {
            cell.appendChild(chip(
                'warn',
                `${item.provider} skipped`,
                `${item.model} is configured but will not run: ${item.reason}.`,
            ));
        });
        container.appendChild(cell);
    });
}

function currentPresetModels() {
    const result = {};
    document.querySelectorAll('[data-preset-id]').forEach(select => {
        const presetId = select.dataset.presetId;
        if (!result[presetId]) result[presetId] = { answers: {} };
        if (select.dataset.presetSlot === 'consensus') {
            if (select.value) result[presetId].consensus = select.value;
            return;
        }
        if (select.dataset.presetAnswerIndex === undefined || !select.value) return;
        try {
            const [provider, model] = JSON.parse(select.value);
            if (provider && model) result[presetId].answers[provider] = model;
        } catch (_) {}
    });
    return result;
}

function isLockedConsensusModel(model) {
    const alias = (meta().aliases || {})[model];
    if (alias && model.endsWith('-Pro')) return true;
    return (globalModelsData.premium || []).includes(model);
}

function appendPresetOption(select, value, label, locked, showValue = true) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label || value;
    if (showValue && option.textContent !== value) option.textContent += ` (${value})`;
    const apiModel = showValue ? apiModelFor(value) : '';
    if (apiModel) option.textContent += ` → ${apiModel}`;
    // Daily/Balanced sind Free-faehig und duerfen keine Premium-Modelle
    // setzen. Sichtbar lassen statt ausblenden: sonst wirkt die Liste
    // unvollstaendig, ohne dass der Grund erkennbar waere.
    if (locked) {
        option.disabled = true;
        option.textContent += ' — Pro only';
    }
    select.appendChild(option);
}

function renderPresetModels() {
    const container = document.getElementById('presetModelsContainer');
    if (!container) return;
    const chosenNow = currentPresetModels();
    const saved = globalModelsData.preset_models || {};
    const premium = new Set(globalModelsData.premium || []);
    container.innerHTML = '';

    (meta().preset_definitions || []).forEach(definition => {
        const configured = chosenNow[definition.id] || saved[definition.id] || {};
        const configuredAnswers = configured.answers || Object.fromEntries(
            providers.filter(provider => configured[provider]).map(provider => [provider, configured[provider]])
        );
        const answerEntries = Object.entries(configuredAnswers).slice(0, 6);
        const card = document.createElement('div');
        card.className = 'preset-model-card';
        const title = document.createElement('h4');
        title.textContent = definition.label;
        if (definition.pro_only) title.appendChild(chip('', 'Pro', 'This preset is available to Pro users only.'));
        card.appendChild(title);

        for (let index = 0; index < 6; index += 1) {
            const field = document.createElement('div');
            field.className = 'preset-model-field';
            const label = document.createElement('label');
            label.textContent = `Answer ${index + 1}`;
            const select = document.createElement('select');
            select.dataset.presetId = definition.id;
            select.dataset.presetAnswerIndex = String(index);
            select.setAttribute('aria-label', `${definition.label} answer ${index + 1} model`);
            providers.forEach(provider => {
                currentProviderModels(provider).forEach(model => {
                    appendPresetOption(
                        select,
                        JSON.stringify([provider, model]),
                        `${providerLabel(provider)} · ${labelFor(model)}`,
                        !definition.pro_only && premium.has(model),
                        false,
                    );
                });
            });
            const selected = answerEntries[index];
            select.value = selected ? JSON.stringify(selected) : '';
            select.addEventListener('change', markDirty);
            field.appendChild(label);
            field.appendChild(select);
            card.appendChild(field);
        }

        const consensusField = document.createElement('div');
        consensusField.className = 'preset-model-field';
        const consensusLabel = document.createElement('label');
        consensusLabel.textContent = 'Consensus';
        const consensusSelect = document.createElement('select');
        consensusSelect.dataset.presetId = definition.id;
        consensusSelect.dataset.presetSlot = 'consensus';
        consensusSelect.setAttribute('aria-label', `${definition.label} consensus model`);
        consensusListValues().forEach(model => {
            appendPresetOption(consensusSelect, model, consensusDescription(model),
                !definition.pro_only && isLockedConsensusModel(model));
        });
        consensusSelect.value = configured.consensus || '';
        consensusSelect.addEventListener('change', markDirty);
        consensusField.append(consensusLabel, consensusSelect);
        card.appendChild(consensusField);
        container.appendChild(card);
    });
}

// ==============================
// Rendering
// ==============================
function renderUI() {
    renderLimits();
    renderReasoningOverview();

    const container = document.getElementById('providersContainer');
    container.innerHTML = '';

    const premiumSet = new Set(globalModelsData.premium || []);
    const consensusSet = new Set(globalModelsData.consensus || []);
    const defaults = globalModelsData.defaults || {};

    providers.forEach(p => {
        const section = document.createElement('div');
        section.className = 'admin-section';

        const title = document.createElement('h3');
        title.textContent = providerLabel(p);
        section.appendChild(title);

        const listContainer = document.createElement('div');
        listContainer.id = `list-${p}`;

        const models = globalModelsData[p] || [];
        models.forEach(m => {
            const row = createModelRow(p, m, premiumSet.has(m), consensusSet.has(m), defaults[p] === m);
            listContainer.appendChild(row);
        });

        section.appendChild(listContainer);

        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'add-btn';
        addBtn.textContent = '+ Add Model';
        addBtn.onclick = () => {
            listContainer.appendChild(createModelRow(p, '', false, false, false));
            markDirty();
        };
        section.appendChild(addBtn);

        container.appendChild(section);
    });

    // Nach den Provider-Listen rendern, damit Add-Dropdown und
    // Alias-Aufloesung den aktuellen DOM-Stand sehen.
    renderConsensusModels();
    renderPresetModels();
    renderJudgeSelects();
    renderSourceVerificationSelect(true);
    renderWatchModelConfig();
}

function createModelRow(provider, modelName, isPremium, isConsensus, isDefault) {
    const row = document.createElement('div');
    row.className = 'model-row';

    const dependencies = modelName ? dependencyReasons(provider, modelName) : [];

    const upBtn = document.createElement('button');
    upBtn.type = 'button';
    upBtn.className = 'icon-btn';
    upBtn.textContent = '↑';
    upBtn.title = 'Move up (picker order)';
    upBtn.onclick = () => { moveRow(row, -1); markDirty(); };

    const downBtn = document.createElement('button');
    downBtn.type = 'button';
    downBtn.className = 'icon-btn';
    downBtn.textContent = '↓';
    downBtn.title = 'Move down (picker order)';
    downBtn.onclick = () => { moveRow(row, 1); markDirty(); };

    const input = document.createElement('input');
    input.type = 'text';
    input.value = modelName;
    input.placeholder = 'Model identifier (e.g. gpt-5.5)';
    const modelLabel = modelName ? labelFor(modelName) : '';
    if (modelLabel && modelLabel !== modelName) {
        input.title = (input.title ? input.title + ' · ' : '') + `Shown as “${modelLabel}”`;
    }
    input.addEventListener('focus', () => {
        row.dataset.previousModelName = input.value.trim();
    });
    input.addEventListener('change', () => {
        if (!consensusCheckbox.checked) return;
        const previous = row.dataset.previousModelName || '';
        if (previous && previous !== input.value.trim()) {
            removeConsensusListValue(previous);
        }
        addConsensusListValue(input.value.trim());
        row.dataset.previousModelName = input.value.trim();
    });

    const flags = document.createElement('div');
    flags.className = 'model-flags';

    const reasoningEntry = (((meta().reasoning || {}).model_answers || {})[provider] || {})[modelName];
    if (reasoningEntry && reasoningEntry.reasoning) {
        flags.appendChild(chip(
            'reasoning',
            reasoningText(reasoningEntry),
            `Effective answer request · ${reasoningEntry.source}`
        ));
    }

    if (dependencies.length) {
        flags.appendChild(chip(
            'required',
            'In use',
            `Referenced by: ${dependencies.join(', ')}. You can remove it after updating those selections.`
        ));
    }

    const defaultLabel = document.createElement('label');
    defaultLabel.title = 'Free default for this provider (shown before a manual pick). Must not be a Premium model.';
    const defaultRadio = document.createElement('input');
    defaultRadio.type = 'radio';
    defaultRadio.className = 'default-radio';
    defaultRadio.name = `default-${provider}`;
    defaultRadio.checked = !!isDefault;
    defaultLabel.appendChild(defaultRadio);
    defaultLabel.appendChild(document.createTextNode(' Default'));

    const premiumLabel = document.createElement('label');
    const premiumCheckbox = document.createElement('input');
    premiumCheckbox.type = 'checkbox';
    premiumCheckbox.className = 'premium-checkbox';
    premiumCheckbox.checked = isPremium;
    premiumLabel.appendChild(premiumCheckbox);
    premiumLabel.appendChild(document.createTextNode(' Premium'));

    const consensusLabel = document.createElement('label');
    consensusLabel.title = 'Offer this model in the Consensus picker (ordered in the Consensus tab).';
    const consensusCheckbox = document.createElement('input');
    consensusCheckbox.type = 'checkbox';
    consensusCheckbox.className = 'consensus-checkbox';
    consensusCheckbox.checked = isConsensus;
    consensusCheckbox.addEventListener('change', () => {
        if (consensusCheckbox.checked) {
            addConsensusListValue(input.value.trim());
        } else {
            removeConsensusListValue(input.value.trim());
        }
    });
    consensusLabel.appendChild(consensusCheckbox);
    consensusLabel.appendChild(document.createTextNode(' Consensus'));

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'icon-btn danger';
    removeBtn.textContent = '✕';
    removeBtn.title = dependencies.length
        ? `Remove model; then update: ${dependencies.join(', ')}`
        : 'Remove model';
    removeBtn.disabled = false;
    removeBtn.onclick = () => {
        if (consensusCheckbox.checked) removeConsensusListValue(input.value.trim());
        row.remove();
        renderJudgeSelects();
        renderConsensusAddSelect();
        renderPresetModels();
        renderWatchModelConfig();
        markDirty();
    };

    row.appendChild(upBtn);
    row.appendChild(downBtn);
    row.appendChild(input);
    row.appendChild(flags);
    row.appendChild(defaultLabel);
    row.appendChild(premiumLabel);
    row.appendChild(consensusLabel);
    row.appendChild(removeBtn);

    return row;
}

function moveRow(row, direction) {
    if (!row) return;
    if (direction < 0 && row.previousElementSibling) {
        row.parentNode.insertBefore(row, row.previousElementSibling);
    } else if (direction > 0 && row.nextElementSibling) {
        row.parentNode.insertBefore(row.nextElementSibling, row);
    }
}

// ==============================
// Consensus
// ==============================
function renderConsensusModels() {
    const listContainer = document.getElementById('consensusModelsList');
    listContainer.innerHTML = '';
    const models = globalModelsData.consensus || [];
    models.forEach(model => {
        listContainer.appendChild(createConsensusModelRow(model));
    });
    renderConsensusAddSelect();
}

function consensusListValues() {
    return Array.from(document.querySelectorAll('#consensusModelsList .consensus-row'))
        .map(row => (row.dataset.value || '').trim())
        .filter(Boolean);
}

function createConsensusModelRow(modelName) {
    const row = document.createElement('div');
    row.className = 'consensus-row';
    row.dataset.value = modelName;

    const forcedFirst = modelName === meta().consensus_forced_first;

    const upBtn = document.createElement('button');
    upBtn.type = 'button';
    upBtn.className = 'icon-btn';
    upBtn.textContent = '↑';
    upBtn.title = 'Move up (picker order)';
    upBtn.onclick = () => { moveConsensusRow(row, -1); markDirty(); };

    const downBtn = document.createElement('button');
    downBtn.type = 'button';
    downBtn.className = 'icon-btn';
    downBtn.textContent = '↓';
    downBtn.title = 'Move down (picker order)';
    downBtn.onclick = () => { moveConsensusRow(row, 1); markDirty(); };

    const value = document.createElement('span');
    value.className = 'consensus-value';
    value.textContent = modelName;

    const desc = document.createElement('span');
    desc.className = 'consensus-desc';
    desc.textContent = consensusDescription(modelName);
    desc.title = desc.textContent;

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'icon-btn danger';
    removeBtn.textContent = '✕';
    if (forcedFirst) {
        removeBtn.disabled = true;
        removeBtn.title = 'Server-enforced: this engine is always available (re-inserted on save).';
    } else {
        removeBtn.title = 'Remove from Consensus picker';
    }
    removeBtn.onclick = () => {
        setProviderConsensusChecked(modelName, false);
        row.remove();
        renderConsensusAddSelect();
        markDirty();
    };

    row.appendChild(upBtn);
    row.appendChild(downBtn);
    row.appendChild(value);
    row.appendChild(desc);
    if (forcedFirst) row.appendChild(chip('required', 'Required', 'Always kept in the list by the server.'));
    row.appendChild(removeBtn);

    return row;
}

function moveConsensusRow(row, direction) {
    moveRow(row, direction);
}

function findProviderConsensusCheckbox(modelName) {
    if (!modelName) return null;
    for (const row of document.querySelectorAll('#providersContainer .model-row')) {
        const input = row.querySelector('input[type="text"]');
        if (input && input.value.trim() === modelName) {
            return row.querySelector('.consensus-checkbox');
        }
    }
    return null;
}

function setProviderConsensusChecked(modelName, checked) {
    const checkbox = findProviderConsensusCheckbox(modelName);
    if (checkbox) checkbox.checked = checked;
}

function addConsensusListValue(modelName) {
    const value = (modelName || '').trim();
    if (!value || consensusListValues().includes(value)) return;
    document.getElementById('consensusModelsList').appendChild(createConsensusModelRow(value));
    setProviderConsensusChecked(value, true);
    renderConsensusAddSelect();
    renderPresetModels();
    renderWatchModelConfig();
}

function removeConsensusListValue(modelName) {
    const value = (modelName || '').trim();
    if (!value) return;
    document.querySelectorAll('#consensusModelsList .consensus-row').forEach(row => {
        if ((row.dataset.value || '').trim() === value) row.remove();
    });
    setProviderConsensusChecked(value, false);
    renderConsensusAddSelect();
    renderPresetModels();
    renderWatchModelConfig();
}

// Kandidaten fuer das Add-Dropdown: Aliase + direkte Modell-IDs aus den
// Provider-Listen, die noch nicht in der Consensus-Liste stehen.
function renderConsensusAddSelect() {
    const select = document.getElementById('consensusAddSelect');
    if (!select) return;
    const existing = new Set(consensusListValues());
    select.innerHTML = '';

    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Add engine…';
    select.appendChild(placeholder);

    const aliasGroup = document.createElement('optgroup');
    aliasGroup.label = 'Aliases (auto-track provider defaults)';
    Object.keys(meta().aliases || {}).forEach(alias => {
        if (existing.has(alias)) return;
        const opt = document.createElement('option');
        opt.value = alias;
        opt.textContent = `${alias} — ${consensusDescription(alias)}`;
        aliasGroup.appendChild(opt);
    });
    if (aliasGroup.children.length) select.appendChild(aliasGroup);

    providers.forEach(p => {
        const group = document.createElement('optgroup');
        group.label = providerLabel(p);
        (currentProviderModels(p) || []).forEach(model => {
            if (!model || existing.has(model)) return;
            const opt = document.createElement('option');
            opt.value = model;
            const label = labelFor(model);
            opt.textContent = label && label !== model ? `${model} — ${label}` : model;
            group.appendChild(opt);
        });
        if (group.children.length) select.appendChild(group);
    });
}

// Provider-Modelle aus dem aktuellen DOM (inkl. ungespeicherter Zeilen).
function currentProviderModels(provider) {
    const listContainer = document.getElementById(`list-${provider}`);
    if (!listContainer) return globalModelsData[provider] || [];
    return Array.from(listContainer.querySelectorAll('.model-row input[type="text"]'))
        .map(input => input.value.trim())
        .filter(Boolean);
}

// ==============================
// Differences Judges
// ==============================
function currentSourceVerificationModel() {
    return document.getElementById('sourceVerificationModelSelect')?.value
        || globalModelsData.source_verification_model
        || meta().source_verification_default
        || 'google/gemini-3.5-flash-lite';
}

function renderSourceVerificationSelect(fromSaved = false) {
    const select = document.getElementById('sourceVerificationModelSelect');
    if (!select) return;
    const chosen = fromSaved
        ? globalModelsData.source_verification_model || meta().source_verification_default || 'google/gemini-3.5-flash-lite'
        : currentSourceVerificationModel();
    const options = Array.isArray(meta().source_verification_models) ? meta().source_verification_models : [];
    const rows = options.filter(row => row && typeof row.id === 'string');
    // Never silently change an unsaved selection while another setting changes.
    if (!rows.some(row => row.id === chosen)) rows.unshift({id: chosen, label: chosen});
    select.replaceChildren();
    rows.forEach(row => {
        const option = document.createElement('option');
        option.value = row.id;
        option.textContent = row.label && row.label !== row.id ? `${row.label} (${row.id})` : row.id;
        if (row.id === meta().source_verification_default) option.textContent += ' — default';
        select.appendChild(option);
    });
    select.value = chosen;
    renderSourceVerificationFallbackSelect(fromSaved);
}

function currentSourceVerificationFallbackModel() {
    const select = document.getElementById('sourceVerificationFallbackModelSelect');
    return select?.options.length ? select.value : globalModelsData.source_verification_fallback_model || '';
}

function renderSourceVerificationFallbackSelect(fromSaved = false) {
    const select = document.getElementById('sourceVerificationFallbackModelSelect');
    if (!select) return;
    const chosen = fromSaved ? globalModelsData.source_verification_fallback_model || ''
        : currentSourceVerificationFallbackModel();
    const configured = Array.isArray(meta().source_verification_models) ? meta().source_verification_models : [];
    const rows = [{id: '', label: 'Disabled'}, ...configured.filter(row => row && typeof row.id === 'string' && row.id)];
    if (!rows.some(row => row.id === chosen)) rows.push({id: chosen, label: chosen});
    select.replaceChildren();
    rows.forEach(row => {
        const option = document.createElement('option');
        option.value = row.id;
        option.textContent = row.label && row.label !== row.id ? `${row.label}${row.id ? ` (${row.id})` : ''}` : row.id;
        option.disabled = Boolean(row.id) && row.id === currentSourceVerificationModel();
        select.appendChild(option);
    });
    select.value = chosen;
}

function currentJudgeModels() {
    const result = {};
    document.querySelectorAll('[data-judge-provider]').forEach(select => {
        if (select.value) result[select.dataset.judgeProvider] = select.value;
    });
    return result;
}

function currentProJudgeModels() {
    const result = {};
    document.querySelectorAll('[data-projudge-provider]').forEach(select => {
        if (select.value) result[select.dataset.projudgeProvider] = select.value;
    });
    return result;
}

function currentChatMemoryModels() {
    const result = {};
    document.querySelectorAll('[data-chatmemory-provider]').forEach(select => {
        if (select.value) result[select.dataset.chatmemoryProvider] = select.value;
    });
    return result;
}

function currentJudgeFamilies() {
    const result = {};
    document.querySelectorAll('[data-judgefam-engine]').forEach(select => {
        if (select.value) result[select.dataset.judgefamEngine] = select.value;
    });
    return result;
}

function buildJudgeModelSelect(provider, chosen, defaultModel, datasetKey, ariaText) {
    const select = document.createElement('select');
    select.dataset[datasetKey] = provider;
    select.setAttribute('aria-label', ariaText);
    currentProviderModels(provider).forEach(model => {
        const opt = document.createElement('option');
        opt.value = model;
        const lbl = labelFor(model);
        opt.textContent = lbl && lbl !== model ? `${model} — ${lbl}` : model;
        const apiModel = apiModelFor(model);
        if (apiModel) opt.textContent += ` → ${apiModel}`;
        if (model === defaultModel) opt.textContent += ' (server default)';
        if (model === chosen) opt.selected = true;
        select.appendChild(opt);
    });
    return select;
}

function renderJudgeSelects() {
    const container = document.getElementById('judgeModelsContainer');
    if (!container) return;
    // Ungespeicherte Auswahl bei Re-Renders erhalten.
    const chosenNow = currentJudgeModels();
    const chosenProNow = currentProJudgeModels();
    container.innerHTML = '';
    const judgeDefaults = meta().judge_defaults || {};
    const proDefaults = meta().judge_pro_defaults || {};
    const saved = globalModelsData.judge_models || {};
    const savedPro = globalModelsData.judge_models_pro || {};

    const head = document.createElement('div');
    head.className = 'judge-row judge-head';
    ['Family', 'Standard judge', 'Pro judge (reduced effort)'].forEach(text => {
        const cell = document.createElement('span');
        cell.textContent = text;
        head.appendChild(cell);
    });
    container.appendChild(head);

    providers.forEach(p => {
        const row = document.createElement('div');
        row.className = 'judge-row';

        const label = document.createElement('label');
        label.textContent = providerLabel(p);

        const chosen = chosenNow[p] || saved[p] || judgeDefaults[p] || '';
        const chosenPro = chosenProNow[p] || savedPro[p] || proDefaults[p] || '';

        row.appendChild(label);
        row.appendChild(buildJudgeModelSelect(
            p, chosen, judgeDefaults[p], 'judgeProvider', `Standard differences judge for ${p}`));
        row.appendChild(buildJudgeModelSelect(
            p, chosenPro, proDefaults[p], 'projudgeProvider', `Pro differences judge for ${p}`));
        container.appendChild(row);
    });

    renderJudgeFamilies();
    renderChatMemorySelects();
}

// Chat-Memory je Provider-Familie. Die Familie selbst waehlt der Nutzer
// mit der Consensus-Engine — hier steht nur, welches Modell dieser
// Familie die Memory laengerer Chats fortschreibt.
function renderChatMemorySelects() {
    const container = document.getElementById('chatMemoryModelsContainer');
    if (!container) return;
    const chosenNow = currentChatMemoryModels();
    container.innerHTML = '';
    const defaults = meta().chat_memory_defaults || {};
    const saved = globalModelsData.chat_memory_models || {};

    const head = document.createElement('div');
    head.className = 'judge-fam-row judge-head';
    ['Family', 'Chat memory model'].forEach(text => {
        const cell = document.createElement('span');
        cell.textContent = text;
        head.appendChild(cell);
    });
    container.appendChild(head);

    providers.forEach(p => {
        const row = document.createElement('div');
        row.className = 'judge-fam-row';

        const label = document.createElement('label');
        label.textContent = providerLabel(p);

        const chosen = chosenNow[p] || saved[p] || defaults[p] || '';
        row.appendChild(label);
        row.appendChild(buildJudgeModelSelect(
            p, chosen, defaults[p], 'chatmemoryProvider', `Chat memory model for ${p}`));
        container.appendChild(row);
    });
}

function renderJudgeFamilies() {
    const container = document.getElementById('judgeFamiliesContainer');
    if (!container) return;
    const chosenNow = currentJudgeFamilies();
    container.innerHTML = '';
    const saved = globalModelsData.judge_families || {};
    const priority = meta().judge_priority || [];

    providers.forEach(engine => {
        const row = document.createElement('div');
        row.className = 'judge-fam-row';

        const label = document.createElement('label');
        label.textContent = `${providerLabel(engine)} engine`;

        const select = document.createElement('select');
        select.dataset.judgefamEngine = engine;
        select.setAttribute('aria-label', `Judge family for ${engine} engines`);

        const autoOrder = priority.join(' → ');
        const autoOpt = document.createElement('option');
        autoOpt.value = '';
        autoOpt.textContent = `Auto — first available: ${autoOrder}`;
        select.appendChild(autoOpt);

        const chosen = chosenNow[engine] || saved[engine] || '';
        providers.forEach(judgeFamily => {
            const opt = document.createElement('option');
            opt.value = judgeFamily;
            opt.textContent = providerLabel(judgeFamily);
            if (judgeFamily === chosen) opt.selected = true;
            select.appendChild(opt);
        });

        row.appendChild(label);
        row.appendChild(select);
        container.appendChild(row);
    });
}

function renderLimits() {
    const container = document.getElementById('limitsContainer');
    container.innerHTML = '';
    const limits = globalModelsData.limits || {};

    limitGroups.forEach(group => {
        const section = document.createElement('div');
        section.className = 'admin-section';

        const title = document.createElement('h3');
        title.textContent = group.title;
        section.appendChild(title);

        group.fields.forEach(([key, labelText]) => {
            const row = document.createElement('div');
            row.className = 'limit-row';

            const label = document.createElement('label');
            label.htmlFor = `limit-${key}`;
            label.textContent = labelText;

            const input = document.createElement('input');
            input.type = 'number';
            input.min = '0';
            input.step = '1';
            input.id = `limit-${key}`;
            input.dataset.limitKey = key;
            input.value = Number.isFinite(Number(limits[key])) ? limits[key] : 0;

            row.appendChild(label);
            row.appendChild(input);
            section.appendChild(row);
        });

        container.appendChild(section);
    });

    const memory = globalModelsData.memory_edit || {};
    const section = document.createElement('div');
    section.className = 'admin-section';
    const title = document.createElement('h3');
    title.textContent = 'Edit Memory';
    section.appendChild(title);
    const hint = document.createElement('p');
    hint.className = 'section-hint';
    hint.textContent = 'Server-authoritative Luna patching, plan limits and persistent cost controls.';
    section.appendChild(hint);

    const enabledRow = document.createElement('div');
    enabledRow.className = 'limit-row';
    const enabledLabel = document.createElement('label');
    enabledLabel.htmlFor = 'memory-edit-enabled';
    enabledLabel.textContent = 'Feature enabled';
    const enabled = document.createElement('input');
    enabled.type = 'checkbox';
    enabled.id = 'memory-edit-enabled';
    enabled.dataset.memoryEditKey = 'memory_edit_enabled';
    enabled.checked = memory.memory_edit_enabled === true;
    enabledRow.append(enabledLabel, enabled);
    section.appendChild(enabledRow);

    const modelRow = document.createElement('div');
    modelRow.className = 'limit-row';
    const modelLabel = document.createElement('label');
    modelLabel.htmlFor = 'memory-edit-model';
    modelLabel.textContent = 'OpenAI model';
    const modelSelect = document.createElement('select');
    modelSelect.id = 'memory-edit-model';
    modelSelect.dataset.memoryEditKey = 'memory_edit_model';
    const memoryModels = [...(globalModelsData.openai || [])];
    if (memory.memory_edit_model && !memoryModels.includes(memory.memory_edit_model)) {
        memoryModels.unshift(memory.memory_edit_model);
    }
    memoryModels.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = labelFor(model);
        modelSelect.appendChild(option);
    });
    modelSelect.value = memory.memory_edit_model || '';
    modelRow.append(modelLabel, modelSelect);
    section.appendChild(modelRow);

    const fields = [
        ['memory_free_chars', 'Free Memory note characters'],
        ['memory_plus_chars', 'Plus Memory note characters'],
        ['memory_pro_chars', 'Pro Memory note characters'],
        ['memory_free_ai_edits_daily', 'Free AI edits / UTC day'],
        ['memory_plus_ai_edits_daily', 'Plus AI edits / UTC day'],
        ['memory_pro_ai_edits_daily', 'Pro AI edits / UTC day'],
        ['memory_ai_edits_per_minute', 'AI edits / minute'],
        ['memory_global_calls_daily', 'Global calls / UTC day'],
        ['memory_edit_input_chars', 'Correction input characters'],
        ['memory_edit_output_tokens', 'Patch output tokens'],
        ['memory_edit_timeout_seconds', 'Provider timeout seconds']
    ];
    fields.forEach(([key, labelText]) => {
        const row = document.createElement('div');
        row.className = 'limit-row';
        const label = document.createElement('label');
        label.htmlFor = `memory-edit-${key}`;
        label.textContent = labelText;
        const input = document.createElement('input');
        input.type = 'number';
        input.min = '0';
        input.step = '1';
        input.id = `memory-edit-${key}`;
        input.dataset.memoryEditKey = key;
        input.value = Number.isFinite(Number(memory[key])) ? memory[key] : 0;
        row.append(label, input);
        section.appendChild(row);
    });
    container.appendChild(section);
}

// ==============================
// Laden & Speichern
// ==============================
function setStatus(message, isError) {
    const el = document.getElementById('statusMessage');
    el.textContent = message || '';
    el.className = isError ? 'error' : 'success';
}

async function fetchModels(idToken) {
    try {
        const response = await fetch('/api/admin/models', {
            headers: { 'Authorization': `Bearer ${idToken}` }
        });
        if (!response.ok) {
            throw new Error('Failed to fetch models. Admin access required.');
        }
        globalModelsData = await response.json();
        providers = Array.isArray(meta().provider_keys)
            ? meta().provider_keys.slice()
            : [];
        renderUI();
        clearDirty();
    } catch (err) {
        setStatus(err.message, true);
    }
}

async function reloadModels() {
    const user = auth.currentUser;
    if (!user) return;
    setStatus('Reloading…', false);
    await fetchModels(await user.getIdToken());
    setStatus('', false);
}

async function saveModels() {
    const user = auth.currentUser;
    if (!user) return;
    const idToken = await user.getIdToken();

    const data = {
        // Compare-and-swap token: the server refuses the save with 409 if
        // another admin or process stored a newer configuration meanwhile.
        revision: Number.isInteger(globalModelsData.revision) ? globalModelsData.revision : 0,
        premium: [],
        reasoning_policy: globalModelsData.reasoning_policy || { profile: 'existing', models: {} },
        consensus: consensusListValues(),
        preset_models: currentPresetModels(),
        judge_models: currentJudgeModels(),
        judge_models_pro: currentProJudgeModels(),
        source_verification_model: currentSourceVerificationModel(),
        source_verification_fallback_model: currentSourceVerificationFallbackModel(),
        judge_families: currentJudgeFamilies(),
        chat_memory_models: currentChatMemoryModels(),
        watch_models: { free: {}, pro: {} },
        watch_consensus_models: { free: '', pro: '' },
        defaults: {},
        limits: {},
        memory_edit: {}
    };
    function addConsensusValue(modelName) {
        if (modelName && !data.consensus.includes(modelName)) {
            data.consensus.push(modelName);
        }
    }
    document.querySelectorAll('[data-limit-key]').forEach(input => {
        const value = parseInt(input.value, 10);
        data.limits[input.dataset.limitKey] = Number.isFinite(value) && value >= 0 ? value : 0;
    });
    document.querySelectorAll('[data-memory-edit-key]').forEach(input => {
        const key = input.dataset.memoryEditKey;
        if (input.type === 'checkbox') data.memory_edit[key] = input.checked;
        else if (input.tagName === 'SELECT') data.memory_edit[key] = input.value;
        else data.memory_edit[key] = Number.parseInt(input.value, 10);
    });

    providers.forEach(p => {
        data[p] = [];
        const listContainer = document.getElementById(`list-${p}`);
        const rows = listContainer.querySelectorAll('.model-row');
        rows.forEach(row => {
            const input = row.querySelector('input[type="text"]');
            const premiumCheckbox = row.querySelector('.premium-checkbox');
            const consensusCheckbox = row.querySelector('.consensus-checkbox');
            const defaultRadio = row.querySelector('.default-radio');
            const modelName = input.value.trim();

            if (modelName) {
                // Reihenfolge = DOM-Reihenfolge der Zeilen (per ↑/↓ sortierbar).
                data[p].push(modelName);
                if (premiumCheckbox.checked) {
                    data.premium.push(modelName);
                }
                if (consensusCheckbox.checked) {
                    addConsensusValue(modelName);
                }
                if (defaultRadio && defaultRadio.checked) {
                    data.defaults[p] = modelName;
                }
            }
        });
    });

    document.querySelectorAll('[data-watch-tier][data-provider]').forEach(select => {
        if (select.value) data.watch_models[select.dataset.watchTier][select.dataset.provider] = select.value;
    });
    document.querySelectorAll('[data-watch-consensus-tier]').forEach(select => {
        data.watch_consensus_models[select.dataset.watchConsensusTier] = select.value;
    });
    for (const tier of ['free', 'pro']) {
        if (Object.keys(data.watch_models[tier]).length < 2) {
            setStatus(`Select at least two ${tier} Watch models.`, true);
            return;
        }
        if (!data.watch_consensus_models[tier]) {
            setStatus(`Select a ${tier} Watch consensus engine.`, true);
            return;
        }
    }
    for (const definition of (meta().preset_definitions || [])) {
        const configured = data.preset_models[definition.id] || {};
        const answers = configured.answers || {};
        if (Object.keys(answers).length !== 6 || !configured.consensus) {
            setStatus(`${definition.label} must select six different model families and one consensus engine.`, true);
            return;
        }
    }

    try {
        const response = await fetch('/api/admin/models', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${idToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            setStatus('Configuration saved.', false);
            clearDirty();
            // Normalisierten Server-Stand nachladen (ensures/drops sichtbar machen).
            await fetchModels(idToken);
            setTimeout(() => setStatus('', false), 4000);
        } else {
            const resData = await response.json();
            if (response.status === 409) {
                throw new Error(resData.error || resData.detail
                    || 'The configuration was changed elsewhere. Reload before saving again.');
            }
            throw new Error(resData.error || resData.detail || 'Failed to update models');
        }
    } catch (err) {
        setStatus(err.message, true);
    }
}

document.getElementById('saveBtn').addEventListener('click', saveModels);
document.getElementById('reloadBtn').addEventListener('click', reloadModels);
document.getElementById('consensusAddBtn').addEventListener('click', () => {
    const select = document.getElementById('consensusAddSelect');
    if (select.value) {
        addConsensusListValue(select.value);
        markDirty();
    }
});

// === Shared Pages Moderation ===
let currentSharesFilter = 'reported';

function sharesStatus(message, isError) {
    const el = document.getElementById('sharesStatus');
    el.textContent = message || '';
    el.className = isError ? 'error' : 'success';
}

let loadedShares = [];
let sharesNextCursor = null;
let sharesRequestId = 0;

// Paged moderation list: the server filters and orders before limiting and
// says whether more rows exist, so nothing relevant hides behind a window.
async function loadShares(filter, { append = false } = {}) {
    const requestId = ++sharesRequestId;
    if (!append) {
        currentSharesFilter = filter;
        loadedShares = [];
        sharesNextCursor = null;
    }
    sharesStatus('Loading…', false);
    let data;
    const cursor = append && sharesNextCursor ? `&cursor=${encodeURIComponent(sharesNextCursor)}` : '';
    try {
        data = await shareAdminRequest('GET', `/api/admin/shares?filter=${filter}${cursor}`);
    } catch (err) {
        if (requestId === sharesRequestId) sharesStatus(err.message, true);
        return;
    }
    if (requestId !== sharesRequestId) return;
    loadedShares = loadedShares.concat(data.shares || []);
    sharesNextCursor = data.has_more ? data.next_cursor : null;
    sharesStatus(sharesNextCursor ? `${loadedShares.length} loaded · more available` : '', false);
    renderShares(loadedShares, data.site_url || '');
}

async function moderateShare(shareId, payload, confirmText) {
    if (confirmText && !confirm(confirmText)) return;
    try {
        await shareAdminRequest('POST', `/api/admin/shares/${encodeURIComponent(shareId)}/moderate`, payload);
        await loadShares(currentSharesFilter);
    } catch (err) {
        sharesStatus(err.message, true);
    }
}

async function deleteShare(shareId, question, statusFn = sharesStatus) {
    const label = question || shareId;
    if (!confirm(`Permanently delete "${label}"? The page, its Watch schedule, history, and followers will be removed immediately. This cannot be undone.`)) return;
    statusFn('Deleting page…', false);
    try {
        await shareAdminRequest('DELETE', `/api/admin/shares/${encodeURIComponent(shareId)}`);
        await Promise.all([
            loadShares(currentSharesFilter),
            loadPublisherWatches(),
            loadAdminWatches()
        ]);
    } catch (err) {
        statusFn(err.message, true);
    }
}

function renderShares(shares, siteUrl) {
    const container = document.getElementById('sharesContainer');
    container.innerHTML = '';
    if (!shares.length) {
        container.textContent = currentSharesFilter === 'reported'
            ? 'No reported shares.' : 'No shares found.';
        return;
    }
    shares.forEach(share => {
        const row = document.createElement('div');
        row.className = 'share-mod-row';

        const link = document.createElement('a');
        link.className = 'share-mod-question';
        link.textContent = share.question || '(untitled)';
        link.href = siteUrl + share.path;
        link.target = '_blank';
        link.rel = 'noopener';
        row.appendChild(link);

        if (share.needs_review) row.appendChild(badge('review', 'needs review'));
        if (share.index_requested) row.appendChild(badge('review', 'listing requested', 'The owner asked for this page to be indexed on Google.'));
        if (share.reports_count > 0) {
            const reasons = Object.entries(share.report_reasons || {})
                .map(([k, v]) => `${k}: ${v}`).join(', ');
            row.appendChild(badge('reported', `${share.reports_count} report(s)`, reasons));
        }
        row.appendChild(badge('', share.status));
        if (share.visibility === 'private') row.appendChild(badge('', 'private'));
        if (share.indexed) row.appendChild(badge('indexed', 'indexed'));
        else if (share.visibility !== 'private' && share.index_eligible && share.status === 'active') row.appendChild(badge('', 'eligible'));

        const actions = document.createElement('div');
        actions.className = 'share-mod-actions';
        if (share.status === 'blocked') {
            actions.appendChild(actionBtn('Unblock', () =>
                moderateShare(share.share_id, { action: 'unblock' })));
        } else if (share.status === 'active') {
            actions.appendChild(actionBtn('Block', () =>
                moderateShare(share.share_id, { action: 'block' },
                    'Block this page? It will return 410 for all visitors.')));
            if (share.indexed) {
                actions.appendChild(actionBtn('De-index', () =>
                    moderateShare(share.share_id, { indexed: false })));
            } else if (share.visibility !== 'private') {
                actions.appendChild(actionBtn('Index', () =>
                    moderateShare(share.share_id, { indexed: true },
                        share.index_eligible ? '' :
                        'This page does NOT meet the quality filter. Index anyway?')));
            }
        }
        if (share.needs_review && share.status !== 'blocked') {
            actions.appendChild(actionBtn('Mark reviewed', () =>
                moderateShare(share.share_id, { indexed: !!share.indexed })));
        }
        const remove = actionBtn('Delete', () => deleteShare(share.share_id, share.question));
        remove.className = 'danger';
        actions.appendChild(remove);
        row.appendChild(actions);

        const meta = document.createElement('div');
        meta.className = 'share-mod-meta';
        meta.textContent = `${share.share_id} · created ${share.created_at || '–'}`
            + (share.last_reported_at ? ` · last report ${share.last_reported_at}` : '');
        row.appendChild(meta);

        container.appendChild(row);
    });
    if (sharesNextCursor) {
        const more = actionBtn('Load more', () => loadShares(currentSharesFilter, { append: true }));
        more.id = 'loadMoreSharesBtn';
        more.className = 'admin-btn secondary';
        container.appendChild(more);
    }
}

function badge(kind, text, title) {
    const span = document.createElement('span');
    span.className = 'share-mod-badge' + (kind ? ` ${kind}` : '');
    span.textContent = text;
    if (title) span.title = title;
    return span;
}

function actionBtn(label, onClick) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = label;
    btn.onclick = onClick;
    return btn;
}

document.getElementById('loadReportedSharesBtn').addEventListener('click', () => loadShares('reported'));
document.getElementById('loadAllSharesBtn').addEventListener('click', () => loadShares('all'));

// === Scheduled Publisher Watch pages ===
function publisherWatchesStatus(message, isError) {
    const el = document.getElementById('publisherWatchesStatus');
    el.textContent = message || '';
    el.className = isError ? 'error' : 'success';
}

function renderPublisherWatches(watches) {
    const container = document.getElementById('publisherWatchesContainer');
    container.innerHTML = '';
    const publisherWatches = watches.filter(watch => watch.model_tier === 'free');
    if (!publisherWatches.length) {
        container.textContent = 'No automation-created Watch pages found.';
        return;
    }
    publisherWatches.forEach(watch => {
        const row = document.createElement('div');
        row.className = 'watch-admin-row';

        const question = document.createElement('a');
        question.className = 'watch-admin-question';
        question.href = watch.share_path || '#';
        question.target = '_blank';
        question.rel = 'noopener';
        question.textContent = watch.question || '(untitled)';

        const actions = document.createElement('div');
        actions.className = 'share-mod-actions';
        const paused = watch.status !== 'active';
        actions.appendChild(actionBtn(paused ? 'Resume watch' : 'Pause watch', () =>
            setPublisherWatchStatus(watch, paused ? 'active' : 'paused')));
        const remove = actionBtn('Delete page', () =>
            deleteShare(watch.share_id, watch.question, publisherWatchesStatus));
        remove.className = 'danger';
        actions.appendChild(remove);

        const metaLine = document.createElement('div');
        metaLine.className = 'watch-admin-meta';
        metaLine.textContent = [
            `Watch: ${watch.status}`,
            `Listing: ${watch.indexed ? 'indexed' : watch.index_requested ? 'requested' : 'noindex'}`,
            `Schedule: ${watch.interval}${watch.run_weekday ? ` on ${watch.run_weekday}` : ''}${watch.run_time ? ` at ${watch.run_time} (${watch.timezone})` : ''}`,
            `Next: ${formatAdminTime(watch.next_run_at)}`,
            `Last: ${formatAdminTime(watch.last_run_at)}`,
            `Share ID: ${watch.share_id}`
        ].join(' | ');
        row.append(question, actions, metaLine);
        container.appendChild(row);
    });
}

async function setPublisherWatchStatus(watch, status) {
    publisherWatchesStatus(status === 'paused' ? 'Pausing…' : 'Resuming…', false);
    try {
        await shareAdminRequest('POST', `/api/admin/watches/${encodeURIComponent(watch.id)}/status`, { status });
        await loadPublisherWatches();
    } catch (err) {
        publisherWatchesStatus(err.message, true);
    }
}

async function pauseAllPublisherWatches() {
    const button = document.getElementById('pauseAllPublisherWatchesBtn');
    button.disabled = true;
    publisherWatchesStatus('Pausing…', false);
    try {
        const data = await shareAdminRequest('GET', '/api/admin/watches');
        const active = (data.watches || []).filter(w => w.model_tier === 'free' && w.status === 'active');
        for (const watch of active) {
            await shareAdminRequest('POST', `/api/admin/watches/${encodeURIComponent(watch.id)}/status`, { status: 'paused' });
        }
        await loadPublisherWatches();
        publisherWatchesStatus(`${active.length} watch(es) paused.`, false);
    } catch (err) {
        publisherWatchesStatus(err.message, true);
    } finally {
        button.disabled = false;
    }
}

// `pending` lets the first admin load share one /api/admin/watches request
// between this list and the Watches tab (each costs up to ~200 reads).
async function loadPublisherWatches(pending) {
    publisherWatchesStatus('Loading...', false);
    try {
        const data = await (pending instanceof Promise ? pending : shareAdminRequest('GET', '/api/admin/watches'));
        renderPublisherWatches(data.watches || []);
        publisherWatchesStatus('', false);
    } catch (err) {
        publisherWatchesStatus(err.message, true);
    }
}

document.getElementById('reloadPublisherWatchesBtn').addEventListener('click', loadPublisherWatches);
document.getElementById('pauseAllPublisherWatchesBtn').addEventListener('click', pauseAllPublisherWatches);

// === Account tier (Free / Plus / Pro) ===
// Eigener Speicherpfad: die Stufe ist eine Kontoaenderung, keine
// Modellkonfiguration -- sie geht deshalb nicht ueber die Savebar.
const TIER_LABELS = { free: 'Free', plus: 'Plus', pro: 'Pro' };

function accountTierStatus(message, isError) {
    const el = document.getElementById('accountTierStatus');
    el.textContent = message || '';
    el.className = isError ? 'error' : 'success';
}

function accountTiersStatus(message, isError) {
    const el = document.getElementById('accountTiersStatus');
    el.textContent = message || '';
    el.className = isError ? 'error' : 'success';
}

function tierChip(tier) {
    const value = TIER_LABELS[tier] ? tier : 'free';
    return chip(`tier-${value}`, TIER_LABELS[value]);
}

function renderAccountTierDetail(account) {
    const panel = document.getElementById('accountTierDetail');
    panel.innerHTML = '';
    if (!account) {
        panel.hidden = true;
        return;
    }
    const head = document.createElement('div');
    head.className = 'api-key-name';
    const who = document.createElement('span');
    who.textContent = account.email || account.uid;
    head.append(who, tierChip(account.tier));
    if (account.role === 'admin') head.appendChild(chip('', 'admin'));

    const meta = document.createElement('div');
    meta.className = 'api-key-meta';
    // Genau die Faehigkeiten, die der Server aus der Stufe ableitet -- damit
    // im Dashboard nichts anderes steht als im Lauf gilt.
    meta.textContent = [
        `UID: ${account.uid}`,
        `Frontier models: ${account.premium_models ? 'yes' : 'no'}`,
        `Attachments: ${account.attachments ? 'yes' : 'no'}`,
        `Resolve: ${account.resolve ? 'yes' : 'no'}`,
        `Changed: ${formatAdminTime(account.tier_updated_at)}`,
        account.tier_note ? `Note: ${account.tier_note}` : ''
    ].filter(Boolean).join(' | ');

    panel.append(head, meta);
    const usage = document.createElement('div');
    usage.className = 'api-key-meta';
    const agentUsage = account.agent_usage || {};
    const cost = Number(agentUsage.estimated_cost_nano_usd || 0) / 1e9;
    const measuredCost = Number(agentUsage.provider_cost_nano_usd || 0) / 1e9;
    const estimatedCost = Math.max(0, cost - measuredCost);
    usage.textContent = `Agent Beta · recorded total: $${cost.toFixed(6)} USD `
        + `($${measuredCost.toFixed(6)} provider cost, ~$${estimatedCost.toFixed(6)} estimated) · `
        + `${Number(agentUsage.input_tokens || 0).toLocaleString()} input / `
        + `${Number(agentUsage.output_tokens || 0).toLocaleString()} output tokens · `
        + `${Number(agentUsage.calls || 0)} calls`
        + (agentUsage.unmetered_calls ? ` · ${agentUsage.unmetered_calls} without token usage data` : '')
        + (agentUsage.incomplete_calls ? ` · ${agentUsage.incomplete_calls} with partial usage data` : '')
        + (agentUsage.unsettled_calls ? ` · ${agentUsage.unsettled_calls} pending/unsettled` : '');
    panel.append(usage);
    panel.hidden = false;
}

async function lookupAccountTier() {
    const identifier = document.getElementById('accountTierIdentifier').value.trim();
    if (!identifier) {
        accountTierStatus('Enter a UID or an email address.', true);
        document.getElementById('accountTierIdentifier').focus();
        return;
    }
    accountTierStatus('Looking up...', false);
    try {
        const data = await shareAdminRequest(
            'GET', `/api/admin/account-tier?identifier=${encodeURIComponent(identifier)}`);
        renderAccountTierDetail(data.account);
        // Der Select zeigt die Ist-Stufe, damit "Set tier" ohne weiteres
        // Zutun nichts veraendert.
        document.getElementById('accountTierSelect').value = data.account.tier;
        accountTierStatus('', false);
    } catch (err) {
        renderAccountTierDetail(null);
        accountTierStatus(err.message, true);
    }
}

async function saveAccountTier() {
    const identifier = document.getElementById('accountTierIdentifier').value.trim();
    const tier = document.getElementById('accountTierSelect').value;
    const note = document.getElementById('accountTierNote').value.trim();
    if (!identifier) {
        accountTierStatus('Enter a UID or an email address.', true);
        document.getElementById('accountTierIdentifier').focus();
        return;
    }
    if (!confirm(`Set ${identifier} to ${TIER_LABELS[tier] || tier}?`)) return;
    const button = document.getElementById('saveAccountTierBtn');
    button.disabled = true;
    accountTierStatus('Saving...', false);
    try {
        const data = await shareAdminRequest('PUT', '/api/admin/account-tier', { identifier, tier, note });
        renderAccountTierDetail(data.account);
        const from = TIER_LABELS[data.account.previous_tier] || data.account.previous_tier;
        accountTierStatus(`Tier changed: ${from} -> ${TIER_LABELS[data.account.tier]}.`, false);
        await loadAccountTiers();
    } catch (err) {
        accountTierStatus(err.message, true);
    } finally {
        button.disabled = false;
    }
}

function renderAccountTiers(accounts) {
    const container = document.getElementById('accountTiersContainer');
    container.innerHTML = '';
    if (!accounts.length) {
        container.textContent = 'No account is above Free.';
        return;
    }
    accounts.forEach(account => {
        const row = document.createElement('div');
        row.className = 'api-key-row';
        const main = document.createElement('div');
        main.className = 'api-key-main';
        const name = document.createElement('div');
        name.className = 'api-key-name';
        const who = document.createElement('span');
        who.textContent = account.uid;
        name.append(who, tierChip(account.tier));
        const meta = document.createElement('div');
        meta.className = 'api-key-meta';
        meta.textContent = [
            `Changed: ${formatAdminTime(account.tier_updated_at)}`,
            account.tier_updated_by ? `By: ${account.tier_updated_by}` : '',
            account.tier_note ? `Note: ${account.tier_note}` : ''
        ].filter(Boolean).join(' | ');
        main.append(name, meta);

        const actions = document.createElement('div');
        actions.className = 'api-key-actions';
        const open = actionBtn('Open', () => {
            document.getElementById('accountTierIdentifier').value = account.uid;
            lookupAccountTier();
        });
        open.className = 'admin-btn secondary';
        actions.appendChild(open);
        row.append(main, actions);
        container.appendChild(row);
    });
}

function renderAccountTierChanges(changes) {
    const container = document.getElementById('accountTierChangesContainer');
    container.innerHTML = '';
    if (!changes.length) {
        container.textContent = 'No tier change has been recorded yet.';
        return;
    }
    changes.forEach(entry => {
        const row = document.createElement('div');
        row.className = 'api-key-meta';
        row.textContent = [
            formatAdminTime(entry.changed_at),
            `${entry.uid}: ${TIER_LABELS[entry.from_tier] || entry.from_tier} -> ${TIER_LABELS[entry.to_tier] || entry.to_tier}`,
            entry.changed_by ? `by ${entry.changed_by}` : '',
            entry.note || ''
        ].filter(Boolean).join(' | ');
        container.appendChild(row);
    });
}

async function loadAccountTiers() {
    accountTiersStatus('Loading...', false);
    try {
        const data = await shareAdminRequest('GET', '/api/admin/account-tiers');
        renderAccountTiers(data.accounts || []);
        renderAccountTierChanges(data.changes || []);
        accountTiersStatus('', false);
    } catch (err) {
        accountTiersStatus(err.message, true);
    }
}

document.getElementById('lookupAccountTierBtn').addEventListener('click', lookupAccountTier);
document.getElementById('saveAccountTierBtn').addEventListener('click', saveAccountTier);
document.getElementById('reloadAccountTiersBtn').addEventListener('click', loadAccountTiers);

// === Consensus API keys ===
function apiKeysStatus(message, isError) {
    const el = document.getElementById('apiKeysStatus');
    el.textContent = message || '';
    el.className = isError ? 'error' : 'success';
}

function clearIssuedApiKey() {
    const panel = document.getElementById('issuedApiKeyPanel');
    const input = document.getElementById('issuedApiKeyValue');
    input.value = '';
    panel.hidden = true;
}

async function copyIssuedApiKey() {
    const input = document.getElementById('issuedApiKeyValue');
    if (!input.value) return;
    try {
        await navigator.clipboard.writeText(input.value);
    } catch (err) {
        input.focus();
        input.select();
        document.execCommand('copy');
    }
    apiKeysStatus('API key copied. Store it in your secret manager now.', false);
}

function renderApiKeys(keys) {
    const container = document.getElementById('apiKeysContainer');
    container.innerHTML = '';
    if (!keys.length) {
        container.textContent = 'No API keys found.';
        return;
    }
    keys.forEach(key => {
        const row = document.createElement('div');
        row.className = 'api-key-row';

        const main = document.createElement('div');
        main.className = 'api-key-main';
        const name = document.createElement('div');
        name.className = 'api-key-name';
        const label = document.createElement('span');
        label.textContent = key.label || 'Unlabelled key';
        const prefix = document.createElement('span');
        prefix.className = 'api-key-prefix';
        prefix.textContent = `${key.prefix || 'cns_live_'}...`;
        name.append(label, prefix, chip('', key.status || 'unknown'));

        const metadata = document.createElement('div');
        metadata.className = 'api-key-meta';
        metadata.textContent = [
            `UID: ${key.uid || 'unknown'}`,
            `Scopes: ${(key.scopes || []).join(', ') || 'legacy defaults'}`,
            `Created: ${formatAdminTime(key.created_at)}`,
            `Last used: ${formatAdminTime(key.last_used_at)}`,
            `Key ID: ${key.key_id || 'unknown'}`
        ].join(' | ');
        main.append(name, metadata);

        const actions = document.createElement('div');
        actions.className = 'api-key-actions';
        if (key.status === 'active') {
            const revoke = actionBtn('Revoke', () => revokeApiKey(key));
            revoke.className = 'admin-btn secondary';
            actions.appendChild(revoke);
        }
        row.append(main, actions);
        container.appendChild(row);
    });
}

async function loadApiKeys() {
    const filter = document.getElementById('apiKeyFilterUid').value.trim();
    apiKeysStatus('Loading...', false);
    try {
        const path = '/api/admin/api-keys' + (filter ? `?uid=${encodeURIComponent(filter)}` : '');
        const data = await shareAdminRequest('GET', path);
        renderApiKeys(data.keys || []);
        apiKeysStatus('', false);
    } catch (err) {
        apiKeysStatus(err.message, true);
    }
}

async function issueApiKey() {
    const uid = document.getElementById('apiKeyUid').value.trim();
    const label = document.getElementById('apiKeyLabel').value.trim();
    const scopes = ['consensus:run', 'share:write'];
    if (document.getElementById('apiKeyDirectIndex').checked) scopes.push('share:index');
    if (!uid) {
        apiKeysStatus('Enter the Firebase UID that should own this key.', true);
        document.getElementById('apiKeyUid').focus();
        return;
    }
    const button = document.getElementById('issueApiKeyBtn');
    button.disabled = true;
    clearIssuedApiKey();
    apiKeysStatus('Issuing key...', false);
    try {
        const key = await shareAdminRequest('POST', '/api/admin/api-keys', { uid, label, scopes });
        document.getElementById('issuedApiKeyValue').value = key.api_key;
        document.getElementById('issuedApiKeyPanel').hidden = false;
        document.getElementById('apiKeyFilterUid').value = uid;
        apiKeysStatus('API key issued. This is the only time the full key is available.', false);
        await loadApiKeys();
    } catch (err) {
        apiKeysStatus(err.message, true);
    } finally {
        button.disabled = false;
    }
}

async function revokeApiKey(key) {
    if (!confirm(`Revoke API key "${key.label || key.prefix}"? Existing clients will stop authenticating immediately.`)) return;
    apiKeysStatus('Revoking key...', false);
    try {
        await shareAdminRequest('DELETE', `/api/admin/api-keys/${encodeURIComponent(key.key_id)}`);
        apiKeysStatus('API key revoked.', false);
        await loadApiKeys();
    } catch (err) {
        apiKeysStatus(err.message, true);
    }
}

document.getElementById('issueApiKeyBtn').addEventListener('click', issueApiKey);
document.getElementById('reloadApiKeysBtn').addEventListener('click', loadApiKeys);
document.getElementById('copyIssuedApiKeyBtn').addEventListener('click', copyIssuedApiKey);
document.getElementById('dismissIssuedApiKeyBtn').addEventListener('click', clearIssuedApiKey);

// === Consensus Watch diagnostics ===
function watchesStatus(message, isError) {
    const el = document.getElementById('watchesStatus');
    el.textContent = message || '';
    el.className = isError ? 'error' : 'success';
}

function formatAdminTime(value) {
    if (!value) return 'never';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function renderAdminWatches(watches) {
    const container = document.getElementById('watchesContainer');
    container.innerHTML = '';
    if (!watches.length) {
        container.textContent = 'No Consensus Watches exist.';
        return;
    }
    watches.forEach(watch => {
        const row = document.createElement('div');
        row.className = 'watch-admin-row';
        const question = document.createElement('a');
        question.className = 'watch-admin-question';
        question.href = watch.share_path || '#';
        question.target = '_blank';
        question.rel = 'noopener';
        question.textContent = watch.question || '(untitled)';

        const actions = document.createElement('div');
        actions.className = 'watch-admin-actions';
        const queue = actionBtn('Run now', async () => {
            if (!confirm('Run this watch now? This performs real LLM calls and applies its configured e-mail rule.')) return;
            queue.disabled = true;
            watchesStatus('Starting watch…', false);
            try {
                await shareAdminRequest('POST', `/api/admin/watches/${encodeURIComponent(watch.id)}/run`, {});
                watchesStatus('Watch queued and scheduler started. Reload shortly to see the result.', false);
                await loadAdminWatches();
            } catch (err) {
                watchesStatus(err.message, true);
            } finally {
                queue.disabled = false;
            }
        });
        queue.className = 'admin-btn secondary';
        const leaseActive = watch.claimed_until && new Date(watch.claimed_until).getTime() > Date.now();
        queue.disabled = watch.status !== 'active' || leaseActive;
        queue.title = watch.status !== 'active' ? 'Only active watches can run' : 'Start now through the normal leased scheduler path';
        actions.appendChild(queue);

        const metaLine = document.createElement('div');
        metaLine.className = 'watch-admin-meta';
        metaLine.textContent = [
            `Status: ${watch.status}`,
            `Mode: ${watch.email_mode}`,
            `Interval: ${watch.interval}${watch.run_weekday ? ` on ${watch.run_weekday}` : ''}${watch.run_time ? ` at ${watch.run_time} (${watch.timezone})` : ''}`,
            `Next: ${formatAdminTime(watch.next_run_at)}`,
            `Last: ${formatAdminTime(watch.last_run_at)}`,
            `Failures: ${watch.consecutive_failures}`,
            `Owner: ${watch.owner_uid}`
        ].join(' · ');
        row.append(question, actions, metaLine);
        container.appendChild(row);
    });
}

async function loadAdminWatches(pending) {
    watchesStatus('Loading…', false);
    try {
        const data = await (pending instanceof Promise ? pending : shareAdminRequest('GET', '/api/admin/watches'));
        document.getElementById('smtpConfigState').textContent = data.smtp_configured ? 'SMTP configured' : 'SMTP not configured';
        renderAdminWatches(data.watches || []);
        watchesStatus('', false);
    } catch (err) {
        watchesStatus(err.message, true);
    }
}

document.getElementById('loadWatchesBtn').addEventListener('click', loadAdminWatches);
document.getElementById('sendWatchTestMailBtn').addEventListener('click', async function () {
    if (!confirm('Send a real SMTP test message to your verified admin e-mail address?')) return;
    this.disabled = true;
    watchesStatus('Sending test e-mail…', false);
    try {
        const data = await shareAdminRequest('POST', '/api/admin/watches/test-email', {});
        watchesStatus(`Test e-mail accepted for ${data.recipient}.`, false);
    } catch (err) {
        watchesStatus(err.message, true);
    } finally {
        this.disabled = false;
    }
});

// === Public Topic tickers ===
let adminTopics = [];
// Three separate facts, never one global: what the list highlights, which
// Topic the form actually holds, and which request may still fill the form.
// Save uses only the form's own id, so a failed or overtaken load of B can
// never write A's form content to B.
let selectedTopicId = '';
let loadedTopicId = null;        // null: form holds nothing savable; '': new Topic
let topicEditorGeneration = 0;
let selectedTopicDetail = null;
let topicSlugTouched = false;

function beginTopicEditorChange() {
    topicEditorGeneration += 1;
    loadedTopicId = null;
    syncTopicSaveButton();
    return topicEditorGeneration;
}

function syncTopicSaveButton() {
    const button = document.getElementById('saveAdminTopicBtn');
    if (button) button.disabled = loadedTopicId === null;
}

function topicAdminStatus(message, isError) {
    const el = document.getElementById('topicAdminStatus');
    el.textContent = message || '';
    el.className = `topic-status-line ${isError ? 'error' : 'success'}`;
}

function topicSlug(value) {
    return String(value || '').toLowerCase().trim()
        .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function renderAdminTopicList() {
    const container = document.getElementById('adminTopicList');
    container.innerHTML = '';
    if (!adminTopics.length) {
        container.textContent = 'No Topics yet.';
        return;
    }
    adminTopics.forEach(topic => {
        const button = document.createElement('button');
        button.type = 'button';
        button.classList.toggle('is-active', topic.id === selectedTopicId);
        const title = document.createElement('strong');
        title.textContent = topic.title || '(untitled)';
        const metaLine = document.createElement('small');
        metaLine.textContent = `${topic.status} · ${topic.run_count || 0} runs · next ${formatAdminTime(topic.next_run_at)}`;
        button.append(title, metaLine);
        button.addEventListener('click', () => selectAdminTopic(topic.id));
        container.appendChild(button);
    });
}

function renderTopicModelPlan(providerModels) {
    const selected = providerModels || {};
    const defaults = (globalModelsData.watch_models || {}).free || {};
    const container = document.getElementById('topicModelPlan');
    container.innerHTML = '';
    providers.forEach(provider => {
        const models = globalModelsData[provider] || [];
        const chosen = selected[provider] || defaults[provider] || '';
        const row = document.createElement('div');
        row.className = 'topic-model-row';
        row.dataset.provider = provider;
        const toggleLabel = document.createElement('label');
        const toggle = document.createElement('input');
        toggle.type = 'checkbox';
        toggle.checked = !!chosen;
        toggle.setAttribute('aria-label', `Run ${provider}`);
        toggleLabel.append(toggle, document.createTextNode(providerLabel(provider)));
        const select = document.createElement('select');
        const options = models.length ? models : (chosen ? [chosen] : []);
        options.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = (meta().labels || {})[model] || model;
            option.selected = model === chosen;
            select.appendChild(option);
        });
        select.disabled = !toggle.checked;
        toggle.addEventListener('change', () => {
            select.disabled = !toggle.checked;
            if (toggle.checked && !select.value && select.options.length) select.selectedIndex = 0;
        });
        row.append(toggleLabel, select);
        container.appendChild(row);
    });
}

function fillAdminTopic(topic, runs) {
    selectedTopicDetail = topic;
    document.getElementById('topicEditorEmpty').hidden = true;
    document.getElementById('topicAdminForm').hidden = false;
    document.getElementById('adminTopicTitle').value = topic.title || '';
    document.getElementById('adminTopicSlug').value = topic.slug || '';
    const slugHistory = document.getElementById('adminTopicSlugHistory');
    const retired = (topic.slug_history || []).filter(Boolean);
    slugHistory.hidden = retired.length === 0;
    slugHistory.textContent = retired.length
        ? `Redirecting (301): ${retired.map((item) => `/topics/${item}`).join(', ')}`
        : '';
    document.getElementById('adminTopicQuestion').value = topic.lead_question || '';
    document.getElementById('adminTopicCategory').value = topic.category || '';
    document.getElementById('adminTopicSummary').value = topic.summary || '';
    document.getElementById('adminTopicStatus').value = topic.status || 'active';
    document.getElementById('adminTopicInterval').value = topic.update_interval || 'weekly';
    document.getElementById('adminTopicDomains').value =
        ((topic.source_rules || {}).preferred_domains || []).join('\n');
    document.getElementById('adminTopicSourceNotes').value =
        (topic.source_rules || {}).notes || '';
    document.getElementById('adminTopicSeoTitle').value = (topic.seo || {}).title || '';
    document.getElementById('adminTopicSeoDescription').value = (topic.seo || {}).description || '';
    document.getElementById('adminTopicNoindex').checked = !!(topic.seo || {}).noindex;
    renderTopicModelPlan((topic.run_config || {}).provider_models || {});
    const schedule = document.getElementById('topicScheduleState');
    schedule.textContent = topic.id
        ? `Last: ${formatAdminTime(topic.latest_run_at)} · Next: ${formatAdminTime(topic.next_run_at)} · ${topic.last_run_status || 'never'}${topic.last_run_error ? ` · ${topic.last_run_error}` : ''}`
        : 'Save the Topic before its first run.';
    const history = document.getElementById('topicRunHistory');
    history.innerHTML = '';
    (runs || []).forEach(run => {
        const item = document.createElement('div');
        const headline = document.createElement('strong');
        headline.textContent = `Run ${run.version} · ${run.agreement_score}/100 · ${run.change_type}`;
        const details = document.createElement('small');
        details.textContent = `${formatAdminTime(run.observed_at)} · ${(run.models || []).length} models · ${(run.evidence || []).length} sources`;
        const summary = document.createElement('small');
        summary.textContent = run.change_summary || 'No material change.';
        item.append(headline, details, summary);
        history.appendChild(item);
    });
    if (!(runs || []).length) history.textContent = 'No runs yet.';
    const leaseActive = topic.claimed_until && new Date(topic.claimed_until).getTime() > Date.now();
    document.getElementById('runAdminTopicBtn').disabled =
        !topic.id || topic.status !== 'active' || leaseActive;
    document.getElementById('openAdminTopicBtn').hidden = !topic.latest_run_id;
    document.getElementById('openAdminTopicBtn').href = topic.slug ? `/topics/${encodeURIComponent(topic.slug)}` : '#';
    topicSlugTouched = !!topic.id;
    topicAdminStatus('', false);
}

async function selectAdminTopic(topicId) {
    selectedTopicId = topicId;
    const generation = beginTopicEditorChange();
    renderAdminTopicList();
    topicAdminStatus('Loading Topic...', false);
    try {
        const data = await shareAdminRequest('GET', `/api/admin/topics/${encodeURIComponent(topicId)}`);
        // Only the newest selection may fill the form; a slower answer for an
        // earlier click is dropped.
        if (generation !== topicEditorGeneration) return false;
        if (!data || !data.topic || data.topic.id !== topicId) {
            throw new Error('The loaded Topic does not match the selection. Reload the list.');
        }
        fillAdminTopic(data.topic, data.runs || []);
        loadedTopicId = topicId;
        syncTopicSaveButton();
        return true;
    } catch (err) {
        if (generation === topicEditorGeneration) {
            topicAdminStatus(`${err.message} Saving stays disabled until the Topic loads.`, true);
        }
        return false;
    }
}

async function loadAdminTopics(selectId) {
    const generation = topicEditorGeneration;
    topicAdminStatus('Loading Topics...', false);
    try {
        const data = await shareAdminRequest('GET', '/api/admin/topics');
        adminTopics = data.topics || [];
        renderAdminTopicList();
        // A newer selection, "New Topic" or account change owns the editor now.
        if (generation !== topicEditorGeneration) return;
        const target = selectId || selectedTopicId;
        if (target) {
            if (await selectAdminTopic(target)) topicAdminStatus('', false);
        } else {
            topicAdminStatus('', false);
        }
    } catch (err) {
        if (generation === topicEditorGeneration) topicAdminStatus(err.message, true);
    }
}

function resetAdminTopicEditor() {
    beginTopicEditorChange();
    selectedTopicId = '';
    selectedTopicDetail = null;
    adminTopics = [];
    document.getElementById('topicAdminForm').hidden = true;
    document.getElementById('topicEditorEmpty').hidden = false;
    renderAdminTopicList();
}

function newAdminTopic() {
    selectedTopicId = '';
    beginTopicEditorChange();
    renderAdminTopicList();
    fillAdminTopic({
        status: 'active',
        update_interval: 'weekly',
        source_rules: { allowed_types: ['primary', 'research', 'documentation', 'reporting', 'community', 'rumor'] },
        run_config: { provider_models: (globalModelsData.watch_models || {}).free || {} },
        seo: {}
    }, []);
    loadedTopicId = '';
    syncTopicSaveButton();
    topicSlugTouched = false;
}

function topicProviderModels() {
    const result = {};
    document.querySelectorAll('#topicModelPlan .topic-model-row').forEach(row => {
        const toggle = row.querySelector('input[type="checkbox"]');
        const select = row.querySelector('select');
        if (toggle.checked && select.value) result[row.dataset.provider] = select.value;
    });
    return result;
}

function topicLines(value) {
    return String(value || '').split(/\r?\n/).map(item => item.trim()).filter(Boolean);
}

function adminTopicPayload() {
    return {
        title: document.getElementById('adminTopicTitle').value.trim(),
        slug: document.getElementById('adminTopicSlug').value.trim(),
        lead_question: document.getElementById('adminTopicQuestion').value.trim(),
        category: document.getElementById('adminTopicCategory').value.trim(),
        summary: document.getElementById('adminTopicSummary').value.trim(),
        status: document.getElementById('adminTopicStatus').value,
        update_interval: document.getElementById('adminTopicInterval').value,
        run_config: { provider_models: topicProviderModels(), collect_sources: true },
        source_rules: {
            allowed_types: ['primary', 'research', 'documentation', 'reporting', 'community', 'rumor'],
            preferred_domains: topicLines(document.getElementById('adminTopicDomains').value),
            notes: document.getElementById('adminTopicSourceNotes').value.trim()
        },
        seo: {
            title: document.getElementById('adminTopicSeoTitle').value.trim(),
            description: document.getElementById('adminTopicSeoDescription').value.trim(),
            noindex: document.getElementById('adminTopicNoindex').checked
        }
    };
}

async function saveAdminTopic() {
    // The snapshot is bound to the Topic the form really holds, never to the
    // list highlight: while a switch is loading or after it failed, there is
    // nothing savable.
    const formTopicId = loadedTopicId;
    if (formTopicId === null || formTopicId !== selectedTopicId) {
        topicAdminStatus('Wait until the selected Topic has loaded before saving.', true);
        return;
    }
    const generation = topicEditorGeneration;
    const payload = adminTopicPayload();
    const button = document.getElementById('saveAdminTopicBtn');
    button.disabled = true;
    topicAdminStatus('Saving Topic...', false);
    try {
        const data = await shareAdminRequest(
            formTopicId ? 'PUT' : 'POST',
            formTopicId ? `/api/admin/topics/${encodeURIComponent(formTopicId)}` : '/api/admin/topics',
            payload
        );
        if (generation !== topicEditorGeneration) return;
        selectedTopicId = data.topic.id;
        await loadAdminTopics(selectedTopicId);
        if (loadedTopicId === data.topic.id) topicAdminStatus('Topic configuration saved.', false);
    } catch (err) {
        if (generation === topicEditorGeneration) topicAdminStatus(err.message, true);
    } finally {
        syncTopicSaveButton();
    }
}

async function runAdminTopic() {
    if (!selectedTopicId || loadedTopicId !== selectedTopicId) return;
    if (!confirm('Run this Topic now? The selected models will research current sources and create a new immutable timeline point.')) return;
    const button = document.getElementById('runAdminTopicBtn');
    button.disabled = true;
    topicAdminStatus('Researching sources and building Consensus. This can take a minute...', false);
    try {
        const data = await shareAdminRequest('POST', `/api/admin/topics/${encodeURIComponent(selectedTopicId)}/runs`, {});
        await loadAdminTopics(selectedTopicId);
        topicAdminStatus(`Run ${data.run.version} saved: ${data.run.agreement_score}/100 agreement and ${(data.run.evidence || []).length} sources.`, false);
    } catch (err) {
        topicAdminStatus(err.message, true);
    } finally {
        button.disabled = false;
    }
}

document.getElementById('newAdminTopicBtn').addEventListener('click', newAdminTopic);
document.getElementById('reloadAdminTopicsBtn').addEventListener('click', () => loadAdminTopics(selectedTopicId));
document.getElementById('saveAdminTopicBtn').addEventListener('click', saveAdminTopic);
document.getElementById('runAdminTopicBtn').addEventListener('click', runAdminTopic);
document.getElementById('topicAdminForm').addEventListener('submit', event => event.preventDefault());
document.getElementById('adminTopicTitle').addEventListener('input', event => {
    if (!topicSlugTouched) document.getElementById('adminTopicSlug').value = topicSlug(event.target.value);
});
document.getElementById('adminTopicSlug').addEventListener('input', () => { topicSlugTouched = true; });

// === SEO pulse ===
// One Firestore document: the latest weekly report, a 12-week trend and the
// pages the pulse set to noindex. No per-page metrics are stored anywhere.
function seoStatus(message, isError) {
    const el = document.getElementById('seoStatus');
    el.textContent = message || '';
    el.className = 'admin-status-text ' + (isError ? 'error' : 'success');
}

function formatSeoDay(iso) {
    if (!iso) return '';
    return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
}

function seoChange(now, before) {
    if (!before) return `prev ${before ?? 0}`;
    const pct = Math.round(((now - before) * 100) / before);
    return `prev ${before}, ${pct > 0 ? '+' : ''}${pct}%`;
}

function renderSeoTrend(history) {
    const trend = document.getElementById('seoPulseTrend');
    trend.innerHTML = '';
    const max = Math.max(1, ...history.map(entry => entry.impressions || 0));
    history.forEach(entry => {
        const bar = document.createElement('div');
        bar.className = 'seo-trend-bar';
        bar.style.height = `${Math.max(4, Math.round(((entry.impressions || 0) / max) * 100))}%`;
        bar.title = `Week to ${formatSeoDay(entry.end)}: ${entry.impressions} impressions, ${entry.clicks} clicks`;
        trend.appendChild(bar);
    });
    trend.hidden = history.length < 2;
}

function renderSeoMovers(report) {
    const list = document.getElementById('seoPulseMovers');
    list.innerHTML = '';
    const moved = [
        ...((report?.movers?.up) || []).map(item => ['↑', item]),
        ...((report?.movers?.down) || []).map(item => ['↓', item])
    ];
    if (!moved.length) {
        const li = document.createElement('li');
        li.className = 'section-hint';
        li.textContent = report ? 'Nothing moved.' : 'No report yet.';
        list.appendChild(li);
        return;
    }
    moved.forEach(([arrow, item]) => {
        const li = document.createElement('li');
        li.className = arrow === '↑' ? 'is-up' : 'is-down';
        const delta = document.createElement('strong');
        delta.textContent = `${arrow} ${item.delta > 0 ? '+' : ''}${item.delta}`;
        const link = document.createElement('a');
        link.href = item.path;
        link.target = '_blank';
        link.rel = 'noopener';
        link.textContent = item.path;
        const meta = document.createElement('span');
        meta.textContent = `${item.prev_impressions} → ${item.impressions} impressions`
            + (item.clicks ? ` · ${item.clicks} click${item.clicks === 1 ? '' : 's'}` : '')
            + (item.top_query ? ` · “${item.top_query}”` : '');
        li.append(delta, link, meta);
        list.appendChild(li);
    });
}

function renderSeoNoindexed(entries) {
    const box = document.getElementById('seoPulseNoindexed');
    box.innerHTML = '';
    box.classList.toggle('section-hint', !entries.length);
    if (!entries.length) {
        box.textContent = 'None so far.';
        return;
    }
    entries.forEach(entry => {
        const row = document.createElement('div');
        row.className = 'seo-pulse-row';
        const link = document.createElement('a');
        link.href = entry.path;
        link.target = '_blank';
        link.rel = 'noopener';
        link.textContent = entry.path;
        const meta = document.createElement('span');
        meta.textContent = `${entry.impressions_90d} impressions in 90 days · ${formatAdminTime(entry.at)}`;
        const keep = actionBtn('Keep indexed', async () => {
            keep.disabled = true;
            seoStatus('Re-indexing…', false);
            try {
                renderSeoPulse(await shareAdminRequest('POST', `/api/admin/seo/shares/${encodeURIComponent(entry.share_id)}/keep`, {}));
                seoStatus('Indexed again; the pulse will leave it alone.', false);
            } catch (err) {
                keep.disabled = false;
                seoStatus(err.message, true);
            }
        });
        keep.className = 'admin-btn secondary';
        row.append(link, meta, keep);
        box.appendChild(row);
    });
}

function renderSeoPulse(data) {
    const report = data.report || null;
    document.getElementById('seoPulseEnabled').checked = !!data.enabled;
    document.getElementById('seoPulseSchedule').textContent = data.enabled
        ? `Next run ${formatAdminTime(data.next_run_at)}` + (data.last_run_at ? ` · last ${formatAdminTime(data.last_run_at)}` : '')
        : 'Paused. Nothing runs and nothing is set to noindex.';
    const error = document.getElementById('seoPulseError');
    error.hidden = !report?.error;
    error.textContent = report?.error ? `Last run failed: ${report.error}` : '';
    const ok = !!report && !report.error;
    document.getElementById('seoPulseWeek').textContent = ok
        ? `Week ${formatSeoDay(report.window.start)} – ${formatSeoDay(report.window.end)}`
        : 'No report yet';
    const week = ok ? report.week : {};
    const prev = ok ? report.prev_week : {};
    document.getElementById('seoPulseImpressions').textContent = ok ? week.impressions : '–';
    document.getElementById('seoPulseImpressionsPrev').textContent = ok ? seoChange(week.impressions, prev.impressions) : '';
    document.getElementById('seoPulseClicks').textContent = ok ? week.clicks : '–';
    document.getElementById('seoPulseClicksPrev').textContent = ok ? `prev ${prev.clicks}` : '';
    document.getElementById('seoPulsePosition').textContent = ok && week.position ? week.position : '–';
    renderSeoTrend(data.history || []);
    renderSeoMovers(ok ? report : null);
    renderSeoNoindexed(data.noindexed || []);
}

async function loadSeoPulse() {
    try {
        renderSeoPulse(await shareAdminRequest('GET', '/api/admin/seo'));
        seoStatus('', false);
    } catch (err) {
        seoStatus(err.message, true);
    }
}

document.getElementById('runSeoPulseBtn').addEventListener('click', async function () {
    this.disabled = true;
    seoStatus('Reading Search Console…', false);
    try {
        renderSeoPulse(await shareAdminRequest('POST', '/api/admin/seo/run', {}));
        seoStatus('Done. The note went to Telegram.', false);
    } catch (err) {
        seoStatus(err.message, true);
    } finally {
        this.disabled = false;
    }
});

document.getElementById('seoPulseEnabled').addEventListener('change', async function () {
    try {
        renderSeoPulse(await shareAdminRequest('PUT', '/api/admin/seo/config', { enabled: this.checked }));
        seoStatus(this.checked ? 'Weekly pulse on.' : 'Weekly pulse paused.', false);
    } catch (err) {
        this.checked = !this.checked;
        seoStatus(err.message, true);
    }
});

onAuthStateChanged(auth, async (user) => {
    promptConfigPanel.setUser(user?.uid || null);
    agentBudgetPanel.setUser(user?.uid || null);
    // Any account change invalidates open Topic editor requests and the form.
    resetAdminTopicEditor();
    if (user) {
        const idToken = await user.getIdToken();
        fetchModels(idToken);
        const watches = shareAdminRequest('GET', '/api/admin/watches');
        watches.catch(() => {});
        loadPublisherWatches(watches);
        loadApiKeys();
        loadShares('reported');
        loadAdminWatches(watches);
        loadAdminTopics();
        loadSeoPulse();
    } else {
        setStatus('Please log in to access the admin panel.', true);
        window.location.href = '/';
    }
});
