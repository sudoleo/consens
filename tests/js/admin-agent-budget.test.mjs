import { readFileSync } from 'node:fs';
import path from 'node:path';
import { expect, it, vi } from 'vitest';
import { JSDOM } from 'jsdom';
import { ROOT } from './helpers/appWindow.mjs';

function boot(request) {
  const dom = new JSDOM(readFileSync(path.join(ROOT, 'templates/admin.html'), 'utf8'), {runScripts:'outside-only'});
  dom.window.eval(readFileSync(path.join(ROOT, 'static/js/admin-agent-budget.js'), 'utf8').replace('export function', 'function'));
  dom.window.confirm = vi.fn(() => true);
  return {dom, w:dom.window, d:dom.window.document, panel:dom.window.createAgentBudgetPanel(request)};
}
const config = {daily_token_limit:250000,revision:1,reset_epoch:''};

it('saves the limit separately from the revision-guarded global reset', async () => {
  let finish;
  const request = vi.fn(async (method, _path, body) => {
    if(method === 'GET') return {config};
    if(method === 'POST') return new Promise(resolve => {finish=resolve;});
    return {config:{...config,daily_token_limit:body.daily_token_limit,revision:2}};
  });
  const {dom,w,d,panel} = boot(request); await panel.setUser('admin');
  const input = d.getElementById('agentDailyTokenLimit');
  input.value = '400000'; input.dispatchEvent(new w.Event('input'));
  d.getElementById('agentBudgetForm').dispatchEvent(new w.Event('submit',{cancelable:true}));
  await vi.waitFor(() => expect(d.getElementById('agentBudgetStatus').textContent).toContain('saved'));
  expect(request.mock.calls[1]).toEqual(['PUT','/api/admin/agent-budget',{revision:1,daily_token_limit:400000}]);
  const reset = d.getElementById('resetAgentBudgets'); reset.click(); reset.click();
  expect(request.mock.calls.filter(([method])=>method==='POST')).toHaveLength(1);
  expect(reset.disabled).toBe(true);
  finish({config:{...config,revision:3,daily_token_limit:400000,reset_epoch:'a'.repeat(32)}});
  await vi.waitFor(() => expect(d.getElementById('agentBudgetStatus').textContent).toContain('All Agent budgets reset'));
  expect(input.value).toBe('400000');
  dom.window.close();
});

it('preserves the draft on failure and ignores an old account response', async () => {
  let finish;
  const request = vi.fn(async method => {
    if(method === 'PUT') throw new Error('Revision conflict');
    return {config};
  });
  const {dom,w,d,panel} = boot(request); await panel.setUser('admin');
  d.getElementById('agentDailyTokenLimit').value = '500000';
  d.getElementById('agentBudgetForm').dispatchEvent(new w.Event('submit',{cancelable:true}));
  await vi.waitFor(() => expect(d.getElementById('agentBudgetStatus').textContent).toBe('Revision conflict'));
  expect(d.getElementById('agentDailyTokenLimit').value).toBe('500000');
  request.mockImplementationOnce(() => new Promise(resolve => {finish = resolve;}));
  const pending = panel.setUser('admin'); panel.setUser(null); finish({config}); await pending;
  expect(d.getElementById('agentDailyTokenLimit').value).toBe('');
  expect(d.getElementById('resetAgentBudgets').disabled).toBe(true);
  dom.window.close();
});
