import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

function boot({ reduced = false, mode = "agent" } = {}) {
  let y = 0, height = 3200, now = 0, serial = 0, resize;
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
  result.window.App.chatScroll.project(visible);
  return { ...result, frames,
    tick(count = 40) { for (let i = 0; i < count; i++) { now += 16; const current = [...frames.values()]; frames.clear(); current.forEach(fn => fn(now)); } },
    grow(amount) { height += amount; resize(); },
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
    const activity = app.document.querySelector('#threadAsk');
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

  it('ends automatic following when the response finishes', () => {
    const app = boot();
    app.window.App.revealSentMessage(); app.tick();
    app.show({runId:'one', finishedAt:123, config:{executionMode:'agent', agentMode:true}});
    app.window.scrollTo.mockClear(); app.grow(400); app.tick();
    expect(app.window.scrollTo).not.toHaveBeenCalled();
    expect(app.document.body.classList.contains('chat-scroll-following')).toBe(false);
    app.dom.window.close();
  });
  it.each(['agent', 'consensus'])('opens a saved %s conversation with one cancellable smooth jump', mode => {
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

  it("smoothly reaches the end and follows growing agent output despite a hidden pending bubble", () => {
    const app = boot();
    app.window.App.revealSentMessage();
    app.tick(8);
    expect(app.window.scrollY).toBeGreaterThan(0);
    expect(app.window.scrollY).toBeLessThan(2400);
    app.grow(800); app.tick();
    expect(app.window.scrollY).toBe(3200);
    app.grow(500); app.tick();
    expect(app.window.scrollY).toBe(3700);
    expect(app.window.scrollTo.mock.calls.every(([value]) => value.behavior === "instant")).toBe(true);
    app.dom.window.close();
  });

  it.each([false, true])("keeps consensus still after a single jump, including fast deltas and reduced motion: %s", reduced => {
    const app = boot({ mode: "consensus", reduced });
    app.window.App.revealSentMessage();
    app.grow(800); app.tick();
    expect(app.window.scrollY).toBe(2400);
    app.grow(500); app.tick();
    expect(app.window.scrollY).toBe(2400);
    const button = app.document.querySelector(".chat-scroll-latest");
    expect(button.hidden).toBe(false);
    button.click();
    app.grow(600); app.tick();
    expect(app.window.scrollY).toBe(3700);
    expect(button.hidden).toBe(false);
    button.click(); app.tick();
    expect(app.window.scrollY).toBe(4300);
    expect(button.hidden).toBe(true);
    app.grow(500); app.tick();
    expect(app.window.scrollY).toBe(4300);
    app.wheel(300); app.scroll(4800); app.grow(200); app.tick();
    expect(app.window.scrollY).toBe(4800);
    expect(button.hidden).toBe(false);
    app.dom.window.close();
  });

  it("gives the reader control even before the first frame, then offers a keyboard usable return", () => {
    const app = boot();
    app.window.App.revealSentMessage(); app.wheel(); app.tick();
    expect(app.window.scrollTo).not.toHaveBeenCalled();
    app.grow(500); app.tick();
    expect(app.window.scrollY).toBe(0);
    const button = app.document.querySelector(".chat-scroll-latest");
    expect(button.hidden).toBe(false);
    button.click(); app.tick();
    expect(app.window.scrollY).toBe(2900);
    expect(app.document.activeElement.id).toBe("questionInput");
    expect(button.hidden).toBe(true);
    app.wheel(); app.scroll(600); app.grow(1000); app.tick();
    expect(app.window.scrollY).toBe(600);
    app.wheel(300); app.scroll(3850); app.grow(300); app.tick();
    expect(app.window.scrollY).toBe(4200);
    app.dom.window.close();
  });

  it("never resumes from layout scrolls and cancels on a different run, saved view or account", () => {
    const app = boot();
    app.window.App.revealSentMessage(); app.tick(8);
    app.show({ runId: "two", config: { executionMode: "agent" } });
    app.window.scrollTo.mockClear();
    app.scroll(2400); app.grow(500); app.tick();
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

  it("interrupts a finger gesture and resumes only when swiping back to the end", () => {
    const app = boot();
    const touch = (type, y) => {
      const event = new app.window.Event(type);
      event.touches = [{ clientY: y }];
      app.window.dispatchEvent(event);
    };
    app.window.App.revealSentMessage(); app.tick();
    touch("touchstart", 200); touch("touchmove", 500); app.scroll(800);
    app.grow(1000); app.tick();
    expect(app.window.scrollY).toBe(800);
    touch("touchstart", 500); touch("touchmove", 200); app.scroll(3350);
    app.grow(300); app.tick();
    expect(app.window.scrollY).toBe(3700);
    app.dom.window.close();
  });

  it("respects reduced motion and viewport/composer changes without scrolling upwards", () => {
    const app = boot({ reduced: true });
    app.window.App.revealSentMessage(); app.tick(2);
    expect(app.window.scrollTo).toHaveBeenCalledTimes(1);
    expect(app.window.scrollY).toBe(2400);
    app.window.innerHeight = 500;
    app.window.dispatchEvent(new app.window.Event("resize")); app.tick();
    expect(app.window.scrollY).toBe(2700);
    app.window.scrollTo.mockClear(); app.grow(-500); app.tick();
    expect(app.window.scrollTo).not.toHaveBeenCalled();
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
