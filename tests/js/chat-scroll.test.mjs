import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// The page scrolls like ChatGPT/Claude: Send brings the newest question to
// the top once, nothing follows streamed output, "Latest message" and opening
// a conversation jump to the end once. Geometry is faked: `askAt` is the
// question's document position, `height` the document height.
function boot({ reduced = false, mode = "agent", askAt = 2000, executing = false } = {}) {
  let y = 0, height = 3200, now = 0, serial = 0, resize, ask = askAt;
  const frames = new Map();
  let visible = { runId: "one", config: { executionMode: mode, agentMode: true } };
  let basis = null;
  const result = loadScripts(["static/js/app-core.js", "static/js/chat-scroll.js"], {
    body: '<main class="container"><div id="threadPendingAsk" hidden></div><div id="threadAsk">New question</div><section class="input-section"><textarea id="questionInput"></textarea></section></main>',
    before(window) {
      window.matchMedia = () => ({ matches: reduced });
      window.App = { runRegistry: { visible: () => visible, isAuthCurrent: () => true, getSelectedConversationIdentity: () => basis,
        isExecuting: runId => executing && runId === visible?.runId } };
      Object.defineProperty(window, "scrollY", { get: () => y });
      // With a working run, the column's floor (its min-height) holds the
      // page as the layout would: the page is at least that tall.
      const floor = () => executing ? parseFloat(/([\d.]+)px\)$/.exec(window.document.querySelector(".container")?.style.minHeight || "")?.[1]) || 0 : 0;
      Object.defineProperty(window.document.documentElement, "scrollHeight", { get: () => Math.max(height, floor()) });
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
  // The column is as tall as its floor, at least (min-height).
  const floor = () => parseFloat(/([\d.]+)px\)$/.exec(column.style.minHeight || "")?.[1]) || 0;
  column.getBoundingClientRect = () => ({ top: -y, bottom: (executing ? Math.max(height, floor()) : height) - y });
  column.getClientRects = () => [{}];
  result.window.App.chatScroll.project(visible);
  // The reserve closes the content; the composer has no height here.
  // With a floor above the content, the reserve fills the room between them.
  document.querySelector(".chat-scroll-reserve").getBoundingClientRect = () => ({ top: height - y,
    bottom: (executing ? Math.max(height, floor()) : height) - y });
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

  // The column holds the page's end (its minimum height) and the reserve
  // takes what the turn leaves of it in the same layout: a turn that gets
  // shorter cannot shorten the page for a frame and clamp the scroll offset.
  const floorOf = app => app.document.querySelector('.container').style.minHeight;
  it('ends the page one viewport below the question while the turn is short', () => {
    const app = boot({ askAt: 100 });
    expect(app.document.querySelector('.chat-scroll-reserve')).not.toBeNull();
    app.grow(0);
    // 100 question offset - 0 landing + 800 viewport - 0 above and below the column.
    expect(floorOf(app)).toBe('max(calc(100dvh - 10px), 900px)');
    app.document.body.classList.add('is-hero');
    app.grow(0);
    expect(floorOf(app)).toBe('');
    app.dom.window.close();
  });

  // The live lines are 20.8px tall: an end at the turn's own fraction moved
  // with every line, and at the end of the page every line that crossed a
  // pixel pulled the chat 1px down and back. The end does not depend on the
  // turn at all: one viewport below the whole-pixel offset of the question.
  it('ends the page at the same place whatever the turn does', () => {
    const app = boot({ askAt: 100.3 });
    const reserve = app.document.querySelector('.chat-scroll-reserve');
    const floors = new Set();
    for (const top of [400.6, 421.397, 442.194, 457.563, 478.36]) {
      reserve.getBoundingClientRect = () => ({ top: top - app.window.scrollY });
      app.grow(0);
      floors.add(floorOf(app));
    }
    expect([...floors]).toEqual(['max(calc(100dvh - 10px), 900px)']);
    app.dom.window.close();
  });

  // The reviewers finish while the reader types the next question: a row
  // that gets shorter at the end of a long turn pulled the chat down.
  it('never lets the column of a working run get shorter, until the next run', () => {
    const app = boot({ askAt: 100, executing: true });
    app.grow(0);
    expect(floorOf(app)).toBe('max(calc(100dvh - 10px), 3200px)');
    app.grow(-300);
    expect(floorOf(app)).toBe('max(calc(100dvh - 10px), 3200px)');
    app.show({ runId: 'two', config: { executionMode: 'agent', agentMode: true } });
    app.grow(0);
    expect(floorOf(app)).toBe('max(calc(100dvh - 10px), 2900px)');
    app.dom.window.close();
  });

  // A reader at the end of a long working turn while the activity above
  // grows: the floor that held a taller moment of the run took the growth
  // into the reserve below, and the text in view moved down (2026-10-30).
  it('lets the floor grow with what grows above a reader at the end', () => {
    const app = boot({ askAt: 100, executing: true });
    app.grow(60); app.grow(-60);
    expect(floorOf(app)).toBe('max(calc(100dvh - 10px), 3260px)');
    app.scroll(2460);
    const activity = app.document.createElement('div');
    app.document.querySelector('.container').prepend(activity);
    let bottom = 900;
    activity.getBoundingClientRect = () => ({ bottom: bottom - app.window.scrollY });
    const restore = app.window.App.chatScroll.preserveAbove(activity);
    bottom += 24.8; app.grow(24.8);
    restore();
    expect(app.window.scrollY).toBeCloseTo(2484.8, 3);
    app.dom.window.close();
  });

  it.each(['agent', 'consensus'])('opens a saved %s conversation at its newest question before the first frame, without a ride', mode => {
    const app = boot({ mode });
    app.saved(); app.window.App.chatScroll.opened();
    // Written at once, as one instant scroll: no frame shows the top first.
    expect(app.window.scrollY).toBe(2000);
    expect(app.window.scrollTo).toHaveBeenCalledTimes(1);
    expect(app.window.scrollTo.mock.calls[0][0].behavior).toBe('instant');
    // More content below (late layout) does not pull it to the end.
    app.grow(500); app.tick(4);
    expect(app.window.scrollY).toBe(2000);
    // The question settling a little is followed while the view settles ...
    app.moveAsk(2060); app.tick(4);
    expect(app.window.scrollY).toBe(2060);
    expect(app.window.scrollTo.mock.calls.every(([value]) => value.behavior === 'instant')).toBe(true);
    // ... and never after it.
    app.tick(40); app.moveAsk(2300); app.tick();
    expect(app.window.scrollY).toBe(2060);
    // The reader takes over at once; another view or account writes nothing.
    app.scroll(0); app.moveAsk(2000); app.window.App.chatScroll.opened(); app.wheel(); app.moveAsk(2100); app.tick();
    expect(app.window.scrollY).toBe(2000);
    app.scroll(0); app.window.scrollTo.mockClear();
    app.saved('different'); app.window.App.runRegistry.isAuthCurrent = () => false; app.window.App.chatScroll.opened(); app.tick();
    expect(app.window.scrollTo).not.toHaveBeenCalled();
    app.dom.window.close();
  });

  it('opens a short chat with its question below the header, not cut off at the end', () => {
    // A phone: the question sits right under the column's top padding.
    const app = boot({ askAt: 88 });
    app.document.querySelector('.container').style.paddingTop = '46px';
    app.document.getElementById('threadAsk').style.marginTop = '10px';
    app.document.querySelector('.container').getBoundingClientRect = () => ({ top: 32 - app.window.scrollY, bottom: 3200 - app.window.scrollY });
    app.saved(); app.window.App.chatScroll.opened(); app.tick();
    expect(app.window.scrollY).toBe(0);
    app.dom.window.close();
  });

  it("returns an opened chat to a given place once, held while it settles, with no ride (Apple-Audit B7)", () => {
    const app = boot();
    let place = 1234;
    app.saved();
    app.window.App.chatScroll.returnTo(() => place);
    app.window.App.chatScroll.opened();
    // At once, not glided there from the top.
    expect(app.window.scrollY).toBe(1234);
    expect(app.window.scrollTo.mock.calls.map(([options]) => options.top)).toEqual([1234]);
    // Late layout moves the place: the next frames follow it.
    place = 1300; app.tick(3);
    expect(app.window.scrollY).toBe(1300);
    app.tick();
    // The next opened chat stands at its newest question again.
    app.scroll(0); app.saved('other'); app.window.App.chatScroll.opened(); app.tick();
    expect(app.window.scrollY).toBe(2000);
    app.dom.window.close();
  });

  it("offers a keyboard usable return to the latest message that jumps once", () => {
    const app = boot();
    app.window.App.revealSentMessage(); app.tick();
    const button = app.document.querySelector(".chat-scroll-latest");
    // It comes once the end stays out of reach for half a second (2026-10-28:
    // live lines that grew and folded made it flash), not in the jump's frames.
    expect(button.hidden).toBe(true);
    app.tick();
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

  it("does not flash Latest message while live lines grow and fold back", () => {
    const app = boot();
    app.window.App.revealSentMessage(); app.tick(80);
    const button = app.document.querySelector(".chat-scroll-latest");
    button.click(); app.tick(80);
    expect(button.hidden).toBe(true);
    // A few live lines push the end out of reach and fold again within a moment.
    app.grow(300); app.tick(10);
    expect(button.hidden).toBe(true);
    app.grow(-300); app.tick(80);
    expect(button.hidden).toBe(true);
    // Out of reach for good: then it comes.
    app.grow(300); app.tick(40);
    expect(button.hidden).toBe(false);
    app.dom.window.close();
  });

  it("waits for Latest message without a frame loop while the end is just out of reach", () => {
    const app = boot();
    app.window.App.revealSentMessage(); app.tick(80);
    const button = app.document.querySelector(".chat-scroll-latest");
    button.click(); app.tick(80);
    expect(button.hidden).toBe(true);
    // 120px above the end: past the near-end band, not far enough for the
    // button. Idle, no frame stays scheduled (bug hunt 2026-10-30: one per
    // frame, 3750 in a minute).
    app.scroll(2280); app.tick(80);
    expect(button.hidden).toBe(true);
    expect(app.frames.size).toBe(0);
    // Further up, the button comes as before.
    app.scroll(2000); app.tick(40);
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
