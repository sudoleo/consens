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
        title: 'Input words',
        fields: [
            ['free_max_words', 'Free'],
            ['plus_max_words', 'Plus'],
            ['pro_max_words', 'Pro']
        ]
    },
    {
        title: 'Output tokens',
        fields: [
            ['free_max_tokens', 'Free'],
            ['plus_max_tokens', 'Plus'],
            ['pro_max_tokens', 'Pro'],
            ['reasoning_max_tokens', 'With Reasoning on (every plan, at least its own limit)']
        ]
    },
    {
        title: 'Consensus output tokens',
        fields: [
            ['consensus_max_tokens', 'Consensus'],
            ['differences_max_tokens', 'Differences'],
            ['coverage_max_tokens', 'Claim coverage']
        ]
    },
    {
        title: 'Consensus Watches',
        fields: [
            ['watch_free_active_limit', 'Active, Free'],
            ['watch_plus_active_limit', 'Active, Plus'],
            ['watch_pro_active_limit', 'Active, Pro'],
            ['watch_max_runs_per_day', 'Runs per day, all accounts'],
            ['watch_probe_max_per_day', 'Evidence probes per day (0 = off)'],
            ['watch_daily_interval_requires_pro', 'Daily runs only for Pro (1 = yes, 0 = Free too)'],
            ['watch_plus_daily_interval_allowed', 'Plus may run daily (1 = yes)']
        ]
    },
    {
        title: 'Agent Watches',
        fields: [
            ['agent_watch_free_active_limit', 'Active, Free'],
            ['agent_watch_plus_active_limit', 'Active, Plus'],
            ['agent_watch_pro_active_limit', 'Active, Pro'],
            ['agent_watch_free_min_hours', 'Shortest interval in hours, Free'],
            ['agent_watch_plus_min_hours', 'Shortest interval in hours, Plus'],
            ['agent_watch_pro_min_hours', 'Shortest interval in hours, Pro'],
            ['agent_watch_max_runs_per_day', 'Runs per day, all accounts']
        ]
    },
    {
        title: 'Share pages in search',
        fields: [
            ['share_min_consensus_chars', 'Consensus at least (characters)'],
            ['share_min_sources', 'Sources at least'],
            ['share_min_models', 'Models at least'],
            ['share_question_min_chars', 'Question at least (characters)'],
            ['share_question_max_chars', 'Question at most (characters)']
        ]
    }
];
let globalModelsData = {};

document.body.classList.toggle('dark-mode', document.documentElement.classList.contains('dark-mode'));

// ==============================
// Pages
// ==============================
// A page shows one or more sections. Older links name a section (#seo in the
// SEO pulse's Telegram note, #api, #consensus); they open its page there.
const PAGES = ['overview', 'accounts', 'pages', 'topics', 'watches', 'models', 'limits', 'prompts'];
const SECTION_PAGES = { shares: 'pages', seo: 'pages', api: 'accounts', consensus: 'models', configuration: 'prompts' };
let currentPage = '';
// The archived Consensus Watches load with the first visit of Watches.
let consensusWatchesRequested = false;
function activateTab(target) {
    const name = String(target || '');
    const page = PAGES.includes(name) ? name : SECTION_PAGES[name] || 'overview';
    currentPage = page;
    if (page !== 'accounts') clearIssuedApiKey();
    if (page === 'watches' && !consensusWatchesRequested && auth.currentUser) loadAdminWatches();
    document.querySelectorAll('.admin-tab-panel').forEach(panel => {
        panel.hidden = panel.dataset.page !== page;
    });
    document.querySelectorAll('.admin-tabs button[data-tab]').forEach(btn => {
        const current = btn.dataset.tab === page;
        btn.classList.toggle('active', current);
        if (current) btn.setAttribute('aria-current', 'page');
        else btn.removeAttribute('aria-current');
    });
    history.replaceState(null, '', `#${name && name !== page && SECTION_PAGES[name] ? name : page}`);
    const section = SECTION_PAGES[name] && document.getElementById(`tab-${name}`);
    if (section && section.dataset.page === page && name !== 'configuration') {
        // A section that is one fold (the API keys) opens with the jump.
        if (section.firstElementChild?.tagName === 'DETAILS') section.firstElementChild.open = true;
        section.scrollIntoView({ block: 'start' });
    } else {
        window.scrollTo(0, 0);
    }
}

document.querySelectorAll('.admin-tabs button[data-tab]').forEach(btn => {
    btn.addEventListener('click', () => activateTab(btn.dataset.tab));
});
document.querySelectorAll('[data-go]').forEach(link => {
    link.addEventListener('click', () => activateTab(link.dataset.go));
});
activateTab((location.hash || '').replace('#', ''));

// ==============================
// Unsaved model settings
// ==============================
// Models, Advanced and Detailed limits are one document with one Save. The
// bar shows only while there is something to save or a save result to read.
function syncSavebar() {
    const bar = document.getElementById('adminSavebar');
    const status = document.getElementById('statusMessage');
    const dirty = bar.classList.contains('is-dirty');
    if (!status.dataset.message) status.textContent = dirty ? 'Unsaved model settings' : '';
    bar.hidden = !dirty && !status.dataset.message;
    document.getElementById('saveBtn').hidden = !dirty;
    document.getElementById('reloadBtn').hidden = !dirty;
}
function markDirty(event) {
    if (event?.target?.closest?.('#agentBudgetForm')) return;
    document.getElementById('adminSavebar').classList.add('is-dirty');
    syncSavebar();
}
function clearDirty() {
    document.getElementById('adminSavebar').classList.remove('is-dirty');
    syncSavebar();
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
document.getElementById('tab-models').addEventListener('change', (event) => {
    // A preset pick changes no provider list; the preset redraws itself.
    if (event.target.closest('#presetModelsContainer')) return;
    renderJudgeSelects();
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
// claude-haiku-4-5 -> claude-haiku-4.5). Sichtbar machen, sonst sieht man
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
    ['Model', 'Policy', 'Effective', 'Why'].forEach(text => {
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
        usage.textContent = `${providerLabel(control.provider)} · ${reasons.length ? reasons.join(', ') : 'in the picker'}`;
        modelCell.append(name, usage);
        const policyCell = row.insertCell();
        if (control.supported) {
            const select = document.createElement('select');
            select.dataset.reasoningModel = control.model;
            select.setAttribute('aria-label', `Reasoning policy for ${control.label}`);
            [['', 'Follow policy'], ['economy', 'Always save'], ['existing', 'Keep default (quality)']].forEach(([value, label]) => {
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
            policyCell.textContent = 'Keeps its setting';
        }
        const valueCell = row.insertCell();
        valueCell.textContent = reasoningText({ reasoning: preview });
        if (differs) {
            const before = document.createElement('small');
            before.textContent = `Was: ${reasoningText({ reasoning: original })}`;
            valueCell.appendChild(before);
            valueCell.className = 'reasoning-budget-changed';
        }
        row.insertCell().textContent = control.note;
    });
    container.appendChild(table);
    document.getElementById('reasoningSummary').textContent = `${changed} of ${controls.length} models changed for this request · ${exceptions} ${exceptions === 1 ? 'exception' : 'exceptions'} · ${protectedModels} keep their setting.`;
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

// An engine as a person reads it: the family and the model's name; an alias
// names the model it currently stands for.
function engineLabel(model) {
    const alias = (meta().aliases || {})[model];
    if (alias) return `${model} (now ${alias.label})`;
    const provider = providers.find(p => (globalModelsData[p] || []).includes(model));
    const label = labelFor(model) || model;
    return provider ? `${providerLabel(provider)} · ${label}` : label;
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
    // Daily/Open Models sind Free-faehig und duerfen keine Premium-Modelle
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
        const title = document.createElement('h3');
        title.textContent = definition.label;
        if (definition.pro_only) {
            const pro = document.createElement('span');
            pro.className = 'pro-badge';
            pro.textContent = 'Pro';
            pro.title = 'Only Pro accounts can pick this preset.';
            title.appendChild(pro);
        }
        card.appendChild(title);

        // The chosen families and one empty slot to add another; up to six.
        for (let index = 0; index < 6; index += 1) {
            const field = document.createElement('div');
            field.className = 'preset-model-field';
            field.hidden = index > answerEntries.length;
            const label = document.createElement('label');
            label.textContent = `Model ${index + 1}`;
            const select = document.createElement('select');
            select.dataset.presetId = definition.id;
            select.dataset.presetAnswerIndex = String(index);
            select.setAttribute('aria-label', `${definition.label} model ${index + 1}`);
            label.htmlFor = select.id = `preset-${definition.id}-${index}`;
            select.add(new Option(index < answerEntries.length ? 'None (remove)' : 'Add a model…', ''));
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
            select.addEventListener('change', () => {
                markDirty();
                renderPresetModels();
                document.getElementById(select.id)?.focus();
            });
            field.appendChild(label);
            field.appendChild(select);
            card.appendChild(field);
        }

        const consensusField = document.createElement('div');
        consensusField.className = 'preset-model-field preset-engine';
        const consensusLabel = document.createElement('label');
        consensusLabel.textContent = 'Engine';
        const consensusSelect = document.createElement('select');
        consensusSelect.dataset.presetId = definition.id;
        consensusSelect.dataset.presetSlot = 'consensus';
        consensusSelect.setAttribute('aria-label', `${definition.label} Consensus engine`);
        consensusLabel.htmlFor = consensusSelect.id = `preset-${definition.id}-engine`;
        consensusListValues().forEach(model => {
            appendPresetOption(consensusSelect, model, engineLabel(model),
                !definition.pro_only && isLockedConsensusModel(model), false);
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
        // One fold per provider: the summary says what matters at a glance,
        // the rows are there when a model is added or moved.
        const section = document.createElement('details');
        section.className = 'admin-fold provider-fold';

        const summary = document.createElement('summary');
        const title = document.createElement('span');
        title.textContent = providerLabel(p);
        const info = document.createElement('span');
        info.className = 'admin-count';
        summary.append(title, info);
        section.appendChild(summary);

        const listContainer = document.createElement('div');
        listContainer.id = `list-${p}`;
        listContainer.className = 'model-list';

        const models = globalModelsData[p] || [];
        models.forEach(m => {
            const row = createModelRow(p, m, premiumSet.has(m), consensusSet.has(m), defaults[p] === m);
            listContainer.appendChild(row);
        });

        section.appendChild(listContainer);

        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'admin-btn quiet add-btn';
        addBtn.textContent = 'Add model';
        addBtn.onclick = () => {
            const row = createModelRow(p, '', false, false, false);
            listContainer.appendChild(row);
            row.querySelector('input[type="text"]').focus();
            markDirty();
            summarizeProvider(section);
        };
        section.appendChild(addBtn);
        section.addEventListener('change', () => summarizeProvider(section));
        summarizeProvider(section);

        container.appendChild(section);
    });

    // Nach den Provider-Listen rendern, damit Add-Dropdown und
    // Alias-Aufloesung den aktuellen DOM-Stand sehen.
    renderConsensusModels();
    renderPresetModels();
    renderJudgeSelects();
    renderWatchModelConfig();
}

function summarizeProvider(section) {
    const info = section.querySelector('summary .admin-count');
    if (!info) return;
    const rows = Array.from(section.querySelectorAll('.model-row'));
    const named = rows.map(row => row.querySelector('input[type="text"]').value.trim()).filter(Boolean);
    const chosen = rows.find(row => row.querySelector('.default-radio')?.checked);
    const fallback = chosen?.querySelector('input[type="text"]').value.trim() || '';
    const parts = [`${named.length} ${named.length === 1 ? 'model' : 'models'}`];
    if (fallback) parts.push(`Free default ${labelFor(fallback) || fallback}`);
    info.textContent = parts.join(' · ');
}

function createModelRow(provider, modelName, isPremium, isConsensus, isDefault) {
    const row = document.createElement('div');
    row.className = 'model-row';

    const dependencies = modelName ? dependencyReasons(provider, modelName) : [];

    const upBtn = document.createElement('button');
    upBtn.type = 'button';
    upBtn.className = 'icon-btn';
    upBtn.textContent = '↑';
    upBtn.title = 'Move up';
    upBtn.setAttribute('aria-label', `Move ${modelName || 'model'} up`);
    upBtn.onclick = () => { moveRow(row, -1); markDirty(); };

    const downBtn = document.createElement('button');
    downBtn.type = 'button';
    downBtn.className = 'icon-btn';
    downBtn.textContent = '↓';
    downBtn.title = 'Move down';
    downBtn.setAttribute('aria-label', `Move ${modelName || 'model'} down`);
    downBtn.onclick = () => { moveRow(row, 1); markDirty(); };

    const input = document.createElement('input');
    input.type = 'text';
    input.value = modelName;
    input.placeholder = 'Model id, e.g. gpt-5.5';
    input.setAttribute('aria-label', 'Model id');
    input.spellcheck = false;
    const modelLabel = modelName ? labelFor(modelName) : '';
    const shownAs = document.createElement('span');
    shownAs.className = 'model-label';
    if (modelLabel && modelLabel !== modelName) shownAs.textContent = modelLabel;
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
    defaultLabel.title = 'Preselected for Free accounts in this family. Cannot be Pro only.';
    const defaultRadio = document.createElement('input');
    defaultRadio.type = 'radio';
    defaultRadio.className = 'default-radio';
    defaultRadio.name = `default-${provider}`;
    defaultRadio.checked = !!isDefault;
    defaultLabel.appendChild(defaultRadio);
    defaultLabel.appendChild(document.createTextNode(' Free default'));

    const premiumLabel = document.createElement('label');
    premiumLabel.title = 'Only Pro accounts may pick this model.';
    const premiumCheckbox = document.createElement('input');
    premiumCheckbox.type = 'checkbox';
    premiumCheckbox.className = 'premium-checkbox';
    premiumCheckbox.checked = isPremium;
    premiumLabel.appendChild(premiumCheckbox);
    premiumLabel.appendChild(document.createTextNode(' Pro only'));

    const consensusLabel = document.createElement('label');
    consensusLabel.title = 'Offer this model as Consensus engine (order under Advanced).';
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
    removeBtn.setAttribute('aria-label', `Remove ${modelName || 'model'}`);
    removeBtn.onclick = () => {
        const section = row.closest('.provider-fold');
        if (consensusCheckbox.checked) removeConsensusListValue(input.value.trim());
        row.remove();
        renderJudgeSelects();
        renderConsensusAddSelect();
        renderPresetModels();
        renderWatchModelConfig();
        markDirty();
        if (section) summarizeProvider(section);
    };

    const name = document.createElement('div');
    name.className = 'model-name';
    name.append(input, shownAs, flags);
    const toggles = document.createElement('div');
    toggles.className = 'model-toggles';
    toggles.append(defaultLabel, premiumLabel, consensusLabel);

    row.appendChild(upBtn);
    row.appendChild(downBtn);
    row.appendChild(name);
    row.appendChild(toggles);
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
        section.className = 'limit-group';

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
    section.className = 'limit-group';
    const title = document.createElement('h3');
    title.textContent = 'Memory edits';
    section.appendChild(title);

    const enabledRow = document.createElement('div');
    enabledRow.className = 'limit-row';
    const enabledLabel = document.createElement('label');
    enabledLabel.htmlFor = 'memory-edit-enabled';
    enabledLabel.textContent = 'On';
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
    modelLabel.textContent = 'Model (OpenAI)';
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
        ['memory_free_chars', 'Memory size, Free (characters)'],
        ['memory_plus_chars', 'Memory size, Plus (characters)'],
        ['memory_pro_chars', 'Memory size, Pro (characters)'],
        ['memory_free_ai_edits_daily', 'Edits per day, Free'],
        ['memory_plus_ai_edits_daily', 'Edits per day, Plus'],
        ['memory_pro_ai_edits_daily', 'Edits per day, Pro'],
        ['memory_ai_edits_per_minute', 'Edits per minute'],
        ['memory_global_calls_daily', 'Calls per day, all accounts'],
        ['memory_edit_input_chars', 'Correction length (characters)'],
        ['memory_edit_output_tokens', 'Patch output tokens'],
        ['memory_edit_timeout_seconds', 'Timeout in seconds']
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
    el.dataset.message = message || '';
    el.textContent = message || '';
    el.className = message ? (isError ? 'error' : 'success') : '';
    syncSavebar();
}

let modelsLoadError = '';
async function fetchModels(idToken) {
    const notice = document.getElementById('modelsLoadError');
    try {
        const response = await fetch('/api/admin/models', {
            headers: { 'Authorization': `Bearer ${idToken}` }
        });
        if (!response.ok) {
            throw new Error('The model settings could not be loaded. Reload the page to try again.');
        }
        globalModelsData = await response.json();
        providers = Array.isArray(meta().provider_keys)
            ? meta().provider_keys.slice()
            : [];
        modelsLoadError = '';
        notice.hidden = true;
        renderUI();
        clearDirty();
    } catch (err) {
        modelsLoadError = err.message;
        notice.textContent = err.message;
        notice.hidden = false;
    }
    renderOverview();
}

async function reloadModels() {
    const user = auth.currentUser;
    if (!user) return;
    if (!confirm('Discard your unsaved model changes?')) return;
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
        const profile = tier === 'free' ? 'Free/Plus' : 'Pro';
        if (Object.keys(data.watch_models[tier]).length < 2) {
            setStatus(`Watch models: pick at least two families for ${profile}.`, true);
            return;
        }
        if (!data.watch_consensus_models[tier]) {
            setStatus(`Watch models: pick a Consensus engine for ${profile}.`, true);
            return;
        }
    }
    for (const definition of (meta().preset_definitions || [])) {
        const configured = data.preset_models[definition.id] || {};
        const answers = configured.answers || {};
        // 2 to 6 families (the defaults have two or three).
        const families = Object.keys(answers).length;
        if (families < 2 || families > 6 || !configured.consensus) {
            setStatus(`${definition.label} needs two to six model families and an engine.`, true);
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
            setStatus('Saved. Live now.', false);
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

// === Shared pages ===
let currentSharesFilter = 'reported';

function sharesStatus(message, isError) {
    const el = document.getElementById('sharesStatus');
    el.textContent = message || '';
    el.className = 'admin-status' + (message ? (isError ? ' error' : ' success') : '');
}

let loadedShares = [];
let sharesNextCursor = null;
let sharesRequestId = 0;
// Reported pages nobody has reviewed yet: the Overview and the menu count them.
let unreviewedShares = null;

// Paged moderation list: the server filters and orders before limiting and
// says whether more rows exist, so nothing relevant hides behind a window.
async function loadShares(filter, { append = false } = {}) {
    const requestId = ++sharesRequestId;
    if (!append) {
        currentSharesFilter = filter;
        loadedShares = [];
        sharesNextCursor = null;
    }
    document.getElementById('loadReportedSharesBtn').setAttribute('aria-pressed', String(filter === 'reported'));
    document.getElementById('loadAllSharesBtn').setAttribute('aria-pressed', String(filter !== 'reported'));
    sharesStatus('Loading…', false);
    let data;
    const cursor = append && sharesNextCursor ? `&cursor=${encodeURIComponent(sharesNextCursor)}` : '';
    try {
        data = await shareAdminRequest('GET', `/api/admin/shares?filter=${filter}${cursor}`);
    } catch (err) {
        if (requestId === sharesRequestId) sharesStatus(err.message, true);
        if (filter === 'reported' && unreviewedShares === null) {
            unreviewedShares = 0;
            overviewFailed('shares', 'Reported pages did not load', 'pages');
        }
        return;
    }
    if (requestId !== sharesRequestId) return;
    overviewErrors.delete('shares');
    loadedShares = loadedShares.concat(data.shares || []);
    sharesNextCursor = data.has_more ? data.next_cursor : null;
    sharesStatus(sharesNextCursor ? `${loadedShares.length} shown, more below` : '', false);
    if (filter === 'reported' && !append) {
        unreviewedShares = loadedShares.filter(share => share.needs_review && share.status !== 'blocked').length;
        renderOverview();
    }
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
    if (!confirm(`Delete "${label}" for good? The page, its Watch, history and followers go at once. This cannot be undone.`)) return;
    statusFn('Deleting…', false);
    try {
        await shareAdminRequest('DELETE', `/api/admin/shares/${encodeURIComponent(shareId)}`);
        await Promise.all([loadShares(currentSharesFilter), loadAdminWatches()]);
    } catch (err) {
        statusFn(err.message, true);
    }
}

function formatAdminDay(value) {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value)
        : date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

// One status word with a dot: red asks for a look, green is live in search.
function stateWord(text, tone, title) {
    const span = document.createElement('span');
    span.className = 'admin-state' + (tone ? ` is-${tone}` : '');
    span.textContent = text;
    if (title) span.title = title;
    return span;
}

function renderShares(shares, siteUrl) {
    const container = document.getElementById('sharesContainer');
    container.innerHTML = '';
    if (!shares.length) {
        const empty = document.createElement('p');
        empty.className = 'admin-empty';
        empty.textContent = currentSharesFilter === 'reported' ? 'No reported pages.' : 'No pages yet.';
        container.appendChild(empty);
        return;
    }
    shares.forEach(share => {
        const row = document.createElement('div');
        row.className = 'admin-row share-mod-row';

        const main = document.createElement('div');
        main.className = 'admin-row-main';
        const link = document.createElement('a');
        link.className = 'admin-row-title';
        link.textContent = share.question || '(untitled)';
        link.href = siteUrl + share.path;
        link.target = '_blank';
        link.rel = 'noopener';

        const states = document.createElement('div');
        states.className = 'admin-row-meta';
        if (share.reports_count > 0) {
            const reasons = Object.entries(share.report_reasons || {})
                .map(([k, v]) => `${k}: ${v}`).join(', ');
            states.appendChild(stateWord(
                share.reports_count === 1 ? '1 report' : `${share.reports_count} reports`,
                share.needs_review ? 'alert' : '', reasons));
        }
        if (share.needs_review) states.appendChild(stateWord('needs review', 'alert'));
        if (share.index_requested) states.appendChild(stateWord('listing requested', 'warn', 'The owner asked for this page to be in Google.'));
        if (share.status === 'blocked') states.appendChild(stateWord('blocked', 'alert'));
        if (share.visibility === 'private') states.appendChild(stateWord('private'));
        if (share.indexed) states.appendChild(stateWord('in search', 'ok'));
        else if (share.visibility !== 'private' && share.index_eligible && share.status === 'active') states.appendChild(stateWord('could be listed'));
        const when = document.createElement('span');
        when.textContent = `shared ${formatAdminDay(share.created_at) || '–'}`
            + (share.last_reported_at ? ` · last report ${formatAdminDay(share.last_reported_at)}` : '');
        when.title = share.share_id;
        states.appendChild(when);
        main.append(link, states);

        const actions = document.createElement('div');
        actions.className = 'admin-row-actions share-mod-actions';
        if (share.needs_review && share.status !== 'blocked') {
            actions.appendChild(actionBtn('Mark reviewed', () =>
                moderateShare(share.share_id, { indexed: !!share.indexed })));
        }
        if (share.status === 'blocked') {
            actions.appendChild(actionBtn('Unblock', () =>
                moderateShare(share.share_id, { action: 'unblock' })));
        } else if (share.status === 'active') {
            if (share.indexed) {
                actions.appendChild(actionBtn('Remove from search', () =>
                    moderateShare(share.share_id, { indexed: false })));
            } else if (share.visibility !== 'private') {
                actions.appendChild(actionBtn('List in search', () =>
                    moderateShare(share.share_id, { indexed: true },
                        share.index_eligible ? '' :
                        'This page does not meet the quality filter. List it anyway?')));
            }
            actions.appendChild(actionBtn('Block', () =>
                moderateShare(share.share_id, { action: 'block' },
                    'Block this page? Every visitor gets “gone” (410).')));
        }
        const remove = actionBtn('Delete', () => deleteShare(share.share_id, share.question));
        remove.classList.add('danger');
        actions.appendChild(remove);

        row.append(main, actions);
        container.appendChild(row);
    });
    if (sharesNextCursor) {
        const more = actionBtn('Show more', () => loadShares(currentSharesFilter, { append: true }));
        more.id = 'loadMoreSharesBtn';
        more.className = 'admin-btn quiet admin-more';
        container.appendChild(more);
    }
}

function actionBtn(label, onClick) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'admin-btn quiet';
    btn.textContent = label;
    btn.onclick = onClick;
    return btn;
}

document.getElementById('loadReportedSharesBtn').addEventListener('click', () => loadShares('reported'));
document.getElementById('loadAllSharesBtn').addEventListener('click', () => loadShares('all'));

// === Account tier (Free / Plus / Pro) ===
// Eigener Speicherpfad: die Stufe ist eine Kontoaenderung, keine
// Modellkonfiguration -- sie geht deshalb nicht ueber die Savebar.
const TIER_LABELS = { free: 'Free', plus: 'Plus', pro: 'Pro' };
let shownAccount = null;
let elevatedAccounts = null;

function accountTierStatus(message, isError) {
    const el = document.getElementById('accountTierStatus');
    el.textContent = message || '';
    el.className = 'admin-status' + (message ? (isError ? ' error' : ' success') : '');
}

function accountTiersStatus(message, isError) {
    const el = document.getElementById('accountTiersStatus');
    el.textContent = message || '';
    el.className = 'admin-status' + (message ? (isError ? ' error' : ' success') : '');
}

function tierChip(tier) {
    const value = TIER_LABELS[tier] ? tier : 'free';
    return chip(`tier-${value}`, TIER_LABELS[value]);
}

function chosenTier() {
    return document.querySelector('input[name="accountTier"]:checked')?.value || '';
}

function syncAccountTierSave() {
    const button = document.getElementById('saveAccountTierBtn');
    button.disabled = !shownAccount || !chosenTier() || chosenTier() === shownAccount.tier;
}

function money(nanoUsd) {
    const usd = Number(nanoUsd || 0) / 1e9;
    return `$${usd < 1 ? usd.toFixed(3) : usd.toFixed(2)}`;
}

function renderAccountTierDetail(account) {
    const panel = document.getElementById('accountTierDetail');
    shownAccount = account || null;
    if (!account) {
        panel.hidden = true;
        syncAccountTierSave();
        return;
    }
    const who = document.getElementById('accountTierWho');
    who.innerHTML = '';
    const name = document.createElement('strong');
    name.textContent = account.email || account.uid;
    const uid = document.createElement('span');
    uid.className = 'admin-muted admin-mono';
    uid.textContent = account.uid;
    who.append(name, uid);
    if (account.role === 'admin') who.appendChild(chip('', 'admin'));

    document.querySelectorAll('input[name="accountTier"]').forEach(radio => {
        radio.checked = radio.value === account.tier;
    });

    // Genau die Faehigkeiten, die der Server aus der Stufe ableitet -- damit
    // im Dashboard nichts anderes steht als im Lauf gilt.
    const agentUsage = account.agent_usage || {};
    const facts = [
        `Frontier models ${account.premium_models ? 'yes' : 'no'}`,
        `Attachments ${account.attachments ? 'yes' : 'no'}`,
        `Resolve ${account.resolve ? 'yes' : 'no'}`,
        `Agent so far ${money(agentUsage.estimated_cost_nano_usd)} in ${Number(agentUsage.calls || 0)} calls`,
    ];
    if (account.tier_updated_at) facts.push(`plan changed ${formatAdminDay(account.tier_updated_at)}`);
    if (account.tier_note) facts.push(`note: ${account.tier_note}`);
    const factLine = document.getElementById('accountTierFacts');
    factLine.textContent = facts.join(' · ');
    const measured = Number(agentUsage.provider_cost_nano_usd || 0);
    factLine.title = `Provider cost ${money(measured)}, estimated ${money(Math.max(0, Number(agentUsage.estimated_cost_nano_usd || 0) - measured))}; `
        + `${Number(agentUsage.input_tokens || 0).toLocaleString()} input and ${Number(agentUsage.output_tokens || 0).toLocaleString()} output tokens`
        + (agentUsage.unsettled_calls ? `; ${agentUsage.unsettled_calls} not settled yet` : '');
    document.getElementById('accountTierNote').value = '';
    panel.hidden = false;
    syncAccountTierSave();
}

async function lookupAccountTier() {
    const field = document.getElementById('accountTierIdentifier');
    const identifier = field.value.trim();
    if (!identifier) {
        accountTierStatus('Enter an email or a UID.', true);
        field.focus();
        return;
    }
    accountTierStatus('Looking…', false);
    try {
        const data = await shareAdminRequest(
            'GET', `/api/admin/account-tier?identifier=${encodeURIComponent(identifier)}`);
        renderAccountTierDetail(data.account);
        accountTierStatus('', false);
    } catch (err) {
        renderAccountTierDetail(null);
        accountTierStatus(err.message, true);
    }
}

async function saveAccountTier() {
    if (!shownAccount) return;
    const tier = chosenTier();
    const note = document.getElementById('accountTierNote').value.trim();
    const button = document.getElementById('saveAccountTierBtn');
    button.disabled = true;
    accountTierStatus('Saving…', false);
    try {
        const data = await shareAdminRequest('PUT', '/api/admin/account-tier', { identifier: shownAccount.uid, tier, note });
        renderAccountTierDetail(data.account);
        const from = TIER_LABELS[data.account.previous_tier] || data.account.previous_tier;
        accountTierStatus(`${data.account.email || data.account.uid} is now ${TIER_LABELS[data.account.tier]} (was ${from}).`, false);
        await loadAccountTiers();
    } catch (err) {
        accountTierStatus(err.message, true);
        syncAccountTierSave();
    }
}

function openAccount(identifier) {
    activateTab('accounts');
    document.getElementById('accountTierIdentifier').value = identifier;
    lookupAccountTier();
}

function renderAccountTiers(accounts) {
    const container = document.getElementById('accountTiersContainer');
    container.innerHTML = '';
    if (!accounts.length) {
        const empty = document.createElement('p');
        empty.className = 'admin-empty';
        empty.textContent = 'Everyone is on Free.';
        container.appendChild(empty);
        return;
    }
    accounts.forEach(account => {
        const row = document.createElement('button');
        row.type = 'button';
        row.className = 'admin-row account-row';
        const main = document.createElement('span');
        main.className = 'admin-row-main';
        const who = document.createElement('span');
        who.className = 'admin-row-title';
        who.textContent = account.email || account.uid;
        const meta = document.createElement('span');
        meta.className = 'admin-row-meta';
        meta.textContent = [
            account.tier_updated_at ? `since ${formatAdminDay(account.tier_updated_at)}` : '',
            account.tier_note || ''
        ].filter(Boolean).join(' · ');
        main.append(who, meta);
        row.title = account.uid;
        row.append(main, tierChip(account.tier));
        row.addEventListener('click', () => openAccount(account.uid));
        container.appendChild(row);
    });
}

function renderAccountTierChanges(changes) {
    const container = document.getElementById('accountTierChangesContainer');
    container.innerHTML = '';
    if (!changes.length) {
        const empty = document.createElement('p');
        empty.className = 'admin-empty';
        empty.textContent = 'No plan change yet.';
        container.appendChild(empty);
        return;
    }
    changes.forEach(entry => {
        const row = document.createElement('div');
        row.className = 'admin-row is-compact';
        const main = document.createElement('div');
        main.className = 'admin-row-main';
        const what = document.createElement('span');
        what.className = 'admin-row-title';
        what.textContent = `${entry.email || entry.uid}: ${TIER_LABELS[entry.from_tier] || entry.from_tier} → ${TIER_LABELS[entry.to_tier] || entry.to_tier}`;
        what.title = entry.uid;
        const meta = document.createElement('span');
        meta.className = 'admin-row-meta';
        meta.textContent = [formatAdminTime(entry.changed_at), entry.note || ''].filter(Boolean).join(' · ');
        main.append(what, meta);
        row.appendChild(main);
        container.appendChild(row);
    });
}

async function loadAccountTiers() {
    accountTiersStatus('Loading…', false);
    try {
        const data = await shareAdminRequest('GET', '/api/admin/account-tiers');
        elevatedAccounts = data.accounts || [];
        renderAccountTiers(elevatedAccounts);
        renderAccountTierChanges(data.changes || []);
        accountTiersStatus('', false);
    } catch (err) {
        accountTiersStatus(err.message, true);
    }
    renderOverview();
}

document.getElementById('accountTierForm').addEventListener('submit', event => {
    event.preventDefault();
    lookupAccountTier();
});
document.getElementById('accountTierChoice').addEventListener('change', syncAccountTierSave);
document.getElementById('saveAccountTierBtn').addEventListener('click', saveAccountTier);
document.getElementById('reloadAccountTiersBtn').addEventListener('click', loadAccountTiers);

// === Consensus API keys ===
function apiKeysStatus(message, isError) {
    const el = document.getElementById('apiKeysStatus');
    el.textContent = message || '';
    el.className = 'admin-status' + (message ? (isError ? ' error' : ' success') : '');
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
    const active = keys.filter(key => key.status === 'active').length;
    document.getElementById('apiKeysCount').textContent = active ? `${active} active` : '';
    if (!keys.length) {
        const empty = document.createElement('p');
        empty.className = 'admin-empty';
        empty.textContent = 'No API keys.';
        container.appendChild(empty);
        return;
    }
    keys.forEach(key => {
        const row = document.createElement('div');
        row.className = 'admin-row';

        const main = document.createElement('div');
        main.className = 'admin-row-main';
        const name = document.createElement('span');
        name.className = 'admin-row-title';
        name.textContent = key.label || 'Unlabelled key';
        const prefix = document.createElement('span');
        prefix.className = 'admin-mono admin-muted';
        prefix.textContent = ` ${key.prefix || 'cns_live_'}…`;
        name.appendChild(prefix);

        const metadata = document.createElement('div');
        metadata.className = 'admin-row-meta';
        metadata.appendChild(stateWord(key.status || 'unknown', key.status === 'active' ? 'ok' : ''));
        const facts = document.createElement('span');
        facts.textContent = [
            `owner ${key.uid || 'unknown'}`,
            (key.scopes || []).join(', ') || 'legacy scopes',
            `last used ${formatAdminTime(key.last_used_at)}`,
        ].join(' · ');
        facts.title = `Created ${formatAdminTime(key.created_at)} · key id ${key.key_id || 'unknown'}`;
        metadata.appendChild(facts);
        main.append(name, metadata);

        const actions = document.createElement('div');
        actions.className = 'admin-row-actions';
        if (key.status === 'active') {
            const revoke = actionBtn('Revoke', () => revokeApiKey(key));
            revoke.classList.add('danger');
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

// === Watches ===
// A Watch runs the Agent (agent_watches.py). The Consensus Watches before
// them stay as a record while they are archived: no run, no pause.
let agentWatchList = null;
let lateAfterMs = 2 * 60 * 60 * 1000;
let adminWatches = null;
let consensusArchived = true;

function watchesStatus(message, isError) {
    const el = document.getElementById('watchesStatus');
    el.textContent = message || '';
    el.className = 'admin-status' + (message ? (isError ? ' error' : ' success') : '');
}

function formatAdminTime(value) {
    if (!value) return 'never';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

const WATCH_INTERVALS = { hourly: 'hourly', every_6_hours: 'every 6 hours', daily: 'daily', weekly: 'weekly' };
function watchSchedule(watch) {
    const day = watch.run_weekday ? ` on ${watch.run_weekday}` : '';
    const time = watch.run_time ? ` at ${watch.run_time}` : '';
    return `${WATCH_INTERVALS[watch.interval] || watch.interval}${day}${time}`;
}

// An hour past LATE_AFTER and not looking: the scheduler skips a late
// morning run on purpose, so only a wait beyond that is a fault.
function agentWatchOverdue(watch) {
    if (watch.status !== 'active' || watch.looking || !watch.next_run_at) return false;
    return Date.now() - new Date(watch.next_run_at).getTime() > lateAfterMs + 60 * 60 * 1000;
}

const FAILED_LOOKS = new Set(['failed', 'not_started', 'cannot_run']);
function agentWatchFailing(watch) {
    const looks = watch.looks || [];
    return watch.status === 'active' && looks.length > 0 && FAILED_LOOKS.has(looks[looks.length - 1].outcome);
}

const LOOK_WORDS = {
    finding: 'found something', needs_you: 'needs its owner', done: 'reached its goal', quiet: 'nothing new',
    failed: 'failed', not_started: 'did not start', cannot_run: 'cannot run', chat_gone: 'chat deleted',
    google_data: 'chat holds Google data', already_ran: 'already ran',
};

function agentWatchRow(watch) {
    const row = document.createElement('div');
    row.className = 'admin-row';
    const main = document.createElement('div');
    main.className = 'admin-row-main';
    const task = document.createElement('span');
    task.className = 'admin-row-title';
    task.textContent = watch.task || '(no task)';
    task.title = watch.goal ? `Done when: ${watch.goal}` : '';

    const meta = document.createElement('div');
    meta.className = 'admin-row-meta';
    const failing = agentWatchFailing(watch);
    const overdue = agentWatchOverdue(watch);
    if (watch.looking) meta.appendChild(stateWord('looking now', 'ok'));
    else if (watch.status === 'active') meta.appendChild(stateWord('running', failing ? 'alert' : 'ok'));
    else meta.appendChild(stateWord(watch.status === 'paused' ? 'paused' : `ended${watch.ended ? `: ${watch.ended.replace(/_/g, ' ')}` : ''}`));
    if (failing) meta.appendChild(stateWord(`last look ${LOOK_WORDS[watch.looks.at(-1).outcome] || 'failed'}`, 'alert'));
    if (overdue) meta.appendChild(stateWord(`overdue since ${formatAdminTime(watch.next_run_at)}`, 'warn'));
    const when = document.createElement('span');
    const last = (watch.looks || []).at(-1);
    when.textContent = [
        watchSchedule(watch),
        watch.status === 'active' && !overdue && watch.next_run_at ? `next ${formatAdminTime(watch.next_run_at)}` : '',
        last && !failing ? `last ${LOOK_WORDS[last.outcome] || last.outcome}` : '',
        watch.owner_email || watch.uid,
    ].filter(Boolean).join(' · ');
    if (last?.summary) when.title = last.summary;
    meta.appendChild(when);
    main.append(task, meta);
    row.appendChild(main);
    return row;
}

function renderAgentWatches(watches) {
    const container = document.getElementById('agentWatchesContainer');
    container.innerHTML = '';
    // Failing and overdue ones on top; paused and ended wait in a fold.
    const trouble = watch => (agentWatchFailing(watch) || agentWatchOverdue(watch) ? 0 : 1);
    const running = watches.filter(watch => watch.status === 'active').sort((a, b) => trouble(a) - trouble(b));
    const rest = watches.filter(watch => watch.status !== 'active');
    running.forEach(watch => container.appendChild(agentWatchRow(watch)));
    if (!running.length) {
        const empty = document.createElement('p');
        empty.className = 'admin-empty';
        empty.textContent = 'No Watch is running.';
        container.appendChild(empty);
    }
    if (rest.length) container.appendChild(watchFold('Paused and ended', rest.map(agentWatchRow)));
}

function watchFold(title, rows) {
    const fold = document.createElement('details');
    fold.className = 'admin-fold';
    const summary = document.createElement('summary');
    summary.textContent = `${title} `;
    const count = document.createElement('span');
    count.className = 'admin-count';
    count.textContent = String(rows.length);
    summary.appendChild(count);
    fold.append(summary, ...rows);
    return fold;
}

function consensusWatchRow(watch) {
    const row = document.createElement('div');
    row.className = 'admin-row watch-admin-row';
    const main = document.createElement('div');
    main.className = 'admin-row-main';
    const question = document.createElement('a');
    question.className = 'admin-row-title';
    question.href = watch.share_path || '#';
    question.target = '_blank';
    question.rel = 'noopener';
    question.textContent = watch.question || '(untitled)';
    const meta = document.createElement('div');
    meta.className = 'admin-row-meta';
    meta.appendChild(stateWord(consensusArchived ? 'archived' : watch.status));
    const when = document.createElement('span');
    when.textContent = `${watchSchedule(watch)} · last ran ${formatAdminTime(watch.last_run_at)}`;
    when.title = `${watch.timezone || ''} · mail ${watch.email_mode} · owner ${watch.owner_uid}`;
    meta.appendChild(when);
    main.append(question, meta);
    row.appendChild(main);
    if (consensusArchived) return row;

    const actions = document.createElement('div');
    actions.className = 'admin-row-actions watch-admin-actions';
    if (watch.status === 'active' || watch.status === 'paused') {
        const paused = watch.status === 'paused';
        const toggle = actionBtn(paused ? 'Resume' : 'Pause', async () => {
            toggle.disabled = true;
            watchesStatus(paused ? 'Resuming…' : 'Pausing…', false);
            try {
                await shareAdminRequest('POST', `/api/admin/watches/${encodeURIComponent(watch.id)}/status`,
                    { status: paused ? 'active' : 'paused' });
                await loadAdminWatches();
            } catch (err) {
                toggle.disabled = false;
                watchesStatus(err.message, true);
            }
        });
        actions.appendChild(toggle);
    }
    if (watch.status === 'active') {
        const queue = actionBtn('Run now', async () => {
            if (!confirm('Run this Watch now? It makes real model calls and may send its e-mail.')) return;
            queue.disabled = true;
            watchesStatus('Starting…', false);
            try {
                await shareAdminRequest('POST', `/api/admin/watches/${encodeURIComponent(watch.id)}/run`, {});
                watchesStatus('Started. Reload in a minute to see the result.', false);
                await loadAdminWatches();
            } catch (err) {
                watchesStatus(err.message, true);
            } finally {
                queue.disabled = false;
            }
        });
        const leaseActive = watch.claimed_until && new Date(watch.claimed_until).getTime() > Date.now();
        queue.disabled = leaseActive;
        queue.title = leaseActive ? 'Running right now' : 'Start through the normal scheduler';
        actions.appendChild(queue);
    }
    row.appendChild(actions);
    return row;
}

function renderAdminWatches(watches) {
    const container = document.getElementById('watchesContainer');
    container.innerHTML = '';
    if (!watches.length) return;
    container.appendChild(watchFold(consensusArchived ? 'Archived Consensus Watches' : 'Consensus Watches',
        watches.map(consensusWatchRow)));
}

async function loadAgentWatches() {
    try {
        const data = await shareAdminRequest('GET', '/api/admin/agent-watches');
        agentWatchList = data.watches || [];
        if (Number(data.late_after_seconds) > 0) lateAfterMs = Number(data.late_after_seconds) * 1000;
        overviewErrors.delete('agent-watches');
        renderAgentWatches(agentWatchList);
    } catch (err) {
        watchesStatus(err.message, true);
        if (agentWatchList === null) agentWatchList = [];
        overviewErrors.set('agent-watches', ['Watches did not load', 'watches']);
    }
    renderOverview();
}

// The Consensus Watches cost up to ~200 reads; they load when the page opens.
async function loadAdminWatches() {
    consensusWatchesRequested = true;
    watchesStatus('Loading…', false);
    try {
        const data = await shareAdminRequest('GET', '/api/admin/watches');
        const smtp = document.getElementById('smtpConfigState');
        smtp.textContent = data.smtp_configured ? 'Mail ready' : 'Mail not set up';
        smtp.className = 'admin-state ' + (data.smtp_configured ? 'is-ok' : 'is-alert');
        consensusArchived = data.archived !== false;
        adminWatches = data.watches || [];
        renderAdminWatches(adminWatches);
        watchesStatus('', false);
    } catch (err) {
        watchesStatus(err.message, true);
    }
}

document.getElementById('loadWatchesBtn').addEventListener('click', () => {
    loadAgentWatches();
    loadAdminWatches();
});
document.getElementById('sendWatchTestMailBtn').addEventListener('click', async function () {
    if (!confirm('Send a real test e-mail to your admin address?')) return;
    this.disabled = true;
    watchesStatus('Sending…', false);
    try {
        const data = await shareAdminRequest('POST', '/api/admin/watches/test-email', {});
        watchesStatus(`Test e-mail accepted for ${data.recipient}.`, false);
    } catch (err) {
        watchesStatus(err.message, true);
    } finally {
        this.disabled = false;
    }
});

// === Overview ===
// Built from what the other pages load anyway, plus the Agent's daily
// counters (one read per day). Each part draws as soon as its data is there.
let agentDays = null;
let seoOverview = null;
// A part that failed to load says so here instead of looking like "nothing".
const overviewErrors = new Map();
function overviewFailed(key, text, page) {
    overviewErrors.set(key, [text, page]);
    renderOverview();
}

function setCount(page, value) {
    const el = document.querySelector(`.admin-tab-count[data-count="${page}"]`);
    if (el) el.textContent = value ? String(value) : '';
}

function attentionItem(text, page, tone = 'alert') {
    const item = document.createElement('li');
    item.className = `attention-item is-${tone}`;
    const label = document.createElement('span');
    label.textContent = text;
    item.appendChild(label);
    if (page) {
        const go = document.createElement('button');
        go.type = 'button';
        go.className = 'admin-link';
        go.textContent = 'Open';
        go.setAttribute('aria-label', `Open: ${text}`);
        go.addEventListener('click', () => activateTab(page));
        item.appendChild(go);
    }
    return item;
}

function renderAgentDays() {
    const bars = document.getElementById('overviewAgentBars');
    const note = document.getElementById('overviewAgentNote');
    if (!agentDays) return;
    const total = day => Object.values(day.turns || {}).reduce((sum, n) => sum + (Number(n) || 0), 0);
    const today = agentDays[agentDays.length - 1] || { turns: {} };
    document.getElementById('overviewAgentToday').textContent = String(total(today));
    const max = Math.max(1, ...agentDays.map(total));
    bars.innerHTML = '';
    agentDays.forEach(day => {
        const bar = document.createElement('span');
        bar.className = 'overview-bar';
        bar.style.height = `${Math.max(3, Math.round((total(day) / max) * 100))}%`;
        bar.title = `${formatAdminDay(day.day)}: ${total(day)}`;
        bars.appendChild(bar);
    });
    const fortnight = agentDays.reduce((sum, day) => sum + total(day), 0);
    const failed = agentDays.reduce((sum, day) => sum + (Number(day.turns?.failed) || 0), 0);
    note.textContent = `${fortnight} in 14 days` + (failed ? ` · ${failed} failed` : '');
}

function renderOverview() {
    const list = document.getElementById('overviewAttention');
    if (!list) return;
    const items = [];
    if (modelsLoadError) items.push(attentionItem('Model settings did not load', 'models'));
    if (unreviewedShares) {
        items.push(attentionItem(unreviewedShares === 1 ? '1 reported page waits for review'
            : `${unreviewedShares} reported pages wait for review`, 'pages'));
    }
    const failing = (agentWatchList || []).filter(agentWatchFailing);
    if (failing.length) {
        items.push(attentionItem(failing.length === 1 ? 'The last look of 1 Watch failed' : `The last look of ${failing.length} Watches failed`, 'watches'));
    }
    const overdue = (agentWatchList || []).filter(agentWatchOverdue);
    if (overdue.length) {
        items.push(attentionItem(overdue.length === 1 ? '1 Watch is overdue' : `${overdue.length} Watches are overdue`, 'watches', 'warn'));
    }
    if (seoOverview?.report?.error) items.push(attentionItem('The last SEO pulse failed', 'seo'));
    overviewErrors.forEach(([text, page]) => items.push(attentionItem(text, page, 'warn')));
    setCount('pages', unreviewedShares);
    setCount('watches', new Set([...failing, ...overdue]).size);

    const loaded = unreviewedShares !== null && agentWatchList !== null && seoOverview !== null;
    list.innerHTML = '';
    if (items.length) items.forEach(item => list.appendChild(item));
    else list.appendChild(attentionItem(loaded ? 'Nothing needs you.' : 'Looking…', '', loaded ? 'ok' : 'quiet'));

    if (elevatedAccounts) {
        const plus = elevatedAccounts.filter(account => account.tier === 'plus').length;
        const pro = elevatedAccounts.filter(account => account.tier === 'pro').length;
        document.getElementById('overviewAccountsPaid').textContent = String(plus + pro);
        document.getElementById('overviewAccountsPaid').title = `${plus} Plus, ${pro} Pro`;
    }
    const report = seoOverview?.report;
    if (report && !report.error) {
        document.getElementById('overviewSearchImpressions').textContent = String(report.week?.impressions ?? '–');
        const clicks = report.week?.clicks ?? 0;
        document.getElementById('overviewSearchNote').textContent =
            `${seoChange(report.week?.impressions || 0, report.prev_week?.impressions || 0).replace('prev', 'week before')} · ${clicks} ${clicks === 1 ? 'click' : 'clicks'}`;
    } else if (seoOverview) {
        document.getElementById('overviewSearchNote').textContent = report?.error ? 'Last run failed.' : 'No report yet.';
    }
    renderAgentDays();
}

async function loadOverview() {
    document.getElementById('overviewDate').textContent = new Date().toLocaleDateString('en-GB',
        { weekday: 'long', day: 'numeric', month: 'long' });
    try {
        const data = await shareAdminRequest('GET', '/api/admin/overview');
        agentDays = data.agent_days || [];
    } catch (err) {
        document.getElementById('overviewAgentNote').textContent = err.message;
    }
    renderOverview();
}

document.getElementById('overviewFindForm').addEventListener('submit', event => {
    event.preventDefault();
    const value = document.getElementById('overviewFind').value.trim();
    if (value) openAccount(value);
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
    document.getElementById('adminTopicBenchmark').value =
        ((topic.benchmark || {}).models || []).join('\n');
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
        benchmark: { models: topicLines(document.getElementById('adminTopicBenchmark').value) },
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
    el.className = 'admin-status' + (message ? (isError ? ' error' : ' success') : '');
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
        li.className = 'admin-empty';
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
    const count = document.getElementById('seoPulseNoindexedCount');
    if (count) count.textContent = entries.length ? String(entries.length) : '';
    box.innerHTML = '';
    box.classList.toggle('admin-empty', !entries.length);
    if (!entries.length) {
        box.textContent = 'None so far.';
        return;
    }
    entries.forEach(entry => {
        const row = document.createElement('div');
        row.className = 'admin-row seo-pulse-row';
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
        keep.className = 'admin-btn quiet';
        const main = document.createElement('div');
        main.className = 'admin-row-main';
        link.className = 'admin-row-title';
        meta.className = 'admin-row-meta';
        main.append(link, meta);
        row.append(main, keep);
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
        const data = await shareAdminRequest('GET', '/api/admin/seo');
        renderSeoPulse(data);
        seoStatus('', false);
        seoOverview = data;
        overviewErrors.delete('seo');
    } catch (err) {
        seoStatus(err.message, true);
        seoOverview = seoOverview || {};
        overviewErrors.set('seo', ['Search data did not load', 'seo']);
    }
    renderOverview();
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
        loadOverview();
        loadShares('reported');
        loadAgentWatches();
        if (currentPage === 'watches') loadAdminWatches();
        loadSeoPulse();
        loadAccountTiers();
        loadApiKeys();
        loadAdminTopics();
    } else {
        window.location.href = '/';
    }
});
