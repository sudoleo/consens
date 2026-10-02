import { describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

function boot({ width = 350, measure = () => 52 } = {}) {
  const frames = new Map();
  let sequence = 0, onResize;
  const app = loadScripts(["static/js/composer-autosize.js"], {
    body: '<div class="chat-input-container"><textarea style="min-height:52px;max-height:180px" placeholder="Enter your question"></textarea></div>',
    before(window) {
      window.requestAnimationFrame = callback => {
        const id = ++sequence; frames.set(id, callback); return id;
      };
      window.ResizeObserver = class {
        constructor(callback) { onResize = callback; }
        observe() {}
      };
    },
  });
  const field = app.document.querySelector('textarea');
  field.getBoundingClientRect = () => ({ width });
  Object.defineProperty(field, 'scrollHeight', { get: () => measure(width, field) });
  const resize = app.window.App.initComposerAutosize(field);
  return { ...app, field, resize, frames,
    tick() { const callbacks = [...frames.values()]; frames.clear(); callbacks.forEach(callback => callback()); },
    geometry(nextWidth = width) { width = nextWidth; onResize(); },
    input(text) { field.value = text; field.dispatchEvent(new app.window.Event('input')); },
  };
}

describe('composer autosize', () => {
  it('shrinks a wrapped placeholder when the actual width finishes changing without another viewport event', () => {
    const app = boot({ width: 90, measure: width => width < 300 ? 190 : 52 });
    app.tick();
    expect(app.field.style.height).toBe('180px');
    expect(app.field.style.overflowY).toBe('auto');
    app.geometry(350);
    expect(app.field.style.height).toBe('180px');
    app.tick();
    expect(app.field.style.height).toBe('52px');
    expect(app.field.style.overflowY).toBe('hidden');
    app.dom.window.close();
  });

  it('coalesces width observations and ignores height-only notifications from its own writes', () => {
    const app = boot(); app.tick();
    app.geometry(250); app.geometry(300); app.geometry(320);
    expect(app.frames.size).toBe(1);
    app.tick();
    app.geometry();
    expect(app.frames.size).toBe(0);
    app.field.style.height = '120px';
    app.geometry();
    expect(app.frames.size).toBe(0);
    app.dom.window.close();
  });

  it('keeps the multiline form while editing and resets it only when empty', () => {
    let height = 52;
    const app = boot({ measure: () => height }); app.tick();
    height = 440; app.input('Several lines');
    expect(app.field.style.height).toBe('180px');
    expect(app.field.style.overflowY).toBe('auto');
    expect(app.field.parentElement.classList.contains('is-multiline')).toBe(true);
    height = 52; app.input('Shorter');
    expect(app.field.parentElement.classList.contains('is-multiline')).toBe(true);
    app.input('');
    expect(app.field.parentElement.classList.contains('is-multiline')).toBe(false);
    expect(app.field.style.height).toBe('52px');
    expect(app.field.style.overflowY).toBe('hidden');
    app.dom.window.close();
  });

  it('still responds to placeholder changes and explicit viewport changes', async () => {
    const app = boot({ measure: (_, field) => field.placeholder.length > 30 ? 190 : 52 });
    app.tick();
    app.field.placeholder = 'A long authentication instruction for an empty input';
    await Promise.resolve();
    expect(app.field.style.height).toBe('180px');
    app.field.placeholder = 'Question';
    await Promise.resolve();
    expect(app.field.style.height).toBe('52px');
    app.field.style.maxHeight = '40px'; app.field.style.minHeight = '20px';
    app.window.dispatchEvent(new app.window.Event('resize'));
    expect(app.field.style.height).toBe('40px');
    expect(app.field.style.overflowY).toBe('auto');
    app.dom.window.close();
  });
});
