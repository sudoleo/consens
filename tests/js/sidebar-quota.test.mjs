import { expect, it } from 'vitest';
import { loadScripts } from './helpers/appWindow.mjs';

const MARKUP = `
  <div id="usageDisplay"><span id="watchUsageDisplay"><strong>3 / 5</strong></span><span id="countdownDisplay"></span></div>
  <input type="checkbox" id="reasoningToggle">
  <section id="sidebarQuota">
    <span id="quotaPlanLabel">Free</span>
    <div id="quotaPrimary" hidden><span id="quotaPercent"></span>
      <div id="quotaTrack"><i></i></div><p id="quotaReset"></p></div>
    <p id="quotaDetail" hidden></p>
    <div id="quotaRowWatch" hidden><span id="quotaWatchValue"></span></div>
    <p id="quotaFoot" hidden></p>
  </section>
  <button id="quotaTrigger" hidden><svg><circle id="quotaRingArc"/></svg></button>`;

function boot({ mode = 'consensus' } = {}) {
  const ctx = loadScripts(['static/js/token-budget.js', 'static/js/sidebar-quota.js'], {
    body: MARKUP,
    before(w) {
      w.auth = { currentUser: { uid: 'u1' } };
      w.App = { runMode: { effective: () => mode } };
    }
  });
  return { ...ctx, d: ctx.document, w: ctx.window };
}

const estimates = { compare: 32000, consensus: 55000, deep_think: 150000 };

it('shows one quiet ring for the shared account, the value only in label and panel', () => {
  const { d, w, dom } = boot();
  const trigger = d.getElementById('quotaTrigger');
  // Nothing known yet: no ring, no invented number.
  w.App.sidebarQuota.sync();
  expect(trigger.hidden).toBe(true);

  w.App.tokenBudget.apply({ limit: 660000, used: 250800, estimated: 0, reserved: 0, remaining: 409200,
    revision: 3, day: '2026-10-01', run_estimates: estimates });
  expect(trigger.hidden).toBe(false);
  // No text inside the ring at all.
  expect(trigger.textContent.trim()).toBe('');
  expect(trigger.getAttribute('aria-label')).toMatch(/^62% of today’s allowance left · resets /);
  expect(d.getElementById('quotaRingArc').getAttribute('stroke')).toBe('var(--ink-2)');
  expect(d.getElementById('quotaRingArc').getAttribute('stroke-dashoffset')).toBe('38.00');

  expect(d.getElementById('quotaPrimary').hidden).toBe(false);
  expect(d.getElementById('quotaPercent').textContent).toBe('62%');
  expect(d.getElementById('quotaReset').textContent).toMatch(/^Resets at .+ · in /);
  expect(d.getElementById('quotaDetail').textContent).toBe('409k of 660k tokens · a Consensus run uses about 8%');
  // The Reasoning switch shows its own (larger) run, under its new name.
  const reasoning = d.getElementById('reasoningToggle');
  reasoning.checked = true;
  w.App.sidebarQuota.sync();
  expect(d.getElementById('quotaDetail').textContent).toBe('409k of 660k tokens · a Reasoning run uses about 23%');
  reasoning.checked = false;
  w.App.sidebarQuota.sync();
  expect(d.getElementById('quotaWatchValue').textContent).toBe('3 / 5');
  expect(d.getElementById('quotaFoot').hidden).toBe(true);
  dom.window.close();
});

it('turns only the arc and the bar amber or red, and explains holds and estimates', () => {
  const { d, w, dom } = boot();
  w.App.tokenBudget.apply({ limit: 660000, used: 500000, estimated: 10000, reserved: 55000, remaining: 95000,
    revision: 4, day: '2026-10-01', run_estimates: estimates });
  expect(d.getElementById('quotaPercent').textContent).toBe('22%');
  expect(d.getElementById('quotaRingArc').getAttribute('stroke')).toBe('var(--partial)');
  expect(d.getElementById('quotaTrack').dataset.state).toBe('low');
  expect(d.getElementById('quotaFoot').textContent).toContain('55k held for work in progress.');
  expect(d.getElementById('quotaFoot').textContent).toContain('10k estimated until the provider reports');

  // Small remainders are "<1%", an overdrawn account is 0% and red.
  w.App.tokenBudget.apply({ limit: 660000, used: 657700, remaining: 2300, revision: 5, day: '2026-10-01' });
  expect(d.getElementById('quotaPercent').textContent).toBe('<1%');
  w.App.tokenBudget.apply({ limit: 660000, used: 700000, remaining: 0, revision: 6, day: '2026-10-01' });
  expect(d.getElementById('quotaPercent').textContent).toBe('0%');
  expect(d.getElementById('quotaRingArc').getAttribute('stroke')).toBe('var(--dispute)');
  expect(d.getElementById('quotaFoot').textContent).toContain('share this allowance');
  dom.window.close();
});

it('orders concurrent snapshots and fences other accounts', () => {
  const { w, dom } = boot();
  const api = w.App.tokenBudget;
  expect(api.apply({ limit: 1000, used: 100, revision: 5, day: '2026-10-01' })).toBe(true);
  // An older revision of the same day never overwrites a newer one.
  expect(api.apply({ limit: 1000, used: 50, revision: 4, day: '2026-10-01' })).toBe(false);
  expect(api.current().used).toBe(100);
  // A new UTC day or an authoritative read wins.
  expect(api.apply({ limit: 1000, used: 0, revision: 1, day: '2026-10-02' })).toBe(true);
  expect(api.apply({ limit: 1000, used: 10, revision: 0, day: '2026-10-02' }, { authoritative: true })).toBe(true);
  // A late answer of another login is ignored; invalid snapshots too.
  expect(api.apply({ limit: 1000, used: 999, revision: 9, day: '2026-10-02' }, { uid: 'someone-else' })).toBe(false);
  expect(api.apply({ limit: 0, used: 1 })).toBe(false);
  expect(api.fromResponse({ detail: { token_budget: { limit: 1000, used: 20, revision: 2, day: '2026-10-02' } } })).toBe(true);
  expect(api.current().used).toBe(20);
  dom.window.close();
});

it('admits a run like the server: available tokens against the mode estimate', () => {
  const { w, dom } = boot({ mode: 'compare' });
  const api = w.App.tokenBudget;
  expect(api.canStart('consensus')).toBe(null);
  api.apply({ limit: 660000, used: 600000, reserved: 10000, remaining: 50000, revision: 1, day: '2026-10-01',
    run_estimates: estimates });
  expect(api.canStart('compare')).toBe(true);
  expect(api.canStart('consensus')).toBe(false);
  expect(api.runShare('deep_think')).toBe('23%');
  expect(api.formatTokens(1650000)).toBe('1.7M');
  expect(api.formatTokens(5000000)).toBe('5M');
  dom.window.close();
});
