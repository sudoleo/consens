import { describe, expect, it, vi } from 'vitest';
import { loadScripts } from './helpers/appWindow.mjs';

function boot() {
  return loadScripts(['static/js/agent-answer-actions.js'], {
    body: '<div id="answer"></div><textarea id="questionInput">My next question</textarea>',
    before(window) {
      Object.defineProperty(window.navigator, 'clipboard', { configurable: true, value: { writeText: vi.fn().mockResolvedValue() } });
    },
  });
}

describe('Agent answer actions', () => {
  it('copies only the canonical answer and keeps controls stable across projections', async () => {
    const { window: w, document: d, dom } = boot();
    const body = d.getElementById('answer');
    body.innerHTML = '<p>Answer <button>Review badge</button></p>';
    const state = {key: 'first', text: '**Answer** with [source](https://example.com)'};
    w.App.agentAnswerActions.render(body, state);
    const copy = d.querySelector('.agent-answer-actions button');
    copy.focus();
    copy.click();
    await vi.waitFor(() => expect(d.querySelector('[role="status"]').textContent).toBe('Copied'));
    expect(w.navigator.clipboard.writeText).toHaveBeenCalledWith(state.text);
    w.App.agentAnswerActions.render(body, state);
    expect(d.activeElement).toBe(copy);
    expect(d.querySelector('[role="status"]').textContent).toBe('Copied');
    expect(d.querySelectorAll('.agent-answer-actions button')).toHaveLength(1);
    dom.window.close();
  });

  it('hides incomplete streams, preserves partial answers after stop and separates archived turns', () => {
    const { window: w, document: d, dom } = boot();
    const body = d.getElementById('answer');
    w.App.agentAnswerActions.render(body, {key: 'live', text: 'Partial', running: true});
    expect(body.nextElementSibling.hidden).toBe(true);
    w.App.agentAnswerActions.render(body, {key: 'live', text: 'Partial', running: false});
    expect(body.nextElementSibling.hidden).toBe(false);
    expect(body.nextElementSibling.querySelectorAll('button')).toHaveLength(1);
    w.App.agentAnswerActions.render(body, {key: 'empty', text: ''});
    expect(body.nextElementSibling.hidden).toBe(true);
    dom.window.close();
  });

  it('does not apply late clipboard feedback to a different answer and allows retry after denial', async () => {
    const { window: w, document: d, dom } = boot();
    const body = d.getElementById('answer');
    let finish;
    w.navigator.clipboard.writeText.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    w.App.agentAnswerActions.render(body, {key: 'one', text: 'One'});
    const copy = body.nextElementSibling.querySelector('button');
    copy.click();
    w.App.agentAnswerActions.render(body, {key: 'two', text: 'Two'});
    finish();
    await Promise.resolve(); await Promise.resolve();
    expect(d.querySelector('[role="status"]').textContent).toBe('');
    w.navigator.clipboard.writeText.mockRejectedValueOnce(new Error('Denied'));
    copy.click();
    await vi.waitFor(() => expect(d.querySelector('[role="status"]').textContent).toContain('Could not copy'));
    expect(copy.disabled).toBe(false);
    copy.click();
    await vi.waitFor(() => expect(d.querySelector('[role="status"]').textContent).toBe('Copied'));
    expect(w.navigator.clipboard.writeText).toHaveBeenLastCalledWith('Two');
    dom.window.close();
  });

  it('checks fallback clipboard success and returns keyboard focus', async () => {
    const { window: w, document: d, dom } = boot();
    Object.defineProperty(w.navigator, 'clipboard', { value: undefined });
    d.execCommand = vi.fn(() => false);
    w.App.agentAnswerActions.render(d.getElementById('answer'), {text: 'Answer'});
    const copy = d.querySelector('.agent-answer-actions button');
    copy.focus(); copy.click();
    await vi.waitFor(() => expect(d.querySelector('[role="status"]').textContent).toContain('Could not copy'));
    expect(d.querySelector('.agent-copy-buffer')).toBeNull();
    expect(d.activeElement).toBe(copy);
    d.execCommand.mockReturnValue(true);
    copy.click();
    await vi.waitFor(() => expect(d.querySelector('[role="status"]').textContent).toBe('Copied'));
    dom.window.close();
  });
});
