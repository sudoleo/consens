// Daily token allowance (one account for Compare, Consensus, Deep Think and
// Agent): limit per tier and the expected tokens of a typical run per tier and
// mode, which is the admission threshold of the pipeline. Revision-guarded like
// before; the global reset stays a separate product action.
const TIERS = [['free', 'Free'], ['plus', 'Plus'], ['pro', 'Pro'], ['admin', 'Admin']];
const MODES = [['compare', 'Compare run'], ['consensus', 'Consensus run'], ['deep_think', 'Deep Think run']];

export function createAgentBudgetPanel(request) {
    const form = document.getElementById('agentBudgetForm');
    const rows = document.getElementById('agentBudgetRows');
    const save = document.getElementById('saveAgentBudget');
    const reset = document.getElementById('resetAgentBudgets');
    const reload = document.getElementById('reloadAgentBudget');
    const status = document.getElementById('agentBudgetStatus');
    const meta = document.getElementById('agentBudgetMeta');
    let user = null, generation = 0, saved = null, busy = false;

    function input(id, label, max) {
        const field = document.createElement('input');
        field.type = 'number';
        field.id = id;
        field.min = '1';
        field.max = String(max);
        field.step = '1';
        field.required = true;
        field.disabled = true;
        field.inputMode = 'numeric';
        field.setAttribute('aria-label', label);
        return field;
    }
    // Rows are built once; the table scrolls inside its own box on phones.
    for (const [tier, tierLabel] of TIERS) {
        const row = document.createElement('tr');
        row.dataset.tier = tier;
        const head = document.createElement('th');
        head.scope = 'row';
        head.textContent = tierLabel;
        row.append(head);
        const limitCell = document.createElement('td');
        limitCell.append(input(`budgetLimit-${tier}`, `${tierLabel} tokens per day`, 100000000));
        row.append(limitCell);
        for (const [mode, modeLabel] of MODES) {
            const cell = document.createElement('td');
            cell.append(input(`budgetEstimate-${tier}-${mode}`, `${tierLabel} ${modeLabel} estimate`, 10000000));
            row.append(cell);
        }
        rows?.append(row);
    }
    const fields = () => Array.from(form.querySelectorAll('input[type="number"]'));

    function draft() {
        const tier_limits = {}, run_estimates = {};
        for (const [tier] of TIERS) {
            tier_limits[tier] = Number(document.getElementById(`budgetLimit-${tier}`).value);
            run_estimates[tier] = {};
            for (const [mode] of MODES) run_estimates[tier][mode] = Number(document.getElementById(`budgetEstimate-${tier}-${mode}`).value);
        }
        return { tier_limits, run_estimates };
    }
    function changed() {
        if (!saved) return false;
        const next = draft();
        return TIERS.some(([tier]) => next.tier_limits[tier] !== saved.tier_limits?.[tier]
            || MODES.some(([mode]) => next.run_estimates[tier][mode] !== saved.run_estimates?.[tier]?.[mode]));
    }
    function sync() {
        for (const field of fields()) field.disabled = !user || busy || !saved;
        save.disabled = !user || busy || !saved || !changed();
        reset.disabled = !user || busy || !saved;
        reload.disabled = !user || busy;
    }
    function display(config) {
        saved = config;
        for (const [tier] of TIERS) {
            document.getElementById(`budgetLimit-${tier}`).value = config.tier_limits?.[tier] ?? '';
            for (const [mode] of MODES) {
                document.getElementById(`budgetEstimate-${tier}-${mode}`).value = config.run_estimates?.[tier]?.[mode] ?? '';
            }
        }
        meta.textContent = `Revision ${config.revision}` + (config.reset_at ? ` · Last reset: ${new Date(config.reset_at).toLocaleString()}` : ' · No manual reset');
    }
    async function perform(method, path, body, message) {
        if (!user || busy) return;
        const owner = generation;
        busy = true; sync(); status.textContent = 'Updating…'; status.classList.remove('is-error');
        try {
            const result = await request(method, path, body);
            if (owner !== generation) return;
            display(result.config); status.textContent = message;
        } catch (error) {
            if (owner === generation) { status.textContent = error.message; status.classList.add('is-error'); }
        } finally {
            if (owner === generation) { busy = false; sync(); }
        }
    }
    form.addEventListener('input', sync);
    form.addEventListener('submit', event => {
        event.preventDefault();
        if (!saved || busy || !form.reportValidity()) return;
        return perform('PUT', '/api/admin/agent-budget', { revision: saved.revision, ...draft() },
            'Allowance saved. Applies to every account within 30 seconds.');
    });
    reload.addEventListener('click', () => perform('GET', '/api/admin/agent-budget', null, ''));
    reset.addEventListener('click', () => {
        if (!saved || busy) return;
        // This is a product action affecting every account, distinct from Save.
        if (!window.confirm('Reset today’s token allowance for every account? Work already started keeps its previous accounting.')) return;
        return perform('POST', '/api/admin/agent-budget/reset', { revision: saved.revision },
            'All allowances reset. Applies within 30 seconds; usage history is preserved.');
    });
    sync();
    return { setUser(uid) {
        generation++; user = uid; saved = null; busy = false;
        for (const field of fields()) field.value = '';
        meta.textContent = ''; status.textContent = ''; sync();
        if (uid) return perform('GET', '/api/admin/agent-budget', null, '');
    } };
}
