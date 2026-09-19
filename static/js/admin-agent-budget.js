export function createAgentBudgetPanel(request) {
    const form = document.getElementById('agentBudgetForm');
    const input = document.getElementById('agentDailyTokenLimit');
    const save = document.getElementById('saveAgentBudget');
    const reset = document.getElementById('resetAgentBudgets');
    const reload = document.getElementById('reloadAgentBudget');
    const status = document.getElementById('agentBudgetStatus');
    const meta = document.getElementById('agentBudgetMeta');
    let user = null, generation = 0, saved = null, busy = false;
    function sync() {
        input.disabled = !user || busy || !saved;
        save.disabled = !user || busy || !saved || (saved.revision > 0 && Number(input.value) === saved.daily_token_limit);
        reset.disabled = !user || busy || !saved;
        reload.disabled = !user || busy;
    }
    function display(config) {
        saved = config;
        input.value = config.daily_token_limit;
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
    input.addEventListener('input', sync);
    form.addEventListener('submit', event => {
        event.preventDefault();
        if (!saved || busy || !form.reportValidity()) return;
        return perform('PUT', '/api/admin/agent-budget', { revision: saved.revision, daily_token_limit: Number(input.value) },
            'Daily budget saved. Applies to all Agent accounts within 30 seconds.');
    });
    reload.addEventListener('click', () => perform('GET', '/api/admin/agent-budget', null, ''));
    reset.addEventListener('click', () => {
        if (!saved || busy) return;
        // This is a product action affecting every account, distinct from Save.
        if (!window.confirm('Reset the Agent token budget for every account? Calls already started keep their previous accounting.')) return;
        return perform('POST', '/api/admin/agent-budget/reset', { revision: saved.revision },
            'All Agent budgets reset. Applies within 30 seconds; usage history is preserved.');
    });
    sync();
    return { setUser(uid) {
        generation++; user = uid; saved = null; busy = false;
        input.value = ''; meta.textContent = ''; status.textContent = ''; sync();
        if (uid) return perform('GET', '/api/admin/agent-budget', null, '');
    } };
}
