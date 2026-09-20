import { describe, expect, it, vi } from 'vitest';
import { loadScripts } from './helpers/appWindow.mjs';

describe('Request deadlines', () => {
  it('aborts a stalled request and allows another attempt', async () => {
    const { window: w, dom } = loadScripts(['static/js/request-deadline.js']);
    let signal;
    await expect(w.App.withRequestDeadline(s => { signal = s; return new Promise(() => {}); }, { timeoutMs: 10 }))
      .rejects.toThrow('taking too long');
    expect(signal.aborted).toBe(true);
    expect(await w.App.withRequestDeadline(async () => 'recovered')).toBe('recovered');
    dom.window.close();
  });
  it('preserves cancellation and never dispatches an already cancelled operation', async () => {
    const { window: w, dom } = loadScripts(['static/js/request-deadline.js']);
    const controller = new w.AbortController(); controller.abort();
    const operation = vi.fn();
    await expect(w.App.withRequestDeadline(operation, { signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' });
    expect(operation).not.toHaveBeenCalled();
    dom.window.close();
  });
  it('renews streaming liveness and removes timers after completion', async () => {
    const { window: w, dom } = loadScripts(['static/js/request-deadline.js']);
    const timers = new Map(); let id = 0, touch;
    w.setTimeout = vi.fn(fn => { timers.set(++id, fn); return id; });
    w.clearTimeout = vi.fn(key => timers.delete(key));
    const result = await w.App.withRequestDeadline(async (signal, progress) => {
      touch = progress;
      for (let i = 0; i < 10; i++) { progress(); expect(timers.size).toBe(1); }
      return 'done';
    });
    expect(result).toBe('done'); expect(timers.size).toBe(0);
    touch(); expect(timers.size).toBe(0);
    dom.window.close();
  });
});
