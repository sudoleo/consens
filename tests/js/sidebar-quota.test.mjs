import { expect, it } from 'vitest';
import { loadScripts } from './helpers/appWindow.mjs';

it('projects remaining Agent tokens into the existing ring without changing Consensus quotas', () => {
  let agent = false, budget = { remaining: 188878, limit: 250000 };
  const ctx = loadScripts(['static/js/sidebar-quota.js'], { body: `
    <div id="usageDisplay"><span id="freeUsageDisplay"><strong>2 / 3</strong></span>
    <span id="deepUsageDisplay"><strong>1 / 2</strong></span><span id="watchUsageDisplay"><strong>3 / 5</strong></span>
    <span id="countdownDisplay">Resets soon</span></div>
    <button id="quotaTrigger"><span id="quotaTriggerValue"></span><svg><circle id="quotaRingArc"/></svg></button>
    <section id="sidebarQuota"><div id="quotaRowRuns"><b>Runs</b><span id="quotaRunsValue"></span><div class="quota-track"><i></i></div></div>
    <div id="quotaRowDeep"><span id="quotaDeepValue"></span></div><div id="quotaRowWatch"><span id="quotaWatchValue"></span></div>
    <p id="quotaFoot"></p></section>`, before(w) {
      w.App = { agentChat: { isSelected: () => agent, tokenBudget: () => budget } };
    } });
  const {document: d, window: w} = ctx;
  w.App.sidebarQuota.sync(); expect(d.getElementById('quotaTriggerValue').textContent).toBe('2');
  agent = true; w.App.sidebarQuota.sync();
  expect(d.getElementById('quotaTriggerValue').textContent).toBe('75%');
  expect(d.getElementById('quotaTrigger').getAttribute('aria-label')).toContain('daily Agent token budget left');
  expect(d.getElementById('quotaRowDeep').hidden).toBe(true);
  expect(w.App.sidebarQuota.runs()).toEqual({value: 2, limit: 3});
  budget = {used: 50000, remaining: 80000, reserved: 120000, limit: 250000};
  w.App.sidebarQuota.sync(); expect(d.getElementById('quotaTriggerValue').textContent).toBe('80%');
  expect(d.getElementById('quotaFoot').textContent).toContain('temporarily reserved');
  budget = {...budget, remaining: 200000, reserved: 0};
  w.App.sidebarQuota.sync(); expect(d.getElementById('quotaTriggerValue').textContent).toBe('80%');
  budget = {remaining: 188878, limit: 250000};
  budget.remaining = 0; w.App.sidebarQuota.sync(); expect(d.getElementById('quotaTriggerValue').textContent).toBe('0%');
  budget.remaining = 300000; w.App.sidebarQuota.sync(); expect(d.getElementById('quotaTriggerValue').textContent).toBe('100%');
  budget = null; w.App.sidebarQuota.sync(); expect(d.getElementById('quotaTrigger').hidden).toBe(true);
  agent = false; w.App.sidebarQuota.sync();
  expect(d.getElementById('quotaTriggerValue').textContent).toBe('2');
  expect(d.getElementById('quotaRowDeep').hidden).toBe(false);
  expect(d.getElementById('quotaFoot').textContent).toBe('Resets soon');
  ctx.dom.window.close();
});
