import { readFileSync } from 'node:fs';
import path from 'node:path';
import { expect, it, vi } from 'vitest';
import { JSDOM } from 'jsdom';
import { ROOT } from './helpers/appWindow.mjs';

function boot(request) {
  const dom = new JSDOM(readFileSync(path.join(ROOT, 'templates/admin.html'), 'utf8'), {runScripts:'outside-only'});
  const source = readFileSync(path.join(ROOT, 'static/js/admin-agent-budget.js'), 'utf8').replace('export function', 'function');
  // const at top level stays script-local; expose the factory explicitly.
  dom.window.eval(source + '\nwindow.createAgentBudgetPanel = createAgentBudgetPanel;');
  dom.window.confirm = vi.fn(() => true);
  return {dom, w:dom.window, d:dom.window.document, panel:dom.window.createAgentBudgetPanel(request)};
}
// Micro-euros, as the API speaks them; the fields show euros.
const estimates = {compare:60000, consensus:100000, deep_think:200000};
const config = {
  tier_limits:{free:1000000, plus:2500000, pro:5000000, admin:5000000},
  run_estimates:{free:estimates, plus:estimates, pro:estimates, admin:estimates},
  revision:1, reset_epoch:'',
};

it('renders one row per tier and saves limits and run estimates apart from the global reset', async () => {
  let finish;
  const request = vi.fn(async (method, _path, body) => {
    if(method === 'GET') return {config};
    if(method === 'POST') return new Promise(resolve => {finish=resolve;});
    return {config:{...config, ...body, revision:2}};
  });
  const {dom,w,d,panel} = boot(request); await panel.setUser('admin');
  expect([...d.querySelectorAll('#agentBudgetRows tr')].map(row => row.dataset.tier)).toEqual(['free','plus','pro','admin']);
  expect(d.getElementById('budgetLimit-plus').value).toBe('2.5');
  expect(d.getElementById('budgetEstimate-free-compare').value).toBe('0.06');
  const save = d.getElementById('saveAgentBudget');
  expect(save.disabled).toBe(true); // nothing changed yet
  const limit = d.getElementById('budgetLimit-free');
  limit.value = '0.8'; limit.dispatchEvent(new w.Event('input', {bubbles:true}));
  const deep = d.getElementById('budgetEstimate-pro-deep_think');
  deep.value = '0.45'; deep.dispatchEvent(new w.Event('input', {bubbles:true}));
  expect(save.disabled).toBe(false);
  d.getElementById('agentBudgetForm').dispatchEvent(new w.Event('submit',{cancelable:true}));
  await vi.waitFor(() => expect(d.getElementById('agentBudgetStatus').textContent).toContain('saved'));
  const [method, url, body] = request.mock.calls[1];
  expect([method, url, body.revision]).toEqual(['PUT','/api/admin/agent-budget',1]);
  expect(body.tier_limits).toEqual({...config.tier_limits, free:800000});
  expect(body.run_estimates.pro).toEqual({...estimates, deep_think:450000});
  const reset = d.getElementById('resetAgentBudgets'); reset.click(); reset.click();
  expect(request.mock.calls.filter(([m])=>m==='POST')).toHaveLength(1);
  expect(reset.disabled).toBe(true);
  finish({config:{...config, tier_limits:body.tier_limits, revision:3, reset_epoch:'a'.repeat(32)}});
  await vi.waitFor(() => expect(d.getElementById('agentBudgetStatus').textContent).toContain('All allowances reset'));
  expect(limit.value).toBe('0.8');
  dom.window.close();
});

it('preserves the draft on failure and ignores an old account response', async () => {
  let finish;
  const request = vi.fn(async method => {
    if(method === 'PUT') throw new Error('Revision conflict');
    return {config};
  });
  const {dom,w,d,panel} = boot(request); await panel.setUser('admin');
  d.getElementById('budgetLimit-free').value = '0.5';
  d.getElementById('agentBudgetForm').dispatchEvent(new w.Event('submit',{cancelable:true}));
  await vi.waitFor(() => expect(d.getElementById('agentBudgetStatus').textContent).toBe('Revision conflict'));
  expect(d.getElementById('budgetLimit-free').value).toBe('0.5');
  request.mockImplementationOnce(() => new Promise(resolve => {finish = resolve;}));
  const pending = panel.setUser('admin'); panel.setUser(null); finish({config}); await pending;
  expect(d.getElementById('budgetLimit-free').value).toBe('');
  expect(d.getElementById('resetAgentBudgets').disabled).toBe(true);
  dom.window.close();
});
