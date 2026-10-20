import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// The shared "… · Undo" line (Apple audit E2): the way back first, the
// step itself only once the line ran out.
function boot() {
  const app = loadScripts(["static/js/undo-notice.js"], {
    before(window) { window.matchMedia = () => ({ matches: true }); },
  });
  return { ...app, notices: app.window.App.undoNotice };
}

describe("undo notice", () => {
  it("runs the step only when the line runs out, and Undo instead of it", () => {
    vi.useFakeTimers();
    const { notices, document, dom } = boot();
    const first = { onAction: vi.fn(), onExpire: vi.fn() };
    notices.show({ text: "Chat deleted", duration: 5000, ...first });
    const line = document.getElementById("undoNotice");
    expect(line.hidden).toBe(false);
    expect(line.textContent).toContain("Chat deleted");
    expect(line.getAttribute("role")).toBe("status");
    vi.advanceTimersByTime(4900);
    expect(first.onExpire).not.toHaveBeenCalled();
    vi.advanceTimersByTime(200);
    expect(first.onExpire).toHaveBeenCalledOnce();
    expect(first.onAction).not.toHaveBeenCalled();

    const second = { onAction: vi.fn(), onExpire: vi.fn() };
    notices.show({ text: "Chat deleted", ...second });
    line.querySelector(".undo-notice-action").click();
    expect(second.onAction).toHaveBeenCalledOnce();
    vi.advanceTimersByTime(10000);
    expect(second.onExpire).not.toHaveBeenCalled();
    vi.useRealTimers();
    dom.window.close();
  });

  it("settles the line before it when a new one comes, and pauses while pointed at", () => {
    vi.useFakeTimers();
    const { notices, document, window, dom } = boot();
    const first = { onAction: vi.fn(), onExpire: vi.fn() };
    const second = { onAction: vi.fn(), onExpire: vi.fn() };
    notices.show({ text: "One", ...first });
    notices.show({ text: "Two", duration: 3000, ...second });
    expect(first.onExpire).toHaveBeenCalledOnce();
    const line = document.getElementById("undoNotice");
    line.dispatchEvent(new window.Event("pointerenter"));
    vi.advanceTimersByTime(10000);
    expect(second.onExpire).not.toHaveBeenCalled();
    line.dispatchEvent(new window.Event("pointerleave"));
    vi.advanceTimersByTime(3100);
    expect(second.onExpire).toHaveBeenCalledOnce();
    // settle() and cancel() end it now.
    const third = { onAction: vi.fn(), onExpire: vi.fn() };
    notices.show({ text: "Three", ...third }).cancel();
    expect(third.onExpire).not.toHaveBeenCalled();
    const fourth = { onAction: vi.fn(), onExpire: vi.fn() };
    notices.show({ text: "Four", ...fourth }).settle();
    expect(fourth.onExpire).toHaveBeenCalledOnce();
    expect(notices.current()).toBeNull();
    vi.useRealTimers();
    dom.window.close();
  });
});
