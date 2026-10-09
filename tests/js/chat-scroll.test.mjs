import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// The page scrolls like ChatGPT/Claude: Send brings the newest question to
// the top once, nothing follows streamed output, "Latest message" and opening
// a conversation jump to the end once. Geometry is faked: `askAt` is the
// question's document position, `height` the document height.
function boot({ reduced = false, mode = "agent", askAt = 2000 } = {}) {
  let y = 0, height = 3200, now = 0, serial = 0, resize, ask = askAt;
  const frames = new Map();
  let visible = { runId: "one", config: { executionMode: mode, agentMode: true } };
  let basis = null;
  const result = loadScripts(["static/js/app-core.js", "static/js/chat-scroll.js"], {
    body: '<main class="container"><div id="threadPendingAsk" hidden></div><div id="threadAsk">New question</div><section class="input-section"><textarea id="questionInput"></textarea></section></main>',
    before(window) {
      window.matchMedia = () => ({ matches: reduced });
      window.App = { runRegistry: { visible: () => visible, isAuthCurrent: () => true, getSelectedConversationIdentity: () => basis } };
      Object.defineProperty(window, "scrollY", { get: () => y });
      Object.defineProperty(window.document.documentElement, "scrollHeight", { get: () => height });
      window.innerHeight = 800;
      window.performance.now = () => now;
      window.requestAnimationFrame = fn => { const id = ++serial; frames.set(id, fn); return id; };
      window.cancelAnimationFrame = id => frames.delete(id);
      window.scrollTo = vi.fn(({ top }) => { y = top; window.dispatchEvent(new window.Event("scroll")); });
      window.ResizeObserver = class { constructor(fn) { resize = fn; } observe() {} };
    }
  });
  const { document } = result;
  // As in the app (base.css); jsdom's default is 8px.
  document.body.style.margin = "0";
  const question = document.getElementById("threadAsk");
  question.getClientRects = () => [{}];
  question.getBoundingClientRect = () => ({ top: ask - y, bottom: ask + 40 - y });
  const column = document.querySelector(".container");
  column.getBoundingClientRect = () => ({ top: -y, bottom: height - y });
  column.getClientRects = () => [{}];
  result.window.App.chatScroll.project(visible);
  // The reserve closes the content; the composer has no height here.
  document.querySelector(".chat-scroll-reserve").getBoundingClientRect = () => ({ top: height - y, bottom: height - y });
  return { ...result, frames,
    tick(count = 40) { for (let i = 0; i < count; i++) { now += 16; const current = [...frames.values()]; frames.clear(); current.forEach(fn => fn(now)); } },
    grow(amount) { height += amount; resize(); },
    moveAsk(to) { ask = to; },
    wheel(delta = -100) { result.window.dispatchEvent(new result.window.WheelEvent("wheel", { deltaY: delta })); },
    scroll(top) { y = top; result.window.dispatchEvent(new result.window.Event("scroll")); },
    show(next) { visible = next; result.window.App.chatScroll.project(next); },
    saved(id = 'saved') { visible = null; basis = { bookmarkId: id, executionMode: mode }; result.window.App.chatScroll.project(null); },
  };
}

describe("conversation scroll", () => {
  it('keeps the reading position when offscreen activity shrinks, including native anchoring', () => {
    const app = boot();
    app.scroll(1200);
    const activity = app.document.createElement('div');
    app.document.querySelector('.container').prepend(activity);
    let bottom = 900;
    activity.getBoundingClientRect = () => ({bottom: bottom - app.window.scrollY});
    let restore = app.window.App.chatScroll.preserveAbove(activity);
    bottom -= 240;
    restore();
    expect(app.window.scrollY).toBe(960);
    restore = app.window.App.chatScroll.preserveAbove(activity);
    bottom -= 180;
    app.scroll(780); // Browser already compensated for this layout change.
    app.window.scrollTo.mockClear();
    restore();
    expect(app.window.scrollY).toBe(780);
    expect(app.window.scrollTo).not.toHaveBeenCalled();
    app.scroll(0);
    expect(app.window.App.chatScroll.preserveAbove(activity)).toBeNull();
    app.dom.window.close();
  });

  it.each(['agent', 'consensus'])('Send brings the %s question to the top once and never follows the answer', mode => {
    const app = boot({ mode });
    app.window.App.revealSentMessage(); app.tick(8);
    expect(app.window.scrollY).toBeGreaterThan(0);
    expect(app.window.scrollY).toBeLessThan(2000);
    app.tick();
    expect(app.window.scrollY).toBe(2000);
    expect(app.document.body.classList.contains('chat-scroll-following')).toBe(false);
    app.window.scrollTo.mockClear();
    app.grow(900); app.tick();
    app.show({ runId: 'one', finishedAt: 123, config: { executionMode: mode, agentMode: true } });
    app.grow(48); app.tick();
    expect(app.window.scrollTo).not.toHaveBeenCalled();
    expect(app.window.scrollY).toBe(2000);
    app.dom.window.close();
  });

  it('follows the question while the thread settles during the jump', () => {
    const app = boot();
    app.window.App.revealSentMessage(); app.tick(6);
    app.moveAsk(2300); // The previous turn moved into the history above it.
    app.tick();
    expect(app.window.scrollY).toBe(2300);
    app.dom.window.close();
  });

  it('stops at the end when the question cannot reach the top', () => {
    const app = boot({ askAt: 3000 });
    app.window.App.revealSentMessage(); app.tick();
    expect(app.window.scrollY).toBe(2400);
    app.dom.window.close();
  });

  it('sizes the reserve so a short turn can sit at the top without lengthening the page later', () => {
    const app = boot({ askAt: 100 });
    const reserve = app.document.querySelector('.chat-scroll-reserve');
    expect(reserve).not.toBeNull();
    reserve.getBoundingClientRect = () => ({ top: 400 - app.window.scrollY });
    app.grow(0);
    // 800 viewport - 0 landing - 300 turn - 0 below.
    expect(reserve.style.height).toBe('500px');
    app.document.body.classList.add('is-hero');
    app.grow(0);
    expect(reserve.style.height).toBe('0px');
    app.dom.window.close();
  });

  it.each(['agent', 'consensus'])('opens a saved %s conversation with one cancellable smooth jump to its end', mode => {
    const app = boot({ mode });
    app.saved(); app.window.App.chatScroll.opened(); app.tick(8);
    expect(app.window.scrollY).toBeGreaterThan(0);
    expect(app.window.scrollY).toBeLessThan(2400);
    app.grow(500); app.tick();
    expect(app.window.scrollY).toBe(2900);
    app.grow(500); app.tick();
    expect(app.window.scrollY).toBe(2900);
    app.scroll(0); app.window.App.chatScroll.opened(); app.wheel(); app.tick();
    expect(app.window.scrollY).toBe(0);
    app.window.App.chatScroll.opened(); app.saved('different'); app.tick();
    expect(app.window.scrollY).toBe(0);
    app.window.App.chatScroll.opened(); app.window.App.runRegistry.isAuthCurrent = () => false; app.tick();
    expect(app.window.scrollY).toBe(0);
    app.dom.window.close();
  });

  it("offers a keyboard usable return to the latest message that jumps once", () => {
    const app = boot();
    app.window.App.revealSentMessage(); app.tick();
    const button = app.document.querySelector(".chat-scroll-latest");
    expect(button.hidden).toBe(false); // 2000 of 2400: more than the near-end band.
    app.grow(1000);
    expect(button.hidden).toBe(false);
    button.click(); app.tick();
    expect(app.window.scrollY).toBe(3400);
    expect(app.document.activeElement.id).toBe("questionInput");
    expect(button.hidden).toBe(true);
    app.grow(500); app.tick();
    expect(app.window.scrollY).toBe(3400);
    expect(button.hidden).toBe(false);
    app.dom.window.close();
  });

  it("keeps the Latest message jump on the end it was pressed for while text streams in", () => {
    const app = boot();
    app.window.App.revealSentMessage(); app.tick();
    app.grow(1000);
    app.document.querySelector(".chat-scroll-latest").click(); app.tick(8);
    app.grow(1800); app.tick();
    expect(app.window.scrollY).toBe(3400);
    app.dom.window.close();
  });

  it("gives the reader control even before the first frame", () => {
    const app = boot();
    app.window.App.revealSentMessage(); app.wheel(); app.tick();
    expect(app.window.scrollTo).not.toHaveBeenCalled();
    app.window.App.revealSentMessage(); app.tick(4);
    const touch = new app.window.Event("touchstart");
    touch.touches = [{ clientY: 200 }];
    app.window.dispatchEvent(touch);
    const stopped = app.window.scrollY;
    app.tick();
    expect(app.window.scrollY).toBe(stopped);
    expect(stopped).toBeLessThan(2000);
    app.dom.window.close();
  });

  it("cancels on a different run, a cleared view or another account", () => {
    const app = boot();
    app.window.App.revealSentMessage(); app.tick(3);
    app.show({ runId: "two", config: { executionMode: "agent" } });
    app.window.scrollTo.mockClear();
    app.tick();
    expect(app.window.scrollTo).not.toHaveBeenCalled();
    app.window.App.revealSentMessage(); app.show(null); app.tick();
    expect(app.window.scrollTo).not.toHaveBeenCalled();
    app.show({ runId: "three", config: { executionMode: "agent" } });
    app.window.App.revealSentMessage();
    app.window.App.runRegistry.isAuthCurrent = () => false;
    app.tick();
    expect(app.window.scrollTo).not.toHaveBeenCalled();
    app.dom.window.close();
  });

  it("respects reduced motion with a single immediate jump", () => {
    const app = boot({ reduced: true });
    app.window.App.revealSentMessage(); app.tick(2);
    expect(app.window.scrollTo).toHaveBeenCalledTimes(1);
    expect(app.window.scrollY).toBe(2000);
    expect(app.window.scrollTo.mock.calls.every(([value]) => value.behavior === "instant")).toBe(true);
    app.window.innerHeight = 500;
    app.window.dispatchEvent(new app.window.Event("resize")); app.tick();
    expect(app.window.scrollTo).toHaveBeenCalledTimes(1);
    app.dom.window.close();
  });

  it("stops for text selection, dialogs and direct comparison", () => {
    const app = boot();
    app.window.App.revealSentMessage();
    app.window.getSelection = () => ({ isCollapsed: false });
    app.document.dispatchEvent(new app.window.Event("selectionchange")); app.tick();
    expect(app.window.scrollTo).not.toHaveBeenCalled();
    app.window.getSelection = () => ({ isCollapsed: true });
    app.document.body.insertAdjacentHTML("beforeend", "<dialog open>Read this</dialog>");
    app.window.App.revealSentMessage(); app.tick();
    expect(app.window.scrollTo).not.toHaveBeenCalled();
    app.document.querySelector("dialog").remove();
    app.show({ runId: "direct", config: { agentMode: false } });
    app.window.App.revealSentMessage(); app.tick();
    expect(app.window.scrollTo).not.toHaveBeenCalled();
    app.dom.window.close();
  });
});
