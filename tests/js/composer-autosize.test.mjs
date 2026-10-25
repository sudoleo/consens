import { describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// The field is measured in a hidden twin (composer-autosize.js): `measure`
// answers the twin's scrollHeight from its width and its text or hint.
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
      Object.defineProperty(window.HTMLTextAreaElement.prototype, 'scrollHeight', {
        configurable: true,
        get() { return this.classList.contains('input-field-twin') ? measure(Number.parseFloat(this.style.width), this) : 0; },
      });
    },
  });
  const field = app.document.querySelector('textarea');
  field.getBoundingClientRect = () => ({ width });
  // Every style the field went through, in order (inline style attribute).
  const styles = new app.window.MutationObserver(() => {});
  styles.observe(field, { attributes: true, attributeFilter: ['style'], attributeOldValue: true });
  const history = () => [...styles.takeRecords().map(record => record.oldValue || ''), field.getAttribute('style') || ''];
  const resize = app.window.App.initComposerAutosize(field);
  return { ...app, field, resize, frames, history,
    tick() { const callbacks = [...frames.values()]; frames.clear(); callbacks.forEach(callback => callback()); },
    geometry(nextWidth = width) { width = nextWidth; onResize(); },
    // Typing is measured in the frame (the next tick), once per frame.
    input(text) { field.value = text; field.dispatchEvent(new app.window.Event('input')); this.tick(); },
    type(text) { field.value = text; field.dispatchEvent(new app.window.Event('input')); },
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

  it('measures the text, not the field: the field never shrinks for a moment (Apple audit A12, B5)', () => {
    const seen = [];
    const app = boot({ measure: (_, twin) => { seen.push(twin.value || twin.placeholder); return twin.value.length > 20 ? 76 : 52; } });
    app.tick();
    app.history();
    app.input('A first letter');
    app.input('A question that runs onto a second line');
    // Only the heights it settles on, never 0 px or another stand-in.
    const heights = app.history().map(style => /(?:^|;\s*)height: ([^;]+)/.exec(style)?.[1]).filter(Boolean);
    expect([...new Set(heights)]).toEqual(['52px', '76px']);
    expect(seen.at(-1)).toBe('A question that runs onto a second line');
    // An empty field is as tall as its hint.
    app.input('');
    expect(seen.at(-1)).toBe('Enter your question');
    app.dom.window.close();
  });

  it('measures typing once per frame, after the rest of the task wrote (Apple audit D3)', () => {
    let measured = 0;
    const app = boot({ measure: () => { measured += 1; return 52; } });
    app.tick();
    measured = 0;
    app.type('A'); app.type('An'); app.type('');
    expect(measured).toBe(0);
    app.tick();
    expect(measured).toBe(1);
    app.dom.window.close();
  });

  it('grows softly only while typing; a width or state change is instant', () => {
    let height = 52;
    const app = boot({ measure: () => height });
    const instant = () => app.history().some(style => /transition: none/.test(style));
    app.tick();
    expect(instant()).toBe(true);
    height = 76; app.input('Two lines of text in the start field');
    expect(app.field.style.height).toBe('76px');
    expect(instant()).toBe(false);
    height = 100; app.window.dispatchEvent(new app.window.Event('resize'));
    expect(app.field.style.height).toBe('100px');
    expect(instant()).toBe(true);
    // The transition is handed back to the stylesheet each time.
    expect(app.field.style.transition).toBe('');
    app.dom.window.close();
  });

  it('sizes a field before anything is installed (app-bootstrap.js, first frame)', () => {
    const app = loadScripts(["static/js/composer-autosize.js"], {
      body: '<div class="chat-input-container"><textarea style="min-height:52px;max-height:180px"></textarea></div>',
      before(window) {
        Object.defineProperty(window.HTMLTextAreaElement.prototype, 'scrollHeight', {
          configurable: true, get() { return this.classList.contains('input-field-twin') ? 120 : 0; } });
      },
    });
    const field = app.document.querySelector('textarea');
    field.getBoundingClientRect = () => ({ width: 300 });
    field.value = 'A question waiting for the sign-in';
    app.window.App.sizeQuestionInput(field);
    expect(field.style.height).toBe('120px');
    expect(field.parentElement.classList.contains('is-multiline')).toBe(true);
    // The twin is not part of the page for anyone else.
    const twin = app.document.querySelector('.input-field-twin');
    expect(twin.getAttribute('aria-hidden')).toBe('true');
    expect(twin.tabIndex).toBe(-1);
    expect(twin.id).toBe('');
    app.dom.window.close();
  });

  it('ignores the same hint written again while the field grows', async () => {
    let measured = 0;
    const app = boot({ measure: () => { measured += 1; return 52; } });
    app.tick();
    measured = 0;
    app.field.placeholder = 'Enter your question';
    await Promise.resolve();
    expect(measured).toBe(0);
    app.dom.window.close();
  });

  it('still responds to placeholder changes and explicit viewport changes', async () => {
    const app = boot({ measure: (_, twin) => twin.placeholder.length > 30 ? 190 : 52 });
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

  it('measures nothing while the field is not shown (Watches hides the chat column)', () => {
    // At width 0 every word of the twin breaks onto its own line.
    const app = boot({ measure: width => width > 0 ? 52 : 900 });
    app.tick();
    app.input('Is that right?');
    expect(app.field.parentElement.classList.contains('is-multiline')).toBe(false);
    app.geometry(0); app.tick();
    app.window.dispatchEvent(new app.window.Event('resize'));
    // Back in the chat the one-line question keeps its one-line form.
    app.geometry(350); app.tick();
    expect(app.field.parentElement.classList.contains('is-multiline')).toBe(false);
    expect(app.field.style.height).toBe('52px');
    app.dom.window.close();
  });
});
